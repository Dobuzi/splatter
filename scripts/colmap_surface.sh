#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/colmap_surface.sh <capture-name> [model-id]" >&2
  exit 1
fi

capture_name="$1"
model_id="${2:-best}"
capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
sparse_dir="$capture_dir/colmap/sparse"
dense_dir="$capture_dir/colmap/dense"
threads="${COLMAP_NUM_THREADS:-4}"
max_image_size="${COLMAP_DENSE_MAX_IMAGE_SIZE:-960}"
patch_iterations="${COLMAP_PATCH_MATCH_ITERATIONS:-3}"
poisson_depth="${COLMAP_POISSON_DEPTH:-9}"

echo "COLMAP surface reconstruction for $capture_name"
echo "- Model: $model_id"
echo "- Dense workspace: $dense_dir"
echo "- Depth backend: COLMAP patch_match_stereo"
echo "- Surface outputs: stereo_fusion fused.ply, poisson mesh, delaunay mesh"

if [[ "${SPLAT_SURFACE_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

if [[ ! -d "$sparse_dir" ]]; then
  echo "COLMAP sparse output not found: $sparse_dir" >&2
  exit 1
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for surface reconstruction. Install it with: brew install colmap" >&2
  exit 1
fi

if [[ "$model_id" == "best" ]]; then
  best_model=""
  best_registered=0
  while IFS= read -r model_dir; do
    analysis=$(colmap model_analyzer --path "$model_dir" 2>&1)
    registered=$(printf '%s\n' "$analysis" | awk '/Registered images:/ {value=$NF} END {print value+0}')
    if (( registered > best_registered )); then
      best_registered="$registered"
      best_model="${model_dir:t}"
    fi
  done < <(find "$sparse_dir" -mindepth 1 -maxdepth 1 -type d | sort)
  model_id="$best_model"
fi

input_model="$sparse_dir/$model_id"
if [[ -z "$model_id" || ! -d "$input_model" ]]; then
  echo "Sparse model not found: $input_model" >&2
  exit 1
fi

rm -rf "$dense_dir"
mkdir -p "$dense_dir"

colmap image_undistorter \
  --image_path "$images_dir" \
  --input_path "$input_model" \
  --output_path "$dense_dir" \
  --output_type COLMAP \
  --max_image_size "$max_image_size" \
  --num_threads "$threads"

fused_ply="$dense_dir/fused.ply"
poisson_ply="$dense_dir/meshed-poisson.ply"
delaunay_ply="$dense_dir/meshed-delaunay.ply"
sparse_delaunay_ply="$capture_dir/colmap/sparse-meshed-delaunay.ply"

if colmap patch_match_stereo \
  --workspace_path "$dense_dir" \
  --workspace_format COLMAP \
  --PatchMatchStereo.max_image_size "$max_image_size" \
  --PatchMatchStereo.num_iterations "$patch_iterations" \
  --PatchMatchStereo.num_threads "$threads"; then

  colmap stereo_fusion \
    --workspace_path "$dense_dir" \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path "$fused_ply" \
    --StereoFusion.max_image_size "$max_image_size" \
    --StereoFusion.num_threads "$threads"

  colmap poisson_mesher \
    --input_path "$fused_ply" \
    --output_path "$poisson_ply" \
    --PoissonMeshing.depth "$poisson_depth" \
    --PoissonMeshing.num_threads "$threads" || true

  colmap delaunay_mesher \
    --input_path "$dense_dir" \
    --input_type dense \
    --output_path "$delaunay_ply" \
    --DelaunayMeshing.num_threads "$threads" || true
else
  echo "PatchMatch dense stereo is unavailable or failed; falling back to sparse Delaunay meshing." >&2
fi

colmap delaunay_mesher \
  --input_path "$input_model" \
  --input_type sparse \
  --output_path "$sparse_delaunay_ply" \
  --DelaunayMeshing.num_threads "$threads"

depth_count=$(find "$dense_dir/stereo/depth_maps" -type f -name '*.geometric.bin' 2>/dev/null | wc -l | tr -d ' ')
echo
echo "Surface reconstruction outputs"
echo "- Sparse model: $model_id"
echo "- Depth maps: $depth_count"
if [[ -f "$fused_ply" ]]; then
  fused_bytes=$(wc -c < "$fused_ply" | tr -d ' ')
  echo "- Fused point cloud: $fused_ply ($fused_bytes bytes)"
fi
if [[ -f "$poisson_ply" ]]; then
  echo "- Poisson mesh: $poisson_ply"
fi
if [[ -f "$delaunay_ply" ]]; then
  echo "- Delaunay mesh: $delaunay_ply"
fi
echo "- Sparse Delaunay mesh: $sparse_delaunay_ply"
