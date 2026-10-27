import * as THREE from './three.module.js';
import { OrbitControls } from './OrbitControls.js';

const mount = document.querySelector('#scene');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#e9eeec');
const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 10000);
camera.up.set(0, 0, 1);
camera.position.set(100, -130, 105);
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(mount.clientWidth, mount.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
mount.appendChild(renderer.domElement);

scene.add(new THREE.HemisphereLight(0xffffff, 0x87938f, 2.0));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
keyLight.position.set(-80, -120, 180);
keyLight.castShadow = true;
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0xffffff, 0.8);
fillLight.position.set(100, 70, 100);
scene.add(fillLight);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.075;
controls.screenSpacePanning = false;
controls.minDistance = 1;
controls.maxDistance = 5000;

let modelGroup = new THREE.Group();
scene.add(modelGroup);
let diaphragmMeshes = [];
let loadArrows = [];
let loadAnnotations = [];
let floorGroups = [];
let structuralMeshes = [];
let diaphragmsVisible = true;
let displayMode = 'default';
let initialCamera = null;
let modelPayload = null;
let analysisOptions = [];
let selectedGeometryId = null;
let selectedCaseName = null;
let selectedColorMetric = 'Element node SRSS sum';
const deformationScale = 1000;
const colors = { shear_wall: 0x004050, column: 0x8b9064, beam: 0x00a3ad, outrigger: 0xd4451d, diaphragm: 0x88dbdf };
const inchToFoot = value => value / 12;
const makeMaterial = (color, options = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.02, ...options });

function clearModel() {
  scene.remove(modelGroup);
  modelGroup.traverse(object => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) (Array.isArray(object.material) ? object.material : [object.material]).forEach(m => m.dispose());
  });
  modelGroup = new THREE.Group();
  scene.add(modelGroup);
  diaphragmMeshes = [];
  loadArrows = [];
  loadAnnotations = [];
  floorGroups = [];
  structuralMeshes = [];
  globalThis.document.querySelector('#load-labels').replaceChildren();
}

function addMember(parentGroup, element, floorType, floorIndex, typeName, bottomZ, topZ) {
  const nodeMap = new Map(floorType.structural_nodes.map(node => [node.id, node]));
  const refs = element.nodes.map(id => nodeMap.get(id));
  if (refs.some(point => !point)) return;
  const type = element.type.toLowerCase();
  const width = inchToFoot(element.section_dims.width);
  const depth = inchToFoot(element.section_dims.depth);
  const height = topZ - bottomZ;
  let geometry, center, angle = 0;
  if (type === 'column') {
    geometry = new THREE.BoxGeometry(width, depth, height);
    center = [refs[0].x, refs[0].y, bottomZ + height / 2];
  } else if (type === 'shear_wall') {
    const [a, b] = refs;
    const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy);
    angle = Math.atan2(dy, dx);
    // Wall width is plan thickness; connected node spacing defines the in-plane length.
    geometry = new THREE.BoxGeometry(length, width, height);
    center = [(a.x + b.x) / 2, (a.y + b.y) / 2, bottomZ + height / 2];
  } else {
    const [a, b] = refs;
    const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy);
    angle = Math.atan2(dy, dx);
    // Beam/outtrigger depth is vertical; width is horizontal and perpendicular to the span.
    geometry = new THREE.BoxGeometry(length, width, depth);
    center = [(a.x + b.x) / 2, (a.y + b.y) / 2, topZ - depth / 2];
  }
  const mesh = new THREE.Mesh(geometry, makeMaterial(colors[type] ?? 0x737d7a));
  mesh.position.set(...center);
  mesh.rotation.z = angle;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  // Preserve source node IDs on rendered members for a future analysis-result adapter.
  mesh.userData = {
    elementId: element.id,
    elementType: type,
    floorIndex,
    floorType: typeName,
    nodeRefs: [...element.nodes],
    nodeCoords: refs.map(point => ({ x: point.x, y: point.y })),
    baseColor: mesh.material.color.clone()
  };
  parentGroup.add(mesh);
  structuralMeshes.push(mesh);
}

function addDiaphragm(parentGroup, floorType, z, thickness) {
  const byId = new Map(floorType.floor_plate.boundary_nodes.map(node => [node.id, node]));
  const loop = floorType.floor_plate.boundary_loop.map(id => byId.get(id)).filter(Boolean);
  if (loop.length < 3) return;
  const shape = new THREE.Shape();
  shape.moveTo(loop[0].x, loop[0].y);
  for (const point of loop.slice(1)) shape.lineTo(point.x, point.y);
  shape.closePath();
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: thickness, bevelEnabled: false, curveSegments: 1 });
  const mesh = new THREE.Mesh(geometry, makeMaterial(colors.diaphragm, { transparent: true, opacity: 0.46, side: THREE.DoubleSide, depthWrite: false }));
  mesh.position.z = z - thickness;
  mesh.receiveShadow = true;
  mesh.userData = { role: 'diaphragm' };
  parentGroup.add(mesh);
  diaphragmMeshes.push(mesh);
}

function addGrid(document) {
  const points = Object.values(document.floor_types).flatMap(floor => floor.floor_plate.boundary_nodes.map(p => [p.x, p.y]));
  if (!points.length) return;
  const extent = Math.max(20, ...points.flatMap(([x, y]) => [Math.abs(x), Math.abs(y)])) * 1.8;
  const grid = new THREE.GridHelper(extent * 2, Math.max(10, Math.round(extent / 5)), 0x87938f, 0xcbd4d1);
  grid.rotation.x = Math.PI / 2;
  grid.position.z = -0.01;
  grid.material.transparent = true;
  grid.material.opacity = 0.52;
  modelGroup.add(grid);
  const axes = new THREE.AxesHelper(Math.max(5, extent * 0.12));
  axes.position.z = 0.02;
  modelGroup.add(axes);
}

function addStoryLoads(loads, forceUnit) {
  const activeLoads = loads.filter(load => Math.abs(load.force_kip) > 0);
  if (!activeLoads.length) return;
  const maxMagnitude = Math.max(...activeLoads.map(load => Math.abs(load.force_kip)));
  const maxLength = 100;
  const minLength = 5;
  const labelLayer = globalThis.document.querySelector('#load-labels');
  for (const load of activeLoads) {
    const directionSign = Math.sign(load.force_kip);
    const ratio = Math.abs(load.force_kip) / maxMagnitude;
    const length = minLength + (maxLength - minLength) * ratio;
    const direction = new THREE.Vector3(directionSign, 0, 0);
    const origin = new THREE.Vector3(load.x, load.y, load.z);
    const arrow = new THREE.ArrowHelper(direction, origin, length, directionSign > 0 ? 0xc45532 : 0x426e9b, 1.8, 1.0);
    arrow.userData = { storyNumber: load.floor_number, forceKip: load.force_kip, globalAxis: 'X' };
    modelGroup.add(arrow);
    loadArrows.push(arrow);

    const label = globalThis.document.createElement('div');
    label.className = `load-label ${directionSign > 0 ? 'positive' : 'negative'}`;
    const signedForce = `${load.force_kip > 0 ? '+' : ''}${Number(load.force_kip).toLocaleString(undefined, { maximumSignificantDigits: 4 })}`;
    label.textContent = `F${load.floor_number}: ${signedForce} ${forceUnit}`;
    labelLayer.appendChild(label);
    loadAnnotations.push({
      element: label,
      position: origin.clone().addScaledVector(direction, length * 0.68).add(new THREE.Vector3(0, 0, 0.25)),
      laneOffset: ((load.floor_number % 5) - 2) * 36
    });
  }
}

function updateLoadAnnotations() {
  const width = mount.clientWidth;
  const height = mount.clientHeight;
  for (const annotation of loadAnnotations) {
    const projected = annotation.position.clone().project(camera);
    const visible = projected.z >= -1 && projected.z <= 1 && Math.abs(projected.x) <= 1.15 && Math.abs(projected.y) <= 1.15 && displayMode === 'loads';
    annotation.element.style.display = visible ? 'block' : 'none';
    if (visible) {
      const screenX = (projected.x * 0.5 + 0.5) * width + annotation.laneOffset;
      annotation.element.style.left = `${Math.max(70, Math.min(width - 70, screenX))}px`;
      annotation.element.style.top = `${(-projected.y * 0.5 + 0.5) * height}px`;
    }
  }
}

function fitView() {
  const box = new THREE.Box3().setFromObject(modelGroup);
  if (box.isEmpty()) return;
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  controls.target.copy(sphere.center);
  const distance = sphere.radius / Math.sin(THREE.MathUtils.degToRad(camera.fov * 0.5)) * 0.83;
  const direction = new THREE.Vector3(1, -1.3, 0.95).normalize();
  camera.position.copy(sphere.center).addScaledVector(direction, distance);
  camera.near = Math.max(0.01, distance / 10000);
  camera.far = Math.max(1000, distance * 100);
  camera.updateProjectionMatrix();
  controls.update();
  initialCamera = { position: camera.position.clone(), target: controls.target.clone() };
}

function getFloorCentroid(floorType) {
  const byId = new Map(floorType.floor_plate.boundary_nodes.map(node => [node.id, node]));
  const loop = floorType.floor_plate.boundary_loop.map(id => byId.get(id)).filter(Boolean);
  if (loop.length < 3) {
    const nodes = floorType.structural_nodes;
    return nodes.length
      ? { x: nodes.reduce((sum, node) => sum + node.x, 0) / nodes.length, y: nodes.reduce((sum, node) => sum + node.y, 0) / nodes.length }
      : { x: 0, y: 0 };
  }
  let twiceArea = 0, cx = 0, cy = 0;
  for (let i = 0; i < loop.length; i++) {
    const a = loop[i], b = loop[(i + 1) % loop.length];
    const cross = a.x * b.y - b.x * a.y;
    twiceArea += cross;
    cx += (a.x + b.x) * cross;
    cy += (a.y + b.y) * cross;
  }
  if (Math.abs(twiceArea) < 1e-9) return { x: 0, y: 0 };
  return { x: cx / (3 * twiceArea), y: cy / (3 * twiceArea) };
}

function getActiveOption() {
  return analysisOptions.find(option => option.id === selectedGeometryId) ?? analysisOptions[0] ?? null;
}

function getActiveDocument() {
  const option = getActiveOption();
  return option?.geometry ?? modelPayload?.document ?? null;
}

function getActiveCaseFloors() {
  const option = getActiveOption();
  if (!option?.cases) return [];
  const matchingCase = Object.keys(option.cases).find(name => name.toLowerCase() === (selectedCaseName ?? '').toLowerCase());
  return matchingCase ? option.cases[matchingCase] ?? [] : [];
}

function nearestFloorResult(topZ, floorIndex, floors) {
  if (!floors.length) return null;
  return floors.reduce((nearest, candidate) => {
    const candidateDistance = Number.isFinite(candidate.elevation_ft)
      ? Math.abs(candidate.elevation_ft - topZ)
      : Math.abs((candidate.floor_number ?? floorIndex + 1) - (floorIndex + 1));
    if (!nearest || candidateDistance < nearest.distance) return { result: candidate, distance: candidateDistance };
    return nearest;
  }, null)?.result ?? null;
}

function nodeDisplacementIn(point, center, response) {
  const radiusXIn = (point.x - center.x) * 12;
  const radiusYIn = (point.y - center.y) * 12;
  return {
    x: (response.ux_in ?? 0) - (response.rz_rad ?? 0) * radiusYIn,
    y: (response.uy_in ?? 0) + (response.rz_rad ?? 0) * radiusXIn
  };
}

function resultScalar(mesh, floorState) {
  if (!floorState) return null;
  if (selectedColorMetric === 'Member DCR') return null;
  if (selectedColorMetric === 'Story drift') return floorState.response.max_drift_resultant ?? null;
  const nodeValues = mesh.userData.nodeCoords.map(point => {
    const displacement = nodeDisplacementIn(point, floorState.center, floorState.response);
    return Math.hypot(displacement.x, displacement.y);
  });
  if (!nodeValues.length) return null;
  if (selectedColorMetric === 'Node displacement (SRSS)') return Math.max(...nodeValues);
  return nodeValues.reduce((sum, value) => sum + value, 0);
}

function displacementGradient(ratio) {
  const low = new THREE.Color(0x88dbdf);
  const middle = new THREE.Color(0x8b9064);
  const high = new THREE.Color(0xd4451d);
  const color = new THREE.Color();
  if (ratio <= 0.5) return color.lerpColors(low, middle, ratio * 2);
  return color.lerpColors(middle, high, (ratio - 0.5) * 2);
}

function updateAnalysisVisualization() {
  const floors = getActiveCaseFloors();
  const floorStates = floorGroups.map(item => ({
    ...item,
    response: nearestFloorResult(item.topZ, item.floorIndex, floors)
  }));

  for (const floorState of floorStates) {
    const { group, center, response } = floorState;
    if (displayMode !== 'deformed' || !response) {
      group.position.set(0, 0, 0);
      group.rotation.z = 0;
      continue;
    }
    const angle = (response.rz_rad ?? 0) * deformationScale;
    const cosine = Math.cos(angle), sine = Math.sin(angle);
    const ux = (response.ux_in ?? 0) / 12 * deformationScale;
    const uy = (response.uy_in ?? 0) / 12 * deformationScale;
    group.position.set(
      center.x + ux - (center.x * cosine - center.y * sine),
      center.y + uy - (center.x * sine + center.y * cosine),
      0
    );
    group.rotation.z = angle;
  }

  for (const mesh of structuralMeshes) mesh.material.color.copy(mesh.userData.baseColor);
  if (displayMode !== 'colors') return;

  const stateByIndex = new Map(floorStates.map(state => [state.floorIndex, state]));
  const colored = structuralMeshes.map(mesh => ({ mesh, scalar: resultScalar(mesh, stateByIndex.get(mesh.userData.floorIndex)) }))
    .filter(item => Number.isFinite(item.scalar));
  if (!colored.length) return;
  const min = Math.min(...colored.map(item => item.scalar));
  const max = Math.max(...colored.map(item => item.scalar));
  for (const item of colored) {
    const ratio = max - min < 1e-12 ? 0.5 : (item.scalar - min) / (max - min);
    item.mesh.material.color.copy(displacementGradient(ratio));
  }
}

function rebuildGeometry(shouldFit = true) {
  const document = getActiveDocument();
  if (!document || !modelPayload) return;
  clearModel();
  let baseZ = 0;
  document.floor_sequence.forEach((entry, floorIndex) => {
    const floorType = document.floor_types[entry.type];
    if (!floorType) return;
    const topZ = baseZ + entry.floor_height;
    const group = new THREE.Group();
    group.userData = { floorIndex, floorType: entry.type };
    modelGroup.add(group);
    for (const element of floorType.structural_elements) addMember(group, element, floorType, floorIndex, entry.type, baseZ, topZ);
    addDiaphragm(group, floorType, topZ, inchToFoot(modelPayload.diaphragmThicknessInches ?? 8));
    floorGroups.push({ group, floorIndex, floorType, typeName: entry.type, bottomZ: baseZ, topZ, center: getFloorCentroid(floorType) });
    baseZ = topZ;
  });
  addGrid(document);
  addStoryLoads(modelPayload.storyLoads ?? [], modelPayload.forceUnit ?? 'kip');
  globalThis.document.querySelector('#empty').style.display = 'none';
  updateAnalysisVisualization();
  const showLoads = displayMode === 'loads';
  loadArrows.forEach(arrow => { arrow.visible = showLoads; });
  loadAnnotations.forEach(annotation => { annotation.element.style.display = showLoads ? 'block' : 'none'; });
  if (shouldFit) fitView();
}

function buildModel(payload) {
  modelPayload = payload;
  analysisOptions = payload.analysisOptions ?? [];
  selectedGeometryId = payload.selectedGeometryId ?? analysisOptions[0]?.id ?? null;
  selectedCaseName = payload.selectedCaseName ?? Object.keys(analysisOptions[0]?.cases ?? {})[0] ?? null;
  selectedColorMetric = payload.colorMetric ?? 'Element node SRSS sum';
  rebuildGeometry(true);
  setDisplayMode(displayMode);
}

document.querySelector('#fit').addEventListener('click', () => {
  if (initialCamera) { camera.position.copy(initialCamera.position); controls.target.copy(initialCamera.target); controls.update(); }
});
document.querySelector('#toggle-plates').addEventListener('click', event => {
  diaphragmsVisible = !diaphragmsVisible;
  diaphragmMeshes.forEach(mesh => { mesh.visible = diaphragmsVisible; });
  event.currentTarget.textContent = diaphragmsVisible ? 'Hide diaphragms' : 'Show diaphragms';
});
function setDisplayMode(mode) {
  if (!['default', 'loads', 'deformed', 'colors'].includes(mode)) return;
  displayMode = mode;
  const showLoads = mode === 'loads';
  loadArrows.forEach(arrow => { arrow.visible = showLoads; });
  loadAnnotations.forEach(annotation => { annotation.element.style.display = showLoads ? 'block' : 'none'; });
  updateAnalysisVisualization();
}

function setAnalysisSelection(geometryId, caseName, colorMetric) {
  const geometryChanged = geometryId && geometryId !== selectedGeometryId;
  if (geometryId) selectedGeometryId = geometryId;
  if (caseName) selectedCaseName = caseName;
  if (colorMetric) selectedColorMetric = colorMetric;
  if (geometryChanged) rebuildGeometry(true);
  else updateAnalysisVisualization();
}

window.floorplateViewer = { setModel: buildModel, setDisplayMode, setAnalysisSelection };
window.chrome.webview.postMessage('viewer-ready');

function resize() {
  const width = Math.max(1, mount.clientWidth), height = Math.max(1, mount.clientHeight);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}
new ResizeObserver(resize).observe(mount);
function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); updateLoadAnnotations(); }
animate();
