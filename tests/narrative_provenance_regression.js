'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Source = require('../js/atlas/atlas-source.js');
let checks = 0;
function test(name, run) { run(); checks++; console.log('PASS ' + name); }
function graph(edges, events) {
  return { characters: [], events: events || [
    { id: 'ev_a', order: 1, title: '点火', quote: '点火烧船' },
    { id: 'ev_b', order: 2, title: '船毁', quote: '船烧毁了' }
  ], relations: [], causeEdges: edges || [], meta: { schema: 'castline/4' } };
}
function ref(quote, extra) {
  return Object.assign({ quote, verified: true, status: 'verified', match: 'exact',
    sourceId: 'source-a', textHash: 'source-hash', start: 3, end: 3 + Array.from(quote).length,
    offsetUnit: 'codepoint' }, extra || {});
}
test('server-produced endpoint IDs survive normalize and repeat normalization', () => {
  const input = graph([{ fromEventId: 'ev_a', toEventId: 'ev_b', resolved: true }]);
  const before = JSON.stringify(input), output = Source.normalize(input);
  assert.strictEqual(JSON.stringify(input), before);
  assert.strictEqual(output.causeEdges[0].sourceId, 'ev_a');
  assert.strictEqual(output.causeEdges[0].targetId, 'ev_b');
  assert.strictEqual(output.causeEdges[0].resolved, true);
  assert.deepStrictEqual(Source.normalize(output).causeEdges, output.causeEdges);
});
test('legacy numeric orders and numeric ID zero retain valid endpoints', () => {
  const legacy = Source.normalize(graph([{ from: 1, to: 2 }])).causeEdges[0];
  assert.strictEqual(legacy.resolved, true);
  const zero = Source.normalize(graph([{ fromEventId: 0, toEventId: 'ev_b' }], [
    { id: 0, order: 1 }, { id: 'ev_b', order: 2 }
  ])).causeEdges[0];
  assert.strictEqual(zero.sourceId, 0); assert.strictEqual(zero.resolved, true);
});
test('missing, ambiguous and contradictory endpoints never pick an arbitrary event', () => {
  const conflict = Source.normalize(graph([{ fromEventId: 'ev_a', sourceId: 'ev_b', toEventId: 'ev_b' }])).causeEdges[0];
  assert.strictEqual(conflict.resolved, false); assert.strictEqual(conflict.sourceId, null);
  const missing = Source.normalize(graph([{ fromEventId: 'missing', toEventId: 'ev_b' }])).causeEdges[0];
  assert.strictEqual(missing.resolved, false); assert.strictEqual(missing.fromEventId, 'missing');
  const duplicate = Source.normalize(graph([{ fromEventId: 'same', toEventId: 'same' }], [
    { id: 'same', order: 1 }, { id: 'same', order: 2 }
  ])).causeEdges[0];
  assert.strictEqual(duplicate.resolved, false);
  const ambiguous = Source.normalize(graph([{ from: 1, to: 1 }], [
    { id: 'a', order: 1 }, { id: 'b', order: 1 }
  ])).causeEdges[0];
  assert.strictEqual(ambiguous.resolved, false);
});
test('a quote and a legacy verified flag are not a verified source anchor', () => {
  assert.strictEqual(Source.evidenceStatus({ quote: '引用' }).code, 'quoted');
  assert.strictEqual(Source.evidenceStatus({ quote: '引用', verified: true }).anchored, false);
  assert.strictEqual(Source.evidenceStatus({ source: '文件名', summary: '归纳' }).code, 'synthesis');
});
test('reviewed identity mixtures retain reported values but do not present combined scores', () => {
  const input = graph([]); input.characters = [{id: 'mixed', name: '同名人物', attrs: {智谋: {score: 88, evidence: ['有引句']}}}];
  input.reviewIssues = [{id: 'identity-review', kind: 'identity', status: 'confirmed_issue', characterId: 'mixed', description: '两个不同人物被合并'}];
  const out = Source.normalize(input), attr = out.characters[0].attrs.智谋;
  assert.strictEqual(out.characters[0].identityStatus, 'ambiguous');
  assert.strictEqual(attr.reportedScore, 88); assert.strictEqual(attr.score, null); assert.strictEqual(attr.pending, true);
  assert.strictEqual(Source.normalize(out).characters[0].attrs.智谋.reportedScore, 88);
  assert.strictEqual(out.reviewIssues.length, 1);
});
test('an exact citation with a reviewed wrong-event attribution is not counted as an anchored event', () => {
  const q = '点火烧船', input = graph([]);
  input.events[0].sourceRefs = [ref(q)];
  input.reviewIssues = [{id: 'quote-review', kind: 'quote', status: 'confirmed_issue', eventId: 'ev_a', description: '这段引文属于另一个事件'}];
  input.narrativeUnits = [{id: 'unit', name: '同一目标单元', eventIds: ['ev_a','ev_b']}];
  const out = Source.normalize(input), status = Source.evidenceStatus(out.events[0]);
  assert.strictEqual(status.code, 'quoted'); assert.strictEqual(status.anchored, false);
  assert.strictEqual(status.label, '引文归属待确认'); assert.strictEqual(out.narrativeUnits.length, 1);
});
test('server unresolved state and retained conflicting declarations survive repeated normalization', () => {
  for (const edge of [
    { fromEventId: 'ev_a', toEventId: 'ev_b', declaredSourceId: 'ev_b', referenceStatus: 'unresolved' },
    { fromEventId: 'ev_a', toEventId: 'ev_b', referenceStatus: 'unresolved' },
    { fromEventId: 'ev_a', toEventId: 'ev_b', declaredTargetId: 'ev_a' }
  ]) {
    let current = graph([edge]);
    for (let i = 0; i < 3; i++) {
      current = Source.normalize(current);
      assert.strictEqual(current.causeEdges[0].resolved, false);
      assert.strictEqual(current.causeEdges[0].fromEventId, 'ev_a');
    }
  }
});
test('only matching, complete exact references establish quoted-text verification', () => {
  const q = '😀星光。', valid = ref(q);
  assert.strictEqual(Source.evidenceStatus({ quote: q, quoteRef: valid }).code, 'verified');
  assert.strictEqual(Source.verifyRef(valid, '前三字' + q, 'source-hash').verified, true);
  for (const invalid of [ref('其他句'), ref(q, { match: 'normalized' }), ref(q, { end: 99 }),
    ref(q, { start: 3.5 }), ref(q, { textHash: null }), ref(q, { verified: false })]) {
    assert.strictEqual(Source.evidenceStatus({ quote: q, sourceRefs: [invalid] }).anchored, false);
  }
  assert.strictEqual(Source.evidenceStatus({ quote: q, verified: false, quoteRef: valid }).code, 'quoted');
});
test('partial citation coverage stays unverified and inference stays inference', () => {
  const q = '已证句';
  const partial = Source.evidenceStatus({ quote: q, quoteRef: ref(q), evidence: ['没有来源'] });
  assert.strictEqual(partial.code, 'quoted'); assert.strictEqual(partial.verifiedQuotes, 1);
  assert.strictEqual(partial.anchored, false);
  const inferred = Source.evidenceStatus({ quote: q, quoteRef: ref(q), derived: true });
  assert.strictEqual(inferred.code, 'inference'); assert.strictEqual(inferred.anchored, true);
  const nested = Source.evidenceStatus({ evidence: [{ quote: q, sourceRefs: [ref(q)] }] });
  assert.strictEqual(nested.code, 'verified');
  assert.strictEqual(Source.evidenceStatus({ quote: q, quoteRef: ref(q), basis: 'inferred' }).code, 'inference');
  assert.strictEqual(Source.evidenceStatus({ basis: 'uncertain' }).code, 'unverified');
});
test('tasks survive the application source boundary without manufacturing goals', () => {
  const task = { id: 'task-1', character: '甲', name: '取证', goal: '取回密信', obstacle: '',
    action: '', outcome: '', cost: '', status: 'unknown', eventIds: ['ev_a'], claimVerified: false };
  const raw = Object.assign(graph(), { tasks: [task] });
  const normalized = Source.normalize(raw);
  const reconciled = Source.reconcile(raw, { characters: normalized.characters, events: normalized.events, relations: [] });
  assert.deepStrictEqual(reconciled.tasks, normalized.tasks);
  assert.strictEqual(reconciled.tasks[0].cost, '');
  assert.strictEqual(reconciled.meta.coverage.tasks.known, true);
  assert.strictEqual(Source.normalize(graph()).meta.coverage.tasks.known, false);
});
test('current real-book caches retain unverified quotation status without source offsets', () => {
  for (const key of ['a935953b2678a80b352091d5', '2ef47b2ecaa99a67352091d5', 'd16db79a529a1727352091d5']) {
    const p = path.join(__dirname, '../data/cache', key + '.json');
    const g = Source.normalize(JSON.parse(fs.readFileSync(p, 'utf8')));
    const quoted = g.events.filter(e => typeof e.quote === 'string' && e.quote.trim());
    assert(quoted.length > 0);
    assert.strictEqual(quoted.filter(e => Source.evidenceStatus(e).anchored).length, 0);
    assert.strictEqual(quoted.filter(e => Source.evidenceStatus(e).code === 'quoted').length, quoted.length);
  }
});
console.log(checks + ' narrative provenance regression checks passed');
