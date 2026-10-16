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
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
test('chronology alone cannot create a causal edge or payoff', () => {
  const n = projection(book()); assert.equal(n.causalEdges.length, 0); assert.equal(n.foreshadowPayoffs.length, 0);
});
test('producer IDs resolve unique event identities and retain original declaration evidence', () => {
  const g = book({causeEdges: [{id: 'c', fromEventId: 'e1', toEventId: 'e3', basis: 'inferred',
    description: '只是推断', quote: '原句1', claimVerified: false}]});
  const before = JSON.stringify(g), n = projection(g), edge = n.architecture.edges[0];
  assert.equal(n.causalEdges.length, 1); assert.equal(edge.source, 0); assert.equal(edge.target, 2);
  assert.equal(edge.description, '只是推断'); assert.equal(edge.quote, '原句1'); assert.equal(edge.basisCode, 'inference');
  assert.equal(edge.claimVerified, false); assert.equal(JSON.stringify(g), before);
});
test('typed stable IDs never fall back to matching order numbers', () => {
  const g = book({causeEdges: [{fromEventId: '1', toEventId: 'e2'}, {sourceId: '1', targetId: 'e3'}]});
  assert.equal(projection(g).causalEdges.length, 0); assert.equal(projection(g).unresolved.length, 2);
});
test('duplicate IDs stay ambiguous even when an order offers another match', () => {
  const g = book({causeEdges: [{from: '1', to: 'e3'}]});
  g.events[0].id = '1'; g.events[1].id = '1';
  assert.equal(projection(g).causalEdges.length, 0); assert.equal(projection(g).unresolved.length, 1);
});
test('a unique legacy order still resolves and preserves the event index', () => {
  const g = book({causeEdges: [{from: 1, to: 3, basis: 'explicit'}]});
  g.events.forEach(e => {delete e.id; e.rawOrder = e.order;});
  const edge = projection(g).architecture.edges[0];
  assert.equal(edge.source, 0); assert.equal(edge.target, 2);
  g.events[1].order = 1; assert.equal(projection(g).causalEdges.length, 0);
});
test('every supplied endpoint alias must agree, including title and quote', () => {
  for (const extra of [{sourceId: 'e2'}, {from: 2}, {declaredSourceId: 'missing'}, {fromTitle: '事件2'}, {fromQuote: '原句2'}]) {
    const g = book({causeEdges: [Object.assign({fromEventId: 'e1', toEventId: 'e3'}, extra)]});
    assert.equal(projection(g).causalEdges.length, 0, JSON.stringify(extra));
    assert.equal(projection(g).unresolved.length, 1);
  }
});
test('an explicit unresolved marker vetoes otherwise valid endpoints', () => {
  for (const extra of [{resolved: false}, {referenceStatus: 'unresolved'}, {referenceStatus: 'unresolved_or_conflicting'}]) {
    const g = book({causeEdges: [Object.assign({sourceId: 'e1', targetId: 'e2'}, extra)]});
    assert.equal(projection(g).causalEdges.length, 0);
    assert.equal(projection(g).unresolved[0].reason, 'declared_unresolved');
  }
});
test('unknown and invalid reference statuses, plus self edges, stay out of the architecture', () => {
  const g = book({causeEdges: [
    {sourceId: 'e1', targetId: 'e2', referenceStatus: 'unknown'},
    {sourceId: 'e1', targetId: 'e2', referenceStatus: 'invalid'},
    {sourceId: 'e2', targetId: 'e2'}
  ]});
  const n = projection(g); assert.equal(n.causalEdges.length, 0); assert.equal(n.unresolved.length, 3);
  assert.ok(n.unresolved.some(x => x.reason === 'self_reference'));
});
test('event-owned links honor stable aliases, legacy refs, and resolution vetoes', () => {
  const g = book();
  g.events[0].consequences = [{targetId: 'e2', basis: 'explicit'}, {targetId: 'e3', resolved: false}];
  g.events[2].causes = [{ref: 2, basis: 'inferred'}];
  const n = projection(g);
  assert.equal(n.causalEdges.length, 2); assert.deepEqual(plain(n.architecture.roots), [0]); assert.deepEqual(plain(n.architecture.leaves), [2]);
  assert.equal(n.unresolved.length, 1);
  g.events[2].causes[0].eventId = 'e1'; assert.equal(projection(g).causalEdges.length, 1);
});
test('normalized server projections retain valid references and rejected declarations', () => {
  const g = Source.normalize(book({causeEdges: [
    {id: 'good', fromEventId: 'e1', toEventId: 'e3', basis: 'explicit'},
    {id: 'bad', sourceId: 'e1', fromEventId: 'e2', toEventId: 'e3'}]}));
  const n = projection(g); assert.equal(n.causalEdges.length, 1); assert.equal(n.unresolved.length, 1);
});
test('multiple claims on one direction remain inspectable without inflating node degree', () => {
  const n = projection(book({causeEdges: [
    {id: 'c1', fromEventId: 'e1', toEventId: 'e2', basis: 'explicit', quote: '第一种声明'},
    {id: 'c2', fromEventId: 'e1', toEventId: 'e2', basis: 'inferred', quote: '另一个声明'}]}));
  assert.equal(n.causalEdges.length, 2); assert.equal(n.architecture.nodes[0].out, 1); assert.equal(n.architecture.stats.causalPairs, 1);
});
test('clues expose actual payoff links, pending seeds and broken references separately', () => {
  const n = projection(book({clues: [
    {id: 'resolved', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved', basis: 'explicit'},
    {id: 'seed', seedEventId: 'e2', payoffEventId: '', status: 'seeded'},
    {id: 'bad', seedEventId: '1', payoffEventId: 'e3', status: 'resolved'},
    {id: 'backwards', seedEventId: 'e3', payoffEventId: 'e1', status: 'resolved'}]}));
  assert.equal(n.foreshadowPayoffs.length, 4); assert.equal(n.foreshadowPayoffs[0].resolved, true);
  assert.equal(n.foreshadowPayoffs[1].pending, true); assert.equal(n.foreshadowPayoffs[1].resolved, false);
  assert.equal(n.architecture.stats.foreshadowEdges, 1); assert.equal(n.unresolved.length, 2);
  assert.equal(n.foreshadowPayoffs[2].source, null); assert.equal(n.foreshadowPayoffs[3].resolved, false);
});
const readerWindow = {CLSkyModel: M, CLAtlasSource: Source, document: {addEventListener(){}}, addEventListener(){}};
const readerCode = read('js/sky/sky-deconstruction.js').replace('  g.CLSkyDeconstruction =', `
  g.readerTest = function(book, cfg) {
    graph = book; model = g.CLSkyModel.build(book); index = buildIndex();
    Object.keys(browse).forEach(function(key) { browse[key].page = 0; });
    browse.causal.query = ''; browse.causal.filter = 'all';
    Object.keys(cfg || {}).forEach(function(key) { Object.assign(browse[key], cfg[key]); });
    return {html: renderCausal(), reference: referenceRow({label:'任务相关事件',value:'1'})};
  };
  g.CLSkyDeconstruction =`);
vm.runInNewContext(readerCode, {window: readerWindow});
test('causal reading is paginated with every final claim reachable', () => {
  const g = book({causeEdges: Array.from({length: 55}, (_, i) => ({id: 'c'+i, fromEventId:'e1',toEventId:'e3',description:'因果声明'+i,basis:'explicit'}))});
  let result = readerWindow.readerTest(g); assert.equal((result.html.match(/class="sd-causal-edge\b/g)||[]).length, 24);
  assert.ok(result.html.includes('1–24 / 55')); assert.ok(result.reference.includes('未提供可确认的事件引用'));
  result = readerWindow.readerTest(g, {causal:{page:2}}); assert.equal((result.html.match(/class="sd-causal-edge\b/g)||[]).length, 7);
  assert.ok(result.html.includes('因果声明54'));
});
test('basis filters and full evidence search preserve inference labels and escape quotations', () => {
  const g = book({causeEdges: [
    {id:'c1',fromEventId:'e1',toEventId:'e2',basis:'explicit',description:'明示原因'},
    {id:'c2',fromEventId:'e1',toEventId:'e3',basis:'inferred',description:'推导原因',quote:'检索<script>原句</script>'}]});
  const html = readerWindow.readerTest(g,{causal:{filter:'inference',query:'检索'}}).html;
  assert.equal((html.match(/class="sd-causal-edge\b/g)||[]).length, 1); assert.ok(html.includes('事件推导 · 判断待核'));
  assert.ok(html.includes('&lt;script&gt;')); assert.ok(!html.includes('<script>')); assert.ok(html.includes('data-record-id="c2"'));
  assert.ok(html.includes('data-action="select-event"'));
});
test('payoffs and unresolved references are also bounded and never disappear at eight rows', () => {
  const g = book({clues:Array.from({length:55}, (_,i)=>({id:'clue'+i,name:'线索'+i,seedEventId:'missing'+i,payoffEventId:'e3',status:'resolved'}))});
  let html = readerWindow.readerTest(g).html;
  assert.ok(html.includes('data-page-number="payoffs"')); assert.ok(html.includes('data-page-number="unresolved"'));
  assert.ok(!html.includes('data-record-id="clue54"'));
  html = readerWindow.readerTest(g,{payoffs:{page:2},unresolved:{page:2}}).html;
  assert.ok(html.includes('线索54')); assert.ok(html.includes('missing54')); assert.ok(html.includes('data-record-id="clue54"'));
});
test('duplicate declaration IDs cannot open an arbitrary first record', () => {
  const g = book({causeEdges: [
    {id: 'same', sourceId: 'e1', targetId: 'e2'},
    {id: 'same', sourceId: 'e1', targetId: 'e3'}
  ]});
  const html = readerWindow.readerTest(g).html;
  assert.ok(html.includes('声明 ID 不唯一，请在情节证据列表逐条查阅'));
  assert.ok(!html.includes('data-record-id="same"'));
});
console.log('CAUSAL ARCHITECTURE ' + passed + '/' + passed);
