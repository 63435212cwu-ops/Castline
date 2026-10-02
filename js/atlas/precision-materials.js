/* Castline · precision-materials.js
 * Shared SVG material library. The filters are intentionally defined once and
 * referenced by CSS, so three lenses gain a coherent surface language without
 * extra canvases, textures or draw calls.
 */
(function (g) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(n);
    return n;
  }
  function stop(parent, offset, color, opacity) {
    return el('stop', { offset: offset, 'stop-color': color, 'stop-opacity': opacity }, parent);
  }
  function caustic(parent, duration, reverse) {
    /* SMIL keeps the sheen on the gradient itself: no extra DOM path, canvas,
     * draw call or rAF loop. It is omitted for still/low motion modes. */
    var reduced = false, tier = '';
    try { reduced = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
    try { tier = document.body && document.body.getAttribute('data-tier') || ''; } catch (e2) {}
    if (reduced || tier === 'low') return;
    el('animateTransform', {
      attributeName: 'gradientTransform', type: 'rotate',
      from: (reverse ? '342 .5 .5' : '-18 .5 .5'), to: (reverse ? '-18 .5 .5' : '342 .5 .5'),
      dur: duration, repeatCount: 'indefinite', additive: 'sum'
    }, parent);
  }
  function addFilter(defs, id, spec) {
    var f = el('filter', { id: id, x: '-28%', y: '-28%', width: '156%', height: '156%', 'color-interpolation-filters': 'sRGB' }, defs);
    if (spec === 'annulus' || spec === 'hot') {
      var noise = el('feTurbulence', { type: 'fractalNoise', baseFrequency: '.018 .035', numOctaves: '2', seed: spec === 'hot' ? '31' : '17', result: 'grain' }, f);
      el('feDisplacementMap', { in: 'SourceGraphic', in2: 'grain', scale: spec === 'hot' ? '1.4' : '.72', xChannelSelector: 'R', yChannelSelector: 'B', result: 'edge' }, f);
      el('feGaussianBlur', { in: 'edge', stdDeviation: spec === 'hot' ? '2.4' : '1.15', result: 'halo' }, f);
      el('feSpecularLighting', { in: 'SourceAlpha', surfaceScale: spec === 'hot' ? '2.7' : '1.6', specularConstant: spec === 'hot' ? '.76' : '.48', specularExponent: '22', lightingColor: 'white', result: 'spec' }, f);
      el('feDistantLight', { azimuth: '-38', elevation: '52' }, f.lastChild);
      var m = el('feMerge', {}, f);
      el('feMergeNode', { in: 'halo' }, m);
      el('feMergeNode', { in: 'spec' }, m);
      el('feMergeNode', { in: 'edge' }, m);
    } else if (spec === 'bead') {
      el('feGaussianBlur', { in: 'SourceAlpha', stdDeviation: '1.4', result: 'blur' }, f);
      el('feSpecularLighting', { in: 'SourceAlpha', surfaceScale: '3', specularConstant: '.72', specularExponent: '28', lightingColor: 'white', result: 'spec' }, f);
      el('feDistantLight', { azimuth: '-40', elevation: '54' }, f.lastChild);
      var bm = el('feMerge', {}, f); el('feMergeNode', { in: 'blur' }, bm); el('feMergeNode', { in: 'spec' }, bm); el('feMergeNode', { in: 'SourceGraphic' }, bm);
    } else if (spec === 'bead-hot') {
      el('feGaussianBlur', { in: 'SourceAlpha', stdDeviation: '2.8', result: 'blur' }, f);
      el('feSpecularLighting', { in: 'SourceAlpha', surfaceScale: '4', specularConstant: '.88', specularExponent: '34', lightingColor: 'white', result: 'spec' }, f);
      el('feDistantLight', { azimuth: '-48', elevation: '58' }, f.lastChild);
      var bh = el('feMerge', {}, f); el('feMergeNode', { in: 'blur' }, bh); el('feMergeNode', { in: 'spec' }, bh); el('feMergeNode', { in: 'SourceGraphic' }, bh);
    } else if (spec === 'gem') {
      el('feGaussianBlur', { in: 'SourceAlpha', stdDeviation: '1.2', result: 'rim' }, f);
      el('feSpecularLighting', { in: 'SourceAlpha', surfaceScale: '3', specularConstant: '.62', specularExponent: '24', lightingColor: 'white', result: 'facet' }, f);
      el('feDistantLight', { azimuth: '-34', elevation: '62' }, f.lastChild);
      var gm = el('feMerge', {}, f); el('feMergeNode', { in: 'rim' }, gm); el('feMergeNode', { in: 'facet' }, gm); el('feMergeNode', { in: 'SourceGraphic' }, gm);
    } else if (spec === 'gem-edge') {
      el('feGaussianBlur', { in: 'SourceAlpha', stdDeviation: '.7', result: 'rim' }, f);
      el('feSpecularLighting', { in: 'SourceAlpha', surfaceScale: '2', specularConstant: '.76', specularExponent: '30', lightingColor: 'white', result: 'facet' }, f);
      el('feDistantLight', { azimuth: '-50', elevation: '58' }, f.lastChild);
      var ge = el('feMerge', {}, f); el('feMergeNode', { in: 'rim' }, ge); el('feMergeNode', { in: 'facet' }, ge); el('feMergeNode', { in: 'SourceGraphic' }, ge);
    }
  }
  function mount() {
    if (!document.body || document.getElementById('clPrecisionDefs')) return;
    var host = document.createElementNS(NS, 'svg'); host.id = 'clPrecisionDefs'; host.setAttribute('aria-hidden', 'true'); host.setAttribute('width', '1'); host.setAttribute('height', '1'); host.style.cssText = 'position:fixed;width:1px;height:1px;left:-2px;top:-2px;overflow:hidden;pointer-events:none;opacity:0';
    var defs = el('defs', {}, host);
    var a = el('linearGradient', { id: 'cl-gem-surface-attr', x1: '0', y1: '0', x2: '1', y2: '1' }, defs);
    stop(a, '0', 'var(--cl-gem-attr-bright)', '.38'); stop(a, '.34', 'var(--cl-gem-attr)', '.16'); stop(a, '.66', 'var(--abyss-ink-bright)', '.06'); stop(a, '1', 'var(--cl-gem-attr)', '.28');
    caustic(a, '31s', false);
    var m = el('linearGradient', { id: 'cl-gem-surface-meta', x1: '1', y1: '0', x2: '0', y2: '1' }, defs);
    stop(m, '0', 'var(--cl-gem-meta-bright)', '.34'); stop(m, '.4', 'var(--cl-gem-meta)', '.12'); stop(m, '.72', 'var(--abyss-ink-bright)', '.05'); stop(m, '1', 'var(--cl-gem-meta)', '.25');
    caustic(m, '37s', true);
    addFilter(defs, 'cl-precision-annulus', 'annulus'); addFilter(defs, 'cl-precision-annulus-hot', 'hot'); addFilter(defs, 'cl-precision-bead', 'bead'); addFilter(defs, 'cl-precision-bead-hot', 'bead-hot'); addFilter(defs, 'cl-precision-gem', 'gem'); addFilter(defs, 'cl-precision-gem-edge', 'gem-edge');
    document.body.appendChild(host);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
  g.CLPrecisionMaterials = { name: 'precision-materials', version: 'v1', mount: mount };
})(window);
