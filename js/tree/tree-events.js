(function () {
  'use strict';

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function str(v) { return v == null ? '' : String(v); }

  var SRC_LABEL = { model: '模型抽取', derived: '算法推导', mixed: '模型+推导', manual: '人工标注' };

  var evIdx = -1;
  var evThread = '';

  function tree() {
    var s = window.CLStory;
    if (!s || !s.get) return null;
    var t = tryFn(s.get);
    return (t && t.ok === true) ? t : null;
  }
  function twigs() {
    var g = window.CLTreeGhost;
    if (!g || !g.shapeOf) return [];
    var s = tryFn(g.shapeOf);
    return (s && s.twigs) ? s.twigs : [];
  }
  function events() {
    var t = tree();
    return (t && t.events) ? t.events : [];
  }
  function evAt(v) {
    var es = events(), i;
    for (i = 0; i < es.length; i++) {
      if (es[i] && Math.floor(num(es[i].i, -1)) === v) return es[i];
    }
    return null;
  }
  function inDomain(v) {
    if (v < 0) return false;
    var tw = twigs(), i;
    if (tw.length) {
      for (i = 0; i < tw.length; i++) if (tw[i] && Math.floor(num(tw[i].evIdx, -1)) === v) return true;
      return false;
    }
    var es = events();
    if (es.length) return v < es.length;
    return true;
  }
  function ready() { return twigs().length > 0 && events().length > 0; }

  function focusEv() {
    var F = window.CLTreeFocus;
    if (!F || !F.get) return -1;
    var g = tryFn(function () { return F.get(); });
    return (g && typeof g.evIdx === 'number' && g.evIdx >= 0) ? g.evIdx : -1;
  }
  function sync() {
    if (evIdx >= 0 && focusEv() !== evIdx) { evIdx = -1; evThread = ''; }
    return evIdx;
  }
  function applySolo(v) {
    var F = window.CLTreeFocus;
    if (F && F.solo) tryFn(function () { return F.solo(v); });
  }

  function pick(v, threadId) {
    sync();
    var n = +v;
    if (!isFinite(n)) { return clear(); }
    n = Math.floor(n);
    if (!inDomain(n)) { return clear(); }
    evIdx = n;
    evThread = (threadId == null) ? '' : str(threadId);
    applySolo(n);
    return evIdx;
  }

  function clear() {
    sync();
    var owned = evIdx >= 0;
    evIdx = -1;
    evThread = '';
    if (owned) applySolo(-1);
    return -1;
  }

  function next() {
    sync();
    var dom = domain();
    if (!dom.length) return evIdx;
    if (evIdx < 0) return pick(dom[0]);
    var i = indexOf(dom, evIdx);
    if (i < 0) return pick(dom[0]);
    if (i >= dom.length - 1) return evIdx;
    return pick(dom[i + 1]);
  }

  function prev() {
    sync();
    var dom = domain();
    if (!dom.length) return evIdx;
    if (evIdx < 0) return pick(dom[dom.length - 1]);
    var i = indexOf(dom, evIdx);
    if (i < 0) return pick(dom[dom.length - 1]);
    if (i <= 0) return evIdx;
    return pick(dom[i - 1]);
  }

  function get() {
    sync();
    var e = (evIdx >= 0) ? evAt(evIdx) : null;
    var L = e ? lineInfo(evIdx, evThread) : null;
    return {
      evIdx: evIdx,
      threadId: evThread,
      ready: ready(),
      kind: e ? str(e.kind) : '',
      chapter: e ? str(e.chapter) : '',
      title: e ? str(e.title) : '',
      /* v46 追加：当前选中事件的星盘线上下文（未选中时全空/零） */
      line: L ? L.line : '',
      source: L ? L.source : '',
      len: L ? L.len : 0,
      completion: L ? L.completion : null,
      completionKnown: L ? L.completionKnown : false,
      occIndex: L ? L.occIndex : -1,
      occCount: L ? L.occCount : 0,
      isShared: L ? L.isShared : false
    };
  }

  function stats() {
    sync();
    var F = window.CLTreeFocus;
    var fs = (F && F.stats) ? tryFn(F.stats) : null;
    var n = 0, verts = 0, dc = 0;
    if (evIdx >= 0 && fs) { n = num(fs.n, 0); verts = num(fs.verts, 0); dc = num(fs.drawcalls, 0); }
    return { ready: ready(), evIdx: evIdx, n: n, tubes: n, verts: verts, drawcalls: dc };
  }

  function indexOf(a, v) { for (var i = 0; i < a.length; i++) if (a[i] === v) return i; return -1; }

  function domain() {
    var tw = twigs(), i, seen = {}, out = [], v;
    for (i = 0; i < tw.length; i++) {
      if (!tw[i]) continue;
      v = Math.floor(num(tw[i].evIdx, -1));
      if (v >= 0 && !seen[v]) { seen[v] = 1; out.push(v); }
    }
    out.sort(function (a, b) { return a - b; });
    return out;
  }

  function ownersOf(ix) {
    var t = tree();
    var th = (t && t.threads) ? t.threads : [];
    var out = [], i, j, evs;
    for (i = 0; i < th.length; i++) {
      evs = th[i] && th[i].events;
      if (!evs) continue;
      for (j = 0; j < evs.length; j++) if (Math.floor(num(evs[j], -1)) === ix) { out.push(th[i]); break; }
    }
    return out;
  }

  function threadOf(ix, tid) {
    var t = tree();
    var th = (t && t.threads) ? t.threads : [];
    var hit = null, hitDepth = -Infinity, i, j, evs, d, id;
    function owns(x) {
      evs = x && x.events;
      if (!evs) return false;
      for (j = 0; j < evs.length; j++) if (Math.floor(num(evs[j], -1)) === ix) return true;
      return false;
    }
    if (tid) {
      id = str(tid);
      for (i = 0; i < th.length; i++) if (str(th[i] && th[i].id) === id && owns(th[i])) return th[i];
    }
    for (i = 0; i < th.length; i++) {
      if (!owns(th[i])) continue;
      d = num(th[i].depth, 0);
      if (d > hitDepth) { hit = th[i]; hitDepth = d; }
    }
    return hit;
  }

  function occIndexOf(th, ix) {
    var evs = th && th.events;
    if (!evs) return -1;
    for (var k = 0; k < evs.length; k++) if (Math.floor(num(evs[k], -1)) === ix) return k;
    return -1;
  }

  function lineInfo(ix, tid) {
    var th = threadOf(ix, tid);
    var t = tree();
    var src = th ? str(th.src) : (t ? str(t.src) : '');
    var known = !!(th && th.completionKnown === true);
    var comp = null;
    if (known && th.completion != null && isFinite(+th.completion)) comp = +th.completion;
    var len = th ? Math.floor(num(th.len, (th.events || []).length)) : 0;
    var occ = th ? occIndexOf(th, ix) : -1;
    var ownerN = ownersOf(ix).length;
    return {
      threadId: th ? str(th.id) : '',
      line: th ? str(th.title) : '',
      source: SRC_LABEL[src] || (src ? src : '未标注'),
      srcRaw: src,
      status: th && th.topologyStatus != null ? str(th.topologyStatus) : '',
      completion: comp,
      completionKnown: known,
      len: len,
      metric: 'event-count',
      occIndex: occ,
      occCount: len,
      isShared: occ >= 0 && ownerN > 1,
      canonical: !tid
    };
  }

  function info(v, threadId) {
    var ix = (v == null) ? evIdx : Math.floor(+v);
    var e = evAt(ix);
    if (!e) return null;
    var names = [], i;
    if (e.cast && e.cast.length) { for (i = 0; i < e.cast.length; i++) names.push(str(e.cast[i])); }
    else if (e.characters && e.characters.length) { for (i = 0; i < e.characters.length; i++) names.push(str(e.characters[i])); }
    var tid = (threadId == null) ? evThread : str(threadId);
    var L = lineInfo(ix, tid);
    return {
      evIdx: Math.floor(num(e.i, -1)), chapIdx: Math.floor(num(e.chapIdx, 0)),
      kind: str(e.kind), chapter: str(e.chapter), title: str(e.title),
      quote: str(e.quote), characters: names, threadId: L.threadId,
      line: L.line, source: L.source, metric: L.metric,
      completion: L.completion, completionKnown: L.completionKnown,
      status: L.status, len: L.len,
      srcRaw: L.srcRaw, occIndex: L.occIndex, occCount: L.occCount,
      isShared: L.isShared, canonical: L.canonical
    };
  }

  function context(v, threadId) {
    var ix = (v == null) ? evIdx : Math.floor(+v);
    var tid = (threadId == null) ? evThread : str(threadId);
    var L = lineInfo(ix, tid);
    return {
      evIdx: ix,
      threadId: L.threadId, line: L.line,
      source: L.source, srcRaw: L.srcRaw, status: L.status,
      len: L.len, metric: L.metric,
      completion: L.completion, completionKnown: L.completionKnown,
      occIndex: L.occIndex, occCount: L.occCount,
      isShared: L.isShared, canonical: L.canonical
    };
  }

  function occurrences(v) {
    var ix = Math.floor(+v);
    if (!isFinite(ix)) return [];
    var t = tree();
    var th = (t && t.threads) ? t.threads : [];
    var out = [], i, occ, src, known, comp, len;
    for (i = 0; i < th.length; i++) {
      occ = occIndexOf(th[i], ix);
      if (occ < 0) continue;
      src = str(th[i].src);
      known = !!(th[i].completionKnown === true);
      comp = (known && th[i].completion != null && isFinite(+th[i].completion)) ? +th[i].completion : null;
      len = Math.floor(num(th[i].len, (th[i].events || []).length));
      out.push({
        threadId: str(th[i].id), line: str(th[i].title),
        source: SRC_LABEL[src] || (src ? src : '未标注'), srcRaw: src,
        status: th[i].topologyStatus != null ? str(th[i].topologyStatus) : '',
        len: len, metric: 'event-count',
        completion: comp, completionKnown: known,
        occIndex: occ, occCount: len, isShared: false,
        depth: num(th[i].depth, 0), canonical: false
      });
    }
    out.sort(function (a, b) { return a.depth - b.depth; });
    var shared = out.length > 1;
    for (i = 0; i < out.length; i++) out[i].isShared = shared;
    return out;
  }

  function chapters() {
    var t = tree();
    var CH = (t && t.chapters) ? t.chapters : null;
    var out = [], i;
    if (CH && CH.length) {
      for (i = 0; i < CH.length; i++) {
        var c = CH[i] || {};
        out.push({ idx: Math.floor(num(c.idx, i)), name: str(c.name), n: Math.floor(num(c.n, 0)) });
      }
      return out;
    }
    var es = events(), seen = {};
    for (i = 0; i < es.length; i++) {
      var ci = Math.floor(num(es[i] && es[i].chapIdx, -1));
      if (ci < 0) continue;
      if (!seen[ci]) { seen[ci] = { idx: ci, name: str(es[i].chapter), n: 0 }; out.push(seen[ci]); }
      seen[ci].n += 1;
    }
    out.sort(function (a, b) { return a.idx - b.idx; });
    return out;
  }

  function firstOfChapter(ci) {
    var dom = domain(), i, e;
    for (i = 0; i < dom.length; i++) {
      e = evAt(dom[i]);
      if (e && Math.floor(num(e.chapIdx, -1)) === Math.floor(+ci)) return dom[i];
    }
    return -1;
  }

  var API = {
    name: 'tree-events',
    pick: pick,
    next: next,
    prev: prev,
    clear: clear,
    get: get,
    stats: stats,
    domain: domain,
    info: info,
    chapters: chapters,
    firstOfChapter: firstOfChapter,
    /* v46 星盘接口（纯查询，只增不改）：上下文归一化 + 共享事件 occurrence 审计 */
    context: context,
    occurrences: occurrences
  };
  window.CLTreeEvents = API;
})();
