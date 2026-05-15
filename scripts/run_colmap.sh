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
matcher="${COLMAP_MATCHER:-automatic}"
mask_path="${COLMAP_MASK_PATH:-}"
quality="${COLMAP_QUALITY:-medium}"
vocab_tree="${COLMAP_VOCAB_TREE:-}"
max_image_size="${COLMAP_MAX_IMAGE_SIZE:-}"
num_threads="${COLMAP_NUM_THREADS:-}"

echo "COLMAP reconstruction for $capture_name"
echo "- Camera model: $camera_model"
echo "- Matcher: $matcher"
echo "- Quality: $quality"
if [[ -n "$mask_path" ]]; then
  echo "- ImageReader.mask_path: $mask_path"
fi
if [[ -n "$max_image_size" ]]; then
  echo "- Max image size: $max_image_size"
fi
if [[ -n "$num_threads" ]]; then
  echo "- Threads: $num_threads"
fi

if [[ "${SPLAT_COLMAP_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for reconstruction. Install it with: brew install colmap" >&2
  exit 1
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  echo "Run scripts/extract_frames.sh first." >&2
  exit 1
fi

mkdir -p "$workspace_dir" "$cache_dir" "$home_dir"
export XDG_CACHE_HOME="$cache_dir"
export HOME="$home_dir"

case "$matcher" in
  automatic)
    automatic_args=(
      automatic_reconstructor
      --workspace_path "$workspace_dir"
      --image_path "$images_dir"
      --data_type individual
      --camera_model "$camera_model"
      --single_camera 1
      --quality "$quality"
      --sparse 1
      --dense 0
      --use_gpu 0
    )
    if [[ -n "$mask_path" ]]; then
      automatic_args+=(--mask_path "$mask_path")
    fi
    if [[ -n "$num_threads" ]]; then
      automatic_args+=(--num_threads "$num_threads")
    fi
    colmap "${automatic_args[@]}"
    ;;
  sequential|exhaustive|spatial|vocab_tree)
    database_path="$workspace_dir/database.db"
    sparse_path="$workspace_dir/sparse"
    rm -f "$database_path"
    mkdir -p "$sparse_path"

    feature_args=(
      feature_extractor
      --database_path "$database_path"
      --image_path "$images_dir"
      --ImageReader.camera_model "$camera_model"
      --ImageReader.single_camera 1
      --FeatureExtraction.use_gpu 0
    )
    if [[ -n "$mask_path" ]]; then
      feature_args+=(--ImageReader.mask_path "$mask_path")
    fi
    if [[ -n "$max_image_size" ]]; then
      feature_args+=(--FeatureExtraction.max_image_size "$max_image_size")
    fi
    if [[ -n "$num_threads" ]]; then
      feature_args+=(--FeatureExtraction.num_threads "$num_threads")
    fi
    colmap "${feature_args[@]}"

    matcher_args=(--database_path "$database_path" --FeatureMatching.use_gpu 0)
    if [[ -n "$num_threads" ]]; then
      matcher_args+=(--FeatureMatching.num_threads "$num_threads")
    fi

    case "$matcher" in
      sequential)
        colmap sequential_matcher "${matcher_args[@]}"
        ;;
      exhaustive)
        colmap exhaustive_matcher "${matcher_args[@]}"
        ;;
      spatial)
        colmap spatial_matcher "${matcher_args[@]}"
        ;;
      vocab_tree)
        if [[ -z "$vocab_tree" ]]; then
          echo "COLMAP_VOCAB_TREE is required for COLMAP_MATCHER=vocab_tree" >&2
          exit 2
        fi
        colmap vocab_tree_matcher "${matcher_args[@]}" --VocabTreeMatching.vocab_tree_path "$vocab_tree"
        ;;
    esac

    colmap mapper \
      --database_path "$database_path" \
      --image_path "$images_dir" \
      --output_path "$sparse_path"
    ;;
  *)
    echo "COLMAP_MATCHER must be automatic, sequential, exhaustive, spatial, or vocab_tree." >&2
    exit 1
    ;;
esac

echo "COLMAP reconstruction written to $workspace_dir"
echo "COLMAP camera model: $camera_model"
echo "COLMAP matcher: $matcher"
echo "Use this capture with a Mac-compatible 3DGS trainer, then export .ply, .compressed.ply, or .sog."
