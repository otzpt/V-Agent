<p align="center">
  <img src="src-tauri/icons/icon.svg" width="120" alt="V-Agent logo"/>
</p>

<h1 align="center">V-Agent</h1>
<p align="center"><em>Local-first AI coding agent. No cloud lock-in, no bloat.</em></p>

<p align="center">
  <a href="https://github.com/otzpt/V-Agent/releases"><img src="https://img.shields.io/badge/version-0.9.3-7c6ef8?style=flat-square" alt="Version"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-7cf26e?style=flat-square" alt="License"/></a>
  <a href="https://github.com/otzpt/V-Agent/releases"><img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-555?style=flat-square" alt="Platform"/></a>
</p>

---

## Features

- **Monaco editor** — the same engine powering VS Code, with syntax highlighting for 30+ languages, tabs, and save
- **Real PTY terminal** — multi-tab, full shell, not an echo stub
- **AI agent** — tool-calling loop with `read_file`, `write_file` (diff preview with Accept/Reject), `search`, `run`
- **Git panel** — status, stage, commit, push/pull, inline diff viewer
- **Live HTML preview** — real-time render with Visual Inspector
- **Extension store** — installable Python-based extensions
- **Hackatime integration** — automatic coding time tracking
- **8 themes** — GitHub Dark (default), GitHub Light, Monokai, Dracula, Nord, Solarized, One Dark, Ayu
- **Onboarding wizard** — guided first-run setup
- **Command palette** — `Ctrl+Shift+P`
- **Search in files** — `Ctrl+Shift+F` with regex support
- **Arduino support** — compile and upload from the editor
- **Offline capable** — Ollama provider works with no internet

---

## Note on "Jarvis mode" (experimental)

V-Agent v0.9.1 includes an experimental **Jarvis mode** — persistent cross-session memory, autonomous agent loop, MCP tool support, and RAG context. This is a **testing ground**, not the main feature of V-Agent.

The real, standalone Jarvis/AI assistant project is **[ECHOVOID](https://github.com/otzpt/ECHOVOID)** — a separate voice + text AI assistant (Siri/Jarvis-style). The features prototyped here will migrate there. Don't treat the Jarvis code in V-Agent as production-ready; it exists to validate the sidecar architecture before it lands in ECHOVOID.

---

## Download

Get the latest installer from [GitHub Releases](https://github.com/otzpt/V-Agent/releases).

| Platform | File |
|----------|------|
| Windows  | `V-Agent_x.x.x_x64_en-US.msi` |
| Linux    | `v-agent_x.x.x_amd64.deb` · `v-agent_x.x.x_amd64.AppImage` |
| macOS    | `V-Agent_x.x.x_x64.dmg` |

---

## Quick Start

1. Download the installer for your platform
2. Run V-Agent
3. Complete the onboarding wizard (choose AI provider, optionally set up Hackatime)
4. Open a folder with **File → Open Folder**
5. Ask the AI to help with your code

---

## AI Providers

| Provider | Setup | Notes |
|----------|-------|-------|
| V-Agent Cloud | None (default) | Rate-limited shared backend — runs **Groq Compound** (built-in web search + code execution) |
| Groq | Free API key at [console.groq.com](https://console.groq.com) | Groq Compound, fast free tier |
| OpenRouter | API key at [openrouter.ai](https://openrouter.ai) | Many models including free tier |
| Anthropic | API key at [console.anthropic.com](https://console.anthropic.com) | Claude Haiku / Sonnet / Opus |
| Ollama | [Install Ollama](https://ollama.ai) locally | Fully offline, no API key |

Configure in **Settings** (`Ctrl+,`) → AI Provider.

Auto-fallback: if Groq hits rate limits, V-Agent switches to OpenRouter automatically (if key is set).

---

## Build from Source

### Prerequisites

- [Rust](https://rustup.rs) (stable)
- [Node.js](https://nodejs.org) 20+
- [Python](https://python.org) 3.11+
- Linux only: `libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev`

### Steps

```bash
# 1. Clone
git clone https://github.com/otzpt/V-Agent
cd V-Agent

# 2. Install Python deps
pip install pyinstaller requests python-dotenv

# 3. Build the Python sidecar
cd sidecar
pyinstaller --onefile vagent_sidecar.py --name vagent_sidecar
cd ..

# 4. Copy sidecar to binaries/ (adjust triple for your platform)
# Linux x86_64:
mkdir -p src-tauri/binaries
cp sidecar/dist/vagent_sidecar src-tauri/binaries/vagent-sidecar-x86_64-unknown-linux-gnu
chmod +x src-tauri/binaries/vagent-sidecar-x86_64-unknown-linux-gnu

# Windows x86_64 (in PowerShell):
# copy sidecar\dist\vagent_sidecar.exe src-tauri\binaries\vagent-sidecar-x86_64-pc-windows-msvc.exe

# 5. Install npm deps
npm install

# 6. Dev mode
npm run tauri dev

# 7. Production build (creates installer in src-tauri/target/release/bundle/)
npm run tauri build
```

---

## Project Structure

```
src/
  App.jsx                   main layout, theme, Hackatime loader
  components/
    AIPanel.jsx             AI chat with streaming + tool diffs
    EditorPane.jsx          Monaco editor, tabs, LSP markers, heartbeats
    FileTree.jsx            file system tree with refresh
    Terminal.jsx            xterm.js PTY terminal
    Settings.jsx            provider + key configuration overlay
    Onboarding.jsx          first-run wizard
    GitPanel.jsx            git status, stage, commit, diff
    HtmlPreview.jsx         live HTML preview + inspector
    ExtensionStore.jsx      extension marketplace
src-tauri/
  src/lib.rs                Rust commands (FS, git, PTY, heartbeat, search)
  tauri.conf.json           app + bundle config
  wix/main.wxs              Windows MSI installer template
sidecar/
  vagent_sidecar.py         JSON stdio agent loop (multi-session, MCP, RAG)
  llm_provider.py           Groq / OpenRouter / Ollama / Anthropic abstraction
  agent_loop.py             tool-calling loop (normal + autonomous mode)
  context_manager.py        token estimation + auto-compact
  rag.py                    keyword-based file index + retrieval
  model_router.py           heuristic model selection
  memory.py                 cross-session memory (Jarvis — see note above)
```

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
