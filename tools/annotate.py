# annotate.py <session> [video] [--panel auto|tl|tr|bl|br] — whole practice video re-encoded with skeleton, stroke numbers, player names and a small live-stats panel
# -> web/sessions/<s>/annotated_<video>.mp4 (1280x720, 60 fps, original audio), ready to send to a friend. No video argument = every video in the session.
# Needs work/<s>/<video>/pose.npy (python tools/run.py prep.py). Stroke numbers and figures come from web/sessions/<s>/strokes.json (final numbers shown on the page);
# without it you still get the skeleton + live knee angle. Frames are streamed ffmpeg -> draw -> ffmpeg, so memory does not grow with video length.
# Drawing constants (fonts, colours, knee colouring) mirror tools/highlights.py, which is a script and cannot be imported.
import argparse, math, subprocess, sys, time, numpy as np, cv2
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import ROOT, FPS, session, work, web, videos, load, tracks, track_file
from platform_util import h264_args
from proxy import map_pose
from prep import probe_rate

LONG = 1280  # long side of the output, px
FONTS = ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/msjh.ttc"]
FONT = next((f for f in FONTS if Path(f).exists()), None) or sys.exit("no CJK font found; add one to FONTS in annotate.py")
INK = (240, 240, 240); MUTE = (160, 165, 175); GOOD = (74, 222, 128); WARN = (251, 191, 36); BAD = (248, 113, 113); GOLD = (255, 214, 10)
kc = lambda a: GOOD if a <= 130 else WARN if a <= 150 else BAD
# MediaPipe landmark indices: shoulders 11/12, elbows 13/14, wrists 15/16, hips 23/24, knees 25/26, ankles 27/28
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28)]
JOINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
KIND = {"FH": "正拍", "BH": "反拍", "SV": "發球", "OH": "高壓"}; DRILL = {"feed": "自拋", "rally": "對打", "high": "高球"}
PRE, POST = 30, 150  # a stroke's tag shows from 0.5 s before contact to 2.5 s after
MINVIS = 0.3
CORNERS = ("tl", "tr", "bl", "br")
PANEL_W, PANEL_MX, PANEL_MY = 320, 10, 8
_fonts = {}
def F(n): return _fonts.setdefault(n, ImageFont.truetype(FONT, n))


def probe(src):
    """(w, h) after rotation, the same view ffmpeg decodes."""
    return probe_rate(src)[:2]


def angle(a, b, c):
    v1, v2 = a - b, c - b; n = np.linalg.norm(v1) * np.linalg.norm(v2)
    return float(np.degrees(np.arccos(np.clip(v1 @ v2 / n, -1, 1)))) if n else None


def live_knee(p, w, size):
    """(angle, knee landmark) of the more bent knee; 3D when pose_world exists (same rule as highlights.py), else 2D in pixels."""
    pts = lambda a: [(w[i] if w is not None else p[i, :2] * size) for i in a]
    r = angle(*pts((24, 26, 28))); l = angle(*pts((23, 25, 27)))
    return (r, 26) if r is not None and l is not None and r <= l else (l, 25) if l is not None and r is not None else (None, None)


def draw_text(img, x, y, s, size, col, anchor="la"):
    """Draw CJK text with PIL on just the small region it covers, then paste it back (a full 720p PIL round trip per frame is too slow)."""
    f = F(size); l, t, r, b = f.getbbox(s, anchor=anchor, stroke_width=3); x0, y0 = int(x + l) - 2, int(y + t) - 2; x1, y1 = int(x + r) + 2, int(y + b) + 2
    H, W = img.shape[:2]; x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0: return
    pil = Image.fromarray(cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(pil).text((x - x0, y - y0), s, font=f, fill=col, anchor=anchor, stroke_width=3, stroke_fill=(0, 0, 0))
    img[y0:y1, x0:x1] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def stroke_info(x):
    k = x["knee3d"] if x.get("knee3d") is not None else x["knee"]
    head = f"#{x['no']:02d} {KIND.get(x['kind'], x['kind'])}" + (f"·{DRILL[x['drill']]}" if x.get("drill") in DRILL else "")
    lines = [(f"準備時膝蓋 {'3D' if x.get('knee3d') is not None else '2D'} {k:.0f}°", kc(k))] if k is not None else []
    if x.get("prep") is not None: lines.append((f"準備時間 {x['prep']:.2f}s", INK))
    if x.get("contact_h") is not None:
        lines.extend([("擊球時手腕高度（2D）", INK), (f"{x['contact_h'] * 100:.0f}（髖＝0、肩＝100）", INK), ("接觸格附近五格中位數", INK)])
    if x.get("knee_warn"): lines.append(("擊球格不可信，這拍不量" if x.get("knee_warn_why") == "contact" else "這拍角度不準", BAD))
    return head, lines


def starts(S):
    """S sorted by contact frame "c": add each stroke's tag start "a", never earlier than 4 frames after the same track's previous contact, never after its own."""
    last = {}
    for x in S:
        k = x.get("track", 0); x["a"] = min(x["c"], max(x["c"] - PRE, last[k] + 4)) if k in last else x["c"] - PRE; last[k] = x["c"]
    return S


def active(S, n):
    return next((x for x in reversed(S) if x["a"] <= n <= x["c"] + POST), None)  # latest stroke whose window covers this frame


def pose_bbox(p, W, H):
    """Pixel bounding box (x0, y0, x1, y1) of visible JOINTS in one frame, or None."""
    if p is None: return None
    pts = [(float(p[j, 0]) * W, float(p[j, 1]) * H) for j in JOINTS if p[j, 2] >= MINVIS]
    if not pts: return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def _rect_score(r, b):
    """(distance, -overlap_area) between panel rect r and player bbox b; higher is farther."""
    dx = max(0.0, r[0] - b[2], b[0] - r[2]); dy = max(0.0, r[1] - b[3], b[1] - r[3])
    if dx or dy: return math.hypot(dx, dy), 0.0
    ov = max(0.0, min(r[2], b[2]) - max(r[0], b[0])) * max(0.0, min(r[3], b[3]) - max(r[1], b[1]))
    return 0.0, -ov


def panel_pos(bboxes, W, H, pw, ph, pos="auto"):
    """Top-left (x0, y0) for the stats panel: fixed corner or farthest from all player bboxes."""
    xr, yb = max(0, W - pw - PANEL_MX), max(0, H - ph - PANEL_MY)
    corners = {"tl": (min(PANEL_MX, xr), min(PANEL_MY, yb)), "tr": (xr, min(PANEL_MY, yb)),
               "bl": (min(PANEL_MX, xr), yb), "br": (xr, yb)}
    if pos != "auto":
        if pos not in corners: raise ValueError(f"invalid panel position {pos!r}; expected 'auto' or {CORNERS}")
        return corners[pos]
    if not bboxes: return corners["tl"]
    best = max(CORNERS, key=lambda c: (*min(_rect_score((*corners[c], corners[c][0] + pw, corners[c][1] + ph), b) for b in bboxes), -CORNERS.index(c)))
    return corners[best]


def annotate(s, name, src, panel="auto"):
    Wd = work(s) / name
    if not (Wd / "pose.npy").exists(): sys.exit(f"missing work/{s}/{name}/pose.npy; run python tools/run.py prep.py {s}")
    ks = tracks(Wd)  # every tracked person is drawn; a stroke's tag sits on the body of the track that swung (strokes.json "track")
    poses = {k: np.load(track_file(Wd, "pose", k)) for k in ks}; pose = poses[0]
    worlds = {k: np.load(w) if (w := track_file(Wd, "pose_world", k)).exists() else None for k in ks}
    vn = videos(s).index(name) + 1
    sp = web(s) / "strokes.json"; allS = load(sp) if sp.exists() else []
    S = starts(sorted(({**x, "no": i + 1, "c": round(x["t"] * FPS)} for i, x in enumerate(allS) if x["video"] == vn), key=lambda x: x["c"]))
    w, h = probe(src); sc = LONG / max(w, h); W, H = int(round(w * sc / 2)) * 2, int(round(h * sc / 2)) * 2
    if (Wd / "proxy_filter.txt").exists(): poses = {k: map_pose(p, w, h, inverse=True) for k, p in poses.items()}
    out = web(s) / f"annotated_{name}.mp4"; out.parent.mkdir(parents=True, exist_ok=True)
    vcodec = h264_args("6000k", 22)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-an", "-vf", f"scale={W}:{H},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a:0?",
                            *vcodec, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    t0 = time.time(); n = 0
    while True:
        b = dec.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        img = np.frombuffer(b, np.uint8).reshape(H, W, 3).copy()
        st = active(S, n)
        bboxes = []
        for k in ks:
            pk = poses[k]; p = pk[n] if n < len(pk) and not np.isnan(pk[n][0, 0]) else None
            if p is None: continue
            if (bb := pose_bbox(p, W, H)) is not None: bboxes.append(bb)
            P = lambda j: (int(p[j, 0] * W), int(p[j, 1] * H)); ok = lambda j: p[j, 2] >= MINVIS
            for a, c in EDGES:
                if ok(a) and ok(c): cv2.line(img, P(a), P(c), (255, 140, 70) if a % 2 == 0 and c % 2 == 0 else (90, 180, 255), 3, cv2.LINE_AA)  # BGR: right side (even landmark ids) orange, left blue, like highlights.py
            for j in JOINTS:
                if ok(j): cv2.circle(img, P(j), 4, (255, 255, 255), -1, cv2.LINE_AA)
            wk = worlds[k]; wn = wk[n] if wk is not None and n < len(wk) and not np.isnan(wk[n][0, 0]) else None; a, j = live_knee(p, wn, (W, H))
            if a is not None and ok(j): x, y = P(j); draw_text(img, x + 14, y - 18, f"{a:.0f}°{'3D' if wn is not None else '2D'}", 26, kc(a))
            if st is not None and st.get("track", 0) == k:
                nx, ny = P(0); who = (f" {st['player']}" if st.get("player") else "")
                draw_text(img, nx, max(ny - 44, 30), f"#{st['no']:02d}{who}", 30, INK, "ma")
        if st is not None:
            head, lines = stroke_info(st); pw, ph = PANEL_W, 52 + 30 * len(lines)
            x0, y0 = panel_pos(bboxes, W, H, pw, ph, panel); x, y = x0 + 10, y0 + 8
            roi = img[y0:y0 + ph, x0:x0 + pw]; cv2.addWeighted(np.full_like(roi, (24, 20, 18)), 0.6, roi, 0.4, 0, roi)  # dim only the panel, not a full-frame copy
            draw_text(img, x, y, head, 30, INK)
            for i, (t, col) in enumerate(lines): draw_text(img, x, y + 40 + i * 30, t, 24, col)
            if abs(n - st["c"]) <= 3: draw_text(img, W // 2, H - 24, "擊球", 44, GOLD, "ms")
        try: enc.stdin.write(img.tobytes())
        except BrokenPipeError: dec.kill(); break  # encoder died (bad codec, disk full); its exit code is reported below
        n += 1
    dec.stdout.close()
    try: enc.stdin.close()
    except BrokenPipeError: pass
    enc.wait(); dec.wait()
    if enc.returncode or dec.returncode:
        out.unlink(missing_ok=True); sys.exit(f"ffmpeg failed on {name} (decode {dec.returncode}, encode {enc.returncode})")
    dt = time.time() - t0
    print(f"{name}: {n} frames ({n / FPS:.1f}s video, pose {len(pose)} frames), {len(S)} strokes, {W}x{H}, {dt:.0f}s ({n / FPS / dt:.2f}x realtime), {out.stat().st_size / 1e6:.1f} MB -> {out}")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Render annotated practice video with skeleton and live-stats panel.")
    ap.add_argument("session", help="session folder under videos/")
    ap.add_argument("video", nargs="?", help="optional single video stem/filename")
    ap.add_argument("--panel", choices=("auto", *CORNERS), default="auto", help="stats panel corner (default: auto, avoids players)")
    return ap.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    s = session([sys.argv[0], args.session]); names = videos(s)
    if args.video is not None:
        want = Path(args.video).stem
        if want not in names: sys.exit(f"{want} not in work/{s}/videos.json: {names}")
        names = [want]
    for name in names:
        src = next(iter(sorted(p for p in (ROOT / "videos" / s).iterdir() if p.stem == name and p.suffix.lower() in (".mov", ".mp4", ".m4v"))), None)
        if src is None: sys.exit(f"no video named {name} in videos/{s}/")
        annotate(s, name, src, panel=args.panel)
