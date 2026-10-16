(function (g) {
  'use strict';
  var d = g.document, NS = 'http://www.w3.org/2000/svg', root = null, svg = null;
  var scene = null, offFrame = null, offTug = null, model = null, shown = false, opened = false;
  var closing = 0, threshold = 0.055, reduce = false, phase = 'idle';
  var progress = 0, age = 0, closeAge = 0, closeFrom = 0, lastDraw = '', hint = null;
  var followX = 0, followY = 0, screenA = null, screenB = null, canvasRect = null;
  var W = 360, H = 342, cx = 180, cy = 166;

  function el(tag, cls, parent) { var n = d.createElement(tag); if (cls) n.className = cls; if (parent) parent.appendChild(n); return n; }
  function se(tag, cls, parent) { var n = d.createElementNS(NS, tag); if (cls) n.setAttribute('class', cls); if (parent) parent.appendChild(n); return n; }
  function attr(n, k, v) { n.setAttribute(k, String(v)); return n; }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function ease(v) { return 1 - Math.pow(1 - clamp(v, 0, 1), 3); }
  function motionReduced() { var U = g.CLSkyUtil; return !!(U && U.reduced ? U.reduced() : g.CLSkyTokens && g.CLSkyTokens.reduced()); }
  function hex(n) { var T = g.CLSkyTokens, x = T && T.hexCss ? T.hexCss(n) : '#c9c5ff'; return x; }
  function app() { return g.CLApp || null; }
  function skyView() { var A = app(), v = A && A.atlas && A.atlas.skyView ? A.atlas.skyView() : A && A.graph ? A.graph() : null; return v || { relations: [], characters: [] }; }
  function currentScene() { return g.CLScene && g.CLScene.current || null; }
  function live(name) { var n = scene && scene.nodeOf ? scene.nodeOf('c:' + name) : null; return !!(n && n.kind === 'char' && n.render !== false && n.g && n.g.visible !== false); }
  function relationList(name) {
    var v = skyView(), rs = v.relations || [], out = [], seen = Object.create(null), i, r, other, s, item;
    for (i = 0; i < rs.length; i++) {
      r = rs[i] || {};
      other = r.a === name ? r.b : r.b === name ? r.a : null;
      if (!other || other === name || !live(other)) continue;
      s = isFinite(+r.strength) ? clamp(+r.strength, 0.12, 1) : 0.5;
      item = { name: other, strength: s, kind: String(r.kind || (r.derived ? '同场' : '联系')), line: String(r.line || ''), derived: !!r.derived, desc: String(r.desc || '') };
      if (!seen[other]) { seen[other] = item; out.push(item); }
      else if (s > seen[other].strength) { out[out.indexOf(seen[other])] = item; seen[other] = item; }
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
    var rels = relationList(name), pos = layout(rels.length), i, p, gN, c, e, flow, label, halo, caption;
    model = { name: name, rels: rels, nodes: [] };
    lastDraw = ''; canvasRect = scene && scene.renderer ? scene.renderer.domElement.getBoundingClientRect() : null;
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
      p = pos[i]; e = se('path', 'scp-link', links); attr(e, 'pathLength', 1);
      attr(e, 'stroke', relColor(rels[i].kind)); e.style.setProperty('--scp-strength', rels[i].strength.toFixed(3));
      flow = se('path', 'scp-link-flow', links); attr(flow, 'stroke', relColor(rels[i].kind));
      flow.style.setProperty('--scp-delay', (-i * 0.7).toFixed(2) + 's');
      model.nodes.push({ x: p.x, y: p.y, bend: i % 2 ? 9 : -9, link: e, flow: flow,
        delay: i / Math.max(1, rels.length - 1) * 0.28 });
    }
    gN = se('g', 'scp-node scp-node-main', stars); attr(gN, 'transform', 'translate(' + cx + ' ' + cy + ')');
    halo = se('circle', 'scp-halo', gN); attr(halo, 'r', 28); attr(halo, 'fill', 'url(#scpCoreGrad)');
    c = se('circle', 'scp-core', gN); attr(c, 'r', 12); attr(c, 'fill', 'url(#scpCoreGrad)');
    label = se('text', 'scp-label scp-label-main', gN); attr(label, 'y', 35); attr(label, 'text-anchor', 'middle'); label.textContent = name;
    for (i = 0; i < rels.length; i++) {
      p = pos[i]; gN = se('g', 'scp-node', stars); attr(gN, 'opacity', 0); gN.style.setProperty('--scp-color', campColor(rels[i].name, i));
      halo = se('circle', 'scp-halo', gN); attr(halo, 'r', (p.r * 2.8).toFixed(1));
      c = se('circle', 'scp-dot', gN); attr(c, 'r', p.r); attr(c, 'fill', 'var(--scp-color)');
      caption = se('g', 'scp-caption', gN);
      label = se('text', 'scp-label', caption); attr(label, 'y', p.r + 15); attr(label, 'text-anchor', 'middle'); label.textContent = rels[i].name;
      var sub = se('text', 'scp-sub', caption); attr(sub, 'y', p.r + 27); attr(sub, 'text-anchor', 'middle'); sub.textContent = rels[i].kind + ' · ' + Math.round(rels[i].strength * 100) + '%';
      var detail = se('title', null, gN); detail.textContent = rels[i].name + ' · ' + rels[i].kind + (rels[i].desc ? ' · ' + rels[i].desc : '');
      model.nodes[i].node = gN; model.nodes[i].caption = caption;
    }
    title(name, rels.length);
    svg.setAttribute('aria-label', name + '的关系星座，' + rels.length + '个关联角色');
  }
  function draw() {
    if (!model || !svg) return;
    var stamp = [progress.toFixed(3), Math.min(age, 0.84).toFixed(3), reduce].join(':');
    if (stamp === lastDraw) return;
    lastDraw = stamp; root.style.setProperty('--scp-progress', progress.toFixed(3));
    model.nodes.forEach(function (n) {
      var q = reduce ? (opened ? 1 : 0) : ease((age - n.delay) / 0.56);
      var amount = q * progress, spread = q * ease(progress);
      var lineAmount = q * (phase === 'closing' ? (closeFrom > 0 ? ease(progress) / ease(closeFrom) : 0) : 1);
      var x = cx + (n.x - cx) * spread, y = cy + (n.y - cy) * spread;
      var bx = (cx + x) / 2 + n.bend * spread, by = (cy + y) / 2 - 7 * spread;
      var path = 'M' + cx + ' ' + cy + ' Q' + bx.toFixed(2) + ' ' + by.toFixed(2) + ' ' + x.toFixed(2) + ' ' + y.toFixed(2);
      attr(n.node, 'transform', 'translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ')');
      attr(n.node, 'opacity', ease(amount / 0.45));
      attr(n.caption, 'opacity', ease((amount - 0.18) / 0.58));
      attr(n.link, 'd', path); attr(n.flow, 'd', path);
      attr(n.link, 'stroke-dashoffset', (1 - lineAmount).toFixed(3));
      attr(n.link, 'opacity', amount.toFixed(3));
      attr(n.flow, 'opacity', (clamp((amount - 0.65) / 0.35, 0, 1) * 0.42).toFixed(3));
    });
  }
  function mount() {
    if (root) return;
    root = el('aside', 'scp-panel', d.body); root.id = 'skyConstellationPeek'; root.hidden = true; root.setAttribute('aria-hidden', 'true');
    var head = el('div', 'scp-head', root), eyebrow = el('span', 'scp-eyebrow', head); eyebrow.textContent = 'TEMPORARY ORBIT · 01';
    el('strong', 'scp-title', head); var meta = el('span', 'scp-meta', head); meta.setAttribute('aria-live', 'polite');
    var wrap = el('div', 'scp-figure', root); svg = d.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', '临时关系星座'); wrap.appendChild(svg);
    hint = el('div', 'scp-hint', root); hint.textContent = '继续轻拖 · 展开关联星座';
    var foot = el('div', 'scp-foot', root); foot.textContent = '松手后星点自动回到原位';
    if (g.THREE) { screenA = new g.THREE.Vector3(); screenB = new g.THREE.Vector3(); }
  }
  function reveal(name) {
    mount(); clearTimeout(closing);
    var resume = phase === 'closing' && model && model.name === name;
    if (!resume) { progress = age = 0; build(name); }
    reduce = motionReduced(); root.classList.toggle('is-reduced', reduce);
    shown = true; opened = resume && age > 0; phase = 'drag'; lastDraw = '';
    root.classList.remove('is-closing', 'is-open', 'is-dragging'); root.hidden = false;
    root.setAttribute('aria-hidden', 'false');
    followX = followY = 0; root.style.setProperty('--scp-follow-x', '0px'); root.style.setProperty('--scp-follow-y', '0px');
    draw();
    root.getBoundingClientRect(); root.classList.add('is-dragging');
    if (opened) root.classList.add('is-open');
    hint.textContent = opened ? '关联星座已展开 · 松手收回' : '继续轻拖 · 展开关联星座';
    attach();
  }
  function openConstellation() {
    if (!root || opened || !model) return;
    opened = true; root.classList.add('is-open');
    hint.textContent = model.rels.length ? '关联星座已展开 · 松手收回' : '暂无直接关系 · 松手返回星空';
  }
  function finish() {
    clearTimeout(closing); closing = 0; phase = 'idle'; shown = opened = false; progress = 0;
    if (root) { root.hidden = true; root.setAttribute('aria-hidden', 'true'); root.classList.remove('is-dragging', 'is-open', 'is-closing'); }
    if (offFrame) { offFrame(); offFrame = null; }
  }
  function hide(immediate) {
    if (!root) return;
    if (immediate || motionReduced()) { finish(); return; }
    if (phase === 'idle' || phase === 'closing') return;
    shown = opened = false; phase = 'closing'; closeAge = 0; closeFrom = progress;
    root.setAttribute('aria-hidden', 'true'); root.classList.remove('is-dragging', 'is-open'); root.classList.add('is-closing');
    hint.textContent = '关系星座收回中';
    closing = setTimeout(finish, 520);
  }
  function frame(dt) {
    if (phase === 'idle' || !root) return;
    dt = clamp(+dt || 0, 0, 0.05);
    reduce = motionReduced(); root.classList.toggle('is-reduced', reduce);
    if (phase === 'closing') {
      if (reduce) { finish(); return; }
      closeAge += dt; progress = closeFrom * (1 - ease(closeAge / 0.46)); draw();
      if (closeAge >= 0.52) finish();
      return;
    }
    var tug = g.CLSkyTug, st = tug && tug.state ? tug.state() : null, t = st ? +st.tension || 0 : 0;
    if (!st || !st.on || !model || st.name !== model.name) { hide(true); return; }
    root.style.setProperty('--scp-tension', clamp(t / 0.24, 0, 1).toFixed(3));
    if (!opened && t >= threshold) openConstellation();
    var target = opened ? 0.62 + 0.38 * clamp((t - threshold) / 0.18, 0, 1) : 0;
    progress = reduce ? (opened ? 1 : 0) : progress + (target - progress) * (1 - Math.exp(-dt * 12));
    if (opened) age += dt;
    if (screenA && canvasRect && st.home && st.off && scene && scene.group && scene.camera) {
      screenA.copy(st.home).applyMatrix4(scene.group.matrixWorld).project(scene.camera);
      screenB.copy(st.home).add(st.off).applyMatrix4(scene.group.matrixWorld).project(scene.camera);
      var x = reduce ? 0 : clamp((screenB.x - screenA.x) * canvasRect.width / 2 * 0.065, -5, 5);
      var y = reduce ? 0 : clamp((screenA.y - screenB.y) * canvasRect.height / 2 * 0.065, -5, 5);
      var damping = reduce ? 1 : 1 - Math.exp(-dt * 10);
      followX += (x - followX) * damping; followY += (y - followY) * damping;
      root.style.setProperty('--scp-follow-x', followX.toFixed(2) + 'px'); root.style.setProperty('--scp-follow-y', followY.toFixed(2) + 'px');
    }
    draw();
  }
  function onTug(e) {
    if (!e) return;
    if (e.type === 'grab') reveal(e.name || String(e.key || '').replace(/^c:/, ''));
    else if (e.type === 'release') hide(false);
    else if (e.type === 'sleep' && phase !== 'closing') hide(true);
  }
  function attach() {
    var s = currentScene(); if (!s || !s.registerFrameHook) return;
    if (scene !== s) { if (offFrame) offFrame(); offFrame = null; scene = s; }
    if (phase !== 'idle' && !offFrame) offFrame = s.registerFrameHook(frame);
    if (!offTug && g.CLSkyTug && g.CLSkyTug.on) offTug = g.CLSkyTug.on(onTug);
  }
  function reset() { finish(); model = null; scene = null; attach(); }
  ['cl:graph-loading', 'cl:graph-ready', 'cl:sky-plot', 'cl:sky-compass', 'cl:atlas-view'].forEach(function (eventName) {
    d.addEventListener(eventName, function () { reset(); }, false);
  });
  d.addEventListener('click', function (e) { if (shown && e.target !== root && root && !root.contains(e.target) && !(e.target && e.target.tagName === 'CANVAS')) hide(true); }, true);
  g.addEventListener('resize', function () { hide(true); }, false);
  attach();
  g.CLSkyConstellationPreview = { reset: reset, hide: hide, stats: function () { return { mounted: !!root, visible: shown, open: opened, name: model && model.name || null, related: model ? model.rels.length : 0, threshold: threshold, phase: phase, progress: +progress.toFixed(3), hooked: !!offFrame, reduced: reduce }; } };
})(window);
