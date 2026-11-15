# candidates.py <session> — hit sounds where a tracked player's wrist swung, as contact sheets to label by eye.
# Writes work/<s>/cands.json, sheet<idx>.jpg (one candidate each: 12 wide crops around the hit sound from the original video + 3 whole frames;
# --legacy: the old sheets, 24 candidates per sheet, 5 frames each: -0.75s -0.42s -0.13s contact +0.2s)
# and labels.txt with one "<idx> ? ?" line per candidate for you to fill in.
# Several people tracked (prep.sh people > 1): first writes work/<s>/players.jpg (each tracked person over time) and a players.txt
# template '<video no> <track> ?' to fill with names, then stops. Each hit goes to the person whose wrist swung most into it (swing()),
# and labels.txt lines carry '@name' so a wrong prefill can be corrected.
import sys, cv2, numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import ROOT, session, work, videos, save, tracks, track_file, players, size, FPS, load_profiles, profile_for
from kind import classify, prefill
from crop import square, wide, cut, brighten
from match import match, WRIST
from assemble import cands_fp
from metrics import hand_gate

OFF = [-45, -25, -8, 0, 12]  # --legacy sheets: 24 candidates per sheet, 5 small square crops each
PER_SHEET = 24
OFF_NEW = [-12, -9, -6, -3, -2, -1, 0, 1, 2, 3, 6, 9]  # default sheets: one candidate per sheet, frames around the hit sound (60 fps)
WHOLE = [-45, -20, 0]
TILE = (375, 250)  # 4 x 3 crops + a row of whole frames = 1500 x 1000: small enough that an image reader does not shrink it
LEGACY = "--legacy" in sys.argv[2:]


def tile(cap, Ps, f, label, mark=None):
    """Square crop around the torsos of every pose in Ps at frame f (at least 220 px, so a lone player looks as before; with
    several people the crop grows to hold them all, so a hit by someone other than the prefilled player is visible).
    mark: index in Ps of the prefilled player, drawn as a dot on the hips."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
    H, W = im.shape[:2] if ok else (960, 540)
    cs = [np.nanmean(P[max(0, f - 5):f + 6, [11, 12, 23, 24], :2], axis=(0, 1)) * (W, H) for P in Ps]
    side, x0, y0 = square(np.array([c for c in cs if np.isfinite(c).all()]).reshape(-1, 2), W, H)
    t = cv2.resize(cut(im, x0, y0, side, side), (200, 200)) if ok else np.zeros((200, 200, 3), np.uint8)
    if mark is not None and len(Ps) > 1 and np.isfinite(cs[mark]).all():
        cv2.circle(t, (int((cs[mark][0] - x0) * 200 / side), int((cs[mark][1] - y0) * 200 / side)), 5, (0, 255, 255), -1)
    cv2.putText(t, label, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return t


def frames(src, ts):
    """{t: frame} for times ts (s) from video src: one seek, then decode forward, keeping only the frame nearest each time
    (the source may be 59.94 fps: times, not frame numbers). None where the clip has no frame."""
    cap = cv2.VideoCapture(str(src)); cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, min(ts) - 0.1) * 1000); best = {t: (0.03, None) for t in ts}
    while True:
        ok, im = cap.read()
        if not ok: break
        now = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        for t in ts:
            if abs(now - t) < best[t][0]: best[t] = (abs(now - t), im)
        if now > max(ts) + 0.05: break
    cap.release()
    return {t: b[1] for t, b in best.items()}


def text(t, s, y=22, c=(0, 255, 255)):
    cv2.putText(t, s, (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3); cv2.putText(t, s, (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 1)


def sheet(c, idx, Ps, mark, src, low):
    """One candidate, 1500x1000: 12 wide crops of the hitter around the hit sound (every 3 frames, every frame within 3), brightened,
    cut from the original video when there is one (low: proxy only, the ball is about half as big); under them 3 whole frames
    (-45 -20 0: a feed toss, and who else is there). Crop box from the pose (normalised), so it maps onto any frame size."""
    f = int(round(c["t"] * FPS)); P = Ps[mark]
    T = {o: c["t"] + o / FPS for o in OFF_NEW + WHOLE}; F = frames(src, sorted(set(T.values())))
    H, W = next((im.shape[:2] for im in F.values() if im is not None), (1080, 1920)); wh = np.array((W, H), float)
    rows, row = [], []
    for o in OFF_NEW:
        q = P[max(0, f + o - 5):f + o + 6].astype(float); sh = np.nanmean(q[:, [11, 12], :2], axis=(0, 1)) * wh; hp = np.nanmean(q[:, [23, 24], :2], axis=(0, 1)) * wh
        L = min(float(np.linalg.norm(sh - hp)), H / 3) if np.isfinite([*sh, *hp]).all() else H / 6  # cap: a pose glitch must not ask for a gigapixel crop
        x0, y0, w, h = wide((sh + hp) / 2 if np.isfinite([*sh, *hp]).all() else wh / 2, max(L, H / 20), W, H)
        t = cv2.resize(brighten(cut(F[T[o]], x0, y0, w, h)), TILE, interpolation=cv2.INTER_AREA if w > TILE[0] else cv2.INTER_CUBIC)
        text(t, f"{idx} {o:+d}" if o else f"{idx} v{c['vn']} {int(c['t'] // 60)}:{c['t'] % 60:04.1f} hit sound" + (f" @{c['player']}" if len(Ps) > 1 else ""))
        if o == 0: t[:, :3] = t[:, -3:] = (0, 0, 255)
        row.append(t)
        if len(row) == 4: rows.append(np.hstack(row)); row = []
    gw = int(TILE[1] * W / H); g = []
    for o in WHOLE:
        t = cv2.resize(brighten(F[T[o]]), (gw, TILE[1]), interpolation=cv2.INTER_AREA) if F[T[o]] is not None else np.zeros((TILE[1], gw, 3), np.uint8)
        if len(Ps) > 1:
            hp = np.nanmean(P[max(0, f + o - 5):f + o + 6, [23, 24], :2].astype(float), axis=(0, 1))
            if np.isfinite(hp).all(): cv2.circle(t, (int(hp[0] * gw), int(hp[1] * TILE[1])), 6, (0, 255, 255), -1)
        text(t, f"whole frame {o:+d}"); g.append(t)
    g = np.hstack(g); pad = 4 * TILE[0] - g.shape[1]
    g = np.hstack([g, np.zeros((TILE[1], pad, 3), np.uint8)]) if pad >= 0 else cv2.resize(g, (4 * TILE[0], TILE[1]))
    if low: text(g, "proxy resolution only (no original video): the ball is small", TILE[1] - 12, (0, 0, 255))
    return np.vstack(rows + [g])


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
    Ps = {k: np.load(track_file(Wd / v, "pose", k)).astype(float) for k in ks}; prof = {k: hand(names[(vi + 1, k)]) for k in ks}
    wh = np.array(size(Wd / v / "proxy.mp4"), float) / 540; E = np.load(Wd / v / "events.npy"); Hd = dict(prof)
    for k in ks:  # no profile: guess from this track's own matched hits (as assemble does), only to pick the wrist; None = both wrists
        if Hd[k] is None:
            ts = [t for t, _, _, sp, arc in matched(Ps[k], E, wh, None).values() if sp >= 0.05 and arc >= 0.7]
            if ts: Hd[k] = hand_gate([Ps[k]], size(Wd / v / "proxy.mp4"), [ts])[0]
    M = {k: matched(Ps[k], E, wh, Hd[k]) for k in ks}
    for t in sorted({t for m in M.values() for t in m}):
        k = max(ks, key=lambda k: max(swing(Ps[k], int(round(t * 60)), wh, WRIST[h]) for h in ([Hd[k]] if Hd[k] else "RL"))) if len(ks) > 1 else ks[0]  # who hit it, then: is it a stroke for them
        if t not in M[k]: continue
        _, pk, on, sp, arc = M[k][t]
        if sp >= 0.05 and arc >= 0.7:
            C.append(dict(v=v, vn=vi + 1, t=float(t), arc=float(arc), sp=float(sp), track=k, player=names[(vi + 1, k)], hand=prof[k]))  # profile hand only: a guessed hand must not pre-fill FH/BH (a wrong guess mirrors them)
save(Wd / "cands.json", C)

for old in Wd.glob("sheet*.jpg"): old.unlink()
caps, poses = {}, {}
for c in C:
    for k2 in T[c["v"]]:
        if names[(c["vn"], k2)] != "x" and (c["v"], k2) not in poses: poses[(c["v"], k2)] = np.load(track_file(Wd / c["v"], "pose", k2))
if LEGACY:
    for k in range(0, len(C), PER_SHEET):
        rows = []
        for i, c in enumerate(C[k:k + PER_SHEET]):
            v = c["v"]; ks = [k2 for k2 in T[v] if names[(c["vn"], k2)] != "x"]
            if v not in caps: caps[v] = cv2.VideoCapture(str(Wd / v / "proxy.mp4"))
            f = int(round(c["t"] * 60))
            labs = [f"{k + i} v{c['vn']} {int(c['t'] // 60)}:{c['t'] % 60:04.1f}" + (f" @{c['player']}" if multi else "")] + [f"{o:+d}" for o in OFF[1:]]
            row = np.hstack([tile(caps[v], [poses[(v, k2)] for k2 in ks], f + o, l, ks.index(c["track"])) for o, l in zip(OFF, labs)]); row[:, -3:] = (0, 0, 255)
            rows.append(row)
        if len(rows) % 2: rows.append(np.zeros_like(rows[0]))
        sheet_im = np.vstack([np.hstack(rows[i:i + 2]) for i in range(0, len(rows), 2)])
        cv2.imwrite(str(Wd / f"sheet{k // PER_SHEET}.jpg"), sheet_im, [cv2.IMWRITE_JPEG_QUALITY, 80])
else:
    srcs, low = {}, set()
    for v in dict.fromkeys(c["v"] for c in C):  # original video = the file whose stem is v (a glob "v.*" would also match "v.x.mov"); not openable (codec) -> proxy
        src = next((p for p in sorted((ROOT / "videos" / s).iterdir()) if p.stem == v and p.suffix.lower() in (".mov", ".mp4", ".m4v") and cv2.VideoCapture(str(p)).isOpened()), None)
        if src is None: low.add(v)
        srcs[v] = src or Wd / v / "proxy.mp4"
    for i, c in enumerate(C):  # each candidate decodes only ~0.9 s of its video
        v = c["v"]; ks = [k2 for k2 in T[v] if names[(c["vn"], k2)] != "x"]; src = srcs[v]
        im = sheet(c, i, [poses[(v, k2)] for k2 in ks], ks.index(c["track"]), src, v in low)
        cv2.imwrite(str(Wd / f"sheet{i}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if low: print("no original video for", sorted(low), "- sheets from proxy.mp4 only (about half the resolution, the ball is small)")

def guess(c):
    """Pre-fill for labels.txt: the automatic stroke kind when confident, else '?' (you still confirm it and add the drill)."""
    if not c["hand"]: return "?"  # FH/BH flip with the hand: no profile, no guess
    v, key = c["v"], (c["v"], c["track"]); wp = track_file(Wd / v, "pose_world", c["track"])
    if key not in poses: poses[key] = np.load(track_file(Wd / v, "pose", c["track"]))
    if key not in worlds: worlds[key] = np.load(wp) if wp.exists() else None
    if v not in sizes: sizes[v] = size(Wd / v / "proxy.mp4")  # one open per video (and size() exits on an unreadable proxy)
    k = classify(poses[key], int(round(c["t"] * FPS)), c["hand"], worlds[key], sizes[v])  # a left-hander's backswing side mirrors
    return prefill(k["kind"], k["conf"])


worlds, sizes = {}, {}
lab = Wd / "labels.txt"
if lab.exists():
    old = next((l.split()[2] for l in lab.read_text().splitlines() if l.startswith("# cands ") and len(l.split()) > 2), None)
    print("labels.txt exists, left untouched" + ("" if old in (None, cands_fp(Wd / "cands.json")) else
          ". WARNING: it was written for other candidates, its lines now point at other hits; assemble.py will refuse it. Move it aside and re-run to get a fresh one"))
else:
    G = [guess(c) for c in C]
    lab.write_text("# idx kind drill [@player]   kind: FH BH SV OH, or x = not a player / not a hit (keep a line only if the sheet shows the ball on the strings or leaving them; else x + why: dropped in-hand shadow follow-through pickup no-swing). A kind already filled in is a guess about the swing, NOT proof of contact; fill each ? from its sheet, never in bulk."
                   "  drill: feed rally high unsure (SV takes none). @player: who hit it (prefilled from players.txt, change it if the crop shows someone else). Anything after is a comment\n"
                   + f"# cands {cands_fp(Wd / 'cands.json')}   (which candidates these lines belong to; leave it)\n"
                   + "".join(f"{i} {g} ?{' @' + c['player'] if multi else ''}\n" for i, (g, c) in enumerate(zip(G, C))))
    print("auto kind pre-filled for", sum(g != "?" for g in G), "of", len(G))
print(len(C), "candidates,", (len(C) + PER_SHEET - 1) // PER_SHEET if LEGACY else len(C), "sheets in", Wd)
