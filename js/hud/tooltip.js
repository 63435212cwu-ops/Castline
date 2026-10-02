/* @role component · @owns js/hud/tooltip.js · @budget dom_nodes=1 js_ms=0.03 · @contract v54 */
/**
 * tooltip.js - D4: 全局 Tooltip 大一统体系
 *
 * 核心法则：
 * 1. 单例调度：全屏任何时刻至多同时存在 1 个 Tooltip 实体，同屏永不双 tip；
 * 2. 边缘翻转（Edge Flip）：右侧溢出左翻、底部溢出上翻，杜绝视口截断；
 * 3. 200ms 驻留防闪烁（Anti-Flicker Dwell）：移出时保留 200ms 缓冲区，防鼠标抖动误关；
 * 4. 样式只认 .cl-tooltip，全域继承 A5 --z-tooltip (300) 音阶与玻璃材质；
 * 5. 无缝桥接：支持 type ∈ legend / twig / kbd / help / node / attr，并与 CLTreeTips 互斥。
 */
(function (g) {
  'use strict';

  var NAME = 'tooltip';
  var VERSION = '54';
  var DWELL_MS = 200;
  var GAP = 12;

  var DOC = (typeof document !== 'undefined') ? document : null;

  var tipEl = null;
  var titleEl = null;
  var bodyEl = null;
  var extraEl = null;

  var isVisible = false;
  var currentType = null;
  var dwellTimer = null;
  var showsCount = 0;
  var currentTarget = null;

  function ensureDom() {
    if (tipEl) return tipEl;
    if (!DOC || !DOC.body) return null;

    tipEl = DOC.createElement('div');
    tipEl.id = 'clGlobalTooltip';
    tipEl.className = 'cl-tooltip cl-panel-subtle';
    tipEl.setAttribute('role', 'tooltip');
    tipEl.setAttribute('aria-hidden', 'true');
    tipEl.style.position = 'fixed';
    tipEl.style.pointerEvents = 'none';
    tipEl.style.zIndex = 'var(--z-tooltip, 300)';
    tipEl.hidden = true;

    titleEl = DOC.createElement('b');
    titleEl.className = 'cl-tooltip__title';

    bodyEl = DOC.createElement('span');
    bodyEl.className = 'cl-tooltip__body';

    extraEl = DOC.createElement('span');
    extraEl.className = 'cl-tooltip__extra';

    tipEl.appendChild(titleEl);
    tipEl.appendChild(bodyEl);
    tipEl.appendChild(extraEl);

    DOC.body.appendChild(tipEl);
    return tipEl;
  }

  function clearDwell() {
    if (dwellTimer) {
      clearTimeout(dwellTimer);
      dwellTimer = null;
    }
  }

  /**
   * 边缘翻转与智能定位
   */
  function place(anchor) {
    if (!tipEl) return;
    var vw = g.innerWidth || (DOC && DOC.documentElement.clientWidth) || 1440;
    var vh = g.innerHeight || (DOC && DOC.documentElement.clientHeight) || 900;
    var tw = tipEl.offsetWidth || 160;
    var th = tipEl.offsetHeight || 36;

    var x = 0, y = 0;
    if (anchor && typeof anchor.clientX === 'number') {
      /* 鼠标光标坐标 */
      x = anchor.clientX + GAP;
      y = anchor.clientY + GAP;
      if (x + tw > vw) x = anchor.clientX - tw - GAP;
      if (y + th > vh) y = anchor.clientY - th - GAP;
    } else if (anchor && anchor.getBoundingClientRect) {
      /* DOM 元素坐标 */
      var r = anchor.getBoundingClientRect();
      x = r.right + GAP;
      y = r.top + (r.height - th) / 2;
      if (x + tw > vw) x = r.left - tw - GAP;
      if (y + th > vh) y = vh - th - GAP;
    }

    if (x < 0) x = 0;
    if (y < 0) y = 0;

    tipEl.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
  }

  /**
   * 显示 Tooltip
   * @param {Object} options - { type, title, body, extra, anchor, x, y }
   */
  function show(options) {
    options = options || {};
    clearDwell();

    /* 互斥律：若激活了全局 Tooltip，收回 tree 家族独立 tip */
    if (g.CLTreeTips && typeof g.CLTreeTips.hide === 'function') {
      try { g.CLTreeTips.hide(); } catch (e) {}
    }

    if (!ensureDom()) return false;

    var type = options.type || 'general';
    currentType = type;
    currentTarget = options.anchor || null;

    /* 内容渲染 */
    titleEl.textContent = options.title || '';
    titleEl.style.display = options.title ? '' : 'none';

    bodyEl.textContent = options.body || (typeof options === 'string' ? options : '');
    bodyEl.style.display = bodyEl.textContent ? '' : 'none';

    extraEl.textContent = options.extra ? (' · ' + options.extra) : '';
    extraEl.style.display = options.extra ? '' : 'none';

    tipEl.setAttribute('data-type', type);
    tipEl.removeAttribute('hidden');
    tipEl.setAttribute('aria-hidden', 'false');
    isVisible = true;
    showsCount++;

    var anchor = options.anchor || (typeof options.x === 'number' ? { clientX: options.x, clientY: options.y } : null);
    place(anchor);
    return true;
  }

  /**
   * 隐藏 Tooltip（带 200ms 防闪烁驻留）
   * @param {boolean} [immediate=false] - 是否立即隐藏
   */
  function hide(immediate) {
    clearDwell();
    if (immediate) {
      doHide();
      return;
    }
    dwellTimer = setTimeout(doHide, DWELL_MS);
  }

  function doHide() {
    clearDwell();
    if (!tipEl) return;
    tipEl.setAttribute('hidden', '');
    tipEl.setAttribute('aria-hidden', 'true');
    isVisible = false;
    currentType = null;
    currentTarget = null;
  }

  function stats() {
    return {
      name: NAME,
      version: VERSION,
      ready: !!tipEl,
      visible: isVisible,
      type: currentType,
      shows: showsCount,
      dwellMs: DWELL_MS
    };
  }

  /* 全局事件委托：自动发现带有 [data-tip] 或 [title] 的元素 */
  function onDocOver(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var tipTarget = t.closest('[data-tip]');
    if (!tipTarget) return;

    var text = tipTarget.getAttribute('data-tip');
    if (!text) return;

    var title = tipTarget.getAttribute('data-tip-title') || '';
    var type = tipTarget.getAttribute('data-tip-type') || 'general';
    show({ type: type, title: title, body: text, anchor: e });
  }

  function onDocOut(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var tipTarget = t.closest('[data-tip]');
    if (!tipTarget) return;
    if (tipTarget.contains(e.relatedTarget)) return;
    hide(false);
  }

  function init() {
    ensureDom();
    if (DOC) {
      DOC.addEventListener('mouseover', onDocOver, false);
      DOC.addEventListener('mouseout', onDocOut, false);
    }
  }

  if (DOC && DOC.readyState === 'loading') {
    DOC.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  var API = {
    name: NAME,
    version: VERSION,
    show: show,
    hide: hide,
    stats: stats
  };

  g.CLTooltip = API;
  if (!g.__cl) g.__cl = {};
  g.__cl.tooltip = API;

})(typeof window !== 'undefined' ? window : this);
