# near_only_measure.py <work dir> <cands.json> <near_labels.csv> — #60: score one doubles video's events.npy and cands.json
# against near-player-only labels (eval_hits, +-3 frames, spans, unsure rows as ignore zones), with Wilson 95% intervals,
# then print events.py's gate values for every missed near stroke and every false hit:
#   bb (sounds.npy, dB), hand = fastest trusted wrist in pick()'s window (-6..+2 frames), nan = untrusted frames in that window,
#   peak = fastest wrist -20..+5 frames with the hip-jump mask off and its offset, hip = hip speed max +-12 frames, arc = attrib.swing.
# Labels: near,stroke = targets; coach,stroke = the far player's hits (reported as "coach kept"); anything else = ignore zone.
# Run from the repo root with the venv Python. Work dirs and labels are private footage: keep them out of git.
import json, sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import events as E
from attrib import swing
from common import size
from eval_hits import read_labels, score
from eval_thetis_grip import wilson

warnings.filterwarnings("ignore", category=RuntimeWarning)


def gates(d, times):
    P = np.load(d / "pose.npy").astype(float); S = np.load(d / "sounds.npy").reshape(-1, 4)
    w, h = size(d / "proxy.mp4"); a = w / h; lag = int((d / "lag.txt").read_text().split()[0])
    hand = E.hand_speed(P, a)
    keep = E.JUMP_R; E.JUMP_R = 0; raw = E.hand_speed(P, a); E.JUMP_R = keep
    Q = P[:, :, :2] * [a, 1]; hip = Q[:, [23, 24]].mean(1); L = np.nanmedian(np.linalg.norm(Q[:, [11, 12]].mean(1) - hip, axis=1))
    hipv = np.r_[np.nan, np.linalg.norm(np.diff(hip, axis=0), axis=1) * E.FPS / L]
    for t in times:
        i = int(np.argmin(np.abs(S[:, 0] - lag / E.FPS - t))); f = int(round(t * E.FPS))
        win = hand[f - 6:f + 3]; r = raw[f - 20:f + 6]
        print(f"  {t:.2f}s sound {i}: bb {S[i, 3]:.1f} hand {np.nanmax(win) if not np.isnan(win).all() else np.nan:.1f} "
              f"nan {int(np.isnan(win).sum())}/9 peak {np.nanmax(r):.1f}@{int(np.nanargmax(r)) - 20:+d} "
              f"hip {np.nanmax(hipv[f - 12:f + 13]):.0f} arc {swing(P, f, np.array([a, 1.0])):.2f}")


def main():
    d = Path(sys.argv[1]); labels, spans = read_labels(sys.argv[3])
    near = [float(r["t_sec"]) for r in labels if r["player"] == "near" and r["kind"] == "stroke"]
    coach = [float(r["t_sec"]) for r in labels if r["player"] == "coach" and r["kind"] == "stroke"]
    ign = [float(r["t_sec"]) for r in labels if not (r["player"] == "near" and r["kind"] == "stroke")]
    preds = {"events.npy": np.load(d / "events.npy")[:, 0].tolist(), "cands.json": [c["t"] for c in json.loads(Path(sys.argv[2]).read_text())]}
    for name, pred in preds.items():
        tp, fn, fp = score(near, ign, pred, spans=spans); kept = score(coach, [], pred, spans=spans)[0]
        print(f"{name}: near missed {len(fn)}/{len(near)} ({wilson(len(fn), len(near))[0]:.0%}-{wilson(len(fn), len(near))[1]:.0%}), "
              f"coach kept {len(kept)}/{len(coach)} ({wilson(len(kept), len(coach))[0]:.0%}-{wilson(len(kept), len(coach))[1]:.0%}), "
              f"other false hits {len(fp)}")
    tp, fn, fp = score(near, ign, preds["events.npy"], spans=spans)
    print("missed near strokes:"); gates(d, sorted(fn))
    print("false hits:"); gates(d, sorted(fp))


if __name__ == "__main__":
    main()
