(function () {
  'use strict';
  var api;
  if (typeof require === 'function') {
    api = require('../js/core/boot-errors.js');
  } else {
    api = Function(read('js/core/boot-errors.js') + '\nreturn (typeof window!=="undefined"?window:globalThis).CLBootErrors;')();
  }
  var count = 0;
  function ok(value, label) {
    if (!value) throw new Error('FAIL ' + label);
    count++;
  }
  function leaks(text, label) {
    ok(typeof text === 'string' && text.length > 0, label + ' has user-facing copy');
    ok(!/\.js:\d/.test(text), label + ' copy never leaks a JS frame');
    ok(!/\/Users\//.test(text) && !/[A-Za-z]:\\/.test(text), label + ' copy never leaks an absolute path');
    ok(!/\n\s*at\s/.test(text), label + ' copy never leaks a stack trace');
  }

  var network = [
    { kind: 'http', status: 404, src: 'data/cache/abc.json' },
    { kind: 'http', status: 500, src: 'data/cache/abc.json' },
    { kind: 'net', src: 'data/cache/abc.json' },
    { kind: 'slow', src: 'data/cache/abc.json' }
  ];
  var data = [
    { kind: 'json', message: '数据文件不是图谱：内容无法按 JSON 读取', src: 'data/cache/abc.json' },
    { kind: 'shape', message: '数据文件不是图谱：里面没有角色列表', src: 'data/cache/abc.json' },
    { kind: 'mount', message: '图谱数据无法展开：Error: bad node\n  at build (/Users/u/星系/js/app.js:123:4)', src: 'data/cache/abc.json' }
  ];
  network.forEach(function (raw, i) {
    var c = api.classify(raw);
    ok(c.category === 'network' && c.retryable === true, 'network kind #' + i + ' classified retryable');
    leaks(api.why(raw), 'network #' + i);
    leaks(api.detail(raw), 'network detail #' + i);
    ok(api.detail(raw).indexOf('data/cache/abc.json') >= 0, 'network detail #' + i + ' keeps the address');
  });
  data.forEach(function (raw, i) {
    var c = api.classify(raw);
    ok(c.category === 'data' && c.retryable === false, 'data kind #' + i + ' classified non-retryable');
    leaks(api.why(raw), 'data #' + i);
    ok(api.detail(raw).indexOf('原始信息') >= 0, 'data detail #' + i + ' keeps the raw diagnostic');
  });
  ok(api.classify({ kind: 'mount' }).retryable === false, 'mount failure is data, retry is not presented as a fix');
  ok(api.why({ kind: 'http', status: 404 }).indexOf('找不到') >= 0, '404 copy names the missing file');
  ok(/损坏|不完整/.test(api.why({ kind: 'json' })), 'corrupt JSON copy says corrupted, not "no data"');
  ok(api.why({ kind: 'json' }).indexOf('没有数据」是两回事') >= 0, 'corrupt copy explicitly separates corruption from absence');
  ok(api.why({ kind: 'slow' }).indexOf('15') >= 0, 'slow copy states the timeout');

  [null, undefined, {}, { kind: '??' }, { kind: 'json_x' }, 'net', 7].forEach(function (raw, i) {
    var c = api.classify(raw);
    ok(c.kind === 'unknown' && c.category === 'unknown' && c.retryable === false, 'unknown input #' + i + ' falls into the honest unknown bucket');
    leaks(api.why(raw), 'unknown ' + i);
  });
  ok(api.kinds.length === 7 && api.kinds.indexOf('slow') >= 0, 'kind catalogue is explicit');
  ok(api.slowInfo('data/x.json').kind === 'slow', 'slowInfo produces a structured slow error');
  ok(api.retryable({ kind: 'net' }) === true && api.retryable({ kind: 'json' }) === false, 'retryable() shortcut follows the same categories');
  ok(api.SLOW_MS === 15000, 'slow gate constant is published');

  var mount = { kind: 'mount', message: '图谱数据无法展开：TypeError: x is not a function', src: 'data/cache/abc.json' };
  ok(api.why(mount).indexOf('TypeError') < 0, 'friendly copy never embeds the raw exception');
  ok(api.detail(mount).indexOf('TypeError') >= 0, 'expandable detail keeps the raw exception');

  var line = 'boot_errors_contract OK · ' + count + ' checks';
  if (typeof process !== 'undefined' && process.stdout) process.stdout.write(line + '\n');
  else if (typeof print === 'function') print(line);
})();


if (typeof require === 'function') (async function () {
  'use strict';
  const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
  const file = process.env.CL_TEST_APP_FILE || path.join(__dirname, '..', 'js', 'app.js');
  const source = fs.readFileSync(file, 'utf8');
  let checks = 0;
  function section(start, end) {
    const at = source.indexOf(start), stop = source.indexOf(end, at);
    assert.ok(at >= 0 && stop > at, 'production function boundary: ' + start);
    return source.slice(at, stop);
  }
  const original = section('  function readMark(', '  function libCard(') + section('  function loadHistory()', '  function sortedHist()') + section("  $('libSweep').addEventListener", '  function histPost(') + section('  function histPost(', '  function loadDocsFromHistory(')
    + section('  function histAction(', '  function bindHistClicks(')
    + section('  function loadStage(', '  // ---------------------------------------------------------------- v30')
    + section('  function bootFail(', '  /* v91');
  const api = 'var versionApi = {' + section('    mountRevision: function', '    sourceDocuments: function') + section('    sourceDocuments: function', '    title: function') + '};';
  const micro = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
  function check(label, fn) { fn(); checks++; console.log('PASS ' + label); }
  function harness() {
    const requests = [], timers = [], mounts = [], events = [], urls = [], provenance = [], downloads = [], notices = [];
    const nodes = Object.create(null);
    const flags = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
    function node(id) { return nodes[id] || (nodes[id] = { textContent: '', firstChild: { textContent: '' }, classList: flags, title: '', listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; } }); }
    const origin = { title: 'origin', key: '11111111', characters: [], events: [], meta: {} };
    let failNextMount = false;
    const sky = { curtainWait() { return 0; }, enabled() { return true; } };
    const ctx = {
      historyListSerial: 0, G: origin, GKey: '11111111', GSrc: { from: 'library', key: '11111111' },
      histItems: [{ key: 'aaaaaaaa', title: 'A' }, { key: 'bbbbbbbb', title: 'B' }],
      fetch(url, options) { return new Promise((resolve, reject) => requests.push({ url, options, resolve, reject, replied: false })); },
      AbortController, Blob, URL,
      CustomEvent: function (type, init) { this.type = type; this.detail = init.detail; },
      document: { body: { classList: flags }, dispatchEvent(e) { const event = { type: e.type, detail: e.detail }; events.push(event); if (ctx.onEvent) ctx.onEvent(event); },
        createElement() { return { click() { downloads.push({ name: this.download, url: this.href }); } }; } },
      window: { CLSky: sky }, CLSky: sky,
      setTimeout(fn) { timers.push(fn); return timers.length; }, requestAnimationFrame(fn) { timers.push(fn); },
      history: { replaceState(a, b, url) { urls.push(url); ctx.location.href = url; } },
      location: { href: 'http://127.0.0.1:8781/?data=data/cache/11111111.json', search: '', origin: 'http://127.0.0.1:8781' },
      qs: { get() { return null; } }, esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }, err: { textContent: '' }, $: node, NC: { FIELD: 'field' },
      normalizeGraph(graph) { mounts.push({ graph: graph.title, key: ctx.GKey }); return Object.assign({}, graph, { meta: Object.assign({}, graph.meta) }); },
      indexGraph() {}, syncSafeArea() {}, mountScene() { if (failNextMount) { failNextMount = false; throw new Error('controlled scene failure'); } },
      scene: { stats() { return { chapters: 1, fibers: 0 }; }, lod() {} },
      renderProvenance(it) { provenance.push({ requested: it && it.key, graph: ctx.G.title, key: ctx.GKey }); },
      toast(text) { notices.push(text); }, console: { warn() {} }, fail() {}, sessionStorage: { getItem() {}, setItem() {} }
    };
    ['closeLib','showLoader','renderLib','renderHistory','loadHistory','buildTimeline','renderTimeline',
      'plotAnalyze','renderRoleChips','renderCampChips','renderIndex','closeDock','crumb','labelExtras','renderOverview','syncViewbar','warm'].forEach(k => { ctx[k] = function () {}; });
    ctx.URL = class extends URL {};
    ctx.URL.createObjectURL = () => 'blob:contract'; ctx.URL.revokeObjectURL = () => {};
    vm.createContext(ctx); vm.runInContext(original + api, ctx);
    async function reply(key, opts) {
      const request = requests.find(r => !r.replied && r.url === (opts && opts.url || 'data/cache/' + key + '.json'));
      assert.ok(request, 'pending graph request ' + key); request.replied = true;
      opts = opts || {};
      request.resolve({ ok: opts.status == null || opts.status === 200, status: opts.status || 200,
        text: () => Promise.resolve(opts.text == null ? JSON.stringify({ title: key, key, characters: [], events: [], meta: {} }) : opts.text),
        blob: () => Promise.resolve(new Blob(['404 HTML'], { type: 'text/html' })) });
      await micro();
    }
    async function runTimers() { while (timers.length) { timers.shift()(); await micro(); } }
    async function historyReply(i, items) {
      const request = requests.filter(r => r.url === '/api/history')[i];
      assert.ok(request, 'pending history update ' + i); request.replied = true;
      request.resolve({ ok: true, json: () => Promise.resolve({ items }) }); await micro();
    }
    return { ctx, requests, timers, mounts, events, urls, provenance, downloads, notices, origin, reply, runTimers, historyReply,
      sweep() { nodes.libSweep.listeners.click(); }, failMount() { failNextMount = true; } };
  }
  const A = 'aaaaaaaa', B = 'bbbbbbbb';
  {
    const h = harness(), a = h.ctx.versionApi.openVersion(A), b = h.ctx.versionApi.openVersion(B);
    await h.reply(B); await h.runTimers(); await b;
    await h.reply(A); await h.runTimers(); await a;
    check('last requested work owns the graph and URL despite late earlier response', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.ctx.G.title, B);
      assert.equal(h.mounts.length, 1); assert.ok(h.urls.length >= 1); assert.ok(h.urls.every(url => url.includes(B)));
      assert.equal(h.requests[0].options.signal.aborted, true);
    });
  }
  {
    const h = harness(), a = h.ctx.openHistory(A); await h.reply(A);
    check('delayed mount leaves current graph key and source together until commit', () => {
      assert.equal(h.ctx.G, h.origin); assert.equal(h.ctx.GKey, '11111111'); assert.equal(h.ctx.GSrc.key, '11111111');
    });
    const b = h.ctx.openHistory(B); await h.reply(B); await h.runTimers(); await Promise.all([a, b]);
    check('queued earlier mount cannot bind earlier graph to the newer key', () => {
      assert.equal(h.mounts.length, 1); assert.equal(h.mounts[0].key, B); assert.equal(h.mounts[0].graph, B);
    });
  }
  {
    const h = harness(), a = h.ctx.histAction(A), b = h.ctx.histAction(B);
    await h.reply(B); await h.runTimers(); await b; await h.reply(A, { status: 404 }); await a;
    check('obsolete open failure cannot overwrite successful new work error state', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.ctx.err.textContent, '');
      assert.equal(h.events.filter(e => e.type === 'cl:work-open-error' || e.detail && e.detail.stage === 'error').length, 0);
    });
  }
  {
    const h = harness(), a = h.ctx.openHistory(A); await h.reply(A); await h.runTimers(); await a;
    const b = h.ctx.openHistory(B); await h.reply(B); await h.runTimers(); await b;
    await h.historyReply(1, [{ key: A, opens: 1 }, { key: B, opens: 1 }]);
    await h.historyReply(0, [{ key: A, opens: 1 }, { key: B, opens: 0 }]);
    check('late earlier history response cannot reset new history counts or provenance', () => {
      assert.equal(h.ctx.histItems.find(it => it.key === B).opens, 1);
      assert.equal(h.provenance.some(it => it.requested === A && it.key === B), false);
    });
  }
  {
    const h = harness(), a = h.ctx.bootData('data/cache/' + A + '.json'), b = h.ctx.openHistory(B);
    await h.reply(B); await h.runTimers(); await b; await h.reply(A); await h.runTimers(); await a;
    check('URL boot and library opening share ownership of the current work', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.mounts.length, 1);
    });
  }
  {
    const h = harness(), a = h.ctx.bootData('data/cache/' + A + '.json'), b = h.ctx.openHistory(B);
    await h.reply(B); await h.runTimers(); await b; await h.reply(A, { status: 404 }); await a;
    check('obsolete URL boot failure cannot replace the new work with an error screen', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.ctx.window.CLLoadError, null);
      assert.equal(h.events.filter(e => e.type === 'cl:graph-error').length, 0);
    });
  }
  {
    const h = harness(), a = h.ctx.openHistory(A); await h.reply(A);
    h.ctx.mount({ title: 'direct', characters: [], events: [], meta: {} });
    await h.runTimers(); await a;
    check('direct production mount invalidates previously scheduled work requests', () => {
      assert.equal(h.ctx.G.title, 'direct'); assert.equal(h.mounts.length, 1);
      assert.equal(h.ctx.window.CLLoadStage, null);
      assert.equal(h.events.filter(e => e.type === 'cl:graph-loading' && e.detail.stage === 'analyze').at(-1).detail.title, 'direct');
    });
  }
  {
    const h = harness(); h.failMount();
    const failed = h.ctx.openHistory(A).catch(e => e); await h.reply(A); await h.runTimers(); const error = await failed;
    check('mount failure restores graph key and source as one previous-work state', () => {
      assert.equal(error.clKind, 'mount'); assert.equal(h.ctx.GKey, '11111111'); assert.equal(h.ctx.GSrc.key, '11111111');
      assert.equal(h.ctx.G.title, 'origin'); assert.equal(h.ctx.G.meta.graph_key, '11111111');
    });
  }
  {
    const h = harness(), revision = h.ctx.versionApi.mountRevision({ title: A, characters: [], events: [], meta: {} }, A, '11111111');
    const newer = h.ctx.openHistory(B); await h.reply(B); await h.runTimers(); await Promise.all([revision, newer]);
    check('obsolete revision cannot mount or update URL after a newer work selection', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.mounts.length, 1); assert.equal(h.urls.some(url => url.includes(A)), false);
    });
  }
  {
    const h = harness(); h.failMount();
    const failure = h.ctx.versionApi.mountRevision({ title: A, characters: [], events: [], meta: {} }, A, '11111111').catch(e => e);
    await h.runTimers(); await failure;
    check('revision mount failure uses the same graph-and-key rollback', () => {
      assert.equal(h.ctx.GKey, '11111111'); assert.equal(h.ctx.G.title, 'origin'); assert.equal(h.urls.length, 0);
    });
  }
  for (const failure of [{ status: 404 }, { status: 200, text: '{broken' }, { status: 200, text: '{"events":[]}' }]) {
    const h = harness(), result = h.ctx.histAction(A, 'export'); await h.reply(A, failure); await result;
    check('invalid library export creates no mislabeled graph download ' + JSON.stringify(failure), () => {
      assert.equal(h.downloads.length, 0); assert.equal(h.notices.length, 1);
    });
  }
  {
    const h = harness(), result = h.ctx.histAction(A, 'export'); await h.reply(A); await result;
    check('valid library export keeps the existing graph JSON download', () => {
      assert.equal(h.downloads.length, 1); assert.equal(h.downloads[0].name, 'A.castline.json'); assert.equal(h.notices.length, 0);
    });
  }

  for (const row of [
    { src: 'data/sample-saga.json?label=aaaaaaaa.json', key: null },
    { src: 'http://other.invalid/data/cache/aaaaaaaa.json', key: null },
    { src: 'data/cache/aaaaaaaa.json?label=bbbbbbbb.json#detail', key: A },
    { src: 'http://127.0.0.1:8781/data/cache/aaaaaaaa.json', key: A }
  ]) {
    const h = harness(), result = h.ctx.bootData(row.src); await h.reply(A, { url: row.src }); await h.runTimers(); await result;
    check('URL boot binds only the same-origin actual cache pathname ' + row.src, () => {
      assert.equal(h.ctx.GKey, row.key); assert.equal(h.ctx.GSrc.key, row.key);
    });
  }
  {
    const h = harness(); let newer;
    h.ctx.onEvent = event => {
      if (event.type === 'cl:graph-loading' && event.detail.stage === 'error') { h.ctx.onEvent = null; newer = h.ctx.openHistory(B); }
    };
    const older = h.ctx.histAction(A); await h.reply(A, { status: 404 }); await older;
    await h.reply(B); await h.runTimers(); await newer;
    check('a recovery listener opening a new work before rejection delivery suppresses old work errors', () => {
      assert.equal(h.ctx.GKey, B); assert.equal(h.ctx.err.textContent, '');
      assert.equal(h.events.filter(e => e.type === 'cl:work-open-error').length, 0);
    });
  }

  {
    const h = harness(), pending = h.ctx.openHistory(A); await h.reply(A);
    const reading = h.ctx.versionApi.sourceDocuments();
    const sourceRequest = h.requests.find(r => r.url === '/api/history/docs?key=11111111');
    check('source lookup during delayed opening remains bound to the currently displayed old graph', () => {
      assert.ok(sourceRequest); assert.equal(h.requests.some(r => r.url === '/api/history/docs?key=' + A), false);
    });
    sourceRequest.resolve({ ok: true, json: () => Promise.resolve([{ name: 'origin.txt', text: 'origin source' }]) });
    await micro(); const docs = await reading;
    assert.equal(docs[0].name, 'origin.txt'); await h.runTimers(); await pending;
  }
  {
    const h = harness(), reading = h.ctx.versionApi.sourceDocuments().catch(e => e);
    const sourceRequest = h.requests.find(r => r.url === '/api/history/docs?key=11111111');
    const newer = h.ctx.openHistory(B); await h.reply(B); await h.runTimers(); await newer;
    sourceRequest.resolve({ ok: true, json: () => Promise.resolve([{ name: 'origin.txt', text: 'origin source' }]) });
    await micro(); const result = await reading;
    check('a late old source response is refused after a new graph commits', () => {
      assert.ok(result instanceof Error || result && result.message); assert.ok(result.message.includes('作品已切换'));
    });
  }

  {
    const h = harness(), result = h.ctx.openHistory(B); await h.reply(B); await h.runTimers(); await result;
    check('ordinary library selection updates the reload URL to the selected graph', () => {
      assert.equal(new URL(h.ctx.location.href).searchParams.get('data'), 'data/cache/' + B + '.json');
    });
  }
  {
    const h = harness(), oldList = h.ctx.loadHistory(), selected = h.ctx.openHistory(B);
    await h.reply(B); await h.runTimers(); await selected;
    await h.historyReply(1, [{ key: B, opens: 1 }]); await h.historyReply(0, [{ key: B, opens: 0 }]); await oldList;
    check('older library GET cannot replace a newer opened-work POST result', () => {
      assert.equal(h.ctx.histItems[0].opens, 1); assert.equal(h.ctx.histItems[0].key, B);
    });
  }
  {
    const h = harness(), oldList = h.ctx.loadHistory(), newList = h.ctx.loadHistory();
    await h.historyReply(1, [{ key: B, title: 'new library' }]); await newList;
    await h.historyReply(0, [{ key: A, title: 'old library' }]); await oldList;
    check('library GET responses respect the latest list request independently of graph loading', () => {
      assert.equal(h.ctx.histItems[0].key, B);
    });
  }
  {
    const h = harness(), opened = h.ctx.openHistory(A); await h.reply(A); await h.runTimers(); await opened;
    const list = h.ctx.loadHistory(); await h.historyReply(1, [{ key: A, opens: 9 }]); await list;
    await h.historyReply(0, [{ key: A, opens: 1 }]);
    check('older opened-work POST cannot replace a newer library GET result', () => {
      assert.equal(h.ctx.histItems[0].opens, 9);
    });
  }
  {
    const h = harness(); h.sweep(); const list = h.ctx.loadHistory();
    await h.historyReply(1, [{ key: B, title: 'new library' }]); await list;
    await h.historyReply(0, [{ key: A, title: 'stale sweep' }]);
    check('older sweep response cannot replace a newer library GET result', () => {
      assert.equal(h.ctx.histItems[0].key, B); assert.equal(h.ctx.$('libCount').textContent.includes('清理'), false);
    });
  }

  {
    const h = harness();
    h.ctx.GSrc = { from: 'analyze', key: '11111111', preview: true };
    h.ctx.CLTray = { payload() { return [{ name: 'new-work.txt', text: 'new work source' }]; } };
    const docs = await h.ctx.versionApi.sourceDocuments();
    check('analysis preview with inherited old key reads its actual tray source', () => {
      assert.equal(docs[0].name, 'new-work.txt');
      assert.equal(h.requests.length, 0, 'preview must not fetch the previous stored work source');
    });
  }
  {
    const h = harness();
    h.ctx.GSrc = { from: 'analyze', key: '11111111', preview: true };
    h.ctx.CLTray = { payload() { return []; } };
    const result = await h.ctx.versionApi.sourceDocuments().catch(e => e);
    check('analysis preview with no source tray refuses inherited old-work documents', () => {
      assert.ok(result && result.message); assert.equal(h.requests.length, 0);
    });
  }
  {
    const h = harness(), before = JSON.stringify(h.ctx.histItems);
    const result = h.ctx.histPost({ action: 'pin', key: A, pinned: true }).catch(e => e);
    h.requests[0].resolve({ ok: false, status: 403, json: () => Promise.resolve({ error: 'blocked' }) });
    const error = await result;
    check('failed library mutation refuses JSON error bodies and preserves the existing list', () => {
      assert.ok(error && error.message && error.message.includes('403'));
      assert.equal(JSON.stringify(h.ctx.histItems), before);
    });
  }
  {
    const h = harness(), before = JSON.stringify(h.ctx.histItems); h.sweep();
    h.requests[0].resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: 'failed' }) });
    await micro();
    check('failed library sweep preserves the list and presents its HTTP failure', () => {
      assert.equal(JSON.stringify(h.ctx.histItems), before);
      assert.ok(h.notices.some(text => text.includes('500')));
    });
  }
  {
    const h = harness();
    const recovered = h.ctx.readMark({ historyRecovered: true, opens: 0 });
    check('recovered library entries keep unknown prior reading separate from a new unread work', () => {
      assert.ok(recovered.includes('阅读记录未知'));
      assert.equal(recovered.includes('NEW'), false);
      assert.ok(h.ctx.readMark({ opens: 0 }).includes('NEW'));
    });
  }
  {
    const h = harness(), markup = h.ctx.readMark({ historyRecovered: true, opens: 3 });
    check('recovered reading counts identify new records and retain the unknown prior history', () => {
      assert.ok(markup.includes('新记录 3 次')); assert.ok(markup.includes('旧阅读次数未保留'));
    });
  }
  console.log('BOOT LOAD OWNERSHIP ' + checks + '/' + checks);
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
