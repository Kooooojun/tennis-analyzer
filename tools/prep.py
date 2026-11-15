# usage: python tools/prep.py <session> [people]   e.g. python tools/prep.py 2026-11-05   (people = max people to track, default 2)
# For every video in videos/<session>/: 60fps proxy (540x960 portrait, 960x540 landscape), high-passed audio, pose (one file per tracked person), hit sounds, ball track, hit events (sound + ball).
# Wrist motion per hit (match.py) runs in candidates.py, once the racket hand of each person is known.
# Re-running skips finished steps, so it is safe to resume after an interruption; a step re-runs when its output is missing or an input is newer.
# Every ffmpeg output is written to <name>.part first and renamed, so a killed run never leaves a half file that looks finished.
import json, os, subprocess, sys
from functools import lru_cache
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "tools"))  # run with -I: the script's folder is not on sys.path
from platform_util import h264_args, need_ffmpeg, replace, stale, unlink, utf8_stdout, venv_python, write_text

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
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate:stream_side_data=rotation:stream_tags=rotate", "-of", "json", str(v)],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        s = json.loads(r.stdout)["streams"][0]; w, h = int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError, TypeError):
        sys.exit(f"ffprobe could not read {v}: {r.stderr.strip() or 'no video stream'}")
    rot = next((d["rotation"] for d in s.get("side_data_list", []) if "rotation" in d), s.get("tags", {}).get("rotate", 0))
    if abs(int(float(rot))) % 360 in (90, 270): w, h = h, w
    n, _, d = s.get("avg_frame_rate", "0/0").partition("/")  # avg handles variable frame rate
    try:
        fps = int(float(n) / float(d or 1) + 0.5) if float(n) > 0 and float(d or 1) > 0 else None
    except ValueError:
        fps = None
    return w, h, fps


@lru_cache(None)
def gpu():
    import torch  # ball.py picks mps > cuda > cpu the same way
    return torch.backends.mps.is_available() or torch.cuda.is_available()


def ball_note(proxy):
    """On CPU ball.py is ~60x slower than real time: say so before it starts. Not in ball.py, which another change owns."""
    if gpu(): return
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(proxy)], capture_output=True, text=True)
    try: secs = float(r.stdout)
    except ValueError: return
    print(f"警告：沒有 GPU，球追蹤用 CPU 跑（約 {CPU_S_PER_FRAME:.1f} 秒/格）：這段 {secs:.0f} 秒影片預估 {secs * 60 * CPU_S_PER_FRAME / 60:.0f} 分鐘"
          "（推算，不是在這台電腦實測；實際 ms/frame 看 ball.log）", file=sys.stderr, flush=True)


def main(argv):
    if not argv or not argv[0] or ".." in argv[0] or "/" in argv[0] or "\\" in argv[0]: usage()
    S = argv[0]
    try:
        N = int(argv[1]) if len(argv) > 1 else 2
    except ValueError:
        N = 0
    if N < 1: sys.exit(f"people must be a whole number >= 1, got {argv[1]}")
    src = R / "videos" / S
    if not src.is_dir(): usage()
    need_ffmpeg()
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
    enc = h264_args("2500k", 23)
    for V, n in zip(vids, names):
        D = W / n; D.mkdir(parents=True, exist_ok=True)
        w, h, fps = probe(V)
        print(f"== {n}", flush=True)
        # the proxy below is always 60 fps, so a 30 fps source becomes duplicated frames
        if fps: write_text(D / "src_fps.txt", f"{fps}\n")
        else: delete(D / "src_fps.txt")  # unreadable: no stale value from an earlier video
        if fps and fps < 50: print(f"警告：{n} 來源 {fps} fps，proxy 會補成 60 fps（重複影格），速度類數字（手速、準備時間）沒驗證過", file=sys.stderr)
        # shortcut: assumes 16:9 sources (phone video); other ratios get stretched, as before
        if stale(D / "proxy.mp4", V):
            ffmpeg(V, D / "proxy.mp4", "-an", "-vf", f"scale={'960:540' if w > h else '540:960'},fps=60", *enc, "-g", "30", "-f", "mp4")
        if stale(D / "audio_hp.f32", V): ffmpeg(V, D / "audio_hp.f32", "-vn", "-ac", "1", "-ar", "16000", "-af", "highpass=f=1500", "-f", "f32le")
        if stale(D / "audio.f32", V): ffmpeg(V, D / "audio.f32", "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le")
        # a different people count means a different pose run; no people.txt (older work dir) = trust what is there
        pt, pose = D / "people.txt", D / "pose.npy"
        if pt.is_file() and pose.is_file() and pt.read_text(encoding="utf-8").strip() != str(N): delete(pose)
        for t in D.glob("pose*_t*.npy"):  # extra tracks from an earlier, larger run
            k = t.stem.rsplit("_t", 1)[1]
            if k.isdigit() and int(k) >= N: delete(t)
        if stale(pose, D / "proxy.mp4"): py("pose_full.py", D / "proxy.mp4", R / "models" / "pose_heavy.task", pose, N, log=D / "pose.log")
        write_text(pt, f"{N}\n")
        if stale(D / "sounds.npy", D / "audio_hp.f32", D / "audio.f32"): py("hits.py", D / "audio_hp.f32", D / "audio.f32", D / "sounds.npy")
        if stale(D / "ball.npy", D / "proxy.mp4"):
            ball_note(D / "proxy.mp4")
            py("ball.py", D / "proxy.mp4", D / "ball.npy", out=D / "ball.log")
        if stale(D / "events.npy", D / "sounds.npy", D / "ball.npy", pose):
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
    main(sys.argv[1:])
