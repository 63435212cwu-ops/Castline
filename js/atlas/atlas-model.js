/* Castline · js/atlas/atlas-model.js — 全书星图 v7.0 数据底座（window.CLAtlasModel）
 * 契约：mystic-refactor-plan/grand-atlas-plan/CONTRACT.md §1。
 * 纯函数、无 DOM、无副作用、ES5 兼容；只读 CLStory.analyze(G) 的 tree 与图谱 G 已有字段，
 * 缺字段一律 known:false / null，不推断、不用颜色或默认值补齐（v70 CONTRACT §0）。
 *
 * 关键取舍（与契约字面冲突时，选「最不发明数据」的一边，写在这里而不是停工等人）：
 *  1) turns 的 kind 白名单：契约写「转折/抉择/高潮/冲突」，但全书唯一的 kind 词表
 *     （js/tree/storylines.js 的 KINDS/TENSE）里从没有「高潮」，只有「高燃」——
 *     且「高燃」正是该文件自己定义的张力族（TENSE）成员之一，与「转折/抉择/冲突」同族。
 *     判定「高潮」是笔误：两个词同时收进白名单（可加不可改），既不丢真实数据（高燃事件
 *     不会被静默排除），也不违反契约字面（真出现「高潮」一样命中），不是发明新语义。
 *  2) cast 全集不信任 tree.threads[].cast（该数组来自 enrich() 的加权聚合，在 model/mixed
 *     来源下可能只覆盖 model 声明的 events），改为从本线 eventIdxs 关联到的
 *     tree.events[].cast 重新聚合，逐字对照任务书「不得只用 tree.cast 前几位」。
 *  3) status 只在 resolved/suspended 两个布尔字段都缺席（不是 false，是 undefined/非布尔）
 *     时才退到 resolution → completion 兜底，再退到 unknown；两个布尔字段只要存在（哪怕都是
 *     false）就已经是「未收束也未悬置」的确定信息 → 'open'，不算 unknown。
 *  4) handoff 解析：tree.handoffs 优先；对 tree.handoffs 没覆盖到的 toId，
 *     再逐条尝试 G.storylines[].handoff_from（按 sourceId 优先、否则按线名对齐），
 *     不是「tree.handoffs 一空就整体切换」的全局开关 —— 那样会把 tree.handoffs 部分覆盖、
 *     部分空缺的真实情况错误地判成「tree 完全没给」。
 *  5) crossings 定义为「两条线的 eventIdxs 字面上共享同一个下标」，不用 tree.junctions
 *     （那是亲和度/共同角色的推断关系，契约明确写「仅共享事件；不生成因果」，用 junctions
 *     反而是二次推断）。实测 sample-saga 真数据里这种字面重叠并不罕见（90 组）——
 *     严格来源结构下主干与支线各自的 events 是作者在 graph.storylines 里各自声明的，
 *     同一个事件号完全可能被两条线同时列入（同一场戏两条故事线都在场），tree.threads
 *     最终确实保留了这种重叠，不是分区去重后的产物。
 *
 * v71 派生层（build 末尾对已有字段二次聚合，不引入新数据源、不发明数据）：
 *  每条 line 增加 metrics{lengthRank,chapRank,sharePct}（同 kind 内排名，并列按 order.first
 *  小者居前；span.known=false 时 chapRank=null；placedEvents=0 时 sharePct=null）、
 *  lifecycle（status 的显示态映射，statusKnown=false → 'unknown'）、isCurrentMain（gen 最大的
 *  主线）、roster（cast 摘要：lead/core 前 5/coreCount/totalCount）、crossings（本线参与的
 *  共享事件对反查）；顶层增加 succession（main 按 gen 升序 + 入向 handoff 含 fromName）与
 *  orphanEvents（不属于任何线的事件下标）。缺数据一律 null/[]/known:false。
 *
 * @contract v70, v71
 */
(function () {
  'use strict';

  var VERSION = '7.0';
  var TURN_KINDS = { '转折': 1, '抉择': 1, '高潮': 1, '冲突': 1, '高燃': 1 };

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function isStr(x) { return typeof x === 'string' && x !== ''; }
  function isArr(x) { return Object.prototype.toString.call(x) === '[object Array]'; }

  // ───────────────────────────────── status（取舍 3）
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

  // ───────────────────────────────── build
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

    // ── chapters
    var chapters = [], chapByIdx = {}, ci;
    for (ci = 0; ci < rawChapters.length; ci++) {
      var rc = rawChapters[ci];
      var idx = (rc && isNum(rc.idx)) ? rc.idx : ci;
      var nm = (rc && isStr(rc.name)) ? rc.name : null;
      var ec = (rc && isNum(rc.n)) ? rc.n : ((rc && isNum(rc.eventCount)) ? rc.eventCount : null);
      chapters.push({ idx: idx, name: nm, eventCount: ec });
      chapByIdx[idx] = chapters[chapters.length - 1];
    }

    // ── events（与 tree.events 下标对齐；lineIds 留空槽，装配线时回填）
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
        // R2-B 唯一获准改动：透传 tree.events[i].quote/summary（U02 事件卡用），不参与守恒计算、
        // 不推断、缺失即 null（不是空字符串——空字符串会被 U02 误判成「有引句但是空」）。
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

    // ── lines（第一遍：与 tree.threads 一一对应，绝不丢线——rawThreads.length === lines.length）
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

      // order.first/last：来自本线事件的 order 值
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

      // span：仅当本线全部事件的 chapIdx 都可靠时 known
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
      // chapCount = 叙事跨度（首末章之差 +1，「跨 N 章」）；chapTouched = 实际出现过事件的章数（「涉 k 章」）。
      // 两者不能混：一条跨 25 章只落 4 章的低频长支线，跨度是 25，不是 4。
      var chapCount = spanKnown ? (endChap - startChap + 1) : null;
      var span = { startChap: spanKnown ? startChap : null, endChap: spanKnown ? endChap : null, chapCount: chapCount, chapTouched: spanKnown ? chapTouched : null, known: spanKnown };

      // cast 全集：从本线 eventIdxs 关联到的真实事件里重新聚合（取舍 2），不信任 t.cast
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

    // ── gen：main 按 order.first 排序编号 0..n；branch/twig 继承 parent 的 gen
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

    // ── handoffs（取舍 4）：tree.handoffs 优先，未覆盖的 toId 再用 G.storylines[].handoff_from 兜底
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
      if (handoffToLine[String(toLine.id)]) continue; // tree 已给出，不重复兜底
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

    // ── crossings（取舍 5）：字面共享事件下标，不用 tree.junctions
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

    // ── totals / conservation
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

    // ── v71 派生层：全部从上面已算出的字段二次聚合，缺数据给 null/[]/known:false
    var LIFECYCLE = { resolved: 'resolved', suspended: 'suspended', open: 'active', conflict: 'conflict', unknown: 'unknown' };
    var currentMain = mains.length ? mains[mains.length - 1] : null; // mains 已按 order.first 升序、gen=下标
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
    // 名次：同 kind 分组；lengthRank 按 eventCount 降序，chapRank 按 span.chapCount 降序（span 未知不参与，留 null）。
    // 并列按 order.first 小者居前，再按 id 字典序——完全确定性，同输入两次 build 逐字节相同。
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

    // ── v71 succession：main 按 gen 升序；handoff 取 model.handoffs 里 toId===lineId 的那条，
    // fromName 从 lines 查名（查不到/名未知 → known:false）；无入向 handoff（含第一条主线）为 null。
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

    // ── v71 orphanEvents：不属于任何线的事件下标（全归线时为 []）
    var orphanList = [], oi3;
    for (oi3 = 0; oi3 < events.length; oi3++) if (events[oi3].lineIds.length === 0) orphanList.push(oi3);

    var modelSrc = (tree.src === 'model' || tree.src === 'derived' || tree.src === 'mixed') ? tree.src : 'derived';

    return { ok: true, src: modelSrc, warnings: warnings, chapters: chapters, events: events, lines: lines, handoffs: handoffs, crossings: crossings, succession: succession, orphanEvents: orphanList, totals: totals, conservation: conservation };
  }

  // ───────────────────────────────── lanes（一线一道；容量有限时按优先级溢出进 aggregate，计数守恒）
  // 优先级：main 优先于 branch 优先于 twig（代次/叙事顺序升序），保证被吞掉的总是末梢而不是主干——
  // 这里不做「不重叠可共享车道」的时间轴打包：契约没有要求打包，且真实素材里主/支/末梢的事件区间
  // 天然顺序排列、互不重叠，打包算法会把「容量不足」的场景全部吃成 1 条车道、测不出真正的溢出，
  // 反而是打包本身在发明一种契约没写的调度语义。一线一道最贴近「aggregate 幽灵环 + N」的心智模型。
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

  // ───────────────────────────────── search
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

  // ───────────────────────────────── footprint
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
