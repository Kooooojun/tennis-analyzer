#!/bin/zsh
# usage: tools/prep.sh <session> [people]   e.g. tools/prep.sh 2026-11-05   (people = max people to track, default 2)
# For every video in videos/<session>/: 60fps proxy (540x960 portrait, 960x540 landscape), high-passed audio, pose (one file per tracked person), hit sounds, ball track, hit events (sound + ball).
# Wrist motion per hit (match.py) runs in candidates.py, once the racket hand of each person is known.
# Re-running skips finished steps, so it is safe to resume after an interruption; a step re-runs when its output is missing or an input is newer.
set -e -o pipefail
del() { if command -v trash >/dev/null; then trash "$@"; else command rm -f -- "$@"; fi; }  # trash when installed, so a mistake can be undone
R=${0:A:h:h}; S=$1; N=${2:-2}; PY=$R/.venv/bin/python
[ -n "$S" ] && [ -d $R/videos/$S ] || { echo "usage: tools/prep.sh <session> [people]  (folder under videos/)"; exit 1; }
[ -x $PY ] || { echo "run ./setup.sh first"; exit 1; }
W=$R/work/$S; mkdir -p $W
if [ "$(uname)" = Darwin ]; then ENC=(-c:v h264_videotoolbox -b:v 2500k); else ENC=(-c:v libx264 -preset veryfast -crf 23); fi
# stale OUT IN...: true when OUT is missing or any input is newer, so a re-run upstream rebuilds what hangs off it
stale() { local o=$1 i; shift; [ -f $o ] || return 0; for i; do [[ $i -nt $o ]] && return 0; done; return 1 }
names=()
for V in $R/videos/$S/*.(mov|MOV|mp4|MP4|m4v)(N); do
  n=${V:t:r}; names+=$n; D=$W/$n; mkdir -p $D
  read w h < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height:stream_side_data=rotation -of default=nw=1 $V |
    awk -F= '/^width/{w=$2} /^height/{h=$2} /^rotation/{r=$2} END{ if (r==90||r==-90||r==270||r==-270) print h, w; else print w, h }')
  echo "== $n"
  # source fps (avg handles variable frame rate); the proxy below is always 60 fps, so a 30 fps source becomes duplicated frames
  fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of csv=p=0 $V | awk -F/ '{ d=($2==""?1:$2); if (d>0 && $1+0>0) printf "%d", $1/d+0.5 }' || true)  # ffprobe failing must not stop prep (set -e, pipefail)
  if [ -n "$fps" ]; then echo $fps > $D/src_fps.txt; elif [ -f $D/src_fps.txt ]; then del $D/src_fps.txt; fi  # unreadable: no stale value from an earlier video
  [ -n "$fps" ] && (( fps < 50 )) && echo "警告：$n 來源 ${fps} fps，proxy 會補成 60 fps（重複影格），速度類數字（手速、準備時間）沒驗證過" >&2
  # shortcut: assumes 16:9 sources (phone video); other ratios get stretched, as before
  stale $D/proxy.mp4 $V && ffmpeg -v error -y -i $V -an -vf "scale=$( (( w > h )) && echo 960:540 || echo 540:960 ),fps=60" $ENC -g 30 $D/proxy.mp4
  stale $D/audio_hp.f32 $V && ffmpeg -v error -y -i $V -vn -ac 1 -ar 16000 -af "highpass=f=1500" -f f32le $D/audio_hp.f32
  stale $D/audio.f32 $V && ffmpeg -v error -y -i $V -vn -ac 1 -ar 16000 -f f32le $D/audio.f32
  # a different people count means a different pose run; no people.txt (older work dir) = trust what is there
  [ -f $D/people.txt ] && [ -f $D/pose.npy ] && [ "$(<$D/people.txt)" != $N ] && del $D/pose.npy
  for t in $D/pose*_t*.npy(N); do (( ${${t:t:r}##*_t} >= N )) && del $t; done  # extra tracks from an earlier, larger run
  stale $D/pose.npy $D/proxy.mp4 && $PY -I $R/tools/pose_full.py $D/proxy.mp4 $R/models/pose_heavy.task $D/pose.npy $N 2>$D/pose.log
  echo $N > $D/people.txt
  stale $D/sounds.npy $D/audio_hp.f32 $D/audio.f32 && $PY -I $R/tools/hits.py $D/audio_hp.f32 $D/audio.f32 $D/sounds.npy
  stale $D/ball.npy $D/proxy.mp4 && $PY -I $R/tools/ball.py $D/proxy.mp4 $D/ball.npy >$D/ball.log
  stale $D/events.npy $D/sounds.npy $D/ball.npy $D/pose.npy && $PY -I $R/tools/events.py $D/sounds.npy $D/ball.npy $D/pose.npy $D/events.npy >/dev/null
done
(( ${#names} )) || { echo "no videos in videos/$S"; exit 1; }
printf '%s\n' $names | $PY -c 'import json,sys; print(json.dumps(sys.stdin.read().split()))' > $W/videos.json
echo "ready: ${#names} videos -> work/$S"
