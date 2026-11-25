"""YouTube long-form intro edit (16:9) in the Breaking School reference style.

Reference style (learned from the first 20 s of the channel's reference video):
  TEXT
  * setup line (small, white) wipes in left -> right
  * key words in the setup can get a red marker-highlight sweep with yellow text
  * punch line (big, yellow / green / red, thick outline) slides UP from behind an
    invisible baseline, slight overshoot
  * color-emoji sticker pops in beside the punch line and floats gently
  * red "?!" snaps in with a rotation on question beats
  SOUND (synthesized to match the reference's spectrogram)
  * sparkle / twinkle burst (5 bright chime hits ~0.1 s apart) on light-leak transitions
  * airy swish on setup lines, rising swoosh + soft thump on punch lines
  * bubble pop on stickers, marker squeak on highlights, "bip-bip" alert + boom on "?!"
  PICTURE
  * warm light-leak transitions (yellow / red / orange) at each idea change
  * jump-zoom punch-ins; zoom returns to 1.0 before the end for an invisible join

Keeps original speed, length, resolution, fps and speech level so the rest of the long
video can be appended seamlessly.

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
NOTO = "/usr/share/fonts/truetype/noto/"
EMOJI_FONT = NOTO + "NotoColorEmoji.ttf"
LIBASS_TO_PIL = 0.75          # libass renders Noto Bengali at ~0.75x Pillow's size (calibrated)

COLORS = {  # ASS is &HBBGGRR&
    "yellow": "&H00F2FF&", "green": "&H2AFF3C&", "red": "&H2A2AFF&", "white": "&HFFFFFF&"}
LEAK_RGB = {"yellow": [(255, 235, 60), (255, 150, 0)],
            "red": [(255, 50, 25), (255, 140, 0)],
            "orange": [(255, 140, 20), (255, 60, 30)]}
SETUP_Y = CAP["setup_y"]            # bottom anchor of setup line
PUNCH_Y = CAP["punch_y"]            # bottom anchor of punch line

_setup_font = ImageFont.truetype(NOTO + "NotoSansBengali-SemiBold.ttf", CAP["setup_size"] * LIBASS_TO_PIL)
_punch_font = ImageFont.truetype(NOTO + "NotoSansBengali-Black.ttf", CAP["punch_size"] * LIBASS_TO_PIL)


def width(font, text):
    return font.getlength(text)


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
            img = ((1 - (1 - f) * (1 - leak_layer(p, kind))) * 255).astype(np.uint8)
    return img


# ---------- stickers ----------
_ef = ImageFont.truetype(EMOJI_FONT, 109)
_emoji_cache = {}


def emoji_img(ch):
    if ch not in _emoji_cache:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((80, 80), ch, font=_ef, embedded_color=True, anchor="mm")
        _emoji_cache[ch] = im.crop(im.getbbox())
    return _emoji_cache[ch]


stickers = []  # (start, end, emoji, x, y)
for c in cfg["captions"]:
    if c.get("sticker"):
        x = W / 2 + width(_punch_font, c["punch"]) / 2 + 18 + CAP["sticker_size"] / 2
        c["_sticker_at"] = c["punch_at"] + 0.05
        stickers.append((c["_sticker_at"], c["end"], c["sticker"], min(x, W - 60), PUNCH_Y - 70))


def apply_stickers(img, ts):
    im = None
    for s, e, ch, x, y in stickers:
        if s <= ts < e:
            k = ts - s
            # elastic pop: 0 -> 1.25 -> 0.92 -> 1.0, then gentle float
            if k < 0.10:
                sc = 1.25 * smooth(k / 0.10)
            elif k < 0.18:
                sc = 1.25 - 0.33 * smooth((k - 0.10) / 0.08)
            else:
                sc = 0.92 + 0.08 * smooth((k - 0.18) / 0.08)
            rot = -18 * (1 - smooth(k / 0.18)) + 5 * np.sin(k * 5.5)
            bob = 4 * np.sin(k * 4.0)
            em = emoji_img(ch)
            size = max(6, int(CAP["sticker_size"] * sc))
            em = em.resize((size, max(6, int(size * em.height / em.width))), Image.LANCZOS)
            em = em.rotate(rot, expand=True, resample=Image.BICUBIC)
            if im is None:
                im = Image.fromarray(img)
            im.paste(em, (int(x - em.width / 2), int(y + bob - em.height / 2)), em)
    return np.asarray(im) if im is not None else img


# ---------- captions (ASS) ----------
def t_ass(t):
    return f"0:{int(t // 60):02d}:{t % 60:05.2f}"


ev = []
for c in cfg["captions"]:
    col = COLORS[c["color"]]
    sw = width(_setup_font, c["setup"])
    sx0, sx1 = W / 2 - sw / 2, W / 2 + sw / 2
    setup_text = c["setup"]
    sa, pa, end = c["setup_at"], c["punch_at"], c["end"]

    # marker highlight sweep behind key words of the setup line
    if c.get("mark") and c["mark"] in setup_text:
        pre = setup_text[:setup_text.index(c["mark"])]
        mx0 = sx0 + width(_setup_font, pre) - 6
        mx1 = mx0 + width(_setup_font, c["mark"]) + 12
        my0, my1 = SETUP_Y - 50, SETUP_Y - 6
        mt = int(c.get("mark_delay", 0.35) * 1000)
        ev.append(f"Dialogue: 0,{t_ass(sa)},{t_ass(end)},Mark,,0,0,0,,"
                  rf"{{\an7\pos(0,0)\clip({mx0:.0f},{my0},{mx0:.0f},{my1})"
                  rf"\t({mt},{mt + 260},\clip({mx0:.0f},{my0},{mx1:.0f},{my1}))\p1}}"
                  f"m {mx0:.0f} {my0 + 4} l {mx1:.0f} {my0} {mx1 - 4:.0f} {my1} {mx0 + 3:.0f} {my1 - 2}")
        setup_text = setup_text.replace(c["mark"], r"{\c&H00F2FF&}" + c["mark"] + r"{\c&HFFFFFF&}")
        c["_mark_at"] = sa + mt / 1000

    # setup: left->right wipe reveal
    ev.append(f"Dialogue: 1,{t_ass(sa)},{t_ass(end)},Setup,,0,0,0,,"
              rf"{{\an2\pos({W // 2},{SETUP_Y})\clip({sx0 - 12:.0f},0,{sx0 - 12:.0f},{H})"
              rf"\t(0,300,\clip({sx0 - 12:.0f},0,{sx1 + 12:.0f},{H}))}}{setup_text}")

    # punch: slides up from behind an invisible baseline, with overshoot
    cl = rf"\clip(0,0,{W},{PUNCH_Y + 8})"
    ev.append(f"Dialogue: 2,{t_ass(pa)},{t_ass(pa + 0.14)},Punch,,0,0,0,,"
              rf"{{\an2\move({W // 2},{PUNCH_Y + 95},{W // 2},{PUNCH_Y - 8},0,140){cl}\c{col}}}{c['punch']}")
    ev.append(f"Dialogue: 2,{t_ass(pa + 0.14)},{t_ass(end)},Punch,,0,0,0,,"
              rf"{{\an2\move({W // 2},{PUNCH_Y - 8},{W // 2},{PUNCH_Y},0,90){cl}\c{col}}}{c['punch']}")

    if c.get("bang"):
        x = int(W / 2 - width(_punch_font, c["punch"]) / 2 - 62)
        ev.append(f"Dialogue: 3,{t_ass(pa + 0.05)},{t_ass(end)},Bang,,0,0,0,,"
                  rf"{{\an2\pos({x},{PUNCH_Y + 10})\frz-35\fscx10\fscy10"
                  rf"\t(0,130,\frz14\fscx125\fscy125)\t(130,230,\frz8\fscx100\fscy100)}}?!")
        c["_bang_at"] = pa + 0.05

ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Setup,Noto Sans Bengali SemiBold,{CAP['setup_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H50000000,0,0,0,0,100,100,0,0,1,2.5,3,2,20,20,0,1
Style: Punch,Noto Sans Bengali Black,{CAP['punch_size']},&H0000F2FF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,5,5,2,20,20,0,1
Style: Bang,DejaVu Sans,{int(CAP['punch_size'] * 1.6)},&H002A2AFF,&H00FFFFFF,&H00FFFFFF,&H64000000,1,1,0,0,100,100,0,0,1,5,4,2,0,0,0,1
Style: Mark,Arial,20,&H202A2AFF,&H202A2AFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

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

# ---------- SFX kit ----------
rng = np.random.default_rng(7)


def env(m, attack, decay):
    t = np.arange(m) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def band_noise(m, lo, hi):
    spec = np.fft.rfft(rng.standard_normal(m))
    f = np.fft.rfftfreq(m, 1 / SR)
    spec *= ((f > lo) & (f < hi)) * 1.0
    s = np.fft.irfft(spec, m)
    return s / (np.abs(s).max() + 1e-9)


def sweep_noise(d, f0, f1, q=0.35):
    """Noise through a moving band-pass (STFT-ish, 20 ms blocks)."""
    m = int(SR * d)
    out = np.zeros(m)
    blk = int(SR * 0.02)
    src = rng.standard_normal(m + blk)
    for i in range(0, m, blk):
        p = i / m
        fc = f0 * (f1 / f0) ** p
        seg = src[i:i + 2 * blk]
        sp = np.fft.rfft(seg * np.hanning(len(seg)))
        fr = np.fft.rfftfreq(len(seg), 1 / SR)
        sp *= np.exp(-((np.log(fr + 1) - np.log(fc)) / q) ** 2)
        y = np.fft.irfft(sp, len(seg))
        out[i:i + len(y)] += y[:max(0, m - i)]
    return out / (np.abs(out).max() + 1e-9)


def swish():                       # light, airy - setup line wipe
    m = int(SR * 0.22)
    s = sweep_noise(0.22, 2500, 7000) * np.sin(np.linspace(0, np.pi, m)) ** 1.5
    return 0.35 * s


def swoosh():                      # rising swoosh + soft thump - punch slide-up
    m = int(SR * 0.32)
    s = sweep_noise(0.32, 500, 6000) * (np.linspace(0, 1, m) ** 1.6) * np.exp(-np.linspace(0, 1, m) * 0.5)
    t = np.arange(int(SR * 0.25)) / SR
    th = np.sin(2 * np.pi * (110 * t - 120 * t * t)) * env(len(t), 0.002, 0.06)
    out = 0.7 * s
    i = int(SR * 0.28)
    tail = np.zeros(i + len(th))
    tail[:m] += out
    tail[i:i + len(th)] += 0.8 * th
    return tail


def bubble():                      # sticker pop
    m = int(SR * 0.12)
    t = np.arange(m) / SR
    return 0.6 * np.sin(2 * np.pi * (380 * t + 9000 * t * t)) * env(m, 0.001, 0.03)


def sparkle():                     # 5 bright chime hits ~0.1 s apart (reference transition)
    hit_m = int(SR * 0.35)
    t = np.arange(hit_m) / SR
    out = np.zeros(int(SR * 0.9))
    base = [2093, 2637, 3136, 3520, 4186]
    for k in range(5):
        f = base[k] * rng.uniform(0.99, 1.01)
        tone = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in [(1, 1), (2.76, 0.5), (5.4, 0.35), (4.2, 0.25)])
        tone *= env(hit_m, 0.001, 0.07)
        shimmer = band_noise(hit_m, 8000, 14000) * env(hit_m, 0.001, 0.03) * 0.3
        i = int(SR * 0.095 * k)
        out[i:i + hit_m] += 0.32 * (tone + shimmer)
    return out


def alert():                       # "bip-bip" + low boom for ?!
    t = np.arange(int(SR * 0.05)) / SR
    bip = np.sin(2 * np.pi * 3500 * t) * np.minimum(1, (0.05 - t) / 0.01) * np.minimum(1, t / 0.003)
    m = int(SR * 0.7)
    tb = np.arange(m) / SR
    boom = np.sin(2 * np.pi * (62 * tb - 25 * tb * tb)) * env(m, 0.003, 0.22)
    out = np.zeros(m)
    out += 0.75 * boom
    for k in (0, 1):
        i = int(SR * 0.085 * k)
        out[i:i + len(bip)] += 0.3 * bip
    return out


def marker():                      # highlighter stroke
    m = int(SR * 0.26)
    s = sweep_noise(0.26, 1800, 3200, q=0.25) * np.sin(np.linspace(0, np.pi, m)) ** 0.8
    return 0.25 * s


def boom():
    m = int(SR * 0.5)
    t = np.arange(m) / SR
    return 0.9 * np.sin(2 * np.pi * (70 * t - 35 * t * t)) * env(m, 0.002, 0.15)


KIT = {"swish": swish, "swoosh": swoosh, "bubble": bubble, "sparkle": sparkle, "alert": alert,
       "marker": marker, "boom": boom}
hits = list(cfg["sfx"])
for t0, _ in cfg["leaks"]:
    hits.append(["sparkle", t0 - 0.05, 0.9])
    hits.append(["swoosh", t0 - 0.25, 0.4])
for c in cfg["captions"]:
    hits.append(["swish", c["setup_at"], 0.8])
    hits.append(["swoosh", c["punch_at"] - 0.27, 1.0])
    if "_sticker_at" in c:
        hits.append(["bubble", c["_sticker_at"], 0.9])
    if "_mark_at" in c:
        hits.append(["marker", c["_mark_at"], 1.0])
    if "_bang_at" in c:
        hits.append(["alert", c["_bang_at"], 1.0])
track = np.zeros((int(SR * (dur + 1)), 2))
for name, at, gain in hits:
    s = KIT[name]()
    i = max(0, int(at * SR))
    s = s[:max(0, len(track) - i)]
    pan = 0.15 if name == "sparkle" else 0.0
    track[i:i + len(s), 0] += gain * s * (1 - pan)
    track[i:i + len(s), 1] += gain * s * (1 + pan)
WAV = OUT + ".sfx.wav"
st = (np.clip(track, -1, 1) * 32767).astype(np.int16)
with wave.open(WAV, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())

# ---------- final: captions burned in, speech level untouched, SFX underneath ----------
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-i", SRC, "-i", WAV, "-filter_complex",
                f"[0:v]ass={ASS}[v];[2:a]volume={cfg['sfx_volume']}[fx];"
                f"[1:a][fx]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                "-ac", "2", "-t", f"{dur:.3f}", "-movflags", "+faststart", OUT], check=True)
print(json.dumps({"frames": j, "sec": round(dur, 3), "captions": len(cfg["captions"]),
                  "leaks": len(cfg["leaks"]), "sfx_hits": len(hits)}))
