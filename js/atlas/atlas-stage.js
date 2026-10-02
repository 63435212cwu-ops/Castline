/*!
 * atlas-stage.js
 * @role component
 * @owns js/atlas/atlas-stage.js
 * @contract v70
 *
 * 展卷控制器：把同一份全书图谱在「星盘」（观赏姿态）与「线谱」（阅读姿态，CLAtlasScore）
 * 之间切换。只读参考 js/orbit3d/plot-orbit-solo.js（运行时隐藏其它层的做法，不改它）与
 * js/keys.js（window 捕获阶段拦键 · say() 提示条的写法，不改它，本文件自带独立的 U 键捕获）。
 *
 * U02 CLAtlasScore / U03 CLOrbit3DAtlas 是并行单元，可能还未落地：
 *   - CLAtlasScore 缺席 → host 里直接显示文案「线谱模块未加载」，不抛错、不假装成功。
 *   - 共享锚点动画：优先用 CLPlotOrbit.eventAt() 给的屏幕坐标；没有就退回 orbit3d 卡片/标签
 *     的 DOM rect（约定属性 data-ev）；两者都拿不到（比如根本没有星盘数据）时整体退化为
 *     一次淡入/淡出，不出现飞到 (0,0) 之类的假动画。
 * 因此本文件在任何加载序下、任何依赖缺席时都必须能独立 open()/close()，不崩、不静默失败给错文案。
 */
(function (global) {
  'use strict';

  var VERSION = '7.0.0';
  var MAX_ANCHORS = 200;
  var FALLBACK_STEP = 16;
  var DEFAULT_DUR = 320; /* ms · 令牌 --cl-atlas-dur-3 未就位（U10 未落地）时的退化值 */
  var STAGE_Z = 150;

  var doc = (typeof document !== 'undefined') ? document : null;

  /* ---------------------------------------------------------------- 基础工具 */
  function now() {
    try {
      if (typeof performance !== 'undefined' && performance && typeof performance.now === 'function') return performance.now();
    } catch (e) {}
    return Date.now();
  }
  var hasRaf = !!(global.requestAnimationFrame);
  function raf(fn) { return hasRaf ? global.requestAnimationFrame(fn) : global.setTimeout(function () { fn(now()); }, FALLBACK_STEP); }
  function caf(id) {
    if (hasRaf && global.cancelAnimationFrame) { global.cancelAnimationFrame(id); return; }
    global.clearTimeout(id);
  }
  function prefersReduced() {
    try { return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function easeOutCubic(p) { var q = 1 - p; return 1 - q * q * q; }
  function numOrNull(v) { return (typeof v === 'number' && isFinite(v)) ? v : null; }

  function $(id) { return doc ? doc.getElementById(id) : null; }
  function qs(sel, root) { var r = root || doc; return (r && r.querySelector) ? r.querySelector(sel) : null; }
  function isTypingTarget(t) {
    if (!t) return false;
    var tag = (t.tagName || '').toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || !!t.isContentEditable;
  }
  function cssMs(varName, fallback) {
    try {
      if (!doc || !doc.documentElement || !global.getComputedStyle) return fallback;
      var raw = global.getComputedStyle(doc.documentElement).getPropertyValue(varName);
      if (!raw) return fallback;
      raw = raw.trim();
      if (!raw) return fallback;
      var n = parseFloat(raw);
      if (!isFinite(n)) return fallback;
      return /ms\s*$/i.test(raw) ? n : n * 1000;
    } catch (e) { return fallback; }
  }
  function dispatch(name, detail) {
    if (!doc) return;
    try {
      var ev;
      if (typeof global.CustomEvent === 'function') ev = new global.CustomEvent(name, { detail: detail });
      else { ev = doc.createEvent('CustomEvent'); ev.initCustomEvent(name, false, false, detail); }
      doc.dispatchEvent(ev);
    } catch (e) { /* 从不因为一次广播打断控制器 */ }
  }

  /* ---------------------------------------------------------------- 状态 */
  var on = false;
  var initDone = false;
  var root = null, nameEl = null, metaEl = null, searchEl = null, closeBtn = null, hostEl = null;
  var canvas = null, ctx = null;
  var vbBtn = null;
  var scoreHandle = null;
  var lastModel = null;
  var pendingFocus = null; /* cl:atlas-open 传来的 lineIds，等下一次 mount 完成后消费 */
  var saved = { plot: null, cpWrap: null }; /* null = 元素本不存在；否则 {el, hidden:原始 hidden 值} */
  var onKeyRef = null, onAtlasOpenRef = null;

  var anim = { running: false, mode: null, direction: null, id: null, t0: 0, dur: DEFAULT_DUR, points: [] };

  /* ---------------------------------------------------------------- 数据 */
  var injectedModel = null; /* 主控 app.js 经 setModel() 注入的正典模型；有它就不自己算 */
  function setModel(m) { injectedModel = m || null; lastModel = null; if (on) { try { close(); open(); } catch (e0) {} } return injectedModel; }
  function buildModel() {
    /* 优先级：注入模型 → CLPlot.atlas() → 现成的 CLStory.get() 树（不重新 analyze，与圆盘同一棵树）。
       图谱 G 只从 CLPlot.graph() 取；取不到就传 {}，CLAtlasModel 会只用 tree。 */
    try {
      if (injectedModel) return injectedModel;
      var M = global.CLAtlasModel;
      if (!M || typeof M.build !== 'function') return null;
      var P = global.CLPlot;
      if (P && typeof P.atlas === 'function') { try { var a = P.atlas(); if (a && a.lines) return a; } catch (eA) {} }
      var tree = null;
      try { if (P && typeof P.tree === 'function') tree = P.tree(); } catch (eT) { tree = null; }
      try { if (!tree && global.CLStory && typeof global.CLStory.get === 'function') tree = global.CLStory.get(); } catch (e1) { tree = null; }
      if (!tree || !tree.ok) return null;
      var G = null;
      try { if (P && typeof P.graph === 'function') G = P.graph(); } catch (eG) { G = null; }
      return M.build(tree, G || {}) || null;
    } catch (e) { return null; }
  }

  function titleText() {
    var te = $('title');
    if (!te) return '—';
    var text = te.textContent || '';
    var sub = $('titleSub');
    if (sub && sub.textContent) {
      var idx = text.indexOf(sub.textContent);
      if (idx >= 0) text = text.slice(0, idx);
    }
    text = text.replace(/\s+/g, ' ').trim();
    return text || '—';
  }

  function headText(model) {
    var meta = '剧情数据未提供';
    if (model && model.totals) {
      var t = model.totals;
      meta = (t.lines != null ? t.lines : '—') + ' 线 · ' + (t.events != null ? t.events : '—') + ' 事件';
      /* R7-F：未归线口径直接上进展卷头（与 CLAtlasScore 未归线轨行头同一事实源 totals）：
         圆盘徽记在无 aggregate 时不渲染（车道复用下真实大样本 aggCount=0，R7-F 实测），
         头部元信息是阅读姿态里始终可见的同口径诚实标注，不是新视觉——同一行文字加一段。 */
      if (typeof t.orphanEvents === 'number' && t.orphanEvents > 0) {
        meta += ' · 未归线 ' + t.orphanEvents + ' 事';
        if (typeof t.placedEvents === 'number' && typeof t.events === 'number' && t.events > 0) {
          meta += '（覆盖 ' + Math.round(t.placedEvents / t.events * 100) + '%）';
        }
      }
    }
    return { title: titleText(), meta: meta };
  }

  /* ---------------------------------------------------------------- DOM：阅读层 */
  function ensureDom() {
    if (root) return true;
    if (!doc || !doc.body) return false;
    root = doc.createElement('div');
    root.id = 'atlasStage';
    root.className = 'cl-atlas-stage';
    root.hidden = true;
    root.innerHTML =
      '<div class="atlas-stage-bg" aria-hidden="true"></div>' +
      '<div class="atlas-stage-panel" role="dialog" aria-label="展卷 · 剧情线谱">' +
        '<div class="atlas-stage-head">' +
          '<div class="atlas-stage-title"><b class="atlas-stage-name">—</b><span class="atlas-stage-meta mono">剧情数据未提供</span></div>' +
          '<div class="atlas-stage-search"><input type="search" class="atlas-stage-q" placeholder="搜索线 / 事件 / 角色" aria-label="展卷搜索"></div>' +
          '<button type="button" class="btn atlas-stage-close" aria-label="收卷">收卷</button>' +
        '</div>' +
        '<div class="atlas-stage-host" tabindex="-1"></div>' +
      '</div>';
    doc.body.appendChild(root);
    nameEl = qs('.atlas-stage-name', root);
    metaEl = qs('.atlas-stage-meta', root);
    searchEl = qs('.atlas-stage-q', root);
    closeBtn = qs('.atlas-stage-close', root);
    hostEl = qs('.atlas-stage-host', root);
    if (closeBtn) closeBtn.addEventListener('click', function () { close(); });
    if (searchEl) searchEl.addEventListener('input', onSearchInput);
    return true;
  }

  function onSearchInput() {
    var q = searchEl ? searchEl.value : '';
    if (scoreHandle && typeof scoreHandle.setFilter === 'function') {
      try { scoreHandle.setFilter({ q: q }); } catch (e) {}
    }
  }

  /* 共享锚点动画用的独立覆盖层：不放进 #atlasStage，避免 root.hidden 切换把飞行中的
   * 动画一并瞬间隐藏——close() 的锚点要从「谱位」飞回「环位」，这一刻 #atlasStage 已经收起。 */
  function ensureCanvas() {
    if (canvas) return !!ctx;
    if (!doc || !doc.body) return false;
    canvas = doc.createElement('canvas');
    canvas.className = 'cl-atlas-anchor';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.hidden = true;
    doc.body.appendChild(canvas);
    ctx = (canvas.getContext) ? canvas.getContext('2d') : null;
    return !!ctx;
  }

  /* ---------------------------------------------------------------- 顶栏按钮 */
  function ensureButton() {
    if (vbBtn) return;
    var row = qs('#viewbar .vb-row:last-child');
    if (!row) return;
    vbBtn = doc.createElement('button');
    vbBtn.type = 'button';
    vbBtn.className = 'tgl';
    vbBtn.id = 'vbAtlas';
    vbBtn.setAttribute('aria-pressed', 'false');
    vbBtn.title = '展卷：把星盘平铺为逐线阅读的线谱（快捷键 U）';
    vbBtn.textContent = '展卷';
    vbBtn.addEventListener('click', function () { toggle(); });
    row.appendChild(vbBtn);
  }
  function syncButton() {
    if (!vbBtn) return;
    vbBtn.textContent = on ? '收卷' : '展卷';
    vbBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  /* ---------------------------------------------------------------- 旧面板运行时隐藏 */
  /* R7-G ③（R7-D 短板 4）：旧剧情 HUD 的运行时根其实是 #clPlot（js/hud/plot-hud.js:606
   * wrap.id='clPlot'，class .cl-plot，全代码域不存在任何 .cp-wrap 元素），原来 qs('.cp-wrap')
   * 恒为 null → 旧 HUD 开着时开展卷不会隐藏它。专修选择器：主查 getElementById('clPlot')，
   * .cp-wrap 仅作历史兼容退路；plot-hud 未挂载时两条查询都得 null，保持无操作。docProbe 仅供
   * tests/atlas_stage_contract.js（jsc 无 DOM）注入 mock 验证这条选择器路径，生产调用不传。 */
  function hidePanels(docProbe) {
    var d = docProbe || doc;
    saved.plot = null; saved.cpWrap = null;
    var p = (d && typeof d.getElementById === 'function') ? d.getElementById('plotTextPanel') : null;
    if (p) { saved.plot = { el: p, hidden: !!p.hidden }; p.hidden = true; }
    var w = (d && typeof d.getElementById === 'function') ? d.getElementById('clPlot') : null;
    if (!w && d && typeof d.querySelector === 'function') w = d.querySelector('#clPlot') || d.querySelector('.cp-wrap');
    if (w) { saved.cpWrap = { el: w, hidden: !!w.hidden }; w.hidden = true; }
  }
  function restorePanels() {
    if (saved.plot) { saved.plot.el.hidden = saved.plot.hidden; saved.plot = null; }
    if (saved.cpWrap) { saved.cpWrap.el.hidden = saved.cpWrap.hidden; saved.cpWrap = null; }
  }

  /* ---------------------------------------------------------------- 线谱挂载 */
  function missingNotice() {
    var p = doc.createElement('p');
    p.className = 'atlas-stage-missing';
    p.textContent = '线谱模块未加载';
    return p;
  }
  function mountScore(model) {
    if (!hostEl) return;
    hostEl.innerHTML = '';
    var Score = global.CLAtlasScore;
    if (!Score || typeof Score.mount !== 'function') { scoreHandle = null; hostEl.appendChild(missingNotice()); return; }
    try {
      scoreHandle = Score.mount(hostEl, {
        model: model,
        glyphs: global.CLAtlasGlyphs,
        onLine: function (id) { dispatch('cl:atlas-line', { id: id }); },
        onEvent: function (i) { dispatch('cl:atlas-event', { i: i }); },
        onCharacter: function (name) { dispatch('cl:atlas-character', { name: name }); },
        onBack: function () { close(); }
      }) || null;
    } catch (e) { scoreHandle = null; }
    if (!scoreHandle) { hostEl.innerHTML = ''; hostEl.appendChild(missingNotice()); }
  }
  function unmountScore() {
    if (scoreHandle && typeof scoreHandle.dispose === 'function') {
      try { scoreHandle.dispose(); } catch (e) {}
    }
    scoreHandle = null;
    if (hostEl) hostEl.innerHTML = '';
  }

  /* ---------------------------------------------------------------- 共享锚点动画 */
  function pickAnchorEvents(model) {
    if (!model || !model.events || !model.events.length) return [];
    var out = [];
    for (var i = 0; i < model.events.length && out.length < MAX_ANCHORS; i++) {
      var ev = model.events[i];
      if (ev && typeof ev.i === 'number') out.push(ev.i);
    }
    return out;
  }
  function rectCenter(el) {
    if (!el || typeof el.getBoundingClientRect !== 'function') return null;
    var r = el.getBoundingClientRect();
    if (!r || (r.width === 0 && r.height === 0)) return null;
    return [r.left + r.width / 2, r.top + r.height / 2];
  }
  function domEventEl(scopeEl, evIdx) {
    if (!scopeEl || !scopeEl.querySelector) return null;
    return scopeEl.querySelector('[data-ev="' + evIdx + '"]') ||
      scopeEl.querySelector('[data-atlas-event="' + evIdx + '"]') ||
      scopeEl.querySelector('[data-event-idx="' + evIdx + '"]');
  }
  /* 环位：优先问 CLPlotOrbit 拿投影后的屏幕坐标；它现在只给数据空间坐标，不给屏幕坐标，
   * 所以第二步永远会走到——退回 orbit3d 卡片/标签的 DOM rect（约定属性 data-ev，见
   * js/orbit3d/orbit3d-floaters.js）。两者都没有就是 null，调用方据此整体退化为淡入。 */
  function ringPos(evIdx) {
    try {
      var P = global.CLPlotOrbit;
      if (P && typeof P.eventAt === 'function') {
        var e = P.eventAt(evIdx);
        if (e) {
          var x = numOrNull(e.sx); if (x == null) x = numOrNull(e.screenX);
          var y = numOrNull(e.sy); if (y == null) y = numOrNull(e.screenY);
          if (x != null && y != null) return [x, y];
        }
      }
    } catch (e2) {}
    return rectCenter(domEventEl(doc, evIdx));
  }
  function scorePos(evIdx) { return rectCenter(domEventEl(hostEl, evIdx)); }
  function capture(evIdxs, fn) {
    var out = [];
    for (var i = 0; i < evIdxs.length; i++) out.push(fn(evIdxs[i]));
    return out;
  }

  function sizeCanvas() {
    if (!canvas) return;
    var dpr = global.devicePixelRatio || 1;
    var w = global.innerWidth || (doc.documentElement && doc.documentElement.clientWidth) || 0;
    var h = global.innerHeight || (doc.documentElement && doc.documentElement.clientHeight) || 0;
    canvas.width = Math.max(1, Math.round(w * dpr));
    canvas.height = Math.max(1, Math.round(h * dpr));
  }
  function clearCanvas() { if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height); }
  function anchorColor() {
    try {
      if (doc && doc.documentElement && global.getComputedStyle) {
        var v = global.getComputedStyle(doc.documentElement).getPropertyValue('--cl-gold');
        if (v && v.trim()) return v.trim();
      }
    } catch (e) {}
    return '#ffb45c';
  }
  function drawPoints(e) {
    if (!ctx || !canvas) return;
    clearCanvas();
    var dpr = global.devicePixelRatio || 1;
    ctx.save();
    ctx.fillStyle = anchorColor();
    for (var i = 0; i < anim.points.length; i++) {
      var pt = anim.points[i];
      var x = (pt.from[0] + (pt.to[0] - pt.from[0]) * e) * dpr;
      var y = (pt.from[1] + (pt.to[1] - pt.from[1]) * e) * dpr;
      ctx.beginPath();
      ctx.arc(x, y, 3 * dpr, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
  function drawFade(e, direction) {
    if (!ctx || !canvas) return;
    clearCanvas();
    var alpha = direction === 'open' ? e : (1 - e);
    ctx.save();
    ctx.fillStyle = 'rgba(6,4,12,' + (alpha * 0.7).toFixed(3) + ')';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  }
  function tickAnim() {
    anim.id = null;
    if (!anim.running) return;
    var p = (now() - anim.t0) / anim.dur;
    if (p > 1) p = 1;
    var e = easeOutCubic(p);
    if (anim.mode === 'points') drawPoints(e);
    else if (anim.mode === 'fade') drawFade(e, anim.direction);
    if (p >= 1) { finishAnchor(); return; }
    anim.id = raf(tickAnim);
  }
  function finishAnchor() {
    anim.running = false;
    if (anim.id != null) { caf(anim.id); anim.id = null; }
    clearCanvas();
    if (canvas) canvas.hidden = true;
    anim.mode = null; anim.direction = null; anim.points = [];
  }
  function cancelAnchor() {
    if (anim.id != null) { caf(anim.id); anim.id = null; }
    anim.running = false; anim.mode = null; anim.direction = null; anim.points = [];
    clearCanvas();
    if (canvas) canvas.hidden = true;
  }
  /* fromPts/toPts 必须在调用前各自捕捉好（分别在「隐藏旧面板/挂线谱」前后各拍一次），
   * 这样 open/close 的 DOM 状态切换本身完全同步、可立即断言；动画只是叠加的装饰层。 */
  function animateAnchors(fromPts, toPts, direction) {
    cancelAnchor();
    if (!ensureCanvas()) return;
    sizeCanvas();
    var reduced = prefersReduced();
    var dur = cssMs('--cl-atlas-dur-3', DEFAULT_DUR);
    var pts = [];
    for (var i = 0; i < fromPts.length; i++) {
      if (fromPts[i] && toPts[i]) pts.push({ from: fromPts[i], to: toPts[i] });
    }
    anim.direction = direction; anim.dur = dur;
    if (!pts.length) {
      anim.mode = 'fade';
      if (reduced) return; /* 直接跳：不显示任何过渡帧 */
      canvas.hidden = false;
      anim.running = true; anim.t0 = now(); anim.id = raf(tickAnim);
      return;
    }
    anim.mode = 'points'; anim.points = pts;
    if (reduced) return;
    canvas.hidden = false;
    anim.running = true; anim.t0 = now(); anim.id = raf(tickAnim);
  }

  /* ---------------------------------------------------------------- 开关 */
  function open() {
    init();
    if (on) {
      flushPendingFocus();
      return true;
    }
    if (!ensureDom()) return false;
    ensureButton();
    lastModel = buildModel();
    var evIdxs = pickAnchorEvents(lastModel);
    var fromPts = capture(evIdxs, ringPos); /* 环位：挂线谱之前拍 */
    var ht = headText(lastModel);
    if (nameEl) nameEl.textContent = ht.title;
    if (metaEl) metaEl.textContent = ht.meta;
    if (searchEl) searchEl.value = '';
    hidePanels();
    root.hidden = false;
    root.classList.add('on');
    mountScore(lastModel);
    on = true;
    syncButton();
    dispatch('cl:atlas-stage', { on: true });
    if (closeBtn && closeBtn.focus) { try { closeBtn.focus(); } catch (e) {} }
    var toPts = capture(evIdxs, scorePos); /* 谱位：挂线谱之后拍 */
    animateAnchors(fromPts, toPts, 'open');
    flushPendingFocus();
    return true;
  }

  function close() {
    if (!on) return false;
    var evIdxs = pickAnchorEvents(lastModel);
    var fromPts = capture(evIdxs, scorePos); /* 谱位：卸线谱之前拍 */
    unmountScore();
    restorePanels();
    root.classList.remove('on');
    root.hidden = true;
    on = false;
    syncButton();
    dispatch('cl:atlas-stage', { on: false });
    var toPts = capture(evIdxs, ringPos); /* 环位：星盘恢复可见之后拍 */
    animateAnchors(fromPts, toPts, 'close');
    return true;
  }

  function toggle() { if (on) { close(); } else { open(); } return on; }
  function isOn() { return !!on; }

  function setFocus(sel) {
    if (scoreHandle && typeof scoreHandle.setFocus === 'function') {
      try { return scoreHandle.setFocus(sel); } catch (e) { return undefined; }
    }
    return undefined;
  }
  function flushPendingFocus() {
    if (!pendingFocus || !pendingFocus.length) return;
    var first = pendingFocus[0];
    pendingFocus = null;
    setFocus({ lineId: first });
  }

  function step(ms) {
    var d = (typeof ms === 'number' && isFinite(ms)) ? ms : FALLBACK_STEP;
    if (anim.running) {
      anim.t0 -= d;
      if (anim.id != null) { caf(anim.id); anim.id = null; }
      tickAnim();
    }
    if (scoreHandle && typeof scoreHandle.step === 'function') {
      try { scoreHandle.step(ms); } catch (e) {}
    }
    return { on: on, animating: anim.running };
  }

  /* ---------------------------------------------------------------- 全局接线 */
  function onAtlasOpen(e) {
    var ids = e && e.detail && e.detail.lineIds;
    pendingFocus = (ids && ids.length) ? ids.slice(0) : null;
    open();
  }
  function onKeyDown(e) {
    if (global.CLInformationArchitecture && global.CLInformationArchitecture.isOpen()) return;
    if (global.CLAtlasPreview && global.CLAtlasPreview.active() && global.CLAtlasPreview.handlesKey(e)) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    if (isTypingTarget(e.target)) return;
    if ((e.key || '').toLowerCase() !== 'u') return;
    e.preventDefault();
    toggle();
  }

  function init() {
    if (initDone || !doc) return;
    initDone = true;
    onKeyRef = onKeyDown;
    global.addEventListener('keydown', onKeyRef, true);
    onAtlasOpenRef = onAtlasOpen;
    doc.addEventListener('cl:atlas-open', onAtlasOpenRef);
    ensureButton();
  }

  function dispose() {
    if (on) { try { close(); } catch (e) {} }
    cancelAnchor();
    if (onKeyRef) { global.removeEventListener('keydown', onKeyRef, true); onKeyRef = null; }
    if (onAtlasOpenRef && doc) { doc.removeEventListener('cl:atlas-open', onAtlasOpenRef); onAtlasOpenRef = null; }
    if (vbBtn && vbBtn.parentNode) vbBtn.parentNode.removeChild(vbBtn);
    vbBtn = null;
    if (root && root.parentNode) root.parentNode.removeChild(root);
    root = nameEl = metaEl = searchEl = closeBtn = hostEl = null;
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    canvas = null; ctx = null;
    scoreHandle = null;
    saved.plot = null; saved.cpWrap = null;
    pendingFocus = null;
    lastModel = null;
    on = false;
    initDone = false;
  }

  if (doc) {
    if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init);
    else init();
  }

  global.CLAtlasStage = {
    setModel: setModel,
    open: open,
    close: close,
    toggle: toggle,
    isOn: isOn,
    setFocus: setFocus,
    step: step,
    dispose: dispose,
    version: VERSION,
    /* 供 tests/atlas_stage_contract.js（jsc，无 DOM）直接检验的纯逻辑，不额外挂 window.__cl* */
    __test: {
      pickAnchorEvents: pickAnchorEvents,
      isTypingTarget: isTypingTarget,
      easeOutCubic: easeOutCubic,
      MAX_ANCHORS: MAX_ANCHORS,
      /* R7-G ③：隐藏路径（接受 mock document 注入，不影响生产路径——生产调用不传参） */
      hidePanels: hidePanels,
      restorePanels: restorePanels
    }
  };
})(typeof window !== 'undefined' ? window : this);
