import re

_YEAR = re.compile(r"(?<!\d)(?:19|20)\d\d(?!\d)")


_EPISODE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})((?:[Ee]\d{1,3})*)")


def parse_episode(filename: str) -> tuple[int, list[int]] | None:
    """Season and episode numbers from "S02E01e02e03"-style codes (any letter case)."""
    m = _EPISODE.search(filename)
    if not m:
        return None
    return int(m.group(1)), [int(m.group(2))] + [int(n) for n in re.findall(r"\d+", m.group(3))]


def parse_name(stem: str) -> tuple[str, int | None]:
    """Title and year from a file name: the year is the last 19xx/20xx
    that is not the whole title ("Blade Runner 2049 2017" -> 2017)."""
    text = re.sub(r"[._]", " ", stem).strip()
    for m in reversed(list(_YEAR.finditer(text))):
        title = text[: m.start()].rstrip(" ([-").strip()
        if title:
            return title, int(m.group())
    return text, None
