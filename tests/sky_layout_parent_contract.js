'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '..');
const window = {};
const context = vm.createContext({ window });
for (const file of ['js/tree/storylines.js', 'js/sky/sky-model.js']) {
  vm.runInContext(fs.readFileSync(path.join(ROOT, file), 'utf8'), context, { filename: file });
}
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
function fixture() {
  return {
    characters: [{ name: '甲', importance: 90 }], relations: [],
    events: Array.from({ length: 8 }, (_, i) => ({ id: 'e' + (i + 1), order: i + 1,
      chapter: '第' + (i + 1) + '章', title: '事件' + (i + 1), characters: ['甲'] })),
    storylines: [
      { id: 'early', kind: '主线', name: '早期机械分段', events: [1, 2], derived: true },
      { id: 'late', kind: '主线', name: '后续机械分段', events: [3, 4, 5, 6, 7, 8], derived: true, handoff_from: 'early' },
      { id: 'reviewed', kind: '支线', name: '独立已审阅事件线', events: [5, 6], parent: 'early', attach_order: 2,
        provenance: 'assistant-reviewed-source', claimVerified: false, parentRelation: '来源中的父线说明' }
    ],
    meta: { storylines: { src: 'mixed' } }
  };
}
function build(graph) {
  const tree = window.CLStory.analyze(graph);
  assert.equal(tree.ok, true);
  return { tree, sky: window.CLSkyModel.build(graph, tree) };
}
function thread(tree, id = 'reviewed') { return tree.threads.find(t => t.sourceId === id); }
function line(sky, id = 'reviewed') { return sky.lines.find(t => t.sourceId === id); }

test('a legal declared parent stays confirmed, including a mechanically derived parent', () => {
  const graph = fixture();
  graph.storylines.push({ id: 'child', kind: '末梢', name: '有来源的子线', events: [6, 7], parent: 'reviewed', attach_order: 5 });
  const before = JSON.stringify(graph), { tree, sky } = build(graph), branch = thread(tree);
  assert.equal(branch.topologyStatus, 'confirmed');
  assert.equal(branch.anchored, false);
  assert.equal(branch.parent, thread(tree, 'early').id);
  assert.equal(branch.attach, 1);
  assert.equal(thread(tree, 'child').parent, branch.id);
  assert.equal(thread(tree, 'child').topologyStatus, 'confirmed');
  assert.equal(thread(tree, 'child').kind, 'twig');
  assert.equal(line(sky).topologyStatus, 'confirmed');
  assert.equal(line(sky).anchored, false);
  assert.equal(line(sky).mainId, thread(tree, 'early').id);
  assert.equal(sky.mains.find(t => t.sourceId === 'early').derived, true);
  assert.equal(JSON.stringify(graph), before);
});

test('layout declarations stay pending and preserve the original parent while visually anchoring nearby', () => {
  const graph = fixture(), source = graph.storylines[2];
  source.parentBasis = 'layout';
  source.parentRelation = '仅用于旧分段布局，剧情父线待确认';
  const before = JSON.stringify(graph), { tree, sky } = build(graph), branch = thread(tree), projected = line(sky);
  assert.equal(branch.topologyStatus, 'pending');
  assert.equal(branch.anchored, true);
  assert.equal(branch.declaredParent, 'early');
  assert.equal(branch.declaredAttach, '2');
  assert.equal(branch.parentBasis, 'layout');
  assert.equal(branch.parentRelation, source.parentRelation);
  assert.match(branch.pendingReason, /仅为布局挂点.*剧情父线尚未确认/);
  assert.equal(branch.parent, thread(tree, 'late').id, 'layout may choose a nearby main independently of the declaration');
  assert.equal(branch.attach, 4);
  const unresolved = tree.unresolved.find(t => t.sourceId === 'reviewed');
  assert.equal(unresolved.parent, 'early');
  assert.equal(unresolved.attach, '2');
  assert.equal(unresolved.reasons, branch.pendingReason);
  for (const key of ['sourceId', 'parent', 'declaredParent', 'declaredAttach', 'parentBasis', 'parentRelation', 'topologyStatus', 'anchored', 'pendingReason']) {
    assert.equal(projected[key], branch[key], key + ' survives the sky projection');
  }
  assert.equal(projected.mainId, thread(tree, 'late').id);
  assert.equal(projected.provenance, 'assistant-reviewed-source', 'review of the line does not certify its parent edge');
  assert.equal(projected.derived, false);
  assert.deepEqual(Array.from(projected.events), [4, 5]);
  assert.equal(JSON.stringify(graph), before);
});

test('a valid child cannot turn an unconfirmed layout ancestry into confirmed topology', () => {
  const graph = fixture(); graph.storylines[2].parentBasis = 'layout';
  graph.storylines.push({ id: 'child', kind: '末梢', name: '父线待确认的子线', events: [6, 7], parent: 'reviewed', attach_order: 5 });
  const { tree, sky } = build(graph), child = thread(tree, 'child');
  assert.equal(child.topologyStatus, 'pending');
  assert.equal(child.anchored, true);
  assert.equal(child.declaredParent, 'reviewed');
  assert.match(child.pendingReason, /父线未确认/);
  assert.equal(line(sky, 'child').topologyStatus, 'pending');
});

test('without a main line a layout declaration remains pending without inventing an anchor', () => {
  const graph = fixture(); graph.storylines = [graph.storylines[2]];
  graph.storylines[0].parentBasis = 'layout';
  const { tree, sky } = build(graph), branch = thread(tree), projected = line(sky);
  assert.equal(branch.topologyStatus, 'pending');
  assert.equal(branch.anchored, false);
  assert.equal(branch.parent, null);
  assert.equal(branch.attach, null);
  assert.equal(branch.declaredParent, 'early');
  assert.match(branch.pendingReason, /布局/);
  assert.equal(projected.parent, null);
  assert.equal(projected.mainId, null);
  assert.equal(projected.anchored, false);
  assert.equal(projected.topologyStatus, 'pending');
});

test('ordinary invalid parent declarations still retain their original pending reasons', () => {
  const graph = fixture(); graph.storylines[2].attach_order = 3;
  const { tree, sky } = build(graph), branch = thread(tree);
  assert.equal(branch.topologyStatus, 'pending');
  assert.equal(branch.anchored, true);
  assert.match(branch.pendingReason, /attach 点不属于父线/);
  assert.doesNotMatch(branch.pendingReason, /仅为布局/);
  assert.equal(line(sky).pendingReason, branch.pendingReason);
});

test('changing only parentBasis or parentRelation invalidates an already cached tree', () => {
  const graph = fixture(), first = build(graph).tree;
  assert.equal(thread(first).topologyStatus, 'confirmed');
  graph.storylines[2].parentBasis = 'layout';
  const second = build(graph).tree;
  assert.notEqual(second.fp, first.fp);
  assert.equal(thread(second).topologyStatus, 'pending');
  graph.storylines[2].parentRelation = '修订后的布局说明';
  const third = build(graph).tree;
  assert.notEqual(third.fp, second.fp);
  assert.equal(thread(third).parentRelation, '修订后的布局说明');
  delete graph.storylines[2].parentBasis;
  const restored = build(graph).tree;
  assert.equal(thread(restored).topologyStatus, 'confirmed');
  assert.equal(thread(restored).anchored, false);
});

console.log('SKY LAYOUT PARENT ' + passed + '/' + passed);
