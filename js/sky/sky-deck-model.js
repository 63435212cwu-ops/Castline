/*! @role component · @owns js/sky/sky-deck-model.js · @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0 · @contract deep-sky/2
 * 剧情卡片叠 · 纯数据层：排序 / 分组 / 布局 / 窗口化 / 当回合命中。
 * 纯函数、不持状态、不碰 DOM；只吃星盘线数组，回卡片数组与几何量。
 */
(function (g) {
  'use strict';

  var DEF_M = { mainH: 40, branchH: 34, twigH: 30, openH: 260, gap: 2 };
  var DEF_PAD = 240;
  var TWIG_CAST = 12;
  var KINDS = { main: 1, named: 1, quiet: 1 };

  /* ---- 安全取值 ---- */
  function num(v) {
    var n = typeof v === 'number' ? v : (typeof v === 'string' && v !== '' ? +v : NaN);
    return isFinite(n) ? n : 0;
  }
  function numOr(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function str(v) { return typeof v === 'string' ? v : ''; }
  function bool(v) { return v ? true : false; }
  function arr(v) { return Array.isArray(v) ? v : []; }

  /* ---- 排序 ---- */
  function cmpStr(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }
  function byC0Id(a, b) { return a.c0 !== b.c0 ? (a.c0 - b.c0) : cmpStr(a.id, b.id); }
  function byC0EvId(a, b) {
    if (a.c0 !== b.c0) return a.c0 - b.c0;
    if (a.events !== b.events) return b.events - a.events;
    return cmpStr(a.id, b.id);
  }

  /* ---- 线 → 记录 ---- */
  function recOf(ln) {
    return {
      ln: ln, id: str(ln.id), kind: str(ln.kind),
      c0: num(ln.c0), c1: num(ln.c1),
      no0: num(ln.no0), no1: num(ln.no1),
      events: num(ln.events), mainId: str(ln.mainId)
    };
  }

  /* ---- 单线卡 ---- */
  function single(r, type, key, mainKey, depth, mainNo) {
    var ln = r.ln;
    return {
      key: key, type: type, id: r.id, mainKey: mainKey, title: str(ln.label),
      c0: r.c0, c1: r.c1, no0: r.no0, no1: r.no1,
      span: num(ln.span), events: r.events, cast: arr(ln.cast).slice(0),
      color: num(ln.color), gen: num(ln.gen),
      resolved: bool(ln.resolved), suspended: bool(ln.suspended), derived: bool(ln.derived),
      theme: str(ln.theme), eventIdx: arr(ln.eventIdx).slice(0),
      members: [], depth: depth, mainNo: mainNo, index: 0
    };
  }

  /* ---- 细支合成卡 ---- */
  function twig(list, key, mainKey, depth) {
    list.sort(byC0Id);
    var c0 = list[0].c0, c1 = list[0].c1, no0 = list[0].no0, no1 = list[0].no1;
    var ev = 0, members = [], cast = [], seen = {}, i, j;
    for (i = 0; i < list.length; i++) {
      var r = list[i];
      ev += r.events;
      members.push(r.id);
      if (r.c1 > c1) { c1 = r.c1; no1 = r.no1; }
      var cs = arr(r.ln.cast);
      for (j = 0; j < cs.length && cast.length < TWIG_CAST; j++) {
        var nm = str(cs[j]);
        if (!nm) continue;
        var kk = 'c' + nm;
        if (seen[kk]) continue;
        seen[kk] = 1;
        cast.push(nm);
      }
    }
    return {
      key: key, type: 'twig', id: '', mainKey: mainKey, title: '细支 ×' + list.length,
      c0: c0, c1: c1, no0: no0, no1: no1, span: 0, events: ev, cast: cast,
      color: 0, gen: 0, resolved: false, suspended: false, derived: false, theme: '',
      eventIdx: [], members: members, depth: depth, mainNo: 0, index: 0
    };
  }

  /* ---- build ---- */
  function build(lines, opts) {
    var src = arr(lines), i, j, n = src.length;
    var mains = [], others = [], byId = {};
    for (i = 0; i < n; i++) {
      var ln = src[i] || {};
      var kind = str(ln.kind);
      if (!KINDS[kind]) continue;
      var r = recOf(ln);
      if (kind === 'main') {
        mains.push(r);
        if (!byId.hasOwnProperty('k' + r.id)) byId['k' + r.id] = r;
      } else others.push(r);
    }
    var orphans = [], stray = [], m;
    for (i = 0; i < others.length; i++) {
      var o = others[i];
      m = o.mainId && byId.hasOwnProperty('k' + o.mainId) ? byId['k' + o.mainId] : null;
      if (!m) {
        if (o.kind === 'quiet') stray.push(o); else orphans.push(o);
        continue;
      }
      if (!m.grp) { m.grp = { named: [], quiet: [] }; }
      if (o.kind === 'quiet') m.grp.quiet.push(o); else m.grp.named.push(o);
    }

    mains.sort(byC0Id);
    orphans.sort(byC0Id);
    var cards = [], bi = 0;
    for (i = 0; i < mains.length; i++) {
      m = mains[i];
      while (bi < orphans.length && orphans[bi].c0 < m.c0) {
        var ob = orphans[bi++];
        cards.push(single(ob, 'branch', 'b:' + ob.id, '', 0, 0));
      }
      var mainKey = 'm:' + m.id, grp = m.grp;
      cards.push(single(m, 'main', mainKey, '', 0, i + 1));
      if (grp) {
        grp.named.sort(byC0EvId);
        for (j = 0; j < grp.named.length; j++) {
          cards.push(single(grp.named[j], 'branch', 'b:' + grp.named[j].id, mainKey, 1, 0));
        }
        if (grp.quiet.length) cards.push(twig(grp.quiet, 'q:' + m.id, mainKey, 1));
      }
    }
    while (bi < orphans.length) {
      var oz = orphans[bi++];
      cards.push(single(oz, 'branch', 'b:' + oz.id, '', 0, 0));
    }
    if (stray.length) cards.push(twig(stray, 'q:', '', 0));
    for (i = 0; i < cards.length; i++) cards[i].index = i;
    return cards;
  }

  /* ---- layout ---- */
  function layout(cards, openKey, m) {
    var list = arr(cards), o = m || {};
    var mainH = numOr(o.mainH, DEF_M.mainH), branchH = numOr(o.branchH, DEF_M.branchH);
    var twigH = numOr(o.twigH, DEF_M.twigH), openH = numOr(o.openH, DEF_M.openH);
    var gap = numOr(o.gap, DEF_M.gap);
    var n = list.length, tops = [], heights = [], y = 0, i;
    var want = openKey == null ? null : str(openKey);
    for (i = 0; i < n; i++) {
      var c = list[i] || {}, t = str(c.type);
      var h = t === 'main' ? mainH : (t === 'twig' ? twigH : branchH);
      if (want !== null && str(c.key) === want) h += openH;
      tops[i] = y;
      heights[i] = h;
      y += h + gap;
    }
    return { tops: tops, heights: heights, total: y };
  }

  /* ---- visibleRange（二分） ---- */
  function visibleRange(lay, scrollTop, viewH, pad) {
    var L = lay || {};
    var tops = arr(L.tops), heights = arr(L.heights);
    var n = Math.min(tops.length, heights.length);
    if (!n) return [0, -1];
    var p = pad == null ? DEF_PAD : num(pad);
    var top = num(scrollTop) - p, bot = num(scrollTop) + num(viewH) + p;
    var lo = 0, hi = n - 1, mid, i0 = 0, i1 = n - 1;
    while (lo <= hi) {
      mid = (lo + hi) >> 1;
      if (tops[mid] + heights[mid] >= top) { i0 = mid; hi = mid - 1; } else lo = mid + 1;
    }
    lo = 0; hi = n - 1;
    while (lo <= hi) {
      mid = (lo + hi) >> 1;
      if (tops[mid] <= bot) { i1 = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return [i0, i1];
  }

  /* ---- activeAt ---- */
  function activeAt(cards, c) {
    var out = [];
    if (c == null || c !== c) return out;
    var list = arr(cards);
    for (var i = 0; i < list.length; i++) {
      var cd = list[i] || {};
      if (num(cd.c0) <= c && c <= num(cd.c1)) out.push(str(cd.key));
    }
    return out;
  }

  g.CLSkyDeckModel = {
    build: build, layout: layout, visibleRange: visibleRange, activeAt: activeAt
  };
})(window);
