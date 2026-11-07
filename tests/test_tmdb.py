from biblio.tmdb import TmdbClient


def fake_get(calls):
    def get(path, params):
        calls.append((path, dict(params)))
        if path == "/search/movie":
            return {"results": [] if "year" in params else [{"id": 9}]}
        if params["language"] == "en-US":
            return {"overview": "English text"}
        return {"overview": "", "vote_average": 7.66, "runtime": 100, "genres": [{"name": "Drama"}],
                "credits": {"crew": [{"job": "Director", "name": "D"}], "cast": [{"name": "A"}]},
                "release_dates": {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "R"}]}]}}
    return get


def test_retries_without_year_and_falls_back_to_english():
    calls = []
    m = TmdbClient("k", fake_get(calls)).find_movie("X", 2001)
    assert [c[0] for c in calls[:2]] == ["/search/movie", "/search/movie"]
    assert m["overview"] == "English text" and m["certification"] == "R" and m["rating"] == 7.7
    assert m["director"] == "D" and m["tmdb_id"] == 9


def test_find_tv_uses_creators_and_episode_runtime():
    def get(path, params):
        if path == "/search/tv":
            return {"results": [{"id": 5}]}
        return {"overview": "Serie", "vote_average": 8.0, "episode_run_time": [55], "genres": [],
                "created_by": [{"name": "A"}, {"name": "B"}], "credits": {"cast": []},
                "content_ratings": {"results": [{"iso_3166_1": "ES", "rating": "18"}]}}
    m = TmdbClient("k", get).find_tv("X", None)
    assert m["tmdb_id"] == 5 and m["director"] == "A, B" and m["runtime_min"] == 55
    assert m["certification"] == "18"


def test_season_titles_fall_back_to_english():
    def get(path, params):
        title = "" if params["language"] == "es-ES" else "Winter Is Coming"
        return {"episodes": [{"episode_number": 1, "name": title, "air_date": "2011-04-17",
                              "overview": "x", "still_path": "/s.jpg"}]}
    eps = TmdbClient("k", get).season(1399, 1)
    assert eps == [{"number": 1, "title": "Winter Is Coming", "air_date": "2011-04-17",
                    "overview": "x", "still_path": "/s.jpg"}]


def test_network_error_returns_none():
    def boom(path, params):
        raise OSError("offline")
    assert TmdbClient("k", boom).find_movie("X", None) is None


def test_logo_prefers_spanish_png_and_skips_svg():
    def get(path, params):
        assert path == "/movie/9/images" and "es" in params["include_image_language"]
        return {"logos": [{"file_path": "/en.png", "iso_639_1": "en", "vote_average": 9},
                          {"file_path": "/es.svg", "iso_639_1": "es", "vote_average": 9},
                          {"file_path": "/es.png", "iso_639_1": "es", "vote_average": 1}]}
    assert TmdbClient("k", get).logo_path("movie", 9) == "/es.png"


def test_logo_none_when_only_svg():
    assert TmdbClient("k", lambda p, q: {"logos": [{"file_path": "/a.svg", "iso_639_1": "en"}]}) \
        .logo_path("tv", 5) is None


def test_picks_the_most_voted_hit_not_a_making_of():
    def get(path, params):
        if path == "/search/movie":
            return {"results": [{"id": 1086967, "vote_count": 17}, {"id": 49046, "vote_count": 5043}]}
        return {"overview": "x", "credits": {}, "release_dates": {}}
    assert TmdbClient("k", get).find_movie("all quiet on the western front", 2022)["tmdb_id"] == 49046


def test_same_year_wins_over_a_more_voted_sequel():
    def get(path, params):
        if path == "/search/movie":
            return {"results": [{"id": 1087192, "release_date": "2025-06-06", "vote_count": 3223},
                                {"id": 82702, "release_date": "2014-06-05", "vote_count": 10785},
                                {"id": 1494489, "release_date": "2025-06-06", "vote_count": 4}]}
        return {"overview": "x", "credits": {}, "release_dates": {}}
    assert TmdbClient("k", get).find_movie("how to train your dragon", 2025)["tmdb_id"] == 1087192


def _pick(results, title, year):
    from biblio.tmdb import _best
    return _best(results, title, year)


def test_year_off_by_one_and_closest_title():
    assert _pick([{"id": 1, "title": "300", "release_date": "2007-03-07", "vote_count": 15251},
                  {"id": 2, "title": "Video 3000", "release_date": "2006-01-01", "vote_count": 1}], "300", 2006) == 1
    assert _pick([{"id": 7, "title": "El juicio de los 7 de Chicago", "original_title": "The Trial of the Chicago 7",
                   "release_date": "2020-09-25", "vote_count": 3495},
                  {"id": 8, "title": "Chicago", "release_date": "2002-12-10", "vote_count": 3025}], "Chicago", None) == 8
    assert _pick([{"id": 1, "original_title": "Harry Potter and the Deathly Hallows: Part 1", "release_date": "2010-11-17",
                   "vote_count": 21011},
                  {"id": 2, "original_title": "Harry Potter and the Deathly Hallows: Part 2", "release_date": "2011-07-12",
                   "vote_count": 22693}], "Harry Potter and the Deathly Hallows Part 2", 2011) == 2
    assert _pick([{"id": 98, "title": "Mulán", "release_date": "1998-06-18", "vote_count": 10784},
                  {"id": 20, "title": "Mulán", "release_date": "2020-09-04", "vote_count": 7204}], "Mulan", 2020) == 20
