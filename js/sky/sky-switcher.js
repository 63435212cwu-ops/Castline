(function (root) {
  'use strict';
  var VERSION = 'castline/sky-switcher/1';

  function orderWorks(items) {
    return (items || []).filter(function (it) { return !!(it && it.key); }).slice().sort(function (a, b) {
      return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0)
        || String(b.at || '').localeCompare(String(a.at || ''))
        || String(a.key || '').localeCompare(String(b.key || ''));
    });
  }

  function scopeOf(it) {
    it = it || {};
    var docs = Array.isArray(it.docs) ? it.docs : [];
    var docChars = 0, kinds = [];
    docs.forEach(function (d) {
      var c = Math.round(+(d && d.chars) || 0);
      if (c > 0) docChars += c;
      var k = d && (d.kind || d.name);
      if (k && kinds.indexOf(String(k)) < 0) kinds.push(String(k));
    });
    var total = Math.round(+(it.chars) || 0);
    return {
      materials: docs.length,
      kinds: kinds,
      docChars: docChars || null,
      totalChars: total || null,
      charsMatch: (docChars && total) ? docChars === total : null,
      chapters: Math.round(+(it.chapters) || 0) || null,
      events: Math.round(+(it.events) || 0) || null,
      characters: Math.round(+(it.characters) || 0) || null,
      chunkCount: Math.round(+(it.chunks) || 0) || null
    };
  }
  function gapsOf(it) {
    it = it || {};
    var q = (it.quality && typeof it.quality === 'object') ? it.quality : null;
    var num = function (v) { var n = Math.round(+v); return isFinite(n) && n > 0 ? n : 0; };
    var failed = num(it.failed_chunks);
    var pending = num(it.pending);
    var flags = q ? num(q.audit_flags) : 0;
    var known = ('failed_chunks' in it) || ('pending' in it) || !!q;
    return {
      known: known,
      failedChunks: failed,
      pending: pending,
      auditFlags: flags,
      notes: {
        failedChunks: '切分/分析失败的块数（0 = 记录里没有失败块）',
        pending: '待处理项（不等于失败；需看记录）',
        auditFlags: '审计标记数'
      },
      total: failed + flags,
      any: (failed + flags) > 0
    };
  }
  function whyDefault(it, order) {
    it = it || {};
    if (it.pinned) return '你把它置顶了';
    var at = String(it.at || '');
    var sameAt = (order || []).filter(function (x) { return String(x.at || '') === at; }).length;
    var kindZh = { assistant_review: '代理核验版', source_review: '引文核对版',
      model_enrichment: '结构补析版', original: '原分析版' }[it.versionKind] || '版本性质未提供';
    if (sameAt > 1) {
      return '置顶优先 → 分析时间倒序 → 同一时间下按作品键定序（本次同时间有 ' + sameAt
        + ' 条，故键参与定序；' + kindZh + '）。刻意不比事件数。';
    }
    return '置顶优先 → 最近分析（' + (at || '时间未提供') + '；' + kindZh + '）。刻意不比事件数。';
  }
  function countOf(v) { v = Math.round(+v || 0); return v > 0 && isFinite(v) ? v : 0; }
  function entryOf(it, currentKey) {
    if (!it || !it.key) return null;
    var key = String(it.key);
    return {
      key: key,
      title: String(it.display || it.title || '未命名'),
      current: !!currentKey && key === String(currentKey),
      probe: 'ok',
      characters: countOf(it.characters),
      chapters: countOf(it.chapters)
    };
  }
  function listFor(items, currentKey) {
    return orderWorks(items).map(function (it) { return entryOf(it, currentKey); }).filter(Boolean);
  }
  function markUnavailable(entries, key, state) {
    var hit = false;
    (entries || []).forEach(function (e) {
      if (e && e.key === String(key)) { e.probe = state === 'lost' ? 'lost' : 'down'; hit = true; }
    });
    return hit;
  }
  function itemNote(e) {
    if (!e) return '';
    if (e.probe === 'down') return '数据不可用 · 缓存文件缺失或已损坏';
    if (e.probe === 'lost') return '数据不可用 · 本地服务未响应';
    var parts = [];
    if (e.characters) parts.push(e.characters + ' 角色');
    if (e.chapters) parts.push(e.chapters + ' 章');
    return parts.length ? parts.join(' · ') : '——';
  }
  function failOf(e) {
    return { kind: (e && e.clKind) || 'net', status: (e && e.clStatus) || 0, message: String((e && e.message) || e) };
  }

  var g = root && root.document ? root : null;
  if (!g) {
    var api0 = { version: VERSION, listFor: listFor, orderWorks: orderWorks, entryOf: entryOf, markUnavailable: markUnavailable, itemNote: itemNote, failOf: failOf, scopeOf: scopeOf, gapsOf: gapsOf, whyDefault: whyDefault };
    if (typeof module !== 'undefined' && module.exports) module.exports = api0;
    return;
  }
  var d = g.document, body = d.body, esc = g.CLSkyUtil && g.CLSkyUtil.esc ? g.CLSkyUtil.esc : function (t) { return String(t == null ? '' : t); };
  var ENABLED = (function () {
    if (g.CLSky && typeof g.CLSky.enabled === 'function') return !!g.CLSky.enabled();
    try { var q = new URLSearchParams(g.location.search); if (q.get('shell') === 'atlas') return false; if (q.get('shell') === 'sky' || q.get('sky')) return true; return q.get('probe') !== '1'; } catch (e) { return true; }
  })();

  var panel = null, failPanel = null, entries = [], currentKeyCache = '', openGen = 0;
  var pending = null, lastFail = null, prevFocus = null, netErr = null;
  var activeScope = null, activeProbeCount = 0, MAX_PROBE_CONCURRENCY = 4;

  function app() { return g.CLApp || null; }
  function key() { var A = app(); return A && A.key ? A.key() : null; }
  function hasGraph() { var A = app(); try { return !!(A && A.graph && A.graph()); } catch (e) { return false; } }
  function toast(t, ms) { var A = app(); if (A && A.toast) A.toast(t, ms); }
  function cacheUrl(k) { return 'data/cache/' + String(k).replace(/[^0-9a-zA-Z_-]/g, '') + '.json'; }
  function scopeCurrent(scope) { return !!scope && activeScope === scope && !scope.cancelled; }
  function cancelScope(scope) {
    scope = scope || activeScope;
    if (!scope || scope.cancelled) return false;
    scope.cancelled = true;
    scope.queue.length = 0;
    if (activeScope === scope) activeScope = null;
    if (scope.controller && !scope.abortSent) {
      scope.abortSent = true;
      try { scope.controller.abort(); } catch (e) {}
    }
    return true;
  }
  function beginScope() {
    cancelScope();
    var Controller = typeof g.AbortController === 'function' ? g.AbortController : null;
    var scope = { gen: ++openGen, cancelled: false, abortSent: false, queue: [], active: 0,
                  controller: Controller ? new Controller() : null };
    activeScope = scope;
    return scope;
  }
  function finishProbe(scope) {
    scope.active = Math.max(0, scope.active - 1);
    activeProbeCount = Math.max(0, activeProbeCount - 1);
    if (scopeCurrent(scope)) pumpProbeQueue(scope);
    else if (activeScope) pumpProbeQueue(activeScope);
  }
  function startProbe(scope, entry) {
    var done = false;
    scope.active++; activeProbeCount++;
    var options = { method: 'HEAD', cache: 'no-store' };
    if (scope.controller) options.signal = scope.controller.signal;
    function finish() { if (done) return; done = true; finishProbe(scope); }
    function markDown(response) {
      if (!scopeCurrent(scope) || !panel || panel.hidden || response.ok) return;
      if (markUnavailable(entries, entry.key, 'down')) renderList();
    }
    function markLost() {
      if (!scopeCurrent(scope) || !panel || panel.hidden) return;
      if (markUnavailable(entries, entry.key, 'lost')) renderList();
    }
    try {
      Promise.resolve(g.fetch(cacheUrl(entry.key), options)).then(markDown, markLost).then(finish, finish);
    } catch (err) { markLost(); finish(); }
  }
  function pumpProbeQueue(scope) {
    if (!scopeCurrent(scope)) return;
    while (activeProbeCount < MAX_PROBE_CONCURRENCY && scope.queue.length && scopeCurrent(scope)) {
      startProbe(scope, scope.queue.shift());
    }
  }

  function buildPanel() {
    if (panel) return panel;
    panel = d.createElement('section');
    panel.id = 'skySwitcher'; panel.className = 'sky-switch-panel'; panel.hidden = true;
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'false'); panel.setAttribute('aria-labelledby', 'skySwitchH');
    panel.innerHTML =
      '<div class="sws-head"><h2 id="skySwitchH">换作品</h2><button type="button" class="sws-close" id="skySwitchClose" aria-label="关闭换作品面板（Esc）">×</button></div>' +
      '<div class="sws-scroll"><ol class="sws-list" id="skySwitchList"></ol>' +
      '<p class="sws-note" id="skySwitchNote" hidden></p></div>';
    body.appendChild(panel);
    d.getElementById('skySwitchClose').addEventListener('click', function () { close(true); });
    panel.querySelector('.sws-list').addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('.sws-item') : null;
      if (!b || b.getAttribute('aria-disabled') === 'true') return;
      var ent = entries[+b.getAttribute('data-i')];
      choose(ent);
    });
    return panel;
  }
  function buildFail() {
    if (failPanel) return failPanel;
    failPanel = d.createElement('section');
    failPanel.id = 'skySwitchFail'; failPanel.className = 'sky-switch-fail'; failPanel.hidden = true;
    failPanel.setAttribute('role', 'alert'); failPanel.setAttribute('aria-labelledby', 'skySwitchFailH');
    failPanel.innerHTML =
      '<h2 id="skySwitchFailH" class="sws-fail-h">没能换到《<span id="skySwitchFailT"></span>》</h2>' +
      '<p class="sws-fail-why" id="skySwitchFailWhy"></p>' +
      '<p class="sws-fail-src" id="skySwitchFailSrc"></p>' +
      '<details class="sws-fail-tech" id="skySwitchFailTech"><summary>技术细节</summary><p class="sws-fail-detail" id="skySwitchFailDetail"></p></details>' +
      '<div class="sws-fail-acts">' +
        '<button type="button" class="sws-btn is-primary" id="skySwitchFailBack">返回原作品</button>' +
        '<button type="button" class="sws-btn" id="skySwitchFailRetry">重试</button>' +
        '<button type="button" class="sws-btn" id="skySwitchFailLib">返回作品库</button>' +
      '</div>';
    body.appendChild(failPanel);
    d.getElementById('skySwitchFailBack').addEventListener('click', backToOrigin);
    d.getElementById('skySwitchFailRetry').addEventListener('click', retryFail);
    d.getElementById('skySwitchFailLib').addEventListener('click', function () { hideFail(); var b = d.getElementById('btnLib'); if (b) b.click(); });
    return failPanel;
  }

  function renderList() {
    var ol = d.getElementById('skySwitchList'); if (!ol) return;
    ol.innerHTML = entries.map(function (e, i) {
      var down = e.probe !== 'ok';
      return '<li><button type="button" class="sws-item' + (e.current ? ' is-current' : '') + (down ? ' is-down' : '') + '"' +
        ' data-i="' + i + '"' + (down ? ' aria-disabled="true"' : '') + (e.current ? ' aria-current="true"' : '') +
        ' aria-describedby="swsD-' + i + '">' +
        '<span class="sws-item-t">' + esc(e.title) + (e.current ? '<span class="sws-cur">当前</span>' : '') + '</span>' +
        '<span class="sws-item-m" id="swsD-' + i + '">' + esc(itemNote(e)) + '</span></button></li>';
    }).join('');
  }
  function note(text) {
    var n = d.getElementById('skySwitchNote'); if (!n) return;
    n.textContent = text || ''; n.hidden = !text;
  }

  function probeAll(scope) {
    if (!scopeCurrent(scope)) return;
    scope.queue = entries.filter(function (e) { return e.probe === 'ok'; }).slice();
    pumpProbeQueue(scope);
  }

  function open() {
    if (!ENABLED || !hasGraph()) return false;
    var scope = beginScope();
    buildPanel(); buildFail(); hideFail();
    prevFocus = d.activeElement;
    netErr = null;
    panel.hidden = false;
    d.getElementById('skySwitchList').innerHTML = '';
    note('正在读取作品清单…');
    var options = scope.controller ? { signal: scope.controller.signal } : {};
    try {
      Promise.resolve(g.fetch('/api/history', options)).then(function (r) {
        if (!scopeCurrent(scope) || !panel || panel.hidden) return null;
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (dd) {
        if (!dd || !scopeCurrent(scope) || !panel || panel.hidden) return;
        currentKeyCache = key() || '';
        entries = listFor((dd && dd.items) || [], currentKeyCache);
        if (!entries.length) { netErr = 'empty'; note('作品库是空的 · 先导入一部小说'); return; }
        note('');
        renderList();
        probeAll(scope);
        var first = panel.querySelector('.sws-item:not(.is-down):not(.is-current)') || panel.querySelector('.sws-item');
        if (first && first.focus) first.focus({ preventScroll: true });
      }).catch(function () {
        if (!scopeCurrent(scope) || !panel || panel.hidden) return;
        netErr = 'fetch';
        note('作品清单取不到 · 本地服务可能已停止。恢复后重开此面板，或先「返回作品库」。');
      });
    } catch (e) {
      if (scopeCurrent(scope) && panel && !panel.hidden) {
        netErr = 'fetch';
        note('作品清单取不到 · 本地服务可能已停止。恢复后重开此面板，或先「返回作品库」。');
      }
    }
    return true;
  }
  function isOpen() { return !!(panel && !panel.hidden); }
  function close(refocus) {
    cancelScope();
    if (!panel || panel.hidden) return false;
    panel.hidden = true;
    if (refocus && prevFocus && prevFocus.focus && prevFocus.isConnected !== false) prevFocus.focus({ preventScroll: true });
    prevFocus = null;
    return true;
  }

  function choose(ent) {
    if (!ent || ent.probe !== 'ok') return false;
    if (ent.key === (key() || '')) { close(true); return true; }
    pending = { from: key(), to: ent.key, title: ent.title };
    close(false);
    if (g.CLSkyChrome && g.CLSkyChrome.openWork) g.CLSkyChrome.openWork(ent.key);
    return true;
  }

  function showFail(f) {
    buildFail();
    var BE = g.CLBootErrors || null, info = f.info || {};
    d.getElementById('skySwitchFailT').textContent = f.title || f.to || '';
    d.getElementById('skySwitchFailWhy').textContent = BE ? BE.why(info) : (info.message || '数据文件读取失败');
    d.getElementById('skySwitchFailSrc').textContent = info.src ? '地址：' + info.src : '';
    var det = d.getElementById('skySwitchFailDetail');
    if (det) det.textContent = BE ? BE.detail(info) : '';
    var tech = d.getElementById('skySwitchFailTech');
    if (tech) tech.hidden = !(BE && BE.detail(info));
    failPanel.hidden = false;
    var b = d.getElementById('skySwitchFailBack'); if (b && b.focus) b.focus({ preventScroll: true });
  }
  function hideFail() { if (failPanel && !failPanel.hidden) { failPanel.hidden = true; return true; } return false; }
  function failOpen() { return !!(failPanel && !failPanel.hidden); }
  function backToOrigin() {
    var f = lastFail; hideFail();
    if (!f || !f.from) return;
    var cur = key();
    if (cur === f.from) return;
    pending = { from: cur, to: f.from, title: '' };
    if (g.CLSkyChrome && g.CLSkyChrome.openWork) g.CLSkyChrome.openWork(f.from);
  }
  function retryFail() {
    var f = lastFail; hideFail();
    if (!f) return;
    pending = { from: f.from, to: f.to, title: f.title };
    if (g.CLSkyChrome && g.CLSkyChrome.openWork) g.CLSkyChrome.openWork(f.to);
  }

  d.addEventListener('cl:graph-loading', function (event) {
    if (event && event.detail && event.detail.stage === 'fetch') close(false);
  });
  d.addEventListener('cl:work-open-error', function (e) {
    var info = e && e.detail ? e.detail : {};
    if (!pending || info.key !== pending.to) return;
    lastFail = { from: pending.from, to: pending.to, title: pending.title, info: info };
    pending = null;
    showFail(lastFail);
  });
  d.addEventListener('cl:graph-ready', function (e) {
    if (pending && e && e.detail && e.detail.key === pending.to) pending = null;
    hideFail();
  });
  d.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (hideFail()) { e.preventDefault(); e.stopPropagation(); return; }
    if (close(true)) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  d.addEventListener('pointerdown', function (e) {
    var t = e.target;
    if (failOpen() && failPanel && !failPanel.contains(t)) hideFail();
    if (isOpen() && panel && !panel.contains(t)) close(false);
  }, true);

  var api = {
    VERSION: VERSION,
    enabled: function () { return ENABLED; },
    open: open,
    close: function (refocus) { return close(!!refocus); },
    isOpen: isOpen,
    failOpen: failOpen,
    pending: function () { return pending ? { from: pending.from, to: pending.to, title: pending.title } : null; },
    lastFail: function () {
      if (!lastFail) return null;
      return { from: lastFail.from, to: lastFail.to, title: lastFail.title, kind: lastFail.info.kind, status: lastFail.info.status };
    },
    entries: function () { return entries.map(function (e) { return { key: e.key, title: e.title, current: e.current, probe: e.probe }; }); },
    listFor: listFor, orderWorks: orderWorks, entryOf: entryOf, markUnavailable: markUnavailable, itemNote: itemNote, failOf: failOf,
    scopeOf: scopeOf, gapsOf: gapsOf, whyDefault: whyDefault
  };
  g.CLSkySwitcher = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this);
