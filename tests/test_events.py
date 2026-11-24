"""Run: .venv/bin/python tests/test_events.py"""
import hashlib, sys, subprocess, tempfile, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from events import pick, hand_speed

# A sustained swing wins over a louder sound confirmed by only two isolated pose samples.
hand = np.zeros(180); hand[54:64] = 8
hand[81:90] = np.nan; hand[86:88] = 30
rows = np.array([[1., -20., 12., 9.], [1.45, -20., 20., 9.]])
assert [r[0] for r in pick(rows, hand, source_fps=30)] == [1.], pick(rows, hand, source_fps=30)
assert pick(rows, np.zeros(180), source_fps=30) == []
assert pick(rows, np.full(180, np.nan), source_fps=30) == []

# The same real swing, sampled at 30 fps then interpolated onto the proxy timeline, remains detectable.
pose = np.zeros((180, 33, 3)); pose[..., 2] = 1
pose[:, [11, 12], 1] = .4; pose[:, [23, 24], 1] = .6
pose[:, [11, 23], 0] = .45; pose[:, [12, 24], 0] = .55
pose[:, 15] = [.4, .6, 1]; pose[:, 16] = [.6, .6, 1]
pose[:, 16, 0] += np.interp(np.arange(180), [0, 54, 62, 179], [0, 0, .2, .2])
low = pose[::2]; restored = pose.copy()
for joint in range(33):
    for axis in range(3): restored[:, joint, axis] = np.interp(np.arange(180), np.arange(0, 180, 2), low[:, joint, axis])
assert len(pick(rows[:1], hand_speed(restored, 1.), source_fps=30)) == 1
# A scene of repeated slower, sustained swings can calibrate itself; an isolated weak sound cannot.
times = np.arange(1., 18., 1.6); h = np.zeros(1200)
for t in times:
    f = round(t * 60); h[f-12:f+3] = 4
slow = np.array([[t, -20, 12, 9] for t in times])
assert len(pick(slow, h, source_fps=24)) == len(slow)
assert pick(slow[:1], h, source_fps=24) == []
assert pick(rows[:1], hand, source_fps=60)  # existing callers retain peak-speed behavior
print("ok")


class CandidateTests(unittest.TestCase):
    def test_window_front(self):
        h = np.zeros(180); h[48:54] = 8
        self.assertEqual(len(pick(rows[:1], h, source_fps=24)), 1)

    def test_missing_samples_count_as_zero(self):
        h = np.zeros(180); h[48:63] = np.nan; h[48] = 0; h[49:52] = 8
        self.assertEqual(pick(rows[:1], h, source_fps=24), [])

    def scene(self, speeds, broadband=None):
        ts = 1 + np.arange(len(speeds)) * 2.; h = np.zeros(round((ts[-1] + 1) * 60))
        for t, speed in zip(ts, speeds): h[round(t*60)-12:round(t*60)+3] = speed
        return np.array([[t, -20, 12, bb] for t, bb in zip(ts, [9]*len(ts) if broadband is None else broadband)]), h

    def test_ten_candidates_required(self):
        r, h = self.scene([4]*10)
        self.assertEqual(pick(r[:9], h, source_fps=24), [])
        self.assertEqual(len(pick(r, h, source_fps=24)), 10)

    def test_broadband_and_zero_speed_excluded(self):
        r, h = self.scene([4]*10, [9]*9+[3.99])
        self.assertEqual(pick(r, h, source_fps=24), [])
        r, h = self.scene([4]*9+[0])
        self.assertEqual(pick(r, h, source_fps=24), [])

    def test_lower_and_upper_clamps(self):
        r, h = self.scene([2]*10+[3])
        self.assertEqual([x[0] for x in pick(r, h, source_fps=24)], [r[-1, 0]])
        r, h = self.scene([2]*10+[2.7])
        self.assertEqual(pick(r, h, source_fps=24), [])
        r, h = self.scene([12]*10+[6])
        self.assertEqual(len(pick(r, h, source_fps=24, low=False)), 11)

    def test_sustained_person_wins_over_peak_person(self):
        r = np.array([[1., -20, 12, 9], [1.7, -20, 12, 9]])
        h = np.zeros(180); people = np.zeros(180, dtype=int)
        h[48:63] = h[90:105] = 8; h[60] = 30; people[60] = 1
        self.assertEqual(len(pick(r, h, who=people, source_fps=24)), 1)

    def test_tied_people_fall_back_to_peak(self):
        r = np.array([[1., -20, 12, 9], [1.7, -20, 12, 9]])
        h = np.zeros(180); people = np.zeros(180, dtype=int)
        h[48:58] = h[90:105] = 8; people[53:58] = 1; h[55] = 30
        self.assertEqual(len(pick(r, h, who=people, source_fps=24)), 2)

    def test_no_eligible_person_samples(self):
        h = np.full(180, np.nan); h[48] = -1
        self.assertEqual(pick(rows[:1], h, who=np.zeros(180, dtype=int), source_fps=24), [])


class SourceGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.d = Path(tmp.name)
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x64:r=60:d=3", "-pix_fmt", "yuv420p", str(self.d / "proxy.mp4")], check=True)
        p = pose.copy(); p[:, 16, 0] = .6 + np.interp(np.arange(180), [0, 58, 60, 179], [0, 0, .08, .08])
        np.save(self.d / "pose.npy", p); np.save(self.d / "ball.npy", np.full((180, 3), np.nan)); np.save(self.d / "sounds.npy", rows[:1])

    def cli(self, fps, method):
        for name, value in (("src_fps.txt", fps), ("pose_method.txt", method)):
            p = self.d / name
            if p.exists():
                if p.is_dir(): p.rmdir()
                else: p.unlink()
            if value == "directory": p.mkdir()
            elif value is not None: p.write_text(value, encoding="utf-8")
        return subprocess.run([sys.executable, "tools/events.py", *[str(self.d / f) for f in ("sounds.npy", "ball.npy", "pose.npy", "events.npy")]], capture_output=True, text=True, encoding="utf-8")

    def test_pose_method_gate_and_source_fps(self):
        r = self.cli(None, None); self.assertEqual(r.returncode, 0, r.stderr); baseline = np.load(self.d / "events.npy")
        self.assertEqual(len(baseline), 1)
        # SHA-256 from this fixed fixture before the silent path was added.
        self.assertEqual(hashlib.sha256((self.d / "events.npy").read_bytes()).hexdigest(),
                         "632ce5fa982e527ef699803276653d6c12a2564425b7a001cf997a6ad6636811")
        # the lag goes next to events.npy: one sound, no ball track -> fallback 0, written and marked
        lag = (self.d / "lag.txt").read_text(encoding="utf-8").split()
        self.assertEqual(lag[0], "0"); self.assertIn("fallback", lag)
        self.assertIn("sound lag 0 frames (fallback)", r.stdout)
        cases = [("24", None, False), ("24", "1", False), ("24", "2", True), ("24", "3", True),
                 ("24", "2.0", False), ("24", "bad", False), ("24", "directory", False),
                 ("24", "\ufeff2", True), ("\ufeff24", "2", True), ("60", "2", False), ("50", "2", False), (None, "2", False)]
        for fps, method, active in cases:
            with self.subTest(fps=fps, method=method):
                r = self.cli(fps, method); self.assertEqual(r.returncode, 0, r.stderr)
                result = np.load(self.d / "events.npy")
                if active: self.assertEqual(len(result), 0)
                else: self.assertTrue(np.array_equal(result, baseline))

    def test_invalid_source_fps(self):
        for fps in ("", "0", "-24", "nan", "inf", "bad"):
            with self.subTest(fps=fps):
                r = self.cli(fps, "2")
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn("Traceback", r.stderr)

    def test_ball_turn_and_trusted_wrist_must_agree(self):
        p = pose.copy()
        ball = np.full((len(p), 3), np.nan)
        frames = np.arange(51, 70)
        ball[frames] = np.column_stack((.75 + .025 * abs(frames - 60), np.full(len(frames), .6), np.ones(len(frames))))
        for scenario in ("silent", "missing", "no turn", "opposed swing", "hip jump"):
            with self.subTest(scenario=scenario):
                sound = self.d / "sounds.npy"
                sound.unlink(missing_ok=True)
                if scenario != "missing": np.save(sound, np.empty((0, 4)))
                q = p.copy()
                track = ball.copy()
                if scenario == "no turn": track[:, 0] = .75 + .02 * (np.arange(len(p)) - 60)
                if scenario == "opposed swing": q[:, 16, 0] = 1.5 - q[:, 16, 0]
                if scenario == "hip jump": q[60:, :, 0] += .2
                np.save(self.d / "pose.npy", q)
                np.save(self.d / "ball.npy", track)
                r = self.cli(None, None)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(np.load(self.d / "events.npy")[:, 0].tolist(),
                                 [1.] if scenario in ("silent", "missing") else [])


if __name__ == "__main__": unittest.main()
