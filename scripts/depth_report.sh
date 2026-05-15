#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/depth_report.sh <capture-name> [depth-dir]" >&2
  exit 1
fi

capture_name="$1"
images_dir="captures/$capture_name/images"
depth_dir="${2:-captures/$capture_name/depth}"

echo "Depth prior report for $capture_name"
echo "- Reports depth coverage before depth maps are used for ranking or training priors."
echo "- Coverage target: one depth map per selected input frame."

if [[ "${SPLAT_DEPTH_REPORT_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

frame_count=$(find -L "$images_dir" -type f -name '*.jpg' | wc -l | tr -d ' ')
depth_count=0
if [[ -d "$depth_dir" ]]; then
  depth_count=$(find -L "$depth_dir" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.npy' \) | wc -l | tr -d ' ')
fi

coverage=$(awk -v depths="$depth_count" -v frames="$frame_count" 'BEGIN {
  if (frames == 0) { print "0.00" } else { printf "%.2f", depths / frames }
}')

echo
echo "Frames: $frame_count"
echo "Depth maps: $depth_count"
echo "Depth coverage: $coverage"

if awk -v coverage="$coverage" 'BEGIN { exit !(coverage < 0.95) }'; then
  echo "Recommendation: generate missing depth priors before using depth consistency as a ranking signal."
  exit 2
fi

echo "PASS: depth coverage is sufficient for downstream depth consistency checks."
