"""Bangla word-level transcript with faster-whisper large-v3.

Usage: python3 -I engine/transcribe.py <video> <out_words.json>
Prints a readable timeline "[t]word ..." and writes [[start, end, word], ...].

Notes learned the hard way:
  * set HF_HUB_DISABLE_XET=1 (done here) - the Xet CDN host is not allowed by the network policy
  * pass raw PCM (the bundled PyAV rejects a keyword faster-whisper uses when given a path)
  * whisper sometimes stops early on Bangla; we re-run from the last word until the end is covered
  * output is phonetic and messy - always rewrite captions by meaning, never copy verbatim
"""
import json
import os
import subprocess
import sys

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
dur = len(audio) / 16000
model = WhisperModel("large-v3", device="cpu", compute_type="int8")

words, offset = [], 0.0
for _ in range(4):
    segs, _info = model.transcribe(audio[int(offset * 16000):], language="bn", word_timestamps=True,
                                   beam_size=5, vad_filter=False)
    got = [[round(w.start + offset, 2), round(w.end + offset, 2), w.word.strip()] for s in segs for w in s.words]
    # a "word" lasting > 1.5 s means whisper stalled and smeared the rest: cut there and resume
    stall = next((i for i, (a, b, _) in enumerate(got) if b - a > 1.5), None)
    if stall is not None:
        got = got[:stall]
    got = [g for g in got if not words or g[0] >= words[-1][1] - 0.05]
    words += got
    last = words[-1][1] if words else offset
    if last > dur - 1.5 or (not got and stall is None):
        break
    offset = max(offset + 0.5, last - 0.25)
json.dump(words, open(out, "w"), ensure_ascii=False)
print(f"duration {dur:.2f}s, {len(words)} words")
print(" ".join(f"[{a:.2f}]{t}" for a, _, t in words))
