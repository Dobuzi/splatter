#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/depth_priors.sh <capture-name> [output-dir]" >&2
  exit 1
fi

capture_name="$1"
output_dir="${2:-captures/$capture_name/depth}"
images_dir="captures/$capture_name/images"
depth_command="${SPLAT_DEPTH_COMMAND:-}"
backend="${SPLAT_DEPTH_BACKEND:-command}"

echo "Depth prior generation for $capture_name"
echo "- Backend: $backend"
echo "- Intended backend: Depth Anything V2 or a compatible monocular depth command."
echo "- COLMAP backend: set SPLAT_DEPTH_BACKEND=colmap to run dense stereo from an existing sparse model."
echo "- Set SPLAT_DEPTH_COMMAND with {input} and {output} placeholders."
echo "- Output: $output_dir"

if [[ "${SPLAT_DEPTH_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

if [[ "$backend" == "colmap" ]]; then
  scripts/colmap_surface.sh "$capture_name" "${SPLAT_DEPTH_MODEL_ID:-best}"
  exit $?
fi

if [[ "$backend" != "command" ]]; then
  echo "SPLAT_DEPTH_BACKEND must be command or colmap." >&2
  exit 1
fi

if [[ -z "$depth_command" ]]; then
  echo "SPLAT_DEPTH_COMMAND is required, for example: 'python run_depth.py --image {input} --out {output}'" >&2
  exit 2
fi

mkdir -p "$output_dir"
for image in "$images_dir"/*.jpg; do
  depth="$output_dir/${image:t:r}.png"
  command="${depth_command//\{input\}/$image}"
  command="${command//\{output\}/$depth}"
  eval "$command"
done

echo "Depth priors written to $output_dir"
echo "Next: scale-align depth maps against COLMAP sparse points before using them as training or evaluation priors."
