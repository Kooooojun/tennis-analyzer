# 慣用手閘門（純邏輯，合成資料）：速度與高度兩個線索要同一邊才算猜到，否則 UNSURE。
# 用法（repo 根目錄）：.venv/bin/python tests/test_guess_hand.py
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from metrics import hand_gate

N = 600; t = np.arange(N) / 60
def body(fast=16, high=16, slow_amp=0.02):
    """一人站著，fast 那隻手腕揮得快，high 那隻手腕舉過肩膀。座標是 0-1 影像比例。"""
    P = np.zeros((N, 33, 3)); P[:, :, 2] = 1
    P[:, 11, :2] = (0.45, 0.4); P[:, 12, :2] = (0.55, 0.4); P[:, 23, :2] = (0.46, 0.6); P[:, 24, :2] = (0.54, 0.6)
    for w in (15, 16):
        amp = 0.15 if w == fast else slow_amp
        P[:, w, 0] = 0.5 + amp * np.sin(2 * np.pi * 1.5 * t)
        P[:, w, 1] = 0.5 - (0.2 if w == high else 0.0) * np.clip(np.sin(2 * np.pi * 1.5 * t), 0, 1)
    return P

SZ = (960, 540); T = [list(np.arange(1, 9, 1.0))]
h, ratio, why = hand_gate([body()], SZ, T); assert (h, why) == ("R", None) and ratio > 1.15, (h, ratio, why)
h, ratio, why = hand_gate([body(15, 15)], SZ, T); assert (h, why) == ("L", None), (h, ratio, why)
h, ratio, why = hand_gate([body(16, 15)], SZ, T); assert h is None and "height" in why, (h, ratio, why)  # 線索不一致（像 p7、單反影片）
h, ratio, why = hand_gate([body(high=0, slow_amp=0.15)], SZ, T); assert h is None and "ratio" in why, (h, ratio, why)  # 兩手一樣快
h, ratio, why = hand_gate([body()[:20]], SZ, None); assert h is None and "too little" in why, (h, ratio, why)
print("hand_gate OK")

# candidates.py：沒 profile 時就算手猜得出來，cands 的 hand 也要是 None，預填拍種留 '?'（猜錯手時 FH/BH 整個鏡像）
import ast
src = (Path(__file__).resolve().parent.parent / "tools/candidates.py").read_text()
fn = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
g = {}; exec(ast.get_source_segment(src, fn["guess"]), g)
assert g["guess"](dict(v="a", t=1.0, track=0, hand=None)) == "?"
assert "hand=prof[k]" in src, "cands.json 'hand' must be the profile hand only, not the guessed one"
print("prefill OK")
