"""
context_manager.py — Context window management for V-Agent
Estimates token usage and compacts history when approaching provider limits.
"""

from typing import Optional

# Approximate context limits per model (conservative)
MODEL_TOKEN_LIMITS: dict[str, int] = {
    # Groq
    "llama-3.1-8b-instant":     8_000,
    "llama-3.3-70b-versatile": 32_000,
    "mixtral-8x7b-32768":      32_000,
    "gemma2-9b-it":             8_000,
    "gemma-7b-it":              8_000,
    # Anthropic
    "claude-haiku-4-5":       200_000,
    "claude-sonnet-4-5":      200_000,
    "claude-opus-4-8":        200_000,
    # OpenRouter (use model suffix after /)
    "claude-haiku-4-5:beta":  200_000,
    # Ollama
    "llama3.2":                 4_000,
    "llama3":                   4_000,
    "mistral":                  8_000,
    # default
    "_default":                 8_000,
}

COMPACT_THRESHOLD = 0.80   # auto-compact when > 80 % of limit
KEEP_RECENT       = 5      # always keep last N messages intact after compact


def estimate_tokens(text: str) -> int:
    """~1 token per 4 chars — fast, good enough for budget decisions."""
    return max(1, len(text) // 4)


def history_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):          # multi-part content blocks
            for block in content:
                if isinstance(block, dict):
                    total += estimate_tokens(block.get("text", ""))
    return total


def _limit_for(model: str) -> int:
    if not model:
        return MODEL_TOKEN_LIMITS["_default"]
    # exact match first
    if model in MODEL_TOKEN_LIMITS:
        return MODEL_TOKEN_LIMITS[model]
    # strip org prefix (e.g. "anthropic/claude-haiku-4-5" → "claude-haiku-4-5")
    short = model.split("/")[-1]
    if short in MODEL_TOKEN_LIMITS:
        return MODEL_TOKEN_LIMITS[short]
    return MODEL_TOKEN_LIMITS["_default"]


def needs_compact(messages: list, model: str) -> bool:
    return history_tokens(messages) > _limit_for(model) * COMPACT_THRESHOLD


def simple_compact(messages: list, keep: int = KEEP_RECENT) -> tuple[list, int]:
    """
    Drop older messages and prepend a summary note.
    Returns (new_messages, n_dropped).
    """
    if len(messages) <= keep:
        return messages, 0
    older  = messages[:-keep]
    recent = messages[-keep:]
    n      = len(older)
    note   = {"role": "user",
              "content": f"[{n} earlier messages were compacted to manage context length.]"}
    return [note] + recent, n


def llm_compact(messages: list, provider, keep: int = KEEP_RECENT) -> list:
    """
    Summarize older messages via the LLM, keep the summary + recent messages.
    Falls back to simple_compact if the LLM call fails.
    """
    if len(messages) <= keep:
        return messages

    older  = messages[:-keep]
    recent = messages[-keep:]

    summary_req = [{
        "role": "user",
        "content": (
            "Summarize the following conversation in 4-6 concise sentences, "
            "preserving key facts, file paths, decisions, and code snippets that may be referenced later:\n\n"
            + "\n".join(
                f"[{m['role']}]: {str(m.get('content', ''))[:600]}"
                for m in older
            )
        ),
    }]

    try:
        summary = ""
        for tok in provider.stream(summary_req, temperature=0.1, max_tokens=512):
            summary += tok
        note = {"role": "user", "content": f"[Conversation summary: {summary.strip()}]"}
        return [note] + recent
    except Exception:
        compacted, _ = simple_compact(messages, keep)
        return compacted


def token_report(messages: list, model: str) -> dict:
    used  = history_tokens(messages)
    limit = _limit_for(model)
    return {
        "tokens_used":   used,
        "token_limit":   limit,
        "pct":           round(used / limit * 100, 1) if limit else 0,
        "needs_compact": used > limit * COMPACT_THRESHOLD,
    }
