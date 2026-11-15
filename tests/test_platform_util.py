# Run: .venv/bin/python tests/test_platform_util.py   (plain asserts; cases follow testset/results/cross-platform_pred.md)
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import platform_util as pu

T = Path(tempfile.mkdtemp())

# read_text: BOM ok, UTF-16 / cp950 -> clear error naming the file
(T / "a.txt").write_bytes("﻿中文\n".encode("utf-8"))
assert pu.read_text(T / "a.txt") == "中文\n"
for enc in ("utf-16", "cp950"):
    (T / "b.txt").write_bytes("球員 白\n".encode(enc))
    try:
        pu.read_text(T / "b.txt"); raise AssertionError("no error")
    except SystemExit as e:
        assert "b.txt" in str(e) and "UTF-8" in str(e) and "Write" in str(e), e

# write_text: UTF-8, LF only
pu.write_text(T / "c.txt", "一\n二\n")
assert (T / "c.txt").read_bytes() == "一\n二\n".encode("utf-8")

# retry: transient PermissionError then success; permanent -> raises after 5 tries
calls = []
def flaky(n):
    def f():
        calls.append(1)
        if len(calls) <= n: raise PermissionError("locked")
        return "ok"
    return f
assert pu.retry(flaky(3), wait=0) == "ok" and len(calls) == 4
calls.clear()
try:
    pu.retry(flaky(99), wait=0); raise AssertionError("no raise")
except PermissionError:
    assert len(calls) == 5
(T / "d").write_text("x"); pu.replace(T / "d", T / "e"); assert (T / "e").read_text() == "x" and not (T / "d").exists()
pu.unlink(T / "e"); pu.unlink(T / "e"); assert not (T / "e").exists()  # missing file is fine

# stale: missing out; strictly newer input; equal mtime is fresh
o, i = T / "out", T / "in"
assert pu.stale(o, i)
o.write_text("o"); i.write_text("i")
os.utime(i, (1000, 1000)); os.utime(o, (1000, 1000)); assert not pu.stale(o, i)
os.utime(i, (1001, 1001)); assert pu.stale(o, i)
assert pu.stale(T, i)  # a directory is not a finished output

# venv_python per platform
r = Path("/r")
assert pu.venv_python(r) == (r / ".venv/Scripts/python.exe" if os.name == "nt" else r / ".venv/bin/python")

# encoder args: darwin -> videotoolbox; else nvenc only when it really encodes, otherwise libx264
a = pu.h264_args("2500k", 23)
if sys.platform == "darwin": assert a == ["-c:v", "h264_videotoolbox", "-b:v", "2500k"], a
else: assert a[1] in ("h264_nvenc", "libx264"), a
# imwrite: Chinese path (cv2.imwrite fails silently there on Windows) and a write that cannot succeed
import numpy as np
img = np.full((8, 8, 3), 200, np.uint8); q = T / "中文" / "圖.jpg"; q.parent.mkdir()
assert pu.imwrite(q, img, [1, 95]) and q.stat().st_size > 0
import cv2; back = cv2.imdecode(np.fromfile(q, np.uint8), cv2.IMREAD_COLOR); assert back.shape == img.shape and abs(int(back.mean()) - 200) < 3
assert pu.imwrite(T / "沒有這個資料夾" / "x.jpg", img) is False
print("ok")
