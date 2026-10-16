'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const T = require('../js/sky/sky-task-status.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('七个计划内状态各有独立中文名与解释，互不同义', () => {
  const codes = ['completed', 'failed', 'blocked', 'planned', 'ongoing', 'partial', 'unknown'];
  const labels = codes.map(c => T.STATUS[c].zh);
  assert.equal(new Set(labels).size, codes.length, '状态中文名不得重复：' + JSON.stringify(labels));
  codes.forEach(c => assert.ok(T.STATUS[c].hint && T.STATUS[c].hint.length > 6, c + ' 必须有解释，不能只给一个词'));
});

test('planned 不是进行中（计划原句），两者必须可区分', () => {
  const p = T.of({ status: 'planned' }), o = T.of({ status: 'ongoing' });
  assert.notEqual(p.label, o.label);
  assert.ok(/尚未开始|不是进行中/.test(T.STATUS.planned.hint), 'planned 的解释必须点明它不是进行中');
  assert.equal(p.isTerminal, false);
  assert.equal(o.isTerminal, false);
});

test('partial 必须说明「可能是阶段结果或材料不全，需看记录」', () => {
  const h = T.STATUS.partial.hint;
  assert.ok(/阶段|材料不全/.test(h), 'partial 解释必须点明两种可能：' + h);
  assert.ok(/不能当已完成|需看记录/.test(h), 'partial 不得被当成已完成：' + h);
  const s = T.of({ status: 'partial' });
  assert.equal(s.isTerminal, false, 'partial 不是终局');
  assert.equal(s.impliesSuccess, false);
});

test('负例 · 缺失不默认成功：无 status / 未知码都不得变成已完成', () => {
  for (const t of [{}, { status: '' }, { status: null }, { status: 'weird_future_code' }, null, undefined]) {
    const s = T.of(t);
    assert.equal(s.code, 'unknown', 'code=' + s.code);
    assert.equal(s.isTerminal, false);
    assert.equal(s.impliesSuccess, false);
    assert.ok(/未提供/.test(s.label), 'label=' + s.label);
  }
});

test('负例 · 标了 completed 但无结果事件锚点，必须降级（终局需结果事件和原文）', () => {
  const noAnchor = T.of({ status: 'completed', outcome: '吏员宣布税银已追回' });
  assert.notEqual(noAnchor.code, 'completed', '无锚点不得保持 completed');
  assert.equal(noAnchor.code, 'unanchored');
  assert.equal(noAnchor.isTerminal, false);
  assert.equal(noAnchor.downgradedFrom, 'completed');
  assert.ok(/结果事件/.test(noAnchor.downgradeReason));
  const anchored = T.of({ status: 'completed', outcomeEventId: 'ev_x', outcome: '…' });
  assert.equal(anchored.code, 'completed');
  assert.equal(anchored.isTerminal, true);
});

test('原状态码必须保留（中文显示不改变含义）', () => {
  const s = T.of({ status: 'completed', outcome: '有描述' });
  assert.equal(s.rawStatus, 'completed', '降级也必须保留原状态码');
  assert.equal(s.preservesRawStatus, true);
  const f = T.of({ status: 'failed' });
  assert.equal(f.rawStatus, 'failed');
  assert.equal(f.isTerminal, true);
  assert.equal(f.impliesSuccess, false, 'failed 绝不能意味着成功');
});

test('负例 · 播放结束不得让任务变成终局（播放结束≠任务完成）', () => {
  const done = T.of({ status: 'ongoing' });
  const cmp = T.playbackVsTask(true, done);
  assert.equal(cmp.playbackFinished, true);
  assert.equal(cmp.taskCompleted, false, '播放到末尾不得把 ongoing 读成完成');
  assert.equal(cmp.mustNotInfer, true);
  assert.ok(/不代表任务达成/.test(cmp.note), cmp.note);
  const term = T.of({ status: 'completed', outcomeEventId: 'ev_y' });
  const cmp2 = T.playbackVsTask(false, term);
  assert.equal(cmp2.playbackFinished, false);
  assert.equal(cmp2.taskCompleted, true, '任务终局只由记录里的锚点决定');
});

test('五字段完整度与状态分开报（完整≠成功，缺字段≠失败）', () => {
  const full = T.of({ status: 'ongoing', goal: 'a', obstacle: 'b', action: 'c', outcome: 'd', cost: 'e' });
  assert.equal(full.fields.complete, true);
  assert.equal(full.isTerminal, false, '五字段齐全也不代表完成');
  const sparse = T.of({ status: 'completed', outcomeEventId: 'ev_z' });
  assert.equal(sparse.fields.complete, false);
  assert.equal(sparse.isTerminal, true, '缺字段也不妨碍它是终局');
  assert.deepEqual(sparse.fields.missing, ['goal', 'obstacle', 'action', 'outcome', 'cost']);
});

test('汇总只叫状态分布，不得自称完成率', () => {
  const t = T.tally([{ status: 'completed', outcomeEventId: 'ev_1' }, { status: 'completed', outcome: '描述' }, {}]);
  assert.equal(t.title, '任务状态分布');
  assert.equal(t.isCompletionRate, false);
  assert.equal(t.total, 3);
  assert.equal(t.byCode.completed, 1);
  assert.equal(t.byCode.unanchored, 1);
  assert.equal(t.byCode.unknown, 1);
  assert.ok(/不是完成率/.test(t.note), t.note);
});

test('真实数据：大奉 24 条任务的分布，且 11 条 completed 都必须有锚点', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const tasks = g.tasks || [];
  assert.equal(tasks.length, 24, '夹具任务数');
  const t = T.tally(tasks);
  assert.equal(t.total, 24);
  assert.equal(t.byCode.completed, 11, '11 条 completed 都带 outcomeEventId，应保持终局');
  assert.equal(t.byCode.failed, 1);
  assert.equal(t.byCode.unknown, 12);
  assert.equal(t.terminal, 12, '终局 = completed + failed');
  const unknowns = tasks.filter(x => (x.status || '') === '' || x.status === 'unknown');
  assert.equal(unknowns.length, 12);
  unknowns.forEach(x => assert.equal(T.of(x).isTerminal, false, '未提供状态不得算终局'));
});

console.log('SKY TASK STATUS ' + passed + '/' + passed);
