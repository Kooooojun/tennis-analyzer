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
for bad_t in (10 / 60, 190 / 60):  # 邊界：前後不足 0.5 s 要報錯，不能讓負數切片繞到尾端
    try: who_hit(Ps, {0: "R", 1: "R"}, bad_t, wh); raise AssertionError(bad_t)
    except ValueError: pass
# eval_attrib 的 CSV 檢查：BOM、非有限時間、名字打錯、靠頭尾的行跳過
import tempfile
from eval_attrib import read_holdout
W = {"v": ({0: np.zeros((6000, 33, 3)), 1: np.zeros((6000, 33, 3))}, {}, wh, {0: "p1", 1: "p2"})}
def csv(text):
    p = Path(tempfile.mkdtemp()) / "l.csv"; p.write_bytes(text.encode("utf-8")); return p
assert read_holdout(csv("\ufeffv,10.0,p1\nv,20.0,p2\n"), W) == ([(1, "v", 10.0, "p1"), (2, "v", 20.0, "p2")], [])
for bad in ("v,nan,p1\n", "v,inf,p1\n", "v,10.0,p3\n", "v,abc,p1\n"):
    try: read_holdout(csv("v,5.0,p1\n" + bad), W); raise AssertionError(bad)
    except SystemExit as e: assert "line 2" in str(e), e
assert read_holdout(csv("v,0.2,p1\nv,99.9,p2\nv,50,p1\n"), W) == ([(3, "v", 50.0, "p1")], [1, 2])  # 6000 格 = 100 s：頭 45 格、尾 30 格擋掉
print("attrib OK")
