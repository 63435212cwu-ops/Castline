(function (g) {
  'use strict';
  var LAYERS = { storylines: '故事线', tasks: '任务', causeEdges: '因果', clues: '伏笔', characterStates: '人物状态', relations: '人物关系' };
  function arr(v) { return Array.isArray(v) ? v : []; }
  function obj(v) { return v && typeof v === 'object' && !Array.isArray(v); }
  function canonical(v) { return JSON.stringify(v, function (k, value) { if (!obj(value)) return value; var out = {}; Object.keys(value).sort().forEach(function (key) { out[key] = value[key]; }); return out; }); }
  function binding(scope) { return scope && typeof scope.sourceId === 'string' && /^[a-f0-9]{64}$/.test(scope.textHash || '') ? [{ sourceId: scope.sourceId, textHash: scope.textHash }] : []; }
  function legacy(meta) {
    var groups = Object.create(null), enrichment = meta.enrichment || {};
    function add(scope, layers, gaps) {
      if (!obj(scope) || !Object.keys(scope).length || !layers.length) return;
      var key = canonical(scope), entry = groups[key] || (groups[key] = { scope: scope, layers: [], sources: binding(scope), origin: 'legacy_metadata', coverageGaps: [], scopeVerification: 'declared_only' });
      layers.forEach(function (layer) { if (entry.layers.indexOf(layer) < 0) entry.layers.push(layer); });
      arr(gaps).forEach(function (gap) { if (!entry.coverageGaps.some(function (old) { return canonical(old) === canonical(gap); })) entry.coverageGaps.push(gap); });
    }
    if (enrichment.method === 'assistant_source_review') add(enrichment.scope, arr(enrichment.layers).filter(function (x) { return LAYERS[x]; }), enrichment.coverageGaps);
    Object.keys(LAYERS).forEach(function (layer) { var coverage = meta.coverage && meta.coverage[layer]; if (obj(coverage)) add(coverage.scope, [layer]); });
    return Object.keys(groups).map(function (key) { return groups[key]; });
  }
  function describe(scope) {
    var lines = [];
    if (typeof scope.name === 'string') lines.push(scope.name);
    if (arr(scope.chapters).length) lines.push('范围：' + scope.chapters.join('、'));
    if (arr(scope.fullOriginalChaptersRead).length) lines.push('完整章节回读声明：' + scope.fullOriginalChaptersRead.join('、'));
    if (arr(scope.fullEpisodeRead).length) lines.push('完整情节回读声明：' + scope.fullEpisodeRead.join('；'));
    if (arr(scope.originalWindowChaptersRead).length) lines.push('另有 ' + scope.originalWindowChaptersRead.length + ' 个章节的局部窗口记录，不等于整章回读。');
    if (arr(scope.reviewedAreas).length) lines.push('选定场景：' + scope.reviewedAreas.join('、'));
    if (typeof scope.originalRead === 'string' && /[\u4e00-\u9fff]/.test(scope.originalRead)) lines.push(scope.originalRead);
    if (typeof scope.source === 'string' && /critical_verbatim_windows/.test(scope.source)) lines.push('仅选定原文窗口及目标段落，未声明全书逐字回读。');
    if (Number.isInteger(scope.lineStart) && Number.isInteger(scope.lineEnd) && scope.lineStart > 0 && scope.lineEnd >= scope.lineStart) lines.push('所声明原文行 ' + scope.lineStart + '–' + scope.lineEnd);
    ['unreviewed', 'unreviewedOriginal'].forEach(function (key) { if (typeof scope[key] === 'string') lines.push(scope[key]); });
    if (scope.wholeNovelVerbatimRead === true) lines.push('记录声明全文回读；尚未独立核验其语义完整性。');
    return lines.length ? lines : ['仅保存范围声明，缺少可读的完整精读边界。'];
  }
  function summarize(graph, adapter) {
    graph = graph || {}; var meta = graph.meta || {}, sources = Object.create(null), malformed = false;
    arr(meta.sources).forEach(function (s) { var id = s && (s.id || s.sourceId); if (id) (sources[id] || (sources[id] = [])).push(s.textHash); });
    var history;
    if (Object.prototype.hasOwnProperty.call(meta, 'reviewHistory')) {
      malformed = !Array.isArray(meta.reviewHistory);
      history = arr(meta.reviewHistory).filter(function (entry) {
        var valid = obj(entry) && obj(entry.scope) && Array.isArray(entry.layers) && entry.layers.every(function (x) { return !!LAYERS[x]; }) && Array.isArray(entry.sources) && entry.sources.every(function (s) { return binding(s).length === 1; }) && /^(legacy_metadata|reviewed_publication)$/.test(entry.origin) && entry.scopeVerification === 'declared_only';
        if (!valid) malformed = true; return valid;
      });
    } else history = legacy(meta);
    var seen = Object.create(null), records = [];
    history.forEach(function (entry) {
      var key = entry.id || canonical([entry.scope, entry.layers, entry.sources]); if (seen[key]) return; seen[key] = true;
      var current = entry.sources.length && entry.sources.every(function (s) { return sources[s.sourceId] && sources[s.sourceId].length === 1 && sources[s.sourceId][0] === s.textHash; });
      records.push({ layers: entry.layers.slice(), origin: entry.origin, applicability: !entry.sources.length ? 'source_unbound' : current ? 'current' : 'source_changed', lines: describe(entry.scope), gaps: arr(entry.coverageGaps).map(function (gap) { return typeof gap === 'string' ? gap : gap && (gap.reason || gap.description); }).filter(Boolean) });
    });
    var events = arr(graph.events), anchored = events.filter(function (event) { return adapter && adapter.evidenceStatus && adapter.evidenceStatus(event).anchored; }).length;
    var layers = Object.keys(LAYERS).map(function (key) { var items = arr(graph[key]); return { key: key, label: LAYERS[key], count: items.length, reviewed: items.filter(function (item) { return item && item.provenance === 'assistant-reviewed-source'; }).length }; });
    return { events: events.length, anchoredEvents: anchored, layers: layers, records: records, malformed: malformed, issues: arr(graph.reviewIssues).length, fullSemanticCoverage: null };
  }
  var api = { summarize: summarize, layers: LAYERS };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (g) g.CLSkyCoverage = api;
})(typeof window !== 'undefined' ? window : null);
