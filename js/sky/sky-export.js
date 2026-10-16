(function (g) {
  'use strict';
  var VERSION = 'castline/evidence-export/1';

  function arr(v) { return Array.isArray(v) ? v : []; }
  function clone(v) { return v == null ? v : JSON.parse(JSON.stringify(v)); }
  function str(v) { return v == null || v === '' ? null : String(v); }
  function text(v) { return v == null ? '' : String(v); }

  function basisCounts(items, extra) {
    var counts = { total: arr(items).length, explicit: 0, synthesis: 0, inference: 0, unverified: 0 };
    arr(items).forEach(function (item) {
      var code = item && item.basisCode;
      counts[Object.prototype.hasOwnProperty.call(counts, code) ? code : 'unverified']++;
    });
    if (extra) Object.keys(extra).forEach(function (k) { counts[k] = extra[k]; });
    return counts;
  }

  function relationClaims(graph, honesty) {
    var items = honesty && arr(honesty.items), byIndex = Object.create(null);
    items.forEach(function (item) { if (item && item.index != null) byIndex[item.index] = item; });
    return arr(graph && graph.relations).map(function (r, i) {
      var row = {
        index: i,
        id: r && r.id != null ? String(r.id) : r && r.entityId != null ? String(r.entityId) : null,
        a: text(r && r.a), b: text(r && r.b),
        kind: text(r && r.kind), line: str(r && r.line),
        strength: r && typeof r.strength === 'number' ? r.strength : null,
        desc: text(r && r.desc), hidden: text(r && r.hidden),
        status: byIndex[i] ? { evidence: byIndex[i].evidence, label: byIndex[i].label } : null
      };
      ['quote', 'quoteVerified', 'claimVerified', 'claimStatus', 'semanticStatus', 'provenance', 'basis', 'basisCode',
        'sourceRefs', 'evidenceRefs', 'quoteReview', 'verified'].forEach(function (key) {
        if (r && r[key] != null) row[key] = clone(r[key]);
      });
      return row;
    });
  }

  function storylineClaims(story, lineHonesty) {
    return {
      honesty: lineHonesty ? clone(lineHonesty) : null,
      threads: arr(story && story.threads).map(function (t) {
        var row = {
          id: t && t.id != null ? String(t.id) : null,
          kind: text(t && t.kind), title: text(t && t.title), lead: text(t && t.lead),
          objective: text(t && t.objective), objectiveText: text(t && t.objectiveText),
          objectiveReason: text(t && t.objectiveReason), autoSegment: !!(t && t.autoSegment),
          resolved: !!(t && t.resolved), suspended: !!(t && t.suspended),
          eventCount: arr(t && t.events).length
        };
        if (t && t.sourceId != null) row.sourceId = String(t.sourceId);
        return row;
      })
    };
  }

  function snapshot(opts) {
    opts = opts || {};
    var graph = opts.graph || null, model = opts.model || null, story = opts.story || null;
    var narrative = model && model.narrative || null;
    var reading = narrative && narrative.characterReading || null;
    var honesty = model && model.relationsHonesty || null;
    var lineHonesty = model && model.lineHonesty || null;
    var evidence = clone(narrative ? narrative.evidence : []);
    var causalEdges = clone(narrative ? narrative.causalEdges : []);
    var turningPoints = clone(narrative ? narrative.turningPoints : []);
    var foreshadowLifecycles = clone(narrative ? narrative.foreshadowLifecycles : []);
    var stageCounts = { resolved: 0, pending: 0, broken: 0, conflicted: 0 };
    arr(foreshadowLifecycles).forEach(function (record) {
      if (record && Object.prototype.hasOwnProperty.call(stageCounts, record.stage)) stageCounts[record.stage]++;
    });
    var states = clone(reading ? reading.states : []);
    var knowledge = clone(reading ? reading.knowledge : []);
    var knowledgeGaps = clone(reading ? reading.knowledgeGaps : []);
    var transitions = clone(reading ? reading.transitions : []);
    var storylines = storylineClaims(story, lineHonesty);
    var relations = relationClaims(graph, honesty);
    var stages = narrative && narrative.architecture && narrative.architecture.stats && narrative.architecture.stats.foreshadow || {};
    var counts = {
      claims: 0,
      evidence: basisCounts(evidence),
      causalEdges: basisCounts(causalEdges),
      turningPoints: basisCounts(turningPoints),
      foreshadowLifecycles: basisCounts(foreshadowLifecycles, {
        resolved: stageCounts.resolved, pending: stageCounts.pending, broken: stageCounts.broken,
        conflicted: stageCounts.conflicted, projectionTotal: stages.total == null ? null : stages.total
      }),
      characters: {
        states: basisCounts(states), knowledge: basisCounts(knowledge),
        knowledgeGaps: basisCounts(knowledgeGaps), transitions: basisCounts(transitions)
      },
      storylines: {
        total: lineHonesty ? lineHonesty.total : arr(storylines.threads).length,
        declared: lineHonesty && lineHonesty.declared != null ? lineHonesty.declared : null,
        mechanical: lineHonesty && lineHonesty.mechanical != null ? lineHonesty.mechanical : null,
        unknown: lineHonesty && lineHonesty.unknown != null ? lineHonesty.unknown : null,
        verdict: lineHonesty ? lineHonesty.verdict : null
      },
      relations: {
        total: honesty ? honesty.total : relations.length,
        anchored: honesty ? honesty.anchored : 0,
        inheritedPending: honesty ? honesty.inherited : relations.filter(function (r) { return r.status && r.status.evidence === 'inherited-pending'; }).length
      },
      unresolved: narrative ? arr(narrative.unresolved).length : 0
    };
    counts.claims = counts.evidence.total + counts.causalEdges.total + counts.turningPoints.total +
      counts.foreshadowLifecycles.total + counts.characters.states.total + counts.characters.knowledge.total +
      counts.characters.transitions.total + counts.storylines.total + counts.relations.total;
    return {
      schema: VERSION,
      generatedAt: opts.generatedAt != null ? String(opts.generatedAt) : new Date().toISOString(),
      work: {
        key: opts.workKey != null ? String(opts.workKey) : null,
        title: str(graph && graph.title),
        graphHash: opts.graphHash != null ? String(opts.graphHash) : null
      },
      projections: {
        narrative: narrative && narrative.version || null,
        characterReading: reading && reading.version || null,
        relationHonesty: honesty && honesty.version || null,
        lineHonesty: lineHonesty && lineHonesty.version || null
      },
      counts: counts,
      claims: {
        evidence: evidence,
        causalEdges: causalEdges,
        turningPoints: turningPoints,
        foreshadowLifecycles: foreshadowLifecycles,
        characters: { states: states, knowledge: knowledge, knowledgeGaps: knowledgeGaps, transitions: transitions },
        storylines: storylines,
        relations: relations,
        unresolved: clone(narrative ? narrative.unresolved : [])
      }
    };
  }

  function textOf(pkg) { return JSON.stringify(pkg, null, 2); }

  function slug(s) { return text(s).replace(/[\\/:*?"<>|\s]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'work'; }

  function fileNameOf(pkg) {
    var stamp = String(pkg.generatedAt || '').slice(0, 10).replace(/-/g, '') || 'export';
    return slug(pkg.work.title || pkg.work.key || 'work') + '-evidence-' + stamp + '.json';
  }

  function current() {
    var app = g.CLApp, graph = app && app.graph ? app.graph() : null;
    if (!graph) return null;
    var story = app.story ? app.story() : null;
    var sky = g.CLSky, model = sky && sky.model ? sky.model() : null;
    if (!model && g.CLSkyModel) model = g.CLSkyModel.build(graph, story);
    var hash = null;
    if (g.CLStory && typeof g.CLStory.fingerprint === 'function') hash = g.CLStory.fingerprint(graph);
    else if (graph.meta && (graph.meta.graph_hash || graph.meta.hash)) hash = graph.meta.graph_hash || graph.meta.hash;
    return { graph: graph, model: model, story: story,
      workKey: app.key ? app.key() : graph.meta && graph.meta.graph_key != null ? graph.meta.graph_key : null,
      graphHash: hash };
  }

  function download(opts) {
    var c = opts && opts.graph ? opts : current();
    if (!c) return null;
    var pkg = snapshot(c), body = textOf(pkg), name = fileNameOf(pkg);
    var doc = g.document, blob = typeof Blob === 'function' ? new Blob([body], { type: 'application/json;charset=utf-8' }) : null;
    if (doc && blob && g.URL && typeof g.URL.createObjectURL === 'function') {
      var a = doc.createElement('a'), url = g.URL.createObjectURL(blob);
      a.href = url; a.download = name; a.rel = 'noopener';
      (doc.body || doc.documentElement).appendChild(a);
      a.click();
      setTimeout(function () { if (a.parentNode) a.parentNode.removeChild(a); g.URL.revokeObjectURL(url); }, 0);
    }
    return { name: name, text: body, blob: blob, package: pkg };
  }

  g.CLSkyExport = { VERSION: VERSION, snapshot: snapshot, text: textOf, fileName: fileNameOf, current: current, download: download };
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this);
