#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 7 )); then
  echo "Usage: scripts/process_publish.sh <input-video> <capture-name> [fps] [iters] [downscale] [title] [stage|no-stage]" >&2
  exit 1
fi

input_video="$1"
capture_name="$2"
fps="${3:-2}"
iters="${4:-2000}"
downscale="${5:-4}"
title="${6:-$capture_name}"
stage_mode="${7:-stage}"

if [[ "$stage_mode" != "stage" && "$stage_mode" != "no-stage" ]]; then
  echo "Stage mode must be 'stage' or 'no-stage'." >&2
  exit 1
fi

if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi

capture_dir="captures/$capture_name"
ply_output="output/${capture_name}-opensplat-${iters}.ply"
sog_output="output/${capture_name}-opensplat-${iters}.sog"

if [[ -d "$capture_dir/colmap/sparse" && -d "$capture_dir/images" ]]; then
  echo "Reusing existing COLMAP capture: $capture_name"
  scripts/analyze_colmap.sh "$capture_name"
else
  scripts/process_capture.sh "$input_video" "$capture_name" "$fps"
fi

scripts/run_opensplat.sh "$capture_name" "$iters" "$downscale" "$ply_output"
scripts/convert_scene.sh "$ply_output" "$sog_output"

if [[ "$stage_mode" == "stage" ]]; then
  scripts/prepare_scene.sh "$sog_output" "$title"
  echo "Production scene staged from $sog_output"
else
  echo "Skipping stage step. SOG output is ready at $sog_output"
fi
