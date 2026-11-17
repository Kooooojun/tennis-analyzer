"""RTMO-s 公開 COCO 重現；只寫本機結果，不接受部分資料集。"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


def records(image_id, outputs, ratio, keep):
    detections, poses = outputs
    if (not np.isfinite(ratio) or ratio <= 0 or detections.ndim != 3
            or detections.shape[0] != 1 or detections.shape[2] != 5
            or poses.shape != (1, detections.shape[1], 17, 3)
            or not np.isfinite(detections).all() or not np.isfinite(poses).all()):
        raise ValueError('非法 RTMO 輸出或縮放比例')
    result = []
    for index in (() if keep is None else keep):
        box = detections[0, index, :4] / ratio
        points = poses[0, index].copy(); points[:, :2] /= ratio
        result.append(dict(image_id=image_id, category_id=1,
                           keypoints=points.reshape(-1).tolist(),
                           bbox=[float(box[0]), float(box[1]), float(box[2] - box[0]), float(box[3] - box[1])],
                           score=float(detections[0, index, 4])))
    return result


def image_paths(images, root):
    if len(images) != 5000 or len({image['id'] for image in images}) != 5000:
        raise ValueError('須提供完整 COCO val2017 的 5,000 張與唯一 ID')
    root = root.resolve(); paths = []
    for image in images:
        path = (root / image['file_name']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('圖片路徑超出指定資料目錄')
        if not path.is_file():
            raise FileNotFoundError(path)
        paths.append((image['id'], path))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--rtmlib', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    paths = image_paths(json.loads(args.annotations.read_text(encoding='utf-8'))['images'], args.images)
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    args.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / 'docs/research/caltennis'))
    from ct_lr_run import memory
    from ct_world_run import release_lock
    # 只明確載入已核對的 clone；-I 仍隔離使用者 site 與環境匯入。
    sys.path.insert(0, str(args.rtmlib.resolve()))
    from rtmlib import RTMO
    from rtmlib.tools.object_detection.post_processings import multiclass_nms
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    import cv2

    busy = subprocess.run(['pgrep', '-fl', 'pose_full|prep.py|ball.py'], capture_output=True, text=True)
    if busy.returncode != 1:
        raise RuntimeError('重運算尚未清空：' + busy.stdout + busy.stderr)
    lock = repo / 'testset/results/heavy.lock'
    with ExitStack() as cleanup:
        lock.mkdir()
        cleanup.callback(release_lock, lock)
        import datetime
        (repo / 'testset/results/heavy.lock/owner.txt').write_text(
            'borrow-pose / COCO / ' + datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(), encoding='utf-8')
        lowest = memory()
        if lowest < 8:
            raise RuntimeError('記憶體不足 8 GiB')
        start = time.monotonic()
        model = RTMO(str(args.model.resolve()), backend='onnxruntime', device='cpu', score_thr=.1, nms_thr=.65)
        results = []
        for i, (image_id, path) in enumerate(paths):
            lowest = min(lowest, memory())
            if lowest < 8:
                raise RuntimeError('記憶體低於 8 GiB，停止')
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError('無法讀取公開圖片')
            image, ratio = model.preprocess(image)
            outputs = model.inference(image)
            # 官方 COCO 排序使用 bbox score；高階 API 只回傳關節分數。
            _, keep = multiclass_nms(outputs[0][0, :, :4], outputs[0][0, :, 4:5], nms_thr=.65, score_thr=.1)
            results.extend(records(image_id, outputs, ratio, keep))
            if (i + 1) % 100 == 0:
                print(f'{i + 1}/5000；{time.monotonic() - start:.1f} 秒', flush=True)
        seconds = time.monotonic() - start
        (args.out / 'predictions.json').write_text(json.dumps(results), encoding='utf-8')
        if not results:
            raise RuntimeError('沒有任何預測，不產生假零評分')
        coco = COCO(str(args.annotations)); evaluation = COCOeval(coco, coco.loadRes(results), 'keypoints')
        evaluation.evaluate(); evaluation.accumulate(); evaluation.summarize()
        summary = dict(images=len(paths), predictions=len(results), ap=float(evaluation.stats[0]),
                       expected_ap=.686, difference_ap_points=float((evaluation.stats[0] - .686) * 100),
                       reproduced=bool(abs(evaluation.stats[0] - .686) <= .01),
                       seconds=seconds, min_free_inactive_gib=lowest)
        (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
