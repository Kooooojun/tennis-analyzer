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
f = lambda cite, text="", **kw: dict(title="t", text=text, cite=cite, **kw)
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
assert e2(False, f([dict(kind="FH", field="open_min", stat="median", value=20)]))
assert e2(True, f([dict(kind="FH", field="open_min", stat="median", value=20)])) == []
assert e2(False, f([dict(stroke=1, field="open_min", value=20)]))
assert e2(True, f([dict(stroke=1, field="open_min", value=20)])) == []
print("ok")
