#!/usr/bin/env zsh
set -euo pipefail

scene_file="public/scene.json"
index_file="public/index.html"
main_file="public/main.js"
max_asset_bytes=$((25 * 1024 * 1024))
max_public_bytes="${SPLAT_MAX_PUBLIC_BYTES:-$((180 * 1024 * 1024))}"

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
  if (config.voxelGridAssetUrl) {
    assertPublicRelative(config.voxelGridAssetUrl, `${file} voxelGridAssetUrl`);
  }
  if (config.voxelGridUrl) {
    assertPublicRelative(config.voxelGridUrl, `${file} voxelGridUrl`);
  }
  if (config.freeSpaceGridUrl) {
    assertPublicRelative(config.freeSpaceGridUrl, `${file} freeSpaceGridUrl`);
  }
  if (config.freeSpaceGridAssetUrl) {
    assertPublicRelative(config.freeSpaceGridAssetUrl, `${file} freeSpaceGridAssetUrl`);
  }
  if (config.navigableGridAssetUrl) {
    assertPublicRelative(config.navigableGridAssetUrl, `${file} navigableGridAssetUrl`);
  }
  if (config.semanticVoxelUrl) {
    assertPublicRelative(config.semanticVoxelUrl, `${file} semanticVoxelUrl`);
  }
  if (config.semanticVoxelAssetUrl) {
    assertPublicRelative(config.semanticVoxelAssetUrl, `${file} semanticVoxelAssetUrl`);
  }
  if (config.samSemanticVoxelUrl) {
    assertPublicRelative(config.samSemanticVoxelUrl, `${file} samSemanticVoxelUrl`);
  }
  if (config.samSemanticVoxelAssetUrl) {
    assertPublicRelative(config.samSemanticVoxelAssetUrl, `${file} samSemanticVoxelAssetUrl`);
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
  return [
    config.assetUrl,
    config.previewAssetUrl,
    config.pointCloudAssetUrl,
    config.voxelGridAssetUrl,
    config.voxelGridUrl,
    config.freeSpaceGridUrl,
    config.freeSpaceGridAssetUrl,
    config.navigableGridAssetUrl,
    config.semanticVoxelUrl,
    config.semanticVoxelAssetUrl,
    config.samSemanticVoxelUrl,
    config.samSemanticVoxelAssetUrl,
    config.textureAssetUrl
  ].filter(Boolean);
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

  const pipelinePath = "public/pipeline-manifest.json";
  if (!fs.existsSync(pipelinePath)) {
    throw new Error("Missing public/pipeline-manifest.json");
  }
  const pipeline = readJson(pipelinePath);
  if (!Array.isArray(manifest.primaryTargets) || manifest.primaryTargets.length === 0) {
    throw new Error("scenes.json requires primaryTargets");
  }
  if (!Array.isArray(pipeline.primaryTargets)) {
    throw new Error("pipeline-manifest.json requires primaryTargets");
  }
  const scenePrimaryTargets = [...manifest.primaryTargets].sort();
  const pipelinePrimaryTargets = [...pipeline.primaryTargets].sort();
  if (JSON.stringify(scenePrimaryTargets) !== JSON.stringify(pipelinePrimaryTargets)) {
    throw new Error("pipeline-manifest.json primaryTargets must match scenes.json primaryTargets");
  }
  if (!Array.isArray(pipeline.inputs)) {
    throw new Error("pipeline-manifest.json requires inputs");
  }
  if (!pipeline.localPolicy || !pipeline.externalAccelerators) {
    throw new Error("pipeline-manifest.json requires localPolicy and externalAccelerators");
  }
  if (pipeline.externalAccelerators.sam3dObjects?.execution !== "external-cuda-worker") {
    throw new Error("pipeline-manifest.json must mark SAM 3D as an external CUDA worker");
  }
  for (const primaryTarget of manifest.primaryTargets) {
    const input = pipeline.inputs.find((item) => item.inputSlug === primaryTarget);
    if (!input) {
      throw new Error(`pipeline-manifest.json missing primary input ${primaryTarget}`);
    }
    if (input.primaryTarget !== true) {
      throw new Error(`pipeline-manifest.json ${primaryTarget} must be marked primaryTarget`);
    }
    if (input.stageStatus !== "staged") {
      throw new Error(`pipeline-manifest.json ${primaryTarget} must be staged`);
    }
    if (!Array.isArray(input.nextActions) || input.nextActions.join(",") !== "ready") {
      throw new Error(`pipeline-manifest.json ${primaryTarget} must be ready`);
    }
    const sceneUrl = input.staged && input.staged.sceneUrl;
    if (!sceneUrl) {
      throw new Error(`pipeline-manifest.json ${primaryTarget} missing staged.sceneUrl`);
    }
    const scene = manifest.scenes.find((entry) => entry.primaryTarget === true && entry.sceneUrl === sceneUrl);
    if (!scene) {
      throw new Error(`scenes.json missing primary scene for ${primaryTarget}: ${sceneUrl}`);
    }
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
  *.sog|*.ply|*.compressed.ply|*.png|*.json) ;;
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

unreferenced_assets=$(ASSET_URLS="$asset_urls" node <<'NODE'
const fs = require("fs");
const path = require("path");

const referenced = new Set(process.env.ASSET_URLS.split(/\r?\n/).filter(Boolean));
const allowUnreferenced = new Set(["assets/.gitkeep"]);
const unreferenced = [];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath);
    } else if (entry.isFile()) {
      const publicPath = fullPath.replace(/^public\//, "");
      if (!referenced.has(publicPath) && !allowUnreferenced.has(publicPath)) {
        unreferenced.push(publicPath);
      }
    }
  }
}

walk("public/assets");
for (const asset of unreferenced.sort()) {
  console.log(asset);
}
NODE
)

if [[ -n "$unreferenced_assets" ]]; then
  echo "Unreferenced public assets found:" >&2
  printf '%s\n' "$unreferenced_assets" >&2
  exit 1
fi

public_bytes=$(node <<'NODE'
const fs = require("fs");
const path = require("path");

function totalBytes(dir) {
  let total = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      total += totalBytes(fullPath);
    } else if (entry.isFile()) {
      total += fs.statSync(fullPath).size;
    }
  }
  return total;
}

console.log(totalBytes("public"));
NODE
)

if (( public_bytes > max_public_bytes )); then
  echo "public/ exceeds Pages asset budget: $public_bytes bytes > $max_public_bytes bytes" >&2
  exit 1
fi

echo "Public asset budget: $public_bytes / $max_public_bytes bytes"
