'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const R = require('../js/sky/sky-relation-scope.js');
const Source = require('../js/atlas/atlas-source.js');
const modelWindow = { CLAtlasSource: Source, CLSkyRelationScope: R };
vm.runInNewContext(fs.readFileSync('js/sky/sky-model.js', 'utf8'), { window: modelWindow });
const M = modelWindow.CLSkyModel;

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('七类（亲缘/师徒/同盟/敌对/利用/情感/隐秘）+ 同场 + 其他各有独立名称与解释', () => {
  const seven = ['kinship', 'mentorship', 'alliance', 'hostility', 'exploitation', 'affection', 'secret'];
  const labels = seven.map(c => R.KINDS[c].zh);
  assert.equal(new Set(labels).size, seven.length, '七类名称不得重复：' + JSON.stringify(labels));
  seven.forEach(c => assert.ok(R.KINDS[c].hint.length > 8, c + ' 必须带解释'));
  assert.ok(/不构成关系/.test(R.KINDS.copresence.hint), R.KINDS.copresence.hint);
  assert.equal(R.KINDS.copresence.zh, '同场（非关系）');
});

test('负例 · 缺字段不得默认成「有锚点」', () => {
  for (const r of [{}, { a: '甲', b: '乙' }, null, undefined, { kind: '敌对' }]) {
    const s = R.of(r);
    assert.equal(s.anchored, false, '缺字段不得判有锚点：' + JSON.stringify(r));
    assert.equal(s.mustShowPending, true, '无锚点必须显式标出');
  }
});

test('负例 · 同场不得被算成关系（计划：同场推导维持独立类型）', () => {
  const same = R.of({ a: '临安公主', b: '姜律中', kind: '同场',
    desc: '渭水之会与出征送行同场' });
  assert.equal(same.kind, 'copresence', '实际=' + same.kind);
  assert.equal(same.isCopresence, true, '同场必须被标成"不是关系"');
  const none = R.of({ a: '天枢', b: '萧月奴', kind: '同场', desc: '武林盟事件中同场，无明确直接互动' });
  assert.equal(none.isCopresence, true);
});

test('负例 · 无锚点必须显式标为待核（描述写得好不算证据）', () => {
  const pretty = R.of({ a: '许七安', b: '李妙真', kind: '盟友战友',
    desc: '天地会同道，并肩破案、互相试探后渐成挚交战友' });
  assert.equal(pretty.anchored, false, '描述写得好不得算有证据');
  assert.equal(pretty.mustShowPending, true);
  assert.equal(pretty.evidence, 'inherited-pending');
  assert.ok(/不构成.*证据|不得附任意同场引句/.test(pretty.evidenceHint), pretty.evidenceHint);
  const anchored = R.of({ a: '甲', b: '乙', kind: '敌对', quoteVerified: true });
  assert.equal(anchored.anchored, true);
  const byRef = R.of({ kind: '敌对', sourceRefs: [{ verified: true, status: 'verified',
    match: 'exact', sourceId: 's1', textHash: 'h', start: 0, end: 2, quote: '甲乙' }] });
  assert.equal(byRef.anchored, true, 'sourceRefs 形态必须认');
});

test('负例 · 全书汇总不得被默认成某时刻', () => {
  const summary = R.of({ kind: '敌对', desc: '全书从结盟到反目' });
  assert.equal(summary.scope, 'bookSummary', '实际=' + summary.scope);
  assert.equal(summary.isBookSummary, true);
  assert.ok(/不对应某一时刻/.test(summary.scopeHint), summary.scopeHint);
  assert.equal(R.scopeOf({ from: 'a', to: 'b' }).code, 'bookSummary',
    'from/to 是端点不是时段，不得判成限定时段');
  assert.equal(R.scopeOf({ chapterRange: '1-10' }).code, 'atTime');
  assert.equal(R.scopeOf({ eventIds: ['ev_1'] }).code, 'atTime');
});

test('负例 · strength 不得被当成证据强度', () => {
  const s = R.of({ kind: '敌对', strength: 0.9 });
  assert.equal(s.strength, 0.9, '来源分数要如实搬运');
  assert.equal(s.strengthIsEvidence, false, '但它不是证据强度');
  assert.equal(s.anchored, false, '高分不等于有锚点');
  assert.ok(/不是证据强度/.test(R.tally([]).note), R.tally([]).note);
});

test('负例 · 认不出的 kind 记 other，不硬塞进七类', () => {
  const o = R.of({ kind: '某种没见过的关系' });
  assert.equal(o.kind, 'other', '实际=' + o.kind);
  assert.equal(o.needsManualKind, true);
  const cases = [['父子', 'kinship'], ['师徒', 'mentorship'], ['同盟', 'alliance'],
    ['敌对', 'hostility'], ['利用', 'exploitation'], ['情感纠葛', 'affection']];
  for (const [kind, want] of cases) {
    assert.equal(R.kindOf({ kind }).code, want, kind + ' 应归 ' + want);
  }
  const sec = R.kindOf({ kind: '同僚', line: '暗线' });
  assert.equal(sec.code, 'secret', '暗线必须判隐秘');
  assert.equal(sec.baseCode, 'institutional', '同时要保留它本来的类别，实际=' + sec.baseCode);
  assert.equal(R.kindOf({ kind: '同僚', hidden: '暗中勾结' }).code, 'secret');
  assert.equal(R.kindOf({ kind: '同僚', hidden: '—', line: '明线' }).code, 'institutional');
  assert.equal(R.kindOf({ kind: '某种没见过的关系' }).code, 'other');
});

test('制度关系与泛交往单列，但必须如实说明它们**不在计划七类里**', () => {
  assert.ok(/不是计划七类之一/.test(R.KINDS.institutional.hint), R.KINDS.institutional.hint);
  assert.equal(R.kindOf({ kind: '上下级' }).code, 'institutional');
  assert.equal(R.kindOf({ kind: '君臣' }).code, 'institutional');
  assert.equal(R.kindOf({ kind: '相识' }).code, 'association');
});

test('负例 · 非对象/数字/字符串不抛异常', () => {
  for (const bad of [0, 'rel_1', [], { kind: 123 }, { sourceRefs: 'x' }]) {
    const s = R.of(bad);
    assert.ok(s && typeof s.kind === 'string');
  }
  assert.equal(R.tally(null).total, 0);
});

test('汇总只叫关系构成，不得自称质量分；0 条不得宣称没有关系', () => {
  const t = R.tally([]);
  assert.equal(t.title, '关系构成');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.lacksDispositionEvidence, true);
  assert.ok(/缺乏处置证据/.test(t.summary), t.summary);
  const t2 = R.tally([{ kind: '敌对' }, { kind: '同场' }]);
  assert.equal(t2.total, 2);
  assert.equal(t2.copresence, 1);
  assert.equal(t2.pending, 2);
});

test('C1正例 · 冻结西游稳定ID由完整关系数组计算交集、双方来源、仅A/B', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/ed3dc1255ca08fbdaae30bbd.json', 'utf8'));
  const before = JSON.stringify(g);
  const c = M.compareRelations(g, 'ch_25537390c961aa39', 'ch_1dee9e1be8a97b5f');
  assert.equal(c.ok, true, c.reason);
  assert.equal(c.a.name, '孙悟空'); assert.equal(c.b.name, '猪八戒');
  assert.deepEqual(JSON.parse(JSON.stringify(c.common.map(x => [x.id, x.name]))), [['ch_0ebf2655f1fb3db3', '陈玄奘']]);
  assert.equal(c.onlyA.length, 6); assert.equal(c.onlyB.length, 0);
  const common = c.common[0];
  assert.deepEqual(JSON.parse(JSON.stringify(common.relationsA.map(r => r.id))), ['rel_review_617180930c9aadd0']);
  assert.deepEqual(JSON.parse(JSON.stringify(common.relationsB.map(r => r.id))), ['rel_review_eca2bade5e2847a8']);
  [common.relationsA[0], common.relationsB[0]].forEach(r => {
    assert.equal(r.kind, 'mentorship'); assert.equal(r.scope, 'atTime'); assert.equal(r.evidence, 'anchored');
  });
  assert.equal(c.stats.sourceRelations, 20); assert.equal(c.stats.copresenceExcluded, 0);
  assert.equal(JSON.stringify(g), before, '适配不能改关系、人物或来源记录');
});

test('C1类型和许可范围在交集计算前生效；单人/空图保持未知边界', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/ed3dc1255ca08fbdaae30bbd.json', 'utf8'));
  const a = 'ch_25537390c961aa39', b = 'ch_1dee9e1be8a97b5f';
  const kinship = M.compareRelations(g, a, b, { kind: 'kinship' });
  assert.equal(kinship.common.length, 0, '过滤掉构成交集的师徒边后不得沿用旧交集');
  assert.equal(kinship.stats.kindFiltered > 0, true);
  const scoped = M.compareRelations(g, a, b, { scope: { relationIds: ['rel_review_617180930c9aadd0'] } });
  assert.equal(scoped.common.length, 0, '仅许可A侧关系时不能继续宣称共同');
  assert.equal(scoped.onlyA.some(x => x.id === 'ch_0ebf2655f1fb3db3'), true);
  const single = M.compareRelations(g, a, null);
  assert.equal(single.mode, 'single'); assert.equal(single.b, null);
  assert.equal(single.common.length, 0); assert.equal(single.onlyA.length, 8, '单人模式把原B作为A的一度联系人恢复出来');
  const absent = M.compareRelations({ characters: [], events: [] }, 'ch_missing', null);
  assert.equal(absent.ok, false); assert.equal(absent.reason, 'graph_or_relations_missing');
});

test('C1反例 · 同名别名、重复人物ID、双ID冲突都不猜端点归属', () => {
  const ambiguous = { characters: [
    { id: 'ch_a', entityId: 'ch_a', name: '甲', aliases: ['共享名'] },
    { id: 'ch_b', entityId: 'ch_b', name: '乙', aliases: ['共享名'] },
    { id: 'ch_c', entityId: 'ch_c', name: '丙' }
  ], relations: [{ id: 'r1', a: '共享名', b: '丙', kind: '师徒' }] };
  const amb = M.compareRelations(ambiguous, 'ch_a', 'ch_c');
  assert.equal(amb.common.length, 0); assert.equal(amb.onlyA.length, 0);
  assert.equal(amb.stats.ambiguousEndpoints, 1, '冲突owner不得回退到第一个姓名命中');
  const duplicate = { characters: [
    { id: 'ch_dup', entityId: 'ch_dup', name: '甲' },
    { id: 'ch_dup', entityId: 'ch_dup', name: '乙' }
  ], relations: [] };
  assert.equal(M.compareRelations(duplicate, 'ch_dup', null).reason, 'a_duplicate_id');
  const dual = { characters: [{ id: 'ch_a', entityId: 'ch_other', name: '甲' }], relations: [] };
  assert.equal(M.compareRelations(dual, 'ch_a', null).reason, 'a_id_entity_id_conflict');
});

test('C1反例 · 重复边只计一次，冲突关系ID、同场、自身环和A-B边不构成邻居', () => {
  const g = { characters: [
    { id: 'ch_a', entityId: 'ch_a', name: '甲' }, { id: 'ch_b', entityId: 'ch_b', name: '乙' },
    { id: 'ch_c', entityId: 'ch_c', name: '丙' }, { id: 'ch_d', entityId: 'ch_d', name: '丁' }
  ], relations: [
    { id: 'ab', a: '甲', b: '乙', kind: '师徒' },
    { id: 'same', a: '甲', b: '丙', kind: '师徒' },
    { id: 'same', a: '甲', b: '丙', kind: '师徒' },
    { id: 'conflict', a: '甲', b: '丙', kind: '师徒' },
    { id: 'conflict', a: '甲', b: '丁', kind: '师徒' },
    { id: 'bc', a: '乙', b: '丙', kind: '师徒' },
    { id: 'self', a: '甲', b: '甲', kind: '师徒' },
    { id: 'co', a: '甲', b: '丁', kind: '同场' }
  ] };
  const c = M.compareRelations(g, 'ch_a', 'ch_b');
  assert.deepEqual(JSON.parse(JSON.stringify(c.common.map(x => x.id))), ['ch_c']);
  assert.equal(c.stats.directPairEdges, 1); assert.equal(c.stats.selfEdges, 1);
  assert.equal(c.stats.copresenceExcluded, 1); assert.equal(c.stats.duplicateEdges, 1);
  assert.equal(c.stats.conflictingRelationIds, 1);
  assert.equal(c.onlyA.length, 0); assert.equal(c.onlyB.length, 0, '冲突关系ID不得伪造丁为邻居');
});

test('C1反例 · relation ID 全组先审计；类型、许可范围、同场或端点错误不能藏住冲突', () => {
  const chars = [
    { id: 'ch_a', entityId: 'ch_a', name: '甲' }, { id: 'ch_b', entityId: 'ch_b', name: '乙' },
    { id: 'ch_c', entityId: 'ch_c', name: '丙' }, { id: 'ch_d', entityId: 'ch_d', name: '丁' }
  ];
  const cases = [
    { label: '类型过滤前', options: { kind: 'mentorship' }, sibling: { id: 'r', a: '甲', b: '丁', kind: '同场' } },
    { label: '许可范围过滤前', options: { scope: { allowsRelation: rel => rel.keep === true } }, sibling: { id: 'r', a: '甲', b: '丁', kind: '师徒', keep: false } },
    { label: '端点解析过滤前', options: {}, sibling: { id: 'r', a: '未登记人物', b: '丁', kind: '师徒' } }
  ];
  cases.forEach(({ label, options, sibling }) => {
    const graph = { characters: chars, relations: [
      Object.assign({ id: 'r', a: '甲', b: '丙', kind: '师徒', keep: true }, {}), sibling
    ] };
    const result = M.compareRelations(graph, 'ch_a', 'ch_b', options);
    assert.equal(result.stats.conflictingRelationIds, 1, label + '必须先数同ID冲突');
    assert.equal(result.onlyA.some(row => row.id === 'ch_c' || row.id === 'ch_d'), false, label + '不得留下冲突组的可用半边');
  });
});

test('C1反例 · 待区分人物不可选；精确重复关系ID的依据入口不可声称唯一', () => {
  const pending = { characters: [
    { id: 'ch_a', entityId: 'ch_a', name: '甲', identityStatus: 'pending' },
    { id: 'ch_b', entityId: 'ch_b', name: '乙' }
  ], relations: [{ id: 'r1', a: '甲', b: '乙', kind: '师徒' }] };
  const people = M.relationPeople(pending).people;
  assert.equal(people.find(p => p.id === 'ch_a').selectable, false);
  assert.equal(M.compareRelations(pending, 'ch_a', 'ch_b').reason, 'a_identity_pending');
  const duplicate = { characters: [
    { id: 'ch_a', entityId: 'ch_a', name: '甲' }, { id: 'ch_b', entityId: 'ch_b', name: '乙' },
    { id: 'ch_c', entityId: 'ch_c', name: '丙' }
  ], relations: [
    { id: 'r1', a: '甲', b: '丙', kind: '师徒' }, { id: 'r1', a: '甲', b: '丙', kind: '师徒' }
  ] };
  const result = M.compareRelations(duplicate, 'ch_a', null);
  assert.equal(result.onlyA.length, 1, '集合里相同记录ID只计一次');
  assert.equal(result.onlyA[0].relationsA[0].recordUnique, false, '精确重复ID不能冒充唯一依据入口');
});

test('真实数据：大奉 2106 条关系必须**全部**无锚点，且面板须能说出来', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const rels = g.relations || [];
  assert.equal(rels.length, 2106, '夹具关系数（计划原文即 2106）');
  const t = R.tally(rels);
  assert.equal(t.anchored, 0, '实测大奉零锚点，实际=' + t.anchored);
  assert.equal(t.pending, 2106);
  assert.equal(t.allPending, true, '汇总必须标明"全部待核"');
  assert.ok(/没有任何一条有已核验的原文锚点/.test(t.summary), t.summary);
  assert.ok(t.copresence >= 97, '同场类应被分出，实际=' + t.copresence);
  assert.equal(t.atTime, 0, '实测没有任何一条限定时段，实际=' + t.atTime);
  console.log('     ' + t.summary);
  console.log('     分类：' + JSON.stringify(t.byKind));
});

test('真实数据：三国 1539 条同样零锚点（计划原文即 1539）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8'));
  const rels = g.relations || [];
  assert.equal(rels.length, 1539, '夹具关系数（计划原文即 1539）');
  const t = R.tally(rels);
  assert.equal(t.anchored, 0, '实测三国零锚点，实际=' + t.anchored);
  assert.equal(t.pending, 1539);
  assert.equal(t.allPending, true);
  console.log('     三国：' + t.summary);
});

test('真实数据：西游 20 条**全部**有锚点（对照组，证明判据不是恒假）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/a065244455cfb2221bcda94a.json', 'utf8'));
  const rels = g.relations || [];
  assert.equal(rels.length, 20, '夹具关系数');
  const t = R.tally(rels);
  assert.equal(t.anchored, 20, '西游必须全部有锚点，实际=' + t.anchored);
  assert.equal(t.pending, 0);
  assert.equal(t.allPending, false, '不得标成全部待核');
  assert.ok((t.byKind.other || 0) < rels.length, '不得全部落进 other：' + JSON.stringify(t.byKind));
  console.log('     西游：' + t.summary);
});

test('两个已发布图谱的关系数必须与计划原文一致（2106 / 1539）', () => {
  const dafeng = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const sanguo = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8'));
  assert.equal((dafeng.relations || []).length, 2106, '大奉旧关系数');
  assert.equal((sanguo.relations || []).length, 1539, '三国旧关系数');
});

console.log('SKY RELATION SCOPE ' + passed + '/' + passed);
