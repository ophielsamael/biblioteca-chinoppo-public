from biblio.config import Folder, load_folders, load_settings, save_folders


def test_defaults_when_missing(tmp_path):
    f = load_folders(tmp_path)
    assert [x.id for x in f] == ["3d", "atmos", "conciertos", "movies", "series"]
    assert f[4].kind == "series" and f[0].path == "Library/3D"


def test_network_from_env():
    s = load_settings({"CHINOPPO_IP": "10.0.0.5", "NFS_SERVER": "10.0.0.9", "NFS_FOLDER": "volume2/Video"})
    assert (s.chinoppo_ip, s.nfs_server, s.nfs_folder) == ("10.0.0.5", "10.0.0.9", "volume2/Video")
    assert load_settings({}).chinoppo_ip == "192.168.1.16"


def test_roundtrip(tmp_path):
    save_folders(tmp_path, [Folder("x", "Mis 4K", "atmos.png", "Library/ATMOS", "movies", 0)])
    assert load_folders(tmp_path)[0].name == "Mis 4K"
