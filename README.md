<<<<<<< HEAD
# V-Agent v0.9

Local-first AI coding agent. Tauri (Rust) shell + React UI + Monaco editor + xterm.js, with the existing Python LLM backend running as a sidecar.

> **This is a scaffold / starting point.** It has not been run end-to-end. Expect to debug the first launch — that's normal for a Tauri + sidecar project. See "Known first-run issues" below.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Tauri window (native webview)               │
│  ┌────────────────────────────────────────┐  │
│  │  React UI                               │  │
│  │  • Monaco editor  • xterm terminal      │  │
│  │  • file tree      • AI chat panel       │  │
│  └────────────────────────────────────────┘  │
│                  │ invoke()                    │
│                  ▼                             │
│  Rust commands (src-tauri/src/lib.rs)         │
│  • read_file / write_file / list_dir          │
│  • ai_chat → spawns Python sidecar             │
└──────────────────┬──────────────────────────┘
                   │ stdin/stdout JSON
                   ▼
   Python sidecar (sidecar/vagent_sidecar.py)
   wraps llm_provider.py  →  backend/Ollama/Groq/OpenRouter
```

The UI never talks to the LLM directly. It calls the Rust `ai_chat` command, which spawns the Python sidecar, writes a JSON request to its stdin, and streams JSON token lines back as `ai-token` events.

---

## Prerequisites (Linux)

```bash
# 1. Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# 2. Tauri system deps (Debian/Ubuntu/Mint)
sudo apt update
sudo apt install -y libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

# 3. Node deps
npm install
=======
# V-Agent v0.8.0

> The zero-bloat alternative to cloud-based AI agents. Cross-platform, secure, Ollama optional.

🔗 **Repo:** [github.com/otzpt/V-Agent](https://github.com/otzpt/V-Agent)

---

## What is V-Agent?

V-Agent is a local-first AI coding assistant with a modern Qt6 GUI (PySide6). It supports multiple LLM providers — a self-hosted backend, Ollama (local), Groq, and OpenRouter — with graceful fallback between them. Your API keys never leave your machine.

---

## Features

- **Cross-platform** — Windows and Linux (pathlib everywhere, no hardcoded paths)
- **PySide6 Qt6 GUI** — Dark/light themes with CSS-variable design tokens, HiDPI support
- **Multi-provider LLM** — Backend → Ollama → OpenRouter (free tier enforced), with automatic fallback
- **Tabbed IDE** — Syntax highlighting for 15+ languages, file tree, tabbed editor
- **Agentic AI** — read/write/edit/ls/run/search tools built in
- **Terminal panel** — Safe command execution with allowlist
- **Secure key storage** — API keys written only to `.env` via `write_env_key`, never to `config.json`
- **Config in AppData** — Not stored next to the script
- **Automator** — File watcher (watchdog optional, falls back to polling)
- **Installers** — `install.sh` (Linux, with distro detection + desktop entry) and `install.ps1` (Windows, with PATH + shortcut)
- **GitHub Actions** — Lint, syntax check, and auto ZIP on tag push

---

## LLM Providers

| Provider | Requires | Notes |
|---|---|---|
| Backend | Vercel deployment | Default, rate-limited, keys server-side |
| Ollama | Local install | Optional, auto-detected |
| OpenRouter | API key in `.env` | Free tier models only |
| Groq | API key in `.env` | Free tier models |

---

## Quick Start

### Windows
```powershell
.\installer\install.ps1
```

### Linux
```bash
chmod +x installer/install.sh && ./installer/install.sh
>>>>>>> 2d0b6d95de4e0d14f1d4316753b832ac983366e1
```

---

<<<<<<< HEAD
## Build the Python sidecar (required before `tauri dev`)

The app spawns a compiled sidecar binary, so you must build it first:

```bash
bash sidecar/build.sh
```

This uses PyInstaller to produce `src-tauri/binaries/vagent-sidecar-<target-triple>`.

---

## Run

```bash
npm run tauri dev
```

First compile of the Rust side takes a few minutes. Subsequent runs are fast.

---

## Build installers

```bash
npm run tauri build
```

Produces a `.deb` / `.AppImage` on Linux, `.msi` / `.exe` on Windows (when built on Windows).

---

## Known first-run issues (debug these together)

1. **Sidecar not found** — `ai_chat` fails if `src-tauri/binaries/vagent-sidecar-<triple>` doesn't exist or the triple is wrong. Check `rustc -Vv | grep host` matches the filename suffix.
2. **Capability/permission errors** — if the console says a command is not allowed, the permission is missing in `src-tauri/capabilities/default.json`.
3. **Plugin version mismatch** — the `@tauri-apps/plugin-*` npm versions must match the Rust crate versions in `Cargo.toml`.
4. **WebKit blank window on Linux** — usually a missing `libwebkit2gtk` dependency (see prerequisites).
5. **Monaco not loading** — `@monaco-editor/react` loads Monaco from a CDN by default; offline use needs the `loader` configured to a local copy (a later task).

---

## What's stubbed / TODO

- **Terminal** is echo-mode only. Real shell needs a Rust PTY command (next part).
- **Provider switching / settings UI** not built yet — defaults to the backend provider.
- **Agentic file tools** (the AI reading/writing files itself) not wired yet.
- **Monaco offline loader**, theme persistence, tab management — future parts.

---

## Project layout

```
package.json            → npm scripts + deps
vite.config.js          → Vite dev server (port 1420)
index.html              → React entry
src/
  main.jsx
  App.jsx               → grid layout, theme state
  styles.css            → void/nebula theme tokens (dark + light)
  lib/tauri.js          → invoke() wrappers
  components/
    ActivityBar.jsx
    FileTree.jsx
    EditorPane.jsx      → Monaco
    Terminal.jsx        → xterm (echo stub)
    AIPanel.jsx         → streaming chat + markdown rendering
src-tauri/
  Cargo.toml
  tauri.conf.json
  build.rs
  capabilities/default.json
  src/
    main.rs
    lib.rs             → commands + sidecar bridge
sidecar/
  vagent_sidecar.py    → stdin/stdout JSON loop
  llm_provider.py      → (your v0.8 provider, unchanged)
  requirements.txt
  build.sh             → PyInstaller → binaries/
```
=======
## Security

API keys are stored exclusively in `.env` (never `config.json`). The `.env` file is git-ignored. The backend runs on Vercel with rate limiting (30 req/min per IP) and a model whitelist. See `SECURITY.md` for full policy.

---

## Requirements

| Component | Minimum |
|---|---|
| Python | 3.8+ |
| OS | Windows 10/11 or Linux |
| RAM | 8 GB |
| VRAM | 4 GB (Ollama only) |

---

## About

Built as a personal project to learn Python, PySide6, and AI integration — without cloud lock-in.
>>>>>>> 2d0b6d95de4e0d14f1d4316753b832ac983366e1
