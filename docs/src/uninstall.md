---
title: Uninstall
description: "This guide covers how to uninstall V-Agent on different operating systems."
---

# Uninstall

This guide covers how to uninstall V-Agent on different operating systems. See [Installation](./installation.md) for how V-Agent is packaged on each platform.

## Linux

### Arch, Manjaro, EndeavourOS, CachyOS

```sh
sudo pacman -R v-agent
```

### Debian, Ubuntu, Mint, Pop!\_OS

```sh
sudo apt remove v-agent
```

### AppImage or portable tarball

These are self-contained — delete the `.AppImage` file or the extracted tarball directory.

### Removing User Data (Optional)

To completely remove V-Agent's configuration, data, and cache:

```sh
rm -rf ~/.config/v-agent
rm -rf ~/.local/share/v-agent
rm -rf ~/.cache/v-agent
rm -rf ~/.local/state/v-agent
```

(Or the equivalents under `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, `$XDG_CACHE_HOME`, `$XDG_STATE_HOME` if you've customized those.)

## Windows

### Standard Installation

1. Quit V-Agent if it's running
2. Open Settings (Windows key + I)
3. Go to "Apps" > "Installed apps" (or "Apps & features" on Windows 10)
4. Search for "V-Agent"
5. Click the three dots menu next to V-Agent and select "Uninstall"
6. Follow the prompts to complete the uninstallation

Alternatively, you can:

1. Open the Start menu
2. Right-click on V-Agent
3. Select "Uninstall"

### Portable (.zip)

Delete the extracted folder — nothing else was installed.

### Removing User Data (Optional)

To completely remove all V-Agent configuration files and data:

1. Press `Windows key + R` to open Run
2. Type `%APPDATA%` and press Enter
3. Delete the `V-Agent` folder if it exists
4. Press `Windows key + R` again, type `%LOCALAPPDATA%` and press Enter
5. Delete the `V-Agent` folder if it exists

## macOS

V-Agent doesn't ship prebuilt macOS releases yet (see [Installation](./installation.md)). If you built it from source, quit the app and remove:

```sh
rm -rf ~/.config/v-agent
rm -rf ~/Library/Application\ Support/V-Agent
rm -rf ~/Library/Caches/V-Agent
rm -rf ~/Library/Logs/V-Agent
rm -rf ~/.local/state/V-Agent
```

## Troubleshooting

If you encounter issues during uninstallation:

- **macOS/Windows**: Ensure V-Agent is completely quit before attempting to uninstall. Check Activity Monitor (macOS) or Task Manager (Windows) for any running V-Agent processes.
- **All platforms**: If you want to start fresh while keeping V-Agent installed, you can delete the configuration directories instead of uninstalling the application entirely.

For additional help, see the [Linux-specific documentation](./linux.md) or [open an issue](https://github.com/otzpt/V-Agent/issues).
