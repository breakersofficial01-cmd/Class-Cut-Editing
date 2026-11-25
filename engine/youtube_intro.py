"""YouTube long-form intro edit (16:9, no text overlays).

Keeps original speed, length, resolution, fps and audio format so the rest of the
long video can be appended seamlessly. Adds jump-zoom punch-ins, a flash on slide
changes, and subtle synthesized SFX. Zoom must end at 1.0 for an invisible join.

Usage: python3 youtube_intro.py <config.json> <source.mp4> <out.mp4>
"""
import json
import subprocess
import sys
import wave

import numpy as np
from PIL import Image

cfg = json.load(open(sys.argv[1]))
SRC, OUT = sys.argv[2], sys.argv[3]
W, H, FPS = cfg["size"][0], cfg["size"][1], cfg["fps"]
SR = cfg["audio_rate"]
OUT_WAV = OUT + ".sfx.wav"


def smooth(a):
    a = min(max(a, 0.0), 1.0)
    return a * a * (3 - 2 * a)


def zoom_for(ts):
    for s, e, z0, z1, cx, cy in cfg["zooms"]:
        if s <= ts < e:
            return z0 + (z1 - z0) * smooth((ts - s) / (e - s)), cx, cy
    return 1.0, W / 2, H / 2


def crop_zoom(frame, z, cx, cy):
    if abs(z - 1.0) < 1e-3:
        return frame
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    im = Image.fromarray(frame).resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    return np.asarray(im)


# ---- picture ----
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-r", str(FPS), "-"], stdout=subprocess.PIPE)
tmp_v = OUT + ".v.mp4"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
                        "-preset", "slow", "-pix_fmt", "yuv420p", tmp_v], stdin=subprocess.PIPE)
n, j = W * H * 3, 0
while True:
    b = dec.stdout.read(n)
    if len(b) < n:
        break
    ts = j / FPS
    fr = np.frombuffer(b, np.uint8).reshape(H, W, 3)
    z, cx, cy = zoom_for(ts)
    out = crop_zoom(fr, z, cx, cy)
    for ft in cfg["flash_times"]:
        k = (ts - ft) * FPS
        if 0 <= k < 4:
            a = 0.45 - k * 0.11
            out = (out * (1 - a) + 255 * a).astype(np.uint8)
    enc.stdin.write(np.ascontiguousarray(out).tobytes())
    j += 1
enc.stdin.close()
enc.wait()
dur = j / FPS

# ---- SFX ----
rng = np.random.default_rng(7)


def env(m, attack, decay):
    t = np.arange(m) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def whoosh(d=0.4):
    m = int(SR * d)
    spec = np.fft.rfft(rng.standard_normal(m))
    f = np.fft.rfftfreq(m, 1 / SR)
    spec *= np.exp(-((f - 1800) / 1500) ** 2) + 0.15 * np.exp(-((f - 400) / 300) ** 2)
    s = np.fft.irfft(spec, m) * np.sin(np.linspace(0, np.pi, m)) ** 2
    return 0.9 * s / np.abs(s).max()


def pop():
    m = int(SR * 0.09)
    t = np.arange(m) / SR
    return 0.45 * np.sin(2 * np.pi * (700 + 900 * np.exp(-t * 60)) * t) * env(m, 0.001, 0.025)


def boom():
    m = int(SR * 0.5)
    t = np.arange(m) / SR
    return 0.9 * np.sin(2 * np.pi * (70 * t - 35 * t * t)) * env(m, 0.002, 0.15)


track = np.zeros(int(SR * (dur + 1)))
for name, at, gain in cfg["sfx"]:
    s = {"whoosh": whoosh, "pop": pop, "boom": boom}[name]()
    i = int(at * SR)
    track[i:i + len(s)] += gain * s[:max(0, len(track) - i)]
st = (np.repeat(np.clip(track, -1, 1)[:, None], 2, 1) * 32767).astype(np.int16)
with wave.open(OUT_WAV, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())

# ---- mux: original speech untouched in level/speed, SFX underneath, limiter for safety ----
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-i", SRC, "-i", OUT_WAV, "-filter_complex",
                f"[2:a]volume={cfg['sfx_volume']}[fx];[1:a][fx]amix=inputs=2:normalize=0:duration=first,"
                f"alimiter=limit=0.97[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", f"{dur:.3f}",
                "-movflags", "+faststart", OUT], check=True)
print(json.dumps({"frames": j, "sec": round(dur, 3)}))
