#!/usr/bin/env bash
# bgm.sh — Generate ambient BGM and mix into video
# Usage:
#   ./bgm.sh generate <seconds> <output.mp3>
#   ./bgm.sh mix <video.mp4> <bgm.mp3> <output.mp4> [volume=0.15]
#   ./bgm.sh fetch <youtube-url> <output.mp3>

set -euo pipefail

CMD="${1:?Usage: bgm.sh <generate|mix|fetch> ...}"
shift

case "$CMD" in
  generate)
    SECONDS="${1:?Usage: bgm.sh generate <seconds> <output.mp3>}"
    OUTPUT="${2:?Usage: bgm.sh generate <seconds> <output.mp3>}"

    # Generate ambient sine-wave pad: A3 + C#4 + E4 + A4
    ffmpeg -y \
      -f lavfi -i "sine=frequency=220:duration=${SECONDS}" \
      -f lavfi -i "sine=frequency=277.18:duration=${SECONDS}" \
      -f lavfi -i "sine=frequency=329.63:duration=${SECONDS}" \
      -f lavfi -i "sine=frequency=440:duration=${SECONDS}" \
      -filter_complex "\
        [0:a]volume=0.3[a0];\
        [1:a]volume=0.25[a1];\
        [2:a]volume=0.2[a2];\
        [3:a]volume=0.15[a3];\
        [a0][a1][a2][a3]amix=inputs=4:duration=longest,\
        lowpass=f=800,\
        tremolo=f=0.5:d=0.3,\
        afade=t=in:st=0:d=2,\
        afade=t=out:st=$((SECONDS-3)):d=3\
      " \
      -c:a libmp3lame -b:a 128k "$OUTPUT"

    echo "✓ Generated BGM: $OUTPUT (${SECONDS}s)"
    ;;

  mix)
    VIDEO="${1:?Usage: bgm.sh mix <video.mp4> <bgm.mp3> <output.mp4> [volume]}"
    BGM="${2:?Usage: bgm.sh mix <video.mp4> <bgm.mp3> <output.mp4> [volume]}"
    OUTPUT="${3:?Usage: bgm.sh mix <video.mp4> <bgm.mp3> <output.mp4> [volume]}"
    VOL="${4:-0.15}"

    # Get video duration
    VDUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")

    # Mix: loop BGM if shorter, add fade in/out, set volume
    ffmpeg -y -i "$VIDEO" -stream_loop -1 -i "$BGM" \
      -filter_complex "\
        [1:a]atrim=0:${VDUR},asetpts=PTS-STARTPTS,\
        volume=${VOL},\
        afade=t=in:st=0:d=2,\
        afade=t=out:st=$(echo "$VDUR - 3" | bc):d=3[bgm];\
        [0:a][bgm]amix=inputs=2:duration=first[out]\
      " \
      -map 0:v -map "[out]" \
      -c:v copy -c:a aac -b:a 192k \
      "$OUTPUT"

    echo "✓ Mixed: $OUTPUT (vol=$VOL)"
    ;;

  fetch)
    URL="${1:?Usage: bgm.sh fetch <youtube-url> <output.mp3>}"
    OUTPUT="${2:?Usage: bgm.sh fetch <youtube-url> <output.mp3>}"

    if ! command -v yt-dlp &>/dev/null; then
      echo "Error: yt-dlp not found. Install with: pip install yt-dlp" >&2
      exit 1
    fi

    yt-dlp -x --audio-format mp3 -o "$OUTPUT" "$URL"
    echo "✓ Downloaded BGM: $OUTPUT"
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: bgm.sh <generate|mix|fetch> ..." >&2
    exit 1
    ;;
esac
