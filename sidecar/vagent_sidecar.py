"""
vagent_sidecar.py — V-Agent Python sidecar

Two protocols on the same binary:

1. Legacy single-shot (request has NO "type"):
       {"messages": [...], "config": {...}, "system_prompt": "..."}
   → streams {"token": ...} lines, ends with {"done": true}.

2. Persistent agent (request has "type"), used by the bidirectional bridge:
       {"type":"chat","id":..,"messages":[..],"config":{..},"cwd":..,
        "system_prompt":..,"agent":true,"plan":false}
       {"type":"cancel","id":..}
       {"type":"load_session"} / {"type":"clear_session"}
   → streams events: token / tool_call / tool_result / propose_write /
     propose_command / info / error / done  (each with the request "id").

Read-only tools (read_file, list_dir, search_in_files) run here. write_file and
run_command are surfaced to the UI as proposals (never auto-applied). Tool calls
use a provider-agnostic XML protocol, so every existing provider works unchanged.
"""

import sys
import os
import re
import json
import threading
from pathlib import Path

from llm_provider import build_provider, LLMError, LLMRateLimitError

# ── Output (thread-safe) ───────────────────────────────────────────────────────

_emit_lock = threading.Lock()


def emit(obj: dict) -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


# ── Session persistence ────────────────────────────────────────────────────────

def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", ".")) / "VAgent"
    return Path(os.environ.get("HOME", ".")) / ".config" / "VAgent"


SESSION_PATH = config_dir() / "session.json"


def load_session() -> list:
    try:
        return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_session(messages: list) -> None:
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        SESSION_PATH.write_text(json.dumps(messages[-60:]), encoding="utf-8")
    except Exception:
        pass


# ── Persisted credentials/config ────────────────────────────────────────────────
# The frontend only sends {ai_provider, model} per request — never API keys. Keys
# live in config.json (written by onboarding) and/or .env (written by Settings).
# Load them here so Groq/OpenRouter/Ollama actually receive their credentials
# instead of silently falling back to the backend provider.

def _persisted_config() -> dict:
    data: dict = {}
    try:
        cfg_path = config_dir() / "config.json"
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data.update(loaded)
    except Exception:
        pass
    try:
        env_path = config_dir() / ".env"
        env: dict = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
        if env.get("GROQ_API_KEY"):
            data["groq_api_key"] = env["GROQ_API_KEY"]
        if env.get("OPENROUTER_API_KEY"):
            data["openrouter_api_key"] = env["OPENROUTER_API_KEY"]
        if env.get("OLLAMA_MODEL"):
            data.setdefault("model", env["OLLAMA_MODEL"])
    except Exception:
        pass
    return data


def merged_config(req_cfg: dict) -> dict:
    """Request config wins; persisted keys/model fill in the gaps."""
    merged = _persisted_config()
    merged.update(req_cfg or {})
    return merged


# ── Extension system ──────────────────────────────────────────────────────────
# Extensions live in config_dir()/extensions/<id>/main.py and expose
# a register(vagent) function. vagent.add_tool() adds callable tools to
# the agentic loop. Errors in individual extensions are logged and skipped.

EXTENSION_TOOLS: dict = {}   # tool_name → fn(cwd, args) → str
EXTENSION_DOCS:  list = []   # extra tool doc lines appended to TOOLS_DOC


class VagentContext:
    """API surface passed to extension register() functions."""

    def add_tool(self, name: str, fn, description: str = "") -> None:
        """Register a tool callable from the agentic loop.
        fn signature: fn(cwd: str, args: dict) -> str
        """
        EXTENSION_TOOLS[name] = fn
        if description:
            EXTENSION_DOCS.append(
                f'<tool_call>{{"tool": "{name}", "args": {{}}}}</tool_call>\n{description}'
            )


def load_extensions() -> None:
    """Discover and load all extensions installed under config_dir()/extensions/."""
    import importlib.util

    ext_dir = config_dir() / "extensions"
    if not ext_dir.exists():
        return

    ctx = VagentContext()
    for path in sorted(ext_dir.iterdir()):
        if not path.is_dir():
            continue
        main_py = path / "main.py"
        if not main_py.exists():
            continue
        ext_id = path.name
        try:
            spec = importlib.util.spec_from_file_location(
                f"vagent_ext_{ext_id}", main_py
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            if hasattr(module, "register") and callable(module.register):
                module.register(ctx)
        except Exception as exc:
            print(
                f"[sidecar] extension '{ext_id}' failed to load: {exc}",
                file=sys.stderr,
            )


# ── Tools (read-only ones execute locally) ─────────────────────────────────────

SKIP_DIRS = {".git", "node_modules", "__pycache__", "target", "dist", "build", ".venv", "venv"}


def _resolve(cwd: str, rel: str) -> Path:
    return (Path(cwd) / rel).resolve()


def tool_read_file(cwd, args):
    try:
        return _resolve(cwd, args.get("path", "")).read_text(encoding="utf-8", errors="replace")[:12000]
    except Exception as e:
        return f"ERROR: {e}"


def tool_list_dir(cwd, args):
    try:
        p = _resolve(cwd, args.get("path", "."))
        names = []
        for e in sorted(os.scandir(p), key=lambda x: (not x.is_dir(), x.name.lower())):
            if e.name.startswith(".") or e.name in SKIP_DIRS:
                continue
            names.append(e.name + ("/" if e.is_dir() else ""))
        return "\n".join(names[:200]) or "(empty)"
    except Exception as e:
        return f"ERROR: {e}"


def tool_search(cwd, args):
    query = args.get("query", "")
    if not query:
        return "ERROR: empty query"
    out = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            fp = Path(root) / f
            try:
                if fp.stat().st_size > 1_000_000:
                    continue
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if query in line:
                            rel = os.path.relpath(fp, cwd)
                            out.append(f"{rel}:{i}: {line.strip()[:160]}")
                            if len(out) >= 60:
                                return "\n".join(out)
            except Exception:
                continue
    return "\n".join(out) if out else "(no matches)"


TOOLS_DOC = """You have tools. Use them proactively.

CRITICAL RULE: When the user asks to create, write, edit, or modify a file — always use write_file immediately. Never just show code in a code block without also proposing write_file. If the user wants a file created, create it.

Tool calls (one per line):
<tool_call>{"tool": "read_file", "args": {"path": "relative/path"}}</tool_call>
<tool_call>{"tool": "list_dir", "args": {"path": "."}}</tool_call>
<tool_call>{"tool": "search_in_files", "args": {"query": "text to find"}}</tool_call>
<tool_call>{"tool": "write_file", "args": {"path": "relative/path", "content": "FULL file content here"}}</tool_call>
<tool_call>{"tool": "run_command", "args": {"command": "shell command"}}</tool_call>

Rules:
- Paths are relative to the project root.
- read_file / list_dir / search_in_files execute immediately; you receive their output and may call more tools.
- write_file and run_command are shown to the user to Accept or Reject — always propose them, never skip.
- DEFAULT BEHAVIOR: If the user mentions a file by name and wants code written, use write_file. Do not ask for permission to write — just propose it.
- Only skip write_file if the user explicitly says 'just show me the code' or 'don't create a file'."""

TOOL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_tool_calls(text):
    calls = []
    for m in TOOL_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and obj.get("tool"):
                calls.append(obj)
        except Exception:
            continue
    return calls


def strip_tool_calls(text):
    return TOOL_RE.sub("", text).strip()


# ── Agentic loop ───────────────────────────────────────────────────────────────

_cancel = {}  # request id -> bool


def run_agent(req):
    rid = req.get("id")
    messages = req.get("messages", [])
    config = merged_config(req.get("config", {}))
    cwd = req.get("cwd") or os.getcwd()
    base_system = req.get("system_prompt", "") or ""
    agent = bool(req.get("agent", True))
    plan = bool(req.get("plan", False))

    _cancel[rid] = False

    def cancelled():
        return _cancel.get(rid, False)

    if plan:
        system = (base_system + "\n\nPLAN MODE: Provide a concise step-by-step plan only. Do NOT use tools or write code.").strip()
        use_tools = False
    elif agent:
        extra = ("\n\nExtension tools:\n" + "\n".join(EXTENSION_DOCS)) if EXTENSION_DOCS else ""
        system = (base_system + "\n\n" + TOOLS_DOC + extra).strip()
        use_tools = True
    else:
        system = base_system
        use_tools = False

    try:
        provider = build_provider(config, system)
    except Exception as e:
        emit({"type": "error", "id": rid, "error": f"provider: {e}"})
        emit({"type": "done", "id": rid})
        _cancel.pop(rid, None)
        return

    convo = list(messages)

    # Auto-trim history when it grows too large: keep last 5 + a note about what was dropped
    if len(convo) > 20:
        kept = convo[-5:]
        dropped = len(convo) - 5
        convo = [{"role": "user", "content": f"[{dropped} earlier messages trimmed to manage context length]"}] + kept

    call_seq = 0
    max_steps = 6 if use_tools else 1

    for _step in range(max_steps):
        if cancelled():
            break

        # Collect the full turn so we can detect tool calls before showing text.
        acc = ""
        try:
            for tok in provider.stream(convo, cancel_flag=cancelled):
                acc += tok
        except LLMRateLimitError:
            # Groq rate limited: try OpenRouter automatically
            or_key = config.get("openrouter_api_key", "").strip()
            if or_key:
                emit({"type": "info", "id": rid, "text": "Groq rate limited — switched to OpenRouter"})
                or_cfg = {**config, "ai_provider": "openrouter"}
                try:
                    or_provider = build_provider(or_cfg, system)
                    for tok in or_provider.stream(convo, cancel_flag=cancelled):
                        acc += tok
                except LLMError as e2:
                    emit({"type": "error", "id": rid, "error": str(e2)})
                    break
            else:
                emit({"type": "error", "id": rid, "error": "Groq rate limited. Add an OpenRouter key in Settings to auto-switch."})
                break
        except LLMError as e:
            emit({"type": "error", "id": rid, "error": str(e)})
            break
        except Exception as e:
            emit({"type": "error", "id": rid, "error": f"sidecar: {e}"})
            break

        calls = parse_tool_calls(acc) if use_tools else []

        if not calls:
            final = strip_tool_calls(acc) if agent else acc   # drop any stray tool XML
            for i in range(0, len(final), 24):       # stream the final answer
                if cancelled():
                    break
                emit({"type": "token", "id": rid, "text": final[i:i + 24]})
            convo.append({"role": "assistant", "content": final})
            break

        convo.append({"role": "assistant", "content": acc})
        results = []
        for call in calls:
            if cancelled():
                break
            call_seq += 1
            cid = f"{rid}-{call_seq}"
            tool = call.get("tool")
            args = call.get("args", {}) or {}
            emit({"type": "tool_call", "id": rid, "call_id": cid, "tool": tool, "args": args})

            if tool == "read_file":
                res = tool_read_file(cwd, args)
            elif tool == "list_dir":
                res = tool_list_dir(cwd, args)
            elif tool == "search_in_files":
                res = tool_search(cwd, args)
            elif tool == "write_file":
                original = ""
                try:
                    original = _resolve(cwd, args.get("path", "")).read_text(encoding="utf-8", errors="replace")[:20000]
                except Exception:
                    original = ""
                emit({"type": "propose_write", "id": rid, "call_id": cid,
                      "path": args.get("path", ""), "content": args.get("content", ""), "original": original})
                res = "Proposed to the user for approval (Accept/Reject)."
            elif tool == "run_command":
                emit({"type": "propose_command", "id": rid, "call_id": cid, "command": args.get("command", "")})
                res = "Command proposed to the user for approval."
            elif tool in EXTENSION_TOOLS:
                try:
                    res = EXTENSION_TOOLS[tool](cwd, args)
                except Exception as exc:
                    res = f"ERROR in extension tool '{tool}': {exc}"
            else:
                res = f"ERROR: unknown tool '{tool}'"

            emit({"type": "tool_result", "id": rid, "call_id": cid, "tool": tool, "result": res[:4000]})
            results.append(f"[{tool}] {res}")

        convo.append({"role": "user", "content": "Tool results:\n" + "\n\n".join(results)})
    else:
        emit({"type": "info", "id": rid, "text": "Reached the tool-step limit; answering with what I have."})

    save_session(convo)
    _cancel.pop(rid, None)
    emit({"type": "done", "id": rid})


# ── Legacy single-shot path ────────────────────────────────────────────────────

def handle_legacy(req):
    messages = req.get("messages", [])
    config = merged_config(req.get("config", {}))
    system_prompt = req.get("system_prompt", "")
    if not messages:
        emit({"error": "no messages provided"})
        emit({"done": True})
        return
    try:
        provider = build_provider(config, system_prompt)
        for token in provider.stream(messages):
            emit({"token": token})
        emit({"done": True})
    except LLMError as e:
        emit({"error": str(e)})
        emit({"done": True})
    except Exception as e:  # noqa: BLE001
        emit({"error": f"sidecar error: {e}"})
        emit({"done": True})


# ── Dispatch ───────────────────────────────────────────────────────────────────

def dispatch(req):
    t = req.get("type")
    if t is None:
        handle_legacy(req)
    elif t == "chat":
        threading.Thread(target=run_agent, args=(req,), daemon=True).start()
    elif t == "cancel":
        _cancel[req.get("id")] = True
    elif t == "load_session":
        emit({"type": "session", "messages": load_session()})
    elif t == "clear_session":
        save_session([])
        emit({"type": "session", "messages": []})
    else:
        emit({"type": "error", "error": f"unknown request type '{t}'"})


def main():
    load_extensions()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            emit({"type": "error", "error": "invalid JSON request"})
            continue
        try:
            dispatch(req)
        except Exception as e:  # noqa: BLE001 — never crash the loop
            emit({"type": "error", "error": f"dispatch: {e}"})


if __name__ == "__main__":
    main()
