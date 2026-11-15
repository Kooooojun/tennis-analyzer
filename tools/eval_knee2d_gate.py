"""A15：`knee2d_ok`（2D 膝角閘門）對 CalTennis 兩機三角測量真值有沒有預測力。
用法：.venv/bin/python tools/eval_knee2d_gate.py [work 目錄，預設 work]   需要 <work>/ct-{1..4}/pose.npy（60 fps proxy 的姿態，960x540）
與 testset/results/eval-caltennis/res.csv（只在本機，不進 git）。不重算姿態。
步驟：(1) 用已知的 proxy 起點（下方 T0）把 res.csv 的 t 換成格號，並報與舊 2D 膝角的中位差當檢查；(2) 每拍·機用 metrics.kinematics 算
knee2d_ok，誤差 = |本姿態 2D 膝角 − knee_ref|；(3) true／false 兩組 n、中位、p90、比值，按拍分群 bootstrap 95% 區間；(4) 掃 LIMB_FULL。
選值只用 cam 1、2，cam 3、4 驗證：同一球員在兩邊都有（1/3、2/4 同人），只能當粗略驗證。"""
import csv, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import metrics
from metrics import _knee, _scale, kinematics, FULL

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = sys.argv[1] if len(sys.argv) > 1 else f"{R}/work"
RES = f"{R}/testset/results/eval-caltennis/res.csv"
SIZE = (960, 540); MIN_FALSE = 30


def rows():
    return [dict(r, cam=int(r["cam"]), partner=int(r["partner"]), t=float(r["t"]), knee_ref=float(r["knee_ref"]), knee2d=float(r["knee2d"]))
            for r in csv.DictReader(open(RES, encoding="utf-8")) if r["knee_ref"] not in ("", "nan")]


# proxy 第 0 格在 CalTennis 共用時鐘（距 19:49:00 秒）的時間：每機原檔 ffmpeg -ss 300 -t 300 -c copy，起點用逐像素比對原檔格找到，
# 換算 = 檔名開錄秒數 + 該格 timestamps.npy / 1000。res.csv 的 t 是同一個共用時鐘（ct_pose.py）。proxy 60 fps 重取樣，原檔 59.92–59.98 fps，
# 5 分鐘內 k/60 與逐格時間差 < 0.1 s（約 6 格），對 _knee 的 43 格窗是小誤差。
# res.csv 的 t 已扣掉 docs/research/caltennis/ct_tri.py 的 SHIFT（檔名開錄時間不準的修正，cam 3、4），這裡同樣扣掉。
SHIFT = {1: 0, 2: 0, 3: 126 / 60, 4: 35 / 60}
T0 = {c: t - SHIFT[c] for c, t in {1: 333.980, 2: 328.980, 3: 356.025, 4: 352.015}.items()}


def align(P, rs, T0c):
    """對齊檢查：在給定起點下，本姿態 2D 膝角與 res.csv 舊 2D 膝角的中位差與拍數。"""
    xy = P[:, :, :2] * _scale(SIZE); d = []
    for r in rs:
        g = int(round((r["t"] - T0c) * 60))
        if 48 <= g < len(P) - 6 and np.isfinite(r["knee2d"]):
            k = _knee(xy, FULL, g)
            if np.isfinite(k): d.append(abs(k - r["knee2d"]))
    return T0c, float(np.median(d)) if d else np.nan, len(d)


def measure():
    ROWS = rows(); out = []; al = {}
    for cam in (1, 2, 3, 4):
        P = np.load(f"{WK}/ct-{cam}/pose.npy").astype(float)
        assert P.ndim == 3 and P.shape[1:] == (33, 3), P.shape
        rs = [r for r in ROWS if r["cam"] == cam]; T0c, md, n = align(P, rs, T0[cam]); al[cam] = (T0c, md, n, len(rs), float(np.isfinite(P[:, 0, 0]).mean()))
        xy = P[:, :, :2] * _scale(SIZE)
        for r in rs:
            g = int(round((r["t"] - T0c) * 60))
            if not 48 <= g < len(P) - 6: continue
            k2 = _knee(xy, FULL, g)
            out.append(dict(cam=cam, partner=r["partner"], t=r["t"], g=g, ref=r["knee_ref"], k2=k2, err=abs(k2 - r["knee_ref"]) if np.isfinite(k2) else np.nan,
                            xy=xy, hand=r["hand"]))
    return out, al


def gate(o, limb):
    old, metrics.LIMB_FULL = metrics.LIMB_FULL, limb
    try: return kinematics(o["xy"], FULL, o["g"], o["hand"])["knee2d_ok"]
    finally: metrics.LIMB_FULL = old


def strokes(O):
    """同一拍兩機（1/3、2/4）＝同一群：同一對、時間差 ≤0.15 s。"""
    gid = []; seen = []
    for o in O:
        pair = min(o["cam"], o["partner"]); m = next((i for i, (p, t) in enumerate(seen) if p == pair and abs(t - o["t"]) <= 0.15), None)
        if m is None: seen.append((pair, o["t"])); m = len(seen) - 1
        gid.append(m)
    return np.array(gid)


def stats(err, ok, gid, B=2000, seed=15):
    """ok: True/False 陣列。回傳 dict(nT, nF, medT, medF, p90T, p90F, ratio, lo, hi)；ratio = false 組中位 ÷ true 組中位。"""
    def one(e, k):
        t, f = e[k], e[~k]
        return (np.median(t) if len(t) else np.nan, np.median(f) if len(f) else np.nan)
    mt, mf = one(err, ok); r = mf / mt if mt > 0 else np.nan
    rng = np.random.default_rng(seed); u = np.unique(gid); bs = []
    for _ in range(B):
        pick = rng.choice(u, len(u)); idx = np.concatenate([np.flatnonzero(gid == g) for g in pick])
        a, b = one(err[idx], ok[idx]); bs.append(b / a if a > 0 else np.nan)
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return dict(nT=int(ok.sum()), nF=int((~ok).sum()), medT=mt, medF=mf, p90T=np.percentile(err[ok], 90) if ok.any() else np.nan,
                p90F=np.percentile(err[~ok], 90) if (~ok).any() else np.nan, ratio=r, lo=lo, hi=hi)


def table(O, limb, sel=None):
    g = [gate(o, limb) for o in O]; keep = [i for i, o in enumerate(O) if g[i] is not None and np.isfinite(o["err"]) and (sel is None or o["cam"] in sel)]
    if not keep: return None, 0
    err = np.array([O[i]["err"] for i in keep]); ok = np.array([g[i] for i in keep], bool); gid = strokes([O[i] for i in keep])
    return stats(err, ok, gid), len(keep)


if __name__ == "__main__":
    O, al = measure()
    print("## 對齊（proxy 起點 T0，與舊 2D 膝角的中位差）\n\n| cam | T0 (s) | 中位差 | 用到 | res 拍數 | 有骨架的格 |\n|---|---|---|---|---|---|")
    for c, (t0, md, n, nr, det) in al.items(): print(f"| {c} | {t0:.3f} | {md:.1f}° | {n} | {nr} | {det:.0%} |")
    fin = sum(np.isfinite(o["err"]) for o in O); print(f"\n拍·機 {len(O)}，有 2D 膝角（窗內有骨架）{fin}\n")
    fmt = lambda s, n: (f"| {n} | {s['nT']} | {s['nF']} ({s['nF'] / max(n, 1):.0%}) | {s['medT']:.1f}° / {s['p90T']:.1f}° | {s['medF']:.1f}° / {s['p90F']:.1f}° | "
                        f"{s['ratio']:.2f}（{s['lo']:.2f}–{s['hi']:.2f}） |")
    print("## LIMB_FULL 掃描（比值 = false 組中位 ÷ true 組中位，區間 = 按拍分群 bootstrap 95%）\n")
    for name, sel in (("全部 cam", None), ("選值 cam 1、2", (1, 2)), ("驗證 cam 3、4", (3, 4))):
        print(f"### {name}\n\n| LIMB_FULL | 有旗標 n | true | false (比例) | true 中位/p90 | false 中位/p90 | 比值 |\n|---|---|---|---|---|---|---|")
        for limb in (0.6, 0.7, 0.8, 0.9):
            s, n = table(O, limb, sel)
            if s: print(fmt(s, n).replace(f"| {n} |", f"| {limb} | {n} |", 1))
        print()
    s, n = table(O, 0.8)
    if s is None: sys.exit("沒有任何拍同時有閘門旗標與 2D 膝角誤差：檢查姿態檔與對齊表")
    if s["nF"] < MIN_FALSE: verdict = "資料不夠（false 組 < 30）：不改"
    elif s["ratio"] >= 2.0 and s["lo"] >= 1.5: verdict = "閘門有效：metrics.py 不動"
    else:
        tr = {l: table(O, l, (1, 2))[0] for l in (0.6, 0.7, 0.9)}; cand = [l for l, t in tr.items() if t and t["nF"] >= MIN_FALSE and t["ratio"] >= 2.0]
        va = {l: table(O, l, (3, 4)) for l in cand}
        good = [l for l, (t, n) in va.items() if t and t["ratio"] >= 2.0 and t["nF"] / n <= 0.5]
        verdict = f"改 LIMB_FULL 為 {good[0]}（cam 1、2 選、3、4 驗，粗略）" if good else "閘門沒有預測力：不改程式，建議降為提示"
    print(f"決策（現行 0.8，全部 cam）：false {s['nF']}、比值 {s['ratio']:.2f}（下界 {s['lo']:.2f}）→ {verdict}")
