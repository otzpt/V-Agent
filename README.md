# V-Agent v0.4

**Local AI Coding Agent** — Zero telemetry. Your code never leaves your machine.

---

## What is V-Agent?

V-Agent is a local-first AI coding assistant that runs entirely on your machine. It uses **Ollama** to run large language models locally, providing AI-powered code generation, editing, explanation, and planning — all without sending your code to any cloud service.

The project includes both a **command-line interface** (terminal) and a **graphical user interface** (GUI) built with Python/Tkinter, inspired by modern AI coding tools.

---

## Features

- **100% Local** — No data leaves your machine. No telemetry.
- **GUI + CLI** — Modern dark-themed graphical interface + traditional terminal
- **Hardware Detection** — Auto-detects CPU, RAM, GPU, VRAM
- **Smart Model Recommendations** — Suggests the best model for your hardware
- **First-Run Wizard** — Guided setup on first launch
- **Git Integration** — Status, diff, log, branch, commit, push, pull
- **Intent Detection** — Automatically understands if you want to create, edit, explain, or plan
- **Session Persistence** — Saves and restores your conversation history
- **Multiple File Types** — Supports C++, Python, JavaScript, HTML, CSS, PowerShell, Bash, and more
- **VOIDTUNE Theme** — Custom dark purple color scheme
- **Streaming Output** — Real-time AI response display
- **Clipboard Support** — Copy AI responses with `/copy`
- **Undo Support** — Revert saved files with `/undo`

---

## Screenshots

![V-Agent GUI](screenshots/gui.png)
*V-Agent Terminal GUI — Dark theme with AI chat*

![V-Agent CLI](screenshots/cli.png)
*V-Agent Command Line Interface*

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10/11 64-bit | Windows 11 64-bit |
| **RAM** | 8 GB | 16 GB |
| **VRAM** | 4 GB | 8 GB |
| **Disk** | 10 GB free | 20 GB free |
| **Python** | 3.8+ (for GUI) | 3.11+ |
| **Ollama** | Latest | Latest |

---

## Quick Start

### 1. Install Ollama

Download and install Ollama from:  
[https://ollama.com/download/windows](https://ollama.com/download/windows)

### 2. Pull a Model

```bash
ollama pull qwen2.5-coder:14b
