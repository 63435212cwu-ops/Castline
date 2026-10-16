'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const F = require('../js/sky/sky-foreshadow-stage.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('八阶段（外加缺兑现端/断裂/未标明）各有独立名称与解释', () => {
  const eight = ['setup', 'hint', 'misdirect', 'delayed', 'payoff', 'partial', 'restart', 'open'];
  const labels = eight.map(c => F.STAGES[c].zh);
  assert.equal(new Set(labels).size, eight.length, '八阶段名称不得重复：' + JSON.stringify(labels));
  eight.forEach(c => assert.ok(F.STAGES[c].hint.length > 8, c + ' 必须带解释'));
  ['claimed_unbacked', 'broken', 'unknown'].forEach(c =>
    assert.ok(F.STAGES[c] && F.STAGES[c].zh, c + ' 必须存在'));
});

test('负例 · 缺字段不得默认成「已兑现」', () => {
  for (const c of [{}, { id: 'clue_1' }, null, undefined, { description: '某线索' }]) {
    const s = F.of(c);
    assert.notEqual(s.code, 'payoff', '缺字段不得判兑现：' + JSON.stringify(c));
    assert.equal(s.closed, false);
  }
});

test('负例 · 声称 resolved 但缺兑现端，不得算兑现（实测大奉 9/9 是这个形态）', () => {
  const s = F.of({ id: 'clue_x', seedEventId: 'ev_a', payoffEventId: null,
    resolved: true, referenceStatus: 'resolved' });
  assert.notEqual(s.code, 'payoff', '缺兑现端不得判兑现，实际=' + s.code);
  assert.equal(s.code, 'claimed_unbacked', '必须单列为「声称已兑现但缺兑现端」');
  assert.equal(s.closed, false);
  assert.equal(s.isDefect, true, '数据自相矛盾必须算缺陷');
  assert.equal(s.bothEndsVerifiable, false);
  assert.ok(/不能当作已兑现/.test(F.STAGES.claimed_unbacked.hint), F.STAGES.claimed_unbacked.hint);
});

test('负例 ·「未回收」不是缺陷（未完稿里不算）', () => {
  const s = F.of({ id: 'clue_y', seedEventId: 'ev_a', resolved: false });
  assert.equal(s.code, 'open');
  assert.equal(s.isDefect, false, '未回收不得算缺陷');
  assert.equal(s.openIsNotDefect, true);
  assert.equal(F.STAGES.open.tone, 'neutral', '未回收用中性色，不报错');
  assert.ok(/不是缺陷/.test(F.STAGES.open.hint), F.STAGES.open.hint);
});

test('负例 ·「引用断裂」必须与「未回收」分开', () => {
  const broken = F.of({ id: 'clue_z', seedEventId: 'ev_a', referenceStatus: 'unresolved_or_conflicting' });
  const open = F.of({ id: 'clue_w', seedEventId: 'ev_a' });
  assert.equal(broken.code, 'broken');
  assert.equal(open.code, 'open');
  assert.notEqual(broken.label, open.label, '断裂与未回收不得显示成同一个词');
  assert.equal(broken.isDefect, true);
  assert.equal(open.isDefect, false);
});

test('两端齐全才算兑现，且两端必须可跳原文', () => {
  const ok = F.of({ id: 'c1', seedEventId: 'ev_a', payoffEventId: 'ev_b' });
  assert.equal(ok.code, 'payoff');
  assert.equal(ok.closed, true);
  assert.equal(ok.bothEndsVerifiable, true);
  assert.deepEqual(ok.anchors, { seed: 'ev_a', payoff: 'ev_b' });
  const alt = F.of({ id: 'c2', eventIds: ['ev_a', 'ev_b'], payoffEventId: 'ev_b' });
  assert.equal(alt.bothEndsVerifiable, true);
});

test('clueType 已知字面必须映射到八阶段（西游在用）', () => {
  const pro = F.of({ id: 'c3', seedEventId: 'a', payoffEventId: 'b', clueType: 'narrative_prolepsis' });
  assert.equal(pro.code, 'hint', '实际=' + pro.code);
  const mis = F.of({ id: 'c4', seedEventId: 'a', clueType: 'misdirection' });
  assert.equal(mis.code, 'misdirect', '实际=' + mis.code);
  assert.equal(mis.isDefect, false, '误导是手法，不是缺陷');
  const partial = F.of({ id: 'c5', seedEventId: 'a', payoffEventId: 'b', clueType: 'partial_payoff' });
  assert.equal(partial.code, 'partial', '实际=' + partial.code);
  assert.equal(partial.closed, false, '部分兑现不得算闭合');
});

test('模型投影形态（seedId/payoffId/declaredStatus）必须与原始线索同判', () => {
  const modelMissing = F.of({ stage: 'pending', seedId: 'ev_x', payoffId: null, declaredStatus: 'unresolved' });
  assert.equal(modelMissing.code, 'claimed_unbacked', '模型形态缺兑现端必须单列，实际=' + modelMissing.code);
  assert.equal(modelMissing.bothEndsVerifiable, false);
  const modelOk = F.of({ stage: 'resolved', seedId: 'ev_a', payoffId: 'ev_b', declaredStatus: 'resolved' });
  assert.equal(modelOk.code, 'payoff', '模型形态两端齐全必须判兑现，实际=' + modelOk.code);
  const byIndex = F.of({ seedIndex: 3, payoffIndex: 9 });
  assert.equal(byIndex.bothEndsVerifiable, true, '用下标表示的两端也必须认');
  assert.equal(F.of({ seedEventId: 'ev_x' }).code, 'open');
  assert.equal(F.of({ seedEventId: 'ev_x' }).isDefect, false);
});

test('负例 · 0 条提取必须说「缺乏处置证据」，不得宣称作品无伏笔', () => {
  const t = F.tally([]);
  assert.equal(t.total, 0);
  assert.equal(t.lacksDispositionEvidence, true);
  assert.ok(/缺乏处置证据/.test(t.summary), t.summary);
  assert.equal(t.mustNotClaim, '本作品无伏笔');
  assert.ok(!/本作品没有伏笔|无伏笔/.test(t.summary.replace('不能据此宣称作品没有伏笔', '')),
    '不得输出「作品无伏笔」的结论：' + t.summary);
});

test('负例 · 面向读者的文案不得残留 markdown 强调', () => {
  const codes = Object.keys(F.STAGES);
  const bad = codes.filter(c => /\*\*|__|`/.test(F.STAGES[c].hint) || /\*\*/.test(F.STAGES[c].zh));
  assert.deepEqual(bad, [], '这些阶段的读者文案残留 markdown：' + JSON.stringify(bad));
  const t = F.tally([]);
  assert.doesNotMatch(t.summary, /\*\*/, '0 条摘要不得含 markdown：' + t.summary);
});

test('负例 · 非对象/数字/字符串不抛异常', () => {
  for (const bad of [0, 'clue_1', [], { seedEventId: 123 }, { eventIds: 'x' }]) {
    const s = F.of(bad);
    assert.ok(s && typeof s.code === 'string');
  }
  assert.ok(F.tally(null).total === 0);
});

test('汇总只叫生命周期分布，不得自称质量分', () => {
  const t = F.tally([
    { id: 'a', seedEventId: 's', payoffEventId: 'p' },
    { id: 'b', seedEventId: 's', resolved: true },
    { id: 'c', seedEventId: 's' }
  ]);
  assert.equal(t.title, '伏笔生命周期分布');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.total, 3);
  assert.equal(t.bothEnds, 1);
  assert.equal(t.claimedUnbacked, 1);
  assert.equal(t.open, 1);
  assert.equal(t.defects, 1, '只有「缺兑现端」算缺陷');
});

test('真实数据：大奉 9 条线索必须全部判「缺兑现端」，不得判兑现', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const clues = g.clues || [];
  assert.equal(clues.length, 9, '夹具线索数');
  const contradictory = clues.filter(c => c.resolved === true && !c.payoffEventId);
  assert.equal(contradictory.length, 9, '夹具必须 9/9 都是「声称已兑现但缺兑现端」');
  const t = F.tally(clues);
  assert.equal(t.claimedUnbacked, 9, '实际=' + t.claimedUnbacked);
  assert.equal(t.byCode.payoff, undefined, '不得有任何一条被判兑现');
  assert.equal(t.bothEnds, 0, '一条两端可跳原文的都没有');
  assert.equal(t.defects, 9);
  console.log('     ' + t.summary);
});

test('真实数据：三国 4 条与西游 7 条都两端齐全（对照组）', () => {
  for (const [tag, key, n] of [['三国', 'fe42d01f3826fe8096f86614', 4],
                                ['西游', 'a065244455cfb2221bcda94a', 7]]) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    const clues = g.clues || [];
    assert.equal(clues.length, n, tag + ' 夹具线索数');
    const t = F.tally(clues);
    assert.equal(t.bothEnds, n, tag + ' 必须全部两端齐全，实际=' + t.bothEnds);
    assert.equal(t.claimedUnbacked, 0, tag + ' 不应有缺兑现端');
    assert.equal(t.defects, 0, tag + ' 不应有缺陷');
    console.log('     ' + tag + '：' + t.summary);
  }
});

test('真实数据：大奉大图谱 0 条提取必须报「缺乏处置证据」', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/aee4c99808674e4220ab0104.json', 'utf8'));
  const clues = g.clues || [];
  assert.equal(clues.length, 0, '夹具应为 0 条（计划点名的大奉 0 条提取）');
  const t = F.tally(clues);
  assert.equal(t.lacksDispositionEvidence, true);
  assert.ok(/缺乏处置证据/.test(t.summary), t.summary);
  console.log('     ' + t.summary);
});

console.log('SKY FORESHADOW STAGE ' + passed + '/' + passed);
