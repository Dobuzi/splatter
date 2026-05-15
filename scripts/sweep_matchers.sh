#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/sweep_matchers.sh <source-capture> [base-name]" >&2
  exit 1
fi

source_capture="$1"
base_name="${2:-$source_capture-match}"
source_images="captures/$source_capture/images"
execute="${SPLAT_MATCHER_EXECUTE:-0}"
matchers=(${=SPLAT_MATCHERS:-sequential exhaustive spatial})
camera_models=(${=SPLAT_MATCHER_CAMERA_MODELS:-PINHOLE SIMPLE_PINHOLE OPENCV})
mask_path="${SPLAT_MATCHER_MASK_PATH:-}"

echo "Matcher sweep for $source_capture"
echo "- Base: $base_name"
echo "- Execute: $execute"
echo "- Matchers: ${matchers[*]}"
echo "- Camera models: ${camera_models[*]}"
if [[ -n "$mask_path" ]]; then
  echo "- Mask path: $mask_path"
fi

if [[ "$execute" == "1" && ! -d "$source_images" ]]; then
  echo "Source capture images not found: $source_images" >&2
  exit 1
fi

for matcher in "${matchers[@]}"; do
  for camera_model in "${camera_models[@]}"; do
    camera_slug="${camera_model:l}"
    capture_name="$base_name-$matcher-$camera_slug"
    echo
    echo "Candidate: $capture_name"
    echo "  COLMAP_MATCHER=$matcher COLMAP_CAMERA_MODEL=$camera_model scripts/run_colmap.sh $capture_name"
    echo "  bin/splatter colmap-gate $capture_name"

    if [[ "$execute" == "1" ]]; then
      images_dir="captures/$capture_name/images"
      mkdir -p "$images_dir"
      find "$images_dir" -type l -o -type f | while read -r old; do
        rm -f "$old"
      done
      for image in "$source_images"/*.jpg; do
        ln -sf "$(realpath "$image")" "$images_dir/${image:t}"
      done

      if [[ -n "$mask_path" ]]; then
        COLMAP_MATCHER="$matcher" COLMAP_CAMERA_MODEL="$camera_model" COLMAP_MASK_PATH="$mask_path" scripts/run_colmap.sh "$capture_name"
      else
        COLMAP_MATCHER="$matcher" COLMAP_CAMERA_MODEL="$camera_model" scripts/run_colmap.sh "$capture_name"
      fi
      scripts/colmap_gate.sh "$capture_name" || true
    fi
  done
done

echo
echo "Next: bin/splatter rank-captures $base_name"
