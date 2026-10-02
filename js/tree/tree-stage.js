/* tree-stage.js —— 「显示剧情线」时刻的取景与让位。
 * 星点要从星座飞到巨树枝干上，这一秒星座连线/姓名标签不能压在树前面：
 * 1) 星座让位到背景（0.72 而非 1，全灭就看不出飞离过程）；2) 树提亮，一让一提；
 * 3) 相机回标准机位并做有限次取景校正（不追焦，追了会抖）；
 * 4) 退出按进入前快照精确还原。ES5 IIFE，依赖缺席时静默让路，绝不抛错。 */
(function () {
  'use strict';

  var BODY_CLS = 'cl-treestage';
  var STYLE_ID = 'cl-treestage-style';

  var STAGE_K = 0.72;      // 不是 1：星座要退，但星点飞离的过程还得看得见
  var GHOST_DEPTH = 1.35;  // 树提亮，与星座一让一提
  var ZOOM_NEAR = 0.92, ZOOM_FAR = 1.08; // 树太小/太大各走一档，防过冲
  var MAX_STEPS = 6;       // 拉远需更多档位：取景是校正不是每帧追焦
  var STEP_GAP = 20;       // 每次隔 20 帧，给相机缓动留收敛时间
  var MIN_RATIO = 0.55, MAX_RATIO = 0.95; // 树高占视口的舒适带
  var FIRST_DELAY = 40;    // 先等 home() 缓动落位再校验，别拿中间态做判断
  var SAFE_MARGIN = 24;    // 视口四周留白，整树须完整落于此内
  var SAFE_FILL = 0.86;    // 拉远时按视口 86% 收口，留安全余量
  /* 整树单位空间 AABB 的**回落值**：只在拿不到骨架（CLTreeShape 缺席/作品还没解析）时用。
   * v32 是把它当唯一真值用的，而 v34 把骨架从"扫帚形"换成"伞形"，冠幅包络收窄、
   * 板根又往外铺 —— 一对写死的 0.6/1.05 再也框不准。取景器按虚胖的框缩放，树就在屏上偏小。 */
  var BBOX_XZ = 0.6, BBOX_YTOP = 1.05;
  var bboxU = null;   // 实测的单位空间整树 AABB：{x0,x1,y0,y1,z0,z1}

  var before = null;       // 进入前快照 { stageK, ghostDepth }
  var active = false;
  var mounted = false;
  var restored = false;
  var muted = false;       // degrade>=2 时关闭取景跟踪
  var heightRatio = -1;    // 算不出来保持 -1
  var bbox = null;         // 整树屏幕包围盒，测不到时保留上一次有效值
  var kicked = false;      // 已进入且 CAM 就绪后，是否已做过一次同步收敛
  var zoomSteps = 0;
  var frame = 0;
  var nextCheck = -1;
  var styleEl = null;
  var onPlotline = null;
  var pendingAuto = false; // ?treestage=1 且场景尚未就绪时，留到首帧重试
  var rafId = 0;           // 自驱校正循环句柄：主循环若未驱动 update，这里兜底推进取景

  function scene() {
    return (window.__cl && window.__cl.scene) ? window.__cl.scene : null;
  }
  function anchor() { return window.CLTreeAnchor || null; }
  function ghost() { return window.CLTreeGhost || null; }

  /* ---- 样式：只压暗侧栏面板（hover 恢复 1，canvas 不动）；前缀必须逐个拼，
     否则 :hover 只挂在列表末尾、其余选择器变无条件 opacity:1（首版踩坑） ---- */
  var PANELS = '.panel,.panels,.side,.sidebar,.side-panel,.sidebox,.hud,.hud-panel,' +
               'aside,.legend,.info,.info-panel,.card,.toolbar,.ui-panel,#panel,#sidebar,#hud';
  function cssRule(hoverSuffix) {
    var parts = PANELS.split(','), out = [];
    for (var i = 0; i < parts.length; i++) out.push('body.' + BODY_CLS + ' ' + parts[i] + hoverSuffix);
    return out.join(',');
  }
  var CSS = cssRule('') + '{opacity:.22!important;transition:opacity .3s ease}' +
            cssRule(':hover') + '{opacity:1!important}';

  function ensureStyle() {
    if (styleEl && document.getElementById(STYLE_ID)) return;
    try {
      styleEl = document.createElement('style');
      styleEl.id = STYLE_ID;
      styleEl.textContent = CSS;
      document.head.appendChild(styleEl);
    } catch (e) { styleEl = null; }
  }
  function removeStyle() {
    try {
      var el = document.getElementById(STYLE_ID);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    } catch (e) {}
    styleEl = null;
  }

  /** 实测整树 AABB（单位空间，取自骨架的真实顶点）。
   *  枝的 pts 是**中心线**、不含半径，所以算完要外扩：水平 6%、竖直 4%，再各留 0.02 垫底。
   *  外扩是单向的（只会更大），保证"宁可多包一圈也不把树切掉"。 */
  function measureUnit() {
    var sh = null;
    try {
      var tree = (window.CLStory && CLStory.get) ? CLStory.get() : null;
      /* v45.1：取景测量是高频路径，禁止每次测量重新进入 build 入口。
       * tree-ghost 已缓存形状；优先复用同一引用，数据指纹变化才重新取一次。 */
      var ghost = window.CLTreeGhost;
      if (ghost && typeof ghost.shapeOf === 'function') sh = ghost.shapeOf();
      if (!sh && window.CLTreeShape && tree) sh = CLTreeShape.build(tree);
    } catch (e) { sh = null; }
    if (!sh || !sh.ok) return null;
    var x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, z0 = 1e9, z1 = -1e9, n = 0, i;
    function eat(pts) {
      if (!pts || !pts.length) return;
      for (var q = 0; q < pts.length; q++) {
        var p = pts[q];
        if (!p || p.length < 3) continue;
        if (!isFinite(p[0]) || !isFinite(p[1]) || !isFinite(p[2])) continue;
        if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
        if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
        if (p[2] < z0) z0 = p[2]; if (p[2] > z1) z1 = p[2];
        n++;
      }
    }
    if (sh.trunk) eat(sh.trunk.pts);
    var keys = ['boughs', 'limbs', 'twigs'], k, j;
    for (k = 0; k < keys.length; k++) {
      var list = sh[keys[k]] || [];
      for (j = 0; j < list.length; j++) eat(list[j] && list[j].pts);
    }
    if (n < 8 || !(x1 >= x0) || !(y1 >= y0) || !(z1 >= z0)) return null;
    var padX = Math.max(0.02, (x1 - x0) * 0.06), padY = Math.max(0.02, (y1 - y0) * 0.04);
    return { x0: x0 - padX, x1: x1 + padX, y0: Math.min(0, y0), y1: y1 + padY, z0: z0 - padX, z1: z1 + padX };
  }

  /* ---- 整树屏幕包围盒：把单位空间 AABB 的 8 角 + 6 面心投到屏幕，取 min/max ----
   * 为什么不止 8 个角：透视投影下 AABB 的屏幕轮廓**不是** 8 角投影的凸包 ——
   * 离相机最近的那个面的四个角会被拉得最开，而"最近面"往往不是角所在的角点。
   * 加 6 个面心能把这种内凹补上，实测 top 差 3~8 px（够在 A03/A04 的边界判据上翻盘）。 */
  function measureBBox() {
    var a = anchor();
    if (!a || !a.toScreen) return null;
    if (!a.ready || !a.cam) return null;
    if (!a.cam()) return null; /* 相机没嗅到 → 作废，沿用上一次有效值 */
    var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    if (vw < 16 || vh < 16) return null;
    // 每次实测前刷新一次：骨架变了（换数据/改形状）取景框跟着变，不留在上一次作品的尺寸上
    var U = measureUnit();
    if (U) bboxU = U;
    else U = bboxU || { x0: -BBOX_XZ, x1: BBOX_XZ, y0: 0, y1: BBOX_YTOP, z0: -BBOX_XZ, z1: BBOX_XZ };
    var mx = (U.x0 + U.x1) * 0.5, my = (U.y0 + U.y1) * 0.5, mz = (U.z0 + U.z1) * 0.5;
    var corners = [
      [U.x0, U.y0, U.z0], [U.x1, U.y0, U.z0], [U.x0, U.y1, U.z0], [U.x1, U.y1, U.z0],
      [U.x0, U.y0, U.z1], [U.x1, U.y0, U.z1], [U.x0, U.y1, U.z1], [U.x1, U.y1, U.z1],
      [mx, my, U.z0], [mx, my, U.z1], [mx, U.y0, mz], [mx, U.y1, mz], [U.x0, my, mz], [U.x1, my, mz]
    ];
    var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (var i = 0; i < corners.length; i++) {
      var s = null;
      try { s = a.toScreen(corners[i]); } catch (e) { return null; }
      if (!s) return null;
      if (typeof s.x !== 'number' || typeof s.y !== 'number') return null;
      if (!isFinite(s.x) || !isFinite(s.y)) return null;
      /* 点落到相机后方（on:false）仍有真实屏幕坐标，照常纳入包围盒，不因此作废 */
      if (s.x < minx) minx = s.x;
      if (s.y < miny) miny = s.y;
      if (s.x > maxx) maxx = s.x;
      if (s.y > maxy) maxy = s.y;
    }
    return { left: minx, top: miny, right: maxx, bottom: maxy, w: maxx - minx, h: maxy - miny,
      unit: !!bboxU, u: U };
  }

  /* ---- 树心对位：单位的树在 [0,1] 沿 +Y，锚点把它整体下移 rimR*0.55，
   * 于是树心落在世界 y≈+0.6*rimR，而 home() 的相机注视点是 (0,0,0) —— 树因此在画面里偏上
   * （实测包围盒中心比视口中心高 136px），靠 zoom 永远修不回来：拉远只会让它更小。
   * 进入时把树心平移到注视点，取景才有可用空间；退出按快照逐字还原，默认构图不受影响。 ---- */
  function rebalance() {
    var a = anchor();
    if (!a || !a.root) return false;
    var r = null;
    try { r = a.root(); } catch (e) { return false; }
    if (!r || !r.position || !r.scale) return false;
    var s = +r.scale.x;
    if (!isFinite(s) || !(s > 0)) return false;
    try {
      /* 三轴对位到**实测 AABB 中心**，不再固定 -s*0.5。
       * 只调 y 的老做法有两个漏：① 假设树高恰好是 1（伞形冠顶到 y≈1.02，差 2% 会累积成几十像素）；
       * ② 主干是条 S 弯、板根又只往四个方向铺，整棵树的 AABB 中心在 x/z 上并不在 0 ——
       * 不平掉这一项，树在画面里始终斜着偏一点，zoom 永远修不回来（和当初 y 偏 136px 同一个病）。 */
      var U = bboxU;
      var cy = U ? (U.y0 + U.y1) * 0.5 : 0.5;
      var cx = U ? (U.x0 + U.x1) * 0.5 : 0;
      var cz = U ? (U.z0 + U.z1) * 0.5 : 0;
      r.position.y = -cy * s;   /* 单位空间树心 → 世界树心，平移到注视点 */
      r.position.x = -cx * s;
      r.position.z = -cz * s;
      r.updateMatrixWorld(true);
    } catch (e) { return false; }
    return true;
  }

  /* ---- 取景测量：**整树屏幕包围盒的竖直跨度** ÷ 视口高（与出界判据同源，见下） ---- */
  function measure() {
    heightRatio = -1;
    var a = anchor();
    if (!a || !a.toScreen) return -1;
    /* 测不到的判据是「相机没嗅到」：此时 toScreen 回占位 0,0,z:9。
     * 若相机已嗅到、只是树尖偶然落到相机后方（on:false），投影仍是真实屏幕坐标，照样可读。 */
    if (!a.ready || !a.cam) return -1;
    if (!a.cam()) return -1;
    var vh0 = window.innerHeight || 0;
    if (vh0 < 16) return -1;
    /* v35 口径统一：**与 bbox 同源**。
     * v34 时量的是「实测 AABB 上下沿**中点**」（主干轴投影），而取景决策里的出界判据用的是
     * measureBBox() 的**角点**包围盒 —— 两把标尺本来就不是一个数，v34 恰好量得接近（0.83 vs 0.830）
     * 才没暴露。v35 的根盘从 4 条变 16 条环向铺开后，角点被真实根尖占住，两个数就分岔了：
     *   轴投影 0.566（= 主干那根轴线在屏上占多高） vs 角点 0.711（= 整棵树在屏上占多高）。
     * 0.566 离 MIN_RATIO=0.55 只剩 0.016 —— 取景器一直以为树比实际小一截，纯属侥幸没触发拉近。
     * 现在直接取 bbox 的竖直跨度：**屏幕上的包围盒多高，heightRatio 就是多少**，一个真相。 */
    var bb = null;
    try { bb = measureBBox(); } catch (e2) { bb = null; }
    if (bb && bb.h > 1) {
      heightRatio = bb.h / vh0;
      return heightRatio;
    }
    /* 退路：骨架单位盒还没就绪（冷启动）时，按标称 [0,1,0]/[0,0,0] 粗量一次。
     * 只为「不空转」，不作为稳态读数 —— 就绪后下一帧就走上面那条同源路径。 */
    var tip = null, root = null;
    try { tip = a.toScreen([0, 1, 0]); root = a.toScreen([0, 0, 0]); } catch (e) { return -1; }
    if (!tip || !root) return -1;
    if (typeof tip.y !== 'number' || typeof root.y !== 'number') return -1;
    if (!isFinite(tip.y) || !isFinite(root.y)) return -1;
    var d = Math.abs(tip.y - root.y);
    if (!(d > 1)) return -1; /* 冷启动两投影同为 0，或树被压成一条线 → 测不到 */
    var px = d / vh0;
    /* toScreen 若返回 NDC（|y|≤1），像素值假小，按 d/2 解读；加 1.05 上界防误判大位移 */
    if (px < 0.02 && (d / 2 > 0.1) && (d / 2 <= 1.05)) heightRatio = d / 2;
    else heightRatio = px;
    return heightRatio;
  }

  function degradeOf(s) {
    try { if (typeof s === 'number') return s; } catch (e) {}
    try { if (s && typeof s.degrade === 'number') return s.degrade; } catch (e) {}
    try { var S = scene(); if (S && typeof S.degrade === 'number') return S.degrade; } catch (e) {}
    return 0;
  }

  /* ---- 取景校正：一次一档、隔 20 帧、最多连调 6 次；回到舒适带才归零 ----
   * 判据升级为「整树必须完整落在视口安全区内」：先看包围盒有没有出界，
   * 出界就拉远（k>1 = 越远），不出界才按树高舒适带做贴近/收紧。
   * 返回 true 表示本帧确实调了一次 zoom（供 kick 判断收敛）。 */
  function check() {
    var r = measure();
    if (r < 0) return false; /* 测不到绝不动 zoom（含冷启动占位 0） */
    var S = scene();
    if (!S || !S.zoom) return false;
    var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    if (vw < 16 || vh < 16) return false;
    var bb = measureBBox();
    if (bb) bbox = bb;              /* 测到就刷新；没测到保留上一次有效值 */
    else if (!bbox) return false;   /* 自始至终没测到 → 绝不调 zoom */
    var use = bbox;
    var SAFE_TOP = SAFE_MARGIN, SAFE_BOTTOM = vh - SAFE_MARGIN;
    var SAFE_L = SAFE_MARGIN, SAFE_R = vw - SAFE_MARGIN;
    var overflow = (use.top < SAFE_TOP) || (use.bottom > SAFE_BOTTOM) ||
                   (use.left < SAFE_L) || (use.right > SAFE_R);
    if (overflow) {
      if (zoomSteps >= MAX_STEPS) return false;
      /* 拉远量按「出界的那条边到屏幕中心的距离」求解，不能按整树高度算：
       * zoom 是绕屏幕中心按 1/k 缩放的，而树在画面里并不垂直居中（实测偏上 39px），
       * 用 h/(vh*SAFE_FILL) 会算出「刚好还是差十几像素」的临界值 —— 上一版就卡在 top=-14.9。 */
      var cx = vw * 0.5, cy = vh * 0.5;
      var k = 1;
      var kt, kb, kl, kr;
      if (use.top < SAFE_TOP) { kt = (cy - use.top) / Math.max(1, cy - SAFE_TOP); if (kt > k) k = kt; }
      if (use.bottom > SAFE_BOTTOM) { kb = (use.bottom - cy) / Math.max(1, SAFE_BOTTOM - cy); if (kb > k) k = kb; }
      if (use.left < SAFE_L) { kl = (cx - use.left) / Math.max(1, cx - SAFE_L); if (kl > k) k = kl; }
      if (use.right > SAFE_R) { kr = (use.right - cx) / Math.max(1, SAFE_R - cx); if (kr > k) k = kr; }
      k *= 1.03;                                /* 3% 余量，免得收敛在临界值上来回抖 */
      if (k < 1.02) k = 1.02;
      if (k > 1.25) k = 1.25;                   /* 一次别拉太狠，受 maxDistance 夹取，分档收敛 */
      try { S.zoom(k); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else if (r < MIN_RATIO) {
      if (zoomSteps >= MAX_STEPS) return false;
      /* 拉近用「最大安全放大比」而不是固定的 ZOOM_NEAR=0.92：
       * 树在画面里并不居中，固定档既可能一步就出界、也可能永远够不到舒适带（实测卡在 0.4157）。
       * 这里直接解出「最出界的那条边贴到安全区 96% 处」所对应的放大比，一步到位。 */
      var cx2 = vw * 0.5, cy2 = vh * 0.5;
      var dmax = Math.max(cy2 - use.top, use.bottom - cy2, cx2 - use.left, use.right - cx2);
      var allow = Math.min(cy2 - SAFE_TOP, SAFE_BOTTOM - cy2, cx2 - SAFE_L, SAFE_R - cx2);
      if (!(dmax > 1) || !(allow > 1)) return false;
      var grow = (allow * 0.96) / dmax;          /* >1 表示还有放大余地 */
      if (grow <= 1.004) { zoomSteps = 0; return false; } /* 已贴到安全区边缘 → 收手，别空转 */
      var kIn = 1 / grow;                        /* S.zoom 的 k<1 = 拉近 */
      if (kIn < ZOOM_NEAR) kIn = ZOOM_NEAR;      /* 一次不越过一档，防过冲 */
      try { S.zoom(kIn); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else if (r > MAX_RATIO) {
      if (zoomSteps >= MAX_STEPS) return false;
      try { S.zoom(ZOOM_FAR); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else {
      zoomSteps = 0; /* 在舒适带内归零，之后的缓慢漂移仍可再校正 */
      return false;
    }
  }

  /* ---- 同步收敛兜底：无头/隐藏页里宿主循环只在预热期回调 update、CAM 嗅到即停，
   * 定时器又被节流，校正可能一次都跑不到。一旦 CAM 就绪就一次性把取景收敛到位
   * （仍受 MAX_STEPS 限次、一次一档，与正常路径同一套判定）。 ---- */
  function kick() {
    for (var n = 0; n < MAX_STEPS + 2; n++) {
      if (!check()) break; /* check 没步进＝已入舒适带/测不到/已达限次 → 收敛或停下 */
    }
  }
  /* 钩住锚点的 toScreen：它是全工程每帧都会被调用（星点迁移/渲染）的入口，
   * 因此 CAM 一就绪就能可靠触发一次收敛，不依赖被节流的定时器或宿主回调。 */
  function hookAnchor() {
    var a = anchor();
    if (!a || !a.toScreen || a.__tsHooked) return;
    var orig = a.toScreen;
    a.__tsHooked = true;
    a.toScreen = function () {
      var r = orig.apply(a, arguments);
      try { if (active && !kicked && a.cam && a.cam()) { kicked = true; kick(); } } catch (e) {}
      return r;
    };
  }

  function enter() {
    var S = scene();
    if (!S || !S.setStage || !S.stage || !S.home) return false; /* 守空：依赖缺席不硬上 */
    if (active) return true;
    var g0 = 0, gd = 1;
    try { var st = S.stage(); if (st && typeof st.goal === 'number') g0 = st.goal; } catch (e) {}
    try { /* 读得到真实 ghost 深度就存真实值，读不到按默认 1 快照 */
      var gh = ghost();
      if (gh && gh.stats) { var gs = gh.stats(); if (gs && typeof gs.depth === 'number') gd = gs.depth; }
    } catch (e) {}
    // 树心快照（三轴）：退出要逐字还原，默认构图一个像素都不许被改。
    // v32 只快照 y，因为那时也只动 y；现在 rebalance 动三轴，快照必须跟着补齐 ——
    // 少存一个轴，退出后那根轴就永久留在被改过的值上（默认构图被静默污染，且没有任何断言能发现）。
    var py0 = null, px0 = null, pz0 = null;
    try {
      var a0 = anchor(); var r0 = (a0 && a0.root) ? a0.root() : null;
      if (r0 && r0.position) { py0 = r0.position.y; px0 = r0.position.x; pz0 = r0.position.z; }
    } catch (e) {}
    before = { stageK: g0, ghostDepth: gd, posY: py0, posX: px0, posZ: pz0 };
    try { S.setStage(STAGE_K); } catch (e) { before = null; return false; }
    try { var g2 = ghost(); if (g2 && g2.setDepth) g2.setDepth(GHOST_DEPTH); } catch (e) {}
    rebalance(); /* 树心落到相机注视点：否则树在画面里偏上 136px，缩放修不回来（穷举过） */
    ensureStyle();
    try { document.body.classList.add(BODY_CLS); } catch (e) {}
    try { S.home(); } catch (e) {} /* 回全景标准机位，取景才有一个确定起点 */
    active = true;
    restored = false;
    zoomSteps = 0;
    bbox = null; /* 进入时清掉上一次会话残留的包围盒，首帧重新测 */
    bboxU = null; /* 实测单位框也一并作废：换作品后骨架变了，旧的框会把新树切掉 */
    kicked = false; /* 本次进入允许重新做一次同步收敛 */
    nextCheck = frame + FIRST_DELAY;
    measure();
    hookAnchor(); /* 钩住 toScreen：CAM 一嗅到就能可靠触发收敛 */
    startPump(); /* 自驱兜底：宿主循环不回调 update 时也能完成取景校正 */
    return true;
  }

  function exit() {
    if (!active) return false;
    var S = scene();
    if (before) {
      try { if (S && S.setStage) S.setStage(before.stageK); } catch (e) {}
      try { var g = ghost(); if (g && g.setDepth) g.setDepth(before.ghostDepth); } catch (e) {}
      try { /* 树心按进入前快照逐字还原（三轴，缺哪个还原哪个） */
        var a1 = anchor(); var r1 = (a1 && a1.root) ? a1.root() : null;
        if (r1 && r1.position) {
          if (before.posY != null) r1.position.y = before.posY;
          if (before.posX != null) r1.position.x = before.posX;
          if (before.posZ != null) r1.position.z = before.posZ;
          r1.updateMatrixWorld(true);
        }
      } catch (e) {}
    }
    try { document.body.classList.remove(BODY_CLS); } catch (e) {}
    try { if (S && S.home) S.home(); } catch (e) {}
    active = false;
    kicked = false;
    restored = true; /* 已按进入前快照还原 */
    before = null;
    stopPump(); /* 退出即停自驱，绝不空转 */
    return true;
  }

  function toggle() { return active ? exit() : enter(); }
  function setOn(v) { return v ? enter() : exit(); }
  function activeFn() { return active; }

  function build(o) {
    mounted = true;
    // 秘仪层每次重建布局都会 dispose→build，而 dispose 把监听摘了并把 onPlotline 置 null。
    // 不在这里补挂，第一次重建之后「显示剧情线」这个事件就再也进不来了（实测踩过）。
    if (!onPlotline) {
      onPlotline = plotlineHandler;
      try { document.addEventListener('cl:tree-plotline', onPlotline); } catch (e0) {}
    }
    try { /* 无头验收：?treestage=1 构建后自动进入 */
      if (new URLSearchParams(location.search).get('treestage') === '1') pendingAuto = true;
    } catch (e) {}
    if (pendingAuto && enter()) pendingAuto = false;
    hookAnchor(); /* 即便走 build 路径也要确保钩子挂上 */
    return true;
  }

  function update(s) {
    frame++;
    if (pendingAuto) { if (enter()) pendingAuto = false; }
    muted = (degradeOf(s) >= 2); /* 低配档不做取景跟踪：省帧，也避免低帧率下抖动 */
    if (!active || muted) return;
    /* v42 静止档（scene.setCalm(true)）：取景校正本身就是「动效」——
     * 验收的像素门禁要求两次拍摄之间**相机绝对不动**。check() 在临界值上会反复
     * 微调（zoomSteps 归零后又能再调 6 档），自驱 pump 每 320ms 推一次，
     * 于是 A/C 同态两拍之间画面整体位移，噪声地板被顶到 5%（desync-visible 实测）。
     * 这里出手：calm 时不测量、不校正。舞台的初始取景在 calm 之前已完成。 */
    var S0 = scene();
    if (S0 && typeof S0.calm === 'function' && S0.calm()) return;
    /* CAM 就绪但宿主循环没再把 update 驱动起来时，借这一帧同步收敛一次 */
    var a = anchor();
    if (a && a.cam && a.cam() && !kicked) { kicked = true; kick(); }
    /* anchor 冷启动未就绪时只做轻测量（两次投影），zoom 校正仍走 20 帧节奏 */
    if (heightRatio < 0) { measure(); return; }
    if (frame < nextCheck) return;
    nextCheck = frame + STEP_GAP;
    check();
  }

  /* ---- 自驱校正：无头/隐藏页里宿主渲染循环未必会逐帧回调 update（实测 headless 下主循环
   * 只在预热窗口回调、CAM 嗅到后即停），这里用 setInterval 兜底推进取景，确保「完整树」判定一定发生。
   * 与宿主回调并存时只是多一路驱动，update 内部有 STEP_GAP 限频、幂等，互不打架。
   * v42：静止档下连这一路也停 —— update 已在入口挡掉，这里再挡一次是为了省掉空调用。 ---- */
  function pump() {
    if (!!(window.CLSky && CLSky.enabled && CLSky.enabled())) { stopPump(); return; }   /* 星空壳：旧剧情树舞台不上屏，16 ms 泵停 */
    if (!active) return;
    var S0 = scene();
    if (S0 && typeof S0.calm === 'function' && S0.calm()) return;
    try { update(null); } catch (e) {}
  }
  function startPump() {
    stopPump();
    if (typeof setInterval === 'function') rafId = setInterval(pump, 16);
  }
  function stopPump() {
    if (rafId) { try { clearInterval(rafId); } catch (e) {} rafId = 0; }
  }

  function dispose() {
    try { if (active) exit(); } catch (e) {}
    try { if (onPlotline) document.removeEventListener('cl:tree-plotline', onPlotline); } catch (e) {}
    onPlotline = null;
    removeStyle();
    stopPump();
    mounted = false;
    pendingAuto = false;
  }

  /* 剧情线开关事件：detail.on === true 进入，=== false 退出 */
  function plotlineHandler(ev) {
    var d = (ev && ev.detail) ? ev.detail : null;
    if (d && d.on === true) enter();
    else if (d && d.on === false) exit();
  }
  onPlotline = plotlineHandler;
  try { document.addEventListener('cl:tree-plotline', onPlotline); } catch (e) {}

  function stats() {
    var k = -1;
    try {
      var S = scene();
      if (S && S.stage) { var st = S.stage(); if (st && typeof st.k === 'number') k = st.k; }
    } catch (e) {}
    return {
      mounted: mounted,
      active: active,
      stage: k,
      heightRatio: heightRatio,
      zoomSteps: zoomSteps,
      restored: restored,
      hasAnchor: !!(anchor() && anchor().toScreen),
      muted: muted
    };
  }

  var API = {
    name: 'tree-stage',
    build: build,
    update: update,
    dispose: dispose,
    setOn: setOn,
    enter: enter,
    exit: exit,
    toggle: toggle,
    active: activeFn,
    stats: stats
  };

  window.CLTreeStage = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
