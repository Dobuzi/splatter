#!/usr/bin/env node
import fs from 'node:fs';

const manifest = JSON.parse(fs.readFileSync('public/scenes.json', 'utf8'));
const failures = [];

for (const scene of manifest.scenes || []) {
  const config = JSON.parse(fs.readFileSync(`public/${scene.sceneUrl}`, 'utf8'));
  for (const key of ['assetUrl', 'textureAssetUrl', 'pointCloudAssetUrl']) {
    if (!config[key]) continue;
    const path = `public/${config[key]}`;
    if (!fs.existsSync(path)) {
      failures.push(`${scene.id}: missing ${key} ${config[key]}`);
    }
  }
  if (config.format === 'PLY Mesh' && config.pointCloudAssetUrl && !config.metrics?.pointCloud) {
    failures.push(`${scene.id}: pointCloudAssetUrl requires metrics.pointCloud`);
  }
  if (!Array.isArray(config.camera?.position) || !Array.isArray(config.camera?.target)) {
    failures.push(`${scene.id}: camera framing is missing`);
  }
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Viewer QA manifest checks passed for ${manifest.scenes.length} scenes`);
