#!/usr/bin/env bash
# Builds the Python sidecar into a single binary that Tauri can bundle.
# Tauri expects external binaries named:  <name>-<target-triple>
# e.g. vagent-sidecar-x86_64-unknown-linux-gnu
#
# Run this from the project root:  bash sidecar/build.sh

set -e

cd "$(dirname "$0")"

echo "→ Installing sidecar deps..."
pip install -r requirements.txt pyinstaller

echo "→ Detecting target triple..."
TRIPLE="$(rustc -Vv | grep host | cut -d' ' -f2)"
echo "   target = $TRIPLE"

echo "→ Building with PyInstaller..."
pyinstaller --onefile --name vagent-sidecar vagent_sidecar.py \
  --hidden-import=llm_provider \
  --distpath ./build_out \
  --workpath ./build_tmp \
  --specpath ./build_tmp

echo "→ Placing binary in src-tauri/binaries/..."
mkdir -p ../src-tauri/binaries
# PyInstaller appends .exe on Windows; Tauri also expects the suffix on the
# bundled external binary name. Detect it from the target triple.
EXT=""
case "$TRIPLE" in *windows*) EXT=".exe";; esac
cp "./build_out/vagent-sidecar${EXT}" "../src-tauri/binaries/vagent-sidecar-${TRIPLE}${EXT}"

echo "✓ Done: src-tauri/binaries/vagent-sidecar-${TRIPLE}${EXT}"
