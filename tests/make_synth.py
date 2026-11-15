# make_synth.py <out dir> [seconds=6] [WxH=1280x720] — synthetic test videos, no user footage: ffmpeg testsrc picture at 60 fps
# with a short 3 kHz click every 0.5 s (stand-in for ball hits). Writes land.mp4 and port.mp4 (same file with a 90° display
# rotation, as phones store portrait video). No people and no ball in the picture, so pose/ball outputs are all NaN.
import subprocess, sys
from pathlib import Path

out = Path(sys.argv[1]); sec = sys.argv[2] if len(sys.argv) > 2 else "6"; wh = sys.argv[3] if len(sys.argv) > 3 else "1280x720"
out.mkdir(parents=True, exist_ok=True)
run = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
run("-f", "lavfi", "-i", f"testsrc=s={wh}:r=60:d={sec}", "-f", "lavfi", "-i", f"aevalsrc='if(lt(mod(t,0.5),0.003),sin(2*PI*3000*t),0)':s=48000:d={sec}",
    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out / "land.mp4"))
run("-display_rotation", "90", "-i", str(out / "land.mp4"), "-c", "copy", str(out / "port.mp4"))  # rotation side data, not tags
print("wrote", out / "land.mp4", out / "port.mp4")
