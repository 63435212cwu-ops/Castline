(function (g) {
  'use strict';

  var VERSION = '1';

  var TYPES = {
    character: { code: 'character', zh: '人物', hint: '人物名与正名。' },
    alias: { code: 'alias', zh: '别名', hint: '别名、称号、绰号。命中别名时必须同时给出正名，否则读者不知道这是谁。' },
    event: { code: 'event', zh: '事件', hint: '剧情点。上下文用章节。' },
    task: { code: 'task', zh: '任务', hint: '任务/目标。上下文用承担者与章节。' },
    storyline: { code: 'storyline', zh: '线路', hint: '故事线。上下文用跨度与主线/支线。' },
    unknown: { code: 'unknown', zh: '类型未标明', hint: '记录没有标明类型。' }
  };

  var NO_RESULT_REASONS = {
    no_match: { code: 'no_match', zh: '没有匹配项',
      hint: '查询词在当前图谱里没有匹配。可以换词，或到作品库换一个版本。' },
    empty_index: { code: 'empty_index', zh: '索引为空',
      hint: '当前版本没有可搜内容（可能尚未分析）。**这不等于"作品里没有"**。'
        + '下一步：到作品库换一个已分析的版本，或先对这个版本跑一次分析。' },
    broken_cache: { code: 'broken_cache', zh: '缓存损坏',
      hint: '图谱文件存在但读不出可用内容。下一步：到作品库重新分析，或换一个版本。' },
    filtered_out: { code: 'filtered_out', zh: '被筛选条件排除',
      hint: '有匹配项，但被当前筛选/范围排除。下一步：清掉筛选再搜。' },
    unavailable_version: { code: 'unavailable_version', zh: '版本不可用',
      hint: '当前选中的版本无法加载。下一步：在作品库里换一个版本。' }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function build(graph) {
    graph = graph || {};
    var items = [];
    (graph.characters || []).forEach(function (c) {
      if (!c) return;
      var key = c.id != null ? String(c.id) : (c.entityId != null ? String(c.entityId) : '');
      var name = str(c.name);
      if (!present(name) && !present(key)) return;
      items.push({
        type: 'character', key: key || ('name:' + name), label: name,
        context: [c.role, c.camp, c.identity].map(str).filter(Boolean).join(' · '),
        search: [name, c.role, c.camp, c.identity].map(str).join(' ')
      });
      arr(c.aliases).forEach(function (a) {
        if (!present(a)) return;
        items.push({
          type: 'alias', key: (key || ('name:' + name)) + '::alias::' + a, label: str(a),
          canonical: name, canonicalKey: key || ('name:' + name),
          context: (name ? '正名：' + name : '') + (c.role ? ' · ' + str(c.role) : ''),
          search: str(a), exact: str(a)
        });
      });
    });
    (graph.events || []).forEach(function (e, i) {
      if (!e) return;
      var key = e.id != null ? String(e.id) : (e.entityId != null ? String(e.entityId) : '#' + i);
      items.push({
        type: 'event', key: key,
        label: str(e.title) || str(e.summary) || '',
        context: str(e.chapter), search: [e.title, e.summary, e.chapter, e.kind].map(str).join(' ')
      });
    });
    (graph.tasks || []).forEach(function (t, i) {
      if (!t) return;
      var key = t.id != null ? String(t.id) : ('#' + i);
      items.push({
        type: 'task', key: key,
        label: str(t.name) || str(t.title) || str(t.goal) || '',
        context: [t.character, t.chapter].map(str).filter(Boolean).join(' · '),
        search: [t.name, t.title, t.goal, t.obstacle, t.action, t.result, t.character, t.chapter].map(str).join(' ')
      });
    });
    (graph.storylines || []).forEach(function (s, i) {
      if (!s) return;
      var key = s.id != null ? String(s.id) : ('#' + i);
      items.push({
        type: 'storyline', key: key,
        label: str(s.name) || str(s.title) || str(s.theme) || '',
        context: [s.kind, s.lead].map(str).filter(Boolean).join(' · '),
        search: [s.name, s.title, s.theme, s.kind, s.lead].map(str).join(' ')
      });
    });
    return items;
  }

  function arr(v) { return Array.isArray(v) ? v : []; }

  function search(index, query, opts) {
    opts = opts || {};
    var items = Array.isArray(index) ? index : [];
    var q = str(query).trim().toLocaleLowerCase();
    if (!items.length) {
      var why = NO_RESULT_REASONS[opts.status] ? opts.status
        : (opts.broken ? 'broken_cache' : opts.unavailable ? 'unavailable_version' : 'empty_index');
      return noResult(why, 0);
    }
    if (!q) {
      return { results: [], total: 0, query: '', reason: null,
        hint: '未输入查询词。这不是"没有结果"，只是还没搜。' };
    }
    var hits = items.filter(function (it) {
      if (present(it.exact)) return str(it.exact).toLocaleLowerCase() === q;
      return str(it.search).toLocaleLowerCase().indexOf(q) >= 0;
    });
    if (!hits.length) {
      return noResult(opts.hadFilter ? 'filtered_out' : 'no_match', items.length);
    }
    var typed = hits.map(function (it) {
      var t = TYPES[it.type] || TYPES.unknown;
      return {
        type: t.code, typeLabel: t.zh, key: it.key, label: it.label,
        context: it.context || '',
        hasContext: present(it.context),
        canonical: it.canonical || null, canonicalKey: it.canonicalKey || null,
        resolvesToCanonical: it.type !== 'alias' ? true : present(it.canonical)
      };
    });
    return {
      results: typed, total: typed.length, query: str(query),
      reason: null,
      byType: typed.reduce(function (a, r) { a[r.type] = (a[r.type] || 0) + 1; return a; }, {}),
      hint: ('命中 ' + typed.length + ' 条：'
        + Object.keys(typed.reduce(function (a, r) { a[r.type] = 1; return a; }, {}))
            .map(function (k) { return TYPES[k].zh; }).join('、'))
    };
  }

  function noResult(reason, indexed) {
    var r = NO_RESULT_REASONS[reason] || NO_RESULT_REASONS.no_match;
    return {
      results: [], total: 0, reason: r.code, reasonLabel: r.zh,
      indexed: indexed,
      nextStep: r.hint,
      hint: r.zh + ' —— ' + r.hint,
      indexUnavailable: r.code !== 'no_match' && r.code !== 'filtered_out'
    };
  }

  function distinguishVersions(entries) {
    entries = Array.isArray(entries) ? entries : [];
    var byDisplay = {};
    entries.forEach(function (e) {
      if (!e) return;
      var d = str(e.display || e.title);
      (byDisplay[d] = byDisplay[d] || []).push(e);
    });
    var collisions = Object.keys(byDisplay).filter(function (d) { return byDisplay[d].length > 1; });
    var rows = entries.map(function (e) {
      var d = str(e.display || e.title);
      var key = str(e.key);
      var dup = byDisplay[d] && byDisplay[d].length > 1;
      return {
        display: d, key: key,
        disambiguator: dup ? (key ? '版本键 ' + key.slice(0, 8) : null) : null,
        distinguishable: !dup || present(key),
        nature: str(e.nature || e.versionNature) || null,
        scope: present(e.scope) ? e.scope : null,
        gaps: present(e.gaps) ? e.gaps : null
      };
    });
    return {
      rows: rows,
      sameNameCount: collisions.length,
      collisions: collisions,
      allDistinguishable: rows.every(function (r) { return r.distinguishable; }),
      hint: collisions.length
        ? ('有 ' + collisions.length + ' 组同名作品（' + collisions.slice(0, 3).join('、')
           + '）—— 靠版本键区分，**不靠显示名**。')
        : '没有同名作品。'
    };
  }

  function tally(index) {
    var items = Array.isArray(index) ? index : [];
    var byType = {};
    items.forEach(function (it) { byType[it.type] = (byType[it.type] || 0) + 1; });
    var noContext = items.filter(function (it) {
      return it.type !== 'alias' && !present(it.context);
    }).length;
    var aliasNoCanonical = items.filter(function (it) {
      return it.type === 'alias' && !present(it.canonical);
    }).length;
    return {
      title: '可搜条目构成', isQualityScore: false,
      total: items.length, byType: byType,
      missingContext: noContext,
      aliasWithoutCanonical: aliasNoCanonical,
      note: '计数**不是质量徽章**：条目多不等于覆盖好。'
        + '别名命中必须能回到正名；每条结果必须带类型与上下文。',
      summary: items.length
        ? (items.length + ' 条可搜条目：'
           + Object.keys(byType).map(function (k) {
               return (TYPES[k] ? TYPES[k].zh : k) + ' ' + byType[k];
             }).join('、')
           + (noContext ? '；**缺上下文的 ' + noContext + ' 条**' : '；全部带上下文')
           + (aliasNoCanonical ? '；**别名缺正名的 ' + aliasNoCanonical + ' 条**' : ''))
        : '0 条可搜条目 —— 这首先说明**当前版本没有可搜内容**，不等于作品里没有。'
    };
  }

  var API = { VERSION: VERSION, TYPES: TYPES, NO_RESULT_REASONS: NO_RESULT_REASONS,
    build: build, search: search, distinguishVersions: distinguishVersions, tally: tally };
  g.CLSkySearchIndex = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
