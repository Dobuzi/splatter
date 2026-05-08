#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
  echo "Usage: scripts/prepare_scene.sh <scene-file.ply|scene-file.sog> [title]" >&2
  exit 1
fi

scene_file="$1"
title="${2:-Gaussian Splat Capture}"

if [[ ! -f "$scene_file" ]]; then
  echo "Scene file not found: $scene_file" >&2
  exit 1
fi

case "$scene_file" in
  *.ply|*.compressed.ply|*.sog) ;;
  *)
    echo "Unsupported scene format. Use .ply, .compressed.ply, or .sog." >&2
    exit 1
    ;;
esac

mkdir -p public/assets
target_name=$(basename "$scene_file")
target_path="public/assets/$target_name"
cp "$scene_file" "$target_path"

safe_title="${title//\\/\\\\}"
safe_title="${safe_title//\"/\\\"}"
safe_target="${target_name//\\/\\\\}"
safe_target="${safe_target//\"/\\\"}"

cat > public/scene.json <<JSON
{
  "title": "$safe_title",
  "assetUrl": "assets/$safe_target"
}
JSON

echo "Prepared $target_path"
echo "Open SuperSplat for inspection: https://superspl.at/editor"
echo "Preview locally: npm run serve"
