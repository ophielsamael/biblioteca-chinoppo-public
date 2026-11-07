"""Draws plain Blu-ray (blue) and 4K UHD (black) case templates into static/cases.

The service puts each cover into the transparent window of these PNGs (see biblio/images.py:
the window is found by flooding the transparent area from the centre; the spine is the strip
to its left). Replace them with your own case photos if you like: same idea, a PNG whose
cover window is transparent.

    python tools/cases/make_cases.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "static" / "cases"
W, H = 900, 1100
SPINE = 90


def case(body, band, label):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=body)
    d.rectangle((SPINE + 18, 70, W - 22, H - 22), fill=(0, 0, 0, 0))   # cover window
    d.rectangle((SPINE + 18, 18, W - 22, 62), fill=band)                # top band
    d.text((SPINE + 34, 26), label, fill=(255, 255, 255, 255), font_size=30)
    d.line((SPINE, 20, SPINE, H - 20), fill=tuple(min(255, c + 40) for c in body[:3]) + (255,), width=3)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    case((22, 78, 168, 255), (12, 52, 128, 255), "Blu-ray").save(OUT / "bluray.png", optimize=True)
    case((18, 18, 20, 255), (30, 30, 34, 255), "4K ULTRA HD").save(OUT / "uhd.png", optimize=True)
    print("ok", OUT)
