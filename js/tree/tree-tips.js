/* @role component · @owns js/tree/tree-tips.js · @budget dom_nodes<=8 · @contract v46+v2-6 */
/**
 * tree-tips.js - H4: tree 家族 tooltip 三合一与图例键盘可达统一调度
 * 整合原:
 *   - js/tree-legend-tip.js (图例 hover 悬浮说明)
 *   - js/tree-twig-tip.js (枝干拾取悬浮提示)
 *   - js/tree-legend-kbd.js (图例键盘浏览与导航 [ / ] / Enter)
 *
 * 核心保证：
 * 1. 同屏单 tip 互斥律：legend / twig / help / kbd 任何时刻至多显示一个悬浮提示；
 * 2. 100% 向下兼容 window.CLLegendTip, window.CLTwigTip, window.CLLegendKbd；
 * 3. 统一提供 window.CLTreeTips 调度器。
 *
 * R2 三态（V2-6 新增，双域 legend-tip / tree-tip）：
 *   - blank（非态）＝未 hover / 树剧情态未激活 ⇒ tip 整体退场（hidden），与改前一致；
 *   - empty ＝「本页适用但无数据」：图例未知名（LEGEND_TIPS 无此键）／枝干无载记
 *     （CLTreeEvents.info() 回 null）⇒ 改前分别弹出**完全空的 tip 壳**／**静默 hide**，
 *     现在出该域铭文（status-states 引擎，域铭文取自 EMPTY_INSCRIPTIONS）；
 *   - degraded ＝有内容但有损（枝干载记缺标题与出场）⇒ 断态条压在内容之上，**内容照常出**
 *     （E26 口径：degraded 不得吞内容）；
 *   - ready ＝其余。loading 不适用（取数是同步的，无异步窗口）。
 * 态节点独立于内容面（摘挂不毁节点）；同态同文备忘录挡 hover 高频路径的 DOM churn。
 */
(function () {
  'use strict';

  var NAME = 'tree-tips';

  /* =========================================================================
   * 1. 共享环境与无障碍判定
   * ========================================================================= */
  function rootEl() { return document.documentElement; }
  function prefersReduce() {
    try { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
    catch (e) { return false; }
  }
  function lowTier() {
    try { return rootEl().dataset.tier === 'low'; }
    catch (e) { return false; }
  }
  function isStatic() { return prefersReduce() || lowTier(); }

  /* =========================================================================
   * 2. 图例说明 (Legend Tip) 数据与逻辑
   * ========================================================================= */
  var LEGEND_TIPS = {
    '高燃': '情绪与冲突同时到顶的场面',
    '转折': '故事方向在此改变',
    '抉择': '角色做出不可回头的选择',
    '冲突': '目标相撞，正面交锋',
    '关系': '关系建立、破裂或转向',
    '领悟': '角色看清了某件事',
    '日常': '铺垫与呼吸的段落'
  };

  var legendTipEl = null, legBEl = null, legNumEl = null, legDEl = null;
  var legendShows = 0, curLegKind = null, curLegCount = null;
  /* R2 三态（V2-6）：legend-tip 域。内容面登记表 + 独立态节点（摘挂，不毁节点）。 */
  var legStruct = null, legStateEl = null, legStKind = '', legStNotice = '';

  function ensureLegendDom() {
    if (legendTipEl) return legendTipEl;
    if (!document.body) return null;
    legendTipEl = document.createElement('div');
    legendTipEl.id = 'clLegendTip';
    legendTipEl.className = 'cl-tip cl-tooltip';
    legendTipEl.hidden = true;

    legBEl = document.createElement('b');
    legNumEl = document.createElement('span');
    legDEl = document.createElement('span');
    legendTipEl.appendChild(legBEl);
    legendTipEl.appendChild(legNumEl);
    legendTipEl.appendChild(legDEl);

    legStateEl = document.createElement('div');
    legStateEl.className = 'cl-legend-tip__state';
    legendTipEl.appendChild(legStateEl);
    legStruct = [legBEl, legNumEl, legDEl];

    document.body.appendChild(legendTipEl);
    syncLegendStatic();
    return legendTipEl;
  }

  function syncLegendStatic() {
    if (!legendTipEl) return;
    if (isStatic()) legendTipEl.setAttribute('data-static', '1');
    else legendTipEl.removeAttribute('data-static');
  }

  /* ---- R2 态机（legend-tip）------------------------------------------------ */
  function attachLegStruct() {
    if (!legendTipEl || !legStruct) return;
    for (var i = 0; i < legStruct.length; i++) { if (!legStruct[i].parentNode) legendTipEl.appendChild(legStruct[i]); }
  }
  function detachLegStruct() {
    if (!legStruct) return;
    for (var i = 0; i < legStruct.length; i++) { var n = legStruct[i]; if (n && n.parentNode) n.parentNode.removeChild(n); }
  }
  /* empty 扣内容面出铭文；degraded 压断态条且内容照出；ready 无态节点。
   * 同态同文即返回：hover 逐帧重入不产生 DOM churn。 */
  function setLegendState(state, notice) {
    if (!legendTipEl || !legStateEl) return;
    notice = notice || '';
    if (state === legStKind && notice === legStNotice) return;
    legStKind = state; legStNotice = notice;
    legendTipEl.setAttribute('data-tip-state', state);
    if (legStateEl.parentNode) legStateEl.parentNode.removeChild(legStateEl);
    if (state === 'empty') {
      detachLegStruct();
      legendTipEl.appendChild(legStateEl);
    } else {
      attachLegStruct();
      if (state === 'degraded' && legStruct && legStruct[0].parentNode === legendTipEl) {
        legendTipEl.insertBefore(legStateEl, legStruct[0]);
      }
    }
    var SS = window.CLStatusStates;
    if (state === 'ready' || !legStateEl.parentNode || !SS || !SS.applyState) return;
    SS.applyState(legStateEl, state, { domain: 'legend-tip', minHeight: 34, notice: notice });
  }

  function legendText(kind) {
    return LEGEND_TIPS[kind] || '';
  }

  function placeLegend(row) {
    if (!row || !row.getBoundingClientRect || !legendTipEl) return;
    var r = row.getBoundingClientRect();
    var tw = legendTipEl.offsetWidth, th = legendTipEl.offsetHeight;
    var gap = 12;
    var x = r.right + gap;
    if (x + tw > window.innerWidth) x = r.left - gap - tw;
    if (x < 0) x = 0;
    var y = r.top + (r.height - th) / 2;
    var maxY = window.innerHeight - th;
    if (y < 0) y = 0;
    else if (y > maxY) y = maxY;
    legendTipEl.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
  }

  function showLegend(kind, row) {
    /* 互斥：显示图例时强行隐藏树枝 tip */
    hideTwig();

    if (!ensureLegendDom()) return false;
    kind = kind || '';
    var count = '';
    if (row && row.querySelector) {
      var v = row.querySelector('v');
      if (v) count = (v.textContent || '').trim();
    }
    curLegKind = kind;
    curLegCount = count;
    /* R2：未知名 / 空 kind ⇒ 该域空态铭文（改前：弹出 b/span/span 全空的 tip 壳）。 */
    var desc = legendText(kind);
    if (!kind || !desc) setLegendState('empty');
    else setLegendState('ready');
    legBEl.textContent = kind;
    legNumEl.textContent = count ? (' · ' + count + ' ') : ' ';
    legDEl.textContent = desc;
    syncLegendStatic();
    legendTipEl.hidden = false;
    placeLegend(row);
    legendShows++;
    return true;
  }

  function hideLegend() {
    if (!legendTipEl) return;
    legendTipEl.hidden = true;
  }

  function legendRowOf(e) {
    var t = e.target;
    if (!t || !t.closest) return null;
    return t.closest('#clTreeLegend .r');
  }

  function onLegendOver(e) {
    var row = legendRowOf(e);
    if (!row) return;
    if (row.contains(e.relatedTarget)) return;
    var u = row.querySelector('u');
    showLegend(u ? (u.textContent || '').trim() : '', row);
  }

  function onLegendOut(e) {
    var row = legendRowOf(e);
    if (!row) return;
    if (row.contains(e.relatedTarget)) return;
    hideLegend();
  }

  function legendStats() {
    return {
      ready: !!legendTipEl,
      visible: !!(legendTipEl && !legendTipEl.hidden),
      state: legStKind,
      kind: curLegKind,
      count: curLegCount,
      shows: legendShows
    };
  }

  /* =========================================================================
   * 3. 枝干拾取提示 (Twig Tip) 数据与逻辑
   * ========================================================================= */
  var GAP_TOKEN = '--cl-tip-gap';
  var FALLBACK_GAP = 14;
  var PX = 'px';
  var POLL_MS = 100, POLL_MAX = 15000;
  var LEAD_MAX = 3;
  var MOVE_STRIDE = 3, FRAME_STRIDE = 6;

  var twigTipEl = null, twigBEl = null, twigIEl = null, twigSpanEl = null;
  var twigReady = false, twigBound = false, twigVisible = false, curTwigEv = -1, twigShows = 0;
  /* R2 三态（V2-6）：tree-tip 域。内容面登记表 + 独立态节点。 */
  var twigStruct = null, twigStateEl = null, twigStKind = '', twigStNotice = '';
  var twigPointer = { x: 0, y: 0, has: false };
  var twigMoves = 0, twigFrame = 0, twigRafId = 0;

  function ensureTwigDom() {
    if (twigTipEl) return twigTipEl;
    twigTipEl = document.createElement('div');
    twigTipEl.id = 'clTwigTip';
    twigTipEl.className = 'cl-tooltip';
    twigTipEl.setAttribute('hidden', '');
    twigTipEl.style.position = 'fixed';
    twigTipEl.style.pointerEvents = 'none';
    twigBEl = document.createElement('b');
    twigIEl = document.createElement('i');
    twigSpanEl = document.createElement('span');
    twigTipEl.appendChild(twigBEl);
    twigTipEl.appendChild(twigIEl);
    twigTipEl.appendChild(twigSpanEl);
    twigStateEl = document.createElement('div');
    twigStateEl.className = 'cl-twig-tip__state';
    twigTipEl.appendChild(twigStateEl);
    twigStruct = [twigBEl, twigIEl, twigSpanEl];
    (document.body || rootEl()).appendChild(twigTipEl);
    return twigTipEl;
  }

  function applyTwigStatic() {
    if (!twigTipEl) return;
    if (isStatic()) twigTipEl.setAttribute('data-static', '1');
    else twigTipEl.removeAttribute('data-static');
  }

  function gapPx() {
    var v = '';
    try { v = getComputedStyle(rootEl()).getPropertyValue(GAP_TOKEN) || ''; }
    catch (e) { v = ''; }
    var n = parseFloat(String(v).trim());
    return isFinite(n) && n >= 0 ? n : FALLBACK_GAP;
  }

  function namesText(chars) {
    var arr = Array.isArray(chars) ? chars : [];
    var names = [];
    for (var k = 0; k < arr.length; k++) {
      if (arr[k] !== null && arr[k] !== undefined && arr[k] !== '') names.push(String(arr[k]));
    }
    if (names.length <= LEAD_MAX) return names.join('、');
    return names.slice(0, LEAD_MAX).join('、') + '等 ' + (names.length - LEAD_MAX) + ' 人';
  }

  function readTwigInfo(evIdx) {
    var info = null;
    try { if (window.CLTreeEvents) info = window.CLTreeEvents.info(evIdx); }
    catch (e) { info = null; }
    return (info && typeof info === 'object') ? info : null;
  }

  function str(v) { return v === null || v === undefined ? '' : String(v); }

  function renderTwig(info) {
    var kind = str(info.kind), chapter = str(info.chapter);
    twigBEl.textContent = chapter ? (kind ? kind + ' · ' + chapter : chapter) : kind;
    twigIEl.textContent = str(info.title);
    twigSpanEl.textContent = namesText(info.characters);
  }

  /* ---- R2 态机（tree-tip）-------------------------------------------------- */
  function attachTwigStruct() {
    if (!twigTipEl || !twigStruct) return;
    for (var i = 0; i < twigStruct.length; i++) { if (!twigStruct[i].parentNode) twigTipEl.appendChild(twigStruct[i]); }
  }
  function detachTwigStruct() {
    if (!twigStruct) return;
    for (var i = 0; i < twigStruct.length; i++) { var n = twigStruct[i]; if (n && n.parentNode) n.parentNode.removeChild(n); }
  }
  /* 同 legend：empty 扣内容面出铭文；degraded 压断态条且**内容照出**（E26）；ready 无态节点。
   * ⚠ degraded 必须带 notice —— 引擎的 renderDegraded 无 notice 时产 0 子节点容器（0 高不可见，
   *   V2-3 的 E18 同款空洞态）。 */
  function setTwigState(state, notice) {
    if (!twigTipEl || !twigStateEl) return;
    notice = notice || '';
    if (state === twigStKind && notice === twigStNotice) return;
    twigStKind = state; twigStNotice = notice;
    twigTipEl.setAttribute('data-tip-state', state);
    if (twigStateEl.parentNode) twigStateEl.parentNode.removeChild(twigStateEl);
    if (state === 'empty') {
      detachTwigStruct();
      twigTipEl.appendChild(twigStateEl);
    } else {
      attachTwigStruct();
      if (state === 'degraded' && twigStruct && twigStruct[0].parentNode === twigTipEl) {
        twigTipEl.insertBefore(twigStateEl, twigStruct[0]);
      }
    }
    var SS = window.CLStatusStates;
    if (state === 'ready' || !twigStateEl.parentNode || !SS || !SS.applyState) return;
    SS.applyState(twigStateEl, state, { domain: 'tree-tip', minHeight: 34, notice: notice });
  }

  function updatePicked(evIdx) {
    var picked = false;
    try {
      var g = window.CLTreeEvents && window.CLTreeEvents.get();
      picked = !!(g && g.evIdx === evIdx);
    } catch (e) { picked = false; }
    if (picked) twigTipEl.setAttribute('data-picked', '1');
    else twigTipEl.removeAttribute('data-picked');
  }

  function placeTwig(x, y) {
    var g = gapPx();
    var w = twigTipEl.offsetWidth || 0, h = twigTipEl.offsetHeight || 0;
    var vw = window.innerWidth || rootEl().clientWidth || 0;
    var vh = window.innerHeight || rootEl().clientHeight || 0;
    var left = x + g, top = y + g;
    if (w && left + w > vw) left = x - w - g;
    if (h && top + h > vh) top = y - h - g;
    if (left < 0) left = 0;
    if (top < 0) top = 0;
    twigTipEl.style.left = left + PX;
    twigTipEl.style.top = top + PX;
  }

  function hideTwig() {
    if (twigTipEl) twigTipEl.setAttribute('hidden', '');
    twigVisible = false;
    curTwigEv = -1;
  }

  function showTwig(evIdx, x, y) {
    if (typeof evIdx !== 'number' || evIdx < 0) return false;

    /* 互斥：显示枝干 tip 时强行隐藏图例 tip */
    hideLegend();

    ensureTwigDom();
    applyTwigStatic();
    if (twigVisible && curTwigEv === evIdx) {
      updatePicked(evIdx);
      placeTwig(x, y);
      return true;
    }
    var info = readTwigInfo(evIdx);
    if (!info) {
      /* R2：本页适用（正 hover 一根枝）但该位无载记 ⇒ 空态铭文，不再静默退场。
       * 改前是 `hideTwig(); return false;`（调用方与用户都拿零反馈，R2 要消灭的那一类静默）。 */
      setTwigState('empty');
      twigTipEl.removeAttribute('hidden');
      updatePicked(evIdx);
      placeTwig(x, y);
      twigVisible = true;
      curTwigEv = evIdx;
      twigShows++;
      return true;
    }
    renderTwig(info);
    /* R2：有载记但标题与出场双缺 ⇒ degraded + 断态条，内容照常出（kind/chapter 仍在）。 */
    if (!str(info.title) && !namesText(info.characters)) {
      setTwigState('degraded', '该位载记不全 · 缺标题与出场');
    } else {
      setTwigState('ready');
    }
    updatePicked(evIdx);
    twigTipEl.removeAttribute('hidden');
    placeTwig(x, y);
    twigVisible = true;
    curTwigEv = evIdx;
    twigShows++;
    return true;
  }

  function twigDepsReady() {
    try {
      return !!(window.CLTwigPick && typeof window.CLTwigPick.stats === 'function'
        && window.CLTreeEvents && typeof window.CLTreeEvents.info === 'function'
        && typeof window.CLTreeEvents.get === 'function'
        && window.CLTreeStage && typeof window.CLTreeStage.active === 'function');
    } catch (e) { return false; }
  }

  function isTreePlotActive() {
    try {
      if (window.CLTreeStage && typeof window.CLTreeStage.active === 'function') {
        if (!window.CLTreeStage.active()) return false;
      }
      if (window.CLTreeGate && typeof window.CLTreeGate.state === 'function') {
        if (window.CLTreeStage && typeof window.CLTreeStage.active === 'function' && window.CLTreeStage.active() && window.CLTreeGate.state() === 'stars') {
          if (typeof window.CLTreeGate.setState === 'function' && !window.CLTreeGate.__tipSync) {
            window.CLTreeGate.__tipSync = true;
            try { window.CLTreeGate.setState('plot'); } catch (e0) {}
          }
        }
        if (window.CLTreeGate.state() === 'stars') return false;
      }
      return true;
    } catch (e) { return true; }
  }

  function syncTwig() {
    if (!twigReady) { hideTwig(); return; }
    if (!isTreePlotActive()) { hideTwig(); return; }
    var hov = -1;
    try { hov = window.CLTwigPick.stats().hoverEv; } catch (e) { hov = -1; }
    if (typeof hov !== 'number' || hov < 0 || !twigPointer.has) { hideTwig(); return; }
    showTwig(hov, twigPointer.x, twigPointer.y);
  }

  function onTwigMove(e) {
    twigPointer.x = e.clientX;
    twigPointer.y = e.clientY;
    twigPointer.has = true;
    twigMoves++;
    if (twigMoves % MOVE_STRIDE === 0) syncTwig();
  }

  function twigLoop() {
    if (!!(window.CLSky && CLSky.enabled && CLSky.enabled())) { twigRafId = 0; return; }   /* 星空壳：旧剧情树不在屏上 */
    twigRafId = requestAnimationFrame(twigLoop);
    twigFrame++;
    if (twigFrame % FRAME_STRIDE === 0) syncTwig();
  }

  function bindTwig() {
    if (twigBound) return;
    twigBound = true;
    try {
      window.addEventListener('pointermove', onTwigMove, { passive: true });
      document.addEventListener('pointermove', onTwigMove, { passive: true });
      document.addEventListener('cl:tree-plotline', function (ev) {
        var d = ev && ev.detail;
        if (d && d.on === false) hideTwig();
      });
    } catch (e) {
      window.addEventListener('pointermove', onTwigMove, false);
      document.addEventListener('pointermove', onTwigMove, false);
    }
    try { twigRafId = requestAnimationFrame(twigLoop); } catch (e) {}
  }

  function bootTwig() {
    ensureTwigDom();
    applyTwigStatic();
    if (twigDepsReady()) { twigReady = true; bindTwig(); return; }
    var t0 = Date.now();
    var timer = setInterval(function () {
      if (twigDepsReady()) { clearInterval(timer); twigReady = true; bindTwig(); applyTwigStatic(); return; }
      if (Date.now() - t0 >= POLL_MAX) clearInterval(timer);
    }, POLL_MS);
  }

  function twigStats() {
    return { ready: twigReady, visible: twigVisible, state: twigStKind, evIdx: curTwigEv, shows: twigShows };
  }

  /* =========================================================================
   * 4. 图例键盘导航 (Legend Kbd) 数据与逻辑
   * ========================================================================= */
  var kbdState = {
    ready: false,
    index: -1,
    kind: null,
    rows: []
  };
  var kbdTimer = null;
  var kbdTries = 0;
  var kbdBound = false;

  function legendContainer() {
    return document.getElementById('clTreeLegend');
  }

  function legendModule() {
    return window.CLTreeLegend || null;
  }

  function isLegendVisible() {
    var L = legendModule();
    var c = legendContainer();
    if (!L || !c) return false;
    if (typeof L.visible === 'function') {
      try { return !!L.visible(); } catch (e) { return false; }
    }
    return c.offsetParent !== null;
  }

  function legendRows() {
    var c = legendContainer();
    if (!c) return [];
    return Array.prototype.slice.call(c.querySelectorAll('.r'));
  }

  function kindOfLegendRow(row) {
    if (!row) return null;
    var u = row.querySelector('u');
    if (u && u.textContent) return u.textContent.trim();
    var v = row.getAttribute('data-kind');
    return v || null;
  }

  function clearKbdMarks() {
    var list = legendRows();
    for (var i = 0; i < list.length; i++) {
      if (list[i].hasAttribute('data-kbd')) list[i].removeAttribute('data-kbd');
    }
  }

  function markKbd(row) {
    clearKbdMarks();
    if (row) row.setAttribute('data-kbd', '1');
  }

  function resolveKbdIndex(list) {
    if (kbdState.index >= 0 && kbdState.index < list.length) return kbdState.index;
    for (var i = 0; i < list.length; i++) {
      if (list[i].getAttribute('data-kbd') === '1') return i;
    }
    return -1;
  }

  function syncKbd() {
    var list = legendRows();
    kbdState.rows = list.map(kindOfLegendRow);
    kbdState.index = resolveKbdIndex(list);
    kbdState.kind = kbdState.index >= 0 ? kindOfLegendRow(list[kbdState.index]) : null;
    return list;
  }

  function moveKbd(dir) {
    if (!isLegendVisible()) return -1;
    var list = syncKbd();
    if (!list.length) {
      kbdState.index = -1;
      kbdState.kind = null;
      kbdState.rows = [];
      return -1;
    }
    var i = kbdState.index;
    var next = i < 0 ? (dir > 0 ? 0 : list.length - 1) : i + dir;
    if (next < 0) next = list.length - 1;
    if (next >= list.length) next = 0;
    kbdState.index = next;
    kbdState.kind = kindOfLegendRow(list[next]);
    kbdState.rows = list.map(kindOfLegendRow);
    markKbd(list[next]);

    /* 键盘导航联动显示当前 row 图例 tip */
    showLegend(kbdState.kind, list[next]);
    return kbdState.index;
  }

  function activateKbd() {
    if (!isLegendVisible()) return false;
    var list = syncKbd();
    var i = kbdState.index;
    if (i < 0 || i >= list.length) return false;
    var row = list[i];
    if (!row) return false;
    row.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    return true;
  }

  function indexKbd() {
    if (kbdState.index < 0) syncKbd();
    return kbdState.index;
  }

  function isTypingTarget(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    return false;
  }

  function onKbdKeydown(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (isTypingTarget(e.target)) return;
    if (!isLegendVisible()) return;
    var k = e.key;
    if (k === '[') {
      moveKbd(-1);
      if (e.preventDefault) e.preventDefault();
    } else if (k === ']') {
      moveKbd(1);
      if (e.preventDefault) e.preventDefault();
    } else if (k === 'Enter') {
      if (kbdState.index >= 0) {
        activateKbd();
        if (e.preventDefault) e.preventDefault();
      }
    }
  }

  function kbdStats() {
    syncKbd();
    return {
      ready: kbdState.ready,
      index: kbdState.index,
      kind: kbdState.kind,
      rows: kbdState.rows
    };
  }

  function bootKbd() {
    if (window.CLTreeLegend && typeof window.CLTreeLegend.visible === 'function') {
      kbdState.ready = true;
      if (kbdTimer) { clearInterval(kbdTimer); kbdTimer = null; }
      if (!kbdBound) {
        window.addEventListener('keydown', onKbdKeydown, false);
        kbdBound = true;
      }
      return;
    }
    kbdTries += 1;
    if (kbdTries * POLL_MS >= POLL_MAX) {
      kbdState.ready = false;
      if (kbdTimer) { clearInterval(kbdTimer); kbdTimer = null; }
    }
  }

  /* =========================================================================
   * 5. 全局初始化与门面发布
   * ========================================================================= */
  function init() {
    ensureLegendDom();
    document.addEventListener('mouseover', onLegendOver, false);
    document.addEventListener('mouseout', onLegendOut, false);
    bootTwig();
    bootKbd();
    if (!kbdState.ready) kbdTimer = setInterval(bootKbd, POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }

  /* 核心总管：CLTreeTips */
  var CLTreeTips = {
    name: NAME,
    show: function (type, a, b) {
      if (type === 'legend') return showLegend(a, b);
      if (type === 'twig') return showTwig(a, a, b);
      return false;
    },
    hide: function (type) {
      if (type === 'legend') hideLegend();
      else if (type === 'twig') hideTwig();
      else {
        hideLegend();
        hideTwig();
      }
    },
    showLegend: showLegend,
    hideLegend: hideLegend,
    legendText: legendText,
    legendStats: legendStats,

    showTwig: function (evIdx, x, y) {
      var px = typeof x === 'number' ? x : twigPointer.x;
      var py = typeof y === 'number' ? y : twigPointer.y;
      return showTwig(evIdx, px, py);
    },
    hideTwig: hideTwig,
    twigStats: twigStats,

    kbdMove: moveKbd,
    kbdActivate: activateKbd,
    kbdIndex: indexKbd,
    kbdStats: kbdStats,

    stats: function () {
      return {
        legend: legendStats(),
        twig: twigStats(),
        kbd: kbdStats(),
        activeTip: (legendStats().visible ? 'legend' : (twigStats().visible ? 'twig' : 'none'))
      };
    }
  };

  window.CLTreeTips = CLTreeTips;

  /* 兼容导出 1: CLLegendTip */
  window.CLLegendTip = {
    name: 'tree-legend-tip',
    show: showLegend,
    hide: hideLegend,
    text: legendText,
    stats: legendStats
  };

  /* 兼容导出 2: CLTwigTip */
  window.CLTwigTip = {
    name: 'tree-twig-tip',
    show: function (evIdx, x, y) {
      return CLTreeTips.showTwig(evIdx, x, y);
    },
    hide: hideTwig,
    stats: twigStats
  };

  /* 兼容导出 3: CLLegendKbd */
  window.CLLegendKbd = {
    name: 'tree-legend-kbd',
    move: moveKbd,
    activate: activateKbd,
    index: indexKbd,
    stats: kbdStats
  };
})();
