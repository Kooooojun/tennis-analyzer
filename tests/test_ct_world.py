"""研究純函式：先寫測試，再實作；不需要資料集。"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'docs/research/caltennis'))
from ct_world import angle_series, window_angle, paired_mask, sync_shift, summarize
from ct_lr import SW

P = np.zeros((60, 33, 3))
for a, b, c in ((23,25,27),(24,26,28),(11,13,15),(12,14,16)):
    P[:, a] = [1,0,0]; P[:, b] = [0,0,0]; P[:, c] = [0,1,0]
assert np.allclose(angle_series(P, (23,25,27)), 90)
assert window_angle(P, 50, 'knee', 'R') == 90
assert window_angle(P, 50, 'elbow', 'L') == 90
assert window_angle(P, 47, 'knee', 'R') is None
Q = P.copy(); Q[2:11, 27] = np.nan
assert window_angle(Q, 50, 'knee', 'R') is None
Q = P.copy(); Q[48:50, 15] = np.nan
assert window_angle(Q, 50, 'elbow', 'L') is None
Q = P.copy(); Q[:, 27] = 0
assert np.isnan(angle_series(Q, (23,25,27))).all()
uv = np.zeros((5,33,2)); uv[:,11:13,1] = 100; uv[:,23:25,1] = 200
xy = uv.copy(); xy[1] += [60,0]; xy[2] = np.nan
assert paired_mask(xy, uv).tolist() == [True,False,False,True,True]
s = summarize([1,2,3,np.nan]); assert s['n'] == 3 and s['median'] == 2
assert summarize([])['median'] is None
# 以已知對極幾何與連續變動軌跡測同步，避免只測實作算式。
t = np.arange(900)/60; u = np.zeros((900,33,3)); u[...,2]=1
u[...,0]=np.sin(t[:,None]*2)*50+np.arange(33); u[...,1]=t[:,None]**2 + t[:,None]*3+100
v=u.copy(); v[...,0]-=10
Fm=np.array([[0,0,0],[0,0,-1],[0,1,0]])
shift, err=sync_shift(t,u,t+7/60,v,Fm)
assert shift == 7 and err < 1e-8, (shift,err)
try: sync_shift(t,u,t,v* np.nan,Fm)
except ValueError: pass
else: raise AssertionError('全缺值同步必須拒絕')
print('ct_world：角度、缺值、窗口、錯人、同步、空樣本通過')

from ct_world import reference
# 兩機水平基線；三角測量應還原已知3D，左右交換不影響最小膝角。
X=P.copy();X[...,2]+=5
Pa=np.array([[500.,0,0,0],[0,500.,0,0],[0,0,1,0]])
Pb=Pa.copy();Pb[0,3]=-500
ua=X@Pa[:,:3].T+Pa[:,3];ua[...,:2]/=ua[...,2:]
ub=X@Pb[:,:3].T+Pb[:,3];ub[...,:2]/=ub[...,2:]
A={'t':np.arange(60)/60,'lm':ua}; B={'t':A['t'],'lm':ub}
R,e,_,uv=reference(A,B,Pa,Pb,0)
assert np.nanmax(e)<1e-8
assert abs(window_angle(R,50,'knee','R')-90)<1e-7
assert window_angle(P[:,SW],50,'knee','R')==90
print('ct_world：已知雙機3D還原與膝角交換不變量通過')
