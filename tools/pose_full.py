# pose_full.py <proxy.mp4> <model.task> <out/pose.npy> [people=1] — MediaPipe pose for up to N people, one file per tracked person.
# Track 0 (the person seen most) -> pose.npy / pose_world.npy, track k -> pose_t<k>.npy / pose_world_t<k>.npy.
# pose: frames x 33 x (x, y, visibility) normalized; world: frames x 33 x (x, y, z) metres, hip-centred. NaN where the track is unseen.
# Identity is a closed set of N slots: each frame, detections go to slots by hip position + torso colour, so someone who walks
# away and comes back gets their old slot. Which slot is which friend is decided later by eye (candidates.py -> players.txt).
import contextlib, itertools, sys, warnings
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with -I: the script's folder is not on sys.path
from platform_util import unlink
from proxy import video_filter, map_pose


class Tracker:
    NEW = 1.0     # cost of opening an unused slot
    DROP = 1e3    # a detection is dropped only when there are more than N
    COL = 40.0    # Lab distance that costs as much as moving one torso length

    def __init__(self, n):
        self.n = n; self.pos = [None] * n; self.col = [None] * n; self.last = [0] * n; self.f = 0
        self.vel = np.zeros((n, 2)); self.depth = [None] * n; self.scale = [None] * n; self.reid = False; self.motion = False

    def cost(self, k, d):
        if self.pos[k] is None: return self.NEW
        color = np.linalg.norm(np.subtract(d["color"], self.col[k])) / self.COL
        if self.reid: return color
        gap = self.f - self.last[k]
        pred = np.asarray(self.pos[k]) + (self.vel[k] * gap if gap < 5 and (self.n > 2 or self.motion) else 0)
        dp = np.hypot(*np.subtract(d["pos"], pred)) / max(d["scale"], 0.03) / (1 + gap / 15)
        # 兩槽保留原成本，局部誤色才不會永久占住第二個身分。
        if self.n == 2: return dp + color
        depth = abs(d["pos"][1] - self.depth[k]) / max(d["scale"], self.scale[k], 0.03)
        size = abs(np.log(max(d["scale"], 0.03) / max(self.scale[k], 0.03)))
        # 連續運動優先；大跳躍可能是剪接，位置不能蓋過外觀與長期深度。
        continuity = max(1 - dp, 0) * max(1 - color, 0) if gap == 1 else 0
        # 全員失聯後的區域會過時，不能長期壓過相同外觀。
        score = min(dp, 1) - continuity + 0.5 * (depth + size) / max((self.f - max(self.last)) / 15, 1) + color
        # 區域參照不能逼出原可接回的身分；微小遞增項保留封頂後的排序。
        if (color < 0.5 or dp + color <= self.NEW) and any(p is None for p in self.pos):
            return min(score, self.NEW) - 1e-6 / (1 + max(score, 0))
        return score

    def step(self, dets):
        """dets: [{pos: (x, y) in frame heights, scale: torso length, color: Lab}] -> slot per detection, -1 = dropped."""
        self.f += 1; keep = []
        for i, d in enumerate(dets[:6]):  # same place and colour as one already kept = duplicate skeleton
            if not any(np.hypot(*np.subtract(d["pos"], dets[j]["pos"])) < 0.5 * d["scale"]
                       and np.linalg.norm(np.subtract(d["color"], dets[j]["color"])) < self.COL / 2 for j in keep):
                keep.append(i)
        self.reid = False
        self.motion = False
        if self.n == 2 and len(keep) == 2 and all(p is not None for p in self.pos):
            delta = np.subtract(self.pos[1], self.pos[0])
            self.motion = np.dot(delta, self.vel[0]) > 0 > np.dot(delta, self.vel[1]) and np.linalg.norm(
                np.subtract(dets[keep[0]]["color"], dets[keep[1]]["color"])) < self.COL / 2
        if self.n > 1 and len(keep) == self.n and all(c is not None for c in self.col):
            colors = np.array([[np.linalg.norm(np.subtract(dets[i]["color"], c)) for c in self.col] for i in keep])
            nearest = colors.argmin(1); ordered = np.sort(colors, axis=1)
            # 全員外觀皆有唯一對應才跨區接軌；相似外觀仍依運動與深度配對。
            self.reid = len(set(nearest)) == self.n and bool(np.all(ordered[:, 0] < self.COL / 2)
                        and np.all(ordered[:, 1] - ordered[:, 0] > self.COL / 2))
        # 兩人皆同步跳離原區域，才把明確外觀當作剪接接軌。
        if self.reid and self.n == 2:
            self.reid = all(self.f - self.last[k] == 1 and np.hypot(*np.subtract(dets[i]["pos"], self.pos[k])) > max(dets[i]["scale"], 0.03)
                            for i, k in zip(keep, nearest))
        C = [[self.cost(k, dets[i]) for k in range(self.n)] + [self.DROP] * len(keep) for i in keep]
        best = min(itertools.permutations(range(self.n + len(keep)), len(keep)), key=lambda p: sum(C[a][b] for a, b in enumerate(p)), default=())
        out = [-1] * len(dets)
        for a, k in zip(keep, best):
            if k >= self.n: continue
            d = dets[a]; out[a] = k
            if self.pos[k] is not None:
                gap = self.f - self.last[k]; v = np.subtract(d["pos"], self.pos[k]) / gap
                self.vel[k] = 0.5 * self.vel[k] + 0.5 * v if gap < 5 else np.zeros(2)
                self.vel[k] *= min(1, max(d["scale"], 0.03) / max(np.hypot(*self.vel[k]), 0.03))
            self.pos[k] = d["pos"]; self.last[k] = self.f
            # 慢更新保留身分參照，避免短暫錯配迅速污染整個槽。
            alpha = 0.05 if self.n == 2 else 0.005
            self.col[k] = np.array(d["color"], float) if self.col[k] is None else (1 - alpha) * self.col[k] + alpha * np.array(d["color"], float)
            self.depth[k] = d["pos"][1] if self.depth[k] is None else 0.995 * self.depth[k] + 0.005 * d["pos"][1]
            self.scale[k] = d["scale"] if self.scale[k] is None else 0.995 * self.scale[k] + 0.005 * d["scale"]
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


METHOD = "4"  # bump when the pose algorithm changes: prep.py re-runs pose when work/<video>/pose_method.txt differs
CROP_SIDE, CROP_MIN, TILE, TILE_EVERY = 640, 360, 600, 5  # crop scaled to 640 px; box >= 360 px; 600 px search tiles, searched every 5th frame


def to60(A, fps, n60, cut=None):
    """Rows at source frames i/fps -> rows at 60 fps frames j/60, n60 of them. Linear in time, both neighbours must be
    finite (a NaN side gives NaN, never half a skeleton); nothing past the last source frame (NaN). fps >= 50 = as is.
    cut (len(A) - 1 bools): no interpolating between source frames i and i + 1 (a track that jumped to another person)."""
    if fps >= 50:  # already on the 60 fps grid; a decoder that came up a frame short is padded, never shifted
        return A[:n60] if len(A) >= n60 else np.concatenate([A, np.full((n60 - len(A), *A.shape[1:]), np.nan, A.dtype)])
    x = np.arange(n60) * fps / 60; i = np.floor(x).astype(int); w = (x - i).reshape(-1, *[1] * (A.ndim - 1))
    out = np.full((n60, *A.shape[1:]), np.nan, A.dtype); ok = i < len(A)
    j = np.minimum(i + 1, len(A) - 1)
    lo, hi = A[np.minimum(i, len(A) - 1)], A[j]
    exact = (w == 0).reshape(-1)
    v = np.where(w == 0, lo, lo * (1 - w) + hi * w)
    v[~exact & (i + 1 >= len(A))] = np.nan  # needs a right neighbour that does not exist
    if cut is not None and len(A) > 1:
        v[~exact & np.asarray(cut)[np.minimum(i, len(A) - 2)]] = np.nan
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


def distinct(cands, n, keep=(), aspect=1.0):
    """Skeletons (normalized (33, 3) landmarks, world) from overlapping tiles -> up to n different people, tallest first.
    One whose hip is within half a torso of a taller one, or of one in `keep` (found by a crop), is the same person seen twice."""
    def hip(a): return a[[23, 24], :2].mean(0) * (aspect, 1), max(np.hypot(*((a[[11, 12], :2].mean(0) - a[[23, 24], :2].mean(0)) * (aspect, 1))), 1e-3)
    out, seen = [], [hip(a) for a, _ in keep]
    for x in sorted(cands, key=lambda x: -np.ptp(x[0][:, 1])):
        h, L = hip(x[0])
        if len(out) < n and all(np.hypot(*(h - q)) >= 0.5 * max(L, M) for q, M in seen): out.append(x); seen.append((h, L))
    return out


def real(a, vmin=0.3):
    """Normalized (33, 3) landmarks -> is it a person: knees and ankles visibility >= vmin. A square crop scaled up finds
    skeletons in floodlights; on the far-camera dataset their leg visibility is 0.00 median, <= 0.06 at p95, players 0.44-0.69
    at p5 (trunk visibility does not split them: ghosts 0.38-0.94). One such skeleton keeps its crop box on the light."""
    return float(np.mean(a[[25, 26, 27, 28], 2])) >= vmin


def hip_torso(a, aspect):
    """Normalized (..., 33, 3) -> hip centre (..., 2) with x in frame heights, torso length (shoulders to hips)."""
    h = a[..., [23, 24], :2].mean(-2) * (aspect, 1)
    return h, np.hypot(*np.moveaxis(a[..., [11, 12], :2].mean(-2) * (aspect, 1) - h, -1, 0))


def keep(a, prev, aspect):
    """A skeleton found in the crop around a slot's last one (prev, None for a tile search) -> keep it. Legs hidden by the net,
    the frame edge or a crouch fail real(); hips within half a torso of where that slot stood a frame ago are the same person
    (a floodlight is never there). A new find, or one that jumped away with no legs, must pass real()."""
    if real(a): return True
    if prev is None: return False
    (h, L), (q, M) = hip_torso(a, aspect), hip_torso(prev, aspect)
    return bool(np.hypot(*(h - q)) < 0.5 * np.fmax(L, M))


def jumps(P, aspect, k=0.8):
    """Rows (n, 33, 3) of one track -> (n - 1) bools: hips moved more than k torsos between frame i and i + 1, i.e. the
    track switched person. A NaN side is False (to60 leaves it NaN anyway)."""
    h, L = hip_torso(np.asarray(P, float), aspect)
    with np.errstate(invalid="ignore"):
        return np.hypot(*(h[1:] - h[:-1]).T) > k * np.fmax(L[1:], L[:-1])


def correct_lr(P, W, aspect, fps=60):
    """Repair brief elbow/hand label reversals with reliable image poses on both sides, before fps interpolation.
    World labels change only when that independently estimated sequence has no internal switch and fits both boundaries.
    Long intervals and whole-body reversals have no trustworthy absolute reference and are left alone."""
    p, w = P.copy(), W.copy()
    limit = max(1, round(0.2 * fps))
    _, L = hip_torso(P, aspect); cut = jumps(P, aspect)
    def distance(a, b): return np.linalg.norm(a - b, axis=-1).sum(axis=-1)
    body_flip = np.zeros(max(0, len(P) - 1), bool)
    for xyz, scale in ((P[:, :, :2] * (aspect, 1), L),
                       (W, np.linalg.norm(W[:, [11, 12]].mean(1) - W[:, [23, 24]].mean(1), axis=1))):
        q = xyz[:, [11, 12, 23, 24]]
        gap = np.linalg.norm(q[:, [0, 2]] - q[:, [1, 3]], axis=2).mean(1)
        body_flip |= (distance(q[1:, [1, 0, 3, 2]], q[:-1]) < 0.5 * distance(q[1:], q[:-1])) & (gap[:-1] > 0.3 * scale[:-1])
    for left, right in (([13], [14]), ([15, 17, 19, 21], [16, 18, 20, 22])):
        q = P[:, [left[0], right[0]], :2] * (aspect, 1)
        same = distance(q[1:], q[:-1]); swap = distance(q[1:, ::-1], q[:-1])
        gap = np.linalg.norm(q[:, 0] - q[:, 1], axis=1)
        flip = (swap < 0.5 * same) & (gap[:-1] > 0.3 * L[:-1]) & (gap[1:] > 0.3 * L[1:])
        edges = np.flatnonzero(flip) + 1
        for k, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            if b - a > limit or a < 2 or b + 1 >= len(P): continue
            if (k and a - edges[k - 1] <= limit) or (k + 2 < len(edges) and edges[k + 2] - b <= limit): continue
            if cut[a - 1:b].any(): continue
            if body_flip[a - 1:b].any(): continue
            if not np.isfinite(q[a - 1:b + 1]).all() or not np.all(L[a - 1:b + 1] > 0): continue
            vis = P[[a - 1, b]][:, [left[0], right[0]], 2]
            if not np.all(vis.max(1) >= 0.5): continue
            if distance(q[a - 1], q[b]) >= distance(q[a - 1], q[b, ::-1]): continue
            parent = p[a:b, [left[0] - 2, right[0] - 2], :2] * (aspect, 1)
            if not np.isfinite(parent).all(): continue
            if np.any(distance(parent, q[a:b, ::-1]) > 2 * distance(parent, q[a:b])): continue
            p[a:b, left + right] = P[a:b, right + left]
            z = W[:, [left[0], right[0]]]
            if not np.isfinite(z[a - 1:b + 1]).all(): continue
            if np.any(distance(z[a + 1:b, ::-1], z[a:b - 1]) < distance(z[a + 1:b], z[a:b - 1])): continue
            # Image and world estimates can disagree about which frames have reversed labels.
            if all(distance(z[i - 1], z[i, ::-1]) < 0.5 * distance(z[i - 1], z[i]) for i in (a, b)):
                w[a:b, left + right] = W[a:b, right + left]
    return p, w


def use_crop(found):
    """found: people seen per sampled full frame. Crop when the full frame misses everyone in most of them (far camera).
    Measured on ~60 frames spread over each clip: a far-camera dataset (people 150-300 px of 1088) 0.05-0.31, wall practice and web clips
    >= 0.83. Person height cannot split them (far camera 0.18-0.23 of the frame when found, wall practice from 0.25)."""
    return np.mean(np.asarray(found) > 0) < 0.6


def frames(cmd, W, H):
    """Decoded RGB frames; ffmpeg failing (missing, broken or cut-off file) stops the run instead of a shorter clip."""
    import subprocess, tempfile
    with tempfile.TemporaryFile() as err:  # a file, not a pipe: ffmpeg cannot block on a full stderr while we read stdout
        p = subprocess.Popen(["ffmpeg", "-v", "error", *cmd, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=err)
        eof = False
        try:
            while len(b := p.stdout.read(W * H * 3)) == W * H * 3:  # one frame at a time: a 1080p clip never sits in memory
                yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
            eof = True
        finally:
            if not eof: p.terminate()  # the caller stopped early (break, exception): not an ffmpeg failure
            p.stdout.close(); p.wait()
        if p.returncode:
            err.seek(0); sys.exit(f"ffmpeg failed ({p.returncode}) on {' '.join(cmd)}: {err.read().decode(errors='replace').strip()[-500:]}")


DEPTH = 4  # items in flight in in_order(): enough to keep every model busy; each 960x540 frame holds ~4.5 MB (frame + images)


def result(f, poll=0.2):
    """A future's result, waiting in short slices: a bare wait is not interrupted by Ctrl-C on Windows."""
    import concurrent.futures
    while not f.done(): concurrent.futures.wait([f], timeout=poll)
    return f.result()  # re-raises the model's exception here, in the caller's thread


def in_order(items, models, depth=DEPTH):
    """items -> (item, [model(item) for each model]), in input order. Each model gets its own thread and sees every item once,
    in order (a VIDEO-mode landmarker needs increasing timestamps), so the models work on one item at the same time while
    this thread decodes the next and merges the last. At most `depth` items are in flight. An exception in a model is raised
    here; leaving early (exception, Ctrl-C, close()) drops what is queued and waits only for the calls already running."""
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor
    pools = [ThreadPoolExecutor(1, thread_name_prefix=f"pose-model{i}") for i in range(len(models))]  # one worker each: FIFO = item order
    pending = deque()
    try:
        for x in items:
            pending.append((x, [p.submit(m, x) for p, m in zip(pools, models)]))
            if len(pending) >= depth:
                x, fs = pending.popleft(); yield x, [result(f) for f in fs]
        while pending:
            x, fs = pending.popleft(); yield x, [result(f) for f in fs]
    finally:
        for p in pools: p.shutdown(wait=True, cancel_futures=True)
        if hasattr(items, "close"): items.close()  # a generator source (decoder) stops now, not when garbage collected


def sample(inp, step):
    """ffmpeg arguments for every step-th frame of input `inp`: framestep is in every ffmpeg (select needs -fps_mode, 5.1+)."""
    return [*inp, "-vf", f"framestep={step}"]


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
    if source:
        from prep import probe_rate  # ffprobe, as prep.py read it: size after rotation, exact average fps
        SW, SH, r = probe_rate(source)
        if r and r < 50: fps = r
        probe = mk(N, "IMAGE"); step = max(1, n60 // 60)
        found = [len(probe.detect(img_of(f)).pose_landmarks) for f in frames(sample(["-i", src], step), W, H)]
        probe.close()
        if not found: sys.exit(f"no frames decoded from {src}")
        crop = use_crop(found)
        if not r: print(f"warning: no frame rate for {source}; " + ("crops decode it at 60 fps" if crop else "pose runs on the 60 fps proxy (repeated frames for a low-fps source)"), file=sys.stderr)
    # below 50 fps every decoded frame is taken as n / fps: the ffmpeg fps filter puts a variable-rate phone video on that
    # constant grid by its real timestamps (a no-op for constant-rate sources), as the proxy's fps=60 does
    print(f"mode: {'crop' if crop else 'full frame'}, {fps:.3f} fps", flush=True)
    T = Tracker(N); rows = []; wrows = []; crows = []; n = 0
    if not crop:
        lm = mk(N)
        # num_poses > 1 re-detects every frame while fewer people than N are in view, and its landmarks are coarser: on the user's wall practice video the
        # wrist speed at contact dropped (hit recall 88% -> 79%). A second, single-person landmarker keeps frame-to-frame tracking;
        # its skeleton replaces the slot standing in the same place. Costs a second model pass (about 2x time).
        one = mk(1) if N > 1 else None
        it = frames(["-i", src], W, H) if fps >= 50 else frames(["-i", source, "-vf", f"fps={fps!r},{video_filter(SW, SH)}"], W, H)
        # The two landmarkers share no state: each runs on its own thread over the same frames, timestamps and images as when
        # they ran one after the other, so the output is the same bytes; the merge below stays on this thread, in frame order.
        models = [lambda x: lm.detect_for_video(x[2][0], x[1])] + ([lambda x: one.detect_for_video(x[2][1], x[1])] if one else [])
        def items():
            try:
                for i, img in enumerate(it):  # one Image per model: no object is used by two threads
                    yield img, int(i * 1000 / fps), [img_of(img) for _ in models]
            finally:
                if hasattr(it, "close"): it.close()  # frames(): stop ffmpeg now (Ctrl-C, error), not when garbage collected
        with contextlib.closing(in_order(items(), models)) as runs:
            for (img, ts, _), (r, *r1) in runs:
                r1 = r1[0] if r1 else None
                fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy(); fc = np.full((N, 3), np.nan)
                ds = [describe(a, img) for a in r.pose_landmarks]; sl = [None] * N
                for k, d, a, w in zip(T.step(ds), ds, r.pose_landmarks, r.pose_world_landmarks):
                    if k >= 0: fr[k] = [[q.x, q.y, q.visibility] for q in a]; fw[k] = [[q.x, q.y, q.z] for q in w]; fc[k] = d["color"]; sl[k] = d
                if r1 and r1.pose_landmarks and (k := same_person(describe(r1.pose_landmarks[0], img), sl)) is not None:
                    fr[k] = [[q.x, q.y, q.visibility] for q in r1.pose_landmarks[0]]; fw[k] = [[q.x, q.y, q.z] for q in r1.pose_world_landmarks[0]]
                rows.append(fr); wrows.append(fw); crows.append(fc); n += 1
                if n % 6000 == 0: print(n, flush=True)
    else:
        # Far camera (people ~100 px on the proxy): full-resolution source. Each slot is re-found in a square crop around its last
        # skeleton, scaled to 640 px, by a single-person landmarker (this replaces the second model pass above); empty slots are
        # searched in overlapping 600 px tiles every TILE_EVERY frames. All skeletons then go through the same Tracker.
        one, many = mk(1, "IMAGE"), mk(N, "IMAGE"); box = [None] * N
        ts_ = min(TILE, SW, SH)  # a source smaller than a tile (negative offsets would wrap) is searched as one tile
        tiles = [(x, y) for y in sorted({*range(0, SH - ts_, ts_ // 2), SH - ts_}) for x in sorted({*range(0, SW - ts_, ts_ // 2), SW - ts_})]
        last = [None] * N  # each slot's skeleton last frame: a crop that loses the legs near it is still that person
        def look(img, b, det, prev=None):  # skeletons in a crop, as full-frame normalized landmarks; keep() drops floodlights
            r = det.detect(img_of(cv2.resize(img[b[1]:b[1] + b[2], b[0]:b[0] + b[2]], (CROP_SIDE, CROP_SIDE))))
            got = [(np.c_[crop_to_full([[q.x, q.y] for q in a], b, SW, SH), [q.visibility for q in a]], [[q.x, q.y, q.z] for q in w])
                   for a, w in zip(r.pose_landmarks, r.pose_world_landmarks)]
            return [x for x in got if keep(x[0], prev, SW / SH)]
        for img in frames(["-i", source] + ["-vf", f"fps={60 if fps >= 50 else repr(fps)}"], SW, SH):
            got = [x for b, p in zip(box, last) if b for x in look(img, b, one, p)]
            if (None in box and n % TILE_EVERY == 0) or not got:
                found = [x for t in tiles for x in look(img, (*t, ts_), many)]  # tallest first: crowd and far background lose; tile overlaps and crops already found are dropped
                got += distinct(found, N - len(got), keep=got, aspect=SW / SH)
            lms = [[types.SimpleNamespace(x=v[0], y=v[1], visibility=v[2]) for v in a] for a, _ in got]
            ds = [describe(a, img) for a in lms]
            fr = np.full((N, 33, 3), np.nan, np.float32); fw = fr.copy(); fc = np.full((N, 3), np.nan); box = [None] * N; last = [None] * N
            for k, d, (a, w) in zip(T.step(ds), ds, got):
                if k >= 0: fr[k] = a; fw[k] = w; fc[k] = d["color"]; box[k] = crop_box(a[:, :2] * (SW, SH), SW, SH); last[k] = a
            rows.append(fr); wrows.append(fw); crows.append(fc); n += 1
            if n % 6000 == 0: print(n, flush=True)
    if not n: sys.exit(f"no frames decoded from {source if crop or fps < 50 else src}")
    P, Wl = np.array(rows).reshape(n, N, 33, 3), np.array(wrows).reshape(n, N, 33, 3)
    S = ~np.isnan(P[:, :, 0, 0]); C = np.array(crows).reshape(n, N, 3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning); col = np.nanmean(C, 0)  # NaN for a slot never used: merge() skips it
    tr = []
    for g in merge(S, col):  # per frame the biggest slot of the group wins (the rare frames two of them overlap are duplicates)
        p, w = P[:, g[0]].copy(), Wl[:, g[0]].copy()
        for k in g[1:]: m = np.isnan(p[:, 0, 0]) & S[:, k]; p[m], w[m] = P[m, k], Wl[m, k]
        tr.append((p, w))
    tr = [correct_lr(p, w, SW / SH if crop else W / H, fps) for p, w in tr]
    if fps < 50 or crop:  # back on the proxy's 60 fps frame numbers, which every later step indexes by; after merge(), so one
        # person moving between slots is joined first, and never across a frame where the track jumped to someone else
        tr = [(to60(p, fps, n60, c), to60(w, fps, n60, c)) for p, w in tr for c in [jumps(p, SW / SH if crop else W / H)]]; n = n60
    if crop: tr = [(map_pose(p, SW, SH), w) for p, w in tr]
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
