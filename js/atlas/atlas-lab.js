/**
 * @role component
 * @owns js/atlas/atlas-lab.js
 * @contract v90 · F6 预演实验室（briefs/v90/PLAN.md §2 F6；briefs/v80/THREE-ATLAS-VISUAL-SPEC.md §3/§5/§7）
 *
 * 故事板导演（A0–A3 / G0–G3 / D0–D3）· 读图模式（收字/关光/灰阶/静止）· PreviewState 深链 · 样例切换。
 * 纪律：只经公开 API 驱动真实舞台（CLAtlasPreview / CLApp.atlas / CLApp.scene() / CLAtlasState /
 * HUD 既有控件的点击与 change 语义）；不猴补别人的对象；不写 data/、不写作品缓存、不触发分析；
 * 不私开 requestAnimationFrame，帧间等待只用一次性 setTimeout，且随 token 失效。
 * 缺失的宿主能力做可见降级（按钮 aria-disabled + 原因），需求见 reports/v90/F6-host.patch.md。
 */
(function (g) {
  'use strict';
  var d = g.document, S = g.CLAtlasState;
  if (!d || !d.body || !S) return;

  var RETURN_KEY = 'castline.lab.return', FIELD = '散星', KEY_KINDS = ['转折', '高燃'];
  var MODE_NAMES = ['notext', 'noglow', 'gray', 'still'];
  var MODE_LABEL = { notext: '收字', noglow: '关光', gray: '灰阶', still: '静止' };
  var MODE_HELP = {
    notext: '收起文字：隐藏证据层、说明字幕、账本与星名副行，只留图谱名、章号、实体名、轴名与状态词',
    noglow: '关光：关闭 SVG/DOM 光晕与阴影（WebGL 泛光暂无宿主开关，见报告）',
    gray: '灰阶：舞台与图层去色，检验状态/方向/选中/未知不靠颜色',
    still: '静止：与控制台「静止」同一开关，取消自动旋转与过渡，直接落终态'
  };
  var GROUPS = [{ atlas: 'annulus', key: 'A', label: '年轮' }, { atlas: 'gem', key: 'G', label: '双晶' }, { atlas: 'domains', key: 'D', label: '星域' }];
  var FRAMES = [
    { id: 'A0', atlas: 'annulus', name: '全景', q: '全书几条主线、几条支线，哪里还没收束' },
    { id: 'A1', atlas: 'annulus', name: '追线', q: '哪条是主线、它从哪章到哪章' },
    { id: 'A2', atlas: 'annulus', name: '局部事件', q: '这条线第一个关键事件落在哪一章' },
    { id: 'A3', atlas: 'annulus', name: '证据', q: '这个事件的原文依据是什么' },
    { id: 'G0', atlas: 'gem', name: '入晶', q: '全书咖位最高的是谁、上冠下锥各读什么' },
    { id: 'G1', atlas: 'gem', name: '读面', q: '他在叙事里的戏份、跨度与弧光有多大' },
    { id: 'G2', atlas: 'gem', name: '对照', q: '与同阵营次位者相比，强弱落在哪几维' },
    { id: 'G3', atlas: 'gem', name: '取证', q: '他最强的一维是什么、依据在哪' },
    { id: 'D0', atlas: 'domains', name: '星域全景', q: '分几派、各多少人、关系有多密' },
    { id: 'D1', atlas: 'domains', name: '群内', q: '最大的阵营里有哪些人' },
    { id: 'D2', atlas: 'domains', name: '类型边', q: '他最强的一条关系是什么类型' },
    { id: 'D3', atlas: 'domains', name: '追人', q: '这条关系另一端的人是什么样' }
  ];
  var SAMPLES = [
    { file: 'data/sample-saga.json', label: '中篇', hint: 'saga' },
    { file: 'data/sample-mid.json', label: '群像', hint: 'mid' },
    { file: 'data/sample-large.json', label: '长篇 184 人', hint: 'large' },
    { file: 'data/sample-focus.json', label: '聚焦', hint: 'focus' }
  ];
  var DROP_PARAMS = ['data', 'demo', 'lib', 'sel', 'view', 'api', 'onboard'];

  var root = null, els = {}, seq = 0, running = null, frameId = null, frameSig = null, planCache = null;
  var lab = { notext: false, noglow: false, gray: false };
  var open = null, autoFold = false, labSearch = false, labHold = false, labRelation = false, wasPreview = false;
  var urlGraph = null, urlGraphSeen = false, addr = { state: 'pending', ok: false, reason: '核对作品地址中…' };
  var pendingLink = null, linkResult = null, lastNote = '', errors = [], samplesOpen = false, renderQueued = false;
  var lastAttr = null, lastAnswer = {}, interrupts = 0;

  // ------------------------------------------------------------------ 公开 API 访问器（只读取、只调用）
  function app() { return g.CLApp || null; }
  function PV() { return g.CLAtlasPreview || null; }
  function graph() { var a = app(); return a && a.graph ? a.graph() : null; }
  function story() { var a = app(); return a && a.story ? a.story() : null; }
  function scene() { var a = app(); return a && a.scene ? a.scene() : null; }
  function bridge() { var a = app(); return a && a.atlas ? a.atlas : null; }
  function $(id) { return d.getElementById(id); }
  function copy(x) { return x == null ? x : JSON.parse(JSON.stringify(x)); }
  function eid(x) {
    if (!x) return null;
    if (x.id != null && x.id !== '') return String(x.id);
    if (x.entityId != null && x.entityId !== '') return String(x.entityId);
    return x.name != null ? String(x.name) : null;
  }
  function eventId(e) { if (!e) return null; if (e.id != null && e.id !== '') return String(e.id); if (e.entityId != null && e.entityId !== '') return String(e.entityId); return 'order:' + e.order; }
  function lineKey(t) { return t ? String(t.sourceId != null && t.sourceId !== '' ? t.sourceId : t.id) : null; }
  function relKey(r) { return r ? String(r.id != null && r.id !== '' ? r.id : r.entityId != null && r.entityId !== '' ? r.entityId : [r.a, r.b, r.kind || ''].join('|')) : null; }
  function campKey(name) { return 'group:name:' + encodeURIComponent(name); }
  function chap(e) { var c = String(e && e.chapter || '未分章'), m = /^(第[^章\s]{1,6}[章回])/.exec(c); return m ? m[1] : c.length > 8 ? c.slice(0, 8) + '…' : c; }
  function charByName(name) { var G = graph(); return G && (G.characters || []).filter(function (c) { return c.name === name; })[0] || null; }
  function charById(id) { var G = graph(); return G && id != null && (G.characters || []).filter(function (c) { return eid(c) === String(id) || String(c.entityId) === String(id); })[0] || null; }
  function evidenceCard() { return $('aphEvidenceCard'); }
  function evidenceOpen() { var c = evidenceCard(); return !!(c && !c.hidden); }
  function localOpen() { return !!(g.CLAtlasLocalGraph && CLAtlasLocalGraph.isOpen && CLAtlasLocalGraph.isOpen()); }
  function narrow() { return g.innerWidth <= 480; }
  function wide() { return g.innerWidth > 1100; }

  function has(path) {
    if (path.charAt(0) === '#') return !!$(path.slice(1));
    var parts = path.split('.'), o = g;
    if (parts[0] === 'scene') { o = scene(); parts.shift(); }
    for (var i = 0; i < parts.length; i++) { if (o == null) return false; o = o[parts[i]]; }
    return typeof o === 'function' || (o != null && typeof o === 'object');
  }
  var NEED = {
    base: ['CLAtlasPreview.open', 'CLAtlasPreview.setAtlas', 'CLAtlasPreview.pause', 'CLApp.atlas.state', 'CLAtlasState.dispatch'],
    line: ['CLAtlasPreview.chooseLine'], cursor: ['CLAtlasPreview.setCursor', 'CLApp.atlas.restore'],
    evidence: ['CLAtlasPreview.evidence', '#aphEvidenceCard'], character: ['CLAtlasPreview.chooseCharacter', 'scene.gemStageState'],
    face: ['#aphFace', 'scene.face'], peer: ['#aphPeer'], lens: ['#aphLens'], camp: ['CLAtlasLocalGraph.stats'],
    relation: ['scene.setSearchSet'], still: ['#aphReduced']
  };
  var FRAME_NEED = { A0: ['base'], A1: ['base', 'line'], A2: ['base', 'line', 'cursor'], A3: ['base', 'line', 'cursor', 'evidence'],
    G0: ['base', 'character', 'face', 'peer'], G1: ['base', 'character', 'face', 'peer'], G2: ['base', 'character', 'face', 'peer'], G3: ['base', 'character', 'face', 'peer', 'evidence'],
    D0: ['base', 'lens'], D1: ['base', 'lens', 'camp'], D2: ['base', 'lens', 'relation'], D3: ['base', 'lens', 'relation', 'character', 'face', 'peer'] };
  function missingApi(id) {
    var out = [];
    (FRAME_NEED[id] || ['base']).forEach(function (k) { NEED[k].forEach(function (p) { if (!has(p) && out.indexOf(p) < 0) out.push(p); }); });
    return out;
  }

  // ------------------------------------------------------------------ 时间：只用令牌时长；静止/低动效/低档直接落终态
  function quiet() {
    try { if (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) return true; } catch (e) {}
    try { if (S.get().reduced) return true; } catch (e2) {}
    try { if (g.CLOrbit3DTier && CLOrbit3DTier.get() === 'low') return true; } catch (e3) {}
    return false;
  }
  function dur(n) {
    if (!n || quiet()) return 0;
    var v = String(g.getComputedStyle(d.documentElement).getPropertyValue('--cl-atlas-dur-' + n) || '').trim();
    var ms = /ms$/.test(v) ? parseFloat(v) : /s$/.test(v) ? parseFloat(v) * 1000 : NaN;
    return isFinite(ms) ? ms : [0, 220, 360, 780][n] || 0;
  }
  function sleep(ms) { return new Promise(function (r) { if (!ms) r(); else g.setTimeout(r, ms); }); }

  // ------------------------------------------------------------------ 确定性选取：同一作品同一结果，不按下标替选
  function plan() {
    var G = graph(), T = story(); if (!G) return null;
    if (planCache && planCache.G === G && planCache.T === T) return planCache;
    var p = { G: G, T: T }, threads = T && T.threads || [], chars = G.characters || [], events = G.events || [];
    var mains = threads.filter(function (t) { return t.kind === 'main'; }), pool = mains.length ? mains : threads;
    p.mains = mains.length; p.branches = threads.length - mains.length;
    p.line = null; pool.forEach(function (t) { if (!p.line || (t.events || []).length > (p.line.events || []).length) p.line = t; });
    p.lineIsMain = mains.length > 0;
    p.eventIndex = null; p.eventIsKey = false;
    if (p.line) {
      var idx = (p.line.events || []).filter(function (i) { return Number.isInteger(i) && events[i]; }).sort(function (a, b) { return a - b; });
      var key = idx.filter(function (i) { return KEY_KINDS.indexOf(events[i].kind) >= 0; })[0];
      p.eventIndex = key != null ? key : idx.length ? idx[0] : null; p.eventIsKey = key != null;
      p.lineFrom = idx.length ? events[idx[0]] : null; p.lineTo = idx.length ? events[idx[idx.length - 1]] : null; p.lineN = idx.length;
    }
    var known = chars.filter(function (c) { return c.importanceKnown !== false && typeof c.importance === 'number' && isFinite(c.importance); });
    p.top = null; known.forEach(function (c) { if (!p.top || c.importance > p.top.importance) p.top = c; });
    p.peer = null;
    if (p.top && p.top.camp && p.top.camp !== FIELD) known.forEach(function (c) { if (c !== p.top && c.camp === p.top.camp && (!p.peer || c.importance > p.peer.importance)) p.peer = c; });
    var camps = (G.camps || []).filter(function (c) { return c && c.name && c.name !== FIELD && (c.members || []).length; });
    p.camps = camps.length; p.camp = null; camps.forEach(function (c) { if (!p.camp || c.members.length > p.camp.members.length) p.camp = c; });
    var rels = p.top ? (G.relations || []).filter(function (r) { return r && (r.a === p.top.name || r.b === p.top.name); }) : [];
    var provided = rels.filter(function (r) { return r.strengthProvided !== false && typeof r.strength === 'number' && isFinite(r.strength); });
    p.relProvided = provided.length > 0; p.rel = null;
    (p.relProvided ? provided : rels.slice(0, 1)).forEach(function (r) { if (!p.rel || r.strength > p.rel.strength) p.rel = r; });
    p.other = p.rel ? charByName(p.rel.a === p.top.name ? p.rel.b : p.rel.a) : null;
    var chapters = Object.create(null); events.forEach(function (e) { chapters[String(e.chapter || '')] = 1; }); p.chapters = Object.keys(chapters).length;
    planCache = p; return p;
  }
  function unavailable(id, p) {
    var miss = missingApi(id); if (miss.length) return '缺宿主 API：' + miss.join('、');
    if (!p) return '尚未载入作品';
    var grp = id.charAt(0);
    if (grp === 'A' && id !== 'A0' && !p.line) return '该作品没有可追的剧情线';
    if ((id === 'A2' || id === 'A3') && p.eventIndex == null) return '这条线没有可定位的事件';
    if (grp === 'G' && !p.top) return '咖位未提供 · 不按顺序替选角色';
    if (id === 'G2' && !p.peer) return '同阵营没有第二位已知咖位者 · 不生成对照';
    if (id === 'D1' && !p.camp) return '没有可展开的阵营成员';
    if ((id === 'D2' || id === 'D3') && !p.top) return '咖位未提供 · 无从选关系';
    if ((id === 'D2' || id === 'D3') && !p.rel) return p.top.name + ' 没有记录在案的关系';
    if (id === 'D3' && !p.other) return '关系另一端不在角色表中';
    return '';
  }
  function frameOf(id) { return FRAMES.filter(function (f) { return f.id === id; })[0] || null; }
  function targetOf(id, p) {
    var t = { frame: id, view: null, line: null, cursor: null, evidence: null, character: null, peer: null, face: 'top', camp: null, relation: null, lens: 'camps', unfolded: false };
    switch (id) {
      case 'A0': t.view = 'annulus'; break;
      case 'A1': t.view = 'annulus'; t.line = p.line; break;
      case 'A2': t.view = 'annulus'; t.line = p.line; t.cursor = p.eventIndex; break;
      case 'A3': t.view = 'annulus'; t.line = p.line; t.cursor = p.eventIndex; t.evidence = { type: 'event', index: p.eventIndex }; break;
      case 'G0': t.view = 'gem'; t.character = p.top; break;
      case 'G1': t.view = 'gem'; t.character = p.top; t.face = 'under'; break;
      case 'G2': t.view = 'gem'; t.character = p.top; t.peer = p.peer; break;
      case 'G3': t.view = 'gem'; t.character = p.top; t.evidence = { type: 'attr' }; break;
      case 'D0': t.view = 'domains'; break;
      case 'D1': t.view = 'domains'; t.camp = p.camp; break;
      case 'D2': t.view = 'domains'; t.relation = p.rel; break;
      case 'D3': t.view = 'domains'; t.relation = p.rel; t.character = p.other; break;
    }
    return t;
  }

  // ------------------------------------------------------------------ 舞台动作（每一步幂等、同步；返回下一拍等待的时长档）
  function hideEvidence() { var b = $('aphEvidenceClose'); if (evidenceOpen() && b) b.click(); }
  function setLens(value) {
    var el = $('aphLens'); if (!el || S.get().lens === value) return;
    el.value = value; el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function clearCursor() {
    var br = bridge(), snap = br.state();
    snap.chapter = null;
    if (snap.orbit) { snap.orbit = copy(snap.orbit); snap.orbit.focusEv = -1; }
    if (g.CLDomainsInteract && CLDomainsInteract.getSelection) snap.domains = CLDomainsInteract.getSelection();
    br.restore(snap);
    S.dispatch({ type: 'cursor', index: null });
  }
  function closeLocal() { if (localOpen()) PV().back(); }
  function prepare(t) {
    var pv = PV(), st = S.get(), sc = scene(), br = bridge();
    pv.pause();
    if (labHold && sc && sc.hoverAttr) sc.hoverAttr(null);
    labHold = false;
    hideEvidence();
    if (br.state().unfolded && !t.unfolded) br.closeUnfold();
    if (labSearch && sc && sc.setSearchSet) sc.setSearchSet(null);
    labSearch = false;
    if (labRelation && typeof br.relation === 'function') br.relation(null);
    labRelation = false;
    if (st.cursor != null && t.cursor !== st.cursor) clearCursor();
    if (st.lens !== t.lens && t.lens === 'camps') setLens('camps');
    if (localOpen() && !t.camp) closeLocal();
    return 0;
  }
  function toAnnulus(t) {
    var st = S.get(), changed = st.view !== 'annulus', sel = st.selected;
    var keep = t.line && sel && sel.type === 'line';
    if (sel && !keep) S.dispatch({ type: 'select', entity: null });
    if (changed || (sel && !keep)) PV().setAtlas('annulus', changed);
    return changed && t.line ? 3 : 0;
  }
  function pickLine(t) {
    var sel = S.get().selected;
    if (sel && sel.type === 'line' && (sel.runtimeId === t.line.id || sel.id === lineKey(t.line)) && S.get().view === 'annulus') return 0;
    PV().chooseLine(t.line.id); return 2;
  }
  function pickCursor(t) { if (S.get().cursor === t.cursor) return 0; PV().setCursor(t.cursor); return 2; }
  function toDomains(t) {
    var st = S.get(), changed = st.view !== 'domains';
    if (st.selected) S.dispatch({ type: 'select', entity: null });
    if (changed || st.selected) PV().setAtlas('domains', changed);
    return changed && (t.camp || t.relation) ? 3 : 0;
  }
  function expandCamp(t) {
    var c = t.camp, badge = d.querySelector('.cl-camp-halo__badge[data-camp-id="' + campKey(c.name).replace(/"/g, '\\"') + '"]');
    var seen = Object.create(null), members = (c.members || []).filter(function (n) { if (typeof n !== 'string' || !n || seen[n]) return false; seen[n] = 1; return true; });
    g.dispatchEvent(new CustomEvent('cl:atlas-camp', { detail: { id: badge ? badge.getAttribute('data-camp-id') : campKey(c.name), name: c.name, members: members } }));
    return 0;
  }
  function selectRelation(t) {
    var r = t.relation, sc = scene(), br = bridge();
    S.dispatch({ type: 'select', entity: { type: 'relation', id: relKey(r), name: r.a + ' — ' + r.b, a: r.a, b: r.b, kind: r.kind || null } });
    /* 单边高亮要宿主 CLApp.atlas.relation（host.patch P2）；现阶段以两端星强制点亮兜底。 */
    if (br && typeof br.relation === 'function' && br.relation(relKey(r))) labRelation = true;
    if (sc && sc.setSearchSet) { sc.setSearchSet([r.a, r.b]); labSearch = true; }
    return t.character ? 2 : 0;
  }
  function dropPeerState(t) {
    var st = S.get(), want = t.peer ? t.peer.name : null, sc = scene(), gs = sc.gemStageState();
    var sameStage = st.view === 'gem' && gs && gs.on && gs.name === t.character.name;
    if (!sameStage && st.peer && st.peer !== want) { S.dispatch({ type: 'peer', id: null }); var el = $('aphPeer'); if (el) el.value = ''; }
    return 0;
  }
  function toCharacter(t) {
    var c = t.character, st = S.get(), sc = scene(), gs = sc.gemStageState();
    if (st.view === 'gem' && gs && gs.on && gs.name === c.name && st.selected && st.selected.type === 'character' && st.selected.id === eid(c)) return 0;
    PV().chooseCharacter(c.id != null && c.id !== '' ? c.id : c.name);
    return 3;
  }
  function ensurePeer(t) {
    var want = t.peer ? t.peer.name : null, el = $('aphPeer');
    if ((S.get().peer || null) === want) return 0;
    el.value = want || ''; el.dispatchEvent(new Event('change', { bubbles: true }));
    return 2;
  }
  function ensureFace(t) {
    var sc = scene(), b = $('aphFace');
    if (S.get().view !== 'gem' || sc.face() === t.face) return 0;
    b.click(); return 3;
  }
  function topAttr(gm) {
    var best = null;
    (gm && gm.attr || []).forEach(function (a) { if (a && a.known && typeof a.score === 'number' && (!best || a.score > best.score)) best = a; });
    return best;
  }
  function showEvidence(t) {
    var pv = PV(), sc = scene();
    if (t.evidence.type === 'event') { pv.evidence({ type: 'event', index: t.evidence.index }); return 0; }
    var gm = sc.gemModel ? sc.gemModel() : null, best = topAttr(gm);
    lastAttr = best ? { key: best.key, score: best.score, evidence: (best.evidence || []).length } : null;
    if (!best) { pv.evidence({ name: t.character.name }); note('该角色没有已知属性维 · 只展示人物依据，不补默认分'); return 0; }
    pv.evidence({ type: 'attr', id: best.key });
    if (sc.hoverAttr) { sc.hoverAttr(best.key); labHold = true; }
    return 0;
  }
  function applyLensStep(t) { setLens(t.lens); return 0; }
  /* 非双晶帧也把对照人写成目标值：帧是完整状态，不能把上一帧的 peer 带进来；深链则按记录恢复。
     只改状态与下拉值，不派发 change（change 会把舞台切进双晶）。 */
  function syncPeerState(t) {
    var want = t.peer ? t.peer.name : null, el = $('aphPeer');
    if ((S.get().peer || null) !== want) { S.dispatch({ type: 'peer', id: want }); if (el) el.value = want || ''; }
    return 0;
  }
  function unfoldStep(t) { var br = bridge(); if (!br.state().unfolded) br.unfold(t.line ? t.line.id : null); return 0; }
  function stepsFor(t) {
    var s = [prepare];
    if (t.view === 'annulus') s.push(toAnnulus);
    if (t.view === 'domains') s.push(toDomains);
    if (t.line) s.push(pickLine);
    if (t.camp) s.push(expandCamp);
    if (t.relation) s.push(selectRelation);
    if (t.character) s.push(dropPeerState, toCharacter, ensurePeer, ensureFace);
    else s.push(syncPeerState);
    if (t.cursor != null) s.push(pickCursor);
    if (t.lens && t.lens !== 'camps') s.push(applyLensStep);
    if (t.evidence) s.push(showEvidence);
    if (t.unfolded) s.push(unfoldStep);
    return s;
  }
  /* 每步同步执行并记下舞台签名；等待期间签名被别人改动（用户拖游标、点星、按键）即视为接管，
     余下步骤作废——旧回调不得把视图拉回（规格 §4.2-1）。 */
  function run(t, my) {
    var steps = stepsFor(t), i = 0, mark = null;
    function next() {
      if (my !== seq) return Promise.resolve(false);
      if (mark !== null && sig() !== mark) { seq++; running = null; interrupts++; note('检测到新的操作 · 未完成的帧步骤已作废'); queueRender(); return Promise.resolve(false); }
      if (i >= steps.length) return Promise.resolve(true);
      var wait = steps[i++](t); mark = sig();
      return sleep(typeof wait === 'number' && i < steps.length ? dur(wait) : 0).then(next);
    }
    try { return next(); } catch (e) { return Promise.reject(e); }
  }

  // ------------------------------------------------------------------ 导演：帧切换先让上一帧 token 失效
  function ensurePreview() {
    var pv = PV(); if (!pv || !pv.active || !pv.active()) return false;
    if (!S.get().preview) pv.open();
    return !!S.get().preview;
  }
  function cancel() { if (running) { seq++; running = null; queueRender(); } }
  function sig() {
    var st = S.get(), sc = scene(), sel = st.selected;
    return JSON.stringify([st.view, sel && sel.type, sel && sel.id, st.cursor, st.peer || null, st.lens, st.view === 'gem' && sc && sc.face ? sc.face() : 'top', localOpen(), evidenceOpen()]);
  }
  function current() { return frameId && frameSig === sig() ? frameId : null; }
  function go(id, via) {
    var f = frameOf(id); if (!f) return Promise.resolve({ ok: false, id: id, reason: '未知帧' });
    var my = ++seq; running = id; frameId = null; frameSig = null;
    if (!ensurePreview()) { running = null; note('先载入作品，再进入预演'); return Promise.resolve({ ok: false, id: id, reason: 'no-preview' }); }
    var p = plan(), why = unavailable(id, p);
    if (why) { running = null; showCard(id, why, true); return Promise.resolve({ ok: false, id: id, reason: why }); }
    var t = targetOf(id, p);
    showCard(id, '', false);
    if (via === 'ui' && narrow()) setOpen(false);
    return run(t, my).then(function (done) {
      if (!done || my !== seq) return { ok: false, id: id, cancelled: true };
      running = null; frameId = id; frameSig = sig(); render();
      return { ok: true, id: id, state: state() };
    }, function (err) {
      if (my === seq) running = null;
      errors.push(String(err && (err.stack || err.message) || err)); note('帧 ' + id + ' 执行失败 · 已停在当前视图'); render();
      return { ok: false, id: id, error: String(err && err.message || err) };
    });
  }

  // ------------------------------------------------------------------ 一句话回答（只取已有记录；缺即写缺）
  function answer(id, p) {
    if (!p) return '';
    var G = p.G, gm, sc = scene();
    switch (id) {
      case 'A0': return p.mains + ' 主线 · ' + p.branches + ' 支线 · ' + p.chapters + ' 章 · ' + (G.events || []).length + ' 事件';
      case 'A1': return (p.line.title || p.line.id) + (p.lineIsMain ? '' : '（无主线 · 取最长线）') + ' · ' + chap(p.lineFrom) + ' → ' + chap(p.lineTo) + ' · ' + p.lineN + ' 事件';
      case 'A2': var e = G.events[p.eventIndex]; return chap(e) + ' · ' + (e.title || '事件') + ' · ' + (e.kind || '类型未提供') + (p.eventIsKey ? '' : '（无转折/高燃 · 取首事件）');
      case 'A3': var e3 = G.events[p.eventIndex]; return (e3.title || '事件') + ' · ' + (e3.quote ? '有原文引句' : '未提供原文引句');
      case 'G0': return p.top.name + ' · ' + (p.top.role || '角色') + (p.top.camp ? ' · ' + p.top.camp : '');
      case 'G1': gm = sc && sc.gemModel && sc.gemModel(); var mk = gm && gm.meta ? gm.meta.filter(function (m) { return m.known; }).length : null; return '下锥 · 叙事八维' + (mk == null ? '' : ' · 已知 ' + mk + '/8');
      case 'G2': return p.top.name + ' ↔ ' + p.peer.name + ' · 同属 ' + p.top.camp;
      case 'G3': return lastAttr ? lastAttr.key + ' ' + lastAttr.score + ' · 引句 ' + lastAttr.evidence + ' 条' : '取双晶同源模型中最高的已知维';
      case 'D0': return p.camps + ' 阵营 · ' + (G.characters || []).length + ' 人 · ' + (G.relations || []).length + ' 关系';
      case 'D1': return p.camp.name + ' · ' + p.camp.members.length + ' 人';
      case 'D2': return p.rel.a + ' —' + (p.rel.kind || '关系') + '— ' + p.rel.b + ' · ' + (p.relProvided ? '强度 ' + (+p.rel.strength).toFixed(2) : '强度未提供 · 取首条记录');
      case 'D3': return p.other.name + ' · 同一颗星进入双晶';
    }
    return '';
  }

  // ------------------------------------------------------------------ PreviewState 与深链
  function selectionRef(sel) {
    if (!sel) return null;
    var G = graph();
    if (sel.type === 'character') { var c = charById(sel.id) || charByName(sel.name); return { type: 'character', id: c ? eid(c) : String(sel.id), name: c ? c.name : sel.name || null }; }
    if (sel.type === 'line') { var T = story(), t = T && T.threads.filter(function (x) { return x.id === sel.runtimeId || lineKey(x) === String(sel.id); })[0]; return { type: 'line', id: t ? lineKey(t) : String(sel.id), name: t ? t.title || t.id : null }; }
    if (sel.type === 'camp') return { type: 'camp', id: String(sel.id), name: sel.name || null };
    if (sel.type === 'relation') return { type: 'relation', id: String(sel.id), name: sel.name || null };
    if (sel.type === 'world') { var rows = G && G[sel.field] || [], r = rows.filter(function (x) { return String(x.id) === String(sel.id); })[0]; return { type: 'world', field: sel.field, id: String(sel.id), name: r ? r.name || r.title || null : null }; }
    return { type: String(sel.type), id: sel.id == null ? null : String(sel.id), name: sel.name || null };
  }
  function state() {
    var st = S.get(), G = graph(), sc = scene(), br = bridge(), peer = st.peer ? charByName(st.peer) : null;
    return {
      v: 1, atlas: st.view, frame: current(), selection: selectionRef(st.selected),
      cursor: st.cursor == null || !G ? null : { index: st.cursor, id: eventId(G.events[st.cursor]) },
      lens: st.lens, peer: st.peer ? { id: peer ? eid(peer) : null, name: st.peer } : null,
      face: st.view === 'gem' && sc && sc.face ? sc.face() : 'top',
      unfolded: !!(br && br.state && br.state().unfolded), modes: modes()
    };
  }
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
    var s = String(input == null ? '' : input).trim(), i = s.indexOf('lab=');
    if (i >= 0) s = s.slice(i + 4);
    s = s.split('&')[0].split('#')[0];
    try { s = decodeURIComponent(s); } catch (e) {}
    try { var obj = dec(s); return obj && obj.v === 1 ? obj : null; } catch (e2) { return null; }
  }
  function baseUrl() { return g.location.href.split('#')[0]; }
  function link() { return baseUrl() + '#lab=' + enc(state()); }
  function resolve(ps) {
    var G = graph(), T = story(), out = { missing: [], t: { frame: null, view: ps.atlas, line: null, cursor: null, evidence: null, character: null, peer: null, face: ps.face === 'under' ? 'under' : 'top', camp: null, relation: null, lens: ps.lens || 'camps', unfolded: !!ps.unfolded } };
    var sel = ps.selection, t = out.t;
    if (['annulus', 'gem', 'domains'].indexOf(ps.atlas) < 0) { out.missing.push('atlas:' + ps.atlas); return out; }
    if (sel) {
      if (sel.type === 'character') { t.character = charById(sel.id); if (!t.character) out.missing.push('character:' + sel.id); }
      else if (sel.type === 'line') { t.line = T && T.threads.filter(function (x) { return lineKey(x) === String(sel.id); })[0] || null; if (!t.line) out.missing.push('line:' + sel.id); else t.view = 'annulus'; }
      else if (sel.type === 'camp') { t.camp = (G.camps || []).filter(function (c) { return c.name === sel.name || campKey(c.name) === String(sel.id); })[0] || null; if (!t.camp) out.missing.push('camp:' + sel.id); else t.view = 'domains'; }
      else if (sel.type === 'relation') { t.relation = (G.relations || []).filter(function (r) { return relKey(r) === String(sel.id); })[0] || null; if (!t.relation) out.missing.push('relation:' + sel.id); else t.view = 'domains'; }
      else out.missing.push(sel.type + ':' + sel.id);
    } else if (ps.atlas === 'gem') out.missing.push('gem:selection');
    if (ps.peer) { t.peer = charById(ps.peer.id); if (!t.peer) out.missing.push('peer:' + ps.peer.id); }
    if (ps.cursor) {
      var ev = G.events || [], idx = ev[ps.cursor.index] && eventId(ev[ps.cursor.index]) === String(ps.cursor.id) ? ps.cursor.index : ev.findIndex(function (e) { return eventId(e) === String(ps.cursor.id); });
      if (idx < 0) out.missing.push('event:' + ps.cursor.id); else t.cursor = idx;
    }
    if (t.character && ps.atlas === 'domains' && !t.relation) t.view = 'gem';
    if (t.character && ps.atlas === 'gem') t.view = 'gem';
    return out;
  }
  function sameAsLink(ps) {
    var now = state();
    return JSON.stringify([now.atlas, now.selection && now.selection.type, now.selection && now.selection.id, now.cursor, now.peer && now.peer.id, now.face]) ===
      JSON.stringify([ps.atlas, ps.selection && ps.selection.type, ps.selection && ps.selection.id, ps.cursor || null, ps.peer && ps.peer.id || null, ps.face || 'top']);
  }
  function applyModes(m) { if (!m) return; MODE_NAMES.forEach(function (k) { if (typeof m[k] === 'boolean' && modes()[k] !== m[k]) setMode(k, m[k]); }); }
  function applyLink(input) {
    var ps = payloadOf(input);
    if (!ps) { note('深链无法解析 · 保持当前视图'); linkResult = { ok: false, reason: 'parse' }; render(); return Promise.resolve(linkResult); }
    if (!ensurePreview()) { linkResult = { ok: false, reason: 'no-preview' }; return Promise.resolve(linkResult); }
    applyModes(ps.modes);
    if (!ps.selection && ps.frame && frameOf(ps.frame)) {
      /* 样例链接只带图谱与帧：在本作品里按同一确定性规则重选对象；该帧不可用就停在该图全景。 */
      return go(ps.frame).then(function (r) {
        if (r.ok) { note('已按帧 ' + ps.frame + ' 的规则在本作品取景'); linkResult = { ok: true, via: 'frame', frame: ps.frame }; render(); return linkResult; }
        var pano = samplePanorama(ps.atlas);
        return go(pano).then(function () { note('帧 ' + ps.frame + ' 在本作品不可用（' + (r.reason || '已取消') + '）· 停在全景'); linkResult = { ok: false, reason: 'frame-unavailable', fallback: pano }; render(); return linkResult; });
      });
    }
    var R = resolve(ps);
    if (R.missing.length) {
      var pano = ps.atlas === 'annulus' ? 'A0' : 'D0';
      return go(pano).then(function () {
        note('深链对象不在当前作品 · 已停在' + (pano === 'A0' ? '年轮' : '星域') + '全景，未替选其他记录');
        linkResult = { ok: false, reason: 'missing', missing: R.missing, fallback: pano }; render(); return linkResult;
      });
    }
    var viaFrame = ps.frame && frameOf(ps.frame) ? go(ps.frame).then(function (r) { return r.ok && (!ps.selection || sameAsLink(ps)); }) : Promise.resolve(false);
    return viaFrame.then(function (done) {
      if (done) { note('深链已恢复 · ' + ps.frame); linkResult = { ok: true, via: 'frame', frame: ps.frame }; render(); return linkResult; }
      var my = ++seq; running = 'link'; frameId = null;
      return run(R.t, my).then(function (ok) {
        if (my === seq) running = null;
        linkResult = ok ? { ok: true, via: 'state' } : { ok: false, reason: 'cancelled' };
        if (ok) note('深链已恢复'); render(); return linkResult;
      });
    });
  }
  function whenStageReady(tries) {
    tries = tries || 0;
    var pv = PV(), ok = pv && pv.active && pv.active() && bridge() && graph();
    if (ok || tries > 100) return Promise.resolve(!!ok);
    return sleep(200).then(function () { return whenStageReady(tries + 1); });
  }

  // ------------------------------------------------------------------ 样例切换（导航 + sessionStorage 返回点；不改全局 graph）
  function readReturn() { try { var v = JSON.parse(g.sessionStorage.getItem(RETURN_KEY) || 'null'); return v && v.url ? v : null; } catch (e) { return null; } }
  function writeReturn(v) { try { g.sessionStorage.setItem(RETURN_KEY, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function clearReturn() { try { g.sessionStorage.removeItem(RETURN_KEY); } catch (e) {} }
  function dataParam() { try { return new URLSearchParams(g.location.search).get('data'); } catch (e) { return null; } }
  function sampleOf(file) { return SAMPLES.filter(function (s) { return s.file === file; })[0] || null; }
  function onSamplePage() { var rp = readReturn(); return !!(rp && rp.url !== baseUrl() && sampleOf(dataParam())); }
  function keepQuery(extra) {
    var q = new URLSearchParams(g.location.search);
    DROP_PARAMS.forEach(function (k) { q.delete(k); });
    Object.keys(extra || {}).forEach(function (k) { q.set(k, extra[k]); });
    var s = q.toString().replace(/%2F/gi, '/');
    return g.location.origin + g.location.pathname + (s ? '?' + s : '');
  }
  function checkAddress() {
    var G = graph(), a = app(); if (!G) { addr = { state: 'none', ok: false, reason: '尚未载入作品' }; return; }
    if (urlGraph === G) { addr = { state: 'url', ok: true, url: baseUrl() }; queueRender(); return; }
    var key = a && a.key ? a.key() : null;
    if (key && /^[0-9a-f]{8,40}$/.test(key)) {
      var url = keepQuery({ data: 'data/cache/' + key + '.json' }), mounted = G;
      addr = { state: 'pending', ok: false, reason: '核对作品库地址中…' };
      g.fetch('data/cache/' + key + '.json', { method: 'HEAD', cache: 'no-store' }).then(function (r) {
        if (graph() !== mounted) return;
        addr = r.ok ? { state: 'library', ok: true, url: url } : { state: 'none', ok: false, reason: '作品库缓存缺失 · 无法用地址恢复原作品' };
        queueRender();
      }, function () { if (graph() === mounted) { addr = { state: 'none', ok: false, reason: '作品库地址不可达 · 切换已禁用' }; queueRender(); } });
      return;
    }
    addr = { state: 'none', ok: false, reason: '当前作品未存入作品库、也不是从地址打开 · 切到样例会丢失它，切换已禁用' };
    queueRender();
  }
  function samplePanorama(view) { return view === 'annulus' ? 'A0' : view === 'gem' ? 'G0' : 'D0'; }
  function switchSample(file) {
    var s = sampleOf(file); if (!s) return false;
    var rp = readReturn(), here = baseUrl();
    if (!rp || rp.url === here) {
      if (!addr.ok) { note(samplesOpen ? '样例切换已禁用 · 原因见列表' : addr.reason); render(); return false; }
      var G = graph();
      if (!writeReturn({ url: addr.url, state: state(), title: G && G.title || '', at: Date.now() })) { note('浏览器禁用了会话存储 · 无法保存返回点，切换已取消'); return false; }
    }
    var st = S.get(), ps = { v: 1, atlas: st.view, frame: current() || samplePanorama(st.view), selection: null, cursor: null, lens: 'camps', peer: null, face: 'top', unfolded: false, modes: modes() };
    note('前往样例 · ' + s.label + ' · 当前作品未改动');
    g.location.assign(keepQuery({ data: s.file }) + '#lab=' + enc(ps));
    return true;
  }
  function returnToWork() {
    var rp = readReturn(); if (!rp) { note('没有返回点'); return false; }
    g.location.assign(rp.url + '#lab=' + enc(rp.state));
    return true;
  }

  // ------------------------------------------------------------------ 读图模式
  function modes() {
    var on = !!S.get().preview;
    return { notext: on && lab.notext, noglow: on && lab.noglow, gray: on && lab.gray, still: !!S.get().reduced };
  }
  function setMode(name, on) {
    on = !!on;
    if (MODE_NAMES.indexOf(name) < 0) return false;
    if (on && !S.get().preview && !ensurePreview()) return false;
    if (name === 'still') { var b = $('aphReduced'); if (!b) return false; if (!!S.get().reduced !== on) b.click(); }
    else { lab[name] = on; d.body.classList.toggle('lab-' + name, on); }
    if (name === 'noglow') glow(on);
    if (name === 'notext' && root) onEvidence();
    render(); return modes();
  }
  /* WebGL 泛光：宿主提供 scene.setGlow 才关（host.patch P1）；没有就如实说明只关了 SVG/DOM 光晕。 */
  function glow(off) {
    var sc = scene(), api = !!(sc && typeof sc.setGlow === 'function');
    if (api) sc.setGlow(off ? 0 : 1);
    if (off) note(api ? '关光 · WebGL 泛光与 SVG/DOM 光晕均已关闭' : '关光 · 已关 SVG/DOM 光晕；WebGL 泛光暂无公开开关，未关闭');
    return api;
  }
  function clearModes() { if (lab.noglow) glow(false); ['notext', 'noglow', 'gray'].forEach(function (k) { lab[k] = false; d.body.classList.remove('lab-' + k); }); }

  // ------------------------------------------------------------------ DOM（全部由本模块动态创建）
  function h(tag, attrs, kids) {
    var el = d.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] == null || attrs[k] === false) return; if (k === 'text') el.textContent = attrs[k]; else if (k === 'cls') el.className = attrs[k]; else el.setAttribute(k, attrs[k] === true ? '' : attrs[k]); });
    (kids || []).forEach(function (c) { if (c) el.appendChild(c); });
    return el;
  }
  function build() {
    if (root) return;
    els.tag = h('button', { type: 'button', cls: 'alab-tag', 'aria-expanded': 'false', 'aria-controls': 'atlasLabPanel', title: '展开预演实验室' }, [h('span', { cls: 'alab-tag-name', text: '实验室' }), els.tagFrame = h('b', { cls: 'alab-tag-frame', text: '—' })]);
    els.fold = h('button', { type: 'button', cls: 'alab-fold', 'aria-label': '收起预演实验室', title: '收起', text: '›' });
    var board = h('div', { cls: 'alab-board', role: 'group', 'aria-label': '故事板 · 12 帧' });
    els.ticks = {};
    GROUPS.forEach(function (gr) {
      var col = h('div', { cls: 'alab-ticks' });
      FRAMES.filter(function (f) { return f.id.charAt(0) === gr.key; }).forEach(function (f) {
        var b = h('button', { type: 'button', cls: 'alab-tick', 'data-frame': f.id, 'aria-pressed': 'false', title: f.id + ' · ' + f.q }, [h('span', { cls: 'alab-fid', text: f.id }), h('span', { cls: 'alab-fname', text: f.name })]);
        els.ticks[f.id] = b; col.appendChild(b);
      });
      board.appendChild(h('div', { cls: 'alab-group', 'data-atlas': gr.atlas }, [h('span', { cls: 'alab-glabel', text: gr.label }), col]));
    });
    els.cardId = h('b', { cls: 'alab-card-id', text: '选一帧' });
    els.q = h('p', { cls: 'alab-q', text: '每一帧回答一个读图问题，驱动的是真实舞台' });
    els.a = h('p', { cls: 'alab-a', text: '' });
    var card = h('div', { cls: 'alab-card', 'aria-live': 'polite' }, [els.cardId, els.q, els.a]);
    els.modes = {};
    var modeRow = h('div', { cls: 'alab-modes', role: 'group', 'aria-label': '读图模式' });
    MODE_NAMES.forEach(function (k) { var b = h('button', { type: 'button', cls: 'alab-mode', 'data-mode': k, 'aria-pressed': 'false', title: MODE_HELP[k], 'aria-label': MODE_HELP[k], text: MODE_LABEL[k] }); els.modes[k] = b; modeRow.appendChild(b); });
    els.copy = h('button', { type: 'button', cls: 'alab-copy', title: '复制当前状态的深链：新开页面恢复同一图谱、选择、章节与读图模式', text: '复制深链' });
    els.url = h('input', { cls: 'alab-url', type: 'text', readonly: true, 'aria-label': '当前状态深链', hidden: true });
    els.disclose = h('button', { type: 'button', cls: 'alab-disclose', 'aria-expanded': 'false', 'aria-controls': 'atlasLabSamples', text: '样例' });
    els.slist = h('ul', { cls: 'alab-slist', id: 'atlasLabSamples', hidden: true });
    var share = h('div', { cls: 'alab-share' }, [els.copy, els.disclose]);
    els.note = h('p', { cls: 'alab-note', role: 'status', 'aria-live': 'polite' });
    els.panel = h('section', { cls: 'alab-panel', id: 'atlasLabPanel', 'aria-label': '预演实验室' }, [
      h('header', { cls: 'alab-head' }, [h('span', { cls: 'alab-sigil', 'aria-hidden': 'true' }), h('span', { cls: 'alab-kicker', text: '预演实验室' }), h('span', { cls: 'alab-kicker-en', text: 'LAB' }), els.fold]),
      board, card, modeRow, share, els.url, els.slist, els.note]);
    root = h('aside', { id: 'atlasLab', cls: 'atlas-lab', 'data-open': 'false', 'aria-label': '预演实验室', hidden: true }, [els.tag, els.panel]);
    els.ret = h('button', { type: 'button', id: 'atlasLabReturn', cls: 'atlas-lab-return', hidden: true, title: '回到切换样例之前的作品，并恢复当时的图谱与选择' }, [h('span', { cls: 'alab-stag', text: '样例' }), h('span', { text: '回到原作品' })]);
    d.body.appendChild(root); d.body.appendChild(els.ret);
    els.tag.addEventListener('click', function () { setOpen(true); });
    els.fold.addEventListener('click', function () { setOpen(false); });
    board.addEventListener('click', function (e) { var b = e.target.closest('[data-frame]'); if (b) go(b.getAttribute('data-frame'), 'ui'); });
    modeRow.addEventListener('click', function (e) { var b = e.target.closest('[data-mode]'); if (b) setMode(b.getAttribute('data-mode'), b.getAttribute('aria-pressed') !== 'true'); });
    els.copy.addEventListener('click', copyLink);
    els.disclose.addEventListener('click', function () { samplesOpen = !samplesOpen; render(); });
    els.slist.addEventListener('click', function (e) { var b = e.target.closest('[data-file]'); if (b && b.getAttribute('aria-disabled') !== 'true') switchSample(b.getAttribute('data-file')); });
    els.ret.addEventListener('click', returnToWork);
    var card0 = evidenceCard();
    if (card0 && g.MutationObserver) new MutationObserver(onEvidence).observe(card0, { attributes: true, attributeFilter: ['hidden'] });
    if (g.ResizeObserver) { var ro = new ResizeObserver(layout); ['.aph-shell', '.aph-timeline'].forEach(function (sel) { var el = d.querySelector(sel); if (el) ro.observe(el); }); }
  }
  function copyLink() {
    var url = link(); els.url.value = url;
    function done(ok) {
      els.url.hidden = !!ok;
      if (!ok) { els.url.focus(); els.url.select(); }
      note(ok ? '深链已复制 · 新开页面即恢复此状态' : '剪贴板不可用 · 已选中链接，请手动复制');
      root.setAttribute('data-copy', ok ? 'ok' : 'manual');
    }
    function fallback() { try { els.url.hidden = false; els.url.select(); return !!(d.execCommand && d.execCommand('copy')); } catch (e) { return false; } }
    try {
      if (g.navigator.clipboard && g.navigator.clipboard.writeText) g.navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(fallback()); });
      else done(fallback());
    } catch (e) { done(false); }
    return url;
  }
  function onEvidence() {
    var c = evidenceCard(), on = evidenceOpen() && !!c && g.getComputedStyle(c).display !== 'none';
    root.classList.toggle('is-evidence', on);
    if (on && open && !narrow()) { autoFold = true; setOpen(false, true); }
    else if (!on && autoFold) { autoFold = false; setOpen(true, true); }
  }
  function setOpen(v, auto) {
    open = !!v; if (!auto) autoFold = false;
    if (root) { root.setAttribute('data-open', String(open)); els.tag.setAttribute('aria-expanded', String(open)); }
    layout(); return open;
  }
  function layout() {
    if (!root) return;
    var shell = d.querySelector('.aph-shell'), tl = d.querySelector('.aph-timeline'), H = g.innerHeight;
    var top = shell ? shell.getBoundingClientRect().bottom : 0, tlr = tl ? tl.getBoundingClientRect() : null;
    var bottom = tlr && tlr.height ? H - tlr.top : 0;
    root.style.setProperty('--alab-top', Math.max(12, Math.round(top + 12)) + 'px');
    root.style.setProperty('--alab-bottom', Math.max(12, Math.round(bottom + 10)) + 'px');
    els.ret.style.setProperty('--alab-top', Math.max(12, Math.round(top + 12)) + 'px');
    els.ret.style.setProperty('--alab-bottom', Math.max(12, Math.round(bottom + 10)) + 'px');
    root.classList.toggle('is-narrow', narrow());
  }
  function note(text) { lastNote = String(text || ''); if (els.note) els.note.textContent = lastNote; }
  function showCard(id, why, disabled) {
    var f = frameOf(id); if (!f || !els.cardId) return;
    els.cardId.textContent = f.id + ' · ' + f.name;
    els.q.textContent = f.q;
    els.a.textContent = why || (running === id ? '驱动舞台中…' : '');
    root.setAttribute('data-card', disabled ? 'disabled' : 'live');
  }
  function queueRender() { if (renderQueued) return; renderQueued = true; Promise.resolve().then(function () { renderQueued = false; render(); }); }
  function render() {
    if (!root) return;
    var st = S.get(), on = !!st.preview;
    root.hidden = !on;
    els.ret.hidden = !(onSamplePage() && graph());
    if (!on) return;
    var p = plan(), cur = current();
    if (open === null) setOpen(wide());
    FRAMES.forEach(function (f) {
      var b = els.ticks[f.id], why = unavailable(f.id, p);
      b.setAttribute('aria-pressed', String(cur === f.id || running === f.id));
      b.classList.toggle('is-running', running === f.id);
      b.setAttribute('aria-disabled', why ? 'true' : 'false');
      b.title = f.id + ' · ' + f.q + (why ? '（' + why + '）' : '');
    });
    var shown = running && frameOf(running) ? running : cur;
    els.tagFrame.textContent = shown || '—';
    if (shown) {
      var why0 = unavailable(shown, p);
      showCard(shown, why0, !!why0);
      if (!why0 && running !== shown) { var ans = ''; try { ans = answer(shown, p); } catch (e) { ans = ''; } els.a.textContent = ans; lastAnswer[shown] = ans; }
    } else if (frameId === null && running === null && els.cardId.textContent !== '选一帧') {
      els.cardId.textContent = '自由浏览'; els.q.textContent = '当前视图已偏离故事板帧，深链仍记录完整状态'; els.a.textContent = '';
    }
    var m = modes();
    MODE_NAMES.forEach(function (k) {
      var b = els.modes[k], miss = k === 'still' && !$('aphReduced');
      b.setAttribute('aria-pressed', String(!!m[k]));
      b.setAttribute('aria-disabled', miss ? 'true' : 'false');
      if (k === 'noglow') b.setAttribute('data-partial', 'webgl');
    });
    els.disclose.setAttribute('aria-expanded', String(samplesOpen));
    els.slist.hidden = !samplesOpen;
    renderSamples();
    var rp = readReturn(), sample = onSamplePage();
    root.setAttribute('data-sample', sample ? 'true' : 'false');
    if (lastNote && els.note.textContent !== lastNote) els.note.textContent = lastNote;
    if (!rp) root.removeAttribute('data-return');
  }
  var samplesKey = '';
  function renderSamples() {
    var G = graph(), here = dataParam(), sample = onSamplePage(), cur = sampleOf(here), rows = [];
    var title = G ? (G.title || '未命名') : '未载入', key = JSON.stringify([title, here, sample, addr.ok, addr.reason || '', urlGraph === G]);
    if (key === samplesKey && els.slist.childNodes.length) return;
    samplesKey = key;
    rows.push(h('li', { cls: 'alab-srow is-current' }, [h('span', { cls: 'alab-stag' + (cur ? '' : ' is-work'), text: cur ? '样例' : '作品' }), h('span', { cls: 'alab-sname', text: '当前 · ' + title })]));
    SAMPLES.forEach(function (s) {
      var isHere = here === s.file && !!urlGraph && urlGraph === G;
      var why = isHere ? '当前已是此样例' : (!sample && !addr.ok) ? addr.reason : '';
      rows.push(h('li', { cls: 'alab-srow' }, [h('button', { type: 'button', cls: 'alab-sample', 'data-file': s.file, 'aria-disabled': why ? 'true' : 'false', title: why || ('切到样例「' + s.label + '」· 当前作品不改动，可一键返回') }, [h('span', { cls: 'alab-stag', text: '样例' }), h('span', { cls: 'alab-sname', text: s.label }), h('small', { text: s.hint })])]));
    });
    if (!sample && !addr.ok) rows.push(h('li', { cls: 'alab-sreason', text: addr.reason }));
    els.slist.replaceChildren.apply(els.slist, rows);
  }

  // ------------------------------------------------------------------ 生命周期
  function enter() { build(); layout(); if (open === null) setOpen(wide()); render(); }
  function leave() {
    seq++; running = null; frameId = null; frameSig = null;
    var sc = scene();
    if (labHold && sc && sc.hoverAttr) sc.hoverAttr(null);
    if (labRelation && bridge() && typeof bridge().relation === 'function') bridge().relation(null);
    labHold = false; labSearch = false; labRelation = false; autoFold = false;
    clearModes(); render();
  }
  S.subscribe(function (st, action) {
    if (action && action.type === 'graph') { seq++; running = null; frameId = null; planCache = null; lastAttr = null; }
    if (!!st.preview !== wasPreview) { wasPreview = !!st.preview; if (wasPreview) enter(); else leave(); }
    queueRender();
  });
  d.addEventListener('cl:graph-ready', function () {
    build();
    var G = graph(), q = new URLSearchParams(g.location.search);
    if (!urlGraphSeen) { urlGraphSeen = true; if (q.get('data') || q.get('demo') === '1') urlGraph = G; }
    planCache = null; checkAddress();
    var rp = readReturn(); if (rp && rp.url === baseUrl()) clearReturn();
    if (pendingLink) { var l = pendingLink; pendingLink = null; whenStageReady().then(function (ok) { if (ok) return sleep(dur(2)).then(function () { return applyLink(l); }); }); }
    layout(); render();
  });
  g.addEventListener('hashchange', function () { if (/^#lab=/.test(g.location.hash) && graph()) applyLink(g.location.hash); });
  g.addEventListener('resize', function () { layout(); queueRender(); });
  d.addEventListener('cl:atlas-view', function () { layout(); queueRender(); });
  // 用户在实验室外的任何新动作都让未完成的帧步骤失效（规格 §4.2-1）
  d.addEventListener('pointerdown', function (e) { if (running && root && !root.contains(e.target)) cancel(); }, true);
  d.addEventListener('keydown', function (e) { if (running && root && !root.contains(e.target) && !/^(Shift|Control|Alt|Meta)$/.test(e.key)) cancel(); }, true);
  if (/^#lab=/.test(g.location.hash)) pendingLink = g.location.hash;

  g.CLAtlasLab = {
    go: function (id) { return go(String(id || '').toUpperCase()); },
    frames: function () {
      var p = plan();
      return FRAMES.map(function (f) {
        var why = unavailable(f.id, p), t = !why && p ? targetOf(f.id, p) : null, focus = t && (t.relation ? { type: 'relation', id: relKey(t.relation), name: t.relation.a + ' — ' + t.relation.b } : t.camp ? { type: 'camp', id: campKey(t.camp.name), name: t.camp.name } : t.character ? { type: 'character', id: eid(t.character), name: t.character.name } : t.line ? { type: 'line', id: lineKey(t.line), name: t.line.title || t.line.id } : null);
        return { id: f.id, atlas: f.atlas, name: f.name, question: f.q, available: !why, reason: why || null, target: focus, cursor: t ? t.cursor : null, peer: t && t.peer ? { id: eid(t.peer), name: t.peer.name } : null, face: t ? t.face : null, evidence: t && t.evidence ? t.evidence.type : null, members: t && t.camp ? t.camp.members.length : null, view: t ? (t.character ? 'gem' : t.view) : null };
      });
    },
    current: current, link: link, applyLink: applyLink, modes: modes, setMode: setMode, state: state,
    open: function (v) { build(); return setOpen(v !== false); },
    samples: function () { return SAMPLES.map(function (s) { return { file: s.file, label: s.label, sample: true }; }); },
    switchSample: switchSample, returnToWork: returnToWork,
    stats: function () {
      return { built: !!root, visible: !!(root && !root.hidden), open: !!open, narrow: narrow(), frame: current(), running: running, token: seq,
        modes: modes(), note: lastNote, link: linkResult, address: { state: addr.state, ok: addr.ok, reason: addr.reason || null },
        sample: { page: onSamplePage(), current: dataParam(), returnPoint: !!readReturn() }, lastAttr: lastAttr, interrupts: interrupts, errors: errors.slice(-5) };
    }
  };
  if (graph()) {
    build(); urlGraphSeen = true;
    var q0 = new URLSearchParams(g.location.search); if (q0.get('data') || q0.get('demo') === '1') urlGraph = graph();
    checkAddress(); render();
  }
})(window);
