from pathlib import Path

from flask import Blueprint, Response, abort, current_app, request

from biblio import badges, formats, images
from biblio.config import load_folders
from biblio.proto import line, text

disc_bp = Blueprint("disc", __name__, url_prefix="/d")
STATIC_ICONS = Path(__file__).resolve().parent.parent / "static" / "icons"


def _ctx():
    return current_app.config["SETTINGS"], current_app.config["CATALOG"]


def _item():
    _, cat = _ctx()
    it = cat.get(request.args.get("id", type=int) or 0)
    return it or abort(404)


def _jpeg(data: bytes) -> Response:
    return Response(data, mimetype="image/jpeg")


@disc_bp.get("/folders")
def folders():
    s, cat = _ctx()
    return text([line(f.id, f.name, cat.count(f.id)) for f in load_folders(s.data_dir)])


@disc_bp.get("/items")
def items():
    _, cat = _ctx()
    folder = request.args.get("folder", "")
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 1000, type=int)
    rows = [line(it.id, it.title, it.year, it.kind) for it in cat.items(folder, offset, limit)]
    return text([str(cat.count(folder))] + rows)


@disc_bp.get("/item")
def item():
    s, cat = _ctx()
    it = _item()
    m = it.meta
    prog = cat.progress(it.id)
    resume = prog[0] if prog and it.kind == "file" else 0
    extra = []
    if it.kind == "series":
        seasons = cat.seasons(it.id)
        files = cat.episode_files(it.id)
        counts = [len({n for f in files if f.season == s for n in f.episodes}) for s in seasons]
        extra = [line("seasons", ",".join(map(str, seasons))),
                 line("season_counts", ",".join(map(str, counts)))]   # episodes on the NAS
    return text(extra + [
        line("title", it.title), line("year", it.year), line("rating", m.get("rating")),
        line("runtime", m.get("runtime_min")), line("certification", m.get("certification")),
        line("genres", ", ".join(m.get("genres", []))), line("director", m.get("director")),
        line("cast", ", ".join(m.get("cast", []))), line("overview", m.get("overview")),
        line("kind", it.kind), line("resume", resume),
        line("hascase", 1 if images.own_bytes(it, s.data_dir / "cache", "case") is not None else 0),
        line("badges", ",".join(formats.badges(cat.format(it.id)))),
    ])


@disc_bp.get("/img/poster")
def poster():
    s, _ = _ctx()
    w = min(request.args.get("w", 150, type=int), 600)
    h = min(request.args.get("h", 225, type=int), 900)
    return _jpeg(images.poster_jpeg(_item(), s.data_dir / "cache", w, h, current_app.config["FETCH"]))


@disc_bp.get("/img/case")
def case():
    """The poster inside a Blu-ray case, transparent PNG (detail pages)."""
    s, _ = _ctx()
    w = min(request.args.get("w", 260, type=int), 600)
    h = min(request.args.get("h", 370, type=int), 900)
    return Response(images.case_png(_item(), s.data_dir / "cache", w, h, current_app.config["FETCH"]),
                    mimetype="image/png")


@disc_bp.get("/img/badges")
def badge_strip():
    """The title's format badges in a row (Badger "Elite" template): ?id=&h=36&w=600, PNG, 404 if none."""
    s, cat = _ctx()
    it = _item()
    h = max(12, min(request.args.get("h", 36, type=int), 120))
    w = max(h, min(request.args.get("w", 600, type=int), 1280))
    season = request.args.get("season", type=int)
    fmt = cat.season_format(it.id, season) if season is not None else cat.format(it.id)
    url = badges.style(cat.get_state("badge_style"))["url"]   # the style picked in Artwork Studio
    img = badges.strip(fmt, s.data_dir / "badges", h, w, current_app.config["FETCH"], url)
    if img is None:
        abort(404)
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@disc_bp.get("/img/disc")
def disc():
    """Pre-rotated disc frames (sprite sheet) that slide out of the case; 404 without a case."""
    s, _ = _ctx()
    size = min(max(request.args.get("size", 260, type=int), 40), 400)
    frames = min(max(request.args.get("frames", 48, type=int), 1), 72)
    data = images.disc_png(_item(), s.data_dir / "cache", size, frames, current_app.config["FETCH"])
    return Response(data, mimetype="image/png") if data else abort(404)


@disc_bp.get("/img/logo")
def logo():
    """Transparent PNG title logo; 404 when there is none (the disc then shows the title)."""
    s, _ = _ctx()
    w = min(request.args.get("w", 500, type=int), 800)
    h = min(request.args.get("h", 140, type=int), 300)
    data = images.logo_png(_item(), s.data_dir / "cache", w, h, current_app.config["LOGOS"],
                           current_app.config["FETCH"])
    return Response(data, mimetype="image/png") if data else abort(404)


@disc_bp.get("/img/backdrop")
def backdrop():
    s, _ = _ctx()
    return _jpeg(images.backdrop_jpeg(_item(), s.data_dir / "cache", current_app.config["FETCH"]))


@disc_bp.get("/img/icon")
def icon():
    s, _ = _ctx()
    fid = request.args.get("folder", "")
    folder = next((f for f in load_folders(s.data_dir) if f.id == fid), None) or abort(404)
    custom = s.data_dir / "icons" / f"{folder.id}.png"
    path = custom if custom.exists() else STATIC_ICONS / folder.icon
    return _jpeg(images.icon_jpeg(path, 48, request.args.get("sel") == "1"))


@disc_bp.get("/episodes")
def episodes():
    """One line per episode of a season: number, title, air_date, ep_file_id (0 = not on disk),
    resume seconds, overview. TMDb list when known, otherwise the episodes found on disk."""
    _, cat = _ctx()
    it = _item()
    season = request.args.get("season", 0, type=int)
    on_disk = {n for f in cat.episode_files(it.id) if f.season == season for n in f.episodes}
    meta = cat.season_meta(it.id, season) or []
    # TMDb's list plus anything on disk it doesn't know (new episodes, other numbering)
    known = {ep["number"] for ep in meta}
    meta = sorted(meta + [{"number": n, "title": f"Episodio {n}", "air_date": "", "overview": ""}
                          for n in on_disk - known], key=lambda ep: ep["number"])
    rows = []
    for ep in meta:
        f = cat.file_for(it.id, season, ep["number"])
        prog = cat.progress(-f.id) if f and f.kind == "file" else None
        rows.append(line(ep["number"], ep.get("title") or f"Episodio {ep['number']}", ep.get("air_date"),
                         f.id if f else 0, prog[0] if prog else 0, ep.get("overview")))
    return text(rows)


@disc_bp.get("/img/season")
def season_poster():
    s, _ = _ctx()
    w = min(request.args.get("w", 140, type=int), 400)
    h = min(request.args.get("h", 210, type=int), 600)
    return _jpeg(images.season_jpeg(_item(), request.args.get("season", 0, type=int), s.data_dir / "cache", w, h,
                                    current_app.config["FETCH"]))


@disc_bp.get("/img/still")
def still():
    s, cat = _ctx()
    it = _item()
    season, number = request.args.get("season", 0, type=int), request.args.get("episode", 0, type=int)
    w = min(request.args.get("w", 240, type=int), 600)
    h = min(request.args.get("h", 135, type=int), 400)
    ep = next((e for e in cat.season_meta(it.id, season) or [] if e["number"] == number), {})
    return _jpeg(images.still_jpeg(it.id, season, number, ep.get("still_path"), s.data_dir / "cache", w, h,
                                   current_app.config["FETCH"]))


@disc_bp.get("/play")
def play():
    player = current_app.config["PLAYER"]
    resume = request.args.get("resume") == "1"
    if "ep" in request.args:
        _, cat = _ctx()
        ep_id = request.args.get("ep", 0, type=int)
        if cat.episode_file(ep_id) is None:
            abort(404)
        if player is None:
            return text([line("error", "reproductor no configurado")])
        r = player.play_episode(ep_id, resume)
    else:
        it = _item()
        if player is None:
            return text([line("error", "reproductor no configurado")])
        r = player.play(it.id, resume)
    return text([line("error", r[6:]) if r.startswith("error:") else r])


@disc_bp.get("/state")
def state():
    _, cat = _ctx()
    return text([line(k, v) for k in ("folder", "item") if (v := cat.get_state(k))])


@disc_bp.get("/select")
def select():
    _, cat = _ctx()
    for k in ("folder", "item"):
        if request.args.get(k):
            cat.set_state(k, request.args[k])
    return Response("ok", mimetype="text/plain")
