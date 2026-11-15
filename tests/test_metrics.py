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

# --- knee view gate (testset/results/knee-view-gate_pred.md) ---
from metrics import cam_az, measure_clip, arm_checks, KNEE_VIEW_MIN
from common import KEEP
CJ = dict(ls=1, rs=2, lh=7, rh=8)  # CLIP layout


def body(right, n=150):
    """CLIP world frames (metres, camera-aligned: x right, y down, z away from camera); `right` = body right direction (x, z).
    Legs bent 40 deg in the x-y plane, so 2D (orthographic x, y) and 3D knee angles agree."""
    rx, rz = np.array(right, float) / np.linalg.norm(right); W = np.zeros((17, 3))
    for i, (side, y) in {1: (-1, -0.5), 2: (1, -0.5), 7: (-1, 0), 8: (1, 0)}.items(): W[i] = (side * 0.15 * rx, y, side * 0.15 * rz)
    for hip, k, a in ((7, 9, 11), (8, 10, 12)):
        W[k] = W[hip] + (0.15, 0.4, 0); W[a] = W[k] + (-0.15 * 1.2, 0.4, 0)
    W[0] = (0, -0.7, 0); W[3:7] = W[1:3].repeat(2, 0) + (0, 0.2, 0)
    P = np.c_[W[:, :2] + 0.5, np.full(17, 0.9)]
    return [P.tolist()] * n, [W.tolist()] * n


near = lambda a, b, tol=1.0: a is not None and abs(a - b) <= tol
# 0 = camera in front of the chest, 90 = side, 180 = behind (ct_eval.az); facing the camera, the body's right is image left (-x)
for right, want in (((-1, 0), 0), ((1, 0), 180), ((0, -1), 90), ((0, 1), 90), ((-1, -1), 45), ((1, -1), 135)):
    fr, wd = body(right); assert near(cam_az(np.array(wd, float), CJ, range(0, 10)), want), (right, cam_az(np.array(wd, float), CJ, range(0, 10)))
# 2: all-NaN window -> None; 3: no horizontal body line (hips stacked vertically) -> None
assert cam_az(np.full((20, 17, 3), np.nan), CJ, range(0, 10)) is None
Wv = np.zeros((20, 17, 3)); Wv[:, 2, 1] = Wv[:, 8, 1] = 1; assert cam_az(Wv, CJ, range(0, 10)) is None
# view gate through measure_clip: front / back -> warn "view"; side -> no warn; 45 deg -> no warn
for right, warn in (((-1, 0), True), ((1, 0.1), True), ((0, 1), False), ((-1, -1), False)):
    fr, wd = body(right); m = measure_clip(fr, 90, (540, 540), wd)
    assert m["knee3d"] is not None and m["knee"] is not None, m
    assert m["knee_warn"] is warn and m["knee_warn_why"] == ("view" if warn else None), (right, m["knee_warn"], m["knee_warn_why"], m["cam_az"])
# 5: view wins over gap; 6: no world -> no cam_az, gate falls back to gap only
fr, wd = body((-1, 0)); m = measure_clip(fr, 90, (540, 540), None); assert m["cam_az"] is None and m["knee_warn"] is None and m["knee_warn_why"] is None
# 8: a left-hander's shoulder remap does not flip the view
fr, wd = body((1, 0)); assert near(measure_clip(fr, 90, (540, 540), wd, "L")["cam_az"], 180)
# 4: window before the clip start -> None
fr, wd = body((0, 1)); assert measure_clip(fr, 30, (540, 540), wd)["cam_az"] is None
assert KNEE_VIEW_MIN == 30
# --- arm_checks: cannot measure -> conf 0.0 (counts as "cannot tell"); not applicable -> None ---
fr, wd = body((0, 1))
assert arm_checks(fr, 90, (540, 540), None, "SV")["serve_arm_conf"] == 0.0
assert arm_checks([None] * 150, 90, (540, 540), [None] * 150, "BH", one_hand=True)["bh_elbow_conf"] == 0.0
assert arm_checks(fr, 90, (540, 540), None, "FH")["serve_arm_conf"] is None and arm_checks(fr, 90, (540, 540), None, "BH")["bh_elbow_conf"] is None
# --- annotate: a stroke's tag window does not reach back into the previous stroke ---
from annotate import active, starts
S = starts([dict(c=100), dict(c=120)])
assert active(S, 95) is S[0] and active(S, 103) is S[0] and active(S, 104) is S[1] and active(S, 60) is None and active(S, 70) is S[0]
print("metrics tests ok")
