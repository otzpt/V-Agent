"""
llm_provider.py — V-Agent LLM backend abstraction
Supports: Backend (Vercel), Local (Ollama), Groq, OpenRouter
No API keys ever stored in this file.
"""

import os
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Generator, Optional

import requests

logger = logging.getLogger("vagent.llm")

# ── Allowed models whitelist (free only) ──────────────────────────────────────

ALLOWED_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemma-7b-it",
]

ALLOWED_OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-7b-instruct:free",
]

# ── Base interface ─────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Quick check — should not raise."""
        ...

    @abstractmethod
    def stream(
        self,
        messages: list,
        cancel_flag=None,
        temperature: float = 0.15,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """Yield tokens. Raises LLMError on fatal failure."""
        ...

class LLMError(Exception):
    """Raised by providers on non-recoverable errors."""

# ── Backend provider (Vercel — keys server-side, zero exposure) ───────────────

class BackendProvider(LLMProvider):
    name = "backend"

    def __init__(self, server_url: str, model: str):
        self.server_url = server_url.rstrip("/")
        self.model      = model

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.server_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def stream(self, messages, cancel_flag=None, temperature=0.15, max_tokens=4096):
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        history = [
            m for m in messages
            if m["role"] in ("user", "assistant") and m["content"] != last_user
        ][-10:]

        try:
            resp = requests.post(
                f"{self.server_url}/chat",
                json={"message": last_user, "model": self.model, "history": history},
                timeout=60,
            )
        except requests.exceptions.ConnectionError:
            raise LLMError("Cannot reach backend. Check internet connection.")
        except requests.exceptions.Timeout:
            raise LLMError("Backend request timed out (60s).")

        if resp.status_code == 429:
            raise LLMError("Rate limit reached (30/min). Try again shortly.")
        if resp.status_code == 503:
            raise LLMError("Backend temporarily unavailable.")
        if resp.status_code != 200:
            raise LLMError(f"Backend error ({resp.status_code}).")

        content = resp.json().get("content", "")
        for char in content:
            if cancel_flag and cancel_flag():
                return
            yield char

# ── Local Ollama provider ──────────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    name = "local"

    def __init__(self, base_url: str, model: str, system_prompt: str = ""):
        self.base_url      = base_url.rstrip("/")
        self.model         = model
        self.system_prompt = system_prompt

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def stream(self, messages, cancel_flag=None, temperature=0.15, max_tokens=4096):
        if self.system_prompt:
            msgs = [{"role": "system", "content": self.system_prompt}] + messages[-20:]
        else:
            msgs = messages[-20:]

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model":   self.model,
                    "messages": msgs,
                    "stream":  True,
                    "options": {"temperature": temperature, "num_ctx": 32768},
                },
                stream=True,
                timeout=180,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise LLMError(
                "Ollama not running. Start it with: ollama serve\n"
                "Or switch to Backend provider in Settings.")
        except requests.exceptions.Timeout:
            raise LLMError("Ollama timed out.")
        except requests.HTTPError as e:
            raise LLMError(f"Ollama HTTP error: {e}")

        for line in resp.iter_lines():
            if cancel_flag and cancel_flag():
                return
            if not line:
                continue
            try:
                data = json.loads(line)
                tok  = data.get("message", {}).get("content", "")
                if tok:
                    yield tok
                if data.get("done"):
                    break
            except json.JSONDecodeError:
                continue

# ── Groq direct provider ───────────────────────────────────────────────────────

class GroqProvider(LLMProvider):
    name = "groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, system_prompt: str = ""):
        self._key          = api_key
        self.model         = model if model in ALLOWED_GROQ_MODELS else ALLOWED_GROQ_MODELS[0]
        self.system_prompt = system_prompt

    def is_available(self) -> bool:
        return bool(self._key and self._key.startswith("gsk_"))

    def stream(self, messages, cancel_flag=None, temperature=0.15, max_tokens=4096):
        if not self.is_available():
            raise LLMError("No Groq API key. Add it in Settings.")

        msgs = ([{"role": "system", "content": self.system_prompt}]
                if self.system_prompt else []) + messages[-20:]

        try:
            resp = requests.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self._key}",
                         "Content-Type": "application/json"},
                json={"model": self.model, "messages": msgs,
                      "stream": True, "temperature": temperature,
                      "max_tokens": max_tokens},
                stream=True,
                timeout=180,
            )
        except requests.exceptions.ConnectionError:
            raise LLMError("Cannot reach Groq API. Check internet.")
        except requests.exceptions.Timeout:
            raise LLMError("Groq request timed out.")

        if resp.status_code == 401:
            raise LLMError("Invalid Groq API key.")
        if resp.status_code == 429:
            raise LLMError("Groq rate limit reached. Try again later.")
        if resp.status_code != 200:
            raise LLMError(f"Groq API error ({resp.status_code}).")

        for raw in resp.iter_lines():
            if cancel_flag and cancel_flag():
                return
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0].get("delta", {})
                tok   = delta.get("content", "")
                if tok:
                    yield tok
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

# ── OpenRouter provider ────────────────────────────────────────────────────────

class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str, system_prompt: str = ""):
        self._key          = api_key
        self.system_prompt = system_prompt
        # Force :free suffix to avoid accidental charges
        if model and not model.endswith(":free"):
            logger.warning("OpenRouter model '%s' is not free. Falling back.", model)
            model = ALLOWED_OPENROUTER_FREE_MODELS[0]
        self.model = model or ALLOWED_OPENROUTER_FREE_MODELS[0]

    def is_available(self) -> bool:
        return bool(self._key and self._key.startswith("sk-or-"))

    def stream(self, messages, cancel_flag=None, temperature=0.15, max_tokens=4096):
        if not self.is_available():
            raise LLMError("No OpenRouter API key. Add it in Settings.")

        msgs = ([{"role": "system", "content": self.system_prompt}]
                if self.system_prompt else []) + messages[-20:]

        try:
            resp = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization":  f"Bearer {self._key}",
                    "Content-Type":   "application/json",
                    "HTTP-Referer":   "https://github.com/otzpt/V-Agent",
                    "X-Title":        "V-Agent",
                },
                json={"model": self.model, "messages": msgs,
                      "stream": True, "temperature": temperature,
                      "max_tokens": max_tokens},
                stream=True,
                timeout=180,
            )
        except requests.exceptions.ConnectionError:
            raise LLMError("Cannot reach OpenRouter. Check internet.")
        except requests.exceptions.Timeout:
            raise LLMError("OpenRouter request timed out.")

        if resp.status_code == 401:
            raise LLMError("Invalid OpenRouter API key.")
        if resp.status_code == 402:
            raise LLMError("OpenRouter: insufficient credits (only :free models allowed).")
        if resp.status_code == 429:
            raise LLMError("OpenRouter rate limit reached.")
        if resp.status_code != 200:
            raise LLMError(f"OpenRouter error ({resp.status_code}).")

        for raw in resp.iter_lines():
            if cancel_flag and cancel_flag():
                return
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0].get("delta", {})
                tok   = delta.get("content", "")
                if tok:
                    yield tok
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

# ── Provider factory ───────────────────────────────────────────────────────────

def build_provider(cfg: dict, system_prompt: str = "") -> LLMProvider:
    """
    Build the correct provider from config.
    Priority:
      1. Explicit ai_provider setting
      2. If backend → BackendProvider
      3. If local → OllamaProvider
      4. If groq/openrouter → cloud provider
    Falls back gracefully: if chosen provider unavailable, try backend.
    """
    provider_name = cfg.get("ai_provider", "backend")

    if provider_name == "backend":
        return BackendProvider(
            server_url=cfg.get("vagent_server_url", "https://vt-inference-relay.vercel.app"),
            model=cfg.get("groq_model", "llama-3.3-70b-versatile"),
        )

    # The frontend labels this provider "ollama"; "local" kept for back-compat.
    if provider_name in ("local", "ollama"):
        p = OllamaProvider(
            base_url=cfg.get("ollama_base_url", "http://localhost:11434"),
            model=cfg.get("model") or cfg.get("ollama_model") or "llama3.2",
            system_prompt=system_prompt,
        )
        if not p.is_available():
            logger.warning("Ollama not available — falling back to backend.")
            return BackendProvider(
                server_url=cfg.get("vagent_server_url", "https://vt-inference-relay.vercel.app"),
                model=cfg.get("groq_model", "llama-3.3-70b-versatile"),
            )
        return p

    if provider_name == "groq":
        key = cfg.get("groq_api_key", "").strip()
        if not key:
            logger.warning("No Groq key — falling back to backend.")
            return BackendProvider(
                server_url=cfg.get("vagent_server_url", "https://vt-inference-relay.vercel.app"),
                model=cfg.get("groq_model", "llama-3.3-70b-versatile"),
            )
        model = cfg.get("model") or cfg.get("groq_model") or ALLOWED_GROQ_MODELS[0]
        return GroqProvider(key, model, system_prompt)

    if provider_name == "openrouter":
        key = cfg.get("openrouter_api_key", "").strip()
        if not key:
            logger.warning("No OpenRouter key — falling back to backend.")
            return BackendProvider(
                server_url=cfg.get("vagent_server_url", "https://vt-inference-relay.vercel.app"),
                model=cfg.get("groq_model", "llama-3.3-70b-versatile"),
            )
        model = cfg.get("model") or cfg.get("openrouter_model") or ALLOWED_OPENROUTER_FREE_MODELS[0]
        return OpenRouterProvider(key, model, system_prompt)

    # Unknown provider — safe fallback
    logger.error("Unknown provider '%s' — using backend.", provider_name)
    return BackendProvider(
        server_url=cfg.get("vagent_server_url", "https://vt-inference-relay.vercel.app"),
        model=cfg.get("groq_model", "llama-3.3-70b-versatile"),
    )
