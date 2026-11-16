"""多機位左右參考的失敗案例；不需要資料集或模型。"""
from pathlib import Path
from contextlib import redirect_stderr
import io
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "docs/research/caltennis"),
               str(Path(__file__).resolve().parents[1] / "tools")]
from ct_lr import SW, orientation, label_pose, triangulate, candidate
from metrics import _knee, _angle, FULL
from ct_lr_run import heavy_lock


def body():
    X = np.zeros((1, 33, 3))
    X[:, 0] = (0, .2, 1.7)
    for l, r, half, y, z in ((11, 12, .2, 0, 1.5), (23, 24, .15, 0, 1),
                            (13, 14, .35, .1, 1.2), (15, 16, .45, .2, 1.35),
                            (25, 26, .14, .1, .55), (27, 28, .13, 0, .1),
                            (29, 30, .13, -.1, .05), (31, 32, .13, .15, .05)):
        X[:, l] = (-half, y, z)
        X[:, r] = (half, y, z)
    return X


X = body(); e = np.zeros((1, 33))
assert np.array_equal(SW[SW], np.arange(33)) and SW[0] == 0
assert orientation(X, e).tolist() == [0]
assert orientation(X[:, SW], e).tolist() == [1]
for change in ("back_feet", "missing_face", "zero_face", "tiny_face", "high_error", "hips_only", "collapse"):
    q, err = X.copy(), e.copy()
    if change == "back_feet": q[:, [31, 32], 1] = -.2
    if change == "missing_face": q[:, 0] = np.nan
    if change == "zero_face": q[:, 0, :2] = q[:, [11, 12], :2].mean(1)
    if change == "tiny_face": q[:, 0, :2] = (0, .001)
    if change == "high_error": err[:, 0] = 21
    if change == "hips_only": q[:, [23, 24]] = q[:, [24, 23]]
    if change == "collapse": q[:, 24] = q[:, 23]
    assert orientation(q, err).tolist() == [-1], change

# 正式輸出與獨立重投影的配對：缺格、換人、局部交換不能冒充整身交換。
uv = X[..., [0, 2]] * (200, -200) + (900, 600)
assert label_pose(uv, uv).tolist() == [0]
assert label_pose(uv[:, SW], uv).tolist() == [1]
q = uv.copy(); q[:, [11, 12]] = q[:, [12, 11]]
assert label_pose(q, uv).tolist() == [-2]
q = uv[:, SW].copy(); q[:, [13, 14, 15, 16]] = uv[:, [13, 14, 15, 16]]
assert label_pose(q, uv).tolist() == [-2], "手臂正常時不能用軀幹對調標籤強翻整身"
assert label_pose(uv + 1000, uv).tolist() == [-1]
q = uv.copy(); q[:, 23] = np.nan
assert label_pose(q, uv).tolist() == [-1]

# 兩機都交換仍須由面向決定解剖左右；幾何重投影本身不能判定。
P1 = np.array([[100, 0, 0, 0], [0, 100, 0, 0], [0, 0, 1, 5.]])
P2 = np.array([[90, 20, 0, -100], [-20, 90, 0, 50], [.1, .2, 1, 5.]])
project = lambda P: (np.c_[X[0], np.ones(33)] @ P.T)
a, b = project(P1), project(P2)
a, b = (a[:, :2] / a[:, 2:])[None], (b[:, :2] / b[:, 2:])[None]
for sa, sb in ((False, False), (False, True), (True, False), (True, True)):
    out, err, paired, margin = triangulate(P1, P2, a[:, SW] if sa else a, b[:, SW] if sb else b)
    assert np.nanmax(err) < 1e-8
    assert orientation(out, err).tolist() == [int(sa)]
    assert paired.tolist() == [sa != sb]

# 同高度平行機位的對極線可讓錯配也零誤差；必須揭露配對差距為零。
Pr = np.array([[100, 0, 0, -100], [0, 100, 0, 0], [0, 0, 1, 5.]])
br = project(Pr); br = (br[:, :2] / br[:, 2:])[None]
_, err, _, margin = triangulate(P1, Pr, a, br)
assert np.nanmax(err) < 1e-8 and margin[0] < 1e-8

# 完整兩腿交換保留 metrics._knee 的值；不是假設單側膝不變。
q = np.repeat(X, 100, axis=0)
q[:, 25, 1] += .3
assert abs(_angle(q, 60, 23, 25, 27) - _angle(q, 60, 24, 26, 28)) > 5
assert _knee(q, FULL, 60) == _knee(q[:, SW], FULL, 60)
q[:, 13, 1] += .4
assert abs(_angle(q, 60, 12, 14, 16) - _angle(q[:, SW], 60, 12, 14, 16)) > 10

# 凍結的單機規則：至少連續 12 格、鼻與腳點可見；不足或局部翻轉不動。
P = np.ones((20, 33, 3))
world = np.repeat(X[..., [0, 2, 1]] * (1, -1, 1), 20, axis=0)
assert not candidate(P, world).any()
assert candidate(P, world[:, SW]).all()
assert not candidate(P[:11], world[:11, SW]).any()
low = P.copy(); low[:, 0, 2] = .49
assert not candidate(low, world[:, SW]).any()
partial = world.copy(); partial[:, [23, 24]] = partial[:, [24, 23]]
assert not candidate(P, partial).any()
print("多機位左右參考：合成失敗案例與交換不變量通過")

# 只用臨時目錄：建立父目錄、寫 owner 前失敗及 marker 清理失敗都不能漏掉釋鎖。
with TemporaryDirectory() as tmp:
    lock = Path(tmp) / "results" / "heavy.lock"
    for owner in (False, True):
        with heavy_lock(lock):
            assert lock.is_dir()
            if owner: (lock / "owner.txt").write_text("測試", encoding="utf-8")
        assert not lock.exists()
    try:
        with heavy_lock(lock):
            raise RuntimeError("寫入 owner 前失敗")
    except RuntimeError as e:
        assert str(e) == "寫入 owner 前失敗"
    else: raise AssertionError("原始錯誤遭遮蔽")
    assert not lock.exists()
    error = io.StringIO()
    with redirect_stderr(error), patch.object(Path, "unlink", side_effect=PermissionError("模擬刪除失敗")):
        with heavy_lock(lock): pass
    assert not lock.exists() and "模擬刪除失敗" in error.getvalue()
    with heavy_lock(lock):
        try:
            with heavy_lock(lock): raise AssertionError("不應取得別人的鎖")
        except FileExistsError: pass
        assert lock.is_dir()
    assert not lock.exists()
print("重運算鎖：缺父目錄、缺 owner、刪除例外與互斥保護通過")
