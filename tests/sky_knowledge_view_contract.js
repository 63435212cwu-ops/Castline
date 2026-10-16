'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const K = require('../js/sky/sky-knowledge-view.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('六类（知道/相信/误信/隐瞒/明确不知/读者已知）+ 叙述者全知各有独立名称与解释', () => {
  const six = ['knows', 'believes', 'misbelief', 'conceals', 'unaware', 'readerKnows'];
  const labels = six.map(c => K.STATES[c].zh);
  assert.equal(new Set(labels).size, six.length, '六类名称不得重复：' + JSON.stringify(labels));
  six.forEach(c => assert.ok(K.STATES[c].hint.length > 8, c + ' 必须带解释'));
  assert.ok(K.STATES.narrator && K.STATES.narrator.zh === '叙述者全知');
  assert.ok(/不得灌给任何人物/.test(K.STATES.narrator.hint), K.STATES.narrator.hint);
});

test('负例 · 缺字段不得默认成「知道」', () => {
  for (const r of [{}, { id: 'k1' }, null, undefined, { note: '' }]) {
    const s = K.of(r);
    assert.notEqual(s.code, 'knows', '缺字段不得判知道：' + JSON.stringify(r));
    assert.equal(s.countsAsKnowing, false);
  }
});

test('负例 · 相信与误信都不得算「知道」（误信更必须分开）', () => {
  const bel = K.of({ knows: '许七安相信卷宗里有线索', chapter: 1,
    quotes: [{ quote: 'x' }] });
  assert.equal(bel.code, 'believes', '实际=' + bel.code);
  assert.equal(bel.countsAsKnowing, false, '相信不等于知道');
  const mis = K.of({ knows: '许七安误以为张献已经招供', chapter: 1, quotes: [{ quote: 'x' }] });
  assert.equal(mis.code, 'misbelief', '实际=' + mis.code);
  assert.equal(mis.isFalseBelief, true);
  assert.equal(mis.countsAsKnowing, false);
  assert.notEqual(bel.label, mis.label, '相信与误信不得显示成同一个词');
});

test('负例 · 沉默不得判知情（取得信息需事件或明确叙述）', () => {
  const silent = K.audit({ knows: '许七安知道卷宗内容' });
  assert.equal(silent.acquisition.bySilence, true, '无引句无事件无叙述应判为沉默');
  assert.equal(silent.downgraded, true, '必须降级');
  assert.equal(silent.downgradeReason, 'acquisition_unsupported');
  assert.equal(silent.countsAsKnowing, false, '沉默不证明知情');
  assert.equal(silent.code, 'unknown', '降级后应为未标明，实际=' + silent.code);
  const ok = K.audit({ knows: '许七安知道卷宗内容', chapter: 1, quotes: [{ quote: '原文' }] });
  assert.equal(ok.downgraded, false, '有依据不得降级');
  assert.equal(ok.countsAsKnowing, true);
});

test('负例 · 叙述者全知不得灌给人物', () => {
  const nar = K.of({ knows: '叙述者交代：许新年未被下狱', chapter: 1, quotes: [{ quote: 'x' }] });
  assert.equal(nar.code, 'narrator', '实际=' + nar.code);
  assert.equal(nar.mustNotAttributeToCharacter, true);
  assert.equal(nar.countsAsKnowing, false);
  const attached = K.audit({ knows: '叙述者交代：许新年未被下狱', chapter: 1, quotes: [{ quote: 'x' }] },
    { attachToCharacter: true });
  assert.equal(attached.downgraded, true, '挂到人物身上必须被拒');
  assert.equal(attached.downgradeReason, 'narrator_not_attributable');
  assert.equal(attached.countsAsKnowing, false);
  const reader = K.of({ knows: '读者已知真凶是谁，许七安尚在推测', chapter: 3, quotes: [{ quote: 'x' }] });
  assert.equal(reader.code, 'readerKnows', '实际=' + reader.code);
  assert.equal(reader.mustNotAttributeToCharacter, true);
});

test('负例 · 前章回看不得携带后章知识（时代错置）', () => {
  const future = K.anachronism({ chapter: 90 }, 12);
  assert.equal(future.checked, true);
  assert.equal(future.anachronism, true, '第 90 章的知识出现在第 12 章回看里必须报错');
  const past = K.anachronism({ chapter: 5 }, 12);
  assert.equal(past.anachronism, false);
  const unknownCh = K.anachronism({}, 12);
  assert.equal(unknownCh.checked, false, '无章号不得假装检查过');
  assert.equal(unknownCh.anachronism, false);
  const t = K.tally([{ knows: '许七安知道某事', chapter: 90, quotes: [{ quote: 'x' }] }], { atChapter: 12 });
  assert.equal(t.anachronisms, 1, '实际=' + t.anachronisms);
});

test('明确不知必须与「沉默」分开（原文写明 vs 没提）', () => {
  const unaware = K.of({ unknownTo: '许七安不知道卷宗内容', chapter: 1, quotes: [{ quote: 'x' }] });
  assert.equal(unaware.code, 'unaware', '实际=' + unaware.code);
  assert.equal(unaware.countsAsKnowing, false);
  assert.ok(/沉默.*不构成/.test(K.STATES.unaware.hint), K.STATES.unaware.hint);
});

test('隐瞒是行为，不等于别人不知道', () => {
  const c = K.of({ knows: '许新年隐瞒了三百两的去向', chapter: 5, quotes: [{ quote: 'x' }] });
  assert.equal(c.code, 'conceals', '实际=' + c.code);
  assert.equal(c.countsAsKnowing, false, '隐瞒本身不是「知道」这一类');
  assert.ok(/不等于别人不知道/.test(K.STATES.conceals.hint), K.STATES.conceals.hint);
});


test('主体认知不被其它人和注记中的误信、否定或未知改写', () => {
  const primary = { knows: '甲知道这是计策', chapter: 1, quotes: [{ quote: '依据' }] };
  for (const aux of [
    { note: '材料未写乙是否发现自己被骗' },
    { note: '这是乙设计的假消息' },
    { whoElseKnows: '乙误以为约定已经生效' },
    { unknownTo: '乙不知道这件事' },
    { description: '旁白未写乙是否误信' }
  ]) {
    const row = K.audit(Object.assign({}, primary, aux));
    assert.equal(row.code, 'knows', JSON.stringify(aux));
    assert.equal(row.isFalseBelief, false, JSON.stringify(aux));
  }
  for (const rec of [
    { note: '甲知道这是计策' },
    { whoElseKnows: '乙知道这是计策' },
    { knows: '当前人物状态未标明', note: '乙误以为约定已经生效' }
  ]) {
    const row = K.audit(rec);
    assert.equal(row.code, 'unknown');
    assert.equal(row.countsAsKnowing, false);
    assert.equal(row.isFalseBelief, false);
  }
  assert.equal(K.of({ knows: '甲误以为约定生效', note: '乙知道真相' }).code, 'misbelief');
  assert.equal(K.of({ knows: '甲相信约定生效', note: '乙知道真相' }).code, 'believes');
  assert.equal(K.of({ knows: '叙述者交代了真相', note: '甲知道真相' }).code, 'narrator');
  assert.equal(K.of({ status: 'misbelief', knows: '甲知道真相', note: '乙未知' }).code, 'misbelief');
});


test('未声明的疑问、否定与条件不能提升为知道或误信', () => {
  for (const knows of [
    '甲是否误以为此事已经结束？', '甲并没有被骗', '甲从未误以为此事已经结束',
    '甲是否知道此事？', '甲可能知道此事', '如果甲知道此事，便会离开',
    '甲并非不知道此事', '甲未曾得知此事', '甲并非误信此事',
    '甲不是不知道此事', '甲并未获悉此事', '甲没有上当', '甲没有中计'
  ]) {
    const row = K.audit({ knows, chapter: 1, quotes: [{ quote: '依据' }] });
    assert.equal(row.code, 'unknown', knows);
    assert.equal(row.countsAsKnowing, false, knows);
    assert.equal(row.isFalseBelief, false, knows);
  }
  assert.equal(K.of({ unknownTo: '甲是否不知道此事？' }).code, 'unknown');
  assert.equal(K.of({ knows: '甲不知道此事' }).code, 'unaware');
  assert.equal(K.of({ knows: '甲知道此事', chapter: 1, quotes: [{ quote: '依据' }] }).code, 'knows');
  assert.equal(K.of({ knows: '甲误以为此事已经结束' }).code, 'misbelief');
  assert.equal(K.of({ status: 'misbelief', knows: '甲是否误以为此事已经结束？' }).code, 'misbelief');
});

test('记录自声明的 status 优先于文字推断', () => {
  const d = K.of({ status: 'misbelief', knows: '他清楚地知道真相', chapter: 1, quotes: [{ quote: 'x' }] });
  assert.equal(d.code, 'misbelief', 'declared 必须优先，实际=' + d.code);
  assert.equal(d.basis, 'declared');
  const i = K.of({ knows: '他误以为真相如此', chapter: 1, quotes: [{ quote: 'x' }] });
  assert.equal(i.basis, 'marker');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'k1', [], { knows: 123 }, { quotes: 'x' }]) {
    const s = K.of(bad);
    assert.ok(s && typeof s.code === 'string');
    const a = K.audit(bad);
    assert.ok(a && typeof a.code === 'string');
  }
  assert.equal(K.tally(null).total, 0);
});

test('汇总只叫认知分布，不得自称清晰度评分', () => {
  const t = K.tally([
    { knows: '甲知道', chapter: 1, quotes: [{ quote: 'x' }] },
    { knows: '乙误以为', chapter: 2, quotes: [{ quote: 'x' }] },
    { knows: '叙述者交代', chapter: 3, quotes: [{ quote: 'x' }] },
    { knows: '丙知道但没有依据' }
  ]);
  assert.equal(t.title, '认知状态分布');
  assert.equal(t.isWorldviewScore, false);
  assert.equal(t.total, 4);
  assert.equal(t.knowing, 1);
  assert.equal(t.misbelief, 1);
  assert.equal(t.notAttributable, 1);
  assert.equal(t.downgraded, 1, '沉默那条必须被降级');
  assert.ok(/沉默不证明知情/.test(t.note), t.note);
});

test('结构性缺口①：管线有 523 条认知记录，而已发布图谱里为 0', () => {
  const files = fs.readdirSync('loop/state/out').filter(f => /^read_.*\.candidate\.json$/.test(f));
  let pipeline = 0;
  for (const f of files) {
    let c; try { c = JSON.parse(fs.readFileSync(path.join('loop/state/out', f), 'utf8')); } catch (e) { continue; }
    pipeline += (c.knowledgeGaps || []).length;
  }
  assert.ok(pipeline >= 500, '管线认知记录数应 ≥500，实际=' + pipeline);
  for (const key of ['1063b17ca65ec1b76f30e460', 'aee4c99808674e4220ab0104']) {
    const raw = fs.readFileSync('data/cache/' + key + '.json', 'utf8');
    assert.equal(raw.indexOf('"knows"'), -1, key + ' 已发布图谱不应含 knows 字段');
    assert.equal(raw.indexOf('"whoElseKnows"'), -1, key + ' 已发布图谱不应含 whoElseKnows 字段');
    assert.equal(raw.indexOf('knowledgeGaps'), -1, key + ' 已发布图谱不应含 knowledgeGaps');
  }
  console.log('     管线认知记录 ' + pipeline + ' 条；两个已发布图谱 0 条 ⇒ 结论从未落地');
});

test('结构性缺口②：模型读的字段在人物对象上不存在（这才是 stats.knowledge=0 的原因）', () => {
  const g = JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8'));
  const ch = g.characters || [];
  assert.equal(ch.length, 453, '夹具人物数');
  const withKnowledge = ch.filter(c => c && (c.knowledge || c.knowledgeGaps)).length;
  assert.equal(withKnowledge, 0, '实测没有任何人物带 knowledge/knowledgeGaps 字段');
  const withJudgments = ch.filter(c => Array.isArray(c.judgments) && c.judgments.length).length;
  assert.ok(withJudgments > 0, '人物上确实有 judgments（另一种形态），实际=' + withJudgments);
  console.log('     453 个人物：带 knowledge/knowledgeGaps 的 0 个；带 judgments 的 ' + withJudgments + ' 个');
});

test('当前管线记录逐条保留认知类别与依据边界，报告实际分布', () => {
  const files = fs.readdirSync('loop/state/out').filter(f => /^read_.*\.candidate\.json$/.test(f));
  assert.ok(files.length > 0, '必要管线夹具缺失');
  const by = {};
  let count = 0, knowing = 0;
  for (const file of files) {
    const c = JSON.parse(fs.readFileSync(path.join('loop/state/out', file), 'utf8'));
    for (const rec of (c.knowledgeGaps || [])) {
      const tag = file + ':' + (rec && rec.id || count);
      const row = K.audit(rec, { chapter: c.unitHead });
      assert.ok(Object.hasOwn(K.STATES, row.code), tag + ': unknown category');
      assert.equal(row.label, K.STATES[row.code].zh, tag + ': label does not match category');
      assert.equal(row.countsAsKnowing, row.code === 'knows', tag + ': a different state was counted as knowing');
      assert.equal(row.isFalseBelief, row.code === 'misbelief', tag + ': false belief flag does not match category');
      if (row.countsAsKnowing) {
        assert.equal(row.acquisition.acceptable, true, tag + ': knowing without evidence');
        knowing++;
      }
      if (row.code === 'readerKnows' || row.code === 'narrator') {
        assert.equal(row.mustNotAttributeToCharacter, true, tag + ': viewpoint attributed to a character');
      }
      by[row.code] = (by[row.code] || 0) + 1;
      count++;
    }
  }
  assert.ok(count >= 500, '必要认知记录夹具缺失，实际=' + count);
  assert.ok(knowing > 0, 'fixture must retain records with evidenced knowledge');
  console.log('     当前记录=' + count + '；分布：' + JSON.stringify(by) + '；可确证知情=' + knowing + '（分类检查不代表原文语义审阅）');
});

console.log('SKY KNOWLEDGE VIEW ' + passed + '/' + passed);
