# export_session.py <session> — one 150-frame clip per stroke (contact at frame 90) plus trimmed pose
# -> web/sessions/<s>/clips/sNN.mp4 and web/sessions/<s>/strokes_raw.json. Stroke numbers here are what refine.json refers to.
import subprocess, numpy as np
from common import session, work, web, load, save, KEEP, PORTRAIT

s = session(); Wd = work(s); D = web(s); (D / "clips").mkdir(parents=True, exist_ok=True)
r = load(Wd / "strokes_all.json")
P = {v: np.load(Wd / v / "pose.npy") for v in {x["video"] for x in r}}
for old in (D / "clips").glob("s*.mp4"): old.unlink()
out = []
for i, x in enumerate(r):
    a = x["f"] - 90; name = f"s{i:02d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a / 60:.4f}", "-i", str(Wd / x["video"] / "proxy.mp4"), "-frames:v", "150", "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-g", "10", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(D / "clips" / name)], check=True)
    seg = P[x["video"]][a:a + 150][:, KEEP]
    frames = [None if np.isnan(fr[0, 0]) else [[round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 2)] for p in fr] for fr in seg]
    t = x["t"]
    out.append(dict(id=i, kind=x["kind"], t=t, video=x["vn"], clock=f"{x['vn']}·{int(t // 60)}:{t % 60:04.1f}", src=f"clips/{name}", contact=90,
                    knee=x["knee"], open_min=x["open_min"], open_contact=x["open_contact"], contact_h=x["contact_h"], elbow=x["elbow"], vis=x["vis"],
                    drill=x["drill"], size=x.get("size", PORTRAIT), frames=frames))
save(D / "strokes_raw.json", out, compact=True)
for x in out: print(x["id"] + 1, x["kind"], x["drill"], x["clock"], x["knee"], round(x["contact_h"] * 100))
print(len(out), "clips ->", D)
