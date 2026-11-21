# Run: .venv/bin/python tests/test_drill_diff.py   (plain asserts; 編號對應 testset/results/drill-diff/pred.md 的失敗方式；合成資料，不讀私人資料)
import copy
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import numpy as np
import score
from score import score_session, drill_diff, MIN_N_DRILL

assert MIN_N_DRILL == 10


def stroke(i, drill, fwd, video=0, **kw):
    return dict(kind="FH", player="p", drill=drill, video=video, vis=0.9, contact_fwd=fwd, contact_h=0.4 + i % 3 * 0.01, prep=0.4 + i % 4 * 0.01,
                knee=130 + i % 5, knee3d=125 + i % 5, **kw)


# 已知分布：自拋 0.70–0.81（中位 0.755），對打 0.95–1.06（中位 1.005）；兩支影片各一半
feed = [stroke(i, "feed", 0.70 + i * 0.01, video=i % 2) for i in range(12)]
rally = [stroke(i, "rally", 0.95 + i * 0.01, video=i % 2) for i in range(12)]
S = feed + rally
g = drill_diff(S, "FH")
m = g["metrics"]["contact_fwd"]
# 8: 方向 = 自拋 − 對打；11: 未四捨五入的中位數相減
assert math.isclose(np.median([s["contact_fwd"] for s in feed]) - np.median([s["contact_fwd"] for s in rally]), -0.25)
assert m["diff"] == -0.25 and m["feed"] == dict(median=0.76, n=12) and m["rally"] == dict(median=1.0, n=12), m  # 中位數各自四捨五入到 2 位
assert g["direction"].startswith("自拋 − 對打") and m["unit"] == "肩髖長" and g["metrics"]["prep"]["unit"] == "秒" and g["metrics"]["knee"]["unit"] == "度"
assert m["reason"] is None and m["ci"][0] < m["diff"] < m["ci"][1] and m["ci"][1] < 0, m  # 分得很開：區間不含 0
assert m["valid"] == m["samples"] == score.BOOTSTRAP_N and m["sem"] > 0
# 5: 每支影片內重抽，亂數順序 = 每次先自拋後對打，各影片依首次出現順序；種子同既有 bootstrap
rng = np.random.default_rng(score.BOOTSTRAP_SEED)
by = lambda rows: [[s for s in rows if s["video"] == v] for v in (0, 1)]
fv, rv = by(feed), by(rally)
draws = []
for _ in range(score.BOOTSTRAP_N):
    f = [c[i] for c in fv for i in rng.integers(0, len(c), len(c))]
    r = [c[i] for c in rv for i in rng.integers(0, len(c), len(c))]
    draws.append(np.median([s["contact_fwd"] for s in f]) - np.median([s["contact_fwd"] for s in r]))
assert m["ci"] == [round(float(x), 3) for x in np.percentile(draws, [2.5, 97.5])] and m["sem"] == round(float(np.std(draws, ddof=1)), 3)
# 4: 固定種子，重跑一樣；輸入順序不同的無關組不影響
assert drill_diff(S, "FH") == g and drill_diff(copy.deepcopy(S), "FH") == g
# 兩組同分布：區間含 0
same = [stroke(i, "feed", 0.8 + i % 6 * 0.02, video=i % 2) for i in range(14)] + [stroke(i, "rally", 0.8 + i % 6 * 0.02, video=i % 2) for i in range(14)]
z = drill_diff(same, "FH")["metrics"]["contact_fwd"]
assert z["diff"] == 0 and z["ci"][0] < 0 < z["ci"][1]
# 3: ≥ 10 拍是過閘門後的拍數：12 拍裡 3 拍手腕可見度 < 0.5 → 只剩 9 → null 並說原因；其他不受影響的指標照給
gated = [dict(s, vis=0.3) if i in (0, 1, 2) and s["drill"] == "feed" else s for i, s in enumerate(S)]
n = drill_diff(gated, "FH")["metrics"]
assert n["contact_fwd"]["diff"] is None and n["contact_fwd"]["ci"] is None and "自拋" in n["contact_fwd"]["reason"] and "9" in n["contact_fwd"]["reason"], n["contact_fwd"]
assert n["contact_fwd"]["feed"]["n"] == 9 and n["contact_fwd"]["rally"]["n"] == 12
assert n["prep"]["diff"] is not None and n["prep"]["reason"] is None
# 剛好 10 拍算
ten = drill_diff([s for s in S if not (s["drill"] == "feed" and s["contact_fwd"] > 0.795)], "FH")["metrics"]["contact_fwd"]
assert ten["feed"]["n"] == 10 and ten["diff"] is not None
# 9: 少一邊、unsure／high 不算、SV 沒有練習類型
only_rally = drill_diff(rally + [stroke(0, "high", 0.2)] * 20 + [stroke(0, "unsure", 0.2)] * 20, "FH")["metrics"]["contact_fwd"]
assert only_rally["diff"] is None and "自拋" in only_rally["reason"] and "0" in only_rally["reason"] and only_rally["feed"]["n"] == 0
both_small = drill_diff(feed[:4] + rally[:5], "FH")["metrics"]["contact_fwd"]
assert both_small["diff"] is None and "自拋" in both_small["reason"] and "對打" in both_small["reason"]
sv = drill_diff([dict(s, kind="SV", drill=None) for s in S], "SV")
assert sv["metrics"] is None and "發球" in sv["reason"]
# 2: 膝角來源看整個拍種組，不是各練習類型各選各的（組內多數有 knee3d → 全用 knee3d；對打拍沒有 3D 就不算，不退回 2D）
mixed = [dict(s, knee3d=None) if s["drill"] == "rally" and i % 12 < 6 else s for i, s in enumerate(S)]
kn = drill_diff(mixed, "FH")["metrics"]["knee"]
assert kn["feed"]["median"] == round(float(np.median([s["knee3d"] for s in feed])), 2) and kn["rally"]["n"] == 6 and kn["diff"] is None
# 1: 品質閘門同分數：knee_warn、prep_trunc 的拍不算
warn = drill_diff([dict(s, knee_warn=True) if s["drill"] == "feed" and i < 4 else dict(s, prep_trunc=True) if s["drill"] == "rally" and i % 12 < 5 else s for i, s in enumerate(S)], "FH")["metrics"]
assert warn["knee"]["feed"]["n"] == 8 and warn["knee"]["diff"] is None and warn["prep"]["rally"]["n"] == 7 and warn["prep"]["diff"] is None
# 6: 重抽時某一邊整組被閘門擋光（真資料幾乎不會發生，所以暫時把門檻降到 1 拍來造）：3 拍只有 1 拍可用 → 約 30% 的重抽是空的；有差值，但不給區間，原因寫出來
score.MIN_N_DRILL = 1
thin = [dict(stroke(i, "feed", 0.7 + i * 0.01), vis=0.9 if i == 0 else 0.3) for i in range(3)] + rally
t = drill_diff(thin, "FH")["metrics"]["contact_fwd"]
score.MIN_N_DRILL = 10
assert t["feed"]["n"] == 1 and t["diff"] is not None and t["ci"] is None and t["sem"] is None and 0 < t["valid"] < t["samples"] and "重抽" in t["reason"], t
# 7、10: 不動既有分數；score_session 只在要區間時多一欄 drill_diff，其他欄位逐位相同
plain = score_session(S, False)
full = score_session(S, False, True)
assert "drill_diff" not in plain[0]
assert full[0]["drill_diff"] == drill_diff([s for s in S if s["player"] == "p" and s["kind"] == "FH"], "FH")
strip = lambda gs: [{k: v for k, v in x.items() if k not in ("drill_diff", "uncertainty", "metrics")} for x in gs]
assert strip(full) == strip(plain)
for a, b in zip(full[0]["metrics"].values(), plain[0]["metrics"].values()):
    assert {k: v for k, v in a.items() if k != "uncertainty"} == b
assert full[0]["score_version"] == score.SCORE_VERSION == 10
# 有 SV 的場次：SV 組也有 drill_diff（null 並說原因）
ses = score_session(S + [dict(s, kind="SV", drill=None) for s in S[:6]], False, True)
assert next(x for x in ses if x["kind"] == "SV")["drill_diff"]["metrics"] is None
print("drill_diff OK")
