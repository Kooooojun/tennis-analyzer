# highlights.py <session> — highlight reel from work/<s>/reel.json -> web/sessions/<s>/reel.mp4
# Clips are zoomed on the player, slowed to 0.5x with skeleton + live knee angle, and freeze at contact. reel.json:
#   [{"type":"card","title":"11/05 練習精華","lines":[["自拋 155°、對打 135°","ink"],["10/27：163°","mute"]],"secs":3},
#    {"type":"clip","title":"對打蹲得最好 #05","sub":"膝蓋彎、重心低","items":[[5,"#05 對打正拍"]]},
#    {"type":"clip","title":"自拋進步了","sub":"左 10/27、右 11/05","items":[[["2026-10-27",23],"10/27 #23"],[17,"11/05 #17"]]}]
# Stroke numbers are the final ones shown on the page; [session, no] reaches into another session. One or two items per clip.
import subprocess,sys,numpy as np,cv2
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from common import ROOT, session, work, web, load, PORTRAIT
S=session(); OUT=web(S)/"reel.mp4"; W,H=1080,1350; TOP=230; FPS=30
FONTS=["/System/Library/Fonts/STHeiti Medium.ttc","/System/Library/Fonts/PingFang.ttc","/System/Library/Fonts/Hiragino Sans GB.ttc",
       "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc","/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc","C:/Windows/Fonts/msjh.ttc"]
FONT=next((f for f in FONTS if Path(f).exists()),None) or sys.exit("no CJK font found; add one to FONTS in highlights.py")
F=lambda n:ImageFont.truetype(FONT,n)
D={}
def stroke(ref):
    s,n=(ref if isinstance(ref,list) else [S,ref])
    if s not in D: D[s]=load(web(s)/"strokes.json")
    x=D[s][n-1]; return {**x,"path":str(web(s)/x["src"])}
EDGES=[(1,2),(1,3),(3,5),(2,4),(4,6),(1,7),(2,8),(7,8),(7,9),(9,11),(8,10),(10,12)]
BG=(18,20,24); INK=(240,240,240); MUTE=(160,165,175); GOOD=(74,222,128); WARN=(251,191,36); BAD=(248,113,113)
kc=lambda a:MUTE if a is None else GOOD if a<=130 else WARN if a<=150 else BAD

def frames(s):
    cap=cv2.VideoCapture(s['path']); out=[]
    while True:
        ok,im=cap.read()
        if not ok: break
        out.append(im)
    return out
def box(s,aspect):
    sw,sh=s.get('size',PORTRAIT)
    P=[f for f in s['frames'] if f]; cx=np.median([(f[7][0]+f[8][0])/2 for f in P])*sw
    top=np.median([f[0][1] for f in P])*sh; ank=np.median([(f[11][1]+f[12][1])/2 for f in P])*sh
    h=min(sh,max(300*sh/960,(ank-top)*1.9)); w=min(sw,h*aspect); h=w/aspect
    cy=(top+ank)/2; x0=int(np.clip(cx-w/2,0,sw-w)); y0=int(np.clip(cy-h/2,0,sh-h))
    return x0,y0,int(w),int(h)
def ang(f,a,b,c,size):
    A,B,C=[np.array(f[i][:2])*size for i in (a,b,c)]; v1,v2=A-B,C-B; n=np.linalg.norm(v1)*np.linalg.norm(v2)
    return np.degrees(np.arccos(np.clip(v1@v2/n,-1,1))) if n else None
def ang3(w,a,b,c):
    A,B,C=[np.array(w[i]) for i in (a,b,c)]; v1,v2=A-B,C-B; n=np.linalg.norm(v1)*np.linalg.norm(v2)
    return np.degrees(np.arccos(np.clip(v1@v2/n,-1,1))) if n else None
def panel(s,im,i,size,bx):
    x0,y0,w,h=bx; k=size[0]/w
    crop=cv2.resize(im[y0:y0+h,x0:x0+w],size,interpolation=cv2.INTER_CUBIC)
    pil=Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)); d=ImageDraw.Draw(pil)
    f=s['frames'][i] if i<len(s['frames']) else None
    if f:
        sw,sh=s.get('size',PORTRAIT); P=lambda j:((f[j][0]*sw-x0)*k,(f[j][1]*sh-y0)*k)
        for a,b in EDGES: d.line([P(a),P(b)],fill=(255,140,70) if a%2==0 and b%2==0 else (90,180,255),width=5)
        for j in range(13): x,y=P(j); d.ellipse([x-5,y-5,x+5,y+5],fill=(255,255,255))
        w=s['world'][i] if s.get('world') and i<len(s['world']) else None  # 3D when the session has world data
        kr,kl=(ang3(w,8,10,12),ang3(w,7,9,11)) if w else (ang(f,8,10,12,(sw,sh)),ang(f,7,9,11,(sw,sh)))
        if kr and kl:
            a,j=(kr,10) if kr<=kl else (kl,9); x,y=P(j)
            d.text((x+14,y-18),f"{a:.0f}°{'3D' if w else '2D'}",font=F(34),fill=kc(a),stroke_width=4,stroke_fill=(0,0,0))
    if i==s['contact']:
        d.text((16,size[1]-70),"擊球",font=F(46),fill=(255,214,10),stroke_width=4,stroke_fill=(0,0,0))
    return pil
def header(title,sub,lines=()):
    im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im)
    d.text((48,40),title,font=F(58),fill=INK); d.text((48,120),sub,font=F(34),fill=MUTE)
    return im,d
def label(d,x,y,s,tag,col):
    d.text((x,y),tag,font=F(34),fill=INK,stroke_width=3,stroke_fill=(0,0,0))
    k=s['knee3d'] if s.get('knee3d') is not None else s['knee']
    if k is not None: d.text((x,y+44),f"準備時膝蓋 {'3D' if s.get('knee3d') is not None else '2D'} {k:.0f}°",font=F(30),fill=col,stroke_width=3,stroke_fill=(0,0,0))
    if s.get('knee_warn'): d.text((x,y+84),"擊球格不可信，這拍不量" if s.get("knee_warn_why")=="contact" else "這拍角度不準",font=F(30),fill=BAD,stroke_width=3,stroke_fill=(0,0,0))

class Out:
    def __init__(s,path): s.p=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-c:v","libx264","-preset","slow","-crf","22","-pix_fmt","yuv420p","-movflags","+faststart",path],stdin=subprocess.PIPE)
    def put(s,im,n=1):
        b=np.asarray(im,np.uint8).tobytes()
        for _ in range(n): s.p.stdin.write(b)
    def close(s): s.p.stdin.close(); s.p.wait()

def clip(o,title,sub,items,hold=24):
    """items: [(ref,tag)] one or two; plays frames contact-60..contact+30 at 0.5x, holds contact."""
    S=[stroke(r) for r,_ in items]; n=len(S); pw=W//n; ph=H-TOP
    V=[frames(s) for s in S]; B=[box(s,pw/ph) for s in S]
    for t in range(-60,31):
        im,d=header(title,sub)
        for j,s in enumerate(S):
            i=max(0,min(len(V[j])-1,s['contact']+t))
            im.paste(panel(s,V[j][i],i,(pw,ph),B[j]),(j*pw,TOP))
            label(d,j*pw+20,TOP+16,s,items[j][1],kc(s['knee3d'] if s.get('knee3d') is not None else s['knee']))
        if n==2: d.line([(pw,TOP),(pw,H)],fill=BG,width=6)
        o.put(im,hold if t==0 else 1)
def card(o,title,lines,secs=3.5):
    im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); d.text((64,300),title,font=F(64),fill=INK); y=440
    for ln,col in lines: d.text((64,y),ln,font=F(40),fill=col); y+=78
    o.put(im,int(secs*FPS))

COL={"ink":INK,"mute":MUTE,"good":GOOD,"warn":WARN,"bad":BAD}
o=Out(str(OUT))
for seg in load(work(S)/"reel.json"):
    if seg["type"]=="card": card(o,seg["title"],[(t,COL[c]) for t,c in seg.get("lines",[])],seg.get("secs",3.5))
    else: clip(o,seg["title"],seg.get("sub",""),seg["items"])
o.close(); print("wrote",OUT)
