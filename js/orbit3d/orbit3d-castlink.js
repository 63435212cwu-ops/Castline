/* @role component · @owns js/orbit3d-castlink.js · @budget dom_nodes=1/chip js_ms=0.03 · @contract v47+v49 */
(function (g) {
  'use strict';

  var NAME = 'orbit3d-castlink';
  var VERSION = '49';
  var CARD_SEL = '#clOrbit .cl-orbit__card';
  var CHIP_SEL = '[data-name]';
  var CNT_CLS = 'cl-o3-cnt';

  var counts = null;
  var countsLen = -1;
  var card = null;
  var bound = false;
  var hover = null;
  var refreshes = 0;
  var reduced = false;

  function escapeHatch() {
    var q = (g.location && g.location.search) || '';
    return q.indexOf('tree=1') >= 0 || q.indexOf('treestage=1') >= 0;
  }

  function isReduced() {
    if (!g.matchMedia) return false;
    return !!g.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function decorOff() {
    if (reduced) return true;
    var L = g.CLOrbit3DLayer;
    if (L && L.stats) {
      var s = L.stats();
      if (s && s.tier === 2) return true;
    }
    return false;
  }

  function chipOf(node, root) {
    while (node && node !== root) {
      if (node.nodeType === 1 && node.getAttribute && node.getAttribute('data-name')) return node;
      node = node.parentNode;
    }
    return null;
  }

  function buildCounts(V) {
    var list = V.orderList();
    var m = {};
    var i, j, ev, cast, n;
    for (i = 0; i < list.length; i++) {
      ev = V.eventAt(list[i]);
      cast = ev && ev.cast;
      if (!cast) continue;
      for (j = 0; j < cast.length; j++) {
        n = cast[j];
        if (n) m[n] = (m[n] || 0) + 1;
      }
    }
    return m;
  }

  function ensureCounts(V) {
    var st = V.state ? V.state() : null;
    var ch = st ? st.character : null;
    if (!ch) {
      var len = V.orderList().length;
      if (!counts || len !== countsLen) {
        counts = buildCounts(V);
        countsLen = len;
      }
    }
    return counts;
  }

  function onOver(e) {
    var chip = chipOf(e && e.target, card);
    if (!chip) return;
    var name = chip.getAttribute('data-name');
    if (!name) return;
    hover = name;
    if (decorOff()) return;
    var F = g.CLOrbit3DFootprint;
    if (F && F.preview) F.preview(name);
  }

  function onOut(e) {
    var chip = chipOf(e && e.target, card);
    var rt = e && e.relatedTarget;
    if (chip && rt && chip.contains(rt)) return;
    hover = null;
    var F = g.CLOrbit3DFootprint;
    if (F && F.clear) F.clear();
  }

  function bind(node) {
    card = node;
    node.addEventListener('mouseover', onOver);
    node.addEventListener('mouseout', onOut);
    bound = true;
  }

  function badge(node, map) {
    var chips = node.querySelectorAll(CHIP_SEL);
    var doc = node.ownerDocument;
    var i, chip, name, sup;
    for (i = 0; i < chips.length; i++) {
      chip = chips[i];
      if (chip.querySelector && chip.querySelector('sup.' + CNT_CLS)) continue;
      name = chip.getAttribute('data-name');
      if (!name) continue;
      sup = doc.createElement('sup');
      sup.className = CNT_CLS;
      sup.textContent = '\u00d7' + (map[name] || 0);
      chip.appendChild(sup);
    }
  }

  function findCard() {
    if (!g.document || !g.document.querySelector) return null;
    var node = g.document.querySelector(CARD_SEL);
    if (!node || node.hidden) return null;
    return node;
  }

  function refresh() {
    refreshes++;
    reduced = isReduced();
    var V = g.CLPlotOrbitView;
    var node = findCard();
    if (!V || !node) return;
    if (!bound || !card || !card.isConnected || card !== node) bind(node);
    var map = ensureCounts(V);
    if (map) badge(node, map);
  }

  function countKeys(m) {
    var k = 0, p;
    for (p in m) { if (m.hasOwnProperty(p)) k++; }
    return k;
  }

  function stats() {
    reduced = isReduced();
    var badged = 0;
    if (card && card.isConnected && card.querySelectorAll) {
      badged = card.querySelectorAll('sup.' + CNT_CLS).length;
    }
    return {
      name: NAME,
      version: VERSION,
      ready: !!card,
      names: counts ? countKeys(counts) : 0,
      badged: badged,
      hover: hover,
      refreshes: refreshes,
      reduced: reduced
    };
  }

  function tick() { refresh(); }

  function boot() {
    if (escapeHatch()) return;
    if (g.CLArcana && g.CLArcana.register) {
      g.CLArcana.register({ name: NAME, update: tick });
    }
  }

  g.CLOrbit3DCastLink = { name: NAME, version: VERSION, refresh: refresh, stats: stats };

  boot();
})(typeof window !== 'undefined' ? window : this);
