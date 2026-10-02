/* Castline · peerchart.js — 星位盘 PEER FIELD（雷达之外的第二种属性读法）
 *
 * 它回答什么：右坞的八维雷达（js/radar.js）答的是「聚焦角色每一维多强」——八个数。
 * 它答不了的是：**这个人在全书人群里长什么样、像谁、和谁正相反。**
 * 星位盘把每个已建档角色投影成星图上的一枚星，一眼读出三件事：
 *   离盘心多远 = 有多偏科（八维越不均衡越靠外，越平越贴中心）；
 *   朝哪个方向 = 偏向哪一维（八根辐条与 3D 晶冠的八条棱同一套角度，星偏向谁就是被谁主导）；
 *   星有多亮多大 = 综合有多强（八维均值）。
 *
 * 为什么是这个投影（scene.js buildCrown 同款 crownAxisAngle）：
 *   s_k = score/100；mean = Σs/8；P = Σ (s_k − mean) · u_k。
 *   **减均值是全部含义所在**：不减的话，八维全 90 的强者和全 10 的弱者会落在同一方向
 *   （Σu_k = 0 只在完全相等时成立，会被整体量级拖偏）。减掉后 P 只表达「偏离自身平均的形状」，
 *   强弱被彻底剥离给亮度 —— 于是「中心 = 均衡、边缘 = 偏科」这句话才是真的。
 *   半径取全体 |P| 的第 95 百分位做 Rmax（不用最大值：一个极端值会把所有人压到中心），
 *   超出的钳到盘沿并计数（stats.clipped）。距离（同类/对极）在**完整八维空间**里算，
 *   只在两人都已建档的维上取欧氏距离 —— 2D 投影只是画布，不是距离空间。
 *
 * 待建档纪律（零默认契约）：attrs 缺失 / score == null / pending 一律是「未建档」，
 * 绝不用 0 冒充。一维都没建过的角色不投影、不画点、不进同类对极，在面板头上明写「未建档 N 人」。
 *
 * 成本纪律（照 js/plot-hud.js 头注释）：这一层不进每帧循环。动效全部交给 CSS
 * （入场淡入 + 聚焦星的极慢呼吸，prefers-reduced-motion 下全关），JS 只在
 * setGraph / setFocus 各重算重绘一次；面板尺寸固定（300 × 320），不依赖窗口尺寸，无需 resize 重绘。
 * 零 scene.js / app.js / index.html 依赖：DOM 自注入，全 ES5，确定性投影（无随机）。
 * 点星只对外发一个事件 'cl:peer-char'（detail.name），接收端由接线层负责。
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- 常量
  // 维度顺序 = scene.js ATTR_KEYS 的顺序；i = 0..7 对应晶冠八条棱
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' };

  // 配色语义沿用 app.css 现有的一套，不自造色系（金=聚焦本人 · 紫=常规星点 · 薄荷=同类 · 绯红=对极）
  var COL = {
    focus: '#ffb45c', star: '#c9b8ff', kin: '#3fd6a8', anti: '#ff4a62',
    ink: '#f7f2e9', ink2: '#c7c0d1', ink3: '#88819d', grid: 'rgba(170,150,232,.16)', grid2: 'rgba(170,150,232,.30)'
  };

  // 画布几何：面板 300 × 320；SVG 视窗 272 × 236，盘心与盘半径按标签留白定死
  var W = 272, H = 236, CX = 136, CY = 118, R = 84, LAB = R + 9;
  var SIZE_LO = 2.0, SIZE_HI = 7.0;                                  // 星点尺寸：mean 0.2→2px，0.9→7px

  var CALM = false;
  try { CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e0) {}

  // ---------------------------------------------------------------- 小工具
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function f1(v) { return (Math.round(v * 10) / 10).toFixed(1); }
  /** 与 scene.js 晶冠顶点同一套 (sin, cos)：i=0..7 → SVG 平面坐标（cos 朝上） */
  function axisAngle(i) { return Math.PI + Math.PI / 8 + i * Math.PI / 4; }
  function ux(i) { return Math.sin(axisAngle(i)); }
  function uy(i) { return Math.cos(axisAngle(i)); }                  // SVG y 向下，画的时候取负

  // ---------------------------------------------------------------- 状态
  var LAY = null;               // 最近一次投影结果 {items, rmax, byName}
  var FOCUS = null;             // 聚焦角色的 item（LAY 内引用）；null = 全景态
  var wrap = null, svg = null, tipEl = null, footEl = null, pendEl = null;
  var panelEl = null, stateEl = null;                            // R2：态节点宿主（`.pf-state`，落在 `.pf-head` 之后）
  var GRAPH = null;             // 最近一次收到的图（R4 订阅端重算用；改前不存图，回调无从重绘）
  var SRC_FALLBACK = false;     // R2 degraded 判据：属性真源 CLAttrSource 缺席 ⇒ 本次投影走了 c.attrs 直读回退
  var mounted = false, opened = false;
  var recalcs = 0;              // 重算计数器：验收「不进每帧循环」用（300 帧前后必须不变）

  // ================================================================ 投影计算
  /** 唯一真相：分值判定与夹取全部委托 CLRadar.scoreOf；缺席时退回等价 fallback（同一份反例表）。 */
  function peerScoreOf(a) {
    var fn = window.CLRadar && typeof window.CLRadar.scoreOf === 'function' ? window.CLRadar.scoreOf : null;
    if (fn) return fn(a);
    if (a == null || typeof a === 'boolean' || Array.isArray(a)) return null;
    var raw = (a && typeof a === 'object') ? (a.pending ? null : a.score) : a;
    if (raw == null || typeof raw === 'boolean' || Array.isArray(raw)) return null;
    if (typeof raw === 'string' && raw.trim() === '') return null;
    var n = Number(raw);
    return isFinite(n) ? Math.max(0, Math.min(100, n)) : null;
  }
  /** 一维是否算「已建档」：attrs 缺失 / score==null / pending / 非有限数 都不算（零默认契约） */
  function builtOf(a) {
    return peerScoreOf(a) != null;
  }

  /** 全体重算。确定性：无随机，排序带名字 tiebreak，P95 取法固定。 */
  function compute(g) {
    recalcs++;
    var chars = (g && g.characters) || [];
    var items = [], pending = 0, i, c;
    // 真源是否在场（不变量，提到循环外）。缺席则整轮走 c.attrs 直读回退 —— 这是**改前就存在的
    // 静默降级**（原本无声发生）；R2 只把它显性化为 degraded，不改变取值口径。
    var hasSrc = !!(window.CLAttrSource && typeof window.CLAttrSource.extractAttr === 'function');
    SRC_FALLBACK = !hasSrc;
    for (i = 0; i < chars.length; i++) {
      c = chars[i];
      var v = new Array(8), built = [], sum = 0, k;
      for (k = 0; k < 8; k++) {
        var aData = hasSrc ? window.CLAttrSource.extractAttr(c, KEYS[k]) : (c.attrs && c.attrs[KEYS[k]]);
        var sPk = peerScoreOf(aData);
        if (sPk != null) {
          v[k] = clamp(sPk, 0, 100) / 100;
          built.push(k); sum += v[k];
        } else v[k] = null;
      }
      if (!built.length) { pending++; continue; }                    // 一维都没建档：不投影不画点
      // 分母必须是**已建档维数**，不是恒定的 8。
      // 恒 8 等价于把未建档的维按 0 分算进平均：残差 (v−mean) 于是整体抬高，
      // Σ 残差·u 不再为零，方向恰好指向「缺的那一维的反方向」，幅度还随本人 mean 线性增长。
      // sample-large 全员缺「道义」→ 184 个人被同一个偏置推离盘心，且强者推得更远，
      // 直接推翻本层的核心承诺「位置只管形状、亮度只管强度」。
      // 以 built.length 为分母后：已建档维全部相等 ⇒ 每一项残差恒为 0 ⇒ P = 0，落点回到盘心。
      var mean = sum / built.length;
      var px = 0, py = 0, j;
      for (j = 0; j < built.length; j++) {
        k = built[j];
        px += (v[k] - mean) * ux(k);
        py += (v[k] - mean) * uy(k);
      }
      var m = Math.sqrt(px * px + py * py);
      items.push({ c: c, name: c.name || ('#' + i), v: v, built: built, mean: mean, px: px, py: py, m: m,
        nx: m > 0 ? px / m : 0, ny: m > 0 ? py / m : 0, rn: 0, clip: false, dom: dominantDim(v, built) });
    }
    // Rmax = |P| 的第 95 百分位（升序第 ceil(0.95n) 个）—— 不用最大值，防止一个极端值把所有人压到中心
    var ms = items.map(function (it) { return it.m; }).sort(function (a, b) { return a - b; });
    var rmax = ms.length ? ms[Math.min(ms.length - 1, Math.ceil(0.95 * ms.length) - 1)] : 0;
    for (i = 0; i < items.length; i++) {
      var it = items[i];
      it.rn = (rmax > 0 && it.m > 0) ? Math.min(1, it.m / rmax) : 0;
      it.clip = it.m > rmax && rmax > 0;
    }
    var byName = {};
    for (i = 0; i < items.length; i++) if (!(items[i].name in byName)) byName[items[i].name] = items[i];
    LAY = { items: items, rmax: rmax, byName: byName, pending: pending, total: chars.length };
    if (FOCUS && !(FOCUS.name in byName)) FOCUS = null;
    if (FOCUS) FOCUS = byName[FOCUS.name];                           // 换图谱后重挂到新 item
  }

  /** 主导维：建档维里分最高的（并列取 KEYS 序在前者） */
  function dominantDim(v, built) {
    var best = -1, bk = -1, j;
    for (j = 0; j < built.length; j++) {
      if (v[built[j]] > best) { best = v[built[j]]; bk = built[j]; }
    }
    return bk >= 0 ? KEYS[bk] : '';
  }

  /** 八维欧氏距离：只在两人都已建档的维上算（2D 投影只是画布，不是距离空间） */
  function dist(a, b) {
    var s = 0, n = 0, k;
    for (k = 0; k < 8; k++) {
      if (a.v[k] == null || b.v[k] == null) continue;
      var d = a.v[k] - b.v[k]; s += d * d; n++;
    }
    return n ? Math.sqrt(s) : Infinity;                              // 没有共同建档维：不可比
  }

  /** 同类（最近 3 人）与对极（最远 1 人）。排序 (d, name) 双键 → 确定性 */
  function peers(f) {
    var arr = [], i, it;
    for (i = 0; i < LAY.items.length; i++) {
      it = LAY.items[i];
      if (it === f) continue;
      var d = dist(f, it);
      if (d === Infinity) continue;
      arr.push({ name: it.name, d: d });
    }
    arr.sort(function (a, b) { return (a.d - b.d) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0); });
    return { kin: arr.slice(0, 3), anti: arr.length ? arr[arr.length - 1] : null };
  }

  // ================================================================ 绘制（SVG 字符串，一次 innerHTML）
  function starSize(mean) {
    return SIZE_LO + (SIZE_HI - SIZE_LO) * clamp((mean - 0.2) / 0.7, 0, 1);
  }
  function starOpacity(mean) {
    return 0.32 + 0.58 * clamp((mean - 0.2) / 0.7, 0, 1);
  }
  function sxOf(it) { var r = it.rn * R; return CX + it.nx * r; }
  function syOf(it) { var r = it.rn * R; return CY - it.ny * r; }
  /** 星点 / 连线坐标保留 6 位小数：视觉上仍是亚像素，但验收的方向自检（< 1e-6 rad）要求不被取整淹没 */
  function n6(v) { return +v.toFixed(6); }

  /* ---------------------------------------------------------------- R2 三态（domain: 'peerchart'）
   * loading  ← 已挂载但还没收到图（app.js:1467 先 mount 再 setGraph，这个窗口真实存在）·
   * empty    ← 图在但**一个角色都没建档**（含 setGraph(null) 显式无数据 / API.empty()）·
   * degraded ← 有可画角色，但属性真源 CLAttrSource 缺席 ⇒ 整轮走了 c.attrs 直读回退（有损）·
   * ready    ← 有可画角色且真源在场。
   * 用户收起（close → 去 .on，`.pf:not(.on) .pf-panel{display:none}`）是 **blank**，不注入铭文。
   *
   * 态节点落 `.pf-panel` 内新建的 `.pf-state`（`.pf-head` 之后、svg 之前），**不在 svg 内**：
   * svg 是 272×236 的绘图面，装不下 status-states 的 HTML 态节点（那是 DOM 构建器，非 SVG 构建器）。
   * 无数据（loading/empty）时把 svg **摘出文档**让位给态节点 —— 纯 JS 节点操作，**不写内联样式**
   * （免得给 G1「静态内联样式清零」添新账）；有数据时按原位置插回。
   * ⚠ 可见性边界：面板收起时（`.pf:not(.on)`）整个 `.pf-panel` display:none ⇒ 态不可见。这与改前
   * 一致（收起本就看不到面板），非回归。让 `empty` 在收起态也可见须改 css/peer.css（本单元无该文件
   * owner）⇒ 登记 erratum 交总纲。 */
  function setState(state, notice) {
    if (!wrap) return;
    if (!stateEl) {
      var head = wrap.querySelector('.pf-head');
      if (!head) return;
      stateEl = document.createElement('div');
      stateEl.className = 'pf-state';
      head.parentNode.insertBefore(stateEl, head.nextSibling);
    }
    stateEl.textContent = '';
    stateEl.removeAttribute('data-cl-state');
    wrap.setAttribute('data-pf-state', state);
    var hold = (state === 'loading' || state === 'empty');        // 无数据：图面让位
    if (svg) {
      if (hold && svg.parentNode) svg.parentNode.removeChild(svg);
      else if (!hold && !svg.parentNode && panelEl && tipEl) panelEl.insertBefore(svg, tipEl);
    }
    var SS = window.CLStatusStates;
    if (state === 'ready' || !SS || !SS.applyState) return;
    SS.applyState(stateEl, state, { domain: 'peerchart', bars: 4, minHeight: 120, notice: notice });
  }

  function draw() {
    if (!svg || !LAY) return;
    if (LAY.items.length === 0) { setState('empty'); foot(); return; }
    setState(SRC_FALLBACK ? 'degraded' : 'ready', SRC_FALLBACK ? '真元源未达 · 按卷内直读投影' : '');
    var o = [], i, k, it;
    o.push('<g class="pf-grids">');
    // 同心圆环 3–4 道 = 偏科度刻度；最外圈是 P95
    var fr = [0.28, 0.55, 0.8, 1];
    for (i = 0; i < fr.length; i++) {
      o.push('<circle class="' + (i === fr.length - 1 ? 'pf-ring-outer' : 'pf-ring') + '" cx="' + CX + '" cy="' + CY + '" r="' + (fr[i] * R).toFixed(1) + '"/>');
    }
    o.push('<text class="pf-p95" x="' + (CX - R + 3) + '" y="' + (CY + 13) + '">P95</text>');
    // 八根辐条 = 晶冠八条棱的平面投影；末端外侧标维名（中文主 + 英文副）
    for (k = 0; k < 8; k++) {
      var s = ux(k), c = uy(k);
      o.push('<line class="pf-spoke" x1="' + CX + '" y1="' + CY + '" x2="' + (CX + s * R).toFixed(1) + '" y2="' + (CY - c * R).toFixed(1) + '"/>');
      var lx = CX + s * LAB, ly = CY - c * LAB;
      var anch = s > 0.3 ? 'start' : (s < -0.3 ? 'end' : 'middle');
      var dy = c > 0.3 ? -3 : (c < -0.3 ? 9 : 2);                    // 上方标签上提、下方标签下放，别压盘沿
      o.push('<text class="pf-zh" x="' + lx.toFixed(1) + '" y="' + (ly + dy).toFixed(1) + '" text-anchor="' + anch + '">' + esc(KEYS[k]) + '</text>');
      o.push('<text class="pf-en" x="' + lx.toFixed(1) + '" y="' + (ly + dy + (c > 0.3 ? -10 : 9)).toFixed(1) + '" text-anchor="' + anch + '">' + EN[KEYS[k]] + '</text>');
    }
    o.push('<circle class="pf-core" cx="' + CX + '" cy="' + CY + '" r="1.4"/>');
    o.push('</g>');

    // 同类 / 对极连线：从聚焦星出发（无聚焦则整段跳过）
    var lines = '', labels = '';
    if (FOCUS) {
      var ps = peers(FOCUS), fx = n6(sxOf(FOCUS)), fy = n6(syOf(FOCUS)), q;
      for (i = 0; i < ps.kin.length; i++) {
        q = LAY.byName[ps.kin[i].name];
        lines += '<line class="pf-kin" x1="' + fx + '" y1="' + fy + '" x2="' + n6(sxOf(q)) + '" y2="' + n6(syOf(q)) + '"/>';
        labels += '<text class="pf-klabel" x="' + (sxOf(q) + 4).toFixed(1) + '" y="' + (syOf(q) - 4).toFixed(1) + '">' + esc(q.name) + '</text>';
      }
      if (ps.anti) {
        q = LAY.byName[ps.anti.name];
        lines += '<line class="pf-anti" x1="' + fx + '" y1="' + fy + '" x2="' + n6(sxOf(q)) + '" y2="' + n6(syOf(q)) + '"/>';
        labels += '<text class="pf-alabel" x="' + (sxOf(q) + 4).toFixed(1) + '" y="' + (syOf(q) - 4).toFixed(1) + '">' + esc(q.name) + '</text>';
      }
    }
    o.push('<g class="pf-links">' + lines + '</g>');

    // 全体星点：半径与不透明度只随 mean（综合强度）走；位置只管形状
    o.push('<g class="pf-stars">');
    for (i = 0; i < LAY.items.length; i++) {
      it = LAY.items[i];
      if (it === FOCUS) continue;
      o.push('<circle class="pf-dot' + (it.clip ? ' pf-clip' : '') + '" data-nm="' + esc(it.name) + '" cx="' + n6(sxOf(it)) + '" cy="' + n6(syOf(it)) +
        '" r="' + starSize(it.mean).toFixed(2) + '" fill="' + COL.star + '" fill-opacity="' + starOpacity(it.mean).toFixed(3) + '"/>');
    }
    o.push('</g>');

    // 聚焦星：琥珀色 + 衍射芒（两条细十字 + 一个环，极慢呼吸交给 CSS）
    if (FOCUS) {
      var fx2 = n6(sxOf(FOCUS)), fy2 = n6(syOf(FOCUS));
      var sz = starSize(FOCUS.mean) + 1.2, arm = sz * 3.4, ring = sz * 3.1;
      o.push('<g class="pf-focus">');
      o.push('<g class="pf-diff">' +
        '<line x1="' + (fx2 - arm).toFixed(1) + '" y1="' + fy2 + '" x2="' + (fx2 + arm).toFixed(1) + '" y2="' + fy2 + '"/>' +
        '<line x1="' + fx2 + '" y1="' + (fy2 - arm).toFixed(1) + '" x2="' + fx2 + '" y2="' + (fy2 + arm).toFixed(1) + '"/>' +
        '<circle cx="' + fx2 + '" cy="' + fy2 + '" r="' + ring.toFixed(1) + '"/></g>');
      o.push('<circle class="pf-dot pf-me" data-nm="' + esc(FOCUS.name) + '" cx="' + fx2 + '" cy="' + fy2 +
        '" r="' + sz.toFixed(2) + '" fill="' + COL.focus + '"/>');
      o.push('</g>');
    }
    o.push('<g class="pf-labels">' + labels + '</g>');
    svg.innerHTML = o.join('');
    foot();
  }

  // ---------------------------------------------------------------- 面板文字行
  function foot() {
    if (!footEl || !LAY) return;
    var pend = LAY.total - LAY.items.length;
    if (pendEl) pendEl.textContent = pend > 0 ? '未建档 ' + pend + ' 人' : '';
    if (!FOCUS) {
      footEl.innerHTML = '全景 · 落盘 <b class="cl-info-primary abyss-num">' + LAY.items.length + '</b> · 未建档 <span class="abyss-num">' + pend + '</span> ｜ P95 <span class="abyss-num">' + LAY.rmax.toFixed(3) + '</span>';
      tip();
      return;
    }
    var ps = peers(FOCUS), t = [], i;
    for (i = 0; i < ps.kin.length; i++) t.push(ps.kin[i].name + ' Δ' + f1(ps.kin[i].d));
    footEl.innerHTML = '<span class="cl-info-secondary">同类</span> · ' + (t.length ? t.join(' · ') : '—') +
      ' ｜ <span class="cl-info-secondary">对极</span> · ' + (ps.anti ? ps.anti.name + ' <b class="cl-info-primary abyss-num">Δ' + f1(ps.anti.d) + '</b>' : '—');
    tip();
  }
  function tip(hoverName) {
    if (!tipEl) return;
    if (hoverName && LAY && LAY.byName[hoverName]) {
      var it = LAY.byName[hoverName];
      var d = (FOCUS && it !== FOCUS) ? ' · Δ' + f1(dist(FOCUS, it)) : (FOCUS === it ? ' · 聚焦本人' : '');
      tipEl.innerHTML = '<b class="cl-info-primary">' + it.name + '</b> · 均值 <b class="cl-info-primary abyss-num">' + f1(it.mean * 100) + '</b> · 主导 <span class="cl-info-secondary">' + (it.dom || '—') + '</span>' + d;
    } else if (FOCUS) {
      tipEl.innerHTML = '<span class="cl-info-secondary">聚焦</span> · <b class="cl-info-primary">' + FOCUS.name + '</b> · r <span class="abyss-num">' + FOCUS.rn.toFixed(2) + '</span>' + (FOCUS.clip ? ' · 越界钳至盘沿' : '');
    } else {
      tipEl.innerHTML = '<span class="cl-info-rune">点星换聚焦 · 悬停看数</span>';
    }
  }

  // ================================================================ DOM 装配（自注入，幂等）
  function mount() {
    if (mounted || !document.body) return;
    mounted = true;
    wrap = document.createElement('div');
    wrap.className = 'hud pf';
    wrap.id = 'clPeer';
    wrap.innerHTML =
      '<div class="pf-panel">' +
      '  <div class="pf-head">' +
      '    <div class="eyebrow"><span class="dot"></span>星位盘 · <b>PEER FIELD</b> <small style="font-size:10px;opacity:.75;margin-left:4px" title="八维多维特征投影偏倚分析（第二种读法，主位在雷达全息）">「第二种读法」</small></div>' +
      '    <span class="pf-pend mono"></span>' +
      '    <button class="pf-x" data-act="close" title="收起星位盘">×</button>' +
      '  </div>' +
      '  <svg class="pf-svg" viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '"></svg>' +
      '  <div class="pf-tip mono"></div>' +
      '  <div class="pf-foot mono"></div>' +
      '</div>' +
      '<button class="pf-rail mono" title="展开星位盘"><i></i><span>星位盘 · PEER</span></button>';
    document.body.appendChild(wrap);
    svg = wrap.querySelector('.pf-svg');
    tipEl = wrap.querySelector('.pf-tip');
    footEl = wrap.querySelector('.pf-foot');
    pendEl = wrap.querySelector('.pf-pend');
    panelEl = wrap.querySelector('.pf-panel');

    // 交互全部走事件委托：星点最多几百枚，逐个挂 listener 是纯浪费
    svg.addEventListener('mouseover', function (e) {
      var n = e.target;
      var nm = n && n.getAttribute && n.getAttribute('data-nm');
      if (nm != null) tip(nm);
    });
    svg.addEventListener('mouseout', function (e) {
      var n = e.target;
      if (n && n.getAttribute && n.getAttribute('data-nm') != null) tip(null);
    });
    svg.addEventListener('click', function (e) {
      var n = e.target;
      var nm = n && n.getAttribute && n.getAttribute('data-nm');
      if (nm == null) return;
      try { document.dispatchEvent(new CustomEvent('cl:peer-char', { detail: { name: nm } })); } catch (e2) {}
    });
    wrap.addEventListener('click', function (e) {
      var n = e.target;
      while (n && n !== wrap && !(n.getAttribute && n.getAttribute('data-act'))) n = n.parentNode;
      if (n && n !== wrap && n.getAttribute('data-act') === 'close') close();
    });
    var rail = wrap.querySelector('.pf-rail');
    rail.addEventListener('click', function () { open(); });
    apply();
    // R2：挂载即定态。已收到图（如 arcana build 早于 mount）就直接补画，否则置 loading ——
    // 改前这里既不置态也不补画：既是一块**可见的空白**，又埋着「setGraph 早于 mount ⇒ 图永不出现」
    // 的静默（draw 的 `!svg` 早退把这次绘制吃掉了）。两处一并消灭。
    if (!LAY) setState('loading'); else draw();
  }

  function apply() {
    if (!wrap) return;
    wrap.classList.toggle('on', opened);
  }

  // ================================================================ 对外 API
  var API = {
    name: 'peer-field',
    mount: mount,
    /** 收到图即定态。改前 `if (!g) return;` 是**静默 return**：无数据时面板既不置态也不清旧图，
     *  留一块空白或上一轮的残影。现在 falsy 图 = 显式 empty，与 API.empty() 同一归宿。 */
    setGraph: function (g) {
      GRAPH = g || null;
      if (!GRAPH) { LAY = { items: [], rmax: 0, byName: {}, pending: 0, total: 0 }; FOCUS = null; SRC_FALLBACK = false; draw(); return; }
      compute(GRAPH); draw();
    },
    setFocus: function (name) {
      if (!LAY) return;
      var it = name ? LAY.byName[name] : null;
      FOCUS = it || null;                                            // 未建档 / 不存在的名字 → 回全景态，不造假
      recalcs++;
      draw();
    },
    toggle: function () { opened = !opened; apply(); return opened; },
    open: function () { opened = true; apply(); },
    close: function () { opened = false; apply(); },
    empty: function () {
      LAY = { items: [], rmax: 0, byName: {}, pending: 0, total: 0 };
      FOCUS = null;
      draw();
    },
    /** 探针：无头验收全靠它 */
    stats: function () {
      var ps = FOCUS ? peers(FOCUS) : { kin: [], anti: null };
      return {
        ok: !!(mounted && LAY),
        chars: LAY ? LAY.items.length : 0,                           // 已落盘人数（≥1 维建档）
        plotted: LAY ? LAY.items.length : 0,
        pending: LAY ? (LAY.total - LAY.items.length) : 0,           // 一维都没建档的人数
        focus: FOCUS ? FOCUS.name : '',
        focusR: FOCUS ? +FOCUS.rn.toFixed(4) : 0,
        rmax: LAY ? LAY.rmax : 0,                                    // P95 原始单位，不给探针引入取整误差
        kin: ps.kin.map(function (x) { return { name: x.name, d: +x.d.toFixed(4) }; }),
        anti: ps.anti ? { name: ps.anti.name, d: +ps.anti.d.toFixed(4) } : { name: '', d: 0 },
        dominant: FOCUS ? FOCUS.dom : '',
        clipped: LAY ? LAY.items.reduce(function (n, it) { return n + (it.clip ? 1 : 0); }, 0) : 0,
        recalcs: recalcs,
        open: opened, calm: CALM
      };
    },
    /** 深层补挂：晚于 CLArcana 加载也能活。无图时也走 setGraph（归一为 empty，不静默丢事件）。 */
    build: function (o) { API.setGraph(o && o.graph); },
    /** 只读：唯一真相 scoreOf，供契约测试验证与 CLRadar.scoreOf 同一份反例表（不留第二套强转逻辑）。 */
    scoreOf: peerScoreOf
  };

  if (window.CLArcana && CLArcana.register) CLArcana.register(API);
  window.CLPeer = API;

  /* R4 订阅端：真源广播 ⇒ 只读重算重绘。**禁止回写** attr-source（承 V2-1 契约：回调内不得调
   * notify / 不得改 listeners，违反会被重入哨兵警告并拒绝）。
   * 改前此处引用了**本模块并不存在的 `render`**（本模块的绘制函数叫 draw）⇒
   * `typeof render === 'function'` 恒为 false，回调是彻底的**死挂**：广播到达后什么也不做。
   * 现在改为真的重算重绘，并以「已挂载 且 有图」双重守卫。 */
  if (typeof window !== 'undefined' && window.CLAttrSource && typeof window.CLAttrSource.subscribe === 'function') {
    window.CLAttrSource.subscribe(function () { if (mounted && GRAPH) { compute(GRAPH); draw(); } });
  }
})();
