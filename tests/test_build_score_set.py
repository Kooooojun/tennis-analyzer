"""真跑建站：每組採計集合來自 scores，未知的舊組明列 null。"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from score import score_group

groups = []
for kind, fields in [("FH", dict(knee=125, prep=.7, contact_h=.5, vis=.9, wrist_speed=4, leg_load=.02)), ("BH", dict(prep=.7)), ("SV", {})]:
    g = score_group([dict(kind=kind, **fields)] * 10, False, kind)
    groups.append(dict(g, player="me", kind=kind))
legacy = copy.deepcopy(groups[0]); legacy["player"] = "legacy"
for key in ("form_metrics", "form_n"): del legacy[key]
groups.append(legacy)
scores = dict(session="synthetic", groups=groups)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    shutil.copytree(ROOT / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    day = root / "web" / "sessions" / "synthetic"; day.mkdir(parents=True)
    (day / "strokes.json").write_text(json.dumps([dict(id=0, video=1, src="clips/0.mp4", frames=[])]), encoding="utf-8")
    (day / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    trend = day.parent / "trend.json"; trend.write_text("[]\n", encoding="utf-8")
    before = [(p, p.read_bytes()) for p in (day / "scores.json", trend)]
    subprocess.run([sys.executable, str(root / "tools" / "build_site.py")], check=True, capture_output=True)
    js = (day / "data.js").read_text(encoding="utf-8")
    emitted = json.loads(js[js.index("push(") + 5:-2])["scores"]
    assert len(emitted["groups"]) == 4
    for original, actual in zip(groups, emitted["groups"]):
        assert "score_set" in actual, "每組（含舊組）都要有 score_set"
        expected = None if "form_metrics" not in original else [
            sorted([k for k in ("total", "consistency") if original[k] is not None] +
                   [k for k, m in original["metrics"].items() if m["score"] is not None]),
            sorted(k for k, m in original["metrics"].items() if m["cons"] is not None)]
        assert actual.pop("score_set") == expected
        assert actual == original, "建站不能改 scores 的既有欄位"
    assert emitted == scores
    for p, data in before: assert p.read_bytes() == data, "來源 JSON 不可被改寫"
print("建站四組 score_set 與來源 JSON 不變：通過")
