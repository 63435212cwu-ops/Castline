/*! Castline · atlas-cinema v1
 * Filmic camera language for the stage. One demand-driven pointer loop, no
 * geometry writes and no WebGL resources. The visible finish lives in CSS.
 */
(function (g) {
  'use strict';
  var d = g.document, root = d && d.documentElement, stage = null, layer = null;
  var raf = 0, px = .5, py = .44, flight = 0, reduced = false, low = false, clean = [], cutTimer = 0;
  function media() { try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; } }
  function quiet() { return media() || !!(d.body && (d.body.classList.contains('skylab-still') || d.body.classList.contains('atlas-motion-quiet'))); }
  function vars() {
    reduced = quiet(); low = !!(d.body && d.body.getAttribute('data-tier') === 'low');
    if (reduced || low) { px = .5; py = .44; flight = 0; }
    root.style.setProperty('--cinema-x', (px * 100).toFixed(2) + '%');
    root.style.setProperty('--cinema-y', (py * 100).toFixed(2) + '%');
    root.style.setProperty('--cinema-depth', Math.min(1, Math.abs(px - .5) + Math.abs(py - .44)).toFixed(3));
    root.style.setProperty('--cinema-flight', flight.toFixed(3));
  }
  function mount() {
    if (!d || !d.body || layer) return layer;
    stage = d.getElementById('stage');
    layer = d.createElement('div'); layer.className = 'cinema-depth'; layer.setAttribute('aria-hidden', 'true');
    ['grain', 'bloom', 'iris', 'sweep', 'gate', 'runes', 'meteor', 'pulse'].forEach(function (name) {
      var e = d.createElement('i'); e.className = 'cinema-depth__' + name; layer.appendChild(e);
    });
    (stage || d.body).appendChild(layer);
    vars();
    function occult(cls, duration) {
      if (!d.body || reduced || low) return;
      d.body.classList.remove(cls);
      g.requestAnimationFrame(function () { if (d.body) d.body.classList.add(cls); });
      g.setTimeout(function () { if (d.body) d.body.classList.remove(cls); }, duration);
    }
    function seedMeteor() {
      root.style.setProperty('--cinema-meteor-x', (8 + Math.random() * 62).toFixed(2) + '%');
      root.style.setProperty('--cinema-meteor-y', (17 + Math.random() * 55).toFixed(2) + '%');
      root.style.setProperty('--cinema-meteor-angle', (-34 + Math.random() * 28).toFixed(2) + 'deg');
    }
    function move(e) {
      if (reduced || low || !stage) return;
      px = Math.max(0, Math.min(1, e.clientX / Math.max(1, g.innerWidth)));
      py = Math.max(0, Math.min(1, e.clientY / Math.max(1, g.innerHeight)));
      if (!raf) raf = g.requestAnimationFrame(function () { raf = 0; vars(); });
    }
    function down(e) {
      if (reduced || low || !stage || e.pointerType === 'mouse' && e.button > 0) return;
      flight = Math.min(1, flight + .58); vars();
      if (d.body) d.body.classList.add('cinema-flight');
      occult('cinema-pulse', 920);
    }
    function up() {
      flight = .22; vars();
      if (d.body) d.body.classList.remove('cinema-flight');
      g.setTimeout(function () { flight = 0; vars(); }, reduced ? 0 : 720);
    }
    function cut(e) {
      if (reduced || low || !d.body) return;
      if (cutTimer) g.clearTimeout(cutTimer);
      d.body.classList.remove('cinema-cut', 'cinema-gate', 'cinema-meteor');
      seedMeteor();
      g.requestAnimationFrame(function () {
        if (!d.body) return;
        d.body.classList.add('cinema-cut', 'cinema-gate', 'cinema-meteor');
      });
      cutTimer = g.setTimeout(function () { if (d.body) d.body.classList.remove('cinema-cut'); cutTimer = 0; }, 1020);
      g.setTimeout(function () { if (d.body) d.body.classList.remove('cinema-gate', 'cinema-meteor'); }, 1880);
      var v = e && e.detail && e.detail.view;
      if (v) d.body.setAttribute('data-cinema-lens', v);
    }
    d.addEventListener('pointermove', move, { passive: true }); clean.push(function () { d.removeEventListener('pointermove', move); });
    d.addEventListener('pointerdown', down, { passive: true, capture: true }); clean.push(function () { d.removeEventListener('pointerdown', down, true); });
    d.addEventListener('pointerup', up, { passive: true, capture: true }); d.addEventListener('pointercancel', up, { passive: true, capture: true });
    clean.push(function () { d.removeEventListener('pointerup', up, true); d.removeEventListener('pointercancel', up, true); });
    d.addEventListener('cl:atlas-view', cut, { passive: true }); clean.push(function () { d.removeEventListener('cl:atlas-view', cut); });
    g.addEventListener('resize', vars, { passive: true }); clean.push(function () { g.removeEventListener('resize', vars); });
    d.addEventListener('visibilitychange', function () { if (d.hidden) { flight = 0; if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0; vars(); } });
    if (g.MutationObserver) {
      var mo = new g.MutationObserver(vars);
      mo.observe(d.body, { attributes: true, attributeFilter: ['class', 'data-tier'] });
      clean.push(function () { mo.disconnect(); });
    }
    return layer;
  }
  function dispose() {
    while (clean.length) { try { clean.pop()(); } catch (e) {} }
    if (cutTimer) g.clearTimeout(cutTimer); cutTimer = 0;
    if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0;
    if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    layer = stage = null; flight = 0;
  }
  g.CLAtlasCinema = { mount: mount, dispose: dispose, stats: function () { return { mounted: layer ? 1 : 0, reduced: reduced ? 1 : 0, low: low ? 1 : 0, flight: flight }; } };
  if (d && d.readyState === 'loading') d.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
})(window);
