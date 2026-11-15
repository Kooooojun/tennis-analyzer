# kind_cands.py <id> — 候選揮拍（任一手腕速度峰值）與縮圖板，用眼睛標種類。從 repo 根目錄跑。
# 輸出 work/kind/<id>/cands.json、sheetN.jpg（每列一個候選：峰值幀 -12 -8 -4 0 +4，60fps，角標 <cand>:<幀>）
import sys, json, numpy as np, cv2
from pathlib import Path
D = Path("work/kind") / sys.argv[1]
P = np.load(D / "pose.npy"); n = len(P); xy = P[:, :, :2] * np.array([960, 540]); ok = ~np.isnan(P[:, 0, 0])
def sm(a, k=5): return np.convolve(np.nan_to_num(a), np.ones(k) / k, mode="same")
sp = np.zeros(n)
for j in (15, 16): sp = np.maximum(sp, sm(np.r_[0, np.linalg.norm(np.diff(xy[:, j], axis=0), axis=1)]))
sp = np.where(ok, sp, 0)
cand = [i for i in range(14, n - 10) if sp[i] > 12 and sp[i] == sp[i - 40:i + 41].max()]
json.dump(cand, open(D / "cands.json", "w")); print(len(cand), "candidates")
cap = cv2.VideoCapture(str(D / "proxy.mp4")); OFF = [-12, -8, -4, 0, 4]; rows = []
for k, c in enumerate(cand):
    pts = xy[c - 6:c + 7, [0, 11, 12, 23, 24, 27, 28]].reshape(-1, 2); pts = pts[~np.isnan(pts).any(1)]
    cx, cy = pts.mean(0) if len(pts) else (480, 270); h = 300
    x0, y0 = int(min(max(cx - h * .5, 0), 960 - h)), int(min(max(cy - h * .6, 0), 540 - h)); cells = []
    for o in OFF:
        cap.set(cv2.CAP_PROP_POS_FRAMES, c + o); r, im = cap.read()
        t = cv2.resize(im[y0:y0 + h, x0:x0 + h], (240, 240)) if r else np.zeros((240, 240, 3), np.uint8)
        cv2.putText(t, f"{k}:{c + o}", (4, 18), 0, .55, (0, 255, 255), 2); cells.append(t)
    rows.append(np.hstack(cells))
for s in range(0, len(rows), 8): cv2.imwrite(str(D / f"sheet{s // 8}.jpg"), np.vstack(rows[s:s + 8]), [cv2.IMWRITE_JPEG_QUALITY, 82])
print((len(rows) + 7) // 8, "sheets")
