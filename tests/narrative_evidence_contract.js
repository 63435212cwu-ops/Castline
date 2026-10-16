const assert = require('assert');
const Source = require('../js/atlas/atlas-source.js');

function graph(extra) {
  return Object.assign({
    title: 'narrative-contract',
    characters: [{ name: '甲' }],
    events: [
      { order: 1, chapter: '一', title: '起点', characters: ['甲'], quote: '起点原文' },
      { order: 2, chapter: '二', title: '结果', characters: ['甲'], quote: '结果原文' }
    ],
    relations: [], storylines: []
  }, extra || {});
}

function check(name, fn) {
  fn(); console.log('PASS ' + name);
}

check('narrative schema version and coverage are registered', () => {
  const g = Source.normalize(graph());
  assert.strictEqual(g.meta.narrativeEvidence.version, 'castline/narrative-evidence/1');
  assert.strictEqual(g.meta.coverage.narrative.causes.reason, 'not_provided');
  assert.strictEqual(g.meta.coverage.narrative.evidence.reason, 'not_provided');
});

check('unique order refs resolve cause edges to stable event IDs', () => {
  const g = Source.normalize(graph({ causeEdges: [{ id: 'c1', from: 1, to: 2, basis: '原文明确' }] }));
  const edge = g.causeEdges[0];
  assert(edge && edge.resolved && edge.sourceId && edge.targetId);
  assert.strictEqual(edge.basisCode, 'explicit');
});

check('ambiguous order refs remain unresolved', () => {
  const g = Source.normalize(graph({ events: [
    { order: 1, chapter: '一', title: '甲', characters: ['甲'], quote: '甲' },
    { order: 1, chapter: '一', title: '乙', characters: ['甲'], quote: '乙' }
  ], causeEdges: [{ id: 'c1', from: 1, to: 1 }] }));
  assert.strictEqual(g.causeEdges[0].resolved, false);
  assert.strictEqual(g.causeEdges[0].sourceId, null);
  assert.strictEqual(g.causeEdges[0].targetId, null);
});

check('evidence basis is normalized without inventing missing evidence', () => {
  const g = Source.normalize(graph({ events: [
    { order: 1, chapter: '一', title: '起点', characters: ['甲'], quote: '起点原文', evidence: [{ quote: '起点原文', basis: '原文明确' }] },
    { order: 2, chapter: '二', title: '结果', characters: ['甲'], quote: '结果原文' }
  ] }));
  assert.strictEqual(g.events[0].evidence[0].basisCode, 'explicit');
  assert.deepStrictEqual(g.events[1].evidence, []);
});

console.log('NARRATIVE EVIDENCE CONTRACT PASSED');
