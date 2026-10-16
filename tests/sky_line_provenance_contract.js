'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const L = require('../js/sky/sky-line-provenance.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('四个来源档位各有独立名称与解释，互不同义', () => {
  const codes = ['mechanical', 'derived', 'reviewed', 'unknown'];
  const labels = codes.map(c => L.SOURCES[c].zh);
  assert.equal(new Set(labels).size, codes.length, '名称不得重复：' + JSON.stringify(labels));
  codes.forEach(c => assert.ok(L.SOURCES[c].hint.length > 8, c + ' 必须带解释'));
  assert.ok(/只当导航|不计故事结构/.test(L.SOURCES.mechanical.hint), L.SOURCES.mechanical.hint);
});

test('负例 · 缺来源字段不得默认成「已审阅」', () => {
  for (const line of [{}, { name: '某线' }, null, undefined, { events: [1, 2, 3] }]) {
    const s = L.of(line, {});
    assert.notEqual(s.code, 'reviewed', '缺来源不得判已审阅：' + JSON.stringify(line));
    assert.equal(s.countsAsStructure, false);
  }
});

test('负例 · 机械线不得被算作故事结构（只能导航）', () => {
  const s = L.of({ events: [1, 2, 3], src: 'local-completion' }, {});
  assert.equal(s.code, 'mechanical');
  assert.equal(s.countsAsStructure, false, '机械线不得计入故事结构');
  assert.equal(s.navigableOnly, true, '机械线仍可导航');
  const r = L.of({ events: [1], provenance: 'assistant-reviewed-source' }, {});
  assert.equal(r.code, 'reviewed');
  assert.equal(r.countsAsStructure, true, '审阅线才算结构');
});

test('负例 · 模型给机械线写了 provenance=derived 时，仍必须判机械（优先级）', () => {
  const line = { events: new Array(374).fill(0), provenance: 'derived' };
  const s = L.of(line, { src: 'local-completion' });
  assert.equal(s.code, 'mechanical', 'local-completion 必须压过 provenance=derived，实际=' + s.code);
  assert.equal(s.countsAsStructure, false);
  const r = L.of({ events: [1], provenance: 'derived' }, { src: 'assistant-reviewed-source' });
  assert.equal(r.code, 'reviewed', '图谱审阅来源必须压过 line.provenance，实际=' + r.code);
});

test('负例 · 段大小不等的真实线不得被误判成机械等分', () => {
  const real = [{ events: new Array(8).fill(0) }, { events: new Array(21).fill(0) },
                { events: new Array(47).fill(0) }, { events: new Array(26).fill(0) },
                { events: new Array(6).fill(0) }];
  const m = L.looksMechanical(real, { src: 'assistant-reviewed-source' });
  assert.equal(m.mechanical, false, '不均匀的线不得判机械');
  assert.equal(m.equalSplit, false);
});

test('负例 · 段大小相等但无 src 声明时，仍须靠极差识别', () => {
  const even = [374, 374, 374, 374, 374, 374, 374, 372].map(n => ({ events: new Array(n).fill(0) }));
  const m = L.looksMechanical(even, {});
  assert.equal(m.equalSplit, true, '极差 ≤5% 必须判等分');
  assert.equal(m.mechanical, true, '没有 src 也要能识别机械等分');
  assert.equal(m.declared, false, '如实标明「图谱没有自述」');
});

test('负例 · 非数组/缺字段不抛异常', () => {
  for (const bad of [null, undefined, 0, 'x', {}, { events: 'abc' }, { eventIds: null }]) {
    const t = L.tally(bad, null);
    assert.ok(t && typeof t.total === 'number', '必须返回结构化结果');
    assert.equal(L.sizeOf(bad) >= 0, true);
  }
});

test('sizeOf 兼容 events 与 eventIds 两种真实形态', () => {
  assert.equal(L.sizeOf({ events: [1, 2, 3] }), 3);
  assert.equal(L.sizeOf({ eventIds: ['a', 'b'] }), 2);
  assert.equal(L.sizeOf({ events: [], eventIds: [1] }), 1, 'events 为空时回退 eventIds');
  assert.equal(L.sizeOf({}), 0);
});

test('汇总只叫来源计数，不得自称结构质量分', () => {
  const t = L.tally([{ events: [1], src: 'assistant-reviewed-source' },
                     { events: [2], src: 'local-completion' }], {});
  assert.equal(t.title, '剧情线来源');
  assert.equal(t.isStructureScore, false);
  assert.equal(t.total, 2);
  assert.equal(t.countsAsStructure, 1);
  assert.ok(/不计故事结构/.test(t.note), t.note);
});

test('真实数据：大奉 8 条线必须被识别为机械等分（极差 ≤5% 且图谱自述）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const lines = g.storylines || [];
  assert.equal(lines.length, 8, '夹具线数');
  const meta = (g.meta || {}).storylines || {};
  assert.equal(meta.src, 'local-completion', '夹具来源');
  const t = L.tally(lines, meta);
  assert.equal(t.declaredByGraph, true);
  assert.equal(t.equalSplit, true, '段大小极差必须 ≤5%');
  assert.equal(t.countsAsStructure, 0, '机械线一条都不算故事结构');
  assert.equal(t.byCode.mechanical, 8);
  assert.deepEqual(t.sizes, [374, 374, 374, 374, 374, 374, 374, 372]);
  assert.ok(/只能当导航/.test(t.summary), t.summary);
  assert.equal(t.withoutBasis, 8, '八条线都没写为何独立');
  console.log('     ' + t.summary);
});

test('真实数据：三国 34 条线来自审阅，不得被判成机械等分', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8'));
  const lines = g.storylines || [];
  const meta = (g.meta || {}).storylines || {};
  const t = L.tally(lines, meta);
  assert.equal(meta.src, 'assistant-reviewed-source');
  assert.equal(t.equalSplit, false, '三国段大小不均，不得判机械等分');
  assert.equal(t.countsAsStructure, lines.length, '审阅线全部计入结构');
  assert.ok(t.byCode.reviewed === lines.length, 'byCode=' + JSON.stringify(t.byCode));
  console.log('     三国 ' + lines.length + ' 条：' + t.summary);
});

test('真实数据：西游 10 条线同样来自审阅，且段大小极不均', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/a065244455cfb2221bcda94a.json', 'utf8'));
  const lines = g.storylines || [];
  const meta = (g.meta || {}).storylines || {};
  const t = L.tally(lines, meta);
  assert.equal(t.equalSplit, false);
  assert.ok(t.spread > 1, '西游极差应远大于 5%，实际=' + t.spread);
  assert.equal(t.byCode.reviewed, lines.length);
  console.log('     西游 ' + lines.length + ' 条：spread=' + t.spread);
});

console.log('SKY LINE PROVENANCE ' + passed + '/' + passed);
