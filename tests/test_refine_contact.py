"""執行：.venv/bin/python tests/test_refine_contact.py；以隔離場次驗證 refine 的輸出。"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from score import score_session

ROOT = Path(__file__).resolve().parent.parent
# 持拍腕在第70格完成引拍，之後向前；沒有私人影格或骨架。
frames = []
for f in range(150):
    xy = [[.5, .2], [.4, .4], [.6, .4], [.35, .5], [.65, .5], [.3, .6],
          [.3 + max(0, f - 70) * .01, .5], [.43, .6], [.57, .6],
          [.4, .75], [.6, .75], [.35, .9], [.65, .9], [.35, .92], [.65, .92], [.35, .94], [.65, .94]]
    frames.append([[x, y, 1.] for x, y in xy])
raw = [dict(id=i, video=1, player="p1", kind="FH", drill="feed", t=2. + i * .4,
            contact=90, contact_h=.5, knee=150., elbow=135., frames=frames, size=[960, 540], hand="R") for i in range(3)]


def run(config, rows=raw, forbid_marker=False):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tools").mkdir(); (root / "videos" / "synthetic").mkdir(parents=True)
        for name in ("refine", "common", "metrics", "kind", "platform_util"):
            shutil.copyfile(ROOT / "tools" / (name + ".py"), root / "tools" / (name + ".py"))
        w = root / "work" / "synthetic"; w.mkdir(parents=True)
        d = root / "web" / "sessions" / "synthetic"; d.mkdir(parents=True)
        (w / "refine.json").write_text(json.dumps(config), encoding="utf-8")
        source = json.dumps(rows)
        (d / "strokes_raw.json").write_text(source, encoding="utf-8")
        command = [sys.executable, str(root / "tools" / "refine.py"), "synthetic"]
        if forbid_marker:
            code = """import runpy, sys
sys.path.insert(0, sys.argv[1])
import metrics
def guarded(fn):
    def call(frames, *args, **kwargs):
        assert frames[0][0][0] != .123, '不可信拍仍呼叫 ' + fn.__name__
        return fn(frames, *args, **kwargs)
    return call
for name in ('measure_clip', 'arm_checks', 'form_checks'):
    setattr(metrics, name, guarded(getattr(metrics, name)))
path = sys.argv[2]; sys.argv = [path, 'synthetic']
runpy.run_path(path, run_name='__main__')
"""
            command = [sys.executable, "-c", code, str(root / "tools"), str(root / "tools" / "refine.py")]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert (d / "strokes_raw.json").read_text(encoding="utf-8") == source
        return json.loads((d / "strokes.json").read_text(encoding="utf-8"))


normal = run({})
gated = run({"set": {"2": {"contact_untrusted": True}}})
assert gated[1]["contact_untrusted"] is True
fields = ("knee", "knee3d", "open_min", "open_contact", "contact_h", "contact_fwd", "prep", "prep_trunc",
          "elbow", "vis", "cam_az", "leg_load", "leg_drive", "wrist_speed", "trunk_share", "turn", "knee2d_ok",
          "finish", "reach", "tilt", "lean", "stance", "serve_arm_straight", "serve_arm_conf", "bh_elbow_ok", "bh_elbow_conf", "bh_front_ok")
assert normal[1]["contact_h"] is not None and normal[1]["wrist_speed"] is not None and normal[1]["finish"] is not None
assert all(gated[1][k] is None for k in fields), {k: gated[1][k] for k in fields if gated[1][k] is not None}
assert gated[1]["frames"] == normal[1]["frames"] and gated[1]["contact"] == 90
assert run({"set": {"2": {"contact_untrusted": False}}})[1]["contact_h"] == normal[1]["contact_h"]
g = score_session(gated, False)[0]
assert g["n"] == 3 and all(m["n"] <= 2 and m["status"] == "資料不足" for m in g["metrics"].values())
print("refine contact gate OK")
# 不可信拍的時間不能限制下一拍的引拍搜尋；和直接刪掉它的搜尋界線相同。
without = run({"drop": [2]})
assert normal[2]["prep"] != without[1]["prep"], "合成資料必須確實測到上一拍界線"
assert gated[2]["prep"] == without[1]["prep"] and gated[2]["prep_trunc"] == without[1]["prep_trunc"]
# 原始資料已有旗標、或設定將它清除，都使用合併後的狀態。
flagged_raw = copy.deepcopy(raw); flagged_raw[1]["contact_untrusted"] = True
assert run({}, flagged_raw)[2]["prep"] == without[1]["prep"]
assert run({"set": {"2": {"contact_untrusted": False}}}, flagged_raw)[2]["prep"] == normal[2]["prep"]
# 每次從 raw 起算，off 不累加；drop 後仍以 raw 編號選取修正。
config = {"off": {"3": 5}, "drop": [1]}
a = run(config); b = run(config)
assert a == b and a[1]["id"] == 1 and a[1]["contact"] == 95 and abs(a[1]["t"] - (2.8 + 5 / 60)) < .001
print("refine previous-contact boundary / rerun OK")
# 發球的參考檢查也不能以錯誤時刻回傳判斷或信心值。
serve = copy.deepcopy(raw); serve[1]["kind"] = "SV"
assert run({}, serve)[1]["serve_arm_conf"] == 0.
assert run({"set": {"2": {"contact_untrusted": True}}}, serve)[1]["serve_arm_conf"] is None
print("refine untrusted serve check OK")

# 排除的拍不能改變整組膝角的2D/3D來源多數決。
knees = [dict(normal[0], knee3d=v) for v in (120., 125., None)] + [gated[1]]
assert score_session(knees, False)[0]["knee_src"] == "knee3d"
assert gated[1]["knee_warn"] is True and gated[1]["knee_warn_why"] == "contact"
print("refine untrusted knee source OK")

# 不可信拍連原始格診斷也不得呼叫量測；raw／set 的最終狀態優先。
marked = copy.deepcopy(raw)
marked[1]["frames"] = copy.deepcopy(marked[1]["frames"])
marked[1]["frames"][0][0][0] = .123
run({"set": {"2": {"contact_untrusted": True}}}, marked, forbid_marker=True)
marked[1]["contact_untrusted"] = True
run({}, marked, forbid_marker=True)
assert run({"set": {"2": {"contact_untrusted": False}}}, marked)[1]["contact_h"] is not None
assert [k for k in gated[1] if k != "contact_untrusted"] == list(normal[1])
print("refine 不可信拍提前跳過量測通過")
