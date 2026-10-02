/*!
 * @role component
 * @owns js/sky/sky-constellation-preview.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 *
 * A temporary reading lens for the sky tug gesture.  A short pull is enough to
 * unfold the selected character's connected stars into a quiet right-hand
 * constellation.  It only reads CLSkyTug / skyView; the real stars keep their
 * home coordinates and are therefore restored by the tug host automatically.
 */
(function (g) {
  'use strict';
  var d = g.document, NS = 'http://www.w3.org/2000/svg', root = null, svg = null;
  var scene = null, offFrame = null, offTug = null, model = null, shown = false, opened = false;
  var closing = 0, threshold = 0.055, lastT = 0, reduce = false;
  var W = 360, H = 342, cx = 180, cy = 166;

  function el(tag, cls, parent) { var n = d.createElement(tag); if (cls) n.className = cls; if (parent) parent.appendChild(n); return n; }
  function se(tag, cls, parent) { var n = d.createElementNS(NS, tag); if (cls) n.setAttribute('class', cls); if (parent) parent.appendChild(n); return n; }
  function attr(n, k, v) { n.setAttribute(k, String(v)); return n; }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]; }); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function hex(n) { var T = g.CLSkyTokens, x = T && T.hexCss ? T.hexCss(n) : '#c9c5ff'; return x; }
  function app() { return g.CLApp || null; }
  function skyView() { var A = app(), v = A && A.atlas && A.atlas.skyView ? A.atlas.skyView() : A && A.graph ? A.graph() : null; return v || { relations: [], characters: [] }; }
  function currentScene() { return g.CLScene && g.CLScene.current || null; }
  function live(name) { var n = scene && scene.nodeOf ? scene.nodeOf('c:' + name) : null; return !!(n && n.kind === 'char' && n.g); }
  function relationList(name) {
    var v = skyView(), rs = v.relations || [], out = [], seen = {}, i, r, other, s;
    for (i = 0; i < rs.length; i++) {
      r = rs[i] || {};
      other = r.a === name ? r.b : r.b === name ? r.a : null;
      if (!other || other === name || seen[other] || !live(other)) continue;
      seen[other] = 1; s = isFinite(+r.strength) ? clamp(+r.strength, 0.12, 1) : 0.5;
      out.push({ name: other, strength: s, kind: String(r.kind || (r.derived ? '同场' : '联系')), line: String(r.line || ''), derived: !!r.derived, desc: String(r.desc || '') });
    }
    out.sort(function (a, b) { return b.strength - a.strength || a.name.localeCompare(b.name); });
    return out.slice(0, 42);
  }
  function campColor(name, i) {
    var n = scene && scene.nodeOf ? scene.nodeOf('c:' + name) : null, T = g.CLSkyTokens, c = T && T.C ? T.C.STAR_COOL : 0xcfe0ff;
    try { if (T && T.groupHex) c = T.groupHex(n && n.camp || '', i || 0); } catch (_) {}
    return hex(c);
  }
  function relColor(kind) { var T = g.CLSkyTokens, c = T && T.relHex ? T.relHex(kind) : 0x9d94c8; return hex(c); }
  function layout(count) {
    var a = [], i, n, ring, ringCount, r, start, step;
    if (!count) return a;
    for (i = 0; i < count; i++) {
      if (count <= 7) { r = 112; n = count; start = -Math.PI / 2; }
      else { ring = i < Math.ceil(count * 0.42) ? 0 : 1; ringCount = ring ? count - Math.ceil(count * 0.42) : Math.ceil(count * 0.42); n = ringCount; r = ring ? 132 : 91; start = ring ? -Math.PI / 2 + 0.18 : -Math.PI / 2 - 0.08; }
      step = Math.PI * 2 / Math.max(1, n);
      var j = ring ? i - Math.ceil(count * 0.42) : i;
      a.push({ x: cx + r * Math.cos(start + j * step), y: cy + r * Math.sin(start + j * step), r: ring ? 6.2 : 7.2 });
    }
    return a;
  }
  function title(name, count) {
    var n = root.querySelector('.scp-title'), m = root.querySelector('.scp-meta');
    if (n) n.textContent = '关系星座 · ' + name;
    if (m) m.textContent = count ? count + ' 个有联系的角色 · 仅供临时观测' : '未发现直接联系 · 仍可回到原位';
  }
  function build(name) {
    scene = currentScene();
    var rels = relationList(name), all = [{ name: name, strength: 1, kind: '观测中心', line: '', main: true }].concat(rels), pos = layout(rels.length), T = g.CLSkyTokens, i, p, gN, c, e, label, halo;
    model = { name: name, rels: rels, all: all };
    clear(svg);
    var defs = se('defs', null, svg), grad = se('radialGradient', 'scp-core-grad', defs), stop;
    attr(grad, 'id', 'scpCoreGrad'); attr(grad, 'cx', '50%'); attr(grad, 'cy', '50%');
    stop = se('stop', null, grad); attr(stop, 'offset', '0%'); attr(stop, 'stop-color', '#fff4cb'); attr(stop, 'stop-opacity', '.94');
    stop = se('stop', null, grad); attr(stop, 'offset', '34%'); attr(stop, 'stop-color', '#d5c6ff'); attr(stop, 'stop-opacity', '.54');
    stop = se('stop', null, grad); attr(stop, 'offset', '100%'); attr(stop, 'stop-color', '#6f5fd0'); attr(stop, 'stop-opacity', '0');
    var grid = se('g', 'scp-grid', svg); attr(grid, 'aria-hidden', 'true');
    [56, 106, 148].forEach(function (r) { var q = se('circle', null, grid); attr(q, 'cx', cx); attr(q, 'cy', cy); attr(q, 'r', r); });
    var links = se('g', 'scp-links', svg), stars = se('g', 'scp-stars', svg);
    for (i = 0; i < rels.length; i++) {
      p = pos[i]; e = se('path', 'scp-link', links); attr(e, 'd', 'M' + cx.toFixed(1) + ' ' + cy.toFixed(1) + ' Q' + ((cx + p.x) / 2 + (i % 2 ? 7 : -7)).toFixed(1) + ' ' + ((cy + p.y) / 2 - 7).toFixed(1) + ' ' + p.x.toFixed(1) + ' ' + p.y.toFixed(1));
      attr(e, 'stroke', relColor(rels[i].kind)); attr(e, 'style', '--scp-delay:' + (i * 0.035).toFixed(3) + 's;--scp-strength:' + rels[i].strength.toFixed(3));
    }
    gN = se('g', 'scp-node scp-node-main', stars); attr(gN, 'transform', 'translate(' + cx + ' ' + cy + ')');
    halo = se('circle', 'scp-halo', gN); attr(halo, 'r', 28); attr(halo, 'fill', 'url(#scpCoreGrad)');
    c = se('circle', 'scp-core', gN); attr(c, 'r', 12); attr(c, 'fill', 'url(#scpCoreGrad)');
    label = se('text', 'scp-label scp-label-main', gN); attr(label, 'y', 35); attr(label, 'text-anchor', 'middle'); label.textContent = name;
    for (i = 0; i < rels.length; i++) {
      p = pos[i]; gN = se('g', 'scp-node', stars); attr(gN, 'transform', 'translate(' + p.x.toFixed(1) + ' ' + p.y.toFixed(1) + ')'); attr(gN, 'style', '--scp-delay:' + (i * 0.035).toFixed(3) + 's;--scp-color:' + campColor(rels[i].name, i));
      halo = se('circle', 'scp-halo', gN); attr(halo, 'r', (p.r * 2.8).toFixed(1));
      c = se('circle', 'scp-dot', gN); attr(c, 'r', p.r); attr(c, 'fill', 'var(--scp-color)');
      label = se('text', 'scp-label', gN); attr(label, 'y', p.r + 15); attr(label, 'text-anchor', 'middle'); label.textContent = rels[i].name;
      var sub = se('text', 'scp-sub', gN); attr(sub, 'y', p.r + 27); attr(sub, 'text-anchor', 'middle'); sub.textContent = rels[i].kind + ' · ' + Math.round(rels[i].strength * 100) + '%';
    }
    title(name, rels.length);
  }
  function mount() {
    if (root) return;
    root = el('aside', 'scp-panel', d.body); root.id = 'skyConstellationPeek'; root.setAttribute('aria-live', 'polite');
    var head = el('div', 'scp-head', root), eyebrow = el('span', 'scp-eyebrow', head); eyebrow.textContent = 'TEMPORARY ORBIT · 01';
    el('strong', 'scp-title', head); el('span', 'scp-meta', head);
    var wrap = el('div', 'scp-figure', root); svg = d.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', '临时关系星座'); wrap.appendChild(svg);
    var hint = el('div', 'scp-hint', root); hint.textContent = '轻拖星点 · 展开关联星座';
    var foot = el('div', 'scp-foot', root); foot.textContent = '松手后星点自动回到原位';
    reduce = !!(g.CLSkyUtil && g.CLSkyUtil.reduced && g.CLSkyUtil.reduced());
  }
  function reveal(name) {
    mount(); clearTimeout(closing); shown = true; opened = false; root.classList.remove('is-closing', 'is-open'); root.classList.add('is-dragging'); build(name); root.hidden = false;
  }
  function openConstellation() { if (!root || opened || !model) return; opened = true; root.classList.add('is-open'); }
  function hide(immediate) {
    if (!root) return; shown = opened = false; root.classList.remove('is-dragging', 'is-open'); root.classList.add('is-closing');
    clearTimeout(closing); closing = setTimeout(function () { if (!shown && root) { root.hidden = true; root.classList.remove('is-closing'); } }, immediate ? 0 : 520);
  }
  function frame(dt, _a, tAnim, _calm, _deg) {
    if (!shown || !root) return;
    var tug = g.CLSkyTug, st = tug && tug.state ? tug.state() : null, t = st ? +st.tension || 0 : 0;
    if (!st || !st.on || !model || st.name !== model.name) { hide(true); return; }
    root.style.setProperty('--scp-tension', clamp(t / 0.24, 0, 1).toFixed(3));
    if (!opened && t >= threshold) openConstellation();
    var p = clamp((t - threshold) / 0.12, 0, 1); root.style.setProperty('--scp-progress', p.toFixed(3));
    if (!reduce && svg) svg.style.setProperty('--scp-time', String(tAnim || lastT)); lastT = tAnim || lastT;
  }
  function onTug(e) {
    if (!e) return;
    if (e.type === 'grab') reveal(e.name || String(e.key || '').replace(/^c:/, ''));
    else if (e.type === 'release') hide(false);
    else if (e.type === 'sleep') hide(true);
  }
  function attach() {
    var s = currentScene(); if (!s || !s.registerFrameHook) return;
    if (scene !== s) { scene = s; if (offFrame) offFrame(); offFrame = s.registerFrameHook(frame); }
    if (!offTug && g.CLSkyTug && g.CLSkyTug.on) offTug = g.CLSkyTug.on(onTug);
  }
  function reset() { hide(true); model = null; if (offFrame) { offFrame(); offFrame = null; } scene = null; attach(); }
  ['cl:graph-loading', 'cl:graph-ready', 'cl:sky-plot', 'cl:sky-compass', 'cl:atlas-view'].forEach(function (eventName) {
    d.addEventListener(eventName, function () { reset(); }, false);
  });
  d.addEventListener('click', function (e) { if (shown && e.target !== root && root && !root.contains(e.target) && !(e.target && e.target.tagName === 'CANVAS')) hide(true); }, true);
  g.addEventListener('resize', function () { hide(true); }, false);
  attach();
  g.CLSkyConstellationPreview = { reset: reset, hide: hide, stats: function () { return { mounted: !!root, visible: shown, open: opened, name: model && model.name || null, related: model ? model.rels.length : 0, threshold: threshold }; } };
})(window);
