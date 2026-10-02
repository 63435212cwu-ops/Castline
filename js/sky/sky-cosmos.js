/*! sky-cosmos.js
* @role webgl | @owns js/sky/sky-cosmos.js
* @budget drawcalls=4 points=29940 vertices=4 rtpx=1572864 passes=0
* @contract deep-sky/2
* degrade: reduced()=freeze/snap; tier=low=static shell, no twinkle/dust */
(function (g) {
'use strict';
var T = g.CLSkyTokens || { C: {}, COSMOS: {} };
var C = T.C || {}, O = T.COSMOS || {}, D = Math.PI / 180, P = Math.PI * 2;
var HI = 768, LO = 256, SC = 25000, DR = 2400;
function cs(d){return Math.cos(d*D);}
function sn(d){return Math.sin(d*D);}
var GL = g.CLSkyCosmosGLSL, VC = GL.VC, FC = GL.FC, VS = GL.VS, FS = GL.FS, VG = GL.VG, FG = GL.FG, VD = GL.VD, FD = GL.FD;   /* 着色器文本在 sky-cosmos-glsl.js */

function rc() { return T.reduced(); }
function v3(a){return new THREE.Vector3(a[0],a[1],a[2]);}
function lcg(s0) { var s = (s0 | 0) || 1; return function () { s = (s * 1664525 + 1013904223) | 0; return ((s >>> 8) & 0xffffff) / 0x1000000; }; }
var rgb=g.CLSkyUtil.rgb;
function col3(h,n){var c=rgb(h),a=new Float32Array(n*3),i,j;for(i=0;i<n;i++)for(j=0;j<3;j++)a[i*3+j]=c[j];return a;}
function put(geo, nm, a, sz) { geo.setAttribute(nm, new THREE.Float32BufferAttribute(new Float32Array(a || []), sz)); }
function fp(a) { return { cx: .5, cy: .5, rx: .35, ry: .35, alpha: a }; }
/* 高档深空贴图按真实视口取样：普通 1440 级仍用 512，Retina / 原生 4K
   才升到 768，避免开书时无意义地为小屏烘焙大立方体。 */
function hiCubeSize() {
var dpr = g.devicePixelRatio || 1, area = (g.innerWidth || 0) * (g.innerHeight || 0);
return dpr >= 1.5 || area >= 3000000 ? HI : 512;
}

function create(opts) {
var S = (opts || {}).scene;
if (!S) throw new Error('CLSkyCosmos');
var R = S.renderer, sc = S.scene, cam = S.camera;
var U = { tCube: { value: null }, uInvProj: { value: new THREE.Matrix4() }, uCamRot: { value: new THREE.Matrix3() },
uDrift: { value: new THREE.Matrix3() }, uDriftT: { value: new THREE.Matrix3() }, uRes: { value: new THREE.Vector2(1, 1) },
uFocusC: { value: new THREE.Vector2(.5, .5) }, uFocusR: { value: new THREE.Vector2(.35, .35) },
uFocusK: { value: .45 }, uAlpha: { value: 1 }, uFar: { value: 1000 }, uDpr: { value: 1 }, uPxRad: { value: 500 },
uMagMin: { value: 0 }, uTime: { value: 0 }, uTw: { value: 1 }, uDef: { value: 0 } };
var defTo = 0;
function add(o, geo, vs, fs, ro, op) {
o.geometry = geo;
o.material = new THREE.ShaderMaterial({ uniforms: U, vertexShader: vs, fragmentShader: fs, transparent: !!op, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending, premultipliedAlpha: true });
o.frustumCulled = false; o.renderOrder = ro; sc.add(o); return o;
}
var tg = fp(1), cu = fp(0);
var m4 = new THREE.Matrix4(), m3a = new THREE.Matrix3(), v2 = new THREE.Vector2();
var pole = new THREE.Vector3(0, 1, 0), t3 = new THREE.Vector3(), bd = new THREE.Vector3();
var th = 0, clk = 0, rad = 1, tier = 'high', state = 'show', built = false, bk = null;
/* 天球朝向：构图按构建时的视线系摆，开书飞行落定后 reorient 把整片天转到落定的视线系（不可见时直接落位，可见时缓转） */
var qB = new THREE.Quaternion(), qG = new THREE.Quaternion(), mB = new THREE.Matrix4(), fr0 = new THREE.Matrix4();
function frameOf(f) {
var a = v3(f).normalize(), rr = new THREE.Vector3().crossVectors(a, v3([0, 1, 0]));
if (!rr.lengthSq()) rr.crossVectors(a, v3([0, 0, 1]));
rr.normalize();
return new THREE.Matrix4().makeBasis(rr, new THREE.Vector3().crossVectors(rr, a).normalize(), a);
}
function reorient(f) {
if (!built || !f) return false;
qG.setFromRotationMatrix(frameOf(f).multiply(fr0.clone().transpose()));
if (cu.alpha < .02 || rc()) qB.copy(qG);
return true;
}
var objs = [], cubeSize = 0, nStar = 0, dustAll = 0, nGlow = 0, nClus = 0, nGal = 0;

function kill() {
var i, m;
for (i = 0; i < objs.length; i++) { m = objs[i]; if (m.parent) m.parent.remove(m); if (m.geometry) m.geometry.dispose(); if (m.material) m.material.dispose(); }
objs = [];
if (bk && bk.dispose) bk.dispose();
bk = null; U.tCube.value = null; built = false; nStar = dustAll = cubeSize = 0;
}

function build(o) {
kill(); o = o || {};
rad = o.R || 1;
var ctr = v3(o.center || [0, 0, 0]);
var av = v3(o.avoid || [0, 0, 1]).normalize();
fr0 = frameOf(av.toArray()); qB.identity(); qG.identity(); cu.alpha = 0;
var seed = o.seed == null ? 1 : o.seed, rq = lcg(seed), i, b, sz, br, cl, kk, aa, d, q;
var r = new THREE.Vector3().crossVectors(av, v3([0, 1, 0]));
if (!r.lengthSq()) r.crossVectors(av, v3([0, 0, 1]));
r.normalize();
var u = new THREE.Vector3().crossVectors(r, av).normalize();
/* 开书视角的构图（视线系：离轴角 θ、自右起逆时针的方位 φ；左右随书镜像）：图谱外缘与屏幕边之间，
   左上一团玫瑰星云、右下一团青星云（里面一团疏散星团）、左下一团球状星团、右上一个远星系；另两团星云在身后，转过去才看见 */
var sd = seed & 1 ? 1 : -1;
function peri(t, f) { if (sd < 0) f = 180 - f; t *= D; f *= D; return av.clone().multiplyScalar(Math.cos(t)).addScaledVector(r, Math.sin(t) * Math.cos(f)).addScaledVector(u, Math.sin(t) * Math.sin(f)).normalize(); }
/* 银河斜挂左上角：离视线最近处在 (27°, 145°)，银心在带上再往外 46°（暖色核球只露出一角） */
var bp = peri(27, 145), bw = bp.clone().addScaledVector(av, -bp.dot(av)).normalize();
pole.copy(bw).multiplyScalar(cs(27)).addScaledVector(av, -sn(27)).normalize();
t3.crossVectors(pole, bp).normalize();
var core = bp.clone().multiplyScalar(cs(46)).addScaledVector(t3, sn(46) * (sd > 0 ? 1 : -1)).normalize();
var CL = [O.cloudRose, O.cloudTeal, O.cloudViolet, O.cloudAmber], CP = [[37, 150], [39, -32], [118, 40], [150, 220]], clouds = [];
for (i = 0; i < 4; i++) clouds.push({ dir: peri(CP[i][0] + rq() * 4, CP[i][1] + rq() * 14 - 7).toArray(), radius: .14 + rq() * .1, hex: CL[i] || C.VIOLET });

cubeSize = tier === 'high' ? hiCubeSize() : LO;
/* 烘焙与生成器只收数组形式的方向 */
bk = g.CLSkyCosmosBake.bake(R, { size: cubeSize, seed: seed, pole: pole.toArray(), core: core.toArray(), clouds: clouds, gain: 1 });
U.tCube.value = bk && (bk.texture || bk.cube || (bk.target && bk.target.texture));
if (!U.tCube.value) throw new Error('CLSkyCosmos:bake');
objs[0] = add(new THREE.Mesh(), new THREE.PlaneGeometry(2, 2), VC, FC, -300, 0);

var gen = g.CLSkyCosmosStars.generate({ seed: seed, pole: pole.toArray(), avoid: av.toArray(), avoidDeg: 26, count: SC, dust: 2000 }) || {};
var s = gen.stars || {}, co = s.col, ps = s.dir, ns = ps ? (ps.length / 3) | 0 : 0;
var gc = (gen.clusters || []).filter(function (c) { return c.kind === 'globular'; }), oc = (gen.clusters || []).filter(function (c) { return c.kind === 'open'; }), rg = gen.ranges || {};
function moveTo(c, span, to) {
if (!c || !span || !ps) return;
var qn = new THREE.Quaternion().setFromUnitVectors(v3(c.dir), to), w = new THREE.Vector3(), j;
for (j = span[0]; j < span[0] + span[1]; j++) { w.fromArray(ps, j * 3).applyQuaternion(qn); ps[j * 3] = w.x; ps[j * 3 + 1] = w.y; ps[j * 3 + 2] = w.z; }
c.dir = to.toArray();
}
moveTo(oc[0], rg.open && rg.open[0], peri(30 + rq() * 3, -28 + rq() * 12 - 6));
moveTo(gc[0], rg.globular && rg.globular[0], peri(31 + rq() * 3, 205 + rq() * 12 - 6));
if (gen.galaxies && gen.galaxies[0]) gen.galaxies[0].dir = peri(28 + rq() * 3, 14 + rq() * 8 - 4).toArray();
var gs = new THREE.BufferGeometry();
put(gs, 'position', ps, 3); put(gs, 'aMag', s.aMag || s.mag, 1);
put(gs, 'aCol', typeof co === 'number' ? col3(co, ns) : co, 3); put(gs, 'aTw', s.aTw || s.tw, 1);
nStar = gs.getAttribute('position').count; nClus = (gen.clusters || []).length; nGal = (gen.galaxies || []).length;
objs[1] = add(new THREE.Points(), gs, VS, FS, -290);

/* 光晕：远星系（小而淡、核心一点亮）+ 球状星团没分辨开的核；星云的颜色在烘焙的天球里，不另画圆斑 */
var gal = gen.galaxies || [], glo = (gen.clusters || []).filter(function (c) { return c.kind === 'globular'; }), GL = [], k;
gal.forEach(function (x) { GL.push({ d: x.dir, sz: x.size * 1.15, ax: x.axis, tl: x.tilt, br: x.bright, col: x.col, kd: 0 }); });
glo.forEach(function (x) { GL.push({ d: x.dir, sz: x.radius * .75, ax: 0, tl: 1, br: .32, col: rgb(O.starYellow || C.STAR_WHITE), kd: 1 }); });
var GN = GL.length, KS = 'position aSize aAxis aTilt aBright aCol aKind'.split(' '), A = {};
for (k = 0; k < KS.length; k++) A[KS[k]] = new Float32Array(KS[k] === 'position' || KS[k] === 'aCol' ? GN * 3 : GN);
for (i = 0; i < GN; i++) {
q = GL[i];
for (k = 0; k < 3; k++) { A.position[i * 3 + k] = q.d[k]; A.aCol[i * 3 + k] = q.col[k]; }
A.aSize[i] = q.sz; A.aAxis[i] = q.ax; A.aTilt[i] = q.tl; A.aBright[i] = q.br; A.aKind[i] = q.kd;
}
nGlow = GN;
var gg = new THREE.BufferGeometry();
for (k in A) put(gg, k, A[k], k === 'position' || k === 'aCol' ? 3 : 1);
objs[2] = add(new THREE.Points(), gg, VG, FG, -285);

var dg = gen.dust || {}, dpos = dg.pos, dm = dg.mag;
if (dpos) {
var nd = (dpos.length / 3) | 0, pd = new Float32Array(nd * 3), mg = dm ? new Float32Array(dm) : new Float32Array(nd);
for (i = 0; i < nd * 3; i++) pd[i] = ctr.getComponent(i % 3) + dpos[i] * rad;
if (!dm) for (i = 0; i < nd; i++) mg[i] = .5;
var dgeo = new THREE.BufferGeometry();
put(dgeo, 'position', pd, 3); put(dgeo, 'aMag', mg, 1); put(dgeo, 'aCol', col3(O.mote || C.INK3, nd), 3);
objs[3] = add(new THREE.Points(), dgeo, VD, FD, -280);
dustAll = nd;
}
th = 0; clk = 0; applyTier(); built = true; update(0, 0);
return self;
}

function applyTier() {
U.uMagMin.value = tier === 'high' ? 0 : tier === 'mid' ? .012 : .05;
U.uTw.value = rc() || tier === 'low' ? 0 : 1;
var dp = objs[3];
if (!dp) return;
dp.visible = tier !== 'low';
if (dp.visible) dp.geometry.setDrawRange(0, tier === 'mid' ? (dustAll / 2) | 0 : dustAll);
}

function setTier(t) { tier = t === 'low' || t === 'mid' ? t : 'high'; applyTier(); }

function setFocus(f) {
R.getSize(v2);
if (!f) { tg = fp(tg.alpha); }
else {
tg.cx = (f.cx || 0) / v2.x; tg.cy = 1 - (f.cy || 0) / v2.y;
tg.rx = Math.max(.02, (f.rx || .2) / v2.x); tg.ry = Math.max(.02, (f.ry || .2) / v2.y);
}
if (rc()) { cu.cx = tg.cx; cu.cy = tg.cy; cu.rx = tg.rx; cu.ry = tg.ry; }
}

function setDefocus(v) { defTo = Math.max(0, Math.min(1, +v || 0)); if (rc()) U.uDef.value = defTo; }

function setState(s, now) {   /* now：跳过揭幕时一帧到位 */
state = s === 'dim' || s === 'hidden' ? s : 'show';
tg.alpha = state === 'show' ? 1 : state === 'dim' ? .6 : 0;
if (now || rc()) cu.alpha = tg.alpha;
}

function update(dt, tAnim) {
if (!built) return;
var d = dt > 0 && isFinite(dt) ? dt : 0, reducedMotion = rc(), kf, ka;
cam.updateMatrixWorld();
R.getDrawingBufferSize(v2);
U.uRes.value.copy(v2);
U.uDpr.value = Math.max(1, Math.min(2.4, v2.y / 1080));   /* 星点大小跟角分辨率走（绘制缓冲高度），4K 下不缩成单像素 */
U.uPxRad.value = v2.y / (2 * Math.tan(cam.fov * D * .5));
U.uInvProj.value.copy(cam.projectionMatrixInverse);
U.uCamRot.value.setFromMatrix4(cam.matrixWorld);
U.uFar.value = cam.far * .8;
if (!reducedMotion && tier !== 'low') { th += d * (P / DR); clk += d; }
if (!qB.equals(qG)) qB.slerp(qG, reducedMotion ? 1 : 1 - Math.exp(-d * 2.5));
m4.makeRotationAxis(pole, -th).premultiply(mB.makeRotationFromQuaternion(qB)); m3a.setFromMatrix4(m4);
U.uDriftT.value.copy(m3a); U.uDrift.value.copy(m3a).transpose(); U.uTime.value = clk;
kf = reducedMotion ? 1 : 1 - Math.exp(-d * 6); ka = reducedMotion ? 1 : 1 - Math.exp(-d * 2.2);
cu.cx += (tg.cx - cu.cx) * kf; cu.cy += (tg.cy - cu.cy) * kf;
cu.rx += (tg.rx - cu.rx) * kf; cu.ry += (tg.ry - cu.ry) * kf; cu.alpha += (tg.alpha - cu.alpha) * ka;
U.uFocusC.value.set(cu.cx, cu.cy); U.uFocusR.value.set(cu.rx, cu.ry); U.uAlpha.value = cu.alpha;
U.uDef.value += (defTo - U.uDef.value) * (reducedMotion ? 1 : 1 - Math.exp(-d * 3.2));
}

function stats() {
var dp = objs[3], h = dp && dp.visible ? (tier === 'mid' ? (dustAll / 2) | 0 : dustAll) : 0;
return { built: built ? 1 : 0, stars: nStar, clusters: nClus, galaxies: nGal, glows: nGlow, dust: h, cube: cubeSize, state: state, tier: tier, alpha: +U.uAlpha.value.toFixed(3), defocus: +U.uDef.value.toFixed(3) };
}

var self = { build: build, update: update, reorient: reorient, setFocus: setFocus, setState: setState, setDefocus: setDefocus, setTier: setTier, stats: stats, dispose: kill };
return self;
}

g.CLSkyCosmos = { create: create };
})(window);
