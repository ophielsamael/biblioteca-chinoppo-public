import re

from flask import Response

_WS = re.compile(r"[\t\r\n]+")


def line(*fields: object) -> str:
    """One protocol line for the BD-J disc: tab-separated, no tabs/newlines inside fields."""
    return "\t".join("" if f is None else _WS.sub(" ", str(f)) for f in fields)


def text(lines: list[str]) -> Response:
    return Response("\n".join(lines), mimetype="text/plain; charset=utf-8")
