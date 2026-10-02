/* Castline · tree-shape.js — v34 分形树形几何引擎（window.CLTreeShape）
 *
 * 为什么单独一层：星盘背景那棵巨树必须是**一棵完整的树**（主干 → 一级枝 → 二级枝 → 事件级细枝），
 * 而渲染层有三个（虚影本体 / 雾尘 / 叶位落点），它们必须用同一副骨架，否则彼此错位。
 * 所以骨架只算一次、在这里算，且**只算不画**。
 *
 * 单位空间：主干沿 +Y，长度恒为 1.0，根在 [0,0,0]。整棵树由渲染层一次定标。
 * 坐标一律用普通数组 [x,y,z] —— 结果可以 JSON.stringify 直接比对，确定性才测得了。
 *
 * ── v34 相对 v33 的四条结构性改造（全部来自改前量化，不是审美猜测）─────────────
 * 1) 新增 crownR(y) 冠形包络：v33 用 sin(π(0.22+0.58·bt))，树顶 env=0.588 ⇒ **冠不收口**，
 *    实测冠幅剖面顶部两档 0.842 / 0.829 —— 这就是「扫帚形」的数学原因。
 *    新曲线 0.62 处峰值 1.0、1.0 处收口到 0.06。
 * 2) 一级枝改成「末端落在冠形包络上」反解：由末端高度求水平半径，再由弦长反解长度与仰角。
 *    v33 是「仰角写死 + 长度写死」的组合（实测仰角 39°~63°，无一根接近水平），
 *    新式自然给出 低枝 68° / 中枝 71° / 高枝 26°（相对竖直）的分布。
 * 3) 二级枝分形：v33 只有一层二级枝（56 根 = 3.7×一级枝），本轮加第三级（order 2），
 *    两级合计 ≥ 15×，且仰角随阶数收敛（order1 ≈ 35°，order2 ≈ 29°）。
 *    **不新增数组、不改 levels:4** —— order2 也放进 limbs[]，靠 order 字段区分。
 * 4) 主干根盘：0.18 以下不再全裸（v33 是 0.30），半径按指数鼓起（板根），另加 4 条露出地面的根。
 */
(function () {
  'use strict';

  var GOLD = 2.39996;                    // 黄金角：任意条数绕主干分方位都不会成排重叠
  var TAU = Math.PI * 2;
  var TRUNK_N = 72;                      // 主干站位数（≥64）
  var FREE = 0.18;                       // 主干裸段：0~0.18 只长根盘，不出枝
  var AT_TOP = 0.74;                     // 一级枝挂点上限：冠由枝的末端向上撑满，不是把枝挂在顶上
  var TIP_LO = 0.42, TIP_HI = 0.92;      // 一级枝**末端**冠位区间（低枝落到中冠、高枝到冠顶）
  /* 【v36-W4】挂点 → 末端的**最大竖直跨度**。at（挂点，0.18~0.74）与 tipY（末端，0.42~0.92）
   *   是两条独立单调轴，错位时会出现「挂点不高、末端却顶到冠顶」的枝：
   *   B14 at=0.551 → tipY=0.92，竖直跨度 0.369 而水平只剩 0.259 ⇒ 弦本身 56.4°、前段实测 58.2°。
   *   真树不会这样长：从低处出发的枝够不到冠顶，就停在自己那一层（层状分枝）。
   *   实测（sample-saga）：上界 0.30 → 最高仰角 53.0°（差 3° 不达标）；收到 **0.26** → 最高 **49.2°** ✓，
   *   梯度差 20.2°（≥18 ✓）· prof[9] 0.517（Q1a 的 0.60 反而更宽裕）· 树高 H 1.084→0.969。
   *   ⚠ 只压 tipY，**不碰 crownR 的四个控制点**；tipR 由名义冠位 tipY0 解（见下方 ①），冠宽不动。 */
  var TIP_RISE_MAX = 0.26;
  /* 冠位为什么按「枝的序号」而不是「挂点归一化高度」：
   * 实测 sample-saga 的 15 条支线 attach 只铺开 0~0.66，用它当冠位会让所有枝的末端全挤在中段，
   * 仰角全变成 57°~65°、冠顶空掉 —— 这是 v34 第一次实测踩到的坑。
   * 序号是均匀的，冠才不会跟着数据的疏密一起塌。 */
  var ORDER1_K = 0.52, ORDER2_K = 0.52;  // 子枝长度系数（莱昂纳多式递减，但比 0.42 长一档）

  /* 七类事件色。**真值是 js/palette.js 的 CLPalette.HEX**，这里留一份字面量只作回落：
   * palette.js 缺席时（单独加载本文件调试、旧缓存）不能把事件上成黑色。
   * ⚠ 这份副本必须与 palette.js 逐值相同 —— tests/palette_check.py 会静态比对，不一致直接失败。
   *   要改色值请改 palette.js，再回来同步这一份（或跑 palette_check 让它告诉你差在哪）。 */
  var KIND_COL = { '高燃': 0xffd166, '转折': 0xffb45c, '抉择': 0xc8a7ff, '冲突': 0xff5d73,
                   '关系': 0xff9ad5, '领悟': 0x7af0c8, '日常': 0x9a92b8 };
  if (window.CLPalette && window.CLPalette.map) KIND_COL = window.CLPalette.map();

  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function str(v) { return v == null ? '' : String(v); }
  function sum(s) { var t = 0, i; for (i = 0; i < s.length; i++) t += s.charCodeAt(i); return t; }

  function V(x, y, z) { return [x, y, z]; }
  function vadd(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vmul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function vlen(a) { return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]); }
  function vnorm(a) { var L = vlen(a); return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0]; }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  /** 冠形包络：单位空间高度 y → 该高度允许的最大水平半径（归一化）。
   *  0~0.16 根盘极窄；0.62 处峰值 1.0；1.0 处收口到 0.06。
   *  上升段 pow(u/0.55, 0.80)（先慢后快，像真树中段展宽）；
   *  下降段 pow(cos(·), 0.85)（越到顶收得越急，冠顶是圆的不是尖的）。
   *
   *  ⚠ 下降段指数 v34 用 1.30、v35 收到 **0.85** —— 这是「上段仰角」的隐藏开关，值得记牢：
   *  仰角 = atan2(弦竖直, 弦水平)，而高挂点枝的末端贴着冠顶，末端半径 tipR = crownR(tipY)·0.55。
   *  指数 1.30 时 crownR(0.89)≈0.379 ⇒ tipR≈0.21，弦水平只剩 0.15 ⇒ 仰角冲到 67°（扫帚梢）。
   *  收到 0.85 后 crownR(0.89)≈0.524 ⇒ tipR≈0.29，水平分量抬到 0.27 ⇒ 仰角回落到 51°。
   *  **峰值位置不变**（u=0.55 处 fall=cos(0)=1，恒为 1.0）⇒ 整树最大宽度不动、AABB 不膨胀、
   *  取景与 B 组边界判据不受牵连 —— 改的是「冠顶有多钝」，不是「冠有多宽」。
   *  四个点必须记住：0.06 / 1.00 / 0.52 / 0.06。 */
  function crownR(y) {
    y = clamp(num(y, 0), 0, 1);
    if (y <= 0.16) return 0.06;
    var u = (y - 0.16) / 0.84;
    var rise = Math.pow(Math.min(1, u / 0.55), 0.80);
    var fall = u <= 0.55 ? 1 : Math.pow(Math.cos((u - 0.55) / 0.45 * Math.PI * 0.5), 0.85);
    return 0.06 + 0.94 * Math.min(rise, fall);
  }

  /** 均匀参数化的 Catmull-Rom：控制点两端各自复制一份做哨兵，采 n 个点。
   *  为什么不用 three 的 CatmullRomCurve3：这一层是纯计算，不许依赖 THREE —— 它要能在没有渲染器的地方跑。 */
  function cat(cps, n) {
    if (cps.length < 2) return [cps[0] || V(0, 0, 0)];
    var p = [cps[0]].concat(cps, [cps[cps.length - 1]]), out = [], i, seg = cps.length - 1;
    for (i = 0; i < n; i++) {
      var u = seg * (i / (n - 1)), k = Math.min(seg - 1, Math.floor(u)), f = u - k;
      var p0 = p[k], p1 = p[k + 1], p2 = p[k + 2], p3 = p[k + 3], f2 = f * f, f3 = f2 * f, d;
      var o = [0, 0, 0];
      for (d = 0; d < 3; d++) {
        o[d] = 0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * f +
               (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * f2 +
               (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * f3);
      }
      out.push(o);
    }
    return out;
  }

  /** 半径序列：从 r0 单调递减到 r1，指数收细（树枝末端要细得快，线性看起来像塑料管） */
  function taper(n, r0, r1) {
    var out = [], i;
    for (i = 0; i < n; i++) out.push(r1 + (r0 - r1) * Math.pow(1 - i / Math.max(1, n - 1), 1.35));
    return out;
  }

  // ─────────────────────────────────────────────────────────── 缓存
  var CACHE = null, CACHE_KEY = '', MS = {};

  function empty(reason) {
    return { ok: false, reason: reason, fp: '', logical: false, strictTopology: true,
      unit: 1, lengthMetric: 'event-count', dir: [0, 1, 0], height: 1,
      trunk: { pts: [], r: [], segs: [] }, boughs: [], limbs: [], twigs: [],
      eventAnchors: {}, threadPaths: {}, pending: [], unresolved: [],
      stats: { levels: 0, trunkPts: 0, boughs: 0, limbs: 0, twigs: 0, events: 0,
        unit: 1, pending: 0, unresolved: 0, ms: 0, fp: '', warn: [] } };
  }

  function buildLegacy(tree, opts) {
    opts = opts || {};
    if (!tree || tree.ok !== true) return empty('no-tree');
    var EV = tree.events || [], TH = tree.threads || [];
    if (!EV.length) return empty('no-events');

    var key = 'v35a|' + str(tree.fp) + '|' + num(opts.maxTwigs, 1200);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], i, j, k;
    var maxTwigs = num(opts.maxTwigs, 1200);

    // ── 主干：一条极缓的 S 弯。
    // 直线没有生命感，而弯太大又会让挂在上面的枝互相穿插。
    // 半径：0.0178·(1−t)^0.56 + 0.0029，从根部 0.0207 收到梢端 0.0029（6.9×）。
    // ⚠ 这里**故意不加幂律 flare**：根部半径一旦膨胀，验收 B06「一级枝根半径/主干根半径≥0.45」
    // 就会挂 —— 那个比值拿 trunk.r[0] 当分母，而一级枝只能按「挂点处」的主干半径给（挂点最低
    // 0.18，那里主干已经收掉 10%）。曾经写过 (1+2.60·e^(−t/0.055))，trunk0 从 0.0198 涨到
    // 0.0688，比值掉到 0.157（实测）。根盘的视觉**改由四条板根实体承担**（见下方 (d)），
    // 那是水平外抛的独立几何，不参与主干半径，两边不再互斥。
    // ── 主干分段（换手）
    var trunkSegs = [], tsrc = (tree.trunk && tree.trunk.segments) || [];
    for (i = 0; i < tsrc.length; i++) {
      var sg = tsrc[i] || {};
      trunkSegs.push({ t0: clamp(num(sg.t0, 0), 0, 1), t1: clamp(num(sg.t1, 1), 0, 1),
        threadId: str(sg.threadId), color: num(sg.color, 0xffb45c), lead: str(sg.lead) });
    }
    if (!trunkSegs.length) trunkSegs.push({ t0: 0, t1: 1, threadId: str(TH[0] && TH[0].id) || 'T0', color: 0xffb45c, lead: '' });

    // ── 主干：一条极缓的 S 弯与 T1 弧度张力 / 章节年轮瘤节
    // 直线没有生命感，而弯太大又会让挂在上面的枝互相穿插。
    // 半径：0.0178·(1−t)^0.56 + 0.0029，从根部 0.0207 收到梢端 0.0029（6.9×）。
    // ⚠ 这里故意不加幂律 flare：根部半径一旦膨胀，验收 B06「一级枝根半径/主干根半径≥0.45」
    // 就会挂 —— 那个比值拿 trunk.r[0] 当分母，而一级枝只能按「挂点处」的主干半径给。
    // T1 骨架参数由 CLTreeShapeConfig 统领：弧度张力随剧情冲突值蜿蜒，章节枢纽处主干膨大成年轮瘤
    var CFG = window.CLTreeShapeConfig || {};
    var tension = num(CFG.curvatureTension, 0.042);
    var tFreq = num(CFG.tensionFrequency, 1.85);
    var tp = [], tr = [];
    for (i = 0; i < TRUNK_N; i++) {
      var t = i / (TRUNK_N - 1);
      var cx = Math.sin(t * Math.PI * 0.9) * 0.035 + Math.sin(t * Math.PI * tFreq) * (tension * 0.22);
      var cz = Math.sin(t * Math.PI * 1.7) * 0.022 + Math.cos(t * Math.PI * tFreq) * (tension * 0.18);
      tp.push(V(cx, t, cz));

      // T1 章节年轮瘤节 (Nodal Burls)
      var burl = 0;
      if (CFG.nodalBurls !== false && tsrc.length > 1) {
        for (var bi = 0; bi < tsrc.length; bi++) {
          var tj = clamp(num(tsrc[bi].t1, 0), 0.16, 0.94);
          if (tj > 0.16 && tj < 0.94) {
            var dt = t - tj;
            var falloff = num(CFG.burlFalloff, 0.022);
            burl += (num(CFG.burlRadiusScale, 1.28) - 1.0) * Math.exp(-(dt * dt) / (2 * falloff * falloff));
          }
        }
      }
      var baseR = 0.0178 * Math.pow(1 - t, 0.56) + 0.0029;
      tr.push(baseR * (1.0 + burl));
    }
    function trunkAt(t) {
      t = clamp(num(t, 0), 0, 1);
      var u = t * (TRUNK_N - 1), a = Math.floor(u), b = Math.min(TRUNK_N - 1, a + 1), f = u - a;
      return vadd(vmul(tp[a], 1 - f), vmul(tp[b], f));
    }
    function trunkR(t) {
      t = clamp(num(t, 0), 0, 1);
      var u = t * (TRUNK_N - 1), a = Math.floor(u), b = Math.min(TRUNK_N - 1, a + 1), f = u - a;
      return tr[a] * (1 - f) + tr[b] * f;
    }
    /** 绕主干 az 方位的径向单位向量。主干整体沿 +Y，所以两个基就取 X / Z ——
     *  用真实切线去算会让 S 弯处的方位角发生扭转，同一个 az 在不同高度指向不同方向，读起来是乱的。 */
    function radOf(az) { return [Math.cos(az), 0, Math.sin(az)]; }

    // ── 事件在主干上的归一化位置：先查主干序列，落不到主干上的用 order 兜底
    var trunkEv = (tree.trunk && tree.trunk.events) || [], trunkLen = Math.max(1, trunkEv.length - 1);
    var onTrunk = {}, maxOrder = 1;
    for (i = 0; i < trunkEv.length; i++) onTrunk[trunkEv[i]] = i / trunkLen;
    for (i = 0; i < EV.length; i++) maxOrder = Math.max(maxOrder, num(EV[i] && EV[i].order, i + 1));
    function posOf(ev) {
      if (onTrunk[ev] != null) return onTrunk[ev];
      var e = EV[ev];
      return clamp(num(e && e.order, 1) / maxOrder, 0, 1);
    }

    // ── 线的分类
    var mainIds = {}, branches = [], twigThreads = [], maxThLen = 1, maxBrLen = 1, byId = {};
    for (i = 0; i < trunkSegs.length; i++) mainIds[trunkSegs[i].threadId] = 1;
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {};
      byId[str(th.id)] = th;
      var dep = num(th.depth, th.kind === 'twig' ? 2 : (th.kind === 'main' ? 0 : 1));
      maxThLen = Math.max(maxThLen, num(th.len, 1));
      if (dep === 1) maxBrLen = Math.max(maxBrLen, num(th.len, 1));
      if (dep === 0 || mainIds[str(th.id)]) continue;
      (dep >= 2 ? twigThreads : branches).push(th);
    }
    // 挂点稳定排序：按挂点位置，再按 id 字符序（相等时不许依赖引擎的排序稳定性）
    branches.sort(function (a, b) {
      var pa = posOf(num(a.attach, (a.events || [0])[0])), pb = posOf(num(b.attach, (b.events || [0])[0]));
      return pa - pb || (str(a.id) < str(b.id) ? -1 : 1);
    });

    /** 绕任意宿主枝的 (at, az) 取「径向 + 沿枝」的正交基。
     *  法向必须由该处的真实切线求：用全局轴算会让下垂段的子枝插进母枝里。 */
    function frameOf(pts, at) {
      var hi = clamp(Math.round(at * (pts.length - 1)), 0, pts.length - 1);
      var tan = vnorm(vsub(pts[Math.min(pts.length - 1, hi + 1)], pts[Math.max(0, hi - 1)]));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      return { hi: hi, base: pts[hi], tan: tan, U: U, W: W };
    }

    // ── 一级枝：每条支线一根。
    // v34 关键：**末端直接钉在冠形包络上** —— 按序号定末端冠位 tipY，向 crownR 要该高度的水平半径 tipR，
    // 末端落点 P3 = (tipR·cos(azEnd), tipY, tipR·sin(azEnd))，起点 P0 是主干上的挂点，
    // 中间用 C 形曲线连起来（起始上抬抢光、末端下垂自重）。冠幅剖面因此由 crownR 精确控制，不再碰运气。
    var boughs = [], byThread = {};
    var NB = Math.max(1, branches.length);
    for (i = 0; i < NB; i++) {
      var b = branches[i];
      var at = clamp(FREE + posOf(num(b.attach, (b.events || [0])[0])) * (AT_TOP - FREE), FREE, AT_TOP);
      var az = (i * GOLD) % TAU;
      var rank = NB > 1 ? i / (NB - 1) : 0.5;
      var lr = Math.sqrt(clamp(num(b.len, 1) / maxBrLen, 0, 1));
      var heat = clamp(num(b.heat, 0.4), 0, 1);
      // v36-W4：**冠位分两条轴** —— tipY0 是「这条枝按序号该到的名义冠位」，
      //   tipY 是「它从自己的挂点实际够得到的高度」。分离的理由：
      //   ① tipR 必须用 tipY0 解（冠幅包络由序号决定；实测共用被压后的 tipY 会让
      //      tipR 涨 78%、prof[9] 顶穿 Q1a 的 0.60）；
      //   ② tipY 用 min 压回「挂点上方可达高度」（层状分枝：从低处出发的枝停在自己那一层）。
      //   效果：竖直跨度 ≤0.30 而水平保持原值 ⇒ 弦仰角 ≈ atan2(0.30, 0.26) ≈ 49°，Q1 轮廓不动。
      var tipY0 = clamp(TIP_LO + (TIP_HI - TIP_LO) * rank, TIP_LO, TIP_HI);
      var tipY = Math.min(tipY0, at + TIP_RISE_MAX);
      // lr 只给 ±10% 的个体差异，不让长短把冠形本身带歪
      var tipR = crownR(tipY0) * (0.50 + 0.10 * lr) * (1 + (rnd(i * 13.3) - 0.5) * 0.16);
      // 末端方位相对本枝 az 偏摆：所有枝末端落在同一放射线上，冠会读成车轮辐条
      var azEnd = az + (rnd(i * 5.7 + 2.1) - 0.5) * 0.46;
      var P0 = vadd(trunkAt(at), vmul(radOf(az), trunkR(at) * 0.95));
      var P3 = vadd(vmul(radOf(azEnd), tipR), V(0, tipY, 0));
      var chord = vsub(P3, P0), BL = Math.max(0.16, vlen(chord));
      var chDir = vnorm(chord);
      // 仰角梯度是「伞形 / 扫帚形」的分水岭，必须由 rank 直接控制，不能靠弦角碰运气：
      //   低枝（rank→0）：upBias 为负 → 出枝即外抛近水平，末端再被 drpBias 压下去，读成伞沿；
      //   高枝（rank→1）：upBias 为正 → 出枝先上举抢光，末端下垂收口，读成冠顶。
      // 实测：upBias 系数从 (0.20−0.06·rank) 改成 (−0.02+0.14·rank) 后，一级枝前段仰角
      // 从「61°→75° 的平行陡坡」变成「30°→62° 的张开扇面」——老那版整棵树都是陡枝，冠顶收不拢。
      /* v35：上段仰角从 73.7° 收到 ≤62° —— 「扫帚形」的最后一处残留。
       * 系数 (−0.02 + 0.14·rank) 在 rank→1 时给出 +0.14·BL 的强上举，冠顶因此竖成扫帚梢。
       * 改为 (−0.06 + 0.085·rank)：低枝 −0.06 更强外抛（伞沿更宽），高枝 +0.025 只微微上举。
       * ⚠ 末端落点 P3 由 crownR(tipY) 决定，**与本系数无关** —— 所以冠幅包络（Q1）不动，
       *   两边被独立判据夹住：改仰角有 Q2b 兜，改冠形有 Q1 兜，谁也糊不过去。 */
      var upBias = BL * (-0.06 + 0.085 * rank);
      var drpBias = BL * (0.20 - 0.10 * rank) * (0.72 + 0.28 * (1 - heat));
      var c1 = vadd(P0, vmul(chDir, BL * 0.26)); c1[1] += upBias * 0.95;
      var c2 = vadd(P0, vmul(chDir, BL * 0.56)); c2[1] += upBias * 0.40;
      var c3 = vadd(P0, vmul(chDir, BL * 0.82)); c3[1] -= drpBias * 0.30;
      var pts = cat([P0, c1, c2, c3, V(P3[0], P3[1] - drpBias, P3[2])], 20);
      // 根半径按**挂点处**主干半径给（0.58×）。别改成按根部半径 —— 那样低处一级枝会比主干还粗，
      // 且 B06 用 trunk.r[0] 当分母，改动会立刻穿透到验收。
      var r0 = trunkR(at) * 0.58;
      var it = { id: 'B' + (i < 10 ? '0' : '') + i, level: 1, order: 1, threadId: str(b.id), host: 'trunk',
        at: at, az: az, pts: pts, r: taper(pts.length, r0, r0 * 0.22), len: BL,
        color: num(b.color, 0xffb45c), lead: str(b.lead), heat: heat,
        resolved: !!b.resolved, suspended: !!b.suspended };
      boughs.push(it); byThread[it.threadId] = it;
    }

    // ── 二级枝 / 三级枝：数量必须远多于一级枝，这是「完整」而不是「缩略」的关键。
    //    order 1 挂在一级枝上，order 2 挂在 order 1 上；**都放进 limbs[]**，靠 order 字段区分。
    //    点数按阶数递减（order1 14 点、order2 9 点）：渲染层的挤出成本由此可控。
    var limbs = [], ln = 0, deepByThread = {};
    function mkLimb(host, at2, az2, len2, color, threadId, heat2, order) {
      var fr = frameOf(host.pts, at2);
      var hr = num(host.r[fr.hi], 0.004);
      var rad2 = vnorm(vadd(vmul(fr.U, Math.cos(az2)), vmul(fr.W, Math.sin(az2))));
      // 仰角随阶数收敛：order1 ≈ 35.5°、order2 ≈ 29.8°（Q3 要求 order2 < order1）
      var th2 = (0.62 - 0.10 * order) - at2 * 0.10 + (rnd(ln * 7.13 + az2) - 0.5) * 0.16;
      th2 = clamp(th2, 0.16, 1.10);
      var dir2 = vnorm(vadd(vmul(rad2, Math.sin(th2)), vmul(fr.tan, Math.cos(th2))));
      var q0 = vadd(fr.base, vmul(rad2, hr * 0.9));
      var dr = len2 * (0.26 + 0.20 * (1 - clamp(heat2, 0, 1)));
      var npts = order <= 1 ? 14 : 9;
      var pts2 = cat([q0,
        vadd(q0, vmul(dir2, len2 * 0.40)),
        vadd(vadd(q0, vmul(dir2, len2 * 0.74)), V(0, -dr * 0.28, 0)),
        vadd(vadd(q0, vmul(dir2, len2 * 1.00)), V(0, -dr, 0))], npts);
      var rr = hr * (order <= 1 ? 0.60 : 0.52);
      var it2 = { id: 'L' + (ln < 10 ? '00' : ln < 100 ? '0' : '') + ln, level: 2, order: order,
        threadId: threadId, host: host.id || 'trunk',
        at: at2, az: az2, pts: pts2, r: taper(pts2.length, rr, rr * (order <= 1 ? 0.22 : 0.18)),
        len: len2, color: color, lead: '', heat: clamp(heat2, 0, 1),
        resolved: false, suspended: false };
      ln++; limbs.push(it2);
      if (threadId) deepByThread[threadId] = it2;   // 后写覆盖：事件细枝因此落到最末级枝
      return it2;
    }
    // (a) 末梢线（depth≥2 的线）：挂在自己 parent 那根一级枝上
    for (i = 0; i < twigThreads.length; i++) {
      var tw = twigThreads[i], host = byThread[str(tw.parent)];
      if (!host) { host = boughs[i % Math.max(1, boughs.length)]; if (!host) continue; warn.push('末梢线 ' + str(tw.id) + ' 的父线不在一级枝里，已就近挂靠'); }
      mkLimb(host, clamp(0.42 + rnd(i * 3.7) * 0.34, 0.3, 0.9), (host.az + GOLD * (1 + i)) % TAU,
        host.len * (0.30 + 0.18 * (num(tw.len, 1) / maxThLen)), num(tw.color, host.color), str(tw.id), num(tw.heat, 0.35), 1);
    }
    // (b) 结构性分枝：每根一级枝再分 5~7 根（v33 是 3~7，实测 15 根里 13 根只拿到 3）
    var order1 = [];
    for (i = 0; i < boughs.length; i++) {
      var hb = boughs[i], nb = clamp(Math.round(num(byId[hb.threadId] && byId[hb.threadId].len, 6) / 1.1), 5, 7);
      for (j = 0; j < nb; j++) {
        var at3 = 0.24 + (0.94 - 0.24) * (nb === 1 ? 0.5 : j / (nb - 1));
        var it3 = mkLimb(hb, at3, (hb.az + GOLD * (j + 1)) % TAU,
          hb.len * (0.42 - 0.14 * (j / Math.max(1, nb - 1))), hb.color, hb.threadId, hb.heat * 0.85, 1);
        order1.push(it3);
      }
    }
    // (c) 三级枝：在每根 order1 上再分 2~4 根。没有这一步，树冠只有「一层枝」的读数。
    for (i = 0; i < order1.length; i++) {
      var h1 = order1[i], nb2 = clamp(Math.round(h1.len * 11), 2, 4);
      for (j = 0; j < nb2; j++) {
        var at4 = 0.30 + 0.60 * (nb2 === 1 ? 0.5 : j / (nb2 - 1));
        mkLimb(h1, at4, (h1.az + GOLD * (j + 1.7)) % TAU,
          h1.len * (0.46 - 0.16 * (j / Math.max(1, nb2 - 1))), h1.color, h1.threadId, h1.heat * 0.8, 2);
      }
    }
    // (d) 根盘：**环向连续**，不再是「四条腿」。
    // v34 只有 4 条、方位均分 90°，正视图读成四条等长腿 —— 那是「支架」不是「树」。
    // v35 拆成两层，合起来 16 条，覆盖整圈方位：
    //   d1 主板根 9 条：方位走黄金角螺旋（0°/137.5°/275°…，不再均分），长度 0.155~0.260（差 1.68×），
    //      末端压到地下 −0.036，读成「扎进地里」。
    //   d2 环向鼓包带 7 条：方位与主根**错开半个间隔**，极短（0.06~0.10）且更粗（0.55×），
    //      末端只沉 0.020 —— 作用是把主根之间的空隙填上，正视图因此读成一圈连续的根盘鼓包。
    // ⚠ 两者都是 isRoot:true。**Q3 的分枝角统计必须排除它们** —— 根是向下扎的（仰角为负），
    //   混进 order1 会把 el1 拉低到与 el2 无法比较。标记就是为这条判据留的。
    var roots = 0, ROOT_N = 9, BELT_N = 7;
    for (j = 0; j < ROOT_N; j++) {
      var rAz = (j * GOLD) % TAU + 0.35;
      var rRad = radOf(rAz);
      var rAt = 0.012, rBase = trunkAt(rAt);
      var rLen = 0.155 + 0.105 * rnd(j * 9.1);
      var rDir = vnorm(vadd(vmul(rRad, Math.sin(1.42)), V(0, Math.cos(1.42) - 0.72, 0)));
      var rPts = cat([rBase,
        vadd(rBase, vmul(rDir, rLen * 0.42)),
        vadd(vadd(rBase, vmul(rDir, rLen * 0.78)), V(0, -0.014, 0)),
        vadd(vadd(rBase, vmul(rDir, rLen)), V(0, -0.036, 0))], 10);
      var rRoot = trunkR(rAt) * 0.76;
      limbs.push({ id: 'R' + j, level: 2, order: 1, isRoot: true, threadId: '', host: 'trunk',
        at: rAt, az: rAz, pts: rPts, r: taper(rPts.length, rRoot, rRoot * 0.14),
        len: rLen, color: num(trunkSegs[0].color, 0xffb45c), lead: '', heat: 0.3,
        resolved: false, suspended: false });
      roots++;
    }
    for (j = 0; j < BELT_N; j++) {
      var bAz = (j / BELT_N) * TAU + 0.35 + (Math.PI / BELT_N);
      var bRad = radOf(bAz);
      var bAt = 0.004, bBase = trunkAt(bAt);
      var bLen = 0.058 + 0.042 * rnd(j * 6.7 + 1.3);
      var bDir = vnorm(vadd(vmul(bRad, 0.94), V(0, -0.34, 0)));
      var bPts = cat([bBase,
        vadd(bBase, vmul(bDir, bLen * 0.45)),
        vadd(vadd(bBase, vmul(bDir, bLen * 0.80)), V(0, -0.008, 0)),
        vadd(vadd(bBase, vmul(bDir, bLen)), V(0, -0.020, 0))], 7);
      var bRoot = trunkR(bAt) * 0.55;
      limbs.push({ id: 'K' + j, level: 2, order: 1, isRoot: true, threadId: '', host: 'trunk',
        at: bAt, az: bAz, pts: bPts, r: taper(bPts.length, bRoot, bRoot * 0.34),
        len: bLen, color: num(trunkSegs[0].color, 0xffb45c), lead: '', heat: 0.28,
        resolved: false, suspended: false });
      roots++;
    }
    // (e) 主干光秃区段补枝（v33 保留项，gap 阈值从 0.12 收到 0.14 因为 FREE 已从 0.30 降到 0.18）
    var ats = [];
    for (i = 0; i < boughs.length; i++) ats.push(boughs[i].at);
    ats.push(FREE); ats.push(AT_TOP); ats.sort(function (a, b) { return a - b; });
    var trunkHost = { id: 'trunk', pts: tp, r: tr, az: 0, len: 1 };
    for (i = 1; i < ats.length; i++) {
      var gap = ats[i] - ats[i - 1];
      if (gap <= 0.14) continue;
      var nf = Math.min(3, Math.floor(gap / 0.14));
      for (j = 0; j < nf; j++) {
        var atf = ats[i - 1] + gap * ((j + 1) / (nf + 1));
        mkLimb(trunkHost, clamp(atf, 0.19, 0.72), (limbs.length * GOLD) % TAU,
          0.12 + 0.07 * rnd(i * 5.1 + j), trunkSegs[0].color, '', 0.3, 1);
      }
    }

    // ── 细枝：每个剧情点一根。这是「完整树」的密度来源。
    // 事件归属：包含它的线里 depth 最大的那条（最里层的线才是它真正的归属）
    var evHost = {}, evAt = {};
    for (i = 0; i < TH.length; i++) {
      var th2b = TH[i] || {}, evs = th2b.events || [], dep2 = num(th2b.depth, th2b.kind === 'twig' ? 2 : (th2b.kind === 'main' ? 0 : 1));
      for (j = 0; j < evs.length; j++) {
        var e2 = evs[j];
        if (evHost[e2] == null || dep2 > evHost[e2].dep) evHost[e2] = { id: str(th2b.id), dep: dep2, at: evs.length > 1 ? j / (evs.length - 1) : 0.5 };
      }
    }
    var order = [];
    for (i = 0; i < EV.length; i++) order.push(i);
    if (EV.length > maxTwigs) {
      order.sort(function (a, b) { return num(EV[b].w, 0) - num(EV[a].w, 0) || a - b; });
      warn.push('细枝按剧情点权重截断：' + EV.length + ' → ' + maxTwigs);
      order = order.slice(0, maxTwigs);
      order.sort(function (a, b) { return a - b; });
    }
    var twigs = [];
    for (i = 0; i < order.length; i++) {
      var ev = order[i], e3 = EV[ev] || {}, info = evHost[ev];
      // 优先挂最末级枝（deepByThread），其次一级枝 / 末梢线枝，最后主干
      var hostObj = info ? (deepByThread[info.id] || byThread[info.id]) : null, atH, hostId, hostPts, hostR;
      if (hostObj) { atH = clamp(num(info.at, 0.5) * 0.62 + 0.30, 0.16, 0.96); hostId = hostObj.id; hostPts = hostObj.pts; hostR = hostObj.r; }
      else { atH = clamp(posOf(ev), 0.03, 0.97); hostId = 'trunk'; hostPts = tp; hostR = tr; }
      var frw = frameOf(hostPts, atH);
      var hrr = num(hostR[frw.hi], 0.004);
      var azw = (ev * GOLD + sum(hostId) * 0.37) % TAU;
      var radw = vnorm(vadd(vmul(frw.U, Math.cos(azw)), vmul(frw.W, Math.sin(azw))));
      // 细枝长度用**绝对量程**而不是宿主长度的比例：挂到 order2 那种 0.1 长的子枝上时，
      // 按比例算会缩到 0.04（v34 实测），最细的一层直接在画面上消失。
      // 事件细枝是「树冠的绒毛」，它的大小该由整棵树的尺度定，不该由它恰好挂在谁身上定。
      var lw = 0.075 + 0.065 * clamp(num(e3.w, 0.4), 0, 1);
      if (hostId === 'trunk') lw *= 1.55;              // 主干上的事件撑起树冠中轴，给长一档
      else if (hostObj && hostObj.len < 0.16) lw *= 0.85;
      var dirw = vnorm(vadd(vmul(radw, 0.86), vmul(frw.tan, 0.50)));
      var w0 = vadd(frw.base, vmul(radw, hrr * 0.92));
      // 末端微微上翘：真实枝梢是朝光的，全都直挺挺会像天线
      var ptsw = cat([w0, vadd(w0, vmul(dirw, lw * 0.45)),
        vadd(vadd(w0, vmul(dirw, lw * 0.80)), V(0, lw * 0.06, 0)),
        vadd(vadd(w0, vmul(dirw, lw * 1.00)), V(0, lw * 0.16, 0))], 7);
      var rw = hrr * 0.42;
      twigs.push({ id: 'W' + (ev < 10 ? '000' : ev < 100 ? '00' : ev < 1000 ? '0' : '') + ev,
        level: 3, order: 1, host: hostId, at: atH, az: azw, pts: ptsw, r: taper(ptsw.length, rw, rw * 0.08),
        evIdx: ev, kind: str(e3.kind) || '日常', color: KIND_COL[str(e3.kind)] || KIND_COL['日常'],
        chapIdx: num(e3.chapIdx, 0) });
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var nO1 = 0, nO2 = 0;
    for (i = 0; i < limbs.length; i++) { if (limbs[i].order >= 2) nO2++; else nO1++; }
    var out = { ok: true, reason: '', fp: str(tree.fp), dir: [0, 1, 0], height: 1,
      trunk: { pts: tp, r: tr, segs: trunkSegs }, boughs: boughs, limbs: limbs, twigs: twigs,
      stats: { levels: 4, trunkPts: tp.length, boughs: boughs.length, limbs: limbs.length,
        order1: nO1, order2: nO2, roots: roots, twigs: twigs.length, events: EV.length,
        ms: MS[key], fp: str(tree.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  /* ═════════════════════ v45 逻辑树（strictTopology=true）════════════════════
   * 与旧分形路径唯一的关系是同一份输入。严格路径只画来源线：不就近挂靠、不造填充枝、不强制冠形。
   *
   * 尺度：unit=1/max(1,主干事件数-1)；主干相邻事件一单位；支线从 attach 起，其后的**每个**
   *   事件（含与父线共享的事件）都作为本线 occurrence 增长一步。lengthMetric='event-count'，
   *   不声称厘米或正文篇幅。路径取直线，实际弧长/已知步数恒等于 unit（T4）。
   *
   * 拓扑：**每个来源 threadId 都有一条 threadPaths**（含主线），主干几何另存 hostPaths['trunk']，
   *   不作为虚构 thread 键。分叉首点严格取**父线在 attach 事件上的本线 occurrence**（不是全局 canonical）。
   *   每事件一个沿宿主路径的短 marker（isEventMarker=true），末端 == eventAnchors[evIdx].pos。
   *   全局 canonical 只作「没有指定线」时的默认事件入口；共享事件保留多条 occurrence。
   *
   * 非法边不挂接：来源 topologyStatus='pending' 的线一律保留为 pending（**不重新推测为 confirmed**）；
   *   确认线若父线真实 membership 不成立，也降级 pending 并记录原因。pending 线进 threadPaths 与
   *   pending[] 独立待校对轨（x≈+1.8）；无归属事件进 orphan 独立索引轨（x≈-1.8）。全部事件仍可到达。
   *
   * 无主线：trunk.pts/r 为空，不画长度 1 的伪主干。单事件路径 length 0，用点 marker。
   * 不变量：输入不修改（只读 + slice）；不用 Math.random；重复构建逐字节确定（ms 记首次）。
   */
  function buildStrict(tree, opts) {
    opts = opts || {};
    if (!tree || tree.ok !== true) return empty('no-tree');
    var EV = tree.events || [], TH = tree.threads || [], nEV = EV.length;
    if (!nEV) return empty('no-events');

    var key = 'v45s|' + str(tree.fp) + '|' + num(opts.maxTwigs, 1200);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], i, j, oq;
    var PEND_X = 1.8, ORPH_X = -1.8;

    function kindColor(kd) { return KIND_COL[str(kd)] || KIND_COL['日常']; }
    function pad3(n) { return n < 10 ? '00' + n : (n < 100 ? '0' + n : str(n)); }
    function hashStr(s) { var h = 0; s = str(s); for (var q = 0; q < s.length; q++) h = (h * 31 + s.charCodeAt(q)) | 0; return h >>> 0; }
    function frameFromDir(dir) {
      var up = Math.abs(vdot(dir, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(dir, up));
      return { U: U, W: vnorm(vcross(dir, U)) };
    }
    function radSeries(path, at) {
      var R = (path && path.r) ? path.r : [0.004];
      if (R.length < 2) return R[0];
      var u = clamp(num(at, 0), 0, 1) * (R.length - 1);
      var a = Math.floor(u), b = Math.min(R.length - 1, a + 1), f = u - a;
      return R[a] * (1 - f) + R[b] * f;
    }
    function dedupSorted(list) {
      var out = [], seen = {};
      for (var q = 0; q < (list || []).length; q++) {
        var e = Math.floor(num(list[q], -1));
        if (e >= 0 && e < nEV && !seen[e]) { seen[e] = 1; out.push(e); }
      }
      out.sort(function (x, y) { return x - y; });
      return out;
    }
    function reasonOf(t) {
      var r = str(t.pendingReason);
      if (/未来挂点/.test(r)) return 'future-attach';
      if (/成环/.test(r)) return 'cycle';
      if (/不存在/.test(r)) return 'bad-parent';
      if (/缺少 parent|缺少parent|自由枝/.test(r)) return 'free-branch';
      if (/attach/.test(r)) return 'missing-attach';
      if (/父线/.test(r)) return 'parent-pending';
      return 'pending';
    }

    // ── 线索引
    var byId = {}, mainList = [], otherList = [];
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, id = str(th.id);
      if (!id || byId[id]) continue;
      byId[id] = th;
      if (th.kind === 'main' || num(th.depth, -1) === 0) mainList.push(th); else otherList.push(th);
    }
    function isMainT(t) { return !!t && (t.kind === 'main' || num(t.depth, -1) === 0); }

    // ── 主干事件：全体主线事件的升序并集（每条主线事件都落在主干坐标上）
    var trunkOrder = [], trunkIdx = {}, seenT = {};
    for (i = 0; i < mainList.length; i++) {
      var mev = mainList[i].events || [];
      for (j = 0; j < mev.length; j++) {
        var e0 = Math.floor(num(mev[j], -1));
        if (e0 >= 0 && e0 < nEV && !seenT[e0]) { seenT[e0] = 1; trunkOrder.push(e0); }
      }
    }
    if (!trunkOrder.length) {
      var tsrcEv = (tree.trunk && tree.trunk.events) || [];
      for (i = 0; i < tsrcEv.length; i++) {
        var e1 = Math.floor(num(tsrcEv[i], -1));
        if (e1 >= 0 && e1 < nEV && !seenT[e1]) { seenT[e1] = 1; trunkOrder.push(e1); }
      }
    }
    trunkOrder.sort(function (a, b) { return a - b; });
    var nTrunk = trunkOrder.length, unit = 1 / Math.max(1, nTrunk - 1);
    for (i = 0; i < nTrunk; i++) trunkIdx[trunkOrder[i]] = i;

    // ── 主干几何：沿 +Y 直线；无主线则 pts/r 为空（不画长度 1 的伪主干）
    var tp = [], tr = [];
    if (nTrunk > 0) {
      for (i = 0; i < nTrunk; i++) {
        var ty = i * unit;
        tp.push(V(0, ty, 0));
        tr.push(0.0178 * Math.pow(1 - Math.min(1, ty), 0.56) + 0.0029);
      }
    }
    var trunkPath = { kind: 'trunk', id: 'trunk', threadId: '', host: '', parent: null, attach: null,
      at: 0, depth: -1, dir: [0, 1, 0], start: tp.length ? tp[0].slice() : [0, 0, 0],
      len: Math.max(0, nTrunk - 1) * unit, pts: tp, r: tr, events: trunkOrder.slice(0),
      newEvents: trunkOrder.slice(0), evSet: {}, evPos: {}, stepCount: Math.max(0, nTrunk - 1),
      knownSteps: Math.max(0, nTrunk - 1), lengthMetric: 'event-count', topologyStatus: 'confirmed' };

    // trunk 只作几何宿主，不作为虚构 thread 键放进 threadPaths
    var hostPaths = { trunk: trunkPath }, threadPaths = {};
    var canon = {}, occCount = {}, pending = [], unresolved = [];
    function rec(e, pos, tid, host, at, src, depth) {
      occCount[e] = (occCount[e] || 0) + 1;
      if (!canon[e]) canon[e] = { pos: pos.slice(), threadId: tid, host: host, at: at, src: src, depth: depth };
    }

    // ── 主线路径：本段自己的事件在主干涉距上的坐标（完整 eventPositions/evPos/events）
    for (i = 0; i < mainList.length; i++) {
      var mt = mainList[i], mid = str(mt.id), mevs = dedupSorted(mt.events);
      var mPos = {}, mEvs = [], mSet = {}, firstIdx = -1, lastIdx = -1;
      for (j = 0; j < mevs.length; j++) {
        var ti = trunkIdx[mevs[j]];
        if (ti == null) { warn.push('主线 ' + mid + ' 事件 ' + mevs[j] + ' 不在主干并集'); continue; }
        mEvs.push(mevs[j]); mSet[mevs[j]] = 1;
        mPos[mevs[j]] = { evIdx: mevs[j], pos: [0, ti * unit, 0], at: nTrunk > 1 ? ti / (nTrunk - 1) : 0, stepped: true };
        if (firstIdx < 0 || ti < firstIdx) firstIdx = ti;
        if (lastIdx < 0 || ti > lastIdx) lastIdx = ti;
      }
      var mPts = [];
      for (var mi = 0; firstIdx >= 0 && mi <= lastIdx - firstIdx; mi++) mPts.push([0, (firstIdx + mi) * unit, 0]);
      var mSteps = firstIdx >= 0 ? (lastIdx - firstIdx) : 0;
      var mp = { kind: 'main', id: mid, threadId: mid, host: 'trunk', parent: null, attach: null,
        at: 0, depth: 0, dir: [0, 1, 0], start: mPts.length ? mPts[0].slice() : [0, 0, 0],
        len: mSteps * unit, pts: mPts, r: taper(mPts.length || 1, radSeries(trunkPath, 0), 0.006),
        events: mEvs, newEvents: mEvs.slice(0), eventPositions: mPos, evPos: mPos, evSet: mSet,
        stepCount: mSteps, knownSteps: mSteps, color: num(mt.color, 0xffb45c), lead: str(mt.lead),
        sourceId: str(mt.sourceId), resolved: !!mt.resolved, suspended: !!mt.suspended,
        level: 0, order: 0, lengthMetric: 'event-count', topologyStatus: 'confirmed' };
      threadPaths[mid] = mp; hostPaths[mid] = mp;
      for (oq in mPos) if (mPos.hasOwnProperty(oq)) rec(mPos[oq].evIdx, mPos[oq].pos, mid, mid, mPos[oq].at, 'confirmed', 0);
    }

    // ── 确认的非主线：仅顶层 topologyStatus==='confirmed' 才尝试挂接（不重推 pending）
    function depthOfT(t) {
      var d = 0, cur = t, hop = 0;
      while (cur && hop++ < 128) {
        if (isMainT(cur)) return d;
        cur = cur.parent != null ? byId[str(cur.parent)] : null;
        d++;
      }
      return d;
    }
    var orderList = [];
    for (i = 0; i < otherList.length; i++) {
      var ot = otherList[i];
      if (ot.topologyStatus && ot.topologyStatus !== 'confirmed') continue;
      orderList.push(str(ot.id));
    }
    orderList.sort(function (a, b) { return depthOfT(byId[a]) - depthOfT(byId[b]) || (a < b ? -1 : 1); });

    var boughs = [], limbs = [], bCount = 0, lCount = 0;
    for (i = 0; i < orderList.length; i++) {
      var id2 = orderList[i], t2 = byId[id2];
      var pid2 = t2.parent == null ? '' : str(t2.parent);
      var ae2 = (t2.attach == null) ? -1 : Math.floor(num(t2.attach, -1));
      var pth = byId[pid2], parentPath = threadPaths[pid2];
      var bad = '';
      if (!pid2) bad = 'free-branch';
      else if (!pth) bad = 'bad-parent';
      else if (ae2 < 0) bad = 'missing-attach';
      else if (!parentPath) bad = 'parent-pending';
      else if (!parentPath.evSet || !parentPath.evSet[ae2]) bad = 'bad-attach';
      else if (t2.events && t2.events.length && ae2 > Math.floor(num(t2.events[0], 1e9))) bad = 'future-attach';
      if (bad) { t2.topologyStatus = 'pending'; t2.pendingReason = str(t2.pendingReason) || bad; warn.push('线 ' + id2 + ' 确认边不成立（' + bad + '），降级 pending'); continue; }
      var tev = dedupSorted(t2.events);
      var hasBase = tev.length > 0 && tev[0] === ae2;
      // 只跳过「本线首事件 === attach」这一项；其余事件（含与父线共享）都作为本线 occurrence 增长一步
      var steps = hasBase ? tev.slice(1) : tev.slice(0);
      var stepCount = steps.length;
      // 分叉首点严格取父线在 attach 上的本线 occurrence
      var start = parentPath.evPos[ae2].pos.slice();
      var dp = depthOfT(t2), fr = frameFromDir(parentPath.dir);
      var az = ((hashStr(id2) % 10007) / 10007) * TAU % TAU;
      var el = clamp(0.10 + 0.05 * dp, 0.08, 0.42);
      var dir = vnorm(vadd(vadd(vmul(fr.U, Math.cos(az)), vmul(fr.W, Math.sin(az))), vmul(parentPath.dir, el)));
      var pts = [start.slice()];
      for (j = 1; j <= stepCount; j++) pts.push(vadd(start, vmul(dir, j * unit)));
      var evPos = {}, evSet = {};
      if (hasBase) { evPos[ae2] = { evIdx: ae2, pos: start.slice(), at: 0, stepped: false }; evSet[ae2] = 1; }
      for (j = 0; j < steps.length; j++) {
        evPos[steps[j]] = { evIdx: steps[j], pos: vadd(start, vmul(dir, (j + 1) * unit)), at: stepCount ? (j + 1) / stepCount : 0, stepped: true };
        evSet[steps[j]] = 1;
      }
      var r0 = radSeries(parentPath, parentPath.evPos[ae2].at) * 0.58;
      if (!isFinite(r0) || r0 <= 0) r0 = 0.006;
      var geomId = (dp <= 1 ? 'B' : 'L') + pad3(dp <= 1 ? (bCount++) : (lCount++));
      var path = { kind: 'branch', id: geomId, threadId: id2, host: parentPath.id, parent: pid2, attach: ae2,
        at: parentPath.evPos[ae2].at, depth: dp, dir: dir, start: start, len: stepCount * unit, pts: pts,
        r: taper(pts.length || 1, r0, r0 * 0.22), events: tev.slice(0), newEvents: steps.slice(0),
        eventPositions: evPos, evPos: evPos, evSet: evSet, stepCount: stepCount, knownSteps: stepCount,
        color: num(t2.color, 0xffb45c), lead: str(t2.lead), heat: clamp(num(t2.heat, 0.4), 0, 1),
        sourceId: str(t2.sourceId), resolved: !!t2.resolved, suspended: !!t2.suspended,
        level: dp <= 1 ? 1 : 2, order: dp, lengthMetric: 'event-count', topologyStatus: 'confirmed' };
      threadPaths[id2] = path; hostPaths[geomId] = path;
      if (dp <= 1) boughs.push(path); else limbs.push(path);
      for (oq in evPos) if (evPos.hasOwnProperty(oq)) rec(evPos[oq].evIdx, evPos[oq].pos, id2, geomId, evPos[oq].at, 'confirmed', dp);
    }

    // ── pending：来源 pending 一律保留（不重推 confirmed），进 threadPaths 与独立待校对轨
    var py = 0, pendN = 0;
    for (i = 0; i < otherList.length; i++) {
      var pt = otherList[i], pid = str(pt.id);
      if (pt.topologyStatus === 'confirmed') continue;
      if (threadPaths[pid]) continue;
      var pevs = dedupSorted(pt.events), code = reasonOf(pt), nP = pevs.length;
      unresolved.push({ threadId: pid, sourceId: str(pt.sourceId), code: code, reason: str(pt.pendingReason) || code, events: pevs.slice(0) });
      var pStart = [PEND_X + (pendN % 4) * 0.22, py, 0];
      var pPts = [pStart.slice()];
      var pPos = {}, pSet = {};
      for (j = 0; j < nP; j++) {
        var ppos = nP > 1 ? [pStart[0], py + j * unit, 0] : [pStart[0], py, 0];
        if (j > 0) pPts.push(ppos.slice());
        pPos[pevs[j]] = { evIdx: pevs[j], pos: ppos, at: nP > 1 ? j / (nP - 1) : 0, stepped: j > 0 };
        pSet[pevs[j]] = 1;
      }
      var pPath = { kind: pt.kind === 'twig' ? 'twig' : 'branch', id: 'P' + pad3(pendN), threadId: pid, host: 'pending',
        parent: pt.declaredParent != null ? str(pt.declaredParent) : null,
        attach: (pt.declaredAttach == null || pt.declaredAttach === '') ? null : str(pt.declaredAttach),
        at: 0, depth: 1, dir: [0, 1, 0], start: pStart, len: Math.max(0, nP - 1) * unit, pts: pPts,
        r: taper(pPts.length || 1, 0.010, 0.003), events: pevs.slice(0), newEvents: pevs.slice(0),
        eventPositions: pPos, evPos: pPos, evSet: pSet, stepCount: Math.max(0, nP - 1), knownSteps: Math.max(0, nP - 1), reason: code,
        color: num(pt.color, 0xffb45c), lead: str(pt.lead), heat: 0.3, level: 0, order: 0,
        sourceId: str(pt.sourceId), lengthMetric: 'event-count', topologyStatus: 'pending' };
      threadPaths[pid] = pPath; hostPaths[pPath.id] = pPath; pending.push(pPath);
      for (oq in pPos) if (pPos.hasOwnProperty(oq)) rec(pPos[oq].evIdx, pPos[oq].pos, pid, pPath.id, pPos[oq].at, 'pending', 1);
      py += Math.max(1, nP) * unit + unit;
      pendN++;
    }
    // 来源侧丢弃（无 threadId）的待校对项透传
    var tu = tree.unresolved || [];
    for (i = 0; i < tu.length; i++) {
      var u = tu[i] || {};
      if (u.threadId == null) unresolved.push({ threadId: null, sourceId: str(u.sourceId), code: 'unknown-order', reason: str(u.reasons) || '来源线无有效事件', events: [] });
    }

    // ── 孤事件（不属任何线）独立索引轨
    var owned = {}, orph = [];
    for (i = 0; i < nTrunk; i++) owned[trunkOrder[i]] = 1;
    for (i = 0; i < otherList.length; i++) { var oev = otherList[i].events || []; for (j = 0; j < oev.length; j++) { var oo = Math.floor(num(oev[j], -1)); if (oo >= 0 && oo < nEV) owned[oo] = 1; } }
    for (i = 0; i < nEV; i++) if (!owned[i]) orph.push(i);
    if (orph.length) {
      var oPts = [[ORPH_X, 0, 0]], oN = orph.length, oR = 0.010;
      for (i = 1; i <= oN; i++) oPts.push([ORPH_X, i * unit, 0]);
      var oPath = { kind: 'branch', id: 'O', threadId: 'orphan', host: 'orphan', parent: null, attach: null,
        at: 0, depth: 0, dir: [0, 1, 0], start: [ORPH_X, 0, 0], len: oN * unit, pts: oPts,
        r: taper(oPts.length, oR, 0.003), events: orph, newEvents: orph, eventPositions: {}, evSet: {}, evPos: {}, stepCount: oN, knownSteps: oN,
        color: 0x9a92b8, lead: '', heat: 0.2, level: 0, order: 0,
        lengthMetric: 'event-count', topologyStatus: 'orphan' };
      for (i = 0; i < orph.length; i++) {
        var s4 = i + 1, opos = [ORPH_X, s4 * unit, 0], oat = s4 / oN;
        oPath.evPos[orph[i]] = { evIdx: orph[i], pos: opos, at: oat, stepped: true };
        oPath.eventPositions[orph[i]] = oPath.evPos[orph[i]];
        oPath.evSet[orph[i]] = 1;
        rec(orph[i], opos, 'orphan', 'O', oat, 'orphan', 0);
      }
      hostPaths['O'] = oPath;
      pending.push(oPath);
      warn.push('无归属事件 ' + orph.length + ' 个，已放独立索引轨（不编造主/支线）');
    }

    // ── canonical anchor + 每事件一个沿宿主的 marker
    var eventAnchors = {}, twigs = [];
    for (i = 0; i < nEV; i++) {
      var c = canon[i];
      if (!c) { warn.push('事件 ' + i + ' 无 occurrence，跳过'); continue; }
      eventAnchors[i] = { pos: c.pos.slice(), threadId: c.threadId, host: c.host, at: c.at,
        occurrences: occCount[i] || 1, canonical: true };
      var hpath = hostPaths[c.host], hdir = hpath ? hpath.dir : [0, 1, 0];
      var ml = clamp(unit * 0.5, 0.004, 0.06);
      var mpts = [vsub(c.pos, vmul(hdir, ml)), c.pos.slice()];
      var hr = hpath ? radSeries(hpath, c.at) : 0.004;
      var evD = EV[i] || {};
      twigs.push({ id: 'M' + (i < 10 ? '000' : i < 100 ? '00' : i < 1000 ? '0' : '') + i,
        level: 3, order: 1, host: c.host, at: c.at, az: Math.atan2(hdir[2], hdir[0]), pts: mpts,
        r: taper(mpts.length, Math.max(0.0015, hr * 0.5), Math.max(0.0005, hr * 0.5 * 0.3)),
        evIdx: i, kind: str(evD.kind) || '日常', color: kindColor(evD.kind), chapIdx: num(evD.chapIdx, 0),
        isEventMarker: true, threadId: c.threadId });
    }

    // ── 主干分段（兼容旧消费者：tree-leaf 读 segs[].threadId/t0/t1）
    var segs = [];
    for (i = 0; i < mainList.length; i++) {
      var mm = mainList[i], mev2 = mm.events || [], fi = -1, la = -1;
      for (j = 0; j < mev2.length; j++) {
        var ix = trunkIdx[Math.floor(num(mev2[j], -1))];
        if (ix == null) continue;
        if (fi < 0 || ix < fi) fi = ix;
        if (la < 0 || ix > la) la = ix;
      }
      if (fi < 0) continue;
      segs.push({ t0: nTrunk > 1 ? fi / (nTrunk - 1) : 0, t1: nTrunk > 1 ? la / (nTrunk - 1) : 0,
        threadId: str(mm.id), color: num(mm.color, 0xffb45c), lead: str(mm.lead) });
    }
    if (!segs.length) {
      var tsrc2 = (tree.trunk && tree.trunk.segments) || [];
      for (i = 0; i < tsrc2.length; i++) {
        var sg2 = tsrc2[i] || {};
        segs.push({ t0: clamp(num(sg2.t0, 0), 0, 1), t1: clamp(num(sg2.t1, 1), 0, 1),
          threadId: str(sg2.threadId), color: num(sg2.color, 0xffb45c), lead: str(sg2.lead) });
      }
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var nO1 = 0, nO2 = 0, maxDepth = 0;
    for (i = 0; i < limbs.length; i++) { if (limbs[i].order >= 2) nO2++; else nO1++; if (limbs[i].depth > maxDepth) maxDepth = limbs[i].depth; }
    for (i = 0; i < boughs.length; i++) if (boughs[i].depth > maxDepth) maxDepth = boughs[i].depth;
    var out = { ok: true, reason: '', fp: str(tree.fp), logical: true, strictTopology: true, dir: [0, 1, 0], height: 1,
      unit: unit, lengthMetric: 'event-count',
      trunk: { pts: tp, r: tr, segs: segs }, boughs: boughs, limbs: limbs, twigs: twigs,
      eventAnchors: eventAnchors, threadPaths: threadPaths, pending: pending, unresolved: unresolved,
      stats: { levels: maxDepth + 1, trunkPts: tp.length, boughs: boughs.length, limbs: limbs.length,
        order1: nO1, order2: nO2, roots: 0, twigs: twigs.length, events: nEV, unit: unit,
        pending: pending.length, unresolved: unresolved.length, ms: MS[key], fp: str(tree.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  /** 调度：strictTopology=true 走逻辑树；否则保留旧分形路径（旧树 / 旧测试不回归）。 */
  function build(tree, opts) {
    if (tree && (tree.strictTopology === true || (opts && opts.strictTopology === true))) return buildStrict(tree, opts);
    return buildLegacy(tree, opts);
  }

  var API = {
    build: build,
    shape: build,
    get: function () { return CACHE; },
    crownR: crownR,
    stats: function () { return CACHE ? CACHE.stats : { levels: 0, ready: false }; }
  };
  window.CLTreeShape = API;
})();
