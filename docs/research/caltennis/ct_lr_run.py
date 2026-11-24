"""逐機以目前的正式姿態方法重算：ct_lr_run.py <cam> <參考 npz 目錄> <本機輸出目錄>。"""
import datetime
from contextlib import contextmanager
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from pose_full import METHOD
from proxy import video_filter
from ct_tri import CAL


def memory():
    # shortcut: 記憶體檢查只支援 macOS，移植研究重算入口時再補平台分支。
    s = subprocess.check_output(["vm_stat"], text=True)
    page = int(re.search(r"page size of (\d+)", s)[1])
    return sum(int(re.search(rf"Pages {k}:\s+(\d+)", s)[1]) for k in ("free", "inactive")) * page / 2**30


@contextmanager
def heavy_lock(lock):
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir()  # 已有人持鎖就失敗，不清理別人的鎖。
    try:
        yield
    finally:
        try:
            (lock / "owner.txt").unlink(missing_ok=True)
        except OSError as e:
            print(f"無法刪除重運算鎖 owner：{e}", file=sys.stderr)
        try:
            lock.rmdir()
        except OSError as e:
            print(f"無法移除重運算鎖目錄，請檢查後清理：{e}", file=sys.stderr)


def main():
    cam, refdir, outdir = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    assert cam in (1, 2, 3, 4)
    ref = np.load(refdir / f"c{cam}.npz")
    src = next((Path(CAL).parents[1] / Path(CAL).name).glob(f"*_X_{cam}_*.mp4"))
    h, m, s = map(int, src.stem.split("_")[3:6])
    ts = np.load(src.with_name(src.stem + "_timestamps.npy")) / 1000 + (h - 19) * 3600 + (m - 49) * 60 + s
    start = int(np.searchsorted(ts, ref["t"][0]))
    n = len(ref["t"])
    assert np.array_equal(ts[start:start + n], ref["t"]), "參考逐格時間不符"
    out = outdir / f"c{cam}"
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / "pose.npy").exists(), "已有姿態結果，先核對而非覆蓋"
    busy = subprocess.run(["pgrep", "-fl", "pose_full|prep.py|ball.py"], capture_output=True, text=True)
    if busy.returncode != 1:
        sys.exit("重運算尚未清空：" + busy.stdout + busy.stderr)
    lock = Path("testset/results/heavy.lock")
    with heavy_lock(lock):
        (lock / "owner.txt").write_text(f"#61 side / CalTennis c{cam} / {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()}\n", encoding="utf-8")
        low = memory()
        if low < 8: sys.exit("記憶體不足 8 GiB")
        t0 = time.monotonic()
        # 一個解碼格對應一個參考時間戳；只改時間基底，避免近 60 fps 的複製格使真值錯位。
        clip = out / "source.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(src), "-vf",
                        f"trim=start_frame={start}:end_frame={start + n},setpts=N/(60*TB)",
                        "-an", "-r", "60", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", str(clip)], check=True)
        proxy = out / "proxy.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(clip), "-vf", video_filter(1920, 1088),
                        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(proxy)], check=True)
        with (out / "pose.log").open("w", encoding="utf-8") as log:
            p = subprocess.Popen([sys.executable, "tools/pose_full.py", str(proxy), "models/pose_heavy.task",
                                  str(out / "pose.npy"), "1", str(clip)], stdout=log, stderr=subprocess.STDOUT)
            try:
                while p.poll() is None:
                    low = min(low, memory())
                    if low < 8: sys.exit("記憶體低於 8 GiB，停止重算")
                    try: p.wait(timeout=5)
                    except subprocess.TimeoutExpired: pass
            finally:
                if p.poll() is None:
                    p.terminate()
                    p.wait()
        assert p.returncode == 0, f"正式姿態失敗：{p.returncode}"
        P, W = np.load(out / "pose.npy"), np.load(out / "pose_world.npy")
        assert P.shape == W.shape == (n, 33, 3), (P.shape, W.shape, n)
        result = dict(cam=cam, method=METHOD, frames=n, seen=int(np.isfinite(P[:, 0, 0]).sum()),
                      seconds=round(time.monotonic() - t0, 2), min_free_inactive_gib=round(low, 2), start_frame=start)
        (out / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        np.save(out / "t.npy", ref["t"])
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
