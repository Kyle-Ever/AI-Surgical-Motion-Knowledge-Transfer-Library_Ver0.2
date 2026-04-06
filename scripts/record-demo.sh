#!/usr/bin/env bash
# record-demo.sh — Record, convert, and add BGM to demo video
# Usage: ./scripts/record-demo.sh
#
# Prerequisites:
#   - Frontend (localhost:3000) and Backend (localhost:8001) running
#   - ffmpeg installed
#   - npm packages installed in frontend/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
OUTPUT_DIR="$ROOT_DIR/demo-output"

mkdir -p "$OUTPUT_DIR"

echo "━━━ Step 1: Recording demo with Playwright ━━━"
cd "$FRONTEND_DIR"
npx playwright test --config=playwright.demo.config.ts 2>&1 | tee "$OUTPUT_DIR/playwright.log"

echo ""
echo "━━━ Step 2: Finding recorded video ━━━"
WEBM_FILE=$(find "$FRONTEND_DIR/test-results" -name "*.webm" -newer "$OUTPUT_DIR/playwright.log" 2>/dev/null | head -1)

if [[ -z "$WEBM_FILE" ]]; then
  # Fallback: find newest webm
  WEBM_FILE=$(find "$FRONTEND_DIR/test-results" -name "*.webm" 2>/dev/null | sort -t/ -k1 | tail -1)
fi

if [[ -z "$WEBM_FILE" ]]; then
  echo "Error: No webm video found in test-results/" >&2
  exit 1
fi

echo "Found: $WEBM_FILE"

echo ""
echo "━━━ Step 3: Converting webm → mp4 ━━━"
bash "$SCRIPT_DIR/convert.sh" "$WEBM_FILE" "$OUTPUT_DIR/demo.mp4" 1

echo ""
echo "━━━ Step 4: Generating BGM ━━━"
# Get video duration
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_DIR/demo.mp4" | cut -d. -f1)
DURATION=$((DURATION + 5)) # Add buffer
bash "$SCRIPT_DIR/bgm.sh" generate "$DURATION" "$OUTPUT_DIR/bgm.mp3"

echo ""
echo "━━━ Step 5: Mixing BGM ━━━"
bash "$SCRIPT_DIR/bgm.sh" mix "$OUTPUT_DIR/demo.mp4" "$OUTPUT_DIR/bgm.mp3" "$OUTPUT_DIR/demo_final.mp4" 0.15

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Demo video complete!"
echo "  Raw:   $OUTPUT_DIR/demo.mp4"
echo "  Final: $OUTPUT_DIR/demo_final.mp4"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
