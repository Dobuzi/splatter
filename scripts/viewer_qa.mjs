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
  for (const key of ['assetUrl', 'textureAssetUrl', 'pointCloudAssetUrl', 'voxelGridAssetUrl', 'voxelGridUrl', 'freeSpaceGridUrl', 'freeSpaceGridAssetUrl', 'navigableGridAssetUrl', 'semanticVoxelUrl', 'semanticVoxelAssetUrl', 'samSemanticVoxelUrl', 'samSemanticVoxelAssetUrl']) {
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
  if ((config.freeSpaceGridAssetUrl || config.navigableGridAssetUrl) && !config.metrics?.freeSpaceGrid) {
    failures.push(`${scene.id}: free-space assets require metrics.freeSpaceGrid`);
  }
  if (config.semanticVoxelAssetUrl && !config.metrics?.semanticVoxels) {
    failures.push(`${scene.id}: semanticVoxelAssetUrl requires metrics.semanticVoxels`);
  }
  if (config.samSemanticVoxelAssetUrl && !config.metrics?.samSemanticVoxels) {
    failures.push(`${scene.id}: samSemanticVoxelAssetUrl requires metrics.samSemanticVoxels`);
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
if (!indexHtml.includes('data-action="render-free-space"') || !indexHtml.includes('data-action="render-navigable"')) {
  failures.push('viewer is missing free-space render mode controls');
}
if (!indexHtml.includes('data-action="render-semantics"')) {
  failures.push('viewer is missing semantic voxel render mode controls');
}
if (!indexHtml.includes('data-action="render-sam-semantics"')) {
  failures.push('viewer is missing SAM-mask semantic render mode controls');
}
if (!indexHtml.includes('id="pipelineSummary"')) {
  failures.push('viewer is missing the pipeline summary surface');
}
if (!indexHtml.includes('id="hudDetailsToggle"') || !indexHtml.includes('id="hudDetails"')) {
  failures.push('viewer is missing the collapsible HUD details controls');
}
if (!pipelineManifest.localPolicy || pipelineManifest.externalAccelerators?.sam3dObjects?.execution !== 'external-cuda-worker') {
  failures.push('pipeline manifest must expose local policy and external accelerator status');
}
if (!mainJs.includes('voxelSizeStorageKey') || !mainJs.includes('uPointSize')) {
  failures.push('viewer is missing persisted voxel point size rendering');
}
if (!mainJs.includes('freeSpaceGridAssetUrl') || !mainJs.includes('navigableGridAssetUrl')) {
  failures.push('viewer is missing free/navigable voxel loading');
}
if (!mainJs.includes('semanticVoxelAssetUrl')) {
  failures.push('viewer is missing semantic voxel loading');
}
if (!mainJs.includes('samSemanticVoxelAssetUrl')) {
  failures.push('viewer is missing SAM-mask semantic voxel loading');
}
if (!mainJs.includes('setPipelineSummary') || !mainJs.includes('pipelineSummaryItems')) {
  failures.push('viewer is missing pipeline summary rendering');
}
if (!mainJs.includes('installHudDetailsToggle') || !mainJs.includes('detailsCollapsed')) {
  failures.push('viewer is missing persisted HUD details collapse handling');
}
if (!mainJs.includes('scene.label || scene.input || scene.id')) {
  failures.push('scene selector should prefer distinct scene labels over raw input names');
}
if (!mainJs.includes('colors.push(red, green, blue, 255)')) {
  failures.push('PLY vertex colors must stay in 0-255 byte space for PlayCanvas createMesh');
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Viewer QA manifest checks passed for ${manifest.scenes.length} scenes and ${scenePrimaryTargets.size} primary pipeline targets`);
