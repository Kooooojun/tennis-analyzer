"""合成轉接檢查，不需影片與權重。"""
import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('lift_clip', Path(__file__).with_name('lift_clip.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = np.ones((5,33,3), np.float32)
p[...,0] = np.arange(33); p[...,1] = np.arange(33)*2
xy, valid = m.input17(p, (1920,1088))
assert xy.shape == (5,17,2) and valid.all()
np.testing.assert_allclose(xy[0,5], [11,22])
p[2,11] = np.nan
filled, mask = m.input17(p, (1920,1088))
assert not mask[2] and np.isfinite(filled).all()
np.testing.assert_allclose(filled[2],xy[2])
p[:,11] = np.nan
try: m.input17(p,(1920,1088))
except ValueError: pass
else: raise AssertionError('整關節缺失須拒絕')
x = np.arange(5*17*3,dtype=float).reshape(5,17,3)
w = m.output33(x)
np.testing.assert_array_equal(w[:,[23,24,25,26,27,28]],x[:,[4,1,5,2,6,3]])
np.testing.assert_array_equal(w[:,[11,12,13,14,15,16]],x[:,[11,14,12,15,13,16]])
assert np.isnan(w[:,0]).all()
chunks = list(m.chunks(x,2,1))
np.testing.assert_array_equal(np.concatenate([a[1:-1] for _,a in chunks]), x)
assert len(chunks)==3 and chunks[0][1].shape[0]==4
for bad in (np.zeros((5,17,3)),np.zeros((0,33,3))):
    try: m.input17(bad,(1920,1088))
    except ValueError: pass
    else: raise AssertionError('形狀須拒絕')
print('轉接合成自檢通過')
