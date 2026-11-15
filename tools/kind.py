"""Stroke kind (FH / BH / SV / OH / ?) from the pose around contact. classify() gives '?' (low conf) when the evidence is thin.
Design and numbers: docs/research/stroke-classify.md."""
import numpy as np

HIGH = 0.25      # racket wrist above the nose by this many torso lengths (best of contact-3 .. contact+5) = SV / OH
FH_MIN = 0.9     # backswing side (racket wrist along the hip line, hip widths, + = racket side) at or above this = FH
BH_MAX = 0.3     # at or below this = BH; between = '?'  (the 0.2-0.4 s before contact: at contact the turning body flips the sign)
VIS_MIN = 0.5
CONF_MIN = 0.5   # callers pre-fill / trust a kind only at or above this
HANG = -0.4      # SV cue: racket wrist this many torso lengths below the shoulder (arm hanging) 1.7-1.0 s before contact


def _m(a): return np.nanmedian(a, axis=0) if np.isfinite(a).any() else np.full(a.shape[1:], np.nan)


def _side(P, W, f, rw, rs, os_, lh, rh):
    """Racket wrist offset from the hip centre along the right-hip direction (hip widths), median over f-24..f-14. 3D (x, z) when W is
    given, else the image x of the 2D pose (only trusted when the hips are wide in the image)."""
    A = (W if W is not None else P[:, :, :2])[f - 24:f - 13].astype(float)
    ax = A[:, rh] - A[:, lh]; off = A[:, rw] - (A[:, lh] + A[:, rh]) / 2
    if W is not None: ax, off = ax[:, [0, 2]], off[:, [0, 2]]
    w = np.linalg.norm(ax, axis=1)
    with np.errstate(all="ignore"): s = np.einsum("ij,ij->i", off, ax) / w ** 2
    s = s[np.isfinite(s) & (w > (0 if W is not None else 0.02))]
    return float(np.median(s)) if len(s) >= 4 else np.nan


def classify(P, f, hand="R", Wd=None):
    """P: pose.npy (frames,33,3) normalised x,y,visibility. f: contact frame (60 fps). Wd: pose_world.npy or None. hand: racket hand R / L
    (L mirrors: left side landmarks, and + = left).  -> dict(kind, conf 0-1, side = backswing side in hip widths, None for SV / OH)."""
    out = dict(kind="?", conf=0.0, side=None)
    if f < 30 or f + 6 > len(P): return out
    rw, rs, os_, lh, rh = (16, 12, 11, 23, 24) if hand == "R" else (15, 11, 12, 24, 23)
    A = P[f - 3:f + 6].astype(float); vis = float(np.nanmean(A[3:8, rw, 2])) if np.isfinite(A[3:8, rw, 2]).any() else 0.0
    sh = _m(A[:, [11, 12], :2]); hip = _m(A[:, [23, 24], :2]).mean(0); nose = _m(A[:, 0, :2])
    if not np.isfinite(np.concatenate([sh.ravel(), hip, nose])).all() or vis < VIS_MIN: return out
    L = np.linalg.norm(sh.mean(0) - hip)
    if not L > 0: return out
    wy = A[:, rw, 1]
    hi = float(np.nanmax((nose[1] - wy) / L)) if np.isfinite(wy).any() else -9.0
    if hi >= HIGH:
        out.update(kind=_high(P, f, rw, L), conf=0.6 if _high(P, f, rw, L) == "SV" else 0.4); return out
    side = _side(P, Wd, f, rw, rs, os_, lh, rh)
    if not np.isfinite(side): return out
    out["side"] = round(side, 2)
    if side >= FH_MIN: out.update(kind="FH", conf=round(min(vis, 1.0, 0.5 + (side - FH_MIN) / 2), 2))
    elif side <= BH_MAX: out.update(kind="BH", conf=round(min(vis, 1.0, 0.5 + (BH_MAX - side) / 2), 2))
    else: out["conf"] = round(0.25 * vis, 2)
    return out


def _high(P, f, rw, L):
    """SV when the racket arm was hanging 1.0-1.7 s before contact (serve starts from rest), else OH. Not validated for OH: see the report."""
    a = f - 100
    if a < 0: return "OH"
    b = f - 60; sh = np.nanmean(P[a:b, [11, 12], 1], axis=1); y = P[a:b, rw, 1]
    if not np.isfinite(y).any() or not np.isfinite(sh).any(): return "OH"
    return "SV" if np.nanmedian((sh - y) / L) < HANG else "OH"
