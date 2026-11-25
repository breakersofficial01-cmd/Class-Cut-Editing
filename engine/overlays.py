"""Build the text layer (ASS, rendered by libass with Bangla shaping) and a synthesized SFX track.

Usage: python3 overlays.py <config.json> <reveal_start_sec> <total_sec> <out.ass> <out_sfx.wav>
All caption times in config are SOURCE seconds; they are mapped through the cold open + speed-up.
"""
import json
import sys
import wave

import numpy as np

cfg = json.load(open(sys.argv[1]))
R = float(sys.argv[2])            # reveal start (output seconds)
TOTAL = float(sys.argv[3])
OUT_ASS, OUT_WAV = sys.argv[4], sys.argv[5]
COLD, SPEED = cfg["cold_open_sec"], cfg["speed"]
HIT = R + cfg["reveal_hit_sec"]

Y, G, WH = r"{\c&H0AD6FF&}", r"{\c&H5EC522&}", r"{\c&HFFFFFF&}"
POP = r"\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,170,\fscx100\fscy100)"


def o(ts):
    return COLD + ts / SPEED


def ts_(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def color(text):
    return text.replace("[y]", Y).replace("[g]", G).replace("[/]", WH)


events = []


DY = cfg.get("text_dy", 0)   # shifts the whole text layout with the video window


def ev(start, end, text, style="Cap", x=540, y=1290, tags=POP, layer=1):
    events.append(f"Dialogue: {layer},{ts_(start)},{ts_(end)},{style},,0,0,0,,"
                  f"{{\\an5\\pos({x},{y + DY}){tags}}}{color(text)}")


# ---- cold open hook ----
h = cfg["hook"]
ev(0.00, COLD, h["line1"], y=330, tags=r"\fs66" + POP)
ev(0.12, COLD, "[y]" + h["line2"], y=445, tags=r"\fs104\frz-2" + POP)
ev(0.55, COLD, h["line3"], y=1300, tags=r"\fs118" + POP)

# ---- persistent question card (open loop) ----
q = cfg["question"]
ev(COLD, R, q["label"], style="Pill", y=235, tags=r"\fad(120,0)")
ev(COLD, R, q["text"], y=375, tags=r"\fs60\fad(120,0)")
t = COLD
while t < R - 0.2:
    ev(t, min(t + 1.5, R), "[y]" + q["tease"], y=505,
       tags=r"\fs50\t(0,250,\fscx110\fscy110)\t(250,500,\fscx100\fscy100)")
    t += 1.5

# ---- captions (source-timed) ----
for s, e, text, *opt in cfg["captions"]:
    fs = opt[0] if opt else 80
    ev(o(s), o(e), text, tags=rf"\fs{fs}" + POP)

# ---- reveal ----
rv = cfg["reveal"]
ev(R, HIT, rv["think"], y=330, tags=r"\fs70" + POP)
for i, n in enumerate(rv["countdown"]):
    a = R + i * cfg["reveal_hit_sec"] / len(rv["countdown"])
    b = a + cfg["reveal_hit_sec"] / len(rv["countdown"])
    ev(a, b, "[y]" + n, y=845, tags=r"\fs300\bord12" + POP, layer=3)
ev(HIT, TOTAL, rv["label"], style="PillG", y=250, tags=POP)
ev(HIT, TOTAL, "[g]" + rv["answer"], y=400, tags=r"\fs112\bord9" + POP)
ev(HIT + 0.25, TOTAL, rv["why"], y=1250, tags=r"\fs52\bord5\fad(150,0)")
ev(HIT + 1.3, TOTAL, rv["cta"], style="CTA", y=1385, tags=POP)
ev(HIT + 1.6, TOTAL, rv["follow"], y=1465, tags=r"\fs46\bord5" + POP)

header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{cfg['font']},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,7,3,5,70,70,0,1
Style: Pill,{cfg['font']},46,&H00000000,&H00000000,&H000AD6FF,&H000AD6FF,0,0,0,0,100,100,0,0,3,14,0,5,70,70,0,1
Style: PillG,{cfg['font']},50,&H00FFFFFF,&H00FFFFFF,&H005EC522,&H005EC522,0,0,0,0,100,100,0,0,3,16,0,5,70,70,0,1
Style: CTA,{cfg['font']},48,&H00000000,&H00000000,&H000AD6FF,&H000AD6FF,0,0,0,0,100,100,0,0,3,18,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(OUT_ASS, "w", encoding="utf-8").write(header + "\n".join(events) + "\n")

# ---- SFX synthesis (no external assets needed) ----
SR = 48000
track = np.zeros(int(SR * (TOTAL + 1)), np.float32)
rng = np.random.default_rng(7)


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def whoosh(d=0.38):
    n = int(SR * d)
    noise = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(noise)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec *= np.exp(-((f - 1800) / 1500) ** 2) + 0.15 * np.exp(-((f - 400) / 300) ** 2)
    s = np.fft.irfft(spec, n)
    s *= np.sin(np.linspace(0, np.pi, n)) ** 2
    return 0.9 * s / np.abs(s).max()


def impact(d=0.55):
    n = int(SR * d)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (75 * t - 40 * t * t)) * env(n, 0.002, 0.16)
    click = rng.standard_normal(n) * env(n, 0.0005, 0.012)
    return (0.95 * body + 0.35 * click).astype(np.float32)


def tone(freqs, d, decay, amp=0.5):
    n = int(SR * d)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    return (amp * s * env(n, 0.003, decay)).astype(np.float32)


def pop():
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    return (0.45 * np.sin(2 * np.pi * (700 + 900 * np.exp(-t * 60)) * t) * env(n, 0.001, 0.025)).astype(np.float32)


def put(sig, at, gain=1.0):
    i = int(at * SR)
    track[i:i + len(sig)] += gain * sig[:max(0, len(track) - i)]


SFX = {"whoosh": whoosh, "impact": impact, "pop": pop,
       "tick": lambda: tone([1900, 3800], 0.05, 0.012, 0.5),
       "ding": lambda: np.concatenate([tone([1047, 1568], 0.12, 0.25, 0.45),
                                       tone([1319, 1976, 2637], 0.9, 0.35, 0.5)])}
for name, where, at, gain in cfg["sfx"]:
    base = {"cold": 0.0, "src": None, "reveal": R, "hit": HIT}[where]
    put(SFX[name](), o(at) if where == "src" else base + at, gain)

track = np.clip(track, -1, 1)
st = (np.repeat(track[:, None], 2, 1) * 32767).astype(np.int16)
with wave.open(OUT_WAV, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(st.tobytes())
print(f"{len(events)} text events, sfx {len(cfg['sfx'])} hits")
