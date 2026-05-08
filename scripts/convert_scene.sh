#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/convert_scene.sh <input-scene.ply|input-scene.sog> [output-scene.sog|output-scene.ply]" >&2
  exit 1
fi

input_scene="$1"
output_scene="${2:-${input_scene%.*}.sog}"

if [[ ! -f "$input_scene" ]]; then
  echo "Input scene not found: $input_scene" >&2
  exit 1
fi

case "$output_scene" in
  *.ply|*.compressed.ply|*.sog) ;;
  *)
    echo "Unsupported output format. Use .ply, .compressed.ply, or .sog." >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "$output_scene")"

case "$output_scene" in
  *.sog)
    npx splat-transform -w -g cpu "$input_scene" "$output_scene"
    ;;
  *)
    npx splat-transform -w "$input_scene" "$output_scene"
    ;;
esac

input_size=$(wc -c < "$input_scene" | tr -d ' ')
output_size=$(wc -c < "$output_scene" | tr -d ' ')

echo "Converted $input_scene to $output_scene"
echo "Input bytes: $input_size"
echo "Output bytes: $output_size"
