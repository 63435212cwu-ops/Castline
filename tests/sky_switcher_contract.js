'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.join(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'js/sky/sky-switcher.js'), 'utf8');
const CHROME = fs.readFileSync(path.join(ROOT, 'js/sky/sky-chrome.js'), 'utf8');
const APP = fs.readFileSync(path.join(ROOT, 'js/app.js'), 'utf8');
const CSS = fs.readFileSync(path.join(ROOT, 'css/sky-reading.css'), 'utf8');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
const asyncCases = [];
function testAsync(name, run) { asyncCases.push({ name, run }); }

function boot() {
  const sandbox = {};
  vm.runInNewContext(SRC, sandbox);
  assert.ok(sandbox.CLSkySwitcher || sandbox.module === undefined);
  return require(path.join(ROOT, 'js/sky/sky-switcher.js'));
}
const sw = boot();

const RAW = [
  { key: 'plain', title: '未排作品', at: '2026-01-02 10:00', characters: 10, chapters: 4 },
  { key: 'pinned', title: '置顶作品', at: '2020-01-01 10:00', pinned: true, characters: 0, chapters: 0 },
  { key: 'recent', title: '最新作品', at: '2026-09-07 17:37', display: '显示标题', characters: 453, chapters: 904 },
  { key: 'noname', at: '2026-01-01 10:00', characters: 0, chapters: 0 }
];

test('list ordering is byte-identical to the shelf comparator (pinned first, then most recent analysis)', () => {
  const keys = sw.listFor(RAW, null).map(e => e.key);
  assert.deepEqual(keys, ['pinned', 'recent', 'plain', 'noname']);
  const third = 'String(a.key || \'\').localeCompare(String(b.key || \'\'))';
  assert.ok(SRC.includes(third), 'switcher comparator lost the tie-break key (P2.8)');
  assert.ok(CHROME.includes('CLSkySwitcher') && CHROME.includes('orderWorks'),
    'shelf comparator drifted: sky-chrome must delegate to CLSkySwitcher.orderWorks, not re-implement');
});
test('current work is marked exactly once; display falls back to title then 未命名', () => {
  const list = sw.listFor(RAW, 'recent');
  assert.equal(list.filter(e => e.current).length, 1);
  assert.equal(list.find(e => e.key === 'recent').current, true);
  assert.equal(list.find(e => e.key === 'recent').title, '显示标题');
  assert.equal(list.find(e => e.key === 'noname').title, '未命名');
  assert.equal(sw.listFor(RAW, '').filter(e => e.current).length, 0);
});
test('missing-cache honesty: the entry stays in the list, marked unavailable — hiding is not an option', () => {
  const list = sw.listFor(RAW, null);
  assert.equal(sw.markUnavailable(list, 'plain'), true);
  assert.equal(list.length, 4, 'unavailable works are listed, not removed');
  assert.equal(list.find(e => e.key === 'plain').probe, 'down');
  assert.ok(sw.itemNote(list.find(e => e.key === 'plain')).includes('数据不可用'));
  assert.ok(sw.itemNote(list.find(e => e.key === 'plain')).includes('缺失'));
  assert.equal(sw.markUnavailable(list, 'plain', 'lost'), true);
  assert.ok(sw.itemNote(list.find(e => e.key === 'plain')).includes('服务未响应'));
  assert.equal(sw.markUnavailable(list, 'ghost'), false);
});
test('item notes state real counts; empty works get an honest dash, not fake numbers', () => {
  const list = sw.listFor(RAW, null);
  assert.equal(sw.itemNote(list.find(e => e.key === 'recent')), '453 角色 · 904 章');
  assert.equal(sw.itemNote(list.find(e => e.key === 'pinned')), '——');
  const odd = sw.listFor([{ key: 'x', characters: 'not-a-number', chapters: -3 }], null);
  assert.equal(odd[0].characters, 0);
  assert.equal(odd[0].chapters, 0);
});
test('failure normalization: explicit CLBootErrors kinds win; transport rejects fall back to net', () => {
  const e = new Error('boom'); e.clKind = 'http'; e.clStatus = 404;
  assert.deepEqual(sw.failOf(e), { kind: 'http', status: 404, message: 'boom' });
  const plain = new TypeError('fetch failed');
  const f = sw.failOf(plain);
  assert.equal(f.kind, 'net');
  assert.equal(f.status, 0);
});
test('single switch call path: only CLSkyChrome.openWork — the module never mounts or fetches graphs itself', () => {
  const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '');
  assert.ok(SRC.includes('CLSkyChrome.openWork'), 'switch must go through the same path as a shelf entry');
  assert.ok(!CODE.includes('openHistory'), 'switcher must not bypass the card-click path to call openHistory');
  assert.ok(!CODE.includes('mountRevision') && !CODE.includes('stagedMount'), 'switcher must never mount a graph');
  assert.equal((CODE.match(/cacheUrl/g) || []).length, 2);
  assert.ok(CODE.includes("method: 'HEAD'") && CODE.includes("cache: 'no-store'"), 'availability probe is fresh HEAD-only fetch');
  assert.ok(CODE.includes('MAX_PROBE_CONCURRENCY = 4'), 'availability probes have a fixed concurrency budget');
  assert.ok(CODE.includes('AbortController') && CODE.includes('cancelScope'), 'probe and history scopes are cancellable');
  assert.equal((CODE.match(/data\/cache\//g) || []).length, 1, 'the only data/cache touch is the HEAD probe URL builder');
  const owStart = CHROME.indexOf('function openWork(key)');
  assert.ok(owStart > 0);
  const owEnd = CHROME.indexOf('\n  }', owStart);
  const ow = CHROME.slice(owStart, owEnd);
  assert.ok(ow.includes("#histList .hist"), 'openWork clicks the recent card');
  assert.ok(ow.includes("#libList .lbc"), 'openWork clicks the library card');
});
test('shelf entry and in-book switch share the exact openHistory call site', () => {
  const ha = APP.slice(APP.indexOf('function histAction'), APP.indexOf('function bindHistClicks'));
  assert.ok(ha.includes('return openHistory(key)'), 'default card action routes into openHistory');
  assert.ok(ha.includes("cl:work-open-error"), 'open failure signs out the structured event');
  assert.ok(ha.includes("(e && e.clKind) || 'net'"), 'event classification honours CLBootErrors kinds with net fallback');
});
test('openHistory carries CLBootErrors classification end to end (http/json/mount, 404 keeps its wording)', () => {
  const oh = APP.slice(APP.indexOf('function openHistory'), APP.indexOf('function loadDocsFromHistory'));
  assert.ok(oh.includes("bootFail('http'") && oh.includes('记忆文件缺失'), 'http classification with original 404 wording');
  assert.ok(oh.includes("bootFail('json'"), 'corrupt JSON classified');
  assert.ok(oh.includes("bootFail('mount'"), 'mount failure classified');
});
test('tools menu wiring: the 换作品 item lives in the 作品 group with activate and sync special-casing', () => {
  const groups = CHROME.slice(CHROME.indexOf('var TOOL_GROUPS'), CHROME.indexOf('var menu = null'));
  assert.ok(groups.includes("id: 'skySwitch'"), 'menu item exists');
  assert.ok(groups.slice(0, groups.indexOf('{ key: \'data\'')).includes("id: 'skySwitch'"), 'item sits in the work group');
  assert.equal((CHROME.match(/getAttribute\('data-for'\) === 'skySwitch'/g) || []).length, 2, 'activate + syncItems both special-case');
});
test('panel markup facts: aria-current on the current work, 44px hit targets, failure actions present', () => {
  assert.ok(SRC.includes('aria-current="true"'), 'current work marked aria-current');
  assert.ok(SRC.includes('skySwitchFailBack'), 'return-to-origin action exists');
  assert.ok(/\.sws-item[^{]*\{[^}]*min-height:\s*44px/.test(CSS), 'list items keep the 44px hit target');
  assert.ok(CSS.includes('.sky-switch-fail') && CSS.includes('.sws-btn.is-primary'), 'failure surface styled with a primary action');
  assert.ok(!/style=/.test(SRC.replace(/\/\*[\s\S]*?\*\//g, '')), 'no inline style attributes');
});

function fakeElement(doc, id) {
  return {
    id: id || '', hidden: false, className: '', innerHTML: '', textContent: '',
    attributes: Object.create(null), listeners: Object.create(null), parentNode: null,
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    appendChild(child) { child.parentNode = this; if (child.id) doc.nodes.set(child.id, child); return child; },
    querySelector(selector) { return selector === '.sws-list' ? doc.getElementById('skySwitchList') : null; },
    focus() {}, contains() { return false; }
  };
}
function makeRuntime(fetch, withAbort) {
  const doc = {
    nodes: new Map(), handlers: Object.create(null), activeElement: null, body: null,
    createElement() { return fakeElement(this, ''); },
    getElementById(id) { if (!this.nodes.has(id)) this.nodes.set(id, fakeElement(this, id)); return this.nodes.get(id); },
    addEventListener(name, fn) { (this.handlers[name] || (this.handlers[name] = [])).push(fn); },
    fire(name, detail) { (this.handlers[name] || []).forEach(fn => fn({ type: name, detail: detail || {} })); }
  };
  doc.body = fakeElement(doc, 'body'); doc.activeElement = fakeElement(doc, 'active');
  const opened = [];
  const sandbox = {
    document: doc, location: { search: '?sky=1' }, fetch,
    CLSky: { enabled: () => true },
    CLApp: { key: () => 'current', graph: () => ({ title: 'fixture' }) },
    CLSkyChrome: { openWork: key => { opened.push(key); doc.fire('cl:graph-loading', { stage: 'fetch' }); } },
    console: { log() {}, warn() {}, error() {} }
  };
  if (withAbort) sandbox.AbortController = function () { this.signal = { aborted: false }; this.abort = () => { this.signal.aborted = true; }; };
  sandbox.window = sandbox;
  vm.runInNewContext(SRC, sandbox, { filename: 'sky-switcher.js' });
  return { api: sandbox.CLSkySwitcher, doc, opened, sandbox };
}
function controlledFetch() {
  const calls = []; let activeHeads = 0, maxActiveHeads = 0;
  function fetch(url, options) {
    let resolvePromise, rejectPromise, settled = false;
    const promise = new Promise((resolve, reject) => { resolvePromise = resolve; rejectPromise = reject; });
    const rec = {
      url, options: options || {}, settled: false,
      resolve(value) { if (settled) return; settled = rec.settled = true; if (rec.options.method === 'HEAD') activeHeads--; resolvePromise(value); },
      reject(error) { if (settled) return; settled = rec.settled = true; if (rec.options.method === 'HEAD') activeHeads--; rejectPromise(error); }
    };
    if (rec.options.method === 'HEAD') { activeHeads++; maxActiveHeads = Math.max(maxActiveHeads, activeHeads); }
    calls.push(rec); return promise;
  }
  return { fetch, calls, maxActiveHeads: () => maxActiveHeads,
    heads: () => calls.filter(x => x.options.method === 'HEAD'),
    histories: () => calls.filter(x => x.url === '/api/history') };
}
function apiResponse(status, items) { return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve({ items: items || [] }) }; }
function workItems(keys) { return keys.map((key, i) => ({ key, title: key, at: '2026-12-' + String(31 - (i % 28)).padStart(2, '0') + ' 12:00', characters: 1, chapters: 1 })); }
async function flushPromises(turns = 12) { for (let i = 0; i < turns; i++) await Promise.resolve(); }
function headKey(req) { return req.url.slice(req.url.lastIndexOf('/') + 1).replace(/\.json$/, ''); }
function resolveHeads(calls, statusOf) {
  calls.forEach(req => { const status = statusOf(headKey(req)); if (status === 'lost') req.reject(new Error('offline fixture')); else req.resolve(apiResponse(status, [])); });
}
function entry(api, key) { return api.entries().find(row => row.key === key); }
function clickEntry(rt, api, key) {
  const index = api.entries().findIndex(row => row.key === key);
  assert.ok(index >= 0, 'test target exists in the module entry list');
  const button = { getAttribute(name) { return name === 'data-i' ? String(index) : null; } };
  const list = rt.doc.getElementById('skySwitchList');
  assert.equal(typeof list.listeners.click, 'function');
  list.listeners.click({ target: { closest: () => button } });
}

testAsync('92-entry probes stay within four concurrent HEADs and preserve down/lost states', async () => {
  const fetch = controlledFetch(), rt = makeRuntime(fetch.fetch, true);
  const keys = Array.from({ length: 92 }, (_, i) => i === 0 ? 'current' : 'bulk-' + i);
  rt.api.open(); fetch.histories()[0].resolve(apiResponse(200, workItems(keys))); await flushPromises();
  assert.equal(fetch.heads().length, 4);
  let guard = 0;
  while (fetch.heads().filter(req => !req.settled).length || fetch.heads().length < 92) {
    assert.ok(++guard < 40, 'controlled scheduler drains the full untruncated list');
    const pending = fetch.heads().filter(req => !req.settled);
    if (!pending.length) { await flushPromises(); continue; }
    assert.ok(pending.length <= 4);
    resolveHeads(pending, key => key === 'bulk-90' ? 404 : key === 'bulk-91' ? 'lost' : 200);
    await flushPromises(); assert.ok(fetch.maxActiveHeads() <= 4);
  }
  assert.equal(fetch.heads().length, 92);
  assert.equal(entry(rt.api, 'bulk-90').probe, 'down');
  assert.equal(entry(rt.api, 'bulk-91').probe, 'lost');
  assert.equal(entry(rt.api, 'bulk-89').probe, 'ok');
  rt.api.close(false);
});

testAsync('new open and choose abort old scopes; late responses do not overwrite the live list', async () => {
  const fetch = controlledFetch(), rt = makeRuntime(fetch.fetch, true);
  rt.api.open(); fetch.histories()[0].resolve(apiResponse(200, workItems(['current','shared-B','old-C','old-D','old-E','old-F','old-G','old-H']))); await flushPromises();
  const oldHeads = fetch.heads().slice(); assert.equal(oldHeads.length, 4);
  rt.api.open();
  assert.ok(oldHeads.every(req => req.options.signal && req.options.signal.aborted), 'new open aborts previous scope');
  fetch.histories()[1].resolve(apiResponse(200, workItems(['current','shared-B','new-C','new-D']))); await flushPromises();
  assert.equal(fetch.heads().length, 4, 'new probes wait for globally active old requests');
  resolveHeads(oldHeads, key => key === 'shared-B' ? 404 : 200); await flushPromises();
  const newHeads = fetch.heads().slice(4);
  assert.equal(newHeads.length, 4);
  assert.equal(entry(rt.api, 'shared-B').probe, 'ok', 'late same-key 404 cannot poison the new scope');
  clickEntry(rt, rt.api, 'shared-B');
  assert.deepEqual(rt.opened, ['shared-B']);
  assert.ok(newHeads.every(req => req.options.signal && req.options.signal.aborted), 'choose aborts its probe scope');
  resolveHeads(newHeads, key => key === 'shared-B' ? 404 : 200); await flushPromises();
  assert.equal(entry(rt.api, 'shared-B').probe, 'ok', 'late post-choose response cannot overwrite current entries');
  assert.equal(fetch.heads().length, 8, 'old queued probes never launch after close/choose');

  rt.api.open(); fetch.histories()[2].resolve(apiResponse(200, workItems(['current','close-B','close-C','close-D']))); await flushPromises();
  const closeHeads = fetch.heads().slice(8); assert.equal(closeHeads.length, 4);
  rt.api.close(false);
  assert.ok(closeHeads.every(req => req.options.signal && req.options.signal.aborted), 'explicit close aborts active HEAD requests');
  resolveHeads(closeHeads, () => 404); await flushPromises();
  assert.equal(fetch.heads().length, 12, 'close stops the remainder of the old queue');
  assert.equal(entry(rt.api, 'close-B').probe, 'ok', 'late responses after close cannot mark entries unavailable');

  rt.api.open(); fetch.histories()[3].resolve(apiResponse(200, workItems(['current','graph-B','graph-C','graph-D']))); await flushPromises();
  const graphHeads = fetch.heads().slice(12); assert.equal(graphHeads.length, 4);
  rt.doc.fire('cl:graph-loading', { stage: 'layout' });
  assert.ok(graphHeads.some(req => req.options.signal && !req.options.signal.aborted), 'non-fetch graph phases do not cancel switcher probes');
  assert.equal(rt.doc.getElementById('skySwitcher').hidden, false, 'non-fetch graph phases leave the current panel open');
  rt.doc.fire('cl:graph-loading', { stage: 'fetch' });
  assert.ok(graphHeads.every(req => req.options.signal && req.options.signal.aborted), 'real fetch phase cancels and closes the old switcher scope');
  assert.equal(rt.doc.getElementById('skySwitcher').hidden, true);
  resolveHeads(graphHeads, () => 404); await flushPromises();
  assert.equal(fetch.heads().length, 16);
  assert.equal(entry(rt.api, 'graph-B').probe, 'ok');

  const headsBeforeLateHistory = fetch.heads().length;
  rt.api.open(); const lateHistory = fetch.histories()[4];
  rt.api.close(false);
  assert.ok(lateHistory.options.signal && lateHistory.options.signal.aborted, 'close aborts in-flight metadata fetch');
  lateHistory.resolve(apiResponse(200, workItems(Array.from({ length: 92 }, (_, i) => 'late-meta-' + i))));
  await flushPromises();
  assert.equal(fetch.heads().length, headsBeforeLateHistory, 'aborted stale metadata does not schedule HEADs');
});

testAsync('close cancels metadata; without AbortController stale history and probe queues cannot affect reopen', async () => {
  const fetch = controlledFetch(), rt = makeRuntime(fetch.fetch, false);
  rt.api.open(); const staleHistory = fetch.histories()[0];
  rt.api.close(false);
  rt.api.open(); const liveHistory = fetch.histories()[1];
  liveHistory.resolve(apiResponse(200, workItems(['current','shared-B','scope2-C','scope2-D','scope2-E','scope2-F','scope2-G','scope2-H']))); await flushPromises();
  assert.equal(fetch.heads().length, 4);
  staleHistory.resolve(apiResponse(200, workItems(Array.from({ length: 92 }, (_, i) => 'stale-' + i)))); await flushPromises();
  assert.equal(fetch.heads().length, 4, 'late metadata cannot schedule the old 92-entry queue');
  assert.equal(entry(rt.api, 'shared-B').probe, 'ok');

  rt.api.close(false);
  rt.api.open(); const latestHistory = fetch.histories()[2];
  latestHistory.resolve(apiResponse(200, workItems(['current','shared-B','latest-C','latest-D']))); await flushPromises();
  const oldHeads = fetch.heads().slice();
  assert.equal(oldHeads.length, 4, 'the old queue has only four in-flight requests without AbortController');
  assert.ok(oldHeads.every(req => !req.options.signal), 'fallback omits unsupported AbortSignal');
  resolveHeads(oldHeads, () => 404); await flushPromises();
  const allHeads = fetch.heads();
  assert.equal(allHeads.length, 8, 'old queued remainder stays stopped while latest scope consumes freed slots');
  assert.equal(entry(rt.api, 'shared-B').probe, 'ok', 'late old HEADs cannot poison latest entries');
  const latestHeads = allHeads.slice(4);
  resolveHeads(latestHeads, key => key === 'latest-C' ? 404 : key === 'latest-D' ? 'lost' : 200); await flushPromises();
  assert.equal(entry(rt.api, 'shared-B').probe, 'ok');
  assert.equal(entry(rt.api, 'latest-C').probe, 'down');
  assert.equal(entry(rt.api, 'latest-D').probe, 'lost');
});

async function runAsyncContracts() {
  for (const item of asyncCases) { await item.run(); passed++; console.log('PASS ' + item.name); }
  console.log('sky_switcher_contract: ' + passed + ' passed');
}
runAsyncContracts().catch(error => { console.error(error && error.stack || error); process.exitCode = 1; });
