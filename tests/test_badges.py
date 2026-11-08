import io
import json

from PIL import Image

from biblio import badges

TEMPLATE = {
    "groups": [{"id": "res"}, {"id": "hdr"}, {"id": "audio"}],
    "filters": [
        {"groupId": "audio", "name": "TrueHD", "pattern": "(?i)truehd", "imageURL": "https://x/truehd.png"},
        {"groupId": "audio", "name": "Dolby Atmos", "pattern": "(?i)atmos", "imageURL": "https://x/atmos.png"},
        {"groupId": "hdr", "name": "Dolby Vision", "pattern": r"(?i)\bDV\b", "imageURL": "https://x/dv.png"},
        {"groupId": "res", "name": "4K", "pattern": "(?i)2160p", "imageURL": "https://x/4k.png"},
        {"groupId": "res", "name": "4K svg", "pattern": "(?i)2160p", "imageURL": "https://x/4k.gif"},
        {"groupId": "hdr", "name": "off", "pattern": ".", "imageURL": "https://x/off.png", "isEnabled": False},
    ],
}
UHD = {"res": "4K", "hdr": ["DV", "HDR10"], "audio": "TrueHD", "atmos": True, "ch": "7.1", "source": "disc"}


def _png(w, h, colour):
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


def fake_fetch(calls):
    def fetch(url):
        calls.append(url)
        return json.dumps(TEMPLATE).encode() if url == badges.TEMPLATE_URL else _png(80, 40, (255, 0, 0, 255))
    return fetch


def test_truehd_and_atmos_both_even_when_the_template_makes_them_exclusive():
    names = badges.release_names(UHD)
    assert names == ["Title.2160p.BluRay.DV.HDR10.TrueHD.Atmos.7.1.mkv", "Title.2160p.BluRay.DV.HDR10.Atmos.7.1.mkv"]
    tpl = dict(TEMPLATE, filters=[dict(f, pattern=r"(?i)^(?!.*truehd).*atmos") if f["name"] == "Dolby Atmos" else f
                                  for f in TEMPLATE["filters"]])
    assert [f["name"] for f in badges.matches(tpl, names)] == ["4K", "Dolby Vision", "TrueHD", "Dolby Atmos"]
    assert badges.release_names({"res": "1080p", "hdr": [], "audio": "DTS"}) == ["Title.1080p.DTS.mkv"]


def test_strip_is_cached_scaled_and_fits(tmp_path):
    calls = []
    s = badges.strip(UHD, tmp_path, 20, 1000, fake_fetch(calls))
    assert s.size == (4 * 40 + 3 * 6, 20)              # 80x40 badges at h=20, gap h//3
    badges.strip(UHD, tmp_path, 20, 1000, fake_fetch(calls))
    assert len(calls) == 5                              # template + 4 images, downloaded once
    assert badges.strip(UHD, tmp_path, 20, 66, fake_fetch(calls)).width == 66


def test_no_badges_without_format_or_network(tmp_path):
    assert badges.strip(None, tmp_path, 20, 500, fake_fetch([])) is None
    def down(url):
        raise OSError("offline")
    assert badges.strip(UHD, tmp_path, 20, 500, down) is None


def test_badges_route(settings, catalog, otto_id, tmp_path):
    from app import create_app
    catalog.set_format(otto_id, "1:1", UHD)
    c = create_app(settings, catalog, fetch=fake_fetch([]), tmdb=object()).test_client()
    r = c.get(f"/d/img/badges?id={otto_id}&h=30&w=400")
    assert r.status_code == 200 and Image.open(io.BytesIO(r.data)).height == 30
    coda = catalog.items("movies")[1].id
    assert c.get(f"/d/img/badges?id={coda}").status_code == 404


def test_svg_badge_inside_a_bordered_tag(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="#fff"/></svg>'
    tpl = {"groups": [{"id": "g"}], "filters": [
        {"groupId": "g", "name": "4K", "pattern": "2160p", "imageURL": "https://x/4k.svg",
         "tagStyle": "bordered", "borderColor": "#FFFFFF", "tagColor": "#00000000"}]}
    def fetch(url):
        return json.dumps(tpl).encode() if url == "https://x/t.json" else svg
    s = badges.strip(UHD, tmp_path, 40, 1000, fetch, "https://x/t.json")
    assert s.height == 40 and s.width > 2 * 40 * 0.62     # the 2:1 image plus the tag's padding
    assert s.getpixel((0, 20))[3] == 255                  # the border, left edge
    assert s.getpixel((3, 20))[3] == 0                    # transparent inside the tag, before the image


def test_strip_is_kept_on_disk(tmp_path):
    calls = []
    badges.strip(UHD, tmp_path, 20, 1000, fake_fetch(calls))
    n = len(calls)
    def offline(url):
        raise OSError("offline")
    assert badges.strip(UHD, tmp_path, 20, 1000, offline).size == (4 * 40 + 3 * 6, 20)   # from the cached strip
    assert len(calls) == n


def test_own_text_style_needs_no_download(tmp_path):
    def offline(url):
        raise OSError("offline")
    s = badges.strip(UHD, tmp_path, 30, 2000, offline, None)
    assert s is not None and s.height == 30
    assert badges.text_labels(UHD) == ["4K", "BluRay", "Dolby Vision", "HDR10", "TrueHD", "Atmos", "7.1"]


def test_snapshot_keeps_every_badge_and_works_offline(tmp_path):
    calls = []
    fetch = fake_fetch(calls)
    url = badges.style("minimalist-white")["url"]
    def by_style(u):
        return fetch(badges.TEMPLATE_URL if u == url else u)
    assert badges.snapshot("minimalist-white", tmp_path, by_style) == 4        # every enabled png/svg (not the gif)
    def offline(u):
        raise OSError("offline")
    assert badges.strip(UHD, tmp_path, 20, 1000, offline, url) is not None    # all from the saved copy


def test_badge_style_api(settings, catalog, otto_id):
    from app import create_app
    catalog.set_format(otto_id, "1:1", UHD)
    c = create_app(settings, catalog, fetch=fake_fetch([]), tmdb=object()).test_client()
    styles = c.get("/api/badge-styles").json
    assert [st["id"] for st in styles if st["selected"]] == ["minimalist-white"]
    assert c.post("/api/badge-style", json={"id": "texto"}).json["ok"]
    assert [st["id"] for st in c.get("/api/badge-styles").json if st["selected"]] == ["texto"]
    assert c.get("/api/badge-styles/texto.png").status_code == 200
    assert c.post("/api/badge-style", json={"id": "nope"}).status_code == 400
    r = c.get(f"/d/img/badges?id={otto_id}&h=30&w=900")      # now drawn with our text style
    assert r.status_code == 200


def test_prefetch_saves_every_style_and_reports_it(tmp_path):
    cache = tmp_path / "badges"
    def fetch(url):
        if url.endswith(".json"):
            return json.dumps({"groups": [{"id": "g"}], "filters": [
                {"groupId": "g", "name": "4K", "pattern": "2160p", "imageURL": url.replace(".json", ".png")}]}).encode()
        return _png(80, 40, (255, 0, 0, 255))
    assert not badges.is_saved("haz", cache) and badges.is_saved("texto", cache)
    logs = []
    n = badges.prefetch_all(cache, fetch, lambda *a: logs.append(a), pause=0)
    assert n == len([s for s in badges.STYLES if s["url"]])
    assert all(badges.is_saved(s["id"], cache) for s in badges.STYLES)
    assert badges.prefetch_all(cache, fetch, None, pause=0) == 0            # nothing left to download


def test_prefetch_survives_one_unreachable_style(tmp_path):
    def fetch(url):
        if "djgenesis" in url:
            raise OSError("gone")
        if url.endswith(".json"):
            return json.dumps({"filters": []}).encode()
        return b""
    cache = tmp_path / "badges"
    badges.prefetch_all(cache, fetch, None, pause=0)
    assert not badges.is_saved("haz", cache) and badges.is_saved("elite", cache)


def test_own_3d_tag_when_the_template_has_none(tmp_path):
    fmt = {"res": "1080p", "hdr": [], "3d": True, "source": "disc"}
    tpl = {"groups": [{"id": "g"}], "filters": [
        {"groupId": "g", "name": "1080p", "pattern": "1080p", "imageURL": "https://x/1080.png"}]}
    def fetch(url):
        return json.dumps(tpl).encode() if url == "https://x/t.json" else _png(80, 40, (255, 0, 0, 255))
    with3d = badges.strip(fmt, tmp_path, 30, 1000, fetch, "https://x/t.json")
    without = badges.strip(dict(fmt, **{"3d": False}), tmp_path, 30, 1000, fetch, "https://x/t.json")
    assert with3d.width > without.width + 30
