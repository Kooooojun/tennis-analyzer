"""Proxy 的縮放／補邊幾何；尺寸與偏移均對齊 yuv420 的偶數像素。"""


def needs_padding(w, h):
    pw, ph = (960, 540) if w > h else (540, 960)
    return 100 * abs(w * ph - h * pw) > h * pw  # 沿用 prep 的 ±1% 容許範圍。


def layout(w, h):
    if w <= 0 or h <= 0: raise ValueError("影片尺寸必須大於零")
    pw, ph = (960, 540) if w > h else (540, 960)
    if not needs_padding(w, h): return pw, ph, pw, ph, 0, 0
    scale = min(pw / w, ph / h)
    cw, ch = min(pw, max(2, 2 * int(w * scale / 2 + 0.5))), min(ph, max(2, 2 * int(h * scale / 2 + 0.5)))
    return pw, ph, cw, ch, (pw - cw) // 4 * 2, (ph - ch) // 4 * 2


def video_filter(w, h):
    pw, ph, cw, ch, x, y = layout(w, h)
    if not needs_padding(w, h): return f"scale={pw}:{ph}"
    return f"scale={cw}:{ch},setsar=1,pad={pw}:{ph}:{x}:{y}:black"


def map_pose(P, w, h, inverse=False):
    """原片與 proxy 之間的 normalized 姿態；保留 visibility 與缺值。"""
    pw, ph, cw, ch, x, y = layout(w, h)
    if not needs_padding(w, h): return P  # 16:9 容許範圍內不增加浮點運算。
    Q = P.copy()
    if inverse: Q[..., :2] = (P[..., :2] * (pw, ph) - (x, y)) / (cw, ch)
    else: Q[..., :2] = (P[..., :2] * (cw, ch) + (x, y)) / (pw, ph)
    return Q
