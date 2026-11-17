"""不需要私人資料；在隔離 venv 執行本檔。"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signal_adapter import sample_signals, contacts


class AdapterTests(unittest.TestCase):
    def inputs(self):
        pose = np.zeros((240, 33, 3)); pose[..., 2] = 1
        pose[..., :2] = .5
        pose[48:65, 16, 0] += np.linspace(0, .2, 17)
        pose[65:, 16, 0] += .2
        return pose, np.full((240, 3), np.nan)

    def test_pixel_coordinates_and_timing(self):
        pose, ball = self.inputs(); ball[8] = [.1, .2, .9]
        t, b, p = sample_signals(pose, ball, (960, 540))
        np.testing.assert_allclose(t, np.arange(60) / 15)
        np.testing.assert_allclose(b[2], [96, 108])
        np.testing.assert_allclose(p[2, 16, :2], [480, 270])
        self.assertTrue(np.isnan(b[1]).all())

    def test_missing_visibility_and_no_input_mutation(self):
        pose, ball = self.inputs(); pose[8, 16, 2] = .1
        original = pose.copy()
        _, _, p = sample_signals(pose, ball, (960, 540))
        self.assertEqual(p[2, 16, 2], .1)
        np.testing.assert_array_equal(pose, original)

    def test_upstream_defaults_and_missing_ball(self):
        pose, ball = self.inputs()
        got = contacts([pose], ball, (960, 540), Path('work/repos/swing-analysis'))
        self.assertTrue(got)
        self.assertTrue(all(abs(t * 15 - round(t * 15)) < 1e-6 for t in got))
        self.assertEqual(got, contacts([pose, pose], ball, (960, 540), Path('work/repos/swing-analysis')))

    def test_misaligned_inputs_rejected(self):
        pose, ball = self.inputs()
        with self.assertRaises(ValueError): sample_signals(pose, ball[:-1], (960, 540))


if __name__ == '__main__': unittest.main()
