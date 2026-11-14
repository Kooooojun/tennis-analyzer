# events.py <onsets.npy> <ball.npy> <pose.npy> <events.npy> — hit events from sound AND the ball track, same (t, pk, on) rows as onsets.npy
# so match.py / candidates.py read it unchanged. Sound onsets are kept as they are. A ball event is added when the ball
# turns sharply (velocity change over +-4 frames) near the tracked player's wrist and no sound onset is within 0.15 s.
# Added rows are timed 2 frames after the turn (a hit sound lags the contact by 1-3 frames) and carry pk=-99, on=0 (no sound).
# With several tracked people (pose_t1.npy.. next to pose.npy) the wrist gate uses every tracked person's wrists.
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FPS, size

GAP, K = 4, 4            # fill ball gaps up to 4 frames; velocity compared over 4 frames each side
DV_MIN = 0.008                    # min velocity change, frame heights per frame (~3 m/s, a rally ball is 8+ m/s; gravity adds ~0.0013 per 4 frames)
NEAR = 0.15                       # ball-to-wrist distance in frame heights (arm + racket reach ~0.7 body heights, body ~0.25 frame)
SOUND_WIN = 0.15                  # seconds


def fill(xy, gap=GAP):  # linear interpolation over NaN runs of at most `gap` frames
    xy = xy.copy(); ok = ~np.isnan(xy[:, 0]); idx = np.flatnonzero(ok)
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= gap + 1:
            for c in (0, 1): xy[a + 1:b, c] = np.interp(np.arange(a + 1, b), [a, b], xy[[a, b], c])
    return xy


def ball_events(ball, wrists, aspect):
    """ball (N,3) x,y,conf normalized; wrists (N,2,2) normalized (NaN when unseen); aspect = W/H. Returns [(frame, dv, near)]."""
    N = len(ball); p = fill(ball[:, :2]) * [aspect, 1]   # frame-height units on both axes
    dv = np.full(N, np.nan)
    for f in range(K, N - K):
        a, b, c = p[f - K], p[f], p[f + K]
        if np.isnan([a, b, c]).any(): continue
        dv[f] = np.linalg.norm((c - b) / K - (b - a) / K)
    out = []
    for f in np.flatnonzero(dv > DV_MIN):
        if dv[f] < np.nanmax(dv[max(0, f - 6):f + 7]): continue   # local maximum within +-6 frames
        d = np.linalg.norm(p[f - 3:f + 4, None] - wrists[f - 3:f + 4] * [aspect, 1], axis=2)
        out.append((int(f), float(dv[f]), bool(np.nanmin(d) < NEAR) if not np.isnan(d).all() else False))
    return out


def merge(onsets, evs):
    rows = [tuple(r) for r in onsets]; ts = onsets[:, 0] if len(onsets) else np.zeros(0)
    for f, dv, near in evs:
        if near and (len(ts) == 0 or np.abs(ts - f / FPS).min() > SOUND_WIN): rows.append(((f + 2) / FPS, -99.0, 0.0))
    return np.array(sorted(rows), dtype=np.float64).reshape(-1, 3)


if __name__ == "__main__":
    if len(sys.argv) != 5: sys.exit("usage: events.py <onsets.npy> <ball.npy> <pose.npy> <events.npy>")
    on, ball = np.load(sys.argv[1]), np.load(sys.argv[2]); pp = Path(sys.argv[3])
    poses = [np.load(q).astype(np.float64) for q in [pp, *sorted(pp.parent.glob(pp.stem + "_t*.npy"))]]
    w, h = size(pp.parent / "proxy.mp4"); n = min(len(ball), len(poses[0]))
    wr = np.concatenate([np.where((q[:n, [15, 16], 2] > 0.2)[..., None], q[:n, [15, 16], :2], np.nan) for q in poses], axis=1)  # wrists seen by the pose model
    evs = ball_events(ball[:n], wr, w / h); out = merge(on.reshape(-1, 3), evs)
    np.save(sys.argv[4], out)
    print(f"{len(on)} sound onsets + {len(out) - len(on)} ball-only hits = {len(out)} ({len(evs)} ball turns, {sum(e[2] for e in evs)} near a wrist)")
