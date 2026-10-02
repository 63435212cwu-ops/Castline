/* Castline · atlas-motion-polish.js
 * Demand-driven optical motion. Graph geometry and pointer capture stay with
 * their engines; one delegated gesture observer adds spring light, finite
 * selection waves and lens transitions. Nothing runs while the field rests.
 */
(function (g) {
  'use strict';
  var d = g.document;
  if (!d || !d.documentElement) return;
  var root = d.documentElement, states = [], bound = [], observer = null, bodyObserver = null;
  var raf = 0, lastFrame = 0, scanTimer = 0, initDone = false, reduced = false, low = false;
  var gesture = null, pulses = [], canvas = null, ctx = null, transitTimer = 0, lastLens = '';
  var world = { x: 0, y: -.16, tx: 0, ty: -.16, vx: 0, vy: 0, energy: 0, dx: 0, dy: 0 };
  var HOST = '#stage,.cl-ann-layer,#gemHost,.cl-gem-host,.cl-atlas-stage,.cl-domains-lamps,.afb-stage,.afb-gem,.atlas-local-layer,.sky-disc,.sky-field,.sky-compass';
  var HIT = '.is-hit,.cl-gem-vertex,.cl-gem-badge,.cl-gem-arc__line,.cl-gem-arc__hit,.cl-domains-lamp,.afb-star,.afb-event,.afb-arc-target,.afb-relation-target,.atlas-local-node,.atlas-local-page,.sd-knot,.sd-arc,.sd-dot,.sf-star,.skc-sat,.cl-lab[role="button"]';
  var CONTROL = '.aph-badge,.aph-gbtn,.sky-icon,.sky-plot,.sky-speed,.sky-crumb button,.sky-view button,.afb-nav button,.atlas-local-page';
  var SURFACE = '#gl,#labels,.cl-ann-svg,.afb-map,.sky-disc,.sky-field,.sky-compass';
  function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }
  function now() { return g.performance && g.performance.now ? g.performance.now() : Date.now(); }
  function quiet() {
    try { if (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) return true; } catch (e) {}
    if (d.body && (d.body.classList.contains('skylab-still') || d.body.classList.contains('atlas-motion-still'))) return true;
    try { if (g.CLAtlasState && g.CLAtlasState.get && g.CLAtlasState.get().reduced) return true; } catch (e1) {}
    try { if (g.CLSkyTokens && g.CLSkyTokens.reduced && g.CLSkyTokens.reduced()) return true; } catch (e2) {}
    return false;
  }
  function refreshEnv() {
    reduced = quiet();
    low = !!(d.body && d.body.getAttribute('data-tier') === 'low');
    try { low = low || !!(g.CLOrbit3DTier && g.CLOrbit3DTier.get && g.CLOrbit3DTier.get() === 'low'); } catch (e) {}
    low = low || !!(g.navigator && g.navigator.hardwareConcurrency && g.navigator.hardwareConcurrency <= 4);
    root.classList.toggle('atlas-motion-quiet', reduced);
    root.classList.toggle('atlas-motion-low', low);
    if (reduced) { pulses.length = 0; resetWorld(); clearCanvas(); }
  }
  function listen(el, type, fn, opts) { el.addEventListener(type, fn, opts || false); bound.push([el, type, fn, opts || false]); }
  function closest(el, selector) { return el && el.nodeType === 1 && el.closest ? el.closest(selector) : null; }
  function active() {
    var b = d.body;
    return !!(b && (b.classList.contains('sky-shell') || b.classList.contains('atlas-workspace') || b.classList.contains('atlas-2d') || b.classList.contains('is-ann') || b.classList.contains('is-gem') || d.querySelector('.afb:not([hidden])')));
  }
  function kind(host) {
    if (host.id === 'stage') return 'stage';
    if (host.matches('#gemHost,.cl-gem-host,.afb-gem')) return 'gem';
    if (host.matches('.cl-ann-layer,.sky-disc')) return 'annulus';
    return 'field';
  }
  function bind(host) {
    for (var i = 0; i < states.length; i++) if (states[i].host === host) return states[i];
    var s = { host: host, kind: kind(host), hot: null, pressed: null, timer: 0, rect: null, rectAt: 0, target: null, current: null };
    if (s.kind !== 'stage') host.classList.add('atlas-motion-lens');
    if (s.kind === 'gem') host.classList.add('atlas-motion-tilt');
    states.push(s); return s;
  }
  function getState(target) { var h = closest(target, HOST); return h ? bind(h) : null; }
  function dropState(s) {
    clearPress(s, false); setHot(s, null);
    if (s.timer) g.clearTimeout(s.timer);
    s.host.classList.remove('atlas-motion-lens', 'atlas-motion-tilt');
    ['--amp-pointer-px', '--amp-pointer-py', '--amp-tilt-x', '--amp-tilt-y'].forEach(function (v) { s.host.style.removeProperty(v); });
  }
  function scan() {
    refreshEnv();
    for (var i = states.length - 1; i >= 0; i--) if (!states[i].host.isConnected) { dropState(states[i]); states.splice(i, 1); }
    var hosts = d.querySelectorAll(HOST);
    for (var j = 0; j < hosts.length; j++) bind(hosts[j]);
  }
  function hostIn(nodes) {
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (n.nodeType === 1 && (n.matches(HOST) || n.querySelector(HOST))) return true;
    }
    return false;
  }
  function scheduleScan() { if (!scanTimer) scanTimer = g.setTimeout(function () { scanTimer = 0; scan(); }, 0); }
  function setHot(s, node) {
    if (!s || s.hot === node) return;
    if (s.hot) {
      s.hot.classList.remove('atlas-motion-hot');
      var oldFace = closest(s.hot, '.cl-gem-face'); if (oldFace) oldFace.classList.remove('atlas-motion-face-hot');
    }
    s.hot = node;
    if (node) { node.classList.add('atlas-motion-hot'); var face = closest(node, '.cl-gem-face'); if (face) face.classList.add('atlas-motion-face-hot'); }
    s.host.classList.toggle('atlas-motion-hover', !!node);
  }
  function clearPress(s, commit) {
    if (!s) return;
    var n = s.pressed;
    if (n) {
      n.classList.remove('atlas-motion-press');
      if (commit && n.isConnected) {
        n.classList.add('atlas-motion-commit');
        if (s.timer) g.clearTimeout(s.timer);
        s.timer = g.setTimeout(function () { n.classList.remove('atlas-motion-commit'); s.timer = 0; }, reduced || low ? 120 : 620);
      }
    }
    s.pressed = null; s.host.classList.remove('atlas-motion-pressed');
  }
  function press(s, n) {
    clearPress(s, false);
    if (!n) return;
    n.classList.remove('atlas-motion-commit'); n.classList.add('atlas-motion-press');
    s.pressed = n; s.host.classList.add('atlas-motion-pressed');
  }
  function targetHost(s, ev) {
    if (!s || reduced || low) return;
    var t = now();
    if (!s.rect || t - s.rectAt > 220) { s.rect = s.host.getBoundingClientRect(); s.rectAt = t; }
    var r = s.rect, w = r.width || g.innerWidth || 1, h = r.height || g.innerHeight || 1;
    var px = clamp((ev.clientX - r.left) / w, 0, 1), py = clamp((ev.clientY - r.top) / h, 0, 1);
    s.target = { px: px, py: py, tx: (px - .5) * 7, ty: (.5 - py) * 5.2 };
    if (!s.current) s.current = { px: .5, py: .5, tx: 0, ty: 0 };
    schedule();
  }
  function targetWorld(ev) {
    if (reduced || low) return;
    world.tx = clamp(ev.clientX / (g.innerWidth || 1) * 2 - 1, -1, 1);
    world.ty = clamp(ev.clientY / (g.innerHeight || 1) * 2 - 1, -1, 1);
    schedule();
  }
  function resetWorld() {
    world.x = world.tx = world.vx = world.dx = 0; world.y = world.ty = -.16; world.vy = world.dy = world.energy = 0;
    root.style.setProperty('--amp-world-x', '0'); root.style.setProperty('--amp-world-y', '-0.16');
    root.style.setProperty('--amp-drift-x', '0px'); root.style.setProperty('--amp-drift-y', '0px'); root.style.setProperty('--amp-energy', '0');
    cameraFollow(0, 0);
  }
  var aimX = NaN, aimY = NaN;
  function cameraFollow(x, y) {
    /* A compass drag has two independent pointer owners: the SVG satellite
       layer and OrbitControls on the canvas.  The global motion polish used
       to keep feeding scene.aim() from pointermove while either owner was
       active, moving controls.target underneath the gesture.  That showed
       up as a small but measurable target drift on narrow viewports (and as
       a larger drift after a blank-space orbit).  The compass keeps its own
       optical CSS response; camera aim is intentionally neutral there. */
    var body = d.body;
    var compass = body && (body.classList.contains('sky-compass-on') || body.getAttribute('data-atlas-view') === 'gem');
    var skyShell = body && body.classList.contains('sky-shell');
    var tug = body && body.classList.contains('sky-tug-grabbing');
    /* 星空壳的相机基线属于读图操作；保持 aim 中性，仍让 CSS 世界层
       使用 world.x/world.y 做视觉视差。这样点星、拨盘和牵引共用一个
       不会被指针光学层悄悄改写的 camera target。 */
    if (reduced || low || skyShell || compass || tug || (gesture && gesture.moved)) { x = 0; y = 0; }
    x = clamp(x, -1, 1); y = clamp(y, -1, 1);
    if (isFinite(aimX) && Math.abs(aimX - x) < .002 && Math.abs(aimY - y) < .002) return;
    aimX = x; aimY = y;
    try {
      var app = g.CLApp, scene = app && typeof app.scene === 'function' ? app.scene() : null;
      if (scene && typeof scene.aim === 'function') scene.aim(x * 16, -y * 10, 0);
    } catch (e) {}
  }
  function makeCanvas() {
    if (canvas) return !!ctx;
    canvas = d.createElement('canvas'); canvas.className = 'atlas-motion-fx'; canvas.setAttribute('aria-hidden', 'true'); canvas.hidden = true;
    d.body.appendChild(canvas); ctx = canvas.getContext && canvas.getContext('2d'); sizeCanvas(); return !!ctx;
  }
  function sizeCanvas() {
    if (!canvas) return;
    var p = Math.min(g.devicePixelRatio || 1, 1.5);
    canvas.width = Math.round((g.innerWidth || 1) * p); canvas.height = Math.round((g.innerHeight || 1) * p); canvas.__ampDpr = p;
  }
  function clearCanvas() { if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height); if (canvas) canvas.hidden = true; }
  function colorFor(view) {
    var token = view === 'gem' || view === 'compass' ? '--abyss-mint-bright' : view === 'domains' || view === 'field' ? '--abyss-violet-bright' : '--abyss-gold';
    try { return g.getComputedStyle(root).getPropertyValue(token).trim() || g.getComputedStyle(root).getPropertyValue('--abyss-gold').trim(); } catch (e) { return 'white'; }
  }
  function wave(x, y, strong, view) {
    if (reduced || low || !makeCanvas()) return;
    if (pulses.length >= 8) pulses.shift();
    pulses.push({ x: x, y: y, start: now(), duration: strong ? 1100 : 620, strong: !!strong, color: colorFor(view), phase: Math.random() * 6.28 });
    canvas.hidden = false; schedule();
  }
  function drawWaves(t) {
    if (!ctx || !canvas || !pulses.length) { clearCanvas(); return false; }
    var p = canvas.__ampDpr || 1; ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.save(); ctx.scale(p, p); ctx.globalCompositeOperation = 'lighter';
    for (var i = pulses.length - 1; i >= 0; i--) {
      var a = pulses[i], u = clamp((t - a.start) / a.duration, 0, 1);
      if (u >= 1) { pulses.splice(i, 1); continue; }
      var e = 1 - Math.pow(1 - u, 3), radius = 8 + e * (a.strong ? Math.min(g.innerWidth, g.innerHeight) * .56 : 94), alpha = (1 - u) * (a.strong ? .34 : .58);
      ctx.strokeStyle = ctx.fillStyle = a.color; ctx.globalAlpha = alpha; ctx.lineWidth = a.strong ? .8 : 1;
      ctx.beginPath(); ctx.ellipse(a.x, a.y, radius, radius * (a.strong ? .72 : .82), -.25, 0, 6.283); ctx.stroke();
      ctx.globalAlpha = alpha * .42; ctx.beginPath(); ctx.ellipse(a.x, a.y, radius * .73, radius * .58, .35, a.phase, a.phase + 3.8); ctx.stroke();
      var count = a.strong ? 16 : 8;
      for (var j = 0; j < count; j++) {
        var angle = a.phase + j / count * 6.283, rr = radius * (j % 3 === 0 ? 1.14 : .9), x = a.x + Math.cos(angle) * rr, y = a.y + Math.sin(angle) * rr * .82;
        ctx.globalAlpha = alpha * (j % 3 === 0 ? .95 : .6); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - Math.cos(angle) * (a.strong ? 14 : 6) * (1 - u), y - Math.sin(angle) * 6 * (1 - u)); ctx.stroke();
      }
    }
    ctx.restore(); if (!pulses.length) clearCanvas(); return !!pulses.length;
  }
  function schedule() { if (!raf && g.requestAnimationFrame && !d.hidden) raf = g.requestAnimationFrame(frame); }
  function frame(t) {
    raf = 0; var dt = clamp(lastFrame ? (t - lastFrame) / 1000 : .016, .006, .032); lastFrame = t;
    var more = false;
    if (!reduced && !low) {
      world.vx += ((world.tx - world.x) * 118 - world.vx * 18) * dt; world.vy += ((world.ty - world.y) * 118 - world.vy * 18) * dt;
      world.x += world.vx * dt; world.y += world.vy * dt;
      world.energy *= Math.exp(-dt * (gesture ? 2.2 : 4.4)); world.dx *= Math.exp(-dt * 5); world.dy *= Math.exp(-dt * 5);
      cameraFollow(world.x, world.y);
      root.style.setProperty('--amp-world-x', world.x.toFixed(4)); root.style.setProperty('--amp-world-y', world.y.toFixed(4));
      root.style.setProperty('--amp-drift-x', (world.x * 12 + world.dx).toFixed(2) + 'px'); root.style.setProperty('--amp-drift-y', (world.y * 8 + world.dy).toFixed(2) + 'px'); root.style.setProperty('--amp-energy', world.energy.toFixed(3));
      more = Math.abs(world.tx - world.x) + Math.abs(world.ty - world.y) + Math.abs(world.vx) + Math.abs(world.vy) + world.energy + Math.abs(world.dx) + Math.abs(world.dy) > .006;
      var k = 1 - Math.exp(-dt * 13);
      for (var i = 0; i < states.length; i++) {
        var s = states[i], a = s.current, b = s.target; if (!a || !b || !s.host.isConnected) continue;
        a.px += (b.px - a.px) * k; a.py += (b.py - a.py) * k; a.tx += (b.tx - a.tx) * k; a.ty += (b.ty - a.ty) * k;
        s.host.style.setProperty('--amp-pointer-px', (a.px * 100).toFixed(2) + '%'); s.host.style.setProperty('--amp-pointer-py', (a.py * 100).toFixed(2) + '%');
        if (s.kind === 'gem') { s.host.style.setProperty('--amp-tilt-x', a.tx.toFixed(3) + 'deg'); s.host.style.setProperty('--amp-tilt-y', a.ty.toFixed(3) + 'deg'); }
        if (Math.abs(a.tx - b.tx) + Math.abs(a.ty - b.ty) > .008) more = true;
      }
    }
    if (drawWaves(t)) more = true;
    if (more) schedule(); else lastFrame = 0;
  }
  function currentLens() { var b = d.body; return b && (b.getAttribute('data-atlas-view') || (b.classList.contains('sky-compass-on') ? 'compass' : b.classList.contains('sky-plot-on') ? 'annulus' : 'domains')); }
  function transition(view) {
    if (!active() || reduced || low || !d.body) return;
    if (transitTimer) g.clearTimeout(transitTimer); d.body.classList.remove('atlas-motion-transit'); d.body.setAttribute('data-motion-lens', view || currentLens());
    g.requestAnimationFrame(function () { if (!initDone || reduced || !d.body) return; d.body.classList.add('atlas-motion-transit'); wave((g.innerWidth || 1) * .5, (g.innerHeight || 1) * .48, true, view); });
    transitTimer = g.setTimeout(function () { if (d.body) d.body.classList.remove('atlas-motion-transit'); transitTimer = 0; }, 1100);
  }
  function move(ev) {
    if (!active()) return;
    var s = getState(ev.target); targetHost(s, ev); targetWorld(ev);
    if (!gesture || ev.pointerId !== gesture.id) return;
    var dx = ev.clientX - gesture.x, dy = ev.clientY - gesture.y; gesture.x = ev.clientX; gesture.y = ev.clientY;
    if (!gesture.moved && Math.hypot(ev.clientX - gesture.x0, ev.clientY - gesture.y0) > (gesture.touch ? 9 : 5)) { gesture.moved = true; clearPress(gesture.state, false); d.body.classList.add('atlas-motion-dragging'); }
    if (gesture.moved && !reduced && !low) { world.energy = Math.min(1, world.energy + (Math.abs(dx) + Math.abs(dy)) / 65); world.dx = clamp(world.dx + dx * .08, -16, 16); world.dy = clamp(world.dy + dy * .06, -12, 12); schedule(); }
  }
  function down(ev) {
    if (!active() || (ev.button > 0 && ev.pointerType !== 'touch')) return;
    if (gesture && ev.pointerId !== gesture.id) { end(null, false); return; }
    var s = getState(ev.target), n = closest(ev.target, HIT), control = closest(ev.target, CONTROL);
    if (!s && !control) return; if (!n && !control && !closest(ev.target, SURFACE)) return;
    refreshEnv(); targetHost(s, ev); targetWorld(ev); if (s && n) press(s, n);
    gesture = { id: ev.pointerId, state: s, node: n, control: control, touch: ev.pointerType === 'touch', x0: ev.clientX, y0: ev.clientY, x: ev.clientX, y: ev.clientY, moved: false };
    if (gesture.touch && d.body) d.body.classList.add('atlas-motion-touch');
  }
  function end(ev, commit) {
    if (!gesture || (ev && ev.pointerId !== gesture.id)) return;
    var a = gesture; gesture = null; if (d.body) d.body.classList.remove('atlas-motion-dragging', 'atlas-motion-touch');
    var ok = commit && !a.moved; clearPress(a.state, ok); if (ok && (a.node || a.control)) wave(a.x, a.y, false, currentLens());
    if (a.touch && a.state) setHot(a.state, null); schedule();
  }
  function over(ev) { if (!active() || ev.pointerType === 'touch') return; var s = getState(ev.target); if (s) setHot(s, closest(ev.target, HIT)); }
  function out(ev) {
    var s = getState(ev.target); if (!s) return; var n = closest(ev.relatedTarget, HIT), next = getState(ev.relatedTarget);
    if (next !== s) { setHot(s, null); s.target = { px: .5, py: .5, tx: 0, ty: 0 }; schedule(); } else setHot(s, n);
    if (s.pressed && !(ev.relatedTarget && s.pressed.contains(ev.relatedTarget))) clearPress(s, false);
  }
  function reset() { end(null, false); for (var i = 0; i < states.length; i++) { setHot(states[i], null); clearPress(states[i], false); states[i].rect = null; } world.tx = 0; world.ty = -.16; schedule(); }
  function resize() { for (var i = 0; i < states.length; i++) states[i].rect = null; sizeCanvas(); }
  function init() {
    if (initDone || !d.body) return; initDone = true; scan(); lastLens = currentLens();
    listen(d, 'pointermove', move, { passive: true }); listen(d, 'pointerdown', down, { passive: true, capture: true }); listen(d, 'pointerup', function (e) { end(e, true); }, { passive: true, capture: true }); listen(d, 'pointercancel', function (e) { end(e, false); }, { passive: true, capture: true });
    listen(d, 'pointerover', over, { passive: true }); listen(d, 'pointerout', out, { passive: true });
    listen(d, 'focusin', function (e) { var s = getState(e.target); if (s) setHot(s, closest(e.target, HIT)); }); listen(d, 'focusout', function (e) { var s = getState(e.target); if (s) setHot(s, closest(e.relatedTarget, HIT)); });
    listen(d, 'keydown', function (e) { if (e.repeat || (e.key !== 'Enter' && e.key !== ' ')) return; var n = closest(e.target, HIT + ',' + CONTROL); if (!n || !active()) return; var r = n.getBoundingClientRect(); wave(r.left + r.width / 2, r.top + r.height / 2, false, currentLens()); });
    listen(g, 'blur', reset); listen(g, 'resize', resize, { passive: true }); listen(d, 'visibilitychange', function () { if (d.hidden) { reset(); pulses.length = 0; clearCanvas(); if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0; lastFrame = 0; } });
    listen(d, 'cl:atlas-view', function (e) { var v = e.detail && e.detail.view || currentLens(); if (v !== lastLens) { lastLens = v; transition(v); } refreshEnv(); }); listen(d, 'cl:atlas-stage', function () { refreshEnv(); transition(currentLens()); });
    if (g.MutationObserver) {
      observer = new g.MutationObserver(function (records) { for (var i = 0; i < records.length; i++) if (hostIn(records[i].addedNodes) || hostIn(records[i].removedNodes)) { scheduleScan(); return; } }); observer.observe(d.body, { childList: true, subtree: true });
      bodyObserver = new g.MutationObserver(function () { refreshEnv(); var next = currentLens(); if (next !== lastLens) { lastLens = next; transition(next); } }); bodyObserver.observe(d.body, { attributes: true, attributeFilter: ['class', 'data-tier', 'data-atlas-view'] });
    }
    try { var mq = g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)'); if (mq && mq.addEventListener) listen(mq, 'change', refreshEnv); } catch (e) {}
  }
  function dispose() {
    initDone = false; reset(); if (observer) observer.disconnect(); if (bodyObserver) bodyObserver.disconnect(); observer = bodyObserver = null;
    if (scanTimer) g.clearTimeout(scanTimer); if (transitTimer) g.clearTimeout(transitTimer); scanTimer = transitTimer = 0;
    for (var i = 0; i < bound.length; i++) bound[i][0].removeEventListener(bound[i][1], bound[i][2], bound[i][3]); bound.length = 0;
    for (var j = 0; j < states.length; j++) dropState(states[j]); states.length = 0; pulses.length = 0;
    if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0; lastFrame = 0; if (canvas) canvas.remove(); canvas = ctx = null;
    if (d.body) { d.body.classList.remove('atlas-motion-transit', 'atlas-motion-dragging', 'atlas-motion-touch'); d.body.removeAttribute('data-motion-lens'); }
    root.classList.remove('atlas-motion-quiet', 'atlas-motion-low'); resetWorld();
  }
  g.CLAtlasMotionPolish = { name: 'atlas-motion-polish', version: 'v2', init: init, scan: scan, dispose: dispose, stats: function () { return { hosts: states.length, reduced: reduced, low: low, raf: !!raf, waves: pulses.length, dragging: !!(gesture && gesture.moved), listeners: bound.length }; } };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', init, false); else init();
})(window);
