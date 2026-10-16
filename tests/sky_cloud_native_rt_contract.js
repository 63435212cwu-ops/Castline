'use strict';
const assert = require('assert'), fs = require('fs'), vm = require('vm'), path = require('path');
const THREE = require('../js/vendor/three.min.js');
function fixture({ supported = true, complete = true } = {}) {
  const context = { THREE, matchMedia: () => ({ matches: false }) }; context.window = context; vm.createContext(context);
  for (const n of ['sky-tokens', 'sky-cloud-noise', 'sky-nebula-glsl', 'sky-nebula'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/sky', n + '.js'), 'utf8'), context);
  const scene = new THREE.Scene(), group = new THREE.Group(), camera = new THREE.PerspectiveCamera(42, 16 / 9, 1, 6000);
  scene.add(group); camera.position.set(0, 0, 1500); camera.lookAt(0, 0, 0); camera.updateMatrixWorld();
  const node = new THREE.Object3D(); group.add(node);
  let target = null, alpha = .7, scissorTest = true, checks = 0, size = [3840, 2160], renders = 0;
  const color = new THREE.Color(.1, .2, .3), viewport = new THREE.Vector4(2, 3, 7, 11), scissor = new THREE.Vector4(1, 2, 6, 9);
  const renderer = { capabilities: { isWebGL2: true }, autoClear: true,
    getContext: () => ({ FRAMEBUFFER: 1, FRAMEBUFFER_COMPLETE: 2, getExtension: () => supported ? {} : null,
      checkFramebufferStatus: () => { checks++; return complete ? 2 : 0; } }),
    getDrawingBufferSize: v => v.set(size[0], size[1]), getRenderTarget: () => target, setRenderTarget: t => { target = t; },
    getClearColor: v => v.copy(color), setClearColor: (v, a) => { color.set(v); alpha = a; }, getClearAlpha: () => alpha,
    getViewport: v => v.copy(viewport), setViewport: v => viewport.copy(v), getScissor: v => v.copy(scissor), setScissor: v => scissor.copy(v),
    getScissorTest: () => scissorTest, setScissorTest: v => { scissorTest = v; }, clear() {}, render() { renders++; } };
  const owner = context.CLSkyNebula.create({ scene: { scene, group, camera, renderer, nodeOf: () => ({ g: node }) } });
  owner.build({ R: 400, stars: [{ key: '真实角色', group: 0, w01: .8 }], groups: [{ color: 0x79bdaf }] }); owner.setState('show', true);
  const before = { color: color.toArray(), alpha, viewport: viewport.toArray(), scissor: scissor.toArray(), scissorTest, auto: renderer.autoClear };
  function frame() { owner.update(1 / 60, renders / 60, false); return owner.stats(); }
  return { context, owner, scene, renderer, frame, before, checks: () => checks, size: v => { size = v; },
    state: () => ({ color: color.toArray(), alpha, viewport: viewport.toArray(), scissor: scissor.toArray(), scissorTest, auto: renderer.autoClear, target }) };
}
const f = fixture(), first = f.frame();
assert.strictEqual(first.viewActive, true); assert.deepStrictEqual(Array.from(first.viewRT), [2880, 1620]);
assert.strictEqual(first.steps, 24); assert.strictEqual(first.viewType, THREE.HalfFloatType); assert.strictEqual(first.viewEncoding, THREE.LinearEncoding);
assert.strictEqual(f.checks(), 1, 'validate the allocated 16-bit framebuffer');
f.frame(); assert.strictEqual(f.checks(), 1, 'unchanged render targets do not sync-check every frame');
const state = f.state(); assert.strictEqual(state.target, null); delete state.target; assert.deepStrictEqual(state, f.before);
f.owner.setNativeCloudScale(1); let direct = f.frame(); assert.strictEqual(direct.viewActive, false); assert.strictEqual(direct.viewRT, null);
f.owner.setNativeCloudScale(.75); f.frame(); f.size([1920, 1080]); assert.strictEqual(f.frame().viewActive, false);
f.size([3000, 3000]); const capped = f.frame();
assert.ok(capped.viewRT[0] * capped.viewRT[1] <= 4.7e6, 'allocated dimensions must respect the cloud pixel cap after rounding');
f.size([3840, 2160]); f.owner.setTier('low'); assert.strictEqual(f.frame().viewActive, false);
f.owner.setTier('high'); f.context.CLSkyTokens.reduced = () => true; assert.strictEqual(f.frame().viewActive, false);
f.context.CLSkyTokens.reduced = () => false; f.frame(); f.owner.setState('hidden', true); assert.strictEqual(f.frame().viewActive, false);
f.owner.dispose(); const disposed = f.owner.stats(); assert.strictEqual(disposed.viewRT, null); assert.strictEqual(disposed.viewRTCreates, disposed.viewRTDisposes);
assert.strictEqual(f.scene.getObjectByName('sky-nebula-composite'), undefined);
for (const input of [{ supported: false }, { complete: false }]) {
  const b = fixture(input), s = b.frame(); assert.strictEqual(s.viewActive, false); assert.strictEqual(s.viewRT, null);
  assert.strictEqual(b.scene.getObjectByName('sky-nebula-volume').visible, true, 'unsupported RT retains the real cloud rather than hiding it');
  b.owner.dispose();
}
console.log('PASS native half-float RT, linear alpha composition, state restoration, 1.0/size/low/reduced/hidden fallback and owned resource disposal');
