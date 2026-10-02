/*! sky-rings.js — 星盘光环：弧带 / 事件珠 / 刻度环（layer 3，3 drawcall）
 * @role rings
 * @owns js/sky/sky-rings.js
 * @budget drawcalls=3 vertices=160000 points=6000 passes=0 rtpx=0 shader=yes
 * @contract deep-sky/1
 * 降级：reducedMotion 通路 = CLSkyTokens.reduced()（prefers-reduced-motion / body.skylab-still）
 * 一帧到终态并冻结 uTime/uSweep；setTier('low')（hardwareConcurrency<=4 自动 low）不建事件珠、
 * uSweepK→0，弧带无循环扫光。
 */
(function (g) {
  'use strict';
  var K5 = 'main,named,quiet,bezel,sweepK'.split(',');
  var U5 = 'uAMain,uANamed,uAQuiet,uABezel,uSweepK'.split(',');
  var UN = 'uDpr,uTime,uSweep,uReveal,uFront,uEmph,uEmphMain,uCur,uFlow,uBackdrop'.split(',').concat(U5);
  /* 背景态只留可发现的残弧；完整时间环只在剧情态出现，避免外围环抢星座主视觉。 */
  var S3 = { hidden: [0, 0, 0, 0, 0], backdrop: [0.10, 0, 0, 0.06, 0.28], plot: [1, 0.7, 0.8, 0.75, 0] };
  var RS = 'position3,aPrev3,aNext3,aSide1,aC1,aC01,aC11,aKind1,aLine1,aMain1,aWpx1,aGlow1,aCol3';
  var BS = 'position3,aC1,aC01,aC11,aKind1,aLine1,aMain1,aCol3,aPx1';
  var TS = 'position3,aC1,aB1';
  var GL = g.CLSkyRingsGLSL.rings, RV = GL.RV, RF = GL.RF, BV = GL.BV, BF = GL.BF, TV = GL.TV, TF = GL.TF;   /* 着色器文本在 sky-rings-glsl.js */
  var MV = 160000, MP = 6000, ST = 0.02;

  function rgb(h, k) {
    var c = g.CLSkyUtil.rgb(h), i;
    if (k) for (i = 0; i < 3; i++) c[i] += (1 - c[i]) * k;
    return c;
  }
  function v3(h) { var c = rgb(h); return new g.THREE.Vector3(c[0], c[1], c[2]); }
  function fill(A, v, n) { while (n--) { A.push(v); } }
  function pt(A, r, a, z) { A.push(r * Math.cos(a), r * Math.sin(a), z || 0); }
  function aa(n) { var a = []; while (n--) { a.push([]); } return a; }
  function att(gr, sp, arrs) {
    var s = sp.split(','), i, n, e;
    for (i = 0; i < s.length; i++) {
      n = s[i]; e = n.length - 1;
      gr.setAttribute(n.slice(0, e), new g.THREE.BufferAttribute(new Float32Array(arrs[i]), n.charAt(e) | 0));
    }
  }

  function create(a, b) {
    var W = g.THREE, TK = g.CLSkyTokens;
    var S = (b && a) ? a : (b || a).scene;
    var anchor = (b || a).anchor || (S && S.group);
    if (!W || !TK || !anchor) { return null; }
    var LD = (TK.LAYER_DISC === undefined) ? 3 : TK.LAYER_DISC;
    var C = TK.C, LP = TK.LOOP, T0 = TK.TIER || {};
    var tau = Math.max(1e-4, ((TK.DUR && TK.DUR.focus) || 0.9) / 3);
    var i, j, k, t, oR = null, oB = null, oT = null, v2 = null, d = null;
    var nc = g.navigator && g.navigator.hardwareConcurrency;
    var st = { tier: (nc && nc <= 4) ? 'low' : 'high', state: 'plot', reveal: 1, emph: -1, em: -1, cursor: -1 };
    var tg = { main: 1, named: 0.85, quiet: 1, bezel: 0.75, sweepK: 0 };
    var cv = { main: 0, named: 0, quiet: 0, bezel: 0, sweepK: 0 };
    var q = { items: 0, beads: 0, ticks: 0, verts: 0 }, tgFlow = 1, cvFlow = 0;
    var u = { uRes: { value: new W.Vector2(1, 1) } };
    for (i = 0; i < UN.length; i++) { u[UN[i]] = { value: 0 }; }
    u.uDpr.value = u.uReveal.value = 1;
    u.uEmph.value = u.uEmphMain.value = u.uCur.value = -1;
    var uT = { uABezel: u.uABezel, uReveal: u.uReveal, uBackdrop: u.uBackdrop, cDim: { value: v3(C.BRASS_DIM) }, cHot: { value: v3(C.BRASS) } };

    function M(vs, fs, uu) {
      return new W.ShaderMaterial({
        uniforms: uu || u, vertexShader: vs, fragmentShader: fs,
        transparent: true, depthWrite: false, depthTest: false, side: W.DoubleSide, blending: W.AdditiveBlending, premultipliedAlpha: true
      });
    }
    function P(o) { o.frustumCulled = false; o.renderOrder = 1; o.layers.set(LD); anchor.add(o); return o; }
    function to(o, r, lo) {
      for (i = 0; i < 5; i++) { o[K5[i]] = (i === 4 && lo) ? 0 : r[i]; }
    }
    function drop() {
      var ar = [oR, oB, oT];
      for (i = 0; i < 3; i++) {
        if (!ar[i]) { continue; }
        if (ar[i].parent) { ar[i].parent.remove(ar[i]); }
        ar[i].geometry.dispose(); ar[i].material.dispose(); ar[i] = null;
      }
      q.beads = 0; q.verts = 0;
    }
    function snap() { to(cv, S3[st.state] || S3.plot, st.tier === 'low'); u.uBackdrop.value = st.state === 'backdrop' ? 1 : 0; }

    function build(desc) {
      drop();
      d = desc || null;
      q.items = 0; q.ticks = 0;
      if (!d) { return null; }
      var nCh = Math.max(1, d.nCh || 1), A0 = d.angle0, A1 = d.angle1, den = (A0 - A1) || 1;
      function C2(x) { return (A0 - x) / den; }
      var I = d.items || [], R = aa(13), B = aa(9), T = aa(3), IX = [], nv = 0, nb = 0;
      var CV = [0, 0, 0, 0, 0, 0, 0], TB = T0[st.tier] ? T0[st.tier].beads === 1 : st.tier !== 'low';
      for (i = 0; i < I.length; i++) {
        var o = I[i];
        var kd = (o.kind === 'main') ? 0 : ((o.kind === 'named') ? 1 : 2);
        var gl = (kd === 0) ? 6 : ((kd === 1) ? 3 : 1.5);
        var hc = (o.color === undefined) ? C.BRASS : o.color, c3 = rgb(hc);
        var n = Math.max(2, Math.ceil(Math.abs(o.a1 - o.a0) / ST) + 1);
        if (n * 2 > MV - nv) { n = (MV - nv) >> 1; }
        if (n < 2) { break; }
        var sp = (o.a1 - o.a0) / (n - 1), N = n * 2, s0 = nv, a, ap, an, bs, bd, c4, b, bN = 0;
        var mi = (typeof o.mainIdx === 'number') ? o.mainIdx : (kd ? -1 : i), oz = o.z || 0;
        for (j = 0; j < n; j++) {
          a = o.a0 + sp * j;
          ap = j > 0 ? a - sp : a;          /* 相邻点：弧可顺可逆（数学角递减 = 顺时针），端点取自身，不能用 min/max 夹 */
          an = j < n - 1 ? a + sp : a;
          for (t = 0; t < 2; t++) { pt(R[0], o.r, a, oz); pt(R[1], o.r, ap, oz); pt(R[2], o.r, an, oz); }
          R[3].push(-1, 1);
          R[4].push(C2(a), C2(a));
        }
        CV[0] = o.c0 / nCh; CV[1] = (o.c1 + 1) / nCh; CV[2] = kd; CV[3] = i;
        CV[4] = mi; CV[5] = o.w; CV[6] = gl;
        for (j = 5; j < 12; j++) { fill(R[j], CV[j - 5], N); }
        for (t = 0; t < N; t++) { R[12].push(c3[0], c3[1], c3[2]); }
        for (j = 0; j < n - 1; j++) {
          b = s0 + j * 2;
          IX.push(b, b + 1, b + 2, b + 1, b + 3, b + 2);
        }
        nv += N;
        bs = o.beads;
        if (bs && kd < 2 && TB) {
          for (j = 0; j < bs.length && nb < MP; j++) {
            bd = bs[j];
            c4 = bd.key ? rgb(C.BRASS_HOT) : rgb(hc, 0.3);
            pt(B[0], o.r, bd.a, oz);
            B[1].push(C2(bd.a));
            B[7].push(c4[0], c4[1], c4[2]);
            B[8].push((bd.key ? 1.5 : 1) * (kd ? 3 : 4));
            bN++; nb++;
          }
          if (bN) {
            CV[4] = mi;
            for (j = 0; j < 5; j++) { fill(B[j + 2], CV[j], bN); }
          }
        }
      }
      q.items = I.length; q.beads = nb; q.verts = nv;
      if (nv > 0) {
        var gr = new W.BufferGeometry();
        att(gr, RS, R);
        gr.setIndex(IX);
        oR = P(new W.Mesh(gr, M(RV, RF)));
      }
      if (nb > 0) {
        var gb = new W.BufferGeometry();
        att(gb, BS, B);
        oB = P(new W.Points(gb, M(BV, BF)));
      }
      var rB = d.rBez, zB = d.zBez || 0;
      if (rB > 0) {
        var sg = Math.max(2, Math.ceil(Math.abs(A0 - A1) / ST)), a0, a1, ln, tl = d.tickLen || {}, tks = d.ticks || [];
        for (k = 0; k < sg; k++) {
          a0 = A0 + (A1 - A0) * (k / sg);
          a1 = A0 + (A1 - A0) * ((k + 1) / sg);
          pt(T[0], rB, a0, zB); pt(T[0], rB, a1, zB);
          T[1].push(C2(a0), C2(a1));
          T[2].push(0.5, 0.5);
        }
        for (k = 0; k < tks.length; k++) {
          ln = tks[k].major ? (tl.major || 0) : (tl.minor || 0);
          if (ln > 0) {
            pt(T[0], rB, tks[k].a, zB); pt(T[0], rB + ln, tks[k].a, zB);
            T[1].push(C2(tks[k].a), C2(tks[k].a));
            /* 一条刻度两顶点，亮度属性也要成对：短缓冲会让 WebGL 拒绝整批刻度环。 */
            var tickB = tks[k].major ? 1 : 0.6;
            T[2].push(tickB, tickB);
          }
        }
        q.ticks = T[1].length;
        var gt = new W.BufferGeometry();
        att(gt, TS, T);
        oT = P(new W.LineSegments(gt, M(TV, TF, uT)));
      }
      return stats();
    }

    function setState(s) {
      st.state = s;
      to(tg, S3[s] || S3.plot, 0);
      tgFlow = s === 'plot' ? 1 : 0;
      if (TK.reduced()) { snap(); }
    }
    function reveal(x) { st.reveal = x; u.uReveal.value = x; u.uFront.value = (x < 0.999) ? 1 : 0; }
    function setEmph(l, mn) {
      st.emph = (l == null) ? -1 : l;
      st.em = (mn == null) ? -1 : mn;
      u.uEmph.value = st.emph; u.uEmphMain.value = st.em;
    }
    function setCursor(x) { st.cursor = (x == null) ? -1 : x; u.uCur.value = st.cursor; }
    function setTier(t) {
      st.tier = t;
      if (d) { build(d); }
      if (TK.reduced()) { snap(); }
    }
    function update(dt, tAnim) {
      var red = TK.reduced();
      var k = red ? 1 : 1 - Math.exp(-((dt > 0 && dt < 1) ? dt : 0) / tau);
      var lo = st.tier === 'low', nm;
      for (i = 0; i < 5; i++) {
        nm = K5[i];
        cv[nm] += ((i === 4 && lo ? 0 : tg[nm]) - cv[nm]) * k;
        u[U5[i]].value = cv[nm];
      }
      cvFlow += ((red || lo ? 0 : tgFlow) - cvFlow) * k; u.uFlow.value = cvFlow;   /* 减弱动效 / low 档不流 */
      u.uBackdrop.value += ((st.state === 'backdrop' ? 1 : 0) - u.uBackdrop.value) * k;
      if (!red) {
        u.uTime.value = tAnim || 0;
        u.uSweep.value = ((tAnim || 0) / (LP.sweep || 40)) % 1;
      }
      if (S && S.renderer) {
        if (!v2) { v2 = new W.Vector2(); }
        S.renderer.getDrawingBufferSize(v2);
        u.uRes.value.copy(v2);
        u.uDpr.value = S.renderer.getPixelRatio();
      }
    }
    function stats() {
      return {
        items: q.items, beads: q.beads, ticks: q.ticks, verts: q.verts, state: st.state,
        reveal: st.reveal, emph: st.emph, cursor: st.cursor
      };
    }
    function dispose() { drop(); d = null; v2 = null; q.items = 0; q.ticks = 0; }

    return {
      build: build, setState: setState, reveal: reveal, setEmph: setEmph,
      setCursor: setCursor, update: update, setTier: setTier, stats: stats, dispose: dispose
    };
  }

  g.CLSkyRings = { create: create };
})(window);
