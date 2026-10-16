(function () {
  'use strict';

  var GOLD = 2.39996;
  var TAU = Math.PI * 2;
  var TRUNK_N = 72;
  var FREE = 0.18;
  var AT_TOP = 0.74;
  var TIP_LO = 0.42, TIP_HI = 0.92;
  var TIP_RISE_MAX = 0.26;
  var ORDER1_K = 0.52, ORDER2_K = 0.52;

  var KIND_COL = { '高燃': 0xffd166, '转折': 0xffb45c, '抉择': 0xc8a7ff, '冲突': 0xff5d73,
                   '关系': 0xff9ad5, '领悟': 0x7af0c8, '日常': 0x9a92b8 };
  if (window.CLPalette && window.CLPalette.map) KIND_COL = window.CLPalette.map();

  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function str(v) { return v == null ? '' : String(v); }
  function sum(s) { var t = 0, i; for (i = 0; i < s.length; i++) t += s.charCodeAt(i); return t; }

  function V(x, y, z) { return [x, y, z]; }
  function vadd(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vmul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function vlen(a) { return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]); }
  function vnorm(a) { var L = vlen(a); return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0]; }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  function crownR(y) {
    y = clamp(num(y, 0), 0, 1);
    if (y <= 0.16) return 0.06;
    var u = (y - 0.16) / 0.84;
    var rise = Math.pow(Math.min(1, u / 0.55), 0.80);
    var fall = u <= 0.55 ? 1 : Math.pow(Math.cos((u - 0.55) / 0.45 * Math.PI * 0.5), 0.85);
    return 0.06 + 0.94 * Math.min(rise, fall);
  }

  function cat(cps, n) {
    if (cps.length < 2) return [cps[0] || V(0, 0, 0)];
    var p = [cps[0]].concat(cps, [cps[cps.length - 1]]), out = [], i, seg = cps.length - 1;
    for (i = 0; i < n; i++) {
      var u = seg * (i / (n - 1)), k = Math.min(seg - 1, Math.floor(u)), f = u - k;
      var p0 = p[k], p1 = p[k + 1], p2 = p[k + 2], p3 = p[k + 3], f2 = f * f, f3 = f2 * f, d;
      var o = [0, 0, 0];
      for (d = 0; d < 3; d++) {
        o[d] = 0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * f +
               (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * f2 +
               (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * f3);
      }
      out.push(o);
    }
    return out;
  }

  function taper(n, r0, r1) {
    var out = [], i;
    for (i = 0; i < n; i++) out.push(r1 + (r0 - r1) * Math.pow(1 - i / Math.max(1, n - 1), 1.35));
    return out;
  }

  var CACHE = null, CACHE_KEY = '', MS = {};

  function empty(reason) {
    return { ok: false, reason: reason, fp: '', logical: false, strictTopology: true,
      unit: 1, lengthMetric: 'event-count', dir: [0, 1, 0], height: 1,
      trunk: { pts: [], r: [], segs: [] }, boughs: [], limbs: [], twigs: [],
      eventAnchors: {}, threadPaths: {}, pending: [], unresolved: [],
      stats: { levels: 0, trunkPts: 0, boughs: 0, limbs: 0, twigs: 0, events: 0,
        unit: 1, pending: 0, unresolved: 0, ms: 0, fp: '', warn: [] } };
  }

  function buildLegacy(tree, opts) {
    opts = opts || {};
    if (!tree || tree.ok !== true) return empty('no-tree');
    var EV = tree.events || [], TH = tree.threads || [];
    if (!EV.length) return empty('no-events');

    var key = 'v35a|' + str(tree.fp) + '|' + num(opts.maxTwigs, 1200);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], i, j, k;
    var maxTwigs = num(opts.maxTwigs, 1200);

    var trunkSegs = [], tsrc = (tree.trunk && tree.trunk.segments) || [];
    for (i = 0; i < tsrc.length; i++) {
      var sg = tsrc[i] || {};
      trunkSegs.push({ t0: clamp(num(sg.t0, 0), 0, 1), t1: clamp(num(sg.t1, 1), 0, 1),
        threadId: str(sg.threadId), color: num(sg.color, 0xffb45c), lead: str(sg.lead) });
    }
    if (!trunkSegs.length) trunkSegs.push({ t0: 0, t1: 1, threadId: str(TH[0] && TH[0].id) || 'T0', color: 0xffb45c, lead: '' });

    var CFG = window.CLTreeShapeConfig || {};
    var tension = num(CFG.curvatureTension, 0.042);
    var tFreq = num(CFG.tensionFrequency, 1.85);
    var tp = [], tr = [];
    for (i = 0; i < TRUNK_N; i++) {
      var t = i / (TRUNK_N - 1);
      var cx = Math.sin(t * Math.PI * 0.9) * 0.035 + Math.sin(t * Math.PI * tFreq) * (tension * 0.22);
      var cz = Math.sin(t * Math.PI * 1.7) * 0.022 + Math.cos(t * Math.PI * tFreq) * (tension * 0.18);
      tp.push(V(cx, t, cz));

      var burl = 0;
      if (CFG.nodalBurls !== false && tsrc.length > 1) {
        for (var bi = 0; bi < tsrc.length; bi++) {
          var tj = clamp(num(tsrc[bi].t1, 0), 0.16, 0.94);
          if (tj > 0.16 && tj < 0.94) {
            var dt = t - tj;
            var falloff = num(CFG.burlFalloff, 0.022);
            burl += (num(CFG.burlRadiusScale, 1.28) - 1.0) * Math.exp(-(dt * dt) / (2 * falloff * falloff));
          }
        }
      }
      var baseR = 0.0178 * Math.pow(1 - t, 0.56) + 0.0029;
      tr.push(baseR * (1.0 + burl));
    }
    function trunkAt(t) {
      t = clamp(num(t, 0), 0, 1);
      var u = t * (TRUNK_N - 1), a = Math.floor(u), b = Math.min(TRUNK_N - 1, a + 1), f = u - a;
      return vadd(vmul(tp[a], 1 - f), vmul(tp[b], f));
    }
    function trunkR(t) {
      t = clamp(num(t, 0), 0, 1);
      var u = t * (TRUNK_N - 1), a = Math.floor(u), b = Math.min(TRUNK_N - 1, a + 1), f = u - a;
      return tr[a] * (1 - f) + tr[b] * f;
    }
    function radOf(az) { return [Math.cos(az), 0, Math.sin(az)]; }

    var trunkEv = (tree.trunk && tree.trunk.events) || [], trunkLen = Math.max(1, trunkEv.length - 1);
    var onTrunk = {}, maxOrder = 1;
    for (i = 0; i < trunkEv.length; i++) onTrunk[trunkEv[i]] = i / trunkLen;
    for (i = 0; i < EV.length; i++) maxOrder = Math.max(maxOrder, num(EV[i] && EV[i].order, i + 1));
    function posOf(ev) {
      if (onTrunk[ev] != null) return onTrunk[ev];
      var e = EV[ev];
      return clamp(num(e && e.order, 1) / maxOrder, 0, 1);
    }

    var mainIds = {}, branches = [], twigThreads = [], maxThLen = 1, maxBrLen = 1, byId = {};
    for (i = 0; i < trunkSegs.length; i++) mainIds[trunkSegs[i].threadId] = 1;
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {};
      byId[str(th.id)] = th;
      var dep = num(th.depth, th.kind === 'twig' ? 2 : (th.kind === 'main' ? 0 : 1));
      maxThLen = Math.max(maxThLen, num(th.len, 1));
      if (dep === 1) maxBrLen = Math.max(maxBrLen, num(th.len, 1));
      if (dep === 0 || mainIds[str(th.id)]) continue;
      (dep >= 2 ? twigThreads : branches).push(th);
    }
    branches.sort(function (a, b) {
      var pa = posOf(num(a.attach, (a.events || [0])[0])), pb = posOf(num(b.attach, (b.events || [0])[0]));
      return pa - pb || (str(a.id) < str(b.id) ? -1 : 1);
    });

    function frameOf(pts, at) {
      var hi = clamp(Math.round(at * (pts.length - 1)), 0, pts.length - 1);
      var tan = vnorm(vsub(pts[Math.min(pts.length - 1, hi + 1)], pts[Math.max(0, hi - 1)]));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      return { hi: hi, base: pts[hi], tan: tan, U: U, W: W };
    }

    var boughs = [], byThread = {};
    var NB = Math.max(1, branches.length);
    for (i = 0; i < NB; i++) {
      var b = branches[i];
      var at = clamp(FREE + posOf(num(b.attach, (b.events || [0])[0])) * (AT_TOP - FREE), FREE, AT_TOP);
      var az = (i * GOLD) % TAU;
      var rank = NB > 1 ? i / (NB - 1) : 0.5;
      var lr = Math.sqrt(clamp(num(b.len, 1) / maxBrLen, 0, 1));
      var heat = clamp(num(b.heat, 0.4), 0, 1);
      var tipY0 = clamp(TIP_LO + (TIP_HI - TIP_LO) * rank, TIP_LO, TIP_HI);
      var tipY = Math.min(tipY0, at + TIP_RISE_MAX);
      var tipR = crownR(tipY0) * (0.50 + 0.10 * lr) * (1 + (rnd(i * 13.3) - 0.5) * 0.16);
      var azEnd = az + (rnd(i * 5.7 + 2.1) - 0.5) * 0.46;
      var P0 = vadd(trunkAt(at), vmul(radOf(az), trunkR(at) * 0.95));
      var P3 = vadd(vmul(radOf(azEnd), tipR), V(0, tipY, 0));
      var chord = vsub(P3, P0), BL = Math.max(0.16, vlen(chord));
      var chDir = vnorm(chord);
      /* v35：上段仰角从 73.7° 收到 ≤62° —— 「扫帚形」的最后一处残留。
       * 系数 (−0.02 + 0.14·rank) 在 rank→1 时给出 +0.14·BL 的强上举，冠顶因此竖成扫帚梢。
       * 改为 (−0.06 + 0.085·rank)：低枝 −0.06 更强外抛（伞沿更宽），高枝 +0.025 只微微上举。
       * ⚠ 末端落点 P3 由 crownR(tipY) 决定，**与本系数无关** —— 所以冠幅包络（Q1）不动，
       *   两边被独立判据夹住：改仰角有 Q2b 兜，改冠形有 Q1 兜，谁也糊不过去。 */
      var upBias = BL * (-0.06 + 0.085 * rank);
      var drpBias = BL * (0.20 - 0.10 * rank) * (0.72 + 0.28 * (1 - heat));
      var c1 = vadd(P0, vmul(chDir, BL * 0.26)); c1[1] += upBias * 0.95;
      var c2 = vadd(P0, vmul(chDir, BL * 0.56)); c2[1] += upBias * 0.40;
      var c3 = vadd(P0, vmul(chDir, BL * 0.82)); c3[1] -= drpBias * 0.30;
      var pts = cat([P0, c1, c2, c3, V(P3[0], P3[1] - drpBias, P3[2])], 20);
      var r0 = trunkR(at) * 0.58;
      var it = { id: 'B' + (i < 10 ? '0' : '') + i, level: 1, order: 1, threadId: str(b.id), host: 'trunk',
        at: at, az: az, pts: pts, r: taper(pts.length, r0, r0 * 0.22), len: BL,
        color: num(b.color, 0xffb45c), lead: str(b.lead), heat: heat,
        resolved: !!b.resolved, suspended: !!b.suspended };
      boughs.push(it); byThread[it.threadId] = it;
    }

    var limbs = [], ln = 0, deepByThread = {};
    function mkLimb(host, at2, az2, len2, color, threadId, heat2, order) {
      var fr = frameOf(host.pts, at2);
      var hr = num(host.r[fr.hi], 0.004);
      var rad2 = vnorm(vadd(vmul(fr.U, Math.cos(az2)), vmul(fr.W, Math.sin(az2))));
      var th2 = (0.62 - 0.10 * order) - at2 * 0.10 + (rnd(ln * 7.13 + az2) - 0.5) * 0.16;
      th2 = clamp(th2, 0.16, 1.10);
      var dir2 = vnorm(vadd(vmul(rad2, Math.sin(th2)), vmul(fr.tan, Math.cos(th2))));
      var q0 = vadd(fr.base, vmul(rad2, hr * 0.9));
      var dr = len2 * (0.26 + 0.20 * (1 - clamp(heat2, 0, 1)));
      var npts = order <= 1 ? 14 : 9;
      var pts2 = cat([q0,
        vadd(q0, vmul(dir2, len2 * 0.40)),
        vadd(vadd(q0, vmul(dir2, len2 * 0.74)), V(0, -dr * 0.28, 0)),
        vadd(vadd(q0, vmul(dir2, len2 * 1.00)), V(0, -dr, 0))], npts);
      var rr = hr * (order <= 1 ? 0.60 : 0.52);
      var it2 = { id: 'L' + (ln < 10 ? '00' : ln < 100 ? '0' : '') + ln, level: 2, order: order,
        threadId: threadId, host: host.id || 'trunk',
        at: at2, az: az2, pts: pts2, r: taper(pts2.length, rr, rr * (order <= 1 ? 0.22 : 0.18)),
        len: len2, color: color, lead: '', heat: clamp(heat2, 0, 1),
        resolved: false, suspended: false };
      ln++; limbs.push(it2);
      if (threadId) deepByThread[threadId] = it2;
      return it2;
    }
    for (i = 0; i < twigThreads.length; i++) {
      var tw = twigThreads[i], host = byThread[str(tw.parent)];
      if (!host) { host = boughs[i % Math.max(1, boughs.length)]; if (!host) continue; warn.push('末梢线 ' + str(tw.id) + ' 的父线不在一级枝里，已就近挂靠'); }
      mkLimb(host, clamp(0.42 + rnd(i * 3.7) * 0.34, 0.3, 0.9), (host.az + GOLD * (1 + i)) % TAU,
        host.len * (0.30 + 0.18 * (num(tw.len, 1) / maxThLen)), num(tw.color, host.color), str(tw.id), num(tw.heat, 0.35), 1);
    }
    var order1 = [];
    for (i = 0; i < boughs.length; i++) {
      var hb = boughs[i], nb = clamp(Math.round(num(byId[hb.threadId] && byId[hb.threadId].len, 6) / 1.1), 5, 7);
      for (j = 0; j < nb; j++) {
        var at3 = 0.24 + (0.94 - 0.24) * (nb === 1 ? 0.5 : j / (nb - 1));
        var it3 = mkLimb(hb, at3, (hb.az + GOLD * (j + 1)) % TAU,
          hb.len * (0.42 - 0.14 * (j / Math.max(1, nb - 1))), hb.color, hb.threadId, hb.heat * 0.85, 1);
        order1.push(it3);
      }
    }
    for (i = 0; i < order1.length; i++) {
      var h1 = order1[i], nb2 = clamp(Math.round(h1.len * 11), 2, 4);
      for (j = 0; j < nb2; j++) {
        var at4 = 0.30 + 0.60 * (nb2 === 1 ? 0.5 : j / (nb2 - 1));
        mkLimb(h1, at4, (h1.az + GOLD * (j + 1.7)) % TAU,
          h1.len * (0.46 - 0.16 * (j / Math.max(1, nb2 - 1))), h1.color, h1.threadId, h1.heat * 0.8, 2);
      }
    }
    var roots = 0, ROOT_N = 9, BELT_N = 7;
    for (j = 0; j < ROOT_N; j++) {
      var rAz = (j * GOLD) % TAU + 0.35;
      var rRad = radOf(rAz);
      var rAt = 0.012, rBase = trunkAt(rAt);
      var rLen = 0.155 + 0.105 * rnd(j * 9.1);
      var rDir = vnorm(vadd(vmul(rRad, Math.sin(1.42)), V(0, Math.cos(1.42) - 0.72, 0)));
      var rPts = cat([rBase,
        vadd(rBase, vmul(rDir, rLen * 0.42)),
        vadd(vadd(rBase, vmul(rDir, rLen * 0.78)), V(0, -0.014, 0)),
        vadd(vadd(rBase, vmul(rDir, rLen)), V(0, -0.036, 0))], 10);
      var rRoot = trunkR(rAt) * 0.76;
      limbs.push({ id: 'R' + j, level: 2, order: 1, isRoot: true, threadId: '', host: 'trunk',
        at: rAt, az: rAz, pts: rPts, r: taper(rPts.length, rRoot, rRoot * 0.14),
        len: rLen, color: num(trunkSegs[0].color, 0xffb45c), lead: '', heat: 0.3,
        resolved: false, suspended: false });
      roots++;
    }
    for (j = 0; j < BELT_N; j++) {
      var bAz = (j / BELT_N) * TAU + 0.35 + (Math.PI / BELT_N);
      var bRad = radOf(bAz);
      var bAt = 0.004, bBase = trunkAt(bAt);
      var bLen = 0.058 + 0.042 * rnd(j * 6.7 + 1.3);
      var bDir = vnorm(vadd(vmul(bRad, 0.94), V(0, -0.34, 0)));
      var bPts = cat([bBase,
        vadd(bBase, vmul(bDir, bLen * 0.45)),
        vadd(vadd(bBase, vmul(bDir, bLen * 0.80)), V(0, -0.008, 0)),
        vadd(vadd(bBase, vmul(bDir, bLen)), V(0, -0.020, 0))], 7);
      var bRoot = trunkR(bAt) * 0.55;
      limbs.push({ id: 'K' + j, level: 2, order: 1, isRoot: true, threadId: '', host: 'trunk',
        at: bAt, az: bAz, pts: bPts, r: taper(bPts.length, bRoot, bRoot * 0.34),
        len: bLen, color: num(trunkSegs[0].color, 0xffb45c), lead: '', heat: 0.28,
        resolved: false, suspended: false });
      roots++;
    }
    var ats = [];
    for (i = 0; i < boughs.length; i++) ats.push(boughs[i].at);
    ats.push(FREE); ats.push(AT_TOP); ats.sort(function (a, b) { return a - b; });
    var trunkHost = { id: 'trunk', pts: tp, r: tr, az: 0, len: 1 };
    for (i = 1; i < ats.length; i++) {
      var gap = ats[i] - ats[i - 1];
      if (gap <= 0.14) continue;
      var nf = Math.min(3, Math.floor(gap / 0.14));
      for (j = 0; j < nf; j++) {
        var atf = ats[i - 1] + gap * ((j + 1) / (nf + 1));
        mkLimb(trunkHost, clamp(atf, 0.19, 0.72), (limbs.length * GOLD) % TAU,
          0.12 + 0.07 * rnd(i * 5.1 + j), trunkSegs[0].color, '', 0.3, 1);
      }
    }

    var evHost = {}, evAt = {};
    for (i = 0; i < TH.length; i++) {
      var th2b = TH[i] || {}, evs = th2b.events || [], dep2 = num(th2b.depth, th2b.kind === 'twig' ? 2 : (th2b.kind === 'main' ? 0 : 1));
      for (j = 0; j < evs.length; j++) {
        var e2 = evs[j];
        if (evHost[e2] == null || dep2 > evHost[e2].dep) evHost[e2] = { id: str(th2b.id), dep: dep2, at: evs.length > 1 ? j / (evs.length - 1) : 0.5 };
      }
    }
    var order = [];
    for (i = 0; i < EV.length; i++) order.push(i);
    if (EV.length > maxTwigs) {
      order.sort(function (a, b) { return num(EV[b].w, 0) - num(EV[a].w, 0) || a - b; });
      warn.push('细枝按剧情点权重截断：' + EV.length + ' → ' + maxTwigs);
      order = order.slice(0, maxTwigs);
      order.sort(function (a, b) { return a - b; });
    }
    var twigs = [];
    for (i = 0; i < order.length; i++) {
      var ev = order[i], e3 = EV[ev] || {}, info = evHost[ev];
      var hostObj = info ? (deepByThread[info.id] || byThread[info.id]) : null, atH, hostId, hostPts, hostR;
      if (hostObj) { atH = clamp(num(info.at, 0.5) * 0.62 + 0.30, 0.16, 0.96); hostId = hostObj.id; hostPts = hostObj.pts; hostR = hostObj.r; }
      else { atH = clamp(posOf(ev), 0.03, 0.97); hostId = 'trunk'; hostPts = tp; hostR = tr; }
      var frw = frameOf(hostPts, atH);
      var hrr = num(hostR[frw.hi], 0.004);
      var azw = (ev * GOLD + sum(hostId) * 0.37) % TAU;
      var radw = vnorm(vadd(vmul(frw.U, Math.cos(azw)), vmul(frw.W, Math.sin(azw))));
      var lw = 0.075 + 0.065 * clamp(num(e3.w, 0.4), 0, 1);
      if (hostId === 'trunk') lw *= 1.55;
      else if (hostObj && hostObj.len < 0.16) lw *= 0.85;
      var dirw = vnorm(vadd(vmul(radw, 0.86), vmul(frw.tan, 0.50)));
      var w0 = vadd(frw.base, vmul(radw, hrr * 0.92));
      var ptsw = cat([w0, vadd(w0, vmul(dirw, lw * 0.45)),
        vadd(vadd(w0, vmul(dirw, lw * 0.80)), V(0, lw * 0.06, 0)),
        vadd(vadd(w0, vmul(dirw, lw * 1.00)), V(0, lw * 0.16, 0))], 7);
      var rw = hrr * 0.42;
      twigs.push({ id: 'W' + (ev < 10 ? '000' : ev < 100 ? '00' : ev < 1000 ? '0' : '') + ev,
        level: 3, order: 1, host: hostId, at: atH, az: azw, pts: ptsw, r: taper(ptsw.length, rw, rw * 0.08),
        evIdx: ev, kind: str(e3.kind) || '日常', color: KIND_COL[str(e3.kind)] || KIND_COL['日常'],
        chapIdx: num(e3.chapIdx, 0) });
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var nO1 = 0, nO2 = 0;
    for (i = 0; i < limbs.length; i++) { if (limbs[i].order >= 2) nO2++; else nO1++; }
    var out = { ok: true, reason: '', fp: str(tree.fp), dir: [0, 1, 0], height: 1,
      trunk: { pts: tp, r: tr, segs: trunkSegs }, boughs: boughs, limbs: limbs, twigs: twigs,
      stats: { levels: 4, trunkPts: tp.length, boughs: boughs.length, limbs: limbs.length,
        order1: nO1, order2: nO2, roots: roots, twigs: twigs.length, events: EV.length,
        ms: MS[key], fp: str(tree.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  function buildStrict(tree, opts) {
    opts = opts || {};
    if (!tree || tree.ok !== true) return empty('no-tree');
    var EV = tree.events || [], TH = tree.threads || [], nEV = EV.length;
    if (!nEV) return empty('no-events');

    var key = 'v45s|' + str(tree.fp) + '|' + num(opts.maxTwigs, 1200);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], i, j, oq;
    var PEND_X = 1.8, ORPH_X = -1.8;

    function kindColor(kd) { return KIND_COL[str(kd)] || KIND_COL['日常']; }
    function pad3(n) { return n < 10 ? '00' + n : (n < 100 ? '0' + n : str(n)); }
    function hashStr(s) { var h = 0; s = str(s); for (var q = 0; q < s.length; q++) h = (h * 31 + s.charCodeAt(q)) | 0; return h >>> 0; }
    function frameFromDir(dir) {
      var up = Math.abs(vdot(dir, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(dir, up));
      return { U: U, W: vnorm(vcross(dir, U)) };
    }
    function radSeries(path, at) {
      var R = (path && path.r) ? path.r : [0.004];
      if (R.length < 2) return R[0];
      var u = clamp(num(at, 0), 0, 1) * (R.length - 1);
      var a = Math.floor(u), b = Math.min(R.length - 1, a + 1), f = u - a;
      return R[a] * (1 - f) + R[b] * f;
    }
    function dedupSorted(list) {
      var out = [], seen = {};
      for (var q = 0; q < (list || []).length; q++) {
        var e = Math.floor(num(list[q], -1));
        if (e >= 0 && e < nEV && !seen[e]) { seen[e] = 1; out.push(e); }
      }
      out.sort(function (x, y) { return x - y; });
      return out;
    }
    function reasonOf(t) {
      var r = str(t.pendingReason);
      if (/未来挂点/.test(r)) return 'future-attach';
      if (/成环/.test(r)) return 'cycle';
      if (/不存在/.test(r)) return 'bad-parent';
      if (/缺少 parent|缺少parent|自由枝/.test(r)) return 'free-branch';
      if (/attach/.test(r)) return 'missing-attach';
      if (/父线/.test(r)) return 'parent-pending';
      return 'pending';
    }

    var byId = {}, mainList = [], otherList = [];
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, id = str(th.id);
      if (!id || byId[id]) continue;
      byId[id] = th;
      if (th.kind === 'main' || num(th.depth, -1) === 0) mainList.push(th); else otherList.push(th);
    }
    function isMainT(t) { return !!t && (t.kind === 'main' || num(t.depth, -1) === 0); }

    var trunkOrder = [], trunkIdx = {}, seenT = {};
    for (i = 0; i < mainList.length; i++) {
      var mev = mainList[i].events || [];
      for (j = 0; j < mev.length; j++) {
        var e0 = Math.floor(num(mev[j], -1));
        if (e0 >= 0 && e0 < nEV && !seenT[e0]) { seenT[e0] = 1; trunkOrder.push(e0); }
      }
    }
    if (!trunkOrder.length) {
      var tsrcEv = (tree.trunk && tree.trunk.events) || [];
      for (i = 0; i < tsrcEv.length; i++) {
        var e1 = Math.floor(num(tsrcEv[i], -1));
        if (e1 >= 0 && e1 < nEV && !seenT[e1]) { seenT[e1] = 1; trunkOrder.push(e1); }
      }
    }
    trunkOrder.sort(function (a, b) { return a - b; });
    var nTrunk = trunkOrder.length, unit = 1 / Math.max(1, nTrunk - 1);
    for (i = 0; i < nTrunk; i++) trunkIdx[trunkOrder[i]] = i;

    var tp = [], tr = [];
    if (nTrunk > 0) {
      for (i = 0; i < nTrunk; i++) {
        var ty = i * unit;
        tp.push(V(0, ty, 0));
        tr.push(0.0178 * Math.pow(1 - Math.min(1, ty), 0.56) + 0.0029);
      }
    }
    var trunkPath = { kind: 'trunk', id: 'trunk', threadId: '', host: '', parent: null, attach: null,
      at: 0, depth: -1, dir: [0, 1, 0], start: tp.length ? tp[0].slice() : [0, 0, 0],
      len: Math.max(0, nTrunk - 1) * unit, pts: tp, r: tr, events: trunkOrder.slice(0),
      newEvents: trunkOrder.slice(0), evSet: {}, evPos: {}, stepCount: Math.max(0, nTrunk - 1),
      knownSteps: Math.max(0, nTrunk - 1), lengthMetric: 'event-count', topologyStatus: 'confirmed' };

    var hostPaths = { trunk: trunkPath }, threadPaths = {};
    var canon = {}, occCount = {}, pending = [], unresolved = [];
    function rec(e, pos, tid, host, at, src, depth) {
      occCount[e] = (occCount[e] || 0) + 1;
      if (!canon[e]) canon[e] = { pos: pos.slice(), threadId: tid, host: host, at: at, src: src, depth: depth };
    }

    for (i = 0; i < mainList.length; i++) {
      var mt = mainList[i], mid = str(mt.id), mevs = dedupSorted(mt.events);
      var mPos = {}, mEvs = [], mSet = {}, firstIdx = -1, lastIdx = -1;
      for (j = 0; j < mevs.length; j++) {
        var ti = trunkIdx[mevs[j]];
        if (ti == null) { warn.push('主线 ' + mid + ' 事件 ' + mevs[j] + ' 不在主干并集'); continue; }
        mEvs.push(mevs[j]); mSet[mevs[j]] = 1;
        mPos[mevs[j]] = { evIdx: mevs[j], pos: [0, ti * unit, 0], at: nTrunk > 1 ? ti / (nTrunk - 1) : 0, stepped: true };
        if (firstIdx < 0 || ti < firstIdx) firstIdx = ti;
        if (lastIdx < 0 || ti > lastIdx) lastIdx = ti;
      }
      var mPts = [];
      for (var mi = 0; firstIdx >= 0 && mi <= lastIdx - firstIdx; mi++) mPts.push([0, (firstIdx + mi) * unit, 0]);
      var mSteps = firstIdx >= 0 ? (lastIdx - firstIdx) : 0;
      var mp = { kind: 'main', id: mid, threadId: mid, host: 'trunk', parent: null, attach: null,
        at: 0, depth: 0, dir: [0, 1, 0], start: mPts.length ? mPts[0].slice() : [0, 0, 0],
        len: mSteps * unit, pts: mPts, r: taper(mPts.length || 1, radSeries(trunkPath, 0), 0.006),
        events: mEvs, newEvents: mEvs.slice(0), eventPositions: mPos, evPos: mPos, evSet: mSet,
        stepCount: mSteps, knownSteps: mSteps, color: num(mt.color, 0xffb45c), lead: str(mt.lead),
        sourceId: str(mt.sourceId), resolved: !!mt.resolved, suspended: !!mt.suspended,
        level: 0, order: 0, lengthMetric: 'event-count', topologyStatus: 'confirmed' };
      threadPaths[mid] = mp; hostPaths[mid] = mp;
      for (oq in mPos) if (mPos.hasOwnProperty(oq)) rec(mPos[oq].evIdx, mPos[oq].pos, mid, mid, mPos[oq].at, 'confirmed', 0);
    }

    function depthOfT(t) {
      var d = 0, cur = t, hop = 0;
      while (cur && hop++ < 128) {
        if (isMainT(cur)) return d;
        cur = cur.parent != null ? byId[str(cur.parent)] : null;
        d++;
      }
      return d;
    }
    var orderList = [];
    for (i = 0; i < otherList.length; i++) {
      var ot = otherList[i];
      if (ot.topologyStatus && ot.topologyStatus !== 'confirmed') continue;
      orderList.push(str(ot.id));
    }
    orderList.sort(function (a, b) { return depthOfT(byId[a]) - depthOfT(byId[b]) || (a < b ? -1 : 1); });

    var boughs = [], limbs = [], bCount = 0, lCount = 0;
    for (i = 0; i < orderList.length; i++) {
      var id2 = orderList[i], t2 = byId[id2];
      var pid2 = t2.parent == null ? '' : str(t2.parent);
      var ae2 = (t2.attach == null) ? -1 : Math.floor(num(t2.attach, -1));
      var pth = byId[pid2], parentPath = threadPaths[pid2];
      var bad = '';
      if (!pid2) bad = 'free-branch';
      else if (!pth) bad = 'bad-parent';
      else if (ae2 < 0) bad = 'missing-attach';
      else if (!parentPath) bad = 'parent-pending';
      else if (!parentPath.evSet || !parentPath.evSet[ae2]) bad = 'bad-attach';
      else if (t2.events && t2.events.length && ae2 > Math.floor(num(t2.events[0], 1e9))) bad = 'future-attach';
      if (bad) { t2.topologyStatus = 'pending'; t2.pendingReason = str(t2.pendingReason) || bad; warn.push('线 ' + id2 + ' 确认边不成立（' + bad + '），降级 pending'); continue; }
      var tev = dedupSorted(t2.events);
      var hasBase = tev.length > 0 && tev[0] === ae2;
      var steps = hasBase ? tev.slice(1) : tev.slice(0);
      var stepCount = steps.length;
      var start = parentPath.evPos[ae2].pos.slice();
      var dp = depthOfT(t2), fr = frameFromDir(parentPath.dir);
      var az = ((hashStr(id2) % 10007) / 10007) * TAU % TAU;
      var el = clamp(0.10 + 0.05 * dp, 0.08, 0.42);
      var dir = vnorm(vadd(vadd(vmul(fr.U, Math.cos(az)), vmul(fr.W, Math.sin(az))), vmul(parentPath.dir, el)));
      var pts = [start.slice()];
      for (j = 1; j <= stepCount; j++) pts.push(vadd(start, vmul(dir, j * unit)));
      var evPos = {}, evSet = {};
      if (hasBase) { evPos[ae2] = { evIdx: ae2, pos: start.slice(), at: 0, stepped: false }; evSet[ae2] = 1; }
      for (j = 0; j < steps.length; j++) {
        evPos[steps[j]] = { evIdx: steps[j], pos: vadd(start, vmul(dir, (j + 1) * unit)), at: stepCount ? (j + 1) / stepCount : 0, stepped: true };
        evSet[steps[j]] = 1;
      }
      var r0 = radSeries(parentPath, parentPath.evPos[ae2].at) * 0.58;
      if (!isFinite(r0) || r0 <= 0) r0 = 0.006;
      var geomId = (dp <= 1 ? 'B' : 'L') + pad3(dp <= 1 ? (bCount++) : (lCount++));
      var path = { kind: 'branch', id: geomId, threadId: id2, host: parentPath.id, parent: pid2, attach: ae2,
        at: parentPath.evPos[ae2].at, depth: dp, dir: dir, start: start, len: stepCount * unit, pts: pts,
        r: taper(pts.length || 1, r0, r0 * 0.22), events: tev.slice(0), newEvents: steps.slice(0),
        eventPositions: evPos, evPos: evPos, evSet: evSet, stepCount: stepCount, knownSteps: stepCount,
        color: num(t2.color, 0xffb45c), lead: str(t2.lead), heat: clamp(num(t2.heat, 0.4), 0, 1),
        sourceId: str(t2.sourceId), resolved: !!t2.resolved, suspended: !!t2.suspended,
        level: dp <= 1 ? 1 : 2, order: dp, lengthMetric: 'event-count', topologyStatus: 'confirmed' };
      threadPaths[id2] = path; hostPaths[geomId] = path;
      if (dp <= 1) boughs.push(path); else limbs.push(path);
      for (oq in evPos) if (evPos.hasOwnProperty(oq)) rec(evPos[oq].evIdx, evPos[oq].pos, id2, geomId, evPos[oq].at, 'confirmed', dp);
    }

    var py = 0, pendN = 0;
    for (i = 0; i < otherList.length; i++) {
      var pt = otherList[i], pid = str(pt.id);
      if (pt.topologyStatus === 'confirmed') continue;
      if (threadPaths[pid]) continue;
      var pevs = dedupSorted(pt.events), code = reasonOf(pt), nP = pevs.length;
      unresolved.push({ threadId: pid, sourceId: str(pt.sourceId), code: code, reason: str(pt.pendingReason) || code, events: pevs.slice(0) });
      var pStart = [PEND_X + (pendN % 4) * 0.22, py, 0];
      var pPts = [pStart.slice()];
      var pPos = {}, pSet = {};
      for (j = 0; j < nP; j++) {
        var ppos = nP > 1 ? [pStart[0], py + j * unit, 0] : [pStart[0], py, 0];
        if (j > 0) pPts.push(ppos.slice());
        pPos[pevs[j]] = { evIdx: pevs[j], pos: ppos, at: nP > 1 ? j / (nP - 1) : 0, stepped: j > 0 };
        pSet[pevs[j]] = 1;
      }
      var pPath = { kind: pt.kind === 'twig' ? 'twig' : 'branch', id: 'P' + pad3(pendN), threadId: pid, host: 'pending',
        parent: pt.declaredParent != null ? str(pt.declaredParent) : null,
        attach: (pt.declaredAttach == null || pt.declaredAttach === '') ? null : str(pt.declaredAttach),
        at: 0, depth: 1, dir: [0, 1, 0], start: pStart, len: Math.max(0, nP - 1) * unit, pts: pPts,
        r: taper(pPts.length || 1, 0.010, 0.003), events: pevs.slice(0), newEvents: pevs.slice(0),
        eventPositions: pPos, evPos: pPos, evSet: pSet, stepCount: Math.max(0, nP - 1), knownSteps: Math.max(0, nP - 1), reason: code,
        color: num(pt.color, 0xffb45c), lead: str(pt.lead), heat: 0.3, level: 0, order: 0,
        sourceId: str(pt.sourceId), lengthMetric: 'event-count', topologyStatus: 'pending' };
      threadPaths[pid] = pPath; hostPaths[pPath.id] = pPath; pending.push(pPath);
      for (oq in pPos) if (pPos.hasOwnProperty(oq)) rec(pPos[oq].evIdx, pPos[oq].pos, pid, pPath.id, pPos[oq].at, 'pending', 1);
      py += Math.max(1, nP) * unit + unit;
      pendN++;
    }
    var tu = tree.unresolved || [];
    for (i = 0; i < tu.length; i++) {
      var u = tu[i] || {};
      if (u.threadId == null) unresolved.push({ threadId: null, sourceId: str(u.sourceId), code: 'unknown-order', reason: str(u.reasons) || '来源线无有效事件', events: [] });
    }

    var owned = {}, orph = [];
    for (i = 0; i < nTrunk; i++) owned[trunkOrder[i]] = 1;
    for (i = 0; i < otherList.length; i++) { var oev = otherList[i].events || []; for (j = 0; j < oev.length; j++) { var oo = Math.floor(num(oev[j], -1)); if (oo >= 0 && oo < nEV) owned[oo] = 1; } }
    for (i = 0; i < nEV; i++) if (!owned[i]) orph.push(i);
    if (orph.length) {
      var oPts = [[ORPH_X, 0, 0]], oN = orph.length, oR = 0.010;
      for (i = 1; i <= oN; i++) oPts.push([ORPH_X, i * unit, 0]);
      var oPath = { kind: 'branch', id: 'O', threadId: 'orphan', host: 'orphan', parent: null, attach: null,
        at: 0, depth: 0, dir: [0, 1, 0], start: [ORPH_X, 0, 0], len: oN * unit, pts: oPts,
        r: taper(oPts.length, oR, 0.003), events: orph, newEvents: orph, eventPositions: {}, evSet: {}, evPos: {}, stepCount: oN, knownSteps: oN,
        color: 0x9a92b8, lead: '', heat: 0.2, level: 0, order: 0,
        lengthMetric: 'event-count', topologyStatus: 'orphan' };
      for (i = 0; i < orph.length; i++) {
        var s4 = i + 1, opos = [ORPH_X, s4 * unit, 0], oat = s4 / oN;
        oPath.evPos[orph[i]] = { evIdx: orph[i], pos: opos, at: oat, stepped: true };
        oPath.eventPositions[orph[i]] = oPath.evPos[orph[i]];
        oPath.evSet[orph[i]] = 1;
        rec(orph[i], opos, 'orphan', 'O', oat, 'orphan', 0);
      }
      hostPaths['O'] = oPath;
      pending.push(oPath);
      warn.push('无归属事件 ' + orph.length + ' 个，已放独立索引轨（不编造主/支线）');
    }

    var eventAnchors = {}, twigs = [];
    for (i = 0; i < nEV; i++) {
      var c = canon[i];
      if (!c) { warn.push('事件 ' + i + ' 无 occurrence，跳过'); continue; }
      eventAnchors[i] = { pos: c.pos.slice(), threadId: c.threadId, host: c.host, at: c.at,
        occurrences: occCount[i] || 1, canonical: true };
      var hpath = hostPaths[c.host], hdir = hpath ? hpath.dir : [0, 1, 0];
      var ml = clamp(unit * 0.5, 0.004, 0.06);
      var mpts = [vsub(c.pos, vmul(hdir, ml)), c.pos.slice()];
      var hr = hpath ? radSeries(hpath, c.at) : 0.004;
      var evD = EV[i] || {};
      twigs.push({ id: 'M' + (i < 10 ? '000' : i < 100 ? '00' : i < 1000 ? '0' : '') + i,
        level: 3, order: 1, host: c.host, at: c.at, az: Math.atan2(hdir[2], hdir[0]), pts: mpts,
        r: taper(mpts.length, Math.max(0.0015, hr * 0.5), Math.max(0.0005, hr * 0.5 * 0.3)),
        evIdx: i, kind: str(evD.kind) || '日常', color: kindColor(evD.kind), chapIdx: num(evD.chapIdx, 0),
        isEventMarker: true, threadId: c.threadId });
    }

    var segs = [];
    for (i = 0; i < mainList.length; i++) {
      var mm = mainList[i], mev2 = mm.events || [], fi = -1, la = -1;
      for (j = 0; j < mev2.length; j++) {
        var ix = trunkIdx[Math.floor(num(mev2[j], -1))];
        if (ix == null) continue;
        if (fi < 0 || ix < fi) fi = ix;
        if (la < 0 || ix > la) la = ix;
      }
      if (fi < 0) continue;
      segs.push({ t0: nTrunk > 1 ? fi / (nTrunk - 1) : 0, t1: nTrunk > 1 ? la / (nTrunk - 1) : 0,
        threadId: str(mm.id), color: num(mm.color, 0xffb45c), lead: str(mm.lead) });
    }
    if (!segs.length) {
      var tsrc2 = (tree.trunk && tree.trunk.segments) || [];
      for (i = 0; i < tsrc2.length; i++) {
        var sg2 = tsrc2[i] || {};
        segs.push({ t0: clamp(num(sg2.t0, 0), 0, 1), t1: clamp(num(sg2.t1, 1), 0, 1),
          threadId: str(sg2.threadId), color: num(sg2.color, 0xffb45c), lead: str(sg2.lead) });
      }
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var nO1 = 0, nO2 = 0, maxDepth = 0;
    for (i = 0; i < limbs.length; i++) { if (limbs[i].order >= 2) nO2++; else nO1++; if (limbs[i].depth > maxDepth) maxDepth = limbs[i].depth; }
    for (i = 0; i < boughs.length; i++) if (boughs[i].depth > maxDepth) maxDepth = boughs[i].depth;
    var out = { ok: true, reason: '', fp: str(tree.fp), logical: true, strictTopology: true, dir: [0, 1, 0], height: 1,
      unit: unit, lengthMetric: 'event-count',
      trunk: { pts: tp, r: tr, segs: segs }, boughs: boughs, limbs: limbs, twigs: twigs,
      eventAnchors: eventAnchors, threadPaths: threadPaths, pending: pending, unresolved: unresolved,
      stats: { levels: maxDepth + 1, trunkPts: tp.length, boughs: boughs.length, limbs: limbs.length,
        order1: nO1, order2: nO2, roots: 0, twigs: twigs.length, events: nEV, unit: unit,
        pending: pending.length, unresolved: unresolved.length, ms: MS[key], fp: str(tree.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  function build(tree, opts) {
    if (tree && (tree.strictTopology === true || (opts && opts.strictTopology === true))) return buildStrict(tree, opts);
    return buildLegacy(tree, opts);
  }

  var API = {
    build: build,
    shape: build,
    get: function () { return CACHE; },
    crownR: crownR,
    stats: function () { return CACHE ? CACHE.stats : { levels: 0, ready: false }; }
  };
  window.CLTreeShape = API;
})();
