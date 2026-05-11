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
const tools = document.querySelector('#tools');

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

function vec3FromConfig(value, fallback) {
  return Array.isArray(value) && value.length === 3
    ? { x: value[0], y: value[1], z: value[2] }
    : fallback;
}

function tupleFromConfig(value, fallback) {
  return Array.isArray(value) && value.length === 3
    ? value.map(Number)
    : [...fallback];
}

function numberFromConfig(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

function transformStorageKey(config) {
  return `splatter:transform:${config.assetUrl}`;
}

function baseTransform(config) {
  const pivot = tupleFromConfig(config.transform?.pivot, config.camera?.target || [0, 0, 0]);
  return {
    pivot,
    position: tupleFromConfig(config.transform?.position, [0, 0, 0]),
    rotation: tupleFromConfig(config.transform?.rotation, [0, 0, 0]),
    scale: tupleFromConfig(config.transform?.scale, [1, 1, 1])
  };
}

function loadSavedTransform(config) {
  try {
    const saved = localStorage.getItem(transformStorageKey(config));
    if (!saved) {
      return null;
    }
    const parsed = JSON.parse(saved);
    return {
      pivot: tupleFromConfig(parsed.pivot, config.transform?.pivot || config.camera?.target || [0, 0, 0]),
      position: tupleFromConfig(parsed.position, [0, 0, 0]),
      rotation: tupleFromConfig(parsed.rotation, [0, 0, 0]),
      scale: tupleFromConfig(parsed.scale, [1, 1, 1])
    };
  } catch {
    return null;
  }
}

function cloneTransform(transform) {
  return {
    pivot: [...transform.pivot],
    position: [...transform.position],
    rotation: [...transform.rotation],
    scale: [...transform.scale]
  };
}

function applySplatTransform(root, child, transform) {
  root.setPosition(
    transform.pivot[0] + transform.position[0],
    transform.pivot[1] + transform.position[1],
    transform.pivot[2] + transform.position[2]
  );
  root.setEulerAngles(transform.rotation[0], transform.rotation[1], transform.rotation[2]);
  root.setLocalScale(transform.scale[0], transform.scale[1], transform.scale[2]);
  child.setLocalPosition(-transform.pivot[0], -transform.pivot[1], -transform.pivot[2]);
}

function installTransformTools(config, root, child, transform) {
  if (!tools) {
    return;
  }

  function save() {
    localStorage.setItem(transformStorageKey(config), JSON.stringify(transform));
    setStatus('Saved');
  }

  function copyConfig() {
    const nextConfig = {
      ...config,
      transform: cloneTransform(transform)
    };
    navigator.clipboard?.writeText(JSON.stringify(nextConfig, null, 2));
    setStatus('Copied JSON');
  }

  function reset() {
    const next = baseTransform(config);
    transform.pivot = next.pivot;
    transform.position = next.position;
    transform.rotation = next.rotation;
    transform.scale = next.scale;
    localStorage.removeItem(transformStorageKey(config));
    applySplatTransform(root, child, transform);
    setStatus('Reset');
  }

  tools.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) {
      return;
    }

    const action = button.dataset.action;
    if (action === 'flip-x') {
      transform.scale[0] *= -1;
    } else if (action === 'flip-y') {
      transform.scale[1] *= -1;
    } else if (action === 'flip-z') {
      transform.scale[2] *= -1;
    } else if (action === 'rotate-x') {
      transform.rotation[0] = (transform.rotation[0] + 90) % 360;
    } else if (action === 'rotate-y') {
      transform.rotation[1] = (transform.rotation[1] + 90) % 360;
    } else if (action === 'rotate-z') {
      transform.rotation[2] = (transform.rotation[2] + 90) % 360;
    } else if (action === 'save') {
      save();
      return;
    } else if (action === 'copy') {
      copyConfig();
      return;
    } else if (action === 'reset') {
      reset();
      return;
    }

    applySplatTransform(root, child, transform);
    setStatus('Adjusted');
  });

  window.__splatterTransform = {
    getState: () => cloneTransform(transform),
    setState: (nextTransform) => {
      transform.pivot = tupleFromConfig(nextTransform.pivot, transform.pivot);
      transform.position = tupleFromConfig(nextTransform.position, transform.position);
      transform.rotation = tupleFromConfig(nextTransform.rotation, transform.rotation);
      transform.scale = tupleFromConfig(nextTransform.scale, transform.scale);
      applySplatTransform(root, child, transform);
    },
    save,
    reset
  };
}

function installOrbitControls(canvas, camera, config) {
  const target = vec3FromConfig(config.camera?.target, { x: 0, y: 0, z: 0 });
  const startPosition = camera.getPosition();
  const offset = {
    x: startPosition.x - target.x,
    y: startPosition.y - target.y,
    z: startPosition.z - target.z
  };
  const startDistance = Math.hypot(offset.x, offset.y, offset.z);
  const minDistance = config.camera?.minDistance || 0.2;
  const maxDistance = config.camera?.maxDistance || 20;
  const orbit = {
    yaw: Math.atan2(offset.x, offset.z),
    pitch: Math.asin(offset.y / Math.max(startDistance, 0.0001)),
    distance: config.camera?.distance || startDistance
  };
  const pointers = new Map();
  let gesture = null;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function updateCamera() {
    const cosPitch = Math.cos(orbit.pitch);
    const x = Math.sin(orbit.yaw) * cosPitch * orbit.distance;
    const y = Math.sin(orbit.pitch) * orbit.distance;
    const z = Math.cos(orbit.yaw) * cosPitch * orbit.distance;
    camera.setPosition(target.x + x, target.y + y, target.z + z);
    camera.lookAt(target.x, target.y, target.z);
  }

  function panBy(deltaX, deltaY) {
    const position = camera.getPosition();
    const forward = {
      x: target.x - position.x,
      y: target.y - position.y,
      z: target.z - position.z
    };
    const forwardLength = Math.hypot(forward.x, forward.y, forward.z) || 1;
    forward.x /= forwardLength;
    forward.y /= forwardLength;
    forward.z /= forwardLength;

    const right = {
      x: forward.z,
      y: 0,
      z: -forward.x
    };
    const rightLength = Math.hypot(right.x, right.y, right.z) || 1;
    right.x /= rightLength;
    right.z /= rightLength;

    const up = {
      x: right.y * forward.z - right.z * forward.y,
      y: right.z * forward.x - right.x * forward.z,
      z: right.x * forward.y - right.y * forward.x
    };
    const panScale = orbit.distance * 0.0015;
    target.x += (-deltaX * right.x + deltaY * up.x) * panScale;
    target.y += (-deltaX * right.y + deltaY * up.y) * panScale;
    target.z += (-deltaX * right.z + deltaY * up.z) * panScale;
    updateCamera();
  }

  function zoomBy(delta) {
    orbit.distance = clamp(orbit.distance * Math.exp(delta * 0.0015), minDistance, maxDistance);
    updateCamera();
  }

  function pointerDistance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function pointerMidpoint(a, b) {
    return {
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2
    };
  }

  function currentPointerPair() {
    return Array.from(pointers.values()).slice(0, 2);
  }

  canvas.addEventListener('pointerdown', (event) => {
    pointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
      button: event.button,
      buttons: event.buttons,
      pointerType: event.pointerType
    });
    if (pointers.size === 2) {
      const [a, b] = currentPointerPair();
      gesture = {
        distance: pointerDistance(a, b),
        midpoint: pointerMidpoint(a, b)
      };
    }
    try {
      canvas.setPointerCapture(event.pointerId);
    } catch {
      // Synthetic touch tests and some browser edge cases can lack an active pointer.
    }
  });

  canvas.addEventListener('pointermove', (event) => {
    const previous = pointers.get(event.pointerId);
    if (!previous) {
      return;
    }

    pointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
      button: previous.button,
      buttons: event.buttons,
      pointerType: event.pointerType
    });

    if (pointers.size >= 2) {
      const [a, b] = currentPointerPair();
      const nextDistance = pointerDistance(a, b);
      const nextMidpoint = pointerMidpoint(a, b);
      if (gesture) {
        zoomBy(gesture.distance - nextDistance);
        panBy(nextMidpoint.x - gesture.midpoint.x, nextMidpoint.y - gesture.midpoint.y);
      }
      gesture = {
        distance: nextDistance,
        midpoint: nextMidpoint
      };
      return;
    }

    const deltaX = event.clientX - previous.x;
    const deltaY = event.clientY - previous.y;
    const isPan = event.shiftKey || event.altKey || event.button === 1 || event.button === 2 || (event.buttons & 4) || (event.buttons & 2);

    if (isPan) {
      panBy(deltaX, deltaY);
    } else {
      orbit.yaw -= deltaX * 0.006;
      orbit.pitch = clamp(orbit.pitch - deltaY * 0.006, -1.35, 1.35);
      updateCamera();
    }
  });

  function endPointer(event) {
    pointers.delete(event.pointerId);
    gesture = null;
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
  }

  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('contextmenu', (event) => event.preventDefault());

  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    if (event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
      panBy(event.deltaX, event.deltaY);
    } else {
      zoomBy(event.deltaY);
    }
  }, { passive: false });

  window.__splatterControls = {
    getState: () => ({
      target: { ...target },
      yaw: orbit.yaw,
      pitch: orbit.pitch,
      distance: orbit.distance,
      position: camera.getPosition().toArray()
    })
  };
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
  const background = tupleFromConfig(config.viewer?.background, [0.02, 0.025, 0.03]);
  app.scene.clearColor = new Color(background[0], background[1], background[2]);
  app.start();

  window.addEventListener('resize', () => app.resizeCanvas());

  const camera = new Entity('Camera');
  const cameraPosition = config.camera?.position || [0, 0, 3];
  camera.setPosition(cameraPosition[0], cameraPosition[1], cameraPosition[2]);
  camera.addComponent('camera', {
    fov: numberFromConfig(config.viewer?.fov, 45)
  });
  app.root.addChild(camera);
  installOrbitControls(canvas, camera, config);

  const previewAssetUrl = config.previewAssetUrl || config.assetUrl;
  const previewAsset = await loadAsset(new Asset('capture-preview', 'gsplat', {
    url: previewAssetUrl
  }), app);

  const transform = loadSavedTransform(config) || baseTransform(config);
  const splatRoot = new Entity('Splat Transform');
  const splat = new Entity('Gaussian Splat');
  app.root.addChild(splatRoot);
  splatRoot.addChild(splat);
  splat.setPosition(0, 0, 0);
  applySplatTransform(splatRoot, splat, transform);
  installTransformTools(config, splatRoot, splat, transform);
  splat.addComponent('gsplat', { asset: previewAsset });
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
