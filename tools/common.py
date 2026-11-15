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


def tracks(d):
    """Tracked people in one video's work dir d: [0, 1, ..]. pose.npy is track 0, pose_t1.npy track 1 (see pose_full.py)."""
    return [0] + sorted(int(p.stem[6:]) for p in d.glob("pose_t*.npy"))


def track_file(d, kind, k=0):
    """kind 'pose', 'pose_world' or 'match' -> d/pose.npy for track 0, d/pose_t2.npy for track 2."""
    return d / f"{kind}{f'_t{k}' if k else ''}.npy"


def players(s):
    """work/<s>/players.txt -> {(video no, track): name}. One line per tracked person: '<video no> <track> <name>', name x = ignore."""
    p = work(s) / "players.txt"
    if not p.exists(): return {}
    rows = [l.split("#")[0].split() for l in p.read_text().splitlines()]; rows = [r for r in rows if r]
    bad = [r for r in rows if len(r) != 3 or not (r[0].isdigit() and r[1].isdigit()) or r[2] == "?"]
    if bad: sys.exit(f"players.txt lines must be '<video no> <track> <name>' (fill in every ?): {bad[:5]}")
    return {(int(r[0]), int(r[1])): r[2] for r in rows}


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


def load_profiles():
    """work/profiles.json (private, not in git): {"<player>": {"hand": "R"|"L", "backhand": "one"|"two"}}. Missing file = {}."""
    return load(ROOT / "work" / "profiles.json", {})


def profile_for(profiles, name):
    """Validated profile of one player, or None when not set (then the hand is guessed and flagged). Bad values raise, never default to R."""
    p = profiles.get(name)
    if p is None: return None
    if not isinstance(p, dict) or p.get("hand") not in ("R", "L") or p.get("backhand") not in (None, "one", "two"):
        raise ValueError(f"profiles.json['{name}'] must look like {{'hand': 'R'|'L', 'backhand': 'one'|'two'}}, got {p!r}")
    return {"hand": p["hand"], "backhand": p.get("backhand")}  # None = not said: no one-hand checks unless refine.json says so
