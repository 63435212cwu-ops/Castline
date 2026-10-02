/* @role component · @owns js/orbit3d-ruler.js · @budget dom_nodes=5 js_ms=0.1 · @contract v47+v48+v70
 * R3-B（主控本轮追加、临时接管）：窄屏（<=600px）下固定 190px 宽的 `.cl-o3-ruler__hd`
 * 文字表头（「章回 · N 回 · M 事件」）容不下整行，会被浏览器逐字折成一列竖排贴在左边缘
 * （主控复审截图 outputs/v70/r3/shell-plot-390x844.png 指出，疑似命中 canvas#gl 是因为
 * elementFromPoint 在该像素点先撞上更上层的 3D 画布，不代表文字画在画布纹理里——文字仍是
 * 这个文件建的真实 DOM 节点，只是窄屏溢出）。css/shell-chrome.css 已有一条同选择器的
 * `@media (max-width:600px){.cl-o3-ruler__hd{display:none}}`（R3-A 加），但那是另一个
 * 单元的文件、加载顺序不受本文件控制；这里在本体侧再补一道同效果的兜底：rebuild()/tick()
 * 里按 g.innerWidth 直接切 `.is-hidden`（app-shell.css 既有状态类，非本文件新造），双保险
 * 不冲突（两条规则都只会把 display 判成 none，不会出现「谁赢」的争用）。只隐藏文字表头，
 * 画刻度的 canvas 与悬停提示不动——「只留刻度」。
 *
 * R5-D（本轮，docs/atlas/REVIEW-2026-09-20.md §八 #8「圆盘左列 30 行章×线矩阵无标注」）：
 * 1) 表头避让 #index：1440 桌面态默认 `--cl-o3r-top:330px` 落在 #index（CAST INDEX，
 *    `top:calc(--gap+186px)` 到 `bottom:calc(--gap+52px)`，实测约 y204–830）区间内，被
 *    面板盖住。这里每次 tick() 现读两者 getBoundingClientRect() 判交叠，交叠时把
 *    `root.style.top` 改写成 `#index` 面板底 +12px（纯坐标数值，不新增颜色/字体内联样式，
 *    符合契约「只允许坐标/进度动态数值」）；不交叠时清空内联 top，退回 CSS 变量默认值——
 *    不改 #index 本身，不碰 css/app-shell.css。
 * 2) 矩阵列语义：原来每行只有一个序号，看不出这一格对应哪条线、多少事件。改法不新建
 *    DOM/CSS（矩阵本体是 <canvas>，不是 U08 report 里另一处误认的 WebGL `#gl`）——延用文件
 *    既有 `cssTok()` 读令牌的取色方式，在画布顶部多画一行「主线色标」（每条 kind==='main'
 *    的线一个 6px 色点 + 2 字缩写，≤5 条，超出显示「+N」，色值取 --cl-atlas-gen-0..5，循环
 *    复用、不发明新颜色）；悬停任一事件色块时，找最近的 mark，换算「第N章 · 线名 · M 事」，
 *    交给全局 `window.CLTooltip`（js/hud/tooltip.js）显示——不再自建 `.cl-o3-ruler__tip`
 *    DOM（该文件被移除，css/orbit3d.css 里的同名旧规则变成死选择器，不属于本单元文件，
 *    不清理，无害）。线名/线所属通过 `CLPlotOrbitView.eventAt(ev).lineIds` +
 *    `CLPlotOrbitView.threadAt(id)`（该 view 本文件一直只读依赖，未新增依赖面）取得。
 *
 * v90 F2（briefs/v90/PLAN.md A3「左侧常驻章回矩阵表」）：三图工作区（body.atlas-workspace）里
 * 矩阵默认所有宽度都收成左缘竖签（复用年轮账本 ≤900 竖签形态：--cl-ann-ledger-tab-w/h 44×160、
 * 原生 <button> + aria-expanded/aria-controls/aria-label、Enter/Space、Esc 收回并把焦点还给竖签，
 * 按键在 window 捕获阶段先于 keys.js 接管）。点竖签滑出矩阵，再点或 Esc 收回；用户选择存
 * sessionStorage（本会话记住）。展开宽度按年轮盘真实投影现算，遮挡盘面 ≤ 1/4 盘宽；竖签/矩阵
 * 纵向落在 HUD 与底部时间轴之间的安全带里（每次尺寸变化现读，不写死坐标）。
 * 工作区之外（经典星盘）保持原 190px 常驻矩阵原样。
 */
(function (g) {
  'use strict';

  var NAME = 'orbit3d-ruler';
  var VERSION = '90';
  var ROW = 11;
  var W = 190;               /* v90：可变——竖签展开态按盘面 1/4 规则收窄 */
  var W_FULL = 190;
  var W_MIN = 84;             /* v90：竖屏放大取景后盘几乎贴满视口宽，1/4 盘宽规则下展开面板最窄到 84px（序号列 24 + 刻轨 54） */
  var MAXROWS = 36;
  var TRACK_X = 44;
  var TRACK_W = 140;
  var DOCK_KEY = 'cl.o3ruler.open';   /* v90：sessionStorage 键，'1' = 用户选择展开 */
  var DOCK_GAP = 12;                  /* v90：竖签与 HUD 底的间距 */
  var HD_NARROW_MAX = 600;   /* R3-B：文字表头窄屏隐藏阈值，与 shell-chrome.css 的 600px 一致 */
  var LEG_ROW = 13;          /* R5-D：顶部主线色标行高 */
  var MAX_LEGEND = 5;        /* R5-D：色标最多显示 5 条主线，超出收进 +N */
  var DOT_R = 3;             /* R5-D：色标圆点半径（直径 6px，任务书原话） */
  var INDEX_GAP = 12;        /* R5-D：与 #index 面板底的避让间距 */

  var root = null, hdEl = null, cv = null, ctx = null;
  var rows = [], listRef = [], maxN = 1;
  var legend = [], legendExtra = 0, legendShown = 0;
  var ready = false, built = false, subs = false;
  var hover = -1, hoverMark = null, focusRow = -1, redraws = 0, cursor = 0;
  var dpr = 1, lastSig = '', tk = null, avoidTop = '';
  /* v90 竖签：tabEl 竖签按钮 · tabN 展开态计数 · panelEl 矩阵面板 · dockOn 工作区竖签态 · dockOpen 展开 */
  var tabEl = null, tabN = null, panelEl = null, dockOn = false, dockOpen = false, dockInit = false;
  var dockTicks = 0, dockSize = '', dockTop = null, dockMaxH = null, dockToggles = 0;

  function setWidth(w) {
    w = Math.round(w);
    if (!(w > 0) || w === W) return false;
    W = w;
    TRACK_X = W >= 170 ? 44 : 24;
    TRACK_W = W - TRACK_X - 6;
    return true;
  }

  function store(v) { try { if (g.sessionStorage) g.sessionStorage.setItem(DOCK_KEY, v ? '1' : '0'); } catch (e) {} }
  function stored() { try { return !!(g.sessionStorage && g.sessionStorage.getItem(DOCK_KEY) === '1'); } catch (e) { return false; } }
  function workspace() { var b = document.body; return !!(b && b.classList && b.classList.contains('atlas-workspace')); }

  /* v90：HUD 与底部时间轴之间的安全带（与 annulus-labels 同一口径，优先复用其导出）。 */
  function safeBand() {
    var LB = g.CLAnnulusLabels;
    if (LB && typeof LB.safeBand === 'function') { try { var sb = LB.safeBand(); if (sb) return sb; } catch (e) {} }
    var H = g.innerHeight || 800, top = 0, bottom = H, hud = document.getElementById('atlasPreviewHUD');
    if (hud && hud.classList.contains('on')) {
      var kids = hud.querySelectorAll('.aph-shell > *'), i, r;
      for (i = 0; i < kids.length; i++) {
        r = kids[i].getBoundingClientRect();
        if (!(r.height > 0) || !(r.width > 0)) continue;
        if (r.bottom <= H * 0.5) top = Math.max(top, r.bottom);
        else if (r.top >= H * 0.5) bottom = Math.min(bottom, r.top);
      }
    }
    return { top: top, bottom: bottom, left: 0, right: g.innerWidth || 1200 };
  }

  /* v90：年轮盘在屏上的真实外接盒（CLAnnulusSVG 插件投影，盘缘 1.0R 采 32 点）；未挂年轮返回 null */
  function discBox() {
    var S = g.CLAnnulusSVG, c = null;
    try { c = S && S.ctx ? S.ctx() : null; } catch (e) { c = null; }
    if (!c || !c.A || !(c.A.R > 0) || typeof c.project !== 'function') return null;
    var l = Infinity, r = -Infinity, t = Infinity, b = -Infinity, i, p;
    for (i = 0; i < 32; i++) {
      p = c.project(c.A.R, i / 32 * Math.PI * 2);
      if (!p) continue;
      if (p[0] < l) l = p[0]; if (p[0] > r) r = p[0]; if (p[1] < t) t = p[1]; if (p[1] > b) b = p[1];
    }
    return (r > l) ? { left: l, right: r, top: t, bottom: b, width: r - l } : null;
  }

  function cssTok(name) {
    try {
      var v = g.getComputedStyle(document.documentElement).getPropertyValue(name);
      return v ? v.replace(/^\s+|\s+$/g, '') : '';
    } catch (e) { return ''; }
  }

  function tokens() {
    if (tk) return tk;
    tk = {
      ink3: cssTok('--ink-3'),
      line: cssTok('--line'),
      warm: cssTok('--warm'),
      signal: cssTok('--signal'),
      glass2: cssTok('--glass-2'),
      mono: cssTok('--mono')
    };
    return tk;
  }

  /* R5-D：主线代次色，契约令牌 --cl-atlas-gen-0..5（金/琥珀/玫瑰金/紫罗兰/靛/薄荷），
   * 第 6 条主线起循环复用，不发明新颜色。 */
  function genColor(i) {
    var v = cssTok('--cl-atlas-gen-' + (((i % 6) + 6) % 6));
    return v || cssTok('--signal');
  }

  function hexOf(kind) {
    var P = g.CLPalette;
    if (P && P.hex) {
      var n = P.hex(kind, 0) >>> 0;
      return '#' + ('000000' + n.toString(16)).slice(-6);
    }
    return '';
  }

  function isReduced() {
    return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function lowTier() {
    var L = g.CLOrbit3DLayer;
    if (!L || !L.stats) return false;
    var s;
    try { s = L.stats(); } catch (e) { return false; }
    return !!(s && s.tier === 2);
  }

  function motionPos() {
    if (isReduced()) return 1;
    if (lowTier()) return cursor;
    var V = g.CLPlotOrbitView;
    if (!V || !V.motion) return cursor;
    var ms;
    try { var mc = V.motion(); ms = mc && mc.state ? mc.state() : null; } catch (e) { return cursor; }
    if (!ms) return cursor;
    var len = ms.orderLen || 1;
    var pos = (ms.pulse && typeof ms.pulse.i === 'number') ? ms.pulse.i / len : 0;
    if (pos < 0) pos = 0;
    if (pos > 1) pos = 1;
    return pos;
  }

  function sig(pos, fe) {
    return [(pos * 300) | 0, fe, hover, rows.length, listRef.length, dpr].join('|');
  }

  function shortName(ci, i) {   /* 章名不在此出口（COPY §章名唯一出口=事件卡），只给序号 */
    var n = (typeof ci === 'number' && ci >= 0) ? (ci + 1) : (i + 1);
    return String(n);
  }

  function rebuild() {
    var V = g.CLPlotOrbitView;
    if (!V || !V.orderList || !V.eventAt) { ready = false; return false; }
    var list;
    try { list = V.orderList(); } catch (e) { ready = false; return false; }
    if (!list || !list.length) { ready = false; return false; }
    listRef = list;

    var groups = [], gi = -1, lastChap = null;
    var i, j, ev, e, order, ci;
    for (i = 0; i < list.length; i++) {
      ev = list[i];
      e = V.eventAt(ev);
      if (!e) continue;
      order = (e.order != null) ? e.order : (i + 1);
      ci = (e.chapIdx != null) ? e.chapIdx : Math.floor(order / 12);
      if (gi < 0 || ci !== lastChap) {
        groups.push({ ci: ci, evs: [], first: order, last: order, maxW: -1, climax: ev });
        gi++;
        lastChap = ci;
      }
      var gr = groups[gi];
      gr.evs.push(ev);
      gr.last = order;
      var w = (e.w != null) ? e.w : 0;
      if (w > gr.maxW) { gr.maxW = w; gr.climax = ev; }
    }

    if (groups.length > MAXROWS) {
      var per = Math.ceil(groups.length / MAXROWS);
      var merged = [], k;
      for (k = 0; k < groups.length; k += per) {
        var chunk = groups.slice(k, k + per);
        var m = { ci: chunk[0].ci, evs: [], first: chunk[0].first, last: chunk[chunk.length - 1].last, maxW: -1, climax: chunk[0].climax };
        var q;
        for (q = 0; q < chunk.length; q++) {
          var c = chunk[q], z;
          for (z = 0; z < c.evs.length; z++) m.evs.push(c.evs[z]);
          if (c.maxW > m.maxW) { m.maxW = c.maxW; m.climax = c.climax; }
        }
        merged.push(m);
      }
      groups = merged;
    }

    maxN = 1;
    for (i = 0; i < groups.length; i++) {
      if (groups[i].evs.length > maxN) maxN = groups[i].evs.length;
    }

    rows = [];
    for (i = 0; i < groups.length; i++) {
      var r = groups[i];
      r.idx = i;
      r.name = shortName(r.ci, i);
      r.full = '第 ' + r.name + ' 段';
      r.n = r.evs.length;
      r.marks = [];
      for (j = 0; j < r.evs.length; j++) {
        var ej = V.eventAt(r.evs[j]);
        var oj = (ej && ej.order != null) ? ej.order : (j + 1);
        r.marks.push({ ev: r.evs[j], order: oj, kind: ej ? ej.kind : '' });
      }
      rows.push(r);
    }

    buildLegend(V, list);

    ready = true;
    hover = -1;
    hoverMark = null;
    lastSig = '';
    if (hdEl) hdEl.textContent = '章回 · ' + rows.length + ' 回 · ' + listRef.length + ' 事件';
    syncTab();
    refreshHdVisibility();
    if (g.CLTooltip && g.CLTooltip.hide) { try { g.CLTooltip.hide(true); } catch (e3) {} }
    sizeCanvas();
    return true;
  }

  /* R5-D：顶部主线色标——kind==='main' 的线各一个 6px 色点 + 2 字缩写，≤MAX_LEGEND 条，
   * 超出以「+N」收（任务书原话）。线的归属/名字只读 view.eventAt(ev).lineIds 与
   * view.threadAt(id)，不新增数据依赖。 */
  function buildLegend(V, list) {
    legend = [];
    legendExtra = 0;
    if (!V || !V.eventAt || !V.threadAt || !list || !list.length) return;
    var seen = {}, mains = [], i, j;
    for (i = 0; i < list.length; i++) {
      var e = V.eventAt(list[i]);
      var lids = (e && e.lineIds) || [];
      for (j = 0; j < lids.length; j++) {
        var id = lids[j];
        var key = String(id);
        if (seen[key]) continue;
        seen[key] = 1;
        var t = V.threadAt(id);
        if (t && t.kind === 'main') mains.push({ id: id, t: t });
      }
    }
    mains.sort(function (a, b) { return (b.t.len || 0) - (a.t.len || 0); });
    legendExtra = Math.max(0, mains.length - MAX_LEGEND);
    for (i = 0; i < mains.length && i < MAX_LEGEND; i++) {
      var nm = mains[i].t.title || mains[i].t.en || ('线' + mains[i].id);
      legend.push({ id: mains[i].id, name: nm, abbr: nm.slice(0, 2), len: mains[i].t.len || 0, ci: i });
    }
  }

  /* R3-B：窄屏隐藏文字表头（本体侧兜底，见头注）；只切 class，不写内联 style。 */
  function refreshHdVisibility() {
    if (!hdEl) return;
    var narrow = (g.innerWidth || 0) > 0 && g.innerWidth <= HD_NARROW_MAX;
    hdEl.classList.toggle('is-hidden', narrow);
  }

  function legH() { return legend.length ? LEG_ROW : 0; }

  function sizeCanvas() {
    if (!cv || !ctx) return;
    dpr = Math.min(2, Math.max(1, g.devicePixelRatio || 1));
    var h = rows.length * ROW + 6 + legH();
    cv.style.width = W + 'px';
    cv.style.height = h + 'px';
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lastSig = '';
  }

  function buildDom() {
    if (built) return;
    built = true;
    root = document.createElement('div');
    root.className = 'cl-o3-ruler';
    root.setAttribute('aria-hidden', 'true');
    /* v90 竖签：原生按钮；非工作区由 CSS 隐藏（display:none，不进焦点序） */
    tabEl = document.createElement('button');
    tabEl.type = 'button';
    tabEl.className = 'cl-o3-ruler__tab';
    tabEl.setAttribute('aria-controls', 'cl-o3-ruler-panel');
    tabEl.setAttribute('aria-expanded', 'false');
    var tg = document.createElement('span');
    tg.className = 'cl-o3-ruler__tab-g';
    tg.setAttribute('aria-hidden', 'true');
    var tt = document.createElement('span');
    tt.className = 'cl-o3-ruler__tab-t';
    tt.textContent = '章回';
    tabN = document.createElement('span');
    tabN.className = 'cl-o3-ruler__tab-n';
    tabEl.appendChild(tg);
    tabEl.appendChild(tt);
    tabEl.appendChild(tabN);
    panelEl = document.createElement('div');
    panelEl.className = 'cl-o3-ruler__panel';
    panelEl.id = 'cl-o3-ruler-panel';
    hdEl = document.createElement('div');
    hdEl.className = 'cl-o3-ruler__hd';
    cv = document.createElement('canvas');
    cv.className = 'cl-o3-ruler__cv';
    cv.setAttribute('aria-hidden', 'true');
    panelEl.appendChild(hdEl);
    panelEl.appendChild(cv);
    root.appendChild(tabEl);
    root.appendChild(panelEl);
    document.body.appendChild(root);
    ctx = cv.getContext('2d');
    root.addEventListener('click', function (e) { e.stopPropagation(); });
    root.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
    /* v90：指针读数只挂在画布上（offsetX/Y 以画布为参照；点竖签不能误选行） */
    cv.addEventListener('pointermove', onMove);
    cv.addEventListener('pointerleave', onLeave);
    cv.addEventListener('click', onClick);
    tabEl.addEventListener('click', function () { if (dockOn) setDock(!dockOpen, true); });
  }

  /* v90：竖签文字/无障碍标签随数据刷新 */
  function syncTab() {
    if (!tabEl) return;
    var cnt = rows.length + ' 回 · ' + listRef.length + ' 事件';
    if (tabN) tabN.textContent = cnt;
    tabEl.setAttribute('aria-label', (dockOpen ? '收起' : '展开') + '章回矩阵 · ' + cnt);
    tabEl.title = (dockOpen ? '收起' : '展开') + '章回矩阵（Esc 收回）';
  }

  /* v90：展开/收起。fromUser 才写 sessionStorage（本会话记住用户选择） */
  function setDock(open, fromUser) {
    if (!root) return;
    dockOpen = !!open;
    root.classList.toggle('is-open', dockOn && dockOpen);
    tabEl.setAttribute('aria-expanded', String(dockOn && dockOpen));
    panelEl.hidden = dockOn && !dockOpen;
    if (fromUser) { store(dockOpen); dockToggles++; }
    if (!dockOpen && panelEl.contains(document.activeElement)) { try { tabEl.focus(); } catch (e) {} }
    if (!dockOpen && hover !== -1) onLeave();
    syncTab();
    layoutDock(true);
  }

  /* v90：进/出工作区竖签态 */
  function applyDock(on) {
    if (!root || on === dockOn) return;
    dockOn = on;
    root.classList.toggle('is-dock', on);
    if (on) {
      root.removeAttribute('aria-hidden');
      root.setAttribute('role', 'region');
      root.setAttribute('aria-label', '章回矩阵');
      if (!dockInit) { dockInit = true; dockOpen = stored(); }
      setDock(dockOpen, false);
    } else {
      root.classList.remove('is-open');
      root.setAttribute('aria-hidden', 'true');
      root.removeAttribute('role');
      root.removeAttribute('aria-label');
      tabEl.setAttribute('aria-expanded', 'false');
      panelEl.hidden = false;
      root.style.top = ''; root.style.maxHeight = ''; root.style.width = '';
      dockTop = null; dockMaxH = null; dockSize = '';
      if (setWidth(W_FULL)) sizeCanvas();
    }
  }

  /* v90：竖签/矩阵落位（仅坐标数值写内联：top/maxHeight；宽度走画布尺寸）。
   * 纵向：HUD 底 + DOCK_GAP，底边不越过时间轴；横向展开宽度：遮挡盘面 ≤ 1/4 盘宽。 */
  function layoutDock(force) {
    if (!root || !dockOn) return;
    var key = (g.innerWidth || 0) + 'x' + (g.innerHeight || 0) + '|' + (dockOpen ? 1 : 0);
    dockTicks++;
    if (!force && key === dockSize && dockTicks % 45) return;
    dockSize = key;
    var band = safeBand(), top = Math.round(band.top + DOCK_GAP), maxH = Math.max(160, Math.round(band.bottom - DOCK_GAP - top));
    if (top !== dockTop) { root.style.top = top + 'px'; dockTop = top; }
    if (maxH !== dockMaxH) { root.style.maxHeight = maxH + 'px'; dockMaxH = maxH; }
    var w = W_FULL;
    if (dockOpen) {
      var d = discBox(), left = root.getBoundingClientRect().left || 0;
      /* 面板左缘 left、自身边框/内距约 10px：右缘 ≤ 盘左缘 + 1/4 盘宽 */
      if (d) w = Math.min(W_FULL, Math.max(W_MIN, Math.floor(d.left + d.width * 0.24 - left - 11)));
      w = Math.min(w, Math.max(W_MIN, (g.innerWidth || 1200) - 16));
    }
    if (setWidth(w)) { sizeCanvas(); draw(); }
    /* 展开态根宽 = 画布逻辑宽 + 面板内距/边框（表头计数文字不得把面板撑宽） */
    var rw = dockOpen ? (W + 11) + 'px' : '';
    if (root.style.width !== rw) root.style.width = rw;
  }

  /* v90：竖签键盘——先于 keys.js（window 捕获）；只接管竖签/矩阵内的键与展开态的 Esc */
  function onKey(e) {
    if (!dockOn || !root || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target, inside = !!(t && t.nodeType === 1 && root.contains(t));
    if (e.key === 'Escape' && dockOpen && (inside || !t || t === document.body || t === document.documentElement)) {
      setDock(false, true);
      try { tabEl.focus(); } catch (e2) {}
    } else if ((e.key === 'Enter' || e.key === ' ') && t === tabEl) {
      if (!e.repeat) tabEl.click();
    } else return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }

  function rowAt(y) {
    if (!ready || !rows.length) return -1;
    var i = Math.floor((y - 3 - legH()) / ROW);
    if (i < 0 || i >= rows.length) return -1;
    return i;
  }

  function pick(y) {
    var i = rowAt(y);
    if (i < 0) return -1;
    var ev = rows[i].climax;
    var V = g.CLPlotOrbitView;
    if (V && V.focusEvent && ev >= 0) V.focusEvent(ev);
    return ev;
  }

  /* R5-D：在某一行里按 x 找最近的事件色块（marks[j]），供 tooltip 精确到「这一格」
   * 而不是整行。 */
  function markAt(i, x) {
    var r = rows[i];
    if (!r || !r.marks.length) return null;
    var best = null, bestD = Infinity, j;
    for (j = 0; j < r.marks.length; j++) {
      var mk = r.marks[j];
      var mx = TRACK_X + TRACK_W * ((mk.order - r.first) / Math.max(1, r.last - r.first + 1));
      var d = Math.abs(mx - x);
      if (d < bestD) { bestD = d; best = mk; }
    }
    return best;
  }

  /* R5-D：拼「第N章 · 线名 · M 事」——线名/M 只读 view.eventAt/threadAt，未提供就说未提供，
   * 不发明（契约 §0）。复用 window.CLTooltip（js/hud/tooltip.js），不再自建 tip DOM。 */
  function tipTextFor(rowIdx, mk) {
    var r = rows[rowIdx];
    var chapText = '第 ' + r.name + ' 段';
    var V = g.CLPlotOrbitView;
    var lineText = '线未知', mText = '事未知';
    if (V && mk) {
      var e = V.eventAt(mk.ev);
      var lids = (e && e.lineIds) || [];
      if (lids.length && V.threadAt) {
        var t = V.threadAt(lids[0]);
        if (t) {
          lineText = t.title || t.en || ('线 ' + lids[0]);
          mText = (typeof t.len === 'number') ? (t.len + ' 事') : '事未提供';
        }
      } else {
        lineText = '未归属任何线';
      }
    }
    return chapText + ' · ' + lineText + ' · ' + mText;
  }

  function showTip(rowIdx, mk, anchorEvent) {
    if (!g.CLTooltip || !g.CLTooltip.show) return;
    var anchor = anchorEvent;
    /* v90：竖签展开态面板压在年轮层之上（--z-dock）；提示改锚到面板右缘外，永不被面板自己盖住 */
    if (dockOn && root && anchorEvent && typeof anchorEvent.clientY === 'number') {
      var rr = root.getBoundingClientRect();
      anchor = { clientX: rr.right, clientY: anchorEvent.clientY };
    }
    try { g.CLTooltip.show({ type: 'legend', body: tipTextFor(rowIdx, mk), anchor: anchor }); } catch (e4) {}
  }

  function hideTip() {
    if (g.CLTooltip && g.CLTooltip.hide) { try { g.CLTooltip.hide(false); } catch (e5) {} }
  }

  function onMove(e) {
    var y = (typeof e.offsetY === 'number') ? e.offsetY : 0;
    var x = (typeof e.offsetX === 'number') ? e.offsetX : 0;
    var i = rowAt(y);
    var mk = (i >= 0) ? markAt(i, x) : null;
    if (i === hover && mk === hoverMark) return;
    hover = i;
    hoverMark = mk;
    if (i >= 0) showTip(i, mk, e); else hideTip();
    lastSig = '';
    draw();
  }

  function onLeave() {
    if (hover === -1) return;
    hover = -1;
    hoverMark = null;
    hideTip();
    lastSig = '';
    draw();
  }

  function onClick(e) {
    var y = (typeof e.offsetY === 'number') ? e.offsetY : 0;
    pick(y);
  }

  /* R5-D：顶部主线色标行——6px 色点 + 2 字缩写，超出 MAX_LEGEND 显示「+N」。 */
  function drawLegend(mono, t) {
    if (!legend.length) return;
    var x = 4, y0 = 2, i, extra = legendExtra;
    ctx.textBaseline = 'middle';
    ctx.font = (LEG_ROW - 4) + 'px ' + mono;
    legendShown = 0;
    for (i = 0; i < legend.length; i++) {
      var lg = legend[i], c = genColor(lg.ci);
      /* v90：竖签展开态可能收窄——放不下的主线色标并进 +N（守恒：显示数 + N = 主线数） */
      if (x + DOT_R * 2 + 3 + ctx.measureText(lg.abbr).width > W - 22) { extra += legend.length - i; break; }
      legendShown++;
      if (c) {
        ctx.fillStyle = c;
        ctx.beginPath();
        ctx.arc(x + DOT_R, y0 + LEG_ROW / 2 - 2, DOT_R, 0, Math.PI * 2);
        ctx.fill();
      }
      if (t.ink3) {
        ctx.fillStyle = t.ink3;
        ctx.fillText(lg.abbr, x + DOT_R * 2 + 3, y0 + LEG_ROW / 2 - 2);
      }
      x += DOT_R * 2 + 3 + ctx.measureText(lg.abbr).width + 8;
    }
    if (extra > 0 && t.ink3) {
      ctx.fillStyle = t.ink3;
      ctx.globalAlpha = 0.75;
      ctx.fillText('+' + extra, x, y0 + LEG_ROW / 2 - 2);
      ctx.globalAlpha = 1;
    }
  }

  function draw() {
    if (!ready || !ctx) return;
    redraws++;
    var t = tokens();
    var H = rows.length * ROW + 6 + legH();
    ctx.clearRect(0, 0, W, H);
    var V = g.CLPlotOrbitView, fe = -1;
    if (V && V.state) {
      try { fe = V.state().focusEv; } catch (e2) { fe = -1; }
    }
    var mono = t.mono || 'monospace';
    var i, j, y0;
    focusRow = -1;

    drawLegend(mono, t);

    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      y0 = 3 + legH() + i * ROW;
      if (i === hover && t.glass2) {
        ctx.globalAlpha = 0.6;
        ctx.fillStyle = t.glass2;
        ctx.fillRect(2, y0, W - 4, ROW);
        ctx.globalAlpha = 1;
      }
      if (t.ink3) {
        ctx.fillStyle = t.ink3;
        ctx.font = (ROW - 3) + 'px ' + mono;
        ctx.textBaseline = 'middle';
        ctx.fillText(r.name, 4, y0 + ROW / 2);
      }
      if (t.line) {
        ctx.globalAlpha = 0.26;
        ctx.fillStyle = t.line;
        ctx.fillRect(TRACK_X, y0 + 2, TRACK_W, ROW - 4);
        ctx.globalAlpha = 0.9;
        ctx.fillRect(TRACK_X, y0 + 2, TRACK_W * (r.n / maxN), ROW - 4);
        ctx.globalAlpha = 1;
      }
      for (j = 0; j < r.marks.length; j++) {
        var mk = r.marks[j];
        var mx = TRACK_X + TRACK_W * ((mk.order - r.first) / Math.max(1, r.last - r.first + 1));
        var c = hexOf(mk.kind);
        if (c) {
          var clim = (mk.ev === r.climax);
          ctx.fillStyle = c;
          ctx.globalAlpha = clim ? 1 : 0.85;
          ctx.fillRect(mx, y0 + 2, clim ? 2.5 : 1.5, ROW - 5);
          ctx.globalAlpha = 1;
        }
        if (fe >= 0 && mk.ev === fe) {
          focusRow = i;
          if (t.signal) {
            ctx.strokeStyle = t.signal;
            ctx.lineWidth = 1;
            ctx.strokeRect(mx - 1, y0 + 1, 4, ROW - 3);
          }
        }
      }
    }

    var idx = cursor * listRef.length;
    var cum = 0, ci = -1, local = 0;
    for (i = 0; i < rows.length; i++) {
      if (idx < cum + rows[i].n) { ci = i; local = idx - cum; break; }
      cum += rows[i].n;
    }
    if (ci < 0 && rows.length) { ci = rows.length - 1; local = rows[ci].n; }
    if (ci >= 0 && t.warm) {
      var cy = 3 + legH() + ci * ROW;
      ctx.fillStyle = t.warm;
      ctx.globalAlpha = 0.9;
      ctx.fillRect(TRACK_X, cy + ROW - 2, TRACK_W, 1);
      var frac = local / Math.max(1, rows[ci].n);
      if (frac < 0) frac = 0;
      if (frac > 1) frac = 1;
      var cx = TRACK_X + TRACK_W * frac;
      ctx.fillRect(cx - 1, cy + 1, 2, ROW - 2);
      ctx.globalAlpha = 1;
    }

    lastSig = sig(cursor, fe);
  }

  function onFrame() {
    if (!ready) return;
    cursor = motionPos();
    var V = g.CLPlotOrbitView, fe = -1;
    if (V && V.state) {
      try { fe = V.state().focusEv; } catch (e) { fe = -1; }
    }
    var s = sig(cursor, fe);
    if (s !== lastSig) { lastSig = s; draw(); }
  }

  function subscribe(V) {
    if (subs) return;
    subs = true;
    if (!V.on) return;
    V.on('mode', function () { rebuild(); });
    V.on('character', function () { rebuild(); });
    V.on('frame', onFrame);
  }

  /* R5-D：每 tick 现读 #index 面板矩形（HOST 面板，只读不改），与本组件默认位置矩形
   * 判交叠；交叠则把 root.style.top 改写成面板底 +INDEX_GAP（纯坐标数值），否则清空
   * 内联 top 交还给 CSS 变量默认值——不缓存死坐标，面板折叠/展开/窗口变化都跟得上。 */
  function avoidIndexPanel() {
    if (!root) return;
    var idx = document.getElementById('index');
    if (!idx) { if (avoidTop !== '') { root.style.top = ''; avoidTop = ''; } return; }
    var cs;
    try { cs = g.getComputedStyle(idx); } catch (e6) { cs = null; }
    if (!cs || cs.display === 'none' || cs.visibility === 'hidden') {
      if (avoidTop !== '') { root.style.top = ''; avoidTop = ''; }
      return;
    }
    var wantTop = avoidTop;
    root.style.top = '';    /* 先退回默认值，才能诚实量出「不避让时」是否真的交叠 */
    var r = root.getBoundingClientRect();
    var ir = idx.getBoundingClientRect();
    if (ir.width <= 0 || ir.height <= 0) return;
    var ox = Math.min(r.right, ir.right) - Math.max(r.left, ir.left);
    var oy = Math.min(r.bottom, ir.bottom) - Math.max(r.top, ir.top);
    if (ox > 0 && oy > 0) {
      wantTop = Math.round(ir.bottom + INDEX_GAP) + 'px';
      root.style.top = wantTop;
    } else {
      wantTop = '';
    }
    avoidTop = wantTop;
  }

  function tick() {
    var V = g.CLPlotOrbitView;
    if (!V || !V.orderList) return;
    var list;
    try { list = V.orderList(); } catch (e) { return; }
    if (!list || !list.length) { ready = false; return; }
    if (!built) buildDom();
    if (!ready || list.length !== listRef.length) rebuild();
    subscribe(V);
    var nd = Math.min(2, Math.max(1, g.devicePixelRatio || 1));
    if (nd !== dpr) sizeCanvas();
    refreshHdVisibility();   /* R3-B：每 tick 校一次窄屏隐藏，跟得上 resize（无需专门监听器） */
    applyDock(workspace());  /* v90：工作区 ⇄ 经典星盘切换竖签态（只比 body 类，无布局读） */
    if (dockOn) layoutDock(false);
    else avoidIndexPanel();  /* R5-D：每 tick 校一次表头/矩阵是否被 #index 盖住（竖签态由 layoutDock 落位） */
    onFrame();
  }

  function stats() {
    return {
      name: NAME,
      version: VERSION,
      ready: ready,
      rows: rows.length,
      events: listRef.length,
      cursor: Math.round(cursor * 10000) / 10000,
      hover: hover,
      focusRow: focusRow,
      redraws: redraws,
      dom: root ? root.childNodes.length : 0,
      visible: !!(root && (function () { try { var cs = g.getComputedStyle(root); return cs.display !== 'none' && parseFloat(cs.opacity) > 0.5; } catch (e) { return false; } })()),
      legend: legend.length,
      legendExtra: legendExtra,
      legRowPx: legH(),   /* R5-D：供外部判据换算「顶部色标行」在画布内的像素高度，不猜数字 */
      avoided: avoidTop !== '',
      /* v90 竖签态：on = 工作区竖签；open = 展开；width = 画布逻辑宽；legendShown = 实画色标数 */
      dock: { on: dockOn, open: dockOn && dockOpen, width: W, legendShown: legendShown, toggles: dockToggles, stored: stored() }
    };
  }

  /* v90：供 annulus-labels 把收起态竖签当作避让区（只在竖签态且收起时返回矩形） */
  function dockRect() {
    if (!root || !dockOn) return null;
    var r = root.getBoundingClientRect();
    return (r.width > 0 && r.height > 0) ? { left: r.left, top: r.top, right: r.right, bottom: r.bottom, open: dockOpen } : null;
  }
  /* 廉价签名（无布局读）：labels 用它判断是否需要重排 */
  function dockKey() { return dockOn ? ((dockOpen ? 'o' : 'c') + (dockTop == null ? '' : dockTop)) : ''; }

  if (g.CLArcana && g.CLArcana.register) {
    g.CLArcana.register({ name: NAME, update: tick });
  }
  if (g.addEventListener) g.addEventListener('keydown', onKey, true);

  g.CLOrbit3DRuler = {
    name: NAME,
    version: VERSION,
    rebuild: rebuild,
    rowAt: rowAt,
    pick: pick,
    draw: draw,
    stats: stats,
    setDock: function (open) { if (dockOn) setDock(!!open, true); return dockOn && dockOpen; },
    dockRect: dockRect,
    dockKey: dockKey
  };
})(typeof window !== 'undefined' ? window : this);
