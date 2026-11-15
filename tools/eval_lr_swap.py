# eval_lr_swap.py <work/session> [out.json]: measure left/right label swaps and one-frame skeleton jumps on existing pose files (no pose re-run).
# Per video/track: share of frames where the elbow or wrist labels swap. Per stroke in strokes_all.json: metrics.pose_flags (+-FLAG_WIN frames).
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import swap_frames, pose_flags, _scale, _med, FULL, FLAG_WIN
from common import track_file
from platform_util import read_text, write_text, utf8_stdout


def main():
    utf8_stdout(); W = Path(sys.argv[1]); S = json.loads(read_text(W / "strokes_all.json")); cache = {}; per_video = {}; rows = []
    for s in S:
        key = (s["video"], s.get("track", 0))
        if key not in cache:
            P = np.load(track_file(W / s["video"], "pose", key[1])).astype(float)
            xy = P[:, :, :2] * _scale(s.get("size")); cache[key] = xy
            L = _med(np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1)); fr = np.arange(1, len(xy))
            sw = swap_frames(xy, FULL, L, fr) if L else None  # no visible torso in the whole video: nothing to measure
            ok = sw[0][1] | sw[1][1] if sw else np.zeros(len(fr), bool)
            per_video[f"{key[0]}/t{key[1]}"] = dict(frames=int(ok.sum()), swap_frames=int(((sw[0][0] & sw[0][1]) | (sw[1][0] & sw[1][1]))[ok].sum()) if sw else 0)
        rows.append(dict(video=s["video"], track=key[1], t=s["t"], f=s["f"], player=s.get("player"), **pose_flags(cache[key], FULL, s["f"])))
    for v in per_video.values(): v["swap_rate"] = round(v["swap_frames"] / v["frames"], 4) if v["frames"] else None  # nothing measurable: unknown, not 0
    rate = lambda k: (lambda v: round(np.mean(v), 3) if v else None)([r[k] for r in rows if r[k] is not None])  # unknown (null) strokes are not in the denominator
    out = dict(win=FLAG_WIN, per_video=per_video, strokes=len(rows), lr_swap_rate=rate("lr_swap"), pose_jump_rate=rate("pose_jump"), rows=rows)
    pc = lambda v: "unknown" if v is None else f"{v:.1%}"
    for k, v in per_video.items(): print(f"{k}: swap frames {v['swap_frames']}/{v['frames']} ({pc(v['swap_rate'])})")
    print(f"{len(rows)} strokes: lr_swap within +-{FLAG_WIN} frames {pc(out['lr_swap_rate'])}, pose_jump {pc(out['pose_jump_rate'])}")
    if len(sys.argv) > 2: write_text(Path(sys.argv[2]), json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
