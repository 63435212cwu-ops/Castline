(function (g) {
  'use strict';
  var d = g.document, VERSION = '1';
  if (!d || !d.body) { g.CLSkyChrome = { VERSION: VERSION, enabled: function () { return false; } }; return; }

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

  var GL = {
    lib: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h3.4v15H5zM10.4 4.5h3.4v15h-3.4z"/><path d="m15.6 5.4 3.3-.8 2.6 14.4-3.3.8z"/></svg>',
    swap: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13.5v5h16v-5"/><path d="M12 4v10M8.2 10.4 12 14l3.8-3.6"/></svg>',
    re: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.8 12.6A6.9 6.9 0 1 1 16.9 7"/><path d="M17.6 3.6v4h-4"/><circle cx="12" cy="12" r="1.2" class="gl-fill"/></svg>',
    vswitch: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4.5v10M6 4.5 3.4 7.1M6 4.5l2.6 2.6"/><path d="M18 19.5v-10M18 19.5l-2.6-2.6M18 19.5l2.6-2.6"/></svg>',
    api: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7.6" cy="12" r="3.3"/><path d="M10.9 12H20.4M17.4 12v3M20.4 12v2.2"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.5h9M4 11h6M4 15.5h4.5"/><circle cx="15.6" cy="14.2" r="3.6"/><path d="m18.2 16.8 2.6 2.6"/></svg>',
    distill: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.3 4h5.4M10.4 4v5.1L5.9 17.4a1.8 1.8 0 0 0 1.6 2.6h9a1.8 1.8 0 0 0 1.6-2.6l-4.5-8.3V4"/><path d="M7.9 15.4h8.2"/></svg>',
    full: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
    open: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="9.5" ry="5.6"/><path d="M12 3.4 13.2 10.8 20.6 12 13.2 13.2 12 20.6 10.8 13.2 3.4 12 10.8 10.8z" class="gl-fill"/></svg>',
    tray: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13.5v5h16v-5"/><path d="M12 4v10M8.2 10.4 12 14l3.8-3.6"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 5.5 8 12l6.5 6.5"/></svg>',
    lab: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="7" height="6" rx="1"/><rect x="13.5" y="5" width="7" height="6" rx="1"/><rect x="3.5" y="14" width="7" height="6" rx="1"/><path d="M14 17h6M17 14v6"/></svg>',
    audio: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 9.2a4 4 0 0 1 0 5.6M18.3 6.6a7.8 7.8 0 0 1 0 10.8"/></svg>',
    warn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 21.5 20h-19z"/><path d="M12 10v4.6"/><circle cx="12" cy="17.2" r="1" class="gl-fill"/></svg>',
    cam: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="7" width="18" height="12" rx="2"/><path d="M8.5 7 10 4.5h4L15.5 7"/><circle cx="12" cy="13" r="3.6"/></svg>'
  };
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
        '<section class="sh-error" id="skyHomeError" role="alert" aria-labelledby="skyHomeErrorH" hidden>' +
          '<h2 class="sh-error-h" id="skyHomeErrorH">' + GL.warn + '<span>这张星图没能展开</span></h2>' +
          '<p class="sh-error-why" id="skyHomeErrorWhy"></p>' +
          '<p class="sh-error-src" id="skyHomeErrorSrc"></p>' +
          '<details class="sh-error-tech" id="skyHomeErrorTech"><summary>技术细节</summary><p class="sh-error-detail" id="skyHomeErrorDetail"></p></details>' +
          '<div class="sh-error-acts">' +
            '<button type="button" class="sh-btn is-primary" id="skyHomeErrLib">' + GL.lib + '<span>返回作品库</span></button>' +
            '<button type="button" class="sh-btn" id="skyHomeErrRetry">' + GL.re + '<span>重试</span></button>' +
          '</div>' +
        '</section>' +
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
    $('skyHomeErrLib').addEventListener('click', openLibrary);
    $('skyHomeErrRetry').addEventListener('click', function () { try { g.location.reload(); } catch (e) {} });
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
    var on = mode === 'home' || mode === 'loading' || mode === 'error';
    body.classList.toggle('sky-home-on', on);
    home.hidden = !on;
    $('skyHomeLoading').hidden = mode !== 'loading';
    $('skyHomeError').hidden = mode !== 'error';
  }
  var ERR_WHY = {
    http: function (e) { return e.status === 404 ? '找不到这份图谱文件：它可能已被删除、改名，或链接里的地址有误。' : '服务器没有返回这份图谱（HTTP ' + e.status + '）。'; },
    json: function () { return '这个地址指向的不是图谱数据：内容无法按 JSON 读取。'; },
    shape: function () { return '这个文件不是图谱：里面没有角色列表。'; },
    mount: function (e) { return '图谱数据已取到，但展开时出错：' + String(e.message || '').replace(/^图谱数据无法展开：/, ''); },
    net: function () { return '读取图谱时连接中断：本地服务可能已停止。'; },
    slow: function () { return '读取这份图谱很久没有返回：本地服务可能已停止，或这份数据特别大。'; }
  };
  function showError(info) {
    info = info || {};
    if (hasGraph()) { toast(info.message || '数据文件读取失败', 4200); return; }
    buildHome(); buildBack(); clearTimeout(homeTimer);
    var BE = g.CLBootErrors || null;
    $('skyHomeErrorWhy').textContent = BE ? BE.why(info) : (ERR_WHY[info.kind] || ERR_WHY.net)(info);
    $('skyHomeErrorSrc').textContent = info.src ? '地址：' + info.src : '';
    var det = $('skyHomeErrorDetail');
    if (det) det.textContent = BE ? BE.detail(info) : '';
    var tech = $('skyHomeErrorTech');
    if (tech) tech.hidden = !(BE && BE.detail(info));
    var retry = $('skyHomeErrRetry');
    if (retry) retry.dataset.retryable = BE && BE.classify(info).retryable ? 'true' : 'false';
    setHomeMode('error');
    if (loaderOpen() && app() && app().showLoader) app().showLoader(false);
    loadRecent();
    var b = $('skyHomeErrLib'); if (b && b.focus) b.focus({ preventScroll: true });
  }
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
    if (g.CLLoadError) { showError(g.CLLoadError); return; }
    var E0 = $('lcErr'), early = E0 ? String(E0.textContent || '').trim() : '', loading = bootLoading() && !early;
    setHomeMode(loading ? 'loading' : 'home');
    var L = $('loader');
    if (!loading && !early && L && !L.classList.contains('off') && app() && app().showLoader) app().showLoader(false);
    if (early) toast(early, 4200);
    if (loading) { clearTimeout(homeTimer); homeTimer = setTimeout(function () { if (!hasGraph() && homeMode === 'loading') slowGate(); }, slowMs()); }
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

  var back = null;
  function loaderOpen() { var L = $('loader'); return !!(L && !L.classList.contains('off')); }
  function otherPanelOpen() {
    if (g.CLModal && CLModal.open && CLModal.open()) return true;
    return !!(g.CLInformationArchitecture && CLInformationArchitecture.isOpen && CLInformationArchitecture.isOpen());
  }
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

  function sortRecent(list) {
    if (g.CLSkySwitcher && g.CLSkySwitcher.orderWorks) return g.CLSkySwitcher.orderWorks(list);
    return list.slice().sort(function (a, b) { return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || String(b.at || '').localeCompare(String(a.at || '')) || String(a.key || '').localeCompare(String(b.key || '')); });
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
    all.textContent = '全部 ' + homeItems.length + ' 张星图 · 作品库';
    var maxN = list.reduce(function (m, it) { return Math.max(m, num(it.characters) || 0); }, 1);
    var latest = list.reduce(function (b, it) { var t = String(it.last_open || it.at || ''); return !b || t > b.t ? { k: it.key, t: t } : b; }, null);
    row.innerHTML = list.map(function (it, i) {
      var n = num(it.characters), ch = num(it.chapters), title = it.display || it.title || '未命名';
      var kind = {assistant_review:'代理核验版',source_review:'引文核对版',model_enrichment:'结构补析版',original:'原分析版'}[it.versionKind] || '原分析版';
      var meta = [kind,n != null ? n + ' 人' : null,ch != null ? ch + ' 回' : null].filter(Boolean).join(' · ');
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
    homeTimer = setTimeout(function () { if (!hasGraph() && homeMode === 'loading') slowGate(); }, slowMs());
  }
  function slowMs() { return (g.CLBootErrors && g.CLBootErrors.SLOW_MS) || 15000; }
  function slowGate() {
    var q; try { q = new URLSearchParams(g.location.search); } catch (e) { q = null; }
    showError(g.CLBootErrors && g.CLBootErrors.slowInfo ? g.CLBootErrors.slowInfo(q && q.get('data') || '') : { kind: 'slow' });
  }

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
    { key: 'work', label: '作品', items: [
      { id: 'btnLib', name: '作品库', desc: '打开已分析过的作品，或把材料载回托盘', glyph: 'lib', kbd: 'H' },
      { id: 'skySwitch', name: '换作品', desc: '不绕书库 · 直接打开另一部已分析的作品，这本书留在原地', glyph: 'vswitch' },
      { id: 'btnOpen', name: '更换材料', desc: '继续加一批材料，或换一部作品', glyph: 'swap' },
      { id: 'btnRe', name: '重新分析', desc: '先出方案，确认后才调用模型', glyph: 're' }
    ] },
    { key: 'data', label: '数据', items: [
      { id: 'btnApi', name: 'API 接入', desc: '模型档案 · 连通测试 · 调参', glyph: 'api' },
      { id: 'btnInfo', name: '资料索引', desc: '检索人物、剧情线、章节与引文', glyph: 'info' },
      { id: 'btnEnrich', name: '结构补析', desc: '先核对引文来源，再选择补充故事线、任务与伏笔', glyph: 're' },
      { id: 'btnDistill', name: '蒸馏文风', desc: '把写法蒸馏成提示词 · 打开只看方案', glyph: 'distill' }
    ] },
    { key: 'view', label: '视图', items: [
      { id: 'btnDual', name: '双页观测台', desc: '罗盘与星核共振场同时运行', glyph: 'full', kbd: '⇧D' },
      { id: 'btnFull', name: '全屏', desc: '铺满屏幕 · 再点一次退出', glyph: 'full' },
      { id: 'skySnapshot', name: '导出快照', desc: '当前星盘画面存成 PNG（按当前画质档原尺寸）· 快照为星盘画面，不含界面', glyph: 'cam', kbd: '⇧S' }
    ] },
    { key: 'more', label: '更多', items: [
      { id: 'skyLabBtn', name: '预演实验室', desc: '故事板 · 读图模式 · 可分享深链', glyph: 'lab', fold: true },
      { id: 'skyAudioToggle', name: '声场', desc: '深空环境声 · 快捷键 M', glyph: 'audio', fold: true }
    ] }
  ];
  var menu = null, menuOn = false, returnFocus = null;
  function buildMenu() {
    if (menu) return menu;
    menu = d.createElement('div');
    menu.id = 'skyToolsMenu'; menu.className = 'sky-tools-menu'; menu.hidden = true;
    menu.setAttribute('role', 'menu'); menu.setAttribute('aria-label', '工具');
    menu.innerHTML = TOOL_GROUPS.map(function (gp) {
      return '<div class="stm-group" role="group" data-group="' + gp.key + '" aria-labelledby="stmG-' + gp.key + '"><div class="stm-gl" id="stmG-' + gp.key + '"><span>' + esc(gp.label) + '</span></div>' +
        gp.items.map(function (it) {
          return '<button type="button" class="stm-item" role="menuitem" tabindex="-1" data-for="' + it.id + '"' + (it.fold ? ' data-fold="1"' : '') + ' aria-describedby="stmD-' + it.id + '">' + GL[it.glyph] +
            '<span class="stm-name">' + esc(it.name) + '</span>' + (it.kbd ? '<kbd class="stm-key">' + it.kbd + '</kbd>' : '') +
            '<span class="stm-desc" id="stmD-' + it.id + '">' + esc(it.desc) + '</span></button>';
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
    if (b.getAttribute('data-for') === 'btnEnrich' && g.CLSkyEnrich) { CLSkyEnrich.open(); return; }
    if (b.getAttribute('data-for') === 'skySwitch') { if (g.CLSkySwitcher) g.CLSkySwitcher.open(); return; }
    if (b.getAttribute('data-for') === 'skySnapshot') { if (g.CLSkySnapshot) g.CLSkySnapshot.exportNow(); return; }
    if (src) src.click();
  }
  function syncItems() {
    Array.prototype.forEach.call(menu.querySelectorAll('.stm-item'), function (b) {
      var src = $(b.getAttribute('data-for'));
      if (b.getAttribute('data-for') === 'btnEnrich') { b.hidden = !g.CLSkyEnrich; b.setAttribute('aria-disabled', g.CLSkyEnrich ? 'false' : 'true'); return; }
      if (b.getAttribute('data-for') === 'skySwitch') { b.hidden = !g.CLSkySwitcher; b.setAttribute('aria-disabled', g.CLSkySwitcher && hasGraph() ? 'false' : 'true'); return; }
      if (b.getAttribute('data-for') === 'skySnapshot') {
        var sn = g.CLSkySnapshot;
        b.hidden = !sn;
        b.setAttribute('aria-disabled', sn && sn.ready && sn.ready() ? 'false' : 'true');
        if (sn) {
          var sd = $('stmD-skySnapshot');
          if (sd) sd.textContent = sn.ready() ? '当前星盘画面存成 PNG（按当前画质档原尺寸）· 快照为星盘画面，不含界面' : '还没展开星盘，没有可导出的画面 · 快照为星盘画面，不含界面';
        }
        return;
      }
      b.hidden = !src || (b.hasAttribute('data-fold') && !!src.getClientRects().length);
      if (src && b.getAttribute('data-for') === 'skyAudioToggle') {
        var playing = src.getAttribute('aria-pressed') === 'true';
        b.querySelector('.stm-name').textContent = playing ? '声场 · 开' : '声场 · 关';
        b.querySelector('.stm-desc').textContent = playing ? '深空环境声播放中 · 点按静音（M）' : '已静音 · 点按开启深空环境声（M）';
      }
      var off = !!(src && (src.disabled || src.getAttribute('aria-disabled') === 'true'));
      if (b.getAttribute('data-for') === 'btnRe' && app() && app().busy && app().busy()) off = true;
      b.setAttribute('aria-disabled', off ? 'true' : 'false');
      if (b.getAttribute('data-for') === 'btnFull') {
        var FS = g.CLSkyFullscreen, fsEl = d.documentElement;
        var fsOk = FS ? FS.supported(d) : !!(fsEl && (typeof fsEl.requestFullscreen === 'function' || typeof fsEl.webkitRequestFullscreen === 'function'));
        var full = FS ? FS.active(d) : !!(d.fullscreenElement || d.webkitFullscreenElement);
        if (!fsOk) {
          b.setAttribute('aria-disabled', 'true');
          b.querySelector('.stm-name').textContent = '全屏';
          b.querySelector('.stm-desc').textContent = '此浏览器不支持整页全屏 · 部分移动端浏览器不支持 Fullscreen API';
        } else {
          b.setAttribute('aria-pressed', full ? 'true' : 'false');
          b.querySelector('.stm-name').textContent = full ? '退出全屏' : '全屏';
          b.querySelector('.stm-desc').textContent = full ? '回到窗口 · Esc 或再点一次退出' : '铺满屏幕 · 再点一次退出';
        }
      }
    });
    Array.prototype.forEach.call(menu.querySelectorAll('.stm-group'), function (gp) { gp.hidden = !gp.querySelector('.stm-item:not([hidden])'); });
  }
  function placeMenu() {
    var t = $('skyTools'); if (!menu || !t) return;
    var bar = t.closest ? t.closest('.sky-top') : null;
    var r = t.getBoundingClientRect(), W = g.innerWidth || 1200, top = bar ? bar.getBoundingClientRect().bottom : r.bottom;
    menu.style.setProperty('--stm-y', Math.round(Math.max(r.bottom, top) + 6) + 'px');
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
  function syncMenuToBody() {
    var want = body.classList.contains('atlas-tools-open') && body.classList.contains('sky-shell');
    if (want && !menuOn) openMenu();
    else if (!want && menuOn) closeMenu(false);
  }
  function onMenuKey(e) {
    if (e.isComposing) return;
    if (!menuOn) {
      if (e.key === 'Escape' && homeMode === 'home' && loaderOpen() && !otherPanelOpen() && closeLoaderToHome()) { e.preventDefault(); e.stopPropagation(); }
      return;
    }
    var k = e.key, list = menuItems().filter(function (b) { return b.getAttribute('aria-disabled') !== 'true'; }), i = list.indexOf(d.activeElement);
    if (e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing && (k === 'Enter' || k === ' ')) { e.preventDefault(); e.stopPropagation(); return; }
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
    if (k && k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) closeMenu(false);
  }
  function onPointerDown(e) {
    if (!menuOn) return;
    var t = e.target;
    if (menu && menu.contains(t)) return;
    var tb = $('skyTools'); if (tb && tb.contains(t)) return;
    closeMenu(false);
  }

  /* ================================================================ ③ 星座态底部小注 */
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
    try {
      var DIS = g.CLSkyDisclosure;
      if (DIS) {
        var shownTotal = fs ? (shownN + (fs.beams || 0)) : (web && web.shown ? web.shown : null);
        var grandTotal = fs ? (fs.silkTotal + (fs.beams || 0)) : (web && web.total ? web.total : null);
        if (grandTotal != null && shownTotal != null) {
          var disc = DIS.of({ level: 'panorama', total: grandTotal, shown: shownTotal,
            retained: grandTotal, labelCount: rel.length });
          var bdg = DIS.badge({ level: 'panorama', total: grandTotal, shown: shownTotal, retained: grandTotal });
          hint.push(bdg.text + ' · ' + (disc.restore.canRestore ? '可恢复' : '不可恢复'));
        }
      }
    } catch (e) {  }
    hint.push('点星进入罗盘');
    hint.push('「剧情」唤醒星盘');
    hint.push('阅读按原文出现顺序');
    parts.push('<span class="lg lg-hint">' + esc(hint.join(' · ')) + '</span>');
    return '<span class="lg-chrome" hidden></span>' + parts.join('<span class="lg-sep" aria-hidden="true"></span>');
  }
  var legendObs = null, fieldObs = null, legendBusy = false, legendLast = '';
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
    var F = g.CLSky && g.CLSky.field ? g.CLSky.field() : null;
    if (F && F.el && !fieldObs && g.MutationObserver) {
      fieldObs = new g.MutationObserver(function () { decorateLegend(true); if (!insetRO) syncInsets(); });
      fieldObs.observe(F.el, { attributes: true, attributeFilter: ['data-silk', 'data-beams'] });
    }
    decorateLegend(true);
  }

  var brandObs = null;
  function syncBrandMeta() {
    var titleEl = $('skyTitle'), subEl = $('skySub');
    if (!titleEl || !subEl) return;
    var tText = String(titleEl.textContent || '').trim();
    if (tText && titleEl.title !== tText) titleEl.title = tText;
    var sText = String(subEl.textContent || '').trim();
    if (sText && subEl.title !== sText) subEl.title = sText;

    var A = app(), G = A && A.graph ? A.graph() : null;
    var author = G && (G.author || (G.meta && G.meta.author) || (G.info && G.info.author));
    if (author && sText && sText.indexOf(author) < 0 && !subEl.dataset.hasAuthor) {
      subEl.dataset.hasAuthor = '1';
      var authorBadge = '〔' + author + ' 著〕 · ';
      subEl.textContent = authorBadge + sText;
      subEl.title = subEl.textContent;
    }
  }

  function syncViewport4K() {
    var W = g.innerWidth || 1200;
    var is4K = W >= 2560;
    body.classList.toggle('sky-fui-4k', is4K);
  }

  function watchBrand() {
    var bar = d.querySelector('.sky-brand');
    syncBrandMeta();
    syncViewport4K();
    if (bar && !brandObs && g.MutationObserver) {
      brandObs = new g.MutationObserver(function () { syncBrandMeta(); });
      brandObs.observe(bar, { childList: true, subtree: true, characterData: true });
    }
  }

  var insetRO = null, insetTop = null, insetBottom = null;
  function publishInsets() {
    function put(id, token, value) {
      var el = $(id);
      if (el && value !== null && el.style.getPropertyValue(token) !== value) el.style.setProperty(token, value);
    }
    put('attach', '--sky-chrome-top', insetTop);
    put('runbar', '--sky-chrome-bottom', insetBottom);
    put('toast', '--sky-chrome-bottom', insetBottom);
    ['skyHud', 'skyDeconPanel', 'skySearchPanel', 'skyEnrichPanel'].forEach(function (id) { put(id, '--sky-chrome-top', insetTop); });
    put('skyHud', '--sky-chrome-bottom', insetBottom);
  }
  function watchInsets() {
    if (insetRO || !g.ResizeObserver) return;
    var bar = d.querySelector('.sky-top'), bot = d.querySelector('.sky-bottom');
    if (!bar && !bot) return;
    insetRO = new g.ResizeObserver(function () { syncInsets(); });
    if (bar) insetRO.observe(bar);
    if (bot) insetRO.observe(bot);
  }
  function syncInsets() {
    var bar = d.querySelector('.sky-top'), bot = d.querySelector('.sky-bottom'), H = g.innerHeight || 800;
    if (bar && bar.offsetHeight) insetTop = Math.round(bar.getBoundingClientRect().bottom) + 'px';
    if (bot) {
      var top = H;
      Array.prototype.forEach.call(bot.children, function (c) { if (c.hidden || !c.offsetHeight) return; top = Math.min(top, c.getBoundingClientRect().top); });
      insetBottom = Math.max(16, Math.round(H - top)) + 'px';
    }
    publishInsets();
  }
  function onBodyChange(records) {
    var classes = false, children = false;
    for (var i = 0; i < records.length; i++) {
      if (records[i].type === 'attributes') classes = true;
      else if (records[i].type === 'childList') children = true;
    }
    if (classes) syncMenuToBody();
    if (children) publishInsets();
  }

  /* ================================================================ 接线 */
  function onGraphReady() {
    leaveHome();
    setTimeout(function () { watchLegend(); syncMenuToBody(); syncInsets(); watchInsets(); watchBrand(); notifyIfEmptyGraph(); }, 0);
  }
  function emptyGraphWhat(G) {
    var nc = (G && G.characters && G.characters.length) || 0;
    var ne = (G && G.events && G.events.length) || 0;
    if (nc || ne) return '';
    return '这部作品没有角色，也没有事件：星图上不会有可读的内容。可回作品库另选一部，或导入包含角色与事件的图谱。';
  }
  function notifyIfEmptyGraph() {
    var A = app(); var G = A && A.graph && A.graph();
    var why = emptyGraphWhat(G);
    if (!why) return false;
    toast(why, 7000);
    return true;
  }
  d.addEventListener('cl:sky-plot', function () { if (!insetRO) setTimeout(syncInsets, 0); });
  d.addEventListener('cl:sky-compass', function () { if (!insetRO) setTimeout(syncInsets, 0); });
  d.addEventListener('cl:graph-ready', onGraphReady);
  d.addEventListener('cl:graph-error', function (e) { showError(e.detail || g.CLLoadError); });
  if (g.MutationObserver) new g.MutationObserver(onBodyChange).observe(body, { attributes: true, attributeFilter: ['class'], childList: true });
  g.addEventListener('keydown', onMenuKey, true);
  d.addEventListener('pointerdown', onPointerDown, true);
  g.addEventListener('resize', function () { if (menuOn) placeMenu(); syncInsets(); syncViewport4K(); });
  d.addEventListener('fullscreenchange', function () { if (menuOn) syncItems(); });
  if (!hasGraph()) enterHome(); else onGraphReady();

  g.CLSkyChrome = {
    VERSION: VERSION,
    enabled: function () { return true; },
    home: function () { return homeMode; },
    showError: showError,
    recent: function () { return homeItems.slice(0, 6).map(function (it) { return { key: it.key, title: it.display || it.title, characters: num(it.characters), chapters: num(it.chapters) }; }); },
    openWork: openWork,
    routeDrop: routeDrop,
    menuOpen: function () { return menuOn; },
    openMenu: openMenu,
    closeMenu: function () { return closeMenu(false); },
    legendHtml: legendHtml,
    refresh: function () { if (homeMode !== 'off') loadRecent(); decorateLegend(true); syncBrandMeta(); }
  };
})(window);

/* v91.2 · Pointer constellation: feeds only optical CSS variables.  No graph
 * coordinates, camera state, or hit targets are touched, so drag/keyboard
 * navigation keeps its existing ownership and precision. */
(function (g) {
  'use strict';
  var d = g.document;
  if (!d || !d.documentElement || !d.body) return;
  var raf = 0, px = .5, py = .42, reduced = false;
  var HUD = '#brand .panel,#ops,#index .panel,#overview .panel,.atlas-preview-hud .aph-shell';
  try { reduced = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) {}
  if (reduced || !g.addEventListener) return;
  function frame() {
    raf = 0;
    var st = d.getElementById('stage'), hud = d.querySelectorAll(HUD), hx = ((px - .5) * 8).toFixed(2) + 'px', hy = ((py - .42) * 5).toFixed(2) + 'px';
    if (st) { st.style.setProperty('--frontier-pointer-x', (px * 100).toFixed(2) + '%'); st.style.setProperty('--frontier-pointer-y', (py * 100).toFixed(2) + '%'); }
    for (var i = 0; i < hud.length; i++) { hud[i].style.setProperty('--frontier-hud-x', hx); hud[i].style.setProperty('--frontier-hud-y', hy); }
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
