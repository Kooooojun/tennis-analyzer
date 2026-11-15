# Run: .venv/bin/python tools/test_arm_checks.py   (written before arm_checks; synthetic arms, orthographic camera)
import numpy as np
from metrics import arm_checks

SIZE = (960, 540); K = 1.2  # metres -> 540-px units
# CLIP indices: 0 nose, 1 ls, 2 rs, 3 le, 4 re, 5 lw, 6 rw ; world y is down, z is toward/away from camera
def pose(rs, re, rw, ls=(-0.2, 0, 0), nose=None, vis=0.9, noise3d=None):
    pts = {0: nose or (0, -0.25, 0.1), 1: ls, 2: rs, 3: (-0.3, 0.25, 0), 4: re, 5: (-0.3, 0.5, 0), 6: rw}
    W = np.zeros((17, 3)); P = np.zeros((17, 3))
    for i in range(17): W[i] = pts.get(i, (0, 0.6 + 0.01 * i, 0))
    P[:, 0] = 0.5 + W[:, 0] * K / (SIZE[0] / 540); P[:, 1] = 0.5 + W[:, 1] * K; P[:, 2] = vis
    return P.tolist(), W.tolist()

def run(rs, re, rw, n=150, c=90, **kw):
    P, W = pose(rs, re, rw, **kw)
    return arm_checks([P] * n, c, SIZE, [W] * n, "SV"), P, W

# 1. arm straight, in the image plane -> straight
r, *_ = run((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0)); assert r["serve_arm_straight"] is True, r
# 2. arm bent 90 deg, in plane -> bent (False)
r, *_ = run((0.2, 0, 0), (0.2, -0.3, 0), (0.5, -0.3, 0)); assert r["serve_arm_straight"] is False, r
# 3. arm pointing at the camera (large depth) -> cannot tell
r, *_ = run((0.2, 0, 0), (0.2, -0.05, -0.3), (0.2, -0.1, -0.6)); assert r["serve_arm_straight"] is None, r
# 4. low visibility -> cannot tell
r, *_ = run((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0), vis=0.2); assert r["serve_arm_straight"] is None, r
# 5. 2D says straight, 3D says very bent (gap > 25) -> cannot tell
P, W = pose((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0)); W[6] = [0.5, -0.3, 0.0]
r = arm_checks([P] * 150, 90, SIZE, [W] * 150, "SV"); assert r["serve_arm_straight"] is None, r
# 6. no world data -> cannot tell (3D is half of the rule)
P, W = pose((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0)); r = arm_checks([P] * 150, 90, SIZE, None, "SV"); assert r["serve_arm_straight"] is None, r
# 7. missing frames (None) around contact -> cannot tell, no crash
r = arm_checks([None] * 150, 90, SIZE, [None] * 150, "SV"); assert r["serve_arm_straight"] is None, r
# 8. kinds: FH never gets either check; SV gets no BH field values and vice versa
P, W = pose((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0))
r = arm_checks([P] * 150, 90, SIZE, [W] * 150, "FH"); assert r["serve_arm_straight"] is None and r["bh_elbow_ok"] is None, r
r = arm_checks([P] * 150, 90, SIZE, [W] * 150, "BH", one_hand=True); assert r["bh_elbow_ok"] is True and r["serve_arm_straight"] is None, r
r = arm_checks([P] * 150, 90, SIZE, [W] * 150, "BH", one_hand=False); assert r["bh_elbow_ok"] is None, r  # two-handed: not checked
# 9. left-handed uses the left arm: right arm straight but left arm (idx 3,5 = bent) is the racket arm
Pl, Wl = pose((0.2, 0, 0), (0.2, -0.3, 0), (0.2, -0.6, 0)); Wl[5] = [-0.1, 0.25, 0]; Pl[5][:2] = [0.5 + -0.1 * K / (SIZE[0] / 540), 0.5 + 0.25 * K]
r = arm_checks([Pl] * 150, 90, SIZE, [Wl] * 150, "SV", hand="L"); assert r["serve_arm_straight"] is False, r
# 10. BH contact in front: wrist ahead of the leading (right) shoulder along the shoulder line
Pf, Wf = pose((0.2, 0, 0), (0.4, 0, 0), (0.7, 0, 0), nose=(0.2, -0.25, 0.1)); r = arm_checks([Pf] * 150, 90, SIZE, [Wf] * 150, "BH", one_hand=True); assert r["bh_front_ok"] is True, r
Pb, Wb = pose((0.2, 0, 0), (0.1, 0, 0), (-0.1, 0, 0)); r = arm_checks([Pb] * 150, 90, SIZE, [Wb] * 150, "BH", one_hand=True); assert r["bh_front_ok"] is False, r
# arm-bent-detect (a) mean 2D/3D elbow 100 deg, all gates pass -> False ; (b) gate fails -> None ; (c) 150 deg -> True
import math
def bend(deg, **kw):  # forearm turned (180-deg) from the upper arm, in the image plane
    t = math.radians(180 - deg); return run((0.2, 0, 0), (0.2, -0.3, 0), (0.2 + 0.3 * math.sin(t), -0.3 - 0.3 * math.cos(t), 0), **kw)[0]["serve_arm_straight"]
assert bend(100) is False and bend(150) is True and bend(100, vis=0.3) is None
print("ok")
