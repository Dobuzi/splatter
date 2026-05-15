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

asset_urls=$(node <<'NODE'
const fs = require("fs");
const path = require("path");

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function assertPublicRelative(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`);
  }
  if (value.startsWith("/") || value.includes("..")) {
    throw new Error(`${label} must be a relative path inside public/`);
  }
}

function validateSceneConfig(config, file) {
  if (!config.title || typeof config.title !== "string") {
    throw new Error(`${file} requires a string title`);
  }
  assertPublicRelative(config.assetUrl, `${file} assetUrl`);
  if (config.previewAssetUrl) {
    assertPublicRelative(config.previewAssetUrl, `${file} previewAssetUrl`);
  }
  if (!["SOG", "PLY", "Compressed PLY", "PLY Mesh"].includes(config.format)) {
    throw new Error(`${file} format must be SOG, PLY, Compressed PLY, or PLY Mesh`);
  }
  if (config.pointCloudAssetUrl) {
    assertPublicRelative(config.pointCloudAssetUrl, `${file} pointCloudAssetUrl`);
  }
  if (config.textureAssetUrl) {
    assertPublicRelative(config.textureAssetUrl, `${file} textureAssetUrl`);
  }
  if (config.viewer) {
    if (typeof config.viewer !== "object" || Array.isArray(config.viewer)) {
      throw new Error(`${file} viewer must be an object when set`);
    }
    if (config.viewer.background !== undefined) {
      if (!Array.isArray(config.viewer.background) || config.viewer.background.length !== 3) {
        throw new Error(`${file} viewer.background must be an RGB array`);
      }
      for (const value of config.viewer.background) {
        if (typeof value !== "number" || value < 0 || value > 1) {
          throw new Error(`${file} viewer.background values must be numbers from 0 to 1`);
        }
      }
    }
    if (config.viewer.fov !== undefined) {
      if (typeof config.viewer.fov !== "number" || config.viewer.fov < 20 || config.viewer.fov > 90) {
        throw new Error(`${file} viewer.fov must be a number from 20 to 90`);
      }
    }
  }
  return [config.assetUrl, config.previewAssetUrl, config.pointCloudAssetUrl, config.textureAssetUrl].filter(Boolean);
}

const assetUrls = new Set(validateSceneConfig(readJson("public/scene.json"), "scene.json"));

if (fs.existsSync("public/scenes.json")) {
  const manifest = readJson("public/scenes.json");
  if (!Array.isArray(manifest.scenes) || manifest.scenes.length === 0) {
    throw new Error("scenes.json requires a non-empty scenes array");
  }
  const ids = new Set();
  for (const scene of manifest.scenes) {
    if (!scene.id || typeof scene.id !== "string") {
      throw new Error("scenes.json scene.id must be a string");
    }
    if (ids.has(scene.id)) {
      throw new Error(`Duplicate scene id: ${scene.id}`);
    }
    ids.add(scene.id);
    assertPublicRelative(scene.sceneUrl, `scenes.json ${scene.id} sceneUrl`);
    const scenePath = path.join("public", scene.sceneUrl);
    if (!fs.existsSync(scenePath)) {
      throw new Error(`Missing scene config: ${scenePath}`);
    }
    for (const assetUrl of validateSceneConfig(readJson(scenePath), scene.sceneUrl)) {
      assetUrls.add(assetUrl);
    }
  }
  if (manifest.defaultScene && !ids.has(manifest.defaultScene)) {
    throw new Error("scenes.json defaultScene must match a scene id");
  }
}

for (const assetUrl of assetUrls) {
  console.log(assetUrl);
}
NODE
)

for asset_url in ${(f)asset_urls}; do
asset_path="public/$asset_url"

if [[ ! -f "$asset_path" ]]; then
  echo "Missing scene asset: $asset_path" >&2
  exit 1
fi

case "$asset_path" in
  *.sog|*.ply|*.compressed.ply|*.png) ;;
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
