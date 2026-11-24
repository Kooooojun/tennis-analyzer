# attrib_near.py <video work dir> <cands.json> <truth.txt> [ball.npy] — #60 tuning notes: for a two-person rally filmed from behind
# the near player, how the current pipeline keeps or drops each hand-labelled hit, and which signals separate near-player hits from
# far-player (coach) hits. Run from the repo root with the venv Python. Prints one row per labelled hit, then the summary.
# truth.txt: '<sound index> <label> [note]', label N = near player hit, C = far player hit, M = another near-camera person hit,
# O = not a hit, anything else (C?, ?) = unsure and left out. Sound index = row of sounds.npy. ball.npy defaults to the work dir's;
# pass one tracked in windows around every labelled hit (ball.py --windows), because prep only tracks the ball around its own events.
import sys, json, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from attrib import swing
from events import hand_speed


NEAR = 0.15    # s: a kept candidate within this of the hit time counts as "kept"


def wilson(k, n, z=1.96):
    if not n: return (float("nan"),) * 2
    p = k / n; c = (p + z * z / (2 * n)); d = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); s = 1 + z * z / n
    return (c - d) / s, (c + d) / s


def main():
    d, cands, truth = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
    S = np.load(d / "sounds.npy"); P = np.load(d / "pose.npy").astype(float); LAG = int((d / "lag.txt").read_text().split()[0])  # sound lag, frames
    B = np.load(sys.argv[4] if len(sys.argv) > 4 else d / "ball.npy").astype(float)
    wh = np.array([16 / 9, 1.0])
    H = hand_speed(P, 16 / 9)
    T = [(int(r[0]), r[1]) for r in (l.split() for l in truth.read_text().splitlines() if l[:1].isdigit()) if r[1] in "NCM"]
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        size = np.nanmedian(P[:, [27, 28], 1], 1) - P[:, 0, 1]  # nose-to-ankle, frame heights
        med = np.nanmedian(size)
        for i, lab in T:
            t = S[i, 0] - LAG / 60; f = int(round(t * 60))
            kept = any(abs(c["t"] - t) < NEAR for c in cands)
            arc = swing(P, f, wh) if not np.isnan(P[f, 0, 0]) else 0.0
            hand = np.nanmax(H[f - 6:f + 3]) if not np.isnan(H[f - 6:f + 3]).all() else np.nan
            b = B[f - 6:f + 7]; ok = b[:, 2] >= 0.5
            L = np.nanmedian(np.linalg.norm((P[f-6:f+7, 11, :2] + P[f-6:f+7, 12, :2] - P[f-6:f+7, 23, :2] - P[f-6:f+7, 24, :2]) / 2 * wh, axis=1))
            # nearest ball-to-wrist (either wrist) distance in the same frame, torso lengths
            dw = np.nanmin(np.linalg.norm((b[ok, None, :2] - P[f - 6:f + 7][ok][:, [15, 16], :2]) * wh, axis=2)) / L if ok.any() else np.nan
            # ball vertical motion after contact (frame heights/frame): + = down the frame = toward the camera = far player hit it
            a = B[f + 2:f + 15]; ok2 = a[:, 2] >= 0.5
            vy = np.polyfit(np.flatnonzero(ok2), a[ok2, 1], 1)[0] if ok2.sum() >= 4 else np.nan
            rows.append(dict(i=i, lab=lab, kept=kept, arc=round(float(arc), 2), hand=round(float(hand), 1), size=round(float(size[f] / med), 2),
                             ball=int(ok.sum()), dw=round(float(dw), 2), vy=round(float(vy) * 1000, 1)))
    for r in rows: print(*(f"{k}={v}" for k, v in r.items()))
    N = [r for r in rows if r["lab"] == "N"]; C = [r for r in rows if r["lab"] == "C"]
    k1 = sum(r["kept"] for r in C); k2 = sum(not r["kept"] for r in N)
    print(f"\ncurrent pipeline: far-player hits kept {k1}/{len(C)} (95% {wilson(k1, len(C))[0]:.0%}-{wilson(k1, len(C))[1]:.0%}); "
          f"near hits dropped {k2}/{len(N)} (95% {wilson(k2, len(N))[0]:.0%}-{wilson(k2, len(N))[1]:.0%}); "
          f"right {len(C) - k1 + len(N) - k2}/{len(C) + len(N)}")
    for key in ("arc", "hand", "dw", "vy", "size"):
        for lab, g in (("N", N), ("C", C)):
            v = np.array([r[key] for r in g], float); v = v[np.isfinite(v)]
            print(f"{key:5s} {lab}: n={len(v):2d} " + (f"min {v.min():6.2f} median {np.median(v):6.2f} max {v.max():6.2f}" if len(v) else "-"))
    # every kept candidate in the labelled range: what it really was
    lab = {int(r[0]): r[1] for r in (l.split() for l in truth.read_text().splitlines() if l[:1].isdigit())}
    hi = max(lab) and S[max(lab), 0]
    print("\nkept candidates in the labelled range:")
    for c in cands:
        if c["t"] > hi: break
        j = int(np.argmin(abs(S[:, 0] - LAG / 60 - c["t"]))); print(f"  t={c['t']:.2f} sound {j} label {lab.get(j, '-')}")


if __name__ == "__main__":
    main()
