(function (g) {
  'use strict';
  var BAND_SP = 5, MIN_GAP = 18;

  var clamp = g.CLSkyUtil.clamp;
  function f1(v) { return v.toFixed(1); }

  function bins(L, dots, w) {
    var out = [], b;
    for (b = 0; b < L.nb; b++) out.push(0);
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i], v = w(d);
      if (!v) continue;
      b = Math.min(L.nb - 1, Math.max(0, Math.floor((d.o.c - L.c0) / L.span * L.nb)));
      out[b] += v;
    }
    var s = [];
    for (b = 0; b < L.nb; b++) s.push(((out[b - 1] || 0) + 2 * out[b] + (out[b + 1] || 0)) / 4);
    return s;
  }
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

  function layout(o) {
    var dots = o.dots || [], N = dots.length;
    if (N < 2) return null;
    var chord = o.x1 - o.x0;
    if (chord / (N - 1) >= (o.minSp || BAND_SP)) return null;
    var c0 = dots[0].o.c, c1 = dots[N - 1].o.c;
    var L = { dots: dots, x0: o.x0, x1: o.x1, chord: chord, y: o.y, c0: c0, span: Math.max(1, c1 - c0 + 1), nb: Math.max(16, Math.floor(chord / 3)), hMax: o.hMax || 7, keyMax: o.keyMax || 3.5 };
    L.xOf = function (c) { return L.x0 + L.chord * (c - L.c0 + 0.5) / L.span; };
    var all = bins(L, dots, function (d) { return d.o.count || 1; }), key = bins(L, dots, function (d) { return d.o.keyCount || 0; });
    L.vmax = 1e-6; all.forEach(function (v) { if (v > L.vmax) L.vmax = v; });
    L.pathAll = bandPath(L, all, L.hMax);
    L.pathKey = bandPath(L, key, L.keyMax);
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
    if (hasKey) take(firstKey);
    take(0); take(N - 1);
    var order = [];
    for (k = 0; k < N; k++) order.push(k);
    order.sort(function (a, b) { var A = dots[a].o, B = dots[b].o; return ((B.imp || 0) - (A.imp || 0)) || ((B.keyCount || 0) - (A.keyCount || 0)) || ((B.count || 1) - (A.count || 1)) || (a - b); });
    for (var j = 0; j < order.length && xs.length < K; j++) if (!hasKey || dots[order[j]].o.key || (dots[order[j]].o.imp || 0) >= 1.2) take(order[j]);
    L.shown = shown;
    L.shownList = Object.keys(shown).map(Number).sort(function (a, b) { return a - b; });
    L.nearest = function (x) {
      var lo = 0, hi = N - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (L.xOf(dots[mid].o.c) < x) lo = mid; else hi = mid; }
      return Math.abs(L.xOf(dots[lo].o.c) - x) <= Math.abs(L.xOf(dots[hi].o.c) - x) ? lo : hi;
    };
    L.boxes = [];
    var stepB = Math.max(1, Math.round(24 / (chord / L.nb)));
    for (var b = 0; b < L.nb; b += stepB) {
      var x = L.x0 + L.chord * (b + 0.5) / L.nb, y = L.y(x), h = Math.max(0.7, halfW(L, all[b], L.hMax));
      L.boxes.push([x - 12, y - h - 1, x + 12, y + h + 1]);
    }
    return L;
  }
  function subset(L, pick, hMax) {
    if (!L) return '';
    var v = bins(L, L.dots, function (d) { return pick(d) ? (d.o.count || 1) : 0; }), m = 1e-6;
    v.forEach(function (x) { if (x > m) m = x; });
    var S = { nb: L.nb, x0: L.x0, x1: L.x1, chord: L.chord, y: L.y, vmax: m };
    return bandPath(S, v, hMax || L.hMax * 0.6);
  }

  var KIND_W = { 高潮: 1, 揭秘: 0.9, 转折: 0.85, 高燃: 0.8, 抉择: 0.75, 冲突: 0.6, 智斗: 0.55, 智谋: 0.55, 智取: 0.55, 领悟: 0.5, 伏笔: 0.45, 关系: 0.3, 情感: 0.3, 日常: 0.1 };
  function kindW(k) {
    k = String(k || ''); if (KIND_W[k] != null) return KIND_W[k];
    for (var key in KIND_W) if (Object.prototype.hasOwnProperty.call(KIND_W, key) && k.indexOf(key) >= 0) return KIND_W[key];
    return 0.3;
  }
  function context(name, G, V) {
    var imp = {}, bounds = {}, idOf = Object.create(null), causes = [], cause = {}, i;
    (G.characters || []).forEach(function (c) { imp[c.name] = +c.importance || 0; });
    ((V && V.storylines) || G.storylines || []).forEach(function (sl) {
      var ord = (sl.events || []).filter(function (x) { return typeof x === 'number' && isFinite(x); });
      if (!ord.length) return;
      var lo = Math.min.apply(null, ord), hi = Math.max.apply(null, ord), w = (sl.lead === name ? 0.9 : 0.55) + (/主/.test(sl.kind || '') ? 0.1 : 0);
      bounds[lo] = Math.max(bounds[lo] || 0, w); bounds[hi] = Math.max(bounds[hi] || 0, w);
    });
    var evs = G.events || [];
    for (i = 0; i < evs.length; i++) if (evs[i].id != null) { var id = String(evs[i].id); idOf[id] = Object.prototype.hasOwnProperty.call(idOf, id) ? null : i; }
    ((V && V.causeEdges) || G.causeEdges || []).forEach(function (ce) {
      if (!ce || ce.resolved === false || ce.referenceStatus === 'unresolved') return;
      var a = idOf[ce.fromEventId != null ? ce.fromEventId : ce.sourceId], b = idOf[ce.toEventId != null ? ce.toEventId : ce.targetId];
      if (a == null || b == null || a === b) return;
      var status = g.CLAtlasSource && g.CLAtlasSource.evidenceStatus ? g.CLAtlasSource.evidenceStatus(ce) : null;
      causes.push({ a: a, b: b, basis: status ? status.label : '未核验', desc: ce.description || '', quote: ce.quote || (ce.evidenceQuotes || [])[0] || '' });
      cause[a] = (cause[a] || 0) + 1; cause[b] = (cause[b] || 0) + 1;
    });
    return { name: name, imp: imp, bounds: bounds, causes: causes, cause: cause };
  }
  function eventScore(e, i, ctx) {
    var s = kindW(e.kind), o = [];
    (e.characters || []).forEach(function (n) { if (n !== ctx.name) o.push(ctx.imp[n] || 0); });
    o.sort(function (a, b) { return b - a; });
    s += 0.35 * ((o[0] || 0) + (o[1] || 0)) / 100;
    if (e.order != null && ctx.bounds[e.order]) s += ctx.bounds[e.order];
    if (e.quote) s += e.quoteVerified === true ? 0.3 : 0.1;
    if (ctx.cause[i]) s += 0.4;
    return s;
  }
  function slots(dots, x0, x1, M) {
    var w = (x1 - x0) / Math.max(1, M), out = [], s;
    for (s = 0; s < M; s++) out.push({ s: s, list: [], best: 0 });
    dots.forEach(function (d) {
      if (!(d.r > 0)) return;
      s = Math.min(M - 1, Math.max(0, Math.floor((d.x - x0) / Math.max(1e-6, w)))); out[s].list.push(d);
    });
    out.forEach(function (sl) { sl.list.sort(function (a, b) { return (b.o.imp || 0) - (a.o.imp || 0) || a.x - b.x; }); sl.best = sl.list.length ? sl.list[0].o.imp || 0 : -1; });
    return out.filter(function (sl) { return sl.list.length; }).sort(function (a, b) { return b.best - a.best || a.s - b.s; });
  }
  function causeLinks(ctx, beadOf) {
    var arcs = [], self = {};
    ctx.causes.forEach(function (c) {
      var ka = beadOf[c.a], kb = beadOf[c.b];
      if (ka == null || kb == null) return;
      if (ka === kb) { (self[ka] = self[ka] || []).push(c); return; }
      arcs.push({ ka: ka, kb: kb, c: c });
    });
    return { arcs: arcs, self: self };
  }

  g.CLSkyCompassBand = { layout: layout, subset: subset, BAND_SP: BAND_SP, context: context, eventScore: eventScore, slots: slots, causeLinks: causeLinks };
})(window);
