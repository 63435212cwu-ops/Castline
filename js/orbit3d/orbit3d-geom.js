/* Castline · js/orbit3d-geom.js — v47「ORBIT-3D」纯几何描述（window.CLOrbit3DGeom）
 *
 * @role geom
 * @owns js/orbit3d/orbit3d-geom.js
 * @budget n/a（纯计算 O(n log n)，无逐帧开销、无 DOM / THREE / 材质）
 * @contract v47
 *
 * build(tree, opts) → desc：契约 §4 的几何描述，layer 的唯一输入。
 * 纯函数：不读 DOM、不建 THREE、不用 Math.random / Date；同一入参两次调用 JSON 等值。
 *
 * 角度：与 js/plot-orbit.js 同一条公式，不另起一套。
 *   angle = π/2 − (orderIndex / total)·2π + 2π   时间前进 = 角度递减 ⇒ 每条弧 aStart ≥ aEnd。
 *   opts.orbit 给了 CLPlotOrbit 的输出就直接复用它的 angle（两者本来同值），否则本文件按
 *   tree.trunk.events 的时间序自算；trunk 覆盖不全（demo / sample-large 只有主干在 trunk 上）
 *   时回落到 events 按 order 排序——两条路的角度必须完全一致。
 *
 * 数值镜像 CLOrbit3DTokens.SIZE（tokens 是唯一数值来源，但 geom 必须能在没有 tokens 的 Node
 * 里纯跑，所以这里按契约 §4 写死同一组比例；改 tokens 必须同步改这里）：
 *   主线带 laneR[0] = R·0.965；支线贪心车道号 k 无上限，落半径时回绕 + 亚道内缩：
 *     kv = ((k−1) mod 6) + 1，m = min(2, floor((k−1)/6))
 *     r  = max(R·0.45, R·(0.905 − 0.062·(kv−1)) − R·0.062·0.34·m)
 *   GAP = 0.05 rad。sample-saga 某个角度上真有 11 条支线同时在跑（T5 一条铺满 93% 环），
 *   6 道是结构性不足而不是调参问题，所以回绕是必须的，不是降级（ENCODING §2.3 / §2.4）。
 *
 * 颜色只从 CLPalette 取（主线段 mainColor(段序)、珠 hex(kind)）或用 thread.color；
 * 没有 CLPalette 时珠色给 null，交给 layer 自己解析，本文件绝不裸写 hex。
 */
(function () {
  'use strict';

  var NAME = 'orbit3d-geom';
  var VERSION = '47';
  var TAU = Math.PI * 2;
  var MERIDIAN = Math.PI / 2;

  var MAIN_K = 0.965;
  var BR0 = 0.905;
  var BR_STEP = 0.062;
  var FLOOR_K = 0.45;
  var GAP = 0.05;
  var VIS_LANES = 6;
  var WRAP_INSET = 0.34;   /* 亚道内缩 = LANE_STEP·0.34 = 0.021R（ENCODING §2.4） */
  var WRAP_MAX = 2;        /* 回绕圈号上限 m∈{0,1,2} ⇒ 18 个互不相同的半径 */

  /* tendril：三次 Bezier 的控制臂长 = r·sweep/3，正是「半径 r、张角 sweep 的圆弧」的
   * 三次近似臂长，所以分叉曲线的曲率与它两端的弧同量级，接上去不会拐硬角。
   * 真实数据里每条支线的 attach 就是它自己的首个事件（saga 15 条全如此），张角为 0，
   * 于是给一个下限 0.08 rad ≈ 81 事件盘的一个事件步长（2π/81 = 0.0776），
   * 让「从主线带上长出来」这件事有一段看得见的行程，而不是一根直插的辐条。 */
  var FORK_MIN_SWEEP = 0.08;
  var FORK_K = 1 / 3;
  var MAX_SAMPLES = 4096;

  /* ─────────────── 小工具（全部确定性） ─────────────── */
  function isArr(v) { return Object.prototype.toString.call(v) === '[object Array]'; }
  function isObj(v) { return !!v && typeof v === 'object' && !isArr(v); }
  function num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function str(v) { return v == null ? '' : String(v); }
  function r6(v) { return Math.round(v * 1e6) / 1e6; }
  function cmpStr(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }

  function colorOf(v) {
    if (typeof v === 'number' && isFinite(v)) return Math.floor(v);
    if (typeof v === 'string' && v) {
      var s = v.charAt(0) === '#' ? v.slice(1) : (v.slice(0, 2).toLowerCase() === '0x' ? v.slice(2) : v);
      if (/^[0-9a-fA-F]{6}$/.test(s)) return parseInt(s, 16);
    }
    return null;
  }
  function paletteOf() {
    try { if (typeof window !== 'undefined' && window && window.CLPalette) return window.CLPalette; } catch (e) {}
    return null;
  }
  function kindColor(P, kind) {
    if (!P || typeof P.hex !== 'function') return null;
    var c = P.hex(kind);
    return (typeof c === 'number' && isFinite(c)) ? c : null;
  }
  function segColor(P, i, fallback) {
    if (P && typeof P.mainColor === 'function') {
      var c = P.mainColor(i);
      if (typeof c === 'number' && isFinite(c)) return c;
    }
    return fallback;
  }
  /** 待校对唯一判据（ENCODING §7.2，geom / layer / legend / labels / interact 同源）：
   *  字段缺失 = 不适用 ≠ 待校对。demo 与 sample-large 走推导路径，线上根本没有
   *  topologyStatus / anchored 两个键，按契约字面判据会 7/7、48/48 整盘变灰。 */
  function isPending(status, anchored) {
    if (anchored === true) return true;
    return !!(status && status !== 'confirmed');
  }
  function angleFor(orderIndex, total) {
    var t = total > 0 ? (orderIndex / total) : 0;
    return r6(Math.PI / 2 - t * TAU + TAU);
  }
  function px(a, r) { return r * Math.cos(a); }
  function py(a, r) { return r * Math.sin(a); }

  /* ─────────────── 公共几何助手（layer 采样用；不进 desc） ─────────────── */
  /** 沿圆按角度采样：时间前进 = 角度递减，所以从 aStart 递减走到 aEnd，两端都取到。
   *  契约 §4「弧必须按角度采样贴圆」，两点直连是明令禁止的。 */
  function sampleArc(aStart, aEnd, r, step) {
    var a0 = num(aStart, 0), a1 = num(aEnd, 0), rr = num(r, 0);
    var st = Math.abs(num(step, 0.02));
    if (!(st > 0)) st = 0.02;
    var span = a0 - a1;
    var out = [];
    if (!(span > 0)) { out.push([px(a0, rr), py(a0, rr)]); out.push([px(a1, rr), py(a1, rr)]); return out; }
    var n = Math.ceil(span / st);
    if (n < 1) n = 1;
    if (n > MAX_SAMPLES) n = MAX_SAMPLES;
    for (var i = 0; i <= n; i++) {
      var a = a0 - span * (i / n);
      out.push([px(a, rr), py(a, rr)]);
    }
    return out;
  }
  /** 三次 Bezier：n 段 → n+1 点，首末点就是 p0 / p1。 */
  function bezier(p0, c1, c2, p1, n) {
    var m = Math.floor(num(n, 16));
    if (!(m >= 1)) m = 1;
    if (m > MAX_SAMPLES) m = MAX_SAMPLES;
    var ax = num(p0 && p0[0], 0), ay = num(p0 && p0[1], 0);
    var bx = num(c1 && c1[0], 0), by = num(c1 && c1[1], 0);
    var cx = num(c2 && c2[0], 0), cy = num(c2 && c2[1], 0);
    var dx = num(p1 && p1[0], 0), dy = num(p1 && p1[1], 0);
    var out = [];
    for (var i = 0; i <= m; i++) {
      var t = i / m, u = 1 - t;
      var w0 = u * u * u, w1 = 3 * u * u * t, w2 = 3 * u * t * t, w3 = t * t * t;
      out.push([w0 * ax + w1 * bx + w2 * cx + w3 * dx, w0 * ay + w1 * by + w2 * cy + w3 * dy]);
    }
    return out;
  }

  /* ─────────────── 空态 ─────────────── */
  function blank(R, ry, reason) {
    return {
      ok: false, version: VERSION, R: r6(R), ry: r6(ry),
      order: [], angleOf: {}, lanes: 0, laneR: [r6(R * MAIN_K)],
      arcs: [], forks: [], beads: [], handoffs: [],
      meridian: { angle: MERIDIAN }, pending: [], crowded: false,
      warn: [reason]
    };
  }

  /* ─────────────── 时间序与角度 ─────────────── */
  function orderOf(tree, orbit, byEv, nEv, warn) {
    var i, cand, src;
    function take(list, key) {
      var seen = {}, out = [], j;
      for (j = 0; j < list.length; j++) {
        var v = list[j];
        var id = Math.floor(num(key ? num(v && v[key], num(v && v.i, -1)) : v, -1));
        if (id < 0 || !byEv[id] || seen[id]) return null;   /* 缺项/重项 ⇒ 这条路不可信 */
        seen[id] = 1; out.push(id);
      }
      return out.length === nEv ? out : null;
    }
    if (orbit && isArr(orbit.events) && orbit.events.length) {
      cand = take(orbit.events, 'evIdx');
      if (cand) return { order: cand, src: 'orbit' };
      warn.push('orbit-order-partial');
    }
    if (tree.trunk && isArr(tree.trunk.events) && tree.trunk.events.length) {
      cand = take(tree.trunk.events, null);
      if (cand) return { order: cand, src: 'trunk' };
      /* demo / sample-large：trunk 只收主干事件，覆盖不全属正常，不算告警 */
    }
    var all = [];
    for (var k in byEv) if (Object.prototype.hasOwnProperty.call(byEv, k)) all.push(byEv[k]);
    all.sort(function (a, b) {
      if (a.order !== b.order) return a.order - b.order;
      return a.evIdx - b.evIdx;
    });
    var out = [];
    for (i = 0; i < all.length; i++) out.push(all[i].evIdx);
    return { order: out, src: 'order' };
  }

  /* ─────────────── 主线接棒切段 ─────────────── */
  /** 段来自 tree.handoffs（来源声明的换手，带 接棒/并流/断层 三型），不重算 lead 变化；
   *  handoffs 为空时才退回「沿主干按 lead 归属变化切」。 */
  function cutSegments(tree, trunkSeq, posInTrunk, ownerMain, mainById, warn) {
    var segs = [], i;
    var hs = isArr(tree.handoffs) ? tree.handoffs : [];
    var cuts = [];
    for (i = 0; i < hs.length; i++) {
      var h = hs[i] || {};
      var at = Math.floor(num(h.at, -1));
      var p = (at >= 0 && posInTrunk[at] !== undefined) ? posInTrunk[at] : -1;
      if (p <= 0) { if (at >= 0 && p !== 0) warn.push('handoff-off-trunk:' + at); continue; }
      cuts.push({ p: p, at: at, from: str(h.from), to: str(h.to), kind: str(h.kind),
        reason: (typeof h.reason === 'string') ? h.reason : null,
        shared: isArr(h.shared) ? h.shared.slice(0) : null });
    }
    cuts.sort(function (a, b) { return a.p !== b.p ? a.p - b.p : cmpStr(a.at + '', b.at + ''); });
    var dedup = [], lastP = -1;
    for (i = 0; i < cuts.length; i++) {
      if (cuts[i].p === lastP) { warn.push('handoff-dup:' + cuts[i].at); continue; }
      lastP = cuts[i].p; dedup.push(cuts[i]);
    }
    cuts = dedup;
    if (!cuts.length && trunkSeq.length) {
      /* 兜底：没有换手记录时按主干事件的归属线切段 */
      for (i = 1; i < trunkSeq.length; i++) {
        if (ownerMain[trunkSeq[i]] !== ownerMain[trunkSeq[i - 1]]) {
          cuts.push({ p: i, at: trunkSeq[i], from: str(ownerMain[trunkSeq[i - 1]]),
            to: str(ownerMain[trunkSeq[i]]), kind: '', reason: null, shared: null });
        }
      }
      if (cuts.length) warn.push('handoffs-empty-derived');
    }
    var bounds = [0];
    for (i = 0; i < cuts.length; i++) bounds.push(cuts[i].p);
    bounds.push(trunkSeq.length);
    for (i = 0; i + 1 < bounds.length; i++) {
      var a = bounds[i], b = bounds[i + 1];
      if (b <= a) continue;
      var lead = (i === 0) ? (cuts.length ? cuts[0].from : '') : cuts[i - 1].to;
      if (!lead || !mainById[lead]) {
        var guess = ownerMain[trunkSeq[a]];
        if (lead && !mainById[lead]) warn.push('handoff-unknown-line:' + lead);
        lead = guess ? guess : '';
      }
      segs.push({ lineId: lead, from: trunkSeq[a], to: trunkSeq[b - 1], n: b - a });
    }
    return { segs: segs, cuts: cuts };
  }

  /* ─────────────── 主体 ─────────────── */
  function build(tree, opts) {
    opts = opts || {};
    var P = paletteOf();
    var orbit = (isObj(opts.orbit) && opts.orbit.ok !== false) ? opts.orbit : null;
    var R = num(opts.R, 0);
    if (!(R > 0) && orbit) R = num(orbit.frame && orbit.frame.R, 0);
    var ry = num(opts.ry, orbit ? num(orbit.frame && orbit.frame.ry, 1) : 1);
    var gap = num(opts.gap, GAP); if (!(gap >= 0)) gap = GAP;
    /* maxLanes = **可见**道数（回绕模数），不是车道总数上限 */
    var maxLanes = Math.floor(num(opts.maxLanes, VIS_LANES)); if (!(maxLanes >= 1)) maxLanes = VIS_LANES;

    if (!(R > 0)) return blank(0, ry, 'no-radius');
    if (!isObj(tree) || tree.ok === false) return blank(R, ry, 'no-tree');
    var evs = isArr(tree.events) ? tree.events : [];
    var ths = isArr(tree.threads) ? tree.threads : [];
    if (!evs.length) return blank(R, ry, 'no-events');
    if (!ths.length) return blank(R, ry, 'no-threads');

    var warn = [], i, j, k;

    /* 1 · 事件表 */
    var byEv = {}, nEv = 0;
    for (i = 0; i < evs.length; i++) {
      var e = evs[i] || {};
      var id = Math.floor(num(e.i, i));
      if (id < 0 || byEv[id]) { warn.push('dup-event:' + id); continue; }
      byEv[id] = { evIdx: id, order: num(e.order, i + 1), kind: str(e.kind), w: num(e.w, 0) };
      nEv++;
    }
    if (!nEv) return blank(R, ry, 'no-events');

    /* 2 · 时间序 + 角度（唯一一条公式） */
    var od = orderOf(tree, orbit, byEv, nEv, warn);
    var order = od.order;
    var angleOf = {};
    var orbAngle = {};
    if (od.src === 'orbit') {
      for (i = 0; i < orbit.events.length; i++) {
        var oe = orbit.events[i] || {};
        var oid = Math.floor(num(oe.evIdx, num(oe.i, -1)));
        if (oid >= 0) orbAngle[oid] = num(oe.angle, NaN);
      }
    }
    for (i = 0; i < order.length; i++) {
      var ev = order[i];
      var a = (od.src === 'orbit') ? orbAngle[ev] : NaN;
      angleOf[ev] = r6(num(a, angleFor(i, order.length)));
    }

    /* 3 · 线表。status 原样记（缺字段就是空串，「没有的就是没有」），待校对只认 isPending()。
     *      resolved / suspended 也原样抄：两者皆 false 是第三态「未定」，
     *      saga 的 T13 / T17 就在这一态上，既不画收束珠也不画悬置渐隐，不得补成任何一边。 */
    var recs = [], byId = {}, ownerCount = {};
    for (i = 0; i < ths.length; i++) {
      var t = ths[i] || {};
      var tid = str(t.id) || ('T' + i);
      if (byId[tid]) { warn.push('dup-line:' + tid); continue; }
      var raw = isArr(t.events) ? t.events : [];
      var clean = [], seenE = {};
      for (j = 0; j < raw.length; j++) {
        var q = Math.floor(num(raw[j], -1));
        if (q < 0 || seenE[q]) continue;
        if (!byEv[q]) { warn.push('missing-event:' + tid + ':' + q); continue; }
        seenE[q] = 1; clean.push(q);
      }
      if (!clean.length) { warn.push('empty-line:' + tid); continue; }
      var st = (typeof t.topologyStatus === 'string') ? t.topologyStatus : '';
      var anch = (t.anchored === true);
      var att = (t.attach == null) ? -1 : Math.floor(num(t.attach, -1));
      var rec = {
        id: tid, kind: (str(t.kind) === 'main') ? 'main' : 'branch', rawKind: str(t.kind),
        lead: str(t.lead), parent: (t.parent == null) ? '' : str(t.parent),
        attach: att >= 0 ? att : null, status: st, anchored: anch,
        valid: !isPending(st, anch),
        resolved: (t.resolved === true), suspended: (t.suspended === true),
        color: colorOf(t.color), heat: num(t.heat, 0), events: clean, lane: 0, r: 0
      };
      /* 陷阱 A（ENCODING §12）：thread.span 是**章节下标**不是角度（saga T5 span 0→28
       * 却只有 5 个事件），弧的起止角只能来自 thread.events[0] / [len−1] 经 angleOf。 */
      rec.aFirst = angleOf[clean[0]];
      rec.aLast = angleOf[clean[clean.length - 1]];
      rec.aStart = rec.aFirst; rec.aEnd = rec.aLast;
      if (rec.aFirst < rec.aLast) {
        /* 事件未按时间序 ⇒ 上游异常。报警并退回包络，保住 aStart ≥ aEnd 不变量 */
        warn.push('unsorted-line:' + tid);
        var aMax = -Infinity, aMin = Infinity;
        for (j = 0; j < clean.length; j++) {
          var ag = angleOf[clean[j]];
          if (ag > aMax) aMax = ag;
          if (ag < aMin) aMin = ag;
        }
        rec.aStart = aMax; rec.aEnd = aMin;
      }
      for (j = 0; j < clean.length; j++) ownerCount[clean[j]] = (ownerCount[clean[j]] || 0) + 1;
      recs.push(rec); byId[tid] = rec;
    }
    if (!recs.length) return blank(R, ry, 'no-threads');

    /* 4 · 车道：主线统一 lane 0；支线按 aStart 时间序贪心装箱（沿用 v46.1 实测逻辑） */
    var branches = [], mains = [];
    for (i = 0; i < recs.length; i++) (recs[i].kind === 'main' ? mains : branches).push(recs[i]);
    branches.sort(function (x, y) {
      if (y.aStart !== x.aStart) return y.aStart - x.aStart;
      return cmpStr(String(x.id), String(y.id));
    });
    /* 贪心首次适配，车道数**不封顶**：sample-saga 在某个角度上真有 11 条支线同时在跑，
     * 任何装箱都不可能少于 11 道（ENCODING §2.3 的下界证明），封到 6 道只能靠重叠作弊。
     * 6 是**可见道**数，超出的道号在落半径时回绕并向内让 0.021R（§2.4），互不压线。 */
    var laneLast = {}, laneCount = 0, crowded = false;
    for (i = 0; i < branches.length; i++) {
      var c = branches[i], lane = -1;
      for (k = 1; k <= laneCount; k++) {
        if (laneLast[k] - gap > c.aStart) { lane = k; break; }
      }
      if (lane === -1) { laneCount++; lane = laneCount; laneLast[lane] = Infinity; }
      laneLast[lane] = Math.min(laneLast[lane], c.aEnd);
      c.lane = lane;
    }
    /* k → 半径：kv 可见道号、m 回绕圈号（m>0 的弧标 crowded，供 layer 画内缘细暗边） */
    var laneR = [r6(R * MAIN_K)], laneV = [0], laneM = [0];
    for (k = 1; k <= laneCount; k++) {
      var kv = ((k - 1) % maxLanes) + 1;
      var m = Math.floor((k - 1) / maxLanes);
      if (m > WRAP_MAX) m = WRAP_MAX;
      laneV.push(kv); laneM.push(m);
      laneR.push(r6(Math.max(R * FLOOR_K,
        R * (BR0 - BR_STEP * (kv - 1)) - R * BR_STEP * WRAP_INSET * m)));
      if (m > 0) crowded = true;
    }
    if (laneCount > maxLanes) warn.push('lanes-wrapped:' + (laneCount - maxLanes));
    for (i = 0; i < mains.length; i++) { mains[i].lane = 0; mains[i].r = laneR[0]; }
    for (i = 0; i < branches.length; i++) branches[i].r = laneR[branches[i].lane];

    /* 5 · 主干时间序 + 接棒切段 */
    var trunkSeq = [], posInTrunk = {}, ownerMain = {};
    for (i = 0; i < mains.length; i++) {
      for (j = 0; j < mains[i].events.length; j++) {
        if (ownerMain[mains[i].events[j]] === undefined) ownerMain[mains[i].events[j]] = mains[i].id;
      }
    }
    var trunkRaw = (tree.trunk && isArr(tree.trunk.events) && tree.trunk.events.length) ? tree.trunk.events : null;
    if (trunkRaw) {
      for (i = 0; i < trunkRaw.length; i++) {
        var tv = Math.floor(num(trunkRaw[i], -1));
        if (tv < 0 || !byEv[tv] || posInTrunk[tv] !== undefined) continue;
        posInTrunk[tv] = trunkSeq.length; trunkSeq.push(tv);
      }
    } else {
      var pool = [];
      for (i = 0; i < order.length; i++) if (ownerMain[order[i]] !== undefined) pool.push(order[i]);
      for (i = 0; i < pool.length; i++) { posInTrunk[pool[i]] = i; trunkSeq.push(pool[i]); }
    }
    var cut = cutSegments(tree, trunkSeq, posInTrunk, ownerMain, byId, warn);
    var segsByLine = {};
    for (i = 0; i < cut.segs.length; i++) {
      var sg = cut.segs[i];
      var host = byId[sg.lineId] && byId[sg.lineId].kind === 'main' ? byId[sg.lineId] : null;
      var fall = host ? host.color : null;
      var one = {
        aStart: angleOf[sg.from], aEnd: angleOf[sg.to],
        lead: host ? host.lead : '', color: segColor(P, i, fall)
      };
      if (!host) { warn.push('segment-no-line:' + sg.from); continue; }
      (segsByLine[host.id] = segsByLine[host.id] || []).push(one);
    }

    /* 6 · arcs（线序 = tree.threads 序，确定性） */
    var arcs = [], byArc = {}, pending = [];
    for (i = 0; i < recs.length; i++) {
      var rc = recs[i];
      var segs = segsByLine[rc.id];
      if (rc.kind === 'main') {
        if (!segs || !segs.length) {
          segs = [{ aStart: rc.aStart, aEnd: rc.aEnd, lead: rc.lead, color: segColor(P, 0, rc.color) }];
          warn.push('main-no-segment:' + rc.id);
        }
      } else {
        segs = [{ aStart: rc.aStart, aEnd: rc.aEnd, lead: rc.lead, color: rc.color }];
      }
      var sw = Math.abs(rc.aStart - rc.aEnd);
      var arcLen = r6(sw * rc.r);
      var lenRatio = r6(Math.min(1, sw / TAU));
      var forkOrig = null;
      if (rc.kind !== 'main' && rc.parent) {
        forkOrig = {
          parent: rc.parent,
          attachEv: rc.attach,
          angle: (rc.attach != null && angleOf[rc.attach] !== undefined) ? angleOf[rc.attach] : null,
          r: (byId[rc.parent] ? byId[rc.parent].r : laneR[0])
        };
      }
      var arc = {
        lineId: rc.id, kind: rc.kind, lane: rc.lane, laneV: laneV[rc.lane], wrap: laneM[rc.lane],
        r: rc.r, crowded: laneM[rc.lane] > 0,
        aStart: rc.aStart, aEnd: rc.aEnd, sweep: r6(sw),
        arcLength: arcLen, lengthRatio: lenRatio, forkOrigin: forkOrig,
        valid: rc.valid, anchored: rc.anchored, status: rc.status,
        resolved: rc.resolved, suspended: rc.suspended,
        color: (rc.kind === 'main') ? segs[0].color : rc.color,
        heat: rc.heat, len: rc.events.length, lead: rc.lead,
        beads: rc.events.slice(0), segments: segs
      };
      arcs.push(arc); byArc[rc.id] = arc;
      if (!rc.valid) pending.push(rc.id);
    }

    /* 7 · beads：每个 occurrence 一珠（线 × 事件），共享事件多珠 */
    var beads = [];
    for (i = 0; i < recs.length; i++) {
      var rb = recs[i];
      for (j = 0; j < rb.events.length; j++) {
        var bv = rb.events[j], be = byEv[bv];
        beads.push({
          evIdx: bv, lineId: rb.id, angle: angleOf[bv], r: rb.r, w: be.w,
          kind: be.kind, color: kindColor(P, be.kind),
          owners: (ownerCount[bv] || 0), shared: (ownerCount[bv] || 0) > 1,
          first: j === 0, last: j === rb.events.length - 1
        });
      }
    }

    /* 8 · forks：只给 valid 支线；父线必须在 desc 里 */
    var forks = [];
    for (i = 0; i < recs.length; i++) {
      var rf = recs[i];
      if (rf.kind === 'main' || !rf.valid) continue;
      if (!rf.parent) { warn.push('no-parent:' + rf.id); continue; }
      var par = byId[rf.parent];
      if (!par) { warn.push('orphan-parent:' + rf.id); continue; }
      if (rf.attach == null || !byEv[rf.attach]) { warn.push('missing-attach:' + rf.id); continue; }
      var a0 = angleOf[rf.attach], r0 = par.r;
      var a1 = rf.aFirst, r1 = rf.r;
      var sweep = a0 - a1;
      if (sweep < 0) warn.push('fork-backwards:' + rf.id);
      if (!(sweep > FORK_MIN_SWEEP)) sweep = FORK_MIN_SWEEP;
      /* u(a) = (sin a, −cos a) 是「时间前进」方向（角度递减）的单位切向。
       * c1 = p0 + r0·sweep/3 · u(a0)  —— 贴着父线带、顺时间方向离开，出发段与主线同切线；
       * c2 = p1 − r1·sweep/3 · u(a1)  —— 从支线弧的上游方向切进首珠，落点与支线弧同切线。
       * 两端切向被钉住，半径差 (r0 − r1) 只能在中段消化，于是曲线自然向内弯成一条须。 */
      var L0 = r0 * sweep * FORK_K, L1 = r1 * sweep * FORK_K;
      var c1x = px(a0, r0) + L0 * Math.sin(a0), c1y = py(a0, r0) - L0 * Math.cos(a0);
      var c2x = px(a1, r1) - L1 * Math.sin(a1), c2y = py(a1, r1) + L1 * Math.cos(a1);
      forks.push({
        lineId: rf.id, parentId: par.id, evIdx: rf.attach, angle: a0,
        rFrom: r0, rTo: r1, ctrl: [[r6(c1x), r6(c1y)], [r6(c2x), r6(c2y)]]
      });
    }

    /* 9 · handoffs：原样读 tree.handoffs（含 接棒/并流/断层），落到主线带半径上 */
    var handoffs = [];
    for (i = 0; i < cut.cuts.length; i++) {
      var cu = cut.cuts[i];
      /* kind(接棒/并流/断层) 决定光脊形态，reason / shared 只进卡片（ENCODING §3.1）；
       * 三者一律原样透传 tree.handoffs，零推断。上游没有的键给 null，不伪造。 */
      handoffs.push({
        evIdx: cu.at, angle: angleOf[cu.at], r: laneR[0],
        from: cu.from, to: cu.to, kind: cu.kind,
        reason: cu.reason, shared: cu.shared
      });
    }

    /* 10 · genesis anchor 与宏伟纪元阶段（Epoch Milestones） */
    var firstEv = (trunkSeq.length ? trunkSeq[0] : (order.length ? order[0] : 0));
    var firstAngle = (angleOf[firstEv] !== undefined) ? angleOf[firstEv] : MERIDIAN;
    var mainR = laneR[0];
    var genesis = {
      evIdx: firstEv,
      angle: r6(firstAngle),
      r: r6(mainR),
      x: r6(px(firstAngle, mainR)),
      y: r6(py(firstAngle, mainR)),
      lead: (recs.length && recs[0].kind === 'main') ? recs[0].lead : '',
      label: '主线起点 · 纪元启航'
    };

    var epochs = [];
    var epochNames = ['纪元破晓 · 启航发端', '风云际会 · 剧情推进', '风暴前夕 · 矛盾激化', '巅峰对决 · 命运高潮', '万流归海 · 纪元收束'];
    var nTrunk = trunkSeq.length || order.length || 1;
    var nEpochs = Math.min(5, Math.max(3, Math.floor(nTrunk / 6) + 1));
    for (var ep = 0; ep < nEpochs; ep++) {
      var idxInTrunk = Math.min(nTrunk - 1, Math.floor(ep * (nTrunk - 1) / Math.max(1, nEpochs - 1)));
      var epEv = trunkSeq.length ? trunkSeq[idxInTrunk] : order[idxInTrunk];
      var epAng = (angleOf[epEv] !== undefined) ? angleOf[epEv] : (MERIDIAN - (ep / nEpochs) * TAU);
      epochs.push({
        epochIdx: ep + 1,
        title: epochNames[ep] || ('纪元阶段 · 第 ' + (ep + 1) + ' 幕'),
        evIdx: epEv,
        angle: r6(epAng),
        r: r6(mainR),
        ratio: r6(ep / Math.max(1, nEpochs - 1))
      });
    }

    return {
      ok: true, version: VERSION, R: r6(R), ry: r6(ry),
      order: order, angleOf: angleOf,
      lanes: laneCount, laneR: laneR,
      arcs: arcs, forks: forks, beads: beads, handoffs: handoffs,
      genesis: genesis, epochs: epochs,
      meridian: { angle: MERIDIAN },
      pending: pending, crowded: crowded, warn: warn
    };
  }

  function stats(desc) {
    var d = isObj(desc) ? desc : null;
    return {
      arcs: d && isArr(d.arcs) ? d.arcs.length : 0,
      forks: d && isArr(d.forks) ? d.forks.length : 0,
      beads: d && isArr(d.beads) ? d.beads.length : 0,
      handoffs: d && isArr(d.handoffs) ? d.handoffs.length : 0,
      pending: d && isArr(d.pending) ? d.pending.length : 0,
      lanes: d ? num(d.lanes, 0) : 0,
      crowded: !!(d && d.crowded)
    };
  }

  var API = {
    name: NAME, version: VERSION,
    build: build, stats: stats, sampleArc: sampleArc, bezier: bezier
  };
  try { window.CLOrbit3DGeom = API; }
  catch (e) { if (typeof module !== 'undefined' && module.exports) module.exports = API; }
})();
