---
title: Install V-Agent - macOS, Linux, Windows
description: Download and install V-Agent on Linux or Windows. Covers native packages, AppImage, portable builds, and building from source.
---

# Installing V-Agent

## Download V-Agent

All commands below pull the **latest release** from [GitHub Releases](https://github.com/otzpt/V-Agent/releases). V-Agent has no auto-update mechanism yet — re-run the install command (or download a new release manually) to update.

### Linux

**Arch, Manjaro, EndeavourOS, CachyOS** — native package:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-x86_64.pkg.tar.zst
sudo pacman -U V-Agent-x86_64.pkg.tar.zst
```

**Debian, Ubuntu, Mint, Pop!\_OS** — `.deb`:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-amd64.deb
sudo apt install ./V-Agent-amd64.deb
```

**Fedora, RHEL, openSUSE** — `.rpm`:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-x86_64.rpm
sudo dnf install ./V-Agent-x86_64.rpm
```

**Any distro** — AppImage, no install needed:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-x86_64.AppImage
chmod +x V-Agent-x86_64.AppImage
./V-Agent-x86_64.AppImage
```

**Portable tarball** — unpack and run:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-linux-x86_64.tar.gz
tar -xzf V-Agent-linux-x86_64.tar.gz
./V-Agent-linux-x86_64/v-agent
```

**Void Linux (glibc)** — same tarball, no `xbps` package yet:

```sh
curl -LO https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-linux-x86_64.tar.gz
tar -xzf V-Agent-linux-x86_64.tar.gz
./V-Agent-linux-x86_64/v-agent
```

**Not native support** — there is no `xbps` template and no Void CI job.
This is the same generic tarball as any untested distro, gated on the same
two requirements: glibc ≥ 2.31 (check with `ldd --version`; the **musl**
Void variant has no system glibc and cannot run this at all) and a
Vulkan-capable GPU driver (`vulkaninfo --summary`). See the
[roadmap](https://github.com/otzpt/V-Agent/blob/main/ROADMAP.md) for what
real Void support would take.

See [runtime dependencies and uninstall instructions](./linux.md) for the Linux build.

### Windows

**Installer (.msi)** — installs to `%LOCALAPPDATA%\Programs\V-Agent`, no administrator rights required:

```powershell
irm https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-x64.msi -OutFile V-Agent.msi
msiexec /i V-Agent.msi
```

**Portable (.zip)** — unpack and run `v-agent.exe`:

```powershell
irm https://github.com/otzpt/V-Agent/releases/latest/download/V-Agent-windows-x86_64.zip -OutFile V-Agent.zip
Expand-Archive V-Agent.zip -DestinationPath V-Agent
.\V-Agent\v-agent.exe
```

### macOS

Not built yet. [`.github/workflows/release.yml`](https://github.com/otzpt/V-Agent/blob/main/.github/workflows/release.yml) only targets Windows and Linux for now — see [ROADMAP.md](https://github.com/otzpt/V-Agent/blob/main/ROADMAP.md). Build from source in the meantime; see the [macOS development docs](./development/macos.md).

### A note on signing

Releases are **not code-signed**. Windows SmartScreen will say "unknown publisher" (_More info → Run anyway_). This is the absence of a paid certificate, not a defect. Every file's checksum is on the release page if you want to verify it.

## System Requirements

### macOS

V-Agent supports the following macOS releases:

| Version       | Codename | Apple Status   | V-Agent Status      |
| ------------- | -------- | -------------- | ------------------- |
| macOS 26.x    | Tahoe    | Supported      | Supported           |
| macOS 15.x    | Sequoia  | Supported      | Supported           |
| macOS 14.x    | Sonoma   | Supported      | Supported           |
| macOS 13.x    | Ventura  | Supported      | Supported           |
| macOS 12.x    | Monterey | EOL 2024-09-16 | Supported           |
| macOS 11.x    | Big Sur  | EOL 2023-09-26 | Partially Supported |
| macOS 10.15.x | Catalina | EOL 2022-09-12 | Partially Supported |

The macOS releases labelled "Partially Supported" (Big Sur and Catalina) do not support screen sharing via Collaboration, which connects through Zed Industries' collaboration servers — V-Agent doesn't run its own. These features use the [LiveKit SDK](https://livekit.io) which relies upon [ScreenCaptureKit.framework](https://developer.apple.com/documentation/screencapturekit/) only available on macOS 12 (Monterey) and newer.

#### Mac Hardware

V-Agent supports machines with Intel (x86_64) or Apple (aarch64) processors that meet the above macOS requirements:

- MacBook Pro (Early 2015 and newer)
- MacBook Air (Early 2015 and newer)
- MacBook (Early 2016 and newer)
- Mac Mini (Late 2014 and newer)
- Mac Pro (Late 2013 or newer)
- iMac (Late 2015 and newer)
- iMac Pro (all models)
- Mac Studio (all models)

### Linux

V-Agent supports 64-bit Intel/AMD (x86_64) and 64-bit Arm (aarch64) processors.

V-Agent requires a Vulkan 1.3 driver and the following desktop portals:

- `org.freedesktop.portal.FileChooser`
- `org.freedesktop.portal.OpenURI`
- `org.freedesktop.portal.Secret` or `org.freedesktop.Secrets`

### Windows

V-Agent supports the following Windows releases:
| Version | V-Agent Status |
| ------------------------- | ------------------- |
| Windows 11, version 22H2 and later | Supported |
| Windows 10, version 1903 and later | Supported |

A 64-bit operating system is required to run V-Agent.

#### Windows Hardware

V-Agent supports machines with x64 (Intel, AMD) or Arm64 (Qualcomm) processors that meet the following requirements:

- Graphics: A GPU that supports DirectX 11 (most PCs from 2012+).
- Driver: Current NVIDIA/AMD/Intel/Qualcomm driver (not the Microsoft Basic Display Adapter).

### FreeBSD

Not yet available as an official download. Can be built [from source](./development/freebsd.md).

### Web

Not supported at this time. See our [Platform Support issue](https://github.com/zed-industries/zed/issues/5391).
