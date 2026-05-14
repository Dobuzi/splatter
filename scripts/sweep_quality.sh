#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: scripts/sweep_quality.sh <input-video> <base-name> [title]" >&2
  exit 1
fi

input_video="$1"
base_name="$2"
title="${3:-$base_name}"

if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi

fps_list="${SPLAT_SWEEP_FPS_LIST:-8 12}"
camera_model_list="${SPLAT_SWEEP_CAMERA_MODELS:-PINHOLE SIMPLE_PINHOLE}"
iters_list="${SPLAT_SWEEP_ITERS_LIST:-5000 10000}"
downscale_list="${SPLAT_SWEEP_DOWNSCALES:-1 2}"

fps_values=(${(z)fps_list})
camera_models=(${(z)camera_model_list})
iters_values=(${(z)iters_list})
downscale_values=(${(z)downscale_list})
execute="${SPLAT_SWEEP_EXECUTE:-0}"
save_every="${SPLAT_SWEEP_SAVE_EVERY:-1000}"
val_image="${SPLAT_SWEEP_VAL_IMAGE:-auto}"

echo "Quality sweep for $input_video"
echo "- Base: $base_name"
echo "- Title: $title"
echo "- Execute: $execute"
echo "- Holdout: $val_image"

for fps in "${fps_values[@]}"; do
  for camera_model in "${camera_models[@]}"; do
    camera_slug=$(printf '%s' "$camera_model" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
    capture_name="${base_name}-fps${fps}-${camera_slug}"
    for iters in "${iters_values[@]}"; do
      for downscale in "${downscale_values[@]}"; do
        output_file="output/${capture_name}-opensplat-${iters}-d${downscale}.ply"
        metrics_dir="output/metrics/${capture_name}-opensplat-${iters}-d${downscale}"
        render_file="$metrics_dir/${iters}.png"
        metrics_file="$metrics_dir/holdout-metrics.json"
        echo
        echo "Experiment: capture=$capture_name iters=$iters downscale=$downscale"
        echo "  COLMAP_CAMERA_MODEL=$camera_model bin/splatter capture $input_video $capture_name $fps"
        if [[ "$val_image" == "none" ]]; then
          echo "  OPENSPLAT_SAVE_EVERY=$save_every bin/splatter train $capture_name $iters $downscale $output_file"
        else
          echo "  OPENSPLAT_SAVE_EVERY=$save_every OPENSPLAT_VAL=1 OPENSPLAT_VAL_IMAGE=$val_image OPENSPLAT_VAL_RENDER=$metrics_dir bin/splatter train $capture_name $iters $downscale $output_file"
          echo "  bin/splatter compare-holdout captures/$capture_name/images/<holdout> $render_file $metrics_file"
        fi
        echo "  bin/splatter quality-report $capture_name $output_file"

        if [[ "$execute" == "1" ]]; then
          if [[ -d "captures/$capture_name/colmap/sparse" && -d "captures/$capture_name/images" ]]; then
            echo "  Reusing existing capture $capture_name"
          else
            COLMAP_CAMERA_MODEL="$camera_model" bin/splatter capture "$input_video" "$capture_name" "$fps"
          fi
          resolved_val_image="$val_image"
          if [[ "$resolved_val_image" == "auto" ]]; then
            image_files=("${(@f)$(find -L "captures/$capture_name/images" -maxdepth 1 -type f -name '*.jpg' | sort)}")
            if (( ${#image_files[@]} == 0 )); then
              echo "No images found for holdout selection: captures/$capture_name/images" >&2
              exit 1
            fi
            middle_index=$(( (${#image_files[@]} + 1) / 2 ))
            resolved_val_image="${image_files[$middle_index]:t}"
          fi

          if [[ "$resolved_val_image" == "none" ]]; then
            OPENSPLAT_SAVE_EVERY="$save_every" bin/splatter train "$capture_name" "$iters" "$downscale" "$output_file"
          else
            mkdir -p "$metrics_dir"
            OPENSPLAT_SAVE_EVERY="$save_every" \
              OPENSPLAT_VAL=1 \
              OPENSPLAT_VAL_IMAGE="$resolved_val_image" \
              OPENSPLAT_VAL_RENDER="$metrics_dir" \
              bin/splatter train "$capture_name" "$iters" "$downscale" "$output_file"

            holdout_file="captures/$capture_name/images/$resolved_val_image"
            if [[ -f "$render_file" ]]; then
              bin/splatter compare-holdout "$holdout_file" "$render_file" "$metrics_file"
            else
              echo "Holdout render not found: $render_file" >&2
              echo "Choose an iteration count divisible by 10 to emit validation renders." >&2
            fi
          fi
          bin/splatter quality-report "$capture_name" "$output_file"
        fi
      done
    done
  done
done
