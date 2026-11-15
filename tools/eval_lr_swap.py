# eval_lr_swap.py <work/session> [out.json]: measure left/right label swaps and one-frame skeleton jumps on existing pose files (no pose re-run).
# Per video/track: share of frames where the elbow or wrist labels swap. Per stroke in strokes_all.json: metrics.pose_flags (+-FLAG_WIN frames).
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import swap_frames, pose_flags, _scale, _med, FULL, FLAG_WIN
from platform_util import read_text, write_text, utf8_stdout


def main():
    utf8_stdout(); W = Path(sys.argv[1]); S = json.loads(read_text(W / "strokes_all.json")); cache = {}; per_video = {}; rows = []
    for s in S:
        key = (s["video"], s["track"])
        if key not in cache:
            P = np.load(W / s["video"] / ("pose.npy" if not s["track"] else f"pose_t{s['track']}.npy")).astype(float)
            xy = P[:, :, :2] * _scale(s.get("size")); cache[key] = xy
            L = _med(np.linalg.norm((xy[:, 11] + xy[:, 12]) / 2 - (xy[:, 23] + xy[:, 24]) / 2, axis=1)); fr = np.arange(1, len(xy))
            sw = swap_frames(xy, FULL, L, fr); ok = sw[0][1] | sw[1][1]
            per_video[f"{key[0]}/t{key[1]}"] = dict(frames=int(ok.sum()), swap_frames=int(((sw[0][0] & sw[0][1]) | (sw[1][0] & sw[1][1]))[ok].sum()))
        rows.append(dict(video=s["video"], track=s["track"], t=s["t"], f=s["f"], player=s.get("player"), **pose_flags(cache[key], FULL, s["f"])))
    for v in per_video.values(): v["swap_rate"] = round(v["swap_frames"] / max(v["frames"], 1), 4)
    rate = lambda k: round(np.mean([bool(r[k]) for r in rows]), 3) if rows else None
    out = dict(win=FLAG_WIN, per_video=per_video, strokes=len(rows), lr_swap_rate=rate("lr_swap"), pose_jump_rate=rate("pose_jump"), rows=rows)
    for k, v in per_video.items(): print(f"{k}: swap frames {v['swap_frames']}/{v['frames']} ({v['swap_rate']:.2%})")
    print(f"{len(rows)} strokes: lr_swap within +-{FLAG_WIN} frames {out['lr_swap_rate']:.1%}, pose_jump {out['pose_jump_rate']:.1%}")
    if len(sys.argv) > 2: write_text(Path(sys.argv[2]), json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
