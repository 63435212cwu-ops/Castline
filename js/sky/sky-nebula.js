/*! 势力星云 nebula — 成员星实时平面坐标溅射(splat)出的发光气团，单张面片上沿视线步进成体积
 * @role nebula
 * @owns js/sky/sky-nebula.js
 * @budget budget.drawcalls=2 budget.points=2000 budget.rtpx=262144 budget.passes=0 budget.vertices=4000
 * @contract deep-sky/3
 * 体积：步进数 CLSkyTokens.VOL.slices[档]（画布像素多时按 √(2.1M / 像素) 降，最少六成），厚度按该团成员离盘面的
 * z 离散度来；low 档 / 减弱动效退回单张平面（slices = 0）。着色器在 sky-nebula-glsl.js。
 * CLSkyNebula.create({scene:S}) → {build,update,setState,hover,setTier,stats,dispose}；无自有 rAF/setInterval。
 * 两条降级路径：CLSkyTokens.reduced()（冻结时间+直落终态） / setTier('low')（fbm=0 静态）。 */
(function (g) {
'use strict';
var T = g.CLSkyTokens, MAX = 2000, EDGE = 1.3, PLANE = 2.6;

var GL = g.CLSkyNebulaGLSL;

g.CLSkyNebula = { create: function (opts) {
opts = opts || {};
var S = opts.scene, tier = 'high', state = 'hidden';
var alpha = 0, target = 0, hoverIdx = -1, needSplat = true, splats = 0, starsN = 0, groupsN = 0;
var R = 1, pitch = 0, anchor = null, mesh = null, splatPoints = null;
var splatScene = null, splatCam = null, splatRT = null;
var planeGeo = null, volN = -1, splatGeo = null, matNeb = null, matSplat = null, posAttr = null, list = null, noiseTex = null;
var uGroupK = [], uGroupT = [], uRT = null, uTimeU = null, uAlphaU = null, tSplatU = null, uCamU = null, uNSU = null, v2 = null;
var uTime = 0, lastAnim = null, rtSize = 0, i, k, col, gd, w, nd, src;
var zSum = [], zSq = [], zN = [], gThick = [];
var tmpV = new THREE.Vector3(), tmpC = new THREE.Color();

/* Dense books contain many overlapping splats. Keep their faction colours
   saturated by reducing only the accumulated gas opacity as population grows;
   the stars, labels and relationship lines retain their normal intensity. */
function densityAlpha() {
var n = starsN || 0;
return n > 320 ? 0.72 : n > 180 ? 0.76 : n > 90 ? 0.84 : n > 42 ? 0.90 : 1;
}

function td() { return T.TIER[tier] || T.TIER.high; }
function mkBlend(o) {
var r = {transparent:true, depthTest:false, depthWrite:false, blending:THREE.AdditiveBlending, premultipliedAlpha: true}, key;
for (key in o) { if (o.hasOwnProperty(key)) { r[key] = o[key]; } } return r;
}

function makeRT(size) {
var gl2 = !!(S.renderer && S.renderer.capabilities && S.renderer.capabilities.isWebGL2);
var rt = new THREE.WebGLRenderTarget(size, size, {minFilter:THREE.LinearFilter, magFilter:THREE.LinearFilter,
format:THREE.RGBAFormat, type: gl2 ? THREE.HalfFloatType : THREE.UnsignedByteType,
depthBuffer:false, stencilBuffer:false});
rt.texture.generateMipmaps = false;
rt.texture.wrapS = THREE.ClampToEdgeWrapping;
rt.texture.wrapT = THREE.ClampToEdgeWrapping;
return rt;
}

function ensureScene() {
if (!splatScene) {
splatScene = new THREE.Scene();
splatCam = new THREE.OrthographicCamera(-EDGE, EDGE, EDGE, -EDGE, -10, 10);
uRT = {value:rtSize || 128};
}
if (!matSplat) {
uRT = uRT || {value:128};
matSplat = new THREE.ShaderMaterial(mkBlend({uniforms:{uRT:uRT, uGroupK:{value:uGroupK}, uGroupT:{value:uGroupT}},
vertexShader:GL.SPLAT_VS, fragmentShader:GL.SPLAT_FS}));
}
}

/* 本档步进数：low / 减弱动效 = 0 → 单张平面 */
function slices() {
var v = T.VOL && T.VOL.slices ? T.VOL.slices[tier] : null;
if (T.reduced()) { return 0; }
return (typeof v === 'number' && v > 1) ? v | 0 : 0;
}

/* 几何永远是单张面片（体积由片元步进）；volN = 这次编译的步进上限 */
function ensureGeo() {
var n = slices();
if (!planeGeo) { planeGeo = GL.volGeo(1, PLANE); }
volN = n;
if (mesh) { mesh.geometry = planeGeo; }
}

function ensureNebMat() {
var oct = td().fbm | 0;
src = GL.volFrag(oct, T.VOL ? T.VOL.jitter : 0.12, slices());
if (!noiseTex) noiseTex = g.CLSkyCloudNoise.create(THREE);
if (!matNeb) {
uTimeU = {value:0}; uAlphaU = {value:0}; tSplatU = {value:null}; uCamU = {value:new THREE.Vector3()}; uNSU = {value:24};
matNeb = new THREE.ShaderMaterial(mkBlend({uniforms:{tSplat:tSplatU, tNoise:{value:noiseTex}, uTime:uTimeU, uAlpha:uAlphaU, uCam:uCamU, uNS:uNSU},
vertexShader:GL.VOL_VS, fragmentShader:src}));
} else if (matNeb.fragmentShader !== src) {
matNeb.fragmentShader = src; matNeb.needsUpdate = true; /* #define OCT / STEPS 变化 → 重编译 */
}
if (splatRT) { tSplatU.value = splatRT.texture; }
}

function ensureRT() {
var want = td().nebulaRT | 0;
if (splatRT && rtSize === want) { return; }
if (splatRT) { splatRT.dispose(); }
splatRT = makeRT(want); rtSize = want;
if (uRT) { uRT.value = rtSize; } else { uRT = {value:rtSize}; }
if (tSplatU) { tSplatU.value = splatRT.texture; }
needSplat = true;
}

function applyHover() {
for (i = 0; i < 32; i++) {
uGroupK[i] = hoverIdx >= 0 ? (i === hoverIdx ? 1.9 : 0.6) : 1.0;
if (typeof uGroupT[i] !== 'number') { uGroupT[i] = 0; }   /* 厚度由 syncPos 量出来；量到之前先按 0（该团不出体积层） */
}
if (matSplat) { matSplat.uniforms.uGroupK.value = uGroupK; matSplat.uniforms.uGroupT.value = uGroupT; }
needSplat = true;
}

/* 溅射位置只要盘面二维（正交相机不看 z）；顺手把每颗星离盘面的 z 收进该团的统计，
   团厚度 = z 的标准差（成员散得越开、这团气体就越厚）—— 只读数据，不虚构。 */
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
/* 按 σ 正比归一（最散的团满厚），下限 0.35：最紧的团仍留一层薄壳（不然独星团整个消失） */
for (i = 0; i < 32; i++) { uGroupT[i] = mx > 1e-6 ? Math.max(0.35, gThick[i] / mx) : (zN[i] ? 0.35 : 0); }
if (matSplat) { matSplat.uniforms.uGroupT.value = uGroupT; }
}

function renderSplat() {
var r = S.renderer, pRT, pA, pa;
if (!r || !splatRT || !splatScene) { return; }
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

function build(cfg) {
cfg = cfg || {};
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
}
anchor.add(mesh);   /* 换书 / 换分组会重建锚点：星云面必须挂到新锚点上，否则随旧锚点一起被摘掉 */
mesh.geometry = planeGeo;
mesh.material = matNeb;
mesh.visible = alpha > 0.002;

var groups = cfg.groups || [], stars = cfg.stars || [];
var n = stars.length > MAX ? MAX : stars.length;
var pos = new Float32Array(n * 3), aCol = new Float32Array(n * 3);
var aRad = new Float32Array(n), aGroup = new Float32Array(n), used = [], seen = {};

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
aRad[k] = (cfg.rad > 0 ? cfg.rad : 0.16) * (0.9 + 0.6 * w);   /* 半径随星距（s0/R）走：相邻成员的气团连成一片势力范围 */
aGroup[k] = gd;
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
splatGeo.setAttribute('aGroup', new THREE.Float32BufferAttribute(aGroup, 1));
splatGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2);
splatPoints = new THREE.Points(splatGeo, matSplat);
splatPoints.frustumCulled = false;
splatPoints.matrixAutoUpdate = false;
splatPoints.updateMatrix();
splatScene.add(splatPoints);
anchor.updateMatrixWorld(true);
syncPos();
}

applyHover();
needSplat = true;
}

function update(dt, tAnim, live) {
var reducedMotion = T.reduced();
var t = (typeof dt === 'number' && dt > 0) ? dt : 0;
var flying = !!live;
if (matNeb && slices() !== volN) { ensureGeo(); ensureNebMat(); }   /* 减弱动效可随时开关 */

target = (state === 'show' ? T.ALPHA.nebula : state === 'dim' ? T.ALPHA.nebulaDim : 0) * densityAlpha();
if (reducedMotion) {
alpha = target;
} else {
alpha += (target - alpha) * (1 - Math.exp(-t / Math.max(T.DUR.focus, 1e-3)));
if (Math.abs(target - alpha) < 1e-4) { alpha = target; }
}
if (uAlphaU) { uAlphaU.value = alpha; }
if (mesh) { mesh.visible = alpha > 0.002; }

/* Integrate only active animation time. Resuming after a low-tier / reduced
   pause must continue this gas shape, not jump to the host's later phase.
   The host delta preserves calm mode; the dt bound drops hidden-tab gaps. */
var anim = typeof tAnim === 'number' && isFinite(tAnim) ? tAnim : null;
if (tier !== 'low' && !reducedMotion && lastAnim !== null && anim !== null) {
uTime += Math.min(t, 0.05, Math.max(0, anim - lastAnim));
}
lastAnim = anim;
if (uTimeU) { uTimeU.value = uTime; }
/* 相机在盘面本地空间（片元据此求视线）；步进数按画布像素量降（uniform，不重编译） */
if (uCamU && anchor && volN > 1 && mesh && mesh.visible) {
anchor.updateMatrixWorld(true);
uCamU.value.copy(S.camera.position); anchor.worldToLocal(uCamU.value);
v2 = v2 || new THREE.Vector2(); S.renderer.getDrawingBufferSize(v2);
uNSU.value = Math.round(volN * Math.max(0.6, Math.min(1, Math.sqrt(2.1e6 / Math.max(1, v2.x * v2.y)))));
}

if (!splatRT || !splatPoints) { needSplat = false; return; }
if (flying) { anchor.updateMatrixWorld(true); syncPos(); }
if (needSplat || (flying && tier !== 'low')) { renderSplat(); splats++; }
needSplat = false;
}

function setState(s, now) {   /* now：跳过揭幕时一帧到位 */
state = (s === 'show' || s === 'dim') ? s : 'hidden';
if (now || T.reduced()) {
alpha = (state === 'show' ? T.ALPHA.nebula : state === 'dim' ? T.ALPHA.nebulaDim : 0) * densityAlpha();
if (uAlphaU) { uAlphaU.value = alpha; }
if (mesh) { mesh.visible = alpha > 0.002; }
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
ensureRT(); ensureGeo(); ensureNebMat();
if (mesh) { mesh.material = matNeb; mesh.geometry = planeGeo; }
needSplat = true;
}

function stats() {
return {groups:groupsN, stars:starsN, rt:rtSize, state:state, alpha:alpha, splats:splats,
slices:volN < 0 ? 0 : volN, steps:volN > 1 && uNSU ? uNSU.value : 0, detailTexture:noiseTex ? 256 : 0, thick:uGroupT.slice(0, Math.max(1, groupsN))};
}

function dispose() {
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
posAttr = null; list = null; splats = 0; starsN = 0; groupsN = 0;
}

return {build:build, update:update, setState:setState, hover:hover,
setTier:setTier, stats:stats, dispose:dispose};
} };
})(window);
