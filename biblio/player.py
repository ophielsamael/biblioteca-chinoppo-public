"""Launch a movie from the BD-J library disc and bring the user back to it.

Measured on the real Chinoppo (2026-11-02): mountNfsSharedFolder answers
"bd_is_playing" while the disc runs, so the disc is closed first with STP;
an ISO only plays when the NFS mount is its own folder (/mnt/nfs1/<name>),
so every title mounts its containing folder (as Xnoppo does); BDMV folders
play through checkfolderhasBDMV. Any unexpected answer aborts: blind
retries once left the player hung."""
import posixpath
import logging
import threading
import time
from dataclasses import dataclass

from biblio.chinoppo import ChinoppoError
from biblio.config import Settings, load_folders
from biblio.db import Catalog, Item

log = logging.getLogger("biblioteca.player")
START_WAIT = 30      # seconds to wait for video to start (ISOs load slowly)
CLOSE_WAIT = 10      # seconds to wait for the library disc to close after STP
SETTLE = 6           # after STP before the next open: 4 s (Xnoppo) still gave "No se puede
                     # reproducir el disco" now and then (2026-11-03), on movies and on the library
PRE_STP = 2          # let the BD-J disc finish handling the OK press
REACH_TIMEOUT = 3    # per call while checking the player answers
AUTO_GRACE = 15      # after power-on, let Xnoppo (Emby -> Chinoppo) act first
FAST_WAIT = 8        # seconds the direct (no-mount) attempt gets before falling back to mounting
RESUME_MIN = 60
WATCHED_RATIO = 0.95


@dataclass
class Target:
    """Something to play. Same field names as db.Item so a movie Item works directly;
    id is the progress key (item id for movies, -episode_file id for episodes)."""
    id: int
    relpath: str
    kind: str


class Player:
    def __init__(self, settings: Settings, catalog: Catalog, box, sleep=time.sleep):
        self.settings, self.catalog, self.box, self.sleep = settings, catalog, box, sleep
        self.launched_by_library: int | None = None
        self._busy = threading.Lock()
        self._last = (0, 0)
        self._was_on: bool | None = None   # unknown until the first observation
        self._mounted: str | None = None   # folder this service last mounted at /mnt/nfs1

    def _path(self, sub: str) -> str:
        return "/mnt/nfs1/" + sub

    def _base(self, relpath: str) -> str:
        """The configured folder (web page) holding relpath: the only thing ever mounted.
        Seen 2026-11-03: with the share root mounted the player indexes the whole NAS
        (~300k entries) and Red, Películas and new plays stall until it is done."""
        paths = [f.path.strip("/") for f in load_folders(self.settings.data_dir)]
        inside = [p for p in paths if relpath.startswith(p + "/")]
        return max(inside, key=len) if inside else posixpath.dirname(relpath)

    def _wait(self, cond, seconds: int) -> bool:
        for _ in range(seconds):
            if cond():
                return True
            self.sleep(1)
        return cond()

    def _info(self) -> dict:
        return self.box.global_info()

    def _reachable(self) -> bool:
        """At most ~3 + 4 + 3 s, so the disc gets "sin respuesta" in under 15 s."""
        try:
            self.box.global_info(REACH_TIMEOUT)
            return True
        except ChinoppoError:
            try:
                self.box.wake()
            except OSError:
                return False
            self.sleep(4)
            try:
                self.box.global_info(REACH_TIMEOUT)
                return True
            except ChinoppoError:
                return False

    def target_for_episode(self, ep_file_id: int) -> Target | None:
        ep = self.catalog.episode_file(ep_file_id)
        return Target(-ep.id, ep.relpath, ep.kind) if ep else None

    def play(self, item_id: int, resume: bool) -> str:
        return self._start(self.catalog.get(item_id), resume)

    def play_episode(self, ep_file_id: int, resume: bool) -> str:
        return self._start(self.target_for_episode(ep_file_id), resume)

    def _start(self, item, resume: bool) -> str:
        if item is None:
            return "error:no existe"
        if not self._busy.acquire(blocking=False):
            return "busy"
        self.launched_by_library = None   # a new launch replaces whatever was being watched
        try:
            if not self._reachable():
                self._busy.release()
                return "error:sin respuesta"
        except Exception:
            self._busy.release()
            raise

        def run():
            try:
                result = self._sequence(item, resume)
                log.info("play %s -> %s", item.relpath, result)
                if result in ("error:montaje", "error:no arrancó"):
                    self._recover()   # the library disc was already closed: don't strand the user
            except Exception:
                log.exception("play failed")
            finally:
                self._busy.release()
        try:
            threading.Thread(target=run, daemon=True).start()
        except Exception:
            self._busy.release()
            raise
        return "ok"

    def _started(self, seconds: int) -> bool:
        return self._wait(lambda: bool(self._safe_info().get("is_video_playing")), seconds)

    def _recover(self) -> None:
        """Reopen Biblioteca.iso: from the USB stick if one is plugged in (instant, leaves the
        NAS mount alone), else from its own NAS folder, mounting it only if needed (~40 s)."""
        s = self.settings
        folder, name = posixpath.split(s.library_iso)
        mnt, lib = posixpath.join(s.nfs_folder, folder), self._path(name)
        # the stick twice: seen 2026-11-03, right after STOP of an ISO the first open showed
        # "No se puede reproducir el disco"; falling back to the NAS cost a 40 s mount and
        # evicted the movie folder, so the next title had to remount it too
        usb = self._usb_library()
        tries = [usb, usb] + ([lib] if self._mounted == mnt else [])
        for i, path in enumerate(tries):
            if i:
                self.sleep(SETTLE)
            if self.box.play_file(path, s.nfs_server, 20).get("success") and self._started(FAST_WAIT):
                return
            log.info("Biblioteca no abrió desde %s", path)
        if self._mount(mnt):
            self.box.play_file(lib, s.nfs_server, 20)
        else:
            log.info("no se pudo reabrir la Biblioteca: montaje de %s falló", mnt)

    def _usb_library(self) -> str:
        """Biblioteca.iso on the stick, wherever the player mounted it (sda1, or sdb1 after
        a standby); the configured path when the player can't tell."""
        name = posixpath.basename(self.settings.library_usb)
        try:
            path = self.box.usb_path()
        except ChinoppoError:
            path = None
        return posixpath.join(path, name) if path else self.settings.library_usb

    def _mount(self, folder: str) -> bool:
        """login + mount, one retry with a fresh login (Xnoppo's pattern). Never unmount."""
        s = self.settings
        for attempt in (1, 2):
            if attempt == 2:
                self.sleep(2)
            # same handshake as Xnoppo; without it the first mount answered "failed" every time
            self.box.login_nfs(s.nfs_server)
            self.box.nfs_share_list()
            self.sleep(2)
            self.box.setup_menu()
            t0 = time.monotonic()
            r = self.box.mount_nfs(s.nfs_server, folder)
            log.info("mount %s (intento %d, %.1fs) -> %s", folder, attempt, time.monotonic() - t0, r)
            if r.get("success"):
                self._mounted = folder
                return True
        self._mounted = None
        return False

    def _close_disc(self) -> bool:
        """STP (twice at most) until no disc is open, then let the drive settle."""
        # seen live: an STP sent while the disc is still handling the OK press is dropped
        self.sleep(PRE_STP)
        closed = lambda: not self._safe_info().get("is_bdmv_playing", True)
        t0 = time.monotonic()
        self.box.send_key("STP")
        if not self._wait(closed, CLOSE_WAIT // 2):
            self.box.send_key("STP")
            if not self._wait(closed, CLOSE_WAIT // 2):
                return False
        log.info("disco cerrado en %.1fs", time.monotonic() - t0)
        self._show_home()
        self.sleep(SETTLE)
        return True

    def _show_home(self) -> None:
        """Closing a disc leaves the player in the USB file list; its home shows our
        "Biblioteca" background for the Películas icon instead (tools/wallpaper)."""
        try:
            self.box.send_key("HOM")
        except ChinoppoError:
            pass

    def _walk(self, sub: str) -> bool:
        """List each folder from the mount down to the title's folder, like the Chinoppo's
        browser does: measured 2026-11-03, a subfolder path only plays after that walk.
        False when a level is empty (nothing mounted, or another folder is)."""
        path = "/mnt/nfs1"
        try:
            for part in [""] + posixpath.dirname(sub).split("/"):
                if part:
                    path += "/" + part
                if len(self.box.list_dir(path)) <= 4:
                    return False
        except ChinoppoError:
            return False
        return True

    def _safe_info(self) -> dict:
        """global_info, or {} while the player is too busy to answer (e.g. loading an ISO)."""
        try:
            return self._info()
        except ChinoppoError:
            return {}

    def _sequence(self, item: Item | Target, resume: bool) -> str:
        s, box = self.settings, self.box
        try:
            info = self._info()
        except ChinoppoError:
            return "error:sin respuesta"
        if (info.get("is_bdmv_playing") or info.get("is_video_playing")) and not self._close_disc():
            return "error:el disco no se cerró"

        def order(path: str) -> bool:
            t0 = time.monotonic()
            try:
                r = box.check_bdmv(path) if item.kind == "bdmv" else box.play_file(path, s.nfs_server, 30)
            except ChinoppoError as e:   # seen live: an order that never answers
                r = {"success": False, "error": str(e)}
            log.info("orden de reproducir %s (%.1fs) -> %s", path, time.monotonic() - t0, r)
            return bool(r.get("success"))

        # some discs (Avatar) are accepted through a subfolder but only start from their own
        # folder: remember them so the next launch skips the 30 s fast attempt
        slow_key = "needs_mount:" + item.relpath
        base = self._base(item.relpath)
        sub = item.relpath[len(base):].lstrip("/")
        mnt = posixpath.join(s.nfs_folder, base)
        parent, name = posixpath.split(item.relpath)
        own = posixpath.join(s.nfs_folder, parent)

        # fast path (measured 2026-11-03): with the folder already mounted, the path inside it
        # plays directly, like the Chinoppo's own browser; no ~40 s remount. An accepted order
        # gets the full start time (big UHD ISOs like Avatar load for >8 s); a rejected one
        # falls back to mounting at once.
        accepted = (self.catalog.get_state(slow_key) is None and self._mounted == mnt
                    and self._walk(sub) and order(self._path(sub)))
        if accepted and self._started(START_WAIT):
            log.info("camino rápido: sin montar")
        else:
            # never mount with a disc left open (loading screen, error dialog): close it first
            if self._safe_info().get("is_bdmv_playing") and not self._close_disc():
                return "error:el disco no se cerró"
            started = False
            # mount the title's configured folder: it stays mounted, so the next titles of
            # that folder take the fast path
            if not accepted and self.catalog.get_state(slow_key) is None:
                if not self._mount(mnt):
                    return "error:montaje"
                started = self._walk(sub) and order(self._path(sub)) and self._started(START_WAIT)
                if not started and self._safe_info().get("is_bdmv_playing") and not self._close_disc():
                    return "error:el disco no se cerró"
            if not started:   # last resort, e.g. Avatar once: mount the title's own folder
                if self._mounted != own and not self._mount(own):
                    return "error:montaje"
                order(self._path(name))
                if not self._started(START_WAIT):
                    return "error:no arrancó"
                if accepted:   # accepted from the root but only plays from its own folder
                    self.catalog.set_state(slow_key, "1")

        prog = self.catalog.progress(item.id)
        if resume and item.kind == "file" and prog and prog[0] > RESUME_MIN:
            box.set_play_time(prog[0])
        self._last = (0, 0)
        self.launched_by_library = item.id
        return "ok"

    def watch_once(self) -> None:
        item_id = self.launched_by_library
        if item_id is None or self._busy.locked():   # never race a launch in progress
            return
        try:
            info = self._info()
            if info.get("is_video_playing") or info.get("is_bdmv_playing"):
                t = self.box.playing_time()
                cur, total = int(t.get("cur_time") or 0), int(t.get("total_time") or 0)
                if total > 0:
                    self._last = (cur, total)
                    self.catalog.save_progress(item_id, cur, total)
                return
            cur, total = self._last
            if total and cur >= WATCHED_RATIO * total:
                self.catalog.save_progress(item_id, 0, total)
            self.launched_by_library = None
            # the movie left its folder mounted; the library ISO lives in its own one
            if self._busy.acquire(blocking=False):
                try:
                    self._show_home()
                    # seen live: reopening right at STOP shows "No se puede reproducir el disco"
                    self.sleep(SETTLE)
                    self._recover()
                finally:
                    self._busy.release()
        except ChinoppoError:
            log.info("watcher: player unreachable, stop watching")
            self.launched_by_library = None

    def _idle(self) -> bool:
        info = self.box.global_info(REACH_TIMEOUT)
        return not (info.get("is_bdmv_playing") or info.get("is_video_playing"))

    def watch_power(self) -> None:
        """Open Biblioteca.iso when the player is switched on (off/standby -> answering, idle).
        The firmware home menu can't be changed, so this stands in for a shortcut."""
        try:
            self.box.global_info(REACH_TIMEOUT)
            on = True
        except ChinoppoError:
            on = False
        was_on, self._was_on = self._was_on, on
        if not (on and was_on is False) or self.catalog.get_state("autoopen") == "0":
            return
        self.sleep(AUTO_GRACE)
        try:
            # a movie we launched was still up when it went to standby: close it and come back to
            # the Biblioteca (the vigilante stays out of the way while a movie plays). Otherwise
            # only open if idle on its home — the vigilante handles that too, but this is harmless.
            had_movie = self.launched_by_library is not None
            if not had_movie and not self._idle():
                return
        except ChinoppoError:
            return
        if not self._busy.acquire(blocking=False):
            return
        try:
            log.info("despertó con una película puesta: volviendo a la Biblioteca" if had_movie
                     else "Chinoppo encendido: abriendo la Biblioteca")
            self._recover()
        finally:
            self._busy.release()

    def watch_forever(self, interval: float = 2) -> None:
        while True:
            for step in (self.watch_once, self.watch_power):
                try:
                    step()
                except Exception:
                    log.exception("watcher")
                    self.launched_by_library = None
            time.sleep(interval)
