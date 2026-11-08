"""API keys typed in Artwork Studio, kept in the service's data folder (data/keys.json), so nobody
has to edit compose.yaml. A key saved here wins over the TMDB_API_KEY environment variable."""
import json
import re
from pathlib import Path

PLACEHOLDER = re.compile(r"^(pon_aqui|tu_|YOUR_)", re.I)
TMDB_FORMAT = re.compile(r"^[0-9a-fA-F]{32}$")     # the v3 "API Key" (not the long v4 token)


def _file(data_dir: Path) -> Path:
    return Path(data_dir) / "keys.json"


def load(data_dir: Path) -> dict:
    try:
        data = json.loads(_file(data_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data_dir: Path, **keys: str) -> None:
    data = load(data_dir)
    data.update({k: v for k, v in keys.items() if v})
    path = _file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def tmdb_key(env_value: str, data_dir: Path) -> str:
    """The saved key if there is one, else the environment's (ignoring compose's placeholder)."""
    saved = load(data_dir).get("tmdb", "")
    if saved:
        return saved
    return "" if PLACEHOLDER.match(env_value or "") else (env_value or "")
