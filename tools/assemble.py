# assemble.py <session> — labels.txt + cands.json -> work/<s>/strokes_all.json (one entry per labelled stroke, with metrics)
import collections, json, sys, numpy as np
from common import session, work, load, save, size, track_file, players, load_profiles, profile_for
from metrics import measure_full, guess_hand

KINDS = {"FH", "BH", "SV", "OH"}; DRILLS = {"feed", "rally", "high", "unsure", "-"}
s = session(); Wd = work(s); C = load(Wd / "cands.json")
rows = [l.split() for l in (Wd / "labels.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
bad = [r for r in rows if not (r[0].isdigit() and int(r[0]) < len(C)) or not (r[1] == "x" or r[1] == "SV" or (r[1] in KINDS and len(r) > 2 and r[2] in DRILLS))]
if bad or len(rows) != len(C) or sorted(int(r[0]) for r in rows) != list(range(len(C))):
    sys.exit(f"labels.txt must have one line per candidate 0..{len(C) - 1}: '<idx> <FH|BH|SV|OH|x> <feed|rally|high|unsure|->' (text after that is ignored). bad lines: {bad[:5]}")

NAMES = set(players(s).values()) - {"x"} or {"me"}
who = {int(r[0]): next((w[1:] for w in r[2:4] if w.startswith("@")), None) for r in rows}  # '@name' after kind/drill corrects the prefilled player
if typo := [(i, n) for i, n in who.items() if n is not None and n not in NAMES]:
    sys.exit(f"labels.txt names a player that is not in players.txt {sorted(NAMES)}: {typo[:5]}")

P = {}; WD = {}; SZ = {}; out = []
def pose(c):  # cached pose of the track that swung ('@' only renames, it keeps that body) + proxy size; key (video, track)
    key = (c["v"], c.get("track", 0))
    if key not in P:
        P[key] = np.load(track_file(Wd / c["v"], "pose", key[1])).astype(float)
        wp = track_file(Wd / c["v"], "pose_world", key[1]); WD[key] = np.load(wp).astype(float) if wp.exists() else None  # old sessions: no 3D
    if c["v"] not in SZ: SZ[c["v"]] = size(Wd / c["v"] / "proxy.mp4")
    return key
name = lambda i: who[i] or C[i].get("player") or "me"  # null / missing player = me
# Racket hand / backhand type per player: work/profiles.json first, else guessed from wrist speed in this session's video (flagged)
PROF = load_profiles(); H = {}; vids = {}
for r in rows:
    if r[1] != "x": c = C[int(r[0])]; vids.setdefault(name(int(r[0])), {}).setdefault(pose(c), []).append(c["t"])
for nm, cs in vids.items():
    p = profile_for(PROF, nm)
    if p: H[nm] = dict(hand=p["hand"], hand_guess=False, backhand=p["backhand"]); print(f"player {nm}: hand {p['hand']}, backhand {p['backhand']} (work/profiles.json)")
    else:
        g, ratio = guess_hand([P[k] for k in cs], [SZ[k[0]] for k in cs], list(cs.values())); H[nm] = dict(hand=g or "R", hand_guess=True, backhand=None)
        print(f"player {nm}: hand {g or 'R'} GUESSED ({'wrist speed ratio %s' % ratio if g else 'too little video, defaulted to R'}{', UNSURE' if ratio and ratio < 1.15 else ''}). Ask the user for the hand and backhand type, then write work/profiles.json: " + json.dumps({nm: {"hand": g or "R", "backhand": "two"}}))
for r in sorted(rows, key=lambda r: int(r[0])):
    if r[1] == "x": continue
    i = int(r[0]); c = C[i]; key = pose(c); h = H[name(i)]
    m = measure_full(P[key], c["t"], SZ[c["v"]], WD[key], h["hand"])
    out.append(dict(t=round(c["t"], 3), video=c["v"], vn=c["vn"], cand=i, arc=round(c["arc"], 2), track=key[1], player=name(i),
                    size=SZ[c["v"]], **h, kind=r[1], drill=None if r[1] == "SV" or r[2] == "-" else r[2], **m))
out.sort(key=lambda x: (x["vn"], x["t"]))
save(Wd / "strokes_all.json", out)
print(len(out), "strokes", dict(collections.Counter((x["player"], x["kind"], x["drill"]) for x in out)))
print("auto-kind disagreements (worth a second look):", [x["cand"] for x in out if x["kind"] != x["auto_kind"]])
