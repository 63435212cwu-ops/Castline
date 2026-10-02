/* @role webgl · @owns js/orbit3d-grade.js · @budget drawcalls=0 js_ms=0.15 · @contract v47+v48 */
(function (g) {
  'use strict';

  var NAME = 'orbit3d-grade';
  var VERSION = '52';
  var WIPE_S = 2.2;
  var TIDE_S = 26;
  var PI = Math.PI;
  var PI2 = Math.PI * 2;

  var THREE = null, pitch = 0;
  var disc = null, cam = null;
  var attached = false, switched = false;
  var swapped = 0, rebuilds = 0, updates = 0;
  var baseRx = 0, baseSy = 1;
  var lastT = 0, wipeT0 = -1, wasOn = false;
  var k = 0, wipe = 0, tideA = 0, tideK = 0, lift = 0;
  var reduced = false, low = false;
  var farCol = null;
  var matDish = null, matArc = null, matFork = null, matBand = null, matBead = null;

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function wrapPi(a) {
    while (a > PI) a -= PI2;
    while (a < -PI) a += PI2;
    return a;
  }
  function r4(v) { return Math.round(v * 10000) / 10000; }

  function cssHex(tok) {
    try {
      var s = g.getComputedStyle(g.document.documentElement).getPropertyValue(tok);
      if (!s) return null;
      s = s.replace(/^\s+|\s+$/g, '');
      var m = s.match(/^#([0-9a-fA-F]{6})$/);
      if (m) return parseInt(m[1], 16);
      m = s.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/);
      if (m) return (parseInt(m[1], 10) << 16) + (parseInt(m[2], 10) << 8) + parseInt(m[3], 10);
    } catch (e) {}
    return null;
  }

  function resolveFarCol(hotU) {
    if (!THREE) return null;
    var hx = cssHex('--violet-2');
    if (hx != null) return new THREE.Color(hx);
    try {
      if (g.CLPalette && g.CLPalette.mainColor) return new THREE.Color(g.CLPalette.mainColor(2));
    } catch (e2) {}
    if (hotU && hotU.value && hotU.value.clone) return hotU.value.clone();
    return new THREE.Color();
  }

  function addUni(mat, src) {
    if (!mat || !mat.uniforms || !src) return;
    for (var key in src) {
      if (!Object.prototype.hasOwnProperty.call(src, key)) continue;
      if (!mat.uniforms[key]) mat.uniforms[key] = { value: src[key] };
    }
  }
  function setU(mat, key, v) {
    if (mat && mat.uniforms && mat.uniforms[key]) mat.uniforms[key].value = v;
  }

  function frameS() {
    try { var L = g.CLOrbit3DLayer, f = L && typeof L.framing === 'function' ? L.framing() : null; var v = f && typeof f.s === 'number' && isFinite(f.s) ? f.s : 1; return v > 0.05 ? v : 1; } catch (e) { return 1; }
  }
  function attach(d) {
    disc = d;
    attached = false;
    switched = true;
    baseRx = d.rotation.x || 0;
    baseSy = (d.scale.y || 1) / frameS();
    matDish = matArc = matFork = matBand = matBead = null;

    var SH = g.CLOrbit3DShaders;
    if (!THREE || !SH) return false;

    var ch = d.children || [], spin = null, i, c;
    for (i = 0; i < ch.length; i++) {
      c = ch[i];
      if (c.renderOrder === -31 || c.renderOrder === -30) continue;
      if (c.children && c.children.length) { spin = c; break; }
    }
    var dish = null, arc = null, fork = null, band = null, bead = null;
    if (spin) {
      var sc = spin.children || [];
      for (i = 0; i < sc.length; i++) {
        c = sc[i];
        if (c.renderOrder === -29) dish = c;
        else if (c.renderOrder === -26) arc = c;
        else if (c.renderOrder === -25) fork = c;
        else if (c.renderOrder === -23) band = c;
        else if (c.renderOrder === -21) bead = c;
      }
    }
    if (!spin || !band || !bead) return false;

    swapped = 0;
    farCol = resolveFarCol(band.material && band.material.uniforms && band.material.uniforms.uHot);

    var strips = [dish, arc, fork, band];
    for (i = 0; i < strips.length; i++) {
      var mesh = strips[i];
      if (!mesh || !mesh.material || !mesh.material.uniforms) continue;
      var mat = mesh.material;
      mat.fragmentShader = SH.S_FS;
      addUni(mat, SH.UNI && SH.UNI.strip);
      if (!mat.uniforms.uFarCol) mat.uniforms.uFarCol = { value: farCol };
      mat.needsUpdate = true;
      if (mesh === dish) matDish = mat;
      else if (mesh === arc) matArc = mat;
      else if (mesh === fork) matFork = mat;
      else if (mesh === band) matBand = mat;
      swapped++;
    }
    if (bead.material && bead.material.uniforms) {
      var bm = bead.material;
      bm.vertexShader = SH.B_VS;
      bm.fragmentShader = SH.B_FS;
      addUni(bm, SH.UNI && SH.UNI.bead);
      if (!bm.uniforms.uFarCol) bm.uniforms.uFarCol = { value: farCol };
      bm.needsUpdate = true;
      matBead = bm;
      swapped++;
    }

    setU(matBand, 'uGain', 0.66); setU(matBand, 'uWhite', 0.24); setU(matBand, 'uK3', 0.55);
    setU(matArc, 'uGain', 1.25); setU(matArc, 'uWhite', 0.0);
    setU(matFork, 'uGain', 1.12);
    setU(matDish, 'uGain', 1.25);
    setU(matDish, 'uWipeOn', 0);
    /* 审核修正：选中态非命中线的地板从 0.40 提到 0.51（DESIGN §5.3：环形要读得出） */
    setU(matBand, 'uDim', 0.78); setU(matArc, 'uDim', 0.78); setU(matFork, 'uDim', 0.78);
    setU(matBead, 'uDimB', 0.74);

    if (arc) {   /* 审核修正：onBeforeRender 在 Mesh 上，不在 material 上 */
      var prev = arc.onBeforeRender;
      arc.onBeforeRender = function (r, s, cc) {
        if (prev) prev.apply(this, arguments);
        cam = cc;
      };
    }
    attached = true;
    return true;
  }

  function build(o) {
    if (!o) return;
    if (o.T) THREE = o.T;
    if (typeof o.pitch === 'number') pitch = o.pitch;
    switched = false;
  }

  function update(s) {
    var L = g.CLOrbit3DLayer, SH = g.CLOrbit3DShaders, V = g.CLPlotOrbitView;
    if (!L || !SH || !L.root) return;
    var d = L.root();
    if (d && d !== disc) {
      if (disc) rebuilds++;
      attach(d);
    }
    if (!disc || !attached) return;

    var t = (s && typeof s.t === 'number') ? s.t : 0;
    var dt = clamp(t - lastT, 0, 0.05);
    lastT = t;

    var st = (L.stats && L.stats()) || {};
    var fade = st.fade || 0;
    reduced = !!(st.reduced || (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches));
    low = st.tier === 2;

    if (fade > 0.01 && !wasOn) wipeT0 = t;
    wasOn = fade > 0.01;
    if (reduced) {
      wipe = 1.2;
    } else if (fade <= 0.01 || wipeT0 < 0) {
      wipe = 0;
    } else {
      var u = clamp((t - wipeT0) / WIPE_S, 0, 1);
      wipe = 1.12 * (1 - Math.pow(1 - u, 3));
    }

    var merid = PI / 2;
    if (V && V.desc) {
      var ds = V.desc();
      if (ds && ds.meridian && typeof ds.meridian.angle === 'number') merid = ds.meridian.angle;
    }
    tideK = (reduced || low) ? 0 : 1;
    tideA = wrapPi(merid - ((t % TIDE_S) / TIDE_S) * PI2);
    lift = (st.R || 0) * 0.012;

    var strips = [matDish, matArc, matFork, matBand], i, un;
    for (i = 0; i < strips.length; i++) {
      if (!strips[i] || !strips[i].uniforms) continue;
      un = strips[i].uniforms;
      if (un.uWipe) un.uWipe.value = wipe;
      if (un.uMerid) un.uMerid.value = merid;
      if (un.uTideA) un.uTideA.value = tideA;
      if (un.uTideK) un.uTideK.value = (strips[i] === matDish) ? tideK * 0.35 : tideK;
      if (un.uAero) un.uAero.value = 1;
      if (un.uLift) un.uLift.value = lift;
      if (un.uFarCol && farCol) un.uFarCol.value = farCol;
    }
    if (matBead && matBead.uniforms) {
      un = matBead.uniforms;
      if (un.uWipe) un.uWipe.value = wipe;
      if (un.uLift) un.uLift.value = lift;
      if (un.uAero) un.uAero.value = 1;
      if (un.uFarCol && farCol) un.uFarCol.value = farCol;
    }

    /* v90 F2：基准俯仰/ry 每帧从 CLOrbit3DLayer.baseTilt() 取（竖屏取景会改 T）；缺省时沿用 attach 时的快照 */
    try {
      var LB = g.CLOrbit3DLayer, bt = LB && typeof LB.baseTilt === 'function' ? LB.baseTilt() : null;
      if (bt && isFinite(bt.rx) && isFinite(bt.sy) && bt.sy > 0) { baseRx = bt.rx; baseSy = bt.sy; }
    } catch (eBT) {}
    var goal = 1;
    if (V && V.state) {
      var vs = V.state();
      if (vs && (vs.focusEv >= 0 || vs.thread)) goal = 0;
    }
    if (reduced) goal = 0;
    k += (goal - k) * Math.min(1, dt * 2.2);
    if (k < 1e-3 && goal === 0) {
      k = 0;
      disc.rotation.x = baseRx;
      disc.rotation.y = 0;
      /* R5-F 主控修正：呼吸是乘在取景 scale 上，不是绝对值——取景由 CLOrbit3DLayer.framing() 持有 */
      var fs0 = frameS(); disc.scale.set(fs0, baseSy * fs0, fs0);
    } else {
      disc.rotation.x = baseRx + k * 0.012 * Math.sin(PI2 * t / 37);
      disc.rotation.y = k * 0.007 * Math.sin(PI2 * t / 53 + 1.3);
      var b = k * 0.006 * Math.sin(PI2 * t / 6.4);
      var fs = frameS(); disc.scale.set(fs * (1 + b), baseSy * fs * (1 + b), fs);
    }

    updates++;
  }

  function gv(mat, key) {
    return (mat && mat.uniforms && mat.uniforms[key]) ? r4(mat.uniforms[key].value) : 0;
  }

  function stats() {
    return {
      name: NAME,
      version: VERSION,
      ready: !!(g.CLOrbit3DLayer && g.CLOrbit3DShaders),
      attached: attached,
      swapped: swapped,
      rebuilds: rebuilds,
      updates: updates,
      wipe: r4(wipe),
      tideA: r4(tideA),
      tideK: tideK,
      k: r4(k),
      baseRx: r4(baseRx),
      rx: disc ? r4(disc.rotation.x) : 0,
      lift: r4(lift),
      gain: { band: gv(matBand, 'uGain'), arc: gv(matArc, 'uGain'), fork: gv(matFork, 'uGain'), dish: gv(matDish, 'uGain') },
      reduced: reduced,
      low: low
    };
  }

  var API = {
    name: NAME,
    version: VERSION,
    build: build,
    update: update,
    attach: function () {
      var L = g.CLOrbit3DLayer;
      if (L && L.root) { var d = L.root(); if (d) attach(d); }
      return attached;
    },
    camera: function () { return cam; },
    stats: stats
  };

  function treePage() {
    var q = g.location && g.location.search;
    if (!q) return false;
    return q.indexOf('tree=1') >= 0 || q.indexOf('treestage=1') >= 0;
  }
  function hook() {
    if (treePage()) return;
    if (g.CLArcana && g.CLArcana.register) g.CLArcana.register(API);
  }

  if (treePage()) { /* tree stage owns its own pipeline */ }
  else if (g.CLArcana && g.CLArcana.register) g.CLArcana.register(API);
  else if (g.document && g.document.readyState === 'loading') g.document.addEventListener('DOMContentLoaded', hook);
  else hook();

  g.CLOrbit3DGrade = API;
})(typeof window !== 'undefined' ? window : this);
