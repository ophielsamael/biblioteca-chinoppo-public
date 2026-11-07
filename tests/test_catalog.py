from biblio.catalog import refresh
from biblio.db import Catalog
from tests.fakes import FakeTmdb, settings_with


def test_refresh_keeps_ids_and_falls_back_without_tmdb(tmp_path):
    s = settings_with(tmp_path, {"Library/Movies/Black Swan (2010).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    assert refresh(s, cat, FakeTmdb(found=False))["movies"] == 1
    it = cat.items("movies")[0]
    assert (it.title, it.year, it.tmdb_id) == ("Black Swan", 2010, None)
    first_id = it.id
    refresh(s, cat, FakeTmdb(found=True))
    it = cat.get(first_id)
    assert it.tmdb_id == 44214 and it.meta["director"] == "Darren Aronofsky"


def test_removed_files_disappear(tmp_path):
    s = settings_with(tmp_path, {"Library/Movies/A (2000).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, None)
    (s.media_root / "Library/Movies/A (2000).mkv").unlink()
    refresh(s, cat, None)
    assert cat.count("movies") == 0


def test_missing_nas_mount_keeps_catalog(tmp_path):
    import shutil
    s = settings_with(tmp_path, {"Library/Movies/A (2000).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, None)
    shutil.rmtree(s.media_root / "Library")          # host bind mount dropped
    refresh(s, cat, None)
    assert cat.count("movies") == 1


def test_removed_item_forgets_progress(tmp_path):
    s = settings_with(tmp_path, {"Library/Movies/A (2000).mkv": b"x", "Library/Movies/B (2001).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, None)
    gone = cat.items("movies")[0].id
    cat.save_progress(gone, 600, 6000)
    (s.media_root / "Library/Movies/A (2000).mkv").unlink()
    refresh(s, cat, None)
    assert cat.progress(gone) is None


def test_series_refresh(tmp_path):
    s = settings_with(tmp_path, {"Library/SERIES/The Last of Us/S02/S02E01e02e03.iso": b"x",
                                 "Library/SERIES/The Last of Us/S02/S02E04e05.iso": b"x"})
    cat = Catalog(tmp_path / "c.db")
    assert refresh(s, cat, FakeTmdb(found=True))["series"] == 1
    show = cat.items("series")[0]
    assert show.kind == "series" and show.tmdb_id == 100088
    assert cat.seasons(show.id) == [2]
    assert len(cat.season_meta(show.id, 2)) == 7
    assert cat.file_for(show.id, 2, 3).relpath.endswith("S02E01e02e03.iso")
    assert cat.file_for(show.id, 2, 6) is None


def test_season_meta_refetched_when_disk_has_newer_episodes(tmp_path):
    s = settings_with(tmp_path, {"Library/SERIES/The Last of Us/S02/S02E01e02e03.iso": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, FakeTmdb(found=True))
    show = cat.items("series")[0]
    cat.set_season_meta(show.id, 2, [{"number": 1, "title": "Viejo", "air_date": "", "overview": "",
                                      "still_path": None}])            # cached while the season aired
    refresh(s, cat, FakeTmdb(found=True))
    assert len(cat.season_meta(show.id, 2)) == 7


def test_series_without_tmdb_keeps_folder_name(tmp_path):
    s = settings_with(tmp_path, {"Library/SERIES/Mi Serie/S01/S01E01.mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, FakeTmdb(found=False))
    show = cat.items("series")[0]
    assert show.title == "Mi Serie" and cat.season_meta(show.id, 1) is None


def test_episode_file_ids_stable_and_progress_dropped(tmp_path):
    s = settings_with(tmp_path, {"Library/SERIES/X/S01/S01E01.mkv": b"x", "Library/SERIES/X/S01/S01E02.mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    refresh(s, cat, None)
    show = cat.items("series")[0]
    f1 = cat.file_for(show.id, 1, 1)
    cat.save_progress(-f1.id, 300, 2400)
    refresh(s, cat, None)
    assert cat.file_for(show.id, 1, 1).id == f1.id
    (s.media_root / "Library/SERIES/X/S01/S01E01.mkv").unlink()
    refresh(s, cat, None)
    assert cat.progress(-f1.id) is None and cat.file_for(show.id, 1, 1) is None


def test_state_and_progress(tmp_path):
    cat = Catalog(tmp_path / "c.db")
    cat.set_state("item", "7")
    cat.save_progress(3, 120, 6000)
    assert cat.get_state("item") == "7" and cat.progress(3) == (120, 6000)
    assert cat.get_state("nope") is None and cat.progress(99) is None


def test_rematch_once_fixes_wrong_ids_and_keeps_data_when_lookup_fails(tmp_path):
    from biblio import catalog as catalog_mod
    from biblio.db import Catalog
    from tests.fakes import settings_with
    s = settings_with(tmp_path, {"Library/Movies/All Quiet (2022).iso": b"x", "Library/Movies/Coda (2021).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")

    class Tmdb:
        calls = 0
        def find_movie(self, title, year):
            Tmdb.calls += 1
            return None if title == "Coda" else {"tmdb_id": 49046, "overview": "film"}
    catalog_mod.refresh(s, cat, None)           # scanned with no TMDb yet
    quiet, coda = sorted(cat.items("movies"), key=lambda i: i.title)
    cat.set_meta(quiet.id, 1086967, {"overview": "making-of"})   # wrong match from the old logic
    cat.set_meta(coda.id, 2, {"overview": "kept"})
    catalog_mod.refresh(s, cat, Tmdb())
    assert cat.get(quiet.id).tmdb_id == 49046 and cat.get(coda.id).meta["overview"] == "kept"
    n = Tmdb.calls
    catalog_mod.refresh(s, cat, Tmdb())         # rematch happens once only
    assert Tmdb.calls == n


def test_removed_title_drops_its_uploaded_art(tmp_path):
    from biblio import catalog as catalog_mod
    from biblio.db import Catalog
    from tests.fakes import settings_with
    s = settings_with(tmp_path, {"Library/Movies/Home Video.mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    catalog_mod.refresh(s, cat, None)
    it = cat.items("movies")[0]
    art = s.data_dir / "art" / f"item_{it.id}_poster"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_bytes(b"img")
    (s.media_root / it.relpath).unlink()
    catalog_mod.refresh(s, cat, None)
    assert not art.exists()
