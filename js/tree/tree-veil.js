/* tree-veil.js — 星空巨树雾/星尘/微光层 (three.js UMD, ES5) */
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
  // 冠幅包络：**必须与 tree-shape.js 的 crownR(y) 逐点同值**。
  // v35 之前这是一份独立的 sin 曲线（sin(π(0.22+0.58t))），与骨架的 rise/fall 双段式对不上，
  // 读起来像「树枝戳出雾外」。后来改成了本地复刻 crownR，但 v36 W4 把 crownR 的 fall 指数
  // 从 1.30 收到 0.85（压上部一级枝仰角），veil 这侧忘了跟着改，于是「两把标尺」再次分岔
  // （y=0.89 处冠幅差 −27.3%，上部树枝戳出雾外）。
  // 现在改为**单一来源**：直接委托 tree-shape 的 crownR。改 crownR（index: tree-shape.js）
  // 必须同步这一处 —— 下面的兜底分支**复刻了 crownR 同一式（0.85）**，只用于 tree-shape
  // 不可用时（单文件调试 / 旧缓存 / 加载顺序异常），正常情况下走委托、不是第二把标尺。
  function crownEnv(hy) {
    if (window.CLTreeShape && typeof window.CLTreeShape.crownR === 'function') {
      return window.CLTreeShape.crownR(hy);
    }
    // 兜底：与 crownR（tree-shape.js）同一式。⚠ 改 crownR 必须同步这里的指数 0.85。
    hy = clamp(num2(hy, 0), 0, 1);
    if (hy <= 0.16) return 0.06;
    var u = (hy - 0.16) / 0.84;
    var rise = Math.pow(Math.min(1, u / 0.55), 0.80);
    var fall = u <= 0.55 ? 1 : Math.pow(Math.cos((u - 0.55) / 0.45 * Math.PI * 0.5), 0.85);
    return 0.06 + 0.94 * Math.min(rise, fall);
  }

  // T5 · 三层视差雾尘：采用 S5 CLAbyssTex FBM 程序化纹理发生器
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

  /** 枝雾：树冠剪影主要靠它。v32 的老写法是「边采样边判预算够不够」，结果三组循环的采样站
   *  总数远小于 budget（实测只用了 48.8%）—— 预算写成 4000，实际出来 1950，等于白写。
   *  v34 改成两遍：先收全部站并给每站算权重，再按权重把预算**分完**（每站至少 1 点）。
   *  这样 budget 是"一定会用完"的配额，而不是"最多不超过"的上限。 */
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
          // 权重 = 层级基准 × 冠幅包络：粗枝周围要多、冠外缘要比冠心多（剪影靠外缘）
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
      // 浮点累加再取差，避免逐站 Math.round 带来的系统性截断（那正是老版用不满预算的一半原因）
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
    // AABB 中心与半宽：候选点的水平半径按冠幅包络做拒绝采样，外缘也是树冠形而非方盒
    var cx = (bb.min.x + bb.max.x) * 0.5;
    var cz = (bb.min.z + bb.max.z) * 0.5;
    var halfX = (bb.max.x - bb.min.x) * 0.5;
    var halfZ = (bb.max.z - bb.min.z) * 0.5;
    var spanY = bb.max.y - bb.min.y;
    /* ── 冠叶团块：均匀撒点读起来是「星星点点的噪」，而树叶在枝上是**成团**的。
     * v32 只有均匀分布，所以星尘看着像星座图不像树冠。这里先在冠内（hy 0.40~0.94）挑 26 个团心，
     * 之后 55% 的点聚到团心附近、45% 仍均匀铺底噪 —— 团块给出「有叶子」的体量，底噪保住「有星尘」的弥散。 */
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
        // 团内点：尺寸小一点，读成叶簇的细颗粒
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
        var rX = u * 2 - 1;            // 归一化水平坐标 ∈ [-1,1]，中心 = AABB 中心
        var rZ = w * 2 - 1;
        var hy = clamp(v, 0, 1);       // v 已是 [0,1] 的归一化高度
        var env = crownEnv(hy);
        var ax = Math.abs(rX), az = Math.abs(rZ);
        if (ax > env * 0.98 || az > env * 0.98) {
          // 按 rnd 决定丢弃，或把它收缩到冠幅边界上（两个方向各自处理）
          if (rnd(i * 5 + 31) < 0.5) continue;
          if (ax > env * 0.98) rX = rX * (env * 0.98) / Math.max(ax, 1e-6);
          if (az > env * 0.98) rZ = rZ * (env * 0.98) / Math.max(az, 1e-6);
        }
        px = cx + rX * halfX;
        py = lerp(bb.min.y, bb.max.y, v);
        pz = cz + rZ * halfZ;
        sz = 0.62 + 0.26 * rnd(i * 5 + 32);   // 底噪点略大，铺出星场的底
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

  /* ── 冠幅刻度环（Q13「量具语言」）──────────────────────────────────────────
   * 为什么要有这一层：这棵树是我们"算"出来的（冠幅包络、分形比、仰角梯度都是可量化的），
   * 但画面上看不到任何"被测量过"的痕迹 —— 它和星盘（八维刻度、刻度数字、五十/七十/八十五的
   * 绝对标尺）摆在一起时，一个像量具、一个像插画。这条落差是"两个模块不像一家的"的根。
   * 三条环沿 crownEnv 包络画在 y = 0.34 / 0.56 / 0.80 上，直接回答"这棵树的冠幅有多宽"。
   *
   * 色与粗细**照抄星盘**（css/app.css 的 .radar-3d 规则），不自造：
   *   .rd-grid       → rgba(170,150,232,.17)  宽 .9  → 内环两条用 0xaa96e8
   *   .rd-grid-outer → rgba(122,240,200,.54)  宽 1.2 虚线 4 5 → 外环用 0x7af0c8 + 虚线
   * 0x7af0c8 恰好就是事件色板里的"领悟"，这不是巧合：星盘的外圈刻度本来就用它。
   * three.js 的 linewidth 在多数平台被驱动忽略（恒 1px），所以"粗细"用**不透明度**分级表达。 */
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
      // 虚线必须显式算一遍线长，否则 dashSize/gapSize 不生效（画出来是实线）
      if (d.dash && ln.computeLineDistances) ln.computeLineDistances();
      ln.raycast = function () {};      // 量具也要让鼠标穿过去，不能挡住星点拾取
      ln.renderOrder = -44;             // 在 ghost(-50) 之后、veil 点云(-45) 之前
      ln.userData.clPickable = false;
      ln.userData.clLayer = 'tree-ring';
      ln.userData.clTree = true;
      host.add(ln);
      out.push(ln);
      made++;
    }
    return made;
  }

  /* ═══ v36 W3：能量流（干流沿干向上）+ 飘落（不穿地面） ═══
   * 【为什么是线、不是第四层点云】
   * tree_fit C03 断言 veil 的点云 drawcall ≤ 3（雾/星尘/微光）。树干流线本质是
   * 「一串沿主干往上走的短划」，线对象最贴形态，且**不进**点云那个计数 ——
   * 与冠幅刻度环同一个处理（导引/量具层另立 flowDraws 记账，不污染 drawcalls）。
   *
   * 【速度与高度相关，且必须可被量出来】
   * 树干越往上越细、流速越快。所以速度写成**显式函数** speedAt(y)，验收侧直接量
   * 它单调递增，而不是看「好像是在动」。位置推进用**定步长累积器**，与帧率无关。
   *
   * 【飘落不穿地面的做法】
   * 微光不是"往下掉就完"，是把每个微光的 y 关在 [FLOOR, 原位] 这个带里做**回绕**，
   * y 的下界恒为 FLOOR>0 —— 它不是"接近地面时被裁掉"，而是**永远到不了地面以下**。
   * 亮度两端归零（顶端刚出现、底端将消散），所以回绕那一下看不见接缝。
   *
   * 【与摇曳的关系】
   * 流线钉在主干上、微光钉在枝梢上，而主干与枝都被摇曳弯过了 —— 所以这两层
   * **必须**走同一个 bendInto。否则树一晃，流就浮在树干外面（v35「两把标尺」的病根）。 */
  var FLOW_LO = 0.055, FLOW_HI = 0.215;      // 归一化弧长 / 秒（低处→高处）
  var FLOW_STEP = 1 / 60, FLOW_MAXSTEP = 4;  // 定步长推进；单帧最多补 4 步（防"死亡螺旋"）
  var FALL_FLOOR = 0.04;                     // 飘落下界（单位空间地面 y=0，留 0.04 余量）
  var FALL_LO = 0.012, FALL_HI = 0.042;      // 飘落速度 / 秒（越高的微光落得越慢）
  function frac(v) { return v - Math.floor(v); }
  function speedAt(y) { return FLOW_LO + (FLOW_HI - FLOW_LO) * clamp(y, 0, 1); }

  /* 主干弧长参数化：只**读** shape.trunk.pts，不重算骨架（重算就是第二把标尺）。 */
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
      /* 相位与划长都从 rnd 走：确定性，两次运行逐字节相同（dryrun 纪律） */
      u.push(rnd(k * 3.31 + 7.7));
      dash.push(0.035 + 0.045 * rnd(k * 3.31 + 19.3));
      /* 划头亮、划尾暗：一亮一暗才读得出"在流"，通体同亮就是一根静止的线。
       * 亮度随高度微增（高处能量更集中），静态烘进顶点色，不逐帧写颜色。 */
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
    ln.raycast = function () {};        // 流线也得让鼠标穿过去（不可点击铁律）
    ln.renderOrder = -43;               // 量具环(-44)之后、点云(-45)之前
    ln.userData = { clPickable: false, clLayer: 'tree-flow', clTree: true };
    ln.frustumCulled = false;           // 位置逐帧重写，包围盒不更新 → 关掉剔除免得整条消失
    return { obj: ln, u: u, dash: dash, n: n, path: P };
  }

  /* 一次推进：u += STEP·speedAt(u)。定步长，帧率无关。 */
  function flowAdvance(F, steps) {
    var i;
    for (var s = 0; s < steps; s++) {
      for (i = 0; i < F.n; i++) F.u[i] = frac(F.u[i] + FLOW_STEP * speedAt(F.u[i]));
    }
  }

  /* 把 N 个脉冲的两个端点写进 position；末端走 bendInto，钉死在（已摇曳的）主干上。 */
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

      // T8: 时间流河潮头高亮 (亮度 <= 60% 稳态，潮头微亮)
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

  /* 飘落 + 摇曳：把每个微光的 y 关在 [FLOOR, 原位] 内回绕，永不小于 FLOOR。
   *
   * 【关键：偏移必须在本位高度求，不能在当前高度求】
   * 一开始的写法是「先算出下落后的 y，再拿这个 y 去过 bendInto」—— 结果微光一边下沉
   * 一边被摇曳场横向推开（实测冻结姿态下仍有 0.0187 的水平漂移）。那是错的：
   * 一颗脱离枝头往下掉的火星，不该跟着树干的高低弯曲剖面横着走。
   * 正确做法是把微光**刚性挂**在它离枝那一刻的摇曳状态上：
   * 偏移 bendInto(bx, by, bz) 只在**原位高度 by** 求一次，然后原样平移到下落位置。
   * 于是 x/z 与下落进度无关（冻结时漂移精确为 0），而整棵树晃动时它照样跟着晃。 */
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
          /* 每颗微光的落速与相位都由 rnd 定 —— 确定性，两次运行逐字节相同 */
          var spd = FALL_LO + (FALL_HI - FALL_LO) * rnd(i * 4.7 + 11);
          var ph = rnd(i * 4.7 + 23) * span;
          fy = by - ((self._fallT * spd + ph) % span);
        }
      }
      var ox = 0, oy = 0, oz = 0;
      if (doBend) {
        SW.bendInto(bx, by, bz, swScratch);        // ← 本位高度，不是下落后的高度
        ox = swScratch[0] - bx; oy = swScratch[1] - by; oz = swScratch[2] - bz;
      }
      var fyOut = fy + oy;
      /* 地板是**最终写出值**上的不变式，不是中间量上的：摇摆偏移是在本位高度求的，
       * 落在低位微光身上可能把 y 再压下去一截（实测最坏到 0.029，穿过了 0.04 的设计地板）。
       * 所以在这里硬夹一道 —— 夹到地板的那些恰好是亮度已经归零的（f→0），看不见。 */
      if (self._fallOn && fyOut < FALL_FLOOR) { fyOut = FALL_FLOOR; clamped++; }
      attr[o] = bx + ox; attr[o + 1] = fyOut; attr[o + 2] = bz + oz;
      if (attr[o + 1] < minY) minY = attr[o + 1];
    }
    self._fallClamped = clamped;
    self._embers.geometry.attributes.position.needsUpdate = true;
    return minY;
  }

  /* ═══ v36 摇曳：点云逐点重投 ═══
   * 枝雾 3600 点、星尘 900 点横跨整个树冠高度，给对象挂一个旋转糊不过去
   * （冠顶和冠腰的角度差到 1.7°，折合好几 px，雾会从冠上「滑下来」）。
   * 和 ghost / clones 一样：留一份**单位空间原位**，每帧从它重投。
   * 刻度环是个例外 —— 它是一条**同高的圆**，所有顶点 y 相同，
   * 所以整条按该高度的姿态做刚体旋转是**精确**的（不是近似），dress 就是干这个的。 */
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
    if (r === swayRev) return;      // 姿态没变 → 一次 GPU 上传都不产生
    swayRev = r;
    swayPoints(self._mist, self._mistBase);
    swayPoints(self._dust, self._dustBase);
    /* 微光不走这里：它有「飘落」这条独立通道，统一由 embersWrite() 负责
     * （见它上方注释 —— 偏移必须在本位高度求，否则会横向漂）。
     * 只有在飘落关闭（flow=0 档 / reduce）时才退回这条静态通道。 */
    if (!self._fallOn) swayPoints(self._embers, self._embersBase);
    var rings = self._rings, i;
    if (rings) {
      for (i = 0; i < rings.length; i++) {
        // 环按 RING_DEF 顺序建（见 buildRings：逐条 push，一条不跳），所以下标直接对齐
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
    pts.renderOrder = -45;   // 树冠雾层：-50 主干虚影 / -45 雾与星尘 / -44 量具环
    // clTree 是"这属于星空巨树层"的**显式标记**。验收侧（tests/tree_qc.py 的 Q12、
    // tests/tree.py 的 D02）靠它判断命中对象是不是树 —— 不许再用「renderOrder ≤ -40」，
    // 那条判据会把 scene.js 的背景层（renderOrder 到 -94）也算成树，是个误报源。
    /* clLayer 不变（tree_qc Q12 / tree.py D02 靠 clTree 判树层，clLayer 是同一层的三名共用）。
     * clSub 是**增量**标记：枝雾/星尘/微光三者同名不同物，验收侧要分栏量摇曳贴合，
     * 没有它就只能按顶点数猜（那是"写死的尺寸"，v34 已经吃过一次亏）。 */
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

    /* 档位监听的挂/摘。**必须与几何寿命解耦** —— 踩过的坑：
     * rebuild() 的第一句是 this.dispose()，而 dispose 里原来会 removeEventListener 并把 _qlv 置 null，
     * 于是"收到档位事件 → 重建 → 顺手把监听摘了"，只能响应**第一次**档位变化（实测 degrade 2
     * 时 mist 还停在 mid 档的 2000，而 low 档应为 1100）。
     * 现在 _qlv 这个句柄一旦建立就不再销毁，只切换 _qBound 记账，绑定幂等。 */
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
      // 档位一变，雾/星尘/微光的点预算就变 —— 必须重建点云（点数不同，没法靠改 opacity 混过去）。
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

      // 预算一律问质量门面；门面缺席时用与 full 档相同的数（3600/900/36），不是"随便给个大的"。
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
      if (o.big) dustCount = Math.min(dustCount, 400);          // 超大规模作品：星尘不是主角，先让位
      this._mistWant = mistBudget; this._dustWant = dustCount; this._emberWant = emberCount;
      var mist = buildMist(shape, this._texSoft, mistBudget);
      if (mist.pos.length) {
        this._mist = makePoints(mist.pos, mist.cols, mist.sizes, this._texSoft, 1.2, 0);
        this._mistBase = mist.pos.slice();       // 摇曳基准（见 swayApply）
        host.add(this._mist);
      } else { this._mist = null; this._mistBase = null; }

      var dust = dustCount > 0 ? buildDust(shape, o, dustCount) : null;
      if (dust && dust.pos.length) {
        // 尺寸随点自带（团块点小、底噪点大），不再用 PointsMaterial 的全局 size
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

      /* 能量流（W3）：flow 档位系数为 0 则该档**根本不铺流线** ——
       * 与 v34「op≤0 = 该档不建这层」同一哲学：省的是件数，不是把 alpha 调小。 */
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

      /* 新几何是「未摇的原位」→ 必须让 swayApply 重写一遍（否则会以上一档的旧姿态亮相一帧）。 */
      swayRev = -1;

      // 冠幅刻度环：件数少（3 条），任何档位都建 —— 它是"量具"不是"装饰"，
      // 降级时先砍星尘微光，量具最后才走（和星盘的刻度一样，刻度永远在）。
      this._rings = [];
      if (!this._logical) buildRings(host, this._rings);
      if (!this._rings.length) this._rings = null;

      this._built = true;
      this.applyVisible();
    },

    rebuild: function () {
      this.dispose();          // 只拆几何，不销毁 _qlv 句柄
      this._built = false;
      this._try();
      this._bind();            // dispose 解绑了，这里必须补回来 —— 否则只响应第一次档位变化
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

      /* ── W3 能量流：定步长累积推进 + 每帧按当前姿态重写端点 ──────────────
       * 先补步（帧率无关），再写位（钉在已摇曳的主干上，不浮在树干外）。 */
      if (this._flow && this._flowK > 0) {
        this._flowAcc += dt;
        var steps = 0;
        while (this._flowAcc >= FLOW_STEP && steps < FLOW_MAXSTEP) {
          this._flowAcc -= FLOW_STEP; steps++;
        }
        if (this._flowAcc > FLOW_STEP) this._flowAcc = 0;   // 长卡顿后不追补，丢掉积压
        if (steps > 0) {
          flowAdvance(this._flow, steps);
          this._flowT += steps * FLOW_STEP;
        }
        flowWrite(this._flow, true, this);
      }

      /* ── W3 飘落：微光缓慢下沉，y 恒 ≥ FLOOR>0，且 x/z 不随下落移位 ──
       * 每帧都要写（不能只在 rev 变化时写）：停了摇曳它也得继续落。 */
      if (this._embers && this._embersBase && this._flowK > 0) {
        this._fallT += dt;
        this._fallOn = true;
        this._emberMinY = +embersWrite(this).toFixed(4);
      } else if (this._fallOn) {
        /* 从"在飘"切回"静止"：必须强制重投一帧，否则停在半空 */
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
          /* 飘落时按高度再压一道：贴地(f→0)与刚复位(f→1)两端都暗，
           * 所以回绕那一跳看不见接缝 —— 微光是"落下即散"，不是"撞地弹回"。 */
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
      this._unbind();   // 只解绑，不销毁 _qlv 句柄：重挂时还用同一个函数引用
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
        mistFill: want > 0 ? +(got / want).toFixed(3) : 0,   // Q11「雾预算用满」的直接读数
        dust: this._dust ? this._dust.geometry.attributes.position.count : 0,
        embers: this._embers ? this._embers.geometry.attributes.position.count : 0,
        rings: this._rings ? this._rings.length : 0,
        ringCols: this._rings ? this._rings.map(function (o) { return o.material.color.getHex(); }) : [],
        ringDef: RING_DEF.map(function (d) { return { y: d.y, col: d.col, op: d.op, dash: !!d.dash }; }),
        // drawcalls 的语义 = **点云三层**（雾/星尘/微光），tree_fit C03 断言的就是这个 ≤3。
        // 刻度环是量具层，件数恒定 3、不随档位变化，单独报 ringDraws，不污染点云那个数。
        drawcalls: (this._mist ? 1 : 0) + (this._dust ? 1 : 0) + (this._embers ? 1 : 0),
        ringDraws: this._rings ? this._rings.length : 0,
        drawcallsAll: (this._mist ? 1 : 0) + (this._dust ? 1 : 0) + (this._embers ? 1 : 0) + (this._rings ? this._rings.length : 0),
        /* W3 能量流的读数（**不进 drawcalls** —— 它是导引层，与刻度环同一处理） */
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
