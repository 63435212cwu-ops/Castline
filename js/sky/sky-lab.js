/**
 * @role component
 * @owns js/sky/sky-lab.js
 * 星空预演实验室：故事板 9 帧（C0–C1 星座 · P0–P3 星盘 · K0–K2 罗盘）· 读图模式（收字 / 关光 / 灰阶 / 静止）· #sky= 深链 · 样例切换。
 * 纪律：只经公开 API 驱动真实舞台（CLSky / CLSkyCompass / CLApp.scene()）；不猴补别人的对象、不改别人的 DOM；
 * 不写 data/、不触发分析；不私开 rAF，帧间等待只用一次性 setTimeout，且随 token 失效（旧帧的回调不得把画面拉回）。
 * 缺失的宿主能力做可见降级（按钮 aria-disabled + 原因 / 栏内注记）。
 */
(function (g) {
  'use strict';
  var d = g.document, SKY = g.CLSky;
  if (!d || !SKY || typeof SKY.enabled !== 'function' || !SKY.enabled()) return;

  var RETURN_KEY = 'castline.skylab.return', BASE_GROUP = 'camp', HASH_KEY = 'sky=';
  var MODES = ['notext', 'noglow', 'gray', 'still'];
  var MODE_LABEL = { notext: '收字', noglow: '关光', gray: '灰阶', still: '静止' };
  var MODE_HELP = {
    notext: '收字：隐藏支线弧名、悬停卡、图例提示与星名副行；保留团名、主线段名、回数与实体名',
    noglow: '关光：WebGL 泛光归零（scene.setGlow(0)），文字辉光一并去掉；退出即复原',
    gray: '灰阶：舞台与 SVG 图层去色，检验主支线、选中与方向是否只靠颜色区分',
    still: '静止：星盘与场景直接落终态（CLSky.setCalm + scene 静止），并停下播放'
  };
  var GROUPS = [{ key: 'C', label: '星座' }, { key: 'P', label: '星盘' }, { key: 'K', label: '罗盘' }];
  var FRAMES = [
    { id: 'C0', name: '全景', q: '全书分几派、各多少人、谁和谁有联系' },
    { id: 'C1', name: '换分类', q: '换一种分类，势力范围怎样重新划分' },
    { id: 'P0', name: '唤醒星盘', q: '全书几段主线、几条支线、各跨多少回' },
    { id: 'P1', name: '主线', q: '事件最多的主线段从第几回到第几回、谁参与' },
    { id: 'P2', name: '支线', q: '这条支线从第几回到第几回、谁参与' },
    { id: 'P3', name: '播到中点', q: '读到全书一半时，哪些线正在进行、谁在场' },
    { id: 'K0', name: '罗盘', q: '咖位最高的是谁、连着多少人、参与多少事件' },
    { id: 'K1', name: '关系对象', q: '他最强的联系对象是谁、那人又连着多少人' },
    { id: 'K2', name: '因果链', q: '他的第一个关键事件在第几回、当时谁在场' }
  ];
  var SAMPLES = [
    { file: 'data/sample-saga.json', label: '中篇', hint: 'saga' },
    { file: 'data/sample-mid.json', label: '群像', hint: 'mid' },
    { file: 'data/sample-large.json', label: '长篇', hint: 'large' },
    { file: 'data/sample-focus.json', label: '聚焦', hint: 'focus' }
  ];
  var DROP_PARAMS = ['data', 'demo', 'lib', 'sel', 'view', 'api', 'onboard', 'plot'];
  var NEED = {
    base: ['CLSky.state', 'CLSky.snapshot', 'CLSky.model', 'CLSky.disc', 'CLSky.stop'],
    stage: ['CLSky.setPlot', 'CLSky.plot', 'CLSky.regroup', 'CLSky.closeCompass', 'CLSky.focusLine'],
    hover: ['CLSky.hoverLine'], seek: ['CLSky.seek'],
    compass: ['CLSky.openCompass', 'CLSkyCompass.stats', 'CLSkyCompass.unhover'],
    sats: ['CLSkyCompass.satellites'], ev: ['CLSkyCompass.hoverEvent', 'CLSkyCompass.keyEvents']
  };
  var FRAME_NEED = { C0: ['base', 'stage'], C1: ['base', 'stage'], P0: ['base', 'stage'], P1: ['base', 'stage', 'hover'], P2: ['base', 'stage', 'hover'],
    P3: ['base', 'stage', 'seek'], K0: ['base', 'stage', 'compass'], K1: ['base', 'stage', 'compass', 'sats'], K2: ['base', 'stage', 'compass', 'ev'] };
  var GLYPH = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5v17"/><path d="M5 6.5h3M5 12h5M5 17.5h3"/><path class="gl-hot" d="M16.5 8.5 20 12l-3.5 3.5L13 12z"/></svg>';

  var root = null, els = {}, btn = null;
  var on = false, open = true, seq = 0, running = null, frameId = null, frameSig = null, card = null;
  var mode = { notext: false, noglow: false, gray: false, still: false }, saved = { glow: 1, calm: false };
  var planCache = null, lastNote = '', errors = [], interrupts = 0, linkResult = null, pendingLink = null, lastAnswer = {}, lastBrief = {}, degraded = {};
  var flyUntil = 0, samplesOpen = false, renderQ = false, addr = { ok: false, reason: '尚未载入作品' }, insetKey = '', cover = 0;

  // ------------------------------------------------------------------ 访问器（只读取、只调用公开 API）
  function app() { return g.CLApp || null; }
  function graph() { var a = app(); return a && a.graph ? a.graph() : null; }
  function scene() { var a = app(); return a && a.scene ? a.scene() : null; }
  function model() { return SKY.model ? SKY.model() : null; }
  function disc() { return SKY.disc ? SKY.disc() : null; }
  function comp() { return g.CLSkyCompass || null; }
  function sst() { return SKY.state(); }
  function $(id) { return d.getElementById(id); }
  var now = g.CLSkyUtil.nowMs;
  function sleep(ms) { return new Promise(function (r) { if (!(ms > 0)) r(); else g.setTimeout(r, ms); }); }
  function has(path) { var o = g, p = path.split('.'); for (var i = 0; i < p.length; i++) { if (o == null) return false; o = o[p[i]]; } return typeof o === 'function'; }
  function missing(id) { var out = []; (FRAME_NEED[id] || ['base']).forEach(function (k) { NEED[k].forEach(function (p) { if (!has(p) && out.indexOf(p) < 0) out.push(p); }); }); return out; }
  function frameOf(id) { return FRAMES.filter(function (f) { return f.id === id; })[0] || null; }
  function charOf(name) { var G = graph(); return G && (G.characters || []).filter(function (c) { return c.name === name; })[0] || null; }
  function eventsOf(name) { var G = graph(); return G ? (G.events || []).filter(function (e) { return (e.characters || []).indexOf(name) >= 0; }).length : 0; }

  /* 时间：令牌时长；低动效 / 低档 / 静止直接落终态。镜头飞行由宿主按 prefers-reduced-motion 决定，与「静止」无关，单独计。 */
  function reducedMotion() { try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; } }
  function lowTier() { try { return !!(g.CLOrbit3DTier && CLOrbit3DTier.get() === 'low'); } catch (e) { return false; } }
  function quiet() { return reducedMotion() || lowTier() || mode.still; }
  function dur(n) {
    if (!n || quiet()) return 0;
    var v = String(g.getComputedStyle(d.documentElement).getPropertyValue('--cl-atlas-dur-' + n) || '').trim();
    var ms = /ms$/.test(v) ? parseFloat(v) : /s$/.test(v) ? parseFloat(v) * 1000 : NaN;
    return isFinite(ms) ? ms : [0, 220, 360, 780][n] || 0;
  }
  function FLY() { return reducedMotion() ? 80 : 1250; }          /* 宿主 flyTo：开剧情 1.2s / 收剧情 0.9s / 罗盘入场 */
  function GROW() { return reducedMotion() || mode.still ? 0 : 2500; }  /* 星盘生长：主线 → 支线 → 名字，约 2.4s 落定 */
  function fly(ms) { flyUntil = Math.max(flyUntil, now() + (ms || 0)); }

  // ------------------------------------------------------------------ 确定性选取：同一作品同一结果，不按下标替选
  function plan() {
    var M = model(), G = graph(); if (!M || !M.ok || !G) return null;
    if (planCache && planCache.M === M && planCache.G === G) return planCache;
    var p = { M: M, G: G, other: null, otherKind: '', k2: null };
    p.group2 = (M.groupings || []).filter(function (x) { return x.key !== BASE_GROUP; })[0] || null;
    p.main = null; (M.mains || []).forEach(function (m) { if (!p.main || m.n > p.main.n) p.main = m; });   /* 并列取最早（mains 已按起始回排序） */
    p.branch = (M.lines || []).filter(function (l) { return l.named && l.rank === 0; })[0] || null;
    p.mid = M.nCh ? Math.floor(M.nCh / 2) : null;
    p.top = null;
    (G.characters || []).forEach(function (c) { if (c.importanceKnown === false || typeof c.importance !== 'number' || !isFinite(c.importance)) return; if (!p.top || c.importance > p.top.importance) p.top = c; });
    planCache = p; return p;
  }
  function why(id, p) {
    var miss = missing(id); if (miss.length) return '缺宿主 API：' + miss.join('、');
    if (!p) return '尚未载入作品';
    var k = id.charAt(0);
    if (id === 'C1' && !p.group2) return '本作只有一种分类 · 无从切换';
    if (k === 'P' && !p.M.nCh) return '没有回目 · 星盘无从展开';
    if (id === 'P1' && !p.main) return '剧情树没有主线段';
    if (id === 'P2' && !p.branch) return '没有具名支线';
    if (k === 'K' && !p.top) return '咖位未提供 · 不按顺序替选角色';
    return '';
  }
  function target(id, p) {
    var t = { frame: id, group: BASE_GROUP, plot: false, compass: null, cursor: null, line: null, hover: null };
    switch (id) {
      case 'C1': t.group = p.group2.key; t.groupLabel = p.group2.label; break;
      case 'P0': t.plot = true; break;
      case 'P1': t.plot = true; t.hover = String(p.main.id); t.label = p.main.label; break;
      case 'P2': t.plot = true; t.hover = String(p.branch.id); t.label = p.branch.label; break;
      case 'P3': t.plot = true; t.cursor = p.mid; break;
      case 'K0': t.compass = p.top.name; break;
      case 'K1': t.compass = p.other; t.via = p.top.name; break;
      case 'K2': t.compass = p.top.name; t.event = p.k2 ? p.k2.index : 'first-key'; break;
    }
    return t;
  }

  // ------------------------------------------------------------------ 舞台动作（每步幂等、同步；返回下一拍等待：毫秒，或 'settle' = 等镜头落定）
  function clearSim() {
    var dd = disc(), C = comp();
    if (dd && dd.hover && dd.hover() != null && dd.state() === 'plot') SKY.hoverLine(null);
    if (C && C.unhover && sst().mode === 'compass') C.unhover();
  }
  function stopPlay() { if (sst().playing) SKY.stop(); }
  function clearCursor() {
    if (typeof SKY.clearCursor === 'function') { SKY.clearCursor(); return; }
    /* 宿主没有「清游标」：直接清星盘游标并按空悬停复位点亮；底栏回目字幕由宿主持有 */
    var dd = disc(); dd.setCursor(null); SKY.hoverLine(null); degraded.clearCursor = true;
  }
  function toConstellation(group) {
    return function () {
      clearSim(); stopPlay();
      if (sst().mode === 'compass') { SKY.closeCompass(); fly(FLY()); }
      if (SKY.plot()) { SKY.setPlot(false); fly(FLY()); }
      if (sst().group !== group) { SKY.regroup(group); fly(dur(3)); }
      return 0;
    };
  }
  /* 从罗盘回星盘：先退罗盘、等镜头落回星座机位，再开剧情——否则宿主会把「罗盘飞回途中」的机位当成剧情前机位，取景拉得过远（窄屏甚至越过远裁剪面） */
  function leaveCompass() {
    return function () {
      clearSim(); stopPlay();
      if (sst().mode === 'compass') { SKY.closeCompass(); fly(FLY()); return 'settle'; }
      return 0;
    };
  }
  function toPlot(group, keepCursor) {
    return function () {
      clearSim(); stopPlay();
      if (sst().mode === 'compass') { SKY.closeCompass(); fly(FLY()); }
      if (sst().group !== group) SKY.regroup(group);
      if (!SKY.plot()) { SKY.setPlot(true); fly(FLY()); fly(GROW()); }
      var dd = disc();
      if (dd.focused && dd.focused() != null) SKY.focusLine(null);
      if (!keepCursor && dd.cursor() != null) clearCursor();
      return 0;
    };
  }
  function hoverTo(id) { return function () { if (!SKY.hoverLine(String(id))) throw new Error('星盘上找不到线 ' + id); return 0; }; }
  function focusTo(id) { return function () { SKY.focusLine(String(id)); return 0; }; }
  function seekTo(c) { return function () { SKY.seek(c); return 0; }; }
  function noop() { return 0; }
  /* 进罗盘前先收剧情：等镜头飞回剧情前机位再进 */
  function leavePlotFor(group) {
    return function () {
      clearSim(); stopPlay();
      var s = sst();
      if (s.group !== group) { if (s.mode === 'compass') { SKY.closeCompass(); fly(FLY()); } SKY.regroup(group); fly(dur(3)); }
      if (SKY.plot()) { SKY.setPlot(false); fly(FLY()); }
      return 'settle';
    };
  }
  function openFor(nameOf) {
    return function () {
      var n = typeof nameOf === 'function' ? nameOf() : nameOf;
      if (!n) throw new Error('没有可进入的罗盘对象');
      var s = sst();
      if (s.mode === 'compass' && s.compass === n) { if (comp() && comp().unhover) comp().unhover(); return 0; }
      if (!SKY.openCompass(n)) throw new Error('罗盘打不开：' + n);
      fly(FLY());
      return 'settle';
    };
  }
  function pickOther(p) {
    return function () {
      var sats = comp().satellites() || [];
      if (sst().compass !== p.top.name) throw new Error('未停在 ' + p.top.name + ' 的罗盘');
      if (!sats.length) { var e = new Error(p.top.name + ' 没有联系对象 · 不替选他人'); e.soft = true; throw e; }
      p.other = sats[0].name; p.otherKind = sats[0].derived ? '同场' : (sats[0].kind || '联系');
      return openFor(p.other)();
    };
  }
  function hoverKey(p) {
    return function () {
      var C = comp(), keys = C.keyEvents() || [], k = keys.length ? keys[0] : 0;
      if (!C.hoverEvent(k)) { var e = new Error(p.top.name + ' 没有可悬停的事件'); e.soft = true; throw e; }
      p.k2 = { index: k, fallback: !keys.length };
      return 0;
    };
  }
  function stepsFor(id, p) {
    var t = target(id, p);
    if (id === 'C0' || id === 'C1') return [toConstellation(t.group)];
    if (id === 'P0') return [leaveCompass(), toPlot(BASE_GROUP, false)];
    if (id === 'P1' || id === 'P2') return [leaveCompass(), toPlot(BASE_GROUP, false), hoverTo(t.hover)];
    if (id === 'P3') return [leaveCompass(), toPlot(BASE_GROUP, true), seekTo(t.cursor)];
    if (id === 'K0') return [leavePlotFor(BASE_GROUP), openFor(p.top.name)];
    if (id === 'K1') {
      var s = sst();
      if (p.other && s.mode === 'compass' && s.compass === p.other && s.group === BASE_GROUP) return [function () { clearSim(); return 0; }];
      return [leavePlotFor(BASE_GROUP), openFor(p.top.name), function () { return dur(3); }, pickOther(p)];
    }
    if (id === 'K2') return [leavePlotFor(BASE_GROUP), openFor(p.top.name), hoverKey(p)];
    return [];
  }
  function snapSteps(s) {
    var grp = s.group || BASE_GROUP;
    if (s.compass) return [leavePlotFor(grp), openFor(s.compass)];
    if (s.plot) return [leaveCompass(), toPlot(grp, s.cursor != null), s.cursor != null ? seekTo(s.cursor) : noop, s.line != null ? focusTo(s.line) : noop];
    return [toConstellation(grp)];
  }

  // ------------------------------------------------------------------ 导演：token 化；等待中被别人改动舞台 = 用户接管，余下步骤作废
  function drift() {
    var s = sst(), dd = disc();
    return JSON.stringify([s.mode, s.plot, s.compass, s.group, s.cursor, s.playing, dd && dd.focused ? dd.focused() : null]);
  }
  function sigFull() {
    var s = sst(), dd = disc(), lit = null;
    if (s.mode === 'compass') lit = [].map.call(d.querySelectorAll('.sky-compass .skc-ev.is-on'), function (e) { return e.getAttribute('data-ev'); }).join(',');
    return JSON.stringify([s.mode, s.plot, s.compass, s.group, s.cursor, s.playing, dd && dd.focused ? dd.focused() : null, dd && dd.hover ? dd.hover() : null, lit]);
  }
  function current() { return frameId && frameSig === sigFull() ? frameId : null; }
  function run(steps, my) {
    var i = 0, mark = null;
    function next() {
      if (my !== seq) return Promise.resolve(false);
      if (mark !== null && drift() !== mark) { cancel('检测到新的操作 · 未完成的帧步骤已作废'); return Promise.resolve(false); }
      if (i >= steps.length) { var rest = flyUntil - now(); return sleep(rest).then(function () { return my === seq; }); }
      var w = steps[i++]();
      mark = drift();
      return sleep(w === 'settle' ? flyUntil - now() : w).then(next);
    }
    try { return next(); } catch (e) { return Promise.reject(e); }
  }
  function cancel(msg) { if (!running) return; seq++; running = null; interrupts++; if (msg) note(msg); queueRender(); }
  function go(id, via) {
    id = String(id || '').toUpperCase();
    var f = frameOf(id); if (!f) return Promise.resolve({ ok: false, id: id, reason: '未知帧' });
    setOn(true);
    var my = ++seq; running = id; frameId = null; frameSig = null;
    var p = plan(), w = why(id, p);
    card = { id: id, why: w }; if (running !== 'link') note('');
    if (w) { running = null; render(); return Promise.resolve({ ok: false, id: id, reason: w }); }
    if (via === 'ui' && autoFold()) setOpen(false);
    var steps = stepsFor(id, p);
    render();
    return run(steps, my).then(function (done) {
      if (!done || my !== seq) return { ok: false, id: id, cancelled: true };
      running = null; frameId = id; frameSig = sigFull();
      try { lastAnswer[id] = answer(id, p); lastBrief[id] = brief(id, p); } catch (e) { lastAnswer[id] = ''; lastBrief[id] = ''; errors.push('answer ' + id + ': ' + (e && e.message)); }
      render();
      return { ok: true, id: id, state: snapshot() };
    }, function (err) {
      var msg = String(err && err.message || err);
      if (my === seq) { running = null; card = { id: id, why: msg }; }
      if (!(err && err.soft)) errors.push(String(err && (err.stack || err.message) || err));
      note('帧 ' + id + ' 未完成 · ' + msg); render();
      return { ok: false, id: id, error: msg };
    });
  }

  // ------------------------------------------------------------------ 这一帧的实际读数（只取已有记录；缺即写缺）
  function groupingOf(key) { var M = model(); return (M && M.groupings || []).filter(function (x) { return x.key === key; })[0] || null; }
  function answer(id, p) {
    var M = p.M, G = p.G, s = sst(), dd = disc(), C = comp(), info, ch;
    switch (id) {
      case 'C0': case 'C1': {
        var gp = groupingOf(s.group), v = app().atlas && app().atlas.skyView ? app().atlas.skyView() : null;
        var camps = (v && v.camps || []).filter(function (c) { return c.members && c.members.length; }), rels = v && v.relations || [];
        var big = camps.slice().sort(function (a, b) { return b.members.length - a.members.length; })[0];
        return (gp ? '按「' + gp.label + '」· ' : '') + camps.length + ' 团 · ' + G.characters.length + ' 人' + (big ? ' · 最大「' + big.name + '」' + big.members.length + ' 人' : '') +
          ' · ' + rels.length + ' 条联系' + (rels.length && rels[0].derived ? '（同场推导）' : '');
      }
      case 'P0': {
        var ds = dd.stats();
        return M.nCh + ' 回 · ' + M.stats.mains + ' 段主线 · ' + (M.stats.branches + M.stats.twigs) + ' 条支线（具名 ' + M.stats.named + '）· 盘上画出 ' + ds.lines + ' 条';
      }
      case 'P1': case 'P2': {
        info = dd.lineInfo(String(target(id, p).hover));
        return (id === 'P1' ? '主线「' : '支线「') + info.label + '」· 第 ' + info.no0 + (info.no1 !== info.no0 ? '–' + info.no1 : '') + ' 回 · 跨 ' + info.span + ' 回 · ' + info.events + ' 事件 · ' + info.cast.length + ' 人 · 连线 ' + dd.stats().tethers;
      }
      case 'P3': {
        var c = s.cursor; ch = M.chapters[c] || {};
        var live = M.mains.concat(M.lines).filter(function (l) { return l.c0 <= c && l.c1 >= c; }).length;
        return '第 ' + ch.no + ' 回' + (ch.short ? ' · ' + ch.short : '') + ' · 进行中 ' + live + ' 条线 · ' + (M.chapterCast[c] || []).length + ' 人在场';
      }
      case 'K0': case 'K1': {
        var cs = C.stats(), c0 = charOf(cs.name) || {};
        var head = id === 'K1' ? p.top.name + ' → ' + cs.name + '（' + (p.otherKind || '联系') + '）' : cs.name + (c0.camp ? ' · ' + c0.camp : '') + (c0.role ? ' · ' + c0.role : '');
        return head + ' · ' + eventsOf(cs.name) + ' 事件 · ' + cs.total + ' 位联系' + (cs.derived && id === 'K0' ? '（同场推导）' : '');
      }
      case 'K2': {
        var ci = typeof C.eventInfo === 'function' ? C.eventInfo(p.k2.index) : null;
        var kline = ci ? '第 ' + ci.no + ' 回' + (ci.kind ? ' · ' + ci.kind : '') : textOf('.skc-card .sc-k');
        var title = ci ? ci.title : textOf('.skc-card .sc-t');
        var lit = d.querySelectorAll('.sky-compass .skc-sat.is-lit').length;
        return kline + ' · 「' + title + '」· 同场亮起 ' + lit + ' 位联系' + (p.k2.fallback ? '（无关键事件 · 取首事件）' : '');
      }
    }
    return '';
  }
  /* 收起态签上的一句短读数（抽屉的药丸签用；竖签只写帧名） */
  function brief(id, p) {
    var s = sst(), M = p.M, dd = disc(), C = comp(), gp, info;
    switch (id) {
      case 'C0': case 'C1': gp = groupingOf(s.group); return (gp ? gp.label : '分类') + ' · ' + ((app().atlas.skyView().camps || []).filter(function (c) { return c.members && c.members.length; }).length) + ' 团';
      case 'P0': return M.stats.mains + ' 段主线 · ' + (M.stats.branches + M.stats.twigs) + ' 条支线';
      case 'P1': case 'P2': info = dd.lineInfo(String(target(id, p).hover)); return info.label + ' · ' + info.span + ' 回 · ' + info.cast.length + ' 人';
      case 'P3': return '第 ' + (M.chapters[s.cursor] || {}).no + ' 回 · ' + (M.chapterCast[s.cursor] || []).length + ' 人在场';
      case 'K0': return C.stats().name + ' · ' + C.stats().total + ' 位联系';
      case 'K1': return p.top.name + ' → ' + C.stats().name;
      case 'K2': return (C.eventInfo ? '第 ' + C.eventInfo(p.k2.index).no + ' 回' : textOf('.skc-card .sc-k').split('·')[0].trim()) + ' · ' + (C.eventInfo ? C.eventInfo(p.k2.index).title : textOf('.skc-card .sc-t'));
    }
    return '';
  }
  function textOf(sel) { var e = d.querySelector(sel); return e ? e.textContent.trim() : '—'; }

  // ------------------------------------------------------------------ 深链：#sky= base64url(JSON {v, frame, snap, modes})
  function snapshot() { return SKY.snapshot(); }
  function enc(obj) {
    var bytes = new TextEncoder().encode(JSON.stringify(obj)), bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return g.btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function dec(str) {
    var b64 = String(str).replace(/-/g, '+').replace(/_/g, '/'); while (b64.length % 4) b64 += '=';
    var bin = g.atob(b64), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  function payloadOf(input) {
    var s = String(input == null ? '' : input).trim(), i = s.indexOf(HASH_KEY);
    if (i >= 0) s = s.slice(i + HASH_KEY.length);
    s = s.split('&')[0].split('#')[0];
    try { s = decodeURIComponent(s); } catch (e) {}
    try { var o = dec(s); return o && o.v === 1 ? o : null; } catch (e2) { return null; }
  }
  function baseUrl() { return g.location.href.split('#')[0]; }
  function link() { return baseUrl() + '#' + HASH_KEY + enc({ v: 1, frame: current(), snap: snapshot(), modes: modes() }); }
  function validate(s, p) {
    var miss = [], M = p.M, G = p.G, dd = disc();
    if (!s || typeof s !== 'object') return ['snapshot'];
    if (s.group && s.group !== BASE_GROUP && !(M.groupings || []).some(function (x) { return x.key === s.group; })) miss.push('group:' + s.group);
    if (s.compass && !(G.characters || []).some(function (c) { return c.name === s.compass; })) miss.push('compass:' + s.compass);
    if (s.plot && s.line != null && !(dd && dd.lineInfo(String(s.line)))) miss.push('line:' + s.line);
    if (s.plot && s.cursor != null && !(Math.floor(s.cursor) === s.cursor && s.cursor >= 0 && s.cursor < M.nCh)) miss.push('cursor:' + s.cursor);
    return miss;
  }
  function sameSnap(a, b) {
    function k(s) { return JSON.stringify([s.group || BASE_GROUP, !!s.plot, s.compass || null, s.plot ? (s.cursor == null ? null : s.cursor) : null, s.plot ? (s.line == null ? null : String(s.line)) : null]); }
    return k(a) === k(b);
  }
  function fresh() { var s = sst(); return s.mode === 'constellation' && !s.plot && !s.playing; }
  function applyModes(m) { if (!m) return; MODES.forEach(function (k) { if (typeof m[k] === 'boolean' && mode[k] !== m[k]) setMode(k, m[k]); }); }
  function finishLink(r) { linkResult = r; render(); return r; }
  function applyLink(input, onLoad) {
    var ps = payloadOf(input);
    setOn(true);
    if (!ps) { note('深链无法解析 · 保持当前视图'); return Promise.resolve(finishLink({ ok: false, reason: 'parse' })); }
    var p = plan();
    if (!p) { note('作品尚未就绪 · 深链未应用'); return Promise.resolve(finishLink({ ok: false, reason: 'no-model' })); }
    applyModes(ps.modes);
    var fr = ps.frame && frameOf(ps.frame) ? ps.frame : null;
    if (!ps.snap) {
      /* 样例链接只带帧：在本作里按同一确定性规则取景；该帧不可用就停在星座全景 */
      var f0 = fr || 'C0';
      return go(f0).then(function (r) {
        if (r.ok) { note(fr ? '已按帧 ' + fr + ' 的规则在本作取景' : '星座全景'); return finishLink({ ok: true, via: 'frame', frame: f0 }); }
        if (r.cancelled) return finishLink({ ok: false, reason: 'cancelled' });
        return go('C0').then(function () { note('帧 ' + f0 + ' 在本作不可用（' + (r.reason || r.error || '') + '）· 停在星座全景'); return finishLink({ ok: false, reason: 'frame-unavailable', frame: f0, fallback: 'C0' }); });
      });
    }
    var miss = validate(ps.snap, p);
    if (miss.length) {
      return go('C0').then(function () { note('深链对象不在当前作品 · 已停在星座全景，未替选其他记录'); return finishLink({ ok: false, reason: 'missing', missing: miss, fallback: 'C0' }); });
    }
    var my = ++seq; running = 'link'; frameId = null; frameSig = null;
    var steps = onLoad && fresh() ?
      [function () { SKY.apply(ps.snap); if (ps.snap.plot || ps.snap.compass) fly(FLY()); if (ps.snap.plot) fly(GROW()); return 0; }] : snapSteps(ps.snap);
    render();
    return run(steps, my).then(function (ok) {
      if (my === seq) running = null;
      if (!ok) return finishLink({ ok: false, reason: 'cancelled' });
      if (!fr || why(fr, p)) { note('深链已恢复'); return finishLink({ ok: true, via: 'state' }); }
      /* 帧态：快照不含悬停，重跑该帧补上悬停并标记；该帧在本作取到的对象与快照不同 → 按快照复原、不标帧 */
      return go(fr).then(function (r) {
        if (r.ok && sameSnap(snapshot(), ps.snap)) { note('深链已恢复 · ' + fr); return finishLink({ ok: true, via: 'frame', frame: fr }); }
        if (r.cancelled) return finishLink({ ok: false, reason: 'cancelled' });
        var my2 = ++seq; running = 'link';
        return run(snapSteps(ps.snap), my2).then(function (ok2) {
          if (my2 === seq) running = null;
          note('帧 ' + fr + ' 在本作取到的对象与深链不同 · 已按快照恢复');
          return finishLink(ok2 ? { ok: true, via: 'state', frame: null } : { ok: false, reason: 'cancelled' });
        });
      });
    }, function (err) {
      if (my === seq) running = null;
      errors.push(String(err && (err.stack || err.message) || err)); note('深链恢复失败 · ' + (err && err.message));
      return finishLink({ ok: false, reason: 'error', error: String(err && err.message || err) });
    });
  }
  /* 页面加载：等 cl:graph-ready 与 CLSky.model() 就绪，再等镜头静止（避免把入场中途的机位存成「剧情前机位」） */
  function whenSettled() {
    var t0 = now(), last = null, stable = 0;
    return new Promise(function (resolve) {
      (function tick() {
        var sc = scene(), ok = !!(model() && sc && sc.camera);
        if (ok) { var k = sc.camera.position.toArray().map(function (v) { return v.toFixed(1); }).join(','); stable = k === last ? stable + 1 : 0; last = k; }
        if ((ok && stable >= 2 && now() - t0 > 400) || now() - t0 > 6000) { resolve(ok); return; }
        g.setTimeout(tick, 150);
      })();
    });
  }

  // ------------------------------------------------------------------ 样例切换（导航 + sessionStorage 返回点；不改全局 graph、不写 data/）
  function readReturn() { try { var v = JSON.parse(g.sessionStorage.getItem(RETURN_KEY) || 'null'); return v && v.url ? v : null; } catch (e) { return null; } }
  function writeReturn(v) { try { g.sessionStorage.setItem(RETURN_KEY, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function clearReturn() { try { g.sessionStorage.removeItem(RETURN_KEY); } catch (e) {} }
  function dataParam() { try { return new URLSearchParams(g.location.search).get('data'); } catch (e) { return null; } }
  function sampleOf(file) { return SAMPLES.filter(function (s) { return s.file === file; })[0] || null; }
  function onSamplePage() { var rp = readReturn(); return !!(rp && rp.url !== baseUrl() && sampleOf(dataParam())); }
  function sampleUrl(file) {
    var q = new URLSearchParams(g.location.search);
    DROP_PARAMS.forEach(function (k) { q.delete(k); });
    if (q.get('sky') === 'plot') q.set('sky', '1');
    q.set('data', file);
    return g.location.origin + g.location.pathname + '?' + q.toString().replace(/%2F/gi, '/');
  }
  function checkAddress() {
    addr = dataParam() ? { ok: true, url: baseUrl() } :
      { ok: false, reason: '当前作品不是从地址（?data=）打开 · 切到样例后回不来，样例切换已禁用' };
  }
  function switchSample(file) {
    var s = sampleOf(file); if (!s) return false;
    if (dataParam() === file) { note('当前已是此样例'); render(); return false; }
    if (!onSamplePage()) {
      if (!addr.ok) { note(addr.reason); render(); return false; }
      var G = graph();
      if (!writeReturn({ url: baseUrl(), snap: snapshot(), frame: current(), modes: modes(), title: G && G.title || '', at: Date.now() })) { note('浏览器禁用了会话存储 · 无法保存返回点，切换已取消'); render(); return false; }
    }
    note('前往样例 · ' + s.label + ' · 当前作品未改动');
    g.location.assign(sampleUrl(file) + '#' + HASH_KEY + enc({ v: 1, frame: current() || 'C0', snap: null, modes: modes() }));
    return true;
  }
  function returnToWork() {
    var rp = readReturn(); if (!rp) { note('没有返回点'); render(); return false; }
    g.location.assign(rp.url + '#' + HASH_KEY + enc({ v: 1, frame: rp.frame || null, snap: rp.snap || null, modes: rp.modes || null }));
    return true;
  }

  // ------------------------------------------------------------------ 读图模式（body 类 + 宿主开关；关闭实验室全部复原）
  function modes() { return { notext: on && mode.notext, noglow: on && mode.noglow, gray: on && mode.gray, still: on && mode.still }; }
  function modeWhy(k) {
    var sc = scene();
    if (k === 'noglow' && !(sc && typeof sc.setGlow === 'function')) return '缺宿主 API：scene.setGlow';
    if (k === 'still' && !has('CLSky.setCalm')) return '缺宿主 API：CLSky.setCalm';
    return '';
  }
  function setModeRaw(k, v) {
    var sc = scene();
    if (k === 'noglow' && sc && typeof sc.setGlow === 'function') {
      if (v) { saved.glow = typeof sc.glow === 'function' ? sc.glow() : 1; sc.setGlow(0); } else sc.setGlow(saved.glow == null ? 1 : saved.glow);
    }
    if (k === 'still') {
      if (v) { saved.calm = sc && typeof sc.calm === 'function' ? !!sc.calm() : false; stopPlay(); SKY.setCalm(true); if (sc && sc.setCalm) sc.setCalm(true); }
      else { SKY.setCalm(false); if (sc && sc.setCalm) sc.setCalm(saved.calm); }
    }
    mode[k] = v; d.body.classList.toggle('skylab-' + k, v);
  }
  function setMode(name, v) {
    if (MODES.indexOf(name) < 0) return false;
    v = !!v;
    var w = modeWhy(name);
    if (v && w) { note(MODE_LABEL[name] + ' 不可用 · ' + w); render(); return modes(); }
    if (v) setOn(true);
    if (mode[name] !== v) setModeRaw(name, v);
    render(); return modes();
  }

  // ------------------------------------------------------------------ DOM（全部由本模块创建）
  function h(tag, attrs, kids) {
    var el = d.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === 'text') el.textContent = v; else if (k === 'cls') el.className = v; else el.setAttribute(k, v === true ? '' : v); });
    (kids || []).forEach(function (c) { if (c) el.appendChild(c); });
    return el;
  }
  function buildButton() {
    if (btn && btn.isConnected) return btn;
    var tools = $('skyTools'); if (!tools || !tools.parentNode) return null;
    btn = h('button', { type: 'button', cls: 'sky-icon sky-lab-btn', id: 'skyLabBtn', 'aria-pressed': 'false', 'aria-controls': 'skyLab', title: '预演实验室 · 故事板 / 读图模式 / 深链 / 样例' });
    btn.innerHTML = GLYPH + '<span>预演</span>';
    tools.parentNode.insertBefore(btn, tools);
    btn.addEventListener('click', function () { setOn(!on); });
    return btn;
  }
  function build() {
    if (root) return root;
    els.tag = h('button', { type: 'button', cls: 'skl-tag', 'aria-expanded': 'false', 'aria-controls': 'skyLabPanel', title: '展开预演实验室' },
      [h('span', { cls: 'skl-tag-name', text: '预演' }), els.tagFrame = h('b', { cls: 'skl-tag-frame', text: '—' }), els.tagBrief = h('span', { cls: 'skl-tag-brief' })]);
    els.fold = h('button', { type: 'button', cls: 'skl-fold', 'aria-label': '收起预演实验室', title: '收起' }, [h('i', { 'aria-hidden': 'true' })]);
    els.ret = h('button', { type: 'button', cls: 'skl-return', hidden: true, title: '回到切换样例之前的作品，并恢复当时的星空状态' }, [h('span', { cls: 'skl-stag', text: '样例' }), h('span', { text: '回到原作品' })]);
    var board = h('div', { cls: 'skl-board', role: 'group', 'aria-label': '故事板 · 9 帧' });
    els.ticks = {};
    GROUPS.forEach(function (gr) {
      var col = h('div', { cls: 'skl-ticks' });
      FRAMES.filter(function (f) { return f.id.charAt(0) === gr.key; }).forEach(function (f) {
        var b = h('button', { type: 'button', cls: 'skl-tick', 'data-frame': f.id, 'aria-pressed': 'false', title: f.id + ' · ' + f.q }, [h('span', { cls: 'skl-fid', text: f.id }), h('span', { cls: 'skl-fname', text: f.name })]);
        els.ticks[f.id] = b; col.appendChild(b);
      });
      board.appendChild(h('div', { cls: 'skl-group', 'data-g': gr.key }, [h('span', { cls: 'skl-glabel', text: gr.label }), col]));
    });
    els.cardId = h('b', { cls: 'skl-card-id', text: '选一帧' });
    els.q = h('p', { cls: 'skl-q', text: '每一帧回答一个读图问题，驱动的是真实星空' });
    els.a = h('p', { cls: 'skl-a' });
    var cardEl = h('div', { cls: 'skl-card', 'aria-live': 'polite' }, [els.cardId, els.q, els.a]);
    els.modes = {};
    var modeRow = h('div', { cls: 'skl-modes', role: 'group', 'aria-label': '读图模式（可叠加）' });
    MODES.forEach(function (k) { var b = h('button', { type: 'button', cls: 'skl-mode', 'data-mode': k, 'aria-pressed': 'false', title: MODE_HELP[k], text: MODE_LABEL[k] }); els.modes[k] = b; modeRow.appendChild(b); });
    els.copy = h('button', { type: 'button', cls: 'skl-copy', title: '复制当前状态的深链：新开页面恢复同一分类、剧情、回目、罗盘与读图模式', text: '复制深链' });
    els.disclose = h('button', { type: 'button', cls: 'skl-disclose', 'aria-expanded': 'false', 'aria-controls': 'skyLabSamples', text: '样例' });
    els.url = h('input', { cls: 'skl-url', type: 'text', readonly: true, 'aria-label': '当前状态深链', hidden: true });
    els.slist = h('ul', { cls: 'skl-slist', id: 'skyLabSamples', hidden: true });
    els.note = h('p', { cls: 'skl-note', role: 'status', 'aria-live': 'polite' });
    els.cover = h('p', { cls: 'skl-cover', hidden: true });
    els.panel = h('section', { cls: 'skl-panel', id: 'skyLabPanel', 'aria-label': '预演实验室' }, [
      h('header', { cls: 'skl-head' }, [h('span', { cls: 'skl-sigil', 'aria-hidden': 'true' }), h('span', { cls: 'skl-kicker', text: '预演' }), h('span', { cls: 'skl-en', text: 'LAB' }), els.fold]),
      els.ret, board, cardEl, h('div', { cls: 'skl-tools' }, [modeRow, h('div', { cls: 'skl-share' }, [els.copy, els.disclose])]), els.url, els.slist, els.cover, els.note]);
    root = h('aside', { id: 'skyLab', cls: 'sky-lab', 'data-open': 'true', 'data-layout': 'side', 'aria-label': '星空预演实验室', hidden: true }, [els.tag, els.panel]);
    d.body.appendChild(root);
    els.tag.addEventListener('click', function () { setOpen(true); });
    els.fold.addEventListener('click', function () { setOpen(false); });
    board.addEventListener('click', function (e) { var b = e.target.closest('[data-frame]'); if (b) go(b.getAttribute('data-frame'), 'ui'); });
    modeRow.addEventListener('click', function (e) { var b = e.target.closest('[data-mode]'); if (b && b.getAttribute('aria-disabled') !== 'true') setMode(b.getAttribute('data-mode'), b.getAttribute('aria-pressed') !== 'true'); });
    els.copy.addEventListener('click', copyLink);
    els.disclose.addEventListener('click', function () { samplesOpen = !samplesOpen; render(); });
    els.slist.addEventListener('click', function (e) { var b = e.target.closest('[data-file]'); if (b && b.getAttribute('aria-disabled') !== 'true') switchSample(b.getAttribute('data-file')); });
    els.ret.addEventListener('click', returnToWork);
    return root;
  }
  function copyLink() {
    var url = link(); els.url.value = url;
    function done(ok) {
      els.url.hidden = !!ok;
      if (!ok) { els.url.focus(); els.url.select(); }
      note(ok ? '深链已复制 · 新开页面即恢复此状态' : '剪贴板不可用 · 已选中链接，请手动复制');
      root.setAttribute('data-copy', ok ? 'ok' : 'manual'); render();
    }
    function fallback() { try { els.url.hidden = false; els.url.select(); return !!(d.execCommand && d.execCommand('copy')); } catch (e) { return false; } }
    try {
      if (g.navigator.clipboard && g.navigator.clipboard.writeText) g.navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(fallback()); });
      else done(fallback());
    } catch (e) { done(false); }
    return url;
  }
  function note(t) { lastNote = String(t || ''); if (els.note) els.note.textContent = lastNote; }
  function isDrawer() { return (g.innerWidth || 1200) <= 560; }
  function autoFold() { return (g.innerWidth || 1200) <= 1100; }   /* 窄 / 中屏：从栏里点一帧后收起，把舞台让出来（抽屉收成带读数的药丸签） */
  function setOn(v) {
    v = !!v; if (v === on) return on;
    on = v;
    if (on) { build(); open = true; layout(); }
    else {
      seq++; running = null; frameId = null; frameSig = null; card = null;
      clearSim();
      MODES.forEach(function (k) { if (mode[k]) setModeRaw(k, false); });
      samplesOpen = false;
    }
    render(); return on;
  }
  function setOpen(v) { open = !!v; layout(); render(); return open; }
  function rectOf(sel) { var e = d.querySelector(sel); if (!e) return null; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? r : null; }
  function layout() {
    if (!root) return;
    var H = g.innerHeight || 800, top = rectOf('.sky-top'), bottom = 0;
    [].forEach.call(d.querySelectorAll('.sky-bottom > *'), function (e) { var r = e.getBoundingClientRect(); if (r.width > 0 && r.height > 0 && !e.hidden) bottom = Math.max(bottom, H - r.top); });
    /* 窄屏宿主把悬停卡停靠在图例上方：药丸签再让到卡片之上（只读卡片位置，不碰它） */
    if (isDrawer()) { var sc = $('skyCard'); if (sc && !sc.hidden) { var cr = sc.getBoundingClientRect(); if (cr.height > 0 && cr.bottom > H * 0.55) bottom = Math.max(bottom, H - cr.top); } }
    root.style.setProperty('--skl-top', Math.round((top ? top.bottom : 60) + 10) + 'px');
    root.style.setProperty('--skl-bottom', Math.round(Math.max(16, bottom + 10)) + 'px');
  }
  /* 宿主留边：宿主提供 CLSky.setInset 时，把右缘栏 / 竖签占去的宽度告诉它（罗盘与剧情取景让位）。
     底部抽屉不报底边：实测把 27% 高度让出去，窄屏罗盘会把关系对象挤到晶体上；抽屉是临时态，点帧即收成药丸签。
     仍有遮挡（宿主未提供，或让位不足）→ 在栏内如实写出 */
  function applyInset() {
    var ins = { right: 0, bottom: 0 };
    if (on && root && !root.hidden && !isDrawer()) { var r = (open ? els.panel : els.tag).getBoundingClientRect(); ins.right = Math.round((g.innerWidth || 0) - r.left); }
    var key = ins.right + ',' + ins.bottom;
    if (key === insetKey) return;
    insetKey = key;
    if (typeof SKY.setInset === 'function') { try { SKY.setInset(ins); } catch (e) { errors.push('setInset: ' + (e && e.message)); } }
  }
  function coverCheck() {
    cover = 0;
    if (!on || !open || sst().mode !== 'compass' || !comp() || !comp()._layout) return 0;
    var L = comp()._layout(), r = els.panel.getBoundingClientRect();
    (L && L.sats || []).forEach(function (s) { if (s.x + 60 > r.left && s.x - 60 < r.right && s.y + 16 > r.top && s.y - 18 < r.bottom) cover++; });
    return cover;
  }
  function showCard() {
    var sh = running && frameOf(running) ? running : current(), f;
    if (card && !running && card.why && (!sh || sh === card.id)) { f = frameOf(card.id); els.cardId.textContent = f.id + ' · ' + f.name; els.q.textContent = f.q; segs(els.a, card.why); root.setAttribute('data-card', 'disabled'); return card.id; }
    if (sh) {
      f = frameOf(sh); els.cardId.textContent = f.id + ' · ' + f.name; els.q.textContent = f.q;
      segs(els.a, running === sh ? '驱动星空中…' : (lastAnswer[sh] || '')); root.setAttribute('data-card', running === sh ? 'running' : 'live'); return sh;
    }
    if (frameId || running === 'link') { els.cardId.textContent = running === 'link' ? '深链' : '自由浏览'; els.q.textContent = running === 'link' ? '正在按深链恢复星空状态' : '画面已偏离故事板帧；深链仍记录完整状态'; segs(els.a, ''); root.setAttribute('data-card', 'free'); return null; }
    root.setAttribute('data-card', 'idle'); return null;
  }
  /* 读数按「 · 」分段、段内不断行：换行只落在分隔处，数字不会和单位拆开 */
  var segKey = null;
  function segs(el, text) {
    text = String(text || ''); if (segKey === text && el.childNodes.length) return; segKey = text;
    var kids = [];
    text.split(/\s*·\s*/).filter(Boolean).forEach(function (t, i) { if (i) kids.push(d.createTextNode(' ')); kids.push(h('span', { cls: 'skl-seg', text: t })); });
    el.replaceChildren.apply(el, kids);
  }
  function queueRender() { if (renderQ) return; renderQ = true; g.setTimeout(function () { renderQ = false; render(); }, 30); }
  function render() {
    if (btn) btn.setAttribute('aria-pressed', String(on));
    if (!root) return;
    root.hidden = !on;
    if (!on) { applyInset(); return; }
    layout();
    var drawer = isDrawer();
    root.setAttribute('data-open', String(open));
    root.setAttribute('data-layout', drawer ? 'drawer' : 'side');
    els.tag.setAttribute('aria-expanded', String(open));
    els.fold.setAttribute('aria-label', open ? '收起预演实验室' : '展开预演实验室');
    var p = plan(), cur = current();
    FRAMES.forEach(function (f) {
      var b = els.ticks[f.id], w = why(f.id, p);
      b.setAttribute('aria-pressed', String(cur === f.id || running === f.id));
      b.classList.toggle('is-running', running === f.id);
      b.setAttribute('aria-disabled', w ? 'true' : 'false');
      b.title = f.id + ' · ' + f.q + (w ? '（' + w + '）' : '');
    });
    var shown = showCard(), fshown = shown && frameOf(shown);
    els.tagFrame.textContent = shown || '—';
    els.tagBrief.textContent = !fshown ? '' : drawer ? (running === shown ? '驱动中…' : lastBrief[shown] || fshown.name) : fshown.name;
    var m = modes();
    MODES.forEach(function (k) { var b = els.modes[k], w = modeWhy(k); b.setAttribute('aria-pressed', String(!!m[k])); b.setAttribute('aria-disabled', w ? 'true' : 'false'); b.title = MODE_HELP[k] + (w ? '（' + w + '）' : ''); });
    els.disclose.setAttribute('aria-expanded', String(samplesOpen));
    els.slist.hidden = !samplesOpen;
    if (samplesOpen) renderSamples();
    var sample = onSamplePage();
    els.ret.hidden = !sample;
    root.setAttribute('data-sample', String(sample));
    if (els.note.textContent !== lastNote) els.note.textContent = lastNote;
    var n = coverCheck();
    els.cover.hidden = !n;
    if (n) els.cover.textContent = '本栏遮住 ' + n + ' 位联系对象 · 收起本栏即可看全';
    applyInset();
  }
  var samplesKey = '';
  function renderSamples() {
    var G = graph(), here = dataParam(), sample = onSamplePage(), cur = sampleOf(here), rows = [];
    var title = G ? (G.title || '未命名') : '未载入', key = JSON.stringify([title, here, sample, addr.ok, addr.reason || '']);
    if (key === samplesKey && els.slist.childNodes.length) return;
    samplesKey = key;
    rows.push(h('li', { cls: 'skl-srow is-current' }, [h('span', { cls: 'skl-stag' + (cur ? '' : ' is-work'), text: cur ? '样例' : '作品' }), h('span', { cls: 'skl-sname', text: '当前 · ' + title })]));
    SAMPLES.forEach(function (s) {
      var w = here === s.file ? '当前已是此样例' : (!sample && !addr.ok) ? addr.reason : '';
      rows.push(h('li', { cls: 'skl-srow' }, [h('button', { type: 'button', cls: 'skl-sample', 'data-file': s.file, 'aria-disabled': w ? 'true' : 'false', title: w || ('切到样例「' + s.label + '」· 当前作品不改动，可一键返回') },
        [h('span', { cls: 'skl-stag', text: '样例' }), h('span', { cls: 'skl-sname', text: s.label }), h('small', { text: s.hint })])]));
    });
    if (!sample && !addr.ok) rows.push(h('li', { cls: 'skl-sreason', text: addr.reason }));
    els.slist.replaceChildren.apply(els.slist, rows);
  }

  // ------------------------------------------------------------------ 生命周期
  function onGraph() {
    if (!SKY.enabled() || !model()) return;
    buildButton(); build();
    seq++; running = null; frameId = null; frameSig = null; card = null; planCache = null; lastAnswer = {}; samplesKey = '';
    checkAddress();
    var rp = readReturn(); if (rp && rp.url === baseUrl()) clearReturn();
    if (pendingLink) {
      var l = pendingLink; pendingLink = null; setOn(true);
      running = 'link'; render();
      whenSettled().then(function (ok) { running = null; if (ok) return applyLink(l, true); note('星空未就绪 · 深链未应用'); render(); });
    }
    layout(); render();
  }
  d.addEventListener('cl:graph-ready', onGraph);
  d.addEventListener('cl:sky-plot', queueRender);
  d.addEventListener('cl:sky-compass', queueRender);
  ['click', 'keyup', 'input', 'pointerup'].forEach(function (t) { d.addEventListener(t, function () { if (on) queueRender(); }, true); });
  g.addEventListener('resize', function () { if (!on) return; layout(); render(); });
  g.addEventListener('hashchange', function () { if (g.location.hash.indexOf('#' + HASH_KEY) === 0 && model()) applyLink(g.location.hash, false); });
  /* 用户在实验室外的任何新动作都让未完成的帧步骤失效 */
  function outside(t) { return root && !root.contains(t) && !(btn && btn.contains(t)); }
  d.addEventListener('pointerdown', function (e) { if (running && outside(e.target)) cancel('检测到新的操作 · 未完成的帧步骤已作废'); }, true);
  d.addEventListener('keydown', function (e) { if (running && outside(e.target) && !/^(Shift|Control|Alt|Meta)$/.test(e.key)) cancel('检测到新的操作 · 未完成的帧步骤已作废'); }, true);
  if (g.location.hash.indexOf('#' + HASH_KEY) === 0) pendingLink = g.location.hash;

  g.CLSkyLab = {
    go: function (id) { return go(id); },
    frames: function () {
      var p = plan();
      return FRAMES.map(function (f) {
        var w = why(f.id, p), t = !w && p ? target(f.id, p) : null;
        return { id: f.id, group: f.id.charAt(0), name: f.name, question: f.q, available: !w, reason: w || null, target: t, answer: lastAnswer[f.id] || null };
      });
    },
    current: current, link: link, applyLink: function (s) { return applyLink(s, false); }, modes: modes, setMode: setMode,
    open: function (v) { setOn(v !== false); return on; }, fold: function (v) { setOn(true); return setOpen(v === false); },
    samples: function () { return SAMPLES.map(function (s) { return { file: s.file, label: s.label, hint: s.hint, sample: true }; }); },
    switchSample: switchSample, returnToWork: returnToWork,
    stats: function () {
      return { built: !!root, on: on, visible: !!(root && !root.hidden), open: open, layout: isDrawer() ? 'drawer' : 'side', frame: current(), running: running, token: seq,
        modes: modes(), note: lastNote, link: linkResult, address: { ok: addr.ok, reason: addr.reason || null },
        sample: { page: onSamplePage(), current: dataParam(), returnPoint: !!readReturn() },
        inset: { api: typeof SKY.setInset === 'function', key: insetKey }, cover: cover, degraded: Object.keys(degraded), interrupts: interrupts, errors: errors.slice(-5) };
    }
  };
  if (model()) onGraph();
})(window);
