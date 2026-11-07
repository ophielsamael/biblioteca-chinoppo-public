from biblio.scan import scan_folder, scan_series


def test_series_tree(tmp_path):
    make(tmp_path, "Library/SERIES/The Last of Us/S02/S02e06E07e08.iso",
         "Library/SERIES/The Last of Us/S01/s01e01e02.iso", "Library/SERIES/The Last of Us/S01/s01e01.nfo",
         "Library/SERIES/Fresh Off the Boat/S04/ S04E01 M de mejores amigas.mkv",
         "Library/SERIES/Fresh Off the Boat/S04/Extras.mkv", "Library/SERIES/@eaDir/x/S01E01.mkv",
         "Library/SERIES/.DS_Store")
    shows = {s.name: s for s in scan_series(tmp_path, "Library/SERIES")}
    assert set(shows) == {"The Last of Us", "Fresh Off the Boat"}
    tlou = sorted((f.season, f.episodes, f.kind) for f in shows["The Last of Us"].files)
    assert tlou == [(1, [1, 2], "iso"), (2, [6, 7, 8], "iso")]
    fob = shows["Fresh Off the Boat"]
    assert fob.relpath == "Library/SERIES/Fresh Off the Boat"
    assert [f.relpath for f in fob.files] == ["Library/SERIES/Fresh Off the Boat/S04/ S04E01 M de mejores amigas.mkv"]
    assert fob.skipped == ["Library/SERIES/Fresh Off the Boat/S04/Extras.mkv"]


def test_series_missing_root_is_none(tmp_path):
    assert scan_series(tmp_path, "Library/SERIES") is None


def make(tmp, *paths):
    for p in paths:
        q = tmp / p
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(b"x")


def test_only_video_and_bdmv(tmp_path):
    make(tmp_path, "Library/ATMOS/1917 (2019).iso", "Library/ATMOS/1917 (2019).nfo",
         "Library/ATMOS/1917 (2019)-fanart.jpg", "Library/ATMOS/@eaDir/x.mkv",
         "Library/ATMOS/Alien (1979)/BDMV/index.bdmv", "Library/Movies/Oblivion (2013).srt",
         "Library/ATMOS/Dune (2021).mkv")
    got = [(e.relpath, e.kind) for e in scan_folder(tmp_path, "Library/ATMOS")]
    assert got == [("Library/ATMOS/1917 (2019).iso", "iso"),
                   ("Library/ATMOS/Alien (1979)", "bdmv"),
                   ("Library/ATMOS/Dune (2021).mkv", "file")]
    assert scan_folder(tmp_path, "Library/Movies") == []


def test_missing_folder_is_unknown_not_empty(tmp_path):
    assert scan_folder(tmp_path, "Library/NOPE") is None
