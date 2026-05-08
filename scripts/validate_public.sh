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

asset_url=$(node -e '
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
if (!["SOG", "PLY", "Compressed PLY"].includes(config.format)) {
  throw new Error("scene.json format must be SOG, PLY, or Compressed PLY");
}
console.log(config.assetUrl);
')

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
