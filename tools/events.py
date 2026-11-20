# events.py <sounds.npy> <ball.npy> <pose.npy> <events.npy> — which sound candidates (hits.py) are racket hits.
# A candidate is a hit when the tracked player's wrist is moving fast at that moment (HAND torso lengths/s relative to the
# hip, so camera distance and portrait/landscape do not matter) and the sound is broadband (BB, see hits.py).
# Within SAME seconds only the loudest stays (on 對牆影片 A loudness ranked better than broadband SNR or onset sharpness):
# one player cannot hit twice that fast, and the ball bouncing before the hit or hitting the wall after it is the usual
# runner-up. There is no cooldown beyond that.
# Two candidates 0.6-0.9 s apart are a hit and its bounce or wall echo: the one with more low band and a faster hand stays.
# A slower swing (HAND_LO, a scoop or self-fed start) counts only with a loud low band one rally beat from a normal hit.
# For method >=2 poses below 50 source fps, the normal gate may fall to 3; a gate <=HAND_LO deliberately disables the slow tier.
# Rows are (t, pk, on) like before, t moved back by the sound lag, measured per video from ball turns (estimate_lag);
# the lag goes to lag.txt next to events.npy: `<frames>`, or `<LAG> fallback` (fewer than 3 matches, or they disagree).
# With several tracked people (pose_t1.npy.. next to pose.npy) any tracked person's fast wrist confirms a hit; people the
# pose model never sees (far doubles players) still cannot confirm theirs. A wrist is not trusted while its person's hip
# jumps (HIP): the pose model hopping between bodies or body parts makes most false hits at rest.
import sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FPS, size

HAND = 6.0     # torso lengths/s; 對牆影片 A hits 6-30 (median 15), sounds with the hand still ~2, wall echoes ~5
BB = 4.0       # dB; 對牆影片 A hits median 11, ground bounces 2
SAME = 0.6     # s
PAIR = 0.9     # s; 對牆影片 A hits are >=1.2 s apart, bounce/echo pairs 0.6-0.9
HAND_LO, BB_LO = 3.5, 6.0  # slow-swing tier: 對牆影片 A scoops 4.3-4.6 with bb 7-9
RALLY = (1.2, 3.0)         # s from the nearest normal hit, one rally beat
HIP = 25.0     # torso lengths/s; 對牆影片 A hits <=4.4 and 對牆影片 A false hits 25-90 (pose model hopping), far serves up to ~20
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
        if N < 2: return np.full(N, np.nan)
        hip[~ok] = np.nan; jump = np.nan_to_num(np.linalg.norm(np.diff(hip, axis=0), axis=1) * FPS / torso[1:]) > HIP   # unseen hip is not a jump
        v[np.convolve(jump, np.ones(2 * JUMP_R + 1))[JUMP_R:JUMP_R + len(jump)] > 0] = np.nan   # "full" sliced: "same" is longer than a clip under 22 frames
        return np.r_[np.nan, np.nanmax(v, 1)]


def hands(poses, aspect, who=False):
    """Fastest trusted wrist over all tracked people, per frame (NaN when nobody's is); with who=True also the index of
    that person per frame (-1 when nobody)."""
    S = np.array([hand_speed(q, aspect) for q in poses])
    with warnings.catch_warnings():  # frames nobody is seen in stay NaN
        warnings.simplefilter("ignore", RuntimeWarning); hand = np.nanmax(S, 0)
    if not who: return hand
    seen = ~np.isnan(S).all(0); k = np.full(S.shape[1], -1); k[seen] = np.nanargmax(S[:, seen], 0)
    return hand, k


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


def estimate_lag(hit_t, turns, lo=-3, hi=15, default=LAG):
    """Sound lag in frames: median over hits of (sound frame - nearest ball turn lo..hi frames before it).
    Falls back to `default` (LAG; None tells a fallback from a measured 0) with fewer than 3 matches or when they
    disagree (IQR > 4 frames): one video, one offset."""
    turns = np.asarray(turns); d = []
    for t in hit_t:
        x = t * FPS - turns; x = x[(x >= lo) & (x <= hi)]
        if len(x): d.append(x.min())
    if len(d) < 3 or np.subtract(*np.percentile(d, [75, 25])) > 4: return default
    return int(round(np.median(d)))


def pick(rows, hand, lag=LAG, slack=0, who=None, low=True, source_fps=FPS):
    """rows (t, pk, on, bb) from hits.py, hand speed per frame -> [(t - lag, pk, on)] for the hits.
    The hand window runs from 6 frames before contact (12 below 50 source fps) up to 2 after; `slack` widens it back
    in time when the lag is not known yet. `who` (per frame, from hands(.., who=True)) is whose wrist that was: a PAIR
    is only merged when it is the same person (two players can hit 0.7 s apart at the net). low=False skips the slow tier.
    Below 50 source fps, use sustained speed over 0.2 s: isolated interpolated pose spikes must not win sound suppression.
    Calibrate that statistic from broadband moving candidates (at least 10), bounded to 3..HAND; otherwise keep HAND.
    A gate <=HAND_LO intentionally disables the slow tier. Callers must verify pose_method >=2 before passing low source fps."""
    def fast(t):
        f = int(round(t * FPS)) - lag; a = max(0, f - (12 if source_fps < 50 else 6) - slack); w = hand[a:max(0, f + 3)]
        if not len(w) or np.isnan(w).all(): return 0.0, -1
        speed = np.percentile(np.nan_to_num(w), 70) if source_fps < 50 else np.nanmax(w)
        person = -1 if who is None else int(who[a + np.nanargmax(w)])
        if source_fps < 50 and who is not None:
            people, counts = np.unique(who[a:a + len(w)][w >= speed], return_counts=True)
            if len(counts):
                winners = people[counts == counts.max()]
                if len(winners) == 1: person = int(winners[0])
        return speed, person
    cand = [(t, pk, on, bb, *fast(t)) for t, pk, on, bb in rows]
    gate = HAND
    if source_fps < 50:
        moving = [r[4] for r in cand if r[3] >= BB and r[4] > 0]
        if len(moving) >= 10: gate = float(np.clip(np.median(moving), 3.0, HAND))
    out = []
    for r in sorted((r for r in cand if r[4] >= gate and r[3] >= BB), key=lambda r: -r[2]):
        if all(abs(r[0] - q[0]) > SAME for q in out): out.append(r)
    hits = []
    for r in sorted(out, key=lambda r: -(r[3] + r[4] / 6)):   # 6 torso lengths/s weigh like 1 dB
        if all(abs(r[0] - q[0]) > PAIR or r[5] != q[5] for q in hits): hits.append(r)
    ts = np.array([r[0] for r in hits])
    for r in sorted(cand, key=lambda r: -r[2]):
        if low and HAND_LO <= r[4] < gate and r[3] >= BB_LO and len(ts) and RALLY[0] <= np.abs(ts - r[0]).min() <= RALLY[1] \
                and all(abs(r[0] - q[0]) > PAIR for q in hits): hits.append(r)
    return [(t - lag / FPS, pk, on) for t, pk, on, *_ in sorted(hits)]


def ball_windows(rows, hand, who, n):
    """第一輪候選估 lag 所需的完整影格範圍，合併為半開區間。"""
    intervals = []
    for t, *_ in pick(rows, hand, lag=0, slack=15, who=who, low=False):
        # Turns in -15..+3 also need 6 frames for peaks, 4 for velocity and 4 for gap endpoints.
        start, stop = max(0, int(np.ceil(t * FPS - 29))), min(n, int(np.floor(t * FPS + 17)) + 1)
        if start < stop: intervals.append((start, stop))
    merged = []
    for start, stop in sorted(intervals):
        if merged and start <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], stop)
        else: merged.append([start, stop])
    return np.array(merged, dtype=np.int64).reshape(-1, 2)


if __name__ == "__main__":
    from platform_util import read_text, utf8_stdout, write_text
    utf8_stdout()
    if len(sys.argv) != 5: sys.exit("usage: events.py <sounds.npy> <ball.npy> <pose.npy> <events.npy>")
    rows, pp = np.load(sys.argv[1]).reshape(-1, 4), Path(sys.argv[3])
    source_fps = FPS
    fps_file = pp.parent / "src_fps.txt"
    if fps_file.exists():
        try: source_fps = float(read_text(fps_file).strip())
        except (OSError, ValueError): sys.exit("無法讀取來源 fps")
        if not np.isfinite(source_fps) or source_fps <= 0: sys.exit("來源 fps 必須是有限的正數")
    try: method = int(read_text(pp.parent / "pose_method.txt").strip())
    except (OSError, ValueError, SystemExit): method = 0
    if method < 2: source_fps = FPS  # Old duplicated-frame poses require the original peak-speed rule.
    poses = [np.load(q).astype(np.float64) for q in [pp, *sorted(pp.parent.glob(pp.stem + "_t*.npy"))]]
    w, h = size(pp.parent / "proxy.mp4"); ball = np.load(sys.argv[2]); n = min(len(ball), len(poses[0]))
    hand, who = hands(poses, w / h, who=True)
    wr = np.concatenate([np.where((q[:n, [15, 16], 2] > 0.2)[..., None], q[:n, [15, 16], :2], np.nan) for q in poses], axis=1)
    lag = estimate_lag([r[0] for r in pick(rows, hand, lag=0, slack=15, who=who, low=False)], ball_turns(ball[:n], wr, w / h),
                       default=None)
    fallback = lag is None; lag = LAG if fallback else lag
    out = np.array(pick(rows, hand, lag, who=who, source_fps=source_fps), dtype=np.float64).reshape(-1, 3)
    # before events.npy: prep re-runs this only when events.npy is stale, so a crash in between must not lose the lag
    write_text(Path(sys.argv[4]).parent / "lag.txt", f"{lag}{' fallback' if fallback else ''}\n")
    np.save(sys.argv[4], out)
    print(f"{len(rows)} sound candidates -> {len(out)} hits, sound lag {lag} frames{' (fallback)' if fallback else ''}")
