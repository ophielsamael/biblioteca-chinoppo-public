from collections.abc import Callable

import requests

API = "https://api.themoviedb.org/3"


def _http_get(path: str, params: dict) -> dict:
    r = requests.get(API + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _norm(t: str) -> str:
    return "".join(c for c in t.casefold() if c.isalnum())


def _best(results: list[dict], title: str, year: int | None) -> int:
    """Pick among the first hits, not just the first one (seen 2026-11-04):
    - TMDb's year filter lets other years through ("Mulan" 2020 -> the 1998 film first): keep the
      hits within a year of the file's (files are often a year off: "300 (2006)" is 2007 on TMDb);
    - drop hits with under a tenth of the best one's votes (making-ofs, fan videos);
    - then the title closest to the file's, then the most voted ("Chicago" vs "The Trial of the
      Chicago 7"; "Deathly Hallows Part 2" vs "Part 1")."""
    from difflib import SequenceMatcher
    top = results[:5]
    def yr(r):
        d = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        return int(d) if d.isdigit() else None
    near = [r for r in top if year and yr(r) is not None and abs(yr(r) - year) <= 1] or top
    votes = lambda r: r.get("vote_count") or 0
    keep = [r for r in near if votes(r) * 10 >= max(map(votes, near))]
    q = _norm(title)
    def sim(r):
        names = [r.get(k) or "" for k in ("title", "original_title", "name", "original_name")]
        return round(max(SequenceMatcher(None, q, _norm(n)).ratio() for n in names), 2)
    return max(keep, key=lambda r: (sim(r), votes(r)))["id"]


class TmdbClient:
    def __init__(self, key: str, get: Callable[[str, dict], dict] = _http_get):
        self.key = key
        self._get = get

    def _q(self, path: str, **params) -> dict:
        return self._get(path, {"api_key": self.key, **params})

    def find_movie(self, title: str, year: int | None) -> dict | None:
        try:
            params = {"query": title, "language": "es-ES"}
            results = self._q("/search/movie", **params, **({"year": year} if year else {}))["results"]
            if not results and year:
                results = self._q("/search/movie", **params)["results"]
            if not results:
                return None
            return self.movie(_best(results, title, year))
        except Exception:
            return None

    def movie(self, mid: int) -> dict | None:
        """One film by TMDb id (the search above, or the one picked by hand in Artwork Studio)."""
        try:
            d = self._q(f"/movie/{mid}", language="es-ES", append_to_response="credits,release_dates")
            overview = d.get("overview") or self._q(f"/movie/{mid}", language="en-US").get("overview", "")
            crew = d.get("credits", {}).get("crew", [])
            return {
                "tmdb_id": mid,
                "overview": overview,
                "rating": round(d.get("vote_average") or 0, 1),
                "runtime_min": d.get("runtime") or 0,
                "certification": _certification(d.get("release_dates", {}).get("results", [])),
                "genres": [g["name"] for g in d.get("genres", [])],
                "director": next((c["name"] for c in crew if c.get("job") == "Director"), ""),
                "cast": [c["name"] for c in d.get("credits", {}).get("cast", [])[:5]],
                "poster_path": d.get("poster_path"),
                "backdrop_path": d.get("backdrop_path"),
            }
        except Exception:
            return None


    def find_tv(self, title: str, year: int | None) -> dict | None:
        try:
            params = {"query": title, "language": "es-ES"}
            results = self._q("/search/tv", **params, **({"first_air_date_year": year} if year else {}))["results"]
            if not results and year:
                results = self._q("/search/tv", **params)["results"]
            if not results:
                return None
            return self.tv(_best(results, title, year))
        except Exception:
            return None

    def tv(self, tid: int) -> dict | None:
        """One series by TMDb id."""
        try:
            d = self._q(f"/tv/{tid}", language="es-ES", append_to_response="credits,content_ratings")
            overview = d.get("overview") or self._q(f"/tv/{tid}", language="en-US").get("overview", "")
            ratings = {r["iso_3166_1"]: r.get("rating", "") for r in d.get("content_ratings", {}).get("results", [])}
            runtimes = d.get("episode_run_time") or [0]
            return {
                "tmdb_id": tid,
                "overview": overview,
                "rating": round(d.get("vote_average") or 0, 1),
                "runtime_min": runtimes[0],
                "certification": ratings.get("ES") or ratings.get("US") or "",
                "genres": [g["name"] for g in d.get("genres", [])],
                "director": ", ".join(c["name"] for c in d.get("created_by", [])),
                "cast": [c["name"] for c in d.get("credits", {}).get("cast", [])[:5]],
                "poster_path": d.get("poster_path"),
                "backdrop_path": d.get("backdrop_path"),
                # JSON keys are strings: {"1": "/abc.jpg", ...}
                "season_posters": {str(x["season_number"]): x.get("poster_path")
                                   for x in d.get("seasons", []) if x.get("season_number") is not None},
            }
        except Exception:
            return None

    def logo_path(self, kind: str, tmdb_id: int) -> str | None:
        """Title logo (transparent PNG) for "movie" or "tv": Spanish first, then English, then
        language-less ones. SVG logos are skipped (the disc can't draw them)."""
        d = self._q(f"/{kind}/{tmdb_id}/images", include_image_language="es,en,null")
        rank = {"es": 0, "en": 1, None: 2}
        logos = [l for l in d.get("logos", []) if (l.get("file_path") or "").endswith(".png")]
        logos.sort(key=lambda l: (rank.get(l.get("iso_639_1"), 3), -(l.get("vote_average") or 0)))
        return logos[0]["file_path"] if logos else None

    def season(self, tv_id: int, season: int) -> list[dict] | None:
        try:
            es = self._q(f"/tv/{tv_id}/season/{season}", language="es-ES")["episodes"]
            en = None
            out = []
            for ep in es:
                title = ep.get("name") or ""
                if not title:
                    en = en or {e["episode_number"]: e for e in
                                self._q(f"/tv/{tv_id}/season/{season}", language="en-US")["episodes"]}
                    title = en.get(ep["episode_number"], {}).get("name", "")
                out.append({"number": ep["episode_number"], "title": title, "air_date": ep.get("air_date") or "",
                            "overview": ep.get("overview") or "", "still_path": ep.get("still_path")})
            return out
        except Exception:
            return None


def _certification(results: list) -> str:
    by_country = {r["iso_3166_1"]: r.get("release_dates", []) for r in results}
    for country in ("ES", "US"):
        for rd in by_country.get(country, []):
            if rd.get("certification"):
                return rd["certification"]
    return ""
