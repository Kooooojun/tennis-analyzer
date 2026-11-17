"""一次比較一個模式、一段已揭露開發片；沿用既有召回評分。"""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def require_reproduced(summary):
    if summary.get('reproduced') is not True:
        raise ValueError('須先重現完整公開評測')


def pose33(rows, slots, width, height):
    result = np.full((slots, 33, 3), np.nan, np.float32)
    for i, row in enumerate(rows[:slots]):
        result[i, COCO] = np.asarray(row['keypoints']).reshape(17, 3) / (width, height, 1)
    return result


def child(config, mode, repo):
    spec = importlib.util.spec_from_file_location('far_pose_lab', repo / 'testset/results/far_pose_lab.py')
    lab = importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)
    out = Path(config['out'])
    if mode == 'main':
        lab.measure(repo / 'tools/pose_full.py', Path(config['proxy']), Path(config['source']), out,
                    config['n'], video=config['video'], start=5)
        return
    sys.path.insert(0, str(repo / 'work/repos/rtmlib'))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rtmlib import RTMO
    from rtmlib.tools.object_detection.post_processings import multiclass_nms
    from rtmo_coco import records
    from pose_full import frames, to60
    import cv2

    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    model = RTMO(str(repo / 'work/weights/rtmo-s/end2end.onnx'), backend='onnxruntime', device='cpu', score_thr=.1, nms_thr=.65)
    capture = cv2.VideoCapture(config['source'])
    width, height, fps = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), capture.get(cv2.CAP_PROP_FPS))
    expected = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)); capture.release()
    if not (width and height and abs(fps - 30) < .001):
        raise ValueError('須沿用既有30fps開發來源')
    proxy = cv2.VideoCapture(config['proxy']); n60 = int(proxy.get(cv2.CAP_PROP_FRAME_COUNT)); proxy.release()
    poses = []
    for image in frames(['-i', config['source']], width, height):
        image, ratio = model.preprocess(np.ascontiguousarray(image[:, :, ::-1]))
        outputs = model.inference(image)
        _, keep = multiclass_nms(outputs[0][0, :, :4], outputs[0][0, :, 4:5], nms_thr=.65, score_thr=.1)
        rows = records(0, outputs, ratio, keep)
        poses.append(pose33(rows, config['n'], width, height))
    if len(poses) != expected or n60 != expected * 2:
        raise ValueError('解碼格數或60fps索引不符')
    poses = to60(np.asarray(poses), fps, n60)
    for i in range(config['n']):
        np.save(out / ('pose.npy' if i == 0 else f'pose_t{i}.npy'), poses[:, i])
    total = time.perf_counter() - start
    summary = dict(total=total, frames=expected, recall=lab.score(out, config['video'], 5))
    (out / 'measurement.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path); parser.add_argument('key')
    parser.add_argument('mode', choices=['main', 'rtmo']); parser.add_argument('--child', action='store_true')
    args = parser.parse_args(); repo = Path(__file__).resolve().parents[3]
    require_reproduced(json.loads((repo / 'work/rtmo-coco/summary.json').read_text(encoding='utf-8')))
    config = json.loads(args.manifest.read_text(encoding='utf-8'))[args.key]
    sys.path[:0] = [str(repo / 'docs/research/caltennis'), str(repo / 'tools')]
    if args.child:
        child(config, args.mode, repo); return
    from ct_lr_run import memory
    from ct_world_run import release_lock
    target = Path(config['out'])
    if target.exists():
        raise FileExistsError('已有輸出，拒絕覆寫')
    busy = subprocess.run(['pgrep', '-fl', 'pose_full|prep.py|ball.py'], capture_output=True, text=True)
    if busy.returncode != 1:
        raise RuntimeError('其他heavy程序尚未清空：' + busy.stdout + busy.stderr)
    lock = repo / 'testset/results/heavy.lock'; lock.mkdir()
    try:
        (lock / 'owner.txt').write_text('borrow-pose / 開發片段 / ' + args.key + ' / ' + datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(), encoding='utf-8')
        low = memory()
        if low < 8:
            raise RuntimeError('記憶體不足8GiB')
        with target.with_suffix('.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-I', __file__, str(args.manifest), args.key, args.mode, '--child'], stdout=log, stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    low = min(low, memory())
                    if low < 8:
                        raise RuntimeError('記憶體低於8GiB，停止')
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: pass
            finally:
                if proc.poll() is None: proc.terminate(); proc.wait()
        if proc.returncode:
            raise RuntimeError(f'試跑失敗：{proc.returncode}，請讀取本機log')
        print(json.dumps(dict(mode=args.mode, min_free_inactive_gib=low)), flush=True)
    finally:
        release_lock(lock)


if __name__ == '__main__':
    main()
