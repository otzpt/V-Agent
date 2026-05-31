#!/usr/bin/env python3
"""
V-Agent Automator v1.0
Watches Input/ and auto-corrects scripts using local Ollama or cloud AI.
Requires: pip install watchdog requests
"""

import os, sys, time, json, re, datetime, argparse, requests, shlex, subprocess
from watchdog.observers import Observer
from watchdog.events    import FileSystemEventHandler

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CFG_PATH    = os.path.join(BASE_DIR, "config.json")
INPUT_DIR   = os.path.join(BASE_DIR, "Input")
OUTPUT_DIR  = os.path.join(BASE_DIR, "Output")
SUPPORTED   = {".bat", ".cmd", ".ps1", ".py", ".js", ".ts", ".sh"}


# ── Config ─────────────────────────────────────────────────────────────────────
def load_cfg() -> dict:
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}]  {msg}", flush=True)


def strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$",          "", text.strip())
    return text.strip()


# ── Local Ollama ────────────────────────────────────────────────────────────────
def _fix_local(content: str, model: str, api_url: str, retries: int = 3):
    ext  = ""   # caller sets via prompt
    lang = "Python" if not content.lstrip().startswith(
        ("@echo", "param(", "Param(", "#!", "::")
    ) else "Windows batch/PowerShell"

    prompt = (
        f"You are an expert {lang} developer.\n"
        "Fix ALL bugs, syntax errors, and bad practices in the script below.\n"
        "Keep the original functionality intact. Add basic error handling where missing.\n"
        "Respond ONLY with the complete corrected script — no explanation, no markdown.\n\n"
        f"<script>\n{content}\n</script>"
    )
    payload = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.1, "num_ctx": 32768},
    }
    for attempt in range(1, retries + 1):
        try:
            log(f"  → Local Ollama (attempt {attempt}/{retries})…")
            r = requests.post(api_url, json=payload, timeout=120)
            r.raise_for_status()
            return strip_fences(r.json().get("response", "")), None
        except requests.RequestException as e:
            if attempt < retries:
                log(f"  ⚠  {e} — retrying in 3s…")
                time.sleep(3)
            else:
                return None, f"Local AI failed after {retries} attempts: {e}"


# ── Cloud AI ────────────────────────────────────────────────────────────────────
_CLOUD_URLS = {
    "groq":        "https://api.groq.com/openai/v1/chat/completions",
    "openrouter":  "https://openrouter.ai/api/v1/chat/completions",
}

def _fix_cloud(content: str, provider: str, model: str,
               api_key: str, retries: int = 3):
    if not api_key:
        return None, f"{provider} API key not set in config.json"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    if provider == "openrouter":
        headers.update({
            "HTTP-Referer": "https://github.com/vagent",
            "X-Title":      "V-Agent Automator",
        })

    messages = [{
        "role":    "user",
        "content": (
            "You are an expert developer. Fix all bugs, syntax errors, and issues "
            "in the script below. Keep functionality intact. Add error handling. "
            "Respond ONLY with the corrected script — no explanation.\n\n"
            f"<script>\n{content}\n</script>"
        ),
    }]
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": 0.1,
        "max_tokens":  4096,
    }
    url = _CLOUD_URLS.get(provider, "")
    for attempt in range(1, retries + 1):
        try:
            log(f"  → Cloud AI ({provider} · {model}) attempt {attempt}/{retries}…")
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return strip_fences(text), None
        except Exception as e:
            if attempt < retries:
                log(f"  ⚠  {e} — retrying in 3s…")
                time.sleep(3)
            else:
                return None, f"Cloud AI ({provider}) failed: {e}"


# ── Main fix dispatcher ─────────────────────────────────────────────────────────
def fix_with_ai(content: str, cfg: dict, retries: int = 3):
    provider = cfg.get("ai_provider", "local")

    if provider == "local":
        base    = cfg.get("ollama_base_url", "http://localhost:11434")
        model   = cfg.get("model", "qwen2.5-coder:14b")
        api_url = f"{base}/api/generate"
        return _fix_local(content, model, api_url, retries)

    elif provider == "groq":
        return _fix_cloud(
            content,
            "groq",
            cfg.get("groq_model", "llama-3.3-70b-versatile"),
            cfg.get("groq_api_key", ""),
            retries,
        )

    elif provider == "openrouter":
        return _fix_cloud(
            content,
            "openrouter",
            cfg.get("openrouter_model", "meta-llama/llama-3.2-3b-instruct:free"),
            cfg.get("openrouter_api_key", ""),
            retries,
        )

    else:
        return None, f"Unknown provider: {provider}"


# ── File processor ──────────────────────────────────────────────────────────────
def process(path: str, output_dir: str, cfg: dict):
    name = os.path.basename(path)
    log(f"\n{'─' * 56}")
    log(f"Processing: {name}")

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        log(f"  ✗ Read error: {e}"); return

    if not content.strip():
        log("  ✗ Empty file — skipped."); return

    fixed, err = fix_with_ai(content, cfg)
    if err:   log(f"  ✗ {err}"); return
    if not fixed: log("  ✗ Empty response."); return

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem, ext = os.path.splitext(name)
    out_path  = os.path.join(output_dir, f"fixed_{stem}_{ts}{ext}")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fixed)
        log(f"  ✓ Saved → {out_path}")
    except Exception as e:
        log(f"  ✗ Save error: {e}")


# ── Watchdog ────────────────────────────────────────────────────────────────────
class Handler(FileSystemEventHandler):
    def __init__(self, output_dir, cfg):
        self.output_dir = output_dir
        self.cfg        = cfg

    def on_created(self, event):
        if event.is_directory: return
        if os.path.splitext(event.src_path)[1].lower() not in SUPPORTED: return
        time.sleep(1.5)
        process(event.src_path, self.output_dir, self.cfg)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="V-Agent Automator")
    parser.add_argument("--input",  default=INPUT_DIR)
    parser.add_argument("--output", default=OUTPUT_DIR)
    args = parser.parse_args()

    cfg = load_cfg()
    os.makedirs(args.input,  exist_ok=True)
    os.makedirs(args.output, exist_ok=True)

    provider = cfg.get("ai_provider", "local")
    if provider == "local":
        model = cfg.get("model", "qwen2.5-coder:14b")
    elif provider == "groq":
        model = cfg.get("groq_model", "llama-3.3-70b-versatile")
    else:
        model = cfg.get("openrouter_model", "meta-llama/llama-3.2-3b-instruct:free")

    log("V-Agent Automator v1.0")
    log(f"  Provider : {provider}")
    log(f"  Model    : {model}")
    log(f"  Watch    : {args.input}")
    log(f"  Output   : {args.output}")
    log(f"  Types    : {', '.join(sorted(SUPPORTED))}")
    log("Waiting for files… (Ctrl+C to stop)\n")

    observer = Observer()
    observer.schedule(Handler(args.output, cfg), args.input, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        log("\nStopping…")
        observer.stop()
    observer.join()
    log("Done.")


if __name__ == "__main__":
    main()
