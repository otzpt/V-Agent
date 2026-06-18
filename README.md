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
```

---

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
