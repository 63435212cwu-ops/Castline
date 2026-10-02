/**
 * @role component
 * @owns js/atlas/atlas-startrack.js
 * @contract v90
 * v90 F5 章节星轨（briefs/v90/PLAN.md §1 第 3 层 · F5）。
 *
 * 一条横向 SVG 星轨取代素色滑条，视觉全由本模块绘制；原生 #aphCursor range 以 opacity:0
 * 覆盖在星轨上，继续承担拖动 / 点击 / 键盘 / 无障碍（语义与 v80 完全相同）。
 *
 * 编码（全部来自当前作品，缺档不补）：
 *   x      = 事件序号线性分布，与 #aphCursor 的 min..max 一一对应：
 *            x(i) = PAD + i/(N-1)·(W-2·PAD)，PAD = range 滑块半宽（css/atlas-startrack.css 同值）。
 *   星点   = 每个事件一颗；半径三档 = 参与人数（≤2 / 3–4 / ≥5）；kind ∈ 转折/抉择/高燃/高潮 → 更亮。
 *   堆高   = 同一章（连续事件）内的星点按「丘」堆起，丘高 ∝ 该章事件数 → 一眼看出哪里密。
 *   章刻度 = 每个不同章节在其首个事件处一根细刻度；章号标签按 ≥28px 间距、整齐步长抽稀（≤16 枚）。
 *   代次带 = 轨下 2px，按事件序号着当时主线的代次色 var(--cl-ann-gen-N)：
 *            主线 = CLApp.atlas.model().lines 里 kind==='main' 的线；事件 i 落在某主线 [首事件, 末事件]
 *            内即属该线，多线重叠取代次最大者（与年轮外环后画者在上一致）；gen>5 按年轮同法钳到 5。
 *            不属于任何主线的区段留空（不画成任何代次）。主线更替处留 2px 缺口 + 一根更替刻。
 *   游标   = 金色亮星 + 竖发丝线；游标变化只改 2 个属性，不重建星点；
 *            呼吸只读 CLAbyssBreath.snap().breath，挂既有 scene 帧钩子写属性（reduced / 静止 / 低档不呼吸）。
 *
 * 对外：window.CLAtlasStartrack = { mount, sync, setCursor, xOf, indexAt, chapterStarts, runs, stats }。
 * 不调用模型、不写数据、不开 rAF / 定时器。
 */
(function (g) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var KEY_KINDS = { '转折': 1, '抉择': 1, '高燃': 1, '高潮': 1 };
  var PAD = 8;            /* = ::-webkit-slider-thumb 宽 16px 的一半，见 css/atlas-startrack.css */
  var H = 44, BY = 25;    /* 轨高 / 基线 y */
  var STACK = 13;         /* 丘高上限 px */
  var LABEL_GAP = 28, LABEL_MAX = 16;
  var STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000];
  var host = null, input = null, svg = null, L = null;
  var G = null, M = null, W = 0, N = 0, span = 0;
  var starY = [], chapStarts = [], bandRuns = [], cursor = null, lastCurKey = '';
  var stat = { builds: 0, moves: 0, lastBuildMs: 0 };
  var ro = null, offFrame = null, lastBreath = -1, mq = null, wantG = null, wantM = null;

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function mk(tag, cls, parent) {
    var n = document.createElementNS(NS, tag);
    if (cls) n.setAttribute('class', cls);
    if (parent) parent.appendChild(n);
    return n;
  }
  function f1(v) { return (Math.round(v * 10) / 10).toString(); }
  function clampGen(x) { if (!isNum(x)) return 5; x = x | 0; return x < 0 ? 0 : (x > 5 ? 5 : x); }
  function xOf(i) { return N > 1 ? PAD + i * (W - 2 * PAD) / (N - 1) : PAD; }
  /* 章号：优先取章名里的真实编号（阿拉伯或中文数字「第两百五十八章」）；取不到才用出场序号 */
  var CN = { '零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9 };
  var CNU = { '十': 10, '百': 100, '千': 1000 };
  function cnNum(t) {
    var total = 0, cur = 0, i, ch, any = false;
    for (i = 0; i < t.length; i++) {
      ch = t.charAt(i);
      if (CN[ch] !== undefined) { cur = CN[ch]; any = true; }
      else if (CNU[ch]) { total += (cur || 1) * CNU[ch]; cur = 0; any = true; }
      else return null;
    }
    return any ? total + cur : null;
  }
  function chapNum(name, ordinal) {
    var m = /第\s*([0-9]+)\s*[章回节卷集幕]/.exec(name) || /^\s*([0-9]+)/.exec(name);
    if (m) return m[1];
    m = /第\s*([零〇一二两三四五六七八九十百千]+)\s*[章回节卷集幕]/.exec(name);
    var v = m ? cnNum(m[1]) : null;
    return v != null ? String(v) : String(ordinal + 1);
  }

  /* 主线代次：每个事件序号 → 当时主线（覆盖该序号的主线中代次最大者），再压成连续区段。 */
  function mainRuns(Graph, Model) {
    var n = Graph.events.length, owner = new Array(n), runs = [], i, k;
    var lines = Model && Model.ok && Model.lines ? Model.lines : [];
    var mEv = Model && Model.events ? Model.events : [];
    function gIndex(k2) { var e = mEv[k2]; return e && isNum(e.i) ? e.i : k2; }
    for (k = 0; k < lines.length; k++) {
      var ln = lines[k];
      if (!ln || ln.kind !== 'main' || !ln.eventIdxs || !ln.eventIdxs.length) continue;
      var lo = Infinity, hi = -Infinity, j;
      for (j = 0; j < ln.eventIdxs.length; j++) { var gi = gIndex(ln.eventIdxs[j]); if (gi < lo) lo = gi; if (gi > hi) hi = gi; }
      lo = Math.max(0, lo); hi = Math.min(n - 1, hi);
      for (i = lo; i <= hi; i++) if (!owner[i] || (isNum(ln.gen) ? ln.gen : -1) > (isNum(owner[i].gen) ? owner[i].gen : -1)) owner[i] = ln;
    }
    for (i = 0; i < n; i++) {
      var o = owner[i] || null, last = runs[runs.length - 1];
      if (last && last.line === o) { last.i1 = i; continue; }
      runs.push({ line: o, id: o ? o.id : null, gen: o ? clampGen(o.gen) : null, i0: i, i1: i });
    }
    return runs.filter(function (r) { return r.line; });
  }

  function clear() { while (svg.firstChild) svg.removeChild(svg.firstChild); }

  function build() {
    var t0 = g.performance ? performance.now() : 0, i, k;
    clear();
    starY = []; chapStarts = []; bandRuns = []; lastCurKey = '';
    N = G && G.events ? G.events.length : 0;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('width', String(W)); svg.setAttribute('height', String(H));
    svg.classList.toggle('is-empty', !N);
    L = {};
    if (!N) {
      L.empty = mk('g', 'st-empty', svg);
      /* 虚线基线在空态字样处断开（两段），不画遮挡块 */
      [[PAD, W / 2 - 56], [W / 2 + 72, W - PAD]].forEach(function (seg) {
        if (seg[1] - seg[0] < 4) return;
        var eb = mk('line', 'st-base st-base-empty', L.empty);
        eb.setAttribute('x1', f1(seg[0])); eb.setAttribute('x2', f1(seg[1])); eb.setAttribute('y1', String(BY)); eb.setAttribute('y2', String(BY));
      });
      var es = mk('path', 'st-empty-star', L.empty);
      es.setAttribute('d', 'M0 -6L1.5 -1.5L6 0L1.5 1.5L0 6L-1.5 1.5L-6 0L-1.5 -1.5Z');
      es.setAttribute('transform', 'translate(' + f1(W / 2 - 44) + ' ' + (BY - 1) + ')');
      var et = mk('text', 'st-empty-text', L.empty);
      et.setAttribute('x', f1(W / 2 - 32)); et.setAttribute('y', String(BY + 3.5));
      et.textContent = '尚无事件 · 星轨待载';
      stat.builds++; stat.lastBuildMs = g.performance ? performance.now() - t0 : 0;
      return;
    }
    span = N > 1 ? (W - 2 * PAD) / (N - 1) : 0;
    /* 章：连续同章为一段（堆丘用）；不同章节各在首个事件处一根刻度 */
    var seen = Object.create(null), segs = [], cur = null;
    for (i = 0; i < N; i++) {
      var ch = G.events[i] && G.events[i].chapter != null ? String(G.events[i].chapter) : '';
      if (!cur || cur.ch !== ch) { cur = { ch: ch, i0: i, i1: i }; segs.push(cur); } else cur.i1 = i;
      if (ch && !seen[ch]) { seen[ch] = 1; chapStarts.push({ i: i, name: ch, ord: chapStarts.length }); }
    }
    var maxLevel = 0;
    segs.forEach(function (s) { var lv = Math.floor((s.i1 - s.i0) / 2); if (lv > maxLevel) maxLevel = lv; });
    var dy = maxLevel ? Math.min(5, STACK / maxLevel) : 0;
    segs.forEach(function (s) { for (var j = s.i0; j <= s.i1; j++) starY[j] = BY - 4 - dy * Math.min(j - s.i0, s.i1 - j); });

    var x0 = xOf(0), x1 = xOf(N - 1), half = N > 1 ? Math.min(span / 2, PAD - 1) : PAD - 1;
    L.band = mk('g', 'st-band', svg);
    L.ticks = mk('g', 'st-ticks', svg);
    L.labels = mk('g', 'st-labels', svg);
    var base = mk('line', 'st-base', svg);
    base.setAttribute('x1', f1(x0 - half)); base.setAttribute('x2', f1(x1 + half)); base.setAttribute('y1', String(BY)); base.setAttribute('y2', String(BY));
    L.progress = mk('line', 'st-progress', svg);
    L.progress.setAttribute('y1', String(BY)); L.progress.setAttribute('y2', String(BY));
    L.progress.setAttribute('x1', f1(x0 - half)); L.progress.setAttribute('x2', f1(x0 - half));
    /* 星丘剪影：各章星点连成的淡丘（一条 path，完全由星点坐标导出，不另造数据） */
    var ridge = '';
    segs.forEach(function (s) {
      if (s.i1 - s.i0 < 2) return;
      ridge += 'M' + f1(xOf(s.i0)) + ' ' + (BY - 0.5);
      for (var j = s.i0; j <= s.i1; j++) ridge += 'L' + f1(xOf(j)) + ' ' + f1(starY[j]);
      ridge += 'L' + f1(xOf(s.i1)) + ' ' + (BY - 0.5) + 'Z';
    });
    if (ridge) { var rp = mk('path', 'st-ridge', svg); rp.setAttribute('d', ridge); }
    L.stars = mk('g', 'st-stars', svg);

    /* 代次带：每个代次色一条 path（多段矩形子路径），更替处两侧各让 1px 形成缺口 */
    bandRuns = mainRuns(G, M);
    var byGen = {}, notch = '';
    bandRuns.forEach(function (r, idx) {
      var a = xOf(r.i0) - (r.i0 === 0 ? half : span / 2), b = xOf(r.i1) + (r.i1 === N - 1 ? half : span / 2);
      var prev = bandRuns[idx - 1], next = bandRuns[idx + 1];
      if (prev && prev.i1 === r.i0 - 1) a += 1;
      if (next && next.i0 === r.i1 + 1) b -= 1;
      if (b - a < 0.6) b = a + 0.6;
      r.x0 = a; r.x1 = b;
      var key = String(r.gen);
      if (!byGen[key]) byGen[key] = { d: '', runs: [] };
      byGen[key].d += 'M' + f1(a) + ' ' + (BY + 2.5) + 'H' + f1(b) + 'V' + (BY + 4.5) + 'H' + f1(a) + 'Z';
      byGen[key].runs.push(r.i0 + '-' + r.i1);
      if (prev) { var nx = xOf(r.i0) - span / 2; notch += 'M' + f1(nx) + ' ' + (BY + 1) + 'V' + (BY + 7.5); }
    });
    Object.keys(byGen).forEach(function (key) {
      var p = mk('path', 'st-gen st-gen-' + key, L.band);
      p.setAttribute('d', byGen[key].d);
      p.setAttribute('data-gen', key);
      p.setAttribute('data-runs', byGen[key].runs.join(','));
    });
    if (notch) { var np = mk('path', 'st-handoff', L.band); np.setAttribute('d', notch); }

    /* 章刻度 + 抽稀章号 */
    var tickX = chapStarts.map(function (c) { return c.i === 0 ? x0 - half : xOf(c.i) - span / 2; });
    /* 章很多（平均间距 <6px）时刻度退成短而淡的梳齿，不盖住代次带；数量仍是每章一根 */
    var dense = chapStarts.length > 1 && (W - 2 * PAD) / chapStarts.length < 6;
    svg.classList.toggle('is-dense', dense);
    chapStarts.forEach(function (c, j) {
      var t = mk('line', 'st-tick', L.ticks);
      t.setAttribute('x1', f1(tickX[j])); t.setAttribute('x2', f1(tickX[j]));
      t.setAttribute('y1', String(dense ? BY + 5 : BY - 2)); t.setAttribute('y2', String(dense ? BY + 8 : BY + 7));
      t.setAttribute('data-chapter', c.name);
    });
    /* 章号：取最小的整齐步长（1/2/5/10…），使该步长的全部章号两两间距 ≥28px 且不超过 16 枚；
       步长 ≥5 时补标首章「1」（与第一枚间距够才补）。刻度本身永远每章一根，不抽稀。 */
    var picks = [];
    for (k = 0; k < STEPS.length; k++) {
      var step = STEPS[k], cand = [], ok = true, j2;
      chapStarts.forEach(function (c, j) { if ((j + 1) % step === 0) cand.push(j); });
      if (step === 1 || !cand.length) cand = step === 1 ? chapStarts.map(function (c, j) { return j; }) : [0];
      for (j2 = 1; j2 < cand.length; j2++) if (tickX[cand[j2]] - tickX[cand[j2 - 1]] < LABEL_GAP) { ok = false; break; }
      if (step >= 5 && cand[0] !== 0 && tickX[cand[0]] - tickX[0] >= LABEL_GAP) cand.unshift(0);
      picks = cand;
      if (ok && cand.length <= LABEL_MAX) break;
    }
    picks.forEach(function (j) {
      var tx = mk('text', 'st-chap', L.labels);
      tx.setAttribute('x', f1(Math.max(6, Math.min(W - 6, tickX[j]))));
      tx.setAttribute('y', String(H - 2));
      tx.textContent = chapNum(chapStarts[j].name, j);
    });

    /* 星点：大小三档 = 参与人数；关键 kind 更亮 */
    var rScale = Math.max(0.5, Math.min(1, span / 7));
    for (i = 0; i < N; i++) {
      var e = G.events[i] || {}, cast = Array.isArray(e.characters) ? e.characters.length : 0;
      var tier = cast >= 5 ? 3 : (cast >= 3 ? 2 : 1);
      var s = mk('circle', 'st-star t' + tier + (KEY_KINDS[e.kind] ? ' is-key' : ''), L.stars);
      s.setAttribute('cx', f1(xOf(i))); s.setAttribute('cy', f1(starY[i]));
      s.setAttribute('r', f1((tier === 3 ? 2.8 : tier === 2 ? 2.1 : 1.5) * rScale));
      s.setAttribute('data-i', String(i));
    }

    L.ghost = mk('line', 'st-ghost', svg);
    L.ghost.setAttribute('y1', '3'); L.ghost.setAttribute('y2', String(BY + 7));
    L.cur = mk('g', 'st-cur', svg);
    var cl = mk('line', 'st-cur-line', L.cur);
    cl.setAttribute('x1', '0'); cl.setAttribute('x2', '0'); cl.setAttribute('y1', '2'); cl.setAttribute('y2', String(BY + 7));
    L.mark = mk('g', 'st-cur-mark', L.cur);
    L.halo = mk('circle', 'st-cur-halo', L.mark); L.halo.setAttribute('r', '5.6');
    var cs = mk('path', 'st-cur-star', L.mark);
    cs.setAttribute('d', 'M0 -5.2L1.25 -1.25L5.2 0L1.25 1.25L0 5.2L-1.25 1.25L-5.2 0L-1.25 -1.25Z');
    stat.builds++; stat.lastBuildMs = g.performance ? performance.now() - t0 : 0;
    place(true);
  }

  function place(force) {
    if (!L || !L.cur) return;
    var c = cursor != null && N ? Math.max(0, Math.min(N - 1, cursor)) : null, key = c == null ? 'none' : String(c);
    if (!force && key === lastCurKey) return;
    lastCurKey = key; stat.moves++;
    svg.classList.toggle('has-cursor', c != null);
    if (c == null) return;
    L.cur.setAttribute('transform', 'translate(' + f1(xOf(c)) + ' 0)');
    L.mark.setAttribute('transform', 'translate(0 ' + f1(starY[c]) + ')');
    L.progress.setAttribute('x2', f1(xOf(c)));
  }

  function quiet() {
    try {
      if (g.CLAtlasState && CLAtlasState.get().reduced) return true;
      if (mq && mq.matches) return true;
      if (g.CLOrbit3DTier && CLOrbit3DTier.get() === 'low') return true;
    } catch (e) {}
    return false;
  }
  function frame() {
    if (!L || !L.halo || cursor == null || !g.CLAbyssBreath) return;
    var q = quiet() ? -2 : Math.round(CLAbyssBreath.snap().breath * 16) / 16;
    if (q === lastBreath) return;
    lastBreath = q;
    L.halo.setAttribute('opacity', q < 0 ? '0.55' : (0.34 + 0.42 * q).toFixed(3));
  }
  function hookFrame() {
    if (offFrame || !g.CLApp || !CLApp.scene) return;
    var sc = CLApp.scene();
    if (sc && typeof sc.registerFrameHook === 'function') offFrame = sc.registerFrameHook(frame);
  }

  function widthNow() { var r = host.getBoundingClientRect(); return Math.round(r.width); }
  function indexAtLocal(lx) { if (!N) return null; if (N === 1) return 0; return Math.max(0, Math.min(N - 1, Math.round((lx - PAD) / span))); }
  function hover(e) {
    if (!L || !L.ghost || !N) return;
    var r = host.getBoundingClientRect(), i = indexAtLocal(e.clientX - r.left), ev = G.events[i] || {};
    L.ghost.setAttribute('x1', f1(xOf(i))); L.ghost.setAttribute('x2', f1(xOf(i)));
    svg.classList.add('is-hover');
    var t = '#' + (ev.order != null ? ev.order : i + 1) + ' · ' + (ev.chapter || '未分章') + (ev.title ? ' · ' + ev.title : '');
    if (input.title !== t) input.title = t;
  }

  function mount(h, range) {
    if (host === h && svg) return true;
    if (!h || !range) return false;
    host = h; input = range;
    svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'aph-startrack');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    host.insertBefore(svg, input);
    try { mq = g.matchMedia ? g.matchMedia('(prefers-reduced-motion: reduce)') : null; } catch (e) { mq = null; }
    if (g.ResizeObserver) { ro = new ResizeObserver(function () { if (wantG) sync(wantG, wantM); }); ro.observe(host); }
    else g.addEventListener('resize', function () { if (wantG) sync(wantG, wantM); });
    input.addEventListener('pointermove', hover);
    input.addEventListener('pointerleave', function () { if (svg) svg.classList.remove('is-hover'); });
    return true;
  }

  /* 只有作品 / 模型 / 宽度变了才重建；其余调用（每次 render）只是廉价比较。 */
  function sync(Graph, Model) {
    if (!svg || !Graph) return false;
    wantG = Graph; wantM = Model || null;
    var w = widthNow();
    if (w < 24) return false;           /* 隐藏态（display:none / 未布局）不建，等 ResizeObserver */
    if (Graph === G && (Model || null) === M && w === W) return false;
    G = Graph; M = Model || null; W = w;
    build(); hookFrame();
    return true;
  }
  function setCursor(i) { cursor = i == null || !isNum(Number(i)) ? null : Math.floor(Number(i)); place(false); frame(); }

  g.CLAtlasStartrack = {
    mount: mount,
    sync: sync,
    setCursor: setCursor,
    mounted: function () { return !!svg; },
    /* 事件序号 → 视口 x（测试 / 宿主用；与 range 映射同一公式） */
    xOf: function (i) { if (!host) return null; return host.getBoundingClientRect().left + xOf(i); },
    indexAt: function (clientX) { if (!host) return null; return indexAtLocal(clientX - host.getBoundingClientRect().left); },
    chapterStarts: function () { return chapStarts.map(function (c) { return c.i; }); },
    runs: function () { return bandRuns.map(function (r) { return { id: r.id, gen: r.gen, i0: r.i0, i1: r.i1, x0: r.x0, x1: r.x1 }; }); },
    stats: function () {
      return { mounted: !!svg, N: N, width: W, pad: PAD, chapters: chapStarts.length, stars: L && L.stars ? L.stars.childNodes.length : 0,
        ticks: L && L.ticks ? L.ticks.childNodes.length : 0, labels: L && L.labels ? L.labels.childNodes.length : 0,
        bands: bandRuns.length, dom: svg ? svg.getElementsByTagName('*').length + 1 : 0, builds: stat.builds, moves: stat.moves,
        lastBuildMs: Math.round(stat.lastBuildMs * 100) / 100, cursor: cursor, frameHook: !!offFrame, empty: !N };
    }
  };
})(window);
