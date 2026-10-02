/**
 * @role component
 * @owns js/gem/gem-model.js
 * @budget build ms ≤ 1（纯计算无 DOM，stats().ms 自报）
 * @contract v80-W3
 */
(function () {
  'use strict';

  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = ['MIND', 'FORCE', 'WILL', 'CHARM', 'HEART', 'DRIVE', 'REACH', 'CODE'];
  var MKEYS = ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
  var MEN = ['BILLING', 'SCREEN', 'SPAN', 'ARC', 'STRIFE', 'HIDDEN', 'LIGHT', 'DARK'];
  var built = 0;
  var msLast = 0;
  var metaCache = null;

  function now() {
    return (typeof performance !== 'undefined' && performance &&
      typeof performance.now === 'function') ? performance.now() : 0;
  }

  function radar() {
    return (typeof window !== 'undefined' && window.CLRadar) ? window.CLRadar : null;
  }

  function attrKeys() {
    var r = radar();
    return (r && r.KEYS && r.KEYS.length === 8) ? r.KEYS : KEYS;
  }

  function attrEn() {
    var r = radar();
    return (r && r.EN && r.EN.length === 8) ? r.EN : EN;
  }

  function scoreOf(a) {
    var r = radar();
    if (r && typeof r.scoreOf === 'function') return r.scoreOf(a);
    if (a && typeof a === 'object' && a.pending) return null;
    var raw = a && typeof a === 'object' && !Array.isArray(a) ? a.score : a;
    if (raw == null || (typeof raw !== 'number' && typeof raw !== 'string') || (typeof raw === 'string' && !raw.trim())) return null;
    var n = Number(raw);
    return isFinite(n) ? Math.max(0, Math.min(100, n)) : null;
  }

  function isPend(a) {
    var r = radar();
    if (r && typeof r.isPending === 'function') return !!r.isPending(a);
    return !!(a && a.pending);
  }

  function attrOf(c, key) {
    return (c && c.attrs) ? c.attrs[key] : null;
  }

  function confOf(a, pend) {
    if (pend || !a) return 'pending';
    if (a.low || a.unverified) return 'low';
    return 'supported';
  }

  function arr8(v) {
    return [v, v, v, v, v, v, v, v];
  }
  function copyValue(value) {
    if (Array.isArray(value)) return value.map(copyValue);
    if (!value || typeof value !== 'object') return value;
    var out = {};
    for (var key in value) if (Object.prototype.hasOwnProperty.call(value, key) && key !== '__proto__') out[key] = copyValue(value[key]);
    return out;
  }

  function stageOf(c, G, ctx) {
    var chapter = ctx && ctx.chapter;
    var out = { scope: 'book', chapter: chapter == null ? null : chapter, id: null, attrs: null,
      sourceRefs: [], verified: false, hasQuantified: false, reason: chapter == null ? 'book-view' : 'no-observed-state' };
    if (!c || chapter == null) return out;
    var states = G.characterStates || [], chapters = ctx.atlas && ctx.atlas.chapters || G.chapters || [];
    var names = [], i;
    for (i = 0; i < chapters.length; i++) names.push(typeof chapters[i] === 'string' ? chapters[i] : chapters[i].name || chapters[i].chapter);
    if (!names.length) (G.events || []).forEach(function (event) { if (event.chapter && names.indexOf(event.chapter) < 0) names.push(event.chapter); });
    function indexOf(value) {
      if (typeof value === 'number' && isFinite(value)) return value;
      return names.indexOf(value);
    }
    var at = indexOf(chapter), matches = [];
    for (i = 0; i < states.length; i++) {
      var state = states[i], who = state && (state.character || state.name || state.characterId);
      if (!state || who == null || (who !== c.name && who !== c.id && who !== 'c:' + c.name)) continue;
      if (!Array.isArray(state.sourceRefs) || !state.sourceRefs.length || !Array.isArray(state.chapterRange) || state.chapterRange.length !== 2) continue;
      var range = state.chapterRange, start = indexOf(range[0]), end = indexOf(range[1]);
      var exact = range[0] === chapter && range[1] === chapter;
      if (exact || (at >= 0 && start >= 0 && end >= start && at >= start && at <= end)) matches.push(state);
    }
    if (matches.length !== 1) { if (matches.length > 1) out.reason = 'ambiguous-observed-states'; return out; }
    var selected = matches[0], count = 0, keys = attrKeys();
    for (i = 0; i < keys.length; i++) if (scoreOf(selected.attrs && selected.attrs[keys[i]]) !== null) count++;
    out.id = selected.id || null;
    out.summary = selected.summary || selected.state || null;
    out.sourceRefs = copyValue(selected.sourceRefs);
    out.verified = out.sourceRefs.every(function (ref) { return !!(ref && typeof ref === 'object' && (ref.verified === true || ref.status === 'verified')); });
    out.hasQuantified = count > 0;
    out.reason = count ? 'observed-snapshot' : 'unquantified-observed-state';
    if (count) { out.scope = 'chapter'; out.attrs = copyValue(selected.attrs); }
    return out;
  }

  function num(x) {
    if (x == null || (typeof x !== 'number' && typeof x !== 'string') || (typeof x === 'string' && !x.trim())) return null;
    return isFinite(Number(x)) ? Number(x) : null;
  }

  /* Narrative dimensions may be supplied by scene/core as a derived score map.
     A score map alone used to make every fallback (including a missing axis)
     look like a real value.  Accept an optional `known` / `pending` map so the
     same null semantics as CLRadar are preserved end-to-end. */
  function metaKnown(mo, key, index) {
    if (!mo || typeof mo !== 'object') return false;
    var known = mo.known;
    if (known && typeof known === 'object') {
      if (Array.isArray(known)) return known[index] !== false;
      if (Object.prototype.hasOwnProperty.call(known, key)) return known[key] !== false;
    }
    var pending = mo.pending;
    if (pending && typeof pending === 'object') {
      if (Array.isArray(pending)) return !pending[index];
      if (Object.prototype.hasOwnProperty.call(pending, key)) return !pending[key];
    }
    return true;
  }

  function rankOf(G, key, score, subjectName) {
    var chars = (G && G.characters) ? G.characters : [];
    var n = 0, higher = 0, i, s;
    for (i = 0; i < chars.length; i++) {
      /* A chapter snapshot replaces this subject for ranking. Its all-book
         self must not compete against it and create impossible rank N+1. */
      if (subjectName && chars[i].name === subjectName) {
        if (score !== null && score !== undefined) n++;
        continue;
      }
      s = scoreOf(attrOf(chars[i], key));
      if (s === null) continue;
      n++;
      if (score !== null && score !== undefined && s > score) higher++;
    }
    return { rank: (score === null || score === undefined ? null : 1 + higher), n: n };
  }

  function pctl(sorted, p) {
    if (!sorted.length) return null;
    var idx = (sorted.length - 1) * p;
    var lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
  }

  function campSize(chars, camp) {
    var n = 0, i, k, has;
    for (i = 0; i < chars.length; i++) {
      if (chars[i].camp !== camp) continue;
      has = false;
      for (k = 0; k < KEYS.length; k++) {
        if (scoreOf(attrOf(chars[i], KEYS[k])) !== null) { has = true; break; }
      }
      if (has) n++;
    }
    return n;
  }

  function metaRanks(chars, ctx) {
    var stamp = chars.map(function (c) {
      return [c.name, c.role, c.importance, (c.arc || []).length, scoreOf(attrOf(c, '道义')), scoreOf(attrOf(c, '野心'))].join(':');
    }).join('|');
    if (metaCache && metaCache.chars === chars && metaCache.metaOf === ctx.metaOf && metaCache.count === chars.length && metaCache.stamp === stamp) return metaCache;
    var scores = {}, i, j, k, mo;
    for (i = 0; i < chars.length; i++) {
      mo = null;
      try { mo = ctx.metaOf(chars[i].name); } catch (e0) { mo = null; }
      var normalized = null;
      if (mo && mo.score && typeof mo.score === 'object') {
        normalized = {};
        for (k = 0; k < MKEYS.length; k++) normalized[MKEYS[k]] = metaKnown(mo, MKEYS[k], k) ? num(mo.score[MKEYS[k]]) : null;
      }
      scores[chars[i].name] = normalized;
    }
    var ranks = {}, counts = {};
    for (k = 0; k < MKEYS.length; k++) {
      var mk = MKEYS[k], list = [], sc, v;
      for (i = 0; i < chars.length; i++) {
        sc = scores[chars[i].name];
        v = sc ? num(sc[mk]) : null;
        if (v !== null) list.push({ name: chars[i].name, v: v });
      }
      counts[mk] = list.length;
      var rmap = {}, higher;
      for (i = 0; i < list.length; i++) {
        higher = 0;
        for (j = 0; j < list.length; j++) if (list[j].v > list[i].v) higher++;
        rmap[list[i].name] = 1 + higher;
      }
      ranks[mk] = rmap;
    }
    var maxes = {};
    for (k = 0; k < MKEYS.length; k++) {
      var mx = 0;
      for (i = 0; i < chars.length; i++) {
        var sc2 = scores[chars[i].name];
        var v2 = sc2 ? num(sc2[MKEYS[k]]) : null;
        if (v2 !== null && v2 > mx) mx = v2;
      }
      maxes[MKEYS[k]] = mx > 100 ? mx : 100;   /* 叙事分可能 >100（戏份 370）：按全书最大值归一，否则冲出晶面 */
    }
    metaCache = { chars: chars, metaOf: ctx.metaOf, count: chars.length, stamp: stamp, ranks: ranks, counts: counts, scores: scores, maxes: maxes };
    return metaCache;
  }

  function buildArc(atlas, name) {
    var arc = { chapters: 0, hits: [], first: null, last: null, lines: [], events: [], known: false };
    if (!atlas || !atlas.ok) return arc;
    var chs = atlas.chapters || [], evs = atlas.events || [], i, j, e;
    arc.chapters = chs.length;
    var hits = [];
    for (i = 0; i < arc.chapters; i++) hits.push(0);
    for (i = 0; i < evs.length; i++) {
      e = evs[i];
      if (e.chapIdx === null || e.chapIdx === undefined ||
        e.chapIdx < 0 || e.chapIdx >= arc.chapters) continue;
      var cast = e.cast || [];
      for (j = 0; j < cast.length; j++) {
        if (cast[j] === name) {
          hits[e.chapIdx]++;
          arc.events.push({
            eventIdx: i,
            sourceEventIdx: (e.i !== undefined && e.i !== null) ? e.i : i,
            order: (e.order !== undefined && e.order !== null) ? e.order : null,
            chapIdx: e.chapIdx,
            chapter: e.chapName || e.chapter || null,
            title: e.title || null,
            kind: e.kind || null,
            lineIds: e.lineIds ? e.lineIds.slice(0) : []
          });
          if (arc.first === null || e.chapIdx < arc.first) arc.first = e.chapIdx;
          if (arc.last === null || e.chapIdx > arc.last) arc.last = e.chapIdx;
          break;
        }
      }
    }
    arc.hits = hits;
    var fp = null;
    try {
      if (typeof window !== 'undefined' && window.CLAtlasModel &&
        typeof window.CLAtlasModel.footprint === 'function') {
        fp = window.CLAtlasModel.footprint(atlas, name);
      }
    } catch (e1) { fp = null; }
    var defs = {}, ls = atlas.lines || [];
    for (i = 0; i < ls.length; i++) defs[ls[i].id] = ls[i];
    var fl = (fp && fp.lines) ? fp.lines : [];
    for (i = 0; i < fl.length; i++) {
      var d = fl[i] || {}, def = defs[d.lineId] || {};
      arc.lines.push({
        id: d.lineId,
        name: def.name || '',
        gen: (def.gen !== undefined && def.gen !== null) ? def.gen : 0,
        kind: def.kind || '',
        entryChap: d.entryChap,
        exitChap: d.exitChap,
        role: d.role
      });
    }
    arc.known = true;
    return arc;
  }

  function fail(c, dt) {
    built++;
    msLast = dt;
    return {
      ok: false,
      name: (c && c.name) ? c.name : '',
      camp: (c && c.camp) ? c.camp : null,
      attr: [],
      meta: null,
      metaReady: false,
      ghost: { book: arr8(null), camp: null, campName: (c && c.camp) ? c.camp : null, campN: 0 },
      band: { lo: arr8(null), hi: arr8(null) },
      peer: null,
      peers: [],
      arc: { chapters: 0, hits: [], first: null, last: null, lines: [], events: [], known: false },
      scoredCount: 0,
      mean: null,
      stats: { built: built, ms: dt }
    };
  }

  function build(c, G, ctx) {
    var t0 = now();
    try {
      ctx = ctx || {};
      G = G || {};
      var stage = stageOf(c, G, ctx), bookCharacter = c;
      if (stage.hasQuantified) {
        c = {};
        for (var field in bookCharacter) if (Object.prototype.hasOwnProperty.call(bookCharacter, field)) c[field] = bookCharacter[field];
        c.attrs = stage.attrs;
      }
      var chars = G.characters || [];
      var K = attrKeys(), Ens = attrEn();
      var attr = [], i, j, key, a, sc, pend, rk, pct;
      for (i = 0; i < 8; i++) {
        key = K[i];
        a = attrOf(c, key);
        sc = scoreOf(a);
        pend = sc === null || isPend(a);
        rk = rankOf(G, key, sc, stage.hasQuantified ? c.name : null);
        pct = null;
        if (sc !== null && ctx.bench && typeof ctx.bench.percentileOf === 'function') {
          try { pct = num(ctx.bench.percentileOf(key, sc)); } catch (e2) { pct = null; }
        }
        attr.push({
          key: key,
          en: Ens[i],
          score: sc,
          basis: a && typeof a.basis === 'string' ? a.basis : '',
          evidence: a && Array.isArray(a.evidence) ? copyValue(a.evidence) : [],
          sourceRefs: a && Array.isArray(a.sourceRefs) && a.sourceRefs.length ? copyValue(a.sourceRefs)
            : stage.hasQuantified && sc !== null ? copyValue(stage.sourceRefs) : [],
          sourceScope: a && Array.isArray(a.sourceRefs) && a.sourceRefs.length ? 'axis' : stage.hasQuantified && sc !== null ? 'stage' : null,
          known: sc !== null,
          conf: stage.hasQuantified && !stage.verified && sc !== null ? 'low' : confOf(a, pend),
          rank: rk.rank,
          n: rk.n,
          pct: pct
        });
      }

      var meta = null, metaReady = false;
      if (typeof ctx.metaOf === 'function' && c) {
        var mo = null;
        try { mo = ctx.metaOf(c.name); } catch (e3) { mo = null; }
        if (mo && mo.score && typeof mo.score === 'object') {
          var mr = metaRanks(chars, ctx), mk, msc;
          meta = [];
          for (i = 0; i < 8; i++) {
            mk = MKEYS[i];
            msc = metaKnown(mo, mk, i) ? num(mo.score[mk]) : null;
            var rawMetaScore = msc;
            if (msc !== null && mr.maxes && mr.maxes[mk] > 100) msc = Math.round(msc / mr.maxes[mk] * 100);
            meta.push({
              key: mk,
              en: MEN[i],
              score: msc,
              rawScore: rawMetaScore,
              scaleMax: mr.maxes[mk],
              known: msc !== null,
              conf: msc !== null ? 'supported' : 'pending',
              rank: (msc !== null && mr.ranks[mk] && mr.ranks[mk][c.name] !== undefined)
                ? mr.ranks[mk][c.name] : null,
              n: mr.counts[mk] || 0,
              pct: null
            });
          }
          for (i = 0; i < meta.length; i++) if (meta[i].known) metaReady = true;
        }
      }

      var bench = ctx.bench || null;
      var ghost = {
        book: arr8(null),
        camp: null,
        campName: (c && c.camp) ? c.camp : null,
        campN: 0
      };
      var campB = null;
      if (bench && c && c.camp && typeof window !== 'undefined' &&
        window.CLRadarBenchmark && typeof window.CLRadarBenchmark.resolveCamp === 'function') {
        try { campB = window.CLRadarBenchmark.resolveCamp(bench, c.camp); } catch (e4) { campB = null; }
      }
      if (campB) ghost.camp = arr8(null);
      var bandLo = arr8(null), bandHi = arr8(null), scores;
      for (i = 0; i < 8; i++) {
        key = K[i];
        if (bench && bench[key]) ghost.book[i] = num(bench[key].avg);
        if (campB && campB[key] && ghost.camp) ghost.camp[i] = num(campB[key].avg);
        scores = [];
        for (j = 0; j < chars.length; j++) {
          var cs = scoreOf(attrOf(chars[j], key));
          if (cs !== null) scores.push(cs);
        }
        scores.sort(function (x, y) { return x - y; });
        if (scores.length >= 4) {
          bandLo[i] = pctl(scores, 0.25);
          bandHi[i] = pctl(scores, 0.75);
        }
      }
      if (ghost.camp) ghost.campN = campSize(chars, c && c.camp ? c.camp : null);

      var peers = [];
      if (ctx.comparison && ctx.comparison.peers && ctx.comparison.peers.length) {
        var cp = ctx.comparison.peers, lim = Math.min(cp.length, 8);
        for (i = 0; i < lim; i++) {
          peers.push({ id: cp[i].id, name: cp[i].name });
        }
      }
      var peer = null;
      if (ctx.peerName) {
        var pc = null;
        for (i = 0; i < chars.length; i++) {
          if (chars[i].name === ctx.peerName) { pc = chars[i]; break; }
        }
        if (pc) {
          var peerStage = stageOf(pc, G, ctx), peerAttrs = peerStage.hasQuantified ? peerStage.attrs : pc.attrs;
          var pa = arr8(null), pd = arr8(null), ps;
          for (i = 0; i < 8; i++) {
            ps = scoreOf(peerAttrs && peerAttrs[K[i]]);
            pa[i] = ps;
            pd[i] = (ps !== null && attr[i].score !== null) ? attr[i].score - ps : null;
          }
          peer = { name: pc.name, attr: pa, delta: pd, stage: peerStage };
        }
      }

      var arc = buildArc(ctx.atlas, (c && c.name) ? c.name : '');

      var sum = 0, cnt = 0;
      for (i = 0; i < 8; i++) {
        if (attr[i].known) { sum += attr[i].score; cnt++; }
      }
      var dt = now() - t0;
      built++;
      msLast = dt;
      return {
        ok: true,
        name: (c && c.name) ? c.name : '',
        camp: (c && c.camp) ? c.camp : null,
        attr: attr,
        meta: meta,
        metaReady: metaReady,
        ghost: ghost,
        band: { lo: bandLo, hi: bandHi },
        peer: peer,
        peers: peers,
        arc: arc,
        scoredCount: cnt,
        mean: cnt ? sum / cnt : null,
        stage: stage,
        metaScope: 'book',
        stats: { built: built, ms: dt }
      };
    } catch (err) {
      return fail(c, now() - t0);
    }
  }

  function stats() {
    return { built: built, ms: msLast };
  }

  if (typeof window !== 'undefined') {
    window.CLGemModel = {
      name: 'gem-model',
      version: 'v80',
      build: build,
      rankOf: rankOf,
      stageOf: stageOf,
      invalidate: function () { metaCache = null; },
      stats: stats
    };
  }
})();
