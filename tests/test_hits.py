# Run: .venv/bin/python tests/test_hits.py   (plain asserts; T1-T7 are listed in testset/results/hit-detect_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hits import SR, envelope, candidates
from events import hand_speed, pick, estimate_lag, LAG

rng = np.random.default_rng(0)

# T1: one click on quiet noise -> one candidate at the click; noise alone -> none
a = rng.normal(0, 1e-3, SR * 3).astype(np.float32)
a[int(1.5 * SR):int(1.5 * SR) + 80] += rng.normal(0, 0.1, 80)
c = candidates(envelope(a))
assert len(c) == 1 and abs(c[0][0] - 1.5) <= 0.005, c
assert candidates(envelope(rng.normal(0, 1e-3, SR * 3).astype(np.float32))) == []


def body(n, aspect=1.0, wrist=None):
    """n frames of a standing body, normalized (x, y, vis); torso 0.2 frame heights. `wrist` (n,2) overrides the right wrist."""
    p = np.zeros((n, 33, 3)); p[..., 2] = 1
    p[:, [11, 12], 1] = 0.4; p[:, [23, 24], 1] = 0.6
    p[:, [11, 23], 0] = 0.5 - 0.05 / aspect; p[:, [12, 24], 0] = 0.5 + 0.05 / aspect
    p[:, 15] = [0.5 - 0.1 / aspect, 0.6, 1]; p[:, 16] = [0.5 + 0.1 / aspect, 0.6, 1]
    if wrist is not None: p[:, 16, :2] = wrist
    return p


# T2: left/right wrists swapped on alternate frames, nobody moves -> slow
p = body(60); p[1::2, [15, 16]] = p[1::2, [16, 15]]
assert np.nanmax(hand_speed(p, 1.0)) < 0.5, np.nanmax(hand_speed(p, 1.0))
# T3: shoulders out of frame -> unknown
p = body(60); p[:, [11, 12], 1] = -0.02
assert np.isnan(hand_speed(p, 1.0)).all()
# T4: same swing (1 torso length in 0.1 s, i.e. 10 torso/s) in landscape and portrait
for aspect in (16 / 9, 9 / 16):
    x = 0.5 + np.r_[np.zeros(30), np.linspace(0, 0.2 / aspect, 7)[1:], np.full(24, 0.2 / aspect)]
    s = hand_speed(body(60, aspect, np.stack([x, np.full(60, 0.6)], 1)), aspect)
    assert 8 < np.nanmax(s) < 12, (aspect, np.nanmax(s))

# T5, T6: rows are (t, pk, on, bb); hand speed sampled at 60 fps
hand = np.zeros(600); hand[[60, 120, 138, 300]] = 10      # swings at 1.0, 2.0, 2.3, 5.0 s
rows = np.array([[1.0, -20, 12, 9],     # hit
                 [2.0, -20, 12, 9],     # two candidates 0.3 s apart -> keep the louder
                 [2.3, -20, 14, 8],
                 [3.0, -20, 25, 15],    # loud, hand still -> dropped (T5)
                 [5.0, -20, 12, 9]])
t = [r[0] for r in pick(rows, hand, lag=0)]
assert t == [1.0, 2.3, 5.0], t
two = rows[[0, 0]].copy(); two[1, 0] = 2.0
assert [r[0] for r in pick(two, hand, lag=0)] == [1.0, 2.0]   # T6: 1.0 s apart, both kept
# T7: per-video sound lag from ball turns next to the wrist (frames)
hits = [1.0, 3.0, 5.0, 7.0]
assert estimate_lag(hits, [50, 170, 290, 410]) == 10                 # every sound 10 frames after its ball turn
assert estimate_lag(hits, [50, 170]) == LAG                          # too few matches -> default
assert estimate_lag(hits, [59, 168, 285, 402]) == LAG                # matches disagree (1..18) -> default
assert estimate_lag(hits, [50, 170, 290, 410, 100, 230]) == 10       # turns far from any hit are ignored
print("ok")
