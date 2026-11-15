# match.py — wrist motion of one tracked person around each hit event. Called by candidates.py; CLI kept for checks:
# match.py <pose.npy> <events.npy> <out.npy> [R|L]. Rows (t, pk, on, sp, arc): peak wrist speed within +-0.2 s and wrist
# arc over +-0.25 s, both in torso lengths, of the racket hand (L = left wrist 15, else right wrist 16).
import sys, warnings, numpy as np
from pathlib import Path

WRIST = {"R": 16, "L": 15}
H_MIN = 0.06   # nose-to-ankle in portrait-frame heights
SEEN = 0.3     # share of the 31 frames around the hit with the person tall enough and the wrist visible
NAN_MAX = 0.8  # share of the 25 wrist speeds around the hit allowed missing (at least 5 left)


def edge_skipped(O, N):
    """How many hit events match() drops for being in the first 45 or last 30 frames of an N-frame clip."""
    f = np.round(np.asarray(O, dtype=np.float64).reshape(-1, O.shape[-1] if len(O) else 3)[:, 0] * 60).astype(int)
    return int(((f < 45) | (f > N - 30)).sum())


def match(P, O, A, hand="R"):
    """P pose (N,33,3) normalized, O events (t, pk, on), A = (W, H) / 540 -> (M,5) rows for events with the person in frame."""
    wi = WRIST[hand]; P = P.astype(np.float64); N = len(P)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        xy = P[:, :, :2] * A; vis = P[:, :, 2]
        h = (np.nanmean(P[:, [27, 28], 1], 1) - P[:, 0, 1]) * A[1] * 9 / 16  # nose-to-ankle in portrait-frame heights, so 0.06 = 58 px either way (far doubles players are 60-90 px)
        L = np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1)
        valid = (h > H_MIN) & (vis[:, wi] > 0.2)
        w = xy[:, wi].copy(); w[~valid] = np.nan
        v = np.full(N, np.nan); v[1:] = np.linalg.norm(w[1:] - w[:-1], axis=1) / L[1:]
        out = []
        for t, pk, on in O:
            f = int(round(t * 60))
            if f < 45 or f > N - 30: continue  # not f-15: candidates.py swing() reads f-30.. and would wrap to the end
            win = v[f - 12:f + 13]
            # only the frames the features use must be seen: far players are tracked in fragments (often 20-40% of a
            # second), and the hitter's fragment usually covers the hit itself
            if np.isnan(win).mean() > NAN_MAX or valid[f - 15:f + 16].mean() < SEEN: continue
            seg = w[f - 15:f + 16]; arc = np.nansum(np.linalg.norm(np.diff(seg, axis=0), axis=1)) / np.nanmedian(L[f - 15:f + 16])  # a fragment may miss frame f
            out.append((t, pk, on, np.nanmax(win), arc))
    return np.array(out, dtype=np.float64).reshape(-1, 5)  # (0,5) when no hit events


if __name__ == "__main__":
    import cv2
    if len(sys.argv) not in (4, 5): sys.exit("usage: match.py <pose.npy> <events.npy> <out.npy> [R|L]")
    c = cv2.VideoCapture(str(Path(sys.argv[1]).parent / "proxy.mp4")); A = np.array([c.get(cv2.CAP_PROP_FRAME_WIDTH), c.get(cv2.CAP_PROP_FRAME_HEIGHT)]) / 540; c.release()
    if not A.all(): sys.exit(f"cannot read {Path(sys.argv[1]).parent / 'proxy.mp4'}")
    out = match(np.load(sys.argv[1]), np.load(sys.argv[2]), A, sys.argv[4] if len(sys.argv) > 4 else "R")
    n = edge_skipped(np.load(sys.argv[2]), len(np.load(sys.argv[1], mmap_mode="r")))  # CLI only: candidates.py calls match() per person and hand, it would repeat
    if n: print(f"頭 0.75 秒／尾 0.5 秒內有 {n} 個擊球沒算（影片太靠近邊界" + ("，影片太短" if len(np.load(sys.argv[1], mmap_mode="r")) < 75 else "") + "）", file=sys.stderr)
    print(len(out), "events with player in frame;", " ".join(f"arc>{q}: {(out[:, 4] > q).sum()}" for q in (0.5, 1, 1.5, 2, 2.5, 3)))
    np.save(sys.argv[3], out)
