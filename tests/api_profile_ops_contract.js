'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = name => fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
const src = read('js/app.js');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

function between(start, end) {
  const i = src.indexOf(start);
  assert.ok(i >= 0, '锚缺失: ' + start);
  const j = src.indexOf(end, i + start.length);
  assert.ok(j > i, '锚缺失: ' + end);
  return src.slice(i, j + end.length);
}
const opsTpl = src.match(/<div class="ops">([\s\S]*?)<\/div><\/div>/);
assert.ok(opsTpl, 'renderProfiles 卡片 ops 渲染模板缺失');
const cardActs = [...opsTpl[1].matchAll(/data-act="([\w-]+)"/g)].map(m => m[1]);
const op = between('function profileOp(act, p, b)', "$('apiList').addEventListener");
function actSeg(act) {
  const m = op.match(new RegExp("if \\(act === '" + act + "'\\) \\{([\\s\\S]*?)(?=\\n    if \\(act ===|\\n    apiMsg\\('该操作未开放')"));
  assert.ok(m, 'profileOp 缺 act=' + act + ' 分支');
  return m[1];
}
function postShapes(seg) {
  return [...seg.matchAll(/apiPost\(\{([^}]*)\}\)/g)].map(m =>
    m[1].split(',').map(s => s.trim()).filter(Boolean));
}

test('渲染面：档案卡片恰好四钮（使用 / 编辑 / 测试 / 删除），data-act 集合钉死', () => {
  assert.deepEqual(cardActs, ['select', 'edit', 'test', 'delete']);
  assert.ok(opsTpl[1].includes('class="danger"'), '删除钮保留 danger 样式标记');
});
test('消费面：$apiList 有委托 click listener，dispatch 到 profileOp', () => {
  assert.ok(src.includes("$('apiList').addEventListener('click'"), 'apiList 委托 listener 缺失');
  assert.ok(src.includes("profileOp(b.getAttribute('data-act'), p, b)"), 'dispatch 缺失');
  assert.ok(src.includes('if (!b || b.disabled) return'), '忙态按钮不得重复触发');
});
test('每个渲染的 act 在 profileOp 有显式分支，未知 act 显式拒绝不静默', () => {
  cardActs.forEach(a => assert.ok(op.includes("act === '" + a + "'"), 'act=' + a + ' 无分支'));
  assert.ok(op.includes("apiMsg('该操作未开放', 'err')"), '未知 act 必须有显式拒绝文案');
});
test('「编辑」走真实本地通道：fillForm 载入既有 save 路径，不发假请求、不假装保存', () => {
  const s = actSeg('edit');
  assert.ok(s.includes('fillForm(p)'), 'edit 必须载入表单');
  assert.equal(postShapes(s).length, 0, 'edit 不得发网络请求（save 由既有表单提交通道完成）');
  assert.ok(s.includes('保存') && s.includes('apiMsg('), 'edit 必须说出「改完点保存」，不得假装已执行');
});
test('参数形状：使用 / 测试 / 删除的 apiPost 只送 { action, id }——打码密钥绝不回送', () => {
  [['select', 'select'], ['test', 'test'], ['delete', 'delete']].forEach(pair => {
    const shapes = postShapes(actSeg(pair[0]));
    assert.equal(shapes.length, 1, 'act=' + pair[0] + ' 应恰好一次 apiPost');
    assert.deepEqual(shapes[0], ["action: '" + pair[1] + "'", 'id: p.id'],
      'act=' + pair[0] + ' 参数形状不符（服务端按 id 取存储档案，不回送卡片字段）');
  });
});
test('反馈时序：三钮忙态按钮先于 apiPost；成功 / 失败两侧都有用户可见说法', () => {
  ['select', 'test', 'delete'].forEach(a => {
    const s = actSeg(a);
    assert.ok(s.indexOf('opBusy(') >= 0 && s.indexOf('opBusy(') < s.indexOf('apiPost('),
      'act=' + a + ' 忙态必须先于请求');
    assert.ok(s.includes('opIdle('), 'act=' + a + ' 失败路径必须还原按钮态');
    assert.ok((s.match(/apiMsg\(/g) || []).length >= 2, 'act=' + a + ' 至少成功 / 失败两处说法');
    assert.ok(s.includes("'err'"), 'act=' + a + ' 失败说法必须是错误档文案');
    assert.ok(s.includes('e && e.message'), 'act=' + a + ' 失败文案取 llmFail 构造的分类文案');
  });
});
test('状态诚实：成功以服务端真实状态重渲染（renderProfiles(d) / loadProfiles()），无乐观假态', () => {
  ['select', 'test', 'delete'].forEach(a => {
    const s = actSeg(a);
    assert.ok(!/\.remove\(\)|innerHTML\s*=/.test(s), 'act=' + a + ' 不得手工改 DOM（乐观假态）');
  });
  assert.ok(actSeg('select').includes('renderProfiles(d)'), 'select 成功必须按服务端回包重渲染');
  assert.ok(actSeg('delete').includes('renderProfiles(d)'), 'delete 成功必须按服务端回包重渲染');
  assert.ok(actSeg('test').includes('loadProfiles()'), 'test 必须重读服务端写下的 last_test 徽记');
});
test('删除先过 confirmBox 确认门，再发删除请求', () => {
  const s = actSeg('delete');
  const ci = s.indexOf('confirmBox('), pi = s.indexOf('apiPost(');
  assert.ok(ci >= 0 && pi >= 0 && ci < pi, '删除必须确认后才发请求');
  assert.ok(s.includes('if (!yes)') && s.includes('档案保留'), '取消删除必须明说「档案保留」');
});
test('失败分类通道完整：apiPost 仍走 llmJson 守卫 + llmFail（CLLlmErrors 分类）', () => {
  assert.ok(src.includes("return llmJson(r, '/api/llm-config');"), 'apiPost 解析守卫缺失');
  assert.ok(src.includes("llmFail({ kind: 'net', src: '/api/llm-config'"), 'apiPost 网络拒绝分类缺失');
  assert.ok(src.includes('e.llm = L.classify(raw)'), 'llmFail 必须附 CLLlmErrors 分类');
});
test('死 UI 静态闸：app.js 渲染的全部 data-act 按钮都有可查证处理路径（缺口 = 0）', () => {
  const rendered = [...new Set([...src.matchAll(/data-act="([\w-]+)"/g)].map(m => m[1]))];
  assert.ok(rendered.length >= 12, '渲染的 act 集合意外变小（模板被改？）：' + rendered.join(','));
  const dead = rendered.filter(a => {
    if (src.includes("act === '" + a + "'") || src.includes('act === "' + a + '"')) return false;
    if (a === 'open') return !(src.includes("b ? b.dataset.act : 'open'") && src.includes('return openHistory(key)'));
    return true;
  });
  assert.deepEqual(dead, [], '渲染了但无处理路径的按钮（死 UI）：' + dead.join(','));
});
test('API 面板内 data-m（模型 chips）与 data-filter（过滤 tabs）动态按钮同样有消费点', () => {
  assert.ok(src.includes("$('apiModelChips').addEventListener('click'") && src.includes("closest('button[data-m]')"),
    '模型 chips data-m 消费点缺失');
  assert.ok(src.includes('mfTabs.addEventListener') && src.includes("closest('button[data-filter]')"),
    '过滤 tabs data-filter 消费点缺失');
});

console.log('api_profile_ops_contract: ' + passed + '/' + passed + ' PASS');
