/* Castline · plot-hud.js — 第二条信息流：剧情线谱 HUD（D 面 · v30.0）
 * 契约：js/PLOT-CONTRACT.md 第 5 节。DOM 自注入，index.html 一行不改。
 *
 * 为什么是「另一种信息流」：3D 剧情树把同一棵树读成**空间**（谁从谁身上长出来、往哪个方位岔开），
 * 这一层把它读成**时间**（横轴是章节，一条线一条泳道，谁在第几章接的手、谁在第几章断掉）。
 * 两种读法共用 CLStory 的同一棵树，谁都不重新算 —— 所以两边永远不会互相打脸。
 *
 * 成本纪律：这一层不进每帧循环。动效全部交给 CSS（脉冲 / 入场），JS 只在 setTree / open / resize
 * 三个时刻各跑一次。所以它不需要 degrade 阶梯 —— 没有逐帧成本可降。
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- 常量
  // 剧情类型色：与 app.css 的 .tag.kind-* / .tl-legend .k-* 同一套，不自造 hex（契约 §0.7）
  var KCOL = {
    '高燃': '#ffd166', '转折': '#ffb45c', '抉择': '#c8a7ff', '冲突': '#ff5d73',
    '关系': '#ff9ad5', '领悟': '#7af0c8', '日常': '#9a92b8'
  };
  var KORD = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];

  var STEP = 20;        // 泳道行距（px）：主干 4px 粗、支线 2px，20px 行距刚好让刻点（≤10px）不咬到邻道
  var PADT = 26;        // 泳道区上留白：章节轴 14px + 最上一条泳道的线名一行，少于这个数字线名会压到轴上
  var MINCH = 30;       // 每章最小像素宽：低于这个数字刻点会糊成一坨，于是改为横向可滚（契约 §5.6）
  var MAXTICK = 3200;   // 刻点上限：再多 DOM 就不划算了，超出时截断并在自证行里明说

  var CALM = false;
  try { CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e0) {}

  // ---------------------------------------------------------------- 小工具
  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function hex(c) {
    if (typeof c === 'string') return c;
    if (typeof c !== 'number' || !isFinite(c)) return '#9a92b8';
    return '#' + ('000000' + ((c | 0) & 0xffffff).toString(16)).slice(-6);
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function kcol(k) { return KCOL[k] || KCOL['日常']; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function pName(v) { return v && typeof v === 'object' ? (typeof v.name === 'string' ? v.name : (typeof v.label === 'string' ? v.label : (typeof v.id === 'string' ? v.id : ''))) : (typeof v === 'string' || typeof v === 'number' ? String(v) : ''); }
  function pList(v) { var a = Array.isArray(v) ? v : (v == null ? [] : [v]), o = Object.create(null), r = [], i, n; for (i = 0; i < a.length; i++) { n = pName(a[i]).trim(); if (n && !o[n]) { o[n] = 1; r.push(n); } } return r; }
  function eIdx(v) { var n; if (typeof v === 'number') n = v; else if (typeof v === 'string' && v.trim()) n = +v; else return -1; return isFinite(n) && n >= 0 && Math.floor(n) === n ? n : -1; }
  function pStatus(t) { var s = String(t && (t.status != null ? t.status : t.state) || '').toLowerCase(), yesR = s === 'resolved' || !!(t && t.resolved === true), yesS = s === 'suspended' || !!(t && t.suspended === true); if (yesR && yesS) return 'conflict'; if (yesR) return 'resolved'; if (yesS) return 'suspended'; return 'unknown'; }
  function namesOf(e) { return pList(e && (e.cast || e.participants || e.characters)); }
  function lineInfo(tree, t) {
    var src = Array.isArray(t && t.events) ? t.events : [], seen = Object.create(null), refs = [], invalid = 0, duplicate = 0, i, n, e, names = [], nm = Object.create(null), last = null, reverse = false;
    for (i = 0; i < src.length; i++) {
      n = eIdx(src[i]); e = n >= 0 ? (tree.events || [])[n] : null;
      if (!e || typeof e !== 'object' || Array.isArray(e)) { invalid++; continue; }
      if (seen[n]) { duplicate++; continue; }
      seen[n] = 1; refs.push(n);
      if (typeof e.chapIdx !== 'number' || !isFinite(e.chapIdx) || Math.floor(e.chapIdx) !== e.chapIdx || e.chapIdx < 0 || e.chapIdx >= (tree.chapters || []).length) last = null;
      else { if (last != null && e.chapIdx < last) reverse = true; last = e.chapIdx; }
      pList(t.cast).concat(namesOf(e)).forEach(function (x) { if (!nm[x]) { nm[x] = 1; names.push(x); } });
    }
    var orderKnown = refs.every(function (ix) { return tree.events[ix] && typeof tree.events[ix].order === 'number' && isFinite(tree.events[ix].order); });
    if (orderKnown) refs = refs.map(function (ix, pos) { return { ix: ix, pos: pos, order: tree.events[ix].order }; }).sort(function (a, b) { return a.order - b.order || a.pos - b.pos; }).map(function (x) { return x.ix; });
    var span = { known: !reverse && refs.length > 0, from: null, to: null, chapters: null, orderKnown: orderKnown };
    if (span.known) { for (i = 0; i < refs.length; i++) { e = tree.events[refs[i]]; if (typeof e.chapIdx !== 'number' || !isFinite(e.chapIdx) || Math.floor(e.chapIdx) !== e.chapIdx || e.chapIdx < 0 || e.chapIdx >= (tree.chapters || []).length) { span.known = false; break; } span.from = span.from == null ? e.chapIdx : Math.min(span.from, e.chapIdx); span.to = span.to == null ? e.chapIdx : Math.max(span.to, e.chapIdx); } }
    if (span.known) span.chapters = span.to - span.from + 1;
    return { id: String(t.id), title: (typeof t.title === 'string' && t.title.trim()) || '未命名剧情线', refs: refs, sourceCount: src.length, invalidCount: invalid, duplicateCount: duplicate, participants: names, span: span, state: pStatus(t), thread: t };
  }

  // ---------------------------------------------------------------- 状态
  var TREE = null;              // 最近一次 setTree 的树（ok:false 也存，用来置灰开关）
  var GRAPH = null;             // 插件 build 拿到的 o.graph，目前只用来兜底章节名
  var wrap = null, panel = null, staffBox = null, grid = null, cardBox = null;
  var readBox = null, footEl = null, peekEl = null, ridgeEl = null, vbBtn = null, vbMeter = null;
  var mounted = false, opened = false, dirty = true;
  var LAY = null;               // 最近一次布局结果（stats / focus 都从这里取）
  var focusId = null, focusName = null;
  var rollVals = {}, rollShown = {};

  // ================================================================ 布局计算
  /** 事件 → 横轴位置。横轴是章节，同一章内的多个事件按全书阅读序均分该章的宽度 ——
   *  否则一章里的十几个事件会叠在同一个 x 上，读成一根竖线而不是一段时间。 */
  function xmap(tree) {
    var ev = tree.events || [], nch = (tree.chapters || []).length, i, e;
    var out = new Array(ev.length);
    if (!ev.length) return { x: out, nch: Math.max(1, nch) };
    if (!nch) {                                   // 没有章节轴就退回全书序：横轴仍然是时间，只是刻度更粗
      for (i = 0; i < ev.length; i++) out[i] = (i + 0.5) / ev.length;
      return { x: out, nch: 1 };
    }
    var slot = {}, cnt = {};
    for (i = 0; i < ev.length; i++) {
      e = ev[i]; var c = (e && e.chapIdx) || 0;
      cnt[c] = (cnt[c] || 0) + 1;
    }
    for (i = 0; i < ev.length; i++) {
      e = ev[i]; var c2 = (e && e.chapIdx) || 0;
      slot[c2] = (slot[c2] || 0) + 1;
      out[i] = (c2 + slot[c2] / (cnt[c2] + 1)) / nch;
    }
    return { x: out, nch: nch };
  }

  function chapOf(tree, evIdx) {
    var e = (tree.events || [])[evIdx];
    return e ? (e.chapIdx || 0) : 0;
  }
  function attachChap(tree, t) {
    if (t.attach != null && (tree.events || [])[t.attach]) return chapOf(tree, t.attach);
    var ev = t.events || [];
    return ev.length ? chapOf(tree, ev[0]) : 0;
  }

  /** 泳道排布：主干各段共用正中那一行（它们在时间上首尾相接，不会横向重叠 ——
   *  所以「一段一行」既浪费又会把「主线换手往后接上」读成「两条并行的线」）。
   *  支线按挂点章节先后左右交替：越早分叉的越贴近主干。末梢再外一层，跟着父支线那一侧。 */
  function layout(tree) {
    var th = (tree.threads || []).filter(function (t) { return t && t.id != null && String(t.id) !== ''; });
    var mains = [], brs = [], twigs = [], i, t;
    for (i = 0; i < th.length; i++) {
      t = th[i];
      if (t.kind === 'main' || t.depth === 0) mains.push(t);
      else if (t.kind === 'twig' || t.depth >= 2) twigs.push(t);
      else brs.push(t);
    }
    function cmpAttach(a, b) {
      return (attachChap(tree, a) - attachChap(tree, b)) || ((b.len || 0) - (a.len || 0)) ||
             (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    }
    brs.sort(cmpAttach); twigs.sort(cmpAttach);

    var off = {}, up = 0, dn = 0, side = -1;
    for (i = 0; i < mains.length; i++) off[mains[i].id] = 0;
    for (i = 0; i < brs.length; i++) {
      if (side < 0) { up++; off[brs[i].id] = -up; } else { dn++; off[brs[i].id] = dn; }
      side = -side;
    }
    var tu = 0, td = 0;
    for (i = 0; i < twigs.length; i++) {
      var po = off[twigs[i].parent];
      if (po == null) po = (i % 2) ? 1 : -1;
      if (po < 0) { tu++; off[twigs[i].id] = -(up + tu); } else { td++; off[twigs[i].id] = dn + td; }
    }
    var A = up + tu, B = dn + td;

    // 刻点归属：一个事件只画一个刻点（主干优先 → 支线 → 末梢，同层按原序）。
    // 这样「刻点总数 == 事件总数」是可断言的（契约 §5.8 / §7.7），共享事件由交汇连丝表达而不是画两遍。
    var ordered = mains.concat(brs, twigs), owner = Object.create(null), k, infoById = Object.create(null);
    for (i = 0; i < ordered.length; i++) {
      infoById[String(ordered[i].id)] = lineInfo(tree, ordered[i]);
      var evs = ordered[i].events || [], seen = Object.create(null), x;
      for (k = 0; k < evs.length; k++) { x = eIdx(evs[k]); if (x >= 0 && x < (tree.events || []).length && !seen[x]) { seen[x] = 1; if (owner[x] == null) owner[x] = ordered[i].id; } }
    }
    var orphan = [];
    for (i = 0; i < (tree.events || []).length; i++) if (owner[i] == null) orphan.push(i);

    var xm = xmap(tree);
    var lanes = [], byId = {};
    for (i = 0; i < th.length; i++) {
      t = th[i];
      byId[t.id] = t;
      var mine = [];
      var evs2 = (infoById[String(t.id)] && infoById[String(t.id)].refs) || [];
      for (k = 0; k < evs2.length; k++) { var ex = evs2[k]; if (ex >= 0 && String(owner[ex]) === String(t.id) && mine.indexOf(ex) < 0) mine.push(ex); }
      lanes.push({ t: t, off: off[t.id] || 0, ticks: mine, main: (t.kind === 'main' || t.depth === 0) });
    }
    return {
      lanes: lanes, mains: mains, brs: brs, twigs: twigs, off: off, owner: owner, orphan: orphan, byId: byId,
      x: xm.x, nch: xm.nch, A: A, B: B, rows: A + B + 1, infoById: infoById,
      y: function (o) { return PADT + (o + A) * STEP + STEP / 2; },
      h: PADT + (A + B + 1) * STEP + 10
    };
  }

  // ================================================================ 渲染
  function pct(v) { return (v * 100).toFixed(3) + '%'; }

  function renderAxis(tree, lay, W) {
    var chs = tree.chapters || [], i, out = [];
    if (!chs.length) return '';
    // 标签密度：超过 14 章就隔着标，否则章名会互相压住（横向可滚时按真实宽度重算）
    var per = W / chs.length, everyN = per >= 54 ? 1 : Math.ceil(54 / Math.max(1, per));
    for (i = 0; i < chs.length; i++) {
      var f = (i + 0.5) / chs.length, lab = (i % everyN === 0 || i === chs.length - 1);
      out.push('<i class="cp-ax-t' + (lab ? ' lab' : '') + '" style="left:' + pct(f) + '"' +
        ' title="' + esc(chs[i].name || ('第' + (i + 1) + '章')) + ' · ' + (chs[i].n || 0) + ' 剧情点">' +
        (lab ? '<u>' + esc(shortChap(chs[i].name, i)) + '</u>' : '') + '</i>');
    }
    return out.join('');
  }
  function shortChap(name, i) {
    var s = String(name || '');
    if (!s) return String(i + 1);
    // 章名常常是「第十二章 · 长长的副题」：轴上只留得下前缀，副题留给 title
    s = s.split(/[·:：|—-]/)[0].replace(/\s+$/, '');
    return s.length > 6 ? s.slice(0, 6) : s;
  }

  function renderTrunk(tree, lay, W) {
    var tr = tree.trunk || {}, segs = tr.segments || [], i, out = [];
    var y = lay.y(0);
    for (i = 0; i < segs.length; i++) {
      var s = segs[i];
      var a = lay.x[s.from], b = lay.x[s.to];
      if (a == null || b == null) continue;
      if (b < a) { var tmp = a; a = b; b = tmp; }
      var st = lay.byId[s.threadId], nm = (st && st.title) || s.lead || ('第' + (i + 1) + '段');
      out.push('<b class="cp-seg" data-t="' + esc(s.threadId || '') + '" style="left:' + pct(a) +
        ';width:' + pct(Math.max(0.002, b - a)) + ';top:' + (y - 2) + 'px;background:' + hex(s.color) +
        '" title="主干第 ' + (i + 1) + ' 段 · ' + esc(nm) + (s.lead ? ' · 主导 ' + esc(s.lead) : '') +
        ' · ' + ((s.events || []).length) + ' 剧情点"></b>');
      // 段名压在段首上方：这是「这一程是谁在推」的唯一读法（主导角色留在 title 里，横轴上放不下两行）
      out.push('<u class="cp-sl' + (a > 0.72 ? ' rt' : '') + '" style="left:' + pct(a) +
        ';top:' + (y - 8) + 'px;color:' + hex(s.color) + '">' + esc(nm) + '</u>');
    }
    // 断口：主干在章节上真的断过 —— 画成一小段去色收细的暗节
    var gaps = tr.gaps || [];
    for (i = 0; i < gaps.length; i++) {
      var g = gaps[i], gx = lay.x[g.after];
      if (gx == null) continue;
      out.push('<b class="cp-gap" style="left:' + pct(gx) + ';top:' + (y - 1) + 'px" title="主干断口 · 跳过 ' +
        (g.chapters || 0) + ' 章"></b>');
    }
    return out.join('');
  }

  function renderHandoffs(tree, lay) {
    var hs = tree.handoffs || [], i, out = [], y = lay.y(0);
    for (i = 0; i < hs.length; i++) {
      var h = hs[i], hx = lay.x[h.at];
      if (hx == null) continue;
      var ev = (tree.events || [])[h.at] || {};
      var src = tree.src === 'derived' ? ' · 推导 · 未核验' : (tree.src === 'fixture' ? ' · 合成样例' : (h.sourceRef ? ' · 来源 ' + h.sourceRef : ' · 来源未提供'));
      out.push('<u class="cp-ho" data-ho="' + i + '" data-ev="' + h.at + '" tabindex="0"' +
        ' style="left:' + pct(hx) + ';top:' + y + 'px"' +
        ' title="换手 · ' + esc(h.kind || '') + '｜' + esc(h.from || '') + ' → ' + esc(h.to || '') +
        (h.reason ? '｜' + esc(h.reason) : '｜理由未提供') + esc(src) + '">' +
        '<i></i><s>' + esc(h.kind || '换手') + '</s></u>');
    }
    return out.join('');
  }

  function renderLane(tree, lay, L, budget) {
    var t = L.t, y = lay.y(L.off), i, out = [];
    var ticks = L.ticks, col = hex(t.color), st = pStatus(t);
    if (!L.main) {
      var xs = [], k;
      var refs = t.events || ticks;
      for (k = 0; k < refs.length; k++) if (lay.x[eIdx(refs[k])] != null) xs.push(lay.x[eIdx(refs[k])]);
      var a = xs.length ? Math.min.apply(null, xs) : 0, b = xs.length ? Math.max.apply(null, xs) : 0;
      var w = Math.max(0.004, b - a);
      var cls = 'cp-rail' + (st === 'suspended' ? ' susp' : '') + (t.depth >= 2 ? ' twig' : '');
      out.push('<b class="' + cls + '" style="left:' + pct(a) + ';width:' + pct(w) + ';top:' + (y - 1) +
        'px;background:' + col + '"></b>');
      // 右端收尾：收束 = 实心结 · 悬置 = 散开的渐隐虚线（契约 §5.2）
      out.push('<s class="cp-end ' + (st === 'suspended' ? 'fray' : (st === 'resolved' ? 'knot' : 'open')) +
        '" style="left:' + pct(b) + ';top:' + y + 'px;color:' + col + '" title="' +
        (st === 'suspended' ? '悬置 · 未收束' : (st === 'resolved' ? '收束' : (st === 'conflict' ? '状态冲突' : '状态未定'))) + '"></s>');
      if (L.lab) out.push('<u class="cp-nm' + (a > 0.72 ? ' rt' : '') + '" style="left:' + pct(a) +
        ';top:' + (y - 7) + 'px">' + esc(t.title || t.id) + '</u>');
    }
    var omitted = 0, firstOmitted = -1;
    for (i = 0; i < ticks.length; i++) {
      var idx = ticks[i], e = (tree.events || [])[idx];
      if (!e || lay.x[idx] == null) continue;
      if (budget && budget.used >= budget.limit) { if (firstOmitted < 0) firstOmitted = idx; omitted++; continue; }
      var sz = Math.round(4 + clamp(e.w || 0, 0, 1) * 6);
      if (L.main) sz += 1;                                  // 主干上的刻点略大：正中那一条本来就该最重
      out.push('<i class="cp-tk" data-ev="' + idx + '" data-t="' + esc(t.id) + '" style="left:' + pct(lay.x[idx]) +
        ';top:' + y + 'px;width:' + sz + 'px;height:' + sz + 'px;background:' + kcol(e.kind) + '"></i>');
      if (budget) budget.used++;
    }
    if (omitted) out.push('<button class="cp-agg" data-t="' + esc(t.id) + '" data-ev="' + firstOmitted + '" tabindex="0" style="top:' + (y - 12) + 'px">展开本线 ' + (ticks.length) + ' 个事件 · ' + omitted + ' 个刻点已聚合</button>');
    return '<div class="cp-lane' + (L.main ? ' main' : '') + (t.depth >= 2 ? ' twig' : '') +
      '" data-t="' + esc(t.id) + '" style="--lc:' + col + '">' + out.join('') + '</div>';
  }

  /** 不靠 z-index 压人，靠不去占人的位置。
   *  底部提示 #hint 会随视口宽度换行到两三行，左列 #index / #overview 又会随聚焦态整列滑走 ——
   *  任何硬编码的 bottom / left 迟早压上去。于是每次开面板 / 改窗口都真量一次邻居的盒子，
   *  只写自己元素的内联样式，app.css 一个字节也不动。 */
  function fit() {
    if (!wrap) return;
    var vh = window.innerHeight, i;
    var hint = document.getElementById('hint');
    if (hint) {
      var hr = hint.getBoundingClientRect();
      if (hr.height > 2) wrap.style.bottom = Math.round(Math.max(0, vh - hr.top + 10)) + 'px';
    }
    var me = wrap.getBoundingClientRect(), L = 0;
    if (window.innerWidth <= 900) { wrap.style.left = ''; wrap.style.bottom = ''; return; }
    var SEL = ['#brand .panel', '#index .panel', '#overview .panel'];
    for (i = 0; i < SEL.length; i++) {
      var e = document.querySelector(SEL[i]);
      if (!e) continue;
      var r = e.getBoundingClientRect();
      if (r.width < 4 || r.height < 4) continue;
      if (Math.min(me.bottom, r.bottom) - Math.max(me.top, r.top) > 2) L = Math.max(L, r.right);
    }
    // L<=0 = 左列这一刻不在我的纵向区间里（聚焦态整列滑走了）：撤掉内联值让 CSS 兜底，别把空位留在那
    wrap.style.left = L > 0 ? (Math.round(L + 18) + 'px') : '';
  }

  function renderOrphans(tree, lay, budget) {
    var o = lay.orphan, i, out = [], y = lay.y(0);
    for (i = 0; i < o.length; i++) {
      var e = (tree.events || [])[o[i]];
      if (!e || lay.x[o[i]] == null) continue;
      if (budget && budget.used >= budget.limit) continue;
      out.push('<i class="cp-tk orph" data-ev="' + o[i] + '" style="left:' + pct(lay.x[o[i]]) +
        ';top:' + (y - 9) + 'px;background:' + kcol(e.kind) + '" title="未归入任何剧情线"></i>');
      if (budget) budget.used++;
    }
    return '<div class="cp-lane orphs">' + out.join('') + '<button class="cp-read-orphans" type="button">阅读未归线事件 · ' + o.length + '</button></div>';
  }

  /** 连丝层：支线泳道左端 → 主干上的分叉点，以及交汇处的两线横连。
   *  用一张 SVG 而不是 DOM：这些是跨行的曲线，DOM 里画只能拿一堆旋转的方块凑，凑出来也读不准。 */
  function renderWires(tree, lay, W) {
    var i, out = [], H = lay.h;
    for (i = 0; i < lay.lanes.length; i++) {
      var L = lay.lanes[i], t = L.t;
      if (L.main || !L.ticks.length) continue;
      var ax = t.attach != null && lay.x[t.attach] != null ? lay.x[t.attach] : null;
      var py = lay.y(lay.off[t.parent] != null ? lay.off[t.parent] : 0);
      var xs = [], k;
      for (k = 0; k < L.ticks.length; k++) if (lay.x[L.ticks[k]] != null) xs.push(lay.x[L.ticks[k]]);
      if (!xs.length) continue;
      var lx = Math.min.apply(null, xs) * W, ly = lay.y(L.off);
      if (ax == null) ax = Math.min.apply(null, xs);
      var px = ax * W;
      var dx = Math.max(10, Math.abs(lx - px) * 0.45);
      out.push('<path class="cp-wire' + (t.depth >= 2 ? ' twig' : '') + '" data-t="' + esc(t.id) +
        '" d="M' + px.toFixed(1) + ' ' + py.toFixed(1) + ' C' + (px + dx).toFixed(1) + ' ' + py.toFixed(1) +
        ' ' + (lx - dx).toFixed(1) + ' ' + ly.toFixed(1) + ' ' + lx.toFixed(1) + ' ' + ly.toFixed(1) +
        '" style="stroke:' + hex(t.color) + '"></path>');
      out.push('<circle class="cp-fork" cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="2.1"></circle>');
    }
    var js = tree.junctions || [];
    for (i = 0; i < js.length; i++) {
      var j = js[i], jx = lay.x[j.at];
      if (jx == null || !j.threads || j.threads.length < 2) continue;
      var y1 = lay.y(lay.off[j.threads[0]] || 0), y2 = lay.y(lay.off[j.threads[1]] || 0);
      var X = jx * W;
      out.push('<line class="cp-jx" x1="' + X.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + X.toFixed(1) +
        '" y2="' + y2.toFixed(1) + '"></line>');
      out.push('<path class="cp-jxm" d="M' + (X - 3).toFixed(1) + ' ' + ((y1 + y2) / 2).toFixed(1) + 'h6M' +
        X.toFixed(1) + ' ' + ((y1 + y2) / 2 - 3).toFixed(1) + 'v6"></path>');
    }
    return '<svg class="cp-wires" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">' +
      out.join('') + '</svg>';
  }

  function renderCards(tree, lay) {
    var th = tree.threads || [], i, k, out = [];
    var maxLen = 1;
    for (i = 0; i < th.length; i++) maxLen = Math.max(maxLen, th[i].len || 0);
    // 卡片顺序 = 主干各段（按时间）→ 支线（按长度）→ 末梢：读者先看到「主线怎么走的」，再看「岔出去多少」
    var seq = lay.mains.concat(
      lay.brs.slice().sort(function (a, b) { return (b.len || 0) - (a.len || 0); }),
      lay.twigs.slice().sort(function (a, b) { return (b.len || 0) - (a.len || 0); }));
    for (i = 0; i < seq.length; i++) {
      var t = seq[i], col = hex(t.color), inf = lay.infoById[String(t.id)];
      var sp = t.span || {}, chs = tree.chapters || [], refs = inf.refs, valid = [], bad = inf.invalidCount, dup = inf.duplicateCount, j;
      for (j = 0; j < refs.length; j++) valid.push((tree.events || [])[refs[j]]);
      var knownSpan = inf.span.known, ca = inf.span.from, cb = inf.span.to;
      var cf = ca != null && chs[ca] ? shortChap(chs[ca].name, ca) : '—';
      var ct = cb != null && chs[cb] ? shortChap(chs[cb].name, cb) : '—';
      var mix = t.kindMix || {}, mmax = 1;
      for (k in mix) if (mix[k] > mmax) mmax = mix[k];
      var bars = [];
      for (k = 0; k < KORD.length; k++) {
        var n = mix[KORD[k]] || 0;
        bars.push('<u class="' + (n ? '' : 'z') + '" title="' + KORD[k] + ' ' + n + '" style="height:' +
          Math.max(6, Math.round(n / mmax * 100)) + '%;background:' + kcol(KORD[k]) + '"></u>');
      }
      var cast = [], castSeen = Object.create(null), chips = [];
      pList(t.cast).forEach(function (n0) { castSeen[n0] = 1; cast.push(n0); });
      valid.forEach(function (e0) { namesOf(e0).forEach(function (n0) { if (!castSeen[n0]) { castSeen[n0] = 1; cast.push(n0); } }); });
      for (k = 0; k < cast.length && k < 8; k++) {
        chips.push('<i class="cp-chip" data-nm="' + esc(cast[k]) + '" tabindex="0" title="' + esc(cast[k]) + '｜点亮此人在所有泳道上的刻点">' + esc(cast[k]) + '</i>');
      }
      if (cast.length > 8) chips.push('<i class="cp-ov" title="另有 ' + (cast.length - 8) + ' 人">+' + (cast.length - 8) + '</i>');
      var kindLab = t.kind === 'main' ? '主干' : (t.depth >= 2 ? '末梢' : '支线');

      out.push('<div class="cp-card" data-t="' + esc(t.id) + '" data-cp-line="' + esc(t.id) + '" tabindex="0" style="--lc:' + col + '">' +
        '<div class="cp-ch"><i class="cp-cdot"></i><b>' + esc(t.title || t.id) + '</b>' +
          (t.en ? '<em>' + esc(t.en) + '</em>' : '') + '<s>' + kindLab + '</s></div>' +
        '<div class="cp-cl">' + (t.lead ? '参与焦点 <b>' + esc(pName(t.lead)) + '</b>' : '<b class="dim">未提供主导依据</b>') +
          '<span class="mono">' + (pStatus(t) === 'suspended' ? '悬置' : (pStatus(t) === 'resolved' ? '收束' : (pStatus(t) === 'conflict' ? '状态冲突' : '状态未定'))) + '</span></div>' +
        '<div class="cp-cbar"><i style="width:' + Math.round((t.len || 0) / maxLen * 100) + '%;background:' + col + '"></i></div>' +
        '<div class="cp-cm mono">事件量 <b>' + valid.length + '</b> · 章节首尾 <b>' + esc(cf) + '→' + esc(ct) +
          ' · ' + (knownSpan ? '跨度 ' + (cb - ca + 1) + ' 章' : '跨度未知') + (bad + dup ? ' · 无效/重复引用 ' + (bad + dup) : '') + '</b></div>' +
        '<div class="cp-cmix" title="类型构成">' + bars.join('') + '</div>' +
        (chips.length ? '<div class="cp-ccast">' + chips.join('') + '</div>' : '') +
        '<details class="cp-cast-all"><summary>参与者 ' + cast.length + ' 人 · 查看全名单</summary><div>' + cast.map(function (n1) { return '<i class="cp-chip" data-nm="' + esc(n1) + '" tabindex="0">' + esc(n1) + '</i>'; }).join('') + '</div></details>' +
        '<button class="cp-read-line" data-cp-line="' + esc(t.id) + '" type="button">阅读全线 · ' + valid.length + '个事件</button>' +
        (t.quote ? '<q>' + esc(t.quote) + '</q>' : (t.theme ? '<p>' + esc(t.theme) + '</p>' : '')) +
        '</div>');
    }
    return out.join('');
  }

  /** 主渲染。同步跑完 —— 无头验收会在 setTree / open 之后立刻读 stats()，异步渲染会读到空壳。 */
  function render() {
    if (!mounted) return;
    /* 星空壳：这块旧剧情面板从不上屏（剧情走星盘 + 卡片栈）——不预建大书 3 万个隐形节点；真打开（open）时再建 */
    if (!opened && window.CLSky && CLSky.enabled && CLSky.enabled()) { dirty = true; return; }
    if (!TREE) { grid.innerHTML = ''; cardBox.innerHTML = ''; LAY = null; syncFoot(); setState(mounted ? 'empty' : 'loading'); return; }
    var ok = !!TREE.ok;
    wrap.classList.toggle('nodata', !ok);
    syncVb();
    if (!ok || !(TREE.threads || []).length) { grid.innerHTML = ''; cardBox.innerHTML = ''; LAY = null; dirty = false; syncFoot(); setState('empty'); return; }
    setState((TREE.warn || []).length ? 'degraded' : 'ready', (TREE.warn || [])[0] || '');

    LAY = layout(TREE);
    // 只给主干各段 + 最长的 8 条支线放线名：再多就是把泳道糊成字幕墙（其余靠 hover / 线卡）
    var byLen = LAY.brs.concat(LAY.twigs).slice().sort(function (a, b) { return (b.len || 0) - (a.len || 0); });
    var labOk = {}, i;
    for (i = 0; i < byLen.length && i < 8; i++) labOk[byLen[i].id] = 1;
    for (i = 0; i < LAY.lanes.length; i++) LAY.lanes[i].lab = !!labOk[LAY.lanes[i].t.id];

    var cw = staffBox.clientWidth || 900;
    var W = Math.max(cw - 4, LAY.nch * MINCH);
    var parts = [], nTick = 0, budget = { used: 0, limit: MAXTICK };
    // 泳道块比容器矮时（小图谱只有几条线）由 .cp-staff 的 flex + margin:auto 居中，
    // 所以这里只给 grid 它自己的自然高度，不撑满 —— 撑满会让几条线孤零零吊在顶上。
    parts.push('<div class="cp-ax">' + renderAxis(TREE, LAY, W) + '</div>');
    parts.push(renderWires(TREE, LAY, W));
    for (i = 0; i < LAY.lanes.length; i++) {
      nTick += LAY.lanes[i].ticks.length;
      parts.push(renderLane(TREE, LAY, LAY.lanes[i], budget));
    }
    parts.push(renderTrunk(TREE, LAY, W));
    parts.push(renderHandoffs(TREE, LAY));
    parts.push(renderOrphans(TREE, LAY, budget));
    nTick += LAY.orphan.length;

    grid.style.width = W + 'px';
    grid.style.height = LAY.h + 'px';
    grid.innerHTML = parts.join('');
    cardBox.innerHTML = renderCards(TREE, LAY);
    LAY.nTick = nTick;
    LAY.nTickRendered = budget.used;
    LAY.totalUnique = (TREE.events || []).filter(function (e) { return e && typeof e === 'object' && !Array.isArray(e); }).length;
    LAY.aggregatedTicks = Math.max(0, LAY.totalUnique - budget.used);
    LAY.nCard = cardBox.children.length;
    dirty = false;
    syncFoot();
    if (focusId) applyThread(focusId);
    if (focusName) applyChar(focusName);
  }

  // ================================================================ 读数条 · 自证行
  /** 跳数：沿用秘仪层 ledger 的机械式逼近（每帧向目标走 28%），读起来像老式计数器咔咔归位。
   *  起点取**当前显示值**而不是上一次的目标值 —— 否则换作品时数字会先跳回旧目标再走，看得见地一闪。 */
  function rollTo(node, to, suf) {
    var k = node.getAttribute('data-k'), from = rollShown[k] || 0, b = node.firstChild;
    rollVals[k] = to;
    if (CALM || from === to) { rollShown[k] = to; b.textContent = to + (suf || ''); return; }
    var cur = from, n = 0;
    clearInterval(node._roll);
    node._roll = setInterval(function () {
      n++;
      cur = cur + (to - cur) * 0.28;
      if (Math.abs(to - cur) < 0.6 || n > 40) { cur = to; clearInterval(node._roll); }
      rollShown[k] = Math.round(cur);
      b.textContent = rollShown[k] + (suf || '');
    }, 34);
  }
  function setState(state, notice) {
    if (!wrap) return;
    var box = wrap.querySelector('.cp-state'), body = wrap.querySelector('.cp-body');
    if (!box && body) { box = el('div', 'cp-state'); body.parentNode.insertBefore(box, body); }
    if (!box) return;
    box.textContent = '';
    box.setAttribute('data-cl-state', state);
    wrap.setAttribute('data-cp-state', state);
    if (state !== 'ready' && window.CLStatusStates && CLStatusStates.applyState) {
      CLStatusStates.applyState(box, state, { domain: 'plot-hud', bars: 4, minHeight: 96, notice: notice || '' });
    }
  }
  var READS = [
    { k: 'trunkLen', s: 'TRUNK · 主干长度' }, { k: 'trunkChapters', s: 'CANTOS · 主干章节' },
    { k: 'handoffs', s: 'RELAYS · 换手' }, { k: 'branches', s: 'BRANCH · 支线' },
    { k: 'maxBranchLen', s: 'LONGEST · 最长支线' }, { k: 'suspended', s: 'OPEN · 悬置' },
    { k: 'coverage', s: 'COVER · 覆盖率', suf: '%' }
  ];
  function syncRead() {
    if (!readBox) return;
    var st = (TREE && TREE.stats) || {};
    Array.prototype.forEach.call(readBox.children, function (n) {
      var k = n.getAttribute('data-k'), spec = null, i;
      for (i = 0; i < READS.length; i++) if (READS[i].k === k) spec = READS[i];
      var v = k === 'coverage' ? Math.round((st.coverage || 0) * 100) : (st[k] || 0);
      rollTo(n, v, spec && spec.suf);
    });
  }
  /** 零 token 自证：这一层画的每一个数字都能追到「哪份数据 · 哪个指纹 · 算了多久」。 */
  function syncFoot() {
    if (!footEl) return;
    if (!TREE || !TREE.ok) {
      footEl.textContent = 'src=— · fp=— · ' + (TREE && TREE.reason ? 'reason=' + TREE.reason : '无剧情线');
      return;
    }
    var st = TREE.stats || {}, fp = String(TREE.fp || '').replace(/^sl-/, '').slice(0, 8);
    var bits = ['src=' + (TREE.src || '?'), 'fp=sl-' + (fp || '········'), (st.ms || 0) + 'ms'];
    bits.push('lane ' + ((LAY && LAY.lanes.length) || 0) + '/' + ((TREE.threads || []).length));
    bits.push('tick ' + ((LAY && LAY.nTick) || 0) + '/' + ((TREE.events || []).length));
    var handoffs = TREE.handoffs || [], sourced = handoffs.filter(function (h) { return h && h.sourceRef && TREE.src !== 'derived' && TREE.src !== 'fixture'; }).length;
    bits.push(handoffs.length ? '更替记录' + handoffs.length + ' · 有理由' + handoffs.filter(function (h) { return h && h.reason; }).length + ' · 可定位来源' + sourced : '未提供更替记录');
    if (LAY && LAY.nTickRendered < LAY.nTick) bits.push('聚合 +' + (LAY.nTick - LAY.nTickRendered) + '/' + LAY.nTick);
    if ((TREE.warn || []).length) bits.push('warn ' + TREE.warn.length);
    footEl.textContent = bits.join(' · ');
    footEl.title = (TREE.warn || []).join('\n') || '';
  }

  // ================================================================ peek
  function showPeek(evIdx, x, y) {
    var e = (TREE && (TREE.events || [])[evIdx]);
    if (!e || !peekEl) return;
    var chs = (TREE.chapters || [])[e.chapIdx];
    var cast = (e.cast || []).slice(0, 6).map(function (n) {
      return '<span' + (focusName === n ? ' class="me"' : '') + '>' + esc(n) + '</span>';
    }).join('');
    peekEl.innerHTML =
      '<div class="t">' + esc(e.title || '（无题）') + '</div>' +
      '<div class="m"><b>#' + (e.order != null ? e.order : evIdx) + '</b> · ' +
        esc((chs && chs.name) || ('第' + ((e.chapIdx || 0) + 1) + '章')) +
        ' · <em class="k">' + esc(e.kind || '日常') + '</em>' +
        ' · w ' + (e.w || 0).toFixed(2) + '</div>' +
      (e.summary ? '<div class="b">' + esc(e.summary) + '</div>' : '') +
      (cast ? '<div class="cst">' + cast + ((e.cast || []).length > 6 ? '<span class="ov">+' + ((e.cast || []).length - 6) + '</span>' : '') + '</div>' : '') +
      (e.quote ? '<q>' + esc(e.quote) + '</q>' : '');
    try { peekEl.style.setProperty('--kc', kcol(e.kind)); } catch (e0) {}
    peekEl.classList.add('on');
    var r = peekEl.getBoundingClientRect();
    peekEl.style.left = clamp(x + 14, 8, window.innerWidth - r.width - 8) + 'px';
    peekEl.style.top = clamp(y - r.height - 14, 8, window.innerHeight - r.height - 8) + 'px';
  }
  function hidePeek() { if (peekEl) peekEl.classList.remove('on'); }

  // ================================================================ 联动
  function applyThread(id) {
    if (!grid) return;
    var any = !!id;
    grid.classList.toggle('foc', any);
    cardBox.classList.toggle('foc', any);
    Array.prototype.forEach.call(grid.querySelectorAll('.cp-lane'), function (n) {
      n.classList.toggle('on', any && n.getAttribute('data-t') === id);
    });
    Array.prototype.forEach.call(grid.querySelectorAll('.cp-wire'), function (n) {
      n.classList.toggle('on', any && n.getAttribute('data-t') === id);
    });
    // 主干各段不在泳道里（它们是 trunk.segments 直接画的），所以要单独跟着压暗 / 点亮
    Array.prototype.forEach.call(grid.querySelectorAll('.cp-seg'), function (n) {
      n.classList.toggle('on', any && n.getAttribute('data-t') === id);
    });
    Array.prototype.forEach.call(cardBox.querySelectorAll('.cp-card'), function (n) {
      n.classList.toggle('on', any && n.getAttribute('data-t') === id);
    });
  }
  function applyChar(name) {
    if (!grid || !TREE) return;
    var any = !!name, ev = TREE.events || [];
    grid.classList.toggle('lit', any);
    Array.prototype.forEach.call(grid.querySelectorAll('.cp-tk'), function (n) {
      var i = +n.getAttribute('data-ev'), e = ev[i], hit = false;
      if (any && e && e.cast) hit = e.cast.indexOf(name) >= 0;
      n.classList.toggle('lit', hit);
    });
    Array.prototype.forEach.call(cardBox.querySelectorAll('.cp-chip'), function (n) {
      n.classList.toggle('me', any && n.getAttribute('data-nm') === name);
    });
  }
  var reader = null, readingId = null, readerReturn = null;
  function openLine(id) {
    if (!reader || !LAY || !LAY.infoById[String(id)]) return;
    var inf = LAY.infoById[String(id)], ev = TREE.events || [], chs = TREE.chapters || [], h = TREE.handoffs || [], out = [], i, e, ch;
    readingId = String(id); readerReturn = document.activeElement;
    wrap.classList.add('cp-reading');
    try { document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: id } })); } catch (ignore) {}
    for (i = 0; i < inf.refs.length; i++) { e = ev[inf.refs[i]] || {}; ch = chs[e.chapIdx] || {}; out.push('<button class="cp-reader-event" type="button" data-cp-event="' + inf.refs[i] + '">' + (e.order != null ? '#' + esc(e.order) : '事件序未提供') + ' · ' + esc(ch.name || '章节未提供') + ' · ' + esc(e.title || '事件标题未提供') + '</button>'); }
    for (i = 0; i < h.length; i++) if (String(h[i].from) === String(id) || String(h[i].to) === String(id)) out.push('<div class="cp-reader-ho">换手 ' + esc(h[i].from || '未提供') + '→' + esc(h[i].to || '未提供') + ' · ' + esc(h[i].reason || '理由未提供') + (TREE.src === 'derived' || TREE.src === 'fixture' ? ' · 推导/未核验' : '') + '</div>');
    reader.innerHTML = '<button class="cp-reader-back" type="button">返回全书</button><h3>' + esc(inf.title) + '</h3><p>事件量 ' + inf.refs.length + ' · ' + (inf.span.known ? '跨度 ' + inf.span.chapters + ' 章' : '跨度未知') + ' · 无效 ' + inf.invalidCount + ' · 重复 ' + inf.duplicateCount + '</p><details open><summary>参与者 ' + inf.participants.length + ' 人</summary><div>' + inf.participants.map(function (n) { return '<button class="cp-person" type="button" data-cp-name="' + esc(n) + '">' + esc(n) + '</button>'; }).join('') + '</div></details><div class="cp-reader-events">' + out.join('') + '</div>';
    reader.hidden = false;
    var back = reader.querySelector('.cp-reader-back'); if (back) back.focus();
    var first = reader.querySelector('.cp-reader-event'); if (first && first.scrollIntoView) first.scrollIntoView({ block: 'nearest' });
  }
  function closeLine() { if (!reader) return; reader.hidden = true; readingId = null; if (wrap) wrap.classList.remove('cp-reading'); if (readerReturn && readerReturn.focus) readerReturn.focus(); }
  function openOrphans() {
    if (!reader) return;
    readerReturn = document.activeElement;
    reader.innerHTML = '<button class="cp-reader-back" type="button">返回全书</button><h3>未归线事件</h3><div>' + (LAY.orphan || []).map(function (x) { var e = TREE.events[x] || {}; return '<button class="cp-reader-event" type="button" data-cp-event="' + x + '">' + (e.order != null ? '#' + esc(e.order) : '事件序未提供') + ' · ' + esc(e.title || '事件标题未提供') + '</button>'; }).join('') + '</div>';
    reader.hidden = false;
    wrap.classList.add('cp-reading');
    var back = reader.querySelector('.cp-reader-back'); if (back) back.focus();
  }

  // ================================================================ DOM 装配
  function mount() {
    if (mounted) return;
    if (!document.body) return;
    wrap = el('div', 'hud cl-plot enter');
    wrap.id = 'clPlot';
    var reads = READS.map(function (r) {
      return '<div class="cp-r" data-k="' + r.k + '"><b>—</b><s>' + r.s + '</s></div>';
    }).join('');
    wrap.innerHTML =
      '<div class="panel cp-panel">' +
      '  <div class="cp-head">' +
      '    <div class="eyebrow"><span class="dot"></span>剧情流 · <b>PLOT STREAM</b></div>' +
      '    <div class="cp-reads">' + reads + '</div>' +
      '    <input class="cp-search" type="search" aria-label="查找剧情线或事件" placeholder="查找剧情线或事件"><button class="cp-search-clear" type="button">清除</button><span class="cp-search-count"></span>' +
      '    <button class="cp-btn" data-act="fold" title="折叠成边缘脊（N 键开关整层）">—</button>' +
      '  </div>' +
      '  <div class="cp-body">' +
      '    <div class="cp-staff"><div class="cp-grid"></div></div>' +
      '    <div class="cp-cards"></div>' +
      '    <div class="cp-reader" hidden></div>' +
      '  </div>' +
      '  <div class="cp-foot mono"></div>' +
      '  <div class="cp-empty">当前图谱没有可解析的剧情线</div>' +
      '</div>' +
      '<button class="cp-ridge" title="展开剧情线谱（N）"><i></i><span>剧情流 · PLOT</span><em></em></button>';
    document.body.appendChild(wrap);
    if (!TREE) setState('loading');
    panel = wrap.querySelector('.cp-panel');
    staffBox = wrap.querySelector('.cp-staff');
    grid = wrap.querySelector('.cp-grid');
    cardBox = wrap.querySelector('.cp-cards');
    reader = wrap.querySelector('.cp-reader');
    function runSearch(input) { var q = String(input.value || '').trim().toLowerCase(), hit = 0, total = cardBox.querySelectorAll('.cp-card').length; Array.prototype.forEach.call(cardBox.querySelectorAll('.cp-card'), function (c) { var inf = LAY && LAY.infoById[c.getAttribute('data-cp-line')], text = c.textContent; if (inf) { text += ' ' + inf.participants.join(' '); inf.refs.forEach(function (x) { var e = TREE.events[x] || {}; text += ' ' + (e.title || '') + ' ' + (e.chapter || '') + ' ' + (e.summary || ''); }); } c.hidden = !!q && text.toLowerCase().indexOf(q) < 0; if (!c.hidden) hit++; }); var count = wrap.querySelector('.cp-search-count'); if (count) count.textContent = q ? hit + '/' + total + ' 条匹配' + (hit ? '' : ' · 无结果') : total + '/' + total + ' 条线'; input.title = count ? count.textContent : ''; }
    wrap.querySelector('.cp-search').addEventListener('input', function () { runSearch(this); });
    wrap.querySelector('.cp-search-clear').addEventListener('click', function () { var input = wrap.querySelector('.cp-search'); input.value = ''; runSearch(input); input.focus(); });
    readBox = wrap.querySelector('.cp-reads');
    footEl = wrap.querySelector('.cp-foot');
    ridgeEl = wrap.querySelector('.cp-ridge');
    peekEl = el('div', 'cp-peek');
    document.body.appendChild(peekEl);
    setTimeout(function () { if (wrap) wrap.classList.remove('enter'); }, 1000);

    // ---- 交互：全部走事件委托。刻点可能有上千个，逐个挂 listener 是纯浪费。
    grid.addEventListener('mouseover', function (e) {
      var n = e.target;
      if (!n || !n.getAttribute) return;
      var idx = n.getAttribute('data-ev');
      if (idx == null) { hidePeek(); return; }
      showPeek(+idx, e.clientX, e.clientY);
    });
    grid.addEventListener('mouseleave', hidePeek);
    grid.addEventListener('click', function (e) {
      var n = e.target;
      if (n && n.closest && n.closest('.cp-agg')) { openLine(n.closest('.cp-agg').getAttribute('data-t')); return; }
      if (n && n.closest && n.closest('.cp-read-orphans')) { openOrphans(); return; }
      if (n && n.getAttribute && n.getAttribute('data-ev') != null && window.CLPlotOrbitView && CLPlotOrbitView.focusEvent) {
        try { CLPlotOrbitView.focusEvent(eIdx(n.getAttribute('data-ev'))); } catch (ignore) {}
        return;
      }
      while (n && n !== grid && !(n.classList && (n.classList.contains('cp-lane') || n.classList.contains('cp-ho')))) n = n.parentNode;
      if (!n || n === grid) return;
      if (n.classList.contains('cp-ho')) {                 // 换手标：跳到接手的那一段
        var i = +n.getAttribute('data-ho'), h = (TREE.handoffs || [])[i];
        if (h) pickThread(h.to || h.from);
        return;
      }
      pickThread(n.getAttribute('data-t'));
    });
    cardBox.addEventListener('click', function (e) {
      var n = e.target;
      if (n && n.classList && n.classList.contains('cp-read-line')) { openLine(n.getAttribute('data-cp-line')); return; }
      if (n && n.classList && n.classList.contains('cp-chip')) { pickChar(n.getAttribute('data-nm')); return; }
      if (n && n.closest && n.closest('details,summary')) return;
      while (n && n !== cardBox && !(n.classList && n.classList.contains('cp-card'))) n = n.parentNode;
      if (n && n !== cardBox) pickThread(n.getAttribute('data-t'));
    });
    cardBox.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('cp-read-line')) { e.preventDefault(); openLine(e.target.getAttribute('data-cp-line')); }
    });
    reader.addEventListener('click', function (e) {
      var n = e.target;
      if (n.classList.contains('cp-reader-back')) { closeLine(); return; }
      if (n.classList.contains('cp-person')) { pickChar(n.getAttribute('data-cp-name')); return; }
      if (n.classList.contains('cp-reader-event')) { var ix = eIdx(n.getAttribute('data-cp-event')), view = window.CLPlotOrbitView; if (!view || typeof view.eventAt !== 'function' || typeof view.focusEvent !== 'function' || !view.eventAt(ix)) { n.disabled = true; n.title = '当前视图不可定位此事件'; return; } view.focusEvent(ix); }
    });
    reader.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.stopPropagation(); closeLine(); } });
    cardBox.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var n = e.target;
      if (!n || !n.classList) return;
      if (n.classList.contains('cp-chip')) { e.preventDefault(); pickChar(n.getAttribute('data-nm')); }
      else if (n.classList.contains('cp-card')) { e.preventDefault(); pickThread(n.getAttribute('data-t')); }
    });
    panel.querySelector('[data-act="fold"]').addEventListener('click', function () { API.close(); });
    ridgeEl.addEventListener('click', function () { API.open(); });

    // 宽度决定横轴刻度密度、邻居盒子决定落位，所以窗口一变两件都要重来（防抖：连续拖动只算最后一次）
    window.addEventListener('resize', function () {
      clearTimeout(mount._rt);
      mount._rt = setTimeout(function () { if (opened) { fit(); render(); } }, 180);
    });

    injectViewbarRow();
    mounted = true;
    fit();
    syncVb();
    syncFoot();
  }

  /** 入口自注入：往 #viewbar .panel 里加一行「剧情流」开关，沿用 .vb-row / .tgl 的既有类名与观感。
   *  注：app.css 里 #viewbar 目前是 display:none（视图控制已并入镜头自动逻辑），
   *  所以这一行在当前皮肤下不可见 —— 契约要求它在，就让它在，并且状态永远同步；
   *  真正可见的入口是折叠态的边缘脊（.cp-ridge）与 N 键。绝不为了露脸去改 #viewbar 的既有样式。 */
  function injectViewbarRow() {
    var host = document.querySelector('#viewbar .panel');
    if (!host || host.querySelector('.cp-vb')) return;
    var row = el('div', 'vb-row cp-vb',
      '<span class="vb-k">剧情</span>' +
      '<button class="tgl" data-act="plot" title="第二条信息流：横轴章节 · 一线一泳道 · 换手与挂点（N）">剧情流 <b>关</b></button>' +
      '<span class="vb-meter cp-vbm">—</span>');
    host.appendChild(row);
    vbBtn = row.querySelector('.tgl');
    vbMeter = row.querySelector('.cp-vbm');
    vbBtn.addEventListener('click', function () { if (!vbBtn.disabled) API.toggle(); });
  }
  function syncVb() {
    var ok = !!(TREE && TREE.ok), st = (TREE && TREE.stats) || {};
    if (vbBtn) {
      vbBtn.disabled = !ok;
      vbBtn.classList.toggle('on', ok && opened);
      vbBtn.classList.toggle('cp-vb-off', !ok);            // 置灰用自己的类，不去动 .tgl 的既有样式
      vbBtn.firstElementChild.textContent = !ok ? '无' : (opened ? '开' : '关');
    }
    if (vbMeter) vbMeter.innerHTML = ok ? ('线 <i>' + (st.threads || 0) + '</i> / 刻 <b>' + (st.events || 0) + '</b>') : '—';
    if (ridgeEl) {
      var em = ridgeEl.querySelector('em');
      if (em) em.textContent = ok ? ('主干 ' + (st.trunkLen || 0) + ' · 换手 ' + (st.handoffs || 0) + ' · 支线 ' + (st.branches || 0)) : '';
    }
  }

  function pickThread(id) {
    if (!id) return;
    focusId = (focusId === id) ? null : id;                 // 再点一次 = 取消聚焦
    applyThread(focusId);
    // 契约 §5.3：线卡直接驱动 3D 树（不经 app），两条信息流于是同步高亮同一条线
    try { document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: focusId } })); } catch (e) {}
  }
  function pickChar(name) {
    if (!name) return;
    focusName = (focusName === name) ? null : name;
    applyChar(focusName);
    // 契约 §5.5：只发事件、不直接调 app —— 「聚焦该角色」的语义归主会话
    if (focusName) {
      try { document.dispatchEvent(new CustomEvent('cl:plot-char', { detail: { name: focusName } })); } catch (e) {}
    }
  }

  // ================================================================ 对外接口
  var API = {
    name: 'plot-hud',
    /** 插件位：秘仪层在星盘建好后 fan 过来，这里只取 o.graph 作兜底。
     *  故意不接 arcana 的 dispose —— 星盘重建（换模式 / 换图谱）与这条 DOM 信息流无关，
     *  跟着拆会把用户正在读的面板凭空抽掉。真正的拆除留给 API.dispose()。 */
    build: function (o) {
      GRAPH = (o && o.graph) || GRAPH;
      mount();
      if (dirty && TREE) render();
      return API.stats();
    },
    dispose: function () {
      closeLine(); reader = null; readerReturn = null; readingId = null;
      if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
      if (peekEl && peekEl.parentNode) peekEl.parentNode.removeChild(peekEl);
      var row = document.querySelector('#viewbar .panel .cp-vb');
      if (row && row.parentNode) row.parentNode.removeChild(row);
      wrap = panel = staffBox = grid = cardBox = readBox = footEl = peekEl = ridgeEl = vbBtn = vbMeter = null;
      mounted = false; opened = false; dirty = true; LAY = null;
      document.body.classList.remove('cl-plot-on');
    },
    mount: mount,
    /** ok:false 时开关置灰、面板不渲染 —— 但绝不报错：A 面缺席不该让整站少一块。 */
    setTree: function (tree) {
      closeLine(); if (reader) reader.innerHTML = '';
      TREE = tree || null;
      dirty = true;
      focusId = focusName = null;
      rollShown = {};
      mount();
      if (!mounted) return;
      if (!TREE || !TREE.ok) { render(); if (opened) API.close(); return; }
      render();
      if (opened) syncRead();
    },
    toggle: function (v) {
      var want = (v == null) ? !opened : !!v;
      if (want) API.open(); else API.close();
      return opened;
    },
    open: function () {
      mount();
      if (!mounted || !TREE || !TREE.ok) { syncVb(); return; }
      opened = true;
      wrap.classList.add('on');
      wrap.classList.remove('ridge');
      document.body.classList.add('cl-plot-on');
      fit();                                                // 先让位（量邻居），再算刻度密度 —— 顺序反了宽度就是错的
      render();                                             // 展开后才有真实宽度，横轴刻度要按它重算
      syncRead();
      syncVb();
    },
    /** 关 = 折叠成边缘脊，而不是彻底消失：#viewbar 在当前皮肤下不可见，
     *  这条 28px 的脊既是契约 §5.6 的「边缘脊」，也是这条信息流唯一看得见的入口。 */
    close: function () {
      opened = false;
      if (!mounted) return;
      wrap.classList.remove('on');
      wrap.classList.add('ridge');
      document.body.classList.remove('cl-plot-on');
      hidePeek();
      syncVb();
    },
    visible: function () { return opened; },
    focusThread: function (id) {
      focusId = id || null;
      if (mounted) applyThread(focusId);
    },
    focusChar: function (name) {
      focusName = name || null;
      if (mounted) applyChar(focusName);
    },
    stats: function () {
      var st = (TREE && TREE.stats) || {};
      return {
        mounted: mounted, open: opened,
        lanes: (LAY && LAY.lanes.length) || 0,
        ticks: (LAY && LAY.nTick) || 0,
        renderedTicks: (LAY && LAY.nTickRendered) || 0,
        aggregatedTicks: (LAY && LAY.aggregatedTicks) || 0,
        cards: (LAY && LAY.nCard) || 0,
        src: (TREE && TREE.src) || '',
        fp: (TREE && TREE.fp) || '',
        ms: st.ms || 0,
        ok: !!(TREE && TREE.ok),
        ridge: !!(wrap && wrap.classList.contains('ridge')),
        threads: (TREE && (TREE.threads || []).length) || 0,
        events: (TREE && (TREE.events || []).length) || 0,
        rows: (LAY && LAY.rows) || 0,
        wires: (LAY && grid) ? grid.querySelectorAll('.cp-wire').length : 0,
        handoffs: (LAY && grid) ? grid.querySelectorAll('.cp-ho').length : 0,
        segs: (LAY && grid) ? grid.querySelectorAll('.cp-seg').length : 0,
        orphans: (LAY && LAY.orphan.length) || 0,
        focusThread: focusId, focusChar: focusName, calm: CALM
      };
    },

    __synth: function () {
      if (window.CLPlotHudSynth && typeof window.CLPlotHudSynth.create === 'function') return window.CLPlotHudSynth.create();
      return { ok: false, reason: 'test fixture not loaded', src: 'fixture', fp: '', chapters: [], events: [], threads: [], trunk: { segments: [], events: [], len: 0, chapters: 0, gaps: [] }, handoffs: [], junctions: [], cast: {}, warn: ['test fixture not loaded'] };
    }
  };

  window.CLPlotHud = API;
  if (window.CLAttrSource && typeof window.CLAttrSource.subscribe === 'function') {
    window.CLAttrSource.subscribe(function () { if (mounted && dirty && TREE) render(); });
  }

  // 秘仪层插件位：只注册 build（拿 o.graph）。故意不给 dispose / update ——
  // arcana 在每次 build 前会 fan 一遍 dispose，跟着拆就会把正在读的面板抽掉；
  // 而这一层没有逐帧成本，也就不需要 update。
  function hook() {
    if (window.CLArcana && window.CLArcana.register) {
      window.CLArcana.register({ name: 'plot-hud', build: function (o) { API.build(o); } });
    } else {
      mount();                                              // 秘仪层缺席也要能自己站起来（契约 §0.4 守空）
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook);
  else hook();
})();
