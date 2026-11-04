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
- **Currently synced to upstream `v1.16.3` (commit `03e2e21e3094`).**

V-Agent's history starts from a squashed snapshot rather than a git fork, so
nothing in the commit graph records which upstream commit it corresponds to.
The line above is that record, and it is what makes the next sync cheap: add
`https://github.com/zed-industries/zed` as a remote, fetch it, and diff or
merge against the commit named there. Without it the base has to be
re-derived by scanning upstream history for the tree that differs least,
which is how this one was found. Update the line whenever the fork is
synced.

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
- Added Arduino support: an Arduino language for `.ino`, an Arduino IDE
  2-style toolbar and Tools menu driven by arduino-cli, and
  arduino-language-server for completions
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

## Arduino

### arduino-cli
The Arduino toolbar, Tools menu and tasks (`crates/zed/src/vagent_arduino.rs`,
`crates/languages/src/arduino.rs`) run arduino-cli as an external program for
board detection, the board list, `board attach`, compiling, uploading, the
serial monitor and core installs.

- Upstream: https://github.com/arduino/arduino-cli
- Copyright © Arduino SA
- License: GPL-3.0
- What V-Agent takes from it: the JSON layout of `board list --format json`
  and `board search --format json`, the `sketch.yaml` keys written by
  `board attach` (`default_port`, `default_fqbn`), the FQBN format
  (`vendor:architecture:board[:options]`), the sketch rule that a folder needs
  an `.ino` named after it, and the serial monitor's `baudrate` setting. No
  arduino-cli source code is copied, and arduino-cli is not redistributed;
  users install it themselves. The Linux install prompt runs arduino-cli's
  official `install.sh`.

### arduino-language-server
`.ino` files use it for completions and diagnostics
(`ArduinoLspAdapter` in `crates/languages/src/arduino.rs`).

- Upstream: https://github.com/arduino/arduino-language-server
- Copyright © Arduino SA
- License: AGPL-3.0
- It runs as a separate program. V-Agent downloads the official release from
  GitHub into its own data folder on first use and starts it with the
  `-clangd`, `-cli`, `-cli-config` and `-fqbn` flags its README documents. It
  is not linked into V-Agent and no source code is copied.

### Arduino IDE 2
The toolbar layout (Verify, Upload, board selector, Serial Monitor) and the
behaviour of asking for a board instead of failing follow Arduino IDE 2.
Installing a missing core when its board is chosen follows IDE 2's
`BoardsAutoInstaller`
(`arduino-ide-extension/src/browser/boards/boards-auto-installer.ts`).
Starting arduino-language-server for the selected board follows
`arduino-ide-extension/src/browser/contributions/ino-language.ts`. Reading
the monitor's baud rate from `Serial.begin(...)` is V-Agent's own; Arduino
IDE 2 has the user pick it.

- Upstream: https://github.com/arduino/arduino-ide
- Copyright © Arduino SA
- License: AGPL-3.0
- No Arduino IDE source code is copied.

### Arduino IDE 1.x keyword list
The extra Arduino colours (`crates/grammars/src/arduino/highlights.scm`) use
the identifier names and their KEYWORD1/KEYWORD2/KEYWORD3 categories from
`build/shared/lib/keywords.txt`, shipped as `lib/keywords.txt` in Arduino IDE
1.8.19.

- Upstream: https://github.com/arduino/Arduino
- Copyright © Arduino SA and the Arduino contributors
- License: the repository's `license.txt` places the IDE under the GNU GPL
  and the core libraries under the GNU LGPL; it does not name
  `keywords.txt` separately.
- Only the API names are used. The file itself is not copied.

---

## Everything else

All other third-party dependencies are declared in `Cargo.toml` /
`Cargo.lock` and retain their own licenses. Zed's own bundled asset licenses
remain in place (for example `assets/icons/LICENSES` and
`assets/themes/*/LICENSE`) and have not been modified.
