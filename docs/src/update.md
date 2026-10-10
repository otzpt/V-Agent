---
title: Update V-Agent
description: "V-Agent has no auto-updater. Check for updates from the menu, then download new releases from GitHub and reinstall."
---

# Update V-Agent

V-Agent does not update itself. Upstream Zed's auto-updater resolves releases against Zed Industries' own server, which would download and install _Zed_ over V-Agent — so V-Agent's updater is disabled at the code level, not just by a setting. Flipping the `auto_update` setting on has no effect.

## Check for a new version

Choose **V-Agent > Check for Updates** in the application menu (or run {#action auto_update::Check} from the Command Palette). V-Agent asks GitHub, once, whether a newer release exists and shows the result in a dialog. If there is one, **View release** opens the releases page in your browser. Nothing is downloaded or installed.

The check only runs when you ask for it. It is a single HTTPS request to `api.github.com`. Like any web request it shows GitHub your IP address, and V-Agent adds only a `User-Agent` header, `V-Agent/<version> (<os>; <arch>)`. No account, token or telemetry ID is sent.

## How to update

Download the latest release from [GitHub Releases](https://github.com/otzpt/V-Agent/releases) and reinstall, the same way you installed it the first time. See [Installation](./installation.md) for the commands for your platform (`pacman -U`, `apt install`, replacing the AppImage/tarball, etc.).

## How to check your current version

To check which version of V-Agent you're using:

Open the Command Palette (Cmd+Shift+P on macOS, Ctrl+Shift+P on Linux/Windows).

Type and select {#action zed::About}. A modal will appear with your version information.
