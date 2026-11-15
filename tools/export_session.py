# export_session.py <session> — one 150-frame clip per stroke (contact at frame 90) plus trimmed pose
# -> web/sessions/<s>/clips/sNN.mp4 and web/sessions/<s>/strokes_raw.json. Stroke numbers here are what refine.json refers to.
import subprocess, numpy as np
from common import session, work, web, load, save, KEEP, PORTRAIT, track_file

s = session(); Wd = work(s); D = web(s); (D / "clips").mkdir(parents=True, exist_ok=True)
r = load(Wd / "strokes_all.json")
P = {key: np.load(track_file(Wd / key[0], "pose", key[1])) for key in {(x["video"], x.get("track", 0)) for x in r}}
WP = {key: track_file(Wd / key[0], "pose_world", key[1]) for key in P}; WP = {key: np.load(p) for key, p in WP.items() if p.exists()}
for old in (D / "clips").glob("s*.mp4"): old.unlink()
out = []
for i, x in enumerate(r):
    a = x["f"] - 90; name = f"s{i:02d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a / 60:.4f}", "-i", str(Wd / x["video"] / "proxy.mp4"), "-frames:v", "150", "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-g", "10", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(D / "clips" / name)], check=True)
    key = (x["video"], x.get("track", 0)); seg = P[key][a:a + 150][:, KEEP]
    frames = [None if np.isnan(fr[0, 0]) else [[round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 2)] for p in fr] for fr in seg]
    world = [None if np.isnan(fr[0, 0]) else [[round(float(c), 3) for c in p] for p in fr] for fr in WP[key][a:a + 150][:, KEEP]] if key in WP else None
    t = x["t"]
    out.append(dict(id=i, kind=x["kind"], t=t, video=x["vn"], clock=f"{x['vn']}·{int(t // 60)}:{t % 60:04.1f}", src=f"clips/{name}", contact=90,
                    knee=x["knee"], knee3d=x.get("knee3d"), knee_warn=x.get("knee_warn"), open_min=x["open_min"], open_contact=x["open_contact"], contact_h=x["contact_h"], contact_fwd=x.get("contact_fwd"), prep=x.get("prep"), elbow=x["elbow"], vis=x["vis"],
                    drill=x["drill"], player=x.get("player") or "me", track=x.get("track", 0), **{k: x[k] for k in ("hand", "hand_guess", "backhand") if k in x}, size=x.get("size", PORTRAIT), frames=frames, **({"world": world} if world else {})))
save(D / "strokes_raw.json", out, compact=True)
for x in out: print(x["id"] + 1, x["kind"], x["drill"], x["clock"], x["knee"], None if x["contact_h"] is None else round(x["contact_h"] * 100))
print(len(out), "clips ->", D)
