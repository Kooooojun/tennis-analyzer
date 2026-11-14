#!/bin/zsh
# One-time setup: Python venv with MediaPipe + OpenCV + PyTorch, the pose model (~30 MB) and the ball-tracking model (~47 MB).
set -e
R=${0:A:h}; cd $R
command -v ffmpeg >/dev/null || { echo "need ffmpeg (macOS: brew install ffmpeg)"; exit 1; }
PY=$(for p in python3.12 python3.11 python3.10; do command -v $p && break; done)
[ -n "$PY" ] || { echo "need Python 3.10-3.12 (macOS: brew install python@3.12)"; exit 1; }
[ -x .venv/bin/python ] || $PY -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p models videos work web/sessions
[ -f models/pose_heavy.task ] || curl -fL -o models/pose_heavy.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task
# Ball-tracking weights (~47 MB), RacketVision BallTrack. The HF model page declares no license; the GitHub repo that links it is MIT (third_party/RacketVision-LICENSE).
[ -f models/balltrack_best.pth ] || curl -fL -o models/balltrack_best.pth \
  https://huggingface.co/linfeng302/RacketVision-Models/resolve/main/checkpoints/balltrack_best.pth
[ "$(shasum -a 256 models/balltrack_best.pth | cut -d' ' -f1)" = 00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342 ] || { echo "balltrack_best.pth checksum mismatch"; exit 1; }
.venv/bin/python -c "import mediapipe, cv2, PIL, numpy; import torch; print('ok: mediapipe', mediapipe.__version__, 'torch', torch.__version__)"
