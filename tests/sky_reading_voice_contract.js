'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const R = require('../js/sky/sky-reading-voice.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('五种状态各有独立文案与下一步（计划逐条点名）', () => {
  const five = ['loading', 'missing', 'pendingReview', 'locateFailed', 'modelFailed'];
  const texts = five.map(k => R.STATES[k].text);
  assert.equal(new Set(texts).size, 5, '五种状态文案不得重复：' + JSON.stringify(texts));
  five.forEach(k => {
    assert.ok(R.STATES[k].hint.length > 8, k + ' 必须带解释');
    assert.ok(R.STATES[k].zh, k + ' 必须有中文名');
  });
  for (const k of five) {
    assert.ok(!/暂无数据/.test(R.STATES[k].text), k + ' 不得用「暂无数据」这种笼统文案');
  }
});

test('负例 · 「定位失败/模型失败」必须与「原文未提供」语义可分', () => {
  const miss = R.voice({ absent: true });
  const loc = R.voice({ locateFailed: true });
  const mod = R.voice({ modelFailed: true });
  assert.equal(miss.code, 'missing');
  assert.equal(loc.code, 'locateFailed');
  assert.equal(mod.code, 'modelFailed');
  assert.equal(miss.aboutWork, true);
  assert.equal(miss.aboutProcess, false);
  assert.equal(loc.aboutProcess, true, '定位失败是关于我们的，不是关于作品的');
  assert.equal(mod.aboutProcess, true);
  assert.equal(loc.contentMayExist, true, '定位失败不等于内容不存在');
  assert.equal(mod.contentMayExist, true, '模型失败不等于内容不存在');
  assert.equal(miss.contentMayExist, false, '原文未提供才是真的没有');
  assert.equal(R.voice({ loading: true }).isTransient, true);
});

test('负例 · 缺字段不得默认成「原文未提供」（这正是计划禁止的那句）', () => {
  for (const s of [{}, null, undefined, { status: 'nonsense' }]) {
    const v = R.voice(s);
    assert.notEqual(v.code, 'missing', '缺信号不得默认成"原文未提供"：' + JSON.stringify(s));
    assert.equal(v.code, 'unknown');
    assert.ok(/不得默认成/.test(R.STATES.unknown.hint), R.STATES.unknown.hint);
  }
  assert.equal(R.voice({ status: 'modelFailed', absent: true }).code, 'modelFailed');
  assert.equal(R.voice({ status: 'modelFailed' }).basis, 'declared');
});

test('五个层级有固定次序，且缺层级不得默认成正文', () => {
  const five = ['body', 'summary', 'meta', 'evidence', 'action'];
  assert.equal(new Set(five.map(k => R.LAYERS[k].zh)).size, 5);
  for (let i = 1; i < five.length; i++) {
    assert.ok(R.LAYERS[five[i]].rank > R.LAYERS[five[i - 1]].rank,
      five[i] + ' 的层级必须低于 ' + five[i - 1]);
    assert.ok(R.order(five[i - 1], five[i]) < 0);
  }
  assert.equal(R.layerOf({ layer: 'body' }).code, 'body');
  assert.equal(R.layerOf({ role: 'quote' }).code, 'body', '引文属正文层');
  assert.equal(R.layerOf({ role: 'button' }).code, 'action');
  const u = R.layerOf({});
  assert.equal(u.code, 'unknown', '实际=' + u.code);
  assert.equal(u.rank, null);
  assert.ok(/不得默认成正文/.test(u.hint), u.hint);
});

test('负例 · 阅读面出现工程秒数/原始代码必须判红（计划验收原句）', () => {
  const bad = [
    '分析用时 12.5s',
    '耗时 800ms',
    '文件 3.2 MB',
    '@budget drawcalls=3',
    'fps 60',
    'console.log(1)'
  ];
  for (const t of bad) {
    assert.equal(R.cleanForReading(t).ok, false, '应判红：' + JSON.stringify(t));
    assert.ok(/挤占阅读/.test(R.cleanForReading(t).hint), R.cleanForReading(t).hint);
  }
  const good = ['原文未提供这一项', '待核验', '许七安在牢中度过三日', '第一章 牢狱之灾',
    '他犹豫了片刻', '引句未能在原文中定位'];
  for (const t of good) {
    assert.equal(R.cleanForReading(t).ok, true, '误判：' + JSON.stringify(t) + ' → ' + R.cleanForReading(t).found);
  }
});

test('负例 · 未知状态弱化到看不见必须判红（有下限，不是建议值）', () => {
  const ok = R.visibilityCheck({ fontSize: 12, contrast: 4.5, opacity: 0.7 });
  assert.equal(ok.ok, true, ok.hint);
  assert.equal(R.visibilityCheck({ fontSize: 9 }).ok, false, '字号过小');
  assert.equal(R.visibilityCheck({ contrast: 3.0 }).ok, false, '对比度不足');
  assert.equal(R.visibilityCheck({ opacity: 0.3 }).ok, false, '不透明度过低');
  const bad = R.visibilityCheck({ fontSize: 9, opacity: 0.2 });
  assert.ok(bad.violations.length >= 2, '实际=' + JSON.stringify(bad.violations));
  assert.ok(/不能弱化到看不见/.test(bad.hint), bad.hint);
  assert.equal(typeof R.MIN_VISIBLE.minFontSize, 'number');
  assert.equal(typeof R.MIN_VISIBLE.minContrast, 'number');
  assert.equal(R.MIN_VISIBLE.minContrast, 4.5, '与项目既有的 WCAG AA 门槛一致');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'x', [], null, undefined]) {
    assert.ok(R.voice(bad));
    assert.ok(R.layerOf(bad));
    assert.ok(R.cleanForReading(bad));
    assert.ok(R.visibilityCheck(bad));
    assert.ok(R.tally(bad));
  }
  assert.equal(R.tally(null).total, 0);
});

test('汇总：只有一个状态被用到时必须报「单一说法」', () => {
  const single = R.tally([{ absent: true }, { absent: true }, { absent: true }, { absent: true }]);
  assert.equal(single.singleVoice, true, '只用一个状态就是「所有空值都是同一句」');
  assert.ok(single.statesUsed <= 2);
  const varied = R.tally([{ loading: true }, { absent: true }, { pending: true },
    { locateFailed: true }, { modelFailed: true }]);
  assert.equal(varied.singleVoice, false);
  assert.equal(varied.statesUsed, 5, '实际=' + varied.statesUsed);
  const dirty = R.tally([{ loading: true }, { text: '耗时 5s', absent: true },
    { pending: true }, { absent: true }]);
  assert.ok(dirty.engineeringLeaks >= 1, '必须报出工程痕迹');
  assert.equal(dirty.isQualityScore, false);
});

test('真实数据：既有正确行为必须保留（加锁，不得回退）', () => {
  const dec = fs.readFileSync('js/sky/sky-deconstruction.js', 'utf8');
  const stripped = dec.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
  const leaks = [];
  for (const line of stripped.split('\n')) {
    const lits = line.match(/'[^']*'/g) || [];
    for (const lit of lits) {
      if (!R.cleanForReading(lit).ok) leaks.push(R.cleanForReading(lit).found);
    }
  }
  console.log('     阅读面字符串字面量中的工程痕迹：' + leaks.length + ' 处'
    + (leaks.length ? '（样本 ' + JSON.stringify([...new Set(leaks)].slice(0, 4)) + '）' : ''));
  const i = dec.indexOf('function esc(v)');
  assert.ok(i > 0, 'esc 必须存在');
  const body = dec.slice(i, i + 260);
  for (const [ch, ent] of [['&', '&amp;'], ['<', '&lt;'], ['>', '&gt;'], ['"', '&quot;'], ["'", '&#39;']]) {
    assert.ok(body.includes(ent), 'esc 必须转义 ' + ch + ' → ' + ent);
  }
  const counts = {};
  for (const k of ['loading', 'missing', 'pendingReview', 'locateFailed', 'modelFailed']) {
    counts[k] = (dec.match(new RegExp(R.STATES[k].text.slice(0, 4), 'g')) || []).length;
  }
  console.log('     阅读面状态文案出现次数（前 4 字匹配）：' + JSON.stringify(counts));
  console.log('     esc() 五字符转义完整（& < > " \'）—— 既有正确行为，已加锁');
});

console.log('SKY READING VOICE ' + passed + '/' + passed);
