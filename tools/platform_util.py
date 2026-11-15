# Platform helpers shared by prep, setup, annotate and friends: venv path, H.264 encoder choice, UTF-8 text I/O,
# and replace/unlink that retry while Windows Defender or the indexer briefly locks a file (PermissionError).
import os, shutil, subprocess, sys, time
from functools import lru_cache
from pathlib import Path

UTF8_HINT = "請以 UTF-8 儲存；用 Write 工具寫檔，不要用 shell 重導向（>、Set-Content）"


def venv_python(root):
    return Path(root) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def read_text(p):
    """UTF-8 text, BOM tolerated. A UTF-16 / ANSI file (PowerShell `>`, Set-Content) stops with a message naming it."""
    try:
        return Path(p).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        sys.exit(f"{p}: 不是 UTF-8 文字檔。{UTF8_HINT}")


def write_text(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:  # LF on Windows too: candidates.py fingerprints labels.txt bytes
        f.write(s)


def retry(fn, tries=5, wait=0.2):
    for i in range(tries):
        try:
            return fn()
        except PermissionError:
            if i == tries - 1: raise
            time.sleep(wait)


def replace(src, dst):
    retry(lambda: os.replace(src, dst))


def unlink(p):
    retry(lambda: Path(p).unlink(missing_ok=True))


def stale(out, *ins):
    """True when out is not a file or any input is strictly newer, so a re-run upstream rebuilds what hangs off it."""
    out = Path(out)
    if not out.is_file(): return True
    t = out.stat().st_mtime
    return any(Path(i).stat().st_mtime > t for i in ins)


def need_ffmpeg():
    miss = [x for x in ("ffmpeg", "ffprobe") if not shutil.which(x)]
    if miss:
        sys.exit(f"找不到 {', '.join(miss)}。macOS: brew install ffmpeg；Windows: winget install Gyan.FFmpeg（裝完開新終端機）；Linux: apt install ffmpeg")


@lru_cache(None)
def _nvenc():
    try:
        if "h264_nvenc" not in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout: return False
        # listed on machines without an NVIDIA GPU too: only trust a real 1-frame encode
        return subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256", "-frames:v", "1", "-c:v", "h264_nvenc",
                               "-f", "null", "-"], capture_output=True).returncode == 0
    except OSError:
        return False


def h264_args(mac_bitrate, crf):
    if sys.platform == "darwin": return ["-c:v", "h264_videotoolbox", "-b:v", mac_bitrate]
    if _nvenc(): return ["-c:v", "h264_nvenc", "-cq", str(crf)]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf)]


def imwrite(p, img, params=()):
    """cv2.imwrite that works on non-ASCII paths (it fails silently there on Windows): encode in memory, write the bytes.
    Returns False and prints the path when it fails."""
    import cv2
    try:
        ok, buf = cv2.imencode(Path(p).suffix, img, list(params))
        if ok: buf.tofile(str(p))
    except (OSError, cv2.error):
        ok = False
    if not ok: print(f"warning: could not write {p}", file=sys.stderr)
    return bool(ok)
