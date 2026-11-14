# candidates.py <session> — hit sounds where a tracked player's wrist swung, as contact sheets to label by eye.
# Writes work/<s>/cands.json, sheet0.jpg.. (24 candidates per sheet, 5 frames each: -0.75s -0.42s -0.13s contact +0.2s)
# and labels.txt with one "<idx> ? ?" line per candidate for you to fill in.
# Several people tracked (prep.sh people > 1): first writes work/<s>/players.jpg (each tracked person over time) and a players.txt
# template '<video no> <track> ?' to fill with names, then stops. Each hit goes to the person whose wrist swung most into it (swing()),
# and labels.txt lines carry '@name' so a wrong prefill can be corrected.
import sys, cv2, numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import session, work, videos, save, tracks, track_file, players, size

OFF = [-45, -25, -8, 0, 12]
PER_SHEET = 24


def tile(cap, P, f, label):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
    H, W = im.shape[:2] if ok else (960, 540)
    c = np.nanmean(P[max(0, f - 5):f + 6, [11, 12, 23, 24], :2], axis=(0, 1))
    cx, cy = (W // 2, H * 5 // 8) if np.isnan(c).any() else (int(c[0] * W), int(c[1] * H))
    x0 = min(max(cx - 110, 0), W - 220); y0 = min(max(cy - 130, 0), H - 220)
    t = cv2.resize(im[y0:y0 + 220, x0:x0 + 220], (200, 200)) if ok else np.zeros((200, 200, 3), np.uint8)
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
            row = [tile(cap, P, int(f), f"v{vn} t{k} {int(f / 60 // 60)}:{f / 60 % 60:04.1f}") for f in fs]
            rows.append(np.hstack(row + [np.zeros((200, 200, 3), np.uint8)] * (10 - len(row))))
        cv2.imwrite(str(Wd / "players.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
        with open(Wd / "players.txt", "a") as fh:
            if not names: fh.write("# <video no> <track> <name>: who each tracked person is (see players.jpg). Same name across videos; x = not a player\n")
            fh.writelines(f"{vn} {k} ?\n" for vn, k in missing)
        sys.exit(f"{len(missing)} tracked people need a name: look at {Wd / 'players.jpg'} and replace the ? in {Wd / 'players.txt'}, then re-run")
multi = bool(names)
names = names or {(vn, 0): "me" for vn in range(1, len(V) + 1)}

def swing(P, f, wh):
    """Wrist path from 0.33 s before a hit sound to 0.07 s after, in torso lengths. The hitter swings into contact;
    the other player's big moves (getting ready for the next ball, walking in) mostly come after it or without a visible wrist."""
    xy = P[:, 16, :2] * wh; xy[P[:, 16, 2] < 0.2] = np.nan
    L = np.linalg.norm((P[f - 30:f + 30, 11, :2] + P[f - 30:f + 30, 12, :2] - P[f - 30:f + 30, 23, :2] - P[f - 30:f + 30, 24, :2]) / 2 * wh, axis=1)
    return np.nansum(np.linalg.norm(np.diff(xy[f - 20:f + 5], axis=0), axis=1)) / np.nanmedian(L) if np.isfinite(L).any() else 0.0


C = []
for vi, v in enumerate(V):
    ks = [k for k in T[v] if names[(vi + 1, k)] != "x"]
    if not ks: continue
    Ps = {k: np.load(track_file(Wd / v, "pose", k)).astype(float) for k in ks} if len(ks) > 1 else {}
    wh = np.array(size(Wd / v / "proxy.mp4"), float) / 540
    M = {k: {r[0]: r for r in np.load(track_file(Wd / v, "match", k))} for k in ks}
    for t in sorted({t for m in M.values() for t in m}):
        k = max(ks, key=lambda k: swing(Ps[k], int(round(t * 60)), wh)) if Ps else ks[0]  # who hit it, then: is it a stroke for them
        if t not in M[k]: continue
        _, pk, on, sp, arc = M[k][t]
        if sp >= 0.05 and arc >= 0.7:
            C.append(dict(v=v, vn=vi + 1, t=float(t), arc=float(arc), sp=float(sp), track=k, player=names[(vi + 1, k)]))
save(Wd / "cands.json", C)

for old in Wd.glob("sheet*.jpg"): old.unlink()
caps, poses = {}, {}
for k in range(0, len(C), PER_SHEET):
    rows = []
    for i, c in enumerate(C[k:k + PER_SHEET]):
        v, key = c["v"], (c["v"], c["track"])
        if v not in caps: caps[v] = cv2.VideoCapture(str(Wd / v / "proxy.mp4"))
        if key not in poses: poses[key] = np.load(track_file(Wd / v, "pose", c["track"]))
        f = int(round(c["t"] * 60))
        labs = [f"{k + i} v{c['vn']} {int(c['t'] // 60)}:{c['t'] % 60:04.1f}" + (f" @{c['player']}" if multi else "")] + [f"{o:+d}" for o in OFF[1:]]
        row = np.hstack([tile(caps[v], poses[key], f + o, l) for o, l in zip(OFF, labs)]); row[:, -3:] = (0, 0, 255)
        rows.append(row)
    if len(rows) % 2: rows.append(np.zeros_like(rows[0]))
    sheet = np.vstack([np.hstack(rows[i:i + 2]) for i in range(0, len(rows), 2)])
    cv2.imwrite(str(Wd / f"sheet{k // PER_SHEET}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])

lab = Wd / "labels.txt"
if lab.exists():
    print("labels.txt exists, left untouched")
else:
    lab.write_text("# idx kind drill [@player]   kind: FH BH SV OH, or x = not a player / not a stroke.  drill: feed rally high unsure (SV takes none)."
                   " @player: who hit it (prefilled from players.txt, change it if the crop shows someone else). Anything after is a comment\n"
                   + "".join(f"{i} ? ?{' @' + c['player'] if multi else ''}\n" for i, c in enumerate(C)))
print(len(C), "candidates,", (len(C) + PER_SHEET - 1) // PER_SHEET, "sheets in", Wd)
