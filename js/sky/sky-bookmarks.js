(function (g) {
  'use strict';
  var VERSION = '1';
  var PREFIX = 'castline.bookmarks.';
  var MAX_ITEMS = 50;
  var MAX_BYTES = 12288;
  var TITLE_MAX = 80;
  var NAME_MAX = 64;
  var VIEWS = { plot: 1, compass: 1, decode: 1 };
  var VIEW_LABEL = { plot: '星盘', compass: '罗盘', decode: '解构' };

  function storage() { try { return g.localStorage || null; } catch (e) { return null; } }
  function keyFor(workKey) { return PREFIX + String(workKey); }

  function intOrNull(v) { return typeof v === 'number' && isFinite(v) && Math.floor(v) === v && v >= 0 ? v : null; }
  function shortStr(v, max) { return typeof v === 'string' && v && v.length <= max ? v : null; }
  function sanitizeItem(input) {
    var it = input;
    if (typeof it === 'string') { try { it = JSON.parse(it); } catch (e) { return null; } }
    if (!it || typeof it !== 'object' || Array.isArray(it)) return null;
    var eventIndex = intOrNull(it.eventIndex); if (eventIndex === null) return null;
    var title = shortStr(it.title, TITLE_MAX); if (!title) return null;
    var view = VIEWS[it.view] ? it.view : null; if (!view) return null;
    var ref = null;
    if (view === 'compass') { ref = shortStr(it.ref, NAME_MAX); if (!ref) return null; }
    var at = intOrNull(it.at); if (at === null) return null;
    return { eventIndex: eventIndex, title: title, view: view, ref: ref, at: at };
  }
  function sanitize(input) {
    var rec = input;
    if (typeof rec === 'string') { try { rec = JSON.parse(rec); } catch (e) { return null; } }
    if (!rec || typeof rec !== 'object' || Array.isArray(rec)) return null;
    if (rec.v !== 1 || !Array.isArray(rec.items)) return null;
    var seen = {}, items = [], healed = false;
    rec.items.forEach(function (row) {
      var it = sanitizeItem(row);
      if (!it || seen[it.eventIndex] != null) { healed = true; return; }
      seen[it.eventIndex] = 1;
      items.push(it);
    });
    if (items.length > MAX_ITEMS) { items = items.slice(0, MAX_ITEMS); healed = true; }
    return { v: 1, items: items, healed: healed };
  }
  function encode(rec) {
    if (!rec || typeof rec !== 'object') return null;
    var s;
    try { s = JSON.stringify({ v: 1, items: rec.items }); } catch (e) { return null; }
    return s && s.length <= MAX_BYTES ? s : null;
  }
  function addDecision(items, item) {
    if (!item) return { ok: false, reason: 'invalid' };
    for (var i = 0; i < items.length; i++) if (items[i].eventIndex === item.eventIndex) return { ok: false, reason: 'exists' };
    if (items.length >= MAX_ITEMS) return { ok: false, reason: 'full' };
    return { ok: true, items: items.concat([item]) };
  }
  function plan(item, env) {
    if (!item || !env || typeof env.events !== 'number') return null;
    if (item.eventIndex < 0 || item.eventIndex >= env.events) return null;
    var ops = [{ op: 'locateEvent', index: item.eventIndex }];
    if (item.view === 'compass') {
      if (!env.chars || env.chars.indexOf(item.ref) < 0) return null;
      ops.push({ op: 'openCompass', name: item.ref });
    } else if (item.view === 'decode') {
      ops.push({ op: 'openDecode' });
    }
    return ops;
  }

  var S = storage();
  var alive = !!S;
  function store(fn) { if (!alive) return null; try { return fn(S); } catch (e) { alive = false; return null; } }
  function save(workKey, items) {
    var s = encode({ v: 1, items: items });
    if (!s) return false;
    return !!store(function (st) { st.setItem(keyFor(workKey), s); return true; });
  }
  function list(workKey) {
    if (!workKey) return [];
    var raw = store(function (s) { return s.getItem(keyFor(workKey)); });
    if (raw == null) return [];
    var rec = sanitize(raw);
    if (!rec) { store(function (s) { return s.removeItem(keyFor(workKey)); }); selfHeals++; return []; }
    if (rec.healed) { save(workKey, rec.items); selfHeals++; }
    return rec.items;
  }
  function has(workKey, eventIndex) {
    var items = list(workKey);
    for (var i = 0; i < items.length; i++) if (items[i].eventIndex === eventIndex) return items[i];
    return null;
  }
  function remove(workKey, eventIndex) {
    var items = list(workKey), next = items.filter(function (it) { return it.eventIndex !== eventIndex; });
    if (next.length === items.length) return false;
    return save(workKey, next);
  }
  function clear(workKey) { if (!workKey) return false; return !!store(function (s) { s.removeItem(keyFor(workKey)); return true; }); }

  /* ── 运行时接线（浏览器壳；纯函数区以上脱离 DOM 可跑） ── */
  var d = g.document;
  var selfHeals = 0, adds = 0, removes = 0, jumps = 0;
  var storyBtn = null, barBtn = null, listEl = null, liveEl = null, observerTg = 0;

  function app() { return g.CLApp || null; }
  function sky() { return g.CLSky || null; }
  function workKey() { var A = app(); return A && A.key ? A.key() : null; }
  function evTitle(eventIndex) {
    var A = app(), G = A && A.graph && A.graph(), e = G && G.events && G.events[eventIndex];
    if (!e) return null;
    var L = g.CLSkyEventLabel;
    var full = (L && L.eventLabel) ? L.eventLabel(e) : (shortStr(e.title || '', TITLE_MAX) || '未命名事件');
    return shortStr(full, TITLE_MAX) || '未命名事件';
  }
  function captureView() {
    var K = sky(), st = K && K.state ? K.state() : null;
    if (st && st.mode === 'compass' && shortStr(st.compass, NAME_MAX)) return { view: 'compass', ref: st.compass };
    if (d && d.body && d.body.classList.contains('sky-decon-on')) return { view: 'decode', ref: null };
    return { view: 'plot', ref: null };
  }
  function say(text) { if (liveEl) liveEl.textContent = text; }

  function doAdd(eventIndex) {
    var key = workKey(); if (!key) return false;
    var title = evTitle(eventIndex); if (!title) return false;
    var v = captureView();
    var item = sanitizeItem({ eventIndex: eventIndex, title: title, view: v.view, ref: v.ref, at: Date.now() });
    var decision = addDecision(list(key), item);
    if (!decision.ok) {
      say(decision.reason === 'full' ? '书签已满 50 条——删除一条旧书签，再收藏新位置'
        : decision.reason === 'exists' ? '本事件已在书签列表中' : '这条书签数据异常，未保存');
      return false;
    }
    if (!save(key, decision.items)) { say('书签保存失败（存储不可用）'); return false; }
    adds++;
    say('已收藏 · ' + title + ' · ' + VIEW_LABEL[item.view] + (item.view === 'compass' ? ' · ' + item.ref : ''));
    refresh();
    return true;
  }
  function doRemove(eventIndex) {
    var key = workKey(); var item = has(key, eventIndex);
    if (!item || !remove(key, eventIndex)) return false;
    removes++;
    say('已删除书签 · ' + item.title);
    refresh();
    return true;
  }
  function toggleCurrent() {
    var K = sky(), ps = K && K.playerState ? K.playerState() : null;
    if (!ps || !ps.panel || ps.eventIndex == null) return false;
    if (has(workKey(), ps.eventIndex)) return doRemove(ps.eventIndex);
    return doAdd(ps.eventIndex);
  }
  function env() {
    var A = app(), G = A && A.graph && A.graph();
    if (!G) return null;
    return { events: (G.events || []).length, chars: (G.characters || []).map(function (c) { return c.name; }) };
  }
  function exec(ops) {
    var K = sky(); if (!K) return false;
    for (var i = 0; i < ops.length; i++) {
      var o = ops[i];
      try {
        if (o.op === 'locateEvent') { if (!(K.locateEvent ? K.locateEvent(o.index) : K.seekEventAt(o.index))) return false; }
        else if (o.op === 'openCompass') K.openCompass(o.name);
        else if (o.op === 'openDecode') { if (g.CLSkyDeconstruction && CLSkyDeconstruction.open) CLSkyDeconstruction.open(); }
        else return false;
      } catch (e) { return false; }
    }
    return true;
  }
  function jump(eventIndex) {
    var key = workKey(); if (!key) return false;
    var item = has(key, eventIndex);
    if (!item) { say('没有找到这条书签'); return false; }
    var ops = plan(item, env());
    if (!ops) {
      remove(key, eventIndex); selfHeals++;
      say('这条书签指向的内容已不在当前图谱，已移除');
      refresh();
      return false;
    }
    if (!exec(ops)) { say('跳读失败——请手动用定位轨或事件阅读回到该事件'); return false; }
    jumps++;
    closeList();
    return true;
  }

  function setText(el, t) { if (el.textContent !== t) el.textContent = t; }
  function setAttr(el, name, v) { if (el.getAttribute(name) !== v) el.setAttribute(name, v); }
  function syncStoryBtn() {
    if (!storyBtn) return;
    var K = sky(), ps = K && K.playerState ? K.playerState() : null;
    var key = workKey();
    var idx = ps && ps.panel && ps.eventIndex != null ? ps.eventIndex : null;
    if (idx == null || !key) {
      storyBtn.disabled = true;
      setAttr(storyBtn, 'aria-pressed', 'false');
      setText(storyBtn, '收藏此事件');
      setAttr(storyBtn, 'aria-label', key ? '收藏此事件' : '收藏此事件（示例作品无独立存储，不可用）');
      return;
    }
    storyBtn.disabled = false;
    var saved = has(key, idx);
    setAttr(storyBtn, 'aria-pressed', String(!!saved));
    setText(storyBtn, saved ? '已收藏' : '收藏此事件');
    setAttr(storyBtn, 'aria-label', (saved ? '已收藏 · 点按取消收藏 · ' : '收藏此事件 · ') + (ps.eventId != null ? (evTitle(idx) || '未命名事件') : '未命名事件'));
  }
  function mountStoryBtn() {
    if (!d) return;
    var panel = d.getElementById('skyStoryPanel'); if (!panel) return;
    var actions = panel.querySelector('.ssp-actions'); if (!actions) return;
    if (!storyBtn || storyBtn.parentNode !== actions) {
      storyBtn = d.createElement('button');
      storyBtn.type = 'button';
      storyBtn.setAttribute('data-cl', 'bm-toggle');
      storyBtn.addEventListener('click', function () { toggleCurrent(); syncStoryBtn(); });
      actions.appendChild(storyBtn);
    }
    syncStoryBtn();
  }

  function syncBarBtn(count) {
    if (!barBtn) return;
    barBtn.textContent = '书签' + (count ? ' ' + count : '');
    barBtn.setAttribute('aria-label', '事件书签 · 打开收藏列表（' + count + ' 条 · 上限 ' + MAX_ITEMS + '）');
  }
  function mountBarBtn() {
    if (!d || barBtn) return;
    var follow = d.getElementById('skyFollow'); if (!follow || !follow.parentNode) return;
    barBtn = d.createElement('button');
    barBtn.type = 'button'; barBtn.id = 'clBmToggle'; barBtn.className = 'sky-speed';
    barBtn.setAttribute('aria-expanded', 'false'); barBtn.setAttribute('aria-controls', 'clBookmarks');
    follow.parentNode.insertBefore(barBtn, follow.nextSibling);
    barBtn.addEventListener('click', function () { toggleList(); });
    syncBarBtn(list(workKey()).length);
  }
  function fmtTime(at) {
    var dt = new Date(at);
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return p(dt.getMonth() + 1) + '-' + p(dt.getDate()) + ' ' + p(dt.getHours()) + ':' + p(dt.getMinutes());
  }
  function viewTag(item) { return VIEW_LABEL[item.view] + (item.view === 'compass' ? ' · ' + item.ref : ''); }
  function renderList() {
    if (!listEl) return;
    var ul = listEl.querySelector('.cl-bm-list'), head = listEl.querySelector('.cl-bm-head h2');
    var items = list(workKey());
    if (head) head.textContent = '事件书签 · ' + items.length + ' / ' + MAX_ITEMS;
    var html = '';
    if (!items.length) {
      html = '<li class="cl-bm-empty">还没有事件书签。阅读事件时点阅读面板底排的「收藏此事件」，这里就能随时跳回那个位置。</li>';
    } else {
      html = items.map(function (it) {
        return '<li class="cl-bm-item">' +
          '<button type="button" class="cl-bm-jump" data-bm-i="' + it.eventIndex + '" aria-label="跳转到书签 · ' + esc(it.title) + '">' +
          esc(it.title) + '<small>' + esc(viewTag(it)) + ' · ' + fmtTime(it.at) + '</small></button>' +
          '<button type="button" class="cl-bm-del" data-bm-d="' + it.eventIndex + '" aria-label="删除书签 · ' + esc(it.title) + '">×</button></li>';
      }).join('');
    }
    if (ul) ul.innerHTML = html;
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function mountList() {
    if (!d || listEl) return;
    var host = d.getElementById('skyHud') || d.body;
    listEl = d.createElement('aside');
    listEl.id = 'clBookmarks'; listEl.className = 'cl-bm'; listEl.hidden = true;
    listEl.setAttribute('role', 'region'); listEl.setAttribute('aria-label', '事件书签列表');
    listEl.innerHTML = '<div class="cl-bm-head"><h2>事件书签</h2></div><ul class="cl-bm-list"></ul><span id="clBmLive" class="ssp-live" role="status" aria-live="polite" aria-atomic="true"></span>';
    liveEl = listEl.querySelector('#clBmLive');
    listEl.addEventListener('click', function (e) {
      var t = e.target && e.target.closest ? e.target.closest('[data-bm-i],[data-bm-d]') : null;
      if (!t) return;
      var i = t.getAttribute('data-bm-i');
      if (i != null) jump(+i); else doRemove(+t.getAttribute('data-bm-d'));
    });
    listEl.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeList(true); } });
    host.appendChild(listEl);
    d.addEventListener('click', function (e) {
      if (listEl.hidden) return;
      if (e.target && e.target.closest && (e.target.closest('#clBookmarks') || e.target.closest('#clBmToggle'))) return;
      closeList();
    }, true);
    d.addEventListener('keydown', function (e) {
      if (!listEl.hidden && e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); closeList(true); }
    });
  }
  function openList() {
    mountList(); renderList();
    listEl.hidden = false;
    if (barBtn) barBtn.setAttribute('aria-expanded', 'true');
  }
  function closeList(refocus) {
    if (!listEl || listEl.hidden) return;
    listEl.hidden = true;
    if (barBtn) { barBtn.setAttribute('aria-expanded', 'false'); if (refocus) barBtn.focus(); }
  }
  function toggleList() { if (!listEl || listEl.hidden) openList(); else closeList(true); }

  function refresh() {
    syncBarBtn(list(workKey()).length);
    mountStoryBtn(); syncStoryBtn();
    if (listEl && !listEl.hidden) renderList();
  }

  var mo = null;
  function observe() {
    if (!d || !g.MutationObserver) return;
    var hudWatch = new g.MutationObserver(function () {
      var panel = d.getElementById('skyStoryPanel');
      if (panel && (!storyBtn || storyBtn.parentNode !== panel.querySelector('.ssp-actions'))) mountStoryBtn();
      if (!barBtn) mountBarBtn();
      if (panel) {
        if (mo) return;
        mo = new g.MutationObserver(function () { syncStoryBtn(); });
        mo.observe(panel, { attributes: true, attributeFilter: ['hidden'], childList: true, subtree: true, characterData: true });
      }
    });
    (function attach() { if (d.body) hudWatch.observe(d.body, { childList: true, subtree: true }); else setTimeout(attach, 200); })();
    mountBarBtn();
  }

  function wire() {
    if (!d) return;
    mountBarBtn(); mountList(); observe();
    d.addEventListener('cl:graph-ready', function () { setTimeout(refresh, 200); });
    d.addEventListener('cl:graph-loading', function () { closeList(); });
    refresh();
  }
  if (d) wire();

  g.CLSkyBookmarks = {
    VERSION: VERSION,
    PREFIX: PREFIX,
    MAX_ITEMS: MAX_ITEMS,
    MAX_BYTES: MAX_BYTES,
    keyFor: keyFor,
    list: list,
    has: has,
    count: function (workKey) { return list(workKey).length; },
    add: function (workKey, item) {
      var it = sanitizeItem(item); if (!it) return { ok: false, reason: 'invalid' };
      var decision = addDecision(list(workKey), it);
      if (!decision.ok) return { ok: false, reason: decision.reason };
      if (!save(workKey, decision.items)) return { ok: false, reason: 'storage' };
      return { ok: true, item: it };
    },
    remove: remove,
    clear: clear,
    toggleCurrent: toggleCurrent,
    jump: jump,
    openList: openList,
    closeList: closeList,
    refresh: refresh,
    probe: function () { return g.CLSkyResume && CLSkyResume.probe ? CLSkyResume.probe() : null; },
    stats: function () { return { storage: alive, adds: adds, removes: removes, jumps: jumps, selfHeals: selfHeals }; },
    pure: {
      sanitizeItem: sanitizeItem,
      sanitize: sanitize,
      encode: encode,
      addDecision: addDecision,
      plan: plan,
      viewLabel: VIEW_LABEL,
      intOrNull: intOrNull
    }
  };
})(typeof window !== 'undefined' ? window : this);
