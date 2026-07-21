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
  MCP context servers are fully supported
- **Agent slash commands** — `/model`, `/effort`, `/clear`, alongside Zed's
  `/compact` and `@` context (files, symbols, web fetch, threads, diagnostics)
- **V-Agent branding** — app icon, menus, and a dark default theme

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
