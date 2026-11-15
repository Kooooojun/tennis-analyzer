# Run: .venv/bin/python tests/test_pose_full.py   (plain asserts; cases follow the failure list in testset/results/pose-small-people_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from pose_full import to60, crop_box, crop_to_full, distinct, real, keep, jumps, frames
import numpy as np

# --- to60: source-fps rows -> 60 fps rows (failure 5, 6) ---
# 60 fps source: identity, same object values, n60 rows
A = np.random.default_rng(0).random((120, 33, 3)).astype(np.float32)
assert np.array_equal(to60(A, 60, 120), A)

# 30 fps: even 60-fps frames hit a source frame exactly, odd ones are the midpoint
B = np.arange(10, dtype=np.float32).reshape(10, 1, 1) * np.ones((1, 33, 3), np.float32)
C = to60(B, 30, 19)
assert C.shape == (19, 33, 3) and C.dtype == np.float32
assert np.allclose(C[::2, 0, 0], np.arange(10)) and np.allclose(C[1::2, 0, 0], np.arange(9) + 0.5)
# no extrapolation past the last source frame: asking for 20 rows leaves the last one NaN, never a copy
D = to60(B, 30, 20); assert D.shape[0] == 20 and np.isnan(D[19]).all() and np.allclose(D[18], 9)
# n60 shorter than the source covers: just cut
assert to60(B, 30, 5).shape[0] == 5

# NaN on one side: no half skeleton; visibility (column 2) interpolates like x and y
B2 = B.copy(); B2[4] = np.nan
E = to60(B2, 30, 19)
assert np.isnan(E[7:10]).all() and np.isnan(E[8]).all()  # 60-fps frames 7, 9 straddle the gap, 8 is it
assert np.allclose(E[6], 3) and np.allclose(E[10], 5) and np.allclose(E[5, :, 2], 2.5)

# 24 fps and 29.97 fps: frame j maps to time j/60 with no drift after a long clip
t24 = np.arange(24 * 60, dtype=np.float32).reshape(-1, 1, 1) * np.ones((1, 33, 3), np.float32)  # value = source index
G = to60(t24, 24, 3600)
j = np.arange(3600 - 3); assert np.allclose(G[j, 0, 0], j * 24 / 60, atol=1e-3)
n = 1798; t2997 = np.arange(n, dtype=np.float64).reshape(-1, 1, 1) * np.ones((1, 33, 3))
H = to60(t2997, 30000 / 1001, 3600)
j = np.arange(3590); assert np.allclose(H[j, 0, 0], j / 60 * 30000 / 1001, atol=1e-6)
assert np.isnan(H[-1]).all()  # 1798 frames at 29.97 end at 59.96 s: 60-fps frame 3599 (59.983 s) is past it

# --- crop_box: square around a skeleton, inside the frame (failure 1) ---
W_, H_ = 1920, 1080
xy = np.array([[900, 400], [940, 600]], float)  # 200 px tall person
x0, y0, s = crop_box(xy, W_, H_)
assert s == 400 and 0 <= x0 and x0 + s <= W_ and 0 <= y0 and y0 + s <= H_
assert abs(x0 + s / 2 - 920) <= 1 and abs(y0 + s / 2 - 500) <= 1
assert crop_box(np.array([[50, 1000], [60, 1070]], float), W_, H_) == (0, 1080 - 360, 360)  # corner: min side, pushed in
assert crop_box(np.array([[1900, 0], [1910, 30]], float), W_, H_) == (1920 - 360, 0, 360)
assert crop_box(np.array([[0, 0], [10, 1500]], float), W_, H_)[2] == 1080  # taller than the frame: side capped at H
assert crop_box(np.full((33, 2), np.nan), W_, H_) is None  # nothing seen: caller falls back to the tile search
p = np.full((33, 2), np.nan); p[3] = (100, 100); p[30] = (120, 300)
assert crop_box(p, W_, H_) is not None  # some landmarks NaN: use the rest

# --- crop_to_full: crop-normalized -> full-frame normalized, round trip < 1 px (failure 2) ---
for W_, H_ in ((1920, 1080), (1080, 1920), (1920, 1088)):
    box = crop_box(np.array([[W_ * 0.4, H_ * 0.3], [W_ * 0.45, H_ * 0.5]]), W_, H_)
    pts = np.array([[box[0] + 13.0, box[1] + 211.0], [box[0] + box[2] - 1.0, box[1] + 5.0]])  # pixels inside the box
    q = (pts - box[:2]) / box[2]  # what the landmarker reports on the square crop
    back = crop_to_full(q, box, W_, H_) * (W_, H_)
    assert np.abs(back - pts).max() < 1, (W_, H_, back, pts)

# --- distinct: overlapping tiles see one person twice; copies must not use up the N people (Codex review) ---
def sk(x, y, h):  # skeleton standing at hip (x, y), shoulder-to-ankle h, normalized
    a = np.zeros((33, 3)); a[:, 0] = x; a[:, 2] = 1
    a[[11, 12], 1] = y - h / 3; a[[23, 24], 1] = y; a[[27, 28], 1] = y + 2 * h / 3; a[0, 1] = y - h / 2
    return (a, None)
big, big2, small = sk(0.3, 0.5, 0.3), sk(0.301, 0.502, 0.29), sk(0.7, 0.4, 0.1)
assert [x[0][0, 0] for x in distinct([big, big2, small], 2, aspect=16 / 9)] == [0.3, 0.7]
assert [x[0][0, 0] for x in distinct([big2, small], 2, keep=[big], aspect=16 / 9)] == [0.7]  # already found by a crop
assert len(distinct([big, small, sk(0.1, 0.5, 0.2)], 2, aspect=1)) == 2

# --- real: a crop on a floodlight returns a skeleton with legs visibility ~0 (trunk can be 0.4-0.9); a player's legs >= 0.44 ---
p = sk(0.5, 0.6, 0.2)[0]; p[:, 2] = 0.9; assert real(p)
p[[25, 26, 27, 28], 2] = 0.02; assert not real(p)
p[[11, 12, 23, 24], 2] = 0.1; p[[25, 26, 27, 28], 2] = 0.5; assert real(p)

# --- keep: a crop that follows a slot may lose the legs (net, frame edge, crouch); a tile find must look like a person ---
prev = sk(0.5, 0.6, 0.2)[0]
legs_hidden = sk(0.51, 0.605, 0.2)[0]; legs_hidden[[25, 26, 27, 28], 2] = 0.1
assert keep(legs_hidden, prev, aspect=16 / 9)        # same place as last frame: same person, legs hidden
far = sk(0.8, 0.2, 0.2)[0]; far[[25, 26, 27, 28], 2] = 0.1
assert not keep(far, prev, aspect=16 / 9)             # legs ~0 somewhere else: a floodlight
assert not keep(legs_hidden, None, aspect=16 / 9)     # tile search (no previous skeleton): must pass real()
assert keep(sk(0.8, 0.2, 0.2)[0], prev, aspect=16 / 9)  # legs seen: a person wherever it is

# --- jumps + to60(cut): a slot that switches person between two source frames must not interpolate a mix of the two ---
J = np.stack([sk(0.2, 0.6, 0.2)[0], sk(0.2, 0.6, 0.2)[0], sk(0.7, 0.5, 0.2)[0], sk(0.7, 0.5, 0.2)[0]]).astype(np.float32)
cut = jumps(J, aspect=16 / 9); assert cut.tolist() == [False, True, False]
M = to60(J, 30, 7, cut)
assert np.isnan(M[3]).all() and np.allclose(M[2], J[1]) and np.allclose(M[4], J[2])  # 60-fps frame 3 sits between source 1 and 2
assert np.allclose(M[1], J[0])  # small moves still interpolate
assert not jumps(np.stack([J[0], np.full_like(J[0], np.nan), J[2]]), 1).any()  # a NaN side is not a jump (to60 leaves it NaN anyway)

# --- frames: ffmpeg failing must stop the run, never look like a clip with fewer (or no) frames ---
import tempfile, os
for bad in (b"", b"not a video at all" * 1000):
    fd, fn = tempfile.mkstemp(suffix=".mp4"); os.write(fd, bad); os.close(fd)
    try: list(frames(["-i", fn], 64, 36)); raise AssertionError("no error for a broken file")
    except SystemExit as e: assert "ffmpeg" in str(e), e
    finally: os.unlink(fn)
try: list(frames(["-i", "/nonexistent/x.mp4"], 64, 36)); raise AssertionError("no error for a missing file")
except SystemExit: pass

print("ok")
