#!/usr/bin/env python3
"""Convert a square PNG into the V-Agent Windows app icon (multi-size .ico)
and the runtime window PNGs. Requires Pillow:  pip install pillow

Usage:
    python tools/make_icon.py path/to/vagent-logo.png

Drops the results into crates/zed/resources/windows/app-icon.ico (and the
dev/preview/nightly variants), which windows_resources embeds into the binary.
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required. Run: pip install pillow")

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python tools/make_icon.py <square-png>")
    src = Path(sys.argv[1])
    if not src.is_file():
        sys.exit(f"not found: {src}")

    img = Image.open(src).convert("RGBA")
    if img.width != img.height:
        # pad to square with transparency (never crop — would clip the logo)
        m = max(img.size)
        square = Image.new("RGBA", (m, m), (0, 0, 0, 0))
        square.paste(img, ((m - img.width) // 2, (m - img.height) // 2))
        img = square

    out_dir = Path(__file__).resolve().parent.parent / "crates" / "zed" / "resources" / "windows"
    out_dir.mkdir(parents=True, exist_ok=True)

    # All release channels share the same V-Agent icon for now.
    for name in ("app-icon.ico", "app-icon-preview.ico", "app-icon-nightly.ico", "app-icon-dev.ico"):
        img.save(out_dir / name, sizes=[(s, s) for s in ICO_SIZES])
        print("wrote", out_dir / name)

    print("\nDone. Rebuild to embed:  cargo build -p zed")

if __name__ == "__main__":
    main()
