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
```

---

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
