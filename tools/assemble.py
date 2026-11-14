# assemble.py <session> — labels.txt + cands.json -> work/<s>/strokes_all.json (one entry per labelled stroke, with metrics)
import collections, sys, numpy as np
from common import session, work, load, save, size, track_file, players
from metrics import measure_full

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

P = {}; SZ = {}; out = []
for r in sorted(rows, key=lambda r: int(r[0])):
    if r[1] == "x": continue
    c = C[int(r[0])]; k = c.get("track", 0); key = (c["v"], k)  # the track that swung; '@' only renames, it keeps that body
    if key not in P: P[key] = np.load(track_file(Wd / c["v"], "pose", k)).astype(float)
    if c["v"] not in SZ: SZ[c["v"]] = size(Wd / c["v"] / "proxy.mp4")
    m = measure_full(P[key], c["t"], SZ[c["v"]])
    out.append(dict(t=round(c["t"], 3), video=c["v"], vn=c["vn"], cand=int(r[0]), arc=round(c["arc"], 2), track=k,
                    player=who[int(r[0])] or c.get("player", "me"),
                    size=SZ[c["v"]], kind=r[1], drill=None if r[1] == "SV" or r[2] == "-" else r[2], **m))
out.sort(key=lambda x: (x["vn"], x["t"]))
save(Wd / "strokes_all.json", out)
print(len(out), "strokes", dict(collections.Counter((x["player"], x["kind"], x["drill"]) for x in out)))
print("auto-kind disagreements (worth a second look):", [x["cand"] for x in out if x["kind"] != x["auto_kind"]])
