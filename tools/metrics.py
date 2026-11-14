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
                knee_warn=bool(ok3 and abs(k3 - k2) > KNEE_GAP_MAX) if ok3 else None,
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
