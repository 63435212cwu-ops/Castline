(function () {
  'use strict';
  var T = window.THREE;
  var rngSeed = 0;

  function rnd(i) {
    var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
    return x - Math.floor(x);
  }

  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function num2(v, d) { v = +v; return isFinite(v) ? v : d; }
  function objCount(o) { var n = 0, k; if (!o) return 0; for (k in o) if (Object.prototype.hasOwnProperty.call(o, k)) n++; return n; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function vnorm(a) {
    var L = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0];
  }
  function crownEnv(hy) {
    if (window.CLTreeShape && typeof window.CLTreeShape.crownR === 'function') {
      return window.CLTreeShape.crownR(hy);
    }
    hy = clamp(num2(hy, 0), 0, 1);
    if (hy <= 0.16) return 0.06;
    var u = (hy - 0.16) / 0.84;
    var rise = Math.pow(Math.min(1, u / 0.55), 0.80);
    var fall = u <= 0.55 ? 1 : Math.pow(Math.cos((u - 0.55) / 0.45 * Math.PI * 0.5), 0.85);
    return 0.06 + 0.94 * Math.min(rise, fall);
  }

  function makeTex(sparkle) {
    if (window.CLAbyssTex && typeof window.CLAbyssTex.generateFBMNebulaCanvas === 'function') {
      var cv = sparkle
        ? (window.CLAbyssTex.generateDustAtlasCanvas ? window.CLAbyssTex.generateDustAtlasCanvas(64, 64) : null)
        : window.CLAbyssTex.generateFBMNebulaCanvas(64, 64, 4);
      if (cv) {
        var t = new T.CanvasTexture(cv);
        t.needsUpdate = true;
        return t;
      }
    }
    var cv2 = document.createElement('canvas');
    cv2.width = 64; cv2.height = 64;
    var ctx = cv2.getContext('2d');
    var g = ctx.createRadialGradient(32, 32, 0, 32, 32, 30);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.35, 'rgba(255,255,255,0.55)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    if (sparkle) {
      ctx.strokeStyle = 'rgba(255,255,255,0.85)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(32, 4); ctx.lineTo(32, 60);
      ctx.moveTo(4, 32); ctx.lineTo(60, 32);
      ctx.stroke();
    }
    var tex = new T.CanvasTexture(cv2);
    tex.needsUpdate = true;
    return tex;
  }

  function mix(a, b, t) {
    return [
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t
    ];
  }

  function hex2rgb(h) {
    return [(h >> 16) & 255, (h >> 8) & 255, h & 255];
  }

  function col2arr(c) {
    if (!c) return [0.6, 0.5, 0.9];
    if (Array.isArray(c)) return c;
    if (typeof c === 'number') {
      return hex2rgb(c).map(function (v) { return v / 255; });
    }
    return [0.6, 0.5, 0.9];
  }

  var lerp = T && T.MathUtils && typeof T.MathUtils.lerp === 'function'
    ? T.MathUtils.lerp
    : function (a, b, t) { return a + (b - a) * t; };

  var MIST_GROUPS = [
    { key: 'boughs', base: 1.00, step: 2 },
    { key: 'limbs', base: 0.55, step: 2 },
    { key: 'twigs', base: 0.32, step: 1 }
  ];
  function buildMist(shape, tex, budget) {
    budget = Math.max(0, Math.floor(budget));
    var stations = [], g, b, s, i, k;
    for (g = 0; g < MIST_GROUPS.length; g++) {
      var grp = MIST_GROUPS[g], list = shape[grp.key] || [];
      for (b = 0; b < list.length; b++) {
        var branch = list[b], pts = branch.pts || [], rs = branch.r || [];
        var bc = col2arr(branch.color);
        for (s = 0; s < pts.length; s += grp.step) {
          var p = pts[s];
          var r = rs[s] !== undefined ? rs[s] : (rs[rs.length - 1] || 0.5);
          var tan = [0, 1, 0];
          if (pts.length === 1) tan = [0, 1, 0];
          else if (s === 0) tan = vnorm(vsub(pts[1], pts[0]));
          else if (s >= pts.length - 1) tan = vnorm(vsub(pts[pts.length - 1], pts[pts.length - 2]));
          else tan = vnorm(vsub(pts[s + 1], pts[s - 1]));
          var env = crownEnv(p[1]);
          stations.push({ p: p, r: r, tan: tan, col: bc, env: env, w: grp.base * (0.42 + 1.05 * env) });
        }
      }
    }
    if (!stations.length || budget <= 0) return { pos: [], cols: [], sizes: [] };
    var tw = 0;
    for (i = 0; i < stations.length; i++) tw += stations[i].w;
    var base = hex2rgb(0x08050f).map(function (v) { return v / 255; });
    var violet = hex2rgb(0x8a6cd8).map(function (v) { return v / 255; });
    var pos = [], cols = [], sizes = [];
    var accF = 0, got = 0, idx = 0, MAX_PER = 16;
    for (i = 0; i < stations.length && got < budget; i++) {
      var st = stations[i];
      accF += budget * st.w / tw;
      var want = Math.floor(accF) - got;
      if (want < 1) want = 1;
      if (want > MAX_PER) want = MAX_PER;
      if (got + want > budget) want = budget - got;
      var tan2 = st.tan;
      var p2 = st.p, r2 = st.r, env2 = st.env;
      var up = Math.abs(vdot(tan2, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan2, up));
      var W = vnorm(vcross(tan2, U));
      for (k = 0; k < want; k++) {
        var n2 = idx++;
        var th = rnd(n2 * 3 + 1) * Math.PI * 2;
        var dist = r2 * (1.6 + rnd(n2 * 3 + 3) * 2.6);
        var rRad = dist * (0.55 + 0.85 * env2);
        var rTan = dist * (0.35 + 0.5 * env2);
        var tOff = rTan * (2 * rnd(n2 * 3 + 2) - 1);
        pos.push(
          p2[0] + U[0] * rRad * Math.cos(th) + W[0] * rRad * Math.sin(th) + tan2[0] * tOff,
          p2[1] + U[1] * rRad * Math.cos(th) + W[1] * rRad * Math.sin(th) + tan2[1] * tOff,
          p2[2] + U[2] * rRad * Math.cos(th) + W[2] * rRad * Math.sin(th) + tan2[2] * tOff
        );
        var near = 1 - Math.min(1, (dist / (r2 * 4.2 + 0.001)) * 0.7);
        var c = mix(base, st.col, 0.3 + 0.4 * near);
        c = mix(c, violet, 0.3 * near);
        cols.push(c[0], c[1], c[2]);
        sizes.push(r2 * (2.2 + rnd(n2 * 7 + 5) * 2.8));
      }
      got += want;
    }
    return { pos: pos, cols: cols, sizes: sizes };
  }

  function buildDust(shape, o, count) {
    var bb = new T.Box3();
    var all = [];
    var trunk = shape.trunk;
    if (trunk && trunk.pts) all = all.concat(trunk.pts);
    ['boughs', 'limbs', 'twigs'].forEach(function (key) {
      (shape[key] || []).forEach(function (br) {
        if (br.pts) all = all.concat(br.pts);
      });
    });
    if (!all.length) return null;
    bb.setFromPoints(all.map(function (p) {
      return new T.Vector3(p[0], p[1], p[2]);
    }));
    var pos = [], cols = [], sizes = [];
    var violet = hex2rgb(0x8a6cd8).map(function (v) { return v / 255; });
    var mint = hex2rgb(0x3fd6a8).map(function (v) { return v / 255; });
    var cx = (bb.min.x + bb.max.x) * 0.5;
    var cz = (bb.min.z + bb.max.z) * 0.5;
    var halfX = (bb.max.x - bb.min.x) * 0.5;
    var halfZ = (bb.max.z - bb.min.z) * 0.5;
    var spanY = bb.max.y - bb.min.y;
    var K = 26, clusters = [], ci;
    for (ci = 0; ci < K; ci++) {
      var cu = rnd(ci * 11 + 41), cvy = 0.40 + 0.54 * rnd(ci * 11 + 42), cwd = rnd(ci * 11 + 43);
      var cenv = crownEnv(cvy);
      clusters.push({
        x: cx + (cu * 2 - 1) * cenv * halfX * 0.86,
        y: lerp(bb.min.y, bb.max.y, cvy),
        z: cz + (cwd * 2 - 1) * cenv * halfZ * 0.86,
        s: 0.13 + 0.15 * rnd(ci * 11 + 44)
      });
    }
    for (var i = 0; i < count; i++) {
      var px, py, pz, sz;
      if (rnd(i * 5 + 71) < 0.55) {
        var cl = clusters[Math.floor(rnd(i * 5 + 72) * K) % K];
        var g1 = rnd(i * 5 + 73) * 2 - 1, g2 = rnd(i * 5 + 74) * 2 - 1, g3 = rnd(i * 5 + 75) * 2 - 1;
        px = cl.x + g1 * cl.s * halfX * 0.55;
        py = cl.y + g2 * cl.s * spanY * 0.75;
        pz = cl.z + g3 * cl.s * halfZ * 0.55;
        sz = 0.42 + 0.30 * rnd(i * 5 + 76);
      } else {
        var u = rnd(i * 5 + 11);
        var v = Math.pow(rnd(i * 5 + 12), 0.6);
        var w = rnd(i * 5 + 13);
        var rX = u * 2 - 1;
        var rZ = w * 2 - 1;
        var hy = clamp(v, 0, 1);
        var env = crownEnv(hy);
        var ax = Math.abs(rX), az = Math.abs(rZ);
        if (ax > env * 0.98 || az > env * 0.98) {
          if (rnd(i * 5 + 31) < 0.5) continue;
          if (ax > env * 0.98) rX = rX * (env * 0.98) / Math.max(ax, 1e-6);
          if (az > env * 0.98) rZ = rZ * (env * 0.98) / Math.max(az, 1e-6);
        }
        px = cx + rX * halfX;
        py = lerp(bb.min.y, bb.max.y, v);
        pz = cz + rZ * halfZ;
        sz = 0.62 + 0.26 * rnd(i * 5 + 32);
      }
      pos.push(px, py, pz);
      var c = mix(violet, mint, rnd(i * 5 + 14));
      cols.push(c[0], c[1], c[2]);
      sizes.push(sz);
    }
    return { pos: pos, cols: cols, sizes: sizes, bb: bb, clusters: K };
  }

  function buildEmbers(shape, count) {
    var twigs = (shape.twigs || []).filter(function (t) {
      return t.kind === '高燃' || t.kind === '转折' || t.kind === '抉择';
    });
    var pool = twigs.length >= count ? twigs : (shape.twigs || []).slice().sort(function (a, b) {
      var ay = a.pts && a.pts.length ? a.pts[a.pts.length - 1][1] : -Infinity;
      var by = b.pts && b.pts.length ? b.pts[b.pts.length - 1][1] : -Infinity;
      return by - ay;
    });
    var pos = [], cols = [];
    var warm = hex2rgb(0xffe9b0).map(function (v) { return v / 255; });
    for (var i = 0; i < count && i < pool.length; i++) {
      var pts = pool[i].pts;
      if (!pts || !pts.length) continue;
      var p = pts[pts.length - 1];
      pos.push(p[0], p[1], p[2]);
      cols.push(warm[0], warm[1], warm[2]);
    }
    return { pos: pos, cols: cols };
  }

  var RING_DEF = [
    { y: 0.34, col: 0xaa96e8, op: 0.17, dash: 0 },
    { y: 0.56, col: 0xaa96e8, op: 0.26, dash: 0 },
    { y: 0.80, col: 0x7af0c8, op: 0.42, dash: 1 }
  ];
  function buildRings(host, out) {
    var seg = 64, made = 0, i, k;
    for (i = 0; i < RING_DEF.length; i++) {
      var d = RING_DEF[i], r = crownEnv(d.y) * 0.96, pts = [];
      for (k = 0; k <= seg; k++) {
        var th = k / seg * Math.PI * 2;
        pts.push(new T.Vector3(Math.cos(th) * r, d.y, Math.sin(th) * r));
      }
      var g = new T.BufferGeometry();
      if (g.setFromPoints) g.setFromPoints(pts);
      else g.setAttribute('position', new T.Float32BufferAttribute(
        pts.reduce(function (a, v) { return a.concat([v.x, v.y, v.z]); }, []), 3));
      var m = d.dash
        ? new T.LineDashedMaterial({ color: d.col, transparent: true, opacity: d.op,
            blending: T.AdditiveBlending, depthWrite: false, dashSize: 0.022, gapSize: 0.026 })
        : new T.LineBasicMaterial({ color: d.col, transparent: true, opacity: d.op,
            blending: T.AdditiveBlending, depthWrite: false });
      var ln = new T.Line(g, m);
      if (d.dash && ln.computeLineDistances) ln.computeLineDistances();
      ln.raycast = function () {};
      ln.renderOrder = -44;
      ln.userData.clPickable = false;
      ln.userData.clLayer = 'tree-ring';
      ln.userData.clTree = true;
      host.add(ln);
      out.push(ln);
      made++;
    }
    return made;
  }

  var FLOW_LO = 0.055, FLOW_HI = 0.215;
  var FLOW_STEP = 1 / 60, FLOW_MAXSTEP = 4;
  var FALL_FLOOR = 0.04;
  var FALL_LO = 0.012, FALL_HI = 0.042;
  function frac(v) { return v - Math.floor(v); }
  function speedAt(y) { return FLOW_LO + (FLOW_HI - FLOW_LO) * clamp(y, 0, 1); }

  function trunkPath(shape) {
    var tp = shape && shape.trunk && shape.trunk.pts;
    if (!tp || tp.length < 2) return null;
    var cum = [0], i, total = 0;
    for (i = 1; i < tp.length; i++) {
      var dx = tp[i][0] - tp[i - 1][0], dy = tp[i][1] - tp[i - 1][1], dz = tp[i][2] - tp[i - 1][2];
      total += Math.sqrt(dx * dx + dy * dy + dz * dz);
      cum.push(total);
    }
    if (total <= 1e-6) return null;
    return { pts: tp, cum: cum, total: total };
  }

  function pathAt(P, u) {
    u = clamp(u, 0, 1);
    var d = u * P.total, lo = 0, hi = P.cum.length - 1, mid;
    while (lo < hi - 1) { mid = (lo + hi) >> 1; if (P.cum[mid] <= d) lo = mid; else hi = mid; }
    var span = P.cum[hi] - P.cum[lo];
    var f = span > 1e-9 ? (d - P.cum[lo]) / span : 0;
    var a = P.pts[lo], b = P.pts[hi];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }

  function buildFlow(shape, count) {
    var P = trunkPath(shape);
    if (!P) return null;
    var n = Math.max(4, Math.round(count));
    var pos = new Float32Array(n * 6);
    var col = new Float32Array(n * 6);
    var u = [], dash = [], k;
    var head = hex2rgb(0xffd166).map(function (v) { return v / 255; });
    var tail = hex2rgb(0x7af0c8).map(function (v) { return v / 255; });
    for (k = 0; k < n; k++) {
      u.push(rnd(k * 3.31 + 7.7));
      dash.push(0.035 + 0.045 * rnd(k * 3.31 + 19.3));
      var gain = 0.62 + 0.38 * (k / Math.max(1, n - 1));
      col[k * 6] = head[0] * gain; col[k * 6 + 1] = head[1] * gain; col[k * 6 + 2] = head[2] * gain;
      col[k * 6 + 3] = tail[0] * 0.34; col[k * 6 + 4] = tail[1] * 0.34; col[k * 6 + 5] = tail[2] * 0.34;
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('color', new T.BufferAttribute(col, 3));
    var mat = new T.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.72,
      blending: T.AdditiveBlending, depthWrite: false });
    var ln = new T.LineSegments(geo, mat);
    ln.raycast = function () {};
    ln.renderOrder = -43;
    ln.userData = { clPickable: false, clLayer: 'tree-flow', clTree: true };
    ln.frustumCulled = false;
    return { obj: ln, u: u, dash: dash, n: n, path: P };
  }

  function flowAdvance(F, steps) {
    var i;
    for (var s = 0; s < steps; s++) {
      for (i = 0; i < F.n; i++) F.u[i] = frac(F.u[i] + FLOW_STEP * speedAt(F.u[i]));
    }
  }

  var flowScratch = [0, 0, 0];
  function flowWrite(F, bend, out) {
    var arr = F.obj.geometry.attributes.position.array;
    var col = (F.obj.geometry.attributes.color && F.obj.geometry.attributes.color.array) ? F.obj.geometry.attributes.color.array : null;
    var SW = bend ? window.CLTreeSway : null;
    var doBend = !!(SW && typeof SW.bendInto === 'function');
    var TL = window.CLTreeTimeline;
    var prog = (TL && typeof TL.getProgress === 'function') ? TL.getProgress() : 0.5;
    var minY = 1e9, i;
    for (i = 0; i < F.n; i++) {
      var u0 = F.u[i];
      var a = pathAt(F.path, u0);
      var b = pathAt(F.path, Math.min(1, u0 + F.dash[i]));
      var o = i * 6;
      if (doBend) {
        SW.bendInto(a[0], a[1], a[2], flowScratch); a = [flowScratch[0], flowScratch[1], flowScratch[2]];
        SW.bendInto(b[0], b[1], b[2], flowScratch); b = [flowScratch[0], flowScratch[1], flowScratch[2]];
      }
      arr[o] = a[0]; arr[o + 1] = a[1]; arr[o + 2] = a[2];
      arr[o + 3] = b[0]; arr[o + 4] = b[1]; arr[o + 5] = b[2];
      if (a[1] < minY) minY = a[1];
      if (b[1] < minY) minY = b[1];

      if (col) {
        var distProg = Math.abs(u0 - prog);
        var isTide = distProg < 0.08;
        var gain = isTide ? 0.72 : (0.28 + 0.16 * (i / Math.max(1, F.n - 1)));
        col[o] = 1.0 * gain;
        col[o + 1] = (isTide ? 0.92 : 0.78) * gain;
        col[o + 2] = (isTide ? 0.55 : 0.38) * gain;
        col[o + 3] = 0.48 * gain;
        col[o + 4] = 0.94 * gain;
        col[o + 5] = 0.78 * gain;
      }
    }
    F.obj.geometry.attributes.position.needsUpdate = true;
    if (col) F.obj.geometry.attributes.color.needsUpdate = true;
    if (out) {
      out.flowMinY = +minY.toFixed(4);
      out._tideHead = +prog.toFixed(4);
    }
  }

  function embersWrite(self) {
    var base = self._embersBase, attr = self._embers.geometry.attributes.position.array;
    var n = self._embers.geometry.attributes.position.count;
    var SW = window.CLTreeSway;
    var doBend = !!(SW && typeof SW.bendInto === 'function');
    var minY = 1e9, clamped = 0, i;
    for (i = 0; i < n; i++) {
      var o = i * 3;
      var bx = base[o], by = base[o + 1], bz = base[o + 2];
      var fy = by;
      if (self._fallOn) {
        var span = by - FALL_FLOOR;
        if (span > 0.005) {
          var spd = FALL_LO + (FALL_HI - FALL_LO) * rnd(i * 4.7 + 11);
          var ph = rnd(i * 4.7 + 23) * span;
          fy = by - ((self._fallT * spd + ph) % span);
        }
      }
      var ox = 0, oy = 0, oz = 0;
      if (doBend) {
        SW.bendInto(bx, by, bz, swScratch);
        ox = swScratch[0] - bx; oy = swScratch[1] - by; oz = swScratch[2] - bz;
      }
      var fyOut = fy + oy;
      if (self._fallOn && fyOut < FALL_FLOOR) { fyOut = FALL_FLOOR; clamped++; }
      attr[o] = bx + ox; attr[o + 1] = fyOut; attr[o + 2] = bz + oz;
      if (attr[o + 1] < minY) minY = attr[o + 1];
    }
    self._fallClamped = clamped;
    self._embers.geometry.attributes.position.needsUpdate = true;
    return minY;
  }

  var swScratch = [0, 0, 0], swayRev = -1;

  function swayPoints(obj, base) {
    if (!obj || !base) return;
    var SW = window.CLTreeSway;
    if (!SW) return;
    var attr = obj.geometry && obj.geometry.attributes && obj.geometry.attributes.position;
    if (!attr) return;
    var a = attr.array, n = base.length, i;
    if (!a || a.length < n) return;
    for (i = 0; i < n; i += 3) {
      SW.bendInto(base[i], base[i + 1], base[i + 2], swScratch);
      a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
    }
    attr.needsUpdate = true;
  }

  function swayApply(self) {
    var SW = (typeof window !== 'undefined') ? window.CLTreeSway : null;
    if (!SW || typeof SW.bendInto !== 'function' || typeof SW.rev !== 'function') return;
    var r = SW.rev();
    if (r === swayRev) return;
    swayRev = r;
    swayPoints(self._mist, self._mistBase);
    swayPoints(self._dust, self._dustBase);
    if (!self._fallOn) swayPoints(self._embers, self._embersBase);
    var rings = self._rings, i;
    if (rings) {
      for (i = 0; i < rings.length; i++) {
        var d = RING_DEF[i];
        SW.dress(rings[i], d ? d.y : 0);
      }
    }
  }

  function makePoints(pos, cols, sizes, tex, size, layer) {
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color', new T.Float32BufferAttribute(cols, 3));
    if (sizes && sizes.length) {
      geo.setAttribute('size', new T.Float32BufferAttribute(sizes, 1));
    }
    var mat = new T.PointsMaterial({
      map: tex,
      vertexColors: true,
      transparent: true,
      blending: T.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
      size: size,
      opacity: layer === 2 ? 0.9 : 0.55
    });
    var pts = new T.Points(geo, mat);
    pts.raycast = function () {};
    pts.renderOrder = -45;
    pts.userData = { clPickable: false, clLayer: 'tree-veil', clTree: true,
      clSub: layer === 0 ? 'mist' : (layer === 1 ? 'dust' : 'embers') };
    return pts;
  }

  var API = {
    name: 'tree-veil',
    _o: null, _shape: null, _group: null, _texSoft: null, _texSpark: null,
    _mist: null, _dust: null, _embers: null, _rings: null, _flow: null,
    _on: true, _visible: true, _muted: false,
    _degrade: 0, _t: 0, _frame: 0, _built: false,
    _flowT: 0, _flowAcc: 0, _fallT: 0, _fallClamped: 0,
    _fallOn: false,
    _flowMinY: 0, _emberMinY: 0, _flowK: 0,
    _density: 1, _qlv: null, _qBound: false,
    _logical: false, _mistWant: null, _dustWant: null, _emberWant: null,

    _bind: function () {
      var self = this;
      if (!this._qlv) this._qlv = function () { self.rebuild(); };
      if (this._qBound || !window.addEventListener) return false;
      window.addEventListener('cl:tree-quality', this._qlv);
      this._qBound = true;
      return true;
    },
    _unbind: function () {
      if (!this._qBound || !window.removeEventListener) return false;
      window.removeEventListener('cl:tree-quality', this._qlv);
      this._qBound = false;
      return true;
    },

    build: function (o) {
      this._o = o;
      this._bind();
      this._try();
    },

    _try: function () {
      if (this._built) return;
      var o = this._o;
      if (!o || !T) return;
      var tree = window.CLStory && CLStory.get ? CLStory.get() : null;
      if (!tree) return;
      var shape = (window.CLTreeShape && tree) ? CLTreeShape.build(tree) : null;
      if (!shape || !shape.ok) return;
      this._shape = shape;
      this._texSoft = makeTex(false);
      this._texSpark = makeTex(true);

      var host = null;
      if (window.CLTreeAnchor && CLTreeAnchor.root) {
        host = CLTreeAnchor.root();
      } else {
        host = new T.Object3D();
        host.scale.setScalar(o.rimR * 2.3);
        host.position.set(0, -o.rimR * 0.55, -o.rimR * 0.35);
        host.rotation.x = -o.pitch * 0.35;
        if (o.group) o.group.add(host);
      }
      this._group = host;

      var q = (window.CLTreeQuality && window.CLTreeQuality.of) ? window.CLTreeQuality : null;
      var mistBudget = q ? num2(q.budget('mist'), 3600) : 3600;
      var dustCount = q ? num2(q.budget('dust'), 900) : 900;
      var emberCount = q ? num2(q.budget('embers'), 36) : 36;
      this._logical = (shape.logical === true);
      if (this._logical) {
        /* v45 逻辑树：这已不是"冠形树"，所以
         *  · 雾按来源线数定预算（每线 12 点），不再按冠幅面积铺；
         *  · 星尘=0：没有冠，就不拿星尘去填一个假冠；
         *  · 微光按事件数发放（一事件一点，上限 36）；
         *  · 冠幅刻度环停建（它量的是冠，此树无冠）。 */
        var lineN = objCount(shape.threadPaths);
        if (!lineN) lineN = ((shape.boughs || []).length + (shape.limbs || []).length) + (shape.trunk ? 1 : 0);
        mistBudget = Math.min(mistBudget, lineN * 12);
        dustCount = 0;
        var evN = objCount(shape.eventAnchors);
        if (!evN && shape.twigs) evN = shape.twigs.length;
        emberCount = Math.min(emberCount, evN, 36);
      }
      if (o.big) dustCount = Math.min(dustCount, 400);
      this._mistWant = mistBudget; this._dustWant = dustCount; this._emberWant = emberCount;
      var mist = buildMist(shape, this._texSoft, mistBudget);
      if (mist.pos.length) {
        this._mist = makePoints(mist.pos, mist.cols, mist.sizes, this._texSoft, 1.2, 0);
        this._mistBase = mist.pos.slice();
        host.add(this._mist);
      } else { this._mist = null; this._mistBase = null; }

      var dust = dustCount > 0 ? buildDust(shape, o, dustCount) : null;
      if (dust && dust.pos.length) {
        this._dust = makePoints(dust.pos, dust.cols, dust.sizes, this._texSoft, 0.6, 1);
        this._dustBase = dust.pos.slice();
        host.add(this._dust);
      } else { this._dust = null; this._dustBase = null; }

      var embers = buildEmbers(shape, emberCount);
      if (embers.pos.length) {
        this._embers = makePoints(embers.pos, embers.cols, null, this._texSpark, 1.6, 2);
        this._embersBase = embers.pos.slice();
        host.add(this._embers);
      } else { this._embers = null; this._embersBase = null; }

      this._flowK = q ? num2(q.of('flow'), 1) : 1;
      this._flow = null;
      if (this._flowK > 0) {
        var flowN = Math.max(6, Math.round(26 * this._flowK));
        var fl = buildFlow(shape, flowN);
        if (fl) {
          this._flow = fl;
          host.add(fl.obj);
          flowWrite(fl, true, this);
        }
      }

      swayRev = -1;

      this._rings = [];
      if (!this._logical) buildRings(host, this._rings);
      if (!this._rings.length) this._rings = null;

      this._built = true;
      this.applyVisible();
    },

    rebuild: function () {
      this.dispose();
      this._built = false;
      this._try();
      this._bind();
    },

    setOn: function (v) { this._on = !!v; this.applyVisible(); },
    show: function (v) { this._visible = !!v; this.applyVisible(); },
    setDensity: function (k) { this._density = k == null ? 1 : k; },

    applyVisible: function () {
      var vis = this._on && this._visible;
      ['_mist', '_dust', '_embers'].forEach(function (k) {
        if (this[k]) this[k].visible = vis;
      }, this);
      if (this._flow) this._flow.obj.visible = vis;
      if (this._rings) for (var i = 0; i < this._rings.length; i++) this._rings[i].visible = vis;
    },

    visible: function () {
      return !!(this._mist && this._mist.visible);
    },

    update: function (s) {
      this._frame++;
      if (!this._built) {
        if (this._frame % 30 === 0) this._try();
        return;
      }
      if (!s || s.on === 0) {
        if (this._mist) this._mist.visible = false;
        if (this._dust) this._dust.visible = false;
        if (this._embers) this._embers.visible = false;
        if (this._rings) for (var ri = 0; ri < this._rings.length; ri++) this._rings[ri].visible = false;
        return;
      }
      this.applyVisible();
      /* v36 摇曳：放在可见性之后 —— 姿态没变时 swayApply 整段跳过，静止档零开销。 */
      swayApply(this);
      if (s.degrade !== undefined) this._degrade = s.degrade;
      if (s.muted !== undefined) this._muted = !!s.muted;
      /* v42 静止档（scene.setCalm(true)）：本层三只时钟 —— 能量流定步推进、微光飘落、
       * 尘环缓转 —— 一并停住（含本层自己的 _t，它喂给下面所有推进式动画）。
       * 它们过去只认 reduce / muted，于是「冻结摇曳 + setCalm」的像素门禁里，
       * 枝雾层仍在逐帧重写端点（desync-visible 实测噪声地板 5.6%，信号几乎被埋）。
       * 判据只看 s.calm（宿主每帧原样转发），不引入新状态。 */
      if (s.calm) return;
      var dt = (s && s.dt) || 0.016;
      this._t += dt;
      var reduce = false;
      try {
        reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      } catch (e) { reduce = false; }
      if (reduce || this._muted) return;

      if (this._flow && this._flowK > 0) {
        this._flowAcc += dt;
        var steps = 0;
        while (this._flowAcc >= FLOW_STEP && steps < FLOW_MAXSTEP) {
          this._flowAcc -= FLOW_STEP; steps++;
        }
        if (this._flowAcc > FLOW_STEP) this._flowAcc = 0;
        if (steps > 0) {
          flowAdvance(this._flow, steps);
          this._flowT += steps * FLOW_STEP;
        }
        flowWrite(this._flow, true, this);
      }

      if (this._embers && this._embersBase && this._flowK > 0) {
        this._fallT += dt;
        this._fallOn = true;
        this._emberMinY = +embersWrite(this).toFixed(4);
      } else if (this._fallOn) {
        this._fallOn = false;
        swayRev = -1;
      }

      if (this._dust && this._degrade < 1) {
        this._dust.rotation.y += 0.006 * dt;
        var rimR = this._o && this._o.rimR ? this._o.rimR : 1;
        this._dust.position.y = Math.sin(this._t * 0.4) * rimR * 0.01;
      }
      if (this._embers) {
        var cols = this._embers.geometry.attributes.color;
        var n = cols.count;
        for (var i = 0; i < n; i++) {
          var phase = rnd(i * 9 + 3) * Math.PI * 2;
          var b = 0.35 + 0.65 * Math.pow(Math.sin(this._t * 0.22 + phase), 6);
          if (this._fallOn && this._embersBase) {
            var ynow = this._embers.geometry.attributes.position.array[i * 3 + 1];
            var yzero = this._embersBase[i * 3 + 1];
            var spanb = yzero - FALL_FLOOR;
            var f = spanb > 0.005 ? clamp((ynow - FALL_FLOOR) / spanb, 0, 1) : 1;
            b *= 0.25 + 0.75 * Math.min(1, Math.sin(Math.PI * f) * 1.9);
          }
          cols.setXYZ(i, b, b * 0.91, b * 0.69);
        }
        cols.needsUpdate = true;
      }
    },

    dispose: function () {
      this._unbind();
      var self = this;
      ['_mist', '_dust', '_embers'].forEach(function (k) {
        var obj = self[k];
        if (!obj) return;
        if (obj.parent) obj.parent.remove(obj);
        obj.geometry.dispose();
        obj.material.dispose();
        self[k] = null;
      });
      if (this._flow) {
        var fo = this._flow.obj;
        if (fo.parent) fo.parent.remove(fo);
        if (fo.geometry) fo.geometry.dispose();
        if (fo.material) fo.material.dispose();
        this._flow = null;
      }
      if (this._rings) {
        for (var i = 0; i < this._rings.length; i++) {
          var rl = this._rings[i];
          if (rl.parent) rl.parent.remove(rl);
          if (rl.geometry) rl.geometry.dispose();
          if (rl.material) rl.material.dispose();
        }
        this._rings = null;
      }
      this._mistBase = null; this._dustBase = null; this._embersBase = null;
      this._fallOn = false;
      swayRev = -1;
      if (this._texSoft) { this._texSoft.dispose(); this._texSoft = null; }
      if (this._texSpark) { this._texSpark.dispose(); this._texSpark = null; }
      this._shape = null;
      this._group = null;
      this._logical = false; this._mistWant = null; this._dustWant = null; this._emberWant = null;
    },

    stats: function () {
      var q = (window.CLTreeQuality && window.CLTreeQuality.of) ? window.CLTreeQuality : null;
      /* v45：严格逻辑树下预算被按来源线数/事件数改写，这里必须报**实际下单数**，
       * 不能再回读质量门面的档位值 —— 否则 stats 说 2000、实物 60，验收读数是假的。 */
      var want = (this._mistWant != null) ? this._mistWant : (q ? num2(q.budget('mist'), 3600) : 3600);
      var wantDust = (this._dustWant != null) ? this._dustWant : (q ? num2(q.budget('dust'), 900) : 900);
      var wantEmber = (this._emberWant != null) ? this._emberWant : (q ? num2(q.budget('embers'), 36) : 36);
      var got = this._mist ? this._mist.geometry.attributes.position.count : 0;
      return {
        ready: this._built,
        on: this._on,
        logical: !!this._logical,
        mist: got,
        mistWant: want,
        dustWant: wantDust,
        embersWant: wantEmber,
        mistFill: want > 0 ? +(got / want).toFixed(3) : 0,
        dust: this._dust ? this._dust.geometry.attributes.position.count : 0,
        embers: this._embers ? this._embers.geometry.attributes.position.count : 0,
        rings: this._rings ? this._rings.length : 0,
        ringCols: this._rings ? this._rings.map(function (o) { return o.material.color.getHex(); }) : [],
        ringDef: RING_DEF.map(function (d) { return { y: d.y, col: d.col, op: d.op, dash: !!d.dash }; }),
        drawcalls: (this._mist ? 1 : 0) + (this._dust ? 1 : 0) + (this._embers ? 1 : 0),
        ringDraws: this._rings ? this._rings.length : 0,
        drawcallsAll: (this._mist ? 1 : 0) + (this._dust ? 1 : 0) + (this._embers ? 1 : 0) + (this._rings ? this._rings.length : 0),
        flowDraws: this._flow ? 1 : 0,
        flowN: this._flow ? this._flow.n : 0,
        flowK: this._flowK,
        flowT: +this._flowT.toFixed(4),
        fallT: +this._fallT.toFixed(4),
        falling: !!this._fallOn,
        fallClamped: this._fallClamped,
        flowMinY: this._flowMinY,
        emberMinY: this._emberMinY,
        floorY: FALL_FLOOR,
        speedLo: +speedAt(0).toFixed(4),
        speedHi: +speedAt(1).toFixed(4),
        hasFlow: !!(this._flow && this._flow.obj),
        tideHead: this._tideHead !== undefined ? this._tideHead : 0.5,
        textures: (this._texSoft ? 1 : 0) + (this._texSpark ? 1 : 0),
        degrade: this._degrade,
        qTag: q ? CLTreeQuality.tag() : 'none',
        muted: this._muted
      };
    }
  };

  window.CLTreeVeil = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
