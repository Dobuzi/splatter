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
backend="${SPLAT_SURFACE_BACKEND:-colmap}"
threads="${COLMAP_NUM_THREADS:-4}"
max_image_size="${COLMAP_DENSE_MAX_IMAGE_SIZE:-960}"
patch_iterations="${COLMAP_PATCH_MATCH_ITERATIONS:-3}"
poisson_depth="${COLMAP_POISSON_DEPTH:-9}"
openmvs_bin_dir="${SPLAT_OPENMVS_BIN_DIR:-}"

echo "COLMAP surface reconstruction for $capture_name"
echo "- Backend: $backend"
echo "- Model: $model_id"
echo "- Dense workspace: $dense_dir"
echo "- Depth backend: COLMAP patch_match_stereo"
echo "- Surface outputs: stereo_fusion fused.ply, poisson mesh, delaunay mesh"
if [[ "$backend" == "openmvs" ]]; then
  echo "- OpenMVS stages: InterfaceCOLMAP, DensifyPointCloud, ReconstructMesh, RefineMesh, TextureMesh"
fi

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

openmvs_command() {
  local name="$1"
  if [[ -n "$openmvs_bin_dir" && -x "$openmvs_bin_dir/$name" ]]; then
    printf '%s/%s\n' "$openmvs_bin_dir" "$name"
  elif command -v "$name" >/dev/null 2>&1; then
    command -v "$name"
  else
    return 1
  fi
}

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

if [[ "$backend" == "openmvs" ]]; then
  interface_colmap=$(openmvs_command InterfaceCOLMAP) || {
    echo "OpenMVS command not found: InterfaceCOLMAP" >&2
    echo "Install OpenMVS and set SPLAT_OPENMVS_BIN_DIR to its bin directory if it is not on PATH." >&2
    exit 2
  }
  densify=$(openmvs_command DensifyPointCloud) || {
    echo "OpenMVS command not found: DensifyPointCloud" >&2
    echo "Install OpenMVS and set SPLAT_OPENMVS_BIN_DIR to its bin directory if it is not on PATH." >&2
    exit 2
  }
  reconstruct=$(openmvs_command ReconstructMesh) || {
    echo "OpenMVS command not found: ReconstructMesh" >&2
    echo "Install OpenMVS and set SPLAT_OPENMVS_BIN_DIR to its bin directory if it is not on PATH." >&2
    exit 2
  }
  refine=$(openmvs_command RefineMesh) || true
  texture=$(openmvs_command TextureMesh) || true

  abs_dense_dir="${dense_dir:a}"
  mvs_dir="$capture_dir/openmvs"
  mkdir -p "$mvs_dir"
  abs_mvs_dir="${mvs_dir:a}"
  scene_mvs="scene.mvs"
  dense_mvs="scene_dense.mvs"
  dense_ply="scene_dense.ply"
  mesh_ply="scene_mesh.ply"
  refined_ply="scene_refined.ply"
  textured_ply="scene_textured.ply"

  "$interface_colmap" \
    -w "$abs_mvs_dir" \
    -i "$abs_dense_dir" \
    -o "$scene_mvs" \
    --image-folder "../colmap/dense/images"

  "$densify" \
    -w "$abs_mvs_dir" \
    -i "$scene_mvs" \
    -o "$dense_mvs" \
    --max-threads "$threads"

  "$reconstruct" \
    -w "$abs_mvs_dir" \
    -i "$dense_mvs" \
    -o "$mesh_ply" \
    --max-threads "$threads"

  if [[ -n "${refine:-}" ]]; then
    "$refine" \
      -w "$abs_mvs_dir" \
      -i "$dense_mvs" \
      -m "$mesh_ply" \
      -o "$refined_ply" \
      --max-threads "$threads" || true
  fi

  if [[ -n "${texture:-}" ]]; then
    texture_input="$mesh_ply"
    if [[ -f "$abs_mvs_dir/$refined_ply" ]]; then
      texture_input="$refined_ply"
    fi
    "$texture" \
      -w "$abs_mvs_dir" \
      -i "$dense_mvs" \
      -m "$texture_input" \
      -o "$textured_ply" \
      --max-threads "$threads" || true
  fi

  echo
  echo "OpenMVS outputs"
  for output in "$scene_mvs" "$dense_mvs" "$dense_ply" "$mesh_ply" "$refined_ply" "$textured_ply"; do
    if [[ -f "$abs_mvs_dir/$output" ]]; then
      echo "- $abs_mvs_dir/$output"
    fi
  done
  exit 0
elif [[ "$backend" != "colmap" ]]; then
  echo "SPLAT_SURFACE_BACKEND must be colmap or openmvs." >&2
  exit 1
fi

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
