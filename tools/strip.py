# strip.py <session> <raw|final> "no,no,.." [f0 f1 step] — body crops around contact, one row per stroke, to pick the
# frame where ball meets strings (for refine.json) or to double-check a label. Default frames -8..+4 around the stored contact.
# -> work/<s>/strip.jpg
import sys, cv2, numpy as np
from common import session, work, web, load
from platform_util import imwrite

s = session(); which = sys.argv[2]; nos = [int(x) for x in sys.argv[3].split(",")]
f0, f1, st = (int(x) for x in sys.argv[4:7]) if len(sys.argv) > 6 else (-8, 4, 1)
D = web(s); d = load(D / ("strokes_raw.json" if which == "raw" else "strokes.json"))
rows = []
for n in nos:
    r = d[n - 1]; cap = cv2.VideoCapture(str(D / r["src"])); fr = []
    while True:
        ok, im = cap.read()
        if not ok: break
        fr.append(im)
    Hh, Ww = fr[0].shape[:2]; c = r["contact"]; p = r["frames"][c] or r["frames"][c - 2]
    cx = int(np.mean([q[0] for q in p[:9]]) * Ww); cy = int(np.mean([q[1] for q in p[:9]]) * Hh); R = int(Hh * 0.17)
    tiles = []
    for i in range(c + f0, c + f1 + 1, st):
        im = cv2.copyMakeBorder(fr[min(max(i, 0), len(fr) - 1)], R, R, R, R, cv2.BORDER_CONSTANT)[cy:cy + 2 * R, cx:cx + 2 * R]
        im = cv2.resize(im, (200, 200)); cv2.putText(im, f"#{n} {i - c:+d}", (4, 18), 0, 0.55, (0, 255, 255), 2); tiles.append(im)
    rows.append(np.hstack(tiles))
out = work(s) / "strip.jpg"; imwrite(out, np.vstack(rows)); print(out)
