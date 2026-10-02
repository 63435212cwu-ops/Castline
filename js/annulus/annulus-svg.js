/**
 * @role component
 * @owns js/annulus/annulus-svg.js
 * @budget js_ms<=2.5/frame(≤48pts/arc, trig cache); dom≈2×rings+defs/groups
 * @contract v80
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var GO = ['chapters', 'orphans', 'chords', 'arcs', 'heads', 'marks', 'labels', 'beads'];
  var MAX_STEP = 2.5 * Math.PI / 180;
  var MAX_PTS = 48, HEAD_PTS = 12, BREATH = 9400, FADE = 'cl-ann-fade-';
  var attached = false, layer = null, svg = null, defs = null;
  var A = null, view = null, groups = {}, items = [], plugins = [];
  var ctxObj = null, hover = null, focus = null;
  var breathMs = 0, jsMs = 0, frameCb = null;
  var tier = 'high', reduced = false, headLen = 26, notch = 7, trig = {};
  var planeProjection = null, projectionKey = null, layoutKey = null, geometryRevision = 0;
  var lastBreathValue = null;
  var cacheStats = { calibrationReads: 0, geometryPasses: 0, frozenFrames: 0 };

  function nowMs() {
    return (window.performance && typeof window.performance.now === 'function') ? window.performance.now() : 0;
  }
  function mk(tag, cls, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (parent) parent.appendChild(n);
    return n;
  }
  function mkSvg(tag, cls, parent) {
    var n = document.createElementNS(NS, tag);
    if (cls) n.setAttribute('class', cls);
    if (parent) parent.appendChild(n);
    return n;
  }
  function cosOf(a) {
    var k = 'c' + Math.round(a * 1e4), e = trig[k];
    if (!e) { e = { c: Math.cos(a), s: Math.sin(a) }; trig[k] = e; }
    return e;
  }
  function rawProject(x, y) {
    if (!view || typeof view.screenOf !== 'function') return null;
    var L = window.CLOrbit3DLayer;
    if (!L || typeof L.localToGroup !== 'function') return null;
    var loc = L.localToGroup(x, y, 0);
    if (!loc) return null;
    return view.screenOf(loc) || null;
  }
  /* 年轮所有图元都在同一 z=0 平面。四角真实投影确定一张精确的平面
   * 单应矩阵；这不是降采样，也不近似为仿射。避免每个星点反复递归更新
   * Three matrixWorld，镜头/透视/盘姿变化仍逐帧通过四个真实角点校准。 */
  function calibrateProjection() {
    var R = A && isFinite(A.R) && A.R > 0 ? A.R : 100;
    var corners = [[-R, -R], [R, -R], [R, R], [-R, R]], p = [], i, q;
    for (i = 0; i < corners.length; i++) {
      q = rawProject(corners[i][0], corners[i][1]); cacheStats.calibrationReads++;
      if (!q || !isFinite(q[0]) || !isFinite(q[1])) { planeProjection = null; projectionKey = null; return false; }
      p.push(q);
    }
    var key = String(R) + '|' + p.map(function (point) { return point[0] + ',' + point[1]; }).join('|');
    if (key === projectionKey) return false;
    projectionKey = key;
    var dx1 = p[1][0] - p[2][0], dx2 = p[3][0] - p[2][0];
    var dy1 = p[1][1] - p[2][1], dy2 = p[3][1] - p[2][1];
    var dx3 = p[0][0] - p[1][0] + p[2][0] - p[3][0];
    var dy3 = p[0][1] - p[1][1] + p[2][1] - p[3][1];
    var den = dx1 * dy2 - dx2 * dy1, g = 0, h = 0;
    if (Math.abs(dx3) + Math.abs(dy3) > 1e-12) {
      if (!isFinite(den) || Math.abs(den) < 1e-12) { planeProjection = null; return true; }
      g = (dx3 * dy2 - dx2 * dy3) / den;
      h = (dx1 * dy3 - dx3 * dy1) / den;
    }
    var pa = p[1][0] - p[0][0] + g * p[1][0], pb = p[3][0] - p[0][0] + h * p[3][0];
    var pd = p[1][1] - p[0][1] + g * p[1][1], pe = p[3][1] - p[0][1] + h * p[3][1], inv = 1 / (2 * R);
    // 预合成 local x/y→单位方形变换；每个投影点无需再做两次除法。
    planeProjection = { a: pa * inv, b: pb * inv, c: (pa + pb) * 0.5 + p[0][0],
      d: pd * inv, e: pe * inv, f: (pd + pe) * 0.5 + p[0][1], g: g * inv, h: h * inv, w: 1 + (g + h) * 0.5 };
    return true;
  }
  function projectXY(x, y) {
    var p = planeProjection;
    if (!p) return rawProject(x, y);
    var den = p.g * x + p.h * y + p.w;
    if (!isFinite(den) || Math.abs(den) < 1e-12) return rawProject(x, y);
    return [(p.a * x + p.b * y + p.c) / den, (p.d * x + p.e * y + p.f) / den];
  }
  function project(r, a) {
    var e = cosOf(a);
    return projectXY(r * e.c, r * e.s);
  }
  function geometryKey() {
    var parts = [projectionKey, headLen, notch], i, r;
    for (i = 0; i < items.length; i++) { r = items[i].ring; parts.push(r.r, r.a0, r.a1); }
    return parts.join('|');
  }
  function tokenPx(name, fb) {
    if (!layer || !window.getComputedStyle) return fb;
    var f = parseFloat(String(window.getComputedStyle(layer).getPropertyValue(name) || '').replace(/px\s*$/, ''));
    return isFinite(f) ? f : fb;
  }
  function detectEnv() {
    var low = (navigator.hardwareConcurrency || 8) <= 4;
    try {
      if (window.CLOrbit3DTier && typeof window.CLOrbit3DTier.get === 'function') low = window.CLOrbit3DTier.get() === 'low';
    } catch (e1) {}
    tier = low ? 'low' : 'high';
    reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function breathPhase() {
    /* W5 同拍：全局呼吸总线 snap().breath 已是 0..1（9.4 s 正弦）；phase() 的单位是「维」(0..8)，不能当 0..1 用 */
    var B = window.CLAbyssBreath;
    if (B && typeof B.snap === 'function') {
      try { var sn = B.snap(); if (sn && isFinite(sn.breath)) return Math.min(1, Math.max(0, sn.breath)); } catch (e) {}
    }
    return 0.5 + 0.5 * Math.sin((breathMs % BREATH) / BREATH * Math.PI * 2);
  }
  function applyBreath(b) {
    /* 活跃弧头的彗尾随总线呼吸（JS 逐帧写 opacity，替代 CSS 1.2 s 自转动画：同拍 + 可断言 + reduce 直落） */
    var i, it, v = String(Math.round((reduced ? 0.8 : (0.35 + 0.65 * b)) * 1000) / 1000);
    if (v === lastBreathValue) return;
    lastBreathValue = v;
    for (i = 0; i < items.length; i++) {
      it = items[i];
      if (it.lc === 'active' || it.lc === 'open') it.head.setAttribute('opacity', v);
    }
  }
  function setCls(n, c, on) {
    if (!n) return;
    if (on) n.classList.add(c); else n.classList.remove(c);
  }
  function lifeOf(r) {
    var lc = r.lifecycle || r.status || 'unknown';
    return (lc === 'active' || lc === 'resolved' || lc === 'suspended' || lc === 'open' || lc === 'unknown') ? lc : 'unknown';
  }
  function strokeOf(r) { return 'var(' + (r.colorVar || '--cl-ann-gen-5') + ')'; }
  function genOf(r) {
    var g = r.gen;
    if (g === null || g === undefined || !isFinite(g)) g = 5;
    g = g | 0;
    return g < 0 ? 0 : (g > 5 ? 5 : g);
  }
  function buildGradients() {
    var i, lg, s0, s1;
    for (i = 0; i < 6; i++) {
      lg = mkSvg('linearGradient', null, defs);
      lg.setAttribute('id', FADE + i);
      lg.setAttribute('gradientUnits', 'objectBoundingBox');
      lg.setAttribute('x1', '0'); lg.setAttribute('y1', '0');
      lg.setAttribute('x2', '1'); lg.setAttribute('y2', '0');
      s0 = mkSvg('stop', null, lg);
      s0.setAttribute('offset', '0');
      s0.setAttribute('stop-color', 'var(--cl-ann-gen-' + i + ')');
      s0.setAttribute('stop-opacity', '1');
      s1 = mkSvg('stop', null, lg);
      s1.setAttribute('offset', '1');
      s1.setAttribute('stop-color', 'var(--cl-ann-gen-' + i + ')');
      s1.setAttribute('stop-opacity', '0');
    }
  }
  function buildArcs() {
    var rings = (A && A.rings) || [], i, r, g, lc, arc, head, kc;
    for (i = 0; i < rings.length; i++) {
      r = rings[i];
      if (!r || !r.valid) continue;
      g = genOf(r); lc = lifeOf(r);
      kc = r.kind === 'main' ? 'is-main' : (r.kind === 'twig' ? 'is-twig' : 'is-branch');
      arc = mkSvg('path', 'cl-ann-arc is-hit ' + kc + ' is-' + lc, groups.arcs);
      arc.setAttribute('data-id', String(r.id));
      arc.setAttribute('data-kind', String(r.kind || 'branch'));
      arc.setAttribute('data-gen', String(g));
      arc.setAttribute('data-shade', String(r.shade || 0));
      arc.setAttribute('fill', 'none');
      arc.setAttribute('stroke', strokeOf(r));
      arc.setAttribute('d', '');
      head = mkSvg('path', 'cl-ann-head is-' + lc, groups.heads);
      head.setAttribute('data-id', String(r.id));
      head.setAttribute('data-gen', String(g));
      head.setAttribute('data-shade', String(r.shade || 0));
      head.setAttribute('fill', 'none');
      head.setAttribute('stroke', (lc === 'active' || lc === 'open') ? 'url(#' + FADE + g + ')' : strokeOf(r));
      head.setAttribute('d', '');
      items.push({ ring: r, gen: g, lc: lc, arc: arc, head: head, arcSamples: null, sampleKey: null, lastArc: '', lastHead: '' });
    }
  }
  function samplePoints(r, from, to, maxN) {
    var span = from - to, n, step, out = [], i, e;
    if (span < 0 || !isFinite(span)) return null;
    if (span === 0) {
      e = cosOf(from);
      var x = r * e.c, y = r * e.s, h = (A && A.R || r) * 0.0042;
      return [[x, y], [x - h, y], [x, y + h], [x + h, y], [x, y - h], [x - h, y], [x, y]];
    }
    n = Math.ceil(span / MAX_STEP) + 1;
    if (n > maxN) n = maxN;
    if (n < 2) n = 2;
    step = span / (n - 1);
    for (i = 0; i < n; i++) {
      e = cosOf(from - step * i); out.push([r * e.c, r * e.s]);
    }
    return out;
  }
  function pathOfSamples(samples) {
    if (!samples) return null;
    var d = '', any = false, i, p;
    for (i = 0; i < samples.length; i++) {
      p = projectXY(samples[i][0], samples[i][1]);
      if (!p) continue;
      d += (any ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      any = true;
    }
    return any ? d : null;
  }
  function pts(r, from, to, maxN) { return pathOfSamples(samplePoints(r, from, to, maxN)); }
  function headPath(it, headAng, notchW) {
    var r = it.ring, span = r.a0 - r.a1, p, p2;
    if (it.lc === 'resolved') {
      p = project(r.r, r.a1);
      p2 = project(r.r - notchW, r.a1);
      if (!p || !p2) return null;
      return 'M' + p[0].toFixed(1) + ' ' + p[1].toFixed(1) + 'L' + p2[0].toFixed(1) + ' ' + p2[1].toFixed(1);
    }
    if (it.lc === 'suspended') return pts(r.r, r.a1 + span * 0.2, r.a1, MAX_PTS);
    if (it.lc === 'active' || it.lc === 'open') {
      if (!(headAng > 0)) return null;
      return pts(r.r, r.a1, r.a1 - headAng, HEAD_PTS);
    }
    return null;
  }
  function refreshPaths() {
    if (!attached) return;
    var i, it, d, hd, rs, hAng, scale = 1;
    var rRef = (A && isFinite(A.R) && A.R > 0) ? A.R : 0;
    if (!rRef && items.length && isFinite(items[0].ring.r)) rRef = items[0].ring.r;
    if (rRef > 0) {
      var p0 = project(0, 0), p1 = project(rRef, 0);
      if (p0 && p1) {
        var dx = p1[0] - p0[0], dy = p1[1] - p0[1];
        var scr = Math.sqrt(dx * dx + dy * dy);
        if (isFinite(scr) && scr > 1) scale = scr / rRef;
      }
    }
    var notchW = notch / scale;
    for (i = 0; i < items.length; i++) {
      it = items[i];
      var sampleKey = [it.ring.r, it.ring.a0, it.ring.a1].join('|');
      if (sampleKey !== it.sampleKey) {
        it.sampleKey = sampleKey;
        it.arcSamples = samplePoints(it.ring.r, it.ring.a0, it.ring.a1, MAX_PTS);
      }
      d = pathOfSamples(it.arcSamples) || '';
      if (d !== it.lastArc) { it.arc.setAttribute('d', d); it.lastArc = d; }
      rs = it.ring.r * scale;
      hAng = rs > 1 ? headLen / rs : 0.06;
      hd = headPath(it, hAng, notchW);
      hd = hd || '';
      if (hd !== it.lastHead) { it.head.setAttribute('d', hd); it.lastHead = hd; }
    }
  }
  function ringById(id) {
    var rs = (A && A.rings) || [], i;
    for (i = 0; i < rs.length; i++) if (rs[i] && String(rs[i].id) === String(id)) return rs[i];
    return null;
  }
  function ensureCtx() {
    if (!ctxObj) {
      ctxObj = { svg: svg, groups: groups, A: A, view: view, project: project, ringById: ringById,
        projectXY: projectXY, geometryRevision: geometryRevision,
        hover: null, focus: null, breath: 0, tier: tier, reduced: reduced,
        far: !!(A && ((A.N > 120) || ((A.rings || []).length > 30))) };   /* 主控：大书 far LOD 旗子，插件据此减量 */
    } else {
      ctxObj.svg = svg; ctxObj.groups = groups; ctxObj.A = A; ctxObj.view = view;
      ctxObj.geometryRevision = geometryRevision;
      ctxObj.far = !!(A && ((A.N > 120) || ((A.rings || []).length > 30)));
    }
    return ctxObj;
  }
  function applyEmphasis() {
    var on = !!(hover || focus), i, it, id, f, h, dim;
    for (i = 0; i < items.length; i++) {
      it = items[i]; id = it.ring.id;
      f = on && focus !== null && String(focus) === String(id);   /* 主控：data-id 回来是字符串，ring.id 可能是数字 */
      h = on && hover !== null && String(hover) === String(id) && !f;
      dim = on && !f && !h;
      setCls(it.arc, 'is-focus', f); setCls(it.arc, 'is-hover', h); setCls(it.arc, 'is-dim', dim);
      setCls(it.head, 'is-focus', f); setCls(it.head, 'is-hover', h); setCls(it.head, 'is-dim', dim);
    }
    var L = window.CLOrbit3DLayer;
    if (L && typeof L.setAnnulusEmphasis === 'function') L.setAnnulusEmphasis(hover, focus);
  }
  function runFrame(frozenStep) {
    if (!attached) return;
    var t0 = nowMs(), i, c;
    calibrateProjection();
    var key = geometryKey(), changed = key !== layoutKey;
    if (changed) {
      layoutKey = key; geometryRevision++; cacheStats.geometryPasses++; refreshPaths();
    } else cacheStats.frozenFrames++;
    c = ensureCtx();
    var priorBreath = c.breath;
    c.geometryChanged = changed;
    c.frozenStep = !!frozenStep;
    c.hover = hover; c.focus = focus; c.tier = tier; c.reduced = reduced;
    /* Contract probes call step(0) to redraw only after a camera/selection
     * change.  A zero-duration step must not advance the ambient breath bus:
     * doing so rewrites every active arc head and defeats the frozen-frame
     * cache even when the projection and paths are unchanged.  Real view
     * frames (and positive-duration manual steps) keep the live breath. */
    c.breath = frozenStep && isFinite(priorBreath) ? priorBreath : breathPhase();
    if (!frozenStep) applyBreath(c.breath);
    for (i = 0; i < plugins.length; i++) if (typeof plugins[i].frame === 'function') plugins[i].frame(c);
    jsMs = nowMs() - t0;
  }
  function attach(v, model) {
    if (attached) detach();
    view = v || null; A = model || null;
    trig = {}; items = []; groups = {}; planeProjection = null; projectionKey = null; layoutKey = null; geometryRevision = 0; lastBreathValue = null;
    cacheStats = { calibrationReads: 0, geometryPasses: 0, frozenFrames: 0 };
    layer = mk('div', 'cl-ann-layer', document.body);
    svg = mkSvg('svg', 'cl-ann-svg', layer);
    defs = mkSvg('defs', null, svg);
    buildGradients();
    var gi;
    for (gi = 0; gi < GO.length; gi++) groups[GO[gi]] = mkSvg('g', 'cl-ann-g-' + GO[gi], svg);
    headLen = tokenPx('--cl-ann-head-len', 26);
    notch = tokenPx('--cl-ann-notch', 7);
    detectEnv();
    buildArcs();
    var L = window.CLOrbit3DLayer;
    if (L && typeof L.setAnnulus === 'function') L.setAnnulus(A);
    attached = true;
    document.body.classList.add('is-ann');
    calibrateProjection(); layoutKey = geometryKey(); geometryRevision++; cacheStats.geometryPasses++;
    refreshPaths();
    ensureCtx();
    if (view && typeof view.on === 'function') {
      frameCb = function () { runFrame(); };
      view.on('frame', frameCb);
    }
    var pi;
    for (pi = 0; pi < plugins.length; pi++) if (typeof plugins[pi].mount === 'function') plugins[pi].mount(ctxObj);
    applyEmphasis();
    return true;
  }
  function detach() {
    if (!attached) return;
    var i;
    for (i = plugins.length - 1; i >= 0; i--) if (typeof plugins[i].unmount === 'function') plugins[i].unmount();
    if (frameCb && view && typeof view.off === 'function') view.off('frame', frameCb);
    frameCb = null;
    if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    document.body.classList.remove('is-ann');
    var L = window.CLOrbit3DLayer;
    if (L && typeof L.setAnnulus === 'function') L.setAnnulus(null);
    layer = null; svg = null; defs = null; groups = {}; items = []; trig = {}; ctxObj = null;
    planeProjection = null; projectionKey = null; layoutKey = null; lastBreathValue = null;
    hover = null; focus = null; attached = false;
  }
  /* 主控补丁：导出表引用了 refresh 却未定义（加载即 ReferenceError）；语义 = 重探环境 + 重投影 + 重算强调 */
  function refresh() {
    if (!attached) return false;
    detectEnv(); headLen = tokenPx('--cl-ann-head-len', headLen); notch = tokenPx('--cl-ann-notch', notch);
    calibrateProjection(); layoutKey = geometryKey(); geometryRevision++; cacheStats.geometryPasses++; refreshPaths();
    var c = ensureCtx(), i; c.tier = tier; c.reduced = reduced;
    /* W1.5：档位/减动效变化要让插件重建（珠只留领衔、刻度减量），不只重投影 */
    for (i = 0; i < plugins.length; i++) {
      if (typeof plugins[i].refresh === 'function') plugins[i].refresh(c);
      else if (typeof plugins[i].unmount === 'function' && typeof plugins[i].mount === 'function') { plugins[i].unmount(); plugins[i].mount(c); }
    }
    applyEmphasis(); return true;
  }
  function step(ms) {
    var frozen = typeof ms === 'number' && isFinite(ms) && ms === 0;
    if (typeof ms === 'number' && isFinite(ms) && ms > 0) breathMs += ms;
    runFrame(frozen);
  }
  function use(plugin) {
    if (!plugin || typeof plugin.mount !== 'function') return;
    /* 角色珠先占位；文字读取本帧珠坐标后避让，不能互读上一帧形成追逐。 */
    if (plugin.name === 'marks') plugins.unshift(plugin); else plugins.push(plugin);
    if (attached && ctxObj) plugin.mount(ctxObj);
  }
  function setId(id) {
    return (id === undefined || id === null || id === '') ? null : id;
  }
  function stats() {
    var names = [], i;
    for (i = 0; i < plugins.length; i++) names.push(plugins[i].name || 'anon');
    return { arcs: items.length, totalLines: A && A.aggregate ? A.aggregate.raw : items.length, aggregatedLines: A && A.aggregate ? A.aggregate.aggregated : 0, hover: hover, focus: focus, breath: ctxObj ? ctxObj.breath : null,
      jsMs: Math.round(jsMs * 100) / 100, plugins: names,
      projection: { calibrationReads: cacheStats.calibrationReads, geometryPasses: cacheStats.geometryPasses, frozenFrames: cacheStats.frozenFrames, revision: geometryRevision },
      domNodes: layer ? layer.querySelectorAll('*').length : 0 };   /* W1.5：契约 §6 dom 预算可断言 */
  }
  window.CLAnnulusSVG = {
    name: 'annulus-svg', version: 'v80',
    attach: attach, detach: detach, step: step, refresh: refresh, use: use,
    setHover: function (id) { hover = setId(id); applyEmphasis(); },
    setFocus: function (id) { focus = setId(id); applyEmphasis(); },
    ctx: function () { return ctxObj; },
    stats: stats
  };
})();
