# ct_power.py <pose dir> <ct_eval csv> [--front <angle npz> <frame> ...]
# Power-cap metrics across two views of the same stroke: cams 1+3 see one player, 2+4 the other. A stroke = ct_eval candidates
# of cams a and b whose shared-clock times are within MATCH s; each camera's own pose goes through tools/metrics.measure_full.
# Ratio = median |cam a - cam b| / robust SD (IQR / 1.349, both cameras pooled), same SD as testset/eval/body_kin.py.
# --front: also print turn for given frames of a whole-video 2D+world landmark npz (p2, p3; 1920x1080).
import sys, os, csv, numpy as np
sys.path[:0] = [os.path.dirname(__file__), "tools"]
from metrics import measure_full

MATCH = 0.2  # s; ct_eval peaks of the same swing on the two timelines (sync residual is about +-1 frame)
SZ = np.array([1920, 1088])
F = ["knee", "wrist_speed", "turn", "leg_load", "trunk_share"]  # knee = 2D knee, the yardstick


def rsd(v):
    q1, q3 = np.percentile(v, [25, 75]); return (q3 - q1) / 1.349


def table(pairs, label):
    print(f"\n{label}: n={len(pairs)}")
    print("field        n  med(a-b)  med|a-b|   rSD  ratio  bias/rSD")
    for k in F:
        p = [(x[k], y[k]) for x, y in pairs if x.get(k) is not None and y.get(k) is not None]
        if len(p) < 3: print(f"{k:11s} {len(p):2d}  too few"); continue
        a, b = np.array(p, float).T; d = a - b; s = rsd(np.r_[a, b])
        print(f"{k:11s} {len(p):2d} {np.median(d):9.3f} {np.median(np.abs(d)):8.3f} {s:6.3f} {np.median(np.abs(d)) / s:6.2f} {abs(np.median(d)) / s:8.2f}")


POSES, MEAS = {}, {}  # npz members decompress on every access, and both vmin passes share the same strokes


def main(pdir, ev, vmin):
    rows = list(csv.DictReader(open(ev)))
    for c in (1, 2, 3, 4): POSES.setdefault(c, dict(np.load(f"{pdir}/c{c}.npz")))
    poses, meas = POSES, MEAS

    def m(r):
        key = (r["cam"], r["f"])
        if key not in meas:
            Z = poses[int(r["cam"])]; P = Z["lm"].copy(); P[..., :2] /= SZ
            # hand = faster reference wrist (anatomical); the camera's own labels may be flipped, as in the app
            meas[key] = measure_full(P, int(r["f"]) / 60, (960, 544), Z["world"], r["hand"])
        return meas[key]
    pairs = []; skipped = 0
    for a, b in ((1, 3), (2, 4)):
        A = [r for r in rows if r["cam"] == str(a) and float(r["speed"]) >= vmin]
        B = [r for r in rows if r["cam"] == str(b) and float(r["speed"]) >= vmin]
        for r in A:
            q = min(B, key=lambda s: abs(float(s["t"]) - float(r["t"])), default=None)
            if q is None or abs(float(q["t"]) - float(r["t"])) > MATCH: continue
            if q["hand"] != r["hand"]: skipped += 1; continue  # faster wrist differs = two different peaks, not one swing
            pairs.append((m(r) | dict(az=float(r["az_contact"]), hand=r["hand"]), m(q) | dict(az=float(q["az_contact"]), hand=q["hand"])))
    print(f"\n=== speed >= {vmin} m/s: {len(pairs)} pairs ({skipped} dropped: different reference hand)")
    table(pairs, "all pairs")
    # az split: the camera nearer to side-on (|az - 90| smaller) vs the other one of the same stroke
    side = lambda x: abs(abs(x["az"]) - 90)
    table([(x, y) if side(x) <= side(y) else (y, x) for x, y in pairs], "ordered (a = nearer side-on cam)")
    isnear = [min(side(x), side(y)) <= 30 for x, y in pairs]
    table([p for p, n in zip(pairs, isnear) if n], "one cam within 30 deg of side-on")
    table([p for p, n in zip(pairs, isnear) if not n], "both cams > 30 deg from side-on")
    print("\naz pairs (deg):", sorted((round(abs(x["az"])), round(abs(y["az"]))) for x, y in pairs))


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--front" in args:
        i = args.index("--front"); z = np.load(args[i + 1]); fr = [int(x) for x in args[i + 2:]]; args = args[:i]
        for f in fr:
            r = measure_full(z["p2"].astype(float), f / 60, (1920, 1080), z["p3"].astype(float))
            print("front", f, {k: r.get(k) for k in F + ["cam_az", "prep"]})
    if args:
        for vmin in (15.0, 20.0): main(args[0], args[1], vmin)
