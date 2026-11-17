"""公開評測轉接的合成自檢，不需影片、權重或第三方 repo。"""
import importlib.util
from pathlib import Path
import tempfile

import numpy as np


spec = importlib.util.spec_from_file_location("rtmo_coco", Path(__file__).with_name("rtmo_coco.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# 篩選後排序、縮放、bbox 分數須維持同一個人；全空不可產生原點假人。
det = np.array([[[1, 2, 3, 4, .2], [10, 20, 30, 40, .9]]], dtype=float)
pose = np.zeros((1, 2, 17, 3)); pose[0, 0] = (2, 4, .4); pose[0, 1] = (20, 40, .8)
original = det.copy(), pose.copy()
rows = module.records(7, [det, pose], .5, np.array([1, 0]))
assert [row['score'] for row in rows] == [.9, .2]
assert rows[0]['bbox'] == [20, 40, 40, 40]
assert rows[0]['keypoints'][:3] == [40, 80, .8]
assert rows[1]['keypoints'][:3] == [4, 8, .4]
assert all(np.array_equal(a, b) for a, b in zip(original, (det, pose)))
assert module.records(7, [det, pose], 1, None) == []
assert module.records(7, [det, pose], 1, np.array([], dtype=int)) == []

# 非法形狀、比例、非有限值不能靜默污染 COCO JSON。
for outputs, ratio in (([det, pose], 0), ([det, pose[:, :, :16]], 1),
                       ([det * np.nan, pose], 1)):
    try:
        module.records(7, outputs, ratio, np.array([0]))
    except ValueError:
        pass
    else:
        raise AssertionError('未拒絕非法模型輸出')

# 評測必須涵蓋完整 5,000 張；重複 ID、越出資料目錄、缺圖皆拒絕。
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory); (root / 'one.jpg').write_bytes(b'x')
    try:
        module.image_paths([dict(id=1, file_name='one.jpg')], root)
    except ValueError:
        pass
    else:
        raise AssertionError('部分資料集被當作完整評測')
    images = [dict(id=i, file_name='one.jpg') for i in range(5000)]
    assert len(module.image_paths(images, root)) == 5000
    for bad in ([dict(id=0, file_name='one.jpg')] * 5000,
                [dict(id=i, file_name='../outside.jpg') for i in range(5000)],
                [dict(id=i, file_name='missing.jpg') for i in range(5000)]):
        try:
            module.image_paths(bad, root)
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise AssertionError('未拒絕錯誤資料集')
print('合成自檢通過')
