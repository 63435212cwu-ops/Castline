/**
 * @role component
 * @owns js/gem/gem-svg.js
 * @budget dom<=160; js_ms<=1.0
 * @contract v80-W3
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var W = 400, CX = 200;
  var svg = null, host = null, M = null, faces = [], axisOn = null, scope = 'book', peer = null;
  var R = 92, GAP = 44, OUT = 22, VR = 3.5, VRLO = 2, DUR = 420;
  var reduced = false, low = false, paused = false;
  var morph = window.CLGemMorph.create({ draw: drawCur, dur: function () { env(); return reduced || low || paused ? 0 : DUR; } });

  function mk(tag, cls, parent) {
    var n = document.createElementNS(NS, tag);
    if (cls) n.setAttribute('class', cls);
    if (parent) parent.appendChild(n);
    return n;
  }
  function attr(n, k, v) { n.setAttribute(k, String(v)); }
  function tok(name, fb) {
    try {
      var v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
      if (isFinite(v) && v > 0) return v;
    } catch (e) {}
    return fb;
  }
  function env() {
    reduced = false; low = false;
    try { reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
    try { low = !!(window.CLOrbit3DTier && window.CLOrbit3DTier.get() === 'low'); } catch (e2) {}
    if (navigator.hardwareConcurrency <= 4) low = true;
  }
  function f1(v) { return Math.round(v * 10) / 10; }
  function ang(i) { return -Math.PI / 2 + i * Math.PI / 4; }
  function pt(cy, i, k) { var a = ang(i); return [CX + Math.cos(a) * R * k, cy + Math.sin(a) * R * k]; }
  function poly(cy, k) {
    var s = '', i, p;
    for (i = 0; i < 8; i++) { p = pt(cy, i, k); s += (i ? 'L' : 'M') + f1(p[0]) + ' ' + f1(p[1]); }
    return s + 'Z';
  }
  function ringPath(cy, vals) {
    var s = '', i, p, open = true, all = true, k;
    for (i = 0; i < 8; i++) if (vals[i] == null) { all = false; break; }
    for (i = 0; i < 8; i++) {
      k = vals[i];
      if (k == null) { open = true; continue; }
      p = pt(cy, i, k / 100);
      s += (open ? 'M' : 'L') + f1(p[0]) + ' ' + f1(p[1]);
      open = false;
    }
    if (all) s += 'Z';
    else if (vals[0] != null && vals[7] != null) { p = pt(cy, 0, vals[0] / 100); s += 'L' + f1(p[0]) + ' ' + f1(p[1]); }
    return s;
  }
  function fanPath(cy, vals) {
    var s = '', i, j, p, run = [], start = 0;
    function flush() {
      if (run.length < 2) { run = []; return; }
      s += 'M' + CX + ' ' + f1(cy);
      for (j = 0; j < run.length; j++) { p = pt(cy, run[j], vals[run[j]] / 100); s += 'L' + f1(p[0]) + ' ' + f1(p[1]); }
      s += 'Z'; run = [];
    }
    for (i = 0; i < 8; i++) if (vals[i] == null) { start = i + 1; break; }
    if (i === 8) return ringPath(cy, vals);
    for (i = 0; i < 8; i++) { j = (start + i) % 8; if (vals[j] == null) flush(); else run.push(j); }
    flush();
    return s;
  }
  function bandPath(cy, lo, hi) {
    var i, ok = true;
    for (i = 0; i < 8; i++) if (lo[i] == null || hi[i] == null) ok = false;
    return ok ? ringPath(cy, hi) + ringPath(cy, lo) : '';
  }
  function anchorOf(i) { var c = Math.cos(ang(i)); return c > 0.3 ? 'start' : (c < -0.3 ? 'end' : 'middle'); }
  function txt(parent, cls, s) { var t = mk('tspan', cls, parent); t.textContent = s; return t; }

  function buildFace(kind, cy, dims, title) {
    var g = mk('g', 'cl-gem-face', svg), i, d, p, hit = ' is-hit' + (kind === 'attr' ? ' rd-vert' : ''), F = { kind: kind, cy: cy, g: g, dims: dims, verts: [], badges: [], axes: [], deltas: [] };
    attr(g, 'data-face', kind);
    var t = mk('text', 'cl-gem-title', g); attr(t, 'x', 14); attr(t, 'y', f1(cy - R - OUT - 22)); t.textContent = title;
    for (i = 1; i <= 4; i++) attr(mk('path', 'cl-gem-grid' + (i === 4 ? ' is-outer' : ''), g), 'd', poly(cy, i / 4));
    for (i = 0; i < 8; i++) {
      d = dims[i]; p = pt(cy, i, 1);
      var ax = mk('line', 'cl-gem-axis' + (d.known ? '' : ' is-unknown'), g);
      attr(ax, 'x1', CX); attr(ax, 'y1', f1(cy)); attr(ax, 'x2', f1(p[0])); attr(ax, 'y2', f1(p[1])); attr(ax, 'data-key', d.key);
      F.axes.push(ax);
    }
    F.band = mk('path', 'cl-gem-band', g); attr(F.band, 'fill-rule', 'evenodd');
    F.gBook = mk('path', 'cl-gem-ghost is-book', g);
    F.gCamp = mk('path', 'cl-gem-ghost is-camp', g);
    F.fill = mk('path', 'cl-gem-fill', g); attr(F.fill, 'data-face', kind);
    F.poly = mk('path', 'cl-gem-poly', g); attr(F.poly, 'data-face', kind);
    /* 电影级流光独立于数据轮廓：保持主轮廓连续清晰，只让一小段
     * 高亮沿当前晶面缓慢行进。它复用同一 d，不增加任何几何计算，
     * 也不会把未知轴补成假数据。 */
    F.sheen = mk('path', 'cl-gem-sheen', g); attr(F.sheen, 'data-face', kind);
    F.peer = mk('path', 'cl-gem-peer', g);
    for (i = 0; i < 8; i++) {
      d = dims[i];
      var v = mk('circle', 'cl-gem-vertex' + hit, g);
      attr(v, 'data-key', d.key); attr(v, 'data-axis', d.key); attr(v, 'r', VR);
      F.verts.push(v);
      p = pt(cy, i, 1 + OUT / R);
      var b = mk('text', 'cl-gem-badge' + hit, g);
      attr(b, 'x', f1(p[0])); attr(b, 'y', f1(p[1] + 4)); attr(b, 'text-anchor', anchorOf(i)); attr(b, 'data-key', d.key); attr(b, 'data-axis', d.key);
      attr(b, 'tabindex', 0); attr(b, 'role', 'button');
      b.__n = txt(b, 'cl-gem-axisname', d.key); b.__v = txt(b, 'cl-gem-badge__v', ''); b.__r = txt(b, 'cl-gem-badge__r', '');
      attr(b.__v, 'dx', 4); attr(b.__r, 'dx', 3);
      F.badges.push(b);
      p = pt(cy, i, 1 - 16 / R);
      var dl = mk('text', 'cl-gem-delta', g);
      attr(dl, 'x', f1(p[0])); attr(dl, 'y', f1(p[1] + 3)); attr(dl, 'text-anchor', 'middle'); attr(dl, 'data-key', d.key);
      F.deltas.push(dl);
    }
    F.na = mk('text', 'cl-gem-na', g); attr(F.na, 'x', CX); attr(F.na, 'y', f1(cy)); attr(F.na, 'text-anchor', 'middle');
    return F;
  }
  function vals(dims) { var a = [], i; for (i = 0; i < 8; i++) a.push(dims[i] && dims[i].known ? dims[i].score : null); return a; }
  function paintFace(F, dims, ghost, band, pr, ready) {
    var i, d, v, p, cy = F.cy, vs = vals(dims), hit = ' is-hit' + (F.kind === 'attr' ? ' rd-vert' : '');
    F.dims = dims;
    F.cur = F.cur || vs.slice(0);
    F.target = vs;
    F.g.classList[ready ? 'remove' : 'add']('is-na');
    F.na.textContent = ready ? '' : (F.kind === 'meta' ? '叙事八维未就绪' : '八维待建档');
    for (i = 0; i < 8; i++) {
      d = dims[i]; v = F.verts[i];
      attr(v, 'class', 'cl-gem-vertex' + hit + (d.known ? (d.conf === 'low' ? ' is-low' : '') : ' is-unknown') + (axisOn === d.key ? ' is-hot' : ''));
      attr(v, 'r', d.known ? (d.conf === 'low' ? VRLO : VR) : VR);
      if (d.known) attr(v, 'data-score', Math.round(d.score)); else v.removeAttribute('data-score');
      var b = F.badges[i];
      attr(b, 'class', 'cl-gem-badge' + hit + (d.known ? '' : ' is-unknown'));
      b.__v.textContent = d.known ? String(Math.round(d.score)) : '—';
      attr(b, 'aria-label', d.key + (d.known ? ' ' + Math.round(d.score) + '，查看依据' : ' 待建档，查看依据'));
      b.__r.textContent = (d.known && d.rank != null && d.n != null) ? ('#' + d.rank + '/' + d.n) : '';
      attr(F.axes[i], 'class', 'cl-gem-axis' + (d.known ? '' : ' is-unknown') + (axisOn === d.key ? ' is-on' : ''));
      var dl = F.deltas[i], dv = pr && pr.delta ? pr.delta[i] : null;
      if (pr && d.known) {
        dl.textContent = dv == null ? '—' : (dv > 0 ? '+' + Math.round(dv) : (dv < 0 ? '−' + Math.round(-dv) : '0'));
        attr(dl, 'class', 'cl-gem-delta ' + (dv > 0 ? 'is-up' : (dv < 0 ? 'is-down' : 'is-flat')));
      } else { dl.textContent = ''; attr(dl, 'class', 'cl-gem-delta'); }
    }
    attr(F.gBook, 'd', ghost && ghost.book ? ringPath(cy, ghost.book) : '');
    attr(F.gCamp, 'd', ghost && ghost.camp ? ringPath(cy, ghost.camp) : '');
    attr(F.gBook, 'class', 'cl-gem-ghost is-book' + (scope === 'book' ? ' is-lit' : ''));
    attr(F.gCamp, 'class', 'cl-gem-ghost is-camp' + (scope === 'camp' ? ' is-lit' : ''));
    attr(F.band, 'd', band && band.lo && band.hi ? bandPath(cy, band.lo, band.hi) : '');
    attr(F.peer, 'd', pr && pr.attr ? ringPath(cy, pr.attr) : '');
    if (reduced || low || paused || !F.cur.length || DUR <= 0) { F.cur = vs.slice(0); drawCur(F); }
    else drawCur(F);
  }
  function drawCur(F) {
    var i, p, cy = F.cy, cur = F.cur;
    var d = ringPath(cy, cur);
    attr(F.poly, 'd', d);
    attr(F.sheen, 'd', d);
    attr(F.fill, 'd', fanPath(cy, cur));
    for (i = 0; i < 8; i++) {
      p = pt(cy, i, cur[i] == null ? 1 : cur[i] / 100);
      attr(F.verts[i], 'cx', f1(p[0])); attr(F.verts[i], 'cy', f1(p[1]));
    }
  }
  function onClick(ev) {
    if (ev.type === 'keydown' && ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar') return;
    var n = ev.target, key = null;
    while (n && n !== svg) { if (n.getAttribute && n.getAttribute('data-key') && / is-hit/.test(' ' + n.getAttribute('class'))) { key = n.getAttribute('data-key'); break; } n = n.parentNode; }
    if (!key) return;
    if (ev.type === 'keydown' && ev.preventDefault) ev.preventDefault();
    setAxis(axisOn === key ? null : key);
    if (!axisOn && n.classList.contains('rd-vert')) n.classList.add('on');
    try { document.dispatchEvent(new CustomEvent('cl:radar-axis-select', { detail: { key: axisOn, axis: axisOn }, bubbles: true })); } catch (e) {}
  }
  function paint() {
    if (!M || !svg) return;
    var unverifiedStage = M.stage && M.stage.hasQuantified && !M.stage.verified;
    env(); DUR = reduced || low || paused || unverifiedStage ? 0 : tok('--cl-gem-dur-morph', 420);
    if (reduced || low || paused || unverifiedStage) morph.cancel();
    paintFace(faces[0], M.attr, M.ghost, M.band, peer, M.scoredCount > 0);
    if (faces[1]) paintFace(faces[1], M.meta || emptyDims(), null, null, null, !!M.metaReady);
    if (!reduced && !low && !paused && !unverifiedStage) morph.start(faces);
    syncBreath();
    attr(svg, 'data-scored', M.scoredCount || 0);
    if (M.mean != null) attr(svg, 'data-average', Math.round(M.mean)); else svg.removeAttribute('data-average');
    attr(svg, 'class', 'cl-gem' + (axisOn ? ' is-axis' : ''));
  }
  function emptyDims() {
    var a = [], i, K = (window.CLRadarMeta && CLRadarMeta.KEYS) || ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
    for (i = 0; i < 8; i++) a.push({ key: K[i], known: false, score: null, conf: 'pending' });
    return a;
  }
  function mount(h, model) {
    unmount();
    host = h; M = model || null; if (!host || !M) return null;
    R = tok('--cl-gem-r', R); GAP = tok('--cl-gem-gap', GAP); OUT = tok('--cl-gem-badge-out', OUT);
    VR = tok('--cl-gem-vertex-r', VR); VRLO = tok('--cl-gem-vertex-r-lo', VRLO);
    var cy1 = R + OUT + 52, cy2 = cy1 + 2 * R + GAP, H = cy2 + R + OUT + 30;
    svg = mk('svg', 'cl-gem');
    attr(svg, 'viewBox', '0 0 ' + W + ' ' + f1(H)); attr(svg, 'width', '100%'); attr(svg, 'role', 'group'); attr(svg, 'aria-label', '八维双晶 · 属性轴可用回车选择依据');
    attr(svg, 'data-attrs', 8);
    faces = [buildFace('attr', cy1, M.attr, '属性八维 · ATTRIBUTES'), buildFace('meta', cy2, M.meta || emptyDims(), '叙事八维 · NARRATIVE')];
    peer = M.peer || null;
    host.appendChild(svg);
    svg.addEventListener('click', onClick, false);
    svg.addEventListener('keydown', onClick, false);
    paint();
    return svg;
  }
  function update(model) { if (!svg) return; M = model || M; peer = M.peer || null; paint(); }
  function setPeer(p) { peer = p || null; if (M) M.peer = peer; paint(); }
  var unsub = null, lastB = null;
  function onBreath(sn) {
    if (!svg || !axisOn || !sn || !isFinite(sn.breath)) return;
    env(); if (reduced || low || paused) { paint(); return; }
    lastB = sn.breath;
    var i, j, F, d, r;
    for (j = 0; j < faces.length; j++) { F = faces[j]; for (i = 0; i < 8; i++) { d = F.dims[i]; if (d.key === axisOn && d.known) { r = (d.conf === 'low' ? VRLO : VR) * (1 + 0.35 * sn.breath); attr(F.verts[i], 'r', f1(r)); } } }
  }
  function syncBreath() {
    var B = window.CLAbyssBreath;
    if (unsub) { try { unsub(); } catch (e) {} unsub = null; }
    if (axisOn && !reduced && !low && !paused && B && typeof B.subscribe === 'function') { try { unsub = B.subscribe(onBreath); } catch (e2) { unsub = null; } }
  }
  function setAxis(k) { axisOn = k || null; paint(); }
  function setScope(s) { scope = s === 'camp' ? 'camp' : 'book'; paint(); }
  function setPaused(value) { paused = !!value; paint(); return paused; }
  function step(ms) { morph.advance(typeof ms === 'number' && ms > 0 ? ms : 16); }
  function unmount() {
    if (svg) { svg.removeEventListener('click', onClick, false); svg.removeEventListener('keydown', onClick, false); if (svg.parentNode) svg.parentNode.removeChild(svg); }
    morph.cancel();
    if (unsub) { try { unsub(); } catch (e) {} unsub = null; }
    svg = null; host = null; faces = []; axisOn = null; peer = null;
  }
  function stats() {
    return { mounted: !!svg, faces: faces.length, axis: axisOn, scope: scope, peer: peer ? peer.name : null, breath: lastB, breathSub: !!unsub,
      animating: morph.active(), domNodes: svg ? svg.querySelectorAll('*').length : 0, reduced: reduced, low: low, paused: paused };
  }
  window.CLGemSVG = { name: 'gem-svg', version: 'v80', mount: mount, update: update, setPeer: setPeer, setAxis: setAxis,
    setScope: setScope, setPaused: setPaused, step: step, unmount: unmount, stats: stats };
})();
