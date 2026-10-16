'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const N = require('../js/sky/sky-name-budget.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('三档（当前/相关/背景）各有数量与占屏预算，且都不是「适量」', () => {
  for (const k of ['current', 'related', 'background']) {
    const t = N.TIERS[k];
    assert.ok(t.maxCount > 0, k + ' 必须有数量上限');
    assert.ok(t.maxScreenShare > 0 && t.maxScreenShare <= 1, k + ' 必须有占屏预算');
    assert.ok(t.hint.length > 8, k + ' 必须带解释');
  }
  assert.equal(N.TIERS.current.maxCount, 1);
  assert.ok(N.TIERS.related.maxCount + N.TIERS.background.maxCount < 100,
    '三档合计必须远小于上百');
});

test('五种名称形态（长中文/重名/单字名/混合字符/极长章名）都有判据', () => {
  for (const k of ['longChinese', 'duplicate', 'singleChar', 'mixed', 'veryLongChapter']) {
    assert.ok(N.SHAPES[k] && N.SHAPES[k].zh, k + ' 必须存在');
    assert.ok(N.SHAPES[k].hint.length > 6, k + ' 必须带解释');
  }
  assert.equal(N.shapesOf('唐三藏之徒猪八戒的丈人高太公').includes('longChinese'), true);
  assert.equal(N.shapesOf('礁').includes('singleChar'), true);
  assert.equal(N.shapesOf('二爷（陈二）').includes('mixed'), true);
  assert.equal(N.shapesOf('许七安', { duplicateCount: 3 }).includes('duplicate'), true);
  assert.equal(N.shapesOf('第一百三十章 许七安：婶婶，你想用黄金打脸，还是绸缎打脸？',
    { isChapter: true }).includes('veryLongChapter'), true);
});

test('负例 · 未知名称不得是空白（计划验收原句）', () => {
  const u = N.unknownLabel({ chapter: '第三章', id: 'ev_abc123', kindZh: '事件' });
  assert.equal(u.nonEmpty, true, '占位必须非空');
  assert.ok(u.text.trim().length > 0, '实际=' + JSON.stringify(u.text));
  assert.equal(u.isPlaceholder, true);
  assert.equal(u.nature, '原文未提供名称');
  assert.ok(u.locator, '必须带章节以便定位');
  const s = N.of({ name: '', id: 'ev_abc123', kindZh: '事件', tier: 'related' });
  assert.ok(s.label.trim().length > 0, 'of() 对空名不得返回空标签，实际=' + JSON.stringify(s.label));
  assert.equal(s.isPlaceholder, true);
  const a = N.unknownLabel({ chapter: '第三章', id: 'ev_aaa111' });
  const b = N.unknownLabel({ chapter: '第三章', id: 'ev_bbb222' });
  assert.notEqual(a.text, b.text, '同名同章的多个未知事件必须靠 id 区分');
});

test('负例 · 缩写不得丢掉全文入口（完整证据不因省略号失去入口）', () => {
  const long = '唐三藏之徒猪八戒的丈人高太公';
  const sl = N.shortLabel(long, 'longChinese');
  assert.equal(sl.abbreviated, true, '超长必须缩写');
  assert.ok(sl.text.length < long.length, '短标签必须更短');
  assert.equal(sl.full, long, '**全文必须原样保留**，实际=' + JSON.stringify(sl.full));
  assert.equal(sl.fullRetained, true);
  assert.ok(!sl.text.endsWith('…'), '短标签不应补省略号，实际=' + JSON.stringify(sl.text));
  const s2 = N.shortLabel('许七安', 'longChinese');
  assert.equal(s2.abbreviated, false);
  assert.equal(s2.text, '许七安');
  assert.equal(N.shortLabel('礁', 'singleChar').text, '礁');
});

test('负例 · 超预算必须判红（当前≤1、相关≤12、背景≤40）', () => {
  const ok = N.budget({ current: 1, related: 8, background: 20,
    shares: { current: 0.3, related: 0.4, background: 0.15 } });
  assert.equal(ok.ok, true, ok.hint);
  const over = N.budget({ current: 3, related: 8, background: 20,
    shares: { current: 0.3, related: 0.4, background: 0.15 } });
  assert.equal(over.ok, false, '当前档超过 1 必须判红');
  assert.ok(/超预算/.test(over.hint), over.hint);
  const overShare = N.budget({ current: 1, related: 8, background: 20,
    shares: { current: 0.9, related: 0.4, background: 0.15 } });
  assert.equal(overShare.ok, false, '占屏超预算必须判红');
  const many = N.budget({ current: 1, related: 60, background: 200, shares: {} });
  assert.equal(many.ok, false);
});

test('负例 · 命中区域必须与可见对象同源，且不得小于可见对象', () => {
  const good = N.hitSource({ key: 'ev_1', w: 10, h: 10 }, { key: 'ev_1', w: 10, h: 10 });
  assert.equal(good.ok, true, good.hint);
  assert.equal(N.hitSource({ key: 'ev_1', w: 10, h: 10 }, { key: 'ev_1', w: 14, h: 14 }).ok, true);
  const diff = N.hitSource({ key: 'ev_1', w: 10, h: 10 }, { key: 'ev_2', w: 10, h: 10 });
  assert.equal(diff.ok, false, '不同源必须判红');
  assert.ok(/同源/.test(diff.hint), diff.hint);
  const small = N.hitSource({ key: 'ev_1', w: 10, h: 10 }, { key: 'ev_1', w: 4, h: 4 });
  assert.equal(small.ok, false, '命中区更小必须判红');
  assert.equal(N.hitSource({}, {}).ok, false);
  assert.equal(N.hitSource({}, {}).reason, 'no_key');
});

test('负例 · 缺 tier 不得默认成「当前」', () => {
  const s = N.of({ name: '许七安' });
  assert.equal(s.tier, 'unknown', '实际=' + s.tier);
  assert.notEqual(s.tier, 'current', '未标明不得默认成当前');
  assert.ok(/未标明不得默认成/.test(N.TIERS.unknown.hint), N.TIERS.unknown.hint);
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'x', [], null, undefined, { name: 123 }]) {
    const s = N.of(bad);
    assert.ok(s && typeof s.tier === 'string');
    assert.ok(s.label.trim().length > 0, '任何输入都必须给出非空标签');
  }
  assert.equal(N.tally(null).total, 0);
});

test('汇总只叫名称构成，0 条时不得声称没问题', () => {
  const t = N.tally(null);
  assert.equal(t.title, '名称与标签构成');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.total, 0);
  assert.ok(/尚无样本/.test(t.summary), t.summary);
  const t2 = N.tally([{ name: '许七安', tier: 'current' }, { name: '', tier: 'related', id: 'ev_x' }]);
  assert.equal(t2.total, 2);
  assert.equal(t2.placeholder, 1);
  assert.equal(t2.lostFullText, 0, '全文入口不得丢失');
});

test('真实数据：五种形态的最坏情况都真实存在（不是假想边界）', () => {
  const names = new Set(), chapters = new Set();
  let longestName = '', longestChapter = '';
  for (const key of ['1063b17ca65ec1b76f30e460', 'fe42d01f3826fe8096f86614',
                     'a065244455cfb2221bcda94a']) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    for (const c of (g.characters || [])) {
      const n = c && c.name;
      if (typeof n === 'string' && n.trim()) {
        names.add(n.trim());
        if (n.trim().length > longestName.length) longestName = n.trim();
      }
    }
    for (const e of (g.events || [])) {
      const ch = e && e.chapter;
      if (typeof ch === 'string' && ch.trim()) {
        chapters.add(ch.trim());
        if (ch.trim().length > longestChapter.length) longestChapter = ch.trim();
      }
    }
  }
  assert.equal(names.size, 1177, '三书人物名去重数');
  assert.equal(chapters.size, 1111, '三书章名去重数');

  const singles = [...names].filter(n => n.length === 1);
  assert.ok(singles.length >= 2, '单字名应 ≥2，实际=' + JSON.stringify(singles));
  assert.ok(singles.includes('礁') || singles.includes('荒'), '实际=' + JSON.stringify(singles));
  const mixed = [...names].filter(n => ![...n].every(c => /[\u4e00-\u9fff]/.test(c)));
  assert.ok(mixed.length >= 1, '混合字符名应 ≥1，实际=' + JSON.stringify(mixed));
  assert.equal(longestName, '唐三藏之徒猪八戒的丈人高太公', '最长人物名');
  assert.equal(longestName.length, 14);
  assert.ok(longestChapter.length >= 29, '最长章名应 ≥29 字，实际=' + longestChapter.length);

  for (const n of [longestName, singles[0], mixed[0]]) {
    const s = N.of({ name: n, tier: 'related' });
    assert.ok(s.label.trim().length > 0, n + ' 的标签不得为空');
    assert.equal(s.full, n, n + ' 的全文必须保留');
  }
  const chs = N.of({ name: longestChapter, tier: 'background', isChapter: true });
  assert.ok(chs.label.trim().length > 0, '极长章名标签不得为空');
  assert.equal(chs.full, longestChapter, '极长章名全文必须保留');
  console.log('     人物名 ' + names.size + '（最长 ' + longestName.length + ' 字：' + longestName + '）');
  console.log('     章名 ' + chapters.size + '（最长 ' + longestChapter.length + ' 字）');
  console.log('     单字名 ' + JSON.stringify(singles) + '；混合字符 ' + JSON.stringify(mixed.slice(0, 3)));
});

console.log('SKY NAME BUDGET ' + passed + '/' + passed);
