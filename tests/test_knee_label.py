# Run: .venv/bin/python tests/test_knee_label.py   (written before the change; failure list in testset/results/knee-display-labels_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from annotate import stroke_info

base = dict(no=1, kind="FH", drill="rally", prep=None, contact_h=None)
_, l3 = stroke_info({**base, "knee": 150.0, "knee3d": 128.0})
assert l3[0][0] == "準備時膝蓋 3D 128°", l3
_, l2 = stroke_info({**base, "knee": 150.0, "knee3d": None})
assert l2[0][0] == "準備時膝蓋 2D 150°", l2
_, l0 = stroke_info({**base, "knee": None, "knee3d": None})
assert not any("膝" in t for t, _ in l0), l0
print("ok")
