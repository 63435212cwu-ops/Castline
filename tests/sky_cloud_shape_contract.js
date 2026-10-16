'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');
let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }
function same(actual, expected, label) { assert.deepEqual(actual, expected, label); checks++; }

const context = { THREE, matchMedia: () => ({ matches: false }) };
context.window = context;
vm.createContext(context);
for (const filename of ['sky-tokens.js', 'sky-cloud-noise.js', 'sky-nebula-glsl.js', 'sky-nebula.js']) {
  const sourcePath = path.join(__dirname, '../js/sky', filename);
  vm.runInContext(fs.readFileSync(sourcePath, 'utf8'), context, { filename: sourcePath });
}

const resources = new Map(), textures = [];
function watch(resource, kind) {
  if (!resources.has(resource)) {
    const axis = resource.isBufferGeometry ? resource.getAttribute('aCloudAxis') : null;
    const record = { resource, kind, axis, disposals: 0, axisPresentAtDisposal: false };
    resources.set(resource, record);
    resource.addEventListener('dispose', () => {
      record.disposals++;
      if (axis) record.axisPresentAtDisposal = resource.getAttribute('aCloudAxis') === axis;
    });
  }
  return resources.get(resource);
}

const createNoise = context.CLSkyCloudNoise.create;
context.CLSkyCloudNoise.create = function (three) {
  need(three === THREE, 'nebula passes the shipped Three to the real noise factory');
  const texture = createNoise.apply(this, arguments);
  textures.push(texture); watch(texture, 'noise');
  return texture;
};

const characters = [
  { key: '孙悟空', group: 0, w01: 0.9 },
  { key: '猪八戒', group: 0, w01: 0.7 },
  { key: '唐三藏', group: 1, w01: 0.8 },
  { key: '沙悟净', group: 1, w01: 0.5 },
  { key: '白龙马', group: 2, w01: 0.4 },
  { key: '角色🪐', group: 2, w01: 0.3 }
];
const groups = [{ color: 0xeecb78 }, { color: 0x8899dd }, { color: 0x79bdaf }];

function fixture() {
  const scene = new THREE.Scene(), group = new THREE.Group(), nodes = new Map(), calls = [];
  scene.add(group); group.position.set(7, -3, 11); group.rotation.set(0.13, -0.19, 0.07);
  for (let i = 0; i < characters.length; i++) {
    const g = new THREE.Object3D();
    g.position.set(-43 + 17 * i, 23 - 7 * i + i * i, -11 + 5 * i);
    group.add(g); nodes.set('c:' + characters[i].key, { g });
  }
  const camera = new THREE.PerspectiveCamera(45, 16 / 9, 1, 1000);
  camera.position.set(10, 30, 220); camera.lookAt(group.position); camera.updateMatrixWorld(true);
  let target = null, clearAlpha = 1, time = 0;
  const clearColor = new THREE.Color(0x030508);
  const renderer = {
    capabilities: { isWebGL2: true }, autoClear: false,
    getRenderTarget: () => target,
    setRenderTarget(value) { target = value; },
    getClearAlpha: () => clearAlpha,
    getClearColor: value => value.copy(clearColor),
    setClearColor(value, alpha) { clearColor.set(value); clearAlpha = alpha; },
    getDrawingBufferSize: value => value.set(1920, 1080),
    clear() {},
    render(splatScene, splatCamera) {
      const points = [];
      splatScene.traverse(object => { if (object.isPoints) points.push(object); });
      need(points.length === 1 && points[0] instanceof THREE.Points, 'normal splat render contains real Three Points');
      need(splatCamera instanceof THREE.OrthographicCamera, 'normal splat uses a real orthographic camera');
      const volume = scene.getObjectByName('sky-nebula-volume');
      need(volume && volume instanceof THREE.Mesh, 'normal build attaches the real volume mesh');
      const point = points[0];
      watch(point.geometry, 'splat geometry'); watch(volume.geometry, 'volume geometry');
      watch(point.material, 'splat material'); watch(volume.material, 'volume material');
      watch(target, 'render target');
      calls.push({ points: point, volume, target, splatScene });
    }
  };
  const host = { scene, group, camera, renderer, nodeOf: key => nodes.get(key) || null };
  const nebula = context.CLSkyNebula.create({ scene: host });
  const owned = new Set();
  function frame(label, live = false) {
    scene.updateMatrixWorld(true);
    const before = calls.length;
    nebula.update(1 / 60, time += 1 / 60, live);
    need(calls.length === before + 1, label + ': public update submits a splat');
    const call = calls[calls.length - 1];
    for (const resource of [call.points.geometry, call.volume.geometry, call.points.material,
      call.volume.material, call.target, call.points.material.uniforms.tNoise.value]) owned.add(resource);
    return call;
  }
  function build(stars, label, extra = {}) {
    scene.updateMatrixWorld(true);
    nebula.build({ R: 100, pitch: 0.23, groups, stars, ...extra });
    nebula.setState('show', true);
    return frame(label);
  }
  return { host, nodes, calls, owned, nebula, frame, build };
}

function axesByRole(f, call, label) {
  f.host.scene.updateMatrixWorld(true);
  const geometry = call.points.geometry, position = geometry.getAttribute('position');
  const axis = geometry.getAttribute('aCloudAxis'), result = new Map(), used = new Set();
  need(axis instanceof THREE.BufferAttribute && axis.itemSize === 2, label + ': real two-component axis attribute');
  need(axis.count === characters.length && position.count === characters.length, label + ': one axis per character');
  for (const character of characters) {
    const local = f.nodes.get('c:' + character.key).g.getWorldPosition(new THREE.Vector3());
    call.volume.parent.worldToLocal(local);
    const matches = [];
    for (let row = 0; row < position.count; row++) {
      if (Math.hypot(position.getX(row) - local.x, position.getY(row) - local.y) < 1e-5) matches.push(row);
    }
    need(matches.length === 1 && !used.has(matches[0]), label + ': unique rendered position for ' + character.key);
    const row = matches[0], value = [axis.getX(row), axis.getY(row)];
    used.add(row);
    need(value.every(Number.isFinite) && Math.abs(Math.hypot(...value) - 1) < 1e-6,
      label + ': finite unit direction for ' + character.key);
    result.set(character.key, value);
  }
  return result;
}
function sameAxes(actual, expected, label) {
  for (const character of characters) same(actual.get(character.key), expected.get(character.key), label + ': ' + character.key);
}
function sharedNoise(call, wanted, label) {
  need(wanted instanceof THREE.DataTexture, label + ': real generated DataTexture');
  need(call.points.material.uniforms.tNoise.value === wanted && call.volume.material.uniforms.tNoise.value === wanted,
    label + ': splat and volume share their owner texture');
  need(resources.get(wanted).disposals === 0, label + ': shared texture remains alive');
}

const first = fixture(), initial = first.build(characters, 'initial build');
same(textures.length, 1, 'first owner creates exactly one noise texture');
const firstNoise = textures[0], baseline = axesByRole(first, initial, 'initial build');
sharedNoise(initial, firstNoise, 'initial build');
const directions = [...baseline.values()];
for (let i = 0; i < directions.length; i++) {
  for (let j = i + 1; j < directions.length; j++) {
    need(Math.hypot(directions[i][0] - directions[j][0], directions[i][1] - directions[j][1]) > 1e-5,
      'different fixture names have distinct directions: ' + i + '/' + j);
  }
}

const originalAxis = initial.points.geometry.getAttribute('aCloudAxis'), originalVersion = originalAxis.version;
const originalPositions = Array.from(initial.points.geometry.getAttribute('position').array);
for (let frame = 0; frame < 3; frame++) {
  for (const node of first.nodes.values()) node.g.position.add(new THREE.Vector3(2 + frame, -3, 1));
  const moved = first.frame('moving frame ' + frame, true);
  need(moved.points.geometry.getAttribute('aCloudAxis') === originalAxis && originalAxis.version === originalVersion,
    'moving frame retains the axis attribute without scheduling another upload');
  sameAxes(axesByRole(first, moved, 'moving frame'), baseline, 'moving does not change role direction');
  sharedNoise(moved, firstNoise, 'moving frame');
}
need(JSON.stringify(Array.from(initial.points.geometry.getAttribute('position').array)) !== JSON.stringify(originalPositions),
  'moving frames actually update splat positions');

const reordered = [characters[3], characters[0], characters[5], characters[2], characters[1], characters[4]];
const secondBuild = first.build(reordered, 'reordered build');
same(resources.get(initial.points.geometry).disposals, 1, 'rebuild disposes the preceding splat geometry once');
sameAxes(axesByRole(first, secondBuild, 'reordered build'), baseline, 'array reordering preserves role direction');
sharedNoise(secondBuild, firstNoise, 'reordered build');
const regrouped = reordered.map(character => ({ ...character, group: (character.group + 1) % groups.length, w01: 0.2 }));
const thirdBuild = first.build(regrouped, 'regrouped build', { R: 135, pitch: -0.17 });
same(resources.get(secondBuild.points.geometry).disposals, 1, 'regroup disposes the preceding splat geometry once');
sameAxes(axesByRole(first, thirdBuild, 'regrouped build'), baseline, 'group, weight and anchor changes preserve direction');
sharedNoise(thirdBuild, firstNoise, 'regrouped build');
same(textures.length, 1, 'rebuilding never allocates another noise texture');

for (const tier of ['mid', 'low', 'mid', 'high', 'low', 'high']) {
  first.nebula.setTier(tier);
  const call = first.frame('tier ' + tier);
  same(first.nebula.stats().rt, context.CLSkyTokens.TIER[tier].nebulaRT, 'tier switch reaches the real render-target budget');
  same(first.nebula.stats().slices, context.CLSkyTokens.VOL.slices[tier], 'tier switch reaches the real volume slice budget');
  sharedNoise(call, firstNoise, 'tier ' + tier);
  sameAxes(axesByRole(first, call, 'tier ' + tier), baseline, 'tier change preserves role direction');
  same(textures.length, 1, 'tier change does not regenerate noise');
}

const second = fixture(), other = second.build(characters, 'independent owner');
same(textures.length, 2, 'independent owner creates exactly one additional texture');
const secondNoise = textures[1];
need(secondNoise !== firstNoise && secondNoise.image.data.buffer !== firstNoise.image.data.buffer,
  'independent owners share neither texture nor pixel backing storage');
sharedNoise(other, secondNoise, 'independent owner');
sameAxes(axesByRole(second, other, 'independent owner'), baseline, 'independent owner preserves role identity');

const fadeStart = first.nebula.stats().alpha;
first.nebula.setState('hidden');
let previousAlpha = fadeStart, fadeClock = 10;
const fadeFrames = Math.ceil(context.CLSkyTokens.DUR.focus * 60);
for (let i = 0; i < fadeFrames; i++) {
  if (i === 18) first.nebula.setState('hidden');
  first.nebula.update(1 / 60, fadeClock += 1 / 60, false);
  const alpha = first.nebula.stats().alpha;
  need(Number.isFinite(alpha) && alpha >= 0 && alpha <= previousAlpha + 1e-9,
    'outgoing fade is finite and monotonic at frame ' + i);
  previousAlpha = alpha;
}
same(first.nebula.stats().alpha, 0, 'outgoing volume reaches zero within focus duration');
need(!initial.volume.visible, 'finished outgoing volume is excluded from rendering');
first.nebula.setState('show');
same(first.nebula.stats().alpha, 0, 'interrupted/new fade resumes from its current value');
first.nebula.update(1 / 60, fadeClock += 1 / 60, false);
need(first.nebula.stats().alpha > 0 && initial.volume.visible, 'returning to the constellation restores its existing volume');
first.nebula.setState('hidden');
const previousMedia = context.matchMedia;
try {
  context.matchMedia = () => ({ matches: true });
  first.nebula.update(1 / 60, fadeClock += 1 / 60, false);
  same(first.nebula.stats().alpha, 0, 'reduced motion finishes an active outgoing fade immediately');
  context.matchMedia = previousMedia;
  first.nebula.update(1 / 60, fadeClock += 1 / 60, false);
  same(first.nebula.stats().alpha, 0, 'leaving reduced motion does not resurrect a hidden volume');
} finally { context.matchMedia = previousMedia; }
first.nebula.setState('show', true);
same(first.nebula.stats().alpha, fadeStart, 'instant reveal restores the original density-weighted alpha');

function disposedOnce(f, label) {
  f.nebula.dispose(); f.nebula.dispose();
  for (const resource of f.owned) {
    const record = resources.get(resource);
    same(record.disposals, 1, label + ': ' + record.kind + ' disposes exactly once, including repeated dispose()');
    if (record.axis) need(record.axisPresentAtDisposal, label + ': owning geometry releases the axis attribute with its dispose event');
  }
  need(!f.host.scene.getObjectByName('sky-nebula-volume'), label + ': volume is detached');
  need(f.calls.every(call => call.points.parent === null), label + ': all splat points are detached');
}
disposedOnce(first, 'first owner');
same(resources.get(secondNoise).disposals, 0, 'first owner disposal leaves independent noise alive');
second.nebula.hover(0);
sharedNoise(second.frame('independent owner after first disposal'), secondNoise, 'surviving owner');
disposedOnce(second, 'second owner');
need([...resources.values()].every(record => record.disposals === 1), 'every observed resource has exactly one disposal event');

console.log(JSON.stringify({ ok: true, checks, three: THREE.REVISION, noiseAllocations: textures.length,
  resources: resources.size, splatGeometries: [...resources.values()].filter(record => record.axis).length,
  cpuOnly: true }, null, 2));
