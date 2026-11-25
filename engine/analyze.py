"""Look at a clip before writing its edit config.

Usage: python3 -I engine/analyze.py <video> <out_dir>
Writes:
  contact.png   - 1 frame/sec with timestamps (Read it to see what happens when)
  grid_<t>.png  - full-res frames with a 1280x720 design-coordinate grid (pick zoom centers from these)
  report.json   - duration, size, fps, scene cuts (slide changes), loudness
"""
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)


def run(args):
    return subprocess.run(args, capture_output=True, text=True).stderr


probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,"
                                   "width,height,r_frame_rate", "-of", "json", src],
                                  capture_output=True, text=True).stdout)
dur = float(probe["format"]["duration"])
v = next(s for s in probe["streams"] if s["codec_type"] == "video")

# contact sheet, 1 fps, timestamps burned in
cols = 6
rows = int(dur) // cols + 1
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                "fps=1,scale=480:-2,drawtext=text='%{pts\\:gmtime\\:0\\:%M\\\\\\:%S}':x=6:y=6:fontsize=28:"
                f"fontcolor=yellow:box=1:boxcolor=black,tile={cols}x{rows}", "-frames:v", "1",
                f"{out}/contact.png"])

# scene cuts (slide changes / camera cuts)
log = run(["ffmpeg", "-hide_banner", "-i", src, "-vf", "select='gt(scene,0.12)',metadata=print", "-f", "null", "-"])
cuts = [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", log)]

# loudness
loud = run(["ffmpeg", "-hide_banner", "-i", src, "-af", "ebur128=peak=true", "-f", "null", "-"])
lufs = re.findall(r"I:\s+(-?[0-9.]+) LUFS", loud)

# design-grid frames at start, each cut, and middle
times = sorted({0.5, dur / 2, *[c + 0.4 for c in cuts[:6]]})
for t in times:
    p = f"{out}/grid_{t:.1f}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", src, "-frames:v", "1",
                    "-vf", "scale=1280:720", p])
    im = Image.open(p).convert("RGB")
    d = ImageDraw.Draw(im)
    for y in range(0, 720, 40):
        d.line([(0, y), (1280, y)], fill=(0, 255, 255))
        d.text((2, y), str(y), fill=(0, 255, 255))
    for x in range(0, 1280, 80):
        d.line([(x, 0), (x, 720)], fill=(255, 0, 255))
        d.text((x + 2, 2), str(x), fill=(255, 0, 255))
    im.save(p)

rep = {"duration": round(dur, 3), "size": [v["width"], v["height"]], "fps": v["r_frame_rate"],
       "scene_cuts": cuts, "integrated_lufs": float(lufs[-1]) if lufs else None,
       "grid_frames": [f"grid_{t:.1f}.png" for t in times]}
json.dump(rep, open(f"{out}/report.json", "w"), indent=2)
print(json.dumps(rep, indent=2))
