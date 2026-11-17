"""正式裁切／全畫面 world 的固定角度驗證；只寫本機彙總與逐候選資料。"""
import argparse
import json
from pathlib import Path
import sys
import warnings

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[3] / 'tools')]
from ct_tri import dlt, interp
from ct_lr import SW, SUPPORT, orientation
from proxy import map_pose

LEG = [23, 24, 25, 26, 27, 28]
ARM = {'R': (12, 14, 16), 'L': (11, 13, 15)}


def validate_timestamps(t):
    assert t.ndim == 1 and len(t) >= 2 and np.isfinite(t).all(), '時間須為有限一維陣列且至少兩格'
    dt = np.diff(t)
    assert (dt > 0).all(), '時間須嚴格遞增'
    assert .01 <= np.median(dt) <= .025, 'CalTennis時間須預先轉為共用時鐘秒數（約60fps），不可傳原始毫秒'


def angle_series(P, joints):
    a, b, c = joints
    u, v = P[:, a] - P[:, b], P[:, c] - P[:, b]
    length = np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', u, v) / length, -1, 1)))
    out[~(length > 0)] = np.nan
    return out


def window_angle(P, c, kind, hand):
    lo, hi = (c - 48, c - 5) if kind == 'knee' else (c - 2, c + 3)
    if lo < 0 or hi > len(P): return None
    if kind == 'knee':
        # 兩膝都有效才取最小值，避免 min 對 NaN 的順序依賴。
        vals = np.minimum(angle_series(P[lo:hi], (23,25,27)), angle_series(P[lo:hi], (24,26,28)))
    else: vals = angle_series(P[lo:hi], ARM[hand])
    if np.isfinite(vals).sum() < (35 if kind == 'knee' else 4): return None
    return float(np.nanpercentile(vals, 10) if kind == 'knee' else np.nanmedian(vals))


def paired_mask(xy, uv):
    torso = np.linalg.norm(uv[:, [11,12]].mean(1) - uv[:, [23,24]].mean(1), axis=1)
    displacement = np.linalg.norm(xy[:, [23,24]].mean(1) - uv[:, [23,24]].mean(1), axis=1)
    return np.isfinite(displacement) & (torso > 0) & (displacement < .5 * torso)


def fundamental(Pa, Pb):
    C = np.linalg.svd(Pa)[2][-1]; e = Pb @ C
    ex = np.array([[0,-e[2],e[1]],[e[2],0,-e[0]],[-e[1],e[0],0]])
    return ex @ Pb @ np.linalg.pinv(Pa)


def sync_shift(ta, ua, tb, ub, Fm):
    validate_timestamps(ta); validate_timestamps(tb)
    ids = np.arange(0, len(ta), 4); js = [0,11,12,15,16,23,24,27,28]
    a = ua[ids][:,js,:2].reshape(-1,2); lines = np.c_[a,np.ones(len(a))] @ Fm.T
    lines = lines.reshape(len(ids),len(js),3)
    def score(d):
        query = ta[ids] + d/60
        overlap = (query >= tb[0]) & (query <= tb[-1])
        b = interp(query[overlap], tb, ub)[:,js,:2].reshape(-1,2)
        selected = lines[overlap].reshape(-1,3)
        with np.errstate(invalid='ignore',divide='ignore'):
            distances = abs(np.sum(selected * np.c_[b,np.ones(len(b))],1)) / np.hypot(selected[:,0],selected[:,1])
        return float(np.nanmedian(distances)) if np.isfinite(distances).sum() >= max(100, .8 * len(distances)) else float('inf')
    coarse = min(range(-1200,1201,20), key=score)
    best = min(range(coarse-25,coarse+26), key=score)
    error = score(best)
    if not np.isfinite(error) or error > 5: raise ValueError('參考時間同步未過 5 px 門檻')
    return best, error


def summarize(values):
    x = np.asarray(values,float); x = x[np.isfinite(x)]
    return dict(n=len(x), median=float(np.median(x)) if len(x) else None,
                p90=float(np.percentile(x,90)) if len(x) else None)


def reference(A, B, Pa, Pb, shift, delta=0):
    ua = A['lm'][...,:2]; ub = interp(A['t'] + (shift+delta)/60, B['t'], B['lm'])[...,:2]
    X,e = dlt([Pa,Pb],np.stack([ua,ub])); Y,f = dlt([Pa,Pb],np.stack([ua,ub[:,SW]]))
    swap = np.nanmedian(f[:,SUPPORT],1) < np.nanmedian(e[:,SUPPORT],1)
    X[swap],e[swap] = Y[swap],f[swap]
    state = orientation(X,e)
    # 沿用 ct_eval 的面向 canon；肘另須較嚴格的面向一致，避免無證據左右。
    fw = X[:,0] - X[:,[11,12]].mean(1) + (X[:,[31,32]].sum(1)-X[:,[29,30]].sum(1))/2
    flip = np.einsum('ij,ij->i',X[:,24]-X[:,23],np.cross(fw,[0,0,1])) < 0
    X[flip],e[flip] = X[flip][:,SW],e[flip][:,SW]
    for P in (Pa,Pb):
        depth = X @ P[2,:3] + P[2,3]
        X[depth<=0] = np.nan
    X[e>20] = np.nan
    uv = X @ Pa[:,:3].T + Pa[:,3]; uv=uv[...,:2]/uv[...,2:]
    return X,e,state,uv


def peaks(v):
    keep=[]
    for i in np.argsort(-np.nan_to_num(v)):
        if v[i]>15 and all(abs(i-k)>=60 for k in keep): keep.append(int(i))
    return sorted(keep)


def evaluate(manifest_path, output):
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    root=Path(manifest_path).parent
    cams=manifest['cameras']; refs=[dict(np.load(root/c['reference'])) for c in cams]
    for ref in refs: validate_timestamps(ref['t'])
    Ps=[np.array(json.loads((root/c['calibration']).read_text())['K']) @ np.array(json.loads((root/c['calibration']).read_text())['Rt_w2c']) for c in cams]
    shift=manifest.get('shift_frames')
    sync_error=None
    if shift is None: shift,sync_error=sync_shift(refs[0]['t'],refs[0]['lm'],refs[1]['t'],refs[1]['lm'],fundamental(*Ps))
    rows=[]; diagnostics=[]
    for j in (0,1):
        A,B=refs[j],refs[1-j]; Pa,Pb=Ps[j],Ps[1-j]; sh=shift if j==0 else -shift
        X,e,state,uv=reference(A,B,Pa,Pb,sh)
        speed={h: np.convolve(np.nan_to_num(np.linalg.norm(np.diff(X[:,w],axis=0),axis=1)*60),np.ones(3)/3,'same') for h,w in [('L',15),('R',16)]}
        hits=[c for c in peaks(np.fmax(speed['L'],speed['R'])) if 48<=c<len(X)-3]
        worlds={}; seen={}; paired={}
        for mode in ('crop','full'):
            d=root/cams[j][mode]; P=np.load(d/'pose.npy'); W=np.load(d/'pose_world.npy').copy()
            assert len(P)==len(W)==len(A['t']), '正式輸出與參考長度不同'
            assert np.array_equal(np.load(d/'t.npy'),A['t']), '正式輸出與參考時間不同'
            xy=map_pose(P,*cams[j]['size'],inverse=True)[...,:2]*cams[j]['size']
            same=paired_mask(xy,uv); W[~same]=np.nan
            worlds[mode]=W; seen[mode]=int(np.isfinite(P[:,0,0]).sum()); paired[mode]=int(same.sum())
        C=np.array(json.loads((root/cams[j]['calibration']).read_text())['C']).reshape(3)
        right=X[:,24]-X[:,23]; fw=np.cross([0,0,1],right);fw[:,2]=0
        to=C-X[:,[23,24]].mean(1);to[:,2]=0
        az=np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',fw,to)/(np.linalg.norm(fw,axis=1)*np.linalg.norm(to,axis=1)),-1,1)))
        variants=[reference(A,B,Pa,Pb,sh,d)[0] for d in (-1,1)]
        for c in hits:
            hand='L' if speed['L'][c]>speed['R'][c] else 'R'
            for kind in ('knee','elbow'):
                ids=np.arange(c-48,c-5) if kind=='knee' else np.arange(c-2,c+3)
                joints=LEG if kind=='knee' else list(ARM[hand])
                ref=X.copy()
                if kind=='elbow': ref[state<0]=np.nan
                truth=window_angle(ref,c,kind,hand)
                reasons=[]
                if window_angle(X,c,kind,hand) is None: reasons.append('缺值或退化角度')
                if kind=='elbow' and np.sum(state[ids]>=0)<4: reasons.append('解剖左右不確定')
                if not np.isfinite(e[ids][:,joints]).any() or np.nanmedian(e[ids][:,joints])>10:
                    truth=None; reasons.append('窗口重投影誤差')
                row=dict(camera=j+1,frame=c,kind=kind,hand=hand,reference=truth,reference_rejections=reasons,
                         azimuth=float(np.nanmedian(az[ids])) if np.isfinite(az[ids]).any() else None)
                for mode,W in worlds.items(): row[mode]=window_angle(W,c,kind,hand)
                row['sync_sensitivity']=[abs(v-truth) if truth is not None and (v:=window_angle(V,c,kind,hand)) is not None else None for V in variants]
                rows.append(row)
        diagnostics.append(dict(camera=j+1,frames=len(X),candidates=len(hits),seen=seen,paired_frames=paired))
    result=dict(sync_shift_frames=shift,sync_error_px=sync_error,cameras=diagnostics,metrics={})
    for kind in ('knee','elbow'):
        eligible=[r for r in rows if r['kind']==kind and r['reference'] is not None]
        metric=dict(candidates=sum(r['kind']==kind for r in rows),reference_eligible=len(eligible),modes={},reference_rejections={reason:sum(reason in r['reference_rejections'] for r in rows if r['kind']==kind) for reason in ('缺值或退化角度','解剖左右不確定','窗口重投影誤差')})
        for mode in ('crop','full'):
            usable=[r for r in eligible if r[mode] is not None]
            signed=[r[mode]-r['reference'] for r in usable]
            stats=summarize(np.abs(signed));stats['bias']=float(np.mean(signed)) if signed else None
            stats['coverage']=len(usable)/len(eligible) if eligible else 0
            stats['passed']=bool(stats['n']>=30 and stats['coverage']>=.5 and stats['median']<=5 and stats['p90']<=10)
            stats['cameras']={str(j):summarize([abs(r[mode]-r['reference']) for r in usable if r['camera']==j]) for j in (1,2)}
            stats['azimuth']={f'{lo}-{hi}':summarize([abs(r[mode]-r['reference']) for r in usable if r['azimuth'] is not None and lo<=r['azimuth'] and (r['azimuth']<hi or hi==180 and r['azimuth']<=hi)]) for lo,hi in ((0,30),(30,60),(60,120),(120,180))}
            metric['modes'][mode]=stats
        common=[r for r in eligible if all(r[m] is not None for m in ('crop','full'))]
        metric['common']={m:summarize([abs(r[m]-r['reference']) for r in common]) for m in ('crop','full')}
        metric['sync_sensitivity']=summarize([v for r in eligible for v in r['sync_sensitivity'] if v is not None])
        result['metrics'][kind]=metric
    output=Path(output)
    with output.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    with output.with_suffix('.rows.json').open('x',encoding='utf-8') as f: json.dump(rows,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest');parser.add_argument('output')
    args=parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        evaluate(args.manifest,args.output)
