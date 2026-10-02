/* Castline · tree-focus.js — 事件类型聚焦层（window.CLTreeFocus，v37）
 *
 * 职责：选中某一类事件 → 该类所有细枝「发光」（类别色 + 呼吸脉动）。
 * 键盘入口与图例联动由同事 C2 负责（keys.js / tree-legend.js），本层只做渲染与 stats。
 *
 * 家族红线（与 ghost / veil / clones 一致，验收 Q12「树层 Raycaster 命中必须为 0」直接依赖）：
 *   · mesh.raycast = noop；userData.clPickable=false；clLayer='tree-focus'；clTree=true
 *   · renderOrder = -49（ghost 是 -50，本层在它上一层）；加性混合 + depthWrite:false + fog:false + transparent
 *   · 不写 GLSL（仓里出过着色器编译失败 → 整屏纯黑而 jserr 仍为 none 的事故）
 *   · 全程 ES5 + IIFE + 'use strict'；禁 Math.random（确定性铁律）
 *
 * 数据源：CLTreeGhost.shapeOf().twigs（{ pts, kind, r, host, ..., evIdx }）。只高亮 kind == 选中 的枝。
 *
 * v39：新增 solo(evIdx) —— 从「类」下沉到「单个事件」，只点亮那一个事件自己的 twig、其余全灭。
 * 与 set(kind) 互斥；两者共用同一套挤出/环数/站距/摇曳（extrudeTwig / ringN / stationStep / applySway）。
 */
(function () {
  'use strict';

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  var T = null, O = null, host = null, ownRoot = null;
  var ready = false, muted = false, vis = true;
  /* v39：state 从「一个 kind」扩成「模式 + 载荷」。
   * mode: '' 清除 / 'kind' 按类（原行为）/ 'solo' 单个事件（新增，树可逐条读取）。
   * 两者互斥：进 kind 清 evIdx，进 solo 清 kind —— 唯一真相只在这一处，外部读 get()。 */
  var state = { kind: '', mode: '', evIdx: -1 };
  var meshes = {}, basePos = {}, seenRev = {};
  var verts = 0, retry = 0, tAcc = 0;
  var CAP = 800;                     // 单次高亮枝数硬上限（超出取前 800 根）
  var GOLDEN = 0.618;                // 错相用的黄金比常数（禁 Math.random 的确定性相位）
  /* v39 聚焦时的主树压暗系数。0.38 的由来：实拍差分里「只叠加不压暗」只有 2.59% 差异像素；
   * 0.38 ≈ 主树亮度降到 38%，让高亮管与底树拉开约 2.6:1 的亮度比 —— 一眼能看出「其余全灭」，
   * 又不至于把整棵树压成黑（树还在，只是退到背景）。同族面板的暗化惯例是 rgba(*,.38~.42)，
   * 取 0.38 与它们同档。退出聚焦精确还原 1.0。 */
  var FOCUS_DIM = 0.38;
  /* ---- v42 增亮三件套：把「压暗别人」换成「抬高自己」 ----
   * v39 审计的结论：FOCUS_DIM 这条杠杆太短 —— 同进程实测只有 2.59% 差异像素，
   * 「一眼看出进入聚焦」不成立。压暗是**减法**，减到 0 也就把主树整块变成黑，
   * 天花板锁死在「主树消失」；而增亮是**加法**，在 AdditiveBlending 下亮度可以
   * 一直加上去（叠到过曝为止），所以杠杆长度不再由底树亮度决定。
   * 三个乘子都作用在**被聚焦的枝管本身**，互不打扰：
   *   · 半径 ×1.5 —— 面积涨 2.25 倍，是三项里最狠的一项（细管变粗一眼可见）；
   *   · 颜色 ×1.35 —— 加性混合下即像素亮度 ×1.35，且不会像 alpha 那样被底树吃掉；
   *   · opacity 0.9+0.3·beat —— 呼吸仍保留，但**底值抬高**，最低也比 v39 的全盛期更亮。 */
  var FOCUS_BOOST_R = 1.5;    // 管半径乘子
  var FOCUS_BOOST_C = 1.35;   // 颜色乘子（加性混合下 = 亮度乘子）
  var FOCUS_OP_BASE = 0.90;   // 呼吸底值（v39 是 0.75）
  var FOCUS_OP_SWING = 0.30;  // 呼吸摆幅（v39 是 0.25）→ 峰值 1.20（会被钳到 1.0，是故意的：峰值段更常处于满亮）
  var TWO_PI = Math.PI * 2;

  /* ---- 几何工具（与 ghost 同一套，保证与骨架/虚影同形） ---- */
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vnorm(a) {
    var L = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0];
  }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  function shapeNow() {
    var g = window.CLTreeGhost;
    return (g && g.shapeOf) ? tryFn(g.shapeOf) : null;
  }

  /** 挂载点：与 ghost 完全一致 —— 优先共享定标器，拿不到退到 o.group 自建。 */
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

  /* ---- v36 摇曳：逐顶点重写（与 ghost 同一机制）----
   * basePos 存建造时的单位空间原位；每帧从它重投，不在上一帧结果上叠（避免漂移）。
   * seenRev 记本层已按哪个姿态版本号写过：姿态没变就一次上传都不产生 —— 静止档开销为 0。 */
  var swScratch = [0, 0, 0];
  function applySway() {
    var SW = window.CLTreeSway;
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
      for (i = 0; i < n; i += 3) {
        SW.bendInto(bp[i], bp[i + 1], bp[i + 2], swScratch);
        a[i] = swScratch[0]; a[i + 1] = swScratch[1]; a[i + 2] = swScratch[2];
      }
      attr.needsUpdate = true;
      seenRev[k] = r;
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

  /* 单枝环挤出：沿 pts 每站一圈 N 个顶点，相邻两圈连成三角带。
   * 颜色从 CLPalette 取（不许自己写色值）；呼吸脉动靠材质 opacity（见 update），不烘进顶点，
   * 这样「逐字节确定性」只由几何位置决定，不受动效干扰。 */
  function extrudeTwig(tw, N, step, col, acc) {
    var pts = tw.pts, rr = tw.r;
    if (!pts || pts.length < 2) return;
    var idx = [], i, k;
    for (i = 0; i < pts.length; i += step) idx.push(i);
    if (idx[idx.length - 1] !== pts.length - 1) idx.push(pts.length - 1);
    var nst = idx.length;
    if (nst < 2) return;
    var base = acc.p.length / 3;
    for (k = 0; k < nst; k++) {
      var si = idx[k], p = pts[si];
      var rad = Math.max(num(rr[si], 0.006), 0.004) * FOCUS_BOOST_R;
      var a = pts[Math.max(0, si - 1)], b = pts[Math.min(pts.length - 1, si + 1)];
      var tan = vnorm(vsub(b, a));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      var q;
      for (q = 0; q < N; q++) {
        var th = q / N * TWO_PI, cth = Math.cos(th), sth = Math.sin(th);
        acc.p.push(p[0] + (U[0] * cth + W[0] * sth) * rad,
                   p[1] + (U[1] * cth + W[1] * sth) * rad,
                   p[2] + (U[2] * cth + W[2] * sth) * rad);
        /* v42：颜色乘子 = 亮度增益。钳到 1 是必须的 —— 顶点色是 0..1 的归一化量，
         * 溢出在部分驱动上会被截断成白斑而不是「更亮」。加性混合下 1.0 已经是很强的信号。 */
        acc.c.push(col.r * FOCUS_BOOST_C > 1 ? 1 : col.r * FOCUS_BOOST_C,
                   col.g * FOCUS_BOOST_C > 1 ? 1 : col.g * FOCUS_BOOST_C,
                   col.b * FOCUS_BOOST_C > 1 ? 1 : col.b * FOCUS_BOOST_C);
      }
    }
    for (k = 0; k < nst - 1; k++) {
      var r0 = base + k * N, r1 = base + (k + 1) * N, q;
      for (q = 0; q < N; q++) {
        var q2 = (q + 1) % N;
        acc.i.push(r0 + q, r1 + q, r0 + q2, r0 + q2, r1 + q, r1 + q2);
      }
    }

    // T4 · 事件星云花簇 (Nebula Flower Clusters): 细枝末端 7 瓣微型星云花簇
    if (tw.isEventMarker || tw.evIdx != null) {
      var tipP = pts[pts.length - 1];
      var tipRad = Math.max(num(rr[pts.length - 1], 0.006), 0.004) * FOCUS_BOOST_R;
      var flowerPetals = 7;
      var petalBase = acc.p.length / 3;
      var tanEnd = vnorm(vsub(pts[pts.length - 1], pts[Math.max(0, pts.length - 2)]));
      var upEnd = Math.abs(vdot(tanEnd, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var Ue = vnorm(vcross(tanEnd, upEnd)), We = vnorm(vcross(tanEnd, Ue));
      for (var fp = 0; fp < flowerPetals; fp++) {
        var fa = fp / flowerPetals * TWO_PI;
        var fScale = 1.0 + 0.45 * Math.sin(fa * 3.0);
        var fR = tipRad * 2.2 * fScale;
        acc.p.push(tipP[0] + (Ue[0] * Math.cos(fa) + We[0] * Math.sin(fa)) * fR + tanEnd[0] * (tipRad * 0.8),
                   tipP[1] + (Ue[1] * Math.cos(fa) + We[1] * Math.sin(fa)) * fR + tanEnd[1] * (tipRad * 0.8),
                   tipP[2] + (Ue[2] * Math.cos(fa) + We[2] * Math.sin(fa)) * fR + tanEnd[2] * (tipRad * 0.8));
        acc.c.push(col.r * 0.9, col.g * 0.9, col.b * 0.9);
      }
      var tipCenter = acc.p.length / 3;
      acc.p.push(tipP[0] + tanEnd[0] * (tipRad * 1.5),
                 tipP[1] + tanEnd[1] * (tipRad * 1.5),
                 tipP[2] + tanEnd[2] * (tipRad * 1.5));
      acc.c.push(1.0, 0.98, 0.92);
      for (var tfi = 0; tfi < flowerPetals; tfi++) {
        acc.i.push(tipCenter, petalBase + tfi, petalBase + ((tfi + 1) % flowerPetals));
      }
    }
  }

  /* 低档位策略（CLTreeQuality.of('sway') === 0 ⇒ low 档）：
   * 用户主动请求的反馈不该被画质关掉 —— 所以仍显示；但顶点预算要小：
   * 圈数 5→3、站间隔 1→2，几何规模直降约 5× 倍，把"主动反馈"的代价压到最低。 */
  function ringN() {
    var Q = window.CLTreeQuality;
    if (Q && Q.of && tryFn(function () { return Q.of('sway'); }) === 0) return 3;
    return 5;
  }
  function stationStep() {
    var Q = window.CLTreeQuality;
    if (Q && Q.of && tryFn(function () { return Q.of('sway'); }) === 0) return 2;
    return 1;
  }

  function rebuild() {
    if (!T || !O) return false;
    if (!mount()) return false;
    var s = shapeNow();
    if (!s) return false;       // 数据可能比首帧晚到：update 里每 30 帧重试
    var twigs = s.twigs || [];
    var mode = state.mode;
    if (!mode) { clearGeom(); return true; }   // 清除态：不建几何
    var N = ringN(), step = stationStep();
    clearGeom();
    var picked = [], i, cap = (mode === 'solo') ? 1 : CAP;
    if (mode === 'solo') {
      /* solo：只点亮 evIdx 命中的那一根 twig（事件 ↔ 枝一一映射，见 tree-shape.js:426）。
       * 不属于任何事件的枝（理论上没有）不参与，匹配不到就空几何归零。 */
      for (i = 0; i < twigs.length && picked.length < cap; i++) {
        if (twigs[i] && Math.floor(num(twigs[i].evIdx, -1)) === state.evIdx) picked.push(twigs[i]);
      }
    } else {
      var kind = state.kind;
      for (i = 0; i < twigs.length && picked.length < cap; i++) {
        if (twigs[i] && String(twigs[i].kind) === kind) picked.push(twigs[i]);
      }
    }
    if (!picked.length) return true;           // 未命中（solo 越界 / 空类）：不建几何 = 全灭
    /* 颜色仍从 CLPalette 取唯一真相：kind 模式 = 该类色；solo 模式 = 该事件自己的 kind 类色。 */
    var hex = (window.CLPalette && CLPalette.hex) ? CLPalette.hex(picked[0].kind) : 0xffb45c;
    var col = new T.Color(hex >>> 0);
    for (i = 0; i < picked.length; i++) {
      var acc = { p: [], c: [], i: [] };
      extrudeTwig(picked[i], N, step, col, acc);
      if (!acc.p.length) continue;
      var id = 'tw' + i;
      basePos[id] = new Float32Array(acc.p);   // 摇曳基准 = 建造时单位空间原位
      seenRev[id] = -1;                         // 首帧必须写一遍，避免旧姿态闪一帧
      var g = new T.BufferGeometry();
      g.setAttribute('position', new T.Float32BufferAttribute(acc.p, 3));
      g.setAttribute('color', new T.Float32BufferAttribute(acc.c, 3));
      g.setIndex(acc.i);
      var mat = new T.MeshBasicMaterial({ vertexColors: true, color: 0xffffff, transparent: true,
        opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide, fog: false });
      var mesh = new T.Mesh(g, mat);
      mesh.frustumCulled = false;
      mesh.renderOrder = -49;                   // 在 ghost(-50) 上一层
      mesh.raycast = function () {};             // 树层不可点击：鼠标必须穿过去（Q12）
      mesh.userData.clPickable = false;
      mesh.userData.clLayer = 'tree-focus';
      mesh.userData.clTree = true;               // 树层显式标记，验收侧只认它
      host.add(mesh);
      meshes[id] = mesh;
      verts += acc.p.length / 3;
    }
    return true;
  }

  function stageActive() {
    var S = window.CLTreeStage;
    if (!S || !S.stats) return false;
    var ss = tryFn(S.stats);
    return !!(ss && ss.active);
  }

  /* 第四道门「有选中」：kind 模式看 kind，solo 模式看 evIdx>=0。
   * 明确写成函数而不是散在 update 里，是为了让「模式」这件事只有一个判断点。 */
  function hasSel() {
    if (state.mode === 'kind') return !!state.kind;
    if (state.mode === 'solo') return state.evIdx >= 0;
    return false;
  }

  /* v39 压暗主树：仅叠加高亮管、不压暗底树时用户几乎看不出聚焦（同机位像素差分只 2.59%）。
   * 由本层每帧把 CLTreeGhost.setDim() 写到唯一真相的位置：
   *   四道门全开 → FOCUS_DIM；其它任何情况 → 1.0。
   * 幂等（同值重复写无副作用）；CLTreeGhost 缺席 / 无 setDim（老加载顺序）→ 静默 no-op。 */
  function driveDim(active) {
    var G = window.CLTreeGhost;
    if (!G || !G.setDim) return;
    /* v41 forge：非聚焦时的基准压暗不再恒为 1，改由 CLTreePose.baseDim() 提供（星座态虚影 / 剧情线态全亮）；
     * CLTreePose 缺席时回到 1，与旧行为逐字一致。 */
    var base = 1;
    try { if (window.CLTreePose && CLTreePose.baseDim) { var b = +CLTreePose.baseDim(); if (isFinite(b) && b > 0 && b <= 1) base = b; } } catch (e0) {}
    tryFn(function () { return G.setDim(active ? Math.min(FOCUS_DIM, base) : base); });
  }

  function update(s) {
    s = s || {};
    tAcc = num(s.t, tAcc + 0.016);
    /* v42：静止档（scene.setCalm(true)）时聚焦呼吸停住 —— 与 ghost 的 calmK 同一纪律。
     * 聚焦层的呼吸是 opacity 动画，像素门禁里它就是噪声地板的一部分。 */
    var calmK = !!s.calm;
    /* 舞台门：剧情线没在显示（CLTreeStage.stats().active 为 false）时整层隐藏。
     * 聚焦层是"显示剧情线"那一刻的辅助反馈，舞台一关就得让位，否则它会盖在星座前。 */
    var on = num(s.on, 1);
    var show = vis && !muted && on > 0 && stageActive() && hasSel();
    /* v39：无论走哪条返回路径都要先把压暗系数写对（幂等）——
     * 四道门全开才压暗主树，其它一切情况精确还原 1.0。树没画出来时也照样还原，
     * 免得「聚焦 → 舞台关 → 再开」之后残留一个压暗态的树。 */
    driveDim(show);
    if (!ready) {
      if (++retry % 30 === 0) { if (rebuild()) ready = true; }
      return;
    }
    if (!show) {
      var k;
      for (k in meshes) {
        if (meshes.hasOwnProperty(k) && meshes[k]) { meshes[k].visible = false; meshes[k].material.opacity = 0; }
      }
      return;
    }
    var i = 0;
    for (var id in meshes) {
      if (!meshes.hasOwnProperty(id) || !meshes[id]) continue;
      var m = meshes[id];
      var phase = (i * GOLDEN) % 1 * TWO_PI;     // 禁 Math.random：相位按枝序号错开（确定性）
      var beat = calmK ? 0.75 : 0.5 + 0.5 * Math.sin(tAcc * 0.30 + phase);
      m.material.opacity = FOCUS_OP_BASE + FOCUS_OP_SWING * beat;   // 呼吸脉动 v42：0.90~1.20（钳到 1.0 满亮）
      m.visible = true;
      i++;
    }
    applySway();
  }

  /* v37 审计修（P1-1）：白名单校验。
   * 原实现把任意字符串照单全收 —— set('不存在的类') / set(123) 会返回该值并进入重建（匹配 0 根 → 空几何），
   * 于是 get().kind 报出一个树上根本不存在的事件类，图例（C2）会高亮一行「什么都没有」的类。
   * 现在：不在 CLPalette.KINDS 白名单内 → 一律归零（等价 set(null)），返回 ''。
   * 白名单缺席（CLPalette 未载入）时保守放行原值 —— 宁可不校验，也不许把有效类误杀成空。 */
  function validKind(kind) {
    if (!kind) return '';
    var P = window.CLPalette;
    var K = (P && P.KINDS) ? P.KINDS : null;
    if (!K || !K.length) return String(kind);
    var i;
    for (i = 0; i < K.length; i++) { if (String(K[i]) === String(kind)) return String(kind); }
    return '';
  }

  function setState(kind) {
    var k = validKind((kind == null) ? '' : kind);
    var want = k ? 'kind' : '';
    /* 与 solo 互斥：set 一律清掉 solo 态（evIdx 归 -1）。
     * 判「变了没」必须连 mode 一起比 —— 否则 solo 态下 set('') 时 k 与旧 kind 同为 '' 会跳过重建，
     * 单事件那根管子会赖在树上不走。 */
    if (k !== state.kind || want !== state.mode) {
      state.kind = k;
      state.mode = want;
      state.evIdx = -1;
      if (ready) rebuild();
    }
    return state.kind;
  }

  /* v39 solo(evIdx)：只点亮第 evIdx 个事件自己那根 twig。
   * 取值域 = 树上 twig 的 evIdx 集合（tree-shape 已挂，事件 ↔ 枝一一映射）。
   * solo(-1) / 非数 / 负 / 树上没有的 evIdx → 一律归零。
   * 骨架尚未就绪时**乐观接受**（拿不到 twigs 无从校验），交给后续 rebuild 兑现/归零 ——
   * 若这里直接判非法，加载窗口内的 pick() 会被静默吞掉。 */
  function validEv(evIdx) {
    var v = +evIdx;
    if (!isFinite(v)) return -1;
    v = Math.floor(v);
    if (v < 0) return -1;
    var s = shapeNow();
    var tw = (s && s.twigs) || [];
    if (!tw.length) return v;
    var i;
    for (i = 0; i < tw.length; i++) {
      if (tw[i] && Math.floor(num(tw[i].evIdx, -1)) === v) return v;
    }
    return -1;
  }

  function soloState(evIdx) {
    var v = validEv(evIdx);
    var want = (v >= 0) ? 'solo' : '';
    if (want !== state.mode || v !== state.evIdx || state.kind) {
      state.mode = want;
      state.evIdx = v;
      state.kind = '';                 // 与 set(kind) 互斥：solo 一律清掉类聚焦
      if (ready) rebuild();
    }
    return state.evIdx;
  }

  function getState() {
    var n = 0, k;
    for (k in meshes) if (meshes.hasOwnProperty(k) && meshes[k]) n++;
    /* v37 审计修（P1-2）：把 ready 一并报出 —— ready=false 时 kind 已记下但几何还没建，
     * 调用方（图例 / 验收）据此知道自己读到的 n 尚不可信，不必去猜。
     * v39：加 evIdx（solo 态下 = 该事件下标；未 solo 时 -1），kind 在 solo 态下为空串。 */
    return { kind: state.kind, evIdx: (state.mode === 'solo') ? state.evIdx : -1, n: n, ready: ready };
  }

  function stats() {
    var k, dc = 0, n = 0;
    for (k in meshes) {
      if (!meshes.hasOwnProperty(k) || !meshes[k]) continue;
      n++;
      if (meshes[k].visible) dc++;
    }
    return { ready: ready, kind: state.kind, evIdx: (state.mode === 'solo') ? state.evIdx : -1,
      n: n, tubes: n, verts: verts, drawcalls: dc };
  }

  var API = {
    name: 'tree-focus',
    build: function (o) {
      if (!o || !o.T || !o.group) return null;
      T = o.T; O = o;
      clearGeom(); retry = 0; ready = false; muted = false; vis = true;
      if (rebuild()) ready = true;
      return stats();
    },
    update: update,
    set: setState,
    solo: soloState,
    get: getState,
    stats: stats,
    dispose: function () {
      clearGeom();
      if (ownRoot && ownRoot.parent) ownRoot.parent.remove(ownRoot);
      ownRoot = null; host = null; ready = false; state.kind = ''; state.mode = ''; state.evIdx = -1;
    },
    setOn: function (v) { muted = !v; return stats(); },
    show: function (v) { vis = (v == null) ? true : !!v; return stats(); },
    /* 验收辅助：返回第一根高亮枝几何中「y 最高」的当前顶点（已含摇曳）。
     * 顶点缓冲是 IIFE 内部量，验收侧只能经此取样；同一 kind → 同一根 twig → 同一顶点布局，确定性可比。 */
    sample: function () {
      var id;
      for (id in meshes) { if (meshes.hasOwnProperty(id) && meshes[id]) break; }
      if (!id || !meshes[id]) return null;
      var attr = meshes[id].geometry && meshes[id].geometry.attributes && meshes[id].geometry.attributes.position;
      if (!attr) return null;
      var a = attr.array, n = a.length, bi = -1, by = -1e9, i;
      for (i = 0; i < n; i += 3) { if (a[i + 1] > by) { by = a[i + 1]; bi = i; } }
      return { id: id, hi: [a[bi], a[bi + 1], a[bi + 2]], y: by, n: n / 3 };
    }
  };

  window.CLTreeFocus = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
