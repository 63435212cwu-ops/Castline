/*!
 * @role component
 * @owns js/sky/sky-compass-drag.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 罗盘关系星拖拽（Q3.1）：跟手 SPRING.follow；连线伸长 = 张力（--skc-k 色 / 粗 / 辉光，虚线随 --skc-rho 拉开）；
 * 其余星沿轨道（网格沿行）让位 SPRING.pull；松手 SPRING.sat 欠阻尼回弹（速度平方阻力限过冲，小振幅转临界阻尼，≤ 1 s 入轨后睡眠）；
 * 落在晶体框内 = 涡旋缩入晶体心后 CLSky.openCompass(他)；slop 内 = 点击照旧。减弱动效：不让位、一帧到位、不吸入；low 档不让位无辉光。
 */
(function (g) {
  'use strict';
  var doc = g.document, IDLE = 0, DRAG = 1, BACK = 2, SUCK = 3;
  var hk = null, svg = null, lay = null, halo = null, ring = null, V3 = null, K = null, SP = null;
  var ph = IDLE, D = null, B = [], hooked = null, eatAt = 0, cb = null, anc = null, tick = 0, low = false;
  var stat = { drags: 0, clicks: 0, drops: 0, settle: 0 };

  function Tk() { return g.CLSkyTokens; }
  var now = g.CLSkyUtil.now, clamp = g.CLSkyUtil.clamp, mk = g.CLSkyUtil.svg;
  function f1(v) { return v.toFixed(1); }
  function xy(x, y) { return f1(x) + ' ' + f1(y); }
  function tr(x, y) { return 'translate(' + xy(x, y) + ')'; }
  function at(el, k, v) { el.setAttribute(k, v); }
  function cxy(el, A) { at(el, 'cx', f1(A[0])); at(el, 'cy', f1(A[1])); }
  function scene() { return hk && hk.scene(); }
  function inside(b, x, y) { return !!b && x >= b.left && x <= b.right && y >= b.top && y <= b.bottom; }
  function pos(st, i) { return [st.sats[i].x + B[i].ox, st.sats[i].y + B[i].oy]; }
  function css(el, k, v) { if (v == null) el.style.removeProperty(k); else el.style.setProperty(k, v); }
  function hook() { var S = scene(); if (S && S.registerFrameHook && hooked !== S) { hooked = S; S.registerFrameHook(frame); } }

  /* 晶体框 = 落点判据（每 6 帧取）；晶体组原点投影 = 吸入的心 */
  function crown(box) {
    var S = scene(); anc = null;
    /* Never reuse a bounds result from a previous frame/view.  A failed
       projection must make the current drop unarmed rather than accepting a
       stale crystal rectangle after the camera or inset changed. */
    if (box) cb = null;
    try {
      var b = box ? S.crownScreenBounds() : null, c = S.core(); if (b && b.right > b.left) cb = b;
      V3 = V3 || new g.THREE.Vector3(); S.crownAnchor().getWorldPosition(V3); V3.project(S.camera);
      if (V3.z < 1) anc = [(V3.x + 1) * c.getW() / 2, (1 - V3.y) * c.getH() / 2];
    } catch (e) {}
  }
  function heart(st) { return anc || [st.B.cx, st.B.cy]; }
  /* 连线同 placeOrbit：自晶体包围椭圆外缘径向出发 */
  function ray(E, x, y, rr) {
    var dx = x - E.cx, dy = y - E.cy, a = E.cw / 2 + 6, b = E.chh / 2 + 6, q = Math.sqrt(dx * dx / (a * a) + dy * dy / (b * b)), l = Math.hypot(dx, dy) || 1;
    if (!(q > 1)) return null;
    var r = { sx: E.cx + dx / q, sy: E.cy + dy / q, ex: x - dx / l * (rr + 4), ey: y - dy / l * (rr + 4) };
    r.L = Math.max(1, Math.hypot(r.ex - r.sx, r.ey - r.sy)); return r;
  }
  function line(r) { return r ? 'M' + xy(r.sx, r.sy) + 'L' + xy(r.ex, r.ey) : ''; }

  /* 让位：沿轨道椭圆（网格沿行）推开 ∝ (1 − d/R)² */
  function give(st, j, P, b) {
    var s = st.sats[j], R = K.yieldR, o = st.orb, dx = s.x - P[0], dy = s.y - P[1], d = Math.hypot(dx, dy), f = K.yieldPx * (1 - d / R) * (1 - d / R);
    b.tx = b.ty = 0;
    if (!s.shown || d >= R) return;
    if (!o || !s.side) { b.tx = dx >= 0 ? f : -f; return; }
    var t0 = clamp((s.y - o.cy) / o.ry, -0.99, 0.99), t1 = clamp(t0 + (dy >= 0 ? f : -f) / o.ry, -0.99, 0.99);
    b.tx = s.side * o.rx * (Math.sqrt(1 - t1 * t1) - Math.sqrt(1 - t0 * t0)); b.ty = (t1 - t0) * o.ry;
  }
  /* 回位振幅 < cap 转临界阻尼 */
  function step(b, h, sp, kq, cap) {
    var w = sp.w, z = sp.z, ex = b.ox - b.tx, ey = b.oy - b.ty, v2 = b.vx * b.vx + b.vy * b.vy;
    if (cap && ex * ex + ey * ey + v2 / (w * w * (1 - z * z)) < cap * cap) b.cap = true;
    if (cap && b.cap) { w = SP.follow.w; z = 1; kq = 0; }
    var q = kq * Math.sqrt(v2);
    b.vx += (-w * w * ex - 2 * z * w * b.vx - q * b.vx) * h; b.vy += (-w * w * ey - 2 * z * w * b.vy - q * b.vy) * h;
    b.ox += b.vx * h; b.oy += b.vy * h;
  }
  function still(b) { return Math.abs(b.ox) < 0.1 && Math.abs(b.oy) < 0.1 && Math.abs(b.vx) < 2 && Math.abs(b.vy) < 2; }

  function place(st, i) {
    var s = st.sats[i], b = B[i], me = i === D.i, p = pos(st, i), r = null;
    if (!s.shown || (!me && b.wx === b.ox && b.wy === b.oy)) return;
    b.wx = b.ox; b.wy = b.oy;
    at(s.g, 'transform', tr(p[0], p[1]) + (b.sc < 1 ? ' scale(' + b.sc.toFixed(3) + ')' : ''));
    if (!me) { if (b.d0 && st.orb) at(s.link, 'd', line(ray(st.B, p[0], p[1], s.rr))); else if (b.d0) at(s.link, 'transform', tr(b.ox, b.oy)); return; }
    if (ph !== SUCK) r = ray(st.B, p[0], p[1], s.rr);
    var d = line(r); at(s.link, 'd', d); at(halo, 'd', low ? '' : d);
    if (!r) return;
    var k = clamp((r.L - D.L0) / (K.taut * D.L0), 0, 1).toFixed(3), rho = clamp(r.L / D.L0, 1, 2.4).toFixed(3);
    if (D.k !== k) { D.k = k; css(s.link, '--skc-k', k); css(halo, '--skc-k', k); }
    if (D.rho !== rho) { D.rho = rho; css(s.link, '--skc-rho', rho); }
  }
  function decor(st) {
    var p = pos(st, D.i), A = heart(st), armed = ph === DRAG && (inside(cb, D.px, D.py) || inside(cb, p[0], p[1]));
    cxy(ring, A);
    if (armed !== D.armed) svg.classList.toggle('skc-armed', D.armed = armed);
  }

  function frame(dt, tAcc, tAnim, calm, degrade) {
    if (ph === IDLE) return;
    var st = hk.state(), j, k, S = scene();
    if (!st || !D || D.st !== st || !st.B) { reset(); return; }
    /* 罗盘入场的晶体仍可能在做最后一段镜头落定；一旦用户真正越过
       slop 开始拖星，锁住当下 target，避免拖动看起来像平移 / 误切镜头。 */
    if ((ph === DRAG || ph === SUCK) && D.camTarget && S && S.controls && S.controls.target) {
      S.controls.target.copy(D.camTarget);
      if (D.camPos && S.camera) { S.camera.position.copy(D.camPos); S.camera.lookAt(D.camTarget); S.camera.updateMatrixWorld(true); }
    }
    low = Tk().tierOf(degrade) === 'low';
    var s0 = st.sats[D.i], b0 = B[D.i], P = pos(st, D.i), yl = ph === DRAG && !low && !Tk().reduced();
    if (ph === DRAG) { b0.tx = D.px - D.gx - s0.x; b0.ty = D.py - D.gy - s0.y; if (++tick % 6 === 1) crown(true); } else b0.tx = b0.ty = 0;
    for (j = 0; j < B.length; j++) if (j !== D.i) { if (yl) give(st, j, P, B[j]); else B[j].tx = B[j].ty = 0; }
    dt = clamp(dt || 0, 0, 0.05);
    var n = Math.ceil(dt / K.step) || 1, h = dt / n;
    for (k = 0; k < n; k++) for (j = 0; j < B.length; j++) {
      if (j !== D.i) step(B[j], h, SP.pull, 0, ph === DRAG ? 0 : 2);
      else if (ph === DRAG) step(b0, h, SP.follow, 0, 0);
      else if (ph === BACK) step(b0, h, SP.sat, K.drag, K.cap);
    }
    if (ph === SUCK && suck(st, s0, b0)) return;
    if (ph === BACK && B.every(still)) { finish(st); return; }
    for (j = 0; j < B.length; j++) place(st, j);
    decor(st);
  }
  /* 吸入：涡旋缩入晶体心，亮一圈脉冲后进他的罗盘 */
  function suck(st, s0, b0) {
    var t = clamp((now() - D.t1) / K.suck, 0, 1), e = t * t * t;
    crown(false);
    var A = heart(st), r = D.r0 * (1 - e), th = D.th0 + K.spin * e;
    b0.ox = A[0] + r * Math.cos(th) - s0.x; b0.oy = A[1] + r * Math.sin(th) - s0.y; b0.sc = Math.max(0.12, 1 - 0.88 * e);
    if (t < 1) return false;
    var p = mk('circle', 'skc-drag-pulse r-' + s0.r.cls, lay);
    cxy(p, A);
    p.addEventListener('animationend', function () { if (p.parentNode) lay.removeChild(p); });
    at(s0.g, 'visibility', 'hidden');
    enter(st, s0);
    return true;
  }
  function enter(st, s) {
    try { hk.pick(s.r.name); } catch (e) {}   /* = CLSky.openCompass；没换成就落回 */
    if (hk.state() === st && D && D.st === st) { at(s.g, 'visibility', 'visible'); finish(st); return; }
    /* pick() rebuilt the compass: finish the old suck transaction now so the
       next frame cannot sample a stale satellite in the new layout. */
    if (D) { releaseCapture(D); restoreControls(D); }
    ph = IDLE; D = null; B = []; clearHalo();
  }
  /*
   * Restore every bit of transient DOM state before dropping the pointer
   * capture.  A compass can be replaced while a pointer is down (for
   * example, a drop switches to the other character and rebuilds the same
   * SVG).  In that case merely clearing D leaves the old satellite hidden or
   * translated until the next layout pass.  Keep this operation idempotent:
   * reset() is also called by frame() after a view switch.
   */
  function restoreVisuals(st, bs) {
    if (!st || !st.sats) return;
    bs = bs || B;
    st.sats.forEach(function (s, i) {
      var b = bs[i];
      if (!s) return;
      try {
        at(s.g, 'visibility', s.shown ? 'visible' : 'hidden');
        s.g.classList.remove('is-grab', 'is-sucked');
        s.link.classList.remove('is-taut');
        s.link.removeAttribute('transform');
        css(s.g, '--skc-lift');
        css(s.link, '--skc-k'); css(s.link, '--skc-rho');
        if (b && s.shown) {
          at(s.g, 'transform', tr(s.x, s.y));
          if (b.d0) at(s.link, 'd', b.d0);
        }
      } catch (e) {}
    });
  }

  function releaseCapture(d) {
    if (!d || d.id == null) return;
    var owner = d.capture || d.captureTarget || svg;
    try { if (owner && owner.releasePointerCapture) owner.releasePointerCapture(d.id); } catch (e) {}
    d.capture = null;
    d.captureTarget = null;
  }
  function restoreControls(d) {
    if (!d || !d.controls) return;
    d.controls.enableRotate = d.rotate == null ? true : d.rotate;
    d.controls.enablePan = d.pan == null ? true : d.pan;
    d.controls = null;
  }

  function clearHalo() {
    if (!halo) return;
    at(halo, 'd', '');
    at(halo, 'class', 'skc-drag-halo');
    css(halo, '--skc-k'); css(halo, '--skc-rho');
  }

  function finish(st) {
    restoreVisuals(st, B);
    if (D && D.t1) stat.settle = +(now() - D.t1).toFixed(3);
    reset(); hk.unlight();
  }

  /* 指针捕获在星上：轨道控制器收不到 */
  function listen(on) { ['pointermove', 'pointerup', 'pointercancel'].forEach(function (t) { g[on ? 'addEventListener' : 'removeEventListener'](t, t === 'pointermove' ? onMove : onUp, true); }); }
  function onDown(e) {
    var t = e.target.closest && e.target.closest('[data-sat]'), st = hk && hk.state(), i = t ? +t.getAttribute('data-sat') : -1, s = st && st.sats[i];
    if (ph !== IDLE || e.button !== 0 || e.ctrlKey || e.metaKey || e.isPrimary === false || !s || !s.shown || !st.B) return;
    var r = ray(st.B, s.x, s.y, s.rr);
    hook(); eatAt = 0; K = Tk().SAT; SP = Tk().SPRING;
    B = st.sats.map(function (x) { return { ox: 0, oy: 0, vx: 0, vy: 0, tx: 0, ty: 0, sc: 1, wx: 0, wy: 0, d0: x.link.getAttribute('d') || '' }; });
    var SS = scene();
    D = { st: st, i: i, id: e.pointerId, mouse: e.pointerType === 'mouse', sx: e.clientX, sy: e.clientY, px: e.clientX, py: e.clientY, gx: e.clientX - s.x, gy: e.clientY - s.y, L0: r ? r.L : 120, capture: null, captureTarget: null, camTarget: SS && SS.controls && SS.controls.target ? SS.controls.target.clone() : null, camPos: SS && SS.camera ? SS.camera.position.clone() : null };
    D.controls = SS && SS.controls || null;
    if (D.controls) { D.rotate = D.controls.enableRotate; D.pan = D.controls.enablePan; D.controls.enableRotate = false; D.controls.enablePan = false; }
    /* 若罗盘镜头仍在入场 tween，拖动从当前机位接管并把 tween 收束到
       同一姿态；否则 target 会在按住期间继续漂移，读起来像平移。 */
    var lowNow = false;
    try { lowNow = !!(SS && SS.core && SS.core().getDegrade && SS.core().getDegrade() >= 2); } catch (e3) {}
    if (SS && SS.flyTo && D.camPos && D.camTarget && !lowNow && !Tk().reduced()) SS.flyTo(D.camPos.clone(), D.camTarget.clone(), 0.001);
    if (e.cancelable) e.preventDefault();
    e.stopPropagation();
    try { t.setPointerCapture(e.pointerId); D.capture = t; D.captureTarget = t; } catch (e2) {}
    listen(true);
  }
  function onMove(e) {
    if (!D || e.pointerId !== D.id) return;
    /* A mouse move with no buttons means the matching pointerup was lost
       (window blur / browser capture handoff).  It is a cancellation, never
       a drop: otherwise moving out of the window can accidentally switch the
       compass when the last coordinates happen to be over the crystal. */
    if (D.mouse && !e.buttons) { cancelDrag(); return; }
    D.px = e.clientX; D.py = e.clientY;
    if (!D.moved) {
      var sl = Tk().TUG.slopPx, s = D.st.sats[D.i];
      if (Math.hypot(D.px - D.sx, D.py - D.sy) <= (D.mouse ? sl.mouse : sl.touch)) return;
      D.moved = true; ph = DRAG; stat.drags++;
      if (!D.controls) {
        D.controls = scene() && scene().controls || null;
        if (D.controls) { D.rotate = D.controls.enableRotate; D.pan = D.controls.enablePan; D.controls.enableRotate = false; D.controls.enablePan = false; }
      }
      svg.classList.add('skc-dragging');
      s.g.classList.add('is-grab'); css(s.g, '--skc-lift', String(K.lift)); s.link.classList.add('is-taut');
      at(halo, 'class', 'skc-drag-halo r-' + s.r.cls);
      hk.lightSat(D.i); svg.card.hidden = true;
      crown(true);
    }
    if (e.cancelable) e.preventDefault();
  }
  function onUp(e) {
    if (!D || e.pointerId !== D.id) return;
    if (e.type === 'pointercancel') { cancelDrag(); return; }
    listen(false);
    if (!D.moved) { stat.clicks++; releaseCapture(D); restoreControls(D); D = null; B = []; return; }   /* slop 内 = 点击 */
    eatAt = D.t1 = now(); D.px = e.clientX; D.py = e.clientY;
    var st = D.st, s = st.sats[D.i], p = pos(st, D.i), A, red = Tk().reduced();
    crown(true); svg.classList.remove('skc-armed'); D.armed = false;
    if (e.type !== 'pointercancel' && (inside(cb, D.px, D.py) || inside(cb, p[0], p[1]))) {
      stat.drops++;
      if (red) { enter(st, s); return; }
      A = heart(st); D.r0 = Math.hypot(p[0] - A[0], p[1] - A[1]); D.th0 = Math.atan2(p[1] - A[1], p[0] - A[0]);
      ph = SUCK; s.g.classList.add('is-sucked');
    } else if (red) finish(st);   /* 减弱动效：一帧到位 */
    else ph = BACK;
  }

  /* Pointer cancellation and lost-button recovery share the same path.  A
     cancelled drag returns to its home position and never invokes onPick. */
  function cancelDrag() {
    if (!D) return;
    var d = D, st = d.st, bs = B;
    listen(false); releaseCapture(d);
    restoreVisuals(st, bs);
    restoreControls(d);
    /* Lost-button / pointercancel stays in the same compass.  Clear the
       temporary highlight and card that onMove() hid when the drag began;
       skip this when a view switch already replaced the state. */
    try { if (hk && hk.state() === st && hk.unlight) hk.unlight(); } catch (e) {}
    eatAt = 0;
    ph = IDLE; D = null; B = [];
    if (svg) svg.classList.remove('skc-dragging', 'skc-armed');
    clearHalo();
  }
  /* 拖动中不改悬停点亮；拖过的 click 吃掉 */
  function gate(e) { if (ph === DRAG || ph === SUCK) e.stopImmediatePropagation(); }
  function eat(e) { if (eatAt && now() - eatAt < 0.6) { eatAt = 0; e.stopImmediatePropagation(); e.preventDefault(); } }

  function attach(s, h) {
    hk = h; if (svg === s) return;
    svg = s; lay = mk('g', 'skc-drag', svg); svg.insertBefore(lay, svg.gChain || null);
    halo = mk('path', 'skc-drag-halo', lay); at(halo, 'mask', 'url(#skcKnock)'); ring = mk('circle', 'skc-drag-ring', lay);
    /* Capture on the SVG root before document-level gesture delegates.  A
       valid satellite drag must own the pointer from the first event so
       OrbitControls / constellation tug cannot start in the same frame. */
    svg.addEventListener('pointerdown', onDown, true);
    ['pointerover', 'pointerout', 'pointermove'].forEach(function (t) { svg.addEventListener(t, gate, true); });
    svg.addEventListener('click', eat, true);
    hook();
  }
  /* 重排后重取家位连线 */
  function relayout() {
    var st = hk && hk.state(); if (!st || ph === IDLE || !D || D.st !== st) return;
    st.sats.forEach(function (s, i) { B[i].d0 = s.link.getAttribute('d') || ''; B[i].wx = NaN; });
    var s0 = st.sats[D.i], r = ray(st.B, s0.x, s0.y, s0.rr); if (r) D.L0 = r.L;
    for (var j = 0; j < B.length; j++) place(st, j);
    decor(st);
  }
  function reset() {
    var d = D, st = d && d.st, bs = B;
    listen(false); releaseCapture(d); restoreVisuals(st, bs); restoreControls(d);
    ph = IDLE; D = null; B = []; cb = null;
    if (svg) svg.classList.remove('skc-dragging', 'skc-armed');
    clearHalo();
  }

  /* 图谱换态时立即收拢拖动层。等 SVG 被卸载后再 reset 会让 pointer capture
     和旧的让位偏移多活一帧，随后切回罗盘时会出现错误的初始位置。 */
  function cancelForView() { if (ph !== IDLE || D) reset(); }
  doc.addEventListener('cl:sky-plot', cancelForView, false);
  doc.addEventListener('cl:sky-compass', cancelForView, false);
  doc.addEventListener('cl:graph-loading', cancelForView, false);

  g.CLSkyCompassDrag = {
    attach: attach, relayout: relayout, reset: reset,
    cancel: cancelForView,
    stats: function () {
      var o = { phase: ['idle', 'drag', 'back', 'suck'][ph], index: D ? D.i : -1, armed: !!(D && D.armed), maxOff: 0 }, k;
      B.forEach(function (b) { o.maxOff = Math.max(o.maxOff, Math.hypot(b.ox, b.oy)); });
      for (k in stat) o[k] = stat[k];
      return o;
    }
  };
})(window);
