"""Home-menu background for the Disc icon, shown while the Biblioteca loads.

The home opens on the Disc icon after power-on (the M901 has no drive anyway), and that
is where the player waits while the vigilante opens the Biblioteca (~40 s cold). The home
background of each icon is a plain PNG in /mnt/ubi_boot (`disk` for Disco, no extension,
1920x1080 RGB); this draws one in the Biblioteca's style so the wait looks like ours.
The bottom ~quarter is covered by the player's icon bar.

    python fondo_cargando.py [salida.png]      # posters come from the running service
    BIBLIO_URL=http://IP-del-servidor:8095 python fondo_cargando.py
Install / undo (on the player): copy to /mnt/ubi_boot/disk / delete it. Seen only after
a power cycle.
"""
import io
import os
import random
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SERVICE = os.environ.get("BIBLIO_URL", "http://192.168.1.201:8095")
W, H = 1920, 1080
BG = (7, 7, 10)                      # Wall.BG in the disc
PW, PH, GAP = 200, 300, 16
FONT = "C:/Windows/Fonts/segoeuib.ttf"
FONT_LIGHT = "C:/Windows/Fonts/segoeui.ttf"


def get(path: str) -> bytes:
    with urllib.request.urlopen(SERVICE + path, timeout=20) as r:
        return r.read()


def poster_ids(limit: int) -> list[int]:
    ids = []
    for folder in ("atmos", "movies", "3d"):
        lines = get(f"/d/items?folder={folder}").decode("utf-8").splitlines()[1:]
        ids += [int(l.split("\t", 1)[0]) for l in lines if l]
    random.Random(7).shuffle(ids)
    return ids[:limit]


def main(out: str) -> None:
    img = Image.new("RGB", (W, H), BG)
    cols = W // (PW + GAP) + 2
    rows = 2
    ids = poster_ids(cols * rows)
    x0 = -(PW // 2)
    for i, pid in enumerate(ids):
        r, c = divmod(i, cols)
        try:
            p = Image.open(io.BytesIO(get(f"/d/img/poster?id={pid}&w={PW}&h={PH}"))).convert("RGB")
        except OSError:
            continue
        img.paste(p.resize((PW, PH)), (x0 + c * (PW + GAP), 40 + r * (PH + GAP)))
    # posters fade into the background towards the middle, where the player draws its icons
    img = img.filter(ImageFilter.GaussianBlur(2))
    fade = Image.new("L", (W, H))
    d = ImageDraw.Draw(fade)
    for y in range(H):
        # both poster rows show (lightly dimmed), then fade out above the text
        d.line([(0, y), (W, y)], fill=int(255 * min(1, 0.25 + max(0, y - 380) / 300)))
    img = Image.composite(Image.new("RGB", (W, H), BG), img, fade)
    d = ImageDraw.Draw(img)
    big, small = ImageFont.truetype(FONT, 64), ImageFont.truetype(FONT_LIGHT, 30)
    for text, font, y, fill in (("Cargando biblioteca", big, 600, (255, 255, 255)),
                                ("un momento…", small, 690, (150, 150, 160))):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)
    img.save(out, "PNG")
    print(out, img.size)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "video.png")
