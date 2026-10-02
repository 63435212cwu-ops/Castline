/**
 * @role component
 * @owns js/sky/sky-chrome.js
 * CLSkyChrome — 星空壳外围：
 *   ① 无作品首页（body.noview、#skyHud 未挂载）：深空 + 缓慢星场、CASTLINE 字标、「打开作品」、最近作品星列、拖入导入；
 *   ② 工具星图菜单：顶栏 #skyTools 的下拉（竖排 · 字形 + 名称 + 一行说明 · 分组），每项复用原按钮的点击；
 *   ③ 星座态底部小注：关系线型样本 + 名 + 数，与提示句合成 #skyLegend 一行（左下 .cl-dom-legend 在星空壳里退场）；
 *   ④ 旧外围（CAST INDEX / 方角按钮排 / 右缘码列 / 方位盘 / 观测角框 / 色温分级 …）在星空壳下隐藏（css/sky-chrome.css）。
 * 纪律：只调用现有公开函数（CLApp.showLoader / toast / busy …）或原按钮 .click()；不重写导入与分析流程；
 * 只读 GET /api/history（与旧壳「记忆」列表同源、同序）；不写 data/、不调模型；不在 JS 里写 style 字面量。
 */
(function (g) {
  'use strict';
  var d = g.document, VERSION = '1';
  if (!d || !d.body) { g.CLSkyChrome = { VERSION: VERSION, enabled: function () { return false; } }; return; }

  /* 与 sky-shell.js 的 ENABLED 同一口径：?shell=atlas → 旧壳；?shell=sky 或带 sky 参数 → 星空壳；否则除 probe=1 外一律星空壳 */
  var ENABLED = (function () {
    if (g.CLSky && typeof g.CLSky.enabled === 'function') return !!g.CLSky.enabled();
    try { var q = new URLSearchParams(g.location.search); if (q.get('shell') === 'atlas') return false; if (q.get('shell') === 'sky' || q.get('sky')) return true; return q.get('probe') !== '1'; } catch (e) { return true; }
  })();
  if (!ENABLED) { g.CLSkyChrome = { VERSION: VERSION, enabled: function () { return false; } }; return; }

  var body = d.body, $ = function (id) { return d.getElementById(id); };
  var app = function () { return g.CLApp || null; };
  body.classList.add('sky-chrome');

  var esc = g.CLSkyUtil.esc, reduced = g.CLSkyUtil.mediaReduced;
  function hasGraph() { var A = app(); try { return !!(A && A.graph && A.graph()); } catch (e) { return false; } }
  function toast(t, ms) { var A = app(); if (A && A.toast) A.toast(t, ms); }

  /* ── 细线字形（24 格，stroke = currentColor） ─────────────────────────── */
  var GL = {
    lib: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h3.4v15H5zM10.4 4.5h3.4v15h-3.4z"/><path d="m15.6 5.4 3.3-.8 2.6 14.4-3.3.8z"/></svg>',
    swap: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13.5v5h16v-5"/><path d="M12 4v10M8.2 10.4 12 14l3.8-3.6"/></svg>',
    re: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.8 12.6A6.9 6.9 0 1 1 16.9 7"/><path d="M17.6 3.6v4h-4"/><circle cx="12" cy="12" r="1.2" class="gl-fill"/></svg>',
    api: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7.6" cy="12" r="3.3"/><path d="M10.9 12H20.4M17.4 12v3M20.4 12v2.2"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.5h9M4 11h6M4 15.5h4.5"/><circle cx="15.6" cy="14.2" r="3.6"/><path d="m18.2 16.8 2.6 2.6"/></svg>',
    distill: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.3 4h5.4M10.4 4v5.1L5.9 17.4a1.8 1.8 0 0 0 1.6 2.6h9a1.8 1.8 0 0 0 1.6-2.6l-4.5-8.3V4"/><path d="M7.9 15.4h8.2"/></svg>',
    full: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
    open: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="9.5" ry="5.6"/><path d="M12 3.4 13.2 10.8 20.6 12 13.2 13.2 12 20.6 10.8 13.2 3.4 12 10.8 10.8z" class="gl-fill"/></svg>',
    tray: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13.5v5h16v-5"/><path d="M12 4v10M8.2 10.4 12 14l3.8-3.6"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 5.5 8 12l6.5 6.5"/></svg>'
  };
  /* 首页印记：一张前倾的平面天球图——外圈时间环、内圈星域、盘心一颗星 */
  var SIGIL = '<svg viewBox="-60 -60 120 120" aria-hidden="true">' +
    '<ellipse class="sg-ring" rx="54" ry="19"/><ellipse class="sg-ring is-in" rx="36" ry="12.6"/>' +
    '<path class="sg-tick" d="M0 -19v-4M54 0h4M0 19v4M-54 0h-4"/>' +
    '<path class="sg-star" d="M0 -24 2.4 -2.4 24 0 2.4 2.4 0 24 -2.4 2.4 -24 0 -2.4 -2.4z"/><circle class="sg-core" r="2.6"/></svg>';
  var STAR = '<svg class="sh-star" viewBox="-12 -12 24 24" aria-hidden="true"><path class="sh-ray" d="M0 -11 1.25 -1.25 11 0 1.25 1.25 0 11 -1.25 1.25 -11 0 -1.25 -1.25z"/><circle class="sh-core" r="2.1"/></svg>';

  /* ================================================================ ① 无作品首页 */
  var home = null, homeMode = 'off', homeItems = [], homeTimer = 0, dragDepth = 0;
  function bootLoading() { try { var q = new URLSearchParams(g.location.search); return !!(q.get('data') || q.get('demo') === '1'); } catch (e) { return false; } }
  function buildHome() {
    if (home) return home;
    home = d.createElement('section');
    home.id = 'skyHome'; home.className = 'sky-home'; home.setAttribute('aria-label', 'Castline 首页');
    home.innerHTML =
      '<div class="sh-sky" aria-hidden="true"><i class="sh-neb"></i><i class="sh-stars s1"></i><i class="sh-stars s2"></i><i class="sh-stars s3"></i></div>' +
      '<div class="sh-center">' +
        '<div class="sh-mark">' +
          '<svg class="sh-plane" viewBox="-500 -170 1000 340" aria-hidden="true"><ellipse class="sp-ring" rx="492" ry="160"/><ellipse class="sp-ring is-time" rx="452" ry="147"/><ellipse class="sp-ring is-in" rx="330" ry="107"/></svg>' +
          '<div class="sh-sigil">' + SIGIL + '</div>' +
          '<h1 class="sh-word">CASTLINE</h1>' +
          '<div class="sh-rule" aria-hidden="true"><i></i><b></b><i></i></div>' +
          '<p class="sh-tag">把一部小说变成一张星图</p>' +
        '</div>' +
        '<p class="sh-loading" id="skyHomeLoading" role="status"><span id="skyHomeLoadingT">正在展开星图</span><span class="sh-loading-line" aria-hidden="true"></span></p>' +
        '<div class="sh-actions">' +
          '<button type="button" class="sh-btn is-primary" id="skyHomeOpen" title="打开作品库（H）">' + GL.open + '<span>打开作品</span></button>' +
          '<button type="button" class="sh-btn" id="skyHomeImport" title="打开材料托盘：拖入或选择文件">' + GL.tray + '<span>导入材料</span></button>' +
        '</div>' +
        '<p class="sh-hint">或把 txt · md · docx 拖进这片星空<span class="sh-hint-key"> · <kbd>H</kbd> 作品库</span></p>' +
        '<section class="sh-recent" id="skyHomeRecent" aria-labelledby="skyHomeRecentH" hidden>' +
          '<header class="sh-recent-h"><i aria-hidden="true"></i><span id="skyHomeRecentH">最近的星图</span><b id="skyHomeCount"></b><i aria-hidden="true"></i></header>' +
          '<ol class="sh-row" id="skyHomeRow"></ol>' +
          '<button type="button" class="sh-all" id="skyHomeAll" hidden></button>' +
        '</section>' +
        '<p class="sh-empty" id="skyHomeEmpty" hidden>还没有星图 · 导入第一部小说</p>' +
      '</div>' +
      '<div class="sh-drop" aria-hidden="true"><div class="sh-drop-ring"></div><span>松手 · 放进材料托盘</span><small>txt · md · docx · json · 可整个文件夹</small></div>';
    body.appendChild(home);
    $('skyHomeOpen').addEventListener('click', openLibrary);
    $('skyHomeAll').addEventListener('click', openLibrary);
    $('skyHomeImport').addEventListener('click', openImport);
    $('skyHomeRow').addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('[data-key]'); if (b) openWork(b.getAttribute('data-key')); });
    home.addEventListener('dragenter', onDragEnter);
    home.addEventListener('dragover', onDragOver);
    home.addEventListener('dragleave', onDragLeave);
    home.addEventListener('drop', onDrop);
    return home;
  }
  function setHomeMode(mode) {
    homeMode = mode;
    if (!home) return;
    home.dataset.mode = mode;
    var on = mode === 'home' || mode === 'loading';
    body.classList.toggle('sky-home-on', on);
    home.hidden = !on;
    $('skyHomeLoading').hidden = mode !== 'loading';
  }
  /* 进入首页：旧加载框（材料托盘）默认收起，由「导入材料」/ 拖入再打开——它是导入入口，不是首页 */
  /* 载入失败（记忆文件缺失 / ?data= 取不到 …）：旧壳把错误写进托盘的 #lcErr；首页此时在「载入中」——退回首页并把原话轻提示出来，不空等 */
  var errObs = null;
  function watchErr() {
    var E = $('lcErr'); if (!E || errObs || !g.MutationObserver) return;
    errObs = new g.MutationObserver(function () {
      var t = String(E.textContent || '').trim();
      if (t && homeMode === 'loading' && !hasGraph()) { clearTimeout(homeTimer); setHomeMode('home'); toast(t, 4200); }
    });
    errObs.observe(E, { childList: true, characterData: true, subtree: true });
  }
  function enterHome() {
    if (hasGraph()) return;
    buildHome(); buildBack(); watchErr();
    /* 载入若在本脚本执行前就已失败（错误已写进 #lcErr）：直接给首页，托盘保持打开让错误可见，并轻提示原话 */
    var E0 = $('lcErr'), early = E0 ? String(E0.textContent || '').trim() : '', loading = bootLoading() && !early;
    setHomeMode(loading ? 'loading' : 'home');
    var L = $('loader');
    if (!loading && !early && L && !L.classList.contains('off') && app() && app().showLoader) app().showLoader(false);
    if (early) toast(early, 4200);
    if (loading) { clearTimeout(homeTimer); homeTimer = setTimeout(function () { if (!hasGraph() && homeMode === 'loading') setHomeMode('home'); }, 15000); }
    loadRecent();
  }
  function leaveHome() {
    clearTimeout(homeTimer);
    if (!home || homeMode === 'off') { body.classList.remove('sky-home-on'); return; }
    body.classList.remove('sky-home-on');
    homeMode = 'off';
    home.dataset.mode = 'off';
    home.classList.add('is-leaving');
    setTimeout(function () { if (homeMode === 'off' && home) { home.hidden = true; home.classList.remove('is-leaving'); } }, reduced() ? 0 : 820);
  }

  /* 首页上打开的材料托盘（旧 #loader）：旧壳里它就是首页，没有出口；星空壳给它三个出口——右上「返回星空」、Esc、点空白。
   * 关闭走 #btnCancel 的原处理（wantProgress=false → showLoader(false)），与「返回图谱」同一条路。 */
  var back = null;
  function loaderOpen() { var L = $('loader'); return !!(L && !L.classList.contains('off')); }
  function otherPanelOpen() { return !!d.querySelector('#library.on,#confirm.on,#apiPanel.on,#dsPanel.on,#infoArchitecture[aria-hidden="false"]'); }
  /* 只在托盘真的排版出来时才给出口（托盘没排版出来时不显示孤零零的按钮） */
  function syncLoader() { var L = $('loader'); body.classList.toggle('sky-loader-on', loaderOpen() && !!(L && L.offsetWidth)); }
  function closeLoaderToHome() {
    if (homeMode !== 'home' || hasGraph() || !loaderOpen()) return false;
    var c = $('btnCancel');
    if (c) c.click(); else if (app() && app().showLoader) app().showLoader(false);
    if (home) { var b = $('skyHomeImport'); if (b && b.focus) b.focus({ preventScroll: true }); }
    return true;
  }
  function buildBack() {
    if (back) return back;
    back = d.createElement('button');
    back.type = 'button'; back.id = 'skyHomeBack'; back.className = 'sky-home-back';
    back.title = '收起材料托盘，回到星空首页（Esc）';
    back.innerHTML = GL.back + '<span>返回星空</span>';
    back.addEventListener('click', closeLoaderToHome);
    body.appendChild(back);
    var L = $('loader');
    if (L) {
      L.addEventListener('click', function (e) { if (e.target === L) closeLoaderToHome(); });
      if (g.MutationObserver) new g.MutationObserver(syncLoader).observe(L, { attributes: true, attributeFilter: ['class'] });
    }
    syncLoader();
    return back;
  }

  /* 最近作品：与旧壳「记忆」列表同源（GET /api/history）、同序（置顶优先 → 最近分析），最多 6 部 */
  function sortRecent(list) {
    return list.slice().sort(function (a, b) { return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || String(b.at || '').localeCompare(String(a.at || '')); });
  }
  function loadRecent() {
    if (!g.fetch) return;
    g.fetch('/api/history').then(function (r) { return r.ok ? r.json() : { items: [] }; }).then(function (dd) {
      homeItems = sortRecent((dd && dd.items) || []);
      renderRecent();
    }).catch(function () { homeItems = []; renderRecent(); });
  }
  function num(v) { v = +v; return isFinite(v) && v > 0 ? v : null; }
  function renderRecent() {
    if (!home) return;
    var list = homeItems.slice(0, 6), row = $('skyHomeRow');
    $('skyHomeRecent').hidden = !list.length;
    $('skyHomeEmpty').hidden = !!list.length;
    $('skyHomeCount').textContent = homeItems.length ? String(homeItems.length) : '';
    var all = $('skyHomeAll');
    all.hidden = homeItems.length <= list.length;
    all.textContent = '全部 ' + homeItems.length + ' 部 · 作品库';
    /* 星的大小 = 人数（对数），最亮（金）= 最近打开（last_open，缺则取分析时间）的那一部——置顶只决定次序，不决定亮度 */
    var maxN = list.reduce(function (m, it) { return Math.max(m, num(it.characters) || 0); }, 1);
    var latest = list.reduce(function (b, it) { var t = String(it.last_open || it.at || ''); return !b || t > b.t ? { k: it.key, t: t } : b; }, null);
    row.innerHTML = list.map(function (it, i) {
      var n = num(it.characters), ch = num(it.chapters), title = it.display || it.title || '未命名';
      var meta = [n != null ? n + ' 人' : null, ch != null ? ch + ' 回' : null].filter(Boolean).join(' · ');
      var tip = title + (it.pinned ? ' · 置顶' : '') + (meta ? ' · ' + meta : '') + (num(it.events) != null ? ' · ' + it.events + ' 剧情点' : '') + (num(it.relations) != null ? ' · ' + it.relations + ' 关系' : '');
      return '<li class="sh-li"><button type="button" class="sh-work' + (latest && latest.k === it.key ? ' is-latest' : '') + (it.pinned ? ' is-pinned' : '') + '" data-key="' + esc(it.key) + '" data-i="' + i + '" title="' + esc(tip) + '">' +
        STAR + '<span class="sh-work-t">' + esc(title) + '</span><span class="sh-work-m">' + esc(meta || '—') + '</span></button></li>';
    }).join('');
    Array.prototype.forEach.call(row.querySelectorAll('.sh-work'), function (b) {
      var it = list[+b.getAttribute('data-i')] || {}, n = num(it.characters) || 1;
      b.style.setProperty('--sh-s', (0.62 + 0.5 * Math.log(1 + n) / Math.log(1 + maxN)).toFixed(3));
      b.style.setProperty('--sh-i', b.getAttribute('data-i'));
    });
  }
  function openLibrary() { var b = $('btnLib'); if (b) b.click(); }
  function openImport() { var A = app(); if (A && A.showLoader) A.showLoader(true); }
  /* 打开一部作品：点旧壳「记忆」列表里同一张卡（走 histAction('open') 的原路径）；不在前 6 就点作品库卡片 */
  function openWork(key) {
    if (!key) return;
    var sel = '[data-key="' + (g.CSS && g.CSS.escape ? g.CSS.escape(key) : key) + '"]';
    var card = d.querySelector('#histList .hist' + sel) || d.querySelector('#libList .lbc' + sel);
    if (card) { card.click(); markOpening(key); return; }
    openLibrary();
  }
  function markOpening(key) {
    if (!home) return;
    Array.prototype.forEach.call(home.querySelectorAll('.sh-work'), function (b) { b.classList.toggle('is-opening', b.getAttribute('data-key') === key); });
    var it = homeItems.filter(function (x) { return x.key === key; })[0], t = it && (it.display || it.title);
    $('skyHomeLoadingT').textContent = t ? '正在展开《' + t + '》' : '正在展开星图';
    setHomeMode('loading');
    clearTimeout(homeTimer);
    homeTimer = setTimeout(function () { if (!hasGraph() && homeMode === 'loading') setHomeMode('home'); }, 15000);
  }

  /* 拖入：原样转交给旧壳托盘 #zone 的 drop 处理（同一个 DataTransfer，同步转发，文件夹递归照旧），再打开托盘 */
  function hasFiles(e) { var t = e.dataTransfer && e.dataTransfer.types; return !!t && Array.prototype.indexOf.call(t, 'Files') >= 0; }
  function onDragEnter(e) { if (!hasFiles(e)) return; e.preventDefault(); dragDepth++; home.classList.add('is-drag'); }
  function onDragOver(e) { if (!hasFiles(e)) return; e.preventDefault(); try { e.dataTransfer.dropEffect = 'copy'; } catch (x) {} }
  function onDragLeave() { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) home.classList.remove('is-drag'); }
  function onDrop(e) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0; home.classList.remove('is-drag');
    routeDrop(e.dataTransfer);
  }
  function routeDrop(dt) {
    var zone = $('zone');
    if (!zone || !dt) return false;
    var files = Array.prototype.slice.call(dt.files || []);
    var epub = files.filter(function (f) { return /\.epub$/i.test(f.name || ''); }).length;
    var ev = null;
    try { ev = new g.DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }); } catch (x) { ev = null; }
    if (!ev) return false;
    zone.dispatchEvent(ev);
    openImport();
    if (epub && epub === files.length) toast('EPUB 暂不能直接读取 · 先转成 txt / md / docx 再拖入', 4200);
    return true;
  }

  /* ================================================================ ② 工具星图菜单 */
  var TOOL_GROUPS = [
    { key: 'work', label: '作品', en: 'WORKS', items: [
      { id: 'btnLib', name: '作品库', desc: '打开已分析过的作品，或把材料载回托盘', glyph: 'lib', kbd: 'H' },
      { id: 'btnOpen', name: '更换材料', desc: '继续加一批材料，或换一部作品', glyph: 'swap' },
      { id: 'btnRe', name: '重新分析', desc: '先出方案，确认后才调用模型', glyph: 're' }
    ] },
    { key: 'data', label: '数据', en: 'DATA', items: [
      { id: 'btnApi', name: 'API 接入', desc: '模型档案 · 连通测试 · 调参', glyph: 'api' },
      { id: 'btnInfo', name: '资料索引', desc: '检索人物、剧情线、章节与引文', glyph: 'info' },
      { id: 'btnDistill', name: '蒸馏文风', desc: '把写法蒸馏成提示词 · 打开只看方案', glyph: 'distill' }
    ] },
    { key: 'view', label: '视图', en: 'VIEW', items: [
      { id: 'btnDual', name: '双页观测台', desc: '罗盘与星核共振场同时运行', glyph: 'full', kbd: '⇧D' },
      { id: 'btnFull', name: '全屏', desc: '铺满屏幕 · 再点一次退出', glyph: 'full' }
    ] }
  ];
  var menu = null, menuOn = false, returnFocus = null;
  function buildMenu() {
    if (menu) return menu;
    menu = d.createElement('div');
    menu.id = 'skyToolsMenu'; menu.className = 'sky-tools-menu'; menu.hidden = true;
    menu.setAttribute('role', 'menu'); menu.setAttribute('aria-label', '工具');
    menu.innerHTML = TOOL_GROUPS.map(function (gp) {
      return '<div class="stm-group" role="group" aria-labelledby="stmG-' + gp.key + '"><div class="stm-gl" id="stmG-' + gp.key + '"><span>' + esc(gp.label) + '</span><i>' + gp.en + '</i></div>' +
        gp.items.map(function (it) {
          return '<button type="button" class="stm-item" role="menuitem" tabindex="-1" data-for="' + it.id + '">' + GL[it.glyph] +
            '<span class="stm-name">' + esc(it.name) + '</span>' + (it.kbd ? '<kbd class="stm-key">' + it.kbd + '</kbd>' : '') +
            '<span class="stm-desc">' + esc(it.desc) + '</span></button>';
        }).join('') + '</div>';
    }).join('');
    body.appendChild(menu);
    menu.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.stm-item'); if (!b) return;
      e.preventDefault(); e.stopPropagation();
      activate(b);
    });
    menu.addEventListener('mousemove', function (e) { var b = e.target.closest && e.target.closest('.stm-item'); if (b && d.activeElement !== b && b.getAttribute('aria-disabled') !== 'true') b.focus({ preventScroll: true }); });
    return menu;
  }
  function menuItems() { return menu ? Array.prototype.filter.call(menu.querySelectorAll('.stm-item'), function (b) { return !b.hidden; }) : []; }
  function activate(b) {
    if (!b || b.getAttribute('aria-disabled') === 'true') return;
    var src = $(b.getAttribute('data-for'));
    closeMenu(false);
    if (src) src.click();
  }
  function syncItems() {
    Array.prototype.forEach.call(menu.querySelectorAll('.stm-item'), function (b) {
      var src = $(b.getAttribute('data-for'));
      b.hidden = !src;
      var off = !!(src && (src.disabled || src.getAttribute('aria-disabled') === 'true'));
      if (b.getAttribute('data-for') === 'btnRe' && app() && app().busy && app().busy()) off = true;
      b.setAttribute('aria-disabled', off ? 'true' : 'false');
      if (b.getAttribute('data-for') === 'btnFull') {
        var full = !!(d.fullscreenElement || d.webkitFullscreenElement);
        b.querySelector('.stm-name').textContent = full ? '退出全屏' : '全屏';
        b.querySelector('.stm-desc').textContent = full ? '回到窗口' : '铺满屏幕 · 再点一次退出';
      }
    });
  }
  function placeMenu() {
    var t = $('skyTools'); if (!menu || !t) return;
    var bar = t.closest ? t.closest('.sky-top') : null;
    var r = t.getBoundingClientRect(), W = g.innerWidth || 1200, top = bar ? bar.getBoundingClientRect().bottom : r.bottom;
    menu.style.setProperty('--stm-y', Math.round(Math.max(r.bottom, top) + 6) + 'px');
    /* 宽屏：挂在「工具」钮下、右缘对齐；窄屏（≤560）：与顶栏同宽的一张薄片，不悬在屏幕中间 */
    var sheet = W <= 560 && bar, br = sheet ? bar.getBoundingClientRect() : null;
    menu.classList.toggle('is-sheet', !!sheet);
    menu.style.setProperty('--stm-r', Math.max(10, Math.round(W - (sheet ? br.right : r.right))) + 'px');
    menu.style.setProperty('--stm-l', Math.max(10, Math.round(sheet ? br.left : 10)) + 'px');
  }
  function openMenu() {
    if (!body.classList.contains('sky-shell') || !$('skyTools')) return false;
    buildMenu(); syncItems(); placeMenu();
    var t = $('skyTools');
    t.setAttribute('aria-haspopup', 'menu'); t.setAttribute('aria-controls', 'skyToolsMenu');
    if (!body.classList.contains('atlas-tools-open')) body.classList.add('atlas-tools-open');
    t.setAttribute('aria-expanded', 'true');
    menu.hidden = false; menuOn = true;
    menu.classList.remove('is-in'); void menu.offsetWidth; menu.classList.add('is-in');
    returnFocus = t;
    var first = menuItems().filter(function (b) { return b.getAttribute('aria-disabled') !== 'true'; })[0];
    if (first) first.focus({ preventScroll: true });
    return true;
  }
  function closeMenu(refocus) {
    if (!menuOn && !body.classList.contains('atlas-tools-open')) return false;
    menuOn = false;
    if (menu) menu.hidden = true;
    body.classList.remove('atlas-tools-open');
    var t = $('skyTools'); if (t) t.setAttribute('aria-expanded', 'false');
    if (refocus && returnFocus && returnFocus.focus) returnFocus.focus({ preventScroll: true });
    return true;
  }
  /* 顶栏「工具」仍由 sky-shell 切 body.atlas-tools-open（原状态位）；这里跟着状态位开合星图菜单，旧方角按钮排由 CSS 收起 */
  function syncMenuToBody() {
    var want = body.classList.contains('atlas-tools-open') && body.classList.contains('sky-shell');
    if (want && !menuOn) openMenu();
    else if (!want && menuOn) closeMenu(false);
  }
  function onMenuKey(e) {
    if (!menuOn) {
      if (e.key === 'Escape' && homeMode === 'home' && loaderOpen() && !otherPanelOpen() && closeLoaderToHome()) { e.preventDefault(); e.stopPropagation(); }
      return;
    }
    var k = e.key, list = menuItems().filter(function (b) { return b.getAttribute('aria-disabled') !== 'true'; }), i = list.indexOf(d.activeElement);
    if (k === 'Escape') { e.preventDefault(); e.stopPropagation(); closeMenu(true); return; }
    if (k === 'Tab') { e.preventDefault(); e.stopPropagation(); closeMenu(true); return; }
    if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'Home' || k === 'End') {
      e.preventDefault(); e.stopPropagation();
      if (!list.length) return;
      var n = k === 'Home' ? 0 : k === 'End' ? list.length - 1 : k === 'ArrowDown' ? (i + 1) % list.length : (i - 1 + list.length) % list.length;
      if (i < 0 && k === 'ArrowUp') n = list.length - 1;
      list[n].focus({ preventScroll: true });
      return;
    }
    if ((k === 'Enter' || k === ' ') && menu.contains(d.activeElement)) { e.preventDefault(); e.stopPropagation(); activate(d.activeElement); return; }
    /* 其余可打印键（H 作品库、/ 搜索 …）：先收起菜单，快捷键照常往下走——免得面板开在菜单底下 */
    if (k && k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) closeMenu(false);
  }
  function onPointerDown(e) {
    if (!menuOn) return;
    var t = e.target;
    if (menu && menu.contains(t)) return;
    var tb = $('skyTools'); if (tb && tb.contains(t)) return;   /* 按钮自己的点击由 sky-shell 切换状态位 */
    closeMenu(false);
  }

  /* ================================================================ ③ 星座态底部小注 */
  /* 线型样本与 .cl-dom-legend 同一口径（CLDomainsModel.REL_CLASSES：色 + 实 / 虚 / 点 / 点划），色与线型在 CSS 里按 data-rel 取 */
  var REL_STYLE = { ally: 1, kin: 1, bond: 1, oppose: 1, dark: 1, other: 1, cooccur: 1 };
  var SAMPLE = '<svg class="lg-sample" viewBox="0 0 24 6" aria-hidden="true"><line x1="1.5" y1="3" x2="22.5" y2="3"/></svg>';
  function legendHtml() {
    var A = app(); if (!A || !A.atlas || !A.atlas.skyView) return null;
    var v = A.atlas.skyView(), rels = (v && v.relations) || [], M = g.CLDomainsModel;
    var st = M && M.relStats ? M.relStats(rels) : { total: rels.length, classes: [] };
    var derived = !!(rels.length && rels[0] && rels[0].derived);
    var S = A.scene && A.scene(), ri = S && S.rimInfo ? S.rimInfo() : null;
    /* 平面天球图（rimInfo.mode = 'sky'）：组间联系由星域层 CLSkyField 画成「束丝」（跨扇区）与「光束」（盘心团 → 各扇区），读它实际画了多少；
     * 旧星路布局才读场景关系网的「全景上限」。两边都写成「画了 / 共有」，守恒、不冒充。 */
    var F = ri && ri.mode === 'sky' && g.CLSky && g.CLSky.field ? g.CLSky.field() : null, fs = F && F.stats ? F.stats() : null;
    var web = !fs && S && S.relationWeb ? S.relationWeb() : null;
    var rel = st.classes.map(function (c) {
      var id = REL_STYLE[c.id] ? c.id : 'other';
      var what = (c.kinds || []).slice(0, 6).map(function (k) { return k.kind + ' ' + k.count; }).join(' · ');
      return '<span class="lg lg-rel" data-rel="' + id + '" title="' + esc(c.label + ' ' + c.count + ' 条' + (what ? '：' + what : '')) + '">' + SAMPLE +
        '<span class="lg-n">' + esc(c.label) + '</span><b>' + c.count + '</b></span>';
    });
    var parts = [];
    if (rel.length) parts.push('<span class="lg-group">' + rel.join('') + '</span>');
    var more = false;
    if (fs) {
      var drawn = [];
      /* 光层在时默认只亮强关系（fs.strong），悬停角色 / 团才现它的全部联系；SVG 退路画的是前 fs.silk 束 */
      var shownN = document.body.classList.contains('skd-gl') && fs.strong ? fs.strong : fs.silk;
      if (fs.silkTotal > 0) drawn.push('<span class="lg lg-web" title="跨扇区的联系：默认只画最强的 ' + shownN + ' 束，共 ' + fs.silkTotal + ' 条；悬停角色或团时显示它的全部联系">组间 <b>' + shownN + '</b> / ' + fs.silkTotal + ' 束丝</span>');
      if (fs.beams > 0) drawn.push('<span class="lg lg-web" title="盘心主角团与各扇区之间的联系，每个相连的扇区一束">盘心 <b>' + fs.beams + '</b> 束光</span>');
      if (drawn.length) parts.push('<span class="lg-group">' + drawn.join('') + '</span>');
      more = shownN < fs.silkTotal;
    } else if (web && web.pruned && web.total) {
      parts.push('<span class="lg lg-web" title="全景只画最强的 ' + web.shown + ' 条，其余悬停角色时显示">全景 <b>' + web.shown + '</b> / ' + web.total + '</span>');
      more = true;
    }
    var hint = [];
    if (derived) hint.push('原书无关系记录');
    if (more) hint.push('悬停角色看全部');
    hint.push('点星进入罗盘');
    hint.push('「剧情」唤醒星盘');
    parts.push('<span class="lg lg-hint">' + esc(hint.join(' · ')) + '</span>');
    return '<span class="lg-chrome" hidden></span>' + parts.join('<span class="lg-sep" aria-hidden="true"></span>');
  }
  var legendObs = null, fieldObs = null, legendBusy = false, legendLast = '';
  /* force = 读数可能变了（星域层重建 / 换分类）：内容不同才重写 */
  function decorateLegend(force) {
    var L = $('skyLegend'); if (!L || legendBusy) return;
    if (body.classList.contains('sky-plot-on') || body.classList.contains('sky-compass-on')) { L.classList.remove('is-chrome'); return; }
    var mine = !!L.querySelector('.lg-chrome');
    if (mine && !force) return;
    var html = legendHtml(); if (html == null) return;
    if (mine && html === legendLast) return;
    legendBusy = true;
    try { L.innerHTML = html; L.classList.add('is-chrome'); legendLast = html; } finally { legendBusy = false; }
  }
  function watchLegend() {
    var L = $('skyLegend');
    if (L && !legendObs && g.MutationObserver) {
      legendObs = new g.MutationObserver(function () { decorateLegend(); if (!insetRO) syncInsets(); });
      legendObs.observe(L, { childList: true });
    }
    /* 星域层每次重建都会改写自己 svg 上的 data-silk / data-beams：跟着它刷新读数（换分类后自动重建） */
    var F = g.CLSky && g.CLSky.field ? g.CLSky.field() : null;
    if (F && F.el && !fieldObs && g.MutationObserver) {
      fieldObs = new g.MutationObserver(function () { decorateLegend(true); if (!insetRO) syncInsets(); });
      fieldObs.observe(F.el, { attributes: true, attributeFilter: ['data-silk', 'data-beams'] });
    }
    decorateLegend(true);
  }

  /* 顶栏底缘 / 底栏顶缘 → 两个 CSS 变量：旧横幅（在跑作业）、进度胶囊、轻提示据此落位，不压星空壳的顶栏与底栏 */
  /* 顶栏 / 底栏尺寸一变就重算两个变量：ResizeObserver 在浏览器排完版之后回调，读框不再强制同步布局。
     之前图例改写（MutationObserver 微任务）与每次换态都立即读框——正赶在刚改完 DOM 的同一个任务里，大书开罗盘那一下要多排一整页（约 24 ms） */
  var insetRO = null;
  function watchInsets() {
    if (insetRO || !g.ResizeObserver) return;
    var bar = d.querySelector('.sky-top'), bot = d.querySelector('.sky-bottom');
    if (!bar && !bot) return;
    insetRO = new g.ResizeObserver(function () { syncInsets(); });
    if (bar) insetRO.observe(bar);
    if (bot) insetRO.observe(bot);
  }
  function syncInsets() {
    var root = d.documentElement, bar = d.querySelector('.sky-top'), bot = d.querySelector('.sky-bottom'), H = g.innerHeight || 800;
    if (bar && bar.offsetHeight) root.style.setProperty('--sky-chrome-top', Math.round(bar.getBoundingClientRect().bottom) + 'px');
    if (bot) {
      var top = H;
      Array.prototype.forEach.call(bot.children, function (c) { if (c.hidden || !c.offsetHeight) return; top = Math.min(top, c.getBoundingClientRect().top); });
      root.style.setProperty('--sky-chrome-bottom', Math.max(16, Math.round(H - top)) + 'px');
    }
  }

  /* ================================================================ 接线 */
  function onGraphReady() {
    leaveHome();
    /* sky-shell 的 cl:graph-ready 监听先注册、先执行：此刻 #skyHud 已挂好 */
    setTimeout(function () { watchLegend(); syncMenuToBody(); syncInsets(); watchInsets(); }, 0);
  }
  d.addEventListener('cl:sky-plot', function () { if (!insetRO) setTimeout(syncInsets, 0); });
  d.addEventListener('cl:sky-compass', function () { if (!insetRO) setTimeout(syncInsets, 0); });
  d.addEventListener('cl:graph-ready', onGraphReady);
  if (g.MutationObserver) new g.MutationObserver(syncMenuToBody).observe(body, { attributes: true, attributeFilter: ['class'] });
  g.addEventListener('keydown', onMenuKey, true);
  d.addEventListener('pointerdown', onPointerDown, true);
  g.addEventListener('resize', function () { if (menuOn) placeMenu(); syncInsets(); });
  d.addEventListener('fullscreenchange', function () { if (menuOn) syncItems(); });
  if (!hasGraph()) enterHome(); else onGraphReady();

  g.CLSkyChrome = {
    VERSION: VERSION,
    enabled: function () { return true; },
    home: function () { return homeMode; },
    recent: function () { return homeItems.slice(0, 6).map(function (it) { return { key: it.key, title: it.display || it.title, characters: num(it.characters), chapters: num(it.chapters) }; }); },
    openWork: openWork,
    routeDrop: routeDrop,
    menuOpen: function () { return menuOn; },
    openMenu: openMenu,
    closeMenu: function () { return closeMenu(false); },
    legendHtml: legendHtml,
    refresh: function () { if (homeMode !== 'off') loadRecent(); decorateLegend(true); }
  };
})(window);

/* v91.2 · Pointer constellation: feeds only optical CSS variables.  No graph
 * coordinates, camera state, or hit targets are touched, so drag/keyboard
 * navigation keeps its existing ownership and precision. */
(function (g) {
  'use strict';
  var d = g.document;
  if (!d || !d.documentElement || !d.body) return;
  var root = d.documentElement, raf = 0, px = .5, py = .42, reduced = false;
  try { reduced = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
  if (reduced || !g.addEventListener) return;
  function frame() {
    raf = 0;
    root.style.setProperty('--frontier-pointer-x', (px * 100).toFixed(2) + '%');
    root.style.setProperty('--frontier-pointer-y', (py * 100).toFixed(2) + '%');
    root.style.setProperty('--frontier-hud-x', ((px - .5) * 8).toFixed(2) + 'px');
    root.style.setProperty('--frontier-hud-y', ((py - .42) * 5).toFixed(2) + 'px');
  }
  function schedule() {
    if (raf) return;
    if (typeof g.requestAnimationFrame === 'function') raf = g.requestAnimationFrame(frame);
    else raf = g.setTimeout(frame, 32);
  }
  function move(e) {
    if (!e || e.pointerType === 'touch') return;
    px = Math.max(0, Math.min(1, e.clientX / Math.max(1, g.innerWidth || 1)));
    py = Math.max(0, Math.min(1, e.clientY / Math.max(1, g.innerHeight || 1)));
    schedule();
  }
  function reset() { px = .5; py = .42; schedule(); }
  d.addEventListener('pointermove', move, { passive: true });
  d.addEventListener('pointerleave', reset, { passive: true });
})(window);

/* v91.3 · Dense-plan orchestration: signal lens changes and drag intent with
 * body state classes. These are presentation cues only; no event is cancelled
 * and no renderer state is mutated. */
(function (g) {
  'use strict';
  var d = g.document, body = d && d.body;
  if (!d || !body) return;
  var pulseTimer = 0, dragging = false;
  function pulse() {
    body.classList.remove('frontier-view-flash');
    if (g.requestAnimationFrame) g.requestAnimationFrame(function () { body.classList.add('frontier-view-flash'); });
    else body.classList.add('frontier-view-flash');
    clearTimeout(pulseTimer); pulseTimer = g.setTimeout(function () { body.classList.remove('frontier-view-flash'); }, 900);
  }
  function interactiveTarget(t) {
    return !!(t && t.closest && t.closest('#gl,.sky-disc,.sky-field,.sky-compass,.cl-ann-layer,#gemHost,.cl-domains-lamps,.atlas-preview-hud'));
  }
  if (g.MutationObserver) {
    var lastView = body.getAttribute('data-atlas-view') || '';
    new g.MutationObserver(function () {
      var next = body.getAttribute('data-atlas-view') || '';
      if (next !== lastView) { lastView = next; pulse(); }
    }).observe(body, { attributes: true, attributeFilter: ['data-atlas-view'] });
  }
  d.addEventListener('pointerdown', function (e) {
    if (interactiveTarget(e.target)) { dragging = true; body.classList.add('frontier-drag'); }
  }, { passive: true, capture: true });
  function endDrag() { if (!dragging) return; dragging = false; body.classList.remove('frontier-drag'); }
  d.addEventListener('pointerup', endDrag, { passive: true, capture: true });
  d.addEventListener('pointercancel', endDrag, { passive: true, capture: true });
  d.addEventListener('pointerleave', endDrag, { passive: true, capture: true });
})(window);
