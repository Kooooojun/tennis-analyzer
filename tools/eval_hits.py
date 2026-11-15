# eval_hits.py <labels.csv> <events.npy> [player] — score detected hits against hand labels (one-to-one, nearest first).
# labels.csv: t_sec,player,kind with kind stroke | touch | unsure. Strokes are the targets. touch/unsure rows are ignore zones:
# a detection within IGNORE s of one is neither right nor wrong. events.npy (or sounds.npy): rows whose first column is the hit time in seconds.
# With [player], only that player's strokes are targets and the other players' rows become ignore zones.
import csv, sys
import numpy as np

TOL = 3 / 60 + 1e-6   # +-3 frames at 60 fps (epsilon: 0.05 s must count)
IGNORE = 0.25     # a touch/unsure label is a coarse moment, not a contact frame


def score(targets, ignore, pred, tol=TOL):
    """Greedy one-to-one matching, closest pairs first. Returns (tp pairs [(label, pred)], fn labels, fp preds)."""
    pairs = sorted((abs(p - t), i, j) for i, t in enumerate(targets) for j, p in enumerate(pred) if abs(p - t) <= tol)
    used_t, used_p, tp = set(), set(), []
    for _, i, j in pairs:
        if i in used_t or j in used_p: continue
        used_t.add(i); used_p.add(j); tp.append((targets[i], pred[j]))
    fn = [t for i, t in enumerate(targets) if i not in used_t]
    fp = [p for j, p in enumerate(pred) if j not in used_p and not any(abs(p - g) <= IGNORE for g in ignore)]
    return sorted(tp), fn, fp


def self_test():
    tp, fn, fp = score([1.0, 2.0], [5.0], [1.02, 1.03, 2.2, 5.1, 9.0])
    assert tp == [(1.0, 1.02)], tp           # closest wins, the second detection near 1.0 is a duplicate -> FP
    assert fn == [2.0], fn                   # 2.2 is outside +-3 frames
    assert fp == [1.03, 2.2, 9.0], fp        # 5.1 sits in the ignore zone
    assert score([], [], []) == ([], [], [])


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]: self_test(); sys.exit(print("ok"))
    if len(sys.argv) not in (3, 4): sys.exit("usage: eval_hits.py <labels.csv> <events.npy> [player]")
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig", newline="")))
    who = sys.argv[3] if len(sys.argv) == 4 else None
    is_target = lambda r: r["kind"] == "stroke" and (who is None or r["player"] == who)
    targets = [float(r["t_sec"]) for r in rows if is_target(r)]
    ignore = [float(r["t_sec"]) for r in rows if not is_target(r)]
    a = np.load(sys.argv[2]); pred = a.reshape(len(a), -1)[:, 0].tolist() if len(a) else []
    tp, fn, fp = score(targets, ignore, pred)
    err = np.array([p - t for t, p in tp]) * 60
    rec = len(tp) / max(len(targets), 1); prec = len(tp) / max(len(tp) + len(fp), 1)
    print(f"TP {len(tp)} FN {len(fn)} FP {len(fp)} | recall {rec:.0%} precision {prec:.0%}"
          + (f" | error frames median {np.median(err):+.1f} max |{np.abs(err).max():.1f}|" if len(err) else ""))
    if fn: print("  missed:", " ".join(f"{t:.2f}" for t in fn))
    if fp: print("  false: ", " ".join(f"{p:.2f}" for p in fp))
