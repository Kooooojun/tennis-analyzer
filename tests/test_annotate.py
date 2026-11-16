# Run: .venv/bin/python tests/test_annotate.py
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from annotate import JOINTS, MINVIS, panel_pos, parse_args, pose_bbox

W, H = 1280, 720
PW, PH = 320, 142


def make_pose(xs, ys, vis=1.0):
    p = np.zeros((33, 3), dtype=np.float32)
    p[:, 2] = 0.0
    for j, x, y in zip(JOINTS, xs, ys):
        p[j] = [x, y, vis]
    return p


# 1. pose_bbox: None or all invisible -> None; otherwise pixel bbox of visible JOINTS
assert pose_bbox(None, W, H) is None
assert pose_bbox(make_pose([0.5] * len(JOINTS), [0.5] * len(JOINTS), vis=MINVIS - 0.05), W, H) is None

p = np.zeros((33, 3), dtype=np.float32)
p[11] = [0.2, 0.3, 0.9]
p[12] = [0.4, 0.7, 0.9]
p[15] = [0.9, 0.9, 0.1]  # below MINVIS: ignored
assert np.allclose(pose_bbox(p, W, H), (0.2 * W, 0.3 * H, 0.4 * W, 0.7 * H))

# 2. panel_pos: no players -> default top-left (10, 8)
assert panel_pos([], W, H, PW, PH) == (10, 8)

# 3. panel_pos: single player near each corner -> picks farthest corner
assert panel_pos([(20, 20, 300, 350)], W, H, PW, PH) == (W - PW - 10, H - PH - 8)        # player TL -> BR
assert panel_pos([(950, 20, 1250, 350)], W, H, PW, PH) == (10, H - PH - 8)               # player TR -> BL
assert panel_pos([(20, 360, 300, 700)], W, H, PW, PH) == (W - PW - 10, 8)                # player BL -> TR
assert panel_pos([(950, 360, 1250, 700)], W, H, PW, PH) == (10, 8)                       # player BR -> TL

# 4. panel_pos: two players on TL and BR -> avoids both, picks TR or BL (not TL/BR)
pos_2p = panel_pos([(20, 20, 300, 350), (960, 380, 1250, 700)], W, H, PW, PH)
assert pos_2p in ((W - PW - 10, 8), (10, H - PH - 8)), pos_2p

# 5. panel_pos: huge player covering all 4 corners, least overlap in TR
# Leave extra room on TR by placing bbox slightly left and down
huge = (10, 100, 1100, 710)
assert panel_pos([huge], W, H, PW, PH) == (W - PW - 10, 8)

# 6. panel_pos: fixed position overrides bboxes
tl_box = [(20, 20, 300, 350)]
assert panel_pos(tl_box, W, H, PW, PH, pos="tl") == (10, 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="tr") == (W - PW - 10, 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="bl") == (10, H - PH - 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="br") == (W - PW - 10, H - PH - 8)

try:
    panel_pos([], W, H, PW, PH, pos="center")
    raise AssertionError("expected ValueError for invalid pos")
except ValueError:
    pass

# 7. parse_args: session, optional video, --panel
a1 = parse_args(["2026-11-20"])
assert a1.session == "2026-11-20" and a1.video is None and a1.panel == "auto"

a2 = parse_args(["2026-11-20", "clip1", "--panel", "br"])
assert a2.session == "2026-11-20" and a2.video == "clip1" and a2.panel == "br"

print("ok")
