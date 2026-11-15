# assemble.py <session> — labels.txt + cands.json -> work/<s>/strokes_all.json (one entry per labelled stroke, with metrics)
import collections, json, sys, numpy as np
from common import session, work, load, save, size, load_profiles, profile_for
from metrics import measure_full, guess_hand

KINDS = {"FH", "BH", "SV", "OH"}; DRILLS = {"feed", "rally", "high", "unsure", "-"}
s = session(); Wd = work(s); C = load(Wd / "cands.json")
rows = [l.split() for l in (Wd / "labels.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
bad = [r for r in rows if not (r[0].isdigit() and int(r[0]) < len(C)) or not (r[1] == "x" or r[1] == "SV" or (r[1] in KINDS and len(r) > 2 and r[2] in DRILLS))]
if bad or len(rows) != len(C) or sorted(int(r[0]) for r in rows) != list(range(len(C))):
    sys.exit(f"labels.txt must have one line per candidate 0..{len(C) - 1}: '<idx> <FH|BH|SV|OH|x> <feed|rally|high|unsure|->' (text after that is ignored). bad lines: {bad[:5]}")

P = {}; WD = {}; SZ = {}; out = []
def pose(c):  # cached pose + proxy size of the candidate's video
    if c["v"] not in P: P[c["v"]] = np.load(Wd / c["v"] / "pose.npy").astype(float); SZ[c["v"]] = size(Wd / c["v"] / "proxy.mp4")
# Racket hand / backhand type per player: work/profiles.json first, else guessed from wrist speed in this session's video (flagged)
PROF = load_profiles(); H = {}; vids = {}
for r in rows:
    if r[1] != "x": c = C[int(r[0])]; pose(c); vids.setdefault(c.get("player", "me"), {}).setdefault(c["v"], []).append(c["t"])
for name, cs in vids.items():
    p = profile_for(PROF, name)
    if p: H[name] = dict(hand=p["hand"], hand_guess=False, backhand=p["backhand"]); print(f"player {name}: hand {p['hand']}, backhand {p['backhand']} (work/profiles.json)")
    else:
        g, ratio = guess_hand([P[v] for v in cs], SZ[next(iter(cs))], list(cs.values())); H[name] = dict(hand=g or "R", hand_guess=True, backhand=None)
        print(f"player {name}: hand {g or 'R'} GUESSED ({'wrist speed ratio %s' % ratio if g else 'too little video, defaulted to R'}{', UNSURE' if ratio and ratio < 1.15 else ''}). Ask the user for the hand and backhand type, then write work/profiles.json: " + json.dumps({name: {"hand": g or "R", "backhand": "two"}}))
for r in sorted(rows, key=lambda r: int(r[0])):
    if r[1] == "x": continue
    c = C[int(r[0])]; pose(c); h = H[c.get("player", "me")]
    if c["v"] not in WD:
        wp = Wd / c["v"] / "pose_world.npy"; WD[c["v"]] = np.load(wp).astype(float) if wp.exists() else None  # old sessions: no 3D
    m = measure_full(P[c["v"]], c["t"], SZ[c["v"]], WD[c["v"]], h["hand"])
    out.append(dict(t=round(c["t"], 3), video=c["v"], vn=c["vn"], cand=int(r[0]), arc=round(c["arc"], 2),
                    size=SZ[c["v"]], **h, kind=r[1], drill=None if r[1] == "SV" or r[2] == "-" else r[2], **m))
out.sort(key=lambda x: (x["vn"], x["t"]))
save(Wd / "strokes_all.json", out)
print(len(out), "strokes", dict(collections.Counter((x["kind"], x["drill"]) for x in out)))
print("auto-kind disagreements (worth a second look):", [x["cand"] for x in out if x["kind"] != x["auto_kind"]])
