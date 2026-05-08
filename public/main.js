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

async function loadSceneConfig() {
  const response = await fetch('scene.json', { cache: 'no-store' });
  if (!response.ok) {
    return null;
  }

  const config = await response.json();
  if (!config.assetUrl) {
    return null;
  }

  return config;
}

function showEmpty() {
  empty.hidden = false;
  title.textContent = 'Gaussian Splat Viewer';
}

async function boot() {
  const config = await loadSceneConfig();
  if (!config) {
    showEmpty();
    return;
  }

  title.textContent = config.title || 'Gaussian Splat Viewer';

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

  const loader = new AssetListLoader(assets, app.assets);
  await new Promise((resolve) => loader.load(resolve));

  const camera = new Entity('Camera');
  camera.setPosition(0, 0, 3);
  camera.addComponent('camera');
  camera.addComponent('script');
  camera.script.create('cameraControls');
  app.root.addChild(camera);

  const splat = new Entity('Gaussian Splat');
  splat.setPosition(0, 0, 0);
  splat.addComponent('gsplat', { asset: assets[1] });
  app.root.addChild(splat);
}

boot().catch((error) => {
  console.error(error);
  showEmpty();
});
