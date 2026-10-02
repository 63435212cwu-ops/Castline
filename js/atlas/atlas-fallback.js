/* No-WebGL reading stage. Pure source/story/gem models; no analysis, storage or paid calls. */
(function (g) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg', TAU = Math.PI * 2, root, ui = {}, G, A, tree, gem, actions = [], generation = 0, request = null;
  var state = {}, sourceURL = '', loading = false, error = '', records = null, resizeTimer = null;
  function array(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return v == null ? '' : String(v); }
  function reset() { state = { view: 'annulus', character: null, event: null, line: null, camp: null, chapter: null, relations: false, page: 0, range: null, zoom: 1, pan: [0, 0] }; }
  function element(tag, cls, parent, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; if (parent) parent.appendChild(n); return n; }
  function svg(tag, attrs, parent) { var n = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (key) { n.setAttribute(key, attrs[key]); }); if (parent) parent.appendChild(n); return n; }
  function text(x, y, value, cls, parent) { var t = svg('text', { x: x, y: y, 'class': cls || 'afb-label', 'text-anchor': 'middle' }, parent || ui.drawing); t.textContent = value; return t; }
  function button(label, fn, parent) { var b = element('button', '', parent, label); b.type = 'button'; b.addEventListener('click', fn); return b; }
  function hit(n, label, fn) { var id = actions.push(fn) - 1; n.setAttribute('data-action', id); n.setAttribute('tabindex', '0'); n.setAttribute('role', 'button'); n.setAttribute('aria-label', label); svg('title', {}, n).textContent = label; return n; }
  function point(cx, cy, r, a) { return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; }
  function path(points, close) { return points.map(function (p, i) { return (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2); }).join('') + (close ? 'Z' : ''); }
  function arc(cx, cy, r, from, to) { var p = [], n = Math.max(2, Math.ceil(Math.abs(to - from) / 0.045)); for (var i = 0; i <= n; i++) p.push(point(cx, cy, r, from + (to - from) * i / n)); return path(p, false); }
  function short(value, length) { var s = str(value); return s.length > length ? s.slice(0, length - 1) + '…' : s; }
  function camera() { state.zoom = 1; state.pan = [0, 0]; }
  function viewport() { var w = ui.stage.clientWidth || 900, h = Math.max(320, ui.stage.clientHeight || 600); return { w: w, h: h, x: w / 2, y: h / 2, r: Math.max(80, Math.min(w, h) * 0.34) }; }
  function applyCamera() { var v = viewport(), z = state.zoom; ui.svg.setAttribute('viewBox', [(v.w - v.w / z) / 2 - state.pan[0], (v.h - v.h / z) / 2 - state.pan[1], v.w / z, v.h / z].join(' ')); }
  function prepare(input) {
    var raw = input && (input.graph || (input.data && input.data.characters && input.data)) || input;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('需要小说图谱 JSON 对象');
    if (!g.CLAtlasSource || !g.CLStory || !g.CLAtlasModel || !g.CLGemModel) throw new Error('二维图谱的数据模块尚未就绪，请重试');
    var graph = g.CLAtlasSource.normalize(raw), story = g.CLStory.analyze(graph, { maxThreads: Math.max(48, graph.events.length, array(graph.storylines).length) });
    return { graph: graph, story: story, atlas: g.CLAtlasModel.build(story, graph) };
  }
  function load(input) {
    var model = prepare(input); G = model.graph; tree = model.story; A = model.atlas;
    reset(); records = null; error = ''; loading = false; ui.evidence.hidden = true;
    ui.chapter.replaceChildren(); var all = element('option', '', ui.chapter, '全书'); all.value = '';
    array(A.chapters).forEach(function (c, i) { var op = element('option', '', ui.chapter, c.name || ('章节 ' + (i + 1))); op.value = i; });
    render(); return stats();
  }
  function notice(message) { if (ui.status) ui.status.textContent = message; }
  function fetchGraph(url) {
    sourceURL = str(url); var ticket = ++generation;
    if (request) request.abort(); request = typeof AbortController === 'function' ? new AbortController() : null;
    loading = true; error = ''; render(); notice('正在读取图谱文件 · 不触发模型分析');
    return fetch(sourceURL, { credentials: 'same-origin', signal: request ? request.signal : undefined }).then(function (r) {
      if (!r.ok) throw new Error('读取失败（HTTP ' + r.status + '）'); return r.json();
    }).then(function (data) { if (ticket === generation) load(data); return stats(); }).catch(function (e) {
      if (ticket !== generation || e.name === 'AbortError') return stats();
      loading = false; error = '无法载入图谱：' + e.message; render(); return stats();
    });
  }
  function selectEvent(index) { if (!G || typeof index !== 'number' || index % 1 || index < 0 || index >= G.events.length) return false; state.event = index; state.chapter = G.events[index].chapter || null; records = G.events[index]; render(); return true; }
  function selectCharacter(index) { state.character = index; state.camp = null; state.page = 0; records = G.characters[index]; render(); }
  function switchView(view) { if (['annulus', 'gem', 'domains'].indexOf(view) < 0) return; state.view = view; state.page = 0; state.relations = false; camera(); render(); }
  function back() { if (!ui.evidence.hidden) { ui.evidence.hidden = true; return; } state.camp = null; state.line = null; state.character = null; state.range = null; state.relations = false; state.page = 0; records = null; camera(); render(); }
  function evidence(record, title) {
    record = record || records; if (!record) { notice('先点选事件、人物、剧情线或关系，再查看来源'); return; }
    ui.evidenceBody.replaceChildren(); ui.evidenceTitle.textContent = title || record.title || record.name || record.kind || '来源记录';
    var body = record.summary || record.brief || record.description || record.theme || record.basis;
    if (body) element('p', '', ui.evidenceBody, body);
    if (record.quote) { element('blockquote', '', ui.evidenceBody, record.quote); element('small', '', ui.evidenceBody, '来源附带引句；二维阅读不另行核验原文'); }
    array(record.evidence).forEach(function (e) { element('blockquote', '', ui.evidenceBody, typeof e === 'string' ? e : JSON.stringify(e)); });
    if (!body && !record.quote && !array(record.evidence).length) element('p', '', ui.evidenceBody, '该记录未提供文字依据；缺失不等于数值为零。');
    element('pre', '', ui.evidenceBody, JSON.stringify(record, null, 2)); ui.evidence.hidden = false; ui.evidenceClose.focus();
  }
  function page(items, size) {
    var total = Math.max(1, Math.ceil(items.length / size)); state.page = Math.max(0, Math.min(total - 1, state.page));
    ui.previous.disabled = state.page === 0; ui.next.disabled = state.page >= total - 1;
    ui.page.textContent = (items.length ? state.page + 1 : 0) + ' / ' + (items.length ? total : 0);
    return items.slice(state.page * size, (state.page + 1) * size);
  }
  function star(x, y, label, tone, fn, options) {
    options = options || {}; var n = hit(svg('g', { 'class': 'afb-star' + (options.selected ? ' is-selected' : '') + (options.unknown ? ' is-unknown' : ''), 'data-tone': tone % 6 }, ui.drawing), label, fn);
    svg('circle', { cx: x, cy: y, r: 22, 'class': 'afb-target' }, n);
    svg('circle', { cx: x, cy: y, r: options.radius || 5, 'class': 'afb-node' }, n);
    if (options.selected) svg('circle', { cx: x, cy: y, r: 13, 'class': 'afb-halo' }, n);
    var t = text(x, y + (options.radius || 5) + 20, short(label, viewport().w < 600 ? 7 : 11), 'afb-label', n);
    if (x < 75) t.setAttribute('text-anchor', 'start'); if (x > viewport().w - 75) t.setAttribute('text-anchor', 'end');
    return n;
  }
  function empty(message) { var v = viewport(); svg('circle', { cx: v.x, cy: v.y, r: v.r * 0.55, 'class': 'afb-orbit' }, ui.drawing); text(v.x, v.y, message, 'afb-empty'); }
  function drawAnnulus(v) {
    var N = G.events.length, range = state.range || [0, N - 1], lo = range[0], hi = range[1], count = hi - lo + 1;
    if (!N) { page([], 1); empty('未提供事件记录'); return; }
    function angle(i) { return -Math.PI / 2 + (i - lo + 0.5) / count * TAU; }
    var lines = array(A.lines).slice().sort(function (a, b) { return (a.kind !== 'main') - (b.kind !== 'main') || (a.order.first || 0) - (b.order.first || 0); });
    var visible = page(lines, v.w < 600 ? 12 : 18), lineCount = visible.length;
    svg('circle', { cx: v.x, cy: v.y, r: v.r + 22, 'class': 'afb-orbit' }, ui.drawing);
    visible.forEach(function (line, k) {
      var events = array(line.eventIdxs), first = events.length ? Math.min.apply(null, events) : null, last = events.length ? Math.max.apply(null, events) : null;
      var radius = v.r * (0.4 + 0.58 * (k + 1) / Math.max(1, lineCount));
      if (first === null) { star(v.x + (k % 4 - 1.5) * 44, v.y + 40 + Math.floor(k / 4) * 34, '待定位 · ' + (line.name || line.id), line.gen || 0, function () { state.line = line.id; records = line; evidence(line); }, { unknown: true }); return; }
      if (last < lo || first > hi) return;
      var a0 = angle(Math.max(lo, first)), a1 = angle(Math.min(hi, last));
      var p = svg('path', { d: arc(v.x, v.y, radius, a0, a1 === a0 ? a0 + 0.002 : a1), 'class': 'afb-arc' + (line.kind === 'main' ? ' is-main' : '') + (String(state.line) === String(line.id) ? ' is-selected' : ''), 'data-tone': (line.gen || 0) % 6, 'data-status': line.status, 'data-line': line.id, 'data-first': first, 'data-last': last }, ui.drawing);
      var pick = hit(svg('g', {}, ui.drawing), (line.name || line.id) + ' · ' + line.kind + ' · ' + events.length + ' 事件', function () { state.line = line.id; records = line; render(); });
      svg('path', { d: p.getAttribute('d'), 'class': 'afb-arc-target' }, pick);
      var end = point(v.x, v.y, radius, a1); svg('circle', { cx: end[0], cy: end[1], r: line.kind === 'main' ? 4 : 2.5, 'class': 'afb-end' }, pick);
    });
    var bucket = Math.max(1, Math.ceil(count / 110));
    for (var start = lo; start <= hi; start += bucket) (function (first, last) {
      var p = point(v.x, v.y, v.r + 22, angle((first + last) / 2)), event = G.events[first], n = last - first + 1;
      var selected = state.event != null && state.event >= first && state.event <= last;
      var mark = hit(svg('g', { 'class': 'afb-event' + (selected ? ' is-selected' : ''), 'data-event-start': first, 'data-event-end': last }, ui.drawing), n === 1 ? ('E' + (first + 1) + ' · ' + event.title) : ('展开 E' + (first + 1) + '–' + (last + 1) + ' · ' + n + ' 事件'), function () { if (n > 1) { state.range = [first, last]; state.page = 0; camera(); render(); } else selectEvent(first); });
      svg('circle', { cx: p[0], cy: p[1], r: n > 1 ? 11 : 8, 'class': 'afb-target' }, mark);
      svg('circle', { cx: p[0], cy: p[1], r: selected ? 6 : (n > 1 ? 4 : 2.3), 'class': 'afb-node' }, mark);
      if (n > 1) text(p[0], p[1] - 10, n, 'afb-micro', mark);
    })(start, Math.min(hi, start + bucket - 1));
    var line = array(A.lines).filter(function (l) { return String(l.id) === String(state.line); })[0];
    text(v.x, v.y - 7, line ? short(line.name, 13) : (state.range ? '局部章序' : '全书年轮'), 'afb-title');
    text(v.x, v.y + 18, 'E' + (lo + 1) + '—' + (hi + 1) + ' · ' + N + ' 事件', 'afb-note');
    text(v.x, v.y + 39, lines.length ? lines.length + (tree && tree.src === 'derived' ? ' 条算法推导线' : ' 条来源线') : '未归线事件轨', 'afb-micro');
    ui.context.textContent = '所有弧与事件共用同一事件角度尺 · 粗弧主线 / 细弧支线 / 虚线悬置';
    if (line) ui.context.textContent = (line.name || line.id) + ' · ' + ({ resolved: '已收束', open: '未收束', suspended: '悬置', unknown: '状态未知', conflict: '记录冲突' }[line.status] || '状态未知') + ' · ' + array(line.cast).length + ' 位参与者';
  }
  function narrativeOf(name) {
    var c = G.characters.filter(function (x) { return x.name === name; }); if (c.length !== 1) return null;
    var m = c[0].narrative || c[0].meta;
    return m && m.score && typeof m.score === 'object' ? m : null;
  }
  function drawGem(v) {
    if (!G.characters.length) { page([], 1); empty('未提供人物记录'); return; }
    if (state.character == null || !G.characters[state.character]) state.character = 0;
    var c = G.characters[state.character]; records = c;
    gem = g.CLGemModel.build(c, G, { atlas: A, chapter: state.chapter, metaOf: narrativeOf });
    if (!gem || !gem.ok) { empty('人物量化模型暂不可用'); return; }
    ui.svg.setAttribute('hidden', ''); ui.gemHost.hidden = false;
    if (!g.CLGemSVG || !g.CLGemSVG.mount) { ui.svg.removeAttribute('hidden'); ui.gemHost.hidden = true; empty('双晶绘制模块尚未就绪'); return; }
    g.CLGemSVG.setPaused(true); g.CLGemSVG.mount(ui.gemHost, gem);
    ui.gemName.textContent = c.name || '未命名人物'; ui.gemName.hidden = false;
    state.page = state.character; ui.previous.disabled = state.character === 0; ui.next.disabled = state.character >= G.characters.length - 1;
    ui.page.textContent = (state.character + 1) + ' / ' + G.characters.length;
    ui.context.textContent = (gem.stage.hasQuantified ? '已观测章节快照' : '全书属性 · 此章没有阶段数值') + ' · ' + gem.scoredCount + '/8 属性已知 · ' + (gem.metaReady ? '叙事分来自所载记录' : '叙事八维未知，不补均值');
  }
  function camps() {
    var groups = [], map = Object.create(null);
    G.characters.forEach(function (c, i) {
      var name = c.camp;
      if (!name) { var declared = array(G.camps).filter(function (cp) { return array(cp.members).indexOf(c.name) >= 0; }); if (declared.length === 1) name = declared[0].name; }
      name = name || '未分群'; if (map[name] == null) { map[name] = groups.length; groups.push({ name: name, members: [] }); }
      groups[map[name]].members.push(i);
    }); return groups;
  }
  function resolve(name) { var found = []; G.characters.forEach(function (c, i) { if (c.name === name || c.id === name) found.push(i); }); return found.length === 1 ? found[0] : null; }
  function relationList() {
    var character = G.characters[state.character], group = camps().filter(function (c) { return c.name === state.camp; })[0];
    return G.relations.map(function (r, i) { return { record: r, index: i, a: resolve(r.a), b: resolve(r.b) }; }).filter(function (r) {
      return character ? r.record.a === character.name || r.record.b === character.name || r.record.a === character.id || r.record.b === character.id : group ? group.members.indexOf(r.a) >= 0 || group.members.indexOf(r.b) >= 0 : true;
    });
  }
  function drawDomains(v) {
    if (!G.characters.length && !G.relations.length) { page([], 1); empty('未提供人物或关系记录'); return; }
    var groups = camps(), small = v.w < 600, positions = Object.create(null), members = [], relations = relationList(), edges = [];
    var overview = state.camp == null && state.character == null && !state.relations;
    if (overview) {
      var shown = page(groups, small ? 8 : 12);
      shown.forEach(function (group, i) { var p = point(v.x, v.y, shown.length === 1 ? 0 : v.r * 0.8, -Math.PI / 2 + TAU * i / shown.length); positions[group.name] = p; });
      var groupOf = {}, pair = Object.create(null); groups.forEach(function (cp) { cp.members.forEach(function (index) { groupOf[index] = cp.name; }); });
      relations.forEach(function (rel) { var a = groupOf[rel.a], b = groupOf[rel.b]; if (!a || !b || a === b || !positions[a] || !positions[b]) return; var key = [a, b].sort().join('\u0001'); if (!pair[key]) pair[key] = { a: a, b: b, records: [] }; pair[key].records.push(rel.record); });
      Object.keys(pair).forEach(function (key) { var edge = pair[key], p = positions[edge.a], q = positions[edge.b], mark = hit(svg('g', {}, ui.drawing), edge.a + ' ↔ ' + edge.b + ' · ' + edge.records.length + ' 条真实关系', function () { state.relations = true; state.page = 0; render(); }); svg('path', { d: path([p, q]), 'class': 'afb-relation-target' }, mark); svg('path', { d: path([p, q]), 'class': 'afb-relation' }, mark); });
      shown.forEach(function (cp, i) { var p = positions[cp.name]; svg('circle', { cx: p[0], cy: p[1], r: 40, 'class': 'afb-cluster', 'data-tone': i % 6 }, ui.drawing); star(p[0], p[1], cp.name + ' · ' + cp.members.length, i, function () { state.camp = cp.name; state.page = 0; render(); }, { radius: 9 }); });
      text(v.x, v.y, groups.length + ' 星团 · ' + G.characters.length + ' 人物', 'afb-title');
    } else {
      if (state.relations) { edges = page(relations, small ? 7 : 12); edges.forEach(function (r) { if (r.a != null && members.indexOf(r.a) < 0) members.push(r.a); if (r.b != null && members.indexOf(r.b) < 0) members.push(r.b); }); }
      else if (state.character != null) { members = [state.character]; relations.forEach(function (r) { if (r.a != null && members.indexOf(r.a) < 0) members.push(r.a); if (r.b != null && members.indexOf(r.b) < 0) members.push(r.b); }); members = page(members, small ? 10 : 24); edges = relations; }
      else { var cp = groups.filter(function (c) { return c.name === state.camp; })[0]; members = page(cp ? cp.members : [], small ? 10 : 24); edges = relations; }
      members.forEach(function (index, i) { positions[index] = point(v.x, v.y, members.length === 1 ? 0 : v.r * 0.85, -Math.PI / 2 + TAU * i / members.length); });
      var unresolved = 0, renderedEdges = 0;
      edges.forEach(function (edge) {
        if (edge.a == null || edge.b == null) { unresolved++; if (state.relations) star(v.x - 65 + (unresolved % 4) * 36, v.y - 36, '待校对关系 ' + (edge.index + 1), 5, function () { records = edge.record; evidence(); }, { unknown: true }).setAttribute('data-relation', edge.index); return; }
        if (!positions[edge.a] || !positions[edge.b]) return; renderedEdges++;
        var p = positions[edge.a], q = positions[edge.b], mark = hit(svg('g', { 'data-relation': edge.index }, ui.drawing), edge.record.a + ' · ' + edge.record.kind + ' · ' + edge.record.b, function () { records = edge.record; evidence(); });
        svg('path', { d: path([p, q]), 'class': 'afb-relation-target' }, mark); svg('path', { d: path([p, q]), 'class': 'afb-relation' }, mark);
      });
      members.forEach(function (index, i) { var p = positions[index], c = G.characters[index]; star(p[0], p[1], c.name || '未命名人物', i, function () { selectCharacter(index); }, { selected: state.character === index }); });
      text(v.x, v.y + 14, state.character != null ? short(G.characters[state.character].name + '的邻域', 12) : short(state.camp || '真实关系', 12), 'afb-title');
      text(v.x, v.y + 36, renderedEdges + ' 可见边 / ' + relations.length + ' 相关边', 'afb-micro');
      ui.context.textContent = '拓扑位置，非地理/强弱 · 关系页保留全部 ' + relations.length + ' 条记录' + (unresolved ? ' · 含待校对端点' : '');
    }
    ui.relations.textContent = state.relations ? '人物/星团' : '关系 ' + relations.length;
  }
  function render() {
    if (!root) return; actions = []; ui.drawing.replaceChildren(); ui.gemHost.replaceChildren(); ui.gemHost.hidden = true; ui.gemName.hidden = true; ui.svg.removeAttribute('hidden');
    if (g.CLGemSVG) g.CLGemSVG.unmount(); gem = null;
    ui.nav.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.view === state.view)); });
    root.dataset.view = state.view; ui.relations.hidden = state.view !== 'domains'; ui.retry.hidden = !error; ui.context.textContent = '缩放、拖动探索 · Enter 选择 · E 来源 · Escape 返回';
    ui.title.textContent = G ? G.title || '未命名作品' : '星典 · 二维图谱'; ui.cursor.disabled = !G || !G.events.length; ui.chapter.disabled = !G || !array(A.chapters).length;
    if (!G) { page([], 1); empty(loading ? '正在读取星图…' : '载入小说图谱，开启星空'); notice(error || 'WebGL 不可用时仍保留图形阅读 · 载入 JSON 或示例'); applyCamera(); return; }
    var v = viewport(); if (state.view === 'annulus') drawAnnulus(v); else if (state.view === 'gem') drawGem(v); else drawDomains(v);
    ui.cursor.max = Math.max(0, G.events.length - 1); ui.cursor.value = state.event == null ? 0 : state.event;
    ui.cursorText.textContent = state.event == null ? '全书 · ' + G.events.length + ' 事件' : 'E' + (state.event + 1) + ' · ' + short(G.events[state.event].title, 20);
    var ci = array(A.chapters).findIndex(function (c) { return c.name === state.chapter; }); ui.chapter.value = ci < 0 ? '' : ci;
    notice(error || (loading ? '读取中…' : '二维同源图谱 · ' + G.characters.length + ' 人物 · ' + G.events.length + ' 事件 · ' + array(A.lines).length + ' 来源线 · ' + G.relations.length + ' 关系'));
    applyCamera(); document.dispatchEvent(new CustomEvent('cl:atlas-fallback-render', { detail: stats() }));
  }
  function changePage(delta) { if (state.view === 'gem') { state.character = Math.max(0, Math.min(G.characters.length - 1, (state.character || 0) + delta)); } else state.page += delta; render(); }
  function search() {
    if (!G) return; var q = ui.search.value.trim().toLowerCase(); if (!q) return;
    var hits = []; G.characters.forEach(function (c, i) { if (str(c.name).toLowerCase().indexOf(q) >= 0) hits.push({ c: i }); }); G.events.forEach(function (e, i) { if (str(e.title).toLowerCase().indexOf(q) >= 0) hits.push({ e: i }); });
    if (!hits.length) { notice('没有匹配实体'); return; } var index = ui.search.dataset.query === q ? Number(ui.search.dataset.position || 0) + 1 : 0; ui.search.dataset.query = q; ui.search.dataset.position = index;
    var found = hits[index % hits.length]; if (found.c != null) { state.view = 'gem'; selectCharacter(found.c); } else { state.view = 'annulus'; state.range = null; selectEvent(found.e); } notice('已在图中定位 · ' + hits.length + ' 项匹配，再次搜索切换');
  }
  function onKey(e) {
    if (!root || !document.body.classList.contains('atlas-2d')) return;
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) { if (e.target === ui.search && e.key === 'Enter') { e.preventDefault(); search(); } return; }
    var target = e.target.closest && e.target.closest('[data-action]');
    if (target && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); e.stopImmediatePropagation(); var fn = actions[Number(target.dataset.action)]; if (fn) fn(); return; }
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); back(); }
    else if (str(e.key).toLowerCase() === 'e') { e.preventDefault(); evidence(); }
    else if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && G && G.events.length) { e.preventDefault(); selectEvent(Math.max(0, Math.min(G.events.length - 1, (state.event || 0) + (e.key === 'ArrowRight' ? 1 : -1)))); }
    else if (e.key === '+' || e.key === '-') { e.preventDefault(); state.zoom = Math.max(0.7, Math.min(7, state.zoom * (e.key === '+' ? 1.2 : 1 / 1.2))); applyCamera(); }
  }
  function bindPan() {
    var pointer = null;
    ui.svg.addEventListener('pointerdown', function (e) { if (e.target.closest('[data-action]')) return; pointer = { id: e.pointerId, x: e.clientX, y: e.clientY, pan: state.pan.slice() }; ui.svg.setPointerCapture(e.pointerId); });
    ui.svg.addEventListener('pointermove', function (e) { if (!pointer || pointer.id !== e.pointerId) return; state.pan = [pointer.pan[0] + (e.clientX - pointer.x) / state.zoom, pointer.pan[1] + (e.clientY - pointer.y) / state.zoom]; applyCamera(); });
    function end() { pointer = null; } ui.svg.addEventListener('pointerup', end); ui.svg.addEventListener('pointercancel', end);
    ui.svg.addEventListener('wheel', function (e) { e.preventDefault(); state.zoom = Math.max(0.7, Math.min(7, state.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12))); applyCamera(); }, { passive: false });
  }
  function onResize() { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 80); }
  function axisEvidence(e) { if (!root || state.view !== 'gem' || !gem || !e.detail) return; var key = e.detail.key, dim = array(gem.attr).concat(array(gem.meta)).filter(function (d) { return d.key === key; })[0]; if (dim) evidence(dim, key + ' · ' + (dim.known ? dim.score : '未知')); }
  function start(options) {
    options = options || {}; if (root) return api; reset(); G = null; A = null; error = ''; records = null;
    document.body.classList.add('atlas-2d'); root = element('main', 'afb', document.body); root.id = 'atlasFallback'; root.setAttribute('aria-label', '二维小说星空图谱');
    var sky = svg('svg', { 'class': 'afb-sky', viewBox: '0 0 1000 800', preserveAspectRatio: 'none', 'aria-hidden': 'true' }, root);
    for (var i = 0; i < 100; i++) svg('circle', { cx: (i * 137.508) % 1000, cy: (i * i * 23.91 + 81) % 800, r: i % 7 === 0 ? 1.2 : 0.65 }, sky);
    var head = element('header', 'afb-head', root); element('span', 'afb-brand', head, 'CASTLINE / 2D'); ui.title = element('h1', '', head, '星典');
    ui.file = element('input', '', head); ui.file.type = 'file'; ui.file.accept = '.json,application/json'; ui.file.hidden = true;
    button('载入 JSON', function () { ui.file.value = ''; ui.file.click(); }, head); button('载入示例', function () { fetchGraph('data/sample-saga.json'); }, head);
    ui.retry = button('重试', function () { if (sourceURL) fetchGraph(sourceURL); else { ui.file.value = ''; ui.file.click(); } }, head); ui.retry.hidden = true;
    ui.nav = element('nav', 'afb-nav', root); ['年轮剧情', '人物双晶', '关系星域'].forEach(function (label, i) { var view = ['annulus', 'gem', 'domains'][i], b = button(label, function () { switchView(view); }, ui.nav); b.dataset.view = view; });
    var tools = element('div', 'afb-tools', root); button('返回', back, tools); ui.relations = button('关系', function () { state.relations = !state.relations; state.page = 0; render(); }, tools);
    button('−', function () { state.zoom = Math.max(0.7, state.zoom / 1.2); applyCamera(); }, tools); button('＋', function () { state.zoom = Math.min(7, state.zoom * 1.2); applyCamera(); }, tools); button('复位', function () { camera(); applyCamera(); }, tools);
    ui.search = element('input', 'afb-search', tools); ui.search.placeholder = '定位人物 / 事件'; ui.search.setAttribute('aria-label', '搜索图谱实体'); button('定位', search, tools); button('来源 E', function () { evidence(); }, tools);
    ui.stage = element('section', 'afb-stage', root); ui.stage.setAttribute('aria-label', '可缩放图谱舞台');
    ui.svg = svg('svg', { 'class': 'afb-map', role: 'group', 'aria-label': '星空图谱，星点可用触控或回车选择' }, ui.stage); ui.drawing = svg('g', {}, ui.svg);
    ui.gemName = element('h2', 'afb-gem-name', ui.stage); ui.gemHost = element('div', 'afb-gem', ui.stage); ui.gemHost.hidden = true;
    var pager = element('div', 'afb-pager', root); ui.previous = button('‹ 上页', function () { changePage(-1); }, pager); ui.page = element('span', '', pager); ui.next = button('下页 ›', function () { changePage(1); }, pager); ui.context = element('span', 'afb-context', pager);
    var clock = element('div', 'afb-clock', root); ui.chapter = element('select', '', clock); ui.chapter.setAttribute('aria-label', '选择章节'); ui.cursor = element('input', '', clock); ui.cursor.type = 'range'; ui.cursor.min = 0; ui.cursor.value = 0; ui.cursor.setAttribute('aria-label', '选择叙事事件'); ui.cursorText = element('span', '', clock, '全书');
    ui.status = element('p', 'afb-status', root); ui.status.setAttribute('role', 'status');
    ui.evidence = element('aside', 'afb-evidence', root); ui.evidence.hidden = true; ui.evidence.setAttribute('aria-label', '来源与原始记录'); ui.evidenceClose = button('关闭', function () { ui.evidence.hidden = true; }, ui.evidence); ui.evidenceTitle = element('h2', '', ui.evidence); ui.evidenceBody = element('div', '', ui.evidence);
    ui.file.addEventListener('change', function () { var file = ui.file.files[0]; if (!file) return; var ticket = ++generation; if (request) request.abort(); sourceURL = ''; file.text().then(function (s) { if (ticket === generation) load(JSON.parse(s)); }).catch(function (e) { if (ticket !== generation) return; error = 'JSON 无法读取：' + e.message; loading = false; render(); }); });
    ui.cursor.addEventListener('input', function () { if (G && G.events.length) selectEvent(Number(this.value)); });
    ui.chapter.addEventListener('change', function () { state.chapter = this.value === '' ? null : A.chapters[Number(this.value)].name; var es = G.events.map(function (e, i) { return e.chapter === state.chapter ? i : -1; }).filter(function (i) { return i >= 0; }); state.range = es.length ? [es[0], es[es.length - 1]] : null; state.event = es.length ? es[0] : null; state.page = 0; camera(); render(); });
    ui.svg.addEventListener('click', function (e) { var target = e.target.closest('[data-action]'); if (target && actions[Number(target.dataset.action)]) actions[Number(target.dataset.action)](); });
    bindPan(); document.addEventListener('keydown', onKey, true); document.addEventListener('cl:radar-axis-select', axisEvidence); g.addEventListener('resize', onResize);
    render(); var q = options.query instanceof URLSearchParams ? options.query : new URLSearchParams(typeof options.query === 'string' ? options.query : location.search);
    var url = q.get('data') || (q.get('demo') === '1' ? 'data/sample-saga.json' : null); if (url) fetchGraph(url);
    return api;
  }
  function stop() { generation++; if (request) request.abort(); request = null; clearTimeout(resizeTimer); document.removeEventListener('keydown', onKey, true); document.removeEventListener('cl:radar-axis-select', axisEvidence); g.removeEventListener('resize', onResize); if (g.CLGemSVG) g.CLGemSVG.unmount(); if (root) root.remove(); root = null; ui = {}; G = null; A = null; tree = null; gem = null; records = null; actions = []; loading = false; error = ''; document.body.classList.remove('atlas-2d'); }
  function stats() { return { active: !!root, renderer: 'svg-2d', loading: loading, error: error, view: state.view, page: state.page || 0, selectedCharacter: state.character, selectedEvent: state.event, chapter: state.chapter, range: state.range && state.range.slice(), characters: G ? G.characters.length : 0, events: G ? G.events.length : 0, relations: G ? G.relations.length : 0, lines: A ? array(A.lines).length : 0, source: tree ? tree.src : null, gem: gem ? { scored: gem.scoredCount, narrativeKnown: gem.metaReady, stage: gem.stage.scope } : null, actionable: actions.length }; }
  var api = { start: start, stop: stop, load: load, loadURL: fetchGraph, setView: switchView, selectEvent: selectEvent, prepare: prepare, stats: stats };
  g.CLAtlasFallback = api;
})(window);
