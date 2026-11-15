# usage: python tools/run.py <script> [args...]   runs tools/<script> (or a path) with the venv's Python, from any Python
#        python tools/run.py open <file>         opens a file (e.g. web/index.html) in the default browser
# Docs use this so nobody has to know where the venv's Python lives (.venv/bin/python or .venv\Scripts\python.exe).
import subprocess, sys, webbrowser
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "tools"))
from platform_util import venv_python

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit("usage: python tools/run.py <script> [args...] | open <file>")
    if a[0] == "open":
        if len(a) != 2 or not Path(a[1]).exists(): sys.exit(f"usage: python tools/run.py open <file>  (file must exist)")
        sys.exit(0 if webbrowser.open(Path(a[1]).resolve().as_uri()) else 1)  # a file:// URL: a bare relative path is unreliable on Windows
    py = venv_python(R)
    if not py.is_file(): sys.exit("run python setup.py first")
    s = Path(a[0]) if Path(a[0]).is_file() else R / "tools" / a[0]
    if not s.is_file(): sys.exit(f"no such script: {a[0]}")
    # subprocess, not os.exec*: on Windows exec hands back to the caller before the script finishes
    sys.exit(subprocess.run([str(py), "-X", "utf8", str(s), *a[1:]]).returncode)
