"""Stroke kind (FH / BH / SV / OH / ?) from the pose around contact. classify() gives '?' (low conf) when the evidence is thin.
Design and numbers: docs/research/stroke-classify.md."""
import warnings
import numpy as np

HIGH = 0.25      # racket wrist above the nose by this many torso lengths (lowest of contact-3 .. contact+1: still up through contact) = SV / OH
FH_MIN = 0.9     # backswing side (racket wrist along the hip line, hip widths, + = racket side) at or above this = FH
BH_MAX = 0.3     # at or below this = BH; between = '?'  (the 0.2-0.4 s before contact: at contact the turning body flips the sign)
VIS_MIN = 0.5
CONF_MIN = 0.5   # callers trust a kind only at or above this (auto_kind disagreements, scoring)
# candidates.py pre-fills labels.txt only at or above this. kind_conf measures "the backswing looks like FH/BH", not "the ball was hit",
# but fake hits (ball dropped, shadow swings) score lower: on the user's wall video A (all 79 candidates, IN-SAMPLE, picked after
# looking) conf >= 0.58 kept precision 0.81 / recall 0.94 for real hits. Fixed before the held-out check; docs/research/hit-evidence.md.
PREFILL_MIN = 0.58
HANG = -0.4      # SV cue: racket wrist this many torso lengths below the shoulder (arm hanging) 1.7-1.0 s before contact
HIPW_MIN = 0.02  # 2D path: hip width must exceed this fraction of the frame width (kept from the normalised-x version: fewer FH errors)
SV_CONF = 0.45   # below CONF_MIN: the hanging-arm cue does not separate serves from smashes (THETIS: median -0.77 vs -0.71)


def prefill(kind, conf, line=None):
    """labels.txt pre-fill: the kind when conf >= line (default PREFILL_MIN), else '?' (no conf = no hand profile = no guess)."""
    line = PREFILL_MIN if line is None else line
    return kind if kind != "?" and conf is not None and conf >= line else "?"


def _m(a): return np.nanmedian(a, axis=0) if np.isfinite(a).any() else np.full(a.shape[1:], np.nan)


def _side(P, W, f, rw, rs, os_, lh, rh, wmin=0.02):
    """Racket wrist offset from the hip centre along the right-hip direction (hip widths), median over f-24..f-14 frames where the racket
    wrist is visible. 3D (x, z) when W is given, else the image x of the 2D pose (only trusted when the hips are wide in the image)."""
    A = (W if W is not None else P[:, :, :2])[f - 24:f - 13].astype(float)
    A = A[P[f - 24:f - 13, rw, 2] >= VIS_MIN]
    ax = A[:, rh] - A[:, lh]; off = A[:, rw] - (A[:, lh] + A[:, rh]) / 2
    if W is not None: ax, off = ax[:, [0, 2]], off[:, [0, 2]]
    w = np.linalg.norm(ax, axis=1)
    with np.errstate(all="ignore"): s = np.einsum("ij,ij->i", off, ax) / w ** 2
    s = s[np.isfinite(s) & (w > (0 if W is not None else wmin))]
    return float(np.median(s)) if len(s) >= 4 else np.nan


def classify(P, f, hand="R", Wd=None, size=None):
    """P: pose.npy (frames,33,3) normalised x,y,visibility. f: contact frame (60 fps). Wd: pose_world.npy or None. hand: racket hand R / L
    (L mirrors: left side landmarks, and + = left). size: frame (w, h) so x and y are in the same units (None = raw normalised, old behaviour).
    -> dict(kind, conf 0-1, side = backswing side in hip widths, None for SV / OH)."""
    out = dict(kind="?", conf=0.0, side=None)
    if Wd is not None and len(Wd) != len(P): Wd = None  # mismatched pose_world: use the 2D path, not a wrong frame alignment
    if f < 30 or f + 6 > len(P): return out
    rw, rs, os_, lh, rh = (16, 12, 11, 23, 24) if hand == "R" else (15, 11, 12, 24, 23)
    a0 = max(f - 100, 0); P = P[a0:f + 6]; Wd = None if Wd is None else Wd[a0:f + 6]; f -= a0  # only the windows read below, not the video
    if size is not None: P = P.astype(float); P[:, :, :2] *= np.array(size, float) / 540  # same as metrics._scale (no import: cycle)
    A = P[f - 3:f + 6].astype(float); vb = P[f - 24:f - 13, rw, 2]; vb = vb[vb >= VIS_MIN]
    vc = float(np.nanmean(A[3:8, rw, 2])) if np.isfinite(A[3:8, rw, 2]).any() else 0.0
    vis = min(vc, float(np.mean(vb))) if len(vb) >= 4 else 0.0  # contact and the visible backswing frames _side reads (it needs 4)
    sh = _m(A[:, [11, 12], :2]); hip = _m(A[:, [23, 24], :2]).mean(0); nose = _m(A[:, 0, :2])
    if not np.isfinite(np.concatenate([sh.ravel(), hip, nose])).all(): return out
    L = np.linalg.norm(sh.mean(0) - hip)
    if not L > 0: return out
    wy = A[:5, rw, 1]  # f-3..f+1: above the head through contact, not only in a high follow-through
    hi = float(np.nanmin((nose[1] - wy) / L)) if np.isfinite(wy).sum() >= 3 else -9.0  # 1-2 stray frames are not 'through contact'
    if hi >= HIGH and vc >= VIS_MIN:
        k = _high(P, f, rw, L)
        if k: out.update(kind=k, conf=SV_CONF if k == "SV" else 0.4)
        return out
    if vis < VIS_MIN: return out
    side = _side(P, Wd, f, rw, rs, os_, lh, rh, HIPW_MIN * (size[0] / 540 if size is not None else 1))
    if not np.isfinite(side): return out
    out["side"] = round(side, 2)
    if side >= FH_MIN: out.update(kind="FH", conf=round(min(vis, 1.0, 0.5 + (side - FH_MIN) / 2), 2))
    elif side <= BH_MAX: out.update(kind="BH", conf=round(min(vis, 1.0, 0.5 + (BH_MAX - side) / 2), 2))
    else: out["conf"] = round(0.25 * vis, 2)
    return out


def _high(P, f, rw, L):
    """SV when the racket arm was hanging 1.0-1.7 s before contact (serve starts from rest), else OH; None = no history to tell.
    Not validated for OH: see the report."""
    a = f - 100
    if a < 0: return None
    b = f - 60
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning); sh = np.nanmean(P[a:b, [11, 12], 1], axis=1)  # all-NaN rows warn
    y = P[a:b, rw, 1]
    if not (np.isfinite(sh - y)).any(): return None
    return "SV" if np.nanmedian((sh - y) / L) < HANG else "OH"
