"""缺估計只補診斷列印；真跑 CLI 的既有 JSON 輸出不變。"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from score import SCORE_VERSION
from trend import _entry, compare

u = dict(ci=[6, 8], sem=.3)
base = dict(player="me", kind="FH", n=20, total=7, consistency=7, knee_src="knee", score_version=SCORE_VERSION,
            form_metrics=["knee"], form_n=1, uncertainty=dict(total=u, consistency=u),
            metrics={"knee": dict(score=7, cons=7, uncertainty=dict(score=u, cons=u)),
                     "prep": dict(score=None, cons=None)})
runs = []
for i, state in enumerate(("complete", "missing", "null", "partial", "unscored"), 1):
    g = copy.deepcopy(base)
    if state == "missing":
        del g["uncertainty"]; del g["metrics"]["knee"]["uncertainty"]
    elif state == "null":
        g["uncertainty"] = None; g["metrics"]["knee"]["uncertainty"] = None
    elif state == "partial": del g["metrics"]["knee"]["uncertainty"]
    elif state == "unscored":
        g.update(total=None, consistency=None, uncertainty=None)
        g["metrics"]["knee"].update(score=None, cons=None, uncertainty=None)
    runs.append(dict(session=state, date=f"2026-01-0{i}", camera="側面", score_version=SCORE_VERSION, groups=[g]))
history = [_entry(r, r["groups"][0]) for r in runs]
expected = [dict(player="me", kind="FH", history=history, flags=compare(history))]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    shutil.copytree(ROOT / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    sources = []
    for r in runs:
        day = root / "web" / "sessions" / r["session"]; day.mkdir(parents=True)
        p = day / "scores.json"; p.write_text(json.dumps(r), encoding="utf-8"); sources.append((p, p.read_bytes()))
    result = subprocess.run([sys.executable, str(root / "tools" / "trend.py")], capture_output=True, check=True, encoding="utf-8")
    assert json.loads((day.parent / "trend.json").read_text(encoding="utf-8")) == expected
    for p, data in sources: assert p.read_bytes() == data
    warnings = [line for line in result.stdout.splitlines() if "區間不足" in line]
    assert len(warnings) == 3, f"缺估計的三組都要列出，實際：{warnings}"
    for state in ("missing", "null", "partial"):
        line = next((line for line in warnings if state in line), "")
        assert "me" in line and "FH" in line and "膝蓋" in line and "不做比較" in line, line
    assert all("complete" not in line and "unscored" not in line and "準備時間" not in line for line in warnings)
print("trend 缺估計三組診斷、JSON 既有欄位不變：通過")
