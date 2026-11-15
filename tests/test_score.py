# Run: .venv/bin/python tests/test_score.py   (plain asserts; numbers refer to the failure list in testset/results/score-trend_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import numpy as np
from score import lin, band, spread, score_session, check_session, SCORE_VERSION
from trend import compare


def close(a, b): return a is not None and abs(a - b) < 1e-6


# 1, 2: clipping and direction
assert lin(120, 125, 160) == 10 and lin(170, 125, 160) == 1
assert close(lin(142.5, 125, 160), 5.5)
assert lin(0.05, 0.08, 0.30) == 10 and lin(0.5, 0.08, 0.30) == 1
# 3: band
assert band(0.3, 0.3, 0.8, -0.2, 1.3) == 10 and band(0.8, 0.3, 0.8, -0.2, 1.3) == 10
assert close(band(0.05, 0.3, 0.8, -0.2, 1.3), 5.5) and close(band(1.05, 0.3, 0.8, -0.2, 1.3), 5.5)
assert band(2, 0.3, 0.8, -0.2, 1.3) == 1
# 4: None / NaN
assert lin(None, 125, 160) is None and lin(float("nan"), 125, 160) is None and band(None, 0.3, 0.8, -0.2, 1.3) is None
# 6: robust spread ignores one wild value
assert spread([130, 131, 132, 133, 134, 135, 79]) < 3


def st(kind="FH", knee=130, h=0.5, op=20, vis=0.9, **kw):
    return dict(kind=kind, knee=knee, contact_h=h, open_min=op, vis=vis, elbow=150, open_contact=60, **kw)


def grp(groups, kind="FH", player="me"):
    return next(g for g in groups if g["kind"] == kind and g["player"] == player)


# 5: too few strokes
g = grp(score_session([st(), st()], False))
assert g["total"] is None and g["metrics"]["knee"]["score"] is None
g = grp(score_session([st()] * 4, False))
assert g["metrics"]["knee"]["score"] is not None and g["consistency"] is None and g["total"] == g["form"]
# a perfect, perfectly consistent session scores 10
g = grp(score_session([st(knee=120, h=0.5)] * 6, False))
assert g["total"] == 10 and g["consistency"] == 10
# 7: quality gates
g = grp(score_session([st(vis=0.2)] * 6, False))
assert g["metrics"]["contact_h"]["score"] is None and g["metrics"]["contact_h"]["n"] == 0
g = grp(score_session([st(knee_warn=True)] * 6, False))
assert g["metrics"]["knee"]["score"] is None
assert "open_min" not in grp(score_session([st()] * 6, False))["metrics"]
assert grp(score_session([st()] * 6, True))["metrics"]["open_min"]["score"] is not None
# 8: knee3d preferred, falls back per stroke
g = grp(score_session([st(knee=160, knee3d=120)] * 6, False))
assert g["metrics"]["knee"]["median"] == 120 and g["knee_src"] == "knee3d"
g = grp(score_session([st(knee=130, knee3d=None)] * 6, False))
assert g["metrics"]["knee"]["median"] == 130 and g["knee_src"] == "knee"
# 9: players kept apart, default "me"; OH not scored; SV group exists only with SV strokes and carries only the serve metrics
G = score_session([st(knee=120)] * 5 + [st(player="A", knee=160)] * 5 + [st(kind="OH")] * 5, False)
assert {(g["player"], g["kind"]) for g in G} == {("me", "FH"), ("A", "FH")}
G = score_session([st(knee=120)] * 5 + [st(kind="SV", reach=1.2, tilt=15, lean=8, stance=1.5)] * 5, False)
assert {(g["player"], g["kind"]) for g in G} == {("me", "FH"), ("me", "SV")}
assert set(grp(G, kind="SV")["metrics"]) == {"reach", "tilt", "lean", "stance"} and "finish" in grp(G)["metrics"] and "reach" not in grp(G)["metrics"]
assert grp(G, kind="SV")["metrics"]["reach"]["status"] == "ok" and grp(G, kind="SV")["metrics"]["reach"]["score"] is None  # consistency only, no target
G = score_session([st(knee=120)] * 5 + [st(player="A", knee=160)] * 5, False)
assert grp(G)["metrics"]["knee"]["score"] == 10 and grp(G, player="A")["metrics"]["knee"]["score"] == 1

# one knee source per group: a 3D majority uses only 3D strokes, never a 2D/3D mix
g = grp(score_session([st(knee=160, knee3d=k) for k in (110, 115, 120, 125, 130)] + [st(knee=160)] * 4, False))
assert g["knee_src"] == "knee3d" and g["metrics"]["knee"]["median"] == 120 and g["metrics"]["knee"]["n"] == 5
# strokes dropped by knee_warn do not count toward the source vote
g = grp(score_session([st(knee3d=120, knee_warn=True)] * 4 + [st(knee=130)] * 5, False))
assert g["knee_src"] == "knee" and g["metrics"]["knee"]["median"] == 130

# trend.compare(history): history = [{"session", "camera", "items": {name: score|None}}] oldest first
def h(s, cam="c", n=20, **items): return dict(session=s, camera=cam, n=n, items=items)


# 11: one session -> no flags
assert compare([h("a", knee=9)]) == []
# strength regress / weakness improve
f = compare([h("a", knee=9, contact_h=4), h("b", knee=7.5, contact_h=6)])
assert ("knee", "優點退步") in [(x["item"], x["flag"]) for x in f]
assert ("contact_h", "缺點改善") in [(x["item"], x["flag"]) for x in f]
# baseline is the mean of up to 3 previous comparable sessions
f = compare([h("a", knee=2), h("b", knee=9), h("c", knee=9), h("d", knee=9), h("e", knee=7.9)])
assert [(x["item"], x["flag"], x["base"]) for x in f] == [("knee", "優點退步", 9.0)]
# 12: exactly 1.0 counts, 0.9 does not; None is skipped
assert compare([h("a", knee=8), h("b", knee=7)])[0]["flag"] == "優點退步"
assert compare([h("a", knee=8), h("b", knee=7.1)]) == []
assert compare([h("a", knee=None), h("b", knee=2)]) == [] and compare([h("a", knee=9), h("b", knee=None)]) == []
# 10: other cameras are not comparable
assert compare([h("a", "ground", knee=9), h("b", "tripod", knee=3)]) == []
assert compare([h("a", "x", knee=9), h("b", "y", knee=9), h("c", "x", knee=7)])[0]["base"] == 9
# unknown camera ("") is not a camera: never comparable, even to another unknown
assert compare([h("a", "", knee=9), h("b", "", knee=3)]) == []
# 15: groups under 10 strokes are too noisy to compare (same-day retest, testset/results/score-trend_pred.md)
assert compare([h("a", knee=9), h("b", n=5, knee=3)]) == []
assert compare([h("a", knee=9), h("b", knee=3), h("c", n=5, knee=3)]) == []  # small latest must not flag an older session
assert compare([h("a", n=5, knee=9), h("b", knee=3)]) == []
assert compare([h("a", n=5, knee=2), h("b", knee=9), h("c", knee=7)])[0]["base"] == 9
# metric set changed (showOpen flipped): total is not comparable, per-metric scores still are
assert compare([h("a", total=9, knee=9), h("b", total=7, knee=9, open_min=5)]) == []
assert compare([h("a", total=9, knee=9), h("b", total=7, knee=7)])[0]["item"] == "total"
# NaN / missing vis fails the gate; player null is "me"
nan = float("nan")
assert grp(score_session([st(vis=nan)] * 6, False))["metrics"]["contact_h"]["n"] == 0
assert grp(score_session([st(player=None)] * 3 + [st()] * 3, False))["n"] == 6
# knee from 3D in one session and 2D in another is not comparable (2D shifts with view angle)
assert compare([h("a", knee=9), dict(h("b", knee=3), knee_src="knee3d")]) == []
# coverage gate (docs/scoring.md §1): 3 usable of 10 strokes is not enough, 6 of 10 is; version and formula are output
g = grp(score_session([st(vis=0.2)] * 7 + [st()] * 3, False))
m = g["metrics"]["contact_h"]; assert m["score"] is None and m["status"] == "資料不足" and m["n"] == 3 and close(m["coverage"], 0.3)
g = grp(score_session([st(vis=0.2)] * 4 + [st()] * 6, False)); assert g["metrics"]["contact_h"]["score"] is not None
m = grp(score_session([st()] * 6, False))["metrics"]["knee"]
assert m["status"] == "ok" and "125" in m["formula"] and m["inputs"]["anchors"] == [125, 160] and g["score_version"] == SCORE_VERSION
assert grp(score_session([st(knee_warn=True)] * 6, False))["metrics"]["knee"]["status"] == "資料不足"
# arm shape checks (docs/scoring.md §9): pass/fail counts only, never mixed into the 1-10 score
def sv(v, **kw): return dict(kind="SV", serve_arm_straight=v, serve_arm_conf=0.6, **kw)
C = check_session([sv(True)] * 4 + [sv(False)] + [sv(None)] * 2)
c = [x for x in C if x["kind"] == "SV" and x["field"] == "serve_arm_straight"][0]
assert (c["n"], c["passed"], c["failed"], c["unclear"]) == (7, 4, 1, 2) and c["status"] == "ok" and abs(c["coverage"] - 5 / 7) < 0.01 and "135" in c["formula"], c
assert check_session([sv(None)] * 6)[0]["status"] == "資料不足"  # nothing decided
assert check_session([sv(True)] * 2)[0]["status"] == "資料不足"  # < 3 decided
assert check_session([st("FH"), st("BH")]) == []  # old strokes without the new fields, FH, two-handed BH: no checks at all
assert [g for g in score_session([sv(True), st()], False) if g["kind"] != "SV"] == score_session([st()], False)  # SV rows do not change FH/BH scores
print("ok")

# prep-contact（testset/results/prep-contact_pred.md）：準備時間越長越好；擊球前後位置只評一致性、不評好壞
from score import METRICS
assert lin(0.8, *METRICS["prep"]["lin"]) == 10 and lin(0.1, *METRICS["prep"]["lin"]) == 1 and close(lin(0.45, *METRICS["prep"]["lin"]), 5.5)
g = grp(score_session([st(knee=120, prep=0.7, contact_fwd=f) for f in (0.5, 0.5, 0.5, 0.5, 0.5, 0.9)], False))
cf = g["metrics"]["contact_fwd"]
assert cf["score"] is None and cf["cons"] == 10 and cf["status"] == "ok" and cf["inputs"]["anchors"] is None
assert g["metrics"]["prep"]["score"] == 10 and g["form"] == 10  # a consistency-only metric does not drag the form score
g = grp(score_session([st(contact_fwd=0.5, vis=0.2)] * 6, False))
assert g["metrics"]["contact_fwd"]["n"] == 0 and g["metrics"]["contact_fwd"]["status"] == "資料不足"
print("prep-contact score tests ok")

# body-kinematics（testset/results/body-kinematics_pred.md）：力量上限、2D 膝縮短閘門
W, LL = (METRICS[m]["lin"] for m in ("wrist_speed", "leg_load"))
strong = dict(wrist_speed=W[0], leg_load=LL[0])  # power 10
weak = dict(wrist_speed=W[1], leg_load=LL[1])     # power 1: arm-only, upright
g = grp(score_session([st(knee=120, **strong)] * 6, False))
assert g["power"] == 10 and g["total"] == 10 and g["form"] == 10 and not g["capped"]  # power metrics do not enter form
g = grp(score_session([st(knee=120, **weak)] * 6, False))
assert g["power"] == 1 and g["form"] == 10 and g["uncapped"] == 10 and close(g["total"], 1 + 1.2) and g["capped"]
assert g["metrics"]["wrist_speed"]["cons"] is None and g["consistency"] == 10  # no consistency score for power metrics
# no power data (old sessions) -> no cap, power null
g = grp(score_session([st(knee=120)] * 6, False)); assert g["power"] is None and g["total"] == 10 and not g["capped"]
# coverage gate applies to power metrics too: 2 of 6 strokes with wrist_speed -> 資料不足, not used for the cap
g = grp(score_session([st(knee=120, wrist_speed=W[1])] * 2 + [st(knee=120)] * 4, False))
assert g["metrics"]["wrist_speed"]["status"] == "資料不足" and g["power"] is None
# 2D knee gate: only when the group uses 2D; a foreshortened leg drops the stroke's 2D knee
g = grp(score_session([st(knee=120, knee2d_ok=False)] * 6, False)); assert g["metrics"]["knee"]["score"] is None
g = grp(score_session([st(knee=150, knee3d=120, knee2d_ok=False)] * 6, False)); assert g["metrics"]["knee"]["median"] == 120
print("body-kinematics score tests ok")
# arm check that applied but could not measure (conf 0.0) counts as "cannot tell", not as "not applicable"
from score import check_session
r = check_session([dict(kind="SV", serve_arm_straight=True, serve_arm_conf=0.9)] * 3 + [dict(kind="SV", serve_arm_straight=None, serve_arm_conf=0.0)])
assert r[0]["n"] == 4 and r[0]["unclear"] == 1, r
print("arm conf tests ok")

# score-groups-consistency（testset/results/score-groups-consistency_pred.md）
from statistics import NormalDist
from score import _cons_spread, spread
from trend import _entry
assert SCORE_VERSION >= 7
nd = [NormalDist().inv_cdf((i + 0.5) / 10) for i in range(10)]; nd = [x * 0.15 / spread(nd) for x in nd]  # 10 values, robust SD exactly 0.15
two = [st(video=1, contact_fwd=0.4 + x) for x in nd] + [st(video=2, contact_fwd=0.75 + x) for x in nd]
assert spread([s["contact_fwd"] for s in two]) > 0.2  # 0.244: medians 0.35 apart widen the pooled IQR (the brief guessed >= 0.3)
sp = _cons_spread(two, "contact_fwd", "knee"); assert abs(sp - 0.15) < 0.03, sp
g = grp(score_session(two, False)); assert abs(g["metrics"]["contact_fwd"]["spread"] - 0.15) < 0.03 and close(g["metrics"]["contact_fwd"]["median"], round(float(np.median([s["contact_fwd"] for s in two])), 2))
# drill centering uses the same key: two drills far apart behave like two videos; SV drill None = one drill
twod = [dict(s, video=1, drill="feed" if s["contact_fwd"] < 0.6 else "rally") for s in two]
assert abs(_cons_spread(twod, "contact_fwd", "knee") - 0.15) < 0.03
# a video with < 3 strokes is not dropped: n and coverage unchanged, it is centred on the whole-group median
three = two + [st(video=3, contact_fwd=0.6), st(video=3, contact_fwd=0.6)]
m = grp(score_session(three, False))["metrics"]["contact_fwd"]; assert m["n"] == 22 and m["coverage"] == 1.0
# 4: one video (or no video field) -> identical to the plain spread
one = [dict(s, video=1) for s in two]
assert _cons_spread(one, "contact_fwd", "knee") == spread([s["contact_fwd"] for s in one])
old = [{k: v for k, v in s.items() if k != "video"} for s in two]
nov = [dict(s, drill="feed" if s["contact_fwd"] < 0.6 else "rally") for s in old]  # drill but no video: whole group, as documented
assert _cons_spread(nov, "contact_fwd", "knee") == spread([s["contact_fwd"] for s in nov])
mixed = [dict(s, video=1 if i % 2 else "1") for i, s in enumerate(one)]  # 1 and "1" are the same video
assert _cons_spread(mixed, "contact_fwd", "knee") == _cons_spread(one, "contact_fwd", "knee")
tiny = [st(video=i // 3, contact_fwd=0.5 + nd[(i * 7) % 10]) for i in range(24)]  # 8 clips of 3 strokes: no self-centring, so no shrink
assert _cons_spread(tiny, "contact_fwd", "knee") >= spread([s["contact_fwd"] for s in tiny]) - 1e-9
assert _cons_spread(old, "contact_fwd", "knee") == spread([s["contact_fwd"] for s in old])
# 2: BH knee / open_min are consistency only; FH unchanged
for kind in ("BH", "FH"):
    g = grp(score_session([st(kind=kind, knee=130 + i % 3, op=20 + i % 3) for i in range(10)], True), kind=kind)
    k, o = g["metrics"]["knee"], g["metrics"]["open_min"]
    assert k["cons"] is not None and o["cons"] is not None
    if kind == "BH": assert k["score"] is None and o["score"] is None and "只評一致性" in k["formula"] and k["inputs"]["anchors"] is None
    else: assert k["score"] == round(lin(131, 125, 160), 1) and o["score"] is not None
# 3: turn no longer caps the total; power = mean(wrist_speed, leg_load); power_n stored
g = grp(score_session([st(knee=120, turn=0, **strong)] * 7, False))
assert "turn" not in g["metrics"] and g["power"] == 10 and not g["capped"] and g["power_n"] == 7
assert grp(score_session([st(knee=120)] * 6, False))["power_n"] == 0
assert grp(score_session([st(knee=120, **strong)] * 2 + [st(knee=120)] * 4, False))["power_n"] == 0  # gated out like power itself
# 5: Codex PR #3 — only-consistency metrics differ (stance spread vs stance None): total / consistency not comparable
A = grp(score_session([st(knee=130, stance=x) for x in (0.8, 1.0, 1.2, 1.4, 1.6, 0.9, 1.1, 1.3, 1.5, 1.7)], False))
B = grp(score_session([st(knee=130, stance=None)] * 10, False))
run = lambda name: dict(session=name, date="2026-11-0" + str(len(name)), camera="c")
assert compare([_entry(run("a"), A), _entry(run("b"), B)]) == []
# 6: comparable / series_key
e = _entry(run("a"), A); assert e["comparable"] and e["series_key"] == ["c", A["knee_src"], SCORE_VERSION]
assert not _entry(dict(run("a"), camera=""), A)["comparable"] and not _entry(dict(run("a"), date="wall-1"), A)["comparable"]
assert not _entry(run("a"), grp(score_session([st()] * 6, False)))["comparable"]
print("score-groups-consistency tests ok")

# --- prep-window-direction: a truncated prep is only a lower bound -> left out of the prep median / spread; SCORE_VERSION 8
from score import _value
assert SCORE_VERSION == 8
assert _value(dict(prep=1.5, prep_trunc=True), "prep") is None and _value(dict(prep=0.4, prep_trunc=False), "prep") == 0.4 and _value(dict(prep=0.4), "prep") == 0.4
G = score_session([dict(kind="FH", prep=0.4)] * 5 + [dict(kind="FH", prep=1.5, prep_trunc=True)], False)[0]["metrics"]["prep"]
assert G["n"] == 5 and G["median"] == 0.4, G
# old sessions have no prep_trunc: a prep at the old 1.0 s window edge is the cut value, not a measurement -> left out too
assert _value(dict(prep=1.0), "prep") is None and _value(dict(prep=0.999), "prep") is None and _value(dict(prep=0.98), "prep") == 0.98
assert _value(dict(prep=1.0, prep_trunc=False), "prep") == 1.0  # new sessions: a real 1.0 s
print("prep-trunc tests ok")
