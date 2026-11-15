# Run: .venv/bin/python tests/test_kind.py   (plain asserts; failure list in testset/results/stroke-classify_pred.md)
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from kind import classify, prefill, PREFILL_MIN, CONF_MIN

N, F = 200, 120


def body(yaw, rw, lw, mirror=False, vis=0.9):
    """Synthetic world + image pose, constant over N frames. Body frame: a = toward the player's right shoulder, h = height above hip, b = forward.
    rw / lw = (a, h, b) metres of the right / left wrist. yaw rotates the body about the vertical axis (0 = back to camera, pi = facing it).
    mirror = a left-hander drawn as the mirror image (swap right/left body parts)."""
    ca, sa = np.cos(yaw), np.sin(yaw)
    def w(a, h, b): return [a * ca + b * sa, -h, -a * sa + b * ca]  # MediaPipe world: y points down
    pts = {0: (0, 0.62, 0.05), 11: (-0.19, 0.5, 0), 12: (0.19, 0.5, 0), 23: (-0.1, 0, 0), 24: (0.1, 0, 0), 15: lw, 16: rw}
    if mirror: pts = {{15: 16, 16: 15, 11: 12, 12: 11, 23: 24, 24: 23}.get(k, k): (-a, h, b) for k, (a, h, b) in pts.items()}  # mirror image, left <-> right labels
    W = np.full((N, 33, 3), np.nan); P = np.full((N, 33, 3), np.nan)
    for k, v in pts.items():
        x, y, z = w(*v); W[:, k] = [x, y, z]; P[:, k] = [0.5 + 0.5 * x, 0.5 + 0.5 * y, vis]
    return P, W


def go(rw, lw, yaw=0.0, hand="R", **kw):
    P, W = body(yaw, rw, lw, mirror=(hand == "L"))
    return classify(P, F, hand, W, **kw)


# 1: racket wrist on the racket side -> FH from every viewing angle; on the other side -> BH
for yaw in (0, 0.8, np.pi / 2, 2.4, np.pi):
    assert go((0.45, 0.1, 0.3), (-0.2, 0.1, 0.2), yaw)["kind"] == "FH", yaw
    assert go((-0.4, 0.1, 0.3), (-0.25, 0.1, 0.3), yaw)["kind"] == "BH", yaw
# 3: backswing wrist near the hips line = cannot tell, not a coin flip (conf < CONF_MIN)
r = go((0.12, 0.1, 0.4), (-0.3, 0.1, 0.2)); assert r["kind"] == "?" and r["conf"] < 0.5, r
# 4: left-hander drawn mirrored gives the same answer with hand="L" and is mirrored
assert go((0.45, 0.1, 0.3), (-0.2, 0.1, 0.2), 0.5, "L")["kind"] == "FH"
assert go((-0.4, 0.1, 0.3), (-0.25, 0.1, 0.3), 0.5, "L")["kind"] == "BH"
# 5: wrist above the head -> SV or OH, never FH / BH
r = go((0.2, 0.95, 0.1), (-0.2, 0.3, 0.1)); assert r["kind"] in ("SV", "OH"), r
# 6: serve = racket arm hanging 1.0-1.7 s before contact (starts from rest); overhead = racket stayed up
def high(kind):
    P, W = body(0.0, (0.2, 0.95, 0.1), (-0.2, 0.3, 0.1)); pre = slice(F - 100, F - 60)
    if kind == "SV": P[pre, 16, 1] = 0.5 + 0.5 * 0.2; W[pre, 16, 1] = 0.2  # wrist hanging at hip level (below the shoulder), y down
    return classify(P, F, "R", W)["kind"]
assert high("SV") == "SV" and high("OH") == "OH"
# 7: no data / low visibility -> "?"
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); P[:] = np.nan; W[:] = np.nan; assert classify(P, F, "R", W)["kind"] == "?"
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); P[:, 16, 2] = 0.1; assert classify(P, F, "R", W)["kind"] == "?"
# 8: contact in the first second of the video (no backswing window) does not crash
P, W = body(0.0, (0.2, 0.95, 0.1), (-0.2, 0.3, 0.1)); assert classify(P, 10, "R", W)["kind"] in ("SV", "OH", "?")
# 9: without world data (2D only) a front-on FH still works
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); assert classify(P, F, "R", None)["kind"] == "FH"
# 10 (K4): high ball with no history 1.0-1.7 s before contact -> "?" with conf 0 (was OH)
P, W = body(0.0, (0.2, 0.95, 0.1), (-0.2, 0.3, 0.1)); r = classify(P, 60, "R", W); assert r["kind"] == "?" and r["conf"] == 0.0, r
P[F - 100:F - 60] = np.nan; r = classify(P, F, "R", W); assert r["kind"] == "?" and r["conf"] == 0.0, r
# 11 (K5): serve evidence (hanging arm) alone is not enough to pre-fill: SV conf < 0.5
P, W = body(0.0, (0.2, 0.95, 0.1), (-0.2, 0.3, 0.1)); P[F - 100:F - 60, 16, 1] = 0.6; r = classify(P, F, "R", W); assert r["kind"] == "SV" and r["conf"] < 0.5, r
# 12 (K5): wrist only rises above the head after contact (high follow-through) is not a serve
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); P[F + 2:F + 6, 16, 1] = 0.5 - 0.5 * 0.95; assert classify(P, F, "R", W)["kind"] not in ("SV", "OH")
# 13: racket wrist hidden in the backswing window (vis 0.1) but visible at contact -> "?"
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); P[F - 24:F - 13, 16, 2] = 0.1; P[F:F + 5, 16, 2] = 0.99; assert classify(P, F, "R", W)["kind"] == "?"
# 14: portrait vs landscape: same body in pixels, normalised by each frame size -> same kind, side within 0.05
for rw in ((0.45, 0.1, 0.3), (-0.4, 0.1, 0.3)):
    P, _ = body(np.pi, rw, (-0.25, 0.1, 0.2)); px = (P[:, :, :2] - 0.5) * 300  # pixel offsets around the frame centre
    res = []
    for w, h in ((540, 960), (960, 540)):
        Q = P.copy(); Q[:, :, 0] = (w / 2 + px[:, :, 0]) / w; Q[:, :, 1] = (h / 2 + px[:, :, 1]) / h; res.append(classify(Q, F, "R", None, size=(w, h)))
    assert res[0]["kind"] == res[1]["kind"] != "?" and abs(res[0]["side"] - res[1]["side"]) < 0.05, res
# 16: hand above the head in only 1-2 of f-3..f+1 (the rest NaN) is not enough for SV / OH
P, W = body(0.0, (0.45, 0.1, 0.3), (-0.2, 0.1, 0.2)); P[F - 3:F + 2, 16, :2] = np.nan; P[F, 16, :2] = (0.6, 0.5 - 0.5 * 0.95)
assert classify(P, F, "R", W)["kind"] not in ("SV", "OH")
# 17: landscape 2D path (no world): hips 15 px wide in a 960x540 frame are below 2% of the width -> "?"; 60 px wide -> FH
for hw, want in ((15, "?"), (60, "FH")):
    Q = np.full((N, 33, 3), np.nan); Q[:, :, 2] = 0.9
    for k, (x, y) in {0: (480, 160), 11: (450, 200), 12: (510, 200), 23: (480 - hw / 2, 300), 24: (480 + hw / 2, 300), 15: (440, 290), 16: (480 + hw * 1.5, 290)}.items():
        Q[:, k, 0] = x / 960; Q[:, k, 1] = y / 540
    assert classify(Q, F, "R", None, size=(960, 540))["kind"] == want, (hw, classify(Q, F, "R", None, size=(960, 540)))
# 18: prefill() only writes the kind when the evidence is strong: just below PREFILL_MIN -> '?', at or above -> the kind
assert PREFILL_MIN > CONF_MIN  # stricter than the old pre-fill line, and CONF_MIN itself is untouched (auto_kind / scoring)
assert prefill("FH", PREFILL_MIN - 0.01) == "?" and prefill("FH", PREFILL_MIN) == "FH" and prefill("BH", PREFILL_MIN + 0.01) == "BH"
assert prefill("FH", 0.5) == "?"  # the old line pre-filled this one
assert prefill("?", 0.9) == "?" and prefill("FH", None) == "?"  # no kind / no conf (no hand profile) -> '?'
assert prefill("FH", 0.5, 0.5) == "FH"  # explicit line = the old behaviour
import kind as K  # line=None reads PREFILL_MIN at call time (a changed constant applies)
K.PREFILL_MIN, old = 0.9, K.PREFILL_MIN; assert prefill("FH", 0.8) == "?"; K.PREFILL_MIN = old
print("kind tests ok")
