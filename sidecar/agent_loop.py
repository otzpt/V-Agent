"""
agent_loop.py — Agentic tool-calling loop for V-Agent
Receives tool functions as an injected dict (avoids circular imports).
"""

import re
import json
from typing import Callable

from llm_provider import LLMError, LLMRateLimitError

TOOL_RE        = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
MAX_STEPS      = 10
MAX_STEPS_AUTO = 30

# Shell patterns considered destructive — always propose even in autonomous mode.
_DESTRUCTIVE_RE = re.compile(
    r"\b(rm\s+-[rRfF]*rf|rm\s+-[rRfF]*f|del\s+/[fqsF]|rmdir\s+/s|"
    r"git\s+(push\s+.*--force|push\s+-f)|DROP\s+TABLE|"
    r"format\s+[a-zA-Z]:|mkfs|dd\s+if=|shred\b)",
    re.IGNORECASE,
)


# ── XML tool parsing ──────────────────────────────────────────────────────────

def parse_tool_calls(text: str) -> list:
    calls = []
    for m in TOOL_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and obj.get("tool"):
                calls.append(obj)
        except Exception:
            continue
    return calls


def strip_tool_calls(text: str) -> str:
    return TOOL_RE.sub("", text).strip()


# ── Agent loop ────────────────────────────────────────────────────────────────

class AgentLoop:
    """
    Runs the multi-step agentic loop for a single request.

    Parameters
    ----------
    session_id      : str   — used only for logging/debugging
    provider        : LLMProvider instance to call for generation
    emit_fn         : callable(dict) → None  — sends events to the frontend
    local_tools     : {"read_file": fn(cwd, args)→str, "list_dir": ..., "search_in_files": ...}
    extension_tools : {"ext_tool_name": fn(cwd, args)→str, ...}
    mcp_servers     : {"server_name": {"url": "http://...", "tools": [...]}, ...}
    """

    def __init__(
        self,
        session_id: str,
        provider,
        emit_fn: Callable,
        local_tools: dict,
        extension_tools: dict | None = None,
        mcp_servers: dict | None     = None,
    ):
        self.session_id      = session_id
        self.provider        = provider
        self.emit            = emit_fn
        self.local_tools     = local_tools
        self.extension_tools = extension_tools or {}
        self.mcp_servers     = mcp_servers or {}
        self._call_seq       = 0

    def _next_cid(self, rid: str) -> str:
        self._call_seq += 1
        return f"{rid}-{self._call_seq}"

    def _is_destructive(self, command: str) -> bool:
        return bool(_DESTRUCTIVE_RE.search(command))

    def _exec_local(
        self, tool: str, args: dict, cwd: str, rid: str, cid: str,
        autonomous: bool = False, plan_confirmed: bool = False,
    ) -> str:
        if tool == "write_file":
            path    = args.get("path", "")
            content = args.get("content", "")
            original = ""
            try:
                from pathlib import Path as _Path
                full     = (_Path(cwd) / path).resolve()
                original = full.read_text(encoding="utf-8", errors="replace")[:20_000]
            except Exception:
                pass

            if autonomous and plan_confirmed:
                # Auto-apply: write the file directly without asking
                try:
                    from pathlib import Path as _Path
                    full = (_Path(cwd) / path).resolve()
                    full.parent.mkdir(parents=True, exist_ok=True)
                    full.write_text(content, encoding="utf-8")
                    self.emit({
                        "type":     "auto_write",  "id": rid, "call_id": cid,
                        "path":     path,           "content": content,
                        "original": original,
                    })
                    return f"Written: {path}"
                except Exception as e:
                    return f"ERROR writing {path}: {e}"
            else:
                # Normal (or first-write plan proposal)
                self.emit({
                    "type": "propose_write", "id": rid, "call_id": cid,
                    "path": path, "content": content, "original": original,
                })
                return "Proposed to the user for approval (Accept/Reject)."

        if tool == "run_command":
            command = args.get("command", "")
            # Destructive commands always require confirmation
            if autonomous and plan_confirmed and not self._is_destructive(command):
                self.emit({
                    "type":    "auto_command", "id": rid, "call_id": cid,
                    "command": command,
                })
                return f"Command sent to terminal: {command}"
            else:
                self.emit({
                    "type":    "propose_command", "id": rid, "call_id": cid,
                    "command": command,
                })
                return "Command proposed to the user for approval."

        fn = self.local_tools.get(tool)
        if fn:
            try:
                return fn(cwd, args)
            except Exception as e:
                return f"ERROR in {tool}: {e}"

        fn = self.extension_tools.get(tool)
        if fn:
            try:
                return fn(cwd, args)
            except Exception as e:
                return f"ERROR in extension tool '{tool}': {e}"

        return f"ERROR: unknown tool '{tool}'"

    def _exec_mcp(self, server_name: str, tool_name: str, args: dict) -> str:
        server = self.mcp_servers.get(server_name)
        if not server:
            return f"ERROR: MCP server '{server_name}' not configured."
        url = server.get("url", "").rstrip("/")
        if not url:
            return f"ERROR: MCP server '{server_name}' has no URL."
        try:
            import requests
            resp = requests.post(
                f"{url}/call",
                json={"tool": tool_name, "args": args},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("result", data))
        except Exception as e:
            return f"ERROR: MCP call to '{server_name}.{tool_name}' failed: {e}"

    def _dispatch(
        self, tool: str, args: dict, cwd: str, rid: str, cid: str,
        autonomous: bool = False, plan_confirmed: bool = False,
    ) -> str:
        if tool.startswith("mcp__"):
            parts = tool.split("__", 2)
            if len(parts) == 3:
                _, server_name, tool_name = parts
                return self._exec_mcp(server_name, tool_name, args)
            return f"ERROR: malformed MCP tool name '{tool}'"
        return self._exec_local(tool, args, cwd, rid, cid, autonomous, plan_confirmed)

    def run(
        self,
        rid: str,
        convo: list,
        cwd: str,
        use_tools: bool,
        cancelled: Callable,
        fallback_provider=None,
        autonomous: bool = False,
    ) -> list:
        """
        Run the loop. Modifies and returns the conversation.
        Emits token / tool_call / tool_result / propose_* / auto_write /
        progress / info / error events.
        """
        max_steps     = MAX_STEPS_AUTO if autonomous else MAX_STEPS
        plan_confirmed = not autonomous  # in normal mode, always "confirmed"
        step          = 0

        for _step in range(max_steps):
            if cancelled():
                break

            step = _step + 1
            if autonomous:
                self.emit({
                    "type":        "progress",
                    "id":          rid,
                    "step":        step,
                    "total":       "estimated",
                    "description": f"Step {step}…",
                })

            acc = ""
            try:
                for tok in self.provider.stream(convo, cancel_flag=cancelled):
                    acc += tok

            except LLMRateLimitError:
                if fallback_provider:
                    self.emit({"type": "info", "id": rid,
                               "text": "Rate limited — switched to fallback provider"})
                    try:
                        for tok in fallback_provider.stream(convo, cancel_flag=cancelled):
                            acc += tok
                    except LLMError as e2:
                        self.emit({"type": "error", "id": rid, "error": str(e2)})
                        break
                else:
                    self.emit({"type": "error", "id": rid,
                               "error": "Rate limited. Add an OpenRouter key in Settings to auto-switch."})
                    break

            except LLMError as e:
                self.emit({"type": "error", "id": rid, "error": str(e)})
                break
            except Exception as e:
                self.emit({"type": "error", "id": rid, "error": f"sidecar: {e}"})
                break

            calls = parse_tool_calls(acc) if use_tools else []

            if not calls:
                final = strip_tool_calls(acc) if use_tools else acc
                for i in range(0, len(final), 24):
                    if cancelled():
                        break
                    self.emit({"type": "token", "id": rid, "text": final[i:i + 24]})
                convo.append({"role": "assistant", "content": final})

                # In autonomous mode, check if the model signals completion
                if autonomous:
                    low = final.lower()
                    if any(kw in low for kw in ("task complete", "all done", "finished", "tarefa concluída", "concluído")):
                        self.emit({"type": "autonomous_done", "id": rid,
                                   "summary": final[:800]})
                break

            # First write_file in autonomous mode → propose the plan first
            if autonomous and not plan_confirmed:
                has_write = any(c.get("tool") == "write_file" for c in calls)
                if has_write:
                    plan_text = strip_tool_calls(acc)
                    self.emit({
                        "type":    "propose_plan",
                        "id":      rid,
                        "content": plan_text or "V-Agent will now execute the task autonomously.",
                    })
                    plan_confirmed = True

            convo.append({"role": "assistant", "content": acc})
            results = []

            for call in calls:
                if cancelled():
                    break
                tool = call.get("tool", "")
                args = call.get("args", {}) or {}
                cid  = self._next_cid(rid)

                if autonomous:
                    self.emit({
                        "type":        "progress",
                        "id":          rid,
                        "step":        step,
                        "total":       "estimated",
                        "description": f"{tool}: {args.get('path', args.get('command', '…'))}",
                    })

                self.emit({"type": "tool_call", "id": rid, "call_id": cid,
                           "tool": tool, "args": args})

                res = self._dispatch(tool, args, cwd, rid, cid, autonomous, plan_confirmed)

                self.emit({"type": "tool_result", "id": rid, "call_id": cid,
                           "tool": tool, "result": res[:4_000]})
                results.append(f"[{tool}] {res}")

            convo.append({"role": "user",
                          "content": "Tool results:\n" + "\n\n".join(results)})
        else:
            self.emit({"type": "info", "id": rid,
                       "text": "Reached the tool-step limit; answering with what I have."})
            if autonomous:
                self.emit({"type": "autonomous_done", "id": rid,
                           "summary": f"Completed {max_steps} steps."})

        return convo
