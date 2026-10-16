(function (g) {
  'use strict';
  var doc = document, SEL = '.skd-deck__viewport';
  var host = null, rect = null, on = false, moves = 0;
  var ax = { x: 0, v: 0 }, ay = { x: 0, v: 0 }, tx = 0, ty = 0, el = null, live = false, hooked = null, offFrame = null, lowOn = false, frames = 0, flips = 0;
  var az = { x: 0, v: 0 }, tz = 0, idle = 0, rests = 0, IDLE = 0.7;

  function T() { return g.CLSkyTokens; }
  function tok() { var t = T() && T().CARD3D; return t || { tilt: 3.2 }; }
  function spr(k) { var s = T() && T().SPRING && T().SPRING[k]; return s || (k === 'back' ? { w: 11, z: 0.38 } : { w: 30, z: 1 }); }
  function sceneLow() {
    var s = g.CLScene && g.CLScene.current, q = s && s.quality ? s.quality() : null;
    return !!(q && q.degrade >= 2);
  }
  function syncLow() {
    var low = sceneLow();
    if (doc.body && low !== lowOn) { doc.body.classList.toggle('sky-cards-low', low); lowOn = low; }
    return low;
  }
  function still() {
    if (sceneLow()) { return true; }
    if (T() && T().reduced && T().reduced()) { return true; }
    if (doc.body && doc.body.classList.contains('skylab-still')) { return true; }
    var d = doc.documentElement.getAttribute('data-tier');
    return d === 'low';
  }
  var clamp = g.CLSkyUtil.clamp;

  function clear(el) {
    if (!el) { return; }
    el.style.removeProperty('--skc3-tx');
    el.style.removeProperty('--skc3-ty');
    el.style.removeProperty('--skc3-oy');
    el.style.removeProperty('--skc3-z');
  }
  function origin(el) { if (el && rect) { el.style.setProperty('--skc3-oy', (el.scrollTop + rect.height / 2).toFixed(0) + 'px'); } }
  function zero() { ax.x = ax.v = ay.x = ay.v = az.x = az.v = 0; }
  function settle() { clear(el); el = null; live = false; zero(); tx = ty = tz = 0; }
  function drop() { host = null; rect = null; tx = ty = tz = 0; if (!hooked) { settle(); } }
  function hook() {
    var sc = g.CLScene && g.CLScene.current;
    if (!sc || !sc.registerFrameHook || sc === hooked) { return; }
    if (offFrame) { offFrame(); }
    hooked = sc; offFrame = sc.registerFrameHook(frame);
  }
  function step(s, to, k, h) {
    g.CLSkyUtil.spring(s, to, k.w, k.z, h);
  }
  function frame(dt) {
    syncLow();
    if (!live || !el) { return; }
    if (still()) { settle(); return; }
    dt = Math.min(Math.max(+dt || 0, 0), 0.1);
    if (host) { idle += dt; if (idle > IDLE) { tx = ty = tz = 0; } }
    var rest = !host || idle > IDLE, k = spr(rest ? 'back' : 'follow'), kz = spr('follow'), n, h, i, sx = ax.x;
    n = Math.max(1, Math.ceil(dt * 240)); h = dt / n;
    for (i = 0; i < n; i++) { step(ax, tx, k, h); step(ay, ty, k, h); step(az, tz, kz, h); }
    if (rest && sx !== 0 && (sx > 0) !== (ax.x > 0)) { flips++; }
    frames++;
    if (rest && Math.abs(ax.x) < 0.01 && Math.abs(ay.x) < 0.01 && Math.abs(ax.v) < 0.05 && Math.abs(ay.v) < 0.05 && Math.abs(az.x) < 0.002 && Math.abs(az.v) < 0.02) {
      rests++;
      if (!host) { settle(); } else { clear(el); zero(); live = false; }
      return;
    }
    el.style.setProperty('--skc3-tx', ax.x.toFixed(2) + 'deg');
    el.style.setProperty('--skc3-ty', ay.x.toFixed(2) + 'deg');
    el.style.setProperty('--skc3-z', az.x.toFixed(3));
  }

  function onMove(e) {
    if (still()) { if (el) { settle(); } host = null; rect = null; return; }
    var t = e.target && e.target.closest ? e.target.closest(SEL) : null;
    if (!t) { if (host) { drop(); } return; }
    if (t !== host) { host = t; rect = null; }
    if (el !== t) { settle(); el = t; }
    if (!rect) { rect = t.getBoundingClientRect(); if (rect.width > 0 && rect.height > 0) { origin(t); } }
    if (!(rect.width > 0 && rect.height > 0)) { rect = null; return; }
    var mx = clamp((e.clientX - rect.left) / rect.width, 0, 1) - 0.5;
    var my = clamp((e.clientY - rect.top) / rect.height, 0, 1) - 0.5;
    var k = +tok().tilt || 3.2;
    tx = mx * 2 * k; ty = -my * 2 * k; tz = 1; idle = 0;
    hook(); live = true; flips = 0; moves++;
    if (!hooked) { ax.x = tx; ay.x = ty; az.x = 1; t.style.setProperty('--skc3-tx', tx.toFixed(2) + 'deg'); t.style.setProperty('--skc3-ty', ty.toFixed(2) + 'deg'); t.style.setProperty('--skc3-z', '1'); }
  }
  function onOut(e) {
    if (!host) { return; }
    var to = e.relatedTarget, inside = to && to.closest && to.closest(SEL) === host;
    if (!inside) { drop(); }
  }
  function onScroll(e) { if (el && e.target === el && (rect || live)) { if (!rect) { rect = el.getBoundingClientRect(); } origin(el); } }
  function onResize() { rect = null; }
  function onGraph() { hook(); syncLow(); }

  function attach() {
    if (on) { return; }
    on = true;
    doc.addEventListener('cl:graph-ready', onGraph, false);
    onGraph();
    doc.addEventListener('pointermove', onMove, { passive: true });
    doc.addEventListener('pointerout', onOut, { passive: true });
    doc.addEventListener('scroll', onScroll, true);
    g.addEventListener('resize', onResize, { passive: true });
  }
  function dispose() {
    if (!on) { return; }
    on = false;
    doc.removeEventListener('cl:graph-ready', onGraph, false);
    if (offFrame) { offFrame(); offFrame = null; } hooked = null;
    if (doc.body) { doc.body.classList.remove('sky-cards-low'); } lowOn = false;
    doc.removeEventListener('pointermove', onMove, { passive: true });
    doc.removeEventListener('pointerout', onOut, { passive: true });
    doc.removeEventListener('scroll', onScroll, true);
    g.removeEventListener('resize', onResize, { passive: true });
    host = null; rect = null; settle();
  }

  attach();

  g.CLSkyCards3D = {
    stats: function () {
      var e = el || host;
      return { on: on, host: host ? (host.className || '') : null, moves: moves, still: still(), live: live, hooked: !!hooked, frames: frames, flips: flips, rests: rests,
        depth: +az.x.toFixed(3), idle: +idle.toFixed(2), target: [+tx.toFixed(2), +ty.toFixed(2)],
        tx: e ? e.style.getPropertyValue('--skc3-tx') : '', ty: e ? e.style.getPropertyValue('--skc3-ty') : '', z: e ? e.style.getPropertyValue('--skc3-z') : '' };
    },
    dispose: dispose
  };
})(window);
