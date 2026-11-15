#!/bin/zsh
# usage: tools/prep.sh <session> [people]   e.g. tools/prep.sh 2026-11-05   (people = max people to track, default 2)
# For every video in videos/<session>/: 60fps proxy (540x960 portrait, 960x540 landscape), high-passed audio, pose (one file per tracked person), hit sounds, ball track, hit events (sound + ball).
# Wrist motion per hit (match.py) runs in candidates.py, once the racket hand of each person is known.
# Re-running skips finished steps, so it is safe to resume after an interruption.
set -e -o pipefail
R=${0:A:h:h}; S=$1; N=${2:-2}; PY=$R/.venv/bin/python
[ -n "$S" ] && [ -d $R/videos/$S ] || { echo "usage: tools/prep.sh <session> [people]  (folder under videos/)"; exit 1; }
[ -x $PY ] || { echo "run ./setup.sh first"; exit 1; }
W=$R/work/$S; mkdir -p $W
if [ "$(uname)" = Darwin ]; then ENC=(-c:v h264_videotoolbox -b:v 2500k); else ENC=(-c:v libx264 -preset veryfast -crf 23); fi
names=()
for V in $R/videos/$S/*.(mov|MOV|mp4|MP4|m4v)(N); do
  n=${V:t:r}; names+=$n; D=$W/$n; mkdir -p $D
  read w h < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height:stream_side_data=rotation -of default=nw=1 $V |
    awk -F= '/^width/{w=$2} /^height/{h=$2} /^rotation/{r=$2} END{ if (r==90||r==-90||r==270||r==-270) print h, w; else print w, h }')
  echo "== $n"
  # shortcut: assumes 16:9 sources (phone video); other ratios get stretched, as before
  [ -f $D/proxy.mp4 ] || ffmpeg -v error -y -i $V -an -vf "scale=$( (( w > h )) && echo 960:540 || echo 540:960 ),fps=60" $ENC -g 30 $D/proxy.mp4
  [ -f $D/audio_hp.f32 ] || ffmpeg -v error -y -i $V -vn -ac 1 -ar 16000 -af "highpass=f=1500" -f f32le $D/audio_hp.f32
  [ -f $D/audio.f32 ] || ffmpeg -v error -y -i $V -vn -ac 1 -ar 16000 -f f32le $D/audio.f32
  [ -f $D/pose.npy ] || $PY -I $R/tools/pose_full.py $D/proxy.mp4 $R/models/pose_heavy.task $D/pose.npy $N 2>$D/pose.log
  [ -f $D/sounds.npy ] || $PY -I $R/tools/hits.py $D/audio_hp.f32 $D/audio.f32 $D/sounds.npy
  [ -f $D/ball.npy ] || $PY -I $R/tools/ball.py $D/proxy.mp4 $D/ball.npy >$D/ball.log
  [ $D/events.npy -nt $D/sounds.npy ] || $PY -I $R/tools/events.py $D/sounds.npy $D/ball.npy $D/pose.npy $D/events.npy >/dev/null
done
(( ${#names} )) || { echo "no videos in videos/$S"; exit 1; }
printf '%s\n' $names | $PY -c 'import json,sys; print(json.dumps(sys.stdin.read().split()))' > $W/videos.json
echo "ready: ${#names} videos -> work/$S"
