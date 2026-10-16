'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const Source = require('../../js/atlas/atlas-source.js');

function makeDom() {
  const nodes = [];
  function el(tag) {
    const n = {
      tagName: tag, _html: '', children: [], attributes: {}, style: { setProperty() {}, removeProperty() {} },
      className: '', hidden: false, id: '', textContent: '', disabled: false,
      set innerHTML(v) { this._html = String(v); }, get innerHTML() { return this._html; },
      setAttribute(k, v) { this.attributes[k] = String(v); }, getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; },
      removeAttribute(k) { delete this.attributes[k]; }, hasAttribute(k) { return k in this.attributes; },
      appendChild(c) { this.children.push(c); if (c && c.id) registry[c.id] = c; return c; },
      removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; },
      insertBefore(c) { this.children.unshift(c); return c; },
      addEventListener() {}, removeEventListener() {}, focus() {}, blur() {}, click() {},
      scrollIntoView() {}, setSelectionRange() {}, contains() { return false; },
      querySelector() { return null; }, querySelectorAll() { return []; },
      remove() {}, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      getBoundingClientRect() { return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 }; },
      closest() { return null; }, matches() { return false; }, cloneNode() { return el(tag); }
    };
    nodes.push(n);
    return n;
  }
  const registry = Object.create(null);
  const body = el('body');
  registry['skyDeconBody'] = el('div');
  registry['skyDeconMeta'] = el('div');
  registry['skyDeconTitle'] = el('h2');
  registry['skyDeconSub'] = el('p');
  registry['skyDecode'] = el('button');

  const doc = {
    body,
    documentElement: el('html'),
    createElement: el,
    createElementNS: (ns, t) => el(t),
    getElementById: id => registry[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
    dispatchEvent() { return true; }
  };
  return { doc, body, registry, el };
}

function bootPanel(graph, opts) {
  const o = opts || {};
  const dom = makeDom();
  const g = {
    document: dom.doc,
    matchMedia: q => ({ matches: o.reducedMotion === true && /prefers-reduced-motion/.test(String(q)),
      media: String(q), addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
    addEventListener() {}, removeEventListener() {},
    setTimeout(fn) { return 0; }, clearTimeout() {}, setInterval() { return 0; }, clearInterval() {},
    innerWidth: 1440, innerHeight: 900, devicePixelRatio: 1,
    requestAnimationFrame: fn => 0, cancelAnimationFrame() {},
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
  return {
    panel: panel, doc: dom.doc, body: dom.registry.skyDeconBody, meta: dom.registry.skyDeconMeta,
    model: model, graph: normalized,
    render(mode) { panel.setMode(mode); return dom.registry.skyDeconBody.innerHTML; }
  };
}

const BOOKS = {
  dafeng: 'data/cache/9b676d7031b1bcd3b8377a18.json',
  xiyou: 'data/cache/df959d743e53206f56db2f92.json',
  sanguo: 'data/cache/152e2a6eed94f1075e7e7070.json'
};
const SAMPLES = {
  'sample-saga': 'data/sample-saga.json',
  'sample-large': 'data/sample-large.json',
  'sample-focus': 'data/sample-focus.json',
  'sample-mid': 'data/sample-mid.json'
};

function loadJson(p) { return JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8')); }

function emptyGraph() { return { title: '空样本', characters: [], events: [], relations: [], storylines: [], camps: [], meta: { schema: 'castline/3' } }; }

function sparseGraph() {
  return {
    title: '稀疏样本', meta: { schema: 'castline/3' },
    characters: [{ id: 'ch_1', name: '甲', role: '主角', importance: 90 }],
    events: [{ id: 'ev_1', order: 1, chapter: '第一章', title: '出发', kind: '日常', characters: ['甲'], summary: '甲出发。' }],
    relations: [], storylines: [], camps: []
  };
}

function longTitleGraph() {
  const LONG = '这是一个极其漫长的标题'.repeat(6);
  return {
    title: '长标题样本', meta: { schema: 'castline/3' },
    characters: [{ id: 'ch_1', name: '非常非常长的角色名字'.repeat(3), role: '主角', importance: 80 }],
    events: [{ id: 'ev_1', order: 1, chapter: '第一章', title: LONG, kind: '转折', characters: ['非常非常长的角色名字'.repeat(3)], summary: LONG }],
    storylines: [{ id: 'sl_1', name: LONG, kind: '主线', events: [1], lead: '非常非常长的角色名字'.repeat(3) }],
    relations: [], camps: []
  };
}

function noEvidenceGraph() {
  return {
    title: '缺证据样本', meta: { schema: 'castline/3' },
    characters: [{ id: 'ch_1', name: '甲', role: '主角', importance: 70 }],
    events: [
      { id: 'ev_1', order: 1, chapter: '第一章', title: '无引句事件', kind: '日常', characters: ['甲'] },
      { id: 'ev_2', order: 2, chapter: '第二章', title: '有引句未核验', kind: '转折', characters: ['甲'], quote: '原文片段。' }
    ],
    relations: [], storylines: [], camps: []
  };
}

function brokenRefGraph() {
  return {
    title: '错误引用样本', meta: { schema: 'castline/3' },
    characters: [{ id: 'ch_1', name: '甲', role: '主角', importance: 70 }],
    events: [
      { id: 'ev_1', order: 1, chapter: '第一章', title: '起点', kind: '日常', characters: ['甲'], quote: '起点句。' },
      { id: 'ev_2', order: 2, chapter: '第二章', title: '终点', kind: '转折', characters: ['甲'], quote: '终点句。' }
    ],
    causeEdges: [
      { id: 'c_1', fromEventId: 'ev_does_not_exist', toEventId: 'ev_2', basis: 'explicit', description: '前因缺失', quote: '起点句。' },
      { id: 'c_2', fromEventId: 'ev_1', toEventId: 'ev_1', basis: 'inference', description: '自引用', quote: '起点句。' }
    ],
    clues: [{ id: 'cl_1', name: '悬空伏笔', seedQuote: '起点句。', payoffEventId: 'ev_missing', seedEventId: 'ev_1' }],
    relations: [], storylines: [], camps: []
  };
}

const HONEST_EMPTY = /sd-empty|暂无|尚未|未提供|待核|未命名|没有匹配|不能从节点数量|未声明不代表|不表示/;

function stripChrome(html) {
  return html
    .replace(/<footer class="sd-foot">[\s\S]*?<\/footer>/g, '')
    .replace(/<div class="sd-evidence-summary"[\s\S]*?<\/div>\s*<\/section>/g, '')
    .replace(/<div class="sd-evidence-counts">[\s\S]*?<\/div>/g, '')
    .replace(/<select[\s\S]*?<\/select>/g, '')
    .replace(/<option[^>]*>[^<]*<\/option>/g, '');
}

function scanFabrication(html, kind, graph) {
  const body = stripChrome(html);
  const hits = [];
  const events = (graph && graph.events) || [];
  const anyVerified = events.some(e => {
    const st = Source.evidenceStatus ? Source.evidenceStatus(e) : null;
    return st && (st.code === 'source' || st.verified === true || st.anchored === true);
  });
  if (!anyVerified && kind !== 'dense' && kind !== 'sample') {
    const claim = body.match(/>(?:[^<]*?)原文已核验/g);
    if (claim) hits.push('输入无已核验引文，但记录本体出现「原文已核验」×' + claim.length);
  }
  return hits;
}

function classTokens(html) {
  const out = [];
  const re = /class="([^"]*)"/g;
  let m;
  while ((m = re.exec(html))) out.push(m[1].split(/\s+/).filter(Boolean));
  return out;
}
function countRows(html) {
  const toks = classTokens(html);
  const has = t => toks.filter(list => list.indexOf(t) >= 0).length;
  return {
    sdEvent: has('sd-event'),
    sdLine: has('sd-line'),
    sdPerson: has('sd-person'),
    sdEmpty: has('sd-empty'),
    sdCausalNode: has('sd-causal-node'),
    sdPaginated: /class="sd-pagination/.test(html) || toks.some(l => l.indexOf('sd-pagination') >= 0)
  };
}

const MODES = ['overview', 'lines', 'people', 'evidence', 'mechanics', 'causal', 'foreshadow', 'states'];

function run() {
  const cases = [];
  const longTitleInDetail = new Set();
  function probe(label, kind, graphFactory, mode, assertFn) {
    let panel = null, html = '', err = null;
    try {
      panel = bootPanel(graphFactory());
      html = panel.render(mode);
    } catch (e) { err = String(e && e.message || e); }
    const rec = {
      case: label, kind, mode, ok: !err, error: err,
      htmlLength: html.length,
      counts: err ? null : countRows(html),
      isEmptyState: err ? null : /sd-empty/.test(html),
      hasHonestFallbackText: err ? null : HONEST_EMPTY.test(html),
      fabricationHits: err ? [] : scanFabrication(html, kind, graphFactory()),
      graphCounts: null
    };
    const gg = err ? null : panel.graph;
    if (gg) rec.graphCounts = { characters: (gg.characters || []).length, events: (gg.events || []).length, storylines: (gg.storylines || []).length };
    if (assertFn && !err) {
      try { assertFn(html, panel, rec); rec.assertion = 'pass'; }
      catch (e) { rec.assertion = 'FAIL: ' + (e && e.message || e); }
    }
    cases.push(rec);
    return rec;
  }

  MODES.forEach(mode => {
    probe('empty/' + mode, 'empty', emptyGraph, mode, (html, p) => {
      if (mode !== 'overview' && mode !== 'states' && !/sd-empty|暂无|尚未|未提供|未命名/.test(html)) {
        throw new Error('空输入在 ' + mode + ' 下没有任何空态文案');
      }
    });
  });

  MODES.forEach(mode => {
    probe('sparse/' + mode, 'sparse', sparseGraph, mode, null);
  });

  Object.keys(BOOKS).forEach(key => {
    MODES.forEach(mode => {
      probe('dense/' + key + '/' + mode, 'dense', () => loadJson(BOOKS[key]), mode, (html, p, rec) => {
        if (mode === 'evidence') {
          const rows = rec.counts.sdEvent;
          const events = rec.graphCounts.events;
          if (events > 24 && rows > 24) throw new Error('事件层未分页：单页 ' + rows + ' 条（PAGE_SIZE 应为 24）');
          if (events > 24 && !rec.counts.sdPaginated) throw new Error('密集输入缺少分页控件');
        }
        if (mode === 'people') {
          const rows = rec.counts.sdPerson;
          if (rec.graphCounts.characters > 24 && rows > 24) throw new Error('人物表未分页：单页 ' + rows + ' 条');
          if (rec.graphCounts.characters > 24 && !rec.counts.sdPaginated) throw new Error('人物表缺少分页控件');
        }
      });
    });
  });

  Object.keys(SAMPLES).forEach(key => {
    MODES.forEach(mode => {
      probe('sample/' + key + '/' + mode, 'sample', () => loadJson(SAMPLES[key]), mode, null);
    });
  });

  MODES.forEach(mode => {
    probe('long-title/' + mode, 'long-title', longTitleGraph, mode, (html) => {
      const rows = html.match(/<span class="sd-event-copy"><b>([^<]*)<\/b>/g) || [];
      rows.forEach(r => {
        const text = r.replace(/^.*<b>/, '').replace(/<\/b>$/, '');
        if (text.length > 40) throw new Error('列表行标题未截断：' + text.length + ' 字（clip 上限 34 + 省略号）');
      });
      const lineNames = html.match(/<span class="sd-line-name">([^<]*)<\/span>/g) || [];
      lineNames.forEach(r => {
        const text = r.replace(/^.*">/, '').replace(/<\/span>$/, '');
        if (text.length > 20) throw new Error('故事线名未截断：' + text.length + ' 字（clip 上限 16 + 省略号）');
      });
      const detail = html.match(/<div class="sd-detail-top"><b>([^<]*)<\/b>/g) || [];
      detail.forEach(d => {
        const text = d.replace(/^.*<b>/, '');
        if (text.length > 40) longTitleInDetail.add(mode);
      });
    });
  });

  MODES.forEach(mode => {
    probe('no-evidence/' + mode, 'no-evidence', noEvidenceGraph, mode, (html, p, rec) => {
      if (mode === 'evidence') {
        if (!/未提供原文引句|未提供引句/.test(html)) throw new Error('缺证据事件没有明确提示未提供引句');
      }
    });
  });

  MODES.forEach(mode => {
    probe('broken-ref/' + mode, 'broken-ref', brokenRefGraph, mode, (html, p, rec) => {
      if (mode === 'causal') {
        if (!/引用待核|未解析|引用缺失|未提供|不唯一|未自动补配/.test(html)) {
          throw new Error('错误引用在因果网络里没有降级说明');
        }
      }
    });
  });

  cases.longTitleInDetail = longTitleInDetail;
  return cases;
}

function summarize(cases) {
  const kinds = Array.from(new Set(cases.map(c => c.kind)));
  const rows = kinds.map(kind => {
    const cs = cases.filter(c => c.kind === kind);
    return {
      kind,
      cases: cs.length,
      crashed: cs.filter(c => !c.ok).length,
      assertionFailures: cs.filter(c => c.assertion && String(c.assertion).startsWith('FAIL')).length,
      withEmptyState: cs.filter(c => c.isEmptyState).length,
      withHonestFallback: cs.filter(c => c.hasHonestFallbackText).length,
      fabricationHits: cs.reduce((n, c) => n + (c.fabricationHits || []).length, 0),
      exampleErrors: cs.filter(c => !c.ok).slice(0, 3).map(c => c.case + ': ' + c.error)
    };
  });
  return {
    kinds: rows,
    totalCases: cases.length,
    totalCrashes: cases.filter(c => !c.ok).length,
    totalAssertionFailures: cases.filter(c => c.assertion && String(c.assertion).startsWith('FAIL')).length,
    totalFabricationHits: cases.reduce((n, c) => n + (c.fabricationHits || []).length, 0)
  };
}

function main() {
  const args = process.argv.slice(2);
  let out = null;
  for (let i = 0; i < args.length; i++) if (args[i] === '--json') out = args[++i];

  const cases = run();
  const summary = summarize(cases);
  const longTitleFullText = cases.longTitleInDetail || new Set();
  const report = {
    schema: 'castline/degradation-matrix/1',
    generatedBy: 'tools/plan100/degradation_matrix.js',
    generatedAt: new Date().toISOString(),
    method: '用最小 DOM 垫片在 Node 里加载真实的 js/sky/sky-deconstruction.js，读回模块自己写出的 innerHTML',
    evidenceKind: 'DOM 序列化（非像素）',
    browserEvidencePending: '像素/截图证据需串行浏览器执行（计划禁止并发 GPU）',
    modes: MODES,
    summary,
    longTitleFullTextModes: Array.from(longTitleFullText),
    cases
  };
  if (out) fs.writeFileSync(path.join(ROOT, out), JSON.stringify(report, null, 2));

  console.log('降级矩阵：' + summary.totalCases + ' 个用例 · 崩溃 ' + summary.totalCrashes +
    ' · 断言失败 ' + summary.totalAssertionFailures + ' · 编造命中 ' + summary.totalFabricationHits);
  console.log('');
  console.log('kind            用例  崩溃  断言失败  有空态  有诚实文案  编造');
  summary.kinds.forEach(k => {
    console.log(k.kind.padEnd(15) + String(k.cases).padStart(4) + String(k.crashed).padStart(6) +
      String(k.assertionFailures).padStart(10) + String(k.withEmptyState).padStart(8) +
      String(k.withHonestFallback).padStart(12) + String(k.fabricationHits).padStart(6));
  });
  const bad = cases.filter(c => !c.ok || (c.assertion && String(c.assertion).startsWith('FAIL')));
  if (bad.length) {
    console.log('\n失败用例：');
    bad.forEach(c => console.log('  ' + c.case + ' → ' + (c.error || c.assertion)));
  }
  return report;
}

if (require.main === module) main();
module.exports = { bootPanel, run, summarize, MODES };
