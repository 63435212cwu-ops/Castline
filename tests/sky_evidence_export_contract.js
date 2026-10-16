'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ctx = { window: {}, console };
vm.createContext(ctx);
for (const file of ['js/tree/storylines.js', 'js/sky/sky-model.js', 'js/sky/sky-export.js']) {
  vm.runInContext(read(file), ctx, { filename: file });
}
const { CLStory, CLSkyModel, CLSkyExport } = ctx.window;
const plain = v => JSON.parse(JSON.stringify(v));
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

const QUOTE = '悟空道：“此间更无六耳，止只弟子一人，望师父大舍慈悲，传与我长生之道罢，永不忘恩！”\n同一空白行也原样保留  ';
const QUOTE2 = '十五万两白银，一夜易手。税银案卷宗第七页，墨痕未干。';

function book() {
  return {
    title: '契约样例', synopsis: 's',
    characters: [{ id: 'c1', name: '甲', importance: 90, knowledge: [{ text: '知道税银藏处', eventId: 'e2', basis: 'explicit' }] }],
    events: [
      { id: 'e1', order: 1, chapter: '第1章', title: '埋钩', summary: 'S1', characters: ['甲'], quote: QUOTE,
        evidence: [{ quote: QUOTE, sourceId: 'src_a', textHash: 'deadbeef', start: 3, end: 3 + QUOTE.length, basis: 'explicit', chapter: '第1章' }] },
      { id: 'e2', order: 2, chapter: '第2章', title: '收钩', summary: 'S2', characters: ['甲'], quote: QUOTE2,
        causes: [{ ref: 'e1', basis: 'explicit', quote: QUOTE, description: '因' }] },
      { id: 'e3', order: 3, chapter: '第3章', title: '尾声', summary: 'S3', characters: [] }
    ],
    clues: [{ id: 'clue1', name: '长生诀', seedEventId: 'e1', payoffEventId: 'e2', status: 'resolved', basis: 'explicit', seedQuote: QUOTE, payoffQuote: QUOTE2 }],
    characterStates: [{ id: 'st1', characterId: 'c1', summary: '知悉真相', eventId: 'e2', basis: 'inferred',
      transition: { before: '不知隐情', after: '知悉隐情', basis: 'explicit', quote: QUOTE2 } }],
    storylines: [
      { id: 'm1', kind: '主线', name: '取经线', goal: '赴灵山取真经回朝缴旨', events: [1, 2] },
      { id: 'm2', kind: '主线', name: '全书阶段2', events: [3] }
    ],
    relations: [
      { id: 'r1', a: '甲', b: '乙', kind: '同盟', line: '暗线', desc: '互相担保', strength: 0.7, quote: QUOTE, quoteVerified: true,
        sourceRefs: [{ sourceId: 'src_a', textHash: 'deadbeef', start: 3, end: 3 + QUOTE.length, verified: true, status: 'verified', quote: QUOTE }] },
      { id: 'r2', a: '乙', b: '丙', kind: '宿怨', desc: '旧账', claimVerified: false }
    ],
    meta: {}
  };
}

function work(g) {
  const t = CLStory.analyze(g), m = CLSkyModel.build(g, t);
  return CLSkyExport.snapshot({ graph: g, model: m, story: t, workKey: 'contract-key',
    graphHash: CLStory.fingerprint(g), generatedAt: '2026-10-07T00:00:00.000Z' });
}

test('导出包带 schema 版本与作品元数据（hash 可取得时如实带上）', () => {
  const g = book(), pkg = work(g);
  assert.equal(pkg.schema, 'castline/evidence-export/1');
  assert.equal(pkg.work.key, 'contract-key');
  assert.equal(pkg.work.title, '契约样例');
  assert.equal(pkg.work.graphHash, CLStory.fingerprint(g));
  assert.equal(typeof pkg.generatedAt, 'string');
  assert.equal(pkg.projections.relationHonesty, 'relationHonesty/1');
  assert.equal(pkg.projections.lineHonesty, 'honesty/1');
});

test('引文与锚点逐字透传：事件证据、因果边、伏笔生命周期、关系', () => {
  const g = book(), pkg = work(g);
  const ev = pkg.claims.evidence.filter(x => x.quote === QUOTE)[0];
  assert.equal(ev.quote, QUOTE, '证据引文逐字');
  assert.equal(ev.sourceId, 'src_a'); assert.equal(ev.textHash, 'deadbeef');
  assert.equal(ev.start, 3); assert.equal(ev.end, 3 + QUOTE.length, '锚点区间存在且未改');
  const edge = pkg.claims.causalEdges[0];
  assert.equal(edge.quote, QUOTE, '因果边引文逐字');
  const life = pkg.claims.foreshadowLifecycles[0];
  assert.equal(life.seedQuote, QUOTE); assert.equal(life.payoffQuote, QUOTE2);
  assert.equal(life.stage, 'resolved');
  const rel = pkg.claims.relations[0];
  assert.equal(rel.quote, QUOTE, '关系引文逐字'); assert.equal(rel.quoteVerified, true);
  assert.equal(rel.sourceRefs[0].start, 3); assert.equal(rel.status.evidence, 'anchored');
  assert.equal(pkg.claims.relations[1].status.evidence, 'inherited-pending');
  assert.equal(pkg.claims.characters.transitions[0].quote, QUOTE2, '人物状态转变引文逐字');
});

test('计数与投影逐项一致，分层桶 = 投影行内 basisCode 分桶', () => {
  const g = book(), m = CLSkyModel.build(g, CLStory.analyze(g)), pkg = work(g);
  const n = m.narrative, c = pkg.counts;
  function bucket(items) {
    const out = { total: items.length, explicit: 0, synthesis: 0, inference: 0, unverified: 0 };
    items.forEach(it => { out[out[it.basisCode] != null ? it.basisCode : 'unverified']++; });
    return out;
  }
  assert.deepEqual(bucket(n.evidence), { total: c.evidence.total, explicit: c.evidence.explicit, synthesis: c.evidence.synthesis, inference: c.evidence.inference, unverified: c.evidence.unverified });
  assert.deepEqual(bucket(n.causalEdges), { total: c.causalEdges.total, explicit: c.causalEdges.explicit, synthesis: c.causalEdges.synthesis, inference: c.causalEdges.inference, unverified: c.causalEdges.unverified });
  assert.equal(c.foreshadowLifecycles.total, n.foreshadowLifecycles.length);
  assert.equal(c.foreshadowLifecycles.resolved, 1);
  assert.equal(c.foreshadowLifecycles.projectionTotal, n.architecture.stats.foreshadow.total);
  assert.equal(c.relations.total, m.relationsHonesty.total);
  assert.equal(c.relations.anchored, m.relationsHonesty.anchored);
  assert.equal(c.relations.inheritedPending, m.relationsHonesty.inherited);
  assert.equal(c.storylines.total, m.lineHonesty.total);
  assert.equal(c.storylines.mechanical, m.lineHonesty.mechanical);
  assert.equal(c.storylines.verdict, m.lineHonesty.verdict);
  assert.equal(c.characters.knowledge.total, n.characterReading.knowledge.length);
  assert.equal(c.unresolved, n.unresolved.length);
  assert.equal(c.claims, c.evidence.total + c.causalEdges.total + c.turningPoints.total + c.foreshadowLifecycles.total +
    c.characters.states.total + c.characters.knowledge.total + c.characters.transitions.total + c.storylines.total + c.relations.total,
    '总声明数 = 各类之和');
});

test('空类别如实导出空数组、键不省略，计数全 0，无声明的作品导出仍成立', () => {
  const g = { title: '空图谱', characters: [], events: [], relations: [], storylines: [], meta: {} };
  const pkg = plain(work(g));
  assert.equal(pkg.schema, 'castline/evidence-export/1');
  assert.deepEqual(pkg.claims.evidence, []);
  assert.deepEqual(pkg.claims.causalEdges, []);
  assert.deepEqual(pkg.claims.turningPoints, []);
  assert.deepEqual(pkg.claims.foreshadowLifecycles, []);
  assert.deepEqual(pkg.claims.characters.states, []);
  assert.deepEqual(pkg.claims.characters.knowledge, []);
  assert.deepEqual(pkg.claims.characters.knowledgeGaps, []);
  assert.deepEqual(pkg.claims.characters.transitions, []);
  assert.deepEqual(pkg.claims.storylines.threads, []);
  assert.equal(pkg.claims.storylines.honesty.total, 0);
  assert.deepEqual(pkg.claims.relations, []);
  assert.deepEqual(pkg.claims.unresolved, []);
  for (const key of ['evidence', 'causalEdges', 'turningPoints', 'foreshadowLifecycles']) assert.equal(pkg.counts[key].total, 0, key);
  assert.equal(pkg.counts.relations.total, 0);
  assert.equal(pkg.counts.relations.inheritedPending, 0);
  assert.equal(pkg.counts.storylines.total, 0);
  assert.equal(pkg.counts.claims, 0);
  const body = CLSkyExport.text(pkg);
  const parsed = JSON.parse(body);
  assert.deepEqual(Object.keys(parsed.claims).sort(), ['causalEdges', 'characters', 'evidence', 'foreshadowLifecycles', 'relations', 'storylines', 'turningPoints', 'unresolved']);
  assert.ok(pkg.work.graphHash, '空图谱也有 graphHash');
  assert.equal(CLSkyExport.fileName(pkg).endsWith('.json'), true);
});

test('逐字节确定性：同一投影两次导出文本一致；generatedAt 是唯一非确定字段', () => {
  const g = book(), t = CLStory.analyze(g), m = CLSkyModel.build(g, t);
  const opts = { graph: g, model: m, story: t, workKey: 'k', graphHash: CLStory.fingerprint(g) };
  const a = CLSkyExport.snapshot(Object.assign({ generatedAt: '2026-01-01T00:00:00.000Z' }, opts));
  const b = CLSkyExport.snapshot(Object.assign({ generatedAt: '2026-01-01T00:00:00.000Z' }, opts));
  assert.equal(CLSkyExport.text(a), CLSkyExport.text(b), '同一投影两次导出逐字节一致');
  const c = CLSkyExport.snapshot(Object.assign({ generatedAt: '2099-12-31T23:59:59.000Z' }, opts));
  assert.notEqual(CLSkyExport.text(a), CLSkyExport.text(c), '时间戳不同则文本不同');
  function diffPaths(x, y, base, out) {
    if (typeof x !== typeof y || x === null || y === null || typeof x !== 'object') { if (x !== y) out.push(base); return; }
    if (Array.isArray(x) !== Array.isArray(y)) { out.push(base); return; }
    const ks = Array.isArray(x) ? x.map((_, i) => i) : Array.from(new Set(Object.keys(x).concat(Object.keys(y))));
    ks.forEach(k => diffPaths(x[k], y[k], base + '.' + k, out));
  }
  const diffs = [];
  diffPaths(a, c, '$', diffs);
  assert.deepEqual(diffs, ['$.generatedAt'], '唯一非确定字段 = generatedAt');
});

test('不新增任何核验判定：导出包里不存在 verified/anchored 之外的新造结论字段', () => {
  const g = book(), pkg = work(g);
  const body = CLSkyExport.text(pkg);
  assert.ok(!body.includes('exportVerified'), '不得声称导出核验通过');
  assert.ok(!body.includes('"ok":true'), '不合成 ok 结论');
});

console.log('EVIDENCE EXPORT CONTRACT ' + passed + '/' + passed);
