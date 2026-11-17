"""研究轉接：幾何自動提示、SAM 物件 ID 與骨架配對；不使用逐拍真值。"""
import argparse
import json
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


def anchor(poses, size):
    keys = sorted(poses)
    for f in range(len(poses[keys[0]])):
        torsos = np.array([poses[k][f, [11, 12, 23, 24]] for k in keys])
        if not np.isfinite(torsos).all() or np.any(torsos[..., 2] < .5): continue
        xy = torsos[..., :2]
        if np.any((xy < 0) | (xy >= 1)): continue
        lo, hi = xy.min(axis=1), xy.max(axis=1)
        if any(np.all(np.minimum(hi[i], hi[j]) > np.maximum(lo[i], lo[j]))
               for i in range(len(keys)) for j in range(i)):
            continue
        return f, xy.mean(axis=1) * np.asarray(size)
    raise ValueError('沒有兩人軀幹分離且可信的提示格')


def assignment(poses, ids, masks):
    keys = sorted(poses); height, width = masks.shape[-2:]
    overlap = np.zeros((len(ids), len(keys)))
    for j, k in enumerate(keys):
        p = poses[k]
        valid = np.isfinite(p).all(axis=1) & (p[:, 2] >= .2) & np.all((p[:, :2] >= 0) & (p[:, :2] < 1), axis=1)
        if not valid.any(): continue
        pixels = (p[valid, :2] * [width, height]).astype(int)
        overlap[:, j] = masks[:, pixels[:, 1], pixels[:, 0]].mean(axis=1)
    rows, cols = linear_sum_assignment(-overlap)
    return {ids[i]: keys[j] for i, j in zip(rows, cols) if overlap[i, j] > 0}


class VideoFrames:
    """只保留當次解碼格，避免預載整支 1024 平方影像耗盡記憶體。"""
    def __init__(self, path, count, image_size):
        import cv2
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened(): raise ValueError('無法開啟 proxy')
        self.count = count; self.image_size = image_size

    def __len__(self): return self.count

    def __getitem__(self, index):
        import cv2
        import torch
        from PIL import Image
        if not 0 <= index < self.count: raise IndexError(index)
        if int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) != index:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = self.cap.read()
        if not ok: raise ValueError('proxy 解碼失敗')
        rgb = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).resize((self.image_size, self.image_size))
        image = torch.from_numpy(np.asarray(rgb) / 255).permute(2, 0, 1).float()
        return (image - torch.tensor([.485, .456, .406])[:, None, None]) / torch.tensor([.229, .224, .225])[:, None, None]


def resources():
    raw = subprocess.check_output(['vm_stat'], text=True)
    page = int(re.search(r'page size of (\d+)', raw)[1])
    pages = sum(int(re.search(r'Pages ' + name + r':\s+(\d+)', raw)[1]) for name in ('free', 'inactive'))
    if page * pages < 8 * 1024**3: raise RuntimeError('free+inactive < 8 GiB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('clip')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    config = next(c for c in json.loads(args.manifest.read_text()) if c['alias'] == args.clip)
    poses = {int(k): np.load(p) for k, p in config['poses'].items()}
    n = config['frames']
    assert all(p.shape == (n, 33, 3) for p in poses.values())
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic(); done = set(); metadata = dict(status='未完成', frames=n)
    stream = None
    try:
        resources()
        if len(poses) == 1:
            result = poses
            done = set(range(n)); metadata['single_track'] = True
        else:
            import torch
            torch.set_num_threads(4)
            sys.path.insert(0, str(Path('work/repos/sam2').resolve()))
            from sam2.build_sam import build_sam2_video_predictor
            import sam2.sam2_video_predictor as predictor_module

            def timeout(*_): raise TimeoutError('單支推論達30分鐘，停止')
            signal.signal(signal.SIGALRM, timeout); signal.alarm(1800)
            f, points = anchor(poses, config['size']); metadata['anchor'] = f
            model = build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_t.yaml',
                'work/weights/sam2.1_hiera_tiny.pt', device='cpu')
            stream = VideoFrames(config['video'], n, model.image_size)
            predictor_module.load_video_frames = lambda **kwargs: (stream, config['size'][1], config['size'][0])
            result = {k: np.full_like(p, np.nan) for k, p in poses.items()}
            with torch.inference_mode():
                state = model.init_state(config['video'], offload_video_to_cpu=True, offload_state_to_cpu=True)
                for k, point in zip(sorted(poses), points):
                    model.add_new_points_or_box(state, f, k, points=point[None].astype(np.float32), labels=np.array([1], np.int32))
                for reverse in (False, True):
                    for frame, ids, logits in model.propagate_in_video(state, start_frame_idx=f, reverse=reverse):
                        resources()
                        match = assignment({k: p[frame] for k, p in poses.items()}, ids, (logits[:, 0] > 0).cpu().numpy())
                        for obj, track in match.items(): result[obj][frame] = poses[track][frame]
                        done.add(frame)
                        if len(done) % 60 == 0:
                            print(json.dumps(dict(completed=len(done), frames=n, seconds=round(time.monotonic()-started, 2))), flush=True)
            assert len(done) == n
        for k, p in result.items(): np.save(args.output / f'pose{k}.npy', p)
        metadata['status'] = '完成'
    except (RuntimeError, TimeoutError, NotImplementedError, ValueError) as exc:
        metadata['reason'] = str(exc)
    finally:
        signal.alarm(0)
        if stream is not None: stream.cap.release()
        metadata.update(completed=len(done), seconds=time.monotonic()-started)
        (args.output / 'status.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        print(json.dumps(metadata), flush=True)
    return 0 if metadata['status'] == '完成' else 1


if __name__ == '__main__': sys.exit(main())
