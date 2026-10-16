'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../js/sky/sky-causal-type.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('八个类型档各有独立名称与解释，互不同义', () => {
  const codes = ['trigger', 'necessary', 'contributing', 'believed', 'inferred',
    'sequence', 'attribution', 'counterfactual', 'unknown'];
  const labels = codes.map(c => C.TYPES[c].zh);
  assert.equal(new Set(labels).size, codes.length, '名称不得重复：' + JSON.stringify(labels));
  codes.forEach(c => assert.ok(C.TYPES[c].hint.length > 8, c + ' 必须带解释'));
});

test('负例 · 缺字段不得默认成「直接触发」', () => {
  for (const e of [{}, { description: '' }, null, undefined, { id: 'cx' }]) {
    const s = C.of(e);
    assert.notEqual(s.code, 'trigger', '缺字段不得判触发：' + JSON.stringify(e));
    assert.equal(s.isEstablishedCausality, false);
  }
});

test('负例 ·「随后/相邻」不得判成因果（计划原句）', () => {
  const seq = C.of({ description: '两军对阵之后，翌日魏军撤退' });
  assert.equal(seq.code, 'sequence', '实际=' + seq.code);
  assert.equal(seq.isEstablishedCausality, false, '纯先后不得算已成立因果');
  assert.equal(seq.mustNotBeCausalEdge, true, '纯先后不应作为因果边保留');
  assert.ok(/不足以建立因果/.test(C.TYPES.sequence.hint), C.TYPES.sequence.hint);
});

test('负例 · 归功/评价必须单列，且不得留在因果网络里', () => {
  const credit = C.of({ description: '吴既平而君臣皆贺，晋主执杯流涕归功于羊祜',
    quote: '朝廷闻吴已平，君臣皆贺，上寿。', basis: 'inference' });
  assert.equal(credit.code, 'attribution', '实际=' + credit.code);
  assert.equal(credit.isEstablishedCausality, false);
  assert.equal(credit.mustNotBeCausalEdge, true,
    '计划明令：不能给明显错方向边降置信度后继续保留');
  assert.ok(/不是因果机制/.test(C.TYPES.attribution.hint), C.TYPES.attribution.hint);
  const zan = C.of({ description: '晋主执杯流涕曰：此羊太傅之功也' });
  assert.equal(zan.code, 'attribution', '实际=' + zan.code);
});

test('负例 · 反事实只能当审阅问题，不得成为事实边', () => {
  const cf = C.of({ description: '若无陆抗之守，则襄阳早失' });
  assert.equal(cf.code, 'counterfactual', '实际=' + cf.code);
  assert.equal(cf.mustNotBeCausalEdge, true);
  assert.equal(cf.isEstablishedCausality, false);
  assert.ok(/不是已发生的事实/.test(C.TYPES.counterfactual.hint), C.TYPES.counterfactual.hint);
});

test('负例 · 人物认为 ≠ 分析推测（混同会把人物偏见读成事实）', () => {
  const believed = C.of({ description: '孙皓疑陆抗通敌，误以为其有异心' });
  const inferred = C.of({ description: '由粮尽可见其军不能久持' });
  assert.equal(believed.code, 'believed', '实际=' + believed.code);
  assert.equal(inferred.code, 'inferred', '实际=' + inferred.code);
  assert.notEqual(believed.label, inferred.label, '两者不得显示成同一个词');
  assert.equal(believed.needsAttribution, true);
  assert.equal(inferred.needsAttribution, true);
  assert.equal(believed.isEstablishedCausality, false);
});

test('写出机制的三类才算已成立因果', () => {
  const trig = C.of({ description: '华核被叱出，孙皓于是令陆抗屯江口图襄阳' });
  assert.equal(trig.code, 'trigger', '实际=' + trig.code);
  assert.equal(trig.isEstablishedCausality, true);
  const nec = C.of({ description: '唯有先取荆州，方能图巴蜀' });
  assert.equal(nec.code, 'necessary', '实际=' + nec.code);
  const con = C.of({ description: '此举为日后北伐创造条件，推动朝议转向' });
  assert.equal(con.code, 'contributing', '实际=' + con.code);
});

test('边自己声明的类型优先于文字推断', () => {
  const d = C.of({ description: '某某归功于他', causalType: 'trigger' });
  assert.equal(d.code, 'trigger', 'declared 必须优先');
  assert.equal(d.basis, 'declared');
  const i = C.of({ description: '某某归功于他' });
  assert.equal(i.basis, 'marker');
});

test('负例 · 非对象/数字/字符串不抛异常', () => {
  for (const bad of [0, 'cx_1', [], { description: 123 }, { quote: {} }]) {
    const s = C.of(bad);
    assert.ok(s && typeof s.code === 'string');
  }
});

test('负例 · 叙述者插诗不得把一条边判成归功（实测 6/7 假阳性的来源）', () => {
  const poem = C.of({
    description: '袁绍吐血而死，审配逢纪遂就榻前立袁尚为主',
    quote: '绍翻身大叫一声，又吐血斗余而死。后人有诗曰：“累世公卿立大名……”'
  });
  assert.notEqual(poem.code, 'attribution', '叙述者插诗不得判归功，实际=' + poem.code);
  const real = C.of({ description: '吴既平而君臣皆贺，晋主执杯流涕归功于羊祜' });
  assert.equal(real.code, 'attribution', '真归功必须保留，实际=' + real.code);
});

test('负例 · 光杆「乃」不得判成纯先后（文言里它常是「于是」）', () => {
  const causal = C.of({ description: '曹操发矫诏，袁绍得之乃起兵会盟' });
  assert.notEqual(causal.code, 'sequence', '「乃」不得单独判先后，实际=' + causal.code);
  const seq = C.of({ description: '孔明病亡之后蜀军按遗命退兵' });
  assert.equal(seq.code, 'sequence', '显式时序词必须判先后，实际=' + seq.code);
});

test('负例 · 面向读者的文案不得残留 markdown 强调', () => {
  const codes = Object.keys(C.TYPES);
  const bad = codes.filter(c => /\*\*|__|`/.test(C.TYPES[c].hint) || /\*\*/.test(C.TYPES[c].zh));
  assert.deepEqual(bad, [], '这些类型的读者文案残留 markdown：' + JSON.stringify(bad));
  codes.forEach(c => {
    assert.doesNotMatch(C.TYPES[c].hint, /[\n\t]/, c + ' hint 不得含控制字符');
    assert.doesNotMatch(C.TYPES[c].zh, /[\n\t]/, c + ' zh 不得含控制字符');
  });
});

test('端点核对：未解析与冲突必须报出来', () => {
  assert.equal(C.endpointsOk({ fromEventId: 'a', toEventId: 'b' }).both, true);
  assert.equal(C.endpointsOk({ fromEventId: 'a' }).both, false);
  assert.equal(C.endpointsOk({ fromEventId: 'a', toEventId: 'b', resolved: false }).unresolved, true);
  assert.equal(C.endpointsOk({ referenceStatus: 'unresolved_or_conflicting' }).unresolved, true);
});

test('汇总只叫类型分布，不得自称因果质量分', () => {
  const t = C.tally([{ description: '于是攻城' }, { description: '随后撤退' },
    { description: '归功于他' }, {}]);
  assert.equal(t.title, '因果类型分布');
  assert.equal(t.isCausalityScore, false);
  assert.equal(t.total, 4);
  assert.equal(t.byCode.sequence, 1);
  assert.equal(t.byCode.attribution, 1);
  assert.equal(t.mustNotBeEdge, 2, '纯先后 + 归功都算不应保留');
  assert.ok(/都不足以建立因果/.test(t.note), t.note);
});

test('真实数据：三国 339 条边必须能分类，且计划点名的羊祜边必须判归功', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8'));
  const edges = g.causeEdges || [];
  assert.equal(edges.length, 339, '夹具边数');
  const t = C.tally(edges);
  assert.equal(t.total, 339);
  assert.ok(t.established > 0, '必须有一批写出机制的边');
  assert.ok(t.mustNotBeEdge > 0, '必须检出不应保留的边');
  const target = edges.filter(e => e.id === 'cx_luoyang_to_credit');
  assert.equal(target.length, 1, '夹具必须含该边');
  const s = C.of(target[0]);
  assert.equal(s.code, 'attribution',
    'cx_luoyang_to_credit 必须判归功/评价，实际=' + s.code + '（marker=' + s.marker + '）');
  assert.equal(s.mustNotBeCausalEdge, true);
  console.log('     分布：' + JSON.stringify(t.byCode));
  console.log('     ' + t.summary);
});

test('真实数据：西游 140 条边同样可分类（跨书一致）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/a065244455cfb2221bcda94a.json', 'utf8'));
  const edges = g.causeEdges || [];
  const t = C.tally(edges);
  assert.equal(t.total, edges.length);
  assert.ok(t.byCode.unknown === undefined || t.byCode.unknown < t.total, '不得全部落进未标明');
  console.log('     西游：' + t.summary);
});

console.log('SKY CAUSAL TYPE ' + passed + '/' + passed);
