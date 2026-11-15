# tools/crop.py 的裁切幾何與亮度（純函式）。用法（repo 根目錄）：.venv/bin/python tests/test_crop.py
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from crop import square, wide, cut, brighten

# 1 舊方塊裁切（標註圖 --legacy 與 players.jpg）：數字照 91aa98b 的 tile() 算
assert square(np.array([[270, 500]]), 540, 960) == (240, 150, 356)  # 直拍，單人
assert square(np.array([[950, 530]]), 960, 540) == (240, 720, 300)  # 橫拍，貼右下角：推回畫面內
assert square(np.array([[100, 300], [900, 300]]), 960, 540) == (960, 0, -180)  # 兩人相距遠：比畫面高，上下補黑
assert square(np.empty((0, 2)), 540, 960) == (240, 150, 456)  # 沒有姿態：畫面中下方

# 2 寬幅裁切：寬 4.5 倍軀幹、寬高比 1.5，從頭頂到膝蓋（擊球時拍與球多在腰到胸），能放進畫面就不越界
for W, H in ((1920, 1080), (1080, 1920)):
    x0, y0, w, h = wide(np.array([W / 2, H / 2]), 150, W, H)
    assert (w, h) == (675, 450) and 0 <= x0 and x0 + w <= W and 0 <= y0 and y0 + h <= H, (W, H, x0, y0)
    assert y0 < H / 2 - 150 and y0 + h > H / 2 + 225  # 上到頭頂（軀幹中心上 1 L 以上）、下到膝蓋（下 1.5 L）
    x0, y0, w, h = wide(np.array([5, H - 5]), 150, W, H)  # 貼左下角：推回畫面內
    assert x0 == 0 and y0 + h == H
x0, y0, w, h = wide(np.array([960, 540]), 500, 1920, 1080)  # 比畫面寬又高：置中、上下補黑，不切人
assert h > 1080 and y0 < 0 and x0 == 960 - w // 2

# 3 越界補黑：片頭片尾（沒有影格）回整張黑格；部分越界的部分是黑的，形狀照要求
im = np.full((100, 200, 3), 50, np.uint8)
t = cut(im, -20, -10, 60, 40); assert t.shape == (40, 60, 3) and t[:10].max() == 0 and t[:, :20].max() == 0 and t[20, 30].max() == 50
assert cut(None, 0, 0, 60, 40).shape == (40, 60, 3)
assert cut(im, 500, 500, 30, 20).max() == 0

# 4 6 px 亮點（球）：裁切加亮度提升後仍可辨，不被洗白；暗背景變亮
im = np.full((1080, 1920, 3), 70, np.uint8); yy, xx = np.mgrid[:1080, :1920]
ball = (yy - 500) ** 2 + (xx - 1000) ** 2 <= 9; im[ball] = (90, 230, 200)  # 6 px 寬的黃綠球
x0, y0, w, h = wide(np.array([960, 600]), 150, 1920, 1080)
t = brighten(cut(im, x0, y0, w, h)); b = t[500 - y0, 1000 - x0].astype(int); g = t[5, 5].astype(int)
assert g.mean() > 70 and np.abs(b - g).max() > 60, (b, g)
assert (np.abs(t.astype(int) - g).max(axis=2) > 60).sum() >= 20  # 球仍有約 28 個像素（6 px 圓）
print("crop tests ok")
