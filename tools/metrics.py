"""Per-stroke body metrics. Two entry points share one definition:
measure_full() on a whole-video pose.npy (33 landmarks), measure_clip() on the 150-frame web clip (KEEP landmarks)."""
import numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import PORTRAIT


def _scale(size):
    """Normalized landmarks -> units of 540 px, so thresholds mean the same in portrait (540x960) and landscape (960x540)."""
    return np.array(size or PORTRAIT, float) / 540

SWMAX = 0.5527  # shoulder width / (nose-to-hip) when chest is square to the camera; 100% open


def _angle(xy, f, a, b, c):
    v1 = xy[f, a] - xy[f, b]; v2 = xy[f, c] - xy[f, b]; n = np.linalg.norm(v1) * np.linalg.norm(v2)
    return np.degrees(np.arccos(np.clip(np.dot(v1, v2) / n, -1, 1))) if n > 0 else np.nan


def _med(a):
    a = np.array(a, float); return float(np.nanmedian(a)) if np.isfinite(a).any() else None


KNEE_GAP_MAX = 20.0  # deg; |knee3d - knee| above this = "angle unreliable for this stroke" (threshold chosen from data, see docs/research/knee-3d.md)


def _knee(xy, J, c):
    ks = [min(_angle(xy, i, J['rh'], J['rk'], J['ra']), _angle(xy, i, J['lh'], J['lk'], J['la'])) for i in range(c - 48, c - 5)]
    return float(np.nanpercentile(ks, 10))


def _core(xy, vis, c, J, world=None):
    """J maps names to landmark indices for this array layout. world: optional (frames, n, 3) metres, same layout, for knee3d.
    knee = 2D knee (unchanged definition); knee3d = same window/percentile on 3D angles, None without world data."""
    L = np.linalg.norm((xy[:, J['ls']] + xy[:, J['rs']]) / 2 - (xy[:, J['lh']] + xy[:, J['rh']]) / 2, axis=1)
    bh = np.linalg.norm(xy[:, J['nose']] - (xy[:, J['lh']] + xy[:, J['rh']]) / 2, axis=1)
    openp = np.clip(np.linalg.norm(xy[:, J['rs']] - xy[:, J['ls']], axis=1) / bh / SWMAX * 100, 0, 120)
    hip = (xy[c - 2:c + 3, J['lh'], 1] + xy[c - 2:c + 3, J['rh'], 1]) / 2
    k3 = _knee(world, J, c) if world is not None else np.nan
    k2 = _knee(xy, J, c)
    ok3 = bool(np.isfinite(k3))
    return dict(knee=round(k2, 1), knee3d=round(k3, 1) if ok3 else None,
                knee_warn=bool(abs(k3 - k2) > KNEE_GAP_MAX) if ok3 else None,
                open_min=round(float(np.nanpercentile(openp[c - 48:c - 5], 10)), 1),
                open_contact=round(_med(openp[c - 2:c + 3]), 1),
                contact_h=round(_med((hip - xy[c - 2:c + 3, J['rw'], 1]) / L[c - 2:c + 3]), 2),
                elbow=round(_med([_angle(xy, i, J['rs'], J['re'], J['rw']) for i in range(c - 2, c + 3)]), 1),
                vis=round(float(np.nanmean(vis[c - 2:c + 3, J['rw']])), 2))


FULL = dict(nose=0, ls=11, rs=12, re=14, rw=16, lh=23, rh=24, lk=25, rk=26, la=27, ra=28)
CLIP = dict(nose=0, ls=1, rs=2, re=4, rw=6, lh=7, rh=8, lk=9, rk=10, la=11, ra=12)


def measure_full(P, t, size, Wd=None):
    """P: pose.npy (frames,33,3). t: contact time in seconds. size: proxy (w, h). Adds an automatic FH/BH/OH guess."""
    xy = P[:, :, :2] * _scale(size); f = int(round(t * 60))
    hip_x = np.nanmean((xy[f - 8:f + 9, 23, 0] + xy[f - 8:f + 9, 24, 0]) / 2)
    nose_y = np.nanmean(xy[f - 3:f + 4, 0, 1]); wy = np.nanmin(xy[f - 6:f + 7, 16, 1])
    dx = np.nanmean(xy[f + 15:f + 22, 16, 0]) - np.nanmean(xy[f - 12:f - 6, 16, 0]); side = np.nanmean(xy[f - 2:f + 3, 16, 0]) - hip_x
    auto = "OH" if wy < nose_y - 0.02 else "FH" if side > 0.04 else "BH" if side < -0.02 else ("FH" if dx < 0 else "BH")
    return dict(f=f, auto_kind=auto, **_core(xy, P[:, :, 2], f, FULL, Wd))


def measure_clip(frames, c, size=None, world=None):
    nan = [[np.nan] * 3] * 17
    P = np.array([nan if fr is None else fr for fr in frames], float)
    Wd = np.array([nan if w is None else w for w in world], float) if world else None
    return _core(P[:, :, :2] * _scale(size), P[:, :, 2], c, CLIP, Wd)


# --- arm shape checks (docs/scoring.md §7): pass/fail with a confidence gate, never a degree score ---
ARM_STRAIGHT = 135.0  # deg, mean of 2D and 3D elbow angle (180 = straight): >= this passes. Meta-analysis impact flexion 30 +/- 16 deg; 3D reads ~20 deg more bent than 2D on straight arms, so 135 is loose on purpose
ARM_BENT = 120.0      # deg: mean below this fails; the band between is "cannot tell"
ARM_GAP_MAX = 35.0    # deg; |elbow 3D - elbow 2D| above this = view or tracking is off, say "cannot tell" (straight arms show a 14-31 deg gap, see testset/results/elbow-shape.md)
ARM_DEPTH_MAX = 0.75  # |depth| / length of upper arm and forearm; 0.75 = segment 49 deg out of the image plane
ARM_VIS_MIN = 0.5
FRONT_MIN = 0.1       # m; one-hand BH contact: wrist ahead of the leading shoulder along the shoulder line
_ARM = dict(R=(2, 4, 6), L=(1, 3, 5))  # CLIP indices (shoulder, elbow, wrist) per racket hand


def arm_checks(frames, c, size=None, world=None, kind=None, hand="R", one_hand=False):
    """Racket-arm shape at contact on the CLIP layout (frames/world as in measure_clip), window c-2..c+2.
    serve_arm_straight (kind SV) and bh_elbow_ok / bh_front_ok (kind BH with one_hand) are True / False / None (None = cannot tell).
    *_conf = min(wrist-chain visibility, 1 - arm depth fraction, 1 - 2D/3D gap / 60), 0-1. FH, OH and two-handed BH get None."""
    out = dict(serve_arm_straight=None, serve_arm_conf=None, bh_elbow_ok=None, bh_elbow_conf=None, bh_front_ok=None)
    want_elbow = kind == "SV" or (kind == "BH" and one_hand)
    if not want_elbow or world is None: return out
    s, e, w = _ARM.get(hand, _ARM["R"]); sc = _scale(size); e2, e3, vis, dep = [], [], [], []
    for i in range(c - 2, c + 3):
        if i < 0 or i >= len(frames) or frames[i] is None or world[i] is None: continue
        P = np.array(frames[i], float); W = np.array(world[i], float)
        xy = P[:, :2] * sc
        e2.append(_angle(xy[None], 0, s, e, w)); e3.append(_angle(W[None], 0, s, e, w)); vis.append(P[[s, e, w], 2].min())
        dep.append(max(abs(W[b, 2] - W[a, 2]) / (np.linalg.norm(W[b] - W[a]) or np.nan) for a, b in ((s, e), (e, w))))
    if len(e2) < 3 or not (np.isfinite(e2).any() and np.isfinite(e3).any()): return out
    a2, a3, v, d = _med(e2), _med(e3), _med(vis), _med(dep)
    if None in (a2, a3, v, d): return out
    gap = abs(a3 - a2); conf = round(float(max(0, min(v, 1 - d, 1 - gap / 70))), 2)
    ok = v >= ARM_VIS_MIN and d <= ARM_DEPTH_MAX and gap <= ARM_GAP_MAX
    m = (a2 + a3) / 2; verdict = None if not ok else True if m >= ARM_STRAIGHT else False if m < ARM_BENT else None
    if kind == "SV": out.update(serve_arm_straight=verdict, serve_arm_conf=conf)
    else:
        out.update(bh_elbow_ok=verdict, bh_elbow_conf=conf)
        out["bh_front_ok"] = _front(frames, world, c, s, w, hand, ok)
    return out


def _front(frames, world, c, s, w, hand, ok):
    """One-hand BH: is the wrist ahead of the racket-side shoulder along the shoulder line (3D, metres)? None if the shoulders are not both visible/wide enough."""
    if not ok: return None
    ds = []
    for i in range(c - 2, c + 3):
        if i < 0 or i >= len(world) or world[i] is None or frames[i] is None: continue
        W = np.array(world[i], float); P = np.array(frames[i], float)
        u = W[2, [0, 2]] - W[1, [0, 2]]
        if hand == "L": u = -u
        n = np.linalg.norm(u)
        if n < 0.2 or P[[1, 2], 2].min() < ARM_VIS_MIN: continue
        ds.append(float(np.dot(W[w, [0, 2]] - W[s, [0, 2]], u / n)))
    m = _med(ds)
    return None if m is None else bool(m >= FRONT_MIN)
