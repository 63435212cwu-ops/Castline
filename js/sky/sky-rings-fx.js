(function (g) {
'use strict';
var T = g.CLSkyTokens, C = T.C, AL = T.ALPHA, DU = T.DUR, LY = T.LAYER_DISC, WGD = T.DISC_WEDGE || { r0: 0.87, midR: 0.3, midA: 0.16, outerA: 0.62, longSpan: 2.3, tip: 0.5 };
var MB = 16, MP = 160, WS = 32, ES = 0.03, EN = 8, EX = 72, P2 = Math.PI * 2, _c = new THREE.Color();
var GX = g.CLSkyRingsGLSL.fx, RV = GX.RV, RI = GX.RI, RP = GX.RP, FV = GX.FV, FF = GX.FF, WV = GX.WV || GX.FV, WF = GX.WF || GX.FF, PV = GX.PV, PF = GX.PF;

function mat(u, vs, fs) {
  return new THREE.ShaderMaterial({ uniforms: u, vertexShader: vs, fragmentShader: fs, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, premultipliedAlpha: true, depthWrite: false, depthTest: false, transparent: true });
}
function rU(half, hex) {
  return { uRes: { value: new THREE.Vector2(1, 1) }, uDpr: { value: 1 }, uHalf: { value: half }, uColor: { value: new THREE.Color(hex) }, uAlpha: { value: 1 } };
}
function fU(hex, base, rad, wake) {
  return { uColor: { value: new THREE.Color(hex) }, uAlpha: { value: 1 }, uBase: { value: base }, uRad: { value: rad }, uWake: { value: wake } };
}
function wU(hex, base, rad, wake) {
  return { uColor: { value: new THREE.Color(hex) }, uAlpha: { value: 1 }, uBase: { value: base }, uRad: { value: rad }, uWake: { value: wake }, uTime: { value: 0 }, uTier: { value: 1 } };
}
function set3(a, i, x, y, z) { a[i * 3] = x; a[i * 3 + 1] = y; a[i * 3 + 2] = z || 0; }
function d3(n) { return new THREE.BufferAttribute(new Float32Array(n * 3), 3).setUsage(THREE.DynamicDrawUsage); }
function idx(seg, vps) {
  var ix = new Uint16Array(seg * 6), i, b, o;
  for (i = 0; i < seg; i++) { b = i * vps; o = i * 6; ix[o] = b; ix[o + 1] = b + 1; ix[o + 2] = b + 2; ix[o + 3] = b + 1; ix[o + 4] = b + 3; ix[o + 5] = b + 2; }
  return new THREE.BufferAttribute(ix, 1);
}
function band(seg) {
  var n = seg * 4, i, b, sd = new Float32Array(n), tt = new Float32Array(n), o = new THREE.BufferGeometry();
  for (i = 0; i < seg; i++) { b = i * 4; sd[b] = -1; sd[b + 1] = 1; sd[b + 2] = -1; sd[b + 3] = 1; tt[b] = 0; tt[b + 1] = 0; tt[b + 2] = 1; tt[b + 3] = 1; }
  o.setAttribute('position', d3(n)); o.setAttribute('aPrev', d3(n)); o.setAttribute('aNext', d3(n));
  o.setAttribute('aSide', new THREE.BufferAttribute(sd, 1)); o.setAttribute('aT', new THREE.BufferAttribute(tt, 1));
  o.setIndex(idx(seg, 4));
  return o;
}
function seg(geo, s, r0, r1, a, h0, h1) {
  var p = geo.attributes.position.array, pv = geo.attributes.aPrev.array, nx = geo.attributes.aNext.array, b = s * 4, i;
  var c = Math.cos(a), y = Math.sin(a), x0 = c * r0, y0 = y * r0, x1 = c * r1, y1 = y * r1;
  set3(p, b, x0, y0, h0); set3(p, b + 1, x0, y0, h0); set3(p, b + 2, x1, y1, h1); set3(p, b + 3, x1, y1, h1);
  for (i = 0; i < 4; i++) { set3(pv, b + i, x0, y0, h0); set3(nx, b + i, x1, y1, h1); }
  geo.attributes.position.needsUpdate = geo.attributes.aPrev.needsUpdate = geo.attributes.aNext.needsUpdate = true;
}
function fanIdx(seg) {
  var ix = new Uint16Array(seg * 12), i, b, o;
  for (i = 0; i < seg; i++) { b = i * 3; o = i * 12;
    ix[o] = b; ix[o + 1] = b + 1; ix[o + 2] = b + 3; ix[o + 3] = b + 1; ix[o + 4] = b + 4; ix[o + 5] = b + 3;
    ix[o + 6] = b + 1; ix[o + 7] = b + 2; ix[o + 8] = b + 4; ix[o + 9] = b + 2; ix[o + 10] = b + 5; ix[o + 11] = b + 4; }
  return new THREE.BufferAttribute(ix, 1);
}
function fan(max) {
  var v = (max + 1) * 3, o = new THREE.BufferGeometry();
  o.setAttribute('position', d3(v));
  o.setAttribute('aT', new THREE.BufferAttribute(new Float32Array(v), 1).setUsage(THREE.DynamicDrawUsage));
  o.setAttribute('aV', new THREE.BufferAttribute(new Float32Array(v), 1).setUsage(THREE.DynamicDrawUsage));
  o.setIndex(fanIdx(max));
  o.setDrawRange(0, 0);
  return o;
}
function setFan(geo, n, a0, a1, r0, r1, h1, prof) {
  var p = geo.attributes.position.array, tt = geo.attributes.aT.array, vv = geo.attributes.aV.array, i;
  var rm = prof ? r0 + (r1 - r0) * prof.m : r0, vm = prof ? prof.v : 0, v1 = prof ? prof.o : 0;
  for (i = 0; i <= n; i++) {
    var t = i / n, a = a0 + (a1 - a0) * t, c = Math.cos(a), y = Math.sin(a), q = i * 3;
    set3(p, q, c * r0, y * r0, 0); set3(p, q + 1, c * rm, y * rm, h1 * (prof ? prof.m : 0)); set3(p, q + 2, c * r1, y * r1, h1);
    tt[q] = t; tt[q + 1] = t; tt[q + 2] = t; vv[q] = 0; vv[q + 1] = vm; vv[q + 2] = v1;
  }
  geo.attributes.position.needsUpdate = geo.attributes.aT.needsUpdate = geo.attributes.aV.needsUpdate = true;
  geo.setDrawRange(0, n * 12);
}
function pins() {
  var o = new THREE.BufferGeometry();
  o.setAttribute('position', d3(MP));
  o.setAttribute('aCol', new THREE.BufferAttribute(new Float32Array(MP * 3), 3));
  o.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(MP), 1));
  o.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(MP), 1).setUsage(THREE.DynamicDrawUsage));
  o.setDrawRange(0, 0);
  return o;
}
function pin(geo, i, r, a, hex, size, shape, alpha, h) {
  set3(geo.attributes.position.array, i, Math.cos(a) * r, Math.sin(a) * r, h);
  _c.setHex(hex);
  var c = geo.attributes.aCol.array;
  c[i * 3] = _c.r; c[i * 3 + 1] = _c.g; c[i * 3 + 2] = _c.b;
  geo.attributes.aSize.array[i] = shape ? size : -size;
  geo.attributes.aAlpha.array[i] = alpha;
}
function node(geo, mt, parent) {
  var m = new THREE.Mesh(geo, mt);
  m.frustumCulled = false; m.renderOrder = 3; m.layers.set(LY); m.visible = false;
  parent.add(m);
  return m;
}

g.CLSkyRingsFx = {
create: function (opts) {
  var S = opts.scene, anchor = opts.anchor, v2 = new THREE.Vector2(), i;
  var tier = 'high';
  if (g.navigator && g.navigator.hardwareConcurrency && g.navigator.hardwareConcurrency <= 4) tier = 'low';
  var reducedMotion = T.reduced();
  var cfg = null, st = 'hidden', nR0 = 0.2, nR1 = 1, nB = 0, nC = 0, nP = 0, head = 0;
  var nOn = false, nA = 0, nT = 0, fN = 0, fS = 0, fW = 0;
  var kOn = false, aF = 0, aT2 = 0, b0 = 1e9, b1 = 1e9;
  var dOn = false, wd = null, d0 = 1e9, d1 = 1e9, dr0 = -1, dr1 = -1, pB = [], wPin = -1, wdLong = false;

  var nMat = mat(rU(7.5, C.BRASS_HOT), RV, RI);
  var eMat = mat(rU(0.6, C.BRASS), RV, RP), bMat = mat(rU(0.8, C.BRASS), RV, RP);
  var kMat = mat(fU(C.BRASS, 0.4, 0.6, 1), FV, FF);
  var dMat = mat(wU(C.BRASS_DIM, 0, WGD.outerA, 0), WV, WF);
  var pMat = mat({ uDpr: { value: 1 } }, PV, PF);
  var ribMats = [nMat, eMat, bMat];
  var nG = band(1), kG = fan(WS), dG = fan(EX), eG = band(2), bG = band(MB), pG = pins();
  var nM = node(nG, nMat, anchor), kM = node(kG, kMat, anchor), dM = node(dG, dMat, anchor);
  var eM = node(eG, eMat, anchor), bM = node(bG, bMat, anchor);
  var pP = new THREE.Points(pG, pMat);
  pP.frustumCulled = false; pP.renderOrder = 3; pP.layers.set(LY); pP.visible = false;
  anchor.add(pP);

  function build(c) {
    if (c) cfg = c;
    if (!cfg) return;
    nR0 = cfg.rIn * 0.2; nR1 = cfg.rBez * 1.02;
    var bs = cfg.bridges || [], cs = cfg.caps || [];
    nB = Math.min(MB, bs.length);
    for (i = 0; i < nB; i++) seg(bG, i, bs[i].r0, bs[i].r1, bs[i].a, bs[i].z0, bs[i].z1);
    bG.setDrawRange(0, nB * 6);
    nC = Math.min(MP - 3 - nB, cs.length);
    nP = 0; pB = [];
    head = nP; pin(pG, nP++, cfg.rMain, nA, C.BRASS_HOT, 14, 1, 1, cfg.zMain); pB.push(1);
    for (i = 0; i < nB; i++) { pin(pG, nP++, bs[i].r1, bs[i].a, bs[i].color, 6, 1, 1, bs[i].z1); pB.push(0.7); }
    for (i = 0; i < nC; i++) { pin(pG, nP++, cs[i].r, cs[i].a, cs[i].color, 10, cs[i].kind === 'resolved' ? 1 : 0, 0.75, cs[i].z); pB.push(0.75); }
    wPin = nP; pin(pG, nP++, 0, 0, C.BRASS, 0, 1, 0, 0); pB.push(0); pin(pG, nP++, 0, 0, C.BRASS, 0, 1, 0, 0); pB.push(0);
    pG.setDrawRange(0, nP);
    pG.attributes.position.needsUpdate = pG.attributes.aCol.needsUpdate = pG.attributes.aSize.needsUpdate = true;
    b0 = b1 = d0 = 1e9;
  }
  function setNeedle(a) {
    if (a === null || a === undefined) { nOn = false; return; }
    if (!nOn) { nA = a; fN = 0; }
    nT = a; nOn = true;
  }
  function setWake(f, t) { if (f === null || f === undefined) { kOn = false; return; } aF = f; aT2 = t; kOn = true; }
  function setWedge(w) { if (!w) { dOn = false; return; } wd = w; dOn = true; dMat.uniforms.uColor.value.setHex(w.color); }
  var structureMix = 0;
  function setStructure(v) { structureMix = Math.max(0, Math.min(1, +v || 0)); }
  function setState(s) { st = s; }
  function setTier(t) {
    tier = t;
    nMat.fragmentShader = t === 'low' ? RP : RI;
    nMat.uniforms.uHalf.value = t === 'low' ? 1.1 : 7.5;
    nMat.needsUpdate = true;
    if (dMat.uniforms.uTier) dMat.uniforms.uTier.value = t === 'low' ? 0 : 1;
  }

  function update(dt, tAnim) {
    if (!cfg) return;
    reducedMotion = T.reduced();
    var r = S.renderer, dpr = r.getPixelRatio() || 1;
    r.getDrawingBufferSize(v2);
    for (i = 0; i < 3; i++) { ribMats[i].uniforms.uRes.value.copy(v2); ribMats[i].uniforms.uDpr.value = dpr; }
    pMat.uniforms.uDpr.value = dpr;
    if (dMat.uniforms.uTime) dMat.uniforms.uTime.value = tAnim || 0;
    var k = reducedMotion ? 1 : 1 - Math.exp(-dt * (3 / DU.soft));
    var tg = st === 'plot' ? 1 : 0;
    fS += (tg - fS) * k;
    if (fS < 0.002) fS = 0; else if (fS > 0.998) fS = 1;
    fN += ((nOn ? 1 : 0) - fN) * k;
    if (reducedMotion) nA = nT;
    else {
      var d = nT - nA;
      if (!isFinite(d)) d = 0;
      while (d > Math.PI) d -= P2;
      while (d < -Math.PI) d += P2;
      nA += d * k;
      if (nA > Math.PI) nA -= P2; else if (nA < -Math.PI) nA += P2;
    }
    if (nOn) {
      seg(nG, 0, nR0, nR1, nA, 0, cfg.zBez);
      set3(pG.attributes.position.array, head, Math.cos(nA) * cfg.rMain, Math.sin(nA) * cfg.rMain, cfg.zMain);
      pG.attributes.position.needsUpdate = true;
    }
    var na = fN * fS;
    nMat.uniforms.uAlpha.value = na * (1 - structureMix * (1 - T.ALPHA.structureKeep));
    nM.visible = na > 0.004;
    var kw = kOn && fS > 0.004;
    if (kw && (Math.abs(aT2 - b0) > 1e-4 || Math.abs(aF - b1) > 1e-4)) { setFan(kG, WS, aT2, aF, nR0, cfg.rBez, cfg.zBez); b0 = aT2; b1 = aF; }
    kMat.uniforms.uAlpha.value = AL.wake * fS * (tier === 'low' ? 0.22 : 1) * (1 - structureMix);
    kM.visible = kw;
    fW += ((dOn ? 1 : 0) - fW) * k;
    var kd = dOn && fW > 0.004 && fS > 0.004, ga = AL.wedge * fW * fS;
    if (kd && wd && (wd.a0 !== d0 || wd.a1 !== d1 || wd.r0 !== dr0 || wd.r1 !== dr1)) {
      var span = Math.abs(wd.a1 - wd.a0);
      wdLong = span > WGD.longSpan;
      var tip = wdLong ? Math.min(span, Math.max(WGD.tip, span * 0.12)) : span;
      var aTip = wd.a0 + (wd.a1 > wd.a0 ? tip : -tip);
      setFan(dG, Math.min(EX, Math.max(EN, Math.ceil(tip / ES))), wd.a0, aTip, wd.r0, wd.r1, wd.z1, { m: WGD.midR, v: WGD.midA, o: WGD.outerA });
      dMat.uniforms.uWake.value = wdLong ? 1 : 0;
      seg(eG, 0, wd.r0, wd.r1, wd.a0, 0, wd.z1);
      seg(eG, 1, wd.r0, wd.r1, wd.a1, 0, wd.z1);
      if (wPin >= 0) {
        pin(pG, wPin, wd.r1, wd.a0, wd.color, 10, 1, 0, wd.z1);
        pin(pG, wPin + 1, wd.r1, wd.a1, wd.color, 10, 1, 0, wd.z1);
        pG.attributes.position.needsUpdate = pG.attributes.aCol.needsUpdate = pG.attributes.aSize.needsUpdate = true;
      }
      d0 = wd.a0; d1 = wd.a1; dr0 = wd.r0; dr1 = wd.r1;
    }
    dMat.uniforms.uAlpha.value = ga;
    dM.visible = kd;
    eMat.uniforms.uAlpha.value = fW * fS * 0.35;
    eM.visible = kd && tier !== 'low';
    bMat.uniforms.uAlpha.value = fS * 0.2;
    bM.visible = fS > 0.004 && nB > 0;
    var al = pG.attributes.aAlpha.array;
    for (i = 0; i < nP; i++) al[i] = pB[i] * fS;
    al[head] = na;
    if (wPin >= 0) { al[wPin] = al[wPin + 1] = wdLong ? 0.9 * fW * fS : 0; }
    pG.attributes.aAlpha.needsUpdate = true;
    pP.visible = fS > 0.004 && nP > 0;
  }
  function stats() {
    return { needle: nM.visible, needleA: nA, wake: kM.visible, wedge: dM.visible, bridges: nB, caps: nC, state: st };
  }
  function dispose() {
    var os = [nM, kM, dM, eM, bM, pP], ms = [nMat, eMat, bMat, kMat, dMat, pMat], j;
    for (j = 0; j < os.length; j++) { if (os[j].parent) os[j].parent.remove(os[j]); os[j].geometry.dispose(); }
    for (j = 0; j < ms.length; j++) ms[j].dispose();
    cfg = null;
  }
  return { build: build, setNeedle: setNeedle, setWake: setWake, setWedge: setWedge, setState: setState, setStructure: setStructure, setTier: setTier, update: update, stats: stats, dispose: dispose };
}
};
})(window);
