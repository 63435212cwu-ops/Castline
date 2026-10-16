'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Source = require('../js/atlas/atlas-source.js');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const window = {};
vm.runInNewContext(read('js/sky/sky-model.js'), {window});
const M = window.CLSkyModel;
const plain = v => JSON.parse(JSON.stringify(v));
function book(changes) {
  return Object.assign({characters: [], relations: [], storylines: [], events: [1, 2, 3].map(i => ({id: 'e' + i, order: i,
    chapter: '第' + i + '章', title: '事件' + i, quote: '原句' + i, characters: []}))}, changes);
}
function projection(g) { return M.build(g).narrative; }
function lifecycles(g) { return projection(g).foreshadowLifecycles; }
function stages(g) { return lifecycles(g).map(x => x.stage); }
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('an explicit resolved declaration yields a resolved lifecycle with both event anchors', () => {
  const g = book({clues: [{id: 'good', name: '锁与钥匙', summary: '钥匙在后文出现', seedEventId: 'e1', payoffEventId: 'e3',
    status: 'resolved', basis: 'explicit', seedQuote: '原句1', payoffQuote: '原句3'}]});
  const rec = lifecycles(g)[0];
  assert.equal(rec.stage, 'resolved'); assert.equal(rec.key, 'clue:good');
  assert.equal(rec.seedIndex, 0); assert.equal(rec.seedTitle, '事件1'); assert.equal(rec.seedChapter, '第1章');
  assert.equal(rec.payoffIndex, 2); assert.equal(rec.payoffTitle, '事件3'); assert.equal(rec.basisCode, 'explicit');
  assert.equal(rec.seedQuote, '原句1'); assert.equal(rec.payoffQuote, '原句3');
  const stats = projection(g).architecture.stats.foreshadow;
  assert.deepEqual(plain(stats), {total: 1, resolved: 1, pending: 0, broken: 0, conflicted: 0});
});
test('a seed without a declared payoff stays pending and never fabricates a payoff event', () => {
  const n = projection(book({clues: [{id: 'seed', seedEventId: 'e2', payoffEventId: '', status: 'seeded'}]}));
  const rec = n.foreshadowLifecycles[0];
  assert.equal(rec.stage, 'pending'); assert.equal(rec.seedIndex, 1);
  assert.equal(rec.payoffIndex, null); assert.equal(rec.payoffTitle, null);
  assert.equal(rec.declaredStatus, 'seeded'); assert.equal(n.architecture.stats.foreshadow.pending, 1);
});
test('an unknown payoff reference stays broken instead of borrowing an order match', () => {
  const n = projection(book({clues: [{id: 'bad', seedEventId: 'e1', payoffEventId: 'missing', status: 'resolved'}]}));
  const rec = n.foreshadowLifecycles[0];
  assert.equal(rec.stage, 'broken'); assert.equal(rec.seedIndex, 0); assert.equal(rec.payoffIndex, null);
  assert.ok(n.unresolved.some(x => x.kind === 'foreshadowPayoff' && x.reason === 'unresolved_or_conflicting'));
});
test('a backwards payoff order is broken, never silently resolved', () => {
  const n = projection(book({clues: [{id: 'backwards', seedEventId: 'e3', payoffEventId: 'e1', status: 'resolved'}]}));
  const rec = n.foreshadowLifecycles[0];
  assert.equal(rec.stage, 'broken'); assert.equal(rec.seedIndex, 2); assert.equal(rec.payoffIndex, null);
  assert.ok(n.unresolved.some(x => x.kind === 'foreshadowPayoff' && x.reason === 'invalid_payoff_order'));
});
test('an unresolved seed reference keeps its textual ref and joins the broken set', () => {
  const n = projection(book({clues: [{id: 'orphan', seedEventId: '9', payoffEventId: 'e3', status: 'resolved'}]}));
  const rec = n.foreshadowLifecycles[0];
  assert.equal(rec.stage, 'broken'); assert.equal(rec.seedIndex, null); assert.equal(rec.seedId, '9');
  assert.equal(n.architecture.stats.foreshadow.broken, 1);
});
test('duplicate declaration identities become conflicted, never an optimistic lifecycle', () => {
  const g = book({clues: [
    {id: 'same', name: '第一种声明', seedEventId: 'e1', payoffEventId: 'e2', status: 'resolved'},
    {id: 'same', name: '第二种声明', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'}
  ]});
  const n = projection(g), records = n.foreshadowLifecycles;
  assert.deepEqual(plain(records.map(x => x.stage)), ['conflicted', 'conflicted']);
  assert.equal(records[0].payoffIndex, null); assert.equal(records[1].payoffIndex, null);
  assert.ok(records.every(x => x.conflicted === true));
  assert.equal(n.unresolved.filter(x => x.reason === 'duplicate_identity').length, 1);
  assert.equal(n.architecture.stats.foreshadow.conflicted, 2); assert.equal(n.architecture.stats.foreshadow.resolved, 0);
});
test('event-owned foreshadow and payoff links join the same lifecycle set', () => {
  const g = book();
  g.events[0].foreshadow_of = [{targetId: 'e3', basis: 'explicit', name: '事件内伏笔'}];
  g.events[2].payoff_of = [{ref: 1, basis: 'inferred'}];
  assert.deepEqual(plain(stages(g)), ['resolved', 'resolved']);
  assert.equal(lifecycles(g)[0].ownerType, 'event'); assert.equal(lifecycles(g)[1].basisCode, 'inference');
});
test('storyline payoff pairs and vetoed declarations keep their declared status', () => {
  const n = projection(book({storylines: [{id: 'line1', name: '线', foreshadow_payoffs: [
    {foreshadowId: 'e1', payoffId: 'e2', basis: 'explicit'}]}],
    clues: [{id: 'veto', seedEventId: 'e1', payoffEventId: 'e2', status: 'resolved', referenceStatus: 'unresolved'}]}));
  const records = n.foreshadowLifecycles;
  assert.equal(records.length, 2);
  assert.equal(records[0].stage, 'resolved'); assert.equal(records[0].ownerType, 'storyline');
  assert.equal(records[1].stage, 'broken');
  assert.ok(n.unresolved.some(x => x.reason === 'declared_unresolved'));
});
test('a graph without foreshadow declarations produces no fabricated lifecycles', () => {
  const n = projection(book({causeEdges: [{fromEventId: 'e1', toEventId: 'e2', basis: 'explicit'}]}));
  assert.deepEqual(plain(n.foreshadowLifecycles), []);
  assert.deepEqual(plain(n.architecture.stats.foreshadow), {total: 0, resolved: 0, pending: 0, broken: 0, conflicted: 0});
});
test('empty books carry an honest empty lifecycle projection', () => {
  const n = projection(book());
  assert.deepEqual(plain(n.foreshadowLifecycles), []);
  assert.equal(n.architecture.stats.foreshadow.total, 0);
});

const readerWindow = {CLSkyModel: M, CLAtlasSource: Source, document: {addEventListener(){}}, addEventListener(){}};
const readerCode = read('js/sky/sky-deconstruction.js').replace('  g.CLSkyDeconstruction =', `
  g.readerTest = function(book, cfg) {
    graph = book; model = g.CLSkyModel.build(book); index = buildIndex();
    Object.keys(browse).forEach(function(key) { browse[key].page = 0; });
    browse.foreshadow.query = ''; browse.foreshadow.filter = 'all';
    Object.keys(cfg || {}).forEach(function(key) { Object.assign(browse[key], cfg[key]); });
    return {html: renderForeshadow()};
  };
  g.CLSkyDeconstruction =`);
vm.runInNewContext(readerCode, {window: readerWindow});

test('every stage renders its own badge with a clickable seed anchor to the evidence layer', () => {
  const g = book({clues: [
    {id: 'r', name: '已兑现的伏笔', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved', basis: 'explicit'},
    {id: 'p', name: '待回收的伏笔', seedEventId: 'e2', payoffEventId: '', status: 'seeded'},
    {id: 'b', name: '断裂的伏笔', seedEventId: 'e1', payoffEventId: 'missing', status: 'resolved'}
  ]});
  const html = readerWindow.readerTest(g).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 3);
  assert.ok(html.includes('已兑现') && html.includes('待回收') && html.includes('引用断裂'));
  assert.ok(html.includes('sd-fore-stage is-resolved') && html.includes('sd-fore-stage is-pending') && html.includes('sd-fore-stage is-broken'));
  assert.ok((html.match(/data-action="select-event"/g) || []).length >= 4);
  assert.ok(html.includes('data-record-id="r"') && html.includes('原文明确声明'));
  assert.ok(!html.includes('<script>'));
});
test('stage filters, search and pagination bound the lifecycle reading', () => {
  const g = book({clues: Array.from({length: 30}, (_, i) => ({id: 'clue' + i, name: '伏笔' + i,
    seedEventId: 'e1', payoffEventId: i < 10 ? 'e3' : '', status: i < 10 ? 'resolved' : 'seeded'}))});
  let html = readerWindow.readerTest(g).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 24);
  assert.ok(html.includes('1–24 / 30'));
  html = readerWindow.readerTest(g, {foreshadow: {page: 1}}).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 6);
  html = readerWindow.readerTest(g, {foreshadow: {filter: 'pending'}}).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 20);
  assert.ok(!html.includes('data-record-id="clue0"'));
  html = readerWindow.readerTest(g, {foreshadow: {query: '伏笔7', filter: 'resolved'}}).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 1);
  assert.ok(html.includes('伏笔7'));
});
test('conflicted declarations keep both cards without opening either record', () => {
  const g = book({clues: [
    {id: 'same', name: '冲突声明一', seedEventId: 'e1', payoffEventId: 'e2', status: 'resolved'},
    {id: 'same', name: '冲突声明二', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'}
  ]});
  const html = readerWindow.readerTest(g).html;
  assert.equal((html.match(/class="sd-causal-edge sd-fore-card\b/g) || []).length, 2);
  assert.ok((html.match(/身份冲突/g) || []).length >= 2);
  assert.ok(html.includes('声明 ID 不唯一，请在情节证据列表逐条查阅'));
  assert.ok(!html.includes('data-record-id="same"'));
  assert.ok(!html.includes('data-action="select-event" data-event-index="1" aria-label="阅读兑现'));
});
test('empty projections state that missing declarations prove nothing', () => {
  const withLayer = readerWindow.readerTest(book({clues: []})).html;
  assert.ok(withLayer.includes('没有声明不代表全书不存在伏笔'));
  assert.ok(!withLayer.includes('sd-fore-card'));
  const noLayer = readerWindow.readerTest(book()).html;
  assert.ok(noLayer.includes('无法据此判断全书有无伏笔结构'));
});
console.log('FORESHADOW LIFECYCLE ' + passed + '/' + passed);
