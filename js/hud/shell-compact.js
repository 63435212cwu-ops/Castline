/* Castline · shell-compact.js — 窄屏剧情态壳（R3-A · v70）
 * @role overlay-fix · @owns js/hud/shell-compact.js · @contract v70
 *
 * 背景（outputs/v70/review/disc-390x844.png · disc-820x1180.png 实测，见
 * docs/atlas/REVIEW-2026-09-20.md §四 4.1、§五「仍未解决」第 1 条）：390/820
 * 两个窄视口下，剧情态/右坞态的圆盘环体沿用桌面半径参数，直接压穿顶部
 * #ops 的 6～8 个大按钮与 #brand 品牌卡文字，属 R7（CONTRACT §5）一票否决。
 *
 * 本文件只做两件事，DOM 足迹严格限定在任务书范围内：
 *   1. 只增删 <body> 的 class（cl-shell-compact / cl-shell-menu-open /
 *      cl-shell-index-open），真正的显隐/布局全部交给 css/shell-chrome.css
 *      的类选择器去接管——不摸 #ops / #index / #brand 原有子树一根节点。
 *   2. 创建两枚按钮（#shellMenuBtn「≡ 菜单」· #shellIndexBtn「角色 ▾」），
 *      插进 #ops 的父容器（<body>）末尾，不改 index.html。
 *
 * 触发条件（R5-K 修订，2026-09-21）：
 *   · viewport ≤600px：全态纳入，含星座态——FINAL4 §3.1 实测 390 星座态
 *     8 枚工具栏按钮平铺占顶部约 1/6（星座 390 得 33/50），跟剧情态/右坞态
 *     是同一个「窄屏容不下一整排按钮」的问题，没有理由只修一半。
 *   · 600<viewport≤900：维持 R3-A 原判——仍只在剧情态（body.cl-plot-on /
 *     cl-orbit-on）或右坞态（body.focus）收起，星座态在这个中间档位本就
 *     不像 390 那么挤（FINAL4 未把 820 星座列为阻断项），先不动，避免过度
 *     收纳引入新的首屏可读性回归。
 * css 侧（css/shell-chrome.css，宿主文件）的选择器一律挂在 body.cl-shell-
 * compact 之下、不区分是哪个态触发的，本文件只需要按上面的口径正确地加/
 * 摘这个 class，css 那边不用跟着改。
 *
 * 没有 mount(host,...) 契约可循（本模块跟 js/hud/plot-hud.js 一样是自举式
 * HUD 脚本，加载即生效），但仍然提供 dispose() 满足「重复挂载先 dispose」
 * 的精神：dispose 会摘掉监听、按钮与 body class，之后可以重新 init。
 */
(function (g) {
  'use strict';

  var DOC = (typeof document !== 'undefined') ? document : null;
  if (!DOC) return;

  var NS = 'CLShellCompact';
  if (g[NS] && typeof g[NS].dispose === 'function') return; // 幂等：已挂载则不重复挂

  var BP = 900; // 断点，与任务书「≤900px」一致
  var BP_FULL = 600; // R5-K：≤600px 全态纳入（含星座态）的断点

  var menuBtn = null, indexBtn = null;
  var menuOpen = false, indexOpen = false;
  var lastCompact = false;
  var mo = null;
  var alive = false;

  function viewportWidth() {
    try { return g.innerWidth; } catch (e) { return Infinity; }
  }
  function isNarrow() { return viewportWidth() <= BP; }
  function isPlotDockState() {
    var b = DOC.body;
    return !!(b && (b.classList.contains('cl-plot-on') || b.classList.contains('cl-orbit-on') || b.classList.contains('focus')));
  }
  /* R5-K：w≤600 全态纳入（含星座态，即既不是 plot 也不是 orbit/focus 的默认
   * 群像视图）；600<w≤900 仍只在剧情态/右坞态收起——两档口径见文件头注。 */
  function wantCompact() {
    var w = viewportWidth();
    /* 主控 R5 收官裁定：≤900 全态紧凑（820 星座态 8 枚按钮平铺两列四行占屏上半，评审图 constellation-820 判为压盘） */
    if (w <= BP) return true;
    return false;
  }

  function ensureButtons() {
    var ops = DOC.getElementById('ops');
    var host = (ops && ops.parentNode) || DOC.body;
    if (!menuBtn) {
      menuBtn = DOC.createElement('button');
      menuBtn.type = 'button';
      menuBtn.id = 'shellMenuBtn';
      menuBtn.className = 'btn shell-compact-btn';
      menuBtn.setAttribute('aria-haspopup', 'true');
      menuBtn.setAttribute('aria-expanded', 'false');
      menuBtn.setAttribute('aria-controls', 'ops');
      menuBtn.title = '展开操作栏';
      menuBtn.textContent = '≡ 菜单'; /* ≡ 菜单 */
      menuBtn.addEventListener('click', onMenuClick);
      host.appendChild(menuBtn);
    }
    if (!indexBtn) {
      indexBtn = DOC.createElement('button');
      indexBtn.type = 'button';
      indexBtn.id = 'shellIndexBtn';
      indexBtn.className = 'btn shell-compact-btn';
      indexBtn.setAttribute('aria-haspopup', 'true');
      indexBtn.setAttribute('aria-expanded', 'false');
      indexBtn.setAttribute('aria-controls', 'index');
      indexBtn.title = '展开角色索引';
      indexBtn.textContent = '角色 ▾'; /* 角色 ▾ */
      indexBtn.addEventListener('click', onIndexClick);
      host.appendChild(indexBtn);
    }
  }

  function onMenuClick(e) { e.stopPropagation(); toggleMenu(); }
  function onIndexClick(e) { e.stopPropagation(); toggleIndex(); }

  function focusFirst(hostId) {
    setTimeout(function () {
      var host = DOC.getElementById(hostId);
      var first = host && host.querySelector('button:not([disabled]), a[href], input:not([disabled])');
      if (first && typeof first.focus === 'function') { try { first.focus(); } catch (e2) {} }
    }, 30);
  }

  function toggleMenu(force) {
    var next = (force !== undefined) ? !!force : !menuOpen;
    if (next === menuOpen) return;
    menuOpen = next;
    DOC.body.classList.toggle('cl-shell-menu-open', menuOpen);
    if (menuBtn) menuBtn.setAttribute('aria-expanded', menuOpen ? 'true' : 'false');
    if (menuOpen) {
      if (indexOpen) toggleIndex(false);
      focusFirst('ops');
    } else if (menuBtn) {
      try { menuBtn.focus(); } catch (e) {}
    }
  }

  function toggleIndex(force) {
    var next = (force !== undefined) ? !!force : !indexOpen;
    if (next === indexOpen) return;
    indexOpen = next;
    DOC.body.classList.toggle('cl-shell-index-open', indexOpen);
    if (indexBtn) indexBtn.setAttribute('aria-expanded', indexOpen ? 'true' : 'false');
    if (indexOpen) {
      if (menuOpen) toggleMenu(false);
      focusFirst('index');
    } else if (indexBtn) {
      try { indexBtn.focus(); } catch (e) {}
    }
  }

  function closeAll() {
    if (menuOpen) toggleMenu(false);
    if (indexOpen) toggleIndex(false);
  }

  function onDocClick(e) {
    if (!menuOpen && !indexOpen) return;
    var t = e.target;
    var ops = DOC.getElementById('ops');
    var idx = DOC.getElementById('index');
    if (menuOpen && ((ops && (ops === t || ops.contains(t))) || t === menuBtn)) return;
    if (indexOpen && ((idx && (idx === t || idx.contains(t))) || t === indexBtn)) return;
    closeAll();
  }

  function onKeydown(e) {
    if (window.CLInformationArchitecture && window.CLInformationArchitecture.isOpen()) return;
    if (e.key === 'Escape' && (menuOpen || indexOpen)) {
      closeAll();
      e.stopPropagation();
    }
  }

  function applyState() {
    var compact = wantCompact();
    if (compact) ensureButtons();
    if (compact === lastCompact) return;
    lastCompact = compact;
    DOC.body.classList.toggle('cl-shell-compact', compact);
    if (!compact) closeAll();
    /* R5-B：紧凑壳改变了世界层的横向安全区口径。让宿主的 resize
     * 同步读取新 class；不直接触碰 scene/camera，避免形成第二个布局真相源。 */
    try { g.dispatchEvent(new g.Event('resize')); } catch (e) {}
  }

  function init() {
    if (alive) return;
    alive = true;
    applyState();
    g.addEventListener('resize', applyState, { passive: true });
    g.addEventListener('orientationchange', applyState, { passive: true });
    DOC.addEventListener('click', onDocClick, true);
    DOC.addEventListener('keydown', onKeydown, true);
    if (g.MutationObserver && DOC.body) {
      mo = new g.MutationObserver(applyState);
      mo.observe(DOC.body, { attributes: true, attributeFilter: ['class'] });
    }
  }

  function dispose() {
    if (!alive) return;
    alive = false;
    g.removeEventListener('resize', applyState);
    g.removeEventListener('orientationchange', applyState);
    DOC.removeEventListener('click', onDocClick, true);
    DOC.removeEventListener('keydown', onKeydown, true);
    if (mo) { mo.disconnect(); mo = null; }
    if (menuBtn && menuBtn.parentNode) menuBtn.parentNode.removeChild(menuBtn);
    if (indexBtn && indexBtn.parentNode) indexBtn.parentNode.removeChild(indexBtn);
    menuBtn = null; indexBtn = null;
    DOC.body.classList.remove('cl-shell-compact', 'cl-shell-menu-open', 'cl-shell-index-open');
    lastCompact = false; menuOpen = false; indexOpen = false;
  }

  if (DOC.readyState === 'loading') {
    DOC.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  g[NS] = {
    VERSION: '2',
    isCompact: function () { return lastCompact; },
    isMenuOpen: function () { return menuOpen; },
    isIndexOpen: function () { return indexOpen; },
    toggleMenu: toggleMenu,
    toggleIndex: toggleIndex,
    closeAll: closeAll,
    refresh: applyState, /* 供测试/联动手动触发一次重判 */
    dispose: dispose
  };
})(typeof window !== 'undefined' ? window : this);
