(function (win, doc) {
  'use strict';
  if (!win || !doc) { return; }

  var VERSION = '47';
  var CACHE_MS = 500;
  var VALID = { high: 1, mid: 1, low: 1 };
  var URL_RE = /[?&]tier=(high|mid|low)(?:&|$)/i;

  var manual = null;
  var cached = null;
  var cachedAt = -1;
  var listeners = [];

  function now() {
    return (win.performance && win.performance.now)
      ? win.performance.now() : Date.now();
  }

  function body() { return doc.body || null; }

  function readUrl() {
    var q = (win.location && win.location.search) || '';
    var m = URL_RE.exec(q);
    return m ? m[1].toLowerCase() : null;
  }

  function readBody() {
    var b = body();
    var v = (b && b.dataset) ? b.dataset.tier : null;
    if (!v) { return null; }
    v = String(v).toLowerCase();
    return VALID[v] ? v : null;
  }

  function readDegrade() {
    var cl = win.__cl;
    var sc = cl && cl.scene;
    if (!sc || typeof sc.digest !== 'function') { return null; }
    var d;
    try { d = Number(sc.digest().degrade); } catch (e) { return null; }
    if (!isFinite(d)) { return null; }
    if (d >= 2) { return 'low'; }
    if (d >= 1) { return 'mid'; }
    return null;
  }

  function cores() {
    var n = win.navigator && win.navigator.hardwareConcurrency;
    return (typeof n === 'number') ? n : 0;
  }

  function bigViewport() {
    var dpr = win.devicePixelRatio || 1;
    var w = win.innerWidth || 0;
    var h = win.innerHeight || 0;
    return dpr >= 2 && (w * h) > 3.5e6;
  }

  function resolve() {
    if (manual) { return manual; }
    var t = readUrl();
    if (t) { return t; }
    t = readBody();
    if (t) { return t; }
    t = readDegrade();
    if (t) { return t; }
    if (cores() <= 4) { return 'mid'; }
    if (bigViewport()) { return 'mid'; }
    return 'high';
  }

  function publish(t) {
    var b = body();
    if (b && b.dataset) { b.dataset.o3tier = t; b.dataset.tier = t; }
  }

  function emit(t) {
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](t); } catch (e) {  }
    }
  }

  function get() {
    var t = now();
    if (cached !== null && (t - cachedAt) < CACHE_MS) { return cached; }
    cached = resolve();
    cachedAt = t;
    publish(cached);
    return cached;
  }

  function set(t) {
    t = String(t || '').toLowerCase();
    if (!VALID[t]) { return get(); }
    manual = t;
    cached = t;
    cachedAt = now();
    publish(t);
    emit(t);
    return t;
  }

  function reduced() {
    return !!(win.matchMedia &&
      win.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function onChange(fn) {
    if (typeof fn !== 'function') { return function () {}; }
    listeners.push(fn);
    return function () {
      var k = listeners.indexOf(fn);
      if (k >= 0) { listeners.splice(k, 1); }
    };
  }

  win.CLOrbit3DTier = {
    version: VERSION,
    get: get,
    set: set,
    reduced: reduced,
    onChange: onChange
  };
})(window, document);
