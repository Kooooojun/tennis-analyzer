import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
FPS = 60
PORTRAIT = (540, 960)  # proxy size before landscape support; strokes saved without "size" are this
# indices kept per frame in the web data: nose, shoulders, elbows, wrists, hips, knees, ankles, heels, toes
KEEP = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]


def session(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) < 2:
        sys.exit(f"usage: {Path(argv[0]).name} <session, e.g. 2026-11-05>")
    s = argv[1]
    if not (ROOT / "videos" / s).is_dir():
        sys.exit(f"videos/{s}/ not found")
    return s


def work(s):
    return ROOT / "work" / s


def web(s):
    return ROOT / "web" / "sessions" / s


def videos(s):
    """Work subdirs in clock order: the n-th video is shown as 'n·m:ss' on the page."""
    return json.loads((work(s) / "videos.json").read_text())


def size(proxy):
    """(width, height) of a proxy.mp4: 540x960 portrait or 960x540 landscape."""
    import cv2
    cap = cv2.VideoCapture(str(proxy)); wh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
    if not all(wh): sys.exit(f"cannot read {proxy}")
    return wh


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        sys.exit(f"missing {p.relative_to(ROOT)}")
    return json.loads(p.read_text())


def save(p, obj, compact=False):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact
                       else json.dumps(obj, ensure_ascii=False, indent=1))
