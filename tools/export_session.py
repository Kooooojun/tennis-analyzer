# export_session.py <session> — one 150-frame clip per stroke (contact at frame 90; clamped to the video start/end, so shorter clips carry their own contact index) plus trimmed pose
# -> web/sessions/<s>/clips/sNN.mp4 and web/sessions/<s>/strokes_raw.json. Stroke numbers here are what refine.json refers to.
import subprocess, sys, numpy as np
from common import session, work, web, load, save, KEEP, PORTRAIT, track_file

s = session(); Wd = work(s); D = web(s); (D / "clips").mkdir(parents=True, exist_ok=True)
r = load(Wd / "strokes_all.json")
P = {key: np.load(track_file(Wd / key[0], "pose", key[1])) for key in {(x["video"], x.get("track", 0)) for x in r}}
WP = {key: track_file(Wd / key[0], "pose_world", key[1]) for key in P}; WP = {key: np.load(p) for key, p in WP.items() if p.exists()}
for (v, k), w in WP.items():
    if len(w) != len(P[v, k]): print(f"warning: video {next(x['vn'] for x in r if x['video'] == v)} track {k}: pose_world has {len(w)} frames, pose has {len(P[v, k])}; using 2D only", file=sys.stderr)
WP = {key: w for key, w in WP.items() if len(w) == len(P[key])}  # pose_world from another run: frames do not line up, use 2D only (as measure_full)
for old in (D / "clips").glob("s*.mp4"): old.unlink()
out = []
for i, x in enumerate(r):
    key = (x["video"], x.get("track", 0)); a = max(0, x["f"] - 90); n = min(150, len(P[key]) - a); name = f"s{i:02d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a / 60:.4f}", "-i", str(Wd / x["video"] / "proxy.mp4"), "-frames:v", str(n), "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-g", "10", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(D / "clips" / name)], check=True)
    seg = P[key][a:a + n][:, KEEP]
    frames = [None if np.isnan(fr[0, 0]) else [[round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 2)] for p in fr] for fr in seg]
    world = [None if np.isnan(fr[0, 0]) else [[round(float(c), 3) for c in p] for p in fr] for fr in WP[key][a:a + n][:, KEEP]] if key in WP else None
    t = x["t"]
    out.append(dict(id=i, kind=x["kind"], t=t, video=x["vn"], clock=f"{x['vn']}·{int(t // 60)}:{t % 60:04.1f}", src=f"clips/{name}", contact=x["f"] - a,
                    knee=x["knee"], knee3d=x.get("knee3d"), knee_warn=x.get("knee_warn"), knee_warn_why=x.get("knee_warn_why"), cam_az=x.get("cam_az"), open_min=x["open_min"], open_contact=x["open_contact"], contact_h=x["contact_h"], contact_fwd=x.get("contact_fwd"), prep=x.get("prep"), prep_trunc=x.get("prep_trunc"), elbow=x["elbow"], vis=x["vis"],
                    drill=x["drill"], player=x.get("player") or "me", track=x.get("track", 0), **{k: x[k] for k in ("hand", "hand_guess", "backhand") if k in x}, size=x.get("size", PORTRAIT), frames=frames, **({"world": world} if world else {})))
save(D / "strokes_raw.json", out, compact=True)
for x in out: print(x["id"] + 1, x["kind"], x["drill"], x["clock"], x["knee"], None if x["contact_h"] is None else round(x["contact_h"] * 100))
print(len(out), "clips ->", D)
