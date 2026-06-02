#!/usr/bin/env python3
"""
V-Agent Automator 0.8.0
Watches Input/ and auto-corrects scripts using AI backend or local Ollama.
watchdog is optional — falls back to polling if not installed.
"""

import os, sys, time, json, re, datetime, requests, subprocess
from pathlib import Path

# ── Setup path so platform_utils is importable ────────────────────────────────
BASE_DIR  = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from platform_utils import load_env_file, get_base_dir, ensure_dir, safe_open, atomic_write

load_env_file()

INPUT_DIR  = BASE_DIR / "Input"
OUTPUT_DIR = BASE_DIR / "Output"
CFG_PATH   = BASE_DIR / "config.json"
SUPPORTED  = {".bat",".cmd",".ps1",".py",".js",".ts",".sh"}

# ── Config ─────────────────────────────────────────────────────────────────────
def load_cfg() -> dict:
    try:
        with safe_open(CFG_PATH,"r") as f:
            return json.load(f)
    except Exception:
        return {}

def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}]  {msg}", flush=True)

def strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?","",text.strip())
    text = re.sub(r"\n?```$","",text.strip())
    return text.strip()

# ── Backend provider (Vercel — preferred, no key needed) ──────────────────────
def fix_via_backend(content: str, cfg: dict):
    server = cfg.get("vagent_server_url","https://vt-inference-relay.vercel.app").rstrip("/")
    model  = cfg.get("groq_model","llama-3.3-70b-versatile")
    prompt = (
        "You are an expert developer. Fix ALL bugs, syntax errors, and bad practices "
        "in the script below. Keep the original functionality intact. "
        "Add basic error handling where missing. "
        "Respond ONLY with the complete corrected script — no explanation, no markdown.\n\n"
        f"<script>\n{content}\n</script>"
    )
    try:
        log("  → Backend (Vercel)…")
        r = requests.post(f"{server}/chat",
            json={"message":prompt,"model":model,"history":[]}, timeout=60)
        if r.status_code == 429:
            return None, "Rate limit (30/min). Wait a minute."
        if r.status_code != 200:
            return None, f"Backend error ({r.status_code})"
        return strip_fences(r.json().get("content","")), None
    except requests.exceptions.ConnectionError:
        return None, "Backend unreachable"
    except requests.exceptions.Timeout:
        return None, "Backend timeout"

# ── Local Ollama ───────────────────────────────────────────────────────────────
def fix_via_local(content: str, cfg: dict):
    base  = cfg.get("ollama_base_url","http://localhost:11434")
    model = cfg.get("model","qwen2.5-coder:14b")
    prompt = (
        "Fix ALL bugs, syntax errors, and bad practices in the script below. "
        "Keep original functionality. Add basic error handling. "
        "Respond ONLY with the complete corrected script.\n\n"
        f"<script>\n{content}\n</script>"
    )
    for attempt in range(1,4):
        try:
            log(f"  → Local Ollama attempt {attempt}/3…")
            r = requests.post(f"{base}/api/generate",
                json={"model":model,"prompt":prompt,"stream":False,
                      "options":{"temperature":0.1,"num_ctx":32768}}, timeout=120)
            r.raise_for_status()
            return strip_fences(r.json().get("response","")), None
        except Exception as e:
            if attempt < 3:
                log(f"  ⚠  {e} — retrying…"); time.sleep(3)
            else:
                return None, f"Ollama failed: {e}"

# ── Process a file ─────────────────────────────────────────────────────────────
def process_file(path: Path, cfg: dict):
    if path.suffix.lower() not in SUPPORTED:
        return

    log(f"📄 Processing: {path.name}")
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log(f"  ❌ Could not read: {e}"); return

    if not content.strip():
        log("  ⚠  File empty — skipping"); return

    provider = cfg.get("ai_provider","backend")

    if provider == "local":
        result, err = fix_via_local(content, cfg)
        if err:
            log(f"  ⚠  Ollama failed: {err}. Trying backend…")
            result, err = fix_via_backend(content, cfg)
    else:
        result, err = fix_via_backend(content, cfg)
        if err:
            log(f"  ⚠  Backend failed: {err}. Trying Ollama…")
            result, err = fix_via_local(content, cfg)

    if err or not result:
        log(f"  ❌ All providers failed: {err}"); return

    out_path = OUTPUT_DIR / path.name
    try:
        atomic_write(out_path, result)
        log(f"  ✅ Saved → Output/{path.name}")
    except Exception as e:
        log(f"  ❌ Write failed: {e}")

# ── Watcher ────────────────────────────────────────────────────────────────────
def watch_polling(cfg: dict):
    """Fallback watcher using polling (no watchdog needed)."""
    log("Watching Input/ (polling mode — install watchdog for instant detection)")
    seen = {}
    while True:
        try:
            for f in INPUT_DIR.iterdir():
                if f.suffix.lower() not in SUPPORTED: continue
                mtime = f.stat().st_mtime
                if seen.get(str(f)) != mtime:
                    seen[str(f)] = mtime
                    time.sleep(0.5)  # debounce
                    process_file(f, cfg)
        except Exception as e:
            log(f"Watch error: {e}")
        time.sleep(2)

def watch_watchdog(cfg: dict):
    """Instant watcher using watchdog."""
    from watchdog.observers import Observer
    from watchdog.events    import FileSystemEventHandler

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory: process_file(Path(event.src_path), cfg)
        def on_modified(self, event):
            if not event.is_directory: process_file(Path(event.src_path), cfg)

    obs = Observer(); obs.schedule(Handler(), str(INPUT_DIR), recursive=False)
    obs.start()
    log("Watching Input/ (watchdog mode — instant detection)")
    try:
        while obs.is_alive(): time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ensure_dir(INPUT_DIR); ensure_dir(OUTPUT_DIR)
    cfg = load_cfg()

    log(f"V-Agent Automator 0.8.0")
    log(f"Input:    {INPUT_DIR}")
    log(f"Output:   {OUTPUT_DIR}")
    log(f"Provider: {cfg.get('ai_provider','backend')}")
    log("")

    try:
        import watchdog
        watch_watchdog(cfg)
    except ImportError:
        log("Note: 'pip install watchdog' for instant file detection")
        watch_polling(cfg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
