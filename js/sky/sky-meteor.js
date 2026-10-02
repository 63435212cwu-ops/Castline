/*!
 * @role meteor
 * @owns js/sky/sky-meteor.js
 * @budget drawcalls=1 points=0 vertices=4 rtpx=0 passes=0
 * @contract deep-sky/3
 * Q9.3 背景流星：同屏一条、令牌间隔，深空方向投影细丝；禁发态立即隐藏。
 * 每帧复核图谱外接圆、团名/星点与HUD面板。stats/_fire/_at为验收探针。
 */
(function (g) {
  'use strict';
  var doc = g.document, D2R = Math.PI / 180, NR = 24, X = g.CLSkyMeteorGLSL || {}, lcg = X.lcg, segDist = X.segDist, segBox = X.segBox, len = X.len;
  var PANELS = '#skyHud > *:not([hidden]), .sky-lab:not([hidden])', OFF = ['sky-plot-on', 'sky-compass-on', 'sky-home-on', 'sky-loader-on'];
  var S = null, T = null, TH = null, mesh = null, U = null, unhook = null;
  var rnd = null, acc = 0, wait = 0, blocked = true, fly = null, pin = null, why = 'init', lastCalm = false, lastDeg = 0;
  var nFired = 0, nSkip = 0, stamps = [], v, fwd, mP, mW, buf, RING = { c: [0, 0], r: 0, rx: 0 }, PA = [0, 0], PB = [0, 0], P = [];

  function M() { return T.METEOR; }
  function lerp(r, k) { return r[0] + (r[1] - r[0]) * k; }
  function sstep(a, b, x) { var t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
  function r1(x) { return Math.round(x * 10) / 10; }
  function sky() { return g.CLSky && CLSky.enabled && CLSky.enabled(); }
  function W() { return g.innerWidth || 1; }
  function H() { return g.innerHeight || 1; }
  function far() { return S.camera.far * 0.8; }
  function toXY(o, i) { o[i] = (v.x * 0.5 + 0.5) * W(); o[i + 1] = (-v.y * 0.5 + 0.5) * H(); return o; }
  /* 天球方向 → 屏幕 CSS px（在镜头背后或太斜 → null） */
  function dirXY(d, o) {
    if (d.dot(fwd) < 0.08) return null;
    v.copy(d).multiplyScalar(far()).add(S.camera.position).project(S.camera);
    return toXY(o, 0);
  }
  function unproj(x, y) { return new TH.Vector3(x / W() * 2 - 1, 1 - y / H() * 2, 0.5).unproject(S.camera).sub(S.camera.position).normalize(); }
  function cam() { S.camera.updateMatrixWorld(); S.camera.getWorldDirection(fwd); }
  /* 图谱外接圆（屏幕 CSS px）：星域外缘（与 sky-field 同锚：group · 俯仰 −pitch · 半径 R）投影的包围盒中心 + 最远距离 */
  function rim() {
    var info = S.skyInfo ? S.skyInfo() : null, i, a, x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, r = 0, cx, cy, cf;
    if (!info || !S.group) return null;
    cf = S.camera.position.dot(fwd);
    mP.makeRotationX(-(info.pitch || 0)); mW.copy(S.group.matrixWorld).multiply(mP);
    for (i = 0; i < NR; i++) {
      a = i / NR * Math.PI * 2;
      v.set(Math.sin(a) * info.R, Math.cos(a) * info.R, 0).applyMatrix4(mW);
      if (v.dot(fwd) - cf < 1) return null;
      v.project(S.camera); toXY(P, i * 2);
      x0 = Math.min(x0, P[i * 2]); x1 = Math.max(x1, P[i * 2]); y0 = Math.min(y0, P[i * 2 + 1]); y1 = Math.max(y1, P[i * 2 + 1]);
    }
    cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
    for (i = 0; i < NR; i++) r = Math.max(r, len(cx, cy, P[i * 2], P[i * 2 + 1]));
    RING.c[0] = cx; RING.c[1] = cy; RING.r = r;
    return RING;
  }
  /* 团名框角与星点离圆心的最远距离（起飞时量，折成比例 q） */
  function reach(c) {
    var f = CLSky.field ? CLSky.field() : null, nm = f && f.names ? f.names() : [], G = g.CLApp && CLApp.graph ? CLApp.graph() : null,
      cs = G && G.characters || [], m = 0, i, b, n, q = [0, 0];
    for (i = 0; i < nm.length; i++) {
      if (!nm[i] || !nm[i].visible || !(b = nm[i].box)) continue;
      m = Math.max(m, len(c[0], c[1], b[0], b[1]), len(c[0], c[1], b[2], b[1]), len(c[0], c[1], b[0], b[3]), len(c[0], c[1], b[2], b[3]));
    }
    for (i = 0; i < cs.length && S.nodeOf; i++) {
      n = S.nodeOf('c:' + cs[i].name);
      if (!n || !n.g) continue;
      n.g.getWorldPosition(v); v.project(S.camera);
      if (v.z < 1) { toXY(q, 0); m = Math.max(m, len(c[0], c[1], q[0], q[1])); }
    }
    return m;
  }
  /* 轨迹（CSS px）：大致向下划落（偏竖直 tilt°），全程在屏内、离外接圆 ≥ 余量、不碰界面面板 */
  function panels() {
    var e = M().px.edge, el = doc.querySelectorAll(PANELS), bx = [], i, b;
    for (i = 0; i < el.length; i++) { b = el[i].getBoundingClientRect(); if (b.width > 1 && b.height > 1) bx.push([b.left - e, b.top - e, b.right + e, b.bottom + e]); }
    return bx;
  }
  function pick(ring) {
    var m = M(), w = W(), h = H(), e = m.px.edge, diag = Math.sqrt(w * w + h * h), bx = panels(), i, j, L, an, x0, y0, x1, y1;
    for (i = 0; i < 96; i++) {
      L = diag * lerp(m.len, rnd()); an = lerp(m.tilt, rnd()) * D2R * (rnd() < 0.5 ? -1 : 1);
      x0 = e + rnd() * (w - 2 * e); y0 = e + rnd() * (h - 2 * e);
      x1 = x0 + Math.sin(an) * L; y1 = y0 + Math.cos(an) * L;
      if (x1 < e || x1 > w - e || y1 < e || y1 > h - e || segDist(ring.c[0], ring.c[1], x0, y0, x1, y1) < ring.rx) continue;
      for (j = 0; j < bx.length && !segBox(x0, y0, x1, y1, bx[j]); j++) {}
      if (j === bx.length) return [x0, y0, x1, y1];
    }
    return null;
  }

  /* 门：每帧查类名 / 档位 / 减弱动效；起飞与飞行中再查深空态 · 揭幕 · 天球 */
  function gate(calm, degrade) {
    var b = doc.body && doc.body.classList, i;
    if (!b || !sky()) return 'shell';
    for (i = 0; i < OFF.length; i++) if (b.contains(OFF[i])) return OFF[i];
    if (calm) return 'calm';
    if (T.tierOf(degrade | 0) === 'low') return 'low';
    return T.reduced() ? 'reduced' : '';
  }
  function deepGate() {
    var Dp = g.CLSkyDeep, st;
    if (!Dp || !Dp.enabled || !Dp.enabled()) return 'deep';
    st = Dp.stats();
    if (st.mode !== 'constellation') return 'mode';
    if (st.tier === 'low') return 'low';
    if (st.reveal && (st.reveal.playing || st.reveal.staged)) return 'reveal';
    return !st.cosmos || st.cosmos.state !== 'show' || st.cosmos.alpha < 0.97 ? 'cosmos' : '';
  }

  function end(r) { fly = null; why = r; if (mesh) mesh.visible = false; }
  function launch(force) {
    if (!mesh || fly) return false;
    var m = M(), w = force ? '' : deepGate(), ring, q, p;
    if (w) { why = w; acc = Math.min(acc, wait - m.settle); return false; }
    cam(); ring = rim();
    if (!ring || !(ring.r > 1)) { why = 'rim'; acc = wait - m.retry; return false; }
    q = Math.max(1, reach(ring.c) / ring.r); ring.rx = ring.r * q + m.px.ring;
    p = pick(ring);
    if (!p) { nSkip++; why = 'room'; acc = wait - 2 * m.retry; return false; }
    fly = { a: unproj(p[0], p[1]), b: unproj(p[2], p[3]), t: 0, dur: lerp(m.dur, rnd()), q: q, clear: 0, seg: null, ring: null, u: null };
    U.uA.value.copy(fly.a); U.uB.value.copy(fly.b);
    acc = 0; wait = lerp(m.gap, rnd()); nFired++; why = '';
    stamps.push(Math.round(g.performance.now())); if (stamps.length > 16) stamps.shift();
    step(0);
    return true;
  }
  /* 飞行一帧：两端重投影（跟着天走），离圆 < 2 px 即熄灭；头近匀速略减速，亮度快起缓落 */
  function step(dt) {
    var m = M(), f = fly, k, a, b, ring, kx, hk, s0, Lpx, bx, i;
    f.t += dt; k = pin != null ? pin : f.t / f.dur;
    if (k >= 1) { end('done'); return; }
    cam(); a = dirXY(f.a, PA); b = a && dirXY(f.b, PB); ring = b && rim();
    if (!ring) { end('behind'); return; }
    ring.rx = Math.max(ring.r, reach(ring.c)) + m.px.ring;
    f.clear = segDist(ring.c[0], ring.c[1], a[0], a[1], b[0], b[1]) - ring.rx;
    if (f.clear < 2) { end('ring'); return; }
    bx = panels();
    for (i = 0; i < bx.length; i++) if (segBox(a[0], a[1], b[0], b[1], bx[i])) { end('panel'); return; }
    S.renderer.getDrawingBufferSize(buf); kx = buf.x / W();
    hk = k * (1.12 - 0.12 * k); s0 = Math.max(0, hk - m.tailRatio); Lpx = len(a[0], a[1], b[0], b[1]) * kx;
    f.seg = [a[0], a[1], b[0], b[1]]; f.ring = [ring.c[0], ring.c[1], ring.r, ring.rx]; f.u = [s0, hk];
    U.uSeg.value.set(s0, hk); U.uRes.value.copy(buf); U.uFar.value = far();
    U.uL.value.set(Math.max(1, m.tailRatio * Lpx), hk * Lpx, Math.max(2 * kx, 0.12 * Lpx));
    U.uW.value.set(m.px.core * kx, m.px.halo * kx, m.px.head * kx, m.alpha * sstep(0, 0.14, k) * (1 - sstep(0.52, 1, k)));
    U.uPad.value = Math.max(m.px.head * 4, m.px.halo * 3.2) * kx;
    mesh.visible = true;
  }

  function frame(dt, tAcc, tAnim, calm, degrade) {
    if (!mesh) return;
    lastCalm = !!calm; lastDeg = degrade | 0; dt = dt > 0 ? dt : 0;
    var w = gate(calm, degrade);
    if (w) { blocked = true; why = w; if (fly) end(w); return; }
    if (blocked) { blocked = false; acc = Math.min(acc, wait - M().settle); }
    if (fly) { w = deepGate(); if (w) { blocked = true; end(w); } else step(dt); return; }
    acc += dt;
    if (acc >= wait) launch(false);
  }

  function build() {
    var geo = new TH.BufferGeometry(), m = M(), V2 = TH.Vector2, V3 = TH.Vector3;
    geo.setAttribute('position', new TH.Float32BufferAttribute([0, -1, 0, 0, 1, 0, 1, -1, 0, 1, 1, 0], 3));
    geo.setIndex([0, 2, 1, 1, 2, 3]);
    U = { uA: { value: new V3() }, uB: { value: new V3() }, uFar: { value: 1 }, uRes: { value: new V2(1, 1) }, uSeg: { value: new V2() }, uPad: { value: 8 },
      uC0: { value: new TH.Color(m.headColor) }, uC1: { value: new TH.Color(m.tailColor) }, uW: { value: new TH.Vector4(1, 2, 1, 0) }, uL: { value: new V3(1, 0, 1) } };
    mesh = new TH.Mesh(geo, new TH.ShaderMaterial({ uniforms: U, vertexShader: X.VS, fragmentShader: X.FS, transparent: false, depthTest: false, depthWrite: false,
      blending: TH.AdditiveBlending, premultipliedAlpha: true, side: TH.DoubleSide }));
    mesh.name = 'sky-meteor'; mesh.frustumCulled = false; mesh.matrixAutoUpdate = false; mesh.renderOrder = -283; mesh.visible = false;
    S.scene.add(mesh);
  }
  function free() {
    if (unhook) { try { unhook(); } catch (e) {} unhook = null; }
    if (mesh) { if (mesh.parent) mesh.parent.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
    mesh = null; fly = null; S = null;
  }
  function ensure() {
    var s = g.CLScene && CLScene.current;
    T = g.CLSkyTokens; TH = g.THREE;
    if (!sky() || !s || !s.scene || !s.camera || !s.renderer || !s.registerFrameHook || !T || !T.METEOR || !TH || !lcg) return false;
    if (S !== s || !mesh) {
      free(); S = s;
      v = new TH.Vector3(); fwd = new TH.Vector3(); mP = new TH.Matrix4(); mW = new TH.Matrix4(); buf = new TH.Vector2();
      build(); unhook = s.registerFrameHook(frame); if (!rnd) reset();
    }
    return true;
  }
  /* 换书：新种子、重新计时（第一条也在 gap 之后） */
  function reset() {
    var G = g.CLApp && CLApp.graph ? CLApp.graph() : null;
    rnd = lcg(X.seedOf(G && G.title)); acc = 0; wait = lerp(M().gap, rnd()); blocked = true; pin = null; end('book');
  }

  doc.addEventListener('cl:graph-ready', function () { if (ensure()) reset(); }, false);
  g.addEventListener('resize', function () { if (fly) end('resize'); }, false);

  g.CLSkyMeteor = {
    /* seg 轨迹两端 · u [尾, 头] 比例 · ring [cx, cy, r, 放大 r]（CSS px）· clear 余量 · wait 距下一条 s */
    stats: function () {
      var f = fly, gp = [], i, a = function (x) { return x ? x.map(r1) : null; };
      for (i = 1; i < stamps.length; i++) gp.push(r1((stamps[i] - stamps[i - 1]) / 1000));
      return { installed: !!mesh, visible: !!(mesh && mesh.visible), flying: !!f, why: why, fired: nFired, skipped: nSkip, wait: r1(wait - acc),
        k: f ? +(pin != null ? pin : f.t / f.dur).toFixed(3) : null, dur: f && f.dur, q: f && f.q,
        seg: f && a(f.seg), u: f && f.u, ring: f && a(f.ring), clear: f ? r1(f.clear) : null, gaps: gp, draw: mesh && mesh.visible ? 1 : 0 };
    },
    _fire: function (force) {
      if (!ensure() || fly) return false;
      var w = force ? '' : gate(lastCalm, lastDeg);
      if (w) { why = w; return false; }
      return launch(!!force);
    },
    _at: function (k) { pin = k == null ? null : Math.max(0, Math.min(0.999, +k || 0)); return pin; },
    dispose: free
  };
})(window);
