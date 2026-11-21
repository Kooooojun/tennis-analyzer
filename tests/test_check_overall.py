# Run: .venv/bin/python tests/test_check_overall.py   (plain asserts; cases follow testset/results/overall-contract/pred.md)
# notes.json `overall` (docs/advice.md) and the `look` rule for prep findings, checked by tools/check_findings.py. Synthetic data only.
import copy
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_findings import check
from score import score_session


def st(i, player="me", drill="feed", cf=0.8, k3=135, **kw):
    return {**dict(id=i, kind="FH", player=player, drill=drill, knee=130, knee3d=k3, contact_h=0.5, contact_fwd=cf, prep=0.4,
                   open_min=20, vis=0.9, elbow=150, open_contact=60), **kw}


# #1-#12 me feed (contact_fwd 0.8, knee3d 135); #13-#22 me rally (contact_fwd 1.0, knee3d 125, #22 knee_warn -> 9 usable knee3d); #23-#26 white rally
S = [st(i) for i in range(1, 13)] + [st(i, drill="rally", cf=1.0, k3=125, prep=0.5) for i in range(13, 23)] + [st(i, player="white", drill="rally") for i in range(23, 27)]
S[21]["knee_warn"] = True
G = score_session(S, False)
SC = dict(groups=G)
run = lambda notes: check(notes, S, SC)
cg = lambda **kw: {"kind": "FH", **kw}
CF = [cg(drill="feed", field="contact_fwd", stat="median", value=0.8), cg(drill="rally", field="contact_fwd", stat="median", value=1.0)]
MAIN = dict(title="自拋時把球打在身前", why="擊球點自拋 0.80、對打 1.00。", cite=CF, practice="自拋時把球丟在身體側前方，在前腳前方打。",
            cue="打在前腳前", jump=[[13, "對打 #13"], [2, "自拋 #02"]])
SECOND = dict(title="看圖觀察：收拍收到對側肩", why="#02、#05、#13 收拍收到對側肩上方。", cite=[cg(field="id", stat="n", value=22)], practice="每拍停住收拍姿勢一秒再回位。")
INS = dict(title="white：資料不足以給方向", why="white 只有 4 拍。", cite=[cg(player="white", field="id", stat="n", value=4)])
ME = dict(player="me", main=MAIN, look=[2, 5, 13])
WHITE = dict(player="white", insufficient=INS, look=[23, 24, 25], film_next="手機放在側面約 90°，連續正拍 30 拍以上。")  # 90° is filming advice, not a cite


def with_(entry=ME, **kw):
    e = copy.deepcopy(entry)
    for k, v in kw.items():
        if v is None: e.pop(k, None)
        else: e[k] = v
    return e


def main_with(**kw): return with_(main=with_(MAIN, **kw))


ok = lambda *entries: run(dict(overall=list(entries))) == []
bad = lambda *entries: run(dict(overall=list(entries))) != []

# 11. old notes (no overall, findings without look) are unchanged
assert run({}) == []
assert run(dict(findings=[dict(info=True, title="t", text="", cite=[cg(field="id", stat="n", value=22)])])) == []

assert ok(ME, WHITE)                                                # 12. "90°" in film_next is not checked as a cite
assert ok(with_(second=SECOND), WHITE)
assert ok(with_(WHITE, second=SECOND | dict(cite=[cg(player="white", field="id", stat="n", value=4)], why="看圖觀察：#23、#24、#25 收拍收到對側肩上方。")))

# 1. malformed overall: an error string, never an exception (build_site checks every session)
for o in ("x", {"player": "me"}, ["x"], [dict(ME, player=None)], [dict(ME, player=3)], [dict(ME, player="nobody")], [dict(ME, main="x")], [dict(ME, look="2,5,13")]):
    e = run(dict(overall=o)); assert isinstance(e, list) and e, o
assert bad(with_(player=None))
# 2. one entry per player
assert bad(ME, with_(main=None, insufficient=INS, film_next="側面拍。"))
# 3. one main, one second
assert bad(with_(main=[MAIN, MAIN]))
assert bad(with_(second=[SECOND, SECOND]))
# 4. main xor insufficient
assert bad(with_(insufficient=INS, film_next="側面拍。"))
assert bad(with_(main=None))
# 5. insufficient needs film_next
assert bad(with_(WHITE, film_next=None))
assert bad(with_(WHITE, film_next=""))
assert bad(with_(WHITE, film_next="   "))
# 6. look: >= 3 distinct strokes that exist and belong to the player
assert bad(with_(look=None))
assert bad(with_(look=[2, 5]))
assert bad(with_(look=[2, 5, 99]))
assert bad(with_(look=[0, 2, 5]))
assert bad(with_(look=[2, 2, 5]))
assert bad(with_(look=[True, 2, 5]))
assert bad(with_(look=[2, 5, 23]))                                  # #23 is white's
assert bad(with_(WHITE, look=[23, 24]))
assert ok(with_(look=[2, 5, 13, 16]))
# 7. numbers in main / second / insufficient text need cites, as in findings
assert bad(main_with(why="擊球點自拋 0.80、對打 0.95。"))
assert bad(main_with(practice="先蹲到 120° 再出手。"))
assert ok(main_with(practice="先蹲到 125° 再出手。", cite=CF + [cg(drill="rally", field="knee3d", stat="median", value=125)]))
assert bad(main_with(cue="手腕 0.5 秒前就側身"))
assert bad(main_with(title="擊球點差 0.20"))
assert bad(with_(WHITE, insufficient=INS | dict(why="white 擊球點 0.80。")))
assert bad(with_(second=SECOND | dict(why="#02 膝蓋 140°。")))
assert bad(main_with(cite=[cg(drill="feed", field="contact_fwd", stat="median", value=0.9), CF[1]]))  # cite does not match the data
assert bad(main_with(jump=[[99, "x"]]))
assert bad(main_with(why="看 #99。"))
# 8. main evidence: a comparison of two groups with >= 10 usable strokes each, or a metric cite
K3 = [cg(drill="feed", field="knee3d", stat="median", value=135), cg(drill="rally", field="knee3d", stat="median", value=125)]
assert bad(main_with(why="膝蓋自拋 135°、對打 125°。", cite=K3))     # rally knee3d: 9 usable
assert ok(main_with(why="膝蓋自拋 135°、對打 125°；擊球點自拋 0.80、對打 1.00。", cite=K3 + CF))
assert bad(main_with(why="擊球點自拋 0.80。", cite=CF[:1]))           # one group is not a comparison
assert bad(main_with(why="擊球點 0.80。", cite=[CF[0], CF[0]]))       # same group twice
ks = G[0]["metrics"]["knee"]["score"] if G[0]["player"] == "me" else next(g for g in G if g["player"] == "me")["metrics"]["knee"]["score"]
assert ok(main_with(why="膝蓋分數偏低。", cite=[cg(metric="knee", stat="score", value=ks)]))
assert bad(main_with(why="膝蓋分數偏低。", cite=[cg(metric="knee", stat="n", value=21)]))  # a count is not a metric cite
assert bad(main_with(cite=[]))
# 9. main and second need practice; main needs jump; second stays optional
assert bad(main_with(practice=None))
assert bad(main_with(practice=""))
assert bad(main_with(jump=None))
assert bad(main_with(title=None))
assert bad(main_with(why="  "))
assert bad(main_with(jump=13)) and bad(main_with(jump="13"))       # wrong shape: an error, not a crash
assert bad(main_with(jump=[13, "a"])) and bad(main_with(jump=[[True, "a"]])) and bad(main_with(jump=[[13]]))  # each item is [stroke, label]
assert bad(main_with(cite=[cg(metric=["knee"], value=1)]))          # unhashable metric: an error, not a TypeError
assert bad(with_(second=SECOND | dict(practice="")))
assert bad(with_(second={k: v for k, v in SECOND.items() if k != "practice"}))

# 10. a problem finding that cites prep needs look (3+ existing strokes); info / good do not
P = [cg(drill="feed", field="prep", stat="median", value=0.4)]
pf = lambda cite, **kw: run(dict(findings=[dict(title="t", text="", cite=cite, **kw)]))
assert pf(P)
assert pf(P, look=[1, 2, 3]) == []
assert pf(P, look=[1, 2])
assert pf(P, look=[1, 2, 99])
assert pf(P, info=True) == [] and pf(P, good=True) == []
assert pf([cg(metric="prep", stat="score", value=next(g for g in G if g["player"] == "me")["metrics"]["prep"]["score"])])
assert pf(CF) == []                                                 # no prep: look not required
assert pf(CF, look=[1, 99, 2])                                      # but a look given must still be valid

# SKILL.md's overall example passes on synthetic strokes shaped like it
md = (Path(__file__).resolve().parent.parent / ".claude/skills/tennis-analyze/SKILL.md").read_text(encoding="utf-8")
ex = json.loads(re.search(r"Add `overall` to `notes.json`:\s*```json\n(.*?)\n```", md, re.S).group(1))
e = run(ex); assert e == [], e
nolook = copy.deepcopy(ex); nolook["overall"][0].pop("look"); assert run(nolook)
nofilm = copy.deepcopy(ex); nofilm["overall"][1].pop("film_next"); assert run(nofilm)
print("ok")
