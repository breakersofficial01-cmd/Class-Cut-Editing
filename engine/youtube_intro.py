"""YouTube long-form intro edit (16:9) in the Breaking School reference style.

Reference style (learned from the first 20 s of the channel's reference video):
  * two-tier lower captions: small white setup line + big bold punch line
    (yellow / green / red rotation, thick black outline, pop-in)
  * emoji-style stickers beside the punch line, red "?!" on question beats
  * warm light-leak transitions (yellow / red / orange) at every idea change
  * jump-zoom punch-ins (teacher, board, face close-up)
  * heavy edit on the hook, then calmer; zoom returns to 1.0 for an invisible join

Keeps original speed, length, resolution, fps and audio level/format so the rest of
the long video can be appended seamlessly.

Usage: python3 youtube_intro.py <config.json> <source.mp4> <out.mp4>
"""
import json
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

cfg = json.load(open(sys.argv[1]))
SRC, OUT = sys.argv[2], sys.argv[3]
W, H, FPS = cfg["size"][0], cfg["size"][1], cfg["fps"]
SR = cfg["audio_rate"]
CAP = cfg["caption_style"]
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
PUNCH_FONT = "/usr/share/fonts/truetype/noto/NotoSansBengali-Black.ttf"

COLORS = {  # ASS is &HBBGGRR&
    "yellow": "&H00F2FF&", "green": "&H2AFF3C&", "red": "&H2A2AFF&", "white": "&HFFFFFF&"}
LEAK_RGB = {"yellow": [(255, 235, 60), (255, 150, 0)],
            "red": [(255, 50, 25), (255, 140, 0)],
            "orange": [(255, 140, 20), (255, 60, 30)]}


def smooth(a):
    a = min(max(a, 0.0), 1.0)
    return a * a * (3 - 2 * a)


# ---------- zoom ----------
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
    return np.asarray(Image.fromarray(frame).resize((W, H), Image.LANCZOS,
                                                    box=(x0, y0, x0 + cw, y0 + ch)))


# ---------- light leaks ----------
YY, XX = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32) * 8


def leak_layer(p, kind):
    """p in [0,1] across the leak. Returns float RGB layer 0..1 (screen-blended)."""
    a = np.sin(np.pi * p) ** 1.1
    c1, c2 = (np.array(c, np.float32) / 255 for c in LEAK_RGB[kind])
    x1 = -0.4 * W + 1.8 * W * p
    x2 = 1.3 * W - 1.6 * W * p
    g1 = np.exp(-(((XX - x1) / (0.55 * W)) ** 2 + ((YY - 0.35 * H) / (0.7 * H)) ** 2))
    g2 = np.exp(-(((XX - x2) / (0.45 * W)) ** 2 + ((YY - 0.8 * H) / (0.5 * H)) ** 2))
    small = np.clip(g1[..., None] * c1 * 1.9 + g2[..., None] * c2 * 1.4, 0, 1) * a
    return np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                      np.float32) / 255


def apply_leaks(img, ts):
    for t0, kind in cfg["leaks"]:
        p = (ts - t0) / cfg["leak_sec"]
        if 0 <= p <= 1:
            f = img.astype(np.float32) / 255
            L = leak_layer(p, kind)
            img = ((1 - (1 - f) * (1 - L)) * 255).astype(np.uint8)
    return img


# ---------- stickers (color emoji) ----------
_ef = ImageFont.truetype(EMOJI_FONT, 109)
_pf = ImageFont.truetype(PUNCH_FONT, CAP["punch_size"])
_emoji_cache = {}


def emoji_img(ch):
    if ch not in _emoji_cache:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((80, 80), ch, font=_ef, embedded_color=True, anchor="mm")
        _emoji_cache[ch] = im.crop(im.getbbox())
    return _emoji_cache[ch]


def punch_width(text):
    return _pf.getlength(text)


stickers = []  # (start, end, emoji, x, y)
for c in cfg["captions"]:
    if c.get("sticker"):
        x = W / 2 + punch_width(c["punch"]) / 2 + 20 + CAP["sticker_size"] / 2
        stickers.append((c["punch_at"], c["end"], c["sticker"], min(x, W - 70), CAP["punch_y"] - 18))


def apply_stickers(img, ts):
    im = None
    for s, e, ch, x, y in stickers:
        if s <= ts < e:
            k = ts - s
            sc = 0.3 + 0.85 * smooth(k / 0.12) - 0.15 * smooth((k - 0.12) / 0.1)
            wob = 6 * np.sin(k * 7)
            em = emoji_img(ch)
            size = max(8, int(CAP["sticker_size"] * sc))
            em = em.resize((size, int(size * em.height / em.width)), Image.LANCZOS).rotate(wob, expand=True,
                                                                                         resample=Image.BICUBIC)
            if im is None:
                im = Image.fromarray(img)
            im.paste(em, (int(x - em.width / 2), int(y - em.height / 2)), em)
    return np.asarray(im) if im is not None else img


# ---------- captions (ASS) ----------
def t_ass(t):
    return f"0:{int(t // 60):02d}:{t % 60:05.2f}"


POP = r"\fscx35\fscy35\t(0,110,\fscx115\fscy115)\t(110,190,\fscx100\fscy100)"
ev = []
for c in cfg["captions"]:
    col = COLORS[c["color"]]
    ev.append(f"Dialogue: 1,{t_ass(c['setup_at'])},{t_ass(c['end'])},Setup,,0,0,0,,"
              rf"{{\an2\pos({W // 2},{CAP['setup_y']})\fad(90,0)\move({W // 2},{CAP['setup_y'] + 14},"
              rf"{W // 2},{CAP['setup_y']},0,120)}}{c['setup']}")
    ev.append(f"Dialogue: 2,{t_ass(c['punch_at'])},{t_ass(c['end'])},Punch,,0,0,0,,"
              rf"{{\an2\pos({W // 2},{CAP['punch_y'] + 40})\c{col}{POP}}}{c['punch']}")
    if c.get("bang"):
        x = int(W / 2 - punch_width(c["punch"]) / 2 - 55)
        ev.append(f"Dialogue: 3,{t_ass(c['punch_at'])},{t_ass(c['end'])},Bang,,0,0,0,,"
                  rf"{{\an2\pos({x},{CAP['punch_y'] + 48})\frz10{POP}}}?!")
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Setup,Noto Sans Bengali SemiBold,{CAP['setup_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,2,2,20,20,0,1
Style: Punch,Noto Sans Bengali Black,{CAP['punch_size']},&H0000F2FF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,5,4,2,20,20,0,1
Style: Bang,DejaVu Sans,{int(CAP['punch_size'] * 1.5)},&H002A2AFF,&H00FFFFFF,&H00FFFFFF,&H78000000,1,1,0,0,100,100,0,0,1,5,4,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n"
ASS = OUT + ".ass"
open(ASS, "w", encoding="utf-8").write(ass)

# ---------- picture ----------
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-r", str(FPS), "-"], stdout=subprocess.PIPE)
tmp_v = OUT + ".v.mp4"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12",
                        "-preset", "fast", "-pix_fmt", "yuv420p", tmp_v], stdin=subprocess.PIPE)
n, j = W * H * 3, 0
while True:
    b = dec.stdout.read(n)
    if len(b) < n:
        break
    ts = j / FPS
    fr = np.frombuffer(b, np.uint8).reshape(H, W, 3)
    z, cx, cy = zoom_for(ts)
    out = crop_zoom(fr, z, cx, cy)
    out = apply_leaks(out, ts)
    out = apply_stickers(out, ts)
    enc.stdin.write(np.ascontiguousarray(out).tobytes())
    j += 1
enc.stdin.close()
enc.wait()
dur = j / FPS

# ---------- SFX ----------
rng = np.random.default_rng(7)


def env(m, attack, decay):
    t = np.arange(m) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def whoosh(d=0.45):
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


hits = list(cfg["sfx"])
hits += [["whoosh", t0 - 0.12, 0.55] for t0, _ in cfg["leaks"]]
hits += [["pop", c["punch_at"], 0.55] for c in cfg["captions"]]
track = np.zeros(int(SR * (dur + 1)))
for name, at, gain in hits:
    s = {"whoosh": whoosh, "pop": pop, "boom": boom}[name]()
    i = max(0, int(at * SR))
    track[i:i + len(s)] += gain * s[:max(0, len(track) - i)]
WAV = OUT + ".sfx.wav"
st = (np.repeat(np.clip(track, -1, 1)[:, None], 2, 1) * 32767).astype(np.int16)
with wave.open(WAV, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())

# ---------- final: captions burned in, speech level untouched, SFX underneath ----------
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-i", SRC, "-i", WAV, "-filter_complex",
                f"[0:v]ass={ASS}[v];[2:a]volume={cfg['sfx_volume']}[fx];"
                f"[1:a][fx]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.97[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                "-ac", "2", "-t", f"{dur:.3f}", "-movflags", "+faststart", OUT], check=True)
print(json.dumps({"frames": j, "sec": round(dur, 3), "captions": len(cfg["captions"]),
                  "leaks": len(cfg["leaks"])}))
