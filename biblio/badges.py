"""Format badges from a Badger template (https://nintle.github.io/Badger/, community templates).

A template is a list of filters: a regex over a release name and the badge image it shows.
We write a release-style name from the detected format (biblio.formats), e.g.
"Title.2160p.BluRay.DV.HDR10.TrueHD.Atmos.7.1.mkv", and keep the filters it matches, in the
template's group order. SVG badges are rasterised here (resvg): the Chinoppo's Java draws PNG only.
Badger draws a tag around each image (tagStyle bordered / filled, with its colours): so do we.
"""
import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# "Minimalist White" by sweatycab (chosen 2026-11-04): white outlined tags, SVG
TEMPLATE_URL = "https://raw.githubusercontent.com/sweatycab/nuvio-minimalist-badges/main/badges-white.json"

AUDIO_TOKENS = {"TrueHD": "TrueHD", "DTS-HD MA": "DTS-HD.MA", "DTS-HD HRA": "DTS-HD.HRA", "DTS": "DTS",
                "DD+": "DDP", "DD": "DD", "LPCM": "LPCM", "FLAC": "FLAC", "AAC": "AAC"}


def release_names(fmt: dict) -> list[str]:
    """With Atmos / DTS:X both the codec and the immersive format get a badge (TrueHD + Atmos).
    Templates often make them exclusive ("Atmos" only when no TrueHD is named), so the name is
    also tried without the codec."""
    full = release_name(fmt, codec=True)
    if fmt.get("atmos") or fmt.get("dtsx"):
        return [full, release_name(fmt, codec=False)]
    return [full]


def release_name(fmt: dict, codec: bool = True) -> str:
    res = {"4K": "2160p", "1080p": "1080p", "720p": "720p", "SD": "576p"}.get(fmt.get("res"), "")
    source = {"disc": "BluRay", "remux": "BluRay.Remux", "web": "WEB-DL", "dvd": "DVDRip"}.get(fmt.get("source"), "")
    parts = ["Title", res, source]
    parts += [{"DV": "DV", "HDR10+": "HDR10Plus", "HDR10": "HDR10", "HLG": "HLG"}[h] for h in fmt.get("hdr", [])]
    if fmt.get("3d"):
        parts.append("3D")
    if fmt.get("audio") and codec:
        parts.append(AUDIO_TOKENS.get(fmt["audio"], fmt["audio"]))
    if fmt.get("dtsx"):
        parts.append("DTS-X")
    if fmt.get("atmos"):
        parts.append("Atmos")
    if fmt.get("ch"):
        parts.append(str(fmt["ch"]))
    return ".".join(p for p in parts if p) + ".mkv"


def _compile(pattern: str):
    """Badger patterns are JavaScript regexes; most work in Python. A leading (?i) is common."""
    try:
        return re.compile(pattern)
    except re.error:
        try:
            return re.compile(pattern.replace("(?i)", ""), re.IGNORECASE)
        except re.error:
            return None


def matches(template: dict, names: list[str]) -> list[dict]:
    """The template's enabled filters (PNG or SVG) matching any of the names, in group order
    and, inside a group, in the template's own order."""
    order = {g["id"]: i for i, g in enumerate(template.get("groups", []))}
    hits = []
    for i, f in enumerate(template.get("filters", [])):
        url = f.get("imageURL") or ""
        if not f.get("isEnabled", True) or not url.split("?")[0].lower().endswith((".png", ".svg")):
            continue
        rx = _compile(f.get("pattern") or "")
        if rx and any(rx.search(n) for n in names):
            hits.append((order.get(f.get("groupId"), 999), i, f))
    return [f for _, _, f in sorted(hits, key=lambda t: (t[0], t[1]))]


def _get(cache: Path, url: str, fetch) -> bytes:
    """Template JSON and badge images, downloaded once (delete data/badges to refresh)."""
    path = cache / hashlib.sha1(url.encode()).hexdigest()
    if not path.exists():
        data = fetch(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path.read_bytes()


def _colour(hexa: str | None) -> tuple[int, int, int, int] | None:
    """#RRGGBB or #RRGGBBAA; None when missing or fully transparent."""
    h = (hexa or "").lstrip("#")
    if len(h) not in (6, 8):
        return None
    rgba = tuple(int(h[i:i + 2], 16) for i in range(0, len(h), 2)) + ((255,) if len(h) == 6 else ())
    return rgba if rgba[3] else None


def _image(cache: Path, url: str, h: int, fetch) -> Image.Image:
    data = _get(cache, url, fetch)
    if url.split("?")[0].lower().endswith(".svg"):
        import resvg_py
        data = bytes(resvg_py.svg_to_bytes(svg_string=data.decode("utf-8"), height=h * 3))
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    return im.crop(im.getbbox() or (0, 0, im.width, im.height))      # tight: badges have margins


def _tag(f: dict, im: Image.Image, h: int) -> Image.Image:
    """One badge h pixels high: the image, inside Badger's tag when the template draws one."""
    style = f.get("tagStyle") or ""
    fill = _colour(f.get("tagColor")) if "filled" in style else None
    border = _colour(f.get("borderColor")) if "bordered" in style else None
    if not fill and not border:
        return im.resize((max(1, im.width * h // im.height), h), Image.LANCZOS)
    ih = int(h * 0.62)
    im = im.resize((max(1, im.width * ih // im.height), ih), Image.LANCZOS)
    pad, line = int(h * 0.22), max(1, h // 16)
    tag = Image.new("RGBA", (im.width + 2 * pad, h), (0, 0, 0, 0))
    ImageDraw.Draw(tag).rounded_rectangle((0, 0, tag.width - 1, h - 1), radius=h // 5, fill=fill,
                                           outline=border, width=line if border else 0)
    tag.alpha_composite(im, (pad, (h - ih) // 2))
    return tag


def _text_tag(text: str, h: int) -> Image.Image:
    """A white outlined tag with bold text, like the template's."""
    font = ImageFont.load_default(size=int(h * 0.62))
    tw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=font))
    pad, line = int(h * 0.22), max(1, h // 16)
    tag = Image.new("RGBA", (tw + 2 * pad, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tag)
    d.rounded_rectangle((0, 0, tag.width - 1, h - 1), radius=h // 5, outline=(255, 255, 255, 255), width=line)
    d.text((tag.width // 2, h // 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm",
           stroke_width=max(1, h // 30), stroke_fill=(255, 255, 255, 255))     # bold-ish, like the SVGs
    return tag


def strip(fmt: dict | None, cache: Path, h: int, max_w: int, fetch, template_url: str = TEMPLATE_URL) -> Image.Image | None:
    """The title's badges side by side, h pixels high, transparent, at most max_w wide.
    None when the format is unknown or nothing matches (or GitHub can't be reached)."""
    if not fmt or not fmt.get("res"):
        return None
    key = hashlib.sha1(json.dumps([template_url, release_names(fmt), h, max_w]).encode()).hexdigest()
    done = cache / f"strip_{key}.png"
    if done.exists():
        return Image.open(done).convert("RGBA")
    try:
        template = json.loads(_get(cache, template_url, fetch))
        imgs = [_tag(f, _image(cache, f["imageURL"], h, fetch), h)
                for f in matches(template, release_names(fmt))]
    except Exception:
        return None
    if fmt.get("3d") and not any("3d" in (f.get("name") or "").lower() for f in matches(template, release_names(fmt))):
        imgs.insert(1 if imgs else 0, _text_tag("3D", h))   # Minimalist White has none: ours, after the resolution
    if not imgs:
        return None
    gap = h // 3
    out = Image.new("RGBA", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), h), (0, 0, 0, 0))
    x = 0
    for im in imgs:
        out.alpha_composite(im, (x, 0))
        x += im.width + gap
    if out.width > max_w:
        out = out.resize((max_w, max(1, h * max_w // out.width)), Image.LANCZOS)
    done.parent.mkdir(parents=True, exist_ok=True)
    out.save(done, "PNG")
    return out
