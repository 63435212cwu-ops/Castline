'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const S = require('../js/sky/sky-state-transition.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('六个面各有独立名称与解释（能力/资源/身份/目标/立场/代价）', () => {
  const six = ['ability', 'resource', 'identity', 'goal', 'stance', 'cost'];
  const labels = six.map(c => S.FACETS[c].zh);
  assert.equal(new Set(labels).size, six.length, '六面名称不得重复：' + JSON.stringify(labels));
  six.forEach(c => assert.ok(S.FACETS[c].hint.length > 6, c + ' 必须带解释'));
});

test('负例 · 无 before 或 无 after 不得算转变（无前后依据不画成长箭头）', () => {
  for (const rec of [{}, { before: '前' }, { after: '后' }, { summary: '某人变了' }, null]) {
    const s = S.of(rec);
    assert.notEqual(s.code, 'transition', '两端不全不得判转变：' + JSON.stringify(rec));
    assert.equal(s.canDrawGrowth, false, '不得画成长箭头');
    assert.equal(s.mustNotCountAsGrowth, true);
  }
  assert.equal(S.of({ before: 'a', after: 'b' }).canDrawGrowth, true);
});

test('负例 · 嵌套与顶层两种形态必须同判（实测代码只认嵌套，静默丢 114 条）', () => {
  const top = S.of({ before: '破黄巾有功而未得官职，尚为白身', after: '被董卓轻慢' });
  const nested = S.of({ transition: { before: '破黄巾有功而未得官职，尚为白身', after: '被董卓轻慢' } });
  assert.equal(top.code, 'transition', '顶层形态必须认，实际=' + top.code);
  assert.equal(nested.code, 'transition', '嵌套形态也必须认，实际=' + nested.code);
  assert.deepEqual(top.ends, nested.ends, '两种形态必须得到同一对端点');
  assert.equal(S.of({ from: 'a', to: 'b' }).canDrawGrowth, true);
});

test('负例 · 情绪瞬间不得计入成长（计划：情绪瞬间与稳定人格分开）', () => {
  const emo = S.of({ attribute: '情绪/压力', before: '恐惧', after: '冷静' });
  assert.equal(emo.code, 'emotion', '实际=' + emo.code);
  assert.equal(emo.canDrawGrowth, false, '情绪瞬间不得画成长箭头');
  assert.equal(emo.isEmotionalMoment, true);
  assert.ok(/不是成长/.test(emo.hint), emo.hint);
  assert.equal(S.of({ attribute: '送行现场的兴致', before: '设彩头', after: '叹息收场' }).canDrawGrowth, false);
  assert.equal(S.of({ attribute: '心理防线（是否开口）', before: '不开口', after: '开口' }).canDrawGrowth, false);
  const stance = S.of({ attribute: '对曹操的态度', before: '未至柴桑表态', after: '决计血战，受水军统帅之任' });
  assert.equal(stance.code, 'transition', '立场确立必须算转变，实际=' + stance.code);
  assert.equal(stance.facet, 'stance', '对X的态度应归立场，实际=' + stance.facet);
});

test('负例 · 旁人评价不得算本人的状态变化', () => {
  const oth = S.of({ summary: '众人对曹操的评价由讥转畏', before: '讥', after: '畏' });
  assert.notEqual(oth.code, 'transition', '旁人评价不得判转变，实际=' + oth.code);
  assert.equal(oth.canDrawGrowth, false);
});

test('负例 · 稳定人格本身不是一次变化', () => {
  const st = S.of({ summary: '此人性格一向如此' });
  assert.equal(st.code, 'stable', '实际=' + st.code);
  assert.equal(st.canDrawGrowth, false);
});

test('可逆 / 不可逆必须可区分，判不出不得默认可逆', () => {
  const dead = S.of({ summary: '阵前被斩', before: '在世', after: '身亡' });
  assert.equal(dead.reversibility, 'irreversible', '实际=' + dead.reversibility);
  const back = S.of({ summary: '官复原职', before: '革职', after: '复职' });
  assert.equal(back.reversibility, 'reversible', '实际=' + back.reversibility);
  const unk = S.of({ before: '甲', after: '乙' });
  assert.equal(unk.reversibility, 'unknown', '判不出必须记未标明，不得默认可逆');
  assert.notEqual(dead.reversibilityLabel, back.reversibilityLabel);
});

test('负例 · 缺 attribute 不得默认成「能力」面', () => {
  const s = S.of({ before: '甲', after: '乙' });
  assert.equal(s.facet, 'unknown', '缺 attribute 必须记未标明，实际=' + s.facet);
  assert.equal(S.of({ attribute: '武艺境界', before: '九品', after: '八品' }).facet, 'ability');
  assert.equal(S.of({ attribute: '官职地位', before: '白身', after: '县令' }).facet, 'identity');
  assert.equal(S.of({ attribute: '所属之主', before: '袁绍', after: '曹操' }).facet, 'stance');
});

test('原文明示 / 分析归纳必须可区分', () => {
  assert.equal(S.of({ before: 'a', after: 'b', basis: 'explicit' }).evidential, 'explicit');
  assert.equal(S.of({ before: 'a', after: 'b', provenance: 'assistant-reviewed-source' }).evidential, 'explicit');
  assert.equal(S.of({ before: 'a', after: 'b', basis: 'inferred' }).evidential, 'inferred');
  assert.equal(S.of({ before: 'a', after: 'b' }).evidential, 'unknown', '缺依据必须记未标明');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'state_1', [], { before: 123 }, { transition: 'x' }]) {
    const s = S.of(bad);
    assert.ok(s && typeof s.code === 'string');
  }
  assert.equal(S.tally(null).total, 0);
});

test('汇总只叫状态记录构成，不得自称成长评分', () => {
  const t = S.tally([
    { before: 'a', after: 'b' },
    { attribute: '情绪/压力', before: 'x', after: 'y' },
    { summary: '众人对袁绍的评价' },
    { before: '只有前' }
  ]);
  assert.equal(t.title, '状态记录构成');
  assert.equal(t.isGrowthScore, false);
  assert.equal(t.total, 4);
  assert.equal(t.drawable, 1, '只有一条两端齐全');
  assert.equal(t.emotional, 1);
  assert.equal(t.incomplete, 1);
  assert.ok(/不得计入成长/.test(t.note), t.note);
});

test('真实数据：三国 114 条顶层两端齐全必须全部可画成长箭头（现状模型投影 0 条）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8'));
  const cs = g.characterStates || [];
  assert.equal(cs.length, 129, '夹具状态数');
  assert.equal(cs.filter(s => s.transition).length, 0, '夹具必须 0 条嵌套形态');
  const topBoth = cs.filter(s => s.before && s.after).length;
  assert.equal(topBoth, 114, '夹具顶层两端齐全数');
  const t = S.tally(cs);
  assert.equal(t.drawable, 114, '可画成长箭头数，实际=' + t.drawable);
  assert.equal(t.emotional, 0, '三国不应有情绪瞬间记录，实际=' + t.emotional);
  assert.equal(t.incomplete, 15, '前后依据不全数');
  console.log('     ' + t.summary);
});

test('真实数据：大奉 17 条里情绪类必须被单列出来（不得计入成长）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const cs = g.characterStates || [];
  assert.equal(cs.length, 17, '夹具状态数');
  const t = S.tally(cs);
  assert.ok(t.emotional >= 4, '实测大奉有多条情绪类 attribute，实际=' + t.emotional);
  assert.equal(t.incomplete, 8, '前后依据不全数（11 条两端全无里 3 条被判情绪/他人），实际=' + t.incomplete);
  assert.equal(t.drawable, 5, '可画成长箭头数（两端齐全 6 减去 1 条情绪），实际=' + t.drawable);
  assert.equal(t.emotional, 4, '情绪类记录数，实际=' + t.emotional);
  console.log('     ' + t.summary);
});

test('真实数据：西游 52 条同样可分类（跨书一致）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/a065244455cfb2221bcda94a.json', 'utf8'));
  const cs = g.characterStates || [];
  const t = S.tally(cs);
  assert.equal(t.total, cs.length);
  assert.ok(t.byCode.transition > 0, '必须有一批真实转变');
  assert.ok(t.byCode.incomplete > 0, '必须有前后依据不全的记录被单列');
  console.log('     西游：' + t.summary);
});

console.log('SKY STATE TRANSITION ' + passed + '/' + passed);
