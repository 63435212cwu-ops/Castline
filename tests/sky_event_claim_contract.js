'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../js/sky/sky-event-claim.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('五个认识论类型各有独立名称与解释，互不同义', () => {
  const codes = ['deception', 'inference', 'claim', 'occurrence', 'unknown'];
  const labels = codes.map(c => C.KINDS[c].zh);
  assert.equal(new Set(labels).size, codes.length, '类型名不得重复：' + JSON.stringify(labels));
  codes.forEach(c => assert.ok(C.KINDS[c].hint && C.KINDS[c].hint.length > 8, c + ' 必须带解释'));
});

test('负例 · 面向读者的文案不得残留 markdown 强调', () => {
  const codes = ['deception', 'inference', 'claim', 'occurrence', 'unknown'];
  const bad = codes.filter(c => /\*\*|__|`/.test(C.KINDS[c].hint) || /\*\*/.test(C.KINDS[c].zh));
  assert.deepEqual(bad, [], '这些类型的读者文案里残留了 markdown：' + JSON.stringify(bad));
  codes.forEach(c => {
    assert.doesNotMatch(C.KINDS[c].hint, /[\n\t]/, c + ' hint 不得含控制字符');
    assert.doesNotMatch(C.KINDS[c].zh, /[\n\t]/, c + ' zh 不得含控制字符');
  });
});

test('负例 · 缺字段不得被默认成「实际发生」（未标明≠已发生）', () => {
  for (const rec of [{}, { title: '' }, null, undefined, { title: '第三章 议事' }]) {
    const s = C.classify(rec);
    assert.notEqual(s.code, 'occurrence', '空/无线索记录不得判成发生：' + JSON.stringify(rec));
    assert.equal(s.isOccurrence, false);
  }
  assert.ok(/不等于已发生/.test(C.KINDS.unknown.hint), C.KINDS.unknown.hint);
});

test('负例 · 欺骗与主张必须分开（明知虚假 ≠ 自认为真）', () => {
  const lie = C.classify({ title: '诈供成功', summary: '许七安谎称张献出卖杨珍珍并许诺免死，骗得口供' });
  assert.equal(lie.code, 'deception', '「谎称/骗得」必须判 deception，实际=' + lie.code);
  assert.equal(lie.isDeceptive, true);
  assert.equal(lie.isOccurrence, false, '欺骗性陈述不得当作发生');
  const claim = C.classify({ title: '当堂主张', summary: '王捕头请求牌票拿人' });
  assert.equal(claim.code, 'claim', '请求/主张判 claim，实际=' + claim.code);
  assert.notEqual(lie.label, claim.label, '欺瞒与主张不得显示成同一个词');
});

test('负例 · 推理必须与发生分开', () => {
  const inf = C.classify({ title: '卷宗推理', summary: '许七安从脚印等疑点推出偷情杀人案' });
  assert.equal(inf.code, 'inference', '实际=' + inf.code);
  assert.equal(inf.isOccurrence, false);
  assert.equal(inf.needsAttribution, true, '推理必须标注「这是某人的推断」');
  const occ = C.classify({ title: '张献被杀', summary: '张献死于狱中', claimType: 'occurrence' });
  assert.equal(occ.code, 'occurrence');
  assert.equal(occ.isOccurrence, true);
  assert.equal(occ.needsAttribution, false);
});

test('负例 · 「未说谎」是否定，不得判成欺骗（第一版实测的假阳性）', () => {
  const neg = C.classify({ title: '问话周百户', summary: '许七安以望气术暗中监视，问话金吾卫周百户，确认其未说谎。' });
  assert.notEqual(neg.code, 'deception', '否定语境不得判欺骗，实际=' + neg.code);
  assert.equal(neg.isDeceptive, false);
});

test('负例 · 「断言别人说谎」是判断行为，不得判成本记录的欺骗', () => {
  const judge = C.classify({ title: '审问张氏', summary: '许七安带褚采薇审张奉父子，褚采薇断言全在说谎' });
  assert.notEqual(judge.code, 'deception', '判断他人说谎不得判欺骗，实际=' + judge.code);
  assert.equal(judge.isDeceptive, false);
  const real = C.classify({ title: '诈供成功', summary: '许七安谎称张献出卖杨珍珍并许诺免死，骗得口供' });
  assert.equal(real.isDeceptive, true, '真阳性必须保留');
  const plant = C.classify({ title: '计划核心', summary: '许七安向家人提出绑走威武侯庶女栽赃周立的计划。' });
  assert.equal(plant.isDeceptive, true, '栽赃仍须判欺骗');
});

test('记录自己声明的类型优先于文字推断', () => {
  const declared = C.classify({ title: '某某谎称某事', claimType: 'occurrence' });
  assert.equal(declared.code, 'occurrence', 'declared 必须优先');
  assert.equal(declared.basis, 'declared');
  const inferred = C.classify({ title: '某某谎称某事' });
  assert.equal(inferred.basis, 'marker');
});

test('优先级：明知虚假 > 推理 > 主张', () => {
  const both = C.classify({ summary: '他怀疑对方，于是谎称自己已拿到证据' });
  assert.equal(both.code, 'deception', '同时含推理与欺骗时取欺骗，实际=' + both.code);
  const infClaim = C.classify({ summary: '他推断出真相，并向众人主张立刻抓人' });
  assert.equal(infClaim.code, 'inference', '同时含推理与主张时取推理，实际=' + infClaim.code);
});

test('负例 · 无语义线索的文本必须落 unknown，不得靠猜', () => {
  const s = C.classify({ title: '第三章 议事', summary: '众人到齐，分坐两侧。' });
  assert.equal(s.code, 'unknown', '实际=' + s.code);
  assert.equal(s.basis, 'no_marker');
  assert.equal(s.isOccurrence, false);
});

test('负例 · 非字符串/数字/对象字段不抛异常', () => {
  for (const rec of [0, 'ev_1', { title: 123, summary: null, quote: {} }, { title: [], summary: 0 }]) {
    const s = C.classify(rec);
    assert.ok(s && typeof s.code === 'string', '必须返回结构化结果');
  }
});

test('标记用文本+符号，五种类型互不相同', () => {
  const marks = [
    { title: 'a谎称b' }, { title: 'a推理b' }, { title: 'a主张b' },
    { title: 'x', claimType: 'occurrence' }, { title: '议事' }
  ].map(r => C.badge(r));
  assert.equal(new Set(marks.map(m => m.text)).size, 5, JSON.stringify(marks.map(m => m.text)));
  marks.forEach(m => assert.ok(m.mark && m.text.indexOf(m.mark) === 0));
});

test('汇总只叫类型分布，不得自称质量分', () => {
  const t = C.tally([{ title: '谎称' }, { title: '推断' }, { title: '议事' }, { title: 'x', claimType: 'occurrence' }]);
  assert.equal(t.title, '记录类型分布');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.total, 4);
  assert.equal(t.deceptive, 1);
  assert.equal(t.unknown, 1);
  assert.equal(t.byCode.occurrence, 1);
  assert.ok(/不等于已发生/.test(t.note), t.note);
});

test('isClaimOnly：主张/推理/欺骗都不是状态改变', () => {
  assert.equal(C.isClaimOnly({ title: '诈供成功' }), true);
  assert.equal(C.isClaimOnly({ title: '当堂推理' }), true);
  assert.equal(C.isClaimOnly({ title: '请求牌票' }), true);
  assert.equal(C.isClaimOnly({ title: 'x', claimType: 'occurrence' }), false);
  assert.equal(C.isClaimOnly({ title: '议事' }), false, 'unknown 不算 claim-only（它是未知，不是断言）');
});

test('真实数据：大奉 2990 条事件的类型分布可算，且未标明占多数（不得默认成发生）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const evs = g.events || [];
  assert.equal(evs.length, 2990, '夹具事件数');
  const t = C.tally(evs);
  assert.equal(t.total, 2990);
  assert.ok(t.unknown > 2000, '未标明应占多数，实际 unknown=' + t.unknown);
  assert.ok(t.byCode.occurrence === undefined || t.byCode.occurrence === 0,
    '数据里没有声明 occurrence 的记录，故不得凭空出现 occurrence');
  assert.equal(t.deceptive, 29, '实测欺骗类记录数（修正假阳性后）');
  assert.ok(t.attributed > 0, '实测存在需署名的主张/推理，实际=' + t.attributed);
  console.log('     分布：' + JSON.stringify(t.byCode) + '  deceptive=' + t.deceptive);
});

console.log('SKY EVENT CLAIM ' + passed + '/' + passed);
