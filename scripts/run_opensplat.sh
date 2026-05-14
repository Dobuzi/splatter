#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 4 )); then
  echo "Usage: scripts/run_opensplat.sh <capture-name> [iters] [downscale] [output-ply]" >&2
  exit 1
fi

capture_name="$1"
iters="${2:-30000}"
downscale="${3:-4}"
output_file="${4:-output/${capture_name}-opensplat.ply}"

capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
colmap_dir="$capture_dir/colmap"
opensplat_bin="${OPENSPLAT_BIN:-.local/OpenSplat/build/opensplat}"

if [[ ! -x "$opensplat_bin" ]]; then
  echo "OpenSplat executable not found: $opensplat_bin" >&2
  echo "Build OpenSplat first, or set OPENSPLAT_BIN to an existing executable." >&2
  exit 1
fi

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

if [[ ! -d "$colmap_dir/sparse" ]]; then
  echo "COLMAP sparse output not found: $colmap_dir/sparse" >&2
  exit 1
fi

mkdir -p "$(dirname "$output_file")"

opensplat_args=("$colmap_dir" \
  --colmap-image-path "$images_dir" \
  -n "$iters" \
  -d "$downscale" \
  -o "$output_file")

case "${OPENSPLAT_DEVICE:-auto}" in
  auto|mps) ;;
  cpu)
    opensplat_args+=(--cpu)
    ;;
  *)
    echo "OPENSPLAT_DEVICE must be auto, mps, or cpu." >&2
    exit 1
    ;;
esac

if [[ -n "${OPENSPLAT_SAVE_EVERY:-}" ]]; then
  opensplat_args+=(--save-every "$OPENSPLAT_SAVE_EVERY")
fi

if [[ "${OPENSPLAT_VAL:-0}" == "1" ]]; then
  opensplat_args+=(--val)
fi

if [[ -n "${OPENSPLAT_VAL_IMAGE:-}" ]]; then
  opensplat_args+=(--val-image "$OPENSPLAT_VAL_IMAGE")
fi

if [[ -n "${OPENSPLAT_VAL_RENDER:-}" ]]; then
  mkdir -p "$OPENSPLAT_VAL_RENDER"
  opensplat_args+=(--val-render "$OPENSPLAT_VAL_RENDER")
fi

if [[ -n "${OPENSPLAT_EXTRA_ARGS:-}" ]]; then
  opensplat_args+=(${(z)OPENSPLAT_EXTRA_ARGS})
fi

"$opensplat_bin" "${opensplat_args[@]}"

echo "OpenSplat output written to $output_file"
echo "Next: inspect and clean the scene in SuperSplat: https://superspl.at/editor"
