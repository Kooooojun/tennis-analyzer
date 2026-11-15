# assemble.py 的標註檢查（純邏輯）：labels.txt 記著它對應的 cands.json 指紋，不符要報錯；'@' 改名後用新名字的手。
# 用法（repo 根目錄）：.venv/bin/python tests/test_assemble.py
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from assemble import cands_fp, read_labels, player_of, bulk_warning, BULK_N, rename_warning

d = Path(tempfile.mkdtemp()); C = [dict(v="a", t=1.0, player="black"), dict(v="a", t=2.0, player="black")]
(d / "cands.json").write_text(json.dumps(C), encoding="utf-8", newline="\n")
fp = cands_fp(d / "cands.json")
(d / "labels.txt").write_text(f"# header\n# cands {fp}\n0 FH rally\n1 x\n", encoding="utf-8", newline="\n")
rows = read_labels(d, C); assert [r[1] for r in rows] == ["FH", "x"], rows

C2 = [dict(v="a", t=1.5, player="black"), dict(v="a", t=2.0, player="black")]  # 重跑 candidates：數量一樣、內容不同
(d / "cands.json").write_text(json.dumps(C2), encoding="utf-8", newline="\n")
try: read_labels(d, C2); raise AssertionError("mismatch not caught")
except SystemExit as e: assert "candidates" in str(e) and "labels.txt" in str(e), e

(d / "labels.txt").write_text("0 FH rally\n1 x\n", encoding="utf-8", newline="\n")  # 舊 labels.txt 沒有指紋：只警告，照跑
assert len(read_labels(d, C2)) == 2

who = {0: "white", 1: None}  # 0 用 '@white' 改名
assert player_of(0, who, C2) == "white" and player_of(1, who, C2) == "black"
# 整批照收警告：>= BULK_N 行且 x 不到 3% 才警告（隨手寫一行 x 繞不過）；少於 BULK_N 行或 x 夠多就不警告；文字註明全是真擊球時可忽略
row = lambda i, k: [str(i), k, "rally"]
assert BULK_N == 10
w = bulk_warning([row(i, "FH") for i in range(10)]); assert w and "ignore" in w, w
assert bulk_warning([row(i, "FH") for i in range(9)]) is None  # 太少行
assert bulk_warning([row(i, "FH") for i in range(40)] + [["40", "x"]])  # 1/41 = 2.4% < 3%：仍警告
assert bulk_warning([row(i, "FH") for i in range(20)] + [["20", "x"]]) is None  # 1/21 = 4.8%
assert bulk_warning([row(i, "FH") for i in range(5)] + [row(i, "BH") for i in range(5, 10)])  # 混合拍種也算
assert bulk_warning(rows) is None  # 上面的舊 labels（2 行，有 x）
# 改名警告：@名字 換成另一人、預填用的手（cands 的 hand）和新名字的手不同、且拍種是 FH／BH 才警告一次
Cr = [dict(player="p1", hand="R"), dict(player="p1", hand="R"), dict(player="p1", hand=None), dict(player="p1", hand="R"), dict(player="p1", hand="R")]
rr = lambda i, k: [str(i), k, "rally"]
hands = {"p1": "R", "p2": "L", "p3": "R"}
w = rename_warning([rr(0, "FH"), rr(1, "BH")], Cr, {0: "p2", 1: "p2"}, hands); assert w and "0, 1" in w, w  # 異手：警告，一行列全部
assert rename_warning([rr(0, "FH")], Cr, {0: "p3"}, hands) is None  # 同手改名
assert rename_warning([rr(2, "FH")], Cr, {2: "p2"}, hands) is None  # 沒預填（cands 沒有手）
assert rename_warning([rr(3, "x")], Cr, {3: "p2"}, hands) is None and rename_warning([rr(3, "SV")], Cr, {3: "p2"}, hands) is None  # x、SV 不警告
assert rename_warning([rr(4, "FH")], Cr, {4: None}, hands) is None and rename_warning([rr(4, "FH")], Cr, {4: "p1"}, hands) is None  # 沒改名
assert rename_warning([rr(0, "FH")], [dict(player="p2", hand="R")], {0: "p2"}, hands) is None  # @同名（沒改名）不警告，即使 cands 的手與現在不同
print("assemble labels OK")
