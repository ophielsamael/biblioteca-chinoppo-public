import io

import pytest
from PIL import Image

from biblio.config import load_folders


@pytest.fixture
def png_bytes():
    buf = io.BytesIO()
    Image.new("RGBA", (300, 200), (255, 0, 0, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_index_lists_folders_and_bdlive_hint(client):
    body = client.get("/").data.decode("utf-8")
    assert "ATMOS" in body and "BD-Live" in body


def test_add_folder_with_gallery_icon(client, tmp_path):
    r = client.post("/folders", data={"id": "demos", "name": "Demos", "path": "Library/DEMOS",
                                      "kind": "movies", "order": "5", "icon": "star.png"})
    assert r.status_code == 302
    assert any(f.name == "Demos" and f.icon == "star.png" for f in load_folders(tmp_path))


def test_edit_keeps_other_folders(client, tmp_path):
    client.post("/folders", data={"id": "atmos", "name": "Atmos 4K", "path": "Library/ATMOS",
                                  "kind": "movies", "order": "1", "icon": "atmos.png"})
    folders = load_folders(tmp_path)
    assert len(folders) == 5 and folders[1].name == "Atmos 4K"


def test_upload_icon_is_resized(client, tmp_path, png_bytes):
    client.post("/folders", data={"id": "x", "name": "X", "path": "Library/X", "kind": "movies",
                                  "order": "6", "icon_upload": (io.BytesIO(png_bytes), "i.png")},
                content_type="multipart/form-data")
    assert Image.open(tmp_path / "icons/x.png").size == (96, 96)


def test_rejects_path_outside_media(client):
    assert client.post("/folders", data={"id": "e", "name": "E", "path": "../etc",
                                         "kind": "movies", "order": "0"}).status_code == 400


def test_rejects_bad_id(client):
    assert client.post("/folders", data={"id": "../x", "name": "E", "path": "Library/X",
                                         "kind": "movies", "order": "0"}).status_code == 400


def test_autoopen_toggle(client, catalog):
    assert "Abrir la Biblioteca al encender" in client.get("/").data.decode("utf-8")
    client.post("/settings", data={})                       # unchecked box sends nothing
    assert catalog.get_state("autoopen") == "0"
    client.post("/settings", data={"autoopen": "1"})
    assert catalog.get_state("autoopen") == "1"


def test_delete_folder(client, tmp_path):
    client.post("/folders/3d/delete")
    assert "3d" not in [f.id for f in load_folders(tmp_path)]


def _red_center(data):
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return img.getpixel((img.width // 2, img.height // 2))


def test_own_poster_from_artwork_studio_replaces_tmdb(client, png_bytes, otto_id):
    before = client.get(f"/d/img/poster?id={otto_id}&w=150&h=225").data   # placeholder, now cached
    r = client.post("/art/poster?tmdb=937278", data=png_bytes, content_type="image/png")
    assert r.status_code == 200 and r.data.decode().startswith("ok")
    after = client.get(f"/d/img/poster?id={otto_id}&w=150&h=225").data
    assert after != before
    red, green, blue = _red_center(after)
    assert red > 200 and green < 60 and blue < 60


def test_own_logo_keeps_transparency(client, otto_id):
    buf = io.BytesIO()
    Image.new("RGBA", (800, 200), (255, 255, 255, 0)).save(buf, "PNG")
    assert client.post("/art/logo?tmdb=937278", data=buf.getvalue(), content_type="image/png").status_code == 200
    r = client.get(f"/d/img/logo?id={otto_id}&w=500&h=140")      # no TMDb in tests: only ours
    assert r.status_code == 200 and Image.open(io.BytesIO(r.data)).mode == "RGBA"


def test_art_for_a_series_does_not_hit_a_movie_with_the_same_id(client, png_bytes, otto_id):
    client.post("/art/poster?tmdb=937278&media=tv", data=png_bytes, content_type="image/png")
    red, green, blue = _red_center(client.get(f"/d/img/poster?id={otto_id}&w=150&h=225").data)
    assert not (red > 200 and green < 60 and blue < 60)


def test_art_rejects_non_images_and_unknown_kinds(client):
    assert client.post("/art/poster?tmdb=1", data=b"not an image").status_code == 400
    assert client.post("/art/poster", data=b"x").status_code == 400
    assert client.post("/art/trailer?tmdb=1", data=b"x").status_code == 404


class _FixedTmdb:
    def movie(self, mid):
        return {"tmdb_id": mid, "overview": "Picked by hand", "genres": [], "cast": []}

    def tv(self, tid):
        return {"tmdb_id": tid, "overview": "Serie", "genres": [], "cast": []}


def test_match_by_emby_path_is_set_and_locked(settings, catalog, otto_id):
    from app import create_app
    from biblio import catalog as catalog_mod
    c = create_app(settings, catalog, fetch=lambda u: b"", tmdb=_FixedTmdb()).test_client()
    path = "/data/Library/Movies/A Man Called Otto (2022).mkv"
    assert c.get("/match", query_string={"path": path}).json == {
        "id": otto_id, "title": "A Man Called Otto", "year": 2022, "tmdb_id": 937278, "media": "movie", "locked": False}
    r = c.post("/match", query_string={"path": path, "tmdb": 12})
    assert r.json["tmdb_id"] == 12 and r.json["locked"]
    assert catalog.get(otto_id).meta["overview"] == "Picked by hand"

    class Searching:
        def find_movie(self, t, y):
            return {"tmdb_id": 999, "overview": "automatic"}
    for rel in ("Library/Movies/A Man Called Otto (2022).mkv", "Library/Movies/Coda (2021).mkv"):
        (settings.media_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (settings.media_root / rel).write_bytes(b"x")
    catalog.set_state("tmdb_match", "0")              # force a rematch of everything
    catalog_mod.refresh(settings, catalog, Searching())
    assert catalog.get(otto_id).tmdb_id == 12          # the hand-picked one stays
    assert catalog.items("movies")[1].tmdb_id == 999   # the others were searched again


def test_match_unknown_path_and_bad_id(client):
    assert client.get("/match", query_string={"path": "/data/Library/Movies/Nope.mkv"}).status_code == 404
    assert client.post("/match", query_string={"path": "Library/Movies/Coda (2021).mkv"}).status_code == 400


def test_api_for_artwork_lists_folders_items_and_poster(client, otto_id):
    folders = client.get("/api/folders").json
    assert {"id": "movies", "kind": "movies", "count": 2}.items() <= next(f for f in folders if f["id"] == "movies").items()
    otto = next(i for i in client.get("/api/items?folder=movies").json if i["id"] == otto_id)
    assert otto["tmdb_id"] == 937278 and otto["path"].endswith("Otto (2022).mkv") and otto["media"] == "movie"
    assert otto["badges"] == []
    r = client.get(f"/api/poster?id={otto_id}")          # TMDb offline in tests: the placeholder
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    assert client.get("/api/poster?id=999").status_code == 404


def test_api_poster_fetches_tmdb_once(settings, catalog, otto_id):
    from app import create_app
    catalog.set_meta(otto_id, 937278, {"poster_path": "/otto.jpg"})
    calls = []
    def fetch(url):
        calls.append(url)
        import io
        from PIL import Image
        buf = io.BytesIO(); Image.new("RGB", (780, 1170)).save(buf, "JPEG"); return buf.getvalue()
    c = create_app(settings, catalog, fetch=fetch, tmdb=object()).test_client()
    assert c.get(f"/api/poster?id={otto_id}").status_code == 200
    assert c.get(f"/api/poster?id={otto_id}").status_code == 200
    assert calls == ["https://image.tmdb.org/t/p/w780/otto.jpg"]


def test_browse_lists_nas_subfolders_only_inside_media(client, settings):
    for d in ("Library/ATMOS", "Library/Movies", "Library/@eaDir", "Library/.hidden"):
        (settings.media_root / d).mkdir(parents=True, exist_ok=True)
    (settings.media_root / "Library/file.mkv").write_bytes(b"x")
    assert client.get("/browse").json == {"path": "", "dirs": ["Library"]}
    assert client.get("/browse?path=Library").json == {"path": "Library", "dirs": ["ATMOS", "Movies"]}
    assert client.get("/browse?path=../..").status_code == 404
    assert client.get("/browse?path=Library/Nope").status_code == 404
    assert "Elegir" in client.get("/").get_data(as_text=True)


def test_custom_poster_for_a_title_tmdb_does_not_know(client, coda_id, png_bytes):
    # Coda has no TMDb id in the fixture: its poster goes by catalog id
    assert client.post(f"/art/poster?item={coda_id}", data=png_bytes).get_data(as_text=True) == "ok 1"
    assert client.get(f"/api/poster?id={coda_id}").get_data() == png_bytes
    wall = client.get(f"/d/img/poster?id={coda_id}&w=150&h=225")
    assert wall.status_code == 200
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(wall.get_data())).getpixel((75, 112))[0] > 200     # the red upload, not the placeholder
    assert client.delete(f"/art/poster?item={coda_id}").status_code == 200
    assert client.get(f"/api/poster?id={coda_id}").get_data() != png_bytes
    assert client.post("/art/poster?item=999", data=png_bytes).status_code == 404


def test_own_season_poster_replaces_tmdbs(client, catalog, show_id, png_bytes):
    from PIL import Image
    import io
    assert client.post("/art/season2?tmdb=100088&media=tv", data=png_bytes).get_data(as_text=True) == "ok 1"
    img = Image.open(io.BytesIO(client.get(f"/d/img/season?id={show_id}&season=2&w=140&h=210").data))
    assert img.getpixel((70, 105))[0] > 200 and img.getpixel((70, 105))[1] < 60   # the red upload
    assert client.post("/art/seasonX?tmdb=100088&media=tv", data=png_bytes).status_code == 404
    series = client.get("/api/items?folder=series").json
    assert series[0]["seasons"] == [2]


def test_warm_makes_every_page_image_once(settings, catalog, show_id):
    from app import create_app, warm
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (300, 450), (200, 0, 0)).save(buf, "JPEG")
    def fetch(url):        # every TMDb image: a red picture
        return buf.getvalue()
    catalog.set_meta(show_id, 100088, {"poster_path": "/p.jpg", "season_posters": {"2": "/s2.jpg"}})
    app = create_app(settings, catalog, fetch=fetch, tmdb=object(), logos=lambda kind, tid: None)
    assert warm(app, catalog) == 3        # Otto, Coda and the series
    names = {p.name.split("_")[0] for p in (settings.data_dir / "cache").iterdir()}
    assert {"poster", "season"} <= names
