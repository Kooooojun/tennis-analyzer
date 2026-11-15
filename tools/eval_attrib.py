# eval_attrib.py <session> <labels.csv> | <session> --check — "who hit it" accuracy of candidates.py's attribution, on a hand-labelled hold-out set.
# labels.csv: one line per hit '<video>,<t seconds>,<name from players.txt>' (the person who really hit it, labelled from the original frames
# without looking at this script's output); '#' lines ignored. Prints N, accuracy and the wrong ones.
# --check: for every row of work/<s>/cands.json, who_hit() must pick the same track as candidates.py did (this file copies that formula; the
# check catches drift). Tune nothing here: a hold-out that is used to tune a window is not a hold-out.
import sys, numpy as np
from common import session, work, load, videos, tracks, track_file, players, size, FPS
from match import WRIST
from profiles import load_session_profiles
from common import profile_for


def swing(P, f, wh, wi=16):
    """Same as candidates.swing: wrist path from 20 frames before to 5 after the hit, in torso lengths (wrist visibility < 0.2 ignored)."""
    xy = P[:, wi, :2] * wh; xy[P[:, wi, 2] < 0.2] = np.nan
    L = np.linalg.norm((P[f - 30:f + 30, 11, :2] + P[f - 30:f + 30, 12, :2] - P[f - 30:f + 30, 23, :2] - P[f - 30:f + 30, 24, :2]) / 2 * wh, axis=1)
    return np.nansum(np.linalg.norm(np.diff(xy[f - 20:f + 5], axis=0), axis=1)) / np.nanmedian(L) if np.isfinite(L).any() else 0.0


def who_hit(Ps, hands, t, wh):
    """Track key (of Ps) of the person whose racket wrist swung most into a hit at time t; hand None = best of both wrists. One person = that one."""
    f = int(round(t * FPS))
    if f < 30: raise ValueError(f"hit at {t}s is too early for the 0.5 s torso window (candidates.py has the same limit)")
    return max(Ps, key=lambda k: max(swing(Ps[k], f, wh, WRIST[h]) for h in ([hands[k]] if hands[k] else "RL"))) if len(Ps) > 1 else next(iter(Ps))


def setup(s):
    """{video: ({track: pose}, {track: hand}, wh, {track: name})} for the tracked people that are not x, like candidates.py (hand: profile only)."""
    Wd = work(s); names = players(s); PROF = load_session_profiles(s)[0]; out = {}
    for vi, v in enumerate(videos(s)):
        nm = {k: names.get((vi + 1, k), "me") for k in tracks(Wd / v)}; nm = {k: n for k, n in nm.items() if n != "x"}
        if not nm: continue
        out[v] = ({k: np.load(track_file(Wd / v, "pose", k)).astype(float) for k in nm}, {k: (profile_for(PROF, n) or {"hand": None})["hand"] for k, n in nm.items()},
                  np.array(size(Wd / v / "proxy.mp4"), float) / 540, nm)
    return out


def main():
    s = session(); W = setup(s)
    if sys.argv[2:3] == ["--check"]:
        C = load(work(s) / "cands.json"); got = [(i, c["t"], c["track"], who_hit(*W[c["v"]][:2], c["t"], W[c["v"]][2])) for i, c in enumerate(C) if c["v"] in W]
        if len(got) != len(C): sys.exit(f"cannot check {len(C) - len(got)} candidates: their video has every person x in players.txt now (re-run candidates.py)")
        bad = [g for g in got if g[2] != g[3]]
        sys.exit(f"MISMATCH with candidates.py on {len(bad)} of {len(C)}: {bad[:5]}" if bad else print(f"check OK: same track as candidates.py on all {len(C)} candidates") or 0)
    if len(sys.argv) < 3: sys.exit("usage: eval_attrib.py <session> <labels.csv> | --check")
    rows = [l.split(",") for l in open(sys.argv[2], encoding="utf-8").read().splitlines() if l.strip() and not l.startswith("#")]
    ok, wrong = 0, []
    for v, t, who in rows:
        if v not in W: sys.exit(f"video {v!r} has no tracked player in this session (videos with every person x are skipped): {sorted(W)}")
        Ps, hands, wh, nm = W[v]; k = who_hit(Ps, hands, float(t), wh)
        if nm[k] == who.strip(): ok += 1
        else: wrong.append((v, float(t), who.strip(), nm[k]))
    print(f"N = {len(rows)}, correct {ok} = {100 * ok / max(1, len(rows)):.1f}% (bar 95%)")
    for w in wrong: print("wrong:", w)


if __name__ == "__main__":
    main()
