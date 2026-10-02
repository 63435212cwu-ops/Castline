/*!
 * @role component
 * @owns js/sky/sky-tug.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 星座星体牵引（Q1.1 输入仲裁 · Q1.2 局部力导向）：window 捕获阶段判星，slop 内松手 = 点击，越过 = 牵引；拖动星追指针射线与抬升面之交
 * （L·tanh 软限位），一跳 / 二跳按关系保形跟随，rep·R 内非邻居被推开；松手回弹，全睡写一次 setTug(null)。
 */
(function (g) {
  'use strict';
  var doc = g.document, BC = doc.body.classList, TK = g.CLSkyTokens, X3 = g.THREE;
  if (!TK || !TK.TUG || !X3) return;
  /* Keep the spring alive until the residual screen offset is sub-pixel; the
     old 0.4 world-unit cutoff stopped writing too early on large books, so
     labels/fibres could remain 1–2 px away while the engine already said idle. */
  var TU = TK.TUG, SP = TK.SPRING, CAP = 3, SLP = 0.1, PH = ['idle', 'drag', 'back'];
  var hk, adj, adjR, rc, P, D, TG, G0, rC, rP, ph = 0, B = [], BK = {}, cand = [], N1 = [], N2 = [], tPh = 0, zb, eat, hotOn, fns = [], ppu = 1, rad, lowG;
  var st = { grabs: 0, clicks: 0, settle: 0, stepMs: 0, subSteps: 0 }, V1 = V(), V2 = V(), V3 = V(), F = V(), A = V(), NL = V(), VD = V(), SB = { h: V(), o: V() };
  var M4 = new X3.Matrix4(), Mi = new X3.Matrix4();

  function V() { return new X3.Vector3(); }
  function O() { return Object.create(null); }
  function scene() { return g.CLScene && CLScene.current || null; }
  function book() { return g.CLApp && CLApp.graph(); }
  function cv(S) { return S.renderer.domElement; }
  function nodes(S) { return S.core().nodes; }
  function live(n) { return !!n && n.kind === 'char' && n.render !== false && n.g.visible; }
  function home(n, o) { o.copy(n.g.position); return n.tugO ? o.sub(n.tugO) : o; }   /* 去掉宿主已叠的位移 */
  function emit(t, k) { fns.slice().forEach(function (f) { try { f({ type: t, key: k, name: k.slice(2) }); } catch (_) {} }); }
  function ready(S) { var r = S && CLSky.enabled() && BC.contains('sky-shell') && !BC.contains('sky-compass-on') && !BC.contains('sky-plot-on') && S.rimInfo(); return !!(r && r.mode === 'sky'); }
  function rect(S, f) { if (f || !rc) rc = cv(S).getBoundingClientRect(); return rc; }
  function hit(S, x, y) {
    var H = TU.hitPx, R = rect(S), ns = nodes(S), best = null, bd = 1e9, i, n, dx, dy, d, r;
    M4.multiplyMatrices(S.camera.projectionMatrix, S.camera.matrixWorldInverse).multiply(S.group.matrixWorld);
    for (i = 0; i < ns.length; i++) {
      n = ns[i];
      if (!live(n) || !(n.alpha > 0.3) || Math.abs(V1.copy(n.g.position).applyMatrix4(M4).z) > 1) continue;
      dx = R.left + (V1.x + 1) / 2 * R.width - x; dy = R.top + (1 - V1.y) / 2 * R.height - y; d = dx * dx + dy * dy; r = H[1] - (H[1] - H[0]) * Math.min(1, (n.tier || 0) / 4);
      if (d <= r * r && d < bd) { bd = d; best = { n: n, x: x + dx, y: y + dy, r: r }; }
    }
    return best;
  }
  function hot(on) { if (on !== hotOn) BC.toggle('sky-tug-hot', hotOn = on); }
  function rot(on) {
    var c = (scene() || {}).controls;
    if (on) { if (rC) rC.enableRotate = rP; rC = null; } else if (c && !rC) { rC = c; rP = c.enableRotate; c.enableRotate = false; }
  }
  function hook(S) { if (S && S !== hk && S.registerFrameHook) { hk = S; S.registerFrameHook(frame); } }
  function adjOf() {   /* 与场景同一份视图图谱 */
    var v = CLApp.atlas.skyView(), R = v && v.relations || [];
    function put(a, b, s) { var m = adj[a] || (adj[a] = O()); if (!(m[b] >= s)) m[b] = s; }
    if (adj && adjR === R) return adj;
    adj = O(); adjR = R;
    R.forEach(function (r) { var s = +r.strength; s = s > 0 ? Math.min(1, s) : 0.5; if (r.a && r.b && r.a !== r.b) { put(r.a, r.b, s); put(r.b, r.a, s); } });
    return adj;
  }
  function byS(a, b) { return b.s - a.s || (b.n.w || 0) - (a.n.w || 0); }
  function kOf(s, a, b) { var d = a.distanceTo(b) / rad; return 0.08 + 0.67 * s / (1 + d * d / 0.16); }
  function body(n, r, p, c) {
    var b = BK[n.key] || (BK[n.key] = B[B.length] = { k: n.key, n: n, o: V(), v: V(), h: V() });
    b.r = r; b.p = p; b.c = c || 0; b.q = 0; home(n, b.h);
    return b;
  }
  function gmat(S) { var q = S.group; q.updateMatrix(); M4.copy(q.matrix); if (q.parent) M4.premultiply(q.parent.matrixWorld); Mi.copy(M4).invert(); }
  function amp(b) { return (b.o.length() + b.v.length() / SP.back.w) * ppu; }

  function grab() {
    var S = scene(), n = P.h.n, J = adjOf(), X = n.key.slice(2), f = S.rimInfo(), l1 = [], l2 = [], bs = O(), in1 = O(), k, q = f.pitch;
    P.drag = true; G0 = book(); rad = f.R || 380; N1 = []; N2 = [];
    P.camTarget = P.camTarget || (S && S.controls && S.controls.target ? S.controls.target.clone() : null);
    P.camPos = P.camPos || (S && S.camera ? S.camera.position.clone() : null);
    gmat(S); NL.set(0, Math.sin(q), Math.cos(q)); if (V1.copy(S.camera.position).applyMatrix4(Mi).sub(home(n, V2)).dot(NL) < 0) NL.negate();
    lowG = TK.tierOf(S.core().getDegrade()) === 'low';
    B.forEach(function (b) { b.r = 3; b.p = null; });
    for (k in J[X]) if (live(q = S.nodeOf('c:' + k))) l1.push({ n: q, nm: k, s: J[X][k] });
    l1 = l1.sort(byS).slice(0, TU.n1); in1[X] = 1; l1.forEach(function (o) { in1[o.nm] = 1; });
    if (!lowG) l1.forEach(function (o, j) { var m = J[o.nm], v, y; for (y in m) { v = o.s * m[y]; if (!in1[y] && !(bs[y] && bs[y].s >= v)) bs[y] = { s: v, s2: m[y], p: j }; } });
    for (k in bs) if (live(q = S.nodeOf('c:' + k))) { bs[k].n = q; l2.push(bs[k]); }
    D = body(n, 0);
    l1.forEach(function (o) { o.b = body(o.n, 1, D); o.b.c = kOf(o.s, o.b.h, D.h); N1.push(o.b.k); });
    l2.sort(byS).slice(0, TU.n2).forEach(function (o) { var p = l1[o.p].b; N2.push(body(o.n, 2, p, 0.55 * kOf(o.s2, home(o.n, V3), p.h)).k); });
    cand = lowG ? [] : nodes(S).filter(function (o) { return o !== n && o.kind === 'char' && !in1[o.key.slice(2)]; });
    ph = 1; tPh = 0; TG = null; st.grabs++;
    try { doc.body.setPointerCapture(P.id); P.cap = true; } catch (_) {}
    hot(false); BC.add('sky-tug-grabbing'); emit('grab', D.k);
  }
  function release() {
    if (ph !== 1) return;
    var a = 0;
    ph = 2; tPh = 0; TG = null; BC.remove('sky-tug-grabbing');
    B.forEach(function (b) { a = Math.max(a, amp(b)); });
    zb = Math.min(0.8, Math.max(SP.back.z, Math.log(Math.max(1, a * 1.08 / CAP)) / (SP.back.w * 0.98)));
    emit('release', D.k);
    if (TK.reduced()) sleep(scene());
  }
  function sleep(S, x) {
    var k = D.k, p = ph;
    if (x && P) endPress();
    if (S && S.setTug) S.setTug(null);
    B = []; BK = {}; cand = []; N1 = []; N2 = []; D = TG = null; ph = 0; st.settle = +tPh.toFixed(3); tPh = 0; BC.remove('sky-tug-grabbing');
    if (p === 1) emit('release', k);
    emit('sleep', k);
  }
  function endPress() { if (P && P.cap) try { doc.body.releasePointerCapture(P.id); } catch (_) {} P = null; rot(true); BC.remove('sky-tug-grabbing'); }

  /* 状态切换是一次事务：拖动中的星不能把 tug 位移带进剧情 / 罗盘层。
     这里比等下一帧 ready() 失败更早清空宿主偏移、释放 pointer capture，
     这样拖动后立即切换显示不会留下半秒的“幽灵星”或卡住镜头旋转。 */
  function abort() {
    var S = scene(), k = D && D.k;
    if (!ph && !P) return;
    if (P) { P.dead = true; endPress(); }
    hot(false);
    if (S && S.setTug) S.setTug(null);
    if (k) emit('sleep', k);
    B = []; BK = {}; cand = []; N1 = []; N2 = []; D = TG = null; ph = 0; tPh = 0;
    BC.remove('sky-tug-grabbing');
  }

  function target(S) {   /* 射线 → 抬升面交点，盘面内 L·tanh 软限位 */
    var R = rect(S), lift = TU.lift * rad, L = TU.maxR * rad, x = (P.x - P.gx - R.left) / R.width * 2 - 1, y = 1 - (P.y - P.gy - R.top) / R.height * 2, dn, t;
    V1.set(x, y, -1).unproject(S.camera).applyMatrix4(Mi); V2.set(x, y, 1).unproject(S.camera).applyMatrix4(Mi).sub(V1);
    V3.copy(NL).multiplyScalar(lift).add(D.h); dn = V2.dot(NL); t = F.copy(V3).sub(V1).dot(NL) / dn;
    if (Math.abs(dn) < 0.06 * V2.length() || !(t > 0)) return;
    t = F.copy(V1).addScaledVector(V2, t).sub(V3).length();
    if (t > 1e-6) F.multiplyScalar(L * Math.tanh(t / L) / t);
    TG = (TG || V()).copy(NL).multiplyScalar(lift).add(F);
  }
  function push(b, rr) {   /* 视平面内距离 r → 沿盘面推开，边上值与斜率为 0 */
    var r = F.copy(b.h).add(b.o).sub(D.h).sub(D.o).addScaledVector(VD, -F.dot(VD)).length();
    if (r >= rr) { F.set(0, 0, 0); return r; }
    if (F.addScaledVector(NL, -F.dot(NL)).lengthSq() < 1e-6) F.set(1, 0, 0);
    r /= rr; F.setLength(1.1 * rr * (1 - r * r) * (1 - r * r));
    return r * rr;
  }
  function frame(dt, _a, _b, _c, dg) {
    if (!ph) return;
    var t0 = g.performance.now(), S = scene(), rr = TU.rep * rad, map = {}, c = S && S.camera, low, red, k, h, i;
    if (S !== hk || S.nodeOf(D.k) !== D.n || book() !== G0) return sleep(hk, 1);
    if (ph === 1 && P && P.camTarget && S.controls && S.controls.target) {
      S.controls.target.copy(P.camTarget);
      if (P.camPos && S.camera) { S.camera.position.copy(P.camPos); S.camera.lookAt(P.camTarget); S.camera.updateMatrixWorld(true); }
    }
    if (ph === 1 && !ready(S)) { drop(); if (!ph) return; }   /* 换态 = 松手 */
    dt = Math.min(0.05, Math.max(0, +dt || 0)); tPh += dt;
    gmat(S); c.updateMatrixWorld(); red = TK.reduced(); low = lowG || TK.tierOf(dg) === 'low';
    B.forEach(function (b) { home(b.n, b.h); });
    V1.copy(D.h).add(D.o).sub(V2.copy(c.position).applyMatrix4(Mi)); VD.copy(V1).normalize(); ppu = rect(S).height / 2 / Math.tan(c.fov * Math.PI / 360) / Math.max(1, V1.length());
    if (ph === 2 && red) return sleep(S);
    if (ph === 1) {
      if (P && !P.dead) target(S);
      if (!low) cand.forEach(function (n) { if (!BK[n.key] && live(n)) { home(n, SB.h); if (push(SB, rr * 1.05) < rr * 1.05) body(n, 3); } });
    }
    k = Math.max(1, Math.ceil(dt * 120 - 1e-6)); h = dt / k;
    for (i = 0; i < k; i++) B.forEach(function (b) {
      var s = ph === 2 ? SP.back : b.r ? SP.pull : SP.follow, z = red || ph === 2 && b.q ? 1 : ph === 2 ? zb : s.z, y;
      A.set(0, 0, 0);
      if (ph === 1 && !b.r) A.copy(TG || b.o);
      else if (ph === 1) { y = b.r > 1 && !low ? Math.min(1, Math.max(0, push(b, rr) / rr - 1) / 0.3) : 1; if (b.p) A.copy(b.p.o).multiplyScalar(b.c * y); if (y < 1) A.add(F); }
      b.v.addScaledVector(A.sub(b.o).multiplyScalar(s.w * s.w).addScaledVector(b.v, -2 * z * s.w), h); b.o.addScaledVector(b.v, h);
    });
    B = B.filter(function (b) {
      var a = amp(b), y;
      if (ph === 2 && a < CAP) b.q = 1;
      y = ph === 2 ? a >= SLP : b.r < 3 || a >= SLP || push(b, rr * 1.3) < rr * 1.3;
      if (y) map[b.k] = b.o; else delete BK[b.k];
      return y;
    });
    if (!B.length) return sleep(S);
    if (S.setTug) S.setTug(map);   /* 宿主下一帧才读 */
    st.subSteps = k; st.stepMs = +(g.performance.now() - t0).toFixed(3);
  }

  /* 输入仲裁：window 捕获阶段 */
  function onDown(e) {
    var S = scene(), t = e.pointerType === 'touch', x = e.clientX, y = e.clientY, h, rv, q;
    eat = 0;
    if (P) { q = !P.dead && (t || P.touch); release(); endPress(); if (q) return; }   /* 第二指 = 捏合，放行 */
    if (e.isPrimary === false || !t && (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) || !ready(S) || e.target !== cv(S)) return;
    try { rv = CLSkyDeep.stats().reveal; } catch (_) {}
    if (rv && (rv.playing || rv.staged) || !(h = hit(S, x, y, rect(S, true)))) return;
    hook(S); rot(false); hot(false);
    P = { id: e.pointerId, touch: t, x0: x, y0: y, x: x, y: y, h: h, gx: x - h.x, gy: y - h.y,
      camTarget: S && S.controls && S.controls.target ? S.controls.target.clone() : null,
      camPos: S && S.camera ? S.camera.position.clone() : null };
    /* Claim the camera-free drag transaction before the slop threshold so
       aim/drift cannot move the baseline while the user is deciding whether
       this is a click or a drag. */
    BC.add('sky-tug-grabbing');
  }
  function onMove(e) {
    var S = scene();
    if (!P) { if (e.pointerType !== 'touch' && !e.buttons) hot(!!(S && e.target === cv(S) && ready(S) && hit(S, e.clientX, e.clientY))); return; }
    if (e.pointerId !== P.id || P.dead) return;
    P.x = e.clientX; P.y = e.clientY;
    if (!P.touch && !e.buttons) return onUp(e);
    if (!P.drag) e.stopPropagation();   /* 待定中不给 scene 判拖 */
    if (!P.drag && Math.hypot(P.x - P.x0, P.y - P.y0) > TU.slopPx[P.touch ? 'touch' : 'mouse']) grab();
  }
  function onUp(e) { if (P && e.pointerId === P.id) { if (P.drag) { release(); eat = e.type === 'pointerup' ? e.timeStamp : 0; } else st.clicks++; endPress(); } }
  function drop() { release(); if (P) { P.dead = true; endPress(); } }

  [['pointerdown', onDown], ['pointermove', onMove], ['pointerup', onUp], ['pointercancel', onUp], ['click', function (e) {
    if (eat && e.timeStamp - eat < 600) { eat = 0; e.stopImmediatePropagation(); e.preventDefault(); }
  }]].forEach(function (p) { g.addEventListener(p[0], p[1], true); });
  g.addEventListener('blur', drop); g.addEventListener('resize', function () { rc = null; drop(); });
  doc.addEventListener('cl:sky-plot', abort, false);
  doc.addEventListener('cl:sky-compass', abort, false);
  doc.addEventListener('cl:graph-loading', abort, false);

  g.CLSkyTug = {
    enabled: function () { return ready(scene()); },
    state: function () {
      var d = D;
      return { on: ph > 0, phase: PH[ph], key: d ? d.k : null, name: d ? d.k.slice(2) : null, home: d ? d.h.clone() : null, off: d ? d.o.clone() : null,
        tension: d ? Math.min(1, d.o.length() / TU.maxR / rad) : 0, n1: N1.slice(), n2: N2.slice(), t: +tPh.toFixed(3) };
    },
    on: function (f) { fns.push(f); return function () { fns = fns.filter(function (x) { return x !== f; }); }; },
    stats: function () { var o = { bodies: B.length, sleeping: !ph, phase: PH[ph] }, k; for (k in st) o[k] = st[k]; return o; },
    pick: function (x, y) { var S = scene(), h = ready(S) && hit(S, x, y, rect(S, true)); return h ? { key: h.n.key, x: h.x, y: h.y, r: h.r } : null; },
    release: drop, cancel: abort
  };
})(window);
