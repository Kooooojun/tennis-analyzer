"""執行：.venv/bin/python tests/test_ball.py"""
import subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np, torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ball
from events import ball_windows


class WindowTests(unittest.TestCase):
    def test_mask(self):
        self.assertTrue(ball.window_mask(None, 60).all())
        self.assertFalse(ball.window_mask([], 60).any())
        mask = ball.window_mask([[0, 1], [15, 18], [16, 20], [59, 60]], 60)
        self.assertEqual(np.flatnonzero(mask).tolist(), [0, 15, 16, 17, 18, 19, 59])
        self.assertFalse(ball.window_mask([[60, 60]], 60).any())

    def test_bad_windows(self):
        for windows in ([1, 2], [[1]], [[1, 2, 3]], [[1., 2.]], [[np.nan, 2]],
                        [[False, True]], [[-1, 2]], [[3, 2]], [[0, 61]], [[61, 61]]):
            with self.subTest(windows=windows), self.assertRaises(ValueError):
                ball.window_mask(windows, 60)

    def test_candidates(self):
        hand = np.full(120, 10.); who = np.zeros(120, int)
        rows = np.array([[0., -20, 12, 9], [1.5, -20, 12, 9], [1.99, -20, 12, 9]])
        with patch("events.pick", return_value=[(0., 0, 0), (.5, 0, 0), (1.99, 0, 0)]) as pick:
            windows = ball_windows(rows, hand, who, 120)
            pick.assert_called_once_with(rows, hand, lag=0, slack=15, who=who, low=False)
        self.assertEqual(windows.tolist(), [[0, 48], [91, 120]])
        self.assertEqual(ball_windows(rows[1:2], hand, who, 120).tolist(), [[61, 108]])
        with patch("events.pick", return_value=[(1.001, 0, 0)]):
            self.assertEqual(ball_windows(rows, hand, who, 120).tolist(), [[32, 78]])
        self.assertEqual(ball_windows(np.empty((0, 4)), hand, who, 120).shape, (0, 2))
        self.assertEqual(ball_windows(rows, np.zeros(120), who, 120).shape, (0, 2))


class Fake(torch.nn.Module):
    batches = []

    def forward(self, x):
        Fake.batches.append(x.clone())
        hm = torch.zeros((len(x), 1, ball.H_IN, ball.W_IN))
        for k in range(len(x)):
            col = int((x[k].mean() * 100).item()) % 100
            hm[k, 0, 20:23, 30 + col:33 + col] = .75
        return hm


class BatchTests(unittest.TestCase):
    def test_selected_inputs_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); src = d / "clip.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=128x72:r=60:d=1",
                            "-c:v", "libx264", str(src)], check=True)
            with patch.object(ball, "Net", Fake), patch.object(ball, "load_weights"):
                Fake.batches = []; ball.main(str(src), d / "full.npy", "cpu")
                full_batches = Fake.batches; full = np.load(d / "full.npy")
                windows = [[0, 1], [15, 34], [33, 35], [59, 60]]
                Fake.batches = []
                with patch.object(ball.cv2, "resize", wraps=ball.cv2.resize) as resize:
                    ball.main(str(src), d / "window.npy", "cpu", windows)
                mask = ball.window_mask(windows, 60)
                self.assertEqual(resize.call_count, 25 + 28)  # 背景加影格 0、12..34、56..59。
                self.assertEqual([len(x) for x in Fake.batches], [16, 6])
                self.assertTrue(torch.equal(torch.cat(Fake.batches), torch.cat(full_batches)[mask]))
                masked = np.load(d / "window.npy")
                self.assertEqual(masked.shape, full.shape)
                self.assertEqual(masked[mask].tobytes(), full[mask].tobytes())
                self.assertTrue(np.isnan(masked[~mask]).all())
            with patch.object(ball, "Net") as net, patch.object(ball, "load_weights") as load:
                ball.main(str(src), d / "empty.npy", "cpu", [])
                net.assert_not_called(); load.assert_not_called()
                self.assertEqual(np.load(d / "empty.npy").shape, (60, 3))
                self.assertTrue(np.isnan(np.load(d / "empty.npy")).all())
            np.save(d / "windows.npy", np.empty((0, 2), dtype=np.int64))
            result = subprocess.run([sys.executable, str(Path(ball.__file__)), str(src), str(d / "cli.npy"), "cpu:0",
                                     "--windows", str(d / "windows.npy")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(np.isnan(np.load(d / "cli.npy")).all())


if __name__ == "__main__": unittest.main()
