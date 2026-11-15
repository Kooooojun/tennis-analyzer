# eval_attrib.who_hit：揮拍進擊球點的人被選中；對方在擊球後大動作（走位）不搶；單人直接是他。
# 用法（repo 根目錄）：.venv/bin/python tests/test_eval_attrib.py
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from eval_attrib import who_hit

def person(move_from, move_to, wrist=16):
    P = np.zeros((200, 33, 3)); P[:, :, 2] = 1.0
    for i, (a, b) in enumerate([(11, 12), (23, 24)]): P[:, a, :2] = (0.4, 0.3 + 0.2 * i); P[:, b, :2] = (0.5, 0.3 + 0.2 * i)
    for f in range(200):  # 手腕在 move_from..move_to 之間走：f 在 move 區間內才動
        P[f, wrist, :2] = (0.5 + 0.2 * np.clip((f - 100 + 20) / 25, 0, 1) * (move_from < f < move_to), 0.4)
    return P
wh = np.array((1.0, 1.0))
hitter, other = person(0, 125), person(106, 200)  # hitter 在 [-20,+5] 內動；other 在擊球之後（f 106 起）才動
Ps = {0: other, 1: hitter}
assert who_hit(Ps, {0: "R", 1: "R"}, 100 / 60, wh) == 1  # f=100
assert who_hit({0: other}, {0: None}, 100 / 60, wh) == 0   # 單人
assert who_hit(Ps, {0: None, 1: None}, 100 / 60, wh) == 1  # 沒 profile：兩邊手腕都比
print("eval_attrib OK")
