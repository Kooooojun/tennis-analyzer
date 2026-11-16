# usage: python tools/prep.py <session> [people]   e.g. python tools/prep.py 2026-11-05   (people = max people to track, default 2)
# For every video in videos/<session>/: 60fps proxy (540x960 portrait, 960x540 landscape), high-passed audio, pose (one file per tracked person), hit sounds, ball track, hit events (sound + ball).
# Wrist motion per hit (match.py) runs in candidates.py, once the racket hand of each person is known.
# Re-running skips finished steps, so it is safe to resume after an interruption; a step re-runs when its output is missing or an input is newer.
# Every ffmpeg output is written to <name>.part first and renamed, so a killed run never leaves a half file that looks finished.
import json, math, os, subprocess, sys, tempfile
from functools import lru_cache
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "tools"))  # run with -I: the script's folder is not on sys.path
from platform_util import h264_args, need_ffmpeg, replace, stale, unlink, utf8_stdout, venv_python, write_text
from proxy import layout, video_filter, needs_padding

EXTS = {".mov", ".mp4", ".m4v"}
MAX_PATH = 240  # Windows MAX_PATH is 260; leave room for temp names
CPU_S_PER_FRAME = 1.1  # ball.py on CPU: 1.0-1.2 s/frame measured on 2-4 vCPU CI runners (960x540)


def usage():
    sys.exit("usage: python tools/prep.py <session> [people]  (folder under videos/)")


def run(cmd, log=None, out=None):
    """log = file for stderr, out = file for stdout (or subprocess.DEVNULL). A failing step stops prep with its exit code."""
    f = open(log or out, "w", encoding="utf-8") if log or isinstance(out, Path) else None
    try:
        rc = subprocess.run(cmd, stderr=f if log else None, stdout=f if isinstance(out, Path) else out).returncode
    finally:
        if f: f.close()
    if rc: print(f"failed ({rc}): {' '.join(map(str, cmd))}" + (f"  (see {f.name})" if f else ""), file=sys.stderr); sys.exit(rc)


def py(script, *args, **kw):
    run([sys.executable, "-X", "utf8", "-I", str(R / "tools" / script), *map(str, args)], **kw)


def ffmpeg(src, out, *args):
    part = out.with_name(out.name + ".part")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *args, str(part)])
    replace(part, out)


def delete(p):
    try:
        unlink(p)
    except PermissionError:
        sys.exit(f"cannot delete {p}: another program has it open (close it and re-run)")


def probe(v):
    """(width, height) after rotation, and source fps (int, or None when unreadable)."""
    w, h, r = probe_rate(v)
    return w, h, int(r + 0.5) if r else None


def probe_rate(v):
    """(width, height) after rotation, and the exact average fps (float, or None when unreadable). pose_full uses it too:
    ffmpeg is the decoder, so its view of the source is the one that counts."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate:stream_side_data=rotation:stream_tags=rotate", "-of", "json", str(v)],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        s = json.loads(r.stdout)["streams"][0]; w, h = int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError, TypeError):
        sys.exit(f"ffprobe could not read {v}: {r.stderr.strip() or 'no video stream'}")
    rot = next((d["rotation"] for d in s.get("side_data_list", []) if "rotation" in d), s.get("tags", {}).get("rotate", 0))
    try:
        if abs(int(float(rot))) % 360 in (90, 270): w, h = h, w
    except ValueError:
        sys.exit(f"ffprobe gave an unreadable rotation for {v}: {rot!r}")
    n, _, d = s.get("avg_frame_rate", "0/0").partition("/")  # avg handles variable frame rate
    try:
        fps = float(n) / float(d or 1) if float(n) > 0 and float(d or 1) > 0 else None
    except ValueError:
        fps = None
    return w, h, fps


def finite_seconds(value):
    try:
        seconds = float(value)
        return seconds if math.isfinite(seconds) else None
    except (TypeError, ValueError):
        return None


@lru_cache(None)
def gpu():
    import torch  # ball.py picks mps > cuda > cpu the same way
    return torch.backends.mps.is_available() or torch.cuda.is_available()


def ball_note(pw, ph, frames):
    """用與視窗相交的原批次格數估算 CPU 推論時間。"""
    if not frames or gpu(): return
    tiles = math.ceil(ph / (pw * 9 / 16))  # ball.py runs one 16:9 crop per tile: portrait 540x960 is 4 crops a frame
    print(f"警告：沒有 GPU，球追蹤只算候選附近的批次（橫式約 {CPU_S_PER_FRAME:.1f} 秒/格，直式約 4 倍）：{frames} 格預估 {frames * CPU_S_PER_FRAME * tiles / 60:.0f} 分鐘"
          "（推算，另需整片解碼；不是在這台電腦實測；實際 ms/frame 看 ball.log）", file=sys.stderr, flush=True)


def main(argv):
    if not argv or argv[0] in ("", ".") or ".." in argv[0] or "/" in argv[0] or "\\" in argv[0]: usage()
    S = argv[0]
    try:
        N = int(argv[1]) if len(argv) > 1 else 2
    except ValueError:
        N = 0
    if N < 1: sys.exit(f"people must be a whole number >= 1, got {argv[1]}")
    src = R / "videos" / S
    if not src.is_dir(): usage()
    need_ffmpeg()
    from pose_full import METHOD as POSE_METHOD  # here, not at the top: pose_full needs numpy, which only the venv has
    # dotfiles (macOS ._A.mp4 sidecars) skipped like the old zsh glob; sorted by name ignoring case (as that glob did), ties broken by exact name so the order never depends on the OS
    vids = sorted((v for v in src.iterdir() if v.is_file() and v.suffix.lower() in EXTS and not v.name.startswith(".")), key=lambda v: (v.name.casefold(), v.name))
    if not vids: sys.exit(f"no videos in videos/{S}")
    names = [v.stem for v in vids]
    folded = [n.casefold() for n in names]  # work/<S>/A and work/<S>/a are one folder on macOS and Windows
    dup = sorted({n for n, f in zip(names, folded) if folded.count(f) > 1})
    if dup: sys.exit(f"same name, different extension in videos/{S}: {', '.join(dup)} (rename one)")
    W = R / "work" / S
    longest = max(len(str(W / n / f"pose_world_t{max(N - 1, 1)}.npy.part")) for n in names)
    if os.name == "nt" and longest > MAX_PATH:
        sys.exit(f"output paths would be {longest} characters (Windows limit ~{MAX_PATH}): shorten the session or video names, or clone to a shorter folder such as C:\\dev\\tennis-analyzer")
    info = [probe(V) for V in vids]  # every video readable before any work starts
    enc = h264_args("2500k", 23)
    for V, n, (w, h, fps) in zip(vids, names, info):
        D = W / n; D.mkdir(parents=True, exist_ok=True)
        print(f"== {n}", flush=True)
        # the proxy below is always 60 fps (duplicated frames for a 30 fps source); pose runs at the source rate and is interpolated
        if fps: write_text(D / "src_fps.txt", f"{fps}\n")
        else: delete(D / "src_fps.txt")  # unreadable: no stale value from an earlier video
        if fps and fps < 50: print(f"警告：{n} 來源 {fps} fps，proxy 會補成 60 fps（重複影格；姿態用原始 fps 跑再內插），速度類數字（手速、準備時間）沒驗證過", file=sys.stderr)
        pw, ph, *_ = layout(w, h)
        filt = video_filter(w, h)
        padded = needs_padding(w, h)
        pf = D / "proxy_filter.txt"  # 僅超出 16:9 容許範圍時記錄，舊拉伸 proxy 缺記錄時自動重建。
        if padded:
            g = math.gcd(w, h)
            print(f"來源比例 {w // g}:{h // g}，等比例縮放後補黑邊成 16:9", file=sys.stderr)
        changed = padded and (not pf.is_file() or pf.read_text(encoding="utf-8").strip() != filt)
        if stale(D / "proxy.mp4", V) or changed:
            ffmpeg(V, D / "proxy.mp4", "-an", "-vf", f"{filt},fps=60", *enc, "-g", "30", "-f", "mp4")
            if padded: write_text(pf, filt + "\n")
            else: delete(pf)
        if any(stale(D / name, V) for name in ("audio_hp.f32", "audio.f32")):
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration:format=duration", "-of", "json", str(V)],
                               capture_output=True, text=True, encoding="utf-8")
            try:
                audio_info = json.loads(r.stdout)
                streams = audio_info["streams"]
                audio_durations = [finite_seconds(s.get("duration")) for s in streams if s.get("codec_type") == "audio"]
                silent = not any(d is None or d > 0 for d in audio_durations)
                if silent:
                    video = next(s for s in streams if s.get("codec_type") == "video")
                    duration = next(d for d in map(finite_seconds, (video.get("duration"), audio_info.get("format", {}).get("duration")))
                                    if d is not None and d > 0)
            except (ValueError, KeyError, TypeError, StopIteration):
                sys.exit(f"ffprobe could not read audio/duration for {V}: {r.stderr.strip() or 'invalid streams or duration'}")
            audio_src = []
            if silent:
                print("這支影片沒有聲音：擊球偵測要靠聲音，這支可能抓不到任何擊球", file=sys.stderr)
                audio_src = ["-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-map", "1:a:0", "-t", str(duration)]
            for name, filt in (("audio_hp.f32", ["-af", "highpass=f=1500"]), ("audio.f32", [])):
                if stale(D / name, V): ffmpeg(V, D / name, *audio_src, "-vn", "-ac", "1", "-ar", "16000", *filt, "-f", "f32le")
        # a different people count means a different pose run; no people.txt (older work dir) = trust what is there
        pt, pose = D / "people.txt", D / "pose.npy"
        if pt.is_file() and pose.is_file() and pt.read_text(encoding="utf-8").strip() != str(N): delete(pose)
        pm = D / "pose_method.txt"  # pose from an older algorithm (no file = before versions existed) is redone
        if pose.is_file() and (not pm.is_file() or pm.read_text(encoding="utf-8").strip() != POSE_METHOD):
            print(f"{n}: pose 是舊方法算的（pose_method {POSE_METHOD}），重算", flush=True); delete(pose)
        for t in D.glob("pose*_t*.npy"):  # extra tracks from an earlier, larger run
            k = t.stem.rsplit("_t", 1)[1]
            if k.isdigit() and int(k) >= N: delete(t)
        if stale(pose, D / "proxy.mp4"): py("pose_full.py", D / "proxy.mp4", R / "models" / "pose_heavy.task", pose, N, V, log=D / "pose.log")
        elif not pt.is_file(): print("舊 work 目錄沒有人數紀錄，沿用現有姿態；要重跑請刪 pose.npy", file=sys.stderr)
        write_text(pt, f"{N}\n"); write_text(pm, f"{POSE_METHOD}\n")
        missing_world = [p.name for p in sorted(D.glob("pose*.npy"))
                         if (p == pose or (p.stem.startswith("pose_t") and p.stem[6:].isdigit()))
                         and not p.with_name(p.name.replace("pose", "pose_world", 1)).is_file()]
        note = D / "pose_world_missing.txt"
        if missing_world:
            record = "\n".join(missing_world) + "\n"
            if not note.is_file() or note.read_text(encoding="utf-8") != record:
                print("沒有 3D 姿態，膝角只有 2D、拍種多半是 ?；要補請刪 pose.npy 重跑（很慢）", file=sys.stderr)
                write_text(note, record)
        else: delete(note)
        if stale(D / "sounds.npy", D / "audio_hp.f32", D / "audio.f32"): py("hits.py", D / "audio_hp.f32", D / "audio.f32", D / "sounds.npy")
        poses = [pose, *sorted(D.glob("pose_t*.npy"))]
        if stale(D / "ball.npy", D / "proxy.mp4", D / "sounds.npy", *poses):
            import cv2, numpy as np
            from ball import BATCH, window_mask
            from common import size
            from events import ball_windows, hands
            cap = cv2.VideoCapture(str(D / "proxy.mp4"))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
            w, h = size(D / "proxy.mp4")
            hand, who = hands([np.load(p).astype(np.float64) for p in poses], w / h, who=True)
            windows = ball_windows(np.load(D / "sounds.npy").reshape(-1, 4), hand, who, n)
            mask = window_mask(windows, n)
            frames = sum(min(BATCH, n - i) for i in range(0, n, BATCH) if mask[i:i + BATCH].any())
            ball_note(pw, ph, frames)
            with tempfile.TemporaryDirectory(prefix="ball_windows_") as tmp:
                wp = Path(tmp) / "windows.npy"; np.save(wp, windows)
                py("ball.py", D / "proxy.mp4", D / "ball.npy", "--windows", wp, out=D / "ball.log")
        if stale(D / "events.npy", D / "sounds.npy", D / "ball.npy", *poses):
            py("events.py", D / "sounds.npy", D / "ball.npy", pose, D / "events.npy", out=subprocess.DEVNULL)
    write_text(W / "videos.json", json.dumps(names) + "\n")
    print(f"ready: {len(names)} videos -> work/{S}")


if __name__ == "__main__":
    utf8_stdout()
    venv = venv_python(R)
    if Path(sys.prefix).resolve() != (R / ".venv").resolve():
        # not the venv: re-run under it. subprocess, not os.exec*: on Windows exec returns to the caller before the child finishes
        if not venv.is_file(): sys.exit("run python setup.py first")
        sys.exit(subprocess.run([str(venv), "-X", "utf8", __file__, *sys.argv[1:]]).returncode)
    try:
        main(sys.argv[1:])
    except PermissionError as e:  # Windows: another program (player, Defender, indexer) has the file open
        sys.exit(f"cannot write {e.filename}: another program may have it open (close it and re-run)")
