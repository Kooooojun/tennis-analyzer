# Run: .venv/bin/python tests/test_body.py   (plain asserts, written before kinematics(); failure list in testset/results/body-kinematics_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from metrics import kinematics

J = dict(nose=0, ls=1, rs=2, le=3, re=4, lw=5, rw=6, lh=7, rh=8, lk=9, rk=10, la=11, ra=12)
N, c = 150, 90
f = np.arange(N)


def body(hip_y=0.5, ankle_y=(1.0, 1.0), sh_w=0.32, sh_c=None):
    """Standing body, y down. Torso length (shoulder mid -> hip mid) = 0.4, shoulder width sh_w (full = 0.8 torso)."""
    xy = np.zeros((N, 13, 2))
    hy = np.broadcast_to(np.asarray(hip_y, float), (N,))
    for i, x in ((7, -0.1), (8, 0.1)): xy[:, i] = np.c_[np.full(N, x), hy]
    w = np.broadcast_to(np.asarray(sh_w, float), (N,))
    xy[:, 1] = np.c_[-w / 2, hy - 0.4]; xy[:, 2] = np.c_[w / 2, hy - 0.4]
    xy[:, 0] = np.c_[np.zeros(N), hy - 0.55]
    for i, side in ((9, -0.1), (10, 0.1)): xy[:, i] = np.c_[np.full(N, side), (hy + 1.0) / 2]
    for i, (side, ay) in zip((11, 12), ((-0.1, ankle_y[0]), (0.1, ankle_y[1]))): xy[:, i] = np.c_[np.full(N, side), np.full(N, ay)]
    xy[:, 3] = xy[:, 1] + [0, 0.25]; xy[:, 5] = xy[:, 1] + [0, 0.5]
    xy[:, 4] = xy[:, 2] + [0, 0.25]; xy[:, 6] = xy[:, 2] + [0, 0.5]
    return xy


near = lambda a, b, tol: a is not None and abs(a - b) <= tol

# --- legs ---------------------------------------------------------------
# hip drops 0.05 below standing (leg height 0.5 -> 0.45 = load 0.10) at c-20, comes back up to 0.48 at contact (drive 0.06)
hy = np.full(N, 0.5); hy[c - 40:c - 20] = np.linspace(0.5, 0.55, 20); hy[c - 20:c + 3] = np.linspace(0.55, 0.52, 23); hy[c + 3:] = 0.52
r = kinematics(body(hy), J, c)
assert near(r["leg_load"], 0.10, 0.01) and near(r["leg_drive"], 0.06, 0.01), r
# 3: one ankle lifted (foot off the ground) -> the lower ankle is the ground, same answer
r2 = kinematics(body(hy, ankle_y=(0.8, 1.0)), J, c); assert near(r2["leg_load"], 0.10, 0.01), r2
# standing still -> no load, no drive
r = kinematics(body(), J, c); assert near(r["leg_load"], 0, 0.005) and near(r["leg_drive"], 0, 0.005), r
# 3: ankles lost -> None, no crash
b = body(hy); b[:, 11:13] = np.nan; r = kinematics(b, J, c); assert r["leg_load"] is None and r["leg_drive"] is None, r

# --- speeds -------------------------------------------------------------
# arm-only swing: wrist circles the right shoulder, shoulders and hips still -> trunk_share ~ 0
def swing(b, shoulder_move=0.0, hand="R"):
    s, w = (2, 6) if hand == "R" else (1, 5)
    ang = np.clip((f - (c - 24)) / 24, 0, 1.2) * np.pi  # wrist sweeps half a circle in 0.4 s
    sx = b[:, s, 0] + shoulder_move * np.sin(ang / 2)  # shoulder moves forward with the swing
    b[:, s, 0] = sx; b[:, w] = np.c_[sx - 0.5 * np.cos(ang), b[:, s, 1] + 0.5 * np.sin(ang)]
    return b
r = kinematics(swing(body()), J, c)
assert r["wrist_speed"] > 4 and r["trunk_share"] < 0.05, r  # 0.5*pi / 0.4 s / 0.4 torso ~ 9.8 torso/s
# body-driven: shoulder moves 0.3 while the wrist sweeps -> clearly higher share
r2 = kinematics(swing(body(), 0.3), J, c); assert r2["trunk_share"] > 0.15, r2
# 8: one-frame wrist glitch does not set the peak
b = swing(body()); b[c - 10, 6] += [2.0, 0]; r3 = kinematics(b, J, c); assert near(r3["wrist_speed"], r["wrist_speed"], 1.0), (r3, r)
# 8: a 4-frame wrist glitch during the backswing (wall-1 #33) does not set the peak: the peak is searched in the forward swing only
b = swing(body()); b[c - 24:c - 20, 6] += [[1.5, -0.5], [0.2, 0.6], [1.2, -0.3], [-0.4, 0.5]]; r3 = kinematics(b, J, c); assert near(r3["wrist_speed"], r["wrist_speed"], 1.0), (r3, r)
# walking: everything translates together -> hip-relative speeds unchanged
b = swing(body(), 0.3); b[:, :, 0] += 0.01 * f[:, None]; r4 = kinematics(b, J, c); assert near(r4["trunk_share"], r2["trunk_share"], 0.03), (r4, r2)
# hand="L" uses the left wrist / shoulder
r5 = kinematics(swing(body(), 0.3, hand="L"), J, c, hand="L"); assert near(r5["trunk_share"], r2["trunk_share"], 0.03), (r5, r2)
r6 = kinematics(swing(body(), 0.3, hand="L"), J, c); assert r6["wrist_speed"] < 1, r6  # right wrist did not move
# no wrist motion -> share undefined
assert kinematics(body(), J, c)["trunk_share"] is None

# --- shoulder turn --------------------------------------------------------
FULLW = 0.32  # = 0.8 torso
def turn_body(phi_deg, yaw=0.0, noise=0.0, seed=0):
    """Shoulder line rotates by phi (deg, 0 = square to camera) seen from a horizontal camera rotated by yaw: width = full*|cos|."""
    w = FULLW * np.abs(np.cos(np.radians(phi_deg + yaw)))
    w = w + np.random.default_rng(seed).normal(0, noise, N)
    return body(sh_w=np.clip(w, 0, None))
# side-on (-90) at backswing end c-30, rotate through square to +45 at c+18: 135 deg of travel
# (5: past square by < ~32 deg the width drops < 15%, so that last bit is not counted: a known limit of the reversal rule)
phi = np.interp(f, [0, c - 30, c + 18, N - 1], [-90, -90, 45, 45])
r = kinematics(turn_body(phi), J, c, start=c - 30); assert near(r["turn"], 135, 8), r
assert near(kinematics(turn_body(np.interp(f, [c - 30, c + 18], [-90, 30])), J, c, start=c - 30)["turn"], 90, 8)
# same motion, camera 40 deg off -> same travel (the fold at square/side-on is counted)
r2 = kinematics(turn_body(phi, yaw=40), J, c, start=c - 30); assert near(r2["turn"], 135, 10), r2
# 5: still body with width jitter (+-3% torso) -> near 0, not accumulated noise
r3 = kinematics(turn_body(np.full(N, -40.0), noise=0.012), J, c, start=c - 30); assert r3["turn"] < 15, r3
# arm-only: shoulders barely move (10 deg, width change 14% < 15%) -> 0
r4 = kinematics(turn_body(np.interp(f, [c - 30, c + 18, c + 40, c + 50], [-60, -50, -50, 0])), J, c, start=c - 30); assert r4["turn"] == 0, r4  # square at the end, so the full width is seen
# full width floor: never side-on enough to see the full width (always 0.3 of full) -> floor 0.55 torso keeps angles sane
r5 = kinematics(body(sh_w=0.3 * FULLW), J, c, start=c - 30); assert r5["turn"] < 5, r5
# no start given -> uses c-30
assert near(kinematics(turn_body(phi), J, c)["turn"], 135, 8)

# --- 2D knee foreshortening gate ---------------------------------------------
assert kinematics(body(hy), J, c)["knee2d_ok"] is True
b = body(hy); b[c - 48:c - 5, 9:11, 1] = b[c - 48:c - 5, 7:9, 1] + 0.12  # thigh shortened to ~48% during the window (leg points at camera)
assert kinematics(b, J, c)["knee2d_ok"] is False
print("ok")
