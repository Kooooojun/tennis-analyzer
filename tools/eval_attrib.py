# eval_attrib.py <session> <labels.csv> | <session> --check — "who hit it" accuracy of candidates.py's attribution (attrib.py), on a hand-labelled hold-out set.
# labels.csv: one line per hit '<video>,<t seconds>,<name from players.txt>' (the person who really hit it, labelled from the original frames
# without looking at this script's output); '#' lines ignored. Prints N, accuracy and the wrong ones.
# --check: for every row of work/<s>/cands.json, who_hit() must pick the same track as candidates.py did.
# Tune nothing on a hold-out: a hold-out that is used to tune a window is not a hold-out.
import sys, numpy as np
from common import session, work, load, videos, tracks, track_file, players, size, FPS, profile_for
from profiles import load_session_profiles
from attrib import wrist_hands, who_hit


def setup(s):
    """{video: ({track: pose}, {track: wrist hand}, wh, {track: name})} for the tracked people that are not x, as candidates.py builds them."""
    Wd = work(s); names = players(s); PROF = load_session_profiles(s)[0]; out = {}
    for vi, v in enumerate(videos(s)):
        nm = {k: names.get((vi + 1, k), "me") for k in tracks(Wd / v)}; nm = {k: n for k, n in nm.items() if n != "x"}
        if not nm: continue
        Ps = {k: np.load(track_file(Wd / v, "pose", k)).astype(float) for k in nm}; sz = size(Wd / v / "proxy.mp4"); wh = np.array(sz, float) / 540
        prof = {k: (profile_for(PROF, n) or {"hand": None})["hand"] for k, n in nm.items()}
        out[v] = (Ps, wrist_hands(Ps, prof, np.load(Wd / v / "events.npy"), wh, sz), wh, nm)
    return out


def main():
    s = session(); W = setup(s)
    if sys.argv[2:3] == ["--check"]:
        C = load(work(s) / "cands.json"); got = [(i, c["t"], c["track"], who_hit(*W[c["v"]][:2], c["t"], W[c["v"]][2])) for i, c in enumerate(C) if c["v"] in W]
        if len(got) != len(C): sys.exit(f"cannot check {len(C) - len(got)} candidates: their video has every person x in players.txt now (re-run candidates.py)")
        bad = [g for g in got if g[2] != g[3]]
        sys.exit(f"MISMATCH with candidates.py on {len(bad)} of {len(C)}: {bad[:5]}" if bad else print(f"check OK: same track as candidates.py on all {len(C)} candidates") or 0)
    if len(sys.argv) < 3: sys.exit("usage: eval_attrib.py <session> <labels.csv> | --check")
    ok, wrong, skipped, n = 0, [], [], 0
    for ln, l in enumerate(open(sys.argv[2], encoding="utf-8").read().splitlines(), 1):
        if not l.strip() or l.startswith("#"): continue
        try: v, t, who = (x.strip() for x in l.split(",")); t = float(t)
        except ValueError: sys.exit(f"{sys.argv[2]} line {ln}: want '<video>,<t seconds>,<name>', got {l!r}")
        if v not in W: sys.exit(f"line {ln}: video {v!r} has no tracked player in this session (videos with every person x are skipped): {sorted(W)}")
        if round(t * FPS) < 30: print(f"skip line {ln}: hit at {t} s is before the 0.5 s torso window"); skipped.append(ln); continue
        Ps, hands, wh, nm = W[v]; k = who_hit(Ps, hands, t, wh); n += 1
        if nm[k] == who: ok += 1
        else: wrong.append((ln, v, t, who, nm[k]))
    if skipped: print(f"skipped {len(skipped)} line(s): {skipped}")
    if not n: sys.exit("no hold-out rows")
    z = 1.96; p = ok / n; lo = (p + z * z / (2 * n) - z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    print(f"N = {n}, correct {ok} = {100 * p:.1f}% (Wilson 95% lower {100 * lo:.1f}%; bar 95%)")
    for w in wrong: print("wrong:", w)


if __name__ == "__main__":
    main()
