(function (g) {
  'use strict';
  var T = g.THREE || null;
  var root = null, D = null, sceneApi = null, lamps = [], hot = null, solo = null, hook = null, tick = 0, low = false, reduced = false, raf = 0, timer = 0, mountVersion = 0;
  var HUD = '#brand .panel, #index .panel, #dock.on .panel, #ops, #timeline .panel, #shellMenuBtn, #shellIndexBtn, .cl-ann-ledger';
  var OFFS = [[0, 0], [0, -1], [0, 1], [1, 0], [-1, 0], [1, -1], [-1, -1], [1, 1], [-1, 1]];

  function el(t, c, p) { var n = document.createElement(t); if (c) n.className = c; if (p) p.appendChild(n); return n; }
  function flag(L, name, on) {
    if (L.flags[name] === on) return;
    L.flags[name] = on;
    L.el.classList.toggle(name, on);
  }
  function env() {
    reduced = false; low = false;
    try { reduced = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
    try { low = !!(g.CLOrbit3DTier && g.CLOrbit3DTier.get() === 'low'); } catch (e2) {}
    if (g.navigator && g.navigator.hardwareConcurrency <= 4) low = true;
  }
  function project(p, r) {
    if (!p || !T || !sceneApi || !sceneApi.camera) return null;
    var v = new T.Vector3(p[0], p[1], p[2] || 0);
    var im = sceneApi.camera.matrixWorldInverse.elements;
    var depth = im[2] * p[0] + im[6] * p[1] + im[10] * (p[2] || 0) + im[14];
    v.project(sceneApi.camera);
    return { x: r.left + (v.x * 0.5 + 0.5) * r.width, y: r.top + (1 - (v.y * 0.5 + 0.5)) * r.height,
      behind: depth >= 0 || v.z > 1 || v.z < -1 || !isFinite(v.x) || !isFinite(v.y) };
  }
  function visRect(e) {
    if (!e) return null;
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) return null;
    var r = e.getBoundingClientRect();
    return (r.width < 2 || r.height < 2) ? null : r;
  }
  function obstacles() {
    var out = [], i, n, r, q;
    try { q = document.querySelectorAll(HUD); for (i = 0; i < q.length; i++) { r = visRect(q[i]); if (r) out.push(r); } } catch (e) {}
    try { q = document.querySelectorAll('.cl-lab.on, .cl-camp-halo__badge, .cl-camp-feature'); for (i = 0; i < q.length; i++) { n = q[i]; r = visRect(n); if (r) out.push(r); } } catch (e2) {}
    return out;
  }
  function hits(r, obs) {
    var i, o;
    for (i = 0; i < obs.length; i++) { o = obs[i]; if (r.left < o.right && r.right > o.left && r.top < o.bottom && r.bottom > o.top) return true; }
    return false;
  }
  function build() {
    clear();
    if (!D || !D.ok) return;
    env();
    root = el('div', 'cl-domains-lamps', document.body);
    var i, dom, L, sub, order = [], FULL = 8;
    for (i = 0; i < D.domains.length; i++) if (D.domains[i]) order.push(D.domains[i]);
    order.sort(function (a, b) { var am = a.kind === 'main' ? 0 : 1, bm = b.kind === 'main' ? 0 : 1; return am !== bm ? am - bm : (b.memberCount - a.memberCount); });
    var rank = {}; for (i = 0; i < order.length; i++) rank[String(order[i].id)] = i;
    for (i = 0; i < D.domains.length; i++) {
      dom = D.domains[i];
      if (!dom) continue;
      L = el('button', 'cl-domains-lamp', root);
      L.type = 'button';
      L.setAttribute('data-id', String(dom.id)); L.setAttribute('data-gen', String(dom.gen));
      el('i', 'cl-domains-lamp__dot', L);
      el('span', 'cl-domains-lamp__name', L).textContent = dom.shortName || dom.name;
      sub = el('span', 'cl-domains-lamp__sub', L);
      var rec = { id: String(dom.id), dom: dom, el: L, sub: sub, w: 0, h: 0, anchor: null, label: null, flags: {},
        dotOnly: rank[String(dom.id)] >= FULL || (low && dom.memberCount < 5), layoutKey: null };
      updateCaption(rec); lamps.push(rec);
      if (rec.dotOnly) flag(rec, 'is-dot', true);
    }
    applyState();
    try { document.dispatchEvent(new CustomEvent('cl:domains-ready', { detail: { lamps: lamps.length } })); } catch (e) {}
    place(true);
  }
  function updateCaption(L) {
    var d = L.dom, key = [d.layout, d.unplacedCount, d.memberCount].join(':');
    if (key === L.layoutKey) return;
    L.layoutKey = key; L.w = 0;
    var count = d.memberCount ? String(d.memberCount) : '成员未知';
    var missing = d.unplacedCount ? ' · ' + d.unplacedCount + ' 待布局' : '';
    L.sub.textContent = '· ' + (d.lead ? d.lead + ' · ' : '') + count + missing;
    L.el.title = d.name + (d.lead ? ' · 领衔 ' + d.lead : '') + ' · ' + count +
      (d.memberCount ? ' 人' : '') + missing + (!d.valid ? '；此星标仅为待布局索引，非角色位置' : '');
    L.el.setAttribute('aria-label', L.el.title);
    L.el.setAttribute('data-layout', d.layout || (d.valid ? 'hull' : 'pending'));
    L.el.setAttribute('data-members', String(d.memberCount || 0));
    L.el.classList.toggle('is-pending', !d.valid);
  }
  function pendingPoint(index, total) {
    var w = g.innerWidth || 800, h = g.innerHeight || 600;
    var radius = Math.max(48, Math.min(w, h) * 0.31);
    var angle = -Math.PI * 0.5 + (index / Math.max(1, total)) * Math.PI * 2;
    return { x: w * 0.5 + Math.cos(angle) * radius,
      y: h * 0.5 + Math.sin(angle) * radius, behind: false };
  }
  function place(force) {
    if (!root || !lamps.length) return;
    if (!force && root.classList.contains('is-hidden')) return;
    tick++;
    if (sceneApi && sceneApi.camera && sceneApi.camera.updateMatrixWorld) sceneApi.camera.updateMatrixWorld(true);
    var cv = sceneApi && sceneApi.renderer && sceneApi.renderer.domElement;
    var viewport = cv ? cv.getBoundingClientRect() : { left: 0, top: 0, width: g.innerWidth, height: g.innerHeight };
    var obs = obstacles(), placed = [], i, k, L, p, w, h, r, ok, off, gap = 6, pending = 0, pendingAt = 0;
    for (i = 0; i < lamps.length; i++) if (!lamps[i].dom.valid) pending++;
    for (i = 0; i < lamps.length; i++) {
      L = lamps[i];
      updateCaption(L);
      p = L.dom.valid ? project(L.dom.centroid, viewport) : pendingPoint(pendingAt++, pending);
      L.anchor = p;
      if (!p || p.behind || p.x < -14 || p.y < -14 || p.x > g.innerWidth + 14 || p.y > g.innerHeight + 14) { flag(L, 'is-behind', true); L.label = null; continue; }
      flag(L, 'is-behind', false);
      if (L.dotOnly && !(hot !== null && L.id === String(hot)) && !(solo !== null && L.id === String(solo))) { flag(L, 'is-dot', true); position(L, p.x, p.y, p); placed.push({ left: p.x - 7, top: p.y - 7, right: p.x + 7, bottom: p.y + 7 }); continue; }
      /* v90 F4：默认镜头是「阵营」，线灯层建好时处于 display:none，offsetWidth=0 只能先记回落宽 120；
       * 切到剧情镜头后必须按真实宽重量一次，否则两枚全灯按 120 避让、实际 131/141 宽而互相压字（domains_v80 D3）。 */
      if (!L.w || force || !L.measured) { flag(L, 'is-dot', false); var ow = L.el.offsetWidth; L.w = ow || 120; L.h = L.el.offsetHeight || 22; L.measured = ow > 0; }
      w = L.w; h = L.h; ok = false;
      for (k = 0; k < OFFS.length && !ok; k++) {
        off = OFFS[k];
        r = { left: p.x - w / 2 + off[0] * (w / 2 + gap + 10), top: p.y - h / 2 + off[1] * (h + gap + 8) };
        r.right = r.left + w; r.bottom = r.top + h;
        if (r.left < 0 || r.top < 0 || r.right > g.innerWidth || r.bottom > g.innerHeight) continue;
        if (Math.sqrt(Math.pow(off[0] * (w / 2 + gap + 10), 2) + Math.pow(off[1] * (h + gap + 8), 2)) > 86) continue;
        if (!hits(r, obs) && !hits(r, placed)) ok = true;
      }
      if (ok) {
        flag(L, 'is-dot', false);
        position(L, (r.left + r.right) / 2, (r.top + r.bottom) / 2, p);
        placed.push(r);
      } else {
        flag(L, 'is-dot', true);
        var d = 14;
        position(L, p.x, p.y, p);
        placed.push({ left: p.x - d / 2, top: p.y - d / 2, right: p.x + d / 2, bottom: p.y + d / 2 });
      }
    }
  }
  function position(L, x, y, p) {
    x = Math.round(x * 100) / 100; y = Math.round(y * 100) / 100;
    if (!L.label || L.label.x !== x) L.el.style.setProperty('--cl-dom-x', x + 'px');
    if (!L.label || L.label.y !== y) L.el.style.setProperty('--cl-dom-y', y + 'px');
    L.label = { x: x, y: y };
    var dx = p.x - x, dy = p.y - y, length = Math.sqrt(dx * dx + dy * dy);
    var leader = length > 8 && !L.flags['is-dot'] && L.dom.valid;
    flag(L, 'has-leader', leader);
    if (leader) {
      var start = Math.min(Math.abs(dx) > 0.0001 ? (L.w / 2 + 2) * length / Math.abs(dx) : Infinity,
        Math.abs(dy) > 0.0001 ? (L.h / 2 + 2) * length / Math.abs(dy) : Infinity);
      L.el.style.setProperty('--cl-dom-leader-start', Math.min(length, start).toFixed(2) + 'px');
      L.el.style.setProperty('--cl-dom-leader-length', Math.max(0, length - start).toFixed(2) + 'px');
      L.el.style.setProperty('--cl-dom-leader-angle', Math.atan2(dy, dx).toFixed(5) + 'rad');
    }
  }
  function applyState() {
    var i, L, isHot, isSolo;
    for (i = 0; i < lamps.length; i++) {
      L = lamps[i]; isHot = hot !== null && L.id === String(hot); isSolo = solo !== null && L.id === String(solo);
      L.el.classList.toggle('is-hot', isHot || isSolo);
      L.el.classList.toggle('is-dim', (hot !== null && !isHot && solo === null) || (solo !== null && !isSolo));
      L.el.classList.toggle('is-solo-off', solo !== null && !isSolo);
      L.el.setAttribute('aria-pressed', isSolo ? 'true' : 'false');
    }
    if (root) place(true);
  }
  function frame() { place(false); }
  function clear() {
    if (root && root.parentNode) root.parentNode.removeChild(root);
    root = null; lamps = [];
  }
  function mount(model, api) {
    unmount();
    T = g.THREE || T; D = model || null; sceneApi = api || null;
    if (!D || !D.ok || !D.domains.length || !sceneApi) return false;
    var ownVersion = ++mountVersion;
    build();
    var reg = (sceneApi && typeof sceneApi.registerFrameHook === 'function') ? sceneApi.registerFrameHook : null;
    if (reg) {
      var frameFn = function () { if (ownVersion === mountVersion) frame(); };
      var off = reg.call(sceneApi, frameFn);
      hook = typeof off === 'function' ? off : null;
    }
    else if (!reduced) { (function loop() { raf = g.requestAnimationFrame(loop); frame(); })(); }
    else { timer = g.setInterval(frame, 250); }
    var closed = false;
    return function () {
      if (closed) return false;
      closed = true;
      if (ownVersion !== mountVersion) return false;
      unmount(); return true;
    };
  }
  function unmount() {
    mountVersion++;
    if (hook) { try { hook(); } catch (e0) {} }
    clear();
    if (raf) { g.cancelAnimationFrame(raf); raf = 0; }
    if (timer) { g.clearInterval(timer); timer = 0; }
    hook = null; D = null; sceneApi = null; hot = null; solo = null; tick = 0;
  }
  g.CLDomainsLamps = {
    name: 'domains-lamps', version: 'v80',
    mount: mount, unmount: unmount, frame: frame, rebuild: build,
    anchors: function () {
      return lamps.map(function (L) { return { id: L.id, world: L.dom.centroid && L.dom.centroid.slice(), anchor: L.anchor, label: L.label,
        pending: !L.dom.valid, dot: L.el.classList.contains('is-dot'), hidden: L.el.classList.contains('is-behind') || L.el.classList.contains('is-solo-off') }; });
    },
    setHot: function (id) { hot = (id === undefined || id === null || id === '') ? null : id; applyState(); },
    setSolo: function (id) { solo = (id === undefined || id === null || id === '') ? null : id; applyState(); },
    stats: function () {
      var dots = 0, behind = 0, pending = 0, i; for (i = 0; i < lamps.length; i++) { if (lamps[i].el.classList.contains('is-dot')) dots++; if (lamps[i].el.classList.contains('is-behind')) behind++; if (!lamps[i].dom.valid) pending++; }
      return { lamps: lamps.length, dots: dots, behind: behind, pending: pending, hot: hot, solo: solo, raf: !!raf, subscribed: !!hook, low: low, reduced: reduced };
    }
  };
})(window);
