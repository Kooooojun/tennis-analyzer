# Run: .venv/bin/python tests/test_score.py   (plain asserts; numbers refer to the failure list in testset/results/score-trend_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
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
# 9: players kept apart, default "me"; SV/OH not scored
G = score_session([st(knee=120)] * 5 + [st(player="A", knee=160)] * 5 + [st(kind="SV")] * 5, False)
assert {(g["player"], g["kind"]) for g in G} == {("me", "FH"), ("A", "FH")}
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
assert score_session([sv(True), st()], False) == score_session([st()], False)  # SV rows do not change FH/BH scores
print("ok")
