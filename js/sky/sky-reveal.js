/*!
 * @role reveal
 * @owns js/sky/sky-reveal.js
 * @budget drawcalls=2 points=2 vertices=3600 rtpx=0 passes=0 fps=60
 * @contract deep-sky/3
 * 揭幕线稿构建（参考开篇：线稿逐笔 → 线框 → 溶成实体 → 点睛）：一条自 12 点顺时针的角向扫掠统一节拍——极坐标线框闪现后渐隐、
 * 扫掠臂与外缘彗头、主角星点睛；星座线描出 / 星点亮 / 束丝生长 / 星云实体化按同一时间轴编排（stage）。结束即隐藏；减弱动效 / low 直接终态。
 * 着色器文本在 sky-reveal-glsl.js（CLSkyRevealGLSL）。
 */
(function (g) {
  'use strict';
  var TAU = Math.PI * 2;
  /* IGN：星的点亮阈值上限（sky-stars 在 ignite ≥ 阈值 + 0.06 才全亮，ignite 满 1 时最晚的星也要亮满）；LAG：星比线框前沿晚多少秒；
     SW：扫掠臂在 lattice 窗口里转 1.02 圈（前沿先扫过 12 点再收） */
  var IGN = 0.92, LAG = 0.03, SW = 1.02;

  function lin(k) { return k; }
  function span(w) { return (w.lattice[1] - w.lattice[0]) / SW; }
  /* 扫掠前沿到达天球平面坐标 (u, v) 的时刻（秒，自揭幕起）：盘心团最先（0.12 s 内由内向外），外圈按自 12 点顺时针的角——与线框前沿同一条时间轴 */
  function when(u, v, info, w) {
    var r = Math.sqrt(u * u + v * v), rc = info && info.rc > 0 ? info.rc : 0, l0 = w.lattice[0];
    if (rc && r < rc * 1.02) return l0 + 0.12 * Math.min(1, r / rc);
    var a = Math.atan2(u, v); if (a < 0) a += TAU;
    return l0 + span(w) * a / TAU;
  }
  /* 家位 → 天球平面坐标（toWorld 的逆） */
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
    /* 线框：分区环 + 等距环 · 网格辐条 · 扇区边 · 外缘刻度（平面坐标 / R）+ 扫掠臂 */
    function build(c) {
      var P = [], A = [], K = [], Rr = [], i, j, r, a0, a1, n;
      function seg(x0, y0, x1, y1, ang0, ang1, kind, rr) { P.push(x0, y0, 0, x1, y1, 0); A.push(ang0, ang1); K.push(kind, kind); Rr.push(rr, rr); }
      var R = c.R || 1, rings = [], sec = c.sectors || [];
      function ring(x) { for (var q = 0; q < rings.length; q++) if (Math.abs(rings[q] - x) < 0.05) return; rings.push(x); }
      if (c.rc > 0) ring(c.rc / R);
      if (c.ra > 0) ring(c.ra / R);
      if (c.ra > 0 && c.rb > 0) ring((c.ra + c.rb) / 2 / R);
      if (c.rb > 0) ring(c.rb / R);
      ring(1); [0.2, 0.4, 0.6, 0.8].forEach(ring);   /* 分区环之间补等距环：线框铺满 */
      for (j = 0; j < 24; j++) { a0 = j / 24 * TAU; seg(Math.sin(a0) * 0.05, Math.cos(a0) * 0.05, Math.sin(a0), Math.cos(a0), j / 24, j / 24, 3, 1); }   /* 每 15° 一根网格辐条 */
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
      apply();
      if (t > end(W())) { playing = false; vis(false); }
    }
    function skip() { if (!playing) return false; playing = false; vis(false); return true; }

    /* 编排：线框 → 线描出（τ+0.05）→ 星点亮（τ+0.15）→ 束丝 → 实体化 → 点睛；点按 / 按键一帧到终态（事件照常下传） */
    var skipBound = false, ctxNow = null;
    function onSkip() { finishNow(); }
    /* 挂在 window 的捕获阶段：壳层 / 键位表的按键处理也在 window 捕获、会 stopPropagation，挂 document 就收不到 */
    function unbind() { if (skipBound) { skipBound = false; g.removeEventListener('pointerdown', onSkip, true); g.removeEventListener('keydown', onSkip, true); } }
    /* 组内关系纤维（scene-core 的纤维网格）：密网不进线稿，随星云一起实体化；uLine 是它的整体亮度（宿主建出来为 1，别处不写） */
    function fib(k) { var co = S.core && S.core(), m = co && co.getFiberMat ? co.getFiberMat() : null; if (m && m.uniforms.uLine) m.uniforms.uLine.value = k; }
    function done(c, lines) { if (lines && S.replayGlyphs) S.replayGlyphs(function () { return -1; }); if (c.stars) c.stars.setIgnite(1, true); if (c.bun && c.bun.grow) c.bun.grow(9); fib(1); if (c.solid) c.solid(!!lines); }
    /* 先摘下现场再收尾：finishAll 会顺手跑完序列的收场步（把 ctxNow 清空），不能让它抢在 done 之前 */
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
      /* 点火补间与阈值同一条时间轴：ignite(t) = IGN·(t − l0 − LAG)/span，星 i 在 when_i + LAG 那一刻越过自己的阈值（逐帧直写，不走 sky-stars 的平滑，否则星落后前沿近 90°） */
      if (c.stars) { c.stars.setIgnite(0, true); M.tween({ from: 0, to: 1, dur: span(w) / IGN, delay: w.lattice[0] + LAG, ease: lin, onUpdate: function (v) { c.stars.setIgnite(v, true); }, tag: 'reveal' }); }
      if (S.replayGlyphs && S.nodeOf) S.replayGlyphs(function (a, b) { var pa = planeOf(a, pitch), pb = planeOf(b, pitch); if (!pa || !pb) return null; return when((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, info, w) + 0.02; });
      if (c.bun && c.bun.grow) { c.bun.grow(0); M.tween({ from: 0, to: 1.2, dur: w.threads[1] - w.threads[0], delay: w.threads[0], ease: lin, onUpdate: function (v) { c.bun.grow(v); }, tag: 'reveal' }); }
      fib(0); M.tween({ from: 0, to: 1, dur: w.solid[1] - w.solid[0], delay: w.solid[0], onUpdate: fib, tag: 'reveal' });
      M.seq([{ at: w.solid[0], fn: function () { if (c.solid) c.solid(); } }, { at: end(w), fn: function () { unbind(); ctxNow = null; } }], 'reveal');
      if (!skipBound) { skipBound = true; g.addEventListener(on, onSkip, true); g.addEventListener(k, onSkip, true); }
      return true;
    }
    /* 星的点亮阈值：扫掠序 → 点火进度，亮星略早一拍 */
    function starReveal(n, info, rank01) {
      var w = W(), p = planeOf(n, info ? info.pitch : 0); if (!p || !info) return 0;
      var s = (when(p[0], p[1], info, w) - w.lattice[0]) / span(w);   /* rank01 = 咖位秩（0 = 最亮）：同一角上亮星早一拍 */
      return IGN * Math.max(0, Math.min(1, s - 0.02 * (1 - (rank01 || 0))));
    }
    function setTier(v) { tier = v || 'high'; if (tier === 'low') skip(); }
    function stats() {
      var u = lmat.uniforms;
      return { playing: playing, staged: !!ctxNow, t: +t.toFixed(3), plays: plays, sweep: +u.uSweep.value.toFixed(3), fade: +u.uFade.value.toFixed(3), flare: pmat.uniforms.uFlare.value, hero: hero, visible: !!(lines && lines.visible) };
    }
    function dispose() {
      if (lines) anc.remove(lines); if (pts) S.scene.remove(pts); S.group.remove(anc);
      if (lgeo) lgeo.dispose(); if (pgeo) pgeo.dispose(); lmat.dispose(); pmat.dispose();
    }
    return { play: play, stage: stage, finish: finishNow, starReveal: starReveal, update: update, skip: skip, setTier: setTier, stats: stats, dispose: dispose };
  }

  g.CLSkyReveal = { create: create, when: when };
})(window);
