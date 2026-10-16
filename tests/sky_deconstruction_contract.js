'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const js = fs.readFileSync(path.join(ROOT, 'js/sky/sky-deconstruction.js'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'css/sky-deep-hud.css'), 'utf8');
const readingCSS = fs.readFileSync(path.join(ROOT, 'css/sky-reading.css'), 'utf8');
let count = 0;
function check(name, condition) {
  assert.ok(condition, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

check('tabpanel exposes the active tab to assistive technology',
  js.includes('role="tabpanel"') && js.includes('aria-labelledby="skyDeconTabOverview"') &&
  js.includes("body.setAttribute('aria-labelledby'"));
check('evidence summary reports original-text anchoring and all four provenance buckets',
  js.includes('原文锚定') && js.includes("basisCounts['原文']") &&
  js.includes("basisCounts['归纳']") && js.includes("basisCounts['推导']") &&
  js.includes("basisCounts['未核验']"));
check('evidence rows carry a spoken label and selected state',
  js.includes('aria-label="\' + esc(label)') && js.includes("aria-current=\"true\""));
check('empty pulse chapters are inert spans instead of dead keyboard buttons',
  js.includes('sd-pulse-bar is-empty') && js.includes('无可定位事件') &&
  js.includes("if (first == null) return"));
check('line and event redraws restore the originating focus target',
  js.includes('state.restore = { attr: \'data-line-id\'') &&
  js.includes('state.restore = { attr: \'data-event-index\'') &&
  js.includes('function restoreFocus(body)') && js.includes('scrollIntoView'));
check('plot jumps close the panel and return focus to the deconstruction entry',
  js.includes('function closeToPlot()') && js.includes("doc.addEventListener('cl:sky-plot'") &&
  js.includes('button.focus({ preventScroll: true })'));
check('the focus target is consumed after one render',
  js.includes('state.restore = null;') && js.includes('found.focus({ preventScroll: true })'));
check('narrow evidence summary wraps and narrow stats use a readable three-column grid',
  css.includes('.sd-evidence-counts { display: flex; flex-wrap: wrap;') &&
  css.includes('.sd-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }'));
check('empty pulse treatment and scroll focus treatment are present',
  css.includes('.sd-pulse-bar.is-empty') && css.includes('.sd-scroll:focus-visible'));
check('reduced-motion still disables deconstruction transitions',
  css.includes('@media (prefers-reduced-motion: reduce)') && css.includes('.sd-event'));
const readerWindow = { document: { addEventListener() {} }, addEventListener() {} };
const context = vm.createContext({ window: readerWindow });
for (const file of ['js/atlas/atlas-source.js', 'js/tree/storylines.js', 'js/sky/sky-model.js', 'js/sky/sky-causal-type.js']) {
  vm.runInContext(fs.readFileSync(path.join(ROOT, file), 'utf8'), context, { filename: file });
}
vm.runInContext(js.replace('  g.CLSkyDeconstruction =', `
  g.citationGroupsForTest = function (book, refId) { graph = book; m106.indexGraph = null; m106.byRef = null; return citationIndex()[refId] || null; };
  g.citationMarkupForTest = function (book, refId, page) { graph = book; m106.indexGraph = null; m106.byRef = null; m106.open = true; m106.view = 'group'; m106.refId = refId; m106.page = page || 0; return renderSharedCitation(refId); };
  g.citationLocatorForTest = citationLocator;
  g.renderLinesForTest = function (book, projection, focus) {
    graph = book; model = projection; state.focus = focus || null;
    return renderLines();
  };
  g.renderCausalForTest = function (book, projection, sourceIndex, filter, query, forkPage) {
    graph = book; model = { narrative: projection }; state.mode = 'causal'; browse.causal.filter = filter || 'all'; browse.causal.query = query || ''; browse.causal.page = 0; browse.causalFork.page = forkPage || 0; causalFork.source = sourceIndex; causalFork.returnTo = null; index = { layers: { causeEdges: arguments[6] || [] } }; return renderCausal();
  };
  g.analyzeCausalForkForTest = function (book, projection, sourceIndex, scope) { graph = book; model = { narrative: projection }; return analyzeCausalFork(sourceIndex, projection.architecture.edges, projection.architecture.nodes, book, scope); };
  g.causalForkSourceUniqueForTest = function (book, eventIndex) { return stableEventIdentity(eventIndex, book); };
  g.m88ReaderForTest = function (book, player, scope, selected, query) {
    graph = book; model = g.CLSkyModel.build(book, g.CLStory.analyze(book)); index = buildIndex();
    m88.orderByIndex = [];
    arr(model.narrative.architecture.nodes).forEach(function (n) { m88.orderByIndex[n.index] = causalNodeOrder(n, graph); });
    g.CLSky = { playerState: function () { return player; } };
    m88.scope = scope || 'reading'; m88.recordId = selected || null; m88.source = null; m88.sourceStatus = null; m88.snapshot = null;
    browse.foreshadow.query = query || ''; browse.foreshadow.filter = 'all'; browse.foreshadow.page = 0;
    state.mode = 'foreshadow'; var html = renderForeshadow();
    var rec = model.narrative.foreshadowLifecycles.find(function (x) { return x.ownerId === selected; });
    var visibility = rec ? m88Visibility(rec, m88Range()) : null;
    var seedRef = rec ? m88Ref(rec, 'seed') : null, payoffRef = rec ? m88Ref(rec, 'payoff') : null;
    state.mode = 'causal'; causalFork.source = null; var causal = renderCausal();
    return { html: html, causal: causal, visibility: visibility, seedRef: seedRef, payoffRef: payoffRef };
  };

  g.CLSkyDeconstruction =`), context);
const m87Graph = { events: Array.from({ length: 32 }, (_, i) => ({ id: 'm87-' + i, title: 'M87 事件 ' + i, order: i + 1 })) };
const m87Nodes = m87Graph.events.map((e, i) => ({ index: i, id: e.id, order: e.order, title: e.title }));
const m87Edges = Array.from({ length: 26 }, (_, i) => ({ source: 0, target: i + 1, ownerId: 'm87-edge-' + i, basisCode: i === 1 ? 'inference' : 'explicit', description: '分支 ' + i }));
m87Edges.push({ source: 0, target: 31, ownerId: 'm87-veto', basisCode: 'explicit', type: 'sequence', description: '随后' });
const m87Projection = { architecture: { nodes: m87Nodes, edges: m87Edges, roots: [0], leaves: [], unresolved: [], stats: {} } };
const m87Markup = readerWindow.renderCausalForTest(m87Graph, m87Projection, 0);
const m87ForkMarkup = (m87Markup.match(/<section class=\"sd-causal-fork\"[\s\S]*?<\/section>/) || [''])[0];
check('M87 draws at most three directed SVG edges while paginating the complete 26-edge declaration set',
  m87Markup.includes('当前范围 26 条记录，演示 3/26') && (m87Markup.match(/data-path-animate="true"/g) || []).length === 3 && (m87Markup.match(/class="sd-fork-edge/g) || []).length === 24 && m87Markup.includes('data-page-mode="causalFork"'));
check('M87 keeps inference dashed and labeled and filters forbidden sequence edges',
  m87ForkMarkup.includes('· 推断') && m87ForkMarkup.includes('is-inference') && !m87ForkMarkup.includes('m87-veto') && m87ForkMarkup.includes('排除非因果类型与自循环 1 条'));
const m87SecondPage = readerWindow.renderCausalForTest(m87Graph, m87Projection, 0, 'all', '', 1);
check('M87 page two reaches every remaining declaration',
  m87SecondPage.includes('data-record-id=\"m87-edge-24\"') && m87SecondPage.includes('data-record-id=\"m87-edge-25\"') && (m87SecondPage.match(/class="sd-fork-edge/g) || []).length === 2);
const m87DuplicateEndpoint = { architecture: { nodes: m87Nodes, edges: [m87Edges[0], Object.assign({}, m87Edges[0], { ownerId: 'm87-duplicate-record' })], roots: [0], leaves: [1], unresolved: [], stats: {} } };
const m87DuplicateMarkup = readerWindow.renderCausalForTest(m87Graph, m87DuplicateEndpoint, 0);
check('M87 retains separate declarations for a repeated endpoint but outlines its event once',
  (m87DuplicateMarkup.match(/class="sd-fork-targets"[\s\S]*?<li/g) || []).length === 1 && (m87DuplicateMarkup.match(/class="sd-fork-edge/g) || []).length === 2 && m87DuplicateMarkup.includes('m87-duplicate-record'));
const m87MergeProjection = { architecture: { nodes: m87Nodes, edges: [
  { source: 0, target: 1, ownerId: 'merge-a', basisCode: 'explicit' }, { source: 0, target: 2, ownerId: 'merge-b', basisCode: 'inference' },
  { source: 1, target: 3, ownerId: 'merge-out-a', basisCode: 'explicit' }, { source: 2, target: 3, ownerId: 'merge-out-b', basisCode: 'explicit' },
  { source: 4, target: 3, ownerId: 'merge-extra', basisCode: 'explicit' }
], roots: [0], leaves: [3], unresolved: [], stats: {} } };
const m87Merge = readerWindow.analyzeCausalForkForTest(m87Graph, m87MergeProjection, 0, m87MergeProjection.architecture.edges.slice(0, 4));
const m87MergeMarkup = readerWindow.renderCausalForTest(m87Graph, m87MergeProjection, 0);
check('M87 marks only direct common targets and labels a real prerequisite outside the active scope',
  m87Merge.shared.length === 1 && m87Merge.shared[0].index === 3 && m87Merge.shared[0].extraPrerequisite && m87Merge.shared[0].hiddenPrerequisite && m87MergeMarkup.includes('已记录的直接共同目标') && m87MergeMarkup.includes('另有前提'));
const m87CycleProjection = { architecture: { nodes: m87Nodes, edges: [{ source: 0, target: 1, ownerId: 'cycle-a', basisCode: 'explicit' }, { source: 1, target: 0, ownerId: 'cycle-b', basisCode: 'explicit' }], roots: [0], leaves: [], unresolved: [], stats: {} } };
const m87Cycle = readerWindow.analyzeCausalForkForTest(m87Graph, m87CycleProjection, 0);
const m87UnknownNodes = m87Nodes.map(n => Object.assign({}, n)); m87UnknownNodes[1].order = null;
const m87UnknownProjection = { architecture: { nodes: m87UnknownNodes, edges: [{ source: 0, target: 1, ownerId: 'unknown-order', basisCode: 'explicit' }], roots: [0], leaves: [1], unresolved: [], stats: {} } };
const m87Unknown = readerWindow.analyzeCausalForkForTest(m87Graph, m87UnknownProjection, 0);
check('M87 holds animation for cycles, missing order, reverse order and equal-order conflicts',
  m87Cycle.cycle && m87Cycle.staticReason.includes('循环') && m87Unknown.unknownOrder && m87Unknown.staticReason.includes('顺序缺失') &&
  readerWindow.analyzeCausalForkForTest(m87Graph, { architecture: { nodes: m87Nodes, edges: [{ source: 2, target: 1 }], stats: {} } }, 2).unknownOrder &&
  readerWindow.analyzeCausalForkForTest({ events: m87Graph.events.map((e, i) => Object.assign({}, e, { order: i < 2 ? 1 : e.order })) }, { architecture: { nodes: m87Nodes.map((n, i) => Object.assign({}, n, { order: i < 2 ? 1 : n.order })), edges: [{ source: 0, target: 1 }], stats: {} } }, 0).unknownOrder);
check('M87 source navigation rejects missing, repeated, conflicting identity but accepts ID zero',
  !readerWindow.causalForkSourceUniqueForTest({ events: [{ title: 'missing' }] }, 0) &&
  !readerWindow.causalForkSourceUniqueForTest({ events: [{ id: 'x', entityId: 'y' }] }, 0) &&
  !readerWindow.causalForkSourceUniqueForTest({ events: [{ id: 'dup' }, { id: 'dup' }] }, 0) &&
  readerWindow.causalForkSourceUniqueForTest({ events: [{ id: 0 }] }, 0));
const xiyouM87Graph = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/cache/ed3dc1255ca08fbdaae30bbd.json'), 'utf8'));
const xiyouM87Model = readerWindow.CLSkyModel.build(xiyouM87Graph, readerWindow.CLStory.analyze(xiyouM87Graph));
const xiyouM87SourceIndex = xiyouM87Graph.events.findIndex(e => e.id === 'ev_chechi_forced_labor');
const xiyouM87Nodes = xiyouM87Model.narrative.architecture.nodes, xiyouM87NodeIndex = xiyouM87Nodes.findIndex(n => n.index === xiyouM87SourceIndex);
const xiyouM87Scope = xiyouM87Model.narrative.architecture.edges.filter(e => e.source === xiyouM87NodeIndex);
const xiyouM87Analysis = readerWindow.analyzeCausalForkForTest(xiyouM87Graph, xiyouM87Model.narrative, xiyouM87NodeIndex, xiyouM87Scope);
check('M87 keeps the fixed Xiyou source static when its published event orders are unknown',
  xiyouM87Scope.length === 2 && xiyouM87Scope.some(e => e.basisCode === 'inference') && xiyouM87Analysis.unknownOrder && xiyouM87Analysis.staticReason.includes('静态说明'));
const normalizedUnknownGraph = { events: [{ id: 'n0', order: 219, rawOrderKnown: false, rawOrder: null }, { id: 'n1', order: 220, rawOrderKnown: false, rawOrder: null }] };
const normalizedUnknownProjection = { architecture: { nodes: [{ index: 0, id: 'n0', order: 219 }, { index: 1, id: 'n1', order: 220 }], edges: [{ source: 0, target: 1, ownerId: 'normalized-unknown', basisCode: 'explicit' }], stats: {} } };
const normalizedUnknown = readerWindow.analyzeCausalForkForTest(normalizedUnknownGraph, normalizedUnknownProjection, 0);
check('M87 treats runtime-reordered finite order as unknown when rawOrderKnown is false',
  normalizedUnknown.unknownOrder && normalizedUnknown.staticReason.includes('静态说明'));
const orderedM87Graph = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/cache/b1687d1214f4d6c8bcd06c6f.json'), 'utf8'));
const orderedM87Model = readerWindow.CLSkyModel.build(orderedM87Graph, readerWindow.CLStory.analyze(orderedM87Graph));
const orderedM87SourceIndex = orderedM87Graph.events.findIndex(e => e.id === 'ev_80d34e18d09b960f');
const orderedM87Nodes = orderedM87Model.narrative.architecture.nodes, orderedM87NodeIndex = orderedM87Nodes.findIndex(n => n.index === orderedM87SourceIndex);
const orderedM87Scope = orderedM87Model.narrative.architecture.edges.filter(e => e.source === orderedM87NodeIndex);
const orderedM87Analysis = readerWindow.analyzeCausalForkForTest(orderedM87Graph, orderedM87Model.narrative, orderedM87NodeIndex, orderedM87Scope);
const orderedM87Markup = readerWindow.renderCausalForTest(orderedM87Graph, orderedM87Model.narrative, orderedM87NodeIndex);
check('M87 runs the real ordered 三国 fork through its published model with both directed SVG edges',
  orderedM87Scope.length === 2 && orderedM87Scope.every(e => e.basisCode === 'explicit') && !orderedM87Analysis.staticReason && orderedM87Analysis.outgoing.length === 2 && (orderedM87Markup.match(/class=\"sd-fork-path/g) || []).length === 2 && orderedM87Markup.includes('徐庶走马荐诸葛'));

const graph = {
  characters: [{ name: '甲', importance: 90 }], relations: [],
  events: Array.from({ length: 6 }, (_, i) => ({ order: i + 1, title: '事件' + (i + 1), chapter: '第' + (i + 1) + '章', characters: ['甲'] })),
  storylines: [
    { id: 'auto1', kind: '主线', name: '自动阶段一', events: [1, 2] },
    { id: 'auto2', kind: '主线', name: '自动阶段二', events: [3, 4] },
    { id: 'goal', kind: '主线', name: '穿过漫长山路寻找失踪亲人并带回救援消息的完整线路名', goal: '寻找失踪亲人并带回救援消息', events: [5, 6] },
    { id: 'branch', kind: '支线', name: '仅末章出现的目标线', goal: '把求助消息送到城中援军', parent: 'goal', attach_order: 5, events: [6] }
  ]
};
const original = JSON.stringify(graph), tree = readerWindow.CLStory.analyze(graph), model = readerWindow.CLSkyModel.build(graph, tree);
const all = Array.from(model.mains).concat(Array.from(model.lines));
const html = readerWindow.renderLinesForTest(graph, model);
check('tree honesty survives both main and branch sky projections', all.every(line => {
  const thread = tree.threads.find(t => t.id === line.id);
  return ['objective', 'objectiveText', 'autoSegment'].every(key => line[key] === thread[key]);
}) && all.some(line => line.kind === 'branch' && line.objective === 'declared'));
check('automatic segments are collapsed without deleting their event or location entries',
  html.includes('<details class="sd-auto-lines"><summary>自动分段 2 条') &&
  (html.match(/data-line-id=/g) || []).length === all.length && JSON.stringify(graph) === original);
check('full line names, true chapter range, source and objective remain visible together',
  html.includes('<span class="sd-line-name">' + graph.storylines[2].name + '</span>') &&
  html.includes('目标声明：' + graph.storylines[2].goal) && html.includes('第 5–6 章') &&
  html.includes('sd-line-basis') && !html.includes('<i>高潮</i>'));
const branch = all.find(line => line.sourceId === 'branch');
const escapedBranch = branch.id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const branchRow = html.match(new RegExp('data-line-id="' + escapedBranch + '"[\\s\\S]*?</button>'))[0];
const bounds = branchRow.match(/data-sd-l="([0-9.]+)" data-sd-w="([0-9.]+)"/);
check('a final-chapter-only storyline occupies visible space inside the time track',
  Number(bounds[1]) < 100 && Number(bounds[2]) > 0 && Math.abs(Number(bounds[1]) + Number(bounds[2]) - 100) < .01);
const automatic = all.find(line => line.autoSegment);
check('restoring an automatic-line focus opens its enclosing disclosure',
  readerWindow.renderLinesForTest(graph, model, automatic.id).includes('<details class="sd-auto-lines" open>'));
const none = readerWindow.CLSkyModel.build({ characters: [], relations: [], events: [], storylines: [] });
check('an empty story map gives an explicit empty state without a fabricated climax',
  readerWindow.renderLinesForTest({ storylines: [] }, none).includes('这份材料没有可绘制的剧情线') &&
  !readerWindow.renderLinesForTest({ storylines: [] }, none).includes('<i>高潮</i>'));

const c3Graph = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/cache/ed3dc1255ca08fbdaae30bbd.json'), 'utf8'));
const c3Event = c3Graph.events.find(e => e.id === 'ev_3ed3f837fd6980ce');
const c3State = c3Graph.characterStates.find(e => e.id === 'characterState_review_d2553588a3653e602b1b');
if (!c3Event || !c3State) throw new Error('required frozen C3 event/state fixture missing');
const c3Ref = readerWindow.CLAtlasSource.sourceRefs(c3Event).find(ref => ref.quote === c3Event.quote);
if (!c3Ref) throw new Error('required complete C3 event sourceRef missing');
const c3RefId = readerWindow.CLAtlasSource.sourceRefId(c3Ref);
if (!c3RefId) throw new Error('complete C3 sourceRef has no stable locator identity');
const c3Group = readerWindow.citationGroupsForTest(c3Graph, c3RefId);
check('fixed C3 locator resolves its declared event and state by layer plus stable ID without hard-coded total N',
  !!c3Group && c3Group.records.some(row => row.layer === 'events' && row.id === c3Event.id) &&
  c3Group.records.some(row => row.layer === 'characterStates' && row.id === c3State.id) &&
  new Set(c3Group.records.map(row => row.layer + ':' + row.id)).size === c3Group.records.length && c3Group.records.length >= 2 &&
  c3Group.records.find(row => row.layer === 'events').status.semantic !== c3Group.records.find(row => row.layer === 'characterStates').status.semantic);
const c3Markup = readerWindow.citationMarkupForTest(c3Graph, c3RefId);
function citationLineCount(markup) {
  return (markup.match(/(?:^|[ \t\r\n\f])class="(?:[^"]*[ \t\r\n\f])?sd-citation-line(?=[ \t\r\n\f]|")/g) || []).length;
}
check('citation line counting accepts the exact class token with state classes before or after it',
  citationLineCount('<i class="sd-citation-line"></i><i class="is-current sd-citation-line"></i>' +
    '<i class="sd-citation-line is-active"></i><i class="is-current\tsd-citation-line\nis-active"></i>') === 4);
check('citation line counting excludes progress, longer names, prefixes and non-class attributes',
  citationLineCount('<i class="sd-citation-line-progress"></i><i class="prefix-sd-citation-line"></i>' +
    '<i class="sd-citation-lineage"></i><i class="xsd-citation-line"></i><i data-class="sd-citation-line"></i>') === 0);
check('C3 group keeps the source quote visible, connects cards without arrows and exposes the computed count',
  c3Markup.includes(c3Event.quote) && c3Markup.includes(c3Group.records.length + ' 条可唯一定位记录') &&
  citationLineCount(c3Markup) === Math.min(c3Group.records.length, 24) &&
  (c3Markup.match(/data-citation-step=/g) || []).length <= 6 && !c3Markup.includes(c3Ref.sourceId) && !c3Markup.includes(c3Ref.textHash));
check('C3 layout uses a persistent source connector, an unarrowed record rail and readable reduced-motion final cards',
  readingCSS.includes('.sd-citation-origin::after') && readingCSS.includes('.sd-citation-list {') &&
  readingCSS.includes('.sd-citation-line {') && readingCSS.includes('.sd-citation-card.is-animated {') &&
  readingCSS.includes('.sd-citation-card.is-animated { opacity: 1 !important; transform: none !important; }') &&
  readingCSS.includes('.sd-citation-trigger, .sd-citation-source, .sd-citation-pages button'));
const c3Large = JSON.parse(JSON.stringify(c3Graph));
c3Large.tasks = c3Large.tasks || [];
for (let i = 0; i < 30; i++) c3Large.tasks.push({ id: 'cpu-citation-' + i, sourceRefs: [Object.assign({}, c3Ref)] });
const largeGroup = readerWindow.citationGroupsForTest(c3Large, c3RefId);
const largePage = readerWindow.citationMarkupForTest(c3Large, c3RefId, 1);
check('large citation groups stay bounded to 24 visible cards and remain reachable by paging',
  largeGroup.records.length >= c3Group.records.length + 30 && (largePage.match(/class="sd-citation-card/g) || []).length <= 24 &&
  largePage.includes('上一页') && largePage.includes('下一页') && (largePage.match(/data-citation-step=/g) || []).length === 0);
const sameQuoteOtherOffset = JSON.parse(JSON.stringify(c3Ref));
sameQuoteOtherOffset.start += 1; sameQuoteOtherOffset.end += 1;
const otherOffset = JSON.parse(JSON.stringify(c3Graph));
otherOffset.relations = [{ id: 'different-position', sourceRefs: [sameQuoteOtherOffset] }];
const otherLocator = readerWindow.citationLocatorForTest(sameQuoteOtherOffset);
const otherGroup = readerWindow.citationGroupsForTest(otherOffset, otherLocator);
check('identical quote text at another offset remains a separate citation identity',
  otherLocator !== c3RefId && !readerWindow.citationGroupsForTest(otherOffset, c3RefId).records.some(row => row.layer === 'relations'));
const ambiguousGraph = JSON.parse(JSON.stringify(c3Graph));
ambiguousGraph.events.push(JSON.parse(JSON.stringify(c3Event)));
const ambiguousGroup = readerWindow.citationGroupsForTest(ambiguousGraph, c3RefId);
check('duplicate stable event identity is retained as unknown, never a wrong record link',
  !ambiguousGroup.records.some(row => row.layer === 'events' && row.id === c3Event.id) && ambiguousGroup.unknownLayers.events === true);
const incomplete = Object.assign({}, c3Ref); delete incomplete.textHash;
check('incomplete source identity cannot create a citation group', readerWindow.citationLocatorForTest(incomplete) === null);
const wrongSpan = Object.assign({}, c3Ref, { end: c3Ref.end + 1 });
check('locator metadata with a mismatched codepoint quote length stays unknown', readerWindow.citationLocatorForTest(wrongSpan) === null);


const m88Hash = 'a'.repeat(64);
function m88Fixture() {
  const ref = (quote, start, verified) => ({ sourceId: 'm88-source', textHash: m88Hash, offsetUnit: 'codepoint', start, end: start + Array.from(quote).length, quote, verified, status: verified ? 'verified' : 'unverified', match: 'exact' });
  return { characters: [], relations: [], storylines: [], causeEdges: [], tasks: [], characterStates: [], narrativeUnits: [], reviewIssues: [],
    meta: { sources: [{ id: 'm88-source', textHash: m88Hash, path: 'm88.txt' }] },
    events: [{ id: 'm88-seed', title: '公开埋设事件', chapter: '第一章', order: 1, rawOrder: 1, rawOrderKnown: true },
      { id: 'm88-middle', title: '当前中间事件', chapter: '第二章', order: 2, rawOrder: 2, rawOrderKnown: true },
      { id: 'm88-future', title: '隐藏兑现事件', chapter: '第三章', order: 3, rawOrder: 3, rawOrderKnown: true }],
    clues: [{ id: 'm88-clue', name: '隐藏配对名称', summary: '隐藏摘要秘密', status: 'resolved', seedEventId: 'm88-seed', payoffEventId: 'm88-future', seedQuote: '公开埋设引句', payoffQuote: '隐藏兑现引句', claimVerified: false, semanticStatus: 'unreviewed',
      sourceRefs: [ref('公开埋设引句', 10, true), ref('隐藏兑现引句', 100, false)] }] };
}
const m88Book = m88Fixture(), m88Cursor = { eventIndex: 0, eventId: 'm88-seed', stopIndex: -1, stage: 'event', journey: null };
const m88Hidden = readerWindow.m88ReaderForTest(m88Book, m88Cursor, 'reading', 'm88-clue');
const futureStrings = ['隐藏兑现事件', '隐藏兑现引句', '隐藏配对名称', '隐藏摘要秘密', 'm88-future', '第三章'];
check('M88 hides future payoff title, quote, ID, chapter, mixed name and summary from the complete reader DOM',
  m88Hidden.visibility.seed && !m88Hidden.visibility.payoff && m88Hidden.html.includes('兑现尚未公开') && futureStrings.every(x => !m88Hidden.html.includes(x)));
check('M88 applies the same disclosure boundary to the existing causal payoff list',
  futureStrings.every(x => !m88Hidden.causal.includes(x)) && m88Hidden.causal.includes('兑现尚未公开'));
const m88Search = readerWindow.m88ReaderForTest(m88Book, m88Cursor, 'reading', null, '隐藏兑现引句');
check('M88 search cannot find a declaration through a hidden payoff quote', !m88Search.html.includes('sd-fore-card'));
const m88Public = readerWindow.m88ReaderForTest(m88Book, m88Cursor, 'published', 'm88-clue');
check('M88 explicit published scope shows both declared quotes while keeping semantic pairing pending',
  m88Public.visibility.payoff && m88Public.html.includes('公开埋设引句') && m88Public.html.includes('隐藏兑现引句') && m88Public.html.includes('配对待核') && !m88Public.html.includes('伏笔已证实'));
check('M88 seed and payoff keep separate source coordinates and independent location status',
  m88Public.seedRef.ref.start === 10 && m88Public.payoffRef.ref.start === 100 && m88Public.seedRef.label !== m88Public.payoffRef.label);
check('M88 published scope retains a way to follow the actual reading position', m88Public.html.includes('跟随阅读位置'));
const m88UnknownBook = m88Fixture(); m88UnknownBook.events.forEach(e => { e.rawOrderKnown = false; e.rawOrder = null; e.order += 100; });
const m88Unknown = readerWindow.m88ReaderForTest(m88UnknownBook, m88Cursor, 'reading', 'm88-clue');
check('M88 runtime display orders cannot disclose payoff when original order is unknown',
  m88Unknown.visibility.seed && !m88Unknown.visibility.payoff && !m88Unknown.html.includes('隐藏兑现引句'));
const m88JourneyCursor = { eventIndex: 1, eventId: 'm88-middle', stopIndex: 0, stage: 'event', journey: { id: 'm88-journey' }, stops: [{ key: 'event:m88-middle', eventIndex: 1 }, { key: 'event:m88-seed', eventIndex: 0 }, { key: 'terminal', eventIndex: 2 }] };
const m88Journey = readerWindow.m88ReaderForTest(m88Book, m88JourneyCursor, 'reading', null);
check('M88 journey scope uses reached stop membership rather than all earlier global orders', !m88Journey.html.includes('sd-fore-card') && !m88Journey.html.includes('公开埋设引句'));
const m88NoPayoffBook = m88Fixture(); delete m88NoPayoffBook.clues[0].payoffEventId; delete m88NoPayoffBook.clues[0].payoffQuote; m88NoPayoffBook.clues[0].status = 'pending';
const m88NoPayoff = readerWindow.m88ReaderForTest(m88NoPayoffBook, null, 'published', 'm88-clue');
check('M88 a seed-only declaration stays open without fabricating a payoff',
  !m88NoPayoff.visibility.payoff && /未提供兑现|尚未声明兑现|尚无兑现记录/.test(m88NoPayoff.html) && !m88NoPayoff.html.includes('隐藏兑现引句'));
const m88NoAnchorBook = m88Fixture(); m88NoAnchorBook.clues[0].sourceRefs = [];
const m88NoAnchor = readerWindow.m88ReaderForTest(m88NoAnchorBook, null, 'published', 'm88-clue');
check('M88 an unlocated but provided quote stays readable without a false source anchor',
  m88NoAnchor.html.includes('公开埋设引句') && m88NoAnchor.html.includes('隐藏兑现引句') && !m88NoAnchor.seedRef.ref && /定位待核|定位不完整/.test(m88NoAnchor.html));
const m88NoChaptersBook = m88Fixture(); m88NoChaptersBook.events.forEach(e => { delete e.chapter; });
const m88NoChapters = readerWindow.m88ReaderForTest(m88NoChaptersBook, null, 'published', 'm88-clue');
check('M88 unknown chapters leave parallel cards and do not invent a chapter-axis SVG',
  m88NoChapters.html.includes('公开埋设引句') && m88NoChapters.html.includes('隐藏兑现引句') && !/<svg[^>]+sd-echo-guide/.test(m88NoChapters.html));
const m88ConflictBook = m88Fixture(); m88ConflictBook.clues.push(JSON.parse(JSON.stringify(m88ConflictBook.clues[0])));
const m88Conflict = readerWindow.m88ReaderForTest(m88ConflictBook, null, 'published', null);
check('M88 conflicting owner identities cannot offer a misleading echo entry', !m88Conflict.html.includes('data-action="foreshadow-echo-open"'));
const m88ConflictAnchorBook = m88Fixture(); m88ConflictAnchorBook.clues[0].sourceRefs[0].verified = false;
const m88ConflictAnchor = readerWindow.m88ReaderForTest(m88ConflictAnchorBook, null, 'published', 'm88-clue');
check('M88 contradictory verified and status flags cannot certify a quote location', !m88ConflictAnchor.seedRef.label.includes('已核验'));
const m88BadSpanBook = m88Fixture(); m88BadSpanBook.clues[0].sourceRefs[0].end++;
const m88BadSpan = readerWindow.m88ReaderForTest(m88BadSpanBook, null, 'published', 'm88-clue');
check('M88 a wrong codepoint span stays readable as an unlocated quote without a source jump', !m88BadSpan.seedRef.ref && m88BadSpan.html.includes('公开埋设引句'));
const m88NegativeBook = m88Fixture(); m88NegativeBook.clues[0].sourceRefs[0].start = -1; m88NegativeBook.clues[0].sourceRefs[0].end = Array.from('公开埋设引句').length - 1;
const m88Negative = readerWindow.m88ReaderForTest(m88NegativeBook, null, 'published', 'm88-clue');
check('M88 negative source coordinates cannot be treated as end-relative text offsets', !m88Negative.seedRef.ref);
readerWindow.CLSky = null;

process.stdout.write('\n' + count + ' LUNA-DECON contract checks passed\n');
