(function () {
  'use strict';

  var DEG = Math.PI / 180;

  var BASE_AMP = 2.7 * DEG;
  var W1 = 0.19, W2 = 0.53, W3 = 1.17;
  var G1 = 0.62, G2 = 0.28, G3 = 0.10;
  var P1 = 0.00, P2 = 2.31, P3 = 4.72;
  var PX = 1.90;
  var XR = 0.42;

  var Y_TOP = 1.15;
  var POW = 1.6;
  var NT = 64;
  var PROF = new Float32Array(NT + 1);
  var i0;
  for (i0 = 0; i0 <= NT; i0++) PROF[i0] = Math.pow(i0 / NT, POW);
  var INV_YTOP = 1 / Y_TOP;

  var TAU = 1.2;

  var R02 = 0.12 * 0.12;
  var DNB = 17, DCENTER = 8;
  var DH1 = 7, DP1 = 1.7, DG1 = 0.62;
  var DH2 = 13, DP2 = 4.1, DG2 = 0.38;
  var dOn = false;
  var dSpread = 0;
  var DCS = new Float32Array(DNB), DSS = new Float32Array(DNB);
  var dTabMode = 'identity';

  var T = null, dummy = null, v3 = null;
  function ensureT() {
    if (!T && typeof window !== 'undefined' && window.THREE) T = window.THREE;
    if (T && !dummy) { dummy = new T.Object3D(); v3 = new T.Vector3(); }
    return !!(T && dummy);
  }

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  var t = 0;
  var on = 1;
  var muted = false;
  var reduce = false;
  var frozen = null;
  var ampK = 1;
  var rev = 0;
  var tabKey = '';
  var tabDirty = true;

  var SXT = new Float32Array(NT + 1), CXT = new Float32Array(NT + 1);
  var SZT = new Float32Array(NT + 1), CZT = new Float32Array(NT + 1);

  function effT() { return (frozen != null) ? frozen : t; }

  function buildDeltaTabs() {
    var i, a;
    if (!deltaLive()) {
      for (i = 0; i < DNB; i++) { DCS[i] = 1; DSS[i] = 0; }
      dTabMode = 'identity';
      return;
    }
    for (i = 0; i < DNB; i++) {
      a = dSpread * (i - DCENTER) / 8;
      DCS[i] = Math.cos(a); DSS[i] = Math.sin(a);
    }
    dTabMode = 'spread';
  }

  function buildTabs() {
    var zero = (!on || muted || reduce || ampK <= 0);
    buildDeltaTabs();
    if (zero) {
      var i;
      for (i = 0; i <= NT; i++) { SXT[i] = 0; CXT[i] = 1; SZT[i] = 0; CZT[i] = 1; }
      return;
    }
    var TT = effT(), A = BASE_AMP * ampK;
    var i2, u, sZ, sX, aZ, aX;
    for (i2 = 0; i2 <= NT; i2++) {
      u = PROF[i2];
      sZ = G1 * Math.sin(W1 * TT + P1 - W1 * TAU * u)
         + G2 * Math.sin(W2 * TT + P2 - W2 * TAU * u)
         + G3 * Math.sin(W3 * TT + P3 - W3 * TAU * u);
      sX = G1 * Math.sin(W1 * TT + P1 + PX - W1 * TAU * u)
         + G2 * Math.sin(W2 * TT + P2 + PX - W2 * TAU * u)
         + G3 * Math.sin(W3 * TT + P3 + PX - W3 * TAU * u);
      aZ = A * u * sZ;
      aX = A * XR * u * sX;
      SZT[i2] = Math.sin(aZ); CZT[i2] = Math.cos(aZ);
      SXT[i2] = Math.sin(aX); CXT[i2] = Math.cos(aX);
    }
  }

  var lastSig = '';
  function poseSig() {
    var zero = (!on || muted || reduce || ampK <= 0);
    return zero ? ('Z|' + ampK.toFixed(4))
                : (effT().toFixed(6) + '|' + ampK.toFixed(4) + '|' + TAU.toFixed(6));
  }

  function deltaSig() {
    if (!(!on || muted || reduce || ampK <= 0) && dOn && dSpread > 1e-6) return 'd' + dSpread.toFixed(6);
    return 'd0';
  }
  var lastDeltaSig = '';
  function rebuildIfDirty() {
    if (!tabDirty) return;
    tabDirty = false;
    buildTabs();
  }

  /* ================= v42 · δ 场 ================= */

  function pollPhase() {
    var P = window.CLTwigPhase;
    if (!P || typeof P.on !== 'function' || typeof P.spread !== 'function') {
      if (dOn !== false) { dOn = false; tabDirty = true; }
      return;
    }
    var o, s;
    try { o = !!P.on(); } catch (e) { o = false; }
    try { s = +P.spread(); } catch (e) { s = 0; }
    if (!isFinite(s)) s = 0;
    if (s < 0) s = 0;
    if (o !== dOn || s !== dSpread) { dOn = o; dSpread = s; tabDirty = true; }
  }

  function deltaLive() {
    return !(!on || muted || reduce || ampK <= 0) && dOn && dSpread > 1e-6;
  }

  function fieldAt(px, pz) {
    var r2 = px * px + pz * pz;
    var w = r2 / (r2 + R02);
    var th = Math.atan2(pz, px);
    var h = DG1 * Math.sin(DH1 * th + DP1) + DG2 * Math.sin(DH2 * th + DP2);
    return w * h;
  }

  function bucketOf(px, py, pz) {
    pollPhase();
    if (!deltaLive()) return DCENTER;
    return bucketRaw(px, pz);
  }

  function bucketRaw(px, pz) {
    var b = Math.round(fieldAt(px, pz) * 8) + DCENTER;
    return b < 0 ? 0 : (b > 16 ? 16 : b);
  }

  function deltaAt(px, py, pz) {
    pollPhase();
    var q = fieldAt(px, pz);
    if (!deltaLive()) return { b: DCENTER, delta: 0 };
    return { b: bucketRaw(px, pz), delta: dSpread * q };
  }


  function compute(TT) {
    var z = G1 * Math.sin(W1 * TT + P1) + G2 * Math.sin(W2 * TT + P2) + G3 * Math.sin(W3 * TT + P3);
    var x = XR * (G1 * Math.sin(W1 * TT + P1 + PX) +
                  G2 * Math.sin(W2 * TT + P2 + PX) +
                  G3 * Math.sin(W3 * TT + P3 + PX));
    return { x: x, z: z };
  }

  function qSway() {
    var Q = window.CLTreeQuality;
    if (!Q || !Q.of) return 1;
    var v = tryFn(function () { return Q.of('sway'); });
    return v == null ? 1 : num(v, 1);
  }

  function reduceNow() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  function bendInto(px, py, pz, out, b) {
    rebuildIfDirty();
    var u = py * INV_YTOP;
    if (u <= 0) { out[0] = px; out[1] = py; out[2] = pz; return out; }
    if (u > 1) u = 1;
    var bb = (b === undefined || b === null) ? bucketOf(px, py, pz) : (b | 0);
    if (bb < 0) bb = 0; else if (bb > 16) bb = 16;
    var dc = DCS[bb], ds = DSS[bb];
    var rx = px * dc - pz * ds, rz = px * ds + pz * dc;
    var f = u * NT, i = f | 0, tt;
    if (i >= NT) { i = NT - 1; tt = 1; } else tt = f - i;
    var j = i + 1;
    var sx = SXT[i] + (SXT[j] - SXT[i]) * tt, cx = CXT[i] + (CXT[j] - CXT[i]) * tt;
    var sz = SZT[i] + (SZT[j] - SZT[i]) * tt, cz = CZT[i] + (CZT[j] - CZT[i]) * tt;
    var y1 = py * cx - rz * sx, z1 = py * sx + rz * cx;
    out[0] = rx * cz - y1 * sz; out[1] = rx * sz + y1 * cz; out[2] = z1;
    return out;
  }

  function bend(p) {
    if (!p || p.length < 3) return p ? [p[0], p[1], p[2]] : [0, 0, 0];
    return bendInto(p[0], p[1], p[2], [0, 0, 0]);
  }

  function pose(y) {
    rebuildIfDirty();
    var u = num(y, 0) * INV_YTOP;
    if (u <= 0) return { ax: 0, az: 0 };
    if (u > 1) u = 1;
    var f = u * NT, i = f | 0, tt;
    if (i >= NT) { i = NT - 1; tt = 1; } else tt = f - i;
    var j = i + 1;
    var sx = SXT[i] + (SXT[j] - SXT[i]) * tt, cx = CXT[i] + (CXT[j] - CXT[i]) * tt;
    var sz = SZT[i] + (SZT[j] - SZT[i]) * tt, cz = CZT[i] + (CZT[j] - CZT[i]) * tt;
    return { ax: Math.atan2(sx, cx), az: Math.atan2(sz, cz) };
  }

  function dress(obj, yRef) {
    if (!obj || !obj.rotation) return;
    var q = pose(num(yRef, 0));
    obj.rotation.set(q.ax, 0, q.az);
  }

  function update(s) {
    s = s || {};
    on = num(s.on, on);
    if (s.muted !== undefined) muted = !!s.muted;
    reduce = reduceNow();
    var k = qSway();
    if (k !== ampK) { ampK = k; tabDirty = true; }
    t = num(s.t, t + 0.016);
    /* v42：每帧一次镜像 CLTwigPhase（订阅式接口不存在，轮询是唯一低成本路径；
     * 每帧一次 × 属性读取 = 零成本，绝不进顶点循环）。必须在两个签名之前。 */
    pollPhase();
    var dsig = deltaSig();
    if (dsig !== lastDeltaSig) { lastDeltaSig = dsig; tabDirty = true; rev++; }
    var sig = poseSig();
    if (sig !== lastSig) { lastSig = sig; tabDirty = true; rev++; }
    rebuildIfDirty();
    return true;
  }

  function freeze(TT) { frozen = num(TT, 0); tabDirty = true; return frozen; }
  function resume() { frozen = null; tabDirty = true; return true; }

  function setWave(tau) {
    var v = num(tau, TAU);
    if (!isFinite(v)) v = TAU;
    if (v < 0) v = 0;
    if (v > 5) v = 5;
    TAU = v;
    tabDirty = true;
    return TAU;
  }

  function norm() {
    /* v37 语义：报「无延迟的 t 时刻风场值」= 旧 compute(t)（行波相位置 0 的 (x,z)）。
     * 旧模型 cur 的精确等价物；新模型没有单一 cur 标量对，故用此口径保留归一化读数。 */
    var c = compute(effT());
    return { x: +c.x.toFixed(6), z: +c.z.toFixed(6) };
  }

  function degAt(y) {
    var q = pose(y);
    return { ax: +(q.ax / DEG).toFixed(6), az: +(q.az / DEG).toFixed(6) };
  }

  function dispAt(y, r) {
    var s = [0, 0, 0];
    bendInto(num(r, 0), num(y, 0), 0, s);
    var dx = s[0] - num(r, 0), dy = s[1] - num(y, 0), dz = s[2] - 0;
    return +Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(8);
  }

  function stats() {
    pollPhase();
    return {
      on: on, muted: muted, reduce: reduce, ampK: ampK, frozen: frozen, rev: rev,
      t: +t.toFixed(4),
      norm: norm(),
      ampDeg: +(BASE_AMP / DEG).toFixed(3),
      period: +(2 * Math.PI / W1).toFixed(3),
      yTop: Y_TOP, pow: POW, tabN: NT,
      delta: {
        on: deltaLive(),
        spread: +dSpread.toFixed(6),
        deg: +(dSpread / Math.PI * 180).toFixed(1),
        nb: DNB,
        center: DCENTER,
        mirrorOn: dOn,
        tabMode: dTabMode,
        r0: Math.sqrt(R02),
        h: [DH1, DP1, DG1, DH2, DP2, DG2]
      },
      deg: { y0: degAt(0), y30: degAt(0.30), y60: degAt(0.60), y90: degAt(0.90) },
      dispY: { y0: dispAt(0, 0.2), y30: dispAt(0.30, 0.10), y60: dispAt(0.60, 0.32), y90: dispAt(0.90, 0.50) },
      wave: {
        on: true,
        tau: +TAU.toFixed(4),
        freqs: [W1, W2, W3],
        gains: [G1, G2, G3],
        phases: [P1, P2, P3],
        xr: XR,
        px: PX
      }
    };
  }

  var API = {
    name: 'tree-sway',
    build: function () { ensureT();
      rebuildIfDirty(); return true; },
    update: update,
    dispose: function () { frozen = null; tabDirty = true; return true; },
    bend: bend,
    bendInto: bendInto,
    pose: pose,
    dress: dress,
    degAt: degAt,
    dispAt: dispAt,
    freeze: freeze,
    resume: resume,
    setWave: setWave,
    setOn: function (v) { muted = !v; tabDirty = true; return true; },
    /* v42 δ 场 */
    bucketOf: bucketOf,
    bucketRaw: bucketRaw,
    deltaAt: deltaAt,
    fieldAt: fieldAt,
    deltaLive: deltaLive,
    get: function () { return { t: t, on: on, muted: muted, reduce: reduce, ampK: ampK, frozen: frozen, rev: rev, tau: TAU }; },
    norm: norm,
    rev: function () { return rev; },
    stats: stats
  };

  window.CLTreeSway = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();

  if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
    window.CLAbyssBreath.subscribe(function (snap) {
      if (snap && isFinite(snap.t)) {
        update({ t: snap.t });
      }
    });
  }
})();
