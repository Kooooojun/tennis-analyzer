# One-time setup: python setup.py [--cuda]   (macOS/Linux also: ./setup.sh)
# Python venv with MediaPipe + OpenCV + PyTorch, the pose model (~30 MB) and the ball-tracking model (~47 MB).
# Needs Python 3.11 or 3.12 (numpy/pillow/torch pins require >= 3.11; 3.13 is untested). When started by another Python, it
# finds 3.12/3.11 and re-runs itself with it, so this top part only uses syntax old Pythons understand.
# --cuda (or nvidia-smi found) on Windows: torch from the PyTorch CUDA index, since the PyPI Windows wheel is CPU only.
import hashlib, os, shutil, subprocess, sys
from pathlib import Path

R = Path(__file__).resolve().parent
OK = ((3, 11), (3, 12))
TORCH_CUDA = "https://download.pytorch.org/whl/cu132"  # torch 2.15.0 is published there as +cu132 (and +cu134), checked 2026-11-15
MODELS = {  # sha256 of the files downloaded on 2026-11-15
    "pose_heavy.task": ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
                        "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b"),
    # RacketVision BallTrack. The HF model page declares no license; the GitHub repo that links it is MIT (third_party/RacketVision-LICENSE).
    "balltrack_best.pth": ("https://huggingface.co/linfeng302/RacketVision-Models/resolve/main/checkpoints/balltrack_best.pth",
                           "00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342"),
}


def version(cmd):
    """(major, minor) of a Python command, or None when it does not run (missing, or the Windows Store stub)."""
    try:
        r = subprocess.run(cmd + ["-c", "import sys; print('%d %d' % sys.version_info[:2])"], capture_output=True, text=True, timeout=30)
        return tuple(int(x) for x in r.stdout.split()) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def find_python():
    cands = [["py", "-3.12"], ["py", "-3.11"]] if os.name == "nt" else [["python3.12"], ["python3.11"]]
    for c in cands:
        if version(c) in OK: return c
    return None


def sh(*cmd):
    if subprocess.run([str(c) for c in cmd]).returncode: sys.exit("failed: " + " ".join(map(str, cmd)))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def download(name, url, want):
    out = R / "models" / name
    if not out.is_file():
        part = out.with_name(name + ".part")  # an interrupted download never looks finished
        print("downloading", name, flush=True)
        sh("curl", "-fL", "-o", part, url)
        os.replace(part, out)
    if sha256(out) != want: sys.exit(f"{name} checksum mismatch: delete models/{name} and re-run")  # also catches an old broken file


def main(args):
    sys.path.insert(0, str(R / "tools"))
    from platform_util import need_ffmpeg, utf8_stdout, venv_python
    utf8_stdout()
    need_ffmpeg()
    if not shutil.which("curl"): sys.exit("need curl (Windows 10/11 ship it; Linux: apt install curl)")
    py = venv_python(R)
    if (R / ".venv").exists():
        if version([str(py)]) not in OK:
            sys.exit(f".venv is broken or not Python 3.11/3.12 ({py}). Delete the .venv folder yourself and re-run python setup.py")
    else:
        sh(sys.executable, "-m", "venv", R / ".venv")
    sh(py, "-m", "pip", "install", "-q", "--upgrade", "pip")
    sh(py, "-m", "pip", "install", "-q", "-r", R / "requirements.txt")
    if os.name == "nt" and ("--cuda" in args or shutil.which("nvidia-smi")):
        print("NVIDIA GPU: installing CUDA torch from", TORCH_CUDA, flush=True)
        sh(py, "-m", "pip", "install", "-q", "--force-reinstall", "--no-deps", "torch==2.15.0", "--index-url", TORCH_CUDA)
    for d in ("models", "videos", "work", "web/sessions"): (R / d).mkdir(parents=True, exist_ok=True)
    for name, (url, want) in MODELS.items(): download(name, url, want)
    r = subprocess.run([str(py), "-c", "import mediapipe, cv2, PIL, numpy, torch; d = 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'; "
                        "print('ok: mediapipe', mediapipe.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'device', d)"])
    if r.returncode:
        sys.exit("import failed" + ("; mediapipe on Windows may need: winget install Microsoft.VCRedist.2015+.x64" if os.name == "nt" else ""))
    print("venv python:", py)
    print("run scripts with: python tools/run.py <script> ...   e.g. python tools/run.py prep.py <session>")


if __name__ == "__main__":
    if sys.version_info[:2] not in OK:
        c = find_python()
        if not c:
            sys.exit("need Python 3.11 or 3.12. Windows: winget install Python.Python.3.12 (or python.org), then open a new terminal; "
                     "macOS: brew install python@3.12")
        # subprocess, not os.exec*: on Windows exec returns to the caller before the child finishes
        sys.exit(subprocess.run(c + [__file__] + sys.argv[1:]).returncode)
    main(sys.argv[1:])
