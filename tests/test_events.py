"""Run: .venv/bin/python tests/test_events.py"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from events import pick, hand_speed

# A sustained swing wins over a louder sound confirmed by only two isolated pose samples.
hand = np.zeros(180); hand[54:64] = 8
hand[81:90] = np.nan; hand[86:88] = 30
rows = np.array([[1., -20., 12., 9.], [1.45, -20., 20., 9.]])
assert [r[0] for r in pick(rows, hand, source_fps=30)] == [1.], pick(rows, hand, source_fps=30)
assert pick(rows, np.zeros(180), source_fps=30) == []
assert pick(rows, np.full(180, np.nan), source_fps=30) == []

# The same real swing, sampled at 30 fps then interpolated onto the proxy timeline, remains detectable.
pose = np.zeros((180, 33, 3)); pose[..., 2] = 1
pose[:, [11, 12], 1] = .4; pose[:, [23, 24], 1] = .6
pose[:, [11, 23], 0] = .45; pose[:, [12, 24], 0] = .55
pose[:, 15] = [.4, .6, 1]; pose[:, 16] = [.6, .6, 1]
pose[:, 16, 0] += np.interp(np.arange(180), [0, 54, 62, 179], [0, 0, .2, .2])
low = pose[::2]; restored = pose.copy()
for joint in range(33):
    for axis in range(3): restored[:, joint, axis] = np.interp(np.arange(180), np.arange(0, 180, 2), low[:, joint, axis])
assert len(pick(rows[:1], hand_speed(restored, 1.), source_fps=30)) == 1
# A scene of repeated slower, sustained swings can calibrate itself; an isolated weak sound cannot.
times = np.arange(1., 18., 1.6); h = np.zeros(1200)
for t in times:
    f = round(t * 60); h[f-12:f+3] = 4
slow = np.array([[t, -20, 12, 9] for t in times])
assert len(pick(slow, h, source_fps=24)) == len(slow)
assert pick(slow[:1], h, source_fps=24) == []
assert pick(rows[:1], hand, source_fps=60)  # existing callers retain peak-speed behavior
print("ok")
