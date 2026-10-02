/* @role component
 * @owns js/orbit3d-tier.js
 * @budget n/a（纯查询逻辑，无每帧开销；get() 500ms 缓存内零分配）
 * @contract v47
 *
 * CLOrbit3DTier —— 设备档 high|mid|low 单一来源。
 * 判定顺序：?tier= → body[data-tier] → scene.digest().degrade(≥2 low / 1 mid)
 *          → hardwareConcurrency<=4 → DPR>=2 且面积>3.5e6 → high
 * 对外：window.CLOrbit3DTier = { version, get, set, reduced, onChange }
 * get() 结果写入 document.body.dataset.o3tier；set() 为手动覆盖并派发 onChange。
 */
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
      try { listeners[i](t); } catch (e) { /* 订阅者异常不阻断其他订阅者 */ }
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
