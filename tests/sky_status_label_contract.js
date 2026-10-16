'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Source = require('../js/atlas/atlas-source.js');
const read = name => fs.readFileSync(require('node:path').join(__dirname, '..', name), 'utf8');
const window = {};
vm.runInNewContext(read('js/sky/sky-model.js'), {window});
const Model = window.CLSkyModel;
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
function book(changes) {
  return Object.assign({characters: [{id: 'p1', name: '甲'}], relations: [], storylines: [],
    events: [1, 2, 3].map(n => ({id: 'e' + n, order: n, chapter: '第' + n + '章', title: '事件' + n, characters: ['甲']}))}, changes);
}
const readerWindow = {CLSkyModel: Model, CLAtlasSource: Source, document: {addEventListener() {}}, addEventListener() {}};
vm.runInNewContext(read('js/sky/sky-deconstruction.js').replace('  g.CLSkyStatusText =', `
  g.readForTest = function(book, config) {
    graph = book; model = g.CLSkyModel.build(book); index = buildIndex();
    Object.keys(browse).forEach(function(key) { browse[key].page = 0; if (browse[key].query != null) browse[key].query = ''; if (browse[key].filter != null) browse[key].filter = 'all'; });
    browse.mechanics = {query: '', filter: 'all', layer: 'clues', page: 0, selected: null};
    browse.mechanicQuotes = {page: 0}; browse.references = {page: 0}; browse.attributes = {page: 0};
    browse.states = {query: '', filter: 'all', kind: 'all', page: 0, selected: null, eventIndex: null, characterId: null};
    browse.stateQuotes = {page: 0}; browse.stateAttributes = {page: 0};
    Object.keys(config || {}).forEach(function(key) { Object.assign(browse[key], config[key]); });
    return {foreshadow: renderForeshadow(), causal: renderCausal(), states: renderStates(), mechanics: renderMechanics()};
  };
  g.CLSkyStatusText =`), {window: readerWindow});
const {label, hint} = readerWindow.CLSkyStatusText;

test('the single-point map covers every known code in every domain', () => {
  assert.equal(label('foreshadow', 'resolved'), '已兑现');
  assert.equal(label('foreshadow', 'pending'), '待回收');
  assert.equal(label('foreshadow', 'broken'), '引用断裂');
  assert.equal(label('foreshadow', 'conflicted'), '身份冲突');
  assert.equal(label('declared', 'resolved'), '已兑现声明');
  assert.equal(label('declared', 'pending'), '待回收声明');
  assert.equal(label('declared', 'seeded'), '已埋设声明');
  assert.equal(label('declared', 'unresolved'), '未解析声明');
  for (const code of ['active', 'completed', 'failed', 'abandoned', 'blocked', 'unknown', 'seeded', 'resolved', 'uncertain', 'linked', 'unlinked'])
    assert.ok(!label('mechanic', code).startsWith('未识别状态'), 'mechanic ' + code);
  for (const code of ['known', 'unknown', 'unaware', 'not_known', 'does_not_know', 'belief', 'suspected', 'unspecified'])
    assert.ok(!label('knowledge', code).startsWith('未识别状态'), 'knowledge ' + code);
  for (const code of ['declared_unresolved', 'self_reference', 'unresolved_or_conflicting', 'invalid_payoff_order', 'unresolved_endpoint', 'duplicate_identity'])
    assert.ok(!label('causalReason', code).startsWith('未识别状态'), 'causalReason ' + code);
});
test('known declared codes carry a short meaning phrase from the same map', () => {
  assert.equal(hint('declared', 'resolved'), '来源声明此伏笔已兑现');
  assert.equal(hint('declared', 'seeded'), '来源仅声明埋设，未提供兑现');
});
test('unknown codes fall back to the raw code marked as 原文, never swallowed or guessed', () => {
  assert.equal(label('declared', 'quantum_lock'), '未识别状态（原文 quantum_lock）');
  assert.equal(label('foreshadow', 'half_baked'), '未识别状态（原文 half_baked）');
  assert.equal(label('knowledge', 'telepathy'), '未识别状态（原文 telepathy）');
  assert.equal(label('mechanic', 'rebooted'), '未识别状态（原文 rebooted）');
  assert.equal(label('declared', null), '状态未提供');
  assert.equal(label('declared', ''), '状态未提供');
  assert.equal(hint('declared', 'quantum_lock'), '');
});
test('foreshadow cards localize declaredStatus and keep the raw code in data attributes', () => {
  const html = readerWindow.readForTest(book({clues: [{id: 'c1', name: '锁与钥匙', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'}]})).foreshadow;
  assert.ok(html.includes('声明状态：')); assert.ok(html.includes('已兑现声明（来源声明此伏笔已兑现）'));
  assert.ok(!html.includes('声明状态：resolved'));
  assert.ok(html.includes('data-status-code="resolved"'));
  assert.ok(html.includes('data-stage="resolved"'));
});
test('every declared-status code in the map renders its own Chinese copy', () => {
  const g = book({clues: [
    {id: 'r', name: '已兑现伏笔', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'},
    {id: 's', name: '仅埋设伏笔', seedEventId: 'e2', payoffEventId: '', status: 'seeded'},
    {id: 'p', name: '待回收伏笔', seedEventId: 'e2', payoffEventId: '', status: 'pending'},
    {id: 'u', name: '未解析伏笔', seedEventId: 'e2', payoffEventId: '', status: 'unresolved'}
  ]});
  const html = readerWindow.readForTest(g).foreshadow;
  assert.ok(html.includes('已兑现声明（来源声明此伏笔已兑现）'));
  assert.ok(html.includes('已埋设声明（来源仅声明埋设，未提供兑现）'));
  assert.ok(html.includes('待回收声明（来源声明兑现留待后文）'));
  assert.ok(html.includes('未解析声明（来源标记此伏笔未解析）'));
  assert.ok(html.includes('data-status-code="seeded"') && html.includes('data-status-code="pending"') && html.includes('data-status-code="unresolved"'));
});
test('an unheard-of declared status renders as 未识别状态 with the original code preserved', () => {
  const html = readerWindow.readForTest(book({clues: [{id: 'x', name: '异码伏笔', seedEventId: 'e1', payoffEventId: 'e3', status: 'quantum_lock'}]})).foreshadow;
  assert.ok(html.includes('未识别状态（原文 quantum_lock）'));
  assert.ok(!html.includes('声明状态：quantum_lock'));
  assert.ok(html.includes('data-status-code="quantum_lock"'));
});
test('stage badges, step text and filter options all go through the map with raw-code data attributes', () => {
  const g = book({clues: [{id: 'p', name: '待回收伏笔', seedEventId: 'e2', payoffEventId: '', status: 'seeded'}]});
  const html = readerWindow.readForTest(g).foreshadow;
  assert.ok(html.includes('<em class="sd-fore-stage is-pending" data-stage="pending">待回收</em>'));
  assert.ok(html.includes('已埋伏') && html.includes('<i class="is-waiting">待回收</i>'));
  assert.ok(html.includes('<option value="pending"') && html.includes('>待回收</option>'));
});
test('causal unresolved reasons are localized with the raw reason only in the fallback path', () => {
  const g = book({clues: [{id: 'bad', seedEventId: 'e1', payoffEventId: 'missing', status: 'resolved'}]});
  const html = readerWindow.readForTest(g).causal;
  assert.ok(html.includes('引用缺失、重复或相互冲突') && !html.includes('<b>unresolved_or_conflicting</b>'));
});
test('mechanics-layer clue statuses are localized instead of showing source English', () => {
  const g = book({clues: [{id: 'c1', name: '锁与钥匙', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'}]});
  const html = readerWindow.readForTest(g).mechanics;
  assert.ok(html.includes('已兑现声明'));
  assert.ok(!html.includes('>resolved</') && !html.includes('兑现状态</span><p class="sd-fact-text">resolved'));
});
test('knowledge statuses render Chinese copy; unheard-of values stay visible as 原文', () => {
  const g = book();
  g.characters[0].knowledge = [{text: '未登记状态', status: 'telepathy', eventId: 'e2'}, {text: '获知姓名', status: 'belief', eventId: 'e2'}];
  const html = readerWindow.readForTest(g).states + readerWindow.readForTest(g, {states: {selected: 'character:0:knowledge:1'}}).states;
  assert.ok(html.includes('人物信念声明'));
  assert.ok(html.includes('未识别状态（原文 telepathy）'));
  assert.ok(!html.includes('知情状态</span><p class="sd-fact-text">belief'));
});
test('sky-search distributes entity statuses through the same mapping when available', () => {
  const searchWindow = {CLSkyStatusText: readerWindow.CLSkyStatusText, document: {getElementById() { return null; }, addEventListener() {}}, addEventListener() {}, setTimeout() {}};
  vm.runInNewContext(read('js/sky/sky-search.js'), {window: searchWindow});
  const rows = searchWindow.CLSkySearch.index(book({clues: [{id: 'c1', name: '锁与钥匙', seedEventId: 'e1', payoffEventId: 'e3', status: 'resolved'}]}));
  const clue = rows.filter(r => r.type === 'clue')[0];
  assert.ok(clue.meta.includes('已兑现声明') && !clue.meta.includes('resolved'));
});
console.log('STATUS LABEL ' + passed + '/' + passed);
