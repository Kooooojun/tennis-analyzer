"""K6：單手／雙手反拍（擊球點 ±4 格兩腕最小距離）在重標標籤上的樣本外準確率。
用法：.venv/bin/python tools/eval_thetis_grip.py   （需要 work/thetis 的 interp60 姿態與 testset/labels/thetis_bh_grip.csv；只在本機）
切分單位是受試者：奇偶對分（一半選門檻、另一半只測一次）與留一受試者。門檻只在訓練受試者的「雙腕可見度≥0.5」拍上選。
決策（事先定）：可見度≥0.5 子集樣本外 ≥85% 且 Wilson 95% 下界 ≥78% 且覆蓋 ≥40% 才在 kind.py 加 grip。"""
import csv, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from eval_thetis import EYE, SIZE, load, peak
from metrics import _scale

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.environ.get("GRIP_LABELS", f"{R}/testset/labels/thetis_bh_grip.csv")
DROP = {int(x) for x in os.environ.get("GRIP_DROP", "").split(",") if x}  # 受試者排除（敏感度檢查）


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def best_t(x, y):
    """y=True 雙手；判雙手 = x < t。回傳訓練準確率最高的 t（同分取中間值）。"""
    u = np.unique(x); c = np.concatenate([[u[0] - 1e-6], (u[:-1] + u[1:]) / 2, [u[-1] + 1e-6]]) if len(u) else np.array([0.0])
    acc = np.array([np.mean((x < t) == y) for t in c]); return float(c[acc == acc.max()][len(c[acc == acc.max()]) // 2])


def feats():
    rows = [r for r in csv.DictReader(open(LAB, encoding="utf-8")) if r["grip"] in ("one", "two") and int(r["person"]) not in DROP]
    F = []; sc = _scale(SIZE)
    for r in rows:
        P, Wd = load("interp60", r["clip"].removesuffix(".avi")); p = int(r["person"]); f = peak(P, EYE.get(p, "R"), 60)
        if f is None or f < 4 or f + 4 >= len(P): F.append((r["grip"] == "two", np.nan, np.nan, 0.0, p, r["folder"] == "two")); continue
        xy = P[:, :, :2] * sc; L = np.nanmedian(np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1))
        w = slice(f - 4, f + 5); d2 = np.linalg.norm(xy[w, 15] - xy[w, 16], axis=1) / L; d3 = np.linalg.norm(Wd[w, 15] - Wd[w, 16], axis=1)
        vis = float(np.nanmin(np.nanmean(P[w, 15:17, 2], axis=0)))  # 兩腕各自的平均可見度，取較低者（任一腕看不到就不算）
        F.append((r["grip"] == "two", np.nanmin(d2) if np.isfinite(d2).any() else np.nan, np.nanmin(d3) if np.isfinite(d3).any() else np.nan, vis, p, r["folder"] == "two"))
    return np.array(F, float)


def held_out(F, col, gate, splits):
    """splits: [(train_mask, test_mask)]，門檻在 train&gate 上選；回傳 (test 命中, test 數, 覆蓋分母)。"""
    k = n = 0
    ok = np.isfinite(F[:, col]) & (F[:, 3] >= gate)
    for tr, te in splits:
        a, b = tr & ok, te & ok
        if not a.any() or not b.any(): continue
        t = best_t(F[a, col], F[a, 0] == 1); k += int(np.sum((F[b, col] < t) == (F[b, 0] == 1))); n += int(b.sum())
    return k, n


if __name__ == "__main__":
    allr = list(csv.DictReader(open(LAB, encoding="utf-8")))
    q = sum(r["grip"] == "?" for r in allr); dis = sum(r["grip"] in ("one", "two") and r["grip"] != r["folder"] for r in allr)
    F = feats(); two = int(F[:, 0].sum())
    print(f"重標：{len(allr)} 拍，與原資料夾不一致 {dis}、`?` {q}；可用 {len(F)}（雙手 {two} = {two / len(F):.0%}）{'；排除受試者 ' + str(sorted(DROP)) if DROP else ''}\n")
    pp = F[:, 4]; subj = np.unique(pp)
    odd = [(pp % 2 == 0, pp % 2 == 1), (pp % 2 == 1, pp % 2 == 0)]
    loso = [(pp != s, pp == s) for s in subj]
    print("| 特徵 | 子集 | 切分 | 樣本外準確率 | Wilson 95% | 覆蓋 |\n|---|---|---|---|---|---|")
    for name, col in (("2D", 1), ("3D", 2)):
        for gname, g in (("全部", -1.0), ("雙腕可見度≥0.5", 0.5)):
            for sname, sp in (("奇偶對分", odd), ("留一受試者", loso)):
                k, n = held_out(F, col, g, sp); lo, hi = wilson(k, n)
                print(f"| {name} | {gname} | {sname} | {k}/{n} = {k / max(n, 1):.0%} | {lo:.0%}–{hi:.0%} | {n / len(F):.0%} |")
    k, n = held_out(F, 2, 0.5, loso); lo, _ = wilson(k, n); cov = n / len(F)
    ok = n and k / n >= 0.85 and lo >= 0.78 and cov >= 0.40
    print(f"\n決策（3D、可見度≥0.5、留一受試者）：{k / max(n, 1):.0%}、下界 {lo:.0%}、覆蓋 {cov:.0%} → {'達標：可加 grip' if ok else '沒達標：kind.py 不加 grip'}")
    t = best_t(F[np.isfinite(F[:, 2]) & (F[:, 3] >= 0.5), 2], F[np.isfinite(F[:, 2]) & (F[:, 3] >= 0.5), 0] == 1)
    print(f"全體（樣本內，僅供參考）3D 門檻 {t:.3f} m")
    # 原資料夾標籤當答案的對照（跟舊報告同口徑）
    G = F.copy(); G[:, 0] = G[:, 5]; k, n = held_out(G, 2, -1.0, odd); print(f"對照：原資料夾標籤、3D、全部、奇偶對分 {k}/{n} = {k / max(n, 1):.0%}")
