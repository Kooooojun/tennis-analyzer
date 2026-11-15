# ct_pose.py <cam 1-4> <start: seconds since 19:49:00 session clock> <dur s> <out.npz>
# MediaPipe pose on one CalTennis camera. Crop: square box around last frame's skeleton (2x its height, >= 360 px),
# scaled to 640 px; if that finds no one, overlapping 600 px tiles (tallest person). Output in full-frame pixels.
import sys, glob, re, subprocess, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

D = "testset/raw/datasets/caltennis/01_28_2026_19_00_ath"
cam, t0, dur, out = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
f = glob.glob(f"{D}/*_X_{cam}_*.mp4")[0]
h, m, s = map(int, re.search(r"01_28_2026_(\d+)_(\d+)_(\d+)_000", f).groups())
start = (h - 19) * 3600 + (m - 49) * 60 + s  # camera start on the shared clock (s since 19:49:00)
ts = np.load(f.replace(".mp4", "_timestamps.npy")) / 1000 + start
i0 = int(np.searchsorted(ts, t0)); n = int(np.searchsorted(ts, t0 + dur)) - i0
W, H = 1920, 1088
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", f, "-vf", f"select=gte(n\\,{i0})", "-vsync", "0", "-frames:v", str(n),
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
mk = lambda: vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path="models/pose_heavy.task"), running_mode=vision.RunningMode.IMAGE, num_poses=3))
det = mk()
L2 = np.full((n, 33, 3), np.nan); WD = np.full((n, 33, 3), np.nan); box = None; used = np.zeros(n, int)


def run(img):
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)))
    return list(zip(r.pose_landmarks, r.pose_world_landmarks))


for k in range(n):
    buf = p.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    img = np.frombuffer(buf, np.uint8).reshape(H, W, 3); got = None
    if box is not None:
        x0, y0, side = box; S = 640 / side
        crop = cv2.resize(img[y0:y0 + side, x0:x0 + side], (640, 640))
        rs = run(crop)
        if rs:
            lm, wd = max(rs, key=lambda r: np.ptp([q.y for q in r[0]]))
            got = (np.array([[x0 + q.x * side, y0 + q.y * side, q.visibility] for q in lm]), wd); used[k] = 1
    if got is None:  # reacquire: 600 px tiles (person ~200 px is too small for the full frame), tallest skeleton wins
        best = None
        for y0 in (0, 244, 488):
            for x0 in range(0, W - 599, 330):
                for lm, wd in run(cv2.resize(img[y0:y0 + 600, x0:x0 + 600], (640, 640))):
                    a = np.array([[x0 + q.x * 600, y0 + q.y * 600, q.visibility] for q in lm])
                    if best is None or np.ptp(a[:, 1]) > np.ptp(best[0][:, 1]): best = (a, wd)
        if best is not None: got = best; used[k] = 2
    if got is None: box = None; continue
    L2[k] = got[0]; WD[k] = [[q.x, q.y, q.z] for q in got[1]]
    xy = got[0][:, :2]; c = (xy.min(0) + xy.max(0)) / 2; side = int(max(360, 2 * np.ptp(xy[:, 1]), 1.6 * np.ptp(xy[:, 0])))
    side = min(side, H); x0 = int(np.clip(c[0] - side / 2, 0, W - side)); y0 = int(np.clip(c[1] - side / 2, 0, H - side)); box = (x0, y0, side)
np.savez(out, t=ts[i0:i0 + n], lm=L2, world=WD, used=used)
print(cam, n, "found", np.isfinite(L2[:, 0, 0]).mean().round(3), "crop", (used == 1).mean().round(3))
