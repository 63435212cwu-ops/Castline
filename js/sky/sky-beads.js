/*!
 * @role component
 * @owns js/sky/sky-beads.js
 * @budget drawcalls=1 points=24 vertices=24 rtpx=0 passes=0
 * @contract deep-sky/3
 * 常驻数据流（Q8.5）：强关系丝上偶尔滑过一枚数据珠；悬停一颗星时，改从这颗星出发、沿它的关系丝往外发。
 *  · 节拍取 CLSkyTokens.OPEN.bead：同屏至多 max 枚；平时两枚相隔 gap[0]…gap[1] 秒；speed = 每秒走过的丝长比例；悬停先发一枚，之后每 gap[0] / 4 秒一枚。
 *  · 位置直接采样束丝自己的顶点缓冲（每条丝 npt 点 × 2 边，aT 0→1），不另算曲线；每枚 = 白热珠头 + TAIL 个渐隐尾点，一个 Points。
 *  · 走哪条丝也读同一缓冲：aHl > 0.5 = 悬停这颗星的丝，aCk > 0.5 = 强关系丝；几条亮丝共有的那端 = 悬停的星，珠从那端发。
 *  · 束丝只连跨组关系：悬停的星没有束丝（组内关系画成星座线）时，改沿它的星座线发（读星座线的 endA / endB）。
 *  · 跟着束丝淡入淡出（uAlpha）；揭幕生长（uGrow < 1）没长完不发；丝网重建时在路上的珠子作废。
 * 降级：减弱动效（calm / reduced()）或 TIER[tier].beads = 0 一枚不发（在路上的立刻收）。
 * 挂 scene.registerFrameHook，不开自己的 rAF。
 * CLSkyBeads = { setTier(t), stats() }
 */
(function (g) {
  'use strict';
  var T3 = g.THREE;
  if (!T3) return;

  var CAP = 4, TAIL = 5, DU = 0.017, NV = CAP * (1 + TAIL);
  var mesh = null, pts = null, geo = null, mat = null, hooked = null, host = null;
  var npt = 21, seg = 20, stride = 42, nTh = 0, lastDc = -1, hlVer = -1, pool = [];
  var live = [], tNext = 0, clock = 0, lookAt = 0, pin = '', tier = 'high', hot0 = 0;
  var pos = new Float32Array(NV * 3), col = new Float32Array(NV * 3), alp = new Float32Array(NV), siz = new Float32Array(NV);
  var st = { sent: 0, alive: 0, hot: 0, strong: 0, skipped: 0, fromStar: 0, remesh: 0, glyph: 0 };
  var V = new T3.Vector3(), HS = new T3.Vector3(), E = [new T3.Vector3(), new T3.Vector3(), new T3.Vector3(), new T3.Vector3()];
  var hv = null, hvOld = '', gpool = [], gl = null, IM = new T3.Matrix4();

  function B() {
    var K = g.CLSkyTokens, b = K && K.OPEN && K.OPEN.bead;
    return b || { max: 3, speed: 0.34, gap: [2.6, 6] };
  }
  function rnd(a, b) { return a + (b - a) * Math.random(); }

  /* 每条丝的点数从 aT 读，不写死 */
  function shape(aT) {
    var j = 2;
    while (j < aT.length && aT[j] > aT[j - 2]) j += 2;
    if (j >= 4 && j < aT.length) { npt = j / 2; seg = npt - 1; stride = npt * 2; }
  }

  /* 束丝的丝网格：材质带 uFlow + uSpeed，几何带 aT；没找到时每 0.5 s 才再找 */
  function find() {
    var S, got = null;
    if (mesh && mesh.parent) return mesh;
    if (clock < lookAt) return null;
    lookAt = clock + 0.5;
    S = g.CLApp && CLApp.scene && CLApp.scene();
    if (!S || !S.scene) return null;
    S.scene.traverse(function (o) {
      var u = o.material && o.material.uniforms;
      if (!got && u && u.uFlow && u.uSpeed && o.geometry && o.geometry.attributes && o.geometry.attributes.aT) got = o;
    });
    if (got && got !== mesh) { live.length = 0; lastDc = -1; st.remesh++; shape(got.geometry.attributes.aT.array); }
    mesh = got;
    return mesh;
  }

  function ensure() {
    var m = find();
    if (!m || !m.parent) return null;
    if (pts && host === m.parent) return pts;
    if (pts && pts.parent) pts.parent.remove(pts);
    host = m.parent;
    geo = new T3.BufferGeometry();
    function at(n, a, k) { geo.setAttribute(n, new T3.BufferAttribute(a, k).setUsage(T3.DynamicDrawUsage)); }
    at('position', pos, 3); at('aCol', col, 3); at('aA', alp, 1); at('aS', siz, 1);
    geo.boundingSphere = new T3.Sphere(new T3.Vector3(), 4);
    /* 珠头 aS ≥ 12：白热芯 + 丝色辉光；尾点只有丝色、越往后越小越淡 */
    mat = new T3.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest: false,
      blending: T3.AdditiveBlending, premultipliedAlpha: true,
      uniforms: { uDpr: { value: 1 } },
      vertexShader: ['attribute vec3 aCol;', 'attribute float aA;', 'attribute float aS;', 'uniform float uDpr;',
        'varying vec3 vC;', 'varying float vA;', 'varying float vH;',
        'void main(){vC=aCol;vA=aA;vH=step(12.0,aS);',
        'gl_PointSize=aS*uDpr;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}'].join(''),
      fragmentShader: ['varying vec3 vC;', 'varying float vA;', 'varying float vH;',
        'void main(){float r=length(gl_PointCoord*2.0-1.0);if(r>1.0)discard;',
        'float h=exp(-r*r*5.5);float c=vH*(1.0-smoothstep(0.0,0.3,r));',
        'vec3 o=(vC*h*1.15+vec3(1.0,0.97,0.92)*c*1.25)*vA;gl_FragColor=vec4(o,max(h,c)*vA);}'].join('')
    });
    pts = new T3.Points(geo, mat);
    pts.frustumCulled = false;
    pts.renderOrder = 6;
    host.add(pts);
    return pts;
  }

  /* 丝 i 上参数 u（0…1）处的中心线点（两边顶点同位，取一边即可） */
  function sample(p, i, u, out) {
    var s = u * seg, k = s | 0, f, o0;
    if (k >= seg) k = seg - 1;
    if (k < 0) k = 0;
    f = s - k;
    o0 = (i * stride + k * 2) * 3;
    return out.set(p[o0] + (p[o0 + 6] - p[o0]) * f, p[o0 + 1] + (p[o0 + 7] - p[o0 + 1]) * f, p[o0 + 2] + (p[o0 + 8] - p[o0 + 2]) * f);
  }

  /* 可发的丝：优先悬停亮起的那几条，没有就在强关系丝里挑；aHl 改写过或丝网重建后才重扫 */
  function scan(at) {
    var hl = at.aHl && at.aHl.array, ck = at.aCk && at.aCk.array, hot = [], strong = [], i, b;
    for (i = 0; i < nTh; i++) {
      b = i * stride;
      if (hl && hl[b] > 0.5) hot.push(i);
      else if (ck && ck[b] > 0.5) strong.push(i);
    }
    st.hot = hot.length; st.strong = strong.length;
    pool = hot.length ? hot : strong;
  }

  /* 悬停星的星座线（getGlyphSegs 与网格同序，每段 gs 个浮点） */
  var gsegs = [], gs = 78;
  function gscan() {
    var S = g.CLScene && CLScene.current, c = S && S.core ? S.core() : null, k = 'c:' + hv, i;
    gl = c && c.getGlyphLine ? c.getGlyphLine() : null; gsegs = gl && c.getGlyphSegs ? c.getGlyphSegs() : []; gpool = [];
    if (gl && gsegs.length) gs = (gl.geometry.attributes.endA.count / gsegs.length) * 3;
    for (i = 0; hv && i < gsegs.length; i++) if (gsegs[i].a.key === k || gsegs[i].b.key === k) gpool.push(i);
    hvOld = hv || '';
  }
  function gsample(i, u, out) {
    var a = gl.geometry.attributes, A = a.endA.array, Z = a.endB.array, q = i * gs;
    return out.set(A[q] + (Z[q] - A[q]) * u, A[q + 1] + (Z[q + 1] - A[q + 1]) * u, A[q + 2] + (Z[q + 2] - A[q + 2]) * u).applyMatrix4(gl.matrixWorld).applyMatrix4(IM);
  }

  /* 悬停的星 = 两条亮丝共有的那一端 */
  function star(p) {
    var best = 1e9, k, m, d;
    sample(p, pool[0], 0, E[0]); sample(p, pool[0], 1, E[1]); sample(p, pool[1], 0, E[2]); sample(p, pool[1], 1, E[3]);
    for (k = 0; k < 2; k++) for (m = 2; m < 4; m++) { d = E[k].distanceToSquared(E[m]); if (d < best) { best = d; HS.copy(E[k]); } }
  }

  function spawn(p, c) {
    var i, dir = 1, b, q;
    if (!st.hot && gpool.length) {
      i = gpool[(Math.random() * gpool.length) | 0]; q = gsegs[i]; dir = q.a.key === 'c:' + hv ? 1 : -1;
      live.push({ g: 1, i: i, d: dir, u: dir > 0 ? 0 : 1, v: B().speed * rnd(0.85, 1.2), c: [q.c.r, q.c.g, q.c.b], t0: clock, a: q.a.key, b: q.b.key });
      st.sent++; st.fromStar++; st.glyph++;
      return;
    }
    if (!pool.length) return;
    i = pool[(Math.random() * pool.length) | 0];
    if (st.hot > 1) {
      star(p); sample(p, i, 0, E[0]); sample(p, i, 1, E[1]);
      dir = E[0].distanceToSquared(HS) <= E[1].distanceToSquared(HS) ? 1 : -1;
      st.fromStar++;
    }
    b = i * stride * 3;
    live.push({ i: i, d: dir, u: dir > 0 ? 0 : 1, v: B().speed * rnd(0.85, 1.2), c: c ? [c[b], c[b + 1], c[b + 2]] : [1, 1, 1], t0: clock });
    st.sent++;
  }

  function off(calm) {
    var K = g.CLSkyTokens, bt = K && K.TIER && K.TIER[tier];
    return !!calm || !!(K && K.reduced && K.reduced()) || (bt ? !bt.beads : tier === 'low');
  }

  function frame(dt, tAcc, tAnim, calm, degrade) {
    var P, K = g.CLSkyTokens, at, p, u, i, j, o, n = 0, bd, dc, w, a, uu, vi, fade, gr, S;
    dt = (dt > 0 && dt < 0.5) ? dt : 0.016;
    clock += dt;
    P = ensure();
    if (!P) return;
    at = mesh.geometry.attributes; p = at.position.array; u = mesh.material.uniforms;
    tier = pin || (K && K.tierOf ? K.tierOf(degrade | 0) : 'high');
    dc = mesh.geometry.drawRange.count;
    if (dc !== lastDc) {
      lastDc = dc; live.length = 0; hlVer = -1;
      nTh = isFinite(dc) ? (dc / (seg * 6)) | 0 : (at.position.count / stride) | 0;
    }
    if (hlVer < 0 || (at.aHl && at.aHl.version !== hlVer)) {
      hlVer = at.aHl ? at.aHl.version : 0;
      scan(at);
      if (st.hot && !hot0) tNext = clock;
      hot0 = st.hot;
    }
    if ((hv || '') !== hvOld || (gl && !gl.parent)) {
      if (gl && !gl.parent) for (i = live.length - 1; i >= 0; i--) if (live[i].g) live.splice(i, 1);
      gscan(); if (gpool.length && !st.hot) tNext = clock;
    }
    bd = B(); gr = u.uGrow;
    if (off(calm)) { if (live.length) { live.length = 0; st.skipped++; } }
    else {
      if (clock >= tNext && live.length < Math.min(CAP, bd.max | 0) && !(gr && gr.value < 0.999)) {
        spawn(p, at.aCol && at.aCol.array);
        tNext = clock + (st.hot || gpool.length ? Math.max(0.35, bd.gap[0] * 0.25) : rnd(bd.gap[0], bd.gap[1]));
      }
      for (i = live.length - 1; i >= 0; i--) {
        o = live[i]; o.u += o.d * o.v * dt;
        if (o.u > 1 || o.u < 0) live.splice(i, 1);
      }
    }
    fade = u.uAlpha ? u.uAlpha.value : 1;
    if (gl) IM.copy(host.matrixWorld).invert();
    for (i = 0; i < CAP; i++) {
      o = i < live.length ? live[i] : null;
      w = o ? (o.d > 0 ? o.u : 1 - o.u) : 0;
      /* 两头淡入淡出 */
      a = o ? Math.min(1, w / 0.1) * Math.min(1, (1 - w) / 0.16) * fade : 0;
      if (a > 0) n++;
      for (j = 0; j <= TAIL; j++) {
        vi = i * (1 + TAIL) + j;
        uu = o ? o.u - o.d * DU * j : -1;
        if (a <= 0 || uu < 0 || uu > 1) { alp[vi] = 0; siz[vi] = 0; continue; }
        if (o.g) gsample(o.i, uu, V); else sample(p, o.i, uu, V);
        pos[vi * 3] = V.x; pos[vi * 3 + 1] = V.y; pos[vi * 3 + 2] = V.z;
        col[vi * 3] = o.c[0]; col[vi * 3 + 1] = o.c[1]; col[vi * 3 + 2] = o.c[2];
        alp[vi] = j ? a * 0.8 * Math.pow(1 - j / (TAIL + 1), 1.6) : a;
        siz[vi] = j ? 8.5 * Math.pow(0.84, j - 1) : 14;
      }
    }
    st.alive = n;
    geo.attributes.position.needsUpdate = true;
    geo.attributes.aCol.needsUpdate = true;
    geo.attributes.aA.needsUpdate = true;
    geo.attributes.aS.needsUpdate = true;
    P.visible = mesh.visible && n > 0;
    S = g.CLApp && CLApp.scene && CLApp.scene();
    if (S && S.renderer && mat) mat.uniforms.uDpr.value = S.renderer.getPixelRatio() || 1;
  }

  function hook() {
    var sc = g.CLScene && CLScene.current;
    if (!sc || !sc.registerFrameHook || sc === hooked) return;
    hooked = sc; sc.registerFrameHook(frame);
    if (sc.on) sc.on('hover', function (e) { hv = e && e.name ? e.name : null; });
  }
  hook();
  g.addEventListener('cl-scene-ready', hook, false);
  new MutationObserver(hook).observe(g.document.body, { attributes: true, attributeFilter: ['class'] });

  g.CLSkyBeads = {
    /* 测试钉档；空串 = 跟随宿主 */
    setTier: function (t) { pin = t || ''; },
    stats: function () {
      var o = {}, k;
      for (k in st) o[k] = st[k];
      o.mesh = !!mesh; o.tier = tier; o.max = Math.min(CAP, B().max | 0); o.threads = nTh; o.npt = npt;
      /* 在路上的珠：哪条丝、缓冲里的强弱 / 悬停标记（O6 验收读）；星座线珠 g = 1 + 两端星 */
      var at = mesh && mesh.geometry.attributes, ck = at && at.aCk && at.aCk.array, hl = at && at.aHl && at.aHl.array;
      o.live = live.map(function (x) { var b = x.i * stride; return x.g ? { g: 1, i: x.i, d: x.d, u: +x.u.toFixed(3), age: +(clock - x.t0).toFixed(3), ck: -1, hl: 1, a: x.a, b: x.b } : { i: x.i, d: x.d, u: +x.u.toFixed(3), age: +(clock - x.t0).toFixed(3), ck: ck ? ck[b] : -1, hl: hl ? hl[b] : -1 }; });
      return o;
    }
  };
})(window);
