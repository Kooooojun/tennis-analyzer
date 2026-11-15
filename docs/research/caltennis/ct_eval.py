# ct_eval.py <pose dir> <out.csv> — per stroke: reference knee/elbow (2-view DLT) vs single-camera 2D and MediaPipe-world 3D.
# Pairs: cams 1+3 see one player, 2+4 the other. Each camera is scored on its own timeline; the partner is interpolated to it.
import sys, csv, numpy as np
import os; sys.path[:0] = [os.path.dirname(__file__), "tools"]
from ct_tri import proj, interp, dlt, clock
from metrics import _knee, _angle, _scale, FULL

pdir, out = sys.argv[1:3]
SZ = np.array([1920, 1088]); ERR_MAX = 20.0  # px: a joint whose 2-view reprojection error is above this is dropped from the reference
LEG = [23, 24, 25, 26, 27, 28]; ARM = {"R": (12, 14, 16), "L": (11, 13, 15)}
UP = np.array([0, 0, 1.0])


def az(X, C, f):
    """Camera azimuth around the player, deg: 0 = camera in front of the chest (hip line), +90 = player's right side, 180 = behind."""
    r = np.nanmean(X[f, 24] - X[f, 23], 0); fw = np.cross(UP, r); fw[2] = 0
    to = C - np.nanmean((X[f, 23] + X[f, 24]) / 2, 0); to[2] = 0
    return float(np.degrees(np.arctan2(np.dot(np.cross(fw, to), UP), np.dot(fw, to))) * -1)


def peaks(v, thr, gap):
    """Local maxima of v above thr, at least gap frames apart (largest first)."""
    idx = [i for i in np.argsort(-np.nan_to_num(v)) if v[i] > thr]; keep = []
    for i in idx:
        if all(abs(i - k) >= gap for k in keep): keep.append(i)
    return sorted(keep)


SW = np.arange(33); _l = [1, 2, 3, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31]; SW[_l] = [x + 1 for x in _l]; SW[[x + 1 for x in _l]] = _l


def tri(Pa, Pb, ua, ub):
    """DLT with the partner's left/right labels swapped per frame when that fits better (MediaPipe flips sides, mostly from behind)."""
    X1, e1 = dlt([Pa, Pb], np.stack([ua, ub])); X2, e2 = dlt([Pa, Pb], np.stack([ua, ub[:, SW]]))
    sw = np.nanmedian(e2, 1) < np.nanmedian(e1, 1)
    X1[sw], e1[sw] = X2[sw], e2[sw]
    return X1, e1, sw


def canon(X, e):
    """Make reference left/right anatomical: right hip must lie to the right of the facing direction (nose and toes)."""
    fw = (X[:, 0] - (X[:, 11] + X[:, 12]) / 2) + ((X[:, 31] + X[:, 32]) - (X[:, 29] + X[:, 30])) / 2
    fl = np.einsum("ij,ij->i", X[:, 24] - X[:, 23], np.cross(fw, UP)) < 0
    X[fl], e[fl] = X[fl][:, SW], e[fl][:, SW]
    return fl


rows = []; sync = []
for a, b in ((1, 3), (3, 1), (2, 4), (4, 2)):
    A, B = np.load(f"{pdir}/c{a}.npz"), np.load(f"{pdir}/c{b}.npz"); (Pa, Ca), (Pb, _) = proj(a), proj(b)
    t = clock(a, A); ua = A["lm"][..., :2]
    X, e, sw = tri(Pa, Pb, ua, interp(t, clock(b, B), B["lm"])[..., :2])
    X[e > ERR_MAX] = np.nan; fl = canon(X, e)
    sp = {h: np.linalg.norm(np.diff(X[:, w], axis=0), axis=1) * 60 for h, w in (("L", 15), ("R", 16))}
    sm = {h: np.convolve(np.nan_to_num(x), np.ones(3) / 3, "same") for h, x in sp.items()}
    v = np.fmax(sm["L"], sm["R"])
    # >= 15 m/s wrist (3-frame mean) = a swing, 1 s apart; 8-12 m/s peaks were ready-position fidgets and ball pick-ups (checked by eye)
    hits = [c for c in peaks(v, 15.0, 60) if 48 <= c < len(t) - 3]
    if a in (1, 2):  # sync check on the swing frames: shift partner by d frames, median wrist error
        fr = [c + k for c in hits[:40] for k in range(-6, 3)]
        for d in range(-15, 16, 1):
            _, ed, _ = tri(Pa, Pb, ua[fr], interp(t[fr] + d / 60, clock(b, B), B["lm"])[..., :2])
            ed = ed[:, [15, 16]]
            sync.append((a, b, d, float(np.nanmedian(ed))))
    xy = ua / SZ * _scale((960, 544)); Wd = A["world"]
    for c in hits:
        hand = "L" if sm["L"][c] > sm["R"][c] else "R"; s_, e_, w_ = ARM[hand]  # arm = the faster wrist at this swing (reference labels)
        win = range(c - 48, c - 5); ct = range(c - 2, c + 3)
        kr = _knee(X, FULL, c); k2 = _knee(xy, FULL, c); k3 = _knee(Wd, FULL, c)
        el = lambda P: float(np.nanmedian([_angle(P, i, s_, e_, w_) for i in ct]))
        er, e2, e3 = el(X), el(xy), el(Wd)
        rows.append(dict(cam=a, partner=b, hand=hand, f=c, t=round(float(t[c]), 3), speed=round(float(v[c]), 1),
                         knee_ref=kr, knee2d=k2, knee3d=k3, elbow_ref=er, elbow2d=e2, elbow3d=e3,
                         az_knee=az(X, Ca, list(win)), az_contact=az(X, Ca, list(ct)),
                         err_leg=float(np.nanmedian(e[list(win)][:, LEG])), err_arm=float(np.nanmedian(e[list(ct)][:, [s_, e_, w_]])),
                         vis_leg=float(np.nanmean(A["lm"][list(win)][:, LEG, 2])), vis_arm=float(np.nanmean(A["lm"][list(ct)][:, [s_, e_, w_], 2]))))
    print(a, b, "hits", len(hits), "frames", len(t), "partner swapped", sw.mean().round(3), "cam mislabeled", fl.mean().round(3), "ref ok", np.isfinite(X[:, LEG + [12, 14, 16], 0]).mean().round(3))
with open(out, "w") as f:
    w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
with open(out.replace(".csv", "_sync.csv"), "w") as f:
    f.write("cam,partner,shift_frames,median_wrist_err_px\n"); f.writelines(f"{a},{b},{d},{x:.2f}\n" for a, b, d, x in sync)
