import io
import zipfile

import pytest

from biblio import usbpack


def test_patch_rewrites_every_placeholder_and_keeps_size():
    iso = b"x" * 100 + usbpack.PLACEHOLDER + b" " * 4000 + b"y" * 50 + usbpack.PLACEHOLDER + b" " * 4000
    out = usbpack.patch_iso(iso, "http://10.0.0.7:8095")
    assert len(out) == len(iso) and usbpack.PLACEHOLDER not in out
    assert out.count(b"BIBLIO_URL=http://10.0.0.7:8095\n") == 2
    with pytest.raises(ValueError):
        usbpack.patch_iso(b"no placeholder here", "http://10.0.0.7:8095")


def test_real_iso_has_both_placeholders():
    assert usbpack.ISO.read_bytes().count(usbpack.PLACEHOLDER) == 2


def test_usb_zip_from_the_web_page(client, settings):
    r = client.get("/usb.zip", base_url="http://10.0.0.7:8095")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.data))
    names = set(z.namelist())
    assert {"Biblioteca.iso", "AutoScript/AutoScript.TSS", "AutoScript/vigilante.sh", "AutoScript/consola"} <= names
    assert b"BIBLIO_URL=http://10.0.0.7:8095\n" in z.read("Biblioteca.iso")
    vig = z.read("AutoScript/vigilante.sh")
    assert f"CHINOPPO_IP={settings.chinoppo_ip}".encode() in vig and b"\r" not in vig
    assert client.get("/usb.zip", base_url="http://127.0.0.1:8095").status_code == 400
