# Run: .venv/bin/python tests/test_check_findings.py   (plain asserts; cases follow testset/results/findings-check_pred.md)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_findings import check
from score import score_session


def st(knee=130, h=0.5, **kw):
    return {**dict(kind="FH", knee=knee, knee3d=None, contact_h=h, open_min=20, vis=0.9, elbow=150, open_contact=60, drill="feed"), **kw}


S = [st(knee=120), st(knee=130, drill="rally"), st(knee=140), st(knee=150, knee_warn=True), st(knee=125, vis=0.2)]
G = score_session(S, False)
f = lambda cite, text="", **kw: dict(title="t", text=text, cite=cite, **{"info": True, **kw})  # info: these cases test cites, not the evidence rule
pf = lambda cite, **kw: dict(title="t", text="", cite=cite, **kw)  # problem finding
errs = lambda *fs: check(dict(findings=list(fs)), S, dict(groups=G))

assert errs(f([dict(stroke=1, field="knee", value=120)])) == []
assert errs(f([dict(stroke=2, field="knee", value=130.4)]))  # 1 decimal: 130 != 130.4
assert errs(f([dict(stroke=2, field="knee", value=130.0)])) == []
assert errs(f([dict(stroke=1, field="knee", value=121)]))                 # wrong value
assert errs(f([dict(stroke=99, field="knee", value=120)]))                # stroke does not exist
assert errs(f([dict(stroke=0, field="knee", value=120)]))                 # numbering starts at 1
assert errs(f([]))                                                        # no cite
assert errs(dict(title="t", text="x"))                                    # no cite key
assert errs(f([dict(stroke=4, field="knee", value=150)]))                 # knee_warn gate
assert errs(f([dict(stroke=5, field="contact_h", value=0.5)]))            # vis gate
assert errs(f([dict(stroke=1, field="nope", value=1)]))                   # unknown field
# group stats are recomputed from gated strokes: knee_warn stroke excluded -> median of 120,130,140,(125 ok) = 127.5
assert errs(f([dict(kind="FH", field="knee", stat="median", value=128)])) == []
assert errs(f([dict(kind="FH", field="knee", stat="median", value=150)]))
assert errs(f([dict(kind="FH", drill="rally", field="knee", stat="median", value=130)])) == []
assert errs(f([dict(kind="FH", drill="high", field="knee", stat="median", value=130)]))  # empty selection
assert errs(f([dict(kind="FH", field="knee", stat="n", value=4)])) == []
# score cites come from scores.json
sc = G[0]["metrics"]["knee"]["score"]
assert errs(f([dict(kind="FH", metric="knee", stat="score", value=sc)])) == []
assert errs(f([dict(kind="FH", metric="knee", stat="score", value=sc + 2)]))
assert errs(f([dict(kind="FH", metric="total", stat="score", value=G[0]["total"])])) == []
# a null score cannot be cited as a number
G2 = score_session(S[:2], False)
assert check(dict(findings=[f([dict(kind="FH", metric="knee", stat="score", value=5)])]), S[:2], dict(groups=G2))
# text numbers next to ° must be backed by a cite
assert errs(f([dict(stroke=1, field="knee", value=120)], "膝蓋 120°")) == []
assert errs(f([dict(stroke=1, field="knee", value=120)], "膝蓋 155°"))
# #NN in text or jump must exist
assert errs(f([dict(stroke=1, field="knee", value=120)], "看 #99"))
assert errs(f([dict(stroke=1, field="knee", value=120)], jump=[[99, "x"]]))
assert errs(f([dict(stroke=1, field="knee", value=120)], "看 #01", jump=[[1, "x"]])) == []
# which finding failed is named
e = errs(f([dict(stroke=1, field="knee", value=120)]), f([]))
assert len(e) == 1 and e[0].startswith("#2")
assert errs(f([dict(stroke=1, field="contact_h", value=0)]))  # integer cite cannot swallow a 0.5-scale value
assert errs(f(["not a dict"]))  # malformed cite is reported, not a crash
# three more gates (problem-inventory A5): elbow is never citable, knee with knee2d_ok False, open_min without showOpen
S2 = [st(knee=120, open_min=20), st(knee=130, knee2d_ok=False), st(knee=140, open_min=30)]
G2 = score_session(S2, False)
e2 = lambda show, *fs: check(dict(findings=list(fs)), S2, dict(groups=G2, show_open=show))
assert e2(False, f([dict(stroke=1, field="elbow", value=150)]))
assert e2(False, f([dict(stroke=2, field="knee", value=130)]))
assert e2(False, f([dict(stroke=2, field="knee3d", value=130)]))  # knee3d is None here anyway
assert e2(False, f([dict(stroke=1, field="knee", value=120)])) == []
# characterization (#128): knee3d shares knee_warn but not the 2D knee2d_ok gate; contact_fwd shares the vis gate
S8 = [st(knee3d=118, knee_warn=True), st(contact_fwd=0.1, vis=0.2), st(knee3d=118, knee2d_ok=False)]
e8 = lambda *fs: check(dict(findings=list(fs)), S8, dict(groups=score_session(S8, False)))
assert e8(f([dict(stroke=1, field="knee3d", value=118)]))
assert e8(f([dict(stroke=2, field="contact_fwd", value=0.1)]))
assert e8(f([dict(stroke=3, field="knee3d", value=118)])) == []
assert e2(False, f([dict(kind="FH", field="open_min", stat="median", value=20)]))
assert e2(True, f([dict(kind="FH", field="open_min", stat="median", value=20)])) == []
assert e2(False, f([dict(stroke=1, field="open_min", value=20)]))
assert e2(True, f([dict(stroke=1, field="open_min", value=20)])) == []
# prep_trunc (lower bound) is dropped like score.py: median of 0.3, 0.5 = 0.4, not 0.5 with the 1.5 lower bound
S3 = [st(prep=0.3), st(prep=0.5), st(prep=1.5, prep_trunc=True)]
e3 = lambda *fs: check(dict(findings=list(fs)), S3, dict(groups=score_session(S3, False)))
assert e3(f([dict(kind="FH", field="prep", stat="median", value=0.4)])) == []
assert e3(f([dict(kind="FH", field="prep", stat="median", value=0.5)]))
assert e3(f([dict(stroke=3, field="prep", value=1.5)]))
S4 = [st(prep=0.3), st(prep=0.5), st(prep=1.0, prep_trunc=None)]  # null = strokes.json refined before prep_trunc existed; 1.0 = the old window edge
assert check(dict(findings=[f([dict(stroke=3, field="prep", value=1.0)])]), S4, dict(groups=score_session(S4, False)))
# numbers in text other than degrees (docs/scoring.md §8): %, 秒 and bare decimals need a cite; ranges, 拍 counts and #NN do not
c1 = [dict(stroke=1, field="knee", value=120)]
assert errs(f(c1, "準備 0.53 秒"))
assert errs(f(c1, "只有 13%"))
assert errs(f(c1, "高度 0.30"))
S5 = [st(prep=0.43, contact_h=0.53)]
e5 = lambda *fs: check(dict(findings=list(fs)), S5, dict(groups=score_session(S5, False)))
assert e5(f([dict(stroke=1, field="prep", value=0.43)], "準備 0.43 秒")) == []
assert e5(f([dict(stroke=1, field="contact_h", value=0.53)], "擊球高度 53%")) == []
assert e5(f([dict(stroke=1, field="contact_h", value=0.53)], "高度 0.53（目標 0.3–0.8、1-10），共 62 拍、看 #01")) == []
assert errs(f(c1, "膝蓋 120.0°")) == []  # ° keeps its 0.5 tolerance
assert errs(f(c1, "膝蓋落在 154–156°"))  # a degree range is still checked
S6 = [st(contact_fwd=-0.2)]
assert check(dict(findings=[f([dict(stroke=1, field="contact_fwd", value=-0.2)], "擊球位置 -0.20")]), S6, dict(groups=score_session(S6, False))) == []  # sign kept
# hyphen between two numbers is a range, not a minus sign; ° ranges check both ends; times and thousands are not decimals
c2 = [dict(stroke=1, field="knee", value=120), dict(stroke=3, field="knee", value=140)]
assert errs(f(c2, "膝蓋 120°-140°")) == []
assert errs(f(c2, "膝蓋 120-140°")) == []
assert errs(f(c1, "膝蓋 120°-130°"))  # 130 has no cite
assert errs(f(c1, "膝蓋 110–120°"))   # lower end checked too
assert errs(f(c1, "目標 75%-85%")) == []
assert errs(f(c1, "在 1:04.8 那拍，共 1,234.5 次")) == []
# ASCII '-' with a space before it is a minus sign, not a range; ',' is a thousands separator only before 3 digits
S7 = [st(contact_fwd=-0.2, contact_h=0.5)]
e7 = lambda *fs: check(dict(findings=list(fs)), S7, dict(groups=score_session(S7, False)))
c7 = [dict(stroke=1, field="contact_h", value=0.5), dict(stroke=1, field="contact_fwd", value=-0.2)]
assert e7(f(c7, "高度 0.5 -0.20")) == []
assert e7(f(c7[:1], "高度 0.5 -0.20"))  # -0.20 needs its cite
assert errs(f(c1, "手速 7.6,9.0"))  # 9.0 is checked
# problem findings (not good/info) need a metric cite, a stat cite with usable n >= score.MIN_N, or 2+ different strokes (docs/scoring.md §8)
SE = [st(knee=120), st(knee=130), st(knee=140, knee_warn=True), st(knee=125, knee_warn=True)]  # usable knee: #1, #2
ee = lambda *fs: check(dict(findings=list(fs)), SE, dict(groups=score_session(SE, False)))
s1, s2 = dict(stroke=1, field="knee", value=120), dict(stroke=2, field="knee", value=130)
assert ee(pf([s1]))                                                          # one stroke only
assert ee(pf([s1, dict(stroke=1, field="contact_h", value=0.5)]))            # same stroke twice is one stroke
assert ee(pf([s1, s2])) == []                                                # two different strokes
assert ee(pf([s1], good=True)) == [] and ee(pf([s1], info=True)) == []       # good / info unchanged
assert ee(pf([dict(kind="FH", field="knee", stat="median", value=125)]))     # group stat, usable n = 2 (gated strokes do not count)
assert ee(pf([dict(kind="FH", field="knee", stat="n", value=2)]))
assert errs(pf([dict(kind="FH", metric="knee", stat="score", value=sc)])) == []  # metric cite (scores.json already applied MIN_N)
S10 = [st(knee=120), st(knee=130), st(knee=140)]                             # usable n = 3 passes
e10 = lambda *fs: check(dict(findings=list(fs)), S10, dict(groups=score_session(S10, False)))
assert e10(pf([dict(kind="FH", field="knee", stat="median", value=130)])) == []
assert "至少" in errs(pf([dict(kind="FH", metric="knee", stat="n", value=G[0]["metrics"]["knee"]["n"])]))[0]  # metric stat n has no MIN_N gate: not evidence
assert errs(pf([dict(stroke=1, field="knee", value=120, metric="knee")]))  # a stroke cite stays a single stroke even with a stray metric key
assert "至少" in ee(pf([s1]))[0]                                             # message says what is missing
print("ok")
