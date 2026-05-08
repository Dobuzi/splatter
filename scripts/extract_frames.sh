#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: scripts/extract_frames.sh <input-video> <capture-name> [fps]" >&2
  exit 1
fi

input_video="$1"
capture_name="$2"
fps="${3:-2}"

if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required. Install it with: brew install ffmpeg" >&2
  exit 1
fi

capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
mkdir -p "$images_dir"

ffmpeg -hide_banner -loglevel error -i "$input_video" \
  -vf "fps=$fps,scale='min(1920,iw)':-2" \
  -q:v 2 "$images_dir/frame_%05d.jpg"

count=$(find "$images_dir" -type f -name '*.jpg' | wc -l | tr -d ' ')
if [[ "$count" == "0" ]]; then
  echo "No frames were extracted." >&2
  exit 1
fi

echo "Extracted $count frames to $images_dir"

