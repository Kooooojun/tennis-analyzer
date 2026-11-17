"""先以合成骨架／遮罩檢查換軌及缺失，不需要私人資料或模型。"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sam_identity import anchor, assignment


def pose(x):
    p = np.full((33, 3), np.nan)
    p[[11, 12, 23, 24]] = [[x-.04, .3, 1], [x+.04, .3, 1], [x-.04, .6, 1], [x+.04, .6, 1]]
    return p


class IdentityTests(unittest.TestCase):
    def test_anchor_ignores_missing_and_overlapping_torsos(self):
        a = np.stack([pose(.3)] * 3); b = np.stack([pose(.3), pose(.7), pose(.8)])
        a[0] = np.nan
        f, points = anchor({0: a, 1: b}, (100, 100))
        self.assertEqual(f, 1)
        np.testing.assert_allclose(points, [[30, 45], [70, 45]])

    def test_no_separated_anchor_rejected(self):
        a = np.stack([pose(.3)] * 2)
        with self.assertRaises(ValueError): anchor({0: a, 1: a.copy()}, (100, 100))

    def test_id_follows_mask_after_track_switch(self):
        masks = np.zeros((2, 100, 100), bool)
        masks[0, :, :50] = True; masks[1, :, 50:] = True
        self.assertEqual(assignment({0: pose(.7), 1: pose(.3)}, [0, 1], masks), {0: 1, 1: 0})

    def test_missing_overlap_does_not_invent_pose(self):
        masks = np.zeros((2, 100, 100), bool)
        self.assertEqual(assignment({0: pose(.7), 1: pose(.3)}, [0, 1], masks), {})

    def test_one_track_cannot_fill_both_ids(self):
        masks = np.ones((2, 100, 100), bool)
        got = assignment({0: pose(.3)}, [0, 1], masks)
        self.assertEqual(len(got), 1)
        self.assertEqual(list(got.values()), [0])


if __name__ == '__main__': unittest.main()
