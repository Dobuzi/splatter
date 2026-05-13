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
cache_dir="$capture_dir/cache"
home_dir="$capture_dir/home"
camera_model="${COLMAP_CAMERA_MODEL:-OPENCV}"

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  echo "Run scripts/extract_frames.sh first." >&2
  exit 1
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for reconstruction. Install it with: brew install colmap" >&2
  exit 1
fi

mkdir -p "$workspace_dir" "$cache_dir" "$home_dir"
export XDG_CACHE_HOME="$cache_dir"
export HOME="$home_dir"

colmap automatic_reconstructor \
  --workspace_path "$workspace_dir" \
  --image_path "$images_dir" \
  --data_type individual \
  --camera_model "$camera_model" \
  --single_camera 1 \
  --quality medium \
  --sparse 1 \
  --dense 0 \
  --use_gpu 0

echo "COLMAP reconstruction written to $workspace_dir"
echo "COLMAP camera model: $camera_model"
echo "Use this capture with a Mac-compatible 3DGS trainer, then export .ply, .compressed.ply, or .sog."
