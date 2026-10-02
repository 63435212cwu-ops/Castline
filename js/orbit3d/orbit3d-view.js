/*!
 * @role component · @owns js/orbit3d-view.js · @budget js_ms<=0.5 · @contract v47
 * 覆盖 CLPlotOrbitViewFactory：v46.1 view 同名 API（interact 原样挂上来），内里驱动
 * geom/layer/motion/pick/labels 的 WebGL 盘面，无 SVG；帧优先挂 CLArcana.update
 * （scene.step() 泵帧也能推进），否则回落 rAF。状态机 briefs/v47/STATES.md。
 * §7：search 含 tree=1 / treestage=1 时不接管工厂。
 */
(function (g) {
  'use strict';

  var V = '47.0.0';
  var doc = g.document;
  if (!doc) return;
  var Q = (g.location && g.location.search) || '';
  if (/[?&]tree=1(?:&|$)/.test(Q) || /[?&]treestage=1(?:&|$)/.test(Q)) return;

  var RING_OFF = 0.058, RIDE_EVERY = 6;   /* 星点环偏移（同 interact）· 每 N 帧回写星点 */
  var SPIN_EPS = 0.0004, PUMP_GRACE = 260;
  var PITCH_FB = 0.46, RY_FB = 0.74;

  function isFn(o, n) { return !!(o && typeof o[n] === 'function'); }
  function call(o, n, a, b) { if (isFn(o, n)) { try { return o[n](a, b); } catch (e) {} } return undefined; }
  function nowMs() { return (g.performance && g.performance.now) ? g.performance.now() : (new Date()).getTime(); }
  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function cp(src, over) {   /* 浅拷贝 + 覆盖：来源字段整份带过来，只覆盖本层要定的 */
    var o = {}, k;
    for (k in src) { if (has(src, k)) o[k] = src[k]; }
    for (k in over) o[k] = over[k];
    return o;
  }

  function mod(n) { return g['CLOrbit3D' + n] || null; }
  function TOKENS() { return mod('Tokens'); }
  function TIERM() { return mod('Tier'); }
  function LAYER() { return mod('Layer'); }

  function CONV() { return g.CLPlotOrbitConverge || null; }

  function tierName() {
    var T = TIERM();
    if (isFn(T, 'get')) { try { return T.get(); } catch (e) {} }
    var k = TOKENS();
    return (k && isFn(k, 'isLowDevice') && k.isLowDevice()) ? 'low' : 'high';
  }
  function reducedMotion() {
    var T = TIERM();
    if (isFn(T, 'reduced')) { try { return !!T.reduced(); } catch (e) {} }
    return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function create(scene, opts) {
    opts = opts || {};
    var strict = opts.strictTopology !== false;

    var mode = 'constellation', tree = null, desc = null, M = null;
    var focusEv = -1, hoverEv = -1, thread = null, charName = null, lit = null;
    var isEmpty = false, builds = 0, builtR = 0, dead = false;
    var motion = null, pick = null, labels = null, layerOn = false;
    var spin = 0, fade = 0, pulseEv = -1, pulseK = 0, pulseAngle = null;
    var L = {}, raf = 0, lastPump = -1e9, lastT = -1, rideN = 0, rideSpin = 1e9;
    var ptrX = -1, ptrY = -1, ptrDirty = false, ptrOwn = false, hitEv = -1;
    var frame = { group: null, rimR: 0, rimV: 0, pitch: PITCH_FB, R: 0 };

    var root = doc.createElement('div');
    root.id = 'clOrbit';
    root.className = 'cl-orbit';
    root.setAttribute('tabindex', '-1');
    var lab = doc.createElement('div');
    lab.className = 'cl-orbit__labels cl-o3-labels';
    root.appendChild(lab);
    /* 命中片：给 interact 留一个 [data-ev] 目标（hover 卡片 / 点击） */
    var hit = doc.createElement('div');
    hit.className = 'cl-o3-hit';
    hit.style.cssText = 'position:fixed;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;' +
      'background:transparent;pointer-events:auto;cursor:pointer';
    hit.hidden = true;
    root.appendChild(hit);
    (doc.body || doc.documentElement).appendChild(root);

    function on(t, f) { (L[t] = L[t] || []).push(f); return function () { off(t, f); }; }
    function off(t, f) { var a = L[t] || [], i = a.indexOf(f); if (i >= 0) a.splice(i, 1); }
    function emit(t, p) {
      var a = L[t];
      if (!a || !a.length) return;
      a = a.slice();
      for (var i = 0; i < a.length; i++) { try { a[i](p); } catch (e) {} }
    }

    function anchorGroup() {
      var A = g.CLTreeAnchor, r;
      if (!isFn(A, 'root')) return null;
      try { r = A.root(); } catch (e) { return null; }
      return (r && r.parent) ? r.parent : null;
    }
    function uRout(m) {
      var u = m && m.uniforms && m.uniforms.uRout;
      return (u && typeof u.value === 'number') ? u.value : null;
    }
    var R_FALLBACK = 240;
    /* 外圈半径：沿用 v46.1 取法（uRout 最大的那件），再退 scene.roadRim() */
    function resolveR() {
      var q = frame.group || anchorGroup(), best = -Infinity, rr = null;
      try { rr = isFn(scene, 'roadRim') ? scene.roadRim() : null; } catch (e) { rr = null; }
      var roadR = (rr && rr.R >= 50) ? rr.R : 0;
      if (q && isFn(q, 'traverse')) {
        frame.group = q;
        q.traverse(function (o) {
          var v = uRout(o && o.material);
          if (v !== null && v >= 50 && v > best) best = v;
        });
      }
      if (best >= 50 && !(roadR > 0 && best < roadR * 0.5)) {
        frame.R = best; if (!(frame.rimR > 0)) frame.rimR = best; return frame.R;
      }
      if (roadR >= 50) frame.R = roadR;
      else if (frame.rimR >= 50) frame.R = frame.rimR;
      else frame.R = R_FALLBACK;
      return frame.R;
    }
    function ryOf() {
      var k = (frame.rimR > 0 && frame.rimV > 0) ? frame.rimV / frame.rimR : RY_FB;
      return k < 0.35 ? 0.35 : (k > 1 ? 1 : k);
    }

    /* 被动插件：只取 group/rimR/rimV/pitch 与逐帧 t，不建网格 */
    var probe = {
      name: 'orbit3d-view',
      build: function (o) {
        if (!o || dead) return;
        frame.group = o.group || frame.group;
        frame.rimR = num(o.rimR, frame.rimR);
        frame.rimV = num(o.rimV, frame.rimV);
        frame.pitch = num(o.pitch, frame.pitch);
        if (frame.rimR > 0) frame.R = frame.rimR;
        if (tree && (!desc || Math.abs(frame.R - builtR) > 0.5)) rebuild();
      },
      update: function (s) {
        if (dead) return;
        var t = (s && isFinite(s.t)) ? s.t : (nowMs() / 1000);
        var dt = (lastT < 0) ? 0.016 : (t - lastT);
        lastT = t; lastPump = nowMs();
        step(dt, t);
      }
    };
    try { if (isFn(g.CLArcana, 'register')) g.CLArcana.register(probe); } catch (e) {}

    /* 数据索引：直接读 tree；待校对判据只此一处 anchored || topologyStatus!=='confirmed' */
    function indexTree() {
      M = { events: {}, lines: {}, order: [], eventRoles: {}, roleEvents: {}, list: [], nEv: 0, nLn: 0 };
      if (!tree) return;
      var evs = tree.events || [], ths = tree.threads || [], el = {}, i, j, ev, id, ln;
      for (i = 0; i < ths.length; i++) {
        var t = ths[i] || {};
        id = t.id || ('T' + i);
        ev = t.events || [];
        var st = (typeof t.topologyStatus === 'string' && t.topologyStatus) ? t.topologyStatus : 'confirmed';
        var pend = (t.anchored === true) || (st !== 'confirmed');
        ln = cp(t, { id: id, kind: (t.kind === 'main') ? 'main' : 'branch', title: t.title || '',
          lead: t.lead || '', len: ev.length, events: ev.slice(0), status: st, anchored: t.anchored === true,
          pending: pend, valid: !pend, resolved: t.resolved === true, suspended: !!t.suspended,
          pendingReason: t.pendingReason || '' });
        M.lines[id] = ln; M.list.push(ln); M.nLn++;
        for (j = 0; j < ev.length; j++) (el[ev[j]] = el[ev[j]] || []).push(id);
      }
      for (i = 0; i < evs.length; i++) {
        var e = evs[i] || {}, ix = isFinite(e.i) ? e.i : i, ids = el[ix] || [], pd = false;
        for (j = 0; j < ids.length; j++) { if (M.lines[ids[j]] && M.lines[ids[j]].pending) { pd = true; break; } }
        M.events[ix] = cp(e, { evIdx: ix, i: ix, order: num(e.order, i + 1), cast: e.cast || [],
          lineIds: ids, owners: ids.length, shared: ids.length > 1, pending: pd, handoff: null, angle: 0, r: 0 });
        M.order.push(M.events[ix]);
        M.nEv++;
      }
      M.order.sort(function (x, y) { return x.order - y.order; });
      for (i = 0; i < M.order.length; i++) M.order[i] = M.order[i].evIdx;
      var cast = tree.cast || {}, nm;
      for (nm in cast) {
        if (!has(cast, nm)) continue;
        var ce = (cast[nm] && cast[nm].events) || [];
        M.roleEvents[nm] = ce.slice(0);
        for (j = 0; j < ce.length; j++) (M.eventRoles[ce[j]] = M.eventRoles[ce[j]] || []).push(nm);
      }
    }
    function indexDesc() {
      if (!desc || !M) return;
      var b = desc.beads || [], a = desc.arcs || [], h = desc.handoffs || [], i, r;
      for (i = 0; i < b.length; i++) {
        var bd = b[i], me = M.events[bd.evIdx];
        if (!me) continue;
        if (bd.owners !== undefined) me.owners = num(bd.owners, me.owners);
        if (bd.shared !== undefined) me.shared = !!bd.shared;
        r = num(bd.r, 0);
        if (r >= me.r) { me.r = r; me.angle = num(bd.angle, me.angle); me.lineId = bd.lineId; me.color = bd.color; }
      }
      for (i = 0; i < a.length; i++) {
        var ar = a[i], ml = M.lines[ar.lineId];
        if (!ml) continue;
        ml.lane = num(ar.lane, 0); ml.r = num(ar.r, 0); ml.aStart = ar.aStart; ml.aEnd = ar.aEnd;
        ml.segments = ar.segments || null; ml.arcColor = ar.color; ml.crowded = !!ar.crowded;
        if (ar.resolved !== undefined) ml.resolved = !!ar.resolved;
        if (ar.suspended !== undefined) ml.suspended = !!ar.suspended;
      }
      for (i = 0; i < h.length; i++) {
        var at = isFinite(h[i].evIdx) ? h[i].evIdx : h[i].at;
        if (M.events[at]) M.events[at].handoff = h[i];
      }
    }

    function eventAt(ev) { return (M && M.events[ev]) || null; }
    function threadAt(id) { return (M && M.lines[id]) || null; }
    /* F 态：有角色筛选时 ←/→ 只走该角色的事件子集（STATES §F） */
    function orderList() {
      var src = (M && M.order.length) ? M.order : ((desc && desc.order) || []), o = [], i;
      if (!charName || !M || !M.roleEvents[charName]) return src.slice(0);
      var mine = {}, re = M.roleEvents[charName];
      for (i = 0; i < re.length; i++) mine[re[i]] = 1;
      for (i = 0; i < src.length; i++) { if (mine[src[i]]) o.push(src[i]); }
      return o.length ? o : src.slice(0);
    }
    function lineEvents(id) { var t = threadAt(id); return t ? t.events.slice(0) : []; }
    function participants(ev) {
      var o = [], s = {}, i;
      function add(n) { if (n && !s[n]) { s[n] = 1; o.push(n); } }
      var er = M ? M.eventRoles[ev] : null;
      if (er) for (i = 0; i < er.length; i++) add(er[i]);
      var e = eventAt(ev);
      if (e && e.cast) for (i = 0; i < e.cast.length; i++) add(e.cast[i]);
      return o;
    }

    function mkMotion() {
      var Mo = mod('Motion');
      if (motion || !isFn(Mo, 'create')) return motion;
      try { motion = Mo.create(TOKENS()); } catch (e) { motion = null; }
      if (!motion) return null;
      call(motion, 'setReduced', reducedMotion());
      call(motion, 'setTier', tierName());
      call(motion, 'setVisible', mode === 'plot');
      if (desc) call(motion, 'setOrder', desc.order || orderList(), desc.angleOf || {});
      return motion;
    }
    function mkPick() {
      var P = mod('Pick');
      if (pick || !isFn(P, 'create') || !desc) return pick;
      try { pick = P.create(LAYER(), desc, scene); } catch (e) { pick = null; }
      return pick;
    }
    function mkLabels() {
      var B = mod('Labels');
      if (labels || !isFn(B, 'create') || !desc) return labels;
      try { labels = B.create(view, pick, TOKENS()); } catch (e) { labels = null; }
      return labels;
    }
    function setLayerOn(v) {
      var Y = LAYER();
      if (!Y || layerOn === !!v) return;
      layerOn = !!v;
      call(Y, 'setOn', layerOn);
    }
    function rebuild() {
      var G = mod('Geom'), d = null;
      if (!tree || !(frame.R > 0) || !isFn(G, 'build')) return false;
      try { d = G.build(tree, { R: frame.R, ry: ryOf(), strictTopology: strict }); } catch (e) { d = null; }
      if (!d) return false;
      desc = d; builds++; builtR = frame.R;
      indexDesc();
      isEmpty = !(desc.arcs && desc.arcs.length) || !(desc.beads && desc.beads.length);
      call(LAYER(), 'setGeom', desc);
      mkMotion();
      if (motion) call(motion, 'setOrder', (tree && tree.trunk && tree.trunk.events && tree.trunk.events.length) ? tree.trunk.events : (desc.order || orderList()), desc.angleOf || {});
      if (pick) call(pick, 'setGeom', desc); else mkPick();
      mkLabels();
      apply();
      return true;
    }
    function ensure() {
      if (!tree || desc) return !!desc;
      if (!(frame.R > 0)) resolveR();
      return rebuild();
    }

    function toGroup(x, y, z) {
      var Y = LAYER(), p;
      if (isFn(Y, 'localToGroup')) {
        try { p = Y.localToGroup(x, y, z || 0); } catch (e) { p = null; }
        if (p) return (p.length >= 3) ? [p[0], p[1], p[2]] : [p.x, p.y, p.z];
      }
      var c = Math.cos(spin), s = Math.sin(spin);
      var px = x * c - y * s, py = (x * s + y * c) * ryOf();
      return [px, py * Math.cos(frame.pitch), -py * Math.sin(frame.pitch)];
    }
    function screenOf(loc) {
      var T = g.THREE, f = null;
      if (!loc || !T || !T.Vector3 || !scene || !scene.camera) return null;
      var v = new T.Vector3(loc[0], loc[1], loc[2]), q = frame.group || anchorGroup();
      /* Projection runs before WebGLRenderer.render. A dragged camera must not
       * retain the inverse matrix from the preceding rendered frame. */
      scene.camera.updateMatrixWorld(true);
      if (q && isFn(q, 'updateWorldMatrix')) q.updateWorldMatrix(true, false);
      if (q && isFn(q, 'localToWorld')) q.localToWorld(v);
      v.project(scene.camera);
      try { f = isFn(scene, 'camInfo') ? scene.camInfo() : null; } catch (e) { return null; }
      if (!f || !f.W || !f.H) return null;
      return [(v.x * 0.5 + 0.5) * f.W, (-v.y * 0.5 + 0.5) * f.H];
    }
    function angleOf(ev) {
      if (desc && desc.angleOf && isFinite(desc.angleOf[ev])) return desc.angleOf[ev];
      var e = eventAt(ev);
      return (e && isFinite(e.angle) && e.r > 0) ? e.angle : null;
    }
    function anchorLocal(ev, offs, aOff) {
      var e = eventAt(ev), a = angleOf(ev);
      if (a === null) return null;
      var r = (e && e.r > 0) ? e.r : num(desc && desc.R, frame.R);
      if (typeof aOff === 'number') {
        var rT = r + (offs ? num(offs[0], 0) : 0);
        var aT = a + aOff;
        return toGroup(rT * Math.cos(aT), rT * Math.sin(aT), 0);
      }
      var dx = offs ? num(offs[0], 0) : 0, dy = offs ? num(offs[1], 0) : 0;
      return toGroup(r * Math.cos(a) + dx, r * Math.sin(a) + dy, 0);
    }
    function anchorScreen(ev) {
      var p = null;
      try { p = isFn(pick, 'screenOf') ? pick.screenOf(ev) : null; } catch (e) { p = null; }
      return (p && isFinite(p[0]) && isFinite(p[1])) ? [p[0], p[1]] : screenOf(anchorLocal(ev, null));
    }

    /* ── 星点随盘：盘在转珠也在动，interact 只在选中那一刻问一次锚点，这里按帧补发 ── */
    function targets(ev, parts) {
      var out = {}, n = parts.length, R = frame.R || 240, i, p;
      var tok = TOKENS(), ro = (tok && tok.SIZE && tok.SIZE.RING_OFF) || RING_OFF;
      for (i = 0; i < n; i++) {
        var aOff = n > 1 ? (i - (n - 1) / 2) * 0.105 : 0;
        p = anchorLocal(ev, [ro * R, 0], aOff);
        if (p) out[parts[i]] = p;
      }
      return out;
    }
    function rideStars() {
      if (focusEv < 0) { rideSpin = 1e9; return; }
      if (rideN-- > 0) return;
      rideN = RIDE_EVERY;
      var C = CONV(), st = null;
      if (!isFn(C, 'set') || !isFn(C, 'state') || Math.abs(spin - rideSpin) < SPIN_EPS) return;
      try { st = C.state(); } catch (e) { return; }
      if (!st || st.phase !== 'hold' || !st.n) return;
      rideSpin = spin;
      var parts = participants(focusEv);
      if (parts.length) { try { C.set(targets(focusEv, parts)); } catch (e2) {} }
    }

    function apply() {
      var d = root.dataset;
      if (d) {
        d.mode = mode; d.focus = focusEv >= 0 ? '1' : '0'; d.hover = hoverEv >= 0 ? '1' : '0';
        d.thread = thread || ''; d.empty = isEmpty ? '1' : '0';
      }
      root.setAttribute('aria-hidden', mode === 'constellation' ? 'true' : 'false');
    }
    var userPaused = false, heldMotionTime = null;
    function step(dt, t) {
      if (!desc) ensure();
      if (!motion || !pick || !labels) { mkMotion(); mkPick(); mkLabels(); }
      if (userPaused) { if (heldMotionTime === null) heldMotionTime = t; t = heldMotionTime; dt = 0; } else heldMotionTime = null;
      var m = motion ? motion.tick(dt, t) : null, Y = LAYER();
      if (scene && scene.camera) scene.camera.updateMatrixWorld(true);
      if (m) {
        spin = num(m.spin, spin);
        fade = num(m.fade, mode === 'plot' ? 1 : 0);
        if (m.pulse) { pulseEv = num(m.pulse.evIdx, -1); pulseK = num(m.pulse.k, 0); pulseAngle = (typeof m.pulse.a === 'number' && isFinite(m.pulse.a)) ? m.pulse.a : null; }
      } else { fade = (mode === 'plot') ? 1 : 0; }
      if (Y) {
        if (mode === 'plot' && !layerOn) setLayerOn(true);
        call(Y, 'setSpin', spin);
        call(Y, 'setFade', fade);
        if (desc) {
          call(Y, 'setState', { focusEv: focusEv, hoverEv: hoverEv, thread: thread, litEvents: lit,
            charName: charName, pulseEv: pulseEv, pulseK: pulseK, pulseAngle: pulseAngle, empty: isEmpty });
        }
        if (mode !== 'plot' && layerOn && fade <= 0.002) setLayerOn(false);
      }
      if (mode !== 'plot') return;
      call(pick, 'refresh');
      if (ptrDirty) hover();
      call(labels, 'update');
      rideStars();
      emit('frame');
    }
    function loop() {
      if (g.CLSky && g.CLSky.enabled && g.CLSky.enabled()) { raf = 0; return; }   /* 星空壳：旧三维轨道视图从不上屏，不再逐帧空转 */
      raf = g.requestAnimationFrame(loop);
      if (dead || nowMs() - lastPump < PUMP_GRACE) return;   /* arcana 在推帧就让位 */
      var t = nowMs() / 1000, dt = (lastT < 0) ? 0.016 : (t - lastT);
      lastT = t;
      step(dt, t);
    }

    function setHit(ev, x, y) {
      if (ev < 0) {
        if (hitEv >= 0) { hit.hidden = true; hit.removeAttribute('data-ev'); hitEv = -1; }
        return;
      }
      if (ev !== hitEv) { hit.setAttribute('data-ev', String(ev)); hitEv = ev; }
      var p = isFinite(x) ? [x, y] : anchorScreen(ev);
      if (!p) return;
      hit.style.left = p[0] + 'px'; hit.style.top = p[1] + 'px'; hit.hidden = false;
    }
    function hover() {
      ptrDirty = false;
      if (mode !== 'plot') return;
      /* 指针压在卡片上：交给 interact */
      var ev = ptrOwn ? -1 : (isFn(pick, 'bead') ? pick.bead(ptrX, ptrY) : -1);
      if (!(ev >= 0)) ev = -1;
      setHit(ev, ev >= 0 ? ptrX : NaN, ptrY);
      hoverEvent(ev);
    }
    function inRoot(t) { return !!(t && t !== hit && t.nodeType === 1 && root.contains(t)); }
    function onMove(e) {
      if (e.__clo3m) return;
      e.__clo3m = 1;
      if (mode !== 'plot') return;
      ptrX = e.clientX; ptrY = e.clientY; ptrOwn = inRoot(e.target) || !!(e.target && e.target.closest && e.target.closest('#atlasPreviewHUD,#atlasLocalGraph,.cl-ann-layer,#ops,#loader,#apiPanel,#library,#infoArchitecture')); ptrDirty = true;
    }
    var downX = -1, downY = -1;
    function onDown(e) { if (e.button === 0) { downX = e.clientX; downY = e.clientY; } }
    function onClick(e) {
      if (e.__clo3c) return;
      if (e.target && e.target.closest && e.target.closest('#atlasPreviewHUD,#atlasLocalGraph,.cl-ann-layer,#ops,#loader,#apiPanel,#library,#infoArchitecture')) return;
      e.__clo3c = 1;
      if (downX >= 0 && downY >= 0 && Math.hypot(e.clientX - downX, e.clientY - downY) > 6) {
        downX = -1; downY = -1;
        return;
      }
      downX = -1; downY = -1;
      if (mode !== 'plot' || inRoot(e.target)) return;
      var ev = isFn(pick, 'bead') ? pick.bead(e.clientX, e.clientY) : -1;
      if (ev >= 0) { focusEvent(ev); return; }
      var id = isFn(pick, 'arc') ? pick.arc(e.clientX, e.clientY) : null;
      if (id) { focusThread(id); return; }
      /* 只有点在空处才撤选：HUD 的 [data-ev] 归 interact.onDocClick */
      var tn = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
      if ((focusEv >= 0 || thread) && (tn === 'canvas' || tn === 'body' || tn === 'html')) { focusEvent(-1); focusThread(null); }
    }
    /* Esc 链的「撤角色筛选」一层归本文件（interact 不认识 character 且禁改）：
     * 本监听注册早于 interact.attach()，同为 window 捕获 → 先跑，吃掉这一次 Esc。 */
    function onEsc(e) {
      if (g.CLInformationArchitecture && g.CLInformationArchitecture.isOpen()) return;
      if (g.CLAtlasPreview && g.CLAtlasPreview.active()) return;
      if (mode !== 'plot' || e.key !== 'Escape' || !charName || hoverEv >= 0) return;
      var t = e.target, tag = (t && t.tagName) ? t.tagName.toLowerCase() : '';
      if (t && (t.isContentEditable || tag === 'input' || tag === 'textarea' || tag === 'select')) return;
      setCharacter(null);
      call(scene, 'setSearchSet', focusEv >= 0 ? participants(focusEv) : null);
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    }
    root.addEventListener('pointerdown', onDown, false); root.addEventListener('pointermove', onMove, false); root.addEventListener('click', onClick, false);
    g.addEventListener('pointerdown', onDown, false); g.addEventListener('pointermove', onMove, false); g.addEventListener('click', onClick, false);
    g.addEventListener('keydown', onEsc, true);

    function setTree(t) {
      tree = t || null; desc = null; pick = null; builtR = 0;
      if (labels) { call(labels, 'destroy'); labels = null; }
      indexTree();
      resolveR();
      ensure();
      return view;
    }
    function setMode(m) {
      m = (m === 'plot') ? 'plot' : 'constellation';
      if (m === mode) return mode;
      mode = m;
      apply();
      if (mode === 'plot') {
        ensure(); setLayerOn(true);
        if (motion) call(motion, 'setVisible', true); else { fade = 1; call(LAYER(), 'setFade', 1); }
      } else {
        hoverEvent(-1); setHit(-1);
        focusEvent(-1); focusThread(null); setCharacter(null);
        if (motion) call(motion, 'setVisible', false);
        else { fade = 0; call(LAYER(), 'setFade', 0); setLayerOn(false); }
      }
      emit('mode', mode);
      return mode;
    }
    function toggle() { setMode(mode === 'plot' ? 'constellation' : 'plot'); return visible(); }
    function visible() { return mode === 'plot'; }
    function focusEvent(ev) {
      var v = (typeof ev === 'number' && ev >= 0) ? ev : -1;
      if (v === focusEv) return;
      focusEv = v;
      apply();
      var a = (motion && v >= 0) ? angleOf(v) : null;
      if (motion) { if (v < 0) call(motion, 'release'); else if (a !== null) call(motion, 'focusAngle', a); }
      rideN = 0; rideSpin = 1e9;
      emit('focus', focusEv);
    }
    function hoverEvent(ev) {
      var v = (typeof ev === 'number' && ev >= 0) ? ev : -1;
      if (v === hoverEv) return;
      hoverEv = v;
      apply();
      emit('hover', hoverEv);
    }
    /* 线选不转正、不停转（STATES §E） */
    function focusThread(id) {
      var v = id || null;
      if (v === thread) return;
      thread = v;
      apply();
      emit('thread', thread);
    }
    function setCharacter(n) {
      var v = n || null;
      if (v === charName) return charName;
      charName = v;
      lit = (charName && M && M.roleEvents[charName]) ? M.roleEvents[charName].slice(0) : null;
      emit('character', charName);
      return charName;
    }
    function setEmpty(v) { isEmpty = !!v; apply(); return isEmpty; }
    function layout() {
      return { R: frame.R, ry: ryOf(), lanes: desc ? num(desc.lanes, 0) : 0, crowded: !!(desc && desc.crowded),
        arcs: (desc && desc.arcs) || [], forks: (desc && desc.forks) || [], threads: M ? M.list.slice(0) : [] };
    }
    function stats() {
      var Y = LAYER(), ls = null, nb = (desc && desc.beads) ? desc.beads.length : 0;
      if (isFn(Y, 'stats')) { try { ls = Y.stats(); } catch (e) { ls = null; } }
      return { mode: mode, empty: isEmpty, R: frame.R, focusEv: focusEv, hoverEv: hoverEv, thread: thread,
        character: charName, events: M ? M.nEv : 0, lines: M ? M.nLn : 0, beads: nb,
        arcs: (desc && desc.arcs) ? desc.arcs.length : 0, forks: (desc && desc.forks) ? desc.forks.length : 0,
        handoffs: (desc && desc.handoffs) ? desc.handoffs.length : 0,
        pending: (desc && desc.pending) ? desc.pending.length : 0, spin: spin, fade: fade, ok: !!desc,
        rimReady: frame.R > 0, builds: builds, tier: tierName(), layer: ls, version: V };
    }
    function state() {
      return { mode: mode, focusEv: focusEv, hoverEv: hoverEv, thread: thread, character: charName,
        empty: isEmpty, focus: focusEv, visible: mode === 'plot' };
    }
    function layerOf(n) { return n === 'labels' ? lab : root; }
    function destroy() {
      dead = true;
      if (raf) { g.cancelAnimationFrame(raf); raf = 0; }
      root.removeEventListener('pointermove', onMove, false); root.removeEventListener('click', onClick, false);
      g.removeEventListener('pointermove', onMove, false); g.removeEventListener('click', onClick, false);
      g.removeEventListener('keydown', onEsc, true);
      call(labels, 'destroy'); labels = null;
      setLayerOn(false);
      call(LAYER(), 'setFade', 0);
      if (root.parentNode) root.parentNode.removeChild(root);
      L = {}; tree = null; desc = null; pick = null; motion = null; M = null;
    }

    var view = {
      setTree: setTree, setMode: setMode, toggle: toggle, visible: visible,
      focusEvent: focusEvent, focusThread: focusThread, hoverEvent: hoverEvent,
      setMotionPaused: function (v) { userPaused = !!v; if (!userPaused) heldMotionTime = null; if (motion) call(motion, 'setReduced', userPaused || reducedMotion()); return userPaused; },
      motionPaused: function () { return userPaused; },
      setCharacter: setCharacter, setEmpty: setEmpty, stats: stats, state: state,
      eventAt: eventAt, threadAt: threadAt, layout: layout, orderList: orderList,
      lineEvents: lineEvents, participants: participants, anchorLocal: anchorLocal,
      anchorLocalLive: function (ev) { return anchorLocal(ev, null); },
      anchorScreen: anchorScreen, screenOf: screenOf, layer: layerOf,
      on: on, off: off, destroy: destroy,
      desc: function () { return desc; },
      motion: function () { return motion; }, picker: function () { return pick; }, version: V
    };

    apply(); resolveR(); setLayerOn(false); call(LAYER(), 'setFade', 0);
    var TR = TIERM();
    if (isFn(TR, 'onChange')) {
      TR.onChange(function (t) { if (motion) { call(motion, 'setTier', t); call(motion, 'setReduced', userPaused || reducedMotion()); } });
    }
    raf = g.requestAnimationFrame(loop);
    return view;
  }

  g.CLPlotOrbitViewFactory = { name: 'CLOrbit3DViewFactory', version: V, create: create, prev: g.CLPlotOrbitViewFactory || null };
})(typeof window !== 'undefined' ? window : this);
