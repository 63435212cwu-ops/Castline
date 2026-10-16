'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const D = require('../js/sky/sky-disclosure.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('三级（全景/聚焦/证据）各有独立的「应出现/不应出现」', () => {
  const three = ['panorama', 'focus', 'evidence'];
  const labels = three.map(c => D.LEVELS[c].zh);
  assert.deepEqual(labels, ['全景', '聚焦', '证据']);
  three.forEach(c => {
    assert.ok(D.LEVELS[c].shows && D.LEVELS[c].shows.length > 4, c + ' 必须写明显示什么');
    assert.ok(D.LEVELS[c].mustNotShow && D.LEVELS[c].mustNotShow.length > 4, c + ' 必须写明不该出现什么');
  });
  assert.ok(/当前问题/.test(D.LEVELS.panorama.shows), D.LEVELS.panorama.shows);
  assert.ok(/人物|人/.test(D.LEVELS.focus.shows) && /线/.test(D.LEVELS.focus.shows) && /事件/.test(D.LEVELS.focus.shows));
  assert.ok(/完整原文/.test(D.LEVELS.evidence.shows) && /判断边界/.test(D.LEVELS.evidence.shows));
});

test('负例 · 降噪不得删除数据（计划原句）', () => {
  const bad = D.folding({ total: 100, shown: 10, retained: 10 });
  assert.equal(bad.deletedData, true, '保留数小于总数必须判为删了数据');
  assert.equal(bad.folded, 90);
  assert.ok(/降噪不删除数据/.test(bad.hint), bad.hint);
  const ok = D.folding({ total: 100, shown: 10, retained: 100 });
  assert.equal(ok.deletedData, false);
  assert.equal(ok.folded, 90);
  assert.equal(ok.retained, 100, '数据必须原样保留');
  assert.ok(/可恢复/.test(ok.hint), ok.hint);
  assert.equal(D.restore({ total: 100, shown: 10, retained: 100 }).canRestore, true);
  assert.equal(D.restore({ total: 100, shown: 10, retained: 10 }).canRestore, false);
});

test('负例 · 不得声称折叠却折叠数为 0', () => {
  const lie = D.folding({ total: 50, shown: 50, claimsFolded: true });
  assert.equal(lie.folded, 0);
  assert.equal(lie.liesAboutFolding, true, '声称折叠了但折叠数 0 必须判红');
});

test('负例 · 缺字段不得默认「没折叠」', () => {
  for (const bad of [{}, { shown: 5 }, null, undefined]) {
    const f = D.folding(bad);
    assert.equal(f.known, false, '没有总数必须如实报未知：' + JSON.stringify(bad));
    assert.equal(f.folded, null, '不得默认成 0');
    assert.ok(/不得默认成/.test(f.hint), f.hint);
  }
});

test('负例 · 全景标签超预算必须判越级（不要要求全景读上百个标签）', () => {
  const over = D.budget('panorama', 120);
  assert.equal(over.over, true, '全景 120 个标签必须判越级');
  assert.equal(over.budget, 40);
  assert.ok(/应折叠或改由下一级承担/.test(over.hint), over.hint);
  const ok = D.budget('panorama', 12);
  assert.equal(ok.over, false);
  assert.equal(D.LEVELS.evidence.labelBudget, null);
  const ev = D.budget('evidence', 5000);
  assert.equal(ev.over, false, '证据态不得因条数多而判越级');
  assert.equal(D.budget('nope', 5).known, false);
});

test('负例 · 稀疏不得用装饰伪造丰富', () => {
  const padded = D.sparsity({ count: 3, capacity: 100, paddedWithDecoration: true });
  assert.equal(padded.sparse, true);
  assert.equal(padded.paddedWithDecoration, true, '稀疏却用装饰补齐必须判红');
  assert.ok(/不用装饰伪造丰富/.test(padded.hint), padded.hint);
  const sparse = D.sparsity({ count: 3, capacity: 100 });
  assert.equal(sparse.sparse, true);
  assert.equal(sparse.paddedWithDecoration, false);
  assert.ok(/不是缺陷/.test(sparse.hint), sparse.hint);
  assert.equal(D.sparsity({ count: 60, capacity: 100 }).sparse, false);
  const unk = D.sparsity({});
  assert.equal(unk.known, false);
  assert.equal(unk.sparse, null, '不得默认成不稀疏');
});

test('负例 · 从主问题到原文必须沿连续路径（不得跳级）', () => {
  const p = D.path();
  assert.equal(p.continuous, true);
  assert.deepEqual(p.steps.map(s => s.code), ['panorama', 'focus', 'evidence']);
  assert.ok(/逐级返回/.test(p.hint), p.hint);
});

test('负例 · 未声明层级必须如实报，不得默认成某一级', () => {
  const o = D.of({ total: 10, shown: 10 });
  assert.equal(o.known, false);
  assert.equal(o.level, 'unknown');
  assert.ok(/无法预期这一屏该读到什么/.test(o.levelHint), o.levelHint);
  const good = D.of({ level: 'panorama', total: 100, shown: 10, retained: 100, labelCount: 8 });
  assert.deepEqual(good.violations, [], '合规屏不得有违规：' + JSON.stringify(good.violations));
  assert.equal(good.folding.foldedLabel, '已折叠 90 / 100');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'x', [], null, undefined, { level: 123 }]) {
    const o = D.of(bad);
    assert.ok(o && typeof o.level === 'string');
    assert.ok(Array.isArray(o.violations));
  }
  assert.equal(D.tally(null).total, 0);
});

test('汇总只叫披露状态，不得自称质量分', () => {
  const t = D.tally([
    { level: 'panorama', total: 100, shown: 10, retained: 100, labelCount: 8 },
    { level: 'focus', total: 100, shown: 5, retained: 5, labelCount: 200 }
  ]);
  assert.equal(t.title, '渐进披露状态');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.total, 2);
  assert.equal(t.foldedTotal, 185);
  assert.equal(t.violations, 1, '第二屏删了数据必须计为违规');
  assert.equal(t.deletedData, 1);
  assert.ok(/降噪不删除数据/.test(t.note), t.note);
});

test('真实数据：既有代码里确实已有「画了/共有」的诚实披露（不是从零开始）', () => {
  const src = fs.readFileSync('js/sky/sky-chrome.js', 'utf8');
  assert.notEqual(src.indexOf('守恒、不冒充'), -1, '夹具应含「守恒、不冒充」的既有注释');
  assert.notEqual(src.indexOf('全景 <b>'), -1, '夹具应含「全景 N / M」的既有图例');
  assert.notEqual(src.indexOf('默认只画最强的'), -1, '夹具应含「只画最强的 N 束，共 M 条」的既有披露');
  const before = ['CLSkyDisclosure'];
  for (const name of before) {
    assert.equal(fs.existsSync('js/sky/sky-disclosure.js'), true, '本模块应存在');
  }
  console.log('     sky-chrome.js 已有局部披露（全景 N/M、只画最强 N 束）；本包补三级定义与整体折叠账');
});

console.log('SKY DISCLOSURE ' + passed + '/' + passed);
