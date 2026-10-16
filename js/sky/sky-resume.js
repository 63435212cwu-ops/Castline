(function (g) {
  'use strict';
  var VERSION = '1';
  var PREFIX = 'castline.resume.';
  var MAX_BYTES = 2048;
  var WRITE_GAP = 2000;
  var POLL_MS = 1500;
  var LABEL_MAX = 80;
  var NAME_MAX = 64, GROUP_MAX = 32;
  var VIEWS = { plot: 1, compass: 1 };
  var PLAYBACKS = { chapters: 1, events: 1 };

  function storage() { try { return g.localStorage || null; } catch (e) { return null; } }
  function keyFor(workKey) { return PREFIX + String(workKey); }

  function intOrNull(v) { return typeof v === 'number' && isFinite(v) && Math.floor(v) === v && v >= 0 ? v : null; }
  function shortStr(v, max) { return typeof v === 'string' && v && v.length <= max ? v : null; }
  function sanitize(input) {
    var rec = input;
    if (typeof rec === 'string') { try { rec = JSON.parse(rec); } catch (e) { return null; } }
    if (!rec || typeof rec !== 'object' || Array.isArray(rec)) return null;
    if (rec.v !== 1) return null;
    var view = VIEWS[rec.view] ? rec.view : null;
    if (!view) return null;
    var playback = PLAYBACKS[rec.playback] ? rec.playback : 'chapters';
    var at = intOrNull(rec.at); if (at === null) return null;
    var out = { v: 1, at: at, view: view, compass: null, group: null, playback: playback, cursor: null, eventIndex: null, label: '' };
    if (view === 'compass') {
      out.compass = shortStr(rec.compass, NAME_MAX);
      if (!out.compass) return null;
    } else {
      if (rec.cursor != null) { out.cursor = intOrNull(rec.cursor); if (out.cursor === null) return null; }
      if (rec.eventIndex != null) { out.eventIndex = intOrNull(rec.eventIndex); if (out.eventIndex === null) return null; }
    }
    if (rec.group != null) { out.group = shortStr(rec.group, GROUP_MAX); if (out.group === null) return null; }
    if (rec.label != null && !shortStr(rec.label, LABEL_MAX)) return null;
    out.label = shortStr(rec.label, LABEL_MAX) || '';
    return out;
  }
  function encode(rec) {
    if (!rec || typeof rec !== 'object') return null;
    var s;
    try { s = JSON.stringify(rec); } catch (e) { return null; }
    return s && s.length <= MAX_BYTES ? s : null;
  }
  function payloadOf(rec) {
    if (!rec) return '';
    return JSON.stringify({ v: 1, view: rec.view, compass: rec.compass, group: rec.group, playback: rec.playback, cursor: rec.cursor, eventIndex: rec.eventIndex, label: rec.label });
  }
  function shouldWrite(now, lastWriteAt, payload, lastPayload) {
    if (!payload) return 'skip';
    if (payload === lastPayload) return 'skip';
    return now - lastWriteAt >= WRITE_GAP ? 'write' : 'defer';
  }
  function labelOf(rec, ctx) {
    ctx = ctx || {};
    if (!rec) return '';
    if (rec.view === 'compass') return '罗盘 · ' + String(rec.compass || '').slice(0, LABEL_MAX);
    if (rec.eventIndex != null) {
      var t = shortStr(ctx.eventTitle, 96) || '';
      var cl = shortStr(ctx.chapterLabel, 64) || '';
      var s = (t || '未命名事件');
      return (cl ? cl + ' · ' : '') + s.slice(0, LABEL_MAX);
    }
    if (rec.cursor != null) return shortStr(ctx.chapterLabel, LABEL_MAX) || '星盘';
    return '星盘';
  }
  function plan(rec, env) {
    if (!rec || !env) return null;
    var ops = [];
    if (rec.group) {
      var okGroup = !env.groups || env.groups.indexOf(rec.group) >= 0;
      if (!okGroup) return null;
      if (rec.group !== 'camp') ops.push({ op: 'regroup', key: rec.group });
    }
    if (rec.view === 'compass') {
      if (env.chars && env.chars.indexOf(rec.compass) < 0) return null;
      ops.push({ op: 'openCompass', name: rec.compass });
      return ops;
    }
    ops.push({ op: 'playback', mode: rec.playback });
    if (rec.eventIndex != null) {
      if (!env.events || rec.eventIndex >= env.events) return null;
      ops.push({ op: 'seekEventAt', index: rec.eventIndex });
      return ops;
    }
    ops.push({ op: 'setPlot', on: true });
    if (rec.cursor != null) {
      if (!env.nCh || rec.cursor >= env.nCh) return null;
      ops.push({ op: 'seek', cursor: rec.cursor });
    }
    return ops;
  }
  function canonOf(state, player, dom) {
    state = state || {}; player = player || {}; dom = dom || {};
    var scrub = player.scrub || {};
    return {
      mode: state.mode || null, plot: !!state.plot, compass: state.compass || null, group: state.group || null,
      playing: !!state.playing, cursor: state.cursor == null ? null : state.cursor,
      player: {
        mode: player.mode || null, eventId: player.eventId || null,
        eventIndex: player.eventIndex == null ? null : player.eventIndex,
        position: player.position == null ? null : player.position, stage: player.stage || null,
        panel: !!player.panel, scrubNow: scrub.position == null ? null : scrub.position, scrubMax: scrub.total == null ? null : scrub.total
      },
      caption: typeof dom.caption === 'string' ? dom.caption : null,
      crumb: typeof dom.crumb === 'string' ? dom.crumb : null
    };
  }

  var S = storage();
  var alive = !!S;
  function store(fn) { if (!alive) return null; try { return fn(S); } catch (e) { alive = false; return null; } }
  function read(workKey) {
    if (!workKey) return null;
    var raw = store(function (s) { return s.getItem(keyFor(workKey)); });
    if (raw == null) return null;
    var rec = sanitize(raw);
    if (!rec) { store(function (s) { return s.removeItem(keyFor(workKey)); }); return null; }
    if (String(raw).length > MAX_BYTES) { store(function (s) { return s.removeItem(keyFor(workKey)); }); return null; }
    return rec;
  }
  function write(workKey, rec) {
    if (!workKey || !rec) return false;
    var s = encode(rec);
    if (!s) return false;
    return !!store(function (st) { st.setItem(keyFor(workKey), s); return true; });
  }
  function clear(workKey) { if (!workKey) return false; return !!store(function (s) { s.removeItem(keyFor(workKey)); return true; }); }

  /* ── 运行时接线（浏览器壳；纯函数区以上脱离 DOM 可跑） ── */
  var d = g.document;
  var lastWriteAt = -1e13, lastPayload = '', pendingPayload = null, pendingT = 0, pollT = 0;
  var resumePending = null, resumeSerial = 0, writeCount = 0, selfHeals = 0;

  function app() { return g.CLApp || null; }
  function sky() { return g.CLSky || null; }
  function workKey() { var A = app(); return A && A.key ? A.key() : null; }
  function chapterOf(M, i) {
    if (!M || !M.chapterEvents) return null;
    for (var c = 0; c < M.chapterEvents.length; c++) { var xs = M.chapterEvents[c]; if (xs && xs.indexOf(i) >= 0) return c; }
    return null;
  }
  function chapterLabel(M, c) {
    return g.CLSkyModel && g.CLSkyModel.chapterLabel ? g.CLSkyModel.chapterLabel(M, c) : null;
  }
  function capture() {
    var K = sky(), A = app();
    if (!K || !A || !K.model()) return null;
    var key = workKey(); if (!key) return null;
    var st = K.state(), ps = {}, M = K.model(), G = A.graph && A.graph();
    try { ps = K.playerState() || {}; } catch (eP) { ps = {}; }
    var rec = { v: 1, at: Date.now(), view: null, compass: null, group: null, playback: PLAYBACKS[ps.mode] ? ps.mode : 'chapters', cursor: null, eventIndex: null, label: '' };
    if (st.mode === 'compass' && shortStr(st.compass, NAME_MAX)) {
      rec.view = 'compass'; rec.compass = String(st.compass);
      rec.label = labelOf(rec, {});
    } else if (st.plot) {
      rec.view = 'plot';
      if (st.cursor != null) { rec.cursor = intOrNull(st.cursor); if (rec.cursor === null || rec.cursor >= (M.nCh || 0)) return null; }
      if (ps.eventIndex != null && ps.panel) {
        rec.eventIndex = intOrNull(ps.eventIndex);
        if (rec.eventIndex === null || !G || !G.events || rec.eventIndex >= G.events.length) return null;
        var c = chapterOf(M, rec.eventIndex), e = G.events[rec.eventIndex] || {};
        var lblApi = g.CLSkyEventLabel;
        var evName = (lblApi && lblApi.eventLabel) ? lblApi.eventLabel(e) : (e.title || e.name || '');
        rec.label = labelOf(rec, { chapterLabel: c != null ? chapterLabel(M, c) : null, eventTitle: evName });
      } else if (rec.cursor != null) {
        rec.label = labelOf(rec, { chapterLabel: chapterLabel(M, rec.cursor) });
      } else rec.label = labelOf(rec, {});
      if (rec.cursor == null && rec.eventIndex == null) {  }
    } else return null;
    if (shortStr(st.group, GROUP_MAX) && st.group !== 'camp') rec.group = st.group;
    var san = sanitize(rec); if (!san) return null;
    if (!encode(san)) return null;
    return san;
  }
  function writeNow() {
    var key = workKey(); if (!key) return false;
    var rec = capture(); if (!rec) return false;
    lastPayload = pendingPayload = payloadOf(rec);
    if (!write(key, rec)) return false;
    lastWriteAt = Date.now(); writeCount++;
    refresh();
    return true;
  }
  function tick() {
    if (!d) return;
    var key = workKey(); if (!key) return;
    var rec = capture(); if (!rec) return;
    var pay = payloadOf(rec);
    var act = shouldWrite(Date.now(), lastWriteAt, pay, lastPayload);
    if (act === 'skip') return;
    if (act === 'write') writeNow();
    else if (!pendingT) {
      pendingPayload = pay;
      pendingT = setTimeout(function () { pendingT = 0; pendingPayload = null; writeNow(); }, WRITE_GAP - (Date.now() - lastWriteAt) + 30);
    }
  }
  function flush() {
    if (pendingT) { clearTimeout(pendingT); pendingT = 0; pendingPayload = null; }
    var key = workKey(); if (!key) return;
    var rec = capture(); if (!rec) return;
    if (payloadOf(rec) === lastPayload) return;
    writeNow();
  }

  function env() {
    var K = sky(), A = app(), M = K && K.model(), G = A && A.graph && A.graph();
    if (!K || !M || !G) return null;
    return { nCh: M.nCh || 0, events: (G.events || []).length, chars: (G.characters || []).map(function (c) { return c.name; }), groups: (M.groupings || []).map(function (x) { return x.key; }) };
  }
  function exec(ops) {
    var K = sky(); if (!K) return false;
    for (var i = 0; i < ops.length; i++) {
      var o = ops[i];
      try {
        if (o.op === 'regroup') K.regroup(o.key);
        else if (o.op === 'playback') K.playback(o.mode);
        else if (o.op === 'setPlot') K.setPlot(o.on);
        else if (o.op === 'seek') K.seek(o.cursor);
        else if (o.op === 'seekEventAt') K.seekEventAt(o.index);
        else if (o.op === 'openCompass') K.openCompass(o.name);
        else return false;
      } catch (e) { return false; }
    }
    return true;
  }
  function applyRecord(workKeyIn) {
    if (workKey() !== workKeyIn) return false;
    var rec = read(workKeyIn);
    resumePending = null;
    if (!rec) return false;
    var ops = plan(rec, env());
    if (!ops || !exec(ops)) { clear(workKeyIn); selfHeals++; refresh(); return false; }
    refresh();
    return true;
  }
  function onGraphReady(e) {
    var key = e && e.detail && e.detail.key, serial = ++resumeSerial;
    var A = app(), graph = A && A.graph ? A.graph() : null;
    if (resumePending && key === resumePending) {
      resumePending = null;
      setTimeout(function () {
        var current = app();
        if (serial !== resumeSerial || workKey() !== key || !current || !current.graph || current.graph() !== graph) return;
        applyRecord(key);
      }, 120);
    } else resumePending = null;
  }
  function openResume(workKeyIn) {
    if (!read(workKeyIn)) return false;
    resumeSerial++; resumePending = workKeyIn;
    var keySel = String(workKeyIn).replace(/"/g, '');
    var btn = d && d.querySelector('#libList .lbc[data-key="' + keySel + '"] .acts [data-act="open"]') ||
      d && d.querySelector('#histList .hist[data-key="' + keySel + '"]');
    if (btn) { btn.click(); return true; }
    if (g.CLSkyChrome && CLSkyChrome.openWork) { CLSkyChrome.openWork(workKeyIn); return true; }
    resumePending = null;
    return false;
  }

  function entryText(rec) { return '继续上次 · ' + (rec.label || '上次位置'); }
  function syncButton(btn, key, workTitle) {
    var rec = read(key);
    if (!rec) { if (btn) btn.remove(); return; }
    if (!btn) return;
    var text = entryText(rec);
    if (btn.textContent !== text) btn.textContent = text;
    var aria = '继续上次：' + (workTitle || '') + ' · ' + text;
    if (btn.getAttribute('aria-label') !== aria) btn.setAttribute('aria-label', aria);
  }
  function decorateHome() {
    if (!d) return;
    var row = d.getElementById('skyHomeRow'); if (!row) return;
    Array.prototype.forEach.call(row.querySelectorAll('.sh-li'), function (li) {
      var star = li.querySelector('.sh-work'); if (!star) return;
      var key = star.getAttribute('data-key');
      var btn = li.querySelector('.cl-resume-star');
      if (!key) { if (btn) btn.remove(); return; }
      if (read(key) && !btn) {
        btn = d.createElement('button');
        btn.type = 'button'; btn.className = 'cl-resume-star'; btn.setAttribute('data-key', key);
        li.appendChild(btn);
      }
      syncButton(btn, key, (star.querySelector('.sh-work-t') || {}).textContent || '');
    });
  }
  function decorateLib() {
    if (!d) return;
    var list = d.getElementById('libList'); if (!list) return;
    Array.prototype.forEach.call(list.querySelectorAll('.lbc'), function (card) {
      var key = card.getAttribute('data-key'); if (!key) return;
      var acts = card.querySelector('.acts'); if (!acts) return;
      var btn = acts.querySelector('.cl-resume');
      if (read(key) && !btn) {
        btn = d.createElement('button');
        btn.type = 'button'; btn.className = 'cl-resume'; btn.setAttribute('data-key', key);
        acts.insertBefore(btn, acts.firstChild ? acts.firstChild.nextSibling : null);
      }
      syncButton(btn, key, (card.querySelector('.lbc-h .t') || {}).textContent || '');
    });
  }
  function refresh() { decorateHome(); decorateLib(); }
  function watch() {
    if (!d || !g.MutationObserver) return;
    var row = d.getElementById('skyHomeRow'), list = d.getElementById('libList');
    if (row) new g.MutationObserver(function () { decorateHome(); }).observe(row, { childList: true });
    if (list) new g.MutationObserver(function () { decorateLib(); }).observe(list, { childList: true });
  }
  function onClick(e) {
    var t = e.target && e.target.closest ? e.target.closest('.cl-resume, .cl-resume-star') : null;
    if (!t) return;
    var key = t.getAttribute('data-key'); if (!key) return;
    e.preventDefault(); e.stopPropagation();
    openResume(key);
  }

  var wired = false;
  function wire() {
    if (wired || !d || !g.addEventListener) return;
    wired = true;
    d.addEventListener('click', onClick, true);
    d.addEventListener('cl:graph-ready', onGraphReady);
    d.addEventListener('cl:graph-loading', function (e) { var s = e && e.detail && e.detail.stage; if (s === 'fetch' || s === 'error') { resumeSerial++; flush(); if (s === 'error') resumePending = null; } });
    g.addEventListener('pagehide', flush);
    g.addEventListener('beforeunload', flush);
    watch(); refresh();
    pollT = setInterval(tick, POLL_MS);
  }
  if (d) wire();

  g.CLSkyResume = {
    VERSION: VERSION,
    PREFIX: PREFIX,
    MAX_BYTES: MAX_BYTES,
    WRITE_GAP: WRITE_GAP,
    keyFor: keyFor,
    read: read,
    write: write,
    clear: clear,
    capture: capture,
    flush: flush,
    openResume: openResume,
    refresh: refresh,
    pending: function () { return resumePending; },
    stats: function () { return { storage: alive, writes: writeCount, selfHeals: selfHeals, lastWriteAt: lastWriteAt, polling: !!pollT }; },
    probe: function () {
      var K = sky();
      var st = K && K.state ? K.state() : null;
      var ps = null; try { ps = K && K.playerState ? K.playerState() : null; } catch (eP) { ps = null; }
      var capEl = d && d.getElementById('skyCaption'), crumbEl = d && d.getElementById('skyCrumbName');
      return canonOf(st, ps, {
        caption: capEl ? capEl.textContent : null,
        crumb: crumbEl && d.getElementById('skyCrumb') && !d.getElementById('skyCrumb').hidden ? crumbEl.textContent : null
      });
    },
    statsLabel: labelOf,
    pure: {
      sanitize: sanitize,
      encode: encode,
      payloadOf: payloadOf,
      shouldWrite: shouldWrite,
      labelOf: labelOf,
      plan: plan,
      canonOf: canonOf,
      intOrNull: intOrNull
    }
  };
})(typeof window !== 'undefined' ? window : this);
