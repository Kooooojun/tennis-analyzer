# 場次級 profiles：work/<s>/profiles.json 優先，逐名字回退全域 work/profiles.json。
# 用法（repo 根目錄）：.venv/bin/python tests/test_profiles.py
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from profiles import load_session_profiles
from common import profile_for

root = Path(tempfile.mkdtemp())
def put(rel, text):
    p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(text.encode("utf-8")); return p
R, L = {"hand": "R", "backhand": "two"}, {"hand": "L", "backhand": "one"}
glob = lambda **k: put("work/profiles.json", json.dumps(k))
sess = lambda s, **k: put(f"work/{s}/profiles.json", json.dumps(k))

# 沒有任何檔 = 現況（空）
assert load_session_profiles("a", root) == ({}, {})
# 只有全域檔 = 現況
glob(me=R, bob=L); P, W = load_session_profiles("a", root)
assert P == {"me": R, "bob": L} and set(W.values()) == {"work/profiles.json"}, (P, W)
# 場次檔優先；沒列的名字逐名字回退（不整批當作沒有）
sess("a", me=L); P, W = load_session_profiles("a", root)
assert P["me"] == L and P["bob"] == L and W == {"me": "work/a/profiles.json", "bob": "work/profiles.json"}, (P, W)
# 兩場次同名 me 不同手：各自正確，互不污染
sess("b", me=R); assert profile_for(load_session_profiles("a", root)[0], "me")["hand"] == "L"
assert profile_for(load_session_profiles("b", root)[0], "me")["hand"] == "R"
# 別的場次的檔不影響沒有場次檔的場次
assert load_session_profiles("c", root)[0] == {"me": R, "bob": L}
# 壞格式一律 ValueError（含編碼壞、最上層不是物件），不當 R
put("work/bad1/profiles.json", "{not json")
put("work/bad2/profiles.json", "[1,2]")
(root / "work/bad3").mkdir(); (root / "work/bad3/profiles.json").write_bytes(b"\xff\xfe\x00bad")
for s in ("bad1", "bad2", "bad3"):
    try: load_session_profiles(s, root); raise AssertionError(f"{s} 應該報錯")
    except (ValueError, SystemExit): pass  # 編碼壞時 read_text 直接 sys.exit，一樣不靜默
sess("bad4", me={"hand": "X", "backhand": "two"})  # 值不合法：載入時過，取用時 profile_for 報錯（沿用既有行為）
try: profile_for(load_session_profiles("bad4", root)[0], "me"); raise AssertionError("bad hand")
except ValueError: pass
print("profiles OK")
