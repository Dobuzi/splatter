#!/usr/bin/env zsh
set -euo pipefail

if (( $# > 1 )); then
  echo "Usage: scripts/openmvs_batch.sh [input-dir]" >&2
  exit 1
fi

input_dir="${1:-input}"

if [[ "${SPLAT_OPENMVS_BATCH_DRY_RUN:-0}" == "1" ]]; then
  echo "OpenMVS batch for $input_dir"
  echo "- Selects the best existing capture per input video"
  echo "- Integrates frame-quality/MLX quality reports into ranking"
  echo "- Runs SPLAT_SURFACE_BACKEND=openmvs"
  echo "- Stages largest-component cleaned mesh PLY and dense point-cloud PLY into public/assets"
  echo "- Writes output/openmvs-ranking.json"
  exit 0
fi

python3 scripts/openmvs_batch.py "$input_dir"
