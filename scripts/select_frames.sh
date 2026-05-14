#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: scripts/select_frames.sh <source-capture> <output-capture> [max-frames]" >&2
  exit 1
fi

source_capture="$1"
output_capture="$2"
max_frames="${3:-180}"

source_dir="captures/$source_capture/images"
output_dir="captures/$output_capture/images"

if [[ ! -d "$source_dir" ]]; then
  echo "Source capture images not found: $source_dir" >&2
  exit 1
fi

python3 scripts/select_frames.py "$source_dir" "$output_dir" "$max_frames"

echo "Next: run COLMAP on the selected frame set with:"
echo "  COLMAP_CAMERA_MODEL=PINHOLE scripts/run_colmap.sh $output_capture"
echo "then inspect it with:"
echo "  bin/splatter analyze $output_capture"
