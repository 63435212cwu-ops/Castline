/*! Castline · mystic ritual field v1 */
(function (g) {
  'use strict';
  var d = g.document, root = d && d.documentElement, stage, layer, raf = 0, clean = [], pulseTimer = 0, px = .5, py = .44, reduced = false;
  function mq() { try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; } }
  function low() { var b = d && d.body; return !!(root && root.getAttribute('data-tier') === 'low') || !!(b && b.classList.contains('skylab-still')); }
  function active() { var b = d && d.body; return !!(b && !(b.classList.contains('sky-shell') && b.classList.contains('skd-gl')) && (b.classList.contains('sky-shell') || b.classList.contains('atlas-workspace') || b.classList.contains('atlas-2d'))); }
  function pulse() {
    if (!active() || reduced || low()) return;
    d.body.classList.remove('mystic-surge');
    if (g.requestAnimationFrame) g.requestAnimationFrame(function () { d.body.classList.add('mystic-surge'); });
    if (pulseTimer) g.clearTimeout(pulseTimer);
    pulseTimer = g.setTimeout(function () { if (d.body) d.body.classList.remove('mystic-surge'); pulseTimer = 0; }, 1040);
  }
  function mount() {
    if (layer || !d || !d.body) return layer;
    stage = d.getElementById('stage'); if (!stage) return null;
    reduced = mq();
    layer = d.createElement('div'); layer.className = 'mystic-ritual'; layer.setAttribute('aria-hidden', 'true');
    var veil = d.createElement('i'); veil.className = 'mystic-ritual__veil';
    var sigil = d.createElement('i'); sigil.className = 'mystic-ritual__sigil';
    var orbit = d.createElement('i'); orbit.className = 'mystic-ritual__orbit';
    var dust = d.createElement('i'); dust.className = 'mystic-ritual__dust';
    var glyph = d.createElement('i'); glyph.className = 'mystic-ritual__glyph'; glyph.textContent = '✦  ⟡  ◇  ⌁  ✧  ⌁  ◇  ⟡  ✦';
    var comet = d.createElement('i'); comet.className = 'mystic-ritual__comet';
    layer.appendChild(veil); layer.appendChild(sigil); layer.appendChild(orbit); layer.appendChild(dust); layer.appendChild(glyph); layer.appendChild(comet);
    stage.insertBefore(layer, d.getElementById('labels') || null);
    function update() {
      raf = 0; if (!layer || reduced || low()) return;
      root.style.setProperty('--mystic-x', (px * 100).toFixed(2) + '%'); root.style.setProperty('--mystic-y', (py * 100).toFixed(2) + '%');
      root.style.setProperty('--mystic-tilt-x', ((px - .5) * 5.2).toFixed(2) + 'deg'); root.style.setProperty('--mystic-tilt-y', ((.44 - py) * 4.2).toFixed(2) + 'deg');
    }
    function move(e) { if (!active() || reduced || low()) return; px = Math.max(0, Math.min(1, e.clientX / Math.max(1, g.innerWidth || 1))); py = Math.max(0, Math.min(1, e.clientY / Math.max(1, g.innerHeight || 1))); if (!raf) raf = g.requestAnimationFrame(update); }
    function down(e) { if (active() && !(e.pointerType === 'mouse' && e.button > 0)) pulse(); }
    function view() { pulse(); }
    g.addEventListener('pointermove', move, { passive: true }); clean.push(function () { g.removeEventListener('pointermove', move); });
    g.addEventListener('pointerdown', down, { passive: true }); clean.push(function () { g.removeEventListener('pointerdown', down); });
    d.addEventListener('cl:atlas-view', view, { passive: true }); clean.push(function () { d.removeEventListener('cl:atlas-view', view); });
    var ob = g.MutationObserver && new g.MutationObserver(function () { if (active()) pulse(); });
    if (ob) { ob.observe(d.body, { attributes: true, attributeFilter: ['data-atlas-view'] }); clean.push(function () { ob.disconnect(); }); }
    return layer;
  }
  function dispose() { while (clean.length) { try { clean.pop()(); } catch (e) {} } if (pulseTimer) g.clearTimeout(pulseTimer); if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); if (layer && layer.parentNode) layer.parentNode.removeChild(layer); layer = stage = null; }
  g.CLMysticRitual = { name: 'mystic-ritual', version: 'v1', mount: mount, dispose: dispose, stats: function () { return { mounted: layer ? 1 : 0, reduced: reduced ? 1 : 0, children: layer ? layer.children.length : 0 }; } };
  if (d && d.readyState === 'loading') d.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
})(window);
