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
    config.training,
    config.delivery
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

async function loadAsset(asset, app) {
  await createAssetLoader([asset], app);
  return asset;
}

function installOrbitControls(canvas, camera) {
  const target = { x: 0, y: 0, z: 0 };
  const orbit = {
    yaw: 0,
    pitch: 0,
    distance: camera.getPosition().length()
  };
  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  function updateCamera() {
    const cosPitch = Math.cos(orbit.pitch);
    const x = Math.sin(orbit.yaw) * cosPitch * orbit.distance;
    const y = Math.sin(orbit.pitch) * orbit.distance;
    const z = Math.cos(orbit.yaw) * cosPitch * orbit.distance;
    camera.setPosition(x, y, z);
    camera.lookAt(target.x, target.y, target.z);
  }

  canvas.addEventListener('pointerdown', (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener('pointermove', (event) => {
    if (!dragging) {
      return;
    }

    orbit.yaw -= (event.clientX - lastX) * 0.006;
    orbit.pitch = Math.max(-1.2, Math.min(1.2, orbit.pitch - (event.clientY - lastY) * 0.006));
    lastX = event.clientX;
    lastY = event.clientY;
    updateCamera();
  });

  canvas.addEventListener('pointerup', (event) => {
    dragging = false;
    canvas.releasePointerCapture(event.pointerId);
  });

  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    orbit.distance = Math.max(0.5, Math.min(12, orbit.distance + event.deltaY * 0.003));
    updateCamera();
  }, { passive: false });

  updateCamera();
}

async function boot() {
  const bootStart = performance.now();
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

  const camera = new Entity('Camera');
  const cameraPosition = config.camera?.position || [0, 0, 3];
  camera.setPosition(cameraPosition[0], cameraPosition[1], cameraPosition[2]);
  camera.addComponent('camera');
  app.root.addChild(camera);
  installOrbitControls(canvas, camera);

  const previewAssetUrl = config.previewAssetUrl || config.assetUrl;
  const previewAsset = await loadAsset(new Asset('capture-preview', 'gsplat', {
    url: previewAssetUrl
  }), app);

  const splat = new Entity('Gaussian Splat');
  splat.setPosition(0, 0, 0);
  splat.addComponent('gsplat', { asset: previewAsset });
  app.root.addChild(splat);
  setStatus('Ready');
  window.__splatterMetrics = {
    previewReadyMs: Math.round(performance.now() - bootStart),
    highQualityReadyMs: null
  };

  if (config.assetUrl && config.assetUrl !== previewAssetUrl) {
    loadAsset(new Asset('capture-high-quality', 'gsplat', {
      url: config.assetUrl
    }), app).then((highQualityAsset) => {
      splat.removeComponent('gsplat');
      splat.addComponent('gsplat', { asset: highQualityAsset });
      window.__splatterMetrics.highQualityReadyMs = Math.round(performance.now() - bootStart);
      setStatus('Ready · HQ');
    }).catch((error) => {
      console.error(error);
      setStatus('Ready · HQ failed');
    });
  }
}

boot().catch((error) => {
  console.error(error);
  showEmpty('Scene failed to load');
});
