# Run: .venv/bin/python tests/test_tracker.py   (plain asserts; cases follow the failure list in testset/results/multi-player_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from pose_full import Tracker, merge, same_person
import numpy as np

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

# merge: one person split over two slots (they almost never coexist, same shirt) becomes one track
seen = np.zeros((100, 3), bool); seen[:50, 0] = seen[50:, 1] = True; seen[48:52, 2] = True; seen[49:51, 1] = True
assert merge(seen, np.array([WHITE, WHITE, BLACK], float)) == [[1, 0], [2]]
# two different people who take turns (never together) stay apart: the shirt colour differs
assert merge(seen[:, :2], np.array([WHITE, BLACK], float)) == [[1], [0]]
# two people in the same shirt who are often on screen together stay apart
both = np.ones((100, 2), bool)
assert merge(both, np.array([WHITE, WHITE], float)) == [[0], [1]]
# three fragments of one person chain into one, biggest first
seen = np.zeros((90, 3), bool); seen[:20, 0] = seen[20:60, 1] = seen[60:, 2] = True
assert merge(seen, np.array([WHITE] * 3, float)) == [[1, 2, 0]]
# a track never seen does not join anything
assert merge(np.zeros((10, 2), bool), np.array([WHITE, WHITE], float)) == [[0], [1]]

# same_person: the single-person model's detection replaces the slot standing where it stands, nothing else
d1 = det(0.5, 0.5, WHITE)
assert same_person(d1, [det(1.3, 0.5, BLACK), det(0.52, 0.5, WHITE)]) == 1
assert same_person(d1, [det(1.3, 0.5, BLACK)]) is None          # it is someone the two-person model did not see
assert same_person(d1, [None, det(0.53, 0.5, WHITE)]) == 1       # empty slots are skipped
assert same_person(d1, []) is None

# 同色交叉仍有連續運動方向；兩個骨架之間超過既有重複判斷距離。
t = Tracker(2)
ids = t.step([det(0.2, 0.49, WHITE, 0.06), det(0.8, 0.51, WHITE, 0.06)])
for i in range(1, 16):
    x = 0.2 + 0.04 * i
    assert t.step([det(x, 0.49, WHITE, 0.06), det(1 - x, 0.51, WHITE, 0.06)]) == ids, i

# 剪接後換位：位置不連續，外觀仍足以分辨身分。
t = Tracker(2)
ids = t.step([det(0.2, 0.5, WHITE), det(0.8, 0.5, BLACK)])
assert t.step([det(0.8, 0.5, WHITE), det(0.2, 0.5, BLACK)]) == ids

# 四人同時換位，不能讓短期位置覆蓋外觀記憶。
colors = (WHITE, BLACK, RED, (45, -40, -35))
positions = ((0.2, 0.3), (0.8, 0.3), (0.2, 0.8), (0.8, 0.8))
t = Tracker(4)
ids = t.step([det(*p, c, 0.08) for p, c in zip(positions, colors)])
assert t.step([det(*p, c, 0.08) for p, c in zip(positions[::-1], colors)]) == ids

# 一人獨留移動，不應只因有空槽就拆成另一個身分。
t = Tracker(4)
[solo] = t.step([det(0.2, 0.6, WHITE)])
assert t.step([det(0.7, 0.6, WHITE)]) == [solo]

# 完全同色且切鏡換位沒有可辨線索，只要求不崩潰、不新增槽。
t = Tracker(2)
t.step([det(0.2, 0.5, WHITE), det(0.8, 0.5, WHITE)])
assert sorted(t.step([det(0.8, 0.5, WHITE), det(0.2, 0.5, WHITE)])) == [0, 1]

# 有空槽時，獨留者的深度、尺度或亮度小變化也不能拆槽。
t = Tracker(4)
[solo] = t.step([det(0.2, 0.6, WHITE)])
assert t.step([det(0.7, 0.61, (94, 0, 0), 0.21)]) == [solo]

# 離場後在不同深度回來，長期區域參照不能讓原本可接回的身分拆槽。
t = Tracker(3)
[solo] = t.step([det(0.2, 0.3, WHITE)])
for _ in range(60): t.step([])
assert t.step([det(0.2, 0.8, WHITE, 0.1)]) == [solo]

# 缺一位時，不能以負的連續成本把不同外觀的人指到對方舊位置。
t = Tracker(3)
colors = ((65, 0, 0), (5, 0, 0), RED)
ids = t.step([det(0.3, 0.5, colors[0]), det(0.55, 0.5, colors[1]), det(1.4, 0.7, colors[2])])
assert t.step([det(0.55, 0.5, colors[0]), det(0.3, 0.5, colors[1])]) == ids[:2]

# 速度超過一個軀幹時仍保留方向，不能直接清零而在交叉當格換號。
t = Tracker(2)
ids = t.step([det(0.2, 0.49, WHITE, 0.06), det(0.8, 0.51, WHITE, 0.06)])
for i in range(1, 9):
    x = 0.2 + 0.08 * i
    assert t.step([det(x, 0.49, WHITE, 0.06), det(1 - x, 0.51, WHITE, 0.06)]) == ids, i

# 有空槽且同色兩槽皆高成本時，仍保留接回較近槽的成本排序。
t = Tracker(3)
ids = t.step([det(0.2, 0.2, WHITE, 0.1), det(0.8, 0.8, WHITE)])
t.step([])
assert t.step([det(0.96, 0.82, (81, 0, 0), 0.22)]) == ids[1:2]

# 缺一人時的近色小距離換位，位置權重不能蓋過足夠的色差。
t = Tracker(3)
ids = t.step([det(0.3, 0.5, (50, 0, 0)), det(0.41, 0.5, (26, 0, 0)), det(1.4, 0.7, WHITE)])
assert t.step([det(0.41, 0.5, (50, 0, 0)), det(0.3, 0.5, (26, 0, 0))]) == ids[:2]

# 首格偏色後漏一格，小幅深度尺度變化不能把原可接回者拆槽。
t = Tracker(3)
ids = t.step([det(0.2, 0.3, (40, 0, 0))])
t.step([])
assert t.step([det(0.26, 0.34, (65, 0, 0), 0.22)]) == ids

# 僅一人可見且亮度改變時，位置仍須區分近槽，避免平均色永久分裂。
t = Tracker(2)
seen = np.zeros((102, 2), bool); col = np.full((102, 2, 3), np.nan)
dets = [det(0.2, 0.5, WHITE), det(1.0, 0.5, BLACK)] + [det(1.0, 0.5, WHITE)] * 100
for f, d in enumerate(dets):
    [k] = t.step([d]); seen[f, k] = True; col[f, k] = d["color"]
means = np.array([col[seen[:, k], k].mean(0) for k in range(2)])
assert len(merge(seen, means)) == 1

# 同色相向運動也可能沿畫面縱向交叉。
t = Tracker(2)
ids = t.step([det(0.49, 0.2, WHITE, 0.06), det(0.51, 0.8, WHITE, 0.06)])
for i in range(1, 16):
    y = 0.2 + 0.04 * i
    assert t.step([det(0.49, y, WHITE, 0.06), det(0.51, 1 - y, WHITE, 0.06)]) == ids, i

# 全槽都用過時，離場後的舊區域也不能壓過相同外觀。
t = Tracker(3)
ids = t.step([det(0.2, 0.2, WHITE, 0.1), det(0.8, 0.8, BLACK, 0.1), det(1.4, 0.5, RED, 0.1)])
for _ in range(240): t.step([])
assert t.step([det(0.2, 0.8, WHITE, 0.1)]) == ids[:1]
print("ok")
