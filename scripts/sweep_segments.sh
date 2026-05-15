#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 4 )); then
  echo "Usage: scripts/sweep_segments.sh <input-video> <base-name> [window-sec] [stride-sec]" >&2
  exit 1
fi

input_video="$1"
base_name="$2"
window_sec="${3:-45}"
stride_sec="${4:-15}"

if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi

execute="${SPLAT_SEGMENT_EXECUTE:-0}"
fps="${SPLAT_SEGMENT_FPS:-4}"
camera_model="${SPLAT_SEGMENT_CAMERA_MODEL:-PINHOLE}"
scale="${SPLAT_SEGMENT_SCALE:-1920}"
duration="${SPLAT_SEGMENT_DURATION:-}"

if [[ -z "$duration" ]]; then
  duration=$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$input_video" 2>/dev/null || printf '60')
fi
duration_int=$(awk -v value="$duration" 'BEGIN { printf "%d", value }')

echo "Segment sweep for $input_video"
echo "- Base: $base_name"
echo "- Execute: $execute"
echo "- Window: ${window_sec}s"
echo "- Stride: ${stride_sec}s"
echo "- FPS: $fps"
echo "- Camera model: $camera_model"

for start in $(seq 0 "$stride_sec" "$duration_int"); do
  end=$(( start + window_sec ))
  if (( end > duration_int + stride_sec )); then
    break
  fi
  capture_name=$(printf '%s-%03d-%03d-fps%s-pinhole' "$base_name" "$start" "$end" "$fps")
  echo
  echo "Segment: ${start}-${end}s"
  echo "  ffmpeg -ss $start -t $window_sec -i $input_video -vf fps=$fps,scale='min($scale,iw)':-2 captures/$capture_name/images/frame_%05d.jpg"
  echo "  COLMAP_CAMERA_MODEL=$camera_model scripts/run_colmap.sh $capture_name"
  echo "  bin/splatter colmap-gate $capture_name"

  if [[ "$execute" == "1" ]]; then
    images_dir="captures/$capture_name/images"
    mkdir -p "$images_dir"
    ffmpeg -hide_banner -loglevel error \
      -ss "$start" \
      -t "$window_sec" \
      -i "$input_video" \
      -vf "fps=$fps,scale='min($scale,iw)':-2" \
      -q:v 2 \
      "$images_dir/frame_%05d.jpg"
    COLMAP_CAMERA_MODEL="$camera_model" scripts/run_colmap.sh "$capture_name"
    scripts/colmap_gate.sh "$capture_name" || true
  fi
done
