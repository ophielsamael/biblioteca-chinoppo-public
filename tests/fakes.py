from pathlib import Path

from biblio.config import Settings

BLACK_SWAN_META = {
    "tmdb_id": 44214, "overview": "Una bailarina…", "rating": 7.7, "runtime_min": 108,
    "certification": "16", "genres": ["Drama", "Suspense"], "director": "Darren Aronofsky",
    "cast": ["Natalie Portman", "Mila Kunis"], "poster_path": None, "backdrop_path": None,
}


def settings_with(tmp: Path, files: dict[str, bytes]) -> Settings:
    media = tmp / "media"
    for rel, data in files.items():
        p = media / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    media.mkdir(exist_ok=True)
    return Settings(data_dir=tmp, media_root=media, tmdb_key="")


class FakeChinoppo:
    """Simulates the player states seen on the real Chinoppo (2026-11-02):
    while a BD-J disc runs, playnormalfile blocks (queued) until STP closes the disc."""

    def __init__(self):
        import threading
        self.calls = []
        self.state = "idle"          # idle | bdmv | playing
        self.on_key_stp = "closes_disc_and_runs_queue"
        self.play_starts = True
        self.mount_ok = True
        self.unreachable = False
        self.block_play = False
        self.cur, self.total = 0, 0
        self.start_after = 0           # polls an accepted play needs before video runs (big ISOs load slowly)
        self._pending = 0
        self.mounted = None            # NFS folder currently at /mnt/nfs1 (unknown = None)
        self.subpath_ok = False        # True: subfolder paths of the mounted folder play directly
        self.accept_but_hang = False   # True: a subfolder path is accepted but leaves a disc open, no video
        self.flaky_polls = 0           # next N global_info calls raise (player busy loading)
        self.usb = False               # a stick with Biblioteca.iso is plugged in
        self.usb_mount = "/mnt/sda1"   # /mnt/sdb1 after a standby (stick re-enumerated)
        self.listed = set()            # folders walked with getfilelist
        self.require_walk = True
        self._disc_closed = threading.Event()

    def list_dir(self, path):
        self._check()
        self.calls.append(("list_dir", path))
        if self.mounted is None or (path != "/mnt/nfs1" and path.rsplit("/", 1)[0] not in self.listed):
            return b"FLAG"                         # empty: not mounted / not reachable
        self.listed.add(path)
        return b"FLAG\x05\x00\x00\x00entry"

    def _check(self):
        from biblio.chinoppo import ChinoppoError
        if self.unreachable:
            raise ChinoppoError("timeout")

    def global_info(self, timeout=8):
        self._check()
        if self.flaky_polls:
            from biblio.chinoppo import ChinoppoError
            self.flaky_polls -= 1
            raise ChinoppoError("timed out")
        if self._pending:
            self._pending -= 1
            if not self._pending:
                self.state = "playing"
        # "menu": a disc is open (error screen / loading) but no video runs yet
        return {"is_bdmv_playing": self.state in ("bdmv", "menu"),
                "is_video_playing": self.state in ("bdmv", "playing")}

    def playing_time(self):
        self._check()
        return {"cur_time": self.cur, "total_time": self.total}

    LIBRARY_DIR = "volume1/Plex/Biblioteca"

    def _start(self, path):
        # Real player (2026-11-03): a title in a subfolder of the mounted folder plays directly
        # (subpath_ok); otherwise only "/mnt/nfs1/<name>" in the mounted folder works.
        # Biblioteca.iso has its own folder. Nothing plays while another disc is open.
        if path.startswith("/mnt/sd"):               # USB stick: plays if plugged in, at its mount
            if not path.startswith(self.usb_mount + "/"):
                return {"success": False}
            if self.state in ("bdmv", "menu") or not self.usb:
                return {"success": False}
            self.state = "bdmv"
            return {"success": True}
        rel = path[len("/mnt/nfs1/"):]
        parent = path.rsplit("/", 1)[0]
        # measured 2026-11-03: a subfolder path plays only after its folders were listed
        # level by level (getfilelist), like the browser walking into them
        walked = parent in self.listed or not self.require_walk
        valid = (self.mounted is not None
                 and ("/" not in rel or (self.subpath_ok and walked))
                 and (rel == "Biblioteca.iso") == (self.mounted == self.LIBRARY_DIR))
        if self.state in ("bdmv", "menu"):
            return {"success": False}
        if self.accept_but_hang and "/" in rel and self.mounted:   # seen once with Avatar
            self.state = "menu"                     # accepted, leaves a disc open, never starts
            return {"success": True}
        if not valid:
            return {"success": False}
        if self.play_starts and self.start_after:
            self._pending = self.start_after
        elif self.play_starts:
            self.state = "playing"
        return {"success": True}

    def play_file(self, path, nfs_server, timeout):
        self._check()
        self.calls.append(("play_file", path))
        if self.block_play:
            self._disc_closed.wait(1)
            return {"success": False}
        return self._start(path)

    def check_bdmv(self, folderpath):
        self._check()
        self.calls.append(("check_bdmv", folderpath))
        return self._start(folderpath)

    def send_key(self, key):
        self._check()
        self.calls.append(("send_key", key))
        if key == "STP" and self.on_key_stp == "ignore_first":
            self.on_key_stp = "closes_disc_and_runs_queue"   # seen live: STP right after OK is dropped
            return {"success": True}
        if key == "STP" and self.on_key_stp == "closes_disc_and_runs_queue" and self.state in ("bdmv", "menu"):
            self.state = "idle"
            self._disc_closed.set()
        return {"success": True}

    def login_nfs(self, server):
        self.calls.append(("login_nfs", server))
        return {"success": True}

    def nfs_share_list(self):
        self.calls.append(("nfs_share_list",))
        return b""

    def setup_menu(self):
        self.calls.append(("setup_menu",))
        return {"success": True}

    def mount_nfs(self, server, folder):
        self.calls.append(("mount_nfs", server, folder))
        if self.mount_ok:
            self.mounted = folder
            self.listed = set()
        return {"success": self.mount_ok}

    def set_play_time(self, seconds):
        self.calls.append(("set_play_time", seconds))
        return {"success": True}

    def wake(self):
        self.calls.append(("wake",))

    def usb_path(self):
        return self.usb_mount if self.usb else None


class FakeTmdb:
    def __init__(self, found: bool):
        self.found = found

    def find_movie(self, title, year):
        return dict(BLACK_SWAN_META) if self.found else None

    def find_tv(self, title, year):
        if not self.found:
            return None
        return {"tmdb_id": 100088, "overview": "Joel y Ellie…", "rating": 8.6, "runtime_min": 55,
                "certification": "", "genres": ["Drama"], "director": "Craig Mazin, Neil Druckmann",
                "cast": ["Pedro Pascal", "Bella Ramsey"], "poster_path": None, "backdrop_path": None,
                "season_posters": {"1": "/s1.jpg", "2": "/s2.jpg"}}

    def tv(self, tid):
        return self.find_tv("", None)

    def season(self, tv_id, season):
        if not self.found:
            return None
        return [{"number": n, "title": f"Capítulo {n}", "air_date": "2025-04-13", "overview": "…",
                 "still_path": None} for n in range(1, 8)]
