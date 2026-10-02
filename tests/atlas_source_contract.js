/* Run: node tests/atlas_source_contract.js (offline, no browser or network). */
'use strict';
const assert = require('assert');
const M = require('../js/atlas/atlas-source.js');
let count = 0;
function test(name, run) { run(); count++; process.stdout.write('PASS ' + name + '\n'); }
const fixture = {
  meta: { schema: 'castline/3' },
  characters: [{ id: 'writer-ch', name: '北辰' }],
  events: [
    { id: 'ev-late', order: 90, chapter: '终章', title: '归来', quote: '他终究归来。', characters: ['北辰'] },
    { id: 'ev-world', order: 4, chapter: '序章', title: '天裂', quote: '天穹裂开。', characters: [] },
    { id: 'ev-first', order: 12, chapter: '首章', title: '出发', quote: '他离开家。', characters: ['北辰'] }
  ],
  storylines: [{ id: 'writer-line', name: '归途', events: [12, 90], kind: '主线', attach_order: 0 }],
  locations: [{ id: 'writer-place', name: '古塔', mystery: { sealed: true } }],
  items: [],
  characterStates: [{ id: 'writer-state', characterId: 'writer-ch', chapterRange: ['首章', '终章'], attrs: { 意志: { score: 88, evidence: ['他仍不放弃。'] } } }]
};

test('normalize is pure and keeps existing IDs', () => {
  const before = JSON.stringify(fixture), g = M.normalize(fixture);
  assert.strictEqual(JSON.stringify(fixture), before);
  assert.strictEqual(g.characters[0].id, 'writer-ch');
  assert.deepStrictEqual(g.events.map(e => e.id), ['ev-world', 'ev-first', 'ev-late']);
  assert.strictEqual(g.locations[0].id, 'writer-place');
});
test('source order is mapped, not mistaken for event array index', () => {
  const g = M.normalize(fixture);
  assert.deepStrictEqual(g.storylines[0].events, [2, 3]);
  assert.deepStrictEqual(g.storylines[0].eventIdxs, [1, 2]);
  assert.deepStrictEqual(g.storylines[0].eventIds, ['ev-first', 'ev-late']);
  assert.deepStrictEqual(g.meta.eventIndexMap.rawOrderToNormalized['90'], [2]);
});
test('world events and opaque optional fields survive', () => {
  const g = M.normalize(fixture);
  assert.strictEqual(g.events[0].characters.length, 0);
  assert.deepStrictEqual(g.locations[0].mystery, { sealed: true });
  assert.strictEqual(g.characterStates[0].attrs.意志.score, 88);
  assert.strictEqual(Object.hasOwn(g, 'clues'), false);
});
test('empty optional arrays do not claim extraction succeeded', () => {
  const report = M.inspect(M.normalize(fixture));
  assert.strictEqual(report.coverage.items.known, false);
  assert.strictEqual(report.coverage.worldRules.known, false);
  assert.strictEqual(report.counts.worldRules, null);
  assert.strictEqual(report.provenance.known, false);
  assert.strictEqual(report.complete, null);
});
test('explicit empty extraction retains its declared scope', () => {
  const g = M.normalize({ clues: [], meta: { coverage: { clues: { known: true, scope: 'chapter-one' } } } });
  assert.strictEqual(g.meta.coverage.clues.known, true);
  assert.strictEqual(g.meta.coverage.clues.scope, 'chapter-one');
});
test('normalize is idempotent and does not duplicate migrations', () => {
  const a = M.normalize(fixture), b = M.normalize(a);
  assert.deepStrictEqual(a.events, b.events);
  assert.deepStrictEqual(a.storylines, b.storylines);
  assert.deepStrictEqual(a.meta.migrations, b.meta.migrations);
});
test('generated character identities survive list reorder', () => {
  const a = M.normalize({ characters: [{ name: '甲' }, { name: '乙' }] });
  const b = M.normalize({ characters: [{ name: '乙' }, { name: '甲' }] });
  assert.strictEqual(a.characters[0].id, b.characters[1].id);
});
test('ID zero is not overwritten by a truthiness fallback', () => {
  const g = M.normalize({ characters: [{ id: 0, name: '零' }], events: [{ id: 0, order: 8 }] });
  assert.strictEqual(g.characters[0].id, 0);
  assert.strictEqual(g.events[0].id, 0);
});
test('ambiguous source orders are warned and never randomly attached', () => {
  const g = M.normalize({ events: [{ order: 7, title: '甲' }, { order: 7, title: '乙' }, { order: 18, title: '丙' }],
    storylines: [{ id: 'line', events: [7, 18] }] });
  assert.deepStrictEqual(g.storylines[0].events, [3]);
  assert.strictEqual(g.meta.sourceWarnings[0].code, 'ambiguous-event-order');
});
test('raw invalid slots do not shift the raw-index map', () => {
  const g = M.normalize({ events: [null, { id: 'b', order: 6 }, false, { id: 'a', order: 1 }] });
  assert.strictEqual(g.meta.eventIndexMap.rawIndexToNormalized['1'], 1);
  assert.strictEqual(g.meta.eventIndexMap.rawIndexToNormalized['3'], 0);
});
test('unmeasured importance/strength/attributes remain unknown', () => {
  const g = M.normalize({ characters: [{ name: '甲', attrs: { 意志: { score: 50, evidence: [] } } }],
    relations: [{ a: '甲', b: '乙', kind: '同行' }] });
  assert.strictEqual(g.characters[0].importance, null);
  assert.strictEqual(g.characters[0].attrs.意志.score, null);
  assert.strictEqual(g.characters[0].attrs.意志.reportedScore, 50);
  assert.strictEqual(g.relations[0].strength, null);
});
test('reconcile restores IDs after UI rebuilding and filtering', () => {
  const g = M.normalize(fixture);
  const rendered = { characters: [{ name: '北辰', importance: 99 }],
    events: [Object.assign({}, g.events[2], { id: undefined, entityId: undefined }), g.events[1]],
    relations: [] };
  const joined = M.reconcile(fixture, rendered);
  assert.strictEqual(joined.characters[0].id, 'writer-ch');
  assert.deepStrictEqual(joined.events.map(e => e.id), ['ev-late', 'ev-first']);
  assert.deepStrictEqual(joined.storylines[0].events, [1, 2]);
  assert.deepStrictEqual(joined.storylines[0].eventIds, ['ev-late', 'ev-first']);
  assert.strictEqual(joined.locations[0].id, 'writer-place');
});
test('filtered storyline references are not reassigned to another event', () => {
  const g = M.normalize(fixture);
  const joined = M.reconcile(fixture, { characters: g.characters, events: [g.events[0]], relations: [] });
  assert.deepStrictEqual(joined.storylines[0].events, []);
  assert.strictEqual(joined.meta.sourceWarnings.filter(w => w.code === 'missing-event-order').length, 2);
});
test('exact sourceRef replay understands codepoint offsets', () => {
  const raw = '😀她推开门。', ref = { status: 'verified', verified: true, quote: '她推开门。', start: 1, end: 6,
    sourceId: 's', textHash: 'hash', offsetUnit: 'codepoint' };
  assert.strictEqual(M.verifyRef(ref, raw, 'hash').verified, true);
  assert.strictEqual(M.verifyRef(ref, raw, 'different').verified, false);
  assert.strictEqual(M.verifyRef(Object.assign({}, ref, { verified: false }), raw).verified, false);
});
test('inspect counts anchored references, not summary prose', () => {
  const g = M.normalize({ events: [{ title: '事件', summary: '看似原文但只是摘要', sourceRefs: [
    { status: 'verified', verified: true, quote: '星光。', sourceId: 's', textHash: 'h', start: 0, end: 3 },
    { status: 'unverified', verified: false, quote: '近似星光', sourceId: null, textHash: null }
  ] }] });
  assert.deepStrictEqual(M.inspect(g).sourceRefs, { total: 2, anchored: 1, unverified: 1 });
});
test('no silent 48-line/16-event cap exists in the adapter', () => {
  const g = M.normalize({ events: Array.from({ length: 3000 }, (_, i) => ({ order: i + 100, title: '事件' + i })),
    storylines: Array.from({ length: 70 }, (_, i) => ({ id: 's' + i, events: [i + 100] })) });
  assert.strictEqual(g.events.length, 3000); assert.strictEqual(g.storylines.length, 70);
});
process.stdout.write('\n' + count + ' atlas source contract checks passed\n');
