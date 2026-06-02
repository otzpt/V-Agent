#!/usr/bin/env bash
# V-Agent Linux Installer
# Usage: bash install.sh [--venv] [--system]
set -euo pipefail

VERSION="0.7.1"
REPO="https://github.com/otzpt/V-Agent"
INSTALL_DIR="$HOME/.local/share/vagent"
BIN_DIR="$HOME/.local/bin"
VENV=false

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --venv)   VENV=true ;;
        --system) BIN_DIR="/usr/local/bin"; INSTALL_DIR="/opt/vagent" ;;
    esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  V-Agent $VERSION — Linux Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.10+ required. Install it first:"
    echo "   Ubuntu: sudo apt install python3"
    echo "   Arch:   sudo pacman -S python"
    exit 1
fi

PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MIN=$($PYTHON -c "import sys; print(1 if sys.version_info >= (3,10) else 0)")
if [ "$PY_MIN" != "1" ]; then
    echo "❌ Python 3.10+ required (found $PY_VER)"
    exit 1
fi
echo "✅ Python $PY_VER"

# ── System dependencies ────────────────────────────────────────────────────────
if command -v apt &>/dev/null; then
    echo "→ Installing system dependencies (apt)..."
    sudo apt-get install -y python3-pip python3-venv libxcb-cursor0 libgl1 libglib2.0-0 2>/dev/null || true
elif command -v pacman &>/dev/null; then
    echo "→ Installing system dependencies (pacman)..."
    sudo pacman -S --noconfirm python-pip 2>/dev/null || true
elif command -v dnf &>/dev/null; then
    echo "→ Installing system dependencies (dnf)..."
    sudo dnf install -y python3-pip python3-gobject 2>/dev/null || true
fi

# ── Install dir ───────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "→ Copying files to $INSTALL_DIR..."
cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR/"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ "$VENV" = true ]; then
    echo "→ Creating virtual environment..."
    $PYTHON -m venv "$INSTALL_DIR/venv"
    PIP="$INSTALL_DIR/venv/bin/pip"
    PYTHON_RUN="$INSTALL_DIR/venv/bin/python3"
else
    PIP="$($PYTHON -m pip --version &>/dev/null && echo "$PYTHON -m pip" || echo "pip3")"
    PYTHON_RUN="$PYTHON"
fi

# ── Python dependencies ───────────────────────────────────────────────────────
echo "→ Installing Python dependencies..."
$PIP install --quiet --upgrade pip
$PIP install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── Launcher script ───────────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/vagent" << LAUNCHER
#!/usr/bin/env bash
# V-Agent launcher
export QT_QPA_PLATFORM=\${QT_QPA_PLATFORM:-xcb}
exec "$PYTHON_RUN" "$INSTALL_DIR/vagent.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/vagent"

# ── Desktop entry ─────────────────────────────────────────────────────────────
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/vagent.desktop" << DESKTOP
[Desktop Entry]
Name=V-Agent
Comment=Professional Agentic IDE
Exec=$BIN_DIR/vagent
Icon=$INSTALL_DIR/assets/icon.png
Type=Application
Categories=Development;IDE;
Terminal=false
StartupWMClass=V-Agent
DESKTOP

echo ""
echo "✅ V-Agent $VERSION installed successfully!"
echo ""
echo "Launch: vagent"
echo "       (make sure $BIN_DIR is in your PATH)"
echo ""
echo "Wayland fix (if needed): QT_QPA_PLATFORM=wayland vagent"
