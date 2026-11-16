"""執行：.venv/bin/python tests/test_prep_ball.py"""
import contextlib, io, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import prep
from pose_full import METHOD


class CacheTests(unittest.TestCase):
    def test_cpu_note_uses_selected_batches(self):
        err = io.StringIO()
        with patch.object(prep, "gpu", return_value=False), contextlib.redirect_stderr(err):
            prep.ball_note(960, 540, 160)
        self.assertIn("160 格預估 3 分鐘", err.getvalue())
        with patch.object(prep, "gpu") as gpu, contextlib.redirect_stderr(io.StringIO()) as err:
            prep.ball_note(960, 540, 0)
        gpu.assert_not_called(); self.assertEqual(err.getvalue(), "")

    def test_dependencies_and_legacy_superset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "videos" / "sample"; source.mkdir(parents=True)
            (source / "clip.mp4").touch()
            d = root / "work" / "sample" / "clip"; d.mkdir(parents=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x64:r=60:d=1",
                            "-c:v", "libx264", str(d / "proxy.mp4")], check=True)
            np.save(d / "sounds.npy", np.empty((0, 4)))
            np.save(d / "ball.npy", np.zeros((60, 3), np.float32))
            np.save(d / "events.npy", np.empty((0, 3)))
            for p in ("pose.npy", "pose_t1.npy", "pose_world.npy", "pose_world_t1.npy"):
                np.save(d / p, np.full((60, 33, 3), np.nan))
            for p, text in (("people.txt", "2\n"), ("pose_method.txt", METHOD), ("audio.f32", ""), ("audio_hp.f32", "")):
                (d / p).write_text(text, encoding="utf-8")
            old = 1_600_000_000
            os.utime(source / "clip.mp4", (old - 10, old - 10))
            for p in d.iterdir(): os.utime(p, (old, old))

            calls = []; expected_windows = []
            def py(script, *args, **kwargs):
                calls.append(script)
                if script == "ball.py":
                    self.assertIn("--windows", args)
                    windows = np.load(args[args.index("--windows") + 1])
                    self.assertEqual(windows.tolist(), expected_windows)
                    np.save(d / "ball.npy", np.full((60, 3), np.nan, np.float32))
                elif script == "events.py": np.save(d / "events.npy", np.empty((0, 3)))
                else: self.fail(script)

            with patch.object(prep, "R", root), patch.object(prep, "need_ffmpeg"), \
                 patch.object(prep, "probe", return_value=(1920, 1080, 60)), patch.object(prep, "h264_args", return_value=[]), \
                 patch.object(prep, "gpu", return_value=True), patch.object(prep, "py", side_effect=py), contextlib.redirect_stdout(io.StringIO()):
                # A full legacy track is a safe superset and needs no migration.
                original = (d / "ball.npy").read_bytes()
                prep.main(["sample", "2"])
                self.assertEqual(calls, [])
                self.assertEqual((d / "ball.npy").read_bytes(), original)
                for dependency in ("sounds.npy", "pose.npy", "pose_t1.npy"):
                    calls.clear()
                    os.utime(d / "ball.npy", (old, old)); os.utime(d / "events.npy", (old, old))
                    os.utime(d / dependency, (old + 1, old + 1))
                    prep.main(["sample", "2"])
                    self.assertEqual(calls, ["ball.py", "events.py"], dependency)
                    os.utime(d / dependency, (old, old))
                calls.clear(); prep.main(["sample", "2"])
                self.assertEqual(calls, [])
                self.assertFalse(list(d.glob("*.part")))
                # Only the secondary person swings; the main track is entirely unseen.
                p = np.zeros((60, 33, 3), np.float32); p[..., 2] = 1
                p[:, [11, 12], 1] = .4; p[:, [23, 24], 1] = .6
                p[:, [11, 23], 0] = .45; p[:, [12, 24], 0] = .55
                p[:, 15] = [.4, .6, 1]; p[:, 16] = [.6, .6, 1]
                p[:, 16, 0] += np.interp(np.arange(60), [0, 24, 34, 59], [0, 0, .3, .3])
                np.save(d / "pose_t1.npy", p)
                np.save(d / "sounds.npy", [[.5, -20, 12, 9]])
                expected_windows = [[1, 48]]
                prep.main(["sample", "2"])
                self.assertEqual(calls, ["ball.py", "events.py"])
                os.utime(d / "ball.npy", (old, old))
                with patch("cv2.VideoCapture") as capture:
                    capture.return_value.get.return_value = 0
                    with self.assertRaises(SystemExit) as error: prep.main(["sample", "2"])
                    self.assertIn("cannot read", str(error.exception))


if __name__ == "__main__": unittest.main()
