# candidates.py <session> — hit sounds where a tracked player's wrist swung, as contact sheets to label by eye.
# Writes work/<s>/cands.json, sheet0.jpg.. (24 candidates per sheet, 5 frames each: -0.75s -0.42s -0.13s contact +0.2s)
# and labels.txt with one "<idx> ? ?" line per candidate for you to fill in.
# Several people tracked (prep.sh people > 1): first writes work/<s>/players.jpg (each tracked person over time) and a players.txt
# template '<video no> <track> ?' to fill with names, then stops. Each hit goes to the person whose wrist swung most into it (swing()),
# and labels.txt lines carry '@name' so a wrong prefill can be corrected.
import sys, cv2, numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import session, work, videos, save, tracks, track_file, players, size, FPS, load_profiles, profile_for
from kind import classify, CONF_MIN
from match import match, WRIST
from assemble import cands_fp
from metrics import hand_gate

OFF = [-45, -25, -8, 0, 12]
PER_SHEET = 24


def tile(cap, Ps, f, label, mark=None):
    """Square crop around the torsos of every pose in Ps at frame f (at least 220 px, so a lone player looks as before; with
    several people the crop grows to hold them all, so a hit by someone other than the prefilled player is visible).
    mark: index in Ps of the prefilled player, drawn as a dot on the hips."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
    H, W = im.shape[:2] if ok else (960, 540)
    cs = [np.nanmean(P[max(0, f - 5):f + 6, [11, 12, 23, 24], :2], axis=(0, 1)) * (W, H) for P in Ps]
    pts = np.array([c for c in cs if np.isfinite(c).all()]).reshape(-1, 2)
    lo, hi = (pts.min(0), pts.max(0)) if len(pts) else (np.array([W / 2, H * 5 / 8]),) * 2
    side = int(min(max(220, *(hi - lo + 240)), H, W)); cx, cy = (lo + hi) / 2
    x0 = int(min(max(cx - side / 2, 0), W - side)); y0 = int(min(max(cy - side * 0.6, 0), H - side))
    t = cv2.resize(im[y0:y0 + side, x0:x0 + side], (200, 200)) if ok else np.zeros((200, 200, 3), np.uint8)
    if mark is not None and len(Ps) > 1 and np.isfinite(cs[mark]).all():
        cv2.circle(t, (int((cs[mark][0] - x0) * 200 / side), int((cs[mark][1] - y0) * 200 / side)), 5, (0, 255, 255), -1)
    cv2.putText(t, label, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return t


s = session(); Wd = work(s); V = videos(s); T = {v: tracks(Wd / v) for v in V}
names = players(s)
if names or any(len(t) > 1 for t in T.values()):
    missing = [(vn, k) for vn, v in enumerate(V, 1) for k in T[v] if (vn, k) not in names]
    if missing:  # who-is-who sheet: one row per tracked person, 10 moments spread over the frames where they were seen
        rows = []
        for vn, k in missing:
            v = V[vn - 1]; P = np.load(track_file(Wd / v, "pose", k)); cap = cv2.VideoCapture(str(Wd / v / "proxy.mp4"))
            seen = np.flatnonzero(~np.isnan(P[:, 0, 0]))
            fs = seen[np.linspace(0, len(seen) - 1, 10).astype(int)] if len(seen) else []
            row = [tile(cap, [P], int(f), f"v{vn} t{k} {int(f / 60 // 60)}:{f / 60 % 60:04.1f}") for f in fs]
            rows.append(np.hstack(row + [np.zeros((200, 200, 3), np.uint8)] * (10 - len(row))))
        cv2.imwrite(str(Wd / "players.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
        with open(Wd / "players.txt", "a") as fh:
            if not names: fh.write("# <video no> <track> <name>: who each tracked person is (see players.jpg). Same name across videos; x = not a player\n")
            fh.writelines(f"{vn} {k} ?\n" for vn, k in missing)
        sys.exit(f"{len(missing)} tracked people need a name: look at {Wd / 'players.jpg'} and replace the ? in {Wd / 'players.txt'}, then re-run")
multi = bool(names)
names = names or {(vn, 0): "me" for vn in range(1, len(V) + 1)}
PROF = load_profiles()
hand = lambda name: (profile_for(PROF, name) or {"hand": None})["hand"]  # racket hand; None = no profile yet: look at both wrists (assemble.py guesses it later)


def matched(P, E, wh, hand):
    """match() rows by hit time for the racket wrist; unknown hand: the wrist that swung more (bigger arc) at each hit,
    so a left-hander without a profile does not lose hits (default-R missed 6 of 45 on a left-handed test video)."""
    M = {}
    for h in ([hand] if hand else "RL"):
        for r in match(P, E, wh, h):
            if r[0] not in M or r[4] > M[r[0]][4]: M[r[0]] = r
    return M


def swing(P, f, wh, wi=16):
    """Wrist path from 0.33 s before a hit sound to 0.07 s after, in torso lengths. The hitter swings into contact;
    the other player's big moves (getting ready for the next ball, walking in) mostly come after it or without a visible wrist."""
    xy = P[:, wi, :2] * wh; xy[P[:, wi, 2] < 0.2] = np.nan
    L = np.linalg.norm((P[f - 30:f + 30, 11, :2] + P[f - 30:f + 30, 12, :2] - P[f - 30:f + 30, 23, :2] - P[f - 30:f + 30, 24, :2]) / 2 * wh, axis=1)
    return np.nansum(np.linalg.norm(np.diff(xy[f - 20:f + 5], axis=0), axis=1)) / np.nanmedian(L) if np.isfinite(L).any() else 0.0


C = []
for vi, v in enumerate(V):
    ks = [k for k in T[v] if names[(vi + 1, k)] != "x"]
    if not ks: continue
    Ps = {k: np.load(track_file(Wd / v, "pose", k)).astype(float) for k in ks}; Hd = {k: hand(names[(vi + 1, k)]) for k in ks}
    wh = np.array(size(Wd / v / "proxy.mp4"), float) / 540; E = np.load(Wd / v / "events.npy")
    for k in ks:  # no profile: the hand this track swings with around the hit events, when speed and height agree (else None = both wrists)
        if Hd[k] is None and len(E): Hd[k] = hand_gate([Ps[k]], size(Wd / v / "proxy.mp4"), [list(E[:, 0])])[0]
    M = {k: matched(Ps[k], E, wh, Hd[k]) for k in ks}
    for t in sorted({t for m in M.values() for t in m}):
        k = max(ks, key=lambda k: max(swing(Ps[k], int(round(t * 60)), wh, WRIST[h]) for h in ([Hd[k]] if Hd[k] else "RL"))) if len(ks) > 1 else ks[0]  # who hit it, then: is it a stroke for them
        if t not in M[k]: continue
        _, pk, on, sp, arc = M[k][t]
        if sp >= 0.05 and arc >= 0.7:
            C.append(dict(v=v, vn=vi + 1, t=float(t), arc=float(arc), sp=float(sp), track=k, player=names[(vi + 1, k)], hand=Hd[k]))
save(Wd / "cands.json", C)

for old in Wd.glob("sheet*.jpg"): old.unlink()
caps, poses = {}, {}
for k in range(0, len(C), PER_SHEET):
    rows = []
    for i, c in enumerate(C[k:k + PER_SHEET]):
        v = c["v"]; ks = [k2 for k2 in T[v] if names[(c["vn"], k2)] != "x"]
        if v not in caps: caps[v] = cv2.VideoCapture(str(Wd / v / "proxy.mp4"))
        for k2 in ks:
            if (v, k2) not in poses: poses[(v, k2)] = np.load(track_file(Wd / v, "pose", k2))
        f = int(round(c["t"] * 60))
        labs = [f"{k + i} v{c['vn']} {int(c['t'] // 60)}:{c['t'] % 60:04.1f}" + (f" @{c['player']}" if multi else "")] + [f"{o:+d}" for o in OFF[1:]]
        row = np.hstack([tile(caps[v], [poses[(v, k2)] for k2 in ks], f + o, l, ks.index(c["track"])) for o, l in zip(OFF, labs)]); row[:, -3:] = (0, 0, 255)
        rows.append(row)
    if len(rows) % 2: rows.append(np.zeros_like(rows[0]))
    sheet = np.vstack([np.hstack(rows[i:i + 2]) for i in range(0, len(rows), 2)])
    cv2.imwrite(str(Wd / f"sheet{k // PER_SHEET}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])

def guess(c):
    """Pre-fill for labels.txt: the automatic stroke kind when confident, else '?' (you still confirm it and add the drill)."""
    if not c["hand"]: return "?"  # FH/BH flip with the hand: no profile, no guess
    v, key = c["v"], (c["v"], c["track"]); wp = track_file(Wd / v, "pose_world", c["track"])
    if key not in poses: poses[key] = np.load(track_file(Wd / v, "pose", c["track"]))
    if key not in worlds: worlds[key] = np.load(wp) if wp.exists() else None
    k = classify(poses[key], int(round(c["t"] * FPS)), c["hand"], worlds[key])  # a left-hander's backswing side mirrors
    return k["kind"] if k["conf"] >= CONF_MIN else "?"


worlds = {}
lab = Wd / "labels.txt"
if lab.exists():
    old = next((l.split()[2] for l in lab.read_text().splitlines() if l.startswith("# cands ") and len(l.split()) > 2), None)
    print("labels.txt exists, left untouched" + ("" if old in (None, cands_fp(Wd / "cands.json")) else
          ". WARNING: it was written for other candidates, its lines now point at other hits; assemble.py will refuse it. Move it aside and re-run to get a fresh one"))
else:
    G = [guess(c) for c in C]
    lab.write_text("# idx kind drill [@player]   kind: FH BH SV OH, or x = not a player / not a stroke (a kind already filled in is the automatic guess: confirm or change it)."
                   "  drill: feed rally high unsure (SV takes none). @player: who hit it (prefilled from players.txt, change it if the crop shows someone else). Anything after is a comment\n"
                   + f"# cands {cands_fp(Wd / 'cands.json')}   (which candidates these lines belong to; leave it)\n"
                   + "".join(f"{i} {g} ?{' @' + c['player'] if multi else ''}\n" for i, (g, c) in enumerate(zip(G, C))))
    print("auto kind pre-filled for", sum(g != "?" for g in G), "of", len(G))
print(len(C), "candidates,", (len(C) + PER_SHEET - 1) // PER_SHEET, "sheets in", Wd)
