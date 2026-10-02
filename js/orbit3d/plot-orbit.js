/* Castline · js/orbit3d/plot-orbit.js — v46「圆形剧情星盘」核心（window.CLPlotOrbit）
 * @role component · @owns js/orbit3d/plot-orbit.js · @budget js_ms<=2 (pure compute) · @contract v46+v47
 * 唯一职责：把 tree.events / tree.threads 投影成同一圆盘坐标上的一份几何数据。
 *   - 事件节点、主线/支线弧、共享事件 occurrence、角色参与连接与双向索引。
 *   - 环半径复用既有星座外圈约定（rimR/rimV/ROAD_PITCH），不新建第二套圆盘。
 * 设计约束：ES5 + IIFE + 'use strict'；确定性（不用随机）；纯数据（Node 下无 THREE/DOM）。
 * 可访问性接线集中在本文件末尾 wire()，Node 环境守空跳过，不参与几何计算。
 */
(function () {
  'use strict';

  var NAME = 'plot-orbit';
  var VERSION = 'v46.0';
  var TAU = Math.PI * 2;
  var PITCH = 0.46;          /* 与 constellation layout 的 ROAD_PITCH 对齐 */
  var RING_EVENT = 1.0;      /* 主线基准环 = 最外剧情环 = 事件时间环 */
  var RING_BRANCH_BASE = 0.86;
  var RING_BRANCH_STEP = 0.14;
  var RING_FLOOR = 0.42;

  var last = null;
  var lastStats = null;
  var lastLayout = null;
  var cache = { key: null, orbit: null, stats: null };

  /* ─────────────── 基础工具（守空、确定性） ─────────────── */
  function isObj(v) { return !!v && typeof v === 'object' && !isArr(v); }
  function isArr(v) { return Object.prototype.toString.call(v) === '[object Array]'; }
  function num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function str(v) { return v == null ? '' : String(v); }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function r6(v) { return Math.round(v * 1e6) / 1e6; }
  function nowMs() {
    try { if (typeof performance !== 'undefined' && performance && typeof performance.now === 'function') return performance.now(); } catch (e) {}
    return Date.now();
  }
  function attemptTree() {
    try { if (window.CLStory && typeof window.CLStory.analyze === 'function') return window.CLStory.analyze(window.graph || null, { strictTopology: true }); } catch (e) {}
    return null;
  }
  /* 仅取外圈半径/压扁/中心：CLTreePose 为冻结上游，CLPlotTree 已废弃不得引用。 */
  function runtimeFrame() {
    var f = { R: 240, ry: 0.74, pitch: PITCH, host: 'constellation-rim' };
    try {
      if (window.CLTreePose && typeof window.CLTreePose.stats === 'function') {
        var s = window.CLTreePose.stats() || {};
        if (num(s.rimR, 0) > 0) { f.R = s.rimR; }
      }
    } catch (e) {}
    return f;
  }
  function frameOf(opts) {
    var f = runtimeFrame(), o = (opts && opts.frame) || {};
    if (num(opts && opts.rimR, 0) > 0) f.R = opts.rimR;
    if (num(o.R, 0) > 0) f.R = o.R;
    if (num(o.ry, 0) > 0) f.ry = clamp(o.ry, 0.35, 1);
    if (num(o.pitch, 0) > 0) f.pitch = o.pitch;
    f.cx = num(o.cx, 0);
    f.cy = num(o.cy, 0);
    f.astro = num(o.astro, 1.015 * f.R);
    f.floor = num(o.floor, RING_FLOOR * f.R);
    return f;
  }

  /* 共享事件在同一环上按出现次序错开，避免 15 条支线在同一角度重叠。 */
  function pickCanon(k, seen, size) {
    var c = num(seen[k], 0);
    seen[k] = c + 1;
    return (Math.PI * 2 * c) / (size > 0 ? size : 1);
  }
  function angleFor(orderIndex, total) {
    var t = total > 0 ? (orderIndex / total) : 0;
    return r6(Math.PI / 2 - t * TAU + TAU);
  }
  function fpOf(parts) {
    var h = 2166136261, s = parts.join('|'), i;
    for (i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
    return ('0000000' + h.toString(16)).slice(-8);
  }
  function roundEvent(n) {
    return { evIdx: n.evIdx, order: n.order, kind: n.kind, chapter: n.chapter,
      lineCount: n.lineIds.length, ring: n.ring, angle: n.angle, r: n.r, x: n.x, y: n.y };
  }
  function statsSnapshot(o) {
    var s = { name: NAME, version: VERSION, fp: o.fp, mode: o.mode, ok: o.ok, reason: o.reason,
      events: o.events.length, lines: o.lines.length, roles: o.roles.length,
      unresolved: o.unresolved.length, rings: o.rings ? (2 + (isArr(o.rings.branch) ? o.rings.branch.length : 0)) : 0, ms: 0, host: o.host };
    return s;
  }
  function blank(tree, opts, reason, strict) {
    var o = { ok: false, reason: reason || 'no-tree', fp: '', mode: 'constellation',
      host: 'constellation-rim', strictTopology: strict,
      events: [], lines: [], eventLines: {}, lineEvents: {}, linesByEvent: {}, eventsByLine: {},
      eventToLines: {}, lineToEvents: {}, roles: [], eventRoles: {}, roleEvents: {}, roleLinks: [],
      unresolved: [], pending: [], eventAnchors: {}, orderToEv: {}, evOfOrder: {},
      rings: { event: null, main: null, tick: null, core: null, branch: [] }, timeRing: null, singleDisc: true, reusesConstellation: true,
      stars: { source: 'constellation', center: true, n: 0 } };
    last = o; lastStats = statsSnapshot(o); lastLayout = null;
    return o;
  }

  /* ─────────────── 几何构建（缓存命中时不重算） ─────────────── */
  function buildFrom(tree, opts, strict, frame) {
    var evs = isArr(tree.events) ? tree.events : [];
    var threads = isArr(tree.threads) ? tree.threads : [];
    var total = evs.length;

    /* 按 order 排序，保持顺时针时间语义；缺 order 时退回数组下标。 */
    var orderIdx = [];
    var i, j;
    for (i = 0; i < evs.length; i++) orderIdx.push(i);
    orderIdx.sort(function (a, b) {
      var oa = num(evs[a] && evs[a].order, a + 1), ob = num(evs[b] && evs[b].order, b + 1);
      return oa === ob ? (a - b) : (oa - ob);
    });
    var orderToEv = {}, evOfOrder = {}, byEv = {};
    for (i = 0; i < orderIdx.length; i++) { orderToEv[i + 1] = orderIdx[i]; evOfOrder[orderIdx[i]] = i + 1; }

    /* 每个事件落在事件环上的唯一角度。 */
    var angles = new Array(total);
    for (i = 0; i < orderIdx.length; i++) angles[orderIdx[i]] = angleFor(i, total);
    /* 预扫：每个事件被多少条真实线拥有，决定 isShared 与节点错开。 */
    var ownerCount = {};
    for (i = 0; i < threads.length; i++) {
      var tRaw = isArr(threads[i] && threads[i].events) ? threads[i].events : [], tSeen = {};
      for (j = 0; j < tRaw.length; j++) {
        var tev = num(tRaw[j], -1);
        if (tev < 0 || tSeen[tev]) continue;
        tSeen[tev] = 1; ownerCount[tev] = (ownerCount[tev] || 0) + 1;
      }
    }
    var counts = {}, eventLines = {}, eventCast = {};
    for (i = 0; i < evs.length; i++) {
      var e = evs[i] || {}, evIdx = num(e.i, i), li = [], cst = isArr(e.cast) ? e.cast : [], k;
      byEv[evIdx] = { i: i, order: num(e.order, i + 1), chapter: str(e.chapter), chapIdx: num(e.chapIdx, 0),
        kind: str(e.kind), title: str(e.title), summary: str(e.summary), quote: str(e.quote), w: num(e.w, 0),
        cast: cst, angle: num(angles[evIdx], angleFor(i, total)) };
      for (k = 0; k < cst.length; k++) eventCast[evIdx] = eventCast[evIdx] || {}, eventCast[evIdx][str(cst[k])] = true;
    }

    /* 支线同心环：按真实 depth 递进，主线统一落基准事件环。 */
    var lines = [], lineEvents = {}, byId = {};
    for (i = 0; i < threads.length; i++) {
      var t = threads[i] || {}, kind = str(t.kind), id = str(t.id) || ('T' + i);
      var raw = isArr(t.events) ? t.events : [];
      var clean = [], seenEv = {};
      for (j = 0; j < raw.length; j++) {
        var ei = num(raw[j], -1);
        if (ei < 0 || seenEv[ei]) continue;
        seenEv[ei] = 1; clean.push(ei);
      }
      var base;
      if (kind === 'main') base = frame.R * RING_EVENT;
      else base = Math.max(frame.floor, frame.R * (RING_BRANCH_BASE - RING_BRANCH_STEP * (Math.max(1, num(t.depth, 1)) - 1)));
      var occurrence = {}, occArr = [];
      for (j = 0; j < clean.length; j++) {
        var q = clean[j], qa = num(byEv[q] && byEv[q].angle, 0);
        var ent = { evIdx: q, occIndex: j, occCount: clean.length, n: clean.length,
          isShared: (ownerCount[q] || 0) > 1, angle: r6(qa),
          x: r6(base * Math.cos(qa)), y: r6(base * frame.ry * Math.sin(qa)), r: r6(base), radius: r6(base) };
        occurrence[q] = ent; occArr.push(ent);
      }
      var line = { id: id, sourceId: str(t.sourceId) || ('S' + (i + 1)), kind: kind, title: str(t.title),
        en: str(t.en), lead: str(t.lead), depth: num(t.depth, 0), len: clean.length,
        status: str(t.topologyStatus) || 'confirmed', resolved: t.resolved !== false, suspended: !!t.suspended,
        theme: str(t.theme), color: str(t.color), radius: r6(num(t.radius, base)),
        ring: kind === 'main' ? 'main' : 'branch',
        events: clean, occurrence: occurrence,
        parent: t.parent,
        attach: t.attach,
        declaredParent: t.declaredParent, declaredAttach: t.declaredAttach,
        pendingReason: str(t.pendingReason),
        arc: { rIn: r6(base), rOut: r6(base), rMid: r6(base), a0: num(angles[clean[0]], 0), a1: num(angles[clean[clean.length - 1]], 0) },
        cast: isArr(t.cast) ? t.cast : [] };
      var pts = [];
      for (j = 0; j < occArr.length; j++) {
        var oo = occArr[j];
        pts.push({ evIdx: oo.evIdx, angle: oo.angle, radius: oo.r, r: oo.r, x: oo.x, y: oo.y });
      }
      line.points = pts;
      lines.push(line); byId[id] = line;
      lineEvents[id] = clean.slice(0);
      for (j = 0; j < clean.length; j++) {
        var ev = clean[j];
        eventLines[ev] = eventLines[ev] || [];
        if (eventLines[ev].indexOf(id) < 0) eventLines[ev].push(id);
        counts[ev] = (counts[ev] || 0) + 1;
      }
    }

    /* 事件节点：同一角度的共享事件按落点错开，避免完全重合。 */
    var events = [], eventAnchors = {};
    for (i = 0; i < orderIdx.length; i++) {
      var idx = orderIdx[i], b = byEv[idx] || {};
      var seen = eventCast[idx] ? Object.keys(eventCast[idx]).length : 1;
      var size = Math.max(1, counts[idx] || 1);
      var shift = pickCanon(idx, {}, size);
      var ang = r6(num(b.angle, angleFor(i, total)) + (size > 1 ? shift * 0.5 : 0));
      var rr = frame.R * RING_EVENT;
      var u = Math.cos(ang), v = Math.sin(ang);
      var node = { evIdx: idx, i: idx, orderIndex: b.order, order: b.order, chapIdx: b.chapIdx, chapter: b.chapter,
        kind: b.kind, title: b.title, summary: b.summary, quote: b.quote, cast: b.cast, w: b.w,
        roleCount: seen, angle: ang, r: r6(rr), radius: r6(rr), u: r6(u), v: r6(v),
        x: r6(rr * u), y: r6(rr * frame.ry * v), ring: 'event',
        lineIds: isArr(eventLines[idx]) ? eventLines[idx].slice(0) : [] };
      events.push(node);
      eventAnchors[idx] = [node.x, node.y, 0];
    }

    /* rings：单盘对象。event 时间环与 main 主线环共用同一 R，branch 为同心支线环。 */
    var RR = r6(frame.R * RING_EVENT);
    var rings = {
      core: { name: 'core', kind: 'core', r: 0, radius: 0, ring: 'core' },
      event: { name: 'event', kind: 'time', r: RR, radius: RR, ring: 'event', count: total },
      main: { name: 'main', kind: 'main', r: RR, radius: RR, ring: 'main' },
      tick: { name: 'tick', kind: 'tick', r: r6(frame.floor), radius: r6(frame.floor), ring: 'tick' },
      branch: []
    };
    for (i = 0; i < lines.length; i++) {
      if (lines[i].kind === 'main') continue;
      rings.branch.push({ name: lines[i].id, kind: lines[i].kind, lineId: lines[i].id,
        r: r6(lines[i].arc.rMid), radius: r6(lines[i].arc.rMid), ring: lines[i].ring,
        depth: lines[i].depth, status: lines[i].status });
    }

    /* 角色参与连接与双向索引。 */
    var castMap = isObj(tree.cast) ? tree.cast : {};
    var roles = [], eventRoles = {}, roleEvents = {}, roleLinks = [];
    var names = Object.keys(castMap);
    for (i = 0; i < names.length; i++) {
      var nm = str(names[i]), role = castMap[names[i]] || {};
      var tids = isArr(role.threads) ? role.threads.slice(0) : [];
      var eis = isArr(role.events) ? role.events.slice(0) : [];
      roles.push({ name: nm, threads: tids, events: eis, main: !!role.main, w: num(role.w, 0) });
      roleEvents[nm] = eis;
      for (j = 0; j < eis.length; j++) {
        var evn = eis[j];
        eventRoles[evn] = eventRoles[evn] || [];
        if (eventRoles[evn].indexOf(nm) < 0) eventRoles[evn].push(nm);
        roleLinks.push({ name: nm, evIdx: evn });
      }
    }

    /* 待校对线：显式保留，不补造挂点。 */
    var unresolved = [], pending = [];
    var uarr = isArr(tree.unresolved) ? tree.unresolved : [];
    for (i = 0; i < uarr.length; i++) {
      var u = uarr[i] || {};
      var entry = { threadId: str(u.threadId), sourceId: str(u.sourceId), kind: str(u.kind),
        parent: str(u.parent), attach: str(u.attach), reasons: str(u.reasons || u.reason),
        events: isArr(u.events) ? u.events.slice(0) : [] };
      unresolved.push(entry); pending.push(entry);
    }

    var linesOut = [], lineEvents2 = {}, linesByEvent = {}, eventToLines = {}, lineToEvents = {};
    for (i = 0; i < lines.length; i++) {
      linesOut.push(lines[i]);
      lineEvents2[lines[i].id] = lineEvents[lines[i].id].slice(0);
      lineToEvents[lines[i].id] = lineEvents[lines[i].id].slice(0);
    }
    for (var ek in eventLines) {
      if (!Object.prototype.hasOwnProperty.call(eventLines, ek)) continue;
      linesByEvent[ek] = eventLines[ek].slice(0);
      eventToLines[ek] = eventLines[ek].slice(0);
    }

    var t0 = nowMs();
    var orbit = { ok: true, reason: '', fp: str(tree.fp) || fpOf(['tree', total, lines.length, names.length]),
      mode: 'constellation', host: 'constellation-rim', strictTopology: strict,
      version: VERSION, builtMs: 0,
      frame: { R: r6(frame.R), ry: r6(frame.ry), pitch: r6(frame.pitch), cx: frame.cx, cy: frame.cy },
      events: events, eventAnchors: eventAnchors, lines: linesOut,
      eventLines: eventLines, lineEvents: lineEvents2, linesByEvent: linesByEvent, eventsByLine: lineEvents2,
      eventToLines: eventToLines, lineToEvents: lineToEvents,
      roles: roles, eventRoles: eventRoles, roleEvents: roleEvents, roleLinks: roleLinks,
      unresolved: unresolved, pending: pending, rings: rings,
      timeRing: { name: 'time', radius: r6(frame.R * RING_EVENT), count: total },
      orderToEv: orderToEv, evOfOrder: evOfOrder,
      singleDisc: true, reusesConstellation: true,
      stars: { source: 'constellation', center: true, n: names.length } };
    orbit.builtMs = Math.round((nowMs() - t0) * 100) / 100;
    last = orbit; lastStats = statsSnapshot(orbit); lastLayout = null;
    return orbit;
  }

  /* ─────────────── 公开 API ─────────────── */
  function build(tree, opts) {
    opts = opts || {};
    if (tree == null) tree = attemptTree();
    var strict = opts.strictTopology !== false;
    if (!isObj(tree) || tree.ok !== true) return blank(tree, opts, 'no-tree', strict);
    var frame = frameOf(opts);
    var key = VERSION + '|' + str(tree.fp) + '|' + (strict ? 1 : 0) + '|' +
      r6(frame.R) + '/' + r6(frame.ry) + '/' + r6(frame.pitch);
    if (!opts.force && cache.key === key && cache.orbit) {
      last = cache.orbit; lastStats = cache.stats;
      return cache.orbit;
    }
    var orbit = buildFrom(tree, opts, strict, frame);
    cache.key = key; cache.orbit = orbit; cache.stats = lastStats;
    return orbit;
  }
  function get() { return last; }
  function stats() { return lastStats; }
  function invalidate() { cache.key = null; cache.orbit = null; cache.stats = null; lastLayout = null; }
  /* layout() 供渲染层消费；几何不变时返回同一对象，稳定帧不重建。 */
  function layout() {
    if (lastLayout) return lastLayout;
    var o = last;
    if (!o) return null;
    lastLayout = { mode: o.mode, host: o.host, fp: o.fp, frame: o.frame,
      rings: o.rings, events: o.events, lines: o.lines, timeRing: o.timeRing };
    return lastLayout;
  }
  function eventAt(ev) {
    var o = last; if (!o) return null;
    var e = Math.floor(num(ev, -1));
    for (var i = 0; i < o.events.length; i++) if (o.events[i].evIdx === e) return o.events[i];
    return null;
  }
  function threadAt(id) {
    var o = last; if (!o) return null;
    var s = str(id);
    for (var i = 0; i < o.lines.length; i++) if (str(o.lines[i].id) === s || str(o.lines[i].sourceId) === s) return o.lines[i];
    return null;
  }
  function participation(ev) {
    var o = last; if (!o) return null;
    var e = Math.floor(num(ev, -1));
    return { evIdx: e, roles: (o.eventRoles[e] || []).slice(0), lines: (o.eventLines[e] || []).slice(0) };
  }
  function clear() { last = null; lastStats = null; lastLayout = null; cache = { key: null, orbit: null, stats: null }; }

  /* ─────────────── 可访问性 / 键盘接线 ───────────────
   * 供渲染层 wire() 调用；Node 无 document 时直接跳过，不产生副作用、不建第二套几何。
   * 选择结果一律回落到 CLTreeEvents.pick，保证与事件卡入口同源。 */
  var KEYMAP = { prev: ['ArrowLeft', 'ArrowUp'], next: ['ArrowRight', 'ArrowDown'],
    activate: ['Enter', ' ', 'Spacebar'], exit: ['Escape', 'Esc'] };
  function isReducedMotion() {
    try { if (typeof matchMedia === 'function') return !!matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
    return false;
  }
  function pickEvent(ev) {
    try {
      var te = window.CLTreeEvents;
      if (te && typeof te.pick === 'function') { te.pick(ev); return true; }
      if (te && typeof te.select === 'function') { te.select(ev); return true; }
    } catch (e) {}
    if (last) last.selectedEvent = ev;
    return false;
  }
  function wire(root, opts) {
    opts = opts || {};
    if (typeof document === 'undefined' || !root || !root.addEventListener) return null;
    var host = root;
    host.setAttribute('role', 'application');
    host.setAttribute('tabindex', '0');
    host.setAttribute('aria-label', opts.label || '剧情星盘');
    host.setAttribute('data-kbd', 'on');
    if (opts.deco && opts.deco.setAttribute) opts.deco.setAttribute('aria-hidden', 'true');
    if (opts.card && opts.card.setAttribute) {
      opts.card.setAttribute('aria-live', 'polite');
      opts.card.setAttribute('aria-describedby', opts.describeBy || '');
    }
    var reduced = isReducedMotion();
    if (reduced) host.setAttribute('data-tier', 'low');
    var order = [];
    if (last && isArr(last.events)) for (var q = 0; q < last.events.length; q++) order.push(last.events[q].evIdx);
    var cursor = -1;
    function mark(ev) {
      if (last) last.selectedEvent = ev;
      var nodes = host.querySelectorAll('[data-ev]');
      for (var m = 0; m < nodes.length; m++) {
        var on = str(nodes[m].getAttribute('data-ev')) === str(ev);
        nodes[m].setAttribute('aria-selected', on ? 'true' : 'false');
        if (on && nodes[m].focus) nodes[m].focus();
      }
      return ev;
    }
    function move(d) {
      if (!order.length) return -1;
      cursor = (cursor + d + order.length) % order.length;
      return mark(order[cursor]);
    }
    function activate() { return cursor >= 0 ? pickEvent(order[cursor]) : false; }
    function leave() { cursor = -1; return true; }
    function onKeyDown(e) {
      var k = e && e.key;
      if (k === 'ArrowLeft' || k === 'ArrowUp') { move(-1); }
      else if (k === 'ArrowRight' || k === 'ArrowDown') { move(1); }
      else if (k === 'Enter' || k === ' ' || k === 'Spacebar') { activate(); }
      else if (k === 'Escape' || k === 'Esc') { leave(); }
      else return;
      if (e && e.preventDefault) e.preventDefault();
    }
    host.addEventListener('keydown', onKeyDown, false);
    return { keymap: KEYMAP, reduced: reduced, move: move, activate: activate, exit: leave, select: mark,
      focus: function () { if (host.focus) host.focus(); },
      destroy: function () { host.removeEventListener('keydown', onKeyDown, false); } };
  }

  var API = { name: NAME, version: VERSION,
    build: build, get: get, stats: stats, layout: layout, eventAt: eventAt, threadAt: threadAt,
    participation: participation, invalidate: invalidate, clear: clear,
    wire: wire, keymap: KEYMAP, isReducedMotion: isReducedMotion };
  try { window.CLPlotOrbit = API; } catch (e) { if (typeof module !== 'undefined' && module.exports) module.exports = API; }
})();
