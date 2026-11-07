import json
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from biblio.scan import Entry

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY, folder_id TEXT NOT NULL, relpath TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, year INTEGER, tmdb_id INTEGER, meta TEXT NOT NULL DEFAULT '{}',
  UNIQUE(folder_id, relpath));
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS progress (item_id INTEGER PRIMARY KEY, seconds INTEGER, total INTEGER);
CREATE TABLE IF NOT EXISTS episode_files (
  id INTEGER PRIMARY KEY, show_id INTEGER NOT NULL, relpath TEXT NOT NULL, kind TEXT NOT NULL,
  season INTEGER NOT NULL, episodes TEXT NOT NULL, UNIQUE(show_id, relpath));
CREATE TABLE IF NOT EXISTS season_meta (
  show_id INTEGER NOT NULL, season INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(show_id, season));
CREATE TABLE IF NOT EXISTS formats (item_id INTEGER PRIMARY KEY, sig TEXT NOT NULL, data TEXT NOT NULL);
"""


@dataclass
class EpisodeFileRow:
    id: int
    show_id: int
    relpath: str
    kind: str
    season: int
    episodes: list[int]


@dataclass
class Item:
    id: int
    folder_id: str
    relpath: str
    kind: str
    title: str
    year: int | None
    tmdb_id: int | None
    meta: dict = field(default_factory=dict)


class Catalog:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _write(self, sql, args=()):
        with self._lock, self._db:
            return self._db.execute(sql, args)

    def upsert_item(self, folder_id: str, e: Entry, title: str, year: int | None) -> int:
        self._write(
            "INSERT INTO items(folder_id, relpath, kind, title, year) VALUES (?,?,?,?,?) "
            "ON CONFLICT(folder_id, relpath) DO UPDATE SET kind=excluded.kind",
            (folder_id, e.relpath, e.kind, title, year))
        return self._db.execute("SELECT id FROM items WHERE folder_id=? AND relpath=?",
                                (folder_id, e.relpath)).fetchone()[0]

    def remove_missing(self, folder_id: str, keep: set[str]) -> list[int]:
        """Delete items no longer on disk, with their progress; returns the removed ids."""
        rows = self._db.execute("SELECT id, relpath FROM items WHERE folder_id=?", (folder_id,)).fetchall()
        removed = [item_id for item_id, rel in rows if rel not in keep]
        for item_id in removed:
            self._write("DELETE FROM items WHERE id=?", (item_id,))
            self._write("DELETE FROM progress WHERE item_id=?", (item_id,))
            self._write("DELETE FROM formats WHERE item_id=?", (item_id,))
        return removed

    def set_meta(self, item_id: int, tmdb_id: int | None, meta: dict) -> None:
        self._write("UPDATE items SET tmdb_id=?, meta=? WHERE id=?",
                    (tmdb_id, json.dumps(meta, ensure_ascii=False), item_id))

    def _item(self, row) -> Item:
        return Item(*row[:7], meta=json.loads(row[7]))

    def items(self, folder_id: str, offset: int = 0, limit: int = 1000) -> list[Item]:
        rows = self._db.execute(
            "SELECT id, folder_id, relpath, kind, title, year, tmdb_id, meta FROM items "
            "WHERE folder_id=? ORDER BY title COLLATE NOCASE, id LIMIT ? OFFSET ?",
            (folder_id, limit, offset)).fetchall()
        return [self._item(r) for r in rows]

    def count(self, folder_id: str) -> int:
        return self._db.execute("SELECT COUNT(*) FROM items WHERE folder_id=?", (folder_id,)).fetchone()[0]

    def get(self, item_id: int) -> Item | None:
        row = self._db.execute(
            "SELECT id, folder_id, relpath, kind, title, year, tmdb_id, meta FROM items WHERE id=?",
            (item_id,)).fetchone()
        return self._item(row) if row else None

    def item_by_path(self, relpath: str) -> Item | None:
        row = self._db.execute(
            "SELECT id, folder_id, relpath, kind, title, year, tmdb_id, meta FROM items WHERE relpath=?",
            (relpath,)).fetchone()
        return self._item(row) if row else None

    def items_by_tmdb(self, tmdb_id: int) -> list[Item]:
        """Every copy of a title (e.g. the 3D and the 4K HDR one share a TMDb id)."""
        rows = self._db.execute(
            "SELECT id, folder_id, relpath, kind, title, year, tmdb_id, meta FROM items WHERE tmdb_id=?",
            (tmdb_id,)).fetchall()
        return [self._item(r) for r in rows]

    def set_state(self, key: str, value: str) -> None:
        self._write("INSERT OR REPLACE INTO state(key, value) VALUES (?,?)", (key, value))

    def get_state(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def save_progress(self, item_id: int, seconds: int, total: int) -> None:
        self._write("INSERT OR REPLACE INTO progress(item_id, seconds, total) VALUES (?,?,?)",
                    (item_id, seconds, total))

    # --- series -------------------------------------------------------------
    # progress keys: item id for movies, -episode_file id for episodes

    def set_episode_files(self, show_id: int, files: list) -> None:
        keep = set()
        for f in files:
            keep.add(f.relpath)
            self._write(
                "INSERT INTO episode_files(show_id, relpath, kind, season, episodes) VALUES (?,?,?,?,?) "
                "ON CONFLICT(show_id, relpath) DO UPDATE SET kind=excluded.kind, season=excluded.season, "
                "episodes=excluded.episodes",
                (show_id, f.relpath, f.kind, f.season, ",".join(map(str, f.episodes))))
        for row_id, rel in self._db.execute("SELECT id, relpath FROM episode_files WHERE show_id=?",
                                            (show_id,)).fetchall():
            if rel not in keep:
                self._write("DELETE FROM episode_files WHERE id=?", (row_id,))
                self._write("DELETE FROM progress WHERE item_id=?", (-row_id,))
                self._write("DELETE FROM formats WHERE item_id=?", (-row_id,))

    def _ep_row(self, r) -> EpisodeFileRow:
        return EpisodeFileRow(r[0], r[1], r[2], r[3], r[4], [int(n) for n in r[5].split(",")])

    def episode_files(self, show_id: int) -> list[EpisodeFileRow]:
        rows = self._db.execute("SELECT id, show_id, relpath, kind, season, episodes FROM episode_files "
                                "WHERE show_id=? ORDER BY season, relpath", (show_id,)).fetchall()
        return [self._ep_row(r) for r in rows]

    def episode_file(self, ep_file_id: int) -> EpisodeFileRow | None:
        r = self._db.execute("SELECT id, show_id, relpath, kind, season, episodes FROM episode_files WHERE id=?",
                             (ep_file_id,)).fetchone()
        return self._ep_row(r) if r else None

    def season_format(self, show_id: int, season: int) -> dict | None:
        files = [f for f in self.episode_files(show_id) if f.season == season]
        from biblio import formats
        return formats.most_common([self.format(-f.id) for f in files])

    def seasons(self, show_id: int) -> list[int]:
        return [r[0] for r in self._db.execute(
            "SELECT DISTINCT season FROM episode_files WHERE show_id=? ORDER BY season", (show_id,))]

    def file_for(self, show_id: int, season: int, episode: int) -> EpisodeFileRow | None:
        return next((f for f in self.episode_files(show_id) if f.season == season and episode in f.episodes), None)

    def set_season_meta(self, show_id: int, season: int, episodes: list[dict]) -> None:
        self._write("INSERT OR REPLACE INTO season_meta(show_id, season, data) VALUES (?,?,?)",
                    (show_id, season, json.dumps(episodes, ensure_ascii=False)))

    def season_meta(self, show_id: int, season: int) -> list[dict] | None:
        r = self._db.execute("SELECT data FROM season_meta WHERE show_id=? AND season=?", (show_id, season)).fetchone()
        return json.loads(r[0]) if r else None

    def drop_show(self, show_id: int) -> None:
        for f in self.episode_files(show_id):
            self._write("DELETE FROM progress WHERE item_id=?", (-f.id,))
        self._write("DELETE FROM episode_files WHERE show_id=?", (show_id,))
        self._write("DELETE FROM season_meta WHERE show_id=?", (show_id,))

    # --- detected video/audio format (biblio.formats) --------------------------

    def set_format(self, item_id: int, sig: str, data: dict | None) -> None:
        """data None = probing failed; kept with its sig so the same file isn't retried every scan."""
        self._write("INSERT OR REPLACE INTO formats(item_id, sig, data) VALUES (?,?,?)",
                    (item_id, sig, json.dumps(data)))

    def format_sig(self, item_id: int) -> str | None:
        r = self._db.execute("SELECT sig FROM formats WHERE item_id=?", (item_id,)).fetchone()
        return r[0] if r else None

    def format(self, item_id: int) -> dict | None:
        r = self._db.execute("SELECT data FROM formats WHERE item_id=?", (item_id,)).fetchone()
        return json.loads(r[0]) if r else None

    def progress(self, item_id: int) -> tuple[int, int] | None:
        row = self._db.execute("SELECT seconds, total FROM progress WHERE item_id=?", (item_id,)).fetchone()
        return (row[0], row[1]) if row else None
