import pytest

from biblio.db import Catalog
from biblio.scan import Entry
from tests.fakes import settings_with


def _offline(url):
    raise OSError("offline in tests")


@pytest.fixture
def settings(tmp_path):
    return settings_with(tmp_path, {})


@pytest.fixture
def catalog(tmp_path):
    cat = Catalog(tmp_path / "c.db")
    otto = cat.upsert_item("movies", Entry("Library/Movies/A Man Called Otto (2022).mkv",
                                           "A Man Called Otto (2022)", "file"), "A Man Called Otto", 2022)
    cat.set_meta(otto, 937278, {"director": "Marc Forster", "genres": ["Comedia", "Drama"],
                                "cast": ["Tom Hanks"], "overview": "Otto…", "rating": 7.5,
                                "runtime_min": 126, "certification": "12",
                                "poster_path": None, "backdrop_path": None})
    cat.upsert_item("movies", Entry("Library/Movies/Coda (2021).mkv", "Coda (2021)", "file"), "Coda", 2021)
    return cat


@pytest.fixture
def show_id(catalog):
    """The Last of Us with season 2 on disk (two multi-episode ISOs) and TMDb data for 7 episodes."""
    from biblio.scan import EpisodeFile
    sid = catalog.upsert_item("series", Entry("Library/SERIES/The Last of Us", "The Last of Us", "series"),
                              "The Last of Us", None)
    catalog.set_meta(sid, 100088, {"overview": "x", "genres": [], "cast": [], "poster_path": None,
                                   "backdrop_path": None})
    base = "Library/SERIES/The Last of Us/S02/"
    catalog.set_episode_files(sid, [EpisodeFile(base + "S02E01e02e03.iso", "iso", 2, [1, 2, 3]),
                                    EpisodeFile(base + "S02E04e05.iso", "iso", 2, [4, 5])])
    catalog.set_season_meta(sid, 2, [{"number": n, "title": f"Capítulo {n}", "air_date": "2025-04-13",
                                      "overview": "o", "still_path": None} for n in range(1, 8)])
    return sid


@pytest.fixture
def otto_id(catalog):
    return catalog.items("movies")[0].id


@pytest.fixture
def coda_id(catalog):
    return catalog.items("movies")[1].id


@pytest.fixture
def app(settings, catalog):
    from app import create_app
    return create_app(settings, catalog, fetch=_offline)


@pytest.fixture
def client(app):
    return app.test_client()
