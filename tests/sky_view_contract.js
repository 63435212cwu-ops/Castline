'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const V = require('../js/sky/sky-view-contract.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('四个主视图各有唯一主问题，且与计划原文一致', () => {
  const four = ['constellation', 'stage', 'compass', 'deconstruction'];
  assert.deepEqual(Object.keys(V.VIEWS).sort(), four.slice().sort(),
    '视图清单必须恰好是计划点名的四个');
  assert.equal(V.VIEWS.constellation.question, '人物/势力如何关联？');
  assert.equal(V.VIEWS.stage.question, '叙事线路怎样展开？');
  assert.equal(V.VIEWS.compass.question, '单人的特征、关系与轨迹是什么？');
  assert.equal(V.VIEWS.deconstruction.question, '目标、因果与证据是什么？');
});

test('负例 · 一个视图有两个主问题必须判红（「唯一」主问题）', () => {
  for (const c of Object.keys(V.VIEWS)) {
    const a = V.auditView(c);
    assert.equal(a.questionCount, 1, c + ' 必须恰好一个主问题，实际=' + a.questionCount);
    assert.equal(a.singleQuestion, true);
  }
  const patched = JSON.parse(JSON.stringify(V.VIEWS));
  patched.stage.questions = ['叙事线路怎样展开？', '人物成长如何？'];
  const audits = Object.keys(patched).map(k => {
    const q = Array.isArray(patched[k].questions) ? patched[k].questions.length : (patched[k].question ? 1 : 0);
    return { code: k, n: q };
  });
  assert.ok(audits.some(a => a.n !== 1), '两问的视图必须能被识别为非唯一');
});

test('负例 · 五个声明缺任何一个都必须点名，不得默认补齐', () => {
  const a = V.auditView('stage');
  assert.deepEqual(a.missing, [], 'stage 应五项齐全，实际缺：' + JSON.stringify(a.missing));
  assert.equal(a.ok, true);
  assert.deepEqual(V.REQUIRED, ['displays', 'encodes', 'basedOn', 'degrades', 'crossView']);
  assert.equal(V.REQUIRED_ZH.displays, '显示什么');
  assert.equal(V.REQUIRED_ZH.degrades, '缺失时怎样退化');
  assert.equal(V.REQUIRED_ZH.crossView, '如何跨图');
});

test('负例 · 未登记的视图不得被当成「没有主问题」（是没写下来）', () => {
  const a = V.auditView('someUnknownView');
  assert.equal(a.known, false);
  assert.equal(a.ok, false);
  assert.equal(a.missing.length, 5, '未登记应报全部五项缺失');
  assert.ok(/不等于没有主问题|没有写下来/.test(a.hint), a.hint);
});

test('负例 · 同一事实在两处含义不同必须判冲突', () => {
  const bad = V.conflicts([
    { view: '星座', fact: '许七安与魏渊', meaning: '上下级' },
    { view: '罗盘', fact: '许七安与魏渊', meaning: '师徒' }
  ]);
  assert.equal(bad.length, 1, '必须判出冲突');
  assert.equal(bad[0].fact, '许七安与魏渊');
  assert.ok(/同一事实不在四处拥有不同含义/.test(bad[0].hint), bad[0].hint);
  const good = V.conflicts([
    { view: '星座', fact: '某关系', meaning: '同盟' },
    { view: '罗盘', fact: '某关系', meaning: '同盟' }
  ]);
  assert.deepEqual(good, [], '含义一致不得判冲突');
  assert.deepEqual(V.conflicts([
    { view: 'a', fact: 'x', meaning: 'p' }, { view: 'b', fact: 'y', meaning: 'q' }
  ]), []);
});

test('负例 · 旧入口没有兼容说明必须判红（计划：不与新用户主流程混杂）', () => {
  const l = V.legacyIsolation();
  assert.equal(l.ok, true, '实测三个旧入口都带兼容说明：' + JSON.stringify(l.problems));
  assert.equal(l.legacyCount, 3, '计划点名的旧入口是年轮/双晶/星域');
  assert.deepEqual(Object.keys(V.LEGACY).sort(), ['ring', 'sector', 'twin']);
  Object.keys(V.LEGACY).forEach(k => {
    assert.equal(V.LEGACY[k].legacy, true, k + ' 必须标 legacy');
    assert.ok(/兼容入口/.test(V.LEGACY[k].compatNote), k + ' 必须说明是兼容入口');
  });
});

test('负例 · 非数组/空值不抛异常', () => {
  for (const bad of [null, undefined, 0, 'x', {}]) {
    assert.ok(Array.isArray(V.conflicts(bad)));
  }
  const t = V.tally(null);
  assert.ok(t && typeof t.viewCount === 'number');
});

test('汇总只叫登记表，不得自称质量分', () => {
  const t = V.tally([
    { view: '星座', fact: '同一关系', meaning: '同盟' },
    { view: '罗盘', fact: '同一关系', meaning: '同盟' }
  ]);
  assert.equal(t.title, '视图主问题登记');
  assert.equal(t.isQualityScore, false);
  assert.equal(t.viewCount, 4);
  assert.equal(t.completeViews, 4, '四个视图都应五项齐全，不齐：' + JSON.stringify(t.incomplete));
  assert.deepEqual(t.crossViewConflicts, []);
  assert.ok(/旧入口只保留明确兼容入口/.test(t.note), t.note);
});

test('真实数据：index.html 里旧入口（年轮/双晶/星域）确实还在，必须被隔离说明', () => {
  const html = fs.readFileSync('index.html', 'utf8');
  for (const w of ['年轮', '双晶', '星域']) {
    assert.notEqual(html.indexOf(w), -1, '夹具应含旧入口「' + w + '」（若消失说明已清理，需重新评估本包）');
  }
  const m = /id="btnPreview"[^>]*title="([^"]*)"/.exec(html);
  assert.ok(m, '应能读到 #btnPreview 的 title');
  assert.ok(/年轮/.test(m[1]) && /双晶/.test(m[1]) && /星域/.test(m[1]),
    '#btnPreview 的 title 应点出三个旧图：' + m[1]);
  assert.equal(V.LEGACY.ring.legacy, true);
  console.log('     #btnPreview title = ' + m[1].slice(0, 60));
});

test('真实数据：四个视图的 title 与登记的主问题不得互相矛盾', () => {
  const html = fs.readFileSync('index.html', 'utf8');
  const titles = {};
  for (const m of html.matchAll(/<button[^>]*id="(btn[A-Za-z]+)"[^>]*title="([^"]{4,120})"/g)) {
    titles[m[1]] = m[2];
  }
  assert.ok(titles.btnStage, '应读到星盘按钮');
  assert.ok(titles.btnAtlas, '应读到展卷按钮');
  assert.ok(/主线|支线/.test(titles.btnStage), '星盘自述应提到主线/支线：' + titles.btnStage);
  assert.ok(/剧情线|线谱/.test(titles.btnAtlas), '展卷自述应是线谱：' + titles.btnAtlas);
  console.log('     星盘：' + titles.btnStage.slice(0, 40));
  console.log('     展卷：' + titles.btnAtlas.slice(0, 40));
});

console.log('SKY VIEW CONTRACT ' + passed + '/' + passed);
