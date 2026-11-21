# strip.py <session> <raw|final> "no,no,.." [f0 f1 step] — body crops around contact, one row per stroke, to pick the
# frame where ball meets strings (for refine.json) or to double-check a label. Default frames -8..+4 around the stored contact.
# -> work/<s>/strip.jpg
# strip.py <session> <raw|final> "no,no,.." --stages — the pre-labelling skeleton check: one row per stroke, four whole frames
# (ready, backswing end, contact, finish) with the full skeleton drawn on them, right side orange and left side blue (the same as the web page and the highlight reel). Look for a body
# that is mirrored (colours swap sides while the person does not) or a skeleton on someone else. -> work/<s>/stages.jpg
import sys, cv2, numpy as np
from common import FPS, PORTRAIT, session, work, web, load
from platform_util import imwrite

STAGES = "--stages" in sys.argv; sys.argv = [a for a in sys.argv if a != "--stages"]  # a flag, so it must not shift f0 f1 step
s = session(); which = sys.argv[2]; nos = [int(x) for x in sys.argv[3].split(",")]
f0, f1, st = (int(x) for x in sys.argv[4:7]) if len(sys.argv) > 6 else (-8, 4, 1)
D = web(s); d = load(D / ("strokes_raw.json" if which == "raw" else "strokes.json"))

if STAGES:
    TH, MINVIS = 320, 0.3  # tile height; landmarks below this visibility are not drawn (annotate.py uses the same)
    LEFT, RIGHT, MID = (255, 130, 30), (30, 150, 255), (230, 230, 230)  # BGR blue / orange / neutral: right orange, left blue, like web/index.html and highlights.py
    # the 17 points of common.KEEP: odd index = left side (landmark 11, 13, 15, 23, ...), even = right. A bone inside one side takes that side's colour.
    BONES = [(1, 2), (1, 3), (3, 5), (2, 4), (4, 6), (1, 7), (2, 8), (7, 8), (7, 9), (9, 11), (8, 10), (10, 12), (11, 13), (13, 15), (11, 15), (12, 14), (14, 16), (12, 16)]

    def stage_tile(im, pose, label, none="no skeleton"):
        t = cv2.resize(im, (round(im.shape[1] * TH / im.shape[0]), TH)); h, w = t.shape[:2]
        pt = lambda q: (int(q[0] * w), int(q[1] * h))
        ok = pose is not None and sum(q[2] >= MINVIS for q in pose) > 0
        for a, b in BONES if ok else []:
            if pose[a][2] >= MINVIS and pose[b][2] >= MINVIS:
                col = MID if a % 2 != b % 2 else LEFT if a % 2 else RIGHT
                cv2.line(t, pt(pose[a]), pt(pose[b]), (0, 0, 0), 7, cv2.LINE_AA); cv2.line(t, pt(pose[a]), pt(pose[b]), col, 3, cv2.LINE_AA)  # dark outline: readable on bright and dark pictures
        for q in pose if ok else []:
            if q[2] >= MINVIS: cv2.circle(t, pt(q), 5, (0, 0, 0), -1, cv2.LINE_AA); cv2.circle(t, pt(q), 3, (255, 255, 255), -1, cv2.LINE_AA)
        if not ok: cv2.putText(t, none, (w // 2 - 50, h // 2), 0, 0.6, (200, 200, 200), 2)
        cv2.putText(t, label, (4, 18), 0, 0.55, (0, 255, 255), 2)
        return t

    rows = []
    for n in nos:
        r = d[n - 1]; c = r["contact"]; nf = len(r["frames"]); clip = D / r["src"]
        back = c - round(r["prep"] * FPS) if r.get("prep") is not None else c - 30  # backswing end; without a prep time, 0.5 s before contact
        wanted = [("ready", c - 48), ("backswing", back), ("contact", c), ("finish", c + 30)]
        wanted = [(name, min(max(i, 0), nf - 1)) for name, i in wanted]
        got, cap = {}, cv2.VideoCapture(str(clip)) if clip.is_file() else None
        for i in range(nf) if cap is not None and cap.isOpened() else []:
            ok, im = cap.read()
            if not ok: break
            if i in {k for _, k in wanted}: got[i] = im
        if cap is not None: cap.release()
        real = set(got)
        if got and any(k not in got for _, k in wanted):  # the clip ended early: its last frame stands in, without a skeleton (it belongs to another frame)
            last = got[max(got)]; got = {k: got.get(k, last) for _, k in wanted}
        if not got:
            print(f"沒有原片 {clip.name}：#{n} 畫在灰底上，看不出有沒有追錯人", file=sys.stderr)
            Ww, Hh = r.get("size") or PORTRAIT; blank = np.full((Hh, Ww, 3), 96, np.uint8); got = {k: blank.copy() for _, k in wanted}
        rows.append(np.hstack([stage_tile(got[k], r["frames"][k] if k in real or not real else None, f"#{n} {name} {k - c:+d}", "no skeleton" if k in real or not real else "clip ended") for name, k in wanted]))
    width = max(x.shape[1] for x in rows)  # clips of different shapes: pad on the right
    out = work(s) / "stages.jpg"; out.parent.mkdir(parents=True, exist_ok=True)
    imwrite(out, np.vstack([np.pad(x, ((0, 0), (0, width - x.shape[1]), (0, 0))) for x in rows])) or sys.exit(f"could not write {out}"); print(out)
    sys.exit(0)

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
out = work(s) / "strip.jpg"; imwrite(out, np.vstack(rows)) or sys.exit(f"could not write {out}"); print(out)
