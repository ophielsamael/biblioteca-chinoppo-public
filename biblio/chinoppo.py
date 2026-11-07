"""Minimal client for the Chinoppo/Oppo UDP-203 HTTP API on :436.
URL formats copied from xnoppo/lib/oppo.py (proven against this player)."""
import json
import socket
import urllib.parse
import urllib.request
from collections.abc import Callable


class ChinoppoError(Exception):
    pass


def _urlopen(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


class Chinoppo:
    def __init__(self, ip: str, get: Callable[[str, float], str] | None = None):
        self.ip = ip
        self._get = get or _urlopen

    def _call(self, endpoint: str, timeout: float = 8) -> dict:
        try:
            raw = self._get(f"http://{self.ip}:436{endpoint}", timeout)
        except Exception as e:
            raise ChinoppoError(str(e)) from e
        try:
            return json.loads(raw)
        except ValueError:
            return {"success": False, "raw": raw}

    @staticmethod
    def _q(obj: str) -> str:
        return urllib.parse.quote(obj)

    def global_info(self, timeout: float = 8) -> dict:
        return self._call("/getglobalinfo", timeout)

    def usb_path(self) -> str | None:
        """Where the USB stick is mounted: /mnt/sda1 after boot, /mnt/sdb1 after a standby
        (the player cuts USB power and the stick comes back as a new disk)."""
        devices = self._call("/getdevicelist", 5).get("devicelist") or []
        return next((d.get("path") for d in devices if d.get("sub_type") == "usb"), None)

    def playing_time(self) -> dict:
        return self._call("/getplayingtime")

    def play_file(self, path: str, nfs_server: str, timeout: float) -> dict:
        inner = (f'"path":"{path}","index":0,"type":1,"appDeviceType":2,'
                 f'"extraNetPath":"{nfs_server}","playMode":0')
        return self._call("/playnormalfile?{" + self._q(inner) + "}", timeout)

    def check_bdmv(self, folderpath: str) -> dict:
        """Plays a BDMV folder (Xnoppo's call for Blu-ray folder structures)."""
        return self._call(f'/checkfolderhasBDMV?{{"folderpath":"{self._q(folderpath)}"}}', 30)

    def send_key(self, key: str) -> dict:
        return self._call("/sendremotekey?" + self._q(json.dumps({"key": key})))

    def login_nfs(self, server: str) -> dict:
        return self._call("/loginNfsServer?" + self._q(json.dumps({"serverName": server})))

    def nfs_share_list(self) -> bytes:
        """Binary listing; called only because Xnoppo's login->list->setupmenu->mount works."""
        try:
            return self._get(f"http://{self.ip}:436/getNfsShareFolderlist", 15).encode()
        except Exception as e:
            raise ChinoppoError(str(e)) from e

    def list_dir(self, path: str) -> bytes:
        """Binary folder listing (getfilelist); b"FLAG" alone means empty / not mounted."""
        q = self._q(path)
        try:
            return self._get(f'http://{self.ip}:436/getfilelist?{{"path":"{q}","fileType":1,'
                             f'"mediaType":3,"flag":1}}', 15).encode("latin-1", "replace")
        except Exception as e:
            raise ChinoppoError(str(e)) from e

    def setup_menu(self) -> dict:
        return self._call("/getsetupmenu")

    def mount_nfs(self, server: str, folder: str) -> dict:
        return self._call(f'/mountNfsSharedFolder?{{"server":"{server}","folder":"{self._q(folder)}"}}', 60)

    def set_play_time(self, seconds: int) -> dict:
        h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
        return self._call(f'/setplaytime?{{"h":{h},"m":{m},"s":{s}}}')

    def wake(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"NOTIFY OREMOTE LOGIN", (self.ip, 7624))
