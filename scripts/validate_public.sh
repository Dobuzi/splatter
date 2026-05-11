#!/usr/bin/env zsh
set -euo pipefail

scene_file="public/scene.json"
index_file="public/index.html"
main_file="public/main.js"
max_asset_bytes=$((25 * 1024 * 1024))

if [[ ! -f "$index_file" ]]; then
  echo "Missing $index_file" >&2
  exit 1
fi

if [[ ! -f "$main_file" ]]; then
  echo "Missing $main_file" >&2
  exit 1
fi

if [[ ! -f "$scene_file" ]]; then
  echo "Missing $scene_file" >&2
  exit 1
fi

asset_urls=$(node -e '
const fs = require("fs");
const config = JSON.parse(fs.readFileSync("public/scene.json", "utf8"));
if (!config.title || typeof config.title !== "string") {
  throw new Error("scene.json requires a string title");
}
if (!config.assetUrl || typeof config.assetUrl !== "string") {
  throw new Error("scene.json requires a string assetUrl");
}
if (config.assetUrl.startsWith("/") || config.assetUrl.includes("..")) {
  throw new Error("assetUrl must be a relative path inside public/");
}
if (config.previewAssetUrl) {
  if (typeof config.previewAssetUrl !== "string") {
    throw new Error("scene.json previewAssetUrl must be a string when set");
  }
  if (config.previewAssetUrl.startsWith("/") || config.previewAssetUrl.includes("..")) {
    throw new Error("previewAssetUrl must be a relative path inside public/");
  }
}
if (!["SOG", "PLY", "Compressed PLY"].includes(config.format)) {
  throw new Error("scene.json format must be SOG, PLY, or Compressed PLY");
}
if (config.viewer) {
  if (typeof config.viewer !== "object" || Array.isArray(config.viewer)) {
    throw new Error("scene.json viewer must be an object when set");
  }
  if (config.viewer.background !== undefined) {
    if (!Array.isArray(config.viewer.background) || config.viewer.background.length !== 3) {
      throw new Error("scene.json viewer.background must be an RGB array");
    }
    for (const value of config.viewer.background) {
      if (typeof value !== "number" || value < 0 || value > 1) {
        throw new Error("scene.json viewer.background values must be numbers from 0 to 1");
      }
    }
  }
  if (config.viewer.fov !== undefined) {
    if (typeof config.viewer.fov !== "number" || config.viewer.fov < 20 || config.viewer.fov > 90) {
      throw new Error("scene.json viewer.fov must be a number from 20 to 90");
    }
  }
}
console.log(config.assetUrl);
if (config.previewAssetUrl) {
  console.log(config.previewAssetUrl);
}
')

for asset_url in ${(f)asset_urls}; do
asset_path="public/$asset_url"

if [[ ! -f "$asset_path" ]]; then
  echo "Missing scene asset: $asset_path" >&2
  exit 1
fi

case "$asset_path" in
  *.sog|*.ply|*.compressed.ply) ;;
  *)
    echo "Unsupported scene asset format: $asset_path" >&2
    exit 1
    ;;
esac

asset_bytes=$(wc -c < "$asset_path" | tr -d ' ')
if (( asset_bytes == 0 )); then
  echo "Scene asset is empty: $asset_path" >&2
  exit 1
fi

if (( asset_bytes > max_asset_bytes )); then
  echo "Scene asset exceeds $max_asset_bytes bytes: $asset_path ($asset_bytes bytes)" >&2
  exit 1
fi

echo "Validated public viewer"
echo "Scene asset: $asset_path"
echo "Asset bytes: $asset_bytes"
done
