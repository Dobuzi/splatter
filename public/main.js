import {
  Application,
  Asset,
  AssetListLoader,
  Color,
  Entity,
  FILLMODE_FILL_WINDOW,
  MeshInstance,
  PRIMITIVE_POINTS,
  RESOLUTION_AUTO,
  StandardMaterial,
  createMesh
} from 'playcanvas';

const empty = document.querySelector('#empty');
const title = document.querySelector('#title');
const status = document.querySelector('#status');
const metadata = document.querySelector('#metadata');
const qualityBadges = document.querySelector('#qualityBadges');
const pipelineStatus = document.querySelector('#pipelineStatus');
const tools = document.querySelector('#tools');
const sceneSelect = document.querySelector('#sceneSelect');

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
  setQualityBadges(config);
}

function formatRatio(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : null;
}

function setQualityBadges(config) {
  if (!qualityBadges) {
    return;
  }
  const quality = config.quality || {};
  const metrics = config.metrics || {};
  const badges = [];
  if (config.primaryTarget || quality.primaryTarget) {
    badges.push('Primary');
  }
  if (Number.isFinite(quality.registrationRatio)) {
    badges.push(`Reg ${formatRatio(quality.registrationRatio)}`);
  }
  if (Number.isFinite(quality.blurRejectRatio)) {
    badges.push(`Blur reject ${formatRatio(quality.blurRejectRatio)}`);
  }
  const largestRatio = Number.isFinite(quality.largestComponentRatio)
    ? quality.largestComponentRatio
    : metrics.largestComponentRatio;
  if (Number.isFinite(largestRatio)) {
    badges.push(`Largest ${formatRatio(largestRatio)}`);
  }
  const componentCount = quality.componentCount ?? metrics.componentCount;
  if (Number.isFinite(componentCount)) {
    badges.push(`${componentCount} comp`);
  }
  if (Number.isFinite(quality.score)) {
    badges.push(`Score ${Math.round(quality.score)}`);
  }

  qualityBadges.replaceChildren(...badges.map((label) => {
    const badge = document.createElement('span');
    badge.textContent = label;
    return badge;
  }));
  qualityBadges.hidden = badges.length === 0;
}

function setPipelineStatus(pipelineManifest, activeScene, config) {
  if (!pipelineStatus) {
    return;
  }

  const item = pipelineInputForScene(pipelineManifest, activeScene, config);
  if (!item) {
    pipelineStatus.hidden = true;
    return;
  }

  const state = item.stageStatus === 'staged' && item.nextActions?.includes('ready')
    ? 'ready'
    : item.stageStatus || 'pending';
  const prefix = item.primaryTarget ? 'Primary pipeline' : 'Pipeline';
  const suffix = item.selectedCapture ? ` · ${item.selectedCapture}` : '';
  pipelineStatus.textContent = `${prefix} ${state}${suffix}`;
  pipelineStatus.title = item.nextActions?.length ? `Next: ${item.nextActions.join(', ')}` : '';
  pipelineStatus.hidden = false;
}

function pipelineInputForScene(pipelineManifest, activeScene, config) {
  const inputs = pipelineManifest?.inputs;
  if (!Array.isArray(inputs)) {
    return null;
  }

  const activeId = activeScene?.id || '';
  return inputs.find((item) => item.input === activeScene?.input)
    || inputs.find((item) => item.staged?.sceneUrl === activeScene?.sceneUrl)
    || inputs.find((item) => item.inputSlug === activeId || activeId.startsWith(`${item.inputSlug}-`))
    || inputs.find((item) => item.staged?.sceneUrl && config?.assetUrl === item.staged.assetUrl)
    || null;
}

async function loadSceneConfig(sceneUrl = 'scene.json') {
  try {
    const response = await fetch(sceneUrl, { cache: 'no-store' });
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

async function loadPipelineManifest() {
  try {
    const response = await fetch('pipeline-manifest.json', { cache: 'no-store' });
    if (!response.ok) {
      return null;
    }

    const manifest = await response.json();
    if (!Array.isArray(manifest.inputs)) {
      return null;
    }

    return manifest;
  } catch {
    return null;
  }
}

async function loadSceneManifest() {
  try {
    const response = await fetch('scenes.json', { cache: 'no-store' });
    if (!response.ok) {
      return null;
    }

    const manifest = await response.json();
    if (!Array.isArray(manifest.scenes) || manifest.scenes.length === 0) {
      return null;
    }

    return manifest;
  } catch {
    return null;
  }
}

function selectedSceneId(manifest) {
  const requested = new URLSearchParams(window.location.search).get('scene');
  if (requested && manifest.scenes.some((scene) => scene.id === requested)) {
    return requested;
  }

  if (manifest.defaultScene && manifest.scenes.some((scene) => scene.id === manifest.defaultScene)) {
    return manifest.defaultScene;
  }

  return manifest.scenes[0].id;
}

function installSceneSelector(manifest, activeSceneId) {
  if (!sceneSelect || !manifest) {
    return;
  }

  sceneSelect.replaceChildren();
  for (const scene of manifest.scenes) {
    const option = document.createElement('option');
    option.value = scene.id;
    option.textContent = scene.input || scene.label || scene.id;
    sceneSelect.appendChild(option);
  }

  sceneSelect.value = activeSceneId;
  sceneSelect.hidden = manifest.scenes.length < 2;
  sceneSelect.addEventListener('change', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('scene', sceneSelect.value);
    window.location.assign(url);
  });
}

function showEmpty(message = 'No scene staged') {
  empty.hidden = false;
  empty.querySelector('h1').textContent = message;
  title.textContent = 'Gaussian Splat Viewer';
  setStatus('Waiting for scene');
  metadata.hidden = true;
  if (qualityBadges) {
    qualityBadges.hidden = true;
  }
  if (pipelineStatus) {
    pipelineStatus.hidden = true;
  }
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

function isMeshScene(config) {
  return config.format === 'PLY Mesh';
}

function pointCloudStorageKey(config) {
  return `splatter:render-mode:${config.assetUrl}`;
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

function installTransformTools(config, root, children, transform) {
  if (!tools) {
    return;
  }
  const transformChildren = Array.isArray(children) ? children : [children];

  function applyTransform() {
    for (const child of transformChildren) {
      applySplatTransform(root, child, transform);
    }
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
    applyTransform();
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
    } else if (action.startsWith('render-')) {
      return;
    }

    applyTransform();
    setStatus('Adjusted');
  });

  window.__splatterTransform = {
    getState: () => cloneTransform(transform),
    setState: (nextTransform) => {
      transform.pivot = tupleFromConfig(nextTransform.pivot, transform.pivot);
      transform.position = tupleFromConfig(nextTransform.position, transform.position);
      transform.rotation = tupleFromConfig(nextTransform.rotation, transform.rotation);
      transform.scale = tupleFromConfig(nextTransform.scale, transform.scale);
      applyTransform();
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

function plyScalarSize(type) {
  return {
    char: 1,
    uchar: 1,
    int8: 1,
    uint8: 1,
    short: 2,
    ushort: 2,
    int16: 2,
    uint16: 2,
    int: 4,
    uint: 4,
    int32: 4,
    uint32: 4,
    float: 4,
    float32: 4,
    double: 8,
    float64: 8
  }[type];
}

function readPlyScalar(view, offset, type, littleEndian) {
  switch (type) {
    case 'char':
    case 'int8':
      return [view.getInt8(offset), offset + 1];
    case 'uchar':
    case 'uint8':
      return [view.getUint8(offset), offset + 1];
    case 'short':
    case 'int16':
      return [view.getInt16(offset, littleEndian), offset + 2];
    case 'ushort':
    case 'uint16':
      return [view.getUint16(offset, littleEndian), offset + 2];
    case 'int':
    case 'int32':
      return [view.getInt32(offset, littleEndian), offset + 4];
    case 'uint':
    case 'uint32':
      return [view.getUint32(offset, littleEndian), offset + 4];
    case 'float':
    case 'float32':
      return [view.getFloat32(offset, littleEndian), offset + 4];
    case 'double':
    case 'float64':
      return [view.getFloat64(offset, littleEndian), offset + 8];
    default:
      throw new Error(`Unsupported PLY scalar type: ${type}`);
  }
}

function parsePlyHeader(text) {
  const lines = text.split(/\r?\n/);
  const elements = [];
  let format = null;
  let current = null;

  for (const line of lines) {
    const parts = line.trim().split(/\s+/);
    if (parts[0] === 'format') {
      format = parts[1];
    } else if (parts[0] === 'element') {
      current = { name: parts[1], count: Number(parts[2]), properties: [] };
      elements.push(current);
    } else if (parts[0] === 'property' && current) {
      if (parts[1] === 'list') {
        current.properties.push({
          kind: 'list',
          countType: parts[2],
          itemType: parts[3],
          name: parts[4]
        });
      } else {
        current.properties.push({
          kind: 'scalar',
          type: parts[1],
          name: parts[2]
        });
      }
    }
  }

  return { format, elements };
}

function locatePlyBody(buffer) {
  const bytes = new Uint8Array(buffer);
  const marker = new TextEncoder().encode('end_header');
  for (let i = 0; i <= bytes.length - marker.length; i += 1) {
    let matched = true;
    for (let j = 0; j < marker.length; j += 1) {
      if (bytes[i + j] !== marker[j]) {
        matched = false;
        break;
      }
    }
    if (matched) {
      let offset = i + marker.length;
      if (bytes[offset] === 13) {
        offset += 1;
      }
      if (bytes[offset] === 10) {
        offset += 1;
      }
      return offset;
    }
  }
  throw new Error('Invalid PLY header');
}

function computeNormals(positions, indices) {
  const normals = new Array(positions.length).fill(0);
  for (let i = 0; i < indices.length; i += 3) {
    const ia = indices[i] * 3;
    const ib = indices[i + 1] * 3;
    const ic = indices[i + 2] * 3;
    const ab = [
      positions[ib] - positions[ia],
      positions[ib + 1] - positions[ia + 1],
      positions[ib + 2] - positions[ia + 2]
    ];
    const ac = [
      positions[ic] - positions[ia],
      positions[ic + 1] - positions[ia + 1],
      positions[ic + 2] - positions[ia + 2]
    ];
    const normal = [
      ab[1] * ac[2] - ab[2] * ac[1],
      ab[2] * ac[0] - ab[0] * ac[2],
      ab[0] * ac[1] - ab[1] * ac[0]
    ];
    for (const index of [ia, ib, ic]) {
      normals[index] += normal[0];
      normals[index + 1] += normal[1];
      normals[index + 2] += normal[2];
    }
  }
  for (let i = 0; i < normals.length; i += 3) {
    const length = Math.hypot(normals[i], normals[i + 1], normals[i + 2]) || 1;
    normals[i] /= length;
    normals[i + 1] /= length;
    normals[i + 2] /= length;
  }
  return normals;
}

function parseBinaryPly(buffer) {
  const headerBytes = locatePlyBody(buffer);
  const header = new TextDecoder('ascii').decode(buffer.slice(0, headerBytes));
  const parsed = parsePlyHeader(header);
  if (parsed.format !== 'binary_little_endian') {
    throw new Error(`Unsupported PLY format: ${parsed.format}`);
  }

  const view = new DataView(buffer);
  const positions = [];
  const colors = [];
  const sourceFaces = [];
  let offset = headerBytes;

  for (const element of parsed.elements) {
    for (let row = 0; row < element.count; row += 1) {
      if (element.name === 'vertex') {
        let x = 0;
        let y = 0;
        let z = 0;
        let red = 210;
        let green = 218;
        let blue = 230;
        for (const property of element.properties) {
          if (property.kind === 'list') {
            let count;
            [count, offset] = readPlyScalar(view, offset, property.countType, true);
            offset += count * plyScalarSize(property.itemType);
          } else {
            let value;
            [value, offset] = readPlyScalar(view, offset, property.type, true);
            if (property.name === 'x') {
              x = value;
            } else if (property.name === 'y') {
              y = value;
            } else if (property.name === 'z') {
              z = value;
            } else if (property.name === 'red') {
              red = value;
            } else if (property.name === 'green') {
              green = value;
            } else if (property.name === 'blue') {
              blue = value;
            }
          }
        }
        positions.push(x, y, z);
        colors.push(red / 255, green / 255, blue / 255, 1);
      } else if (element.name === 'face') {
        let faceIndices = null;
        let faceTexcoords = null;
        for (const property of element.properties) {
          if (property.kind === 'list') {
            let count;
            [count, offset] = readPlyScalar(view, offset, property.countType, true);
            const values = [];
            for (let i = 0; i < count; i += 1) {
              let value;
              [value, offset] = readPlyScalar(view, offset, property.itemType, true);
              values.push(value);
            }
            if (property.name === 'vertex_indices') {
              faceIndices = values;
            } else if (property.name === 'texcoord') {
              faceTexcoords = values;
            }
          } else {
            offset += plyScalarSize(property.type);
          }
        }
        if (faceIndices && faceIndices.length >= 3) {
          sourceFaces.push({ indices: faceIndices, texcoords: faceTexcoords });
        }
      } else {
        for (const property of element.properties) {
          if (property.kind === 'list') {
            let count;
            [count, offset] = readPlyScalar(view, offset, property.countType, true);
            offset += count * plyScalarSize(property.itemType);
          } else {
            offset += plyScalarSize(property.type);
          }
        }
      }
    }
  }

  if (positions.length === 0) {
    throw new Error('PLY requires vertices');
  }
  if (sourceFaces.length === 0) {
    return { positions, colors, indices: [], normals: [], pointCloud: true };
  }

  const hasTexcoords = sourceFaces.some((face) => Array.isArray(face.texcoords) && face.texcoords.length >= face.indices.length * 2);
  if (hasTexcoords) {
    const expandedPositions = [];
    const expandedUvs = [];
    const expandedIndices = [];
    for (const face of sourceFaces) {
      const polygon = face.indices.map((sourceIndex, cornerIndex) => {
        const positionIndex = sourceIndex * 3;
        const nextIndex = expandedPositions.length / 3;
        expandedPositions.push(positions[positionIndex], positions[positionIndex + 1], positions[positionIndex + 2]);
        expandedUvs.push(face.texcoords[cornerIndex * 2], 1 - face.texcoords[cornerIndex * 2 + 1]);
        return nextIndex;
      });
      for (let i = 1; i < polygon.length - 1; i += 1) {
        expandedIndices.push(polygon[0], polygon[i], polygon[i + 1]);
      }
    }
    return {
      positions: expandedPositions,
      indices: expandedIndices,
      normals: computeNormals(expandedPositions, expandedIndices),
      uvs: expandedUvs
    };
  }

  const indices = [];
  for (const face of sourceFaces) {
    for (let i = 1; i < face.indices.length - 1; i += 1) {
      indices.push(face.indices[0], face.indices[i], face.indices[i + 1]);
    }
  }
  return { positions, indices, normals: computeNormals(positions, indices) };
}

async function loadPlyMesh(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Failed to load ${url}`);
  }
  const buffer = await response.arrayBuffer();
  return parseBinaryPly(buffer);
}

function createPointCloud(app, meshData, child) {
  const mesh = createMesh(app.graphicsDevice, meshData.positions, {
    colors: meshData.colors
  });
  mesh.primitive[0].type = PRIMITIVE_POINTS;
  mesh.primitive[0].base = 0;
  mesh.primitive[0].count = meshData.positions.length / 3;
  mesh.primitive[0].indexed = false;
  const material = new StandardMaterial();
  material.diffuse = new Color(0.82, 0.88, 0.96);
  material.diffuseVertexColor = true;
  material.update();
  const meshInstance = new MeshInstance(mesh, material, child);
  child.addComponent('render', { meshInstances: [meshInstance] });
}

async function installMeshScene(config, app, root, child) {
  const meshData = await loadPlyMesh(config.assetUrl);
  if (meshData.pointCloud) {
    createPointCloud(app, meshData, child);
    return null;
  }
  const meshOptions = {
    indices: meshData.indices,
    normals: meshData.normals
  };
  if (meshData.uvs) {
    meshOptions.uvs = meshData.uvs;
  }
  const mesh = createMesh(app.graphicsDevice, meshData.positions, meshOptions);
  const color = tupleFromConfig(config.viewer?.meshColor, [0.72, 0.78, 0.84]);
  const material = new StandardMaterial();
  material.diffuse = new Color(color[0], color[1], color[2]);
  if (config.textureAssetUrl && meshData.uvs) {
    const textureAsset = await loadAsset(new Asset('mesh-texture', 'texture', {
      url: config.textureAssetUrl
    }), app);
    material.diffuseMap = textureAsset.resource;
  }
  material.update();
  const meshInstance = new MeshInstance(mesh, material, child);
  child.addComponent('render', { meshInstances: [meshInstance] });
  return meshInstance;
}

async function installPointCloudScene(config, app, child) {
  if (!config.pointCloudAssetUrl) {
    return null;
  }
  const meshData = await loadPlyMesh(config.pointCloudAssetUrl);
  createPointCloud(app, meshData, child);
  return child;
}

async function installVoxelGridScene(config, app, child) {
  if (!config.voxelGridAssetUrl) {
    return null;
  }
  const meshData = await loadPlyMesh(config.voxelGridAssetUrl);
  createPointCloud(app, meshData, child);
  return child;
}

function installRenderModeTools(config, meshEntity, pointEntity, voxelEntity) {
  const meshButton = tools?.querySelector('[data-action="render-mesh"]');
  const pointButton = tools?.querySelector('[data-action="render-points"]');
  const voxelButton = tools?.querySelector('[data-action="render-voxels"]');
  if (!meshButton || !pointButton || !voxelButton || (!pointEntity && !voxelEntity)) {
    return;
  }
  meshButton.hidden = false;
  pointButton.hidden = !pointEntity;
  voxelButton.hidden = !voxelEntity;

  function setMode(mode) {
    const showPoints = mode === 'points';
    const showVoxels = mode === 'voxels';
    meshEntity.enabled = !showPoints && !showVoxels;
    if (pointEntity) {
      pointEntity.enabled = showPoints;
    }
    if (voxelEntity) {
      voxelEntity.enabled = showVoxels;
    }
    meshButton.setAttribute('aria-pressed', String(meshEntity.enabled));
    pointButton.setAttribute('aria-pressed', String(Boolean(pointEntity && showPoints)));
    voxelButton.setAttribute('aria-pressed', String(Boolean(voxelEntity && showVoxels)));
    localStorage.setItem(pointCloudStorageKey(config), showVoxels && voxelEntity ? 'voxels' : showPoints && pointEntity ? 'points' : 'mesh');
    setStatus(showVoxels && voxelEntity ? 'Ready · Voxels' : showPoints && pointEntity ? 'Ready · Points' : 'Ready · Mesh');
  }

  meshButton.addEventListener('click', () => setMode('mesh'));
  pointButton.addEventListener('click', () => setMode('points'));
  voxelButton.addEventListener('click', () => setMode('voxels'));
  const saved = localStorage.getItem(pointCloudStorageKey(config));
  setMode(saved === 'voxels' && voxelEntity ? 'voxels' : saved === 'points' && pointEntity ? 'points' : 'mesh');
}

async function boot() {
  const bootStart = performance.now();
  const [manifest, pipelineManifest] = await Promise.all([
    loadSceneManifest(),
    loadPipelineManifest()
  ]);
  const activeSceneId = manifest ? selectedSceneId(manifest) : null;
  const activeScene = manifest?.scenes.find((scene) => scene.id === activeSceneId);
  installSceneSelector(manifest, activeSceneId);

  const config = await loadSceneConfig(activeScene?.sceneUrl || 'scene.json');
  if (!config) {
    showEmpty();
    return;
  }

  title.textContent = config.title || 'Gaussian Splat Viewer';
  setStatus('Loading scene');
  setMetadata(config);
  setPipelineStatus(pipelineManifest, activeScene, config);

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

  const transform = loadSavedTransform(config) || baseTransform(config);
  const sceneRoot = new Entity('Scene Transform');
  const sceneEntity = new Entity(isMeshScene(config) ? 'PLY Mesh' : 'Gaussian Splat');
  const pointEntity = new Entity('Dense Point Cloud');
  const voxelEntity = new Entity('Occupancy Voxel Grid');
  app.root.addChild(sceneRoot);
  sceneRoot.addChild(sceneEntity);
  sceneRoot.addChild(pointEntity);
  sceneRoot.addChild(voxelEntity);
  sceneEntity.setPosition(0, 0, 0);
  pointEntity.setPosition(0, 0, 0);
  voxelEntity.setPosition(0, 0, 0);
  applySplatTransform(sceneRoot, sceneEntity, transform);
  applySplatTransform(sceneRoot, pointEntity, transform);
  applySplatTransform(sceneRoot, voxelEntity, transform);
  installTransformTools(config, sceneRoot, [sceneEntity, pointEntity, voxelEntity], transform);

  if (isMeshScene(config)) {
    await installMeshScene(config, app, sceneRoot, sceneEntity);
    await installPointCloudScene(config, app, pointEntity);
    await installVoxelGridScene(config, app, voxelEntity);
    pointEntity.enabled = false;
    voxelEntity.enabled = false;
    installRenderModeTools(config, sceneEntity, config.pointCloudAssetUrl ? pointEntity : null, config.voxelGridAssetUrl ? voxelEntity : null);
  } else {
    const previewAssetUrl = config.previewAssetUrl || config.assetUrl;
    const previewAsset = await loadAsset(new Asset('capture-preview', 'gsplat', {
      url: previewAssetUrl
    }), app);
    sceneEntity.addComponent('gsplat', { asset: previewAsset });
  }
  setStatus('Ready');
  window.__splatterMetrics = {
    sceneId: activeSceneId,
    pipelineInput: pipelineInputForScene(pipelineManifest, activeScene, config)?.inputSlug || null,
    previewReadyMs: Math.round(performance.now() - bootStart),
    highQualityReadyMs: null
  };

  const previewAssetUrl = config.previewAssetUrl || config.assetUrl;
  if (!isMeshScene(config) && config.assetUrl && config.assetUrl !== previewAssetUrl) {
    loadAsset(new Asset('capture-high-quality', 'gsplat', {
      url: config.assetUrl
    }), app).then((highQualityAsset) => {
      sceneEntity.removeComponent('gsplat');
      sceneEntity.addComponent('gsplat', { asset: highQualityAsset });
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
