# Credits & Third-Party Attribution

V-Agent is built on open source. This file records what we use and under which
terms. Nothing here is our original work unless stated otherwise.

---

## Zed — the editor V-Agent is built on

**V-Agent is a fork of [Zed](https://github.com/zed-industries/zed)**, the
high-performance editor by Zed Industries, Inc.

- Upstream: https://github.com/zed-industries/zed
- Copyright © Zed Industries, Inc. and Zed contributors
- License: **GPL-3.0-or-later** (see `LICENSE-GPL`); portions such as GPUI and
  other libraries are Apache-2.0 (see `LICENSE-APACHE`)

Because V-Agent is a derivative work of GPL-3.0 software, **V-Agent is also
released under GPL-3.0-or-later**, and its complete corresponding source code is
published alongside any binaries we distribute.

**V-Agent is not affiliated with, endorsed by, or sponsored by Zed Industries,
Inc.** "Zed" is a trademark of Zed Industries, Inc.; it is used here only to
factually identify the upstream project V-Agent derives from. The V-Agent name,
logo, and branding are separate and are not Zed's.

### Summary of changes made in V-Agent

- Rebranded the application (name, menus, window/app icon, product metadata)
- Added a VS Code-style **activity bar** (left icon rail) to the workspace
- Added **one-click Build & Run** with compiler auto-detection and an
  install prompt when a toolchain is missing
- Added a **colorful file icon theme** (see Material Icon Theme below)
- Made panel toggling a true open/close toggle
- Added `/model`, `/effort`, and `/clear` agent slash commands
- Replaced the hosted "Zed AI" onboarding with a local-first setup
  (Ollama, or bring-your-own API key); removed the Zed-hosted AI provider
- Changed the default theme and various UI defaults

---

## Themes

### One Dark / One Light
Used as the base for Zed's bundled themes and as the starting point for the
derived "V-Agent Dark" theme.

- Copyright © 2014 GitHub Inc.
- License: MIT (see `assets/themes/one/LICENSE`)

### Nightfox / Carbonfox
The default theme references **Carbonfox**, from the Nightfox theme family.

- Upstream: https://github.com/EdenEast/nightfox.nvim
- Copyright © EdenEast
- License: MIT

*(Provided via a Zed theme extension; not redistributed in this repository.)*

---

## Icons

### Material Icon Theme
The colorful language/file icons in `extensions/vagent-icons/icons/` come from
the Material Icon Theme.

- Upstream: https://github.com/material-extensions/vscode-material-icon-theme
- Copyright © Philipp Kief
- License: MIT (see `extensions/vagent-icons/LICENSE`)

---

## Everything else

All other third-party dependencies are declared in `Cargo.toml` /
`Cargo.lock` and retain their own licenses. Zed's own bundled asset licenses
remain in place (for example `assets/icons/LICENSES` and
`assets/themes/*/LICENSE`) and have not been modified.
