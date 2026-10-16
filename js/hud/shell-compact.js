(function (g) {
  'use strict';

  var DOC = (typeof document !== 'undefined') ? document : null;
  if (!DOC) return;

  var NS = 'CLShellCompact';
  if (g[NS] && typeof g[NS].dispose === 'function') return;

  var BP = 900;
  var BP_FULL = 600;

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
  function wantCompact() {
    var w = viewportWidth();
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
      menuBtn.textContent = '≡ 菜单';
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
      indexBtn.textContent = '角色 ▾';
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
    refresh: applyState,
    dispose: dispose
  };
})(typeof window !== 'undefined' ? window : this);
