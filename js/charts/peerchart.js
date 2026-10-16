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
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' };

  var COL = {
    focus: '#ffb45c', star: '#c9b8ff', kin: '#3fd6a8', anti: '#ff4a62',
    ink: '#f7f2e9', ink2: '#c7c0d1', ink3: '#88819d', grid: 'rgba(170,150,232,.16)', grid2: 'rgba(170,150,232,.30)'
  };

  var W = 272, H = 236, CX = 136, CY = 118, R = 84, LAB = R + 9;
  var SIZE_LO = 2.0, SIZE_HI = 7.0;

  var CALM = false;
  try { CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e0) {}

  // ---------------------------------------------------------------- 小工具
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function f1(v) { return (Math.round(v * 10) / 10).toFixed(1); }
  function axisAngle(i) { return Math.PI + Math.PI / 8 + i * Math.PI / 4; }
  function ux(i) { return Math.sin(axisAngle(i)); }
  function uy(i) { return Math.cos(axisAngle(i)); }

  // ---------------------------------------------------------------- 状态
  var LAY = null;
  var FOCUS = null;
  var wrap = null, svg = null, tipEl = null, footEl = null, pendEl = null;
  var panelEl = null, stateEl = null;
  var GRAPH = null;
  var SRC_FALLBACK = false;
  var mounted = false, opened = false;
  var recalcs = 0;

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
  function builtOf(a) {
    return peerScoreOf(a) != null;
  }

  function compute(g) {
    recalcs++;
    var chars = (g && g.characters) || [];
    var items = [], pending = 0, i, c;
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
      if (!built.length) { pending++; continue; }
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
    if (FOCUS) FOCUS = byName[FOCUS.name];
  }

  function dominantDim(v, built) {
    var best = -1, bk = -1, j;
    for (j = 0; j < built.length; j++) {
      if (v[built[j]] > best) { best = v[built[j]]; bk = built[j]; }
    }
    return bk >= 0 ? KEYS[bk] : '';
  }

  function dist(a, b) {
    var s = 0, n = 0, k;
    for (k = 0; k < 8; k++) {
      if (a.v[k] == null || b.v[k] == null) continue;
      var d = a.v[k] - b.v[k]; s += d * d; n++;
    }
    return n ? Math.sqrt(s) : Infinity;
  }

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

  function starSize(mean) {
    return SIZE_LO + (SIZE_HI - SIZE_LO) * clamp((mean - 0.2) / 0.7, 0, 1);
  }
  function starOpacity(mean) {
    return 0.32 + 0.58 * clamp((mean - 0.2) / 0.7, 0, 1);
  }
  function sxOf(it) { var r = it.rn * R; return CX + it.nx * r; }
  function syOf(it) { var r = it.rn * R; return CY - it.ny * r; }
  function n6(v) { return +v.toFixed(6); }

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
    var hold = (state === 'loading' || state === 'empty');
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
    var fr = [0.28, 0.55, 0.8, 1];
    for (i = 0; i < fr.length; i++) {
      o.push('<circle class="' + (i === fr.length - 1 ? 'pf-ring-outer' : 'pf-ring') + '" cx="' + CX + '" cy="' + CY + '" r="' + (fr[i] * R).toFixed(1) + '"/>');
    }
    o.push('<text class="pf-p95" x="' + (CX - R + 3) + '" y="' + (CY + 13) + '">P95</text>');
    for (k = 0; k < 8; k++) {
      var s = ux(k), c = uy(k);
      o.push('<line class="pf-spoke" x1="' + CX + '" y1="' + CY + '" x2="' + (CX + s * R).toFixed(1) + '" y2="' + (CY - c * R).toFixed(1) + '"/>');
      var lx = CX + s * LAB, ly = CY - c * LAB;
      var anch = s > 0.3 ? 'start' : (s < -0.3 ? 'end' : 'middle');
      var dy = c > 0.3 ? -3 : (c < -0.3 ? 9 : 2);
      o.push('<text class="pf-zh" x="' + lx.toFixed(1) + '" y="' + (ly + dy).toFixed(1) + '" text-anchor="' + anch + '">' + esc(KEYS[k]) + '</text>');
      o.push('<text class="pf-en" x="' + lx.toFixed(1) + '" y="' + (ly + dy + (c > 0.3 ? -10 : 9)).toFixed(1) + '" text-anchor="' + anch + '">' + EN[KEYS[k]] + '</text>');
    }
    o.push('<circle class="pf-core" cx="' + CX + '" cy="' + CY + '" r="1.4"/>');
    o.push('</g>');

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

    o.push('<g class="pf-stars">');
    for (i = 0; i < LAY.items.length; i++) {
      it = LAY.items[i];
      if (it === FOCUS) continue;
      o.push('<circle class="pf-dot' + (it.clip ? ' pf-clip' : '') + '" data-nm="' + esc(it.name) + '" cx="' + n6(sxOf(it)) + '" cy="' + n6(syOf(it)) +
        '" r="' + starSize(it.mean).toFixed(2) + '" fill="' + COL.star + '" fill-opacity="' + starOpacity(it.mean).toFixed(3) + '"/>');
    }
    o.push('</g>');

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
    if (!LAY) setState('loading'); else draw();
  }

  function apply() {
    if (!wrap) return;
    wrap.classList.toggle('on', opened);
  }

  var API = {
    name: 'peer-field',
    mount: mount,
    setGraph: function (g) {
      GRAPH = g || null;
      if (!GRAPH) { LAY = { items: [], rmax: 0, byName: {}, pending: 0, total: 0 }; FOCUS = null; SRC_FALLBACK = false; draw(); return; }
      compute(GRAPH); draw();
    },
    setFocus: function (name) {
      if (!LAY) return;
      var it = name ? LAY.byName[name] : null;
      FOCUS = it || null;
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
    stats: function () {
      var ps = FOCUS ? peers(FOCUS) : { kin: [], anti: null };
      return {
        ok: !!(mounted && LAY),
        chars: LAY ? LAY.items.length : 0,
        plotted: LAY ? LAY.items.length : 0,
        pending: LAY ? (LAY.total - LAY.items.length) : 0,
        focus: FOCUS ? FOCUS.name : '',
        focusR: FOCUS ? +FOCUS.rn.toFixed(4) : 0,
        rmax: LAY ? LAY.rmax : 0,
        kin: ps.kin.map(function (x) { return { name: x.name, d: +x.d.toFixed(4) }; }),
        anti: ps.anti ? { name: ps.anti.name, d: +ps.anti.d.toFixed(4) } : { name: '', d: 0 },
        dominant: FOCUS ? FOCUS.dom : '',
        clipped: LAY ? LAY.items.reduce(function (n, it) { return n + (it.clip ? 1 : 0); }, 0) : 0,
        recalcs: recalcs,
        open: opened, calm: CALM
      };
    },
    build: function (o) { API.setGraph(o && o.graph); },
    scoreOf: peerScoreOf
  };

  if (window.CLArcana && CLArcana.register) CLArcana.register(API);
  window.CLPeer = API;

  if (typeof window !== 'undefined' && window.CLAttrSource && typeof window.CLAttrSource.subscribe === 'function') {
    window.CLAttrSource.subscribe(function () { if (mounted && GRAPH) { compute(GRAPH); draw(); } });
  }
})();
