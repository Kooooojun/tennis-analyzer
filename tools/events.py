# events.py <sounds.npy> <ball.npy> <pose.npy> <events.npy> — which sound candidates (hits.py) are racket hits.
# A candidate is a hit when the tracked player's wrist is moving fast at that moment (HAND torso lengths/s relative to the
# hip, so camera distance and portrait/landscape do not matter) and the sound is broadband (BB, see hits.py).
# Within SAME seconds only the loudest stays (on wall-1 loudness ranked better than broadband SNR or onset sharpness):
# one player cannot hit twice that fast, and the ball bouncing before the hit or hitting the wall after it is the usual
# runner-up. There is no cooldown beyond that.
# Two candidates 0.6-0.9 s apart are a hit and its bounce or wall echo: the one with more low band and a faster hand stays.
# A slower swing (HAND_LO, a scoop or self-fed start) counts only with a loud low band one rally beat from a normal hit.
# Rows are (t, pk, on) like before, t moved back by the sound lag, measured per video from ball turns (estimate_lag).
# With several tracked people (pose_t1.npy.. next to pose.npy) any tracked person's fast wrist confirms a hit; people the
# pose model never sees (far doubles players) still cannot confirm theirs. A wrist is not trusted while its person's hip
# jumps (HIP): the pose model hopping between bodies or body parts makes most false hits at rest.
import sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FPS, size

HAND = 6.0     # torso lengths/s; wall-1 hits 6-30 (median 15), sounds with the hand still ~2, wall echoes ~5
BB = 4.0       # dB; wall-1 hits median 11, ground bounces 2
SAME = 0.6     # s
PAIR = 0.9     # s; wall-1 hits are >=1.2 s apart, bounce/echo pairs 0.6-0.9
HAND_LO, BB_LO = 3.5, 6.0  # slow-swing tier: wall-1 scoops 4.3-4.6 with bb 7-9
RALLY = (1.2, 3.0)         # s from the nearest normal hit, one rally beat
HIP = 25.0     # torso lengths/s; wall-1 hits <=4.4 and wall-1 false hits 25-90 (pose model hopping), far serves up to ~20
JUMP_R = 10    # frames on each side of a hip jump where the wrist is not trusted
LAG = 0        # frames from contact to the sound onset, used when the ball track cannot measure it (see estimate_lag)
GAP, K = 4, 4  # ball turns: fill ball gaps up to 4 frames; velocity compared over 4 frames each side
DV_MIN = 0.008 # min velocity change, frame heights per frame (~3 m/s; gravity adds ~0.0013 per 4 frames)
NEAR = 0.15    # ball-to-wrist distance in frame heights
VIS = 0.3


def hand_speed(pose, aspect):
    """pose (N,33,3) normalized x, y, visibility; aspect = W/H. Fastest wrist relative to the hip mid-point, torso lengths/s.
    NaN when the shoulders or hips are unseen or outside the frame, and within JUMP_R frames of the hip moving faster than HIP."""
    P = pose[:, :, :2] * [aspect, 1]; vis = pose[:, :, 2]; N = len(P)
    trunk = [11, 12, 23, 24]
    ok = (vis[:, trunk] > VIS).all(1) & (pose[:, trunk, 1] > 0.01).all(1) & (pose[:, trunk, 1] < 0.99).all(1)
    hip = P[:, [23, 24]].mean(1)
    L = np.linalg.norm(P[:, [11, 12]].mean(1) - hip, axis=1); L[~ok] = np.nan
    r = P[:, [15, 16]] - hip[:, None]; r[~ok] = np.nan; r[vis[:, [15, 16]] < VIS] = np.nan
    for f in range(1, N):   # the pose model swaps left/right wrists now and then: keep the pairing that moves least
        a, b = r[f - 1], r[f]
        if np.isnan(a).any() or np.isnan(b).any(): continue
        if np.linalg.norm(a[0] - b[1]) + np.linalg.norm(a[1] - b[0]) < np.linalg.norm(a - b, axis=1).sum(): r[f] = b[::-1]
    with warnings.catch_warnings():   # all-NaN slices are expected (nobody in frame)
        warnings.simplefilter("ignore", RuntimeWarning)
        pad = np.r_[np.full(15, np.nan), L, np.full(15, np.nan)]
        torso = np.nanmedian(np.lib.stride_tricks.sliding_window_view(pad, 31), 1) if N else L   # walking toward the camera grows it
        prev, nxt = np.roll(r, 1, 0), np.roll(r, -1, 0); prev[:1] = np.nan; nxt[-1:] = np.nan   # no wrap-around at the ends
        r = np.nanmedian(np.stack([prev, r, nxt]), 0)   # drops one-frame jumps
        v = np.linalg.norm(np.diff(r, axis=0), axis=2) * FPS / torso[1:, None]
        if not N: return v[:, 0]
        jump = np.nan_to_num(np.linalg.norm(np.diff(hip, axis=0), axis=1) * FPS / torso[1:]) > HIP   # unseen hip is not a jump
        v[np.convolve(jump, np.ones(2 * JUMP_R + 1), "same") > 0] = np.nan
        return np.r_[np.nan, np.nanmax(v, 1)]


def hands(poses, aspect):
    """Fastest trusted wrist over all tracked people, per frame (NaN when nobody's is)."""
    with warnings.catch_warnings():  # frames nobody is seen in stay NaN
        warnings.simplefilter("ignore", RuntimeWarning); return np.nanmax([hand_speed(q, aspect) for q in poses], 0)


def fill(xy, gap=GAP):  # linear interpolation over NaN runs of at most `gap` frames
    xy = xy.copy(); ok = ~np.isnan(xy[:, 0]); idx = np.flatnonzero(ok)
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= gap + 1:
            for c in (0, 1): xy[a + 1:b, c] = np.interp(np.arange(a + 1, b), [a, b], xy[[a, b], c])
    return xy


def ball_turns(ball, wrists, aspect):
    """ball (N,3) x,y,conf normalized; wrists (N,2k,2) for k tracked people, normalized (NaN when unseen); aspect = W/H.
    Frames where the ball turns sharply (local max of the velocity change over +-K frames) within NEAR of a wrist."""
    N = len(ball); p = fill(ball[:, :2]) * [aspect, 1]   # frame-height units on both axes
    dv = np.full(N, np.nan)
    for f in range(K, N - K):
        a, b, c = p[f - K], p[f], p[f + K]
        if not np.isnan([a, b, c]).any(): dv[f] = np.linalg.norm((c - b) / K - (b - a) / K)
    out = []
    for f in np.flatnonzero(dv > DV_MIN):
        if dv[f] < np.nanmax(dv[max(0, f - 6):f + 7]): continue
        d = np.linalg.norm(p[f - 3:f + 4, None] - wrists[f - 3:f + 4] * [aspect, 1], axis=2)
        if not np.isnan(d).all() and np.nanmin(d) < NEAR: out.append(int(f))
    return out


def estimate_lag(hit_t, turns, lo=-3, hi=15):
    """Sound lag in frames: median over hits of (sound frame - nearest ball turn lo..hi frames before it).
    Falls back to LAG with fewer than 3 matches or when they disagree (IQR > 4 frames): one video, one offset."""
    turns = np.asarray(turns); d = []
    for t in hit_t:
        x = t * FPS - turns; x = x[(x >= lo) & (x <= hi)]
        if len(x): d.append(x.min())
    if len(d) < 3 or np.subtract(*np.percentile(d, [75, 25])) > 4: return LAG
    return int(round(np.median(d)))


def pick(rows, hand, lag=LAG, slack=0):
    """rows (t, pk, on, bb) from hits.py, hand speed per frame -> [(t - lag, pk, on)] for the hits.
    The hand must be fast in the 6 frames before the contact (sound - lag) up to 2 after; `slack` widens that window back
    in time when the lag is not known yet."""
    def fast(t):
        f = int(round(t * FPS)) - lag; w = hand[max(0, f - 6 - slack):max(0, f + 3)]
        return np.nanmax(w, initial=0) if len(w) else 0.0
    cand = [(t, pk, on, bb, fast(t)) for t, pk, on, bb in rows]
    out = []
    for r in sorted((r for r in cand if r[4] >= HAND and r[3] >= BB), key=lambda r: -r[2]):
        if all(abs(r[0] - q[0]) > SAME for q in out): out.append(r)
    hits = []
    for r in sorted(out, key=lambda r: -(r[3] + r[4] / 6)):   # 6 torso lengths/s weigh like 1 dB
        if all(abs(r[0] - q[0]) > PAIR for q in hits): hits.append(r)
    ts = np.array([r[0] for r in hits])
    for r in sorted(cand, key=lambda r: -r[2]):
        if HAND_LO <= r[4] < HAND and r[3] >= BB_LO and len(ts) and RALLY[0] <= np.abs(ts - r[0]).min() <= RALLY[1] \
                and all(abs(r[0] - q[0]) > SAME for q in hits): hits.append(r)
    return [(t - lag / FPS, pk, on) for t, pk, on, _, _ in sorted(hits)]


if __name__ == "__main__":
    if len(sys.argv) != 5: sys.exit("usage: events.py <sounds.npy> <ball.npy> <pose.npy> <events.npy>")
    rows, pp = np.load(sys.argv[1]).reshape(-1, 4), Path(sys.argv[3])
    poses = [np.load(q).astype(np.float64) for q in [pp, *sorted(pp.parent.glob(pp.stem + "_t*.npy"))]]
    w, h = size(pp.parent / "proxy.mp4"); ball = np.load(sys.argv[2]); n = min(len(ball), len(poses[0]))
    hand = hands(poses, w / h)
    wr = np.concatenate([np.where((q[:n, [15, 16], 2] > 0.2)[..., None], q[:n, [15, 16], :2], np.nan) for q in poses], axis=1)
    lag = estimate_lag([r[0] for r in pick(rows, hand, lag=0, slack=15)], ball_turns(ball[:n], wr, w / h))
    out = np.array(pick(rows, hand, lag), dtype=np.float64).reshape(-1, 3)
    np.save(sys.argv[4], out)
    print(f"{len(rows)} sound candidates -> {len(out)} hits, sound lag {lag} frames")
