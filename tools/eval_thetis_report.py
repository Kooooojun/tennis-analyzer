"""res_<mode>_<which>.json -> 拍種混淆矩陣與準確率（markdown）。用法：.venv/bin/python tools/eval_thetis_report.py <mode> [first|all]"""
import json, sys, collections
import os; R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "thetis")
mode = sys.argv[1]; which = sys.argv[2] if len(sys.argv) > 2 else "first"
rows = json.load(open(f"{R}/res_{mode}_{which}.json"))["rows"]
PRED = ["FH", "BH", "SV", "OH", "?"]; GRP = ["FH", "BH", "SV", "OH", "FHV", "BHV"]
OK = dict(FH="FH", BH="BH", SV="SV", OH="OH", FHV="FH", BHV="BH")  # 兩種 volley 只看它們被分到哪裡；「對」當作同側的拍


def table(rs, title):
    print(f"\n#### {title}（{len(rs)} 支）\n\n| 真實＼預測 | " + " | ".join(PRED) + " | n | 正確率（含?） | 正確率（有結論） | ?比例 |\n|---|" + "---|" * (len(PRED) + 4))
    for g in GRP:
        a = [r for r in rs if r["group"] == g]
        if not a: continue
        c = collections.Counter(r["kind"] for r in a); n = len(a); ok = sum(c[OK[g]] for _ in [0]); dec = n - c["?"]
        print(f"| {g} | " + " | ".join(str(c[p]) for p in PRED) + f" | {n} | {ok / n:.0%} | {ok / dec:.0%} | {c['?'] / n:.0%} |" if dec else f"| {g} | all ? |")
    main = [r for r in rs if r["group"] in ("FH", "BH", "SV", "OH")]
    if main:
        ok = sum(r["kind"] == r["group"] for r in main); q = sum(r["kind"] == "?" for r in main)
        print(f"\n四大類合計：正確 {ok}/{len(main)} = {ok / len(main):.0%}（含?）；有結論 {ok}/{len(main) - q} = {ok / max(1, len(main) - q):.0%}；? {q / len(main):.0%}")


print(f"## 模式 {mode}（{which}）")
table(rows, "全部"); table([r for r in rows if r["person"] <= 31], "初學者 p1–p31"); table([r for r in rows if r["person"] >= 32], "高手 p32–p55")
print("\n#### 各動作（拍種預測分佈）\n\n| 動作 | " + " | ".join(PRED) + " | n |\n|---|" + "---|" * 6)
acts = collections.defaultdict(list)
for r in rows: acts[r["action"]].append(r["kind"])
for a, ks in sorted(acts.items()):
    c = collections.Counter(ks); print(f"| {a} | " + " | ".join(str(c[p]) for p in PRED) + f" | {len(ks)} |")
