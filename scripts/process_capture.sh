#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 4 )); then
  echo "Usage: scripts/process_capture.sh <input-video> <capture-name> [fps] [scene-file]" >&2
  exit 1
fi

input_video="$1"
capture_name="$2"
fps="${3:-2}"
scene_file="${4:-}"

if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi

scripts/check_tools.sh

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for process_capture. Install it with: brew install colmap" >&2
  exit 1
fi

echo "Extracting frames..."
scripts/extract_frames.sh "$input_video" "$capture_name" "$fps"

echo "Running COLMAP..."
scripts/run_colmap.sh "$capture_name"

echo "Analyzing COLMAP output..."
scripts/analyze_colmap.sh "$capture_name"

if [[ -n "$scene_file" ]]; then
  echo "Staging exported scene..."
  scripts/prepare_scene.sh "$scene_file" "$capture_name"
else
  echo "Next: if the best model reached at least 50 registered images, run the selected Mac-compatible 3DGS trainer and export .ply, .compressed.ply, or .sog."
fi
