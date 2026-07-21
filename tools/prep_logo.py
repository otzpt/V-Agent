#!/usr/bin/env python3
"""Make the outer background of the V-Agent logo transparent, keeping the
rounded-square icon (and its white letters) intact.

The trick: the white "V" and "V-Agent" text are as bright as the background,
so we do NOT key out white globally. Instead we flood-fill transparency inward
from the image borders through light pixels only. That removes the outer
background + baked checkerboard + soft shadow, but stops at the dark-purple
square, so anything enclosed by it (the letters) is preserved.

Usage:
    python tools/prep_logo.py <source.png> [out.png]

Default out: tools/vagent-logo.png (a tight-cropped, transparent master).
Then run:  python tools/make_icon.py tools/vagent-logo.png
"""
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

LIGHT_MIN = 200  # a pixel counts as "background-light" if every channel > this


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python tools/prep_logo.py <source.png> [out.png]")
    src = Path(sys.argv[1])
    if not src.is_file():
        sys.exit(f"not found: {src}")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "vagent-logo.png"

    img = Image.open(src).convert("RGBA")
    arr = np.asarray(img).astype(np.int16)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3]

    light = np.all(rgb > LIGHT_MIN, axis=2)  # near-white / gray background

    # Flood-fill "background" from every border pixel through light regions.
    bg = np.zeros((h, w), dtype=bool)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if light[y, x] and not bg[y, x]:
                bg[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if light[y, x] and not bg[y, x]:
                bg[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and light[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                dq.append((ny, nx))

    alpha = np.where(bg, 0, 255).astype(np.uint8)
    result = np.dstack([arr[:, :, :3].astype(np.uint8), alpha])
    im = Image.fromarray(result, "RGBA")

    # Feather the cut edge by 1px so it isn't jagged, then tight-crop to the icon.
    a = im.split()[3].filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(a)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(f"wrote {out}  size={im.size}  (transparent background)")
    print("next:  python tools/make_icon.py", out)


if __name__ == "__main__":
    main()
