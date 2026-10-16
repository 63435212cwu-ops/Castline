(function (g) {
  'use strict';

  var NAME = 'panel-manager';
  var VERSION = '55';

  var DOC = (typeof document !== 'undefined') ? document : null;

  var registry = {};
  var panelStack = [];
  var currentActive = null;
  var a11yEl = null;

  var DEFAULT_TIERS = {
    'modal': { tier: 'modal', z: 500, modal: true, title: '模态窗口' },
    'library': { tier: 'modal', z: 500, modal: true, title: '作品库' },
    'keys': { tier: 'modal', z: 500, modal: true, title: '快捷键速查' },
    'dock': { tier: 'dock', z: 400, modal: false, title: '角色资料坞' },
    'evidence': { tier: 'panel', z: 200, modal: false, title: '雷达证据卡' },
    'plotTextPanel': { tier: 'panel', z: 200, modal: false, title: '剧情文本' },
    'ops': { tier: 'panel', z: 200, modal: false, title: '操作栏' },
    'viewbar': { tier: 'panel', z: 200, modal: false, title: '视图栏' },
    'tray': { tier: 'panel', z: 200, modal: false, title: '托盘' },
    'card': { tier: 'panel', z: 200, modal: false, title: '卡片' }
  };

  function injectFocusRing() {
    if (!DOC || DOC.getElementById('clFocusRing')) return;
    try {
      var s = DOC.createElement('style');
      s.id = 'clFocusRing';
      s.textContent = ':focus-visible:not(:where(body.sky-shell.skd-gl .sky-hud *, body.sky-shell.skd-gl .skd-deck *, body.sky-shell.skd-gl .skg-deck *, body.sky-shell.skd-gl .skd-views *)) { outline: 2px solid var(--abyss-mint, #7af0c8) !important; outline-offset: 2px !important; box-shadow: 0 0 8px var(--abyss-glow-mint, rgba(122,240,200,0.5)) !important; }';
      DOC.head.appendChild(s);
    } catch (e) {}
  }

  function ensureAriaLive() {
    if (a11yEl && a11yEl.parentNode) return a11yEl;
    if (!DOC || !DOC.body) return null;
    a11yEl = DOC.getElementById('clA11yLive');
    if (!a11yEl) {
      a11yEl = DOC.createElement('div');
      a11yEl.id = 'clA11yLive';
      a11yEl.setAttribute('role', 'status');
      a11yEl.setAttribute('aria-live', 'polite');
      a11yEl.setAttribute('aria-atomic', 'true');
      a11yEl.className = 'sr-only';
      a11yEl.style.cssText = 'position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;';
      DOC.body.appendChild(a11yEl);
    }
    return a11yEl;
  }

  function announce(msg) {
    if (!msg) return;
    var live = ensureAriaLive();
    if (live) live.textContent = msg;
  }

  function isReduced() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  function register(id, options) {
    if (!id) return false;
    options = options || {};
    var def = DEFAULT_TIERS[id] || { tier: 'panel', z: 200, modal: false, title: id };

    registry[id] = {
      id: id,
      title: options.title || def.title || id,
      el: options.el || (DOC ? (DOC.getElementById(id) || DOC.querySelector('.' + id)) : null),
      tier: options.tier || def.tier,
      z: options.z || def.z,
      modal: (options.modal !== undefined) ? !!options.modal : def.modal,
      isOpen: !!options.isOpen,
      previousFocused: null,
      onOpen: options.onOpen || null,
      onClose: options.onClose || null,
      onKey: options.onKey || null
    };

    applyZIndex(registry[id]);
    return true;
  }

  function applyZIndex(item) {
    if (!item || !item.el) return;
    try {
      if (item.tier === 'modal') item.el.style.zIndex = 'var(--z-modal, 500)';
      else if (item.tier === 'dock') item.el.style.zIndex = 'var(--z-dock, 400)';
      else if (item.tier === 'panel') item.el.style.zIndex = 'var(--z-panel, 200)';
      else item.el.style.zIndex = String(item.z || 200);
    } catch (e) {}
  }

  function open(id, payload) {
    var p = registry[id];
    if (!p) {
      register(id, {});
      p = registry[id];
    }
    if (!p) return false;

    p.isOpen = true;
    currentActive = id;

    if (DOC && DOC.activeElement) {
      p.previousFocused = DOC.activeElement;
    }

    var idx = panelStack.indexOf(id);
    if (idx >= 0) panelStack.splice(idx, 1);
    panelStack.push(id);

    if (p.el) {
      p.el.classList.add('is-open');
      p.el.classList.add('on');
      p.el.removeAttribute('hidden');
      p.el.setAttribute('aria-expanded', 'true');
    }

    applyLayoutRules();

    var label = p.title || p.id;
    announce(label + ' 面板已展开');

    if (id === 'library') {
      var searchInput = DOC.getElementById('libSearch');
      if (searchInput && typeof searchInput.focus === 'function') {
        setTimeout(function () { searchInput.focus(); }, 20);
      }
    } else if (p.el) {
      setTimeout(function () {
        var focusable = p.el.querySelector('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (focusable && typeof focusable.focus === 'function') {
          focusable.focus();
        } else if (typeof p.el.focus === 'function') {
          if (!p.el.hasAttribute('tabindex')) p.el.setAttribute('tabindex', '-1');
          p.el.focus();
        }
      }, 50);
    }

    if (typeof p.onOpen === 'function') {
      try { p.onOpen(payload); } catch (e) {}
    }

    emit('open', { id: id, payload: payload });
    return true;
  }

  function close(id) {
    var p = registry[id];
    if (!p || !p.isOpen) {
      var sIdx = panelStack.indexOf(id);
      if (sIdx >= 0) panelStack.splice(sIdx, 1);
      return false;
    }

    p.isOpen = false;

    var stackIdx = panelStack.indexOf(id);
    if (stackIdx >= 0) panelStack.splice(stackIdx, 1);

    currentActive = panelStack.length ? panelStack[panelStack.length - 1] : null;

    if (p.el) {
      p.el.classList.remove('is-open');
      p.el.classList.remove('on');
      p.el.setAttribute('aria-expanded', 'false');
    }

    if (id === 'evidence') {
      var evHost = DOC.getElementById('rdEvHost');
      if (evHost) evHost.innerHTML = '';
    } else if (id === 'dock') {
      var dockEl = DOC.getElementById('dock');
      if (dockEl) dockEl.classList.remove('on');
    } else if (id === 'library') {
      var libEl = DOC.getElementById('library');
      if (libEl) libEl.classList.remove('on');
    }

    applyLayoutRules();

    var label = p.title || p.id;
    announce(label + ' 面板已关闭');

    if (p.previousFocused && typeof p.previousFocused.focus === 'function') {
      try { p.previousFocused.focus(); } catch (err) {}
      p.previousFocused = null;
    }

    if (typeof p.onClose === 'function') {
      try { p.onClose(); } catch (e) {}
    }

    emit('close', { id: id });
    return true;
  }

  function toggle(id, payload) {
    var p = registry[id];
    if (p && p.isOpen) return close(id);
    return open(id, payload);
  }

  function handleEscape() {
    if (!panelStack.length) return false;
    var topId = panelStack[panelStack.length - 1];
    close(topId);
    return true;
  }

  function shouldAbsorbKey(e) {
    var q = (g.location && g.location.search) || '';
    if (q.indexOf('legacy-keys=1') >= 0) return false;

    if (!currentActive) return false;
    var p = registry[currentActive];
    if (!p || !p.isOpen) return false;

    if (p.modal || p.id === 'dock') return true;

    if (typeof p.onKey === 'function') {
      try { return !!p.onKey(e); } catch (err) { return false; }
    }
    return false;
  }

  function applyLayoutRules() {
    if (!DOC || !DOC.body) return;
    var dockOpen = registry.dock && registry.dock.isOpen;
    var plotText = (registry.plotTextPanel && registry.plotTextPanel.el) || DOC.getElementById('plotTextPanel') || DOC.querySelector('.plot-text-panel');

    if (plotText) {
      if (dockOpen) {
        plotText.setAttribute('data-dock-open', '1');
        plotText.classList.add('is-narrowed');
      } else {
        plotText.removeAttribute('data-dock-open');
        plotText.classList.remove('is-narrowed');
      }
    }

    var ops = DOC.getElementById('ops');
    var vb = DOC.getElementById('viewbar');
    if (dockOpen) {
      if (ops) ops.classList.add('docked');
      if (vb) vb.classList.add('docked');
      DOC.body.classList.add('focus');
    } else {
      if (ops) ops.classList.remove('docked');
      if (vb) vb.classList.remove('docked');
      DOC.body.classList.remove('focus');
    }

    var hasModal = false;
    for (var i = 0; i < panelStack.length; i++) {
      var item = registry[panelStack[i]];
      if (item && item.modal && item.isOpen) {
        hasModal = true;
        break;
      }
    }
    if (hasModal) DOC.body.setAttribute('data-modal-active', '1');
    else DOC.body.removeAttribute('data-modal-active');
  }

  var listeners = {};
  function on(evt, fn) {
    if (!listeners[evt]) listeners[evt] = [];
    listeners[evt].push(fn);
  }
  function off(evt, fn) {
    if (!listeners[evt]) return;
    listeners[evt] = listeners[evt].filter(function (f) { return f !== fn; });
  }
  function emit(evt, data) {
    var arr = listeners[evt] || [];
    for (var i = 0; i < arr.length; i++) {
      try { arr[i](data); } catch (e) {}
    }
  }

  function isOpen(id) {
    var p = registry[id];
    return !!(p && p.isOpen);
  }

  function onChange(fn) {
    if (typeof fn !== 'function') return function () {};
    var hOpen = function (d) { fn({ id: d.id, open: true, payload: d.payload }); };
    var hClose = function (d) { fn({ id: d.id, open: false }); };
    on('open', hOpen);
    on('close', hClose);
    return function () { off('open', hOpen); off('close', hClose); };
  }

  function stats() {
    var openPanels = [];
    for (var k in registry) {
      if (registry[k].isOpen) openPanels.push(k);
    }
    return {
      name: NAME,
      version: VERSION,
      active: currentActive,
      stack: panelStack.slice(),
      openCount: openPanels.length,
      openPanels: openPanels,
      registeredCount: Object.keys(registry).length,
      a11yLive: !!a11yEl,
      focusTrapped: !!(currentActive && registry[currentActive] && registry[currentActive].modal)
    };
  }

  function handleTabTrap(e) {
    if (g.CLInformationArchitecture && g.CLInformationArchitecture.isOpen()) return false;
    if (e.key !== 'Tab' || !currentActive) return false;
    var p = registry[currentActive];
    if (!p || !p.isOpen || !p.modal || !p.el) return false;

    var all = p.el.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary:not([disabled]), [tabindex]:not([tabindex="-1"])');
    var focusables = all ? Array.prototype.filter.call(all, function (n) { return n.getClientRects().length > 0; }) : [];
    if (!focusables.length) { e.preventDefault(); return true; }

    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    var ae = DOC.activeElement;

    if (!p.el.contains(ae)) { e.preventDefault(); try { first.focus(); } catch (err) {} return true; }
    if (e.shiftKey ? ae === first : ae === last) {
      e.preventDefault();
      try { (e.shiftKey ? last : first).focus(); } catch (err) {}
      return true;
    }
    return false;
  }

  function hookApp() {
    if (typeof g === 'undefined') return;
    var cl = g.__cl;
    if (cl) {
      if (typeof cl.openLib === 'function' && !cl.openLib.__hooked) {
        var origOpenLib = cl.openLib;
        cl.openLib = function () {
          var res = origOpenLib.apply(this, arguments);
          open('library');
          return res;
        };
        cl.openLib.__hooked = true;
      }
      if (typeof cl.closeLib === 'function' && !cl.closeLib.__hooked) {
        var origCloseLib = cl.closeLib;
        cl.closeLib = function () {
          var res = origCloseLib.apply(this, arguments);
          close('library');
          return res;
        };
        cl.closeLib.__hooked = true;
      }
      if (typeof cl.select === 'function' && !cl.select.__hooked) {
        var origSelect = cl.select;
        cl.select = function (name) {
          var res = origSelect.apply(this, arguments);
          if (name) open('dock');
          else close('dock');
          return res;
        };
        cl.select.__hooked = true;
      }
      if (typeof cl.openAxisEvidence === 'function' && !cl.openAxisEvidence.__hooked) {
        var origOpenAxis = cl.openAxisEvidence;
        cl.openAxisEvidence = function (k) {
          var res = origOpenAxis.apply(this, arguments);
          if (!res && cl.showAxisRanking && cl.state && cl.state().sel) {
            try { cl.showAxisRanking(k); res = true; } catch (e) {}
          }
          if (res) open('evidence');
          return res;
        };
        cl.openAxisEvidence.__hooked = true;
      }
    }
  }

  function syncDomState() {
    if (!DOC) return;
    hookApp();
    var lib = DOC.getElementById('library') || DOC.querySelector('.cl-library');
    if (lib) {
      var libOpen = lib.classList.contains('on') || lib.classList.contains('is-open');
      if (libOpen && (!registry.library || !registry.library.isOpen)) open('library');
      else if (!libOpen && registry.library && registry.library.isOpen) close('library');
    }

    var dock = DOC.getElementById('dock') || DOC.querySelector('.cl-dock');
    if (dock) {
      var dockOpen = dock.classList.contains('on') || dock.classList.contains('is-open');
      if (dockOpen && (!registry.dock || !registry.dock.isOpen)) open('dock');
      else if (!dockOpen && registry.dock && registry.dock.isOpen) close('dock');
    }

    var evHost = DOC.getElementById('rdEvHost');
    if (evHost) {
      var evOpen = !!(evHost.children && evHost.children.length > 0 && evHost.innerHTML.trim());
      if (evOpen && (!registry.evidence || !registry.evidence.isOpen)) open('evidence');
      else if (!evOpen && registry.evidence && registry.evidence.isOpen) close('evidence');
    }
  }

  function autoDiscover() {
    if (!DOC) return;
    injectFocusRing();
    ensureAriaLive();

    var candidates = [
      { id: 'dock', sel: '.cl-dock, #dock, #clDock', modal: false, tier: 'dock', title: '角色资料坞' },
      { id: 'library', sel: '#library, #clLibrary, .cl-library', modal: true, tier: 'modal', title: '作品库' },
      { id: 'keys', sel: '#clKeys, .cl-keys', modal: true, tier: 'modal', title: '快捷键速查' },
      { id: 'evidence', sel: '#rdEvHost, .rd-ev, .rd-evidence-card', modal: false, tier: 'panel', title: '雷达证据卡' },
      { id: 'plotTextPanel', sel: '#clPlotText, .plot-text-panel, .cl-plot-text', modal: false, tier: 'panel', title: '剧情文本' },
      { id: 'ops', sel: '#ops, #clOps, .cl-ops', modal: false, tier: 'panel', title: '操作面板' },
      { id: 'tray', sel: '#tray, #clTray, .cl-tray', modal: false, tier: 'panel', title: '快捷托盘' },
      { id: 'modal', sel: '.cl-modal', modal: true, tier: 'modal', title: '模态对话框' }
    ];
    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      var el = DOC.querySelector(c.sel);
      if (el) {
        register(c.id, { el: el, modal: c.modal, tier: c.tier, title: c.title });
      }
    }

    DOC.addEventListener('keydown', handleTabTrap, true);

    if (typeof MutationObserver !== 'undefined' && DOC.body) {
      try {
        var obs = new MutationObserver(function (recs) {
          for (var i = 0; i < recs.length; i++) {
            var t = recs[i].target;
            if (t && t.nodeType === 1 && (t.id === 'library' || t.id === 'dock' || t.id === 'rdEvHost' || (recs[i].type === 'childList' && t.closest && t.closest('#rdEvHost')))) { syncDomState(); return; }
          }
        });
        obs.observe(DOC.body, { attributes: true, attributeFilter: ['class'], childList: true, subtree: true });
      } catch (e) {}
    }

    syncDomState();
    hookApp();
    if (typeof setInterval !== 'undefined') {
      var hookCount = 0;
      var hookTimer = setInterval(function () {
        hookApp();
        syncDomState();
        hookCount++;
        if (hookCount > 20) clearInterval(hookTimer);
      }, 200);
    }
  }

  if (DOC && DOC.readyState === 'loading') {
    DOC.addEventListener('DOMContentLoaded', autoDiscover);
  } else {
    autoDiscover();
  }

  var API = {
    name: NAME,
    version: VERSION,
    register: register,
    open: open,
    close: close,
    toggle: toggle,
    /* v5·R1：旁路清剿的两个前置出口 —— 只读查询 + 状态订阅（供 app.js / keys.js 改读总线） */
    isOpen: isOpen,
    onChange: onChange,
    announce: announce,
    active: function () { return currentActive; },
    handleEscape: handleEscape,
    shouldAbsorbKey: shouldAbsorbKey,
    /* v55：window 捕获层（keys.js）代调的焦点陷阱——document 捕获那份监听在 keys.js 的
     * stopPropagation 下到不了，Tab 环绕语义唯一可靠入口在这里 */
    tabTrap: handleTabTrap,
    on: on,
    off: off,
    emit: emit,
    getStack: function () { return panelStack.slice(); },
    stats: stats
  };

  g.CLPanelManager = API;
  if (!g.__cl) g.__cl = {};
  g.__cl.panelManager = API;

})(typeof window !== 'undefined' ? window : this);
