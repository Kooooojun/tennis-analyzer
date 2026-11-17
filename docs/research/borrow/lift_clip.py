"""固定 VideoPose3D 官方權重，僅轉接已揭露開發場次的裁切 2D。"""
import argparse
import datetime
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

COCO = [0,2,5,7,8,11,12,13,14,15,16,23,24,25,26,27,28]
MP = [23,24,25,26,27,28,11,12,13,14,15,16]
H36M = [4,1,5,2,6,3,11,14,12,15,13,16]


def input17(p, size):
    if p.ndim != 3 or p.shape[1:] != (33,3) or not len(p) or min(size)<=0:
        raise ValueError('須有非空33點與來源尺寸')
    xy=p[:,COCO,:2].copy(); valid=np.isfinite(xy).all(axis=(1,2))
    for j in range(17):
        for axis in range(2):
            keep=np.isfinite(xy[:,j,axis])
            if not keep.any(): raise ValueError('整段缺少輸入關節')
            xy[:,j,axis]=np.interp(np.arange(len(p)),np.flatnonzero(keep),xy[keep,j,axis])
    return xy,valid


def output33(x):
    out=np.full((len(x),33,3),np.nan,np.float32)
    out[:,MP]=x[:,H36M]
    return out


def chunks(x, count=256, pad=121):
    for start in range(0,len(x),count):
        end=min(start+count,len(x)); lo=max(0,start-pad); hi=min(len(x),end+pad)
        yield start,np.pad(x[lo:hi],((max(0,pad-start),max(0,end+pad-len(x))),(0,0),(0,0)),'edge')


def child(cfg, camera, out, repo):
    import torch
    modules={}
    for name in ('model','generators'):
        spec=importlib.util.spec_from_file_location('vp3d_'+name,repo/'work/repos/VideoPose3D/common'/f'{name}.py')
        modules[name]=importlib.util.module_from_spec(spec); spec.loader.exec_module(modules[name])
    TemporalModel=modules['model'].TemporalModel; UnchunkedGenerator=modules['generators'].UnchunkedGenerator
    from proxy import map_pose
    from ct_world import reference, paired_mask
    root=Path(cfg['manifest']).parent
    manifest=json.loads(Path(cfg['manifest']).read_text(encoding='utf-8')); cams=manifest['cameras']
    c=cams[camera]; p=np.load(root/c['crop']/'pose.npy'); size=c['size']
    pixels=map_pose(p,*size,inverse=True); pixels[...,:2]*=size
    xy,valid=input17(pixels,size)
    xy=(xy/size[0]*2-[1,size[1]/size[0]]).astype(np.float32)
    start=time.perf_counter()
    model=TemporalModel(17,2,17,[3,3,3,3,3]); model.load_state_dict(torch.load(repo/'work/weights/pretrained_h36m_detectron_coco.bin',map_location='cpu',weights_only=True)['model_pos']); model.eval()
    assert model.receptive_field()==243
    predictions=[]
    with torch.inference_mode():
        for _, block in chunks(xy):
            gen=UnchunkedGenerator(None,None,[block],pad=0,augment=True,
                kps_left=[1,3,5,7,9,11,13,15],kps_right=[2,4,6,8,10,12,14,16],
                joints_left=[4,5,6,11,12,13],joints_right=[1,2,3,14,15,16])
            _,_,batch=next(gen.next_epoch()); y=model(torch.from_numpy(batch.astype(np.float32)))
            y[1,:,:,0]*=-1
            left=[4,5,6,11,12,13]; right=[1,2,3,14,15,16]
            y[1,:,left+right]=y[1,:,right+left]
            predictions.append(y.mean(0).numpy())
    world=output33(np.concatenate(predictions)); assert len(world)==len(p)
    infer_seconds=time.perf_counter()-start
    refs=[dict(np.load(root/c['reference'])) for c in cams]
    Ps=[]
    for c in cams:
        calibration=json.loads((root/c['calibration']).read_text(encoding='utf-8'))
        Ps.append(np.array(calibration['K'])@np.array(calibration['Rt_w2c']))
    sh=manifest['shift_frames']*(1 if camera==0 else -1)
    uv=reference(refs[camera],refs[1-camera],Ps[camera],Ps[1-camera],sh)[3]
    valid &= paired_mask(pixels[...,:2],uv)
    world[~valid]=np.nan
    np.save(out/'world.npy',world)
    record=dict(camera=camera+1,frames=len(p),observed_paired_frames=int(valid.sum()),inference_seconds=infer_seconds)
    (out/'measurement.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record),flush=True)


def summarize(cfg,out):
    from ct_world import summarize as stats, window_angle
    rows=json.loads(Path(cfg['rows']).read_text(encoding='utf-8'))
    worlds=[np.load(out/str(j)/'world.npy') for j in (0,1)]
    result={}
    for kind in ('knee','elbow'):
        eligible=[r for r in rows if r['kind']==kind and r['reference'] is not None]
        samples=[(r,window_angle(worlds[r['camera']-1],r['frame'],kind,r['hand'])) for r in eligible]
        usable=[(r,v) for r,v in samples if v is not None]
        s=stats([abs(v-r['reference']) for r,v in usable]); s['reference_eligible']=len(eligible); s['coverage']=len(usable)/len(eligible) if eligible else 0
        s['main_crop']=stats([abs(r['crop']-r['reference']) for r in eligible if r['crop'] is not None])
        s['cameras']={str(j):stats([abs(v-r['reference']) for r,v in usable if r['camera']==j]) for j in (1,2)}
        s['passed']=bool(s['n']>=30 and s['coverage']>=.5 and s['median']<=5 and s['p90']<=10)
        result[kind]=s
    with (out/'summary.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('config',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('camera',choices=['0','1','summary']); parser.add_argument('--child',action='store_true')
    a=parser.parse_args(); cfg=json.loads(a.config.read_text(encoding='utf-8'))
    if cfg.get('split')!='development': raise ValueError('僅允許已揭露開發場次')
    repo=Path(__file__).resolve().parents[3]
    sys.path[:0]=[str(repo/'docs/research/caltennis'),str(repo/'tools')]
    if a.camera=='summary': summarize(cfg,a.output); return
    out=a.output/a.camera
    if a.child: child(cfg,int(a.camera),out,repo); return
    from ct_lr_run import memory
    from ct_world_run import release_lock
    if out.exists(): raise FileExistsError('拒絕覆寫')
    busy=subprocess.run(['pgrep','-fl','pose_full|prep.py|ball.py'],capture_output=True,text=True)
    if busy.returncode!=1: raise RuntimeError('其他heavy程序執行中')
    lock=repo/'testset/results/heavy.lock'; lock.parent.mkdir(parents=True,exist_ok=True); lock.mkdir()
    try:
        (lock/'owner.txt').write_text('borrow-pose / CalTennis開發 / lifting機位'+a.camera+' / '+datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),encoding='utf-8')
        low=memory()
        if low<8: raise RuntimeError('記憶體不足8GiB')
        out.mkdir(parents=True); start=time.monotonic()
        with (out/'run.log').open('x',encoding='utf-8') as log:
            proc=subprocess.Popen([sys.executable,'-I',__file__,str(a.config),str(a.output),a.camera,'--child'],stdout=log,stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    low=min(low,memory())
                    if low<8 or time.monotonic()-start>1800: raise RuntimeError('記憶體或30分鐘停止線')
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: pass
            finally:
                if proc.poll() is None: proc.terminate(); proc.wait()
        if proc.returncode: raise RuntimeError('推論失敗，請讀取本機log')
        record=dict(total_seconds=time.monotonic()-start,min_free_inactive_gib=low)
        (out/'guard.json').write_text(json.dumps(record,indent=2),encoding='utf-8'); print(json.dumps(record),flush=True)
    finally: release_lock(lock)


if __name__=='__main__': main()
