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
    assert set(usbpack.LOADERS) <= names                  # the loading videos go on the stick too
    assert b"BIBLIO_URL=http://10.0.0.7:8095\n" in z.read("Biblioteca.iso")
    vig = z.read("AutoScript/vigilante.sh")
    assert f"CHINOPPO_IP={settings.chinoppo_ip}".encode() in vig and b"\r" not in vig
    assert f"NFS_SERVER={settings.nfs_server}".encode() in vig
    assert client.get("/usb.zip", base_url="http://127.0.0.1:8095").status_code == 400


def test_page_shows_the_folder_mounted_at_power_on_and_an_outdated_stick(client, settings):
    settings.mount_root = "auto"                          # default folders: all inside Library
    page = client.get("/", base_url="http://10.0.0.7:8095").get_data(as_text=True)
    assert "volume1/Plex/Library" in page and "Tu USB no está al día" in page
    client.get("/usb.zip", base_url="http://10.0.0.7:8095")          # the stick now mounts that folder
    page = client.get("/", base_url="http://10.0.0.7:8095").get_data(as_text=True)
    assert "Tu USB no está al día" not in page
    settings.mount_root = ""                              # one folder per title: tell how to get the fast way
    page = client.get("/", base_url="http://10.0.0.7:8095").get_data(as_text=True)
    assert "no están dentro de una misma carpeta" in page and "Tu USB no está al día" in page


def test_vigilante_gets_the_nas_and_the_folder_to_mount():
    z = zipfile.ZipFile(io.BytesIO(usbpack.build_zip("http://10.0.0.7:8095", "10.0.0.9", "10.0.0.5", "volume2/Cine/Library")))
    vig = z.read("AutoScript/vigilante.sh")
    assert b"NFS_SERVER=10.0.0.5" in vig and b"NFS_LIBRARY=volume2/Cine/Library" in vig
    off = zipfile.ZipFile(io.BytesIO(usbpack.build_zip("http://10.0.0.7:8095", "10.0.0.9", "10.0.0.5", "")))
    assert b"NFS_LIBRARY= " in off.read("AutoScript/vigilante.sh")   # one folder per title: nothing mounted at power-on


def test_zip_carries_the_loading_video_wait_to_the_stick_script():
    z = zipfile.ZipFile(io.BytesIO(usbpack.build_zip("http://10.0.0.7:8095", "10.0.0.9", loader_settle=7.0)))
    script = z.read("AutoScript/vigilante.sh").decode()
    assert "LOADER_SETTLE=7 " in script and "sleep $LOADER_SETTLE" in script
