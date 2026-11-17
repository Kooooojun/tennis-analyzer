"""只轉接既有訊號；上游切分器直接由隔離 clone 匯入，不調參。"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def sample_signals(pose, ball, size):
    if pose.shape != (len(ball), 33, 3) or ball.ndim != 2 or ball.shape[1] != 3:
        raise ValueError('姿態與球軌必須逐格對齊')
    idx = np.arange(0, len(ball), 4)
    p = pose[idx].copy(); p[..., :2] *= np.asarray(size)
    b = ball[idx, :2].copy() * np.asarray(size)
    b[~np.isfinite(ball[idx, 2]) | (ball[idx, 2] <= 0)] = np.nan
    return idx / 60, b, p


def contacts(poses, ball, size, upstream):
    sys.path.insert(0, str(upstream.resolve() / 'backend'))
    from app import config
    from app.kinematics import dominant_wrist_track, infer_handedness
    from app.schemas import PoseResult
    from app.services.segmentation import SegmentationService, SignalTracks

    assert config.WORKING_FPS == 15
    times = set()
    for pose in poses:
        t, b, p = sample_signals(pose, ball, size)
        rows = [PoseResult(i, row[:, :2], np.full((33, 3), np.nan), row[:, 2]) for i, row in enumerate(p)]
        wrist = dominant_wrist_track(rows, infer_handedness(rows))
        shots, _ = SegmentationService().segment(SignalTracks(t, b, np.full_like(b, np.nan), wrist))
        times.update(shot.t_contact for shot in shots)
    return sorted(times)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='只含原四支開發資料的目錄')
    parser.add_argument('output', type=Path)
    parser.add_argument('--repo', type=Path, default=Path('work/repos/swing-analysis'))
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
    from common import size
    from eval_hits import read_labels, score

    result = []
    for alias, expected in zip(('A1', 'A2', 'D24', 'D30'), (25, 17, 32, 71)):
        d = args.data / alias
        labels, spans = read_labels(d / 'labels.csv')
        target = [float(x['t_sec']) for x in labels if x['kind'] == 'stroke']
        ignore = [float(x['t_sec']) for x in labels if x['kind'] != 'stroke']
        assert len(target) == expected and spans
        poses = [np.load(p).astype(float) for p in [d / 'pose.npy', *sorted(d.glob('pose_t*.npy'))]]
        pred = contacts(poses, np.load(d / 'ball.npy'), size(d / 'proxy.mp4'), args.repo)
        tp, fn, fp = score(target, ignore, pred, spans=spans)
        n, miss, extra = len(tp), len(fn), len(fp)
        result.append(dict(fold=len(result) + 1, tp=n, fn=miss, fp=extra,
                           recall=n / (n + miss), precision=n / (n + extra) if n + extra else None,
                           predictions=pred))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps([{k: v for k, v in row.items() if k != 'predictions'} for row in result]))


if __name__ == '__main__': main()
