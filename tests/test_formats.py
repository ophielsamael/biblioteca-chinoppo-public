from biblio.formats import badges, biggest_m2ts, summarize

HEVC_4K = {"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 2160,
           "color_transfer": "smpte2084"}
EL = {"codec_type": "video", "codec_name": "hevc", "width": 1920, "height": 1080, "color_transfer": "smpte2084"}
ATMOS = {"codec_type": "audio", "codec_name": "truehd", "profile": "Dolby TrueHD + Dolby Atmos", "channels": 8}


def test_uhd_bluray_with_enhancement_layer_is_dolby_vision():
    f = summarize([HEVC_4K, EL, ATMOS, {"codec_type": "audio", "codec_name": "ac3", "channels": 6}])
    assert (f["res"], f["hdr"], f["dv_profile"], f["atmos"], f["audio"], f["ch"]) == \
        ("4K", ["DV", "HDR10"], 7, True, "TrueHD", "7.1")
    assert badges(f) == ["4K", "DV", "ATMOS"]


def test_mkv_dovi_record_and_hdr10plus_frames():
    v = dict(HEVC_4K, side_data_list=[{"side_data_type": "DOVI configuration record", "dv_profile": 8}])
    dtsx = {"codec_type": "audio", "codec_name": "dts", "profile": "DTS-HD MA + DTS:X", "channels": 8}
    f = summarize([v, dtsx], [{"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}])
    assert f["hdr"] == ["DV", "HDR10+", "HDR10"] and f["dv_profile"] == 8
    assert f["audio"] == "DTS-HD MA" and f["dtsx"]
    assert badges(f) == ["4K", "DV", "HDR10+", "DTS:X"]


def test_plain_hdr10_and_sdr_1080p():
    assert badges(summarize([HEVC_4K, {"codec_type": "audio", "codec_name": "eac3", "channels": 6}])) == \
        ["4K", "HDR10"]
    sdr = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1040}
    assert badges(summarize([sdr, {"codec_type": "audio", "codec_name": "dts", "profile": "DTS-HD MA",
                                   "channels": 6}])) == ["1080p", "DTS-HD MA"]


def test_cover_art_is_not_the_video():
    cover = {"codec_type": "video", "codec_name": "mjpeg", "width": 600, "height": 900,
             "disposition": {"attached_pic": 1}}
    assert summarize([cover, HEVC_4K])["res"] == "4K"


def test_biggest_m2ts_skips_backup_and_other_files():
    listing = "\n".join([
        "Path = BDMV\\STREAM\\00001.m2ts", "Size = 100", "",
        "Path = BDMV\\BACKUP\\STREAM\\00010.m2ts", "Size = 999999", "",
        "Path = BDMV\\STREAM\\00010.m2ts", "Size = 5000", "",
        "Path = CERTIFICATE\\big.bin", "Size = 9999999", ""])
    assert biggest_m2ts(listing) == "BDMV\\STREAM\\00010.m2ts"
    assert biggest_m2ts("") is None


def test_detect_formats_probes_once_until_the_file_changes(tmp_path, monkeypatch):
    import os
    from biblio import catalog as catalog_mod, formats
    from biblio.db import Catalog
    from tests.fakes import settings_with
    s = settings_with(tmp_path, {"Library/Movies/Dune (2021).mkv": b"x"})
    cat = Catalog(tmp_path / "c.db")
    calls = []
    monkeypatch.setattr(formats, "tools", lambda: ("ffprobe", "7z"))
    monkeypatch.setattr(formats, "probe", lambda root, rel, kind: calls.append(rel) or summarize([HEVC_4K, ATMOS]))
    catalog_mod.refresh(s, cat, None)
    catalog_mod.refresh(s, cat, None)
    it = cat.items("movies")[0]
    assert calls == ["Library/Movies/Dune (2021).mkv"]
    assert badges(cat.format(it.id)) == ["4K", "HDR10", "ATMOS"]
    p = s.media_root / it.relpath
    p.write_bytes(b"replaced, bigger")
    os.utime(p, (1, 1))
    catalog_mod.refresh(s, cat, None)
    assert len(calls) == 2


def test_failed_probe_is_not_retried_and_item_api_has_no_badges(tmp_path, monkeypatch, client=None):
    from biblio import catalog as catalog_mod, formats
    from biblio.db import Catalog
    from tests.fakes import settings_with
    s = settings_with(tmp_path, {"Library/Movies/Broken (2020).iso": b"x"})
    cat = Catalog(tmp_path / "c.db")
    calls = []
    def boom(root, rel, kind):
        calls.append(rel)
        raise RuntimeError("ISO sin BDMV/STREAM")
    monkeypatch.setattr(formats, "tools", lambda: ("ffprobe", "7z"))
    monkeypatch.setattr(formats, "probe", boom)
    catalog_mod.refresh(s, cat, None)
    catalog_mod.refresh(s, cat, None)
    assert len(calls) == 1 and badges(cat.format(cat.items("movies")[0].id)) == []


def test_source_of_a_video_file():
    from biblio.formats import source_of
    otto = {"res": "4K", "audio": "DD+", "atmos": True}               # 27 Mbps, DD+ Atmos: a WEB-DL
    assert source_of(otto, 27.1) == "web"
    assert source_of({"res": "4K", "audio": "TrueHD"}, 58.0) == "remux"
    assert source_of({"res": "4K", "audio": "TrueHD"}, 20.0) is None   # lossless but squeezed: an encode
    assert source_of({"res": "1080p", "audio": "DTS-HD MA"}, 24.0) == "remux"
    assert source_of({"res": "1080p", "audio": "DTS"}, 9.0) is None


def test_source_token_in_the_release_name():
    from biblio.badges import release_name
    assert ".BluRay.Remux." in release_name({"res": "4K", "hdr": [], "source": "remux"})
    assert ".WEB-DL." in release_name({"res": "4K", "hdr": [], "source": "web"})
    assert "BluRay" not in release_name({"res": "1080p", "hdr": []})


def test_best_audio_track_not_the_first():
    dub = {"codec_type": "audio", "codec_name": "ac3", "channels": 2}
    truehd = {"codec_type": "audio", "codec_name": "truehd", "channels": 6}
    f = summarize([HEVC_4K, dub, dub, truehd, {"codec_type": "audio", "codec_name": "ac3", "channels": 6}])
    assert (f["audio"], f["ch"]) == ("TrueHD", "5.1")


def test_clpi_audio_of_a_3d_disc():
    from biblio.formats import clpi_audio
    # Life of Pi 3D: DTS-HD MA eng (0x86, multichannel), DTS spa, AC-3 dan
    data = bytes.fromhex("0000" "1100158661656e67" "0000" "1101158261737061" "0000" "1102158161 64616e".replace(" ", "")) + bytes(10)
    assert clpi_audio(data) == ("DTS-HD MA", "5.1")
    assert clpi_audio(b"") == (None, None)


def test_most_common_season_format():
    from biblio.formats import most_common
    a = {"res": "4K", "hdr": ["HDR10"], "audio": "DD+", "atmos": True}
    b = {"res": "1080p", "hdr": [], "audio": "DD"}
    assert most_common([a, a, b, None]) is a       # 4K shared by most
    assert most_common([None, None]) is None
    assert most_common([]) is None
