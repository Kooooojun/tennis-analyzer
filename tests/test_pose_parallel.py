# Run: .venv/bin/python tests/test_pose_parallel.py   (failure list: testset/results/pose-parallel/pred.md, F2-F8, F10-F12)
# pose_full.in_order(): the full-frame path runs its two landmarkers on two threads; these check order, errors, exit and Ctrl-C.
import os, signal, subprocess, sys, tempfile, textwrap, threading, time, types, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import pose_full
from pose_full import in_order


def pose_threads():
    return [t for t in threading.enumerate() if t.name.startswith("pose")]


class InOrder(unittest.TestCase):
    def tearDown(self):  # F5: nothing left running after any case
        for t in pose_threads(): t.join(5)
        self.assertEqual(pose_threads(), [])

    def test_order_and_each_model_sees_every_item_once(self):  # F2, F3
        seen = {"a": [], "b": []}
        def model(name):
            def run(x):
                seen[name].append((x, threading.current_thread().name))
                time.sleep(0.001 * (x % 3))  # uneven: results still come back in item order
                return (name, x)
            return run
        out = list(in_order(range(20), [model("a"), model("b")]))
        self.assertEqual([x for x, _ in out], list(range(20)))
        self.assertEqual([r for _, r in out], [[("a", x), ("b", x)] for x in range(20)])
        for name in seen:
            self.assertEqual([x for x, _ in seen[name]], list(range(20)))
            self.assertEqual(len({t for _, t in seen[name]}), 1)  # one thread per model: its calls never overlap
        self.assertNotEqual(seen["a"][0][1], seen["b"][0][1])
        self.assertNotIn(threading.current_thread().name, {seen["a"][0][1], seen["b"][0][1]})

    def test_models_run_at_the_same_time(self):  # F9 in miniature: two models meet on the same item, so neither waits for the other
        meet = threading.Barrier(2, timeout=5)
        def model(x): meet.wait(); return x
        self.assertEqual([r for _, r in in_order(range(5), [model, model])], [[x, x] for x in range(5)])

    def test_single_model(self):  # F10: N = 1 has one landmarker
        self.assertEqual(list(in_order("abc", [str.upper])), [("a", ["A"]), ("b", ["B"]), ("c", ["C"])])
        self.assertEqual(list(in_order([], [str.upper])), [])

    def test_in_flight_is_bounded(self):  # F7
        made = [0]
        def items():
            for i in range(50): made[0] += 1; yield i
        for depth in (1, 2, 4):
            made[0] = 0
            for j, _ in in_order(items(), [lambda x: x, lambda x: x], depth=depth):
                self.assertLessEqual(made[0] - j, depth)

    def test_model_error_reaches_caller_and_stops(self):  # F4, F5, F12
        closed, calls = [], []
        def items():
            try:
                for i in range(1000): yield i
            finally: closed.append(True)
        def bad(x):
            calls.append(x)
            if x == 3: raise RuntimeError("model failed on 3")
            return x
        got = []
        with self.assertRaisesRegex(RuntimeError, "model failed on 3"):
            for x, _ in in_order(items(), [lambda x: x, bad]): got.append(x)
        self.assertEqual(got, [0, 1, 2])  # nothing after the failed item reaches the caller
        self.assertEqual(closed, [True])  # the source (ffmpeg in pose_full) is stopped at once
        self.assertLessEqual(max(calls), 3 + pose_full.DEPTH)  # queued work is dropped, not run to the end
        for e in (TimeoutError("inside the model"), KeyboardInterrupt()):  # not mistaken for a wait timeout / swallowed
            def raise_(x, e=e): raise e
            with self.assertRaises(type(e)): list(in_order(range(3), [raise_]))

    def test_source_error_reaches_caller(self):  # F4: frames() exits on an ffmpeg failure
        def items():
            yield 0; yield 1; sys.exit("ffmpeg failed")
        with self.assertRaises(SystemExit): list(in_order(items(), [lambda x: x, lambda x: x]))

    def test_caller_leaving_early_stops_workers(self):  # F5: an exception in the merge, outside in_order
        calls = []
        def slow(x): calls.append(x); time.sleep(0.01); return x
        runs = in_order(range(1000), [slow, slow])
        for x, _ in runs:
            if x == 2: break
        runs.close()
        n = len(calls); time.sleep(0.1)
        self.assertEqual(len(calls), n)  # nothing keeps running after close()
        self.assertLess(n, 2 * (3 + pose_full.DEPTH) + 1)

    @unittest.skipIf(os.name == "nt", "SIGINT cannot be sent to one child process on Windows")
    def test_ctrl_c_stops_promptly(self):  # F6
        script = textwrap.dedent(f"""
            import sys, time, itertools
            sys.path.insert(0, {str(ROOT / 'tools')!r})
            from pose_full import in_order
            def slow(x): time.sleep(0.5); return x
            for x, _ in in_order(itertools.count(), [slow, slow]):
                print(x, flush=True)
        """)
        p = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(), "0")
            t = time.monotonic(); p.send_signal(signal.SIGINT)
            _, err = p.communicate(timeout=10)
            self.assertLess(time.monotonic() - t, 3)  # one running call (0.5 s) + one wait slice, not the queued items
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("KeyboardInterrupt", err)
        finally:
            if p.poll() is None: p.kill(); p.wait()


class FullFramePath(unittest.TestCase):
    """main() on the full-frame path with fake landmarkers: frame i is a solid image of value i."""
    def landmarks(self, i, vis):
        P = np.ones((33, 3)) * vis; P[:, :2] = (0.5, 0.1)
        P[[11, 12], :2] = ((0.4, 0.3), (0.6, 0.3)); P[[23, 24], :2] = ((0.45, 0.55), (0.55, 0.55))
        P[0, 0] = 0.01 * i  # the nose marks which frame this skeleton came from
        return [types.SimpleNamespace(x=x, y=y, visibility=v) for x, y, v in P], [types.SimpleNamespace(x=i, y=vis, z=0.) for _ in range(33)]

    def run_main(self, d, fail_at=None, n_frames=8):
        calls = {2: [], 1: []}
        def make(opts):
            k = opts.num_poses
            def detect_for_video(image, ts):
                i = int(image.numpy_view()[0, 0, 0])
                calls[k].append((ts, i, threading.current_thread().name))
                if k == 1 and i == fail_at: raise RuntimeError(f"landmarker failed on frame {i}")
                lm, w = self.landmarks(i, 0.9 if k == 2 else 0.6)
                return types.SimpleNamespace(pose_landmarks=[lm], pose_world_landmarks=[w])
            return types.SimpleNamespace(detect_for_video=detect_for_video)
        def frames(cmd, w, h):
            for i in range(n_frames): yield np.full((h, w, 3), i, np.uint8)
        with patch.object(sys, "argv", ["pose_full.py", "proxy.mp4", "model.task", str(Path(d) / "pose.npy"), "2"]), \
             patch("cv2.VideoCapture") as cap, patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options", side_effect=make), \
             patch.object(pose_full, "frames", side_effect=frames):
            cap.return_value.get.side_effect = lambda key: {3: 96, 4: 54, 7: n_frames}[key]
            pose_full.main()
        return calls

    def test_rows_match_frames_and_timestamps_increase(self):  # F2, F3, F11
        d = Path(tempfile.mkdtemp()); calls = self.run_main(d)
        for k in (2, 1):
            self.assertEqual([i for _, i, _ in calls[k]], list(range(8)))
            self.assertEqual([ts for ts, _, _ in calls[k]], [int(i * 1000 / 60) for i in range(8)])
        self.assertNotEqual(calls[2][0][2], calls[1][0][2])
        P, W = np.load(d / "pose.npy"), np.load(d / "pose_world.npy")
        np.testing.assert_allclose(P[:, 0, 0], 0.01 * np.arange(8), atol=1e-6)  # row i is frame i
        np.testing.assert_allclose(P[:, 5, 2], 0.6)  # the single-person skeleton replaced the slot it stands on
        np.testing.assert_array_equal(W[:, 0, 0], np.arange(8))

    def test_landmarker_error_fails_the_run(self):  # F4: no shorter pose.npy is written
        d = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(RuntimeError, "landmarker failed on frame 3"):
            self.run_main(d, fail_at=3)
        self.assertEqual(list(d.iterdir()), [])
        for t in pose_threads(): t.join(5)
        self.assertEqual(pose_threads(), [])


if __name__ == "__main__": unittest.main()
