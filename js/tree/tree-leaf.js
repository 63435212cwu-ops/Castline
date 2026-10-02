/* Castline · tree-leaf.js — v32 叶位分配（window.CLTreeLeaf）
 *
 * 一片叶 = 一个 (剧情线, 角色) 组合的落点。它是「点一下按钮，星点飞到枝干上就位」的目标位。
 *
 * 为什么不按 (事件, 角色) 出叶：三国规模下那是上千个点，一个角色会碎成一片噪声；
 * 按线出叶则正好回答用户要看的那件事 —— **这个人在哪几条线上**。
 * 同一个角色在多条线上就有多片叶：**不去重、不合并**，用户明确要看见重复出场。
 */
(function () {
  'use strict';

  var GOLD = 2.39996;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function str(v) { return v == null ? '' : String(v); }

  function vadd(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vmul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function vlen(a) { return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]); }
  function vnorm(a) { var L = vlen(a); return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0]; }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  var CACHE = null, CACHE_KEY = '', MS = {};

  function empty(reason) {
    return { ok: false, reason: reason, fp: '', leaves: [], byName: {}, byThread: {},
      stats: { leaves: 0, names: 0, dupNames: 0, maxPerName: 0, avgPerName: 0, onTrunk: 0, onBough: 0,
        spilled: 0, spillDY: -1, spillRr: -1, spillN: 0, loadMin: 0, loadMax: 0, loadUsed: 0, boughN: 0,
        ms: 0, fp: '', warn: [] } };
  }

  function assignLegacy(shape, tree, opts) {
    opts = opts || {};

    var key = 'L35|' + str(shape.fp) + '|' + str(tree.fp) + '|' + num(opts.maxLeaves, 900);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var i, j, k, warn = [], maxLeaves = num(opts.maxLeaves, 900);
    var TH = tree.threads || [], segs = (shape.trunk && shape.trunk.segs) || [];
    var BOUGHS = shape.boughs || [], TAU2 = Math.PI * 2;
    /** 每段主线**留在主干上**的叶数。0.20 是"重要人物"的比例，夹在 [2,4]：
     *  下界 2 保证小段不会一根叶不剩（那会读成"这条线在主干上消失了"），
     *  上界 4 保证大段不会把主干重新糊满。
     *  v34 用 0.34/[3,7] 实测留 26 片 = 13.5%；v35 收到 0.20/[2,4] 目标 ≤9%
     *  —— 真实的树干是光秃的，主干上那几片只该是「这条线在这里」的锚点。 */
    function spillN(n) { return n <= 0 ? 0 : clamp(Math.round(n * 0.20), 2, 4); }

    /** 就近选枝的状态：每根一级枝的**挂点**（pts[0]）与已收叶数。
     *  挂点而不是枝的中段：溢出叶是从主干散出来的，枝根是它最自然的落点。 */
    var boughLoad = [], boughRoot = [], bi;
    for (bi = 0; bi < BOUGHS.length; bi++) {
      boughLoad.push(0);
      boughRoot.push((BOUGHS[bi].pts && BOUGHS[bi].pts.length) ? BOUGHS[bi].pts[0] : [0, 0, 0]);
    }
    /** 主干上参数 t 处的点（插值）。用于算"这片叶本来长在哪儿"。 */
    function trunkPtAt(t) {
      var pts = (shape.trunk && shape.trunk.pts) || [];
      if (!pts.length) return [0, 0, 0];
      var u = clamp(t, 0, 1) * (pts.length - 1), a = Math.floor(u), b = Math.min(pts.length - 1, a + 1), f = u - a;
      return vadd(vmul(pts[a], 1 - f), vmul(pts[b], f));
    }
    /** 溢出叶选枝（v35）：**以就近为主、均衡为辅**，取代 v34 的「轮询 slot % 枝数」。
     *  轮询虽然天然均衡，却完全无视空间 —— 长在主干 0.2 处的叶可能被派到 0.7 处的一级枝根，
     *  读起来是「叶子乱飞」。
     *
     *  ⚠ 这一条调了三次才对，两次失败都值得记：
     *   ① 加权和 cost = dh + 0.85·dy + 0.16·load → 实测比 0.939，**等于没改**。
     *      负载项强到能防塞爆（攒 5 片 +0.80）时，已经盖过高度差全域（dy 只有 0~0.8），
     *      「均衡」把「就近」吃掉了。教训：**两个目标揉进一个加权和，系数就成了零和博弈**。
     *   ② 两级决策（最近 6 根里挑收叶最少的）→ 比 0.718，就近有改善，但极差 2~8 仍不均衡。
     *      原因：候选集**按高度偏斜** —— 多数叶都在低处，最近 6 根永远是那几根矮枝。
     *      **限制候选集本身就在制造不均**。
     *   ③ 恒定小系数 0.03 → 比 0.670（就近很好），但极差 1~11（低处枝被反复选）。
     *      恒定系数没有「进度」概念：开头该摊得开，后头该允许集中，同一个数做不到两件事。
     *   ④ 最终式：**水填式软上限**。上限 tgt = 2 + 已选片数/枝数，只有超过才罚，罚项平方：
     *        cost = |Δy| + (load > tgt ? (load−tgt)² · 0.12 : 0)
     *      tgt 随进度自然抬高 —— 开头 ≈2（摊开），收尾 ≈6（允许集中到 62/15≈4 上下）。
     *      实测 dy 均值 0.21（轮询 0.30，优 30%），各枝收叶 1~6。
     *
     *  ⚠ 另一个实测提醒：叶的原位与枝的挂点**都贴着主干轴**（|x|,|z| ≤ 0.05），水平距离 dh 因此
     *    几乎没有区分度（所有枝都在 0.02~0.06 之间），真正决定「就近」的是**高度差 dy**。
     *    打分里干脆不要 dh —— 留着只会让「就近」看起来比实际更好。
     *  返回 {i: 枝序号, load: 收之前已收几片, dy: 高度差} —— dy 是「就近度」的实证读数（Q6c 用）。 */
    function pickBough(p) {
      var best = 0, bestCost = 1e18, bestDY = 0, k2;
      var tgt = 2 + outN / Math.max(1, BOUGHS.length);
      for (k2 = 0; k2 < BOUGHS.length; k2++) {
        var dyy = Math.abs(p[1] - boughRoot[k2][1]);
        var over = boughLoad[k2] - tgt;
        var cost = dyy + (over > 0 ? over * over * 0.12 : 0);
        if (cost < bestCost) { bestCost = cost; bestDY = dyy; best = k2; }
      }
      var l0 = boughLoad[best];
      boughLoad[best] = l0 + 1;
      return { i: best, load: l0, dy: bestDY };
    }

    // 宿主索引：线 → 枝。主线段没有独立的枝，落在主干上。
    var hostOf = {}, mainIds = {};
    for (i = 0; i < segs.length; i++) mainIds[str(segs[i].threadId)] = segs[i];
    var trunkHost = { id: 'trunk', level: 0, pts: shape.trunk.pts, r: shape.trunk.r, az: 0 };
    for (i = 0; i < (shape.boughs || []).length; i++) hostOf[str(shape.boughs[i].threadId)] = shape.boughs[i];
    for (i = 0; i < (shape.limbs || []).length; i++) {
      var lm = shape.limbs[i], tid = str(lm.threadId);
      if (tid && !hostOf[tid]) hostOf[tid] = lm;         // 一条线只认第一根同名枝（结构性分枝共用 threadId）
    }

    /** 枝上 at 处、绕枝 az 方位、外推 r*2.2 的落点。
     *  法向必须由该处的真实切线求：叶子贴着枝面长，用全局轴算会让下垂段的叶子插进枝里。 */
    function leafPos(host, at, az, spread) {
      var pts = host.pts, rr = host.r;
      var hi = clamp(Math.round(at * (pts.length - 1)), 0, pts.length - 1);
      var base = pts[hi], rad0 = num(rr[hi], 0.01);
      var tan = vnorm(vsub(pts[Math.min(pts.length - 1, hi + 1)], pts[Math.max(0, hi - 1)]));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      var nrm = vnorm(vadd(vmul(U, Math.cos(az)), vmul(W, Math.sin(az))));
      // 外推量不能只按枝半径给：主干半径只有 0.019，78 片主线叶全贴在轴上会堆成一根竖柱
      // （实测第一版就是这样）。所以主干叶另给一个**绝对**的螺旋外推量。
      return { pos: vadd(base, vmul(nrm, Math.max(rad0 * 2.2, num(spread, 0)))), r: rad0 };
    }

    // ── 第一遍：统计全主干叶总数，供主干叶螺旋展开用全局占比（确定性，不依赖随机）
    var trunkLeafTotal = 0;
    for (i = 0; i < TH.length; i++) {
      var t1 = TH[i] || {}, tid1 = str(t1.id), cs1 = t1.cast || [];
      if (!cs1.length) continue;
      var h1 = hostOf[tid1];
      if (mainIds[tid1] || num(t1.depth, 1) === 0) h1 = trunkHost;
      if (!h1) { h1 = hostOf[str(t1.parent)]; if (!h1) h1 = trunkHost; }
      if (h1 === trunkHost) {
        for (j = 0; j < cs1.length; j++) { if (str(cs1[j] && cs1[j].name)) trunkLeafTotal++; }
      }
    }

    // ── 一线一批：该线的 cast 全部出叶
    var raw = [], onTrunk = 0, kTrunk = 0, outN = 0, spilled = 0, spillSum = 0, spillCnt = 0, rrSum = 0;
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, tid2 = str(th.id), cast = th.cast || [];
      if (!cast.length) continue;
      var host = hostOf[tid2], hostKind = 1;
      if (mainIds[tid2] || num(th.depth, 1) === 0) { host = trunkHost; hostKind = 0; }
      if (!host) {
        host = hostOf[str(th.parent)];
        if (host) warn.push('线 ' + tid2 + ' 没有对应的枝，已挂到父线的枝上');
        else { host = trunkHost; hostKind = 0; warn.push('线 ' + tid2 + ' 没有对应的枝，已挂主干'); }
      }
      var hostLevel = host === trunkHost ? 0 : num(host.level, hostKind);
      // 同一根枝上按权重降序铺开：权重大的更靠根部（那里更粗、更显眼）
      var cs = cast.slice();
      cs.sort(function (a, b) {
        var d = num(b.w, 0) - num(a.w, 0);
        if (d) return d;
        return str(a.name) < str(b.name) ? -1 : (str(a.name) > str(b.name) ? 1 : 0);
      });
      /* 两个序号，各管一件事：
       *   j  —— 权重序。决定「谁配留在主干上」（权重大的留下，那是这段的重要人物）。
       *   ord —— 时序序（entry 升序）。决定「叶铺在枝上的哪个位置」——
       *          故事里先出场的人靠枝根（近主干），后出场的往外走，整根枝读起来就是一条时间轴。
       * v32 只有一个权重序，于是枝上的位置也由重要性决定，时间轴是乱的。 */
      var ord = {}, csT = cs.slice(), q2;
      csT.sort(function (a, b) {
        var ea = num(a.entry, -1), eb = num(b.entry, -1);
        if (ea < 0 && eb >= 0) return 1;
        if (eb < 0 && ea >= 0) return -1;
        if (ea !== eb) return ea - eb;
        return str(a.name) < str(b.name) ? -1 : (str(a.name) > str(b.name) ? 1 : 0);
      });
      for (q2 = 0; q2 < csT.length; q2++) ord[str(csT[q2].name)] = q2;
      var mainSeg = mainIds[tid2];
      // 主干叶分流（Q6）：真实的树干是光秃的，不该挂满叶。
      // 每段只留权重最高的 keepN 片贴主干，其余散到一级枝上 —— 选枝用 pickBough（空间就近 + 负载惩罚）。
      var keepN = spillN(hostLevel === 0 ? cs.length : 0);
      for (j = 0; j < cs.length; j++) {
        var c = cs[j] || {}, nm = str(c.name);
        if (!nm) continue;
        var hUse = host, lvUse = hostLevel, lane = 0, pickDY = -1, rrDY = -1;
        var tIdx = ord[nm] != null ? ord[nm] : j;
        var dnm = Math.max(1, cs.length - 1);
        // 「这片叶本来长在主干哪儿」只依赖主线段与序号，与最终挂谁无关 → 先算出来，供就近选枝。
        // （v34 是在 lvUse===0 分支里算的，那时候已经选完枝了，来不及。）
        var s0 = mainSeg ? num(mainSeg.t0, 0.1) : 0.1, s1 = mainSeg ? num(mainSeg.t1, 1) : 0.9;
        var atT = clamp(s0 + (s1 - s0) * (cs.length === 1 ? 0.5 : 0.12 + 0.76 * (tIdx / dnm)), 0.02, 0.985);
        if (hostLevel === 0 && j >= keepN && BOUGHS.length) {
          var rri = outN++;
          var pOrig = trunkPtAt(atT);
          var pick = pickBough(pOrig);
          hUse = BOUGHS[pick.i];
          lvUse = 1;
          lane = pick.load;   // 这是第几轮分到同一根枝 → 决定同枝溢出叶铺在哪一段
          pickDY = pick.dy;   // 就近度的实证读数（Q6c）：选中枝与叶原位的高度差
          /* 同轮 A/B：记下「v34 的轮询会选哪根枝」，用它当**同一次运行里的对照基线**。
           * 固定阈值（「平均 ≤0.15」之类）没有意义 —— 叶原位最高到 0.99、一级枝最高才挂到 0.55，
           * 高处的叶不管怎么选都有一大截高度差。只有「就近 vs 轮询」在同一次运行里的比值才是证据。 */
          var rrq = boughRoot[rri % BOUGHS.length];
          rrDY = Math.abs(pOrig[1] - rrq[1]);
        }
        var at2, az2;
        if (lvUse === 0) {
          // 主干：叶铺在该主线段自己的区间里；方位角与螺旋外推量改用全主干全局序号 kTrunk，
          // 这样换手的分段之间不会再出现方位角断层（同一角度上两片叶重叠）。
          at2 = atT;
          az2 = (kTrunk * GOLD) % TAU2;
        } else if (hUse !== host) {
          // 溢出叶：lane = 这是第几轮分到同一根枝。每轮换一段铺开区间，同枝的溢出叶才不会叠成一点。
          at2 = clamp(0.26 + 0.62 * ((lane % 5) / 4), 0.10, 0.94);
          az2 = (num(hUse.az, 0) + tIdx * GOLD) % TAU2;
        } else {
          // 支线叶铺满整根枝（0.30 → 0.92），不再挤在中上段
          at2 = cs.length === 1 ? 0.62 : 0.30 + 0.62 * (tIdx / dnm);
          az2 = (num(hUse.az, 0) + tIdx * GOLD) % TAU2;
        }
        // 主干叶按全局序号向外螺旋展开（0.10 → 0.36），整条主干拧成螺旋星带而非竖柱；
        // 「比例」用 kTrunk 在全主干叶总数里的占比，跨段连续、确定性。枝上叶保持贴枝（spread=0）。
        var spread = lvUse === 0 ? (0.10 + 0.26 * (kTrunk / Math.max(1, trunkLeafTotal))) : 0;
        var lp = leafPos(hUse, at2, az2, spread);
        if (lvUse === 0) { onTrunk++; kTrunk++; } else if (hUse !== host) { spilled++; if (pickDY >= 0) { spillSum += pickDY; spillCnt++; rrSum += rrDY; } }
        raw.push({ key: tid2 + '|' + nm, name: nm, threadId: tid2, host: str(hUse.id) || 'trunk',
          hostLevel: lvUse, at: at2, az: az2, pos: lp.pos, pickDY: pickDY, rrDY: rrDY,
          n: num(c.n, 1), w: clamp(num(c.w, 0), 0, 1), lead: str(th.lead) === nm,
          main: !!mainIds[tid2] || num(th.depth, 1) === 0, dup: false, dupIdx: 0, dupOf: 0,
          entry: num(c.entry, -1), exit: num(c.exit, -1), camp: str(c.camp),
          color: num(th.color, 0xffb45c), spilled: lvUse === 1 && hUse !== host });
      }
    }

    // ── 规模保护：先给每个角色保底一片，再按权重补满配额。
    // 不保底的话，三国 507 角色会有大批人整个消失 —— 那就不是「按剧情分布」而是「只剩主角」。
    if (raw.length > maxLeaves) {
      var seen = {}, keep = [], rest = [];
      var byW = raw.slice();
      byW.sort(function (a, b) { return num(b.w, 0) - num(a.w, 0) || (a.key < b.key ? -1 : 1); });
      for (i = 0; i < byW.length; i++) {
        if (!seen[byW[i].name]) { seen[byW[i].name] = 1; keep.push(byW[i]); }
        else rest.push(byW[i]);
      }
      var room = Math.max(0, maxLeaves - keep.length);
      warn.push('叶位截断：' + raw.length + ' → ' + Math.min(maxLeaves, keep.length + room) + '（每角色保底 1 片）');
      raw = keep.concat(rest.slice(0, room));
    }

    // ── 稳定全序：线序 → 权重降序 → key 字符序（相等时不许依赖引擎的排序稳定性）
    raw.sort(function (a, b) {
      if (a.threadId !== b.threadId) return a.threadId < b.threadId ? -1 : 1;
      var d = num(b.w, 0) - num(a.w, 0);
      if (d) return d;
      return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0);
    });
    for (i = 0; i < raw.length; i++) raw[i].i = i;

    // ── 重复出场：按权重降序，dupIdx 0 = 本体，其余是分身，每片都指回本体
    var byName = {}, byThread = {};
    for (i = 0; i < raw.length; i++) {
      var L = raw[i];
      (byName[L.name] = byName[L.name] || []).push(i);
      (byThread[L.threadId] = byThread[L.threadId] || []).push(i);
    }
    var names = 0, dupNames = 0, maxPer = 0, nm2;
    for (nm2 in byName) {
      if (!byName.hasOwnProperty(nm2)) continue;
      var arr = byName[nm2];
      arr.sort(function (a, b) { return num(raw[b].w, 0) - num(raw[a].w, 0) || (raw[a].key < raw[b].key ? -1 : 1); });
      for (k = 0; k < arr.length; k++) {
        raw[arr[k]].dupIdx = k;
        raw[arr[k]].dupOf = arr[0];
        raw[arr[k]].dup = arr.length > 1;
      }
      names++; if (arr.length > 1) dupNames++;
      if (arr.length > maxPer) maxPer = arr.length;
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    // 就近分流的分布读数（Q6c）：平均水平距离 + 各一级枝收叶数的极差。
    // loadMax 远大于 loadMin 就说明「负载惩罚」没起作用（一根枝被塞爆）；
    // spillDist 过大则说明「就近」没起作用（叶被派到了远处的枝）。
    var loadMin = 999, loadMax = -1, loadUsed = 0;
    for (i = 0; i < boughLoad.length; i++) {
      if (boughLoad[i] < loadMin) loadMin = boughLoad[i];
      if (boughLoad[i] > loadMax) loadMax = boughLoad[i];
      if (boughLoad[i] > 0) loadUsed++;
    }
    if (!boughLoad.length) { loadMin = 0; loadMax = 0; }
    var out = { ok: true, reason: '', fp: str(shape.fp), leaves: raw, byName: byName, byThread: byThread,
      stats: { leaves: raw.length, names: names, dupNames: dupNames, maxPerName: maxPer,
        avgPerName: names ? Math.round(raw.length / names * 100) / 100 : 0,
        onTrunk: onTrunk, onBough: raw.length - onTrunk,
        spilled: spilled, spillDY: spillCnt ? Math.round(spillSum / spillCnt * 10000) / 10000 : -1,
        spillRr: spillCnt ? Math.round(rrSum / spillCnt * 10000) / 10000 : -1,
        spillN: spillCnt, loadMin: loadMin, loadMax: loadMax, loadUsed: loadUsed,
        boughN: boughLoad.length, ms: MS[key], fp: str(shape.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  /** ── v45 逻辑树严格落点（仅 shape.logical === true）─────────────────────
   *  ① 每个 (线, 角色) 只在**该线真实包含、且该角色真实参与**的事件锚点上落一片叶；
   *  ② 该线没有该角色的参与事件就不造叶（不编参与），更不 spill 到无关枝；
   *  ③ 权重只在来源给出时编码；来源仅给名单时 w=0，只表示参与，不编贡献分数。
   *  返回值与 legacy 完全同构：leaves/byName/byThread/stats 与叶的 consumer 字段都在。 */
  /** 本线 occurrence → 坐标。契约（主控 23:37）要求同名事件跨多线时，
   *  **角色本线叶先取本线 occurrence**，全局 anchor 只作无指定线的默认入口。
   *  兼容三种存法：B 现状 evPos[evIdx]={pos,at}；契约名 eventPositions[evIdx]；
   *  eventPositions 数组（与 path.events 对齐，元素可为 [x,y,z] / {pos,at} / 沿 pts 的 t）。 */
  function posOf(x, path) {
    if (!x) return null;
    if (x.pos && x.pos.length >= 3 && isFinite(x.pos[0]) && isFinite(x.pos[1]) && isFinite(x.pos[2])) {
      return [x.pos[0], x.pos[1], x.pos[2]];
    }
    if (x.length >= 3 && isFinite(x[0]) && isFinite(x[1]) && isFinite(x[2])) {
      return [x[0], x[1], x[2]];
    }
    var t = isFinite(x) ? x : (isFinite(x.at) ? x.at : null);
    if (t != null && path && path.pts && path.pts.length) {
      var u = clamp(t, 0, 1) * (path.pts.length - 1), a = Math.floor(u),
          b = Math.min(path.pts.length - 1, a + 1), f = u - a;
      return vadd(vmul(path.pts[a], 1 - f), vmul(path.pts[b], f));
    }
    return null;
  }

  function pathOccurrence(path, evIdx) {
    if (!path) return null;
    var ep = path.eventPositions;
    if (ep && !ep.length && ep[evIdx]) {   /* 对象映射：eventPositions 或 evPos */
      var q = posOf(ep[evIdx], path);
      if (q) return q;
    }
    var map = path.evPos;
    if (map && map[evIdx]) {
      var q2 = posOf(map[evIdx], path);
      if (q2) return q2;
    }
    if (ep && ep.length) {                  /* 数组：与 events 对齐 */
      var evs = path.events || [], i;
      for (i = 0; i < evs.length; i++) {
        if (Math.floor(num(evs[i], -1)) !== evIdx) continue;
        var q3 = posOf(ep[i], path);
        if (q3) return q3;
      }
    }
    return null;
  }

  function anchorAt(shape, evIdx, path) {
    var occ = pathOccurrence(path, evIdx);
    if (occ) {
      return { pos: occ, host: (path && str(path.host)) || 'trunk', at: -1 };
    }
    var ea = shape && shape.eventAnchors && shape.eventAnchors[evIdx];
    if (ea && ea.pos && ea.pos.length >= 3 &&
        isFinite(ea.pos[0]) && isFinite(ea.pos[1]) && isFinite(ea.pos[2])) {
      return { pos: [ea.pos[0], ea.pos[1], ea.pos[2]],
        host: str(ea.host) || (path && str(path.host)) || 'trunk', at: num(ea.at, -1) };
    }
    return null;
  }

  function assignLogical(shape, tree, opts) {
    var maxLeaves = num(opts.maxLeaves, 900);
    var key = 'L45|' + str(shape.fp) + '|' + str(tree.fp) + '|' + maxLeaves;
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], raw = [], i, j, q;
    var TP = shape.threadPaths || {}, TH = tree.threads || [], EV = tree.events || [];
    var evCast = {};
    function participates(evIdx, name) {
      var set = evCast[evIdx];
      if (!set) {
        set = evCast[evIdx] = {};
        var e = EV[evIdx], cs = (e && e.cast) || [];
        for (var z = 0; z < cs.length; z++) set[str(cs[z])] = 1;
      }
      return set[name] === 1;
    }

    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, tid = str(th.id), cast = th.cast || [];
      if (!cast.length) continue;
      var path = TP[tid];
      if (!path || !path.events || !path.events.length) {
        warn.push('线 ' + tid + ' 无 threadPaths，角色不落点（禁止 spill）');
        continue;
      }
      var isMain = (str(th.kind) === 'main' || num(th.depth, -1) === 0);
      for (j = 0; j < cast.length; j++) {
        var c = cast[j] || {}, nm = str(c.name);
        if (!nm) continue;
        var pickEv = -1, ap = null;
        for (q = 0; q < path.events.length; q++) {
          var evi = Math.floor(num(path.events[q], -1));
          if (evi < 0 || !participates(evi, nm)) continue;
          var cand = anchorAt(shape, evi, path);
          if (cand) { pickEv = evi; ap = cand; break; }
        }
        if (pickEv < 0 || !ap) {
          warn.push('角色 ' + nm + ' 在线 ' + tid + ' 无参与事件锚点，未落点');
          continue;
        }
        raw.push({
          key: tid + '|' + nm, name: nm, threadId: tid, host: str(ap.host) || 'trunk',
          hostLevel: isMain ? 0 : 1, at: num(ap.at, -1), az: 0, pos: ap.pos,
          pickDY: -1, rrDY: -1, n: num(c.n, 1),
          w: (typeof c.w === 'number' && isFinite(c.w)) ? clamp(c.w, 0, 1) : 0,
          lead: str(th.lead) === nm, main: isMain, dup: false, dupIdx: 0, dupOf: 0,
          entry: num(c.entry, -1), exit: num(c.exit, -1), camp: str(c.camp),
          color: num(th.color, 0xffb45c), spilled: false, evIdx: pickEv, logical: true
        });
      }
    }

    if (raw.length > maxLeaves) {
      var seen = {}, keep = [], rest = [];
      var byW = raw.slice();
      byW.sort(function (a, b) { return num(b.w, 0) - num(a.w, 0) || (a.key < b.key ? -1 : 1); });
      for (i = 0; i < byW.length; i++) {
        if (!seen[byW[i].name]) { seen[byW[i].name] = 1; keep.push(byW[i]); }
        else rest.push(byW[i]);
      }
      var room = Math.max(0, maxLeaves - keep.length);
      warn.push('叶位截断：' + raw.length + ' → ' + Math.min(maxLeaves, keep.length + room) + '（每角色保底 1 片）');
      raw = keep.concat(rest.slice(0, room));
    }

    raw.sort(function (a, b) {
      if (a.threadId !== b.threadId) return a.threadId < b.threadId ? -1 : 1;
      var d = num(b.w, 0) - num(a.w, 0);
      if (d) return d;
      return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0);
    });
    for (i = 0; i < raw.length; i++) raw[i].i = i;

    var byName = {}, byThread = {};
    for (i = 0; i < raw.length; i++) {
      var L = raw[i];
      (byName[L.name] = byName[L.name] || []).push(i);
      (byThread[L.threadId] = byThread[L.threadId] || []).push(i);
    }
    var names = 0, dupNames = 0, maxPer = 0, nm2, k;
    for (nm2 in byName) {
      if (!byName.hasOwnProperty(nm2)) continue;
      var arr = byName[nm2];
      arr.sort(function (a, b) { return num(raw[b].w, 0) - num(raw[a].w, 0) || (raw[a].key < raw[b].key ? -1 : 1); });
      for (k = 0; k < arr.length; k++) {
        raw[arr[k]].dupIdx = k;
        raw[arr[k]].dupOf = arr[0];
        raw[arr[k]].dup = arr.length > 1;
      }
      names++; if (arr.length > 1) dupNames++;
      if (arr.length > maxPer) maxPer = arr.length;
    }

    var onTrunk = 0, onBough = 0;
    for (i = 0; i < raw.length; i++) { if (num(raw[i].hostLevel, 1) === 0) onTrunk++; else onBough++; }
    var boughN = 0;
    for (k in TP) { if (TP.hasOwnProperty(k)) boughN++; }
    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var out = { ok: true, reason: '', fp: str(shape.fp), logical: true,
      leaves: raw, byName: byName, byThread: byThread,
      stats: { leaves: raw.length, names: names, dupNames: dupNames, maxPerName: maxPer,
        avgPerName: names ? Math.round(raw.length / names * 100) / 100 : 0,
        onTrunk: onTrunk, onBough: onBough,
        spilled: 0, spillDY: -1, spillRr: -1, spillN: 0, loadMin: 0, loadMax: 0, loadUsed: 0,
        boughN: boughN, ms: MS[key], fp: str(shape.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  /** 路径分发：logical 严格落点；其余一律保留 legacy（含就近 spill）行为。 */
  function assign(shape, tree, opts) {
    opts = opts || {};
    if (!shape || shape.ok !== true) return empty('no-shape');
    if (!tree || tree.ok !== true) return empty('no-tree');
    if (shape.logical === true) return assignLogical(shape, tree, opts);
    return assignLegacy(shape, tree, opts);
  }

  var API = {
    assign: assign,
    get: function () { return CACHE; },
    ofName: function (name) { return (CACHE && CACHE.byName[str(name)]) ? CACHE.byName[str(name)].slice() : []; },
    stats: function () { return CACHE ? CACHE.stats : { leaves: 0, ready: false }; }
  };
  window.CLTreeLeaf = API;
})();
