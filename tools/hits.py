import sys,numpy as np
a=np.fromfile(sys.argv[1],np.float32); SR=16000; hop=80  # 5ms
n=len(a)//hop; e=np.sqrt((a[:n*hop].reshape(n,hop)**2).mean(1))+1e-6
db=20*np.log10(e)
bg=np.array([np.median(db[max(0,i-40):i-2]) if i>2 else db[0] for i in range(n)])  # 200ms background
on=db-bg
cand=[]
for i in np.argsort(-on):
    if on[i]<18: break
    if any(abs(i-j)<80 for j in cand): continue  # 0.4s
    cand.append(i)
cand=sorted(cand)
t=np.array(cand)*hop/SR; pk=np.array([db[i:i+6].max() for i in cand])
np.save(sys.argv[2],np.stack([t,pk,on[cand]],1))
print(len(t),"onsets; peak dB pct",np.percentile(pk,[10,50,90]).round(1) if len(pk) else "-")
