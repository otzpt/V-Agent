# V-Agent v0.7 — Local AI Coding Agent

```
   ______     __  __     __     __   __     __  __
  /\  ___\   /\ \/\ \   /\ \   /\ "-.\ \  /\ \/\ \
  \ \ \____  \ \ \_\ \  \ \ \  \ \ \-. \ \ \ \_\ \
   \ \_____\  \ \_____\  \ \_\  \ \_\\"\_\ \ \_____\
    \/_____/   \/_____/   \/_/   \/_/ \/_/  \/_____/
```

**100% local. Zero telemetry. Your code never leaves your machine.**

Powered by [Ollama](https://ollama.com) — no API keys, no internet after model download.

---

## What's New in v0.7

- **Unified IDE** — launcher, terminal, settings, and automator merged into a single `vagent.py`
- **Sidebar navigation** — switch between Terminal / Settings / Automator with one click or `/settings` `/automator` commands
- **Simplified file structure** — from 9 directories and 4 bat scripts down to a flat layout
- **Single config file** — `config.json` at the root, no duplicates
- **Live theme recolor** — theme changes apply instantly without restart
- **Automator integrated** — start/stop the file watcher from inside the app

---

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10 / 11 (64-bit) | Required |
| [Ollama](https://ollama.com/download/windows) | Must be running (`ollama serve`) |
| Python 3.9+ | From [python.org](https://www.python.org/downloads/) — **not** Microsoft Store |
| `requests` | Auto-installed by `start.bat` |
| `watchdog` | Required only for the Automator — `pip install watchdog` |

---

## Quick Start

### 1. Install Ollama and pull a model
```
ollama serve
ollama pull qwen2.5-coder:14b
```

### 2. Launch V-Agent
```
start.bat          ← double-click on Windows
```
or directly:
```
python vagent.py
```

---

## File Structure

```
V-Agent/
├── vagent.py        ← Unified app (terminal + settings + automator)
├── automator.py     ← Script auto-corrector (watchdog)
├── config.json      ← Settings (auto-created on first save)
├── start.bat        ← Windows launcher
├── README.md
├── LICENSE
├── Input/           ← Drop scripts here for auto-fix
├── Output/          ← Fixed scripts appear here
└── bin/             ← Pre-compiled C++ IDE (optional)
    ├── V-Agent.exe
    └── WebView2Loader.dll
```

---

## Terminal Commands

```
AI
  /ask <text>          Ask the AI a question
  /model <name>        Switch model
  /streaming           Toggle streaming on/off
  /context             Show context token usage
  /clear-history       Erase conversation history
  /copy                Copy last AI response to clipboard

Files & Shell
  /files [path]        List files
  /cd <path>           Change directory
  /run <cmd>           Run a shell command
  /edit <file>         Open file in default editor

Navigation
  /settings            Open Settings panel
  /automator           Open Automator panel

Display
  /clear               Clear screen  (Ctrl+L)
  /theme               Toggle theme
  /neofetch            System info
  /matrix              Matrix rain effect
  /cowsay [msg]        Cow says something
  /fortune             Random fortune cookie

Utility
  /date                Date and time
  /whoami              User + cwd
  /echo <text>         Echo text
  /about               About V-Agent
  /exit                Exit
```

---

## Automator

Drop `.bat`, `.ps1`, `.cmd`, or `.py` files into `Input/`. The AI fixes bugs and
saves corrected versions to `Output/` with a timestamp.

From inside V-Agent, click 🤖 in the sidebar or type `/automator`.

From the command line:
```
python automator.py
python automator.py --input C:\MyScripts --output C:\Fixed
```

---

## Configuration (`config.json`)

```json
{
  "model":           "qwen2.5-coder:14b",
  "theme":           "voidtune_purple",
  "ollama_base_url": "http://localhost:11434",
  "streaming":       true,
  "font_size":       12
}
```

---

## Supported Models

| Model | VRAM | Notes |
|---|---|---|
| `qwen2.5-coder:14b` | 8 GB | Best balance (default) |
| `qwen2.5-coder:7b`  | 4 GB | Lighter |
| `deepseek-coder-v2:16b` | 9 GB | Smarter |
| `codellama:13b`     | 8 GB | Meta |
| `granite-code:8b`   | 5 GB | IBM, fast |

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
