# Run: .venv/bin/python tests/test_tracker.py   (plain asserts; cases follow the failure list in testset/results/multi-player_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from pose_full import Tracker

WHITE, BLACK, RED = (95, 0, 0), (15, 0, 0), (50, 60, 40)


def det(x, y, color, scale=0.2):
    return dict(pos=(x, y), scale=scale, color=color)


# two people standing apart keep their slots
t = Tracker(2)
a = [t.step([det(0.3, 0.5, WHITE), det(1.2, 0.5, BLACK)]) for _ in range(20)]
assert all(r == a[0] for r in a) and sorted(a[0]) == [0, 1]
# detector order flips: slots follow the people, not the list order
assert t.step([det(1.2, 0.5, BLACK), det(0.3, 0.5, WHITE)]) == [a[0][1], a[0][0]]

# crossing: positions meet and pass, colours decide
t = Tracker(2); w, b = t.step([det(0.3, 0.5, WHITE), det(1.2, 0.5, BLACK)])
for i in range(1, 31):
    x = 0.3 + 0.03 * i
    r = t.step([det(1.5 - x, 0.5, BLACK), det(x, 0.5, WHITE)])
    assert r == [b, w], (i, r)

# one person leaves for 4 s and comes back elsewhere: same slot, no new id (3 slots)
t = Tracker(3); w, b = t.step([det(0.3, 0.5, WHITE), det(1.2, 0.5, BLACK)])
for _ in range(240): assert t.step([det(1.2, 0.5, BLACK)]) == [b]
assert t.step([det(1.2, 0.5, BLACK), det(1.6, 0.4, WHITE)]) == [b, w]

# a duplicate skeleton on the same person does not take a second slot
t = Tracker(2); r = t.step([det(0.5, 0.5, WHITE), det(0.51, 0.5, WHITE)])
assert r[0] >= 0 and r[1] == -1
# the free slot is still there for the real second person
assert sorted(t.step([det(0.5, 0.5, WHITE), det(1.3, 0.5, BLACK)])) == [0, 1]

# more detections than slots: the extra one is dropped, existing people keep their slots
t = Tracker(2); w, b = t.step([det(0.3, 0.5, WHITE), det(1.2, 0.5, BLACK)])
assert t.step([det(0.3, 0.5, WHITE), det(1.2, 0.5, BLACK), det(0.8, 0.5, RED)]) == [w, b, -1]

# empty frame changes nothing
assert t.step([]) == [] and t.step([det(1.2, 0.5, BLACK)]) == [b]
print("ok")
