# build_site.py — bundle every finished session for web/index.html (works from file://, no server needed).
# Reads web/sessions/<s>/strokes.json + notes.json (+ scores.json, reel.mp4 if present) and web/sessions/trend.json,
# writes web/sessions/<s>/data.js (per-stroke summary), web/sessions/<s>/pose/<id>.js (one stroke's frames/world, loaded on demand),
# web/sessions/manifest.js and web/sessions/trend.js.
import hashlib, json, re, sys
from check_findings import check
from common import ROOT, load, work
from platform_util import read_text, unlink, write_text
from trend import _score_set

S = ROOT / "web" / "sessions"
POSE = ("frames", "world")  # per-frame arrays: ~99% of the bytes, only needed for the stroke on screen


def src_fps(s):
    """Lowest source fps prep.sh recorded for the session's videos, or None when unknown (older work dirs)."""
    fps = [int(t) for p in work(s).glob("*/src_fps.txt") if (t := read_text(p).strip()).isdigit() and int(t) > 0]
    return min(fps) if fps else None


ids, ver, built, bad = [], {}, [], []
runs = [load(p) for p in S.glob("*/scores.json")]
for d in sorted(p for p in S.iterdir() if p.is_dir()):  # pass 1: build and check everything, write nothing
    if not (d / "strokes.json").exists():
        print(f"skip {d.name}: no strokes.json yet"); continue
    s = d.name; strokes = load(d / "strokes.json"); notes = load(d / "notes.json", {})
    vids = sorted({x["video"] for x in strokes})
    sc = load(d / "scores.json") if (d / "scores.json").exists() else None
    for g in (sc or {}).get("groups", []):
        g["score_set"] = _score_set(g)
    errs = check(notes, strokes, sc, runs=runs) if sc is not None else []  # {} still checks: cites that need scores fail
    bad += [f"{s}: {e}" for e in errs]
    sess = dict(id=s, label=notes.get("label", s[5:].replace("-", "/") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else s),
                checked=sc is not None, srcFps=src_fps(s),
                sub=notes.get("sub", f"{len(vids)} 支影片"), camera=notes.get("camera", ""), showOpen=notes.get("showOpen", False),
                date=notes.get("date", s), players=sorted({x.get("player") or "me" for x in strokes}), scores=sc,
                caveat=notes.get("caveat", ""), findings=notes.get("findings", []), presets=notes.get("presets", []),
                reel=f"sessions/{s}/reel.mp4" if (d / "reel.mp4").exists() else None,
                strokes=[{**{k: v for k, v in x.items() if k not in POSE}, "n": len(x["frames"]), "src": f"sessions/{s}/{x['src']}"} for x in strokes])
    n = len(strokes)
    for f in sess["findings"]:
        assert all(1 <= j[0] <= n for j in f.get("jump", [])), f"{s}: finding '{f['title']}' jumps past #{n}"
    built.append((d, s, sess, bool(notes)))  # strokes are reloaded in pass 2, so only one session's skeletons sit in memory
if bad: sys.exit("建議的數字對不上（docs/scoring.md §8），沒有寫出任何檔案：\n" + "\n".join(bad))
for d, s, sess, has_notes in built:  # pass 2: write
    strokes = load(d / "strokes.json"); n = len(strokes)
    js = "(window.SESSIONS=window.SESSIONS||[]).push(" + json.dumps(sess, ensure_ascii=False, separators=(",", ":")) + ");"
    (d / "pose").mkdir(exist_ok=True); h = hashlib.sha1(js.encode())
    for old in (d / "pose").glob("*.js"):  # a re-analysis with fewer strokes must not leave stale skeletons behind
        if old.stem not in {str(x["id"]) for x in strokes}: unlink(old)
    for x in strokes:  # pose/<id>.js hands one stroke's skeleton to the page via a <script> tag, so file:// works (no fetch)
        pj = f"POSE({json.dumps(s)},{x['id']}," + json.dumps({k: x.get(k) for k in POSE}, separators=(",", ":")) + ");"
        write_text(d / "pose" / f"{x['id']}.js", pj); h.update(pj.encode())
    write_text(d / "data.js", js); ver[s] = h.hexdigest()[:10]  # page loads data.js and pose/*.js with ?v=<hash> so browsers cache them
    ids.append(s); print(f"{s}: {n} strokes, {len(sess['findings'])} findings{', reel' if sess['reel'] else ''}{'' if has_notes else '  (no notes.json yet)'}")
write_text(S / "manifest.js", "window.SESSION_IDS=" + json.dumps(ids) + ";window.SESSION_VER=" + json.dumps(ver) + ";")
write_text(S / "trend.js", "window.TREND=" + json.dumps(load(S / "trend.json", []), ensure_ascii=False, separators=(",", ":")) + ";")
print("open web/index.html")
