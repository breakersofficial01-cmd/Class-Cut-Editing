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
import os
import subprocess
import sys
import wave

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

cfg = json.load(open(sys.argv[1]))
SRC, OUT = sys.argv[2], sys.argv[3]
W, H, FPS = cfg["size"][0], cfg["size"][1], cfg["fps"]
SR = cfg["audio_rate"]
CAP = cfg["caption_style"]
NOTO = "/usr/share/fonts/truetype/noto/"
EMOJI_FONT = NOTO + "NotoColorEmoji.ttf"

COLORS = {  # ASS is &HBBGGRR&
    "yellow": "&H00F2FF&", "green": "&H2AFF3C&", "red": "&H2A2AFF&", "white": "&HFFFFFF&"}
LEAK_RGB = {"yellow": [(255, 238, 80), (255, 205, 30)],
            "red": [(255, 50, 25), (255, 140, 0)],
            "orange": [(255, 140, 20), (255, 60, 30)]}
SETUP_Y = CAP["setup_y"]            # bottom anchor of setup line
PUNCH_Y = CAP["punch_y"]            # bottom anchor of punch line

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def font_for(file, ass_size):
    """Pillow font matching libass's rendering size (libass scales by em/(ascent-descent))."""
    path = os.path.join(FONTS_DIR, file)
    f = TTFont(path)
    ratio = f["head"].unitsPerEm / (f["hhea"].ascent - f["hhea"].descent)
    name = f["name"].getDebugName(1)
    return ImageFont.truetype(path, ass_size * ratio), name


def text_band(file, ass_size, anchor_y):
    """Vertical extent (top, bottom) of Bangla letters for a bottom-anchored libass line."""
    f = TTFont(os.path.join(FONTS_DIR, file))
    h = f["hhea"]
    px = ass_size / (h.ascent - h.descent)          # px per font unit
    baseline = anchor_y + h.descent * px            # descent is negative
    em = f["head"].unitsPerEm * px
    return baseline - 0.92 * em, baseline + 0.18 * em


# Font roles (files in engine/fonts): bold = punch, regular = setup, light = accent words.
# Inline markup: [l]..[/l] -> light weight inside a punch line; setup "mark" words -> bold.
FONTSET = CAP["fonts"]
_fullname = {k: TTFont(os.path.join(FONTS_DIR, f))["name"].getDebugName(4) for k, f in FONTSET.items()}
_pil = {}


def pil(role, size):
    key = (role, size)
    if key not in _pil:
        _pil[key] = font_for(FONTSET[role], size)[0]
    return _pil[key]


def segments(text, base, alt="light"):
    """'a [l]b[/l] c' -> [('a ', base), ('b', alt), (' c', base)]"""
    out, cur = [], base
    for part in text.replace("[/l]", "\x00" + base).replace("[l]", "\x00" + alt).split("\x00"):
        role = cur
        for r in (base, alt):
            if part.startswith(r):
                role, part = r, part[len(r):]
                break
        if part:
            out.append((part, role))
        cur = role
    return out


def seg_width(segs, size):
    return sum(pil(r, size).getlength(t) for t, r in segs)


def seg_ass(segs):
    return "".join(rf"{{\fn{_fullname[r]}}}{t}" for t, r in segs)


def plain(text):
    return text.replace("[l]", "").replace("[/l]", "")


class _W:  # width helper used by sticker placement
    def getlength(self, text):
        return seg_width(segments(text, "bold"), CAP["punch_size"])


_punch_font = _W()


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
        x = W / 2 + _punch_font.getlength(c["punch"]) / 2 + 28 + CAP["sticker_size"] / 2
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


# House palette: white text + ONE accent (yellow). Extrusion front edge = gold, glow = yellow.
GOLD = (0, 185, 240)          # BGR
GLOW = "&H00D7FF&"            # yellow glow (BGR)
DARK = {k: GOLD for k in ("yellow", "green", "red", "white")}


def bgr(t):
    return "&H%02X%02X%02X&" % t


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def layered(start, end, layer0, x0, y0, x1, y1, move_ms, clip, body, size, accent, depth, step,
            bord, shadow_off, tint_band=None, glow=0):
    """3D text: soft shadow -> extrusion (back black -> front accent-dark) -> white face -> bevel tint."""
    out = []

    def mv(dx, dy):
        if move_ms:
            return rf"\move({x0 + dx:.0f},{y0 + dy:.0f},{x1 + dx:.0f},{y1 + dy:.0f},0,{move_ms})"
        return rf"\pos({x1 + dx:.0f},{y1 + dy:.0f})"

    base = rf"\an2\fs{size}\b0\i0{clip}"
    out.append((layer0, rf"{base}{mv(shadow_off, shadow_off + 2)}\1c&H000000&\3c&H000000&\bord{bord + 2}"
                        rf"\blur6\1a&H70&\3a&H70&\shad0"))
    if glow:
        out.append((layer0, rf"{base}{mv(0, 0)}\1c{GLOW}\3c{GLOW}\bord{bord + glow}\blur{glow * 1.8:.0f}"
                            rf"\1a&H50&\3a&H50&\shad0"))
    for k in range(depth, 0, -1):
        col = bgr(mix((10, 10, 10), DARK[accent], 1 - (k - 1) / max(depth, 1)))
        out.append((layer0 + 1 + depth - k,
                    rf"{base}{mv(k * step, k * step)}\1c{col}\3c{col}\bord{bord}\shad0\blur0.6"))
    out.append((layer0 + depth + 2, rf"{base}{mv(0, 0)}\1c&HFFFFFF&\3c&H101010&\bord{bord}\shad0"))
    if tint_band:
        ty0, ty1 = tint_band
        out.append((layer0 + depth + 3,
                    rf"\an2\fs{size}\b0\i0\clip(0,{ty0:.0f},{W},{ty1:.0f}){mv(0, 0)}"
                    rf"\1c&HDCD2C8&\3c&H101010&\bord0\shad0\blur0.8"))
    return [f"Dialogue: {L},{t_ass(start)},{t_ass(end)},Txt,,0,0,0,,{{{tags}}}{body}" for L, tags in out]


ev = []
PS, SS = CAP["punch_size"], CAP["setup_size"]
for c in cfg["captions"]:
    acc = c["color"]
    sa, pa, end = c["setup_at"], c["punch_at"], c["end"]

    # ---- setup line: regular italic, marked words bold italic over a red marker ----
    if c.get("mark") and c["mark"] in c["setup"]:
        i = c["setup"].index(c["mark"])
        ssegs = [(c["setup"][:i], "regular"), (c["mark"], "bold"), (c["setup"][i + len(c["mark"]):], "regular")]
        ssegs = [x for x in ssegs if x[0]]
    else:
        ssegs = [(c["setup"], "regular")]
    sw = seg_width(ssegs, SS)
    sx0, sx1 = W / 2 - sw / 2, W / 2 + sw / 2
    if c.get("mark") and c["mark"] in c["setup"]:
        mx0 = sx0 + seg_width(ssegs[:1], SS) - 8 if ssegs[0][1] == "regular" else sx0 - 8
        mx1 = mx0 + pil("bold", SS).getlength(c["mark"]) + 16
        my0, my1 = (round(v) for v in text_band(FONTSET["regular"], SS, SETUP_Y))
        mt = int(c.get("mark_delay", 0.35) * 1000)
        ev.append(f"Dialogue: 0,{t_ass(sa)},{t_ass(end)},Mark,,0,0,0,,"
                  rf"{{\an7\pos(0,0)\clip({mx0:.0f},{my0},{mx0:.0f},{my1})"
                  rf"\t({mt},{mt + 260},\clip({mx0:.0f},{my0},{mx1:.0f},{my1}))\p1}}"
                  f"m {mx0:.0f} {my0 + 4} l {mx1:.0f} {my0} {mx1 - 4:.0f} {my1} {mx0 + 3:.0f} {my1 - 2}")
        c["_mark_at"] = sa + mt / 1000
    wipe = rf"\clip({sx0 - 20:.0f},0,{sx0 - 20:.0f},{H})\t(0,300,\clip({sx0 - 20:.0f},0,{sx1 + 20:.0f},{H}))"
    ev += layered(sa, end, 1, W / 2, SETUP_Y, W / 2, SETUP_Y, 0, wipe, seg_ass(ssegs), SS, "white",
                  depth=3, step=1.0, bord=2.5, shadow_off=3, glow=CAP.get("setup_glow", 3))

    # ---- punch line: bold italic (+ light accent words), 3D, slides up then settles ----
    psegs = segments(c["punch"], "bold")
    body = seg_ass(psegs)
    mask = rf"\clip(0,0,{W},{PUNCH_Y + 10})"
    d = CAP.get("depth", 7)
    ty0, ty1 = text_band(FONTSET["bold"], PS, PUNCH_Y)
    band = (ty0 + (ty1 - ty0) * 0.52, ty1 + 6)
    ev += layered(pa, pa + 0.14, 10, W / 2, PUNCH_Y + 110, W / 2, PUNCH_Y - 10, 140, mask, body, PS, acc,
                  depth=d, step=1.3, bord=4, shadow_off=d * 1.3 + 4, glow=CAP.get("glow", 7))
    ev += layered(pa + 0.14, end, 10, W / 2, PUNCH_Y - 10, W / 2, PUNCH_Y, 90, "", body, PS, acc,
                  depth=d, step=1.3, bord=4, shadow_off=d * 1.3 + 4, tint_band=band,
                  glow=CAP.get("glow", 7))

    if c.get("bang"):
        x = W / 2 - _punch_font.getlength(c["punch"]) / 2 - CAP.get("bang_gap", 80)

        def bang_tags(dx):
            return (rf"\an2\pos({x + dx:.0f},{PUNCH_Y + 6 + dx:.0f})\fn{_fullname['bold']}"
                    rf"\fs{CAP.get('bang_size', 130)}\b0\i0\frz-35\fscx10\fscy10"
                    rf"\t(0,130,\frz14\fscx125\fscy125)\t(130,230,\frz8\fscx100\fscy100)")
        for k in range(5, 0, -1):
            ev.append(f"Dialogue: {35 - k},{t_ass(pa + 0.05)},{t_ass(end)},Txt,,0,0,0,,"
                      f"{{{bang_tags(k * 1.4)}\\1c{bgr(GOLD)}\\3c{bgr(GOLD)}\\bord4\\shad0}}?!")
        ev.append(f"Dialogue: 36,{t_ass(pa + 0.05)},{t_ass(end)},Txt,,0,0,0,,"
                  f"{{{bang_tags(0)}\\1c&HFFFFFF&\\3c&H101010&\\bord4\\shad0}}?!")
        c["_bang_at"] = pa + 0.05

ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Txt,{_fullname['bold']},{PS},&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,0,0,0,0,100,100,0,0,1,4,0,2,0,0,0,1
Style: Mark,Arial,20,&H2000C8FF,&H2000C8FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

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
                f"[0:v]ass={ASS}:fontsdir={FONTS_DIR}[v];[2:a]volume={cfg['sfx_volume']}[fx];"
                f"[1:a][fx]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                "-ac", "2", "-t", f"{dur:.3f}", "-movflags", "+faststart", OUT], check=True)
print(json.dumps({"frames": j, "sec": round(dur, 3), "captions": len(cfg["captions"]),
                  "leaks": len(cfg["leaks"]), "sfx_hits": len(hits)}))
