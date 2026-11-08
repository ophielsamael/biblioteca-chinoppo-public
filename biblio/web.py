import io
import re
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, redirect, render_template, request
from PIL import Image, ImageOps

from biblio import badges, formats, images, usbpack
from biblio.config import Folder, load_folders, save_folders

web_bp = Blueprint("web", __name__)
STATIC_ICONS = Path(__file__).resolve().parent.parent / "static" / "icons"
_ID = re.compile(r"^[a-z0-9_-]{1,32}$")


@web_bp.get("/")
def index():
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    folders = [(f, cat.count(f.id)) for f in load_folders(s.data_dir)]
    gallery = sorted(p.name for p in STATIC_ICONS.glob("*.png"))
    return render_template("folders.html", folders=folders, gallery=gallery,
                           autoopen=cat.get_state("autoopen") != "0",
                           service_url=_service_url(), chinoppo_ip=s.chinoppo_ip,
                           no_key=not s.tmdb_key, media_problem=_media_problem(Path(s.media_root)))


def _media_problem(root: Path) -> str:
    """'' when the NAS folder is readable, else what the page should warn about."""
    try:
        return "" if any(root.iterdir()) else "empty"
    except PermissionError:
        return "forbidden"
    except OSError:
        return "empty"


def _service_url() -> str:
    """This service as the player must reach it: the host the browser used, as an IP."""
    import socket
    host = request.host.rsplit(":", 1)[0].strip("[]")
    try:
        host = socket.gethostbyname(host)
    except OSError:
        pass
    return f"http://{host}:{current_app.config['SETTINGS'].port}"


@web_bp.get("/api/badge-styles")
def badge_styles():
    """Badge styles for Artwork Studio: id, name, author, which one is in use."""
    cur = badges.style(current_app.config["CATALOG"].get_state("badge_style"))["id"]
    return [{"id": st["id"], "name": st["name"], "author": st["author"], "own": st["url"] is None,
             "selected": st["id"] == cur} for st in badges.STYLES]


@web_bp.get("/api/badge-styles/<sid>.png")
def badge_style_preview(sid):
    """A sample strip (4K · Remux · DV · HDR10 · TrueHD · Atmos · 7.1) in that style."""
    s = current_app.config["SETTINGS"]
    st = badges.style(sid)
    if st["id"] != sid:
        abort(404)
    img = badges.strip(badges.SAMPLE, s.data_dir / "badges", 36, 900, current_app.config["FETCH"], st["url"])
    if img is None:
        abort(502, "No se pudo descargar ese estilo")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), mimetype="image/png", headers={"Cache-Control": "max-age=3600"})


@web_bp.post("/api/badge-style")
def set_badge_style():
    """Use this style for every title, after keeping a full copy of it on this NAS."""
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    sid = (request.get_json(silent=True) or {}).get("id") or request.form.get("id", "")
    st = badges.style(sid)
    if st["id"] != sid:
        abort(400)
    try:
        saved = badges.snapshot(sid, s.data_dir / "badges", current_app.config["FETCH"])
    except Exception:
        abort(502, "No se pudo descargar ese estilo")
    cat.set_state("badge_style", sid)
    return {"ok": True, "id": sid, "saved": saved}


@web_bp.get("/preview")
def preview():
    """The disc's screens drawn in the browser (same /d/ API): to look at, and for screenshots."""
    return render_template("preview.html")


@web_bp.get("/usb.zip")
def usb_zip():
    s = current_app.config["SETTINGS"]
    url = _service_url()
    if url.split("//")[1].startswith("127."):
        abort(400, "Abre esta página con la IP del servidor (no localhost) y vuelve a descargar.")
    data = usbpack.build_zip(url, s.chinoppo_ip)
    return Response(data, mimetype="application/zip",
                    headers={"Content-Disposition": "attachment; filename=Biblioteca-USB.zip"})


@web_bp.post("/settings")
def settings():
    cat = current_app.config["CATALOG"]
    cat.set_state("autoopen", "1" if request.form.get("autoopen") else "0")
    return redirect("/")


@web_bp.route("/art/<kind>", methods=["POST", "DELETE"])
def art(kind):
    """Artwork Studio sends the poster / backdrop / logo it applied to Emby here too, as the
    raw image body: POST /art/poster?tmdb=603&media=movie. It replaces TMDb's for every copy
    of that title, from the next request on. "case" is the Blu-ray / 4K box for the detail
    page only. DELETE drops ours (back to TMDb's, or to no case). season<N> is a series' season poster.
    A title TMDb doesn't know goes by its catalog id instead: POST /art/poster?item=42."""
    if not images.art_kind_ok(kind):
        abort(404)
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    cache = s.data_dir / "cache"
    item_id = request.args.get("item", type=int)
    if item_id:
        it = cat.get(item_id) or abort(404)
        media, tmdb_id = "item", it.id
        hits = [it]
    else:
        tmdb_id, media = request.args.get("tmdb", type=int), request.args.get("media", "movie")
        if not tmdb_id or media not in ("movie", "tv"):
            abort(400)
        hits = [it for it in cat.items_by_tmdb(tmdb_id) if (it.kind == "series") == (media == "tv")]
    if request.method == "DELETE":
        images.drop_own(cache, media, tmdb_id, kind)
    else:
        data = request.get_data()
        if not data or len(data) > 30 * 1024 * 1024:
            abort(400)
        try:
            images.save_own(cache, media, tmdb_id, kind, data)
        except Exception:
            abort(400)
    for it in hits:
        images.forget(cache, it.id)   # their cached sizes were made from the old image
    return f"ok {len(hits)}"


# --- JSON for Artwork Studio: it edits the Biblioteca's own catalog, not Emby's ------------

@web_bp.get("/api/folders")
def api_folders():
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    return [{"id": f.id, "name": f.name, "kind": f.kind, "count": cat.count(f.id)} for f in load_folders(s.data_dir)]


@web_bp.get("/api/items")
def api_items():
    cat = current_app.config["CATALOG"]
    return [{"id": it.id, "title": it.title, "year": it.year, "tmdb_id": it.tmdb_id, "path": it.relpath,
             "media": "tv" if it.kind == "series" else "movie", "genres": it.meta.get("genres", []),
             "rating": it.meta.get("rating"), "badges": formats.badges(cat.format(it.id)),
             "format": cat.format(it.id),   # raw fields, so Artwork can propose overlay + case
             "seasons": cat.seasons(it.id) if it.kind == "series" else []}
            for it in cat.items(request.args.get("folder", ""))]


@web_bp.get("/api/poster")
def api_poster():
    """The title's current poster, big: the one Artwork sent, else TMDb's (780 px wide)."""
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    it = cat.get(request.args.get("id", type=int) or 0) or abort(404)
    cache = s.data_dir / "cache"
    fetch = current_app.config["FETCH"]

    def tmdb_780():   # big enough to edit, and cached: a library page asks for all of them at once
        try:
            return fetch(images.TMDB_IMG + "w780" + it.meta["poster_path"]) if it.meta.get("poster_path") else None
        except Exception:
            return None
    data = images.own_bytes(it, cache, "poster") or images._cached(
        cache / f"poster_{it.id}_full.jpg", tmdb_780, lambda: images.poster_jpeg(it, cache, 600, 900, fetch))
    mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
    return Response(data, mimetype=mime, headers={"Cache-Control": "no-cache"})


def _match_item():
    """The catalog item for ?path=, as Emby gives it (/data/Library/...) or relative (Library/...)."""
    path = (request.args.get("path") or "").replace("\\", "/")
    rel = path[len("/data/"):] if path.startswith("/data/") else path.lstrip("/")
    it = current_app.config["CATALOG"].item_by_path(rel.rstrip("/"))
    if not it:
        abort(404)
    return it


def _match_json(it):
    return {"id": it.id, "title": it.title, "year": it.year, "tmdb_id": it.tmdb_id,
            "media": "tv" if it.kind == "series" else "movie", "locked": bool(it.meta.get("locked"))}


@web_bp.get("/match")
def match_get():
    """Which TMDb title the Biblioteca shows for a file (Artwork Studio's "Metadatos" tab)."""
    return _match_json(_match_item())


@web_bp.post("/match")
def match_set():
    """POST /match?path=/data/Library/ATMOS/x.iso&tmdb=49046: use that TMDb title, locked."""
    from biblio.catalog import set_match
    it, tmdb = _match_item(), current_app.config["TMDB"]
    tmdb_id = request.args.get("tmdb", type=int)
    if not tmdb_id or not tmdb:
        abort(400)
    meta = tmdb.tv(tmdb_id) if it.kind == "series" else tmdb.movie(tmdb_id)
    if not meta:
        abort(502)
    s, cat = current_app.config["SETTINGS"], current_app.config["CATALOG"]
    set_match(s, cat, it, meta)
    return _match_json(cat.get(it.id))


@web_bp.post("/tools/case")
def case_tool():
    """Artwork Studio's "Caja Blu-ray" / "Caja 4K" overlays: the posted cover comes back as a
    transparent PNG inside that case (the perspective warp lives here, in Pillow).
    POST /tools/case?kind=bluray|uhd&title=Spine%20text, body = the cover image."""
    kind = request.args.get("kind", "bluray")
    data = request.get_data()
    if kind not in ("bluray", "uhd") or not data or len(data) > 30 * 1024 * 1024:
        abort(400)
    try:
        cover = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        abort(400)
    buf = io.BytesIO()
    images.case_image(cover, request.args.get("title", ""), kind == "uhd").save(buf, "PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@web_bp.post("/folders")
def save_folder():
    s = current_app.config["SETTINGS"]
    f = request.form
    fid, path = f.get("id", "").strip().lower(), f.get("path", "").strip().strip("/")
    media = s.media_root.resolve()
    target = (media / path).resolve()
    if not _ID.match(fid) or f.get("kind") not in ("movies", "series") or not path \
            or not target.is_relative_to(media):
        abort(400)
    icon = f.get("icon") or "film.png"
    upload = request.files.get("icon_upload")
    if upload and upload.filename:
        out = s.data_dir / "icons" / f"{fid}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        ImageOps.fit(Image.open(upload.stream).convert("RGBA"), (96, 96)).save(out, "PNG")
        icon = f"{fid}.png"
    folders = [x for x in load_folders(s.data_dir) if x.id != fid]
    folders.append(Folder(fid, f.get("name", fid).strip() or fid, icon, path, f["kind"],
                          f.get("order", len(folders), type=int)))
    save_folders(s.data_dir, sorted(folders, key=lambda x: x.order))
    return redirect("/")


@web_bp.get("/browse")
def browse():
    """Subfolders of a NAS folder, for the folder picker: /browse?path=Library -> {path, dirs}.
    Only inside the media root; hidden and Synology @eaDir folders are left out."""
    import os
    media = current_app.config["SETTINGS"].media_root.resolve()
    rel = (request.args.get("path") or "").strip("/")
    target = (media / rel).resolve()
    if not target.is_relative_to(media) or not target.is_dir():
        abort(404)
    with os.scandir(target) as it:
        dirs = sorted((e.name for e in it if e.is_dir() and not e.name.startswith((".", "@"))), key=str.casefold)
    path = "" if target == media else target.relative_to(media).as_posix()
    return {"path": path, "dirs": dirs[:2000]}


@web_bp.post("/folders/<fid>/delete")
def delete_folder(fid):
    s = current_app.config["SETTINGS"]
    save_folders(s.data_dir, [x for x in load_folders(s.data_dir) if x.id != fid])
    return redirect("/")


@web_bp.post("/rescan")
def rescan():
    current_app.config["RESCAN"]()
    return redirect("/")
