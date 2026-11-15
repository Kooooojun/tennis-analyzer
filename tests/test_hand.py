# 慣用手測試（純邏輯）：把右手的真實資料左右鏡像，hand="L" 的結果必須與原資料 hand="R" 相同。
# 用法（repo 根目錄）：.venv/bin/python tests/test_hand.py   需要 work/wall-1/*/pose.npy 與 testset/archive/prep-contact 的結果。
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from metrics import measure_full, measure_clip, guess_hand
from common import ROOT, load_profiles, profile_for

NEED = [ROOT / "testset/archive/prep-contact/web/sessions/wall-1/strokes.json", ROOT / "work/wall-1/IMG_8460/pose_t1.npy", ROOT / "testset/labels/hits_IMG_8460.csv"]
if not all(p.exists() for p in NEED):  # private footage-derived data, only on the owner's machine
    print("skip: test_hand needs local wall-1 data"); sys.exit(0)

# MediaPipe 33 點、web 用的 17 點（common.KEEP 順序）裡的左右對換表
SW33 = list(range(33)); SW17 = list(range(17))
for a in range(1, 33, 2): SW33[a], SW33[a + 1] = a + 1, a
for a in range(1, 17, 2): SW17[a], SW17[a + 1] = a + 1, a
mir = lambda P, sw: np.concatenate([-P[..., sw, :1], P[..., sw, 1:]], axis=-1)  # x 取負（指標只用差值，取負是精確鏡像，不會有 1-x 的浮點誤差），左右點互換
mirw = lambda W, sw: np.concatenate([-W[..., sw, :1], W[..., sw, 1:]], axis=-1)    # world: x 取負

def close(a, b, tol, tag):
    for k in a:
        x, y = a[k], b[k]
        if x is None or y is None or isinstance(x, (bool, str)): assert x == y, (tag, k, x, y); continue
        if k == "auto_kind": assert x == y, (tag, k, x, y); continue
        if x != x and y != y: continue  # NaN 對 NaN
        assert abs(x - y) <= tol.get(k, 0.011), (tag, k, x, y)

# 1. clip 版：35 拍 wall-1（含 3D world）
S = json.load(open(ROOT / "testset/archive/prep-contact/web/sessions/wall-1/strokes.json")); off = 0
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
for v in ("IMG_8460", "IMG_8462", "IMG_8466"):
    d = ROOT / "work/wall-1" / v; P = np.load(d / "pose.npy").astype(float); W = np.load(d / "pose_world.npy").astype(float)
    for s in S:
        if s["video"] != ["IMG_8460", "IMG_8462", "IMG_8466"].index(v) + 1: continue
        try: a = measure_full(P, s["t"], (960, 540), W)
        except TypeError: continue  # 那一格沒抓到人
        b = measure_full(mir(P, SW33), s["t"], (960, 540), mirw(W, SW33), hand="L"); n += 1
        close(a, b, {}, f"full {v} t={s['t']}")
        wk = measure_full(mir(P, SW33), s["t"], (960, 540), mirw(W, SW33))["auto_kind"]  # 對照：不告訴它是左手
        assert wk in ("FH", "BH", "SV", "OH", "?"), wk
        bad += wk != a["auto_kind"]
print("full 鏡像 OK", n, "拍；左手資料當右手時 auto_kind 錯", bad)

# 3. 猜慣用手：只看揮拍段；鏡像資料猜出相反邊；太短不猜
import csv
P = np.load(ROOT / "work/wall-1/IMG_8460/pose_t1.npy").astype(float)  # 白衣，右手（逐拍看圖確認過，見 testset/results/player-profile.md）
ts = [[float(r["t_sec"]) for r in csv.DictReader(open(ROOT / "testset/labels/hits_IMG_8460.csv")) if r["player"] == "white"]]
h, ratio = guess_hand([P], (960, 540), ts); hm, _ = guess_hand([mir(P, SW33)], (960, 540), ts)
assert (h, hm) == ("R", "L") and ratio > 1.15, (h, hm, ratio)
assert guess_hand([P[:30]], (960, 540))[0] is None
print("猜慣用手 OK", h, ratio)

# 3b. 多人：candidates.py 用每人自己的持拍手腕算 match / swing（左手玩家鏡像後要跟右手原資料相同）
from match import match, WRIST
import ast
E = np.load(ROOT / "work/wall-1/IMG_8460/events.npy"); A = np.array([960, 540]) / 540
for v in ("pose.npy", "pose_t1.npy"):
    Q = np.load(ROOT / "work/wall-1/IMG_8460" / v).astype(float); a = match(Q, E, A, "R"); b = match(mir(Q, SW33), E, A, "L")
    assert len(a) and np.array_equal(a, b, equal_nan=True), v
    assert not np.array_equal(a, match(mir(Q, SW33), E, A, "R"), equal_nan=True), "對照組：左手資料當右手應該不同"
src = (ROOT / "tools/candidates.py").read_text(); fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "swing")
exec(ast.get_source_segment(src, fn))
f0 = [int(round(t * 60)) for t in E[:, 0] if 30 < t * 60 < len(Q) - 30]
assert all(abs(swing(Q, f, A) - swing(mir(Q, SW33), f, A, WRIST["L"])) < 1e-9 for f in f0)
print("多人 match/swing 鏡像 OK", len(a), "個擊球事件")

# 4. 設定檔：打錯的值要報錯，沒設定回 None
assert profile_for({}, "x") is None and profile_for({"a": {"hand": "L", "backhand": "one"}}, "a") == {"hand": "L", "backhand": "one"}
for bad_cfg in ({"a": {"hand": "left"}}, {"a": {"hand": "R", "backhand": "3"}}, {"a": "R"}):
    try: profile_for(bad_cfg, "a"); raise SystemExit(f"應該報錯：{bad_cfg}")
    except ValueError: pass
print("設定檔 OK"); print("test_hand: ALL OK")
