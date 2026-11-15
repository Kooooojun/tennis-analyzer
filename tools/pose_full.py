# pose_full.py <proxy.mp4> <model.task> <out/pose.npy> [people=1] — MediaPipe pose for up to N people, one file per tracked person.
# Track 0 (the person seen most) -> pose.npy / pose_world.npy, track k -> pose_t<k>.npy / pose_world_t<k>.npy.
# pose: frames x 33 x (x, y, visibility) normalized; world: frames x 33 x (x, y, z) metres, hip-centred. NaN where the track is unseen.
# Identity is a closed set of N slots: each frame, detections go to slots by hip position + torso colour, so someone who walks
# away and comes back gets their old slot. Which slot is which friend is decided later by eye (candidates.py -> players.txt).
import itertools, sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with -I: the script's folder is not on sys.path
from platform_util import unlink


class Tracker:
    NEW = 1.0     # cost of opening an unused slot
    DROP = 1e3    # a detection is dropped only when there are more than N
    COL = 40.0    # Lab distance that costs as much as moving one torso length

    def __init__(self, n):
        self.n = n; self.pos = [None] * n; self.col = [None] * n; self.last = [0] * n; self.f = 0

    def cost(self, k, d):
        if self.pos[k] is None: return self.NEW
        gap = self.f - self.last[k]
        dp = np.hypot(*np.subtract(d["pos"], self.pos[k])) / max(d["scale"], 0.03) / (1 + gap / 15)  # lost a while: position counts less
        return dp + np.linalg.norm(np.subtract(d["color"], self.col[k])) / self.COL

    def step(self, dets):
        """dets: [{pos: (x, y) in frame heights, scale: torso length, color: Lab}] -> slot per detection, -1 = dropped."""
        self.f += 1; keep = []
        for i, d in enumerate(dets[:6]):  # same place and colour as one already kept = duplicate skeleton
            if not any(np.hypot(*np.subtract(d["pos"], dets[j]["pos"])) < 0.5 * d["scale"]
                       and np.linalg.norm(np.subtract(d["color"], dets[j]["color"])) < self.COL / 2 for j in keep):
                keep.append(i)
        C = [[self.cost(k, dets[i]) for k in range(self.n)] + [self.DROP] * len(keep) for i in keep]
        best = min(itertools.permutations(range(self.n + len(keep)), len(keep)), key=lambda p: sum(C[a][b] for a, b in enumerate(p)), default=())
        out = [-1] * len(dets)
        for a, k in zip(keep, best):
            if k >= self.n: continue
            d = dets[a]; out[a] = k; self.pos[k] = d["pos"]; self.last[k] = self.f
            self.col[k] = np.array(d["color"], float) if self.col[k] is None else 0.95 * self.col[k] + 0.05 * np.array(d["color"], float)
        return out


def merge(seen, col, overlap=0.1):
    """seen (frames, slots) bool, col (slots, 3) mean shirt Lab -> groups of slots that are one person, biggest slot first.
    One person alone in the frame drifts between free slots; slots that almost never coexist (< `overlap` of the smaller one's
    frames) and wear the same colour are joined. Two people seen together, or in different shirts, stay apart."""
    groups = []
    for k in np.argsort(-seen.sum(0), kind="stable"):
        g = next((g for g in groups if seen[:, k].any() and np.linalg.norm(col[k] - col[g[0]]) < Tracker.COL / 2
                  and (seen[:, k] & seen[:, g].any(1)).sum() < overlap * seen[:, k].sum()), None)
        if g is None: groups.append([int(k)])
        else: g.append(int(k))
    return groups


def same_person(d, slots):
    """Slot (index into slots: describe() dicts, None = empty) whose hip is within half a torso of d's, nearest first; None = no one."""
    near = [(np.hypot(*np.subtract(d["pos"], q["pos"])), k) for k, q in enumerate(slots) if q is not None]
    near = [x for x in near if x[0] < 0.5 * d["scale"]]
    return min(near)[1] if near else None


def describe(lm, img):
    """Hip centre and torso length in frame heights, and mean Lab colour of the shirt (box between shoulders and hips)."""
    import cv2
    H, W = img.shape[:2]; p = np.array([[lm[i].x * W, lm[i].y * H] for i in (11, 12, 23, 24)])
    sh, hp = p[:2].mean(0), p[2:].mean(0); L = max(np.hypot(*(sh - hp)), 4.0)
    cx = p[:, 0].mean(); hw = max(np.ptp(p[:, 0]) * 0.35, L * 0.15)
    x0, x1 = int(np.clip(cx - hw, 0, W - 1)), int(np.clip(cx + hw, 1, W)); y0, y1 = int(np.clip(sh[1] + 0.15 * L, 0, H - 1)), int(np.clip(hp[1] - 0.15 * L, 1, H))
    crop = img[min(y0, y1 - 1):max(y1, y0 + 1), min(x0, x1 - 1):max(x1, x0 + 1)]
    lab = cv2.cvtColor(crop.astype(np.float32) / 255, cv2.COLOR_RGB2Lab).reshape(-1, 3).mean(0) if crop.size else np.zeros(3)
    return dict(pos=(hp[0] / H, hp[1] / H), scale=L / H, color=lab)


METHOD = "2"  # bump when the pose algorithm changes: prep.py re-runs pose when work/<video>/pose_method.txt differs
CROP_SIDE, CROP_MIN, TILE, TILE_EVERY = 640, 360, 600, 5  # crop scaled to 640 px; box >= 360 px; 600 px search tiles, searched every 5th frame


def to60(A, fps, n60):
    """Rows at source frames i/fps -> rows at 60 fps frames j/60, n60 of them. Linear in time, both neighbours must be
    finite (a NaN side gives NaN, never half a skeleton); nothing past the last source frame (NaN). fps >= 50 = as is."""
    if fps >= 50:  # already on the 60 fps grid; a decoder that came up a frame short is padded, never shifted
        return A[:n60] if len(A) >= n60 else np.concatenate([A, np.full((n60 - len(A), *A.shape[1:]), np.nan, A.dtype)])
    x = np.arange(n60) * fps / 60; i = np.floor(x).astype(int); w = (x - i).reshape(-1, *[1] * (A.ndim - 1))
    out = np.full((n60, *A.shape[1:]), np.nan, A.dtype); ok = i < len(A)
    j = np.minimum(i + 1, len(A) - 1)
    lo, hi = A[np.minimum(i, len(A) - 1)], A[j]
    exact = (w == 0).reshape(-1)
    v = np.where(w == 0, lo, lo * (1 - w) + hi * w)
    v[~exact & (i + 1 >= len(A))] = np.nan  # needs a right neighbour that does not exist
    out[ok] = v[ok]
    return out


def crop_box(xy, W, H, min_side=CROP_MIN):
    """Pixel landmarks (k, 2), NaN allowed -> square (x0, y0, side) of 2x the skeleton height, >= min_side, inside the frame."""
    xy = xy[np.isfinite(xy).all(1)]
    if not len(xy): return None
    c = (xy.min(0) + xy.max(0)) / 2; ext = np.ptp(xy, 0)
    side = int(min(max(min_side, 2 * ext[1], 1.6 * ext[0]), H, W))
    return int(np.clip(round(c[0] - side / 2), 0, W - side)), int(np.clip(round(c[1] - side / 2), 0, H - side)), side


def crop_to_full(q, box, W, H):
    """Landmarks normalized to the square crop (k, 2) -> normalized to the full frame (x by W, y by H)."""
    x0, y0, side = box
    return (np.asarray(q, float) * side + (x0, y0)) / (W, H)


def use_crop(found):
    """found: people seen per sampled full frame. Crop when the full frame misses everyone in most of them (far camera)."""
    return np.mean(np.asarray(found) > 0) < 0.6


def frames(cmd, W, H):
    import subprocess
    p = subprocess.Popen(["ffmpeg", "-v", "error", *cmd, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    while len(b := p.stdout.read(W * H * 3)) == W * H * 3:  # one frame at a time: a 1080p clip never sits in memory
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.stdout.close(); p.wait()


def main():
    import types, cv2, mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    src, model, out = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    source = sys.argv[5] if len(sys.argv) > 5 else None  # the original video: low-fps sources run at their own rate, far cameras get crops
    c = cv2.VideoCapture(src); W, H = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))  # 540x960 or 960x540
    n60 = int(c.get(cv2.CAP_PROP_FRAME_COUNT)); c.release()
    if not (W and H): sys.exit(f"cannot read {src}")
    mk = lambda n, mode="VIDEO": vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=model),
        running_mode=getattr(vision.RunningMode, mode), num_poses=n, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3))
    img_of = lambda a: mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(a))
    fps, crop, SW, SH = 60, False, W, H
    ft = Path(out).parent / "src_fps.txt"  # written by prep.py (whole fps); the exact rate comes from the source itself
    if source and ft.is_file():
        c = cv2.VideoCapture(source); r = c.get(cv2.CAP_PROP_FPS); SW, SH = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)); c.release()
        if (SW > SH) != (W > H): SW, SH = SH, SW  # rotation metadata: ffmpeg outputs it upright, like the proxy
        if ft.read_text(encoding="utf-8").strip().isdigit() and int(ft.read_text(encoding="utf-8").strip()) < 50 and r > 0: fps = r
        probe = mk(N, "IMAGE"); step = max(1, n60 // 60)
        crop = use_crop([len(probe.detect(img_of(f)).pose_landmarks) for f in frames(["-i", src, "-vf", f"select=not(mod(n\\,{step}))", "-vsync", "0"], W, H)])
        probe.close()
    print(f"mode: {'crop' if crop else 'full frame'}, {fps:.3f} fps", flush=True)
    T = Tracker(N); rows = []; wrows = []; crows = []; n = 0
    if not crop:
        lm = mk(N)
        # num_poses > 1 re-detects every frame while fewer people than N are in view, and its landmarks are coarser: on wall-1 the
        # wrist speed at contact dropped (hit recall 88% -> 79%). A second, single-person landmarker keeps frame-to-frame tracking;
        # its skeleton replaces the slot standing in the same place. Costs a second model pass (about 2x time).
        one = mk(1) if N > 1 else None
        it = frames(["-i", src], W, H) if fps >= 50 else frames(["-i", source, "-vf", f"scale={W}:{H}"], W, H)
        for img in it:
            mi = img_of(img); ts = int(n * 1000 / fps); r = lm.detect_for_video(mi, ts)
            fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy(); fc = np.full((N, 3), np.nan)
            ds = [describe(a, img) for a in r.pose_landmarks]; sl = [None] * N
            for k, d, a, w in zip(T.step(ds), ds, r.pose_landmarks, r.pose_world_landmarks):
                if k >= 0: fr[k] = [[q.x, q.y, q.visibility] for q in a]; fw[k] = [[q.x, q.y, q.z] for q in w]; fc[k] = d["color"]; sl[k] = d
            r1 = one.detect_for_video(mi, ts) if one else None
            if r1 and r1.pose_landmarks and (k := same_person(describe(r1.pose_landmarks[0], img), sl)) is not None:
                fr[k] = [[q.x, q.y, q.visibility] for q in r1.pose_landmarks[0]]; fw[k] = [[q.x, q.y, q.z] for q in r1.pose_world_landmarks[0]]
            rows.append(fr); wrows.append(fw); crows.append(fc); n += 1
            if n % 6000 == 0: print(n, flush=True)
    else:
        # Far camera (people ~100 px on the proxy): full-resolution source. Each slot is re-found in a square crop around its last
        # skeleton, scaled to 640 px, by a single-person landmarker (this replaces the second model pass above); empty slots are
        # searched in overlapping 600 px tiles every TILE_EVERY frames. All skeletons then go through the same Tracker.
        one, many = mk(1, "IMAGE"), mk(N, "IMAGE"); box = [None] * N
        tiles = [(x, y) for y in sorted({*range(0, SH - TILE, TILE // 2), SH - TILE}) for x in sorted({*range(0, SW - TILE, TILE // 2), SW - TILE})]
        def look(img, b, det):  # skeletons in a crop, as full-frame normalized landmarks
            r = det.detect(img_of(cv2.resize(img[b[1]:b[1] + b[2], b[0]:b[0] + b[2]], (CROP_SIDE, CROP_SIDE))))
            return [(np.c_[crop_to_full([[q.x, q.y] for q in a], b, SW, SH), [q.visibility for q in a]], [[q.x, q.y, q.z] for q in w])
                    for a, w in zip(r.pose_landmarks, r.pose_world_landmarks)]
        for img in frames(["-i", source] + (["-vf", "fps=60"] if fps >= 50 else []), SW, SH):
            got = [x for b in box if b for x in look(img, b, one)]
            if (None in box and n % TILE_EVERY == 0) or not got:
                found = [x for t in tiles for x in look(img, (*t, TILE), many)]  # tallest first: crowd and far background lose
                got += sorted(found, key=lambda x: -np.ptp(x[0][:, 1]))[:N]
            lms = [[types.SimpleNamespace(x=v[0], y=v[1], visibility=v[2]) for v in a] for a, _ in got]
            ds = [describe(a, img) for a in lms]
            fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy(); fc = np.full((N, 3), np.nan); box = [None] * N
            for k, d, (a, w) in zip(T.step(ds), ds, got):
                if k >= 0: fr[k] = a; fw[k] = w; fc[k] = d["color"]; box[k] = crop_box(a[:, :2] * (SW, SH), SW, SH)
            rows.append(fr); wrows.append(fw); crows.append(fc); n += 1
            if n % 6000 == 0: print(n, flush=True)
    if fps < 50 or crop:  # back on the proxy's 60 fps frame numbers, which every later step indexes by
        rows, wrows, crows = (list(to60(np.array(x), fps, n60)) for x in (rows, wrows, crows)); n = n60
    P, Wl = np.array(rows).reshape(n, N, 33, 3), np.array(wrows).reshape(n, N, 33, 3)
    S = ~np.isnan(P[:, :, 0, 0]); C = np.array(crows).reshape(n, N, 3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning); col = np.nanmean(C, 0)  # NaN for a slot never used: merge() skips it
    tr = []
    for g in merge(S, col):  # per frame the biggest slot of the group wins (the rare frames two of them overlap are duplicates)
        p, w = P[:, g[0]].copy(), Wl[:, g[0]].copy()
        for k in g[1:]: m = np.isnan(p[:, 0, 0]) & S[:, k]; p[m], w[m] = P[m, k], Wl[m, k]
        tr.append((p, w))
    tr = sorted([t for t in tr if (~np.isnan(t[0][:, 0, 0])).any()], key=lambda t: -(~np.isnan(t[0][:, 0, 0])).sum()) or tr[:1]
    out = Path(out)
    for old in out.parent.glob("pose*_t*.npy"):  # a re-run may find fewer people: stale extra tracks would be read as people
        if int(old.stem.rsplit("_t", 1)[1]) >= len(tr):
            try: unlink(old)
            except PermissionError: sys.exit(f"cannot delete {old} (open in another program?); it would be read as a person")
    for i, (p, w) in reversed(list(enumerate(tr))):  # pose.npy last: prep.sh treats it as "this video is done"
        sfx = "" if i == 0 else f"_t{i}"
        np.save(out.with_name(f"pose_world{sfx}.npy"), w); np.save(out.with_name(f"pose{sfx}.npy"), p)
    print("done", n, "frames; frames seen per slot:", S.sum(0).tolist(), "-> per track after joining one person's slots:",
          [int((~np.isnan(p[:, 0, 0])).sum()) for p, _ in tr])


if __name__ == "__main__":
    main()
