'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const code = fs.readFileSync(path.join(__dirname, '..', 'js', 'sky', 'sky-model.js'), 'utf8');
let count = 0;
function test(name, run) { run(); count++; process.stdout.write('PASS ' + name + '\n'); }
const ctx = { window: {}, console };
vm.runInNewContext(code, ctx);
const M = ctx.window.CLSkyModel;
assert.ok(M && typeof M.relationHonesty === 'function', 'CLSkyModel.relationHonesty 导出');

const LEGACY = [
  { a: '刘备', b: '关羽', kind: '结义', strength: 1, desc: '桃园结义', line: '明线', sourceRefs: [], quoteVerified: false, claimStatus: 'unreviewed' },
  { a: '刘备', b: '张飞', kind: '结义', strength: 1, desc: '桃园结义', line: '明线' }
];

test('旧关系（无锚点字段）→ inherited-pending，计数守恒', () => {
  const h = M.relationHonesty({ relations: LEGACY });
  assert.strictEqual(h.total, 2);
  assert.strictEqual(h.anchored, 0);
  assert.strictEqual(h.inherited, 2);
  assert.strictEqual(h.anchored + h.inherited, h.total);
  h.items.forEach(function (it) {
    assert.strictEqual(it.evidence, 'inherited-pending');
    assert.strictEqual(it.label, '继承 · 待核验');
  });
});

test('quoteVerified===true → anchored，不降级', () => {
  const h = M.relationHonesty({ relations: [{ a: '甲', b: '乙', quoteVerified: true }] });
  assert.strictEqual(h.anchored, 1);
  assert.strictEqual(h.items[0].evidence, 'anchored');
  assert.strictEqual(h.items[0].label, '原文锚点');
});

test('精确定位 sourceRef（verified+exact 区间与 quote 等长）→ anchored', () => {
  const quote = '宴桃园豪杰三结义';
  const g = {
    relations: [
      { a: '甲', b: '乙', sourceRefs: [{ sourceId: 'src-1', textHash: 'h', verified: true, status: 'verified', match: 'exact', start: 0, end: quote.length, quote: quote }] },
      { a: '丙', b: '丁', sourceRefs: [{ sourceId: 'src-1', textHash: 'h', verified: true, status: 'verified', start: 0, end: quote.length + 1, quote: quote }] },
      { a: '戊', b: '己', sourceRefs: [{ sourceId: 'src-1', textHash: 'h', verified: false, status: 'pending', start: 0, end: quote.length, quote: quote }] },
      { a: '庚', b: '辛', evidenceRefs: [{ sourceId: 'src-1', textHash: 'h', verified: true, status: 'verified', match: 'exact', start: 0, end: quote.length, quote: quote }] }
    ]
  };
  const h = M.relationHonesty(g);
  assert.strictEqual(h.anchored, 2);
  assert.strictEqual(h.inherited, 2);
  assert.strictEqual(h.items[0].evidence, 'anchored');
  assert.strictEqual(h.items[1].evidence, 'inherited-pending');
  assert.strictEqual(h.items[2].evidence, 'inherited-pending');
  assert.strictEqual(h.items[3].evidence, 'anchored', 'evidenceRefs 同样计入');
});

test('空图谱/缺 relations 字段 → total 0，不报错', () => {
  const h = M.relationHonesty({});
  assert.deepStrictEqual({ total: h.total, anchored: h.anchored, inherited: h.inherited }, { total: 0, anchored: 0, inherited: 0 });
  assert.strictEqual(M.relationHonesty(null).total, 0);
});

test('函数为纯函数：同一输入两次输出逐字节一致，且不改输入', () => {
  const g = { relations: LEGACY };
  const before = JSON.stringify(g);
  const a = JSON.stringify(M.relationHonesty(g));
  const b = JSON.stringify(M.relationHonesty(g));
  assert.strictEqual(a, b);
  assert.strictEqual(JSON.stringify(g), before, '输入未被修改');
});

process.stdout.write('RELATION-HONESTY OK · ' + count + ' contracts\n');
