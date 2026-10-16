(function () {
  'use strict';
  var T = (typeof window !== 'undefined' && window.THREE) || null;
  var A = (typeof window !== 'undefined' && window.CLTreeAnchor) || null;
  var GOLD = [1, 0.706, 0.361];
  var MAX_STD = 600, MAX_BIG = 300, FADE = 0.9;
  var group = null, points = null, lines = null;
  var pGeo = null, lGeo = null, pMat = null, lMat = null, tex = null;
  var on = false, force = null, level = 0, target = 0, built = false;
  var tick = 0, degrade = 0, big = false, bound = false, lastT = -1;
  var st = { clones: 0, lines: 0, dupNames: 0, maxPerName: 0 };

  var baseP = null, baseL = null, revSeen = -1, swScratch = [0, 0, 0];

  function refreshSway() {
    var SW = (typeof window !== 'undefined') ? window.CLTreeSway : null;
    if (!SW || typeof SW.bendInto !== 'function' || typeof SW.rev !== 'function') return;
    var r = SW.rev();
    if (r === revSeen) return;
    revSeen = r;
    var a, i;
    if (points && baseP && pGeo && pGeo.attributes && pGeo.attributes.position) {
      a = pGeo.attributes.position.array;
      for (i = 0; i < baseP.length; i += 3) {
        SW.bendInto(baseP[i], baseP[i + 1], baseP[i + 2], swScratch);
        a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
      }
      pGeo.attributes.position.needsUpdate = true;
    }
    if (lines && baseL && lGeo && lGeo.attributes && lGeo.attributes.position) {
      a = lGeo.attributes.position.array;
      for (i = 0; i < baseL.length; i += 3) {
        SW.bendInto(baseL[i], baseL[i + 1], baseL[i + 2], swScratch);
        a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
      }
      lGeo.attributes.position.needsUpdate = true;
    }
  }

  function reduced() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  function numE(v) { return (typeof v === 'number' && isFinite(v) && v >= 0) ? v : -1; }

  function hex2rgb(h) {
    var v;
    if (typeof h === 'number' && isFinite(h) && h >= 0) v = h;
    else if (typeof h === 'string') {
      var s = h.charAt(0) === '#' ? h.slice(1) : h;
      if (s.length === 3) s = s.charAt(0) + s.charAt(0) + s.charAt(1) + s.charAt(1) + s.charAt(2) + s.charAt(2);
      v = parseInt(s, 16);
      if (!isFinite(v) || v < 0) v = 0xffffff;
    } else v = 0xffffff;
    return [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
  }

  function makeTex() {
    var cv = document.createElement('canvas');
    cv.width = cv.height = 64;
    var g = cv.getContext ? cv.getContext('2d') : null;
    if (g && g.createRadialGradient) {
      var gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      gr.addColorStop(0, 'rgba(255,255,255,1)');
      gr.addColorStop(0.3, 'rgba(255,255,255,0.5)');
      gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    }
    return new T.CanvasTexture(cv);
  }

  function ensureMounted() {
    A = window.CLTreeAnchor || A;
    if (!group) group = new T.Group();
    if (!group.parent) {
      var root = (A && A.root) ? A.root() : null;
      if (root && root.add) root.add(group);
    }
    return !!(group && group.parent);
  }

  function killGeo() {
    if (group) {
      if (points) { group.remove(points); points = null; }
      if (lines) { group.remove(lines); lines = null; }
    }
    if (pGeo) { pGeo.dispose(); pGeo = null; }
    if (lGeo) { lGeo.dispose(); lGeo = null; }
    if (pMat) { pMat.dispose(); pMat = null; }
    if (lMat) { lMat.dispose(); lMat = null; }
    st.clones = st.lines = st.dupNames = st.maxPerName = 0;
  }

  function rebuild() {
    T = (typeof window !== 'undefined' && window.THREE) || T;
    if (!T) return false;
    A = window.CLTreeAnchor || A;
    var tree = (window.CLStory && CLStory.get) ? CLStory.get() : null;
    var shape = (window.CLTreeShape && tree) ? CLTreeShape.build(tree) : null;
    var res = (window.CLTreeLeaf && shape && shape.ok) ? CLTreeLeaf.assign(shape, tree) : null;
    if (!res || !res.leaves || !res.leaves.length) {
      st.state = 'empty';
      st.reason = 'no-leaves';
      if (group) group.visible = false;
      return false;
    }
    if (!A || !A.root || (A.ready && !A.ready()) || !ensureMounted()) {
      st.state = 'waiting-anchor';
      st.reason = 'anchor-not-ready';
      return false;
    }

    var cap = (big || degrade >= 1) ? MAX_BIG : MAX_STD;
    var leaves = res.leaves, cand = [], i, lf;
    for (i = 0; i < leaves.length; i++) {
      lf = leaves[i];
      if (lf && lf.dupIdx >= 1 && lf.pos && lf.pos.length >= 3) cand.push(lf);
    }
    if (cand.length === 0) {
      st.state = 'empty';
      st.reason = 'zero-clones';
    } else {
      st.state = 'ready';
      st.reason = 'ok';
    }
    cand.sort(function (a, b) {
      return (b.w || 0) - (a.w || 0) || (String(a.name) < String(b.name) ? -1 : 1);
    });
    if (cand.length > cap) cand.length = cap;
    cand.sort(function (a, b) {
      var ea = numE(a.entry), eb = numE(b.entry);
      if (ea < 0 && eb >= 0) return 1;
      if (eb < 0 && ea >= 0) return -1;
      if (ea !== eb) return ea - eb;
      return (b.w || 0) - (a.w || 0) || (String(a.name) < String(b.name) ? -1 : 1);
    });

    var eMax = 0, eMin = 1e9, ei, ev2;
    for (ei = 0; ei < leaves.length; ei++) {
      ev2 = numE(leaves[ei] && leaves[ei].entry);
      if (ev2 >= 0) { if (ev2 > eMax) eMax = ev2; if (ev2 < eMin) eMin = ev2; }
    }
    var eSpan = Math.max(1, eMax >= eMin ? eMax - eMin : 0);

    var n = cand.length, wSum = 0, w, c, nm;
    var pp = new Float32Array(n * 3), pc = new Float32Array(n * 3);
    var perName = Object.create ? Object.create(null) : {};
    for (i = 0; i < n; i++) {
      lf = cand[i];
      w = (typeof lf.w === 'number' && isFinite(lf.w)) ? lf.w : 0;
      if (w < 0) w = 0; else if (w > 1) w = 1;
      wSum += w;
      pp[i * 3] = lf.pos[0]; pp[i * 3 + 1] = lf.pos[1]; pp[i * 3 + 2] = lf.pos[2];
      c = hex2rgb(lf.color);
      var lum = 0.45 + 0.55 * w;
      pc[i * 3] = (c[0] * 0.6 + GOLD[0] * 0.4) * lum;
      pc[i * 3 + 1] = (c[1] * 0.6 + GOLD[1] * 0.4) * lum;
      pc[i * 3 + 2] = (c[2] * 0.6 + GOLD[2] * 0.4) * lum;
      nm = String(lf.name == null ? '?' : lf.name);
      perName[nm] = (perName[nm] || 0) + 1;
    }

    killGeo();

    baseP = pp.slice(); revSeen = -1;

    pGeo = new T.BufferGeometry();
    pGeo.setAttribute('position', new T.BufferAttribute(pp, 3));
    pGeo.setAttribute('color', new T.BufferAttribute(pc, 3));
    if (!tex) tex = makeTex();
    pMat = new T.PointsMaterial({
      map: tex, vertexColors: true, transparent: true, opacity: 0,
      blending: T.AdditiveBlending, depthWrite: false, sizeAttenuation: true
    });
    pMat.size = 0.006 + 0.010 * (n ? wSum / n : 0);
    points = new T.Points(pGeo, pMat);
    points.raycast = function () {};
    points.userData = { clPickable: false, clLayer: 'tree-clones', clTree: true };
    points.frustumCulled = false;
    group.add(points);

    var lCount = 0;
    if (degrade < 1 && n > 0) {
      var lp = new Float32Array(n * 6), lc = new Float32Array(n * 6);
      for (i = 0; i < n; i++) {
        lf = cand[i];
        var src = (typeof lf.dupOf === 'number') ? leaves[lf.dupOf] : null;
        if (!src || !src.pos || src.pos.length < 3) continue;
        var o = lCount * 6, cc = hex2rgb(lf.color);
        lp[o] = lf.pos[0]; lp[o + 1] = lf.pos[1]; lp[o + 2] = lf.pos[2];
        lp[o + 3] = src.pos[0]; lp[o + 4] = src.pos[1]; lp[o + 5] = src.pos[2];
        var eA = numE(lf.entry), eB = numE(src.entry), wLine = 1;
        if (eA >= 0 && eB >= 0) wLine = 0.50 + 0.50 * (1 - Math.min(1, Math.abs(eA - eB) / eSpan));
        var hd = 0.55 * wLine, tl = 0.12 * wLine;
        lc[o] = cc[0] * hd; lc[o + 1] = cc[1] * hd; lc[o + 2] = cc[2] * hd;
        lc[o + 3] = cc[0] * tl; lc[o + 4] = cc[1] * tl; lc[o + 5] = cc[2] * tl;
        lCount++;
      }
      baseL = lp.slice(); revSeen = -1;
      lGeo = new T.BufferGeometry();
      lGeo.setAttribute('position', new T.BufferAttribute(lp, 3));
      lGeo.setAttribute('color', new T.BufferAttribute(lc, 3));
      if (lGeo.setDrawRange) lGeo.setDrawRange(0, lCount * 2);
      lMat = new T.LineBasicMaterial({
        vertexColors: true, transparent: true, opacity: 0,
        blending: T.AdditiveBlending, depthWrite: false
      });
      lines = new T.LineSegments(lGeo, lMat);
      lines.raycast = function () {};
      lines.userData = { clPickable: false, clLayer: 'tree-clone-links', clTree: true };
      lines.frustumCulled = false;
      group.add(lines);
    } else { baseL = null; }

    st.clones = n; st.lines = lCount; st.dupNames = 0; st.maxPerName = 0;
    for (var k in perName) {
      st.dupNames++;
      if (perName[k] > st.maxPerName) st.maxPerName = perName[k];
    }
    built = true;
    return true;
  }

  function setOn(v) { on = v === true; }
  function show(v) { force = (v == null) ? null : !!v; }
  function visible() { return !!(group && group.visible); }

  function onPlotline(e) { setOn(e && e.detail ? e.detail.on === true : false); }
  function bind() {
    if (bound) return;
    document.addEventListener('cl:tree-plotline', onPlotline);
    bound = true;
  }
  function unbind() {
    if (!bound) return;
    document.removeEventListener('cl:tree-plotline', onPlotline);
    bound = false;
  }

  function build(o) {
    o = o || {};
    big = !!o.big;
    if (o.degrade != null) degrade = o.degrade | 0;
    bind();
    return rebuild();
  }

  function update(s) {
    s = s || {};
    if (!built && ++tick >= 30) { tick = 0; rebuild(); }
    if (s.degrade != null && (s.degrade | 0) !== degrade) {
      degrade = s.degrade | 0;
      if (built) rebuild();
    }
    var mig = (window.CLStarMigrate && CLStarMigrate.state) ? CLStarMigrate.state() : null;
    var want = (force != null ? force : on) && built &&
      (!mig || mig === 'plot' || mig === 'flying') && s.on !== 0 && degrade < 2;
    target = want ? 1 : 0;

    var dt = 1 / 60, d;
    if (typeof s.dt === 'number' && isFinite(s.dt) && s.dt > 0 && s.dt < 0.5) dt = s.dt;
    else if (typeof s.t === 'number' && isFinite(s.t) && lastT >= 0 &&
             (d = s.t - lastT) > 0 && d < 0.5) dt = d;
    if (typeof s.t === 'number' && isFinite(s.t)) lastT = s.t;

    if (level < target) { level += dt / FADE; if (level > target) level = target; }
    else if (level > target) { level -= dt / FADE; if (level < target) level = target; }

    if (!group) return;
    /* v36：逐点跟上摇曳。放在可见性判断之前 —— 否则「刚被点开的那一帧」会先亮出
     * 上一姿态的旧点位，下一帧才追上（一闪）。 */
    refreshSway();
    var breath = 1;
    if (!reduced()) {
      var beat = (typeof s.beat === 'number' && isFinite(s.beat)) ? s.beat
        : 0.5 + 0.5 * Math.sin((typeof s.t === 'number' && isFinite(s.t) ? s.t : 0) * 0.3);
      breath = 0.82 + 0.18 * beat;
    }
    if (pMat) pMat.opacity = level * breath;
    if (lMat) lMat.opacity = 0.16 * Math.min(1, Math.sqrt(60 / Math.max(1, lCount))) * level * breath;
    group.visible = level > 0.002;
  }

  function dispose() {
    unbind();
    killGeo();
    if (group) {
      if (group.parent && group.parent.remove) group.parent.remove(group);
      group = null;
    }
    if (tex) { tex.dispose(); tex = null; }
    built = on = false; force = null;
    level = target = tick = 0; lastT = -1;
  }

  function state() {
    return st.state || (built ? (st.clones > 0 ? 'ready' : 'empty') : 'empty');
  }

  function stats() {
    return {
      ready: built, state: state(), reason: st.reason || '', on: level, clones: st.clones, lines: st.lines,
      dupNames: st.dupNames, maxPerName: st.maxPerName,
      drawcalls: built ? (st.clones > 0 ? 1 : 0) + (st.lines > 0 && degrade < 1 ? 1 : 0) : 0,
      degrade: degrade, muted: reduced()
    };
  }

  var API = {
    name: 'cast-clones', build: build, update: update, dispose: dispose,
    setOn: setOn, rebuild: rebuild, show: show, visible: visible, state: state, stats: stats
  };

  bind();

  window.CLCastClones = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
