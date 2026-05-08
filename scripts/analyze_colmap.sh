#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/analyze_colmap.sh <capture-name>" >&2
  exit 1
fi

capture_name="$1"
sparse_dir="captures/$capture_name/colmap/sparse"

if [[ ! -d "$sparse_dir" ]]; then
  echo "COLMAP sparse directory not found: $sparse_dir" >&2
  echo "Run scripts/run_colmap.sh first." >&2
  exit 1
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for analysis. Install it with: brew install colmap" >&2
  exit 1
fi

model_dirs=()
while IFS= read -r model_dir; do
  model_dirs+=("$model_dir")
done < <(find "$sparse_dir" -mindepth 1 -maxdepth 1 -type d | sort)

if (( ${#model_dirs[@]} == 0 )); then
  echo "No sparse models found under: $sparse_dir" >&2
  exit 1
fi

best_model=""
best_registered=0

echo "COLMAP sparse model summary for $capture_name"

for model_dir in "${model_dirs[@]}"; do
  analysis=$(colmap model_analyzer --path "$model_dir" 2>&1)

  registered=$(printf '%s\n' "$analysis" | awk -F': ' '/Registered images:/ {print $2; exit}')
  points=$(printf '%s\n' "$analysis" | awk -F': ' '/Points:/ {print $2; exit}')
  error=$(printf '%s\n' "$analysis" | awk -F': ' '/Mean reprojection error:/ {gsub(/px/, "", $2); print $2; exit}')

  registered="${registered:-0}"
  points="${points:-0}"
  error="${error:-unknown}"

  echo "- ${model_dir#$sparse_dir/}: ${registered} registered images, ${points} points, ${error}px mean reprojection error"

  if (( registered > best_registered )); then
    best_registered="$registered"
    best_model="${model_dir#$sparse_dir/}"
  fi
done

echo "Best model: $best_model with $best_registered registered images"

if (( best_registered >= 50 )); then
  echo "Status: ready to test 3DGS training input."
else
  echo "Status: below the 50-frame target. Improve capture before 3DGS training."
fi
