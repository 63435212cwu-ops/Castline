'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const P = require('../js/sky/sky-position-label.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('三种 kind 各有独立、可区分的读者可读状态', () => {
  const exact = P.of({ sourcePosition: { kind: 'exact_quote', start: 10, end: 20 } });
  const bounded = P.of({ sourcePosition: { kind: 'legacy_interval', start: 0, end: 99 } });
  const unknown = P.of({ sourcePosition: { kind: 'unresolved', reason: 'missing_trusted_primary_quote' } });
  const labels = [exact.label, bounded.label, unknown.label];
  assert.equal(new Set(labels).size, 3, '三种位置状态不能显示成同一句话：' + JSON.stringify(labels));
  assert.equal(exact.located, true);
  assert.equal(bounded.located, false, '旧区间的位置本身未经核验，不能算已定位');
  assert.equal(unknown.located, false);
  assert.ok(bounded.hint && unknown.hint && bounded.hint !== unknown.hint, '区间与未知的解释必须不同');
});

test('只有精确引句允许被当成确定时间点', () => {
  assert.equal(P.of({ sourcePosition: { kind: 'exact_quote' } }).placesAtExactTime, true);
  for (const kind of ['legacy_interval', 'unresolved', 'nonsense']) {
    assert.equal(P.of({ sourcePosition: { kind } }).placesAtExactTime, false, kind + ' 不得被当成确定时间点');
  }
});

test('来源冲突与普通未知分开（多来源无全局序必须单独一档）', () => {
  const conflict = P.of({ sourcePosition: { kind: 'unresolved', reason: 'multiple_sources_no_global_order' } });
  const plain = P.of({ sourcePosition: { kind: 'unresolved', reason: 'missing_trusted_primary_quote' } });
  assert.equal(conflict.code, 'conflicted');
  assert.equal(plain.code, 'unresolved');
  assert.notEqual(conflict.label, plain.label);
  assert.ok(conflict.reasonText.indexOf('多个来源') >= 0, '冲突必须给出可读理由，实际=' + conflict.reasonText);
  const byIds = P.of({ sourcePosition: { kind: 'unresolved', reason: '' } }, { sourceIds: ['a', 'b'] });
  assert.equal(byIds.code, 'conflicted', '多来源要能靠 sourceIds 判成冲突');
});

test('负例 · 没见过的 kind 落进「未提供」，不得被当作已确认', () => {
  const weird = P.of({ sourcePosition: { kind: 'brand_new_state_from_future' } });
  assert.equal(weird.code, 'unknown');
  assert.equal(weird.located, false);
  assert.equal(weird.placesAtExactTime, false);
  assert.ok(/未提供/.test(weird.label), '实际=' + weird.label);
});

test('负例 · 缺字段/非对象/空值不抛异常，也不冒充已核验', () => {
  for (const bad of [null, undefined, {}, { sourcePosition: null }, { sourcePosition: 'x' }, { sourcePosition: 7 }, 0, 'ev_1']) {
    const s = P.of(bad);
    assert.equal(s.located, false);
    assert.equal(s.code, 'unknown');
  }
});

test('标记用文本+符号，不靠颜色单独承载含义', () => {
  const marks = ['exact_quote', 'legacy_interval', 'unresolved'].map(k => P.badge({ sourcePosition: { kind: k } }));
  assert.equal(new Set(marks.map(m => m.text)).size, 3);
  marks.forEach(m => assert.ok(m.mark && m.text.indexOf(m.mark) === 0, '标记必须带符号：' + JSON.stringify(m)));
});

test('进度只叫定位进度，且文本里不得出现语义完成类措辞', () => {
  const pr = P.progress({ exact_quote: 1170, legacy_interval: 105, unresolved: 11 });
  assert.equal(pr.title, '定位进度');
  assert.equal(pr.isSemanticCompletion, false);
  assert.equal(pr.exact, 1170);
  assert.equal(pr.bounded, 105);
  assert.equal(pr.unknown, 11);
  assert.equal(pr.locatedPercent, Math.round(1170 / 1286 * 100));
  const claims = [pr.title, pr.summary, pr.detail].join(' | ');
  assert.doesNotMatch(claims, /语义完成|全书已理解|理解度/, '声称字段不得把定位写成语义完成：' + claims);
  assert.ok(/不等于语义完成/.test(pr.semanticNote), '必须显式声明它不是语义完成率');
});

test('真实数据：三个计数与适配器报告一致，且四档之和等于事件总数', () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const window = {};
  const ctx = vm.createContext({ window });
  vm.runInContext(fs.readFileSync('js/atlas/atlas-source.js', 'utf8'), ctx, { filename: 'atlas-source.js' });
  const Source = window.CLAtlasSource;
  for (const [key, want] of [
    ['fe42d01f3826fe8096f86614', { exact: 1170, bounded: 105, unresolved: 11 }],
    ['a065244455cfb2221bcda94a', { exact: 678, bounded: 115, unresolved: 5 }],
  ]) {
    const g = Source.normalize(JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8')));
    const counts = P.countEvents(g.events);
    assert.equal(counts.exact_quote, want.exact, key + ' exact');
    assert.equal(counts.legacy_interval, want.bounded, key + ' bounded');
    assert.equal(counts.unresolved + counts.conflicted, want.unresolved, key + ' unresolved');
    assert.equal(counts.total, g.events.length, key + ' 四档必须覆盖全部事件');
    const rep = g.meta.eventOrdering;
    assert.equal(counts.exact_quote, rep.exact, key + ' 显示层与适配器的 exact 必须一致');
    assert.equal(counts.legacy_interval, rep.bounded, key + ' 显示层与适配器的 bounded 必须一致');
  }
});

test('固定 C2 输入的两端锚点在读层 CPU resolver 中都匹配', () => {
  const ROOT = path.resolve(__dirname, '..');
  const input = JSON.parse(fs.readFileSync(path.join(ROOT, 'loop/state/out/input_rsi-source-span_20261011.json'), 'utf8'));
  const fakeDoc = { addEventListener() {}, getElementById() { return null; } };
  const window = { document: fakeDoc, CLSkyPositionLabel: P, addEventListener() {} };
  const context = vm.createContext({ window });
  let source = fs.readFileSync(path.join(ROOT, 'js/sky/sky-deconstruction.js'), 'utf8');
  source = source.replace('  g.CLSkyDeconstruction =', `
    g.positionDataForTest = function (book, at) { graph = book; return positionExplanationData(at); };
    g.positionMarkupForTest = function (book, at) { graph = book; return renderPositionExplanation(at); };
    g.CLSkyDeconstruction =`);
  vm.runInContext(source, context, { filename: 'sky-deconstruction.js' });
  const graph = { events: [input.bounds[0], input.event, input.bounds[1]] };
  const at = 1, d = window.positionDataForTest(graph, at);
  assert.equal(d.before.state, 'matched', 'before exact_quote anchor must match by its start boundary');
  assert.equal(d.after.state, 'matched', 'after exact_quote anchor must match by its start boundary');
  assert.equal(d.before.event.id, input.event.sourcePosition.beforeEventId);
  assert.equal(d.after.event.id, input.event.sourcePosition.afterEventId);
  assert.equal(d.before.event.sourcePosition.start, input.event.sourcePosition.start);
  assert.equal(d.after.event.sourcePosition.start, input.event.sourcePosition.end);
  const entityGraph = JSON.parse(JSON.stringify(graph));
  entityGraph.events[0].entityId = input.bounds[0].id; delete entityGraph.events[0].id;
  assert.equal(window.positionDataForTest(entityGraph, at).before.state, 'matched', 'entityId alone is a stable identity');
  entityGraph.events[0].id = input.bounds[0].id; entityGraph.events[0].entityId = 'conflicting-stable-id';
  assert.notEqual(window.positionDataForTest(entityGraph, at).before.state, 'matched', 'conflicting id/entityId must not match');
  const wrongKind = JSON.parse(JSON.stringify(graph));
  wrongKind.events[0].sourcePosition.kind = 'legacy_interval';
  assert.equal(window.positionDataForTest(wrongKind, at).before.state, 'unavailable', 'a positioned but non-exact record is not a trusted event anchor');
  const fractional = JSON.parse(JSON.stringify(graph));
  fractional.events[0].sourcePosition.start += 0.5;
  assert.equal(window.positionDataForTest(fractional, at).before.state, 'unavailable', 'fractional codepoint offsets are not trusted anchors');
  const readingCSS = fs.readFileSync(path.join(ROOT, 'css/sky-reading.css'), 'utf8');
  input.event.sourcePosition.beforeEventId = null;
  const openMarkup = window.positionMarkupForTest(graph, at);
  assert.match(openMarkup, /sd-position-span is-open-before/);
  assert.match(openMarkup, /只有一侧找到可核验的定位边界/);
  assert.match(openMarkup, /前界未提供/);
  assert.match(openMarkup, /class="sd-detail-action sd-position-explain-action"/);
  assert.doesNotMatch(openMarkup, /data-position-side="before"/);
  assert.match(readingCSS, /is-open-before \.sd-position-bracket::before[\s\S]*display: none/);
  assert.match(readingCSS, /\.sd-position-explain-action, \.sd-position-return \{ min-height: 44px; \}/);
});

console.log('SKY POSITION LABEL ' + passed + '/' + passed);
