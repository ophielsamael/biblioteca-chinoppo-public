import os
from dataclasses import dataclass, field
from pathlib import Path

from biblio.names import parse_episode

VIDEO_EXT = {".mkv", ".mp4", ".m2ts", ".ts", ".avi", ".iso"}


@dataclass
class Entry:
    relpath: str  # relative to media_root, "/" separated
    stem: str
    kind: str  # "file" | "iso" | "bdmv"


@dataclass
class EpisodeFile:
    relpath: str
    kind: str  # "file" | "iso"
    season: int
    episodes: list[int]


@dataclass
class Show:
    relpath: str  # the series folder
    name: str
    files: list[EpisodeFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # videos without an SxxEyy code


def _hidden(name: str) -> bool:
    return name.startswith("@") or name.startswith(".")


def scan_series(media_root: Path, folder_path: str) -> list[Show] | None:
    """One Show per series folder, walking Serie/Temporada/archivo. None if the root is missing."""
    root = Path(media_root) / folder_path
    if not root.is_dir():
        return None
    base = folder_path.strip("/")
    shows = []
    for show_dir in sorted(p for p in root.iterdir() if p.is_dir() and not _hidden(p.name)):
        show = Show(f"{base}/{show_dir.name}", show_dir.name)
        for dirpath, dirnames, filenames in os.walk(show_dir):
            dirnames[:] = sorted(d for d in dirnames if not _hidden(d))
            for name in sorted(filenames):
                ext = os.path.splitext(name)[1].lower()
                if ext not in VIDEO_EXT:
                    continue
                rel = Path(dirpath, name).relative_to(media_root).as_posix()
                code = parse_episode(name)
                if code is None:
                    show.skipped.append(rel)
                else:
                    show.files.append(EpisodeFile(rel, "iso" if ext == ".iso" else "file", code[0], code[1]))
        shows.append(show)
    return shows


def scan_folder(media_root: Path, folder_path: str) -> list[Entry] | None:
    """None when the folder isn't there (e.g. the NAS mount dropped): unknown, not empty."""
    root = Path(media_root) / folder_path
    if not root.is_dir():
        return None
    out = []
    for p in root.iterdir():
        if p.name.startswith("@"):  # Synology @eaDir
            continue
        rel = f"{folder_path.strip('/')}/{p.name}"
        if p.is_dir():
            if (p / "BDMV").is_dir():
                out.append(Entry(rel, p.name, "bdmv"))
        elif p.suffix.lower() in VIDEO_EXT:
            out.append(Entry(rel, p.stem, "iso" if p.suffix.lower() == ".iso" else "file"))
    return sorted(out, key=lambda e: e.stem.casefold())
