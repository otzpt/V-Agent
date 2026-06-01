<div align="center">

# V-Agent 0.7.1

**Professional Agentic IDE · Voidtune Ecosystem**

[![Release](https://img.shields.io/github/v/release/otzpt/V-Agent?style=flat-square)](https://github.com/otzpt/V-Agent/releases)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green?style=flat-square)](https://doc.qt.io/qtforpython)

</div>

---

## ✨ Features

- 🤖 **AI-powered coding** — Groq cloud backend, no API key required
- 🖥️ **Cross-platform** — Windows & Linux (PySide6)
- 🔒 **Secure** — Keys never visible to users, stored only on server
- ⚡ **Fast** — llama-3.3-70b-versatile via Groq (~200 tokens/sec)
- 📁 **Full IDE** — File explorer, syntax highlighting, tabs
- 🔧 **Automator** — Watches Input/ and AI-fixes scripts to Output/
- 🌙 **Dark/Light themes** — GitHub-inspired design

## 🚀 Quick Start

### Windows
```bash
# 1. Download V-Agent-0.7.1.zip from Releases and extract
# 2. Run:
pip install -r requirements.txt
python vagent.py
```

### Linux
```bash
# Ubuntu/Debian
sudo apt install python3-pip python3-venv libxcb-cursor0 -y
pip install -r requirements.txt
python3 vagent.py

# Arch
sudo pacman -S python-pip
pip install -r requirements.txt
python3 vagent.py
```

> **No API key needed!** The backend handles everything securely.

## 🏗️ Architecture

```
V-Agent Desktop  (no keys ever)
       │
       │  POST /chat
       ▼
Backend (Vercel)  ◄── GROQ_API_KEY (env var, server-side only)
       │
       ▼
  Groq API  (llama-3.3-70b-versatile, free)
```

## 🔒 Security

- API keys stored **only** in Vercel environment variables
- Rate limiting: 30 req/min per IP
- Model whitelist (free Groq models only)
- Input sanitization (max 8000 chars)
- Keys written to `.env` locally only — never to `config.json` or GitHub

See [SECURITY.md](SECURITY.md) for full details.

## 📦 Folder Structure

```
V-Agent/
├── vagent.py          # Main app (PySide6)
├── automator.py       # File watcher
├── api/
│   ├── chat.py        # Backend (Vercel serverless)
│   └── requirements.txt
├── vercel.json        # Vercel config
├── requirements.txt   # Client dependencies
├── .env.example       # Template (no real keys)
├── .gitignore         # Protects .env + config.json
├── SECURITY.md
└── README.md
```

## 🛠️ Optional: Self-hosting

If you want to run your own backend:

```bash
# Clone
git clone https://github.com/otzpt/V-Agent.git
cd V-Agent/api

# Install backend deps
pip install -r requirements.txt

# Set your key
export GROQ_API_KEY=gsk_...

# Run locally
uvicorn chat:app --reload --port 8000
```

Then in V-Agent Settings → Backend URL → `http://localhost:8000`

## 📝 License

MIT — See [LICENSE](LICENSE)
