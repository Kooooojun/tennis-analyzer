# events_near_sweep.py <manifest> [NAME=value ...] — #60 follow-up: re-run events.py's decision on several prepped videos with
# some constants changed, and score each against its labels with eval_hits (+-3 frames, spans, ignore zones).
# manifest: one video per line, '<label> <work dir> <labels.csv> [player]'; with player, only that player's strokes are targets and
# everything else in the file is an ignore zone (a far-player 'stroke' row then also reports how many of those were kept).
# NAME=value sets events.<NAME> (e.g. RALLY=(1.2,4.0) JUMP_R=5); SLACK=n widens the final hand window n frames back in time.
# Each line ends with same=True when the output equals the work dir's events.npy byte for byte (baseline check), then the
# events this variant added (+t) or dropped (-t) with the sound's bb, the hand speed in the decision window and the swing arc.
# Run from the repo root with the venv Python. The work dirs and labels are private footage: keep them out of git.
import sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import events as E
from attrib import swing
from common import size
from eval_hits import read_labels, score

warnings.filterwarnings("ignore", category=RuntimeWarning)


def detect(d, slack):
    """events.py's __main__ (sound path) on work dir d, without writing anything; returns the events and the hand speed."""
    rows = np.load(d / "sounds.npy").reshape(-1, 4); pp = d / "pose.npy"
    fps = float((d / "src_fps.txt").read_text()) if (d / "src_fps.txt").exists() else E.FPS
    try: method = int((d / "pose_method.txt").read_text().strip())
    except (OSError, ValueError): method = 0
    if method < 2: fps = E.FPS
    poses = [np.load(q).astype(np.float64) for q in [pp, *sorted(d.glob("pose_t*.npy"))]]
    w, h = size(d / "proxy.mp4"); ball = np.load(d / "ball.npy"); n = min(len(ball), len(poses[0]))
    hand, who = E.hands(poses, w / h, who=True)
    wr = np.concatenate([np.where((q[:n, [15, 16], 2] > 0.2)[..., None], q[:n, [15, 16], :2], np.nan) for q in poses], axis=1)
    lag = E.estimate_lag([r[0] for r in E.pick(rows, hand, lag=0, slack=15, who=who, low=False)],
                         E.ball_turns(ball[:n], wr, w / h), default=None)
    lag = E.LAG if lag is None else lag
    out = np.array(E.pick(rows, hand, lag, slack=slack, who=who, source_fps=fps), dtype=np.float64).reshape(-1, 3)
    return out, hand, rows, lag, poses[0], w / h


def main():
    slack = 0
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        if k == "SLACK": slack = int(v)
        else: setattr(E, k, eval(v))   # constants are numbers or tuples
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"): continue
        name, d, lab, *who = line.split(); d = Path(d); who = who[0] if who else None
        out, hand, rows, lag, pose, aspect = detect(d, slack); pred = out[:, 0].tolist()
        base = np.load(d / "events.npy")[:, 0]
        labels, spans = read_labels(lab)
        target = lambda r: r["kind"] == "stroke" and (who is None or r["player"] == who)
        tgt = [float(r["t_sec"]) for r in labels if target(r)]; ign = [float(r["t_sec"]) for r in labels if not target(r)]
        tp, fn, fp = score(tgt, ign, pred, spans=spans)
        msg = (f"{name} TP {len(tp)} FN {len(fn)} FP {len(fp)} recall {len(tp) / max(len(tgt), 1):.1%} "
               f"precision {len(tp) / max(len(tp) + len(fp), 1):.1%} same={np.array_equal(out, np.load(d / 'events.npy'))}")
        if who:
            far = [float(r["t_sec"]) for r in labels if r["kind"] == "stroke" and r["player"] != who]
            msg += f" far_kept {len(score(far, [], pred, spans=spans)[0])}/{len(far)}"
        print(msg)
        for t in pred:
            if len(base) and np.abs(base - t).min() < 0.02: continue
            f = int(round(t * E.FPS)); i = int(np.argmin(np.abs(rows[:, 0] - lag / E.FPS - t))); w = hand[max(0, f - 6):f + 3]
            arc = swing(pose, f, np.array([aspect, 1.0])) if not np.isnan(pose[f, 0, 0]) else np.nan
            print(f"  +{t:.2f} bb {rows[i, 3]:.1f} hand {np.nanmax(w) if len(w) and not np.isnan(w).all() else np.nan:.1f} "
                  f"gap {np.abs(base - t).min() if len(base) else np.nan:.2f} arc {arc:.2f}")
        for t in base:
            if not len(pred) or np.abs(np.array(pred) - t).min() >= 0.02: print(f"  -{t:.2f}")


if __name__ == "__main__":
    main()
