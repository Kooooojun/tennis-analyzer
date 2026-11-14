# assemble.py <session> — labels.txt + cands.json -> work/<s>/strokes_all.json (one entry per labelled stroke, with metrics)
import collections, sys, numpy as np
from common import session, work, load, save
from metrics import measure_full

KINDS = {"FH", "BH", "SV", "OH"}; DRILLS = {"feed", "rally", "high", "unsure", "-"}
s = session(); Wd = work(s); C = load(Wd / "cands.json")
rows = [l.split() for l in (Wd / "labels.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
bad = [r for r in rows if not (r[0].isdigit() and int(r[0]) < len(C)) or not (r[1] == "x" or r[1] == "SV" or (r[1] in KINDS and len(r) > 2 and r[2] in DRILLS))]
if bad or len(rows) != len(C) or sorted(int(r[0]) for r in rows) != list(range(len(C))):
    sys.exit(f"labels.txt must have one line per candidate 0..{len(C) - 1}: '<idx> <FH|BH|SV|OH|x> <feed|rally|high|unsure|->' (text after that is ignored). bad lines: {bad[:5]}")

P = {}; out = []
for r in sorted(rows, key=lambda r: int(r[0])):
    if r[1] == "x": continue
    c = C[int(r[0])]
    if c["v"] not in P: P[c["v"]] = np.load(Wd / c["v"] / "pose.npy").astype(float)
    m = measure_full(P[c["v"]], c["t"])
    out.append(dict(t=round(c["t"], 3), video=c["v"], vn=c["vn"], cand=int(r[0]), arc=round(c["arc"], 2),
                    kind=r[1], drill=None if r[1] == "SV" or r[2] == "-" else r[2], **m))
out.sort(key=lambda x: (x["vn"], x["t"]))
save(Wd / "strokes_all.json", out)
print(len(out), "strokes", dict(collections.Counter((x["kind"], x["drill"]) for x in out)))
print("auto-kind disagreements (worth a second look):", [x["cand"] for x in out if x["kind"] != x["auto_kind"]])
