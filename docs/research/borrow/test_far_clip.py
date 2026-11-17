"""17 點格式轉接與公開重現關卡的合成自檢。"""
import importlib.util
from pathlib import Path

import numpy as np


spec = importlib.util.spec_from_file_location('far_clip', Path(__file__).with_name('far_clip.py'))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
points = np.arange(51, dtype=float).reshape(17, 3)
row = dict(keypoints=points.reshape(-1).tolist(), score=.9)
pose = module.pose33([row], 2, 1920, 1080)
assert pose.shape == (2, 33, 3)
assert np.allclose(pose[0, module.COCO], points / (1920, 1080, 1))
assert np.isnan(pose[1]).all()
assert np.isnan(module.pose33([], 2, 1920, 1080)).all()
second = dict(keypoints=(points + 1).reshape(-1).tolist(), score=.8)
assert np.array_equal(module.pose33([row, second], 1, 1920, 1080), pose[:1], equal_nan=True)
for summary in ({'reproduced': False}, {}, {'reproduced': 1}):
    try:
        module.require_reproduced(summary)
    except ValueError:
        pass
    else:
        raise AssertionError('未重現公開數字卻進入開發資料')
module.require_reproduced({'reproduced': True})
print('合成自檢通過')
