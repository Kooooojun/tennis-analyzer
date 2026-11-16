"""多機位整身左右量測：ct_lr.py <參考 npz 目錄> <正式逐機輸出目錄> <候選 csv>。

只在本機寫逐格標籤與彙總；不修改正式姿態。-1 無法判定、-2 身體各組不一致、0 正常、1 整身對調。
"""
import csv
import json
from pathlib import Path
import sys
import warnings

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[3] / "tools")]
from ct_tri import proj, interp, dlt, clock
from metrics import measure_full
from proxy import map_pose

SW = np.arange(33)
for a, b in [(1, 4), (2, 5), (3, 6)] + [(i, i + 1) for i in range(7, 32, 2)]: SW[[a, b]] = b, a
BODY = np.array([[11, 12], [23, 24], [25, 26], [27, 28], [13, 14], [15, 16]])
SUPPORT = [0, 11, 12, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
JOINTS = sorted(SUPPORT + [13, 14, 15, 16])
UP = np.array([0., 0., 1.])
BINS = [(0, 30), (30, 60), (60, 120), (120, 180)]


def orientation(X, err):
    """鼻與腳尖須各自支持相同的肩／髖解剖左右；低重投影誤差本身不夠。"""
    out = np.full(len(X), -1, np.int8)
    ok = np.isfinite(X[:, SUPPORT]).all((1, 2)) & np.isfinite(err[:, SUPPORT]).all(1)
    ok &= (np.max(err[:, SUPPORT], axis=1) <= 20) & (np.median(err[:, SUPPORT], axis=1) <= 10)
    shoulder = X[:, 12] - X[:, 11]; hip = X[:, 24] - X[:, 23]
    nose = X[:, 0] - X[:, [11, 12]].mean(1)
    foot = X[:, [31, 32]].mean(1) - X[:, [29, 30]].mean(1)
    signs = []
    for fw, minimum in ((nose, .03), (foot, .05)):
        fw = fw.copy(); fw[:, 2] = 0
        ok &= np.linalg.norm(fw, axis=1) >= minimum
        right = np.cross(fw, UP)
        for r in (shoulder, hip):
            horizontal = r.copy(); horizontal[:, 2] = 0
            score = np.einsum("ij,ij->i", horizontal, right) / (np.linalg.norm(horizontal, axis=1) * np.linalg.norm(right, axis=1))
            ok &= np.isfinite(score) & (abs(score) >= .2)
            signs.append(score < 0)
    signs = np.array(signs)
    ok &= (signs == signs[0]).all(0)
    torso = np.linalg.norm(X[:, [11, 12]].mean(1) - X[:, [23, 24]].mean(1), axis=1)
    ok &= (torso >= .15) & (torso <= 1)
    for r in (shoulder, hip):
        width = np.linalg.norm(r, axis=1)
        ok &= (width >= .08) & (width <= .8)
    out[ok] = signs[0, ok].astype(np.int8)
    return out


def triangulate(Pa, Pb, ua, ub):
    """沿用兩機 DLT；只估本研究需要的關節，兩種 partner 左右配對取低誤差者。"""
    candidates = []
    for partner in (ub, ub[:, SW]):
        x, e = dlt([Pa, Pb], np.stack([ua[:, JOINTS], partner[:, JOINTS]]))
        X = np.full((*ua.shape[:2], 3), np.nan); err = np.full(ua.shape[:2], np.nan)
        X[:, JOINTS], err[:, JOINTS] = x, e
        candidates.append((X, err))
    (X, e), (Y, f) = candidates
    first, second = np.nanmedian(e[:, SUPPORT], axis=1), np.nanmedian(f[:, SUPPORT], axis=1)
    swap = second < first
    X[swap], e[swap] = Y[swap], f[swap]
    return X, e, swap, abs(first - second)


def label_pose(observed, reference):
    """六組身體點各自須有二倍配對距離優勢；錯人、缺點與混合交換分開。"""
    out = np.full(len(observed), -1, np.int8)
    ok = np.isfinite(observed[:, BODY]).all((1, 2, 3)) & np.isfinite(reference[:, BODY]).all((1, 2, 3))
    torso = np.linalg.norm(reference[:, [11, 12]].mean(1) - reference[:, [23, 24]].mean(1), axis=1)
    displacement = np.linalg.norm(observed[:, [23, 24]].mean(1) - reference[:, [23, 24]].mean(1), axis=1)
    ok &= (torso > 0) & (displacement < .5 * torso)
    own = np.linalg.norm(observed[:, BODY] - reference[:, BODY], axis=3).sum(2)
    other = np.linalg.norm(observed[:, BODY] - reference[:, BODY[:, ::-1]], axis=3).sum(2)
    same, swap = own < .5 * other, other < .5 * own
    out[ok & (same | swap).all(1)] = -2
    out[ok & same.all(1)] = 0
    out[ok & swap.all(1)] = 1
    return out


def candidate(P, W):
    """凍結的單機候選：世界座標面向一致反標、面部／腳點可見，連續至少 12 格。"""
    state = orientation(W[..., [0, 2, 1]] * (1, 1, -1), np.zeros(W.shape[:2]))
    flagged = (state == 1) & (P[:, [0, 29, 30, 31, 32], 2] >= .5).all(1)
    out = np.zeros(len(P), bool)
    edges = np.flatnonzero(np.diff(np.r_[False, flagged, False]))
    for a, b in zip(edges[::2], edges[1::2]):
        if b - a >= 12: out[a:b] = True
    return out


def reference(A, B, a, b, offset=0):
    Pa, Ca = proj(a); Pb, _ = proj(b)
    ub = interp(clock(a, A) + offset / 60, clock(b, B), B["lm"])[..., :2]
    X, e, paired, margin = triangulate(Pa, Pb, A["lm"][..., :2], ub)
    state = orientation(X, e)
    state[~(margin >= 1)] = -1
    state[~(e[:, JOINTS] <= 20).all(1)] = -1
    for P in (Pa, Pb):
        depth = np.einsum("j,fkj->fk", P[2, :3], X[:, SUPPORT]) + P[2, 3]
        state[~(depth > 0).all(1)] = -1
    flip = state == 1
    X[flip], e[flip] = X[flip][:, SW], e[flip][:, SW]
    right = X[:, 24] - X[:, 23]; fw = np.cross(UP, right); fw[:, 2] = 0
    to = Ca - X[:, [23, 24]].mean(1); to[:, 2] = 0
    az = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", fw, to) / (np.linalg.norm(fw, axis=1) * np.linalg.norm(to, axis=1)), -1, 1)))
    projected = X @ Pa[:, :3].T + Pa[:, 3]
    uv = projected[..., :2] / projected[..., 2:]
    return dict(X=X, err=e, state=state, paired=paired, az=az, uv=uv)


def counts(state, mask):
    n = int(mask.sum()); k = int(((state == 1) & mask).sum())
    return dict(n=n, swapped=k, rate=round(k / n, 6) if n else None)


def summary(values):
    a = np.asarray(values, float); a = a[np.isfinite(a)]
    return dict(n=len(a), median=round(float(np.median(a)), 3), p90=round(float(np.percentile(a, 90)), 3), maximum=round(float(a.max()), 3)) if len(a) else dict(n=0)


def main():
    refdir, outdir, hitfile = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    hits = list(csv.DictReader(hitfile.open(encoding="utf-8")))
    result, strokes = [], []
    for a, b in ((1, 3), (2, 4), (3, 1), (4, 2)):
        dest = outdir / f"c{a}"
        checkpoint = dest / "truth.npz"
        P = np.load(dest / "pose.npy"); W = np.load(dest / "pose_world.npy")
        A, B = dict(np.load(refdir / f"c{a}.npz")), dict(np.load(refdir / f"c{b}.npz"))
        assert len(P) == len(A["t"]) and np.array_equal(np.load(dest / "t.npy"), A["t"])
        px = map_pose(P, 1920, 1088, inverse=True)[..., :2] * (1920, 1088)
        if checkpoint.exists():
            Z = dict(np.load(checkpoint))
        else:
            variants = []
            for d in (-1, 0, 1):
                cache = dest / f"reference_{d}.npz"
                if cache.exists(): r = dict(np.load(cache))
                else:
                    r = reference(A, B, a, b, d)
                    np.savez(cache, **r)
                variants.append(r)
            labels = np.array([label_pose(px, r["uv"]) for r in variants])
            refs = np.array([r["state"] for r in variants])
            baseline = variants[1]
            label = labels[1].copy(); label[refs[1] < 0] = -1
            stable = (refs >= 0).all(0) & (labels >= 0).all(0) & (labels == labels[1]).all(0)
            truth = np.where(stable, label, -1).astype(np.int8)
            Z = dict(truth=truth, baseline=label, labels=labels, refs=refs, az=baseline["az"],
                     ref_X=baseline["X"], err=baseline["err"])
            np.savez(checkpoint, **Z)
        truth, az = Z["truth"], Z["az"]
        valid = truth >= 0
        row = dict(cam=a, frames=len(P), seen=int(np.isfinite(P[:, 0, 0]).sum()),
                   reference_baseline=int((Z["refs"][1] >= 0).sum()),
                   baseline=counts(Z["baseline"], Z["baseline"] >= 0),
                   mixed_baseline=int((Z["baseline"] == -2).sum()),
                   unknown=int((~valid).sum()), stable=counts(truth, valid),
                   sync_changed=int(((Z["refs"] >= 0).all(0) & (Z["labels"] >= 0).all(0) & (Z["labels"] != Z["labels"][1]).any(0)).sum()),
                   angles={f"{lo}-{hi}": counts(truth, valid & (az >= lo) & (az < hi if hi < 180 else az <= hi)) for lo, hi in BINS})
        prediction = candidate(P, W)
        tp = int((prediction & (truth == 1)).sum()); fp = int((prediction & (truth == 0)).sum())
        bad, good = int((truth == 1).sum()), int((truth == 0).sum())
        row["detector"] = dict(tp=tp, swapped=bad, fp=fp, normal=good,
                               recall=tp / bad if bad else None, false_flip=fp / good if good else None,
                               unknown_predicted=int((prediction & ~valid).sum()),
                               passed=bool(bad and good and tp / bad >= .7 and fp / good <= .005))
        for lo, hi in BINS:
            m = (Z["refs"][1] >= 0) & (az >= lo) & (az < hi if hi < 180 else az <= hi)
            row["angles"][f"{lo}-{hi}"]["reference_n"] = int(m.sum())
        np.save(dest / "prediction.npy", prediction)
        fixed = P.copy(); fixed[truth == 1] = P[truth == 1][:, SW]
        for hit in (h for h in hits if int(h["cam"]) == a):
            c = int(hit["f"]); lo, hi = max(0, c - 90), min(len(P), c + 61)
            args = ((c - lo) / 60, (960, 540), W[lo:hi], hit["hand"])
            old = measure_full(P[lo:hi], *args); new = measure_full(fixed[lo:hi], *args)
            stroke = dict(cam=a, candidate=c, az=float(az[c]), hand=hit["hand"])
            for key, ids in (("knee", np.arange(c - 48, c - 5)), ("elbow", np.arange(c - 2, c + 3))):
                stroke[key + "_known"] = int(valid[ids].sum())
                stroke[key + "_swapped"] = int((truth[ids] == 1).sum())
                stroke[key + "_old"], stroke[key + "_fixed"] = old[key], new[key]
                stroke[key + "_delta"] = abs(old[key] - new[key]) if old[key] is not None and new[key] is not None else None
            strokes.append(stroke)
        result.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = dict(cameras=result, candidates=len(strokes), impact={})
    for key in ("knee", "elbow"):
        changed = [r[key + "_delta"] for r in strokes if r[key + "_swapped"] and r[key + "_delta"] is not None]
        report["impact"][key] = dict(with_known_swap=summary(changed),
                                     complete_windows=sum(r[key + "_known"] == (43 if key == "knee" else 5) for r in strokes),
                                     changed=sum(x > .05 for x in changed))
    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (outdir / "strokes.json").write_text(json.dumps(strokes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["impact"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        main()
