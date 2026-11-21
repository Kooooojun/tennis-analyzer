# build_site.py — bundle every finished session for web/index.html (works from file://, no server needed).
# Reads web/sessions/<s>/strokes.json + notes.json (+ scores.json, reel.mp4 if present) and web/sessions/trend.json,
# writes web/sessions/<s>/data.js (per-stroke summary), web/sessions/<s>/pose/<id>.js (one stroke's frames/world, loaded on demand),
# web/sessions/manifest.js and web/sessions/trend.js. data.js also carries methodVer: prep's work/<s>/<video>/versions.txt (package, model, skeleton
# frame counts) folded for the page's method note; null for work dirs made before versions.txt existed (the page says 未記錄).
import hashlib, json, re, sys
from check_findings import check
from common import ROOT, load, src_fps, work
from platform_util import read_text, unlink, write_text
from trend import _score_set

S = ROOT / "web" / "sessions"
POSE = ("frames", "world")  # per-frame arrays: ~99% of the bytes, only needed for the stroke on screen


def method_ver(s):
    """prep's work/<s>/<video>/versions.txt of every video, folded into one dict for the page's method note.
    None when no video has a readable one (old work dirs: the page says 未記錄); `recorded` of `videos` folders had it."""
    try: names = load(work(s) / "videos.json", False)  # the session's own videos; a folder left behind by a removed video does not count
    except (OSError, ValueError): names = None  # empty or broken file: count the folders instead, never stop the whole build
    dirs = [work(s) / n for n in names if (work(s) / n).is_dir()] if isinstance(names, list) else [p for p in work(s).glob("*") if p.is_dir()]; recs = []
    for p in dirs:
        f = p / "versions.txt"
        kv = dict(l.split("=", 1) for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if "=" in l) if f.is_file() else {}  # never exits: a bad file is just "not recorded"
        if kv.get("mediapipe") and all(kv.get(k, "").isdecimal() for k in ("pose_frames", "pose_detected", "pose_interpolated")): recs.append(kv)
    if not recs: return None
    same = lambda k: " / ".join(sorted({r[k] for r in recs if r.get(k)}))  # videos made with different versions list every one
    total = lambda k: sum(int(r[k]) for r in recs)
    return dict(mediapipe=same("mediapipe"), model=same("pose_model"), sha256=same("pose_model_sha256"), url=same("pose_model_url"), method=same("pose_method"),
                frames=total("pose_frames"), detected=total("pose_detected"), interpolated=total("pose_interpolated"), videos=len(dirs), recorded=len(recs))


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
                checked=sc is not None, srcFps=src_fps(s), methodVer=method_ver(s),
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
