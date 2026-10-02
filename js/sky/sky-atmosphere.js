/*! @role atmosphere | @owns js/sky/sky-atmosphere.js | @contract deep-sky/4 */
(function (g) {
  'use strict';
  var node = null, raf = 0, igniteTimer = 0, dead = false, reduced = false, clean = [], px = .5, py = .44;
  function mediaReduced() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function add(cls, tag) { var e = g.document.createElement(tag || 'i'); e.className = cls; return e; }
  function frozen() {
    var body = g.document && g.document.body;
    var root = g.document && g.document.documentElement;
    return dead || reduced || !!(g.document && g.document.hidden) || !!((root && root.getAttribute('data-tier') === 'low') || (body && (body.getAttribute('data-tier') === 'low' || body.classList.contains('skylab-still'))));
  }
  function mount() {
    var stage = g.document && g.document.getElementById('stage');
    if (!stage || node) return node;
    dead = false; reduced = mediaReduced();
    node = g.document.createElement('div'); node.className = 'sky-atmosphere'; node.setAttribute('aria-hidden', 'true');
    node.appendChild(add('sa-cloud sa-cloud-a'));
    node.appendChild(add('sa-cloud sa-cloud-b'));
    node.appendChild(add('sa-cloud sa-cloud-c'));
    /* Sparse optical strata: each is a single composited sheet, so the
       atmosphere gains depth without a per-star DOM cost. */
    node.appendChild(add('sa-aurora'));
    node.appendChild(add('sa-filaments'));
    node.appendChild(add('sa-dust'));
    /* A procedural combustion pass.  It is still one DOM layer per material
       (no per-ember nodes), so dragging the compass never has to walk a
       particle list.  The CSS layer is disabled with the same low/reduced
       motion gates as the rest of the atmosphere. */
    node.appendChild(add('sa-fire sa-fire-a'));
    node.appendChild(add('sa-fire sa-fire-b'));
    node.appendChild(add('sa-embers'));
    node.appendChild(add('sa-flare'));
    node.appendChild(add('sa-lens-ring'));
    node.appendChild(add('sa-vignette'));
    var canvas = g.document.getElementById('gl');
    stage.insertBefore(node, canvas && canvas.parentNode === stage ? canvas.nextSibling : stage.firstChild || null);
    function setPointer(ev) {
      if (!node || frozen()) return;
      px = Math.max(0, Math.min(1, ev.clientX / Math.max(1, g.innerWidth)));
      py = Math.max(0, Math.min(1, ev.clientY / Math.max(1, g.innerHeight)));
      if (raf) return;
      raf = g.requestAnimationFrame(function () {
        raf = 0;
        if (!node || frozen()) return;
        node.style.setProperty('--sa-x', (px * 100).toFixed(2) + '%');
        node.style.setProperty('--sa-y', (py * 100).toFixed(2) + '%');
        node.style.setProperty('--sa-depth', Math.min(1, Math.abs(px - .5) + Math.abs(py - .5)).toFixed(3));
        node.classList.toggle('is-near', px > .28 && px < .72 && py > .22 && py < .78);
      });
    }
    function ignite(on) {
      if (!node || on && frozen()) return;
      node.classList.toggle('is-ignite', !!on);
      node.style.setProperty('--sa-heat', on ? '1' : '0');
    }
    function down() { if (node && !frozen()) { node.classList.add('is-press'); ignite(true); } }
    function up() { if (node) { node.classList.remove('is-press'); ignite(false); } }
    g.addEventListener('pointermove', setPointer, { passive: true }); clean.push(function () { g.removeEventListener('pointermove', setPointer); });
    g.addEventListener('pointerdown', down, { passive: true }); clean.push(function () { g.removeEventListener('pointerdown', down); });
    g.addEventListener('pointerup', up, { passive: true }); g.addEventListener('pointercancel', up, { passive: true });
    clean.push(function () { g.removeEventListener('pointerup', up); g.removeEventListener('pointercancel', up); });
    function visibility() { if (node) node.classList.toggle('is-paused', g.document.hidden); }
    g.document.addEventListener('visibilitychange', visibility);
    clean.push(function () { g.document.removeEventListener('visibilitychange', visibility); });
    if (g.matchMedia) {
      var media = g.matchMedia('(prefers-reduced-motion: reduce)');
      function motion() { reduced = !!media.matches; if (reduced) up(); }
      if (media.addEventListener) { media.addEventListener('change', motion); clean.push(function () { media.removeEventListener('change', motion); }); }
      else if (media.addListener) { media.addListener(motion); clean.push(function () { media.removeListener(motion); }); }
    }
    /* 图谱切换已经由 shell 做完数据 / 镜头写入后再发事件；此处只做一次热闪，
       避免旧镜头的余烬动画跨态残留。 */
    function lens(e) {
      if (!node || frozen()) return;
      if (igniteTimer) g.clearTimeout(igniteTimer);
      node.setAttribute('data-lens', e && e.detail && e.detail.on ? 'plot' : 'constellation');
      ignite(true);
      igniteTimer = g.setTimeout(function () { igniteTimer = 0; if (node) ignite(false); }, reduced ? 0 : 760);
    }
    g.document.addEventListener('cl:sky-plot', lens, false);
    clean.push(function () { g.document.removeEventListener('cl:sky-plot', lens, false); });
    function compassLens() { lens({ detail: { on: false } }); }
    g.document.addEventListener('cl:sky-compass', compassLens, false);
    clean.push(function () { g.document.removeEventListener('cl:sky-compass', compassLens, false); });
    visibility();
    return node;
  }
  function dispose() {
    dead = true; if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0;
    if (igniteTimer) g.clearTimeout(igniteTimer); igniteTimer = 0;
    while (clean.length) { try { clean.pop()(); } catch (e) {} }
    if (node && node.parentNode) node.parentNode.removeChild(node); node = null;
  }
  function stats() { return { mounted: node ? 1 : 0, reduced: reduced ? 1 : 0, children: node ? node.children.length : 0, ignite: !!(node && node.classList.contains('is-ignite')) }; }
  g.CLSkyAtmosphere = { mount: mount, dispose: dispose, stats: stats };
  if (g.document && g.document.readyState === 'loading') g.document.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
})(window);
