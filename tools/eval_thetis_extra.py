"""THETIS 評估補充：(a) guess_hand 逐受試者、跨模式一致性與對眼睛確認者的命中；(b) 單手 vs 雙手反拍（雙腕距離）可分性。
用法：.venv/bin/python tools/eval_thetis_extra.py   （需先跑 eval_thetis.py 三個模式；只用本機 THETIS 姿態，不輸出任何影格）"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from eval_thetis import EYE, W, SIZE, load, peak
from metrics import _scale

res = {m: json.load(open(f"{W}/res_{m}_first.json", encoding="utf-8")) for m in ("native18", "interp60", "dup60")}
print("## guess_hand（逐受試者，括號 = 快手腕/慢手腕 98 百分位比）\n")
print("| 模式 | 判 R | 判 L | 判不出 | 與 interp60 一致 | 眼睛確認者命中 |\n|---|---|---|---|---|---|")
base = {int(p): v[0] for p, v in res["interp60"]["hands"].items()}
for m, d in res.items():
    h = {int(p): v[0] for p, v in d["hands"].items()}
    ag = np.mean([h[p] == base[p] for p in h if h[p] and base[p]])
    hit = [h[p] == e for p, e in EYE.items() if h.get(p)]
    print(f"| {m} | {sum(v == 'R' for v in h.values())} | {sum(v == 'L' for v in h.values())} | {sum(v is None for v in h.values())} | {ag:.0%} | {sum(hit)}/{len(EYE)} |")
print("\n| 受試者 | 眼睛 | native18 | interp60 | dup60 | interp60 ratio |\n|---|---|---|---|---|---|")
for p in sorted(base):
    e = EYE.get(p, "")
    print(f"| p{p} | {e} | " + " | ".join(str(res[m]['hands'][str(p)][0]) for m in res) + f" | {res['interp60']['hands'][str(p)][1]} |")

print("\n## 單手 vs 雙手反拍（backhand vs backhand2h，interp60，擊球點 = 速度峰值，持拍手 = 眼睛確認者其餘 R）\n")
rows = [r for r in res["interp60"]["rows"] if r["action"] in ("backhand", "backhand2h")]
F = []; sc = _scale(SIZE)
for r in rows:
    P, Wd = load("interp60", r["name"]); h = EYE.get(r["person"], "R"); f = peak(P, h, 60)
    if f is None or f < 4 or f + 4 >= len(P): continue
    xy = P[:, :, :2] * sc; L = np.nanmedian(np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1))
    w = slice(f - 4, f + 5); d2 = np.linalg.norm(xy[w, 15] - xy[w, 16], axis=1) / L; d3 = np.linalg.norm(Wd[w, 15] - Wd[w, 16], axis=1)
    vis = np.nanmean(P[w, 15:17, 2])
    F.append((r["action"] == "backhand2h", np.nanmin(d2) if np.isfinite(d2).any() else np.nan, np.nanmin(d3) if np.isfinite(d3).any() else np.nan, vis, r["person"]))
F = np.array(F, float); print(f"片段 {len(F)}（雙手 {int(F[:, 0].sum())}、單手 {int((1 - F[:, 0]).sum())}）\n")
for name, col in (("2D 雙腕最小距離/軀幹長", 1), ("3D 雙腕最小距離(m)", 2)):
    x = F[:, col]; ok = np.isfinite(x); best = (0, 0)
    for t in np.unique(x[ok]):
        pred = x < t; acc = np.mean(pred[ok] == (F[ok, 0] == 1)); best = max(best, (acc, t))
    # 兩手互換也可（單手者距離應大）；另報可見度閘（雙腕可見度 >= 0.5）後的結果與覆蓋率
    g = ok & (F[:, 3] >= 0.5); b2 = (0, 0)
    for t in np.unique(x[g]):
        acc = np.mean((x[g] < t) == (F[g, 0] == 1)); b2 = max(b2, (acc, t))
    print(f"- {name}：全部 {ok.sum()} 支最佳門檻 {best[1]:.2f} → {best[0]:.0%}；可見度≥0.5 的 {g.sum()} 支（{g.mean():.0%}）最佳 {b2[0]:.0%}（門檻 {b2[1]:.2f}）")
# 初學者／高手分開
for lab, sel in (("初學者", F[:, 4] <= 31), ("高手", F[:, 4] >= 32)):
    x = F[sel, 1]; y = F[sel, 0] == 1; ok = np.isfinite(x)
    t = 0.0 if not ok.any() else max(np.unique(x[ok]), key=lambda t: np.mean((x[ok] < t) == y[ok]))
    print(f"- {lab} 2D：{ok.sum()} 支，最佳門檻 {t:.2f} → {np.mean((x[ok] < t) == y[ok]):.0%}（雙手 {int(y.sum())}）")
# 樣本外：受試者奇偶分兩半，一半選門檻、另一半測（兩個方向取平均）
for name, col in (("2D", 1), ("3D", 2)):
    accs = []
    for tr in (F[:, 4] % 2 == 0, F[:, 4] % 2 == 1):
        te = ~tr; a, b = tr & np.isfinite(F[:, col]), te & np.isfinite(F[:, col])
        t = max(np.unique(F[a, col]), key=lambda t: np.mean((F[a, col] < t) == (F[a, 0] == 1)))
        accs.append(np.mean((F[b, col] < t) == (F[b, 0] == 1)))
    print(f"- 樣本外（按受試者奇偶對分）{name}：{accs[0]:.0%} / {accs[1]:.0%}，平均 {np.mean(accs):.0%}")
