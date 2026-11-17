"""每次只跑一支參考／正式姿態，持共用鎖並監測記憶體。"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[3] / 'tools')]
from ct_lr_run import memory
from ct_world import validate_timestamps
from proxy import video_filter


def release_lock(lock):
    original = sys.exception()
    error = None
    owner = lock/'owner.txt'
    try:
        if owner.exists(): subprocess.run(['trash',str(owner)],check=True)
    except (OSError,subprocess.SubprocessError) as e:
        print(f'無法trash鎖owner，改用unlink：{e}',file=sys.stderr)
        try: owner.unlink(missing_ok=True)
        except OSError as e:
            error = e
            print(f'無法移除鎖owner：{e}',file=sys.stderr)
    finally:
        try: lock.rmdir()
        except OSError as e:
            error = e
            print(f'無法移除鎖目錄，需檢查後清理：{e}',file=sys.stderr)
    if error is not None and original is None: raise error


def child(manifest, camera, mode):
    root=Path(manifest).parent; cfg=json.loads(Path(manifest).read_text(encoding='utf-8'))['cameras'][camera]
    if mode=='reference':
        from ct_pose import extract
        ts=np.load(root/cfg['timestamps']); validate_timestamps(ts)
        extract(root/cfg['source'],ts,cfg['start_frame'],cfg['frames'],root/cfg['reference'])
    else:
        ref=np.load(root/cfg['reference']); validate_timestamps(ref['t'])
        import pose_full
        pose_full.use_crop=lambda found: mode=='crop'
        d=root/cfg[mode]
        sys.argv=['pose_full.py',str(root/cfg['proxy']),'models/pose_heavy.task',str(d/'pose.npy'),'1',str(root/cfg['clip'])]
        pose_full.main()
        assert np.load(d/'pose.npy').shape==np.load(d/'pose_world.npy').shape==(len(ref['t']),33,3)
        np.save(d/'t.npy',ref['t'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('camera',type=int);p.add_argument('mode',choices=['reference','crop','full']);p.add_argument('--child',action='store_true')
    a=p.parse_args()
    if a.child: child(a.manifest,a.camera,a.mode);return
    root=Path(a.manifest).parent; cfg=json.loads(Path(a.manifest).read_text(encoding='utf-8'))['cameras'][a.camera]
    target=root/cfg['reference'] if a.mode=='reference' else root/cfg[a.mode]/'pose.npy'
    if target.exists(): sys.exit('已有輸出，拒絕覆寫')
    target.parent.mkdir(parents=True,exist_ok=True)
    busy=subprocess.run(['pgrep','-fl','pose_full|prep.py|ball.py'],capture_output=True,text=True)
    if busy.returncode!=1: sys.exit('其他heavy程序執行中：'+busy.stdout+busy.stderr)
    lock=Path('testset/results/heavy.lock');lock.parent.mkdir(parents=True,exist_ok=True);lock.mkdir()
    owner=lock/'owner.txt'
    try:
        owner.write_text(f'#68 3D / CalTennis / {a.mode} / 機位{a.camera+1} / '+datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()+'\n',encoding='utf-8')
        low=memory()
        if low<8: sys.exit('記憶體不足8GiB')
        start=time.monotonic()
        if a.mode!='reference':
            clip,proxy=root/cfg['clip'],root/cfg['proxy']
            if not clip.exists():
                subprocess.run(['ffmpeg','-v','error','-n','-i',str(root/cfg['source']),'-vf',f"trim=start_frame={cfg['start_frame']}:end_frame={cfg['start_frame']+cfg['frames']},setpts=N/(60*TB)",'-an','-r','60','-c:v','libx264','-preset','ultrafast','-crf','16',str(clip)],check=True)
            if not proxy.exists():
                subprocess.run(['ffmpeg','-v','error','-n','-i',str(clip),'-vf',video_filter(*cfg['size']),'-an','-c:v','libx264','-preset','ultrafast','-crf','18',str(proxy)],check=True)
        with target.with_suffix('.log').open('x',encoding='utf-8') as log:
            proc=subprocess.Popen([sys.executable,__file__,a.manifest,str(a.camera),a.mode,'--child'],stdout=log,stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    low=min(low,memory())
                    if low<8: raise RuntimeError('記憶體低於8GiB，停止')
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:pass
            finally:
                if proc.poll() is None:proc.terminate();proc.wait()
        if proc.returncode: raise RuntimeError(f'姿態失敗：{proc.returncode}，請讀取本機log')
        record=dict(mode=a.mode,camera=a.camera+1,seconds=time.monotonic()-start,min_free_inactive_gib=low,frames=cfg['frames'])
        target.with_suffix('.run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(record,ensure_ascii=False),flush=True)
    finally:
        release_lock(lock)


if __name__=='__main__':main()
