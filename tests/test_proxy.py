"""補邊幾何、原片往返及 sheet 使用原片座標。"""
import ast, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
import cv2, numpy as np

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "tools"))
from proxy import layout, video_filter, map_pose
from crop import wide, cut, brighten
import pose_full


class ProxyTest(unittest.TestCase):
    def test_layout(self):
        for wh, expected in (((640, 480), (960, 540, 720, 540, 120, 0)),
                             ((480, 640), (540, 960, 540, 720, 0, 120)),
                             ((2520, 1080), (960, 540, 960, 412, 0, 64)),
                             ((1920, 1080), (960, 540, 960, 540, 0, 0)),
                             ((1080, 1920), (540, 960, 540, 960, 0, 0))):
            self.assertEqual(layout(*wh), expected)
        for wh in ((1920, 1080), (1080, 1920)):
            pw, ph, *_ = layout(*wh)
            self.assertEqual(video_filter(*wh), f"scale={pw}:{ph}")
        self.assertEqual(video_filter(640, 480), "scale=720:540,setsar=1,pad=960:540:120:0:black")
        for wh in ((0, 480), (-640, 480)):
            with self.assertRaises(ValueError): layout(*wh)

    def test_round_trip(self):
        P = np.random.default_rng(64).random((30, 33, 3)).astype(np.float32)
        P[0, 2] = np.nan
        for wh in ((640, 480), (480, 640), (2520, 1080), (641, 479), (1920, 1080), (1080, 1920)):
            Q = map_pose(P, *wh)
            back = map_pose(Q, *wh, inverse=True)
            self.assertLess(np.nanmax(np.abs(back[..., :2] - P[..., :2]) * wh), 0.5)
            np.testing.assert_array_equal(Q[..., 2], P[..., 2])
            np.testing.assert_array_equal(np.isnan(Q), np.isnan(P))
            if wh[0] * layout(*wh)[1] == wh[1] * layout(*wh)[0]:
                self.assertIs(Q, P)
        np.testing.assert_allclose(map_pose(np.array([[0., 0., 1.], [1., 1., 0.5]]), 640, 480),
                                   [[0.125, 0., 1.], [0.875, 1., 0.5]])

    def test_near_16_9(self):
        P = np.array([[0.2, 0.3, 1.]], np.float32)
        for w, h in ((1920, 1088), (1088, 1920), (854, 480), (1920, 1078),
                     (1616, 900), (1584, 900), (909, 1600), (891, 1600)):
            pw, ph = (960, 540) if w > h else (540, 960)
            self.assertEqual(video_filter(w, h), f"scale={pw}:{ph}")
            self.assertEqual(layout(w, h), (pw, ph, pw, ph, 0, 0))
            self.assertIs(map_pose(P, w, h), P)
            self.assertIs(map_pose(P, w, h, inverse=True), P)
        for wh in ((1440, 1080), (480, 640), (1618, 900), (1582, 900), (910, 1600), (890, 1600)):
            self.assertIn(",pad=", video_filter(*wh))
            self.assertIsNot(map_pose(P, *wh), P)

    def test_sheet_inverse(self):
        # 只載函式，避免 candidates 的 CLI 主程式讀取私人場次。
        tree = ast.parse((R / "tools" / "candidates.py").read_text(encoding="utf-8"))
        ns = dict(np=np, cv2=cv2, FPS=60, TILE=(375, 250), OFF_NEW=[0] * 12, WHOLE=[0],
                  wide=wide, cut=cut, brighten=brighten, map_pose=map_pose, text=lambda *a: None)
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), "candidates.py", "exec"), ns)
        P = np.ones((120, 33, 3), float)
        P[..., :2] = (0.2, 0.5); P[:, [11, 12], 1] = 0.3
        P[:, [23, 24], 1] = 0.6; P[:, [15, 16], :2] = (0.7, 0.4)
        Q = map_pose(P, 640, 480)
        image = np.full((480, 640, 3), 64, np.uint8)
        c = dict(t=1., vn=1, player="alpha")
        for low, padded, poses, frame in ((False, True, [Q, Q], image),
                                          (False, False, [P, P], image),
                                          (True, True, [Q, Q], np.zeros((540, 960, 3), np.uint8))):
            ns["frames"] = lambda src, ts: {t: frame for t in ts}
            with patch.object(cv2, "circle") as circle, patch.dict(ns, wide=unittest.mock.Mock(wraps=wide)):
                ns["sheet"](c, 0, poses, 0, Path("clip.mp4"), low, padded=padded)
                center = ns["wide"].call_args_list[0].args[0]
                expected = (np.array([0.275, 0.45]) * (960, 540) if low else np.array([128., 216.]))
                np.testing.assert_allclose(center, expected)
                if not low:
                    self.assertLessEqual(np.max(np.abs(np.array(circle.call_args_list[0].args[1]) - (66, 150))), 1)
                    self.assertLessEqual(np.max(np.abs(np.array(circle.call_args_list[1].args[1]) - (233, 100))), 1)

    def test_pose_source_paths(self):
        # 已知模型座標，驗證兩條原片路徑實際儲存的 proxy 座標。
        P = np.ones((33, 3), float); P[:, :2] = (0.5, 0.1)
        P[[11, 12], :2] = ((0.4, 0.3), (0.6, 0.3))
        P[[23, 24], :2] = ((0.45, 0.55), (0.55, 0.55))
        P[[25, 26, 27, 28], :2] = ((0.45, 0.7), (0.55, 0.7), (0.45, 0.9), (0.55, 0.9))
        lm = [types.SimpleNamespace(x=x, y=y, visibility=v) for x, y, v in P]
        world = [types.SimpleNamespace(x=float(i), y=0., z=0.) for i in range(33)]
        result = types.SimpleNamespace(pose_landmarks=[lm], pose_world_landmarks=[world])
        detector = unittest.mock.Mock(); detector.detect.return_value = result; detector.detect_for_video.return_value = result
        for crop in (False, True):
            calls = []
            def frames(cmd, w, h):
                calls.append(cmd)
                return iter([np.full((h, w, 3), 64, np.uint8)] * 3)
            with tempfile.TemporaryDirectory() as d, patch.object(sys, "argv", ["pose_full.py", "proxy.mp4", "model.task", str(Path(d) / "pose.npy"), "1", "source.mp4"]), \
                 patch("cv2.VideoCapture") as cap, patch("prep.probe_rate", return_value=(640, 480, 30.)), \
                 patch("mediapipe.tasks.python.vision.PoseLandmarker.create_from_options", return_value=detector), \
                 patch.object(pose_full, "frames", side_effect=frames), patch.object(pose_full, "use_crop", return_value=crop):
                cap.return_value.get.side_effect = lambda key: {3: 960, 4: 540, 7: 6}[key]
                pose_full.main()
                out = np.load(Path(d) / "pose.npy")
                np.testing.assert_allclose(out[0, 0, :2], (0.40625, 0.1) if crop else (0.5, 0.1), atol=1e-6)
                np.testing.assert_array_equal(np.load(Path(d) / "pose_world.npy")[0, :, 0], np.arange(33))
                self.assertTrue(np.isnan(out[-1]).all())
                if not crop: self.assertIn("fps=30.0,scale=720:540,setsar=1,pad=960:540:120:0:black", calls[-1])


if __name__ == "__main__": unittest.main()
