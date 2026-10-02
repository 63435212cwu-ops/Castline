/* Offline tests of the actual SSE/IndexedDB client. No browser, network, model
 * or user storage is used. Run: node tests/deep_client_contract.js.
 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../js/analyze.js'), 'utf8');
const tests = [];
function test(name, fn) { tests.push([name, fn]); }
const plain = value => JSON.parse(JSON.stringify(value));

function runtime() {
  const store = new Map(), requests = [], responses = [], events = [];
  const later = fn => Promise.resolve().then(fn);
  const database = { createObjectStore() {}, transaction() { return { objectStore() { return {
    get(key) { const req = {}; later(() => { req.result = store.get(key) || null; if (req.onsuccess) req.onsuccess(); }); return req; },
    put(value, key) { store.set(key, plain(value)); }
  }; } }; } };
  const indexedDB = { open() { const req = { result: database }; later(() => { if (req.onsuccess) req.onsuccess(); }); return req; } };
  function stream(messages) {
    let index = 0;
    return { ok: true, body: { getReader() { return { read() {
      if (index >= messages.length) return Promise.resolve({ done: true });
      const message = messages[index++];
      if (message instanceof Error) return Promise.reject(message);
      return Promise.resolve({ done: false, value: Buffer.from('event: ' + message[0] + '\ndata: ' + JSON.stringify(message[1]) + '\n\n', 'utf8') });
    } }; } } };
  }
  const context = { window: {}, indexedDB, TextDecoder, AbortController, Promise, console,
    setTimeout(fn) { later(fn); return 1; }, clearTimeout() {},
    fetch(url, options) {
      requests.push({ url, payload: options && options.body ? JSON.parse(options.body) : null });
      if (!responses.length) return Promise.reject(new Error('Unexpected test network request: ' + url));
      const response = responses.shift();
      return response instanceof Error ? Promise.reject(response) : Promise.resolve(stream(response));
    } };
  vm.runInNewContext(source, context, { filename: 'js/analyze.js' });
  return { api: context.window.CLAnalyze, store, requests, responses, events,
    opts(mode, extra) { return Object.assign({ mode, modelKey: 'offline-model', onEvent: (ev, value) => events.push([ev, plain(value)]) }, extra); } };
}
function doneGraph(mode, extra) {
  return Object.assign({ title: mode, characters: [], events: [], relations: [], meta: { mode,
    extraction: { mode, processedComplete: true, complete: null, semanticCompleteness: 'unverified' } } }, extra);
}
const docs = [{ path: 'one.txt', name: '首章', text: '北辰看向星空。', kind: '正文', sourceId: 'original-upload-id' }];

test('summary and deep use distinct local cache keys and request modes', async () => {
  const t = runtime();
  t.responses.push([['done', { graph: doneGraph('summary') }]], [['done', { graph: doneGraph('deep') }]]);
  const summary = await t.api.run(docs, t.opts('summary'));
  const deep = await t.api.run(docs, t.opts('deep'));
  assert.strictEqual(summary.meta.mode, 'summary'); assert.strictEqual(deep.meta.mode, 'deep');
  assert.strictEqual(t.store.size, 2);
  assert.deepStrictEqual(t.requests.map(r => r.payload.mode), ['summary', 'deep']);
  await t.api.run(docs, t.opts('summary')); await t.api.run(docs, t.opts('deep'));
  assert.strictEqual(t.requests.length, 2, 'each mode should reuse only its own local cache');
});
test('default mode remains summary for backwards-compatible callers', async () => {
  const t = runtime(); t.responses.push([['done', { graph: doneGraph('summary') }]]);
  await t.api.run(docs, t.opts(undefined));
  assert.strictEqual(t.requests[0].payload.mode, 'summary');
});
test('stream reconnect preserves deep mode, source snapshot and force/refresh flags', async () => {
  const t = runtime(), control = {};
  t.responses.push([['hello', { job: 'deep-force-job', mode: 'deep' }]], [['done', { graph: doneGraph('deep') }]]);
  await t.api.run(docs, t.opts('deep', { force: true, refresh: true, control }));
  assert.strictEqual(t.requests.length, 2);
  const first = t.requests[0].payload, second = t.requests[1].payload;
  assert.strictEqual(first.mode, 'deep'); assert.strictEqual(second.mode, 'deep');
  assert.deepStrictEqual(first.docs, second.docs);
  assert.strictEqual(second.force, true); assert.strictEqual(second.refresh, true);
  assert.strictEqual(second.job, 'deep-force-job', 'finished force jobs must be replayed by exact ID, not started again');
});
test('explicit job attachment bypasses any older local graph cache', async () => {
  const t = runtime();
  t.responses.push([['done', { graph: doneGraph('deep', { title: 'old-result' }) }]],
    [['hello', { job: 'active-deep-job', mode: 'deep' }], ['done', { graph: doneGraph('deep', { title: 'active-job-result' }) }]]);
  await t.api.run(docs, t.opts('deep'));
  const attached = await t.api.run(docs, t.opts('deep', { job: 'active-deep-job' }));
  assert.strictEqual(t.requests.length, 2);
  assert.strictEqual(t.requests[1].payload.job, 'active-deep-job');
  assert.strictEqual(attached.title, 'active-job-result');
});
test('original source identity survives the actual client payload boundary', async () => {
  const t = runtime(); t.responses.push([['done', { graph: doneGraph('deep') }]]);
  await t.api.run(docs, t.opts('deep'));
  assert.strictEqual(t.requests[0].payload.docs[0].sourceId, 'original-upload-id');
});
test('file names participate in local identity like server assemble()', async () => {
  const t = runtime();
  const a = [{ name: '设定甲', text: '相同材料', kind: '设定' }], b = [{ name: '设定乙', text: '相同材料', kind: '设定' }];
  assert.notStrictEqual(t.api.hashDocs(a, 'model'), t.api.hashDocs(b, 'model'));
});
test('partial cached graph remains explicitly incomplete; refresh bypasses it', async () => {
  const t = runtime();
  const partial = doneGraph('deep');
  partial.meta.extraction = { mode: 'deep', complete: false, processedComplete: false, failedSegments: 1 };
  t.responses.push([['done', { graph: partial }]], [['done', { graph: doneGraph('deep') }]]);
  const first = await t.api.run(docs, t.opts('deep'));
  const cached = await t.api.run(docs, t.opts('deep'));
  assert.strictEqual(first.meta.extraction.complete, false); assert.strictEqual(cached.meta.extraction.complete, false);
  const resumed = await t.api.run(docs, t.opts('deep', { refresh: true }));
  assert.strictEqual(resumed.meta.extraction.complete, null);
  assert.strictEqual(t.requests.length, 2); assert.strictEqual(t.requests[1].payload.refresh, true);
});
test('failed stream is never cached as a complete graph', async () => {
  const t = runtime(); t.responses.push([['error', { message: 'offline failure' }]]);
  await assert.rejects(() => t.api.run(docs, t.opts('deep')), /offline failure/);
  assert.strictEqual(t.store.size, 0);
});
test('deep mode rejects an old server summary response instead of poisoning deep cache', async () => {
  const t = runtime(); t.responses.push([['done', { graph: doneGraph('summary') }]]);
  await assert.rejects(() => t.api.run(docs, t.opts('deep')), /深度|deep|模式|重启/);
  assert.strictEqual(t.store.size, 0);
});
test('deep mode rejects old unmarked cache while legacy summary caches stay readable', async () => {
  const t = runtime();
  const legacy = { title: 'legacy', characters: [], events: [], meta: { schema: 'castline/3' } };
  t.store.set(t.api.hashDocs(docs, 'offline-model'), legacy);
  const summary = await t.api.run(docs, t.opts('summary'));
  assert.strictEqual(summary.title, 'legacy');
  t.responses.push([['done', { graph: legacy }]]);
  await assert.rejects(() => t.api.run(docs, t.opts('deep')), /深度|deep|模式|重启/);
});
test('app and index expose both scopes and propagate selected/attached run mode', async () => {
  const app = fs.readFileSync(path.join(__dirname, '../js/app.js'), 'utf8');
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  const picker = html.match(/<select\b[^>]*\bid="analysisMode"[^>]*>([\s\S]*?)<\/select>/);
  assert(picker); assert(/value="summary"/.test(picker[1])); assert(/value="deep"/.test(picker[1]));
  const plan = app.slice(app.indexOf('function requestPlan('), app.indexOf('function renderPlan('));
  assert(/mode:\s*analysisMode\(\)/.test(plan));
  const start = app.slice(app.indexOf('function startRun('), app.indexOf('function failRun('));
  assert(/mode:\s*o\.mode\s*\|\|\s*analysisMode\(\)/.test(start));
  assert(/mode:\s*LAST\.mode/.test(start)); assert(/job:\s*o\.job/.test(start));
  const attach = app.slice(app.indexOf('function attachJob('), app.indexOf("$('attachHide')"));
  assert((attach.match(/mode:\s*j\.mode/g) || []).length === 2, 'both tray and source-recovery attachment paths preserve job mode');
  assert((attach.match(/job:\s*j\.job/g) || []).length === 2);
});

(async () => {
  let failures = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS ' + name); }
    catch (error) { failures++; console.error('FAIL ' + name + '\n' + error.stack); }
  }
  console.log('\n' + (tests.length - failures) + '/' + tests.length + ' deep client checks passed');
  process.exitCode = failures ? 1 : 0;
})();
