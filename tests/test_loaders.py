import io
import sys
import urllib.request

from PIL import Image

sys.path.insert(0, "tools/loaders")
import make_loaders


def test_library_posters_reads_every_page_of_a_big_folder(monkeypatch):
    """A folder of 1500 titles: the answer is paged (1000 at most), the last titles must be considered too."""
    png = io.BytesIO()
    Image.new("RGB", (150, 225)).save(png, "PNG")
    seen = []

    def reply(text: str):
        return type("R", (), {"read": lambda self: text.encode()})()

    def fake(url, timeout=0):
        path = url.split("//x", 1)[1]
        seen.append(path)
        if path == "/d/folders":
            return reply("big\tBig\t1500")
        if path.startswith("/d/items?folder=big"):
            offset = int(path.split("offset=")[1]) if "offset=" in path else 0
            rows = [f"{i}\tT{i}\t2020\tmovie" for i in range(offset, min(offset + 1000, 1500))]
            return reply("\n".join(["1500"] + rows))
        if path.startswith("/d/item?"):
            return reply("rating\t7.5")
        return type("R", (), {"read": lambda self: png.getvalue()})()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    make_loaders.library_posters("http://x", n=1499, seed=1)   # almost all of them: needs the second page
    assert any("offset=1000" in p for p in seen)
    assert any(p.startswith("/d/item?id=1499") for p in seen)   # a title that is only on the second page
