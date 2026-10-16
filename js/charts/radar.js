(function () {
  'use strict';
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' };
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
  var TICK_SETTLE = 0.34;
  // ---- v26.0 · 轮流呼吸灯 ------------------------------------------------------------
  var LAMP_SLOT = 2.62, LAMP_WIDE = 1.34, LAMP_GAIN = 1.55;
  var IRIS_PER = 37.6, BLINK_PER = 28.3;
  function nowSec() { return (typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()) / 1000; }
  function lampAt(i, ph, n) {
    var d = (i - ph) % n; if (d < 0) d += n; if (d > n / 2) d -= n;
    var x = Math.abs(d) / LAMP_WIDE;
    if (x >= 1) return 0;
    return Math.pow(Math.cos(x * Math.PI / 2), LAMP_GAIN * 2);
  }
  var WAKE_SPAN = 2.15, WAKE_GAIN = 0.62;
  function wakeAt(i, ph, n) {
    var d = (ph - i) % n; if (d < 0) d += n;
    if (d > WAKE_SPAN) return 0;
    return Math.pow(1 - d / WAKE_SPAN, 1.9) * WAKE_GAIN;
  }
  function auraPhase(n) {
    var q = calm(), B = window.CLAbyssBreath, t, breath, iris, blink;
    if (B && B.snap) {
      var s = B.snap();
      t = s.t; breath = s.breath; iris = s.iris; blink = s.blink;
    } else {
      t = nowSec();
      var bPeriod = (B && B.C && B.C.BREATH_CYCLE) ? B.C.BREATH_CYCLE : 9.4;
      breath = 0.5 + 0.5 * Math.sin(t * Math.PI * 2 / bPeriod);
      iris = 0.5 + 0.5 * Math.sin(t * Math.PI * 2 / IRIS_PER);
      var bp = (t % BLINK_PER) / BLINK_PER;
      blink = bp < 0.06 ? Math.exp(-Math.pow((bp - 0.03) / 0.014, 2)) : 0;
    }
    var ph = (t / LAMP_SLOT) % n;
    return { t: t, ph: ph, breath: q ? 0.5 : breath, iris: q ? 0.55 : iris, blink: q ? 0 : blink, n: n, calm: q, src: B ? 'bus' : 'wall' };
  }
  var WEEK = '日一二三四五六';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
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
        return wrap.outerHTML;
      } catch (e) {  }
    }
    return '<div class="rd-pending"><b>八维待建档</b><span>' + PENDING_DETAIL + '</span></div>';
  }
  function calm() { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
  function easeOutBack(t) { var c = 1.10158, c3 = c + 1; return t >= 1 ? 1 : 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function tierOf(s, low) { return low ? 'low' : s >= 96 ? 'legend' : s >= 85 ? 'hi' : s >= 70 ? 'up' : 'mid'; }
  function tierName(s, low) { return low ? '低证保守' : s >= 96 ? '传说级' : s >= 85 ? '一方之最' : s >= 70 ? '圈内出色' : s >= 41 ? '常人' : s >= 21 ? '弱于常人' : '明显低于常人'; }
  var CHIP_H = 36, CHIP_G = 4;
  function txtW(s, px, mono, ls) {
    var w = s.length * px * (ls || 0);
    for (var q = 0; q < s.length; q++) { var cc = s.charCodeAt(q); w += cc > 0x2e80 ? px : px * (mono ? 0.6 : 0.52); }
    return w;
  }
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
  function rankBadgeSVG(chipX, chipY, chipW, prefixW, txt, tier, top) {
    var r2 = function (v) { return Math.round(v * 100) / 100; };
    var w = txtW(txt, 8.5, true, 0.1) + 7;
    var x0 = Math.max(chipX + 6, Math.min(chipX + 9 + prefixW - 3, chipX + chipW - 9 - w));
    var c = top ? '#ffd9a0' : (RANK_TIER_FILL[tier] || RANK_TIER_FILL.mid);
    return '<rect class="rd-rank-badge' + (top ? ' rd-rank-top' : '') + '" x="' + r2(x0) + '" y="' + r2(chipY + 22) + '" width="' + r2(w) + '" height="12" rx="5.5" fill="' + c + '" fill-opacity="' + (top ? '.22' : '.1') + '" stroke="' + c + '" stroke-opacity="' + (top ? '.9' : '.45') + '" stroke-width=".75"/>';
  }
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
    var r2 = function (v) { return Math.round(v * 100) / 100; };
    return '<rect class="rd-status-pill ' + cls + '" x="' + r2(x0) + '" y="' + r2(chipY + 22) + '" width="' + r2(w) + '" height="12" rx="5.5"/>';
  }
  function wallClock() {
    var d = new Date(), ms = d.getMilliseconds(), s = d.getSeconds(), m = d.getMinutes(), h = d.getHours();
    var sec = s + ms / 1000, min = m + sec / 60;
    return { d: d, s: s, m: m, h: h, frac: ms / 1000, sec: sec, min: min, hr: (h % 12) + min / 60, epoch: Math.floor(d.getTime() / 1000) };
  }
  function handAngles(wc) {
    var te = wc.frac < TICK_SETTLE ? easeOutBack(wc.frac / TICK_SETTLE) : 1;
    return { s: calm() ? wc.sec * 6 : ((wc.s - 1) + te) * 6, m: wc.min * 6, h: wc.hr * 30 };
  }
  function fmtTime(wc) { return pad2(wc.h) + ':' + pad2(wc.m) + ':' + pad2(wc.s); }
  function fmtDate(wc) { return wc.d.getFullYear() + '-' + pad2(wc.d.getMonth() + 1) + '-' + pad2(wc.d.getDate()) + ' · 周' + WEEK[wc.d.getDay()]; }

  // ---- 表盘 + 神秘层驱动：一个 rAF 循环服务页面里所有雷达（右坞重绘后自动接管新表）；连续 4 s 找不到表就自停，render() 会再拉起
  var clockRaf = 0, clockIdle = 0, lastSec = -1;
  function rot(el, deg, cx, cy) { if (el) el.setAttribute('transform', 'rotate(' + deg.toFixed(2) + ' ' + cx + ' ' + cy + ')'); }
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
  var clockSvgs = null;
  function radarSvgs() { return clockSvgs || (clockSvgs = document.getElementsByClassName('radar-3d')); }
  function tickClocks() {
    var svgs = radarSvgs();
    if (!svgs.length) { if (++clockIdle > 240) { clockRaf = 0; return; } clockRaf = requestAnimationFrame(tickClocks); return; }
    clockIdle = 0;
    var wc = wallClock(), ang = handAngles(wc), secChanged = wc.epoch !== lastSec; lastSec = wc.epoch;
    var n = KEYS.length, A = auraPhase(n), i, j, si;
    var lampV = [], wakeV = [];
    for (i = 0; i < n; i++) { lampV.push(lampAt(i, A.ph, n)); wakeV.push(A.calm ? 0 : wakeAt(i, A.ph, n)); }
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
      if (c.clock && (secChanged || !c.clock.textContent)) c.clock.textContent = fmtTime(wc);
      if (svg.classList) svg.classList.toggle('tick', !A.calm && wc.frac < 0.18);
    }
    clockRaf = requestAnimationFrame(tickClocks);
  }
  function ensureClock() { if (!clockRaf && typeof requestAnimationFrame === 'function') { clockIdle = 0; clockRaf = requestAnimationFrame(tickClocks); } }
  // ---- v26.0 · 禁忌铭文：12 笔无名笔画在 10×10 框里，配 24 个方位与两种镜像 → 读起来是一门看不懂的文字，
  var RUNE_STROKES = [
    'M2,1H8M5,1V9M2,9H8', 'M2,9L5,1L8,9M3.4,6H6.6', 'M2,1V9M2,5H7M7,2V8', 'M5,1V9M2,3H8M3,7H7',
    'M2,2L8,8M8,2L2,8M5,1V9', 'M2,1L8,5L2,9M4,5H8', 'M2,5A3,3 0 1 1 8,5M5,5V9', 'M3,1V9H8M3,5L7,3',
    'M2,3H8M5,3V9M3,6H7', 'M2,9H8L5,1Z', 'M2,2H8V8M2,5H6', 'M5,1L2,5L5,9L8,5Z'
  ];

  var STARS_NEAR = [[6, 9, .55, .85, 0], [22, 4, .35, .5, 1], [40, 14, .75, .95, 0], [58, 7, .4, .6, 0], [13, 30, .45, .55, 1], [34, 38, .95, 1, 0], [50, 27, .35, .5, 0], [66, 40, .55, .7, 1], [8, 52, .6, .75, 0], [27, 60, .4, .5, 0], [46, 55, .5, .65, 1], [62, 66, .35, .45, 0], [19, 45, .3, .4, 0], [70, 20, .45, .6, 0]];
  var TENDRILS = [
    [-2.10, -1.30, -1.18, -0.44, -1.72, -0.22], [2.14, -1.05, 1.22, -0.52, 1.78, 0.08],
    [-2.05, 1.38, -1.14, 0.56, -1.68, 0.48], [2.10, 1.46, 1.18, 0.64, 1.74, 0.58],
    [-0.46, -2.02, -0.30, -1.22, -1.16, -1.66], [0.54, 2.08, 0.32, 1.26, 1.24, 1.70]
  ];
  var TENDRILS_DEEP = [
    [-2.25, -0.70, -1.25, -0.22, -1.85, 0.05], [2.20, -0.65, 1.30, -0.18, 1.90, -0.10],
    [-2.15, 0.85, -1.20, 0.32, -1.80, 0.25], [2.22, 0.90, 1.25, 0.38, 1.85, 0.30],
    [-1.20, -2.15, -0.65, -1.30, -1.45, -1.50], [1.25, -2.10, 0.70, -1.28, 1.50, -1.45],
    [-1.25, 2.15, -0.68, 1.32, -1.48, 1.52], [1.18, 2.20, 0.65, 1.35, 1.42, 1.58],
    [-0.10, -2.30, -0.05, -1.35, -0.50, -1.80], [0.12, 2.32, 0.08, 1.38, 0.55, 1.82]
  ];
  var STARS_FAR = [[9, 14, .3, .55], [37, 6, .25, .4], [61, 22, .35, .6], [84, 11, .25, .45], [18, 48, .3, .5], [52, 40, .25, .4], [73, 58, .3, .55], [30, 78, .25, .45], [90, 84, .3, .5], [5, 90, .25, .4]];

  function render(attrs, opt) {
    opt = opt || {};
    if (allPending(attrs)) return pendingHTML();
    var parsedSize = Number(opt.size);
    var size = isFinite(parsedSize) && parsedSize > 0 ? parsedSize : 320;
    var cx = size / 2, cy = size / 2 + 4, R = size * 0.285, n = KEYS.length;
    var parsedDepth = Number(opt.depth);
    var depth = isFinite(parsedDepth) && parsedDepth > 0 ? parsedDepth : Math.max(10, size * 0.055);
    var squash = 0.9;
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
    function spin(dur, reverse) {
      return quiet ? '' : '<animateTransform attributeName="transform" type="rotate" from="' + (reverse ? 360 : 0) + ' ' + cx + ' ' + cy + '" to="' + (reverse ? 0 : 360) + ' ' + cx + ' ' + cy + '" dur="' + dur + 's" repeatCount="indefinite"/>';
    }
    var Rs = R * 1.04;
    var PAD = Math.round(size * 0.175), VB_X = -PAD, VB_W = size + PAD * 2;
    var VB_MARGIN = 8;
    var railTop = cy - R * 1.62 - 2.5;
    var FOOT_GAP = 36;
    var GAUGE_R = 14;
    var TIDE_SWING = 2.2 * n;
    var contentTop = cy - (R + 44) * squash - CHIP_H / 2;
    var footBase = size - 12;
    var contentBottom = Math.max(
      footBase + FOOT_GAP + GAUGE_R + 2,
      footBase + FOOT_GAP + 14 + TIDE_SWING,
      cy + R * 1.62 + 2.5
    );
    var VB_Y = Math.round(Math.min(contentTop, railTop)) - VB_MARGIN;
    var VB_H = Math.round(contentBottom - VB_Y) + VB_MARGIN * 0.5;
    var values = KEYS.map(function (k) { return scoreOf(get(attrs, k)); });
    var scored = values.filter(function (s) { return s != null; }).length;
    var sum = values.reduce(function (t, s) { return t + (s == null ? 0 : s); }, 0);
    var avg = Math.round(sum / scored);
    var complete = scored === n;
    var ready = 0;
    KEYS.forEach(function (k) { var ca = get(attrs, k); if (!isPending(ca) && ca.evidence && ca.evidence.length) ready++; });
    var outer = KEYS.map(function (_, i) { return pt(i, R); });
    var outerDepth = shift(outer, skew, depth);
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
      '<linearGradient id="' + uid + 'bgv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a1036" stop-opacity=".72"/><stop offset=".55" stop-color="#090614" stop-opacity=".42"/><stop offset="1" stop-color="#2a170c" stop-opacity=".46"/></linearGradient>',
      '<radialGradient id="' + uid + 'nebA" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#6a4fd6" stop-opacity=".34"/><stop offset=".45" stop-color="#4a2f9a" stop-opacity=".14"/><stop offset="1" stop-color="#1a1036" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'nebB" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#c84dff" stop-opacity=".16"/><stop offset=".5" stop-color="#7a2a70" stop-opacity=".08"/><stop offset="1" stop-color="#2a170c" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'nebC" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#3fd6a8" stop-opacity=".10"/><stop offset="1" stop-color="#3fd6a8" stop-opacity="0"/></radialGradient>',
      '<radialGradient id="' + uid + 'fadeG" cx="50%" cy="46%" r="62%"><stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset=".62" stop-color="#fff" stop-opacity=".7"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>',
      '<mask id="' + uid + 'fade"><rect x="' + VB_X + '" y="' + VB_Y + '" width="' + VB_W + '" height="' + VB_H + '" fill="url(#' + uid + 'fadeG)"/></mask>',
      '<pattern id="' + uid + 'stN" patternUnits="userSpaceOnUse" width="72" height="72">' + STARS_NEAR.map(function (s) { return '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="' + s[2] + '" opacity="' + s[3] + '" fill="' + (s[4] ? '#ffe4c2' : '#efe9ff') + '"/>'; }).join('') + '</pattern>',
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
    if (typeof window !== 'undefined' && window.CLRadarHoloFrame && window.CLRadarHoloFrame.renderFrameSVG) {
      out.push(window.CLRadarHoloFrame.renderFrameSVG(cx, cy, R, { uid: uid, idPrefix: uid, size: size, depth: depth }));
    }
    var rt = round(R * .72), rt2 = round(R * .49), arm = round(R * .18);
    out.push('<g class="rd-reticle" aria-hidden="true">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + rt + '"/>' +
      '<circle class="inner" cx="' + cx + '" cy="' + cy + '" r="' + rt2 + '"/>' +
      line(round(cx - arm), cy, round(cx + arm), cy, 'arm') +
      line(cx, round(cy - arm), cx, round(cy + arm), 'arm') +
      '<path class="bracket" d="M' + round(cx - rt - 5) + ',' + round(cy - 10) + 'v-8h8 M' + round(cx + rt + 5) + ',' + round(cy - 10) + 'v-8h-8 M' + round(cx - rt - 5) + ',' + round(cy + 10) + 'v8h8 M' + round(cx + rt + 5) + ',' + round(cy + 10) + 'v8h-8"/>' +
      '</g>');
    out.push('<ellipse class="rd-halo" cx="' + cx + '" cy="' + (cy + depth * .18) + '" rx="' + (R * 1.55) + '" ry="' + (R * .94) + '" fill="url(#' + uid + 'bg)"/>');
    out.push('<ellipse class="rd-floor-shadow" cx="' + (cx + skew * .7) + '" cy="' + (cy + depth * .78) + '" rx="' + (R * 1.13) + '" ry="' + (R * .27) + '"/>');
    out.push('<g class="rd-platform" filter="url(#' + uid + 'shadow)"><polygon class="rd-platform-depth" points="' + ps(outerDepth) + '" fill="url(#' + uid + 'd)"/><polygon class="rd-platform-top" points="' + ps(outer) + '"/></g>');
    out.push('<polygon class="rd-platform-scan" points="' + ps(outer) + '" fill="url(#' + uid + 'hl)"/>');
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
    out.push('<polygon class="rd-grid-scan" points="' + ps(KEYS.map(function (_, i) { return pt(i, R * 0.75); })) + '"/>');
    for (var i = 0; i < n; i++) {
      var axis = pt(i, R), axisDepth = shift([axis], skew, depth * .62)[0];
      out.push(line(cx + skew, cy + depth * .62, axisDepth[0], axisDepth[1], 'rd-axis-depth'));
      out.push(line(cx, cy, axis[0], axis[1], 'rd-axis' + (i === topI ? ' peak' : ''), ' data-axis="' + KEYS[i] + '" data-lamp-i="' + i + '"'));
      out.push('<circle class="rd-axis-node" cx="' + axis[0] + '" cy="' + axis[1] + '" r="2.2" data-lamp-i="' + i + '"/>');
      var wa = Math.PI / 34, ca0 = -Math.PI / 2 + i * (2 * Math.PI / n);
      var cone = [[cx, cy], [round(cx + Math.cos(ca0 - wa) * R * 1.16), round(cy + Math.sin(ca0 - wa) * R * 1.16 * squash)], [round(cx + Math.cos(ca0 + wa) * R * 1.16), round(cy + Math.sin(ca0 + wa) * R * 1.16 * squash)]];
      out.push('<polygon class="rd-lamp-cone" data-lamp-i="' + i + '" fill="url(#' + uid + 'cone)" points="' + ps(cone) + '"/>');
    }
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
    out.push('<circle class="rd-scan-ring" cx="' + cx + '" cy="' + cy + '" r="' + round(Rs) + '" pathLength="240"/>');
    function handEl(cls, len, tail, w, deg, extra) {
      return '<g class="rd-hand ' + cls + '" transform="rotate(' + deg.toFixed(2) + ' ' + cx + ' ' + cy + ')">' + (extra || '') +
        '<line class="rd-hand-shadow" x1="' + cx + '" y1="' + round(cy + tail) + '" x2="' + cx + '" y2="' + round(cy - len) + '" stroke-width="' + (w * 2.6) + '"/>' +
        '<line class="rd-hand-line" x1="' + cx + '" y1="' + round(cy + tail) + '" x2="' + cx + '" y2="' + round(cy - len) + '" stroke-width="' + w + '"/>' +
        '<circle class="rd-hand-tip" cx="' + cx + '" cy="' + round(cy - len) + '" r="' + (w * 1.1 + 0.6) + '"/></g>';
    }
    var swA = -26 * Math.PI / 180, swR = Rs + 1;
    var sweep = '<path class="rd-sweep" fill="url(#' + uid + 'sw)" d="M' + cx + ',' + cy + ' L' + round(cx + Math.sin(swA) * swR) + ',' + round(cy - Math.cos(swA) * swR) + ' A' + round(swR) + ',' + round(swR) + ' 0 0 1 ' + cx + ',' + round(cy - swR) + ' Z"/>';
    out.push('<g class="rd-hands" data-cx="' + cx + '" data-cy="' + cy + '" role="img" aria-label="本机时间 ' + fmtTime(wc) + '">' +
      handEl('hour', R * 0.58, 8, 2.6, ang.h) +
      handEl('minute', R * 0.92, 11, 1.5, ang.m) +
      handEl('second', Rs + 3, 14, 0.85, ang.s, sweep) + '</g>');
    out.push('<g class="rd-data">');
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
      for (i = 0; i < n; i++) {
        var next = (i + 1) % n;
        if (pts[i] && pts[next]) out.push(line(pts[i][0], pts[i][1], pts[next][0], pts[next][1], 'rd-shape-open', ' stroke="url(#' + uid + 's)" stroke-width="1.5" fill="none"'));
      }
    }
    if (complete) for (i = 0; i < n; i++) {
      out.push('<line class="rd-crystal-ridge" x1="' + cx + '" y1="' + cy + '" x2="' + pts[i][0] + '" y2="' + pts[i][1] + '"/>');
    }
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
    for (i = 0; i < n; i++) {
      if (values[i] == null) continue;
      var bv = pts[i], bh = 5 + 24 * values[i] / 100, blow = isLow(get(attrs, KEYS[i]));
      out.push('<polygon class="rd-beacon' + (blow ? ' low' : '') + '" data-lamp-i="' + i + '" points="' + round(bv[0] - 1.3) + ',' + bv[1] + ' ' + round(bv[0] + 1.3) + ',' + bv[1] + ' ' + bv[0] + ',' + round(bv[1] - bh) + '" style="animation-delay:' + (0.5 + i * 0.06) + 's,' + (1 + i * 0.13) + 's"/>');
    }
    out.push('</g>');
    for (i = 0; i < n; i++) {
      var a = get(attrs, KEYS[i]), score = scoreOf(a), pend = score == null, low = isLow(a), sc = pend ? null : Math.round(score), tier = pend ? 'pend' : tierOf(sc, low), vp = pts[i] || pt(i, R);
      var vertical = i === 0 || i === 4, side = i === 2 || i === 6;
      var lp = pt(i, R + (vertical ? 44 : side ? 20 : 30)), leader = pt(i, R + 12);
      var anchor = Math.abs(lp[0] - cx) < 6 ? 'middle' : (lp[0] > cx ? 'start' : 'end');
      var evidenceCount = (a.evidence && a.evidence.length) || 0;
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
    var fy = size - 12, lx = VB_X + 14, rx = VB_X + VB_W - 14;
    var gy = fy + FOOT_GAP, gx = lx + 16, gr = GAUGE_R;
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

  function miniHTML(attrs) {
    return '<div class="rd-mini">' + KEYS.map(function (k) {
      var a = get(attrs, k), s0 = scoreOf(a), pend = s0 == null, s = pend ? 0 : s0;
      return '<span class="mb' + (isLow(a) ? ' low' : '') + (pend ? ' pend' : '') + '" title="' + k + ' ' + (pend ? '待建档' : Math.round(s)) + '"><i style="height:' + (pend ? 4 : Math.max(6, s)) + '%"></i><em>' + k[0] + '</em></span>';
    }).join('') + '</div>';
  }
  function topOf(attrs) {
    var best = null;
    KEYS.forEach(function (k) { var a = get(attrs, k), s = scoreOf(a); if (s == null) return; if (!best || s > best.score) best = { k: k, score: s }; });
    return best;
  }

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
