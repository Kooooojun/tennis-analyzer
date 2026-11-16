# Run: .venv/bin/python tests/test_annotate.py
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from annotate import JOINTS, MINVIS, panel_pos, parse_args, pose_bbox

# #101：影片面板說明量測對象、五格中位數與 0–100 尺度，文字不超出面板。
from annotate import stroke_info, F, PANEL_W, INK
_, lines = stroke_info(dict(no=1, kind="FH", knee=None, contact_h=0.53))
assert [s for s, _ in lines] == ["擊球時手腕高度（2D）", "53（髖＝0、肩＝100）", "接觸格附近五格中位數"]
assert all(col == INK and F(24).getlength(s) <= PANEL_W - 20 for s, col in lines)
assert stroke_info(dict(no=1, kind="FH", knee=None, contact_h=None))[1] == []

W, H = 1280, 720
PW, PH = 320, 142


def make_pose(xs, ys, vis=1.0):
    p = np.zeros((33, 3), dtype=np.float32)
    p[:, 2] = 0.0
    for j, x, y in zip(JOINTS, xs, ys):
        p[j] = [x, y, vis]
    return p


# 1. pose_bbox: None or all invisible -> None; otherwise pixel bbox of visible JOINTS
assert pose_bbox(None, W, H) is None
assert pose_bbox(make_pose([0.5] * len(JOINTS), [0.5] * len(JOINTS), vis=MINVIS - 0.05), W, H) is None

p = np.zeros((33, 3), dtype=np.float32)
p[11] = [0.2, 0.3, 0.9]
p[12] = [0.4, 0.7, 0.9]
p[15] = [0.9, 0.9, 0.1]  # below MINVIS: ignored
assert np.allclose(pose_bbox(p, W, H), (0.2 * W, 0.3 * H, 0.4 * W, 0.7 * H))

# 2. panel_pos: no players -> default top-left (10, 8)
assert panel_pos([], W, H, PW, PH) == (10, 8)

# 3. panel_pos: single player near each corner -> picks farthest corner
assert panel_pos([(20, 20, 300, 350)], W, H, PW, PH) == (W - PW - 10, H - PH - 8)        # player TL -> BR
assert panel_pos([(950, 20, 1250, 350)], W, H, PW, PH) == (10, H - PH - 8)               # player TR -> BL
assert panel_pos([(20, 360, 300, 700)], W, H, PW, PH) == (W - PW - 10, 8)                # player BL -> TR
assert panel_pos([(950, 360, 1250, 700)], W, H, PW, PH) == (10, 8)                       # player BR -> TL

# 4. panel_pos: two players on TL and BR -> avoids both, picks TR or BL (not TL/BR)
pos_2p = panel_pos([(20, 20, 300, 350), (960, 380, 1250, 700)], W, H, PW, PH)
assert pos_2p in ((W - PW - 10, 8), (10, H - PH - 8)), pos_2p

# 5. panel_pos: huge player covering all 4 corners, least overlap in TR
# Leave extra room on TR by placing bbox slightly left and down
huge = (10, 100, 1100, 710)
assert panel_pos([huge], W, H, PW, PH) == (W - PW - 10, 8)

# 6. panel_pos: fixed position overrides bboxes
tl_box = [(20, 20, 300, 350)]
assert panel_pos(tl_box, W, H, PW, PH, pos="tl") == (10, 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="tr") == (W - PW - 10, 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="bl") == (10, H - PH - 8)
assert panel_pos(tl_box, W, H, PW, PH, pos="br") == (W - PW - 10, H - PH - 8)

try:
    panel_pos([], W, H, PW, PH, pos="center")
    raise AssertionError("expected ValueError for invalid pos")
except ValueError:
    pass

# 7. parse_args: session, optional video, --panel
a1 = parse_args(["2026-11-20"])
assert a1.session == "2026-11-20" and a1.video is None and a1.panel == "auto"

a2 = parse_args(["2026-11-20", "clip1", "--panel", "br"])
assert a2.session == "2026-11-20" and a2.video == "clip1" and a2.panel == "br"

# 新補邊姿態畫回原片；真 ffmpeg 輸出核對所有軌，及送往即時膝角的座標。
import contextlib, io, json, subprocess, tempfile, cv2
from unittest.mock import patch
import annotate as mod
from prep import probe_rate

for metadata, size in (({"tags": {"rotate": "-90.0"}}, (1088, 1920)),
                       ({"side_data_list": [{"rotation": "-90.0"}]}, (1088, 1920)),
                       ({"side_data_list": [{"rotation": 0}], "tags": {"rotate": "90"}}, (1920, 1088)),
                       ({"tags": {"rotate": "180.0"}}, (1920, 1088))):
    data = json.dumps({"streams": [{"width": 1920, "height": 1088, "avg_frame_rate": "60/1", **metadata}]})
    with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=data, stderr="")), \
         patch.object(subprocess, "check_output", return_value=data.encode()):
        assert probe_rate("clip.mp4") == (*size, 60.)
        assert mod.probe("clip.mp4") == size, "標註與prep的旋轉尺寸須相同"

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp); wd = root / "work" / "clip"; wd.mkdir(parents=True)
    unpadded = {}
    for w, h, padded in ((640, 480, True), (480, 640, True), (640, 480, False),
                         (960, 540, False), (960, 540, True), (540, 960, False), (540, 960, True)):
        src = root / "source.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=black:s={w}x{h}:r=60:d=0.05",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
        marker = wd / "proxy_filter.txt"
        if padded: marker.write_text("padded", encoding="utf-8")
        else: marker.unlink(missing_ok=True)
        originals = []; saved = []
        for k, x in enumerate((0.2, 0.8)):
            p = np.zeros((3, 33, 3), np.float32); p[:, 0] = [x, 0.3, 1]
            originals.append(p); q = p.copy()
            if padded and (w, h) == (640, 480): q[..., 0] = q[..., 0] * 0.75 + 0.125
            if padded and (w, h) == (480, 640): q[..., 1] = q[..., 1] * 0.75 + 0.125
            saved.append(q); np.save(wd / f"pose{'_t1' if k else ''}.npy", q)
        seen = []
        def knee(p, world, size):
            seen.append(p.copy()); return None, None
        with patch.object(mod, "work", return_value=root / "work"), patch.object(mod, "web", return_value=root / "web"), \
             patch.object(mod, "videos", return_value=["clip"]), patch.object(mod, "live_knee", side_effect=knee), \
             patch.object(mod, "h264_args", return_value=["-c:v", "libx264", "-crf", "18"]), contextlib.redirect_stdout(io.StringIO()):
            mod.annotate("synth", "clip", src)
        assert len(seen) == 6
        for i, p in enumerate(seen):
            expected = originals[i % 2][i // 2]
            if padded and w * 9 != h * 16 and h * 9 != w * 16:
                assert np.allclose(p, expected, atol=1e-6), "每條軌須回到原片座標"
            else:
                assert p.tobytes() == saved[i % 2][i // 2].tobytes(), "舊場次與16:9逐位元不變"
        cap = cv2.VideoCapture(str(root / "web" / "annotated_clip.mp4")); ok, frame = cap.read(); cap.release()
        assert ok
        encoded = (root / "web" / "annotated_clip.mp4").read_bytes()
        if not padded: unpadded[w, h] = encoded
        elif (w, h) in unpadded: assert encoded == unpadded[w, h], "16:9 標註輸出逐位元不變"
        H, W = frame.shape[:2]
        for p in originals:
            x, y = (p[0, 0, :2] * (W, H)).astype(int)
            assert frame[y-1:y+2, x-1:x+2].mean() > 180, "輸出圓點須落在原片位置"

print("ok")
