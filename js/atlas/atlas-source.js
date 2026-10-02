/* Castline · v4 source boundary. Pure adapter: no DOM, storage, network or model calls.
 * Optional entity layers are never fabricated. Source offsets are accepted only
 * as explicit references; summary prose is never treated as quoted source text.
 */
(function (root) {
  'use strict';
  var VERSION = 'castline/4';
  var AUX = ['locations', 'items', 'worldRules', 'clues', 'causeEdges', 'characterStates'];
  var own = Object.prototype.hasOwnProperty;

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
  function mapLine(line, orderMap, events, warnings) {
    var out = clone(line), indexes = [];
    arr(line.events).forEach(function (order) {
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
    if (attach && targets.length === 1) out.attach_order = events[targets[0]].order;
    else if (attach) { out.attach_order = 0; warnings.push({ code: 'unresolved-attach-order', entityId: ident(line), order: attach }); }
    assignId(out, 'sl', { name: out.name || out.title, eventIds: out.eventIds });
    return out;
  }

  function normalize(input) {
    var g = obj(input) ? clone(input) : {}, meta = obj(g.meta) ? g.meta : {};
    var warnings = [], inputSchema = str(meta.schemaVersion || meta.schema || 'legacy');
    g.characters = arr(g.characters).filter(obj);
    var rawEventEntries = arr(g.events).map(function (e, i) { return { e: e, rawIndex: i }; }).filter(function (d) { return obj(d.e); });
    g.events = rawEventEntries.map(function (d) { return d.e; });
    g.relations = arr(g.relations).filter(obj);
    g.characters.forEach(function (c) {
      assignId(c, 'ch', { name: c.name || '' });
      c.importanceKnown = number(c.importance) != null;
      if (!c.importanceKnown) c.importance = null;
      if (obj(c.attrs)) Object.keys(c.attrs).forEach(function (k) {
        var a = c.attrs[k]; if (!obj(a)) return;
        if (number(a.score) == null || !arr(a.evidence).length) {
          if (number(a.score) != null) { a.reportedScore = a.score; a.unknownReason = 'no_supporting_evidence'; }
          a.score = null; a.pending = true; a.known = false;
        }
      });
    });
    var sourceEvents = g.events.slice(), sourceOrders = [], orderMap = Object.create(null), rawOrderMap = Object.create(null);
    var inputIndex = Object.create(null);
    sourceEvents.forEach(function (e, i) {
      var order = number(e.order); if (order == null) order = rawEventEntries[i].rawIndex + 1;
      sourceOrders[i] = order;
      if (e.rawOrder == null) e.rawOrder = order;
      assignId(e, 'ev', eventKey(e));
    });
    // Stable order: equal input orders keep input array order, and remain
    // explicitly ambiguous to storyline references rather than silently
    // choosing the first event with that order.
    var decorated = sourceEvents.map(function (e, i) { return { e: e, i: i, order: sourceOrders[i] }; });
    decorated.sort(function (a, b) { return a.order - b.order || a.i - b.i; });
    g.events = decorated.map(function (d, i) {
      d.e.order = i + 1; inputIndex[str(rawEventEntries[d.i].rawIndex)] = i;
      pushUnique(orderMap, d.order, i); pushUnique(rawOrderMap, d.e.rawOrder, i);
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
    var migrations = arr(meta.migrations).slice(), transition = inputSchema + '>' + VERSION;
    if (inputSchema !== VERSION && migrations.indexOf(transition) < 0) migrations.push(transition);
    meta.schema = VERSION; meta.schemaVersion = VERSION; meta.migrations = migrations;
    meta.coverage = coverage;
    meta.eventIndexMap = { rawIndexToNormalized: inputIndex, rawOrderToNormalized: rawOrderMap,
      sourceOrderToNormalized: orderMap, indexBase: 0, orderBase: 1 };
    meta.capabilities = Object.assign({}, obj(meta.capabilities) ? meta.capabilities : {}, {
      schema: VERSION, stableEntityIds: true,
      optionalLayers: AUX.reduce(function (m, f) { m[f] = !!coverage[f].known; return m; }, {})
    });
    if (!obj(meta.provenance)) meta.provenance = { known: false, reason: 'source_material_not_attached', sourceIds: [], textHashes: [] };
    meta.sourceWarnings = warnings;
    g.meta = meta;
    return g;
  }

  function reconcile(source, rendered) {
    // UI normalizers may sort/filter/rebuild objects. Restore their source
    // identity and exact storyline references without reintroducing filtered
    // events. Nothing is matched by current array index.
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
    var refs = arr(entity && entity.sourceRefs).filter(obj);
    if (!refs.length && obj(entity && entity.quoteRef)) refs = [entity.quoteRef];
    if (!refs.length && obj(entity && entity.evidenceRef)) refs = [entity.evidenceRef];
    return refs;
  }
  function anchored(ref) {
    return obj(ref) && ref.verified === true && ref.status === 'verified' && !!ref.sourceId && !!ref.textHash &&
      number(ref.start) !== null && number(ref.end) !== null && ref.start >= 0 && ref.end > ref.start &&
      Math.floor(ref.start) === ref.start && Math.floor(ref.end) === ref.end && typeof ref.quote === 'string';
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
    return { schema: meta.schemaVersion || meta.schema || 'legacy', version: VERSION,
      counts: counts, coverage: coverage, capabilities: clone(meta.capabilities || {}),
      provenance: clone(meta.provenance || { known: false }), sources: clone(arr(meta.sources)),
      extraction: extraction, sourceRefs: refs, worldEvents: emptyCast,
      eventIndexMap: clone(meta.eventIndexMap || null), warnings: warnings,
      // An extracted result is not a proof that every narrative fact was
      // covered. Full-book semantic completeness remains independently unknown.
      complete: extraction.complete === true ? true : (extraction.complete === false ? false : null) };
  }

  var api = { version: VERSION, optionalFields: AUX.slice(), normalize: normalize, reconcile: reconcile,
    inspect: inspect, stableId: stableId, sourceRefs: sourceRefs, verifyRef: verifyRef };
  root.CLAtlasSource = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
