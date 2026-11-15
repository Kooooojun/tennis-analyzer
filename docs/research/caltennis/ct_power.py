# ct_power.py <pose dir> <ct_eval csv> [--front <angle npz> <frame> ...]
# Power-cap metrics across two views of the same stroke: cams 1+3 see one player, 2+4 the other. A stroke = ct_eval candidates
# of cams a and b whose shared-clock times are within MATCH s; each camera's own pose goes through tools/metrics.measure_full.
# Ratio = median |cam a - cam b| / robust SD (IQR / 1.349 of both cameras' values pooled). ratio_c: SD after centring each player
# on its own median (like tools/score.py _cons_spread). CI: 95% bootstrap over pairs, resampled within each player.
# --front: also print turn for given frames of a whole-video 2D+world landmark npz (p2, p3; 1920x1080).
import sys, os, csv, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "..", "tools")]
from metrics import measure_full

MATCH = 0.2  # s; ct_eval peaks of the same swing on the two timelines (sync residual is about +-1 frame)
SZ = np.array([1920, 1088])
F = ["knee", "wrist_speed", "turn", "leg_load", "trunk_share"]  # knee = 2D knee, the yardstick


def rsd(v):
    q1, q3 = np.percentile(v, [25, 75]); return (q3 - q1) / 1.349


def ratios(a, b, g, centre=False):
    d = np.abs(a - b); v = np.r_[a, b]
    if centre: gg = np.r_[g, g]; v = v - np.array([np.median(v[gg == x]) for x in gg])
    s = rsd(v); return np.median(d) / s if s > 0 else np.nan


def table(pairs, label):
    rng = np.random.default_rng(0)  # same draws for every table, whatever ran before
    print(f"\n{label}: n={len(pairs)}")
    print("field        n  med(a-b)  med|a-b|   rSD  ratio  [95% CI]       ratio_c  bias/rSD")
    for k in F:
        p = [(x[k], y[k], x["player"]) for x, y in pairs if x.get(k) is not None and y.get(k) is not None]
        if len(p) < 3: print(f"{k:11s} {len(p):2d}  too few"); continue
        a, b, g = np.array(p, float).T; d = a - b; s = rsd(np.r_[a, b])
        if s <= 0: print(f"{k:11s} {len(p):2d}  rSD 0, n/a"); continue
        idx = [np.flatnonzero(g == x) for x in np.unique(g)]
        bs = [ratios(a[j], b[j], g[j]) for j in (np.concatenate([rng.choice(i, len(i)) for i in idx]) for _ in range(2000))]
        bs = np.array(bs); bs = bs[np.isfinite(bs)]; lo, hi = np.percentile(bs, [2.5, 97.5]) if len(bs) else (np.nan, np.nan)
        f = lambda x, w: f"{x:{w}.2f}" if np.isfinite(x) else f"{'n/a':>{w}s}"
        print(f"{k:11s} {len(p):2d} {np.median(d):9.3f} {np.median(np.abs(d)):8.3f} {s:6.3f} {f(np.median(np.abs(d)) / s, 6)}  [{f(lo, 4)}, {f(hi, 4)}]   {f(ratios(a, b, g, True), 6)}  {f(abs(np.median(d)) / s, 8)}")


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
            near = [q for q in B if abs(float(q["t"]) - float(r["t"])) <= MATCH]
            same = [q for q in near if q["hand"] == r["hand"]]  # faster wrist differs = two different peaks, not one swing
            if near and not same: skipped += 1
            if not same: continue
            q = min(same, key=lambda s: abs(float(s["t"]) - float(r["t"])))
            pairs.append((m(r) | dict(az=float(r["az_contact"]), player=a), m(q) | dict(az=float(q["az_contact"]), player=a)))
    print(f"\n=== speed >= {vmin} m/s: {len(pairs)} pairs ({skipped} in window with only a different reference hand, dropped)")
    if not pairs: print("no pairs"); return
    table(pairs, "all pairs")
    # az split: the camera nearer to side-on (|az - 90| smaller) vs the other one of the same stroke
    side = lambda x: abs(abs(x["az"]) - 90)
    table([(x, y) if side(x) <= side(y) else (y, x) for x, y in pairs], "ordered (a = nearer side-on cam)")
    isnear = [min(side(x), side(y)) <= 30 for x, y in pairs]
    table([p for p, n in zip(pairs, isnear) if n], "one cam within 30 deg of side-on")
    table([p for p, n in zip(pairs, isnear) if not n], "both cams > 30 deg from side-on")
    az = np.array([abs(p["az"]) for xy in pairs for p in xy])
    print(f"\n|az| of all paired views: min {az.min():.0f} max {az.max():.0f} quartiles {np.percentile(az, [25, 50, 75]).round()}; "
          f"within 30 deg of front {np.sum(az < 30)}, of back {np.sum(az > 150)}; pairs with a front/back view {sum(min(abs(x['az']), 180 - abs(x['az']), abs(y['az']), 180 - abs(y['az'])) < 30 for x, y in pairs)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--front" in args:
        i = args.index("--front"); z = np.load(args[i + 1]); fr = [int(x) for x in args[i + 2:]]; args = args[:i]
        for f in fr:
            r = measure_full(z["p2"].astype(float), f / 60, (1920, 1080), z["p3"].astype(float))
            print("front", f, {k: r.get(k) for k in F + ["cam_az", "prep"]})
    if args:
        for vmin in (15.0, 20.0, 30.0): main(args[0], args[1], vmin)
