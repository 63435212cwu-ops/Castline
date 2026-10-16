'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.join(__dirname, '..');
const LABEL_SRC = fs.readFileSync(path.join(ROOT, 'js/sky/sky-event-label.js'), 'utf8');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

function boot() {
  const sandbox = { window: {}, globalThis: {} };
  vm.runInNewContext(LABEL_SRC, sandbox);
  const api = sandbox.CLSkyEventLabel || (sandbox.window && sandbox.window.CLSkyEventLabel);
  assert.ok(api, 'CLSkyEventLabel must be defined');
  return api;
}
const L = boot();

test('有效 title 原样返回，不被 name/summary 覆盖', () => {
  assert.equal(L.eventLabel({ title: '牢狱之灾', name: '别的名字', summary: '摘要' }), '牢狱之灾');
});
test('title 前后空白不算有效值，但原值不被改写', () => {
  const e = { title: '   ', name: '真名' };
  assert.equal(L.eventLabel(e), '真名');
  assert.equal(e.title, '   ', '不得就地修改输入对象');
});
test('title 缺失时才读有效 name', () => {
  assert.equal(L.eventLabel({ name: '穿越入狱' }), '穿越入狱');
});
test('title 与 name 冲突时保留 title（不按 name 改写）', () => {
  assert.equal(L.eventLabel({ title: 'A', name: 'B' }), 'A');
});

test('两者皆空且有 summary 时，不得用摘要杜撰标题，但必须可区分', () => {
  const e1 = { id: 'ev_1', chapter: '第一章 牢狱之灾', summary: '许七安在死牢中醒来' };
  const e2 = { id: 'ev_2', chapter: '第一章 牢狱之灾', summary: '税银丢失' };
  const l1 = L.eventLabel(e1), l2 = L.eventLabel(e2);
  assert.notEqual(l1, '许七安在死牢中醒来', '不得把 summary 当标题');
  assert.notEqual(l1, l2, '同章两条必须可区分');
  assert.ok(l1 && l1.length, '不得为空白');
});
test('未知态标签必须标明「未命名」性质，而不是伪装成标题', () => {
  const l = L.eventLabel({ id: 'ev_1', chapter: '第一章 牢狱之灾' });
  assert.match(l, /未命名/, '读者必须能看出这是未命名而非真实标题');
});
test('未知态提供章节入口信息', () => {
  const l = L.eventLabel({ id: 'ev_1', chapter: '第一章 牢狱之灾' });
  assert.match(l, /第一章/, '应带上章节以便定位');
});
test('无章节时不得杜撰章节', () => {
  const l = L.eventLabel({ id: 'ev_1' });
  assert.doesNotMatch(l, /第[一二三四五六七八九十百千0-9]+章/, '没有 chapter 就不该出现章节号');
});

test('负例 · 空白字符串按缺失处理', () => {
  assert.match(L.eventLabel({ title: '', name: '  ', summary: '\t\n' }), /未命名/);
});
test('负例 · 非字符串字段不参与比较、不抛异常', () => {
  for (const v of [null, undefined, 0, 1, false, {}, [], NaN]) {
    assert.doesNotThrow(() => L.eventLabel({ title: v, name: v, summary: v }));
  }
});
test('负例 · 超长中文标题被截断但保留前缀', () => {
  const long = '第一章'.repeat(200);
  const l = L.eventLabel({ title: long });
  assert.ok(l.length <= L.LABEL_MAX, '标签长度必须受控（避免撑破密集图）');
  assert.ok(long.startsWith(l.slice(0, 6)), '截断必须保留前缀可辨认');
});
test('负例 · 同名不同 ID 不得被合并成同一标签', () => {
  const a = L.eventLabel({ id: 'ev_a', title: '同名', chapter: '第一章' });
  const b = L.eventLabel({ id: 'ev_b', title: '同名', chapter: '第一章' });
  assert.equal(a, b, '有真实标题时同名就该同名（不做人为区分）');
  const u1 = L.eventLabel({ id: 'ev_a', chapter: '第一章' });
  const u2 = L.eventLabel({ id: 'ev_b', chapter: '第一章' });
  assert.notEqual(u1, u2, '未知态必须靠稳定 ID 区分，否则密集图无法阅读');
});
test('负例 · 恶意 HTML 不进入标签（消费者负责转义，标签不得自带标签）', () => {
  const l = L.eventLabel({ title: '<img src=x onerror=alert(1)>' });
  assert.doesNotMatch(l, /<img/, '标签文本不得包含 HTML 标签');
});
test('负例 · 缺演员不影响标签生成', () => {
  assert.ok(L.eventLabel({ title: '事件', characters: undefined }).length);
  assert.ok(L.eventLabel({ chapter: '第一章', characters: null }).length);
});

test('未知态标签对同一 ID 稳定（重复调用同结果）', () => {
  const e = { id: 'ev_stable', chapter: '第一章' };
  assert.equal(L.eventLabel(e), L.eventLabel(e));
});
test('未知态在没有 ID 时也不得抛异常，且仍可读', () => {
  assert.ok(L.eventLabel({ chapter: '第一章' }).length);
});

function codeOnly(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}
test('播放器不再各自写 title||剧情事件 的匿名占位', () => {
  const P = codeOnly(fs.readFileSync(path.join(ROOT, 'js/sky/sky-shell-player.js'), 'utf8'));
  const anon = (P.match(/title\s*\|\|\s*'剧情事件'/g) || []).length;
  assert.equal(anon, 0, '播放器仍有无兜底的匿名占位 ' + anon + ' 处');
  assert.match(P, /evLabel\(|CLSkyEventLabel\.eventLabel/, '播放器必须调用共享标签函数');
});
test('书签/续读同样读共享标签函数', () => {
  for (const f of ['js/sky/sky-bookmarks.js', 'js/sky/sky-resume.js']) {
    const S = fs.readFileSync(path.join(ROOT, f), 'utf8');
    assert.match(S, /CLSkyEventLabel|labelOf/, f + ' 未接入共享标签');
  }
});
test('index.html 加载了共享标签模块', () => {
  const H = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  assert.match(H, /sky-event-label\.js/, 'index.html 未加载 sky-event-label.js');
});

console.log('\n' + passed + ' passed');
