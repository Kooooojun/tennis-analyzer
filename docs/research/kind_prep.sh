#!/bin/zsh
# kind_prep.sh <video> [secs] — 960x540 60fps proxy + pose for one raw video -> work/kind/<id>/ (stroke-classify 標準答案用；從 repo 根目錄跑)
set -e; V=$1; id=${V:t:r}; D=work/kind/$id; mkdir -p $D
T=(); [ -n "$2" ] && T=(-t $2)
[ -f $D/proxy.mp4 ] || ffmpeg -v error -y $T -i $V -an -vf "scale=960:540,fps=60" -c:v h264_videotoolbox -b:v 2500k -g 30 $D/proxy.mp4
[ -f $D/pose.npy ] || .venv/bin/python -I tools/pose_full.py $D/proxy.mp4 models/pose_heavy.task $D/pose.npy 2>$D/pose.log
echo done $id
