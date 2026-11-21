# strip.py --stages: one row per stroke, four tiles (準備 / 引拍 / 擊球 / 收拍), the whole skeleton drawn on the clip frame,
# left side orange and right side blue, to check by eye that the body is not mirrored and the tracker did not follow someone else.
# Synthetic only (cv2 writes the clips; no user footage). Cases follow testset/results/method-notes/pred.md, failure modes 6 and 7.
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
import cv2, numpy as np

R = Path(__file__).resolve().parent.parent
T = Path(tempfile.mkdtemp()) / "root"; shutil.copytree(R / "tools", T / "tools", ignore=shutil.ignore_patterns("__pycache__"))
s = "stages-1"; D = T / "web" / "sessions" / s; (D / "clips").mkdir(parents=True); (T / "videos" / s).mkdir(parents=True); (T / "work" / s).mkdir(parents=True)
W, H, N, C = 240, 320, 120, 60  # clip size, frames, contact frame; prep 0.5 s -> the stages are frames 12, 30, 60, 90


def clip(name, gray):
    w = cv2.VideoWriter(str(D / "clips" / name), cv2.VideoWriter_fourcc(*"mp4v"), 60, (W, H))
    for _ in range(N): w.write(np.full((H, W, 3), gray, np.uint8))
    w.release()


# 17 points (common.KEEP order); odd index = left side (landmark 11, 13, 15, 23, ...), even = right
P = {0: (.5, .2), 1: (.62, .35), 2: (.38, .35), 3: (.70, .50), 4: (.30, .50), 5: (.75, .65), 6: (.25, .65), 7: (.57, .60), 8: (.43, .60),
     9: (.58, .78), 10: (.42, .78), 11: (.58, .95), 12: (.42, .95), 13: (.56, .97), 14: (.44, .97), 15: (.62, .97), 16: (.38, .97)}
body = [[*P[i], 1.0] for i in range(17)]
frames = lambda hole=(): [None if f in hole else body for f in range(N)]
common = dict(kind="FH", contact=C, prep=0.5, size=[W, H])
clip("black.mp4", 0); clip("white.mp4", 255)
strokes = [dict(id=0, src="clips/black.mp4", frames=frames(), **common),
           dict(id=1, src="clips/white.mp4", frames=frames(hole=range(80, N)), **common),  # tracker lost the person after contact
           dict(id=2, src="clips/gone.mp4", frames=frames(), **common)]  # the clip file is missing
(D / "strokes.json").write_text(json.dumps(strokes), encoding="utf-8")


def run(*args):
    r = subprocess.run([sys.executable, str(T / "tools" / "strip.py"), s, "final", *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r


def tiles(img, rows):
    th, tw = img.shape[0] // rows, img.shape[1] // 4
    assert img.shape[0] == th * rows and img.shape[1] == tw * 4, img.shape
    return th, tw


def colour_near(tile, x, y, want):
    """True when a pixel within 2 px of (x, y) in tile (BGR) is orange ('L') or blue ('R')."""
    th, tw = tile.shape[:2]; px, py = int(x * tw), int(y * th)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            b, g, r = (int(v) for v in tile[py + dy, px + dx])
            if want == "L" and r > 200 and r > b + 120: return True
            if want == "R" and b > 200 and b > r + 120: return True
    return False


# the old call keeps working (positional frame range, strip.jpg), with or without the new flag next to it
run("1,2", "-8", "4", "2"); assert cv2.imread(str(T / "work" / s / "strip.jpg")).shape[0] == 2 * 200
run("1", "--stages", "-8", "4", "2"); assert cv2.imread(str(T / "work" / s / "strip.jpg")) is not None, "the flag must not shift the positional arguments"

r = run("1,2,3", "--stages")
out = T / "work" / s / "stages.jpg"; assert str(out.name) in r.stdout, r.stdout
img = cv2.imread(str(out)); th, tw = tiles(img, 3)
assert "沒有原片" in r.stderr or "沒有原片" in r.stdout, "a missing clip is reported, not silent"
mid = lambda a, b: ((P[a][0] + P[b][0]) / 2, (P[a][1] + P[b][1]) / 2)
for row in range(3):
    for col in range(4):
        tile = img[row * th:(row + 1) * th, col * tw:(col + 1) * tw]
        lost = row == 1 and col == 3  # stroke 2, 收拍: no skeleton in that frame
        for side, a, b in (("L", 1, 3), ("L", 3, 5), ("L", 7, 9), ("L", 9, 11), ("R", 2, 4), ("R", 4, 6), ("R", 8, 10), ("R", 10, 12)):
            x, y = mid(a, b)
            assert colour_near(tile, x, y, side) == (not lost), (row, col, side, a, b)  # left orange / right blue; none where there is no skeleton
        if lost:  # nothing orange or blue anywhere: the gap is visible as a gap, not as a skeleton drawn at the corner
            hsv = cv2.cvtColor(tile, cv2.COLOR_BGR2HSV); assert not ((hsv[..., 1] > 150) & (hsv[..., 2] > 150))[30:].any()
# a dark and a bright picture both carry the colours (checked above); the missing clip falls back to a plain mid-grey picture
means = [img[row * th:(row + 1) * th, :tw].mean() for row in range(3)]
assert means[0] < 70 and means[1] > 180 and 40 < means[2] < 140, means
print("ok")
shutil.rmtree(T.parent)
