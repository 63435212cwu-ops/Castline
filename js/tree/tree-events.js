/* Castline · tree-events.js — 事件选择层（window.CLTreeEvents，v46）
 *
 * 【v46 · orbit context 兼容（只增不改）】
 * 圆形星盘（plot-orbit）要把「事件落在哪条线的第几个 occurrence」画到环上，并允许悬停任一
 * occurrence 时读它的线/来源/长度/完整度 —— 这些查询**不得改动当前选中态**。因此本层在
 * 既有 API（pick/next/prev/clear/get/stats/domain/info/chapters/firstOfChapter）之上只加：
 *   · info(v, threadId?) —— 第二参可选；给了就用那条线的 occurrence 上下文，不给仍走选中态。
 *   · context(v, threadId?) —— 归一化的星盘上下文（含 occIndex/occCount/isShared/canonical）。
 *   · occurrences(v) —— 该事件所属的**每一条线/每一个 occurrence**（共享事件不丢上下文）。
 * 既有字段名与取值全部保留；新增字段只追加，不移动、不重命名。
 *
 * 【为什么需要】
 * v37 的聚焦只到「类」：按 1-7 点亮某一类事件的所有枝。用户看到一片同色的枝，仍不知道
 * 「这一根具体是哪一场戏」。v39 把交互下沉到**单个事件** —— 树不再只是配色，而是一份可
 * 逐条读取的故事索引：选中一条事件 → 树上只亮它那一根 twig，底部刻度条跳到它所在的章，
 * 详情卡报出标题 / 章节 / 引文 / 角色。
 *
 * 【为什么本层不画东西】
 * 「点亮哪根枝」是渲染，归 CLTreeFocus.solo(evIdx)（唯一挤出逻辑在那里，见 tree-focus.js）；
 * 本层的职责只有一件：**持有「当前选中哪个事件」这一个真相**，并把所有入口
 * （键盘上一条/下一条、刻度条点章、未来的点击）都收敛到 pick() 一条路上。
 *
 * 【数据唯一真相】
 * 事件表与章节表一律来自 CLStory.get()（tree-shape 也是从同一份 tree.events 长出 twig 的），
 * 树的 evIdx 域来自 CLTreeGhost.shapeOf().twigs[i].evIdx —— 事件 ↔ 枝一一映射。
 * 本层**不自己造事件表、不自己排序**：domain() 只是把 twigs 上的 evIdx 去重升序。
 *
 * 【与聚焦层的互斥】
 * 调 pick() → CLTreeFocus.solo()（清掉 kind 态）；用户若随后按 1-7 走 set(kind)，
 * CLTreeFocus 的 solo 态被清，本层在 sync() 里发现自己不再是焦点持有者，就把 evIdx 归 -1 ——
 * 「树上亮着一类、卡片说着另一条」这种两把标尺的状态不存在。
 *
 * 纪律：ES5 + IIFE + 'use strict'；禁 Math.random。
 */
(function () {
  'use strict';

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function str(v) { return v == null ? '' : String(v); }

  /* 来源标注：模型抽取不是原文已验证，措辞只到「来源」，不下「原文确证」。 */
  var SRC_LABEL = { model: '模型抽取', derived: '算法推导', mixed: '模型+推导', manual: '人工标注' };

  var evIdx = -1;                 // -1 = 未选中（唯一真相）
  var evThread = '';              // 被点枝的 threadId：共享事件选 occurrence 用（无则回退 canonical）

  /* ---- 取数：全部守空 ---- */
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
  /** 事件数组（CLStory 已按 order 稳定排序；下标 i === evIdx）。 */
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
  /** 域的成员判定：从 twigs 的 evIdx 集合来（拿不到 twigs 时退到事件表长度）。 */
  function inDomain(v) {
    if (v < 0) return false;
    var tw = twigs(), i;
    if (tw.length) {
      for (i = 0; i < tw.length; i++) if (tw[i] && Math.floor(num(tw[i].evIdx, -1)) === v) return true;
      return false;
    }
    var es = events();
    if (es.length) return v < es.length;
    return true;                                  // 两者都没就绪：乐观接受，渲染时自然归零
  }
  function ready() { return twigs().length > 0 && events().length > 0; }

  /* ---- 选择态 ---- */
  function focusEv() {
    var F = window.CLTreeFocus;
    if (!F || !F.get) return -1;
    var g = tryFn(function () { return F.get(); });
    return (g && typeof g.evIdx === 'number' && g.evIdx >= 0) ? g.evIdx : -1;
  }
  /** 外部接管回收：若聚焦层已不再 solo 我们记住的那个事件，就放弃自己的选中态。 */
  function sync() {
    if (evIdx >= 0 && focusEv() !== evIdx) { evIdx = -1; evThread = ''; }
    return evIdx;
  }
  function applySolo(v) {
    var F = window.CLTreeFocus;
    if (F && F.solo) tryFn(function () { return F.solo(v); });
  }

  /* ---- 对外：冻结接口 ---- */
  function pick(v, threadId) {
    sync();
    var n = +v;
    if (!isFinite(n)) { return clear(); }
    n = Math.floor(n);
    if (!inDomain(n)) { return clear(); }
    evIdx = n;
    evThread = (threadId == null) ? '' : str(threadId);   // 从某根枝进入：留住那根的 occurrence 上下文
    applySolo(n);
    return evIdx;
  }

  function clear() {
    sync();
    var owned = evIdx >= 0;
    evIdx = -1;
    evThread = '';
    if (owned) applySolo(-1);                    // 只清自己的；别人（set(kind)）的焦点不动
    return -1;
  }

  function next() {
    sync();
    var dom = domain();
    if (!dom.length) return evIdx;
    if (evIdx < 0) return pick(dom[0]);
    var i = indexOf(dom, evIdx);
    if (i < 0) return pick(dom[0]);
    if (i >= dom.length - 1) return evIdx;       // 到末尾停住，不回绕
    return pick(dom[i + 1]);
  }

  function prev() {
    sync();
    var dom = domain();
    if (!dom.length) return evIdx;
    if (evIdx < 0) return pick(dom[dom.length - 1]);
    var i = indexOf(dom, evIdx);
    if (i < 0) return pick(dom[dom.length - 1]);
    if (i <= 0) return evIdx;                    // 到开头停住
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

  /* ---- 内部工具（刻度条 / 详情卡复用，不再各算一套）---- */
  function indexOf(a, v) { for (var i = 0; i < a.length; i++) if (a[i] === v) return i; return -1; }

  /** 域：树上真实 twig 的 evIdx 去重升序。 */
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

  /** 含该事件的所有线（判定共享事件用：同一事件出现在 ≥2 条线才叫 shared）。
   *  纯取数，不写选中态。 */
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

  /** 含该事件的线：有上下文 threadId 就用上下文（被点的那根枝优先），
   *  否则取 depth 最深（最具体）的那条。共享事件按被点线取 occurrence。 */
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

  /** 事件在某条线的 occurrence 序号（0 基）；不在该线 → -1。occurrence 是「同一事件在本线的位置」。 */
  function occIndexOf(th, ix) {
    var evs = th && th.events;
    if (!evs) return -1;
    for (var k = 0; k < evs.length; k++) if (Math.floor(num(evs[k], -1)) === ix) return k;
    return -1;
  }

  /** 一条线的来源/长度/完整度说明（全部守空；未知就是未知，不编）。
   *  v46：追加 occurrence 字段（occIndex/occCount/isShared/canonical），既有字段原样保留。 */
  function lineInfo(ix, tid) {
    var th = threadOf(ix, tid);
    var t = tree();
    var src = th ? str(th.src) : (t ? str(t.src) : '');
    var known = !!(th && th.completionKnown === true);
    var comp = null;
    if (known && th.completion != null && isFinite(+th.completion)) comp = +th.completion;
    var len = th ? Math.floor(num(th.len, (th.events || []).length)) : 0;
    var occ = th ? occIndexOf(th, ix) : -1;
    var ownerN = ownersOf(ix).length;            // 同一事件属于几条线：>1 才是共享事件
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

  /** 事件详情（NaN 安全）：标题 / 章节 / 引文 / 角色名 + 来源标注。取不到返回 null。
   *  v46：第二参 threadId 可选 —— 星盘悬停某 occurrence 时按那条线取上下文，不动选中态；
   *  不传则沿用选中态记住的线（既有单参调用行为不变）。 */
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

  /** v46 星盘上下文：归一化「事件落在哪条线的第几个 occurrence」+ 线/来源/长度/完整度。
   *  不传 threadId 时沿用选中态；纯查询，不写 evIdx / 不调 solo。 */
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

  /** v46 共享事件审计：该事件所属的**每一条线/每一个 occurrence**（不丢任何上下文）。
   *  纯查询，不动选中态。返回按 depth 升序（主线在前）。 */
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
    var shared = out.length > 1;                 // 出现在 ≥2 条线才叫共享；每条 occurrence 同一口径
    for (i = 0; i < out.length; i++) out[i].isShared = shared;
    return out;
  }

  /** 章节表：[{ idx, name, n }]。优先 CLStory.get().chapters，缺则从事件现算（宁缺勿编）。 */
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

  /** 第 ci 章的第一个事件（按 evIdx 升序取最小）；没有 → -1。 */
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
    /* 复用小工具（刻度条 / 详情卡）：不改冻结四件的语义，只是把同一份取数公开一次。 */
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
