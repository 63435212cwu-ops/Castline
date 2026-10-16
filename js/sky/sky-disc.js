(function (g) {
  'use strict';
  var R_IN = 1.10, STEP = 2.0 * Math.PI / 180;
  var TILT_MS = 780;
  var MAIN_W = 8, MAIN_SUB_W = 4, NAMED_W0 = 1.4, NAMED_W1 = 2.2;
  var CLEAR_NAMED = 1.5, CLEAR_MAIN = 3.2, INK = 0.46, LAB_PAD = 3.5, LAB_GAP = 17.5, LINE_H = 1.22;
  var PX = { lane: 15, laneMin: 7, laneSpread: 12, laneMax: 30, groove: 2, grooveGap: 4, mainGap: 9, mainPitch: 8, bez: 20, line2: 17, num: 12, tail: 19, tick: 5, tickMinor: 2.5 };
  function loFrac(K) { return K >= 250 ? 0.45 : K <= 170 ? 0.30 : 0.30 + (K - 170) / 80 * 0.15; }
  var FIT_K = 0.92;
  var LIFT = 0.1;

  var mk = g.CLSkyUtil.svg, clamp = g.CLSkyUtil.clamp, reduced = g.CLSkyUtil.mediaReduced;
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function now() { return g.CLSkyUtil.nowMs(0); }

  function create(opts) {
    var scene = opts.scene, THREE = g.THREE, stage = opts.stage || document.getElementById('stage') || document.body;
    var M = null, rim = null, anchor = null, dead = false;
    var state = 'hidden', tilt = 0, tiltFrom = 0, tiltTo = 0, tiltT0 = -1;
    var items = [], byId = {}, geo = null;
    var prevKey = '', Wv = 0, Hv = 0, dirty = true, lastMove = 0, placePending = false, placedOnce = false;
    var hoverId = null, focusId = null, cursor = null, playing = false, calm = false;
    var tetherFor = null, tetherNames = [], tetherFrom = null;
    var L = {};
    var stats = { frames: 0, projections: 0, lastMs: 0, tunes: 0 };
    var P = null;

    var svg = mk('svg', 'sky-disc is-hidden');
    svg.setAttribute('aria-hidden', 'true');
    var defs = mk('defs', null, svg);
    var gBezel = mk('g', 'sd-bezel', svg), gDorm = mk('g', 'sd-dorm', svg), gQuiet = mk('g', 'sd-quiet', svg), gNamed = mk('g', 'sd-named', svg),
      gMain = mk('g', 'sd-main', svg), gDots = mk('g', 'sd-dots', svg), gHo = mk('g', 'sd-ho', svg),
      gCur = mk('g', 'sd-cursor', svg), gTeth = mk('g', 'sd-teth', svg), gLab = mk('g', 'sd-labels', svg), gHit = mk('g', 'sd-hits', svg);
    var labelsHost = stage.querySelector('#labels');
    if (labelsHost && labelsHost.parentNode === stage) stage.insertBefore(svg, labelsHost); else stage.appendChild(svg);

    var unitCtx = { CLEAR_MAIN: CLEAR_MAIN, CLEAR_NAMED: CLEAR_NAMED, INK: INK, LAB_GAP: LAB_GAP, LAB_PAD: LAB_PAD, LINE_H: LINE_H, LIFT: LIFT, MAIN_W: MAIN_W, MAIN_SUB_W: MAIN_SUB_W, NAMED_W0: NAMED_W0, NAMED_W1: NAMED_W1, R_IN: R_IN, STEP: STEP, THREE: THREE, angle: angle, clamp: clamp, defs: defs, drawCursor: drawCursor, ease: ease, estimateK: estimateK, gBezel: gBezel, gCur: gCur, gDorm: gDorm, gDots: gDots, gHit: gHit, gHo: gHo, gLab: gLab, gMain: gMain, gNamed: gNamed, gQuiet: gQuiet, gTeth: gTeth, knot: knot, mk: mk, now: now, opts: opts, scene: scene, stats: stats, svg: svg, tune: tune };
    function bindUnit(k, get, set) { Object.defineProperty(unitCtx, k, { get: get, set: set }); }
    bindUnit('M', function () { return M; }, function (v) { M = v; });
    bindUnit('rim', function () { return rim; }, function (v) { rim = v; });
    bindUnit('anchor', function () { return anchor; }, function (v) { anchor = v; });
    bindUnit('tilt', function () { return tilt; }, function (v) { tilt = v; });
    bindUnit('items', function () { return items; }, function (v) { items = v; });
    bindUnit('byId', function () { return byId; }, function (v) { byId = v; });
    bindUnit('geo', function () { return geo; }, function (v) { geo = v; });
    bindUnit('prevKey', function () { return prevKey; }, function (v) { prevKey = v; });
    bindUnit('Wv', function () { return Wv; }, function (v) { Wv = v; });
    bindUnit('Hv', function () { return Hv; }, function (v) { Hv = v; });
    bindUnit('dirty', function () { return dirty; }, function (v) { dirty = v; });
    bindUnit('placedOnce', function () { return placedOnce; }, function (v) { placedOnce = v; });
    bindUnit('hoverId', function () { return hoverId; }, function (v) { hoverId = v; });
    bindUnit('focusId', function () { return focusId; }, function (v) { focusId = v; });
    bindUnit('cursor', function () { return cursor; }, function (v) { cursor = v; });
    bindUnit('state', function () { return state; }, function (v) { state = v; });
    bindUnit('P', function () { return P; }, function (v) { P = v; });
    bindUnit('rev', function () { return rev; }, function (v) { rev = v; });
    bindUnit('builtGl', function () { return builtGl; }, function (v) { builtGl = v; });
    bindUnit('evChIdx', function () { return evChIdx; }, function (v) { evChIdx = v; });
    bindUnit('E', function () { return E; }, function (v) { E = v; });
    bindUnit('growT0', function () { return growT0; }, function (v) { growT0 = v; });
    bindUnit('staleHit', function () { return staleHit; }, function (v) { staleHit = v; });
    bindUnit('tetherFor', function () { return tetherFor; }, function (v) { tetherFor = v; });
    bindUnit('tetherNames', function () { return tetherNames; }, function (v) { tetherNames = v; });
    bindUnit('tetherFrom', function () { return tetherFrom; }, function (v) { tetherFrom = v; });
    bindUnit('tethEls', function () { return tethEls; }, function (v) { tethEls = v; });
    bindUnit('tethGl', function () { return tethGl; }, function (v) { tethGl = v; });
    var projectUnit = g.CLSkyDiscProject.create(unitCtx);
    var geomUnit = g.CLSkyDiscGeom.create(unitCtx);
    var tracksUnit = g.CLSkyDiscTracks.create(unitCtx);
    var labelsUnit = g.CLSkyDiscLabels.create(unitCtx);
    var layoutUnit = g.CLSkyDiscLayout.create(unitCtx);
    var threadsUnit = g.CLSkyDiscThreads.create(unitCtx);
    var rimOf = projectUnit.rimOf,
      ensureAnchor = projectUnit.ensureAnchor,
      applyTilt = projectUnit.applyTilt,
      computeMatrix = projectUnit.computeMatrix,
      proj = projectUnit.proj,
      zAt = projectUnit.zAt,
      projA = projectUnit.projA,
      center = projectUnit.center,
      samplesOf = geomUnit.samplesOf,
      pathOf = geomUnit.pathOf,
      ptsOf = geomUnit.ptsOf,
      dOfPts = geomUnit.dOfPts,
      clear = geomUnit.clear,
      build = geomUnit.build,
      evSlot = geomUnit.evSlot,
      descOf = geomUnit.descOf,
      noOf = geomUnit.noOf,
      track = tracksUnit.track,
      trackFor = tracksUnit.trackFor,
      at = tracksUnit.at,
      uprightTrack = tracksUnit.uprightTrack,
      footprint = tracksUnit.footprint,
      footprint2 = tracksUnit.footprint2,
      shape2 = tracksUnit.shape2,
      clash = tracksUnit.clash,
      arcClash = tracksUnit.arcClash,
      placeLabels = labelsUnit.placeLabels,
      followLabels = labelsUnit.followLabels,
      setTrack = labelsUnit.setTrack,
      reproject = layoutUnit.reproject,
      setTether = threadsUnit.setTether,
      drawTethers = threadsUnit.drawTethers;
    unitCtx.rimOf = rimOf;
    unitCtx.ensureAnchor = ensureAnchor;
    unitCtx.applyTilt = applyTilt;
    unitCtx.computeMatrix = computeMatrix;
    unitCtx.proj = proj;
    unitCtx.zAt = zAt;
    unitCtx.projA = projA;
    unitCtx.center = center;
    unitCtx.samplesOf = samplesOf;
    unitCtx.pathOf = pathOf;
    unitCtx.ptsOf = ptsOf;
    unitCtx.dOfPts = dOfPts;
    unitCtx.clear = clear;
    unitCtx.build = build;
    unitCtx.evSlot = evSlot;
    unitCtx.descOf = descOf;
    unitCtx.noOf = noOf;
    unitCtx.track = track;
    unitCtx.trackFor = trackFor;
    unitCtx.at = at;
    unitCtx.uprightTrack = uprightTrack;
    unitCtx.footprint = footprint;
    unitCtx.footprint2 = footprint2;
    unitCtx.shape2 = shape2;
    unitCtx.clash = clash;
    unitCtx.arcClash = arcClash;
    unitCtx.placeLabels = placeLabels;
    unitCtx.followLabels = followLabels;
    unitCtx.setTrack = setTrack;
    unitCtx.reproject = reproject;
    unitCtx.setTether = setTether;
    unitCtx.drawTethers = drawTethers;

    function on(t, f) { (L[t] = L[t] || []).push(f); }
    function emit(t, p) { (L[t] || []).slice().forEach(function (f) { try { f(p); } catch (e) { if (g.console) console.warn('[sky-disc]', e); } }); }

    var E = null;

    function angle(slot) { return g.CLSkyModel.angleAt(slot, M.nCh); }
    var rev = 0, builtGl = false, evChIdx = null;

    function knot(p, s) { return 'M' + p[0].toFixed(1) + ' ' + (p[1] - s).toFixed(1) + 'L' + (p[0] + s).toFixed(1) + ' ' + p[1].toFixed(1) + 'L' + p[0].toFixed(1) + ' ' + (p[1] + s).toFixed(1) + 'L' + (p[0] - s).toFixed(1) + ' ' + p[1].toFixed(1) + 'Z'; }
    var growT0 = -1;

    var staleHit = false;

    function liveItems(c) { return items.filter(function (it) { return it.line.c0 <= c && it.line.c1 >= c; }); }
    function drawCursor() {
      if (cursor == null) { geo.curMark.setAttribute('d', ''); geo.curNum.textContent = ''; geo.nums.forEach(function (n) { n.el.classList.remove('is-masked'); }); geo.comets.forEach(function (o) { o.el.remove(); }); geo.comets = []; return; }
      var a = angle(cursor + 0.5), p0 = projA(geo.rBez + P.tick * 1.2, a), p1 = projA(geo.rBez - P.tick * 0.3, a);
      geo.curMark.setAttribute('d', p0 && p1 ? 'M' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) + 'L' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) : '');
      var pn = projA(geo.rNum + P.num * 0.25, a);
      if (pn) { geo.curNum.setAttribute('x', pn[0].toFixed(1)); geo.curNum.setAttribute('y', pn[1].toFixed(1)); var no = String(noOf(cursor)); if (geo.curNum.textContent !== no) geo.curNum.textContent = no; }
      geo.nums.forEach(function (n) { var p = n.point || projA(geo.rNum, n.a), hide = !!(p && pn && Math.hypot(p[0] - pn[0], p[1] - pn[1]) < 22); n.el.classList.toggle('is-masked', hide); });
      geo.comets.forEach(function (o) { var p = projA(o.it.r, a); if (p) { o.el.setAttribute('cx', p[0].toFixed(1)); o.el.setAttribute('cy', p[1].toFixed(1)); } });
    }
    function setCursor(c) {
      if (!M || !geo) return;
      cursor = c == null ? null : clamp(Math.round(c), 0, M.nCh - 1);
      var comets = [];
      svg.classList.toggle('sd-timed', cursor != null);
      items.forEach(function (it) {
        var l = it.line, past = cursor != null && l.c1 < cursor, live = cursor != null && l.c0 <= cursor && l.c1 >= cursor;
        var mask = cursor == null ? 0 : past ? 1 : live ? 2 : 4;
        it.live = live;
        if (it.cursorState !== mask) {
          if (it.el) { it.el.classList.toggle('is-past', past); it.el.classList.toggle('is-live', live); it.el.classList.toggle('is-future', mask === 4); }
          if (it.tx) it.tx.classList.toggle('is-live', live);
          it.cursorState = mask;
        }
        if (live && it.kind !== 'quiet') {
          if (!it.comet) { it.comet = mk('circle', 'sd-comet g' + l.gen, gCur); it.comet.setAttribute('r', it.kind === 'main' ? '4' : '3'); }
          comets.push({ el: it.comet, it: it });
        } else if (it.comet) { it.comet.remove(); it.comet = null; }
      });
      geo.comets = comets;
      drawCursor();
      if (cursor != null && !hoverId && !focusId) {
        var cast = M.chapterCast[cursor] || [], lives = liveItems(cursor).filter(function (it) { return it.kind !== 'quiet'; });
        setTether(null, cast.slice(0, 14), lives);
      } else if (cursor == null && !hoverId && !focusId) setTether(null, [], null);
      emit('cursor', cursor);
    }

    var tethEls = [], tethGl = null;
    function emph() {
      var act = focusId || hoverId;
      svg.classList.toggle('sd-emph', !!act);
      items.forEach(function (it) {
        var on = act === it.id, fam = act && byId[act] && (it.line.mainId === byId[act].line.id || byId[act].line.mainId === it.id);
        if (it.el) { it.el.classList.toggle('is-on', on); it.el.classList.toggle('is-kin', !on && !!fam); }
        if (it.tx) { it.tx.classList.toggle('is-on', on); }
      });
      if (act && byId[act]) setTether(act, byId[act].line.cast.slice(0, 14));
      else if (cursor != null) setCursor(cursor);
      else setTether(null, [], null);
      if (state === 'plot' && geo && E) placeLabels();
    }
    function lineInfo(id) {
      var it = byId[id]; if (!it) return null;
      var l = it.line;
      return { id: it.id, kind: it.kind === 'main' ? 'main' : l.kind, label: l.fullLabel || l.label, short: l.label, keyEvent: l.keyEvent, lead: l.lead, c0: l.c0, c1: l.c1, no0: noOf(l.c0), no1: noOf(l.c1),
        chapter0: g.CLSkyModel.chapterLabel(M, l.c0), spanLabel: g.CLSkyModel.chapterSpan(M, l.c0, l.c1), spanUnit: '个章节段',
        span: l.c1 - l.c0 + 1, events: l.n, cast: l.cast.slice(), derived: l.derived, theme: (l.title && l.title.indexOf(' · ') < 0 && l.title !== l.label && l.title !== l.fullLabel) ? l.title : '', resolved: l.resolved, suspended: l.suspended, gen: l.gen, mainLabel: l.mainId && byId[l.mainId] ? byId[l.mainId].line.fullLabel || byId[l.mainId].line.label : '' };
    }
    function pointerId(e) { var t = e.target; return t && t.getAttribute && t.getAttribute('data-id'); }
    function hitSegD2(px, py, a, b) { var vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy, t = L > 0 ? clamp(((px - a[0]) * vx + (py - a[1]) * vy) / L, 0, 1) : 0, dx = a[0] + vx * t - px, dy = a[1] + vy * t - py; return dx * dx + dy * dy; }
    function pickLine(cx, cy) {
      var els = document.elementsFromPoint ? document.elementsFromPoint(cx, cy) : [], x = cx - stageL, y = cy - stageT, best = null, bd = Infinity;
      for (var i = 0; i < els.length; i++) {
        var el = els[i]; if (!el.classList || !el.classList.contains('sd-hit')) continue;
        var id = el.getAttribute('data-id'), it = byId[id], Q = it && it.Q; if (!Q || !Q.length) continue;
        for (var k = 0; k + 1 < Q.length; k++) { var d = hitSegD2(x, y, Q[k], Q[k + 1]); if (d < bd) { bd = d; best = id; } }
      }
      return best;
    }
    gHit.addEventListener('pointerover', function (e) { var id = pickLine(e.clientX, e.clientY) || pointerId(e); if (!id || state !== 'plot') return; hoverId = id; emph(); emit('hover', { info: lineInfo(id), x: e.clientX, y: e.clientY }); });
    gHit.addEventListener('pointermove', function (e) {
      if (!hoverId || state !== 'plot') return;
      var id = pickLine(e.clientX, e.clientY);
      if (id && id !== hoverId) { hoverId = id; emph(); emit('hover', { info: lineInfo(id), x: e.clientX, y: e.clientY }); }
      emit('hovermove', { x: e.clientX, y: e.clientY });
    });
    gHit.addEventListener('pointerout', function (e) { var id = pointerId(e); if (!id || id !== hoverId) return; hoverId = null; emph(); emit('hover', null); });
    gHit.addEventListener('click', function (e) { var id = pickLine(e.clientX, e.clientY) || pointerId(e); if (!id || state !== 'plot') return; e.stopPropagation(); focus(focusId === id ? null : id); });
    function focus(id) { focusId = id && byId[id] ? id : null; emph(); emit('select', focusId ? lineInfo(focusId) : null); }

    function setState(s) {
      if (s === state) return;
      var prev = state; state = s;
      svg.classList.remove('is-hidden', 'is-backdrop', 'is-plot'); svg.classList.add('is-' + s);
      svg.setAttribute('aria-hidden', s === 'plot' ? 'false' : 'true');
      tiltFrom = tilt; tiltTo = s === 'plot' ? 1 : 0; tiltT0 = now();
      if (reduced() || calm) { tilt = tiltTo; tiltT0 = -1; applyTilt(); dirty = true; }
      if (s === 'plot' && prev !== 'plot') {
        items.forEach(function (it) { if (it.tx) { it.shown = false; it.tx.classList.remove('is-fit', 'is-outer'); } });
        placedOnce = true; growT0 = now();
      }
      if (s === 'plot' && prev !== 'plot' && !reduced() && !calm) {
        svg.classList.remove('sd-grow'); svg.classList.add('sd-reset');
        void svg.getBoundingClientRect();
        g.requestAnimationFrame(function () { svg.classList.remove('sd-reset'); svg.classList.add('sd-grow'); });
        clearTimeout(svg._growT); svg._growT = setTimeout(function () { svg.classList.remove('sd-grow'); }, 3200);
      }
      if (s !== 'plot') { hoverId = null; focusId = null; emph(); emit('hover', null); }
      drawTethers();
      dirty = true;
    }
    var lastRef = null, sizeDirty = true, stageL = 0, stageT = 0;
    g.addEventListener('resize', function () { sizeDirty = true; });
    function frame() {
      if (dead || !M || !geo || state === 'hidden') return;
      if (document.body.classList.contains('skd-gl') !== builtGl) rebuild();
      var t0 = now();
      stats.frames++;
      if (tiltT0 >= 0) { var k = clamp((now() - tiltT0) / TILT_MS, 0, 1); tilt = tiltFrom + (tiltTo - tiltFrom) * k; if (k >= 1) tiltT0 = -1; applyTilt(); dirty = true; }
      if (sizeDirty) { sizeDirty = false; var r = stage.getBoundingClientRect(); stageL = r.left; stageT = r.top; if (r.width !== Wv || r.height !== Hv) { Wv = r.width; Hv = r.height; svg.setAttribute('viewBox', '0 0 ' + Wv + ' ' + Hv); dirty = true; } }
      if (anchor) anchor.updateWorldMatrix(true, false);
      if (state === 'backdrop' && document.body.classList.contains('skd-gl')) { dirty = true; prevKey = ''; stats.lastMs = now() - t0; return; }
      E = computeMatrix(); if (!E) return;
      var key = ''; for (var i = 0; i < 16; i++) key += E[i].toFixed(5) + ',';
      if (key !== prevKey || dirty) {
        var moved = prevKey !== '' && key !== prevKey;
        prevKey = key; dirty = false;
        if (moved) { lastMove = now(); placePending = true; } else placePending = false;
        reproject(moved);
      } else if (placePending && now() - lastMove > 140) { placePending = false; if (staleHit) reproject(false); else placeLabels(); }
      if (tetherFrom && tetherNames.length) drawTethers();
      stats.lastMs = now() - t0;
    }
    function setModel(model) {
      M = model; evChIdx = null; rim = rimOf(); ensureAnchor(); applyTilt(); build();
      if (cursor != null) setCursor(Math.min(cursor, M.nCh - 1));
    }
    function relayout() { rim = rimOf(); applyTilt(); dirty = true; }
    function plotExtent() {
      var keep = tilt; tilt = 1; applyTilt(); anchor.updateWorldMatrix(true, false);
      var El = computeMatrix(), save = E; E = El;
      var r = stage.getBoundingClientRect(); Wv = r.width; Hv = r.height;
      var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (var i = 0; i < 72; i++) { var p = projA(geo.E, i / 72 * Math.PI * 2); if (!p) continue; x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
      E = save; tilt = keep; applyTilt(); dirty = true;
      return isFinite(x0) ? { w: x1 - x0, h: y1 - y0 } : null;
    }
    function tune(K, nq, nls, nlp, nm, two) {
      K = Math.max(60, K || 280); nm = Math.max(1, nm || 1);
      var small = K < 200, gq = small ? 1.6 : PX.groove, bez = (small ? 18 : PX.bez) + (two ? (small ? 14 : PX.line2) : 0), tail = small ? 17 : PX.tail;
      var F = PX.mainGap + (nm - 1) * PX.mainPitch + bez + tail;
      var E0 = R_IN / Math.max(0.3, 1 - F / K), pxR = K / E0, lo = loFrac(K) * E0;
      var band = (R_IN - lo) * pxR - (nq ? nq * gq + PX.grooveGap : 0);
      var spread = nls > 0 && band / nls >= PX.laneSpread, nl = spread ? nls : nlp;
      var lane = nl ? clamp(band / nl, PX.laneMin, PX.laneMax) : PX.lane;
      return { K: K, nq: nq, nls: nls, nlp: nlp, nm: nm, two: !!two, nl: nl, spread: spread, pxR: pxR, lanePx: lane, lo: lo, wq: gq / pxR, gap: PX.grooveGap / pxR, wn: lane / pxR, mainGap: PX.mainGap / pxR,
        mainPitch: PX.mainPitch / pxR, bez: bez / pxR, num: PX.num / pxR, tail: tail / pxR, tick: PX.tick / pxR, tickMinor: PX.tickMinor / pxR };
    }
    function estimateK() {
      var W = g.innerWidth || 1200, H = g.innerHeight || 800;
      return 0.5 * Math.min(Math.max(200, W - 64), Math.max(200, H - (W <= 900 ? 250 : 188)) / 0.94) * FIT_K;
    }
    function rebuild() {
      build(); stats.tunes++;
      if (cursor != null) setCursor(cursor);
      if (hoverId || focusId) emph();
    }
    function fitFactor(area) {
      if (!M || !geo || !anchor) return 1;
      var ext = plotExtent(); if (!ext) return 1;
      var aw = area ? area.width : Wv, ah = area ? area.height : Hv, f = Math.max(ext.w / aw, ext.h / ah);
      var K = Math.sqrt(ext.w * ext.h) / f / 2 * FIT_K;
      if (K > 40 && P && Math.abs(K - P.K) / P.K > 0.03) {
        P = tune(K, P.nq, P.nls, P.nlp, P.nm, P.two); rebuild();
        ext = plotExtent(); if (ext) f = Math.max(ext.w / aw, ext.h / ah);
      }
      return f;
    }
    function dispose() {
      dead = true;
      if (tethGl) { tethGl.dispose(); tethGl = null; }
      if (anchor && anchor.parent) anchor.parent.remove(anchor);
      if (svg.parentNode) svg.parentNode.removeChild(svg);
      clearTimeout(svg._growT);
    }

    var eventAnchorRev = -1, eventAnchors = Object.create(null);
    function ensureEventAnchors() {
      if (eventAnchorRev === rev) return;
      eventAnchors = Object.create(null); eventAnchorRev = rev;
      M.chapterEvents.forEach(function (events, chapter) {
        events.forEach(function (ev) { eventAnchors[ev] = { a: angle(chapter + 0.5), r: geo.rMain, chapter: chapter, kind: 'chapter', lineId: null, priority: 0 }; });
      });
      items.forEach(function (it) {
        (it.dots || []).forEach(function (dot, j) {
          var ev = it.line.events[j], old = eventAnchors[ev], priority = it.kind === 'main' ? 2 : 1;
          if (old && priority > old.priority) eventAnchors[ev] = { a: dot.a, r: it.r, chapter: old.chapter, kind: 'bead', lineId: it.id, priority: priority };
        });
      });
    }
    function eventPoint(index) {
      if (!M || !geo || !E || !Number.isInteger(index) || index < 0) return null;
      ensureEventAnchors();
      var local = eventAnchors[index]; if (!local) return null;
      var p = projA(local.r, local.a); if (!p) return null;
      return { x: p[0] + stageL, y: p[1] + stageT, chapter: local.chapter, kind: local.kind, lineId: local.lineId };
    }
    function eventWorld(index) {
      if (!M || !geo || !anchor || !THREE || !Number.isInteger(index) || index < 0) return null;
      ensureEventAnchors();
      var local = eventAnchors[index]; if (!local) return null;
      anchor.updateWorldMatrix(true, false);
      return anchor.localToWorld(new THREE.Vector3(local.r * Math.cos(local.a), local.r * Math.sin(local.a), zAt(local.r)));
    }

    return {
      el: svg, setModel: setModel, setState: setState, state: function () { return state; }, frame: frame, on: on,
      anchor: function () { return anchor; }, desc: descOf, rev: function () { return rev; }, tilt: function () { return tilt; }, lineIndex: function (id) { for (var i = 0; i < items.length; i++) if (items[i].id === String(id)) return i; return -1; },
      eventPoint: eventPoint, eventWorld: eventWorld,
      setCursor: setCursor, cursor: function () { return cursor; }, focus: focus, focused: function () { return focusId; }, hover: function () { return hoverId; },
      lineInfo: lineInfo, chapterNo: noOf, maxNo: function () { return M && M.nCh ? noOf(M.nCh - 1) : 0; }, pickLine: pickLine, relayout: relayout, fitFactor: fitFactor, setCalm: function (v) { calm = !!v; },
      hoverLine: function (id) { if (state !== 'plot') return false; hoverId = id && byId[id] ? String(id) : null; emph(); return !!hoverId; },
      ringScreen: function (r, n) { if (!E) return []; var out = []; n = n || 72; for (var i = 0; i < n; i++) { var p = projA(r, i / n * Math.PI * 2); if (p) out.push(p); } return out; },
      rIn: function () { return R_IN; }, rLo: function () { return geo ? geo.rLo : R_IN; }, rMainIn: function () { return geo ? geo.rMainIn : R_IN; }, outer: function () { return geo ? geo.E : 0; },
      labelBoxes: function () { return items.filter(function (it) { return it.shown && it.tx; }).map(function (it) { var b = it.tx.getBoundingClientRect(); return { id: it.id, kind: it.kind, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom, fp: it.P ? null : null }; }); },
      liveIds: function () { return items.filter(function (it) { return it.live; }).map(function (it) { return it.id; }); },
      tetherStats: function () { return tethGl ? tethGl.stats() : null; },
      itemRadii: function () { return items.map(function (it) { return it.r; }); },
      lineScreen: function (id) { var it = byId[id]; if (!it || !E) return null; var p = projA(it.r, (it.a0 + it.a1) / 2); return p; },
      stats: function () {
        return { state: state, lines: items.length, mains: items.filter(function (i) { return i.kind === 'main'; }).length, named: items.filter(function (i) { return i.kind === 'named'; }).length,
          quiet: items.filter(function (i) { return i.kind === 'quiet'; }).length, labelsFit: items.filter(function (i) { return i.fit; }).length, labelsShown: items.filter(function (i) { return i.shown; }).length,
          labelsNamed: items.filter(function (i) { return i.shown && i.kind === 'named'; }).length, labelsOuter: items.filter(function (i) { return i.shown && i.kind === 'named' && i.side === 1; }).length, labelsLane: items.filter(function (i) { return i.shown && i.side >= 2; }).length, tilt: +tilt.toFixed(3),
          geo: geo ? { rMain: +geo.rMain.toFixed(3), rMainIn: +geo.rMainIn.toFixed(3), rLo: +geo.rLo.toFixed(3), mainLanes: geo.mainLanes, spread: P.spread, two: P.two, rBez: +geo.rBez.toFixed(3), E: +geo.E.toFixed(3), lanes: geo.lanes, named: geo.rc.length, groove: geo.rq.length, wNamed: +P.wn.toFixed(3), lanePx: +P.lanePx.toFixed(1), pxR: +P.pxR.toFixed(1), K: +P.K.toFixed(1), bez: +P.bez.toFixed(3), tunes: stats.tunes } : null,
          tethers: tethGl && document.body.classList.contains('skd-gl') ? tethGl.stats().shown : tethEls.filter(function (e) { return e.getAttribute('visibility') === 'visible'; }).length, cursor: cursor, frames: stats.frames, projections: stats.projections, lastMs: +stats.lastMs.toFixed(2),
          dom: svg.querySelectorAll('*').length };
      },
      dispose: dispose
    };
  }

  g.CLSkyDisc = { create: create, version: '1' };
})(window);
