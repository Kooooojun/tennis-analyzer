# E2E for tools/prep.py on a synthetic clip (tests/make_synth.py; no user footage), with the real pose and ball models.
# Builds a throwaway repo root (tools/ copied, models/ hard-linked, a fresh .venv that sees this interpreter's packages) so
# the run also goes through prep.py's "not the venv: re-run under it" path. Needs models/ (python setup.py) and ffmpeg.
# Checks: outputs complete, second run does no work (mtimes unchanged), people count changes, exit codes pass through.
import os, shutil, site, subprocess, sys, tempfile, venv
from pathlib import Path
import contextlib, hashlib, io, json
from unittest.mock import patch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import prep as prep_module
from proxy import video_filter

# Inspect real prep command construction without running models; rotation is already applied by probe().
with tempfile.TemporaryDirectory() as d:
    root = Path(d); (root / "videos" / "ratios").mkdir(parents=True)
    (root / "videos" / "ratios" / "clip.mp4").touch()
    for wh, warned in (((1920, 1080), False), ((1080, 1920), False), ((1088, 1920), False), ((720, 1280), False),
                       ((1904, 1080), False), ((1760, 1000), False), ((1616, 900), False), ((891, 1600), False), ((909, 1600), False),
                       ((1888, 1080), True), ((640, 480), True), ((480, 640), True)):
        calls = []; err = io.StringIO()
        with patch.object(prep_module, "R", root), patch.object(prep_module, "need_ffmpeg"), \
             patch.object(prep_module, "probe", return_value=(*wh, 60)), patch.object(prep_module, "h264_args", return_value=[]), \
             patch.object(prep_module, "stale", side_effect=lambda p, *a: p.name == "proxy.mp4"), \
             patch.object(prep_module, "ffmpeg", side_effect=lambda *a: calls.append(a)), contextlib.redirect_stderr(err):
            prep_module.main(["ratios", "1"])
        assert ("來源比例" in err.getvalue()) == warned, (wh, err.getvalue())
        pw, ph = (960, 540) if wh[0] > wh[1] else (540, 960)
        filt = f"scale={pw}:{ph}" if wh[0] * ph == wh[1] * pw else video_filter(*wh)
        assert calls[0][2:] == ("-an", "-vf", f"{filt},fps=60", "-g", "30", "-f", "mp4"), calls

def audio_commands(streams):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); (root / "videos" / "audio").mkdir(parents=True)
        (root / "videos" / "audio" / "clip.mp4").touch()
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps({"streams": streams, "format": {"duration": "1.25"}}), stderr="")
        calls = []; err = io.StringIO()
        with patch.object(prep_module, "R", root), patch.object(prep_module, "need_ffmpeg"), \
             patch.object(prep_module, "probe", return_value=(1920, 1080, 60)), patch.object(prep_module, "h264_args", return_value=[]), \
             patch.object(prep_module, "stale", side_effect=lambda p, *a: p.name in ("audio.f32", "audio_hp.f32")), \
             patch.object(prep_module.subprocess, "run", return_value=result), \
             patch.object(prep_module, "ffmpeg", side_effect=lambda *a: calls.append(a)), contextlib.redirect_stderr(err):
            prep_module.main(["audio", "1"])
        return calls, err.getvalue()


def test_empty_audio():
    for value in ("0", "-1", "N/A", None):
        calls, err = audio_commands([{"codec_type": "video", "duration": "1.25"}, {"codec_type": "audio", "duration": value}])
        silent = value in ("0", "-1")
        assert ("這支影片沒有聲音" in err) == silent, (value, err)
        assert len(calls) == 2 and all(("anullsrc=r=16000:cl=mono" in c) == silent for c in calls), calls


def test_duration_fallback():
    for value in ("N/A", None, "0", "nan"):
        calls, err = audio_commands([{"codec_type": "video", "duration": value}])
        assert "這支影片沒有聲音" in err and len(calls) == 2, (value, err)
        assert all(c[c.index("-t") + 1] == "1.25" for c in calls), calls


test_empty_audio()
test_duration_fallback()

tmp = Path(tempfile.mkdtemp(prefix="prep_e2e_")); R = tmp / "repo"
shutil.copytree(REPO / "tools", R / "tools", ignore=shutil.ignore_patterns("__pycache__"))
(R / "models").mkdir(parents=True)
for m in ("pose_heavy.task", "balltrack_best.pth"):
    try: os.link(REPO / "models" / m, R / "models" / m)
    except OSError: shutil.copy(REPO / "models" / m, R / "models" / m)
venv.create(R / ".venv", with_pip=False)
sys.path.insert(0, str(REPO / "tools")); from platform_util import venv_python
pyv = venv_python(R)
sp = subprocess.run([str(pyv), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], capture_output=True, text=True, check=True).stdout.strip()
Path(sp, "parent_env.pth").write_text("\n".join(site.getsitepackages() + [site.getusersitepackages()]) + "\n", encoding="utf-8")
subprocess.run([sys.executable, str(REPO / "tests" / "make_synth.py"), str(tmp / "syn"), "0.4", "960x540"], check=True)
# Prep can have no first-pass candidates; exercise real windowed inference explicitly too.
import numpy as np
np.save(tmp / "windows.npy", np.array([[0, 1]], dtype=np.int64))
subprocess.run([str(pyv), str(R / "tools" / "ball.py"), str(tmp / "syn" / "land.mp4"), str(tmp / "real-ball.npy"),
                "--windows", str(tmp / "windows.npy")], check=True)
real_ball = np.load(tmp / "real-ball.npy")
assert real_ball.shape == (24, 3) and real_ball.dtype == np.float32
assert np.isnan(real_ball[1:]).all()
V = R / "videos" / "synth"; V.mkdir(parents=True)
shutil.copy(tmp / "syn" / "land.mp4", V / "b.mp4"); shutil.copy(tmp / "syn" / "port.mp4", V / "A x.MOV")
old = 1_600_000_000
for v in V.iterdir(): os.utime(v, (old, old))  # inputs clearly older than outputs: no reliance on mtime resolution or sleep


def prep(*a):
    r = subprocess.run([sys.executable, str(R / "tools" / "prep.py"), *a], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout, r.stderr, sep="")
    return r


W = R / "work" / "synth"
r = prep("synth", "2"); assert r.returncode == 0
assert "來源比例" not in r.stderr and "沒有 3D 姿態" not in r.stderr and "舊 work" not in r.stderr
assert r.stdout.splitlines()[-1] == "ready: 2 videos -> work/synth", r.stdout
assert (W / "videos.json").read_text(encoding="utf-8") == '["A x", "b"]\n'  # case-insensitive name order; a space stays inside one name
want = {"proxy.mp4", "audio.f32", "audio_hp.f32", "pose.npy", "pose_world.npy", "people.txt", "sounds.npy", "ball.npy", "events.npy", "src_fps.txt", "pose_method.txt", "pose.log", "ball.log"}
for d in ("A x", "b"):
    got = {p.name for p in (W / d).iterdir()}
    assert got == want, (d, got ^ want)
    assert (W / d / "people.txt").read_bytes() == b"2\n"
import cv2, numpy as np
for d in ("A x", "b"):
    assert np.load(W / d / "sounds.npy").shape == (1, 4), d
    assert np.load(W / d / "events.npy").shape == (0, 3), d
c = cv2.VideoCapture(str(W / "A x" / "proxy.mp4")); assert (c.get(3), c.get(4)) == (540, 960), "portrait proxy"
c = cv2.VideoCapture(str(W / "b" / "proxy.mp4")); assert (c.get(3), c.get(4)) == (960, 540)
del c

# 硬體編碼的私有 SEI 可能隨時間改變；正式 proxy 全格解碼相同，libx264 合成片整檔相同。
for name, src, pw, ph in (("b", V / "b.mp4", 960, 540), ("A x", V / "A x.MOV", 540, 960)):
    baseline = tmp / "baseline.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", f"scale={pw}:{ph},fps=60",
                    *prep_module.h264_args("2500k", 23), "-g", "30", "-f", "mp4", str(baseline)], check=True)
    md5 = lambda p: subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(p), "-f", "framemd5", "-"])
    before, after = md5(baseline), md5(W / name / "proxy.mp4")
    assert before == after, "16:9 proxy 全部影格必須與 main 逐位元相同"
    print("16:9 framemd5 sha256", hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())
    for mode, filt in (("main", f"scale={pw}:{ph}"), ("branch", video_filter(pw, ph))):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", filt + ",fps=60",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-g", "30", "-f", "mp4", str(tmp / f"{mode}.mp4")], check=True)
    assert (tmp / "main.mp4").read_bytes() == (tmp / "branch.mp4").read_bytes(), "libx264 16:9 合成片整檔相同"

ALWAYS = {"people.txt", "src_fps.txt", "pose_method.txt"}  # rewritten every run by design
mt = lambda: {p: p.stat().st_mtime_ns for p in W.rglob("*") if p.is_file() and p.name not in ALWAYS and p.name != "videos.json"}
before = mt()
assert prep("synth", "2").returncode == 0
assert mt() == before, "second run must do no work"

# Missing legacy metadata never invalidates a current-method pose, and warnings appear only once.
pose = W / "b" / "pose.npy"; t = pose.stat().st_mtime_ns; data = pose.read_bytes()
(W / "b" / "people.txt").unlink()
r = prep("synth", "2")
assert r.returncode == 0 and r.stderr.count("舊 work 目錄沒有人數紀錄") == 1, r.stderr
assert pose.stat().st_mtime_ns == t and pose.read_bytes() == data
assert "舊 work" not in prep("synth", "2").stderr
world = W / "b" / "pose_world.npy"; saved_world = world.read_bytes(); world.unlink()
r = prep("synth", "2")
assert r.returncode == 0 and r.stderr.count("沒有 3D 姿態") == 1, r.stderr
assert pose.stat().st_mtime_ns == t and pose.read_bytes() == data
assert "沒有 3D 姿態" not in prep("synth", "2").stderr
world.write_bytes(saved_world)
assert prep("synth", "2").returncode == 0
assert not (W / "b" / "pose_world_missing.txt").exists()

# pose from an older algorithm (other version, or no pose_method.txt as before versions existed) is redone, once;
# even when people.txt and pose_world.npy are also missing, pose re-runs first without stale-work or missing-3D warnings.
pose = W / "b" / "pose.npy"
for stale_method in ("1\n", None):
    pm = W / "b" / "pose_method.txt"
    if stale_method: pm.write_text(stale_method, encoding="utf-8")
    else: pm.unlink()
    (W / "b" / "people.txt").unlink(missing_ok=True)
    (W / "b" / "pose_world.npy").unlink(missing_ok=True)
    t = pose.stat().st_mtime_ns
    r = prep("synth", "2")
    assert r.returncode == 0 and pose.stat().st_mtime_ns != t and "重算" in r.stdout, stale_method
    assert "沒有 3D 姿態" not in r.stderr and "舊 work" not in r.stderr, r.stderr
    assert (W / "b" / "pose_world.npy").is_file() and (W / "b" / "people.txt").read_bytes() == b"2\n"
    t = pose.stat().st_mtime_ns
    assert prep("synth", "2").returncode == 0 and pose.stat().st_mtime_ns == t

# people 2 -> 3: pose.npy is deleted and pose re-runs
pose = W / "b" / "pose.npy"; t = pose.stat().st_mtime_ns
assert prep("synth", "3").returncode == 0
assert pose.stat().st_mtime_ns != t and (W / "b" / "people.txt").read_bytes() == b"3\n"
# extra tracks from a larger run: people.txt already says 2, so pose.npy stays; prep itself drops tracks k >= 2
import numpy as np
for k in (1, 2): np.save(W / "b" / f"pose_t{k}.npy", np.load(pose)); np.save(W / "b" / f"pose_world_t{k}.npy", np.zeros(1))
(W / "b" / "people.txt").write_bytes(b"2\n"); os.utime(W / "b" / "people.txt")
t = pose.stat().st_mtime_ns
assert prep("synth", "2").returncode == 0
names = {p.name for p in (W / "b").glob("pose*_t*.npy")}
assert names == {"pose_t1.npy", "pose_world_t1.npy"}, names  # k >= 2 deleted by prep, k = 1 kept, pose.npy not re-run
assert pose.stat().st_mtime_ns == t

# A missing world for any existing secondary track is reported once too.
(W / "b" / "pose_world_t1.npy").unlink()
r = prep("synth", "2")
assert r.returncode == 0 and r.stderr.count("沒有 3D 姿態") == 1, r.stderr
assert pose.stat().st_mtime_ns == t
assert "沒有 3D 姿態" not in prep("synth", "2").stderr

# Real ffmpeg, pose, hits and events on a silent 4:3 clip; no fake audio/model outputs.
silent = R / "videos" / "silent"; silent.mkdir()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=640x480:r=60:d=0.4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent / "clip.mp4")], check=True)
os.utime(silent / "clip.mp4", (old, old))
r = prep("silent", "1")
assert r.returncode == 0 and r.stderr.count("這支影片沒有聲音：擊球偵測要靠聲音，這支可能抓不到任何擊球") == 1, r.stderr
assert "來源比例 4:3" in r.stderr
D = R / "work" / "silent" / "clip"
cap = cv2.VideoCapture(str(D / "proxy.mp4")); ok, frame = cap.read(); cap.release()
assert ok and frame.shape[:2] == (540, 960)
# H.264 去塊濾波會讓邊界少量溢色；核對黑邊內部，並另外確認內容邊界。
assert frame[:, :104].max() < 4 and frame[:, 856:].max() < 4, "4:3 的左右黑邊"
content_x = np.flatnonzero(frame.max(axis=(0, 2)) > 128)
assert (content_x[0], content_x[-1]) == (120, 839), "4:3 內容須位於中央 720 px"
assert frame[:, 122:838].mean() > 50, "原片內容等比例縮到 720×540"
assert (D / "proxy_filter.txt").read_text(encoding="utf-8").strip() == "scale=720:540,setsar=1,pad=960:540:120:0:black"
for name in ("audio.f32", "audio_hp.f32"):
    audio = np.fromfile(D / name, dtype=np.float32)
    assert len(audio) == 6400 and not audio.any(), (name, audio.shape)
assert np.load(D / "sounds.npy").shape == (0, 4) and np.load(D / "events.npy").shape == (0, 3)
assert np.load(D / "ball.npy").shape == (24, 3) and np.isnan(np.load(D / "ball.npy")).all()
assert not list(D.glob("*.part"))
before = {p: p.stat().st_mtime_ns for p in D.iterdir() if p.name not in ALWAYS}
assert prep("silent", "1").returncode == 0
assert before == {p: p.stat().st_mtime_ns for p in D.iterdir() if p.name not in ALWAYS}

# 舊非 16:9 proxy 沒版本記錄時，重建後連帶重算姿態與事件；16:9 不需版本檔。
assert not (W / "b" / "proxy_filter.txt").exists()
before = {p: (D / p).stat().st_mtime_ns for p in ("proxy.mp4", "pose.npy", "ball.npy", "events.npy")}
(D / "proxy_filter.txt").unlink()
assert prep("silent", "1").returncode == 0
assert all((D / p).stat().st_mtime_ns != t for p, t in before.items())

# Candidate CLI reports once per video even with two tracks and both wrists, never for empty events.
np.save(D / "pose_t1.npy", np.load(D / "pose.npy"))
(D.parent / "players.txt").write_text("1 0 alpha\n1 1 beta\n", encoding="utf-8")
def candidates(e):
    np.save(D / "events.npy", e)
    return subprocess.run([str(pyv), str(R / "tools" / "candidates.py"), "silent"], capture_output=True, text=True, encoding="utf-8")
r = candidates(np.array([[0.1, -20, 12], [0.3, -20, 12]]))
assert r.returncode == 0 and r.stderr.count("2 個擊球沒算") == 1, (r.stdout, r.stderr)
assert "影片太短" in r.stderr
cands = (D.parent / "cands.json").read_bytes()
r = candidates(np.zeros((0, 3)))
assert r.returncode == 0 and "擊球沒算" not in r.stderr, r.stderr
assert (D.parent / "cands.json").read_bytes() == cands

# Non-empty cands.json on a synthetic 3s clip with a real-looking swing: adding head/tail events warns once and leaves cands.json byte-identical.
subprocess.run([sys.executable, str(REPO / "tests" / "make_synth.py"), str(tmp / "syn3"), "3", "960x540"], check=True)
HV = R / "videos" / "hit_edge"; HV.mkdir()
HW = R / "work" / "hit_edge"; HC = HW / "clip"; HC.mkdir(parents=True)
shutil.copy(tmp / "syn3" / "land.mp4", HV / "clip.mp4")
shutil.copy(tmp / "syn3" / "land.mp4", HC / "proxy.mp4")
(HW / "videos.json").write_text('["clip"]\n', encoding="utf-8")
P3 = np.full((180, 33, 3), np.nan, dtype=np.float32)
P3[:, 0] = [0.5, 0.2, 1.0]
P3[:, [11, 12]] = [[0.45, 0.35, 1.0], [0.55, 0.35, 1.0]]
P3[:, [23, 24]] = [[0.45, 0.55, 1.0], [0.55, 0.55, 1.0]]
P3[:, [27, 28]] = [[0.45, 0.85, 1.0], [0.55, 0.85, 1.0]]
P3[:, 15] = [0.40, 0.45, 1.0]
P3[:, 16] = [0.60, 0.45, 1.0]
for f in range(75, 106):
    P3[f, 16, 0] = 0.35 + (f - 75) * 0.02
def hit_candidates(e):
    np.save(HC / "pose.npy", P3)
    np.save(HC / "events.npy", e)
    return subprocess.run([str(pyv), str(R / "tools" / "candidates.py"), "hit_edge"], capture_output=True, text=True, encoding="utf-8")
r = hit_candidates(np.array([[1.5, -20, 12]]))
assert r.returncode == 0 and "擊球沒算" not in r.stderr, (r.stdout, r.stderr)
cands_hit = (HW / "cands.json").read_bytes()
assert len(json.loads(cands_hit)) == 1, cands_hit
r = hit_candidates(np.array([[0.1, -20, 12], [1.5, -20, 12], [2.9, -20, 12]]))
assert r.returncode == 0 and r.stderr.count("2 個擊球沒算") == 1, (r.stdout, r.stderr)
assert (HW / "cands.json").read_bytes() == cands_hit

# a failing step stops prep with that step's exit code, through the re-run-under-venv hop too
(R / "tools" / "hits.py").write_text("import sys; sys.exit(7)\n", encoding="utf-8")
(W / "b" / "sounds.npy").unlink()
assert prep("synth", "2").returncode == 7
(R / "tools" / "seven.py").write_text("import sys; sys.exit(7)\n", encoding="utf-8")
assert subprocess.run([sys.executable, str(R / "tools" / "run.py"), "seven.py"]).returncode == 7

# argument checks
for bad in (["."], ["../x"], ["synth", "0"], ["synth", "two"], ["nope"], []):
    assert prep(*bad).returncode == 1, bad
E = R / "videos" / "empty"; E.mkdir()
r = prep("empty"); assert r.returncode == 1 and "no videos" in r.stderr, r.stderr
B = R / "videos" / "bad"; B.mkdir(); shutil.copy(V / "b.mp4", B / "a.mp4"); (B / "z.mp4").write_text("not a video", encoding="utf-8")
r = prep("bad"); assert r.returncode == 1 and "ffprobe could not read" in r.stderr, r.stderr
assert not (R / "work" / "bad").exists(), "a bad video must stop prep before any work"
(V / "b.m4v").write_bytes(b""); r = prep("synth"); assert r.returncode == 1 and "same name" in r.stderr, r.stderr
shutil.rmtree(tmp, ignore_errors=True)
print("ok test_prep_e2e")
