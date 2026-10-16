'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const R = require('../js/sky/sky-channel-registry.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('七个通道各有名称与「必须写明什么」', () => {
  const seven = ['position', 'hue', 'brightness', 'width', 'dash', 'size', 'motion'];
  assert.deepEqual(Object.keys(R.CHANNELS).sort(), seven.slice().sort(),
    '通道清单必须恰好是计划点名的七个');
  assert.deepEqual(seven.map(c => R.CHANNELS[c].zh), ['位置', '色相', '亮度', '线宽', '线型', '尺寸', '运动']);
  seven.forEach(c => assert.ok(R.CHANNELS[c].must.length > 4, c + ' 必须写明含义要求'));
});

test('负例 · 同一视图同一取值两个含义必须判冲突（计划原句：一种紫色不能同时代表三件事）', () => {
  const c = R.conflicts([
    { view: 'sky', channel: 'hue', value: '--abyss-violet', meaning: '暗线关系', where: 'css/sky-chrome.css:219' },
    { view: 'sky', channel: 'hue', value: '--abyss-violet', meaning: '镜头/氛围', where: 'css/sky-atmosphere-polish.css:14' }
  ]);
  assert.equal(c.length, 1, '必须判出冲突');
  assert.deepEqual(c[0].meanings.sort(), ['暗线关系', '镜头/氛围'].sort());
  assert.ok(/一种取值只能有一个含义/.test(c[0].hint), c[0].hint);
  assert.deepEqual(R.conflicts([
    { view: 'sky', channel: 'hue', value: 'x', meaning: '同一个意思' },
    { view: 'sky', channel: 'hue', value: 'x', meaning: '同一个意思' }
  ]), []);
  assert.deepEqual(R.conflicts([
    { view: 'sky', channel: 'hue', value: 'x', meaning: '甲' },
    { view: 'compass', channel: 'hue', value: 'x', meaning: '乙' }
  ]), [], '不同视图不得判为同视图冲突');
});

test('负例 · 置信状态不能只变暗（必须有文字或符号）', () => {
  const bad = R.confidenceByDimmingOnly([
    { view: 'sky', channel: 'brightness', value: 'dim', meaning: '置信低/未核验' }
  ]);
  assert.equal(bad.length, 1, '只靠亮度表达置信必须判红');
  assert.ok(/不能只变暗/.test(bad[0].hint), bad[0].hint);
  assert.deepEqual(R.confidenceByDimmingOnly([
    { view: 'sky', channel: 'brightness', value: 'dim', meaning: '置信低/未核验', textOrSymbol: true }
  ]), []);
  assert.deepEqual(R.confidenceByDimmingOnly([
    { view: 'sky', channel: 'brightness', value: 'hi', meaning: '重要性高' }
  ]), []);
});

test('负例 · 跨视图语义变化必须同时有上下文与同步图例', () => {
  const bad = R.crossViewChanges([
    { view: 'sky', channel: 'dash', value: '4 3', meaning: '暗线' },
    { view: 'compass', channel: 'dash', value: '4 3', meaning: '推断' }
  ]);
  assert.equal(bad.length, 1);
  assert.equal(bad[0].ok, false);
  assert.ok(/上下文/.test(bad[0].hint) && /同步图例/.test(bad[0].hint), bad[0].hint);
  const ok = R.crossViewChanges([
    { view: 'sky', channel: 'dash', value: '4 3', meaning: '暗线', context: true, syncedLegend: true },
    { view: 'compass', channel: 'dash', value: '4 3', meaning: '推断', context: true, syncedLegend: true }
  ]);
  assert.equal(ok[0].ok, true);
  assert.deepEqual(R.crossViewChanges([
    { view: 'sky', channel: 'dash', value: '4 3', meaning: '暗线' }
  ]), []);
});

test('负例 · 冲突不能靠删除登记清零（棘轮）', () => {
  const cur = [{ view: 'sky', channel: 'hue', value: 'v', meaning: 'A' }];
  const r = R.ratchet(cur, ['sky␟hue␟v']);
  assert.equal(r.shrunkWithoutFix, true, '冲突从登记里消失必须被报出');
  assert.ok(/靠删除登记清零/.test(r.hint), r.hint);
  const r2 = R.ratchet([
    { view: 'sky', channel: 'hue', value: 'v', meaning: 'A' },
    { view: 'sky', channel: 'hue', value: 'v', meaning: 'B' }
  ], []);
  assert.equal(r2.ok, false, '新增冲突必须判红');
  assert.equal(r2.addedKeys.length, 1);
});

test('负例 · 只有颜色通道的视图必须被指出灰阶下不可区分', () => {
  const deg = R.survivesDegradation([
    { view: 'sky', channel: 'hue', value: 'a', meaning: 'x' },
    { view: 'sky', channel: 'position', value: 'b', meaning: 'y' }
  ]);
  assert.equal(deg[0].hasNonColorChannel, false, '只有位置+色相 ⇒ 灰阶下不可区分');
  assert.ok(/灰阶或关光后主要结构将无法区分/.test(deg[0].hint), deg[0].hint);
  const ok = R.survivesDegradation([
    { view: 'sky', channel: 'hue', value: 'a', meaning: 'x' },
    { view: 'sky', channel: 'dash', value: '4 3', meaning: 'y' }
  ]);
  assert.equal(ok[0].hasNonColorChannel, true);
});

test('负例 · 七通道缺登记必须点名', () => {
  const c = R.coverage([{ channel: 'hue' }, { channel: 'position' }]);
  assert.equal(c.ok, false);
  assert.deepEqual(c.missing.sort(), ['brightness', 'dash', 'motion', 'size', 'width']);
  assert.ok(c.missingLabels.indexOf('线型') >= 0);
  assert.equal(R.coverage(Object.keys(R.CHANNELS).map(ch => ({ channel: ch }))).ok, true);
});

test('负例 · 非数组/空值不抛异常', () => {
  for (const bad of [null, undefined, 0, 'x', {}]) {
    assert.ok(Array.isArray(R.conflicts(bad)));
    assert.ok(Array.isArray(R.confidenceByDimmingOnly(bad)));
    assert.ok(Array.isArray(R.survivesDegradation(bad)));
  }
  assert.equal(R.tally(null).entries, 0);
});

test('真实数据 · other 与 oppose 亮度只差 7.5，必须靠**线型**区分（已修）', () => {
  const tokens = fs.readFileSync('css/abyss-tokens.css', 'utf8');
  function hexOf(name) {
    const m = new RegExp('--abyss-' + name + ':\\s*(#[0-9a-fA-F]{6})').exec(tokens);
    return m ? m[1] : null;
  }
  function lum(hex) {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  const none = hexOf('camp-none'), oppose = hexOf('camp-oppose');
  assert.ok(none && oppose, '夹具应能在 tokens 里读到 camp-none / camp-oppose');
  const d = Math.abs(lum(none) - lum(oppose));
  assert.ok(d < 12, 'other 与 oppose 的亮度差应 < 12，实际=' + d.toFixed(1));
  const chrome = fs.readFileSync('css/sky-chrome.css', 'utf8');
  assert.equal(/data-rel=other[^\n]*stroke-dasharray/.test(chrome), true,
    'other 必须有点线（否则与 oppose 在灰阶下不可区分）');
  assert.equal(/data-rel=oppose[^\n]*stroke-dasharray/.test(chrome), false,
    'oppose 应保持实线（与 other 的点线形成对照）');
  const otherDash = /data-rel=other[^\n]*stroke-dasharray:([^;}\n]+)/.exec(chrome);
  assert.ok(otherDash && otherDash[1].trim().length > 0, 'other 的 dasharray 不能为空');
  console.log('     camp-none 亮度 ' + lum(none).toFixed(0) + ' vs camp-oppose ' + lum(oppose).toFixed(0)
    + '（差 ' + d.toFixed(1) + '）；other 已配点线 ' + otherDash[1].trim() + ' ⇒ 灰阶下可区分');
});

test('真实数据 · 图例确实给部分关系类配了非颜色通道（局部已做对）', () => {
  const chrome = fs.readFileSync('css/sky-chrome.css', 'utf8');
  assert.notEqual(chrome.indexOf('data-rel=dark] line{stroke-dasharray'), -1, 'dark 应有 dasharray');
  assert.notEqual(chrome.indexOf('data-rel=kin] line{stroke-dasharray'), -1, 'kin 应有 dasharray');
  assert.notEqual(chrome.indexOf('stroke-width:2.2'), -1, 'bond 应改过线宽');
  console.log('     sky-chrome.css 已给 dark/kin/bond 配线型、bond 配线宽；缺的是全域登记与判据');
});

test('真实数据 · --abyss-violet 在同一视图里确实一值两义（计划点名的形态）', () => {
  const chrome = fs.readFileSync('css/sky-chrome.css', 'utf8');
  const atmo = fs.readFileSync('css/sky-atmosphere-polish.css', 'utf8');
  assert.notEqual(chrome.indexOf('[data-rel=dark]{--sky-rel:var(--abyss-violet)}'), -1,
    '夹具应含「暗线 = violet」');
  assert.notEqual(atmo.indexOf('--sa-lens: var(--abyss-violet-bright)'), -1,
    '夹具应含「镜头 = violet-bright」');
  const c = R.conflicts([
    { view: 'sky', channel: 'hue', value: '--abyss-violet', meaning: '暗线关系', where: 'sky-chrome.css:219' },
    { view: 'sky', channel: 'hue', value: '--abyss-violet', meaning: '镜头/氛围', where: 'sky-atmosphere-polish.css' }
  ]);
  assert.equal(c.length, 1, '同视图一值两义必须判冲突');
  console.log('     violet：图例=暗线关系 ｜ 氛围层=镜头（同属天空视图）⇒ 判冲突');
});

console.log('SKY CHANNEL REGISTRY ' + passed + '/' + passed);
