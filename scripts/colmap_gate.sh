#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/colmap_gate.sh <capture-name>" >&2
  exit 1
fi

capture_name="$1"
capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
sparse_dir="$capture_dir/colmap/sparse"
min_registered="${SPLAT_GATE_MIN_REGISTERED:-80}"
min_ratio="${SPLAT_GATE_MIN_RATIO:-0.70}"
min_points="${SPLAT_GATE_MIN_POINTS:-15000}"
max_error="${SPLAT_GATE_MAX_ERROR:-1.50}"

echo "COLMAP quality gate for $capture_name"
echo "- Minimum registered images: $min_registered"
echo "- Minimum registration ratio: $min_ratio"
echo "- Minimum sparse points: $min_points"
echo "- Maximum reprojection error: ${max_error}px"

if [[ "${SPLAT_COLMAP_GATE_DRY_RUN:-0}" == "1" ]]; then
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

frame_count=$(find -L "$images_dir" -type f -name '*.jpg' | wc -l | tr -d ' ')
best_model="none"
best_registered=0
best_points=0
best_error="999"

while IFS= read -r model_dir; do
  analysis=$(colmap model_analyzer --path "$model_dir" 2>&1)
  registered=$(printf '%s\n' "$analysis" | awk -F': ' '/Registered images:/ {print $2; exit}')
  points=$(printf '%s\n' "$analysis" | awk -F': ' '/Points:/ {print $2; exit}')
  error=$(printf '%s\n' "$analysis" | awk -F': ' '/Mean reprojection error:/ {gsub(/px/, "", $2); print $2; exit}')
  registered="${registered:-0}"
  points="${points:-0}"
  error="${error:-999}"
  if (( registered > best_registered )); then
    best_model="${model_dir#$sparse_dir/}"
    best_registered="$registered"
    best_points="$points"
    best_error="$error"
  fi
done < <(find "$sparse_dir" -mindepth 1 -maxdepth 1 -type d | sort)

ratio=$(awk -v registered="$best_registered" -v frames="$frame_count" 'BEGIN {
  if (frames == 0) { print "0.00" } else { printf "%.2f", registered / frames }
}')

echo
echo "Best model: $best_model"
echo "- Frames: $frame_count"
echo "- Registered images: $best_registered"
echo "- Registration ratio: $ratio"
echo "- Sparse points: $best_points"
echo "- Mean reprojection error: ${best_error}px"

failed=0
if (( best_registered < min_registered )); then
  echo "FAIL: registered images below gate"
  failed=1
fi
if awk -v ratio="$ratio" -v min="$min_ratio" 'BEGIN { exit !(ratio < min) }'; then
  echo "FAIL: registration ratio below gate"
  failed=1
fi
if (( best_points < min_points )); then
  echo "FAIL: sparse points below gate"
  failed=1
fi
if awk -v error="$best_error" -v max="$max_error" 'BEGIN { exit !(error > max) }'; then
  echo "FAIL: reprojection error above gate"
  failed=1
fi

if (( failed == 1 )); then
  echo
  echo "Recommendation: rerun segment-sweep, raise fps for the best segment, or apply mask-frames before training."
  exit 2
fi

echo
echo "PASS: COLMAP structure is strong enough for 3DGS training."
