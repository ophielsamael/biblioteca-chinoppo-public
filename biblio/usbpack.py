"""The ZIP a user unpacks onto the USB stick: the Biblioteca disc with this server's address
written in, and the AutoScript files with the player's IP. Nobody has to compile anything.

The disc (static/usb/Biblioteca.iso, built by disc/Makefile) carries BIBLIO.TXT twice, each a
4 KB file starting with the placeholder line below; the disc reads the address from it."""
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISO = ROOT / "static" / "usb" / "Biblioteca.iso"
AUTOSCRIPT = ROOT / "tools" / "autoscript" / "AutoScript"
PLACEHOLDER = b"BIBLIO_URL=http://0.0.0.0:8095"
SLOT = 200   # bytes rewritten at each placeholder (the file is 4 KB of spaces after it)
FILES = ["AutoScript", "AutoScript.TSS", "arrancar.sh", "vigilante.sh", "consola"]


def patch_iso(iso: bytes, url: str) -> bytes:
    line = b"BIBLIO_URL=" + url.encode("ascii") + b"\n"
    if not url.startswith("http://") or len(line) > SLOT:
        raise ValueError(url)
    out, n, i = bytearray(iso), 0, iso.find(PLACEHOLDER)
    while i != -1:
        out[i:i + SLOT] = line.ljust(SLOT, b" ")
        n += 1
        i = iso.find(PLACEHOLDER, i + 1)
    if n == 0:
        raise ValueError("no BIBLIO.TXT placeholder in the ISO")
    return bytes(out)


def build_zip(url: str, chinoppo_ip: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Biblioteca.iso", patch_iso(ISO.read_bytes(), url))
        for name in FILES:
            data = (AUTOSCRIPT / name).read_bytes()
            if name != "consola":
                data = data.replace(b"\r\n", b"\n")   # the player's shell wants LF
            if name == "vigilante.sh":
                data = data.replace(b"CHINOPPO_IP=192.168.1.16", f"CHINOPPO_IP={chinoppo_ip}".encode())
            info = zipfile.ZipInfo(f"AutoScript/{name}", (2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if name.endswith(".sh") or name == "consola" else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()
