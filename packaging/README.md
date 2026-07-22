# Packaging & platform builds

V-Agent is a native GPU application. Each platform's artifact must be built on
that platform (or cross-compiled with its SDK) — there is no single machine
that can produce them all. This directory holds the Windows installer; the
other platforms are described here so the work is not lost.

## What a full release looks like

Matching upstream, a complete release publishes:

| Artifact | Platform | Built on |
|---|---|---|
| `V-Agent-x86_64.exe` / `.msi` | Windows x64 | Windows (or Windows CI runner) |
| `V-Agent-aarch64.exe` | Windows ARM64 | Windows, cross-compiled |
| `V-Agent-x86_64.dmg` | macOS Intel | **macOS only** (Apple SDK + signing) |
| `V-Agent-aarch64.dmg` | macOS Apple Silicon | **macOS only** |
| `v-agent-linux-x86_64.tar.gz` | Linux x64 | Linux (Vulkan + wayland/x11 dev libs) |
| `v-agent-linux-aarch64.tar.gz` | Linux ARM64 | Linux, cross-compiled |
| `v-agent-remote-server-*` (6) | per platform | the remote SSH server, per OS/arch |
| `bwrap-linux-*` (2) | Linux | bubblewrap sandbox helper |

**You cannot build the macOS or Linux artifacts on Windows.** A `.dmg` needs a
Mac with the Apple SDK and code-signing; the Linux build needs a Linux system
with GPU development libraries. The correct way to produce all platforms is
**CI** — GitHub Actions provides free macOS, Linux and Windows runners, and a
release workflow builds each artifact on its own runner. (Note macOS runners
bill at ~10x the minute rate.)

Upstream's release workflows were removed from this fork during the licensing
cleanup; a V-Agent release workflow has not yet been written. Until it is,
only the Windows build below is produced locally.

## Windows installer (this directory)

`v-agent.wxs` — a WiX v5 manifest for a **per-user** MSI. It installs to
`%LOCALAPPDATA%\Programs\V-Agent` (no administrator rights) and does not touch
a separately installed Zed. It bundles the editor plus its runtime siblings:
`conpty.dll` and `OpenConsole.exe` (terminal), and `amd_ags_x64.dll` (AMD's
GPU-services redistributable — required on AMD GPUs, harmless otherwise).

### Build it

```powershell
# 1. Build the release binary (produces v-agent.exe)
cargo build --release --bin v-agent

# 2. Install the WiX tool once
dotnet tool install --global wix

# 3. Build the MSI into Downloads
pwsh packaging/windows/build-msi.ps1 `
    -TargetDir C:\path\to\target `
    -OutFile   $env:USERPROFILE\Downloads\V-Agent-1.0.0-x64.msi
```

The script stages the payload onto an ASCII path first, because the repository
may live under a path containing non-ASCII characters that some Windows build
tools mishandle.

### Not code-signed

The MSI is **unsigned**. On first run Windows SmartScreen shows
"unrecognized app" / "unknown publisher" — click *More info → Run anyway*. This
is the absence of a paid code-signing certificate, not a defect. Tell testers
so the warning does not alarm them.

### Install location and upgrades

Per-user, `%LOCALAPPDATA%\Programs\V-Agent`. The `UpgradeCode` in `v-agent.wxs`
is stable, so a newer MSI upgrades an older one in place. It will **not**
replace a differently-packaged install (e.g. the legacy Tauri build) — those
carry a different upgrade code and must be removed manually.
