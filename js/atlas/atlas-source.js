(function (root) {
  'use strict';
  var VERSION = 'castline/5';
  var NARRATIVE_VERSION = 'castline/narrative-evidence/1';
  var AUX = ['locations', 'items', 'worldRules', 'clues', 'causeEdges', 'characterStates', 'stateTransitions', 'characterTransitions', 'tasks', 'narrativeUnits', 'reviewIssues'];
  var READS_DOWN = ['castline/5', 'castline/4', 'castline/3', 'v3-universal', 'legacy'];
  var MIGRATION_HOPS = {
    'castline/4': ['castline/4>castline/5'],
    'castline/3': ['castline/3>castline/4', 'castline/4>castline/5'],
    'v3-universal': ['v3-universal>castline/4', 'castline/4>castline/5'],
    'legacy': ['legacy>castline/4', 'castline/4>castline/5']
  };
  var DUAL_READ = {
    entityId: { also: ['id'] },
    chapterLabel: { also: ['chapter'] },
    sourceRefs: { also: ['sourceRef', 'evidenceRefs', 'quoteRef'], same: 'locator' }
  };
  var own = Object.prototype.hasOwnProperty;
  var BASIS = {
    explicit: '原文明确', synthesis: '材料支持的归纳', inference: '事件推导', unverified: '未核验'
  };
  var BASIS_CODES = {
    explicit: 'explicit', '原文明确': 'explicit', '原文': 'explicit',
    synthesis: 'synthesis', '材料支持的归纳': 'synthesis', '归纳': 'synthesis',
    inference: 'inference', inferred: 'inference', '事件推导': 'inference', '推导': 'inference',
    unverified: 'unverified', uncertain: 'unverified', '未知': 'unverified', '未核验': 'unverified'
  };

  function obj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return v == null ? '' : String(v); }
  function number(v) {
    if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
    var n = Number(v); return isFinite(n) ? n : null;
  }
  function clone(v) {
    if (Array.isArray(v)) return v.map(clone);
    if (!obj(v)) return v;
    var out = {}; Object.keys(v).forEach(function (k) {
      if (k !== '__proto__' && k !== 'constructor' && k !== 'prototype') out[k] = clone(v[k]);
    }); return out;
  }
  function canonical(v) {
    if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
    if (!obj(v)) return JSON.stringify(v == null ? null : v);
    return '{' + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ':' + canonical(v[k]); }).join(',') + '}';
  }
  function hash(s) {
    s = str(s); var a = 2166136261, b = 2246822519, i;
    for (i = 0; i < s.length; i++) {
      a ^= s.charCodeAt(i); a = Math.imul ? Math.imul(a, 16777619) : ((a << 1) + (a << 4) + (a << 7) + (a << 8) + (a << 24) + a);
      b ^= s.charCodeAt(i); b = Math.imul ? Math.imul(b, 3266489917) : ((b << 5) - b);
    }
    return ('00000000' + (a >>> 0).toString(16)).slice(-8) + ('00000000' + (b >>> 0).toString(16)).slice(-8);
  }
  function stableId(kind, key) { return kind + '_' + hash(canonical(key)); }
  function ident(v) { return obj(v) ? (v.id != null && v.id !== '' ? v.id : v.entityId) : null; }
  function assignId(v, kind, key) {
    var id = ident(v);
    if (id == null || id === '') id = stableId(kind, key);
    if (v.id == null || v.id === '') v.id = id;
    if (v.entityId == null || v.entityId === '') v.entityId = id;
    return id;
  }
  function eventKey(e) {
    return { chapter: e.chapter || null, title: e.title || null, summary: e.summary || null,
      quote: e.quote || null, rawOrder: e.rawOrder != null ? e.rawOrder : e.order };
  }
  function pushUnique(map, key, value) {
    key = str(key); if (!own.call(map, key)) map[key] = [];
    if (map[key].indexOf(value) < 0) map[key].push(value);
  }
  function basisInfo(value) {
    var raw = str(value).trim(), code = BASIS_CODES[raw.toLowerCase()] || BASIS_CODES[raw];
    if (!code) code = 'unverified';
    return { code: code, label: BASIS[code] };
  }
  function normalizeEvidence(value) {
    return arr(value).map(function (item) {
      if (typeof item === 'string') return { quote: item, basis: BASIS.unverified, basisCode: 'unverified' };
      if (!obj(item)) return null;
      var out = clone(item), info = basisInfo(out.basisCode != null ? out.basisCode : out.basis);
      out.basis = out.basis == null || out.basis === '' ? info.label : out.basis;
      out.basisCode = info.code;
      if (!Array.isArray(out.sourceRefs) && obj(out.sourceRef)) out.sourceRefs = [clone(out.sourceRef)];
      return out;
    }).filter(function (item) { return !!item; });
  }
  function linkTarget(item) {
    if (obj(item)) {
      if (item.targetId != null && item.targetId !== '') return item.targetId;
      if (item.eventId != null && item.eventId !== '') return item.eventId;
      if (item.to != null && item.to !== '') return item.to;
      if (item.target != null && item.target !== '') return item.target;
      if (item.id != null && item.id !== '') return item.id;
      return null;
    }
    return item == null || item === '' ? null : item;
  }
  function normalizeLink(item) {
    var out = obj(item) ? clone(item) : { ref: item }, target = linkTarget(item), info;
    if (target != null && target !== '') out.targetId = target;
    else out.targetId = null;
    if (out.ref == null && !obj(item)) out.ref = item;
    info = basisInfo(out.basisCode != null ? out.basisCode : out.basis);
    out.basis = out.basis == null || out.basis === '' ? info.label : out.basis;
    out.basisCode = info.code;
    out.evidence = normalizeEvidence(out.evidence != null ? out.evidence : out.evidenceRefs);
    return out;
  }
  function normalizeLinks(value) { return arr(value).map(normalizeLink); }
  function normalizeTurningPoint(item) {
    var out = obj(item) ? clone(item) : { ref: item }, target = obj(item) ?
      (item.eventId != null ? item.eventId : item.targetId != null ? item.targetId : item.order) : item;
    if (target != null && target !== '') out.eventId = target;
    else if (out.eventId == null) out.eventId = null;
    if (out.order != null && number(out.order) != null) out.order = number(out.order);
    else if (out.order == null) out.order = null;
    var info = basisInfo(out.basisCode != null ? out.basisCode : out.basis);
    out.basis = out.basis == null || out.basis === '' ? info.label : out.basis;
    out.basisCode = info.code;
    out.evidence = normalizeEvidence(out.evidence != null ? out.evidence : out.evidenceRefs);
    return out;
  }
  function normalizeTurningPoints(value) { return arr(value).map(normalizeTurningPoint); }
  function normalizePair(item) {
    var out = obj(item) ? clone(item) : { ref: item };
    var f = obj(item) ? (item.foreshadowId != null ? item.foreshadowId : item.foreshadow != null ? item.foreshadow : item.from) : null;
    var p = obj(item) ? (item.payoffId != null ? item.payoffId : item.payoff != null ? item.payoff : item.to) : null;
    if (f == null && obj(item) && item.foreshadow_of != null) f = item.foreshadow_of;
    if (p == null && obj(item) && item.payoff_of != null) p = item.payoff_of;
    out.foreshadowId = f == null ? null : f;
    out.payoffId = p == null ? null : p;
    var info = basisInfo(out.basisCode != null ? out.basisCode : out.basis);
    out.basis = out.basis == null || out.basis === '' ? info.label : out.basis;
    out.basisCode = info.code;
    out.evidence = normalizeEvidence(out.evidence != null ? out.evidence : out.evidenceRefs);
    return out;
  }
  function normalizePairs(value) { return arr(value).map(normalizePair); }
  function resolveEventRef(value, byId, byOrder) {
    var raw = value;
    if (obj(value)) raw = value.targetId != null ? value.targetId : value.eventId;
    if (raw != null && own.call(byId, str(raw))) {
      var ids = byId[str(raw)];
      return Array.isArray(ids) ? (ids.length === 1 ? ids[0] : null) : ids;
    }
    var n = number(raw), hits = n == null ? [] : (byOrder[str(n)] || []);
    if (hits.length !== 1) return null;
    var found = byId[str(hits[0])];
    return obj(hits[0]) ? hits[0] : (Array.isArray(found) ? (found.length === 1 ? found[0] : null) : found || null);
  }
  function resolveTurningPoint(item, byId, byOrder) {
    var hit = resolveEventRef(item, byId, byOrder);
    if (!hit && item && item.order != null) hit = resolveEventRef(item.order, byId, byOrder);
    item.eventId = hit ? ident(hit) : null;
    item.resolved = !!hit;
    return item;
  }
  function resolveLink(item, byId, byOrder) {
    var hit = resolveEventRef(item, byId, byOrder);
    item.targetId = hit ? ident(hit) : null;
    item.resolved = !!hit;
    return item;
  }
  function resolvePair(item, byId, byOrder) {
    var f = resolveEventRef(item.foreshadowId, byId, byOrder), p = resolveEventRef(item.payoffId, byId, byOrder);
    item.foreshadowId = f ? ident(f) : null; item.payoffId = p ? ident(p) : null;
    item.resolved = !!(f && p);
    return item;
  }
  function causeEndpoint(edge, side, byId, byOrder) {
    var names = side === 'from' ? ['fromEventId', 'from', 'sourceId', 'declaredSourceId'] : ['toEventId', 'to', 'targetId', 'declaredTargetId'];
    var resolved = null, supplied = false, conflict = false;
    names.forEach(function (key) {
      var value = edge[key];
      if (value == null || value === '') return;
      supplied = true;
      var hit = resolveEventRef(value, byId, byOrder);
      if (!hit || (resolved && ident(resolved) !== ident(hit))) conflict = true;
      else resolved = hit;
    });
    return { event: conflict ? null : resolved, status: conflict ? 'unresolved_or_conflicting' : supplied ? 'resolved' : 'missing' };
  }
  function narrativeContract(g, provided) {
    var events = g.events, byId = Object.create(null), byOrder = Object.create(null);
    events.forEach(function (e) {
      pushUnique(byId, ident(e), e);
      pushUnique(byOrder, e.order, ident(e));
      if (e.rawOrder != null) pushUnique(byOrder, e.rawOrder, ident(e));
    });
    events.forEach(function (e) {
      e.causes = normalizeLinks(e.causes); e.consequences = normalizeLinks(e.consequences);
      e.foreshadow_of = normalizeLinks(e.foreshadow_of);
      e.payoff_of = normalizeLinks(e.payoff_of);
      e.evidence = normalizeEvidence(e.evidence);
      e.causes.forEach(function (x) { resolveLink(x, byId, byOrder); });
      e.consequences.forEach(function (x) { resolveLink(x, byId, byOrder); });
      e.foreshadow_of.forEach(function (x) { resolveLink(x, byId, byOrder); });
      e.payoff_of.forEach(function (x) { resolveLink(x, byId, byOrder); });
    });
    g.characters.forEach(function (c) {
      c.turning_points = normalizeTurningPoints(c.turning_points);
      c.turning_points.forEach(function (x) { resolveTurningPoint(x, byId, byOrder); });
    });
    (g.storylines || []).forEach(function (line) {
      line.turning_points = normalizeTurningPoints(line.turning_points);
      line.foreshadow_payoffs = normalizePairs(line.foreshadow_payoffs);
      line.turning_points.forEach(function (x) { resolveTurningPoint(x, byId, byOrder); });
      line.foreshadow_payoffs.forEach(function (x) { resolvePair(x, byId, byOrder); });
    });
    if (Array.isArray(g.causeEdges)) g.causeEdges = g.causeEdges.filter(obj).map(function (edge) {
      var out = clone(edge), from = causeEndpoint(edge, 'from', byId, byOrder), to = causeEndpoint(edge, 'to', byId, byOrder);
      var veto = edge.referenceStatus === 'unresolved' || edge.referenceStatus === 'unresolved_or_conflicting';
      out.sourceId = !veto && from.event ? ident(from.event) : null;
      out.targetId = !veto && to.event ? ident(to.event) : null;
      out.resolved = !veto && !!(from.event && to.event);
      out.endpointResolution = { from: veto ? 'server_unresolved' : from.status, to: veto ? 'server_unresolved' : to.status };
      var info = basisInfo(out.basisCode != null ? out.basisCode : out.basis);
      out.basis = out.basis == null || out.basis === '' ? info.label : out.basis; out.basisCode = info.code;
      out.evidence = normalizeEvidence(out.evidence != null ? out.evidence : out.evidenceRefs);
      return out;
    });
    var fields = ['causes', 'consequences', 'evidence', 'turning_points', 'foreshadow_payoffs'];
    var coverage = obj(g.meta.coverage && g.meta.coverage.narrative) ? clone(g.meta.coverage.narrative) : {};
    fields.forEach(function (field) {
      var count = field === 'evidence' ? events.reduce(function (n, e) { return n + e.evidence.length; }, 0) :
        field === 'turning_points' ? g.characters.concat(g.storylines || []).reduce(function (n, x) { return n + x.turning_points.length; }, 0) :
        field === 'foreshadow_payoffs' ? (g.storylines || []).reduce(function (n, x) { return n + x.foreshadow_payoffs.length; }, 0) :
        events.reduce(function (n, e) { return n + e[field].length; }, 0);
      var supplied = !!(provided && provided[field]);
      coverage[field] = Object.assign({}, obj(coverage[field]) ? coverage[field] : {}, { known: coverage[field] && typeof coverage[field].known === 'boolean' ? coverage[field].known : count > 0, count: count, supplied: supplied, reason: count > 0 ? 'provided' : supplied ? 'explicit_empty' : 'not_provided' });
    });
    g.meta.coverage.narrative = coverage;
    g.meta.narrativeEvidence = Object.assign({}, obj(g.meta.narrativeEvidence) ? g.meta.narrativeEvidence : {}, { version: NARRATIVE_VERSION, fields: fields.slice() });
    return g;
  }
  function mapLine(line, orderMap, events, warnings) {
    var out = clone(line), indexes = [];
    var byId = Object.create(null);
    events.forEach(function (e, i) { pushUnique(byId, ident(e), i); });
    if (!own.call(out, 'rawEvents') && Array.isArray(line.events)) out.rawEvents = clone(line.events);
    if (!own.call(out, 'rawAttachOrder') && own.call(line, 'attach_order')) out.rawAttachOrder = line.attach_order;
    if (arr(line.eventIds).length) arr(line.eventIds).forEach(function (id) {
      var found = byId[str(id)] || [];
      if (found.length === 1) { if (indexes.indexOf(found[0]) < 0) indexes.push(found[0]); }
      else warnings.push({ code: found.length ? 'ambiguous-event-id' : 'missing-event-id', entityId: ident(line), eventId: id });
    });
    else arr(line.events).forEach(function (order) {
      var n = number(order), found = n == null ? [] : (orderMap[str(n)] || []);
      if (found.length === 1) { if (indexes.indexOf(found[0]) < 0) indexes.push(found[0]); }
      else warnings.push({ code: found.length ? 'ambiguous-event-order' : 'missing-event-order',
        entityId: ident(line), order: order });
    });
    indexes.sort(function (a, b) { return a - b; });
    out.events = indexes.map(function (i) { return events[i].order; });
    out.eventIdxs = indexes;
    out.eventIds = indexes.map(function (i) { return ident(events[i]); });
    var attach = number(line.attach_order), targets = attach == null ? [] : (orderMap[str(attach)] || []);
    if (line.attachEventId != null && line.attachEventId !== '') {
      targets = byId[str(line.attachEventId)] || [];
      out.attach_order = targets.length === 1 ? events[targets[0]].order : 0;
      if (targets.length !== 1) warnings.push({ code: 'unresolved-attach-event-id', entityId: ident(line), eventId: line.attachEventId });
    } else if (attach && targets.length === 1) out.attach_order = events[targets[0]].order;
    else if (attach) { out.attach_order = 0; warnings.push({ code: 'unresolved-attach-order', entityId: ident(line), order: attach }); }
    assignId(out, 'sl', { name: out.name || out.title, eventIds: out.eventIds });
    return out;
  }

  // ---------------------------------------------------------------- P01 v5
  function labelKey(value) { return str(value).replace(/[\s\u3000]+/g, ' ').trim(); }
  function chapterId(label) { return stableId('chp', labelKey(label)); }
  function orderedId(kind, key, name) { return kind + '_' + hash(canonical(key)).slice(0, 6) + '_' + name; }

  function migrationPath(from, to) {
    if (!from || from === to) return [];
    return (MIGRATION_HOPS[from] || ['legacy>castline/4', 'castline/4>castline/5']).slice();
  }

  function dualRead(src, primary, legacy, identityOf) {
    var seen = [], values = [], marks = [], i, v, mark;
    var fields = [primary].concat(legacy || []);
    function markOf(value) {
      if (!identityOf) return canonical(value);
      var list = Array.isArray(value) ? value : [value];
      var marks = list.map(function (item) { return identityOf(item); });
      if (marks.some(function (m) { return m == null; })) return null;
      return marks.slice().sort().join('|');
    }
    for (i = 0; i < fields.length; i++) {
      v = src[fields[i]];
      if (v === undefined || v === null || v === '') continue;
      if (Array.isArray(v) && !v.length) continue;
      mark = markOf(v);
      if (mark == null) continue;
      seen.push(fields[i]); values.push(v); marks.push(mark);
    }
    if (!seen.length) return { present: false, field: null, value: null, fields: [], conflict: false, marks: [] };
    var first = marks[0], conflict = false;
    for (i = 1; i < marks.length; i++) if (marks[i] !== first) conflict = true;
    return { present: true, field: seen[0], value: values[0], fields: seen, marks: marks, conflict: conflict };
  }

  function evidenceId(item) {
    if (typeof item === 'string') return stableId('evd', { quote: item });
    var key = clone(obj(item) ? item : {});
    delete key.id; delete key.entityId; delete key.locatorId;
    return stableId('evd', key);
  }
  function sourceRefId(ref) {
    if (!obj(ref)) return null;
    var start = number(ref.start), end = number(ref.end);
    return stableId('loc', { sourceId: ref.sourceId == null ? null : str(ref.sourceId),
      textHash: ref.textHash == null ? null : str(ref.textHash),
      offsetUnit: ref.offsetUnit == null ? null : str(ref.offsetUnit),
      start: start, end: end, quote: typeof ref.quote === 'string' ? ref.quote : null });
  }
  function assignEvidenceIds(container, field) {
    var list = arr(container && container[field]);
    list.forEach(function (item) {
      if (!obj(item)) return;
      if (item.id == null || item.id === '') item.id = evidenceId(item);
      if (typeof item.quote !== 'string' && typeof item.text === 'string') item.quote = item.text;
    });
  }

  function aliasIndex(characters) {
    var tokens = Object.create(null), order = [], i, j;
    characters.forEach(function (c, ci) {
      var names = [str(c.name)].concat(arr(c.aliases).map(str));
      names.forEach(function (token, ti) {
        if (!token) return;
        if (!own.call(tokens, token)) { tokens[token] = { token: token, canonical: [], aliases: [], mentions: 0 }; order.push(token); }
        var rec = tokens[token];
        if (ti === 0) { if (rec.canonical.indexOf(ci) < 0) rec.canonical.push(ci); }
        else if (rec.aliases.indexOf(ci) < 0) rec.aliases.push(ci);
      });
    });
    var queue = [], owners = Object.create(null);
    order.forEach(function (token) {
      var rec = tokens[token], nodeIds = [];
      rec.canonical.concat(rec.aliases).forEach(function (ci) {
        var id = ident(characters[ci]);
        if (nodeIds.indexOf(id) < 0) nodeIds.push(id);
      });
      rec.nodeIds = nodeIds;
      owners[token] = nodeIds;
      if (nodeIds.length > 1) {
        queue.push({ token: token, kind: rec.canonical.length > 1 ? 'duplicate_canonical_name' : 'canonical_alias_collision',
          nodeIds: nodeIds, canonicalOwnerIds: rec.canonical.map(function (ci) { return ident(characters[ci]); }),
          autoMerged: false, attribution: 'review_required',
          reason: '一个名字被多个节点声明；自动归并会把不同人物并成一个' });
      }
    });
    return { tokens: tokens, owners: owners, queue: queue };
  }
  function aliasTokensOf(item) {
    var out = [], add = function (v) { var s = str(v).trim(); if (s && out.indexOf(s) < 0) out.push(s); };
    add(item && item.a); add(item && item.b);
    arr(item && item.characters).forEach(add);
    add(item && item.character);
    return out;
  }
  function conflictedTokens(item, owners) {
    return aliasTokensOf(item).filter(function (token) { return arr(owners[token]).length > 1; });
  }

  function chapterLedger(events) {
    var order = [], byLabel = Object.create(null);
    events.forEach(function (e) {
      var raw = e && e.chapter, key = labelKey(raw);
      if (!key) return;
      if (!own.call(byLabel, key)) { byLabel[key] = { id: chapterId(key), label: key, rawLabel: str(raw), eventIds: [], orders: [] }; order.push(key); }
      var rec = byLabel[key];
      rec.eventIds.push(ident(e));
      if (typeof e.order === 'number') rec.orders.push(e.order);
    });
    var unlabelled = events.filter(function (e) { return !labelKey(e && e.chapter); });
    return { order: order, byLabel: byLabel, unlabelled: unlabelled };
  }

  function identityLedger(graph, aliases, chapters, warnings) {
    var characters = arr(graph.characters), events = arr(graph.events), relations = arr(graph.relations);
    var ids = Object.create(null);
    ['characters', 'events', 'relations', 'storylines'].forEach(function (field) {
      ids[field] = arr(graph[field]).filter(obj).map(ident);
    });
    ids.chapters = chapters.order.map(function (key) { return chapters.byLabel[key].id; });
    ids.aux = {};
    var evidence = { declarations: 0, located: 0, unlocated: 0, refs: 0, anchoredRefs: 0, orphanRefs: 0 };
    function tallyEvidence(container) {
      var decls = arr(container && container.evidence);
      var ownRefs = sourceRefs(container);
      var byQuote = Object.create(null);
      ownRefs.forEach(function (ref) {
        if (ref && typeof ref.quote === 'string') (byQuote[ref.quote] || (byQuote[ref.quote] = [])).push(ref);
      });
      decls.forEach(function (item, index) {
        if (typeof item === 'string') {
          evidence.declarations++;
          var same = ownRefs[index];
          var cand = (same && same.quote === item) ? same
                   : (byQuote[item] && byQuote[item].length === 1 ? byQuote[item][0] : null);
          if (cand && anchored(cand)) evidence.located++; else evidence.unlocated++;
          return;
        }
        if (!obj(item)) return;
        evidence.declarations++;
        var refs = sourceRefs(item);
        evidence.refs += refs.length;
        var ok = refs.filter(anchored).length;
        evidence.anchoredRefs += ok;
        if (refs.length && ok === refs.length) evidence.located++; else evidence.unlocated++;
      });
      evidence.refs += ownRefs.length;
      evidence.anchoredRefs += ownRefs.filter(anchored).length;
      var claimed = decls.filter(function (item, index) {
        if (typeof item !== 'string') return false;
        var same = ownRefs[index];
        return !!(same && same.quote === item) || !!(byQuote[item] && byQuote[item].length === 1);
      }).length;
      if (ownRefs.length && !claimed && !decls.length) evidence.orphanRefs++;
    }
    AUX.forEach(function (field) {
      arr(graph[field]).forEach(function (node) {
        if (!obj(node)) return;
        assignEvidenceIds(node, 'evidence');
        tallyEvidence(node);
      });
      ids.aux[field] = arr(graph[field]).filter(obj).length;
    });
    events.forEach(function (e) { assignEvidenceIds(e, 'evidence'); tallyEvidence(e); });
    characters.forEach(function (c) {
      Object.keys(obj(c.attrs) ? c.attrs : {}).forEach(function (k) {
        assignEvidenceIds(c.attrs[k], 'evidence');
        tallyEvidence(c.attrs[k]);
      });
      tallyEvidence(c);
    });
    relations.forEach(function (r) { tallyEvidence(r); });

    var eventIds = Object.create(null), nameIds = Object.create(null);
    events.forEach(function (e) { var id = ident(e); if (id != null) eventIds[str(id)] = 1; });
    characters.forEach(function (c) {
      var id = ident(c);
      if (id != null) nameIds[str(id)] = 1;
    });
    var orphans = { events: 0, relations: 0, storylineEventRefs: 0, storylineIds: [], relationIds: [], danglingIds: [] };
    var dangling = Object.create(null);
    events.forEach(function (e) {
      arr(e.characters).forEach(function (c) {});
    });
    relations.forEach(function (r) {
      var a = str(r.a), b = str(r.b), bad = false;
      if (!byName(characters, a) || !byName(characters, b) || a === b) { orphans.relations++; orphans.relationIds.push(ident(r)); bad = true; }
      arr(r.eventIds).forEach(function (eid) { if (!own.call(eventIds, str(eid))) { dangling[str(eid)] = 1; bad = true; } });
      if (bad && ident(r) != null) dangling[str(ident(r))] = 1;
    });
    arr(graph.storylines).forEach(function (line) {
      var missing = arr(line.eventIds).filter(function (eid) { return !own.call(eventIds, str(eid)); });
      if (missing.length) { orphans.storylineEventRefs += missing.length; if (ident(line) != null) orphans.storylineIds.push(ident(line)); }
    });
    ['tasks', 'clues', 'characterStates', 'causeEdges', 'narrativeUnits'].forEach(function (field) {
      arr(graph[field]).forEach(function (node) {
        if (!obj(node)) return;
        var refs = [];
        ['eventId', 'outcomeEventId', 'seedEventId', 'payoffEventId', 'sourceId', 'targetId'].forEach(function (k) {
          if (node[k] != null && node[k] !== '') refs.push(node[k]);
        });
        arr(node.eventIds).forEach(function (v) { refs.push(v); });
        var bad = refs.filter(function (v) { return !own.call(eventIds, str(v)); });
        if (bad.length) { dangling[str(ident(node))] = 1; if (ident(node) != null) orphans.relationIds.push(ident(node)); }
        if (node.resolved === false || node.referenceStatus === 'unresolved') { if (ident(node) != null) orphans.relationIds.push(ident(node)); }
      });
    });
    orphans.danglingIds = Object.keys(dangling);
    orphans.pendingNodes = orphans.relationIds.length;

    var unknown = { importance: 0, scoredAttributes: 0, pendingAttributes: 0, relationStrength: 0, fabricatedDefaults: 0 };
    characters.forEach(function (c) {
      if (c.importance == null) unknown.importance++;
      Object.keys(obj(c.attrs) ? c.attrs : {}).forEach(function (k) {
        var a = c.attrs[k];
        if (!obj(a)) return;
        if (a.pending || number(a.score) == null) unknown.pendingAttributes++; else unknown.scoredAttributes++;
        if (number(a.reportedScore) != null && number(a.score) == null) unknown.fabricatedDefaults++;
      });
    });
    relations.forEach(function (r) { if (number(r.strength) == null) unknown.relationStrength++; });

    var reviewQueue = arr(graph.reviewIssues).filter(function (issue) {
      return obj(issue) && issue.kind === 'identity' && (issue.status === 'confirmed_issue' || issue.status === 'unresolved');
    }).map(function (issue) {
      return { token: null, kind: 'reviewed_identity_issue', issueId: str(issue.id), nodeIds: [str(issue.characterId)],
        identityStatus: str(issue.identityStatus) || 'ambiguous', autoMerged: false, attribution: 'review_required',
        reason: str(issue.description) || '审核已确认身份冲突，等待人工区分' };
    });
    characters.forEach(function (c) {
      if (!c.identityStatus || c.identityStatus === 'resolved') return;
      var id = ident(c);
      var present = reviewQueue.some(function (row) { return row.nodeIds.indexOf(str(id)) >= 0; });
      if (!present) reviewQueue.push({ token: str(c.name), kind: 'reviewed_identity_issue', issueId: null, nodeIds: [str(id)],
        identityStatus: str(c.identityStatus), autoMerged: false, attribution: 'review_required',
        reason: '节点带有未解决的 identityStatus；属性分保持待建档' });
    });

    return {
      version: 'castline/identity/1',
      schema: VERSION,
      ids: ids,
      chapters: { count: chapters.order.length, unlabelledEvents: chapters.unlabelled.length,
        labels: chapters.order.map(function (key) { return chapters.byLabel[key].label; }) },
      evidence: evidence,
      aliases: { tokens: Object.keys(aliases.tokens).length, conflictedTokens: aliases.queue.length,
        conflictedNodes: aliases.queue.reduce(function (n, row) { return n + row.nodeIds.length; }, 0),
        queue: aliases.queue, autoMerged: 0 },
      reviewQueue: reviewQueue,
      orphans: orphans,
      unknown: unknown,
      identityVetoes: characters.filter(function (c) { return c.identityStatus && c.identityStatus !== 'resolved'; })
        .map(function (c) { return { id: ident(c), name: str(c.name), identityStatus: str(c.identityStatus) }; }),
      warnings: arr(warnings).slice()
    };
  }
  function byName(characters, value) {
    var name = str(value);
    if (!name) return false;
    return characters.some(function (c) { return str(c.name) === name || arr(c.aliases).map(str).indexOf(name) >= 0; });
  }

  function chapterNumber(label) {
    var text = str(label).trim(), match = /^第([零〇一二两三四五六七八九十百千\d]+)[章回节]/.exec(text);
    if (!match) return /^\d+$/.test(text) ? +text : null;
    var digits = '零一二三四五六七八九', total = 0, value = 0;
    if (/^\d+$/.test(match[1])) return +match[1];
    match[1].split('').forEach(function (ch) {
      var unit = { 十: 10, 百: 100, 千: 1000 }[ch];
      if (unit) { total += (value || 1) * unit; value = 0; }
      else value = ch === '两' ? 2 : ch === '〇' ? 0 : digits.indexOf(ch);
    });
    return total + value;
  }
  function compatibleChapter(a, b) {
    if (!labelKey(a) || !labelKey(b)) return false;
    if (labelKey(a) === labelKey(b)) return true;
    var an = chapterNumber(a), bn = chapterNumber(b);
    if (an == null || an !== bn) return false;
    var au = /第[零〇一二两三四五六七八九十百千\d]+([章回节])/.exec(str(a));
    var bu = /第[零〇一二两三四五六七八九十百千\d]+([章回节])/.exec(str(b));
    if (au && bu && au[1] !== bu[1]) return false;
    var tail = function (v) { return labelKey(v).replace(/^(第[零〇一二两三四五六七八九十百千\d]+[章回节]|\d+)\s*/, ''); };
    return !tail(a) || !tail(b) || tail(a) === tail(b);
  }
  function sourceAppearanceOrder(rows, graph, warnings) {
    var sources = Object.create(null), hashes = Object.create(null), counts = Object.create(null), lineIds = Object.create(null);
    arr(graph.meta && graph.meta.sources).filter(obj).forEach(function (s) {
      var id = str(s.id || s.sourceId);
      if (!id || !s.textHash) return;
      pushUnique(hashes, id, str(s.textHash)); sources[id] = s;
    });
    rows.forEach(function (d) { if (d.e.rawOrderKnown && number(d.e.rawOrder) != null) pushUnique(counts, d.e.rawOrder, str(ident(d.e))); });
    arr(graph.storylines).forEach(function (line) {
      arr(line.eventIds).forEach(function (id) { lineIds[str(id)] = true; });
    });
    var ids = Object.keys(sources), source = ids.length === 1 && hashes[ids[0]].length === 1 ? sources[ids[0]] : null;
    var report = { version: 'castline/source-appearance/1', basis: 'source_appearance_not_causality_or_story_time',
      mode: source ? 'single_source_with_explicit_gaps' : 'legacy_order_no_comparable_source',
      exact: 0, bounded: 0, unresolved: 0, unresolvedIds: [], sourceId: source ? ids[0] : null,
      textHash: source ? str(source.textHash) : null, complete: false };
    if (!source) {
      rows.forEach(function (d) { d.e.sourcePosition = { kind: 'unresolved', reason: ids.length > 1 ? 'multiple_sources_no_global_order' : 'missing_or_conflicting_source_identity' }; });
      rows.sort(function (a, b) { return a.order - b.order || a.i - b.i; });
    } else {
      var sid = ids[0], anchors = [];
      rows.forEach(function (d) {
        var e = d.e, candidates = Object.create(null);
        if (!e.quoteReview && e.verified !== false && e.quoteVerified !== false) sourceRefs(e).forEach(function (ref) {
          if (anchored(ref) && ref.match === 'exact' && ref.offsetUnit === 'codepoint' && ref.quote === e.quote &&
              str(ref.sourceId) === sid && ref.textHash === source.textHash &&
              (number(source.chars) == null || ref.end <= number(source.chars))) candidates[ref.start + ':' + ref.end] = ref;
        });
        var keys = Object.keys(candidates);
        if (keys.length === 1) {
          var ref = candidates[keys[0]];
          d.position = ref.start; d.phase = 1;
          e.sourcePosition = { kind: 'exact_quote', sourceId: sid, textHash: source.textHash, start: ref.start, end: ref.end };
        } else e.sourcePosition = { kind: 'unresolved', reason: keys.length > 1 ? 'ambiguous_primary_quote' : 'missing_trusted_primary_quote' };
        d.legacy = e.rawOrderKnown && number(e.rawOrder) != null &&
          ((counts[str(e.rawOrder)] || []).length === 1 || lineIds[str(ident(e))]);
        if (d.legacy && d.position != null) anchors.push(d);
      });
      anchors.sort(function (a, b) { return number(a.e.rawOrder) - number(b.e.rawOrder) || a.i - b.i; });
      rows.forEach(function (d) {
        if (d.position != null || !d.legacy) return;
        var order = number(d.e.rawOrder), lo = 0, hi = anchors.length;
        while (lo < hi) { var mid = (lo + hi) >> 1; if (number(anchors[mid].e.rawOrder) < order) lo = mid + 1; else hi = mid; }
        var before = lo ? anchors[lo - 1] : null, after = anchors[lo] || null;
        if ((before && number(before.e.rawOrder) >= order) || (after && number(after.e.rawOrder) <= order) ||
            (before && after && before.position > after.position) ||
            !((before && compatibleChapter(d.e.chapter, before.e.chapter)) || (after && compatibleChapter(d.e.chapter, after.e.chapter)))) return;
        if (!before && !after) return;
        d.position = before ? before.position : 0; d.phase = before ? 2 : 0;
        d.e.sourcePosition = { kind: 'legacy_interval', sourceId: sid, textHash: source.textHash,
          start: before ? before.position : 0, end: after ? after.position : number(source.chars),
          beforeEventId: before ? ident(before.e) : null, afterEventId: after ? ident(after.e) : null,
          exactWithinInterval: false };
      });
      var chapterPosCache = (function () {
        var byKey = Object.create(null);
        function keyOf(name) {
          var s = str(name).trim();
          var m = /^第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*([回章节集幕])/.exec(s);
          if (m) return m[2] + '|' + m[1].replace(/^0+(?=\d)/, '');
          return labelKey(s) || null;
        }
        rows.forEach(function (d) {
          if (d.position == null) return;
          if ((d.e.sourcePosition || {}).kind !== 'exact_quote') return;
          var k = keyOf(d.e.chapter);
          if (!k) return;
          if (byKey[k] == null) byKey[k] = d.position;
          else if (d.position < byKey[k]) byKey[k] = d.position;
        });
        return { byKey: byKey, any: function (name) { var k = keyOf(name); return k ? byKey[k] : undefined; } };
      })();
      function sortPosOf(d) {
        if (d.position == null) return null;
        var sp = d.e.sourcePosition || {};
        if (sp.kind === 'legacy_interval') {
          var cp = chapterPosCache.any(d.e.chapter);
          if (cp != null && cp > d.position) return cp;
        }
        return d.position;
      }
      var located = rows.filter(function (d) { return d.position != null; });
      located.sort(function (a, b) {
        return sortPosOf(a) - sortPosOf(b) || a.phase - b.phase ||
          (a.phase === 2 && b.phase === 2 ? number(a.e.rawOrder) - number(b.e.rawOrder) : 0) || a.i - b.i;
      });
      located.forEach(function (d, k) { d.sortRank = k; });
      var locatedByRaw = located.filter(function (d) { return number(d.e.rawOrder) != null; })
        .sort(function (a, b) { return number(a.e.rawOrder) - number(b.e.rawOrder); });
      var CN_DIGIT = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
      function cnNumLocal(s) {
        if (/^\d+$/.test(s)) return +s;
        var total = 0, sec = 0, cur = 0, i, ch;
        for (i = 0; i < s.length; i++) {
          ch = s[i];
          if (CN_DIGIT[ch] !== undefined) cur = CN_DIGIT[ch];
          else if (ch === '十') { sec += (cur || 1) * 10; cur = 0; }
          else if (ch === '百') { sec += (cur || 1) * 100; cur = 0; }
          else if (ch === '千') { sec += (cur || 1) * 1000; cur = 0; }
          else return null;
        }
        return (sec + cur) || null;
      }
      function chapterKey(name) {
        var s = String(name == null ? '' : name).trim();
        var m = /^第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*([回章节集幕])/.exec(s);
        if (m) return m[2] + '|' + cnNumLocal(m[1]);
        var d = /^(\d+)$/.exec(s);
        return d ? '回|' + (+d[1]) : (s || null);
      }
      rows.forEach(function (d) {
        if (d.position != null) return;
        var ro = number(d.e.rawOrder);
        var ck = chapterKey(d.e.chapter);
        var sameChap = ck ? located.filter(function (l) { return chapterKey(l.e.chapter) === ck; }) : [];
        if (sameChap.length) {
          var crossedVolume = false;
          if (ro != null) {
            var sameRaw = [];
            sameChap.forEach(function (l) { var v = number(l.e.rawOrder); if (v != null) sameRaw.push(v); });
            if (sameRaw.length) {
              var loS = Math.min.apply(null, sameRaw), hiS = Math.max.apply(null, sameRaw);
              for (var q = 0; q < locatedByRaw.length; q++) {
                var oR2 = number(locatedByRaw[q].e.rawOrder);
                if (oR2 > loS && oR2 < hiS && chapterKey(locatedByRaw[q].e.chapter) !== ck) { crossedVolume = true; break; }
              }
            }
          }
          if (!crossedVolume) {
            var lo1 = Math.min.apply(null, sameChap.map(function (l) { return l.sortRank; }));
            var hi1 = Math.max.apply(null, sameChap.map(function (l) { return l.sortRank; }));
            d.sortRank = lo1 - 0.25 + (hi1 - lo1 + 0.5) * 0.5;
            return;
          }
        }
        if (ro != null) {
          var before = null, after = null, j;
          for (j = 0; j < locatedByRaw.length; j++) {
            var lr = number(locatedByRaw[j].e.rawOrder);
            if (lr < ro) before = locatedByRaw[j];
            else if (lr > ro && !after) { after = locatedByRaw[j]; break; }
          }
          if (before && after && before.sortRank < after.sortRank) {
            d.sortRank = (before.sortRank + after.sortRank) / 2;
            return;
          }
          if (before) { d.sortRank = before.sortRank + 0.25; return; }
          if (after) { d.sortRank = after.sortRank - 0.25; return; }
        }
        d.sortRank = located.length + d.i;
      });
      rows.sort(function (a, b) { return a.sortRank - b.sortRank || a.i - b.i; });
      rows.forEach(function (d) { delete d.sortRank; });
    }
    rows.forEach(function (d) {
      if (d.e.sourcePosition.kind === 'exact_quote') report.exact++;
      else if (d.e.sourcePosition.kind === 'legacy_interval') report.bounded++;
      else { report.unresolved++; report.unresolvedIds.push(ident(d.e)); }
    });
    report.complete = report.exact === rows.length && rows.length > 0;
    if (source && report.unresolved) warnings.push({ code: 'unlocated-event-order', count: report.unresolved,
      reason: 'Unlocated events remain available after located events; their source order is unknown.' });
    return report;
  }

  function normalize(input) {
    var g = obj(input) ? clone(input) : {}, meta = obj(g.meta) ? g.meta : {};
    var warnings = [], inputSchema = str(meta.schemaVersion || meta.schema || 'legacy');
    g.characters = arr(g.characters).filter(obj);
    var rawEventEntries = arr(g.events).map(function (e, i) { return { e: e, rawIndex: i }; }).filter(function (d) { return obj(d.e); });
    g.events = rawEventEntries.map(function (d) { return d.e; });
    g.relations = arr(g.relations).filter(obj);
    var narrativeProvided = { causes: false, consequences: false, evidence: false, turning_points: false, foreshadow_payoffs: false };
    g.events.forEach(function (e) {
      narrativeProvided.causes = narrativeProvided.causes || own.call(e, 'causes');
      narrativeProvided.consequences = narrativeProvided.consequences || own.call(e, 'consequences');
      narrativeProvided.evidence = narrativeProvided.evidence || own.call(e, 'evidence');
    });
    g.characters.forEach(function (c) { narrativeProvided.turning_points = narrativeProvided.turning_points || own.call(c, 'turning_points'); });
    arr(g.storylines).forEach(function (line) {
      narrativeProvided.turning_points = narrativeProvided.turning_points || own.call(line, 'turning_points');
      narrativeProvided.foreshadow_payoffs = narrativeProvided.foreshadow_payoffs || own.call(line, 'foreshadow_payoffs');
    });
    var identityReviews = Object.create(null), eventReviews = Object.create(null);
    arr(g.reviewIssues).forEach(function (issue) {
      if (!obj(issue)) return;
      if (issue.kind === 'identity' && issue.status === 'confirmed_issue' && issue.characterId != null) identityReviews[str(issue.characterId)] = issue;
      if (/^(quote|attribution)$/.test(issue.kind || '') && issue.eventId != null) eventReviews[str(issue.eventId)] = issue;
    });
    g.characters.forEach(function (c) {
      assignId(c, 'ch', { name: c.name || '' });
      if (identityReviews[str(ident(c))]) { c.identityStatus = 'ambiguous'; c.identityReview = clone(identityReviews[str(ident(c))]); }
      c.importanceKnown = number(c.importance) != null;
      if (!c.importanceKnown) c.importance = null;
      if (obj(c.attrs)) Object.keys(c.attrs).forEach(function (k) {
        var a = c.attrs[k]; if (!obj(a)) return;
        if (c.identityStatus === 'ambiguous' || number(a.score) == null || !arr(a.evidence).length) {
          if (number(a.score) != null) { a.reportedScore = a.score; a.unknownReason = 'no_supporting_evidence'; }
          if (c.identityStatus === 'ambiguous') a.unknownReason = 'identity_requires_disambiguation';
          a.score = null; a.pending = true; a.known = false;
        }
      });
    });
    var sourceEvents = g.events.slice(), sourceOrders = [], orderMap = Object.create(null), rawOrderMap = Object.create(null);
    var inputIndex = Object.create(null);
    sourceEvents.forEach(function (e, i) {
      var order = number(e.order); if (order == null) order = rawEventEntries[i].rawIndex + 1;
      sourceOrders[i] = order;
      if (!own.call(e, 'rawOrderKnown')) e.rawOrderKnown = number(e.rawOrder != null ? e.rawOrder : e.order) != null;
      if (!own.call(e, 'rawOrder')) e.rawOrder = e.rawOrderKnown ? e.order : null;
      if (!str(e.title).trim() && str(e.name).trim()) { e.title = str(e.name); e.titleSource = 'name'; }
      assignId(e, 'ev', eventKey(e));
      if (eventReviews[str(ident(e))]) { e.quoteReview = clone(eventReviews[str(ident(e))]); e.verified = false; }
    });
    var decorated = sourceEvents.map(function (e, i) { return { e: e, i: i, order: sourceOrders[i] }; });
    g.meta = meta;
    meta.eventOrdering = sourceAppearanceOrder(decorated, g, warnings);
    g.events = decorated.map(function (d, i) {
      d.e.order = i + 1; inputIndex[str(rawEventEntries[d.i].rawIndex)] = i;
      pushUnique(orderMap, d.order, i); if (d.e.rawOrderKnown) pushUnique(rawOrderMap, d.e.rawOrder, i);
      return d.e;
    });
    if (Array.isArray(g.storylines)) g.storylines = g.storylines.filter(obj).map(function (line) {
      return mapLine(line, orderMap, g.events, warnings);
    });
    g.relations.forEach(function (r) {
      assignId(r, 'rel', { ends: [str(r.a), str(r.b)].sort(), kind: r.kind || '', line: r.line || '' });
      r.strengthKnown = number(r.strength) != null;
      if (!r.strengthKnown) r.strength = null;
    });
    var coverage = obj(meta.coverage) ? meta.coverage : {};
    AUX.forEach(function (field) {
      if (!own.call(g, field)) {
        if (!obj(coverage[field])) coverage[field] = { known: false, reason: 'not_provided' };
        return;
      }
      var value = g[field], explicit = obj(coverage[field]) && typeof coverage[field].known === 'boolean';
      var count = Array.isArray(value) ? value.length : (obj(value) ? Object.keys(value).length : 0);
      var known = explicit ? coverage[field].known : count > 0;
      coverage[field] = Object.assign({}, obj(coverage[field]) ? coverage[field] : {}, {
        known: known, count: count, reason: known ? 'provided' : 'empty_or_unknown'
      });
      if (Array.isArray(value)) value.forEach(function (v) {
        if (!obj(v)) return;
        var key = clone(v); delete key.id; delete key.entityId; delete key.sourceRefs; delete key.provenance;
        assignId(v, field, key);
      });
    });
    var migrations = arr(meta.migrations).slice();
    migrationPath(inputSchema, VERSION).forEach(function (hop) { if (migrations.indexOf(hop) < 0) migrations.push(hop); });
    meta.schema = VERSION; meta.schemaVersion = VERSION; meta.migrations = migrations;
    meta.coverage = coverage;
    meta.eventIndexMap = { rawIndexToNormalized: inputIndex, rawOrderToNormalized: rawOrderMap,
      sourceOrderToNormalized: orderMap, indexBase: 0, orderBase: 1 };

    // ------------------------------------------------------------------ v5
    var aliases = aliasIndex(g.characters);
    var chapters = chapterLedger(g.events);
    var reviewQueue = [];
    g.relations.forEach(function (r) {
      var hits = conflictedTokens(r, aliases.owners);
      r.ambiguousTokens = hits;
      r.attribution = hits.length ? 'review_required' : 'resolved';
      if (hits.length) reviewQueue.push({ token: hits.join('、'), kind: 'relation_endpoint_alias_conflict',
        nodeIds: ident(r) == null ? [] : [ident(r)], ownerCandidates: hits.reduce(function (m, t) { return m.concat(aliases.owners[t]); }, []),
        autoMerged: false, attribution: 'review_required', reason: '关系端点使用了被多个节点声明的名字；未自动归并' });
    });
    g.events.forEach(function (e) {
      var hits = conflictedTokens(e, aliases.owners);
      e.ambiguousTokens = hits;
      e.attribution = hits.length ? 'review_required' : 'resolved';
      if (hits.length) reviewQueue.push({ token: hits.join('、'), kind: 'event_cast_alias_conflict',
        nodeIds: ident(e) == null ? [] : [ident(e)], ownerCandidates: hits.reduce(function (m, t) { return m.concat(aliases.owners[t]); }, []),
        autoMerged: false, attribution: 'review_required', reason: '事件人物表使用了被多个节点声明的名字；未自动归并' });
    });
    g.characters.forEach(function (c) {
      c.chapterIds = [];
      var tokens = [str(c.name)].concat(arr(c.aliases).map(str)).filter(function (t) { return t && arr(aliases.owners[t]).length > 1; });
      c.ambiguousTokens = tokens;
      c.attribution = tokens.length ? 'review_required' : 'resolved';
    });
    var dualConflicts = [];
    function dualOwner(row, kind, key, identityOf) {
      var spec = DUAL_READ[key] || {}, d = dualRead(row, key, spec.also, spec.same === 'locator' ? sourceRefId : identityOf);
      if (d.conflict) dualConflicts.push({ kind: kind, id: ident(row), field: key, fields: d.fields,
        values: d.fields.map(function (f) { return row[f]; }), resolution: 'pending_review' });
      return d;
    }
    g.events.forEach(function (e) { dualOwner(e, 'event', 'chapterLabel'); dualOwner(e, 'event', 'sourceRefs'); });
    g.characters.forEach(function (c) { dualOwner(c, 'character', 'entityId'); });
    g.relations.forEach(function (r) { dualOwner(r, 'relation', 'entityId'); dualOwner(r, 'relation', 'sourceRefs'); });
    meta.dualRead = { fields: Object.keys(DUAL_READ).reduce(function (m, k) { m[k] = k === 'sourceRefs' ? null : (DUAL_READ[k].also || []).slice(); return m; }, {}),
      conflicts: dualConflicts, policy: 'both_spellings_read_no_preference_order', autoMerged: 0 };
    meta.schemaCompat = { reads: READS_DOWN.slice(), wrote: VERSION, inputSchema: inputSchema,
      migrationPath: migrationPath(inputSchema, VERSION), hops: migrationPath(inputSchema, VERSION),
      additive: true, rewritesInput: false };
    meta.identity = identityLedger(g, aliases, chapters, warnings);
    if (reviewQueue.length) {
      meta.identity.reviewQueue = meta.identity.reviewQueue.concat(reviewQueue);
      meta.identity.aliases.pendingRows = reviewQueue.length;
    } else {
      meta.identity.aliases.pendingRows = 0;
    }
    meta.capabilities = Object.assign({}, obj(meta.capabilities) ? meta.capabilities : {}, {
      schema: VERSION, stableEntityIds: true,
      chapterIds: true, legacyAliasRead: true,
      optionalLayers: AUX.reduce(function (m, f) { m[f] = !!coverage[f].known; return m; }, {})
    });
    if (!obj(meta.provenance)) meta.provenance = { known: false, reason: 'source_material_not_attached', sourceIds: [], textHashes: [] };
    meta.sourceWarnings = warnings;
    g.meta = meta;
    return narrativeContract(g, narrativeProvided);
  }

  function reconcile(source, rendered) {
    var raw = normalize(source), out = obj(rendered) ? clone(rendered) : {};
    var sourceById = Object.create(null), byFingerprint = Object.create(null), rawOrders = Object.create(null);
    arr(raw.events).forEach(function (e) {
      sourceById[str(ident(e))] = e;
      var fp = canonical({ chapter: e.chapter || null, title: e.title || null, summary: e.summary || null, quote: e.quote || null });
      if (!own.call(byFingerprint, fp)) byFingerprint[fp] = [];
      byFingerprint[fp].push(e);
    });
    out.events = arr(out.events).filter(obj).map(function (event, i) {
      var match = sourceById[str(ident(event))];
      if (!match) {
        var fp = canonical({ chapter: event.chapter || null, title: event.title || null, summary: event.summary || null, quote: event.quote || null });
        var candidates = byFingerprint[fp] || [];
        if (candidates.length === 1) match = candidates[0];
      }
      var e = match ? Object.assign({}, clone(match), event) : event;
      if (match) {
        e.id = ident(match); e.entityId = match.entityId; e.rawOrder = match.rawOrder;
        pushUnique(rawOrders, match.order, i);
      }
      e.order = i + 1;
      return e;
    });
    out.meta = Object.assign({}, raw.meta, obj(out.meta) ? out.meta : {});
    ['characters', 'relations'].forEach(function (field) {
      var byId = Object.create(null), byKey = Object.create(null);
      function key(v) { return field === 'characters' ? str(v.name) : canonical({ ends: [str(v.a), str(v.b)].sort(), kind: v.kind || '', line: v.line || '' }); }
      arr(raw[field]).forEach(function (v) {
        byId[str(ident(v))] = v;
        var k = key(v); if (!own.call(byKey, k)) byKey[k] = []; byKey[k].push(v);
      });
      out[field] = arr(out[field]).filter(obj).map(function (v) {
        var match = byId[str(ident(v))], candidates = byKey[key(v)] || [];
        if (!match && candidates.length === 1) match = candidates[0];
        var result = match ? Object.assign({}, clone(match), v) : v;
        if (match) { result.id = match.id; result.entityId = match.entityId; }
        return result;
      });
    });
    AUX.forEach(function (f) { if (own.call(raw, f) && !own.call(out, f)) out[f] = clone(raw[f]); });
    var warnings = [];
    if (Array.isArray(raw.storylines)) out.storylines = raw.storylines.map(function (line) {
      return mapLine(line, rawOrders, out.events, warnings);
    });
    var normalized = normalize(out);
    normalized.meta.sourceWarnings = arr(normalized.meta.sourceWarnings).concat(warnings);
    return normalized;
  }

  function sourceRefs(entity) {
    var refs = [], seen = Object.create(null);
    arr(entity && entity.sourceRefs).concat(arr(entity && entity.evidenceRefs),
      [entity && entity.sourceRef, entity && entity.quoteRef, entity && entity.evidenceRef]).filter(obj).forEach(function (ref) {
      var key = canonical(ref);
      if (!seen[key]) { seen[key] = true; refs.push(ref); }
    });
    return refs;
  }
  function anchored(ref) {
    return obj(ref) && ref.verified === true && ref.status === 'verified' && (ref.match == null || ref.match === 'exact') && !!ref.sourceId && !!ref.textHash &&
      number(ref.start) !== null && number(ref.end) !== null && ref.start >= 0 && ref.end > ref.start &&
      Math.floor(ref.start) === ref.start && Math.floor(ref.end) === ref.end && typeof ref.quote === 'string' &&
      ref.end - ref.start === (ref.offsetUnit === 'codepoint' && Array.from ? Array.from(ref.quote).length : ref.quote.length);
  }
  function evidenceStatus(entity) {
    var quotes = [], refs = sourceRefs(entity), code, verified = 0;
    function quote(value) { if (typeof value === 'string' && value.trim() && quotes.indexOf(value.trim()) < 0) quotes.push(value.trim()); }
    quote(entity && entity.quote);
    arr(entity && entity.evidence).forEach(function (item) {
      quote(typeof item === 'string' ? item : item && (item.quote || item.text || item.value));
      if (obj(item)) refs = refs.concat(sourceRefs(item));
    });
    quotes.forEach(function (q) { if (refs.some(function (ref) { return anchored(ref) && ref.quote === q; })) verified++; });
    var basis = basisInfo(entity && (entity.basisCode != null ? entity.basisCode : entity.basis)).code;
    if (entity && (entity.derived || entity.inferred || basis === 'inference')) code = 'inference';
    else if (quotes.length && verified === quotes.length && entity.verified !== false) code = 'verified';
    else if (quotes.length) code = 'quoted';
    else if (!entity || entity.basisCode === 'unverified' || entity.basis === '未核验' || entity.basis === 'uncertain') code = 'unverified';
    else code = 'synthesis';
    var labels = { verified: '原文已核验', quoted: '有引文未核验', synthesis: '归纳', inference: '推导', unverified: '未核验' };
    if (entity && entity.quoteReview) { code = 'quoted'; labels.quoted = '引文归属待确认'; }
    return { code: code, label: labels[code], quotes: quotes, verifiedQuotes: verified,
      unverifiedQuotes: quotes.length - verified,
      anchored: quotes.length > 0 && verified === quotes.length && entity.verified !== false && !entity.quoteReview,
      locateStatus: locateStatusOf(entity, refs, verified, quotes.length) };
  }
  function locateStatusOf(entity, refs, verifiedQuotes, quoteCount) {
    var list = arr(refs).filter(obj);
    if (!list.length) return 'no_ref';
    var hasOffset = list.some(function (r) { return number(r.start) !== null && number(r.end) !== null; });
    if (!hasOffset) return 'unlocatable';
    if (quoteCount > 0 && verifiedQuotes === quoteCount && entity && entity.verified !== false && !entity.quoteReview) return 'anchored';
    return 'unverified_offset';
  }
  function verifyRef(ref, text, textHash) {
    if (!anchored(ref) || typeof text !== 'string') return { verified: false, reason: 'invalid_or_missing_source' };
    if (textHash && textHash !== ref.textHash) return { verified: false, reason: 'source_hash_mismatch' };
    var part = ref.offsetUnit === 'codepoint' && Array.from ? Array.from(text).slice(ref.start, ref.end).join('') : text.slice(ref.start, ref.end);
    var ok = part === ref.quote;
    return { verified: ok, hashVerified: textHash ? true : null, reason: ok ? 'exact' : 'quote_mismatch' };
  }
  function inspect(input) {
    var g = obj(input) ? input : {}, meta = obj(g.meta) ? g.meta : {}, warnings = arr(meta.sourceWarnings).slice();
    var counts = {}, ids = Object.create(null), refs = { total: 0, anchored: 0, unverified: 0 }, emptyCast = 0;
    ['characters', 'events', 'relations', 'storylines'].concat(AUX).forEach(function (field) {
      counts[field] = Array.isArray(g[field]) ? g[field].length : null;
      arr(g[field]).forEach(function (e) {
        if (!obj(e)) return;
        var id = ident(e);
        if (id != null && id !== '') {
          if (own.call(ids, str(id))) warnings.push({ code: 'duplicate-entity-id', entityId: id, field: field });
          ids[str(id)] = field;
        }
        sourceRefs(e).forEach(function (ref) { refs.total++; if (anchored(ref)) refs.anchored++; else refs.unverified++; });
        if (field === 'events' && !arr(e.characters).length) emptyCast++;
        if (field === 'characters' && obj(e.attrs)) Object.keys(e.attrs).forEach(function (k) {
          sourceRefs(e.attrs[k]).forEach(function (ref) { refs.total++; if (anchored(ref)) refs.anchored++; else refs.unverified++; });
        });
      });
    });
    var coverage = clone(obj(meta.coverage) ? meta.coverage : {});
    AUX.forEach(function (f) {
      if (!obj(coverage[f])) coverage[f] = { known: false, reason: own.call(g, f) ? 'not_declared' : 'not_provided' };
    });
    var extraction = obj(meta.extraction) ? clone(meta.extraction) : { mode: meta.mode || 'unknown',
      complete: null, reason: 'legacy_coverage_unknown' };
    var compat = obj(meta.schemaCompat) ? clone(meta.schemaCompat) : null;
    if (compat && READS_DOWN.indexOf(str(compat.inputSchema)) < 0) warnings.push({ code: 'unlisted-input-schema', schema: compat.inputSchema });
    return { schema: meta.schemaVersion || meta.schema || 'legacy', version: VERSION,
      readsDown: READS_DOWN.slice(), additive: true, schemaCompat: compat,
      identity: clone(obj(meta.identity) ? meta.identity : null),
      dualRead: clone(obj(meta.dualRead) ? meta.dualRead : null),
      reviewQueue: clone(arr(obj(meta.identity) && meta.identity.reviewQueue)),
      counts: counts, coverage: coverage, capabilities: clone(meta.capabilities || {}),
      provenance: clone(meta.provenance || { known: false }), sources: clone(arr(meta.sources)),
      extraction: extraction, sourceRefs: refs, worldEvents: emptyCast,
      eventIndexMap: clone(meta.eventIndexMap || null), warnings: warnings,
      complete: extraction.complete === true ? true : (extraction.complete === false ? false : null) };
  }

  function entityKey(item) {
    if (!obj(item)) return null;
    var id = ident(item);
    if (id != null && id !== '') return 'id:' + str(id);
    return 'v:' + canonical(item);
  }
  function legacyDiff(original, migrated) {
    var out = [], seen = 0, indexed = 0;
    function walk(before, after, path) {
      if (!obj(before)) return;
      Object.keys(before).forEach(function (k) {
        if (k === 'meta' || k === '__proto__' || k === 'constructor' || k === 'prototype') return;
        var b = before[k], a = obj(after) ? after[k] : undefined;
        if (Array.isArray(b)) {
          if (!Array.isArray(a)) { out.push({ path: path + '.' + k, reason: 'dropped' }); return; }
          var keyed = b.length > 0 && b.every(function (row) { return entityKey(row) != null; });
          if (keyed) {
            indexed++;
            var pool = Object.create(null);
            a.forEach(function (row) { var kk = entityKey(row); if (kk != null) pushUnique(pool, kk, row); });
            b.forEach(function (row, i) {
              var kk = entityKey(row), hits = pool[kk] || [];
              var at = path + '.' + k + '[' + kk + ']';
              if (!hits.length) { out.push({ path: at, reason: 'dropped' }); return; }
              walk(row, hits[0], at);
            });
            return;
          }
          if (b.length !== a.length) out.push({ path: path + '.' + k, reason: 'length_changed', before: b.length, after: a.length });
          var n = Math.min(b.length, a.length);
          for (var i = 0; i < n; i++) walk(b[i], a[i], path + '.' + k + '[' + i + ']');
          return;
        }
        if (obj(b)) { walk(b, a, path + '.' + k); return; }
        seen++;
        if (a === undefined) { out.push({ path: path + '.' + k, reason: 'dropped' }); return; }
        if (canonical(b) !== canonical(a)) out.push({ path: path + '.' + k, reason: 'rewritten', before: b, after: a });
      });
    }
    walk(obj(original) ? original : {}, obj(migrated) ? migrated : {}, '');
    return { compared: seen, indexedArrays: indexed, changed: out };
  }

  var DOCUMENTED_REWRITES = [{ path: 'events[].order', recoverable: 'rawOrder + meta.eventIndexMap.rawOrderToNormalized' }];
  var EVENT_ORDER_PATH = /(?:^|\.)events\[([^\]]+)\]\.order$/;
  function unrecoverableRewrites(original, migrated, diff) {
    var events = arr(obj(original) && original.events);
    var byId = Object.create(null);
    events.forEach(function (e, i) { var id = ident(e); if (id != null && id !== '') byId[str(id)] = e; });
    var migratedEvents = arr(obj(migrated) && migrated.events);
    var migratedById = Object.create(null);
    migratedEvents.forEach(function (e) { var id = ident(e); if (id != null && id !== '') migratedById[str(id)] = e; });
    var out = [];
    diff.changed.forEach(function (row) {
      var hit = row.reason === 'rewritten' ? EVENT_ORDER_PATH.exec(str(row.path)) : null;
      if (!hit) { out.push(row); return; }
      var token = hit[1];
      var before = own.call(byId, token) ? byId[token] : events[+token];
      var after = own.call(migratedById, token) ? migratedById[token] : null;
      if (obj(after) && canonical(after.rawOrder) === canonical(row.before)) return;
      void before;
      out.push({ path: row.path, reason: 'documented_rewrite_not_recoverable', before: row.before, after: row.after });
    });
    return out;
  }

  function migrationPlan(input) {
    var g = obj(input) ? input : {}, meta = obj(g.meta) ? g.meta : {};
    var from = str(meta.schemaVersion || meta.schema || 'legacy');
    var hops = migrationPath(from, VERSION);
    return { from: from, to: VERSION, hops: hops, needed: hops.length > 0,
      additive: true, rewritesInput: false, preservesLegacyFields: true,
      documentedRewrites: clone(DOCUMENTED_REWRITES),
      published: obj(meta.revision) ? { key: str(meta.revision.key), parentKey: str(meta.revision.parentKey),
        originalPreserved: meta.revision.originalPreserved === true } : null,
      inPlaceAllowed: !obj(meta.revision) };
  }
  function applyMigration(input, options) {
    var opts = obj(options) ? options : {}, plan = migrationPlan(input);
    if (plan.published && opts.allowPublished !== true) {
      return { ok: false, applied: false, reason: 'published_revision_not_migrated_in_place', plan: plan };
    }
    var out = normalize(input);
    var diff = legacyDiff(obj(input) ? input : {}, out);
    var bad = unrecoverableRewrites(obj(input) ? input : {}, out, diff);
    if (bad.length) return { ok: false, applied: false, reason: 'migration_not_additive', plan: plan,
      graph: out, changed: diff.changed, unrecoverable: bad, legacyFieldsPreserved: false };
    return { ok: true, applied: true, plan: migrationPlan(out), graph: out,
      rewritesInput: false, legacyFieldsPreserved: true, hops: plan.hops.slice(),
      documentedRewrites: clone(DOCUMENTED_REWRITES), changed: diff.changed };
  }

  function stripContractFields(graph) {
    var out = clone(obj(graph) ? graph : {}), meta = obj(out.meta) ? out.meta : {};
    var fields = ['schemaCompat', 'identity', 'dualRead'];
    var removed = fields.filter(function (f) { return own.call(meta, f); });
    fields.forEach(function (f) { delete meta[f]; });
    if (obj(meta.capabilities)) { delete meta.capabilities.chapterIds; delete meta.capabilities.legacyAliasRead; }
    if (meta.schemaVersion === VERSION) {
      meta.schemaVersion = str(meta.schemaCompat && meta.schemaCompat.inputSchema) === VERSION ? 'castline/4'
        : str(removed.length ? (obj(graph.meta) && obj(graph.meta.schemaCompat) ? graph.meta.schemaCompat.inputSchema : '') : '') || 'castline/4';
      meta.schema = meta.schemaVersion;
    }
    out.meta = meta;
    return { graph: out, restoredFields: removed.slice().sort() };
  }
  function rollbackMigration(migrated, snapshot) {
    var stripped = stripContractFields(migrated);
    var out = stripped.graph, meta = obj(out.meta) ? out.meta : {};
    if (obj(snapshot)) {
      out = clone(snapshot);
      meta = obj(out.meta) ? out.meta : {};
    }
    var before = obj(migrated) && obj(migrated.meta) ? migrated.meta : {};
    return { ok: true, applied: stripped.restoredFields.length > 0, graph: out,
      restoredFields: stripped.restoredFields, snapshotUsed: obj(snapshot),
      fromSchema: str(before.schemaVersion || before.schema || 'legacy'),
      toSchema: str(meta.schemaVersion || meta.schema || 'legacy'),
      rewroteLegacyFields: false };
  }

  var api = { version: VERSION, narrativeVersion: NARRATIVE_VERSION, optionalFields: AUX.slice(), normalize: normalize, reconcile: reconcile,
    inspect: inspect, stableId: stableId, sourceRefs: sourceRefs, verifyRef: verifyRef, evidenceStatus: evidenceStatus,
    chapterId: chapterId, evidenceId: evidenceId, sourceRefId: sourceRefId, aliasIndex: aliasIndex,
    migrationPlan: migrationPlan, applyMigration: applyMigration, rollbackMigration: rollbackMigration,
    readsDown: READS_DOWN.slice(), writesSchema: VERSION };
  root.CLAtlasSource = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
