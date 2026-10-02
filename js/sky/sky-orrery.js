/*! @role orrery · @owns js/sky/sky-orrery.js · @contract deep-sky/1
 *  @budget drawcalls=6 points=12 vertices=966 rtpx=0 passes=0 kb<=12
 *  3 轨丝带(161 采样 x2 顶点=322,共 966 顶点)+ 3 组游星(每轨 2 星 x 芯/辉光=12
 *  点);low 档 3 drawcalls / 0 点 / 不转动。1.1px 轨宽、10px 游星芯、96 刻度、半径
 *  倾角与公转/自转数值均出自本单元规格;颜色取 CLSkyTokens,时长取 DUR.focus/
 *  soft,缓动取 EASE.out/inOut。降级:reduced() → 1 帧终态 + 时间冻结;
 *  hardwareConcurrency<=4 → 初始 low(宿主 setTier 优先)。
 */
(function (g) {
'use strict';
var THREE = g.THREE, N_RING = 3, SEG = 160, PX_LINE = 1.1, PX_STAR = 10,
  PX_GLOW = 26, ENTRY_K = 0.82,
  RING_K = [1.28, 1.58, 1.92], TILT_X = [1.18, 1.34, 1.05],
  TILT_Z = [0.2, -0.35, 0.62], ORBIT_W = [0.05, -0.034, 0.027],
  SELF_W = [0.018, -0.012, 0.009], PHASE = [0, Math.PI],
  S_CLOSED = 0, S_IN = 1, S_OPEN = 2, S_OUT = 3;
var EASE_OUT = function (t) { var u = 1 - t; return 1 - u * u * u * u; };
var EASE_IO = function (t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(2 - 2 * t, 3) * 0.5;
};
var GL=g.CLSkyOrreryGLSL,LINE_VS=GL.LINE_VS,LINE_FS=GL.LINE_FS,STAR_VS=GL.STAR_VS,STAR_FS=GL.STAR_FS;
function ringGeometry() {
  var n = SEG + 1, vc = n * 2, i, j, s, k, v, b, ip, iq, a,
    px = new Float32Array(n * 3), pos = new Float32Array(vc * 3),
    prv = new Float32Array(vc * 3), nxt = new Float32Array(vc * 3),
    side = new Float32Array(vc), tt = new Float32Array(vc),
    idx = new Uint16Array(SEG * 6);
  for (i = 0; i < n; i++) {
    a = (i / SEG) * 6.283185307179586;
    px[i * 3] = Math.cos(a); px[i * 3 + 1] = Math.sin(a); tt[i] = i / SEG;
  }
  for (j = 0; j < n; j++) {
    ip = j > 0 ? j - 1 : 0; iq = j < n - 1 ? j + 1 : n - 1;
    for (s = 0; s < 2; s++) {
      v = j * 2 + s;
      pos[v * 3] = px[j * 3]; pos[v * 3 + 1] = px[j * 3 + 1];
      prv[v * 3] = px[ip * 3]; prv[v * 3 + 1] = px[ip * 3 + 1];
      nxt[v * 3] = px[iq * 3]; nxt[v * 3 + 1] = px[iq * 3 + 1];
      side[v] = s ? 1 : -1; tt[v] = j / SEG;
    }
  }
  for (k = 0; k < SEG; k++) {
    b = k * 2;
    idx[k * 6] = b; idx[k * 6 + 1] = b + 1; idx[k * 6 + 2] = b + 2;
    idx[k * 6 + 3] = b + 1; idx[k * 6 + 4] = b + 3; idx[k * 6 + 5] = b + 2;
  }
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('aPrev', new THREE.Float32BufferAttribute(prv, 3));
  geo.setAttribute('aNext', new THREE.Float32BufferAttribute(nxt, 3));
  geo.setAttribute('aSide', new THREE.Float32BufferAttribute(side, 1));
  geo.setAttribute('aT', new THREE.Float32BufferAttribute(tt, 1));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  return geo;
}
function starGeometry() {
  var pos = new THREE.BufferAttribute(new Float32Array(12), 3);
  var kk = new Float32Array(4), sz = new Float32Array(4), i;
  for (i = 0; i < 4; i += 2) {
    kk[i] = 0; kk[i + 1] = 1; sz[i] = PX_STAR; sz[i + 1] = PX_GLOW;
  }
  pos.setUsage(THREE.DynamicDrawUsage);
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', pos);
  geo.setAttribute('aK', new THREE.Float32BufferAttribute(kk, 1));
  geo.setAttribute('aSize', new THREE.Float32BufferAttribute(sz, 1));
  return geo;
}
function additive(vs, fs, uni) {
  return new THREE.ShaderMaterial({
    uniforms: uni, vertexShader: vs, fragmentShader: fs,
    transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending, premultipliedAlpha: true
  });
}
function create(opts) {
  var S = (opts && opts.scene) || (opts && typeof opts.add === 'function' ? opts : null);
  var T = g.CLSkyTokens || null;
  var DUR = (T && T.DUR) ? T.DUR : { focus: 0.9, soft: 0.36 };
  var C = (T && T.C) ? T.C : null;
  var reducedMotion = !!(T && T.reduced && T.reduced());
  var weak = !!(g.navigator && g.navigator.hardwareConcurrency &&
    g.navigator.hardwareConcurrency <= 4);
  var tier = weak ? 'low' : 'high';
  var dead = !THREE || !S, disposed = false, built = false;
  var root = null, rings = [], uniL = null, uniS = null, v2 = null;
  var state = S_CLOSED, openT = 0, closeT = 0, alpha = 0, scale = 1, clock = 0;
  var occlude = { value: new THREE.Vector4(0,0,0,0) }, occKeep = { value: T.ORRERY_UI.occludeKeep };
  function ensure() {
    if (built || dead || disposed) return;
    v2 = new THREE.Vector2();
    uniL = {
      uRes: { value: new THREE.Vector2(1, 1) },
      uDpr: { value: 1 },
      uHalfPx: { value: PX_LINE * 0.5 },
      uAlpha: { value: 0 }, uOcclude: occlude, uOccKeep: occKeep,
      uColor: { value: new THREE.Color(C ? C.BRASS : 0xeac07a) },
      uColB: { value: new THREE.Color(C ? C.BRASS : 0xeac07a) }
    };
    uniS = {
      uDpr: { value: 1 },
      uAlpha: { value: 0 }, uOcclude: occlude, uOccKeep: occKeep,
      uColA: { value: new THREE.Color(C ? C.STAR_WHITE : 0xfff6e8) },
      uColB: { value: new THREE.Color(C ? C.BRASS : 0xeac07a) }
    };
    root = new THREE.Group();
    S.scene.add(root);
    var i, rec, line;
    for (i = 0; i < N_RING; i++) {
      rec = { grp: new THREE.Group(), line: null, orb: new THREE.Group(),
        star: null, geoS: null, matS: null };
      rec.grp.rotation.order = 'ZYX';
      rec.grp.rotation.x = TILT_X[i];
      rec.grp.rotation.z = TILT_Z[i];
      rec.grp.scale.set(RING_K[i], RING_K[i], RING_K[i]);
      line = new THREE.Mesh(ringGeometry(), additive(LINE_VS, LINE_FS, uniL));
      line.frustumCulled = false; line.renderOrder = 4;
      rec.grp.add(line); rec.grp.add(rec.orb);
      rec.line = line;
      root.add(rec.grp);
      rings.push(rec);
    }
    built = true;
    if (tier !== 'low') ensureStars();
  }
  function ensureStars() {
    if (dead || disposed) return;
    for (var i = 0; i < rings.length; i++) {
      var r = rings[i];
      if (!r || r.star) continue;
      r.geoS = starGeometry();
      r.matS = additive(STAR_VS, STAR_FS, uniS);
      r.star = new THREE.Points(r.geoS, r.matS);
      r.star.frustumCulled = false; r.star.renderOrder = 4;
      r.orb.add(r.star);
    }
  }
  function sync() {
    var on = state !== S_CLOSED, st = on && tier !== 'low', i, r;
    if (root) root.visible = on;
    for (i = 0; i < rings.length; i++) {
      r = rings[i];
      if (r && r.star) r.star.visible = st;
    }
  }
  function hide() { state = S_CLOSED; alpha = 0; scale = 1; sync(); }
  function open(o) {
    if (disposed || dead) return;
    ensure();
    o = o || {};
    var c = o.center, rad = o.radius, col = o.color, i, s;
    if (c && root.position.copy) root.position.copy(c);
    s = (typeof rad === 'number' && rad > 0) ? rad : 1;
    var hex = (typeof col === 'number') ? col : (C ? C.BRASS : 0xeac07a);
    uniL.uColor.value.setHex(hex);
    uniL.uColB.value.setHex(C ? C.BRASS : 0xeac07a);
    uniS.uColA.value.setHex(C ? C.STAR_WHITE : 0xfff6e8);
    uniS.uColB.value.setHex(hex);
    if (tier !== 'low') ensureStars();
    for (i = 0; i < rings.length; i++) {
      rings[i].grp.scale.set(RING_K[i] * s, RING_K[i] * s, RING_K[i] * s);
    }
    reducedMotion = !!(T && T.reduced && T.reduced());
    openT = 0; closeT = 0; state = S_IN;
    if (reducedMotion) { alpha = 1; scale = 1; state = S_OPEN; }
    else { alpha = 0; scale = ENTRY_K; }
    sync();
  }
  function close() {
    if (disposed || state === S_CLOSED || state === S_OUT) return;
    if (reducedMotion || !built) { hide(); return; }
    state = S_OUT; closeT = 0;
  }
  function setTier(t) {
    tier = (t === 'low' || t === 'mid' || t === 'high') ? t : 'high';
    if (tier === 'low') clock = 0;
    else if (built) ensureStars();
    sync();
  }
  function update(dt, tAnim) {
    if (!built || disposed || state === S_CLOSED) return;
    var d = (typeof dt === 'number' && dt > 0) ? (dt > 0.25 ? 0.25 : dt) : 0;
    if (T && T.reduced) reducedMotion = !!T.reduced();
    if (!reducedMotion) {
      openT += d; closeT += d;
      if (tier !== 'low') clock += d;
    }
    var f, i, s, r, self, ang, arr, x, y;
    if (state === S_IN) {
      f = DUR.focus > 0 ? Math.min(1, openT / DUR.focus) : 1;
      if (reducedMotion) f = 1;
      scale = ENTRY_K + (1 - ENTRY_K) * EASE_OUT(f);
      alpha = EASE_OUT(f);
      if (f >= 1) state = S_OPEN;
    } else if (state === S_OUT) {
      f = DUR.soft > 0 ? Math.min(1, closeT / DUR.soft) : 1;
      if (reducedMotion) f = 1;
      alpha = 1 - EASE_IO(f);
      if (f >= 1) { hide(); return; }
    }
    var rr = S.renderer;
    if (!rr) return;
    var dpr = rr.getPixelRatio ? rr.getPixelRatio() : 1;
    rr.getDrawingBufferSize(v2);
    uniL.uRes.value.copy(v2);
    uniL.uDpr.value = dpr;
    uniL.uHalfPx.value = PX_LINE * 0.5 * dpr;
    uniL.uAlpha.value = alpha;
    uniS.uDpr.value = dpr;
    uniS.uAlpha.value = alpha;
    var spin = (tier !== 'low' && !reducedMotion);
    for (i = 0; i < rings.length; i++) {
      r = rings[i];
      if (!r) continue;
      self = spin ? SELF_W[i] * clock : 0;
      r.grp.rotation.z = TILT_Z[i] + self;
      r.orb.rotation.z = -self;
      if (!r.geoS) continue;
      arr = r.geoS.attributes.position.array;
      for (s = 0; s < 2; s++) {
        ang = (spin ? ORBIT_W[i] * clock : 0) + PHASE[s];
        x = Math.cos(ang); y = Math.sin(ang);
        arr[s * 6] = x; arr[s * 6 + 1] = y;
        arr[s * 6 + 3] = x; arr[s * 6 + 4] = y;
      }
      r.geoS.attributes.position.needsUpdate = true;
    }
  }
  function setOcclusion(b,w,h) {
    if (!b || !(w>0&&h>0)) { occlude.value.set(0,0,0,0); return; }
    occlude.value.set((b.left+b.right)/2/w,(b.top+b.bottom)/2/h,Math.max(1,b.right-b.left)*.52/w,Math.max(1,b.bottom-b.top)*.52/h);
  }
  function setCenter(c) { if (root && c) root.position.copy(c); }
  function stats() {
    var on = state !== S_CLOSED;
    return {
      open: on,
      rings: on ? N_RING : 0,
      alpha: Math.round(alpha * 1000) / 1000,
      tier: tier, occlusion: occlude.value.toArray(), occludeKeep: occKeep.value
    };
  }
  function dispose() {
    if (disposed) return;
    for (var i = 0; i < rings.length; i++) {
      var r = rings[i];
      if (!r) continue;
      if (r.line.geometry) r.line.geometry.dispose();
      if (r.line.material) r.line.material.dispose();
      if (r.geoS) r.geoS.dispose();
      if (r.matS) r.matS.dispose();
      if (r.grp && r.grp.parent) r.grp.parent.remove(r.grp);
      rings[i] = null;
    }
    rings = [];
    if (root && root.parent) root.parent.remove(root);
    root = null; built = false; uniL = null; uniS = null; v2 = null;
    state = S_CLOSED; alpha = 0; scale = 1; clock = 0;
    disposed = true;
  }
  return {
    open: open, close: close, update: update,
    setTier: setTier, setOcclusion: setOcclusion, setCenter: setCenter, stats: stats, dispose: dispose,
    rig: function () { return rings; }
  };
}
g.CLSkyOrrery = { create: create };
})(window);
