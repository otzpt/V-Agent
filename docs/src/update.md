---
title: Update V-Agent
description: "V-Agent has no auto-updater. Download new releases from GitHub and reinstall to update."
---

# Update V-Agent

V-Agent does not update itself. Upstream Zed's auto-updater resolves releases against Zed Industries' own server, which would download and install _Zed_ over V-Agent — so V-Agent's updater is disabled at the code level, not just by a setting. Flipping the `auto_update` setting on has no effect.

## How to update

Download the latest release from [GitHub Releases](https://github.com/otzpt/V-Agent/releases) and reinstall, the same way you installed it the first time. See [Installation](./installation.md) for the commands for your platform (`pacman -U`, `apt install`, replacing the AppImage/tarball, etc.).

## How to check your current version

To check which version of V-Agent you're using:

Open the Command Palette (Cmd+Shift+P on macOS, Ctrl+Shift+P on Linux/Windows).

Type and select {#action zed::About}. A modal will appear with your version information.
