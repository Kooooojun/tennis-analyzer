# candidates.py <session> — hit sounds where the tracked player's wrist swung, as contact sheets to label by eye.
# Writes work/<s>/cands.json, sheet0.jpg.. (24 candidates per sheet, 5 frames each: -0.75s -0.42s -0.13s contact +0.2s)
# and labels.txt with one "<idx> ? ?" line per candidate for you to fill in.
import cv2, numpy as np
import warnings; warnings.filterwarnings("ignore")
from common import session, work, videos, save

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


s = session(); Wd = work(s); C = []
for vi, v in enumerate(videos(s)):
    M = np.load(Wd / v / "match.npy"); M = M[M[:, 4] > 0.5]
    for j, (t, pk, on, sp, arc) in enumerate(M):
        if sp >= 0.05 and arc >= 0.7:
            C.append(dict(v=v, vn=vi + 1, j=j, t=float(t), arc=float(arc), sp=float(sp)))
save(Wd / "cands.json", C)

for old in Wd.glob("sheet*.jpg"): old.unlink()
caps, poses = {}, {}
for k in range(0, len(C), PER_SHEET):
    rows = []
    for i, c in enumerate(C[k:k + PER_SHEET]):
        v = c["v"]
        if v not in caps: caps[v] = cv2.VideoCapture(str(Wd / v / "proxy.mp4")); poses[v] = np.load(Wd / v / "pose.npy")
        f = int(round(c["t"] * 60))
        labs = [f"{k + i} v{c['vn']} {int(c['t'] // 60)}:{c['t'] % 60:04.1f}"] + [f"{o:+d}" for o in OFF[1:]]
        row = np.hstack([tile(caps[v], poses[v], f + o, l) for o, l in zip(OFF, labs)]); row[:, -3:] = (0, 0, 255)
        rows.append(row)
    if len(rows) % 2: rows.append(np.zeros_like(rows[0]))
    sheet = np.vstack([np.hstack(rows[i:i + 2]) for i in range(0, len(rows), 2)])
    cv2.imwrite(str(Wd / f"sheet{k // PER_SHEET}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])

lab = Wd / "labels.txt"
if lab.exists():
    print("labels.txt exists, left untouched")
else:
    lab.write_text("# idx kind drill   kind: FH BH SV OH, or x = not you / not a stroke.  drill: feed rally high unsure (SV takes none). Anything after is a comment\n"
                   + "".join(f"{i} ? ?\n" for i in range(len(C))))
print(len(C), "candidates,", (len(C) + PER_SHEET - 1) // PER_SHEET, "sheets in", Wd)
