# assemble.py 的標註檢查（純邏輯）：labels.txt 記著它對應的 cands.json 指紋，不符要報錯；'@' 改名後用新名字的手。
# 用法（repo 根目錄）：.venv/bin/python tests/test_assemble.py
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from assemble import cands_fp, read_labels, player_of, bulk_warning, BULK_N

d = Path(tempfile.mkdtemp()); C = [dict(v="a", t=1.0, player="black"), dict(v="a", t=2.0, player="black")]
(d / "cands.json").write_text(json.dumps(C))
fp = cands_fp(d / "cands.json")
(d / "labels.txt").write_text(f"# header\n# cands {fp}\n0 FH rally\n1 x\n")
rows = read_labels(d, C); assert [r[1] for r in rows] == ["FH", "x"], rows

C2 = [dict(v="a", t=1.5, player="black"), dict(v="a", t=2.0, player="black")]  # 重跑 candidates：數量一樣、內容不同
(d / "cands.json").write_text(json.dumps(C2))
try: read_labels(d, C2); raise AssertionError("mismatch not caught")
except SystemExit as e: assert "candidates" in str(e) and "labels.txt" in str(e), e

(d / "labels.txt").write_text("0 FH rally\n1 x\n")  # 舊 labels.txt 沒有指紋：只警告，照跑
assert len(read_labels(d, C2)) == 2

who = {0: "white", 1: None}  # 0 用 '@white' 改名
assert player_of(0, who, C2) == "white" and player_of(1, who, C2) == "black"
# 整批照收警告：沒有任何 x、且同一 kind >= BULK_N 拍才警告；有一行 x 或 kind 不夠多就不警告；沒有註解行的舊 labels 也照常
row = lambda i, k: [str(i), k, "rally"]
assert BULK_N == 10
assert bulk_warning([row(i, "FH") for i in range(10)]) and "FH" in bulk_warning([row(i, "FH") for i in range(10)])
assert bulk_warning([row(i, "FH") for i in range(9)] + [row(9, "BH")]) is None
assert bulk_warning([row(i, "FH") for i in range(20)] + [["20", "x"]]) is None
assert bulk_warning(rows) is None  # 上面的舊 labels（有 x）
print("assemble labels OK")
