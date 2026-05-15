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

echo "Depth prior generation for $capture_name"
echo "- Intended backend: Depth Anything V2 or a compatible monocular depth command."
echo "- Set SPLAT_DEPTH_COMMAND with {input} and {output} placeholders."
echo "- Output: $output_dir"

if [[ "${SPLAT_DEPTH_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
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
