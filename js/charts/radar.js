/* Castline · radar.js — 通用八维属性雷达（SVG）· v26.0 轮流呼吸灯 + 克苏鲁式神秘层 · v17.15 零默认契约（pending = 待建档，不画假分）· v17.14 本机时钟表盘 / 显性分值胶囊 / 星尘背景 / 与晶冠同拍
 * 维度：智谋 MIND · 实力 FORCE · 意志 WILL · 魅力 CHARM · 情感 HEART · 野心 DRIVE · 权势 REACH · 道义 CODE
 * 视觉：渐变填充 + 描边描画动画 + 顶点置信环 + 轴可点看依据与证据
 * 时钟：三针读 Date()，秒针 1 Hz 擒纵跳格（TICK_SETTLE 与 scene.js 晶冠表盘同一常数），由 JS rAF 驱动而非 SMIL，两只表同拍
 * v26.0 · 神秘层：
 *   轮流呼吸灯 —— 一枚"意识"沿八维顺次巡行，被点到的那一维整轴亮起（幅度大），其余维沉在暗处；
 *                  相位自 P0/S3 起由 CLAbyssBreath 呼吸总线统一供给（与 scene.js tAnim、树行波同源）
 *                  → 右坞的表与 3D 晶冠永远亮同一维，且与星盘树同相。总线缺席时退回 performance.now()。
 *   全局微呼吸 —— 整块表盘极轻微地涨落（幅度小，只用来让画面"活着"，不抢数据）。
 *   克苏鲁元素 —— 深渊之瞳（缓慢开合的巨大虹膜）· 禁忌符文环（24 枚无名铭文，逆向巡回）· 触须（自暗处伸入的弧线）。
 *   两者都写成 CSS 自定义属性（--rd-lamp / --rd-breath），几何与配色全部交给 CSS —— JS 每帧只写数，不碰 DOM 结构。
 */
(function () {
  'use strict';
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' };
  // 与 serve.py ATTR_DEF 同步：八维跨题材通用，刻度为跨作品绝对刻度
  var DEF = {
    智谋: '认知、判断、算计与布局（计谋 / 推理 / 学识 / 商业与专业判断 / 识人），以计划是否奏效为据',
    实力: '该世界体系内的直接对抗与行动能力（武功 / 修为 / 枪法 / 体能 / 统兵 / 专业硬实力），以实战结果为据',
    意志: '承压、坚持、不被击垮的韧性（逆境中的选择、忍耐与自制）',
    魅力: '令他人倾心、信服或追随的吸引力（人望 / 口才 / 气度 / 被爱慕与被追随的事实）',
    情感: '情感浓度、共情与牵绊之深（爱憎强度、为亲友的付出、被触动的程度），不是情绪化程度',
    野心: '欲望与向上攫取的驱动力（目标大小、付出的代价、对现状的不满足）',
    权势: '当下实际可调动的地位、资源、人脉与靠山（官职 / 门派或公司地位 / 财富 / 家族 / 势力）',
    道义: '底线、原则与对他人的善意（守诺 / 护弱 / 公正）；低分 = 为达目的不择手段'
  };
  var SCALE = '刻度 · 50 常人 · 70 圈内出色 · 85 一方之最 · 96+ 传说级 · 跨作品统一';
  // 秒针落格时长（s）：与 scene.js 晶冠表盘同一常数 → 右坞表与 3D 表盘同一拍落格
  var TICK_SETTLE = 0.34;
  // ---- v26.0 · 轮流呼吸灯 ------------------------------------------------------------
  // LAMP_SLOT：一维亮起到交给下一维的时长（s）。8 维一圈 = LAMP_SLOT × 8，用户要"缓慢"，所以一圈 21 s。
  // LAMP_WIDE：亮斑的半宽（单位 = 维），> 1 表示相邻维会有重叠 —— 永远有东西在亮，不会出现全暗的空档。
  // LAMP_GAIN：亮斑的锐度指数，越大越"聚光"。幅度（0 → 1 全摆幅）由 CSS 那侧决定，用户要"幅度大一些"。
  var LAMP_SLOT = 2.62, LAMP_WIDE = 1.34, LAMP_GAIN = 1.55;
  // 深渊之瞳的开合：38 s 一次极慢的睁闭，另有约 1/6 的概率在一轮里"眨"一下
  var IRIS_PER = 37.6, BLINK_PER = 28.3;
  function nowSec() { return (typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()) / 1000; }
  /** 第 i 维在相位 ph（单位 = 维，连续）上的灯值 0..1：升余弦亮斑，环形距离，相邻维重叠 */
  function lampAt(i, ph, n) {
    var d = (i - ph) % n; if (d < 0) d += n; if (d > n / 2) d -= n;
    var x = Math.abs(d) / LAMP_WIDE;
    if (x >= 1) return 0;
    return Math.pow(Math.cos(x * Math.PI / 2), LAMP_GAIN * 2);
  }
  // W6 · 读取头拖尾（v28.0）：只有一枚灯在跳，读到的是"闪"，不是"扫过"。
  // 拖尾只朝**已经走过**的那一侧衰减（有向），覆盖身后两维，强度单调递减 —— 于是方向感立刻出来。
  var WAKE_SPAN = 2.15, WAKE_GAIN = 0.62;
  function wakeAt(i, ph, n) {
    var d = (ph - i) % n; if (d < 0) d += n;      // 只看"灯已经过去了多久"
    if (d > WAKE_SPAN) return 0;
    return Math.pow(1 - d / WAKE_SPAN, 1.9) * WAKE_GAIN;
  }
  /** 当帧的神秘层相位快照（右坞所有表共用一份，保证同拍）
   *  P0 · S3（2026-09-16）：t 改由呼吸总线 CLAbyssBreath 提供 —— 与 scene.js 的 tAnim、
   *  树行波同一时钟，于是表盘呼吸 / 晶冠巡灯 / 树波谷同相（实测偏差 0，见 tests/abyss_breath.py）。
   *  总线缺席时**逐位退回**原有 nowSec() 墙钟分支，radar 单独加载行为不变。
   *  src 字段供探针判定走的是哪条支路（不许靠猜）。 */
  function auraPhase(n) {
    var q = calm(), B = window.CLAbyssBreath, t, breath, iris, blink;
    if (B && B.snap) {
      var s = B.snap();
      t = s.t; breath = s.breath; iris = s.iris; blink = s.blink;
    } else {
      t = nowSec();
      var bPeriod = (B && B.C && B.C.BREATH_CYCLE) ? B.C.BREATH_CYCLE : 9.4;
      breath = 0.5 + 0.5 * Math.sin(t * Math.PI * 2 / bPeriod);
      // 虹膜：sin 的绝对值做"睁—闭"，再叠一次稀疏的眨眼（指数衰减的窄脉冲）
      iris = 0.5 + 0.5 * Math.sin(t * Math.PI * 2 / IRIS_PER);
      var bp = (t % BLINK_PER) / BLINK_PER;
      blink = bp < 0.06 ? Math.exp(-Math.pow((bp - 0.03) / 0.014, 2)) : 0;
    }
    var ph = (t / LAMP_SLOT) % n;
    return { t: t, ph: ph, breath: q ? 0.5 : breath, iris: q ? 0.55 : iris, blink: q ? 0 : blink, n: n, calm: q, src: B ? 'bus' : 'wall' };
  }
  var WEEK = '日一二三四五六';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  // 缺失的维度 = 待建档（pending）：分值 null；所有绘制把它画成“无”，绝不用 0 或默认分冒充。
  // 分数入口只有这一处：数字字符串仍兼容旧数据，空白/布尔/非有限数一律未知。
  function get(attrs, k) {
    var a = attrs && attrs[k];
    return a == null ? { score: null, evidence: [], basis: '', low: true, pending: true } : a;
  }
  function rawScore(a) { return a && typeof a === 'object' && !Array.isArray(a) ? a.score : a; }
  function scoreOf(a) {
    if (a && typeof a === 'object' && a.pending) return null;
    var raw = rawScore(a);
    if (raw == null || (typeof raw !== 'number' && typeof raw !== 'string')) return null;
    if (typeof raw === 'string' && raw.trim() === '') return null;
    var n = Number(raw);
    if (!isFinite(n)) return null;
    return Math.max(0, Math.min(100, n));
  }
  function isLow(a) { return !!(a && a.low) || !(a && a.evidence && a.evidence.length); }
  function isPending(a) { return scoreOf(a) == null; }
  function normalizedAttrs(attrs) {
    var out = {}, i, k, a, s;
    for (i = 0; i < KEYS.length; i++) {
      k = KEYS[i]; a = get(attrs, k); s = scoreOf(a);
      if (a && typeof a === 'object' && !Array.isArray(a)) {
        out[k] = {};
        for (var p in a) if (Object.prototype.hasOwnProperty.call(a, p)) out[k][p] = a[p];
      } else out[k] = {};
      out[k].score = s;
      out[k].pending = s == null;
    }
    return out;
  }
  function allPending(attrs) { return KEYS.every(function (k) { return isPending(get(attrs, k)); }); }
  /* R2（V2-6 · radar 域）：全维待建档 ⇒ 改走 status-states 引擎出空态（域铭文「此魂八维待建档 ·
   * 宿命星轨未明」+ 符印 ◇），并**保留**原有的具体解释 —— 那段文案比通用铭文有用，信息不降级。
   * 本文件是字符串生产器（宿主在 app.js，本 run 无权触碰），故以 `wrap.outerHTML` 交付，
   * 由既有 `host.innerHTML = CLRadar.render(...)` 链路消费，宿主零改动。
   * 引擎缺席时回落到原串（该回落分支引擎在页面恒在，登记为已知未测路径，与 V2-2 的 P2-3 同类）。 */
  var PENDING_DETAIL = '本次分析没有对该角色建档（材料不足，或超出深度建档上限）；不用默认分冒充结论。「重新分析 → 补齐续跑」可补建。';
  function pendingHTML() {
    var SS = (typeof window !== 'undefined') ? window.CLStatusStates : null;
    if (SS && typeof SS.renderEmpty === 'function') {
      try {
        var wrap = document.createElement('div');
        wrap.className = 'rd-pending';
        wrap.appendChild(SS.renderEmpty({ domain: 'radar' }));
        var d = document.createElement('span');
        d.textContent = PENDING_DETAIL;
        wrap.appendChild(d);
        /* 必须是 outerHTML：innerHTML 只序列化子节点，外层 .rd-pending 包裹类会丢，
         * 宿主 host.innerHTML 拿到的将是裸子串，views-hud.css 的 .rd-pending 样式链路即断。 */
        return wrap.outerHTML;
      } catch (e) { /* 引擎异常 ⇒ 落到下方原串 */ }
    }
    return '<div class="rd-pending"><b>八维待建档</b><span>' + PENDING_DETAIL + '</span></div>';
  }
  function calm() { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
  function easeOutBack(t) { var c = 1.10158, c3 = c + 1; return t >= 1 ? 1 : 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function tierOf(s, low) { return low ? 'low' : s >= 96 ? 'legend' : s >= 85 ? 'hi' : s >= 70 ? 'up' : 'mid'; }
  function tierName(s, low) { return low ? '低证保守' : s >= 96 ? '传说级' : s >= 85 ? '一方之最' : s >= 70 ? '圈内出色' : s >= 41 ? '常人' : s >= 21 ? '弱于常人' : '明显低于常人'; }
  // 分值胶囊：高度 / 内缩留白，以及一个不依赖 DOM 测量的文本宽度估算（渲染时还没有布局，getComputedTextLength 拿不到）
  var CHIP_H = 36, CHIP_G = 4;
  // px = 字号，mono = 等宽（0.6em 定宽推进），ls = letter-spacing（em）。字距必须计入：
  // .rd-val 的 .1em 在 15 个字符上就是 12.75px，漏掉它会让胶囊比文字窄一圈。
  function txtW(s, px, mono, ls) {
    var w = s.length * px * (ls || 0);
    for (var q = 0; q < s.length; q++) { var cc = s.charCodeAt(q); w += cc > 0x2e80 ? px : px * (mono ? 0.6 : 0.52); }
    return w;
  }
  // 副行文案。ev = 0 时不再另挂「低证」：0E 本身就是这个结论（且按低证配色），重复一次只会把胶囊撑破侧向余量。
  function lowTag(ev, low) { return low && ev > 0; }
  function subText(k, pend, ev, low, peak) { return EN[k] + (pend ? ' · 待建档' : ' · ' + ev + 'E' + (lowTag(ev, low) ? ' · 低证' : '') + (peak ? ' · 最高维' : '')); }
  /* v71 W1·U3 · 全书排名徽章（opt.ranks）。配色对齐 abyss-tokens 的 tier 色板，用
   * presentation attribute 直给（与本文件渐变/潮汐谱的硬编码色同源）：.rd-rank 在外部
   * CSS 里没有任何规则，属性不会被层叠覆盖；r=1 榜首改金/琥珀强调。 */
  var RANK_TIER_FILL = { legend: '#fff1c4', hi: '#ffd9a0', up: '#9af5d2', mid: '#e4dcff', low: '#a39cb8' };
  function rankTspan(rank, tier) {
    var top = rank.r === 1;
    return '<tspan class="rd-rank' + (top ? ' rd-rank-top' : '') + '" fill="' + (top ? '#ffe9b0' : (RANK_TIER_FILL[tier] || RANK_TIER_FILL.mid)) + '" font-weight="600">#' + rank.r + '/' + rank.n + '</tspan>';
  }
  // 排名文字背后的细描边徽章：与 statusPillSVG 同一几何语言（txtW 估算定位、右界夹紧、圆角背板）
  function rankBadgeSVG(chipX, chipY, chipW, prefixW, txt, tier, top) {
    var r2 = function (v) { return Math.round(v * 100) / 100; };
    var w = txtW(txt, 8.5, true, 0.1) + 7;
    var x0 = Math.max(chipX + 6, Math.min(chipX + 9 + prefixW - 3, chipX + chipW - 9 - w));
    var c = top ? '#ffd9a0' : (RANK_TIER_FILL[tier] || RANK_TIER_FILL.mid);
    return '<rect class="rd-rank-badge' + (top ? ' rd-rank-top' : '') + '" x="' + r2(x0) + '" y="' + r2(chipY + 22) + '" width="' + r2(w) + '" height="12" rx="5.5" fill="' + c + '" fill-opacity="' + (top ? '.22' : '.1') + '" stroke="' + c + '" stroke-opacity="' + (top ? '.9' : '.45') + '" stroke-width=".75"/>';
  }
  // R2-D · 「低证/待建档」status 色胶囊背板（只画一个 rect，不碰 B1 的 chipX/chipY/chipW/chipH）。
  // 用与 subW（8.5px mono letter-spacing .1）同一套 txtW 估算前缀宽度，定位到「· 待建档」或「· 低证」
  // 这段 tspan 开头；估算天然带余量（真实渲染字号更小，见 css/radar-theme.css R2-D 段落注释），
  // 因此夹一次右边界即可，不会因误差把胶囊画出 chip 之外。胶囊本身常显（它不属于 ROUND2
  // 说的「装饰铭牌」，是分值区之外独立的状态提示），配色见 css/radar-theme.css。
  function statusPillSVG(chipX, chipY, chipW, en, pend, ev, low, peak) {
    var SEP = ' · ', segPx = 8.5, mono = true, ls = 0.1;
    var prefix = en + SEP, tag = null, cls = null;
    if (pend) { tag = '待建档'; cls = 'rd-status-pill-pend'; }
    else if (lowTag(ev, low)) { prefix += ev + 'E' + SEP; tag = '低证'; cls = 'rd-status-pill-weak'; }
    if (!tag) return '';
    var x0 = chipX + 9 + txtW(prefix, segPx, mono, ls) - 3;
    var w = txtW(tag, segPx, mono, ls) + 7;
    var xMax = chipX + chipW - 9 - w;
    x0 = Math.max(chipX + 6, Math.min(x0, xMax));
    // round() 是 render() 内部的局部函数，statusPillSVG 挂在外层作用域够不到，这里用
    // Math.round 到整数即可——装饰背板不需要 2 位小数精度。
    var r2 = function (v) { return Math.round(v * 100) / 100; };
    return '<rect class="rd-status-pill ' + cls + '" x="' + r2(x0) + '" y="' + r2(chipY + 22) + '" width="' + r2(w) + '" height="12" rx="5.5"/>';
  }
  /** 本机时钟快照：整秒 / 毫秒相位 / 连续分时 */
  function wallClock() {
    var d = new Date(), ms = d.getMilliseconds(), s = d.getSeconds(), m = d.getMinutes(), h = d.getHours();
    var sec = s + ms / 1000, min = m + sec / 60;
    return { d: d, s: s, m: m, h: h, frac: ms / 1000, sec: sec, min: min, hr: (h % 12) + min / 60, epoch: Math.floor(d.getTime() / 1000) };
  }
  /** 三针角度（度，12 点 = 0，顺时针）：秒针从上一格弹到本格；分针 / 时针按真实速率连续走 */
  function handAngles(wc) {
    var te = wc.frac < TICK_SETTLE ? easeOutBack(wc.frac / TICK_SETTLE) : 1;
    return { s: calm() ? wc.sec * 6 : ((wc.s - 1) + te) * 6, m: wc.min * 6, h: wc.hr * 30 };
  }
  function fmtTime(wc) { return pad2(wc.h) + ':' + pad2(wc.m) + ':' + pad2(wc.s); }
  function fmtDate(wc) { return wc.d.getFullYear() + '-' + pad2(wc.d.getMonth() + 1) + '-' + pad2(wc.d.getDate()) + ' · 周' + WEEK[wc.d.getDay()]; }

  // ---- 表盘 + 神秘层驱动：一个 rAF 循环服务页面里所有雷达（右坞重绘后自动接管新表）；连续 4 s 找不到表就自停，render() 会再拉起
  // v26.0：这个循环从"只走针"扩成"走针 + 轮流呼吸灯 + 微呼吸 + 深渊之瞳"。
  // 每帧只写 CSS 自定义属性，不增删任何节点 —— 动画的形状与配色全部留在 CSS，JS 只负责"现在该亮第几维"。
  var clockRaf = 0, clockIdle = 0, lastSec = -1;
  function rot(el, deg, cx, cy) { if (el) el.setAttribute('transform', 'rotate(' + deg.toFixed(2) + ' ' + cx + ' ' + cy + ')'); }
  /** 把一张表上要每帧写数的节点缓存到元素自己身上：右坞重绘会连缓存一起丢掉，不需要手工失效 */
  function auraCache(svg) {
    var c = svg._rdAura, i;
    if (c) return c;
    c = { lamps: [], runes: [], runesOuter: [], hands: svg.querySelector('.rd-hands'), clock: svg.querySelector('.rd-clock') };
    var ls = svg.querySelectorAll('[data-lamp-i]');
    for (i = 0; i < ls.length; i++) {
      var k = +ls[i].getAttribute('data-lamp-i');
      if (!(k >= 0)) continue;
      (c.lamps[k] || (c.lamps[k] = [])).push(ls[i]);
    }
    var rs = svg.querySelectorAll('.rd-rune');
    for (i = 0; i < rs.length; i++) c.runes.push(rs[i]);
    var rso = svg.querySelectorAll('.rd-rune-outer');
    for (i = 0; i < rso.length; i++) c.runesOuter.push(rso[i]);
    // R2 · 悬停联动：悬停某维时点亮对应的 6 枚外环符文与 3 枚内环符文
    if (!svg._rdBoundHover) {
      svg._rdBoundHover = true;
      svg.addEventListener('mouseover', function (e) {
        var t = e.target.closest('[data-axis], [data-lamp-i]');
        if (t) {
          var k = t.getAttribute('data-lamp-i');
          if (k == null && t.getAttribute('data-axis')) k = KEYS.indexOf(t.getAttribute('data-axis'));
          if (k >= 0) {
            var matching = svg.querySelectorAll('[data-dim="' + k + '"]');
            for (var m = 0; m < matching.length; m++) matching[m].setAttribute('data-lit', 'true');
          }
        }
      });
      svg.addEventListener('mouseout', function (e) {
        var t = e.target.closest('[data-axis], [data-lamp-i]');
        if (t) {
          var lit = svg.querySelectorAll('[data-lit="true"]');
          for (var m = 0; m < lit.length; m++) lit[m].removeAttribute('data-lit');
        }
      });
    }
    svg._rdAura = c;
    return c;
  }
  /* 活集合：DOM 变动时浏览器自己维护，逐帧取长度不再整树 querySelectorAll（星空壳下 6 万节点里每帧扫一遍） */
  var clockSvgs = null;
  function radarSvgs() { return clockSvgs || (clockSvgs = document.getElementsByClassName('radar-3d')); }
  function tickClocks() {
    var svgs = radarSvgs();
    if (!svgs.length) { if (++clockIdle > 240) { clockRaf = 0; return; } clockRaf = requestAnimationFrame(tickClocks); return; }
    clockIdle = 0;
    var wc = wallClock(), ang = handAngles(wc), secChanged = wc.epoch !== lastSec; lastSec = wc.epoch;
    var n = KEYS.length, A = auraPhase(n), i, j, si;
    // 八维的灯值一帧只算一次（所有表共用），逐维写下去 → 右坞的表与 3D 晶冠亮同一维
    var lampV = [], wakeV = [];
    for (i = 0; i < n; i++) { lampV.push(lampAt(i, A.ph, n)); wakeV.push(A.calm ? 0 : wakeAt(i, A.ph, n)); }
    // 符文环走自己的、更快且反向的巡回：24 枚铭文里同时有两三枚在亮，读起来像"文字自己在念"
    // 双速反向：外环 0.94 s/枚（逆行）· 内环 2.35 s/枚（顺行）。两圈角速度比 2.5:1，
    // 于是它们不断错开又对齐 —— 这是"星盘在算什么"，不是一圈会亮的贴纸。
    var RN = 24, rph = RN - (A.t / 0.94) % RN, rph2 = (A.t / 2.35) % RN, runeV = [];
    for (j = 0; j < RN; j++) runeV.push(A.calm ? 0.28 : Math.max(lampAt(j, rph, RN), lampAt(j, rph2, RN) * 0.72));
    var RN_OUTER = 48, rphOuter = (A.t / 1.52) % RN_OUTER, runeVOuter = [];
    for (j = 0; j < RN_OUTER; j++) runeVOuter.push(A.calm ? 0.22 : lampAt(j, rphOuter, RN_OUTER));
    for (si = 0; si < svgs.length; si++) {
      var svg = svgs[si], c = auraCache(svg), st = svg.style;
      st.setProperty('--rd-breath', A.breath.toFixed(3));
      st.setProperty('--rd-iris', A.iris.toFixed(3));
      st.setProperty('--rd-blink', A.blink.toFixed(3));
      st.setProperty('--rd-lampph', (A.ph / n).toFixed(4));
      for (i = 0; i < n; i++) {
        var arr = c.lamps[i]; if (!arr) continue;
        var v = lampV[i].toFixed(3), w = wakeV[i].toFixed(3);
        for (j = 0; j < arr.length; j++) { arr[j].style.setProperty('--rd-lamp', v); arr[j].style.setProperty('--rd-wake', w); }
      }
      for (j = 0; j < c.runes.length && j < RN; j++) c.runes[j].style.setProperty('--rd-lamp', runeV[j].toFixed(3));
      if (c.runesOuter) {
        for (j = 0; j < c.runesOuter.length && j < RN_OUTER; j++) c.runesOuter[j].style.setProperty('--rd-lamp', runeVOuter[j].toFixed(3));
      }
      var g = c.hands;
      if (g) {
        var cx = g.getAttribute('data-cx'), cy = g.getAttribute('data-cy');
        rot(g.querySelector('.rd-hand.hour'), ang.h, cx, cy); rot(g.querySelector('.rd-hand.minute'), ang.m, cx, cy); rot(g.querySelector('.rd-hand.second'), ang.s, cx, cy);
        if (secChanged || !g.getAttribute('data-lit')) g.setAttribute('data-lit', '1');
      }
      // 读数只在整秒变化时写一次：跳字与三针落格同拍，也不必每帧碰 DOM
      if (c.clock && (secChanged || !c.clock.textContent)) c.clock.textContent = fmtTime(wc);
      if (svg.classList) svg.classList.toggle('tick', !A.calm && wc.frac < 0.18);
    }
    clockRaf = requestAnimationFrame(tickClocks);
  }
  function ensureClock() { if (!clockRaf && typeof requestAnimationFrame === 'function') { clockIdle = 0; clockRaf = requestAnimationFrame(tickClocks); } }
  // ---- v26.0 · 禁忌铭文：12 笔无名笔画在 10×10 框里，配 24 个方位与两种镜像 → 读起来是一门看不懂的文字，
  //      而不是 24 个重复图标。全部静态几何，亮度由 --rd-lamp 逐枚给。
  var RUNE_STROKES = [
    'M2,1H8M5,1V9M2,9H8', 'M2,9L5,1L8,9M3.4,6H6.6', 'M2,1V9M2,5H7M7,2V8', 'M5,1V9M2,3H8M3,7H7',
    'M2,2L8,8M8,2L2,8M5,1V9', 'M2,1L8,5L2,9M4,5H8', 'M2,5A3,3 0 1 1 8,5M5,5V9', 'M3,1V9H8M3,5L7,3',
    'M2,3H8M5,3V9M3,6H7', 'M2,9H8L5,1Z', 'M2,2H8V8M2,5H6', 'M5,1L2,5L5,9L8,5Z'
  ];

  // 星尘贴片（两层 pattern：近层 72² 稍亮、远层 96² 更细），全部静态几何，靠 mask 向边缘淡出
  var STARS_NEAR = [[6, 9, .55, .85, 0], [22, 4, .35, .5, 1], [40, 14, .75, .95, 0], [58, 7, .4, .6, 0], [13, 30, .45, .55, 1], [34, 38, .95, 1, 0], [50, 27, .35, .5, 0], [66, 40, .55, .7, 1], [8, 52, .6, .75, 0], [27, 60, .4, .5, 0], [46, 55, .5, .65, 1], [62, 66, .35, .45, 0], [19, 45, .3, .4, 0], [70, 20, .45, .6, 0]];
  // 触须（v26.0）：[起点 x,y, 终点 x,y, 控制点 x,y]，单位 = R。起点全在画布外的暗处，终点停在数据环之外 ——
  // 不许碰到数据面，它们只是"从外面伸进来的东西"。
  var TENDRILS = [
    [-2.10, -1.30, -1.18, -0.44, -1.72, -0.22], [2.14, -1.05, 1.22, -0.52, 1.78, 0.08],
    [-2.05, 1.38, -1.14, 0.56, -1.68, 0.48], [2.10, 1.46, 1.18, 0.64, 1.74, 0.58],
    [-0.46, -2.02, -0.30, -1.22, -1.16, -1.66], [0.54, 2.08, 0.32, 1.26, 1.24, 1.70]
  ];
  // R2 · 触须扩至 16 条：补足 10 条深空副触须
  var TENDRILS_DEEP = [
    [-2.25, -0.70, -1.25, -0.22, -1.85, 0.05], [2.20, -0.65, 1.30, -0.18, 1.90, -0.10],
    [-2.15, 0.85, -1.20, 0.32, -1.80, 0.25], [2.22, 0.90, 1.25, 0.38, 1.85, 0.30],
    [-1.20, -2.15, -0.65, -1.30, -1.45, -1.50], [1.25, -2.10, 0.70, -1.28, 1.50, -1.45],
    [-1.25, 2.15, -0.68, 1.32, -1.48, 1.52], [1.18, 2.20, 0.65, 1.35, 1.42, 1.58],
    [-0.10, -2.30, -0.05, -1.35, -0.50, -1.80], [0.12, 2.32, 0.08, 1.38, 0.55, 1.82]
  ];
  var STARS_FAR = [[9, 14, .3, .55], [37, 6, .25, .4], [61, 22, .35, .6], [84, 11, .25, .45], [18, 48, .3, .5], [52, 40, .25, .4], [73, 58, .3, .55], [30, 78, .25, .45], [90, 84, .3, .5], [5, 90, .25, .4]];

  /**
   * render(attrs, {size, depth}) → SVG HTML
   *
   * The radar deliberately stays SVG (the surrounding app relies on the
   * `.rd-lab` / `.rd-bar` event contract), but is built as a small layered
   * scene: a star-dust backdrop, an oblique platform, extruded data facets, a
   * watch bezel whose three hands read the machine clock, and a glass HUD.
   */
  function render(attrs, opt) {
    opt = opt || {};
    if (allPending(attrs)) return pendingHTML();
    var parsedSize = Number(opt.size);
    var size = isFinite(parsedSize) && parsedSize > 0 ? parsedSize : 320;
    var cx = size / 2, cy = size / 2 + 4, R = size * 0.285, n = KEYS.length;
    var parsedDepth = Number(opt.depth);
    var depth = isFinite(parsedDepth) && parsedDepth > 0 ? parsedDepth : Math.max(10, size * 0.055);
    var squash = 0.9; // a slight vertical compression makes the platform read as a plane
    var skew = depth * 0.16;
    function round(v) { return Math.round(v * 100) / 100; }
    function pt(i, r) {
      var a = -Math.PI / 2 + i * (2 * Math.PI / n);
      return [round(cx + Math.cos(a) * r), round(cy + Math.sin(a) * r * squash)];
    }
    function shift(points, dx, dy) { return points.map(function (p) { return [round(p[0] + dx), round(p[1] + dy)]; }); }
    function ps(points) { return points.map(function (p) { return p[0] + ',' + p[1]; }).join(' '); }
    function line(x1, y1, x2, y2, cls, extra) {
      return '<line class="' + cls + '" x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '"' + (extra || '') + '/>';
    }
    var uid = 'rd' + Date.now().toString(36) + Math.floor(Math.random() * 1e6).toString(36);
    var quiet = calm();
    /* v71 W1·U3 · 全书排名：opt.ranks = { mind:{r:3,n:22}, ... }，key 为 EN 键小写（兼容原大写）。
     * 只在有分值的轴上显示；r=名次（1 起），n=参与排名总人数。ranks 缺席或该维记录非法时
     * 返回 null，整条支路不触发，输出与旧版逐字节一致。 */
    var ranks = (opt.ranks && typeof opt.ranks === 'object') ? opt.ranks : null;
    function rankOf(k) {
      if (!ranks) return null;
      var rec = ranks[String(EN[k]).toLowerCase()] || ranks[EN[k]];
      if (!rec || typeof rec !== 'object') return null;
      var r = Number(rec.r), nn = Number(rec.n);
      if (!isFinite(r) || !isFinite(nn) || r < 1 || nn < 1) return null;
      return { r: Math.round(r), n: Math.round(nn) };
    }
    // 旋转类装饰动效一律用 SMIL 绕 (cx, cy)：CSS transform-origin 在 SVG 分组上会随 fill-box 漂移；走针则由 JS 按本机时钟设置 transform
    function spin(dur, reverse) {
      return quiet ? '' : '<animateTransform attributeName="transform" type="rotate" from="' + (reverse ? 360 : 0) + ' ' + cx + ' ' + cy + '" to="' + (reverse ? 0 : 360) + ' ' + cx + ' ' + cy + '" dur="' + dur + 's" repeatCount="indefinite"/>';
    }
    var Rs = R * 1.04;
    // 左右各留 PAD；上下留白按「真实内容极值」推，不写死常数。
    // 标签安全区不再占掉四分之一画布：旧版因此让真正的数据晶体缩小一圈。
    // 0.14 仍能容纳左右标签和挤出层，但让仪表盘在右坞首屏拥有更高的有效像素密度。
    // VB_H 只影响 SVG 在坞里的高度（宽度 100% 决定缩放比），加高页脚不会让晶体变小
    var PAD = Math.round(size * 0.175), VB_X = -PAD, VB_W = size + PAD * 2;
    /* R5-C §2（页脚被折线切半）——**上下留白改为内容驱动**。旧版 VB_Y = -depth*0.62 与
     * VB_H = size + depth*1.7 + 66 是两个常数，跟真实内容无关：顶部实际只有「智谋」胶囊
     * 上沿（user y≈24）在 16 与 56 之间，却留到 -11（35px 空转）；底部页脚仪表实际底
     * ≈ size+43，却留到 405（42px 空转）。这 77 user px 的空转把整块高度顶到 VB_H/36 ≈
     * 11.6 个胶囊高，坞里放不下 ⇒ 页脚落到折线下方被切半（2026-09-20 CDP 实测：
     * 390 下 `.rd-gauge-k` 底 852.6 > #dockBody 底 843，只露上半；1440 下 934.6 > 881）。
     * 现在 VB_Y 取「顶部胶囊上沿 - 8」，VB_H 取「底部内容极值 - VB_Y + 10」，
     * 底部极值取「页脚仪表下沿」与「星象潮汐谱下摆」的较大者（潮汐只在高分态画，但盒子
     * 高度不能随分数跳变，否则坞里会出现布局抖动）。 */
    var VB_MARGIN = 8;      /* 内容极值 → viewBox 边的固定呼吸位 */
    /* 顶部留白还要容下全息外框：`radar-holo-frame.js` 的导轨半高 rh = R*1.62，
     * 顶端 L 护角再外扩 2.5 ⇒ 外框最高点 = cy - R*1.62 - 2.5。VB_Y 取「轴标签上沿」与
     * 「外框最高点」的较小者再减 VB_MARGIN，两者不同步就会把护角推出 viewBox
     * （溢出可见但会被 .radar-wrap 的边框/后续版式呼应得很奇怪）。门禁
     * tests/radar_footer_fold_browser.py 的 railInsideViewBox 负责拦住不同步。 */
    var railTop = cy - R * 1.62 - 2.5;
    var FOOT_GAP = 36;      /* 地平线（fy）→ 均值仪表圆心（gy）的间距 */
    var GAUGE_R = 14;       /* 仪表圆环半径，与下方 gr 同源 */
    var TIDE_SWING = 2.2 * n; /* 潮汐谱最大摆幅：8 维正弦叠加，每维 |sin| ≤ 1 */
    var contentTop = cy - (R + 44) * squash - CHIP_H / 2;
    var footBase = size - 12;                       /* fy：地平线/页脚基线 */
    var contentBottom = Math.max(
      footBase + FOOT_GAP + GAUGE_R + 2,            /* 仪表圆环下沿（含描边） */
      footBase + FOOT_GAP + 14 + TIDE_SWING,        /* 潮汐谱最低下摆 */
      cy + R * 1.62 + 2.5                           /* 全息外框下沿的 L 护角 */
    );
    var VB_Y = Math.round(Math.min(contentTop, railTop)) - VB_MARGIN;
    var VB_H = Math.round(contentBottom - VB_Y) + VB_MARGIN * 0.5;
    var values = KEYS.map(function (k) { return scoreOf(get(attrs, k)); });
    var scored = values.filter(function (s) { return s != null; }).length;
    // 全空态已在上面返回 pendingHTML；这里的分母永远是实际有效分数数目。
    var sum = values.reduce(function (t, s) { return t + (s == null ? 0 : s); }, 0);
    var avg = Math.round(sum / scored);
    var complete = scored === n;
    var ready = 0;
    KEYS.forEach(function (k) { var ca = get(attrs, k); if (!isPending(ca) && ca.evidence && ca.evidence.length) ready++; });
    var outer = KEYS.map(function (_, i) { return pt(i, R); });
    var outerDepth = shift(outer, skew, depth);
    // 真 0 必须落在盘心；未知轴没有数据点坐标，避免其进入任何数据几何。
    var pts = values.map(function (s, i) { return s == null ? null : pt(i, R * (s / 100)); });
    var ptsDepth = complete ? shift(pts, skew, depth) : null;
    var top = topOf(attrs), topI = top ? KEYS.indexOf(top.k) : -1;
    var wc = wallClock(), ang = handAngles(wc);
    var aria = '八维属性雷达，已评分 ' + scored + ' / 8 维，已评分维度均值 ' + avg + '，证据覆盖 ' + ready + ' / 8，表盘显示本机时间 ' + fmtTime(wc);
    var out = ['<svg class="radar radar-3d' + (complete ? '' : ' rd-partial') + '" viewBox="' + VB_X + ' ' + VB_Y + ' ' + VB_W + ' ' + VB_H + '" width="100%" role="img" aria-label="' + aria + '" data-average="' + avg + '" data-scored="' + scored + '" text-rendering="geometricPrecision">'];
    out.push('<title>八维属性雷达 · 已评分 ' + scored + ' / 8 维 · 均值 ' + avg + '</title><desc>八个属性轴以立体数据面呈现，未知维度不以零分代替；胶囊内为分值与原文证据数；表盘三针为本机时间。点击任意维度可查看推断依据与原文证据。</desc>');
    var defs = ['<defs>',
      '<radialGradient id="' + uid + 'bg" cx="50%" cy="45%" r="68%"><stop offset="0" stop-color="#2a1a4a" stop-opacity=".32"/><stop offset=".58" stop-color="#180f30" stop-opacity=".15"/><stop offset="1" stop-color="#07060d" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'f" cx="38%" cy="30%" r="78%"><stop offset="0" stop-color="#f3fff8" stop-opacity=".82"/><stop offset=".25" stop-color="#8af2d0" stop-opacity=".62"/><stop offset=".62" stop-color="#3fd6a8" stop-opacity=".34"/><stop offset="1" stop-color="#5a3fb0" stop-opacity=".16"/></radialGradient>',
      '<linearGradient id="' + uid + 's" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff6e8"/><stop offset=".32" stop-color="#9af5d2"/><stop offset=".72" stop-color="#ffb45c"/><stop offset="1" stop-color="#a688ff"/></linearGradient>',
      '<linearGradient id="' + uid + 'd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6a4fd6" stop-opacity=".68"/><stop offset=".45" stop-color="#3a2a7a" stop-opacity=".62"/><stop offset="1" stop-color="#150e2c" stop-opacity=".88"/></linearGradient>',
      '<linearGradient id="' + uid + 'fa" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7af0c8" stop-opacity=".72"/><stop offset="1" stop-color="#6a4fd6" stop-opacity=".38"/></linearGradient>',
      '<linearGradient id="' + uid + 'fb" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a688ff" stop-opacity=".62"/><stop offset="1" stop-color="#4f9f88" stop-opacity=".35"/></linearGradient>',
      '<filter id="' + uid + 'g" x="-45%" y="-45%" width="190%" height="190%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="3.2" result="b"/><feColorMatrix in="b" type="matrix" values="0 0 0 0 0.48 0 0 0 0 0.94 0 0 0 0 0.78 0 0 0 .8 0" result="c"/><feMerge><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
      '<filter id="' + uid + 'shadow" x="-30%" y="-30%" width="160%" height="180%"><feGaussianBlur in="SourceAlpha" stdDeviation="4" result="b"/><feOffset dy="5" result="o"/><feComponentTransfer><feFuncA type="linear" slope=".6"/></feComponentTransfer><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
      '<radialGradient id="' + uid + 'sw" gradientUnits="userSpaceOnUse" cx="' + cx + '" cy="' + cy + '" r="' + round(Rs) + '"><stop offset="0" stop-color="#9af5d2" stop-opacity="0"/><stop offset=".55" stop-color="#9af5d2" stop-opacity=".12"/><stop offset="1" stop-color="#ffd9a0" stop-opacity=".55"/></radialGradient>',
      '<pattern id="' + uid + 'hl" patternUnits="userSpaceOnUse" width="4" height="4"><rect width="4" height="1" fill="rgba(200,180,255,.45)"/></pattern>',
      // 背景：竖向黑曜石渐变（顶紫 → 中黑 → 底部琥珀地平）、两团星云、星尘 pattern 与径向淡出 mask
      '<linearGradient id="' + uid + 'bgv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a1036" stop-opacity=".72"/><stop offset=".55" stop-color="#090614" stop-opacity=".42"/><stop offset="1" stop-color="#2a170c" stop-opacity=".46"/></linearGradient>',
      '<radialGradient id="' + uid + 'nebA" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#6a4fd6" stop-opacity=".34"/><stop offset=".45" stop-color="#4a2f9a" stop-opacity=".14"/><stop offset="1" stop-color="#1a1036" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'nebB" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#c84dff" stop-opacity=".16"/><stop offset=".5" stop-color="#7a2a70" stop-opacity=".08"/><stop offset="1" stop-color="#2a170c" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'nebC" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#3fd6a8" stop-opacity=".10"/><stop offset="1" stop-color="#3fd6a8" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'fadeG" cx="50%" cy="46%" r="62%"><stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset=".62" stop-color="#fff" stop-opacity=".7"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>',
      '<mask id="' + uid + 'fade"><rect x="' + VB_X + '" y="' + VB_Y + '" width="' + VB_W + '" height="' + VB_H + '" fill="url(#' + uid + 'fadeG)"/></mask>',
      '<pattern id="' + uid + 'stN" patternUnits="userSpaceOnUse" width="72" height="72">' + STARS_NEAR.map(function (s) { return '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="' + s[2] + '" opacity="' + s[3] + '" fill="' + (s[4] ? '#ffe4c2' : '#efe9ff') + '"/>'; }).join('') + '</pattern>',
      // v26.0 · 神秘层的三张渐变：呼吸灯光斑（薄荷→琥珀，中心近白）· 深渊之瞳的虹膜 · 触须的由暗至亮
      '<radialGradient id="' + uid + 'cone" gradientUnits="userSpaceOnUse" cx="' + cx + '" cy="' + cy + '" r="' + round(R * 1.16) + '"><stop offset="0" stop-color="#eafff6" stop-opacity=".34"/><stop offset=".42" stop-color="#7af0c8" stop-opacity=".20"/><stop offset="1" stop-color="#ffb45c" stop-opacity=".02"/></radialGradient>',
      '<radialGradient id="' + uid + 'lamp" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ffffff" stop-opacity=".95"/><stop offset=".18" stop-color="#bfffe8" stop-opacity=".72"/><stop offset=".52" stop-color="#7af0c8" stop-opacity=".30"/><stop offset="1" stop-color="#ffb45c" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'iris" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#08050f" stop-opacity=".92"/><stop offset=".34" stop-color="#1a0a2e" stop-opacity=".72"/><stop offset=".62" stop-color="#5a1f7a" stop-opacity=".34"/><stop offset=".84" stop-color="#c84dff" stop-opacity=".18"/><stop offset="1" stop-color="#ffb45c" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'pupil" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#000000" stop-opacity=".96"/><stop offset=".72" stop-color="#0a0416" stop-opacity=".78"/><stop offset="1" stop-color="#2a0f3a" stop-opacity="0"/></radialGradient>',
      '<linearGradient id="' + uid + 'tend" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#c84dff" stop-opacity="0"/><stop offset=".55" stop-color="#a06cff" stop-opacity=".30"/><stop offset="1" stop-color="#7af0c8" stop-opacity=".55"/></linearGradient>',
      '<pattern id="' + uid + 'stF" patternUnits="userSpaceOnUse" width="96" height="96">' + STARS_FAR.map(function (s) { return '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="' + s[2] + '" opacity="' + s[3] + '" fill="#d9d2ff"/>'; }).join('') + '</pattern>',
      (typeof window !== 'undefined' && window.CLRadarVisualFX && window.CLRadarVisualFX.renderDefs ? window.CLRadarVisualFX.renderDefs(uid, { innerOnly: true, reducedMotion: quiet }) : ''),
      '</defs>'];
    out.push(defs.join(''));
    // ---- 背景层（静态，不随场景漂浮）：观景窗 + 星云 + 两层星尘 + 地平线
    out.push('<g class="rd-bgfx">' +
      '<rect class="rd-bg" x="' + VB_X + '" y="' + VB_Y + '" width="' + VB_W + '" height="' + VB_H + '" rx="10" fill="url(#' + uid + 'bgv)"/>' +
      '<ellipse class="rd-neb a" cx="' + round(cx - 78) + '" cy="' + round(cy - 46) + '" rx="168" ry="104" fill="url(#' + uid + 'nebA)"/>' +
      '<ellipse class="rd-neb b" cx="' + round(cx + 104) + '" cy="' + round(cy + 74) + '" rx="150" ry="92" fill="url(#' + uid + 'nebB)"/>' +
      '<ellipse class="rd-neb c" cx="' + round(cx + 60) + '" cy="' + round(cy - 96) + '" rx="120" ry="58" fill="url(#' + uid + 'nebC)"/>' +
      '<rect class="rd-stars far" x="' + VB_X + '" y="' + VB_Y + '" width="' + VB_W + '" height="' + VB_H + '" fill="url(#' + uid + 'stF)" mask="url(#' + uid + 'fade)"/>' +
      '<rect class="rd-stars near" x="' + VB_X + '" y="' + VB_Y + '" width="' + VB_W + '" height="' + VB_H + '" fill="url(#' + uid + 'stN)" mask="url(#' + uid + 'fade)"/>' +
      /* R5-C §1：`rd-horizon`（旧 y = size-12 的全宽琥珀细线）在此处删除。
       * 它原本是「盘面 / 页脚」的分界装饰，但全息外框的下边（radar-holo-frame.js 的
       * cy + rh）已按 R5-C 从 289.86 移到 311.74，两条线只差 3.7px ⇒ 视觉上是双线。
       * 分界语义由外框下边接管（更亮更短，且有节点/护角收口），页脚分隔线仍有
       * `rd-foot-rule`（y = gy-26）在，删掉这条全宽细线不丢信息。类名与 CSS 规则一并移除。 */
      '<path class="rd-corner" d="M' + (VB_X + 8) + ',' + (VB_Y + 22) + ' V' + (VB_Y + 8) + ' H' + (VB_X + 22) + ' M' + (VB_X + VB_W - 22) + ',' + (VB_Y + 8) + ' H' + (VB_X + VB_W - 8) + ' V' + (VB_Y + 22) + '"/>' +
      '</g>');
    // ---- R1 · 深渊之瞳活化：方差调制瞳孔缩放，24 条数据驱动长度的虹膜放射线，5 层视差光影 ----
    var validScores = [];
    for (var vi = 0; vi < n; vi++) {
      var sa = get(attrs, KEYS[vi]);
      var sv = scoreOf(sa);
      if (sv != null) validScores.push(sv);
    }
    var variance = 0;
    if (validScores.length > 1) {
      var sMean = validScores.reduce(function (a, b) { return a + b; }, 0) / validScores.length;
      variance = validScores.reduce(function (a, b) { return a + Math.pow(b - sMean, 2); }, 0) / validScores.length;
    }
    var pupFactor = 1.0 - Math.min(0.42, Math.sqrt(variance) / 60);
    var irisR = round(R * 2.35), pupR = round(R * 0.62 * pupFactor);

    // 24 条虹膜射线，长度由各维分值驱动；部分数据停用这项装饰，避免未知被伪造为 50。
    var striations = [];
    for (var si = 0; complete && si < 24; si++) {
      var sAngle = (si / 24) * Math.PI * 2;
      var dimIdx = Math.floor(si / 3) % n;
      var dimScore = values[dimIdx];
      var rIn = pupR + 8;
      var rOut = rIn + (irisR * 0.52 - rIn) * (0.32 + (dimScore / 100) * 0.68);
      var sx0 = round(cx + Math.cos(sAngle) * rIn);
      var sy0 = round((cy - 4) + Math.sin(sAngle) * rIn * 0.66);
      var sx1 = round(cx + Math.cos(sAngle) * rOut);
      var sy1 = round((cy - 4) + Math.sin(sAngle) * rOut * 0.66);
      striations.push('<line class="rd-iris-ray" x1="' + sx0 + '" y1="' + sy0 + '" x2="' + sx1 + '" y2="' + sy1 + '" data-ray="' + si + '"/>');
    }

    out.push('<g class="rd-abyss" aria-hidden="true">' +
      '<ellipse class="rd-sclera-depth" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + round(irisR * 1.08) + '" ry="' + round(irisR * 0.72) + '"/>' +
      '<ellipse class="rd-iris" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + irisR + '" ry="' + round(irisR * 0.66) + '" fill="url(#' + uid + 'iris)"/>' +
      '<g class="rd-iris-rays">' + striations.join('') + '</g>' +
      '<ellipse class="rd-pupil" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + pupR + '" ry="' + round(pupR * 0.78) + '" fill="url(#' + uid + 'pupil)"/>' +
      '<ellipse class="rd-pupil-core" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + round(pupR * 0.45) + '" ry="' + round(pupR * 0.36) + '"/>' +
      '<ellipse class="rd-iris-specular" cx="' + round(cx - pupR * 0.3) + '" cy="' + round(cy - 4 - pupR * 0.25) + '" rx="' + round(pupR * 0.22) + '" ry="' + round(pupR * 0.16) + '"/>' +
      '<ellipse class="rd-limbus" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + round(irisR * 0.52) + '" ry="' + round(irisR * 0.345) + '"/>' +
      '<ellipse class="rd-lid" cx="' + cx + '" cy="' + round(cy - 4) + '" rx="' + irisR + '" ry="' + round(irisR * 0.66) + '"/>' +
      // 触须：自画布四角的暗处伸向盘心的弧线，主 6 + 深空 10 共 16 条，随呼吸微摆
      TENDRILS.map(function (td, ti) {
        var x0 = cx + td[0] * R, y0 = cy + td[1] * R, x1 = cx + td[2] * R, y1 = cy + td[3] * R, xm = cx + td[4] * R, ym = cy + td[5] * R;
        return '<path class="rd-tendril" style="--i:' + ti + '" d="M' + round(x0) + ',' + round(y0) + ' Q' + round(xm) + ',' + round(ym) + ' ' + round(x1) + ',' + round(y1) + '"/>';
      }).join('') +
      TENDRILS_DEEP.map(function (td, ti) {
        var x0 = cx + td[0] * R, y0 = cy + td[1] * R, x1 = cx + td[2] * R, y1 = cy + td[3] * R, xm = cx + td[4] * R, ym = cy + td[5] * R;
        return '<path class="rd-tendril-deep" style="--i:' + (ti + 6) + '" d="M' + round(x0) + ',' + round(y0) + ' Q' + round(xm) + ',' + round(ym) + ' ' + round(x1) + ',' + round(y1) + '"/>';
      }).join('') +
      '</g>');
    out.push('<g class="rd-scene" data-average="' + avg + '">');
    // 全息赛博雷达 HUD 外框与星象刻盘 (v29)
    if (typeof window !== 'undefined' && window.CLRadarHoloFrame && window.CLRadarHoloFrame.renderFrameSVG) {
      out.push(window.CLRadarHoloFrame.renderFrameSVG(cx, cy, R, { uid: uid, idPrefix: uid, size: size, depth: depth }));
    }
    // 精密准星层：给 3D 数据晶体一个稳定的空间基准，线条极淡，不与数据面争夺焦点。
    var rt = round(R * .72), rt2 = round(R * .49), arm = round(R * .18);
    out.push('<g class="rd-reticle" aria-hidden="true">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + rt + '"/>' +
      '<circle class="inner" cx="' + cx + '" cy="' + cy + '" r="' + rt2 + '"/>' +
      line(round(cx - arm), cy, round(cx + arm), cy, 'arm') +
      line(cx, round(cy - arm), cx, round(cy + arm), 'arm') +
      '<path class="bracket" d="M' + round(cx - rt - 5) + ',' + round(cy - 10) + 'v-8h8 M' + round(cx + rt + 5) + ',' + round(cy - 10) + 'v-8h-8 M' + round(cx - rt - 5) + ',' + round(cy + 10) + 'v8h8 M' + round(cx + rt + 5) + ',' + round(cy + 10) + 'v8h-8"/>' +
      '</g>');
    // Ambient halo establishes depth before the grid is drawn.
    out.push('<ellipse class="rd-halo" cx="' + cx + '" cy="' + (cy + depth * .18) + '" rx="' + (R * 1.55) + '" ry="' + (R * .94) + '" fill="url(#' + uid + 'bg)"/>');
    out.push('<ellipse class="rd-floor-shadow" cx="' + (cx + skew * .7) + '" cy="' + (cy + depth * .78) + '" rx="' + (R * 1.13) + '" ry="' + (R * .27) + '"/>');
    // Extruded platform: the lower polygon is intentionally offset diagonally,
    // giving the otherwise flat octagon a physical thickness.
    out.push('<g class="rd-platform" filter="url(#' + uid + 'shadow)"><polygon class="rd-platform-depth" points="' + ps(outerDepth) + '" fill="url(#' + uid + 'd)"/><polygon class="rd-platform-top" points="' + ps(outer) + '"/></g>');
    // 全息扫描线：台面上极淡的横纹，随呼吸明暗
    out.push('<polygon class="rd-platform-scan" points="' + ps(outer) + '" fill="url(#' + uid + 'hl)"/>');
    // R3 · 同心网格扩充为 8 层（主网格 4 层 + 副网格 4 层），外加扫描波
    for (var g = 1; g <= 8; g++) {
      var isMajorG = (g % 2 === 0);
      var gRatio = g / 8.0;
      var levelVal = Math.round(gRatio * 100);
      var ring = KEYS.map(function (_, i) { return pt(i, R * gRatio); });
      var ringDepth = shift(ring, skew, depth * .62);
      if (isMajorG) {
        var gridClass = 'rd-grid' + (g === 8 ? ' rd-grid-outer' : '');
        out.push('<polygon class="' + gridClass + ' rd-grid-depth" points="' + ps(ringDepth) + '" data-level="' + levelVal + '"/>');
        out.push('<polygon class="' + gridClass + '" points="' + ps(ring) + '" data-level="' + levelVal + '"/>');
        out.push('<text class="rd-tick abyss-inscription' + (g === 4 ? ' mid' : '') + '" x="' + (cx + 5) + '" y="' + round(cy - R * gRatio * squash + 3) + '">' + levelVal + '</text>');
      } else {
        out.push('<polygon class="rd-grid-sub" points="' + ps(ring) + '" data-level="' + levelVal + '"/>');
      }
    }
    // 扫描波：沿网格向外辐射高亮
    out.push('<polygon class="rd-grid-scan" points="' + ps(KEYS.map(function (_, i) { return pt(i, R * 0.75); })) + '"/>');
    for (var i = 0; i < n; i++) {
      var axis = pt(i, R), axisDepth = shift([axis], skew, depth * .62)[0];
      out.push(line(cx + skew, cy + depth * .62, axisDepth[0], axisDepth[1], 'rd-axis-depth'));
      out.push(line(cx, cy, axis[0], axis[1], 'rd-axis' + (i === topI ? ' peak' : ''), ' data-axis="' + KEYS[i] + '" data-lamp-i="' + i + '"'));
      out.push('<circle class="rd-axis-node" cx="' + axis[0] + '" cy="' + axis[1] + '" r="2.2" data-lamp-i="' + i + '"/>');
      // v26.0 · 光锥：呼吸灯巡到这一维时，从盘心朝它张开一片扇光。宽度只有 ±5°，
      // 亮的是"这一维正在被读"，不是又一层装饰环。
      var wa = Math.PI / 34, ca0 = -Math.PI / 2 + i * (2 * Math.PI / n);
      var cone = [[cx, cy], [round(cx + Math.cos(ca0 - wa) * R * 1.16), round(cy + Math.sin(ca0 - wa) * R * 1.16 * squash)], [round(cx + Math.cos(ca0 + wa) * R * 1.16), round(cy + Math.sin(ca0 + wa) * R * 1.16 * squash)]];
      out.push('<polygon class="rd-lamp-cone" data-lamp-i="' + i + '" fill="url(#' + uid + 'cone)" points="' + ps(cone) + '"/>');
    }
    // 表圈（钟表式）：宽底带 + 360 细刻 + 60 分刻 + 外沿亮线，全部用 pathLength 归一化的 dasharray 画在圆上；
    // 八个轴向主标对齐八维轴；12 点主标加粗（时钟 0 位）；最高维轴向放一枚琥珀峰标
    var Rb = R * 1.10;
    var bz = ['<g class="rd-bezel">',
      '<circle class="rd-bezel-band" cx="' + cx + '" cy="' + cy + '" r="' + round(Rb + 2.6) + '"/>',
      '<circle class="rd-bezel-fine" cx="' + cx + '" cy="' + cy + '" r="' + round(Rb + 1.2) + '" pathLength="360"/>',
      '<circle class="rd-bezel-min" cx="' + cx + '" cy="' + cy + '" r="' + round(Rb + 2.4) + '" pathLength="60"/>',
      '<circle class="rd-bezel-edge" cx="' + cx + '" cy="' + cy + '" r="' + round(Rb + 6.2) + '"/>',
      '<circle class="rd-bezel-edge inner" cx="' + cx + '" cy="' + cy + '" r="' + round(Rb - 1.4) + '"/>'];
    for (i = 0; i < n; i++) {
      var ba = -Math.PI / 2 + i * (2 * Math.PI / n), br0 = Rb - 1.2, br1 = Rb + 5.2;
      bz.push(line(round(cx + Math.cos(ba) * br0), round(cy + Math.sin(ba) * br0), round(cx + Math.cos(ba) * br1), round(cy + Math.sin(ba) * br1), 'rd-tick-mark major' + (i === 0 ? ' twelve' : '')));
    }
    if (topI >= 0) {
      var pa = -Math.PI / 2 + topI * (2 * Math.PI / n), pr0 = Rb + 7.5, pr1 = Rb + 13, pw = 3.6;
      var tipx = cx + Math.cos(pa) * pr0, tipy = cy + Math.sin(pa) * pr0, bx = cx + Math.cos(pa) * pr1, by = cy + Math.sin(pa) * pr1, nx = -Math.sin(pa) * pw, ny = Math.cos(pa) * pw;
      bz.push('<polygon class="rd-peak-mark" points="' + round(tipx) + ',' + round(tipy) + ' ' + round(bx + nx) + ',' + round(by + ny) + ' ' + round(bx - nx) + ',' + round(by - ny) + '"><title>最高维 ' + top.k + ' ' + Math.round(top.score) + '</title></polygon>');
    }
    bz.push('</g>'); out.push(bz.join(''));
    // ---- R2 · 铭文环加密双层化：外 48 + 内 24 双层反向符文环（转速比 1 : -0.618）
    //      每枚符文绑定一维（data-dim），悬停某维时点亮
    var runeR = round(Rb + 31), runeROuter = round(Rb + 44);
    if (window.CLAbyssRing && typeof window.CLAbyssRing.createSVGRuneRing === 'function') {
      out.push(window.CLAbyssRing.createSVGRuneRing({
        cx: cx, cy: cy, r: runeR, rOuter: runeROuter, squash: squash, forRadar: true, dimCount: n
      }));
    } else {
      var rn = [], rnOuter = [];
      for (i = 0; i < 24; i++) {
        var ra = -Math.PI / 2 + i * (Math.PI * 2 / 24);
        var rx = round(cx + Math.cos(ra) * runeR), ry = round(cy + Math.sin(ra) * runeR * squash);
        var rdeg = round(ra * 180 / Math.PI + 90), rflip = i % 3 === 1 ? ' scale(-1,1)' : '';
        var dimIdx = Math.floor(i / 3) % n;
        rn.push('<g class="rd-rune" data-i="' + i + '" data-dim="' + dimIdx + '" transform="translate(' + rx + ' ' + ry + ') rotate(' + rdeg + ') scale(1.42)' + rflip + '">' +
          '<path d="' + RUNE_STROKES[(i * 5 + (i >> 2)) % RUNE_STROKES.length] + '" transform="translate(-5 -5)"/></g>');
      }
      for (var oi = 0; oi < 48; oi++) {
        var ora = -Math.PI / 2 + oi * (Math.PI * 2 / 48);
        var orx = round(cx + Math.cos(ora) * runeROuter), ory = round(cy + Math.sin(ora) * runeROuter * squash);
        var ordeg = round(ora * 180 / Math.PI + 90), orflip = oi % 2 === 1 ? ' scale(-1,1)' : '';
        var odimIdx = Math.floor(oi / 6) % n;
        rnOuter.push('<g class="rd-rune-outer" data-outer-i="' + oi + '" data-dim="' + odimIdx + '" transform="translate(' + orx + ' ' + ory + ') rotate(' + ordeg + ') scale(1.18)' + orflip + '">' +
          '<path d="' + RUNE_STROKES[(oi * 7 + 3) % RUNE_STROKES.length] + '" transform="translate(-5 -5)"/></g>');
      }
      out.push('<g class="rd-runes-outer" aria-hidden="true" data-speed="1.0">' + rnOuter.join('') + '</g>');
      out.push('<g class="rd-runes" aria-hidden="true" data-speed="-0.618">' + rn.join('') + '</g>');
    }
    // 扫描环保留为点阵质感的参考圈
    out.push('<circle class="rd-scan-ring" cx="' + cx + '" cy="' + cy + '" r="' + round(Rs) + '" pathLength="240"/>');
    // 走针 = 本机时钟：初始角度在渲染时就按 Date() 算好（静态快照也正确），之后由 tickClocks() 每帧更新 transform
    function handEl(cls, len, tail, w, deg, extra) {
      return '<g class="rd-hand ' + cls + '" transform="rotate(' + deg.toFixed(2) + ' ' + cx + ' ' + cy + ')">' + (extra || '') +
        '<line class="rd-hand-shadow" x1="' + cx + '" y1="' + round(cy + tail) + '" x2="' + cx + '" y2="' + round(cy - len) + '" stroke-width="' + (w * 2.6) + '"/>' +
        '<line class="rd-hand-line" x1="' + cx + '" y1="' + round(cy + tail) + '" x2="' + cx + '" y2="' + round(cy - len) + '" stroke-width="' + w + '"/>' +
        '<circle class="rd-hand-tip" cx="' + cx + '" cy="' + round(cy - len) + '" r="' + (w * 1.1 + 0.6) + '"/></g>';
    }
    // 秒针余晖：跟在秒针身后 26° 的扇面，与秒针同组旋转，径向渐变从心到缘
    var swA = -26 * Math.PI / 180, swR = Rs + 1;
    var sweep = '<path class="rd-sweep" fill="url(#' + uid + 'sw)" d="M' + cx + ',' + cy + ' L' + round(cx + Math.sin(swA) * swR) + ',' + round(cy - Math.cos(swA) * swR) + ' A' + round(swR) + ',' + round(swR) + ' 0 0 1 ' + cx + ',' + round(cy - swR) + ' Z"/>';
    out.push('<g class="rd-hands" data-cx="' + cx + '" data-cy="' + cy + '" role="img" aria-label="本机时间 ' + fmtTime(wc) + '">' +
      handEl('hour', R * 0.58, 8, 2.6, ang.h) +
      handEl('minute', R * 0.92, 11, 1.5, ang.m) +
      handEl('second', Rs + 3, 14, 0.85, ang.s, sweep) + '</g>');
    // 数据形：下层 facets + 顶层金属渐变面
    out.push('<g class="rd-data">');
    // 全书基准幽灵线与 R6 命运差值桥（v29/P3）。部分数据不向比较层传伪零英雄几何。
    if (complete && typeof window !== 'undefined' && window.CLRadarHoloFrame && opt && opt.benchmark) {
      var gp = window.CLRadarBenchmark ? window.CLRadarBenchmark.getGhostPoints(opt.benchmark, R, cx, cy, squash) : null;
      if (gp && window.CLRadarHoloFrame.renderGhostPolygon) {
        var bScores = (typeof opt.benchmark === 'object' && opt.benchmark.scores) ? opt.benchmark.scores : opt.benchmark;
        out.push(window.CLRadarHoloFrame.renderGhostPolygon(gp, { uid: uid, squash: squash, heroPoints: pts, scores: values, benchScores: bScores }));
      }
    }
    if (complete) {
      out.push('<polygon class="rd-fill-depth" points="' + ps(ptsDepth) + '"/>');
      for (i = 0; i < n; i++) {
        var j = (i + 1) % n;
        out.push('<polygon class="rd-facet facet-' + i + '" fill="url(#' + uid + (i % 2 ? 'fb' : 'fa') + ')" points="' + [pts[i], pts[j], ptsDepth[j], ptsDepth[i]].map(function (p) { return p.join(','); }).join(' ') + '"/>');
      }
      out.push('<polygon class="rd-fill" fill="url(#' + uid + 'f)" points="' + ps(pts) + '"/>');
      out.push('<polygon class="rd-gloss" points="' + ps(pts.map(function (p) { return [round(cx + (p[0] - cx) * .82), round(cy + (p[1] - cy) * .82)]; })) + '"/>');
      out.push('<polygon class="rd-shape-aura" points="' + ps(pts) + '"/>');
      out.push('<polygon class="rd-shape" stroke="url(#' + uid + 's)" filter="url(#' + uid + 'g)" points="' + ps(pts) + '"/>');
    } else {
      // 部分数据只保留原八边形轴序中“两端均有效”的开放线段，不跨未知轴闭合。
      for (i = 0; i < n; i++) {
        var next = (i + 1) % n;
        if (pts[i] && pts[next]) out.push(line(pts[i][0], pts[i][1], pts[next][0], pts[next][1], 'rd-shape-open', ' stroke="url(#' + uid + 's)" stroke-width="1.5" fill="none"'));
      }
    }
    // R5: 3D 晶体材质切面高光脊线（从盘心到顶点的晶体折射棱）
    if (complete) for (i = 0; i < n; i++) {
      out.push('<line class="rd-crystal-ridge" x1="' + cx + '" y1="' + cy + '" x2="' + pts[i][0] + '" y2="' + pts[i][1] + '"/>');
    }
    // R5: 大分值顶点（≥80 或最高维）光晶簇 (Crystal Clusters)
    for (i = 0; i < n; i++) {
      if (complete && (values[i] >= 80 || i === topI)) {
        var vp = pts[i];
        var va = -Math.PI / 2 + i * (2 * Math.PI / n);
        var pLen = (i === topI ? 14 : 10);
        var pTipX = round(vp[0] + Math.cos(va) * pLen), pTipY = round(vp[1] + Math.sin(va) * pLen * squash);
        var plx = round(vp[0] + Math.cos(va - 0.45) * (pLen * 0.7)), ply = round(vp[1] + Math.sin(va - 0.45) * (pLen * 0.7) * squash);
        var prx = round(vp[0] + Math.cos(va + 0.45) * (pLen * 0.7)), pry = round(vp[1] + Math.sin(va + 0.45) * (pLen * 0.7) * squash);
        out.push('<g class="rd-crystal-cluster" data-axis="' + KEYS[i] + '">' +
          '<polygon class="rd-cluster-petal main" points="' + vp[0] + ',' + vp[1] + ' ' + (vp[0] - 2) + ',' + (vp[1] + 1) + ' ' + pTipX + ',' + pTipY + ' ' + (vp[0] + 2) + ',' + (vp[1] + 1) + '"/>' +
          '<polygon class="rd-cluster-petal left" points="' + vp[0] + ',' + vp[1] + ' ' + plx + ',' + ply + ' ' + (vp[0] - 1) + ',' + vp[1] + '"/>' +
          '<polygon class="rd-cluster-petal right" points="' + vp[0] + ',' + vp[1] + ' ' + prx + ',' + pry + ' ' + (vp[0] + 1) + ',' + vp[1] + '"/>' +
          '</g>');
      }
    }
    // 信标：每个顶点向上升起的渐细光柱，高度随分值；低置信维度更淡
    for (i = 0; i < n; i++) {
      if (values[i] == null) continue;
      var bv = pts[i], bh = 5 + 24 * values[i] / 100, blow = isLow(get(attrs, KEYS[i]));
      out.push('<polygon class="rd-beacon' + (blow ? ' low' : '') + '" data-lamp-i="' + i + '" points="' + round(bv[0] - 1.3) + ',' + bv[1] + ' ' + round(bv[0] + 1.3) + ',' + bv[1] + ' ' + bv[0] + ',' + round(bv[1] - bh) + '" style="animation-delay:' + (0.5 + i * 0.06) + 's,' + (1 + i * 0.13) + 's"/>');
    }
    out.push('</g>');
    // 顶点 + 引导线 + 分值胶囊：名 + 大号分值（按档位着色）/ EN · 证据条数 · 低证 / 底部分值条
    for (i = 0; i < n; i++) {
      var a = get(attrs, KEYS[i]), score = scoreOf(a), pend = score == null, low = isLow(a), sc = pend ? null : Math.round(score), tier = pend ? 'pend' : tierOf(sc, low), vp = pts[i] || pt(i, R);
      // 离心距离按方位分档：正左 / 正右两侧的横向余量最少，收得更近才放得下完整胶囊；上下两轴余量最多，放得最远
      var vertical = i === 0 || i === 4, side = i === 2 || i === 6;
      var lp = pt(i, R + (vertical ? 44 : side ? 20 : 30)), leader = pt(i, R + 12);
      var anchor = Math.abs(lp[0] - cx) < 6 ? 'middle' : (lp[0] > cx ? 'start' : 'end');
      var evidenceCount = (a.evidence && a.evidence.length) || 0;
      // 胶囊宽度按真实文案估算并夹进 viewBox：固定宽度会在「低证 / 最高维」这类长副行上被画布切掉（左轴曾少 32px）
      var room = anchor === 'start' ? (VB_X + VB_W - CHIP_G) - (lp[0] - 4) : anchor === 'end' ? (lp[0] + 4) - (VB_X + CHIP_G) : VB_W - CHIP_G * 2;
      var headW = txtW(KEYS[i], 13.5, false, 0.08) + 12 + txtW(pend ? '—' : String(sc), 17, true, -0.02);
      var peak = i === topI, sub = subText(KEYS[i], pend, evidenceCount, low, peak);
      var subW = function (t) { return txtW(t, 8.5, true, 0.1); };
      /* v71 W1·U3 · 排名并入副行宽度估算。空间不足时按「维名 > 分值 > 排名 > EN/证据」砍：
       * 先砍「最高维」尾标（既有逻辑），再砍 EN/证据整段（副行只留排名），最后才放弃排名。 */
      var rank = pend ? null : rankOf(KEYS[i]);
      var rankTxt = rank ? '#' + rank.r + '/' + rank.n : '';
      var rankW = rank ? subW(' · ' + rankTxt) : 0;
      var wantW = Math.max(headW, subW(sub) + rankW) + 18;
      if (peak && wantW > room) { peak = false; sub = subText(KEYS[i], pend, evidenceCount, low, false); wantW = Math.max(headW, subW(sub) + rankW) + 18; }
      var subRankOnly = false;
      if (rank && wantW > room) { subRankOnly = true; wantW = Math.max(headW, subW(rankTxt)) + 18; }
      if (rank && wantW > room) { rank = null; rankTxt = ''; rankW = 0; subRankOnly = false; wantW = Math.max(headW, subW(sub)) + 18; }
      var chipW = Math.round(Math.max(84, Math.min(wantW, room))), chipH = CHIP_H;
      var chipX = anchor === 'start' ? lp[0] - 4 : (anchor === 'end' ? lp[0] - chipW + 4 : lp[0] - chipW / 2);
      var chipY = lp[1] - chipH / 2;
      chipX = Math.max(VB_X + CHIP_G, Math.min(chipX, VB_X + VB_W - CHIP_G - chipW));
      chipY = Math.max(VB_Y + CHIP_G, Math.min(chipY, VB_Y + VB_H - CHIP_G - chipH));
      out.push(line(leader[0], leader[1], round(anchor === 'start' ? chipX : anchor === 'end' ? chipX + chipW : lp[0]), round(anchor === 'middle' ? (i === 0 ? chipY + chipH : chipY) : chipY + chipH / 2), 'rd-leader' + (low ? ' low' : '')));
      if (!pend) out.push('<g class="rd-vert' + (low ? ' low' : '') + '" data-axis="' + KEYS[i] + '" data-score="' + sc + '" data-lamp-i="' + i + '" style="animation-delay:' + (0.34 + i * 0.065) + 's;transform-origin:' + vp[0] + 'px ' + vp[1] + 'px">' +
        '<circle class="rd-lamp" cx="' + vp[0] + '" cy="' + vp[1] + '" r="22" fill="url(#' + uid + 'lamp)"/>' +
        '<circle class="rd-pulse" cx="' + vp[0] + '" cy="' + vp[1] + '" r="' + (low ? 7 : 10) + '"/>' +
        '<circle class="rd-ring" cx="' + vp[0] + '" cy="' + vp[1] + '" r="' + (low ? 4.5 : 6.5) + '"/>' +
        '<circle class="rd-dot' + (low ? ' low' : '') + '" cx="' + vp[0] + '" cy="' + vp[1] + '" r="' + (low ? 2 : 2.8) + '"/></g>');
      out.push('<g class="rd-lab tier-' + tier + (low ? ' low' : '') + (i === topI ? ' peak' : '') + '" data-lamp-i="' + i + '" data-axis="' + KEYS[i] + '"' + (pend ? '' : ' data-score="' + sc + '"') + ' data-evidence="' + evidenceCount + '" data-confidence="' + (pend ? 'pending' : (low ? 'low' : 'supported')) + '" data-w="' + chipW + '"' + (rank ? ' data-rank="' + rank.r + '" data-rank-of="' + rank.n + '"' : '') + ' role="button" tabindex="0" aria-label="' + KEYS[i] + (pend ? ' 待建档，尚无有效分值' : ' ' + sc + ' 分') + '，证据 ' + evidenceCount + ' 条，' + (pend ? '待建档' : (low ? '低置信' : '有原文支撑')) + (i === topI ? '，最高维' : '') + (rank ? '，全书第 ' + rank.r + ' / ' + rank.n + ' 名' : '') + '">' +
        '<rect class="rd-chip-shadow" x="' + round(chipX + 1) + '" y="' + round(chipY + 3) + '" width="' + chipW + '" height="' + chipH + '" rx="6"/>' +
        '<rect class="rd-chip" x="' + round(chipX) + '" y="' + round(chipY) + '" width="' + chipW + '" height="' + chipH + '" rx="6"/>' +
        '<rect class="rd-chip-highlight" x="' + round(chipX + 1) + '" y="' + round(chipY + 1) + '" width="' + (chipW - 2) + '" height="' + (chipH - 2) + '" rx="5"/>' +
        '<rect class="rd-chip-track" x="' + round(chipX + 9) + '" y="' + round(chipY + chipH - 1) + '" width="' + (chipW - 18) + '" height="0.6" rx="0.3"/>' +
        (pend ? '' : '<rect class="rd-chip-line" x="' + round(chipX + 9) + '" y="' + round(chipY + chipH - 1) + '" width="' + Math.max(2, Math.round((chipW - 18) * score / 100)) + '" height="0.6" rx="0.3"/>') +
        '<text class="rd-name" x="' + round(chipX + 9) + '" y="' + round(chipY + 15) + '">' + KEYS[i] + '</text>' +
        (pend ? '' : '<rect class="rd-score-plate" x="' + round(chipX + chipW - 39) + '" y="' + round(chipY + 2) + '" width="34" height="19" rx="4"/>') +
        '<text class="rd-score" x="' + round(chipX + chipW - 9) + '" y="' + round(chipY + 15) + '" text-anchor="end">' + (pend ? '—' : sc) + '</text>' +
        (subRankOnly ? '' : statusPillSVG(chipX, chipY, chipW, EN[KEYS[i]], pend, evidenceCount, low, peak)) +
        (rank ? rankBadgeSVG(chipX, chipY, chipW, subRankOnly ? 0 : subW(sub) + subW(' · '), rankTxt, tier, rank.r === 1) : '') +
        '<text class="rd-val" x="' + round(chipX + 9) + '" y="' + round(chipY + 31.5) + '">' +
        (subRankOnly ? rankTspan(rank, tier) : EN[KEYS[i]] + (pend ? ' · <tspan class="rd-low rd-low-pend">待建档</tspan>' : ' · <tspan class="rd-ev' + (low ? ' rd-low' : '') + '">' + evidenceCount + 'E</tspan>' + (lowTag(evidenceCount, low) ? ' · <tspan class="rd-low rd-low-weak">低证</tspan>' : '') + (peak ? ' · <tspan class="rd-peak">最高维</tspan>' : '')) + (rank ? ' · ' + rankTspan(rank, tier) : '')) +
        '</text></g>');
    }
    // 中心 = 表芯宝石轴承（不是分值牌）。旧版把均值压成一枚 25px 不透明圆盘扣在盘心，
    // 低分维度（野心 18 → 半径 16px）整个被盖住——中心恰恰是低分区，最不该被读数占用。
    // 均值改挂到页脚仪表，中心只留走针的支点与一圈细齿。
    var coreTicks = '';
    for (i = 0; i < 24; i++) {
      var ca = i / 24 * Math.PI * 2, cr0 = i % 6 === 0 ? 12.5 : 13.4, cr1 = i % 6 === 0 ? 16.5 : 15.2;
      coreTicks += line(round(cx + Math.cos(ca) * cr0), round(cy + Math.sin(ca) * cr0), round(cx + Math.cos(ca) * cr1), round(cy + Math.sin(ca) * cr1), i % 6 === 0 ? 'major' : '');
    }
    out.push('<g class="rd-core" style="transform-origin:' + cx + 'px ' + cy + 'px">' +
      '<circle class="rd-core-shadow" cx="' + cx + '" cy="' + cy + '" r="10.5"/>' +
      '<circle class="rd-core-ring rd-core-ring-a" cx="' + cx + '" cy="' + cy + '" r="8.6"/>' +
      '<g class="rd-core-ticks">' + spin(28, true) + coreTicks + '</g>' +
      '<circle class="rd-core-jewel" cx="' + cx + '" cy="' + cy + '" r="4.6"/>' +
      '<circle class="rd-core-dot" cx="' + cx + '" cy="' + cy + '" r="2.1"/></g>');
    out.push('</g>');
    // ---- 页脚（U05 @contract v70 · SVG 底部重排）：v17.14/v26.0 曾在这块塞时钟读数 +
    // NEURAL PROFILE 装饰文案 + 两行绝对刻度图例，三处不同锚点（start/middle/end）在同一 y 附近
    // 互相咬字（outputs/unification-b2-shell-*.png 与 review 均已实拍证实）。
    // 本版只留一件事：均值 · 有效维 · 证据覆盖，单行、单一文本节点，不与任何几何/分数语义相关。
    // 时钟读数与「NEURAL PROFILE」纯装饰文案整体移出图内（按任务书「可删」处理）；
    // 刻度定义（50 常人…96+ 传说）与「证据优先」说明本就在 evidenceHTML/radar-caption 外部重复展示，
    // 从 SVG 页脚删除不丢信息，只去重叠。
    var fy = size - 12, lx = VB_X + 14, rx = VB_X + VB_W - 14;
    // 均值仪表：弧长 = 均值；唯一一行文字 = 均值 · 有效维 n/8 · 证据覆盖 k/8。
    // R5-C §2：FOOT_GAP / GAUGE_R 上提为常量，与 VB_H 的页脚预留（见上方 contentBottom）同源，
    // 两处一旦不同步就会「盒子留够了但仪表画在盒子外」，所以不允许各写一遍魔数。
    var gy = fy + FOOT_GAP, gx = lx + 16, gr = GAUGE_R;
    // R8 · 星象潮汐图：8 维分值化为叠加正弦潮汐谱（沿用既有几何，不属于本次文字重排范围）
    var tideSvg = '';
    if (complete) {
      var tidePath = 'M' + round(gx + 30) + ',' + round(gy + 14);
      for (var ti = 0; ti <= 20; ti++) {
        var tx = round(gx + 30 + ti * 3.2), tyWave = 0;
        for (var ki = 0; ki < n; ki++) tyWave += (values[ki] / 100) * Math.sin(ti * 0.35 + ki * 0.785);
        tidePath += ' L' + tx + ',' + round(gy + 14 - tyWave * 2.2);
      }
      tideSvg = '<path class="rd-tide-spectrum" d="' + tidePath + '" fill="none" stroke="rgba(122,240,200,0.38)" stroke-width="0.8" stroke-dasharray="2 3"/>';
    }

    out.push('<g class="rd-gauge" role="img" aria-label="已评分维度均值 ' + avg + ' / 100，已评分 ' + scored + ' / 8，证据覆盖 ' + ready + ' / 8">' +
      line(lx, round(gy - 26), rx, round(gy - 26), 'rd-foot-rule') +
      tideSvg +
      '<circle class="rd-gauge-track" cx="' + gx + '" cy="' + gy + '" r="' + gr + '"/>' +
      '<circle class="rd-gauge-arc" cx="' + gx + '" cy="' + gy + '" r="' + gr + '" pathLength="100" stroke-dasharray="' + avg + ' 100" transform="rotate(-90 ' + gx + ' ' + gy + ')"/>' +
      '<text class="rd-gauge-v" x="' + gx + '" y="' + round(gy + 4.5) + '" text-anchor="middle">' + avg + '</text>' +
      '<text class="rd-gauge-k" x="' + round(gx + 30) + '" y="' + round(gy + 2) + '">均值 ' + avg + ' · 有效维 ' + scored + '/8 · 证据覆盖 ' + ready + '/8</text>' +
      '</g>');
    out.push('</svg>');
    ensureClock();
    return out.join('');
  }

  /** 八维条形明细（雷达下方），每行：名 / 分 / 条 / 依据一行 */
  function barsHTML(attrs, opt) {
    var safeAttrs = normalizedAttrs(attrs);
    if (typeof window !== 'undefined' && window.CLRadarBarsEnhanced && window.CLRadarBarsEnhanced.renderBars) {
      return window.CLRadarBarsEnhanced.renderBars(safeAttrs, opt && opt.benchmark, opt && opt.activeKey);
    }
    return '<div class="rd-bars">' + KEYS.map(function (k, i) {
      var a = get(attrs, k), s0 = scoreOf(a), pend = s0 == null, low = isLow(a), s = pend ? 0 : s0;
      return '<div class="rd-bar tier-' + (pend ? 'pend' : tierOf(Math.round(s), low)) + (low ? ' low' : '') + (pend ? ' pend' : '') + '" data-axis="' + k + '" style="animation-delay:' + (i * 0.05) + 's">' +
        '<span class="rb-k">' + k + '<i>' + EN[k] + '</i></span>' +
        '<span class="rb-t"><i style="width:' + (pend ? 0 : s) + '%"></i></span>' +
        '<span class="rb-v mono">' + (pend ? '—' : Math.round(s)) + '</span>' +
        '<span class="rb-b">' + esc(pend ? '待建档 · 未评分' : (a.basis || (low ? '材料未直接支撑，保守估计' : ''))) + '</span></div>';
    }).join('') + '</div>';
  }

  function evidenceHTML(attrs, key, opt) {
    if (typeof window !== 'undefined' && window.CLRadarEvidenceCard && window.CLRadarEvidenceCard.renderCard && opt && opt.character) {
      return window.CLRadarEvidenceCard.renderCard(key, opt.character, opt.ranked, normalizedAttrs(attrs), opt.benchmark);
    }
    var a = get(attrs, key), ev = a.evidence || [], s0 = scoreOf(a), pend = s0 == null;
    var h = '<div class="rd-ev"><div class="rd-ev-h"><b>' + esc(key) + '</b><span class="mono">' + EN[key] + ' · ' + (pend ? '—' : Math.round(s0)) + ' / 100</span>' +
      (pend ? '<span class="tag low">待建档 · 未评分</span>' : isLow(a) ? '<span class="tag low">证据不足 · 保守分</span>' : '') + (a.unverified ? '<span class="tag low" title="模型给出的“原文”不在材料里，已剔除">剔除伪证据 ' + a.unverified + '</span>' : '') + '</div>' +
      '<div class="rd-ev-def">' + esc(DEF[key]) + '</div><div class="rd-ev-scale mono">' + SCALE + '</div>';
    if (a.chain) h += '<div class="rd-ev-basis rd-ev-chain"><span class="eyebrow">推理链' + (a.confidence != null ? ' · 置信 ' + Math.round(a.confidence) : '') + '</span>' + esc(a.chain) + '</div>';
    if (a.basis) h += '<div class="rd-ev-basis"><span class="eyebrow">推断依据</span>' + esc(a.basis) + '</div>';
    if (!ev.length) h += '<div class="rd-ev-none">材料中没有直接支撑这一维的原文。</div>';
    else h += '<div class="rd-ev-q">' + ev.map(function (s) { return '<blockquote>「' + esc(s) + '」</blockquote>'; }).join('') + '</div>';
    return h + '</div>';
  }

  /** 迷你八维竖条（悬浮速览 / 历史卡用）：8 根竖条 + 首字标签 */
  function miniHTML(attrs) {
    return '<div class="rd-mini">' + KEYS.map(function (k) {
      var a = get(attrs, k), s0 = scoreOf(a), pend = s0 == null, s = pend ? 0 : s0;
      return '<span class="mb' + (isLow(a) ? ' low' : '') + (pend ? ' pend' : '') + '" title="' + k + ' ' + (pend ? '待建档' : Math.round(s)) + '"><i style="height:' + (pend ? 4 : Math.max(6, s)) + '%"></i><em>' + k[0] + '</em></span>';
    }).join('') + '</div>';
  }
  /** 最高维（只在已评分的维度之间比；全部待建档 → null） */
  function topOf(attrs) {
    var best = null;
    KEYS.forEach(function (k) { var a = get(attrs, k), s = scoreOf(a); if (s == null) return; if (!best || s > best.score) best = { k: k, score: s }; });
    return best;
  }

  /** 呼吸灯相位（单位 = 维，连续 0..8）。scene.js 的晶冠读同一个函数 → 右坞的表与 3D 晶冠亮同一维。
   *  P0 · S3：时钟改读总线（与场景 tAnim 同源）；总线缺席时退回 nowSec()，行为不变。 */
  function lampPhase() {
    var B = window.CLAbyssBreath;
    var t = (B && B.t) ? B.t() : nowSec();
    return (t / LAMP_SLOT) % KEYS.length;
  }
  window.CLRadar = { KEYS: KEYS, EN: EN, DEF: DEF, SCALE: SCALE, scoreOf: scoreOf, LAMP_SLOT: LAMP_SLOT, lampPhase: lampPhase, lampAt: lampAt, wakeAt: wakeAt, auraPhase: auraPhase, render: render, barsHTML: barsHTML, evidenceHTML: evidenceHTML, miniHTML: miniHTML, topOf: topOf, tierOf: tierOf, tierName: tierName, isPending: isPending, allPending: allPending, wallClock: wallClock, handAngles: handAngles, ensureClock: ensureClock,
    lightOwner: window.CLAbyssGovernance && window.CLAbyssGovernance.LIGHT_OWNER ? window.CLAbyssGovernance.LIGHT_OWNER.radar : 'top-dimension',
    motionLayer: window.CLAbyssGovernance && window.CLAbyssGovernance.MOTION_LAYERS ? window.CLAbyssGovernance.MOTION_LAYERS : null };

  if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
    window.CLAbyssBreath.subscribe(function (snap) {
      if (snap && snap.t && typeof ensureClock === 'function' && radarSvgs().length) {
        ensureClock();
      }
    });
  }
})();
