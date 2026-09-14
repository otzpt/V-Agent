---
title: V-Agent on Void Linux
description: "Installing and building V-Agent on Void Linux, and the quirks specific to it."
---

# V-Agent on Void Linux

Void is supported on the **glibc** variant only. Everything below assumes it.

## glibc or musl

Void ships two libc variants, chosen by which ISO was installed. The musl
images are named `-musl-` in the filename; the default is glibc.

```sh
ldd --version | head -1
```

The prebuilt binary is linked against glibc and cannot run on a musl install
under any circumstance, because there is no system glibc to fall back on.
Building the GUI from source against `x86_64-unknown-linux-musl` has never
been attempted; the only musl target the repository builds today is the
headless `remote_server` (see [Remote Development](../remote-development.md)).

Requirements: glibc 2.35 or newer, and a working Vulkan driver.

The 2.35 floor is MEASURED from the shipped binary, not copied from upstream
Zed's stated 2.31. `objdump -T` on the release binary shows non-weak
`__libc_start_main@GLIBC_2.34` and `hypot@GLIBC_2.35`, so it cannot start below
2.35. It tracks whatever runner the release workflow builds on, currently
`ubuntu-22.04`. Void is a rolling distribution and is well past this, but the
number matters for the dependency the package declares.

## Installing a Vulkan driver

This is the part that catches people out. Void has no `vulkan-driver` virtual
package, and installing `mesa` does **not** install a Vulkan ICD. The driver
is a separate package per GPU, and no V-Agent package can depend on it:

| GPU | Package |
|---|---|
| AMD | `mesa-vulkan-radeon` |
| Intel | `mesa-vulkan-intel` |
| NVIDIA (open source) | `mesa-vulkan-nouveau` |
| NVIDIA (proprietary) | `nvidia` (from the `nonfree` repository) |
| No GPU / software rendering | `mesa-vulkan-lavapipe` |

`vulkan-loader` is a dependency of the package and is pulled in for you.

To confirm the driver works before installing anything else:

```sh
sudo xbps-install -S Vulkan-Tools
vulkaninfo --summary
```

A line naming your GPU under `Devices:` means Vulkan is working. If it lists
no device, the ICD is missing: check `/usr/share/vulkan/icd.d/` for a `.json`
matching your GPU.

CUDA being broken is not evidence that Vulkan is broken. They are separate
driver entry points, and V-Agent uses only Vulkan.

## Installing V-Agent

### From the release `.xbps`

Download `v-agent-<version>_1.x86_64.xbps` from the
[releases page](https://github.com/otzpt/V-Agent/releases). xbps has no
equivalent of `pacman -U` or `dnf install ./file.rpm`: it installs from
repositories, so the directory holding the file has to be indexed first.

```sh
cd ~/Downloads
xbps-rindex -a v-agent-*.x86_64.xbps
sudo xbps-install -R ~/Downloads v-agent
```

The release asset name carries the version, so `releases/latest/download/` does
not resolve to it; take the filename from the releases page.

Do not rename the file. xbps looks it up as `<pkgver>.<arch>.xbps` from the
index it just wrote, and a renamed file fails with
`failed to checksum: No such file or directory`.

### Building the package yourself

`packaging/void/template` is an
[xbps-src](https://github.com/void-linux/void-packages) template that wraps the
same prebuilt binary. Unlike the release `.xbps`, xbps-src derives the library
dependencies from the binary's `NEEDED` entries rather than a hand-written
list:

```sh
git clone --depth 1 https://github.com/void-linux/void-packages
cd void-packages && ./xbps-src binary-bootstrap
cp -r /path/to/V-Agent/packaging/void srcpkgs/v-agent-bin
./xbps-src pkg v-agent-bin
sudo xbps-install --repository hostdir/binpkgs v-agent-bin
```

This does not require root until the final install step.

### Any-distro fallbacks

The `.AppImage` and the portable `.tar.gz` work on Void as on any other
distribution, subject to the same glibc and Vulkan requirements.

## Building from source

`script/linux` already detects `xbps-install` and installs the Void build
dependencies:

```sh
script/linux
cargo run
```

See [Building V-Agent for Linux](./linux.md) for the rest, which is not
Void-specific.

Note that `script/linux` installs no Vulkan ICD, only `vulkan-loader`. Install
the driver package for your GPU separately, as above, or the build will
succeed and the editor will fail to start.

## Package size

The release binary ships unstripped so that V-Agent's hang detector can
symbolize its own backtraces. Installed size is roughly 2.3 GB against a
405 MB download. This is inherited from the `debug = "limited"` setting in the
workspace release profile, not from the packaging.

## Upstreaming

Getting `v-agent` into the official `void-packages` repository requires review
by a Void maintainer, the same adoption problem that applies to Arch's official
repositories and to Debian. The realistic path if that stalls is a self-hosted
xbps repository, which users add once and then install from normally.
