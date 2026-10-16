(function () {
  'use strict';

  var NAME = 'tree-twig-pick';
  var RADIUS = 14;
  var DRAG_TOL = 5;
  var POLL_MS = 100;
  var POLL_MAX = 15000;

  var on = true;
  var ready = false;
  var attached = false;
  var hoverEv = -1;
  var lastPick = -1;
  var timer = null;

  var rafPending = false, pendX = 0, pendY = 0;
  var downActive = false, downMoved = false, downOnCanvas = false, downX = 0, downY = 0;
  var CACHE = null;
  var sigShape = null, sigVW = 0, sigVH = 0;
  var sigM = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  var sigP = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function str(v) { return v == null ? '' : String(v); }
  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function ok3(p) { return !!(p && p.length >= 3 && isFinite(p[0]) && isFinite(p[1]) && isFinite(p[2])); }

  function lowTier() {
    try {
      if (document.documentElement && document.documentElement.dataset.tier === 'low') return true;
    } catch (e) {}
    try {
      var hc = (typeof navigator !== 'undefined') ? navigator.hardwareConcurrency : 0;
      return !!hc && hc <= 4;
    } catch (e2) { return false; }
  }

  function reducedMotion() {
    try {
      return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) { return false; }
  }

  function hasDeps() {
    try {
      var stage = window.CLTreeStage, ghost = window.CLTreeGhost,
        anchor = window.CLTreeAnchor, events = window.CLTreeEvents;
      return !!(stage && ghost && anchor && events
        && typeof stage.active === 'function'
        && typeof ghost.shapeOf === 'function'
        && typeof anchor.toScreen === 'function'
        && typeof events.pick === 'function'
        && typeof events.clear === 'function');
    } catch (e) { return false; }
  }

  function isActive() {
    try {
      return !!(window.CLTreeStage && window.CLTreeStage.active());
    } catch (e) { return false; }
  }

  function shape() {
    try {
      var g = window.CLTreeGhost;
      if (!g || typeof g.shapeOf !== 'function') return null;
      return g.shapeOf();
    } catch (e) { return null; }
  }

  function hoverName() {
    try {
      var c = window.__cl;
      if (c && c.scene && typeof c.scene.hoverName === 'function') {
        var n = c.scene.hoverName();
        return (typeof n === 'string' && n.length > 0) ? n : '';
      }
    } catch (e) {}
    return '';
  }

  function proj(p) {
    if (!p || p.length < 3) return null;
    var r;
    try { r = window.CLTreeAnchor.toScreen(p); } catch (e) { return null; }
    if (!r || r.on === false) return null;
    if (typeof r.x !== 'number' || typeof r.y !== 'number') return null;
    if (!isFinite(r.x) || !isFinite(r.y)) return null;
    return r;
  }

  function dist2(ax, ay, bx, by) {
    var dx = ax - bx, dy = ay - by;
    return dx * dx + dy * dy;
  }

  function cam() {
    try { return (window.CLTreeAnchor && CLTreeAnchor.cam) ? CLTreeAnchor.cam() : null; } catch (e) { return null; }
  }
  function fill16(dst, src) {
    for (var i = 0; i < 16; i++) dst[i] = (src && typeof src[i] === 'number') ? src[i] : NaN;
  }
  function same16(a, b) {
    for (var i = 0; i < 16; i++) if (a[i] !== b[i]) return false;
    return true;
  }
  function indexFresh(s) {
    if (sigShape !== s) return false;
    if (sigVW !== window.innerWidth || sigVH !== window.innerHeight) return false;
    var c = cam();
    if (!c) return false;
    try { if (c.updateMatrixWorld) c.updateMatrixWorld(); } catch (e) { return false; }
    var m = c.matrixWorld && c.matrixWorld.elements;
    var p = c.projectionMatrix && c.projectionMatrix.elements;
    if (!m || !p) return false;
    return same16(m, sigM) && same16(p, sigP);
  }
  function markFresh(s) {
    sigShape = s; sigVW = window.innerWidth || 0; sigVH = window.innerHeight || 0;
    var c = cam();
    if (!c) { fill16(sigM, null); fill16(sigP, null); return; }
    try { if (c.updateMatrixWorld) c.updateMatrixWorld(); } catch (e) {}
    fill16(sigM, c.matrixWorld && c.matrixWorld.elements);
    fill16(sigP, c.projectionMatrix && c.projectionMatrix.elements);
  }

  function projectPts(pts) {
    var n = pts.length, px = new Array(n), py = new Array(n), pn = new Array(n), cum = new Array(n);
    var total = 0, any = false, i, r;
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (i = 0; i < n; i++) {
      r = proj(pts[i]);
      if (r) {
        px[i] = r.x; py[i] = r.y; pn[i] = 1; any = true;
        if (r.x < x0) x0 = r.x; if (r.x > x1) x1 = r.x;
        if (r.y < y0) y0 = r.y; if (r.y > y1) y1 = r.y;
      } else { px[i] = 0; py[i] = 0; pn[i] = 0; }
      if (i > 0 && ok3(pts[i - 1]) && ok3(pts[i])) {
        var ax = pts[i - 1][0] - pts[i][0], ay = pts[i - 1][1] - pts[i][1], az = pts[i - 1][2] - pts[i][2];
        total += Math.sqrt(ax * ax + ay * ay + az * az);
      }
      cum[i] = total;
    }
    if (!any || !(total > 0)) return null;
    return { px: px, py: py, pn: pn, cum: cum, total: total,
      bbox: { x0: x0, y0: y0, x1: x1, y1: y1 } };
  }

  function occPos(x, path) {
    if (x && x.pos && x.pos.length >= 3 && isFinite(x.pos[0]) && isFinite(x.pos[1]) && isFinite(x.pos[2])) {
      return [x.pos[0], x.pos[1], x.pos[2]];
    }
    if (x && x.length >= 3 && isFinite(x[0]) && isFinite(x[1]) && isFinite(x[2])) {
      return [x[0], x[1], x[2]];
    }
    var t = (x && isFinite(x.at)) ? +x.at : (isFinite(x) ? +x : null);
    if (t != null && path && path.pts && path.pts.length) {
      var u = (t < 0 ? 0 : (t > 1 ? 1 : t)) * (path.pts.length - 1);
      var a = Math.floor(u), b = Math.min(path.pts.length - 1, a + 1), f = u - a;
      var pa = path.pts[a], pb = path.pts[b];
      return [pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f, pa[2] + (pb[2] - pa[2]) * f];
    }
    return null;
  }
  function pathOccurrence(path, evIdx) {
    if (!path) return null;
    var ep = path.eventPositions, map = path.evPos, i, evs;
    if (ep && !ep.length && ep[evIdx]) { var q = occPos(ep[evIdx], path); if (q) return q; }
    if (map && map[evIdx]) { var q2 = occPos(map[evIdx], path); if (q2) return q2; }
    if (ep && ep.length) {
      evs = path.events || [];
      for (i = 0; i < evs.length; i++) {
        if (Math.floor(num(evs[i], -1)) !== evIdx) continue;
        var q3 = occPos(ep[i], path); if (q3) return q3;
      }
    }
    return null;
  }
  function linePosFrac(path, evs) {
    var out = [], i, v, pmax = 0, ok = false, ep = path.eventPositions, sc;
    if (ep && ep.length === evs.length) {
      ok = true;
      for (i = 0; i < evs.length; i++) { v = +ep[i]; if (!isFinite(v) || v < 0) { ok = false; break; } if (v > pmax) pmax = v; }
      if (ok) {
        sc = pmax > 1.0001 ? pmax : 1;
        for (i = 0; i < evs.length; i++) out.push((+ep[i]) / sc);
        return out;
      }
    }
    out = []; pmax = 0; ok = true;
    for (i = 0; i < evs.length; i++) {
      var rec = path.evPos && path.evPos[evs[i]];
      v = (rec && isFinite(rec.at)) ? +rec.at : NaN;
      if (!isFinite(v)) { ok = false; break; }
      if (v > pmax) pmax = v;
      out.push(v);
    }
    if (!ok) return null;
    sc = pmax > 1.0001 ? pmax : 1;
    for (i = 0; i < out.length; i++) out[i] = out[i] / sc;
    return out;
  }

  function rebuild(s) {
    var mode = (s && s.logical && s.threadPaths) ? 'logical' : 'legacy';
    var anchors = (s && s.eventAnchors) || null;
    var lines = [], twigs = [], i, j, key, p, geo, evs, occ, i2, pos, r;
    if (mode === 'logical') {
      for (key in s.threadPaths) {
        if (!hasOwn(s.threadPaths, key)) continue;
        p = s.threadPaths[key];
        if (!p || !p.pts || p.pts.length < 2) continue;
        geo = projectPts(p.pts);
        if (!geo) continue;
        evs = (p.events || []).slice(0);
        if (!evs.length && p.evPos) {
          for (i2 in p.evPos) if (hasOwn(p.evPos, i2)) evs.push(Math.floor(num(i2, -1)));
        }
        occ = [];
        for (j = 0; j < evs.length; j++) {
          pos = pathOccurrence(p, evs[j]);
          if (!pos && anchors && anchors[evs[j]]) pos = anchors[evs[j]].pos;
          r = pos ? proj(pos) : null;
          occ.push(r ? { x: r.x, y: r.y } : null);
        }
        lines.push({ threadId: str(p.threadId || key), key: key, events: evs, geo: geo,
          anchorsScr: occ, posFrac: linePosFrac(p, evs), twig: null });
      }
    }
    var tw = (s && s.twigs) || [];
    for (i = 0; i < tw.length; i++) {
      var t = tw[i];
      if (!t || !t.pts || t.pts.length < 2) continue;
      var g2 = projectPts(t.pts);
      if (!g2) continue;
      twigs.push({ evIdx: Math.floor(num(t.evIdx, -1)), threadId: str(t.threadId || t.host || ''),
        geo: g2, twig: t });
    }
    CACHE = { mode: mode, lines: lines, twigs: twigs };
  }
  function index() {
    var s = shape();
    if (!s) { CACHE = null; sigShape = null; return null; }
    if (!CACHE || !indexFresh(s)) { rebuild(s); markFresh(s); }
    return CACHE;
  }

  function segHit(geo, sx, sy) {
    var px = geo.px, py = geo.py, pn = geo.pn, cum = geo.cum;
    var n = px.length, best = -1, bi = 0, bt = 0, i;
    for (i = 0; i + 1 < n; i++) {
      if (!pn[i] || !pn[i + 1]) continue;
      var ax = px[i], ay = py[i], bx = px[i + 1], by = py[i + 1];
      var vx = bx - ax, vy = by - ay, L2 = vx * vx + vy * vy;
      var t = L2 > 1e-9 ? ((sx - ax) * vx + (sy - ay) * vy) / L2 : 0;
      if (t < 0) t = 0; else if (t > 1) t = 1;
      var d2 = dist2(sx, sy, ax + vx * t, ay + vy * t);
      if (best < 0 || d2 < best) { best = d2; bi = i; bt = t; }
    }
    if (best < 0) return null;
    var span = cum[bi + 1] - cum[bi];
    return { d2: best, t: geo.total > 0 ? (cum[bi] + bt * span) / geo.total : 0, seg: bi };
  }

  function eventOnLine(ln, sx, sy, t) {
    var evs = ln.events, i, a, d, bestI = -1, bestD = Infinity, k;
    for (i = 0; i < evs.length; i++) {
      a = ln.anchorsScr[i];
      if (!a) continue;
      d = dist2(sx, sy, a.x, a.y);
      if (d < bestD) { bestD = d; bestI = i; }
    }
    if (bestI >= 0) return Math.floor(num(evs[bestI], -1));
    if (ln.posFrac) {
      bestI = -1; bestD = Infinity;
      for (i = 0; i < evs.length; i++) {
        d = Math.abs(ln.posFrac[i] - t);
        if (d < bestD) { bestD = d; bestI = i; }
      }
      if (bestI >= 0) return Math.floor(num(evs[bestI], -1));
    }
    if (!evs.length) return -1;
    k = Math.round((t < 0 ? 0 : (t > 1 ? 1 : t)) * (evs.length - 1));
    return Math.floor(num(evs[k], -1));
  }

  function nearest(sx, sy) {
    if (!on || !hasDeps() || !isActive()) return null;
    var ix = index();
    if (!ix) return null;
    var R2 = RADIUS * RADIUS, best = null, i, h, b, cand, ev;
    for (i = 0; i < ix.lines.length; i++) {
      var ln = ix.lines[i];
      b = ln.geo.bbox;
      if (sx < b.x0 - RADIUS || sx > b.x1 + RADIUS || sy < b.y0 - RADIUS || sy > b.y1 + RADIUS) continue;
      h = segHit(ln.geo, sx, sy);
      if (!h || h.d2 > R2) continue;
      ev = eventOnLine(ln, sx, sy, h.t);
      if (ev < 0) continue;
      cand = { evIdx: ev, threadId: ln.threadId, d: Math.sqrt(h.d2), d2: h.d2, twig: ln.twig, line: ln };
      if (!best || cand.d2 < best.d2) best = cand;
    }
    for (i = 0; i < ix.twigs.length; i++) {
      var tw = ix.twigs[i];
      b = tw.geo.bbox;
      if (sx < b.x0 - RADIUS || sx > b.x1 + RADIUS || sy < b.y0 - RADIUS || sy > b.y1 + RADIUS) continue;
      h = segHit(tw.geo, sx, sy);
      if (!h || h.d2 > R2) continue;
      if (!best || h.d2 < best.d2) best = { evIdx: tw.evIdx, threadId: tw.threadId, d: Math.sqrt(h.d2), d2: h.d2, twig: tw.twig };
    }
    return best;
  }

  function pickAt(sx, sy) {
    if (!on) return false;
    if (!hasDeps() || !isActive()) return false;
    var n = nearest(sx, sy);
    var events = window.CLTreeEvents;
    if (n && n.d <= RADIUS) {
      try { events.pick(n.evIdx, n.threadId); } catch (e) {}
      lastPick = n.evIdx;
      return true;
    }
    try { events.clear(); } catch (e2) {}
    lastPick = -1;
    return false;
  }

  function cardHit(x, y) {
    var C = window.CLTreeEventCard;
    if (C && typeof C.hitTest === 'function') { try { return !!C.hitTest(x, y); } catch (e) {} }
    return false;
  }
  function domBlocks(x, y) {
    if (cardHit(x, y)) return true;
    try {
      var el = document.elementFromPoint(x, y);
      if (el && el.tagName !== 'CANVAS') return true;
    } catch (e) {}
    return false;
  }
  function canvasEl() {
    try { return document.querySelector('canvas'); } catch (e) { return null; }
  }
  function setCursor(v) {
    var cv = canvasEl();
    if (cv && cv.style) cv.style.cursor = v;
  }

  var hoverDirty = false, sinkReady = false, sinkKind = '';
  function doHover(x, y) {
    if (!on || !hasDeps() || !isActive()) { hoverEv = -1; setCursor(''); return; }
    if (lowTier() || hoverName() || domBlocks(x, y)) { hoverEv = -1; setCursor(''); return; }
    var n = nearest(x, y);
    if (n && n.d <= RADIUS) { hoverEv = n.evIdx; setCursor('pointer'); }
    else { hoverEv = -1; setCursor(''); }
  }
  function hoverFrame() {
    rafPending = false;
    if (!hoverDirty) return;
    hoverDirty = false;
    doHover(pendX, pendY);
  }
  function ensureSink() {
    if (sinkReady) return;
    var A = window.CLArcana;
    if (A && typeof A.register === 'function') {
      try {
        if (A.register({ name: NAME + '-hover', build: function () {}, update: hoverFrame })) { sinkReady = true; sinkKind = 'scene'; return; }
      } catch (e) {}
    }
    if (typeof requestAnimationFrame === 'function') { sinkReady = true; sinkKind = 'raf'; }
  }
  function scheduleHover() {
    if (!sinkReady) ensureSink();
    if (!sinkReady) { rafPending = false; return; }
    if (sinkKind === 'raf') requestAnimationFrame(hoverFrame);
  }

  function onMove(e) {
    if (!on || !e) return;
    if (typeof e.clientX === 'number') pendX = e.clientX;
    if (typeof e.clientY === 'number') pendY = e.clientY;
    if (!rafPending) {
      rafPending = true;
      hoverDirty = false;
      doHover(pendX, pendY);
      scheduleHover();
    } else {
      hoverDirty = true;
    }
  }

  function onDown(e) {
    if (!e) return;
    downActive = true; downMoved = false;
    downOnCanvas = !!(e.target && e.target.tagName === 'CANVAS');
    downX = (typeof e.clientX === 'number') ? e.clientX : 0;
    downY = (typeof e.clientY === 'number') ? e.clientY : 0;
  }
  function onUp(e) {
    if (!downActive) return;
    var x = (typeof e.clientX === 'number') ? e.clientX : downX;
    var y = (typeof e.clientY === 'number') ? e.clientY : downY;
    if (dist2(x, y, downX, downY) > DRAG_TOL * DRAG_TOL) downMoved = true;
    downActive = false;
  }

  function onClick(e) {
    if (!on || !e || !e.target) return;
    if (e.target.tagName !== 'CANVAS') return;
    if (downMoved) { downMoved = false; return; }
    if (hoverName()) return;
    var x = (typeof e.clientX === 'number') ? e.clientX : 0;
    var y = (typeof e.clientY === 'number') ? e.clientY : 0;
    if (domBlocks(x, y)) return;
    pickAt(x, y);
  }

  function attach() {
    if (attached) return;
    attached = true;
    window.addEventListener('click', onClick, true);
    window.addEventListener('pointermove', onMove, false);
    document.addEventListener('pointermove', onMove, false);
    window.addEventListener('pointerdown', onDown, true);
    window.addEventListener('pointerup', onUp, true);
    ensureSink();
  }

  function setOn(b) {
    on = !!b;
    if (!on) {
      hoverEv = -1;
      rafPending = false;
      setCursor('');
    }
  }

  function radius() { return RADIUS; }

  function stats() {
    return {
      name: NAME,
      on: on,
      ready: ready,
      active: isActive(),
      hoverEv: hoverEv,
      lastPick: lastPick,
      radius: RADIUS,
      mode: CACHE ? CACHE.mode : '',
      lines: CACHE ? CACHE.lines.length : 0,
      low: lowTier(),
      reducedMotion: reducedMotion()
    };
  }

  function boot() {
    if (hasDeps()) { ready = true; attach(); return; }
    var waited = 0;
    timer = setInterval(function () {
      if (hasDeps()) {
        ready = true;
        if (timer) { clearInterval(timer); timer = null; }
        attach();
        return;
      }
      waited += POLL_MS;
      if (waited >= POLL_MAX) {
        clearInterval(timer);
        timer = null;
        ready = false;
      }
    }, POLL_MS);
  }

  boot();

  window.CLTwigPick = {
    name: NAME,
    pickAt: pickAt,
    nearest: nearest,
    radius: radius,
    setOn: setOn,
    stats: stats
  };
})();
