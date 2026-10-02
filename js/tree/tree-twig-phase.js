/* @role component · @owns js/tree-twig-phase.js · @budget dom_nodes=0 · @contract v41 */
(function () {
  'use strict';

  var NAME = 'tree-twig-phase';
  var DEF_SPREAD = 0.35;
  var MAX_SPREAD = 1.5;
  var SAMPLE_N = 1000;

  var _spread = DEF_SPREAD;
  var _on = true;

  function fnv1a(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h + (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)) >>> 0;
    }
    return h >>> 0;
  }

  function fmix(h) {
    h ^= h >>> 16;
    h = Math.imul(h, 0x85ebca6b);
    h ^= h >>> 13;
    h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
    return h >>> 0;
  }

  function unit(id) {
    var h = fmix(fnv1a(String(id)));
    return (h / 4294967295) * 2 - 1;
  }

  function phase(id) {
    if (!_on) return 0;
    return unit(id) * _spread;
  }

  function table(ids) {
    var n = ids && ids.length ? ids.length : 0;
    var out = new Float32Array(n);
    for (var i = 0; i < n; i++) out[i] = phase(ids[i]);
    return out;
  }

  function setSpread(rad) {
    var n = Number(rad);
    if (!isFinite(n)) return _spread;
    if (n < 0) n = 0;
    if (n > MAX_SPREAD) n = MAX_SPREAD;
    _spread = n;
    return _spread;
  }

  function spread() {
    return _spread;
  }

  function setOn(b) {
    _on = !!b;
    return _on;
  }

  function on() {
    return _on;
  }

  function pad4(i) {
    var s = String(i);
    while (s.length < 4) s = '0' + s;
    return s;
  }

  function r6(x) {
    return Math.round(x * 1e6) / 1e6;
  }

  function sample() {
    var sum = 0;
    var min = Infinity;
    var max = -Infinity;
    for (var i = 0; i < SAMPLE_N; i++) {
      var v = phase('W' + pad4(i));
      sum += v;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    return { mean: r6(sum / SAMPLE_N), min: r6(min), max: r6(max) };
  }

  function stats() {
    return { on: _on, spread: _spread, sample: sample() };
  }

  window.CLTwigPhase = {
    name: NAME,
    phase: phase,
    table: table,
    setSpread: setSpread,
    spread: spread,
    setOn: setOn,
    on: on,
    stats: stats
  };
})();
