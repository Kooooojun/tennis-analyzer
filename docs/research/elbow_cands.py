# elbow_cands.py <id> serve|swing — candidate swings from wrist speed/height + contact sheets for labelling by eye.
# Output: work/elbow-eval/<id>/cands.json and sheetN.jpg (each row = one candidate, frames c-8..c+8 step 4... labelled with absolute frame numbers)
import sys, json, numpy as np, cv2
from pathlib import Path
R = Path.cwd(); id_, mode = sys.argv[1:3]; D = R / "work/elbow-eval" / id_
P = np.load(D / "pose.npy"); n = len(P); xy = P[:, :, :2] * np.array([960, 540])
ok = ~np.isnan(P[:, 0, 0])
def sm(a, k=5): return np.convolve(np.nan_to_num(a), np.ones(k) / k, mode="same")
if mode == "serve":
    # wrist above the nose and moving fast: take local minima of wrist y (highest point) over both wrists
    hi = np.where(ok, np.minimum(xy[:, 15, 1], xy[:, 16, 1]) - xy[:, 0, 1], 9e9)
    cand = [i for i in range(10, n - 10) if hi[i] < -30 and hi[i] == hi[i - 40:i + 41].min()]
else:
    sp = np.zeros(n)
    for j in (15, 16): sp = np.maximum(sp, sm(np.r_[0, np.linalg.norm(np.diff(xy[:, j], axis=0), axis=1)]))
    sp = np.where(ok, sp, 0)
    cand = [i for i in range(10, n - 10) if sp[i] > 14 and sp[i] == sp[i - 45:i + 46].max()]
json.dump(cand, open(D / "cands.json", "w")); print(len(cand), "candidates", cand)
cap = cv2.VideoCapture(str(D / "proxy.mp4")); fr = {}
need = sorted({c + o for c in cand for o in range(-8, 9, 4)})
for k in need:
    cap.set(cv2.CAP_PROP_POS_FRAMES, k); r, im = cap.read(); fr[k] = im if r else None
rows = []
for c in cand:
    pts = xy[c - 8:c + 9, [0, 11, 12, 23, 24, 27, 28]].reshape(-1, 2); pts = pts[~np.isnan(pts).any(1)]
    if not len(pts): continue
    cx, cy = pts.mean(0); h = max(150, (pts[:, 1].max() - pts[:, 1].min()) * 1.5 if mode != "serve" else 260)
    x0, y0 = int(max(0, cx - h * .8)), int(max(0, cy - h * .9)); w, hh = int(h * 1.6), int(h * 1.6)
    cells = []
    for o in range(-8, 9, 4):
        im = fr[c + o]; im = np.zeros((10, 10, 3), np.uint8) if im is None else im
        t = im[y0:y0 + hh, x0:x0 + w]; t = cv2.resize(t, (300, 300)); cv2.putText(t, f"{c+o}", (6, 24), 0, .8, (0, 255, 255), 2); cells.append(t)
    rows.append(np.hstack(cells))
for k in range(0, len(rows), 4):
    cv2.imwrite(str(D / f"sheet{k//4}.jpg"), np.vstack(rows[k:k + 4]), [cv2.IMWRITE_JPEG_QUALITY, 80])
print(len(rows), "rows,", (len(rows) + 3) // 4, "sheets in", D)
