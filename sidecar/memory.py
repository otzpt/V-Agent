"""
memory.py — Persistent cross-session memory for V-Agent (Jarvis mode)

Stored at ~/.config/VAgent/memory.json (Windows: %APPDATA%/VAgent/memory.json)
"""

import json
import threading
import time
from pathlib import Path


_EMPTY: dict = {
    "user_preferences": {
        "language":      "pt-PT",
        "code_style":    "",
        "explain_level": "",
    },
    "known_projects": [],   # [{path, name, last_worked, summary}]
    "learned_facts":  [],   # [str]
    "remember_me":    True,
}


def _memory_path(config_dir: Path) -> Path:
    return config_dir / "memory.json"


def load_memory(config_dir: Path) -> dict:
    try:
        raw  = _memory_path(config_dir).read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            merged = dict(_EMPTY)
            merged["user_preferences"] = {**_EMPTY["user_preferences"],
                                           **data.get("user_preferences", {})}
            merged["known_projects"] = data.get("known_projects", [])
            merged["learned_facts"]  = data.get("learned_facts",  [])
            merged["remember_me"]    = data.get("remember_me",    True)
            return merged
    except Exception:
        pass
    return dict(_EMPTY)


def save_memory(mem: dict, config_dir: Path) -> None:
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        _memory_path(config_dir).write_text(
            json.dumps(mem, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def clear_memory(config_dir: Path) -> None:
    save_memory(dict(_EMPTY), config_dir)


def memory_to_prompt(mem: dict) -> str:
    """Format memory as a short block for the system prompt."""
    if not mem.get("remember_me", True):
        return ""

    parts: list[str] = []

    prefs = mem.get("user_preferences", {})
    lang  = prefs.get("language",      "")
    style = prefs.get("code_style",    "")
    level = prefs.get("explain_level", "")
    if lang or style or level:
        bits = []
        if lang:  bits.append(f"language={lang}")
        if style: bits.append(f"code_style={style}")
        if level: bits.append(f"explain_level={level}")
        parts.append("User preferences: " + ", ".join(bits))

    facts = mem.get("learned_facts", [])
    if facts:
        lines = "\n".join(f"- {f}" for f in facts[-10:])
        parts.append(f"Known facts about this user:\n{lines}")

    projs = mem.get("known_projects", [])
    if projs:
        recent = sorted(projs, key=lambda p: p.get("last_worked", 0), reverse=True)[:3]
        lines  = "\n".join(
            f"  - {p['name']} ({p['path']})" +
            (f": {p['summary']}" if p.get("summary") else "")
            for p in recent
        )
        parts.append(f"Recent projects:\n{lines}")

    if not parts:
        return ""
    return "[V-Agent Memory]\n" + "\n\n".join(parts)


def update_memory_async(
    mem: dict,
    conversation: list,
    provider,
    config_dir: Path,
    project_path: str = "",
) -> None:
    """
    Fire-and-forget: ask the LLM to extract up to 2 new facts from the
    conversation and persist them. Updates the known_projects list too.
    """
    if not mem.get("remember_me", True):
        return

    def _run() -> None:
        try:
            turns = []
            for m in conversation[-10:]:
                role    = m.get("role", "")
                content = str(m.get("content", ""))[:400]
                if role in ("user", "assistant"):
                    turns.append(f"{role.upper()}: {content}")
            if not turns:
                return

            existing_facts = json.dumps(mem.get("learned_facts", []))
            prompt = (
                "You are a memory assistant. Based on the conversation excerpt below, "
                "identify at most 2 NEW facts about the user (preferences, skills, goals, "
                "working context). Reply with ONLY a JSON list of short strings, e.g. "
                '[\"fact 1\", \"fact 2\"] or []. '
                "Do NOT repeat facts already listed.\n\n"
                f"Existing facts: {existing_facts}\n\n"
                "Conversation:\n" + "\n".join(turns)
            )

            acc = ""
            for tok in provider.stream([{"role": "user", "content": prompt}]):
                acc += tok

            acc   = acc.strip()
            start = acc.find("[")
            end   = acc.rfind("]") + 1
            if 0 <= start < end:
                new_facts = json.loads(acc[start:end])
                if isinstance(new_facts, list):
                    current = mem.get("learned_facts", [])
                    for f in new_facts:
                        if isinstance(f, str) and f.strip() and f not in current:
                            current.append(f.strip())
                    mem["learned_facts"] = current[-30:]

            # Update known_projects
            if project_path:
                projs    = mem.get("known_projects", [])
                existing = next((p for p in projs if p.get("path") == project_path), None)
                now_ms   = int(time.time() * 1000)
                if existing:
                    existing["last_worked"] = now_ms
                else:
                    name = Path(project_path).name
                    projs.append({
                        "path":         project_path,
                        "name":         name,
                        "last_worked":  now_ms,
                        "summary":      "",
                    })
                mem["known_projects"] = projs[-20:]

            save_memory(mem, config_dir)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
