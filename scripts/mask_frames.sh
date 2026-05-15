#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/mask_frames.sh <capture-name> [output-dir]" >&2
  exit 1
fi

capture_name="$1"
output_dir="${2:-captures/$capture_name/masks}"
images_dir="captures/$capture_name/images"
backend="${SPLAT_MASK_BACKEND:-auto}"
python_bin="${SPLAT_PYTHON:-python3}"

echo "Mask generation for $capture_name"
echo "- Backend: $backend"
echo "- Uses rembg when installed, otherwise falls back to a local center/saliency mask."
echo "- Output: $output_dir"

if [[ "${SPLAT_MASK_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

mkdir -p "$output_dir"
case "$backend" in
  auto|rembg)
    if command -v rembg >/dev/null 2>&1; then
      for image in "$images_dir"/*.jpg; do
        mask="$output_dir/${image:t:r}.png"
        rembg i -om "$image" "$mask"
      done
    elif [[ "$backend" == "rembg" ]]; then
      echo "rembg is not installed. Use SPLAT_MASK_BACKEND=local or install rembg." >&2
      exit 2
    else
      "$python_bin" scripts/generate_masks.py "$images_dir" "$output_dir"
    fi
    ;;
  local)
    "$python_bin" scripts/generate_masks.py "$images_dir" "$output_dir"
    ;;
  *)
    echo "SPLAT_MASK_BACKEND must be auto, rembg, or local." >&2
    exit 1
    ;;
esac

echo "Masks written to $output_dir"
echo "Next: rerun COLMAP with COLMAP_MASK_PATH=$output_dir."
