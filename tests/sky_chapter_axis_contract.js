'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Source = require('../js/atlas/atlas-source.js');
const window = {};
const context = vm.createContext({ window });
for (const file of ['js/tree/storylines.js', 'js/sky/sky-model.js', 'js/sky/sky-deck-model.js']) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
}
function fixture(chapters) {
  const graph = { characters: [{ name: '甲', importance: 90 }], relations: [],
    events: chapters.map((chapter, i) => ({ id: 'e' + i, chapter, order: i + 1, title: '事件' + i, characters: ['甲'] })) };
  const tree = { chapters, threads: [{ id: 'main', kind: 'main', title: '完整故事线',
    events: graph.events.map((_, i) => i), span: { from: 0, to: chapters.length - 1 } }] };
  return { graph, tree };
}
function build(f) { return window.CLSkyModel.build(f.graph, f.tree); }
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
test('adjacent full, bare and end-of-chapter names share one position and preserve all events', () => {
  const f = fixture(['第十八回 贾文和料敌决胜', '第十八回', '第十八回（末）', '第十九回']);
  f.tree.threads.push({ id: 'branch', kind: 'branch', events: [2, 3], span: { from: 2, to: 3 } });
  const before = JSON.stringify(f), m = build(f);
  assert.equal(m.nCh, 2);
  assert.deepEqual(Array.from(m.chapterEvents, xs => Array.from(xs)), [[0, 1, 2], [3]]);
  assert.deepEqual([m.mains[0].c0, m.mains[0].c1, m.lines[0].c0, m.lines[0].c1], [0, 1, 0, 1]);
  assert.deepEqual(Array.from(m.chapters, c => c.no), [18, 19]);
  assert.equal(m.chapters[0].name, f.graph.events[0].chapter);
  assert.equal(JSON.stringify(f), before);
});
test('a later full title improves the chapter label without dropping the bare-name event', () => {
  const m = build(fixture(['第2章', '第二章 完整标题', '第二章（未题回目）', '第三章']));
  assert.equal(m.nCh, 2);
  assert.equal(m.chapters[0].name, '第二章 完整标题');
  assert.equal(m.chapterEvents[0].length, 3);
});
test('different titles, explicit volumes and reset chapter numbers never merge', () => {
  const f = fixture(['第一章 前卷开端', '第二章 前卷结尾', '第一章 后卷开端', '第一章 另一个标题', '第二卷 第一章', '第三卷 第一章']);
  const m = build(f);
  assert.equal(m.nCh, 6);
  assert.equal(m.axis.mode, 'seq');
  assert.equal(m.axis.volumes.length, 2);
  assert.equal(m.axis.summary, '6 个章节段');
});
test('appendices and chapter ranges remain separate and never invent a chapter number', () => {
  const m = build(fixture(['第一回', '附录 江流僧复仇报本', '第二回', '第七十五-七十六回', '第七十七回']));
  assert.equal(m.nCh, 5);
  assert.equal(m.axis.mode, 'no');
  assert.equal(m.chapters[1].no, null);
  assert.equal(m.chapters[3].no, null);
  assert.equal(m.chapters[4].no, 77);
  assert.equal(m.axis.summary, '3 回已解析 · 2 段其他材料');
});
test('short excerpts retain large original chapter numbers and missing chapters are not fabricated', () => {
  const m = build(fixture(['第一千章', '第一千零二章']));
  assert.deepEqual(Array.from(m.chapters, c => c.no), [1000, 1002]);
  assert.equal(m.nCh, 2);
  assert.equal(m.axis.summary, '2 章已解析');
});
test('card projection preserves appendix and range labels instead of coercing them to chapter zero', () => {
  const m = build(fixture(['第一章', '附录 旧事', '第三章']));
  assert.equal(window.CLSkyModel.chapterLabel(m, 1), '附录 旧事');
  assert.equal(window.CLSkyModel.chapterSpan(m, 0, 1), '第 1 章 — 附录 旧事');
  assert.equal(window.CLSkyModel.chapterSpan(m, 0, 2), '第 1–3 章');
  const cards = window.CLSkyDeckModel.build([{ id: 'extra', kind: 'main', label: '补充材料', c0: 1, c1: 1, no0: null, no1: null,
    chapter0: window.CLSkyModel.chapterLabel(m, 1), spanLabel: window.CLSkyModel.chapterSpan(m, 1, 1), events: 1 }]);
  assert.equal(cards[0].chapter0, '附录 旧事');
  assert.equal(cards[0].spanLabel, '附录 旧事');
});
test('compact chapter labels keep volume identity and source numbers without taking over event titles', () => {
  const m = build(fixture(['第一章 第一卷开端', '第二章 第一卷末尾', '第一章 第二卷开端', '第二章 第二卷末尾']));
  assert.equal(window.CLSkyModel.chapterLabel(m, 2), '卷2 · 第 1 章');
  assert.equal(window.CLSkyModel.chapterSpan(m, 0, 1), '卷1 · 第 1–2 章');
  assert.equal(window.CLSkyModel.chapterSpan(m, 1, 2), '卷1 · 第 2 章 — 卷2 · 第 1 章');
  assert.equal(m.chapters[2].name, '第一章 第二卷开端', 'full source heading is preserved in the model');
});
test('real Three Kingdoms aliases end at source chapter 120 and all events remain uniquely seekable', () => {
  const graph = Source.normalize(JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json', 'utf8')));
  const before = JSON.stringify(graph), tree = window.CLStory.analyze(graph), m = build({ graph, tree });
  assert.equal(m.axis.mode, 'no');
  assert.equal(m.chapters.at(-1).no, 120);
  assert.ok(m.nCh < tree.chapters.length);
  const indexes = Array.from(m.chapterEvents).flatMap(xs => Array.from(xs)).sort((a, b) => a - b);
  assert.deepEqual(indexes, graph.events.map((_, i) => i));
  const c18 = m.chapters.filter(c => c.raw === 18);
  assert.equal(c18.length, 1);
  for (const line of m.mains.concat(m.lines)) {
    assert.ok(line.c0 >= 0 && line.c1 < m.nCh && line.c0 <= line.c1);
    for (const ei of line.events) {
      const chapter = m.chapterEvents.findIndex(xs => xs.includes(ei));
      assert.ok(chapter >= line.c0 && chapter <= line.c1, 'line still covers each source event');
    }
  }
  assert.equal(JSON.stringify(graph), before);
  console.log('  Three Kingdoms: ' + m.nCh + ' positions; ' + m.axis.summary + '; ends at 120');
});
test('mechanical local stages remain explicitly derived throughout the reading model', () => {
  const graph = Source.normalize(JSON.parse(fs.readFileSync('data/cache/2ef47b2ecaa99a67352091d5.json', 'utf8')));
  const tree = window.CLStory.analyze(graph), m = build({ graph, tree });
  assert.equal(graph.meta.storylines.src, 'local-completion');
  assert.equal(m.derivedLines, true);
  assert.ok(m.mains.length > 0);
  assert.ok(m.mains.concat(m.lines).every(line => line.derived === true), 'cards cannot relabel a heuristic timeline as model analysis');
  assert.equal(m.mains.length + m.lines.length, tree.threads.length, 'all timeline data remains available');
  const f = fixture(['第一章', '第二章']);
  f.graph.meta = { completion: { method: 'existing-graph-local-completion' } };
  assert.equal(build(f).mains[0].derived, true, 'legacy completion metadata carries the same provenance');
});
test('未定位事件不再被排到结局之后（否则会把 120 回伪造成 111 段）', () => {
  const graph = Source.normalize(JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json', 'utf8')));
  const m = build({ graph, tree: window.CLStory.analyze(graph) });
  assert.equal(m.axis.mode, 'no', '三国必须按真实回号成轴，不能因为未定位行而退化成序号轴');
  assert.equal(m.chapters.at(-1).no, 120, '末章号必须仍是 120');
  const rep = graph.meta.eventOrdering;
  assert.equal(rep.exact, 318, 'exact 计数不得因排序改动而变化');
  assert.equal(rep.bounded, 105, 'bounded 计数不得因排序改动而变化');
  assert.equal(rep.unresolved, 11, 'unresolved 计数不得因排序改动而变化');
  const unresolved = graph.events.filter(e => e.sourcePosition && e.sourcePosition.kind === 'unresolved');
  assert.equal(unresolved.length, 11, '未定位就是未定位，不能靠排位置把它变成已定位');
  const tail = graph.events.slice(-11).map(e => String(e.chapter || '')).join('|');
  assert.doesNotMatch(tail, /第十回|第十二回|第五十回|第五十八回/,
    '缺锚点的早章事件不得再被停泊在全书末尾');
});
test('页面默认三国的章身份必须成轴（三种拼写/跨章区间都不得裂成两条）', () => {
  const graph = Source.normalize(JSON.parse(fs.readFileSync('data/cache/fe42d01f3826fe8096f86614.json', 'utf8')));
  const m = build({ graph, tree: window.CLStory.analyze(graph) });
  assert.equal(m.axis.mode, 'no', '三国必须按真实回号成轴，不能退化成序号轴');
  const raws = m.chapters.map(c => c.raw).filter(n => n != null);
  const drops = raws.filter((n, i) => i > 0 && n <= raws[i - 1]);
  assert.equal(drops.length, 0, '章回轴上出现了回号回落（章顺序错乱）');
  const seen = Object.create(null), dup = [];
  m.chapters.forEach(c => { if (c.raw == null) return;
    if (seen[c.raw] != null) dup.push(c.raw); else seen[c.raw] = 1; });
  assert.equal(dup.length, 0, '同一回号在轴上出现了两次：' + JSON.stringify(dup.slice(0, 8)));
  assert.equal(m.chapters.at(-1).no, 120, '末章号必须是 120');
  const rep = graph.meta.eventOrdering;
  assert.equal(rep.exact, 1170);
  assert.equal(rep.bounded, 105);
  assert.equal(rep.unresolved, 11);
  assert.equal(graph.events.length, 1286, '适配器不得增删事件');
});
console.log('SKY CHAPTER AXIS ' + passed + '/' + passed);
test('跨卷同名章号不得把未定位事件夹到别卷（大奉 5 个「第一章」）', () => {
  const graph = Source.normalize(JSON.parse(fs.readFileSync('data/cache/1063b17ca65ec1b76f30e460.json', 'utf8')));
  const name = '第一章 生母';
  const i = graph.events.findIndex(e => String(e.chapter) === name);
  assert.ok(i >= 0, '夹具必须含「' + name + '」');
  const target = graph.events[i];
  assert.equal((target.sourcePosition || {}).kind, 'unresolved', '它必须仍是未定位（修的是显示位置，不是定位结论）');
  let prevStart = null;
  for (let k = i - 1; k >= 0; k--) {
    const sp = graph.events[k].sourcePosition || {};
    if (typeof sp.start === 'number') { prevStart = sp.start; break; }
  }
  assert.ok(prevStart != null, '必须能取到前一条已定位事件的偏移');
  assert.ok(prevStart > 3500000,
    '「' + name + '」是最后一卷卷首，前一条已定位事件应在全书后段（实际偏移 ' + prevStart + '）');
  const rep = graph.meta.eventOrdering;
  assert.equal(rep.exact, 2241, 'exact 不得因排序改动而变化');
  assert.equal(rep.bounded, 669, 'bounded 不得因排序改动而变化');
  assert.equal(rep.unresolved, 80, 'unresolved 不得因排序改动而变化');
});
