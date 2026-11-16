import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Folder:
    id: str
    name: str
    icon: str
    path: str  # relative to Settings.media_root
    kind: str  # "movies" | "series"
    order: int


@dataclass
class Settings:
    data_dir: Path
    media_root: Path
    tmdb_key: str
    chinoppo_ip: str = "192.168.1.16"
    nfs_server: str = "192.168.1.17"
    nfs_folder: str = "volume1/Plex"
    # in its own folder: mounting the share root makes the player index all of it
    # (Downloads alone is ~280k entries) and stalls everything that touches the NAS
    library_iso: str = "Biblioteca/Biblioteca.iso"
    library_usb: str = "/mnt/sda1/Biblioteca.iso"       # copy on a stick left in the player
    port: int = 8095
    loading_videos: bool = True   # cargando_*.mp4 on the stick cover the home menu; LOADING_VIDEOS=off
    # Mount the folder holding every library folder ("Library") once, instead of one folder per
    # title: then every title plays without a 40 s remount. "auto": their common parent; a path:
    # that folder; "": one folder per title (as before). MOUNT_ROOT=off in compose.yaml turns it off.
    mount_root: str = ""
    # Seconds a loading video ("Cargando película", and "Cargando biblioteca" after a movie) runs once it
    # plays, before the next order replaces it. The TV needs ~3 s to lock onto the video's mode (seen
    # 2026-11-16: with 3 s only black showed, with 7 s it does); more shows it longer and delays what
    # follows that much. LOADER_SETTLE in compose.yaml (1 to 20).
    loader_settle: float = 3.0


DEFAULT_FOLDERS = [
    Folder("3d", "3D", "3d.png", "Library/3D", "movies", 0),
    Folder("atmos", "ATMOS", "atmos.png", "Library/ATMOS", "movies", 1),
    Folder("conciertos", "Conciertos", "conciertos.png", "Library/CONCIERTOS", "movies", 2),
    Folder("movies", "Movies", "movies.png", "Library/Movies", "movies", 3),
    Folder("series", "Series", "series.png", "Library/SERIES", "series", 4),
]


def load_settings(env: Mapping[str, str]) -> Settings:
    from biblio import keys
    data_dir = Path(env.get("DATA_DIR", "/app/data"))
    return Settings(
        data_dir=data_dir,
        media_root=Path(env.get("MEDIA_ROOT", "/media/Plex")),
        tmdb_key=keys.tmdb_key(env.get("TMDB_API_KEY", ""), data_dir),   # saved in Artwork > Ajustes, else compose
        chinoppo_ip=env.get("CHINOPPO_IP", Settings.chinoppo_ip),
        nfs_server=env.get("NFS_SERVER", Settings.nfs_server),
        nfs_folder=env.get("NFS_FOLDER", Settings.nfs_folder),
        loading_videos=env.get("LOADING_VIDEOS", "on").strip().lower() != "off",
        mount_root="" if env.get("MOUNT_ROOT", "auto").strip().lower() in ("", "off") else env.get("MOUNT_ROOT", "auto").strip("/ "),
        loader_settle=_seconds(env.get("LOADER_SETTLE"), 3.0),
    )


def _seconds(raw, default: float) -> float:
    try:
        return min(20.0, max(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


def common_root(folders: list[Folder]) -> str:
    """The folder holding every configured folder ("Library" for Library/ATMOS, Library/Movies...);
    '' when they share none (the share root is never mounted: the player indexes all of it)."""
    import posixpath
    paths = [f.path.strip("/") for f in folders if f.path.strip("/")]
    try:
        return posixpath.commonpath(paths) if paths else ""
    except ValueError:
        return ""


def load_folders(data_dir: Path) -> list[Folder]:
    path = Path(data_dir) / "config.json"
    if not path.exists():
        return [Folder(**asdict(f)) for f in DEFAULT_FOLDERS]
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted((Folder(**f) for f in data["folders"]), key=lambda f: f.order)


def save_folders(data_dir: Path, folders: list[Folder]) -> None:
    path = Path(data_dir) / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"folders": [asdict(f) for f in folders]}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)
