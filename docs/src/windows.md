---
title: V-Agent on Windows
description: "Install V-Agent on Windows via the .msi installer or the portable .zip, both from GitHub Releases."
---

# V-Agent on Windows

## Installing V-Agent

See [Installation](./installation.md) for the `.msi` installer and portable `.zip` download commands, both from [GitHub Releases](https://github.com/otzpt/V-Agent/releases). There is no preview or nightly channel; every release is a single stable build, and V-Agent does not auto-update (see [Update](./update.md)).

You can also build V-Agent from source, see [these docs](./development/windows.md) for instructions.

V-Agent isn't available via winget or any other package manager yet.

## Uninstall

- Installed via installer: Use `Settings` → `Apps` → `Installed apps`, search for V-Agent, and click Uninstall.
- Built from source: Remove the build output directory you created (e.g., your target/install folder).

Your settings and extensions live in your user profile. When uninstalling, you can choose to keep or remove them.

## Remote Development (SSH)

V-Agent supports remote development on Windows through both SSH and WSL. You can connect to remote servers via SSH or work with files inside WSL distributions directly from V-Agent.

For detailed instructions on setting up and using remote development features, including SSH configuration, WSL setup, and troubleshooting, see the [Remote Development documentation](./remote-development.md).

## Troubleshooting

### V-Agent fails to start or shows a blank window

- Check that your hardware and operating system version are compatible with V-Agent. See our [installation guide](./installation.md) for more information.
- Update your GPU drivers from your GPU vendor (Intel/AMD/NVIDIA/Qualcomm).
- Ensure hardware acceleration is enabled in Windows and not blocked by third‑party software.
- Try launching V-Agent with no extensions or custom settings to isolate conflicts.

### Terminal issues

If activation scripts don’t run, update to the latest version and verify your shell profile files are not exiting early. For Git operations, confirm Git Bash or PowerShell is available and on PATH.

### SSH remoting problems

When prompted for credentials, use the graphical askpass dialog. If it doesn’t appear, check for credential manager conflicts and that GUI prompts aren’t blocked by your terminal.

### Graphics issues

#### V-Agent fails to open / degraded performance

V-Agent requires a DirectX 11 compatible GPU to run. If V-Agent fails to open, your GPU may not meet the minimum requirements.

To check if your GPU supports DirectX 11, run the following command:

```
dxdiag
```

This will open the DirectX Diagnostic Tool, which shows the DirectX version your GPU supports under `System` → `System Information` → `DirectX Version`.

If you're running V-Agent inside a virtual machine, it will use the emulated adapter provided by your VM. While V-Agent will work in this environment, performance may be degraded.
