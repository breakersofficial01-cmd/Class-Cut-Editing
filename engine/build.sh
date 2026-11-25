#!/usr/bin/env bash
# Build a vertical hook-first short from a classroom clip.
# Usage: engine/build.sh <source.mp4> <project_dir> <work_dir>
# Output: <work_dir>/final_9x16.mp4
set -euo pipefail
SRC=$1; PROJ=$2; WORK=$3
ENGINE=$(cd "$(dirname "$0")" && pwd)
CFG="$PROJ/config.json"
mkdir -p "$WORK"
read SPEED FREEZE <<<"$(python3 -I -c "import json,sys;c=json.load(open(sys.argv[1]));print(c['speed'],c['freeze_at_src'])" "$CFG")"

# 1) sped-up picture + freeze frame for cold open / reveal
ffmpeg -v error -y -i "$SRC" -an -vf "setpts=PTS/$SPEED,fps=30" -c:v libx264 -crf 12 -preset fast "$WORK/sped.mp4"
ffmpeg -v error -y -ss "$FREEZE" -i "$SRC" -frames:v 1 "$WORK/freeze.png"

# 2) render picture (zooms, layout, reveal)
python3 -I - "$CFG" "$WORK" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1])); w = sys.argv[2]
c["sped_video"] = w + "/sped.mp4"; c["freeze_frame"] = w + "/freeze.png"
json.dump(c, open(w + "/run.json", "w"), ensure_ascii=False)
EOF
META=$(python3 -I "$ENGINE/render.py" "$WORK/run.json" "$WORK/base.mp4")
echo "$META"
R=$(python3 -I -c "import json,sys;print(json.loads(sys.argv[1])['reveal_start'])" "$META")
T=$(python3 -I -c "import json,sys;print(json.loads(sys.argv[1])['total_sec'])" "$META")
COLD_MS=$(python3 -I -c "import json,sys;print(int(json.load(open(sys.argv[1]))['cold_open_sec']*1000))" "$CFG")

# 3) text layer + SFX
python3 -I "$ENGINE/overlays.py" "$WORK/run.json" "$R" "$T" "$WORK/text.ass" "$WORK/sfx.wav"

# 4) final mix: cleaned + sped speech, delayed past cold open, SFX on top, -14 LUFS for socials
MAIN_END=$(python3 -I -c "print(round($R - 0.18, 3))")
ffmpeg -v error -y -i "$WORK/base.mp4" -i "$SRC" -i "$WORK/sfx.wav" -filter_complex "
[1:a]atempo=$SPEED,highpass=f=85,lowpass=f=12000,acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2,
 aresample=48000,adelay=${COLD_MS}|${COLD_MS},afade=t=out:st=$MAIN_END:d=0.18[sp];
[2:a]volume=0.55[fx];
[sp][fx]amix=inputs=2:normalize=0:duration=longest,atrim=0:$T,loudnorm=I=-14:TP=-1.0:LRA=9[a];
[0:v]ass=$WORK/text.ass[v]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset slow -profile:v high \
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart -t "$T" "$WORK/final_9x16.mp4"
echo "done: $WORK/final_9x16.mp4"
