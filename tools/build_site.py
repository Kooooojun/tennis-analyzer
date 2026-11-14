# build_site.py — bundle every finished session for web/index.html (works from file://, no server needed).
# Reads web/sessions/<s>/strokes.json + notes.json (+ reel.mp4 if present), writes web/sessions/<s>/data.js and web/sessions/manifest.js.
import json
from common import ROOT, load

S = ROOT / "web" / "sessions"
ids = []
for d in sorted(p for p in S.iterdir() if p.is_dir()):
    if not (d / "strokes.json").exists():
        print(f"skip {d.name}: no strokes.json yet"); continue
    s = d.name; strokes = load(d / "strokes.json"); notes = load(d / "notes.json", {})
    vids = sorted({x["video"] for x in strokes})
    sess = dict(id=s, label=notes.get("label", s[5:].replace("-", "/") if len(s) == 10 else s),
                sub=notes.get("sub", f"{len(vids)} 支影片"), camera=notes.get("camera", ""), showOpen=notes.get("showOpen", False),
                caveat=notes.get("caveat", ""), findings=notes.get("findings", []), presets=notes.get("presets", []),
                reel=f"sessions/{s}/reel.mp4" if (d / "reel.mp4").exists() else None,
                strokes=[{**x, "src": f"sessions/{s}/{x['src']}"} for x in strokes])
    n = len(strokes)
    for f in sess["findings"]:
        assert all(1 <= j[0] <= n for j in f.get("jump", [])), f"{s}: finding '{f['title']}' jumps past #{n}"
    (d / "data.js").write_text("(window.SESSIONS=window.SESSIONS||[]).push(" + json.dumps(sess, ensure_ascii=False, separators=(",", ":")) + ");")
    ids.append(s); print(f"{s}: {n} strokes, {len(sess['findings'])} findings{', reel' if sess['reel'] else ''}{'' if notes else '  (no notes.json yet)'}")
(S / "manifest.js").write_text("window.SESSION_IDS=" + json.dumps(ids) + ";")
print("open web/index.html")
