'use strict';
const assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const THREE = require(path.join(root, 'js/vendor/three.min.js'));
const vendor = vm.createContext({ THREE, console });
for (const name of ['CopyShader', 'LuminosityHighPassShader', 'EffectComposer', 'ShaderPass', 'UnrealBloomPass']) {
  vm.runInContext(read('js/vendor/' + name + '.js'), vendor);
}
const source = read('js/core/scene-core.js'), threeSource = read('js/vendor/three.min.js');
function section(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  assert(a >= 0 && b > a, 'core sizing boundary: ' + start); return source.slice(a, b);
}
function rendererMethod(name) {
  const start = threeSource.indexOf('this.' + name + '=function'); assert(start >= 0, name);
  let end = threeSource.indexOf('{', start), depth = 1;
  while (depth && ++end < threeSource.length) {
    if (threeSource[end] === '{') depth++;
    if (threeSource[end] === '}') depth--;
  }
  assert.strictEqual(depth, 0); return threeSource.slice(start, end + 1) + ';';
}
const counts = { writes: 0, disposed: [], events: [] };
let width = 3840, height = 2160;
const canvas = { style: { width: '100%', height: '100%' } };
Object.defineProperty(canvas, 'width', { get: () => width, set: value => { width = value; counts.writes++; } });
Object.defineProperty(canvas, 'height', { get: () => height, set: value => { height = value; counts.writes++; } });
const renderer = new (Function('THREE', 'canvas',
  'var e=canvas,P=2,R=1920,C=1080,yt={isPresenting:false},vt=THREE.Vector2,St=THREE.Vector4,' +
  'N=new THREE.Vector4(0,0,1920,1080),T=new THREE.Vector4(0,0,3840,2160),q={viewport:function(){}};' +
  ['getPixelRatio','setPixelRatio','getSize','setSize','getDrawingBufferSize','setDrawingBufferSize',
    'getViewport','getCurrentViewport','setViewport'].map(rendererMethod).join('\n') +
  'this.domElement=e;this.capabilities={maxSamples:4,isWebGL2:true};' +
  'this.setCurrentViewportForTest=function(v){T.copy(v);};return this;'))(THREE, canvas);
const c = vm.createContext({ T: THREE, renderer, console, opts: {}, W: 1920, H: 1080, dpr: 2, deviceDpr: 2,
  isGL2: true, boost: 0, msaaSamples: 2, scenePass: null, composer: null, bloom: null, cine: null, rays: null,
  canvas: { parentNode: { clientWidth: 1920, clientHeight: 1080 } },
  scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(), bloomBase: .48,
  Mats: { RAYS_FS: '', CINE_FS: '' }, SKY_FULL: false, skyRT: null, skyDirty: false,
  bgMat: { uniforms: { tSky: { value: null } } }, degrade: 0, requestedDpr: 2,
  fiberMat: { uniforms: { uRes: { value: new THREE.Vector2(1, 1) }, uWidth: { value: 0 } } },
  glyphLine: { material: { uniforms: { uRes: { value: new THREE.Vector2(1, 1) }, uWidth: { value: 0 } } } },
  fiberWidth() { return 0.85 * c.dpr; }, glyphWidth() { return 2.3 * 2.4 * c.dpr; },
  qspec() { return { level: c.degrade }; }, targetDpr() { return c.requestedDpr; },
  fire(name, value) { counts.events.push({ name, level: value.level }); }
});
vm.runInContext(section('    function skyScale()', '    /* 旧屏幕空间背景') +
  section('    function samplesFor(', '    // 基础节点图数据结构') +
  section('    var bufferSizeRead = ', '    /* 显式指定档位') +
  section('    function resize()', '    function shaderErrors()'), c);
vm.runInContext('buildComposer(W,H);buildSkyRT()', c);
const identities = new WeakMap(); let nextId = 0;
function track() {
  const b = c.bloom;
  const entries = [['main1', c.composer.renderTarget1], ['main2', c.composer.renderTarget2], ['msaa', c.scenePass.rt],
    ['sky', c.skyRT], ['bright', b.renderTargetBright], ...b.renderTargetsHorizontal.map((rt, i) => ['H'+i, rt]),
    ...b.renderTargetsVertical.map((rt, i) => ['V'+i, rt])];
  for (const [role, rt] of entries) if (rt && !identities.has(rt)) {
    const id = ++nextId; identities.set(rt, id);
    rt.addEventListener('dispose', () => counts.disposed.push({ id, role }));
  }
}
function run(values = {}, forceResize = false) {
  Object.assign(c, values); track(); counts.writes = 0; counts.disposed = [];
  c.canvas.parentNode.clientWidth = c.W; c.canvas.parentNode.clientHeight = c.H;
  const resize = forceResize || Object.hasOwn(values, 'W') || Object.hasOwn(values, 'H');
  vm.runInContext(resize ? 'resize()' : 'applyDegrade()', c); track();
}
function assertLayout(w, h, dpr, samples, firstMip) {
  const pw = w*dpr, ph = h*dpr, pixels = [Math.floor(pw), Math.floor(ph)];
  assert.deepStrictEqual(renderer.getSize(new THREE.Vector2()).toArray(), [w,h]);
  assert.strictEqual(renderer.getPixelRatio(), dpr);
  assert.deepStrictEqual([canvas.width, canvas.height], pixels);
  assert.deepStrictEqual(renderer.getDrawingBufferSize(new THREE.Vector2()).toArray(), pixels);
  assert.deepStrictEqual(renderer.getViewport(new THREE.Vector4()).toArray(), [0,0,w,h]);
  assert.deepStrictEqual(renderer.getCurrentViewport(new THREE.Vector4()).toArray(), [0,0,...pixels]);
  assert.deepStrictEqual(canvas.style, { width: '100%', height: '100%' });
  assert.deepStrictEqual([c.composer._width,c.composer._height,c.composer._pixelRatio], [w,h,dpr]);
  for (const rt of [c.composer.renderTarget1,c.composer.renderTarget2]) assert.deepStrictEqual([rt.width,rt.height], [pw,ph]);
  assert.strictEqual(c.scenePass.samples, samples);
  if (samples) assert.deepStrictEqual([c.scenePass.rt.width,c.scenePass.rt.height,c.scenePass.rt.samples], [pw,ph,samples]);
  else assert.strictEqual(c.scenePass.rt, null);
  if (firstMip) {
    let [x,y] = firstMip;
    assert.deepStrictEqual([c.bloom.renderTargetBright.width,c.bloom.renderTargetBright.height], [x,y]);
    for (let i=0; i<c.bloom.nMips; i++) {
      for (const rt of [c.bloom.renderTargetsHorizontal[i],c.bloom.renderTargetsVertical[i]]) assert.deepStrictEqual([rt.width,rt.height], [x,y]);
      assert.deepStrictEqual(c.bloom.separableBlurMaterials[i].uniforms.texSize.value.toArray(), [x,y]);
      x=Math.round(x/2); y=Math.round(y/2);
    }
  }
}
function noRebuild() { assert.strictEqual(counts.writes, 0); assert.deepStrictEqual(counts.disposed, []); }
let passed = 0;
function check(name, body) { body(); passed++; console.log('PASS '+name); }

check('same quality and repeated resize retain physical buffers', () => {
  run(); noRebuild(); assertLayout(1920,1080,2,2,[760,428]);
  run({},true); noRebuild();
});
check('both logical and current viewport are repaired without canvas reset', () => {
  renderer.setViewport(13,21,800,600); run(); noRebuild(); assertLayout(1920,1080,2,2);
  renderer.setCurrentViewportForTest(new THREE.Vector4(0,0,720,420)); run(); noRebuild(); assertLayout(1920,1080,2,2);
});
check('stale bloom texSize is repaired without disposing matching targets', () => {
  c.bloom.separableBlurMaterials[2].uniforms.texSize.value.set(1,1);
  run(); noRebuild(); assertLayout(1920,1080,2,2,[760,428]);
});
check('actual composer metadata overrides equal physical pixel dimensions', () => {
  c.composer.setPixelRatio(1); c.composer.setSize(3840,2160);
  run(); assert.strictEqual(counts.writes,0); assertLayout(1920,1080,2,2,[760,428]);
  run({W:960,H:540}); assertLayout(960,540,2,2,[480,270]);
});
check('fractional DPR and viewport update renderer, RTs, camera and post uniforms', () => {
  run({W:1919,H:1079,requestedDpr:1.27}); assert.strictEqual(counts.writes,2);
  assertLayout(1919,1079,1.27,2,[614,345]);
  assert.strictEqual(c.camera.aspect,1919/1079);
  for (const pass of [c.cine,c.rays]) assert.deepStrictEqual(pass.uniforms.uRes.value.toArray(),[1919,1079]);
});
check('portrait and real DPR-only changes remain effective', () => {
  run({W:390,H:844,requestedDpr:2}); assertLayout(390,844,2,2,[195,422]);
  run({W:1920,H:1080,requestedDpr:2}); run({requestedDpr:1.49});
  assert.strictEqual(counts.writes,2); assert(counts.disposed.length>0); assertLayout(1920,1080,1.49,2,[710,400]);
});
check('MSAA pixel threshold is honored in both directions', () => {
  run({requestedDpr:1,deviceDpr:1}); assertLayout(1920,1080,1,4);
  run({W:2600,H:2400}); assertLayout(2600,2400,1,2);
  run({W:1920,H:1080}); assertLayout(1920,1080,1,4);
});
check('sample-only changes replace only the MSAA target', () => {
  renderer.capabilities.maxSamples=2; run(); assertLayout(1920,1080,1,2);
  assert.strictEqual(counts.writes,0); assert.deepStrictEqual(counts.disposed.map(x=>x.role),['msaa']);
  run({isGL2:false}); assertLayout(1920,1080,1,0);
  assert.strictEqual(counts.writes,0); assert.deepStrictEqual(counts.disposed.map(x=>x.role),['msaa']);
  run({isGL2:true}); assertLayout(1920,1080,1,2);
});
check('fiber/glyph line mats get physical uRes and dpr widths on resize and tier changes', () => {
  run({W:960,H:540,requestedDpr:2});
  assert.deepStrictEqual(c.fiberMat.uniforms.uRes.value.toArray(), [960 * 2, 540 * 2]);
  assert.deepStrictEqual(c.glyphLine.material.uniforms.uRes.value.toArray(), [960 * 2, 540 * 2]);
  assert.strictEqual(c.fiberMat.uniforms.uWidth.value, 0.85 * 2);
  assert.strictEqual(c.glyphLine.material.uniforms.uWidth.value, 2.3 * 2.4 * 2);
  run({requestedDpr:1.49});
  assert.deepStrictEqual(c.fiberMat.uniforms.uRes.value.toArray(), [960 * 1.49, 540 * 1.49]);
  assert.strictEqual(c.fiberMat.uniforms.uWidth.value, 0.85 * 1.49);
  assert.strictEqual(c.glyphLine.material.uniforms.uWidth.value, 2.3 * 2.4 * 1.49);
  run({W:1920,H:1080,requestedDpr:1,deviceDpr:1}); assert.deepStrictEqual(c.fiberMat.uniforms.uRes.value.toArray(), [1920, 1080]);
});
check('same canvas tier change still rebuilds legacy sky and emits quality', () => {
  run({degrade:1}); assert.strictEqual(counts.writes,0);
  assert.deepStrictEqual(counts.disposed.map(x=>x.role),['sky']);
  assert.deepStrictEqual([c.skyRT.width,c.skyRT.height],[768,432]);
  assert.deepStrictEqual(counts.events[counts.events.length-1],{name:'degrade',level:1});
});
check('actual shared sky-post receives resize and independent tier changes', () => {
  const window={THREE,CLSkyTokens:{LAYER_DISC:4,reduced(){return false;}},
    CLSkyUtil:{clamp:(v,lo,hi)=>Math.max(lo,Math.min(hi,v))},console};
  vm.runInNewContext(read('js/sky/sky-post.js'),{window,console});
  const post=window.CLSkyPost.install({renderer,scene:c.scene,camera:c.camera,core(){return {getComposer(){return c.composer;}};}});
  assert.strictEqual(post.stats().installed,true);
  run(); noRebuild();
  post.setTier('mid'); assert.deepStrictEqual(Array.from(post.stats().rt),[960,540]);
  run({W:390,H:844,requestedDpr:2}); assert.deepStrictEqual(Array.from(post.stats().rt),[390,844]);
  post.setTier('high'); assert.deepStrictEqual(Array.from(post.stats().rt),[780,1688]);
  run(); noRebuild(); assertLayout(390,844,2,2,[195,422]);
});
check('native 4K retains 2x MSAA when boosted and honors hardware capability', () => {
  renderer.capabilities.maxSamples=4; run({W:1920,H:1080,boost:1}); assertLayout(1920,1080,2,2,[760,428]);
  run({boost:0}); assertLayout(1920,1080,2,2);
  renderer.capabilities.maxSamples=2; run({boost:1}); assertLayout(1920,1080,2,2);
  renderer.capabilities.maxSamples=4; run({boost:0}); assertLayout(1920,1080,2,2);
});
console.log('SCENE BUFFER SIZING OK · '+passed+' CPU resource contracts · no GPU context');
