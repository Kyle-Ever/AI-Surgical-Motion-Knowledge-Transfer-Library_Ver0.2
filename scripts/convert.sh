#!/usr/bin/env bash
# convert.sh — Convert webm to mp4 with optional fade in/out
# Usage: ./convert.sh <input.webm> <output.mp4> [fade_seconds]

set -euo pipefail

INPUT="${1:?Usage: convert.sh <input.webm> <output.mp4> [fade_seconds]}"
OUTPUT="${2:?Usage: convert.sh <input.webm> <output.mp4> [fade_seconds]}"
FADE="${3:-0}"

if ! command -v ffmpeg &>/dev/null; then
  echo "Error: ffmpeg not found on PATH" >&2
  exit 1
fi

if [[ "$FADE" -gt 0 ]]; then
  DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT" | cut -d. -f1)
  FADE_OUT_START=$((DURATION - FADE))
  ffmpeg -y -i "$INPUT" \
    -vf "fade=t=in:st=0:d=${FADE},fade=t=out:st=${FADE_OUT_START}:d=${FADE}" \
    -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
    "$OUTPUT"
else
  ffmpeg -y -i "$INPUT" \
    -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
    "$OUTPUT"
fi

echo "✓ Converted: $OUTPUT"
