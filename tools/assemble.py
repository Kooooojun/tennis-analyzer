# assemble.py <session> — labels.txt + cands.json -> work/<s>/strokes_all.json (one entry per labelled stroke, with metrics)
import collections, hashlib, json, sys, numpy as np
from common import session, work, load, save, size, track_file, players, load_profiles, profile_for
from metrics import measure_full, hand_gate
from kind import PREFILL_MIN

KINDS = {"FH", "BH", "SV", "OH"}; DRILLS = {"feed", "rally", "high", "unsure", "-"}
cands_fp = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:16]  # candidates.py writes it into labels.txt as '# cands <fp>'


def read_labels(Wd, C):
    """labels.txt rows, checked against cands.json: one line per candidate, and written for THIS cands.json (a re-run of
    candidates.py with the same count would otherwise shift every label onto another hit without a word)."""
    lines = (Wd / "labels.txt").read_text().splitlines()
    fp = next((l.split()[2] for l in lines if l.startswith("# cands ") and len(l.split()) > 2), None)
    if fp is None: print("warning: labels.txt has no '# cands' line (made before fingerprints), cannot check it still matches cands.json")
    elif fp != cands_fp(Wd / "cands.json"):
        sys.exit(f"labels.txt was written for another cands.json (candidates.py was re-run since). Move {Wd / 'labels.txt'} aside, "
                 "re-run tools/candidates.py to get a fresh labels.txt and label it again from the new sheets; the old file's lines point at other hits")
    rows = [l.split() for l in lines if l.strip() and not l.startswith("#")]
    bad = [r for r in rows if not (r[0].isdigit() and int(r[0]) < len(C)) or not (r[1] == "x" or r[1] == "SV" or (r[1] in KINDS and len(r) > 2 and r[2] in DRILLS))]
    if bad or len(rows) != len(C) or sorted(int(r[0]) for r in rows) != list(range(len(C))):
        sys.exit(f"labels.txt must have one line per candidate 0..{len(C) - 1}: '<idx> <FH|BH|SV|OH|x> <feed|rally|high|unsure|->' (text after that is ignored). bad lines: {bad[:5]}")
    return rows


BULK_N = 10      # at least this many lines and
BULK_X = 0.03    # under this share of x: probably accepted wholesale (the user's wall video A: 79 x FH, ~2 in 7 fake; one stray x must not hide it)


def bulk_warning(rows):
    """A warning when >= BULK_N lines and under BULK_X of them are x, else None. Only a hint: nothing is changed."""
    nx = sum(r[1] == "x" for r in rows)
    if len(rows) >= BULK_N and nx < BULK_X * len(rows):
        return (f"WARNING: {nx} of {len(rows)} lines are x. Hit sounds include bounces, a ball dropped from the hand and shadow swings; "
                "re-check every sheet and keep a line only where you see the ball on the strings or just leaving them (ignore this if every line really is a hit)")


player_of = lambda i, who, C: who[i] or C[i].get("player") or "me"  # '@name' first; null / missing player = me


def main():
    s = session(); Wd = work(s); C = load(Wd / "cands.json"); rows = read_labels(Wd, C)
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
    name = lambda i: player_of(i, who, C)
    # Racket hand / backhand type per player: work/profiles.json first, else guessed from this session's video (flagged hand_guess);
    # an unsure guess stops here: a wrong hand mirrors FH/BH, elbow and contact checks for every stroke
    PROF = load_profiles(); H = {}; vids = {}; unsure = {}
    for r in rows:
        if r[1] != "x": c = C[int(r[0])]; vids.setdefault(name(int(r[0])), {}).setdefault(pose(c), []).append(c["t"])
    for nm, cs in vids.items():
        p = profile_for(PROF, nm)
        if p: H[nm] = dict(hand=p["hand"], hand_guess=False, backhand=p["backhand"]); print(f"player {nm}: hand {p['hand']}, backhand {p['backhand']} (work/profiles.json)")
        else:
            g, ratio, why = hand_gate([P[k] for k in cs], [SZ[k[0]] for k in cs], list(cs.values()))
            if g is None: unsure[nm] = why; continue
            H[nm] = dict(hand=g, hand_guess=True, backhand=None)
            print(f"player {nm}: hand {g} GUESSED (wrist speed ratio {ratio}, wrist height agrees). Ask the user for the hand and backhand type, then write work/profiles.json: " + json.dumps({nm: {"hand": g, "backhand": "two"}}))
    if unsure:
        sys.exit("cannot tell the racket hand of " + "; ".join(f"{nm} ({why})" for nm, why in unsure.items()) + ". Ask the user, then write work/profiles.json, e.g. "
                 + json.dumps({nm: {"hand": "R", "backhand": "two"} for nm in unsure}) + " and re-run")
    kept = [(C[int(r[0])]["v"], name(int(r[0])), C[int(r[0])]["t"]) for r in rows if r[1] != "x"]  # prep stops at the same player's previous hit
    for r in sorted(rows, key=lambda r: int(r[0])):
        if r[1] == "x": continue
        i = int(r[0]); c = C[i]; key = pose(c); h = H[name(i)]
        pt = [t for v, nm, t in kept if v == c["v"] and nm == name(i) and t < c["t"] - 1e-6]
        m = measure_full(P[key], c["t"], SZ[c["v"]], WD[key], h["hand"], max(pt) if pt else None)
        out.append(dict(t=round(c["t"], 3), video=c["v"], vn=c["vn"], cand=i, arc=round(c["arc"], 2), track=key[1], player=name(i),
                        size=SZ[c["v"]], **h, kind=r[1], drill=None if r[1] == "SV" or r[2] == "-" else r[2], **m))
    out.sort(key=lambda x: (x["vn"], x["t"]))
    save(Wd / "strokes_all.json", out)
    print(len(out), "strokes", dict(collections.Counter((x["player"], x["kind"], x["drill"]) for x in out)))
    if w := bulk_warning(rows): print(w)
    print(f"FH/BH with kind_conf < {PREFILL_MIN} (weak swing evidence, look again):",  # SV / OH confs sit below it by design (kind.SV_CONF)
          [x["cand"] for x in out if x["kind"] in ("FH", "BH") and (x["kind_conf"] is None or x["kind_conf"] < PREFILL_MIN)])
    print("auto-kind disagreements (worth a second look):", [x["cand"] for x in out if x["kind"] != x["auto_kind"]])


if __name__ == "__main__":
    main()
