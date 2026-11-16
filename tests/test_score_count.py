# #105：技術指標採計資訊不改分數；比較集合沿用 trend 的現有規則。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from score import score_group, SCORE_VERSION
from trend import _entry, compare


def group(kind="FH", **values):
    return score_group([dict(kind=kind, knee=125, prep=0.7, contact_h=0.5, vis=0.9, **values)] * 10, False, kind)


g = group(wrist_speed=4, leg_load=0.02)
assert g["form_metrics"] == ["knee", "prep"] and g["form_n"] == 2
assert (g["form"], g["consistency"], g["power"], g["uncapped"], g["total"]) == (10, 10, 1, 10, 2.2)
assert g["score_version"] == SCORE_VERSION == 10
bh = group("BH")
assert bh["form_metrics"] == ["prep"] and bh["form_n"] == 1 and bh["total"] == 10
gate = group(knee_warn=True)
assert gate["form_metrics"] == ["prep"] and gate["form_n"] == 1
opened = score_group([dict(kind="FH", knee=125, prep=0.7, open_min=15)] * 10, True)
assert opened["form_metrics"] == ["knee", "prep", "open_min"] and opened["form_n"] == 3
for kind in ("FH", "BH", "SV"):
    empty = score_group([dict(kind=kind)] * 2, False, kind)
    assert empty["form_metrics"] == [] and empty["form_n"] == 0 and empty["total"] is None

run = dict(session="synthetic", date="2026-01-01", camera="側面")
row = _entry(run, g)
assert row["form_metrics"] == g["form_metrics"] and row["form_n"] == 2
assert row["score_set"] == [["consistency", "knee", "leg_load", "prep", "total", "wrist_speed"], ["contact_h", "knee", "prep"]]
assert _entry(run, bh)["score_set"] != row["score_set"]
# 舊資料未知，不從 metrics 猜成單項，也不產生比較集合的新標記。
old = {k: v for k, v in g.items() if k not in ("form_metrics", "form_n")}
legacy = _entry(run, old)
assert legacy.get("form_metrics") is None and legacy.get("form_n") is None and legacy.get("score_set") is None
# 既有比較閘門仍同時涵蓋絕對分項、力量項與一致性分項。
for changed in (group("BH"), group(), group(stance=1.0)):
    flags = compare([row, _entry(dict(run, date="2026-01-02"), changed)])
    assert not any(f["item"] in ("total", "consistency") for f in flags)
print("技術指標採計測試通過")
