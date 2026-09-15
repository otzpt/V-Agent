#!/bin/sh
#
# V-Agent installer.
#
#   curl -fsSL https://raw.githubusercontent.com/otzpt/V-Agent/main/install.sh | sh
#
# Picks the native package for your distribution and installs it, falling back
# to the portable tarball on anything untested. POSIX sh on purpose: this runs
# before we know anything about the machine, including whether bash exists.
#
# Environment:
#   VAGENT_VERSION=1.1.1   install a specific version instead of the latest
#   VAGENT_METHOD=tarball  force the portable tarball
#   VAGENT_PREFIX=~/.local install prefix for the tarball method
#   VAGENT_DRY_RUN=1       print what would happen, change nothing

set -eu

REPO="otzpt/V-Agent"
RELEASES="https://github.com/${REPO}/releases"
VOID_REPO="${RELEASES}/download/void-repo"
: "${VAGENT_PREFIX:=${HOME}/.local}"
: "${VAGENT_DRY_RUN:=0}"
: "${VAGENT_METHOD:=auto}"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

run() {
    if [ "$VAGENT_DRY_RUN" = "1" ]; then
        printf '  \033[2m[dry-run]\033[0m %s\n' "$*"
    else
        # shellcheck disable=SC2068
        $@
    fi
}

# Only ask for root when a step needs it, and say why.
SUDO=""
need_root() {
    [ "$(id -u)" = "0" ] && return 0
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    elif command -v doas >/dev/null 2>&1; then
        SUDO="doas"
    else
        die "need root to install system packages, but neither sudo nor doas is available"
    fi
}

have() { command -v "$1" >/dev/null 2>&1; }

# ------------------------------------------------------------ preflight -----

case "$(uname -s)" in
    Linux) ;;
    Darwin) die "macOS builds are not published yet. See ${RELEASES}" ;;
    *) die "$(uname -s) is not supported by this installer. See ${RELEASES}" ;;
esac

ARCH="$(uname -m)"
[ "$ARCH" = "x86_64" ] || die "only x86_64 is published today, this machine is ${ARCH}. See ${RELEASES}"

have curl || have wget || die "need curl or wget"
fetch() {
    # $1 url, $2 output path
    if have curl; then curl -fsSL "$1" -o "$2"
    else wget -qO "$2" "$1"; fi
}
fetch_stdout() {
    if have curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}

# musl cannot run these glibc-linked binaries at all, and saying so now is
# kinder than a confusing dynamic-loader error later.
if [ -e /lib/ld-musl-x86_64.so.1 ]; then
    die "this is a musl system. V-Agent's binaries are glibc-linked and its GUI has never been built against musl."
fi

# ------------------------------------------------------------- version ------

if [ -z "${VAGENT_VERSION:-}" ]; then
    say "looking up the latest release"
    # Deliberately not /releases/latest. The xbps repository is published as a
    # release on a fixed tag ("void-repo"), and any non-version tag in the repo
    # can become "latest" and break this. Take the newest tag that actually
    # looks like a version instead.
    VAGENT_VERSION="$(fetch_stdout "https://api.github.com/repos/${REPO}/releases?per_page=100" \
        | sed -n 's/.*"tag_name": *"v\([0-9][^"]*\)".*/\1/p' | head -1)"
    [ -n "$VAGENT_VERSION" ] || die "could not determine the latest version; set VAGENT_VERSION=x.y.z"
fi
say "version ${VAGENT_VERSION}"

DL="${RELEASES}/download/v${VAGENT_VERSION}"

# ----------------------------------------------------------- detection ------

DISTRO_ID=""
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-}"
    DISTRO_LIKE="${ID_LIKE:-}"
fi

method="$VAGENT_METHOD"
if [ "$method" = "auto" ]; then
    if   have xbps-install;                        then method=xbps
    elif have apt-get     && [ -n "$(command -v dpkg)" ]; then method=deb
    elif have dnf || have yum;                     then method=rpm
    elif have pacman;                              then method=pacman
    else method=tarball
    fi
fi
say "install method: ${method}  (distro: ${DISTRO_ID:-unknown})"

# --------------------------------------------------------------- vulkan -----

vulkan_hint() {
    [ -n "$(ls /usr/share/vulkan/icd.d/*.json 2>/dev/null)" ] && return 0
    warn "no Vulkan driver detected in /usr/share/vulkan/icd.d/"
    warn "V-Agent is GPU-accelerated and will not start without one. Install:"
    case "$method" in
        xbps)   warn "  mesa-vulkan-radeon | mesa-vulkan-intel | mesa-vulkan-nouveau | nvidia" ;;
        deb)    warn "  mesa-vulkan-drivers  (or your GPU vendor's driver)" ;;
        rpm)    warn "  mesa-vulkan-drivers  (or your GPU vendor's driver)" ;;
        pacman) warn "  vulkan-radeon | vulkan-intel | nvidia-utils" ;;
        *)      warn "  your distribution's Vulkan driver for this GPU" ;;
    esac
}

# --------------------------------------------------------------- install ----

install_xbps() {
    need_root
    # A persistent repo config is the difference between an install that can be
    # updated with `xbps-install -Su` and one frozen at this version forever.
    say "adding the V-Agent xbps repository"
    if [ "$VAGENT_DRY_RUN" = "1" ]; then
        printf '  \033[2m[dry-run]\033[0m write /etc/xbps.d/10-vagent.conf -> repository=%s\n' "$VOID_REPO"
    else
        printf 'repository=%s\n' "$VOID_REPO" | $SUDO tee /etc/xbps.d/10-vagent.conf >/dev/null
    fi
    say "installing"
    # Not -y: xbps must prompt to accept the repository signing key, and that
    # is a decision the user should make rather than one we make for them.
    run $SUDO xbps-install -S v-agent-bin
    say "updates will arrive with your normal 'xbps-install -Su'"
}

install_deb() {
    need_root
    tmp="$(mktemp -d)"
    say "downloading V-Agent-amd64.deb"
    run fetch "${DL}/V-Agent-amd64.deb" "${tmp}/v-agent.deb"
    say "installing"
    run $SUDO apt-get install -y "${tmp}/v-agent.deb"
    rm -rf "$tmp"
}

install_rpm() {
    need_root
    if have dnf; then pm="dnf"
    elif have yum; then pm="yum"
    else die "rpm method needs dnf or yum, found neither"
    fi
    tmp="$(mktemp -d)"
    say "downloading V-Agent-x86_64.rpm"
    run fetch "${DL}/V-Agent-x86_64.rpm" "${tmp}/v-agent.rpm"
    say "installing"
    run $SUDO "$pm" install -y "${tmp}/v-agent.rpm"
    rm -rf "$tmp"
}

install_pacman() {
    need_root
    tmp="$(mktemp -d)"
    say "downloading V-Agent-x86_64.pkg.tar.zst"
    run fetch "${DL}/V-Agent-x86_64.pkg.tar.zst" "${tmp}/v-agent.pkg.tar.zst"
    say "installing"
    run $SUDO pacman -U --noconfirm "${tmp}/v-agent.pkg.tar.zst"
    rm -rf "$tmp"
}

install_tarball() {
    # No root: everything lands under $VAGENT_PREFIX.
    tmp="$(mktemp -d)"
    say "downloading V-Agent-linux-x86_64.tar.gz"
    run fetch "${DL}/V-Agent-linux-x86_64.tar.gz" "${tmp}/v-agent.tar.gz"
    say "unpacking into ${VAGENT_PREFIX}"
    run mkdir -p "${VAGENT_PREFIX}/bin" "${VAGENT_PREFIX}/share/applications" \
                 "${VAGENT_PREFIX}/share/icons/hicolor/512x512/apps"
    if [ "$VAGENT_DRY_RUN" != "1" ]; then
        tar -xzf "${tmp}/v-agent.tar.gz" -C "$tmp"
        install -Dm755 "${tmp}/V-Agent-linux-x86_64/v-agent" "${VAGENT_PREFIX}/bin/v-agent"
        cat > "${VAGENT_PREFIX}/share/applications/io.github.otzpt.VAgent.desktop" <<DESKTOP
[Desktop Entry]
Name=V-Agent
GenericName=Code Editor
Comment=Native, GPU-accelerated code editor with local-first AI
Exec=${VAGENT_PREFIX}/bin/v-agent %U
Icon=io.github.otzpt.VAgent
Type=Application
Categories=Development;IDE;TextEditor;
MimeType=text/plain;inode/directory;
StartupNotify=true
StartupWMClass=io.github.otzpt.VAgent
Terminal=false
DESKTOP
    fi
    rm -rf "$tmp"
    case ":${PATH}:" in
        *":${VAGENT_PREFIX}/bin:"*) ;;
        *) warn "${VAGENT_PREFIX}/bin is not on your PATH; add it to your shell profile" ;;
    esac
}

case "$method" in
    xbps)    install_xbps ;;
    deb)     install_deb ;;
    rpm)     install_rpm ;;
    pacman)  install_pacman ;;
    tarball) install_tarball ;;
    *) die "unknown method '${method}'; use one of xbps deb rpm pacman tarball" ;;
esac

vulkan_hint

say "done"
printf '\n  run it with:  v-agent\n  or open a project:  v-agent .\n\n'
