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


DEFAULT_FOLDERS = [
    Folder("3d", "3D", "3d.png", "Library/3D", "movies", 0),
    Folder("atmos", "ATMOS", "atmos.png", "Library/ATMOS", "movies", 1),
    Folder("conciertos", "Conciertos", "conciertos.png", "Library/CONCIERTOS", "movies", 2),
    Folder("movies", "Movies", "movies.png", "Library/Movies", "movies", 3),
    Folder("series", "Series", "series.png", "Library/SERIES", "series", 4),
]


def load_settings(env: Mapping[str, str]) -> Settings:
    return Settings(
        data_dir=Path(env.get("DATA_DIR", "/app/data")),
        media_root=Path(env.get("MEDIA_ROOT", "/media/Plex")),
        tmdb_key=env.get("TMDB_API_KEY", ""),
        chinoppo_ip=env.get("CHINOPPO_IP", Settings.chinoppo_ip),
        nfs_server=env.get("NFS_SERVER", Settings.nfs_server),
        nfs_folder=env.get("NFS_FOLDER", Settings.nfs_folder),
    )


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
