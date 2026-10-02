/**
 * @role component
 * @owns js/annulus/annulus-model.js
 * @budget n/a (pure compute, no DOM; build O(N+threads+atlas))
 * @contract v80
 */
(function () {
  'use strict';

  var NAME = 'annulus-model';
  var VERSION = '1.0.0';

  function emptyStats() {
    return { valid: 0, rings: 0, mains: 0, branches: 0, skipped: 0, angleDrift: 0 };
  }

  var lastStats = emptyStats();

  function fail() {
    lastStats = emptyStats();
    return {
      ok: false,
      N: 0,
      R: 0,
      rings: [],
      handoffs: [],
      chapters: [],
      crossings: [],
      orphans: [],
      lanes: 0,
      stats: lastStats
    };
  }

  function isNum(x) {
    return typeof x === 'number' && isFinite(x);
  }

  function angAt(pos, N) {
    return Math.PI / 2 - (pos / N) * Math.PI * 2;
  }

  function clampGen(g) {
    if (!isNum(g)) return 5;
    if (g < 0) return 0;
    if (g > 5) return 5;
    return g;
  }

  function shortName(title, lead) {
    var t = title || '';
    var pfx = (lead || '') + ' · ';
    if (lead && t.indexOf(pfx) === 0) t = t.substring(pfx.length);
    if (t.length > 7) t = t.substring(0, 6) + '\u2026';
    return t;
  }

  function buildRoster(line, threadLead) {
    var cast = (line && line.cast) ? line.cast : [];
    var pool = [];
    var minor = 0;
    var i;
    var c;
    for (i = 0; i < cast.length; i++) {
      c = cast[i];
      if (!c) continue;
      if (c.role === 'core') pool.push(c);
      else if (c.role === 'minor') minor++;
    }
    pool.sort(function (a, b) {
      return (b.events || 0) - (a.events || 0);
    });
    var take = pool.length < 3 ? pool.length : 3;
    var core = [];
    for (i = 0; i < take; i++) core.push(pool[i].name);
    var rr = (line && line.roster) ? line.roster : null;
    var coreCount = rr && isNum(rr.coreCount) ? rr.coreCount : pool.length;
    var total = rr && isNum(rr.totalCount) ? rr.totalCount : cast.length;
    var lead = (rr && rr.lead && typeof rr.lead === 'object') ? (rr.lead.known === false ? '' : (rr.lead.name || '')) : ((rr && typeof rr.lead === 'string') ? rr.lead : (threadLead || ''));   /* 主控：atlas roster.lead 可能是 {name,known} 对象 */
    var more = coreCount - take + minor;
    if (more < 0) more = 0;
    return { lead: lead, core: core, more: more, total: total };
  }

  function turnKind(line, evIdx) {
    if (!line || !line.turns) return null;
    for (var i = 0; i < line.turns.length; i++) {
      if (line.turns[i] && line.turns[i].eventIdx === evIdx) return line.turns[i];
    }
    return null;
  }

  function build(view, atlas) {
    if (!view || typeof view.orderList !== 'function' || typeof view.layout !== 'function') {
      return fail();
    }
    var order = null;
    var layout = null;
    try {
      order = view.orderList();
      layout = view.layout();
    } catch (e) {
      return fail();
    }
    if (!order || !order.length) return fail();
    if (!layout || !layout.threads || !layout.threads.length) return fail();

    var R = isNum(layout.R) ? layout.R : 0;
    if (!R && view.stats) {
      try {
        var vs = view.stats();
        if (vs && isNum(vs.R)) R = vs.R;
      } catch (e2) { R = 0; }
    }
    if (!isNum(R) || R <= 0) return fail();

    var N = order.length;
    var pos = {};
    var i;
    for (i = 0; i < N; i++) pos[order[i]] = i;

    var angleOf = null;
    try {
      var desc = view.desc ? view.desc() : null;
      if (desc && desc.angleOf) angleOf = desc.angleOf;
    } catch (e3) { angleOf = null; }

    var angTab = {};
    var drift = 0;
    for (i = 0; i < N; i++) {
      var ev = order[i];
      var a0t = angAt(i, N);
      /* 主控补丁：盘的真实事件角 desc.angleOf 优先（实测 = 算值 + 2π，同几何但要与珠位逐字对齐）；仅缺失时回落算值 */
      if (angleOf && isNum(angleOf[ev])) { if (Math.abs(angleOf[ev] - a0t) > 1e-3) drift++; a0t = angleOf[ev]; }
      angTab[ev] = a0t;
    }
    function ang(evIdx) {
      var a = angTab[evIdx];
      return isNum(a) ? a : NaN;
    }

    var lines = {};
    var lineArr = (atlas && atlas.lines) ? atlas.lines : [];
    for (i = 0; i < lineArr.length; i++) {
      if (lineArr[i] && lineArr[i].id != null) lines[lineArr[i].id] = lineArr[i];
    }

    var evMeta = {};
    var evArr = (atlas && atlas.events) ? atlas.events : [];
    for (i = 0; i < evArr.length; i++) {
      if (evArr[i] && isNum(evArr[i].i)) evMeta[evArr[i].i] = evArr[i];
    }

    var threads = layout.threads;
    var rings = [];
    var skipped = 0;
    var validCount = 0;
    var mains = 0;
    var branches = 0;

    for (i = 0; i < threads.length; i++) {
      var th = threads[i];
      if (!th || th.id == null || !th.events || !th.events.length) {
        skipped++;
        continue;
      }
      var lane = isNum(th.lane) ? th.lane : 0;
      var r = isNum(th.r) ? th.r : R * (0.965 - 0.062 * lane);
      var line = lines[th.id] || null;
      var lead = (line && line.lead && line.lead.name) ? line.lead.name : (th.lead || '');
      var name = (line && line.name) ? line.name : (th.title || '');

      var evs = [];
      var firstPos = -1;
      var lastPos = -1;
      var j;
      for (j = 0; j < th.events.length; j++) {
        var ei = th.events[j];
        var p = pos[ei];
        if (p === undefined) continue;
        if (firstPos < 0 || p < firstPos) firstPos = p;
        if (p > lastPos) lastPos = p;
        var turn = turnKind(line, ei);
        var meta = evMeta[ei] || null;
        evs.push({
          ev: ei,
          ang: ang(ei),
          kind: meta && meta.kind ? meta.kind : (turn && turn.kind ? turn.kind : 'unknown'),
          turn: !!turn
        });
      }
      evs.sort(function (x, y) { return y.ang - x.ang; });   /* 主控补丁：叙事序 = 角度递减，不信任 th.events 的既有顺序 */
      var valid = evs.length > 0 && isNum(r);
      if (!valid) skipped++;
      else {
        validCount++;
        if (th.kind === 'main') mains++;
        else branches++;
      }

      var gen = line && line.gen != null ? clampGen(line.gen) : 5;
      var span = (line && line.span) ? line.span : null;
      var metrics = (line && line.metrics) ? line.metrics : null;
      var lx = (line && line.crossings) ? line.crossings : [];
      var xcross = [];
      for (j = 0; j < lx.length; j++) {
        var xc = lx[j];
        if (!xc || !isNum(xc.eventIdx)) continue;
        xcross.push({ withId: xc.withId, ev: xc.eventIdx, ang: ang(xc.eventIdx) });
      }

      rings.push({
        id: th.id,
        kind: th.kind === 'branch' ? 'branch' : (th.kind === 'twig' ? 'twig' : 'main'),
        gen: gen,
        lane: lane,
        r: r,
        a0: evs.length ? evs[0].ang : NaN,
        a1: evs.length ? evs[evs.length - 1].ang : NaN,
        t0: firstPos >= 0 ? firstPos / N : 0,
        t1: lastPos >= 0 ? lastPos / N : 0,
        name: name,
        shortName: shortName(name, lead),
        lead: lead,
        lifecycle: line && line.lifecycle ? line.lifecycle : 'unknown',
        status: line && line.status ? line.status : 'unknown',
        statusKnown: line ? line.statusKnown === true : false,
        eventCount: evs.length,
        chapSpan: span ? { first: span.first, last: span.last, known: span.known === true } : { first: null, last: null, known: false },
        lengthRank: metrics && isNum(metrics.lengthRank) ? metrics.lengthRank : null,
        sharePct: metrics && isNum(metrics.sharePct) ? metrics.sharePct : null,
        isCurrentMain: !!(line && line.isCurrentMain),
        roster: buildRoster(line, lead),
        events: evs,
        crossings: xcross,
        handoffIn: null,
        colorVar: (th.kind === 'main' ? '--cl-ann-gen-' : '--cl-ann-gen-') + gen + (th.kind === 'main' ? '' : '-dim'),
        valid: valid
      });
    }

    var ringById = {};
    for (i = 0; i < rings.length; i++) ringById[rings[i].id] = rings[i];

    rings.sort(function (a, b) {
      var am = a.kind === 'main' ? 0 : 1;
      var bm = b.kind === 'main' ? 0 : 1;
      if (am !== bm) return am - bm;
      if (am === 0 && a.gen !== b.gen) return a.gen - b.gen;
      return a.t0 - b.t0;
    });

    /* W1.5：同代次支线按出场序轮转三档明度（shade 0/1/2），相邻同色弧靠明度区分——契约 §一「相邻同车道弧用亮度错开」 */
    var shadeCnt = {};
    for (i = 0; i < rings.length; i++) {
      if (rings[i].kind === 'main') { rings[i].shade = 0; continue; }
      var sg = rings[i].gen == null ? 5 : rings[i].gen;
      var scn = shadeCnt[sg] || 0;
      rings[i].shade = scn % 3;
      shadeCnt[sg] = scn + 1;
    }

    var handoffs = [];
    var hArr = (atlas && atlas.handoffs) ? atlas.handoffs : [];
    for (i = 0; i < hArr.length; i++) {
      var h = hArr[i];
      if (!h || h.toId == null) continue;
      var ha = NaN;
      if (isNum(h.atEventIdx)) ha = ang(h.atEventIdx);
      if (!isNum(ha)) {
        var tr = ringById[h.toId];
        if (tr && tr.events.length) ha = tr.events[0].ang;
      }
      if (!isNum(ha)) continue;
      var toLine = lines[h.toId] || null;
      var hGen = toLine && toLine.gen != null ? clampGen(toLine.gen) : 5;
      handoffs.push({
        fromId: h.fromId,
        toId: h.toId,
        gen: hGen,
        a: ha,
        reason: h.reason || '',
        known: !!h.known,
        x: null
      });
      var target = ringById[h.toId];
      if (target) target.handoffIn = { fromId: h.fromId, reason: h.reason || '', known: !!h.known };
    }

    var agg = {};
    var aggList = [];
    for (i = 0; i < evArr.length; i++) {
      var me = evArr[i];
      if (!me || me.chapIdx == null || !isNum(me.chapIdx)) continue;
      var mp = pos[me.i];
      if (mp === undefined) continue;
      var ci = me.chapIdx;
      var g = agg[ci];
      if (!g) {
        g = { idx: ci, name: me.chapName || '', min: mp, max: mp, evCount: 0 };
        agg[ci] = g;
        aggList.push(g);
      }
      g.evCount++;
      if (mp < g.min) g.min = mp;
      if (mp > g.max) g.max = mp;
      if (!g.name && me.chapName) g.name = me.chapName;
    }
    var orderIdx = {};
    var chArr = (atlas && atlas.chapters) ? atlas.chapters : [];
    for (i = 0; i < chArr.length; i++) {
      if (chArr[i] && isNum(chArr[i].idx)) orderIdx[chArr[i].idx] = i;
    }
    aggList.sort(function (a, b) {
      var ao = orderIdx[a.idx] != null ? orderIdx[a.idx] : a.min;
      var bo = orderIdx[b.idx] != null ? orderIdx[b.idx] : b.min;
      return ao - bo;
    });
    var chapters = [];
    for (i = 0; i < aggList.length; i++) {
      var cg = aggList[i];
      chapters.push({
        idx: cg.idx,
        name: cg.name,
        a0: ang(order[cg.min]),
        a1: ang(order[cg.max]),
        evCount: cg.evCount
      });
    }

    var crossings = [];
    var crArr = (atlas && atlas.crossings) ? atlas.crossings : [];
    for (i = 0; i < crArr.length; i++) {
      var cx = crArr[i];
      if (!cx || !isNum(cx.eventIdx)) continue;
      crossings.push({ a: cx.a, b: cx.b, ev: cx.eventIdx, ang: ang(cx.eventIdx) });
    }

    var orphans = [];
    var orArr = (atlas && atlas.orphanEvents) ? atlas.orphanEvents : [];
    for (i = 0; i < orArr.length; i++) {
      var oe = orArr[i];
      if (!isNum(oe) || pos[oe] === undefined) continue;
      orphans.push({ ev: oe, ang: ang(oe) });
    }

    lastStats = {
      valid: validCount,
      rings: rings.length,
      mains: mains,
      branches: branches,
      skipped: skipped,
      angleDrift: drift
    };

    return {
      ok: true,
      N: N,
      R: R,
      rings: rings,
      handoffs: handoffs,
      chapters: chapters,
      crossings: crossings,
      orphans: orphans,
      lanes: isNum(layout.lanes) ? layout.lanes : 0,
      stats: lastStats
    };
  }

  window.CLAnnulusModel = {
    name: NAME,
    version: VERSION,
    build: build,
    stats: function () { return lastStats; }
  };
})();
