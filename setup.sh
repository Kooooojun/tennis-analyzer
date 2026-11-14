#!/bin/zsh
# One-time setup: Python venv with MediaPipe + OpenCV, and the pose model (~30 MB).
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
.venv/bin/python -c "import mediapipe, cv2, PIL, numpy; print('ok: mediapipe', mediapipe.__version__)"
