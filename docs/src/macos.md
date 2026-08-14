---
title: V-Agent on macOS
description: "V-Agent doesn't ship prebuilt macOS releases yet. This page covers building from source and what to expect once you do."
---

# V-Agent on macOS

V-Agent doesn't ship prebuilt macOS releases yet — [`.github/workflows/release.yml`](https://github.com/otzpt/V-Agent/blob/main/.github/workflows/release.yml) only builds Windows and Linux for now (it needs a Mac runner and signing setup; see [ROADMAP.md](https://github.com/otzpt/V-Agent/blob/main/ROADMAP.md)). The upstream Zed engine V-Agent is built on supports macOS, so building from source works today.

## Building from Source

See the [macOS development documentation](./development/macos.md) for build instructions. Run the built binary with:

```sh
./target/release/v-agent .
```

## System Requirements

- macOS 10.15.7 (Catalina) or later
- Apple Silicon (M1/M2/M3/M4) or Intel processor

V-Agent uses Metal for GPU-accelerated rendering, which is available on all supported macOS versions.

## Uninstall

If you built V-Agent from source and want to remove it, delete your build directory and, optionally, your settings and extensions:

```sh
rm -rf ~/.config/v-agent
rm -rf ~/Library/Application\ Support/V-Agent
rm -rf ~/Library/Caches/V-Agent
rm -rf ~/Library/Logs/V-Agent
rm -rf ~/.local/state/V-Agent
```

## Troubleshooting

### GPU or rendering issues

V-Agent uses Metal for rendering. If you experience graphical glitches:

1. Ensure macOS is up to date
2. Restart your Mac to reset the GPU state
3. Check Activity Monitor for GPU pressure from other apps

### High memory or CPU usage

If V-Agent uses more resources than expected:

1. Check for runaway language servers in the terminal output ({#action zed::OpenLog})
2. Try disabling extensions one by one to identify conflicts
3. For large projects, consider using [project settings](./reference/all-settings.md#file-scan-exclusions) to exclude unnecessary folders from indexing

For additional help, see the [Troubleshooting guide](./troubleshooting.md) or [open an issue](https://github.com/otzpt/V-Agent/issues).
