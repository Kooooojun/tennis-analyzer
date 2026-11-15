# pose_full.py <proxy.mp4> <model.task> <out/pose.npy> [people=1] — MediaPipe pose for up to N people, one file per tracked person.
# Track 0 (the person seen most) -> pose.npy / pose_world.npy, track k -> pose_t<k>.npy / pose_world_t<k>.npy.
# pose: frames x 33 x (x, y, visibility) normalized; world: frames x 33 x (x, y, z) metres, hip-centred. NaN where the track is unseen.
# Identity is a closed set of N slots: each frame, detections go to slots by hip position + torso colour, so someone who walks
# away and comes back gets their old slot. Which slot is which friend is decided later by eye (candidates.py -> players.txt).
import itertools, sys, warnings
import numpy as np


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


def main():
    import subprocess, cv2, mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    src, model, out = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    c = cv2.VideoCapture(src); W, H = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)); c.release()  # 540x960 or 960x540
    if not (W and H): sys.exit(f"cannot read {src}")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=model), running_mode=vision.RunningMode.VIDEO,
                                                   num_poses=N, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3))
    # num_poses > 1 re-detects every frame while fewer people than N are in view, and its landmarks are coarser: on wall-1 the
    # wrist speed at contact dropped (hit recall 88% -> 79%). A second, single-person landmarker keeps frame-to-frame tracking;
    # its skeleton replaces the slot standing in the same place. Costs a second model pass (about 2x time).
    one = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=model), running_mode=vision.RunningMode.VIDEO,
                                                    num_poses=1, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3)) if N > 1 else None
    T = Tracker(N); rows = []; wrows = []; crows = []; n = 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        img = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        mi = mp.Image(image_format=mp.ImageFormat.SRGB, data=img); r = lm.detect_for_video(mi, int(n * 1000 / 60))
        fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy(); fc = np.full((N, 3), np.nan)
        ds = [describe(a, img) for a in r.pose_landmarks]; sl = [None] * N
        for k, d, a, w in zip(T.step(ds), ds, r.pose_landmarks, r.pose_world_landmarks):
            if k >= 0: fr[k] = [[q.x, q.y, q.visibility] for q in a]; fw[k] = [[q.x, q.y, q.z] for q in w]; fc[k] = d["color"]; sl[k] = d
        r1 = one.detect_for_video(mi, int(n * 1000 / 60)) if one else None
        if r1 and r1.pose_landmarks and (k := same_person(describe(r1.pose_landmarks[0], img), sl)) is not None:
            fr[k] = [[q.x, q.y, q.visibility] for q in r1.pose_landmarks[0]]; fw[k] = [[q.x, q.y, q.z] for q in r1.pose_world_landmarks[0]]
        rows.append(fr); wrows.append(fw); crows.append(fc); n += 1
        if n % 6000 == 0: print(n, flush=True)
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
    from pathlib import Path
    for old in Path(out).parent.glob("pose*_t*.npy"):  # a re-run may find fewer people: stale extra tracks would be read as people
        if int(old.stem.rsplit("_t", 1)[1]) >= len(tr): old.unlink()
    for i, (p, w) in reversed(list(enumerate(tr))):  # pose.npy last: prep.sh treats it as "this video is done"
        sfx = "" if i == 0 else f"_t{i}"
        np.save(out.replace("pose.npy", f"pose_world{sfx}.npy"), w); np.save(out.replace("pose.npy", f"pose{sfx}.npy"), p)
    print("done", n, "frames; frames seen per slot:", S.sum(0).tolist(), "-> per track after joining one person's slots:",
          [int((~np.isnan(p[:, 0, 0])).sum()) for p, _ in tr])


if __name__ == "__main__":
    main()
