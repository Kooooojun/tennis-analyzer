# E2E for tools/prep.py on a synthetic clip (tests/make_synth.py; no user footage), with the real pose and ball models.
# Builds a throwaway repo root (tools/ copied, models/ hard-linked, a fresh .venv that sees this interpreter's packages) so
# the run also goes through prep.py's "not the venv: re-run under it" path. Needs models/ (python setup.py) and ffmpeg.
# Checks: outputs complete, second run does no work (mtimes unchanged), people count changes, exit codes pass through.
import os, shutil, site, subprocess, sys, tempfile, venv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parent.parent
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
subprocess.run([sys.executable, str(REPO / "tests" / "make_synth.py"), str(tmp / "syn"), "1", "960x540"], check=True)
V = R / "videos" / "synth"; V.mkdir(parents=True)
shutil.copy(tmp / "syn" / "land.mp4", V / "b.mp4"); shutil.copy(tmp / "syn" / "port.mp4", V / "A.MOV")
old = 1_600_000_000
for v in V.iterdir(): os.utime(v, (old, old))  # inputs clearly older than outputs: no reliance on mtime resolution or sleep


def prep(*a):
    r = subprocess.run([sys.executable, str(R / "tools" / "prep.py"), *a], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout, r.stderr, sep="")
    return r


W = R / "work" / "synth"
r = prep("synth", "2"); assert r.returncode == 0
assert r.stdout.splitlines()[-1] == "ready: 2 videos -> work/synth", r.stdout
assert (W / "videos.json").read_text(encoding="utf-8") == '["A", "b"]\n'  # case-insensitive name order
want = {"proxy.mp4", "audio.f32", "audio_hp.f32", "pose.npy", "pose_world.npy", "people.txt", "sounds.npy", "ball.npy", "events.npy", "src_fps.txt", "pose.log", "ball.log"}
for d in ("A", "b"):
    got = {p.name for p in (W / d).iterdir()}
    assert got == want, (d, got ^ want)
    assert (W / d / "people.txt").read_bytes() == b"2\n"
import cv2
c = cv2.VideoCapture(str(W / "A" / "proxy.mp4")); assert (c.get(3), c.get(4)) == (540, 960), "portrait proxy"
c = cv2.VideoCapture(str(W / "b" / "proxy.mp4")); assert (c.get(3), c.get(4)) == (960, 540)
del c

ALWAYS = {"people.txt", "src_fps.txt"}  # rewritten every run by design
mt = lambda: {p: p.stat().st_mtime_ns for p in W.rglob("*") if p.is_file() and p.name not in ALWAYS and p.name != "videos.json"}
before = mt()
assert prep("synth", "2").returncode == 0
assert mt() == before, "second run must do no work"

# people 2 -> 3: pose.npy is deleted and pose re-runs
pose = W / "b" / "pose.npy"; t = pose.stat().st_mtime_ns
assert prep("synth", "3").returncode == 0
assert pose.stat().st_mtime_ns != t and (W / "b" / "people.txt").read_bytes() == b"3\n"
# extra tracks from a larger run: people.txt already says 2, so pose.npy stays; prep itself drops tracks k >= 2
import numpy as np
for k in (1, 2): np.save(W / "b" / f"pose_t{k}.npy", np.zeros(1)); np.save(W / "b" / f"pose_world_t{k}.npy", np.zeros(1))
(W / "b" / "people.txt").write_bytes(b"2\n"); os.utime(W / "b" / "people.txt")
t = pose.stat().st_mtime_ns
assert prep("synth", "2").returncode == 0
names = {p.name for p in (W / "b").glob("pose*_t*.npy")}
assert names == {"pose_t1.npy", "pose_world_t1.npy"}, names  # k >= 2 deleted by prep, k = 1 kept, pose.npy not re-run
assert pose.stat().st_mtime_ns == t

# a failing step stops prep with that step's exit code, through the re-run-under-venv hop too
(R / "tools" / "hits.py").write_text("import sys; sys.exit(7)\n", encoding="utf-8")
(W / "b" / "sounds.npy").unlink()
assert prep("synth", "2").returncode == 7
(R / "tools" / "seven.py").write_text("import sys; sys.exit(7)\n", encoding="utf-8")
assert subprocess.run([sys.executable, str(R / "tools" / "run.py"), "seven.py"]).returncode == 7

# argument checks
for bad in (["../x"], ["synth", "0"], ["synth", "two"], ["nope"], []):
    assert prep(*bad).returncode == 1, bad
(V / "b.m4v").write_bytes(b""); r = prep("synth"); assert r.returncode == 1 and "same name" in r.stderr, r.stderr
shutil.rmtree(tmp, ignore_errors=True)
print("ok test_prep_e2e")
