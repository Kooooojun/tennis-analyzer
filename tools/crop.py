"""Crop geometry for the labelling sheets (candidates.py). Pure: pixel coordinates in, boxes / images out."""
import numpy as np


def square(pts, W, H):
    """Old sheet crop: square around the torso centres pts (n, 2 pixels) of everyone in frame, at least 220 px, 240 px margin.
    -> (side, x0, y0); x0 / y0 may be outside the frame when the square is bigger than it (black bars, never cut a player off)."""
    lo, hi = (pts.min(0), pts.max(0)) if len(pts) else (np.array([W / 2, H * 5 / 8]),) * 2
    side = int(min(max(220, *(hi - lo + 240)), max(H, W))); cx, cy = (lo + hi) / 2
    x0 = int(min(max(cx - side / 2, 0), W - side)) if side <= W else int(cx - side / 2)
    y0 = int(min(max(cy - side * 0.6, 0), H - side)) if side <= H else int(cy - side / 2)
    return side, x0, y0


def wide(c, L, W, H, k=4.5, aspect=1.5):
    """New sheet crop around one hitter: k torso lengths L wide, aspect wide:high, centred 0.2 L below the torso centre c: head top
    to the knees, so the racket and ball at contact (waist to chest on groundstrokes) and the swing on either side are in it. Pushed back inside the frame when it fits, else centred.
    -> (x0, y0, w, h)."""
    w = int(round(k * L)); h = int(round(w / aspect)); cx, cy = c[0], c[1] + 0.2 * L
    x0 = int(min(max(cx - w / 2, 0), W - w)) if w <= W else int(cx - w // 2)
    y0 = int(min(max(cy - h / 2, 0), H - h)) if h <= H else int(cy - h // 2)
    return x0, y0, w, h


def cut(im, x0, y0, w, h):
    """im[y0:y0+h, x0:x0+w] with black where the box leaves the frame; im None (no frame: clip start / end) -> all black."""
    t = np.zeros((h, w, 3), np.uint8)
    if im is None: return t
    H, W = im.shape[:2]; a, b, c, d = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if a < c and b < d: t[b - y0:d - y0, a - x0:c - x0] = im[b:d, a:c]
    return t


_LUT = np.clip(255 * (np.arange(256) / 255) ** 0.6, 0, 255).astype(np.uint8)  # gamma: lifts shadows, 255 stays 255 (a ball keeps its contrast)


def brighten(im):
    return _LUT[im]
