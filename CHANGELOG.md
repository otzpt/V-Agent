# Changelog

Notable changes to V-Agent. Releases before 1.0.1 are described on the
[GitHub releases page](https://github.com/otzpt/V-Agent/releases). Work that is
planned but not done lives in [ROADMAP.md](./ROADMAP.md).

## Unreleased

### Added

- **Arduino language for `.ino` files.** Uses the C++ grammar, plus extra
  highlighting for the Arduino API, grouped the way Arduino IDE's
  `keywords.txt` groups it: `Serial`, `Keyboard` and `Mouse` as types, `setup`
  and `loop` as keywords, core functions such as `pinMode`, `digitalWrite` and
  `delay` as built-in functions. Previously `.ino` was plain C++.
- **Arduino toolbar** on `.ino` files, laid out like Arduino IDE 2: Verify,
  Upload, a board selector and Serial Monitor, all driven by arduino-cli.
  - The board selector lists the boards plugged in, rescanning when opened. A
    choice is saved to the sketch's `sketch.yaml` with `arduino-cli board
    attach`, which Arduino IDE 2 and arduino-cli also read.
  - A board arduino-cli does not recognise (most CH340 clones) shows as
    *Unknown board*; clicking it asks which board it is.
  - **Select Other Board…** searches every board arduino-cli knows. Boards
    whose core is not installed are marked; picking one installs the core in a
    terminal, then selects the board.
  - With no board chosen, Verify and Upload ask for one instead of failing.
- **Tools menu** with Verify, Upload, Serial Monitor and Board…, and an
  **Arduino Upload for C/C++ Files** toggle (remembered between sessions).
  With it on, `.c` and `.cpp` files get the Arduino controls. arduino-cli only
  builds a folder holding an `.ino` named after it, so the file's folder is
  copied into a generated sketch in V-Agent's data folder; the user's folder is
  not changed.
- **arduino-language-server** for `.ino` completions and diagnostics, the
  server Arduino IDE 2 uses. Downloaded on first use, together with clangd if
  none is available. It starts for the chosen board (the Uno when none is
  chosen) and restarts when the board changes.
- **Serial monitor baud rate from the sketch.** The monitor opens at the rate
  in the first `Serial.begin(...)` instead of arduino-cli's 9600 default.
- **Arduino tasks** (task: spawn): Upload, Compile, Serial Monitor and Install
  Board Core.
- **▶ Run button** in the editor toolbar for code files, the same action as
  **Run > ▶ Build & Run**. It picks the compiler or interpreter from the
  extension with no configuration: C, C++, Python, JavaScript, TypeScript, Go,
  Rust (`cargo run` inside a Cargo project, `rustc` otherwise), Java, Ruby, PHP,
  Lua and shell scripts. If none is installed, it offers to install one. On a
  sketch, Build & Run uploads.

### Fixed

- **Run > ▶ Build & Run did nothing.** It started a task named "▶ Build & Run"
  that was never defined anywhere in the repository. It now runs the active
  file directly. The README said <kbd>F9</kbd> ran it, but F9 toggles a
  breakpoint; the README now points to the toolbar button and the menu.
- The missing-arduino-cli prompt on Linux tried to run `winget`. It now runs
  arduino-cli's official `install.sh` into `~/.local/bin`.

### Security

- `default_fqbn` and `default_port` read from a project's `sketch.yaml` are
  ignored unless they only contain characters an FQBN or port uses, since
  `sketch.yaml` can come from someone else's project and the values reach
  shell commands.

## 1.2.1 (2026-10-10)

- **Synced upstream Zed to v1.16.3** (`03e2e21e3094`): a crash fix in the Git
  panel when a section is collapsed. The fork never modified that file, so it
  is byte-identical to upstream.
- **Removed dead sign-in code** left by an earlier upsell removal: unused
  variables and the never-read `show_sign_in` and `show_user_menu` fields of
  `TitleBarSettings`, plus their Settings UI toggles, which did nothing. The
  keys are still accepted in `settings.json`, so no settings file breaks.
- **FreeBSD release job:** installs `fontconfig` and writes a stub `bzip2.pc`
  (FreeBSD's base system has the library but no pkg-config module), each
  confirmed by a probe workflow in the same FreeBSD 14.2 VM. The job still
  fails later on compile errors in `crates/gpui_linux`; see the roadmap.

## 1.1.2 (2026-09-19)

- **Default Python language server is plain Pyright again** (`8c127a14e1`).
  Upstream Zed switched to `basedpyright` in v0.204.0 and the fork inherited
  it, which took one existing file from 0 to 23 warnings. `basedpyright` stays
  available per project with
  `"languages": {"Python": {"language_servers": ["basedpyright"]}}`.
- **Synced upstream Zed to v1.16.2** (`a5faebb646a0`). Includes the Wasmtime
  WASI fix for an extension filesystem sandbox escape
  ([zed-industries/zed#63140](https://github.com/zed-industries/zed/pull/63140));
  `wasmtime` moves from 36.0.12 to 36.0.14.
- **Void Linux packaging.**
  - `packaging/void/template`, an `xbps-src` template (`v-agent-bin`) for
    submission to `void-packages`. Building it produced
    `v-agent-bin-1.1.1_1.x86_64.xbps` (405 MB, 2284 MB installed) with no lint
    warnings.
  - A `Package Linux (Void .xbps)` step in the release workflow, building the
    same package with `xbps-create` in `ghcr.io/void-linux/void-glibc-full`.
  - Vulkan confirmed on Void 6.18.50_1 with an NVIDIA RTX 3050 Mobile (driver
    595.91.07): the release binary reached `Rendered first frame` on the GPU,
    not software rendering. Two findings from that check: a broken CUDA driver
    state does not mean Vulkan is broken (they are separate entry points), and
    Void's `mesa` installs no Vulkan driver, so the docs name the
    `mesa-vulkan-*` package to install.
  - Docs in `docs/src/development/voidlinux.md`.

## 1.1.0 (2026-08-14)

- **Fedora/RHEL `.rpm`**, built in a `fedora:latest` container. `Requires:`
  come from rpmbuild's own ELF scan, so they follow the binary's real linkage.
- **FreeBSD build fix:** the `scap_screen_capture` module was compiled on
  FreeBSD against a type alias defined only for Windows and Linux
  (`error[E0425]: cannot find type PlatformScreenCaptureFrame`).

## 1.0.1 (2026-07-26)

- **Arch Linux packaging** in `packaging/arch/`: `PKGBUILD-bin` (the AUR
  package `v-agent-bin`, installing the release binary) and `PKGBUILD`
  (from source). Both declare `depends=()` mirroring the official Arch `zed`
  package.
- The release workflow's `.pkg.tar.zst` previously had no `depends` and could
  not start on a clean system. It now carries the same set and takes `pkgver`
  from `script/get-crate-version`.
- **FreeBSD build job** in the release workflow, inside a FreeBSD 14.2 VM
  (`vmactions/freebsd-vm`), reusing upstream's `script/freebsd`. It is
  `continue-on-error`, so a FreeBSD failure cannot hold back a release.
