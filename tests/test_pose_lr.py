# Run: .venv/bin/python tests/test_pose_lr.py
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from pose_full import correct_lr


def body(n=20):
    p = np.zeros((n, 33, 3), np.float32); p[:, :, 2] = 1
    for l, r, y in ((11, 12, 0.3), (13, 14, 0.4), (15, 16, 0.5), (23, 24, 0.6),
                     (25, 26, 0.75), (27, 28, 0.9)):
        p[:, l, :2] = (0.4, y); p[:, r, :2] = (0.6, y)
    p[:, 0, :2] = (0.5, 0.2)
    for l, r in ((17, 18), (19, 20), (21, 22)):
        p[:, l, :2] = (0.4, 0.5); p[:, r, :2] = (0.6, 0.5)
    w = p.copy(); w[:, :, 2] = 0; w[:, 11::2, 2] = -0.2; w[:, 12::2, 2] = 0.2
    return p, w


def exchange(x, a, b, start=5, end=8):
    x[start:end, a + b] = x[start:end, b + a]


p, w = body(); old = p.copy(); oldw = w.copy()
a, b = correct_lr(p, w, 16 / 9)
assert np.array_equal(a, p) and np.array_equal(b, w)
assert np.array_equal(p, old) and np.array_equal(w, oldw)

# Short independent elbow/wrist glitches recover labels, including hands and confidence.
for left, right in (([13], [14]), ([15, 17, 19, 21], [16, 18, 20, 22])):
    p, w = body(); p[:, left, 2] = 0.8; expected, expectedw = p.copy(), w.copy()
    for x in (p, w): exchange(x, left, right)
    original, originalw = p.copy(), w.copy()
    a, b = correct_lr(p, w, 16 / 9)
    assert np.array_equal(a, expected) and np.array_equal(b, expectedw), left
    assert np.array_equal(p, original) and np.array_equal(w, originalw)
    aa, bb = correct_lr(a, b, 16 / 9)
    assert np.array_equal(aa, a) and np.array_equal(bb, b)

# A 2D glitch need not exist in the separately estimated world positions.
p, w = body(); expected = p.copy(); exchange(p, [15, 17, 19, 21], [16, 18, 20, 22])
a, b = correct_lr(p, w, 1)
assert np.array_equal(a, expected) and np.array_equal(b, w)

# World labels can return to the correct side inside a continuous image-label glitch.
p, w = body(); expected = p.copy()
exchange(p, [15, 17, 19, 21], [16, 18, 20, 22], 5, 8)
exchange(w, [15, 17, 19, 21], [16, 18, 20, 22], 5, 6)
exchange(w, [15, 17, 19, 21], [16, 18, 20, 22], 7, 8)
originalw = w.copy()
a, b = correct_lr(p, w, 1)
assert np.array_equal(a, expected) and np.array_equal(b, originalw)

# The visible hand can anchor a pair while the other is occluded.
p, w = body(); p[:, 15, 2] = 0.1; expected = p.copy()
exchange(p, [15, 17, 19, 21], [16, 18, 20, 22])
a, _ = correct_lr(p, w, 1)
assert np.array_equal(a, expected)

# A cluster of competing short intervals has no stable outer reference: leave it alone.
p, w = body()
for x in (p, w):
    exchange(x, [13], [14], 4, 7); exchange(x, [13], [14], 9, 12)
a, b = correct_lr(p, w, 1)
assert np.array_equal(a, p) and np.array_equal(b, w)

# Consistent endpoints alone cannot justify doubling the forearm lengths into crossed arms.
p, w = body(); p[:, [13, 14]] = p[:, [14, 13]]
exchange(p, [15, 17, 19, 21], [16, 18, 20, 22])
a, _ = correct_lr(p, w, 1)
assert np.array_equal(a, p)

# An unseen elbow cannot supply the geometry check for a wrist correction.
p, w = body(); p[5:8, [13, 14], :2] = np.nan
exchange(p, [15, 17, 19, 21], [16, 18, 20, 22])
a, _ = correct_lr(p, w, 1)
assert np.array_equal(a, p, equal_nan=True)

# Long/clipped intervals, holes, changes of person and weak anchors cannot be repaired safely.
for kind in ("long", "start", "end", "gap", "world_gap", "person", "confidence", "zero"):
    p, w = body()
    if kind == "long": start, end = 4, 18
    elif kind == "start": start, end = 0, 4
    elif kind == "end": start, end = 16, 20
    else: start, end = 5, 8
    for x in (p, w): exchange(x, [13, 15, 17, 19, 21], [14, 16, 18, 20, 22], start, end)
    if kind == "gap": p[6] = np.nan; w[6] = np.nan
    if kind == "world_gap": w[6] = np.nan
    if kind == "person": p[5:8, :, 0] += 2
    if kind == "confidence": p[4, [13, 14, 15, 16], 2] = 0.1
    if kind == "zero": p[:, [11, 12], :2] = p[:, [23, 24], :2]
    a, b = correct_lr(p, w, 16 / 9)
    if kind == "world_gap": assert np.array_equal(b, w, equal_nan=True)
    else:
        assert np.array_equal(a, p, equal_nan=True), kind
        assert np.array_equal(b, w, equal_nan=True), kind

# Nearby crossing hands cannot establish a switch.
p, w = body(); p[:, [15, 16], 0] = (0.49, 0.51)
exchange(p, [15], [16])
a, _ = correct_lr(p, w, 1)
assert np.array_equal(a, p)

# Whole-body reversals are outside this repair; do not create a half-corrected skeleton.
p, w = body()
for x in (p, w): exchange(x, list(range(11, 32, 2)), list(range(12, 33, 2)))
a, b = correct_lr(p, w, 1)
assert np.array_equal(a, p) and np.array_equal(b, w)

# A smooth turn reverses image shoulder order while retaining the actual limb identities.
p, w = body(120)
for i, theta in enumerate(np.linspace(0, np.pi, len(p))):
    rot = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
    w[i] = (w[i] - (0.5, 0.6, 0)) @ rot.T
    p[i, :, 0] = 0.5 + w[i, :, 0]; p[i, :, 1] = 0.6 + w[i, :, 1]
a, b = correct_lr(p, w, 16 / 9)
assert np.array_equal(a, p) and np.array_equal(b, w)

# The 0.2 s limit follows source fps before interpolation.
p, w = body()
for x in (p, w): exchange(x, [13], [14], 5, 12)
a, _ = correct_lr(p, w, 1, 30)
assert np.array_equal(a, p)
a, _ = correct_lr(p, w, 1, 60)
assert not np.array_equal(a, p)

p, w = body(); p[:] = np.nan; w[:] = np.nan
a, b = correct_lr(p, w, 1)
assert np.isnan(a).all() and np.isnan(b).all()
assert correct_lr(p[:0], w[:0], 1)[0].shape == (0, 33, 3)
print("ok")
