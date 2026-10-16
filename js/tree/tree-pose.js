(function () {
  'use strict';

  var POLL_MS = 100;
  var POLL_MAX = 15000;
  var CANON_K = 2.3;

  var POSES = {
    stars: { k: 1.88, y: -1.15, dim: 0.35 },
    plot:  { k: 2.30, y: -0.55, dim: 1 }
  };

  var reduce = false;
  try {
    reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) { reduce = false; }

  var ready = false;
  var rimR = null;
  var cur = null;
  var want = null;
  var pending = null;
  var root = null;
  var poll = null;
  var t0 = Date.now();

  function anchor() { return window.CLTreeAnchor; }

  var S0 = null, Y0 = null;
  function readRimR() {
    var a = anchor();
    if (!a || typeof a.ready !== 'function' || !a.ready()) return null;
    var r = treeRoot();
    if (!r || !r.scale || !r.position) return null;
    var sx = r.scale.x, py = r.position.y;
    if (!isFinite(sx) || sx === 0 || !isFinite(py) || py === 0) return null;
    S0 = sx; Y0 = py;
    return -py / 0.55;
  }

  function treeRoot() {
    var a = anchor();
    if (!a || typeof a.root !== 'function') return null;
    try { return a.root(); } catch (e) { return null; }
  }

  function stageActive() {
    var st = window.CLTreeStage;
    if (!st || typeof st.active !== 'function') return false;
    try { return !!st.active(); } catch (e) { return false; }
  }

  function currentMode() {
    if (stageActive()) return 'plot';
    var g = window.CLTreeGate;
    if (g && typeof g.state === 'function') {
      try { return g.state() === 'plot' ? 'plot' : 'stars'; } catch (e) {}
    }
    return 'stars';
  }

  function apply(mode) {
    if (!mode || !POSES[mode]) mode = 'stars';
    if (rimR == null) { pending = mode; return; }
    root = root || treeRoot();
    if (!root || !root.scale || !root.position) return;
    var p = POSES[mode];
    root.scale.setScalar(S0 * (p.k / CANON_K));
    root.position.y = Y0 * (p.y / -0.55);
    if (typeof root.updateMatrixWorld === 'function') root.updateMatrixWorld(true);
    cur = mode;
    pending = null;
  }

  function baseDim() {
    if (!ready) { try { tick(); } catch (e) {} }
    else if (want && cur !== want) {
      if (want === 'stars') { if (!stageActive()) apply('stars'); }
      else apply('plot');
    }
    return (cur && POSES[cur]) ? POSES[cur].dim : 1;
  }

  var stageWrapped = false;
  function wrapStage() {
    var st = window.CLTreeStage;
    if (stageWrapped || !st || typeof st.enter !== 'function' || typeof st.exit !== 'function') return false;
    if (st.enter.__clPose) { stageWrapped = true; return true; }
    var e0 = st.enter, x0 = st.exit;
    var enter = function () { want = 'plot'; apply('plot'); return e0.apply(this, arguments); };
    var exit = function () { var r = x0.apply(this, arguments); want = 'stars'; apply('stars'); return r; };
    enter.__clPose = exit.__clPose = true;
    st.enter = enter; st.exit = exit;
    if (typeof st.toggle === 'function') st.toggle = function () { return st.active() ? st.exit() : st.enter(); };
    if (typeof st.setOn === 'function') st.setOn = function (v) { return v ? st.enter() : st.exit(); };
    stageWrapped = true;
    return true;
  }

  function onPlotline(ev) {
    var on = (ev && ev.detail) ? ev.detail.on : false;
    want = on ? 'plot' : 'stars';
    if (on) apply('plot');
  }

  function stopPoll() {
    if (poll != null) { clearInterval(poll); poll = null; }
  }

  function tick() {
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) { stopPoll(); return; }
    if (rimR == null) {
      var r = readRimR();
      if (r != null) rimR = r;
    }
    if (rimR != null) {
      ready = true;
      wrapStage();
      apply(pending || currentMode());
      if (stageWrapped) { stopPoll(); return; }
      if (Date.now() - t0 > POLL_MAX) stopPoll();
      return;
    }
    if (Date.now() - t0 > POLL_MAX) stopPoll();
  }

  function start() {
    poll = setInterval(tick, POLL_MS);
    tick();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, false);
  } else {
    start();
  }
  document.addEventListener('cl:tree-plotline', onPlotline, false);

  var API = {
    name: 'tree-pose',
    POSES: POSES,
    mode: function () { return cur; },
    apply: apply,
    baseDim: baseDim,
    stats: function () {
      return {
        ready: ready,
        mode: cur,
        rimR: rimR,
        canon: { scale: S0, y: Y0 },
        scale: (root && root.scale) ? root.scale.x : null,
        y: (root && root.position) ? root.position.y : null,
        dim: baseDim(),
        stageWrapped: stageWrapped,
        want: want,
        reduced: reduce
      };
    }
  };

  window.CLTreePose = API;
})();
