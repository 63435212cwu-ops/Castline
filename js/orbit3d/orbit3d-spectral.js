/* @role webgl · @owns js/orbit3d-spectral.js · @budget drawcalls=0 js_ms=0.1 · @contract v47+v50 */
(function (g) {
  'use strict';
  var NAME = 'orbit3d-spectral', VERSION = '50';
  var MM = '(prefers-reduced-motion: reduce)';
  var EP_TOK = ['--violet', '--mint', '--signal', '--hot', '--warm'];
  var UNI_DECL = 'uniform float uSpectral; uniform int uEpN; uniform float uEpA[5]; uniform vec3 uEpC[5]; uniform float uReadA; uniform float uReadK; ';
  var EPC = 'vec3 epochCol(float a, float merid){ float t = fract((merid - a) / 6.283185307); vec3 c = uEpC[0];\nfor (int i = 1; i < 5; i++) { if (i < uEpN) { float t0 = fract((merid - uEpA[i]) / 6.283185307); c = mix(c, uEpC[i], smoothstep(t0 - 0.02, t0 + 0.02, t)); } } return c; }\n';
  var S_ANCHOR = 'gl_FragColor = vec4(c * a, a); }';
  var S_NEW = 'c = mix(c, epochCol(vA.w, uMerid) * (0.55 + 0.45 * clamp(length(c), 0.0, 1.0)), uSpectral);\nif (uReadA > -50.0) { float tf = fract((uMerid - vA.w) / 6.283185307); float ts = fract((uMerid - uReadA) / 6.283185307); a *= mix(1.0, 0.35, uReadK * smoothstep(ts, ts + 0.015, tf)); }\ngl_FragColor = vec4(c * a, a); }';
  var V_ANCHOR = 'vCol = aCol; gl_PointSize';
  var V_NEW = 'float kb = 1.0e9; float kid = 6.0; for (int k = 0; k < 7; k++) { float dd = distance(aCol, uKindC[k]); if (dd < kb) { kb = dd; kid = float(k); } }\nvKind = (aB.w > 0.5) ? -1.0 : kid;\nvCol = mix(aCol, epochCol(ang, uMerid) * (0.6 + 0.4 * clamp(length(aCol), 0.0, 1.0)), uSpectral); gl_PointSize';
  var LUM_BLOCK = '\nif (uReadA > -50.0) { float rtf = fract((uMerid - ang) / 6.283185307); float rts = fract((uMerid - uReadA) / 6.283185307); lum *= mix(1.0, 0.35, uReadK * smoothstep(rts, rts + 0.015, rtf)); }';
  var FAR_ANCHOR = 'float far = vFar * uAero;';
  var KIND_BLOCK = 'if (vKind > 0.5 && vKind < 6.5) { float kk = vKind;\nif (kk < 1.5) { float dia = abs(p.x) + abs(p.y); float m = 1.0 - smoothstep(0.17, 0.24, dia); core = max(core * 0.35, m * 0.95); spike *= 0.3; }\nelse if (kk < 2.5) { vec2 q1 = p - vec2(0.13, 0.0); vec2 q2 = p + vec2(0.13, 0.0); core = max(exp(-dot(q1, q1) * 220.0), exp(-dot(q2, q2) * 220.0)) * 0.95; spike *= 0.3; }\nelse if (kk < 3.5) { float cx = exp(-abs(p.y) * 60.0) * exp(-abs(p.x) * 6.0); float cy = exp(-abs(p.x) * 60.0) * exp(-abs(p.y) * 6.0); spike = max(spike, (cx + cy) * 0.8); }\nelse if (kk < 4.5) { float rg = exp(-pow((r - 0.21) * 34.0, 2.0)); core = core * 0.25 + rg * 0.9; spike *= 0.3; }\nelse if (kk < 5.5) { float up = (p.y > 0.0) ? 1.0 : 0.35; core *= up; glow *= (p.y > 0.0) ? 1.0 : 0.5; }\nelse { spike = 0.0; airy = 0.0; } }\n';

  var T = null, MY = null, epCols = null, kindCols = null, missList = [];
  var spectralK = 0.72, target = null, angle = -99, readK = 0, uaCur = -99;
  var installed = 0, installs = 0, epochsN = 0, lastT = null;

  function surgery() {
    var S = g.CLOrbit3DShaders, miss = [], out = {};
    if (!S) return { miss: ['CLOrbit3DShaders'] };
    var sf = S.S_FS;
    if (typeof sf !== 'string') miss.push('S_FS');
    else if (sf.indexOf(S_ANCHOR) < 0 || sf.indexOf('void main') < 0) miss.push('S_FS:anchor');
    else {
      var a = sf.replace(S_ANCHOR, S_NEW), mi = a.indexOf('void main');
      out.S_FS = UNI_DECL + a.slice(0, mi) + EPC + a.slice(mi);
    }
    var bv = S.B_VS;
    if (typeof bv !== 'string') miss.push('B_VS');
    else if (bv.indexOf(V_ANCHOR) < 0 || bv.indexOf('float lum = aC.y') < 0 || bv.indexOf('void main') < 0) miss.push('B_VS:anchor');
    else {
      var v = bv.replace(V_ANCHOR, V_NEW);
      var li = v.indexOf('float lum = aC.y'), semi = v.indexOf(';', li);
      v = v.slice(0, semi + 1) + LUM_BLOCK + v.slice(semi + 1);
      var m2 = v.indexOf('void main');
      out.B_VS = UNI_DECL + 'uniform vec3 uKindC[7]; varying float vKind; ' + v.slice(0, m2) + EPC + v.slice(m2);
    }
    var bf = S.B_FS;
    if (typeof bf !== 'string') miss.push('B_FS');
    else if (bf.indexOf(FAR_ANCHOR) < 0) miss.push('B_FS:anchor');
    else out.B_FS = 'varying float vKind; ' + bf.replace(FAR_ANCHOR, KIND_BLOCK + FAR_ANCHOR);
    out.miss = miss;
    return out;
  }

  function fbCol(i) {
    var P = g.CLPalette;
    try {
      if (P && P.mainColor) { var m = P.mainColor(i); if (m && m.isColor) return m.clone(); if (m) return new T.Color(m); }
    } catch (e) {}
    try { if (P && P.hex && P.KINDS) return new T.Color(P.hex(P.KINDS[i % P.KINDS.length])); } catch (e) {}
    return new T.Color(0);
  }
  function tokCol(i) {
    var v = '';
    try { if (g.document) v = g.getComputedStyle(g.document.documentElement).getPropertyValue(EP_TOK[i]); } catch (e) {}
    v = (v || '').replace(/^\s+|\s+$/g, '');
    if (v) { try { var c = new T.Color(); c.setStyle(v); return c; } catch (e) {} }
    return fbCol(i);
  }
  function kindCol(k) {
    var P = g.CLPalette;
    try { if (P && P.hex && P.KINDS && P.KINDS[k]) return new T.Color(P.hex(P.KINDS[k])); } catch (e) {}
    return fbCol(k);
  }

  function build(o) {
    if (o && o.T) T = o.T;
    if (!T) T = g.THREE;
    if (!T || !T.Color) return;
    epCols = [tokCol(0), tokCol(1), tokCol(2), tokCol(3), tokCol(4)];
    kindCols = [];
    for (var k = 0; k < 7; k++) kindCols.push(kindCol(k));
    MY = surgery();
    missList = MY.miss || [];
    api.ready = true;
  }

  function addUni(m, isBead) {
    var u = m.uniforms;
    if (!u) { m.uniforms = {}; u = m.uniforms; }
    if (!u.uSpectral) u.uSpectral = { value: spectralK };
    if (!u.uEpN) u.uEpN = { value: 0 };
    if (!u.uEpA) u.uEpA = { value: [0, 0, 0, 0, 0] };
    if (!u.uEpC) u.uEpC = { value: epCols };
    if (!u.uReadA) u.uReadA = { value: -99 };
    if (!u.uReadK) u.uReadK = { value: 0 };
    if (isBead && !u.uKindC) u.uKindC = { value: kindCols };
  }
  function setUnis(m, epN, epA, spect, ua, rk) {
    var u = m.uniforms;
    if (!u) return;
    if (u.uSpectral) u.uSpectral.value = spect;
    if (u.uEpN) u.uEpN.value = epN;
    if (u.uEpA && u.uEpA.value) { var A = u.uEpA.value; for (var i = 0; i < 5; i++) A[i] = epA[i]; }
    if (u.uReadA) u.uReadA.value = ua;
    if (u.uReadK) u.uReadK.value = rk;
  }
  function epochData() {
    var V = g.CLPlotOrbitView, n = 0, arr = [0, 0, 0, 0, 0];
    if (V && V.desc) {
      try {
        var ep = V.desc().epochs;
        if (ep && ep.length) {
          n = ep.length > 5 ? 5 : ep.length;
          for (var i = 0; i < n; i++) { var a = ep[i] && ep[i].angle; arr[i] = (typeof a === 'number') ? a : 0; }
        }
      } catch (e) {}
    }
    epochsN = n;
    return arr;
  }
  function red() { try { return !!(g.matchMedia && g.matchMedia(MM).matches); } catch (e) { return false; } }
  function lowEnd() {
    var hc = (g.navigator && g.navigator.hardwareConcurrency) || 8;
    if (hc <= 4) return true;
    var L = g.CLOrbit3DLayer;
    if (L && L.stats) { try { if (L.stats().tier === 2) return true; } catch (e) {} }
    return false;
  }

  function update(s) {
    if (!api.ready) build(null);
    if (!api.ready) return;
    var dt = 0.016;
    if (s && typeof s.t === 'number') { if (lastT !== null) dt = Math.max(0, Math.min(0.1, s.t - lastT)); lastT = s.t; }
    var damp = red() || lowEnd();
    if (damp) readK = (target === null) ? 0 : 1;
    else {
      var stp = dt / 0.4;
      readK = (target !== null) ? Math.min(1, readK + stp) : Math.max(0, readK - stp);
    }
    uaCur = (target !== null || readK > 0) ? angle : -99;
    var spect = damp ? 0 : spectralK;
    var epA = epochData(), epN = epochsN;

    var L = g.CLOrbit3DLayer;
    installed = 0;
    if (!MY || !L || !L.spinObject) return;
    var spin = L.spinObject();
    if (!spin || !spin.children) return;
    var ch = spin.children;
    for (var i = 0; i < ch.length; i++) {
      var c = ch[i], ro = c && c.renderOrder, m = c && c.material;
      if (!m || !m.fragmentShader && !m.vertexShader) continue;
      if (ro === -21) {
        if (!MY.B_VS || !MY.B_FS) continue;
        if (m.vertexShader !== MY.B_VS || m.fragmentShader !== MY.B_FS) {
          m.vertexShader = MY.B_VS; m.fragmentShader = MY.B_FS;
          addUni(m, true); m.needsUpdate = true; installs++;
        }
        if (m.vertexShader === MY.B_VS && m.fragmentShader === MY.B_FS) installed++;
        setUnis(m, epN, epA, spect, uaCur, readK);
      } else if (ro === -29 || ro === -26 || ro === -25 || ro === -23) {
        if (!MY.S_FS) continue;
        if (m.fragmentShader !== MY.S_FS) {
          m.fragmentShader = MY.S_FS; addUni(m, false); m.needsUpdate = true; installs++;
        }
        if (m.fragmentShader === MY.S_FS) installed++;
        setUnis(m, epN, epA, spect * (ro === -23 ? 0.62 : (ro === -29 ? 1.0 : 1.22)), uaCur, readK);   /* v51：主线带留白芯 0.45、支线更彩 0.88 */
      }
    }
  }

  function setRead(a) {
    if (a === null || a === undefined) target = null;
    else { target = a; angle = a; }
  }
  function setSpectral(k) { if (typeof k === 'number') spectralK = k; }
  function stats() {
    var damp = red() || lowEnd();
    return {
      name: NAME, version: VERSION, ready: !!api.ready,
      installed: installed, epochs: epochsN,
      spectral: damp ? 0 : spectralK,
      readA: (uaCur > -50) ? uaCur : null,
      readK: Math.round(readK * 10000) / 10000,
      installs: installs, reduced: red(), anchorMissing: missList
    };
  }

  var api = {
    name: NAME, version: VERSION, ready: false,
    setRead: setRead, setSpectral: setSpectral, stats: stats
  };
  g.CLOrbit3DSpectral = api;
  if (g.CLArcana && g.CLArcana.register) g.CLArcana.register({ name: NAME, build: build, update: update });
})(typeof window !== 'undefined' ? window : this);
