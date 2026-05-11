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

node - "$title" "$target_name" "$format" "$file_size" "$preview_name" <<'NODE'
const fs = require('fs');

const [, , title, targetName, format, fileSize, previewName] = process.argv;
const scenePath = 'public/scene.json';
let existing = {};

if (fs.existsSync(scenePath)) {
  existing = JSON.parse(fs.readFileSync(scenePath, 'utf8'));
}

const next = {
  ...existing,
  title,
  assetUrl: `assets/${targetName}`,
  format,
  fileSize
};

if (previewName) {
  next.previewAssetUrl = `assets/${previewName}`;
} else {
  delete next.previewAssetUrl;
}

if (process.env.SCENE_CAPTURE) {
  next.capture = process.env.SCENE_CAPTURE;
}
if (process.env.SCENE_TRAINING) {
  next.training = process.env.SCENE_TRAINING;
}
if (process.env.SCENE_DELIVERY) {
  next.delivery = process.env.SCENE_DELIVERY;
}
if (!next.camera) {
  next.camera = { position: [0, 0, 3] };
}

fs.writeFileSync(scenePath, `${JSON.stringify(next, null, 2)}\n`);
NODE

echo "Prepared $target_path"
echo "Open SuperSplat for inspection: https://superspl.at/editor"
echo "Preview locally: npm run serve"
