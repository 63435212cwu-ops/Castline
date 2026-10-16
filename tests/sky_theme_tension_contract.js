'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const T = require('../js/sky/sky-theme-tension.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('三种禁止判据 + 三件必需各有独立名称与解释', () => {
  for (const k of ['density', 'deathToll', 'midpoint']) {
    assert.ok(T.FORBIDDEN[k] && T.FORBIDDEN[k].zh, k + ' 必须存在');
    assert.ok(/不构成/.test(T.FORBIDDEN[k].hint), k + ' hint 必须说明"不构成"：' + T.FORBIDDEN[k].hint);
  }
  for (const k of ['perspective', 'support', 'counter']) {
    assert.ok(T.REQUIRED[k] && T.REQUIRED[k].zh, k + ' 必须存在');
    assert.ok(T.REQUIRED[k].hint.length > 8, k + ' 必须带解释');
  }
});

test('负例 · 事件密度不得定义高潮（计划原句第一条）', () => {
  const a = T.climaxBasis({ reason: '此处事件密度最高，剧情点最多' });
  assert.equal(a.code, 'density', '实际=' + a.code);
  assert.equal(a.ok, false, '密度不得作为高潮依据');
  assert.ok(/计划点名禁止/.test(a.hint), a.hint);
  assert.equal(T.climaxBasis({ basis: 'density' }).ok, false);
});

test('负例 · 死亡数不得定义高潮（计划原句第二条）', () => {
  const a = T.climaxBasis({ reason: '这一回死亡人数最多，阵亡者众' });
  assert.equal(a.code, 'deathToll', '实际=' + a.code);
  assert.equal(a.ok, false);
  const b = T.of({ kind: '高潮', climax: { reason: '死亡人数最多' } });
  assert.equal(b.forbiddenBasis, 'deathToll', '必须显式判红，实际=' + b.forbiddenBasis);
});

test('负例 · 时间中点不得定义高潮（计划原句第三条）', () => {
  const a = T.climaxBasis({ reason: '位于全书时间中点，恰在中间' });
  assert.equal(a.code, 'midpoint', '实际=' + a.code);
  assert.equal(a.ok, false);
});

test('结构依据必须被承认（否则判据就是"凡高潮皆错"）', () => {
  const s1 = T.climaxBasis({ reason: '主角目标在此收束，多条线的因果依赖汇合' });
  assert.equal(s1.code, 'structural', '实际=' + s1.code);
  assert.equal(s1.ok, true);
  const s2 = T.climaxBasis({ basis: 'structural' });
  assert.equal(s2.ok, true, '自声明结构依据必须认');
  const u = T.climaxBasis({ reason: '此处很精彩' });
  assert.equal(u.code, 'unknown');
  assert.equal(u.ok, false, '缺依据不得默认成立');
});

test('负例 · 解释层必须齐三件（视角/支撑/反例）', () => {
  const bare = T.interpretability({ text: '本书主题是成长' });
  assert.equal(bare.complete, false);
  assert.deepEqual(bare.missing, ['perspective', 'support', 'counter']);
  assert.ok(/分析视角/.test(bare.hint), bare.hint);
  const partial = T.interpretability({ theme: '成长', perspective: '以许七安为轴',
    support: ['第一章入狱'], });
  assert.equal(partial.complete, false, '缺反例仍不算齐全');
  assert.deepEqual(partial.missing, ['counter'], '实际缺=' + JSON.stringify(partial.missing));
  const full = T.interpretability({ perspective: '以许七安为轴', support: ['第一章'],
    counter: ['魏渊线并不支持'] });
  assert.equal(full.complete, true);
  assert.ok(/不叫解释/.test(T.REQUIRED.counter.hint), T.REQUIRED.counter.hint);
});

test('负例 · 强制套框架判红，但提及框架不算（可选视角是允许的）', () => {
  const forced = T.forcedFrame({ frameForced: true, summary: '按三幕强行切分' });
  assert.equal(forced.forced, true, '强制套用必须判红');
  const mentions = T.forcedFrame({ summary: '可以按三幕读，也可以按人物线读' });
  assert.equal(mentions.forced, false, '只是提及不得判红');
  assert.equal(mentions.mentions, true);
  const none = T.forcedFrame({ summary: '沿因果依赖展开' });
  assert.equal(none.mentions, false);
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'x', [], null, undefined, { kind: 123 }, { climax: 'y' }]) {
    const s = T.of(bad);
    assert.ok(s && typeof s.kind === 'string');
    assert.ok(s.interpretability && Array.isArray(s.interpretability.missing));
  }
  assert.equal(T.tally(null).total, 0);
});

test('负例 · 0 条必须说「从未被要求过」，不得宣称作品没有主题', () => {
  const t = T.tally([]);
  assert.equal(t.title, '主题与张力解释层');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.neverRequested, true);
  assert.ok(/从未被要求提取过/.test(t.summary), t.summary);
  assert.equal(t.mustNotClaim, '本作品没有主题或张力');
  assert.ok(/多种合理解释可以并列/.test(t.note), t.note);
});

test('真实数据：162 个管线产物里**一条主题/张力都没有**（这就是本包的真实状态）', () => {
  const dir = 'loop/state/out';
  const files = fs.readdirSync(dir).filter(f => /^read_.*\.candidate\.json$/.test(f));
  assert.ok(files.length >= 150, '管线产物应有 150+ 个，实际=' + files.length);
  let found = 0;
  for (const f of files) {
    let c; try { c = JSON.parse(fs.readFileSync(dir + '/' + f, 'utf8')); } catch (e) { continue; }
    for (const k of ['themes', 'theme', 'tension', 'structure', 'interpretations']) {
      if (c[k] !== undefined) found++;
    }
  }
  assert.equal(found, 0, '实测管线从未产出主题/张力，实际=' + found);
  console.log('     ' + files.length + ' 个管线产物：主题/张力字段 0 个');
});

test('真实数据：三书 storylines 的 theme 字段是**线级摘要**，不足以充当主题解释层', () => {
  for (const [tag, key, n] of [['大奉', '1063b17ca65ec1b76f30e460', 8],
                                ['三国', 'fe42d01f3826fe8096f86614', 34],
                                ['西游', 'a065244455cfb2221bcda94a', 10]]) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    const lines = g.storylines || [];
    assert.equal(lines.length, n, tag + ' 线数');
    const withTheme = lines.filter(l => l && l.theme);
    assert.equal(withTheme.length, n, tag + ' 每条线都带 theme');
    let complete = 0;
    for (const l of withTheme) {
      if (T.interpretability(l).complete) complete++;
    }
    assert.equal(complete, 0, tag + ' 不应有线级 theme 满足解释层三件套，实际=' + complete);
  }
  console.log('     三书 52 条线级 theme 全部缺少「视角/支撑/反例」⇒ 不构成主题解释层');
});

console.log('SKY THEME TENSION ' + passed + '/' + passed);
