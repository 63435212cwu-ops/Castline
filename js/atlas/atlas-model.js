(function () {
  'use strict';

  var VERSION = '7.0';
  var TURN_KINDS = { '转折': 1, '抉择': 1, '高潮': 1, '冲突': 1, '高燃': 1 };

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function isStr(x) { return typeof x === 'string' && x !== ''; }
  function isArr(x) { return Object.prototype.toString.call(x) === '[object Array]'; }

  function deriveStatus(t) {
    var hasR = typeof t.resolved === 'boolean', hasS = typeof t.suspended === 'boolean';
    if (hasR && hasS) {
      if (t.resolved && t.suspended) return { status: 'conflict', known: true };
      if (t.resolved) return { status: 'resolved', known: true };
      if (t.suspended) return { status: 'suspended', known: true };
      return { status: 'open', known: true };
    }
    if (isStr(t.resolution)) {
      if (t.resolution.indexOf('收束') >= 0) return { status: 'resolved', known: true };
      if (t.resolution.indexOf('悬置') >= 0) return { status: 'suspended', known: true };
      return { status: 'open', known: true };
    }
    if (t.completionKnown === true && isStr(t.completion)) {
      if (t.completion.indexOf('收束') >= 0) return { status: 'resolved', known: true };
      if (t.completion.indexOf('悬置') >= 0) return { status: 'suspended', known: true };
      return { status: 'open', known: true };
    }
    return { status: 'unknown', known: false };
  }

  function build(tree, G, opts) {
    opts = (opts && typeof opts === 'object') ? opts : {};
    var warnings = [];
    function warn(code, msg, ref) { warnings.push({ code: code, msg: msg, ref: (ref === undefined ? null : ref) }); }

    if (!tree || typeof tree !== 'object' || !tree.ok) {
      return {
        ok: false, src: 'none',
        warnings: [{ code: 'no-tree', msg: 'tree 缺失或 ok=false，未提供任何星图数据', ref: null }],
        chapters: [], events: [], lines: [], handoffs: [], crossings: [], succession: [], orphanEvents: [],
        totals: { lines: 0, main: 0, branch: 0, twig: 0, events: 0, placedEvents: 0, orphanEvents: 0, unknownStatus: 0, unknownSpan: 0 },
        conservation: { rawThreads: 0, lines: 0, droppedReasons: [] }
      };
    }
    G = (G && typeof G === 'object') ? G : {};

    var rawThreads = isArr(tree.threads) ? tree.threads : [];
    if (!isArr(tree.threads)) warn('no-threads', 'tree.threads 不是数组，按 0 条线处理', null);
    var rawEvents = isArr(tree.events) ? tree.events : [];
    if (!isArr(tree.events)) warn('no-events', 'tree.events 不是数组，按 0 个事件处理', null);
    var rawChapters = isArr(tree.chapters) ? tree.chapters : [];
    if (!isArr(tree.chapters)) warn('no-chapters', 'tree.chapters 不是数组，章节名未提供', null);

    var chapters = [], chapByIdx = {}, ci;
    for (ci = 0; ci < rawChapters.length; ci++) {
      var rc = rawChapters[ci];
      var idx = (rc && isNum(rc.idx)) ? rc.idx : ci;
      var nm = (rc && isStr(rc.name)) ? rc.name : null;
      var ec = (rc && isNum(rc.n)) ? rc.n : ((rc && isNum(rc.eventCount)) ? rc.eventCount : null);
      chapters.push({ idx: idx, name: nm, eventCount: ec });
      chapByIdx[idx] = chapters[chapters.length - 1];
    }

    var events = [], NEV = rawEvents.length, ei;
    for (ei = 0; ei < NEV; ei++) {
      var re = rawEvents[ei];
      if (!re || typeof re !== 'object') {
        warn('bad-event', '事件槽 #' + ei + ' 为空槽或非对象，占位保留下标', ei);
        events.push({ i: ei, order: null, chapIdx: null, chapName: null, title: null, kind: null, cast: [], lineIds: [], quote: null, summary: null });
        continue;
      }
      var chapIdx = isNum(re.chapIdx) ? re.chapIdx : null;
      if (re.chapIdx != null && chapIdx == null) warn('bad-chapidx', '事件 #' + ei + ' 的 chapIdx 非法（非数字）', ei);
      var chapName = null;
      if (chapIdx != null && chapByIdx[chapIdx]) chapName = chapByIdx[chapIdx].name;
      else if (isStr(re.chapter)) chapName = re.chapter;
      events.push({
        i: isNum(re.i) ? re.i : ei,
        order: (re.order != null) ? re.order : null,
        chapIdx: chapIdx, chapName: chapName,
        title: isStr(re.title) ? re.title : null,
        kind: isStr(re.kind) ? re.kind : null,
        cast: isArr(re.cast) ? re.cast.slice(0) : [],
        lineIds: [],
        quote: isStr(re.quote) ? re.quote : null,
        summary: isStr(re.summary) ? re.summary : null
      });
    }

    function normEventIdxs(list, refId) {
      var out = [], seen = {}, k;
      if (!isArr(list)) { if (list != null) warn('bad-events-list', '线 ' + refId + ' 的 events 不是数组', refId); return out; }
      for (k = 0; k < list.length; k++) {
        var v = list[k];
        if (v == null) { warn('empty-slot', '线 ' + refId + ' 的 events[' + k + '] 是空槽', refId); continue; }
        if (!isNum(v) || v < 0 || v >= NEV) { warn('bad-index', '线 ' + refId + ' 的 events[' + k + ']=' + v + ' 越界/非法下标', refId); continue; }
        if (seen[v]) { warn('dup-index', '线 ' + refId + ' 的事件下标 ' + v + ' 在自身 events 里重复', refId); continue; }
        seen[v] = 1; out.push(v);
      }
      return out;
    }

    var lines = [], lineById = {}, sourceIdToIdx = {}, nameToIdx = {}, ti;
    for (ti = 0; ti < rawThreads.length; ti++) {
      var t = rawThreads[ti];
      var refLabel = 'threads[' + ti + ']';
      if (!t || typeof t !== 'object') { warn('bad-thread', refLabel + ' 不是有效对象，按空线占位', ti); t = {}; }

      var id = (t.id != null) ? t.id : ('__t' + ti);
      if (t.id == null) warn('missing-id', refLabel + ' 缺 id，使用占位 id=' + id, id);

      var nameKnown = isStr(t.title);
      var name = nameKnown ? t.title : null;

      var kind = (t.kind === 'main' || t.kind === 'branch' || t.kind === 'twig') ? t.kind : null;
      if (kind == null) { warn('bad-kind', refLabel + '（id=' + id + '）kind 缺失或非法，归入 branch（不假设为主线）', id); kind = 'branch'; }

      var eventIdxs = normEventIdxs(t.events, id);
      var eventCount = eventIdxs.length;
      if (eventCount === 0) warn('empty-line', refLabel + '（id=' + id + '）没有任何可用事件', id);

      var ordFirst = null, ordLast = null, ordKnown = 0, oi;
      for (oi = 0; oi < eventIdxs.length; oi++) {
        var ov = events[eventIdxs[oi]].order;
        if (ov != null) {
          ordKnown++;
          if (ordFirst == null || ov < ordFirst) ordFirst = ov;
          if (ordLast == null || ov > ordLast) ordLast = ov;
        }
      }
      if (eventCount > 0 && ordKnown === 0) warn('order-unknown', refLabel + '（id=' + id + '）所有事件都没有 order', id);

      var chapSet = {}, chapAllKnown = eventCount > 0, startChap = null, endChap = null, si;
      for (si = 0; si < eventIdxs.length; si++) {
        var cIdx = events[eventIdxs[si]].chapIdx;
        if (cIdx == null) { chapAllKnown = false; continue; }
        chapSet[cIdx] = 1;
        if (startChap == null || cIdx < startChap) startChap = cIdx;
        if (endChap == null || cIdx > endChap) endChap = cIdx;
      }
      var spanKnown = eventCount > 0 && chapAllKnown;
      if (eventCount > 0 && !spanKnown) warn('span-unknown', refLabel + '（id=' + id + '）部分事件缺 chapIdx，章跨未提供', id);
      var chapTouched = 0, kk;
      if (spanKnown) for (kk in chapSet) chapTouched++;
      var chapCount = spanKnown ? (endChap - startChap + 1) : null;
      var span = { startChap: spanKnown ? startChap : null, endChap: spanKnown ? endChap : null, chapCount: chapCount, chapTouched: spanKnown ? chapTouched : null, known: spanKnown };

      var castMap = {}, castOrder = [], evk, cn;
      for (evk = 0; evk < eventIdxs.length; evk++) {
        var ev = events[eventIdxs[evk]];
        for (cn = 0; cn < ev.cast.length; cn++) {
          var cname = ev.cast[cn];
          if (!isStr(cname)) continue;
          if (!castMap[cname]) { castMap[cname] = { name: cname, events: 0, firstEventIdx: eventIdxs[evk], lastEventIdx: eventIdxs[evk] }; castOrder.push(cname); }
          castMap[cname].events++;
          castMap[cname].lastEventIdx = eventIdxs[evk];
        }
      }

      var leadName = isStr(t.lead) ? t.lead : null;
      var leadKnown = leadName != null;
      if (leadKnown && !castMap[leadName]) {
        warn('lead-not-in-events', refLabel + '（id=' + id + '）lead「' + leadName + '」未出现在本线任何事件的 cast 中', id);
        castMap[leadName] = { name: leadName, events: 0, firstEventIdx: null, lastEventIdx: null };
        castOrder.push(leadName);
      }

      var coreThresh = Math.max(2, Math.ceil(0.3 * eventCount));
      var cast = [], co;
      for (co = 0; co < castOrder.length; co++) {
        var cc = castMap[castOrder[co]];
        var role = (leadKnown && cc.name === leadName) ? 'lead' : (cc.events >= coreThresh ? 'core' : 'minor');
        cast.push({ name: cc.name, role: role, events: cc.events, firstEventIdx: cc.firstEventIdx, lastEventIdx: cc.lastEventIdx });
      }
      var rolePri = { lead: 0, core: 1, minor: 2 };
      cast.sort(function (a, b) { return rolePri[a.role] - rolePri[b.role] || b.events - a.events || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0); });

      var st = deriveStatus(t);

      var turns = [], tk;
      for (tk = 0; tk < eventIdxs.length; tk++) {
        var evx = events[eventIdxs[tk]];
        if (evx.kind && TURN_KINDS[evx.kind]) turns.push({ eventIdx: eventIdxs[tk], kind: evx.kind });
      }

      var parentId = (t.parent != null) ? t.parent : null;
      var attachEventIdx = isNum(t.attach) ? t.attach : null;
      if (t.attach != null && attachEventIdx == null) warn('bad-attach', refLabel + '（id=' + id + '）attach 非法（非数字）', id);
      if (attachEventIdx != null && (attachEventIdx < 0 || attachEventIdx >= NEV)) { warn('bad-attach-index', refLabel + '（id=' + id + '）attach=' + attachEventIdx + ' 越界', id); attachEventIdx = null; }

      var srcOf = isStr(t.src) ? t.src : (isStr(tree.src) ? tree.src : null);

      var line = {
        id: id, name: name, nameKnown: nameKnown, kind: kind, gen: null,
        parentId: parentId, attachEventIdx: attachEventIdx,
        eventIdxs: eventIdxs, eventCount: eventCount,
        span: span, order: { first: ordFirst, last: ordLast },
        status: st.status, statusKnown: st.known,
        lead: { name: leadName, known: leadKnown },
        cast: cast, turns: turns, handoff: null, src: srcOf,
        _sourceId: (t.sourceId != null) ? t.sourceId : null
      };
      lines.push(line);
      lineById[String(id)] = line;
      if (line._sourceId != null && sourceIdToIdx[String(line._sourceId)] == null) sourceIdToIdx[String(line._sourceId)] = lines.length - 1;
      if (nameKnown && nameToIdx[name] == null) nameToIdx[name] = lines.length - 1;

      var mi;
      for (mi = 0; mi < eventIdxs.length; mi++) events[eventIdxs[mi]].lineIds.push(id);
    }

    var mains = [], gi;
    for (gi = 0; gi < lines.length; gi++) if (lines[gi].kind === 'main') mains.push(lines[gi]);
    mains.sort(function (a, b) {
      var af = a.order.first == null ? Infinity : a.order.first, bf = b.order.first == null ? Infinity : b.order.first;
      if (af !== bf) return af - bf;
      var ae = a.eventIdxs.length ? a.eventIdxs[0] : Infinity, be = b.eventIdxs.length ? b.eventIdxs[0] : Infinity;
      if (ae !== be) return ae - be;
      return String(a.id) < String(b.id) ? -1 : (String(a.id) > String(b.id) ? 1 : 0);
    });
    for (gi = 0; gi < mains.length; gi++) mains[gi].gen = gi;
    if (mains.length === 0 && lines.length > 0) warn('no-main', '没有 kind=main 的线，主线代次无从编号', null);

    function resolveGen(line, seen) {
      if (line.gen != null) return line.gen;
      if (seen[String(line.id)]) { warn('gen-cycle', '线 ' + line.id + ' 的 parent 链出现循环', line.id); return null; }
      seen[String(line.id)] = 1;
      if (line.parentId == null) return null;
      var parentLine = lineById[String(line.parentId)];
      if (!parentLine || parentLine === line) return null;
      return resolveGen(parentLine, seen);
    }
    var bi;
    for (bi = 0; bi < lines.length; bi++) {
      var ln = lines[bi];
      if (ln.kind === 'main') continue;
      var g2 = resolveGen(ln, {});
      if (g2 == null) warn('gen-unknown', '线 ' + ln.id + ' 的 parent 缺失/不可判定，gen 未知', ln.id);
      ln.gen = g2;
    }

    var handoffs = [], handoffToLine = {}, hi;
    var treeHandoffs = isArr(tree.handoffs) ? tree.handoffs : [];
    if (!isArr(tree.handoffs)) warn('no-tree-handoffs', 'tree.handoffs 不是数组，全部改走 G.storylines 兜底', null);
    for (hi = 0; hi < treeHandoffs.length; hi++) {
      var h = treeHandoffs[hi];
      if (!h || typeof h !== 'object' || h.from == null || h.to == null) { warn('bad-handoff', 'tree.handoffs[' + hi + '] 缺失/无效', hi); continue; }
      var atv = isNum(h.at) ? h.at : null;
      var entry = { fromId: h.from, toId: h.to, atEventIdx: atv, reason: isStr(h.reason) ? h.reason : null, known: true, src: 'tree' };
      handoffs.push(entry);
      var tk2 = String(h.to);
      if (!handoffToLine[tk2]) handoffToLine[tk2] = entry;
    }
    var gStorylines = isArr(G.storylines) ? G.storylines : [];
    var gi2;
    for (gi2 = 0; gi2 < gStorylines.length; gi2++) {
      var gs = gStorylines[gi2];
      if (!gs || typeof gs !== 'object' || !isStr(gs.handoff_from)) continue;
      var toIdx = (gs.id != null && sourceIdToIdx[String(gs.id)] != null) ? sourceIdToIdx[String(gs.id)]
        : (isStr(gs.name) && nameToIdx[gs.name] != null ? nameToIdx[gs.name] : null);
      if (toIdx == null) continue;
      var toLine = lines[toIdx];
      if (handoffToLine[String(toLine.id)]) continue;
      var fromIdx = (sourceIdToIdx[String(gs.handoff_from)] != null) ? sourceIdToIdx[String(gs.handoff_from)]
        : (nameToIdx[gs.handoff_from] != null ? nameToIdx[gs.handoff_from] : null);
      if (fromIdx == null) { warn('handoff-from-unresolved', '线「' + (gs.name || gs.id) + '」声明 handoff_from=' + gs.handoff_from + '，找不到对应线', toLine.id); continue; }
      var fromLine = lines[fromIdx];
      var entry2 = { fromId: fromLine.id, toId: toLine.id, atEventIdx: null, reason: isStr(gs.handoff_reason) ? gs.handoff_reason : null, known: true, src: 'model' };
      handoffs.push(entry2);
      handoffToLine[String(toLine.id)] = entry2;
    }
    var li;
    for (li = 0; li < lines.length; li++) {
      var he = handoffToLine[String(lines[li].id)];
      lines[li].handoff = he ? { fromId: he.fromId, atEventIdx: he.atEventIdx, reason: he.reason, known: true } : null;
      delete lines[li]._sourceId;
    }

    var crossings = [], seenPair = {}, evI;
    for (evI = 0; evI < events.length; evI++) {
      var e2 = events[evI];
      if (!e2 || e2.lineIds.length < 2) continue;
      var pa, pb;
      for (pa = 0; pa < e2.lineIds.length; pa++) {
        for (pb = pa + 1; pb < e2.lineIds.length; pb++) {
          var key2 = String(e2.lineIds[pa]) + '>' + String(e2.lineIds[pb]) + '@' + evI;
          if (seenPair[key2]) continue;
          seenPair[key2] = 1;
          crossings.push({ a: e2.lineIds[pa], b: e2.lineIds[pb], eventIdx: evI });
        }
      }
    }

    var main = 0, branch = 0, twig = 0, unknownStatus = 0, unknownSpan = 0, tci;
    for (tci = 0; tci < lines.length; tci++) {
      if (lines[tci].kind === 'main') main++; else if (lines[tci].kind === 'twig') twig++; else branch++;
      if (!lines[tci].statusKnown) unknownStatus++;
      if (!lines[tci].span.known) unknownSpan++;
    }
    var placedEvents = 0, pei;
    for (pei = 0; pei < events.length; pei++) if (events[pei].lineIds.length > 0) placedEvents++;
    var orphanEvents = events.length - placedEvents;
    if (orphanEvents > 0) warn('orphan-events', orphanEvents + ' 个事件不属于任何线', null);

    var totals = { lines: lines.length, main: main, branch: branch, twig: twig, events: events.length, placedEvents: placedEvents, orphanEvents: orphanEvents, unknownStatus: unknownStatus, unknownSpan: unknownSpan };
    var conservation = { rawThreads: rawThreads.length, lines: lines.length, droppedReasons: [] };
    if (conservation.lines !== conservation.rawThreads) { conservation.droppedReasons.push('lines(' + conservation.lines + ') != rawThreads(' + conservation.rawThreads + ')'); warn('conservation-violated', conservation.droppedReasons[0], null); }

    var LIFECYCLE = { resolved: 'resolved', suspended: 'suspended', open: 'active', conflict: 'conflict', unknown: 'unknown' };
    var currentMain = mains.length ? mains[mains.length - 1] : null;
    var li3;
    for (li3 = 0; li3 < lines.length; li3++) {
      var dl = lines[li3];
      dl.metrics = {
        lengthRank: null,
        chapRank: null,
        sharePct: placedEvents > 0 ? Math.round(dl.eventCount / placedEvents * 1000) / 10 : null
      };
      dl.lifecycle = dl.statusKnown ? (LIFECYCLE[dl.status] || 'unknown') : 'unknown';
      dl.isCurrentMain = (currentMain !== null && dl === currentMain);
      var coreNames = [], coreCount = 0, ci4;
      for (ci4 = 0; ci4 < dl.cast.length; ci4++) {
        if (dl.cast[ci4].role === 'core') { coreCount++; if (coreNames.length < 5) coreNames.push(dl.cast[ci4].name); }
      }
      dl.roster = { lead: { name: dl.lead.name, known: dl.lead.known }, core: coreNames, coreCount: coreCount, totalCount: dl.cast.length };
      var myCross = [], ci5;
      for (ci5 = 0; ci5 < crossings.length; ci5++) {
        var cr2 = crossings[ci5];
        if (cr2.a === dl.id) myCross.push({ withId: cr2.b, eventIdx: cr2.eventIdx });
        else if (cr2.b === dl.id) myCross.push({ withId: cr2.a, eventIdx: cr2.eventIdx });
      }
      dl.crossings = myCross;
    }
    function rankTie(a, b) {
      var af = a.order.first == null ? Infinity : a.order.first, bf = b.order.first == null ? Infinity : b.order.first;
      if (af !== bf) return af - bf;
      return String(a.id) < String(b.id) ? -1 : (String(a.id) > String(b.id) ? 1 : 0);
    }
    var kindNames = ['main', 'branch', 'twig'], ki2;
    for (ki2 = 0; ki2 < kindNames.length; ki2++) {
      var grp = [], gi3;
      for (gi3 = 0; gi3 < lines.length; gi3++) if (lines[gi3].kind === kindNames[ki2]) grp.push(lines[gi3]);
      var byLen = grp.slice(0).sort(function (a, b) { return (b.eventCount - a.eventCount) || rankTie(a, b); });
      var ri;
      for (ri = 0; ri < byLen.length; ri++) byLen[ri].metrics.lengthRank = ri + 1;
      var byChap = [], gi4;
      for (gi4 = 0; gi4 < grp.length; gi4++) if (grp[gi4].span.known) byChap.push(grp[gi4]);
      byChap.sort(function (a, b) { return (b.span.chapCount - a.span.chapCount) || rankTie(a, b); });
      for (ri = 0; ri < byChap.length; ri++) byChap[ri].metrics.chapRank = ri + 1;
    }

    var succession = [], si3;
    for (si3 = 0; si3 < mains.length; si3++) {
      var ml2 = mains[si3];
      var he3 = handoffToLine[String(ml2.id)];
      var ho2 = null;
      if (he3) {
        var fromLine3 = lineById[String(he3.fromId)];
        var fromName3 = (fromLine3 && fromLine3.nameKnown) ? { name: fromLine3.name, known: true } : { name: null, known: false };
        ho2 = { fromId: he3.fromId, fromName: fromName3, atEventIdx: he3.atEventIdx, reason: he3.reason, known: he3.known === true };
      }
      succession.push({ gen: ml2.gen, lineId: ml2.id, name: ml2.name, lead: { name: ml2.lead.name, known: ml2.lead.known }, handoff: ho2 });
    }

    var orphanList = [], oi3;
    for (oi3 = 0; oi3 < events.length; oi3++) if (events[oi3].lineIds.length === 0) orphanList.push(oi3);

    var modelSrc = (tree.src === 'model' || tree.src === 'derived' || tree.src === 'mixed') ? tree.src : 'derived';

    return { ok: true, src: modelSrc, warnings: warnings, chapters: chapters, events: events, lines: lines, handoffs: handoffs, crossings: crossings, succession: succession, orphanEvents: orphanList, totals: totals, conservation: conservation };
  }

  function lanes(model, opts) {
    opts = (opts && typeof opts === 'object') ? opts : {};
    var maxLanes = (isNum(opts.maxLanes) && opts.maxLanes > 0) ? Math.floor(opts.maxLanes) : Infinity;
    var list = (model && isArr(model.lines)) ? model.lines.slice(0) : [];
    var kindPri = { main: 0, branch: 1, twig: 2 };
    list.sort(function (a, b) {
      var ka = kindPri[a.kind] == null ? 3 : kindPri[a.kind], kb = kindPri[b.kind] == null ? 3 : kindPri[b.kind];
      if (ka !== kb) return ka - kb;
      var ag = a.gen == null ? Infinity : a.gen, bg = b.gen == null ? Infinity : b.gen;
      if (ag !== bg) return ag - bg;
      var af = a.order.first == null ? Infinity : a.order.first, bf = b.order.first == null ? Infinity : b.order.first;
      if (af !== bf) return af - bf;
      return String(a.id) < String(b.id) ? -1 : (String(a.id) > String(b.id) ? 1 : 0);
    });
    var lanesOut = [], aggregateIds = [], i;
    for (i = 0; i < list.length; i++) {
      if (i < maxLanes) lanesOut.push({ laneIdx: i, lineIds: [list[i].id] });
      else aggregateIds.push(list[i].id);
    }
    var aggregate = aggregateIds.length ? { lineIds: aggregateIds, count: aggregateIds.length } : null;
    return { lanes: lanesOut, aggregate: aggregate };
  }

  function search(model, q) {
    var query = isStr(q) ? q.trim() : (typeof q === 'string' ? q : '');
    var out = { lines: [], events: [], characters: [], total: 0 };
    if (!model || !query) return out;
    var qL = query.toLowerCase();
    function hit(s) { return typeof s === 'string' && s.toLowerCase().indexOf(qL) >= 0; }
    var mLines = isArr(model.lines) ? model.lines : [], mEvents = isArr(model.events) ? model.events : [];
    var charSet = {}, i, c;
    for (i = 0; i < mLines.length; i++) {
      var ln = mLines[i], matched = hit(ln.name) || String(ln.id).toLowerCase().indexOf(qL) >= 0;
      for (c = 0; c < ln.cast.length; c++) {
        if (hit(ln.cast[c].name)) { matched = true; charSet[ln.cast[c].name] = 1; }
      }
      if (matched) out.lines.push(ln.id);
    }
    for (i = 0; i < mEvents.length; i++) {
      var ev = mEvents[i];
      if (!ev) continue;
      var m2 = hit(ev.title) || hit(ev.kind), k;
      for (k = 0; k < ev.cast.length; k++) if (hit(ev.cast[k])) { m2 = true; charSet[ev.cast[k]] = 1; }
      if (m2) out.events.push(ev.i);
    }
    var names = [], nm;
    for (nm in charSet) names.push(nm);
    names.sort();
    out.characters = names;
    out.total = out.lines.length + out.events.length + out.characters.length;
    return out;
  }

  function footprint(model, name) {
    var out = { lines: [], eventCount: 0 };
    if (!model || !isStr(name)) return out;
    var mLines = isArr(model.lines) ? model.lines : [], mEvents = isArr(model.events) ? model.events : [];
    function chapOf(idx) { return (idx != null && mEvents[idx]) ? mEvents[idx].chapIdx : null; }
    var i, c;
    for (i = 0; i < mLines.length; i++) {
      var ln = mLines[i];
      for (c = 0; c < ln.cast.length; c++) {
        if (ln.cast[c].name !== name) continue;
        var cc = ln.cast[c];
        out.lines.push({ lineId: ln.id, role: cc.role, events: cc.events, firstEventIdx: cc.firstEventIdx, lastEventIdx: cc.lastEventIdx, entryChap: chapOf(cc.firstEventIdx), exitChap: chapOf(cc.lastEventIdx) });
        out.eventCount += cc.events;
        break;
      }
    }
    return out;
  }

  window.CLAtlasModel = { build: build, lanes: lanes, search: search, footprint: footprint, VERSION: VERSION };
})();
