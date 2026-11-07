import functools
import io
import re
import textwrap
from collections.abc import Callable
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from biblio.db import Item

TMDB_IMG = "https://image.tmdb.org/t/p/"
BG = (7, 7, 10)


def http_fetch(url: str) -> bytes:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.content


def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _cached(path: Path, make: Callable[[], bytes | None], fallback: Callable[[], bytes]) -> bytes:
    """make() returns None when the download failed: serve the fallback without caching it,
    so the real image appears once TMDb is reachable again."""
    if path.exists():
        return path.read_bytes()
    data = make()
    if data is None:
        return fallback()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _remote(fetch, size: str, tmdb_path: str | None) -> Image.Image | None:
    if not tmdb_path:
        return None
    try:
        return Image.open(io.BytesIO(fetch(TMDB_IMG + size + tmdb_path)))
    except Exception:
        return None


def _placeholder(title: str, w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), (29, 29, 36))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=max(12, w // 10))
    lines = textwrap.wrap(title, width=max(8, w // max(1, font.size // 2 + 1)))[:6]
    y = h // 2 - len(lines) * font.size // 2
    for ln in lines:
        tw = draw.textlength(ln, font=font)
        draw.text(((w - tw) / 2, y), ln, fill="white", font=font)
        y += font.size + 2
    return img


ART_KINDS = ("poster", "backdrop", "logo", "case", "disc")   # case, disc: detail page only
SEASON_KIND = re.compile(r"^season\d{1,3}$")                  # season1, season2...: a series' season posters


def art_kind_ok(kind: str) -> bool:
    return kind in ART_KINDS or bool(SEASON_KIND.match(kind))


def _art_file(cache: Path, media: str, tmdb_id: int, kind: str) -> Path:
    """Images made in Artwork Studio live next to the cache, by TMDb id: they survive a
    rescan and apply to every copy of the title. media is "movie" or "tv" (TMDb ids of
    movies and series overlap)."""
    return cache.parent / "art" / f"{media}_{tmdb_id}_{kind}"


def drop_own(cache: Path, media: str, tmdb_id: int, kind: str) -> None:
    _art_file(cache, media, tmdb_id, kind).unlink(missing_ok=True)


def save_own(cache: Path, media: str, tmdb_id: int, kind: str, data: bytes) -> None:
    Image.open(io.BytesIO(data)).verify()   # raises on anything that is not an image
    path = _art_file(cache, media, tmdb_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def own_file(item: Item, cache: Path, kind: str) -> Path:
    """Where Artwork Studio's image for this title lives: by TMDb id (shared by every copy of
    the title), or by catalog id for a title TMDb doesn't know (a home video, a rare concert)."""
    if item.tmdb_id:
        return _art_file(cache, "tv" if item.kind == "series" else "movie", item.tmdb_id, kind)
    return _art_file(cache, "item", item.id, kind)


def _own(item: Item, cache: Path, kind: str) -> Image.Image | None:
    path = own_file(item, cache, kind)
    return Image.open(path) if path.exists() else None


def own_bytes(item: Item, cache: Path, kind: str) -> bytes | None:
    """The image file Artwork Studio stored for this title, as it was sent."""
    path = own_file(item, cache, kind)
    return path.read_bytes() if path.exists() else None


def _boxed(img: Image.Image) -> bool:
    """A poster put in a case in Artwork Studio: transparent around the case."""
    return img.mode in ("RGBA", "LA", "P") and img.convert("RGBA").getpixel((0, 0))[3] < 128


def _contain(img: Image.Image, w: int, h: int) -> Image.Image:
    """Whole image inside w x h, transparent around it (a case must not be cropped)."""
    img = img.convert("RGBA")
    img.thumbnail((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(img, ((w - img.width) // 2, (h - img.height) // 2))
    return out


def poster_jpeg(item: Item, cache: Path, w: int, h: int, fetch=http_fetch) -> bytes:
    def make():
        img = _own(item, cache, "poster") or _remote(fetch, "w500", item.meta.get("poster_path"))
        if img is not None and _boxed(img):   # case on the wall's dark background, uncropped
            flat = Image.new("RGBA", (w, h), BG + (255,))
            flat.alpha_composite(_contain(img, w, h))
            return _jpeg(flat)
        return None if img is None else _jpeg(ImageOps.fit(img, (w, h)))
    return _cached(cache / f"poster_{item.id}_{w}x{h}.jpg", make,
                   lambda: _jpeg(_placeholder(item.title, w, h)))


def _darkened(base: Image.Image) -> bytes:
    # darken left (0.92) -> right (0.35) so text stays readable
    mask = Image.linear_gradient("L").rotate(90).resize((1280, 720))
    alpha = mask.point(lambda v: int(255 * (0.35 + 0.57 * (255 - v) / 255)))  # v=0 at the left edge
    return _jpeg(Image.composite(Image.new("RGB", (1280, 720), BG), base, alpha))


def backdrop_jpeg(item: Item, cache: Path, fetch=http_fetch) -> bytes:
    def make():
        img = _own(item, cache, "backdrop") or _remote(fetch, "w1280", item.meta.get("backdrop_path"))
        return None if img is None else _darkened(ImageOps.fit(img, (1280, 720)).convert("RGB"))
    return _cached(cache / f"backdrop_{item.id}.jpg", make,
                   lambda: _darkened(Image.new("RGB", (1280, 720), BG)))


def season_jpeg(item: Item, season: int, cache: Path, w: int, h: int, fetch=http_fetch) -> bytes:
    """A season's poster: the one sent from Artwork Studio, else TMDb's, else the series poster."""
    path = (item.meta.get("season_posters") or {}).get(str(season)) or item.meta.get("poster_path")

    def make():
        img = _own(item, cache, f"season{season}") or _remote(fetch, "w342", path)
        return None if img is None else _jpeg(ImageOps.fit(img, (w, h)))
    return _cached(cache / f"season_{item.id}_{season}_{w}x{h}.jpg", make,
                   lambda: _jpeg(_placeholder(f"Temporada {season}", w, h)))


def still_jpeg(show_id: int, season: int, episode: int, still_path: str | None, cache: Path,
               w: int, h: int, fetch=http_fetch) -> bytes:
    def make():
        img = _remote(fetch, "w300", still_path)
        return None if img is None else _jpeg(ImageOps.fit(img, (w, h)))
    return _cached(cache / f"still_{show_id}_{season}_{episode}_{w}x{h}.jpg", make,
                   lambda: _jpeg(_placeholder(f"E{episode}", w, h)))


def case_png(item: Item, cache: Path, w: int, h: int, fetch=http_fetch) -> bytes:
    """Detail-page poster as PNG: the case chosen in Artwork Studio (black 4K / blue HD, with
    its transparency) when the title has one, else the plain poster. The wall never shows
    cases (rows of boxes looked bad, 2026-11-04): it keeps the poster with its banner."""
    path = cache / f"case_{item.id}_{w}x{h}_v2.png"
    if path.exists():
        return path.read_bytes()
    own = _own(item, cache, "case")
    if own is not None:
        img = _contain(own, w, h)   # exactly the case chosen in Artwork, its printed logo included
    else:
        # posters are 2:3 and the slot isn't: filling it cropped the top of Artwork's
        # "4K ULTRA HD" banner (2026-11-04). Whole poster, transparent margin instead.
        pw, ph = (w, w * 3 // 2) if w * 3 // 2 <= h else (h * 2 // 3, h)
        img = _contain(Image.open(io.BytesIO(poster_jpeg(item, cache, pw, ph, fetch))), w, h)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def _accent(cover: Image.Image) -> tuple[int, int, int]:
    """Brightest saturated colour of the cover, for the spine title (like real spines)."""
    best, score = (230, 230, 235), 0.0
    for r, g, b in cover.resize((24, 36)).getdata():
        hi, lo = max(r, g, b), min(r, g, b)
        sc = (hi - lo) / 255 * hi / 255
        if sc > score:
            best, score = (r, g, b), sc
    return best if score > 0.25 else (230, 230, 235)


CASES = Path(__file__).resolve().parent.parent / "static" / "cases"


@functools.lru_cache(maxsize=4)
def _template(name: str) -> tuple[Image.Image, list[tuple[int, int]]]:
    """Case PNG (transparent where the cover goes) and that window's corners TL, TR, BR, BL,
    found by flooding the transparent area from the centre."""
    tpl = Image.open(CASES / f"{name}.png").convert("RGBA")
    a, (W, H) = tpl.getchannel("A").load(), tpl.size
    seen, todo = {(W // 2, H // 2)}, [(W // 2, H // 2)]
    while todo:
        x, y = todo.pop()
        for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= p[0] < W and 0 <= p[1] < H and p not in seen and a[p] < 128:
                seen.add(p)
                todo.append(p)
    quad = [min(seen, key=lambda p: p[0] + p[1]), max(seen, key=lambda p: p[0] - p[1]),
            max(seen, key=lambda p: p[0] + p[1]), min(seen, key=lambda p: p[0] - p[1])]
    return tpl, quad


def case_image(cover: Image.Image, title: str = "", uhd: bool = False) -> Image.Image:
    """The cover in a real Blu-ray (blue) or 4K UHD (black) case photo from static/cases,
    following its slight perspective, the title down the spine, a soft drop shadow.
    Transparent around it. Artwork Studio asks for this through POST /tools/case."""
    tpl, quad = _template("uhd" if uhd else "bluray")
    W, H = tpl.size
    src = [(0, 0), (cover.width, 0), (cover.width, cover.height), (0, cover.height)]
    art = cover.convert("RGBA").transform((W, H), Image.PERSPECTIVE, _perspective(quad, src), Image.BICUBIC)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), _quad_mask((W, H), quad)))
    box = Image.alpha_composite(art, tpl)
    if title:
        _spine_title(box, quad, title, _accent(cover), uhd)
    pad = int(W * 0.04)                     # room for the shadow
    out = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    shadow = box.getchannel("A").point(lambda v: v * 3 // 4).filter(ImageFilter.GaussianBlur(pad // 2))
    out.paste((0, 0, 0, 255), (pad + pad // 3, pad + pad // 2), shadow)
    out.alpha_composite(box, (pad, pad))
    return out


def _quad_mask(size, quad) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(quad, fill=255)
    return m


def _spine_title(box: Image.Image, quad, title: str, colour, uhd: bool) -> None:
    """Title written down the spine (the strip left of the window), in the cover's accent
    colour. The 4K case prints logos at both ends of its spine: keep to the middle."""
    x0, x1 = int(quad[0][0] * 0.42), int(quad[0][0] * 0.95)
    top, bottom = (0.30, 0.78) if uhd else (0.20, 0.85)
    y0, y1 = int(box.height * top), int(box.height * bottom)
    size = int((x1 - x0) * 0.62)
    text = title.upper()
    font = ImageFont.load_default(size=size)
    d = ImageDraw.Draw(box)
    while d.textlength(text, font=font) > (y1 - y0) and size > 10:
        size -= 2
        font = ImageFont.load_default(size=size)
    tw = int(d.textlength(text, font=font))
    label = Image.new("RGBA", (tw + 8, size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(label).text((4, 0), text, font=font, fill=colour + (255,),
                               stroke_width=max(1, size // 14), stroke_fill=colour + (255,))
    label = label.rotate(-90, expand=True)
    box.alpha_composite(label, ((x0 + x1 - label.width) // 2, y0 + (y1 - y0 - label.height) // 2))


def _perspective(dst, src) -> list[float]:
    """PIL PERSPECTIVE coefficients mapping output points dst to input points src
    (Gauss-Jordan on the 8x8 system; numpy isn't installed for one small solve)."""
    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    for c in range(8):
        p = max(range(c, 8), key=lambda i: abs(rows[i][c]))
        rows[c], rows[p] = rows[p], rows[c]
        for i in range(8):
            if i != c:
                f = rows[i][c] / rows[c][c]
                rows[i] = [a - f * b for a, b in zip(rows[i], rows[c])]
    return [rows[i][8] / rows[i][i] for i in range(8)]


DISC_COLS = 8


def disc_png(item: Item, cache: Path, size: int, frames: int, fetch=http_fetch) -> bytes | None:
    """The film's disc, pre-rotated: `frames` turns in a sprite sheet of DISC_COLS columns
    (the disc's Java can't rotate images; it shows one cell after another). Each cell is
    only the right half, size/2 x size: the left half never leaves the case, and halving
    the sheet lets it hold twice the turns (15° steps looked jerky, 2026-11-04).
    The disc art picked in Artwork Studio (fanart.tv) when there is one, else one made from
    the poster. Only for titles with a case (the disc slides out of it). None otherwise."""
    if _own(item, cache, "case") is None:
        return None
    path = cache / f"disc_{item.id}_{size}_{frames}.png"
    if path.exists():
        return path.read_bytes()
    own = _own(item, cache, "disc")
    if own is None:
        # label: the middle of the poster (a square from its centre leaves out a top banner)
        poster = Image.open(io.BytesIO(poster_jpeg(item, cache, 500, 750, fetch))).convert("RGB")
        label = poster.crop((0, 125, 500, 625)).resize((size * 2, size * 2), Image.LANCZOS)
    else:
        own = ImageOps.fit(own.convert("RGBA"), (size * 2, size * 2), Image.LANCZOS)
    cols = min(DISC_COLS, frames)
    rows = -(-frames // cols)
    half = size // 2
    sheet = Image.new("RGBA", (half * cols, size * rows), (0, 0, 0, 0))
    shape, shine = _disc_shape(size * 2)
    for i in range(frames):
        if own is not None:                                       # a real disc print: as it is
            disc = own.rotate(-360 * i / frames, Image.BICUBIC)
        else:
            turned = label.rotate(-360 * i / frames, Image.BICUBIC)   # clockwise
            disc = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
            disc.paste(turned, (0, 0), shape)
            disc.alpha_composite(shine)                           # light stays put: it's the room's
        r, c = divmod(i, cols)
        cell = disc.resize((size, size), Image.LANCZOS).crop((size - half, 0, size, size))
        sheet.alpha_composite(cell, (c * half, r * size))
    buf = io.BytesIO()
    sheet.save(buf, "PNG")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


@functools.lru_cache(maxsize=4)
def _disc_shape(n: int) -> tuple[Image.Image, Image.Image]:
    """Mask of a printed disc (outer edge, clear hub ring, centre hole) and its fixed sheen."""
    c = n / 2
    def circle(d, r, **kw):
        d.ellipse([c - r, c - r, c + r, c + r], **kw)
    mask = Image.new("L", (n, n), 0)
    md = ImageDraw.Draw(mask)
    circle(md, c - 1, fill=255)
    circle(md, c * 0.30, fill=110)                                # clear plastic hub
    circle(md, c * 0.12, fill=0)                                  # the hole
    shine = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shine)
    circle(sd, c - 1, outline=(200, 200, 210, 160), width=max(1, n // 120))   # silver rim
    circle(sd, c * 0.30, outline=(220, 220, 230, 140), width=max(1, n // 160))
    glint = Image.new("L", (n, n), 0)                             # diagonal reflection band
    gd = ImageDraw.Draw(glint)
    for i in range(-n, n, max(1, n // 200)):
        a = max(0, 70 - abs(i) * 140 // n)
        gd.line([(i, 0), (i + n, n)], fill=a)
    glint = ImageChops.multiply(glint, mask.point(lambda v: 255 if v == 255 else 0))
    shine.paste((255, 255, 255, 255), (0, 0), glint)
    return mask, shine


def logo_png(item: Item, cache: Path, w: int, h: int, find, fetch=http_fetch) -> bytes | None:
    """Transparent title logo scaled into w x h, or None (no logo: the disc shows the title).
    find(kind, tmdb_id) -> TMDb file path or None. "No logo" is remembered; a failed
    lookup or download is not, so it is retried later."""
    path, none = cache / f"logo_{item.id}_{w}x{h}.png", cache / f"logo_{item.id}.none"
    if path.exists():
        return path.read_bytes()
    img = _own(item, cache, "logo")
    if img is None:
        if none.exists() or not item.tmdb_id or find is None:
            return None
        try:
            tmdb_path = find("tv" if item.kind == "series" else "movie", item.tmdb_id)
        except Exception:
            return None
        if not tmdb_path:
            cache.mkdir(parents=True, exist_ok=True)
            none.touch()
            return None
        img = _remote(fetch, "w500", tmdb_path)
        if img is None:
            return None
    img = img.convert("RGBA")
    img.thumbnail((w, h))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def forget(cache: Path, item_id: int) -> None:
    """Drop cached images of a removed item (SQLite may reuse its id)."""
    paths = (list(cache.glob(f"poster_{item_id}_*.jpg")) + list(cache.glob(f"still_{item_id}_*.jpg"))
             + list(cache.glob(f"logo_{item_id}_*.png")) + list(cache.glob(f"case_{item_id}_*.png"))
             + list(cache.glob(f"disc_{item_id}_*.png")) + list(cache.glob(f"season_{item_id}_*.jpg")))
    for p in paths + [cache / f"backdrop_{item_id}.jpg", cache / f"logo_{item_id}.none"]:
        p.unlink(missing_ok=True)


def icon_jpeg(icon_file: Path, size: int = 48, selected: bool = False) -> bytes:
    bg = (42, 42, 53) if selected else BG
    img = Image.new("RGB", (size, size), bg)
    if icon_file.exists():
        icon = Image.open(icon_file).convert("RGBA")
        icon.thumbnail((size - 12, size - 12))
        img.paste(icon, ((size - icon.width) // 2, (size - icon.height) // 2), icon)
    if selected:
        ImageDraw.Draw(img).rectangle([0, 0, size - 1, size - 1], outline="white", width=2)
    return _jpeg(img)
