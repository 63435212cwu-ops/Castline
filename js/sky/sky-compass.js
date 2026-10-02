/**
 * @role component
 * @owns js/sky/sky-compass.js
 * 罗盘外圈：晶体（属性八维 / 叙事八维，由 scene gemStage 画）之外的三件事——
 *  ① 关系罗盘：联系对象（≤12，余数守恒）按关系类型成扇区、自 12 点顺时针排在晶体两侧的轨道弧上；
 *     连线从晶体外缘径向出发，线型 / 颜色与星座图例同一套（CLDomainsModel.REL_CLASSES，含「同场」）；
 *     经过轴签处被挖空（地图式避让），窄屏收成晶体下方的整齐网格。点对象 → 进入对象的罗盘。
 *  ② 因果事件链：晶体下方一道浅弧，按回聚合（一回一颗珠，珠面积 ∝ 该回事件数），珠色只两级（关键 = 金，其余 = 淡紫灰）；
 *     弧上几粒暖光顺时间方向缓行（光流，24 s 一周期）；
 *     关键事件短名贪心避让（互不相压、不压关系对象与轴签），首尾标第 a 回 / 第 b 回，标题与链同宽居中。
 *  ③ 底部一枚小注（与星空图例同风格）：本罗盘出现的线型 · 数量 · 未列余数 · 缺档参考轮廓说明。
 *  关系星拖拽（sky-compass-drag）与关键事件扇出（sky-compass-fan）经 ensureSvg 里的一组钩子挂在同一张 SVG 上，本文件只把排版结果留给它们读。
 * 只读公开 API（CLApp.scene().crownScreenBounds / gemLegend）与轴签 DOM 的几何；不改场景、不改数据。
 */
(function (g) {
  'use strict';
  var doc = document;
  var MAX_SAT = 12, KEY_KINDS = /转折|高燃|抉择|冲突|高潮|揭秘/;
  var REL_ORDER = ['ally', 'kin', 'bond', 'oppose', 'dark', 'other', 'cooccur'];
  var REL_FALLBACK = { ally: '合作', kin: '亲缘', bond: '情感', oppose: '对立', dark: '暗线', other: '其他', cooccur: '同场 · 推导' };
  var svg = null, note = null, st = null, opts = null, lastKey = '', tick = 0;

  var mk = g.CLSkyUtil.svg, clamp = g.CLSkyUtil.clamp, esc = g.CLSkyUtil.esc;
  function f1(v) { return v.toFixed(1); }
  function attrs(el, o) { for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) el.setAttribute(k, typeof o[k] === 'number' ? f1(o[k]) : o[k]); }
  function show(el, on) { if (el) el.setAttribute('visibility', on ? 'visible' : 'hidden'); }
  function relLabel(id) {
    var M = g.CLDomainsModel, list = M && M.REL_CLASSES || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i].label;
    return REL_FALLBACK[id] || '联系';
  }
  function relRank(id) { var i = REL_ORDER.indexOf(id); return i < 0 ? REL_ORDER.length : i; }
  /* SVG 文本宽：画布 measureText（同一字体 + 字距）量一次缓存，文本变了才重量；字体未就绪量出 0 时按字数估。
     不用 getComputedTextLength：新建的字一量就强制整页同步布局（大书开罗盘那一下 44 ms），而画布量字不碰布局。
     字体按类名取一次计算样式（只算样式、不排版），视口宽变了重取（字号令牌随视口变） */
  var fontOf = {}, fontVw = 0, mctx = null;
  function fontFor(el) {
    var vw = g.innerWidth || 0, cls = (el.getAttribute('class') || '').split(' ')[0];   /* 字体只随基类（skc-sat-name / skc-ch …），is-* 修饰不改字 */
    if (vw !== fontVw) { fontOf = {}; fontVw = vw; }
    var f = fontOf[cls];
    if (!f) {
      var cs = g.getComputedStyle(el), ls = parseFloat(cs.letterSpacing);
      f = fontOf[cls] = { font: [cs.fontStyle, cs.fontWeight, cs.fontSize, cs.fontFamily].join(' '), ls: isFinite(ls) ? ls : 0 };
    }
    return f;
  }
  function txtW(el, px) {
    if (!el) return 0;
    var t = el.textContent || '';
    if (el._wt !== t || !(el._w > 0)) {
      var w = 0;
      try {
        if (!mctx) mctx = doc.createElement('canvas').getContext('2d');
        var f = fontFor(el); mctx.font = f.font;
        w = t ? mctx.measureText(t).width + f.ls * t.length : 0;
      } catch (e) { w = 0; }
      el._w = w > 0 ? w : t.length * (px || 12); el._wt = t;
    }
    return el._w;
  }
  function short(t, n) { t = String(t || ''); return t.length > n ? t.slice(0, n) + '…' : t; }

  function relationsOf(name, view, G) {
    var M = g.CLDomainsModel, list = [], seen = {};
    (view.relations || []).forEach(function (r) {
      if (r.a !== name && r.b !== name) return;
      var other = r.a === name ? r.b : r.a; if (!other || other === name) return;
      var cls = M && M.relClass ? M.relClass(r) : { id: 'other', label: '联系', dash: 0 };
      var key = other + '|' + cls.id; if (seen[key]) { seen[key].strength = Math.max(seen[key].strength, r.strength || 0); return; }
      var o = { name: other, kind: r.kind || cls.label, cls: cls.id, clsLabel: cls.label, dash: cls.dash || 0, strength: r.derived ? (r.n || 1) / 20 + 0.3 : (isFinite(r.strength) ? r.strength : 0.5), derived: !!r.derived, n: r.n || 0, desc: r.desc || '' };
      seen[key] = o; list.push(o);
    });
    var imp = {}; G.characters.forEach(function (c) { imp[c.name] = c.importance || 0; });
    list.sort(function (a, b) { return b.strength - a.strength || (imp[b.name] || 0) - (imp[a.name] || 0); });
    return list;
  }
  /* 因果链一律按回聚合：一回一颗珠（count = 该回事件数），关键事件作这颗珠的代表；珠数 ≤ 事件数 */
  function eventsOf(name, G, M) {
    var chIdx = {}; (M.chapters || []).forEach(function (c) { chIdx[c.name] = c.idx; });
    var out = [];
    G.events.forEach(function (e, i) { if ((e.characters || []).indexOf(name) >= 0) out.push({ i: i, e: e, c: chIdx[e.chapter] != null ? chIdx[e.chapter] : 0, key: KEY_KINDS.test(e.kind || '') }); });
    out.sort(function (a, b) { return a.c - b.c || (a.e.order || 0) - (b.e.order || 0); });
    var byC = {}, list = [];
    out.forEach(function (o) { var b = byC[o.c]; if (!b) { b = byC[o.c] = { c: o.c, items: [] }; list.push(b); } b.items.push(o); });
    return list.map(function (b) {
      var keys = b.items.filter(function (x) { return x.key; }), rep = keys[0] || b.items[0];
      var cast = []; b.items.forEach(function (x) { (x.e.characters || []).forEach(function (n) { if (cast.indexOf(n) < 0) cast.push(n); }); });
      var titles = b.items.map(function (x) { return (x.key ? '◆ ' : '') + (x.e.title || ''); }).filter(Boolean);
      return { i: rep.i, c: b.c, no: M.chapters && M.chapters[b.c] ? M.chapters[b.c].no : b.c + 1, key: keys.length > 0, keyCount: keys.length, count: b.items.length,
        list: b.items.map(function (x) { return { t: x.e.title || '', key: x.key, kind: x.e.kind || '' }; }),   /* 该回全部事件（回内次序），扇出用 */
        e: { title: rep.e.title, kind: rep.e.kind, summary: b.items.length > 1 ? titles.slice(0, 5).join(' · ') + (titles.length > 5 ? ' …' : '') : rep.e.summary, characters: cast } };
    });
  }

  function ensureSvg() {
    if (svg) return svg;
    svg = mk('svg', 'sky-compass'); svg.setAttribute('aria-label', '罗盘：关系与因果事件链');
    var defs = mk('defs', null, svg), mkr = mk('marker', null, defs);
    attrs(mkr, { id: 'skcArrow', viewBox: '0 0 8 8', refX: '6', refY: '4', markerWidth: '6', markerHeight: '6', orient: 'auto' });
    mk('path', 'skc-arrow', mkr).setAttribute('d', 'M1 1 7 4 1 7');
    /* 挖空蒙版：连线经过轴签处断开（白 = 显示，深 = 挖掉） */
    var mask = mk('mask', null, defs); attrs(mask, { id: 'skcKnock', maskUnits: 'userSpaceOnUse' });
    svg.mask = mask; svg.maskBg = mk('rect', 'skc-mask-show', mask); svg.maskHoles = mk('g', 'skc-mask-hole', mask);
    svg.gOrbit = mk('g', 'skc-orbit', svg); svg.gLinks = mk('g', 'skc-links', svg); svg.gLinks.setAttribute('mask', 'url(#skcKnock)');
    svg.gChain = mk('g', 'skc-chain', svg); svg.gChainLab = mk('g', 'skc-chain-labels', svg); svg.gSat = mk('g', 'skc-sats', svg);
    svg.card = doc.createElement('div'); svg.card.className = 'sky-card skc-card'; svg.card.hidden = true;
    note = doc.createElement('div'); note.className = 'sky-legend skc-note'; note.setAttribute('role', 'note'); note.hidden = true;
    doc.body.appendChild(svg); doc.body.appendChild(svg.card); doc.body.appendChild(note);
    svg.addEventListener('pointerover', onOver); svg.addEventListener('pointerout', onOut); svg.addEventListener('click', onClick);
    svg.addEventListener('pointermove', onBandMove); svg.addEventListener('pointerout', onBandOut);
    /* 关系星拖拽（sky-compass-drag）与事件扇出（sky-compass-fan）挂在同一张 SVG 上：只经这组钩子读排版结果、借点亮 / 字宽 / 进罗盘 */
    var hk = { state: function () { return st; }, txtW: txtW, unlight: function () { unlight(); },
      lightEvent: function (k) { if (st && st.dots[k]) lightEvent(k); }, lightSat: function (i) { if (st && st.sats[i]) lightSat(i); },
      scene: function () { return opts && opts.scene; }, pick: function (name) { if (opts && opts.onPick) opts.onPick(name); } };
    if (g.CLSkyCompassDrag) CLSkyCompassDrag.attach(svg, hk);
    if (g.CLSkyCompassFan) CLSkyCompassFan.attach(svg, hk);
    return svg;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function resetMods() { if (g.CLSkyCompassDrag) CLSkyCompassDrag.reset(); if (g.CLSkyCompassFan) CLSkyCompassFan.reset(); }   /* 换人 / 收罗盘：拖拽与扇出先落回静止 */

  function open(name, o) {
    opts = o || {}; ensureSvg(); resetMods();
    var G = opts.graph, M = opts.model, view = opts.view || G;
    if (!G || !M) return;
    var rels = relationsOf(name, view, G), evs = eventsOf(name, G, M);
    st = { name: name, rels: rels.slice(0, MAX_SAT), more: Math.max(0, rels.length - MAX_SAT), total: rels.length, evs: evs, sats: [], dots: [], hover: null, env: null, noteKey: '' };
    [svg.gOrbit, svg.gLinks, svg.gChain, svg.gChainLab, svg.gSat, svg.maskHoles].forEach(clear);
    st.arcs = [mk('path', 'skc-ring', svg.gOrbit), mk('path', 'skc-ring', svg.gOrbit)];
    var sMax = 0; st.rels.forEach(function (r) { sMax = Math.max(sMax, r.strength || 0); });
    st.rels.forEach(function (r, i) {
      var link = mk('path', 'skc-link r-' + r.cls + (r.derived ? ' is-derived' : ''), svg.gLinks);
      var gS = mk('g', 'skc-sat r-' + r.cls, svg.gSat); gS.setAttribute('data-sat', String(i)); gS.setAttribute('tabindex', '0'); gS.setAttribute('role', 'button');
      gS.setAttribute('aria-label', r.name + ' · ' + (r.derived ? '同场 ' + r.n + ' 次（推导）' : r.kind) + ' · 进入其罗盘');
      mk('circle', 'skc-sat-hit', gS).setAttribute('r', '16');
      var rr = 2.4 + 2.2 * (sMax > 0 ? clamp((r.strength || 0) / sMax, 0, 1) : 0.5);
      var dot = mk('circle', 'skc-sat-star', gS); dot.setAttribute('r', f1(rr));
      var nm = mk('text', 'skc-sat-name', gS); nm.textContent = r.name;
      var kd = mk('text', 'skc-sat-kind', gS); kd.textContent = r.derived ? '同场 ' + r.n : r.kind;
      st.sats.push({ r: r, g: gS, link: link, name: nm, kind: kd, rr: rr, shown: true });
    });
    /* 摆位次序：按关系类型成扇区（与图例同序），同类按强度——自 12 点顺时针；satellites() 仍按强度序（[0] = 最强） */
    st.ord = st.sats.map(function (s, i) { return i; }).sort(function (a, b) { return relRank(st.sats[a].r.cls) - relRank(st.sats[b].r.cls) || a - b; });
    st.chain = mk('path', 'skc-chain-line', svg.gChain);
    /* 因果链光流：同一条弧上几粒暖光顺着时间缓行（CSS 动画，pathLength = 1；减弱动效时静止） */
    st.flowG = mk('path', 'skc-flow is-glow', svg.gChain); st.flow = mk('path', 'skc-flow', svg.gChain);
    st.flowG.setAttribute('pathLength', '1'); st.flow.setAttribute('pathLength', '1');
    st.steps = [];
    var maxC = 1; evs.forEach(function (x) { maxC = Math.max(maxC, x.count || 1); }); st.maxC = maxC;
    /* 珠 / 回间箭头 / 关键短名都在排版时按需建（ensureDot / ensureLab）：大书主角几百回，原先一开罗盘就建约 2000 个节点、大半永远不上屏。
       分组定叠放次序：箭头 < 密度带 < 珠 */
    st.gSteps = mk('g', 'skc-steps', svg.gChain);
    st.bandAll = mk('path', 'skc-band', svg.gChain); st.bandKey = mk('path', 'skc-band is-key', svg.gChain); st.bandSel = mk('path', 'skc-band is-sel', svg.gChain);
    st.bandHit = mk('path', 'skc-band-hit', svg.gChain); st.bandHit.setAttribute('data-band', '1');
    st.bandCur = mk('circle', 'skc-band-cur', svg.gChain); show(st.bandCur, false);
    st.gDots = mk('g', 'skc-dots', svg.gChain);
    evs.forEach(function (x) { st.dots.push({ o: x, el: null, lab: null }); });
    st.chNo0 = mk('text', 'skc-ch is-start', svg.gChainLab); st.chNo1 = mk('text', 'skc-ch is-end', svg.gChainLab);
    if (evs.length) { st.chNo0.textContent = '第' + evs[0].no + '回'; st.chNo1.textContent = '第' + evs[evs.length - 1].no + '回'; }
    var nEv = evs.reduce(function (t, x) { return t + (x.count || 1); }, 0);
    st.nEv = nEv;
    st.rule0 = mk('path', 'skc-rule', svg.gChainLab); st.rule1 = mk('path', 'skc-rule', svg.gChainLab); st.rule1.setAttribute('marker-end', 'url(#skcArrow)');
    st.chainTitle = mk('text', 'skc-chain-title', svg.gChainLab);
    st.chainTitle.textContent = evs.length ? '因果事件链 · ' + nEv + ' 事件 · ' + evs.length + ' 回' : '因果事件链 · 暂无事件记录';
    crumbTitle(name, G);
    svg.classList.add('is-on'); note.hidden = false; lastKey = ''; tick = 0;
    /* 所有字宽在这里一次量完（一次布局）：render 里边写属性边量字宽，会让每个没量过的字都强制一次整页同步布局 */
    st.sats.forEach(function (s) { txtW(s.name, 12); txtW(s.kind, 10); });
    txtW(st.chNo0, 10); txtW(st.chNo1, 10); txtW(st.chainTitle, 10);
    /* 首次排版留给下一帧的帧钩子：此刻 body 刚换类、场景刚换态，这里读轴签框 / 计算样式会把整页样式与布局提前强制算一遍（点星那一下多 20–60 ms） */
    st.dirty = true;
  }
  function close() {
    if (!svg) return;
    resetMods();
    svg.classList.remove('is-on'); svg.card.hidden = true; if (note) { note.hidden = true; note.innerHTML = ''; }
    [svg.gOrbit, svg.gLinks, svg.gChain, svg.gChainLab, svg.gSat, svg.maskHoles].forEach(clear);
    var cr = doc.getElementById('skyCrumb'); if (cr) { cr.style.removeProperty('--skc-crumb-top'); cr.style.removeProperty('--skc-crumb-r'); }
    st = null;
  }
  /* 面包屑一句话简介：CSS 负责单行省略；悬停（title）看全文 */
  function crumbTitle(name, G) {
    var meta = doc.getElementById('skyCrumbMeta'); if (!meta) return;
    var ch = (G.characters || []).filter(function (c) { return c.name === name; })[0] || {};
    var evN = G.events.filter(function (e) { return (e.characters || []).indexOf(name) >= 0; }).length;
    meta.setAttribute('title', [ch.camp, ch.role, ch.stance, evN + ' 事件', ch.identity].filter(function (x) { return x != null && String(x).trim() !== ''; }).join(' · '));
  }

  /* ── 环境读数：轴签框 / 顶栏 / 面包屑 / 底栏 / 缺档图例（每 6 帧一次，签名变了才重排） ─────── */
  function rectOf(el) { var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? [r.left, r.top, r.right, r.bottom] : null; }
  function shown(el) { if (!el) return false; var cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden'; }
  function readEnv() {
    var labs = [], lel = [], lsig = [], u = null;
    Array.prototype.forEach.call(doc.querySelectorAll('#labels .cl-lab.attr.on, #labels .cl-lab.meta.on'), function (el) {
      if (!shown(el)) return; var b = rectOf(el); if (!b) return;
      labs.push(b); lel.push(el); lsig.push(Math.round(b[0] / 2), Math.round(b[1] / 2), Math.round(b[2] / 2));
      u = u ? [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])] : b.slice();
    });
    var tb = doc.querySelector('.sky-top'), tr = shown(tb) ? rectOf(tb) : null, hudTop = tr ? tr[3] : 56;
    var crumb = doc.getElementById('skyCrumb');
    if (crumb && !crumb.hidden) {
      var want = Math.round(hudTop + 10) + 'px', ir = Math.round((opts.inset && opts.inset.right) || 0) + 'px';
      if (crumb.style.getPropertyValue('--skc-crumb-top') !== want) crumb.style.setProperty('--skc-crumb-top', want);
      if (crumb.style.getPropertyValue('--skc-crumb-r') !== ir) crumb.style.setProperty('--skc-crumb-r', ir);
      Array.prototype.forEach.call(crumb.children, function (c) { if (!shown(c)) return; var b = rectOf(c); if (b) hudTop = Math.max(hudTop, b[3]); });
    }
    var hud = [], hudBottom = g.innerHeight;
    Array.prototype.forEach.call(doc.querySelectorAll('.sky-bottom > *:not([hidden]), .sky-lab:not([hidden])'), function (el) {
      if (!shown(el)) return; var b = rectOf(el); if (!b) return;
      hud.push(b); if (b[1] > g.innerHeight * 0.6 && b[3] - b[1] > 6) hudBottom = Math.min(hudBottom, b[1]);
    });
    var S = opts.scene, gl = false; try { gl = !!(S && S.gemLegend && S.gemLegend().on); } catch (e) { gl = false; }
    return { labs: labs, lel: lel, lu: u, hud: hud, hudTop: hudTop, hudBottom: hudBottom, gl: gl, hsig: [Math.round(hudTop), Math.round(hudBottom), gl ? 1 : 0, hud.length].join(','), lsig: lsig.join(',') };
  }
  function knockout(labs) {
    clear(svg.maskHoles);
    if (st.mode !== 'orbit') return;
    labs.forEach(function (b) { attrs(mk('rect', null, svg.maskHoles), { x: b[0] - 6, y: b[1] - 3, width: b[2] - b[0] + 12, height: b[3] - b[1] + 6, rx: 3 }); });
  }
  /* 晶体在罗盘里一直缓慢翻转，投影外框与轴签位置随之起伏（实测 ±25px）：罗盘外圈按「只增不减的包络」排版，
     包络长到位（入场飞行 + 一个翻转周期）后外圈就静止——关系对象、事件链不跟着晶体抖；只有挖空蒙版逐签跟随 */
  function grow(k, b) {
    var e = st[k]; if (!e) { st[k] = b.slice(); return true; }
    if (!(b[0] < e[0] - 3 || b[1] < e[1] - 3 || b[2] > e[2] + 3 || b[3] > e[3] + 3)) return false;
    e[0] = Math.min(e[0], b[0]); e[1] = Math.min(e[1], b[1]); e[2] = Math.max(e[2], b[2]); e[3] = Math.max(e[3], b[3]); return true;
  }
  /* 轴签随晶体翻转上下漂 ±25 px：事件短名按每枚轴签「扫过的范围」避让（只增不减）；一次跳 > 40 px 是入场飞行，换基准不累积 */
  function sweep(el, b) {
    var L = st.labSw || (st.labSw = []), e = null, i;
    for (i = 0; i < L.length; i++) if (L[i].el === el) { e = L[i]; break; }
    if (!e) { L.push({ el: el, b: b.slice() }); return false; }
    var o = e.b;
    if (b[0] > o[2] + 40 || b[2] < o[0] - 40 || b[1] > o[3] + 40 || b[3] < o[1] - 40) { e.b = b.slice(); return false; }
    if (!(b[0] < o[0] - 3 || b[1] < o[1] - 3 || b[2] > o[2] + 3 || b[3] > o[3] + 3)) return false;
    o[0] = Math.min(o[0], b[0]); o[1] = Math.min(o[1], b[1]); o[2] = Math.max(o[2], b[2]); o[3] = Math.max(o[3], b[3]); return true;
  }
  function bounds() {
    var ins = opts.inset || { right: 0, bottom: 0 }, W = g.innerWidth - (ins.right || 0), H = g.innerHeight - (ins.bottom || 0), c = st.envC;
    if (!c) return { W: W, H: H, cx: W / 2, cy: H * 0.45, cw: 240, chh: 300 };
    return { W: W, H: H, cx: (c[0] + c[2]) / 2, cy: (c[1] + c[3]) / 2, cw: c[2] - c[0], chh: c[3] - c[1] };
  }
  function hitAny(b, list, pad) { pad = pad || 0; for (var i = 0; i < list.length; i++) { var o = list[i]; if (b[0] < o[2] + pad && b[2] > o[0] - pad && b[1] < o[3] + pad && b[3] > o[1] - pad) return true; } return false; }

  function frame() {
    if (!st || !svg) return;
    tick++;
    var ins = opts.inset || {}, vk = [g.innerWidth, g.innerHeight, ins.right || 0, ins.bottom || 0].join(','), grew = false;
    if (vk !== lastKey) { lastKey = vk; st.envC = st.envU = null; st.labSw = null; st.env = null; st.noteCheck = true; }   /* 视口 / 留边变了：包络重来，小注重量 */
    if (!st.envC || tick % 3 === 0) {
      var S = opts.scene, cb = S && S.crownScreenBounds ? S.crownScreenBounds() : null;
      if (cb && isFinite(cb.left) && cb.right > cb.left) grew = grow('envC', [cb.left, cb.top, cb.right, cb.bottom]);
    }
    if (!st.env || tick % 6 === 0) {
      var env = readEnv(vk), prev = st.env;
      if (env.lu && grow('envU', env.lu)) grew = true;
      for (var li = 0; li < env.labs.length; li++) if (sweep(env.lel[li], env.labs[li])) grew = true;
      env.labsSw = (st.labSw || []).filter(function (e) { return env.lel.indexOf(e.el) >= 0; }).map(function (e) { return e.b; });
      if (!prev || env.hsig !== prev.hsig) grew = true;
      st.env = env;
      /* 小注在窄屏可能折成两行：和上面的读数一起量（读阶段，不在 render 写完之后强制布局），按实测高度回写预算再排一次 */
      if (st.noteCheck && note && !note.hidden) {
        st.noteCheck = false;
        var nh = note.offsetHeight;
        if (nh > (st.noteHt || 16) + 2) { st.noteHt = nh; grew = true; }   /* 只增不减：免得「行数 ↔ 小注折行」来回振荡 */
      }
      if (!grew && (!prev || env.lsig !== prev.lsig)) knockout(env.labs);
    }
    if (!grew && !st.dirty) return;
    st.dirty = false;
    render(bounds(), st.env);
  }

  /* 按需建：只有上屏的珠 / 被挑中试排的关键短名才建节点。入场点燃的先后（--skd-i）按回序，在这里写（sky-deep 的 cascade 早于首次排版） */
  function ensureDot(d, k, N) {
    if (d.el) return d.el;
    var c = mk('circle', 'skc-ev' + (d.o.key ? ' is-key' : ''), st.gDots);
    c.setAttribute('data-ev', String(k)); c.style.setProperty('--skd-i', (N > 1 ? k / (N - 1) : 0).toFixed(3));
    c.setAttribute('tabindex', '0'); c.setAttribute('role', 'button');   /* 键盘可达：Tab 在珠之间走，方向键逐回（sky-compass-fan） */
    c.setAttribute('aria-label', '第 ' + d.o.no + ' 回 · ' + (d.o.count || 1) + ' 个事件' + (d.o.keyCount ? ' · ' + d.o.keyCount + ' 关键' : '') + ' · 展开事件短名');
    d.el = c; return c;
  }
  function ensureLab(d) {
    if (d.lab) return d.lab;
    d.lab = mk('text', 'skc-ev-label', svg.gChainLab); d.lab.textContent = short(d.o.e.title, 6); show(d.lab, false);
    return d.lab;
  }
  function render(B, E) {
    st.B = B;   /* 晶体包络（拖拽重算连线用） */
    var W = B.W, H = B.H, VW = g.innerWidth, VH = g.innerHeight, cx = B.cx;
    svg.setAttribute('viewBox', '0 0 ' + VW + ' ' + VH);   /* 画布始终全屏；W/H 只是扣掉留边后的可排布区 */
    attrs(svg.maskBg, { x: 0, y: 0, width: VW, height: VH });
    var core = [B.cx - B.cw / 2, B.cy - B.chh / 2, B.cx + B.cw / 2, B.cy + B.chh / 2], U = st.envU;
    if (U) { core[0] = Math.min(core[0], U[0]); core[1] = Math.min(core[1], U[1]); core[2] = Math.max(core[2], U[2]); core[3] = Math.max(core[3], U[3]); }
    /* 小注贴底（bottom:18px，高度按上一帧实测，窄屏会折成两行）；它的上沿就是罗盘排版的下界 */
    var top = E.hudTop + 16, noteHt = st.noteHt || 16, noteTop = Math.min(H, E.hudBottom) - 18 - noteHt, bottom = noteTop - 12;
    var n = st.sats.length, maxW = 0;
    st.sats.forEach(function (s) { s.w = Math.max(txtW(s.name, 12), txtW(s.kind, 10)); maxW = Math.max(maxW, s.w); });
    var sideNeed = maxW + 34;
    var orbit = n > 0 && core[0] - 18 - sideNeed >= 8 && (W - 8) - (core[2] + 18) >= sideNeed;
    st.mode = orbit ? 'orbit' : 'grid';
    /* 轨道半径：贴着晶体 + 轴签外缘留一段呼吸（按侧边余量取 45%，60–190px），而不是推到屏幕边 */
    var coreHalf = Math.max(cx - core[0], core[2] - cx), fit = Math.min(cx - 12 - maxW - 16, (W - cx) - 12 - maxW - 16);
    var rxO = Math.max(coreHalf + 44, Math.min(fit, coreHalf + clamp((fit - coreHalf) * 0.45, 60, 190)));

    /* ── 事件链几何：晶体（含轴签）下方一道浅弧 ── */
    /* 窄屏（≤560）：首尾回数写在链端下方，链可以占满整宽；竖向间距收紧一档 */
    var N = st.dots.length, tight = W <= 560, endW = tight ? 0 : Math.max(txtW(st.chNo0, 10), txtW(st.chNo1, 10)) + 12;
    var y0 = core[3] + 24, chordMax = Math.max(80, W - 2 * (endW + 22));
    /* 链宽：宽屏收在两侧轨道之间（不伸到关系对象底下），窄屏占满可用宽 */
    var chordCap = orbit ? Math.max(240, Math.min(chordMax, 2 * rxO * 0.92 - 2 * endW)) : chordMax;
    var chord = N <= 1 ? 0 : Math.min(chordCap, Math.max(core[2] - core[0] + 40, N * 26, 300));
    var sag = clamp(chord * 0.05, 10, 34), titleGap = tight ? 30 : 32, rowH = tight ? 46 : 50, gridPad = tight ? 12 : 20;
    var cols = 0, rows = 0;
    if (!orbit && n) { cols = clamp(Math.floor((W - 24) / Math.max(96, maxW + 22)), 2, 6); rows = Math.ceil(n / cols); }
    /* 自上而下的实际占位：链端 → 弧底 → 标题 → 网格（末行到关系词底 +34）；与 bottom（小注上沿 −12）比 */
    function need(r) { var yt = y0 + sag + titleGap - 6; return r ? yt + gridPad + 8 + (r - 1) * rowH + 34 : yt + 4; }
    /* 竖向预算不够：先压弧深，再收链与晶体的间隙，然后才少排一行关系对象（少排的计入「另 N 位未列」），最后才让链上移压进晶体下缘 */
    if (need(rows) > bottom) sag = Math.max(10, sag - (need(rows) - bottom));
    if (need(rows) > bottom) y0 = Math.max(core[3] + 12, y0 - (need(rows) - bottom));
    while (rows > 1 && need(rows) > bottom) rows--;
    if (need(rows) > bottom) y0 = Math.max(B.cy + B.chh * 0.2, y0 - (need(rows) - bottom));
    var x0 = cx - chord / 2, x1 = cx + chord / 2, sp = N > 1 ? chord / (N - 1) : 40;
    st.chainGeo = { x0: x0, x1: x1, y0: y0, sag: sag, cx: cx, chord: chord };   /* 扇出避让链身用 */
    var rMax = Math.min(clamp(sp * 0.42, 1.8, 6), 2.6 + 1.3 * Math.sqrt(st.maxC)), pts = [];
    function yAt(x) { var u = chord ? (x - cx) / (chord / 2) : 0; return y0 + sag * (1 - u * u); }
    /* 一回一颗珠排不开（珠距 < 5 px）：改铺时间密度带，带上只留少数关键珠（sky-compass-band） */
    var bh = clamp(chord / 120, 6, 11);   /* 带宽随链长（≈视口）放大：4K 下 7 px 的带读成一根线 */
    var band = g.CLSkyCompassBand ? CLSkyCompassBand.layout({ dots: st.dots, x0: x0, x1: x1, y: yAt, hMax: bh, keyMax: bh / 2 }) : null;
    st.band = band;
    st.dots.forEach(function (d, k) {
      var x = band ? band.xOf(d.o.c) : N === 1 ? cx : x0 + sp * k, y = yAt(x), on = !band || !!band.shown[k];
      var r = !on ? 0 : band ? clamp(2.4 + 1.8 * Math.sqrt((d.o.count || 1) / st.maxC), 2.4, 4.2) : Math.max(1.6, rMax * Math.sqrt((d.o.count || 1) / st.maxC));
      d.x = x; d.y = y; d.r = r; pts.push([x, y]);
      if (on) { ensureDot(d, k, N); attrs(d.el, { cx: x, cy: y, r: r }); show(d.el, true); }
      else if (d.el) show(d.el, false);
    });
    var chd = N > 1 ? 'M' + f1(x0) + ' ' + f1(y0) + 'Q' + f1(cx) + ' ' + f1(y0 + 2 * sag) + ' ' + f1(x1) + ' ' + f1(y0) : '';
    st.chain.setAttribute('d', chd); st.flow.setAttribute('d', chd); st.flowG.setAttribute('d', chd);
    st.bandAll.setAttribute('d', band ? band.pathAll : ''); st.bandKey.setAttribute('d', band ? band.pathKey : '');
    st.bandHit.setAttribute('d', band ? chd : ''); st.bandSel.setAttribute('d', ''); show(st.bandCur, false);
    svg.classList.toggle('skc-banded', !!band);
    var wantSteps = !band && N > 1 && sp >= 22;
    if (wantSteps) while (st.steps.length < N - 1) { var sg = mk('path', 'skc-step', st.gSteps); sg.setAttribute('marker-end', 'url(#skcArrow)'); st.steps.push(sg); }
    st.steps.forEach(function (seg, k) {
      var a = st.dots[k], b = st.dots[k + 1]; if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
      if (!wantSteps || len - a.r - b.r < 12) { seg.setAttribute('d', ''); return; }
      var ux = dx / len, uy = dy / len;
      seg.setAttribute('d', 'M' + f1(a.x + ux * (a.r + 3)) + ' ' + f1(a.y + uy * (a.r + 3)) + 'L' + f1(b.x - ux * (b.r + 4)) + ' ' + f1(b.y - uy * (b.r + 4)));
    });
    var yLow = N ? y0 + sag : y0, yT = yLow + titleGap - 6;
    if (N) {
      var d0 = st.dots[0], dz = st.dots[N - 1];
      st.chNo0.classList.toggle('is-below', tight); st.chNo1.classList.toggle('is-below', tight);
      if (tight) { attrs(st.chNo0, { x: d0.x - d0.r, y: d0.y + d0.r + 13 }); attrs(st.chNo1, { x: dz.x + dz.r, y: dz.y + dz.r + 13 }); }
      else { attrs(st.chNo0, { x: d0.x - d0.r - 8, y: d0.y + 3.5 }); attrs(st.chNo1, { x: dz.x + dz.r + 8, y: dz.y + 3.5 }); }
      show(st.chNo0, true); show(st.chNo1, N > 1);
    } else { show(st.chNo0, false); show(st.chNo1, false); }
    attrs(st.chainTitle, { x: cx, y: yT });
    var tw = txtW(st.chainTitle, 10), ry = yT - 3.5, rl = N > 1 ? x0 : cx - tw / 2 - 60, rr = N > 1 ? x1 : cx + tw / 2 + 60;
    st.ruleBoxes = [];
    if (rr - rl > tw + 48) {
      st.rule0.setAttribute('d', 'M' + f1(rl) + ' ' + f1(ry) + 'H' + f1(cx - tw / 2 - 12));
      st.rule1.setAttribute('d', 'M' + f1(cx + tw / 2 + 12) + ' ' + f1(ry) + 'H' + f1(rr));
      st.ruleBoxes = [[rl, ry - 2, cx - tw / 2 - 12, ry + 2], [cx + tw / 2 + 12, ry - 2, rr, ry + 2]];   /* 关键短名不压标题两侧的细线 */
    } else { st.rule0.setAttribute('d', ''); st.rule1.setAttribute('d', ''); }

    /* ── 关系对象 ── */
    var satBoxes = [];
    if (orbit) placeOrbit(); else placeGrid();
    knockout(E.labs);   /* 挖空：轴签处断开连线 */
    function placeOrbit() {
      var yTop = top + 16, yBot = Math.max(yTop + 90, y0 - 36);
      var nR = Math.ceil(n / 2), R = st.ord.slice(0, nR), Lf = st.ord.slice(nR).reverse();
      var cyO = (yTop + yBot) / 2, half = Math.max(40, (yBot - yTop) / 2), ryO = half / 0.7;
      st.orb = { cx: cx, cy: cyO, rx: rxO, ry: ryO };   /* 轨道椭圆：拖拽时其余关系星沿它让位 */
      function colY(k, m) { if (m === 1) return cyO; var span = Math.min(yBot - yTop, 104 * (m - 1)); return cyO - span / 2 + span * k / (m - 1); }
      function ex(y) { var t = (y - cyO) / ryO; return rxO * Math.sqrt(Math.max(0, 1 - t * t)); }
      var obs = E.labs.concat(E.hud);
      [[R, 1], [Lf, -1]].forEach(function (pair) {
        var list = pair[0], side = pair[1];
        list.forEach(function (i, k) {
          var s = st.sats[i], y = colY(k, list.length), x = cx + side * ex(y), guard = 0, box;
          function bx() { return side > 0 ? [x - 8, y - 15, x + 12 + s.w, y + 16] : [x - 12 - s.w, y - 15, x + 8, y + 16]; }
          box = bx();
          while ((hitAny(box, [core], 18) || hitAny(box, obs, 6)) && guard++ < 40) { x += side * 8; box = bx(); }
          x = side > 0 ? Math.min(x, W - 12 - s.w - 12) : Math.max(x, 12 + s.w + 12);
          s.x = x; s.y = y; s.side = side; s.shown = true; box = bx(); satBoxes.push(box);
          s.g.setAttribute('transform', 'translate(' + f1(x) + ' ' + f1(y) + ')'); show(s.g, true); s.g.setAttribute('tabindex', '0');
          attrs(s.name, { x: side > 0 ? 11 : -11, y: -2, 'text-anchor': side > 0 ? 'start' : 'end' });
          attrs(s.kind, { x: side > 0 ? 11 : -11, y: 12, 'text-anchor': side > 0 ? 'start' : 'end' });
          /* 连线：自晶体外缘（包围椭圆）径向出发，止于小星外 */
          var dx = x - B.cx, dy = y - B.cy, a = B.cw / 2 + 6, b = B.chh / 2 + 6, t = 1 / Math.sqrt((dx / a) * (dx / a) + (dy / b) * (dy / b)), len = Math.hypot(dx, dy) || 1;
          var sx = B.cx + dx * t, sy = B.cy + dy * t, exx = x - dx / len * (s.rr + 4), eyy = y - dy / len * (s.rr + 4);
          s.link.setAttribute('d', t < 1 ? 'M' + f1(sx) + ' ' + f1(sy) + 'L' + f1(exx) + ' ' + f1(eyy) : '');
        });
      });
      /* 轨道弧：只画两侧放着关系对象的那一段（上方留给姓名，下方交给事件链） */
      [1, -1].forEach(function (side, j) {
        var m = side > 0 ? R.length : Lf.length; if (!m) { st.arcs[j].setAttribute('d', ''); return; }
        var ya = Math.max(top, colY(0, m) - 30), yb = Math.min(yLow, colY(m - 1, m) + 30), d = '';
        for (var q = 0; q <= 24; q++) { var yy = ya + (yb - ya) * q / 24, xx = cx + side * ex(yy); d += (q ? 'L' : 'M') + f1(xx) + ' ' + f1(yy); }
        st.arcs[j].setAttribute('d', d);
      });
    }
    function placeGrid() {
      st.arcs.forEach(function (a) { a.setAttribute('d', ''); }); st.orb = null;
      /* 各行等量（7 = 4 + 3，不排成 6 + 1），每行居中；列宽全网格一致 */
      var gTop = yT + gridPad + 8, cellW = (W - 24) / Math.max(1, cols), m = Math.min(n, cols * rows), per = Math.max(1, Math.ceil(m / Math.max(1, rows)));
      st.ord.forEach(function (i, k) {
        var s = st.sats[i];
        if (k >= m) { s.shown = false; show(s.g, false); s.g.setAttribute('tabindex', '-1'); s.link.setAttribute('d', ''); return; }
        var row = Math.floor(k / per), col = k % per, inRow = row === rows - 1 ? m - row * per : per;
        var xs = 12 + (W - 24 - inRow * cellW) / 2, x = xs + cellW * (col + 0.5), y = gTop + row * rowH;
        s.x = x; s.y = y; s.side = 0; s.shown = true; satBoxes.push([x - s.w / 2 - 4, y - 14, x + s.w / 2 + 4, y + 34]);
        s.g.setAttribute('transform', 'translate(' + f1(x) + ' ' + f1(y) + ')'); show(s.g, true); s.g.setAttribute('tabindex', '0');
        attrs(s.name, { x: 0, y: 17, 'text-anchor': 'middle' });
        attrs(s.kind, { x: 0, y: 30, 'text-anchor': 'middle' });
        /* 单行网格：星上一截同线型的系绳指向上方晶体；多行时不画（免得读成上下两人之间的连线） */
        s.link.setAttribute('d', rows === 1 ? 'M' + f1(x) + ' ' + f1(y - s.rr - 12) + 'L' + f1(x) + ' ' + f1(y - s.rr - 3) : '');
      });
    }

    /* ── 关键事件短名：按事件数优先，贪心避让（不压彼此、珠、关系对象、轴签、标题、首尾回数、HUD） ── */
    var placed = [], beadBoxes = st.dots.filter(function (d) { return d.r > 0; }).map(function (d) { return [d.x - d.r - 1, d.y - d.r - 1, d.x + d.r + 1, d.y + d.r + 1, d]; });
    if (band) beadBoxes = beadBoxes.concat(band.boxes);
    var fixed = [[cx - tw / 2 - 6, yT - 11, cx + tw / 2 + 6, yT + 3]].concat(st.ruleBoxes || []);
    [st.chNo0, st.chNo1].forEach(function (t) {   /* 首尾回数的字框：宽屏写在链端外侧，窄屏写在链端下方（锚点方向相反） */
      if (t.getAttribute('visibility') === 'hidden') return;
      var w = txtW(t, 10), x = +t.getAttribute('x'), y = +t.getAttribute('y'), leftward = (t === st.chNo0) !== tight;
      fixed.push([leftward ? x - w - 2 : x - 2, y - 10, leftward ? x + 2 : x + w + 2, y + 3]);
    });
    var cbox = [B.cx - B.cw / 2, B.cy - B.chh / 2, B.cx + B.cw / 2, B.cy + B.chh / 2];
    var obsL = satBoxes.concat(E.labsSw || E.labs, E.hud, fixed, [cbox]), cap = Math.max(2, Math.floor(chord / 110));
    st.avoid = { fixed: fixed, sats: satBoxes, beads: beadBoxes, labs: E.labsSw || E.labs, hud: E.hud, W: W, top: top, bottom: bottom };   /* 扇出的避让表 */
    st.dots.forEach(function (d) { if (d.lab) show(d.lab, false); });
    var cand = st.dots.filter(function (d) { return d.o.key && d.r > 0; }).sort(function (a, b) { return (b.o.count - a.o.count) || (b.o.keyCount - a.o.keyCount) || (a.x - b.x); }).slice(0, cap * 4);
    cand.forEach(function (d) {
      ensureLab(d);
      var w = txtW(d.lab, 11), ok = null, rr = band ? Math.max(d.r, band.hMax + 1) : d.r;
      if (placed.length < cap) {
        [[d.y + rr + 14, 'below'], [d.y - rr - 6, 'above']].some(function (p) {
          var box = [d.x - w / 2 - 3, p[0] - 11, d.x + w / 2 + 3, p[0] + 3];
          if (box[0] < 6 || box[2] > W - 6 || box[3] > bottom) return false;
          if (hitAny(box, obsL, 2) || hitAny(box, placed, 12) || beadBoxes.some(function (bb) { return bb[4] !== d && box[0] < bb[2] && box[2] > bb[0] && box[1] < bb[3] && box[3] > bb[1]; })) return false;
          ok = [p[0], box]; return true;
        });
      }
      if (ok) { attrs(d.lab, { x: d.x, y: ok[0] }); show(d.lab, true); placed.push(ok[1]); d.labBox = ok[1]; }
      else { show(d.lab, false); d.labBox = null; }
    });
    st.labBoxes = placed;
    st.budget = { y0: Math.round(y0), sag: Math.round(sag), chord: Math.round(chord), rows: rows, cols: cols, bottom: Math.round(bottom), noteHt: noteHt };
    if (renderNote(E, W) || !st.noteSeen) { st.noteSeen = true; st.noteCheck = true; }
    if (g.CLSkyCompassDrag) CLSkyCompassDrag.relayout();   /* 重排后：拖拽把位移叠回、扇出按新珠位重排 */
    if (g.CLSkyCompassFan) CLSkyCompassFan.relayout();
  }

  /* ── 底部小注：与星空图例同风格（线型样本 + 名 + 数），数量守恒：列出的 + 未列的 = 全部联系 ── */
  function sw(cls) { return '<svg class="skc-sw" viewBox="0 0 24 6" aria-hidden="true"><line class="' + cls + '" x1="1" y1="3" x2="23" y2="3"/></svg>'; }
  function renderNote(E, W) {
    if (!note) return;
    var counts = {}, order = [], shownN = 0;
    st.sats.forEach(function (s) { if (!s.shown) return; shownN++; var c = s.r.cls; if (!counts[c]) { counts[c] = 0; order.push(c); } counts[c]++; });
    order.sort(function (a, b) { return relRank(a) - relRank(b); });
    var parts = [];
    order.forEach(function (c) { parts.push('<span class="lg skc-lg">' + sw('skc-link r-' + c) + esc(relLabel(c)) + ' <b>' + counts[c] + '</b></span>'); });
    var rest = st.total - shownN;
    /* 窄屏且全部列出时省掉「共 N 位」（各类计数之和即全部）；有未列的余数则总数必写 */
    if (!st.total) parts.push('<span class="lg skc-lg-sum">暂无联系记录</span>');
    else if (rest > 0 || W > 560) parts.push('<span class="lg skc-lg-sum">' + (rest > 0 ? '另 ' + rest + ' 位未列 · ' : '') + '共 ' + st.total + ' 位联系</span>');
    if (E.gl) parts.push('<span class="lg skc-lg">' + sw('skc-sw-ref') + '点线 = 未建档参考轮廓（非数据）</span>');
    var html = parts.join(''), ins = Math.round((opts.inset && opts.inset.right) || 0) + 'px', changed = false;
    if (note.style.getPropertyValue('--skc-inset-r') !== ins) { note.style.setProperty('--skc-inset-r', ins); changed = true; }
    if (html !== st.noteKey) { note.innerHTML = html; st.noteKey = html; changed = true; }
    return changed;
  }

  /* ── 交互：事件 ↔ 关系对象 互相点亮 ───────────────── */
  function lightEvent(k) {
    var d = st.dots[k]; if (!d) return;
    var cast = d.o.e.characters || [];
    st.sats.forEach(function (s) { var on = cast.indexOf(s.r.name) >= 0; s.g.classList.toggle('is-lit', on); s.link.classList.toggle('is-lit', on); });
    st.dots.forEach(function (x, j) { if (x.el) x.el.classList.toggle('is-on', j === k); if (x.lab) x.lab.classList.toggle('is-on', j === k); });
    /* 带上没有珠的回：一粒游标落在带上它的位置 */
    if (st.bandCur) { var cur = st.band && !d.el; if (cur) attrs(st.bandCur, { cx: d.x, cy: d.y, r: 3.2 }); show(st.bandCur, cur); }
    svg.classList.add('skc-emph');
    showCard('<div class="sc-k">第 ' + d.o.no + ' 回 · ' + (d.o.count > 1 ? d.o.count + ' 个事件' + (d.o.keyCount ? ' · ' + d.o.keyCount + ' 关键' : '') : esc(d.o.e.kind || '')) + '</div><div class="sc-t">' + esc(d.o.e.title || '') + '</div>' + (d.o.count > 1 && g.CLSkyCompassFan ? '' : '<div class="sc-c">' + esc(d.o.e.summary || '') + '</div>') + '<div class="sc-m">同场：' + esc(cast.filter(function (n) { return n !== st.name; }).slice(0, 8).join('、') || '—') + '</div>', d.x, d.y);
    if (g.CLSkyCompassFan) CLSkyCompassFan.open(k);   /* 该回全部事件短名扇形展开（悬停卡片让到扇面旁边） */
  }
  function lightSat(i) {
    var s = st.sats[i]; if (!s) return;
    var shared = st.dots.filter(function (d) { return (d.o.e.characters || []).indexOf(s.r.name) >= 0; });
    st.dots.forEach(function (d) { var on = shared.indexOf(d) >= 0; if (d.el) d.el.classList.toggle('is-on', on); if (d.lab) d.lab.classList.toggle('is-on', on); });
    if (st.band && st.bandSel) st.bandSel.setAttribute('d', g.CLSkyCompassBand.subset(st.band, function (d) { return shared.indexOf(d) >= 0; }));
    st.sats.forEach(function (x, j) { x.g.classList.toggle('is-lit', j === i); x.link.classList.toggle('is-lit', j === i); });
    svg.classList.add('skc-emph'); if (g.CLSkyCompassFan) CLSkyCompassFan.close();
    showCard('<div class="sc-k">' + esc(s.r.derived ? '同场 · 由事件推导' : s.r.clsLabel + ' · ' + s.r.kind) + '</div><div class="sc-t">' + esc(s.r.name) + '</div><div class="sc-m">共同出场 ' + shared.length + ' 回' + (shared.length ? ' · 第 ' + shared[0].o.no + (shared.length > 1 ? '–' + shared[shared.length - 1].o.no : '') + ' 回' : '') + '</div>' + (s.r.desc && !s.r.derived ? '<div class="sc-c">' + esc(s.r.desc) + '</div>' : '') + '<div class="sc-m">点击进入 ' + esc(s.r.name) + ' 的罗盘</div>', s.x, s.y);
  }
  function unlight() {
    if (!st) return; svg.classList.remove('skc-emph');
    st.sats.forEach(function (x) { x.g.classList.remove('is-lit'); x.link.classList.remove('is-lit'); });
    st.dots.forEach(function (x) { if (x.el) x.el.classList.remove('is-on'); if (x.lab) x.lab.classList.remove('is-on'); });
    if (st.bandSel) st.bandSel.setAttribute('d', ''); if (st.bandCur) show(st.bandCur, false); st.bandK = -1;
    svg.card.hidden = true; if (g.CLSkyCompassFan) CLSkyCompassFan.close();
  }
  function showCard(html, x, y) {
    var c = svg.card; c.innerHTML = html; c.hidden = false;
    var w = c.offsetWidth || 240, h = c.offsetHeight || 90, left = x + 16, top = y - h - 12;
    if (left + w > g.innerWidth - 12) left = x - w - 16;
    if (top < 76) top = y + 16;
    if (top + h > g.innerHeight - 8) top = Math.max(76, g.innerHeight - 8 - h);
    c.style.setProperty('--sc-x', Math.max(12, left).toFixed(0) + 'px'); c.style.setProperty('--sc-y', top.toFixed(0) + 'px');
  }
  function target(e) { var t = e.target; return t && t.closest ? t.closest('[data-sat],[data-ev]') : null; }
  /* 密度带：带上横向移动 = 沿时间扫过每一回（最近的一回） */
  function onBandMove(e) {
    if (!st || !st.band || !e.target || !e.target.hasAttribute || !e.target.hasAttribute('data-band')) return;
    var k = st.band.nearest(e.clientX);
    if (k !== st.bandK) { st.bandK = k; lightEvent(k); }
  }
  function onBandOut(e) { if (st && e.target && e.target.hasAttribute && e.target.hasAttribute('data-band')) unlight(); }
  function onOver(e) { var t = target(e); if (!t || !st) return; if (t.hasAttribute('data-sat')) lightSat(+t.getAttribute('data-sat')); else lightEvent(+t.getAttribute('data-ev')); }
  function onOut(e) { var t = target(e); if (!t) return; var to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('[data-sat],[data-ev]') : null; if (to === t) return; unlight(); }
  function onClick(e) { var t = target(e); if (!t || !st) return; if (t.hasAttribute('data-sat')) { var s = st.sats[+t.getAttribute('data-sat')]; if (s && opts.onPick) { unlight(); opts.onPick(s.r.name); } } }
  doc.addEventListener('keydown', function (e) { if (!st || (e.key !== 'Enter' && e.key !== ' ')) return; var t = e.target && e.target.closest && e.target.closest('[data-sat]'); if (!t) return; e.preventDefault(); var s = st.sats[+t.getAttribute('data-sat')]; if (s && opts.onPick) opts.onPick(s.r.name); });

  /* 空闲时预热晶体模型的叙事八维排名缓存：首开罗盘要为全书每个人算一遍叙事维度（大书约 35 ms，落在点星那一下）。
     与场景同一份图（skyView）、同一个 metaOf，缓存才对得上；等开篇揭幕走完再做，不抢开篇的帧 */
  var FONT_CLS = ['skc-sat-name', 'skc-sat-kind', 'skc-ev-label', 'skc-ch', 'skc-chain-title'];
  /* 空闲预热（分片，一片 ≤ 本帧空闲余量）：① 量字用的字体（开罗盘那一刻 body 换类，任何计算样式读取都要先把整页样式重算一遍）；
     ② 罗盘会量到的每个字（人名 / 关系词 / 回目短名去重后逐字）在各字体下量一遍——首次量某个字要现取字形（大书开罗盘那一下 measureText 占 27 ms）；
     ③ 晶体模型的叙事八维排名缓存（首开要为全书每人算一遍叙事维度，大书约 35 ms）。
     以前一口气做完是 190 ms 的长任务（开篇后约 5 s，正赶上用户第一次点星），现在切成 ≤ 空闲余量的小片 */
  var warm = null;
  function idle(fn) { if (g.requestIdleCallback) g.requestIdleCallback(fn, { timeout: 5000 }); else setTimeout(function () { fn(null); }, 80); }
  function glyphSet(V) {
    var seen = {}, out = [];
    function add(t) { t = String(t || ''); for (var i = 0; i < t.length; i++) { var ch = t.charAt(i); if (!seen[ch]) { seen[ch] = 1; out.push(ch); } } }
    (V.characters || []).forEach(function (c) { add(c.name); });
    (V.relations || []).forEach(function (r) { add(r.kind); });
    (V.events || []).forEach(function (e) { add(String(e.title || '').slice(0, 6)); });
    add('第回事件链·0123456789…◆ 暂无记录同场');
    return out.join('');
  }
  function warmStep(dl) {
    if (!warm) return;
    try {
      do {
        if (warm.step === 0) {   /* 字体：一次取五个类的计算样式（只算样式、不排版） */
          ensureSvg(); if (!mctx) mctx = doc.createElement('canvas').getContext('2d');
          warm.fonts = FONT_CLS.map(function (c) { var t = mk('text', c, svg), f = fontFor(t); svg.removeChild(t); return f.font; });
          warm.step = 1;
        } else if (warm.step === 1) {   /* 字形：每片 120 个字 */
          mctx.font = warm.fonts[warm.fi]; mctx.measureText(warm.glyphs.slice(warm.ci, warm.ci + 120)); warm.ci += 120;
          if (warm.ci >= warm.glyphs.length) { warm.ci = 0; if (++warm.fi >= warm.fonts.length) warm.step = 2; }
        } else {   /* 叙事八维排名（单片，约 35 ms，只在空闲里做） */
          var GM = g.CLGemModel, S = warm.A.scene ? warm.A.scene() : null;
          if (S && S.metaOf && GM && GM.build && warm.V.characters.length) GM.build(warm.V.characters[0], warm.V, { metaOf: S.metaOf });
          warm = null; return;
        }
      } while (dl && !dl.didTimeout && dl.timeRemaining() > 4);
    } catch (e) { warm = null; return; }   /* 预热失败不影响首开：照常现算 */
    idle(warmStep);
  }
  function prewarm() {
    var A = g.CLApp, V = A && A.atlas && A.atlas.skyView ? A.atlas.skyView() : null;
    if (!V || !V.characters || !V.characters.length) return;
    warm = { A: A, V: V, glyphs: glyphSet(V), fonts: null, fi: 0, ci: 0, step: 0 };
    idle(warmStep);
  }
  /* 等开篇揭幕走完再预热，不抢开篇的帧；换书时重来 */
  doc.addEventListener('cl:graph-ready', function () { warm = null; setTimeout(prewarm, 4500); });

  g.CLSkyCompass = {
    open: open, close: close, frame: frame, prewarm: prewarm,
    setInset: function (ins) { if (opts) { opts.inset = ins; lastKey = ''; frame(); } },
    eventInfo: function (k) { var x = st && st.dots[k]; return x ? { no: x.o.no, kind: x.o.count > 1 ? x.o.count + ' 个事件' : (x.o.e.kind || ''), title: x.o.e.title || '', count: x.o.count || 1, cast: (x.o.e.characters || []).slice() } : null; },
    hoverEvent: function (k) { if (!st || !st.dots[k]) return false; if (st.dirty || !st.env) frame(); lightEvent(k); return true; }, hoverSat: function (i) { if (!st || !st.sats[i]) return false; lightSat(i); return true; }, unhover: function () { unlight(); },
    keyEvents: function () { if (st && (st.dirty || !st.env)) frame(); return st ? st.dots.map(function (d, k) { return d.o.key && (!st.band || st.band.shown[k]) ? k : -1; }).filter(function (k) { return k >= 0; }) : []; },
    satellites: function () { return st ? st.sats.map(function (s) { return { name: s.r.name, cls: s.r.cls, kind: s.r.kind, derived: s.r.derived, strength: s.r.strength || 0 }; }) : []; },
    stats: function () { return st ? { open: true, name: st.name, satellites: st.sats.length, more: st.more, total: st.total, events: st.dots.length, eventCount: st.nEv, band: !!st.band, beadsShown: st.dots.filter(function (d) { return d.r > 0; }).length, chainNodes: st.gDots ? st.gDots.childNodes.length + st.gSteps.childNodes.length + svg.gChainLab.childNodes.length : 0, derived: !!(st.rels[0] && st.rels[0].derived), mode: st.mode || null } : { open: false }; },
    /* 排版读数（探针）：sats 带下标 i / 侧 side / 星半径 rr（家位 = 拖拽回弹的目标）；satsOnly 时只回关系对象与轨道椭圆 */
    _layout: function (satsOnly) {
      if (!st) return null;
      var sats = st.sats.map(function (s, i) { return { i: i, name: s.r.name, x: s.x, y: s.y, cls: s.r.cls, side: s.side || 0, rr: s.rr, on: s.g.getAttribute('visibility') !== 'hidden' }; }).filter(function (s) { return s.on; });
      if (satsOnly) return { mode: st.mode || null, sats: sats, orb: st.orb || null, B: st.B || null };
      return { mode: st.mode || null, sats: sats, orb: st.orb || null,
        dots: st.dots.map(function (d) { return { x: d.x, y: d.y, r: d.r, key: d.o.key, count: d.o.count }; }),
        labels: (st.labBoxes || []).map(function (b) { return b.map(Math.round); }), budget: st.budget || null };
    }
  };
})(window);
