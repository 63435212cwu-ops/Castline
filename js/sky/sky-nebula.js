(function (g) {
'use strict';
var T = g.CLSkyTokens, MAX = 2000, EDGE = 1.3, PLANE = 2.6;

var GL = g.CLSkyNebulaGLSL;

function cloudAxis(key, arr, index) {
var name = String(key == null ? '' : key), h = 2166136261, j;
for (j = 0; j < name.length; j++) { h = Math.imul(h ^ name.charCodeAt(j), 16777619); }
var angle = (h >>> 0) / 4294967296 * Math.PI * 2;
arr[index * 2] = Math.cos(angle); arr[index * 2 + 1] = Math.sin(angle);
}

g.CLSkyNebula = { create: function (opts) {
opts = opts || {};
var S = opts.scene, tier = 'high', state = 'hidden';
var alpha = 0, target = 0, hoverIdx = -1, needSplat = true, splats = 0, starsN = 0, groupsN = 0;
var fadeAlpha = 0, fadeElapsed = 0;
var R = 1, pitch = 0, anchor = null, mesh = null, splatPoints = null;
var splatScene = null, splatCam = null, splatRT = null, lastCfg = null, lastLobe = 1, radBase = null;
var planeGeo = null, volN = -1, splatGeo = null, matNeb = null, matSplat = null, posAttr = null, list = null, noiseTex = null;
var uGroupK = [], uGroupT = [], uRT = null, uTimeU = null, uAlphaU = null, tSplatU = null, uCamU = null, uNSU = null, v2 = null;
var uScaleU = {value: 1}, uInvU = {value: 1}, splatHalf = true, overlapM = 1, muClock = -1, radArr = null;
var uTime = 0, lastAnim = null, rtSize = 0, i, k, col, gd, w, nd, src;
var nativeCloudScale = typeof opts.nativeCloudScale === 'number' ? Math.max(0.5, Math.min(1, opts.nativeCloudScale)) : 0.75;
var cloudRT = null, cloudScene = null, cloudCopy = null, cloudComposite = null, cloudCompositeMat = null;
var cloudScale = 1, cloudDraws = 0, cloudRTCreates = 0, cloudRTDisposes = 0, cloudSupport = null, cloudFailed = false;
var cloudV2 = new THREE.Vector2(), cloudColor = new THREE.Color(), cloudViewport = new THREE.Vector4(), cloudScissor = new THREE.Vector4();
var zSum = [], zSq = [], zN = [], gThick = [];
var tmpV = new THREE.Vector3(), tmpC = new THREE.Color();

function densityAlpha() {
var n = starsN || 0;
return n > 320 ? 0.72 : n > 180 ? 0.76 : n > 90 ? 0.84 : n > 42 ? 0.90 : 1;
}

function td() { return T.TIER[tier] || T.TIER.high; }
function ensureNoise() { if (!noiseTex) { noiseTex = g.CLSkyCloudNoise.create(THREE); } return noiseTex; }
function mkBlend(o) {
var r = {transparent:true, depthTest:false, depthWrite:false, blending:THREE.AdditiveBlending, premultipliedAlpha: true}, key;
for (key in o) { if (o.hasOwnProperty(key)) { r[key] = o[key]; } } return r;
}

function halfFloatOK() {
var r = S.renderer, caps = r && r.capabilities, ext = r && r.extensions;
if (caps && caps.isWebGL2) { return true; }
return !!(ext && typeof ext.get === 'function' &&
ext.get('OES_texture_half_float') && ext.get('OES_texture_half_float_linear') && ext.get('EXT_color_buffer_half_float'));
}

function cloudHalfFloatOK() {
if (cloudSupport !== null) { return cloudSupport; }
var r = S.renderer, gl = r && r.getContext ? r.getContext() : null;
cloudSupport = !!(r && r.capabilities && r.capabilities.isWebGL2 && gl && THREE.HalfFloatType &&
  (gl.getExtension('EXT_color_buffer_float') || gl.getExtension('EXT_color_buffer_half_float')));
return cloudSupport;
}

function releaseCloudRT() {
if (cloudRT) { cloudRT.dispose(); cloudRT = null; cloudRTDisposes++; }
if (cloudCompositeMat) { cloudCompositeMat.uniforms.tCloud.value = null; }
}

var dnaOn = false, dnaFray = 0, dnaCut = 0, dnaBands = 1, dnaWant = 1, dnaLobe = 1;

function setDNA(d) {
var f = (d && d.fields) || null;
if (!d || !f) {
if (dnaOn) {
dnaOn = false; dnaLobe = 1; lastLobe = 1;
ensureSplatMat();
applyLobeRadii();
needSplat = true;
}
return false;
}
dnaOn = true;
dnaFray = typeof f.fray === 'number' ? f.fray : 0;
dnaCut = typeof f.cut === 'number' ? f.cut : 0;
dnaLobe = typeof f.lobe === 'number' ? f.lobe : 1;
dnaWant = Math.round(Math.max(1, Math.min(3, typeof f.layerBands === 'number' ? f.layerBands : 1)));
dnaBands = T.dnaBands ? T.dnaBands(tier, dnaWant) : dnaWant;
ensureSplatMat();
needSplat = true;
if (dnaLobe !== lastLobe) { applyLobeRadii(); }
lastLobe = dnaLobe;
return true;
}

function setNativeCloudScale(value) {
nativeCloudScale = Math.max(0.5, Math.min(1, typeof value === 'number' && isFinite(value) ? value : 1));
cloudFailed = false;
cloudSupport = null;
if (nativeCloudScale === 1) { releaseCloudRT(); }
return nativeCloudScale;
}

function ensureCloudComposite() {
if (cloudScene) { return; }
cloudScene = new THREE.Scene();
cloudCopy = new THREE.Mesh(planeGeo, matNeb); cloudCopy.matrixAutoUpdate = false; cloudCopy.frustumCulled = false;
cloudScene.add(cloudCopy);
cloudCompositeMat = new THREE.ShaderMaterial(mkBlend({uniforms:{tCloud:{value:null}},
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.0,1.0);}',
  fragmentShader:'uniform sampler2D tCloud;varying vec2 vUv;void main(){gl_FragColor=texture2D(tCloud,vUv);}'}));
cloudComposite = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), cloudCompositeMat);
cloudComposite.name = 'sky-nebula-composite'; cloudComposite.frustumCulled = false; cloudComposite.renderOrder = -50;
cloudComposite.visible = false; S.scene.add(cloudComposite);
}

function renderCloudView() {
var r = S.renderer, visible = !!(mesh && alpha > 0.002), wanted = 1;
if (visible && nativeCloudScale < 1 && tier === 'high' && volN > 1 && !T.reduced() && !cloudFailed && cloudHalfFloatOK()) {
  r.getDrawingBufferSize(cloudV2);
  if (cloudV2.x * cloudV2.y > 6e6) { wanted = Math.min(nativeCloudScale, Math.sqrt(4.7e6 / Math.max(1, cloudV2.x * cloudV2.y))); }
}
cloudScale = wanted;
if (wanted === 1) {
  if (mesh) { mesh.visible = visible; }
  if (cloudComposite) { cloudComposite.visible = false; }
  return;
}
ensureCloudComposite();
var cw = Math.max(2, Math.floor(cloudV2.x * wanted)), ch = Math.max(2, Math.floor(cloudV2.y * wanted)), newTarget = false;
if (!cloudRT || cloudRT.width !== cw || cloudRT.height !== ch) {
  releaseCloudRT();
  cloudRT = new THREE.WebGLRenderTarget(cw, ch, {type:THREE.HalfFloatType,format:THREE.RGBAFormat,
    minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,depthBuffer:false,stencilBuffer:false});
  cloudRT.texture.generateMipmaps = false; cloudRT.texture.encoding = THREE.LinearEncoding;
  cloudCompositeMat.uniforms.tCloud.value = cloudRT.texture; cloudRTCreates++;
  newTarget = true;
}
mesh.updateWorldMatrix(true, false); cloudCopy.geometry = planeGeo; cloudCopy.material = matNeb;
cloudCopy.matrix.copy(mesh.matrixWorld); cloudCopy.layers.mask = mesh.layers.mask; cloudComposite.layers.mask = mesh.layers.mask;
var oldTarget = r.getRenderTarget(), oldAlpha = r.getClearAlpha(), oldAuto = r.autoClear;
r.getClearColor(cloudColor); r.getViewport(cloudViewport); r.getScissor(cloudScissor); var oldScissorTest = r.getScissorTest();
try {
  r.setRenderTarget(cloudRT);
  var gl = r.getContext();
  if (newTarget && gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) { cloudFailed = true; }
  else {
    r.setScissorTest(false); r.setClearColor(0, 0); r.autoClear = false; r.clear(true, true, false);
    r.render(cloudScene, S.camera); cloudDraws++;
  }
} finally {
  r.setRenderTarget(oldTarget); r.setClearColor(cloudColor, oldAlpha); r.autoClear = oldAuto;
  r.setViewport(cloudViewport); r.setScissor(cloudScissor); r.setScissorTest(oldScissorTest);
}
if (cloudFailed) { releaseCloudRT(); cloudScale = 1; mesh.visible = visible; cloudComposite.visible = false; }
else { mesh.visible = false; cloudComposite.visible = visible; }
}
function makeRT(size) {
splatHalf = halfFloatOK();
var mip = !!(S.renderer && S.renderer.capabilities && S.renderer.capabilities.isWebGL2);
GL.mip = mip;
var rt = new THREE.WebGLRenderTarget(size, size, {minFilter: mip ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter, magFilter:THREE.LinearFilter,
format:THREE.RGBAFormat, type: splatHalf ? THREE.HalfFloatType : THREE.UnsignedByteType,
depthBuffer:false, stencilBuffer:false});
rt.texture.generateMipmaps = mip;
rt.texture.wrapS = THREE.ClampToEdgeWrapping;
rt.texture.wrapT = THREE.ClampToEdgeWrapping;
return rt;
}

function measureOverlap() {
var arr = posAttr ? posAttr.array : null, n = starsN, best = 1, cell = 0.2, j, dx, dy, r;
if (!arr || !radArr || n < 2) { overlapM = 1; return; }
for (i = 0; i < n; i++) { if (radArr[i] > cell) { cell = radArr[i]; } }
cell *= 2;
var bins = {}, cnt, gx, gy, lst, key;
for (i = 0; i < n; i++) {
key = Math.floor(arr[i * 3] / cell) * 65536 + Math.floor(arr[i * 3 + 1] / cell);
if (bins[key]) { bins[key].push(i); } else { bins[key] = [i]; }
}
for (i = 0; i < n; i++) {
cnt = 1;
gx = Math.floor(arr[i * 3] / cell); gy = Math.floor(arr[i * 3 + 1] / cell);
for (var ox = gx - 1; ox <= gx + 1; ox++) {
for (var oy = gy - 1; oy <= gy + 1; oy++) {
lst = bins[ox * 65536 + oy];
if (!lst) { continue; }
for (j = 0; j < lst.length; j++) {
var o = lst[j];
if (o === i) { continue; }
dx = arr[i * 3] - arr[o * 3]; dy = arr[i * 3 + 1] - arr[o * 3 + 1]; r = radArr[i] + radArr[o];
if (dx * dx + dy * dy < r * r) { cnt++; }
}
}
}
if (cnt > best) { best = cnt; }
}
overlapM = best;
}

function applySplatScale() {
var s = 1;
if (!splatHalf) {
var peak = (GL.SPLAT_PEAK || 0.62) * Math.max(1, overlapM) * (hoverIdx >= 0 ? 1.9 : 1);
if (peak > 0.98) { s = 0.98 / peak; }
}
uScaleU.value = s; uInvU.value = 1 / s;
}

function ensureScene() {
if (!splatScene) {
splatScene = new THREE.Scene();
splatCam = new THREE.OrthographicCamera(-EDGE, EDGE, EDGE, -EDGE, -10, 10);
uRT = {value:rtSize || 128};
}
ensureSplatMat();
}

function slices() {
var v = T.VOL && T.VOL.slices ? T.VOL.slices[tier] : null;
if (T.reduced()) { return 0; }
return (typeof v === 'number' && v > 1) ? v | 0 : 0;
}

function ensureGeo() {
var n = slices();
if (!planeGeo) { planeGeo = GL.volGeo(1, PLANE); }
volN = n;
if (mesh) { mesh.geometry = planeGeo; }
}

function ensureNebMat() {
var oct = td().fbm | 0;
src = GL.volFrag(oct, T.VOL ? T.VOL.jitter : 0.12, slices(), undefined, dnaBands);
ensureNoise();
if (!matNeb) {
uTimeU = {value:0}; uAlphaU = {value:0}; tSplatU = {value:null}; uCamU = {value:new THREE.Vector3()}; uNSU = {value:24};
matNeb = new THREE.ShaderMaterial(mkBlend({uniforms:{tSplat:tSplatU, tNoise:{value:noiseTex}, uTime:uTimeU, uAlpha:uAlphaU, uCam:uCamU, uNS:uNSU, uInv:uInvU},
vertexShader:GL.VOL_VS, fragmentShader:src}));
} else if (matNeb.fragmentShader !== src) {
matNeb.fragmentShader = src; matNeb.needsUpdate = true;
}
if (splatRT) { tSplatU.value = splatRT.texture; }
ensureSplatMat();
}

function ensureSplatMat() {
var want = GL.splatFrag && dnaOn ? GL.splatFrag({on:true, fray:dnaFray, cut:dnaCut}) : GL.SPLAT_FS;
if (!matSplat) {
uRT = uRT || {value:128};
matSplat = new THREE.ShaderMaterial(mkBlend({uniforms:{uRT:uRT, uScale:uScaleU, tNoise:{value:ensureNoise()}, uGroupK:{value:uGroupK}, uGroupT:{value:uGroupT}},
vertexShader:GL.SPLAT_VS, fragmentShader:want}));
} else if (matSplat.fragmentShader !== want) {
matSplat.fragmentShader = want; matSplat.needsUpdate = true;
}
}

function ensureRT() {
var want = td().nebulaRT | 0, hf = halfFloatOK();
if (splatRT && rtSize === want && splatHalf === hf) { return; }
if (splatRT) { splatRT.dispose(); }
splatRT = makeRT(want); rtSize = want;
if (uRT) { uRT.value = rtSize; } else { uRT = {value:rtSize}; }
if (tSplatU) { tSplatU.value = splatRT.texture; }
needSplat = true;
}

function applyHover() {
for (i = 0; i < 32; i++) {
uGroupK[i] = hoverIdx >= 0 ? (i === hoverIdx ? 1.9 : 0.6) : 1.0;
if (typeof uGroupT[i] !== 'number') { uGroupT[i] = 0; }
}
if (matSplat) { matSplat.uniforms.uGroupK.value = uGroupK; matSplat.uniforms.uGroupT.value = uGroupT; }
needSplat = true;
}

function syncPos() {
var arr, it, n, gi, sd, mx = 0;
if (!posAttr || !list || !anchor) { return; }
arr = posAttr.array; n = list.length;
for (i = 0; i < 32; i++) { zSum[i] = 0; zSq[i] = 0; zN[i] = 0; }
for (i = 0; i < n; i++) {
it = list[i];
if (!it.g) { continue; }
it.g.getWorldPosition(tmpV);
anchor.worldToLocal(tmpV);
arr[i * 3] = tmpV.x; arr[i * 3 + 1] = tmpV.y; arr[i * 3 + 2] = 0;
gi = it.gi; zSum[gi] += tmpV.z; zSq[gi] += tmpV.z * tmpV.z; zN[gi]++;
}
posAttr.needsUpdate = true;
for (i = 0; i < 32; i++) {
if (zN[i] < 2) { gThick[i] = 0; continue; }
sd = zSq[i] / zN[i] - (zSum[i] / zN[i]) * (zSum[i] / zN[i]);
gThick[i] = sd > 0 ? Math.sqrt(sd) : 0;
if (gThick[i] > mx) { mx = gThick[i]; }
}
for (i = 0; i < 32; i++) { uGroupT[i] = mx > 1e-6 ? Math.max(0.35, gThick[i] / mx) : (zN[i] ? 0.35 : 0); }
if (matSplat) { matSplat.uniforms.uGroupT.value = uGroupT; }
}

function renderSplat() {
var r = S.renderer, pRT, pA, pa;
if (!r || !splatRT || !splatScene) { return; }
applySplatScale();
pRT = r.getRenderTarget(); pA = r.autoClear; pa = r.getClearAlpha();
r.getClearColor(tmpC);
r.autoClear = true;
r.setClearColor(T.C.VOID0, 0);
r.setRenderTarget(splatRT);
r.clear(true, true, false);
r.render(splatScene, splatCam);
r.setRenderTarget(pRT);
r.setClearColor(tmpC, pa);
r.autoClear = pA;
}

var gCountCache = [], gMinCache = 0, gSpanCache = 1;

function lobeKOf(gi) {
if (!dnaOn || !(dnaLobe > 1) || !gCountCache.length) { return 1; }
var c = gCountCache[gi];
if (typeof c !== 'number') { return 1; }
return 1 + (dnaLobe - 1) * ((c - gMinCache) / gSpanCache);
}

function lobeKSnapshot() {
var out = [], i2;
for (i2 = 0; i2 < gCountCache.length && i2 < 32; i2++) { out.push(+lobeKOf(i2).toFixed(4)); }
return out;
}

function applyLobeRadii() {
var arr = radArr, base = radBase, gArr, k2, kk, changed = false;
if (!arr || !base || !splatGeo) { return false; }
gArr = splatGeo.getAttribute('aGroup');
if (!gArr) { return false; }
for (k2 = 0; k2 < arr.length; k2++) {
kk = base[k2] * lobeKOf(gArr.getX(k2));
if (Math.abs(kk - arr[k2]) > 1e-9) { arr[k2] = kk; changed = true; }
}
if (changed) {
if (splatGeo.getAttribute('aRad')) { splatGeo.getAttribute('aRad').needsUpdate = true; }
measureOverlap();
needSplat = true;
}
return changed;
}

function build(cfg) {
cfg = cfg || {};
lastCfg = cfg;
if (typeof cfg.R === 'number' && cfg.R > 0) { R = cfg.R; }
if (typeof cfg.pitch === 'number') { pitch = cfg.pitch; }

if (anchor && anchor.parent) { anchor.parent.remove(anchor); }
anchor = new THREE.Object3D();
S.group.add(anchor);
anchor.rotation.set(-pitch, 0, 0);
anchor.scale.set(R, R, R);

ensureScene(); ensureRT(); ensureGeo(); ensureNebMat();

if (!mesh) {
mesh = new THREE.Mesh(planeGeo, matNeb);
mesh.name = 'sky-nebula-volume';
mesh.renderOrder = -50;
mesh.frustumCulled = false;
mesh.userData.cloudSampler = {setScale:setNativeCloudScale, render:renderCloudView};
}
anchor.add(mesh);
mesh.geometry = planeGeo;
mesh.material = matNeb;
mesh.visible = alpha > 0.002;

var groups = cfg.groups || [], stars = cfg.stars || [];
var n = stars.length > MAX ? MAX : stars.length;
var pos = new Float32Array(n * 3), aCol = new Float32Array(n * 3);
var aRad = new Float32Array(n), aBase = new Float32Array(n), aGroup = new Float32Array(n), used = [], seen = {}, radBaseVal = 0;
var aCloudAxis = new Float32Array(n * 2);

var gCount = [], gi2;
for (i = 0; i < groups.length && i < 32; i++) { gCount[i] = 0; }
for (i = 0; i < n; i++) { gi2 = stars[i].group | 0; if (gi2 >= 0 && gi2 < 32) { gCount[gi2]++; } }
var gMax = 1, gMin = Infinity;
for (i = 0; i < groups.length && i < 32; i++) { if (gCount[i] > gMax) { gMax = gCount[i]; } if (gCount[i] > 0 && gCount[i] < gMin) { gMin = gCount[i]; } }
if (!isFinite(gMin)) { gMin = gMax; }
var gSpan = Math.max(1, gMax - gMin);
gCountCache = gCount.slice(0); gMinCache = gMin; gSpanCache = gSpan;

list = [];
for (i = 0; i < n; i++) {
gd = stars[i].group | 0;
if (gd < 0 || gd >= groups.length) { continue; }
col = groups[gd].color | 0;
w = typeof stars[i].w01 === 'number' ? stars[i].w01 : 0.5;
if (w < 0) { w = 0; } else if (w > 1) { w = 1; }
k = used.length;
used.push(gd);
aCol[k * 3] = ((col >> 16) & 255) / 255 * (0.45 + 0.55 * w);
aCol[k * 3 + 1] = ((col >> 8) & 255) / 255 * (0.45 + 0.55 * w);
aCol[k * 3 + 2] = (col & 255) / 255 * (0.45 + 0.55 * w);
radBaseVal = (cfg.rad > 0 ? cfg.rad : 0.16) * (0.9 + 0.6 * w);
aBase[k] = radBaseVal;
aRad[k] = radBaseVal;
aGroup[k] = gd;
cloudAxis(stars[i].key, aCloudAxis, k);
nd = S.nodeOf ? S.nodeOf('c:' + stars[i].key) : null;
list.push({g: nd ? nd.g : null, gi: gd < 32 ? gd : 31});
}
starsN = used.length;
groupsN = 0;
for (i = 0; i < used.length; i++) { if (!seen[used[i]]) { seen[used[i]] = 1; groupsN++; } }

if (splatGeo) { splatGeo.dispose(); splatGeo = null; }
if (splatPoints && splatPoints.parent) { splatPoints.parent.remove(splatPoints); }
splatPoints = null; posAttr = null;

if (starsN > 0) {
splatGeo = new THREE.BufferGeometry();
posAttr = new THREE.Float32BufferAttribute(pos, 3);
posAttr.setUsage(THREE.DynamicDrawUsage);
splatGeo.setAttribute('position', posAttr);
splatGeo.setAttribute('aCol', new THREE.Float32BufferAttribute(aCol, 3));
splatGeo.setAttribute('aRad', new THREE.Float32BufferAttribute(aRad, 1));
radArr = aRad;
radBase = aBase;
applyLobeRadii();
splatGeo.setAttribute('aGroup', new THREE.Float32BufferAttribute(aGroup, 1));
splatGeo.setAttribute('aCloudAxis', new THREE.Float32BufferAttribute(aCloudAxis, 2));
splatGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2);
splatPoints = new THREE.Points(splatGeo, matSplat);
splatPoints.frustumCulled = false;
splatPoints.matrixAutoUpdate = false;
splatPoints.updateMatrix();
splatScene.add(splatPoints);
anchor.updateMatrixWorld(true);
syncPos();
measureOverlap();
muClock = -1;
}

applyHover();
needSplat = true;
}

function update(dt, tAnim, live) {
var reducedMotion = T.reduced();
var t = (typeof dt === 'number' && dt > 0) ? dt : 0;
var flying = !!live;
if (matNeb && slices() !== volN) { ensureGeo(); ensureNebMat(); }

target = (state === 'show' ? T.ALPHA.nebula : state === 'dim' ? T.ALPHA.nebulaDim : 0) * densityAlpha();
if (reducedMotion) {
alpha = target;
fadeAlpha = alpha; fadeElapsed = T.DUR.focus;
} else if (state === 'hidden') {
fadeElapsed = Math.min(T.DUR.focus, fadeElapsed + t);
var f = Math.min(1, fadeElapsed / Math.max(T.DUR.focus, 1e-3));
alpha = fadeAlpha * (1 - f * f * (3 - 2 * f));
} else {
alpha += (target - alpha) * (1 - Math.exp(-t / Math.max(T.DUR.focus, 1e-3)));
if (Math.abs(target - alpha) < 1e-4) { alpha = target; }
}
if (uAlphaU) { uAlphaU.value = alpha * (1 - structureMix * (1 - T.ALPHA.structureKeep)); }
if (mesh) { mesh.visible = alpha > 0.002; }

var anim = typeof tAnim === 'number' && isFinite(tAnim) ? tAnim : null;
if (tier !== 'low' && !reducedMotion && !structureMix && lastAnim !== null && anim !== null) {
uTime += Math.min(t, 0.05, Math.max(0, anim - lastAnim));
}
lastAnim = anim;
if (uTimeU) { uTimeU.value = uTime; }
if (uCamU && anchor && volN > 1 && mesh && mesh.visible) {
anchor.updateMatrixWorld(true);
uCamU.value.copy(S.camera.position); anchor.worldToLocal(uCamU.value);
v2 = v2 || new THREE.Vector2(); S.renderer.getDrawingBufferSize(v2);
var fullPixels = tier === 'high' ? 8.3e6 : 2.1e6;
uNSU.value = Math.round(volN * Math.max(0.6, Math.min(1, Math.sqrt(fullPixels / Math.max(1, v2.x * v2.y)))));
}

if (!splatRT || !splatPoints) { needSplat = false; renderCloudView(); return; }
if (flying) {
anchor.updateMatrixWorld(true); syncPos();
if (!splatHalf && uTime - muClock > 0.25) { muClock = uTime; measureOverlap(); }
}
if (needSplat || (flying && tier !== 'low')) { renderSplat(); splats++; }
needSplat = false;
renderCloudView();
}

var structureMix = 0;
function setStructure(v) { structureMix = Math.max(0, Math.min(1, +v || 0)); if (uAlphaU) uAlphaU.value = alpha * (1 - structureMix * (1 - T.ALPHA.structureKeep)); }
function setState(s, now) {
var next = (s === 'show' || s === 'dim') ? s : 'hidden';
if (next !== state) { fadeAlpha = alpha; fadeElapsed = 0; }
state = next;
if (now || T.reduced()) {
alpha = (state === 'show' ? T.ALPHA.nebula : state === 'dim' ? T.ALPHA.nebulaDim : 0) * densityAlpha();
fadeAlpha = alpha; fadeElapsed = state === 'hidden' ? T.DUR.focus : 0;
if (uAlphaU) { uAlphaU.value = alpha * (1 - structureMix * (1 - T.ALPHA.structureKeep)); }
if (mesh) { mesh.visible = alpha > 0.002; }
if (cloudComposite && !(alpha > 0.002)) { cloudComposite.visible = false; }
}
}

function hover(gi) {
hoverIdx = (typeof gi === 'number' && gi >= 0) ? gi | 0 : -1;
if (uGroupK.length) { applyHover(); }
}

function setTier(t) {
if (t !== 'high' && t !== 'mid' && t !== 'low') { return; }
if (t === tier) { return; }
tier = t;
if (dnaOn && T.dnaBands) { dnaBands = T.dnaBands(tier, dnaWant); }
ensureRT(); ensureGeo(); ensureNebMat();
if (mesh) { mesh.material = matNeb; mesh.geometry = planeGeo; }
needSplat = true;
}

function stats() {
return {dna:dnaOn, dnaFray:dnaFray, dnaCut:dnaCut, dnaBands:dnaBands, dnaWant:dnaWant, dnaLobe:dnaLobe, lobeK:lobeKSnapshot(), radBase0:radBase&&radBase.length?+radBase[0].toFixed(6):null, radNow0:radArr&&radArr.length?+radArr[0].toFixed(6):null, groups:groupsN, stars:starsN, rt:rtSize, state:state, alpha:alpha, splats:splats,
slices:volN < 0 ? 0 : volN, steps:volN > 1 && uNSU ? uNSU.value : 0, detailTexture:noiseTex ? 256 : 0, thick:uGroupT.slice(0, Math.max(1, groupsN)),
rtFloat:splatHalf, splatScale:+uScaleU.value.toFixed(4), overlap:overlapM,
viewScale:cloudScale, nativeCloudScale:nativeCloudScale, viewRT:cloudRT ? [cloudRT.width,cloudRT.height] : null,
viewEncoding:cloudRT ? cloudRT.texture.encoding : null, viewType:cloudRT ? cloudRT.texture.type : null,
viewActive:!!(cloudComposite && cloudComposite.visible), viewDraws:cloudDraws,
viewRTCreates:cloudRTCreates, viewRTDisposes:cloudRTDisposes, viewFailed:cloudFailed};
}

function dispose() {
releaseCloudRT();
if (cloudComposite) {
  if (cloudComposite.parent) { cloudComposite.parent.remove(cloudComposite); }
  cloudComposite.geometry.dispose(); cloudComposite = null;
}
if (cloudCompositeMat) { cloudCompositeMat.dispose(); cloudCompositeMat = null; }
if (cloudScene && cloudCopy) { cloudScene.remove(cloudCopy); }
cloudCopy = null; cloudScene = null; cloudScale = 1;
if (mesh) { if (mesh.parent) { mesh.parent.remove(mesh); } mesh = null; }
if (anchor && anchor.parent) { anchor.parent.remove(anchor); }
anchor = null;
if (splatPoints && splatPoints.parent) { splatPoints.parent.remove(splatPoints); }
splatPoints = null;
if (splatGeo) { splatGeo.dispose(); splatGeo = null; }
if (planeGeo) { planeGeo.dispose(); planeGeo = null; }
volN = -1;
if (matNeb) { matNeb.dispose(); matNeb = null; }
if (matSplat) { matSplat.dispose(); matSplat = null; }
if (splatRT) { splatRT.dispose(); splatRT = null; }
if (noiseTex) { noiseTex.dispose(); noiseTex = null; }
splatScene = null; splatCam = null;
posAttr = null; list = null; radArr = null; overlapM = 1; muClock = -1; splats = 0; starsN = 0; groupsN = 0;
}

return {build:build, update:update, setState:setState, setStructure:setStructure, hover:hover,
setTier:setTier, setNativeCloudScale:setNativeCloudScale, setDNA:setDNA, renderCloudView:renderCloudView, stats:stats, dispose:dispose};
} };
})(window);
