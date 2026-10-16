(function () {
  'use strict';

  var VOID = 0x08050f, VIOLET = 0x8a6cd8;
  var LIGHT = [-0.52, 0.70, 0.49];
  var AMB = 0.36;
  var POW = 0.72;
  var RIM = 0.12;
  var LAYERS = [
    { key: 'trunk', N: 12, step: 1, op: 0.235, delay: 0.0 },
    { key: 'bough', N: 10, step: 1, op: 0.175, delay: 0.6 },
    { key: 'limb',  N: 8,  step: 2, op: 0.150, delay: 1.2 },
    { key: 'twig',  N: 4,  step: 2, op: 0.105, delay: 1.8 },
    /* v45 待校对轨：淡独立线（约来源线的 1/4 亮度）。T1 悬置丝进一步渐隐：0.060 → 0.048。
     * op 写死 0.048 —— 不走质量门面（门面对未知键回落 0，会把整层画没）。只在逻辑树且有 pending 时才建。 */
    { key: 'pending', N: 6, step: 2, op: 0.048, delay: 2.2, pend: true }
  ];
  var TOP_KNEE = 0.84, TOP_CUT = 0.48;
  var FADE = 0.8, BIG_TWIGS = 600;
  var KEEP = 0.32, TINT = 0.10;
  var TRUNK_W = 1.4, HALO_K = 1.9, HALO_BR = 0.30;
  var FLAME_GOLD = 0xffd166, FLAME_KEEP = 0.16, FLAME_MIX = 0.30;
  var BR_SAT = 0.60, BR_DIM = 0.80;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function Q() { return (window.CLTreeQuality && window.CLTreeQuality.of) ? window.CLTreeQuality : null; }
  function nOf(key, dflt) { var q = Q(); return q ? num(q.n(key), dflt) : dflt; }
  function opOf(key, dflt) { var q = Q(); return q ? num(q.opacity(key), dflt) : dflt; }

  var T = null, O = null, host = null, ownRoot = null;
  var meshes = {}, tAcc = 0, born = -1, deg = 0, muted = false, vis = true;
  var opBase = { trunk: 0.235, bough: 0.175, limb: 0.150, twig: 0.105, pending: 0.048 };
  var PALETTE = [0xffd166, 0xffb45c, 0xc8a7ff, 0xff5d73, 0xff9ad5, 0x7af0c8, 0x9a92b8];
  if (window.CLPalette && window.CLPalette.HEX) PALETTE = window.CLPalette.HEX;
  var on = 1, shape = null, retry = 0, reduce = false, depthK = 1, verts = 0;
  /* v39 聚焦压暗系数：默认 1.0（不压暗）。聚焦层（tree-focus）在四道门全开时压到 0.38，
   * 让「点亮的那几根管」从变暗的主树上跳出来 —— 只叠加、不压暗的话用户几乎看不出聚焦。
   * 只乘在最终 opacity 上（见 update），不碰 LAYERS / 生长动画 / 呼吸项，故退出聚焦可精确还原 1.0。 */
  var dim = 1, DIM_MIN = 0.05;
  /* v45 逻辑树渲染读数：来源线 + 来源上的事件 marker 的**实际渲染**计数（剔除待校对/孤事件轨）。
   * 只读探针，供验收侧核对「只画来源线与事件 marker」，不参与任何几何/动画决策。 */
  var markerN = 0, logicalMode = false, pendLineN = 0;
  var vivid = false, colAttr = {};          /* v44：剧情线态鲜色开关 + 两套顶点色引用（按层） */
  function setVivid(v) {
    v = !!v; if (v === vivid) return vivid; vivid = v;
    for (var k in colAttr) {
      if (!Object.prototype.hasOwnProperty.call(colAttr, k) || !meshes[k]) continue;
      meshes[k].geometry.setAttribute('color', v ? colAttr[k].vivid : colAttr[k].ghost);
    }
    return vivid;
  }
  if (document.addEventListener) document.addEventListener('cl:tree-plotline', function (e) { setVivid(!!(e && e.detail && e.detail.on)); });
  var qBound = false, qHandler = null;
  function bindQ() {
    if (!qHandler) qHandler = function () { rebuild(); };
    if (qBound || !window.addEventListener) return false;
    window.addEventListener('cl:tree-quality', qHandler);
    qBound = true;
    return true;
  }
  function unbindQ() {
    if (!qBound || !window.removeEventListener || !qHandler) return false;
    window.removeEventListener('cl:tree-quality', qHandler);
    qBound = false;
    return true;
  }

  var basePos = {}, seenRev = {}, dBuf = {}, swScratch = [0, 0, 0];

  function swayApi() { return (typeof window !== 'undefined') ? window.CLTreeSway : null; }

  function applySway() {
    var SW = swayApi();
    if (!SW || typeof SW.bendInto !== 'function' || typeof SW.rev !== 'function') return;
    var r = SW.rev(), k;
    for (k in meshes) {
      if (!meshes.hasOwnProperty(k) || !meshes[k]) continue;
      var bp = basePos[k];
      if (!bp || seenRev[k] === r) continue;
      var m = meshes[k];
      var attr = m.geometry && m.geometry.attributes && m.geometry.attributes.position;
      if (!attr) continue;
      var a = attr.array, n = bp.length, i;
      /* v42：桶路径。显式传桶让 1.8 万顶点循环彻底免掉 atan2 + 两次 sin（那是 1ms 级开销，
       * 会把 P3 预算吃穿）。桶缓冲缺失时退回缺省路径（消费方仍正确，只是慢）。 */
      var db = dBuf[k], j = 0;
      if (db) {
        for (i = 0; i < n; i += 3, j++) {
          SW.bendInto(bp[i], bp[i + 1], bp[i + 2], swScratch, db[j]);
          a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
        }
      } else {
        for (i = 0; i < n; i += 3) {
          SW.bendInto(bp[i], bp[i + 1], bp[i + 2], swScratch);
          a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
        }
      }
      attr.needsUpdate = true;
      seenRev[k] = r;
    }
  }

  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  /* v45.1 形状引用缓存：CLTreeShape.build 内部虽按 fp 缓存结果，但**入口调用本身**也有成本，
   *  且逐帧门禁要求「90 帧步进期间 build 调用次数为 0」。这里再挡一层：
   *  只有 CLStory.get() 返回的**对象引用**或 tree.fp 发生变化时才重新 build，否则复用上次结果。
   *  逻辑树 / 旧分形两条路径共用同一份缓存（build 内部自行分派），shapeOf() 仍返回缓存的 shape。
   *  缓存命中判据是「同一对象引用且同一 fp」——任一变化都视为新数据，重建一次。 */
  var shapeCache = null, shapeRef = null, shapeFp = null;
  function shapeNow() {
    var tree = (window.CLStory && CLStory.get) ? tryFn(CLStory.get) : null;
    if (!tree || tree.ok !== true) return null;
    if (shapeCache && shapeRef === tree && shapeFp === tree.fp) return shapeCache;
    if (!window.CLTreeShape || !CLTreeShape.build) return null;
    var s = tryFn(function () { return CLTreeShape.build(tree); });
    if (s && s.ok) { shapeCache = s; shapeRef = tree; shapeFp = tree.fp; return s; }
    return null;
  }

  function mount() {
    var A = window.CLTreeAnchor;
    if (A && A.ready && tryFn(A.ready) && A.root && tryFn(A.root)) { host = A.root(); return !!host; }
    if (!O || !O.group) return false;
    if (!ownRoot) {
      ownRoot = new T.Object3D();
      ownRoot.scale.setScalar(num(O.rimR, 400) * 2.3);
      ownRoot.position.set(0, -num(O.rimR, 400) * 0.55, -num(O.rimR, 400) * 0.35);
      ownRoot.rotation.x = -num(O.pitch, 0) * 0.35;
      ownRoot.raycast = function () {};
      O.group.add(ownRoot);
    }
    host = ownRoot;
    return true;
  }

  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vnorm(a) {
    var L = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0];
  }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  var _c = null, _c2 = null;
  /* v44：剧情线态用「鲜色」——只压 KEEP_V 向虚空、不掺紫。星座态仍用 ghostCol 的虚影调（掺紫 10% 是它像背景的原因）。
   *  两套顶点色在建几何时一起烘好，切态只换 attribute 引用，零重建。 */
  var KEEP_V = 0.26, _c3 = new (window.THREE || {}).Color ? new THREE.Color() : null;
  var _c4 = new (window.THREE || {}).Color ? new THREE.Color() : null;
  function vividCol(hex) {
    if (!_c3) return ghostCol(hex);
    _c3.setHex(hex >>> 0); _c2.setHex(VOID); _c3.lerp(_c2, KEEP_V);
    return _c3;
  }
  function ghostCol(hex) {
    _c.setHex(hex >>> 0);
    _c2.setHex(VOID); _c.lerp(_c2, KEEP);
    _c2.setHex(VIOLET); _c.lerp(_c2, TINT);
    return _c;
  }
  function flameCol(hex) {
    _c.setHex(hex >>> 0); _c2.setHex(VOID); _c.lerp(_c2, FLAME_KEEP);
    _c2.setHex(FLAME_GOLD); _c.lerp(_c2, FLAME_MIX);
    return _c;
  }
  function flameVivid(hex) {
    if (!_c3) return vividCol(hex);
    _c3.setHex(hex >>> 0); _c2.setHex(VOID); _c3.lerp(_c2, 0.14);
    _c2.setHex(FLAME_GOLD); _c3.lerp(_c2, FLAME_MIX);
    return _c3;
  }
  function desatDim(c) {
    if (!_c4) return;
    var g = (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) * BR_DIM;
    _c4.setRGB(g, g, g); c.lerp(_c4, 1 - BR_SAT);
  }
  function goldHalo() {
    _c.setHex(FLAME_GOLD);
    return _c;
  }

  var ROOT_FUSE = 0.14, ROOT_LIT = 0.70, ROOT_DIM = 0.30;
  function rootFuse(y) {
    if (y >= ROOT_FUSE) return 0;
    var t = clamp(1 - y / ROOT_FUSE, 0, 1);
    return t * t * (3 - 2 * t);
  }

  function extrude(branches, N, step, acc, o) {
    o = o || {};
    var isTrunk = !!o.trunk, isHalo = !!o.halo, topKnee = o.topKnee || 0;
    var bi, i, k;
    for (bi = 0; bi < branches.length; bi++) {
      var br = branches[bi], pts = br.pts, rr = br.r;
      if (!pts || pts.length < 2) continue;
      var col, colV, cr, cg, cb, vr, vg, vb;
      if (isHalo) {
        col = goldHalo(); cr = col.r; cg = col.g; cb = col.b; vr = cr; vg = cg; vb = cb;
      } else if (isTrunk) {
        col = flameCol(num(br.color, 0xffb45c)); cr = col.r; cg = col.g; cb = col.b;
        colV = flameVivid(num(br.color, 0xffb45c)); vr = colV.r; vg = colV.g; vb = colV.b;
      } else {
        col = ghostCol(num(br.color, 0xffb45c)); desatDim(col); cr = col.r; cg = col.g; cb = col.b;
        colV = vividCol(num(br.color, 0xffb45c)); desatDim(colV); vr = colV.r; vg = colV.g; vb = colV.b;
      }
      var idx = [], nst = 0;
      for (i = 0; i < pts.length; i += step) idx.push(i);
      if (idx[idx.length - 1] !== pts.length - 1) idx.push(pts.length - 1);
      nst = idx.length;
      if (nst < 2) continue;
      var base = acc.p.length / 3;
      for (k = 0; k < nst; k++) {
        var si = idx[k], p = pts[si];
        var rad = num(rr[si], 0.006) * (isTrunk ? TRUNK_W : 1) * (isHalo ? HALO_K : 1);
        var a = pts[Math.max(0, si - 1)], b = pts[Math.min(pts.length - 1, si + 1)];
        var tan = vnorm(vsub(b, a));
        var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
        var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
        var lu = vdot(LIGHT, U), lw = vdot(LIGHT, W);
        var phi = Math.atan2(lw, lu);
        var sN = nst > 1 ? k / (nst - 1) : 0;
        var fade = 1 - 0.48 * sN;
        if (topKnee && sN > TOP_KNEE) {
          var tk = (sN - TOP_KNEE) / Math.max(1e-6, 1 - TOP_KNEE);
          fade *= 1 - TOP_CUT * Math.pow(clamp(tk, 0, 1), 0.7);
        }
        var rmix = rootFuse(p[1]);
        var q;
        for (q = 0; q < N; q++) {
          var th = q / N * Math.PI * 2, cth = Math.cos(th), sth = Math.sin(th);
          acc.p.push(p[0] + (U[0] * cth + W[0] * sth) * rad,
                     p[1] + (U[1] * cth + W[1] * sth) * rad,
                     p[2] + (U[2] * cth + W[2] * sth) * rad);
          var d = cth * Math.cos(phi) + sth * Math.sin(phi);
          var lit = AMB + (1 - AMB) * Math.pow(d > 0 ? d : 0, POW);
          var m = (lit + RIM * (d < 0 ? -d : 0)) * fade;
          if (isHalo) m *= HALO_BR;
          if (rmix > 0) m = (m + (ROOT_LIT - m) * rmix) * (1 - ROOT_DIM * rmix);
          acc.c.push(cr * m, cg * m, cb * m);
          if (acc.c2) acc.c2.push(vr * m, vg * m, vb * m);
        }
      }
      for (k = 0; k < nst - 1; k++) {
        var r0 = base + k * N, r1 = base + (k + 1) * N;
        for (q = 0; q < N; q++) {
          var q2 = (q + 1) % N;
          acc.i.push(r0 + q, r1 + q, r0 + q2, r0 + q2, r1 + q, r1 + q2);
        }
      }
    }
  }

  function clearGeom() {
    var k;
    for (k in meshes) {
      if (!meshes.hasOwnProperty(k) || !meshes[k]) continue;
      var m = meshes[k];
      if (m.parent) m.parent.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) m.material.dispose();
    }
    meshes = {}; basePos = {}; seenRev = {}; verts = 0;
  }

  function rebuild() {
    if (!T || !O) return false;
    if (!mount()) return false;
    var s = shapeNow();
    if (!s) return false;
    shape = s;
    clearGeom();
    var big = !!O.big, li, tw = s.twigs || [];
    /* v45 逻辑树：**来源线**（trunk + 有真实 threadId 的 boughs/limbs）与来源上的事件 marker 照常画；
     * **待校对轨（host 'pending'）必须以「淡独立线」渲染，不能丢** —— 它是数据里真实存在、
     * 只是尚未定坑的线，抹掉等于对读者隐瞒；但它是未定线，不配与来源线同亮度，也不参与事件 marker。
     * 孤事件轨（host 'orphan'）仍不进渲染。isRoot 装饰枝不进渲染。契约第 7 条「取消可辨识三角扇光晕，
     * 保留细管和点状光」：本层不建任何扇状/三角光晕，逻辑骨架只由细管承载。
     * 只过滤**渲染**，不动 CLTreeShape 产出的 shape 数据（T1 事件覆盖与 pick 仍读全量）。 */
    var boughs = s.boughs || [], limbs = s.limbs || [], pend = [];
    logicalMode = (s.logical === true);
    if (logicalMode) {
      var hostOK = { trunk: 1 }, kB = [], kL = [], q0;
      for (q0 = 0; q0 < boughs.length; q0++) {
        var b1 = boughs[q0];
        if (b1 && String(b1.threadId || '') && b1.isRoot !== true) { kB.push(b1); hostOK[String(b1.id)] = 1; }
      }
      for (q0 = 0; q0 < limbs.length; q0++) {
        var l1 = limbs[q0];
        if (l1 && String(l1.threadId || '') && l1.isRoot !== true) { kL.push(l1); hostOK[String(l1.id)] = 1; }
      }
      boughs = kB; limbs = kL;
      var twf = [];
      for (q0 = 0; q0 < tw.length; q0++) if (tw[q0] && hostOK[String(tw[q0].host || '')]) twf.push(tw[q0]);
      tw = twf;
      var pa = s.pending || [];
      for (q0 = 0; q0 < pa.length; q0++) if (pa[q0] && pa[q0].host === 'pending') pend.push(pa[q0]);
    }
    if (big && tw.length > BIG_TWIGS) {
      var pick = [], stepK = tw.length / BIG_TWIGS, x;
      for (x = 0; x < BIG_TWIGS; x++) pick.push(tw[Math.floor(x * stepK)]);
      tw = pick;
    }
    markerN = tw.length;
    pendLineN = pend.length;
    var src = { trunk: [{ pts: s.trunk.pts, r: s.trunk.r, color: num(s.trunk.segs[0] && s.trunk.segs[0].color, 0xffb45c) }],
      bough: boughs, limb: limbs, twig: tw, pending: pend };
    if (s.trunk.segs && s.trunk.segs.length > 1) {
      var segs = [], sp = s.trunk.pts, sr = s.trunk.r, n = sp.length, gi;
      for (gi = 0; gi < s.trunk.segs.length; gi++) {
        var sg = s.trunk.segs[gi];
        var a2 = clamp(Math.floor(num(sg.t0, 0) * (n - 1)), 0, n - 1);
        var b2 = clamp(Math.ceil(num(sg.t1, 1) * (n - 1)), 0, n - 1);
        if (b2 - a2 < 1) continue;
        segs.push({ pts: sp.slice(a2, b2 + 1), r: sr.slice(a2, b2 + 1), color: num(sg.color, 0xffb45c) });
      }
      if (segs.length) src.trunk = segs;
    }
    for (li = 0; li < LAYERS.length; li++) {
      var LY = LAYERS[li], list = src[LY.key] || [];
      if (!list.length) continue;
      var nRing = LY.pend ? LY.N : nOf(LY.key, LY.N);
      var opK = LY.pend ? LY.op : opOf(LY.key, LY.op);
      opBase[LY.key] = opK;
      if (opK <= 0) continue;
      var acc = { p: [], c: [], c2: [], i: [] };
      extrude(list, nRing, LY.step, acc, LY.key === 'trunk' ? { trunk: true, topKnee: TOP_KNEE } : null);
      if (LY.key === 'trunk') extrude(list, nRing, LY.step, acc, { trunk: true, halo: true, topKnee: TOP_KNEE });
      if (!acc.p.length) continue;
      basePos[LY.key] = new Float32Array(acc.p);
      /* v42：**建期**把每个顶点的 δ 桶号算好，热路径只做一次数组取值。
       * 桶号只依赖 (px,pz)，与 spread / 开关**都无关**（角度才依赖 spread，那在
       * tree-sway 的 17 组桶表里），所以这份缓冲建一次就永久有效 —— 不需要任何失效逻辑。
       * 必须用 bucketRaw（纯几何）而不是 bucketOf：后者吃状态，而本函数运行的时刻
       * 往往早于 CLTwigPhase 就绪，用 bucketOf 会把整张缓冲填成中心桶 8（v42 实测踩过）。
       * δ 未激活时 tree-sway 的桶表全为恒等，传真实桶号与传中心桶 8 逐位等价。 */
      var np = acc.p.length / 3;
      var db = new Uint8Array(np);
      var SWb = swayApi();
      if (SWb && typeof SWb.bucketRaw === 'function') {
        for (var vi = 0, po = 0; vi < np; vi++, po += 3) db[vi] = SWb.bucketRaw(acc.p[po], acc.p[po + 2]);
      } else { db.fill(8); }
      dBuf[LY.key] = db;
      seenRev[LY.key] = -1;
      var g = new T.BufferGeometry();
      g.setAttribute('position', new T.Float32BufferAttribute(acc.p, 3));
      var attrGhost = new T.Float32BufferAttribute(acc.c, 3), attrVivid = new T.Float32BufferAttribute(acc.c2, 3);
      colAttr[LY.key] = { ghost: attrGhost, vivid: attrVivid };
      g.setAttribute('color', vivid ? attrVivid : attrGhost);
      g.setIndex(acc.i);
      var mat = new T.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0,
        blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide, fog: false });
      var mesh = new T.Mesh(g, mat);
      mesh.frustumCulled = false;
      mesh.renderOrder = -50;
      mesh.raycast = function () {};
      mesh.userData.clPickable = false;
      mesh.userData.clLayer = 'tree-ghost';
      mesh.userData.clTree = true;
      host.add(mesh);
      meshes[LY.key] = mesh;
      verts += acc.p.length / 3;
    }
    born = tAcc;
    retry = 0;
    return true;
  }

  function count(key) {
    if (!shape) return 0;
    if (key === 'trunk') return meshes.trunk ? 1 : 0;
    if (key === 'bough') return (shape.boughs || []).length;
    if (key === 'limb') return (shape.limbs || []).length;
    return meshes.twig ? markerN : 0;
  }

  function update(s) {
    s = s || {};
    tAcc = num(s.t, tAcc + 0.016);
    deg = num(s.degrade, 0);
    on = num(s.on, 1);
    /* v42：静止档（scene.setCalm(true)）时，本层自己的两只时钟 —— beat 回落与树冠慢波 ——
     * 一并停住。它们过去只吃本地 tAcc，于是「冻结摇曳 + setCalm」的像素门禁里仍有
     * ±14% 的呼吸噪声压在地板上（desync-visible 实测 5% 噪声地板，信号被埋）。
     * 判据只看 s.calm，不引入新状态：宿主（arcana）每帧原样转发 scene 的 calm。 */
    var calmK = !!s.calm;
    if (!meshes.trunk) {
      if (++retry % 30 === 0) rebuild();
      return;
    }
    var age = born < 0 ? 0 : tAcc - born;
    var beat = calmK ? 0.5 : (s.beat != null ? num(s.beat, 0.5) : 0.5 + 0.5 * Math.sin(tAcc * 0.30));
    var breath = reduce ? 1 : 0.86 + 0.14 * beat;
    var qGrow = Q() ? num(CLTreeQuality.of('grow'), 1) : 1;
    var noGrow = reduce || qGrow === 0;
    var k;
    for (k = 0; k < LAYERS.length; k++) {
      var LY = LAYERS[k], m = meshes[LY.key];
      if (!m) continue;
      var grow = noGrow ? 1 : clamp((age - LY.delay) / FADE, 0, 1);
      var lay = num(opBase[LY.key], LY.op) * depthK * grow * on * breath;
      if (LY.key === 'twig' && !reduce && !calmK) lay *= 0.78 + 0.22 * (0.5 + 0.5 * Math.sin(tAcc * 0.30 + 1.1));
      if (muted || !vis) lay = 0;
      if (deg >= 1 && LY.key === 'twig') lay = 0;
      if (deg >= 2 && (LY.key === 'twig' || LY.key === 'limb')) lay = 0;
      /* v39：压暗系数只乘在最终 opacity 上。visible 仍按未压暗的 lay 判 ——
       * 否则 dim 低到 0.05 时 trunk 会被误判为不可见（那是「隐藏」，不是「压暗」）。 */
      m.material.opacity = lay * dim;
      m.visible = lay > 0.004;
    }
    /* v36 摇曳：逐顶点重写（见 applySway / basePos 的说明）。
     * 放在不透明度之后 —— 可见性先定，摇曳只为看得见的那几层真花钱。 */
    applySway();
  }

  function onQLv() { if (T && O) rebuild(); }
  if (window.addEventListener) window.addEventListener('cl:tree-quality', onQLv);

  function tintProbe() {
    if (!_c || !_c2) return [];
    var out = [], i, cc;
    for (i = 0; i < PALETTE.length; i++) {
      cc = ghostCol(PALETTE[i]);
      out.push([Math.round(cc.r * 255), Math.round(cc.g * 255), Math.round(cc.b * 255)]);
    }
    return out;
  }

  function setDim(v) {
    var d = (v == null) ? 1 : (+v);
    if (!isFinite(d)) d = 1;
    dim = clamp(d, DIM_MIN, 1);
    return dim;
  }

  var API = {
    name: 'tree-ghost',
    build: function (o) {
      if (!o || !o.T || !o.group) return null;
      T = o.T; O = o;
      _c = new T.Color(); _c2 = new T.Color();
      reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches);
      clearGeom(); shape = null; retry = 0; dim = 1;
      shapeCache = null; shapeRef = null; shapeFp = null;
      bindQ();
      rebuild();
      return API.stats();
    },
    update: update,
    dispose: function () {
      clearGeom();
      unbindQ();
      if (ownRoot && ownRoot.parent) ownRoot.parent.remove(ownRoot);
      ownRoot = null; host = null; shape = null; dim = 1;
      shapeCache = null; shapeRef = null; shapeFp = null;
    },
    setOn: function (v) { muted = !v; },
    setDim: setDim,
    setVivid: setVivid,
    vivid: function () { return vivid; },
    rebuild: rebuild,
    show: function (v) { vis = v !== false; },
    visible: function () { return vis && !!meshes.trunk; },
    setDepth: function (k) { depthK = clamp(num(k, 1), 0, 3); return depthK; },
    shapeOf: function () { return shape; },
    rings: function () {
      return { trunk: nOf('trunk', 12), bough: nOf('bough', 10), limb: nOf('limb', 8), twig: nOf('twig', 4) };
    },
    tint: tintProbe,
    bucketAt: function (key, i) {
      var bp = basePos[key], db = dBuf[key];
      if (!bp || !db) return null;
      var vi = i | 0;
      if (vi < 0 || vi * 3 + 2 >= bp.length) return null;
      var o = vi * 3;
      return { b: db[vi], p: [bp[o], bp[o + 1], bp[o + 2]] };
    },
    bucketCount: function (key) { var db = dBuf[key]; return db ? db.length : 0; },
    layers: function () { var out = [], k; for (k in dBuf) if (dBuf.hasOwnProperty(k)) out.push(k); return out; },
    sample: function (key, n) {
      var m = meshes[key], bp = basePos[key];
      if (!m || !bp) return [];
      var at = m.geometry && m.geometry.attributes && m.geometry.attributes.position;
      if (!at || !at.array) return [];
      var a = at.array, len = bp.length / 3;
      n = Math.floor(num(n, 1));
      if (!(n > 0) || len < 1) return [];
      var stp = Math.floor(len / n);
      if (stp < 1) stp = 1;
      var out = [], i, o;
      for (i = 0; i < len && out.length < n; i += stp) {
        o = i * 3;
        out.push({ b: [bp[o], bp[o + 1], bp[o + 2]], p: [a[o], a[o + 1], a[o + 2]] });
      }
      return out;
    },
    stats: function () {
      var dc = 0, k;
      for (k in meshes) if (meshes.hasOwnProperty(k) && meshes[k] && meshes[k].visible) dc++;
      var rr = API.rings();
      return { ready: !!meshes.trunk, on: +on.toFixed(3), levels: shape ? num(shape.stats.levels, 0) : 0,
        trunk: count('trunk'), boughs: count('bough'), limbs: count('limb'), twigs: count('twig'),
        drawcalls: dc, verts: verts, scale: host ? +host.scale.x.toFixed(1) : 0,
        pickable: false, degrade: deg, grow: born < 0 ? 0 : +clamp((tAcc - born) / (1.8 + FADE), 0, 1).toFixed(3),
        muted: muted, dim: +dim.toFixed(3), logical: logicalMode, markers: markerN,
        pending: pendLineN, pendingDraws: meshes.pending ? 1 : 0,
        qTag: Q() ? CLTreeQuality.tag() : 'none',
        rings: rr, ringSum: rr.trunk + rr.bough + rr.limb + rr.twig,
        lit: { amb: AMB, pow: POW, rim: RIM, light: LIGHT, topCut: TOP_CUT } };
    }
  };

  window.CLTreeGhost = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
