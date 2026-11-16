"""Builds the two loading videos the player shows while it works, from drawings made here
(no film art, no studio assets):

  static/usb/cargando_pelicula.mp4    spinning disc + "Cargando película"   (120 s, loops)
  static/usb/cargando_biblioteca.mp4  poster cards + "Cargando biblioteca"  (60 s, loops)

They go on the USB stick (biblio/usbpack.py) and the service plays them with the player's own
video decoder: the home menu stays out of sight while a movie mounts (about 40 s) or the
Biblioteca disc opens (>40 s after a cold boot). Their lengths are in biblio/player.py
(LOADER_SECONDS): the service tells "the loader is still playing" from "the movie started" by it.

Needs Pillow and ffmpeg:   python tools/loaders/make_loaders.py [--font file.ttf] [--lang en]
With your own library's posters instead of the drawn ones (the repo keeps the drawn ones: no film art):
    python tools/loaders/make_loaders.py --posters http://IP-OF-THE-SERVICE:8095 --out some/folder
    python tools/loaders/make_loaders.py --poster-files a.jpg b.webp c.png d.jpg e.jpg --out some/folder
"""
import argparse
import io
import math
import os
import random
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
W, H, FPS, BASE = 1920, 1080, 24, 8   # a seamless 8 s base, looped by ffmpeg
TEXT = {"es": ("Cargando película", "Cargando biblioteca"), "en": ("Loading movie", "Loading library")}
FONTS = ("segoeuib.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf")


def font(path, size):
    for name in ([path] if path else []) + list(FONTS):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit("no font found: pass --font file.ttf")


def disc_frames(n=15):
    """A tilted disc seen from the side, a red wedge going round it: n frames for one turn."""
    S, R = 4, 200   # supersampling, radius
    frames = []
    for i in range(n):
        im = Image.new("RGBA", (2 * R * S, 2 * R * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = R * S
        d.ellipse([c - R * S, c - R * S, c + R * S, c + R * S], fill=(250, 250, 250), outline=(240, 220, 90), width=S * 3)
        d.ellipse([c - 62 * S, c - 62 * S, c + 62 * S, c + 62 * S], fill=(190, 190, 195))     # hub ring
        d.ellipse([c - 44 * S, c - 44 * S, c + 44 * S, c + 44 * S], fill=(0, 0, 0))          # hole
        a = 2 * math.pi * i / n
        pts = [(c, c)] + [(c + (R - 6) * S * math.sin(a + k * 0.04), c - (R - 6) * S * math.cos(a + k * 0.04)) for k in range(-3, 4)]
        d.polygon(pts, fill=(232, 28, 36))                                                    # the wedge
        d.ellipse([c - 62 * S, c - 62 * S, c + 62 * S, c + 62 * S], fill=(190, 190, 195))
        d.ellipse([c - 44 * S, c - 44 * S, c + 44 * S, c + 44 * S], fill=(0, 0, 0))
        im = im.resize((2 * R, 2 * R), Image.LANCZOS)
        im = im.resize((2 * R, int(2 * R * 0.42)), Image.LANCZOS).rotate(35, expand=True, resample=Image.BICUBIC)
        frames.append(im.resize((int(im.width * 0.7), int(im.height * 0.7)), Image.LANCZOS))   # not too big on a projector
    return frames


def poster(seed, w=150, h=225):
    """An invented film poster: sky gradient, a sun or moon, hills, a title bar."""
    r = random.Random(seed)
    top = tuple(r.randint(20, 120) for _ in range(3))
    bot = tuple(min(255, c + r.randint(60, 130)) for c in top)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    cx, cy, rr = r.randint(40, w - 40), r.randint(50, 100), r.randint(16, 28)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(250, 240, 210))
    base = tuple(max(0, c - 70) for c in top)
    for layer in range(2):
        pts = [(0, h)] + [(x, h - 55 - layer * 18 - r.randint(0, 28)) for x in range(0, w + 1, 25)] + [(w, h)]
        d.polygon(pts, fill=tuple(max(0, c - layer * 25) for c in base))
    d.rectangle([14, h - 34, w - 14, h - 26], fill=(235, 235, 240))
    d.rectangle([34, h - 20, w - 34, h - 16], fill=(170, 170, 180))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], 12, fill=255)
    out = Image.new("RGBA", (w, h))
    out.paste(im, (0, 0))
    out.putalpha(mask)
    return out


def _card(im, w: int = 150, h: int = 225):
    """A poster image as a rounded card of the loader's size."""
    im = im.convert("RGB").resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], 12, fill=255)
    card = im.convert("RGBA")
    card.putalpha(mask)
    return card


def file_posters(paths: list[str], w: int = 150, h: int = 225) -> list:
    """The poster images you give, in that order (left to right)."""
    return [_card(Image.open(p), w, h) for p in paths]


def library_posters(base: str, n: int = 5, w: int = 150, h: int = 225, seed: int | None = None) -> list:
    """n posters of titles in the Biblioteca at base (its disc API), rounded like the drawn ones.
    Only titles TMDb knows (a rating): the others have no real poster to show."""
    get = lambda path: urllib.request.urlopen(base.rstrip("/") + path, timeout=30).read()
    rows = lambda raw: [l.split("\t") for l in raw.decode("utf-8").splitlines() if l]
    ids = []
    for folder in rows(get("/d/folders")):
        ids += [r[0] for r in rows(get(f"/d/items?folder={folder[0]}"))[1:] if len(r) > 3 and r[3] != "series"]
    r = random.Random(seed)
    r.shuffle(ids)
    out = []
    for i in ids:
        info = {l[0]: (l[1] if len(l) > 1 else "") for l in rows(get(f"/d/item?id={i}"))}
        if info.get("rating") in (None, "", "None", "0", "0.0"):
            continue
        out.append(_card(Image.open(io.BytesIO(get(f"/d/img/poster?id={i}&w={w}&h={h}"))), w, h))
        if len(out) == n:
            return out
    raise SystemExit(f"only {len(out)} posters found at {base}")


def label(im, fnt, text, t, y):
    dots = "." * int(t * 2 % 4)   # 0..3 dots, one step per 0.5 s: 2 s a cycle, which divides BASE
    d = ImageDraw.Draw(im)
    d.text(((W - d.textlength(text, font=fnt)) / 2, y), text + dots, font=fnt, fill=(225, 225, 230))


def encode(frame, seconds, loops, out):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(BASE),
           "-vf", "format=yuv420p", "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-crf", "18",
           "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", out + ".base.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(FPS * BASE):
        p.stdin.write(frame(n / FPS).tobytes())
    p.stdin.close()
    p.wait()
    # a plain video with a silent audio track: the player is picky about 15 fps / no audio
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", str(loops), "-i", out + ".base.mp4",
                    "-t", str(seconds), "-c", "copy", "-movflags", "+faststart", out], check=True)
    os.remove(out + ".base.mp4")


def main():
    global FFMPEG
    ap = argparse.ArgumentParser()
    ap.add_argument("--font")
    ap.add_argument("--lang", default="es", choices=sorted(TEXT))
    ap.add_argument("--out", default=str(ROOT / "static" / "usb"))
    ap.add_argument("--posters", help="the Biblioteca's address (http://IP:8095): use its posters")
    ap.add_argument("--seed", type=int, help="which posters (same seed, same five)")
    ap.add_argument("--poster-files", nargs=5, metavar="IMG", help="five poster images, left to right")
    a = ap.parse_args()
    FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
    fnt = font(a.font, 44)
    t_movie, t_library = TEXT[a.lang]
    discs = disc_frames()
    dw, dh = discs[0].size
    if a.poster_files:
        posters = file_posters(a.poster_files)
    elif a.posters:
        posters = library_posters(a.posters, seed=a.seed)
    else:
        posters = [poster(s) for s in (11, 27, 42, 63, 85)]

    def movie(t):
        im = Image.new("RGB", (W, H), (0, 0, 0))
        sh = Image.new("RGBA", (260, 40), (0, 0, 0, 0))   # the light patch under the disc
        ImageDraw.Draw(sh).ellipse([0, 0, 259, 39], fill=(240, 235, 190, 90))
        im.paste(sh, ((W - 260) // 2, 520), sh)
        d = discs[int(t * 15) % 15]
        im.paste(d, ((W - dw) // 2, 540 - dh), d)
        label(im, fnt, t_movie, t, 620)
        return im

    def library(t):
        im = Image.new("RGB", (W, H), (0, 0, 0))
        pw, ph, gap = 150, 225, 36
        x0 = (W - (5 * pw + 4 * gap)) // 2
        for i, p in enumerate(posters):   # a wave: each poster rises and brightens in turn
            k = 0.5 + 0.5 * math.sin(2 * math.pi * (t / 2 - i / 5))
            card = Image.alpha_composite(p, Image.new("RGBA", p.size, (0, 0, 0, int(150 * (1 - k)))))
            im.paste(card, (x0 + i * (pw + gap), 330 - int(22 * k)), card)
        label(im, fnt, t_library, t, 660)
        return im

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    encode(movie, 120, 14, str(out / "cargando_pelicula.mp4"))
    encode(library, 60, 7, str(out / "cargando_biblioteca.mp4"))
    print("ok:", *(f"{p.name} {p.stat().st_size // 1024} KB" for p in sorted(out.glob("cargando_*.mp4"))))


if __name__ == "__main__":
    main()
