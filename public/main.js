import {
  Application,
  Asset,
  AssetListLoader,
  Color,
  Entity,
  FILLMODE_FILL_WINDOW,
  RESOLUTION_AUTO
} from 'playcanvas';

const empty = document.querySelector('#empty');
const title = document.querySelector('#title');
const status = document.querySelector('#status');
const metadata = document.querySelector('#metadata');

function setStatus(message) {
  status.textContent = message;
}

function setMetadata(config) {
  const parts = [
    config.format,
    config.fileSize,
    config.capture,
    config.training
  ].filter(Boolean);

  metadata.textContent = parts.join(' · ');
  metadata.hidden = parts.length === 0;
}

async function loadSceneConfig() {
  try {
    const response = await fetch('scene.json', { cache: 'no-store' });
    if (!response.ok) {
      return null;
    }

    const config = await response.json();
    if (!config.assetUrl) {
      return null;
    }

    return config;
  } catch {
    return null;
  }
}

function showEmpty(message = 'No scene staged') {
  empty.hidden = false;
  empty.querySelector('h1').textContent = message;
  title.textContent = 'Gaussian Splat Viewer';
  setStatus('Waiting for scene');
  metadata.hidden = true;
}

function createAssetLoader(assets, app) {
  return new Promise((resolve, reject) => {
    const loader = new AssetListLoader(assets, app.assets);
    loader.load((failed) => {
      if (failed && failed.length > 0) {
        reject(new Error(`Failed to load ${failed.map((asset) => asset.name).join(', ')}`));
        return;
      }

      resolve();
    });
  });
}

async function boot() {
  const config = await loadSceneConfig();
  if (!config) {
    showEmpty();
    return;
  }

  title.textContent = config.title || 'Gaussian Splat Viewer';
  setStatus('Loading scene');
  setMetadata(config);

  const canvas = document.createElement('canvas');
  document.body.appendChild(canvas);

  const app = new Application(canvas, {
    graphicsDeviceOptions: {
      antialias: false
    }
  });

  app.setCanvasFillMode(FILLMODE_FILL_WINDOW);
  app.setCanvasResolution(RESOLUTION_AUTO);
  app.scene.clearColor = new Color(0.02, 0.025, 0.03);
  app.start();

  window.addEventListener('resize', () => app.resizeCanvas());

  const assets = [
    new Asset('camera-controls', 'script', {
      url: 'https://cdn.jsdelivr.net/npm/playcanvas/scripts/esm/camera-controls.mjs'
    }),
    new Asset('capture', 'gsplat', {
      url: config.assetUrl
    })
  ];

  await createAssetLoader(assets, app);

  const camera = new Entity('Camera');
  const cameraPosition = config.camera?.position || [0, 0, 3];
  camera.setPosition(cameraPosition[0], cameraPosition[1], cameraPosition[2]);
  camera.addComponent('camera');
  camera.addComponent('script');
  camera.script.create('cameraControls');
  app.root.addChild(camera);

  const splat = new Entity('Gaussian Splat');
  splat.setPosition(0, 0, 0);
  splat.addComponent('gsplat', { asset: assets[1] });
  app.root.addChild(splat);
  setStatus('Ready');
}

boot().catch((error) => {
  console.error(error);
  showEmpty('Scene failed to load');
});
