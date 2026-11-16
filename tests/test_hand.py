# 慣用手測試（純邏輯）：把右手的真實資料左右鏡像，hand="L" 的結果必須與原資料 hand="R" 相同。
# 用法（repo 根目錄）：.venv/bin/python tests/test_hand.py   需要 testset/labels/private_names.json（私有影片的別名 -> 實際名稱，不進 git）、
# 對牆影片 A 的 pose.npy 與 strokes.json；第 5 段另需網路片 E／F 的姿態。
# CI 排除：需要私人資料（testset/、work/），.github/workflows/ci.yml 不跑這支。
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from metrics import measure_full, measure_clip, guess_hand
from common import ROOT, load_profiles, profile_for

NAMES = ROOT / "testset/labels/private_names.json"  # 檔名留在私有檔，公開 repo 只有別名
PN = json.load(open(NAMES, encoding="utf-8")) if NAMES.exists() else dict(wall_a=["?"], wall_dir="?", wall_strokes="?")
VIDS = PN.get("wall_a") or ["?"]; V0 = VIDS[0]; WD = ROOT / PN.get("wall_dir", "?"); STROKES = ROOT / PN.get("wall_strokes", "?")
NEED = [NAMES, STROKES, WD / V0 / "pose_t1.npy", WD / V0 / "events.npy", ROOT / f"testset/labels/hits_{V0}.csv"]
NEED += [WD / v / f for v in VIDS for f in ("pose.npy", "pose_world.npy")]
if not all(p.exists() for p in NEED):  # private footage-derived data, only on the owner's machine
    print("略過：test_hand 需要本機對牆影片 A 的資料"); sys.exit(0)

# MediaPipe 33 點、web 用的 17 點（common.KEEP 順序）裡的左右對換表
SW33 = list(range(33)); SW17 = list(range(17))
for a in range(1, 33, 2): SW33[a], SW33[a + 1] = a + 1, a
for a in range(1, 17, 2): SW17[a], SW17[a + 1] = a + 1, a
mir = lambda P, sw: np.concatenate([-P[..., sw, :1], P[..., sw, 1:]], axis=-1)  # x 取負（指標只用差值，取負是精確鏡像，不會有 1-x 的浮點誤差），左右點互換
mirw = lambda W, sw: np.concatenate([-W[..., sw, :1], W[..., sw, 1:]], axis=-1)    # world: x 取負

def close(a, b, tol, tag):
    for k in a:
        x, y = a[k], b[k]
        if k == "pose_jump_joints" and x is not None and y is not None:
            # These labels name anatomical sides, so mirroring must swap them back before comparison.
            x, y = sorted(x), sorted(("r" if j[0] == "l" else "l") + j[1:] if j[0] in "lr" else j for j in y)
        if x is None or y is None or isinstance(x, (bool, str, list)): assert x == y, (tag, k, x, y); continue
        if k == "auto_kind": assert x == y, (tag, k, x, y); continue
        if x != x and y != y: continue  # NaN 對 NaN
        assert abs(x - y) <= tol.get(k, 0.011), (tag, k, x, y)

# 1. clip 版：35 拍 對牆影片 A（含 3D world）
S = json.load(open(STROKES, encoding="utf-8")); off = 0
for s in S:
    fr = s["frames"]; wd = s.get("world")
    a = measure_clip(fr, s["contact"], s.get("size"), wd)  # 預設右手
    mf = [None if f is None else mir(np.array(f, float), SW17).tolist() for f in fr]
    mw = None if wd is None else [None if w is None else mirw(np.array(w, float), SW17).tolist() for w in wd]
    assert measure_clip(fr, s["contact"], s.get("size"), wd, hand="R") == a  # 明確寫 R = 沒寫
    close(a, measure_clip(mf, s["contact"], s.get("size"), mw, hand="L"), {}, f"clip#{s['id']}")
    wrong = measure_clip(mf, s["contact"], s.get("size"), mw)  # 對照組：左手資料卻當右手 → 手肘一定偏掉
    off += abs(wrong["elbow"] - a["elbow"]) > 1
assert off > 0, "對照組沒有任何一拍手肘偏掉：鏡像測試沒有鑑別力"
print("clip 鏡像 OK", len(S), "拍；左手資料當右手時手肘偏掉", off)

# 2. full 版：整支 pose.npy（auto_kind 也要鏡像）
n = bad = 0
for v in VIDS:
    d = WD / v; P = np.load(d / "pose.npy").astype(float); W = np.load(d / "pose_world.npy").astype(float)
    for s in S:
        if s["video"] != VIDS.index(v) + 1: continue
        try: a = measure_full(P, s["t"], (960, 540), W)
        except TypeError: continue  # 那一格沒抓到人
        b = measure_full(mir(P, SW33), s["t"], (960, 540), mirw(W, SW33), hand="L"); n += 1
        close(a, b, {}, f"full {v} t={s['t']}")
        wk = measure_full(mir(P, SW33), s["t"], (960, 540), mirw(W, SW33))["auto_kind"]  # 對照：不告訴它是左手
        assert wk in ("FH", "BH", "SV", "OH", "?"), wk
        bad += wk != a["auto_kind"]
print("full 鏡像 OK", n, "拍；左手資料當右手時 auto_kind 錯", bad)

# 3. 猜慣用手：只看揮拍段；鏡像資料猜出相反邊；太短不猜
from eval_hits import read_labels
P = np.load(WD / V0 / "pose_t1.npy").astype(float)  # 使用者本人，右手（逐拍看圖確認過，見 testset/results/player-profile.md）
ts = [[float(r["t_sec"]) for r in read_labels(ROOT / f"testset/labels/hits_{V0}.csv")[0] if r["player"] == "white"]]
h, ratio = guess_hand([P], (960, 540), ts); hm, _ = guess_hand([mir(P, SW33)], (960, 540), ts)
assert (h, hm) == ("R", "L") and ratio > 1.15, (h, hm, ratio)
assert guess_hand([P[:30]], (960, 540))[0] is None
print("猜慣用手 OK", h, ratio)

# 3b. 多人：candidates.py 用每人自己的持拍手腕算 match / swing（左手玩家鏡像後要跟右手原資料相同）
from match import match, WRIST
E = np.load(WD / V0 / "events.npy"); A = np.array([960, 540]) / 540
for v in ("pose.npy", "pose_t1.npy"):
    Q = np.load(WD / V0 / v).astype(float); a = match(Q, E, A, "R"); b = match(mir(Q, SW33), E, A, "L")
    assert len(a) and np.array_equal(a, b, equal_nan=True), v
    assert not np.array_equal(a, match(mir(Q, SW33), E, A, "R"), equal_nan=True), "對照組：左手資料當右手應該不同"
from attrib import swing
f0 = [int(round(t * 60)) for t in E[:, 0] if 30 < t * 60 < len(Q) - 30]
assert all(abs(swing(Q, f, A) - swing(mir(Q, SW33), f, A, WRIST["L"])) < 1e-9 for f in f0)
print("多人 match/swing 鏡像 OK", len(a), "個擊球事件")

# 4. 設定檔：打錯的值要報錯，沒設定回 None
assert profile_for({}, "x") is None and profile_for({"a": {"hand": "L", "backhand": "one"}}, "a") == {"hand": "L", "backhand": "one"}
for bad_cfg in ({"a": {"hand": "left"}}, {"a": {"hand": "R", "backhand": "3"}}, {"a": "R"}):
    try: profile_for(bad_cfg, "a"); raise SystemExit(f"應該報錯：{bad_cfg}")
    except ValueError: pass
print("設定檔 OK")

# 5. 真實左手（網路片 E／F）。不是鏡像：真的左手姿態，hand="L" 對 "R"。
# 門檻 = 2026-11-15 量到的數字（eval-labels-c19），只防退步；不為了過關調 kind.py。網路片 F 只用已標 @player 的拍，兩人都是左手，不算左右手混合測試。
from metrics import arm_checks
from common import KEEP
LEFTY = [ROOT / d for d in PN.get("lefty", [])]
def _lefty_ok(d):  # strokes_all.json 與它用到的每支影片的姿態都在才跑
    f = d / "strokes_all.json"
    return f.exists() and all((d / s["video"] / n).exists() for s in json.load(open(f, encoding="utf-8")) for n in ("pose.npy", "pose_world.npy"))
if len(LEFTY) == 2 and all(_lefty_ok(d) for d in LEFTY):
    got = {}
    for d in LEFTY:
        S = [s for s in json.load(open(d / "strokes_all.json", encoding="utf-8")) if s.get("player") and s["hand"] == "L"]; c = {}
        for s in S:
            v = d / s["video"]; P = np.load(v / "pose.npy").astype(float); W = np.load(v / "pose_world.npy").astype(float)
            for h in "LR":
                m = measure_full(P, s["t"], tuple(s["size"]), W, h); k = c.setdefault(h, dict(ok=0, fb=0, elbow=0, fwd=0, sv=0, sv_has=0))
                if s["kind"] in ("FH", "BH"): k["fb"] += 1; k["ok"] += m["auto_kind"] == s["kind"]
                k["elbow"] += m["elbow"] is not None and m["elbow"] == m["elbow"]; k["fwd"] += m["contact_fwd"] is not None and m["contact_fwd"] == m["contact_fwd"]
                if s["kind"] == "SV":
                    k["sv"] += 1; k["sv_has"] += arm_checks(list(P[:, KEEP]), m["f"], tuple(s["size"]), list(W[:, KEEP]), "SV", h)["serve_arm_straight"] is not None
        got[len(got)] = (len(S), c)
    (na, a), (nb, b) = got[0], got[1]
    assert a["L"]["ok"] > a["R"]["ok"] and b["L"]["ok"] > b["R"]["ok"], got  # 左手設 L 的 FH/BH 對率要比當右手好
    assert a["L"]["fb"] == 42 and a["L"]["ok"] >= 24 and b["L"]["ok"] >= 13, got  # 量到 E 24/42（FH 8/17、BH 16/25）、F 13/17
    assert a["L"]["elbow"] == na and b["L"]["elbow"] == nb and a["L"]["fwd"] >= 0.85 * na and b["L"]["fwd"] >= 0.85 * nb, got
    assert b["L"]["sv"] >= 15 and b["L"]["sv_has"] / b["L"]["sv"] >= 0.4, got  # 發球手臂有結論：量到 11/17；當右手只有 4/17
    print("真實左手 OK", {i: (n, c["L"]["ok"], c["R"]["ok"]) for i, (n, c) in got.items()})
else: print("skip: 真實左手段需要網路左手影片的姿態")
print("test_hand: ALL OK")
