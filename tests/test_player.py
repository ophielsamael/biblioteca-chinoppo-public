import time

import pytest

from biblio.chinoppo import Chinoppo
from biblio.player import SETTLE, Player
from biblio.scan import Entry
from tests.fakes import FakeChinoppo

MOVIES = "volume1/Plex/Library/Movies"       # configured folders (web page) are what gets mounted
ATMOS = "volume1/Plex/Library/ATMOS"
LIBDIR = "volume1/Plex/Biblioteca"
SWAN = "/mnt/nfs1/Black Swan (2010).mkv"
AVATAR = "/mnt/nfs1/Avatar (2009)/Avatar.iso"
LIBRARY = "/mnt/nfs1/Biblioteca.iso"


@pytest.fixture
def box():
    return FakeChinoppo()


@pytest.fixture
def item(catalog):
    from biblio.scan import Entry
    i = catalog.upsert_item("movies", Entry("Library/Movies/Black Swan (2010).mkv", "Black Swan (2010)", "file"),
                            "Black Swan", 2010)
    return catalog.get(i)


@pytest.fixture
def nested(catalog):
    """A title one level below its configured folder (the subpath case)."""
    i = catalog.upsert_item("atmos", Entry("Library/ATMOS/Avatar (2009)/Avatar.iso", "Avatar (2009)", "iso"),
                            "Avatar", 2009)
    return catalog.get(i)


@pytest.fixture
def player(settings, catalog, box):
    return Player(settings, catalog, box, sleep=lambda s: time.sleep(min(s, 0.01)))


def mounted(player, box, folder=MOVIES):
    box.mounted = player._mounted = folder


def test_fast_path_plays_from_mounted_folder_without_mounting(player, box, item):
    box.state = "bdmv"
    mounted(player, box)
    assert player._sequence(item, False) == "ok"
    assert ("play_file", SWAN) in box.calls
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_never_mounts_the_share_root(player, box, item, nested):
    # seen 2026-11-03: with volume1/Plex mounted the player indexes all ~300k entries and stalls
    player._sequence(item, False)
    box.state = "idle"
    player._sequence(nested, False)
    player._recover()
    mounts = [c[2] for c in box.calls if c[0] == "mount_nfs"]
    assert mounts and "volume1/Plex" not in mounts


def test_accepted_fast_play_gets_time_for_big_iso(player, box, item):
    box.start_after = 15   # e.g. Avatar UHD ISO
    mounted(player, box)
    assert player._sequence(item, False) == "ok"
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_rejected_fast_play_falls_back_without_waiting(settings, catalog, box, item):
    slept = []
    p = Player(settings, catalog, box, sleep=slept.append)
    assert p._sequence(item, False) == "ok"          # nothing mounted: fast order is rejected
    assert sum(slept[:slept.index(2)] if 2 in slept else slept) < 8   # straight to mounting


def test_fast_order_timeout_falls_back_to_mount(player, box, item):
    from biblio.chinoppo import ChinoppoError
    mounted(player, box)
    real, first = box.play_file, [True]
    def play(path, server, t):
        if first.pop() if first else False:
            raise ChinoppoError("timed out")
        return real(path, server, t)
    box.play_file = play
    assert player._sequence(item, False) == "ok"
    assert ("mount_nfs", "192.168.1.17", MOVIES) in box.calls


def test_stale_mount_does_not_mark_title_slow(player, box, item, catalog):
    mounted(player, box)
    box.mounted = None                               # the player dropped the mount on its own
    assert player._sequence(item, False) == "ok"
    assert catalog.get_state("needs_mount:" + item.relpath) is None


def test_fallback_closes_a_disc_left_open_before_mounting(player, box, nested):
    box.accept_but_hang = True
    mounted(player, box, ATMOS)
    assert player._sequence(nested, False) == "ok"
    names = [c[0] for c in box.calls]
    assert names.index("send_key") < names.index("mount_nfs")   # never mount with a disc open


def test_player_busy_while_loading_is_not_a_failure(player, box, item):
    mounted(player, box)
    real = box.play_file
    def play(path, server, t):
        r = real(path, server, t)
        box.flaky_polls = 2                            # API stops answering for a moment
        return r
    box.play_file = play
    assert player._sequence(item, False) == "ok"
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_title_that_needed_mount_skips_fast_path_next_time(player, box, nested):
    box.accept_but_hang = True                     # accepted via its subfolder, never starts (Avatar)
    mounted(player, box, ATMOS)
    assert player._sequence(nested, False) == "ok"
    box.calls.clear()
    box.state = "idle"
    mounted(player, box, ATMOS)
    assert player._sequence(nested, False) == "ok"
    assert ("play_file", AVATAR) not in box.calls    # straight to mounting its own folder


def test_fast_path_walks_folders_before_playing(player, box, nested):
    box.subpath_ok = True
    mounted(player, box, ATMOS)
    assert player._sequence(nested, False) == "ok"
    walk = [c[1] for c in box.calls if c[0] == "list_dir"]
    assert walk == ["/mnt/nfs1", "/mnt/nfs1/Avatar (2009)"]
    assert box.calls.index(("play_file", AVATAR)) > box.calls.index(("list_dir", "/mnt/nfs1/Avatar (2009)"))
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_unmounted_share_goes_straight_to_mounting(player, box, item):
    assert player._sequence(item, False) == "ok"   # nothing mounted after a reboot
    first_mount = next(i for i, c in enumerate(box.calls) if c[0] == "mount_nfs")
    assert ("play_file", SWAN) not in box.calls[:first_mount]   # no 30 s hanging order
    assert [c[2] for c in box.calls if c[0] == "mount_nfs"] == [MOVIES]


def test_other_folder_mounted_means_mounting_this_one(player, box, item):
    mounted(player, box, ATMOS)
    assert player._sequence(item, False) == "ok"
    assert [c[2] for c in box.calls if c[0] == "mount_nfs"] == [MOVIES]


def test_fast_path_bdmv_folder(player, box, catalog):
    from biblio.scan import Entry
    rel = "Library/ATMOS/The Lord of the Rings The Two Towers (2002)"
    i = catalog.upsert_item("atmos", Entry(rel, rel.split("/")[-1], "bdmv"), "The Two Towers", 2002)
    mounted(player, box, ATMOS)
    assert player._sequence(catalog.get(i), False) == "ok"
    assert ("check_bdmv", "/mnt/nfs1/The Lord of the Rings The Two Towers (2002)") in box.calls
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_watcher_waits_before_reopening_library(settings, catalog, box, item):
    events = []
    p = Player(settings, catalog, box, sleep=lambda s: events.append(("sleep", s)))
    mounted(p, box, LIBDIR)
    real_play = box.play_file
    box.play_file = lambda path, server, t: events.append(("play_file", path)) or real_play(path, server, t)
    p.launched_by_library = item.id
    box.state = "playing"
    p.watch_once()
    box.state = "idle"
    p.watch_once()
    i = events.index(("play_file", LIBRARY))
    assert ("sleep", SETTLE) in events[:i]        # seen live: reopening right at STOP shows "No se puede reproducir"


def test_recover_prefers_library_on_usb_stick(player, box):
    box.usb = True
    player._recover()
    assert box.calls == [("play_file", "/mnt/sda1/Biblioteca.iso")]


def test_recover_retries_stick_before_mounting_nas(player, box):
    # seen live: right after STOP of an ISO the first open shows "No se puede reproducir"
    box.usb = True
    real, first = box.play_file, [True]
    box.play_file = lambda p, s, t: {"success": False} if first and first.pop() else real(p, s, t)
    player._recover()
    assert not any(c[0] == "mount_nfs" for c in box.calls)
    assert box.state == "bdmv"


def test_fallback_mounts_configured_folder_so_next_titles_are_fast(player, box, item):
    assert player._sequence(item, False) == "ok"
    assert [c[2] for c in box.calls if c[0] == "mount_nfs"] == [MOVIES]
    assert box.calls[-1] == ("play_file", SWAN)
    box.calls.clear()
    box.state = "idle"
    assert player._sequence(item, False) == "ok"
    assert not any(c[0] == "mount_nfs" for c in box.calls)


def test_recover_reopens_library_without_mount_when_its_folder_is_mounted(player, box):
    mounted(player, box, LIBDIR)
    player._recover()
    assert box.calls == [("play_file", "/mnt/sda1/Biblioteca.iso")] * 2 + [("play_file", LIBRARY)]   # no stick


def test_from_library_disc_stops_then_mounts_folder_and_plays_name(player, box, item):
    box.state = "bdmv"
    assert player._sequence(item, resume=False) == "ok"
    # nothing mounted: no fast attempt, mount its configured folder (also its own) and play
    mounts = [c[2] for c in box.calls if c[0] == "mount_nfs"]
    first_mount = next(i for i, c in enumerate(box.calls) if c[0] == "mount_nfs")
    assert box.calls[0] == ("send_key", "STP")
    assert not any(c[0] == "play_file" for c in box.calls[:first_mount])   # share not mounted: no order
    assert mounts == [MOVIES]
    assert box.calls[-1] == ("play_file", SWAN)
    assert player.launched_by_library == item.id


def test_waits_before_stp_and_retries_once(settings, catalog, box, item):
    slept = []
    p = Player(settings, catalog, box, sleep=slept.append)
    box.state = "bdmv"
    box.on_key_stp = "ignore_first"
    assert p._sequence(item, False) == "ok"
    assert slept[0] == 2                      # let the disc finish handling OK first
    assert [c for c in box.calls if c[0] == "send_key"] == [("send_key", "STP")] * 2 + [("send_key", "HOM")]


def test_iso_plays_from_its_own_folder(player, box, catalog):
    from biblio.scan import Entry
    i = catalog.upsert_item("atmos", Entry("Library/ATMOS/The Martian (2015).iso", "The Martian (2015)", "iso"),
                            "The Martian", 2015)
    box.state = "bdmv"
    assert player._sequence(catalog.get(i), False) == "ok"
    assert ("mount_nfs", "192.168.1.17", "volume1/Plex/Library/ATMOS") in box.calls
    assert ("play_file", "/mnt/nfs1/The Martian (2015).iso") in box.calls


def test_bdmv_folder_uses_checkfolderhasbdmv(player, box, catalog):
    from biblio.scan import Entry
    rel = "Library/ATMOS/The Lord of the Rings The Two Towers (2002)"
    i = catalog.upsert_item("atmos", Entry(rel, rel.split("/")[-1], "bdmv"), "The Two Towers", 2002)
    assert player._sequence(catalog.get(i), False) == "ok"
    assert ("check_bdmv", "/mnt/nfs1/The Lord of the Rings The Two Towers (2002)") in box.calls
    assert not any(c[0] == "play_file" for c in box.calls)


def test_disc_does_not_close_aborts_without_mount(player, box, item):
    box.state = "bdmv"
    box.on_key_stp = "ignored"
    assert player._sequence(item, False) == "error:el disco no se cerró"
    assert not any(c[0] in ("mount_nfs", "login_nfs") for c in box.calls)


def test_mount_failure_aborts_without_play(player, box, item):
    box.mount_ok = False
    assert player._sequence(item, False) == "error:montaje"
    assert not any(c[0] == "play_file" for c in box.calls)   # nothing mounted, mount failed: no order


def test_mount_preceded_by_xnoppo_handshake(player, box, item):
    player._sequence(item, False)
    names = [c[0] for c in box.calls]
    i = names.index("login_nfs")
    assert names[i:i + 4] == ["login_nfs", "nfs_share_list", "setup_menu", "mount_nfs"]


def test_mount_retried_once_like_xnoppo(player, box, item):
    box.subpath_ok = True                            # once the root mounts, the full path plays
    results = iter([{"success": False, "retInfo": "busy"}])
    def mount(server, folder):
        box.calls.append(("mount_nfs", server, folder))
        r = next(results, {"success": True})
        if r["success"]:
            box.mounted = folder
        return r
    box.mount_nfs = mount
    assert player._sequence(item, False) == "ok"
    assert [c[0] for c in box.calls].count("login_nfs") == 2


def test_log_endpoint_shows_recent_lines(client):
    import logging
    logging.getLogger("biblioteca.player").info("play X -> error:montaje")
    assert "error:montaje" in client.get("/log").data.decode()


def test_not_started_reports_error(player, box, item):
    box.play_starts = False
    assert player._sequence(item, False) == "error:no arrancó"


def test_unreachable_returns_error_fast(player, box, item):
    box.unreachable = True
    t = time.time()
    assert player.play(item.id, False) == "error:sin respuesta"
    assert time.time() - t < 15 and ("wake",) in box.calls


def test_second_play_is_busy(player, box, item):
    box.block_play = True
    assert player.play(item.id, False) == "ok"
    assert player.play(item.id, False) == "busy"


def test_resume_sets_play_time_for_files(player, box, item, catalog):
    catalog.save_progress(item.id, 600, 6000)
    assert player._sequence(item, resume=True) == "ok"
    assert ("set_play_time", 600) in box.calls


def test_url_encodes_accents_and_ampersand():
    urls = []
    box = Chinoppo("192.168.1.16", get=lambda url, timeout: urls.append(url) or '{"success":true}')
    box.play_file("/mnt/nfs1/Library/ATMOS/Rock & Roll Ñandú (2001).mkv", "192.168.1.17", 5)
    assert "Rock%20%26%20Roll%20%C3%91and%C3%BA" in urls[0]
    assert urls[0].startswith("http://192.168.1.16:436/playnormalfile?{")


def test_watcher_reopens_library_only_for_its_own_playback(player, box, item, catalog):
    box.state = "playing"
    player.watch_once()
    box.state = "idle"
    player.watch_once()
    assert ("play_file", LIBRARY) not in box.calls
    player.launched_by_library = item.id
    box.state = "playing"
    box.cur, box.total = 3000, 6487
    player.watch_once()
    box.state = "idle"
    player.watch_once()
    assert box.calls[-2:] == [("mount_nfs", "192.168.1.17", LIBDIR), ("play_file", LIBRARY)]
    assert catalog.progress(item.id) == (3000, 6487)
    assert player.launched_by_library is None


def test_watcher_marks_watched_near_the_end(player, box, item, catalog):
    player.launched_by_library = item.id
    box.state = "playing"
    box.cur, box.total = 6300, 6487
    player.watch_once()
    box.state = "idle"
    player.watch_once()
    assert catalog.progress(item.id) == (0, 6487)


def test_new_play_forgets_previous_launch(player, box, item):
    player.launched_by_library = 999
    box.block_play = True
    assert player.play(item.id, False) == "ok"
    assert player.launched_by_library is None


def test_watcher_yields_while_a_play_is_running(player, box, item):
    player.launched_by_library = item.id
    player._busy.acquire()
    try:
        player.watch_once()
    finally:
        player._busy.release()
    assert box.calls == [] and player.launched_by_library == item.id


def test_reachability_uses_short_timeout(settings, catalog):
    timeouts = []
    def get(url, timeout):
        timeouts.append(timeout)
        raise OSError("timed out")
    from biblio.chinoppo import Chinoppo
    p = Player(settings, catalog, Chinoppo("192.168.1.16", get=get), sleep=lambda s: None)
    p.box.wake = lambda: None
    assert p._reachable() is False
    assert timeouts and max(timeouts) <= 3


def test_failure_after_closing_disc_reopens_library(player, box, item):
    box.state = "bdmv"
    box.mount_ok = False
    assert player._sequence(item, False) == "error:montaje"
    box.mount_ok = True     # the share root mounts fine; only the title's folder failed
    player._recover()
    assert box.calls[-1] == ("play_file", LIBRARY)


def test_play_thread_recovers_after_mount_error(settings, catalog, box, item):
    box.state = "bdmv"
    original = box.mount_nfs
    box.mount_nfs = lambda s, f: {"success": False} if f.endswith("Movies") else original(s, f)
    p = Player(settings, catalog, box, sleep=lambda s: None)
    assert p.play(item.id, False) == "ok"
    for _ in range(100):
        if not p._busy.locked():
            break
        time.sleep(0.01)
    assert box.calls[-1] == ("play_file", LIBRARY)


def test_autoopen_when_player_powers_on(player, box):
    box.unreachable = True
    player.watch_power()                       # off / standby
    box.unreachable = False
    player.watch_power()                       # just switched on, idle on its home
    assert box.calls[-1] == ("play_file", LIBRARY)


def test_no_autoopen_when_disabled(player, box, catalog):
    catalog.set_state("autoopen", "0")
    box.unreachable = True
    player.watch_power()
    box.unreachable = False
    player.watch_power()
    assert ("play_file", LIBRARY) not in box.calls


def test_no_autoopen_when_service_starts_with_player_on(player, box):
    player.watch_power()
    player.watch_power()
    assert box.calls == []


def test_no_autoopen_if_something_starts_during_grace(settings, catalog, box):
    def sleep(s):
        box.state = "playing"                  # e.g. Xnoppo launched a movie from Emby
    p = Player(settings, catalog, box, sleep=sleep)
    box.unreachable = True
    p.watch_power()
    box.unreachable = False
    p.watch_power()
    assert ("play_file", LIBRARY) not in box.calls


def test_play_episode_uses_its_iso_and_negative_progress_key(player, box, catalog, show_id):
    ep = catalog.file_for(show_id, 2, 3)
    box.state = "bdmv"
    assert player._sequence(player.target_for_episode(ep.id), False) == "ok"
    assert ("mount_nfs", "192.168.1.17", "volume1/Plex/Library/SERIES/The Last of Us/S02") in box.calls
    assert ("play_file", "/mnt/nfs1/S02E01e02e03.iso") in box.calls
    assert player.launched_by_library == -ep.id


def test_episode_with_leading_space_keeps_exact_name(player, box, catalog):
    from biblio.scan import EpisodeFile
    sid = catalog.upsert_item("series", Entry("Library/SERIES/F", "F", "series"), "F", None)
    catalog.set_episode_files(sid, [EpisodeFile("Library/SERIES/F/S04/ S04E01 M de mejores amigas.mkv",
                                                "file", 4, [1])])
    ep = catalog.file_for(sid, 4, 1)
    assert player._sequence(player.target_for_episode(ep.id), False) == "ok"
    assert ("play_file", "/mnt/nfs1/ S04E01 M de mejores amigas.mkv") in box.calls


def test_play_episode_endpoint(settings, catalog, box, show_id):
    from app import create_app
    p = Player(settings, catalog, box, sleep=lambda s: None)
    c = create_app(settings, catalog, player=p).test_client()
    box.unreachable = True
    ep = catalog.file_for(show_id, 2, 4)
    assert c.get(f"/d/play?ep={ep.id}").data.decode() == "error\tsin respuesta"
    assert c.get("/d/play?ep=9999").status_code == 404


def test_watcher_stops_on_standby(player, box, item):
    player.launched_by_library = item.id
    box.unreachable = True
    player.watch_once()
    assert player.launched_by_library is None


def test_play_endpoint(settings, catalog, box, item):
    from app import create_app
    p = Player(settings, catalog, box, sleep=lambda s: None)
    c = create_app(settings, catalog, player=p).test_client()
    box.unreachable = True
    assert c.get(f"/d/play?id={item.id}").data.decode() == "error\tsin respuesta"
    assert c.get("/d/play?id=999").status_code == 404


def test_recover_finds_stick_after_standby(player, box):
    # seen 2026-11-03: after standby the stick came back as /mnt/sdb1
    box.usb, box.usb_mount = True, "/mnt/sdb1"
    player._recover()
    assert box.calls == [("play_file", "/mnt/sdb1/Biblioteca.iso")]


def test_wake_with_a_movie_playing_closes_it_and_reopens_the_library(player, box):
    box.unreachable = True
    player.watch_power()                       # standby
    box.unreachable = False
    box.state = "playing"                      # a movie is still "playing" on wake
    player.launched_by_library = 123           # the service had launched it
    player.watch_power()                       # wake
    assert ("play_file", LIBRARY) in box.calls   # closed the movie and reopened the Biblioteca
