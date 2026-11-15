# build_site.py — bundle every finished session for web/index.html (works from file://, no server needed).
# Reads web/sessions/<s>/strokes.json + notes.json (+ scores.json, reel.mp4 if present) and web/sessions/trend.json,
# writes web/sessions/<s>/data.js, web/sessions/manifest.js and web/sessions/trend.js.
import hashlib, json
from common import ROOT, load

S = ROOT / "web" / "sessions"
ids, ver = [], {}
for d in sorted(p for p in S.iterdir() if p.is_dir()):
    if not (d / "strokes.json").exists():
        print(f"skip {d.name}: no strokes.json yet"); continue
    s = d.name; strokes = load(d / "strokes.json"); notes = load(d / "notes.json", {})
    vids = sorted({x["video"] for x in strokes})
    sess = dict(id=s, label=notes.get("label", s[5:].replace("-", "/") if len(s) == 10 else s),
                sub=notes.get("sub", f"{len(vids)} 支影片"), camera=notes.get("camera", ""), showOpen=notes.get("showOpen", False),
                date=notes.get("date", s), players=sorted({x.get("player") or "me" for x in strokes}), scores=load(d / "scores.json") if (d / "scores.json").exists() else None,
                caveat=notes.get("caveat", ""), findings=notes.get("findings", []), presets=notes.get("presets", []),
                reel=f"sessions/{s}/reel.mp4" if (d / "reel.mp4").exists() else None,
                strokes=[{**x, "src": f"sessions/{s}/{x['src']}"} for x in strokes])
    n = len(strokes)
    for f in sess["findings"]:
        assert all(1 <= j[0] <= n for j in f.get("jump", [])), f"{s}: finding '{f['title']}' jumps past #{n}"
    js = "(window.SESSIONS=window.SESSIONS||[]).push(" + json.dumps(sess, ensure_ascii=False, separators=(",", ":")) + ");"
    (d / "data.js").write_text(js); ver[s] = hashlib.sha1(js.encode()).hexdigest()[:10]  # page loads data.js?v=<hash> so browsers cache it
    ids.append(s); print(f"{s}: {n} strokes, {len(sess['findings'])} findings{', reel' if sess['reel'] else ''}{'' if notes else '  (no notes.json yet)'}")
(S / "manifest.js").write_text("window.SESSION_IDS=" + json.dumps(ids) + ";window.SESSION_VER=" + json.dumps(ver) + ";")
(S / "trend.js").write_text("window.TREND=" + json.dumps(load(S / "trend.json", []), ensure_ascii=False, separators=(",", ":")) + ";")
print("open web/index.html")
