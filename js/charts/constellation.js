/* Castline · constellation.js — 星座布局引擎（纯数学，不依赖 three.js）· v19.2
 * 规则（跨题材通用）：
 *   星座 = 阵营（camp）：角色所属势力 / 团体 / 家庭 / 公司 / 派系；无法归类者进「散星」带
 *   方位 = 立场（stance）：主角方居中 · 盟友在左弧（与时间列同侧）· 中立在上弧 · 摇摆在下弧 · 对立在右弧；越对立越远
 *   星等 = 咖位（tier 0-4）：星体大小 / 亮度 / 标签字级；长尾（tier 4）退到本星座外围的暗晕
 *   连线 = 关系：阵营内关系 = 星座图形（明线实线 / 暗线虚线），孤星用引导线接到最近的亮星保证图形连通
 * 输出全部是确定性的（同一份图谱两次布局完全一致）。
 */
(function () {
  'use strict';
  var GA = 2.399963229728653;                 // 黄金角
  var FIELD = '散星';
  var STANCES = ['主角方', '盟友', '中立', '摇摆', '对立', ''];
  /* 阵营色唯一真相 = js/palette.js 的 CLPalette.campHex()（星渊宪法 C1）。
   * 下方字面量只是回落副本：CLPalette 缺失时兜底，绝不让星体上色变黑。 */
  var COLOR = { 主角方: 0xffd27a, 盟友: 0xf6dfa4, 中立: 0xcbbcf0, 摇摆: 0xffa07a, 对立: 0xff5d73, '': 0x8d84a8 };
  if (window.CLPalette && window.CLPalette.campMap) COLOR = window.CLPalette.campMap();
  // 扇区（弧度，数学坐标：0 = 右，逆时针为正；屏幕 y 向上）
  var SECTOR = { 盟友: [Math.PI * 0.64, Math.PI * 1.36], 对立: [-Math.PI * 0.36, Math.PI * 0.36], 中立: [Math.PI * 0.30, Math.PI * 0.70], 摇摆: [Math.PI * 1.30, Math.PI * 1.70], '': [Math.PI * 1.02, Math.PI * 1.98] };
  var DIST = { 主角方: 0, 盟友: 0.95, 中立: 1.10, 摇摆: 1.16, 对立: 1.28, '': 1.40 };
  var MIN_D = [66, 54, 42, 34, 18];           // 同星座内成员最小间距（按星等）
  var SPREAD = 1;                             // 小卷本放大系数：人少时星座撑开，别挤成一团（layout 按总人数设定）
  var PAD = 58;                               // 星座之间的最小空隙
  var ASPECT_Y = 0.80;                        // 天球纵向压缩（屏幕比宽高）

  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function rnd(seed) { var x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; } return h; }
  function normStance(s) { s = String(s || ''); return STANCES.indexOf(s) >= 0 ? s : ''; }

  /** 分组：按 c.camp（缺省 → 散星），阵营立场取 graph.camps 里的定义，否则成员多数 */
  function groupCamps(chars, campDefs) {
    var by = {}, order = [], defs = {};
    (campDefs || []).forEach(function (d) { if (d && d.name) defs[d.name] = d; });
    chars.forEach(function (c, i) {
      var nm = String(c.camp || '').trim() || FIELD;
      if (!by[nm]) { by[nm] = { name: nm, members: [], stance: normStance(defs[nm] && defs[nm].stance), brief: defs[nm] && defs[nm].brief || '', w: 0 }; order.push(nm); }
      by[nm].members.push(i);
    });
    return order.map(function (k) { return by[k]; });
  }

  /**
   * layout(chars, rels, campDefs, tierOf, weightOf) →
   *   { camps:[{name, stance, brief, members[], core[], tail[], cx, cy, cz, r, lead, color}], pos:[{x,y,z}], halfW, halfH, guides:[[i,j]] }
   * chars: 图谱角色数组；rels: 关系数组（a/b 名）；tierOf(c) 0-4；weightOf(c) 数值权重
   */
  function layout(chars, rels, campDefs, tierOf, weightOf) {
    var n = chars.length, idx = {}, i, j, k;
    SPREAD = n <= 12 ? 1.9 : n <= 26 ? 1.5 : n <= 80 ? 1.2 : 1;
    chars.forEach(function (c, q) { idx[c.name] = q; });
    var camps = groupCamps(chars, campDefs);
    var tier = chars.map(tierOf), w = chars.map(weightOf);
    // 阵营权重与立场
    camps.forEach(function (cp) {
      cp.members.sort(function (a, b) { return w[b] - w[a]; });
      cp.core = cp.members.filter(function (q) { return tier[q] < 4; });
      cp.tail = cp.members.filter(function (q) { return tier[q] >= 4; });
      cp.w = cp.core.reduce(function (s, q) { return s + w[q]; }, 0) + cp.tail.length * 0.5;
      cp.lead = cp.members[0];
      if (!cp.stance) {
        if (cp.name === FIELD) cp.stance = '';
        else if (cp.members.some(function (q) { return chars[q].role === '主角'; })) cp.stance = '主角方';
        else {
          var votes = {}; cp.members.forEach(function (q) { var s = normStance(chars[q].stance); if (s) votes[s] = (votes[s] || 0) + 1 + w[q] / 100; });
          var best = ''; Object.keys(votes).forEach(function (s) { if (!best || votes[s] > votes[best]) best = s; });
          cp.stance = best || (cp.members.some(function (q) { return chars[q].role === '反派'; }) ? '对立' : '中立');
        }
      }
      // 星座半径：随主阵人数开方增长；单人星座给最小半径
      // 主视觉需要让成员之间留出真正的“星座间距”；半径随核心成员数开方增长，
      // 长尾仍退到暗晕，不会把大图谱的镜头撑爆。
      cp.r = (cp.core.length <= 1 ? 30 : clamp(30 + 32 * Math.sqrt(cp.core.length), 52, 220)) * SPREAD;
      cp.color = COLOR[cp.stance] || COLOR[''];
    });
    // 主角方：最重的一个居中，其余主角方阵营按盟友近环处理
    var center = null;
    camps.forEach(function (cp) { if (cp.stance === '主角方' && (!center || cp.w > center.w)) center = cp; });
    if (!center) { camps.forEach(function (cp) { if (cp.name !== FIELD && (!center || cp.w > center.w)) center = cp; }); }
    if (!center) center = camps[0];
    center.cx = 0; center.cy = 0; center.cz = 0; center.fixed = true;
    var others = camps.filter(function (cp) { return cp !== center; });
    // 扇区内按权重从中间向两侧排开：最重的在扇区正中，其后左右交替
    var bySector = {};
    others.forEach(function (cp) { var s = cp.stance === '主角方' ? '盟友' : cp.stance; (bySector[s] = bySector[s] || []).push(cp); });
    var R0 = center.r + 110 * SPREAD + Math.min(100, others.length * 8);
    Object.keys(bySector).forEach(function (s) {
      var list = bySector[s].sort(function (a, b) { return b.w - a.w; }), sec = SECTOR[s] || SECTOR[''];
      var mid = (sec[0] + sec[1]) / 2, span = (sec[1] - sec[0]);
      list.forEach(function (cp, q) {
        var side = (q % 2 ? 1 : -1), step = Math.ceil(q / 2);
        var frac = list.length <= 1 ? 0 : step / Math.max(1, Math.ceil((list.length - 1) / 2)) * 0.5;
        var ang = mid + side * frac * span * 0.92;
        var ring = Math.floor(q / 6);                          // 同扇区超过 6 个阵营时进第二环
        var rad = (R0 + cp.r) * (DIST[s] || 1.5) + ring * 240 + (q % 3) * 22;
        cp.ang = ang; cp.rad = rad; cp.ring = ring;
        cp.cx = Math.cos(ang) * rad; cp.cy = Math.sin(ang) * rad * ASPECT_Y;
        var wn = Math.min(1, cp.w / Math.max(1, center.w));
        cp.cz = -30 - 150 * (1 - wn) - ring * 80 + (rnd(hash(cp.name)) - 0.5) * 40;
      });
    });
    // 圆盘松弛：互不重叠，同时轻微回弹到各自扇区的理想极坐标
    for (k = 0; k < 90; k++) {
      var moved = 0;
      for (i = 0; i < camps.length; i++) for (j = i + 1; j < camps.length; j++) {
        var a = camps[i], b = camps[j], dx = b.cx - a.cx, dy = (b.cy - a.cy) / ASPECT_Y, d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        var need = a.r + b.r + PAD;
        if (d < need) {
          var push = (need - d) * 0.5, ux = dx / d, uy = dy / d;
          if (!a.fixed) { a.cx -= ux * push; a.cy -= uy * push * ASPECT_Y; }
          if (!b.fixed) { b.cx += ux * push; b.cy += uy * push * ASPECT_Y; }
          if (a.fixed) { b.cx += ux * push; b.cy += uy * push * ASPECT_Y; }
          if (b.fixed) { a.cx -= ux * push; a.cy -= uy * push * ASPECT_Y; }
          moved++;
        }
      }
      others.forEach(function (cp) {
        var tx = Math.cos(cp.ang) * cp.rad, ty = Math.sin(cp.ang) * cp.rad * ASPECT_Y;
        cp.cx += (tx - cp.cx) * 0.03; cp.cy += (ty - cp.cy) * 0.03;
      });
      if (!moved && k > 12) break;
    }
    // 成员布点
    var pos = new Array(n), guides = [], glyphEdges = [];
    var relSet = {};
    rels.forEach(function (r) { var a = idx[r.a], b = idx[r.b]; if (a == null || b == null) return; relSet[a + '|' + b] = relSet[b + '|' + a] = (relSet[a + '|' + b] || 0) + (r.strength || 0.5); });
    var fieldCp = null;
    camps.forEach(function (cp) { if (cp.name === FIELD && cp !== center) fieldCp = cp; else placeMembers(cp, chars, pos, tier, w, relSet, guides, glyphEdges, idx, cp === center); });
    var halfW = 0, halfH = 0, skyR = 0;
    // 视觉外框比成员布点略大：星座轨道、刻度与星云必须被镜头完整收纳，
    // 否则小图谱会出现“角色在画面里、星座框被裁掉”的退化状态。
    camps.forEach(function (cp) { if (cp === fieldCp) return; var frameR = cp.r * 1.24; halfW = Math.max(halfW, Math.abs(cp.cx) + frameR); halfH = Math.max(halfH, Math.abs(cp.cy) + frameR); skyR = Math.max(skyR, Math.sqrt(cp.cx * cp.cx + cp.cy * cp.cy / (ASPECT_Y * ASPECT_Y)) + frameR); });
    if (fieldCp) placeField(fieldCp, pos, tier, w, skyR, chars);
    if (fieldCp) { halfW = Math.max(halfW, fieldCp.halfW); halfH = Math.max(halfH, fieldCp.halfH); }
    return { camps: camps, pos: pos, halfW: halfW, halfH: halfH, guides: guides, glyphEdges: glyphEdges, center: center };
  }

  /** 散星带：无阵营的有戏份角色沿整片天球的外缘散布（角度按黄金角、半径随权重略内收），不结成星座；长尾进远景 */
  function placeField(cp, pos, tier, w, skyR, chars) {
    var seed = hash(cp.name), core = cp.core, R = skyR + 90;
    cp.skyR = skyR; cp.cx = 0; cp.cy = -(R + 40) * ASPECT_Y; cp.cz = -200; cp.r = 40; cp.halfW = 0; cp.halfH = 0;
    core.forEach(function (q, m) {
      var t = (m + 0.5) / Math.max(1, core.length), a = Math.PI * 1.5 + (m % 2 ? 1 : -1) * Math.ceil(m / 2) * (Math.PI * 2 / Math.max(6, core.length));
      var rr = R + 50 * Math.sqrt(t) + (m % 3) * 26;
      pos[q] = { x: Math.cos(a) * rr, y: Math.sin(a) * rr * ASPECT_Y, z: -180 - rnd(seed + m * 2.1) * 140 + (tier[q] <= 1 ? 60 : 0) };
      cp.halfW = Math.max(cp.halfW, Math.abs(pos[q].x) + 20); cp.halfH = Math.max(cp.halfH, Math.abs(pos[q].y) + 20);
    });
    cp.tail.forEach(function (q, m) {
      var t = (m + 0.5) / Math.max(1, cp.tail.length), a = m * GA + rnd(seed + 1) * 6.283, rr = R + 140 + 640 * Math.sqrt(t);
      pos[q] = { x: Math.cos(a) * rr, y: Math.sin(a) * rr * 0.62, z: -420 - rnd(seed + m * 1.37) * 300 };
    });
  }

  // 星座字形（v18.4）：以真实星座的骨架为模板 —— 仙后座 W、北斗、猎户、北冕弧、狮子镰、天蝎钩、双子双链、天龙蛇形。
  // 点 0 永远是该星座最亮的星（成员按权重排序后一一对应），边是星图式折线，绝不从中心向全员放射。
  // 坐标归一化到 [-1,1]；大阵营（>12）拆成若干段模板沿弧排布，再用一条桥边接成一座连贯的大星座。
  var TPL = {
    1: [[[0, 0]], []],
    2: [[[-.75, .30], [.80, -.25]], [[0, 1]]],
    3: [[[.20, .62], [-.85, -.30], [.90, -.45]], [[0, 1], [1, 2], [2, 0]]],                                   // 三角座（不等边）
    4: [[[-.55, .50], [.50, .62], [.70, -.45], [-.75, -.55]], [[0, 1], [1, 2], [2, 3], [3, 0]]],             // 乌鸦座（斜四边）
    5: [[[0, -.15], [-.50, .45], [-.95, -.05], [.50, .50], [.95, 0]], [[2, 1], [1, 0], [0, 3], [3, 4]]],      // 仙后座 W
    6: [[[-.10, -.35], [-.55, -.20], [.35, -.25], [-.90, .25], [.70, .10], [.85, .60]], [[3, 1], [1, 0], [0, 2], [2, 4], [4, 5]]],   // 北冕座（开口弧）
    7: [[[.95, .19], [.05, .09], [-.90, .42], [.92, -.28], [-.40, .19], [.45, -.41], [.50, .05]],
        [[0, 3], [3, 5], [5, 6], [6, 0], [6, 1], [1, 4], [4, 2]]],                                            // 北斗七星（斗 + 柄）
    8: [[[-.45, -.68], [.35, .70], [-.40, .62], [0, 0], [.15, .05], [-.15, -.05], [.30, -.72], [0, .95]],
        [[1, 4], [2, 5], [4, 3], [3, 5], [4, 6], [5, 0], [1, 7], [2, 7]]],                                   // 猎户座（肩 · 腰带 · 足 · 头）
    9: [[[.55, -.55], [.55, -.10], [.50, .35], [.30, .68], [-.05, .72], [-.20, .45], [-.35, .20], [-.35, -.35], [-.95, -.05]],
        [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 2], [0, 7], [7, 6], [6, 8], [7, 8]]],           // 狮子座（镰 + 三角）
    10: [[[-.35, .32], [-.70, .30], [-.85, .62], [-.85, -.02], [-.05, .20], [.15, -.10], [.30, -.42], [.55, -.62], [.85, -.50], [.95, -.15]],
        [[2, 1], [3, 1], [1, 0], [0, 4], [4, 5], [5, 6], [6, 7], [7, 8], [8, 9]]],                           // 天蝎座（头 · 心 · 钩尾）
    11: [[[.85, -.05], [.85, .55], [.45, .45], [.05, .50], [-.40, .42], [-.85, .50], [.45, -.20], [.05, -.30], [-.45, -.35], [-.85, -.55], [-.15, .08]],
        [[1, 2], [2, 3], [3, 4], [4, 5], [0, 6], [6, 7], [7, 8], [8, 9], [1, 0], [10, 3], [10, 7]]],        // 双子座（双链 + 联星）
    12: [[[-.55, .45], [-.95, .55], [-.70, .72], [-.80, .30], [-.35, .20], [-.05, .35], [.20, .15], [.40, -.15], [.55, -.45], [.80, -.55], [.95, -.30], [.90, .05]],
        [[1, 2], [2, 0], [0, 3], [3, 1], [0, 4], [4, 5], [5, 6], [6, 7], [7, 8], [8, 9], [9, 10], [10, 11]]] // 天龙座（头四边 + 蛇身）
  };
  // 变体（v20）：同一人数第二套真实星座骨架，含副边（第三项 = 权重 0.55，画得更细更淡）；按座 seed 二选一
  var TPLV = {
    3: [[[-.95, -.25], [.05, .35], [.95, -.40]], [[0, 1], [1, 2]]],                                                  // 狐狸座（开口折线）
    4: [[[0, .95], [-.72, -.08], [.78, .18], [.14, -.95]], [[0, 3], [1, 2], [0, 1, .55], [2, 3, .55]]],              // 南十字（十字 + 副边）
    5: [[[-.10, .55], [.42, .25], [.06, -.15], [-.46, .15], [-.78, -.75]], [[0, 1], [1, 2], [2, 3], [3, 0], [3, 4]]], // 海豚座（菱 + 尾）
    6: [[[.10, .95], [-.75, .45], [-.62, -.60], [.35, -.85], [.85, -.10], [.70, .60]], [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [0, 4, .55]]],   // 御夫座（六边环 + 副边）
    7: [[[0, .95], [-.60, .25], [.60, .35], [-.70, -.65], [.75, -.60], [-.10, -.15], [.22, -.68]], [[0, 1], [0, 2], [1, 3], [2, 4], [3, 4], [1, 5, .55], [5, 6, .55]]],   // 仙王座（屋形 + 内星）
    8: [[[-.50, .45], [.35, .50], [.45, -.35], [-.40, -.40], [.70, .85], [.95, .70], [-.85, -.75], [-.95, .05]], [[0, 1], [1, 2], [2, 3], [3, 0], [1, 4], [4, 5], [3, 6], [0, 7], [0, 2, .55]]],   // 飞马座（大方 + 颈 + 前肢）
    9: [[[0, .95], [0, .45], [0, -.10], [0, -.75], [-.55, .20], [.55, .20], [-.95, .45], [.95, .05], [.30, -.95]], [[0, 1], [1, 2], [2, 3], [4, 2], [2, 5], [6, 4], [5, 7], [3, 8], [1, 4, .55], [1, 5, .55]]]   // 天鹅座（十字 + 翼）
  };
  function tplOf(n, variant) { var t = (variant && TPLV[n]) ? TPLV[n] : TPL[n]; return { points: t[0].map(function (p) { return [p[0], p[1]]; }), edges: t[1].map(function (e) { return e.length > 2 ? [e[0], e[1], e[2]] : [e[0], e[1]]; }) }; }
  function constellationGlyph(n, seed) {
    var g;
    if (n <= 12) g = tplOf(n, rnd(seed * 0.77 + 9) < 0.5);
    else {
      // 分段：每段 6–8 星，段中心沿一条大弧排开，段内模板缩小；相邻段以最近点相接
      var k = Math.ceil(n / 8), sizes = [], base = Math.floor(n / k), extra = n - base * k, i, s;
      for (i = 0; i < k; i++) sizes.push(base + (i < extra ? 1 : 0));
      var points = [], edges = [], off = 0, centers = [], sc = k === 2 ? 0.46 : k === 3 ? 0.40 : Math.max(0.24, 0.62 / Math.sqrt(k)), rad = k === 2 ? 0.62 : 0.68;
      var a0 = Math.PI * 0.5 + (rnd(seed) - 0.5) * 0.6;
      for (i = 0; i < k; i++) {
        var ang = a0 + Math.PI * 2 * i / k, cx = k === 2 ? (i ? 0.62 : -0.62) : Math.cos(ang) * rad, cy = k === 2 ? (i ? -0.14 : 0.14) : Math.sin(ang) * rad * 0.8;
        var sub = tplOf(sizes[i], rnd(seed + i * 3.3) < 0.5), rot = (rnd(seed + i * 7.7) - 0.5) * 1.2, cr = Math.cos(rot), sr = Math.sin(rot);
        centers.push({ off: off, n: sizes[i] });
        sub.points.forEach(function (p) { points.push([cx + (p[0] * cr - p[1] * sr) * sc, cy + (p[0] * sr + p[1] * cr) * sc]); });
        sub.edges.forEach(function (e) { edges.push(e.length > 2 ? [e[0] + off, e[1] + off, e[2]] : [e[0] + off, e[1] + off]); });
        off += sizes[i];
      }
      for (i = 0; i < k - 1; i++) {                                     // 桥边：相邻段最近的一对星
        var A = centers[i], B = centers[i + 1], best = null, bd = 1e9;
        for (var x = 0; x < A.n; x++) for (var y = 0; y < B.n; y++) { var pa = points[A.off + x], pb = points[B.off + y], d = (pa[0] - pb[0]) * (pa[0] - pb[0]) + (pa[1] - pb[1]) * (pa[1] - pb[1]); if (d < bd) { bd = d; best = [A.off + x, B.off + y]; } }
        if (best) edges.push(best);
      }
      g = { points: points, edges: edges };
    }
    // 确定性姿态：轻微旋转 + 随机镜像，避免多座星座朝向雷同；重心归零
    var rot = (rnd(seed * 1.3 + 2) - 0.5) * 0.5, mir = rnd(seed * 2.1 + 5) < 0.5 ? -1 : 1, cr = Math.cos(rot), sr = Math.sin(rot);
    var mx = 0, my = 0; g.points.forEach(function (p) { mx += p[0]; my += p[1]; }); mx /= g.points.length; my /= g.points.length;
    g.points = g.points.map(function (p) { var x = (p[0] - mx) * mir, y = p[1] - my; return [x * cr - y * sr, x * sr + y * cr]; });
    var mag = 0; g.points.forEach(function (p) { mag = Math.max(mag, Math.sqrt(p[0] * p[0] + p[1] * p[1])); });
    if (mag > 0) g.points = g.points.map(function (p) { return [p[0] / mag, p[1] / mag]; });
    return g;
  }

  function placeMembers(cp, chars, pos, tier, w, relSet, guides, glyphEdges, idx, isCenter) {
    var core = cp.core, tail = cp.tail, r = cp.r, seed = hash(cp.name), i, j, k;
    var glyph = constellationGlyph(core.length, seed);
    var P = core.map(function (q, m) { var p = glyph.points[m] || [0, 0]; return { x: p[0] * r * 0.92, y: p[1] * r * 0.92 }; });
    var minD = function (a, b) { return Math.max(MIN_D[tier[core[a]]], MIN_D[tier[core[b]]]) * SPREAD; };
    // 只做最小间距斥力（保护标签可读），不再用关系弹簧拉扯模板：星座的“样子”由字形决定，关系用线来表达。
    for (k = 0; k < 40; k++) {
      var moved = false;
      for (i = 0; i < P.length; i++) for (j = i + 1; j < P.length; j++) {
        var dx = P[j].x - P[i].x, dy = P[j].y - P[i].y, d = Math.sqrt(dx * dx + dy * dy) || 0.01, md = minD(i, j);
        if (d < md) { var p = (md - d) * 0.5, ux = dx / d, uy = dy / d; P[i].x -= ux * p; P[i].y -= uy * p; P[j].x += ux * p; P[j].y += uy * p; moved = true; }
      }
      if (!moved) break;
    }
    for (i = 0; i < P.length; i++) { var L = Math.sqrt(P[i].x * P[i].x + P[i].y * P[i].y); if (L > r * 1.05) { P[i].x *= r * 1.05 / L; P[i].y *= r * 1.05 / L; } }
    core.forEach(function (q, m) {
      var t = tier[q], zt = t === 0 ? 30 : t === 1 ? 12 : t === 2 ? -6 : -22;
      pos[q] = { x: cp.cx + P[m].x, y: cp.cy + P[m].y * ASPECT_Y, z: cp.cz + zt + (rnd(seed + m * 3.7) - 0.5) * 24 };
    });
    glyph.edges.forEach(function (e) {
      var a = core[e[0]], b = core[e[1]];
      if (a == null || b == null) return;
      glyphEdges.push({ a: a, b: b, rel: !!relSet[a + '|' + b], color: cp.color || COLOR[cp.stance] || COLOR[''] });
    });
    // 引导线：无同阵营关系的成员接到最近的更亮成员；再把各连通分量接到主星，保证星座图形连通
    if (core.length >= 2) {
      var parent = core.map(function (_, m) { return m; });
      function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
      function union(a, b) { a = find(a); b = find(b); if (a !== b) parent[a] = b; }
      for (i = 0; i < core.length; i++) for (j = i + 1; j < core.length; j++) if (relSet[core[i] + '|' + core[j]]) union(i, j);
      for (i = 1; i < core.length; i++) {
        var has = false; for (j = 0; j < core.length; j++) if (j !== i && relSet[core[i] + '|' + core[j]]) { has = true; break; }
        if (has) continue;
        var best = -1, bd = 1e9;
        for (j = 0; j < core.length; j++) { if (j === i || w[core[j]] < w[core[i]] && j !== 0) continue; var dx2 = P[j].x - P[i].x, dy2 = P[j].y - P[i].y, d2 = dx2 * dx2 + dy2 * dy2; if (d2 < bd) { bd = d2; best = j; } }
        if (best >= 0) { guides.push([core[i], core[best]]); union(i, best); }
      }
      var roots = {};
      for (i = 0; i < core.length; i++) { var rt = find(i); if (roots[rt] == null) roots[rt] = i; }
      Object.keys(roots).forEach(function (rt) { var m = roots[rt]; if (find(m) !== find(0)) { guides.push([core[m], core[0]]); union(m, 0); } });
    }
    // 长尾：本星座外围的暗晕（散星带的长尾则铺成远景宽螺旋）
    var field = cp.name === FIELD;
    tail.forEach(function (q, m) {
      var t = (m + 0.5) / Math.max(1, tail.length), a = m * GA + rnd(seed + 1) * 6.283;
      var rr = field ? (cp.skyR + 140 + 640 * Math.sqrt(t)) : r * (1.18 + 0.55 * Math.sqrt(t));
      pos[q] = { x: (field ? 0 : cp.cx) + Math.cos(a) * rr, y: (field ? 0 : cp.cy) + Math.sin(a) * rr * (field ? 0.62 : ASPECT_Y), z: cp.cz - (field ? 420 : 150) - rnd(seed + m * 1.37) * (field ? 300 : 160) };
    });
    if (isCenter) cp.cz = 0;
  }

  // ====================================================================================
  // 星链布局（v19.1）：全员一条连续的长链 —— 首尾相接、一颗接一颗，像一幅完整的星图长卷。
  //   走向 = 阿基米德螺旋：主角在中心起笔，按阵营段（段内按权重）逐颗向外缠绕；长尾拖成渐暗的尾迹
  //   珠结 = 链上每 3–7 颗结成一枚可辨的小星座（W / 弓 / 勺 / 折线 / 三角），沿切线排布、向法线起伏
  //   颜色 = 阵营立场色，沿链成段；分类不再画椭圆，只留色段与段首座名
  //   全部确定性；同一份图谱两次布局完全一致。
  // ====================================================================================
  var CHAIN_TPL = {
    2: [[[0, .18], [0, -.18]], []],
    3: [[[0, -.35], [0, .95], [0, -.35]], [[0, 2]]],                                    // 三角（闭合）
    4: [[[0, .55], [0, -.65], [0, .65], [0, -.55]], []],                                 // 折线
    5: [[[0, .62], [0, -.62], [0, .40], [0, -.62], [0, .62]], []],                       // 仙后 W
    6: [[[0, -.55], [0, .45], [0, .92], [0, .92], [0, .45], [0, -.55]], []],             // 北冕弓
    7: [[[0, .22], [0, -.12], [0, .18], [0, -.22], [0, -.62], [0, .30], [0, .68]], [[3, 6]]], // 北斗：柄 → 斗
    8: [[[0, .6], [0, -.6], [0, .12], [0, .38], [0, -.12], [0, .6], [0, -.66], [0, .14]], [[2, 5]]]
  };
  function chainKnotSizes(n, seed, tail) {
    var out = [], left = n, i = 0;
    if (tail) { while (left > 0) { var k = left >= 5 ? 2 + Math.floor(rnd(seed + i) * 2) : left; out.push(k); left -= k; i++; } return out; }
    var pool = [5, 7, 4, 6, 3, 5, 8, 4];
    while (left > 0) {
      var k = pool[Math.floor(rnd(seed + i * 1.7) * pool.length)];
      if (left - k < 3 && left - k > 0) k = left <= 8 ? left : Math.max(3, k - 1);
      k = Math.min(k, left); out.push(k); left -= k; i++;
    }
    return out;
  }
  function layoutChain(chars, rels, campDefs, tierOf, weightOf) {
    var n = chars.length, i, idx = {};
    SPREAD = n <= 12 ? 1.8 : n <= 26 ? 1.45 : n <= 80 ? 1.2 : 1;
    chars.forEach(function (c, q) { idx[c.name] = q; });
    var camps = groupCamps(chars, campDefs), tier = chars.map(tierOf), w = chars.map(weightOf);
    camps.forEach(function (cp) {
      cp.members.sort(function (a, b) { return w[b] - w[a]; });
      cp.core = cp.members.filter(function (q) { return tier[q] < 4; });
      cp.tail = cp.members.filter(function (q) { return tier[q] >= 4; });
      cp.w = cp.core.reduce(function (s, q) { return s + w[q]; }, 0) + cp.tail.length * 0.5;
      cp.lead = cp.members[0];
      if (!cp.stance) {
        if (cp.name === FIELD) cp.stance = '';
        else if (cp.members.some(function (q) { return chars[q].role === '主角'; })) cp.stance = '主角方';
        else {
          var votes = {}; cp.members.forEach(function (q) { var s = normStance(chars[q].stance); if (s) votes[s] = (votes[s] || 0) + 1 + w[q] / 100; });
          var best = ''; Object.keys(votes).forEach(function (s) { if (!best || votes[s] > votes[best]) best = s; });
          cp.stance = best || (cp.members.some(function (q) { return chars[q].role === '反派'; }) ? '对立' : '中立');
        }
      }
      cp.color = COLOR[cp.stance] || COLOR[''];
      cp.r = 40;
    });
    // 链序：主角方最重的阵营起笔，其后按权重；每段 = 该阵营核心成员；所有长尾按权重接在链尾
    var order = camps.slice().sort(function (a, b) { var pa = a.stance === '主角方' ? 1 : 0, pb = b.stance === '主角方' ? 1 : 0; if (pa !== pb) return pb - pa; if ((a.name === FIELD) !== (b.name === FIELD)) return a.name === FIELD ? 1 : -1; return b.w - a.w; });
    var seq = [];   // {q, cp, tail}
    order.forEach(function (cp) { cp.core.forEach(function (q) { seq.push({ q: q, cp: cp, tail: false }); }); });
    var tails = []; camps.forEach(function (cp) { cp.tail.forEach(function (q) { tails.push({ q: q, cp: cp, tail: true }); }); });
    tails.sort(function (a, b) { return w[b.q] - w[a.q]; });
    seq = seq.concat(tails);
    // 珠结划分：同段内连续 3–7 颗；长尾 2–3 颗一组、起伏很小
    var knots = [], p = 0;
    while (p < seq.length) {
      var cp0 = seq[p].cp, isTail = seq[p].tail, run = p;
      while (run < seq.length && seq[run].cp === cp0 && seq[run].tail === isTail) run++;
      var sizes = chainKnotSizes(run - p, hash(cp0.name) + p, isTail), at = p;
      sizes.forEach(function (k) { knots.push({ from: at, to: at + k, cp: cp0, tail: isTail }); at += k; });
      p = run;
    }
    // 步长（弧长）按星等；螺旋圈距 G 要容得下珠结起伏 + 标签
    var STEP = [150, 122, 96, 76, 42];
    var step = seq.map(function (e) { return STEP[Math.min(4, tier[e.q])] * SPREAD; });
    var G = 172 * SPREAD, k = G / (Math.PI * 2), r0 = 34 * SPREAD;
    var pos = new Array(n), glyphEdges = [], guides = [], chain = [];
    // 沿弧长推进：数值积分 s(θ)
    var th = 0, sAcc = 0, dth = 0.02;
    function advance(ds) { var target = sAcc + ds; while (sAcc < target) { var r = r0 + k * th; var dl = Math.sqrt(r * r + k * k) * dth; sAcc += dl; th += dth; } }
    function pointAt(theta) { var r = r0 + k * theta; return { x: Math.cos(theta) * r, y: Math.sin(theta) * r }; }
    var th0 = Math.PI * 0.62;   // 起笔方向：左上
    var cur = 0;
    knots.forEach(function (kn, ki) {
      var m = kn.to - kn.from, tpl = CHAIN_TPL[Math.min(8, Math.max(2, m))] || CHAIN_TPL[2];
      var amp = (kn.tail ? 0.10 : 0.42) * G * (m <= 2 ? 0.5 : 1);
      var flip = rnd(hash(kn.cp.name) + ki * 3.1) < 0.5 ? -1 : 1;
      for (var j = 0; j < m; j++) {
        var e = seq[kn.from + j], q = e.q;
        if (cur > 0) advance((step[cur - 1] + step[cur]) * 0.5);
        var theta = th0 + th, P = pointAt(theta), Pn = pointAt(theta + 0.001);
        var tx = Pn.x - P.x, ty = Pn.y - P.y, tl = Math.sqrt(tx * tx + ty * ty) || 1; tx /= tl; ty /= tl;
        var nx = -ty, ny = tx, off = (m === 1 ? 0 : tpl[0][Math.min(j, tpl[0].length - 1)][1]) * amp * flip;
        var t = tier[q], zt = t === 0 ? 34 : t === 1 ? 16 : t === 2 ? 0 : t === 3 ? -18 : -60;
        pos[q] = { x: P.x + nx * off, y: (P.y + ny * off) * ASPECT_Y, z: zt + (rnd(q * 3.7) - 0.5) * 18 - (kn.tail ? 80 : 0) };
        chain.push(q);
        var col = kn.cp.color;
        if (cur > 0) { var prev = seq[cur - 1].q; glyphEdges.push({ a: prev, b: q, rel: false, color: mixColor(seq[cur - 1].cp.color, col), chain: true, tail: kn.tail || seq[cur - 1].tail }); }
        cur++;
      }
      (tpl[1] || []).forEach(function (ed) { if (ed[0] < m && ed[1] < m) glyphEdges.push({ a: seq[kn.from + ed[0]].q, b: seq[kn.from + ed[1]].q, rel: false, color: kn.cp.color, knot: true }); });
    });
    // 阵营描述量：段首（座名锚点）、质心、外接
    camps.forEach(function (cp) {
      var mem = cp.members.filter(function (q) { return pos[q]; }); if (!mem.length) { cp.cx = cp.cy = cp.cz = 0; return; }
      var sx = 0, sy = 0; mem.forEach(function (q) { sx += pos[q].x; sy += pos[q].y; });
      cp.cx = sx / mem.length; cp.cy = sy / mem.length; cp.cz = 0;
      var head = pos[cp.lead] || pos[mem[0]];
      cp.labelX = head.x - 26 * SPREAD; cp.labelY = head.y + 44 * SPREAD; cp.labelZ = head.z + 8;
      cp.fitRx = cp.fitRy = 60;
    });
    var halfW = 0, halfH = 0;
    pos.forEach(function (pp) { if (!pp) return; halfW = Math.max(halfW, Math.abs(pp.x) + 60); halfH = Math.max(halfH, Math.abs(pp.y) + 60); });
    var center = order[0] || camps[0];
    return { camps: camps, pos: pos, halfW: halfW, halfH: halfH, guides: guides, glyphEdges: glyphEdges, center: center, chain: chain, mode: 'chain', turns: th / (Math.PI * 2) };
  }
  // ====================================================================================
  // 星路布局（v19.2 · 默认）：全员首尾相接，但每一节都是一座「真正的星座」。
  //   节 = 3–9 星的星座字形（三角 / 乌鸦 / 仙后 W / 北冕 / 北斗 / 猎户 / 狮子 / 天蝎 / 双子），
  //       同阵营连续成员按权重结成一节节；长尾结成小而暗的三四星小座
  //   路 = 节与节之间的「桥」：前一座离后一座最近的一颗星 → 后一座最近的一颗星，一座接一座，
  //       从主角座起笔，沿倾斜的星盘螺旋向外——像黄道十二宫沿黄道带排开
  //   3D = 星盘整体前倾（上远下近）+ 每座独立俯仰 / 偏航 + 外圈缓缓退入深空 + 星等抬升
  //   颜色 = 阵营立场色；分类只留色段与段首座名，不再画椭圆框
  //   全部确定性；同一份图谱两次布局完全一致。
  // ====================================================================================
  // ====================================================================================
  // 精密星座生成器（v21）：14–36 星的大星座 = 手绘大星座模板 + 程序化增殖。
  //   模板（点序 = 亮度序，0 号最亮）：猎户 18 · 天蝎 18 · 大熊 20 · 天龙 17 · 天鹅 15 · 长蛇 19 · 英仙 19 · 人马 22
  //   增殖：不足的星作为「叶星」挂到低度数骨节上（边权 0.55）；≥ 28 星时一半概率改用程序化骨架
  //   （主骨折线 → 分枝 → 头环 → 叶星），保证每座都不重样。边权：主骨 1 · 环 0.9 · 枝 0.85 · 叶 0.55。
  // ====================================================================================
  var BIG_TPL = [
    { name: 'Orion', zh: '猎户', p: [[-.55, -.75], [.55, .55], [-.45, .6], [0, -.05], [.18, -.12], [-.18, .02], [.5, -.8], [.05, .85], [-.95, .55], [-1.05, .3], [-1.08, .05], [-1.02, -.2], [-.9, -.42], [.72, .82], [.9, 1.02], [1.05, .88], [.8, 1.15], [.02, -.3]],
      e: [[1, 4], [2, 5], [5, 3], [3, 4], [5, 0], [4, 6], [1, 7], [2, 7], [2, 8, .85], [8, 9, .85], [9, 10, .85], [10, 11, .85], [11, 12, .85], [1, 13, .85], [13, 14, .85], [14, 15, .85], [14, 16, .85], [3, 17, .55], [0, 6, .55]] },
    { name: 'Scorpius', zh: '天蝎', p: [[0, .1], [-.72, .55], [-.62, .85], [-.78, .28], [-.9, .1], [-.32, .38], [.12, -.15], [.2, -.42], [.32, -.66], [.5, -.85], [.72, -.92], [.9, -.8], [.98, -.6], [.92, -.48], [-.5, .62], [-.4, .15], [.35, .2], [.6, -.7]],
      e: [[2, 1], [1, 3], [3, 4], [1, 5], [5, 0], [0, 6], [6, 7], [7, 8], [8, 9], [9, 10], [10, 11], [11, 12], [12, 13], [14, 1, .55], [15, 3, .55], [16, 0, .55], [17, 9, .55]] },
    { name: 'UrsaMajor', zh: '大熊', p: [[.55, .35], [.6, .05], [.28, -.02], [.25, .28], [-.05, .35], [-.32, .42], [-.6, .55], [.3, -.35], [.42, -.62], [.75, -.4], [.85, -.65], [.9, .4], [1.05, .25], [1.1, .55], [.05, -.4], [-.1, -.7], [-.35, -.3], [-.5, -.55], [.7, .6], [-.15, .05]],
      e: [[0, 1], [1, 2], [2, 3], [3, 0], [3, 4], [4, 5], [5, 6], [2, 7, .85], [7, 8, .85], [1, 9, .85], [9, 10, .85], [0, 11, .85], [11, 12, .85], [11, 13, .85], [2, 14, .85], [14, 15, .85], [14, 16, .85], [16, 17, .85], [0, 18, .55], [4, 19, .55]] },
    { name: 'Draco', zh: '天龙', p: [[.75, .55], [.6, .75], [.85, .8], [.95, .6], [.45, .35], [.2, .5], [-.05, .35], [-.25, .1], [-.5, .15], [-.7, .4], [-.85, .2], [-.9, -.1], [-.75, -.35], [-.5, -.55], [-.2, -.7], [.15, -.8], [.5, -.85]],
      e: [[0, 1, .9], [1, 2, .9], [2, 3, .9], [3, 0, .9], [0, 4], [4, 5], [5, 6], [6, 7], [7, 8], [8, 9], [9, 10], [10, 11], [11, 12], [12, 13], [13, 14], [14, 15], [15, 16]] },
    { name: 'Cygnus', zh: '天鹅', p: [[0, .9], [0, .3], [.5, .15], [-.5, .45], [0, -.85], [.85, 0], [-.9, .6], [0, -.3], [1.1, .12], [-1.1, .72], [.25, .65], [-.25, .7], [.15, -.55], [.55, -.25], [-.35, -.1]],
      e: [[0, 1], [1, 7], [7, 4], [1, 2], [2, 5], [5, 8, .85], [1, 3], [3, 6], [6, 9, .85], [0, 10, .55], [0, 11, .55], [7, 12, .55], [2, 13, .55], [3, 14, .55]] },
    { name: 'Hydra', zh: '长蛇', p: [[-.2, .05], [-.9, .55], [-1, .75], [-.8, .85], [-.65, .7], [-.7, .5], [-.45, .35], [.05, -.15], [.25, -.4], [.5, -.45], [.7, -.6], [.9, -.55], [1.05, -.7], [.4, -.7], [.85, -.85], [-.35, .2], [.15, .1], [.6, -.25], [-.55, .75]],
      e: [[1, 2, .9], [2, 3, .9], [3, 4, .9], [4, 5, .9], [5, 1, .9], [5, 6], [6, 0], [0, 7], [7, 8], [8, 9], [9, 10], [10, 11], [11, 12], [9, 13, .85], [12, 14, .85], [15, 6, .55], [16, 0, .55], [17, 9, .55], [18, 3, .55]] },
    { name: 'Perseus', zh: '英仙', p: [[0, .3], [.15, .6], [.35, .85], [.55, 1], [-.45, .05], [-.7, -.2], [-.85, -.5], [.2, -.05], [.35, -.35], [.45, -.65], [.5, -.95], [-.3, .45], [-.55, .55], [.05, 0], [-.2, -.25], [.7, .7], [-.6, .3], [.25, .35], [.7, -.5]],
      e: [[0, 1], [1, 2], [2, 3], [0, 4], [4, 5], [5, 6], [0, 7], [7, 8], [8, 9], [9, 10], [0, 11, .85], [11, 12, .85], [13, 7, .55], [14, 4, .55], [15, 2, .55], [16, 12, .55], [17, 1, .55], [18, 9, .55]] },
    { name: 'Sagittarius', zh: '人马', p: [[-.1, -.35], [.45, .2], [.5, -.2], [-.15, .05], [-.05, .4], [.2, .15], [.7, -.05], [-.5, -.05], [.75, .4], [-.85, .35], [-.95, 0], [-.85, -.35], [-.65, -.6], [.35, .65], [.55, .85], [.8, .75], [.85, .55], [.1, -.7], [-.35, -.5], [.3, -.5], [0, .75], [-.6, .2]],
      e: [[3, 4], [4, 5], [5, 1], [1, 6], [6, 2], [2, 0], [0, 3], [3, 7], [5, 2, .85], [1, 8, .85], [7, 10, .85], [9, 10, .85], [10, 11, .85], [11, 12, .85], [13, 14, .85], [14, 15, .85], [15, 16, .85], [16, 13, .85], [4, 13, .55], [17, 0, .55], [18, 0, .55], [19, 2, .55], [20, 4, .55], [21, 3, .55]] },
    { name: 'Phoenix', zh: '凤凰', p: [[0, .15], [.15, .75], [.32, .85], [.05, .55], [0, .35], [-.25, .3], [-.55, .45], [-.85, .5], [-1, .35], [.25, .3], [.55, .45], [.85, .5], [1, .35], [-.1, -.1], [-.2, -.4], [-.35, -.7], [-.45, -.95], [.1, -.12], [.2, -.42], [.3, -.72], [.4, -.98]],
      e: [[0, 4], [4, 3], [3, 1], [1, 2], [0, 5], [5, 6], [6, 7], [7, 8], [0, 9], [9, 10], [10, 11], [11, 12], [0, 13, .85], [13, 14, .85], [14, 15, .85], [15, 16, .85], [0, 17, .85], [17, 18, .85], [18, 19, .85], [19, 20, .85]] },
    { name: 'Grus', zh: '仙鹤', p: [[0, 0], [.55, .75], [.72, .82], [.35, .55], [.15, .3], [-.2, .35], [-.45, .6], [-.7, .75], [-.25, -.15], [-.55, -.3], [.05, -.35], [.1, -.7], [.2, -1], [-.35, -.5], [-.6, -.75], [.95, .65]],
      e: [[0, 4], [4, 3], [3, 1], [1, 2], [0, 5], [5, 6], [6, 7], [0, 8], [8, 9], [0, 10, .85], [10, 11, .85], [11, 12, .85], [8, 13, .85], [13, 14, .85], [2, 15, .55]] },
    { name: 'Lupus', zh: '天狼', p: [[.75, .45], [.85, .7], [1, .35], [.5, .3], [.2, .35], [-.15, .4], [-.5, .3], [-.8, .45], [-1, .7], [0, .05], [-.35, 0], [.4, -.1], [.45, -.5], [.55, -.9], [-.45, -.2], [-.55, -.55], [-.65, -.95], [.55, .05]],
      e: [[0, 1, .85], [0, 2], [0, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8, .85], [3, 17], [17, 9], [9, 10], [10, 6, .85], [17, 11, .85], [11, 12, .85], [12, 13, .85], [10, 14, .85], [14, 15, .85], [15, 16, .85]] },
    { name: 'Cetus', zh: '鲸鱼', p: [[.9, .1], [.75, .25], [.95, -.15], [.5, .35], [.1, .45], [-.3, .35], [-.6, .15], [-.85, .05], [-1, .3], [-1, -.25], [.5, -.25], [.1, -.35], [-.3, -.3], [-.6, -.15], [.35, -.5], [.2, -.8], [.55, .7], [.6, .95]],
      e: [[0, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8, .85], [7, 9, .85], [0, 2], [2, 10], [10, 11], [11, 12], [12, 13], [13, 7], [10, 14, .85], [14, 15, .85], [0, 1, .55], [3, 16, .55], [16, 17, .55]] },
    { name: 'Argo', zh: '天舟', p: [[0, .4], [0, .9], [0, -.05], [-.9, -.2], [-.5, -.45], [0, -.55], [.5, -.45], [.9, -.2], [-.7, 0], [.7, 0], [-.5, .2], [-.4, .7], [.45, .7], [.5, .2], [1.05, .05], [-1.05, .05], [.9, .6], [.2, .15], [-.2, .6], [-.25, .9]],
      e: [[3, 4], [4, 5], [5, 6], [6, 7], [8, 9, .85], [3, 8], [7, 9], [2, 0], [0, 1], [10, 11, .85], [11, 12, .85], [12, 13, .85], [13, 10, .85], [7, 14, .85], [3, 15, .85], [1, 16, .55], [2, 17, .55], [0, 18, .55], [1, 19, .55]] },
    { name: 'Ensis', zh: '宝剑', p: [[0, .1], [0, 1], [0, .7], [0, .4], [-.45, -.05], [-.2, -.05], [.2, -.05], [.45, -.05], [0, -.3], [0, -.55], [0, -.8], [-.12, .55], [.12, .25], [-.1, .85], [.15, -.9]],
      e: [[1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [0, 5, .85], [0, 6, .85], [0, 8], [8, 9], [9, 10], [11, 2, .55], [12, 3, .55], [13, 1, .55], [14, 10, .55]] },
    { name: 'Lotus', zh: '莲花', p: [[0, 0], [-.3, .4], [.3, .4], [-.5, 0], [.5, 0], [-.75, .55], [.75, .55], [-.95, .05], [.95, .05], [0, .85], [-.45, .95], [.45, .95], [0, -.4], [.1, -.75], [.05, -1], [-.5, -.6]],
      e: [[0, 1], [0, 2], [0, 3], [0, 4], [3, 1, .85], [1, 2, .85], [2, 4, .85], [7, 5, .85], [5, 10, .85], [10, 9, .85], [9, 11, .85], [11, 6, .85], [6, 8, .85], [1, 5, .55], [2, 6, .55], [3, 7, .55], [4, 8, .55], [0, 12], [12, 13], [13, 14], [12, 15, .55]] },
    { name: 'Cervus', zh: '麋鹿', p: [[.6, .45], [.75, .75], [.9, .95], [.55, .85], [.45, 1], [.4, .25], [.1, .3], [-.3, .3], [-.65, .25], [-.85, .35], [0, 0], [-.4, -.02], [.3, -.3], [.35, -.75], [-.55, -.35], [-.6, -.8], [.45, .05]],
      e: [[0, 1, .85], [1, 2, .85], [0, 3, .85], [3, 4, .85], [0, 5], [5, 6], [6, 7], [7, 8], [8, 9, .85], [5, 16], [16, 10], [10, 11], [11, 8, .85], [16, 12, .85], [12, 13, .85], [11, 14, .85], [14, 15, .85]] },
    { name: 'Lyra', zh: '天琴', p: [[0, .6], [-.35, .3], [.35, .3], [-.45, -.3], [.45, -.3], [-.15, 0], [.15, 0], [0, -.2], [-.3, -.7], [.3, -.7], [0, -.95], [-.7, .55], [.7, .55], [0, .95]],
      e: [[0, 1], [0, 2], [1, 3], [3, 8], [8, 10], [10, 9], [9, 4], [4, 2], [1, 5, .55], [5, 7, .55], [6, 7, .55], [2, 6, .55], [1, 11, .55], [2, 12, .55], [0, 13, .55]] },
    { name: 'Leo', zh: '狮子', p: [[.55, -.15], [.7, .2], [.6, .55], [.35, .75], [.1, .6], [.25, .3], [0, 0], [-.4, .05], [-.8, .15], [-1, .4], [-.6, -.35], [-.55, -.75], [.4, -.5], [.45, -.9], [-.2, -.3], [.9, .5]],
      e: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6, .85], [6, 0, .85], [6, 7, .85], [7, 8, .85], [8, 9, .85], [8, 10, .85], [10, 11, .85], [0, 12, .85], [12, 13, .85], [7, 14, .55], [2, 15, .55]] },
    { name: 'Pisces', zh: '双鱼', p: [[.3, -.1], [-.9, .4], [-.7, .6], [-.45, .5], [-.5, .25], [-.75, .2], [-1.05, .55], [-1.05, .25], [-.3, .3], [0, .1], [.55, -.25], [.75, -.15], [.95, -.35], [.85, -.65], [.6, -.6], [1.1, -.75], [1.05, -.45], [-.1, .55]],
      e: [[1, 2, .9], [2, 3, .9], [3, 4, .9], [4, 5, .9], [5, 1, .9], [1, 6, .85], [1, 7, .85], [3, 8], [8, 9], [9, 0], [0, 10], [10, 11], [11, 12, .9], [12, 13, .9], [13, 14, .9], [14, 11, .9], [13, 15, .85], [13, 16, .85], [17, 3, .55]] }
  ];
  function degreeOf(edges, n) { var d = new Array(n).fill(0); edges.forEach(function (e) { d[e[0]]++; d[e[1]]++; }); return d; }
  /** 叶星增殖：把 extra 颗星挂到低度数骨节上，方向背离质心，保证最小间距 */
  function growLeaves(points, edges, extra, seed) {
    var i, j, k;
    for (k = 0; k < extra; k++) {
      var n = points.length, deg = degreeOf(edges, n), mx = 0, my = 0;
      for (i = 0; i < n; i++) { mx += points[i][0]; my += points[i][1]; } mx /= n; my /= n;
      // 候选锚：度数 ≤ 2 的点里按 seed 选，越靠外越优先
      var cands = []; for (i = 0; i < n; i++) if (deg[i] <= 2) cands.push(i);
      if (!cands.length) for (i = 0; i < n; i++) cands.push(i);
      var a = cands[Math.floor(rnd(seed + k * 3.7) * cands.length)], P = points[a];
      var away = Math.atan2(P[1] - my, P[0] - mx) + (rnd(seed + k * 5.1) - 0.5) * 1.9, dist = 0.16 + rnd(seed + k * 7.3) * 0.14;
      var np = [P[0] + Math.cos(away) * dist, P[1] + Math.sin(away) * dist];
      // 最小间距斥力（只动新点）
      for (j = 0; j < 12; j++) {
        var moved = false;
        for (i = 0; i < n; i++) { var dx = np[0] - points[i][0], dy = np[1] - points[i][1], d = Math.sqrt(dx * dx + dy * dy) || 0.001; if (d < 0.13) { np[0] += dx / d * (0.13 - d); np[1] += dy / d * (0.13 - d); moved = true; } }
        if (!moved) break;
      }
      points.push(np); edges.push([a, n, 0.55]);
    }
  }
  /** 程序化骨架：主骨折线 → 分枝 → 头环 → 叶星（点序即亮度序） */
  function proceduralGlyph(n, seed) {
    var points = [], edges = [], i;
    var m0 = Math.min(n, 6 + Math.floor(rnd(seed + 1) * 4));                 // 主骨 6–9
    var A = 0.28 + rnd(seed + 2) * 0.3, f = 1 + rnd(seed + 3) * 1.2, ph = rnd(seed + 4) * 6.283, th = rnd(seed + 5) * 3.1416, ct = Math.cos(th), st = Math.sin(th);
    for (i = 0; i < m0; i++) {
      var t = i / (m0 - 1), x = t * 2 - 1 + (rnd(seed + i * 1.3) - 0.5) * 0.08, y = A * Math.sin(t * 3.1416 * f + ph) + (rnd(seed + i * 2.9) - 0.5) * 0.12;
      points.push([x * ct - y * st, x * st + y * ct]);
      if (i) edges.push([i - 1, i]);
    }
    var left = n - m0;
    // 头环：主骨一端周围 3–4 星
    if (left >= 3) {
      var hn = Math.min(left, 3 + (rnd(seed + 6) < 0.5 ? 1 : 0)), head = rnd(seed + 7) < 0.5 ? 0 : m0 - 1, H = points[head], base = points.length;
      var dir = Math.atan2(H[1] - points[head === 0 ? 1 : m0 - 2][1], H[0] - points[head === 0 ? 1 : m0 - 2][0]);
      for (i = 0; i < hn; i++) { var ang = dir + (i - (hn - 1) / 2) * (2.6 / hn) , r = 0.2 + rnd(seed + 8 + i) * 0.08; points.push([H[0] + Math.cos(ang) * r, H[1] + Math.sin(ang) * r]); }
      for (i = 0; i < hn; i++) edges.push([base + i, i + 1 < hn ? base + i + 1 : head, 0.9]);
      edges.push([head, base, 0.9]);
      left -= hn;
    }
    // 分枝：2–4 条，每条 2–4 星
    var nb = Math.min(4, 2 + Math.floor(rnd(seed + 9) * 3));
    for (var b = 0; b < nb && left >= 2; b++) {
      var at = 1 + Math.floor(rnd(seed + 10 + b) * (m0 - 2)), len = Math.min(left, 2 + Math.floor(rnd(seed + 20 + b) * 3));
      var P = points[at], Q = points[at + 1], tx = Q[0] - P[0], ty = Q[1] - P[1], tl = Math.sqrt(tx * tx + ty * ty) || 1;
      var side = rnd(seed + 30 + b) < 0.5 ? 1 : -1, nx = -ty / tl * side, ny = tx / tl * side, prev = at, drift = (rnd(seed + 40 + b) - 0.5) * 0.9;
      for (i = 0; i < len; i++) {
        var step = 0.2 + rnd(seed + 50 + b * 7 + i) * 0.08, ca = Math.cos(drift * i), sa = Math.sin(drift * i);
        var dx = (nx * ca - ny * sa) * step, dy = (nx * sa + ny * ca) * step, L = points[prev];
        points.push([L[0] + dx, L[1] + dy]); edges.push([prev, points.length - 1, 0.85]); prev = points.length - 1;
      }
      left -= len;
    }
    if (left > 0) growLeaves(points, edges, left, seed + 99);
    return { points: points, edges: edges };
  }
  /** 大星座字形：n ≥ 14 时用模板 + 增殖或程序化骨架；返回 {points, edges}（点序 = 亮度序，已归一化） */
  function bigGlyph(n, seed, avoid) {
    var g;
    // v22：永远用具名形象模板（不再程序化随机骨架）；优先选最贴近人数的（叶星越少形象越清楚），相邻座不重样
    var fits = BIG_TPL.filter(function (t) { return t.p.length <= n && (!avoid || avoid.indexOf(t.name) < 0); });
    if (!fits.length) fits = BIG_TPL.filter(function (t) { return t.p.length <= n; });
    if (!fits.length) fits = BIG_TPL.slice(0, 3);
    var maxSz = 0; fits.forEach(function (t) { maxSz = Math.max(maxSz, t.p.length); });
    var close = fits.filter(function (t) { return n - t.p.length <= Math.max(6, n - maxSz + 4); });
    if (close.length) fits = close;
    var tpl = fits[Math.floor(rnd(seed * 0.53 + 2) * fits.length)];
    g = { points: tpl.p.map(function (p) { return [p[0], p[1]]; }), edges: tpl.e.map(function (e) { return e.length > 2 ? [e[0], e[1], e[2]] : [e[0], e[1]]; }) };
    if (n > g.points.length) growLeaves(g.points, g.edges, n - g.points.length, seed + 7);
    g.tpl = tpl.name; g.figure = { en: tpl.name.toUpperCase(), zh: tpl.zh || tpl.name };
    // 确定性姿态 + 镜像 + 重心归零 + 归一化
    var rot = (rnd(seed * 1.3 + 2) - 0.5) * 0.9, mir = rnd(seed * 2.1 + 5) < 0.5 ? -1 : 1, cr = Math.cos(rot), sr = Math.sin(rot);
    var mx = 0, my = 0; g.points.forEach(function (p) { mx += p[0]; my += p[1]; }); mx /= g.points.length; my /= g.points.length;
    g.points = g.points.map(function (p) { var x = (p[0] - mx) * mir, y = p[1] - my; return [x * cr - y * sr, x * sr + y * cr]; });
    var mag = 0; g.points.forEach(function (p) { mag = Math.max(mag, Math.sqrt(p[0] * p[0] + p[1] * p[1])); });
    if (mag > 0) g.points = g.points.map(function (p) { return [p[0] / mag, p[1] / mag]; });
    return g;
  }
  var KNOT_MIN = 14, KNOT_MAX = 36, KNOT_PREF = 26;
  /** 把一段成员切成 14–36 星的座；n ≤ 36 一座；否则均分成 ceil(n/26) 座 */
  function splitRun(n) {
    if (n <= KNOT_MAX) return [n];
    var k = Math.ceil(n / KNOT_PREF), base = Math.floor(n / k), extra = n - base * k, out = [];
    for (var i = 0; i < k; i++) out.push(base + (i < extra ? 1 : 0));
    return out;
  }
  var ROAD_PITCH = 0.46;                      // 星盘前倾（弧度）：屏幕上方远、下方近（v21 加深）
  function roadKnotSizes(n, seed, tail) {
    var out = [], left = n, i = 0;
    if (n <= 0) return out;
    if (tail) { while (left > 0) { var k = left >= 7 ? 3 + Math.floor(rnd(seed + i) * 3) : left >= 5 ? Math.min(left, 3 + Math.floor(rnd(seed + i) * 2)) : left; out.push(k); left -= k; i++; } return out; }
    if (n <= 9) return [n];
    var pool = [7, 5, 8, 6, 9, 4, 7, 5];
    while (left > 0) {
      var k2 = pool[Math.floor(rnd(seed + i * 1.7) * pool.length)];
      if (left - k2 < 3 && left - k2 > 0) k2 = left <= 9 ? left : Math.max(4, k2 - 2);
      k2 = Math.min(k2, left); out.push(k2); left -= k2; i++;
    }
    return out;
  }
  function rot3(p, ax, ay, az) {
    var x = p[0], y = p[1], z = p[2], c, s, t;
    c = Math.cos(az); s = Math.sin(az); t = x * c - y * s; y = x * s + y * c; x = t;
    c = Math.cos(ax); s = Math.sin(ax); t = y * c - z * s; z = y * s + z * c; y = t;
    c = Math.cos(ay); s = Math.sin(ay); t = x * c + z * s; z = -x * s + z * c; x = t;
    return [x, y, z];
  }
  function layoutRoad(chars, rels, campDefs, tierOf, weightOf) {
    var n = chars.length, i, j, idx = {};
    SPREAD = n <= 12 ? 1.7 : n <= 26 ? 1.4 : n <= 80 ? 1.15 : n <= 300 ? 1 : 0.9;
    chars.forEach(function (c, q) { idx[c.name] = q; });
    var camps = groupCamps(chars, campDefs), tier = chars.map(tierOf), w = chars.map(weightOf);
    camps.forEach(function (cp) {
      cp.members.sort(function (a, b) { return w[b] - w[a]; });
      cp.core = cp.members.filter(function (q) { return tier[q] < 4; });
      cp.tail = cp.members.filter(function (q) { return tier[q] >= 4; });
      cp.w = cp.core.reduce(function (s, q) { return s + w[q]; }, 0) + cp.tail.length * 0.5;
      cp.lead = cp.members[0];
      if (!cp.stance) {
        if (cp.name === FIELD) cp.stance = '';
        else if (cp.members.some(function (q) { return chars[q].role === '主角'; })) cp.stance = '主角方';
        else {
          var votes = {}; cp.members.forEach(function (q) { var s = normStance(chars[q].stance); if (s) votes[s] = (votes[s] || 0) + 1 + w[q] / 100; });
          var best = ''; Object.keys(votes).forEach(function (s) { if (!best || votes[s] > votes[best]) best = s; });
          cp.stance = best || (cp.members.some(function (q) { return chars[q].role === '反派'; }) ? '对立' : '中立');
        }
      }
      cp.color = COLOR[cp.stance] || COLOR[''];
      cp.r = 40; cp.knots = [];
    });
    var order = camps.slice().sort(function (a, b) { var pa = a.stance === '主角方' ? 1 : 0, pb = b.stance === '主角方' ? 1 : 0; if (pa !== pb) return pb - pa; if ((a.name === FIELD) !== (b.name === FIELD)) return a.name === FIELD ? 1 : -1; return b.w - a.w; });
    // 节序（v21）：每座 14–36 星。阵营 = 核心 + 长尾（按权重）为一段；≥14 人的阵营自成一座或均分成若干座；
    // 人少的阵营按顺序并成一座（混色星座）；全书不足 14 人则全员一座。
    var knots = [], pending = [];
    function campOfMost(mem) { var cnt = {}, best = null; mem.forEach(function (q) { var cp = camps.filter(function (c) { return c.members.indexOf(q) >= 0; })[0]; if (!cp) return; cnt[cp.name] = (cnt[cp.name] || 0) + 1; if (!best || cnt[cp.name] > cnt[best.name]) best = cp; }); return best || camps[0]; }
    function pushKnot(mem, cp) { knots.push({ cp: cp || campOfMost(mem), members: mem, tail: false, ki: knots.length, mixed: !cp }); }
    function flushPending(force) {
      if (!pending.length) return;
      if (pending.length >= KNOT_MIN || force) { var sizes = splitRun(pending.length), at = 0; sizes.forEach(function (k) { pushKnot(pending.slice(at, at + k)); at += k; }); pending = []; }
    }
    order.forEach(function (cp) {
      var run = cp.core.concat(cp.tail);
      if (!run.length) return;
      if (run.length >= KNOT_MIN) {
        if (pending.length >= 7) flushPending(true); else if (pending.length) { run = pending.concat(run); pending = []; }
        var sizes = splitRun(run.length), at = 0;
        sizes.forEach(function (k) { pushKnot(run.slice(at, at + k), sizes.length === 1 && !cp.__mixed ? cp : null); at += k; });
      } else {
        pending = pending.concat(run);
        if (pending.length >= KNOT_MIN) flushPending(true);
      }
    });
    if (pending.length) {
      var last = knots[knots.length - 1];
      if (last && pending.length < 7 && last.members.length + pending.length <= KNOT_MAX) { last.members = last.members.concat(pending); last.members.sort(function (a, b) { return w[b] - w[a]; }); pending = []; }
      else flushPending(true);
    }
    knots.forEach(function (kn) { kn.members.sort(function (a, b) { return w[b] - w[a]; }); });
    if (!knots.length) return { camps: camps, pos: [], halfW: 200, halfH: 160, guides: [], glyphEdges: [], center: camps[0], chain: [], knots: [], mode: 'road' };
    // 每节：字形 → 半径 → 独立 3D 姿态
    var recent = [];
    knots.forEach(function (kn, ki) {
      var m = kn.members.length, seed = hash(kn.cp.name) + ki * 131 + (kn.tail ? 9999 : 0);
      kn.glyph = m >= KNOT_MIN ? bigGlyph(m, seed, recent.slice(-3)) : constellationGlyph(Math.min(12, m), seed);
      if (kn.glyph.tpl) recent.push(kn.glyph.tpl);
      kn.figure = kn.glyph.figure || null;
      kn.R = SPREAD * (m <= 1 ? 22 : m < KNOT_MIN ? 30 + 30 * Math.sqrt(m) : 44 + 26 * Math.sqrt(m));
      kn.ax = (rnd(seed * 0.7 + 1) - 0.5) * 0.9;      // 俯仰
      kn.ay = (rnd(seed * 0.9 + 2) - 0.5) * 0.9;      // 偏航
      kn.az = (rnd(seed * 1.1 + 3) - 0.5) * 0.4;      // 滚转
      kn.color = kn.cp.color;
      kn.seed = seed;
    });
    // 节心：向日葵（phyllotaxis）铺满圆盘 + 推开消重叠。
    // v21 的阿基米德螺旋有两个硬伤：圈距被「最大那一座」绑架（G = 2·Rmax + GAP），
    // 起始半径又除了一次纵向压缩（r0 /= EV）——于是中心空出一大片、各座只沿外环排，
    // 看上去就是「星座相聚过远」。向日葵按面积均匀铺点，中心也用得满，邻座只留净距。
    var GAP = 22 * SPREAD;                                  // 座与座之间的净距（原来是 54）
    var EV = 0.64;                                          // 纵向压缩：贴合 16:10 画幅（圆盘会在宽屏两侧留大片空白）
    var K = knots.length, centers = [], GOLD = 2.399963229728653;
    var PACK = 0.70;                                        // 铺点密度（<1 留出推开的余量）
    if (K === 1) centers.push([0, 0]);
    else {
      var acc = 0;
      for (i = 0; i < K; i++) {
        var e = knots[i].R + GAP * 0.5;
        // 面积累加：半径 ∝ sqrt(已铺面积)，大座自然占更大的环带，小座挨得更紧
        var rMid = Math.sqrt((acc + e * e * 0.5) / PACK), a = i * GOLD;
        acc += e * e;
        centers.push([Math.cos(a) * rMid, Math.sin(a) * rMid * EV]);
      }
      // 推开：向日葵按面积均匀，但半径差大时仍可能咬合。沿连心线推到刚好留净距。
      for (var it = 0; it < 90; it++) {
        var moved = 0;
        for (i = 0; i < K; i++) for (j = i + 1; j < K; j++) {
          var ci = centers[i], cj = centers[j];
          var dx2 = cj[0] - ci[0], dy2 = (cj[1] - ci[1]) / EV;      // 在未压缩空间里判圆
          var dd = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 0.001;
          var need2 = knots[i].R + knots[j].R + GAP;
          if (dd < need2) {
            var push = (need2 - dd) / 2, ux = dx2 / dd, uy = dy2 / dd;
            ci[0] -= ux * push; ci[1] -= uy * push * EV;
            cj[0] += ux * push; cj[1] += uy * push * EV;
            moved++;
          }
        }
        if (!moved) break;
      }
    }
    // 重心归零：把外接框中心移回原点，画面上下左右均衡
    (function () {
      var minU = 1e9, maxU = -1e9, minV = 1e9, maxV = -1e9;
      knots.forEach(function (kn, ki) { var c = centers[ki]; minU = Math.min(minU, c[0] - kn.R); maxU = Math.max(maxU, c[0] + kn.R); minV = Math.min(minV, c[1] - kn.R); maxV = Math.max(maxV, c[1] + kn.R); });
      var du = (minU + maxU) / 2, dv = (minV + maxV) / 2;
      centers = centers.map(function (c) { return [c[0] - du, c[1] - dv]; });
    })();
    // 星路次序：向日葵按黄金角铺点，相邻编号在画面上并不相邻——若还按编号连桥，
    // 桥会横穿整个星盘。这里改成「就近取下一座」的贪心路径，既保持一座接一座，走线也干净。
    var roadOrder = (function () {
      if (K <= 2) return knots.map(function (_, q) { return q; });
      var used = new Array(K), path = [0]; used[0] = 1;
      for (var s = 1; s < K; s++) {
        var cur = centers[path[path.length - 1]], bi = -1, bdd = 1e18;
        for (var t2 = 0; t2 < K; t2++) {
          if (used[t2]) continue;
          var ddx = centers[t2][0] - cur[0], ddy = centers[t2][1] - cur[1], dd2 = ddx * ddx + ddy * ddy;
          if (dd2 < bdd) { bdd = dd2; bi = t2; }
        }
        used[bi] = 1; path.push(bi);
      }
      return path;
    })();
    var seqOf = new Array(K);
    roadOrder.forEach(function (ki2, s2) { seqOf[ki2] = s2; });
    // 纵深量级要和画面尺度成比例：固定 ±280 相对 2000+ 的取景距离只有 ~9% 的透视差，
    // 眼睛读不出立体（用户反馈「没有 3d 纵深」）。按星盘半径给，深度差就真的看得见。
    var discR = 1; knots.forEach(function (kn, ki3) { discR = Math.max(discR, Math.sqrt(centers[ki3][0] * centers[ki3][0] + Math.pow(centers[ki3][1] / EV, 2)) + kn.R); });
    var ZSPAN = Math.max(300, Math.min(1500, discR * 0.92));
    // 落点：节心 (u,v) → 成员 3D 点；外圈退入深空；整盘前倾
    var pos = new Array(n), glyphEdges = [], guides = [], chain = [];
    var cP = Math.cos(ROAD_PITCH), sP = Math.sin(ROAD_PITCH);
    function toWorld(u, v, z) { return { x: u, y: v * cP + z * sP, z: -v * sP + z * cP }; }
    knots.forEach(function (kn, ki) {
      var c = centers[ki], ru = Math.sqrt(c[0] * c[0] + c[1] * c[1]);
      // 真 3D 纵深：碗形（外圈退入深空）+ 按星盘半径给的深度抖动。
      // 深度差与取景距离同量级，星等、亮度、透视三条线索同时起作用，拖动时有明显视差。
      kn.seq = seqOf[ki] == null ? ki : seqOf[ki];
      kn.cu = c[0]; kn.cv = c[1];
      kn.cz = -ru * 0.34 + (rnd(kn.seed * 0.11 + 3) - 0.5) * ZSPAN + Math.sin(kn.seq * 1.7) * ZSPAN * 0.06;
      kn.local = [];
      kn.members.forEach(function (q, m) {
        var p = kn.glyph.points[Math.min(m, kn.glyph.points.length - 1)] || [0, 0];
        var t = tier[q], zt = t === 0 ? 26 : t === 1 ? 12 : t === 2 ? 0 : t === 3 ? -10 : -20;
        var lp = rot3([p[0] * kn.R * 0.92, p[1] * kn.R * 1.02, (rnd(kn.seed + m * 2.3) - 0.5) * kn.R * 0.7], kn.ax, kn.ay, kn.az);   // 座内星体前后错落 ±0.35R
        kn.local.push(lp);
        var wpos = toWorld(kn.cu + lp[0], kn.cv + lp[1], kn.cz + lp[2] + zt);
        pos[q] = wpos; chain.push(q);
      });
      var wc = toWorld(kn.cu, kn.cv, kn.cz); kn.cx = wc.x; kn.cy = wc.y; kn.czw = wc.z;
      // 微星尘：每座内部撒 8–30 颗暗星（真实星图的暗星），落在字形平面附近、略退后；长尾座不撒
      kn.dust = [];
      if (!kn.tail && kn.members.length >= 2) {
        var nd = Math.min(30, 6 + kn.members.length * 3), sd = kn.seed * 0.37 + 11;
        for (var di = 0; di < nd; di++) {
          var ang = rnd(sd + di * 1.13) * 6.283, rr = Math.sqrt(rnd(sd + di * 2.71)) * kn.R * 0.95;
          var dp = rot3([Math.cos(ang) * rr, Math.sin(ang) * rr * 0.9, -6 - rnd(sd + di * 3.3) * 26], kn.ax, kn.ay, kn.az);
          var dw = toWorld(kn.cu + dp[0], kn.cv + dp[1], kn.cz + dp[2]);
          kn.dust.push({ x: dw.x, y: dw.y, z: dw.z, s: (1.3 + rnd(sd + di * 5.9) * 1.9) * SPREAD, a: 0.28 + rnd(sd + di * 7.7) * 0.34, color: kn.color });
        }
      }
      kn.glyph.edges.forEach(function (e) {
        var a = kn.members[e[0]], b = kn.members[e[1]]; if (a == null || b == null) return;
        glyphEdges.push({ a: a, b: b, rel: false, color: kn.color, knot: true, tail: kn.tail, seq: kn.seq, w: e[2] || 1 });
      });
      // 一座之内没有边的（1–2 星）不需要额外处理：桥会把它们接进路里
    });
    // v26.1：取消「桥」—— 原来沿星路次序把相邻两座最近的一对星连起来，画面上是一条把所有星座
    // 首尾串成一串的绳子。用户明确要求取消：真实星图里星座之间本来就没有连线，各自独立才有星象的
    // 庄严感；座与座的先后关系改由**轮流点灯**（时间上的次序）承担，不再靠画一条线（空间上的次序）。
    // roadOrder / roadPath 仍然保留：尘带、呼吸相位、入场次序都要用它。
    // 阵营描述量：质心、段首座名锚点（第一节顶缘外侧偏左）
    camps.forEach(function (cp) {
      var mem = cp.members.filter(function (q) { return pos[q]; }); if (!mem.length) { cp.cx = cp.cy = cp.cz = 0; cp.labelX = cp.labelY = 0; cp.labelZ = 10; return; }
      var sx = 0, sy = 0; mem.forEach(function (q) { sx += pos[q].x; sy += pos[q].y; });
      cp.cx = sx / mem.length; cp.cy = sy / mem.length; cp.cz = 0;
      // 座名锚点：该阵营自己的第一座；并入混色座的小阵营则锚在自己成员的最高星上方（不再假定每个阵营都有整座）
      var first = null; knots.forEach(function (kn) { if (!first && kn.cp === cp && !kn.mixed) first = kn; });
      var host = first || knots.filter(function (kn) { return kn.members.indexOf(cp.lead) >= 0; })[0] || knots[0];
      var anchorMem = first ? first.members : mem;
      var top = -1e9, topX = 0, topZ = 0;
      anchorMem.forEach(function (q) { if (pos[q] && pos[q].y > top) { top = pos[q].y; topX = pos[q].x; topZ = pos[q].z; } });
      cp.labelX = first ? host.cx - host.R * 0.34 : topX - 30 * SPREAD; cp.labelY = top + (first ? 62 : 40) * SPREAD; cp.labelZ = topZ + 6;
      cp.fitRx = cp.fitRy = host.R; cp.knots = knots.filter(function (kn) { return kn.cp === cp || kn.members.indexOf(cp.lead) >= 0; }); cp.figure = host.figure || null;
    });
    var halfW = 0, halfH = 0;
    pos.forEach(function (pp) { if (!pp) return; halfW = Math.max(halfW, Math.abs(pp.x) + 70); halfH = Math.max(halfH, Math.abs(pp.y) + 60); });
    var center = order[0] || camps[0], rimR = 0;
    // 沿环贴着最外一座（原来外扩 1.2 倍，压紧后就显得「一个大圈里装着一小团」）
    var rimV = 0; knots.forEach(function (kn) { rimR = Math.max(rimR, Math.abs(kn.cu) + kn.R * 1.04); rimV = Math.max(rimV, Math.abs(kn.cv) + kn.R * 1.02); });
    // roadPath：按就近路径排好的座序，尘带 / 呼吸行波都要用它，否则会横穿星盘
    var roadPath = roadOrder.map(function (ki5) { return knots[ki5]; }).filter(Boolean);
    return { camps: camps, pos: pos, halfW: halfW, halfH: halfH, guides: guides, glyphEdges: glyphEdges, center: center, chain: chain, knots: knots, roadPath: roadPath, mode: 'road', pitch: ROAD_PITCH, rimR: rimR, rimV: Math.max(rimV, rimR * 0.5), tplNames: knots.map(function (k) { return k.glyph.tpl || 'small'; }) };
  }
  function mixColor(a, b) { if (a === b) return a; var ar = a >> 16 & 255, ag = a >> 8 & 255, ab = a & 255, br = b >> 16 & 255, bg = b >> 8 & 255, bb = b & 255; return ((ar + br) >> 1) << 16 | ((ag + bg) >> 1) << 8 | ((ab + bb) >> 1); }

  /** 叙事功能枢：按剧情类型统计 → 右列节点用；返回 [{kind, en, count, top:[{name,n}], share}] */
  var KIND_EN = { 抉择: 'DECISION', 冲突: 'CONFLICT', 转折: 'TURN', 关系: 'BOND', 高燃: 'CLIMAX', 领悟: 'INSIGHT', 日常: 'DAILY' };
  var KIND_ORDER = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
  var KIND_DEF = {
    高燃: '情绪与场面的峰值：决战、告白、逆转、牺牲——推动读者肾上腺素的时刻',
    转折: '改变走向的节点：真相揭露、阵营变动、命运拐点',
    抉择: '人物在两难之间做出的选择，暴露价值序与底线',
    冲突: '正面对抗：争吵、交锋、博弈、战斗',
    关系: '关系的建立、深化、破裂或重组',
    领悟: '认知的更新：想通了什么、看清了谁、接受了什么',
    日常: '铺垫与呼吸：生活场景、闲笔、日常互动'
  };
  function hubs(events, chars) {
    var by = {}, tot = Math.max(1, events.length);
    events.forEach(function (e) { var k = KIND_ORDER.indexOf(e.kind) >= 0 ? e.kind : '日常'; var h = by[k] = by[k] || { kind: k, count: 0, who: {} }; h.count++; (e.characters || []).forEach(function (nm) { h.who[nm] = (h.who[nm] || 0) + 1; }); });
    return KIND_ORDER.filter(function (k) { return by[k]; }).map(function (k) {
      var h = by[k], top = Object.keys(h.who).sort(function (a, b) { return h.who[b] - h.who[a]; }).slice(0, 5).map(function (nm) { return { name: nm, n: h.who[nm] }; });
      return { kind: k, en: KIND_EN[k], count: h.count, share: h.count / tot, top: top, who: h.who };
    });
  }


  /** 阵营回填（旧图谱无 camp 字段时的前端兜底，与 serve.py infer_camps 同思路）：
   *  高重要度角色各自成种子 → 友好关系标签传播 → 连通分量成「X 一系」→ 孤立者散星。只填空缺，不覆盖已有 camp。 */
  var HOSTILE = /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计|对手|竞争|追捕|追查|审讯/;
  var FRIEND = /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱|夫|妻|情|眷|婚|主仆|上下级|部下|下属|同僚|同门/;
  function inferCamps(chars, rels) {
    var by = {}, camp = {}, order = chars.slice().sort(function (a, b) { return (b.importance || 0) - (a.importance || 0) || (a.name < b.name ? -1 : 1); });
    chars.forEach(function (c) { by[c.name] = c; camp[c.name] = String(c.camp || '').trim(); if (camp[c.name] === FIELD) camp[c.name] = ''; });
    var nbr = {};
    rels.forEach(function (r) {
      if (!by[r.a] || !by[r.b] || r.a === r.b) return;
      var k = String(r.kind || ''), w = (+r.strength || 0.5);
      if (HOSTILE.test(k) && !FRIEND.test(k)) return;
      (nbr[r.a] = nbr[r.a] || {})[r.b] = (nbr[r.a][r.b] || 0) + w; (nbr[r.b] = nbr[r.b] || {})[r.a] = (nbr[r.b][r.a] || 0) + w;
    });
    // 种子：主角 / 反派 / 重要度 ≥70 且无阵营者各自立系（避免把对立领袖并进一个社区）
    order.forEach(function (c) { if (!camp[c.name] && (c.role === '主角' || c.role === '反派' || (c.importance || 0) >= 70) && Object.keys(nbr[c.name] || {}).length) camp[c.name] = c.name + ' 一系'; });
    for (var it = 0; it < 8; it++) {
      var changed = 0;
      order.forEach(function (c) {
        if (camp[c.name]) return;
        var votes = {}, best = '';
        Object.keys(nbr[c.name] || {}).forEach(function (m) { var cm = camp[m]; if (!cm) return; votes[cm] = (votes[cm] || 0) + nbr[c.name][m] * (1 + (by[m].importance || 0) / 100); });
        Object.keys(votes).forEach(function (k) { if (!best || votes[k] > votes[best] || (votes[k] === votes[best] && k < best)) best = k; });
        if (best) { camp[c.name] = best; changed++; }
      });
      if (!changed) break;
    }
    // 种子合并：两个「X 一系」的主星之间有友好关系（且不是主角对反派）→ 小系并入大系（诸葛亮 一系 → 刘备 一系）
    var seedOf = {}; order.forEach(function (c) { if (camp[c.name] === c.name + ' 一系') seedOf[c.name] = 1; });
    var seedNames = Object.keys(seedOf).sort(function (a, b) { return (by[b].importance || 0) - (by[a].importance || 0); });
    var merged = true, guard = 0;
    while (merged && guard++ < 12) {
      merged = false;
      for (var si = 0; si < seedNames.length && !merged; si++) for (var sj = si + 1; sj < seedNames.length && !merged; sj++) {
        var A = seedNames[si], B = seedNames[sj], wAB = (nbr[A] || {})[B] || 0;
        if (wAB < 0.5) continue;
        if ((by[A].role === '主角' && by[B].role === '反派') || (by[A].role === '反派' && by[B].role === '主角')) continue;
        var from = camp[B], to = camp[A]; if (from === to) continue;
        chars.forEach(function (c) { if (camp[c.name] === from) camp[c.name] = to; });
        seedNames.splice(sj, 1); merged = true;
      }
    }
    // 剩余：友好连通分量 ≥2 人成系
    var seen = {};
    order.forEach(function (c) {
      if (camp[c.name] || seen[c.name]) return;
      var comp = [], st = [c.name];
      while (st.length) { var x = st.pop(); if (seen[x] || camp[x]) continue; seen[x] = 1; comp.push(x); Object.keys(nbr[x] || {}).forEach(function (m) { if (!seen[m] && !camp[m]) st.push(m); }); }
      if (comp.length >= 2) { var lead = comp.slice().sort(function (a, b) { return (by[b].importance || 0) - (by[a].importance || 0); })[0]; comp.forEach(function (x) { camp[x] = lead + ' 一系'; }); }
    });
    var sizes = {}; chars.forEach(function (c) { var k = camp[c.name] || FIELD; sizes[k] = (sizes[k] || 0) + 1; });
    chars.forEach(function (c) { var k = camp[c.name] || FIELD; if (/ 一系$/.test(k) && sizes[k] === 1) camp[c.name] = k.slice(0, -3); });   // 单人不成“系”：星座名就用角色名
    var defs = {}, list = [];
    chars.forEach(function (c) { c.camp = camp[c.name] || FIELD; if (!defs[c.camp]) { defs[c.camp] = { name: c.camp, stance: '', brief: '', members: [], size: 0, lead: '' }; list.push(defs[c.camp]); } defs[c.camp].members.push(c.name); });
    // 阵营数上限 9（散星不计）：小阵营并入散星
    var real = list.filter(function (d) { return d.name !== FIELD; }).sort(function (a, b) { return sumImp(b) - sumImp(a); });
    function sumImp(d) { return d.members.reduce(function (s, m) { return s + (by[m].importance || 0); }, 0); }
    if (real.length > 9) { var fd = defs[FIELD] || (defs[FIELD] = { name: FIELD, stance: '', brief: '', members: [], size: 0, lead: '' }); real.slice(9).forEach(function (d) { d.members.forEach(function (m) { by[m].camp = FIELD; fd.members.push(m); }); }); real = real.slice(0, 9); if (list.indexOf(fd) < 0) list.push(fd); }
    var out = real.concat(defs[FIELD] && defs[FIELD].members.length ? [defs[FIELD]] : []);
    var protag = {}; chars.forEach(function (c) { if (c.role === '主角') protag[c.name] = 1; });
    out.forEach(function (d) {
      d.size = d.members.length; d.lead = d.members.slice().sort(function (a, b) { return (by[b].importance || 0) - (by[a].importance || 0); })[0];
      if (d.name === FIELD) { d.stance = ''; return; }
      if (d.members.some(function (m) { return protag[m]; })) { d.stance = '主角方'; return; }
      var hostile = 0, friendly = 0;
      rels.forEach(function (r) { var inA = d.members.indexOf(r.a) >= 0, inB = d.members.indexOf(r.b) >= 0; if ((inA && protag[r.b]) || (inB && protag[r.a])) { if (HOSTILE.test(r.kind || '')) hostile++; else if (FRIEND.test(r.kind || '')) friendly++; } });
      d.stance = hostile && friendly ? '摇摆' : hostile ? '对立' : friendly ? '盟友' : d.members.some(function (m) { return by[m].role === '反派'; }) ? '对立' : '中立';
      d.members.forEach(function (m) { if (!normStance(by[m].stance)) by[m].stance = d.stance; });
    });
    return out;
  }

  /* ── 平面天球图（layoutSky）──────────────────────────────────────────────────────────
   * 星座 = 一张前倾的平面天球：主角团（小团）居盘心小圆，其余每个分组一个扇区，12 点起顺时针（与星盘时间环同向）；
   * 扇区角宽 ∝ 人数^0.82（有下限）；扇区内用「最佳候选」蓝噪声等距铺点，咖位高者落在扇区中心，长尾在外缘；
   * 组内核心星按最短生成树连成星座线（有真实关系的边优先）。盘面坐标 (u 右, v 上)，θ 从 +v 顺时针；
   * toWorld 与星盘同一前倾（scene.rimInfo 的 pitch），所以星域、团名带、星盘环在同一平面上严丝合缝。 */
  var SKY_PITCH = 0.36;
  var SKY_ORDER = { 主角方: 0, 盟友: 1, 中立: 2, 摇摆: 3, 对立: 4, '': 5 };
  function mulberry(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function skyRegion(ra, rb, a0, a1, m) {
    var full = a1 - a0 >= Math.PI * 2 - 1e-6, r0 = Math.max(0, ra + (ra > 0 ? m : 0)), r1 = Math.max(r0 + 1, rb - m);
    return {
      area: (a1 - a0) / 2 * (r1 * r1 - r0 * r0),
      sample: function (rng) {
        var r = Math.sqrt(r0 * r0 + rng() * (r1 * r1 - r0 * r0)), am = full ? 0 : Math.min((a1 - a0) * 0.45, m / Math.max(r, 1));
        var th = a0 + am + rng() * Math.max(0, a1 - a0 - 2 * am);
        return [Math.sin(th) * r, Math.cos(th) * r];
      }
    };
  }
  /* 最佳候选蓝噪声：逐点从 K 个均匀候选里挑离已有点最远的一个；网格加速，只看 3 格内 */
  function skyBlue(n, region, spacing, rng, first) {
    var pts = [], cell = Math.max(4, spacing), grid = {}, K = n > 300 ? 7 : n > 80 ? 10 : 14, cap = cell * 3;
    function put(p) { var k = Math.floor(p[0] / cell) + ',' + Math.floor(p[1] / cell); (grid[k] = grid[k] || []).push(p); pts.push(p); }
    function near(x, y) {
      var cx = Math.floor(x / cell), cy = Math.floor(y / cell), best = cap * cap;
      for (var dx = -3; dx <= 3; dx++) for (var dy = -3; dy <= 3; dy++) {
        var list = grid[(cx + dx) + ',' + (cy + dy)]; if (!list) continue;
        for (var i = 0; i < list.length; i++) { var ex = list[i][0] - x, ey = list[i][1] - y, d = ex * ex + ey * ey; if (d < best) best = d; }
      }
      return best;
    }
    if (first && n > 0) put(first);
    while (pts.length < n) {
      var bp = null, bd = -1;
      for (var k = 0; k < K; k++) { var c = region.sample(rng), d = pts.length ? near(c[0], c[1]) : cap * cap; if (d > bd) { bd = d; bp = c; } }
      put(bp);
    }
    return pts;
  }
  function layoutSky(chars, rels, campDefs, tierOf, weightOf) {
    var n = chars.length, idx = {}, defColor = {};
    chars.forEach(function (c, q) { idx[c.name] = q; });
    (campDefs || []).forEach(function (d) { if (d && d.name && d.color != null) defColor[d.name] = d.color; });
    var camps = groupCamps(chars, campDefs), tier = chars.map(tierOf), w = chars.map(weightOf);
    camps.forEach(function (cp) {
      cp.members.sort(function (a, b) { return w[b] - w[a] || a - b; });
      cp.core = cp.members.filter(function (q) { return tier[q] < 4; });
      cp.tail = cp.members.filter(function (q) { return tier[q] >= 4; });
      cp.w = cp.core.reduce(function (s, q) { return s + w[q]; }, 0) + cp.tail.length * 0.5;
      cp.lead = cp.members[0];
      if (!cp.stance) {
        if (cp.name === FIELD) cp.stance = '';
        else if (cp.members.some(function (q) { return chars[q].role === '主角'; })) cp.stance = '主角方';
        else {
          var votes = {}; cp.members.forEach(function (q) { var s = normStance(chars[q].stance); if (s) votes[s] = (votes[s] || 0) + 1 + w[q] / 100; });
          var best = ''; Object.keys(votes).forEach(function (s) { if (!best || votes[s] > votes[best]) best = s; });
          cp.stance = best || (cp.members.some(function (q) { return chars[q].role === '反派'; }) ? '对立' : '中立');
        }
      }
      cp.color = defColor[cp.name] != null ? defColor[cp.name] : (COLOR[cp.stance] || COLOR['']);
      cp.knots = [];
    });
    if (!n || !camps.length) return { camps: camps, pos: [], halfW: 300, halfH: 240, guides: [], glyphEdges: [], center: camps[0] || null, chain: [], knots: [], roadPath: [], mode: 'sky', pitch: SKY_PITCH, rimR: 300, rimV: 300, tplNames: [], sky: { R: 300, sectors: [] } };
    // 盘心：全书最重的人所在的分组，且它足够小（≤ max(8, 12%)）才居中；否则全员走扇区
    var topQ = 0; for (var q0 = 1; q0 < n; q0++) if (w[q0] > w[topQ]) topQ = q0;
    var coreCp = camps.filter(function (cp) { return cp.members.indexOf(topQ) >= 0; })[0] || null;
    if (!coreCp || coreCp.name === FIELD || coreCp.members.length > Math.max(8, n * 0.12) || camps.length < 2) coreCp = null;
    var ring = camps.filter(function (cp) { return cp !== coreCp; }).sort(function (a, b) {
      if ((a.name === FIELD) !== (b.name === FIELD)) return a.name === FIELD ? 1 : -1;
      var sa = SKY_ORDER[a.stance] == null ? 5 : SKY_ORDER[a.stance], sb = SKY_ORDER[b.stance] == null ? 5 : SKY_ORDER[b.stance];
      return sa - sb || b.members.length - a.members.length || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
    });
    /* 立场色族：同一立场的第 k 个组取族里第 k 个兄弟色——「敌我」语义不变，同立场的几股势力也分得开（三国四个对立团不再同色） */
    if (window.CLSkyTokens && window.CLSkyTokens.groupHex) {
      var famK = {};
      (coreCp ? [coreCp] : []).concat(ring).forEach(function (cp) {
        if (defColor[cp.name] != null) return;
        var st = cp.name === FIELD ? '' : cp.stance || '', k = famK[st] || 0;
        famK[st] = k + 1; cp.color = window.CLSkyTokens.groupHex(st, k);
      });
    }
    function effN(cp) { return cp.core.length + cp.tail.length * 0.45; }
    var s0 = n <= 12 ? 72 : n <= 30 ? 62 : n <= 80 ? 54 : n <= 300 ? 48 : 44, DENS = 1.3;
    var rc = 0;
    if (coreCp) rc = coreCp.members.length <= 1 ? s0 * 0.6 : Math.max(s0 * 0.9, Math.sqrt(effN(coreCp) * 0.8 * s0 * s0 / Math.PI) + s0 * 0.3);   // 盘心更紧：主角团是一枚亮核，不是一块大饼
    var ra = coreCp ? rc + s0 * 0.75 : s0 * 1.3;   // 无盘心时留一个小空心轮毂，扇区尖端不挤成一点
    var ringN = ring.reduce(function (t, cp) { return t + effN(cp); }, 0);
    // 角宽：∝ 人数^0.82，下限 minA（小团也写得下名字）
    var TAU = Math.PI * 2, K = ring.length, wts = ring.map(function (cp) { return Math.pow(Math.max(1, cp.members.length), 0.82); });
    var minA = K ? Math.min(0.30, TAU * 0.5 / K) : 0, fixed = ring.map(function () { return false; }), fixedSum = 0, freeSum = 0;
    for (var it = 0; it < 8; it++) {
      fixedSum = 0; freeSum = 0;
      ring.forEach(function (_, i) { if (fixed[i]) fixedSum += minA; else freeSum += wts[i]; });
      var changed = false;
      ring.forEach(function (_, i) { if (!fixed[i] && (TAU - fixedSum) * wts[i] / Math.max(1e-9, freeSum) < minA) { fixed[i] = true; changed = true; } });
      if (!changed) break;
    }
    var angles = ring.map(function (_, i) { return fixed[i] ? minA : (TAU - fixedSum) * wts[i] / Math.max(1e-9, freeSum); });
    // 外缘半径：按「最挤」的扇区定（密度处处不低于 DENS·s0²/人），再按下限 380 撑开
    var need = 0;
    ring.forEach(function (cp, i) { need = Math.max(need, effN(cp) * DENS * s0 * s0 * 2 / Math.max(0.05, angles[i])); });
    var rb = Math.sqrt(ra * ra + Math.max(need * 0.72, ringN * DENS * s0 * s0 / Math.PI));
    var R = rb / 0.88;
    // 小卷本：外缘撑到 380，但盘心只按 √ 放大——主角团仍是一枚紧凑的亮核，多出的地方让给外圈扇区
    if (R < 380) { var up = 380 / R, upc = Math.sqrt(up); rc *= upc; ra *= upc; s0 *= upc; R = 380; rb = R * 0.88; }
    var cP = Math.cos(SKY_PITCH), sP = Math.sin(SKY_PITCH), ZK = Math.max(1, R / 300);
    function toWorld(u, v, z) { return { x: u, y: v * cP + z * sP, z: -v * sP + z * cP }; }
    var pos = new Array(n), glyphEdges = [], chain = [], knots = [], sectors = [];
    var relSet = {};
    rels.forEach(function (r) { var a = idx[r.a], b = idx[r.b]; if (a == null || b == null) return; relSet[a + '|' + b] = relSet[b + '|' + a] = 1; });
    function place(cp, region, heart, seedK, isCore, a0, a1, ra2, rb2) {
      var m = cp.members.length, rng = mulberry(hash(cp.name) + seedK * 7919);
      var spacing = Math.sqrt(region.area / Math.max(1, m)) * 0.92;
      var pts = skyBlue(m, region, spacing, rng, heart);
      pts.sort(function (p1, p2) { var d1 = (p1[0] - heart[0]) * (p1[0] - heart[0]) + (p1[1] - heart[1]) * (p1[1] - heart[1]), d2 = (p2[0] - heart[0]) * (p2[0] - heart[0]) + (p2[1] - heart[1]) * (p2[1] - heart[1]); return d1 - d2; });
      var uv = {};
      cp.members.forEach(function (qq, k) {
        /* 浮雕：按咖位离盘面的高度（一等星浮起、长尾沉下），幅度随天球半径放大——正视时几乎不移位，转到斜视才看出星座的立体层次 */
        var p = pts[k] || heart, t = tier[qq], zt = (t === 0 ? 18 : t === 1 ? 10 : t === 2 ? 0 : t === 3 ? -8 : -16) * ZK;
        var wp = toWorld(p[0], p[1], zt + (rng() - 0.5) * 12 * ZK);
        pos[qq] = wp; uv[qq] = p; chain.push(qq);
      });
      // 星座线：核心星（≤2 等、至多 14 颗）按最短生成树连起来；有真实关系的边打 0.65 折优先
      var fig = cp.members.filter(function (qq) { return tier[qq] <= 2; }).slice(0, 14);
      if (fig.length >= 2) {
        var inT = [fig[0]], out = fig.slice(1), maxL = spacing * 3.2;
        while (out.length) {
          var bi = -1, bj = -1, bd = Infinity;
          for (var i = 0; i < inT.length; i++) for (var j = 0; j < out.length; j++) {
            var A = uv[inT[i]], B = uv[out[j]], d = Math.hypot(A[0] - B[0], A[1] - B[1]) * (relSet[inT[i] + '|' + out[j]] ? 0.65 : 1);
            if (d < bd) { bd = d; bi = i; bj = j; }
          }
          var qb = out.splice(bj, 1)[0];
          if (bd <= maxL) glyphEdges.push({ a: inT[bi], b: qb, rel: !!relSet[inT[bi] + '|' + qb], color: cp.color, knot: true, tail: false, seq: seedK, w: 1 });
          inT.push(qb);
        }
      }
      var hw = toWorld(heart[0], heart[1], 0);
      cp.cx = hw.x; cp.cy = hw.y; cp.cz = hw.z; cp.labelX = hw.x; cp.labelY = hw.y; cp.labelZ = hw.z + 10;
      cp.r = cp.fitRx = cp.fitRy = Math.sqrt(region.area / Math.PI); cp.figure = null;
      var kn = { cp: cp, members: cp.members.slice(), tail: cp.name === FIELD, ki: knots.length, seq: knots.length, mixed: false, R: cp.r, cu: heart[0], cv: heart[1], cx: hw.x, cy: hw.y, czw: hw.z, color: cp.color, seed: hash(cp.name), glyph: { points: [], edges: [] }, figure: null, dust: [], local: [] };
      knots.push(kn); cp.knots = [kn];
      sectors.push({ name: cp.name, stance: cp.stance || '', color: cp.color, count: m, lead: chars[cp.lead] ? chars[cp.lead].name : '', core: !!isCore, a0: a0, a1: a1, ra: ra2, rb: rb2, heart: heart.slice(), field: cp.name === FIELD });
      cp.sector = sectors[sectors.length - 1];
    }
    if (coreCp) place(coreCp, skyRegion(0, rc, 0, TAU, s0 * 0.28), [0, 0], 0, true, 0, TAU, 0, rc);
    var at = 0;
    ring.forEach(function (cp, i) {
      var a0 = at, a1 = at + angles[i]; at = a1;
      var mid = (a0 + a1) / 2, rh = Math.sqrt((ra * ra + rb * rb) / 2);
      var heart = K === 1 ? [0, (ra + rb) / 2] : [Math.sin(mid) * rh, Math.cos(mid) * rh];
      place(cp, skyRegion(ra, rb, a0, a1, s0 * 0.34), heart, i + 1, false, a0, a1, ra, rb);
    });
    var center = coreCp || ring[0];
    return { camps: camps, pos: pos, halfW: R * 1.03, halfH: R * cP + 36, guides: [], glyphEdges: glyphEdges, center: center, chain: chain, knots: knots, roadPath: knots, mode: 'sky', pitch: SKY_PITCH, rimR: R, rimV: R, tplNames: [],
      sky: { R: R, rb: rb, ra: ra, rc: rc, s0: s0, core: coreCp ? coreCp.name : '', sectors: sectors } };
  }

  window.NCConstellation = { inferCamps: inferCamps, layout: layout, layoutChain: layoutChain, layoutRoad: layoutRoad, layoutCamps: layout, layoutSky: layoutSky, SKY_PITCH: SKY_PITCH, hubs: hubs, groupCamps: groupCamps, FIELD: FIELD, STANCES: STANCES, COLOR: COLOR, SECTOR: SECTOR, KIND_EN: KIND_EN, KIND_ORDER: KIND_ORDER, KIND_DEF: KIND_DEF, MIN_D: MIN_D, PAD: PAD, normStance: normStance };
})();
