#!/usr/bin/env bash
# Download a Google Drive share link (or copy a local file) to <out.mp4> and verify it is a video.
# Usage: engine/fetch.sh <drive-link | file-id | local-path> <out.mp4>
set -euo pipefail
SRC=$1; OUT=$2
mkdir -p "$(dirname "$OUT")"
if [ -f "$SRC" ]; then cp "$SRC" "$OUT"; else
  ID=$(echo "$SRC" | sed -nE 's#.*/d/([A-Za-z0-9_-]+).*#\1#p; s#.*[?&]id=([A-Za-z0-9_-]+).*#\1#p' | head -1)
  [ -z "$ID" ] && ID=$SRC
  curl -sSL -o "$OUT" "https://drive.usercontent.google.com/download?id=$ID&export=download&confirm=t"
fi
if ! ffprobe -v error "$OUT" >/dev/null 2>&1; then
  if grep -qi "sign-in\|Sign in" "$OUT" 2>/dev/null; then
    echo "ERROR: Drive returned a sign-in page. The file is private: ask the user to set sharing to 'Anyone with the link can view'." >&2
  else
    echo "ERROR: downloaded file is not a video." >&2
  fi
  exit 1
fi
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate -of compact "$OUT"
