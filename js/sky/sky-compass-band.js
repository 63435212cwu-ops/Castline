/**
 * @role component
 * @owns js/sky/sky-compass-band.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 罗盘因果链的「密度带」排版（只算几何，不碰 DOM；DOM 归 sky-compass）。
 * 一回一颗珠排不开时（珠距 < 5 px：大书主角动辄几百回），链改按回序铺成一条密度带：
 *  · 横轴 = 时间（第一回出场 → 最后一回），不出场的回段带子收成一根细线——看得出他什么时候缺席；
 *  · 带宽 ∝ √(该段事件数)，关键事件另起一层金色芯带（同一把尺，芯带永远不宽过外带）；
 *  · 带上只留少数几颗关键珠：第一个关键事件、首尾两回、事件最多的关键回（互相至少隔 18 px），其余回悬停带子就近取；
 *  · 悬停关系对象时，与他同场的回在带上另画一层（subset 路径）。
 * ES5；不开 rAF / setInterval；只读传入的珠列表，不改数据。
 */
(function (g) {
  'use strict';
  var BAND_SP = 5, MIN_GAP = 18;

  var clamp = g.CLSkyUtil.clamp;
  function f1(v) { return v.toFixed(1); }

  /* 分箱计数：dots 按回序（o.c 升序）；w(d) 返回这一回要计入的量 */
  function bins(L, dots, w) {
    var out = [], b;
    for (b = 0; b < L.nb; b++) out.push(0);
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i], v = w(d);
      if (!v) continue;
      b = Math.min(L.nb - 1, Math.max(0, Math.floor((d.o.c - L.c0) / L.span * L.nb)));
      out[b] += v;
    }
    /* [1 2 1] / 4 平滑：3 px 一箱的原始计数太碎，带边会锯齿 */
    var s = [];
    for (b = 0; b < L.nb; b++) s.push(((out[b - 1] || 0) + 2 * out[b] + (out[b + 1] || 0)) / 4);
    return s;
  }
  /* 一条闭合带：沿链的中心线上下各让出 h(b) —— 先走上沿（左→右）再走下沿（右→左） */
  /* 半宽 ∝ (v / 全带峰值)^0.8：比 √ 更舍得拉开疏密（大书主角几乎回回在场，√ 会把起伏压成一根匀带） */
  function halfW(L, v, hMax) { return v > 0 ? Math.max(0.7, hMax * Math.pow(v / L.vmax, 0.8)) : 0; }
  function bandPath(L, vals, hMax) {
    var up = [], dn = [], b, any = false;
    for (b = 0; b < L.nb; b++) {
      var v = vals[b], h = halfW(L, v, hMax), x = L.x0 + L.chord * (b + 0.5) / L.nb, y = L.y(x);
      if (h > 0) any = true;
      up.push(f1(x) + ' ' + f1(y - h)); dn.push(f1(x) + ' ' + f1(y + h));
    }
    if (!any) return '';
    var d = 'M' + f1(L.x0) + ' ' + f1(L.y(L.x0)) + 'L' + up.join('L') + 'L' + f1(L.x1) + ' ' + f1(L.y(L.x1)) + 'L' + dn.reverse().join('L') + 'Z';
    return d;
  }

  /* o: { dots, x0, x1, y(x), hMax, keyMax, gap } → 带的几何；珠数够少（珠距 ≥ 5 px）返回 null，照旧一回一颗珠 */
  function layout(o) {
    var dots = o.dots || [], N = dots.length;
    if (N < 2) return null;
    var chord = o.x1 - o.x0;
    if (chord / (N - 1) >= (o.minSp || BAND_SP)) return null;
    var c0 = dots[0].o.c, c1 = dots[N - 1].o.c;
    /* 外带半宽 ≤ 7 px；金芯用同一把尺再乘 0.5——关键事件占满的段，金芯也只占带宽一半，外带的疏密始终看得见 */
    var L = { dots: dots, x0: o.x0, x1: o.x1, chord: chord, y: o.y, c0: c0, span: Math.max(1, c1 - c0 + 1), nb: Math.max(16, Math.floor(chord / 3)), hMax: o.hMax || 7, keyMax: o.keyMax || 3.5 };
    L.xOf = function (c) { return L.x0 + L.chord * (c - L.c0 + 0.5) / L.span; };
    var all = bins(L, dots, function (d) { return d.o.count || 1; }), key = bins(L, dots, function (d) { return d.o.keyCount || 0; });
    L.vmax = 1e-6; all.forEach(function (v) { if (v > L.vmax) L.vmax = v; });
    L.pathAll = bandPath(L, all, L.hMax);
    L.pathKey = bandPath(L, key, L.keyMax);
    /* 带上的珠：首尾两回 + 第一个关键回 + 按「关键数 → 事件数」挑，互相隔开 MIN_GAP */
    var K = clamp(Math.floor(chord / 34), 6, 28), gap = o.gap || MIN_GAP, shown = {}, xs = [];
    function take(k) {
      if (shown[k]) return true;
      var x = L.xOf(dots[k].o.c);
      for (var i = 0; i < xs.length; i++) if (Math.abs(xs[i] - x) < gap) return false;
      shown[k] = true; xs.push(x); return true;
    }
    var firstKey = -1, k;
    for (k = 0; k < N; k++) if (dots[k].o.key) { firstKey = k; break; }
    var hasKey = firstKey >= 0;
    if (hasKey) take(firstKey);   /* 预演 K2「第一个关键事件」要能在带上点到它 */
    take(0); take(N - 1);
    var order = [];
    for (k = 0; k < N; k++) order.push(k);
    order.sort(function (a, b) { var A = dots[a].o, B = dots[b].o; return ((B.keyCount || 0) - (A.keyCount || 0)) || ((B.count || 1) - (A.count || 1)) || (a - b); });
    for (var j = 0; j < order.length && xs.length < K; j++) if (!hasKey || dots[order[j]].o.key) take(order[j]);
    L.shown = shown;
    L.shownList = Object.keys(shown).map(Number).sort(function (a, b) { return a - b; });
    /* 悬停带子：横坐标 → 最近的一回（二分，珠按回序） */
    L.nearest = function (x) {
      var lo = 0, hi = N - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (L.xOf(dots[mid].o.c) < x) lo = mid; else hi = mid; }
      return Math.abs(L.xOf(dots[lo].o.c) - x) <= Math.abs(L.xOf(dots[hi].o.c) - x) ? lo : hi;
    };
    /* 标签避让用的带体盒：每 ~24 px 一段 */
    L.boxes = [];
    var stepB = Math.max(1, Math.round(24 / (chord / L.nb)));
    for (var b = 0; b < L.nb; b += stepB) {
      var x = L.x0 + L.chord * (b + 0.5) / L.nb, y = L.y(x), h = Math.max(0.7, halfW(L, all[b], L.hMax));
      L.boxes.push([x - 12, y - h - 1, x + 12, y + h + 1]);
    }
    return L;
  }
  /* 同一把尺画一个子集（悬停关系对象：同场的回） */
  /* 子集按自己的峰值归一（同场的回通常远少于全部，借全带的尺会细成看不见的丝），半宽上限取外带的 0.6 */
  function subset(L, pick, hMax) {
    if (!L) return '';
    var v = bins(L, L.dots, function (d) { return pick(d) ? (d.o.count || 1) : 0; }), m = 1e-6;
    v.forEach(function (x) { if (x > m) m = x; });
    var S = { nb: L.nb, x0: L.x0, x1: L.x1, chord: L.chord, y: L.y, vmax: m };
    return bandPath(S, v, hMax || L.hMax * 0.6);
  }

  g.CLSkyCompassBand = { layout: layout, subset: subset, BAND_SP: BAND_SP };
})(window);
