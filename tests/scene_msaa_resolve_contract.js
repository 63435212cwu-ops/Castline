'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { block } = require('./scene_motion_clock_contract.js');
const source = fs.readFileSync(require('path').join(__dirname, '../js/core/scene-core.js'), 'utf8');
const method = block(source.replace('    MsaaScenePass.prototype.render = function (', '    function msaaRender('), 'msaaRender');
const context = vm.createContext({ scene: {}, camera: {} });
vm.runInContext(method + ';globalThis.render=msaaRender;', context);
function run(change, fail) {
  const calls = [], src = { __webglMultisampledFramebuffer: 'multisample' }, dst = { __webglFramebuffer: 'read' };
  const texture = () => ({ type: 1009, format: 1023, encoding: 3000 });
  const rt = { width: 3840, height: 2160, texture: texture(), isWebGLMultisampleRenderTarget: true };
  const target = { width: 3840, height: 2160, texture: texture() };
  const gl = { READ_FRAMEBUFFER: 0x8ca8, COLOR_BUFFER_BIT: 0x4000, NEAREST: 0x2600,
    bindFramebuffer(kind, id) { calls.push(['bind', kind, id]); }, blitFramebuffer(...args) { calls.push(['blit', ...args]); } };
  const pass = { rt, directResolve: true, renderToScreen: false, directResolveCount: 0, copyDrawCount: 0,
    mat: { uniforms: { tDiffuse: {} } }, fsq: { render() { calls.push(['copy']); } } };
  const renderer = { autoClear: true, setRenderTarget(t) { calls.push(['target', t === rt ? 'msaa' : t === target ? 'read' : 'screen']); }, clear() {},
    render() { calls.push(['scene', rt.isWebGLMultisampleRenderTarget]); if (fail) throw Error('draw failed'); },
    getContext() { return gl; }, properties: { get(t) { return t === rt ? src : dst; } } };
  if (change) change(pass, target);
  if (fail) assert.throws(() => context.render.call(pass, renderer, null, target), /draw failed/);
  else context.render.call(pass, renderer, null, target);
  assert.strictEqual(renderer.autoClear, true);
  assert.strictEqual(rt.isWebGLMultisampleRenderTarget, true);
  return { pass, calls };
}
const direct = run();
assert.strictEqual(direct.pass.directResolveCount, 1);
assert.strictEqual(direct.pass.copyDrawCount, 0);
assert.deepStrictEqual(direct.calls.find(c => c[0] === 'blit').slice(-2), [0x4000, 0x2600], 'resolve only colour with nearest sampling');
assert.deepStrictEqual(direct.calls.filter(c => c[0] === 'bind').at(-1), ['bind', 0x8ca8, 'read']);
for (const change of [p => { p.directResolve = false; }, p => { p.renderToScreen = true; },
  (_, t) => { t.width = 1920; }, (_, t) => { t.height = 1080; }, (_, t) => { t.texture.type = 1016; },
  (_, t) => { t.texture.format = 1022; }, (_, t) => { t.texture.encoding = 3001; },
  (_, t) => { t.isWebGLMultisampleRenderTarget = true; }]) {
  const fallback = run(change);
  assert.strictEqual(fallback.pass.directResolveCount, 0);
  assert.strictEqual(fallback.pass.copyDrawCount, 1);
  assert.strictEqual(fallback.calls.some(c => c[0] === 'blit'), false);
}
run(null, true);
console.log('PASS direct colour resolve, framebuffer restoration, 8 compatibility fallbacks and exception restoration');
