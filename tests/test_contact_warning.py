"""接觸格品質原因須出現在兩種影片說明，且不誤稱膝角差異。"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from annotate import stroke_info, F, PANEL_W

MESSAGE = "擊球格不可信，這拍不量"
base = dict(no=1, kind="FH", knee=None, knee3d=None, contact_h=None)
_, lines = stroke_info({**base, "knee_warn": True, "knee_warn_why": "contact"})
assert [text for text, _ in lines] == [MESSAGE], lines
assert F(24).getlength(MESSAGE) <= PANEL_W - 20
assert stroke_info(base)[1] == []
assert stroke_info({**base, "knee_warn": True, "knee_warn_why": "gap"})[1][0][0] == "這拍角度不準"

# highlights 是啟動即編碼的腳本；只載入實際繪字函式，避免執行影片輸出。
tree = ast.parse((ROOT / "tools" / "highlights.py").read_text(encoding="utf-8"))
label = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "label")
ns = dict(F=lambda _: None, INK=None, BAD=None)
exec(compile(ast.Module(body=[label], type_ignores=[]), "highlights.py", "exec"), ns)


class Text:
    def __init__(self): self.lines = []
    def text(self, xy, text, **kwargs): self.lines.append(text)


for reason, message in [("contact", MESSAGE), ("gap", "這拍角度不準"), ("view", "這拍角度不準")]:
    draw = Text()
    ns["label"](draw, 0, 0, {**base, "knee_warn": True, "knee_warn_why": reason}, "合成拍", None)
    assert draw.lines == ["合成拍", message], draw.lines
print("contact warning video text OK")
