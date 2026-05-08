#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/run_colmap.sh <capture-name>" >&2
  exit 1
fi

capture_name="$1"
capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
workspace_dir="$capture_dir/colmap"

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  echo "Run scripts/extract_frames.sh first." >&2
  exit 1
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for reconstruction. Install it with: brew install colmap" >&2
  exit 1
fi

mkdir -p "$workspace_dir"

colmap automatic_reconstructor \
  --workspace_path "$workspace_dir" \
  --image_path "$images_dir" \
  --camera_model OPENCV \
  --quality medium \
  --sparse 1 \
  --dense 0 \
  --SiftExtraction.use_gpu 0 \
  --SiftMatching.use_gpu 0

echo "COLMAP reconstruction written to $workspace_dir"
echo "Use this capture with a Mac-compatible 3DGS trainer, then export .ply, .compressed.ply, or .sog."

