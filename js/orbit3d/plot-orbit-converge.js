/**
 * @role micro
 * @owns js/orbit3d/plot-orbit-converge.js
 * @budget raf_ms<=0.2
 * @contract v46.1+v47
 *
 * §3.D window.CLPlotOrbitConverge = {set(map), clear(), state(), setTier('low'|'high'), version}
 */
(function (global) {
  'use strict';

  var VERSION = 'v46.1';

  /* ---- 契约令牌（JS 常量，命名即令牌） ---- */
  var CONVERGE_MS = 700;
  var CONVERGE_MS_LOW = 260;
  var FALLBACK_STEP = 16;

  var PHASE_IDLE = 'idle';
  var PHASE_IN = 'in';
  var PHASE_HOLD = 'hold';
  var PHASE_OUT = 'out';

  /* ---- 时钟：performance.now()，缺则 Date.now() ---- */
  var now = (typeof performance !== 'undefined' && performance &&
    typeof performance.now === 'function')
    ? function () { return performance.now(); }
    : function () { return Date.now(); };

  /* ---- rAF，缺则 setTimeout 兜底（FALLBACK_STEP） ---- */
  var hasRaf = (typeof global.requestAnimationFrame === 'function');
  function raf(fn) {
    if (hasRaf) return global.requestAnimationFrame(fn);
    return global.setTimeout(function () { fn(now()); }, FALLBACK_STEP);
  }
  function caf(id) {
    if (hasRaf && typeof global.cancelAnimationFrame === 'function') {
      return global.cancelAnimationFrame(id);
    }
    return global.clearTimeout(id);
  }

  /* ---- 降级开关 ---- */
  var tierOverride = null;

  function prefersReduced() {
    return !!(global.matchMedia &&
      global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isLowTier() {
    if (tierOverride === 'low') return true;
    if (tierOverride === 'high') return false;
    try {
      if (typeof navigator !== 'undefined' && navigator &&
        navigator.hardwareConcurrency <= 4) return true;
      if (typeof document !== 'undefined' && document && document.body &&
        document.body.dataset && document.body.dataset.tier === 'low') return true;
    } catch (e) {}
    return false;
  }

  function duration() { return isLowTier() ? CONVERGE_MS_LOW : CONVERGE_MS; }

  /* ---- 上游守卫 ---- */
  function migrating() {
    var m = global.CLStarMigrate;
    if (m && typeof m.state === 'function') {
      try { return m.state() !== 'stars'; } catch (e) { return false; }
    }
    return false;
  }

  function scene() {
    var s = global.__cl && global.__cl.scene;
    return (s && typeof s.setStarTargets === 'function') ? s : null;
  }

  /* ---- 运行状态 ---- */
  var k = 0;
  var phase = PHASE_IDLE;
  var map = null;
  var count = 0;
  var startK = 0;
  var target = 0;
  var t0 = 0;
  var rafId = null;
  var running = false;

  function easeOutCubic(p) { var q = 1 - p; return 1 - q * q * q; }

  function sanitize(input) {
    var out = {};
    var n = 0;
    if (input && typeof input === 'object') {
      for (var key in input) {
        if (!Object.prototype.hasOwnProperty.call(input, key)) continue;
        var v = input[key];
        if (!v || typeof v.length !== 'number' || v.length < 3) continue;
        var x = Number(v[0]), y = Number(v[1]), z = Number(v[2]);
        if (!isFinite(x) || !isFinite(y) || !isFinite(z)) continue;
        out[key] = [x, y, z];
        n++;
      }
    }
    return { map: n ? out : null, n: n };
  }

  function stop() {
    if (rafId !== null) { caf(rafId); rafId = null; }
    running = false;
  }

  function settle(s) {
    if (target === 1) {
      s.setStarTargets(map, k);
      phase = PHASE_HOLD;
    } else {
      s.setStarTargets(null);
      phase = PHASE_IDLE;
      map = null;
      count = 0;
    }
    stop();
  }

  function tick() {
    rafId = null;
    if (!running) return;
    if (migrating()) { running = false; return; }
    var s = scene();
    if (!s) { running = false; phase = PHASE_IDLE; return; }
    var p = (now() - t0) / duration();
    if (p >= 1) p = 1;
    k = startK + (target - startK) * easeOutCubic(p);
    if (p >= 1) { k = target; settle(s); return; }
    s.setStarTargets(map, k);
    rafId = raf(tick);
  }

  function begin(toTarget) {
    var s = scene();
    if (!s || migrating()) { stop(); return; }
    stop();
    target = toTarget;
    if (prefersReduced() || duration() <= 0 || k === toTarget) {
      k = toTarget;
      settle(s);
      return;
    }
    startK = k;
    t0 = now();
    phase = (toTarget === 1) ? PHASE_IN : PHASE_OUT;
    running = true;
    rafId = raf(tick);
  }

  /* ---- 公开 API ---- */
  function set(input) {
    var clean = sanitize(input);
    if (clean.n === 0) { return clear(); }
    map = clean.map;
    count = clean.n;
    begin(1);
  }

  function clear() { begin(0); }

  function state() { return { k: k, n: count, phase: phase }; }

  function setTier(t) { tierOverride = (t === 'low' || t === 'high') ? t : null; }

  /* 无头/测试专用：手动推进 ms 毫秒（rAF 不跑时也能收敛），返回 state() */
  function step(ms) {
    if (!running) return state();
    t0 -= (typeof ms === 'number' && isFinite(ms) ? ms : FALLBACK_STEP);
    if (rafId !== null) { caf(rafId); rafId = null; }
    tick();
    return state();
  }

  global.CLPlotOrbitConverge = {
    set: set,
    clear: clear,
    state: state,
    setTier: setTier,
    step: step,
    version: VERSION
  };
})(typeof window !== 'undefined' ? window : this);
