# pose_full.py <proxy.mp4> <model.task> <out/pose.npy> [people=1] — MediaPipe pose for up to N people, one file per tracked person.
# Track 0 (the person seen most) -> pose.npy / pose_world.npy, track k -> pose_t<k>.npy / pose_world_t<k>.npy.
# pose: frames x 33 x (x, y, visibility) normalized; world: frames x 33 x (x, y, z) metres, hip-centred. NaN where the track is unseen.
# Identity is a closed set of N slots: each frame, detections go to slots by hip position + torso colour, so someone who walks
# away and comes back gets their old slot. Which slot is which friend is decided later by eye (candidates.py -> players.txt).
import itertools, sys
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
    T = Tracker(N); rows = []; wrows = []; n = 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        img = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=img), int(n * 1000 / 60))
        fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy()
        for k, a, w in zip(T.step([describe(a, img) for a in r.pose_landmarks]), r.pose_landmarks, r.pose_world_landmarks):
            if k >= 0: fr[k] = [[q.x, q.y, q.visibility] for q in a]; fw[k] = [[q.x, q.y, q.z] for q in w]
        rows.append(fr); wrows.append(fw); n += 1
        if n % 6000 == 0: print(n, flush=True)
    P, Wl = np.array(rows).reshape(n, N, 33, 3), np.array(wrows).reshape(n, N, 33, 3)
    seen = (~np.isnan(P[:, :, 0, 0])).sum(0); order = [k for k in np.argsort(-seen, kind="stable") if seen[k]] or [0]
    for i, k in reversed(list(enumerate(order))):  # pose.npy last: prep.sh treats it as "this video is done"
        sfx = "" if i == 0 else f"_t{i}"
        np.save(out.replace("pose.npy", f"pose_world{sfx}.npy"), Wl[:, k]); np.save(out.replace("pose.npy", f"pose{sfx}.npy"), P[:, k])
    print("done", n, "frames; frames seen per track:", [int(seen[k]) for k in order])


if __name__ == "__main__":
    main()
