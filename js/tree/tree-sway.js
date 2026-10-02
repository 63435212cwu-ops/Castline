/* Castline · tree-sway.js — v37 摇曳姿态的**唯一真相**（window.CLTreeSway）
 *
 * 【v37 改了什么】v36 全树同一相位在摆（θ(y)=A·ampK·prof(y)·Σ_k G_k sin(W_k t + P_k)），
 * 动效审计指出「没有波从下往上传递的层次感」。v37 把每个频率分量的相位按高度延迟，
 * 延迟量 = W_k · TAU · prof(y)（弧度）。这就是**行波相位**模型，也是 v37 唯一的动效核心改动。
 *
 *   θz(y,t) = A · ampK · prof(y) · Σ_k G_k · sin( W_k·t + P_k          − W_k·TAU·prof(y) )
 *   θx(y,t) = A · ampK · XR · prof(y) · Σ_k G_k · sin( W_k·t + P_k + PX − W_k·TAU·prof(y) )
 *
 * 退化性质：TAU = 0 → 严格等于 v36 旧模型（相位延迟项全为 0）。
 * 数值安全：TAU ≤ 5s 时最大相位 1.17×5 = 5.85 rad，无溢出风险。
 *
 * 【v37 默认 TAU = 1.2 s】选值理由：TAU=0.6 错拍太弱（几乎还是全冠同相），TAU=2.4 冠顶
 * 相位被快频撕得太散、峰值倾角跌破 1.5° 下限且读起来「散架」；1.2s 让下部与冠部清晰错拍、
 * 冠顶仍收口成一体、峰值倾角仍在 1.5~8° 带内。互相关佐证见交付报告（延迟 ≈ TAU·(prof_hi−prof_lo)）。
 *
 * 【为什么单独一层 · 为什么按高度柔弯 · 风谱三频】—— 同 v36（见 git 历史），本层仍是
 * 全仓 7 处消费方（ghost 顶点循环 / cast-clones / star-migrate / tree-veil 三处 / legend / marks）
 * 唯一的姿态算法，签名 bendInto(px,py,pz,out) 不变、零分配、消费方零改动。
 *
 * 【成本纪律（不变）】每帧按 (t, ampK, TAU) 重建 SXT/CXT/SZT/CZT（4×65 Float32Array），
 * 顶点循环仍走查表+线性插值、一次三角都不做。新模型下每个 prof 采样点的角度含相位延迟
 * → 表按点算：每帧 65×10 ≈ 650 次三角（旧版 260 次，量级不变）。
 *
 * 【零重写纪律（不变·按 v37 调整）】签名字符串（t.toFixed(6)+'|'+ampK+'|'+TAU+'|'+归零标志）
 * 与上次相同 → 不重建表、rev 不涨。freeze 时 t 固定 → rev 必须冻结（tree_anim C04）；
 * 运行时 t 每帧变 → rev 每帧涨。归零开关（!on || muted || reduce || ampK<=0）→ 全表恒等
 * （sin=0, cos=1），进入/离开零态的 rev 只涨一次（签名里含归零标志，零态表与 t 无关）。
 *
 * 【v42 新增 · δ 场（逐枝错落）】v40 的 TAU-SCOUT 结论：单靠行波相位做不出「枝条彼此错开」——
 * 要 λ≈34× 树高才可能，物理上不可能是行波。可行解是**逐枝独立相位**：让每根枝按自己的方位角
 * 从同一个风场里取一个不同的相位偏移 δ，枝条就不再「齐步走」。
 *
 *   w(r)  = r²/(r²+R0²)                        R0 = 0.12；r² = px²+pz²
 *   h(θ)  = 0.62·sin(7θ+1.7) + 0.38·sin(13θ+4.1)   θ = atan2(pz,px)；两谐波，确定性，无随机
 *   δ(p)  = spread · w · h                     spread 由 CLTwigPhase 管辖（默认 0.35 rad）
 *   b     = clamp(round(w·h·8)+8, 0, 16)       17 桶，中心 8 = δ 恒 0
 *   几何  = 先绕 Y 轴转 δ_b，再走原来的 X→Z 摇曳
 *
 * 为什么是**桶**而不是逐点连续角：桶表只有 17 组 cos/sin，按桶查是 O(1) 数组取；逐点算
 * atan2+两次 sin 在 1.8 万顶点循环里是 0.3ms 级开销，而桶化的量化误差只有半桶
 * （spread=0.6 时 ±0.021 rad ≈ 1.2°），肉眼不可分。**桶号只依赖 (px,pz)**，与 y 无关。
 *
 * 三条硬性质（验收靠它们）：
 *  1) 中心桶 b=8 → cos=1,sin=0 → 绕 Y 旋转是**恒等变换**；IEEE754 下 px·1−pz·0 与 px 逐位相等，
 *     所以「δ 未激活 = v41 逐位」不是近似而是精确成立。δ 未激活（muted/on=false/reduce/
 *     ampK≤0/CLTwigPhase.setOn(false)/spread≤0）时 bucketOf 一律返回 8。
 *  2) δ 是**点位的纯函数**（只吃 px,pz）→ 任何消费方对同一点调 bendInto 必得同桶，
 *     一致性由架构保证，不需要跨模块对账。ghost 是唯一例外：热路径在建期预计算每顶点桶。
 *  3) 轴心 w(0)=0 → 主干中轴 δ 恒 0，树不会「掉头」。
 */
(function () {
  'use strict';

  var DEG = Math.PI / 180;

  /* ---- 风谱参数（全部是设计参数，不是随机数：确定性是硬约束） ---- */
  var BASE_AMP = 2.7 * DEG;   // 设计幅值（冠顶角幅）。z 轴峰谷差 = 2×2.7° = 5.4°
  var W1 = 0.19, W2 = 0.53, W3 = 1.17;      // rad/s：慢·主频 / 中·枝 / 快·梢
  var G1 = 0.62, G2 = 0.28, G3 = 0.10;      // 三频权重（和 = 1.0）
  var P1 = 0.00, P2 = 2.31, P3 = 4.72;      // 固定相位：三频不同时过零，避免整树「统一呼吸」
  var PX = 1.90;                            // X 轴相位差 → 摆动走椭圆而非直线
  var XR = 0.42;                            // X 轴幅值比（主风沿 Z 轴走）

  /* ---- 高度柔度剖面 ---- */
  var Y_TOP = 1.15;                         // 标称冠顶高度（树根 y=0）。真 AABB 顶约 1.12
  var POW = 1.6;                            // 柔度指数：位移 ∝ u^(POW+1) = u^2.6（悬臂梁味道）
  var NT = 64;                              // 表分辨率
  var PROF = new Float32Array(NT + 1);
  var i0;
  for (i0 = 0; i0 <= NT; i0++) PROF[i0] = Math.pow(i0 / NT, POW);
  var INV_YTOP = 1 / Y_TOP;

  /* ---- 行波延迟常数（秒）：v37 唯一新增的状态 ---- */
  var TAU = 1.2;                            // 见文件头注释的选值理由

  /* ---- v42 · δ 场常数与状态 ---- */
  var R02 = 0.12 * 0.12;                    // w(r) 的半功率半径平方
  var DNB = 17, DCENTER = 8;                // 17 桶，中心桶 = δ 恒 0
  var DH1 = 7, DP1 = 1.7, DG1 = 0.62;       // 低次谐波（方位角方向的粗结构）
  var DH2 = 13, DP2 = 4.1, DG2 = 0.38;      // 高次谐波（细结构）；DG1+DG2 = 1 → |h| ≤ 1
  var dOn = false;                          // CLTwigPhase.on() 的镜像
  var dSpread = 0;                          // CLTwigPhase.spread() 的镜像（rad）
  var DCS = new Float32Array(DNB), DSS = new Float32Array(DNB);   // 17 组 cos/sin
  var dTabMode = 'identity';                // δ 表上次构建模式：'identity' | 'spread'（stats 探针）

  var T = null, dummy = null, v3 = null;
  function ensureT() {
    if (!T && typeof window !== 'undefined' && window.THREE) T = window.THREE;
    if (T && !dummy) { dummy = new T.Object3D(); v3 = new T.Vector3(); }
    return !!(T && dummy);
  }

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  /* ---- 状态 ---- */
  var t = 0;                 // 绝对时间（从 s.t 取，避免累积误差）
  var on = 1;                // arcana 的 on（聚焦态为 0）
  var muted = false;         // 总开关（G 键，经 arcana 的 setOn）
  var reduce = false;        // prefers-reduced-motion
  var frozen = null;         // 非 null = 冻结在某个 t（验收用）
  var ampK = 1;              // 画质档位系数（CLTreeQuality 'sway'）
  var rev = 0;               // 姿态版本号：**变了才 ++**。消费方靠它省掉静止帧的全部重写
  var tabKey = '';           // 建表时的姿态签名
  var tabDirty = true;

  /* ---- 查表：4 条曲线，按 prof 均匀采样 ---- *
   * 新模型下每点存的是「该高度处的精确 sin/cos 角度」，角度已含行波相位延迟，
   * 所以顶点循环里重解出来就是当时该点的真实姿态。 */
  var SXT = new Float32Array(NT + 1), CXT = new Float32Array(NT + 1);
  var SZT = new Float32Array(NT + 1), CZT = new Float32Array(NT + 1);

  function effT() { return (frozen != null) ? frozen : t; }

  /** v42：17 桶 cos/sin 表。δ_b = spread·(b−DCENTER)/8 —— 桶与 spread 成线性，
   *  所以改 spread 只要重算这 17 组三角（34 次），不必碰 65 点的摇曳主表之外的任何东西。
   *
   *  ⚠ 必须按 **deltaLive()** 而不是裸 dSpread 建表（v42 实测踩过，代价是一整天）：
   *  CLTwigPhase 关闭时 spread() 仍读数 0.35（on=false 但 spread 保留），镜像 dSpread
   *  于是也是 0.35 —— 只吃 dSpread 的话，关态表仍是 0.35 的旋转：δ 开关两态几何逐位相同
   *  （δ 永远"没进几何"），且「缺省桶 == 显式桶」的一致性冒烟也照样绿（两条路径错得一模一样，
   *  互相抵消）。按 deltaLive 建表才是文档承诺的那条不变量：
   *  「未激活 → 全表 (1,0) 恒等 → 传真实桶与传中心桶几何逐位相同」。 */
  function buildDeltaTabs() {
    var i, a;
    if (!deltaLive()) {
      for (i = 0; i < DNB; i++) { DCS[i] = 1; DSS[i] = 0; }
      dTabMode = 'identity';
      return;
    }
    for (i = 0; i < DNB; i++) {
      a = dSpread * (i - DCENTER) / 8;
      DCS[i] = Math.cos(a); DSS[i] = Math.sin(a);
    }
    dTabMode = 'spread';
  }

  function buildTabs() {
    var zero = (!on || muted || reduce || ampK <= 0);
    buildDeltaTabs();
    if (zero) {
      /* 全表恒等：sin=0, cos=1 → bendInto 逐点原样返还（真归零，不是小幅度）。 */
      var i;
      for (i = 0; i <= NT; i++) { SXT[i] = 0; CXT[i] = 1; SZT[i] = 0; CZT[i] = 1; }
      return;
    }
    /* 行波模型：每个频率分量按高度延迟 W_k·TAU·prof(y) 弧度，再按高度乘柔度叠加。 */
    var TT = effT(), A = BASE_AMP * ampK;
    var i2, u, sZ, sX, aZ, aX;
    for (i2 = 0; i2 <= NT; i2++) {
      u = PROF[i2];
      sZ = G1 * Math.sin(W1 * TT + P1 - W1 * TAU * u)
         + G2 * Math.sin(W2 * TT + P2 - W2 * TAU * u)
         + G3 * Math.sin(W3 * TT + P3 - W3 * TAU * u);
      sX = G1 * Math.sin(W1 * TT + P1 + PX - W1 * TAU * u)
         + G2 * Math.sin(W2 * TT + P2 + PX - W2 * TAU * u)
         + G3 * Math.sin(W3 * TT + P3 + PX - W3 * TAU * u);
      aZ = A * u * sZ;
      aX = A * XR * u * sX;
      SZT[i2] = Math.sin(aZ); CZT[i2] = Math.cos(aZ);
      SXT[i2] = Math.sin(aX); CXT[i2] = Math.cos(aX);
    }
  }

  /* 重建纪律（**性能纪律**）：签名 = (t 或 'Z')|ampK|TAU。
   * freeze 时 t 固定 → 签名不变 → 不重建、rev 不涨。
   * 归零态签名不含 t（零态表与 t 无关）→ 进入/离开零态 rev 只涨一次。
   *
   * ⚠ 签名只在 **update 里拼一次**（每帧一次），顶点循环只做布尔判断（rebuildIfDirty）。
   * 原实现把签名拼接放在 sync() 里、bendInto 每顶点都调 —— 1.8 万顶点 × 字符串拼接/帧
   * 是白烧 CPU（v36 顶点循环零三角的纪律，同样适用于字符串）。 */
  var lastSig = '';          // update 侧签名的上次值
  function poseSig() {
    var zero = (!on || muted || reduce || ampK <= 0);
    return zero ? ('Z|' + ampK.toFixed(4))
                : (effT().toFixed(6) + '|' + ampK.toFixed(4) + '|' + TAU.toFixed(6));
  }

  /** v42：δ 的独立签名。**必须与 poseSig 分开** ——
   *  poseSig 在 freeze 期间是常量（这正是 tree_anim C04「冻结则 rev 不动」的前提），
   *  于是 δ 开关如果只体现在 poseSig 里，冻结态下 rev 就不会涨，ghost 的 applySway
   *  会因为 seenRev === rev 直接跳过，**δ 永远写不进几何**（v42 实测踩过：顶点校验和
   *  在 δ 开关两态下逐位相同，δ 明明是对的）。分开之后：时间冻结不影响 δ 生效，
   *  δ 一变 rev 就涨一次，几何与像素两条证据都能拿到。 */
  function deltaSig() {
    if (!(!on || muted || reduce || ampK <= 0) && dOn && dSpread > 1e-6) return 'd' + dSpread.toFixed(6);
    return 'd0';
  }
  var lastDeltaSig = '';
  /** 消费方（bendInto / pose）唯一入口：一个布尔判断，脏了才重建。 */
  function rebuildIfDirty() {
    if (!tabDirty) return;
    tabDirty = false;
    buildTabs();
  }

  /* ================= v42 · δ 场 ================= */

  /** CLTwigPhase 的镜像轮询。**只在 update() 每帧一次 + 查询 API（bucketOf/deltaAt）入口调**，
   *  不进 bendsInto 热路径 —— 1.8 万顶点 × 属性读取是白烧 CPU（同一个教训 v36 在字符串
   *  拼接上踩过一次）。轮询到变化只置 tabDirty：rev 仍由 update() 的签名比对统一涨，
   *  这样 freeze 期间 rev 不会被 δ 变更偷涨（tree_anim C04 的前提）。
   *  v41 的 spread/on 唯一真相在 CLTwigPhase，本模块只做**镜像**，绝不反向写回。 */
  function pollPhase() {
    var P = window.CLTwigPhase;
    if (!P || typeof P.on !== 'function' || typeof P.spread !== 'function') {
      if (dOn !== false) { dOn = false; tabDirty = true; }
      return;
    }
    /* 不用 tryFn(fn 字面量)：那会给每次调用分配一个闭包 —— 查询 API 可能被消费方的
     * 循环调上万次（缺省桶路径就是），堆分配比 try 本身贵一个量级。 */
    var o, s;
    try { o = !!P.on(); } catch (e) { o = false; }
    try { s = +P.spread(); } catch (e) { s = 0; }
    if (!isFinite(s)) s = 0;
    if (s < 0) s = 0;
    if (o !== dOn || s !== dSpread) { dOn = o; dSpread = s; tabDirty = true; }
  }

  /** δ 是否真的作用在几何上。**与摇曳的归零开关完全同源**（!on||muted||reduce||ampK<=0），
   *  这样「摇曳关闭」与「错落关闭」永远同进同出，不会出现静止的树却在错落的怪状态。 */
  function deltaLive() {
    return !(!on || muted || reduce || ampK <= 0) && dOn && dSpread > 1e-6;
  }

  /** 场函数（不含状态判断）：w·h ∈ [-1,1]。给 deltaAt 用，返回连续场值。 */
  function fieldAt(px, pz) {
    var r2 = px * px + pz * pz;
    var w = r2 / (r2 + R02);
    var th = Math.atan2(pz, px);
    var h = DG1 * Math.sin(DH1 * th + DP1) + DG2 * Math.sin(DH2 * th + DP2);
    return w * h;
  }

  /** 点 → 桶号（0..16）。**δ 未激活一律返回中心桶 8**（= 文档化的 API 语义）。
   *  桶号只依赖 (px,pz)：同一条竖直枝上的所有点同桶 → 枝条整体旋转，不会被拧成麻花。
   *
   *  ⚠ 建期预计算**不要**用这个，用 bucketRaw —— 本函数吃状态（未激活时恒 8），
   *  而消费方建缓冲的时刻往往早于 CLTwigPhase 就绪，会把整张缓冲填成 8（v42 实测踩过：
   *  ghost 121 个抽样顶点里 76 个桶错，就是建期 dOn 还是 false 导致的）。 */
  function bucketOf(px, py, pz) {
    pollPhase();
    if (!deltaLive()) return DCENTER;
    return bucketRaw(px, pz);
  }

  /** **纯几何**桶查询（只吃 px,pz，不吃任何开关 / spread / 就绪状态）。
   *  为什么消费方可以无条件用真实桶：桶表在未激活时全为 (cos=1,sin=0)= 恒等旋转，
   *  所以「传真实桶但 δ 关闭」与「传中心桶」的**几何结果逐位相同**。
   *  这条性质是 R3 一致性的全部依据 —— 建期算一次，永久有效，不需要任何失效逻辑。 */
  function bucketRaw(px, pz) {
    var b = Math.round(fieldAt(px, pz) * 8) + DCENTER;
    return b < 0 ? 0 : (b > 16 ? 16 : b);
  }

  /** 查询 API：返回 {b, delta}。b 是量化桶号，delta 是**连续场值**（rad）——
   *  两者的关系是 dSpread·(b−8)/8 ± 半桶，验收同时要这两个读数（一个查一致性、一个查量级）。 */
  function deltaAt(px, py, pz) {
    pollPhase();
    var q = fieldAt(px, pz);
    if (!deltaLive()) return { b: DCENTER, delta: 0 };
    return { b: bucketRaw(px, pz), delta: dSpread * q };
  }


  /* ---- 风场：归一化姿态（无延迟口径）。z 为主动轴、x 为副轴（相位差 → 椭圆轨迹）。
   * 这是 v37 的「无延迟 t 时刻风场值」，供 norm() 使用（旧模型 cur 的精确等价物）。 */
  function compute(TT) {
    var z = G1 * Math.sin(W1 * TT + P1) + G2 * Math.sin(W2 * TT + P2) + G3 * Math.sin(W3 * TT + P3);
    var x = XR * (G1 * Math.sin(W1 * TT + P1 + PX) +
                  G2 * Math.sin(W2 * TT + P2 + PX) +
                  G3 * Math.sin(W3 * TT + P3 + PX));
    return { x: x, z: z };
  }

  function qSway() {
    var Q = window.CLTreeQuality;
    if (!Q || !Q.of) return 1;
    var v = tryFn(function () { return Q.of('sway'); });
    return v == null ? 1 : num(v, 1);
  }

  function reduceNow() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  /** 单位空间点 (px,py,pz) → 摇曳后的点，写进 out（**零分配**）。
   *  这是全世界唯一的姿态算法：ghost 的顶点循环、星点、分身星与连线、枝雾、星尘
   *  全部经这里。out 通常是一个复用的 scratch 数组，别把它存起来。
   *
   *  v42 第 5 参 b（可选）：该点的 δ 桶号。缺省 = 按点查（走 bucketOf）。ghost 的 1.8 万顶点
   *  循环**必须显式传桶**（建期预计算），否则每顶点都要 atan2+两次 sin —— 那是 1ms 级开销。
   *  传 8 或不传且 δ 未激活 → 下两行退化成恒等，逐位等于 v41。 */
  function bendInto(px, py, pz, out, b) {
    rebuildIfDirty();
    var u = py * INV_YTOP;
    if (u <= 0) { out[0] = px; out[1] = py; out[2] = pz; return out; }
    if (u > 1) u = 1;
    /* δ：先绕 Y 轴转自己那一份相位。桶号来自点本身（或消费方预计算），与高度无关 →
     * 同一条竖直枝整体旋转，不会被拧成麻花。 */
    var bb = (b === undefined || b === null) ? bucketOf(px, py, pz) : (b | 0);
    if (bb < 0) bb = 0; else if (bb > 16) bb = 16;
    var dc = DCS[bb], ds = DSS[bb];
    var rx = px * dc - pz * ds, rz = px * ds + pz * dc;
    var f = u * NT, i = f | 0, tt;
    if (i >= NT) { i = NT - 1; tt = 1; } else tt = f - i;
    var j = i + 1;
    var sx = SXT[i] + (SXT[j] - SXT[i]) * tt, cx = CXT[i] + (CXT[j] - CXT[i]) * tt;
    var sz = SZT[i] + (SZT[j] - SZT[i]) * tt, cz = CZT[i] + (CZT[j] - CZT[i]) * tt;
    /* 先绕 X 再绕 Z。**不用线性小角近似**：θ 最大 2.7° 时二阶项仍有 1.1e-3 单位 ≈ 0.5 px，
     * 那点误差在 1.8 万顶点上是看得见的「树在缓慢变形」。查表拿的是**精确** sin/cos。 */
    var y1 = py * cx - rz * sx, z1 = py * sx + rz * cx;
    out[0] = rx * cz - y1 * sz; out[1] = rx * sz + y1 * cz; out[2] = z1;
    return out;
  }

  /** 单发版（会分配）。只在「一次一两点」的地方用；批量一律 bendInto + scratch。 */
  function bend(p) {
    if (!p || p.length < 3) return p ? [p[0], p[1], p[2]] : [0, 0, 0];
    return bendInto(p[0], p[1], p[2], [0, 0, 0]);
  }

  /** 该高度处的真实角度（弧度）。**从表里反解**，与顶点循环用的是同一组数。
   * v37：含行波相位差 —— 同一时刻、不同高度的角不再相等，这正是「波从下往上」的层次感。 */
  function pose(y) {
    rebuildIfDirty();
    var u = num(y, 0) * INV_YTOP;
    if (u <= 0) return { ax: 0, az: 0 };
    if (u > 1) u = 1;
    var f = u * NT, i = f | 0, tt;
    if (i >= NT) { i = NT - 1; tt = 1; } else tt = f - i;
    var j = i + 1;
    var sx = SXT[i] + (SXT[j] - SXT[i]) * tt, cx = CXT[i] + (CXT[j] - CXT[i]) * tt;
    var sz = SZT[i] + (SZT[j] - SZT[i]) * tt, cz = CZT[i] + (CZT[j] - CZT[i]) * tt;
    return { ax: Math.atan2(sx, cx), az: Math.atan2(sz, cz) };
  }

  /** 供**刚体**用：把整个 Object3D 按它所在高度 yRef 的姿态摆好。
   *  只有当物体所有顶点高度相同时这才是精确的 —— 刻度环正是这种（同高的圆）。
   *  顶点横跨多个高度的物体（mesh/点云）必须走 bendInto 逐点算，不许用这个。 */
  function dress(obj, yRef) {
    if (!obj || !obj.rotation) return;
    var q = pose(num(yRef, 0));
    obj.rotation.set(q.ax, 0, q.az);
  }

  function update(s) {
    s = s || {};
    on = num(s.on, on);
    if (s.muted !== undefined) muted = !!s.muted;
    reduce = reduceNow();
    var k = qSway();
    if (k !== ampK) { ampK = k; tabDirty = true; }
    t = num(s.t, t + 0.016);
    /* v42：每帧一次镜像 CLTwigPhase（订阅式接口不存在，轮询是唯一低成本路径；
     * 每帧一次 × 属性读取 = 零成本，绝不进顶点循环）。必须在两个签名之前。 */
    pollPhase();
    /* rev 的涨落完全由这里管：签名变（运行时 t 每帧变）→ 涨；
     * 签名不变（freeze / 归零态）→ 不涨。update 是唯一拼签名与 bump rev 的地方。
     * v42 加了 δ 的独立签名：它不吃 t，所以冻结态下 δ 一变也照样能涨一次。 */
    var dsig = deltaSig();
    if (dsig !== lastDeltaSig) { lastDeltaSig = dsig; tabDirty = true; rev++; }
    var sig = poseSig();
    if (sig !== lastSig) { lastSig = sig; tabDirty = true; rev++; }
    rebuildIfDirty();
    return true;
  }

  /* ---- 验收接口 ---- */
  function freeze(TT) { frozen = num(TT, 0); tabDirty = true; return frozen; }
  function resume() { frozen = null; tabDirty = true; return true; }

  /** v37 新增：运行时设行波延迟常数 TAU（秒）。sanitize 为 [0,5] 内有限数，返回实际生效值。 */
  function setWave(tau) {
    var v = num(tau, TAU);
    if (!isFinite(v)) v = TAU;
    if (v < 0) v = 0;
    if (v > 5) v = 5;
    TAU = v;
    tabDirty = true;
    return TAU;
  }

  function norm() {
    /* v37 语义：报「无延迟的 t 时刻风场值」= 旧 compute(t)（行波相位置 0 的 (x,z)）。
     * 旧模型 cur 的精确等价物；新模型没有单一 cur 标量对，故用此口径保留归一化读数。 */
    var c = compute(effT());
    return { x: +c.x.toFixed(6), z: +c.z.toFixed(6) };
  }

  /** 该高度的角度读数（度）—— A01~A04 用的唯一入口（v37：含行波相位差） */
  function degAt(y) {
    var q = pose(y);
    return { ax: +(q.ax / DEG).toFixed(6), az: +(q.az / DEG).toFixed(6) };
  }

  /** 单点位移读数：把 (r, y, 0) 这一处「某层最外侧代表点」搬一次，报位移量（单位空间）。
   *  层间递增（A04）就是拿四个层各自的特征 (r,y) 来比的 —— 比角度更贴近肉眼看到的「摆幅」。 */
  function dispAt(y, r) {
    var s = [0, 0, 0];
    bendInto(num(r, 0), num(y, 0), 0, s);
    var dx = s[0] - num(r, 0), dy = s[1] - num(y, 0), dz = s[2] - 0;
    return +Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(8);
  }

  function stats() {
    pollPhase();   /* 验收读 stats() 时可能一帧都没走过（脚本里 setOn 完立刻读），
                    * 所以这里也轮询一次，保证读数与 CLTwigPhase 的真实状态一致。 */
    return {
      on: on, muted: muted, reduce: reduce, ampK: ampK, frozen: frozen, rev: rev,
      t: +t.toFixed(4),
      norm: norm(),
      ampDeg: +(BASE_AMP / DEG).toFixed(3),
      period: +(2 * Math.PI / W1).toFixed(3),
      yTop: Y_TOP, pow: POW, tabN: NT,
      delta: {
        on: deltaLive(),
        spread: +dSpread.toFixed(6),
        /* deg = spread 换算成「多少度」。画质牌与快捷键提示都用它，避免各写一处 180/π。
         * spread 是**弧度**（契约 δ 场的单位），但人读「错落 ±20°」比「±0.35 rad」直观。
         * 这是**峰值**：ω(r)=r²/(r²+0.12²) 与 h(θ) 的绝对值最大为 1，所以实际单枝相位落在 [−deg, +deg]。 */
        deg: +(dSpread / Math.PI * 180).toFixed(1),
        nb: DNB,
        center: DCENTER,
        mirrorOn: dOn,
        tabMode: dTabMode,     // 'identity' | 'spread'：δ 表上次构建模式（关态必须 identity）
        r0: Math.sqrt(R02),
        h: [DH1, DP1, DG1, DH2, DP2, DG2]
      },
      deg: { y0: degAt(0), y30: degAt(0.30), y60: degAt(0.60), y90: degAt(0.90) },
      dispY: { y0: dispAt(0, 0.2), y30: dispAt(0.30, 0.10), y60: dispAt(0.60, 0.32), y90: dispAt(0.90, 0.50) },
      wave: {
        on: true,
        tau: +TAU.toFixed(4),
        freqs: [W1, W2, W3],
        gains: [G1, G2, G3],
        phases: [P1, P2, P3],
        xr: XR,
        px: PX
      }
    };
  }

  var API = {
    name: 'tree-sway',
    build: function () { ensureT();
      /* 首帧就把表建好：万一有消费方在第一次 update 之前就调 bendInto，
       * 拿到的必须是「静止」而不是「上一轮的残余」。 */
      rebuildIfDirty(); return true; },
    update: update,
    dispose: function () { frozen = null; tabDirty = true; return true; },
    bend: bend,
    bendInto: bendInto,
    pose: pose,
    dress: dress,
    degAt: degAt,
    dispAt: dispAt,
    freeze: freeze,
    resume: resume,
    setWave: setWave,
    setOn: function (v) { muted = !v; tabDirty = true; return true; },
    /* v42 δ 场 */
    bucketOf: bucketOf,
    bucketRaw: bucketRaw,
    deltaAt: deltaAt,
    fieldAt: fieldAt,
    deltaLive: deltaLive,
    get: function () { return { t: t, on: on, muted: muted, reduce: reduce, ampK: ampK, frozen: frozen, rev: rev, tau: TAU }; },
    norm: norm,
    rev: function () { return rev; },
    stats: stats
  };

  window.CLTreeSway = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();

  if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
    window.CLAbyssBreath.subscribe(function (snap) {
      if (snap && isFinite(snap.t)) {
        update({ t: snap.t });
      }
    });
  }
})();
