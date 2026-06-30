# Changelog

## v0.9.0 — First Release

### Fix (0.9.0 maintenance update)
- **Backend model switched to Groq Compound (`groq/compound`)** — an agentic system
  with built-in web search and code execution, far better suited to coding tasks than
  the previous Llama models. Groq decommissioned the Llama 3.x models, so the backend
  now serves every request with Compound and transparently upgrades any legacy
  `llama-…` request from already-installed apps. No reinstall needed: the fix is
  server-side, so existing 0.9.0 installs pick it up automatically.
- Updated client defaults, `.env.example` and `config.example.json` to `groq/compound`.

### Core editor
- Monaco editor (VS Code engine) with multi-tab support and per-tab save state
- Syntax highlighting for 30+ languages with automatic language detection
- LSP diagnostics with 500ms debounce and 50-marker cap to reduce false positives
- JetBrains Mono default font, configurable size

### Terminal
- Real PTY terminal via `portable-pty` (multi-tab, full shell)
- Windows: `cmd.exe` default; Linux/macOS: bash/sh
- `CREATE_NO_WINDOW` flag on Windows to suppress console flicker

### AI agent
- Streaming token output with markdown rendering
- Tool-calling loop: `read_file`, `write_file`, `list_dir`, `search_files`, `run_command`
- Diff preview for `write_file` tool with Accept / Reject buttons
- Auto-summary when conversation history exceeds 20 messages
- Smart file context: sends open file on first message and on file change only
- `/clear` command resets session
- Strip excessive bold markdown in AI responses

### AI providers
- **V-Agent Cloud** (default, no setup required)
- **Groq** — free API key, streaming SSE
- **OpenRouter** — free and paid models, default `anthropic/claude-haiku-4-5`
- **Ollama** — local, fully offline; raises error if not running (no silent fallback)
- Auto-retry: Groq 429 → switches to OpenRouter automatically if key is set

### Git panel
- Status with XY porcelain codes
- Stage / unstage individual files
- Commit with message
- Push / pull
- Inline unified diff viewer

### File system
- File tree with expand/collapse, refresh button on load failure
- Create, delete, rename files and folders
- Search in files with plain text and regex, up to 2000 hits

### Live HTML preview
- Real-time render of open HTML files
- Visual Inspector (click element → highlight in editor)

### Settings & configuration
- Provider selector with API key fields
- OpenRouter model input with suggestions datalist
- Hackatime API key and URL fields with Test button
- Config stored in `%APPDATA%\VAgent\config.json` (Windows) / `~/.config/VAgent/config.json`
- API keys in `%APPDATA%\VAgent\.env`, never in `config.json`

### Onboarding wizard
- 6-screen first-run wizard: Welcome → System info → AI provider → Hackatime → Theme → Done
- System RAM and VRAM detection for Ollama recommendations

### Hackatime / WakaTime integration
- Heartbeats on file open, save, and content change
- wakatime-cli auto-downloaded from GitHub releases on first use
- API key and URL passed explicitly to wakatime-cli (not dependent on `~/.wakatime.cfg`)
- Line number and cursor position tracking

### Themes
- 8 built-in themes: GitHub Dark (default), GitHub Light, Monokai, Dracula, Nord, Solarized Dark, One Dark, Ayu Dark

### Extensions
- Extension store with install / uninstall
- Python-based extensions stored in `%APPDATA%\VAgent\extensions\`

### Arduino
- `arduino-cli` integration: list ports, compile sketch, upload to board

### Windows installer
- MSI installer via WiX 3 (Tauri default template)
- Desktop and Start Menu shortcuts
- Uninstall shortcut in Start Menu
- "Launch V-Agent" checkbox on finish screen
- Installs to `%PROGRAMFILES%\V-Agent`

### Build & release
- GitHub Actions: 3 parallel platform builds (Windows, Linux, macOS)
- Artifacts: `.msi` + NSIS `.exe` (Windows), `.deb` + `.AppImage` (Linux), `.dmg` (macOS)
- Auto GitHub Release on `v*` tag push
