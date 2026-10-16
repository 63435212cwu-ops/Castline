(function (g) {
  'use strict';
  var live = null, TYPES = { character: '人物', line: '故事线', event: '事件', task: '任务', clue: '伏笔', state: '人物状态', relation: '关系', location: '地点', item: '物品', rule: '世界规则', cause: '因果' };
  function arr(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return String(v == null ? '' : v).trim(); }
  function norm(v) { return str(v).toLocaleLowerCase(); }
  function index(graph, model) {
    graph = graph || {}; model = model || {};
    var out = [], events = arr(graph.events), byEvent = Object.create(null), seenLines = Object.create(null);
    events.forEach(function (e, i) { if (e.id != null) { var key = String(e.id); byEvent[key] = Object.prototype.hasOwnProperty.call(byEvent, key) ? null : i; } });
    function eventIndex(ids) { for (var i = 0; i < ids.length; i++) if (ids[i] != null && Object.prototype.hasOwnProperty.call(byEvent, String(ids[i])) && byEvent[String(ids[i])] != null) return byEvent[String(ids[i])]; return null; }
    function add(type, raw, title, meta, body, ref, aliases, order) {
      out.push({ key: type + ':' + out.length, type: type, raw: raw, title: str(title) || '未命名' + TYPES[type], meta: str(meta), body: str(body), ref: ref || null, aliases: arr(aliases).map(str), order: order != null && isFinite(Number(order)) ? Number(order) : Infinity });
    }
    arr(graph.characters).forEach(function (c) { add('character', c, c.name, [c.role, c.camp, c.identity].filter(Boolean).join(' · '), [c.brief, arr(c.traits).join(' ')].join(' '), { name: c.name }, c.aliases); });
    arr(model.mains).concat(arr(model.lines)).forEach(function (l) {
      if (seenLines[String(l.id)]) return; seenLines[String(l.id)] = true;
      var first = events[arr(l.events)[0]];
      add('line', l, l.fullLabel || l.label || l.title, (arr(model.mains).indexOf(l) >= 0 ? '主线' : '支线') + ' · ' + (l.cast || []).join('、'), l.theme || l.title, { lineId: String(l.id) }, [], first && first.order);
    });
    arr(graph.storylines).forEach(function (l) {
      if (seenLines[String(l.id)]) return;
      add('line', l, l.name || l.title, [l.kind, l.lead].filter(Boolean).join(' · '), l.theme, null, [], null);
    });
    events.forEach(function (e, i) { add('event', e, e.title, [e.chapter, e.kind, arr(e.characters).join('、')].filter(Boolean).join(' · '), e.summary, { eventIndex: i }, [], e.order); });
    function statusText(code) {
      var map = g.CLSkyStatusText;
      return code == null ? null : map && map.label ? map.label('mechanic', code) : code;
    }
    function auxiliary(type, values, refs) { arr(values).forEach(function (x) {
      var ei = eventIndex(refs(x));
      add(type, x, x.name || x.title || x.character || x.summary || x.description, [x.character, x.chapter, statusText(x.status)].filter(Boolean).join(' · '),
        [x.goal, x.obstacle, x.action, x.outcome, x.cost, x.summary, x.description, x.rule, x.quote].filter(Boolean).join(' · '), ei == null ? null : { eventIndex: ei }, [], ei == null ? null : events[ei].order);
    }); }
    auxiliary('task', graph.tasks, function (x) { return arr(x.eventIds); });
    auxiliary('clue', graph.clues, function (x) { return [x.seedEventId, x.payoffEventId]; });
    auxiliary('state', arr(graph.characterStates).length ? graph.characterStates : graph.states, function (x) { return [x.eventId]; });
    auxiliary('cause', graph.causeEdges, function (x) { return [x.fromEventId || x.sourceId, x.toEventId || x.targetId]; });
    auxiliary('location', graph.locations, function (x) { return arr(x.eventIds); });
    auxiliary('item', graph.items, function (x) { return arr(x.eventIds); });
    auxiliary('rule', graph.worldRules, function (x) { return arr(x.eventIds); });
    arr(graph.relations).forEach(function (r) { add('relation', r, r.a + ' × ' + r.b, [r.kind, r.line].filter(Boolean).join(' · '), r.desc || r.description, null); });
    return out;
  }
  function match(rows, query, type, sort) {
    var q = norm(query), all = [], counts = Object.create(null);
    rows.forEach(function (row) {
      var title = norm(row.title), aliases = row.aliases.map(norm), full = norm(row.title + ' ' + row.meta + ' ' + row.body + ' ' + row.aliases.join(' '));
      if (q && full.indexOf(q) < 0) return;
      var rank = !q ? 3 : title === q || aliases.indexOf(q) >= 0 ? 0 : title.indexOf(q) === 0 ? 1 : title.indexOf(q) >= 0 ? 2 : 3;
      all.push({ row: row, rank: rank, alias: q ? row.aliases.filter(function (a) { return norm(a).indexOf(q) >= 0; }).join('、') : '' });
      counts[row.type] = (counts[row.type] || 0) + 1;
    });
    var filtered = all.filter(function (x) { return !type || type === 'all' || x.row.type === type; });
    filtered.sort(function (a, b) {
      if (sort === 'time' && a.row.order !== b.row.order) return a.row.order < b.row.order ? -1 : 1;
      if (sort !== 'name' && sort !== 'time' && a.rank !== b.rank) return a.rank - b.rank;
      return a.row.title.localeCompare(b.row.title, 'zh') || a.row.type.localeCompare(b.row.type) || a.row.key.localeCompare(b.row.key);
    });
    return { all: all.length, rows: filtered, counts: counts };
  }
  function create(opts) {
    var doc = opts.input.ownerDocument, input = opts.input, root = doc.createElement('section'), opened = false, rows = [], graphRef = null, modelRef = null,
      results = { all: 0, rows: [], counts: {} }, at = -1, page = 0, timer = null, type = 'all', sort = 'match', detail = null;
    root.id = 'skySearchPanel'; root.className = 'sky-search-panel'; root.hidden = true; root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'false'); root.setAttribute('aria-labelledby', 'skySearchTitle');
    function mk(tag, cls, parent, value) { var e = doc.createElement(tag); if (cls) e.className = cls; if (value != null) e.textContent = value; if (parent) parent.appendChild(e); return e; }
    var head = mk('header', 'sks-head', root); mk('b', '', head, '搜索候选').id = 'skySearchTitle';
    var closeBtn = mk('button', '', head, '关闭'); closeBtn.type = 'button'; closeBtn.setAttribute('aria-label', '关闭搜索候选');
    var queryLabel = mk('label', 'sks-query', root); mk('span', '', queryLabel, '检索');
    var queryInput = mk('input', '', queryLabel); queryInput.type = 'search'; queryInput.id = 'skySearchQuery'; queryInput.placeholder = '人物 / 事件 / 任务'; queryInput.autocomplete = 'off';
    var controls = mk('div', 'sks-controls', root), filter = mk('select', '', controls), sorting = mk('select', '', controls);
    filter.setAttribute('aria-label', '筛选搜索实体类型'); sorting.setAttribute('aria-label', '搜索排序');
    Object.keys({ all: '全部' }).concat(Object.keys(TYPES)).forEach(function (k) { var o = mk('option', '', filter, k === 'all' ? '全部' : TYPES[k]); o.value = k; });
    [['match', '匹配优先'], ['name', '名称排序'], ['time', '事件顺序']].forEach(function (x) { var o = mk('option', '', sorting, x[1]); o.value = x[0]; });
    var count = mk('p', 'sks-count', root); count.id = 'skySearchCount'; count.setAttribute('role', 'status'); count.setAttribute('aria-live', 'polite');
    var list = mk('div', 'sks-list', root); list.id = 'skySearchResults'; list.setAttribute('role', 'listbox'); list.setAttribute('aria-label', '搜索候选列表'); list.tabIndex = 0;
    var details = mk('section', 'sks-detail', root); details.hidden = true; details.setAttribute('role', 'region'); details.setAttribute('aria-labelledby', 'skySearchDetailTitle'); details.tabIndex = -1;
    var detailHead = mk('div', 'sks-detail-head', details);
    mk('h3', 'sks-detail-title', detailHead, '候选详情').id = 'skySearchDetailTitle';
    var detailBack = mk('button', 'sks-detail-back', detailHead, '返回候选'); detailBack.type = 'button';
    var detailsBody = mk('p', 'sks-detail-body', details);
    var pager = mk('div', 'sks-pager', root), prev = mk('button', '', pager, '上一页'), next = mk('button', '', pager, '下一页'); prev.type = next.type = 'button';
    mk('p', 'sks-empty', root, '输入检索；上下选择，Enter 确认；Esc 收起。'); doc.body.appendChild(root);
    [input, queryInput].forEach(function (field) { field.setAttribute('role', 'combobox'); field.setAttribute('aria-autocomplete', 'list'); field.setAttribute('aria-haspopup', 'listbox'); field.setAttribute('aria-controls', list.id); field.setAttribute('aria-describedby', count.id); field.setAttribute('aria-expanded', 'false'); });
    function clearActive() { input.removeAttribute('aria-activedescendant'); queryInput.removeAttribute('aria-activedescendant'); list.removeAttribute('aria-activedescendant'); }
    function render() {
      list.textContent = ''; clearActive(); var start = page * 50, end = Math.min(results.rows.length, start + 50);
      for (var i = start; i < end; i++) {
        var x = results.rows[i], e = mk('button', 'sks-option', list); e.type = 'button'; e.tabIndex = -1; e.id = 'skySearchOption-' + i;
        e.setAttribute('role', 'option'); e.setAttribute('aria-selected', i === at ? 'true' : 'false'); e.setAttribute('aria-posinset', i + 1); e.setAttribute('aria-setsize', results.rows.length); e.dataset.index = String(i);
        mk('span', 'sks-kind', e, TYPES[x.row.type]); var body = mk('span', '', e); mk('b', 'sks-title', body, x.row.title);
        mk('small', 'sks-meta', body, [x.alias ? '别名命中：' + x.alias : '', x.row.meta, x.row.ref ? '确认后定位' : '查看记录 · 无可定位关联'].filter(Boolean).join(' · '));
        if (i === at) { input.setAttribute('aria-activedescendant', e.id); queryInput.setAttribute('aria-activedescendant', e.id); list.setAttribute('aria-activedescendant', e.id); }
      }
      if (!results.rows.length) mk('p', 'sks-empty', list, '没有匹配候选；可切换类型或修改关键词。');
      count.textContent = '共匹配 ' + results.all + ' 条 · 当前类型 ' + results.rows.length + ' 条 · ' + (results.rows.length ? (start + 1) + '–' + end : '0') + ' / ' + results.rows.length;
      Array.prototype.forEach.call(filter.options, function (o) { var k = o.value; o.textContent = k === 'all' ? '全部 · ' + results.all : TYPES[k] + ' · ' + (results.counts[k] || 0); });
      prev.disabled = page === 0; next.disabled = end >= results.rows.length; pager.hidden = results.rows.length <= 50;
      details.hidden = !detail; detailsBody.textContent = detail || '';
    }
    function refresh(reset) {
      var d = opts.data() || {};
      if (d.graph !== graphRef || d.model !== modelRef) { graphRef = d.graph; modelRef = d.model; rows = index(graphRef, modelRef); reset = true; }
      results = match(rows, input.value, type, sort);
      if (reset) { at = -1; page = 0; detail = null; }
      page = Math.min(page, Math.max(0, Math.ceil(results.rows.length / 50) - 1)); render();
    }
    function open(q) {
      if (q != null) input.value = str(q); queryInput.value = input.value;
      opened = true; root.hidden = false; input.setAttribute('aria-expanded', 'true'); queryInput.setAttribute('aria-expanded', 'true'); refresh(true);
      if (g.matchMedia && g.matchMedia('(max-height: 500px)').matches) {
        g.setTimeout(function () {
          if (opened && !root.hidden && doc.activeElement === input) {
            queryInput.focus({ preventScroll: true });
            queryInput.scrollIntoView({ block: 'nearest', inline: 'nearest' });
          }
        }, 0);
      }
    }
    function close(refocus) { opened = false; root.hidden = true; input.setAttribute('aria-expanded', 'false'); queryInput.setAttribute('aria-expanded', 'false'); clearActive(); if (refocus) input.focus({ preventScroll: true }); }
    function select(i) {
      var x = results.rows[i]; if (!x) return; at = i;
      if (x.row.ref && opts.onPick(x.row) !== false) { close(true); return; }
      detail = TYPES[x.row.type] + ' · ' + x.row.title + '\n' + [x.row.meta, x.row.body, '未提供可定位的有效关联；保持当前图谱。'].filter(Boolean).join('\n'); render();
      if (details && details.focus) details.focus({ preventScroll: true });
      if (details && details.scrollIntoView) details.scrollIntoView({ block: 'start', inline: 'nearest' });
    }
    function owns(e) {
      if (!opened || e.ctrlKey || e.metaKey || e.altKey || e.isComposing || g.CLModal && CLModal.open && CLModal.open()) return false;
      var t = e.target;
      if (t && t.tagName === 'SELECT' && e.key !== 'Escape') return false;
      if (t === input || t === queryInput) return /^(ArrowUp|ArrowDown|Home|End|Enter|Escape)$/.test(e.key);
      return t === list && /^(ArrowUp|ArrowDown|Home|End|Enter| |Escape)$/.test(e.key) || t && t.nodeType && root.contains(t) && /^(Arrow(Up|Down|Left|Right)|Home|End|Enter| |Escape)$/.test(e.key);
    }
    function handle(e) {
      if (!owns(e)) return false;
      if (e.key === 'Escape') { e.stopImmediatePropagation(); e.preventDefault(); close(true); return true; }
      if (e.target !== input && e.target !== queryInput && e.target !== list) return true;
      e.stopImmediatePropagation(); e.preventDefault();
      if (timer) { g.clearTimeout(timer); timer = null; open(); }
      if (e.key === 'Enter' || e.key === ' ') { if (at >= 0) select(at); else { refresh(true); count.textContent += ' · 请用上下键或点击明确选择。'; } return true; }
      if (!/^(ArrowUp|ArrowDown|Home|End)$/.test(e.key)) return true;
      if (!results.rows.length) return true;
      at = e.key === 'Home' ? 0 : e.key === 'End' ? results.rows.length - 1 : e.key === 'ArrowDown' ? Math.min(results.rows.length - 1, at + 1) : at < 0 ? results.rows.length - 1 : Math.max(0, at - 1);
      page = Math.floor(at / 50); render(); var selected = doc.getElementById('skySearchOption-' + at); if (selected) selected.scrollIntoView({ block: 'nearest' }); return true;
    }
    input.addEventListener('input', function () { if (timer) g.clearTimeout(timer); timer = g.setTimeout(function () { timer = null; open(); }, 80); });
    queryInput.addEventListener('input', function () { input.value = queryInput.value; if (timer) g.clearTimeout(timer); timer = g.setTimeout(function () { timer = null; open(); }, 80); });
    closeBtn.addEventListener('click', function () { close(true); });
    detailBack.addEventListener('click', function () {
      detail = null; render(); list.focus({ preventScroll: true });
      var selected = doc.getElementById('skySearchOption-' + at);
      if (selected && selected.scrollIntoView) selected.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });
    filter.addEventListener('change', function () { type = filter.value; refresh(true); }); sorting.addEventListener('change', function () { sort = sorting.value; refresh(true); });
    prev.addEventListener('click', function () { page--; at = -1; detail = null; render(); }); next.addEventListener('click', function () { page++; at = -1; detail = null; render(); });
    list.addEventListener('click', function (e) { var el = e.target.closest && e.target.closest('[data-index]'); if (el) select(+el.dataset.index); });
    root.addEventListener('keydown', function (e) { if (opened && e.target && e.target.closest && e.target.closest('button')) e.stopPropagation(); });
    doc.addEventListener('pointerdown', function (e) { if (opened && !root.contains(e.target) && !opts.container.contains(e.target)) close(false); }, true);
    doc.addEventListener('cl:graph-loading', function () { close(false); graphRef = modelRef = null; });
    live = { open: open, close: close, handlesKey: owns, handleKey: handle, stats: function () { return { open: opened, total: results.all, filtered: results.rows.length, page: page, active: at, type: type, sort: sort, rendered: list.querySelectorAll('[role=option]').length }; } };
    return live;
  }
  g.CLSkySearch = { create: create, index: index, match: match, types: TYPES, handlesKey: function (e) { return !!(live && live.handlesKey(e)); }, handleKey: function (e) { return !!(live && live.handleKey(e)); }, open: function (q) { if (live) live.open(q); }, stats: function () { return live && live.stats(); } };
})(window);
