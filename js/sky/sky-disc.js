/**
 * @role component
 * @owns js/sky/sky-disc.js
 * 星盘：星座外围的剧情时间盘。SVG 画在星座平面上（与星座同一组坐标、随镜头 3D 转动），所有剧情几何都在星座之外（r ≥ 1.10R）。
 *  · 背景态 backdrop：只留主线环 + 刻度环，模糊、低亮、无字、无命中；支线与细纹完全隐去；超出视口处径向淡出（CSS 遮罩）。
 *  · 剧情态 plot：清晰；由内向外 = 细纹带（无名细弧，统一 1px 点线）→ 具名支线车道（同阶段色降彩度）→ 主线环（全饱和、最粗）→ 刻度环。
 *    支线名写在自己弧线内侧（屏幕空间偏移半个线宽 + 字高一半，深空描边），不压任何彩色弧；主线段名写在主线环外侧。
 *  · 悬停/选中一条线 → 参与者连线到星座里的星；播放：游标逐回推进，活跃线头一粒光点，本回参与者连线。
 * 只读 CLSkyModel 的读数，不改数据；不私开 rAF（挂 scene.registerFrameHook）。
 */
(function (g) {
  'use strict';
  /* 盘面由内向外：R_IN(1.10R，团名带之外) → 细纹带 → 具名车道 → 主线环 → 主线段名字轨 → 刻度环 → 回数。
   * 除 R_IN 外全部按「剧情态取景后的真实像素」定宽（见 tune）：屏幕上线距、字轨、刻度长在 1440 / 820 / 390 下都一样，
   * 盘外缘 E 由这些像素反解，并压在 E_MAX 以内（盘面紧凑，星座不被挤小）；车道放不下字轨时名字改走「车道内接在弧尾 / 弧头」。 */
  var R_IN = 1.10, STEP = 2.0 * Math.PI / 180;
  var TILT_MS = 780;
  /* 线宽（px）：三级——主线 8 · 具名支线 1.4–3.6（√事件数）· 细纹 1 */
  var MAIN_W = 8, NAMED_W0 = 1.4, NAMED_W1 = 2.2;
  /* 名字离弧的净空（px）：弧半宽 + 这一段 + 字身半高（汉字墨迹约占字号的 0.92，取 0.46 字号） */
  var CLEAR_NAMED = 1.5, CLEAR_MAIN = 2.6, INK = 0.46, LAB_PAD = 3.5, LAB_GAP = 17.5;
  /* 像素目标：具名车道 15（= 弧 + 内侧字轨）· 最窄 7 · 细纹车道 2 · 细纹带与具名带间隔 4 · 具名带到主线环 9 · 主线段名字轨 20 · 刻度到回数 12 / 外缘 19 */
  var PX = { lane: 15, laneMin: 7, groove: 2, grooveGap: 4, mainGap: 9, bez: 20, num: 12, tail: 19, tick: 5, tickMinor: 2.5 };
  /* E_MAX：桌面 1.85R；小屏（取景半径 K ≤ 170px）放宽到 2.1R——像素预算本身太少，字轨与刻度必须有地方写 */
  function eMax(K) { return K >= 250 ? 1.85 : K <= 170 ? 2.1 : 2.1 - (K - 170) / 80 * 0.25; }
  /* FIT_K：外壳取景时再退 4%，透视也让盘略小于目标区——实测取景后盘半径 ≈ 估计值 × 0.92 */
  var FIT_K = 0.92;
  /* 3D 分层：剧情态盘面是一只浅碗——细纹带贴底、具名车道由内向外逐道升高、主线环与刻度环在碗沿（R 为单位，z = LIFT·u^1.6）。
   * 高度只随半径变：读层（SVG 投影）与光层（sky-rings / ringfx 顶点）都从同一个 zAt(r) 取；锚点 z 向缩放随剧情倾角 0→1，背景态压平 */
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
    var P = null;   /* 当前盘面几何参数（R 单位），tune(K) 求出 */

    /* ── DOM ───────────────────────────────────────────── */
    var svg = mk('svg', 'sky-disc is-hidden');
    svg.setAttribute('aria-hidden', 'true');
    var defs = mk('defs', null, svg);
    var gBezel = mk('g', 'sd-bezel', svg), gDorm = mk('g', 'sd-dorm', svg), gQuiet = mk('g', 'sd-quiet', svg), gNamed = mk('g', 'sd-named', svg),
      gMain = mk('g', 'sd-main', svg), gDots = mk('g', 'sd-dots', svg), gHo = mk('g', 'sd-ho', svg),
      gCur = mk('g', 'sd-cursor', svg), gTeth = mk('g', 'sd-teth', svg), gLab = mk('g', 'sd-labels', svg), gHit = mk('g', 'sd-hits', svg);
    /* 名字层在连线之上：字的深空描边把穿过它的参与者连线切开，名字始终可读 */
    var labelsHost = stage.querySelector('#labels');
    if (labelsHost && labelsHost.parentNode === stage) stage.insertBefore(svg, labelsHost); else stage.appendChild(svg);

    /* 专职单元共读这份闭包状态：几何/投影/字轨/避让/落盘/光丝不另开帧循环。 */
    var unitCtx = { CLEAR_MAIN: CLEAR_MAIN, CLEAR_NAMED: CLEAR_NAMED, INK: INK, LAB_GAP: LAB_GAP, LAB_PAD: LAB_PAD, LIFT: LIFT, MAIN_W: MAIN_W, NAMED_W0: NAMED_W0, NAMED_W1: NAMED_W1, R_IN: R_IN, STEP: STEP, THREE: THREE, angle: angle, clamp: clamp, defs: defs, drawCursor: drawCursor, ease: ease, estimateK: estimateK, gBezel: gBezel, gCur: gCur, gDorm: gDorm, gDots: gDots, gHit: gHit, gHo: gHo, gLab: gLab, gMain: gMain, gNamed: gNamed, gQuiet: gQuiet, gTeth: gTeth, knot: knot, mk: mk, now: now, opts: opts, scene: scene, stats: stats, svg: svg, tune: tune };
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
      track = tracksUnit.track,
      trackFor = tracksUnit.trackFor,
      at = tracksUnit.at,
      uprightTrack = tracksUnit.uprightTrack,
      footprint = tracksUnit.footprint,
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
    unitCtx.track = track;
    unitCtx.trackFor = trackFor;
    unitCtx.at = at;
    unitCtx.uprightTrack = uprightTrack;
    unitCtx.footprint = footprint;
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

    /* ── 平面与投影 ─────────────────────────────────────── */
    var E = null;

    /* ── 几何构建 ─────────────────────────────────────── */
    function angle(slot) { return g.CLSkyModel.angleAt(slot, M.nCh); }
    var rev = 0, builtGl = false, evChIdx = null;

    /* ── 每帧投影 ─────────────────────────────────────── */
    function knot(p, s) { return 'M' + p[0].toFixed(1) + ' ' + (p[1] - s).toFixed(1) + 'L' + (p[0] + s).toFixed(1) + ' ' + p[1].toFixed(1) + 'L' + p[0].toFixed(1) + ' ' + (p[1] + s).toFixed(1) + 'L' + (p[0] - s).toFixed(1) + ' ' + p[1].toFixed(1) + 'Z'; }
    /* ── 名字：屏幕空间的「字轨」──────────────────────────
     * 字轨 = 弧线的屏幕折线沿法向平移：支线名向盘心平移（弧半宽 + 净空 + 字高一半），主线段名向外平移到带与刻度环之间。
     * 用屏幕 px 而不是 R 单位，透视压扁的上下两段也保持同样的净空。 */
    var growT0 = -1;

    var staleHit = false;

    /* ── 播放游标 ─────────────────────────────────────── */
    function liveItems(c) { return items.filter(function (it) { return it.line.c0 <= c && it.line.c1 >= c; }); }
    function drawCursor() {
      if (cursor == null) { geo.curMark.setAttribute('d', ''); geo.curNum.textContent = ''; geo.nums.forEach(function (n) { n.el.classList.remove('is-masked'); }); geo.comets.forEach(function (o) { o.el.remove(); }); geo.comets = []; return; }
      var a = angle(cursor + 0.5), p0 = projA(geo.rBez + P.tick * 1.2, a), p1 = projA(geo.rBez - P.tick * 0.3, a);
      geo.curMark.setAttribute('d', p0 && p1 ? 'M' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) + 'L' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) : '');
      var pn = projA(geo.rNum + P.num * 0.25, a);
      if (pn) { geo.curNum.setAttribute('x', pn[0].toFixed(1)); geo.curNum.setAttribute('y', pn[1].toFixed(1)); var no = String(M.chapters[cursor].no); if (geo.curNum.textContent !== no) geo.curNum.textContent = no; }
      /* 游标回数与刻度回数撞在一起时，让刻度那枚退场（不叠成两个「50」） */
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
        /* 跨回时只改进入 / 离开区间的线；同一条活跃线的光点保留，只推进位置。 */
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

    /* ── 参与者连线 ───────────────────────────────────── */
    var tethEls = [], tethGl = null;
    /* ── 悬停 / 选中 ─────────────────────────────────── */
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
      var l = it.line, ch0 = M.chapters[l.c0], ch1 = M.chapters[l.c1];
      return { id: it.id, kind: it.kind === 'main' ? 'main' : l.kind, label: l.label, keyEvent: l.keyEvent, lead: l.lead, c0: l.c0, c1: l.c1, no0: ch0 ? ch0.no : l.c0 + 1, no1: ch1 ? ch1.no : l.c1 + 1,
        span: l.c1 - l.c0 + 1, events: l.n, cast: l.cast.slice(), derived: l.derived, theme: (l.title && l.title.indexOf(' · ') < 0 && l.title !== l.label) ? l.title : '', resolved: l.resolved, suspended: l.suspended, gen: l.gen, mainLabel: l.mainId && byId[l.mainId] ? byId[l.mainId].line.label : '' };
    }
    /* 光层（sky-rings / sky-rings-fx）读的盘面描述：与 SVG 同一组几何（半径 / 角 / 线宽），光层网格挂在同一个锚点下随倾角转动 */
    function pointerId(e) { var t = e.target; return t && t.getAttribute && t.getAttribute('data-id'); }
    /* 命中取离指针最近的弧：相邻车道的命中描边（14px）会互相盖住，斜视时车道间距还会被压扁——按 DOM 叠放取最上面那条会点到邻线 */
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

    /* ── 状态与动画 ───────────────────────────────────── */
    function setState(s) {
      if (s === state) return;
      var prev = state; state = s;
      svg.classList.remove('is-hidden', 'is-backdrop', 'is-plot'); svg.classList.add('is-' + s);
      svg.setAttribute('aria-hidden', s === 'plot' ? 'false' : 'true');
      tiltFrom = tilt; tiltTo = s === 'plot' ? 1 : 0; tiltT0 = now();
      if (reduced() || calm) { tilt = tiltTo; tiltT0 = -1; applyTilt(); dirty = true; }
      if (s === 'plot' && prev !== 'plot') {
        /* 背景态的名字排布作废：镜头推拉期间一个名字也不出，停稳后统一避让一次再出（名字最后出现） */
        items.forEach(function (it) { if (it.tx) { it.shown = false; it.tx.classList.remove('is-fit', 'is-outer'); } });
        placedOnce = true; growT0 = now();
      }
      if (s === 'plot' && prev !== 'plot' && !reduced() && !calm) {
        /* 生长：先把所有弧收回（无过渡）→ 下一帧按开始时间依次长出 */
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
      /* 背景态且光层在：SVG 里没有任何可见或可交互的东西（光环由 WebGL 按同一锚点画），只推进倾角，不投影 */
      if (state === 'backdrop' && document.body.classList.contains('skd-gl')) { dirty = true; prevKey = ''; stats.lastMs = now() - t0; return; }
      E = computeMatrix(); if (!E) return;
      var key = ''; for (var i = 0; i < 16; i++) key += E[i].toFixed(5) + ',';
      if (key !== prevKey || dirty) {
        /* 按投影矩阵变化判运动，不按单帧像素阈值：高帧率时每帧位移很小，仍不能在旋转中反复跑全表避让。 */
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
    /* 剧情态倾角下、当前镜头里星盘外缘的屏幕外接盒 */
    function plotExtent() {
      var keep = tilt; tilt = 1; applyTilt(); anchor.updateWorldMatrix(true, false);
      var El = computeMatrix(), save = E; E = El;
      var r = stage.getBoundingClientRect(); Wv = r.width; Hv = r.height;
      var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (var i = 0; i < 72; i++) { var p = projA(geo.E, i / 72 * Math.PI * 2); if (!p) continue; x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
      E = save; tilt = keep; applyTilt(); dirty = true;
      return isFinite(x0) ? { w: x1 - x0, h: y1 - y0 } : null;
    }
    /* 像素 → R：取景后盘外缘半径 K px 固定，E = R_IN + (固定像素 F + nl·车道像素) / pxR，pxR = K / E
     * ⇒ E = R_IN / (1 − (F + nl·lane)/K)。车道先取 15px；超出 E_MAX 就收窄车道（≥ 7px），仍超出才让 E 越过 E_MAX。 */
    function tune(K, nq, nl) {
      K = Math.max(60, K || 280);
      var small = K < 200, gq = small ? 1.6 : PX.groove, bez = small ? 18 : PX.bez, tail = small ? 17 : PX.tail;
      var F = nq * gq + (nq && nl ? PX.grooveGap : 0) + PX.mainGap + bez + tail;
      var room = K * (1 - R_IN / eMax(K)) - F, lane = nl ? clamp(room / nl, PX.laneMin, PX.lane) : PX.lane;
      var den = Math.max(0.3, 1 - (F + nl * lane) / K), E0 = R_IN / den, pxR = K / E0;
      return { K: K, nq: nq, nl: nl, pxR: pxR, lanePx: lane, wq: gq / pxR, gap: PX.grooveGap / pxR, wn: lane / pxR, mainGap: PX.mainGap / pxR,
        bez: bez / pxR, num: PX.num / pxR, tail: tail / pxR, tick: PX.tick / pxR, tickMinor: PX.tickMinor / pxR };
    }
    /* 首次（背景态）还没取过景：按视口估一个 K（外壳剧情取景区 = 视口去掉顶栏与底栏） */
    function estimateK() {
      var W = g.innerWidth || 1200, H = g.innerHeight || 800;
      return 0.5 * Math.min(Math.max(200, W - 64), Math.max(200, H - (W <= 900 ? 250 : 188)) / 0.94) * FIT_K;
    }
    function rebuild() {
      build(); stats.tunes++;
      if (cursor != null) setCursor(cursor);
      if (hoverId || focusId) emph();
    }
    /* 剧情态取景：按「剧情态倾角」下星盘外缘的屏幕外接盒，求镜头沿视线的伸缩系数；顺带按目标区域的真实像素重定盘面几何 */
    function fitFactor(area) {
      if (!M || !geo || !anchor) return 1;
      var ext = plotExtent(); if (!ext) return 1;
      var aw = area ? area.width : Wv, ah = area ? area.height : Hv, f = Math.max(ext.w / aw, ext.h / ah);
      var K = Math.sqrt(ext.w * ext.h) / f / 2 * FIT_K;
      if (K > 40 && P && Math.abs(K - P.K) / P.K > 0.03) {
        P = tune(K, P.nq, P.nl); rebuild();
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

    return {
      el: svg, setModel: setModel, setState: setState, state: function () { return state; }, frame: frame, on: on,
      anchor: function () { return anchor; }, desc: descOf, rev: function () { return rev; }, tilt: function () { return tilt; }, lineIndex: function (id) { for (var i = 0; i < items.length; i++) if (items[i].id === String(id)) return i; return -1; },
      setCursor: setCursor, cursor: function () { return cursor; }, focus: focus, focused: function () { return focusId; }, hover: function () { return hoverId; },
      lineInfo: lineInfo, pickLine: pickLine, relayout: relayout, fitFactor: fitFactor, setCalm: function (v) { calm = !!v; },
      hoverLine: function (id) { if (state !== 'plot') return false; hoverId = id && byId[id] ? String(id) : null; emph(); return !!hoverId; },
      ringScreen: function (r, n) { if (!E) return []; var out = []; n = n || 72; for (var i = 0; i < n; i++) { var p = projA(r, i / n * Math.PI * 2); if (p) out.push(p); } return out; },
      rIn: function () { return R_IN; }, outer: function () { return geo ? geo.E : 0; },
      labelBoxes: function () { return items.filter(function (it) { return it.shown && it.tx; }).map(function (it) { var b = it.tx.getBoundingClientRect(); return { id: it.id, kind: it.kind, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom, fp: it.P ? null : null }; }); },
      liveIds: function () { return items.filter(function (it) { return it.live; }).map(function (it) { return it.id; }); },
      tetherStats: function () { return tethGl ? tethGl.stats() : null; },
      itemRadii: function () { return items.map(function (it) { return it.r; }); },
      lineScreen: function (id) { var it = byId[id]; if (!it || !E) return null; var p = projA(it.r, (it.a0 + it.a1) / 2); return p; },
      stats: function () {
        return { state: state, lines: items.length, mains: items.filter(function (i) { return i.kind === 'main'; }).length, named: items.filter(function (i) { return i.kind === 'named'; }).length,
          quiet: items.filter(function (i) { return i.kind === 'quiet'; }).length, labelsFit: items.filter(function (i) { return i.fit; }).length, labelsShown: items.filter(function (i) { return i.shown; }).length,
          labelsNamed: items.filter(function (i) { return i.shown && i.kind === 'named'; }).length, labelsOuter: items.filter(function (i) { return i.shown && i.kind === 'named' && i.side === 1; }).length, labelsLane: items.filter(function (i) { return i.shown && i.side >= 2; }).length, tilt: +tilt.toFixed(3),
          geo: geo ? { rMain: +geo.rMain.toFixed(3), rBez: +geo.rBez.toFixed(3), E: +geo.E.toFixed(3), lanes: geo.lanes, named: geo.rc.length, groove: geo.rq.length, wNamed: +P.wn.toFixed(3), lanePx: +P.lanePx.toFixed(1), pxR: +P.pxR.toFixed(1), K: +P.K.toFixed(1), bez: +P.bez.toFixed(3), tunes: stats.tunes } : null,
          tethers: tethGl && document.body.classList.contains('skd-gl') ? tethGl.stats().shown : tethEls.filter(function (e) { return e.getAttribute('visibility') === 'visible'; }).length, cursor: cursor, frames: stats.frames, projections: stats.projections, lastMs: +stats.lastMs.toFixed(2),
          dom: svg.querySelectorAll('*').length };
      },
      dispose: dispose
    };
  }

  g.CLSkyDisc = { create: create, version: '1' };
})(window);
