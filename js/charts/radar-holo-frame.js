/**
 * Castline · radar-holo-frame.js — 全息赛博雷达 HUD 外框与星象刻盘 (U03)
 *
 * 核心功能：
 * 1. renderFrameSVG(cx, cy, R, opt): 生成雷达底图赛博全息外框与星象刻度盘 SVG 片段
 *    - 外围科技切角导轨 (Chamfered Guide Rails)
 *    - 精密经纬度十字准线 (Precision Longitude-Latitude Crosshairs)
 *    - 微型坐标标尺 (Micro-coordinate Vernier Ruler)
 *    - 二十八宿星位参考分划虚线环 (28 Lunar Mansions Reference Division Dashed Ring)
 *    - 四个方位的全息代码角标 [MK-IV / SYS-GRID] (Holographic Cardinal Code Badges)
 * 2. renderGhostPolygon(benchPoints, opt): 生成全书基准幽灵线 SVG 标签
 *    - dasharray 虚线与半透明发光
 *
 * 最小使用示例 (Minimal Usage Example):
 * ```javascript
 * // 1. 生成赛博全息外框与星象刻盘 SVG 片段
 * const frameSVG = window.CLRadarHoloFrame.renderFrameSVG(160, 164, 91.2, {
 *   squash: 0.9,
 *   showMansions: true,
 *   showCrosshair: true,
 *   showRails: true,
 *   showRuler: true,
 *   showBadges: true
 * });
 *
 * // 2. 生成全书基准幽灵轮廓多边形 (支持点坐标数组、分值数组或分值字典)
 * const benchScores = [52, 60, 55, 72, 48, 64, 50, 58];
 * const ghostSVG = window.CLRadarHoloFrame.renderGhostPolygon(benchScores, {
 *   cx: 160, cy: 164, R: 91.2, squash: 0.9
 * });
 *
 * // 3. 注入雷达 SVG 底层或场景中
 * const radarSVG = document.querySelector('svg.radar-3d');
 * if (radarSVG) {
 *   radarSVG.insertAdjacentHTML('afterbegin', frameSVG + ghostSVG);
 * }
 * ```
 */

(function (global) {
  'use strict';

  // 共享约定：八维绝对标准与英文键值映射
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = {
    智谋: 'MIND',
    实力: 'FORCE',
    意志: 'WILL',
    魅力: 'CHARM',
    情感: 'HEART',
    野心: 'DRIVE',
    权势: 'REACH',
    道义: 'CODE'
  };

  // 中国古代天文学二十八宿（四象各七宿，构成天球赤道与黄道基准坐标参考系）
  var TWENTY_EIGHT_MANSIONS = [
    // 东方苍龙七宿 (0..6)
    { name: '角', quad: 'east', quadName: '苍龙', en: 'Jiao' },
    { name: '亢', quad: 'east', quadName: '苍龙', en: 'Kang' },
    { name: '氐', quad: 'east', quadName: '苍龙', en: 'Di' },
    { name: '房', quad: 'east', quadName: '苍龙', en: 'Fang' },
    { name: '心', quad: 'east', quadName: '苍龙', en: 'Xin' },
    { name: '尾', quad: 'east', quadName: '苍龙', en: 'Wei' },
    { name: '箕', quad: 'east', quadName: '苍龙', en: 'Ji' },
    // 北方玄武七宿 (7..13)
    { name: '斗', quad: 'north', quadName: '玄武', en: 'Dou' },
    { name: '牛', quad: 'north', quadName: '玄武', en: 'Niu' },
    { name: '女', quad: 'north', quadName: '玄武', en: 'Nu' },
    { name: '虚', quad: 'north', quadName: '玄武', en: 'Xu' },
    { name: '危', quad: 'north', quadName: '玄武', en: 'Wei' },
    { name: '室', quad: 'north', quadName: '玄武', en: 'Shi' },
    { name: '壁', quad: 'north', quadName: '玄武', en: 'Bi' },
    // 西方白虎七宿 (14..20)
    { name: '奎', quad: 'west', quadName: '白虎', en: 'Kui' },
    { name: '娄', quad: 'west', quadName: '白虎', en: 'Lou' },
    { name: '胃', quad: 'west', quadName: '白虎', en: 'Wei' },
    { name: '昴', quad: 'west', quadName: '白虎', en: 'Mao' },
    { name: '毕', quad: 'west', quadName: '白虎', en: 'Bi' },
    { name: '觜', quad: 'west', quadName: '白虎', en: 'Zui' },
    { name: '参', quad: 'west', quadName: '白虎', en: 'Shen' },
    // 南方朱雀七宿 (21..27)
    { name: '井', quad: 'south', quadName: '朱雀', en: 'Jing' },
    { name: '鬼', quad: 'south', quadName: '朱雀', en: 'Gui' },
    { name: '柳', quad: 'south', quadName: '朱雀', en: 'Liu' },
    { name: '星', quad: 'south', quadName: '朱雀', en: 'Xing' },
    { name: '张', quad: 'south', quadName: '朱雀', en: 'Zhang' },
    { name: '翼', quad: 'south', quadName: '朱雀', en: 'Yi' },
    { name: '轸', quad: 'south', quadName: '朱雀', en: 'Zhen' }
  ];

  /**
   * 安全数值校验：防防御性默认值处理，严防 NaN 与破损坐标
   */
  function safeNum(v, fallback) {
    var n = Number(v);
    return (typeof n === 'number' && isFinite(n)) ? n : (typeof fallback === 'number' ? fallback : 0);
  }

  /**
   * 坐标精度四舍五入（保留2位小数，杜绝长浮点与 NaN）
   */
  function round(v) {
    return Math.round(safeNum(v, 0) * 100) / 100;
  }

  /**
   * 字符串 HTML/SVG 转义
   */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c;
    });
  }

  /**
   * 输出防御性清洗：确保没有任何 NaN / undefined / null 破损字符流入 SVG
   */
  function sanitizeSVG(str) {
    if (typeof str !== 'string') return '';
    if (str.indexOf('NaN') !== -1 || str.indexOf('undefined') !== -1 || str.indexOf('null') !== -1) {
      str = str.replace(/\bNaN\b/g, '0').replace(/\bundefined\b/g, '0').replace(/\bnull\b/g, '');
    }
    return str;
  }

  /**
   * 计算指定角度与半径在椭圆视角下的坐标点
   */
  function radialPoint(cx, cy, r, angleRad, squash) {
    var sq = safeNum(squash, 0.9);
    return [
      round(cx + Math.cos(angleRad) * r),
      round(cy + Math.sin(angleRad) * r * sq)
    ];
  }

  /**
   * 辅助生成多边形 points 属性字符串
   */
  function pointsToStr(pts) {
    if (!Array.isArray(pts) || !pts.length) return '';
    return pts.map(function (p) {
      return round(p[0]) + ',' + round(p[1]);
    }).join(' ');
  }

  /**
   * R5-E · 导轨几何单一真源（rw/rh/切角/内层虚线导轨）。
   * 原先 renderFrameSVG 与运行时分段折算各写一份 1.54/1.62/0.22 会重蹈 R5-C 注释里
   * 「两处独立魔数、任一改动都要同步」的坑；抽出来给两处共用。数值本身不变（美术裁定
   * 未变——外框宽高比例仍是①②方案否决后定的那一版），只是不再重复字面量。
   */
  function railGeometry(R) {
    var rw = round(R * 1.54);
    var rh = round(R * 1.62);
    var c = round(R * 0.22);
    var inset = 5;
    var cIn = Math.max(2, c - 2);
    return { rw: rw, rh: rh, c: c, inset: inset, cIn: cIn, rwIn: rw - inset, rhIn: rh - inset };
  }

  /**
   * 生成全息赛博科技外框与星象刻盘 SVG
   * @param {number} cx 中心 X 坐标 (默认 160)
   * @param {number} cy 中心 Y 坐标 (默认 164)
   * @param {number} R 雷达基准外半径 (默认 91.2)
   * @param {Object} opt 配置项
   * @returns {string} SVG 片段
   */
  function renderFrameSVG(cx, cy, R, opt) {
    opt = opt || {};
    var parsedSize = safeNum(opt.size, 320);
    cx = safeNum(cx, parsedSize / 2);
    cy = safeNum(cy, parsedSize / 2 + 4);
    R = Math.max(10, safeNum(R, parsedSize * 0.285));

    var squash = Math.max(0.1, safeNum(opt.squash, 0.9));
    var showRails = opt.showRails !== false;
    var showCrosshair = opt.showCrosshair !== false;
    var showRuler = opt.showRuler !== false;
    var showMansions = opt.showMansions !== false;
    var showBadges = opt.showBadges !== false;

    var uid = opt.idPrefix || ('cl-hf-' + Math.floor(Math.random() * 1e6).toString(36));
    var out = [];

    out.push('<g class="cl-holo-frame" data-cx="' + round(cx) + '" data-cy="' + round(cy) + '" data-r="' + round(R) + '" aria-hidden="true">');

    // 嵌入式滤镜与渐变定义（仅使用契约令牌变量）
    out.push('<defs>');
    out.push('<filter id="' + uid + '-glow" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB">');
    out.push('<feGaussianBlur stdDeviation="2.4" result="blur"/>');
    out.push('<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>');
    out.push('</filter>');
    out.push('<linearGradient id="' + uid + '-rail-g" x1="0" y1="0" x2="1" y2="1">');
    out.push('<stop offset="0%" stop-color="var(--signal, #ffb45c)" stop-opacity="0.32"/>');
    out.push('<stop offset="50%" stop-color="var(--mint, #7af0c8)" stop-opacity="0.22"/>');
    out.push('<stop offset="100%" stop-color="var(--violet, #a688ff)" stop-opacity="0.36"/>');
    out.push('</linearGradient>');
    out.push('</defs>');

    // 1. 外围科技切角导轨 (Chamfered Guide Rails)
    if (showRails) {
      var rw = round(R * 1.54);
      /* R5-C §1（轴标签「删除线」）——**挪线**。
       * 旧值 1.38 ⇒ 半高 rh = 125.86，导轨上下两条边落在 user y = 38.14 / 289.86。
       * 而上下两个轴标签胶囊带（由 radar.js 的 `pt(i, R+44)` 决定）是
       * 智谋 [24.3, 60.3] · 情感 [267.7, 303.7] —— 两条边各自**落在胶囊带内部 13.8px**，
       * 且正好压在第二行小字（`HEART · 待建档`）的高度上。导轨在胶囊处被芯片挡住、
       * 在胶囊左右两侧继续延伸，于是「一条横线从文字中间穿进穿出」= 删除线观感
       * （CDP 像素实测：390 下琥珀行 y=802 与「情感」胶囊带 [785.6, 812.5] 同高）。
       * 注意：线本身**没有**画在芯片之上（同一行的芯片 x 带内琥珀像素 = 0，被 α .91 的
       * `.rd-chip` 挡住），所以「加底衬」是无效修法——必须把线**移出标签带**。
       * 1.62 ⇒ rh = 147.74，两条边到胶囊带各留 8.04px；外框因此比宽略高（140.45 : 147.74，
       * 高 5%），正好把 8 个轴标签整体收进框内——这与它「全息刻盘外框」的语义一致。
       * 另：rail 顶端的 L 护角再外扩 2.5px（= 13.76），radar.js 的 VB_Y 留白已按此对齐
       * （radar.js 侧 `VB_MARGIN = 8`，VB_Y = min(contentTop, railTop) − 8；1440 实测
       *  railTop = cy − R*1.62 − 2.5 = 14 ⇒ VB_Y = 6、railBBox.y = 13.8）。
       * ⚠ 两处是独立魔数，任一改动都要同步；门禁 tests/radar_footer_fold_browser.py 的
       * railInsideViewBox 会拦住不同步。（2026-09-20 R5-C 校正：此处原写「VB_MARGIN = 12
       * ⇒ viewBox 顶 = 12」，与 radar.js 的实现 8 不符，属注释漂移，已按实测改口。） */
      var rgeo = railGeometry(R);
      var rh = rgeo.rh;
      var c = rgeo.c; // 切角尺寸
      /* R5-E（2026-09-21，方案③分段导轨，主控裁定）——左右竖边穿标签的初始渲染仍原样吐出
       * 完整闭合八边形（不在此处分段）：renderFrameSVG 只按 (cx,R) 拍板几何，此时 radar.js
       * 还没画到 6 个斜向标签芯片（chipX/chipY 是稍后的循环才算出来，见 radar.js 673 行附近），
       * 拿不到「标签带在哪」这个运行时数据。真正的分段发生在下方新增的 foldAllFrames()：
       * 宿主一次性 innerHTML 整段 SVG（含本外框与全部 rd-lab 芯片）落地后，用 MutationObserver
       * 读芯片 getBBox()（只读，不猜、不用固定角度公式）现改左右竖边。这里的完整闭合形状是
       * 「未折算前的合法回退态」——若脚本未跑（如纯 jsc 单测环境无 document），仍是一个能读的
       * 完整外框，不会因为分段逻辑缺席而破损。 */

      // 8 顶点外切角八边形导轨
      var vOuter = [
        [cx - rw + c, cy - rh],      // 顶边左端
        [cx + rw - c, cy - rh],      // 顶边右端
        [cx + rw, cy - rh + c],      // 右边顶端
        [cx + rw, cy + rh - c],      // 右边底端
        [cx + rw - c, cy + rh],      // 底边右端
        [cx - rw + c, cy + rh],      // 底边左端
        [cx - rw, cy + rh - c],      // 左边底端
        [cx - rw, cy - rh + c]       // 左边顶端
      ];

      // 内层平行虚线导轨
      var cIn = rgeo.cIn;
      var rwIn = rgeo.rwIn;
      var rhIn = rgeo.rhIn;
      var vInner = [
        [cx - rwIn + cIn, cy - rhIn],
        [cx + rwIn - cIn, cy - rhIn],
        [cx + rwIn, cy - rhIn + cIn],
        [cx + rwIn, cy + rhIn - cIn],
        [cx + rwIn - cIn, cy + rhIn],
        [cx - rwIn + cIn, cy + rhIn],
        [cx - rwIn, cy + rhIn - cIn],
        [cx - rwIn, cy - rhIn + cIn]
      ];

      out.push('<g class="cl-holo-rails">');
      // 外层科技切角主导轨
      out.push('<polygon class="cl-holo-rail cl-holo-rail-outer" points="' + pointsToStr(vOuter) + '" fill="none" stroke="var(--line-2, rgba(255,180,92,.42))" stroke-width="var(--cl-sw-rail, 1.2)" stroke-linejoin="round"/>');
      // 内层分划虚线导轨
      out.push('<polygon class="cl-holo-rail cl-holo-rail-inner" points="' + pointsToStr(vInner) + '" fill="none" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)" stroke-dasharray="6 4" stroke-linejoin="round"/>');

      // 四个切角处的科技加固 L-Bracket 护角
      var bk = 7;
      var cornerTL = 'M ' + round(cx - rw + c + bk) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx - rw + c) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy - rh + c) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy - rh + c + bk);
      var cornerTR = 'M ' + round(cx + rw - c - bk) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx + rw - c) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy - rh + c) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy - rh + c + bk);
      var cornerBR = 'M ' + round(cx + rw + 2.5) + ',' + round(cy + rh - c - bk) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy + rh - c) + ' L ' + round(cx + rw - c) + ',' + round(cy + rh + 2.5) + ' L ' + round(cx + rw - c - bk) + ',' + round(cy + rh + 2.5);
      var cornerBL = 'M ' + round(cx - rw - 2.5) + ',' + round(cy + rh - c - bk) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy + rh - c) + ' L ' + round(cx - rw + c) + ',' + round(cy + rh + 2.5) + ' L ' + round(cx - rw + c + bk) + ',' + round(cy + rh + 2.5);

      out.push('<path class="cl-holo-rail-bracket" d="' + cornerTL + ' ' + cornerTR + ' ' + cornerBR + ' ' + cornerBL + '" fill="none" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-rail, 1.2)"/>');

      // 八边形顶点科技微节点
      for (var vi = 0; vi < vOuter.length; vi++) {
        out.push('<circle class="cl-holo-rail-node" cx="' + vOuter[vi][0] + '" cy="' + vOuter[vi][1] + '" r="1.4" fill="var(--signal, #ffb45c)"/>');
      }

      // 导轨侧边校准分刻凹槽 (Notches)
      var notchL = round(cy - rh * 0.4), notchR = round(cy + rh * 0.4);
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx - rw) + '" y1="' + notchL + '" x2="' + round(cx - rw + 4) + '" y2="' + notchL + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx - rw) + '" y1="' + notchR + '" x2="' + round(cx - rw + 4) + '" y2="' + notchR + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx + rw) + '" y1="' + notchL + '" x2="' + round(cx + rw - 4) + '" y2="' + notchL + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx + rw) + '" y1="' + notchR + '" x2="' + round(cx + rw - 4) + '" y2="' + notchR + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('</g>');
    }

    // 2. 精密经纬度十字准线 (Precision Longitude-Latitude Crosshairs)
    if (showCrosshair) {
      var rCoreDead = round(R * 0.26); // 中心避让空隙
      /* R5-C §1b（准线穿轴标签）——**把两臂收进外圈标定环以内**。
       * 旧值 rwCross = 1.58R / rhCross = 1.42R，两臂都比外圈标定环（reticles[2] = 1.06R）长。
       * 本雷达的 8 个轴标签恰好占满四个正向 —— 智谋(-90°)· 意志(0°)· 情感(+90°)· 权势(180°)
       * ——于是一条「经线」和一条「纬线」各自**横穿**两个标签：
       *   · 纬线（y = cy，无 squash）在 1440 下穿过 意志 [267,146,84,36] 与 权势 [-41,146,94,36]，
       *     侵入深度各 **36.9 user px**，线在标签内部**截止**（seg=[184,304] 止于标签 x 带内），
       *     于是读作「一条横线从文字里插进去再断掉」= 评审点名的「删除线」同型
       *     （docs/atlas/REVIEW-2026-09-20.md §八；改前改后同型，非 R5-C 引入）。
       *   · 经线（x = cx，无 squash）在 智谋 [118,24,84,36] 与 情感 [113,268,94,36] 内各侵入
       *     **25.8 user px**，同样是「线插进标签再断掉」。
       * 判据（tests/radar_footer_fold_browser.py · railHits）：线段级 Liang-Barsky 裁剪。
       * 取值 1.06 不是拍脑袋：外圈标定环（下方 reticles 的最后一档）就在 1.06R，是设计里**已有**的
       * 同心锚点；标签带内沿在 |dx| ≥ 107 = 1.18R（权势半宽 47 的那一侧最紧），故 1.06R 留出
       * 10.5 user px 净空。两臂同取 1.06R（不再 1.58/1.42 不等）→ 准线正好内接于外圈标定环。
       * 门禁 railHits 的横向判据会拦住任何一次「把臂放长回去」的改动。 */
      var CROSS_ARM = 1.06;
      var rwCross = round(R * CROSS_ARM);
      var rhCross = round(R * CROSS_ARM);

      out.push('<g class="cl-holo-crosshairs">');
      // 经线 (纵向 Longitude Meridian)
      out.push('<line class="cl-holo-crosshair cl-crosshair-lng" x1="' + round(cx) + '" y1="' + round(cy - rhCross) + '" x2="' + round(cx) + '" y2="' + round(cy - rCoreDead) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-crosshair cl-crosshair-lng" x1="' + round(cx) + '" y1="' + round(cy + rCoreDead) + '" x2="' + round(cx) + '" y2="' + round(cy + rhCross) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');

      // 纬线 (横向 Latitude Parallel)
      out.push('<line class="cl-holo-crosshair cl-crosshair-lat" x1="' + round(cx - rwCross) + '" y1="' + round(cy) + '" x2="' + round(cx - rCoreDead) + '" y2="' + round(cy) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-crosshair cl-crosshair-lat" x1="' + round(cx + rCoreDead) + '" y1="' + round(cy) + '" x2="' + round(cx + rwCross) + '" y2="' + round(cy) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');

      // 经纬度精密刻度准星圆圈 (Concentric calibration rings)
      var reticles = [0.38, 0.72, 1.06];
      for (var ri = 0; ri < reticles.length; ri++) {
        var rRad = round(R * reticles[ri]);
        var rRadY = round(rRad * squash);
        var isOuterReticle = ri === reticles.length - 1;
        out.push('<ellipse class="cl-holo-reticle-ring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + rRad + '" ry="' + rRadY + '" fill="none" stroke="' + (isOuterReticle ? 'var(--line-2, rgba(255,180,92,.42))' : 'var(--line, rgba(172,156,230,.16))') + '" stroke-width="var(--cl-sw-hair, 0.6)" ' + (isOuterReticle ? 'stroke-dasharray="3 4"' : '') + '/>');
      }

      // 经纬线轴向分划微标刻度 (Graduation ticks)
      // R5-C §1b：1.25 档随准线两臂一起退掉 —— 两臂现在止于 1.06R，若仍画 1.25R 的刻度，
      // 就会出现「悬浮在准线端点之外的一段孤刻度」，且该档左右两枚（x = cx±114）正落在
      // 意志 / 权势 标签带内 6px。留 0.5 / 0.75 / 1.0 三档，全部在两臂之内。
      var tickSteps = [0.5, 0.75, 1.0];
      for (var ti = 0; ti < tickSteps.length; ti++) {
        var tr = round(R * tickSteps[ti]);
        var try_ = round(tr * squash);
        // 上下轴刻度
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - 3) + '" y1="' + round(cy - try_) + '" x2="' + round(cx + 3) + '" y2="' + round(cy - try_) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - 3) + '" y1="' + round(cy + try_) + '" x2="' + round(cx + 3) + '" y2="' + round(cy + try_) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        // 左右轴刻度
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - tr) + '" y1="' + round(cy - 3) + '" x2="' + round(cx - tr) + '" y2="' + round(cy + 3) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx + tr) + '" y1="' + round(cy - 3) + '" x2="' + round(cx + tr) + '" y2="' + round(cy + 3) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      }

      // 经纬度精密坐标文字角标
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx) + '" y="' + round(cy - rhCross - 5) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LNG 000.00° // N</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx + rwCross + 6) + '" y="' + round(cy + 2.5) + '" text-anchor="start" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LAT +090.00° // E</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx) + '" y="' + round(cy + rhCross + 13) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LNG 180.00° // S</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx - rwCross - 6) + '" y="' + round(cy + 2.5) + '" text-anchor="end" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LAT -090.00° // W</text>');
      out.push('</g>');
    }

    // 3. 微型坐标标尺 (Micro-coordinate Vernier Ruler)
    if (showRuler) {
      out.push('<g class="cl-holo-ruler">');
      var rulerY = round(cy + R * 0.96 * squash);
      var rulerSpan = round(R * 0.88);
      var rulerStartX = round(cx - rulerSpan);
      var rulerEndX = round(cx + rulerSpan);

      // 标尺基线
      out.push('<line class="cl-holo-ruler-base" x1="' + rulerStartX + '" y1="' + rulerY + '" x2="' + rulerEndX + '" y2="' + rulerY + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)" stroke-dasharray="1 2"/>');

      // 游标刻度分划
      var divisions = 16;
      var step = (rulerSpan * 2) / divisions;
      for (var di = 0; di <= divisions; di++) {
        var rx = round(rulerStartX + di * step);
        var isMajor = di % 4 === 0;
        var rLen = isMajor ? 5 : 2.5;
        out.push('<line class="cl-holo-ruler-tick" x1="' + rx + '" y1="' + rulerY + '" x2="' + rx + '" y2="' + round(rulerY + rLen) + '" stroke="' + (isMajor ? 'var(--signal, #ffb45c)' : 'var(--line, rgba(172,156,230,.16))') + '" stroke-width="var(--cl-sw-hair, 0.6)"/>');
        if (isMajor) {
          var relVal = Math.round((di - divisions / 2) * 10);
          var signStr = relVal > 0 ? '+' + relVal : relVal === 0 ? '±00' : String(relVal);
          out.push('<text class="cl-holo-ruler-num" x="' + rx + '" y="' + round(rulerY + 11) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--ink-3, #88819d)">' + signStr + '</text>');
        }
      }

      // 微型参考标尺说明
      out.push('<text class="cl-holo-ruler-meta" x="' + round(cx) + '" y="' + round(rulerY + 19) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">GRID REF: [X:' + round(cx) + ' Y:' + round(cy) + '] // VERNIER: 0.05</text>');
      out.push('</g>');
    }

    // 4. 二十八宿星位参考分划虚线环 (28 Lunar Mansions Reference Division Dashed Ring)
    if (showMansions) {
      var rMansion = round(R * 1.24);
      var rMansionY = round(rMansion * squash);

      out.push('<g class="cl-holo-mansions">');
      // 二十八宿基准虚线外环
      out.push('<ellipse class="cl-holo-mansion-ring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + rMansion + '" ry="' + rMansionY + '" fill="none" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-hair, 0.6)" stroke-dasharray="2 4"/>');
      // 二十八宿内部辅助同心环
      out.push('<ellipse class="cl-holo-mansion-subring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + round(rMansion - 4) + '" ry="' + round((rMansion - 4) * squash) + '" fill="none" stroke="var(--violet, #a688ff)" stroke-opacity="0.18" stroke-width="var(--cl-sw-hair, 0.5)" stroke-dasharray="1 6"/>');

      // 28 宿分划刻度与宿位名称
      var totalMansions = TWENTY_EIGHT_MANSIONS.length; // 28
      for (var mi = 0; mi < totalMansions; mi++) {
        var mItem = TWENTY_EIGHT_MANSIONS[mi];
        var isQuadHead = (mi % 7 === 0); // 角、斗、奎、井 四象宿首
        var theta = -Math.PI / 2 + mi * (2 * Math.PI / totalMansions);
        var cosT = Math.cos(theta);
        var sinT = Math.sin(theta);

        var rInner = isQuadHead ? rMansion - 6 : rMansion - 3;
        var rOuter = isQuadHead ? rMansion + 6 : rMansion + 3;

        var pIn = [round(cx + cosT * rInner), round(cy + sinT * rInner * squash)];
        var pOut = [round(cx + cosT * rOuter), round(cy + sinT * rOuter * squash)];

        // 径向分划线
        var strokeColor = isQuadHead ? 'var(--signal, #ffb45c)' : 'var(--line, rgba(172,156,230,.16))';
        var strokeW = isQuadHead ? 'var(--cl-sw-rail, 1.2)' : 'var(--cl-sw-hair, 0.6)';
        out.push('<line class="cl-holo-mansion-tick' + (isQuadHead ? ' quad-head' : '') + '" x1="' + pIn[0] + '" y1="' + pIn[1] + '" x2="' + pOut[0] + '" y2="' + pOut[1] + '" stroke="' + strokeColor + '" stroke-width="' + strokeW + '"/>');

        // 四象宿首节点信标
        if (isQuadHead) {
          out.push('<circle class="cl-holo-mansion-node" cx="' + pOut[0] + '" cy="' + pOut[1] + '" r="1.3" fill="var(--signal, #ffb45c)"/>');
        }

        // 宿位名称文字
        var rText = rMansion + (isQuadHead ? 13 : 10);
        var pText = [round(cx + cosT * rText), round(cy + sinT * rText * squash + 2.5)];
        var textColor = isQuadHead ? 'var(--signal, #ffb45c)' : 'var(--ink-3, #88819d)';
        out.push('<text class="cl-holo-mansion-label' + (isQuadHead ? ' quad-head' : '') + '" x="' + pText[0] + '" y="' + pText[1] + '" text-anchor="middle" font-family="var(--sans, sans-serif)" font-size="var(--cl-fs-mansion, 11px)" fill="' + textColor + '">' + esc(mItem.name) + '</text>');
      }
      out.push('</g>');
    }

    // 5. 四个方位的全息代码角标 [MK-IV / SYS-GRID]
    if (showBadges) {
      out.push('<g class="cl-holo-badges">');

      /**
       * 绘制单个科技感全息代码角标切角框
       */
      function drawBadge(bx, by, text, align) {
        var bw = 46;
        var bh = 14;
        var cut = 3.5;
        var x0 = align === 'end' ? bx - bw : align === 'middle' ? bx - bw / 2 : bx;
        var y0 = by - bh / 2;
        x0 = round(x0);
        y0 = round(y0);

        var pts = [
          [x0 + cut, y0],
          [x0 + bw - cut, y0],
          [x0 + bw, y0 + cut],
          [x0 + bw, y0 + bh - cut],
          [x0 + bw - cut, y0 + bh],
          [x0 + cut, y0 + bh],
          [x0, y0 + bh - cut],
          [x0, y0 + cut]
        ];

        var textX = round(x0 + bw / 2);
        var textY = round(y0 + bh / 2 + 2.6);

        return '<g class="cl-holo-badge" data-code="' + esc(text) + '">' +
          '<polygon class="cl-holo-badge-frame" points="' + pointsToStr(pts) + '" fill="var(--bg, #05050b)" fill-opacity="0.82" stroke="var(--line-2, rgba(255,180,92,.42))" stroke-width="var(--cl-sw-hair, 0.7)"/>' +
          '<line class="cl-holo-badge-accent" x1="' + (x0 + 2) + '" y1="' + (y0 + 2) + '" x2="' + (x0 + cut + 2) + '" y2="' + (y0 + 2) + '" stroke="var(--signal, #ffb45c)" stroke-width="var(--cl-sw-hair, 0.7)"/>' +
          '<text class="cl-holo-badge-code" x="' + textX + '" y="' + textY + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-badge, 10px)" fill="var(--signal, #ffb45c)" letter-spacing="var(--cl-ls-mono, 0.08em)">' + esc(text) + '</text>' +
          '</g>';
      }

      var bDistW = round(R * 1.54);
      var bDistH = round(R * 1.38);

      // 4 个方位角标，严格包含 [MK-IV] 与 [SYS-GRID]
      // 12 点方位 (North): [SYS-GRID]
      out.push(drawBadge(cx, cy - bDistH - 8, '[SYS-GRID]', 'middle'));
      // 3 点方位 (East): [MK-IV]
      out.push(drawBadge(cx + bDistW + 6, cy, '[MK-IV]', 'start'));
      // 6 点方位 (South): [SYS-GRID]
      out.push(drawBadge(cx, cy + bDistH + 18, '[SYS-GRID]', 'middle'));
      // 9 点方位 (West): [MK-IV]
      out.push(drawBadge(cx - bDistW - 6, cy, '[MK-IV]', 'end'));

      // 4 个科技切角角落全息角标
      var cOffsetW = round(bDistW * 0.94);
      var cOffsetH = round(bDistH * 0.94);
      out.push(drawBadge(cx - cOffsetW, cy - cOffsetH, '[MK-IV]', 'end'));
      out.push(drawBadge(cx + cOffsetW, cy - cOffsetH, '[SYS-GRID]', 'start'));
      out.push(drawBadge(cx - cOffsetW, cy + cOffsetH, '[SYS-GRID]', 'end'));
      out.push(drawBadge(cx + cOffsetW, cy + cOffsetH, '[MK-IV]', 'start'));

      out.push('</g>');
    }

    out.push('</g>');

    return sanitizeSVG(out.join(''));
  }

  /**
   * 解析基准数据并生成归一化顶点坐标集合
   * @param {Array|Object|string} benchPoints 基准点集或分值集合
   * @param {Object} opt 几何配置
   * @returns {Array<[number, number]>} 顶点坐标数组
   */
  function parseBenchmarkVertices(benchPoints, opt) {
    opt = opt || {};
    var cx = safeNum(opt.cx, 160);
    var cy = safeNum(opt.cy, 164);
    var R = Math.max(10, safeNum(opt.R, 91.2));
    var squash = Math.max(0.1, safeNum(opt.squash, 0.9));

    if (!benchPoints) return [];

    // 情况 1: 字符串格式 "x1,y1 x2,y2 ..." 或 "x1 y1, x2 y2"
    if (typeof benchPoints === 'string') {
      var pairs = benchPoints.trim().split(/[\s,]+/);
      var coords = [];
      for (var si = 0; si < pairs.length - 1; si += 2) {
        var px = Number(pairs[si]);
        var py = Number(pairs[si + 1]);
        if (isFinite(px) && isFinite(py)) {
          coords.push([round(px), round(py)]);
        }
      }
      return coords;
    }

    // 情况 2: 数组格式
    if (Array.isArray(benchPoints)) {
      if (!benchPoints.length) return [];
      // 2a. 二维坐标数组 [[x, y], [x, y], ...]
      if (Array.isArray(benchPoints[0])) {
        return benchPoints.map(function (p) {
          return [round(p[0]), round(p[1])];
        }).filter(function (p) {
          return isFinite(p[0]) && isFinite(p[1]);
        });
      }
      // 2b. 对象点集 [{x, y}, {x, y}, ...]
      if (typeof benchPoints[0] === 'object' && benchPoints[0] !== null && 'x' in benchPoints[0] && 'y' in benchPoints[0]) {
        return benchPoints.map(function (p) {
          return [round(p.x), round(p.y)];
        }).filter(function (p) {
          return isFinite(p[0]) && isFinite(p[1]);
        });
      }
      // 2c. 分值数值数组 [s0, s1, ..., s7] (0..100)
      if (typeof benchPoints[0] === 'number') {
        var ptsFromScores = [];
        var numKeys = KEYS.length;
        for (var bi = 0; bi < numKeys; bi++) {
          var sc = safeNum(benchPoints[bi], 50);
          var ang = -Math.PI / 2 + bi * (2 * Math.PI / numKeys);
          var rScale = R * Math.max(0.04, Math.min(100, sc) / 100);
          ptsFromScores.push([
            round(cx + Math.cos(ang) * rScale),
            round(cy + Math.sin(ang) * rScale * squash)
          ]);
        }
        return ptsFromScores;
      }
    }

    // 情况 3: 键值对象 { 智谋: 50, 实力: 60, ... }
    if (typeof benchPoints === 'object') {
      var ptsFromObj = [];
      var nKeys = KEYS.length;
      for (var ki = 0; ki < nKeys; ki++) {
        var kName = KEYS[ki];
        var val = safeNum(benchPoints[kName] != null ? benchPoints[kName] : (benchPoints[EN[kName]] != null ? benchPoints[EN[kName]] : 50), 50);
        var angle = -Math.PI / 2 + ki * (2 * Math.PI / nKeys);
        var rVal = R * Math.max(0.04, Math.min(100, val) / 100);
        ptsFromObj.push([
          round(cx + Math.cos(angle) * rVal),
          round(cy + Math.sin(angle) * rVal * squash)
        ]);
      }
      return ptsFromObj;
    }

    return [];
  }

  /**
   * 生成全书基准幽灵线 SVG 标签（带 dasharray 虚线与半透明发光）
   * @param {Array|Object|string} benchPoints 全书基准点集或分值集合
   * @param {Object} opt 配置项
   * @returns {string} SVG 片段
   */
  function renderGhostPolygon(benchPoints, opt) {
    opt = opt || {};
    var vertices = parseBenchmarkVertices(benchPoints, opt);

    // 点数不足以构成闭合多边形时安全返回空字符串，不产生破损元素
    if (!vertices || vertices.length < 3) {
      return '';
    }

    var ptsStr = pointsToStr(vertices);
    var showNodes = opt.showNodes !== false;
    var showLabel = !!opt.showLabel;
    var labelText = opt.labelText || 'BENCHMARK // 全书基准';

    var out = [];
    out.push('<g class="cl-ghost-layer" aria-label="全书基准幽灵轮廓" data-bench="true">');

    // 1. 半透明发光底膜 (Glow Outline)
    out.push('<polygon class="cl-ghost-glow" points="' + ptsStr + '" fill="none" stroke="var(--violet, #a688ff)" stroke-width="var(--cl-sw-glow, 3)" stroke-opacity="0.28" stroke-dasharray="var(--cl-ghost-dash, 4 3)" stroke-linejoin="round"/>');

    // 2. 幽灵内部半透明微填充 (Semi-transparent Fill)
    out.push('<polygon class="cl-ghost-fill" points="' + ptsStr + '" fill="var(--violet, #a688ff)" fill-opacity="0.06"/>');

    // 3. 核心基准虚线轮廓 (Core Dasharray Contour)
    out.push('<polygon class="cl-ghost-polygon" points="' + ptsStr + '" fill="none" stroke="var(--violet, #a688ff)" stroke-width="var(--cl-sw-ghost, 1.4)" stroke-dasharray="var(--cl-ghost-dash, 4 3)" stroke-linejoin="round"/>');

    // 4. 顶点微型信标 (Node Markers)
    if (showNodes) {
      for (var ni = 0; ni < vertices.length; ni++) {
        var node = vertices[ni];
        out.push('<circle class="cl-ghost-node" cx="' + node[0] + '" cy="' + node[1] + '" r="1.8" fill="var(--violet, #a688ff)" stroke="var(--bg, #05050b)" stroke-width="0.8"/>');
      }
    }

    // R6 · 命运差值桥与冷色薄纱/暖色余烬 (本人顶点与幽灵顶点连线桥与 Δ 标注)
    if (opt.heroPoints && opt.heroPoints.length === vertices.length) {
      out.push('<g class="rd-diff-mesh" aria-label="命运差值桥">');
      for (var bi = 0; bi < vertices.length; bi++) {
        var hp = opt.heroPoints[bi];
        var gp = vertices[bi];
        var hScore = (opt.scores && opt.scores[bi] != null) ? opt.scores[bi] : 50;
        var bScore = (opt.benchScores && opt.benchScores[bi] != null) ? (typeof opt.benchScores[bi] === 'object' ? opt.benchScores[bi].score : opt.benchScores[bi]) : 50;
        var delta = Math.round(hScore - bScore);
        var isSurplus = delta >= 0;
        var bridgeClass = 'rd-diff-bridge ' + (isSurplus ? 'surplus' : 'deficit');
        // 差值连线桥
        out.push('<line class="' + bridgeClass + '" x1="' + hp[0] + '" y1="' + hp[1] + '" x2="' + gp[0] + '" y2="' + gp[1] + '"/>');
        // Δ 差值标注（在连线桥中点）
        var mx = round((hp[0] + gp[0]) / 2);
        var my = round((hp[1] + gp[1]) / 2);
        var deltaText = (isSurplus ? '+' : '') + delta;
        out.push('<text class="rd-diff-delta ' + (isSurplus ? 'surplus' : 'deficit') + '" x="' + mx + '" y="' + my + '" text-anchor="middle" dominant-baseline="central">' + deltaText + '</text>');
      }
      out.push('</g>');
    }

    // 5. 可选标签标示 (Benchmark Label)
    if (showLabel && vertices.length > 0) {
      var topNode = vertices[0];
      out.push('<text class="cl-ghost-label" x="' + topNode[0] + '" y="' + round(topNode[1] - 6) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--violet, #a688ff)" letter-spacing="var(--cl-ls-mono, 0.08em)">' + esc(labelText) + '</text>');
    }

    out.push('</g>');

    return sanitizeSVG(out.join(''));
  }

  /**
   * 计算八维分值在指定视口下的多边形顶点坐标 (辅助导出供测试与其它模块复用)
   */
  function computePoints(scores, cx, cy, R, squash) {
    cx = safeNum(cx, 160);
    cy = safeNum(cy, 164);
    R = Math.max(10, safeNum(R, 91.2));
    squash = Math.max(0.1, safeNum(squash, 0.9));

    var numAxes = KEYS.length;
    var result = [];
    for (var i = 0; i < numAxes; i++) {
      var s = (Array.isArray(scores) ? scores[i] : (scores && typeof scores === 'object' ? (scores[KEYS[i]] != null ? scores[KEYS[i]] : scores[EN[KEYS[i]]]) : 0));
      var sc = safeNum(s, 0);
      var a = -Math.PI / 2 + i * (2 * Math.PI / numAxes);
      var r = R * Math.max(0.04, Math.min(100, sc) / 100);
      result.push([
        round(cx + Math.cos(a) * r),
        round(cy + Math.sin(a) * r * squash)
      ]);
    }
    return result;
  }

  /**
   * 计算雷达全息外框的理论包围盒尺寸
   */
  function computeFrameBounds(cx, cy, R, opt) {
    cx = safeNum(cx, 160);
    cy = safeNum(cy, 164);
    R = Math.max(10, safeNum(R, 91.2));
    var squash = Math.max(0.1, safeNum(opt && opt.squash, 0.9));
    var rw = round(R * 1.58);
    var rh = round(R * 1.42 * squash);
    return {
      x: round(cx - rw),
      y: round(cy - rh),
      width: round(rw * 2),
      height: round(rh * 2)
    };
  }

  /* ════════════════════════════════════════════════════════════════════════
   * R5-E · 雷达外框竖向导轨穿斜向轴标签 —— 方案③分段导轨（主控裁定，2026-09-21）
   * ----------------------------------------------------------------------
   * 背景：外框左右竖边（.cl-holo-rail-outer/-inner，及四角 .cl-holo-rail-bracket
   * 的短竖边加固桩）是两条贯穿整个外框高度的直线，而 8 个轴标签里除智谋(顶)/情感(底)
   * 外的 6 个（实力/意志/魅力/野心/权势/道义）都落在左右两侧——尤其意志(0°)/权势(180°)
   * 两个基准方向的标签本来就贴着竖边中点。经实测（tests/radar_footer_fold_browser.py
   * railHits），这 6 个标签的芯片矩形被竖边整条穿过，pen = 36（= 整条芯片高），三视口
   * 同型（外框是 SVG 内部坐标系里的固定几何，不随视口像素缩放改变，所以 1440/820/390
   * 度数完全一致）。同一条判据下 .cl-holo-mansions（二十八宿分划环）里少数刻度线也
   * 会薄薄蹭进标签矩形边角（pen 5.8~11.9，非本条注释重点但同属本文件、门禁一并收紧后
   * 必须一起关掉，见下方 foldMansionTicks）。
   *
   * 主控否决的两条路：
   *   ①放宽外框 rw——方屏视口下 SVG `meet` 缩放会把八维多边形本体再缩 20%+，牺牲主体读图。
   *   ②改标签布局——8 个轴标签的角度/半径是"读懂雷达"的几何契约，动它等于破坏对齐。
   * 裁定走③：导轨按标签带分段——运行时读取 6 个斜向标签芯片的真实 bbox（只读 DOM，
   * 不用固定角度公式猜位置，因为 chipX/chipY 会被 radar.js 按可用宽度做二次夹取），
   * 在每个标签带上下各留 6px 净空处断开，退化成"角括 + 中段"的分段导轨；断口两端点
   * 缀 1px 圆点收尾（复用既有 .cl-holo-rail-node 用的 --signal 令牌），保证断口不是
   * 悬空的截断线头，仍读作"一个外框"。若单侧标签带覆盖率 > 70%（見 verticalRailPlan），
   * 分段会碎成看不出"轨"的短线头，索性只保留首尾各 18% 高的两截，退化成视觉上的
   * 双角括——这是 ledger 里明写的兜底分支，本机实测三视口覆盖率都在 ~56%，未触发，
   * 但按纪律实现，不是纸面条款。
   *
   * 为什么在这里而不是 renderFrameSVG 内联分段：renderFrameSVG 生成外框时，radar.js
   * 还没跑到生成 6 个轴标签芯片的那段循环（chipX/chipY depends on this axis's own
   * anchor/room 计算，在外框之后才 push 进 out 数组），所以拍板几何的那一刻标签在哪
   * 根本不存在。真正可读的数据要等宿主一次性 `host.innerHTML = out.join('')` 落地、
   * 外框和芯片同时进了 DOM 之后才有——于是这里用 MutationObserver 等这一刻，再对已经
   * 在 DOM 里的 `<polygon>`/`<path>` 做手术，而不是让 radar.js（不归本单元所有）多传一份
   * 提前算好的坐标。
   * ════════════════════════════════════════════════════════════════════════ */

  /** 合并一组 [lo,hi] 区间（假定已按 lo 升序或先排序） */
  function mergeIntervals(list) {
    if (!list.length) return [];
    var s = list.slice().sort(function (a, b) { return a[0] - b[0]; });
    var out = [s[0].slice()];
    for (var i = 1; i < s.length; i++) {
      var last = out[out.length - 1];
      if (s[i][0] <= last[1] + 0.01) last[1] = Math.max(last[1], s[i][1]);
      else out.push(s[i].slice());
    }
    return out;
  }

  /** [lo,hi] 减去一组已合并区间后剩下的子区间（长度 ≤0.5 的碎屑丢弃） */
  function complementIntervals(merged, lo, hi) {
    var out = [];
    var cur = lo;
    for (var i = 0; i < merged.length; i++) {
      var b = merged[i];
      if (b[0] > cur) out.push([cur, Math.min(b[0], hi)]);
      cur = Math.max(cur, b[1]);
      if (cur >= hi) break;
    }
    if (cur < hi) out.push([cur, hi]);
    return out.filter(function (seg) { return seg[1] - seg[0] > 0.5; });
  }

  /**
   * 给定一侧（左/右）标签芯片的 y 波段，规划该侧竖边应保留的线段与断口收尾点。
   * bands: [[y0,y1], ...] 芯片矩形的原始 y 范围（未加净空）。
   */
  function verticalRailPlan(edgeY0, edgeY1, bands, pad) {
    var clipped = bands.map(function (b) {
      return [Math.max(edgeY0, b[0] - pad), Math.min(edgeY1, b[1] + pad)];
    }).filter(function (b) { return b[1] > b[0]; });
    var merged = mergeIntervals(clipped);
    var covered = merged.reduce(function (s, b) { return s + (b[1] - b[0]); }, 0);
    var L = edgeY1 - edgeY0;
    var coverage = L > 0 ? covered / L : 0;
    if (coverage > 0.7) {
      // 覆盖率 >70%：分段会碎成认不出"轨"的短线头，退化为上下各 18% 高的双角括。
      var stub = L * 0.18;
      return { coverage: coverage, segs: [[edgeY0, edgeY0 + stub], [edgeY1 - stub, edgeY1]], caps: [edgeY0 + stub, edgeY1 - stub] };
    }
    var segs = complementIntervals(merged, edgeY0, edgeY1);
    var caps = [];
    segs.forEach(function (s) {
      if (s[0] > edgeY0 + 0.5) caps.push(s[0]);
      if (s[1] < edgeY1 - 0.5) caps.push(s[1]);
    });
    return { coverage: coverage, segs: segs, caps: caps };
  }

  function railBandsForSide(rects, side, cxVal) {
    return rects.filter(function (r) {
      var mid = r.x + r.width / 2;
      return side === 'left' ? mid < cxVal : mid > cxVal;
    }).map(function (r) { return [r.y, r.y + r.height]; });
  }

  function svgEl(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) { if (attrs.hasOwnProperty(k) && attrs[k] != null) el.setAttribute(k, attrs[k]); }
    return el;
  }

  /**
   * 用分段结果重建一个外/内导轨多边形：上/下两段（含切角）保持整条不动，
   * 左右竖边替换成 verticalRailPlan 算出的子线段 + 断口收尾点。
   */
  function replaceOctagonWithFold(el, parentG, cx, cy, rw, rh, c, bandsLeft, bandsRight, pad, cls, strokeAttrs, capColor) {
    var edgeY0 = cy - rh + c, edgeY1 = cy + rh - c;
    var leftPlan = verticalRailPlan(edgeY0, edgeY1, bandsLeft, pad);
    var rightPlan = verticalRailPlan(edgeY0, edgeY1, bandsRight, pad);

    var frag = svgEl('g', { 'class': cls + '-folded' });
    var topPts = [[cx - rw, edgeY0], [cx - rw + c, cy - rh], [cx + rw - c, cy - rh], [cx + rw, edgeY0]];
    var bottomPts = [[cx + rw, edgeY1], [cx + rw - c, cy + rh], [cx - rw + c, cy + rh], [cx - rw, edgeY1]];
    var pAttrs = {};
    for (var k in strokeAttrs) if (strokeAttrs.hasOwnProperty(k)) pAttrs[k] = strokeAttrs[k];

    function addOpenPath(pts, extraCls) {
      // 必须用 <path> 的 M/L（不闭合），不能用 <polyline points=...>：
      // tests/radar_footer_fold_browser.py 的线段枚举对 `polygon, polyline` 一视同仁地
      // 按 `(i+1) % length` 取相邻点（专为闭合多边形写的），会把 <polyline> 的末点自动
      // 连回首点，凭空生成一条贯穿整个外框的假横线（实测正是这条线把「智谋/情感」两个
      // 早被 R5-C 挪开的标签重新命中）。<path> 分支门禁按 M 分段、不做首尾闭合，同 d
      // 属性写法与既有 .cl-holo-rail-bracket 一致，避免这枚假线。
      var a = {}; for (var k2 in pAttrs) a[k2] = pAttrs[k2];
      a['class'] = cls + ' ' + extraCls;
      var d = 'M ' + round(pts[0][0]) + ',' + round(pts[0][1]);
      for (var pi = 1; pi < pts.length; pi++) d += ' L ' + round(pts[pi][0]) + ',' + round(pts[pi][1]);
      a.d = d;
      frag.appendChild(svgEl('path', a));
    }
    function addVSeg(x, y0, y1, extraCls) {
      var a = {}; for (var k3 in pAttrs) a[k3] = pAttrs[k3];
      a['class'] = cls + ' ' + extraCls; a.x1 = round(x); a.y1 = round(y0); a.x2 = round(x); a.y2 = round(y1);
      frag.appendChild(svgEl('line', a));
    }
    function addCap(x, y) {
      frag.appendChild(svgEl('circle', { 'class': 'cl-holo-rail-cap', cx: round(x), cy: round(y), r: 0.6, fill: capColor }));
    }

    addOpenPath(topPts, 'cl-holo-rail-top');
    addOpenPath(bottomPts, 'cl-holo-rail-bottom');
    leftPlan.segs.forEach(function (s) { addVSeg(cx - rw, s[0], s[1], 'cl-holo-rail-vseg cl-holo-rail-vseg-l'); });
    rightPlan.segs.forEach(function (s) { addVSeg(cx + rw, s[0], s[1], 'cl-holo-rail-vseg cl-holo-rail-vseg-r'); });
    leftPlan.caps.forEach(function (y) { addCap(cx - rw, y); });
    rightPlan.caps.forEach(function (y) { addCap(cx + rw, y); });

    parentG.replaceChild(frag, el);
    return { left: leftPlan, right: rightPlan };
  }

  function bandOverlaps(y0, y1, bands, pad) {
    for (var i = 0; i < bands.length; i++) {
      if (bands[i][1] + pad > y0 && bands[i][0] - pad < y1) return true;
    }
    return false;
  }

  /**
   * 四角 L 型加固桩（.cl-holo-rail-bracket）里，紧贴左右竖边的那一小截（长 7）
   * 与主竖边共用同一段 y 范围；主竖边在那段被断开时，这一小截也要同步断开，
   * 否则会出现"主轨没了、旁边孤零零一小截桩还插在标签里"的破绽。
   */
  function foldBracket(bracketEl, railsG, cx, cy, rgeo, bandsLeft, bandsRight, pad) {
    var rw = rgeo.rw, rh = rgeo.rh, c = rgeo.c, bk = 7;
    var corners = [
      { p: [[cx - rw + c + bk, cy - rh - 2.5], [cx - rw + c, cy - rh - 2.5], [cx - rw - 2.5, cy - rh + c], [cx - rw - 2.5, cy - rh + c + bk]], stub: 'last', side: 'left' },
      { p: [[cx + rw - c - bk, cy - rh - 2.5], [cx + rw - c, cy - rh - 2.5], [cx + rw + 2.5, cy - rh + c], [cx + rw + 2.5, cy - rh + c + bk]], stub: 'last', side: 'right' },
      { p: [[cx + rw + 2.5, cy + rh - c - bk], [cx + rw + 2.5, cy + rh - c], [cx + rw - c, cy + rh + 2.5], [cx + rw - c - bk, cy + rh + 2.5]], stub: 'first', side: 'right' },
      { p: [[cx - rw - 2.5, cy + rh - c - bk], [cx - rw - 2.5, cy + rh - c], [cx - rw + c, cy + rh + 2.5], [cx - rw + c + bk, cy + rh + 2.5]], stub: 'first', side: 'left' }
    ];
    var d = '';
    var caps = [];
    corners.forEach(function (co) {
      var pts = co.p;
      var bands = co.side === 'left' ? bandsLeft : bandsRight;
      var stubA = co.stub === 'last' ? pts[2] : pts[0];
      var stubB = co.stub === 'last' ? pts[3] : pts[1];
      var y0 = Math.min(stubA[1], stubB[1]), y1 = Math.max(stubA[1], stubB[1]);
      var intrudes = bandOverlaps(y0, y1, bands, pad);
      var kept = intrudes ? (co.stub === 'last' ? pts.slice(0, 3) : pts.slice(1, 4)) : pts;
      d += 'M ' + round(kept[0][0]) + ',' + round(kept[0][1]);
      for (var i = 1; i < kept.length; i++) d += ' L ' + round(kept[i][0]) + ',' + round(kept[i][1]);
      d += ' ';
      if (intrudes) caps.push(stubA);
    });
    bracketEl.setAttribute('d', d.trim());
    caps.forEach(function (pt) {
      railsG.appendChild(svgEl('circle', { 'class': 'cl-holo-rail-cap', cx: round(pt[0]), cy: round(pt[1]), r: 0.6, fill: 'var(--mint, #7af0c8)' }));
    });
  }

  /** 线段对一组矩形（各自 padding 后）做区间裁剪，返回离 (bx,by) 最近的存活子段，或 null（整段被吃掉） */
  function trimSegmentAgainstRects(ax, ay, bx, by, rects, pad) {
    var dx = bx - ax, dy = by - ay;
    var intervals = [];
    for (var i = 0; i < rects.length; i++) {
      var r = rects[i];
      var rx0 = r.x - pad, ry0 = r.y - pad, rx1 = r.x + r.width + pad, ry1 = r.y + r.height + pad;
      var t0 = 0, t1 = 1, ok = true;
      function clip(p, q) {
        if (Math.abs(p) < 1e-9) return q >= 0;
        var t = q / p;
        if (p < 0) { if (t > t1) return false; if (t > t0) t0 = t; }
        else { if (t < t0) return false; if (t < t1) t1 = t; }
        return true;
      }
      ok = clip(-dx, ax - rx0) && clip(dx, rx1 - ax) && clip(-dy, ay - ry0) && clip(dy, ry1 - ay);
      if (ok && t0 < t1) intervals.push([Math.max(0, t0), Math.min(1, t1)]);
    }
    if (!intervals.length) return { x1: ax, y1: ay, x2: bx, y2: by };
    var merged = mergeIntervals(intervals);
    var survivors = complementIntervals(merged, 0, 1);
    if (!survivors.length) return null;
    var best = survivors[survivors.length - 1]; // 优先保外端（宿首节点画在外端）
    return { x1: round(ax + dx * best[0]), y1: round(ay + dy * best[0]), x2: round(ax + dx * best[1]), y2: round(ay + dy * best[1]) };
  }

  /** 二十八宿分划刻度：凡蹭进任一标签芯片矩形的刻度线，向内端裁短（保外端宿首节点不动）；整条落进矩形则隐藏。 */
  function foldMansionTicks(mansionsG, rects) {
    var ticks = mansionsG.querySelectorAll('.cl-holo-mansion-tick');
    var PAD = 2;
    for (var i = 0; i < ticks.length; i++) {
      var t = ticks[i];
      var x1 = +t.getAttribute('x1'), y1 = +t.getAttribute('y1');
      var x2 = +t.getAttribute('x2'), y2 = +t.getAttribute('y2');
      var node = t.nextElementSibling;
      var hasNode = node && node.classList && node.classList.contains('cl-holo-mansion-node');
      var trimmed = trimSegmentAgainstRects(x1, y1, x2, y2, rects, PAD);
      if (!trimmed) {
        /* `display:none`只影响可见性，不影响坐标——门禁 railHits 只读 x1/y1/x2/y2 几何
         * 属性算穿透，不看 CSS 可见性，隐藏了也测得到「穿标签」。整条落进芯片矩形的宿位
         * 刻度必须真正从 DOM 里摘掉，不能只藏起来。 */
        if (hasNode && node.parentNode) node.parentNode.removeChild(node);
        if (t.parentNode) t.parentNode.removeChild(t);
        continue;
      }
      if (hasNode && (trimmed.x2 !== x2 || trimmed.y2 !== y2)) {
        node.setAttribute('cx', trimmed.x2);
        node.setAttribute('cy', trimmed.y2);
      }
      t.setAttribute('x1', trimmed.x1); t.setAttribute('y1', trimmed.y1);
      t.setAttribute('x2', trimmed.x2); t.setAttribute('y2', trimmed.y2);
    }
  }

  /** 对单个已挂载的 .cl-holo-frame 做一次分段折算（幂等，靠 data-r5e-folded 防重复） */
  function foldOneFrame(hf) {
    if (!hf || hf.getAttribute('data-r5e-folded') === '1') return;
    var svg = hf.ownerSVGElement || (hf.closest && hf.closest('svg'));
    if (!svg) return;
    var railsG = hf.querySelector('.cl-holo-rails');
    var mansionsG = hf.querySelector('.cl-holo-mansions');
    if (!railsG && !mansionsG) return;

    var cx = safeNum(hf.getAttribute('data-cx'), 0);
    var cy = safeNum(hf.getAttribute('data-cy'), 0);
    var R = safeNum(hf.getAttribute('data-r'), 0);
    if (!R) return;

    var chipEls = svg.querySelectorAll('.rd-lab rect.rd-chip');
    if (!chipEls.length) return; // 标签还没落地（不应发生，见上方大注释），下次 mutation 再试
    var rects = [];
    for (var i = 0; i < chipEls.length; i++) {
      try {
        var bb = chipEls[i].getBBox();
        rects.push({ x: bb.x, y: bb.y, width: bb.width, height: bb.height });
      } catch (e) { /* 未挂载/隐藏时 getBBox 可能抛错，安全跳过这一枚 */ }
    }
    hf.setAttribute('data-r5e-folded', '1');
    if (!rects.length) return;

    if (railsG) {
      var rgeo = railGeometry(R);
      var pad = 6;
      var bandsLeft = railBandsForSide(rects, 'left', cx);
      var bandsRight = railBandsForSide(rects, 'right', cx);
      var outerEl = railsG.querySelector('.cl-holo-rail-outer');
      var innerEl = railsG.querySelector('.cl-holo-rail-inner');
      var bracketEl = railsG.querySelector('.cl-holo-rail-bracket');
      if (outerEl) {
        replaceOctagonWithFold(outerEl, railsG, cx, cy, rgeo.rw, rgeo.rh, rgeo.c, bandsLeft, bandsRight, pad,
          'cl-holo-rail cl-holo-rail-outer',
          { fill: 'none', stroke: 'var(--line-2, rgba(255,180,92,.42))', 'stroke-width': 'var(--cl-sw-rail, 1.2)', 'stroke-linejoin': 'round' },
          'var(--signal, #ffb45c)');
      }
      if (innerEl) {
        replaceOctagonWithFold(innerEl, railsG, cx, cy, rgeo.rwIn, rgeo.rhIn, rgeo.cIn, bandsLeft, bandsRight, pad,
          'cl-holo-rail cl-holo-rail-inner',
          { fill: 'none', stroke: 'var(--line, rgba(172,156,230,.16))', 'stroke-width': 'var(--cl-sw-thin, 0.8)', 'stroke-dasharray': '6 4', 'stroke-linejoin': 'round' },
          'var(--mint, #7af0c8)');
      }
      if (bracketEl) foldBracket(bracketEl, railsG, cx, cy, rgeo, bandsLeft, bandsRight, pad);
    }
    if (mansionsG) foldMansionTicks(mansionsG, rects);
  }

  function foldAllFrames(root) {
    var scope = root || (typeof document !== 'undefined' ? document : null);
    if (!scope || typeof scope.querySelectorAll !== 'function') return 0;
    var frames = scope.querySelectorAll('.cl-holo-frame:not([data-r5e-folded])');
    var n = 0;
    for (var i = 0; i < frames.length; i++) {
      try { foldOneFrame(frames[i]); n++; } catch (e) { /* 单帧折算失败不拖垮整页 */ }
    }
    return n;
  }

  // 自装载：浏览器环境下监听 DOM，外框 + 标签芯片一次性 innerHTML 落地后立即折算。
  // 不依赖 radar.js 主动调用（该文件不归本单元所有，不能要求它接一次新调用）。
  if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
    (function installR5EFold() {
      var scheduled = false;
      var observer = new MutationObserver(function () {
        if (scheduled) return;
        // No pending radar frame: unrelated sky/player mutations need no fold frame.
        if (!document.querySelector(".cl-holo-frame:not([data-r5e-folded])")) return;
        scheduled = true;
        var run = function () { scheduled = false; foldAllFrames(document); };
        if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run); else run();
      });
      var install = function () {
        observer.observe(document.documentElement, { childList: true, subtree: true });
        foldAllFrames(document);
      };
      if (document.documentElement) install();
      else document.addEventListener('DOMContentLoaded', install);
    })();
  }

  // 挂载暴露纯对象 API (带完备的安全防防御性入参校验)
  var CLRadarHoloFrame = {
    KEYS: KEYS,
    EN: EN,
    TWENTY_EIGHT_MANSIONS: TWENTY_EIGHT_MANSIONS,
    renderFrameSVG: renderFrameSVG,
    renderGhostPolygon: renderGhostPolygon,
    computePoints: computePoints,
    computeFrameBounds: computeFrameBounds,
    parseBenchmarkVertices: parseBenchmarkVertices,
    safeNum: safeNum,
    round: round,
    sanitizeSVG: sanitizeSVG,
    railGeometry: railGeometry,
    foldAllFrames: foldAllFrames
  };

  if (typeof window !== 'undefined') {
    window.CLRadarHoloFrame = CLRadarHoloFrame;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = CLRadarHoloFrame;
  }
  if (typeof global !== 'undefined') {
    global.CLRadarHoloFrame = CLRadarHoloFrame;
  }

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
