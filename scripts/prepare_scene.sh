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

preview_name=""
if [[ -n "${SCENE_PREVIEW_ASSET:-}" ]]; then
  if [[ -f "$SCENE_PREVIEW_ASSET" ]]; then
    preview_name=$(basename "$SCENE_PREVIEW_ASSET")
    cp "$SCENE_PREVIEW_ASSET" "public/assets/$preview_name"
  elif [[ -f "public/assets/$SCENE_PREVIEW_ASSET" ]]; then
    preview_name="$SCENE_PREVIEW_ASSET"
  else
    echo "Preview asset not found: $SCENE_PREVIEW_ASSET" >&2
    exit 1
  fi
fi

case "$target_name" in
  *.sog) format="SOG" ;;
  *.compressed.ply) format="Compressed PLY" ;;
  *.ply) format="PLY" ;;
esac

bytes=$(wc -c < "$target_path" | tr -d ' ')
file_size=$(awk -v bytes="$bytes" 'BEGIN {
  if (bytes >= 1048576) {
    printf "%.2f MB", bytes / 1048576
  } else if (bytes >= 1024) {
    printf "%.1f KB", bytes / 1024
  } else {
    printf "%d B", bytes
  }
}')

safe_title="${title//\\/\\\\}"
safe_title="${safe_title//\"/\\\"}"
safe_target="${target_name//\\/\\\\}"
safe_target="${safe_target//\"/\\\"}"
safe_preview="$preview_name"
safe_preview="${safe_preview//\\/\\\\}"
safe_preview="${safe_preview//\"/\\\"}"
safe_format="${format//\\/\\\\}"
safe_format="${safe_format//\"/\\\"}"
safe_file_size="${file_size//\\/\\\\}"
safe_file_size="${safe_file_size//\"/\\\"}"
safe_capture="${SCENE_CAPTURE:-}"
safe_capture="${safe_capture//\\/\\\\}"
safe_capture="${safe_capture//\"/\\\"}"
safe_training="${SCENE_TRAINING:-}"
safe_training="${safe_training//\\/\\\\}"
safe_training="${safe_training//\"/\\\"}"
safe_delivery="${SCENE_DELIVERY:-}"
safe_delivery="${safe_delivery//\\/\\\\}"
safe_delivery="${safe_delivery//\"/\\\"}"

metadata_lines=()
if [[ -n "$safe_preview" ]]; then
  metadata_lines+=("  \"previewAssetUrl\": \"assets/$safe_preview\",")
fi
if [[ -n "$safe_capture" ]]; then
  metadata_lines+=("  \"capture\": \"$safe_capture\",")
fi
if [[ -n "$safe_training" ]]; then
  metadata_lines+=("  \"training\": \"$safe_training\",")
fi
if [[ -n "$safe_delivery" ]]; then
  metadata_lines+=("  \"delivery\": \"$safe_delivery\",")
fi

cat > public/scene.json <<JSON
{
  "title": "$safe_title",
  "assetUrl": "assets/$safe_target",
  "format": "$safe_format",
  "fileSize": "$safe_file_size",
$(printf '%s\n' "${metadata_lines[@]}")
  "camera": {
    "position": [0, 0, 3]
  }
}
JSON

echo "Prepared $target_path"
echo "Open SuperSplat for inspection: https://superspl.at/editor"
echo "Preview locally: npm run serve"
