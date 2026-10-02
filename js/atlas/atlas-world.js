/* Optional-world graph projection. Only explicit IDs/fields create edges. */
(function (g) {
  'use strict';
  var TYPES = { locations: 'location', items: 'item', worldRules: 'rule', clues: 'clue', causeEdges: 'cause', characterStates: 'state' };
  function list(x) { return Array.isArray(x) ? x : []; }
  function label(x) { return String(x && (x.name || x.title || x.statement || x.rule || x.question || x.summary || x.id) || '未命名'); }
  function id(x) { return x && (x.id != null && x.id !== '' ? x.id : x.entityId != null && x.entityId !== '' ? x.entityId : x.name); }
  function resolve(rows, value) { var hits = rows.filter(function (x) { return value != null && String(id(x)) === String(value); }); return hits.length === 1 ? hits[0] : null; }
  function neighbors(G, field, row) {
    G = G || {}; row = row || {}; var nodes = [], seen = Object.create(null), warnings = [];
    function add(type, record, edge, edgeKind, extra) {
      if (!record) return;
      var key = type + ':' + id(record) + ':' + edge; if (seen[key]) return; seen[key] = true;
      var n = { type: type, id: String(id(record)), label: label(record), record: record, edge: edge, edgeKind: edgeKind || 'member' };
      Object.keys(extra || {}).forEach(function (k) { n[k] = extra[k]; }); nodes.push(n);
    }
    function person(value, edge) {
      var hits = list(G.characters).filter(function (c) { return value != null && (String(id(c)) === String(value) || c.name === value); });
      if (hits.length === 1) add('character', hits[0], edge); else warnings.push('人物引用未唯一解析');
    }
    function event(value, edge, direction) {
      var record = resolve(list(G.events), value);
      if (record) add('event', record, edge, direction ? 'causal' : 'member', { index: G.events.indexOf(record), direction: direction || null });
      else if (value != null) warnings.push('事件引用未唯一解析');
    }
    list(row.characters).concat(list(row.characterIds)).forEach(function (v) { person(v, '记录中明确涉及'); });
    list(row.eventIds).forEach(function (v) { event(v, '来源关联事件'); });
    if (field === 'locations') {
      if (row.parentLocationId != null) add('location', resolve(list(G.locations), row.parentLocationId), '属于该地点', 'member', { field: 'locations' });
      list(G.events).forEach(function (e) { if (list(e.locationIds).indexOf(id(row)) >= 0) event(id(e), '发生于此地点'); });
    }
    if (field === 'items') {
      list(row.transfers || row.ownership).forEach(function (t) { if (t.fromCharacterId != null) person(t.fromCharacterId, '交接来源'); if (t.toCharacterId != null) person(t.toCharacterId, '交接去向'); if (t.eventId != null) event(t.eventId, '物品交接事件'); });
      if (row.ownerId != null) person(row.ownerId, '明确持有者');
    }
    if (field === 'worldRules') [['exceptionRuleIds', '例外'], ['conflictRuleIds', '冲突'], ['relatedRuleIds', '关联规则']].forEach(function (spec) { list(row[spec[0]]).forEach(function (v) { add('rule', resolve(list(G.worldRules), v), spec[1], 'member', { field: 'worldRules' }); }); });
    if (field === 'clues') {
      list(row.setupEventIds || row.seedEventIds).forEach(function (v) { event(v, '埋设来源', 'in'); });
      list(row.payoffEventIds).forEach(function (v) { event(v, '声明回收', 'out'); });
      [['seedQuote', '埋设引句', 'in'], ['payoffQuote', '回收引句', 'out']].forEach(function (spec) {
        if (!row[spec[0]]) return;
        var hits = list(G.events).filter(function (e) { return e.quote && e.quote === row[spec[0]]; });
        if (hits.length === 1) event(id(hits[0]), spec[1] + '（逐句匹配）', spec[2]); else warnings.push(spec[1] + '不能唯一定位到事件');
      });
    }
    if (field === 'causeEdges') { event(row.fromEventId, row.relation || row.kind || '原因/条件', 'in'); event(row.toEventId, '声明结果', 'out'); }
    if (field === 'characterStates') person(row.characterId || row.character || row.name, '状态所属人物');
    return { title: label(row), nodes: nodes, count: nodes.length, warnings: warnings, record: row, field: field, type: TYPES[field] };
  }
  g.CLAtlasWorld = { neighbors: neighbors, label: label, types: TYPES };
})(typeof window === 'undefined' ? this : window);
