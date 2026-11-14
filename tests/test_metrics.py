# Run: .venv/bin/python tests/test_metrics.py   (plain asserts; failure list in testset/results/prep-contact_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from metrics import _swing_dir, _prep, PREP_WIN

J = dict(rw=0, lh=1, rh=2)


def clip(wx, hip=0.0):
    """Synthetic frames: wrist x track `wx`, both hips at `hip` (scalar or array)."""
    xy = np.zeros((len(wx), 3, 2)); xy[:, 0, 0] = wx; xy[:, 1, 0] = hip; xy[:, 2, 0] = hip; return xy


c = 90; f = np.arange(150)
# wrist goes back to its furthest point 20 frames before contact, then swings forward through contact
wx = np.where(f < c - 20, -(f - (c - 60)) / 40, -1 + (f - (c - 20)) / 10)
wx[f < c - 60] = 0
xy = clip(wx)
near = lambda v: v is not None and abs(v - 20 / 60) <= 2.5 / 60  # the 5-frame median flattens a sharp tip, ties go to the earliest frame (<= 2 frames)
assert _swing_dir(xy, J, c) == 1
assert near(_prep(xy, J, c, 1))
# 3: mirrored camera (swing toward -x) gives the same answer
m = clip(-wx); assert _swing_dir(m, J, c) == -1 and near(_prep(m, J, c, -1))
# 16: walking (hips and wrist drift together) does not move the backswing end
drift = 0.01 * f; assert near(_prep(clip(wx + drift, drift), J, c, 1))
# 4: one-frame pose glitch further back than the real backswing end is ignored by the 5-frame median
g = wx.copy(); g[c - 45] = -5; assert near(_prep(clip(g), J, c, 1))
# 1: window is PREP_WIN frames; a backswing end before it is not reported as earlier than the window
assert _prep(xy, J, c, 1) <= PREP_WIN / 60
# no wrist data -> None, not a crash
assert _prep(clip(np.full(150, np.nan)), J, c, 1) is None and np.isnan(_swing_dir(clip(np.full(150, np.nan)), J, c))
print("metrics tests ok")
