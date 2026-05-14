#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/report_quality.sh <capture-name> [scene-file]" >&2
  exit 1
fi

capture_name="$1"
scene_file="${2:-}"
capture_dir="captures/$capture_name"
images_dir="$capture_dir/images"
sparse_dir="$capture_dir/colmap/sparse"

if [[ ! -d "$images_dir" ]]; then
  echo "Images directory not found: $images_dir" >&2
  exit 1
fi

frame_count=$(find -L "$images_dir" -type f -name '*.jpg' | wc -l | tr -d ' ')
first_image=$(find -L "$images_dir" -type f -name '*.jpg' | sort | head -n 1)
dimensions="unknown"

if [[ -n "$first_image" ]] && command -v ffprobe >/dev/null 2>&1; then
  dimensions=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$first_image" 2>/dev/null || printf 'unknown')
fi

best_model="none"
best_registered=0
best_points=0
best_error="unknown"

if [[ -d "$sparse_dir" && "$(find "$sparse_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" != "0" ]]; then
  if command -v colmap >/dev/null 2>&1; then
    while IFS= read -r model_dir; do
      analysis=$(colmap model_analyzer --path "$model_dir" 2>&1)
      registered=$(printf '%s\n' "$analysis" | awk -F': ' '/Registered images:/ {print $2; exit}')
      points=$(printf '%s\n' "$analysis" | awk -F': ' '/Points:/ {print $2; exit}')
      error=$(printf '%s\n' "$analysis" | awk -F': ' '/Mean reprojection error:/ {gsub(/px/, "", $2); print $2; exit}')

      registered="${registered:-0}"
      points="${points:-0}"
      error="${error:-unknown}"

      if (( registered > best_registered )); then
        best_model="${model_dir#$sparse_dir/}"
        best_registered="$registered"
        best_points="$points"
        best_error="$error"
      fi
    done < <(find "$sparse_dir" -mindepth 1 -maxdepth 1 -type d | sort)
  else
    best_model="colmap unavailable"
  fi
fi

echo "Quality report for $capture_name"
echo
echo "Capture"
echo "- Frames: $frame_count"
echo "- Frame dimensions: $dimensions"
echo
echo "COLMAP"
echo "- Best model: $best_model"
echo "- Registered images: $best_registered"
echo "- Sparse points: $best_points"
echo "- Mean reprojection error: ${best_error}px"

if [[ -n "$scene_file" ]]; then
  if [[ ! -f "$scene_file" ]]; then
    echo "Scene file not found: $scene_file" >&2
    exit 1
  fi

  scene_bytes=$(wc -c < "$scene_file" | tr -d ' ')
  scene_size=$(awk -v bytes="$scene_bytes" 'BEGIN {
    if (bytes >= 1048576) {
      printf "%.2f MB", bytes / 1048576
    } else if (bytes >= 1024) {
      printf "%.1f KB", bytes / 1024
    } else {
      printf "%d B", bytes
    }
  }')
  echo
  echo "Scene"
  echo "- File: $scene_file"
  echo "- Size: $scene_size"
fi

metrics_files=()
while IFS= read -r metrics_file; do
  metrics_files+=("$metrics_file")
done < <(find output/metrics -type f -name 'holdout-metrics*.json' -path "*/${capture_name}-opensplat-*/*" 2>/dev/null | sort)

if (( ${#metrics_files[@]} > 0 )); then
  echo
  echo "Holdout Metrics"
  for metrics_file in "${metrics_files[@]}"; do
    python3 - "$metrics_file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    metrics = json.load(handle)
print(f"- {path}: PSNR {metrics['psnr_db']:.3f} dB, SSIM {metrics['ssim']:.4f}, MSE {metrics['mse']:.6f}")
PY
  done
fi

echo
echo "Recommendations"

if (( frame_count < 80 )); then
  echo "- Try extracting at a higher fps for more view coverage before retraining."
else
  echo "- Frame count is healthy for another training pass."
fi

if (( best_registered < 50 )); then
  echo "- COLMAP registration is below target; improve capture before OpenSplat training."
else
  echo "- COLMAP registration is above the 50-image training threshold."
fi

if (( frame_count > 0 && best_registered > 0 )); then
  registration_ratio=$(awk -v registered="$best_registered" -v frames="$frame_count" 'BEGIN { printf "%.2f", registered / frames }')
  echo "- Registration ratio: $registration_ratio"
  if awk -v ratio="$registration_ratio" 'BEGIN { exit !(ratio < 0.75) }'; then
    echo "- Registration ratio is low; avoid blurry frames and keep a slower, smoother orbit."
  fi
fi

if [[ "$best_error" != "unknown" ]] && awk -v error="$best_error" 'BEGIN { exit !(error > 1.5) }'; then
  echo "- Reprojection error is high; prefer sharper frames or a lower extraction scale."
fi

if [[ -n "${scene_bytes:-}" ]]; then
  if (( scene_bytes > 25 * 1024 * 1024 )); then
    echo "- Scene exceeds the Pages size gate; use quality-stage with a smaller preset."
  else
    echo "- Scene size is inside the 25MB Pages gate."
  fi
fi
