"""執行：.venv/bin/python tests/test_export_refine.py
export_session.py → refine.py 的端到端測試：合成骨架、ffmpeg testsrc 當 proxy，在暫存根目錄真的跑兩支腳本。
pose_world 長度和 pose 不同（另一輪的 3D）時，export 要當沒有 3D，跟 measure_full 同一條規則：較長不可靜默錯位，較短不可 IndexError。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from metrics import measure_full
from platform_util import utf8_stdout

utf8_stdout()

S = "syn"; N = 480; FPS = 60; CONTACTS = [3.0, 6.0]; SIZE = [540, 960]


def nearest(f):
    return min((f - c * FPS for c in CONTACTS), key=abs)


def pose2d():
    """側身站姿，持拍腕在擊球前 40 格由後往前。"""
    P = np.full((N, 33, 3), np.nan); P[:, :, 2] = 1.0
    base = {0: (.50, .30), 11: (.48, .40), 12: (.52, .40), 13: (.50, .48), 14: (.50, .48), 15: (.48, .55), 16: (.52, .55),
            23: (.49, .60), 24: (.51, .60), 25: (.47, .74), 26: (.53, .74), 27: (.50, .88), 28: (.50, .88),
            29: (.49, .89), 30: (.51, .89), 31: (.47, .90), 32: (.53, .90)}
    for j, (x, y) in base.items(): P[:, j, 0] = x; P[:, j, 1] = y
    for f in range(N):
        d = nearest(f)
        x = .35 + (d + 40) / 40 * .30 if -40 <= d <= 0 else .65 - d / 20 * .1 if 0 < d <= 20 else .40
        P[f, 16, 0] = x; P[f, 16, 1] = .55 - (.05 if -5 <= d <= 5 else 0); P[f, 14, 0] = (x + .52) / 2
    return P


def world(facing):
    """facing 'side'（cam_az 90）或 'front'（cam_az 0）。公尺，x 右、y 下、z 遠離鏡頭。"""
    W = np.zeros((N, 33, 3))
    r = np.array([0, 0, .2]) if facing == "side" else np.array([-.2, 0, 0])  # 身體右半寬
    for j, p in {0: (0, -.6, 0), 13: (0, -.3, 0), 14: (0, -.3, 0), 15: (0, -.1, 0), 16: (0, -.1, 0),
                 29: (0, .9, 0), 30: (0, .9, 0), 31: (0, .9, 0), 32: (0, .9, 0)}.items(): W[:, j] = p
    W[:, 11] = np.array([0, -.5, 0]) - r; W[:, 12] = np.array([0, -.5, 0]) + r
    W[:, 23] = -r * .7; W[:, 24] = r * .7
    W[:, 25] = W[:, 23] + (.1, .4, 0); W[:, 26] = W[:, 24] + (.1, .4, 0)
    W[:, 27] = W[:, 23] + (0, .85, 0); W[:, 28] = W[:, 24] + (0, .85, 0)
    for f in range(N):
        d = nearest(f)
        if -40 <= d <= 0: W[f, 16] = (0, -.1, -.4 + (d + 40) / 40 * .8)
    return W


def run_case(pose_world):
    """回傳 (strokes_all 列, strokes_raw.json, refine 結果, strokes.json 或 None)。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        (root / "videos" / S).mkdir(parents=True)
        v = root / "work" / S / "v1"; v.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=136x240:rate={FPS}", "-frames:v", str(N),
                        "-pix_fmt", "yuv420p", str(v / "proxy.mp4")], check=True)
        P = pose2d(); np.save(v / "pose.npy", P)
        np.save(v / "pose_world.npy", pose_world)
        rows = [dict(t=t, video="v1", vn=1, track=0, player="me", size=SIZE, hand="R", hand_guess=False, kind="FH", drill="feed",
                     **measure_full(P, t, SIZE, pose_world, "R", CONTACTS[i - 1] if i else None))  # 同 assemble.py 的呼叫
                for i, t in enumerate(CONTACTS)]
        (root / "work" / S / "strokes_all.json").write_text(json.dumps(rows), encoding="utf-8")
        d = root / "web" / "sessions" / S
        run = lambda name: subprocess.run([sys.executable, str(root / "tools" / name), S], capture_output=True, text=True,
                                          encoding="utf-8", errors="replace", cwd=root)
        e = run("export_session.py"); assert e.returncode == 0, e.stderr
        raw = json.loads((d / "strokes_raw.json").read_text(encoding="utf-8"))
        r = run("refine.py")
        fin = json.loads((d / "strokes.json").read_text(encoding="utf-8")) if r.returncode == 0 else None
        return rows, raw, r, fin


side, front = world("side"), world("front")
fails = []


def check(name, cond, msg):
    print(("PASS" if cond else "FAIL"), name, "" if cond else msg)
    if not cond: fails.append(name)


# 同長：3D 照用，兩條路一致（側面 cam_az 90）
rows, raw, r, fin = run_case(side)
check("同長", r.returncode == 0 and all("world" in x for x in raw) and fin and
      all(s["knee3d"] is not None and s["cam_az"] == a["cam_az"] == 90 for s, a in zip(fin, rows)),
      (r.returncode, r.stderr[-300:], fin and [(s["knee3d"], s["cam_az"]) for s in fin]))

# 較長（前段是另一輪、面向鏡頭的 3D）：不可錯位用 3D，要跟 strokes_all（measure_full）一樣是 None
rows, raw, r, fin = run_case(np.concatenate([front, side]))
check("較長", r.returncode == 0 and not any("world" in x for x in raw) and fin and
      all(s[k] is None and a[k] is None for s, a in zip(fin, rows) for k in ("knee3d", "cam_az", "knee_warn")) and
      all(s["contact_fwd"] == a["contact_fwd"] is not None for s, a in zip(fin, rows)),
      (r.returncode, fin and [{k: s[k] for k in ("knee3d", "cam_az", "knee_warn", "contact_fwd")} for s in fin]))

# 較短（第 2 拍片段只蓋到 30／150 格）：refine 不可 IndexError，整條 track 走 2D
rows, raw, r, fin = run_case(side[:300])
check("較短", r.returncode == 0 and not any("world" in x for x in raw) and fin and
      all(s["knee3d"] is None and s["cam_az"] is None for s in fin),
      (r.returncode, r.stderr.strip().splitlines()[-1:] if r.stderr.strip() else "", [len(x.get("world") or []) for x in raw]))

assert not fails, fails
print("export→refine pose_world length tests ok")
