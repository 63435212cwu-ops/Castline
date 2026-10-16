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

  function place(anchor) {
    if (!tipEl) return;
    var vw = g.innerWidth || (DOC && DOC.documentElement.clientWidth) || 1440;
    var vh = g.innerHeight || (DOC && DOC.documentElement.clientHeight) || 900;
    var tw = tipEl.offsetWidth || 160;
    var th = tipEl.offsetHeight || 36;

    var x = 0, y = 0;
    if (anchor && typeof anchor.clientX === 'number') {
      x = anchor.clientX + GAP;
      y = anchor.clientY + GAP;
      if (x + tw > vw) x = anchor.clientX - tw - GAP;
      if (y + th > vh) y = anchor.clientY - th - GAP;
    } else if (anchor && anchor.getBoundingClientRect) {
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

  function show(options) {
    options = options || {};
    clearDwell();

    if (g.CLTreeTips && typeof g.CLTreeTips.hide === 'function') {
      try { g.CLTreeTips.hide(); } catch (e) {}
    }

    if (!ensureDom()) return false;

    var type = options.type || 'general';
    currentType = type;
    currentTarget = options.anchor || null;

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
