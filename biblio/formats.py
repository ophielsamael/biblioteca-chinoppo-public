"""Video/audio format of each title (4K, HDR10, HDR10+, Dolby Vision, Atmos, DTS:X...).

MKV/MP4/TS: ffprobe reads the file itself (only the headers and a few frames).
ISO: 7-Zip lists the disc (UDF) and streams the start of the biggest .m2ts, which is the main title;
BDMV folder: the same .m2ts read straight from the folder. ffprobe then looks at that sample.
On a UHD Blu-ray, Dolby Vision is a second HEVC stream (the enhancement layer, 1920x1080).
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("biblioteca.formats")

VERSION = 4   # bump when probe() learns something new: every title is probed again once
SAMPLE = 60 * 1024 * 1024      # the head of a .m2ts holds every stream of the title
TIMEOUT = 180

AUDIO_NAMES = {"truehd": "TrueHD", "eac3": "DD+", "ac3": "DD", "flac": "FLAC", "aac": "AAC",
               "opus": "Opus", "mp3": "MP3", "pcm_bluray": "LPCM", "pcm_s16le": "LPCM", "pcm_s24le": "LPCM"}


def tools() -> tuple[str | None, str | None]:
    """(ffprobe, 7z) paths, None when missing."""
    return shutil.which("ffprobe"), next(filter(None, map(shutil.which, ("7zz", "7z", "7za"))), None)


# --- pure parts ---------------------------------------------------------------

def biggest_m2ts(listing: str) -> str | None:
    """Path of the largest BDMV/STREAM/*.m2ts in a `7z l -slt` listing."""
    best, size, path = None, -1, None
    for line in listing.splitlines():
        if line.startswith("Path = "):
            path = line[7:].strip()
        elif line.startswith("Size = ") and path:
            p = path.replace("\\", "/").upper()
            n = int(line[7:].strip() or 0)
            if p.endswith(".M2TS") and "/STREAM/" in p and "/BACKUP/" not in p and n > size:
                best, size = path, n
            path = None
    return best


def _res(w: int, h: int) -> str:
    if w >= 3200 or h >= 2000:
        return "4K"
    if w >= 1800 or h >= 1000:
        return "1080p"
    if w >= 1200 or h >= 700:
        return "720p"
    return "SD"


RANK = ["MP3", "AAC", "Opus", "DD", "DTS", "DD+", "DTS-HD HRA", "FLAC", "LPCM", "DTS-HD MA", "TrueHD"]   # worst..best


def _audio_name(t: dict) -> str | None:
    codec, prof = t.get("codec_name", ""), t.get("profile") or ""
    if codec == "dts":
        return "DTS-HD MA" if "MA" in prof else "DTS-HD HRA" if "HRA" in prof else "DTS"
    return AUDIO_NAMES.get(codec, codec.upper() or None)


def summarize(streams: list[dict], frame_side_data: list[dict] = ()) -> dict:
    """ffprobe streams (+ side data of the first video frames) -> what the badges need."""
    video = [s for s in streams if s.get("codec_type") == "video"
             and (s.get("disposition") or {}).get("attached_pic") != 1]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    out = {"res": None, "hdr": [], "dv_profile": None, "3d": False,
           "audio": None, "ch": None, "atmos": False, "dtsx": False}
    if video:
        v = video[0]
        out["res"] = _res(v.get("width") or 0, v.get("height") or 0)
        side = [d for s in video for d in s.get("side_data_list", [])]
        dovi = next((d for d in side if "DOVI" in d.get("side_data_type", "")), None)
        hevc = [s for s in video if s.get("codec_name") == "hevc"]
        if dovi:
            out["dv_profile"] = dovi.get("dv_profile")
        elif len(hevc) >= 2:                      # UHD Blu-ray: base layer + enhancement layer
            out["dv_profile"] = 7
        if out["dv_profile"] is not None:
            out["hdr"].append("DV")
        if any("2094-40" in d.get("side_data_type", "") for d in frame_side_data):
            out["hdr"].append("HDR10+")
        trc = v.get("color_transfer")
        if trc == "smpte2084":
            out["hdr"].append("HDR10")
        elif trc == "arib-std-b67":
            out["hdr"].append("HLG")
        out["3d"] = any("stereo" in (s.get("profile") or "").lower() or s.get("codec_name") == "mvc"
                        for s in video) or any("Stereo 3D" in d.get("side_data_type", "") for d in side)
    if audio:
        profiles = [a.get("profile") or "" for a in audio]
        out["atmos"] = any("Atmos" in p for p in profiles)
        out["dtsx"] = any("DTS:X" in p for p in profiles)
        # the best track, not the first: MKVs often start with a DD dub before the TrueHD original
        a = max(audio, key=lambda t: (RANK.index(_audio_name(t)) if _audio_name(t) in RANK else -1,
                                      t.get("channels") or 0))
        out["audio"] = _audio_name(a)
        out["ch"] = {1: "1.0", 2: "2.0", 6: "5.1", 8: "7.1"}.get(a.get("channels"), a.get("channels"))
    return out


LOSSLESS = ("TrueHD", "DTS-HD MA", "LPCM", "FLAC")


def source_of(fmt: dict, mbps: float | None) -> str | None:
    """Where a video file comes from, as far as its streams tell (seen 2026-11-04: a 4K MKV at
    27 Mbps with DD+ Atmos was shown as BluRay; it is a WEB-DL).
    remux: lossless main audio and a disc-like bitrate; web: streaming audio (DD+/AAC/Opus)."""
    if fmt.get("audio") in LOSSLESS and mbps and mbps >= (30 if fmt.get("res") == "4K" else 15):
        return "remux"
    if fmt.get("audio") in ("DD+", "AAC", "Opus"):
        return "web"
    return None


CLPI_AUDIO = {0x80: "LPCM", 0x81: "DD", 0x82: "DTS", 0x83: "TrueHD", 0x84: "DD+", 0x85: "DTS-HD HRA", 0x86: "DTS-HD MA"}


def clpi_audio(data: bytes) -> tuple[str | None, str | None]:
    """Best audio track listed in a Blu-ray CLPI (clip info): (codec, channels). Each stream entry is
    PID (2 bytes, audio 0x11xx), length, coding type, format<<4|rate, language (3 letters).
    The format only says mono / stereo / multichannel: multichannel is shown as 5.1."""
    best, ch = None, None
    for i in range(len(data) - 8):
        code = data[i + 3]
        if data[i] == 0x11 and code in CLPI_AUDIO and data[i + 5:i + 8].isalpha():
            name = CLPI_AUDIO[code]
            if best is None or RANK.index(name) > RANK.index(best):
                best = name
                ch = {1: "1.0", 3: "2.0", 6: "5.1", 12: "5.1"}.get(data[i + 4] >> 4)
    return best, ch


def most_common(fmts: list[dict | None]) -> dict | None:
    """The format shared by most items (a season's episodes), by their badge set; None if none."""
    from collections import Counter
    good = [f for f in fmts if f and f.get("res")]
    if not good:
        return None
    key = Counter(tuple(badges(f)) for f in good).most_common(1)[0][0]
    return next(f for f in good if tuple(badges(f)) == key)


def badges(fmt: dict | None) -> list[str]:
    """Short labels in display order, e.g. ['4K', 'DV', 'HDR10', 'ATMOS']."""
    if not fmt or not fmt.get("res"):
        return []
    out = [fmt["res"]] if fmt["res"] in ("4K", "1080p") else []
    out += [h for h in fmt["hdr"] if h != "HDR10" or len(fmt["hdr"]) == 1]  # HDR10 is implied by DV/HDR10+
    if fmt.get("3d"):
        out.append("3D")
    if fmt.get("atmos"):
        out.append("ATMOS")
    elif fmt.get("dtsx"):
        out.append("DTS:X")
    elif fmt.get("audio") in ("TrueHD", "DTS-HD MA"):
        out.append(fmt["audio"])
    return out


# --- running the tools --------------------------------------------------------

def _ffprobe(ffprobe: str, path: str) -> dict:
    base = [ffprobe, "-v", "error", "-probesize", "60M", "-analyzeduration", "20M", "-of", "json"]
    info = json.loads(subprocess.run(
        base + ["-show_streams", "-show_format", path], capture_output=True, timeout=TIMEOUT, check=True).stdout)
    streams = info.get("streams", [])
    frames = json.loads(subprocess.run(
        base + ["-select_streams", "v:0", "-read_intervals", "%+#4", "-show_entries", "frame=side_data_list", path],
        capture_output=True, timeout=TIMEOUT).stdout or b"{}").get("frames", [])
    side = [d for f in frames for d in f.get("side_data_list", [])]
    out = summarize(streams, side)
    try:
        out["mbps"] = round(int(info["format"]["bit_rate"]) / 1e6, 1)
    except (KeyError, ValueError, TypeError):
        out["mbps"] = None
    return out


def _head(src, dst: str) -> None:
    with open(dst, "wb") as out:
        left = SAMPLE
        while left > 0:
            chunk = src.read(min(left, 1 << 20))
            if not chunk:
                break
            out.write(chunk)
            left -= len(chunk)


def probe(media_root: Path, relpath: str, kind: str) -> dict:
    """Format of one title. Raises on tools missing or an unreadable file."""
    ffprobe, sevenzip = tools()
    if not ffprobe:
        raise RuntimeError("ffprobe no instalado")
    full = Path(media_root) / relpath
    if kind == "file":
        fmt = _ffprobe(ffprobe, str(full))
        return dict(fmt, source=source_of(fmt, fmt.get("mbps")))
    with tempfile.TemporaryDirectory() as tmp:
        sample = os.path.join(tmp, "head.m2ts")
        if kind == "bdmv":
            streams = sorted((full / "BDMV" / "STREAM").glob("*.m2ts"), key=lambda p: p.stat().st_size)
            if not streams:
                raise RuntimeError("BDMV sin .m2ts")
            with open(streams[-1], "rb") as src:
                _head(src, sample)
        elif kind == "iso":
            if not sevenzip:
                raise RuntimeError("7-Zip no instalado")
            # no check=True: ISOs burnt with FoxBurner list fine but 7-Zip exits 2 ("Headers Error")
            listing = subprocess.run([sevenzip, "l", "-slt", str(full)], capture_output=True,
                                     timeout=TIMEOUT).stdout.decode("utf-8", "replace")
            main = biggest_m2ts(listing)
            if not main and "VIDEO_TS" in listing.upper():     # a DVD image
                return dict(summarize([]), res="SD", source="dvd")
            if not main:   # say what 7-Zip answered: the log is all there is on the homelab
                tail = " | ".join(l for l in listing.splitlines() if l.strip())[-300:]
                raise RuntimeError(f"ISO sin BDMV/STREAM ({os.path.basename(sevenzip)}): {tail}")
            p = subprocess.Popen([sevenzip, "e", "-so", str(full), main], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
            try:
                _head(p.stdout, sample)
            finally:
                p.kill()
                p.wait()
            if "\\SSIF\\" in listing.upper() or "/SSIF/" in listing.upper():
                # Blu-ray 3D: 7-Zip can't extract its interleaved .m2ts ("Unsupported Method");
                # a BD3D is always 1080p, audio stays unknown in that case
                if os.path.getsize(sample) == 0:
                    clip = main.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    clpi = subprocess.run([sevenzip, "e", "-so", str(full), f"BDMV/CLIPINF/{clip}.clpi"],
                                          capture_output=True, timeout=TIMEOUT).stdout
                    audio, ch = clpi_audio(clpi)
                    return dict(summarize([]), res="1080p", source="disc", audio=audio, ch=ch, **{"3d": True})
                return dict(_ffprobe(ffprobe, sample), source="disc", **{"3d": True})
        else:
            raise ValueError(kind)
        if os.path.getsize(sample) == 0:
            raise RuntimeError("no se pudo leer el .m2ts principal")
        return dict(_ffprobe(ffprobe, sample), source="disc")


def signature(media_root: Path, relpath: str) -> str:
    """Changes when the file is replaced (size + mtime); for BDMV folders, the folder's mtime."""
    st = (Path(media_root) / relpath).stat()
    return f"{VERSION}:{st.st_size}:{int(st.st_mtime)}"
