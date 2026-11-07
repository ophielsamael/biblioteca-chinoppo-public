def test_folders_lists_defaults_with_counts(client):
    lines = client.get("/d/folders").data.decode("utf-8").split("\n")
    assert lines[3] == "movies\tMovies\t2" and len(lines) == 5


def test_items_paging(client):
    lines = client.get("/d/items?folder=movies&offset=1&limit=1").data.decode().split("\n")
    assert lines[0] == "2" and lines[1].split("\t")[1] == "Coda"


def test_item_detail_utf8(client, otto_id):
    body = client.get(f"/d/item?id={otto_id}").data.decode("utf-8")
    assert "director\tMarc Forster" in body and "resume\t0" in body and "genres\tComedia, Drama" in body


def test_unknown_item_is_404(client):
    assert client.get("/d/item?id=999").status_code == 404


def test_poster_fallback_without_tmdb(client, coda_id):
    r = client.get(f"/d/img/poster?id={coda_id}&w=150&h=225")
    assert r.mimetype == "image/jpeg" and r.data[:2] == b"\xff\xd8"


def test_backdrop_is_1280x720(client, otto_id):
    import io
    from PIL import Image
    r = client.get(f"/d/img/backdrop?id={otto_id}")
    assert Image.open(io.BytesIO(r.data)).size == (1280, 720)


def test_backdrop_darker_on_the_left(settings, catalog, otto_id):
    import io
    from PIL import Image
    from biblio.images import backdrop_jpeg
    it = catalog.get(otto_id)
    it.meta["backdrop_path"] = "/x.jpg"
    buf = io.BytesIO()
    Image.new("RGB", (1280, 720), "white").save(buf, "PNG")
    img = Image.open(io.BytesIO(backdrop_jpeg(it, settings.data_dir / "cache", lambda url: buf.getvalue())))
    left, right = img.getpixel((5, 360))[0], img.getpixel((1274, 360))[0]
    assert left < 40 and 150 < right < 180  # 0.92 dark on the left, 0.35 on the right


def test_failed_download_is_not_cached(settings, catalog, otto_id):
    import io
    from PIL import Image
    from biblio.images import poster_jpeg
    it = catalog.get(otto_id)
    it.meta["poster_path"] = "/p.jpg"
    def offline(url):
        raise OSError("offline")
    poster_jpeg(it, settings.data_dir / "cache", 150, 225, offline)
    buf = io.BytesIO()
    Image.new("RGB", (500, 750), "red").save(buf, "JPEG")
    img = Image.open(io.BytesIO(poster_jpeg(it, settings.data_dir / "cache", 150, 225, lambda u: buf.getvalue())))
    assert img.getpixel((5, 5))[0] > 200   # the real (red) poster, not the cached dark placeholder


def test_items_include_kind(client):
    line = client.get("/d/items?folder=movies").data.decode().split("\n")[1]
    assert line.split("\t")[3] == "file"


def test_series_item_lists_seasons(client, show_id):
    body = client.get(f"/d/item?id={show_id}").data.decode()
    assert "kind\tseries" in body and "seasons\t2" in body


def test_episodes_mark_missing_files(client, show_id):
    lines = client.get(f"/d/episodes?id={show_id}&season=2").data.decode().split("\n")
    assert len(lines) == 7
    assert lines[2].split("\t")[:2] == ["3", "Capítulo 3"]
    assert lines[2].split("\t")[3] != "0"        # E3 is in S02E01e02e03.iso
    assert lines[5].split("\t")[3] == "0"        # E6 is not on disk


def test_episodes_without_tmdb_use_disk(client, catalog, show_id):
    catalog._write("DELETE FROM season_meta")
    lines = client.get(f"/d/episodes?id={show_id}&season=2").data.decode().split("\n")
    assert [l.split("\t")[1] for l in lines] == [f"Episodio {n}" for n in range(1, 6)]


def test_episodes_on_disk_beyond_tmdb_are_listed(client, catalog, show_id):
    from biblio.scan import EpisodeFile
    base = "Library/SERIES/The Last of Us/S02/"
    catalog.set_episode_files(show_id, [EpisodeFile(base + "S02E01e02e03.iso", "iso", 2, [1, 2, 3]),
                                        EpisodeFile(base + "S02E09.mkv", "file", 2, [9])])
    lines = client.get(f"/d/episodes?id={show_id}&season=2").data.decode().split("\n")
    assert [l.split("\t")[0] for l in lines] == [str(n) for n in range(1, 8)] + ["9"]
    assert lines[-1].split("\t")[1] == "Episodio 9" and lines[-1].split("\t")[3] != "0"


def test_still_fallback_is_jpeg(client, show_id):
    r = client.get(f"/d/img/still?id={show_id}&season=2&episode=6&w=240&h=135")
    assert r.mimetype == "image/jpeg" and r.data[:2] == b"\xff\xd8"


def test_state_roundtrip(client, otto_id):
    assert client.get(f"/d/select?folder=movies&item={otto_id}").data == b"ok"
    body = client.get("/d/state").data.decode()
    assert f"item\t{otto_id}" in body and "folder\tmovies" in body


def _logo_app(settings, catalog, find, fetch):
    from app import create_app
    return create_app(settings, catalog, fetch=fetch, logos=find).test_client()


def test_logo_png_fits_box_and_keeps_transparency(settings, catalog, otto_id):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (800, 200), (255, 255, 255, 0)).save(buf, "PNG")
    c = _logo_app(settings, catalog, lambda kind, tid: "/l.png", lambda url: buf.getvalue())
    r = c.get(f"/d/img/logo?id={otto_id}&w=500&h=140")
    img = Image.open(io.BytesIO(r.data))
    assert r.mimetype == "image/png" and img.mode == "RGBA"
    assert img.size == (500, 125)                     # aspect kept, inside 500x140


def test_logo_404_when_tmdb_has_none_and_remembered(settings, catalog, otto_id):
    calls = []
    c = _logo_app(settings, catalog, lambda kind, tid: calls.append(tid) or None, lambda url: b"")
    assert c.get(f"/d/img/logo?id={otto_id}").status_code == 404
    assert c.get(f"/d/img/logo?id={otto_id}").status_code == 404
    assert calls == [937278]                          # asked TMDb once


def test_logo_not_remembered_when_tmdb_fails(settings, catalog, otto_id):
    calls = []
    def find(kind, tid):
        calls.append(tid)
        raise OSError("offline")
    c = _logo_app(settings, catalog, find, lambda url: b"")
    c.get(f"/d/img/logo?id={otto_id}")
    c.get(f"/d/img/logo?id={otto_id}")
    assert len(calls) == 2


def _png(data):
    import io
    from PIL import Image
    return Image.open(io.BytesIO(data))


def test_no_case_unless_one_was_chosen(client, otto_id):
    # not every film is 4K: cases are picked title by title in Artwork Studio
    img = _png(client.get(f"/d/img/case?id={otto_id}&w=240&h=350").data).convert("RGBA")
    assert img.size == (240, 350)
    assert img.getpixel((120, 2))[3] == 255 and img.getpixel((120, 347))[3] == 255   # plain poster, top to bottom


def test_tool_puts_a_cover_in_a_case(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1000, 1500), "red").save(buf, "JPEG")
    for kind in ("bluray", "uhd"):
        r = client.post(f"/tools/case?kind={kind}&title=Otto", data=buf.getvalue(), content_type="image/jpeg")
        img = _png(r.data)
        assert r.mimetype == "image/png" and img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0                                   # see-through around
        red, green, blue, alpha = img.getpixel((img.width // 2, img.height // 2))
        assert alpha == 255 and red > 200 and green < 60                    # the cover inside


def _jpeg_of(colour):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1000, 1500), colour).save(buf, "JPEG")
    return buf.getvalue()


def test_case_only_on_the_detail_page_poster_stays_on_the_wall(client, otto_id):
    # 2026-11-04: rows of cases on the wall looked bad; the wall keeps the poster (with its
    # banner), the case (4K black / HD blue) is a separate image for the detail page
    boxed = client.post("/tools/case?kind=uhd", data=_jpeg_of("red"), content_type="image/jpeg").data
    assert client.post("/art/poster?tmdb=937278", data=_jpeg_of("green"), content_type="image/jpeg").status_code == 200
    assert client.post("/art/case?tmdb=937278", data=boxed, content_type="image/png").status_code == 200
    detail = _png(client.get(f"/d/img/case?id={otto_id}&w=240&h=350").data).convert("RGBA")
    assert detail.getpixel((0, 0))[3] == 0
    red, green, blue, _ = detail.getpixel((130, 175))
    assert red > 200 and green < 60                                          # the case's cover
    red, green, blue = _png(client.get(f"/d/img/poster?id={otto_id}&w=150&h=225").data).getpixel((75, 112))
    assert green > 100 and red < 60                                          # wall: the poster


def test_removing_the_case_goes_back_to_the_poster(client, otto_id):
    boxed = client.post("/tools/case?kind=bluray", data=_jpeg_of("red"), content_type="image/jpeg").data
    client.post("/art/case?tmdb=937278", data=boxed, content_type="image/png")
    client.get(f"/d/img/case?id={otto_id}&w=240&h=350")                      # cached with the case
    assert client.delete("/art/case?tmdb=937278").status_code == 200
    detail = _png(client.get(f"/d/img/case?id={otto_id}&w=240&h=350").data).convert("RGBA")
    assert detail.getpixel((120, 2))[3] == 255                               # plain poster again


def test_detail_poster_is_not_cropped(client, otto_id):
    # seen 2026-11-04: Artwork's "4K ULTRA HD" banner lost its top on the 240x350 detail slot
    import io
    from PIL import Image, ImageDraw
    src = Image.new("RGB", (1000, 1500), "red")
    ImageDraw.Draw(src).rectangle([0, 0, 999, 17], fill="blue")      # thin banner along the top edge
    buf = io.BytesIO()
    src.save(buf, "JPEG")
    client.post("/art/poster?tmdb=937278", data=buf.getvalue(), content_type="image/jpeg")
    img = _png(client.get(f"/d/img/case?id={otto_id}&w=240&h=350").data).convert("RGBA")
    first = next(y for y in range(img.height) if img.getpixel((img.width // 2, y))[3] > 200)
    red, green, blue, _ = img.getpixel((img.width // 2, first + 1))
    assert blue > 150 and red < 100


def test_disc_sprite_only_for_titles_with_a_case(client, otto_id):
    assert client.get(f"/d/img/disc?id={otto_id}").status_code == 404     # no case chosen: no disc
    boxed = client.post("/tools/case?kind=uhd", data=_jpeg_of("red"), content_type="image/jpeg").data
    client.post("/art/case?tmdb=937278", data=boxed, content_type="image/png")
    r = client.get(f"/d/img/disc?id={otto_id}&size=100&frames=48")
    img = _png(r.data).convert("RGBA")
    # only the right half of each turn: the left half never leaves the case (half the memory)
    assert r.mimetype == "image/png" and img.size == (400, 600)            # 8 x 6 cells of 50 x 100
    assert img.getpixel((48, 2))[3] == 0 and img.getpixel((0, 50))[3] == 0   # round, and its hole
    assert img.getpixel((25, 12))[3] == 255                                # the label ring


def test_chosen_disc_art_replaces_the_generated_disc(client, otto_id):
    # Artwork Studio's "Discos" tab: the disc picked on fanart.tv slides out instead
    import io
    from PIL import Image, ImageDraw
    boxed = client.post("/tools/case?kind=bluray", data=_jpeg_of("red"), content_type="image/jpeg").data
    client.post("/art/case?tmdb=937278", data=boxed, content_type="image/png")
    art = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    ImageDraw.Draw(art).ellipse([0, 0, 999, 999], fill=(0, 0, 255, 255))
    buf = io.BytesIO()
    art.save(buf, "PNG")
    assert client.post("/art/disc?tmdb=937278", data=buf.getvalue(), content_type="image/png").status_code == 200
    img = _png(client.get(f"/d/img/disc?id={otto_id}&size=100&frames=1").data).convert("RGBA")
    assert img.size == (50, 100)
    red, green, blue, alpha = img.getpixel((25, 50))
    assert blue > 200 and red < 60 and alpha == 255
    assert img.getpixel((48, 2))[3] == 0                                   # still round


def test_series_item_counts_episodes_per_season_and_serves_season_posters(client, catalog, show_id):
    body = client.get(f"/d/item?id={show_id}").get_data(as_text=True)
    assert "season_counts\t5" in body                      # S02: E1-3 and E4-5 on the NAS
    r = client.get(f"/d/img/season?id={show_id}&season=2&w=140&h=210")
    assert r.status_code == 200 and r.mimetype == "image/jpeg"   # TMDb offline in tests: placeholder


def test_series_matched_before_get_their_season_posters(tmp_path):
    from biblio import catalog as catalog_mod
    from biblio.db import Catalog
    from tests.fakes import FakeTmdb, settings_with
    s = settings_with(tmp_path, {"Library/SERIES/The Last of Us/S01/The Last of Us S01E01.mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    catalog_mod.refresh(s, cat, None)
    show = cat.items("series")[0] if cat.items("series") else None
    assert show is not None
    cat.set_meta(show.id, 100088, {"overview": "old match, no season posters", "locked": True})
    catalog_mod.refresh(s, cat, FakeTmdb(True))
    meta = cat.get(show.id).meta
    assert meta["season_posters"]["1"] == "/s1.jpg" and meta["locked"] and meta["overview"].startswith("old")


def test_item_says_whether_there_is_a_case(client, settings, otto_id):
    assert "hascase\t0" in client.get(f"/d/item?id={otto_id}").get_data(as_text=True)
    from biblio import images
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGBA", (10, 10)).save(buf, "PNG")
    images.save_own(settings.data_dir / "cache", "movie", 937278, "case", buf.getvalue())
    assert "hascase\t1" in client.get(f"/d/item?id={otto_id}").get_data(as_text=True)


def test_season_badges_use_the_shared_episode_format(settings, catalog, show_id):
    from app import create_app
    from biblio import badges
    # S02 has two episode files; give them a 4K HDR10 Atmos format
    fmt = {"res": "4K", "hdr": ["HDR10"], "audio": "TrueHD", "atmos": True, "ch": "7.1", "source": "disc"}
    for f in catalog.episode_files(show_id):
        catalog.set_format(-f.id, "1:1", fmt)
    assert catalog.season_format(show_id, 2) == fmt
    calls = []
    def fetch(url):
        calls.append(url)
        import io, json
        from PIL import Image
        if url == badges.TEMPLATE_URL:
            return json.dumps({"groups": [{"id": "r"}], "filters": [
                {"groupId": "r", "name": "4K", "pattern": "2160p", "imageURL": "https://x/4k.png"}]}).encode()
        buf = io.BytesIO(); Image.new("RGBA", (80, 40)).save(buf, "PNG"); return buf.getvalue()
    c = create_app(settings, catalog, fetch=fetch, tmdb=object()).test_client()
    r = c.get(f"/d/img/badges?id={show_id}&season=2&h=30&w=600")
    assert r.status_code == 200
    assert c.get(f"/d/img/badges?id={show_id}&season=1").status_code == 404   # no episodes on disk
