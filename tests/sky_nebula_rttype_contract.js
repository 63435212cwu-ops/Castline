'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');
let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }
function close(actual, expected, eps, label) {
  assert.ok(Math.abs(actual - expected) <= eps, label + ': ' + actual + ' vs ' + expected);
  checks++;
}

const context = { THREE, matchMedia: () => ({ matches: false }) };
context.window = context;
vm.createContext(context);
for (const filename of ['sky-tokens.js', 'sky-cloud-noise.js', 'sky-nebula-glsl.js', 'sky-nebula.js']) {
  const sourcePath = path.join(__dirname, '../js/sky', filename);
  vm.runInContext(fs.readFileSync(sourcePath, 'utf8'), context, { filename: sourcePath });
}

const HALF_TRIO = ['OES_texture_half_float', 'OES_texture_half_float_linear', 'EXT_color_buffer_half_float'];

const groups = [{ color: 0xeecb78 }, { color: 0x8899dd }];
const stars = [
  { key: '甲', group: 0, w01: 0.9 }, { key: '乙', group: 0, w01: 0.8 },
  { key: '丙', group: 0, w01: 0.7 }, { key: '丁', group: 0, w01: 0.6 },
  { key: '戌', group: 1, w01: 0.5 }
];

function fixture(renderer) {
  const scene = new THREE.Scene(), group = new THREE.Group(), nodes = new Map(), calls = [];
  scene.add(group);
  stars.forEach(function (character, i) {
    const g = new THREE.Object3D();
    if (i < 4) { g.position.set(5, -2, 1 + i * 0.01); } else { g.position.set(-80, 60, 40); }
    group.add(g); nodes.set('c:' + character.key, { g });
  });
  const camera = new THREE.PerspectiveCamera(45, 16 / 9, 1, 1000);
  camera.position.set(10, 30, 220); camera.lookAt(group.position); camera.updateMatrixWorld(true);
  let target = null;
  const clearColor = new THREE.Color(0x030508);
  const full = Object.assign({
    capabilities: { isWebGL2: true }, autoClear: false,
    getRenderTarget: () => target,
    setRenderTarget(value) { target = value; },
    getClearAlpha: () => 1,
    getClearColor: value => value.copy(clearColor),
    setClearColor() {},
    getDrawingBufferSize: value => value.set(1920, 1080),
    clear() {},
    render(splatScene) {
      const points = [];
      splatScene.traverse(object => { if (object.isPoints) points.push(object); });
      const volume = scene.getObjectByName('sky-nebula-volume');
      calls.push({ points: points[0], volume, target });
    }
  }, renderer);
  const host = { scene, group, camera, renderer: full, nodeOf: key => nodes.get(key) || null };
  const nebula = context.CLSkyNebula.create({ scene: host });
  let time = 0;
  function frame(live = false) {
    scene.updateMatrixWorld(true);
    const before = calls.length;
    nebula.update(1 / 60, time += 1 / 60, live);
    need(calls.length === before + 1, 'public update submits one splat');
    return calls[calls.length - 1];
  }
  nebula.build({ R: 100, pitch: 0.23, rad: 0.2, groups, stars });
  nebula.setState('show', true);
  return { nebula, frame, calls, nodes };
}

{
  const f = fixture({ capabilities: { isWebGL2: true } });
  const call = f.frame();
  need(call.target.texture.type === THREE.HalfFloatType, 'WebGL2 keeps the half-float density target');
  need(f.nebula.stats().rtFloat === true, 'WebGL2 reports float density');
  need(f.nebula.stats().splatScale === 1, 'WebGL2 never pre-compresses density');
  need(call.points.material.uniforms.uScale.value === 1 && call.volume.material.uniforms.uInv.value === 1,
    'WebGL2 splat/volume scale uniforms stay at identity');
  f.nebula.dispose();
  need(f.calls.every(c => c.points.parent === null), 'WebGL2 owner detaches splat points');
}

{
  const asked = [];
  const ext = { get(name) { asked.push(name); return HALF_TRIO.indexOf(name) >= 0 ? {} : null; } };
  const f = fixture({ capabilities: { isWebGL2: false }, extensions: ext });
  const call = f.frame();
  HALF_TRIO.forEach(name => need(asked.indexOf(name) >= 0, 'WebGL1 probe asks ' + name));
  need(call.target.texture.type === THREE.HalfFloatType, 'WebGL1 + trio upgrades to half-float');
  need(f.nebula.stats().rtFloat === true && f.nebula.stats().splatScale === 1,
    'WebGL1 + trio keeps uncompressed density');
}

{
  const f = fixture({ capabilities: { isWebGL2: false } });
  const call = f.frame();
  need(call.target.texture.type === THREE.UnsignedByteType, 'WebGL1 without trio drops to 8-bit');
  need(f.nebula.stats().rtFloat === false, 'stats report the 8-bit density path');
  need(f.nebula.stats().overlap === 4, 'grid overlap bound counts the four stacked members');
  const peak = context.CLSkyNebulaGLSL.SPLAT_PEAK || 0.62;
  const want = 0.98 / (peak * 4);
  close(f.nebula.stats().splatScale, want, 5e-5, '8-bit scale packs the worst sum into 0.98');
  close(call.points.material.uniforms.uScale.value, want, 1e-6, 'splat shader receives the same scale');
  close(call.volume.material.uniforms.uInv.value, 1 / want, 1e-4, 'volume shader restores with the reciprocal');
  need(call.points.material.uniforms.uScale.value * call.volume.material.uniforms.uInv.value >= 0.9999,
    'splat scale and volume reciprocal always cancel');
  f.nebula.hover(0);
  const hovered = f.frame();
  close(hovered.points.material.uniforms.uScale.value, 0.98 / (peak * 4 * 1.9), 5e-5, 'hover gain re-packs the scale');
  f.nebula.hover(-1);
  const settled = f.frame();
  close(settled.points.material.uniforms.uScale.value, want, 5e-5, 'leaving hover restores the scale');
  let t = 0;
  for (let i = 0; i < 3; i++) { f.nodes.get('c:甲').g.position.x += 40; f.frame(true); }
  while (t < 40) { t++; f.nodes.get('c:乙').g.position.x += 0.5; f.frame(true); }
  need(f.nebula.stats().overlap <= 3, 'flying frames re-measure the overlap bound');
}

{
  const asked = [];
  const ext = { get(name) { asked.push(name); return name === 'EXT_color_buffer_half_float' || name === 'OES_texture_half_float' ? {} : null; } };
  const f = fixture({ capabilities: { isWebGL2: false }, extensions: ext });
  const call = f.frame();
  need(call.target.texture.type === THREE.UnsignedByteType, 'incomplete trio must not create a half-float target');
  need(asked.indexOf('OES_texture_half_float_linear') >= 0, 'probe also checks linear filtering');
  need(f.nebula.stats().splatScale < 1, '8-bit fallback still pre-compresses the stacked pile');
}

{
  let haveTrio = false;
  const ext = { get(name) { return haveTrio && HALF_TRIO.indexOf(name) >= 0 ? {} : null; } };
  const f = fixture({ capabilities: { isWebGL2: false }, extensions: ext });
  need(f.frame().target.texture.type === THREE.UnsignedByteType, 'starts on the 8-bit rung');
  haveTrio = true;
  f.nebula.setTier('mid');
  const call = f.frame();
  need(call.target.texture.type === THREE.HalfFloatType, 'tier rebuild re-probes and upgrades to half-float');
  need(f.nebula.stats().rtFloat === true && f.nebula.stats().splatScale === 1, 'upgraded rung restores identity scale');
  need(f.nebula.stats().rt === 256, 'mid tier keeps its own RT budget');
}

console.log(JSON.stringify({ ok: true, checks, cases: 5, cpuOnly: true }, null, 2));
