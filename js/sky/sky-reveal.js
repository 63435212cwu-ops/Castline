(function (g) {
  'use strict';
  var TAU = Math.PI * 2;
  var IGN = 0.92, LAG = 0.03, SW = 1.02;

  function lin(k) { return k; }
  function span(w) { return (w.lattice[1] - w.lattice[0]) / SW; }
  function when(u, v, info, w) {
    var r = Math.sqrt(u * u + v * v), rc = info && info.rc > 0 ? info.rc : 0, l0 = w.lattice[0];
    if (rc && r < rc * 1.02) return l0 + 0.12 * Math.min(1, r / rc);
    var a = Math.atan2(u, v); if (a < 0) a += TAU;
    return l0 + span(w) * a / TAU;
  }
  function planeOf(n, pitch) {
    var p = n && (n.to || n.pos); if (!p) return null;
    var cP = Math.cos(pitch || 0), sP = Math.sin(pitch || 0);
    return [p.x, p.y * cP - p.z * sP];
  }

  function create(opts) {
    var S = opts.scene, T = g.THREE, TK = g.CLSkyTokens, C = TK.C, GL = g.CLSkyRevealGLSL;
    var anc = new T.Object3D(), lines = null, pts = null, lgeo = null, pgeo = null, tier = 'high';
    var t = 0, playing = false, hero = null, v3 = new T.Vector3(), plays = 0;
    S.group.add(anc);
    function col(h) { return new T.Color(h); }
    var lmat = new T.ShaderMaterial({ uniforms: { uSweep: { value: 0 }, uFade: { value: 0 }, uArm: { value: 0 }, uColA: { value: col(C.MINT) }, uColB: { value: col(C.STAR_COOL) } },
      vertexShader: GL.L_VS, fragmentShader: GL.L_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending });
    var pmat = new T.ShaderMaterial({ uniforms: { uPx: { value: 1 }, uHead: { value: 0 }, uFlare: { value: 0 }, uFlareT: { value: 0 }, uColA: { value: col(C.STAR_COOL) }, uColB: { value: col(C.BRASS_HOT) } },
      vertexShader: GL.P_VS, fragmentShader: GL.P_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending });

    function W() { return (TK.OPEN && TK.OPEN.sweep) || { lattice: [0.25, 1.35], threads: [0.55, 1.85], solid: [1.15, 2.3], flare: 1.75, flareDur: 1.1 }; }
    function end(w) { return w.flare + (w.flareDur || 1.1) + 0.05; }
    function norm(a) { a = a % TAU; if (a < 0) a += TAU; return a / TAU; }
    function build(c) {
      var P = [], A = [], K = [], Rr = [], i, j, r, a0, a1, n;
      function seg(x0, y0, x1, y1, ang0, ang1, kind, rr) { P.push(x0, y0, 0, x1, y1, 0); A.push(ang0, ang1); K.push(kind, kind); Rr.push(rr, rr); }
      var R = c.R || 1, rings = [], sec = c.sectors || [];
      function ring(x) { for (var q = 0; q < rings.length; q++) if (Math.abs(rings[q] - x) < 0.05) return; rings.push(x); }
      if (c.rc > 0) ring(c.rc / R);
      if (c.ra > 0) ring(c.ra / R);
      if (c.ra > 0 && c.rb > 0) ring((c.ra + c.rb) / 2 / R);
      if (c.rb > 0) ring(c.rb / R);
      ring(1); [0.2, 0.4, 0.6, 0.8].forEach(ring);
      for (j = 0; j < 24; j++) { a0 = j / 24 * TAU; seg(Math.sin(a0) * 0.05, Math.cos(a0) * 0.05, Math.sin(a0), Math.cos(a0), j / 24, j / 24, 3, 1); }
      for (i = 0; i < rings.length; i++) {
        r = rings[i]; n = 160;
        for (j = 0; j < n; j++) { a0 = j / n * TAU; a1 = (j + 1) / n * TAU; seg(Math.sin(a0) * r, Math.cos(a0) * r, Math.sin(a1) * r, Math.cos(a1) * r, j / n, (j + 1) / n, 0, r); }
      }
      for (i = 0; i < sec.length; i++) {
        if (sec[i].core) continue;
        a0 = sec[i].a0; var ri = (c.ra || c.rc || 0) / R;
        seg(Math.sin(a0) * ri, Math.cos(a0) * ri, Math.sin(a0) * 1.04, Math.cos(a0) * 1.04, norm(a0), norm(a0), 1, 1);
      }
      for (j = 0; j < 180; j++) {
        a0 = j / 180 * TAU; var L = j % 5 === 0 ? 1.06 : 1.03;
        seg(Math.sin(a0), Math.cos(a0), Math.sin(a0) * L, Math.cos(a0) * L, j / 180, j / 180, 2, 1);
      }
      seg(0, 0, 0, 0, 0, 0, 9, 0.06); Rr[Rr.length - 1] = 1.06;
      if (lgeo) lgeo.dispose();
      lgeo = new T.BufferGeometry();
      lgeo.setAttribute('position', new T.BufferAttribute(new Float32Array(P), 3));
      lgeo.setAttribute('aAng', new T.BufferAttribute(new Float32Array(A), 1));
      lgeo.setAttribute('aKind', new T.BufferAttribute(new Float32Array(K), 1));
      lgeo.setAttribute('aR', new T.BufferAttribute(new Float32Array(Rr), 1));
      if (!lines) { lines = new T.LineSegments(lgeo, lmat); lines.frustumCulled = false; lines.renderOrder = 3; anc.add(lines); } else lines.geometry = lgeo;
      if (!pgeo) {
        pgeo = new T.BufferGeometry();
        pgeo.setAttribute('position', new T.BufferAttribute(new Float32Array(6), 3).setUsage(T.DynamicDrawUsage));
        pgeo.setAttribute('aKind', new T.BufferAttribute(new Float32Array([0, 1]), 1));
        pts = new T.Points(pgeo, pmat); pts.frustumCulled = false; pts.renderOrder = 6; S.scene.add(pts);
      }
      anc.rotation.set(-(c.pitch || 0), 0, 0); anc.scale.set(R, R, R);
    }
    var names = [], ray = new T.Raycaster(), ndc = new T.Vector2(), pl = new T.Plane(), nv = new T.Vector3(), hv = new T.Vector3(), doc = g.document;
    function onPlane(x, y, info, w) {
      var cv = S.renderer.domElement.getBoundingClientRect(); if (!cv.width || !S.camera) return null;
      ndc.set((x - cv.left) / cv.width * 2 - 1, 1 - (y - cv.top) / cv.height * 2); ray.setFromCamera(ndc, S.camera);
      anc.updateMatrixWorld(true); nv.set(0, 0, 1).transformDirection(anc.matrixWorld); hv.setFromMatrixPosition(anc.matrixWorld);
      if (!ray.ray.intersectPlane(pl.setFromNormalAndCoplanarPoint(nv, hv), hv)) return null;
      anc.worldToLocal(hv); return when(hv.x * info.R, hv.y * info.R, info, w);
    }
    function nameSweep(info, w) {
      clearNames();
      var co = S.core && S.core(), ns = (co && co.nodes) || [], fs = doc.querySelectorAll('.sky-field .sf-nm'), last = w.lattice[1], i, n, p, r, at;
      for (i = 0; i < ns.length; i++) { n = ns[i]; if (n.kind !== 'char' || !n.el) continue; p = planeOf(n, info.pitch); names.push({ el: n.el, at: (p ? when(p[0], p[1], info, w) : last) + LAG + 0.06 }); }
      for (i = 0; i < fs.length; i++) { r = (fs[i].firstChild || fs[i]).getBoundingClientRect(); at = r.width ? onPlane(r.left + r.width / 2, r.top + r.height / 2, info, w) : null; names.push({ el: fs[i], at: (at == null ? last : at) + 0.1 }); }
      for (i = 0; i < names.length; i++) names[i].el.classList.add('skd-unswept');
      hush();
    }
    function hush() { doc.body.classList.add('skd-sweep-now'); setTimeout(function () { doc.body.classList.remove('skd-sweep-now'); }, 80); }
    function sweepNames() { for (var i = 0, o; i < names.length; i++) { o = names[i]; if (!o.on && t >= o.at) { o.on = 1; o.el.classList.remove('skd-unswept'); o.el.classList.add('skd-swept'); } } }
    function clearNames(now) {
      if (!names.length) return;
      for (var i = 0; i < names.length; i++) names[i].el.classList.remove('skd-unswept', 'skd-swept');
      names.length = 0;
      if (now) hush();
    }
    function vis(v) { if (lines) lines.visible = v; if (pts) pts.visible = v; }
    vis(false);

    function play(c) {
      if (!c || tier === 'low' || TK.reduced()) { playing = false; vis(false); return false; }
      hero = c.hero || null; build(c); t = 0; playing = true; plays++; vis(true); apply();
      return true;
    }
    function smooth(a, b, x) { var k = Math.max(0, Math.min(1, (x - a) / Math.max(1e-6, b - a))); return k * k * (3 - 2 * k); }
    function apply() {
      var w = W(), l0 = w.lattice[0], l1 = w.lattice[1], sw = Math.max(0, Math.min(1, (t - l0) / (l1 - l0)));
      var u = lmat.uniforms, p = pmat.uniforms;
      u.uSweep.value = sw * SW;
      u.uFade.value = smooth(l0 - 0.05, l0 + 0.15, t) * (1 - smooth(l1 - 0.1, l1 + 0.7, t));
      u.uArm.value = 0.75 * smooth(l0, l0 + 0.12, t) * (1 - smooth(l1 - 0.15, l1 + 0.1, t));
      p.uHead.value = smooth(l0, l0 + 0.1, t) * (1 - smooth(l1 - 0.1, l1 + 0.25, t));
      var ft = (t - w.flare) / (w.flareDur || 1.1);
      p.uFlareT.value = Math.max(0, Math.min(1, ft)); p.uFlare.value = ft > 0 && ft < 1 ? 1 : 0;
      p.uPx.value = (S.renderer.getPixelRatio && S.renderer.getPixelRatio()) || 1;
      var arr = pgeo.attributes.position.array, th = sw * SW * TAU;
      v3.set(Math.sin(th) * 1.045, Math.cos(th) * 1.045, 0); anc.localToWorld(v3);
      arr[0] = v3.x; arr[1] = v3.y; arr[2] = v3.z;
      var n = hero && S.nodeOf ? S.nodeOf(hero) : null;
      if (n && n.g) { n.g.getWorldPosition(v3); arr[3] = v3.x; arr[4] = v3.y; arr[5] = v3.z; } else p.uFlare.value = 0;
      pgeo.attributes.position.needsUpdate = true;
    }
    function update(dt) {
      if (!playing) return;
      t += Math.min(0.05, dt || 0);
      anc.updateMatrixWorld(true);
      apply(); sweepNames();
      if (t > end(W())) { playing = false; vis(false); clearNames(); }
    }
    function skip() { clearNames(true); if (!playing) return false; playing = false; vis(false); return true; }

    var skipBound = false, ctxNow = null;
    function onSkip() { finishNow(); }
    function unbind() { if (skipBound) { skipBound = false; g.removeEventListener('pointerdown', onSkip, true); g.removeEventListener('keydown', onSkip, true); } }
    function fib(k) { var co = S.core && S.core(), m = co && co.getFiberMat ? co.getFiberMat() : null; if (m && m.uniforms.uLine) m.uniforms.uLine.value = k; }
    function done(c, lines) { if (lines && S.replayGlyphs) S.replayGlyphs(function () { return -1; }); if (c.stars) c.stars.setIgnite(1, true); if (c.bun && c.bun.grow) c.bun.grow(9); fib(1); if (c.solid) c.solid(!!lines); }
    function finishNow() {
      var c = ctxNow; ctxNow = null;
      unbind(); skip(); g.CLSkyMotion.finishAll('reveal');
      if (c) done(c, 1);
      return !!c;
    }
    function stage(c) {
      var w = W(), M = g.CLSkyMotion, info = c.info, pitch = info ? info.pitch : 0, on = 'pointerdown', k = 'keydown';
      finishNow();
      if (!info || TK.reduced() || tier === 'low') { done(c, 0); return false; }
      ctxNow = c;
      play({ R: info.R, pitch: pitch, rc: info.rc, ra: info.ra, rb: info.rb, sectors: info.sectors, hero: c.hero });
      if (playing) nameSweep(info, w);
      if (c.stars) { c.stars.setIgnite(0, true); M.tween({ from: 0, to: 1, dur: span(w) / IGN, delay: w.lattice[0] + LAG, ease: lin, onUpdate: function (v) { c.stars.setIgnite(v, true); }, tag: 'reveal' }); }
      if (S.replayGlyphs && S.nodeOf) S.replayGlyphs(function (a, b) { var pa = planeOf(a, pitch), pb = planeOf(b, pitch); if (!pa || !pb) return null; return when((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, info, w) + 0.02; });
      if (c.bun && c.bun.grow) { c.bun.grow(0); M.tween({ from: 0, to: 1.2, dur: w.threads[1] - w.threads[0], delay: w.threads[0], ease: lin, onUpdate: function (v) { c.bun.grow(v); }, tag: 'reveal' }); }
      fib(0); M.tween({ from: 0, to: 1, dur: w.solid[1] - w.solid[0], delay: w.solid[0], onUpdate: fib, tag: 'reveal' });
      M.seq([{ at: w.solid[0], fn: function () { if (c.solid) c.solid(); } }, { at: end(w), fn: function () { unbind(); ctxNow = null; } }], 'reveal');
      if (!skipBound) { skipBound = true; g.addEventListener(on, onSkip, true); g.addEventListener(k, onSkip, true); }
      return true;
    }
    function starReveal(n, info, rank01) {
      var w = W(), p = planeOf(n, info ? info.pitch : 0); if (!p || !info) return 0;
      var s = (when(p[0], p[1], info, w) - w.lattice[0]) / span(w);
      return IGN * Math.max(0, Math.min(1, s - 0.02 * (1 - (rank01 || 0))));
    }
    function setTier(v) { tier = v || 'high'; if (tier === 'low') skip(); }
    function stats() {
      var u = lmat.uniforms;
      return { playing: playing, staged: !!ctxNow, t: +t.toFixed(3), names: names.length, unswept: names.filter(function (o) { return !o.on; }).length, plays: plays, sweep: +u.uSweep.value.toFixed(3), fade: +u.uFade.value.toFixed(3), flare: pmat.uniforms.uFlare.value, hero: hero, visible: !!(lines && lines.visible) };
    }
    function dispose() {
      clearNames();
      if (lines) anc.remove(lines); if (pts) S.scene.remove(pts); S.group.remove(anc);
      if (lgeo) lgeo.dispose(); if (pgeo) pgeo.dispose(); lmat.dispose(); pmat.dispose();
    }
    return { play: play, stage: stage, finish: finishNow, starReveal: starReveal, update: update, skip: skip, setTier: setTier, stats: stats, dispose: dispose };
  }

  g.CLSkyReveal = { create: create, when: when };
})(window);
