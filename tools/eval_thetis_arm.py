"""手臂檢查對照：用眼睛標的 SV 40 拍／單手反拍 28 拍（資料集：THETIS；標註表只放在報告彙總，不含影格）對照 arm_checks 輸出。
用法：.venv/bin/python tools/eval_thetis_arm.py <結果檔 res_*.json 的 mode 名，例如 interp60REA>  （抽樣清單 work/thetis/arm_sample.json 由本機生成）"""
import json, sys, collections
import os; W = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "thetis")
# 眼睛標註（拍號 = 抽樣清單順序 1 起算）：直 / 彎 / ?＝看不出來。低解析度三格小圖判讀，只有粗略可信度。
_L = json.load(open(f"{W}/arm_eye_labels.json", encoding="utf-8")); SV, BH = _L["SV"], _L["BH"]  # 本機眼睛標註（不進 git）
assert len(SV) == 40 and len(BH) == 28
samp = json.load(open(f"{W}/arm_sample.json", encoding="utf-8"))
for mode in sys.argv[1:]:
    rows = {r["name"]: r for r in json.load(open(f"{W}/res_{mode}_first.json", encoding="utf-8"))["rows"]}
    print(f"\n### {mode}")
    for lab, names, key, eye in (("發球 serve_arm_straight", samp["SV"], "serve_arm_straight", SV), ("單手反拍 bh_elbow_ok", samp["BH"], "bh_elbow_ok", BH)):
        c = collections.Counter(); beg = collections.Counter()
        for n, e in zip(names, eye):
            a = rows[n].get("arm", {}).get(key); p = {True: "直", False: "彎", None: "?"}[a]
            c[(e, p)] += 1; beg[(rows[n]["person"] <= 31, e, p)] += 1
        print(f"\n{lab}（{len(names)} 拍；列 = 眼睛、欄 = 程式）\n\n| 眼睛＼程式 | 直 | 彎 | ? |\n|---|---|---|---|")
        for e in "直彎?":
            print(f"| {e} | " + " | ".join(str(c[(e, p)]) for p in "直彎?") + " |")
        dec = [(e, p) for (e, p), k in c.items() for _ in range(k) if e != "?" and p != "?"]
        ok = sum(e == p for e, p in dec); lab_n = sum(c[(e, p)] for e in "直彎" for p in "直彎?")
        print(f"\n眼睛有標直/彎 {lab_n} 拍；程式有結論且眼睛有標 {len(dec)} 拍，一致 {ok}（{ok / max(1, len(dec)):.0%}）；程式回 ? 共 {sum(k for (e, p), k in c.items() if p == '?')} 拍")
        print("初學者眼睛標彎／程式判彎：", sum(k for (b, e, p), k in beg.items() if b and e == "彎"), "／", sum(k for (b, e, p), k in beg.items() if b and p == "彎"))
