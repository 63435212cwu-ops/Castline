'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

let count = 0;
function check(name, cond) {
  assert.ok(cond, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

function makeDom() {
  const registry = Object.create(null);
  function el(tag) {
    const n = {
      tagName: String(tag).toUpperCase(), children: [], _html: '', textContent: '',
      style: { setProperty() {}, removeProperty() {} }, dataset: {}, attributes: {},
      hidden: false, tabIndex: 0, className: '', innerHTML: '',
      setAttribute(k, v) { this.attributes[k] = String(v); },
      getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null; },
      removeAttribute(k) { delete this.attributes[k]; },
      appendChild(c) { this.children.push(c); return c; },
      insertBefore(c) { this.children.push(c); return c; },
      addEventListener() {}, removeEventListener() {}, focus() {}, blur() {}, click() {},
      scrollIntoView() {}, setSelectionRange() {}, contains() { return false; },
      querySelector() { return null; }, querySelectorAll() { return []; },
      remove() {}, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      getBoundingClientRect() { return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 }; },
      closest() { return null; }, matches() { return false; }, cloneNode() { return el(tag); }
    };
    return n;
  }
  const body = el('body');
  registry.skyDeconBody = el('div');
  registry.skyDeconMeta = el('div');
  registry.skyDeconTitle = el('h2');
  registry.skyDeconSub = el('p');
  registry.skyDecode = el('button');
  const doc = {
    body, documentElement: el('html'),
    createElement: el, createElementNS: (ns, t) => el(t),
    getElementById: id => registry[id] || null,
    querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; }
  };
  return { doc, body, registry };
}

function bootPanel(graph) {
  const dom = makeDom();
  const g = {
    document: dom.doc,
    matchMedia: q => ({ matches: false, media: String(q), addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
    addEventListener() {}, removeEventListener() {},
    setTimeout() { return 0; }, clearTimeout() {}, setInterval() { return 0; }, clearInterval() {},
    innerWidth: 1440, innerHeight: 900, devicePixelRatio: 1,
    requestAnimationFrame: () => 0, cancelAnimationFrame() {},
    performance: { now: () => 0 },
    getComputedStyle: () => ({ getPropertyValue: () => '', color: 'rgb(0,0,0)' }),
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    console
  };
  g.window = g;
  const ctx = vm.createContext(g);

  vm.runInContext(read('js/atlas/atlas-source.js'), ctx, { filename: 'atlas-source.js' });
  vm.runInContext(read('js/tree/storylines.js'), ctx, { filename: 'storylines.js' });
  vm.runInContext(read('js/sky/sky-model.js'), ctx, { filename: 'sky-model.js' });
  vm.runInContext(read('js/sky/sky-coverage.js'), ctx, { filename: 'sky-coverage.js' });
  vm.runInContext(read('js/sky/sky-deconstruction.js'), ctx, { filename: 'sky-deconstruction.js' });

  const normalized = ctx.CLAtlasSource.normalize(graph);
  const model = ctx.CLSkyModel.build(normalized, ctx.CLStory.analyze(normalized));
  g.CLApp = { graph: () => normalized };
  g.CLSky = { model: () => model, setPlot() {}, focusLine() {}, seekEventAt() {}, seek() {}, plot: () => false };
  g.CLSkyCoverage = ctx.CLSkyCoverage;

  const panel = ctx.CLSkyDeconstruction;
  panel.open();
  const root = dom.body.children.filter(c => c.id === 'skyDeconPanel')[0] ||
    dom.body.children[0] || { innerHTML: '' };
  const rootHtml = String(root.innerHTML || '');
  const footMatch = rootHtml.match(/<footer class="sd-foot">([\s\S]*?)<\/footer>/);
  return {
    panel, foot: footMatch ? footMatch[0] : '',
    footItems: footMatch ? (footMatch[1].match(/<span><i class="sd-key ([^"]*)"><\/i>([^<]*)<\/span>/g) || []) : [],
    render: mode => { panel.setMode(mode); return String(dom.registry.skyDeconBody.innerHTML || ''); }
  };
}

function loadFixture() {
  const cands = ['data/cache/9b676d7031b1bcd3b8377a18.json', 'data/sample-large.json', 'data/sample-saga.json'];
  for (const p of cands) {
    const abs = path.join(ROOT, p);
    if (fs.existsSync(abs)) return JSON.parse(fs.readFileSync(abs, 'utf8'));
  }
  return null;
}

const graph = loadFixture();
check('a fixture graph is available to render the real panel', !!graph);

const env = bootPanel(graph);

const overview = env.render('overview');
check('structure totals lead the review scope and match the loaded records',
  overview.indexOf('同一张图的组成') >= 0 && overview.indexOf('同一张图的组成') < overview.indexOf('审阅范围') &&
  overview.indexOf('>' + graph.characters.length + ' →<') >= 0 && overview.indexOf('>' + graph.events.length + ' →<') >= 0);
check('story route summary keeps source-marked, synthesized, derived and automatic counts distinct',
  /来源标记主线/.test(overview) && /模型综合/.test(overview) && /其他推导/.test(overview) && /自动分段/.test(overview) && /来源未明确/.test(overview));
check('structure links remain on the existing six reader paths',
  (overview.match(/data-action="structure-nav"/g) || []).length === 8 &&
  ['people', 'groups', 'relations', 'events', 'chapters', 'units', 'lines', 'clues'].every(k => overview.indexOf('data-structure-nav="' + k + '"') >= 0));

check('the resident footer legend renders at all', env.foot.length > 0 && env.footItems.length >= 4);

const legendText = env.footItems.map(s => String(s).replace(/<[^>]+>/g, '|')).join(' ');
check('the legend still declares the four evidence states (已核验 / 未核验 / 归纳 / 推导)',
  ['原文已核验', '有引文未核验', '归纳', '推导'].every(t => env.foot.indexOf(t) >= 0));

check('the legend declares the causal-role hues, so violet is no longer the only explanation offered',
  env.foot.indexOf('因果 · 前因') >= 0 && env.foot.indexOf('因果 · 后果') >= 0);

check('the legend declares the broken-reference state as its own entry',
  env.foot.indexOf('引用断裂') >= 0);

check('the legend ties the dashed swatch to the availability meaning it actually encodes',
  /is-unknown"><\/i>有引文未核验（虚线边框）/.test(env.foot));

const causalHtml = env.render('causal');
if (causalHtml.length) {
  check('the causal page paints 前因 with the dedicated is-cause-src class',
    causalHtml.indexOf('is-cause-src') >= 0);
  check('the causal page no longer paints nodes with the reused is-source / is-target classes',
    !/class="sd-causal-node is-source/.test(causalHtml) && !/class="sd-causal-node is-target/.test(causalHtml));
} else {
  check('the causal page must render content or an explicit empty state', false);
}

const linesHtml = env.render('lines');
if (linesHtml.length) {
  check('the storyline page still distinguishes main from branch structurally',
    linesHtml.indexOf('is-main') >= 0 || linesHtml.indexOf('is-branch') >= 0);
} else {
  check('the storyline page must render content or an explicit empty state', false);
}

const evidenceHtml = env.render('evidence');
if (evidenceHtml.length) {
  check('the evidence page still uses the evidence-state classes',
    /is-(source|summary|derived|unknown)/.test(evidenceHtml));
} else {
  check('the evidence page must render content or an explicit empty state', false);
}

const foreHtml = env.render('foreshadow');
if (foreHtml.length) {
  const hasBadges = /sd-fore-stage is-/.test(foreHtml);
  const honestEmpty = /sd-empty/.test(foreHtml) &&
    /没有声明不代表全书不存在伏笔|尚未提供伏笔层/.test(foreHtml);
  check('the foreshadow page either renders stage badges or states an honest empty result',
    hasBadges || honestEmpty);
  process.stdout.write('     foreshadow page: ' + (hasBadges ? 'stage badges present' : 'honest empty state') + '\n');
} else {
  check('the foreshadow page must render content or an explicit empty state', false);
}

const hud = read('css/sky-deep-hud.css');
const dashedOwners = (hud.match(/[^{}]*\{[^}]*border-style:\s*dashed[^}]*\}/g) || [])
  .map(r => r.split('{')[0].trim());
check('every dashed-border rule in the panel belongs to the availability family alone',
  dashedOwners.length > 0 && dashedOwners.every(sel => /sd-key\.is-unknown/.test(sel)));
process.stdout.write('     dashed owners: ' + JSON.stringify(dashedOwners) + '\n');

const keys = env.footItems.map(s => (String(s).match(/sd-key ([a-z- ]+?)"/) || [])[1]).filter(Boolean);
check('every legend swatch resolves to a declared .sd-key rule or the base swatch',
  keys.every(k => {
    const cls = k.trim().split(/\s+/).pop();
    return cls === 'sd-key' || hud.indexOf('.' + cls + ' {') >= 0 || new RegExp('\\.' + cls + '\\s*\\{').test(hud);
  }));
process.stdout.write('     legend swatches: ' + JSON.stringify(keys) + '\n');

process.stdout.write('\n' + count + ' legend-parity contracts passed\n');
