"""短缺口參考的合成失敗案例；不需要資料集或模型。"""
from pathlib import Path
from contextlib import redirect_stderr
import io
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs/research/caltennis"))
from test_ct_lr import body
from ct_lr import SW, orientation
from ct_lr_temporal import bridge, main

X = np.repeat(body(), 16, axis=0)
e = np.zeros((16, 33))
geo = np.ones(16, bool)

# 缺口來自鼻水平向量太短；仍有兩端嚴格錨點。
q = X.copy(); q[3:10, 0, :2] = (0, .001)
s = orientation(q, e)
assert s[3:10].tolist() == [-1] * 7
assert bridge(q, s, geo).tolist() == [0] * 16
q[6:9] = q[6:9, SW]
expected = np.zeros(16, int); expected[6:9] = 1
assert np.array_equal(bridge(q, orientation(q, e), geo), expected)

for kind in ('no_left', 'no_right', 'long', 'jump', 'missing', 'mixed', 'contradiction', 'geometry', 'true_turn', 'anchor_conflict'):
    q = X.copy(); q[3:10, 0, :2] = (0, .001)
    g = geo.copy()
    if kind == 'no_left': q[:3, 0, :2] = (0, .001)
    if kind == 'no_right': q[10:, 0, :2] = (0, .001)
    if kind == 'long': q[1:15, 0, :2] = (0, .001)
    if kind == 'jump': q[6, :, 0] += 1
    if kind == 'missing': q[6, 11] = np.nan
    if kind == 'mixed': q[6, [23, 24]] = q[6, [24, 23]]
    if kind == 'contradiction': q[6, 0, :2] = (0, -.2)
    if kind == 'geometry': g[6] = False
    if kind == 'true_turn': q[6, :, :2] *= -1
    if kind == 'anchor_conflict': q[10:, 0, 1] *= -1; q[10:, [29, 30, 31, 32], 1] *= -1
    s = orientation(q, e); r = bridge(q, s, g)
    assert (r[s >= 0] == s[s >= 0]).all(), kind
    assert (r[s < 0] == -1).all(), kind
print('短缺口參考：補判、共同反標、混合、真轉身及拒判測試通過')

# 缺參數時提供用法；已存在的輸出目錄不能覆寫。
with patch.object(sys, "argv", ["ct_lr_temporal.py"]), redirect_stderr(io.StringIO()):
    try:
        main()
    except SystemExit as error:
        assert error.code != 0
    else:
        raise AssertionError("缺參數未拒絕")
with TemporaryDirectory() as tmp, patch.object(sys, "argv", ["ct_lr_temporal.py", "unused", "unused", tmp]):
    try:
        main()
    except FileExistsError:
        pass
    else:
        raise AssertionError("覆寫既有輸出目錄")
print("研究入口：參數與覆寫保護通過")
