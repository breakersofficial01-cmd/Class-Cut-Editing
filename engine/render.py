"""Class-Cut vertical short renderer.

Turns a 16:9 classroom MCQ clip into a 9:16 hook-first short:
cold-open challenge -> sped-up lesson with jump-zoom punch-ins -> 3-2-1 answer reveal.
Writes raw RGB frames to ffmpeg; text/audio are added afterwards (see build.sh).

Usage: python3 render.py <config.json> <out_video_no_text.mp4>
"""
import json
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1080, 1920, 30
YELLOW = (255, 214, 10)
GREEN = (34, 197, 94)

cfg = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
SRC_W, SRC_H = cfg["src_size"]
CROP_H = cfg["crop_bottom"]          # drop screen-recorder toolbar below this y
SPEED = cfg["speed"]
COLD = cfg["cold_open_sec"]
REVEAL = cfg["reveal_sec"]
MAIN = cfg["src_duration"] / SPEED
TOTAL = COLD + MAIN + REVEAL
WIN_Y = cfg["window_y"]
WIN_H = round(W * CROP_H / SRC_W)

freeze = np.array(Image.open(cfg["freeze_frame"]).convert("RGB"))


def smooth(a):
    return a * a * (3 - 2 * a)


def zoom_for(ts):
    for s, e, z0, z1, cx, cy in cfg["zooms"]:
        if s <= ts < e:
            return z0 + (z1 - z0) * smooth((ts - s) / (e - s)), cx, cy
    return 1.0, SRC_W / 2, CROP_H / 2


def crop_zoom(frame, z, cx, cy):
    cw, ch = SRC_W / z, CROP_H / z
    x0 = min(max(cx - cw / 2, 0), SRC_W - cw)
    y0 = min(max(cy - ch / 2, 0), CROP_H - ch)
    im = Image.fromarray(frame)
    return im.resize((W, WIN_H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def background(frame):
    bw = int(SRC_H * 9 / 16)
    x0 = (SRC_W - bw) // 2
    small = Image.fromarray(frame[:, x0:x0 + bw]).resize((54, 96), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(2.2))
    big = np.asarray(small.resize((W, H), Image.BILINEAR)).astype(np.float32)
    # darken + vertical vignette so text pops
    grad = np.linspace(0.42, 0.22, H)[:, None, None]
    grad = np.minimum(grad, np.linspace(0.22, 0.42, H)[:, None, None] + 0.1)
    return (big * grad).astype(np.uint8)


MASK = Image.new("L", (W, WIN_H), 0)
ImageDraw.Draw(MASK).rounded_rectangle([0, 0, W - 1, WIN_H - 1], 30, fill=255)


def highlight_answer(frame, strength):
    """Dim wrong options, paint correct option green. strength 0..1."""
    im = Image.fromarray(frame).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for r in cfg["wrong_rows"]:
        d.rectangle(r, fill=(0, 0, 0, int(150 * strength)))
    x0, y0, x1, y1 = cfg["answer_row"]
    d.rounded_rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], 14,
                        fill=GREEN + (int(80 * strength),),
                        outline=GREEN + (int(255 * strength),), width=8)
    return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))


def compose(src_frame, z, cx, cy, t, shake=0, flash=0.0):
    canvas = Image.fromarray(background(src_frame))
    win = crop_zoom(src_frame, z, cx, cy)
    dx = dy = 0
    if shake:
        rng = np.random.default_rng(int(t * 1000))
        dx, dy = (rng.integers(-shake, shake + 1, 2)).tolist()
    # yellow frame behind the window
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([-8 + dx, WIN_Y - 8 + dy, W + 7 + dx, WIN_Y + WIN_H + 7 + dy], 36, fill=YELLOW)
    canvas.paste(win, (dx, WIN_Y + dy), MASK)
    # progress bar (completion psychology)
    d.rectangle([0, 0, int(W * t / TOTAL), 11], fill=YELLOW)
    arr = np.asarray(canvas)
    if flash > 0:
        arr = (arr * (1 - flash) + 255 * flash).astype(np.uint8)
    return arr


def frames_from(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = SRC_W * SRC_H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(SRC_H, SRC_W, 3)


enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", OUT],
                       stdin=subprocess.PIPE)
fi = 0


def emit(arr):
    global fi
    enc.stdin.write(arr.tobytes())
    fi += 1


# 1) cold open: frozen clean question frame, push-in, flash + shake on entry
n_cold = round(COLD * FPS)
for i in range(n_cold):
    t = i / FPS
    a = i / max(n_cold - 1, 1)
    emit(compose(freeze, 1.0 + 0.07 * smooth(a), 640, 340, t,
                 shake=10 if i < 6 else 0, flash=max(0, 0.85 - i * 0.28)))

# 2) main lesson, sped up
sped = cfg["sped_video"]
for j, fr in enumerate(frames_from(sped)):
    t = COLD + j / FPS
    ts = (j / FPS) * SPEED
    z, cx, cy = zoom_for(ts)
    flash = 0.0
    for ft in cfg["flash_src_times"]:
        k = (ts - ft) * FPS / SPEED
        if 0 <= k < 4:
            flash = max(flash, 0.6 - k * 0.15)
    emit(compose(fr, z, cx, cy, t, flash=flash))

# 3) reveal: countdown on clean frame, then green answer + shake
start = fi / FPS
n_rev = round(REVEAL * FPS)
hit = cfg["reveal_hit_sec"]
for i in range(n_rev):
    t = start + i / FPS
    rt = i / FPS
    if rt < hit:
        arr = compose(freeze, 1.0 + 0.04 * smooth(rt / hit), 640, 400, t)
    else:
        s = min(1.0, (rt - hit) / 0.2)
        fr = highlight_answer(freeze, s)
        k = (rt - hit) * FPS
        z = 1.04 + 0.05 * smooth(min(1, (rt - hit) / 0.5))
        arr = compose(fr, z, 640, 470, t, shake=12 if k < 6 else 0,
                      flash=max(0, 0.7 - k * 0.2))
    emit(arr)

enc.stdin.close()
enc.wait()
print(json.dumps({"frames": fi, "total_sec": round(fi / FPS, 3), "main_start": COLD,
                  "reveal_start": round(start, 3)}))
