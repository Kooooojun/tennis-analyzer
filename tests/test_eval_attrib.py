# attrib.who_hit（candidates.py 與 eval_attrib.py 共用）：揮拍進擊球點的人被選中；對方在擊球後大動作（走位）不搶；單人直接是他。
# 用法（repo 根目錄）：.venv/bin/python tests/test_eval_attrib.py
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import attrib
from attrib import who_hit, wrist_hands

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
# 沒 profile 走猜手路徑：猜出 R 後只比右手腕；左手腕的大動作不算
lefty = person(0, 125, wrist=15)  # 只有左手腕在擊球窗內動
assert who_hit({0: lefty, 1: hitter}, {0: None, 1: "R"}, 100 / 60, wh) == 0  # 兩隻都比：左手腕的人贏（與 hitter 平手時取先者；這裡驗證左手腕有算）
assert who_hit({0: lefty, 1: hitter}, {0: "R", 1: "R"}, 100 / 60, wh) == 1  # 猜成 R：只比右手腕，hitter 贏
calls = []
attrib.matched = lambda P, E, wh, h: {1.0: (1.0, 0, 0, 0.5, 2.0)}
attrib.hand_gate = lambda Ps, sz, ts: (calls.append(ts) or ("R", 2.0, "ok"))
Hd = wrist_hands({0: lefty, 1: hitter}, {0: None, 1: "L"}, None, wh, (960, 540))
assert Hd == {0: "R", 1: "L"} and calls == [[[1.0]]], (Hd, calls)  # 只猜沒 profile 的人；有 profile 的不動
print("attrib OK")
