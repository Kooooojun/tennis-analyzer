# Run: .venv/bin/python tools/test_form_checks.py   (written before form_checks; synthetic body, orthographic camera, world y down)
import numpy as np
from metrics import form_checks

SIZE = (960, 540); K = 1.2  # metres -> 540-px units
# CLIP indices: 0 nose, 1 ls, 2 rs, 3 le, 4 re, 5 lw, 6 rw, 7 lh, 8 rh, 9 lk, 10 rk, 11 la, 12 ra
def pose(rw=(0.3, 0.25, 0), lw=(-0.3, 0.25, 0), rs=(0.2, 0, 0), ls=(-0.2, 0, 0), hx=0.0, la=(-0.15, 1.0, 0), ra=(0.15, 1.0, 0), vis=0.9):
    pts = {0: (0, -0.25, 0), 1: ls, 2: rs, 3: (-0.3, 0.1, 0), 4: (0.3, 0.1, 0), 5: lw, 6: rw, 7: (hx - 0.1, 0.5, 0), 8: (hx + 0.1, 0.5, 0),
           9: (hx - 0.1, 0.75, 0), 10: (hx + 0.1, 0.75, 0), 11: la, 12: ra}
    W = np.array([pts[i] for i in range(13)], float); P = np.zeros((13, 3))
    P[:, 0] = 0.5 + W[:, 0] * K / (SIZE[0] / 540); P[:, 1] = 0.5 + W[:, 1] * K; P[:, 2] = vis
    return P.tolist(), W.tolist()

def clip(per_frame, n=150, az=60):  # per_frame: {frame: pose kwargs}; others use defaults. az: camera azimuth of the 3D body (cam_az), 2D is unchanged
    t = np.radians(180 - az); R = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])  # turn about the vertical axis
    ps = [pose(**per_frame.get(i, {})) for i in range(n)]
    return [p[0] for p in ps], [(np.array(p[1]) @ R.T).tolist() for p in ps]

c = 90
# 1. finish: wrist rises to 0.5 m above shoulder (shoulder-hip = 0.5 m = 1.0 L) 20 frames after contact -> ~1.0; before contact doesn't count
fr, W = clip({**{c + i: dict(rw=(0.3, -0.5 * min(i, 20) / 20, 0)) for i in range(0, 31)}, c - 5: dict(rw=(0.3, -0.9, 0))})
r = form_checks(fr, c, SIZE, W, "FH"); assert abs(r["finish"] - 1.0) < 0.05, r
assert r["reach"] is None and r["tilt"] is None, r  # serve-only fields stay None for groundstrokes
# 2. finish uses whichever wrist is higher (two-handed / left hand)
fr, W = clip({c + i: dict(lw=(-0.3, -0.5, 0)) for i in range(8, 15)}); r = form_checks(fr, c, SIZE, W, "BH"); assert abs(r["finish"] - 1.0) < 0.1, r
# 3. low finish (hands stay at waist) is negative
fr, W = clip({}); r = form_checks(fr, c, SIZE, W, "FH"); assert r["finish"] < 0, r
# 4. reach (SV): racket wrist 0.6 m above shoulders = 1.2 L at contact
fr, W = clip({c + i: dict(rw=(0.2, -0.6, 0)) for i in range(-3, 4)}); r = form_checks(fr, c, SIZE, W, "SV"); assert abs(r["reach"] - 1.2) < 0.05, r
assert r["finish"] is None, r
# 5. tilt (peak over c-30..c-5, so a trophy-time dip counts even though the shoulders level out near contact; hence the whole window is set): racket (right) shoulder 0.1 m lower than left, shoulder width 0.4 -> asin(0.1 / hypot(0.4, 0.1)) = 14.0 deg; left-hand player is the mirror
sh = dict(rs=(0.2, 0.1, 0), ls=(-0.2, 0, 0)); fr, W = clip({i: sh for i in range(c - 30, c - 4)})
r = form_checks(fr, c, SIZE, W, "SV"); assert abs(r["tilt"] - 14.0) < 0.5, r
r = form_checks(fr, c, SIZE, W, "SV", hand="L"); assert abs(r["tilt"] + 14.0) < 0.5, r
r = form_checks(fr, c, SIZE, None, "SV"); assert r["tilt"] is None and r["reach"] is not None, r  # no 3D world data: tilt is not trusted in 2D
# 6. lean: shoulders 0.1 m ahead of hips in the swing direction (wrist moves +x) -> atan(0.1/0.5) = 11.3 deg; moving -x flips the sign
lean = {i: dict(rs=(0.3, 0, 0), ls=(-0.1, 0, 0)) for i in range(0, 150)}  # shoulder centre x = 0.1, hip centre x = 0
mv = {i: dict(lean[i], rw=(0.3 + 0.01 * (i - c), 0.25, 0)) for i in range(150)}
fr, W = clip(mv); r = form_checks(fr, c, SIZE, W, "FH"); assert abs(r["lean"] - 11.3) < 0.7, r
mv = {i: dict(lean[i], rw=(0.3 - 0.01 * (i - c), 0.25, 0)) for i in range(150)}
fr, W = clip(mv); r = form_checks(fr, c, SIZE, W, "FH"); assert abs(r["lean"] + 11.3) < 0.7, r
# 7. stance: ankles 0.4 m apart, hips 0.2 m -> 2.0; ankles 0.8 m apart -> 4.0 is dropped (side-on view collapses hip width)
fr, W = clip({i: dict(la=(-0.2, 1, 0), ra=(0.2, 1, 0)) for i in range(150)}); r = form_checks(fr, c, SIZE, W, "FH"); assert abs(r["stance"] - 2.0) < 0.05, r
fr, W = clip({i: dict(la=(-0.4, 1, 0), ra=(0.4, 1, 0)) for i in range(150)}); r = form_checks(fr, c, SIZE, W, "FH"); assert r["stance"] is None, r
# 8. low visibility, missing frames and a contact too close to the clip end all give None, never a number
fr, W = clip({i: dict(vis=0.1) for i in range(150)}); r = form_checks(fr, c, SIZE, W, "FH"); assert all(r[k] is None for k in ("finish", "lean", "stance")), r
r = form_checks([None] * 150, c, SIZE, [None] * 150, "SV"); assert all(v is None for v in r.values()), r
fr, W = clip({}); r = form_checks(fr, 140, SIZE, W, "FH"); assert r["finish"] is None, r  # < 0.5 s after contact in the clip
# 9. view gates (camera azimuth from the 3D body). Shoulders overlapping along the camera axis (side-on, az 90): tilt is None; normal width keeps the value
sh = dict(rs=(0.2, 0.1, 0), ls=(-0.2, 0, 0))
for az, want in ((90, None), (85, None), (60, 14.0), (180, 14.0), (10, 14.0)):
    fr, W = clip({i: sh for i in range(c - 30, c - 4)}, az=az); r = form_checks(fr, c, SIZE, W, "SV")
    assert (r["tilt"] is None) if want is None else abs(r["tilt"] - want) < 0.5, (az, r)
# camera straight behind / in front: lean and reach are None; side view keeps them; no world (old data) keeps them
mv = {i: dict(lean[i], rw=(0.3 + 0.01 * (i - c), 0.25, 0)) for i in range(150)}
for az, ok in ((170, False), (10, False), (145, True), (90, True)):  # not 150: exactly on the 30 deg gate, Linux libm arccos gives 30-eps
    fr, W = clip(mv, az=az); r = form_checks(fr, c, SIZE, W, "FH"); assert (r["lean"] is None) != ok and (not ok or abs(r["lean"] - 11.3) < 0.7), (az, r)
    fr, W = clip({c + i: dict(rw=(0.2, -0.6, 0)) for i in range(-3, 4)}, az=az); r = form_checks(fr, c, SIZE, W, "SV"); assert abs(r["reach"] - 1.2) < 0.05 and (r["lean"] is None) != ok, (az, r)  # reach is not view-gated (front view had no evidence)
fr, W = clip(mv, az=170); r = form_checks(fr, c, SIZE, None, "FH"); assert abs(r["lean"] - 11.3) < 0.7, r
fr, W = clip({c + i: dict(rw=(0.2, -0.6, 0)) for i in range(-3, 4)}, az=170); r = form_checks(fr, c, SIZE, None, "SV"); assert abs(r["reach"] - 1.2) < 0.05 and r["lean"] is not None, r
# tilt majority rule counts only frames dropped for overlap: 14 of 26 frames hidden by visibility, no overlap -> value kept (old behaviour)
fr, W = clip({**{i: sh for i in range(c - 30, c - 4)}, **{i: dict(sh, vis=0.1) for i in range(c - 30, c - 16)}}); r = form_checks(fr, c, SIZE, W, "SV"); assert abs(r["tilt"] - 14.0) < 0.5, r
print("ok")
