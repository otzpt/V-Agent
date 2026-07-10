"""
model_router.py — Heuristic model selection for V-Agent
Picks the best available model based on message complexity and token budget.
Only activates when the user hasn't explicitly chosen a specific provider;
explicit provider choices are always respected.
"""

from context_manager import history_tokens, estimate_tokens

# ── Thresholds ────────────────────────────────────────────────────────────────

SHORT_MSG_CHARS   = 200     # under this → simple task
LARGE_CTX_TOKENS  = 4_000   # history over this → large-context model needed

COMPLEX_KEYWORDS = {
    "refactor", "rewrite", "redesign", "architect", "migrate",
    "implement", "build", "create", "complete", "review", "audit",
    "debug", "optimize", "analyse", "analyze",
}

# ── Task classification ───────────────────────────────────────────────────────

def _classify(message: str, history: list) -> str:
    """Returns 'simple' | 'complex' | 'large_context'."""
    if history_tokens(history) > LARGE_CTX_TOKENS:
        return "large_context"
    msg_lo = message.lower()
    for kw in COMPLEX_KEYWORDS:
        if kw in msg_lo:
            return "complex"
    if len(message) < SHORT_MSG_CHARS:
        return "simple"
    return "complex"


# ── Router ────────────────────────────────────────────────────────────────────

def route(message: str, history: list, config: dict) -> tuple[dict, str]:
    """
    Return (effective_config, task_type).

    Only overrides provider when the user has 'backend' or 'groq' selected —
    explicit choices (openrouter, ollama, anthropic) are passed through unchanged.
    """
    explicit = config.get("ai_provider", "backend")
    if explicit not in ("backend", "groq"):
        return config, _classify(message, history)

    task   = _classify(message, history)
    routed = dict(config)

    has_groq      = bool(config.get("groq_api_key", "").strip())
    has_or        = bool(config.get("openrouter_api_key", "").strip())
    has_anthropic = bool(config.get("anthropic_api_key", "").strip())

    if task == "large_context":
        if has_anthropic:
            routed["ai_provider"] = "anthropic"
            routed.setdefault("model", "claude-haiku-4-5")
        elif has_or:
            routed["ai_provider"] = "openrouter"
            routed.setdefault("model", "anthropic/claude-haiku-4-5")
        elif has_groq:
            routed["ai_provider"] = "groq"
            routed["model"]       = "groq/compound"

    elif task == "complex":
        if has_groq:
            routed["ai_provider"] = "groq"
            routed["model"]       = "groq/compound"
        elif has_or:
            routed["ai_provider"] = "openrouter"

    elif task == "simple":
        if has_groq:
            routed["ai_provider"] = "groq"
            routed["model"]       = "groq/compound"

    return routed, task
