#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: scripts/stage_quality_scene.sh <input-scene.ply> <title> [web|web-hq]" >&2
  exit 1
fi

input_scene="$1"
title="$2"
preset="${3:-web}"

if [[ ! -f "$input_scene" ]]; then
  echo "Input scene not found: $input_scene" >&2
  exit 1
fi

case "$input_scene" in
  *.ply|*.compressed.ply) ;;
  *)
    echo "Quality staging expects a PLY source scene." >&2
    exit 1
    ;;
esac

case "$preset" in
  web)
    preview_count=20000
    preview_harmonics=0
    final_count=200000
    final_harmonics=1
    ;;
  web-hq)
    preview_count=30000
    preview_harmonics=0
    final_count=300000
    final_harmonics=1
    ;;
  *)
    echo "Unknown quality preset: $preset" >&2
    echo "Use web or web-hq." >&2
    exit 1
    ;;
esac

base="${input_scene%.*}"
preview_output="${base}-$(( preview_count / 1000 ))k-h${preview_harmonics}.sog"
final_output="${base}-$(( final_count / 1000 ))k-h${final_harmonics}.sog"

preview_label="$(( preview_count / 1000 ))k SH$preview_harmonics"
final_label="$(( final_count / 1000 ))k SH$final_harmonics"

if [[ "${SPLAT_QUALITY_DRY_RUN:-}" == "1" ]]; then
  echo "Dry run quality stage"
  echo "- Preset: $preset"
  echo "- Preview: SPLAT_DECIMATE=$preview_count SPLAT_HARMONICS=$preview_harmonics $preview_output"
  echo "- Final: SPLAT_DECIMATE=$final_count SPLAT_HARMONICS=$final_harmonics $final_output"
  echo "- Stage: $title"
  exit 0
fi

SPLAT_DECIMATE="$preview_count" SPLAT_HARMONICS="$preview_harmonics" \
  scripts/convert_scene.sh "$input_scene" "$preview_output"

SPLAT_DECIMATE="$final_count" SPLAT_HARMONICS="$final_harmonics" \
  scripts/convert_scene.sh "$input_scene" "$final_output"

SCENE_TRAINING="${SCENE_TRAINING:-OpenSplat source, staged with $preset preset, final $final_label}" \
SCENE_DELIVERY="${SCENE_DELIVERY:-Progressive preview: $preview_label}" \
SCENE_PREVIEW_ASSET="$preview_output" \
  scripts/prepare_scene.sh "$final_output" "$title"

echo "Quality preset staged"
echo "Preview asset: $preview_output"
echo "Final asset: $final_output"
