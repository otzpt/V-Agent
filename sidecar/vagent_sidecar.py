"""
vagent_sidecar.py — V-Agent Python sidecar  (v0.9.1)

Protocol (newline-delimited JSON on stdin/stdout):

  Legacy single-shot (no "type" field):
    {"messages": [...], "config": {...}, "system_prompt": "..."}
    → streams {"token": ...} lines, ends with {"done": true}

  Persistent agent:
    {"type":"chat",            "id":"..", "session_id":"..", "messages":[..],
     "config":{..}, "cwd":"..", "system_prompt":"..", "agent":true, "plan":false}
    {"type":"cancel",          "id":".."}
    {"type":"load_session",    "session_id":".."}
    {"type":"clear_session",   "session_id":".."}
    {"type":"compact_session", "session_id":".."}
    {"type":"get_context",     "session_id":"..", "model":".."}

  Emitted events:
    token / tool_call / tool_result / propose_write / propose_command /
    info / error / done / session / context
"""

import sys
import os
import json
import threading
from pathlib import Path

from llm_provider  import build_provider, LLMError, LLMRateLimitError
from agent_loop    import AgentLoop
from context_manager import (
    needs_compact, llm_compact, simple_compact, token_report,
)
from model_router  import route as model_route
from rag           import get_rag_context
from memory        import (
    load_memory, save_memory, clear_memory as clear_mem,
    memory_to_prompt, update_memory_async,
)

# ── Output (thread-safe) ──────────────────────────────────────────────────────

_emit_lock = threading.Lock()

# Module-level memory cache (loaded once at startup, mutated as facts arrive)
_MEMORY: dict = {}


def emit(obj: dict) -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


# ── Config / paths ────────────────────────────────────────────────────────────

def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", ".")) / "VAgent"
    return Path(os.environ.get("HOME", ".")) / ".config" / "VAgent"


def _sessions_dir() -> Path:
    d = config_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id)
    return _sessions_dir() / f"{safe}.json"


# ── Session persistence ───────────────────────────────────────────────────────

def load_session(session_id: str = "default") -> list:
    try:
        return json.loads(_session_path(session_id).read_text(encoding="utf-8"))
    except Exception:
        return []


def save_session(messages: list, session_id: str = "default") -> None:
    try:
        _session_path(session_id).write_text(
            json.dumps(messages[-60:], ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def clear_session(session_id: str = "default") -> None:
    save_session([], session_id)


# ── Persisted config (API keys live in config.json / .env) ───────────────────

def _persisted_config() -> dict:
    data: dict = {}
    try:
        raw = (config_dir() / "config.json").read_text(encoding="utf-8")
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            data.update(loaded)
    except Exception:
        pass
    try:
        env_text = (config_dir() / ".env").read_text(encoding="utf-8")
        for line in env_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_key = k.strip()
            env_val = v.strip()
            mapping = {
                "GROQ_API_KEY":        "groq_api_key",
                "OPENROUTER_API_KEY":  "openrouter_api_key",
                "ANTHROPIC_API_KEY":   "anthropic_api_key",
                "OLLAMA_MODEL":        "model",
            }
            if env_key in mapping:
                data.setdefault(mapping[env_key], env_val)
    except Exception:
        pass
    return data


def merged_config(req_cfg: dict) -> dict:
    merged = _persisted_config()
    merged.update(req_cfg or {})
    return merged


# ── MCP integration ───────────────────────────────────────────────────────────
# Loaded once at startup from config.json mcp_servers field.

MCP_SERVERS:   dict = {}    # {"servername": {"url": str, "tools": list, "enabled": bool}}
MCP_TOOLS_DOC: str  = ""    # extra lines appended to TOOLS_DOC for MCP tools


def _load_mcp_servers() -> None:
    global MCP_SERVERS, MCP_TOOLS_DOC
    try:
        cfg = _persisted_config()
        servers = cfg.get("mcp_servers", [])
        if not isinstance(servers, list):
            return
        import requests
        doc_lines: list[str] = []
        for srv in servers:
            name    = srv.get("name", "").strip()
            url     = srv.get("url", "").strip().rstrip("/")
            enabled = srv.get("enabled", True)
            if not name or not url or not enabled:
                continue
            try:
                resp  = requests.get(f"{url}/tools", timeout=5)
                tools = resp.json() if resp.status_code == 200 else []
            except Exception:
                tools = []
            MCP_SERVERS[name] = {"url": url, "tools": tools, "enabled": True}
            for t in tools:
                tname = t.get("name", "")
                tdesc = t.get("description", "")
                if tname:
                    qname = f"mcp__{name}__{tname}"
                    doc_lines.append(
                        f'<tool_call>{{"tool": "{qname}", "args": {{}}}}</tool_call>'
                        f"\n{tdesc or f'MCP tool from server {name}'}"
                    )
        MCP_TOOLS_DOC = "\n".join(doc_lines)
    except Exception:
        pass


# ── Extension system ──────────────────────────────────────────────────────────

EXTENSION_TOOLS: dict = {}
EXTENSION_DOCS:  list = []


class VagentContext:
    def add_tool(self, name: str, fn, description: str = "") -> None:
        EXTENSION_TOOLS[name] = fn
        if description:
            EXTENSION_DOCS.append(
                f'<tool_call>{{"tool": "{name}", "args": {{}}}}</tool_call>\n{description}'
            )


def load_extensions() -> None:
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
        try:
            spec = importlib.util.spec_from_file_location(
                f"vagent_ext_{path.name}", main_py
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)   # type: ignore[union-attr]
            if hasattr(module, "register") and callable(module.register):
                module.register(ctx)
        except Exception as exc:
            print(f"[sidecar] extension '{path.name}' error: {exc}", file=sys.stderr)


# ── Built-in read-only tools ──────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "target",
    "dist", "build", ".venv", "venv",
}


def _resolve(cwd: str, rel: str) -> Path:
    return (Path(cwd) / rel).resolve()


def tool_read_file(cwd: str, args: dict) -> str:
    try:
        return _resolve(cwd, args.get("path", "")).read_text(
            encoding="utf-8", errors="replace"
        )[:12_000]
    except Exception as e:
        return f"ERROR: {e}"


def tool_list_dir(cwd: str, args: dict) -> str:
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


def tool_search(cwd: str, args: dict) -> str:
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


LOCAL_TOOLS = {
    "read_file":        tool_read_file,
    "list_dir":         tool_list_dir,
    "search_in_files":  tool_search,
}

# ── System prompt / tools doc ─────────────────────────────────────────────────

IDENTITY = """You are V-Agent, an AI coding assistant embedded in a local code editor. You remember the user across sessions and build on past context.

STYLE — these rules are strict:
- Answer first. Lead with the fix or the answer, never with background.
- Match length to the question: a simple question gets 1-3 sentences. Never pad.
- Plain short prose by default. No headers, tables, bullet lists, or emoji unless the user asks or the content genuinely needs them.
- No filler ("Sure!", "Great question", "Bottom line", "In summary"), no recap of what you just did, no "what's missing" / "common pitfalls" sections nobody asked for, no cheat-sheets.
- When showing code in chat, show only the relevant lines with one short sentence of explanation. Save full files for write_file.
- Act instead of asking. Only ask a clarifying question when you are truly blocked.
- If something fails, say what failed in one line and fix it."""

TOOLS_DOC = """You have tools. Use them proactively.

CRITICAL RULE: When the user asks to create, write, edit, or modify a file — always use write_file immediately. Never just show code in a code block without also proposing write_file. If the user wants a file created, create it.

CRITICAL RULE: Tool calls only work when the <tool_call> tag appears VERBATIM in your final visible reply — never inside private reasoning or analysis. If you decide to use a tool, your reply must contain the tag itself.

CRITICAL RULE: Never claim a tool is unavailable, and never state that a file exists or is missing, without calling the tool first. Project context included in this prompt may be partial or stale — verify with list_dir / read_file before asserting anything about the project.

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
- Only skip write_file if the user explicitly says 'just show me the code' or 'don't create a file'.

TOOL DISCIPLINE:
- Tools before talk: when the answer depends on project code, read_file / list_dir / search_in_files FIRST — never guess what a file contains.
- When editing an existing file: read_file it first, then write_file the FULL updated content. Do not also paste the code in chat — write_file plus a one-line summary is the whole answer.
- Between tool calls, output nothing or one short line. After the final tool, conclude in 1-3 sentences: what changed and where.
- Batch your reads: if you need three files, request them together, not one per turn."""


def _build_system(base: str, use_tools: bool, plan: bool, rag_ctx: str, mem_ctx: str = "") -> str:
    # Rules FIRST, volatile context LAST: providers (notably the shared
    # backend) may truncate long system prompts from the end — losing file
    # context degrades an answer, but losing TOOLS_DOC silently disables
    # tool use entirely.
    parts = [IDENTITY]
    if plan:
        parts.append("PLAN MODE: Provide a concise step-by-step plan only. Do NOT use tools or write code.")
    elif use_tools:
        parts.append(TOOLS_DOC)
        if EXTENSION_DOCS:
            parts.append("Extension tools:\n" + "\n".join(EXTENSION_DOCS))
        if MCP_TOOLS_DOC:
            parts.append("MCP tools:\n" + MCP_TOOLS_DOC)
    if mem_ctx:
        parts.append(mem_ctx)
    if base:
        parts.append(base)
    if rag_ctx:
        parts.append(rag_ctx)
    return "\n\n".join(p for p in parts if p)


# ── Cancel table ──────────────────────────────────────────────────────────────

_cancel: dict[str, bool] = {}


# ── Main agent handler ────────────────────────────────────────────────────────

def run_agent(req: dict) -> None:
    rid        = req.get("id")
    session_id = req.get("session_id", "default") or "default"
    messages   = req.get("messages", [])
    config     = merged_config(req.get("config", {}))
    cwd        = req.get("cwd") or os.getcwd()
    base_sys   = req.get("system_prompt", "") or ""
    agent      = bool(req.get("agent", True))
    plan       = bool(req.get("plan", False))
    autonomous = bool(req.get("autonomous", False))

    _cancel[rid] = False

    def cancelled() -> bool:
        return bool(_cancel.get(rid, False))

    # ── Model routing ─────────────────────────────────────────────────────────
    last_msg = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    config, task_type = model_route(last_msg, messages, config)
    model = config.get("model", "")

    # ── RAG context ───────────────────────────────────────────────────────────
    rag_ctx = ""
    if cwd and agent and not plan and last_msg:
        try:
            rag_ctx = get_rag_context(last_msg, cwd, config_dir())
        except Exception:
            pass

    # ── Memory context ────────────────────────────────────────────────────────
    mem_ctx = memory_to_prompt(_MEMORY) if _MEMORY else ""

    use_tools = agent and not plan
    system    = _build_system(base_sys, use_tools, plan, rag_ctx, mem_ctx)

    # ── Provider ──────────────────────────────────────────────────────────────
    try:
        provider = build_provider(config, system, agent=use_tools)
    except Exception as e:
        emit({"type": "error", "id": rid, "error": f"provider: {e}"})
        emit({"type": "done",  "id": rid})
        _cancel.pop(rid, None)
        return

    # Build fallback provider (OpenRouter) for rate-limit recovery
    fallback = None
    or_key   = config.get("openrouter_api_key", "").strip()
    if or_key and config.get("ai_provider") == "groq":
        try:
            fallback = build_provider(
                {**config, "ai_provider": "openrouter"}, system
            )
        except Exception:
            pass

    # ── History trim / auto-compact ───────────────────────────────────────────
    convo = list(messages)
    if needs_compact(convo, model):
        try:
            convo = llm_compact(convo, provider)
            emit({"type": "info", "id": rid,
                  "text": "Context compacted automatically to stay within token limit."})
        except Exception:
            compacted, n = simple_compact(convo)
            convo = compacted
            if n:
                emit({"type": "info", "id": rid,
                      "text": f"{n} earlier messages compacted to manage context length."})
    elif len(convo) > 20:
        kept     = convo[-5:]
        dropped  = len(convo) - 5
        convo    = [{"role": "user",
                     "content": f"[{dropped} earlier messages trimmed to manage context]"}] + kept

    # ── Agent loop ────────────────────────────────────────────────────────────
    loop  = AgentLoop(
        session_id      = session_id,
        provider        = provider,
        emit_fn         = lambda ev: emit({**ev}),
        local_tools     = LOCAL_TOOLS,
        extension_tools = EXTENSION_TOOLS,
        mcp_servers     = MCP_SERVERS,
    )
    convo = loop.run(rid, convo, cwd, use_tools, cancelled, fallback,
                     autonomous=autonomous)

    save_session(convo, session_id)
    _cancel.pop(rid, None)
    emit({"type": "done", "id": rid})

    # Update memory asynchronously after the session completes
    if _MEMORY and _MEMORY.get("remember_me", True):
        update_memory_async(_MEMORY, convo, provider, config_dir(), cwd)


# ── Legacy single-shot ────────────────────────────────────────────────────────

def handle_legacy(req: dict) -> None:
    messages      = req.get("messages", [])
    config        = merged_config(req.get("config", {}))
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
    except Exception as e:
        emit({"error": f"sidecar error: {e}"})
        emit({"done": True})


# ── Dispatch ──────────────────────────────────────────────────────────────────

def dispatch(req: dict) -> None:
    t          = req.get("type")
    session_id = req.get("session_id", "default") or "default"

    if t is None:
        handle_legacy(req)

    elif t == "chat":
        threading.Thread(target=run_agent, args=(req,), daemon=True).start()

    elif t == "cancel":
        _cancel[req.get("id")] = True

    elif t == "load_session":
        msgs = load_session(session_id)
        emit({"type": "session", "session_id": session_id, "messages": msgs})

    elif t == "clear_session":
        clear_session(session_id)
        emit({"type": "session", "session_id": session_id, "messages": []})

    elif t == "compact_session":
        msgs = load_session(session_id)
        compacted, n = simple_compact(msgs)
        save_session(compacted, session_id)
        emit({
            "type":       "session",
            "session_id": session_id,
            "messages":   compacted,
            "compacted":  n,
        })

    elif t == "get_context":
        model = req.get("model", "")
        msgs  = load_session(session_id)
        report = token_report(msgs, model)
        emit({
            "type":       "context",
            "session_id": session_id,
            "messages":   msgs,
            **report,
        })

    elif t == "get_memory":
        emit({"type": "memory_data", "data": dict(_MEMORY)})

    elif t == "clear_memory":
        _MEMORY.clear()
        _MEMORY.update(load_memory(config_dir()))
        clear_mem(config_dir())
        emit({"type": "memory_data", "data": dict(_MEMORY)})

    elif t == "update_memory_prefs":
        prefs = req.get("preferences", {})
        remember = req.get("remember_me")
        if isinstance(prefs, dict):
            _MEMORY.setdefault("user_preferences", {}).update(prefs)
        if remember is not None:
            _MEMORY["remember_me"] = bool(remember)
        save_memory(_MEMORY, config_dir())
        emit({"type": "memory_data", "data": dict(_MEMORY)})

    else:
        emit({"type": "error", "error": f"unknown request type '{t}'"})


def main() -> None:
    global _MEMORY
    _MEMORY = load_memory(config_dir())
    load_extensions()
    _load_mcp_servers()
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
        except Exception as e:
            emit({"type": "error", "error": f"dispatch: {e}"})


if __name__ == "__main__":
    main()
