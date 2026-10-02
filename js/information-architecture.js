/* 信息预览：只读投影、摘要预算、逐级查看。评分和推导不冒充原文证据。 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var root = $('infoArchitecture'), trigger = $('btnInfo');
  if (!root || !trigger) return;
  var ATTRS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var state = { view: 'atlas', query: '', limits: { cast: 6, threads: 6, relations: 6 }, detail: null, detailLimit: 12 };
  var model = null, returnFocus = null, inertSiblings = [], focusTimer = null, searchTimer = null, detailFocus = null;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function str(s) { return String(s == null ? '' : s).trim(); }
  function finite(v) { return v !== null && v !== undefined && v !== '' && isFinite(Number(v)); }
  function num(v) { return finite(v) ? Number(v) : 0; }
  function arr(a) { return Array.isArray(a) ? a : []; }
  function tone(k) {
    if (k === '主线') return 'var(--ia-amber)';
    if (k === '支线') return 'var(--ia-violet)';
    return window.CLPalette ? CLPalette.css(k, 'var(--ia-violet)') : 'var(--ia-violet)';
  }
  // 动态图表数据单独赋予自定义属性；静态视觉规则留在 CSS 中。
  function encodeValues() {
    root.querySelectorAll('[data-ia-tone]').forEach(function (el) { el.style.setProperty('--tone', tone(el.dataset.iaTone)); });
    root.querySelectorAll('[data-ia-value]').forEach(function (el) { el.style.setProperty('--ia-value', Math.max(0, Math.min(100, num(el.dataset.iaValue))) + '%'); });
  }
  function matches(s) { return !state.query || str(s).toLowerCase().indexOf(state.query) >= 0; }
  function empty(message) { return '<p class="ia-thread-empty">' + esc(message) + '</p>'; }
  function attr(c, key) { var a = c.attrs && c.attrs[key]; return a && !a.pending && finite(a.score) ? a : null; }
  function source(t) { return t.src === 'model' ? '图谱提供 · 未等同人工确认' : t.src === 'derived' ? '算法推导 · 待核对' : '来源未提供'; }
  function status(t) { return t.resolved ? '收束' : t.suspended ? '悬置' : '状态未提供'; }
  function refreshModel() {
    var g = window.CLApp && CLApp.graph();
    if (model && model.graph === g) return model;
    state.detail = null; state.detailLimit = 12; state.limits = { cast: 6, threads: 6, relations: 6 };
    state.query = ''; $('iaSearch').value = '';
    if (!g) { model = null; return null; }
    var ev = arr(g.events).slice().sort(function (a, b) { return num(a.order) - num(b.order); });
    var chapters = [], chapterMap = Object.create(null), counts = Object.create(null), kinds = Object.create(null);
    ev.forEach(function (e, i) {
      var name = str(e.chapter) || '未分章', c = chapterMap[name];
      if (!c) { c = { name: name, indices: [], kinds: Object.create(null) }; chapterMap[name] = c; chapters.push(c); }
      c.indices.push(i); var k = str(e.kind) || '未提供'; c.kinds[k] = (c.kinds[k] || 0) + 1; kinds[k] = (kinds[k] || 0) + 1;
      arr(e.characters).forEach(function (n) { counts[n] = (counts[n] || 0) + 1; });
    });
    var story = CLApp.story ? CLApp.story() : null;
    model = { graph: g, events: ev, chapters: chapters, eventCounts: counts, kinds: kinds,
      cast: arr(g.characters).slice().sort(function (a, b) { return num(b.importance) - num(a.importance) || (counts[b.name] || 0) - (counts[a.name] || 0); }),
      threads: arr(story && story.threads), relations: arr(g.relations), story: story };
    return model;
  }
  function eventAt(i) { return model && model.events[Number(i)]; }
  function threadIndices(t) { return arr(t.events).filter(function (i) { return !!eventAt(i); }); }
  function moreButton(key, shown, total) {
    var b = root.querySelector('[data-ia-more="' + key + '"]'), collapse = shown >= total && state.limits[key] > 6 && total > 6;
    b.hidden = shown >= total && !collapse; b.dataset.iaCollapse = collapse ? '1' : '0';
    b.textContent = collapse ? '收起列表 · 保留前 6 条' : '加载更多 · 还有 ' + Math.max(0, total - shown) + ' 条';
  }
  function renderKpis() {
    var m = model, scored = 0, cited = 0, total = m.cast.length * ATTRS.length;
    m.cast.forEach(function (c) { ATTRS.forEach(function (k) { var a = attr(c, k); if (a) { scored++; if (arr(a.evidence).some(function (q) { return !!str(q); })) cited++; } }); });
    var main = m.threads.filter(function (t) { return t.kind === 'main'; }).length, derived = m.threads.filter(function (t) { return t.src === 'derived'; }).length;
    var rows = [['角色', m.cast.length, '已载入图谱人物'], ['事件', m.events.length, '抽取记录 · 非全部原文'],
      ['主 / 支线', main + ' / ' + (m.threads.length - main), derived ? derived + ' 条算法推导' : '图谱声明分类'],
      ['关系', m.relations.length, m.relations.filter(function (r) { return r.line === '暗线'; }).length + ' 条暗线'],
      ['章节', m.chapters.length, '事件中出现的章节'], ['属性已评分', total ? Math.round(scored / total * 100) + '%' : '—', scored + '/' + total + ' 维 · 附引文 ' + cited]];
    $('iaKpis').innerHTML = rows.map(function (x) { return '<div class="ia-kpi"><span class="ia-kpi-label">' + esc(x[0]) + '</span><strong class="ia-kpi-value">' + esc(x[1]) + '</strong><span class="ia-kpi-note">' + esc(x[2]) + '</span></div>'; }).join('');
  }
  function renderSpine() {
    var list = model.events.map(function (e, i) { return { e: e, i: i }; }).filter(function (x) { return matches([x.e.title, x.e.chapter, x.e.summary, arr(x.e.characters).join(' ')].join(' ')); });
    var sample = [], n = Math.min(6, list.length);
    for (var j = 0; j < n; j++) sample.push(list[n === 1 ? 0 : Math.round(j * (list.length - 1) / (n - 1))]);
    $('iaSpine').innerHTML = sample.length ? '<div class="ia-spine-track">' + sample.map(function (x) { return '<button type="button" class="ia-spine-point" data-ia-detail="event" data-ia-id="' + x.i + '" data-ia-tone="' + esc(x.e.kind) + '" title="' + esc(x.e.title) + '"><span class="ia-spine-label"><b>' + esc(x.e.title || '未命名事件') + '</b>' + esc(x.e.chapter || '未分章') + '</span></button>'; }).join('') + '</div>' : empty('没有匹配的事件');
    $('iaSpineStat').textContent = '抽样 ' + sample.length + ' / ' + list.length + ' 事件';
    $('iaKindLegend').innerHTML = Object.keys(model.kinds).map(function (k) { return '<span data-ia-tone="' + esc(k) + '">' + esc(k) + ' ' + model.kinds[k] + '</span>'; }).join('');
  }
  function renderCast() {
    var list = model.cast.filter(function (c) { return matches([c.name, c.role, c.identity, c.camp, arr(c.aliases).join(' ')].join(' ')); }), shown = list.slice(0, state.limits.cast);
    $('iaCast').innerHTML = shown.length ? shown.map(function (c, i) { return '<button type="button" class="ia-cast-row" data-ia-detail="character" data-ia-id="' + esc(c.name) + '"><span class="ia-cast-rank">' + (i + 1) + '</span><span class="ia-cast-name">' + esc(c.name) + '<small>' + esc((c.role || '未提供') + ' · ' + (c.camp || '未分群') + ' · ' + (model.eventCounts[c.name] || 0) + ' 事') + '</small></span><span class="ia-cast-bar"><i data-ia-value="' + Math.max(0, Math.min(100, num(c.importance))) + '"></i></span><span class="ia-cast-score">' + Math.round(num(c.importance)) + '</span></button>'; }).join('') : empty('没有匹配的角色');
    $('iaCastStat').textContent = '显示 ' + shown.length + ' / ' + list.length + ' 人'; moreButton('cast', shown.length, list.length);
  }
  function renderThreads() {
    var list = model.threads.filter(function (t) { return matches([t.title, t.lead, t.theme, threadIndices(t).map(function (i) { var e = eventAt(i); return e.title + ' ' + e.chapter + ' ' + arr(e.characters).join(' '); }).join(' ')].join(' ')); });
    var shown = list.slice(0, state.limits.threads), max = list.reduce(function (v, t) { return Math.max(v, threadIndices(t).length); }, 1);
    $('iaThreads').innerHTML = shown.length ? shown.map(function (t) {
      var inds = threadIndices(t), first = eventAt(inds[0]), last = eventAt(inds[inds.length - 1]), main = t.kind === 'main';
      return '<button type="button" class="ia-thread" data-ia-detail="thread" data-ia-id="' + esc(t.id) + '" data-ia-tone="' + (main ? '主线' : '支线') + '"><span class="ia-thread-main"><b class="ia-thread-title">' + esc(t.title || '未命名线') + '</b><small class="ia-thread-meta">' + esc((main ? '主线' : '支线') + ' · ' + (t.lead || '主导未提供') + ' · ' + status(t)) + '</small><small class="ia-thread-meta">' + esc((first ? first.chapter : '—') + ' → ' + (last ? last.chapter : '—')) + '</small></span><span class="ia-thread-meter"><i data-ia-value="' + Math.round(inds.length / max * 100) + '"></i><span>' + inds.length + ' 事</span></span></button>';
    }).join('') : empty('暂无匹配剧情线 · 不补造父子关系');
    $('iaThreadStat').textContent = '显示 ' + shown.length + ' / ' + list.length + ' 线'; moreButton('threads', shown.length, list.length);
  }
  function renderRelations() {
    var list = model.relations.map(function (r, i) { return { r: r, i: i }; }).filter(function (x) { return matches([x.r.a, x.r.b, x.r.kind, x.r.desc, x.r.hidden, x.r.line].join(' ')); });
    var shown = list.slice(0, state.limits.relations), dark = model.relations.filter(function (r) { return r.line === '暗线'; }).length;
    $('iaRelSummary').innerHTML = [['全部', model.relations.length], ['明线', model.relations.length - dark], ['暗线', dark]].map(function (x) { return '<div class="ia-rel-stat"><b>' + x[1] + '</b><span>' + x[0] + '</span></div>'; }).join('');
    $('iaRelations').innerHTML = shown.length ? shown.map(function (x) {
      var r = x.r, known = finite(r.strength) && r.strengthProvided !== false;
      return '<button type="button" class="ia-rel" data-ia-detail="relation" data-ia-id="' + x.i + '" data-ia-tone="' + (r.line === '暗线' ? '支线' : '主线') + '"><span><strong>' + esc(r.a + ' × ' + r.b) + '</strong><small>' + esc((r.line || '线型未提供') + ' · ' + (r.kind || '类型未提供')) + '</small></span>' + (known ? '<span class="ia-rel-meter" title="图谱强度 ' + num(r.strength) + '"><i data-ia-value="' + Math.round(Math.max(0, Math.min(1, num(r.strength))) * 100) + '"></i></span>' : '<span title="未提供关系强度">—</span>') + '</button>';
    }).join('') : empty('没有匹配的关系');
    $('iaRelStat').textContent = '显示 ' + shown.length + ' / ' + list.length + ' 条'; moreButton('relations', shown.length, list.length);
  }
  function renderAttrs() {
    var cited = 0;
    $('iaAttrs').innerHTML = ATTRS.map(function (k) {
      var ranked = model.cast.filter(function (c) { return !!attr(c, k); }).sort(function (a, b) { return num(attr(b, k).score) - num(attr(a, k).score); }), c = ranked[0], a = c && attr(c, k);
      if (!matches(k + ' ' + (c ? c.name : '待建档'))) return '';
      if (a && arr(a.evidence).length) cited++;
      return '<button type="button" class="ia-attr' + (c ? '' : ' ia-attr-pending') + '" data-ia-detail="attribute" data-ia-id="' + esc(k) + '"><span class="ia-attr-label">' + k + '</span><span class="ia-attr-main"><b>' + esc(c ? c.name : '待建档') + '</b><i data-ia-value="' + (a ? Math.max(0, Math.min(100, num(a.score))) : 0) + '"></i></span><span class="ia-attr-score">' + (a ? Math.round(num(a.score)) : '—') + '</span></button>';
    }).join('');
    $('iaAttrStat').textContent = '榜首附引文 ' + cited + ' / 8 · 未全文核验';
  }
  function chapterBins() {
    var matching = model.chapters.filter(function (c) { return matches(c.name + ' ' + c.indices.map(function (i) { return eventAt(i).title; }).join(' ')); });
    var bins = [], size = Math.max(1, Math.ceil(matching.length / 48));
    for (var i = 0; i < matching.length; i += size) {
      var chunk = matching.slice(i, i + size), kinds = Object.create(null), indices = [];
      chunk.forEach(function (c) { indices = indices.concat(c.indices); Object.keys(c.kinds).forEach(function (k) { kinds[k] = (kinds[k] || 0) + c.kinds[k]; }); });
      bins.push({ label: chunk[0].name + (chunk.length > 1 ? ' … ' + chunk[chunk.length - 1].name : ''), chapterCount: chunk.length, indices: indices, kinds: kinds });
    }
    return { bins: bins, count: matching.length };
  }
  function renderChapters() {
    var summary = chapterBins(), bins = summary.bins, max = bins.reduce(function (v, b) { return Math.max(v, b.indices.length); }, 1);
    $('iaChapters').innerHTML = bins.length ? bins.map(function (b, i) {
      var dominant = Object.keys(b.kinds).sort(function (a, c) { return b.kinds[c] - b.kinds[a]; })[0], title = b.label + ' · ' + b.chapterCount + ' 章 · ' + b.indices.length + ' 事';
      return '<button type="button" class="ia-chapter" data-ia-detail="chapter" data-ia-id="' + i + '" data-ia-tone="' + esc(dominant) + '" aria-label="' + esc(title) + '" title="' + esc(title) + '"><span class="ia-chapter-bar" data-ia-value="' + Math.max(4, Math.round(b.indices.length / max * 100)) + '"></span><span class="ia-chapter-tip"><b>' + esc(b.label) + '</b>' + b.indices.length + ' 事 · ' + b.chapterCount + ' 章</span></button>';
    }).join('') : empty('暂无匹配章节');
    $('iaChapterAxis').innerHTML = bins.length ? '<span>' + esc(bins[0].label) + '</span><span>每组峰值 ' + max + ' 事</span><span>' + esc(bins[bins.length - 1].label) + '</span>' : '';
    $('iaChapterStat').textContent = summary.count + ' 章 / ' + bins.length + ' 组';
  }
  function render() {
    var m = refreshModel();
    if (!m) {
      $('iaTitle').textContent = '等待图谱接入'; $('iaSynopsis').textContent = '载入示例或分析材料后预览；此面板不发起模型调用。';
      ['iaKpis', 'iaKindLegend', 'iaRelSummary', 'iaChapterAxis'].forEach(function (id) { $(id).innerHTML = ''; });
      ['iaSpine', 'iaCast', 'iaThreads', 'iaRelations', 'iaAttrs', 'iaChapters'].forEach(function (id) { $(id).innerHTML = empty('未载入图谱'); });
      ['iaSpineStat', 'iaCastStat', 'iaThreadStat', 'iaRelStat', 'iaAttrStat', 'iaChapterStat', 'iaSource', 'iaToolbarMeta'].forEach(function (id) { $(id).textContent = '未提供'; });
      root.querySelectorAll('[data-ia-more]').forEach(function (b) { b.hidden = true; });
    } else {
      var g = m.graph, meta = g.meta || {}, derived = m.threads.some(function (t) { return t.src === 'derived'; });
      $('iaTitle').textContent = str(g.title) || '未命名作品'; $('iaSynopsis').textContent = str(g.synopsis) || '梗概未提供';
      $('iaSource').textContent = [meta.model ? '模型 ' + meta.model : '模型未提供', meta.analyzed_at || '', '未验证整本原文覆盖率'].filter(Boolean).join(' · ');
      $('iaToolbarMeta').textContent = derived ? '含算法推导线 · 待核对' : '图谱声明 · 未等同人工确认';
      renderKpis(); renderSpine(); renderCast(); renderThreads(); renderRelations(); renderAttrs(); renderChapters(); encodeValues();
    }
    root.dataset.iaView = state.view;
    $('iaTrailText').textContent = state.query ? '检索「' + state.query + '」· 摘要 / 匹配数' : state.view === 'plot' ? '主支线 · 顺序 / 跨度 / 状态' : state.view === 'cast' ? '角色 · 重要度 / 关系 / 属性' : '全书摘要 · 六个阅读窗口';
    root.querySelectorAll('button[data-ia-view]').forEach(function (b) { var active = b.dataset.iaView === state.view; b.classList.toggle('active', active); b.setAttribute('aria-pressed', String(active)); });
    $('iaDetail').hidden = !state.detail;
  }
  function eventList(indices) {
    var visible = indices.slice(0, state.detailLimit);
    return visible.map(function (i) { var e = eventAt(i); return '<p><button class="btn" type="button" data-ia-detail="event" data-ia-id="' + i + '">' + esc((e.chapter || '未分章') + ' · ' + (e.title || '未命名事件')) + '</button></p>'; }).join('') + (visible.length < indices.length ? '<button class="ia-more" type="button" data-ia-detail-more>加载后续事件 · 剩余 ' + (indices.length - visible.length) + '</button>' : '');
  }
  function navigateButton(kind, id, label) { return '<p class="ia-detail-actions"><button type="button" class="btn" data-ia-navigate="' + kind + '" data-ia-id="' + esc(id) + '">' + esc(label) + '</button></p>'; }
  function renderDetail(focus) {
    var d = state.detail, title = '', h = '';
    if (!d || !model) return;
    if (d.kind === 'event') {
      var e = eventAt(d.id); if (!e) return;
      title = e.title || '未命名事件';
      h = '<p class="ia-detail-meta">' + esc((e.chapter || '未分章') + ' · ' + (e.kind || '类型未提供') + ' · ' + arr(e.characters).join(' / ')) + '</p><p>' + esc(e.summary || '摘要未提供') + '</p><h4>图谱记录的引文</h4>' + (str(e.quote) ? '<blockquote>' + esc(e.quote) + '</blockquote>' : '<p>未提供原文引句。</p>') + '<p class="ia-detail-note">此预览只读取记录，不重新核验引文与全文的逐字匹配。</p>' + navigateButton('event', e.order, '在角色详情中查看');
    } else if (d.kind === 'thread') {
      var t = model.threads.filter(function (x) { return x.id === d.id; })[0]; if (!t) return;
      var parent = model.threads.filter(function (x) { return x.id === t.parent; })[0];
      title = t.title || '未命名线'; h = '<p class="ia-detail-meta">' + esc(source(t) + ' · ' + status(t)) + '</p><p>' + esc(t.theme || '主题未提供') + '</p><p>父线：' + esc(t.anchored ? '仅为就近视觉挂点，不代表已确认因果' : parent ? parent.title : t.kind === 'main' ? '主线无需父线' : '未提供') + '</p>' + (t.pendingReason ? '<p>' + esc(t.pendingReason) + '</p>' : '') + navigateButton('line', t.id, '在展卷中定位此线') + '<h4>全部归属事件 · ' + threadIndices(t).length + ' 条</h4>' + eventList(threadIndices(t));
    } else if (d.kind === 'character') {
      var c = model.cast.filter(function (x) { return x.name === d.id; })[0]; if (!c) return;
      title = c.name; h = '<p>' + esc(c.identity || c.role || '身份未提供') + '</p><p>' + esc(c.brief || '简介未提供') + '</p><p>属性已评分 ' + ATTRS.filter(function (k) { return attr(c, k); }).length + '/8 维；未知维不补默认分。</p>' + navigateButton('character', c.name, '进入角色星图与双晶详情');
      var indices = []; model.events.forEach(function (e, i) { if (arr(e.characters).indexOf(c.name) >= 0) indices.push(i); }); h += '<h4>参与事件 · ' + indices.length + ' 条</h4>' + eventList(indices);
    } else if (d.kind === 'relation') {
      var r = model.relations[Number(d.id)]; if (!r) return;
      title = r.a + ' × ' + r.b; h = '<p class="ia-detail-meta">' + esc((r.line || '线型未提供') + ' · ' + (r.kind || '类型未提供')) + '</p><p>' + esc(r.desc || '关系说明未提供') + '</p><p>暗线依据：' + esc(r.hidden || '未提供') + '</p><p>证据记录：' + esc(r.evidence || '未提供') + '</p>' + navigateButton('character', r.a, '进入「' + r.a + '」关系详情');
    } else if (d.kind === 'attribute') {
      title = d.id + ' · 全书属性榜首'; var ranked = model.cast.filter(function (c) { return attr(c, d.id); }).sort(function (a, b) { return num(attr(b, d.id).score) - num(attr(a, d.id).score); });
      h = '<p>排名有效分母 ' + ranked.length + ' 人；待建档不参与排名。</p>';
      if (ranked.length) { var leader = ranked[0], a = attr(leader, d.id); h += '<h4>' + esc(leader.name) + ' · ' + num(a.score) + '/100' + (a.low ? ' · 低证据' : '') + '</h4><p>' + esc(a.basis || '推断依据未提供') + '</p>' + arr(a.evidence).slice(0, state.detailLimit).map(function (q) { return '<blockquote>' + esc(q) + '</blockquote>'; }).join('') + navigateButton('character', leader.name, '进入角色查看全部属性依据'); } else h += empty('该维度暂无评分');
    } else if (d.kind === 'chapter') {
      var bin = chapterBins().bins[Number(d.id)]; if (!bin) return;
      title = bin.label; h = '<p>合并 ' + bin.chapterCount + ' 章，' + bin.indices.length + ' 个抽取事件。高度不是情绪强弱。</p>' + eventList(bin.indices);
    }
    $('iaDetailTitle').textContent = title; $('iaDetailBody').innerHTML = h; $('iaDetail').hidden = false;
    if (focus) { $('iaDetailTitle').focus({ preventScroll: true }); $('iaDetail').scrollIntoView({ block: 'nearest' }); }
  }
  function open() {
    if (isOpen()) return;
    returnFocus = document.activeElement; render(); root.classList.add('on'); root.setAttribute('aria-hidden', 'false'); document.body.classList.add('ia-open'); trigger.setAttribute('aria-expanded', 'true');
    inertSiblings = Array.prototype.filter.call(document.body.children, function (el) { return el !== root && !/^(SCRIPT|LINK|STYLE)$/.test(el.tagName); }).map(function (el) { var old = el.inert; el.inert = true; return { el: el, old: old }; });
    focusTimer = setTimeout(function () { if (isOpen()) $('iaClose').focus({ preventScroll: true }); }, 0);
  }
  function close(restore) {
    clearTimeout(focusTimer); clearTimeout(searchTimer); root.classList.remove('on'); root.setAttribute('aria-hidden', 'true'); document.body.classList.remove('ia-open'); trigger.setAttribute('aria-expanded', 'false');
    inertSiblings.forEach(function (x) { x.el.inert = x.old; }); inertSiblings = [];
    if (restore !== false && returnFocus && returnFocus.isConnected) returnFocus.focus({ preventScroll: true });
  }
  function isOpen() { return root.classList.contains('on'); }
  trigger.setAttribute('aria-controls', root.id); trigger.setAttribute('aria-expanded', 'false'); trigger.addEventListener('click', open);
  $('iaClose').addEventListener('click', function () { close(); });
  $('iaDetailClose').addEventListener('click', function () { state.detail = null; $('iaDetail').hidden = true; if (detailFocus && detailFocus.isConnected) detailFocus.focus(); });
  root.addEventListener('click', function (e) {
    var tab = e.target.closest('button[data-ia-view]'); if (tab) { state.view = tab.dataset.iaView; render(); return; }
    var more = e.target.closest('[data-ia-more]'); if (more) { state.limits[more.dataset.iaMore] = more.dataset.iaCollapse === '1' ? 6 : state.limits[more.dataset.iaMore] + 24; render(); return; }
    var detail = e.target.closest('[data-ia-detail]'); if (detail) { detailFocus = detail; state.detail = { kind: detail.dataset.iaDetail, id: detail.dataset.iaId }; state.detailLimit = 12; renderDetail(true); return; }
    if (e.target.closest('[data-ia-detail-more]')) { state.detailLimit += 24; renderDetail(false); return; }
    var nav = e.target.closest('[data-ia-navigate]');
    if (nav && window.CLApp && CLApp.inspect) { close(false); if (!CLApp.inspect({ type: nav.dataset.iaNavigate, id: nav.dataset.iaId })) { open(); $('iaDetailBody').insertAdjacentHTML('beforeend', '<p class="ia-detail-note">无法唯一定位此记录，请在本预览内查看。</p>'); } }
  });
  $('iaSearch').addEventListener('input', function () { clearTimeout(searchTimer); state.query = str(this.value).toLowerCase(); state.detail = null; searchTimer = setTimeout(render, 120); });
  root.addEventListener('keydown', function (e) {
    e.stopPropagation();
    if (e.key === 'Escape') { e.preventDefault(); if (state.detail) $('iaDetailClose').click(); else close(); }
    if (e.key === 'Tab') {
      var items = Array.prototype.filter.call(root.querySelectorAll('button:not([disabled]),input,[tabindex="0"]'), function (el) { return !!el.getClientRects().length; }), first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.CLInformationArchitecture = { open: open, close: close, refresh: render, isOpen: isOpen };
})();
