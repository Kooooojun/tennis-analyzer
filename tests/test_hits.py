# Run: .venv/bin/python tests/test_hits.py   (plain asserts; T1-T7 are listed in testset/results/hit-detect_pred.md, T8-T11 in
# testset/results/hit-detect-multi_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hits import SR, envelope, candidates
from events import hand_speed, hands, pick, estimate_lag, LAG
from match import match, edge_skipped

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

# T8: a far, fragmented track seen only around the hit (25 of the 60 frames match used to need) still gets a row;
# the other fragment, gone by the hit, does not
p = body(200); p[:, 0, 1] = 0.2; p[:, [27, 28], 1] = 0.9                 # nose and ankles so the person is tall enough
p[:, 16, 0] += np.r_[np.zeros(100), np.linspace(0, 0.1, 100)]           # the wrist moves after frame 100
near_hit, before = p.copy(), p.copy()
near_hit[:85] = np.nan; near_hit[110:] = np.nan; before[np.r_[:55, 85:200]] = np.nan
A, ev = np.array([16 / 9, 1.0]), np.array([[100 / 60, -20, 12]])
assert len(match(near_hit, ev, A)) == 1, match(near_hit, ev, A)
assert len(match(before, ev, A)) == 0
assert len(match(p, np.array([[40 / 60, -20, 12]]), A)) == 0               # window would start before frame 0

# T9: the near track's pose hops to another body for a few frames at a sound (hip 45 torso lengths/s): its wrist is not
# trusted, so no hit from it. A far person swinging then confirms it.
def runner(n=200):
    p = body(n); p[95:101, :, 0] += 0.15; p[95:101, 16, 1] -= 0.15   # another body, its wrist up
    return p
import events; HIP0 = events.HIP
events.HIP = np.inf; assert np.nanmax(hand_speed(runner(), 1.0)[95:104]) > 6   # the wrist alone would confirm it
events.HIP = HIP0; assert np.isnan(hand_speed(runner(), 1.0)[95:104]).all()
still, swing = body(200), body(200, wrist=np.stack([0.6 + np.r_[np.zeros(95), np.linspace(0, 0.2, 6), np.full(99, 0.2)], np.full(200, 0.6)], 1))
row = np.array([[100 / 60, -20, 12, 9]])
assert pick(row, hands([runner(), still], 1.0), lag=0) == []
assert len(pick(row, hands([runner(), swing], 1.0), lag=0)) == 1

# T10: low swing (hand 4.5, loud low band) one rally beat after a normal hit is kept; alone, or with a weak low band, dropped
hand = np.zeros(900); hand[60] = 10; hand[[180, 600]] = 4.5
rows = np.array([[1.0, -20, 12, 9], [3.0, -20, 12, 12], [10.0, -20, 12, 12]])
assert [r[0] for r in pick(rows, hand, lag=0)] == [1.0, 3.0]
weak = rows[:2].copy(); weak[1, 3] = 5
assert [r[0] for r in pick(weak, hand, lag=0)] == [1.0]

# T11: a hit and the ball's bounce or wall echo 0.6-0.9 s apart: keep one (more low band + faster hand), not both
hand = np.zeros(300); hand[[60, 105]] = [10, 8]
assert [r[0] for r in pick(np.array([[1.0, -20, 10, 12], [1.75, -20, 14, 5]]), hand, lag=0)] == [1.0]

# T12: a clip shorter than the hip-jump window (21 frames) still gives one value per frame
assert hand_speed(body(10), 1.0).shape == (10,)

# T13: one frame of pose -> unknown, no crash
assert np.isnan(hand_speed(body(1), 1.0)).all() and len(hand_speed(body(0), 1.0)) == 0
# T14: two people hit 0.7 s apart (net exchange): both kept; the same person 0.7 s apart: one kept
hand = np.zeros(300); hand[[60, 102]] = 10
rows = np.array([[1.0, -20, 12, 12], [1.7, -20, 12, 9]])
assert [r[0] for r in pick(rows, hand, lag=0, who=np.r_[np.zeros(80), np.ones(220)])] == [1.0, 1.7]
assert [r[0] for r in pick(rows, hand, lag=0, who=np.zeros(300))] == [1.0]
# T15: head/tail skips are counted: f=44 skipped, f=45 kept; f=N-30 kept, f=N-29 skipped; short clip; no events
N = 200
assert edge_skipped(np.array([[44 / 60, -20, 12]]), N) == 1 and edge_skipped(np.array([[45 / 60, -20, 12]]), N) == 0
assert edge_skipped(np.array([[(N - 30) / 60, -20, 12]]), N) == 0 and edge_skipped(np.array([[(N - 29) / 60, -20, 12]]), N) == 1
assert edge_skipped(np.array([[1.0, -20, 12], [1.5, -20, 12]]), 60) == 2        # N < 75: every hit skipped
assert edge_skipped(np.zeros((0, 3)), N) == 0
# the count agrees with match(): the edge hits never come back as rows
p = body(N); p[:, 0, 1] = 0.2; p[:, [27, 28], 1] = 0.9
ev = np.array([[44 / 60, -20, 12], [100 / 60, -20, 12], [(N - 29) / 60, -20, 12]])
assert edge_skipped(ev, N) == 2 and set(match(p, ev, A)[:, 0]) <= {100 / 60}
print("ok")
