import logging
import os
import threading
from collections import deque

from flask import Flask, Response

from biblio.catalog import refresh
from biblio.chinoppo import Chinoppo
from biblio.player import Player
from biblio.config import Settings, load_folders, load_settings
from biblio.db import Catalog
from biblio.disc_api import disc_bp
from biblio.images import http_fetch
from biblio.tmdb import TmdbClient
from biblio.web import web_bp

log = logging.getLogger("biblioteca")
log.setLevel(logging.INFO)
LOG_LINES: deque[str] = deque(maxlen=300)


class _Ring(logging.Handler):
    def emit(self, record):
        LOG_LINES.append(self.format(record))


_ring = _Ring()
_ring.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
log.addHandler(_ring)


def create_app(settings: Settings, catalog: Catalog, player=None, fetch=http_fetch, logos=None,
               tmdb=None) -> Flask:
    app = Flask(__name__)
    if tmdb is None and settings.tmdb_key:
        tmdb = TmdbClient(settings.tmdb_key)
    if logos is None and settings.tmdb_key:
        logos = TmdbClient(settings.tmdb_key).logo_path
    app.config.update(SETTINGS=settings, CATALOG=catalog, PLAYER=player, FETCH=fetch, LOGOS=logos, TMDB=tmdb,
                      RESCAN=lambda: start_refresh(settings, catalog, app))
    app.register_blueprint(disc_bp)
    app.register_blueprint(web_bp)
    # the service's own log, readable without a shell on the homelab
    app.add_url_rule("/log", "log", lambda: Response("\n".join(LOG_LINES), mimetype="text/plain; charset=utf-8"))
    return app


# What the disc asks for when it opens a title (sizes as in Wall.java / Detail.java / SeriesDetail.java)
WARM_MOVIE = ("/d/img/poster?id={id}&w=150&h=225", "/d/img/backdrop?id={id}", "/d/img/logo?id={id}&w=500&h=140",
              "/d/img/badges?id={id}&h=30&w=790", "/d/img/case?id={id}&w=240&h=350",
              "/d/img/disc?id={id}&size=240&frames=1")
WARM_SERIES = ("/d/img/poster?id={id}&w=150&h=225", "/d/img/backdrop?id={id}", "/d/img/logo?id={id}&w=420&h=80",
               "/d/img/case?id={id}&w=200&h=290")


def warm(app: Flask, catalog: Catalog) -> int:
    """Make every title's page images once, in the background: opening a title on the Chinoppo
    then only reads cached files (first visits took ~0.5 s, the page showed a black screen)."""
    n = 0
    with app.test_client() as c:
        for folder in load_folders(app.config["SETTINGS"].data_dir):
            for it in catalog.items(folder.id):
                for url in WARM_SERIES if it.kind == "series" else WARM_MOVIE:
                    c.get(url.format(id=it.id))
                if it.kind == "series":
                    for season in catalog.seasons(it.id):
                        c.get(f"/d/img/season?id={it.id}&season={season}&w=140&h=210")
                        c.get(f"/d/img/season?id={it.id}&season={season}&w=180&h=270")
                        c.get(f"/d/img/badges?id={it.id}&season={season}&h=28&w=680")
                n += 1
    return n


def start_refresh(settings: Settings, catalog: Catalog, app: Flask | None = None) -> threading.Thread:
    tmdb = TmdbClient(settings.tmdb_key) if settings.tmdb_key else None
    def run():
        try:
            log.info("refresh: %s", refresh(settings, catalog, tmdb))
            if app is not None:
                log.info("imágenes preparadas: %d títulos", warm(app, catalog))
        except Exception:
            log.exception("refresh failed")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings(os.environ)
    catalog = Catalog(settings.data_dir / "catalog.db")
    player = Player(settings, catalog, Chinoppo(settings.chinoppo_ip))
    app = create_app(settings, catalog, player=player)
    start_refresh(settings, catalog, app)
    threading.Thread(target=player.watch_forever, daemon=True).start()
    app.run(host="0.0.0.0", port=settings.port, threaded=True)


if __name__ == "__main__":
    main()
