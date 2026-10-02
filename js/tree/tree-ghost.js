/* Castline · tree-ghost.js — v32 星空巨树虚影（window.CLTreeGhost）· T1 主线圣焰（v33）
 *
 * 用户要的是「星盘背景里一棵完整形状的巨树，虚影，不可点击」。三条据此定死：
 *   ① 四层枝干全画（主干 / 一级枝 / 二级枝 / 事件级细枝）—— 只画主干就还是那个「缩略版」；
 *   ② 加性混合 + 低不透明度 + 环向明暗调制 —— 虚影靠「中间亮、两侧化开」，不是靠调低 alpha 的实体；
 *   ③ 所有对象 raycast 置空 —— 树是背景，鼠标必须穿过它。
 *
 * T1 主线圣焰（v33）：主线成为树视图中唯一满亮度通道 —— 主干线宽 ×1.4、
 * 焰芯双层（内层亮金芯 + 外层低透明金晕，同一份几何两次挤出）、支线整体降饱和 40%
 * 并降一档亮度。drawcalls 契约（tree.py C02 ≤ 4）要求外晕并入主干几何，不许新增 mesh。
 *
 * 不写 GLSL：仓里出过「新加的着色器编译失败 → 整张画面纯黑而 jserr 仍为 none」的事故。
 * 明暗全部烘进顶点色（MeshBasicMaterial 不吃逐顶点 alpha，所以 alpha 直接乘进颜色）。
 */
(function () {
  'use strict';

  var VOID = 0x08050f, VIOLET = 0x8a6cd8;
  /* 树**局部空间**的光方向（左上前方偏后）。用固定局部光而不是跟随相机，是有意的：
   * 虚影是背景，亮面钉死在树上才有雕塑感；跟着相机转会变成「每帧换一张脸」的塑料球。 */
  var LIGHT = [-0.52, 0.70, 0.49];
  var AMB = 0.36;      // 环境项：背光侧不至于全黑
  var POW = 0.72;      // 半兰伯特指数：>1 收窄高光、<1 摊开，0.72 接近真 Lambert 的柔化
  var RIM = 0.12;      // 背光侧边缘微光：完全没它，背光的管子会读成「断了」
  /* 四层回落值（CLTreeQuality 缺席时用）。N/op 与 tree-quality.js 的 full 档**故意写成同一组数**，
   * 这样两个文件各自单独加载都不跑偏；改一处必须改另一处，否则会在「谁后加载谁生效」上打架。 */
  var LAYERS = [
    /* T1 主线圣焰（亮度曲线）：主干 = 唯一满亮度通道（0.235），支线逐级退让。
     * N/op 与 tree-quality.js 的 full 档**故意写成同一组数** —— 改一处必须改另一处。 */
    { key: 'trunk', N: 12, step: 1, op: 0.235, delay: 0.0 },
    { key: 'bough', N: 10, step: 1, op: 0.175, delay: 0.6 },
    { key: 'limb',  N: 8,  step: 2, op: 0.150, delay: 1.2 },
    { key: 'twig',  N: 4,  step: 2, op: 0.105, delay: 1.8 },
    /* v45 待校对轨：淡独立线（约来源线的 1/4 亮度）。T1 悬置丝进一步渐隐：0.060 → 0.048。
     * op 写死 0.048 —— 不走质量门面（门面对未知键回落 0，会把整层画没）。只在逻辑树且有 pending 时才建。 */
    { key: 'pending', N: 6, step: 2, op: 0.048, delay: 2.2, pend: true }
  ];
  // 主干梢端压制：主干最上段（sN>0.84）亮度渐降 48%。冠顶已经是最亮的地方，
  // 主干再往上满亮，整棵树的视觉重心会顶到天上、根部反而变轻。
  var TOP_KNEE = 0.84, TOP_CUT = 0.48;
  var FADE = 0.8, BIG_TWIGS = 600;
  /* 七类事件色 → 虚影色的压底/偏紫强度。v32 是 (0.50, 0.16)：压得太狠，
   * 七类色被 lerp 到几乎同一个紫灰上（实测通道标准差只剩 21/18/27），
   * 「按类型上色」名存实亡。v34 收到 (0.32, 0.10)，把标准差提到约 32/27/36 —— 还认得出线的类型色。 */
  var KEEP = 0.32, TINT = 0.10;
  /* T1 主线圣焰 —— 主线 = 树视图中唯一满亮度通道。
   * 焰芯双层渲染在同一份几何里完成（drawcalls 契约 C02 ≤ 4，不许新增 mesh）：
   *   ① 内层亮金芯：线宽 ×TRUNK_W；压底系数放宽（FLAME_KEEP < KEEP）+ 向焰金上浮 FLAME_MIX；
   *   ② 外层低透明光晕：同站再挤一圈半径 ×(TRUNK_W·HALO_K) 的纯金管，亮度 ×HALO_BR ——
   *      加性混合下「低亮度」等效「低透明」，无需 per-vertex alpha。
   * 支线（bough/limb/twig/pending）整体降饱和 (1−BR_SAT)、降一档亮度 BR_DIM。 */
  var TRUNK_W = 1.4, HALO_K = 1.9, HALO_BR = 0.30;
  var FLAME_GOLD = 0xffd166, FLAME_KEEP = 0.16, FLAME_MIX = 0.30;
  var BR_SAT = 0.60, BR_DIM = 0.80;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function Q() { return (window.CLTreeQuality && window.CLTreeQuality.of) ? window.CLTreeQuality : null; }
  /** 每层的圈数 / 不透明度：优先问质量门面，拿不到就用上面的回落值 */
  function nOf(key, dflt) { var q = Q(); return q ? num(q.n(key), dflt) : dflt; }
  function opOf(key, dflt) { var q = Q(); return q ? num(q.opacity(key), dflt) : dflt; }

  var T = null, O = null, host = null, ownRoot = null;
  var meshes = {}, tAcc = 0, born = -1, deg = 0, muted = false, vis = true;
  // 每层的**基准**不透明度（rebuild 时从质量门面抄下来）。update 只在这个基准上乘动态项，
  // 不再回读 LAYERS —— 否则「档位表」和「回落表」会在每帧打架。
  var opBase = { trunk: 0.235, bough: 0.175, limb: 0.150, twig: 0.105, pending: 0.048 };
  // 七类事件色。真值在 js/palette.js，这里的字面量只是"palette 缺席"时的回落副本
  // （用途：tintProbe 报出虚影侧实际压底/偏紫后的 RGB，供 tree_qc 算类型色标准差）。
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

  /* ---- v36 摇曳：逐顶点重写 ----
   * 本层是全树最大的一块几何（满档 1.8 万顶点），也是唯一「横跨全部高度」的一块，
   * 所以不能用对象旋转糊过去 —— 按高度柔弯要求每个顶点各算各的。
   * basePos 存**建造时的单位空间原位**：每帧从它重投，不在上一帧结果上叠
   * （叠会累积漂移，且与 star-migrate 的解析式再也对不上）。
   * seenRev 记「这一层已经按哪个姿态版本号写过」：姿态没变就一次上传都不产生 ——
   * 静止档（low / 降低动效 / 静默）下的开销精确为 0。 */
  var basePos = {}, seenRev = {}, dBuf = {}, swScratch = [0, 0, 0];

  /** v42：取摇曳层的唯一入口（懒解析 —— 不在模块求值期抓，避免脚本先后顺序成为隐式依赖）。 */
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

  /** 挂载点：优先用共享定标器，让虚影 / 雾 / 按钮 / 迁移落点共用同一副矩阵。
   *  拿不到就按同一组约定常数自建一个 —— 常数在这里重复一次是有意的：
   *  两边写死同一组值，才能在 anchor 缺席时不错位。 */
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
  /** 枝色 → 虚影色：先压进虚空底（否则暖色枝在星云上像塑料），再往紫罗兰偏一点点。
   *  星空里的树不该是暖色实体，但也不能偏成纯紫 —— 12% 是「还认得出线的类型色」的上限。
   *  ⚠ 这两个系数与 tree_qc 的 Q9「类型色标准差」直接挂钩，别随手调大。 */
  /* v44：剧情线态用「鲜色」——只压 KEEP_V 向虚空、不掺紫。星座态仍用 ghostCol 的虚影调（掺紫 10% 是它像背景的原因）。
   *  两套顶点色在建几何时一起烘好，切态只换 attribute 引用，零重建。 */
  var KEEP_V = 0.26, _c3 = new (window.THREE || {}).Color ? new THREE.Color() : null;
  /* T1 支线降饱和/降亮度的灰轴擦色（见 desatDim）。模块求值期建，与 _c3 同款防御。 */
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
  /* T1 焰芯色：比普通虚影压底更轻（FLAME_KEEP < KEEP），再向焰金上浮 —— 主干读成一条金焰，
   * 段色（换手）经 30% 金混合后仍可分辨。vivid 态用同款上浮（KEEP_V 收窄到 0.14）。 */
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
  /* 支线整体降饱和 40%、降一档亮度：向「亮度×BR_DIM 的灰」lerp (1−BR_SAT)。
   * 亮度折进灰轴而不是乘在光照调制上 —— 两种都行，但折进颜色可让根盘融合/梢端渐隐共用同一个 m。 */
  function desatDim(c) {
    if (!_c4) return;
    var g = (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) * BR_DIM;
    _c4.setRGB(g, g, g); c.lerp(_c4, 1 - BR_SAT);
  }
  /* 外晕纯金（T1）：颜色恒定，不随段色走 —— 光晕就该是同一团火的光，而不是七段七色。 */
  function goldHalo() {
    _c.setHex(FLAME_GOLD);
    return _c;
  }

  /* 【v36-W4 · G2】根盘接地融合带 —— v35 如实记下：16 条根各自是独立管体，
   *  颜色其实完全一致（都是主干首段色），**分界来自各自的朝向光照**（方位不同 ⇒ φ 不同 ⇒ 明暗不同）。
   *  着色层不增几何地把它读成一块：
   *    y ≥ ROOT_FUSE（地面上方）→ rmix=0，原样；
   *    y = 0（地面）           → rmix=1：明暗向 ROOT_LIT 收敛（相邻管体的明暗差被压掉）+ 整体压暗 ROOT_DIM；
   *    y < 0（地下根尖）        → rmix 仍为 1，读成「没入同一片虚空」。
   *  smoothstep 过渡，避免出现一条可见的色阶线。 */
  var ROOT_FUSE = 0.14, ROOT_LIT = 0.70, ROOT_DIM = 0.30;
  function rootFuse(y) {
    if (y >= ROOT_FUSE) return 0;
    var t = clamp(1 - y / ROOT_FUSE, 0, 1);
    return t * t * (3 - 2 * t);
  }

  /** 环挤出：沿曲线每站一圈 N 个顶点，相邻两圈连成三角带。
   *  明暗两路调制都烘进顶点色（MeshBasicMaterial 不吃逐顶点光照，也不给 per-vertex alpha）：
   *    ① 朝向光照 —— 逐站算一次 φ，环上 N 个顶点共用，成本 O(站数) 而不是 O(站数×N)；
   *    ② 长度向衰减 —— 枝梢化进背景，根端实、末端虚。
   *  o：T1 主线圣焰的三种挤出模式（缺省 = 支线虚影）——
   *    { trunk:true }   焰芯内层：线宽 ×TRUNK_W + 焰金色（flameCol/flameVivid）
   *    { trunk:true, halo:true }  焰芯外晕：同站半径 ×(TRUNK_W·HALO_K) 的纯金管，亮度 ×HALO_BR
   *    （缺省）         支线：ghostCol/vividCol 后 desatDim（降饱和 40% + 降一档亮度）
   *  topKnee：只对主干传（见 TOP_KNEE），梢端再压一道；外晕共用同一道压制。 */
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
        /* 朝向光照是怎么烘进来的：环上第 q 个顶点的外法线是 n = U·cosθ + W·sinθ，
         * 于是 dot(n, LIGHT) = cosθ·(LIGHT·U) + sinθ·(LIGHT·W)。
         * 把 (LIGHT·U, LIGHT·W) 看成平面向量，它的辐角就是「最受光的那个 θ」= φ。
         * 所以 dot(n,LIGHT) = |(lu,lw)|·cos(θ−φ)，归一化后直接就是 cos(θ−φ)。
         * 这就是真正的 Lambert，只是把「逐顶点点积」省成「逐站一次 atan2」。 */
        var lu = vdot(LIGHT, U), lw = vdot(LIGHT, W);
        var phi = Math.atan2(lw, lu);
        var sN = nst > 1 ? k / (nst - 1) : 0;
        var fade = 1 - 0.48 * sN;                        // 末端亮度降到 0.52
        if (topKnee && sN > TOP_KNEE) {
          var tk = (sN - TOP_KNEE) / Math.max(1e-6, 1 - TOP_KNEE);
          fade *= 1 - TOP_CUT * Math.pow(clamp(tk, 0, 1), 0.7);
        }
        var rmix = rootFuse(p[1]);                       // 【v36-W4 · G2】接地区融合系数
        var q;
        for (q = 0; q < N; q++) {
          var th = q / N * Math.PI * 2, cth = Math.cos(th), sth = Math.sin(th);
          acc.p.push(p[0] + (U[0] * cth + W[0] * sth) * rad,
                     p[1] + (U[1] * cth + W[1] * sth) * rad,
                     p[2] + (U[2] * cth + W[2] * sth) * rad);
          var d = cth * Math.cos(phi) + sth * Math.sin(phi);   // = cos(θ−φ)，省一次三角函数
          var lit = AMB + (1 - AMB) * Math.pow(d > 0 ? d : 0, POW);
          var m = (lit + RIM * (d < 0 ? -d : 0)) * fade;
          if (isHalo) m *= HALO_BR;                            // T1 外晕：低亮度 ≈ 低透明（加性）
          if (rmix > 0) m = (m + (ROOT_LIT - m) * rmix) * (1 - ROOT_DIM * rmix);  // 根盘：明暗收敛 + 压暗
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
    // 主干按分段各自上色：换手是这棵树的骨架事件，不该被抹成一色
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
      // 圈数 / 基准不透明度都问质量门面。op≤0 = 该档不建这一层（不是建了再透明，
      // 是根本不进渲染列表 —— 省的是几何与 drawcall，不是只有 alpha）。
      var nRing = LY.pend ? LY.N : nOf(LY.key, LY.N);
      var opK = LY.pend ? LY.op : opOf(LY.key, LY.op);
      opBase[LY.key] = opK;
      if (opK <= 0) continue;
      var acc = { p: [], c: [], c2: [], i: [] };
      extrude(list, nRing, LY.step, acc, LY.key === 'trunk' ? { trunk: true, topKnee: TOP_KNEE } : null);
      /* T1 焰芯外晕：与主干同一份 acc 第二遍挤出（drawcalls 契约 C02 ≤ 4 → 不许新增 mesh）。
       * 纯金、半径 ×(TRUNK_W·HALO_K)、亮度 ×HALO_BR；共用同一套顶点的摇曳/根盘/梢端衰减。 */
      if (LY.key === 'trunk') extrude(list, nRing, LY.step, acc, { trunk: true, halo: true, topKnee: TOP_KNEE });
      if (!acc.p.length) continue;
      /* 摇曳基准 = **建造时**的单位空间原位（见 applySway 的说明）。
       * seenRev 置 -1：第一次 applySway 必须写一遍，否则「首帧姿态非零」时
       * 树会以上一档的旧姿态亮相一帧再突然跳到本帧（一闪）。 */
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
      mesh.raycast = function () {};                 // 背景层：鼠标必须穿过去
      mesh.userData.clPickable = false;
      mesh.userData.clLayer = 'tree-ghost';
      mesh.userData.clTree = true;   // 见 tree-veil.js 的说明：树层的显式标记，验收侧只认它
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
      // 数据可能比第一帧晚到（分析是异步的）。每 30 帧再试一次，别在 build 失败后就永远不画。
      if (++retry % 30 === 0) rebuild();
      return;
    }
    var age = born < 0 ? 0 : tAcc - born;
    var beat = calmK ? 0.5 : (s.beat != null ? num(s.beat, 0.5) : 0.5 + 0.5 * Math.sin(tAcc * 0.30));
    var breath = reduce ? 1 : 0.86 + 0.14 * beat;
    // 低档位不等生长动画（grow=0）：那时帧率本来就紧，再花 1.8 s 让枝条慢慢长出来是奢侈的
    var qGrow = Q() ? num(CLTreeQuality.of('grow'), 1) : 1;
    var noGrow = reduce || qGrow === 0;
    var k;
    for (k = 0; k < LAYERS.length; k++) {
      var LY = LAYERS[k], m = meshes[LY.key];
      if (!m) continue;
      var grow = noGrow ? 1 : clamp((age - LY.delay) / FADE, 0, 1);
      var lay = num(opBase[LY.key], LY.op) * depthK * grow * on * breath;
      // 树冠比树根呼吸更明显：细枝多叠一层错相的慢波，整棵树才像在换气而不是整体闪
      if (LY.key === 'twig' && !reduce && !calmK) lay *= 0.78 + 0.22 * (0.5 + 0.5 * Math.sin(tAcc * 0.30 + 1.1));
      if (muted || !vis) lay = 0;
      // 双保险：质量门面正常时，被砍的层压根没建（meshes 里没有、上面就 continue 了）；
      // 但门面万一缺席，档位屏蔽就只能落在这里。两步都留着，代价只是一次比较。
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

  /** 质量档一变，圈数就变，几何必须重建 —— 这不是"改个透明度"能糊过去的。
   *  重建是同步的（生成 BufferGeometry，约 10~40 ms）；档位切换本身是低频事件，可以接受。
   *  用事件而不是"在 update 里比对 qTag"，是因为 update 只拿到 degrade，拿不到"档位表本身改了"。 */
  function onQLv() { if (T && O) rebuild(); }
  if (window.addEventListener) window.addEventListener('cl:tree-quality', onQLv);

  /** 类型色探针：把七类事件色过一遍 ghostCol，报出实际的 RGB。
   *  这是 Q9「类型色标准差」与 Q10「色板同源」的唯一可量化入口 —— 顶点色是烘进去的，
   *  验收侧没法从几何里把色反推出来，只能让生产者自己报。 */
  function tintProbe() {
    if (!_c || !_c2) return [];
    var out = [], i, cc;
    for (i = 0; i < PALETTE.length; i++) {
      cc = ghostCol(PALETTE[i]);
      out.push([Math.round(cc.r * 255), Math.round(cc.g * 255), Math.round(cc.b * 255)]);
    }
    return out;
  }

  /** v39 全局压暗系数：1 = 原亮度，<1 = 压暗。sanitize 到 [0.05, 1]；
   *  非数 / 缺失（含 null/undefined）一律回 1.0 —— 「没要求压暗」比「压到最低」安全。
   *  幂等：同值重复写只是赋值，无副作用、不累积；置 1 即精确还原。
   *  下一帧的 update() 才会把它乘进材质 opacity（本函数只改系数，不碰材质）。 */
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
      clearGeom(); shape = null; retry = 0; dim = 1;   // 重建后不许残留压暗态
      shapeCache = null; shapeRef = null; shapeFp = null;   // 新会话必须重新取一次形状（不沿用旧引用）
      bindQ();               // dispose 会解绑，这里必须补回来（否则档位切换永远不重建）
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
    /** 环挤出圈数读数（验 tree-qc 的 Q7「圈数提档」用） */
    rings: function () {
      return { trunk: nOf('trunk', 12), bough: nOf('bough', 10), limb: nOf('limb', 8), twig: nOf('twig', 4) };
    },
    tint: tintProbe,
    /** v42 验收探针（**只读**）：返回第 i 个顶点的 (建造原位坐标, δ 桶号)。
     *  唯一用途：检验「建期预计算的桶」与「按同坐标现查 bucketOf」逐点一致 ——
     *  这是 R3 一致性判据的现场证据，不依赖任何推测。越界/缺层返回 null。 */
    bucketAt: function (key, i) {
      var bp = basePos[key], db = dBuf[key];
      if (!bp || !db) return null;
      var vi = i | 0;
      if (vi < 0 || vi * 3 + 2 >= bp.length) return null;
      var o = vi * 3;
      return { b: db[vi], p: [bp[o], bp[o + 1], bp[o + 2]] };
    },
    /** v42：某层的顶点数（桶缓冲长度）。 */
    bucketCount: function (key) { var db = dBuf[key]; return db ? db.length : 0; },
    /** v42：全部层的名字（供一致性测试遍历）。 */
    layers: function () { var out = [], k; for (k in dBuf) if (dBuf.hasOwnProperty(k)) out.push(k); return out; },
    /** v37 验收探针（**只读**，不改任何状态）：返回 n 个抽样顶点的
     *  「建造原位 basePos vs 当前 position」成对读数（单位空间、同下标顶点）。
     *  唯一用途：tree_qc A04' 的**交叉验证** —— Python 侧按数学规格独立复算行波公式，
     *  与 applySway 真正写进几何的顶点逐点比欧氏距离。缺层 / 未采样完时返回 []。 */
    sample: function (key, n) {
      var m = meshes[key], bp = basePos[key];
      if (!m || !bp) return [];
      var at = m.geometry && m.geometry.attributes && m.geometry.attributes.position;
      if (!at || !at.array) return [];
      var a = at.array, len = bp.length / 3;
      n = Math.floor(num(n, 1));
      if (!(n > 0) || len < 1) return [];
      var stp = Math.floor(len / n);           // 均匀抽样：步长 = floor(len/n)
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
