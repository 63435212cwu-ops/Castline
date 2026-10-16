'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const code = fs.readFileSync(path.join(__dirname, '..', 'js', 'tree', 'storylines.js'), 'utf8');
let count = 0;
function test(name, run) { run(); count++; process.stdout.write('PASS ' + name + '\n'); }
function load() {
  const ctx = { window: {}, console };
  vm.runInNewContext(code, ctx);
  return ctx.window.CLStory;
}

function mkGraph(events, lines, meta) {
  return {
    title: '契约样例', synopsis: 's',
    characters: [{ name: '甲', importance: 90 }, { name: '乙', importance: 50 }, { name: '丙', importance: 20 }],
    events: events.map(function (o) {
      return { order: o, chapter: '第' + Math.ceil(o / 8) + '章', title: '事件' + o, kind: '冲突', summary: '摘要' + o, characters: ['甲', o % 2 ? '乙' : '丙'], quote: '' };
    }),
    storylines: lines, meta: meta || {}
  };
}
function range(a, b) { const out = []; for (let i = a; i <= b; i++) out.push(i); return out; }
function autoLines(n, per, start) {
  const lines = [];
  for (let k = 0; k < n; k++) lines.push({ id: 'auto-main-' + (k + 1), kind: '主线', name: '全书阶段' + (k + 1), events: range(start + k * per, start + (k + 1) * per - 1) });
  return lines;
}
function covered(tree) {
  const set = new Set();
  tree.threads.forEach(function (t) { t.events.forEach(function (i) { set.add(i); }); });
  return set;
}

test('全真实线：goal 声明齐全 → all-declared，零降权', () => {
  const S = load();
  const G = mkGraph(range(1, 24), [
    { id: 'm1', kind: '主线', name: '求长生篇', goal: '求不老脱阎，拒绝低位与控制', events: range(1, 12) },
    { id: 'm2', kind: '主线', name: '取经篇', goal: '赴灵山得真经并回朝缴旨', events: range(13, 24), handoff_from: 'm1', handoff_reason: '许七安归队' }
  ]);
  const t = S.analyze(G);
  assert.strictEqual(t.lineHonesty.verdict, 'all-declared');
  assert.strictEqual(t.lineHonesty.mechanical, 0);
  assert.strictEqual(t.stats.declaredLines, 2);
  assert.strictEqual(t.stats.mechLines, 0);
  t.threads.forEach(function (th) {
    assert.strictEqual(th.objective, 'declared');
    assert.strictEqual(th.autoSegment, false);
    assert.ok(th.objectiveText.length >= 6, '目标文本透传');
  });
  assert.ok(!t.warn.some(function (w) { return w.indexOf('诚实分层') >= 0; }), '无目标缺失不附加分层警告');
});

test('全机械线：无 goal、等长、首尾相接 → all-mechanical（纯结构指纹，无 meta 佐证）', () => {
  const S = load();
  const lines = autoLines(6, 5, 1);
  const G = mkGraph(range(1, 30), lines);
  const h = S.honestyOf(G);
  assert.strictEqual(h.verdict, 'all-mechanical');
  assert.strictEqual(h.structural, true);
  assert.strictEqual(h.provenanceDerived, false);
  assert.strictEqual(h.mechanical, 6);
  const t = S.analyze(G);
  assert.strictEqual(t.stats.mechLines, 6);
  t.threads.forEach(function (th) { assert.strictEqual(th.autoSegment, true); assert.strictEqual(th.objective, 'none'); });
  assert.ok(t.warn.some(function (w) { return w.indexOf('自动分段') >= 0; }), '分层警告如实出现');
});

test('混合：真实任务线保持原权重，机械段单独计数 → mixed', () => {
  const S = load();
  const lines = [{ id: 'd1', kind: '主线', name: '税银案', goal: '查清税银失踪并救回监下眷属', events: range(1, 10) }]
    .concat(autoLines(4, 10, 11));
  const G = mkGraph(range(1, 50), lines);
  const h = S.honestyOf(G);
  assert.strictEqual(h.verdict, 'mixed');
  assert.strictEqual(h.declared, 1);
  assert.strictEqual(h.mechanical, 4);
  const t = S.analyze(G);
  const bySrc = {};
  t.threads.forEach(function (th) { bySrc[th.sourceId] = th; });
  assert.strictEqual(bySrc['d1'].autoSegment, false);
  assert.strictEqual(bySrc['d1'].objective, 'declared');
  ['auto-main-1', 'auto-main-2', 'auto-main-3', 'auto-main-4'].forEach(function (id) {
    assert.strictEqual(bySrc[id].autoSegment, true, id + ' 应为机械分段');
  });
  assert.strictEqual(t.stats.declaredLines, 1);
  assert.strictEqual(t.stats.mechLines, 4);
});

test('goal 异常值逐项分类：空串/null/对象/数组/数字/过短 → none 且 reason 标明类别', () => {
  const S = load();
  const cases = [
    ['', '空串'], [null, '缺席'], [undefined, '缺席'], [{ text: '求长生' }, '类型异常'],
    [['求长生'], '类型异常'], [42, '类型异常'], ['短', '仅 1 字'], ['ab c', '不足']
  ];
  cases.forEach(function (c) {
    const r = S.objectiveOf({ id: 'x', goal: c[0] });
    assert.strictEqual(r.state, 'none', JSON.stringify(c[0]) + ' 应判 none');
    assert.ok(r.reason.indexOf(c[1]) >= 0, 'reason「' + r.reason + '」应含「' + c[1] + '」');
  });
  const ok = S.objectiveOf({ goal: '前往灵山求取真经' });
  assert.strictEqual(ok.state, 'declared');
  assert.strictEqual(ok.text, '前往灵山求取真经');
});

test('goal 为对象的线在树中如实降级为 unknown/none，不冒充任务线', () => {
  const S = load();
  const lines = autoLines(3, 5, 1);
  lines[0].goal = { text: '伪装成对象的目标' };
  lines[1].goal = '';
  const G = mkGraph(range(1, 15), lines);
  const h = S.honestyOf(G);
  const l0 = h.lines.filter(function (l) { return l.id === 'auto-main-1'; })[0];
  assert.strictEqual(l0.objective, 'none');
  assert.ok(l0.reason.indexOf('类型异常') >= 0);
  assert.strictEqual(h.mechanical, 3);
});

test('事件守恒：分层标注不丢任何剧情点（树事件数 == 输入事件数，来源引用全部在线）', () => {
  const S = load();
  const fixtures = [
    mkGraph(range(1, 30), autoLines(6, 5, 1)),
    mkGraph(range(1, 50), [{ id: 'd1', kind: '主线', name: '税银案', goal: '查清税银失踪并救回监下眷属', events: range(1, 10) }].concat(autoLines(4, 10, 11)))
  ];
  fixtures.forEach(function (G, fi) {
    const t = S.analyze(G, { force: true });
    assert.strictEqual(t.events.length, G.events.length, 'fixture ' + fi + ' 树事件数守恒');
    const cov = covered(t);
    G.storylines.forEach(function (l) {
      l.events.forEach(function (o) { assert.ok(cov.has(o - 1), 'fixture ' + fi + ' 来源引用 order ' + o + ' 必须仍在某条线上'); });
    });
    t.threads.forEach(function (th) {
      th.events.forEach(function (i) { assert.ok(i >= 0 && i < t.events.length, '引用下标合法'); });
    });
  });
});

test('逐字节确定性：同图两次 analyze 输出完全一致', () => {
  const S = load();
  const G = mkGraph(range(1, 50), [{ id: 'd1', kind: '主线', name: '税银案', goal: '查清税银失踪并救回监下眷属', events: range(1, 10) }].concat(autoLines(4, 10, 11)));
  const a = JSON.stringify(S.analyze(G, { force: true }));
  const b = JSON.stringify(S.analyze(G, { force: true }));
  assert.strictEqual(a, b);
});

test('主线与任务有机械关联：taskIds 按共享事件 join，taskGoalCount 只数已声明目标', () => {
  const S = load();
  const G = mkGraph(range(1, 40), autoLines(2, 20, 1));
  G.tasks = [
    { id: 'tk-a', name: '有目标', goal: '查清税银去向', eventIds: [1, 2, 3] },
    { id: 'tk-b', name: '无目标', goal: '', eventIds: [6, 7] },
    { id: 'tk-c', name: '越界任务', goal: '不该被第 1 块连上', eventIds: [30, 31] }
  ];
  const t = S.analyze(G, { force: true });
  const th = t.threads || [];
  const first = th[0], second = th[1];
  assert.strictEqual(first.sourceId, 'auto-main-1');
  assert.strictEqual(second.sourceId, 'auto-main-2');
  assert.ok(first && second, '两条主线都应在树上');
  const json = function (v) { return JSON.stringify(Array.from(v || []).slice().sort()); };
  assert.strictEqual(json(first.taskIds), json(['tk-a', 'tk-b']),
    '第 1 块应连到 tk-a 与 tk-b；实际=' + JSON.stringify(first.taskIds));
  assert.strictEqual(first.taskGoalCount, 1, '**只数已声明目标**：tk-b 的 goal 为空，不得计入');
  assert.strictEqual(json(second.taskIds), json(['tk-c']), '第 2 块应连到越界的 tk-c');
  assert.strictEqual(second.taskGoalCount, 1);
});

test('主线连不上任何任务时如实为 0，不编造目标', () => {
  const S = load();
  const G = mkGraph(range(1, 30), autoLines(2, 15, 1));
  G.tasks = [];
  const t = S.analyze(G, { force: true });
  for (const x of (t.threads || [])) {
    assert.strictEqual(JSON.stringify(Array.from(x.taskIds || [])), '[]', '没有任务时 taskIds 必须是空数组');
    assert.strictEqual(x.taskGoalCount, 0, '不得编造目标数');
    assert.strictEqual(x.objective, 'none', '目标状态必须保持 none（诚实）');
  }
});

test('覆盖率口径必须可区分：人物覆盖率 ≠ 事件覆盖率（实测大奉曾把后者误读成前者）', () => {
  const S = load();
  const G = mkGraph(range(1, 20), [
    { id: 'a1', kind: '主线', name: '甲线', events: range(1, 5) },
    { id: 'a2', kind: '主线', name: '乙线', events: range(6, 10) }
  ]);
  const t = S.analyze(G, { force: true });
  const st = t.stats;
  assert.ok('coverage' in st, '保留原字段 coverage（人物覆盖率）');
  assert.ok('eventCoverage' in st, '必须新增 eventCoverage（事件覆盖率）');
  assert.strictEqual(st.eventCovered, 10, '归类事件数应为 10');
  assert.strictEqual(st.eventCoverage, 0.5, '事件覆盖率应为 0.5');
  assert.strictEqual(st.unassignedEvents, 10, '未归属应为 20-10=10（如实暴露，不粉饰）');
});

test('事件覆盖率去重：同一事件被两条线都引用时只计一次', () => {
  const S = load();
  const G = mkGraph(range(1, 20), [
    { id: 'd1', kind: '主线', name: '甲', events: range(1, 5) },
    { id: 'd2', kind: '主线', name: '乙', events: range(1, 5) }
  ]);
  const t = S.analyze(G, { force: true });
  assert.strictEqual(t.stats.eventCovered, 5, '重叠引用必须去重，不得把同事件算两次');
});

test('来源线未覆盖的事件必须如实计数并 warn（runStrict 路径曾静默）', () => {
  const S = load();
  const G = mkGraph(range(1, 100), [{ id: 'm1', kind: '主线', name: '阶段一', lead: '甲',
                                      events: range(1, 10) }]);
  const t = S.analyze(G, { force: true });
  const hit = (t.warn || []).filter(function (w) { return /不在任何故事线里/.test(w); });
  assert.strictEqual(hit.length, 1, '必须有一条「未覆盖事件」的 warn；实际=' + JSON.stringify(t.warn));
  assert.ok(/90/.test(hit[0]), '必须报出真实未覆盖数 90（100-10）；实际=' + hit[0]);
  assert.strictEqual(t.threads.length, 1, '不得为凑覆盖而臆造故事线');
  const cov = t.threads.reduce(function (a, x) { return a + (x.events || []).length; }, 0);
  assert.strictEqual(cov, 10, '覆盖数必须仍是来源声明的 10，不得虚增');
});

test('全覆盖时不得出现未覆盖 warn（反例：不能无条件报警）', () => {
  const S = load();
  const G = mkGraph(range(1, 20), [{ id: 'm1', kind: '主线', name: '全', lead: '甲',
                                     events: range(1, 20) }]);
  const t = S.analyze(G, { force: true });
  const hit = (t.warn || []).filter(function (w) { return /不在任何故事线里/.test(w); });
  assert.strictEqual(hit.length, 0, '全覆盖时不得报警；实际=' + JSON.stringify(t.warn));
});

process.stdout.write('STORYLINE-HONESTY OK · ' + count + ' contracts\n');
