import sys,warnings,numpy as np,json,cv2; warnings.filterwarnings("ignore")
from pathlib import Path
P=np.load(sys.argv[1]).astype(np.float64); O=np.load(sys.argv[2]); N=len(P)
c=cv2.VideoCapture(str(Path(sys.argv[1]).parent/"proxy.mp4")); A=np.array([c.get(cv2.CAP_PROP_FRAME_WIDTH),c.get(cv2.CAP_PROP_FRAME_HEIGHT)])/540; c.release()
if not A.all(): sys.exit(f"cannot read {Path(sys.argv[1]).parent/'proxy.mp4'}")
xy=P[:,:,:2]*A; vis=P[:,:,2]
h=(np.nanmean(P[:,[27,28],1],1)-P[:,0,1])*A[1]*9/16  # nose-to-ankle in portrait-frame heights, so 0.11 = 106 px either way
L=np.linalg.norm((xy[:,11]+xy[:,12])/2-(xy[:,23]+xy[:,24])/2,axis=1)
valid=(h>0.11)&(vis[:,16]>0.2)
w=xy[:,16].copy(); w[~valid]=np.nan
v=np.full(N,np.nan); v[1:]=np.linalg.norm(w[1:]-w[:-1],axis=1)/L[1:]
out=[]
for t,pk,on in O:
    f=int(round(t*60))
    if f<30 or f>N-30: continue
    win=v[f-12:f+13]
    if np.isnan(win).mean()>0.5 or valid[f-45:f+15].mean()<0.6: continue
    sp=np.nanmax(win)
    # arc length of wrist over +-0.25s
    seg=w[f-15:f+16]; d=np.linalg.norm(np.diff(seg,axis=0),axis=1)/L[f]; arc=np.nansum(d)
    out.append((t,pk,on,sp,arc))
out=np.array(out).reshape(-1,5)  # (0,5) when no hit sounds
print(len(out),"onsets with player in frame")
for q in [0.5,1,1.5,2,2.5,3]:
    print("arc>",q,(out[:,4]>q).sum())
np.save(sys.argv[3],out)
