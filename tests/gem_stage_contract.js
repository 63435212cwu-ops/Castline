/* JSC: gem data / chapter-state / arc interaction contract.
 * Run from the project root with JavaScriptCore's jsc binary.
 * No private novel, browser, network or LLM calls are needed.
 */
var window = this;
var performance = { now: function () { return 0; } };
var navigator = { hardwareConcurrency: 8 };
var rafs = {}, rafId = 0, subscribers = [];
function requestAnimationFrame(fn) { rafs[++rafId] = fn; return rafId; }
function cancelAnimationFrame(id) { delete rafs[id]; }
function getComputedStyle() { return { getPropertyValue: function () { return ''; } }; }
function matchMedia() { return { matches: false }; }
function CustomEvent(type, options) { this.type = type; this.detail = options.detail; }
var CLAbyssBreath = { subscribe: function (fn) { subscribers.push(fn); return function () { subscribers.splice(subscribers.indexOf(fn), 1); }; } };
function node(tag) {
  var n = { tagName: tag, children: [], attrs: {}, listeners: {}, textContent: '', parentNode: null };
  n.setAttribute = function (key, value) { n.attrs[key] = String(value); };
  n.getAttribute = function (key) { return Object.prototype.hasOwnProperty.call(n.attrs, key) ? n.attrs[key] : null; };
  n.removeAttribute = function (key) { delete n.attrs[key]; };
  n.appendChild = function (child) { n.children.push(child); child.parentNode = n; return child; };
  n.removeChild = function (child) { n.children.splice(n.children.indexOf(child), 1); child.parentNode = null; };
  n.addEventListener = function (type, fn) { (n.listeners[type] || (n.listeners[type] = [])).push(fn); };
  n.removeEventListener = function (type, fn) { n.listeners[type] = (n.listeners[type] || []).filter(function (f) { return f !== fn; }); };
  n.dispatchEvent = function (event) { (n.listeners[event.type] || []).slice().forEach(function (fn) { fn(event); }); };
  n.querySelectorAll = function () { var out = []; n.children.forEach(function (c) { out.push(c); out = out.concat(c.querySelectorAll()); }); return out; };
  n.classList = {
    contains: function (k) { return (' ' + (n.attrs['class'] || '') + ' ').indexOf(' ' + k + ' ') >= 0; },
    add: function (k) { if (!n.classList.contains(k)) n.attrs['class'] = ((n.attrs['class'] || '') + ' ' + k).trim(); },
    remove: function (k) { n.attrs['class'] = (n.attrs['class'] || '').split(' ').filter(function (s) { return s !== k; }).join(' '); }
  };
  Object.defineProperty(n, 'firstChild', { get: function () { return n.children[0] || null; } });
  return n;
}
var document = node('document');
document.documentElement = node('html'); document.body = node('body');
document.createElement = node;
document.createElementNS = function (_, tag) { return node(tag); };
document.createTextNode = function (text) { var n = node('#text'); n.textContent = text; return n; };
load('js/charts/radar.js');
load('js/charts/radar-benchmark.js');
load('js/gem/gem-model.js');
load('js/gem/gem-morph.js');
load('js/gem/gem-svg.js');
load('js/gem/gem-arc.js');
(function () {
  'use strict';
  var passed = 0, failed = 0;
  function ok(name, yes) { if (yes) { passed++; print('PASS ' + name); } else { failed++; print('FAIL ' + name); } }
  function byClass(root, cls) { return root.querySelectorAll('*').filter(function (n) { return n.classList.contains(cls); }); }
  function attrs(value) { var a = {}; CLRadar.KEYS.forEach(function (k) { a[k] = { score: value, evidence: ['synthetic fixture'] }; }); return a; }
  var a = { id: 'person-a', name: '甲', camp: '前庭', attrs: attrs(60) };
  var b = { id: 'person-b', name: '乙', camp: '前庭', attrs: attrs(80) };
  var pending = { name: '未建档', attrs: attrs(null) };
  a.attrs['智谋'] = { score: 0 };
  a.attrs['实力'] = { score: 99, pending: true };
  a.attrs['意志'] = { score: null };
  a.attrs['魅力'] = { score: false };
  var G = { characters: [a, b, pending], events: [{ chapter: '起', characters: ['甲'] }, { chapter: '承', characters: ['甲'] }, { chapter: '终', characters: ['甲'] }] };
  var metaKeys = ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
  function metaOf(name) {
    var score = {}; metaKeys.forEach(function (k) { score[k] = name === '甲' ? 200 : 400; });
    return { score: score, known: { 光明面: false } };
  }
  var bench = CLRadarBenchmark.computeBenchmark(G.characters);
  var atlas = { ok: true, chapters: [{ idx: 0, name: '起' }, { idx: 1, name: '承' }, { idx: 2, name: '终' }], lines: [],
    events: [{ i: 72, order: 11, chapIdx: 0, chapName: '起', title: '零值已知', cast: ['甲'], lineIds: ['l1'] },
      { i: 19, order: 37, chapIdx: 1, chapName: '承', title: '有据变化', cast: ['甲'], lineIds: [] }] };
  var ctx = { metaOf: metaOf, bench: bench, atlas: atlas, peerName: '乙' };
  var M = CLGemModel.build(a, G, ctx);
  ok('real zero is known with exact zero score', M.attr[0].known && M.attr[0].score === 0);
  ok('null/pending/boolean are unknown, not zero', !M.attr[1].known && !M.attr[2].known && !M.attr[3].known && M.attr[1].score === null);
  ok('book rank excludes every unknown score', M.attr[0].rank === 2 && M.attr[0].n === 2 && M.attr[1].rank === null && M.attr[1].n === 1);
  ok('benchmark and peer use same score semantics', M.ghost.book[0] === 40 && M.ghost.book[1] === 80 && M.peer.delta[1] === null && M.peer.delta[0] === -80);
  ok('narrative scales preserve raw score and share global range', M.meta[0].score === 50 && M.meta[0].rawScore === 200 && M.meta[0].scaleMax === 400 && M.meta[0].rank === 3);
  ok('narrative explicit unknown does not enter ranks', M.meta[6].score === null && M.meta[6].rank === null && M.meta[6].n === 0);
  ok('arc event locators use atlas array index, never source index', M.arc.events[0].eventIdx === 0 && M.arc.events[0].sourceEventIdx === 72 && M.arc.events[0].order === 11);
  var ref = { verified: true, status: 'verified', quote: 'synthetic fixture', sourceId: 'fixture', start: 0, end: 17, offsetUnit: 'codepoint' };
  G.characterStates = [{ id: 'state-a', characterId: 'person-a', chapterRange: ['承', '承'], attrs: { 智谋: { score: 0 }, 实力: { score: 23 } }, sourceRefs: [ref] }];
  ctx.chapter = '承';
  var observed = CLGemModel.build(a, G, ctx);
  ok('only sourced matching state changes attribute crystal', observed.stage.scope === 'chapter' && observed.stage.id === 'state-a' && observed.stage.verified && observed.attr[1].score === 23);
  ok('partial snapshot leaves other dimensions unknown, not book imputation', observed.attr[4].score === null && observed.attr[0].score === 0);
  ok('snapshot rank replaces its book self, never N+1', observed.attr[1].rank === 2 && observed.attr[1].n === 2 && observed.attr[0].rank <= observed.attr[0].n);
  ok('chapter snapshots do not rewrite original book character', a.attrs['情感'].score === 60 && a.attrs['实力'].pending === true);
  ok('axis evidence falls back to clearly scoped stage provenance', observed.attr[0].sourceScope === 'stage' && observed.attr[0].sourceRefs[0].quote === ref.quote && observed.attr[4].sourceRefs.length === 0);
  observed.attr[0].sourceRefs[0].quote = 'edited view'; observed.stage.attrs['智谋'].score = 99;
  ok('model provenance and state attributes never alias source data', G.characterStates[0].sourceRefs[0].quote === 'synthetic fixture' && G.characterStates[0].attrs['智谋'].score === 0);
  ctx.chapter = '终'; var outside = CLGemModel.build(a, G, ctx);
  ok('snapshot does not carry forward outside observed range', outside.stage.scope === 'book' && outside.attr[1].score === null && outside.attr[4].score === 60);
  ctx.chapter = '承'; G.characterStates[0].sourceRefs = [];
  ok('unsourced state never changes geometry', CLGemModel.build(a, G, ctx).stage.scope === 'book');
  G.characterStates[0].sourceRefs = [{ status: 'unverified', verified: false }];
  var unverified = CLGemModel.build(a, G, ctx);
  ok('unverified observed state is explicitly low confidence', unverified.stage.verified === false && unverified.attr[1].conf === 'low');
  G.characterStates.push(G.characterStates[0]);
  var ambiguous = CLGemModel.build(a, G, ctx);
  ok('overlapping states are not arbitrarily selected', ambiguous.stage.reason === 'ambiguous-observed-states' && ambiguous.stage.scope === 'book');
  var host = node('host'), got = [];
  document.addEventListener('cl:gem-event', function (event) { got.push(event.detail); });
  var arc = CLGemArc.mount(host, M), hits = byClass(arc, 'cl-gem-arc__hit');
  arc.dispatchEvent({ type: 'click', target: hits[0], preventDefault: function () {} });
  arc.dispatchEvent({ type: 'keydown', key: 'Enter', target: hits[1], preventDefault: function () {} });
  arc.dispatchEvent({ type: 'keydown', key: ' ', target: hits[2], preventDefault: function () {} });
  ok('arc mouse click emits real order/event location', got[0].name === '甲' && got[0].order === 11 && got[0].eventIdx === 0);
  ok('arc Enter has identical event location semantics', got[1].order === 37 && got[1].chapIdx === 1 && got[1].eventIdx === 1);
  ok('empty chapter Space does not invent an event', got[2].eventIdx === null && got[2].order === null && got[2].chapIdx === 2);
  CLGemArc.update(M); CLGemArc.unmount();
  ok('arc unmount releases DOM and both listeners', host.children.length === 0 && arc.listeners.click.length === 0 && arc.listeners.keydown.length === 0);
  var longModel = { name: '甲', arc: { chapters: 1200, hits: [], first: 0, last: 1199, known: true, lines: [], events: [] } };
  for (var li = 0; li < 1200; li++) longModel.arc.hits.push(li % 3);
  var longArc = CLGemArc.mount(host, longModel);
  ok('long novel arc uses bounded chapter aggregation', CLGemArc.stats().chapters === 1200 && CLGemArc.stats().hits === 80 && longArc.querySelectorAll('*').length < 120);
  CLGemArc.unmount();
  var svg = CLGemSVG.mount(node('svgHost'), M);
  CLGemSVG.setAxis('情感'); CLGemSVG.setPaused(true);
  CLGemSVG.update(unverified);
  ok('pause settles data without animation and releases breath subscriptions', !CLGemSVG.stats().animating && CLGemSVG.stats().paused && !CLGemSVG.stats().breathSub && Object.keys(rafs).length === 0);
  CLGemSVG.setPaused(false); CLGemSVG.update(unverified);
  ok('unverified chapter state has no growth animation', !CLGemSVG.stats().animating);
  var selected = [], badge = byClass(svg, 'cl-gem-badge')[1];
  document.addEventListener('cl:radar-axis-select', function (event) { selected.push(event.detail.key); });
  svg.dispatchEvent({ type: 'keydown', key: 'Enter', target: badge, preventDefault: function () {} });
  ok('crystal axis badge keyboard selection is available', selected[0] === '实力' && badge.getAttribute('role') === 'button');
  CLGemSVG.unmount();
  ok('SVG unmount has no pending animation/listener', Object.keys(rafs).length === 0 && svg.listeners.click.length === 0 && svg.listeners.keydown.length === 0);
  print('GEM STAGE CONTRACT ' + passed + ' passed / ' + failed + ' failed');
  if (failed) quit(1);
})();
