# ct_tri.py helpers: CalTennis calibration, 2-view DLT triangulation, time alignment by interpolation.
import glob, json, numpy as np

CAL = "testset/raw/datasets/caltennis/camera_calibration/01_28_2026_19_00_ath"


def proj(cam):
    c = json.load(open(glob.glob(f"{CAL}/*_X_{cam}_*/calib.json")[0]))
    return np.array(c["K"]) @ np.array(c["Rt_w2c"]), np.array(c["C"])


def interp(t, src_t, src):
    """src (n,33,3) sampled at src_t -> values at times t (linear; NaN outside or where a neighbour is NaN)."""
    i = np.clip(np.searchsorted(src_t, t), 1, len(src_t) - 1); a = ((t - src_t[i - 1]) / (src_t[i] - src_t[i - 1]))[:, None, None]
    v = src[i - 1] * (1 - a) + src[i] * a
    v[(t < src_t[0]) | (t > src_t[-1])] = np.nan
    return v


def dlt(Ps, uvs):
    """Ps: list of 3x4, uvs: (views, frames, joints, 2) -> X (frames, joints, 3), max reprojection error px (frames, joints)."""
    F, J = uvs.shape[1:3]; X = np.full((F, J, 3), np.nan); err = np.full((F, J), np.nan)
    for f in range(F):
        for j in range(J):
            uv = uvs[:, f, j]
            if not np.isfinite(uv).all(): continue
            A = np.concatenate([[u * P[2] - P[0], v * P[2] - P[1]] for P, (u, v) in zip(Ps, uv)])
            x = np.linalg.svd(A)[2][-1]; x = x[:3] / x[3]; X[f, j] = x
            err[f, j] = max(np.linalg.norm((P @ np.append(x, 1))[:2] / (P @ np.append(x, 1))[2] - q) for P, q in zip(Ps, uv))
    return X, err


# Clock fix found by ct_sync.py (filename start times are off): partner frames shifted by this many 1/60 s minimise the
# epipolar distance of all joints (1-3: 2.66 px at +127 vs 8.83 px at 0; 2-4: 2.48 px at +36 vs 6.64 px at 0).
SHIFT = {1: 0, 2: 0, 3: 126 / 60, 4: 35 / 60}  # coarse search +127/+36, then -1 from the swing-wrist fine check


def clock(cam, Z):
    return Z["t"] - SHIFT[cam]
