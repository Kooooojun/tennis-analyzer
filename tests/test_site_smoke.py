# Run: .venv/bin/python tests/test_site_smoke.py   (plain asserts; cases follow testset/results/cross-platform_pred.md)
# Builds a synthetic session (Chinese name and notes, no real data) with build_site.py in a scratch copy of tools/, under the
# default locale and again with a cp1252 stdout, and checks data.js is UTF-8 with LF only and the ?v= hash matches the file bytes.
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent
T = Path(tempfile.mkdtemp()) / "根目錄"; shutil.copytree(R / "tools", T / "tools", ignore=shutil.ignore_patterns("__pycache__"))
s = "練習-1"; D = T / "web" / "sessions" / s; D.mkdir(parents=True); (T / "work" / s).mkdir(parents=True)
fr = [[[0.5, 0.5, 0.9]] * 17] * 3
strokes = [dict(id=i, video="v1", src="clips/s.mp4", frames=fr, world=fr, kind="FH", player="小明") for i in (1, 2)]
(D / "strokes.json").write_text(json.dumps(strokes, ensure_ascii=False), encoding="utf-8")
(D / "notes.json").write_text(json.dumps(dict(label="中文標題", caveat="備註：只有合成資料", findings=[dict(title="重心", text="膝蓋再彎一點")]),
                                         ensure_ascii=False), encoding="utf-8")

for env in ({}, {"PYTHONIOENCODING": "cp1252"}):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}; e.update(env)
    r = subprocess.run([sys.executable, str(T / "tools" / "build_site.py")], capture_output=True, env=e)
    assert r.returncode == 0, (env, r.stderr.decode("utf-8", "replace"))
    b = (D / "data.js").read_bytes()
    assert b"\r" not in b
    js = b.decode("utf-8"); assert "中文標題" in js and "膝蓋再彎一點" in js and "小明" in js
    h = hashlib.sha1(b)
    for x in strokes: h.update((D / "pose" / f"{x['id']}.js").read_bytes())
    man = (T / "web" / "sessions" / "manifest.js").read_text(encoding="utf-8")
    ver = json.loads(re.search(r"SESSION_VER=(\{.*?\});", man).group(1))
    assert ver[s] == h.hexdigest()[:10], (ver, h.hexdigest())
shutil.rmtree(T.parent)
print("ok")
