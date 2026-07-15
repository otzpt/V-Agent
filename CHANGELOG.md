# Changelog

## v0.9.4

### AI agent — tools actually work now
Six stacked bugs kept the agent from ever using its tools on the backend
provider; all fixed and verified end-to-end (real `list_dir`/`read_file`
executions with grounded answers):
- Server system-prompt cap truncated the tool instructions away; prompt now
  orders rules first and the cap fits the whole protocol.
- Oversized tool results were rejected mid-loop; now truncated safely.
- Agent requests route to instruction-faithful models (`gpt-oss-120b` →
  `llama-4-scout` → `compound-mini`); chat keeps Compound and its web search.
- Tool calls hidden in the models' reasoning channel or native `tool_calls`
  field are now harvested into the tool protocol (server + streaming client).
- Lenient tool-tag parser (accepts the `<tool_calls>` plural variant).
- A stale `OLLAMA_MODEL` from `.env` no longer leaks into other providers'
  model choice (this silently forced agent runs onto Compound).

### Explorer — VS Code-grade file handling
- New File/Folder create in the **selected** folder (folder → inside it,
  file → its parent, none → root), with row selection + highlight.
- Inline rename (F2 or context menu) with the name stem preselected.
- Delete goes to the **Recycle Bin** and handles non-empty folders; Delete key
  works on the selection; workspace roots protected.
- Drag & drop to move files/folders (guarded against invalid moves).
- Context menu: Copy Path, Copy Relative Path, Reveal in File Explorer,
  Duplicate.

### Editor
- Default tab size is now **4** (+ a 2/4/8 control in Settings).
- VS Code-style token colors for C/C++/Python: function calls, constants and
  class names get distinct colors (vendored + enhanced Monarch grammars).

### Arduino / Raspberry Pi Pico
- Port listing fixed for arduino-cli ≥ 1.0 (`--json`).
- Upload now compiles first (Arduino IDE parity) and supports **portless
  BOOTSEL flashing** for RP2040 boards, with a hint in the panel.
- Boards added: Pico W, Pico 2, Pico 2 W; one-click **Install core** per board
  family (runs in the terminal).
- **MicroPython mode** for .py files: Run on board, Deploy as main.py, REPL
  via mpremote.

### Extension store
- The registry is live at [vagent-extensions](https://github.com/otzpt/vagent-extensions)
  with three starters: HTTP Fetch, TODO Scanner, Serial Tools.

## v0.9.3

### Fix
- **White editor on app start** — the custom Monaco themes introduced in 0.9.2
  were registered after the editor first applied them, and Monaco falls back to
  the white `vs` theme for unknown names. Themes are now registered synchronously
  in `beforeMount`, so the editor is correctly dark from the first paint.

## v0.9.2

### Backend — rate limit fixes
- **Per-user rate limiting actually works now**: behind Vercel's proxy every user
  was sharing one 30/min bucket (`request.client.host` is the proxy, not the user);
  the real IP is now read from `x-forwarded-for`.
- Rate-limit rejections return a clean **429** (previously surfaced as a 500 from
  inside the middleware), and `/health` pings no longer consume the limit.
- **Automatic fallback to `groq/compound-mini`** when `groq/compound` hits the
  shared key's Groq limit — a separate quota bucket, doubling free capacity.
- Clearer client message when the shared backend is busy, suggesting a personal
  free Groq key.

### In-app auto-updater
- The update banner now has **Install & restart**: downloads the right asset for
  your install (MSI installer or portable ZIP), waits for the app to close,
  installs silently (one UAC prompt for MSI), and relaunches — same system as
  VOIDTUNE. Non-Windows platforms keep the release-page link.

### AI panel
- **Much less talkative**: new system prompt enforces answer-first responses sized
  to the question — no more giant tables, cheat-sheets, and "common pitfalls"
  essays for one-line questions.
- Stronger tool discipline: reads files before editing, batches reads, replies in
  1-3 sentences after tool use instead of narrating.

### Editor
- **New syntax colors** (One-Dark-style: blue keywords, pink operators, gold types,
  green strings) applied across all app themes, with the editor background matched
  to each theme. **Rainbow bracket-pair colorization** + active-pair guides.
- **Structural error detection for C, C++, C#, Java, Kotlin, Swift, Dart and Go**
  (previously no diagnostics at all): unmatched `( [ {`, unclosed strings/char
  literals, unclosed block comments — shown as squiggles + in the Problems panel.

## v0.9.1

### AI backend — Groq Compound
- **All Groq inference now runs on Groq Compound (`groq/compound`)** — an agentic
  system with built-in web search and code execution, far better suited to coding
  tasks. Groq decommissioned the Llama 3.x models; the hosted backend transparently
  upgrades legacy `llama-…` requests from older installs, so 0.9.0 apps keep working.
- Model router, context manager, client defaults and config templates all updated
  to Compound.

### Explorer (file tree)
- **Live refresh** — open folders now detect files created outside the app
  (in-app terminal, git, other programs) within ~1.5s and on window focus.
  Previously the tree only updated on manual actions or AI writes.
- **Create in any folder** — every folder row shows hover New File / New Folder
  buttons that create inside *that* folder. Previously the header buttons only
  created in the first workspace root.
- **Create with no folder open** — VS Code-style empty state: New File… (Save
  dialog), New Folder… (pick location, then opens as workspace), Open Folder….

### Jarvis mode (experimental)
- Sidecar rearchitecture: persistent cross-session memory, autonomous agent loop,
  MCP tool support, RAG file context, heuristic model routing, token-budget
  context compaction. A testing ground for [ECHOVOID](https://github.com/otzpt/ECHOVOID) —
  not production-ready.

### Misc
- Release workflow is idempotent (re-tagging refreshes an existing release).
- Update-check banner: 0.9.0 users will now see the v0.9.1 update notification.

## v0.9.0 — First Release

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
