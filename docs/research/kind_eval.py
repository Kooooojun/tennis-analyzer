# kind_eval.py — 擊球種類混淆矩陣。從 repo 根目錄跑：.venv/bin/python -I docs/research/kind_eval.py
# 標準答案：work/kind/labels.txt（「<影片> <幀> <FH|BH|BH1|BH2|SV|OH>」，眼睛標，標時不看模型輸出）＋ 對牆影片 A 的人工標籤（場次從 testset/labels/private_names.json 的 wall_dir 讀取）（archive 各卡 labels.txt 的 FH）。
import sys, json, glob, collections, numpy as np
from pathlib import Path
sys.path.insert(0, "tools")
from kind import classify, CONF_MIN
from common import size

def legacy(P, f):  # 改前的 metrics.measure_full 規則（右手），原樣保留供對照
    hip_x = np.nanmean((P[f - 8:f + 9, 23, 0] + P[f - 8:f + 9, 24, 0]) / 2)
    nose_y = np.nanmean(P[f - 3:f + 4, 0, 1]); wy = np.nanmin(P[f - 6:f + 7, 16, 1])
    dx = np.nanmean(P[f + 15:f + 22, 16, 0]) - np.nanmean(P[f - 12:f - 6, 16, 0]); side = np.nanmean(P[f - 2:f + 3, 16, 0]) - hip_x
    return "OH" if wy < nose_y - 0.02 else "FH" if side > 0.04 else "BH" if side < -0.02 else ("FH" if dx < 0 else "BH")

G = []  # (video, frame, kind, sub)
for l in Path("work/kind/labels.txt").read_text().split("\n"):
    if l.strip():
        v, f, k = l.split(); G.append((v, int(f), k[:2], k))
seen = set()
session = Path(json.loads(Path("testset/labels/private_names.json").read_text(encoding="utf-8"))["wall_dir"]).name
for p in glob.glob(f"testset/archive/*/work/{glob.escape(session)}/labels.txt"):
    C = json.load(open(Path(p).parent / "cands.json"))
    for r in (x.split() for x in open(p) if x.strip() and not x.startswith("#")):
        if r[1] == "FH":
            c = C[int(r[0])]; key = (c["v"], round(c["t"], 1))
            if key not in seen: seen.add(key); G.append((c["v"], int(round(c["t"] * 60)) - 2, "FH", "FH"))
P = {}; W = {}; SZ = {}
for v in {g[0] for g in G}:
    d = Path("work/kind") / v; P[v] = np.load(d / "pose.npy").astype(float); w = d / "pose_world.npy"; W[v] = np.load(w).astype(float) if w.exists() else None
    SZ[v] = size(d / "proxy.mp4") if (d / "proxy.mp4").exists() else None  # None = old normalised coordinates
ids = {v: f"v{i + 1:02d}" for i, v in enumerate(sorted({g[0] for g in G}))}
K = ["FH", "BH", "SV", "OH"]
for off in (0, -2, 2):
    M = collections.defaultdict(collections.Counter); L = collections.Counter(); two = collections.Counter()
    for v, f, k, sub in G:
        r = classify(P[v], f + off, "R", W[v], SZ[v]); pred = r["kind"] if r["conf"] >= CONF_MIN else "?"
        M[k][pred] += 1; L[k] += 1
        if off == 0: M[k]["_old_" + legacy(P[v], f + off)] += 1
    print(f"\n== 擊球格偏移 {off:+d}（對標準答案幀）  列＝標準答案  行＝預測，? = 未分類")
    print("      " + "".join(f"{c:>6}" for c in K + ["?"]) + "     n  有結論正確率  未分類")
    tot = ok = unk = 0
    for k in K:
        n = L[k]
        if not n: continue
        row = [M[k][c] for c in K + ["?"]]; dec = n - M[k]["?"]; good = M[k][k]
        print(f"{k:>5} " + "".join(f"{x:>6}" for x in row) + f"  {n:>4}  {good}/{dec} ({100 * good / max(1, dec):.0f}%)  {100 * M[k]['?'] / n:.0f}%")
        tot += n; ok += good; unk += M[k]["?"]
    print(f"全部 n={tot}  有結論 {tot - unk} 對 {ok}（{100 * ok / max(1, tot - unk):.0f}%）  未分類 {100 * unk / tot:.0f}%")
    if off == 0:
        old = sum(M[k][f"_old_{k}"] for k in K); print(f"舊規則（無信心、無 SV）全部 {tot} 拍對 {old}（{100 * old / tot:.0f}%）；各類：" + "  ".join(f"{k} {M[k][f'_old_{k}']}/{L[k]}" for k in K if L[k]))
