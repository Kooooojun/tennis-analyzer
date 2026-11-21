# Run: .venv/bin/python tests/test_check_drill_diff.py   (plain asserts; 編號對應 testset/results/drill-cite/pred.md 的失敗方式；合成資料，不讀私人資料)
# check_findings.py 的 cite 引用 scores.json 的 drill_diff（docs/scoring.md §8）。
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_findings import check
from score import score_session


def st(i, player, drill, fwd, video=0, **kw):
    return dict(id=i, kind="FH", player=player, drill=drill, video=video, vis=0.9, contact_fwd=fwd, contact_h=0.4 + i % 3 * 0.01,
                prep=0.4 + i % 4 * 0.01, knee=130 + i % 5, knee3d=125 + i % 5, open_min=20, elbow=150, open_contact=60, **kw)


# me：自拋 0.70–0.81、對打 0.95–1.06（差 -0.25，區間不含 0）；wide：兩邊分布幾乎一樣（區間含 0）；few：對打只有 5 拍（diff 是 null）；sv：發球
S = ([st(i, "me", "feed", 0.70 + i * 0.01, video=i % 2) for i in range(12)] + [st(i, "me", "rally", 0.95 + i * 0.01, video=i % 2) for i in range(12)]
     + [st(i, "wide", "feed", 0.80 + i % 6 * 0.02, video=i % 2) for i in range(14)] + [st(i, "wide", "rally", 0.82 + i % 6 * 0.02, video=i % 2) for i in range(14)]
     + [st(i, "few", "feed", 0.8 + i * 0.01) for i in range(12)] + [st(i, "few", "rally", 1.0 + i * 0.01) for i in range(5)]
     + [dict(st(i, "me", None, 0.9), kind="SV") for i in range(4)])
for i, s in enumerate(S, 1): s["id"] = i  # #NN = 1-based position
G = score_session(S, False, with_uncertainty=True)
SC = dict(groups=G)
grp = lambda p, k="FH": next(g for g in G if g["player"] == p and g["kind"] == k)
DD = lambda p, m="contact_fwd": grp(p)["drill_diff"]["metrics"][m]
ME, WIDE, FEW = DD("me"), DD("wide"), DD("few")
assert ME["diff"] == -0.25 and ME["ci"][1] < 0 and WIDE["ci"][0] <= 0 <= WIDE["ci"][1] and WIDE["diff"] != 0 and FEW["diff"] is None and FEW["ci"] is None and "對打可用 5 拍" in FEW["reason"], (ME, WIDE, FEW)

dd = lambda stat, value, m="contact_fwd", player="me", **kw: {"kind": "FH", "player": player, "drill_diff": m, "stat": stat, "value": value, **kw}
find = lambda text, *cites, **kw: dict(findings=[dict(info=True, title="t", text=text, cite=list(cites), **kw)])
errs = lambda notes, scores=SC: check(notes, S, scores)
ok = lambda notes, scores=SC: errs(notes, scores) == []


def bad(notes, *words, scores=SC):
    e = errs(notes, scores)
    assert e and all(w in "".join(e) for w in words), (words, e)


# 1. 合法引用：每種 stat 都過
d, lo, hi = ME["diff"], ME["ci"][0], ME["ci"][1]
for stat, v in (("diff", d), ("ci_lo", lo), ("ci_hi", hi), ("feed", ME["feed"]["median"]), ("rally", ME["rally"]["median"])):
    assert ok(find("", dd(stat, v))), (stat, errs(find("", dd(stat, v))))
assert ok(find(f"自拋減對打的差 {d}。", dd("diff", d)))
assert ok(find(f"自拋 {ME['feed']['median']}、對打 {ME['rally']['median']}，差 {d}。", dd("feed", ME["feed"]["median"]), dd("rally", ME["rally"]["median"]), dd("diff", d)))
for m in ("knee", "prep", "contact_h"):  # 別的指標走同一條路；它們的區間可能含 0，所以文字寫暫定
    assert ok(find("暫定", dd("diff", DD("me", m)["diff"], m))), (m, errs(find("暫定", dd("diff", DD("me", m)["diff"], m))))
# 2. 值錯、文字裡的數字沒有引用
bad(find("", dd("diff", -0.35)), "實際")
bad(find("", dd("feed", 0.9)), "實際")
bad(find("", dd("ci_hi", hi + 0.2)), "實際")
bad(find(f"自拋減對打的差 {d}。", dd("ci_lo", lo)), "沒有對應的引用")
# 3. metric 不存在、stat 不認得、value 缺
bad(find("", dd("diff", d, "elbow")), "elbow")
bad(find("", dd("sem", 0.06)), "sem")
bad(find("", dd("diff", None)), "實際")
# 4. 沒有 drill_diff 欄位（舊 scores.json）、發球整組 metrics 為 null
old = dict(groups=[{k: v for k, v in g.items() if k != "drill_diff"} for g in G])
e = errs(find("", dd("diff", d)), old); assert e and "沒有 drill_diff" in e[0] and "score.py" in e[0], e
sv = errs(find("", dict(dd("diff", 0.1), kind="SV")))
assert sv and "發球" in sv[0], sv
# 5. 拍數不夠 diff／ci 是 null：三種 stat 都擋，訊息帶 reason；feed／rally 中位數照樣能引
for stat in ("diff", "ci_lo", "ci_hi"): bad(find("", dd(stat, 0.1, player="few")), "對打可用 5 拍", "不能引用")
assert ok(find("", dd("feed", FEW["feed"]["median"], player="few"), dd("rally", FEW["rally"]["median"], player="few")))
# 6. diff 有值、ci 是 null（重抽失敗）：diff 也擋（沒有區間就不能說差）
cut = copy.deepcopy(SC)
for g in cut["groups"]:
    if g["player"] == "me" and g["kind"] == "FH": g["drill_diff"]["metrics"]["contact_fwd"].update(ci=None, sem=None, reason="重抽 1000 次裡有 3 次某一邊沒有可用的拍，不給區間")
bad(find("", dd("diff", d)), "重抽", scores=cut)
bad(find("", dd("ci_lo", lo)), "重抽", scores=cut)
# 7. 區間跨 0：確定語氣擋；有「不確定／暫定」字樣才過；區間不含 0 不要求字樣；feed／rally 不要求
wd = WIDE["diff"]
sure = f"自拋比對打前，差 {wd}。"
bad(find(sure, dd("diff", wd, player="wide")), "區間含 0", "不確定", "暫定")
assert ok(find(f"差 {wd}，區間含 0，不確定自拋是否比對打前。", dd("diff", wd, player="wide")))
assert ok(find(f"暫定：自拋比對打前，差 {wd}。", dd("diff", wd, player="wide")))
assert ok(find(f"差 {wd}，目前無法判定兩種練習有沒有差。", dd("diff", wd, player="wide")))
bad(find("自拋比對打前。", dd("ci_lo", WIDE["ci"][0], player="wide")), "區間含 0")
bad(dict(findings=[dict(info=True, title="自拋比對打前", text=f"差 {wd}。", cite=[dd("diff", wd, player="wide")])]), "區間含 0")  # 標題也算
assert ok(find(sure.replace(f"，差 {wd}", ""), dd("feed", WIDE["feed"]["median"], player="wide"), dd("rally", WIDE["rally"]["median"], player="wide")))
assert ok(find(f"自拋比對打前，差 {d}。", dd("diff", d)))
edge = copy.deepcopy(SC)  # 區間貼著 0（上界剛好 0）也算含 0
for g in edge["groups"]:
    if g["player"] == "me" and g["kind"] == "FH": g["drill_diff"]["metrics"]["contact_fwd"]["ci"] = [lo, 0.0]
bad(find("自拋比對打前。", dd("ci_lo", lo)), "區間含 0", scores=edge)
# 9. 球員／拍種對不上
bad(find("", dd("diff", d, player="nobody")), "nobody")
bad(find("", dd("diff", d, kind="BH")), "BH")
# 13. 壞資料不丟例外
for c in (dd("diff", d, m=["contact_fwd"]), dd("diff", d, m={"a": 1}), dict(dd("diff", d), stat=["diff"]), dict(dd("diff", d), drill_diff=None), dict(dd("diff", d), value="x"), dict(dd("diff", d), value=[d])):
    e = errs(find("", c)); assert isinstance(e, list) and e, c
# 12. change 不能加在 drill_diff 引用上（change 只認分數）
bad(find("", dict(dd("diff", d), change="up")), "change")

# 10./11. main 與問題型 finding 的證據
CITE = [dd("diff", d)]
MAIN = dict(title="自拋時把球打在身前", why=f"自拋減對打的差 {d}。", cite=CITE, practice="自拋時把球丟在身體側前方，在前腳前方打。", cue="打在前腳前", jump=[[13, "對打 #13"], [2, "自拋 #02"]])
OV = lambda **kw: dict(overall=[dict(player="me", main=dict(MAIN, **kw), look=[2, 5, 13])])
assert ok(OV())                                                       # 只靠 drill_diff 的 diff 引用，算比較證據
assert ok(OV(cite=[dd("ci_hi", hi)], why=f"差的區間上界 {hi}。"))
bad(OV(cite=[dd("feed", ME["feed"]["median"]), dd("rally", ME["rally"]["median"])], why=f"自拋 {ME['feed']['median']}、對打 {ME['rally']['median']}。"), "主要的事")  # 只有兩個中位數、沒有 drill 鍵：不是比較
bad(OV(cite=[dd("diff", 0.1, player="few")], why="差 0.1。"), "對打可用 5 拍")
bad(dict(overall=[dict(player="wide", main=dict(MAIN, why=f"自拋比對打前，差 {wd}。", cite=[dd("diff", wd, player="wide")]), look=[25, 26, 27])]), "區間含 0")
PROB = lambda *cites, text="": dict(findings=[dict(title="t", text=text, cite=list(cites))])
assert ok(PROB(dd("diff", d)))                                         # 問題型 finding：diff 是多拍統計，不被「單拍」規則擋
assert ok(PROB(dd("ci_lo", lo)))
bad(PROB(dd("feed", ME["feed"]["median"])), "問題型")                  # 只有一邊的中位數：沿用舊規則

print("ok")
