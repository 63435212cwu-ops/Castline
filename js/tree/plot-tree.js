/* Castline · plot-tree.js — 星云中的剧情树（v30.0 · B 面）
 *
 * 这一层要回答的问题是：一部作品的**剧情形状**长什么样？
 * 线谱 HUD（D 面）是时间读法 —— 一格一章，横着读。这里是空间读法：把剧情长成一棵树，
 * 让人不读任何数字就先看懂三件事：
 *
 *   ① 主线有多长                主干的长度**就是** trunk.len（每个剧情点一小段，不是"象征性地画根柱子"）
 *   ② 主线中途换过手            主干分段换色 + 接缝处一圈接续环（graft ring）+ 三道接骨纹 + 一个换手标。
 *                               这是本层最重要的一条视觉证据：前半程走完，另一组人接着推进，**往后接上**。
 *   ③ 谁在哪条线上、结局如何    每条线上参与者各一颗星珠（大小 = 其在该线的权重，颜色 = 阵营）；
 *                               收束的线末端收成亮结，悬置的线末端散成渐隐的丝。
 *
 * 为什么是「长在星云里」而不是一张浮在前面的示意图：
 * 树的每一段都套一层加性柔光鞘（sheath），鞘的亮度按视角衰减（正对镜头最亮、掠射最淡），
 * 于是线与背后的星云是同一种介质，而不是贴在玻璃上的图形。根部还刻意埋进盘面之下 0.055 ——
 * 看起来是从星云里长出来的，不是摆上去的。
 *
 * 几何取向：树沿**盘面法线**向上长（契约的「+Z 偏 +Y」），所以它是从银道面里立起来的，
 * 镜头一动就有真视差；倾角小到几乎没有（chain/camps 模式）时自动多偏 +Y，否则会正对镜头缩成一个点。
 * 单位空间里主干长度恒为 1.0，整棵树靠 root.scale 一次定标 —— 定标值由**真实投影**解出来
 * （二分求 L 让主干尖端落在 NDC y ≈ 0.55），因此 5 个角色的示例图与 200 个角色的大图谱
 * 都占同样的画面比例，不用为每种规模手调常数。
 *
 * 成本：整棵树 = 骨架 1 + 鞘 1（共用同一份顶点缓冲，只差顶点着色器里的 uFat）+ 接续环 1
 * + 交汇 1 + 星珠/主导环/结与十字 3 个 Points ≈ 7 个 draw call，CPU 每帧只推 uniform。
 *
 * 接线：本文件通过 CLArcana.register() 挂进秘仪层，由它代转 build / update / dispose / setOn。
 * scene.js / index.html / app.js 一行不改 —— 那些文件有并行会话在写，碰它们就是丢改动。
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- 常数
  var GOLD = 137.50776405003785 * Math.PI / 180;
  var GROW_T = 3.6;
  var G_TRUNK = 0.72;
  var G_BR0 = 0.30, G_BR1 = 0.72, G_BR_D = 0.11;
  var G_BEAD0 = 0.79, G_BEAD1 = 0.985;
  var MAX_BRANCH = 40;
  var TIP_NDC = 0.55;
  var CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var HUD_SEL = '#brand .panel, #index .panel, #overview .panel, #ops, #constellationMark, ' +
                '#dock.on .panel, #crumb.on .btn, #hint, #runbar.on .panel, #attach.on .panel, #peek.on';
  var KIND_COL = { 高燃: 0xffd166, 转折: 0xffb45c, 抉择: 0xc8a7ff, 冲突: 0xff5d73, 关系: 0xff9ad5, 领悟: 0x7af0c8, 日常: 0x9a92b8 };
  var STANCE_COL = { 主角方: 0xffd27a, 盟友: 0xf6dfa4, 中立: 0xcbbcf0, 摇摆: 0xffa07a, 对立: 0xff5d73 };
  if (window.CLPalette) {
    if (window.CLPalette.map) KIND_COL = window.CLPalette.map();
    if (window.CLPalette.campMap) {
      var _camp = window.CLPalette.campMap();
      var _s, _sc = {};
      for (_s in _camp) if (Object.prototype.hasOwnProperty.call(_camp, _s) && _s !== '') _sc[_s] = _camp[_s];
      STANCE_COL = _sc;
    }
  }
  var ROLE = { TRUNK: 0, BRANCH: 1, TWIG: 2, RING: 3, RIB: 4, FRAY: 5, JUNC: 6 };

  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  // ---------------------------------------------------------------- v45 严格模式
  // 旧 layout 长一棵独立伪树就是「两棵剧情树」，违反用户要求。所以严格模式下本层只做接线：
  function strictTree(t) {
    if (t && t.strictTopology === true) return true;
    if (t && t.logical === true) return true;
    return false;
  }
  function strictNow() {
    if (strict) return true;
    if (strictTree(tree)) { strict = true; return true; }
    var g = window.CLTreeGhost;
    if (g && g.shapeOf) { var s = tryFn(g.shapeOf); if (s && s.logical === true) { strict = true; return true; } }
    return false;
  }
  function firstEventOfThread(id) {
    var ths = (tree && tree.threads) || [], i, th = null;
    for (i = 0; i < ths.length; i++) if (ths[i] && String(ths[i].id) === String(id)) { th = ths[i]; break; }
    if (!th) return -1;
    var es = th.events || [];
    if (!es.length) return -1;
    var v = es[0];
    if (v && typeof v === 'object') v = (v.i != null ? v.i : v.evIdx);
    v = Math.floor(num(v, -1));
    return v >= 0 ? v : -1;
  }

  // ---------------------------------------------------------------- 状态
  var T = null, O = null, ready = false, muted = false, on = 0;
  var tree = null, L = null;
  var root = null, skel = null, sheath = null, graft = null, junc = null;
  var beads = null, leadRings = null, marks = null, eye = null, tops = [];
  var vis = false, grow = 0, target = 0, lastT = -1, deg = 0, scale = 600, needFit = true;
  var CAM = null;
  var focusTh = -1, focusCh = -1, synthMode = false, lodCut = 0;
  var strict = false;
  var labLayer = null, labs = [], labShown = 0;
  var _v = null, _v2 = null, _m = null;

  // ---------------------------------------------------------------- 颜色
  function campColor(camp, name) {
    var CN = window.NCConstellation, COL = (CN && CN.COLOR) || STANCE_COL;
    var g = O && O.graph, i, st = '';
    if (g && g.camps && camp) for (i = 0; i < g.camps.length; i++) if (g.camps[i] && g.camps[i].name === camp) { st = g.camps[i].stance || ''; break; }
    if (!st && g && g.characters && name) for (i = 0; i < g.characters.length; i++) if (g.characters[i] && g.characters[i].name === name) { st = g.characters[i].stance || ''; break; }
    if (!st && camp && COL[camp]) st = camp;
    return COL[st] || STANCE_COL[st] || 0x8d84a8;
  }
  function distinct(cols) {
    var out = [], i, c = new T.Color(), hsl = { h: 0, s: 0, l: 0 }, prev = null;
    for (i = 0; i < cols.length; i++) {
      c.set(cols[i]); c.getHSL(hsl);
      if (prev !== null) {
        var d = Math.abs(hsl.h - prev); d = Math.min(d, 1 - d);
        if (d < 0.075) { hsl.h = (hsl.h + 0.155) % 1; hsl.s = clamp(hsl.s * 1.05, 0, 1); c.setHSL(hsl.h, hsl.s, hsl.l); }
      }
      prev = hsl.h; out.push(c.clone());
    }
    return out;
  }

  function frames(pts) {
    var n = pts.length, tan = [], nor = [], bin = [], i;
    for (i = 0; i < n; i++) {
      var t = new T.Vector3();
      if (i === 0) t.subVectors(pts[1], pts[0]);
      else if (i === n - 1) t.subVectors(pts[n - 1], pts[n - 2]);
      else t.subVectors(pts[i + 1], pts[i - 1]);
      if (t.lengthSq() < 1e-12) t.set(0, 0, 1);
      tan.push(t.normalize());
    }
    var up = new T.Vector3(1, 0, 0);
    if (Math.abs(tan[0].x) > 0.9) up.set(0, 1, 0);
    var nr = new T.Vector3().crossVectors(tan[0], up);
    if (nr.lengthSq() < 1e-10) nr.set(0, 1, 0);
    nr.normalize();
    for (i = 0; i < n; i++) {
      nr.addScaledVector(tan[i], -nr.dot(tan[i]));
      if (nr.lengthSq() < 1e-10) { nr.crossVectors(tan[i], new T.Vector3(0, 1, 0)); if (nr.lengthSq() < 1e-10) nr.set(1, 0, 0); }
      nr.normalize();
      nor.push(nr.clone());
      bin.push(new T.Vector3().crossVectors(tan[i], nr).normalize());
    }
    return { t: tan, n: nor, b: bin };
  }

  function acc() { return { p: [], nm: [], c: [], aP: [], aM: [], aT: [], ix: [], n: 0 }; }

  function tube(A, pts, radFn, radial, meta) {
    if (!pts || pts.length < 2) return;
    var f = frames(pts), n = pts.length, base = A.n, i, j;
    var col = new T.Color(), g0 = num(meta.g0, 0), g1 = num(meta.g1, g0);
    for (i = 0; i < n; i++) {
      var t = n > 1 ? i / (n - 1) : 0, r = Math.max(1e-4, radFn(t, i));
      var gp = meta.col ? meta.col(t, i) : meta.color;
      col.set(gp == null ? 0xffffff : gp);
      var gg = meta.gFn ? meta.gFn(t) : g0 + (g1 - g0) * t, gap = meta.gap ? meta.gap(t) : 0;
      var tv = meta.thFn ? meta.thFn(t) : num(meta.th, -1);
      for (j = 0; j <= radial; j++) {
        var a = Math.PI * 2 * j / radial, ca = Math.cos(a), sa = Math.sin(a);
        var nx = f.n[i].x * ca + f.b[i].x * sa, ny = f.n[i].y * ca + f.b[i].y * sa, nz = f.n[i].z * ca + f.b[i].z * sa;
        A.p.push(pts[i].x + nx * r, pts[i].y + ny * r, pts[i].z + nz * r);
        A.nm.push(nx, ny, nz);
        A.c.push(col.r, col.g, col.b);
        A.aP.push(meta.ang ? j / radial : t, r, gg);
        A.aM.push(meta.role, num(meta.flow, 1), gap);
        A.aT.push(tv);
      }
    }
    for (i = 0; i < n - 1; i++) for (j = 0; j < radial; j++) {
      var v0 = base + i * (radial + 1) + j, v1 = v0 + 1, v2 = v0 + radial + 1, v3 = v2 + 1;
      A.ix.push(v0, v2, v1, v1, v2, v3);
    }
    A.n += n * (radial + 1);
  }

  function ring(A, ctr, u, v, R, tr, meta, segs) {
    var pts = [], i, N = segs || 40;
    for (i = 0; i <= N; i++) {
      var a = Math.PI * 2 * i / N;
      pts.push(new T.Vector3(ctr.x + (u.x * Math.cos(a) + v.x * Math.sin(a)) * R,
        ctr.y + (u.y * Math.cos(a) + v.y * Math.sin(a)) * R,
        ctr.z + (u.z * Math.cos(a) + v.z * Math.sin(a)) * R));
    }
    meta.ang = true;
    tube(A, pts, function () { return tr; }, 6, meta);
  }

  function toGeo(A) {
    if (!A.n) return null;
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(new Float32Array(A.p), 3));
    g.setAttribute('normal', new T.BufferAttribute(new Float32Array(A.nm), 3));
    g.setAttribute('color', new T.BufferAttribute(new Float32Array(A.c), 3));
    g.setAttribute('aP', new T.BufferAttribute(new Float32Array(A.aP), 3));
    g.setAttribute('aM', new T.BufferAttribute(new Float32Array(A.aM), 3));
    g.setAttribute('aTh', new T.BufferAttribute(new Float32Array(A.aT), 1));
    g.setIndex(new T.BufferAttribute(new Uint32Array(A.ix), 1));
    return g;
  }

  function cat(pts, n) {
    var c = new T.CatmullRomCurve3(pts, false, 'catmullrom', 0.5), out = [], i;
    for (i = 0; i <= n; i++) out.push(c.getPoint(i / n));
    return out;
  }

  function layout(tr) {
    var pitch = num(O.pitch, 0);
    var cP = Math.cos(pitch), sP = Math.sin(pitch);
    var eY = new T.Vector3(0, cP, -sP), eZ = new T.Vector3(0, sP, cP), eX = new T.Vector3(1, 0, 0);
    var kY = 0.58 + (0.46 - Math.min(pitch, 0.46)) * 2.9;
    var DIR = eZ.clone().addScaledVector(eY, kY).normalize();
    var UU = eX.clone().addScaledVector(DIR, -eX.dot(DIR)).normalize();
    var VV = new T.Vector3().crossVectors(DIR, UU).normalize();

    var trunk = tr.trunk || {}, segs = trunk.segments || [], tlen = Math.max(1, num(trunk.len, (trunk.events || []).length));
    var tEv = trunk.events || [];
    var evPos = {}, i, j;
    for (i = 0; i < tEv.length; i++) evPos[tEv[i]] = tEv.length > 1 ? i / (tEv.length - 1) : 0;

    // ---- 主干采样
    var NT = 176, tp = [], R0 = 0.0295, R1 = 0.0105;
    var gaps = (trunk.gaps || []).map(function (g) { return { t: num(evPos[g.after], -1), w: 0.014 + Math.min(0.02, num(g.chapters, 1) * 0.004) }; })
      .filter(function (g) { return g.t >= 0; });
    function gapAt(t) {
      var m = 0;
      for (var q = 0; q < gaps.length; q++) {
        var d = Math.abs(t - gaps[q].t);
        if (d < gaps[q].w) m = Math.max(m, 1 - d / gaps[q].w);
      }
      return m;
    }
    function trunkAt(t) {
      var s = Math.sin(t * 2.35 + 0.7) * 0.030 + Math.sin(t * 5.1 + 2.2) * 0.012;
      var s2 = Math.cos(t * 1.85 + 1.4) * 0.024;
      return new T.Vector3()
        .addScaledVector(DIR, -0.055 + t * 1.055)
        .addScaledVector(UU, s * t)
        .addScaledVector(VV, s2 * t);
    }
    function trunkR(t) { return (R0 + (R1 - R0) * Math.pow(t, 0.78)) * (1 - gapAt(t) * 0.46); }
    for (i = 0; i <= NT; i++) tp.push(trunkAt(i / NT));

    // ---- 段色（换手的第一眼证据）
    var segCols = distinct(segs.length ? segs.map(function (s) { return num(s.color, 0xffb45c); }) : [0xffb45c]);
    var segT = [];
    for (i = 0; i < segs.length; i++) {
      var a = num(segs[i].t0, i / Math.max(1, segs.length)), b = num(segs[i].t1, (i + 1) / Math.max(1, segs.length));
      if (!(b > a)) b = Math.min(1, a + 1 / Math.max(1, segs.length));
      segT.push({ t0: clamp(a, 0, 1), t1: clamp(b, 0, 1), id: segs[i].threadId || '', lead: segs[i].lead || '', col: segCols[i] });
    }
    if (!segT.length) segT.push({ t0: 0, t1: 1, id: (tr.threads && tr.threads[0] && tr.threads[0].id) || 'T0', lead: '', col: segCols[0] });
    function gOfT(t) { return G_TRUNK * Math.pow(clamp(t, 0, 1), 0.82); }
    function segAt(t) {
      for (var q = 0; q < segT.length; q++) if (t <= segT[q].t1 + 1e-6) return segT[q];
      return segT[segT.length - 1];
    }
    function colAt(t) {
      var s = segT[segT.length - 1], q;
      for (q = 0; q < segT.length; q++) if (t <= segT[q].t1 + 1e-6) { s = segT[q]; break; }
      if (q > 0 && t - segT[q].t0 < 0.012) {
        var w = (t - segT[q].t0) / 0.012;
        return new T.Color().copy(segT[q - 1].col).lerp(s.col, clamp(w, 0, 1));
      }
      return s.col;
    }

    // ---- 线表
    var thById = {}, threads = tr.threads || [];
    for (i = 0; i < threads.length; i++) if (threads[i] && threads[i].id) thById[threads[i].id] = threads[i];
    var thIdx = {};
    for (i = 0; i < threads.length; i++) thIdx[threads[i].id] = i;
    var chars = {}, cn = 0, nm;
    for (nm in (tr.cast || {})) { chars[nm] = cn++; }

    var branches = [], twigs = [], mains = [];
    for (i = 0; i < threads.length; i++) {
      var th = threads[i], kd = th.kind || (th.depth === 0 ? 'main' : th.depth === 2 ? 'twig' : 'branch');
      if (kd === 'main') mains.push(th); else if (kd === 'twig') twigs.push(th); else branches.push(th);
    }
    branches.sort(function (a, b) {
      var d = num(b.len, 0) - num(a.len, 0);
      return d !== 0 ? d : (String(a.id) < String(b.id) ? -1 : 1);
    });
    lodCut = Math.max(0, branches.length - MAX_BRANCH);
    if (lodCut > 0) branches = branches.slice(0, MAX_BRANCH);
    var order = branches.slice().sort(function (a, b) {
      var ta = num(evPos[a.attach], num(a.span && a.span.from, 0) / 40), tb = num(evPos[b.attach], num(b.span && b.span.from, 0) / 40);
      return ta - tb;
    });
    var rank = {};
    for (i = 0; i < order.length; i++) rank[order[i].id] = order.length > 1 ? i / (order.length - 1) : 0;

    // ---- 支线几何
    var brs = [], beadList = [], markList = [], graftList = [], juncList = [], labList = [];
    var maxLen = 1;
    for (i = 0; i < branches.length; i++) maxLen = Math.max(maxLen, num(branches[i].len, 1));

    function attachT(th, fallback) {
      var t = evPos[th.attach];
      if (t == null) {
        var sp = th.span || {}, nc = Math.max(1, num(trunk.chapters, 1));
        t = num(sp.from, 0) / nc;
      }
      return clamp(num(t, fallback), 0.06, 0.96);
    }
    function lenOf(th, kmul) {
      return clamp(num(th.len, 1) / Math.max(4, tlen), 0.10, 0.55) * (kmul || 1);
    }

    function makeBranch(th, aT, phi, kmul, depth, host) {
      var bl = lenOf(th, kmul);
      var heat = clamp(num(th.heat, 0.4), 0, 1);
      var base, U2, V2, rHost;
      if (host) { base = host.pts[clamp(Math.round(host.pts.length * 0.55), 0, host.pts.length - 1)].clone(); U2 = host.U; V2 = host.V; rHost = host.r0 * 0.7; }
      else { base = trunkAt(aT); U2 = UU; V2 = VV; rHost = trunkR(aT); }
      var rad = U2.clone().multiplyScalar(Math.cos(phi)).addScaledVector(V2, Math.sin(phi)).normalize();
      var th0 = (depth === 2 ? 0.92 : 1.05) - aT * 0.30 + (rnd(aT * 31.7 + phi) - 0.5) * 0.16;
      var dir = rad.clone().multiplyScalar(Math.sin(th0)).addScaledVector(DIR, Math.cos(th0)).normalize();
      var p0 = base.clone().addScaledVector(rad, rHost * 0.92);
      var droop = bl * (0.30 + 0.26 * (1 - heat));
      var cp = [p0,
        p0.clone().addScaledVector(dir, bl * 0.30),
        p0.clone().addScaledVector(dir, bl * 0.62).addScaledVector(DIR, -droop * 0.14),
        p0.clone().addScaledVector(dir, bl * 0.86).addScaledVector(DIR, -droop * 0.48),
        p0.clone().addScaledVector(dir, bl * 1.00).addScaledVector(DIR, -droop)];
      var pts = cat(cp, depth === 2 ? 14 : 18);
      var r0 = (depth === 2 ? 0.0052 : 0.0082) + heat * (depth === 2 ? 0.0032 : 0.0062);
      var g0 = G_BR0 + (G_BR1 - G_BR0) * num(rank[th.id], 0.5) + (depth === 2 ? G_BR_D * 0.8 : 0);
      return { th: th, pts: pts, r0: r0, U: rad, V: new T.Vector3().crossVectors(dir, rad).normalize(),
        dir: dir, bl: bl, aT: aT, phi: phi, depth: depth, g0: g0, g1: g0 + G_BR_D, idx: num(thIdx[th.id], -1) };
    }

    for (i = 0; i < order.length; i++) {
      var b = makeBranch(order[i], attachT(order[i], (i + 1) / (order.length + 1)), i * GOLD, 1, 1, null);
      brs.push(b);
    }
    for (i = 0; i < twigs.length; i++) {
      var host = null;
      for (j = 0; j < brs.length; j++) if (brs[j].th.id === twigs[i].parent) { host = brs[j]; break; }
      if (!host) continue;
      var tw = makeBranch(twigs[i], host.aT, host.phi + GOLD, 0.62, 2, host);
      tw.g0 = host.g0 + G_BR_D * 0.75; tw.g1 = tw.g0 + G_BR_D * 0.8;
      brs.push(tw);
    }

    // ---- 星珠：每条线上有谁参与就有谁一颗
    function beadsOf(kind, th, ptAt, gBase) {
      var cast = th.cast || [], evs = th.events || [], q;
      var pos = {}, lead = th.lead || '';
      for (q = 0; q < evs.length; q++) pos[evs[q]] = evs.length > 1 ? q / (evs.length - 1) : 0;
      for (q = 0; q < cast.length; q++) {
        var c = cast[q]; if (!c || !c.name) continue;
        var u = num(pos[c.entry], q / Math.max(1, cast.length));
        var o = ptAt(clamp(u, 0, 1), q);
        if (!o) continue;
        var w = clamp(num(c.w, 0.4), 0, 1);
        var wPow = Math.pow(w, 0.6);
        var bSize = 3.2 + wPow * 12.8 + (c.name === lead ? 3.4 : 0);
        beadList.push({ p: o.p, n: o.n, r: o.r, size: bSize,
          col: campColor(c.camp, c.name), lead: c.name === lead ? 1 : 0,
          name: c.name, th: th.id, thIdx: num(thIdx[th.id], -1), ch: num(chars[c.name], -1),
          evIdx: num(c.entry, -1), g: gBase + (G_BEAD1 - G_BEAD0) * 0.32 * (q / Math.max(1, cast.length)) });
      }
    }
    for (i = 0; i < segT.length; i++) {
      var sg = segT[i], thm = thById[sg.id];
      if (!thm) continue;
      (function (sg2, ii) {
        beadsOf('main', thm, function (u, q) {
          var t = sg2.t0 + (sg2.t1 - sg2.t0) * u, p = trunkAt(t), r = trunkR(t);
          var a = (ii * 2.1 + q * GOLD);
          var nrm = UU.clone().multiplyScalar(Math.cos(a)).addScaledVector(VV, Math.sin(a)).normalize();
          return { p: p.clone().addScaledVector(nrm, r * 0.86), n: nrm, r: r };
        }, G_BEAD0 + (G_BEAD1 - G_BEAD0) * 0.30 * (ii / Math.max(1, segT.length)));
      })(sg, i);
    }
    for (i = 0; i < brs.length; i++) {
      (function (bb) {
        beadsOf('branch', bb.th, function (u, q) {
          var k2 = clamp(Math.round(u * (bb.pts.length - 1)), 0, bb.pts.length - 1);
          var a = q * GOLD + bb.phi;
          var nrm = bb.U.clone().multiplyScalar(Math.cos(a)).addScaledVector(bb.V, Math.sin(a)).normalize();
          var r = bb.r0 * (1 - 0.62 * u);
          return { p: bb.pts[k2].clone().addScaledVector(nrm, r * 0.9), n: nrm, r: r };
        }, G_BEAD0 + (G_BEAD1 - G_BEAD0) * 0.34 * num(rank[bb.th.id], 0.5));
      })(brs[i]);
    }

    // ---- 收束亮结 / 悬置渐隐丝
    var lastSeg = segT[segT.length - 1], lastTh = thById[lastSeg.id];
    if (lastTh && lastTh.resolved) markList.push({ p: trunkAt(1), size: 20, col: lastSeg.col.getHex(), kind: 0, g: G_TRUNK + 0.02, th: lastSeg.id });
    var frays = [];
    for (i = 0; i < brs.length; i++) {
      var bb2 = brs[i], tip = bb2.pts[bb2.pts.length - 1], col = num(bb2.th.color, 0xffb45c);
      if (bb2.th.suspended) {
        var nf = 3 + Math.floor(rnd(i * 7.31) * 3);
        for (j = 0; j < nf; j++) {
          var a2 = j / nf * Math.PI * 2 + rnd(i * 3.1 + j) * 0.7;
          var sp = bb2.dir.clone().multiplyScalar(0.55).addScaledVector(bb2.U, Math.cos(a2) * 0.62).addScaledVector(bb2.V, Math.sin(a2) * 0.62)
            .addScaledVector(DIR, -0.42).normalize();
          var fl = bb2.bl * (0.20 + rnd(i * 5.7 + j) * 0.16);
          frays.push({ pts: cat([tip.clone(),
            tip.clone().addScaledVector(sp, fl * 0.45).addScaledVector(DIR, -fl * 0.06),
            tip.clone().addScaledVector(sp, fl * 0.80).addScaledVector(DIR, -fl * 0.22),
            tip.clone().addScaledVector(sp, fl).addScaledVector(DIR, -fl * 0.44)], 10),
            r: bb2.r0 * 0.42, col: col, g0: bb2.g1, g1: bb2.g1 + 0.05, th: num(thIdx[bb2.th.id], -1) });
        }
      } else if (bb2.th.resolved) {
        markList.push({ p: tip, size: 11 + num(bb2.th.len, 1) * 0.5, col: col, kind: 0, g: bb2.g1 + 0.01, th: bb2.th.id });
      }
    }

    // ---- 接续环（换手）：一圈亮环 + 三道接骨纹 + 一个换手标
    var hos = tr.handoffs || [];
    for (i = 1; i < segT.length; i++) {
      var t = segT[i].t0, ctr = trunkAt(t), rr = trunkR(t);
      var ho = null;
      for (j = 0; j < hos.length; j++) if (Math.abs(num(hos[j].t, -9) - t) < 0.06 || (segT[i].id && hos[j].to === segT[i].id)) { ho = hos[j]; break; }
      graftList.push({ t: t, p: ctr, r: rr, cPrev: segT[i - 1].col, cNew: segT[i].col,
        kind: (ho && ho.kind) || '接棒', shared: (ho && ho.shared) || [], reason: (ho && ho.reason) || '',
        at: num(ho && ho.at, -1), from: (ho && ho.from) || segT[i - 1].id, to: (ho && ho.to) || segT[i].id,
        g: gOfT(t) + 0.012, th: num(thIdx[segT[i].id], -1) });
    }

    // ---- 交汇：两线之间一根细横丝 + 一个小十字
    function ptOfThread(id, evIdx) {
      var q, s;
      for (q = 0; q < segT.length; q++) if (segT[q].id === id) {
        var th2 = thById[id], evs = th2 && th2.events || [], u = 0;
        for (s = 0; s < evs.length; s++) if (evs[s] === evIdx) { u = evs.length > 1 ? s / (evs.length - 1) : 0; break; }
        var tt = segT[q].t0 + (segT[q].t1 - segT[q].t0) * u;
        return trunkAt(tt);
      }
      for (q = 0; q < brs.length; q++) if (brs[q].th.id === id) {
        var evs2 = brs[q].th.events || [], u2 = 0;
        for (s = 0; s < evs2.length; s++) if (evs2[s] === evIdx) { u2 = evs2.length > 1 ? s / (evs2.length - 1) : 0; break; }
        return brs[q].pts[clamp(Math.round(u2 * (brs[q].pts.length - 1)), 0, brs[q].pts.length - 1)].clone();
      }
      return null;
    }
    var jns = tr.junctions || [];
    for (i = 0; i < jns.length && i < 24; i++) {
      var jn = jns[i], ids = jn.threads || [];
      if (ids.length < 2) continue;
      var pa = ptOfThread(ids[0], jn.at), pb = ptOfThread(ids[1], jn.at);
      if (!pa || !pb) continue;
      var mid = pa.clone().add(pb).multiplyScalar(0.5).addScaledVector(DIR, pa.distanceTo(pb) * 0.10);
      juncList.push({ pts: cat([pa, mid, pb], 14), r: 0.0026, col: 0xc9b8ff, g: 0.88, th: -1,
        cross: mid, at: num(jn.at, -1), ids: ids });
      markList.push({ p: mid, size: 13, col: 0xc9b8ff, kind: 1, g: 0.90, th: ids[0] });
    }

    // ---- 标签锚点：主干各段 + 最长的 6 条支线 + 换手标 + 余线计数
    for (i = 0; i < segT.length; i++) {
      var mt = (segT[i].t0 + segT[i].t1) * 0.5, thl = thById[segT[i].id] || {};
      labList.push({ kind: 'seg', p: trunkAt(mt).addScaledVector(UU, trunkR(mt) * 3.2),
        name: thl.title || ('主干 ' + (i + 1)), sub: (thl.en || '') + (thl.lead ? (thl.en ? ' · ' : '') + thl.lead : ''),
        col: '#' + segT[i].col.getHexString(), id: segT[i].id, pri: 0, g: gOfT(mt) + 0.02 });
    }
    for (i = 0; i < graftList.length; i++) {
      labList.push({ kind: 'graft', p: graftList[i].p.clone().addScaledVector(VV, graftList[i].r * -3.4),
        name: graftList[i].kind, sub: graftList[i].shared.slice(0, 2).join(' ') || graftList[i].reason.slice(0, 12),
        col: '#' + graftList[i].cNew.getHexString(), id: graftList[i].to, pri: 1, g: graftList[i].g + 0.02 });
    }
    var byLen = brs.filter(function (b2) { return b2.depth === 1; }).slice().sort(function (a3, b3) { return num(b3.th.len, 0) - num(a3.th.len, 0); }).slice(0, 6);
    for (i = 0; i < byLen.length; i++) {
      var bt = byLen[i];
      labList.push({ kind: 'branch', p: bt.pts[bt.pts.length - 1].clone().addScaledVector(bt.dir, bt.bl * 0.06),
        name: bt.th.title || ('支线 ' + (i + 1)), sub: (bt.th.lead || '') + (bt.th.len ? ' · ' + bt.th.len : ''),
        col: '#' + new T.Color(num(bt.th.color, 0xffb45c)).getHexString(), id: bt.th.id, pri: 2, g: bt.g1 + 0.02 });
    }
    var rem = null;
    if (lodCut > 0) {
      rem = { t: 0.90, p: trunkAt(0.90), r: trunkR(0.90) * 3.4, g: gOfT(0.90) };
      labList.push({ kind: 'rem', p: rem.p.clone().addScaledVector(UU, rem.r * 1.1), name: '余线 ' + lodCut,
        sub: 'LOD · 按长度截断', col: '#9a92b8', id: '', pri: 1, g: rem.g + 0.04 });
    }

    return { DIR: DIR, U: UU, V: VV, tp: tp, trunkAt: trunkAt, trunkR: trunkR, colAt: colAt, gapAt: gapAt,
      segAt: segAt, gOfT: gOfT,
      segT: segT, brs: brs, frays: frays, beads: beadList, marks: markList, grafts: graftList, juncs: juncList,
      labs: labList, rem: rem, thIdx: thIdx, chars: chars, evPos: evPos, R0: R0 };
  }

  var SKEL_VS = [
    'attribute vec3 aP; attribute vec3 aM; attribute float aTh;',
    'uniform float uGrow; uniform float uFocus; uniform float uFat;',
    'varying float vT; varying float vG; varying float vRole; varying float vFlow; varying float vGap;',
    'varying float vRev; varying float vFoc; varying vec3 vC; varying vec3 vN; varying vec3 vW;',
    'void main(){',
    '  vT = aP.x; vG = aP.z; vRole = aM.x; vFlow = aM.y; vGap = aM.z; vC = color;',
    '  float rev = smoothstep(aP.z, aP.z + 0.045, uGrow);',
    '  vRev = rev;',
    '  vFoc = 1.0 - step(0.5, abs(aTh - uFocus)) * step(-0.5, uFocus);',
    '  vec3 axis = position - normal * aP.y;',
    '  vec3 p = axis + normal * aP.y * uFat * mix(0.10, 1.0, rev);',
    '  vec4 wp = modelMatrix * vec4(p, 1.0);',
    '  vW = wp.xyz; vN = normalize(mat3(modelMatrix) * normal);',
    '  gl_Position = projectionMatrix * viewMatrix * wp; }'
  ].join('\n');

  var SKEL_FS = [
    'uniform float uTime; uniform float uOn; uniform float uBeat; uniform float uGrow; uniform float uDim; uniform float uRep;',
    'varying float vT; varying float vG; varying float vRole; varying float vFlow; varying float vGap;',
    'varying float vRev; varying float vFoc; varying vec3 vC; varying vec3 vN; varying vec3 vW;',
    'void main(){',
    '  if (vRev < 0.004) discard;',
    '  float fres = 1.0 - abs(dot(normalize(vN), normalize(cameraPosition - vW)));',
    '  float body = 0.26 + 0.74 * pow(fres, 1.8);',
    '  float flow = pow(0.5 + 0.5 * sin(vT * uRep * vFlow - uTime * 1.10), 3.0);',
    '  float node = pow(0.5 + 0.5 * sin(vT * 42.0 * vFlow - uTime * 0.42), 7.0) * 0.55;',
    '  float front = exp(-pow((uGrow - vG) * 30.0, 2.0));',
    '  float isG = step(2.5, vRole) * (1.0 - step(4.5, vRole));',
    '  float isF = step(4.5, vRole) * (1.0 - step(5.5, vRole));',
    '  float a = (body * 0.40 + flow * 0.46 + node + front * 1.25) * vRev * uOn * (0.86 + 0.28 * uBeat);',
    '  a *= mix(1.0, 2.35, isG);',
    '  a *= mix(1.0, pow(1.0 - vT, 1.5) * 0.46, isF);',
    '  a *= mix(1.0, 0.34, vGap);',
    '  a *= mix(uDim, 1.0, vFoc);',
    '  vec3 c = mix(vC, vec3(1.0, 0.95, 0.86), clamp(flow * 0.55 + front * 0.9, 0.0, 1.0));',
    '  c = mix(c, vec3(0.30, 0.26, 0.40), vGap * 0.80);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  var SHEATH_FS = [
    'uniform float uOn; uniform float uTime; uniform float uDim;',
    'varying float vT; varying float vG; varying float vRole; varying float vFlow; varying float vGap;',
    'varying float vRev; varying float vFoc; varying vec3 vC; varying vec3 vN; varying vec3 vW;',
    'void main(){',
    '  if (vRev < 0.004) discard;',
    '  float face = abs(dot(normalize(vN), normalize(cameraPosition - vW)));',
    '  float a = pow(face, 2.6) * 0.14 * vRev * uOn * mix(uDim, 1.0, vFoc);',
    '  a *= mix(1.0, 0.35, vGap);',
    '  float br = 0.72 + 0.28 * sin(vT * 6.0 - uTime * 0.55);',
    '  vec3 c = mix(vC, vec3(0.52, 0.44, 0.86), 0.55);',
    '  gl_FragColor = vec4(c * a * br, a * br); }'
  ].join('\n');

  var BEAD_VS = [
    'attribute float aSize; attribute vec3 aCol; attribute vec3 aK; attribute float aTh; attribute float aCh;',
    'uniform float uTime; uniform float uGrow; uniform float uScale; uniform float uFocus; uniform float uChar; uniform float uDim;',
    'varying vec3 vC; varying float vA; varying float vLead;',
    'void main(){',
    '  float rev = smoothstep(aK.x, aK.x + 0.055, uGrow);',
    '  float pop = 1.0 + exp(-pow((uGrow - aK.x) * 22.0, 2.0)) * 0.85;',
    '  float br = 0.80 + 0.44 * pow(0.5 + 0.5 * sin(uTime * 0.85 + aK.y * 6.2831), 2.0);',
    '  float fo = 1.0 - step(0.5, abs(aTh - uFocus)) * step(-0.5, uFocus);',
    '  float fc = 1.0 - step(0.5, abs(aCh - uChar)) * step(-0.5, uChar);',
    '  vA = rev * mix(uDim, 1.0, fo) * mix(uDim * 0.8, 1.0, fc);',
    '  vC = aCol; vLead = aK.z;',
    '  vec4 mv = modelViewMatrix * vec4(position, 1.0);',
    '  gl_PointSize = clamp(aSize * br * pop * (0.35 + 0.65 * rev) * (1.0 + fc * 0.28) * uScale / max(1.0, -mv.z), 0.0, 44.0);',
    '  gl_Position = projectionMatrix * mv; }'
  ].join('\n');
  var BEAD_FS = [
    'uniform float uOn; uniform float uTime; varying vec3 vC; varying float vA; varying float vLead;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = dot(p, p);',
    '  if (r > 1.0) discard;',
    '  // T2 · 人物星珠史诗化：高斯光核 + 细密光晕补偿 + 日冕微晕',
    '  float core = exp(-r * 5.2) + exp(-r * 26.0) * 0.95;',
    '  float halo = exp(-r * 1.8) * 0.35;',
    '  float corona = vLead > 0.5 ? (exp(-r * 0.9) * 0.25 * (0.8 + 0.2 * sin(uTime * 2.0 + atan(p.y, p.x) * 6.0))) : 0.0;',
    '  float a = (core + halo + corona) * vA * uOn * (0.88 + 0.35 * vLead);',
    '  vec3 col = mix(vC, vec3(1.0, 0.96, 0.90), core * 0.55 + corona * 0.3);',
    '  gl_FragColor = vec4(col * a, a); }'
  ].join('\n');

  var RING_FS = [
    'uniform float uOn; varying vec3 vC; varying float vA; varying float vLead;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p);',
    '  float ring = exp(-pow((r - 0.74) * 9.0, 2.0));',
    '  float a = ring * vA * uOn * 0.72;',
    '  if (a < 0.002) discard;',
    '  gl_FragColor = vec4(vC * a, a); }'
  ].join('\n');

  var MARK_FS = [
    'uniform float uOn; uniform float uTime; varying vec3 vC; varying float vA; varying float vLead;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p);',
    '  float knot = (exp(-r * r * 9.0) * 1.25 + exp(-r * r * 60.0) * 1.1',
    '    + pow(max(0.0, cos(atan(p.y, p.x) * 4.0)), 26.0) * exp(-r * 2.2) * 0.85) * (1.0 - step(0.5, vLead));',
    '  float cross = (smoothstep(0.10, 0.0, abs(p.x)) + smoothstep(0.10, 0.0, abs(p.y)))',
    '    * smoothstep(0.95, 0.30, r) * step(0.5, vLead) * 0.85;',
    '  float a = (knot + cross) * vA * uOn;',
    '  if (a < 0.002) discard;',
    '  gl_FragColor = vec4(mix(vC, vec3(1.0, 0.97, 0.9), knot * 0.5) * a, a); }'
  ].join('\n');

  function skelMat(fs, fat, rep) {
    return new T.ShaderMaterial({ vertexShader: SKEL_VS, fragmentShader: fs, transparent: true, vertexColors: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 }, uGrow: { value: 0 },
        uDim: { value: 1 }, uFocus: { value: -1 }, uFat: { value: fat }, uRep: { value: rep } } });
  }
  function ptsMat(fs) {
    return new T.ShaderMaterial({ vertexShader: BEAD_VS, fragmentShader: fs, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uScale: { value: 600 },
        uFocus: { value: -1 }, uChar: { value: -1 }, uDim: { value: 1 } } });
  }

  function buildEye() {
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(new Float32Array(3), 3));
    var m = new T.PointsMaterial({ size: 0, transparent: true, opacity: 0, depthWrite: false, depthTest: false });
    var p = new T.Points(g, m);
    p.frustumCulled = false; p.renderOrder = -99;
    p.onBeforeRender = function (r, s, cam) { CAM = cam; };
    return p;
  }

  function buildMeshes() {
    var A = acc(), i, j, b;
    tube(A, L.tp, function (t) { return L.trunkR(t); }, 12,
      { role: ROLE.TRUNK, flow: 1, g0: 0, g1: G_TRUNK, gap: L.gapAt,
        gFn: function (t) { return G_TRUNK * Math.pow(t, 0.82); },
        thFn: function (t) { return num(L.thIdx[L.segAt(t).id], -1); },
        col: function (t) { return L.colAt(t); } });
    for (i = 0; i < L.brs.length; i++) {
      b = L.brs[i];
      (function (bb) {
        tube(A, bb.pts, function (t) { return bb.r0 * (1 - 0.62 * t); }, bb.depth === 2 ? 5 : 7,
          { role: bb.depth === 2 ? ROLE.TWIG : ROLE.BRANCH, flow: bb.depth === 2 ? 0.55 : 0.72,
            g0: bb.g0, g1: bb.g1, th: bb.idx, color: num(bb.th.color, 0xffb45c) });
      })(b);
    }
    for (i = 0; i < L.frays.length; i++) {
      (function (fr) {
        tube(A, fr.pts, function (t) { return fr.r * (1 - 0.85 * t); }, 4,
          { role: ROLE.FRAY, flow: 0.5, g0: fr.g0, g1: fr.g1, th: fr.th, color: fr.col });
      })(L.frays[i]);
    }
    var geo = toGeo(A);
    if (!geo) return;
    skel = new T.Mesh(geo, skelMat(SKEL_FS, 1, 13));
    skel.frustumCulled = false; skel.renderOrder = -5;
    root.add(skel);
    sheath = new T.Mesh(geo, skelMat(SHEATH_FS, 3.4, 13));
    sheath.frustumCulled = false; sheath.renderOrder = -7;
    root.add(sheath);

    var G = acc();
    for (i = 0; i < L.grafts.length; i++) {
      var gf = L.grafts[i];
      ring(G, gf.p, L.U, L.V, gf.r * 2.35, gf.r * 0.34,
        { role: ROLE.RING, flow: 1, g0: gf.g, g1: gf.g + 0.02, th: gf.th, color: gf.cNew.getHex() }, 44);
      for (j = 0; j < 3; j++) {
        var a = j * Math.PI * 2 / 3 + i * 0.6;
        var nrm = L.U.clone().multiplyScalar(Math.cos(a)).addScaledVector(L.V, Math.sin(a)).normalize();
        var t0 = Math.max(0, gf.t - 0.032), t1 = Math.min(1, gf.t + 0.032), pts = [], q;
        for (q = 0; q <= 6; q++) {
          var tt = t0 + (t1 - t0) * q / 6;
          pts.push(L.trunkAt(tt).addScaledVector(nrm, L.trunkR(tt) * 1.55));
        }
        (function (gg) {
          tube(G, pts, function (t) { return gg.r * 0.26 * (1 - Math.abs(t - 0.5) * 0.5); }, 5,
            { role: ROLE.RIB, flow: 1.6, g0: gg.g + 0.006, g1: gg.g + 0.024, th: gg.th,
              col: function (t) { return new T.Color().copy(gg.cPrev).lerp(gg.cNew, clamp((t - 0.18) / 0.64, 0, 1)); } });
        })(gf);
      }
    }
    if (L.rem) ring(G, L.rem.p, L.U, L.V, L.rem.r, L.rem.r * 0.055,
      { role: ROLE.RING, flow: 0.5, g0: L.rem.g, g1: L.rem.g + 0.03, th: -1, color: 0x9a92b8 }, 52);
    var gg2 = toGeo(G);
    if (gg2) {
      graft = new T.Mesh(gg2, skelMat(SKEL_FS, 1, 9));
      graft.frustumCulled = false; graft.renderOrder = -4;
      root.add(graft);
    }

    var J = acc();
    for (i = 0; i < L.juncs.length; i++) {
      (function (jj) {
        tube(J, jj.pts, function (t) { return jj.r * (0.6 + 0.4 * Math.sin(t * Math.PI)); }, 4,
          { role: ROLE.JUNC, flow: 0.4, g0: jj.g, g1: jj.g + 0.03, th: -1, color: jj.col });
      })(L.juncs[i]);
    }
    var jg = toGeo(J);
    if (jg) {
      junc = new T.Mesh(jg, skelMat(SKEL_FS, 1, 7));
      junc.frustumCulled = false; junc.renderOrder = -4;
      root.add(junc);
    }

    beads = ptsFrom(L.beads, function (o) { return [o.size, o.col, o.g, rnd(o.thIdx * 3.1 + o.ch * 1.7), o.lead, o.thIdx, o.ch]; }, BEAD_FS);
    var leads = L.beads.filter(function (o) { return o.lead; });
    leadRings = ptsFrom(leads, function (o) { return [o.size * 2.15, o.col, o.g + 0.01, rnd(o.thIdx * 5.3), 1, o.thIdx, o.ch]; }, RING_FS);
    marks = ptsFrom(L.marks, function (o) { return [o.size, o.col, o.g, rnd(o.size * 2.7), o.kind, num(L.thIdx[o.th], -1), -1]; }, MARK_FS);
  }

  function ptsFrom(list, map, fs) {
    if (!list || !list.length) return null;
    var n = list.length, pos = new Float32Array(n * 3), sz = new Float32Array(n), cl = new Float32Array(n * 3);
    var kk = new Float32Array(n * 3), th = new Float32Array(n), ch = new Float32Array(n), c = new T.Color(), i;
    for (i = 0; i < n; i++) {
      var o = list[i], m = map(o);
      pos[i * 3] = o.p.x; pos[i * 3 + 1] = o.p.y; pos[i * 3 + 2] = o.p.z;
      sz[i] = m[0]; c.set(m[1]);
      cl[i * 3] = c.r; cl[i * 3 + 1] = c.g; cl[i * 3 + 2] = c.b;
      kk[i * 3] = m[2]; kk[i * 3 + 1] = m[3]; kk[i * 3 + 2] = m[4];
      th[i] = m[5]; ch[i] = m[6];
    }
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3));
    g.setAttribute('aSize', new T.BufferAttribute(sz, 1));
    g.setAttribute('aCol', new T.BufferAttribute(cl, 3));
    g.setAttribute('aK', new T.BufferAttribute(kk, 3));
    g.setAttribute('aTh', new T.BufferAttribute(th, 1));
    g.setAttribute('aCh', new T.BufferAttribute(ch, 1));
    var p = new T.Points(g, ptsMat(fs));
    p.frustumCulled = false; p.renderOrder = -3;
    root.add(p);
    return p;
  }

  function fitScale() {
    var rimR = Math.max(80, num(O.rimR, 0) || Math.max(220, num(O.lay && O.lay.halfW, 220)));
    var lo = rimR * 0.55, hi = Math.max(360, rimR * 3.4), mid = (lo + hi) * 0.5, i;
    if (!CAM) return clamp(rimR * 1.35, lo, hi);
    for (i = 0; i < 22; i++) {
      mid = (lo + hi) * 0.5;
      root.scale.setScalar(mid);
      root.updateMatrixWorld(true);
      _v.copy(L.trunkAt(1)).applyMatrix4(root.matrixWorld).project(CAM);
      if (!isFinite(_v.y)) break;
      if (_v.y > TIP_NDC) hi = mid; else lo = mid;
    }
    return clamp(mid, rimR * 0.5, Math.max(400, rimR * 3.6));
  }

  function css() {
    if (document.getElementById('clPlotTreeCss')) return;
    var s = document.createElement('style');
    s.id = 'clPlotTreeCss';
    s.textContent =
      '#clPlotLab{position:fixed;inset:0;pointer-events:none;z-index:12;overflow:hidden;contain:strict}' +
      '.cl-plab{position:absolute;left:0;top:0;transform:translate(-999px,-999px);white-space:nowrap;' +
      'display:flex;flex-direction:column;gap:1px;padding-left:13px;margin-top:-8px;opacity:0;' +
      'transition:opacity .34s cubic-bezier(.16,1,.3,1);text-shadow:0 0 8px rgba(6,2,16,.92),0 0 2px #000}' +
      '.cl-plab.on{opacity:1}' +
      '.cl-plab::before{content:"";position:absolute;left:0;top:6px;width:10px;height:1px;opacity:.75;' +
      'background:linear-gradient(90deg,currentColor,transparent)}' +
      '.cl-plab::after{content:"";position:absolute;left:-2px;top:4px;width:4px;height:4px;border-radius:50%;' +
      'background:currentColor;box-shadow:0 0 7px currentColor}' +
      '.cl-plab b{font-size:13px;font-weight:600;letter-spacing:.05em;color:#efe6ff;' +
      'padding:1px 7px 1px 3px;margin-left:-3px;border-radius:2px;' +
      'background:linear-gradient(90deg,rgba(8,6,16,.66),rgba(8,6,16,.30) 62%,rgba(8,6,16,0))}' +
      '.cl-plab s{font-size:11px;text-decoration:none;font-family:var(--mono,ui-monospace,monospace);' +
      'letter-spacing:.10em;color:rgba(201,184,255,.72);text-transform:uppercase}' +
      '.cl-plab.lf{padding-left:0;padding-right:13px;align-items:flex-end}' +
      '.cl-plab.lf::before{left:auto;right:0;background:linear-gradient(270deg,currentColor,transparent)}' +
      '.cl-plab.lf::after{left:auto;right:-2px}' +
      '.cl-plab.lf b{margin-left:0;margin-right:-3px;padding:1px 3px 1px 7px;' +
      'background:linear-gradient(270deg,rgba(8,6,16,.66),rgba(8,6,16,.30) 62%,rgba(8,6,16,0))}' +
      '.cl-plab.k-graft b{font-size:11px;font-family:var(--mono,ui-monospace,monospace);letter-spacing:.16em;' +
      'color:#fff1da;border:1px solid rgba(255,214,150,.34);padding:0 5px}' +
      '.cl-plab.k-branch b{font-size:12px;font-weight:500;color:#e2d8f5}' +
      '.cl-plab.k-rem b{font-size:11px;font-family:var(--mono,ui-monospace,monospace);letter-spacing:.04em;color:#9a92b8}' +
      '@media (prefers-reduced-motion:reduce){.cl-plab{transition:none}}';
    document.head.appendChild(s);
  }

  function buildLabs() {
    css();
    if (!labLayer) {
      labLayer = document.createElement('div');
      labLayer.id = 'clPlotLab';
      labLayer.setAttribute('aria-hidden', 'true');
      document.body.appendChild(labLayer);
    }
    labLayer.innerHTML = '';
    labs = [];
    for (var i = 0; i < L.labs.length; i++) {
      var d = L.labs[i], e = document.createElement('div');
      e.className = 'cl-plab k-' + d.kind;
      e.style.color = d.col;
      e.innerHTML = '<b></b><s></s>';
      e.children[0].textContent = d.name || '';
      e.children[1].textContent = d.sub || '';
      labLayer.appendChild(e);
      labs.push({ el: e, d: d, w: 0, h: 0, on: false });
    }
  }

  var hudBoxes = [], hudAt = -1;
  function hudRects() {
    var now = Date.now();
    if (now - hudAt < 2000) return hudBoxes;
    hudAt = now; hudBoxes = [];
    try {
      Array.prototype.forEach.call(document.querySelectorAll(HUD_SEL), function (e) {
        var r = e.getBoundingClientRect();
        if (r.width > 4 && r.height > 4) hudBoxes.push(r);
      });
    } catch (e2) {}
    return hudBoxes;
  }

  function placeLabs(k) {
    var W = window.innerWidth, H = window.innerHeight, i, taken = hudRects().slice(), shown = 0;
    var only = deg >= 1 || O.big;
    var list = labs.slice().sort(function (a, b) { return a.d.pri - b.d.pri; });
    for (i = 0; i < list.length; i++) {
      var it = list[i], e = it.el;
      var ok = k > 0.05 && grow >= it.d.g && !(only && it.d.kind === 'branch');
      if (ok) {
        _v.copy(it.d.p).applyMatrix4(root.matrixWorld);
        if (CAM) _v.project(CAM); else ok = false;
        if (ok && (_v.z > 1 || !isFinite(_v.x))) ok = false;
      }
      if (ok) {
        if (!it.w) { var r0 = e.getBoundingClientRect(); it.w = Math.max(40, r0.width); it.h = Math.max(14, r0.height); }
        var x = (_v.x * 0.5 + 0.5) * W, y = (-_v.y * 0.5 + 0.5) * H;
        var flip = x > W * 0.62;
        var bx = flip ? x - it.w - 13 : x, by = y - it.h * 0.5;
        var box = { left: bx - 3, right: bx + it.w + 3, top: by - 2, bottom: by + it.h + 2 };
        for (var j = 0; j < taken.length; j++) {
          var t = taken[j];
          if (box.left < t.right && box.right > t.left && box.top < t.bottom && box.bottom > t.top) { ok = false; break; }
        }
        if (ok) {
          taken.push(box);
          e.classList.toggle('lf', flip);
          e.style.transform = 'translate(' + (flip ? x - 13 - it.w : x).toFixed(1) + 'px,' + by.toFixed(1) + 'px)';
          e.style.opacity = (clamp((grow - it.d.g) / 0.10, 0, 1) * k).toFixed(3);
          if (!it.on) { e.classList.add('on'); it.on = true; }
          shown++;
          continue;
        }
      }
      if (it.on) { e.classList.remove('on'); it.on = false; }
      e.style.opacity = '0';
    }
    labShown = shown;
  }

  function setGrow(g) {
    grow = clamp(g, 0, 1);
    var u;
    if (skel) { skel.material.uniforms.uGrow.value = grow; sheath.material.uniforms.uGrow.value = grow; }
    if (graft) graft.material.uniforms.uGrow.value = grow;
    if (junc) junc.material.uniforms.uGrow.value = grow;
    [beads, leadRings, marks].forEach(function (p) { if (p) p.material.uniforms.uGrow.value = grow; });
    if (u) u = null;
  }

  var API = {
    name: 'plot-tree',

    build: function (o) {
      if (!o || !o.T || !o.group) return null;
      T = o.T; O = o;
      _v = new T.Vector3(); _v2 = new T.Vector3(); _m = new T.Matrix4();
      API.dispose();
      try { synthMode = new URLSearchParams(location.search).get('plotsynth') === '1'; } catch (e) { synthMode = false; }
      if (synthMode) {
        if (window.console) console.warn('[plot-tree] plotsynth=1：当前显示的是**合成树**，不是这部作品的剧情线');
        API.setTree(API.__synth());
        API.show(true);
      } else if (tree && tree.ok) {
        API.setTree(tree);
      }
      return API.stats();
    },

    setTree: function (t) {
      if (!t || !t.ok) {
        if (synthMode) return API.stats();
        tree = t || null; strict = strictTree(t); clearGeom(); vis = false; grow = target = 0;
        return API.stats();
      }
      tree = t;
      if (strictTree(t)) {
        strict = true;
        clearGeom(); vis = false; grow = target = 0;
        return API.stats();
      }
      strict = false;
      if (!T || !O || !O.group) return API.stats();
      clearGeom();
      root = new T.Group();
      root.frustumCulled = false;
      O.group.add(root); tops.push(root);
      try {
        L = layout(tree);
        buildMeshes();
        buildLabs();
      } catch (e) {
        if (window.console) console.warn('[plot-tree] layout', e);
        clearGeom(); return API.stats();
      }
      root.scale.setScalar(fitScale());
      ready = true;
      setGrow(grow);
      return API.stats();
    },

    show: function (v) {
      v = v !== false;
      if (strictNow()) {
        vis = v;
        var G = window.CLTreeGate;
        if (G && G.setState) tryFn(function () { G.setState(v ? 'plot' : 'stars'); });
        return vis;
      }
      if (!ready) { vis = v; return vis; }
      vis = v;
      target = v ? 1 : 0;
      if (CALM || deg >= 2) setGrow(target);
      else if (v && grow >= 1) setGrow(0);
      return vis;
    },
    visible: function () {
      if (strictNow()) {
        var G = window.CLTreeGate;
        if (G && G.state) {
          var s = tryFn(G.state);
          if (s === 'plot') return true;
          if (s === 'stars') return false;
        }
      }
      return vis;
    },

    focusThread: function (id) {
      if (strictNow()) {
        var e = firstEventOfThread(id);
        focusTh = -1;
        var E = window.CLTreeEvents;
        if (e >= 0) { if (E && E.pick) tryFn(function () { E.pick(e); }); return e; }
        if (E && E.clear) tryFn(function () { E.clear(); });
        return -1;
      }
      focusTh = (id == null || !L || L.thIdx[id] == null) ? -1 : L.thIdx[id];
      return focusTh;
    },
    focusChar: function (name) {
      focusCh = (name == null || !L || L.chars[name] == null) ? -1 : L.chars[name];
      return focusCh;
    },

    pick: function (nx, ny) {
      if (!ready || !CAM || !root || grow < 0.05) return null;
      var W = window.innerWidth, H = window.innerHeight;
      var px = (num(nx, 0) * 0.5 + 0.5) * W, py = (-num(ny, 0) * 0.5 + 0.5) * H, i;
      var best = null, bd = 1e9;
      function test(p, rad, hit) {
        _v.copy(p).applyMatrix4(root.matrixWorld).project(CAM);
        if (_v.z > 1 || !isFinite(_v.x)) return;
        var x = (_v.x * 0.5 + 0.5) * W, y = (-_v.y * 0.5 + 0.5) * H;
        var d = Math.sqrt((x - px) * (x - px) + (y - py) * (y - py));
        if (d < rad && d < bd) { bd = d; best = hit; }
      }
      for (i = 0; i < L.beads.length; i++) {
        var b = L.beads[i];
        if (grow < b.g) continue;
        test(b.p, 8 + b.size * 0.8, { kind: 'bead', id: b.th, name: b.name, evIdx: b.evIdx });
      }
      if (!best) for (i = 0; i < L.grafts.length; i++) {
        var g = L.grafts[i];
        if (grow < g.g) continue;
        test(g.p, 20, { kind: 'handoff', id: g.to, name: g.kind, evIdx: g.at });
      }
      if (!best) {
        for (i = 0; i < L.segT.length; i++) {
          var s = L.segT[i];
          for (var q = 0; q <= 6; q++) test(L.trunkAt(s.t0 + (s.t1 - s.t0) * q / 6), 13, { kind: 'thread', id: s.id, name: '', evIdx: -1 });
        }
        for (i = 0; i < L.brs.length; i++) {
          var br = L.brs[i];
          if (grow < br.g0) continue;
          for (var q2 = 0; q2 < br.pts.length; q2 += 3) test(br.pts[q2], 11, { kind: 'thread', id: br.th.id, name: br.th.title || '', evIdx: -1 });
        }
      }
      if (best) {
        try {
          document.dispatchEvent(new CustomEvent(best.kind === 'bead' ? 'cl:plot-bead' : 'cl:plot-thread',
            { detail: best.kind === 'bead' ? { name: best.name, threadId: best.id, evIdx: best.evIdx } : { id: best.id } }));
        } catch (e) {}
      }
      return best;
    },

    update: function (s) {
      if (!ready || !root) return;
      var t = num(s && s.t, 0), dt = lastT < 0 ? 0 : clamp(t - lastT, 0, 0.12);
      lastT = t;
      deg = (s && s.degrade) || 0;
      scale = num(s && s.scale, 600);
      var live = (s && s.on ? 1 : 0) * (muted ? 0 : 1) * (vis ? 1 : 0) * (s && s.calm ? 0.62 : 1);
      on += (live - on) * 0.06;
      var beat = num(s && s.beat, 0.5);

      if (dt > 0 && !(CALM || deg >= 2)) {
        if (target > grow) setGrow(grow + dt / GROW_T);
        else if (target < grow) setGrow(grow - dt / (GROW_T * 0.62));
      } else if (CALM || deg >= 2) setGrow(target);

      var k = on * clamp(grow * 2.4, 0, 1), i;
      if (skel) {
        var u = skel.material.uniforms;
        u.uTime.value = t; u.uBeat.value = beat; u.uOn.value = 0.62 * on;
        u.uDim.value = focusTh >= 0 ? 0.18 : 1;
        u.uFocus.value = focusTh;
        skel.visible = u.uOn.value > 0.002 && grow > 0.001;
        var us = sheath.material.uniforms;
        us.uTime.value = t; us.uOn.value = (deg >= 1 ? 0 : 1) * on;
        us.uDim.value = u.uDim.value; us.uFocus.value = focusTh;
        sheath.visible = us.uOn.value > 0.004 && grow > 0.001;
      }
      if (graft) {
        var ug = graft.material.uniforms;
        ug.uTime.value = t; ug.uBeat.value = beat; ug.uOn.value = 0.70 * on;
        ug.uDim.value = 1; ug.uFocus.value = -1;
        graft.visible = ug.uOn.value > 0.002 && grow > 0.001;
      }
      if (junc) {
        var uj = junc.material.uniforms;
        uj.uTime.value = t; uj.uBeat.value = beat; uj.uOn.value = 0.42 * on * (deg >= 1 ? 0.5 : 1);
        uj.uDim.value = focusTh >= 0 ? 0.3 : 1; uj.uFocus.value = -1;
        junc.visible = uj.uOn.value > 0.002 && grow > 0.5;
      }
      var ps = [[beads, 0.86], [leadRings, deg >= 1 ? 0 : 0.66], [marks, 0.80]];
      for (i = 0; i < ps.length; i++) {
        var p = ps[i][0]; if (!p) continue;
        var up = p.material.uniforms;
        up.uTime.value = t; up.uScale.value = scale; up.uOn.value = ps[i][1] * on;
        up.uFocus.value = focusTh; up.uChar.value = focusCh;
        up.uDim.value = (focusTh >= 0 || focusCh >= 0) ? 0.14 : 1;
        p.visible = up.uOn.value > 0.002 && grow > G_BEAD0 - 0.06;
      }
      if (labLayer) placeLabs(k);
    },

    setOn: function (v) { muted = !v; },

    root: function () { return root; },
    layout: function () { return L; },
    tree: function () { return tree; },
    setPose: function (o) {
      if (!root) return null;
      if (!o) { needFit = true; root.position.set(0, 0, 0); root.rotation.set(0, 0, 0); return API.stats(); }
      if (o.scale) { root.scale.setScalar(o.scale); needFit = false; }
      if (o.pos) root.position.set(num(o.pos.x, 0), num(o.pos.y, 0), num(o.pos.z, 0));
      if (o.rot) root.rotation.set(num(o.rot.x, 0), num(o.rot.y, 0), num(o.rot.z, 0));
      root.updateMatrixWorld(true);
      return API.stats();
    },

    dispose: function () {
      clearGeom();
      if (labLayer && labLayer.parentNode) labLayer.parentNode.removeChild(labLayer);
      labLayer = null; labs = []; labShown = 0;
      ready = false;
    },

    stats: function () {
      var thr = tree && tree.threads ? tree.threads.length : 0;
      var dc = 0, i, objs = [skel, sheath, graft, junc, beads, leadRings, marks];
      for (i = 0; i < objs.length; i++) if (objs[i] && objs[i].visible) dc++;
      return {
        ready: ready, on: +on.toFixed(3), threads: thr,
        beads: L ? L.beads.length : 0,
        segs: L ? L.segT.length : 0,
        handoffs: L ? L.grafts.length : 0,
        twigs: L ? L.brs.filter(function (b) { return b.depth === 2; }).length : 0,
        branches: L ? L.brs.filter(function (b) { return b.depth === 1; }).length : 0,
        frays: L ? L.frays.length : 0,
        knots: L ? L.marks.filter(function (m) { return !m.kind; }).length : 0,
        juncs: L ? L.juncs.length : 0,
        grow: +grow.toFixed(3), visible: vis, labels: labShown, drawcalls: dc,
        lod: deg >= 2 ? 2 : deg >= 1 ? 1 : 0, cut: lodCut,
        scale: root ? +root.scale.x.toFixed(1) : 0, cam: !!CAM, synth: synthMode,
        strict: strict,
        focusThread: focusTh, focusChar: focusCh, calm: CALM, muted: muted
      };
    },

    __synth: function () {
      var NM = ['甲一', '乙二', '丙三', '丁四', '戊五', '己六', '庚七', '辛八', '壬九', '癸十', '子一', '丑二'];
      var CP = ['主角方', '对立', '中立', '摇摆', '盟友'];
      var KD = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
      var SEGN = ['合成 · 起', '合成 · 承', '合成 · 转', '合成 · 合'];
      var chapters = [], events = [], i, j, k;
      for (i = 0; i < 12; i++) chapters.push({ name: '第' + (i + 1) + '章', idx: i, n: 0 });
      function mkEv(chapIdx, kind, tag) {
        var i2 = events.length, cast = [], nc = 2 + Math.floor(rnd(i2 * 1.7) * 3);
        for (var q = 0; q < nc; q++) cast.push(NM[Math.floor(rnd(i2 * 3.1 + q * 2.3) * NM.length)]);
        chapters[chapIdx].n++;
        events.push({ i: i2, order: i2 + 1, chapter: chapters[chapIdx].name, chapIdx: chapIdx,
          title: tag + (i2 + 1), summary: tag + '（合成数据 · 非真实剧情）', kind: kind, quote: '',
          cast: cast, w: 0.25 + rnd(i2 * 5.9) * 0.7 });
        return i2;
      }
      var segLen = [6, 5, 5, 4], trunkEv = [], segs = [], cum = 0, tot = 20;
      for (i = 0; i < 4; i++) {
        var ev = [];
        for (j = 0; j < segLen[i]; j++) ev.push(mkEv(Math.min(11, i * 2 + Math.floor(j / 3)), KD[(i * 2 + j) % 7], '主线点'));
        segs.push({ threadId: 'T' + i, from: ev[0], to: ev[ev.length - 1], events: ev,
          t0: cum / tot, t1: (cum + segLen[i]) / tot, color: [0xffd166, 0x7af0c8, 0xff5d73, 0xc8a7ff][i], lead: NM[i] });
        cum += segLen[i];
        trunkEv = trunkEv.concat(ev);
      }
      var threads = [], cast = {};
      function addCast(name, id, evs, main) {
        if (!cast[name]) cast[name] = { threads: [], events: [], main: false, w: 0 };
        if (cast[name].threads.indexOf(id) < 0) cast[name].threads.push(id);
        cast[name].events = cast[name].events.concat(evs);
        cast[name].main = cast[name].main || !!main;
        cast[name].w = clamp(cast[name].w + 0.14, 0, 1);
      }
      function mkThread(id, kind, title, evs, parent, attach, depth, color, extra) {
        var cs = [], seen = {}, q, r;
        for (q = 0; q < evs.length; q++) {
          var e = events[evs[q]];
          for (r = 0; r < e.cast.length; r++) {
            var nm2 = e.cast[r];
            if (!seen[nm2]) { seen[nm2] = { name: nm2, n: 0, w: 0, entry: evs[q], exit: evs[q], camp: CP[NM.indexOf(nm2) % CP.length] }; cs.push(seen[nm2]); }
            seen[nm2].n++; seen[nm2].exit = evs[q];
          }
        }
        for (q = 0; q < cs.length; q++) cs[q].w = clamp(cs[q].n / Math.max(1, evs.length), 0.15, 1);
        cs.sort(function (a, b) { return b.w - a.w; });
        for (q = 0; q < cs.length; q++) addCast(cs[q].name, id, evs, kind === 'main');
        var t = { id: id, kind: kind, title: title, en: '', lead: cs.length ? cs[0].name : '', cast: cs, events: evs,
          len: evs.length, span: { from: events[evs[0]].chapIdx, to: events[evs[evs.length - 1]].chapIdx,
            chapters: events[evs[evs.length - 1]].chapIdx - events[evs[0]].chapIdx + 1 },
          parent: parent, attach: attach, depth: depth, heat: clamp(rnd(evs.length * 3.3 + depth) * 0.9 + 0.1, 0, 1),
          kindMix: {}, resolved: true, suspended: false, color: color, theme: '合成主题（非真实）', quote: '', src: 'derived' };
        for (q = 0; q < evs.length; q++) t.kindMix[events[evs[q]].kind] = (t.kindMix[events[evs[q]].kind] || 0) + 1;
        if (extra) for (q in extra) t[q] = extra[q];
        threads.push(t);
        return t;
      }
      for (i = 0; i < 4; i++) mkThread('T' + i, 'main', SEGN[i], segs[i].events, null, null, 0, segs[i].color, { en: 'MAIN-' + (i + 1), lead: NM[i], resolved: i === 3 });
      var blen = [3, 5, 4, 7, 2, 6, 3, 4, 2, 5, 3, 4], brIds = [];
      for (i = 0; i < 12; i++) {
        var ev2 = [];
        for (j = 0; j < blen[i]; j++) ev2.push(mkEv(Math.min(11, 1 + i), KD[(i + j * 3) % 7], '支线点'));
        var at = trunkEv[Math.min(trunkEv.length - 1, 1 + Math.floor(i * 1.55))];
        var susp = (i === 4 || i === 8);
        var id = 'T' + (4 + i);
        brIds.push(id);
        mkThread(id, 'branch', '合成支线 ' + '一二三四五六七八九十上下'.charAt(i), ev2, 'T' + Math.min(3, Math.floor(i / 3)), at, 1,
          KIND_COL[KD[i % 7]], { resolved: !susp, suspended: susp, en: 'BR-' + (i + 1) });
      }
      for (i = 0; i < 2; i++) {
        var ev3 = [mkEv(Math.min(11, 6 + i), KD[(i + 2) % 7], '末梢点'), mkEv(Math.min(11, 7 + i), KD[(i + 5) % 7], '末梢点')];
        mkThread('T' + (16 + i), 'twig', '合成末梢 ' + (i + 1), ev3, brIds[i * 3], null, 2, KIND_COL[KD[(i + 3) % 7]], { en: 'TW-' + (i + 1) });
      }
      var handoffs = [];
      for (i = 1; i < 4; i++) handoffs.push({ at: segs[i].from, from: 'T' + (i - 1), to: 'T' + i, t: segs[i].t0,
        shared: [NM[i - 1], NM[i]], reason: '合成换手依据（非真实）', kind: ['接棒', '并流', '断层'][(i - 1) % 3] });
      var junctions = [
        { at: threads[5].events[1], threads: ['T1', brIds[1]], t: 0.42, cast: [NM[1], NM[3]] },
        { at: threads[9].events[1], threads: ['T2', brIds[5]], t: 0.68, cast: [NM[2], NM[5]] }
      ];
      var bl = threads.filter(function (t2) { return t2.kind === 'branch'; });
      var covered = 0, nm3;
      for (nm3 in cast) covered++;
      return {
        ok: true, reason: '', src: 'derived', fp: 'sl-synth01', chapters: chapters, events: events, threads: threads,
        trunk: { segments: segs, events: trunkEv, len: trunkEv.length, chapters: 8,
          gaps: [{ after: trunkEv[7], chapters: 2 }, { after: trunkEv[14], chapters: 3 }] },
        handoffs: handoffs, junctions: junctions, cast: cast,
        stats: { events: events.length, threads: threads.length, main: 4, branches: bl.length, twigs: 2,
          trunkLen: trunkEv.length, trunkChapters: 8, trunkSegs: 4, handoffs: 3, junctions: 2,
          maxBranchLen: 7, avgBranchLen: 4, suspended: 2, castCovered: covered, coverage: 1, ms: 0 },
        warn: ['synthetic: 合成树，仅供 B 面几何验收']
      };
    }
  };

  function clearGeom() {
    var i;
    for (i = 0; i < tops.length; i++) {
      var n = tops[i];
      if (n && n.parent) n.parent.remove(n);
      if (n && n.traverse) n.traverse(function (x) {
        if (x.geometry) x.geometry.dispose();
        if (x.material) x.material.dispose();
      });
    }
    tops = [];
    root = skel = sheath = graft = junc = beads = leadRings = marks = null;
    L = null; ready = false; lodCut = 0;
    if (labLayer) { labLayer.innerHTML = ''; labs = []; labShown = 0; }
  }

  window.CLPlotTree = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
