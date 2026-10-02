/* Castline · plot-fork.js — v32 主线换手的 Y 形转正（window.CLPlotFork）
 *
 * 用户要看清的一件事：**主线未完的时候，新主线先以支线的姿态从老主干上分出去，
 * 跑一段之后转正成新主干；老主干在交接点之后收细成一截残枝。**
 * 所以这一层画三样，每样都对应那句话里的一段：
 *   引枝 = 「先以支线的姿态分出去」（粗细从细到粗单调递增 —— 正在变成主干）
 *   转正标 = 「转正」（朝生长方向的三角楔 + 一段加粗套管）
 *   残枝 = 「老主干没走完」（去色、收细、末端散丝）
 *
 * 不写 GLSL：仓里出过着色器编译失败导致整屏纯黑而 jserr 仍为 none 的事故。
 */
(function () {
  'use strict';

  var RO = -48;                    // 在巨树之上、星点之下
  var N = 6;                       // 管的环分段
  var FRAY = 4;                    // 残枝末端散几根丝

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  function vadd(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vmul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function vnorm(a) {
    var L = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0];
  }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  var T = null, O = null, host = null, mIn = null, mMark = null, mStub = null;
  var _c = null, _c2 = null, deg = 0, onK = 1, muted = false, vis = true;
  var nFork = 0, nBorn = 0, nStub = 0, retry = 0, reduce = false, tAcc = 0, ready = false;
  var logical = false;   // v45：严格来源结构 → 统一逻辑巨树接管，本层守空不画接力边

  function anchorRoot() {
    var A = window.CLTreeAnchor;
    if (A && A.ready && tryFn(A.ready) && A.root) { var r = tryFn(A.root); if (r) return r; }
    var g = window.CLTreeGhost;
    if (g && g.stats && tryFn(g.stats) && O && O.group) return null;   // ghost 自建了根也拿不到，只能等 anchor
    return null;
  }

  function dataNow() {
    var tree = (window.CLStory && CLStory.get) ? tryFn(CLStory.get) : null;
    if (!tree || tree.ok !== true) return null;
    // v45 严格来源结构：统一逻辑巨树已按来源线渲染接力关系，本层不得再叠一层独立 Y 形。
    // strictTopology 是 A 层权威信号；sh.logical 是 B 层兜底信号（B 未就绪时仍能认出来）。
    if (tree.strictTopology === true) { logical = true; return null; }
    if (!window.CLPromote || !CLPromote.compute) return null;
    if (!window.CLTreeShape || !CLTreeShape.build) return null;
    var sh = tryFn(function () { return CLTreeShape.build(tree); });
    if (sh && sh.logical === true) { logical = true; return null; }
    logical = false;
    var pr = tryFn(function () { return CLPromote.compute(tree); });
    if (!pr || !pr.ok || !pr.forks || !pr.forks.length) return null;
    if (!sh || !sh.ok || !sh.trunk || !sh.trunk.pts.length) return null;
    return { forks: pr.forks, shape: sh };
  }

  /** 主干上 t 处的点 / 半径。这里必须**复用巨树同一副 trunk.pts**，
   *  自己再拟合一条曲线的话，树形参数一改 Y 形就飘到树外面去了。 */
  function mkTrunk(sh) {
    var pts = sh.trunk.pts, rr = sh.trunk.r, n = pts.length;
    return {
      at: function (t) {
        var u = clamp(num(t, 0), 0, 1) * (n - 1), a = Math.floor(u), b = Math.min(n - 1, a + 1), f = u - a;
        return vadd(vmul(pts[a], 1 - f), vmul(pts[b], f));
      },
      r: function (t) {
        var u = clamp(num(t, 0), 0, 1) * (n - 1), a = Math.floor(u), b = Math.min(n - 1, a + 1), f = u - a;
        return num(rr[a], 0.01) * (1 - f) + num(rr[b], 0.01) * f;
      }
    };
  }

  function radOf(az) { return [Math.cos(az), 0, Math.sin(az)]; }

  function cat(cps, n2) {
    if (cps.length < 2) return [cps[0] || [0, 0, 0]];
    var p = [cps[0]].concat(cps, [cps[cps.length - 1]]), out = [], i, seg = cps.length - 1;
    for (i = 0; i < n2; i++) {
      var u = seg * (i / (n2 - 1)), k = Math.min(seg - 1, Math.floor(u)), f = u - k;
      var p0 = p[k], p1 = p[k + 1], p2 = p[k + 2], p3 = p[k + 3], f2 = f * f, f3 = f2 * f, d, o = [0, 0, 0];
      for (d = 0; d < 3; d++) {
        o[d] = 0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * f +
               (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * f2 +
               (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * f3);
      }
      out.push(o);
    }
    return out;
  }

  function colMix(hex, k) {
    _c.setHex(hex >>> 0);
    _c2.setHex(0x08050f); _c.lerp(_c2, 0.22);
    return { r: _c.r * k, g: _c.g * k, b: _c.b * k };
  }

  /** 环挤出一根变半径的管，颜色沿长度在两色之间过渡，亮度可逐站给。 */
  function tube(acc, pts, rads, colA, colB, alphas) {
    var i, q, nst = pts.length;
    if (nst < 2) return;
    var base = acc.p.length / 3;
    for (i = 0; i < nst; i++) {
      var f = i / (nst - 1), p = pts[i], rad = rads[i];
      var a = pts[Math.max(0, i - 1)], b = pts[Math.min(nst - 1, i + 1)];
      var tan = vnorm(vsub(b, a));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      var al = alphas ? alphas[i] : 1;
      var cr = colA.r + (colB.r - colA.r) * f, cg = colA.g + (colB.g - colA.g) * f, cb = colA.b + (colB.b - colA.b) * f;
      for (q = 0; q < N; q++) {
        var th = q / N * Math.PI * 2, cth = Math.cos(th), sth = Math.sin(th);
        acc.p.push(p[0] + (U[0] * cth + W[0] * sth) * rad,
                   p[1] + (U[1] * cth + W[1] * sth) * rad,
                   p[2] + (U[2] * cth + W[2] * sth) * rad);
        var m = (0.4 + 0.6 * sth * sth) * al;
        acc.c.push(cr * m, cg * m, cb * m);
      }
    }
    for (i = 0; i < nst - 1; i++) {
      var r0 = base + i * N, r1 = base + (i + 1) * N;
      for (q = 0; q < N; q++) {
        var q2 = (q + 1) % N;
        acc.i.push(r0 + q, r1 + q, r0 + q2, r0 + q2, r1 + q, r1 + q2);
      }
    }
  }

  function mesh(acc) {
    if (!acc.p.length) return null;
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.Float32BufferAttribute(acc.p, 3));
    g.setAttribute('color', new T.Float32BufferAttribute(acc.c, 3));
    g.setIndex(acc.i);
    var mt = new T.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0,
      blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide, fog: false });
    var m = new T.Mesh(g, mt);
    m.frustumCulled = false;
    m.renderOrder = RO;
    m.raycast = function () {};
    m.userData.clLayer = 'plot-fork';
    return m;
  }

  function clearGeom() {
    [mIn, mMark, mStub].forEach(function (m) {
      if (!m) return;
      if (m.parent) m.parent.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) m.material.dispose();
    });
    mIn = mMark = mStub = null; ready = false;
  }

  function rebuild() {
    if (!T || !O) return false;
    host = anchorRoot();
    if (!host) return false;
    var D = dataNow();
    if (!D) { if (logical) clearGeom(); return false; }   // 切到严格模式时清掉可能残留的旧 Y 形
    clearGeom();
    var TR = mkTrunk(D.shape), forks = D.forks, i, j;
    var aIn = { p: [], c: [], i: [] }, aMk = { p: [], c: [], i: [] }, aSt = { p: [], c: [], i: [] };
    nFork = forks.length; nBorn = 0; nStub = 0;

    for (i = 0; i < forks.length; i++) {
      var F = forks[i];
      var tF = clamp(num(F.tFork, 0), 0, 1), tP = clamp(num(F.tPromote, 1), 0, 1);
      if (tP <= tF) tP = Math.min(1, tF + 0.02);
      var az = num(F.az, 0), rad = radOf(az);
      var rF = TR.r(tF), rP = TR.r(tP);
      var born = !!F.born;
      if (born) nBorn++;

      // ── 引枝：从主干上射出、再回到主干；粗细单调递增，颜色由老段过渡到新段
      var mid = (tF + tP) * 0.5;
      var p0 = vadd(TR.at(tF), vmul(rad, rF * 0.9));
      var p1 = vadd(vadd(TR.at(mid), vmul(rad, TR.r(mid) * 3.2)), [0, 0.02, 0]);
      var p2 = vadd(TR.at(tP), vmul(rad, rP * 1.1));
      var pin = cat([p0, p1, p2], 18), rin = [], ain = [];
      for (j = 0; j < pin.length; j++) {
        var f2 = j / (pin.length - 1);
        rin.push(rF * 0.42 + (rP * 1.0 - rF * 0.42) * f2);
        // born=false 的引枝画成虚段：数据里没有重叠，就不该假装它跑过一段
        ain.push(born ? 1 : ((j % 6) < 3 ? 0.65 : 0.12));
      }
      tube(aIn, pin, rin, colMix(num(F.colorPrev, 0xffb45c), born ? 1 : 0.65),
        colMix(num(F.color, 0xffb45c), born ? 1 : 0.65), ain);

      // ── 转正标：朝 +Y 的三角楔 + 一段加粗套管（不画环，接续环别处已经有了）
      var cP = colMix(num(F.color, 0xffb45c), 1.25);
      var apex = vadd(TR.at(Math.min(1, tP + 0.026)), [0, rP * 1.2, 0]);
      var wA = vadd(TR.at(tP), vmul(rad, rP * 2.6));
      var wB = vadd(TR.at(tP), vmul(vmul(rad, -1), rP * 2.6));
      var bs = aMk.p.length / 3;
      [apex, wA, wB].forEach(function (p) { aMk.p.push(p[0], p[1], p[2]); aMk.c.push(cP.r, cP.g, cP.b); });
      aMk.i.push(bs, bs + 1, bs + 2);
      var sl = [], slr = [];
      for (j = 0; j <= 4; j++) {
        var tt = tP + 0.03 * (j / 4);
        sl.push(TR.at(Math.min(1, tt)));
        slr.push(TR.r(Math.min(1, tt)) * (1.25 - 0.25 * (j / 4)));
      }
      tube(aMk, sl, slr, cP, colMix(num(F.color, 0xffb45c), 0.7), null);

      // ── 残枝：老主干没走完的那一截。去色 = 「它不再是主角了」
      var t0s = clamp(num(F.tStub0, tP), 0, 1), t1s = num(F.tStub1, tP + 0.05);
      var slen = Math.max(0.03, t1s - t0s);
      var azS = num(F.azStub, az + Math.PI), radS = radOf(azS);
      var dirS = vnorm(vadd(vmul(radS, Math.sin(1.25)), [0, Math.cos(1.25), 0]));
      var s0 = vadd(TR.at(t0s), vmul(radS, TR.r(t0s) * 0.9));
      var ps = cat([s0, vadd(s0, vmul(dirS, slen * 0.45)),
        vadd(vadd(s0, vmul(dirS, slen * 0.8)), [0, -slen * 0.10, 0]),
        vadd(vadd(s0, vmul(dirS, slen * 1.0)), [0, -slen * 0.24, 0])], 12);
      var rs = [];
      for (j = 0; j < ps.length; j++) rs.push(rP * 0.55 * Math.pow(1 - j / (ps.length - 1), 1.5) + rP * 0.02);
      _c.setHex(num(F.colorPrev, 0xffb45c) >>> 0);
      var hsl = { h: 0, s: 0, l: 0 };
      _c.getHSL(hsl);
      _c.setHSL(hsl.h, hsl.s * 0.25, hsl.l * 0.55);
      var cS = { r: _c.r, g: _c.g, b: _c.b };
      tube(aSt, ps, rs, cS, { r: cS.r * 0.2, g: cS.g * 0.2, b: cS.b * 0.2 }, null);
      nStub++;
      // 末端散丝：断掉的线不该是一个干净的切口
      var tip = ps[ps.length - 1];
      for (j = 0; j < FRAY; j++) {
        var jitter = [(rnd(i * 7.7 + j) - 0.5) * slen * 0.5, -rnd(i * 3.1 + j * 2.7) * slen * 0.34,
          (rnd(i * 5.3 + j * 1.9) - 0.5) * slen * 0.5];
        var fp = cat([tip, vadd(tip, vmul(jitter, 0.6)), vadd(tip, jitter)], 6), fr = [];
        for (var q2 = 0; q2 < fp.length; q2++) fr.push(rP * 0.10 * (1 - q2 / (fp.length - 1)) + rP * 0.006);
        tube(aSt, fp, fr, { r: cS.r * 0.5, g: cS.g * 0.5, b: cS.b * 0.5 }, { r: 0, g: 0, b: 0 }, null);
      }
    }

    mIn = mesh(aIn); if (mIn) host.add(mIn);
    mMark = mesh(aMk); if (mMark) host.add(mMark);
    mStub = mesh(aSt); if (mStub) host.add(mStub);
    ready = !!mIn;
    retry = 0;
    return ready;
  }

  var API = {
    name: 'plot-fork',
    build: function (o) {
      if (!o || !o.T || !o.group) return null;
      T = o.T; O = o;
      _c = new T.Color(); _c2 = new T.Color();
      reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches);
      clearGeom(); retry = 0;
      rebuild();
      return API.stats();
    },
    update: function (s) {
      s = s || {};
      tAcc = num(s.t, tAcc + 0.016);
      deg = num(s.degrade, 0);
      onK = num(s.on, 1);
      if (!ready) { if ((++retry % 30) === 0) rebuild(); return; }
      var beat = s.beat != null ? num(s.beat, 0.5) : 0.5 + 0.5 * Math.sin(tAcc * 0.3);
      var breath = reduce ? 1 : 0.85 + 0.15 * beat;
      var base = (muted || !vis) ? 0 : onK * breath;
      if (mIn) { mIn.material.opacity = base * 0.42; mIn.visible = mIn.material.opacity > 0.004; }
      if (mMark) { mMark.material.opacity = base * 0.55; mMark.visible = mMark.material.opacity > 0.004; }
      if (mStub) {
        var so = deg >= 1 ? base * 0.18 : base * 0.30;      // 降级先削散丝那一层
        mStub.material.opacity = so; mStub.visible = so > 0.004;
      }
    },
    dispose: clearGeom,
    setOn: function (v) { muted = !v; },
    rebuild: rebuild,
    show: function (v) { vis = v !== false; },
    visible: function () { return vis && ready; },
    stats: function () {
      var dc = 0;
      [mIn, mMark, mStub].forEach(function (m) { if (m && m.visible) dc++; });
      return { ready: ready, on: +num(onK, 1).toFixed(3), forks: nFork, born: nBorn, stubs: nStub,
        drawcalls: dc, degrade: deg, muted: muted, logical: logical };
    }
  };

  window.CLPlotFork = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
