# refine.py <session> — strokes_raw.json + work/<s>/refine.json -> web/sessions/<s>/strokes.json
# Hit times in strokes_raw.json already have the per-video sound lag taken out (events.py estimate_lag); refine.json moves each contact to the right frame
# (picked by eye from strip.py), relabels, and drops false strokes. Numbers in refine.json are raw stroke numbers (#1 = s00).
#   {"default_off": -2, "off": {"5": -21}, "set": {"65": {"drill": "rally"}}, "drop": [39, 50]}
# Always starts from strokes_raw.json, so re-running with an edited refine.json is safe.
from common import session, work, web, load, save
from metrics import measure_clip, arm_checks

s = session(); D = web(s); C = load(work(s) / "refine.json", {})
d = load(D / "strokes_raw.json")
hand_of = lambda r: C.get("hand", r.get("hand", "R")) if r.get("hand_guess") or not r.get("hand") else r["hand"]  # per-stroke (work/profiles.json via assemble); refine.json "hand" is the fallback for old strokes
err = max(abs((measure_clip(r["frames"], r["contact"], r.get("size"), r.get("world"), hand_of(r))[k] or 0) - r[k]) for r in d for k in ("knee", "knee3d", "contact_h", "contact_fwd", "prep", "elbow") if r.get(k) is not None)
print(f"clip vs full-video metrics at the raw contact: max diff {err:.1f} (a few degrees is coordinate rounding; much more means strokes_raw.json is stale)")
out = []
for r in d:
    no = r["id"] + 1
    if no in C.get("drop", []): continue
    df = C.get("off", {}).get(str(no), C.get("default_off", 0)); c = r["contact"] + df
    r.update(C.get("set", {}).get(str(no), {}))
    old = r["contact_h"]; r.update(measure_clip(r["frames"], c, r.get("size"), r.get("world"), hand_of(r))); r["contact"] = c
    r.update(arm_checks(r["frames"], c, r.get("size"), r.get("world"), r["kind"], hand_of(r), {"one": True, "two": False}.get(r.get("backhand"), C.get("one_hand_bh") is True)))  # profile first; refine.json "hand" / "one_hand_bh" only for strokes made before profiles
    r["t"] = round(r["t"] + df / 60, 3)
    m, sec = divmod(r["t"], 60); r["clock"] = f"{r['video']}·{int(m)}:{sec:04.1f}"
    if df != C.get("default_off", 0) or str(no) in C.get("set", {}):
        print(f"raw #{no:02d} {df:+d} {r['kind']} {r.get('drill')} h {round(old * 100)} -> {round(r['contact_h'] * 100)}  knee {r['knee']}")
    out.append(r)
for i, r in enumerate(out): r["id"] = i
save(D / "strokes.json", out, compact=True)
print(len(d), "->", len(out), "strokes. Final numbering (#01..) is what notes.json and reel.json use.")
