(function (g) {
  'use strict';

  function uniq(a) { var s = {}, o = []; for (var i = 0; i < a.length; i++) if (a[i] && !s[a[i]]) { s[a[i]] = 1; o.push(a[i]); } return o; }

  var CN_DIG = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  function cnNum(s) {
    if (/^\d+$/.test(s)) return +s;
    var total = 0, sec = 0, cur = 0, i, ch;
    for (i = 0; i < s.length; i++) {
      ch = s[i];
      if (CN_DIG[ch] !== undefined) cur = CN_DIG[ch];
      else if (ch === '十') { sec += (cur || 1) * 10; cur = 0; }
      else if (ch === '百') { sec += (cur || 1) * 100; cur = 0; }
      else if (ch === '千') { sec += (cur || 1) * 1000; cur = 0; }
      else return null;
    }
    total = sec + cur;
    return total || null;
  }
  function chapterNo(name) {
    var s = String(name || ''), m = /第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*[回章节集幕]/.exec(s) || /第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*卷/.exec(s);
    return m ? cnNum(m[1]) : null;
  }
  function chapterShort(name) {
    var s = String(name || '').replace(/^第\s*[0-9零〇一二两三四五六七八九十百千]+\s*[回章节卷集幕]\s*/, '');
    s = s.split(/[\s　]+/)[0] || s;
    return s.length > 10 ? s.slice(0, 9) + '…' : s;
  }
  function chapterVolume(model, c) {
    var found = null;
    ((model.axis && model.axis.volumes) || []).forEach(function (v) { if (v.c <= c) found = v; });
    return found;
  }
  function chapterLabel(model, c) {
    var ch = model && model.chapters[c], axis = model && model.axis || {};
    if (!ch) return '未分章';
    if (ch.special || ch.raw === null || ch.no == null) return ch.name || '未分章';
    if (axis.mode === 'seq') {
      var volume = chapterVolume(model, c);
      return volume && ch.raw != null ? volume.label + ' · 第 ' + ch.raw + ' ' + (axis.unit || '回') : ch.name || '未分章';
    }
    return '第 ' + ch.no + ' ' + (axis.unit || '回');
  }
  function chapterSpan(model, a, b) {
    var ca = model.chapters[a], cb = model.chapters[b], axis = model.axis || {};
    if (axis.mode === 'seq' && ca && cb && !ca.special && !cb.special && ca.raw != null && cb.raw != null) {
      var va = chapterVolume(model, a), vb = chapterVolume(model, b);
      if (va && vb && va.c === vb.c) return va.label + ' · 第 ' + ca.raw + (ca.raw === cb.raw ? '' : '–' + cb.raw) + ' ' + (axis.unit || '回');
    }
    if (ca && cb && !ca.special && !cb.special && ca.raw !== null && cb.raw !== null && ca.no != null && cb.no != null && axis.mode !== 'seq') {
      return '第 ' + ca.no + (ca.no === cb.no ? '' : '–' + cb.no) + ' ' + (axis.unit || '回');
    }
    return chapterLabel(model, a) + (a === b ? '' : ' — ' + chapterLabel(model, b));
  }

  var SPECIAL = /番外|未分章|附录|楔子|序章|尾声|后记|外传/;
  function chapterTitleNorm(s) {
    return String(s == null ? '' : s).replace(/[\s\u3000]+/g, ' ').trim()
      .replace(/^(?:[（(](?:末|未标回目|未题回目)[）)]|末尾|末)$/, '').trim();
  }
  function chapterAliases(chs) {
    var names = [], oldToNew = [], byName = Object.create(null);
    var scope = Object.create(null);
    chs.forEach(function (name, i) {
      var m = /^第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*([回章节集幕])(.*)$/.exec(String(name || '').trim());
      var parsed = m && !SPECIAL.test(name) ? { no: cnNum(m[1]), unit: m[2], title: chapterTitleNorm(m[3]) } : null;
      if (!parsed || parsed.no == null) {
        names.push(name); scope = Object.create(null);
        oldToNew[i] = names.length - 1; byName[name] = names.length - 1;
        return;
      }
      var key = parsed.unit + '|' + parsed.no, rec = scope[key];
      if (!rec) {
        names.push(name);
        scope[key] = { index: names.length - 1, title: parsed.title, conflicted: false };
      } else if (rec.conflicted) {
        names.push(name);
      } else if (!rec.title || !parsed.title || rec.title === parsed.title) {
        if (!rec.title && parsed.title) { names[rec.index] = name; rec.title = parsed.title; }
      } else {
        rec.conflicted = true;
        names.push(name);
      }
      oldToNew[i] = names.length - 1; byName[name] = names.length - 1;
    });
    return { names: names, oldToNew: oldToNew, byName: byName };
  }
  function axisOf(chs) {
    var raw = chs.map(function (c) { return SPECIAL.test(String(c || '')) ? null : chapterNo(c); }), prev = -Infinity, mono = true, parsed = 0, unitCnt = {}, vols = [];
    raw.forEach(function (n, i) {
      var m = /第\s*[0-9零〇一二两三四五六七八九十百千]+\s*([回章节集幕])/.exec(String(chs[i] || ''));
      if (m) unitCnt[m[1]] = (unitCnt[m[1]] || 0) + 1;
      if (n == null) return;
      parsed++;
      if (n <= prev) { mono = false; if (n === 1 && n < prev && i > 0) vols.push(i); }
      prev = n;
    });
    var unit = '回', best = 0;
    Object.keys(unitCnt).forEach(function (u) { if (u !== '卷' && unitCnt[u] > best) { best = unitCnt[u]; unit = u; } });
    var seq = !mono || parsed < chs.length * 0.6;
    var extra = chs.length - parsed;
    return { mode: seq ? 'seq' : 'no', unit: unit, volumes: seq && vols.length ? [0].concat(vols).map(function (c, k) { return { c: c, label: '卷' + (k + 1) }; }) : [], raw: raw,
      summary: seq ? chs.length + ' 个章节段' : parsed + ' ' + unit + '已解析' + (extra ? ' · ' + extra + ' 段其他材料' : '') };
  }

  var SAL_DEC = /大败|大破|大溃|溃败|败亡|火烧|火攻|水淹|灭|篡|称帝|即位|受禅|登基|归天|托孤|之死|身亡|殒命|遇害|自刎|病逝|病亡|决战|攻陷|失守|陷落|投降|出降|归降|夺取|攻取|收服|成真|成佛|功成|结局|终局/;
  var SAL_DEATH = /死|亡|殒|薨|崩|遇害|被杀|被斩|自刎|归天|病逝|身故|阵亡|圆寂|坐化|伏诛/;
  var SAL_W = { dec: 2, mech: 1, arc: 1, syn: 1, evq: 1, peak: 1, cast: 0.6, line: 1, exit: 1, judg: 1, call: 1, cause: 1, head: 2, camp: 1 };
  var KEY_SHARE = 0.13, salCache = typeof WeakMap === 'function' ? new WeakMap() : null;
  function bigrams(s) { s = String(s || '').replace(/[^一-鿿]+/g, ' '); var o = {}, i; for (i = 0; i + 1 < s.length; i++) if (s[i] !== ' ' && s[i + 1] !== ' ') o[s.substr(i, 2)] = 1; return o; }
  function storylineProvenance(G, line) {
    var meta = G && G.meta || {}, current = meta.storylines || {}, node = line || {}, id = node.sourceId != null ? node.sourceId : node.id;
    if (node.derived === true || node.src === 'derived' || node.src === 'local-completion') return 'derived';
    var matches = id == null ? [] : (G && G.storylines || []).filter(function (item) { return item && String(item.id != null ? item.id : item.entityId) === String(id); });
    if (matches.length === 1) node = matches[0];
    if (node.derived === true || node.src === 'derived' || node.src === 'local-completion' || node.provenance === 'local-completion') return 'derived';
    if (node.provenance === 'assistant-reviewed-source') return 'assistant-reviewed-source';
    if (node.provenance === 'model') return 'synthesis';
    if (current.derived === true || current.src === 'local-completion' || current.src === 'derived') return 'derived';
    if (current.src === 'assistant-reviewed-source') return 'assistant-reviewed-source';
    if (current.src === 'model' || current.src === 'mixed') return 'synthesis';
    return meta.completion && meta.completion.method === 'existing-graph-local-completion' ? 'derived' : 'synthesis';
  }
  function derivedLines(G) {
    var lines = (G.storylines || []).filter(function (line) { return line && typeof line === 'object'; });
    return lines.length ? lines.every(function (line) { return storylineProvenance(G, line) === 'derived'; }) : storylineProvenance(G) === 'derived';
  }

  function relationRefAnchored(ref) {
    return !!(ref && typeof ref === 'object' && ref.verified === true && ref.status === 'verified' &&
      (ref.match == null || ref.match === 'exact') && !!ref.sourceId && !!ref.textHash &&
      typeof ref.start === 'number' && typeof ref.end === 'number' && isFinite(ref.start) && isFinite(ref.end) &&
      ref.start >= 0 && ref.end > ref.start && Math.floor(ref.start) === ref.start && Math.floor(ref.end) === ref.end &&
      typeof ref.quote === 'string' &&
      ref.end - ref.start === (ref.offsetUnit === 'codepoint' && typeof Array.from === 'function' ? Array.from(ref.quote).length : ref.quote.length));
  }
  function relationAnchored(r) {
    if (!r || typeof r !== 'object') return false;
    if (r.quoteVerified === true) return true;
    var refs = [].concat(r.sourceRefs || [], r.evidenceRefs || []);
    for (var i = 0; i < refs.length; i++) if (relationRefAnchored(refs[i])) return true;
    return false;
  }
  function relationHonesty(G) {
    var rels = (G && Array.isArray(G.relations)) ? G.relations : [], items = [], anchored = 0, i;
    for (i = 0; i < rels.length; i++) {
      var ok = relationAnchored(rels[i]);
      if (ok) anchored++;
      items.push({ index: i, evidence: ok ? 'anchored' : 'inherited-pending', label: ok ? '原文锚点' : '继承 · 待核验' });
    }
    return { version: 'relationHonesty/1', total: rels.length, anchored: anchored, inherited: rels.length - anchored, items: items };
  }

  function compareRelations(G, aId, bId, options) {
    options = options || {};
    function list(v) { return Array.isArray(v) ? v : []; }
    function key(v) { return v == null || v === '' ? null : String(v); }
    function add(map, k, v) {
      if (k == null) return;
      var rows = map[k] || (map[k] = []);
      if (rows.indexOf(v) < 0) rows.push(v);
    }
    function sortedRows(map) { return Object.keys(map).map(function (k) { return map[k]; }); }
    var a = key(aId), b = key(bId), rels = G && Array.isArray(G.relations) ? G.relations : null;
    var empty = { ok: false, mode: 'unavailable', aId: a, bId: b, common: [], onlyA: [], onlyB: [],
      kinds: [], stats: { sourceRelations: rels ? rels.length : 0, includedRelations: 0, copresenceExcluded: 0,
        scopeExcluded: 0, kindFiltered: 0, duplicateEdges: 0, conflictingRelationIds: 0,
        selfEdges: 0, directPairEdges: 0, ambiguousEndpoints: 0, unresolvedEndpoints: 0,
        identityVetoEndpoints: 0 }, reason: '' };
    if (!G || !Array.isArray(G.characters) || !rels) { empty.reason = 'graph_or_relations_missing'; return empty; }
    var source = g.CLAtlasSource, relationScope = g.CLSkyRelationScope;
    if (!source || typeof source.aliasIndex !== 'function' || !relationScope || typeof relationScope.of !== 'function') {
      empty.reason = 'identity_or_relation_adapter_missing'; return empty;
    }
    var characters = G.characters.filter(function (c) { return c && typeof c === 'object' && !Array.isArray(c); }), idRows = Object.create(null), personById = Object.create(null);
    characters.forEach(function (c) {
      if (!c || typeof c !== 'object') return;
      var cid = key(c.id), eid = key(c.entityId), stable = cid || eid;
      if (cid != null) add(idRows, cid, c);
      if (eid != null && eid !== cid) add(idRows, eid, c);
      if (stable != null) add(personById, stable, c);
    });
    var alias = source.aliasIndex(characters), aliasOwners = alias && alias.owners || Object.create(null);
    function identityProblem(c) {
      var status = String(c && c.identityStatus || '').trim().toLowerCase();
      if (c && (c.identityReview || c.identityConflict === true || c.identityPending === true)) return status || 'review_required';
      return status && status !== 'resolved' ? status : '';
    }
    function uniquePerson(id) {
      var rows = idRows[id] || [];
      if (rows.length !== 1) return { person: null, status: rows.length ? 'duplicate_id' : 'missing_id' };
      var c = rows[0], cid = key(c.id), eid = key(c.entityId);
      if (cid != null && eid != null && cid !== eid) return { person: null, status: 'id_entity_id_conflict' };
      var identityStatus = identityProblem(c);
      if (identityStatus) return { person: null, status: 'identity_' + identityStatus };
      var stable = cid || eid;
      if (!stable || stable !== id) return { person: null, status: 'id_mismatch' };
      if ((personById[stable] || []).length !== 1) return { person: null, status: 'duplicate_id' };
      return { person: c, id: stable, status: 'resolved' };
    }
    var aPerson = a == null ? { person: null, status: 'missing_id' } : uniquePerson(a);
    var bPerson = b == null ? null : uniquePerson(b);
    if (!aPerson.person) { empty.reason = 'a_' + aPerson.status; return empty; }
    if (b != null && !bPerson.person) { empty.reason = 'b_' + bPerson.status; return empty; }
    if (b != null && a === b) { empty.reason = 'same_person'; return empty; }

    function resolveEndpoint(value) {
      var token = key(value);
      if (token == null) return { status: 'missing_endpoint' };
      if (idRows[token]) return uniquePerson(token);
      var owners = list(aliasOwners[token]);
      if (owners.length !== 1 || owners[0] == null || owners[0] === '') {
        return { status: owners.length > 1 ? 'ambiguous_alias' : 'unresolved_alias' };
      }
      return uniquePerson(String(owners[0]));
    }
    var scope = options.scope && typeof options.scope === 'object' ? options.scope : {};
    var permittedIds = Array.isArray(scope.relationIds) ? Object.create(null) : null;
    if (permittedIds) scope.relationIds.forEach(function (id) { permittedIds[String(id)] = true; });
    function permitted(rel, index, relId) {
      if (permittedIds && !permittedIds[relId == null ? '' : relId]) return false;
      if (typeof scope.allowsRelation === 'function' && !scope.allowsRelation(rel, index)) return false;
      return true;
    }
    var edges = [], noIdSeen = Object.create(null), kinds = Object.create(null);
    function stable(value) {
      if (Array.isArray(value)) return value.map(stable);
      if (value && typeof value === 'object') {
        var out = {}; Object.keys(value).sort().forEach(function (k) { out[k] = stable(value[k]); }); return out;
      }
      return value;
    }
    var rawById = Object.create(null), rawSignature = typeof WeakMap === 'function' ? new WeakMap() : null;
    rels.forEach(function (rel) {
      if (!rel || typeof rel !== 'object' || Array.isArray(rel)) return;
      var rawId = key(rel.id) || key(rel.entityId);
      if (key(rel.id) && key(rel.entityId) && key(rel.id) !== key(rel.entityId)) {
        empty.stats.conflictingRelationIds++;
        if (rawSignature) rawSignature.set(rel, 'id-conflict:' + key(rel.id) + ':' + key(rel.entityId));
        return;
      }
      if (rawId == null) return;
      var sig = JSON.stringify(stable(rel));
      if (rawSignature) rawSignature.set(rel, sig);
      (rawById[rawId] || (rawById[rawId] = [])).push({ rel: rel, signature: sig });
    });
    var badRelationIds = Object.create(null), duplicateRawIds = Object.create(null);
    Object.keys(rawById).forEach(function (id) {
      var signatures = Object.create(null);
      rawById[id].forEach(function (row) { signatures[row.signature] = true; });
      if (Object.keys(signatures).length > 1) { badRelationIds[id] = true; empty.stats.conflictingRelationIds++; }
      else if (rawById[id].length > 1) duplicateRawIds[id] = true;
    });
    rels.forEach(function (rel, index) {
      if (!rel || typeof rel !== 'object' || Array.isArray(rel)) { empty.stats.unresolvedEndpoints++; return; }
      var relId0 = key(rel.id), entityId = key(rel.entityId);
      var relId = relId0 || entityId;
      if ((relId != null && badRelationIds[relId]) || (relId0 != null && entityId != null && relId0 !== entityId)) return;
      if (!permitted(rel, index, relId)) { empty.stats.scopeExcluded++; return; }
      var meta = relationScope.of(rel);
      if (meta.isCopresence) { empty.stats.copresenceExcluded++; return; }
      var kind = meta.kind || 'other';
      kinds[kind] = { code: kind, label: meta.kindLabel || '其他类型' };
      var left = resolveEndpoint(rel.a), right = resolveEndpoint(rel.b);
      if (!left.person || !right.person) {
        if (left.status === 'ambiguous_alias' || right.status === 'ambiguous_alias' || left.status === 'duplicate_id' || right.status === 'duplicate_id' || left.status === 'id_entity_id_conflict' || right.status === 'id_entity_id_conflict' || /^identity_/.test(left.status || '') || /^identity_/.test(right.status || '')) empty.stats.ambiguousEndpoints++;
        else empty.stats.unresolvedEndpoints++;
        if (/^identity_/.test(left.status || '') || /^identity_/.test(right.status || '')) empty.stats.identityVetoEndpoints++;
        return;
      }
      if (left.id === right.id) { empty.stats.selfEdges++; return; }
      if ((left.id === a && right.id === b) || (left.id === b && right.id === a)) { empty.stats.directPairEdges++; return; }
      var signature = relId == null ? JSON.stringify(stable({ endpoints: left.id < right.id ? [left.id, right.id] : [right.id, left.id],
        kind: kind, line: rel.line || '', description: rel.desc || rel.description || '', scope: rel.scope,
        fromChapter: rel.fromChapter, toChapter: rel.toChapter, chapterRange: rel.chapterRange,
        chapterSpan: rel.chapterSpan, eventIds: rel.eventIds, events: rel.events,
        quoteVerified: rel.quoteVerified, sourceRefs: rel.sourceRefs, evidenceRefs: rel.evidenceRefs })) : rawSignature && rawSignature.get(rel);
      edges.push({ relation: rel, index: index, id: relId, signature: signature, leftId: left.id, rightId: right.id,
        left: left.person, right: right.person, meta: meta, recordUnique: relId == null || !duplicateRawIds[relId] });
    });
    var byRelId = Object.create(null), unique = [];
    edges.forEach(function (edge) {
      if (edge.id == null) {
        if (noIdSeen[edge.signature]) { empty.stats.duplicateEdges++; return; }
        noIdSeen[edge.signature] = true; unique.push(edge); return;
      }
      add(byRelId, edge.id, edge);
    });
    Object.keys(byRelId).forEach(function (id) {
      var rows = byRelId[id], signatures = Object.create(null);
      rows.forEach(function (edge) { signatures[edge.signature] = true; });
      if (Object.keys(signatures).length > 1) { empty.stats.conflictingRelationIds++; return; }
      unique.push(rows[0]); empty.stats.duplicateEdges += rows.length - 1;
    });
    if (options.kind && options.kind !== 'all') {
      unique = unique.filter(function (edge) {
        if (String(options.kind) === edge.meta.kind) return true;
        empty.stats.kindFiltered++; return false;
      });
    }
    var setA = Object.create(null), setB = Object.create(null), detailA = Object.create(null), detailB = Object.create(null);
    function addNeighbor(set, details, person, edge, side) {
      var id = side === 'a' ? edge.rightId : edge.leftId;
      if (id === a || id === b) return;
      set[id] = true;
      var c = side === 'a' ? edge.right : edge.left, row = details[id];
      if (!row) row = details[id] = { id: id, name: c.name || '', role: c.role || '', identity: c.identity || '', relations: [] };
      if (!row.relations.some(function (item) { return item.id != null && item.id === edge.id; }) || edge.id == null) {
        row.relations.push({ id: edge.id, kind: edge.meta.kind, kindLabel: edge.meta.kindLabel, evidence: edge.meta.evidence,
          evidenceLabel: edge.meta.evidenceLabel, evidenceHint: edge.meta.evidenceHint, scope: edge.meta.scope,
          scopeLabel: edge.meta.scopeLabel, scopeHint: edge.meta.scopeHint, line: edge.relation.line || '', recordUnique: edge.recordUnique,
          description: edge.relation.desc || edge.relation.description || '' });
      }
    }
    unique.forEach(function (edge) {
      empty.stats.includedRelations++;
      if (edge.leftId === a || edge.rightId === a) addNeighbor(setA, detailA, aPerson.person, edge, edge.leftId === a ? 'a' : 'b');
      if (b != null && (edge.leftId === b || edge.rightId === b)) addNeighbor(setB, detailB, bPerson.person, edge, edge.leftId === b ? 'a' : 'b');
    });
    var common = [], onlyA = [], onlyB = [];
    Object.keys(detailA).forEach(function (id) {
      if (setB[id]) common.push({ id: detailA[id].id, name: detailA[id].name, role: detailA[id].role,
        identity: detailA[id].identity, relationsA: detailA[id].relations, relationsB: (detailB[id] || {}).relations || [] });
      else onlyA.push({ id: detailA[id].id, name: detailA[id].name, role: detailA[id].role,
        identity: detailA[id].identity, relationsA: detailA[id].relations, relationsB: [] });
    });
    Object.keys(detailB).forEach(function (id) { if (!setA[id]) onlyB.push({ id: detailB[id].id, name: detailB[id].name, role: detailB[id].role,
      identity: detailB[id].identity, relationsA: [], relationsB: detailB[id].relations }); });
    function order(rows) { return rows.sort(function (x, y) { return String(x.name).localeCompare(String(y.name), 'zh') || x.id.localeCompare(y.id); }); }
    empty.ok = true; empty.mode = b == null ? 'single' : 'compare'; empty.aId = a; empty.bId = b;
    empty.a = { id: a, name: aPerson.person.name || '', role: aPerson.person.role || '', identity: aPerson.person.identity || '' };
    empty.b = b == null ? null : { id: b, name: bPerson.person.name || '', role: bPerson.person.role || '', identity: bPerson.person.identity || '' };
    empty.common = order(common); empty.onlyA = order(onlyA); empty.onlyB = order(onlyB);
    empty.kinds = Object.keys(kinds).map(function (k) { return kinds[k]; }).sort(function (x, y) { return x.label.localeCompare(y.label, 'zh'); });
    empty.stats.candidateRelations = rels.length; empty.stats.uniqueEdges = unique.length;
    empty.reason = rels.length ? '' : 'relation_records_missing';
    return empty;
  }

  function relationPeople(G) {
    if (!G || !Array.isArray(G.characters) || !g.CLAtlasSource || typeof g.CLAtlasSource.aliasIndex !== 'function') return { ok: false, people: [] };
    var chars = G.characters.filter(function (c) { return c && typeof c === 'object' && !Array.isArray(c); });
    var aliases = g.CLAtlasSource.aliasIndex(chars), owners = aliases && aliases.owners || Object.create(null), ids = Object.create(null);
    chars.forEach(function (c) {
      var id = c.id != null ? String(c.id) : c.entityId != null ? String(c.entityId) : null;
      if (id != null) (ids[id] || (ids[id] = [])).push(c);
    });
    return { ok: true, people: chars.map(function (c) {
      var id = c.id != null ? String(c.id) : c.entityId != null ? String(c.entityId) : null;
      var mismatch = c.id != null && c.entityId != null && String(c.id) !== String(c.entityId);
      var duplicate = id == null || (ids[id] || []).length !== 1;
      var ambiguousName = !!(c.name && (owners[String(c.name)] || []).length > 1);
      var status = String(c.identityStatus || '').trim().toLowerCase();
      var unknownIdentity = !!(c.identityReview || c.identityConflict === true || c.identityPending === true) || (status !== '' && status !== 'resolved');
      return { id: id, name: String(c.name || ''), role: String(c.role || ''), camp: String(c.camp || ''),
        identity: String(c.identity || ''), identityStatus: c.identityStatus || null,
        ambiguousName: ambiguousName, selectable: !!id && !duplicate && !mismatch && !unknownIdentity,
        reason: !id ? '缺少稳定ID' : duplicate ? '稳定ID重复' : mismatch ? '人物双ID不一致' : unknownIdentity ? '人物身份待区分' : '' };
    }) };
  }

  function salience(G) {
    if (!G || !G.events) return { n: 0, score: [], rank: [], key: [], keyCount: 0, share: KEY_SHARE };
    if (salCache && salCache.has(G) && salCache.get(G).n === G.events.length) return salCache.get(G);
    var E = G.events, C = G.characters || [], n = E.length, i, k, P = {}, F = Object.keys(SAL_W);
    F.forEach(function (f) { P[f] = new Float64Array(n); });
    var byName = {}, nameBi = {}, idOf = {}, ordOf = {}, evOf = {}, chOf = [], tdf = {}, sdf = {}, sumBi = [], post = {};
    C.forEach(function (c) { if (!c || !c.name) return; byName[c.name] = c; [c.name].concat(c.aliases || []).forEach(function (a) { Object.assign(nameBi, bigrams(a)); }); });
    function imp(nm) { var c = byName[nm], v = c && +c.importance; return isFinite(v) && v > 0 ? Math.min(100, v) : 8; }
    E.forEach(function (e, j) {
      var id = e.id != null ? e.id : e.entityId; if (id != null) idOf[String(id)] = j; if (e.order != null) ordOf[String(e.order)] = j;
      (e.characters || []).forEach(function (nm) { (evOf[nm] = evOf[nm] || []).push(j); });
      chOf[j] = e.chapterSeq != null ? +e.chapterSeq : chapterNo(e.chapter);
      Object.keys(bigrams(e.title)).forEach(function (b) { tdf[b] = (tdf[b] || 0) + 1; });
      sumBi[j] = bigrams((e.title || '') + ' ' + (e.summary || ''));
      Object.keys(bigrams(e.summary)).forEach(function (b) { sdf[b] = (sdf[b] || 0) + 1; });
      Object.keys(sumBi[j]).forEach(function (b) { (post[b] = post[b] || []).push(j); });
    });
    var lineDer = derivedLines(G), lines = (G.storylines || []).filter(function (l) { return l && typeof l === 'object' && storylineProvenance(G, l) !== 'derived'; });
    var lineIdx = lines.map(function (l) {
      var ix = [], src = Array.isArray(l.eventIds) && l.eventIds.length ? l.eventIds.map(function (x) { return idOf[String(x)]; }) : (l.events || []).map(function (o) { return ordOf[String(o)]; });
      src.forEach(function (j) { if (j != null && ix.indexOf(j) < 0) ix.push(j); }); return ix.sort(function (a, b) { return a - b; });
    });
    function lw(l) { return l.kind === '主线' || l.kind === 'main' ? 1 : l.kind === '末梢' || l.kind === 'twig' ? 0.3 : 0.6; }
    var lineBi = lines.map(function (l) { return bigrams([l.name, l.goal, l.obstacle, l.outcome].join(' ')); });
    var byCh = {}, laterJ = [];
    E.forEach(function (e, j) { (byCh[chapterNo(e.chapter)] = byCh[chapterNo(e.chapter)] || []).push(j); });
    C.forEach(function (c) {
      var w = imp(c.name) / 100;
      (c.judgments || []).forEach(function (jd) {
        var jn = chapterNo(jd.chapter), jb = bigrams(jd.text), jk = Object.keys(jb), best = -1, bv = 0;
        laterJ.push({ ch: jn, b: jb });
        (byCh[jn] || []).forEach(function (j) { var hit = 0, sk = Object.keys(sumBi[j]); sk.forEach(function (b) { if (jb[b]) hit++; }); var v = hit / Math.max(4, Math.min(sk.length, jk.length)); if (v > bv) { bv = v; best = j; } });
        if (best >= 0 && bv >= 0.3) P.judg[best] += w * (jd.kind === '转折' ? 1.2 : 1);
      });
    });
    var arcBi = {}; C.forEach(function (c) { if (c && c.name) arcBi[c.name] = (c.arc || []).map(function (a) { return bigrams(a && a.text); }); });
    var syn = bigrams(G.synopsis);
    for (i = 0; i < n; i++) {
      var e = E[i], ps = (e.characters || []).filter(function (nm) { return byName[nm]; });
      var dist = Object.keys(bigrams(e.title)).filter(function (b) { return !nameBi[b] && tdf[b] <= 2 && (sdf[b] || 0) <= Math.max(6, n * 0.01); });
      if (dist.length) {
        var hit = function (set) { for (var q = 0; q < dist.length; q++) if (set[dist[q]]) return 1; return 0; };
        ps.forEach(function (nm) { var w = imp(nm) / 100, best = 0; arcBi[nm].forEach(function (a) { best = Math.max(best, hit(a)); }); P.arc[i] += 2 * w * w * best; });
        P.syn[i] = 1.5 * hit(syn);
        var later = {}, lr = 0; dist.forEach(function (b) { (post[b] || []).forEach(function (j) { if (j > i && chOf[j] !== chOf[i]) later[j] = 1; }); });
        lineBi.forEach(function (lb) { lr += hit(lb); });
        laterJ.forEach(function (jd) { if (jd.ch != null && chOf[i] != null && jd.ch > chOf[i] && hit(jd.b)) lr += 0.5; });
        P.call[i] = Math.min(2.5, 0.3 * Object.keys(later).length + 0.5 * lr);
      }
      var ws = ps.map(imp).sort(function (a, b) { return b - a; });
      P.cast[i] = ((ws[0] || 0) + 0.5 * (ws[1] || 0) + 0.25 * (ws[2] || 0)) / 100;
      var mp = 0;
      for (var a = 0; a < ps.length; a++) for (var b2 = a + 1; b2 < ps.length; b2++) {
        var ca = byName[ps[a]].camp, cb = byName[ps[b2]].camp;
        if (ca && cb && ca !== cb && ca !== '散星' && cb !== '散星') mp = Math.max(mp, Math.min(imp(ps[a]), imp(ps[b2])) / 100);
      }
      P.camp[i] = 2 * mp * mp;
      ps.forEach(function (nm) {
        var L = evOf[nm], w = imp(nm) / 100, end, q; if (!L || L.length < 3 || w < 0.3) return;
        end = L[L.length - 1];
        for (q = L.length - 1; q >= Math.max(0, L.length - 3); q--) if (SAL_DEATH.test((E[L[q]].title || '') + (E[L[q]].summary || ''))) { end = L[q]; break; }
        if (end === i && end < n * 0.97) P.exit[i] += 6 * w * w * w * w * Math.min(1, L.length / 10);
      });
      P.exit[i] = Math.min(6, P.exit[i]);
      var hd = bigrams(String(e.chapter || '').replace(/^第\s*[0-9零〇一二两三四五六七八九十百千]+\s*[回章节]/, '')), tb = Object.keys(bigrams(e.title)).filter(function (b) { return !nameBi[b]; });
      if (tb.length) { var h = 0; tb.forEach(function (b) { if (hd[b]) h++; }); P.head[i] = Math.min(1, h / Math.min(3, tb.length)) * 0.8; }
      if (i === 0 || i === n - 1) P.head[i] += 2.5;
      P.dec[i] = SAL_DEC.test(e.title || '') ? 1 : SAL_DEC.test(e.summary || '') ? 0.4 : 0;
    }
    (G.tasks || []).forEach(function (t) { k = t && idOf[String(t.outcomeEventId)]; if (k != null) P.mech[k] += 0.8; });
    (G.characterStates || []).forEach(function (t) { k = t && idOf[String(t.eventId)]; if (k != null) P.mech[k] += 0.5; });
    (G.clues || []).forEach(function (t) { if (t) [t.seedEventId, t.payoffEventId].forEach(function (x) { k = idOf[String(x)]; if (k != null) P.mech[k] += 0.4; }); });
    (G.causeEdges || []).forEach(function (x, i) { if (!x || x.resolved === false) return; k = idOf[String(x.sourceId)]; if (k != null) P.cause[k] += 0.3; k = idOf[String(x.targetId)]; if (k != null) P.cause[k] += 0.4; });
    lines.forEach(function (l, li) {
      var ix = lineIdx[li], w = lw(l), len = Math.min(1, ix.length / 6); if (!ix.length) return;
      P.line[ix[ix.length - 1]] += w * len; P.line[ix[0]] += 0.5 * w * len;
      if (l.handoff_from) P.line[ix[0]] += 0.3;
      (l.evidenceQuotes || []).forEach(function (q) {
        q = String(q || '').replace(/[。！？，；、\s]+$/, ''); if (q.length < 6) return;
        ix.forEach(function (j) { var eq = String(E[j].quote || ''); if (eq && (eq.indexOf(q.slice(0, 8)) >= 0 || q.indexOf(eq.slice(0, 8)) >= 0)) P.evq[j] += 0.6; });
      });
    });
    var score = new Float64Array(n);
    for (i = 0; i < n; i++) F.forEach(function (f) { if (f !== 'peak') score[i] += SAL_W[f] * P[f][i]; });
    lines.forEach(function (l, li) {
      var ix = lineIdx[li], w = lw(l), lg = Math.log(1 + ix.length) / Math.LN2; if (ix.length < 2) return;
      var s = ix.slice().sort(function (a, b) { return score[b] - score[a]; });
      P.peak[s[0]] += 0.6 * w * lg; if (ix.length >= 12) P.peak[s[1]] += 0.3 * w * lg;
    });
    for (i = 0; i < n; i++) score[i] += SAL_W.peak * P.peak[i];
    var rank = []; for (i = 0; i < n; i++) rank.push(i);
    rank.sort(function (a, b) { return score[b] - score[a] || a - b; });
    var keyCount = n ? Math.max(1, Math.round(n * KEY_SHARE)) : 0, key = new Uint8Array(n);
    for (i = 0; i < keyCount; i++) key[rank[i]] = 1;
    var why = function (j) { return F.filter(function (f) { return SAL_W[f] * P[f][j] >= 0.8; }).sort(function (a, b) { return SAL_W[b] * P[b][j] - SAL_W[a] * P[a][j]; }); };
    var out = { n: n, score: score, rank: rank, key: key, keyCount: keyCount, share: KEY_SHARE, threshold: keyCount ? score[rank[keyCount - 1]] : Infinity,
      chapterOf: chOf, derivedLines: lineDer, why: why, version: 'salience/1' };
    if (salCache) salCache.set(G, out);
    return out;
  }
  function isKeyEvent(G, i) { var s = salience(G); return !!(s.key && s.key[i]); }
  function keyEvents(G, n, opts) {
    var s = salience(G), picked = [], seen = {}; n = n || 10; opts = opts || {};
    for (var r = 0; r < s.rank.length && picked.length < n; r++) {
      var i = s.rank[r], c = s.chapterOf[i];
      if (c != null && seen[c] && !opts.allowSameChapter) continue;
      picked.push(i); if (c != null) seen[c] = 1;
    }
    return picked;
  }

  var KEY_KINDS = { 转折: 3, 高燃: 3, 抉择: 2, 冲突: 2, 高潮: 3, 揭秘: 2 };
  function keyEvent(evIdx, G) {
    var best = null, bs = -Infinity, i, e, s, sal = G.events.length ? salience(G) : null;
    for (i = 0; i < evIdx.length; i++) {
      e = G.events[evIdx[i]]; if (!e) continue;
      s = sal ? sal.score[evIdx[i]] : (KEY_KINDS[e.kind] || 0) * 10 + ((e.characters || []).length);
      if (s > bs) { bs = s; best = e; }
    }
    return best;
  }
  function labelOf(t, G) {
    var title = String(t.title || '').trim(), lead = String(t.lead || '').trim();
    if (t.src === 'derived') return '';
    if (title && title.indexOf(' · ') < 0 && title !== lead) return title;
    var parts = title.split(/\s*·\s*/).filter(function (p) { return p && p !== lead && p.length >= 2; });
    return parts.length ? parts[0] : '';
  }
  function clip(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  var NARRATIVE_VERSION = 'castline/narrative-evidence/1';
  var BASIS_LABEL = { explicit: '原文明确', synthesis: '材料支持的归纳', inference: '事件推导', unverified: '未核验' };
  function narrativeBasis(v) {
    var code = String(v == null ? '' : v).toLowerCase();
    if (code === '原文明确' || code === '原文' || code === 'explicit') code = 'explicit';
    else if (code === '材料支持的归纳' || code === '归纳' || code === 'synthesis') code = 'synthesis';
    else if (code === '事件推导' || code === '推导' || code === 'inference' || code === 'inferred') code = 'inference';
    else code = 'unverified';
    return { code: code, label: BASIS_LABEL[code] };
  }
  function narrativeProjection(G) {
    var events = (G && G.events) || [], characters = (G && G.characters) || [], storylines = (G && G.storylines) || [];
    var byId = Object.create(null), byOrder = Object.create(null), byTitle = Object.create(null), byQuote = Object.create(null);
    var evidence = [], causalEdges = [], turningPoints = [], foreshadowPayoffs = [], unresolved = [];
    var eventIndexes = typeof Map === 'function' ? new Map() : null;
    function push(map, key, value) {
      if (key == null || key === '') return;
      var list = map[String(key)] || (map[String(key)] = []);
      if (list.indexOf(value) < 0) list.push(value);
    }
    function one(map, key) { var list = key == null ? [] : map[String(key)] || []; return list.length === 1 ? list[0] : null; }
    function stableId(e) { return e && (e.id != null ? e.id : e.entityId != null ? e.entityId : null); }
    function eventRefId(e) { var id = stableId(e); return id != null ? id : e && e.order != null ? e.order : null; }
    function at(e) { return eventIndexes ? eventIndexes.get(e) : events.indexOf(e); }
    function veto(x) { return x && (x.resolved === false || /^(unresolved|unresolved_or_conflicting|unknown|invalid)$/.test(x.referenceStatus || '')); }
    events.forEach(function (e, i) {
      if (!e) return;
      if (eventIndexes) eventIndexes.set(e, i);
      push(byId, e.id, e); push(byId, e.entityId, e);
      push(byOrder, e.order, e); push(byOrder, e.rawOrder, e);
      push(byTitle, e.title, e); push(byQuote, e.quote, e);
    });
    function lookup(value, typed) {
      if (value == null || value === '') return null;
      if (Object.prototype.hasOwnProperty.call(byId, String(value))) return one(byId, value);
      return typed ? null : one(byOrder, value);
    }
    function claims(items) {
      var found = null, conflict = false;
      items.forEach(function (item) { if (!item || (found && found !== item)) conflict = true; else found = item; });
      return conflict ? null : found;
    }
    function eventOf(ref) {
      if (!ref || typeof ref !== 'object') return lookup(ref, false);
      if (at(ref) >= 0) return ref;
      if (veto(ref)) return null;
      var items = [];
      ['targetId', 'eventId'].forEach(function (key) { if (ref[key] != null && ref[key] !== '') items.push(lookup(ref[key], true)); });
      if (ref.ref != null && ref.ref !== '') items.push(lookup(ref.ref, false));
      if (ref.order != null && ref.order !== '') items.push(one(byOrder, ref.order));
      return claims(items);
    }
    function endpoint(edge, side) {
      var items = [], declarations = [];
      (side === 'from' ? ['fromEventId', 'sourceId', 'declaredSourceId', 'from'] : ['toEventId', 'targetId', 'declaredTargetId', 'to']).forEach(function (key) {
        if (edge[key] == null || edge[key] === '') return;
        declarations.push(String(edge[key])); items.push(lookup(edge[key], key !== side));
      });
      ['Title', 'Quote'].forEach(function (suffix) {
        var value = edge[side + suffix];
        if (value == null || value === '') return;
        declarations.push(String(value)); items.push(one(suffix === 'Title' ? byTitle : byQuote, value));
      });
      return { event: claims(items), ref: declarations.join(' / ') || null };
    }
    function copyBasis(x) { var b = narrativeBasis(x && typeof x === 'object' ? x.basisCode != null ? x.basisCode : x.basis : null); return { basis: b.label, basisCode: b.code }; }
    function refText(x) {
      if (!x || typeof x !== 'object') return x;
      if (at(x) >= 0) return eventRefId(x);
      return x.ref != null ? x.ref : x.targetId != null ? x.targetId : x.eventId != null ? x.eventId : x.order != null ? x.order : null;
    }
    function addUnresolved(ownerType, ownerId, kind, sourceRef, targetRef, reason) {
      unresolved.push({ ownerType: ownerType, ownerId: ownerId, kind: kind, ref: refText(targetRef), sourceRef: refText(sourceRef), targetRef: refText(targetRef), reason: reason || 'unresolved_endpoint' });
    }
    function evidenceOf(ownerType, ownerId, list) {
      (Array.isArray(list) ? list : []).forEach(function (item) {
        if (!item || typeof item !== 'object') return;
        var out = copyBasis(item); out.ownerType = ownerType; out.ownerId = ownerId;
        ['id', 'chapter', 'quote', 'text', 'sourceId', 'textHash', 'start', 'end', 'status', 'verified', 'sourceRefs'].forEach(function (k) { if (item[k] != null) out[k] = item[k]; });
        evidence.push(out);
      });
    }
    function addEdge(s, t, kind, link, ownerType, ownerId, sourceRef, targetRef) {
      if (!s || !t || s === t || veto(link)) {
        addUnresolved(ownerType, ownerId, kind, sourceRef, targetRef, veto(link) ? 'declared_unresolved' : s && s === t ? 'self_reference' : 'unresolved_or_conflicting'); return;
      }
      var edge = copyBasis(link);
      edge.sourceId = eventRefId(s); edge.targetId = eventRefId(t);
      edge.source = at(s); edge.target = at(t); edge.kind = kind;
      edge.ownerType = ownerType; edge.ownerId = ownerId;
      edge.evidence = link && Array.isArray(link.evidence) ? link.evidence.slice() : [];
      edge.sourceRefs = link && Array.isArray(link.sourceRefs) ? link.sourceRefs.slice() : [];
      ['description', 'summary', 'quote', 'quoteReview', 'provenance', 'claimVerified', 'semanticStatus'].forEach(function (key) { if (link && link[key] != null) edge[key] = link[key]; });
      causalEdges.push(edge);
    }
    function addPair(f, p, link, ownerType, ownerId, sourceRef, targetRef, pending) {
      var pair = copyBasis(link), valid = !!(f && p && f !== p && at(f) < at(p) && !veto(link));
      pair.ownerType = ownerType; pair.ownerId = ownerId;
      pair.foreshadowId = f ? eventRefId(f) : refText(sourceRef); pair.payoffId = p ? eventRefId(p) : refText(targetRef);
      pair.source = f ? at(f) : null; pair.target = p ? at(p) : null;
      pair.resolved = valid; pair.pending = !!(pending && f && !p && !veto(link));
      pair.name = link && link.name || ''; pair.summary = link && link.summary || '';
      pair.evidence = link && Array.isArray(link.evidence) ? link.evidence.slice() : [];
      if (link && typeof link === 'object') {
        ['quote', 'seedQuote', 'payoffQuote', 'provenance', 'claimVerified', 'semanticStatus', 'clueType'].forEach(function (key) { if (link[key] != null) pair[key] = link[key]; });
        if (link.status != null) pair.declaredStatus = link.status;
      }
      foreshadowPayoffs.push(pair);
      if (!valid && !pair.pending) addUnresolved(ownerType, ownerId, 'foreshadowPayoff', sourceRef, targetRef, veto(link) ? 'declared_unresolved' : f && p ? 'invalid_payoff_order' : 'unresolved_or_conflicting');
    }
    events.forEach(function (e) {
      if (!e) return;
      var id = eventRefId(e);
      evidenceOf('event', id, e.evidence);
      (Array.isArray(e.causes) ? e.causes : []).forEach(function (x) { addEdge(eventOf(x), e, 'cause', x, 'event', id, x, e); });
      (Array.isArray(e.consequences) ? e.consequences : []).forEach(function (x) { addEdge(e, eventOf(x), 'consequence', x, 'event', id, e, x); });
      (Array.isArray(e.foreshadow_of) ? e.foreshadow_of : []).forEach(function (x) { addPair(e, eventOf(x), x, 'event', id, e, x, false); });
      (Array.isArray(e.payoff_of) ? e.payoff_of : []).forEach(function (x) { addPair(eventOf(x), e, x, 'event', id, x, e, false); });
    });
    (G.causeEdges || []).forEach(function (x, i) {
      if (!x || typeof x !== 'object') return;
      var from = endpoint(x, 'from'), to = endpoint(x, 'to');
      addEdge(from.event, to.event, 'cause', x, 'causeEdge', x.id != null ? x.id : x.entityId, from.ref, to.ref);
    });
    function addTurning(ownerType, ownerId, list) {
      (Array.isArray(list) ? list : []).forEach(function (x) {
        var e = eventOf(x), item = copyBasis(x);
        item.ownerType = ownerType; item.ownerId = ownerId; item.eventId = e ? eventRefId(e) : null;
        item.eventIndex = e ? at(e) : null;
        item.order = x && typeof x === 'object' && x.order != null ? x.order : null;
        item.evidence = x && Array.isArray(x.evidence) ? x.evidence.slice() : []; item.resolved = !!e;
        ['name', 'text', 'summary', 'description', 'quote', 'quoteReview', 'sourceRefs', 'claimVerified', 'semanticStatus', 'provenance'].forEach(function (key) { if (x && typeof x === 'object' && x[key] != null) item[key] = x[key]; });
        turningPoints.push(item); if (!e) addUnresolved(ownerType, ownerId, 'turningPoint', null, x);
      });
    }
    characters.forEach(function (c) { if (c) addTurning('character', c.id != null ? c.id : c.entityId || c.name, c.turning_points); });
    storylines.forEach(function (line) {
      if (!line) return;
      var id = line.id != null ? line.id : line.entityId || line.name; addTurning('storyline', id, line.turning_points);
      (line.foreshadow_payoffs || []).forEach(function (x) {
        if (x) addPair(lookup(x.foreshadowId, true), lookup(x.payoffId, true), x, 'storyline', id, x.foreshadowId, x.payoffId, false);
      });
    });
    (G.clues || []).forEach(function (x, i) {
      if (!x || typeof x !== 'object') return;
      var hasPayoff = x.payoffEventId != null && x.payoffEventId !== '';
      addPair(lookup(x.seedEventId, true), lookup(x.payoffEventId, true), x, 'clue', x.id != null ? x.id : x.entityId,
        x.seedEventId, x.payoffEventId, !hasPayoff && x.status !== 'resolved');
    });
    var foreshadowLifecycles = foreshadowPayoffs.map(function (pair, i) {
      var seed = pair.source != null ? events[pair.source] : null;
      var payoff = pair.resolved && pair.target != null ? events[pair.target] : null;
      var record = copyBasis(pair);
      record.key = pair.ownerType + ':' + (pair.ownerId != null ? pair.ownerId : 'declaration:' + i);
      record.ownerType = pair.ownerType; record.ownerId = pair.ownerId != null ? String(pair.ownerId) : null;
      record.name = pair.name || ''; record.summary = pair.summary || '';
      record.stage = pair.resolved ? 'resolved' : pair.pending ? 'pending' : 'broken';
      record.seedIndex = pair.source;
      record.seedId = pair.foreshadowId != null ? String(pair.foreshadowId) : null;
      record.seedTitle = seed ? seed.title || seed.summary || null : null;
      record.seedChapter = seed ? seed.chapter || null : null;
      record.payoffIndex = payoff ? pair.target : null;
      record.payoffId = payoff && pair.payoffId != null ? String(pair.payoffId) : null;
      record.payoffTitle = payoff ? payoff.title || payoff.summary || null : null;
      record.payoffChapter = payoff ? payoff.chapter || null : null;
      record.declaredStatus = pair.declaredStatus != null ? pair.declaredStatus : null;
      record.evidence = Array.isArray(pair.evidence) ? pair.evidence.slice() : [];
      if (pair.quote != null) record.quote = pair.quote;
      if (pair.seedQuote != null) record.seedQuote = pair.seedQuote;
      if (pair.payoffQuote != null) record.payoffQuote = pair.payoffQuote;
      if (pair.clueType != null) record.clueType = pair.clueType;
      if (pair.provenance != null) record.provenance = pair.provenance;
      if (pair.claimVerified != null) record.claimVerified = pair.claimVerified;
      if (pair.semanticStatus != null) record.semanticStatus = pair.semanticStatus;
      return record;
    });
    var identities = Object.create(null);
    foreshadowLifecycles.forEach(function (record) {
      if (record.ownerId == null) return;
      var id = record.ownerType + ':' + record.ownerId;
      identities[id] = (identities[id] || 0) + 1;
    });
    var conflictReported = Object.create(null);
    foreshadowLifecycles.forEach(function (record) {
      if (record.ownerId == null) return;
      var id = record.ownerType + ':' + record.ownerId;
      if (identities[id] <= 1) return;
      record.stage = 'conflicted'; record.conflicted = true;
      record.payoffIndex = null; record.payoffId = null; record.payoffTitle = null; record.payoffChapter = null;
      if (!conflictReported[id]) {
        conflictReported[id] = true;
        unresolved.push({ ownerType: record.ownerType, ownerId: record.ownerId, kind: 'foreshadowLifecycle',
          ref: record.seedId, sourceRef: record.seedId, targetRef: record.payoffId, reason: 'duplicate_identity' });
      }
    });
    var foreshadowStats = { total: foreshadowLifecycles.length, resolved: 0, pending: 0, broken: 0, conflicted: 0 };
    foreshadowLifecycles.forEach(function (record) { foreshadowStats[record.stage]++; });
    var architectureNodes = events.map(function (e, i) {
      return { index: i, id: eventRefId(e), order: e && e.order != null ? e.order : null,
        title: e && (e.title || e.summary) || null, chapter: e && e.chapter || null, kind: e && e.kind || null,
        in: 0, out: 0, linked: false, evidence: !!(e && Array.isArray(e.evidence) && e.evidence.length) };
    });
    var pairs = Object.create(null);
    causalEdges.forEach(function (edge) {
      var key = edge.source + '>' + edge.target;
      if (!pairs[key]) {
        pairs[key] = true;
        architectureNodes[edge.source].out++; architectureNodes[edge.target].in++;
      }
      architectureNodes[edge.source].linked = true; architectureNodes[edge.target].linked = true;
    });
    var architecture = { version: 'castline/narrative-architecture/3', nodes: architectureNodes, edges: causalEdges,
      roots: architectureNodes.filter(function (n) { return n.linked && n.in === 0; }).map(function (n) { return n.index; }),
      leaves: architectureNodes.filter(function (n) { return n.linked && n.out === 0; }).map(function (n) { return n.index; }),
      unresolved: unresolved.slice(), stats: { events: events.length, linkedEvents: architectureNodes.filter(function (n) { return n.linked; }).length,
        causalEdges: causalEdges.length, causalPairs: Object.keys(pairs).length, foreshadowEdges: foreshadowPayoffs.filter(function (x) { return x.resolved; }).length,
        foreshadow: foreshadowStats,
        turningPoints: turningPoints.length, unresolved: unresolved.length, explicitEvidence: evidence.filter(function (x) { return x.ownerType === 'event'; }).length } };
    var projection = { version: (G.meta && G.meta.narrativeEvidence && G.meta.narrativeEvidence.version) || NARRATIVE_VERSION,
      evidence: evidence, causalEdges: causalEdges, turningPoints: turningPoints, foreshadowPayoffs: foreshadowPayoffs,
      foreshadowLifecycles: foreshadowLifecycles,
      unresolved: unresolved, coverage: (G.meta && G.meta.coverage && G.meta.coverage.narrative) || {}, architecture: architecture };
    projection.characterReading = characterStateReading(G, projection);
    return projection;
  }

  function characterStateReading(G, narrative) {
    function arr(v) { return Array.isArray(v) ? v : []; }
    function text(v) { return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' ? String(v).trim() : ''; }
    function present(v) { return v != null && v !== ''; }
    function clone(v) { return v == null ? v : JSON.parse(JSON.stringify(v)); }
    function add(map, key, value) {
      if (!present(key)) return;
      var list = map[String(key)] || (map[String(key)] = []);
      if (list.indexOf(value) < 0) list.push(value);
    }
    function one(map, key) { var list = present(key) ? map[String(key)] || [] : []; return list.length === 1 ? list[0] : null; }
    function consistent(items) { return items.length && items[0] != null && items.every(function (v) { return v === items[0]; }) ? items[0] : null; }
    function unresolvedStatus(v) { return /^(unresolved|unresolved_or_conflicting|ambiguous|unknown|invalid)$/.test(text(v)); }
    function veto(x) { return x && (x.resolved === false || unresolvedStatus(x.referenceStatus)); }
    function identityVeto(x) { return x && unresolvedStatus(x.identityStatus); }
    var provenanceFields = ['quote', 'quoteReview', 'sourceRefs', 'sourceRef', 'quoteRef', 'evidence', 'evidenceRefs', 'evidenceRef',
      'verified', 'quoteVerified', 'claimVerified', 'semanticStatus', 'provenance', 'derived', 'inferred'];
    var events = arr(G.events), characters = arr(G.characters), byEvent = Object.create(null), byOrder = Object.create(null);
    var byChar = Object.create(null), byName = Object.create(null), states = [], knowledge = [], transitions = [];
    events.forEach(function (e, i) { if (e) { add(byEvent, e.id, i); add(byEvent, e.entityId, i); add(byOrder, e.order, i); add(byOrder, e.rawOrder, i); } });
    characters.forEach(function (c, i) { if (c) { add(byChar, c.id, i); add(byChar, c.entityId, i); add(byName, c.name, i); arr(c.aliases).forEach(function (name) { add(byName, name, i); }); } });
    function eventIndex(raw) {
      if (veto(raw)) return null;
      var claims = [];
      ['eventId', 'eventRef'].forEach(function (key) { if (present(raw[key])) claims.push(one(byEvent, raw[key])); });
      if (present(raw.order)) claims.push(one(byOrder, raw.order));
      return consistent(claims);
    }
    function characterIdentity(raw, inherited) {
      var claims = [];
      if (present(raw.characterId)) claims.push(one(byChar, raw.characterId));
      if (present(raw.character)) claims.push(one(byName, raw.character));
      if (inherited != null) claims.push(inherited);
      var at = consistent(claims), c = at == null ? null : characters[at], blocked = identityVeto(raw) || identityVeto(c);
      var identity = { characterIndex: blocked ? null : at, characterId: c ? text(c.id != null ? c.id : c.entityId) || null : text(raw.characterId) || null,
        character: c ? text(c.name) : text(raw.character) || text(raw.characterId), characterResolved: at != null && !blocked };
      if (identityVeto(c)) identity.identityStatus = text(c.identityStatus);
      return identity;
    }
    function row(raw, key, inherited) {
      var identity = characterIdentity(raw, inherited), ei = eventIndex(raw), b = narrativeBasis(raw.basisCode != null ? raw.basisCode : raw.basis);
      var result = Object.assign(identity, { key: key, id: text(raw.id) || null, eventId: text(raw.eventId != null ? raw.eventId : raw.eventRef) || null,
        eventIndex: ei, eventResolved: ei != null, resolved: ei != null && identity.characterResolved,
        chapter: text(raw.chapter) || (ei != null ? text(events[ei].chapter) : ''), basisCode: b.code, basis: b.label });
      if (raw.identityStatus != null && !identityVeto(identity)) result.identityStatus = text(raw.identityStatus);
      if (raw.referenceStatus != null) result.referenceStatus = text(raw.referenceStatus);
      provenanceFields.forEach(function (field) { if (raw[field] != null) result[field] = clone(raw[field]); });
      return result;
    }
    function nestedSource(raw, source) {
      var merged = Object.assign({}, raw, source);
      ['characterId', 'character', 'eventId', 'eventRef', 'order'].forEach(function (field) {
        if (!present(merged[field]) && present(raw[field])) merged[field] = raw[field];
      });
      if (veto(raw)) merged.resolved = false;
      if (unresolvedStatus(raw.referenceStatus)) merged.referenceStatus = raw.referenceStatus;
      if (identityVeto(raw)) merged.identityStatus = raw.identityStatus;
      provenanceFields.concat(['basis', 'basisCode']).forEach(function (field) {
        if (!Object.prototype.hasOwnProperty.call(source, field)) delete merged[field];
      });
      return merged;
    }
    function knowledgeRows(raw, owner, inherited) {
      [['knowledge', null], ['knowledgeGaps', 'unknown']].forEach(function (field) {
        arr(raw[field[0]]).forEach(function (entry, i) {
          var source = typeof entry === 'string' ? { text: entry } : entry;
          if (!source || typeof source !== 'object') return;
          var content = text(source.text || source.value || source.summary || source.fact);
          if (!content) return;
          var merged = nestedSource(raw, source);
          var item = row(merged, owner + ':' + field[0] + ':' + i, inherited);
          item.text = content; item.status = text(source.status) || field[1] || 'unspecified';
          item.isGap = field[0] === 'knowledgeGaps' || /^(unknown|unaware|not_known|does_not_know|未知|不知)$/.test(item.status);
          item.ownerKey = owner;
          knowledge.push(item);
        });
      });
    }
    function transition(raw, owner, inherited) {
      var inner = raw && raw.transition;
      var source = (inner && typeof inner === 'object'
        && (text(inner.before) || text(inner.after))) ? inner : raw;
      if (!source || typeof source !== 'object' || !text(source.before) || !text(source.after)) return;
      var merged = nestedSource(raw, source);
      var item = row(merged, owner + ':transition', inherited);
      item.before = text(source.before); item.after = text(source.after); item.description = text(source.description || source.summary); item.ownerKey = owner;
      if (source.attribute) item.attribute = text(source.attribute);
      transitions.push(item);
    }
    function transitionExplicit(source, ownerKey, inherited) {
      if (!source || typeof source !== 'object' || !text(source.before) || !text(source.after)) return;
      var item = row(source, ownerKey, inherited);
      item.before = text(source.before); item.after = text(source.after); item.description = text(source.description || source.summary); item.ownerKey = ownerKey;
      transitions.push(item);
    }
    arr(G.characterStates).forEach(function (raw, i) {
      if (!raw || typeof raw !== 'object') return;
      var item = row(raw, 'state:' + i);
      item.index = i; item.summary = text(raw.summary); item.attributes = clone(arr(raw.attributes).filter(function (x) { return x && typeof x === 'object'; }));
      states.push(item); knowledgeRows(raw, item.key); transition(raw, item.key);
    });
    characters.forEach(function (c, i) { if (c) knowledgeRows(c, 'character:' + i, i); });
    arr(G.stateTransitions).concat(arr(G.characterTransitions)).forEach(function (item, i) { transitionExplicit(item, 'transition:' + i); });
    characters.forEach(function (c, i) {
      if (!c) return;
      arr(c.stateTransitions).concat(arr(c.state_transitions)).concat(arr(c.transitions)).forEach(function (item, j) {
        if (!item || typeof item !== 'object') return;
        var source = nestedSource(c, item);
        if (!present(source.characterId) && present(c.id != null ? c.id : c.entityId)) source.characterId = c.id != null ? c.id : c.entityId;
        if (!present(source.character)) source.character = c.name;
        transitionExplicit(source, 'character-transition:' + i + ':' + j, i);
      });
    });
    var turningPoints = arr(narrative.turningPoints).map(function (item, i) {
      var out = clone(item), matches = [], by = item.ownerType === 'character' ? characters : arr(G.storylines);
      by.forEach(function (entity, j) { if (entity && String(entity.id != null ? entity.id : entity.entityId || entity.name) === String(item.ownerId)) matches.push(j); });
      var owner = matches.length === 1 ? by[matches[0]] : null;
      out.key = 'turn:' + i; out.ownerName = owner ? text(owner.name || owner.title) : text(item.ownerId);
      out.character = item.ownerType === 'character' ? out.ownerName : '';
      out.characterId = item.ownerType === 'character' ? text(item.ownerId) : null;
      out.ownerResolved = !!owner; out.resolved = !!item.resolved && !!owner;
      out.summary = text(item.summary || item.description || item.text || item.name);
      return out;
    });
    return { version: 'castline/character-state-reading/1', states: states, transitions: transitions, knowledge: knowledge,
      knowledgeGaps: knowledge.filter(function (x) { return x.isGap; }), turningPoints: turningPoints,
      stats: { states: states.length, linkedStates: states.filter(function (x) { return x.resolved; }).length,
        transitions: transitions.length, knowledge: knowledge.length, knowledgeGaps: knowledge.filter(function (x) { return x.isGap; }).length, turningPoints: turningPoints.length } };
  }

  function build(G, T, opts) {
    opts = opts || {};
    var out = { ok: false, nCh: 0, chapters: [], mains: [], handoffs: [], lines: [], lanes: 0, total: 0,
      chapterCast: [], chapterEvents: [], cooccur: [], cooccurDerived: false, groupings: [], stats: {}, narrative: null };
    if (!G || !G.events || !G.characters) return out;
    out.narrative = narrativeProjection(G);
    var chs = (T && T.chapters && T.chapters.length) ? T.chapters.map(function (c) { return typeof c === 'string' ? c : (c && (c.name || c.label)) || ''; }) : [];
    if (!chs.length) G.events.forEach(function (e) { if (chs.indexOf(e.chapter) < 0) chs.push(e.chapter); });
    var aliases = chapterAliases(chs), chIdx = aliases.byName;
    chs = aliases.names;
    out.nCh = chs.length;
    out.axis = axisOf(chs);
    out.chapters = chs.map(function (c, i) {
      var no = out.axis.raw[i], sp = SPECIAL.test(String(c || '')), show = out.axis.mode === 'seq' ? i + 1 : no;
      return { idx: i, name: c, no: show, raw: no, short: chapterShort(c), special: sp };
    });
    delete out.axis.raw;
    var evCh = G.events.map(function (e) { var k = chIdx[e.chapter]; return k == null ? 0 : k; });
    out.chapterEvents = chs.map(function () { return []; });
    out.chapterCast = chs.map(function () { return []; });
    G.events.forEach(function (e, i) { out.chapterEvents[evCh[i]].push(i); });
    out.chapterCast = out.chapterEvents.map(function (list) { var names = []; list.forEach(function (i) { names = names.concat(G.events[i].characters || []); }); return uniq(names); });
    out.density = out.chapterEvents.map(function (list) { return list.length; });
    var sal = salience(G);
    out.keyChapters = out.chapterEvents.map(function (list, c) { return list.some(function (i) { return sal.key[i]; }) ? c : -1; }).filter(function (c) { return c >= 0; });
    out.keyCount = sal.keyCount; out.derivedLines = sal.derivedLines;

    var threads = (T && T.ok !== false && T.threads) ? T.threads : [];
    var byId = {}; threads.forEach(function (t) { if (t && t.id != null) byId[t.id] = t; });
    function spanOf(t) {
      var ev = (t.events || []).filter(function (i) { return G.events[i]; });
      var c0 = Infinity, c1 = -Infinity;
      ev.forEach(function (i) { var c = evCh[i]; if (c < c0) c0 = c; if (c > c1) c1 = c; });
      if (t.span && isFinite(t.span.from) && isFinite(t.span.to)) {
        var from = aliases.oldToNew[t.span.from], to = aliases.oldToNew[t.span.to];
        if (from != null) c0 = Math.min(c0, from);
        if (to != null) c1 = Math.max(c1, to);
      }
      if (!isFinite(c0)) { c0 = 0; c1 = 0; }
      return { c0: Math.max(0, c0), c1: Math.min(out.nCh - 1, c1), ev: ev.sort(function (a, b) { return a - b; }) };
    }
    function castOf(t, ev) {
      var list = [];
      if (Array.isArray(t.cast)) list = t.cast.slice().sort(function (a, b) { return (b.n || 0) - (a.n || 0) || (b.w || 0) - (a.w || 0); }).map(function (c) { return c && c.name; });
      if (!list.length) { var cnt = {}; ev.forEach(function (i) { (G.events[i].characters || []).forEach(function (n) { cnt[n] = (cnt[n] || 0) + 1; }); }); list = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }); }
      return uniq(list);
    }
    var mains = threads.filter(function (t) { return t.kind === 'main'; }).map(function (t) {
      var s = spanOf(t);
      return { id: t.id, raw: t, title: t.title || '', lead: t.lead || '', c0: s.c0, c1: s.c1, events: s.ev, n: s.ev.length,
        objective: t.objective || 'unknown', autoSegment: t.autoSegment === true, objectiveText: t.objectiveText || '',
        taskIds: (t.taskIds || []).slice(), taskGoalCount: t.taskGoalCount || 0,
        sourceId: t.sourceId, topologyStatus: t.topologyStatus, anchored: !!t.anchored, pendingReason: t.pendingReason || '',
        declaredParent: t.declaredParent, declaredAttach: t.declaredAttach, parentBasis: t.parentBasis, parentRelation: t.parentRelation,
        cast: castOf(t, s.ev), provenance: storylineProvenance(G, t), derived: storylineProvenance(G, t) === 'derived', resolved: !!t.resolved, suspended: !!t.suspended };
    }).sort(function (a, b) { return a.c0 - b.c0 || a.c1 - b.c1; });
    var usedLabels = {};
    mains.forEach(function (m, i) {
      m.gen = i % 6; m.index = i;
      var lb = labelOf(m.raw, G), ke = keyEvent(m.events, G);
      if (!lb || usedLabels[lb]) lb = ke ? ke.title : (m.lead || ('第' + (i + 1) + '段'));
      usedLabels[lb] = 1; m.fullLabel = lb;
      m.label = clip(lb.replace(/^全书阶段\s*\d+\s*[：:]\s*/, ''), 8); m.keyEvent = ke ? ke.title : '';
      delete m.raw;
    });
    var mainOf = {};
    function rootMain(t) {
      var seen = {}, cur = t;
      while (cur && !seen[cur.id]) { seen[cur.id] = 1; if (cur.kind === 'main') return cur.id; cur = byId[cur.parent]; }
      return null;
    }
    mains.forEach(function (m) { mainOf[m.id] = m; });
    function mainAt(c) { for (var i = 0; i < mains.length; i++) if (c >= mains[i].c0 && c <= mains[i].c1) return mains[i]; var best = null, bd = Infinity; mains.forEach(function (m) { var d = Math.min(Math.abs(c - m.c0), Math.abs(c - m.c1)); if (d < bd) { bd = d; best = m; } }); return best; }

    var lines = threads.filter(function (t) { return t.kind !== 'main'; }).map(function (t) {
      var s = spanOf(t), mid = rootMain(t), m = mid && mainOf[mid] ? mainOf[mid] : mainAt(s.c0);
      return { id: t.id, kind: t.kind === 'twig' ? 'twig' : 'branch', title: t.title || '', lead: t.lead || '', parent: t.parent || null,
        objective: t.objective || 'unknown', autoSegment: t.autoSegment === true, objectiveText: t.objectiveText || '',
        taskIds: (t.taskIds || []).slice(), taskGoalCount: t.taskGoalCount || 0,
        sourceId: t.sourceId, topologyStatus: t.topologyStatus, anchored: !!t.anchored, pendingReason: t.pendingReason || '',
        declaredParent: t.declaredParent, declaredAttach: t.declaredAttach, parentBasis: t.parentBasis, parentRelation: t.parentRelation,
        c0: s.c0, c1: s.c1, events: s.ev, n: s.ev.length, cast: castOf(t, s.ev), mainId: m ? m.id : null, gen: m ? m.gen : 5,
        provenance: storylineProvenance(G, t), derived: storylineProvenance(G, t) === 'derived', resolved: !!t.resolved, suspended: !!t.suspended, raw: t,
        attachC: isFinite(t.attach) && G.events[t.attach] ? evCh[t.attach] : s.c0 };
    });
    lines.forEach(function (l) { l.span = l.c1 - l.c0 + 1; l.score = l.n * Math.sqrt(l.span) * (l.kind === 'twig' ? 0.6 : 1); });
    var K = opts.named != null ? opts.named : 16, MAXL = opts.namedLanes != null ? opts.namedLanes : 7;
    (function () {
      var ends = [], picked = 0;
      lines.slice().sort(function (a, b) { return b.score - a.score || a.c0 - b.c0; }).forEach(function (l, r) {
        l.rank = r; l.named = false;
        if (picked >= K) return;
        var trial = ends.concat([[l.c0, l.c1]]).sort(function (x, y) { return x[0] - y[0]; }), lane = [];
        trial.forEach(function (iv) { for (var k = 0; k < lane.length; k++) if (lane[k] + 1 < iv[0]) { lane[k] = iv[1]; return; } lane.push(iv[1]); });
        if (lane.length > MAXL) return;
        ends.push([l.c0, l.c1]); l.named = true; picked++;
      });
    })();
    lines.forEach(function (l) {
      var lb = labelOf(l.raw, G), ke = keyEvent(l.events, G);
      if (!lb || usedLabels[lb]) lb = ke ? ke.title : lb || l.lead;
      if (l.named) usedLabels[lb] = 1;
      l.fullLabel = lb; l.label = clip(lb, 7); l.keyEvent = ke ? ke.title : ''; delete l.raw;
    });
    var laneEnd = [];
    function place(l) {
      for (var k = 0; k < laneEnd.length; k++) if (laneEnd[k] + 1 < l.c0) { laneEnd[k] = l.c1; return k; }
      laneEnd.push(l.c1); return laneEnd.length - 1;
    }
    lines.filter(function (l) { return l.named; }).sort(function (a, b) { return a.c0 - b.c0 || b.span - a.span; }).forEach(function (l) { l.lane = place(l); });
    var namedLanes = laneEnd.length;
    lines.filter(function (l) { return !l.named; }).sort(function (a, b) { return a.c0 - b.c0 || b.span - a.span; }).forEach(function (l) { l.lane = place(l); });
    out.lanes = laneEnd.length; out.namedLanes = namedLanes;
    out.mains = mains; out.lines = lines; out.total = mains.length + lines.length;

    var ho = (T && T.handoffs) || [];
    out.handoffs = ho.map(function (h) {
      var a = mainOf[h.from], b = mainOf[h.to]; if (!b) return null;
      var c = isFinite(h.at) && G.events[h.at] ? evCh[h.at] : b.c0;
      return { from: h.from, to: h.to, c: c, reason: String(h.reason || ''), kind: String(h.kind || ''), leadFrom: a ? a.lead : '', leadTo: b.lead, shared: h.shared || [] };
    }).filter(Boolean);

    out.relationsHonesty = relationHonesty(G);
    out.lineHonesty = (T && T.lineHonesty) || null;
    if (!(G.relations && G.relations.length)) {
      var pair = {};
      G.events.forEach(function (e) {
        var cs = (e.characters || []).slice().sort();
        for (var i = 0; i < cs.length; i++) for (var j = i + 1; j < cs.length; j++) { var k = cs[i] + '\u0000' + cs[j]; pair[k] = (pair[k] || 0) + 1; }
      });
      var all = Object.keys(pair).filter(function (k) { return pair[k] >= 2; }).map(function (k) { var p = k.split('\u0000'); return { a: p[0], b: p[1], n: pair[k] }; })
        .sort(function (x, y) { return y.n - x.n; });
      var per = {}, keep = [], cap = opts.cooccurCap || 320, PER = 4;
      all.forEach(function (p) { if (keep.length >= cap) return; if ((per[p.a] || 0) >= PER && (per[p.b] || 0) >= PER) return; per[p.a] = (per[p.a] || 0) + 1; per[p.b] = (per[p.b] || 0) + 1; keep.push(p); });
      out.cooccur = keep; out.cooccurDerived = true; out.cooccurAll = all.length;
    }

    out.groupings = groupingsOf(G, mains, evCh);
    out.stats = { mains: mains.length, branches: lines.filter(function (l) { return l.kind === 'branch'; }).length, twigs: lines.filter(function (l) { return l.kind === 'twig'; }).length,
      named: lines.filter(function (l) { return l.named; }).length, lanes: out.lanes, chapters: out.nCh, events: G.events.length, characters: G.characters.length };
    out.ok = true;
    return out;
  }

  var FIELD_LABEL = { faction: '势力', force: '势力', world: '世界', realm: '世界', team: '战队', squad: '战队', region: '地域', location: '地点', sect: '门派', school: '门派', org: '组织', organization: '组织', clan: '家族', family: '家族', nation: '国度', country: '国度', guild: '公会' };
  var SKIP = { name: 1, aliases: 1, role: 1, importance: 1, camp: 1, stance: 1, appearances: 1, identity: 1, brief: 1, traits: 1, attrs: 1, arc: 1, judgments: 1, profiled: 1, relations: 1, id: 1, entityId: 1, importanceKnown: 1, profile_complete: 1, sourceRefs: 1, provenance: 1, review: 1 };
  function groupingsOf(G, mains, evCh) {
    var cs = G.characters, out = [];
    function opt(key, label, valueOf, note) {
      var cnt = {}, n = 0;
      cs.forEach(function (c) { var v = valueOf(c); if (v) { cnt[v] = (cnt[v] || 0) + 1; n++; } });
      var names = Object.keys(cnt);
      if (names.length < 2 || n < cs.length * 0.4) return;
      out.push({ key: key, label: label, note: note || '', groups: names.sort(function (a, b) { return cnt[b] - cnt[a]; }).map(function (v) { return { name: v, count: cnt[v] }; }), covered: n });
    }
    opt('camp', '阵营', function (c) { return c.camp || ''; });
    Object.keys(cs[0] || {}).forEach(function (k) {
      if (SKIP[k] || !FIELD_LABEL[k]) return;
      opt('field:' + k, FIELD_LABEL[k], function (c) { var v = c[k]; return typeof v === 'string' ? v.trim() : ''; });
    });
    opt('stance', '立场', function (c) { return c.stance || ''; });
    opt('role', '身份', function (c) { return c.role || ''; });
    if (mains.length >= 2) {
      var phaseOf = {};
      cs.forEach(function (c) { phaseOf[c.name] = {}; });
      G.events.forEach(function (e, i) {
        var c = evCh[i], m = null;
        for (var k = 0; k < mains.length; k++) if (c >= mains[k].c0 && c <= mains[k].c1) { m = mains[k]; break; }
        if (!m) return;
        (e.characters || []).forEach(function (n) { if (phaseOf[n]) phaseOf[n][m.label] = (phaseOf[n][m.label] || 0) + 1; });
      });
      opt('phase', '主线阶段', function (c) { var p = phaseOf[c.name] || {}, best = '', bn = 0; Object.keys(p).forEach(function (k) { if (p[k] > bn) { bn = p[k]; best = k; } }); return best; }, '按出场最多的主线阶段');
    }
    return out;
  }

  var GAP = 0.07;
  function angleAt(slot, nCh) { var n = Math.max(1, nCh); return Math.PI / 2 - GAP / 2 - (slot / n) * (Math.PI * 2 - GAP); }

  g.CLSkyModel = { build: build, angleAt: angleAt, chapterNo: chapterNo, chapterShort: chapterShort, GAP: GAP, version: '1',
    chapterLabel: chapterLabel, chapterSpan: chapterSpan,
    salience: salience, isKeyEvent: isKeyEvent, keyEvents: keyEvents, KEY_SHARE: KEY_SHARE, storylineProvenance: storylineProvenance,
    relationHonesty: relationHonesty, compareRelations: compareRelations, relationPeople: relationPeople };
})(typeof window !== 'undefined' ? window : this);
