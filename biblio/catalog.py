import logging

from biblio import formats
from biblio.config import Settings, load_folders
from biblio.db import Catalog
from biblio.images import forget
from biblio.names import parse_name
from biblio.scan import Entry, scan_folder, scan_series

log = logging.getLogger("biblioteca.catalog")


MATCH_VERSION = "3"   # bump to look every title up again in TMDb (e.g. after fixing the matching)


def refresh(settings: Settings, cat: Catalog, tmdb) -> dict[str, int]:
    """Scan the configured folders and enrich new items from TMDb."""
    counts = {}
    rematch = bool(tmdb) and cat.get_state("tmdb_match") != MATCH_VERSION
    for folder in load_folders(settings.data_dir):
        if folder.kind == "series":
            _refresh_series(settings, cat, tmdb, folder, rematch)
        else:
            _refresh_movies(settings, cat, tmdb, folder, rematch)
        counts[folder.id] = cat.count(folder.id)
    if rematch:
        cat.set_state("tmdb_match", MATCH_VERSION)
    detect_formats(settings, cat)
    return counts


def detect_formats(settings: Settings, cat: Catalog) -> None:
    """Probe titles that are new or whose file changed. Slow (seconds per ISO), so it runs last."""
    if not formats.tools()[0]:
        log.warning("formatos: ffprobe no está instalado, no se detectan")
        return
    done = 0

    def probe_one(key: int, relpath: str, kind: str) -> None:
        nonlocal done
        try:
            sig = formats.signature(settings.media_root, relpath)
        except OSError:
            return
        if cat.format_sig(key) == sig:
            return
        try:
            data = formats.probe(settings.media_root, relpath, kind)
        except Exception as e:
            log.warning("formatos: %s: %s", relpath, e)
            data = None
        if cat.format(key) != data:
            forget(settings.data_dir / "cache", key)
        cat.set_format(key, sig, data)
        done += 1

    for folder in load_folders(settings.data_dir):
        if folder.kind == "series":
            for it in cat.items(folder.id):
                for f in cat.episode_files(it.id):
                    probe_one(-f.id, f.relpath, f.kind)   # episode format keyed by -id
        else:
            for it in cat.items(folder.id):
                probe_one(it.id, it.relpath, it.kind)
    if done:
        log.info("formatos: %d títulos analizados", done)


def _drop(settings: Settings, cat: Catalog, folder_id: str, keep: set[str]) -> None:
    for item_id in cat.remove_missing(folder_id, keep):
        cat.drop_show(item_id)
        forget(settings.data_dir / "cache", item_id)
        # art uploaded for a title TMDb didn't know is keyed by this id, which SQLite may reuse
        for f in (settings.data_dir / "art").glob(f"item_{item_id}_*"):
            f.unlink(missing_ok=True)


def _lookup(settings, cat, it, find, rematch: bool):
    """TMDb data for a new item, or again for every item on a rematch; keeps the old data if the
    lookup fails. Returns the item as stored."""
    if it.meta.get("locked") or (it.tmdb_id is not None and not rematch):
        return it   # picked by hand in Artwork Studio: never searched again
    meta = find(it.title, it.year)
    if meta:
        tmdb_id = meta.pop("tmdb_id")
        if it.tmdb_id not in (None, tmdb_id):
            log.info("TMDb: %s cambia de %s a %s", it.relpath, it.tmdb_id, tmdb_id)
            forget(settings.data_dir / "cache", it.id)   # poster/backdrop/logo of the wrong film
        cat.set_meta(it.id, tmdb_id, meta)
        return cat.get(it.id)
    return it


def set_match(settings: Settings, cat: Catalog, it, meta: dict) -> None:
    """A TMDb match picked by hand (Artwork Studio): stored locked, so no automatic search
    replaces it, with the old film's cached images and episode titles dropped."""
    tmdb_id = meta.pop("tmdb_id")
    changed = it.tmdb_id != tmdb_id
    cat.set_meta(it.id, tmdb_id, {**meta, "locked": True})
    if changed:
        forget(settings.data_dir / "cache", it.id)
        for season in cat.seasons(it.id):
            cat.set_season_meta(it.id, season, [])


def _refresh_movies(settings, cat, tmdb, folder, rematch=False) -> None:
    entries = scan_folder(settings.media_root, folder.path)
    if entries is None:   # folder not reachable: keep what we have
        return
    for e in entries:
        title, year = parse_name(e.stem)
        cat.upsert_item(folder.id, e, title, year)
    _drop(settings, cat, folder.id, {e.relpath for e in entries})
    if tmdb:
        for it in cat.items(folder.id):
            _lookup(settings, cat, it, tmdb.find_movie, rematch)


def _refresh_series(settings, cat, tmdb, folder, rematch=False) -> None:
    shows = scan_series(settings.media_root, folder.path)
    if shows is None:
        return
    for show in shows:
        title, year = parse_name(show.name)
        show_id = cat.upsert_item(folder.id, Entry(show.relpath, show.name, "series"), title, year)
        cat.set_episode_files(show_id, show.files)
        for rel in show.skipped:
            log.info("serie: archivo sin código SxxEyy, ignorado: %s", rel)
    _drop(settings, cat, folder.id, {s.relpath for s in shows})
    if not tmdb:
        return
    for it in cat.items(folder.id):
        old = it.tmdb_id
        it = _lookup(settings, cat, it, tmdb.find_tv, rematch)
        if old not in (None, it.tmdb_id):
            for season in cat.seasons(it.id):    # episode titles of the other show
                cat.set_season_meta(it.id, season, [])
        if it.tmdb_id is None:
            continue
        if "season_posters" not in it.meta:
            details = tmdb.tv(it.tmdb_id)
            if details:
                cat.set_meta(it.id, it.tmdb_id, {**it.meta, "season_posters": details["season_posters"]})
                it = cat.get(it.id)
        for season in cat.seasons(it.id):
            cached = cat.season_meta(it.id, season)
            on_disk = max(n for f in cat.episode_files(it.id) if f.season == season for n in f.episodes)
            # fetch once, and again when the disk has episodes newer than what was cached
            if cached is None or on_disk > max((ep["number"] for ep in cached), default=0):
                episodes = tmdb.season(it.tmdb_id, season)
                if episodes:
                    cat.set_season_meta(it.id, season, episodes)
