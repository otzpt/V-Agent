# V-Agent

A native, GPU-accelerated code editor with local-first AI.

V-Agent is a **fork of [Zed](https://github.com/zed-industries/zed)** — it keeps
Zed's Rust engine (LSP, tree-sitter, multi-cursor, vim mode, splits, git,
terminal, extensions) and layers on its own identity and workflow.

> **V-Agent is not affiliated with, endorsed by, or sponsored by Zed Industries, Inc.**
> "Zed" is a trademark of Zed Industries, Inc. and is used here only to identify
> the upstream project this is derived from. See [CREDITS.md](./CREDITS.md).

## What V-Agent adds on top of Zed

- **Activity bar** — a VS Code-style left icon rail (Explorer, Search, Git, AI,
  Terminal, Extensions, Settings) with true open/close toggling
- **Colorful file icons** — Material-style language icons in the project tree
- **One-click Build & Run** — press <kbd>F9</kbd> and V-Agent detects the
  language, finds your compiler (gcc, python, node, go, rustc, …), builds and
  runs it. If the toolchain is missing, it offers to install it
- **Local-first AI** — the agent panel defaults to a local
  [Ollama](https://ollama.com) model (no API key, nothing leaves your machine).
  Bring your own key (Groq, OpenAI, Anthropic) for a cloud model if you prefer.
  MCP context servers are fully supported (see
  [Choosing a local model](#choosing-a-local-model))
- **Agent slash commands** — `/model`, `/effort`, `/clear`, alongside Zed's
  `/compact` and `@` context (files, symbols, web fetch, threads, diagnostics)
- **V-Agent branding** — app icon, menus, and a dark default theme

## Choosing a local model

The agent panel needs a model that supports **tool calling** — without it the
model can read your prompt but can't open files, search, or edit anything. Many
popular "coder" models are completion/fill-in-the-middle models and have no tool
support at all. Check before you commit to one:

```sh
ollama show <model>   # look for "tools" under Capabilities
```

| Model | Tools | Notes |
|---|---|---|
| `qwen3:8b` | ✅ | Trained for agentic use; thinking mode improves tool *selection*. Good 8 GB VRAM pick |
| `qwen3-coder:30b` | ✅ | Best local agentic coder, but ~18 GB — needs 24 GB VRAM |
| `devstral:24b` | ✅ | Purpose-built for agentic SWE; ~14 GB |
| `qwen2.5-coder:7b` | ✅ | Strong at completion, **weak at deciding to use tools** — often needs prompting |
| `llama3.1:8b` | ✅ | Tool calling fine, code ability weak |
| `deepseek-coder-v2` | ❌ | **No tool support** — completion/FIM only, cannot drive the agent |

**Sizing:** a Q4 model needs roughly its file size in VRAM. Exceeding your card
spills to system RAM and gets dramatically slower — Ollama will still run it, so
slowness is usually the symptom, not an error.

**Context windows are handled for you.** Ollama defaults to a small context
(2–4k tokens), which silently truncates tool definitions out of the prompt — the
single most common reason a local model "ignores" its tools. V-Agent reads each
model's real context length and sends it explicitly, so you don't have to set
`num_ctx` yourself.

**If local isn't enough:** agentic coding is genuinely hard below ~14B. A
practical split is a local model for completion and inline edits, with a
bring-your-own-key provider (Groq's free tier is fast and runs 32B-class models)
for agent mode. Local-first doesn't have to mean local-only.

## Coding-time tracking (Hackatime / WakaTime) — optional

V-Agent can log how long you spend coding to
[Hackatime](https://hackatime.hackclub.com) or any WakaTime-compatible service.
**It is off unless you deliberately set it up**, and it is not enabled by any
default in V-Agent.

To turn it on:

1. Get your config from
   [hackatime.hackclub.com/my/wakatime_setup](https://hackatime.hackclub.com/my/wakatime_setup).
   It writes `~/.wakatime.cfg` with your `api_url` and `api_key`.
2. Install the agent binary, `wakatime-cli`. If you've used a WakaTime plugin in
   another editor you already have it in `~/.wakatime/`. If not, V-Agent will
   notice and offer to download it for you from the official
   [wakatime/wakatime-cli](https://github.com/wakatime/wakatime-cli) releases —
   in a visible terminal that shows the URL and destination first.

**What gets sent, and to whom:** heartbeats go to the `api_url` in *your*
`~/.wakatime.cfg` (Hackatime, or WakaTime, or your own server) — never to
V-Agent, and never to Zed. Each heartbeat contains the file path, project name,
language, a timestamp, and whether it was a save. Your file *contents* are never
sent. Sending is handled by `wakatime-cli` itself, the same agent every other
WakaTime editor plugin uses.

**To turn it off:** delete or rename `~/.wakatime.cfg`. V-Agent then does
nothing at all — no network calls, no prompts.

## Building from source

Requirements: [Rust](https://rustup.rs) (stable), `protoc`, CMake, plus the
Windows 10/11 SDK on Windows (Vulkan and wayland/x11 dev libraries on Linux).

```sh
git clone <this-repo>
cd v-agent
cargo build --release -p zed
```

The binary is written to `target/release/`.

## License

V-Agent is a derivative work of Zed, which is licensed under
**GPL-3.0-or-later**. Accordingly, **V-Agent is released under
GPL-3.0-or-later** — see [LICENSE-GPL](./LICENSE-GPL). Portions of the codebase
(GPUI and other libraries) are Apache-2.0 — see [LICENSE-APACHE](./LICENSE-APACHE).

Third-party attribution — Zed, One Dark, Nightfox/Carbonfox, and the Material
Icon Theme — is documented in [CREDITS.md](./CREDITS.md).
