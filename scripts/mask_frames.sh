#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/mask_frames.sh <capture-name> [output-dir]" >&2
  exit 1
fi

capture_name="$1"
output_dir="${2:-captures/$capture_name/masks}"
images_dir="captures/$capture_name/images"

echo "Mask generation for $capture_name"
echo "- Uses rembg when installed to remove dynamic foreground/background clutter."
echo "- Output: $output_dir"

if [[ "${SPLAT_MASK_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

if ! command -v rembg >/dev/null 2>&1; then
  echo "rembg is not installed. Install it or provide masks manually in $output_dir." >&2
  exit 2
fi

mkdir -p "$output_dir"
for image in "$images_dir"/*.jpg; do
  mask="$output_dir/${image:t:r}.png"
  rembg i -om "$image" "$mask"
done

echo "Masks written to $output_dir"
echo "Next: use trainer-specific mask support, or use these masks to remove bad frames before COLMAP."
