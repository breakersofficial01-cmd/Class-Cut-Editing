#!/usr/bin/env bash
# One-time setup for a fresh Claude Code cloud session. Idempotent; safe to re-run.
# Needs network: package registries (pip/apt), drive.google.com + drive.usercontent.google.com,
# huggingface.co + us.aws.cdn.hf.co (speech model). These are allowed on the user's Default environment.
set -uo pipefail
cd "$(dirname "$0")"

echo "== python packages"
python3 -c "import faster_whisper, fontTools, brotli" 2>/dev/null || pip install -q faster-whisper fonttools brotli 2>&1 | grep -v WARNING

echo "== system fonts (Bangla fallback + color emoji for stickers)"
if ! fc-list | grep -q "NotoSansBengali-Black"; then
  (apt-get install -y -q fonts-noto-core >/dev/null 2>&1 || (apt-get update -q >/dev/null 2>&1 && apt-get install -y -q fonts-noto-core >/dev/null 2>&1))
fi
fc-list | grep -q NotoColorEmoji || apt-get install -y -q fonts-noto-color-emoji >/dev/null 2>&1

echo "== tools"
for t in ffmpeg ffprobe; do command -v $t >/dev/null || { echo "MISSING: $t"; }; done

echo "== house fonts (Li Ador Noirrit, licensed - not stored in git)"
missing=0
for f in LiAdorNoirrit-BoldItalic.ttf LiAdorNoirrit-Italic.ttf LiAdorNoirrit-ExtraLightItalic.ttf; do
  [ -f fonts/$f ] || { echo "  MISSING fonts/$f"; missing=1; }
done
if [ $missing = 1 ]; then
  echo "  -> Ask the user to upload the three Li Ador Noirrit .ttf files (Bold Italic, Italic, ExtraLight Italic),"
  echo "     then copy them to engine/fonts/ with the names above. Do NOT substitute another font silently."
else
  echo "  ok"
fi
echo "setup done"
