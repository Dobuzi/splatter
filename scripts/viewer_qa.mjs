#!/usr/bin/env node
import fs from 'node:fs';

const manifest = JSON.parse(fs.readFileSync('public/scenes.json', 'utf8'));
const pipelineManifest = JSON.parse(fs.readFileSync('public/pipeline-manifest.json', 'utf8'));
const indexHtml = fs.readFileSync('public/index.html', 'utf8');
const mainJs = fs.readFileSync('public/main.js', 'utf8');
const failures = [];
const scenePrimaryTargets = new Set(manifest.primaryTargets || []);
const pipelinePrimaryTargets = new Set(pipelineManifest.primaryTargets || []);

for (const scene of manifest.scenes || []) {
  const config = JSON.parse(fs.readFileSync(`public/${scene.sceneUrl}`, 'utf8'));
  for (const key of ['assetUrl', 'textureAssetUrl', 'pointCloudAssetUrl', 'voxelGridAssetUrl', 'voxelGridUrl']) {
    if (!config[key]) continue;
    const path = `public/${config[key]}`;
    if (!fs.existsSync(path)) {
      failures.push(`${scene.id}: missing ${key} ${config[key]}`);
    }
  }
  if (config.format === 'PLY Mesh' && config.pointCloudAssetUrl && !config.metrics?.pointCloud) {
    failures.push(`${scene.id}: pointCloudAssetUrl requires metrics.pointCloud`);
  }
  if (config.voxelGridAssetUrl && !config.metrics?.voxelGrid) {
    failures.push(`${scene.id}: voxelGridAssetUrl requires metrics.voxelGrid`);
  }
  if (scene.primaryTarget === true && config.format === 'PLY Mesh' && !config.voxelGridAssetUrl) {
    failures.push(`${scene.id}: primary mesh scene requires voxelGridAssetUrl`);
  }
  if (!Array.isArray(config.camera?.position) || !Array.isArray(config.camera?.target)) {
    failures.push(`${scene.id}: camera framing is missing`);
  }
}

for (const primaryTarget of scenePrimaryTargets) {
  if (!pipelinePrimaryTargets.has(primaryTarget)) {
    failures.push(`pipeline manifest missing primary target ${primaryTarget}`);
  }
  const input = pipelineManifest.inputs?.find((item) => item.inputSlug === primaryTarget);
  if (!input) {
    failures.push(`pipeline manifest missing input ${primaryTarget}`);
    continue;
  }
  if (input.stageStatus !== 'staged' || input.nextActions?.join(',') !== 'ready') {
    failures.push(`${primaryTarget}: pipeline input is not ready`);
  }
  if (!manifest.scenes.some((scene) => scene.primaryTarget === true && scene.sceneUrl === input.staged?.sceneUrl)) {
    failures.push(`${primaryTarget}: staged scene is not exposed as primary in scenes.json`);
  }
}

if (!indexHtml.includes('data-action="voxel-size"')) {
  failures.push('viewer is missing the voxel size control');
}
if (!mainJs.includes('voxelSizeStorageKey') || !mainJs.includes('uPointSize')) {
  failures.push('viewer is missing persisted voxel point size rendering');
}
if (!mainJs.includes('colors.push(red, green, blue, 255)')) {
  failures.push('PLY vertex colors must stay in 0-255 byte space for PlayCanvas createMesh');
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Viewer QA manifest checks passed for ${manifest.scenes.length} scenes and ${scenePrimaryTargets.size} primary pipeline targets`);
