'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Source = require('../js/atlas/atlas-source.js');

let checks = 0;
function test(name, run) { run(); checks++; process.stdout.write('PASS ' + name + '\n'); }
const cachePath = key => path.join(__dirname, '..', 'data', 'cache', key + '.json');
const read = key => JSON.parse(fs.readFileSync(cachePath(key), 'utf8'));

function v4(extra) {
  return Object.assign({
    title: '契约样本',
    characters: [
      { id: 'ch_a', name: '甲', aliases: ['阿甲'], importance: null, attrs: { 意志: { score: 71, evidence: ['他仍不放弃。'] } } },
      { id: 'ch_b', name: '乙', aliases: ['阿甲'] }
    ],
    events: [
      { id: 'ev_2', order: 2, chapter: '第二章 归途', title: '归来', quote: '他终究归来。', characters: ['甲'] },
      { id: 'ev_1', order: 1, chapter: '第一章  出发', title: '出发', quote: '他离开家。', characters: ['乙'] }
    ],
    relations: [{ id: 'rel_1', a: '甲', b: '乙', kind: '同行', line: '明线' }],
    storylines: [{ id: 'sl_1', name: '归途', eventIds: ['ev_1', 'ev_2'] }],
    meta: { schema: 'castline/4', schemaVersion: 'castline/4' }
  }, extra || {});
}

test('a castline/4 graph opens in the castline/5 reader and reports its origin', () => {
  const g = Source.normalize(v4());
  assert.strictEqual(g.meta.schemaVersion, 'castline/5');
  assert.strictEqual(g.meta.schemaCompat.inputSchema, 'castline/4');
  assert.strictEqual(g.meta.schemaCompat.additive, true);
  assert.deepStrictEqual(g.meta.schemaCompat.hops, ['castline/4>castline/5']);
  assert.deepStrictEqual(g.meta.schemaCompat.reads, Source.readsDown);
  for (const legacy of ['castline/3', 'v3-universal', 'legacy']) {
    assert(Source.readsDown.indexOf(legacy) >= 0, legacy + ' must stay readable');
  }
});

test('every legacy schema still opens without a migration step', () => {
  for (const schema of ['castline/4', 'castline/3', 'v3-universal', undefined]) {
    const input = v4();
    delete input.meta.schema; delete input.meta.schemaVersion;
    if (schema) { input.meta.schema = schema; input.meta.schemaVersion = schema; }
    const g = Source.normalize(input);
    assert.strictEqual(g.events.length, 2, String(schema));
    assert.strictEqual(g.characters.length, 2, String(schema));
    assert.strictEqual(g.meta.schemaVersion, 'castline/5', String(schema));
    assert(Source.inspect(g).complete === null, 'completeness must not be invented');
  }
});

test('opening a legacy graph never rewrites the bytes it was given', () => {
  const input = v4(), before = JSON.stringify(input);
  Source.normalize(input); Source.inspect(input);
  assert.strictEqual(JSON.stringify(input), before);
});

test('a published revision is never migrated in place', () => {
  const published = v4({ meta: { schema: 'castline/4', schemaVersion: 'castline/4',
    revision: { key: 'abc123', parentKey: 'parent', originalPreserved: true, version: 'narrative/7-context-conservative' } } });
  const plan = Source.migrationPlan(published);
  assert.strictEqual(plan.published.key, 'abc123');
  assert.strictEqual(plan.inPlaceAllowed, false);
  const applied = Source.applyMigration(published);
  assert.strictEqual(applied.ok, false);
  assert.strictEqual(applied.reason, 'published_revision_not_migrated_in_place');
  const forced = Source.applyMigration(published, { allowPublished: true });
  assert.strictEqual(forced.ok, true);
});

test('migration is additive and every legacy value survives it', () => {
  const input = v4({ customLegacyField: { keep: 1 } });
  const before = JSON.stringify(input);
  const result = Source.applyMigration(input);
  assert.strictEqual(result.ok, true, JSON.stringify(result.unrecoverable || []));
  assert.strictEqual(result.legacyFieldsPreserved, true);
  assert.strictEqual(JSON.stringify(result.graph.customLegacyField), '{"keep":1}');
  assert.deepStrictEqual(result.documentedRewrites.map(r => r.path), ['events[].order']);
  assert.strictEqual(result.graph.events[0].rawOrder, 1);
  assert.strictEqual(result.graph.events[1].rawOrder, 2);
  assert.strictEqual(JSON.stringify(input), before, 'the input graph is not mutated');
});

test('rollback restores the exact snapshot a reader had before the hop', () => {
  const input = v4();
  const snapshot = JSON.parse(JSON.stringify(input));
  const migrated = Source.applyMigration(input).graph;
  const back = Source.rollbackMigration(migrated, snapshot);
  assert.strictEqual(back.ok, true);
  assert.strictEqual(back.snapshotUsed, true);
  assert.strictEqual(back.rewroteLegacyFields, false);
  assert.strictEqual(JSON.stringify(back.graph), JSON.stringify(snapshot));
  assert.strictEqual(back.toSchema, 'castline/4');
  const without = Source.rollbackMigration(migrated);
  assert.strictEqual(without.snapshotUsed, false);
  assert.strictEqual(without.graph.meta.identity, undefined);
  assert.strictEqual(without.graph.events.length, migrated.events.length);
  assert.deepStrictEqual(without.restoredFields, ['dualRead', 'identity', 'schemaCompat']);
});

test('chapter IDs are content-addressed and independent of array order', () => {
  const a = Source.normalize(v4());
  const shuffled = v4();
  shuffled.events = shuffled.events.slice().reverse();
  const b = Source.normalize(shuffled);
  const idsA = a.meta.identity.ids.chapters.slice().sort();
  const idsB = b.meta.identity.ids.chapters.slice().sort();
  assert.deepStrictEqual(idsA, idsB);
  assert.strictEqual(idsA.length, 2, 'whitespace runs collapse, distinct labels do not');
  assert.strictEqual(Source.chapterId('第一章  出发'), a.meta.identity.ids.chapters[0]);
});

test('event, character, relation, storyline and evidence IDs are stable', () => {
  const a = Source.normalize(v4());
  const shuffled = v4();
  shuffled.characters = shuffled.characters.slice().reverse();
  const b = Source.normalize(shuffled);
  for (const field of ['events', 'characters', 'relations', 'storylines']) {
    const key = field === 'storylines' ? a.meta.identity.ids.storylines : a.meta.identity.ids[field];
    const other = field === 'storylines' ? b.meta.identity.ids.storylines : b.meta.identity.ids[field];
    assert.deepStrictEqual(key.slice().sort(), other.slice().sort(), field + ' ids must not move');
  }
  const ev = { quote: '他终究归来。' };
  assert.strictEqual(Source.evidenceId(ev), Source.evidenceId({ quote: '他终究归来。' }));
  assert.notStrictEqual(Source.evidenceId(ev), Source.evidenceId({ quote: '他离开了。' }));
  const twice = Source.normalize(a);
  assert.deepStrictEqual(twice.events.map(e => e.id), a.events.map(e => e.id));
  assert.deepStrictEqual(twice.meta.identity.ids.chapters, a.meta.identity.ids.chapters);
});

test('a name claimed by two nodes goes to the review queue and is never merged', () => {
  const g = Source.normalize(v4());
  const queue = g.meta.identity.aliases.queue;
  const row = queue.filter(r => r.token === '阿甲');
  assert.strictEqual(row.length, 1, '阿甲 is one node name and another node alias');
  assert.strictEqual(row[0].autoMerged, false);
  assert.strictEqual(row[0].attribution, 'review_required');
  assert.strictEqual(row[0].nodeIds.length, 2);
  assert.strictEqual(g.meta.identity.aliases.autoMerged, 0);
  assert.deepStrictEqual(g.characters.map(c => c.name).sort(), ['乙', '甲']);
  assert.deepStrictEqual(g.characters[0].aliases.concat(g.characters[1].aliases), ['阿甲', '阿甲']);
});

test('a conflicted name is not used to attribute events or relations', () => {
  const g = Source.normalize(v4({ events: [
    { id: 'ev_x', order: 1, chapter: '第一章', title: '同场', characters: ['阿甲'], quote: '两人同场。' }
  ] }));
  assert.deepStrictEqual(g.events[0].ambiguousTokens, ['阿甲']);
  assert.strictEqual(g.events[0].attribution, 'review_required');
  assert(g.meta.identity.reviewQueue.some(r => r.kind === 'event_cast_alias_conflict'));
});

test('a reviewed identity conflict keeps its node in the queue and its scores pending', () => {
  const input = v4();
  input.characters[0].attrs.意志 = { score: 88, evidence: ['他仍不放弃。'] };
  input.reviewIssues = [{ id: 'issue_1', kind: 'identity', status: 'confirmed_issue', characterId: 'ch_a',
    identityStatus: 'canonical_name_conflict_in_reviewed_scope', description: '主名与别名冲突' }];
  const g = Source.normalize(input);
  const attr = g.characters[0].attrs.意志;
  assert.strictEqual(attr.score, null);
  assert.strictEqual(attr.pending, true);
  assert.strictEqual(attr.reportedScore, 88, 'the reported value is retained, not deleted');
  assert(g.meta.identity.reviewQueue.some(r => r.kind === 'reviewed_identity_issue' && r.nodeIds[0] === 'ch_a'));
  assert.strictEqual(g.meta.identity.aliases.autoMerged, 0);
});

test('missing fields degrade to explicit unknown, never to a default value', () => {
  const g = Source.normalize({
    characters: [{ id: 'ch_a', name: '甲', attrs: { 意志: {} } }],
    events: [{ id: 'ev_1', order: 1, title: '无证据事件' }],
    relations: [{ id: 'rel_1', a: '甲', b: '甲', kind: '自指' }]
  });
  assert.strictEqual(g.characters[0].importance, null);
  assert.strictEqual(g.characters[0].importanceKnown, false);
  assert.strictEqual(g.characters[0].attrs.意志.score, null);
  assert.strictEqual(g.characters[0].attrs.意志.pending, true);
  assert.strictEqual(g.meta.identity.chapters.unlabelledEvents, 1);
  assert.strictEqual(g.meta.identity.chapters.count, 0);
  assert.strictEqual(g.meta.identity.orphans.relations, 1);
  assert.strictEqual(g.relations[0].strength, null);
  assert.strictEqual(g.relations[0].strengthKnown, false);
  assert.strictEqual(g.meta.identity.unknown.fabricatedDefaults, 0);
});

test('unknown coverage stays unknown rather than defaulting to known', () => {
  const g = Source.normalize({ characters: [], events: [] });
  const report = Source.inspect(g);
  for (const field of ['clues', 'causeEdges', 'characterStates', 'locations']) {
    assert.strictEqual(report.coverage[field].known, false, field + ' must not claim extraction');
  }
  assert.strictEqual(report.complete, null);
  assert.strictEqual(report.extraction.reason, 'legacy_coverage_unknown');
});

test('real castline/4 caches still open, with measured identity ledgers', () => {
  const keys = ['9b676d7031b1bcd3b8377a18', 'df959d743e53206f56db2f92', '152e2a6eed94f1075e7e7070'];
  for (const key of keys) {
    const raw = read(key);
    assert.strictEqual(raw.meta.schemaVersion, 'castline/4', key + ' must still be a v4 cache on disk');
    const before = JSON.stringify(raw);
    const g = Source.normalize(raw);
    assert.strictEqual(JSON.stringify(raw), before, key + ' must not be modified by reading it');
    assert.strictEqual(g.meta.schemaCompat.inputSchema, 'castline/4');
    assert(g.meta.identity.ids.chapters.length > 100, key + ' chapters must be identified');
    assert.strictEqual(g.meta.identity.chapters.unlabelledEvents, 0, key);
    assert.strictEqual(g.meta.identity.aliases.autoMerged, 0, key + ' must never auto-merge');
    assert.strictEqual(Source.migrationPlan(raw).inPlaceAllowed, false, key);
  }
});

test('the dafeng canonical/alias collision is queued with its real impact', () => {
  const g = Source.normalize(read('9b676d7031b1bcd3b8377a18'));
  const queue = g.meta.identity.aliases.queue;
  const row = queue.filter(r => r.token === '初代监正');
  assert.strictEqual(row.length, 1, '初代监正 is a node name and 许平峰 alias');
  assert.strictEqual(row[0].nodeIds.length, 2);
  assert(row[0].nodeIds.indexOf('ch_45b2bc1e3bbde2b4') >= 0);
  assert(row[0].nodeIds.indexOf('ch_d50998c6c5bc7460') >= 0);
  const affected = g.events.filter(e => (e.characters || []).indexOf('初代监正') >= 0);
  assert(affected.length > 50, 'the collision affects many events: ' + affected.length);
  assert(affected.every(e => e.attribution === 'review_required'));
  assert(affected.every(e => e.ambiguousTokens.indexOf('初代监正') >= 0));
});

test('the reviewed 许玉春/李玉春 conflict is queued, not resolved by name equality', () => {
  const g = Source.normalize(read('9b676d7031b1bcd3b8377a18'));
  const node = g.characters.filter(c => c.name === '许玉春')[0];
  assert(node && node.identityStatus === 'ambiguous');
  assert(node.aliases.indexOf('李玉春') >= 0);
  assert(Object.keys(node.attrs).every(k => node.attrs[k].score === null && node.attrs[k].pending === true));
  assert(g.meta.identity.reviewQueue.some(r => r.nodeIds.indexOf(node.id) >= 0));
  assert.strictEqual(g.meta.identity.aliases.autoMerged, 0);
});

test('dual read keeps both spellings available to downstream readers', () => {
  const legacy = v4({ meta: { schema: 'castline/4', schemaVersion: 'castline/4' } });
  legacy.events[0].sourceRef = { quote: '他终究归来。', status: 'unverified' };
  legacy.events[0].sourceRefs = [{ quote: '他终究归来。', status: 'unverified' }];
  const g = Source.normalize(legacy);
  assert.deepStrictEqual(g.meta.dualRead.fields.entityId, ['id']);
  assert.strictEqual(g.meta.dualRead.policy, 'both_spellings_read_no_preference_order');
  assert.strictEqual(g.meta.dualRead.autoMerged, 0);
  assert.strictEqual(g.meta.dualRead.conflicts.length, 0);
});

test('a genuine dual-read disagreement becomes a pending conflict', () => {
  const legacy = v4({ meta: { schema: 'castline/4', schemaVersion: 'castline/4' } });
  legacy.events[0].sourceRefs = [{ quote: '甲句', status: 'unverified', sourceId: 's', textHash: 'h', start: 0, end: 2 }];
  legacy.events[0].sourceRef = { quote: '乙句', status: 'unverified', sourceId: 's', textHash: 'h', start: 5, end: 7 };
  const g = Source.normalize(legacy);
  const conflicts = g.meta.dualRead.conflicts;
  assert.strictEqual(conflicts.length, 1);
  assert.strictEqual(conflicts[0].field, 'sourceRefs');
  assert.strictEqual(conflicts[0].resolution, 'pending_review');
  assert.deepStrictEqual(conflicts[0].fields, ['sourceRefs', 'sourceRef']);
});

test('inspect exposes the migration surface for a reader', () => {
  const report = Source.inspect(Source.normalize(v4()));
  assert.strictEqual(report.additive, true);
  assert.strictEqual(report.schemaCompat.inputSchema, 'castline/4');
  assert.strictEqual(report.identity.version, 'castline/identity/1');
  assert.deepStrictEqual(report.reviewQueue, report.identity.reviewQueue);
  assert.strictEqual(report.writesSchema, undefined);
  assert.strictEqual(Source.writesSchema, 'castline/5');
});

test('current reviewed books retain source identities, original references and monotonically ordered exact anchors', () => {
  for (const key of ['ec4cbc93674ff8f4cdfc8138', 'fe42d01f3826fe8096f86614', 'a065244455cfb2221bcda94a']) {
    const input = read(key), before = JSON.stringify(input), g = Source.normalize(input);
    const original = new Map(input.events.map(e => [e.id, e]));
    assert.strictEqual(g.events.length, input.events.length, key);
    assert.strictEqual(new Set(g.events.map(e => e.id)).size, original.size, key);
    let previous = -1;
    for (const e of g.events) {
      const raw = original.get(e.id);
      assert(raw, key + ': stable ID changed');
      assert.deepStrictEqual(e.characters, raw.characters, key + ': actors were inferred');
      if (!String(raw.title || '').trim() && String(raw.name || '').trim()) assert.strictEqual(e.title, raw.name);
      if (!String(raw.title || '').trim() && !String(raw.name || '').trim()) assert(!String(e.title || '').trim());
      if (e.sourcePosition.kind === 'exact_quote') {
        assert(e.sourcePosition.start >= previous, key + ': source offsets run backwards');
        previous = e.sourcePosition.start;
        const source = input.meta.sources.find(s => s.id === e.sourcePosition.sourceId);
        assert(source && source.textHash === e.sourcePosition.textHash, key + ': wrong source version');
      }
    }
    for (const line of input.storylines) {
      const projected = g.storylines.find(x => x.id === line.id);
      if (line.eventIds && line.eventIds.length) assert.deepStrictEqual(projected.eventIds.slice().sort(), line.eventIds.slice().sort());
      assert.deepStrictEqual(projected.rawEvents, line.rawEvents || line.events);
    }
    assert.strictEqual(JSON.stringify(input), before, key + ': input graph changed');
    const again = Source.normalize(g);
    assert.deepStrictEqual(again.events.map(e => [e.id, e.order, e.rawOrder, e.sourcePosition]),
      g.events.map(e => [e.id, e.order, e.rawOrder, e.sourcePosition]), key + ': projection is not idempotent');
    assert.deepStrictEqual(again.storylines, g.storylines, key + ': repeated open changed storyline references');
  }
});
process.stdout.write('\n' + checks + ' schema migration contract checks passed\n');
