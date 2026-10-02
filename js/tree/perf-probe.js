/* @role component · @owns js/perf-probe.js · @budget dom_nodes=1 · @contract v41 */
(function () {
  'use strict';

  var NAME = 'perf-probe';
  var POLL_MS = 100;
  var POLL_MAX = 15000;
  var WIN_MS = 1000;

  var scene = null;
  var ready = false;
  var on = false;
  var wantDom = false;
  var dom = null;
  var pollTimer = null;
  var pollElapsed = 0;
  var rafId = null;
  var lastAgg = null;
  var reduced = false;

  var accRender = 0;
  var accPass = 0;
  var frameMsSum = 0;
  var renderMsSum = 0;
  var passSum = 0;
  var frameCount = 0;
  var spanStart = 0;
  var lastFrameTime = 0;

  try {
    reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) { reduced = false; }

  function now() {
    if (window.performance && performance.now) return performance.now();
    return Date.now();
  }

  function hasPerfParam() {
    try {
      return new URLSearchParams(location.search).get('perf') === '1';
    } catch (e) {
      return /[?&]perf=1(&|$)/.test(location.search || '');
    }
  }

  function buildDom() {
    if (dom || !wantDom) return;
    var host = document.body || document.documentElement;
    if (!host) return;
    dom = document.createElement('div');
    dom.id = 'clPerfProbe';
    var s = dom.style;
    s.position = 'fixed';
    s.right = '12px';
    s.bottom = '64px';
    s.fontSize = '11px';
    s.fontFamily = 'var(--mono)';
    s.color = 'var(--ink-2)';
    s.pointerEvents = 'none';
    s.zIndex = '60';
    dom.textContent = '\u2026';
    host.appendChild(dom);
  }

  function writeDom(msFrame, msRender, msJs, passes, dpr, degrade) {
    if (!dom) return;
    var lodTag = (window.CLAbyssLOD && window.CLAbyssLOD.audit) ? ' \u00b7 ' + window.CLAbyssLOD.audit().tag : '';
    dom.textContent =
      msFrame.toFixed(1) + ' ms/frame \u00b7 render ' + msRender.toFixed(1) +
      ' \u00b7 js ' + msJs.toFixed(1) +
      ' \u00b7 ' + Math.round(passes) + ' pass \u00b7 dpr ' + dpr +
      ' \u00b7 ' + degrade + lodTag;
  }

  function wrap() {
    if (!scene || !scene.renderer) return false;
    var r = scene.renderer;
    if (typeof r.render !== 'function') return false;
    if (r.__clPerfWrapped) return true;
    var orig = r.render;
    r.render = function () {
      var t0 = now();
      try {
        return orig.apply(this, arguments);
      } finally {
        accRender += now() - t0;
        accPass += 1;
      }
    };
    r.__clPerfWrapped = true;
    r.__clPerfOrig = orig;
    return true;
  }

  function frame(t) {
    if (!on) return;
    rafId = window.requestAnimationFrame(frame);
    if (!lastFrameTime) {
      lastFrameTime = t;
      spanStart = t;
      accRender = 0;
      accPass = 0;
      return;
    }
    var dt = t - lastFrameTime;
    lastFrameTime = t;
    frameMsSum += dt;
    renderMsSum += accRender;
    passSum += accPass;
    frameCount += 1;
    accRender = 0;
    accPass = 0;
    if (t - spanStart >= WIN_MS) {
      publish();
      frameMsSum = 0;
      renderMsSum = 0;
      passSum = 0;
      frameCount = 0;
      spanStart = t;
    }
  }

  function publish() {
    if (!frameCount) return;
    var msFrame = frameMsSum / frameCount;
    var msRender = renderMsSum / frameCount;
    var msJs = msFrame > msRender ? msFrame - msRender : 0;
    var passes = passSum / frameCount;
    var dpr = 1;
    var degrade = 'L0';
    try { if (scene && scene.quality) dpr = scene.quality().dpr; } catch (e) {}
    try {
      if (scene && scene.perf) {
        var d = scene.perf().degrade;
        if (typeof d === 'string') degrade = d;
        else if (typeof d === 'number') degrade = 'L' + d;
        else if (d === true) degrade = 'L1';
      }
    } catch (e) {}
    lastAgg = { step: msFrame, render: msRender, js: msJs, passes: passes };
    writeDom(msFrame, msRender, msJs, passes, dpr, degrade);
  }

  function startLoop() {
    if (!on || !ready || rafId != null || !window.requestAnimationFrame) return;
    lastFrameTime = 0;
    spanStart = 0;
    frameCount = 0;
    frameMsSum = 0;
    renderMsSum = 0;
    passSum = 0;
    rafId = window.requestAnimationFrame(frame);
  }

  function stopLoop() {
    if (rafId != null) {
      try { window.cancelAnimationFrame(rafId); } catch (e) {}
      rafId = null;
    }
    lastFrameTime = 0;
  }

  function adopt(sc) {
    scene = sc;
    ready = true;
    stopPoll();
    wrap();
    buildDom();
    if (on) startLoop();
  }

  function poll() {
    var sc = (window.__cl && window.__cl.scene) ? window.__cl.scene : null;
    if (sc && sc.renderer && typeof sc.renderer.render === 'function' && typeof sc.step === 'function') {
      adopt(sc);
      return;
    }
    pollElapsed += POLL_MS;
    if (pollElapsed >= POLL_MAX) stopPoll();
  }

  function startPoll() {
    if (ready || pollTimer != null) return;
    pollTimer = window.setInterval(poll, POLL_MS);
    poll();
  }

  function stopPoll() {
    if (pollTimer != null) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function sample(n) {
    n = Math.max(1, Math.floor(n || 1));
    if (!scene || typeof scene.step !== 'function') return null;
    wrap();
    var t0 = now();
    var r0 = accRender;
    var p0 = accPass;
    for (var i = 0; i < n; i++) scene.step(1);
    var t1 = now();
    var step = (t1 - t0) / n;
    var render = (accRender - r0) / n;
    var passes = (accPass - p0) / n;
    var js = step > render ? step - render : 0;
    lastAgg = { step: step, render: render, js: js, passes: passes };
    return lastAgg;
  }

  function setOn(b) {
    on = !!b;
    if (on) {
      if (ready) { buildDom(); startLoop(); }
    } else {
      stopLoop();
    }
    return on;
  }

  function last() { return lastAgg; }

  function stats() {
    return { ready: ready, on: on, dom: !!dom, last: lastAgg, reduced: reduced };
  }

  wantDom = hasPerfParam();
  on = wantDom;
  startPoll();

  window.CLPerfProbe = {
    name: NAME,
    sample: sample,
    last: last,
    setOn: setOn,
    stats: stats
  };
})();
