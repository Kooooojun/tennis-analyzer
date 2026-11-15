# Run: .venv/bin/python tests/test_pose_flags.py   (plain asserts; failure list in testset/results/pose-flags_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import metrics
from metrics import pose_flags, measure_full, FULL
from kind import classify
from common import PORTRAIT

c = 120; n = 240; f = np.arange(n)


def body():
    """Standing player, torso length 1 (shoulders y=0, hips y=1), small breathing sway; arms out to each side."""
    xy = np.zeros((n, 33, 2)); sway = 0.01 * np.sin(f / 7)[:, None]
    pts = {0: (0, -0.4), 11: (-0.3, 0), 12: (0.3, 0), 13: (-0.6, 0.3), 14: (0.6, 0.3), 15: (-0.9, 0.5), 16: (0.9, 0.5),
           23: (-0.2, 1), 24: (0.2, 1), 25: (-0.2, 1.5), 26: (0.2, 1.5), 27: (-0.2, 2), 28: (0.2, 2)}
    for j, (x, y) in pts.items(): xy[:, j] = (x, y); xy[:, j, 0] += sway[:, 0]
    return xy


# normal pose: no flag, no swap
r = pose_flags(body(), FULL, c)
assert r["pose_jump"] is False and r["lr_swap"] is False, r

# 1-frame teleport of a hip: flagged, joint named, max reported
g = body(); g[c + 3, 23] += (0, 1.5); r = pose_flags(g, FULL, c)
assert r["pose_jump"] is True and "lh" in r["pose_jump_joints"] and r["pose_jump_max"] >= 1.0, r
# same glitch outside the +-12 window: not this stroke's problem
g = body(); g[c + 30, 23] += (0, 1.5); assert pose_flags(g, FULL, c)["pose_jump"] is False

# real fast swing: racket wrist sweeps 3 torso lengths in 10 frames (smooth arc through contact) -> no flag
g = body(); s = slice(c - 6, c + 5); th = np.linspace(-1.2, 1.2, 11)
g[s, 16] = np.c_[0.3 + 1.2 * np.sin(th), 0.4 + 0.3 * np.cos(th)]; g[s, 14] = np.c_[0.3 + 0.6 * np.sin(th), 0.3 + 0.1 * np.cos(th)]
g[c + 5:, 16] = g[c + 4, 16]; g[c + 5:, 14] = g[c + 4, 14]; g[:c - 6, 16] = g[c - 6, 16]; g[:c - 6, 14] = g[c - 6, 14]
r = pose_flags(g, FULL, c); assert r["pose_jump"] is False and r["lr_swap"] is False, r

# hidden arm (NaN for the whole window): ignored, not a jump, flag still works on the rest
g = body(); g[:, [13, 15]] = np.nan; assert pose_flags(g, FULL, c)["pose_jump"] is False
g[c, 25] += (1.5, 0); assert pose_flags(g, FULL, c)["pose_jump"] is True
# a single NaN frame next to good frames is not a jump either
g = body(); g[c, 16] = np.nan; assert pose_flags(g, FULL, c)["pose_jump"] is False
# nothing visible at all -> None (unknown), not False
r = pose_flags(np.full((n, 33, 2), np.nan), FULL, c); assert r["pose_jump"] is None and r["lr_swap"] is None, r

# left/right labels swap for a stretch around contact: lr_swap True
g = body(); g[c - 3:c + 8, [13, 14, 15, 16]] = g[c - 3:c + 8, [14, 13, 16, 15]]
assert pose_flags(g, FULL, c)["lr_swap"] is True
# two-handed backhand: hands close together and crossing -> not a swap
g = body(); g[:, 15] = (0.05, 0.6); g[:, 16] = (-0.05, 0.6); g[c:, 15] = (-0.05, 0.6); g[c:, 16] = (0.05, 0.6)
assert pose_flags(g, FULL, c)["lr_swap"] is False

# window cut by the clip edge: still works on the frames that exist
assert pose_flags(body(), FULL, 3)["pose_jump"] is False

# portrait and landscape: the same motion in pixels gives the same answer (displacement / torso length)
g = body(); g[c + 3, 23] += (0, 1.5)
assert pose_flags(g * (960 / 540), FULL, c)["pose_jump_max"] == pose_flags(g, FULL, c)["pose_jump_max"]

# measure_full on an old stroke without "size": works (kind.classify gets the portrait default)
P = np.zeros((n, 33, 3)); P[:, :, :2] = (body() + 3) / 10; P[:, :, 2] = 1
seen = []; metrics.classify = lambda *a: seen.append(a[4]) or classify(*a)  # record the size kind.classify gets
m = measure_full(P, c / 60, None)
assert seen == [PORTRAIT] and m["pose_jump"] is False and "auto_kind" in m, (seen, m)
print("ok")
