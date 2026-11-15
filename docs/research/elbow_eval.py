# elbow_eval.py — labels were set by eye from contact sheets BEFORE running this (sheet frames, every 4th). Runs tools/metrics.arm_checks at each label.
import sys, numpy as np
from pathlib import Path
R = Path.cwd(); sys.path.insert(0, str(R / "tools"))
from metrics import arm_checks, _angle, _scale
from common import KEEP
# (video, frame, kind, truth) truth: S = arm straight, B = clearly bent
L = [("JnlQnmFAq4s", f, "SV", "S") for f in (7046, 9170, 9611, 9984, 10183, 10418, 10628, 11143, 11455)] + [("INBENXMNZBc", 218, "SV", "S")] \
  + [("N6u9u4I8TVQ", f, "BH", "S") for f in (570, 2250, 3548, 4599)] \
  + [("CcKAq8mW3qY", f, "SV", "B") for f in (111, 488, 1650, 2082)]  # arm shape is the same geometry test whatever the stroke; kind only selects the output field
rows = []
for v, f, k, t in L:
    D = R / "work/elbow-eval" / v; P = np.load(D / "pose.npy"); W = np.load(D / "pose_world.npy")
    for off in range(-3, 4):  # my frame label is +-2 frames; sweep -3..+3
        c = f + off; a = c - 90
        fr = [None if np.isnan(x[0, 0]) else x[KEEP].tolist() for x in P[a:a + 150]]; wd = [None if np.isnan(x[0, 0]) else x[KEEP].tolist() for x in W[a:a + 150]]
        r = arm_checks(fr, 90, (960, 540), wd, "SV" if k == "SV" else "BH", one_hand=True)
        out = r["serve_arm_straight"] if k == "SV" else r["bh_elbow_ok"]
        xy = np.array([x for x in fr[88:93] if x], float)[:, :, :2] * _scale((960, 540))
        e2 = float(np.nanmedian([_angle(xy, i, 2, 4, 6) for i in range(len(xy))])) if len(xy) else float("nan")
        rows.append((v, f, off, k, t, out, r["serve_arm_conf"] if k == "SV" else r["bh_elbow_conf"], e2))
        if off == 0: print(v, f, k, "truth", t, "->", out, "conf", rows[-1][6], "elbow2d", round(e2), "front", r["bh_front_ok"])
def tally(sel, name):
    n = len(sel); unk = sum(r[5] is None for r in sel); dec = [r for r in sel if r[5] is not None]
    ok = sum((r[5] is True) == (r[4] == "S") for r in dec)
    b2 = sum((r[7] >= 130) == (r[4] == "S") for r in sel if np.isfinite(r[7]))
    print(f"{name}: n={n} unclear={unk} ({100*unk/n:.0f}%) decided={len(dec)} correct={ok} ({100*ok/max(1,len(dec)):.0f}%) | ungated 2D>=130: {b2}/{len(sel)} ({100*b2/len(sel):.0f}%)")
for off in range(-3, 4): tally([r for r in rows if r[2] == off], f"offset {off:+d}")
tally([r for r in rows if r[2] == 0 and r[3] == "SV" and r[4] == "S"], "serve straight only")
tally([r for r in rows if r[2] == 0 and r[3] == "BH"], "one-hand BH only")
tally([r for r in rows if r[2] == 0 and r[4] == "B"], "bent only")
