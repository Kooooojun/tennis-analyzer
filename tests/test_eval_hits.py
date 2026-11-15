"""Run: .venv/bin/python tests/test_eval_hits.py"""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from eval_hits import read_labels, score

assert score([1., 4.], [], [0., 1., 2., 3., 4., 5.], spans=[(1., 2.), (4., 4.)]) == ([(1., 1.), (4., 4.)], [], [2.])
assert score([1.], [], [1., 8.])[2] == [8.]
assert score([], [], [], spans=[(0., 1.)]) == ([], [], [])

with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp); label = d / "labels.csv"; events = d / "events.npy"
    def cli(text):
        label.write_text(text, encoding="utf-8-sig")
        return subprocess.run([sys.executable, "tools/eval_hits.py", str(label), str(events)], capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    np.save(events, [[1., 0., 0.], [4., 0., 0.], [8., 0., 0.]])
    header = "t_sec,player,kind\n"
    r = cli("# span 0 2\n" + header + "1,me,stroke\n# comment\n# span 4 4\n4,me,stroke\n")
    assert r.returncode == 0 and "TP 2 FN 0 FP 0" in r.stdout, (r.stdout, r.stderr)
    assert "整支影片都當作已標註" not in r.stderr
    assert "recall 100.00% precision 100.00%" in r.stdout, r.stdout
    rows, spans = read_labels(label)
    assert len(rows) == 2 and spans == [(0., 2.), (4., 4.)]
    r = cli(header + "1,me,stroke\n4,me,stroke\n")
    assert r.returncode == 0 and "FP 1" in r.stdout and "整支影片都當作已標註" in r.stderr
    for span in ("2 1", "-1 2", "nan 2", "0 inf", "0", "0 2 extra", "a 2"):
        r = cli("# span " + span + "\n" + header + "1,me,stroke\n")
        assert r.returncode != 0 and "Traceback" not in r.stderr, (span, r.stderr)
    r = cli("# span 0 0.5\n" + header + "1,me,stroke\n")
    assert r.returncode != 0 and "Traceback" not in r.stderr
    r = cli("# span 0 2\nt_sec,player\n1,me\n")
    assert read_labels(label)[0][0]["player"] == "me"  # legacy consumers do not need a kind column
    assert r.returncode != 0 and "Traceback" not in r.stderr
    r = cli("# span 0 2\nplayer,kind\nme,stroke\n")
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr
print("ok")
