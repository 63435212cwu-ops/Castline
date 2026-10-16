'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, '..', 'js/sky/sky-bookmarks.js'), 'utf8');
const RESUME_SRC = fs.readFileSync(path.join(__dirname, '..', 'js/sky/sky-resume.js'), 'utf8');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

function fakeStorage(seed) {
  const map = new Map(Object.entries(seed || {}));
  return {
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
    size: () => map.size,
    raw: k => map.get('castline.bookmarks.' + k),
    keys: () => Array.from(map.keys())
  };
}
function boot(seed) {
  const sandbox = { localStorage: fakeStorage(seed) };
  vm.runInNewContext(RESUME_SRC, sandbox);
  vm.runInNewContext(SRC, sandbox);
  return { bookmark: sandbox.CLSkyBookmarks, resume: sandbox.CLSkyResume, st: sandbox.localStorage };
}
function item(over) {
  return Object.assign({ eventIndex: 178, title: '大战红孩儿', view: 'plot', ref: null, at: 1759800000000 }, over);
}
const ENV = { events: 240, chars: ['孙悟空', '唐僧'] };

test('write/read round trip under the isolated per-work key', () => {
  const { bookmark, st } = boot();
  const r = bookmark.add('alpha', item());
  assert.equal(r.ok, true);
  assert.equal(JSON.stringify(r.item), JSON.stringify(item()));
  assert.equal(st.keys().length, 1);
  assert.equal(st.keys()[0], 'castline.bookmarks.alpha');
  assert.equal(JSON.stringify(bookmark.list('alpha')), JSON.stringify([item()]));
});
test('records stay isolated between works', () => {
  const { bookmark } = boot();
  bookmark.add('alpha', item({ eventIndex: 1, title: '其一' }));
  bookmark.add('beta', item({ eventIndex: 2, title: '其二' }));
  assert.equal(bookmark.list('alpha')[0].eventIndex, 1);
  assert.equal(bookmark.list('beta')[0].eventIndex, 2);
  assert.equal(bookmark.list('gamma').length, 0);
  assert.equal(bookmark.count('alpha'), 1);
});
test('whole-key corruption self-heals: empty list, bad key removed, no error escapes', () => {
  for (const bad of ['{broken json', '[]', 'null', '42', '"text"',
    JSON.stringify({ v: 9, items: [] }), JSON.stringify({ v: 1, items: {} }),
    JSON.stringify({ v: 1 }), 'x'.repeat(40000)]) {
    const { bookmark, st } = boot({ 'castline.bookmarks.alpha': bad });
    assert.equal(JSON.stringify(bookmark.list('alpha')), '[]', JSON.stringify(bad).slice(0, 60));
    assert.equal(st.raw('alpha'), undefined, 'bad key must be removed for ' + JSON.stringify(bad).slice(0, 40));
    assert.ok(bookmark.stats().selfHeals >= 1);
  }
});
test('partial corruption drops bad entries and persists the cleaned list immediately', () => {
  const payload = { v: 1, items: [item({ eventIndex: 1, title: '其一' }), { eventIndex: 'oops' }, item({ eventIndex: 2, title: '其二' }), item({ eventIndex: 1, title: '重复' })] };
  const { bookmark, st } = boot({ 'castline.bookmarks.alpha': JSON.stringify(payload) });
  const items = bookmark.list('alpha');
  assert.equal(items.length, 2);
  assert.equal(JSON.stringify(items), JSON.stringify([item({ eventIndex: 1, title: '其一' }), item({ eventIndex: 2, title: '其二' })]));
  const rewritten = JSON.parse(st.raw('alpha'));
  assert.equal(rewritten.items.length, 2, 'cleaned list is written back, healing is not display-only');
  assert.equal(bookmark.stats().selfHeals, 1);
});
test('hard cap is an honest refusal, never a silent eviction', () => {
  const { bookmark, st } = boot();
  for (let i = 0; i < 50; i++) {
    const r = bookmark.add('alpha', item({ eventIndex: i, title: '第' + i + '事' }));
    assert.equal(r.ok, true, 'add #' + i);
  }
  assert.equal(bookmark.count('alpha'), 50);
  const before = st.raw('alpha');
  const over = bookmark.add('alpha', item({ eventIndex: 999, title: '进不来的' }));
  assert.equal(over.ok, false);
  assert.equal(over.reason, 'full');
  assert.equal(st.raw('alpha'), before, 'storage untouched when refusing');
  assert.equal(bookmark.count('alpha'), 50);
});
test('re-saving the same event is a stable no-op (toggle idempotence)', () => {
  const { bookmark, st } = boot();
  bookmark.add('alpha', item());
  const before = st.raw('alpha');
  const again = bookmark.add('alpha', item({ at: 1759800001111 }));
  assert.equal(again.ok, false);
  assert.equal(again.reason, 'exists');
  assert.equal(st.raw('alpha'), before);
  assert.equal(bookmark.count('alpha'), 1);
});
test('sanitize bounds: title length cap, view whitelist, compass identity, integer fields', () => {
  const { bookmark } = boot();
  const p = bookmark.pure;
  assert.equal(p.sanitizeItem(item({ title: '长'.repeat(81) })), null);
  assert.ok(p.sanitizeItem(item({ title: '长'.repeat(80) })));
  assert.equal(p.sanitizeItem(item({ view: 'somewhere' })), null);
  assert.equal(p.sanitizeItem(item({ view: 'compass', ref: null })), null);
  assert.equal(p.sanitizeItem(item({ view: 'compass', ref: 'x'.repeat(65) })), null);
  assert.equal(JSON.stringify(p.sanitizeItem(item({ view: 'compass', ref: '孙悟空' }))), JSON.stringify(item({ view: 'compass', ref: '孙悟空' })));
  assert.equal(p.sanitizeItem(item({ view: 'decode', ref: '幻影名' })).ref, null);
  assert.equal(p.sanitizeItem(item({ eventIndex: -1 })), null);
  assert.equal(p.sanitizeItem(item({ eventIndex: 2.5 })), null);
  assert.equal(p.sanitizeItem(item({ at: '昨天' })), null);
  assert.equal(p.sanitizeItem('{"eventIndex":"bad"}'), null);
});
test('oversized or unencodable lists are rejected at write time, never stored', () => {
  const { bookmark, st } = boot();
  const worst = [];
  for (let i = 0; i < 50; i++) worst.push(item({ eventIndex: i, title: '象'.repeat(80), view: 'compass', ref: '人'.repeat(64) }));
  assert.ok(bookmark.pure.encode({ v: 1, items: worst }), 'worst-case legit list fits under the byte cap');
  const bloated = [];
  for (let i = 0; i < 120; i++) bloated.push(item({ eventIndex: i, title: '象'.repeat(80) }));
  const s = bookmark.pure.encode({ v: 1, items: bloated });
  assert.equal(s, null, 'oversized payloads are rejected by the byte cap');
  assert.equal(st.size(), 0);
});
test('dedupe keeps first-come order; removal filters exactly one event', () => {
  const { bookmark } = boot();
  bookmark.add('alpha', item({ eventIndex: 7, title: '七' }));
  bookmark.add('alpha', item({ eventIndex: 3, title: '三' }));
  assert.equal(JSON.stringify(bookmark.list('alpha').map(i => i.eventIndex)), '[7,3]');
  assert.equal(bookmark.remove('alpha', 3), true);
  assert.equal(JSON.stringify(bookmark.list('alpha').map(i => i.eventIndex)), '[7]');
  assert.equal(bookmark.remove('alpha', 3), false, 'removing what is absent is a no-op false');
});
test('jump plans: plot seeks, compass re-enters with its character, decode re-opens the panel', () => {
  const { bookmark } = boot();
  const p = bookmark.pure;
  assert.equal(JSON.stringify(p.plan(item(), ENV)), JSON.stringify([{ op: 'locateEvent', index: 178 }]));
  assert.equal(JSON.stringify(p.plan(item({ view: 'compass', ref: '孙悟空' }), ENV)),
    JSON.stringify([{ op: 'locateEvent', index: 178 }, { op: 'openCompass', name: '孙悟空' }]));
  assert.equal(JSON.stringify(p.plan(item({ view: 'decode' }), ENV)),
    JSON.stringify([{ op: 'locateEvent', index: 178 }, { op: 'openDecode' }]));
  assert.equal(p.plan(item({ eventIndex: 240 }), ENV), null, 'event beyond graph');
  assert.equal(p.plan(item({ view: 'compass', ref: '不存在的人' }), ENV), null, 'compass character missing');
  assert.equal(p.plan(item(), null), null);
  assert.equal(p.plan(item(), {}), null);
});
test('jump plans stay in the resume op family: same vocabulary, same refusals, byte-equal compass op', () => {
  const { bookmark, resume } = boot();
  const bp = bookmark.pure, rp = resume.pure;
  const resumeOps = { playback: 1, setPlot: 1, seek: 1, seekEventAt: 1, openCompass: 1, regroup: 1 };
  const bookmarkOps = { locateEvent: 1, openDecode: 1 };
  for (const view of ['plot', 'compass', 'decode']) {
    const bm = bp.plan(item({ view, ref: view === 'compass' ? '孙悟空' : null }), ENV);
    bm.forEach(op => {
      assert.ok(resumeOps[op.op] || bookmarkOps[op.op], 'bookmarks op ' + op.op + ' is outside the resume family');
    });
  }
  const rs = rp.plan({ v: 1, at: 1, view: 'plot', compass: null, group: null, playback: 'events', cursor: null, eventIndex: 178, label: '' }, { nCh: 10, events: 240, chars: ENV.chars, groups: ['camp'] });
  const bs = bp.plan(item(), ENV);
  assert.equal(JSON.stringify(rs.filter(o => o.op === 'seekEventAt').map(o => o.index)), JSON.stringify(bs.filter(o => o.op === 'locateEvent').map(o => o.index)),
    'same event index drives both families to the same seek target');
  const rc = rp.plan({ v: 1, at: 1, view: 'compass', compass: '孙悟空', group: null, playback: 'chapters', cursor: null, eventIndex: null, label: '' }, { nCh: 10, events: 240, chars: ENV.chars, groups: ['camp'] });
  const bc = bp.plan(item({ view: 'compass', ref: '孙悟空' }), ENV);
  assert.equal(JSON.stringify(rc[0]), JSON.stringify(bc[1]), 'openCompass ops are byte-identical across both families');
  assert.equal(rp.plan({ v: 1, at: 1, view: 'plot', compass: null, group: null, playback: 'events', cursor: null, eventIndex: 240, label: '' }, { nCh: 10, events: 240, chars: ENV.chars }), null);
  assert.equal(bp.plan(item({ eventIndex: 240 }), ENV), null, 'out-of-range event refuses identically in both families');
  assert.equal(rp.plan({ v: 1, at: 1, view: 'compass', compass: '不存在的人', group: null, playback: 'chapters', cursor: null, eventIndex: null, label: '' }, { nCh: 10, events: 240, chars: ENV.chars }), null);
  assert.equal(bp.plan(item({ view: 'compass', ref: '不存在的人' }), ENV), null, 'unknown compass character refuses identically');
});
test('broken storage is tolerated: lists are empty and writes fail without throwing', () => {
  const sandbox = {
    localStorage: {
      getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); }
    }
  };
  vm.runInNewContext(SRC, sandbox);
  const bookmark = sandbox.CLSkyBookmarks;
  assert.equal(JSON.stringify(bookmark.list('alpha')), '[]');
  const r = bookmark.add('alpha', item());
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'storage');
  assert.equal(bookmark.stats().storage, false);
});
test('addDecision is the pure gate: exists before full, full before ok, never mutates input', () => {
  const { bookmark } = boot();
  const p = bookmark.pure;
  const empty = [];
  assert.equal(JSON.stringify(p.addDecision(empty, null)), JSON.stringify({ ok: false, reason: 'invalid' }));
  const one = [item()];
  assert.equal(JSON.stringify(p.addDecision(one, item({ at: 999 }))), JSON.stringify({ ok: false, reason: 'exists' }));
  const fifty = [];
  for (let i = 0; i < 50; i++) fifty.push(item({ eventIndex: i, title: 'x' }));
  assert.equal(JSON.stringify(p.addDecision(fifty, item({ eventIndex: 999, title: 'y' }))), JSON.stringify({ ok: false, reason: 'full' }));
  const decision = p.addDecision(empty, item());
  assert.equal(decision.ok, true);
  assert.equal(decision.items.length, 1);
  assert.equal(empty.length, 0, 'caller list untouched; pure function returns a new array');
});
console.log('BOOKMARKS ' + passed + '/' + passed);
