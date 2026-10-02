/* @role component · @owns js/hud/panel-manager.js · @contract v54 */
/**
 * panel-manager.js - D3: 面板管理器（z 序 · 焦点 · 快捷键吸收）
 *
 * 核心法则：
 * 1. 消费 A5 z-index 音阶：--z-panel (200), --z-dock (400), --z-modal (500), --z-ritual (600)；
 * 2. 焦点模型：同一时刻至多一个「活跃/活面板」（Active Panel），活面板优先吸收键盘事件；
 * 3. 互斥与共存规整：dock 展开时联动 plotTextPanel 收窄，modal 激活时冻结底层面板；
 * 4. Esc 逐层退栈（LIFO 栈）：优先关闭最顶层活跃浮层，退空后平滑回退至全局原生热键；
 * 5. 动效对齐：开闭过渡统一走 --abyss-dur-shift 节奏。
 */
(function (g) {
  'use strict';

  var NAME = 'panel-manager';
  var VERSION = '54';

  var DOC = (typeof document !== 'undefined') ? document : null;

  /* 面板注册表 */
  var registry = {};
  /* 模态/活跃面板退栈（LIFO） */
  var panelStack = [];
  /* 当前获取焦点的活面板 */
  var currentActive = null;
  var a11yEl = null;

  /* 预设已知的面板及其默认 z-index 音阶与层级 */
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
      s.textContent = ':focus-visible { outline: 2px solid var(--abyss-border-mint, #7af0c8) !important; outline-offset: 2px !important; box-shadow: 0 0 8px var(--abyss-glow-mint, rgba(122,240,200,0.5)) !important; }';
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

  /**
   * 注册面板
   * @param {string} id - 面板唯一标识 (e.g. 'dock', 'library', 'plotTextPanel')
   * @param {Object} options - 面板配置 (el, tier, onClose, onOpen, onKey, modal, title)
   */
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

  /**
   * 打开面板并入栈
   */
  function open(id, payload) {
    var p = registry[id];
    if (!p) {
      /* 动态兜底注册 */
      register(id, {});
      p = registry[id];
    }
    if (!p) return false;

    p.isOpen = true;
    currentActive = id;

    /* 记录打开前的聚焦元素（用于关闭时还焦） */
    if (DOC && DOC.activeElement) {
      p.previousFocused = DOC.activeElement;
    }

    /* 压入退栈（保持唯一且置顶） */
    var idx = panelStack.indexOf(id);
    if (idx >= 0) panelStack.splice(idx, 1);
    panelStack.push(id);

    /* 同步 DOM 状态与过渡 class */
    if (p.el) {
      p.el.classList.add('is-open');
      p.el.classList.add('on');
      p.el.removeAttribute('hidden');
      p.el.setAttribute('aria-expanded', 'true');
    }

    /* 互斥与协同联动规则 */
    applyLayoutRules();

    /* 播报面板开启状态 */
    var label = p.title || p.id;
    announce(label + ' 面板已展开');

    /* 自动落焦：将焦点转移至面板内首个可交互控件或面板本体 */
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

  /**
   * 关闭面板并出栈
   */
  function close(id) {
    var p = registry[id];
    if (!p || !p.isOpen) {
      /* 即使未显式注册，也尝试清理栈 */
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

    /* 联动物理清理（如证据卡清空、右坞收起） */
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

    /* 播报面板关闭状态 */
    var label = p.title || p.id;
    announce(label + ' 面板已关闭');

    /* 自动还焦：将焦点归还给触发此面板的前一个元素 */
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

  /**
   * 切换面板开闭
   */
  function toggle(id, payload) {
    var p = registry[id];
    if (p && p.isOpen) return close(id);
    return open(id, payload);
  }

  /**
   * Esc 逐层退栈处理
   * @returns {boolean} - 是否成功拦截并消费了 Esc
   */
  function handleEscape() {
    if (!panelStack.length) return false;
    var topId = panelStack[panelStack.length - 1];
    close(topId);
    return true;
  }

  /**
   * 键盘事件吸收与焦点判定
   */
  function shouldAbsorbKey(e) {
    var q = (g.location && g.location.search) || '';
    if (q.indexOf('legacy-keys=1') >= 0) return false;

    if (!currentActive) return false;
    var p = registry[currentActive];
    if (!p || !p.isOpen) return false;

    /* 模态弹窗或活跃资料坞打开期间，拦截全局热键不外漏给三维画布/全图 */
    if (p.modal || p.id === 'dock') return true;

    /* 若活跃面板注册了专属按键处理器 */
    if (typeof p.onKey === 'function') {
      try { return !!p.onKey(e); } catch (err) { return false; }
    }
    return false;
  }

  /**
   * 布局互斥与规整规则表
   */
  function applyLayoutRules() {
    if (!DOC || !DOC.body) return;
    var dockOpen = registry.dock && registry.dock.isOpen;
    var plotText = (registry.plotTextPanel && registry.plotTextPanel.el) || DOC.getElementById('plotTextPanel') || DOC.querySelector('.plot-text-panel');

    /* 规则 1: dock 展开时，plotTextPanel 标记收窄或避让，杜绝视口遮挡 */
    if (plotText) {
      if (dockOpen) {
        plotText.setAttribute('data-dock-open', '1');
        plotText.classList.add('is-narrowed');
      } else {
        plotText.removeAttribute('data-dock-open');
        plotText.classList.remove('is-narrowed');
      }
    }

    /* 规则 2: dock 展开时，ops 与 viewbar 同步收窄 (docked)，body 标注 focus */
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

    /* 规则 3: 有任何模态面板处于栈顶时，body 标记 data-modal-active="1" 冻结底层视口 pointer-events */
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

  /* 轻量级事件总线 */
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

  /**
   * 只读状态查询：某面板当前是否打开（v5·R1 新增）。
   *
   * 为什么要它：R1「旁路清剿」的结构性障碍就在这里 —— app.js / keys.js 此前**没有任何
   * 官方途径**查询面板态，只能退而 `classList.contains('on')` 直查 DOM 自己猜。只要官方
   * 不开这个查询口，旁路就不可能拆干净（拆了也没法判断该不该开）。本函数是唯一真值出口，
   * 读的就是 `registry[id].isOpen` 这一份状态，**不引入第二份真相**。
   *
   * 语义：未注册的 id 返回 false（不抛异常 —— 抛了调用方只能再加 try/catch，反而把
   * 「id 拼错」这类真 bug 藏起来）。
   */
  function isOpen(id) {
    var p = registry[id];
    return !!(p && p.isOpen);
  }

  /**
   * 状态变更订阅（v5·R1 新增）：把 open/close 两事件合成一条「开关态变化」回调。
   *
   * 复用**既有** emit 总线（见上方 on/off/emit），**不新造第二套订阅机制**。
   * 回调收到 `{ id, open, payload }`；返回值是退订函数。
   *
   * 语义边界（照实写明，避免调用方误判）：
   *  - `close()` 仅在真实 开→关 时 emit（未开则 :189 提前 return）→ `onChange` 必为真变化；
   *  - `open()` **每次都 emit**（不判「已开」）→ 对已开面板再调 open，`onChange` 会**重复**
   *    收到 `open:true`。需要「仅在变化时行动」的调用方请自行比对 `isOpen(id)`。
   */
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

  /**
   * 模态 Tab 焦点陷阱（循环焦点），防止模态开启时焦点跑到底层星图
   */
  function handleTabTrap(e) {
    if (g.CLInformationArchitecture && g.CLInformationArchitecture.isOpen()) return;
    if (e.key !== 'Tab' || !currentActive) return;
    var p = registry[currentActive];
    if (!p || !p.isOpen || !p.modal || !p.el) return;

    var focusables = p.el.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
    if (!focusables || !focusables.length) return;

    var first = focusables[0];
    var last = focusables[focusables.length - 1];

    if (e.shiftKey) {
      if (DOC.activeElement === first || !p.el.contains(DOC.activeElement)) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (DOC.activeElement === last || !p.el.contains(DOC.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    }
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
    // 1. Library
    var lib = DOC.getElementById('library') || DOC.querySelector('.cl-library');
    if (lib) {
      var libOpen = lib.classList.contains('on') || lib.classList.contains('is-open');
      if (libOpen && (!registry.library || !registry.library.isOpen)) open('library');
      else if (!libOpen && registry.library && registry.library.isOpen) close('library');
    }

    // 2. Dock
    var dock = DOC.getElementById('dock') || DOC.querySelector('.cl-dock');
    if (dock) {
      var dockOpen = dock.classList.contains('on') || dock.classList.contains('is-open');
      if (dockOpen && (!registry.dock || !registry.dock.isOpen)) open('dock');
      else if (!dockOpen && registry.dock && registry.dock.isOpen) close('dock');
    }

    // 3. Evidence
    var evHost = DOC.getElementById('rdEvHost');
    if (evHost) {
      var evOpen = !!(evHost.children && evHost.children.length > 0 && evHost.innerHTML.trim());
      if (evOpen && (!registry.evidence || !registry.evidence.isOpen)) open('evidence');
      else if (!evOpen && registry.evidence && registry.evidence.isOpen) close('evidence');
    }
  }

  /* 初始自探测 */
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
        /* 只在库 / 资料坞 / 证据卡自己变了才对账：旧版 body 子树里任何 class 变动都整套重对（星空壳下标签逐帧换 class） */
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
