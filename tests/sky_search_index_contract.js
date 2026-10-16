'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const SI = require('../js/sky/sky-search-index.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('五类可搜对象（人物/别名/事件/任务/线路）各有独立名称与解释', () => {
  const five = ['character', 'alias', 'event', 'task', 'storyline'];
  const labels = five.map(k => SI.TYPES[k].zh);
  assert.equal(new Set(labels).size, 5, '五类名称不得重复：' + JSON.stringify(labels));
  five.forEach(k => assert.ok(SI.TYPES[k].hint.length > 6, k + ' 必须带解释'));
  assert.ok(/必须同时给出正名/.test(SI.TYPES.alias.hint), SI.TYPES.alias.hint);
});

test('五种无结果原因各有独立名称，且都给出下一步', () => {
  const five = ['no_match', 'empty_index', 'broken_cache', 'filtered_out', 'unavailable_version'];
  const labels = five.map(k => SI.NO_RESULT_REASONS[k].zh);
  assert.equal(new Set(labels).size, 5, '原因名称不得重复：' + JSON.stringify(labels));
  five.forEach(k => {
    assert.ok(SI.NO_RESULT_REASONS[k].hint.length > 10, k + ' 必须给出下一步');
    assert.ok(/下一步|可以|换/.test(SI.NO_RESULT_REASONS[k].hint),
      k + ' 的 hint 必须含下一步：' + SI.NO_RESULT_REASONS[k].hint);
  });
});

test('负例 · 别名命中必须能回到正名（否则读者不知道这是谁）', () => {
  const g = { characters: [{ id: 'ch_1', name: '许七安', aliases: ['宁宴', '许宁宴'], role: '捕快' }] };
  const idx = SI.build(g);
  const hit = SI.search(idx, '宁宴');
  assert.equal(hit.total, 1, '实际命中=' + hit.total);
  const r = hit.results[0];
  assert.equal(r.type, 'alias', '实际=' + r.type);
  assert.equal(r.typeLabel, '别名');
  assert.equal(r.canonical, '许七安', '别名必须带正名，实际=' + JSON.stringify(r.canonical));
  assert.equal(r.canonicalKey, 'ch_1', '别名必须能回到正名的稳定键');
  assert.equal(r.resolvesToCanonical, true);
  const own = SI.search(idx, '许七安');
  assert.ok(own.results.some(x => x.type === 'character'), '正名应命中人物本体');
});

test('负例 · 无结果必须带原因与下一步，且「索引为空」≠「没有匹配」', () => {
  const idx = SI.build({ characters: [{ id: 'ch_1', name: '甲' }] });
  const miss = SI.search(idx, '不存在的名字xyz');
  assert.equal(miss.reason, 'no_match');
  assert.equal(miss.indexUnavailable, false, '「没有匹配」不得被当成索引问题');
  assert.ok(miss.nextStep && miss.nextStep.length > 5, '必须给下一步');
  const empty = SI.search([], '任意');
  assert.equal(empty.reason, 'empty_index');
  assert.equal(empty.indexUnavailable, true, '「索引为空」必须与「没有匹配」区分开');
  assert.ok(/不等于.*没有/.test(empty.nextStep), empty.nextStep);
  assert.equal(SI.search([], 'x', { broken: true }).reason, 'broken_cache');
  assert.equal(SI.search([], 'x', { unavailable: true }).reason, 'unavailable_version');
  const filtered = SI.search(idx, '不存在的名字xyz', { hadFilter: true });
  assert.equal(filtered.reason, 'filtered_out');
  assert.equal(SI.search(idx, '').reason, null);
  assert.ok(/还没搜/.test(SI.search(idx, '').hint), SI.search(idx, '').hint);
});

test('负例 · 同名作品必须靠稳定键区分（不靠显示名）', () => {
  const entries = [
    { display: '大奉打更人', key: 'key_aaaa1111' },
    { display: '大奉打更人', key: 'key_bbbb2222' },
    { display: '西游记', key: 'key_cccc3333' }
  ];
  const d = SI.distinguishVersions(entries);
  assert.equal(d.sameNameCount, 1, '应检出 1 组同名，实际=' + d.sameNameCount);
  assert.deepEqual(d.collisions, ['大奉打更人']);
  assert.equal(d.allDistinguishable, true, '有键就能区分');
  const dup = d.rows.filter(r => r.display === '大奉打更人');
  assert.ok(dup.every(r => r.disambiguator), '同名项必须带区分信息');
  assert.notEqual(dup[0].disambiguator, dup[1].disambiguator, '两条的区分信息必须不同');
  const bad = SI.distinguishVersions([{ display: '同名书' }, { display: '同名书' }]);
  assert.equal(bad.allDistinguishable, false, '同名且无键必须判为不可区分');
});

test('负例 · 数量不得被当成质量徽章', () => {
  const t = SI.tally(SI.build({ characters: [{ id: 'c1', name: '甲' }] }));
  assert.equal(t.isQualityScore, false);
  assert.ok(/不是质量徽章/.test(t.note), t.note);
  assert.ok(/条目多不等于覆盖好/.test(t.note), t.note);
  const z = SI.tally([]);
  assert.equal(z.total, 0);
  assert.ok(/不等于作品里没有/.test(z.summary), z.summary);
});

test('负例 · 缺类型不得默认成某一类', () => {
  const idx = [{ type: 'nonsense', key: 'k', label: 'x', context: 'c', search: 'x' }];
  const r = SI.search(idx, 'x');
  assert.equal(r.results[0].type, 'unknown', '未知类型必须记未标明，实际=' + r.results[0].type);
  assert.equal(r.results[0].typeLabel, '类型未标明');
});

test('负例 · 非数组/空值/数字不抛异常', () => {
  for (const bad of [null, undefined, 0, 'x', {}]) {
    assert.ok(SI.build(bad));
    assert.ok(SI.search(bad, 'q'));
    assert.ok(SI.tally(bad));
    assert.ok(SI.distinguishVersions(bad));
  }
  const g = { characters: [null, {}, { name: '' }], events: [null], tasks: [null], storylines: [null] };
  assert.ok(Array.isArray(SI.build(g)), '畸形条目不得抛异常');
});

test('真实数据：三书都能建索引，且五类都出现（含别名带正名）', () => {
  for (const [tag, key] of [['大奉', '1063b17ca65ec1b76f30e460'],
                            ['三国', 'fe42d01f3826fe8096f86614'],
                            ['西游', 'a065244455cfb2221bcda94a']]) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    const idx = SI.build(g);
    const t = SI.tally(idx);
    assert.ok(t.total > 0, tag + ' 索引不得为空');
    assert.ok(t.byType.character > 0, tag + ' 必须有人物条目');
    assert.ok(t.byType.event > 0, tag + ' 必须有事件条目');
    assert.equal(t.aliasWithoutCanonical, 0,
      tag + ' 有 ' + t.aliasWithoutCanonical + ' 条别名缺正名');
    console.log('     ' + tag + '：' + t.summary);
  }
});

test('真实数据：跨类型搜索确实一次命中多类（这正是当前 7 个分层搜索做不到的）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const idx = SI.build(g);
  const hit = SI.search(idx, '许七安');
  assert.ok(hit.total > 10, '应命中多条，实际=' + hit.total);
  const types = Object.keys(hit.byType);
  assert.ok(types.length >= 2, '必须一次跨多类命中，实际类型=' + JSON.stringify(types));
  const noCtx = hit.results.filter(r => !r.typeLabel);
  assert.equal(noCtx.length, 0, '每条结果都必须带类型');
  console.log('     「许七安」一次命中 ' + hit.total + ' 条，跨 ' + types.length + ' 类：'
    + JSON.stringify(hit.byType));
});

test('既有正确行为必须保留：作品库已展示范围与缺口（加锁，不得回退）', () => {
  const app = fs.readFileSync('js/app.js', 'utf8');
  assert.ok(/function scopeLine/.test(app), 'scopeLine 必须存在（作品库展示范围）');
  assert.ok(/lbc-scope/.test(app), '必须有范围展示');
  assert.ok(/lbc-gaps/.test(app), '必须有缺口展示');
  assert.ok(/失败块/.test(app), '缺口必须具体到失败块');
  const dec = fs.readFileSync('js/sky/sky-deconstruction.js', 'utf8');
  const n = (dec.match(/searchControl\(/g) || []).length;
  assert.ok(n >= 6, '分层搜索仍存在（实测 ' + n + ' 处）—— 统一搜索尚未接线，如实记录');
  console.log('     libCard 已展示范围/缺口（既有正确行为，已加锁）；'
    + '分层 searchControl 仍有 ' + n + ' 处 ⇒ 统一搜索未接线');
});

console.log('SKY SEARCH INDEX ' + passed + '/' + passed);
