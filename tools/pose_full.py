import sys,subprocess,numpy as np,mediapipe as mp,cv2
from mediapipe.tasks.python import vision, BaseOptions
src,model,out=sys.argv[1:4]
c=cv2.VideoCapture(src); W,H=int(c.get(cv2.CAP_PROP_FRAME_WIDTH)),int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)); c.release()  # 540x960 or 960x540
p=subprocess.Popen(["ffmpeg","-v","error","-i",src,"-an","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
lm=vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=model),running_mode=vision.RunningMode.VIDEO,min_pose_detection_confidence=0.3,min_tracking_confidence=0.3))
rows=[];n=0
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3:break
    r=lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.frombuffer(b,np.uint8).reshape(H,W,3)),int(n*1000/60))
    rows.append([[q.x,q.y,q.visibility] for q in r.pose_landmarks[0]] if r.pose_landmarks else np.full((33,3),np.nan))
    n+=1
    if n%6000==0: print(n,flush=True)
np.save(out,np.array(rows,dtype=np.float32)); print("done",n)
