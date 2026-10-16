(function (g) {
  'use strict';
  var R0 = 100, RK = 0.8, LOW = 1.25, SETTLE = 180, ZOOM = 0.02, MORPH = 1500;
  var tugK = null, tugSig = '', tugN = 0, moving = true, pend = true, morphTo = 0, selD = 0, selW = 0, selH = 0, selR = 0;
  var CORE = 6, KPX = 36, KMIN = 3, KMAX = 40, RPX0 = 434, KF = 6, HOT = 4, LVA = 12, EDGE = 16, CELL = 6400;
  var tab = null, plan = null, disc = null, discA = 0, hotC = null;
  var cur = { dist: 0, W: 0, H: 0 };
  var st = { quota: 0, forced: 0, drop: 0, resel: 0, keep: 0, sel: '', r: R0 };

  function low() {
    try {
      var S = g.CLScene && g.CLScene.current, K = g.CLSkyTokens;
      return !!(S && S.core && K && K.tierOf && K.tierOf(S.core().getDegrade()) === 'low');
    } catch (e) { return false; }
  }

  function active(mode, labelMode, litOnly) {
    return mode === 'atlas' && labelMode === 'auto' && !litOnly && !!(g.CLSky && g.CLSky.enabled && g.CLSky.enabled());
  }

  function frame(now, still, dist, W, H) {
    var T = g.CLSkyTug, s = null, on, sig, f = 0, i, k;
    try { s = T && T.state ? T.state() : null; } catch (e) { s = null; }
    on = !!(s && s.on && s.key);
    sig = on ? s.key + '#' + s.n1.length : '';
    if (sig !== tugSig) {
      tugSig = sig; tugK = null; tugN = 0; f |= 1;
      if (on) {
        tugK = {}; tugK[s.key] = 2; tugN = 1;
        for (i = 0; i < s.n1.length; i++) { k = s.n1[i]; if (!tugK[k]) { tugK[k] = 1; tugN++; } }
      }
    }
    var F = g.CLSky && g.CLSky.field ? g.CLSky.field() : null, hc = null;
    try { hc = F && F.hot ? F.hot().camp : null; } catch (e) { hc = null; }
    if (hc !== hotC) { hotC = hc; pend = true; f |= 1; }
    if (on || now < morphTo) f |= 3;
    var mv = still < SETTLE || (f & 2) > 0;
    if (moving && !mv) { pend = true; f |= 1; }
    moving = mv;
    if (!selD || Math.abs(dist - selD) > ZOOM * selD || W !== selW || H !== selH) pend = true;
    cur.dist = dist; cur.W = W; cur.H = H;
    return f;
  }

  function select(cands) {
    var rs = pend, R, r2, k2, out = [], pts = [], q = 0, f = 0, d = 0, i, c;
    if (rs || !selR) selR = R0 * (low() ? LOW : 1);
    R = selR; r2 = R * R; k2 = r2 * RK * RK;
    function near(c, lim) {
      for (var j = 0; j < pts.length; j++) { var dx = pts[j].sx - c.sx, dy = pts[j].sy - c.sy; if (dx * dx + dy * dy < lim) return true; }
      return false;
    }
    function take(c, lim) { if (near(c, lim)) { d++; return; } pts.push(c); out.push(c); q++; }
    if (rs) { pend = false; selD = cur.dist; selW = cur.W; selH = cur.H; st.resel++; } else st.keep++;
    for (i = 0; i < cands.length; i++) {
      c = cands[i]; if (!c.forced) continue;
      if (c.forceType === 'guard' && !rs && moving && !c._inc) { d++; continue; }
      out.push(c); f++;
      if (c.forceType !== 'hover' && c.forceType !== 'tug') pts.push(c);
    }
    if (rs) {
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced) take(c, c._inc ? k2 : r2); }
    } else {
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced && c._inc) take(c, k2); }
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced && !c._inc) { if (moving) d++; else take(c, r2); } }
    }
    st.quota = q; st.forced = f; st.drop = d; st.sel = rs ? 'resel' : 'keep'; st.r = R;
    return out;
  }

  var v3 = null;
  function env(W, H) {
    var S = g.CLScene && g.CLScene.current, F = g.CLSky && g.CLSky.field ? g.CLSky.field() : null, I = F && F.info ? F.info() : null, T = g.THREE;
    var A = S && S.group && S.group.getObjectByName ? S.group.getObjectByName('sky-field-plane') : null, cam = S && S.camera;
    if (!S || !I || !A || !cam || !T) return null;
    if (!v3) v3 = new T.Vector3();
    A.updateWorldMatrix(true, false);
    return { S: S, I: I, polar: function (r, th) {
      v3.set(Math.sin(th) * r / I.R, Math.cos(th) * r / I.R, 0).applyMatrix4(A.matrixWorld).project(cam);
      return v3.z > 1 || v3.z < -1 ? null : [(v3.x * 0.5 + 0.5) * W, (-v3.y * 0.5 + 0.5) * H];
    } };
  }
  function tables(e) {
    if (tab && tab.I === e.I) return tab;
    var sec = {}, all = [], grp = {}, rank = {}, cps = e.S.camps ? e.S.camps() : [];
    e.I.sectors.forEach(function (s) { sec[s.name] = s; });
    cps.forEach(function (cp) {
      var s = sec[cp.name], ms = cp.members || [];
      ms.forEach(function (m, i) {
        var n = e.S.nodeOf ? e.S.nodeOf('c:' + m) : null; if (!n || grp[m]) return;
        grp[m] = { i: i, size: ms.length, core: !!(s && s.core), field: !!(s && s.field), camp: cp.name };
        all.push({ m: m, imp: +(n.data && n.data.importance) || 0, w: +n.w || 0 });
      });
    });
    all.sort(function (a, b) { return b.imp - a.imp || b.w - a.w || (a.m < b.m ? -1 : 1); });
    all.forEach(function (x, i) { rank[x.m] = i; });
    tab = { I: e.I, grp: grp, rank: rank };
    return tab;
  }
  function baseN(gi) { return gi.field ? (gi.size >= 12 ? 1 : 0) : gi.size >= 40 ? 3 : gi.size >= 12 ? 2 : gi.size >= 2 ? 1 : 0; }
  function rpxOf(e) { var a = e.polar(e.I.R, Math.PI / 2), b = e.polar(e.I.R, -Math.PI / 2); return a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) / 2 : RPX0; }
  function mkPlan(e, t) {
    var r = rpxOf(e);
    var f = Math.min(4, r / RPX0), K = Math.max(KMIN, Math.min(KMAX, Math.round(r / KPX))), tier = {}, m, gi, N, v, ls = [];
    for (m in t.grp) {
      gi = t.grp[m];
      N = Math.round(baseN(gi) * f);
      if (hotC && gi.camp === hotC) N = Math.min(gi.size, N + HOT);
      v = gi.core && gi.i < CORE ? 0 : t.rank[m] < K ? 1 : gi.i < N ? 2 : -1;
      tier[m] = v; if (v >= 0 && !(hotC && gi.camp === hotC)) ls.push([v, t.rank[m], m]);
    }
    var cap = Math.max(6, Math.round((discA || Math.PI * r * r) / CELL));
    if (ls.length > cap) { ls.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; }); for (v = cap; v < ls.length; v++) tier[ls[v][2]] = -1; }
    return { t: t, tier: tier, K: K, KF: Math.max(8, K * KF), rpx: Math.round(r), hot: hotC, cap: cap };
  }
  function mkDisc(e) {
    var p = [], i, q, ar = 0, out = [];
    for (i = 0; i < 32; i++) { q = e.polar(e.I.R, i * Math.PI / 16); if (!q) return null; p.push(q); }
    for (i = 0; i < 32; i++) { q = p[(i + 1) % 32]; ar += p[i][0] * q[1] - q[0] * p[i][1]; }
    var sg = ar > 0 ? 1 : -1; discA = Math.abs(ar) / 2;
    for (i = 0; i < 32; i++) {
      q = p[(i + 1) % 32]; var ex = q[0] - p[i][0], ey = q[1] - p[i][1], L = Math.hypot(ex, ey) || 1;
      out.push([p[i][0], p[i][1], -ey / L * sg, ex / L * sg]);
    }
    return out;
  }
  function prep(W, H) {
    var e = env(W, H); if (!e) { plan = null; disc = null; discA = 0; return; }
    disc = mkDisc(e);
    var t = tables(e);
    if (plan && Math.abs(rpxOf(e) - plan.rpx) > ZOOM * plan.rpx + 1) pend = true;
    if (pend || !plan || plan.t !== t) plan = mkPlan(e, t);
  }
  function nm(n) { return n && n.kind === 'char' && n.key ? n.key.slice(2) : null; }
  function guard(n) { var m = nm(n), v = plan && m ? plan.tier[m] : null; return v == null ? -1 : v; }
  function fill(n) { var m = nm(n), r = plan && m ? plan.t.rank[m] : null; return r == null || r < plan.KF; }
  function level(n) {
    var m = nm(n), gi = tab && m ? tab.grp[m] : null; if (!gi) return '';
    return (gi.core && gi.i < CORE) || tab.rank[m] < LVA ? 'a' : gi.i < baseN(gi) ? 'b' : 'c';
  }
  function inDisc(x, y, w, h) {
    if (!disc) return true;
    var xs = [x, x + w, x, x + w, x + w / 2], ys = [y, y, y + h, y + h, y + h / 2];
    for (var i = 0; i < disc.length; i++) {
      var D = disc[i];
      for (var k = 0; k < 5; k++) if ((xs[k] - D[0]) * D[2] + (ys[k] - D[1]) * D[3] < (k < 4 ? -EDGE : 0)) return false;
    }
    return true;
  }

  g.CLSkyLabels = {
    prep: prep,
    guard: guard,
    fill: fill,
    level: level,
    inDisc: inDisc,
    planned: function () { return !!plan; },
    rpx: function () { return plan ? plan.rpx : 0; },
    active: active,
    frame: frame,
    select: select,
    tug: function () { return tugK; },
    motion: function () { return moving; },
    low: low,
    reset: function (now) { pend = true; morphTo = (+now || 0) + MORPH; },
    resel: function () { pend = true; },
    stats: function () {
      var o = {}, k;
      for (k in st) o[k] = st[k];
      o.moving = moving; o.tug = tugN; o.R0 = R0; o.RK = RK; o.settle = SETTLE;
      o.guards = {}; if (plan) { for (k in plan.tier) if (plan.tier[k] >= 0) o.guards[k] = plan.tier[k]; o.K = plan.K; o.KF = plan.KF; o.rpx = plan.rpx; o.hot = plan.hot; o.cap = plan.cap; }
      return o;
    }
  };
})(window);
