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
test('locateStatus separates "can return to source" from "semantics verified"', () => {
  const q = '他仍不放弃。';
  const ref = { sourceId: 's', textHash: 'h', offsetUnit: 'codepoint', start: 0, end: q.length,
    quote: q, match: 'exact', status: 'verified', verified: true };
  const mk = (o) => M.normalize(JSON.parse(JSON.stringify(o)));
  const g1 = mk({ events: [{ id: 'e1', order: 1, chapter: '第一章', title: 't', summary: 's',
    characters: ['甲'], quote: q, quoteRef: ref, sourceRefs: [ref], verified: true }],
    characters: [{ id: 'c1', name: '甲' }] });
  assert.strictEqual(M.evidenceStatus(g1.events[0]).locateStatus, 'anchored');
  const noOffset = Object.assign({}, ref); delete noOffset.start; delete noOffset.end;
  const g2 = mk({ events: [{ id: 'e2', order: 1, chapter: '第一章', title: 't', summary: 's',
    characters: ['甲'], quote: q, quoteRef: noOffset, sourceRefs: [noOffset], verified: false }],
    characters: [{ id: 'c1', name: '甲' }] });
  assert.strictEqual(M.evidenceStatus(g2.events[0]).locateStatus, 'unlocatable');
  const g3 = mk({ events: [{ id: 'e3', order: 1, chapter: '第一章', title: 't', summary: 's',
    characters: ['甲'], quote: q }], characters: [{ id: 'c1', name: '甲' }] });
  assert.strictEqual(M.evidenceStatus(g3.events[0]).locateStatus, 'no_ref');
  const normd = Object.assign({}, ref, { match: 'normalized', verified: false, status: 'unverified' });
  const g4 = mk({ events: [{ id: 'e4', order: 1, chapter: '第一章', title: 't', summary: 's',
    characters: ['甲'], quote: q, quoteRef: normd, sourceRefs: [normd], verified: false }],
    characters: [{ id: 'c1', name: '甲' }] });
  assert.strictEqual(M.evidenceStatus(g4.events[0]).locateStatus, 'unverified_offset');
  const all = ['anchored', 'unverified_offset', 'unlocatable', 'no_ref'];
  const expect = [['anchored', g1], ['unlocatable', g2], ['no_ref', g3], ['unverified_offset', g4]];
  for (const [want, g] of expect) {
    const st = M.evidenceStatus(g.events[0]);
    assert.ok(all.indexOf(st.locateStatus) >= 0, 'unknown locateStatus ' + st.locateStatus);
    assert.strictEqual(st.locateStatus, want);
  }
  assert.notStrictEqual(M.evidenceStatus(g2.events[0]).code, 'verified');
  assert.notStrictEqual(M.evidenceStatus(g3.events[0]).code, 'verified');
  const counts = {};
  [g1, g2, g3, g4].forEach((g) => {
    const k = M.evidenceStatus(g.events[0]).locateStatus;
    counts[k] = (counts[k] || 0) + 1;
  });
  assert.strictEqual(Object.values(counts).reduce((a, b) => a + b, 0), 4);
});
test('a bare-string attribute evidence pairs with its container ref by identical quote', () => {
  const q = '他仍不放弃。';
  const ref = { sourceId: 's', textHash: 'h', offsetUnit: 'codepoint', start: 0, end: q.length,
    quote: q, match: 'exact', status: 'verified', verified: true };
  const raw = { characters: [{ name: '甲', attrs: { 意志: { score: 50, evidence: [q], sourceRefs: [ref] } } }],
    meta: {} };
  const g = M.normalize(JSON.parse(JSON.stringify(raw)));
  assert.strictEqual(g.meta.identity.evidence.declarations, 1);
  assert.strictEqual(g.meta.identity.evidence.located, 1);
  assert.strictEqual(g.meta.identity.evidence.unlocated, 0);
  const bad = JSON.parse(JSON.stringify(raw));
  bad.characters[0].attrs.意志.sourceRefs[0].end = q.length + 3;
  const g2 = M.normalize(bad);
  assert.strictEqual(g2.meta.identity.evidence.located, 0);
  assert.strictEqual(g2.meta.identity.evidence.unlocated, 1);
  const other = JSON.parse(JSON.stringify(raw));
  other.characters[0].attrs.意志.sourceRefs[0].quote = '另一句完全不同的原文。';
  const g3 = M.normalize(other);
  assert.strictEqual(g3.meta.identity.evidence.located, 0);
  assert.strictEqual(g3.meta.identity.evidence.unlocated, 1);
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
  assert.strictEqual(joined.meta.sourceWarnings.filter(w => w.code === 'missing-event-id').length, 2);
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
test('reconcile preserves authored state journeys and their own nested citations', () => {
  const source = { characters: [{ id: 'c', name: '甲' }], events: [{ id: 'e', order: 1 }],
    stateTransitions: [{ id: 'st', before: '未发现', after: '发现', knowledge: [{ text: '密门', sourceRefs: [{ quote: '密门出现。' }] }] }],
    characterTransitions: [{ id: 'ct', before: '信任', after: '怀疑', transition: { sourceRefs: [{ quote: '他起了疑心。' }] } }] };
  const before = JSON.stringify(source), normalized = M.normalize(source);
  const joined = M.reconcile(source, { characters: normalized.characters, events: normalized.events, relations: [] });
  assert.deepStrictEqual(joined.stateTransitions, normalized.stateTransitions);
  assert.deepStrictEqual(joined.characterTransitions, normalized.characterTransitions);
  assert.strictEqual(joined.meta.capabilities.optionalLayers.stateTransitions, true);
  assert.strictEqual(JSON.stringify(source), before);
});
test('state journey optional coverage distinguishes missing and explicit scoped empty', () => {
  const absent = M.normalize({}), empty = M.normalize({ stateTransitions: [], meta: { coverage: { stateTransitions: { known: true, scope: '首章' } } } });
  assert.strictEqual(Object.hasOwn(absent, 'stateTransitions'), false);
  assert.strictEqual(absent.meta.coverage.stateTransitions.known, false);
  assert.strictEqual(empty.meta.coverage.stateTransitions.known, true);
  assert.strictEqual(empty.meta.coverage.stateTransitions.scope, '首章');
});
function positioned(id, start, order, extra) {
  const quote = '😀甲走进宫城。';
  const row = { id, chapter: '第一回', quote, sourceRefs: [{ sourceId: 's', textHash: 'hash',
    start, end: start + Array.from(quote).length, quote, match: 'exact', offsetUnit: 'codepoint', verified: true, status: 'verified' }] };
  if (order !== undefined) row.order = order;
  return Object.assign(row, extra || {});
}
function sourced(events, extra) {
  return Object.assign({ meta: { sources: [{ id: 's', textHash: 'hash', chars: 1000 }] }, events }, extra || {});
}
test('named additions return to source appearance order while legacy line numbers remain traceable', () => {
  const input = sourced([positioned('first', 100, 1, { title: '原有标题', name: '不覆盖标题' }),
    positioned('last', 900, 2, { title: '结束' }), positioned('added', 200, undefined, { name: '途中事件' })],
    { storylines: [{ id: 'old-line', events: [1, 2], eventIds: ['first', 'last'], attach_order: 2 }] });
  const before = JSON.stringify(input), g = M.normalize(input);
  assert.deepStrictEqual(g.events.map(e => e.id), ['first', 'added', 'last']);
  assert.deepStrictEqual(g.events.map(e => e.title), ['原有标题', '途中事件', '结束']);
  assert.strictEqual(g.events[1].name, '途中事件');
  assert.strictEqual(g.events[1].rawOrder, null);
  assert.strictEqual(g.events[1].rawOrderKnown, false);
  assert.strictEqual(g.events[2].rawOrder, 2);
  assert.deepStrictEqual(g.storylines[0].events, [1, 3]);
  assert.deepStrictEqual(g.storylines[0].rawEvents, [1, 2]);
  assert.strictEqual(g.storylines[0].attach_order, 3);
  assert.deepStrictEqual(g.meta.eventIndexMap.rawOrderToNormalized['2'], [2]);
  assert.strictEqual(g.meta.eventOrdering.basis, 'source_appearance_not_causality_or_story_time');
  assert.strictEqual(JSON.stringify(input), before);
  assert.deepStrictEqual(M.normalize(g).events, g.events);
  assert.deepStrictEqual(M.normalize(g).storylines, g.storylines);
});
test('stable storyline IDs disambiguate repeated orders but numeric-only references stay pending', () => {
  const g = M.normalize(sourced([positioned('first', 100, 1), positioned('last', 900, 2), positioned('added', 200, 1)],
    { storylines: [{ id: 'stable', events: [1, 2], eventIds: ['first', 'last'], attachEventId: 'first', attach_order: 1 },
      { id: 'legacy', events: [1, 2] }] }));
  assert.deepStrictEqual(g.storylines[0].eventIds, ['first', 'last']);
  assert.deepStrictEqual(g.storylines[0].events, [1, 3]);
  assert.strictEqual(g.storylines[0].attach_order, 1);
  assert.deepStrictEqual(g.storylines[1].eventIds, ['last']);
  assert.deepStrictEqual(g.meta.eventIndexMap.rawOrderToNormalized['1'], [0, 1]);
  assert(g.meta.sourceWarnings.some(w => w.code === 'ambiguous-event-order'));
});
test('unquoted legacy events have honest intervals, not invented exact positions', () => {
  const g = M.normalize(sourced([positioned('first', 100, 1), { id: 'between', order: 2, chapter: '第1回' },
    positioned('last', 300, 3), positioned('new', 200, undefined)]));
  const between = g.events.find(e => e.id === 'between');
  assert.deepStrictEqual(g.events.map(e => e.id), ['first', 'between', 'new', 'last']);
  assert.strictEqual(between.sourcePosition.kind, 'legacy_interval');
  assert.strictEqual(between.sourcePosition.exactWithinInterval, false);
  assert.strictEqual(between.sourcePosition.start, 100);
  assert.strictEqual(between.sourcePosition.end, 300);
  assert.strictEqual(g.meta.eventOrdering.bounded, 1);
  assert.strictEqual(g.meta.eventOrdering.complete, false);
  assert.deepStrictEqual(M.normalize(g).events, g.events);
});
test('stale, contradictory, reviewed and backwards references cannot certify placement', () => {
  const stale = positioned('stale', 1); stale.sourceRefs[0].textHash = 'old-hash';
  const ambiguous = positioned('ambiguous', 2); ambiguous.sourceRefs.push(Object.assign({}, ambiguous.sourceRefs[0], { start: 12, end: 19 }));
  const reviewed = positioned('reviewed', 3, undefined, { quoteReview: 'wrong-scene' });
  const wrongUnit = positioned('utf16', 4); wrongUnit.sourceRefs[0].end = 4 + wrongUnit.quote.length;
  const g = M.normalize(sourced([positioned('before', 300, 1), { id: 'unknown', order: 2, chapter: '第一回' },
    positioned('after', 100, 3), stale, ambiguous, reviewed, wrongUnit]));
  for (const id of ['unknown', 'stale', 'ambiguous', 'reviewed', 'utf16']) {
    assert.strictEqual(g.events.find(e => e.id === id).sourcePosition.kind, 'unresolved', id);
    assert(g.meta.eventOrdering.unresolvedIds.includes(id));
  }
  assert.strictEqual(g.events.find(e => e.id === 'ambiguous').sourcePosition.reason, 'ambiguous_primary_quote');
});
test('offsets from different sources do not become a global chronology', () => {
  const first = positioned('a', 900, 1), second = positioned('b', 10, 2);
  second.sourceRefs[0].sourceId = 'other';
  const g = M.normalize(sourced([first, second], { meta: { sources: [
    { id: 's', textHash: 'hash', chars: 1000 }, { id: 'other', textHash: 'hash', chars: 1000 }] } }));
  assert.deepStrictEqual(g.events.map(e => e.id), ['a', 'b']);
  assert.strictEqual(g.meta.eventOrdering.mode, 'legacy_order_no_comparable_source');
  assert.strictEqual(g.meta.eventOrdering.complete, false);
  assert(g.events.every(e => e.sourcePosition.reason === 'multiple_sources_no_global_order'));
});
test('name fallback does not infer actors or fabricate unknown titles', () => {
  const g = M.normalize(sourced([positioned('named', 100, undefined, { name: '甲救下乙' }), positioned('unnamed', 200),
    positioned('blank', 300, undefined, { name: '   ' })], { characters: [{ name: '甲' }, { name: '乙' }] }));
  assert.strictEqual(g.events[0].title, '甲救下乙');
  assert(!g.events[0].characters || g.events[0].characters.length === 0);
  assert(!g.events[1].title);
  assert(!g.events[2].title);
});
process.stdout.write('\n' + count + ' atlas source contract checks passed\n');
