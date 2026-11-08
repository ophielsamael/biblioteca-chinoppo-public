"""Draws the Blu-ray (blue) and 4K UHD (black) case templates into static/cases.

Each is a case seen slightly from the side (the right edge a little shorter than the left, as in
a photo), with a spine on the left, a header band, a glossy plastic sheen, and a transparent cover
window. The service puts each cover into that window (biblio/images.py finds it by flooding the
transparent area from the centre and follows its perspective). Replace them with your own case
photos if you like: any PNG whose cover window is transparent works.

    python tools/cases/make_cases.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[2] / "static" / "cases"
S = 2                                   # drawn at 2x, then scaled down: smooth edges
W, H = 760 * S, 960 * S
SPINE = 62 * S                          # left strip: the case's hinge
BAND = 58 * S                           # header band above the window
M = 10 * S                              # plastic margin around the window
SKEW = 0.075                            # right edge this much shorter (top and bottom): seen from the side


def _font(size, bold=True):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _vgrad(w, h, top, bottom):
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize((w, h))


def _hgrad(w, h, left, right):
    return _vgrad(h, w, left, right).rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)


def case(body_top, body_bottom, edge, band_rgb, logo):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=22 * S, fill=255)
    body = _vgrad(W, H, body_top, body_bottom)
    img.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # spine: darker, with the hinge ridges
    spine = _hgrad(SPINE, H, tuple(max(0, c - 30) for c in body_bottom[:3]) + (255,), tuple(min(255, c + 25) for c in body_top[:3]) + (255,))
    smask = Image.new("L", (SPINE, H), 0)
    ImageDraw.Draw(smask).rounded_rectangle((0, 0, SPINE + 40 * S, H - 1), radius=22 * S, fill=255)
    img.paste(spine, (0, 0), smask)
    for x in (SPINE - 10 * S, SPINE - 4 * S):
        d.line((x, 26 * S, x, H - 26 * S), fill=edge, width=2 * S)

    # header band with the format logo
    x0, x1 = SPINE + M, W - M
    d.rounded_rectangle((x0, M, x1, M + BAND), radius=6 * S, fill=band_rgb)
    logo(d, x0, M, x1 - x0, BAND)

    # cover window (transparent) with a thin dark sleeve edge
    wy0 = M + BAND + 8 * S
    d.rectangle((x0 - 3 * S, wy0 - 3 * S, x1 + 3 * S, H - M + 3 * S), fill=(8, 8, 10, 255))
    d.rectangle((x0, wy0, x1, H - M), fill=(0, 0, 0, 0))

    # outer edge highlight
    d.rounded_rectangle((1, 1, W - 2, H - 2), radius=22 * S, outline=edge, width=2 * S)

    # glossy sheen across the whole front (faint over the window: the cover shows through)
    sheen = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sheen).polygon([(W * 0.18, 0), (W * 0.46, 0), (W * 0.20, H), (-W * 0.08, H)], fill=95)
    sheen = sheen.filter(ImageFilter.GaussianBlur(40 * S))
    shine = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    shine.putalpha(Image.composite(sheen, Image.new("L", (W, H), 0), mask))
    a = img.getchannel("A")
    img = Image.alpha_composite(img, shine)
    # keep the window clearly transparent (the service floods alpha < 128 to find it)
    win = Image.new("L", (W, H), 0)
    ImageDraw.Draw(win).rectangle((x0, wy0, x1, H - M), fill=255)
    img.putalpha(Image.composite(Image.eval(img.getchannel("A"), lambda v: min(v, 40)), a, win))

    # seen slightly from the side: the right edge shorter, top and bottom
    k = SKEW * H
    quad = (0, 0, 0, H, W, H - k, W, k)                 # source corners for the output's TL, BL, BR, TR
    persp = img.transform((W, H), Image.QUAD, quad, Image.BICUBIC)
    return persp.resize((W // S, H // S), Image.LANCZOS)


def logo_uhd(d, x, y, w, h):
    f4k, fuhd = _font(int(h * 0.62)), _font(int(h * 0.50), bold=False)
    tx = x + w // 2 - int(h * 2.3)
    bw = d.textlength("4K", font=f4k) + h * 0.35
    d.rounded_rectangle((tx, y + h * 0.16, tx + bw, y + h * 0.84), radius=int(h * 0.1), fill=(255, 255, 255, 255))
    d.text((tx + h * 0.17, y + h * 0.50), "4K", font=f4k, fill=(15, 15, 18, 255), anchor="lm")
    d.text((tx + bw + h * 0.2, y + h * 0.52), "ULTRA HD", font=fuhd, fill=(235, 235, 240, 255), anchor="lm")


def logo_bluray(d, x, y, w, h):
    f = _font(int(h * 0.56))
    d.text((x + w // 2, y + h * 0.52), "Blu-ray Disc", font=f, fill=(255, 255, 255, 255), anchor="mm")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    case((44, 112, 210, 255), (16, 62, 150, 255), (120, 170, 235, 255), (10, 46, 120, 255), logo_bluray) \
        .save(OUT / "bluray.png", optimize=True)
    case((40, 40, 46, 255), (10, 10, 12, 255), (90, 90, 98, 255), (0, 0, 0, 255), logo_uhd) \
        .save(OUT / "uhd.png", optimize=True)
    print("ok", OUT)
