---
title: CLI Reference
description: "Reference for V-Agent's command-line interface, including opening files and directories and controlling V-Agent from scripts."
---

# CLI Reference

Upstream Zed ships a separate small CLI wrapper binary (`zed`) alongside the main app, with flags like `--wait`, `--new`/`--add`/`--reuse`/`--existing`, `--uninstall`, and shell completions. That wrapper (`crates/cli`) is not built or packaged by V-Agent's release workflow (`.github/workflows/release.yml`) — released V-Agent builds ship a single `v-agent` binary (`crates/zed`), which has its own, smaller set of command-line flags. This page documents what `v-agent` actually accepts; flags from upstream's `zed` wrapper that aren't listed here are not available.

## Usage

```sh
v-agent [OPTIONS] [PATHS_OR_URLS]...
```

## Opening Files and Directories

Open a file:

```sh
v-agent myfile.txt
```

Open a directory as a workspace:

```sh
v-agent ~/projects/myproject
```

Open multiple files or directories:

```sh
v-agent file1.txt file2.txt ~/projects/myproject
```

Open a file at a specific line and column (existing paths only — the `:line:column` suffix is ignored for paths that don't exist):

```sh
v-agent myfile.txt:42        # Open at line 42
v-agent myfile.txt:42:10     # Open at line 42, column 10
```

## Options

### `--diff <OLD_PATH> <NEW_PATH>`

Open a diff view comparing two files. Can be specified multiple times. When directories are given, recurses into them and shows all changed files in one multi-diff view:

```sh
v-agent --diff file1.txt file2.txt
v-agent --diff old.rs new.rs --diff old2.rs new2.rs
```

### `--user-data-dir <DIR>`

Use a custom directory for all user data (database, extensions, logs) instead of the default location:

```sh
v-agent --user-data-dir ~/.v-agent-custom
```

Default locations:

- **macOS:** `~/Library/Application Support/V-Agent`
- **Linux:** `$XDG_DATA_HOME/v-agent` (typically `~/.local/share/v-agent`)
- **Windows:** `%LOCALAPPDATA%\V-Agent`

### `--dev-container`

Open the project in a dev container. Automatically triggers "Reopen in Dev Container" if a `.devcontainer/` configuration is found in the project directory:

```sh
v-agent --dev-container ~/projects/myproject
```

### `--system-specs`

Print system specs to the terminal instead of opening a window. Useful for filing a bug report when a graphics initialization error prevents V-Agent from starting, so you can't run {#action zed::CopySystemSpecsIntoClipboard} from inside the app:

```sh
v-agent --system-specs
```

## URL Handling

`v-agent` can open `zed://`, `file://`, and `ssh://` URLs passed as positional arguments:

```sh
v-agent zed://settings
v-agent file:///home/you/.zshrc
v-agent ssh://me@example.com/abs/path
v-agent ssh://me@example.com:/abs/path
v-agent ssh://me@example.com/~/project
v-agent ssh://me@example.com:~/project
```

## Not Currently Available

These are documented for upstream Zed's `zed` CLI wrapper but do not apply to V-Agent's `v-agent` binary:

- `--wait` / `-w`, and using V-Agent as `$EDITOR`/`$VISUAL` for tools like `git commit` — there's no wrapper process to block on
- `--new`/`-n`, `--add`/`-a`, `--reuse`/`-r`, `--existing`/`-e` window-reuse controls
- `--uninstall` — see [Uninstall](../uninstall.md) for the actual `pacman -R` / `apt remove` / delete-the-AppImage commands
- `--completions <SHELL>` shell completions
- `--version`/`-v` — check the running version from inside the app instead (see [Update](../update.md))
- reading from stdin via a bare `-` path
- `--foreground` on Linux/macOS (Windows-only, undocumented flag used to match the console-attach behavior macOS gets by default)
