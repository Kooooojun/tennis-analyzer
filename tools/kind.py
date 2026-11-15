"""Stroke kind (FH / BH / SV / OH / ?) from the pose at contact. classify() returns '?' when the evidence is thin; never guesses."""
import numpy as np

HIGH = 0.25      # wrist above the nose by this many torso lengths = SV / OH (calibrated: docs/research/stroke-classify.md)
SIDE_MIN = 0.35  # |racket wrist offset along the shoulder line| / shoulder width needed to call FH / BH
VIS_MIN = 0.5
CONF_MIN = 0.5   # callers pre-fill / trust a kind only at or above this
TWO_HAND = 0.9   # off-hand wrist within this many shoulder widths of the racket wrist = two hands on the racket
DOWN = 0.0       # serve: racket wrist went below the hip (torso lengths) in the 1.2 s .. 0.25 s before contact


def _m(a): return np.nanmedian(a, axis=0) if np.isfinite(a).any() else np.full(a.shape[1:], np.nan)


def classify(P, f, hand="R", Wd=None):
    """P: pose.npy (frames,33,3) normalised x,y,visibility. f: contact frame (60 fps). Wd: pose_world.npy or None. hand: racket hand R / L.
    -> dict(kind, conf 0-1, two_hand True/False/None, side = signed racket-wrist offset in shoulder widths, + = racket side)."""
    out = dict(kind="?", conf=0.0, two_hand=None, side=None)
    if f < 3 or f + 3 > len(P): return out
    rw, ow, rs, os_ = (16, 15, 12, 11) if hand == "R" else (15, 16, 11, 12)
    A = P[f - 2:f + 3].astype(float); xy = A[:, :, :2]
    vis = float(np.nanmean(A[:, rw, 2])) if np.isfinite(A[:, rw, 2]).any() else 0.0
    sh = _m(xy[:, [rs, os_]]); hip = _m(xy[:, [23, 24]]).mean(0); nose = _m(xy[:, 0]); wr = _m(xy[:, rw])
    if not np.isfinite(np.concatenate([sh.ravel(), hip, nose, wr])).all() or vis < VIS_MIN: return out
    L = np.linalg.norm(sh.mean(0) - hip) or np.nan
    if not np.isfinite(L): return out
    hi = (nose[1] - wr[1]) / L
    if hi > HIGH:
        out.update(kind=_high(P, f, rw, L), conf=round(min(1.0, vis, hi / (2 * HIGH)), 2)); return out
    W = None if Wd is None else Wd[f - 2:f + 3].astype(float)
    if W is not None and np.isfinite(W[:, [rw, ow, rs, os_]]).all():  # 3D: horizontal plane (x, z), view-independent
        S = _m(W); ax = (S[rs] - S[os_])[[0, 2]]; w = np.linalg.norm(ax)
        off = lambda j: np.dot(S[j][[0, 2]] - (S[rs] + S[os_])[[0, 2]] / 2, ax / w) / w if w > 0 else np.nan
        sw3 = np.linalg.norm(S[rs] - S[os_])
        side = off(rw); out["two_hand"] = bool(np.linalg.norm(S[rw] - S[ow]) < TWO_HAND * sw3) if np.isfinite(side) else None
    else:  # 2D fallback: shoulder line in the image, unreliable when the shoulders overlap
        ax = sh[0] - sh[1]; w = np.linalg.norm(ax)
        side = np.dot(wr - sh.mean(0), ax / w) / w if w > 0.02 else np.nan
    if not np.isfinite(side): return out
    out["side"] = round(float(side), 2)
    if abs(side) < SIDE_MIN: out["conf"] = round(min(vis, abs(side) / SIDE_MIN) * 0.5, 2); return out
    out.update(kind="FH" if side > 0 else "BH", conf=round(min(vis, abs(side) / (2 * SIDE_MIN), 1.0), 2))
    if out["kind"] == "FH": out["two_hand"] = None
    return out


def _high(P, f, rw, L):
    """SV (racket arm swung down before going up) or OH (racket stayed up). Too little video before contact -> OH-looking default 'SV' is wrong, so OH."""
    a = f - 72
    if a < 0: return "OH"
    hip_y = np.nanmean(P[a:f - 15, [23, 24], 1]); y = P[a:f - 15, rw, 1]
    if not np.isfinite(y).any(): return "OH"
    return "SV" if (np.nanmax(y) - hip_y) / L > DOWN else "OH"
