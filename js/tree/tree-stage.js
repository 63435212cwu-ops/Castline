(function () {
  'use strict';

  var BODY_CLS = 'cl-treestage';
  var STYLE_ID = 'cl-treestage-style';

  var STAGE_K = 0.72;
  var GHOST_DEPTH = 1.35;
  var ZOOM_NEAR = 0.92, ZOOM_FAR = 1.08;
  var MAX_STEPS = 6;
  var STEP_GAP = 20;
  var MIN_RATIO = 0.55, MAX_RATIO = 0.95;
  var FIRST_DELAY = 40;
  var SAFE_MARGIN = 24;
  var SAFE_FILL = 0.86;
  var BBOX_XZ = 0.6, BBOX_YTOP = 1.05;
  var bboxU = null;

  var before = null;
  var active = false;
  var mounted = false;
  var restored = false;
  var muted = false;
  var heightRatio = -1;
  var bbox = null;
  var kicked = false;
  var zoomSteps = 0;
  var frame = 0;
  var nextCheck = -1;
  var styleEl = null;
  var onPlotline = null;
  var pendingAuto = false;
  var rafId = 0;

  function scene() {
    return (window.__cl && window.__cl.scene) ? window.__cl.scene : null;
  }
  function anchor() { return window.CLTreeAnchor || null; }
  function ghost() { return window.CLTreeGhost || null; }

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

  function measureBBox() {
    var a = anchor();
    if (!a || !a.toScreen) return null;
    if (!a.ready || !a.cam) return null;
    if (!a.cam()) return null;
    var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    if (vw < 16 || vh < 16) return null;
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
      if (s.x < minx) minx = s.x;
      if (s.y < miny) miny = s.y;
      if (s.x > maxx) maxx = s.x;
      if (s.y > maxy) maxy = s.y;
    }
    return { left: minx, top: miny, right: maxx, bottom: maxy, w: maxx - minx, h: maxy - miny,
      unit: !!bboxU, u: U };
  }

  function rebalance() {
    var a = anchor();
    if (!a || !a.root) return false;
    var r = null;
    try { r = a.root(); } catch (e) { return false; }
    if (!r || !r.position || !r.scale) return false;
    var s = +r.scale.x;
    if (!isFinite(s) || !(s > 0)) return false;
    try {
      var U = bboxU;
      var cy = U ? (U.y0 + U.y1) * 0.5 : 0.5;
      var cx = U ? (U.x0 + U.x1) * 0.5 : 0;
      var cz = U ? (U.z0 + U.z1) * 0.5 : 0;
      r.position.y = -cy * s;
      r.position.x = -cx * s;
      r.position.z = -cz * s;
      r.updateMatrixWorld(true);
    } catch (e) { return false; }
    return true;
  }

  function measure() {
    heightRatio = -1;
    var a = anchor();
    if (!a || !a.toScreen) return -1;
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
    var tip = null, root = null;
    try { tip = a.toScreen([0, 1, 0]); root = a.toScreen([0, 0, 0]); } catch (e) { return -1; }
    if (!tip || !root) return -1;
    if (typeof tip.y !== 'number' || typeof root.y !== 'number') return -1;
    if (!isFinite(tip.y) || !isFinite(root.y)) return -1;
    var d = Math.abs(tip.y - root.y);
    if (!(d > 1)) return -1;
    var px = d / vh0;
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

  function check() {
    var r = measure();
    if (r < 0) return false;
    var S = scene();
    if (!S || !S.zoom) return false;
    var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    if (vw < 16 || vh < 16) return false;
    var bb = measureBBox();
    if (bb) bbox = bb;
    else if (!bbox) return false;
    var use = bbox;
    var SAFE_TOP = SAFE_MARGIN, SAFE_BOTTOM = vh - SAFE_MARGIN;
    var SAFE_L = SAFE_MARGIN, SAFE_R = vw - SAFE_MARGIN;
    var overflow = (use.top < SAFE_TOP) || (use.bottom > SAFE_BOTTOM) ||
                   (use.left < SAFE_L) || (use.right > SAFE_R);
    if (overflow) {
      if (zoomSteps >= MAX_STEPS) return false;
      var cx = vw * 0.5, cy = vh * 0.5;
      var k = 1;
      var kt, kb, kl, kr;
      if (use.top < SAFE_TOP) { kt = (cy - use.top) / Math.max(1, cy - SAFE_TOP); if (kt > k) k = kt; }
      if (use.bottom > SAFE_BOTTOM) { kb = (use.bottom - cy) / Math.max(1, SAFE_BOTTOM - cy); if (kb > k) k = kb; }
      if (use.left < SAFE_L) { kl = (cx - use.left) / Math.max(1, cx - SAFE_L); if (kl > k) k = kl; }
      if (use.right > SAFE_R) { kr = (use.right - cx) / Math.max(1, SAFE_R - cx); if (kr > k) k = kr; }
      k *= 1.03;
      if (k < 1.02) k = 1.02;
      if (k > 1.25) k = 1.25;
      try { S.zoom(k); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else if (r < MIN_RATIO) {
      if (zoomSteps >= MAX_STEPS) return false;
      var cx2 = vw * 0.5, cy2 = vh * 0.5;
      var dmax = Math.max(cy2 - use.top, use.bottom - cy2, cx2 - use.left, use.right - cx2);
      var allow = Math.min(cy2 - SAFE_TOP, SAFE_BOTTOM - cy2, cx2 - SAFE_L, SAFE_R - cx2);
      if (!(dmax > 1) || !(allow > 1)) return false;
      var grow = (allow * 0.96) / dmax;
      if (grow <= 1.004) { zoomSteps = 0; return false; }
      var kIn = 1 / grow;
      if (kIn < ZOOM_NEAR) kIn = ZOOM_NEAR;
      try { S.zoom(kIn); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else if (r > MAX_RATIO) {
      if (zoomSteps >= MAX_STEPS) return false;
      try { S.zoom(ZOOM_FAR); } catch (e) { return false; }
      zoomSteps++;
      return true;
    } else {
      zoomSteps = 0;
      return false;
    }
  }

  function kick() {
    for (var n = 0; n < MAX_STEPS + 2; n++) {
      if (!check()) break;
    }
  }
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
    if (!S || !S.setStage || !S.stage || !S.home) return false;
    if (active) return true;
    var g0 = 0, gd = 1;
    try { var st = S.stage(); if (st && typeof st.goal === 'number') g0 = st.goal; } catch (e) {}
    try {
      var gh = ghost();
      if (gh && gh.stats) { var gs = gh.stats(); if (gs && typeof gs.depth === 'number') gd = gs.depth; }
    } catch (e) {}
    var py0 = null, px0 = null, pz0 = null;
    try {
      var a0 = anchor(); var r0 = (a0 && a0.root) ? a0.root() : null;
      if (r0 && r0.position) { py0 = r0.position.y; px0 = r0.position.x; pz0 = r0.position.z; }
    } catch (e) {}
    before = { stageK: g0, ghostDepth: gd, posY: py0, posX: px0, posZ: pz0 };
    try { S.setStage(STAGE_K); } catch (e) { before = null; return false; }
    try { var g2 = ghost(); if (g2 && g2.setDepth) g2.setDepth(GHOST_DEPTH); } catch (e) {}
    rebalance();
    ensureStyle();
    try { document.body.classList.add(BODY_CLS); } catch (e) {}
    try { S.home(); } catch (e) {}
    active = true;
    restored = false;
    zoomSteps = 0;
    bbox = null;
    bboxU = null;
    kicked = false;
    nextCheck = frame + FIRST_DELAY;
    measure();
    hookAnchor();
    startPump();
    return true;
  }

  function exit() {
    if (!active) return false;
    var S = scene();
    if (before) {
      try { if (S && S.setStage) S.setStage(before.stageK); } catch (e) {}
      try { var g = ghost(); if (g && g.setDepth) g.setDepth(before.ghostDepth); } catch (e) {}
      try {
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
    restored = true;
    before = null;
    stopPump();
    return true;
  }

  function toggle() { return active ? exit() : enter(); }
  function setOn(v) { return v ? enter() : exit(); }
  function activeFn() { return active; }

  function build(o) {
    mounted = true;
    if (!onPlotline) {
      onPlotline = plotlineHandler;
      try { document.addEventListener('cl:tree-plotline', onPlotline); } catch (e0) {}
    }
    try {
      if (new URLSearchParams(location.search).get('treestage') === '1') pendingAuto = true;
    } catch (e) {}
    if (pendingAuto && enter()) pendingAuto = false;
    hookAnchor();
    return true;
  }

  function update(s) {
    frame++;
    if (pendingAuto) { if (enter()) pendingAuto = false; }
    muted = (degradeOf(s) >= 2);
    if (!active || muted) return;
    /* v42 静止档（scene.setCalm(true)）：取景校正本身就是「动效」——
     * 验收的像素门禁要求两次拍摄之间**相机绝对不动**。check() 在临界值上会反复
     * 微调（zoomSteps 归零后又能再调 6 档），自驱 pump 每 320ms 推一次，
     * 于是 A/C 同态两拍之间画面整体位移，噪声地板被顶到 5%（desync-visible 实测）。
     * 这里出手：calm 时不测量、不校正。舞台的初始取景在 calm 之前已完成。 */
    var S0 = scene();
    if (S0 && typeof S0.calm === 'function' && S0.calm()) return;
    var a = anchor();
    if (a && a.cam && a.cam() && !kicked) { kicked = true; kick(); }
    if (heightRatio < 0) { measure(); return; }
    if (frame < nextCheck) return;
    nextCheck = frame + STEP_GAP;
    check();
  }

  function pump() {
    if (!!(window.CLSky && CLSky.enabled && CLSky.enabled())) { stopPump(); return; }
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
