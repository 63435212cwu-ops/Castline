'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const G = require('../js/sky/sky-gold-standard.js');
const T = require('../js/sky/sky-throughput.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }


test('P3.12 · 七个分层与六个报告维度各有独立名称', () => {
  const seven = ['opening', 'middle', 'turning', 'ending', 'sparseBranch',
    'crossVolumeForeshadow', 'identityHardCase'];
  assert.equal(seven.length, 7);
  const labels = seven.map(c => G.STRATA[c].zh);
  assert.equal(new Set(labels).size, 7, '七层名称不得重复：' + JSON.stringify(labels));
  seven.forEach(c => assert.ok(G.STRATA[c].hint.length > 4, c + ' 必须带解释'));
  const six = ['events', 'tasks', 'causeEdges', 'clues', 'characterStates', 'relations'];
  assert.equal(new Set(six.map(c => G.METRICS[c].zh)).size, 6);
});

test('P3.12 负例 · 七层缺层必须点名，不得默认成已覆盖', () => {
  const cov = G.coverage({});
  assert.equal(cov.coveredCount, 0, '空 fixture 不得算已覆盖');
  assert.equal(cov.complete, false);
  assert.equal(cov.missingLabels.length, 7);
  const one = G.coverage({ strata: ['identityHardCase'] });
  assert.equal(one.coveredCount, 1);
  assert.equal(one.complete, false);
  assert.ok(one.missingLabels.includes('开篇'), '实际缺=' + JSON.stringify(one.missingLabels));
  assert.ok(/尚未覆盖的分层/.test(one.hint), one.hint);
  const all = G.coverage({ strata: Object.keys(G.STRATA) });
  assert.equal(all.complete, true);
  assert.equal(all.missingLabels.length, 0);
});

test('P3.12 负例 · 候选生成者=标准答案作者必须判红（计划明令禁止）', () => {
  const same = G.independence({ producer: 'agent-A', reviewer: 'agent-A',
    reviewMethod: 'independent read', reviewers: [{ name: 'agent-A' }, { name: 'agent-B' }] });
  assert.equal(same.sameParty, true);
  assert.equal(same.ok, false, '同方必须判红');
  assert.ok(/计划明令禁止/.test(same.hint), same.hint);
  const one = G.independence({ reviewMethod: 'independent read', reviewers: [{ name: 'a' }] });
  assert.equal(one.twoReviewers, false);
  assert.equal(one.ok, false, '只有一位审阅者不得判成立');
  assert.ok(/两位/.test(one.hint), one.hint);
  const ok = G.independence({ reviewMethod: 'Independent read; no model call used',
    reviewers: [{ name: 'a' }, { name: 'b' }] });
  assert.equal(ok.ok, true, '实际=' + JSON.stringify(ok));
});

test('P3.12 负例 · 删失败样本必须判红，无论分数多高', () => {
  const cheat = G.score({ layer: 'events', total: 100, correct: 100, droppedSamples: 5 });
  assert.equal(cheat.precision, 1, '分数是满的');
  assert.equal(cheat.deletedSamples, true);
  assert.equal(cheat.ok, false, '删样本必须判红，哪怕精度 100%');
  assert.ok(/不删失败样本提高分数/.test(cheat.hint), cheat.hint);
  const clean = G.score({ layer: 'events', total: 100, correct: 99 });
  assert.equal(clean.deletedSamples, false);
  assert.equal(clean.ok, true);
});

test('P3.12 负例 · 低于下限判红；达下限不得等于「可免逐条审」', () => {
  const low = G.score({ layer: 'relations', total: 100, correct: 90 });
  assert.equal(low.meetsLoose, false);
  assert.equal(low.ok, false);
  assert.ok(/低于下限/.test(low.hint), low.hint);
  const pass = G.score({ layer: 'relations', total: 100, correct: 98 });
  assert.equal(pass.meetsStrict, true);
  assert.equal(pass.floorIsFloorNotPass, true, '下限只是下限');
  assert.ok(/不替代/.test(pass.hint), pass.hint);
  assert.equal(G.score({ layer: 'nonsense', total: 1, correct: 1 }).reason, 'unknown_layer');
  assert.equal(G.score({ layer: 'events' }).reason, 'no_counts');
});

test('P3.12 真实数据：现有金标准**已声明覆盖 0/7 层**（位置线索另记），独立性尚未成立', () => {
  const gold = JSON.parse(fs.readFileSync('tests/fixtures/narrative-gold-xiyou.json', 'utf8'));
  assert.equal(gold.benchmarkVersion, 'castline/narrative-gold/1');
  assert.ok(gold.cannotJudge && gold.cannotJudge.length, '必须有 cannotJudge');
  assert.ok(gold.evaluationLimits, '必须有 evaluationLimits');
  assert.ok(gold.missingFacts && gold.missingFacts.length, '必须有 missingFacts');
  assert.ok(/no model call/i.test(gold.reviewMethod), 'reviewMethod 必须声明无模型调用');
  const cov = G.coverage(gold);
  assert.equal(cov.coveredCount, 0, '实测未声明任何分层，实际=' + cov.coveredCount);
  assert.equal(cov.complete, false);
  assert.ok(/无法推断/.test(cov.positionNote), cov.positionNote);
  const withPos = G.coverage(Object.assign({}, gold, { sourceTotalChars: 722176 }));
  assert.deepEqual(withPos.inferable, ['middle'], '偏移 39.5% 应推断为中段，实际=' + JSON.stringify(withPos.inferable));
  assert.equal(withPos.coveredCount, 0, '位置线索**不得**计入已覆盖，实际=' + withPos.coveredCount);
  assert.ok(/故不计入覆盖/.test(withPos.positionNote), withPos.positionNote);
  const ind = G.independence(gold);
  assert.equal(ind.twoReviewers, false, '实测未记录两位审阅者');
  assert.equal(ind.ok, false, '独立性尚未成立');
  const t = G.tally(gold, []);
  assert.ok(/0\/7 个分层已覆盖/.test(t.summary), t.summary);
  console.log('     ' + t.summary);
  console.log('     ' + withPos.positionNote);
});

test('P3.12 汇总：0 份报告时不得说「没有错误」', () => {
  const t = G.tally({ strata: ['opening'] }, []);
  assert.equal(t.title, '独立金标准覆盖');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.reportedLayers, 0);
  assert.equal(t.missingLayers.length, 6, '六个维度全缺，实际=' + t.missingLayers.length);
  assert.ok(/不替代主要任务链逐条审核/.test(t.note), t.note);
});


test('P3.13 · 三个首批样本与五项记录各有独立名称', () => {
  assert.equal(new Set(Object.keys(T.BATCHES).map(k => T.BATCHES[k].zh)).size, 3);
  assert.equal(new Set(Object.keys(T.RECORDS).map(k => T.RECORDS[k].zh)).size, 5);
  assert.ok(/红孩儿之外/.test(T.BATCHES.xiyouHardEpisode.zh), T.BATCHES.xiyouHardEpisode.zh);
});

test('P3.13 负例 · 合格吞吐的分子不得含被拒产出', () => {
  const r = T.qualifiedRate({ produced: 100, rejected: 20, reworked: 5, hours: 10, readChars: 50000 });
  assert.equal(r.qualified, 80, '被拒 20 条不得计入合格，实际=' + r.qualified);
  assert.equal(r.qualifiedRate, 8, '合格吞吐 = 80/10h，实际=' + r.qualifiedRate);
  assert.equal(r.charRate, 5000);
  assert.equal(r.reviewedIndependently, false);
  assert.ok(/不能替代审核/.test(r.hint), r.hint);
  assert.equal(T.qualifiedRate({}).ok, false);
  assert.equal(T.qualifiedRate({}).reason, 'no_produced');
});

test('P3.13 负例 · 「新增节点多但主要遗漏未减」必须判暂停扩量', () => {
  const pause = T.expansionVerdict({ nodes: 100, majorOmissions: 30 }, { nodes: 500, majorOmissions: 30 });
  assert.equal(pause.verdict, 'pause', '实际=' + pause.verdict);
  assert.ok(/暂停扩量/.test(pause.hint), pause.hint);
  assert.ok(/产出量不能替代覆盖质量/.test(pause.hint), pause.hint);
  assert.equal(T.expansionVerdict({ nodes: 100, majorOmissions: 30 }, { nodes: 500, majorOmissions: 10 }).verdict, 'continue');
  const unk = T.expansionVerdict({ nodes: 100 }, { nodes: 500 });
  assert.equal(unk.verdict, 'unknown', '实际=' + unk.verdict);
  assert.ok(/不得.*默认成有效/.test(unk.hint), unk.hint);
});

test('P3.13 工期推算必须标明是推算且带不确定度区间', () => {
  const p = T.projectWorkload({ remainingChars: 600000, charRate: 5000 });
  assert.equal(p.ok, true);
  assert.equal(p.hours, 120);
  assert.equal(p.isCommitment, false, '推算不得当成承诺');
  assert.ok(p.hoursLow < p.hours && p.hours < p.hoursHigh, '必须有区间');
  assert.ok(/不是统计置信区间/.test(p.uncertaintyNote), p.uncertaintyNote);
  assert.ok(/推算/.test(p.hint), p.hint);
  assert.equal(T.projectWorkload({}).ok, false);
  assert.ok(/不得凭感觉给数字/.test(T.projectWorkload({}).hint));
});

test('P3.13 负例 · 无额外 API 不得判成停摆', () => {
  const c = T.capabilityWithoutApi({ hasSourceText: true, hasLocalTools: true });
  assert.equal(c.reviewPossible, true, '原文在本地就仍可审阅');
  assert.ok(/不得把这种情况误判为停摆/.test(c.hint), c.hint);
  const no = T.capabilityWithoutApi({ hasSourceText: false });
  assert.equal(no.reviewPossible, false);
});

test('P3.13 真实数据：首三批尚未开始，且已有台账是旧计划的', () => {
  const led = JSON.parse(fs.readFileSync('loop/state/PLAN100-LEDGER.json', 'utf8'));
  assert.equal(led.ledgerCount, 79, '实测台账 79 条');
  assert.ok(led.byStatus.rejected >= 1, '台账里有拒绝记录');
  assert.ok(led.byStatus.merged > 0, '台账里有合并记录');
  const first = led.ledgers[0];
  assert.ok(first.startedAt && first.finishedAt, '台账条目必须带起止时间');
  assert.equal(first.readChars, undefined, '台账没有阅读字符字段');
  assert.equal(first.pageSuccessRate, undefined, '台账没有页面成功率字段');
  const t = T.tally([]);
  assert.equal(t.batches, 0);
  assert.ok(/首三批校准尚未开始/.test(t.summary), t.summary);
  assert.ok(/尚无样本/.test(t.summary), '不得说成「吞吐为零」：' + t.summary);
  assert.equal(t.missingRecords.length, 5, '五项记录全缺，实际=' + t.missingRecords.length);
  console.log('     台账 79 条（' + JSON.stringify(led.byStatus) + '），但无阅读字符/页面成功率字段');
});

test('P3.13 汇总：未声明独立复核的批次必须被点出来', () => {
  const t = T.tally([
    { produced: 10, rejected: 2, hours: 2, readChars: 1000, independentReview: true },
    { produced: 10, rejected: 0, hours: 2, readChars: 1000 }
  ]);
  assert.equal(t.batches, 2);
  assert.equal(t.produced, 20);
  assert.equal(t.rejected, 2);
  assert.equal(t.unindependentlyReviewed, 1, '第二批未声明独立复核，实际=' + t.unindependentlyReviewed);
  assert.ok(/未声明独立复核/.test(t.summary), t.summary);
  assert.ok(/分子只算合格产出/.test(t.note), t.note);
});

console.log('SKY GOLD + THROUGHPUT ' + passed + '/' + passed);
