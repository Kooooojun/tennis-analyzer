# ball.py <proxy.mp4> <ball.npy> [cpu|mps|cuda] [--windows windows.npy] — per-frame tennis ball (x, y, conf), normalized 0-1, NaN outside windows or when not found.
# The network is the TrackNetV3-style UNet from RacketVision BallTrack (github.com/OrcustD/RacketVision, MIT, Copyright (c) 2025
# Linfeng Dong; license text in third_party/RacketVision-LICENSE), rewritten without mmengine. Weights: models/balltrack_best.pth.
# Input per frame: median background + the last 4 frames (BGR, 512x288); output: heatmap of the newest frame.
# Landscape proxies run as one crop. Portrait proxies run as 4 stacked, overlapping 16:9 crops (a stretched portrait frame is out
# of the training distribution; 3 would leave 24 px gaps) and the most confident ball wins.
import sys, subprocess, time, pickle, types
from pathlib import Path
import numpy as np, cv2, torch, torch.nn as nn

W_IN, H_IN, SEQ, BATCH, THRE = 512, 288, 4, 16, 0.5
WEIGHTS = Path(__file__).resolve().parent.parent / "models" / "balltrack_best.pth"


def block(i, o, n):  # n x (conv3x3 -> batchnorm -> relu)
    return nn.Sequential(*[nn.Sequential(nn.Conv2d(i if k == 0 else o, o, 3, padding="same", bias=False), nn.BatchNorm2d(o), nn.ReLU()) for k in range(n)])


class Net(nn.Module):
    def __init__(self, d=64, in_dim=3 * (SEQ + 1), out_dim=SEQ):
        super().__init__()
        self.down_block_1, self.down_block_2 = block(in_dim, d, 2), block(d, 2 * d, 2)
        self.down_block_3, self.bottleneck = block(2 * d, 4 * d, 3), block(4 * d, 8 * d, 3)
        self.up_block_1, self.up_block_2, self.up_block_3 = block(12 * d, 4 * d, 3), block(6 * d, 2 * d, 2), block(3 * d, d, 2)
        self.predictor = nn.Conv2d(d, out_dim, 1)

    def forward(self, x):
        up, pool = nn.Upsample(scale_factor=2), nn.MaxPool2d(2)
        x1 = self.down_block_1(x); x2 = self.down_block_2(pool(x1)); x3 = self.down_block_3(pool(x2))
        x = self.bottleneck(pool(x3))
        x = self.up_block_1(torch.cat([up(x), x3], 1)); x = self.up_block_2(torch.cat([up(x), x2], 1))
        x = self.up_block_3(torch.cat([up(x), x1], 1))
        return torch.sigmoid(self.predictor(x))[:, -1:]  # newest frame only


_SAFE = {("collections", "OrderedDict"), ("torch._utils", "_rebuild_tensor_v2"), ("torch._utils", "_rebuild_parameter")}


class _Unpickler(pickle.Unpickler):  # the checkpoint's meta holds mmengine/numpy objects; only tensor rebuilding is real, the rest becomes an inert stub
    def find_class(self, mod, name):
        if (mod, name) in _SAFE or (mod == "torch" and name.endswith("Storage")): return super().find_class(mod, name)
        return type(name, (), {"__init__": lambda s, *a, **k: None, "__setstate__": lambda s, *a: None})


_PICKLE = types.ModuleType("safe_pickle"); _PICKLE.Unpickler = _Unpickler; _PICKLE.load = pickle.load; _PICKLE.__dict__.update(
    {k: getattr(pickle, k) for k in ("UnpicklingError", "dumps", "loads", "HIGHEST_PROTOCOL", "DEFAULT_PROTOCOL")})


def load_weights(net, path):  # original names: down_block_1.conv_1.conv/bn -> ours: down_block_1.0.0/1
    sd = torch.load(path, map_location="cpu", weights_only=False, pickle_module=_PICKLE)
    sd = sd.get("state_dict", sd)
    out = {}
    for k, v in sd.items():
        k = k[7:] if k.startswith("module.") else k
        for a, b in (("conv_1.", "0."), ("conv_2.", "1."), ("conv_3.", "2."), (".conv.", ".0."), (".bn.", ".1.")):
            k = k.replace(a, b)
        out[k] = v
    net.load_state_dict(out)


def crops_for(W, H):  # (x, y, w, h) windows of 16:9 that cover the frame
    if W >= H: return [(0, 0, W, H)]
    ch = round(W * 9 / 16); n = -(-H // ch)  # ceil: n crops of height ch cover H only if n * ch >= H
    return [(0, y, W, ch) for y in sorted({round(i * (H - ch) / (n - 1)) for i in range(n)})]


def locate(hm):  # center of the largest blob above THRE, as in the original inference.py
    m = (hm > THRE).astype(np.uint8)
    if not m.any(): return None
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = max((cv2.boundingRect(c) for c in cnts), key=lambda r: r[2] * r[3])
    return x + w / 2, y + h / 2, float(hm[y:y + h, x:x + w].max())


def window_mask(windows, n):
    """整數半開影格區間；None 表示整片。"""
    mask = np.ones(n, bool) if windows is None else np.zeros(n, bool)
    if windows is None: return mask
    a = np.asarray(windows)
    if a.shape == (0,): return mask
    if a.ndim != 2 or a.shape[1] != 2 or not np.issubdtype(a.dtype, np.integer) or \
            (a[:, 0] < 0).any() or (a[:, 1] < a[:, 0]).any() or (a[:, 1] > n).any():
        raise ValueError("視窗需為影片範圍內的整數起迄格（尾端不含）")
    for start, stop in a: mask[start:stop] = True
    return mask


def main(src, out, device=None, windows=None):
    cap = cv2.VideoCapture(src); W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not (W and H): sys.exit(f"cannot read {src}")
    try: mask = np.r_[window_mask(windows, N), np.full(SEQ, windows is None)]
    except ValueError:
        cap.release(); raise
    crops = crops_for(W, H)
    s = []  # median background from 25 evenly spaced frames (players move, the court stays)
    for f in np.linspace(0, max(N - 2, 0), 25).astype(int) if mask.any() else []:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, im = cap.read()
        if ok: s.append(im)
    cap.release()
    if mask.any() and not s: sys.exit(f"cannot read frames of {src}")
    dev = torch.device(device or ("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"))
    rs = lambda im, c: cv2.resize(im[c[1]:c[1] + c[3], c[0]:c[0] + c[2]], (W_IN, H_IN), interpolation=cv2.INTER_AREA)
    if mask.any():
        med = [torch.from_numpy(np.median(np.stack([rs(im, c) for im in s]), 0).astype(np.float32) / 255).permute(2, 0, 1).to(dev) for c in crops]
        net = Net(); load_weights(net, WEIGHTS); net.to(dev).eval()
    print(f"device {dev}, {len(crops)} crop(s), {N} frames, {int(mask[:N].sum())} selected", flush=True)

    res = np.full((N + SEQ, 3), np.nan, np.float32); score = np.full(N + SEQ, -1.0, np.float32)
    bufs = [[] for _ in crops]; done = 0; t0 = time.time()

    def flush(n):  # n windows per crop; bufs hold SEQ-1 history frames then the new ones
        nonlocal done
        if not mask[done:done + n].any():
            for buf in bufs: del buf[:n]
            done += n
            return
        for ci, c in enumerate(crops):
            fr = torch.from_numpy(np.stack(bufs[ci][:n + SEQ - 1])).to(dev).permute(0, 3, 1, 2).float() / 255
            x = torch.cat([med[ci].expand(n, 3, H_IN, W_IN), torch.stack([fr[k:k + SEQ] for k in range(n)]).reshape(n, 3 * SEQ, H_IN, W_IN)], 1)
            with torch.no_grad(): hm = net(x)[:, 0].cpu().numpy()
            for k in range(n):
                r = locate(hm[k]); i = done + k
                if r and r[2] > score[i]:
                    score[i] = r[2]; res[i] = ((c[0] + r[0] * c[2] / W_IN) / W, (c[1] + r[1] * c[3] / H_IN) / H, r[2])
            del bufs[ci][:n]
        done += n

    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    first, got = True, 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        im = np.frombuffer(b, np.uint8).reshape(H, W, 3); got += 1
        for ci, c in enumerate(crops):
            f = rs(im, c)
            if first: bufs[ci] += [f] * (SEQ - 1)  # pad the start with frame 0, like the original (max(0, j))
            bufs[ci].append(f)
        first = False
        if len(bufs[0]) >= BATCH + SEQ - 1: flush(BATCH)
    if len(bufs[0]) > SEQ - 1: flush(len(bufs[0]) - (SEQ - 1))
    p.stdout.close()
    if p.wait(): sys.exit(f"ffmpeg failed decoding {src} after {got} frames")  # a truncated ball.npy would be cached by prep.sh forever
    res = res[:got]; res[~mask[:got]] = np.nan
    np.save(out, res)
    ok = ~np.isnan(res[:, 0])
    print(f"{got} frames, ball found in {int(ok.sum())} ({100 * ok.mean():.0f}%), {1000 * (time.time() - t0) / max(got, 1):.1f} ms/frame")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="追球；可選整數半開影格視窗 NPY，省略則跑整片")
    parser.add_argument("src"); parser.add_argument("out")
    parser.add_argument("device", nargs="?")
    parser.add_argument("--windows", help="形狀 (N, 2) 的整數 NPY，尾端不含")
    args = parser.parse_args()
    try: main(args.src, args.out, args.device, np.load(args.windows) if args.windows else None)
    except (OSError, ValueError) as e: sys.exit(str(e))
