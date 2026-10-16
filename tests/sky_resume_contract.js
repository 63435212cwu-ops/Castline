'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(process.env.CL_TEST_RESUME_FILE || path.join(__dirname, '..', 'js/sky/sky-resume.js'), 'utf8');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

function fakeStorage(seed) {
  const map = new Map(Object.entries(seed || {}));
  return {
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
    size: () => map.size,
    raw: k => map.get('castline.resume.' + k),
    keys: () => Array.from(map.keys())
  };
}
function boot(seed) {
  const sandbox = { localStorage: fakeStorage(seed) };
  vm.runInNewContext(SRC, sandbox);
  return { api: sandbox.CLSkyResume, st: sandbox.localStorage };
}
function rec(over) {
  return Object.assign({ v: 1, at: 1759800000000, view: 'plot', compass: null, group: null, playback: 'chapters', cursor: 5, eventIndex: null, label: '第 6 回 · 试禅心' }, over);
}
const ENV = { nCh: 10, events: 20, chars: ['红衣', '青灯'], groups: ['camp', 'stance', 'role'] };

test('write/read round-trip keeps a valid record and uses the isolated per-work key', () => {
  const { api, st } = boot();
  assert.equal(api.write('alpha', rec()), true);
  assert.equal(st.keys().length, 1);
  assert.ok(st.keys()[0] === 'castline.resume.alpha');
  assert.equal(JSON.stringify(api.read('alpha')), JSON.stringify(rec()));
});
test('records stay isolated between works', () => {
  const { api } = boot();
  api.write('alpha', rec({ cursor: 1, label: '第 2 回' }));
  api.write('beta', rec({ cursor: 9, label: '第 10 回' }));
  assert.equal(api.read('alpha').cursor, 1);
  assert.equal(api.read('beta').cursor, 9);
  assert.equal(api.read('gamma'), null);
});
test('corrupted entries self-heal: read returns null, the bad key is removed, no error escapes', () => {
  for (const bad of ['{broken json', '[]', 'null', '42', '"text"', JSON.stringify({ v: 9 }),
    JSON.stringify({ v: 1, at: 'yesterday', view: 'plot' }), JSON.stringify({ v: 1, at: 1, view: 'somewhere' }),
    JSON.stringify({ v: 1, at: 1, view: 'compass' }), JSON.stringify(rec({ cursor: -3 })),
    JSON.stringify(rec({ eventIndex: 2.5 })), 'x'.repeat(4096)]) {
    const { api, st } = boot({ 'castline.resume.alpha': bad });
    assert.equal(api.read('alpha'), null, JSON.stringify(bad).slice(0, 60));
    assert.equal(st.raw('alpha'), undefined, 'bad key must be removed for ' + JSON.stringify(bad).slice(0, 40));
  }
});
test('oversized or unencodable records are rejected at write time, never stored', () => {
  const { api, st } = boot();
  assert.equal(api.write('alpha', rec({ label: '象'.repeat(4096) })), false);
  assert.equal(st.size(), 0);
  assert.equal(api.read('alpha'), null);
});
test('sanitize bounds: names/labels/groups are length-capped and must be strings', () => {
  const { api } = boot();
  const p = api.pure;
  assert.equal(p.sanitize(rec({ compass: 'x'.repeat(65), view: 'compass' })), null);
  assert.equal(p.sanitize(rec({ group: 42 })), null);
  assert.equal(p.sanitize(rec({ group: 'stance' })).group, 'stance');
  const still = p.sanitize(rec({ label: '回'.repeat(80) }));
  assert.ok(still && still.label.length === 80);
  assert.equal(p.sanitize(rec({ label: 7 })), null);
});
test('throttle decisions: unchanged payload skips; under the gap defers; past the gap writes', () => {
  const { api } = boot();
  const p = api.pure;
  const pay = p.payloadOf(rec());
  assert.equal(pay, p.payloadOf(rec({ at: 9999999999999 })), 'timestamp is not state');
  assert.equal(p.shouldWrite(10000, 0, pay, pay), 'skip');
  assert.equal(p.shouldWrite(10000, -Infinity, pay, ''), 'write');
  assert.equal(p.shouldWrite(10000, 9500, pay, ''), 'defer');
  assert.equal(p.shouldWrite(10000, 7999, pay, ''), 'write');
  assert.equal(p.shouldWrite(10000, 0, '', ''), 'skip');
});
test('labels state the view essentials: compass name versus chapter and event naming', () => {
  const { api } = boot();
  const p = api.pure;
  assert.equal(p.labelOf(rec({ view: 'compass', compass: '红衣' })), '罗盘 · 红衣');
  assert.equal(p.labelOf(rec({ eventIndex: 3 }), { chapterLabel: '第 6 回', eventTitle: '四圣试禅心' }), '第 6 回 · 四圣试禅心');
  assert.equal(p.labelOf(rec({ eventIndex: 3 }), {}), '未命名事件');
  assert.equal(p.labelOf(rec({ cursor: 5 }), { chapterLabel: '第 6 回' }), '第 6 回');
  assert.equal(p.labelOf(rec({ cursor: null }), {}), '星盘');
});
test('restore plans mirror the manual action sequence and refuse to restore against a mismatched graph', () => {
  const { api } = boot();
  const p = api.pure;
  assert.equal(JSON.stringify(p.plan(rec(), ENV)), JSON.stringify([
    { op: 'playback', mode: 'chapters' }, { op: 'setPlot', on: true }, { op: 'seek', cursor: 5 }]));
  assert.equal(JSON.stringify(p.plan(rec({ cursor: null, eventIndex: 7, playback: 'events' }), ENV)),
    JSON.stringify([{ op: 'playback', mode: 'events' }, { op: 'seekEventAt', index: 7 }]));
  assert.equal(JSON.stringify(p.plan(rec({ cursor: null, view: 'compass', compass: '红衣' }), ENV)),
    JSON.stringify([{ op: 'openCompass', name: '红衣' }]));
  assert.equal(JSON.stringify(p.plan(rec({ group: 'stance' }), ENV)[0]), JSON.stringify({ op: 'regroup', key: 'stance' }));
  assert.equal(p.plan(rec({ cursor: 10 }), ENV), null, 'cursor beyond chapter count');
  assert.equal(p.plan(rec({ cursor: null, eventIndex: 20 }), ENV), null, 'event beyond graph');
  assert.equal(p.plan(rec({ cursor: null, view: 'compass', compass: '无名' }), ENV), null, 'compass character missing');
  assert.equal(p.plan(rec({ group: 'field:x' }), ENV), null, 'grouping the model does not offer');
});
test('equivalence canon is byte-stable and sensitive to exactly one state change at a time', () => {
  const { api } = boot();
  const p = api.pure;
  const base = p.canonOf(
    { mode: 'constellation', plot: true, compass: null, group: 'camp', playing: false, cursor: 5 },
    { mode: 'chapters', eventId: 'e9', eventIndex: 9, position: 8, stage: 'event', panel: false, scrub: { position: 6, total: 10 } },
    { caption: '第 6 回 · 试禅心', crumb: null });
  const same = p.canonOf(
    { mode: 'constellation', plot: true, compass: null, group: 'camp', playing: false, cursor: 5 },
    { mode: 'chapters', eventId: 'e9', eventIndex: 9, position: 8, stage: 'event', panel: false, scrub: { position: 6, total: 10 } },
    { caption: '第 6 回 · 试禅心', crumb: null });
  assert.equal(JSON.stringify(base), JSON.stringify(same));
  const moved = p.canonOf(
    { mode: 'constellation', plot: true, compass: null, group: 'camp', playing: false, cursor: 6 },
    { mode: 'chapters', eventId: 'e9', eventIndex: 9, position: 8, stage: 'event', panel: false, scrub: { position: 7, total: 10 } },
    { caption: '第 7 回', crumb: null });
  assert.notEqual(JSON.stringify(base), JSON.stringify(moved));
});
test('clear removes the record and reads afterwards find nothing', () => {
  const { api } = boot();
  api.write('alpha', rec());
  assert.equal(api.clear('alpha'), true);
  assert.equal(api.read('alpha'), null);
});
test('broken storage is tolerated: reads return null and writes fail without throwing', () => {
  const sandbox = { localStorage: {
    getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); }
  } };
  vm.runInNewContext(SRC, sandbox);
  const api = sandbox.CLSkyResume;
  assert.equal(api.read('alpha'), null);
  assert.equal(api.write('alpha', rec()), false);
  assert.equal(api.stats().storage, false);
});
console.log('RESUME ' + passed + '/' + passed);


function runtimeBoot() {
  const listeners = Object.create(null), timers = new Map(), actions = [];
  let serial = 0, key = 'alpha', graph = { characters: [], events: Array.from({ length: 20 }, (_, i) => ({ id: 'e' + i })) };
  const doc = {
    addEventListener(type, fn) { (listeners[type] || (listeners[type] = [])).push(fn); },
    getElementById() { return null; }, querySelector() { return null; }
  };
  const sky = {
    model() { return { nCh: 20, groupings: [] }; },
    state() { return { mode: 'constellation', plot: false }; },
    playerState() { return {}; },
    playback(mode) { actions.push({ key, op: 'playback', mode }); },
    setPlot(on) { actions.push({ key, op: 'setPlot', on }); },
    seek(cursor) { actions.push({ key, op: 'seek', cursor }); }
  };
  const sandbox = {
    document: doc, localStorage: fakeStorage(), CLSky: sky,
    CLApp: { key() { return key; }, graph() { return graph; } },
    addEventListener() {},
    setTimeout(fn) { const id = ++serial; timers.set(id, fn); return id; },
    clearTimeout(id) { timers.delete(id); }, setInterval() { return 1; }
  };
  sandbox.window = sandbox;
  vm.runInNewContext(SRC, sandbox);
  const api = sandbox.CLSkyResume;
  api.write('alpha', rec({ cursor: 7 }));
  function emit(type, detail) { (listeners[type] || []).forEach(fn => fn({ detail })); }
  function runTimers() { while (timers.size) { const [id, fn] = timers.entries().next().value; timers.delete(id); fn(); } }
  function request() { assert.equal(api.openResume('alpha'), true); emit('cl:graph-ready', { key: 'alpha' }); }
  sandbox.CLSkyChrome = { openWork() {} };
  return { api, actions, emit, runTimers, request,
    setWork(next, replaceGraph = true) { key = next; if (replaceGraph) graph = { characters: [], events: graph.events.slice() }; } };
}
test('runtime restore keeps a valid same-work same-graph continuation', () => {
  const r = runtimeBoot(); r.request(); r.runTimers();
  assert.equal(r.actions.length, 3);
  assert.equal(r.actions[2].key, 'alpha'); assert.equal(r.actions[2].cursor, 7);
});
test('queued restore never applies alpha reading state to beta', () => {
  const r = runtimeBoot(); r.request(); r.setWork('beta'); r.runTimers();
  assert.equal(r.actions.length, 0, 'old work restore must not touch the new work');
  assert.ok(r.api.read('alpha'), 'a cancelled restore keeps the original saved position');
});
test('queued restore never applies to a replacement graph with the same work key', () => {
  const r = runtimeBoot(); r.request(); r.setWork('alpha'); r.runTimers();
  assert.equal(r.actions.length, 0, 'graph identity changed after graph-ready');
});
test('new fetch invalidates an already queued same-work continuation', () => {
  const r = runtimeBoot(); r.request(); r.emit('cl:graph-loading', { stage: 'fetch' }); r.runTimers();
  assert.equal(r.actions.length, 0);
});
test('new graph-ready invalidates an older queued continuation', () => {
  const r = runtimeBoot(); r.request(); r.setWork('beta'); r.emit('cl:graph-ready', { key: 'beta' }); r.runTimers();
  assert.equal(r.actions.length, 0);
});
console.log('RESUME RUNTIME ' + passed + '/' + passed);
