<div align="center">

# V-Agent 0.8.0

**Professional Agentic IDE · Voidtune Ecosystem**

[![Release](https://img.shields.io/github/v/release/otzpt/V-Agent?style=flat-square)](https://github.com/otzpt/V-Agent/releases)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?style=flat-square)]()

</div>

---

## ✨ Features

- 🤖 **AI-powered coding** — Groq cloud, no API key needed
- 🖥️ **Cross-platform** — Windows & Linux (PySide6/Qt6)
- 🔒 **Secure** — Keys never visible to users
- ⚡ **Fast** — llama-3.3-70b via Groq (~200 tok/s)
- 📁 **Full IDE** — File explorer, syntax highlighting, tabs
- 🔧 **Automator** — AI auto-fixes scripts in Input/ → Output/
- 🌙 **Dark/Light themes** — GitHub-inspired

## 🚀 Quick Start

### Windows
```bash
pip install -r requirements.txt
python vagent.py
```

### Linux
```bash
# Ubuntu/Debian
sudo apt install libxcb-cursor0 -y
pip install -r requirements.txt
python3 vagent.py

# Or use the installer:
bash installer/install.sh
```

> **No API key needed.** Backend handles everything securely.

## 📦 Or download the installer

See the [Releases page](https://github.com/otzpt/V-Agent/releases) for pre-packaged ZIPs.

## 🏗️ Architecture

```
V-Agent Desktop  (zero keys)
       │  POST /chat
       ▼
Backend Vercel  ◄── GROQ_API_KEY (server-side only)
       │
       ▼
  Groq API  (free, llama-3.3-70b)
```

## 🔌 AI Providers

| Provider | Setup | Cost |
|---|---|---|
| **Backend** (default) | None | Free |
| Local Ollama | Install Ollama | Free |
| Groq Direct | Your key | Free |
| OpenRouter | Your key | Free (:free models) |

## 🔒 Security

- Keys stored **only** in Vercel env vars
- Rate limiting: 30 req/min per IP
- Model whitelist (free only)
- Input sanitization
- `.env` never committed to git

See [SECURITY.md](SECURITY.md)

## 🛠️ Optional: Self-hosting

```bash
cd api
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
uvicorn chat:app --reload --port 8000
```

Settings → Backend URL → `http://localhost:8000`

## 📝 License

MIT
