# V-Agent Installer

Quick installers for all platforms. No Python knowledge required.

## Linux

```bash
bash installer/install.sh
```

Options:
- `--venv` — install into a virtual environment (recommended)
- `--system` — install system-wide (requires sudo)

After install: run `vagent` from any terminal.

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File installer\install.ps1
```

Options:
- `-Venv` — install into a virtual environment
- `-NoShortcut` — skip desktop shortcut

After install: run `vagent` from any terminal, or use the desktop shortcut.

## Manual (any platform)

```bash
pip install -r requirements.txt
python vagent.py        # Windows
python3 vagent.py       # Linux / Mac
```

## Requirements

- Python 3.10+
- Internet connection (for Groq backend)
- Linux: `libxcb-cursor0` (Ubuntu/Debian) — installed automatically

## No Python?

Download the pre-compiled `.exe` from the [Releases page](https://github.com/otzpt/V-Agent/releases).
Windows users can run it directly — no Python needed.
