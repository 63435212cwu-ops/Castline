'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const W = require('../js/sky/sky-world-object.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('三类（规则/地点/物件）+ 未标明各有独立名称与解释', () => {
  const three = ['rule', 'place', 'item'];
  const labels = three.map(c => W.KINDS[c].zh);
  assert.equal(new Set(labels).size, three.length, '名称不得重复：' + JSON.stringify(labels));
  three.forEach(c => assert.ok(W.KINDS[c].hint.length > 8, c + ' 必须带解释'));
  assert.ok(/提及不等于到达/.test(W.KINDS.place.hint), W.KINDS.place.hint);
});

test('负例 · 地点「提及」不得算到达（计划原句：地点提及≠到达）', () => {
  const mention = W.of({ kind: 'place', name: '荆州' }, { text: '众议荆州之事，孔明曰可取之' });
  assert.equal(mention.place, 'mentioned', '实际=' + mention.place);
  assert.equal(mention.isArrival, false, '提及不得算到达');
  assert.equal(mention.mentionOnly, true);
  const arrive = W.of({ kind: 'place', name: '荆州' }, { text: '玄德遂至荆州' });
  assert.equal(arrive.place, 'arrived', '实际=' + arrive.place);
  assert.equal(arrive.isArrival, true);
  assert.equal(W.of({ kind: 'place', name: '某地', arrived: true }).isArrival, true);
  assert.equal(W.of({ kind: 'place', name: '某地', mentionedOnly: true }).isArrival, false);
});

test('负例 · 物件四态必须分开，不得合并成一条物品链', () => {
  const st = W.itemStates({}, '孙坚匿玉玺，后为袁术所夺，遂归袁绍');
  assert.equal(st.states.hold || st.states.lose || st.states.transfer, true, '至少要认出一态');
  assert.ok(Array.isArray(st.codes), '必须给出命中的态列表');
  const holdOnly = W.itemStates({}, '他执刀而立');
  assert.equal(holdOnly.states.hold, true, '持有必须认出来');
  assert.equal(holdOnly.states.transfer, false, '不得凭空判交接');
  assert.equal(holdOnly.states.lose, false, '不得凭空判丢失');
  const empty = W.itemStates({}, '');
  assert.deepEqual(empty.codes, [], '空上下文不得判出任何态');
  assert.equal(empty.label, '状态未标明');
});

test('负例 · 制度「宣称」不得算「已执行」，人物误解必须单列', () => {
  const declared = W.institutionState({}, '朝廷下诏，令各路诸侯勤王');
  assert.equal(declared.code, 'declared', '只有诏令必须判宣称，实际=' + declared.code);
  assert.ok(/宣称不等于已执行/.test(declared.hint), declared.hint);
  const executed = W.institutionState({}, '朝廷下诏，遂即奉行，各路起兵');
  assert.equal(executed.code, 'executed', '实际=' + executed.code);
  const misread = W.institutionState({}, '他误以为朝廷已下诏赦免');
  assert.equal(misread.code, 'misunderstood', '人物误解必须单列，实际=' + misread.code);
  assert.ok(/不是制度本身的状态/.test(misread.hint), misread.hint);
  assert.equal(W.institutionState({}, '此处无相关文字').code, 'unknown');
});

test('负例 · 没有约束的设定不得算「能解释行动」', () => {
  const deco = W.explainsAction({ text: '此剑名曰青龙偃月，重八十二斤' });
  assert.equal(deco.ok, false, '纯装饰描述不得算能解释行动');
  assert.equal(deco.reason, 'no_constraint');
  assert.ok(/术语装饰层/.test(deco.hint), deco.hint);
  const real = W.explainsAction({ text: '武夫九品之下不得入朝，唯有炼精境方能领兵' });
  assert.equal(real.ok, true, '有约束+有行动必须算，实际=' + real.reason);
  const noAction = W.explainsAction({ text: '任何人不得越过此界' });
  assert.equal(noAction.ok, false, '有约束无行动仍不算');
  assert.equal(noAction.reason, 'no_action');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'place_1', [], { kind: 123 }, null, undefined]) {
    const s = W.of(bad);
    assert.ok(s && typeof s.kind === 'string');
  }
  assert.equal(W.tally(null).total, 0);
  assert.ok(W.itemStates(null, null).codes.length === 0);
});

test('负例 · 0 条必须说「从未被要求过」，不得宣称作品没有设定', () => {
  const t = W.tally([]);
  assert.equal(t.title, '世界设定构成');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.neverRequested, true);
  assert.ok(/从未被要求提取过/.test(t.summary), t.summary);
  assert.equal(t.mustNotClaim, '本作品没有世界规则或物件');
  assert.ok(/没有依据就不扩出地图或物品链/.test(t.note), t.note);
});

test('真实数据：管线已开始产出世界设定（第 14 轮提示词改造后这一层不得再为空）', () => {
  const graphs = ['1063b17ca65ec1b76f30e460', 'fe42d01f3826fe8096f86614', 'a065244455cfb2221bcda94a'];
  for (const key of graphs) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    for (const f of ['rules', 'items', 'places', 'locations', 'worldRules', 'settings', 'worldSettings']) {
      assert.ok(!(f in g), key + ' 图谱不应含 ' + f + ' 字段');
    }
  }
  const fsx = require('node:fs');
  const dir = 'loop/state/out';
  const files = fsx.readdirSync(dir).filter(f => /^read_.*\.candidate\.json$/.test(f));
  assert.ok(files.length >= 150, '管线产物应有 150+ 个，实际=' + files.length);
  let found = 0;
  let withWorld = 0;
  for (const f of files) {
    let c; try { c = JSON.parse(fsx.readFileSync(dir + '/' + f, 'utf8')); } catch (e) { continue; }
    let hit = false;
    for (const k of ['rules', 'items', 'places', 'locations', 'worldRules', 'settings', 'worldSettings']) {
      if (Array.isArray(c[k]) && c[k].length) { found++; hit = true; }
    }
    if (hit) withWorld++;
  }
  assert.ok(found >= 1, '第 14 轮提示词改造后管线必须产出世界设定，实际=' + found);
  const bp = fsx.readFileSync('loop/bin/build_plan.py', 'utf8');
  const prompt = bp.split('产出（写进 {out}）：')[1].split('硬性红线')[0];
  for (const w of ['worldSettings[]', 'rule', 'place', 'item']) {
    assert.notEqual(prompt.indexOf(w), -1,
      '提示词产出清单必须要求「' + w + '」（第 14 轮已补；若消失说明被回退）');
  }
  for (const [needle, why] of [['提及', '地点提及≠到达'], ['itemStates', '物件四态'],
                               ['institution', '制度宣称≠已执行']]) {
    assert.notEqual(prompt.indexOf(needle), -1, '提示词必须写明「' + why + '」');
  }
  console.log('     ' + files.length + ' 个管线产物、3 个图谱：世界设定字段命中 ' + found
    + ' 处（' + withWorld + ' 个候选，第 14 轮后这一层不得再为空）；'
    + '提示词已要求 worldSettings[] 并写明三条区分');
});

test('真实数据：地点提及≠到达 在三国原文上可测（荆州 420 次，到达式 95 次）', () => {
  const d = JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.docs.json', 'utf8'));
  const text = (Array.isArray(d) ? d : d.docs)[0].text;
  const count = (re) => (text.match(re) || []).length;
  const jingzhou = count(/荆州/g);
  assert.equal(jingzhou, 420, '荆州提及次数');
  const seize = count(/取荆州/g);
  assert.equal(seize, 52, '「取荆州」的出现次数（图谋语，不是到达）');
  const arrivePat = /(至|到|入|抵|进驻|兵临|奔|走|回|守|屯|据|围|过|出|往|赴|投|退|驻|移屯|拔寨|亲诣|径往|直抵)荆州/g;
  const jingzhouArrive = count(arrivePat);
  assert.equal(jingzhouArrive, 95, '荆州到达式次数（与模块 ARRIVE 同口径）');
  assert.ok(jingzhouArrive < jingzhou, '到达必须少于提及');
  const arrived = W.placeState({ name: '荆州' }, '玄德遂至荆州，安民已毕');
  assert.equal(arrived.code, 'arrived');
  const plan = W.placeState({ name: '荆州' }, '先取荆州为家，后即取西川建基业');
  assert.equal(plan.code, 'mentioned', '「取荆州」是图谋不是到达，实际=' + plan.code);
  const mentioned = W.placeState({ name: '荆州' }, '今当先取荆州为家，然后图益州');
  assert.equal(mentioned.code, 'mentioned');
  console.log('     荆州 提及 ' + jingzhou + ' / 到达式 ' + jingzhouArrive + ' / 仅提及 ' + (jingzhou - jingzhouArrive)
    + '（其中「取荆州」图谋语 ' + seize + ' 次已正确排除）');
});

test('真实数据：文言物件动词必须能命中（玉玺那条线）', () => {
  const cases = [
    ['匿玉玺孙坚背约', 'hold', '「匿」是私藏'],
    ['检点宫中，不见了传国玉玺', 'lose', '「不见了」是丢失'],
    ['玉玺乃朝廷之宝，公既获得，当对众留于盟主处', 'hold', '「获得」是持有'],
    ['子婴将玉玺献与汉高祖', 'transfer', '「献与」是交接'],
  ];
  for (const [text, want, why] of cases) {
    const st = W.itemStates({}, text);
    assert.equal(st.states[want], true, why + '（' + text + '）应判 ' + want + '，实际=' + JSON.stringify(st.codes));
  }
  console.log('     文言四态全部命中（匿/不见了/获得/献与）');
});

console.log('SKY WORLD OBJECT ' + passed + '/' + passed);
