import json
import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "artwork" / "changelog.json"


def test_changelog_is_valid_and_newest_first():
    """Artwork compares versions by id (a date), so each release needs a well-formed entry and the
    list must go newest first; the notice shows entries with a larger id than the installed one."""
    entries = json.loads(CHANGELOG.read_text(encoding="utf-8"))
    assert entries, "add an entry for every published version"
    ids = [e["id"] for e in entries]
    assert all(re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(\.\d+)?", i) for i in ids), ids
    assert ids == sorted(ids, reverse=True) and len(set(ids)) == len(ids)
    for e in entries:
        for lang in ("es", "en"):
            assert e["title"][lang] and e["changes"][lang], (e["id"], lang)
        assert len(e["changes"]["es"]) == len(e["changes"]["en"])
        assert isinstance(e["compose"], bool) and isinstance(e["usb"], bool)
