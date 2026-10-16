'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, '..', 'js/sky/sky-readscale.js'), 'utf8');
const CSS = fs.readFileSync(path.join(__dirname, '..', 'css/sky-reading.css'), 'utf8');
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

function fakeStorage(seed, opts) {
  const map = new Map(Object.entries(seed || {}));
  const boom = opts && opts.boom;
  return {
    getItem: k => { if (boom) throw new Error('denied'); return map.has(k) ? map.get(k) : null; },
    setItem: (k, v) => { if (boom) throw new Error('denied'); map.set(k, String(v)); },
    removeItem: k => { if (boom) throw new Error('denied'); map.delete(k); },
    raw: k => map.get(k)
  };
}
function boot(seed, opts) {
  const sandbox = { localStorage: fakeStorage(seed, opts) };
  vm.runInNewContext(SRC, sandbox);
  return { rs: sandbox.CLSkyReadScale, st: sandbox.localStorage };
}

test('module surface: constants, steps order, five steps spanning 0.85–1.4', () => {
  const { rs } = boot();
  assert.equal(rs.VERSION, '1');
  assert.equal(rs.KEY, 'castline.readscale');
  assert.equal(JSON.stringify(rs.STEPS), JSON.stringify([0.85, 1, 1.15, 1.3, 1.4]));
  assert.equal(rs.MIN, 0.85); assert.equal(rs.MAX, 1.4); assert.equal(rs.DEFAULT, 1);
});

test('clamp: out-of-range clamps to bounds, garbage falls back to 1.0', () => {
  const p = boot().rs.pure;
  assert.equal(p.clamp(0.5), 0.85);
  assert.equal(p.clamp(9), 1.4);
  assert.equal(p.clamp(NaN), 1);
  assert.equal(p.clamp(Infinity), 1);
  assert.equal(p.clamp(undefined), 1);
  assert.equal(p.clamp('1.3'), 1.3);
  assert.equal(p.clamp('junk'), 1);
  assert.equal(p.clamp(1.15), 1.15);
});

test('parse: stored text inside the step range parses, everything else self-heals to null', () => {
  const p = boot().rs.pure;
  assert.equal(p.parse('1.15'), 1.15);
  assert.equal(p.parse('0.85'), 0.85);
  assert.equal(p.parse('1.4'), 1.4);
  assert.equal(p.parse('1.0'), 1);
  for (const bad of ['garbage', '', '{}', '2', '0.5', 'NaN', 'Infinity', '1.4000001', null, undefined, 12]) {
    assert.equal(p.parse(bad), null, 'expected null for ' + JSON.stringify(bad));
  }
});

test('stepOf: nearest step, midpoint resolves to the lower step', () => {
  const p = boot().rs.pure;
  assert.equal(p.stepOf(1), 1);
  assert.equal(p.stepOf(0.85), 0);
  assert.equal(p.stepOf(1.4), 4);
  assert.equal(p.stepOf(1.4 + 0.01), 4);
  assert.equal(p.stepOf(0.9), 0);
  assert.equal(p.stepOf(1.24), 3);
  assert.equal(p.stepOf(1.225), 2);
});

test('fmt: percentage display for the reset button and live region', () => {
  const p = boot().rs.pure;
  assert.equal(p.fmt(0.85), '85%');
  assert.equal(p.fmt(1), '100%');
  assert.equal(p.fmt(1.15), '115%');
  assert.equal(p.fmt(1.3), '130%');
  assert.equal(p.fmt(1.4), '140%');
});

test('apply path: the only write is --cl-reading-scale on the shell body', () => {
  const p = boot().rs.pure;
  const calls = [];
  const body = { style: { setProperty: (k, v) => calls.push([k, v]) } };
  assert.equal(p.apply(body, 1.3), true);
  assert.equal(JSON.stringify(calls), JSON.stringify([['--cl-reading-scale', '1.3']]));
  assert.equal(p.apply(body, 99), true);
  assert.equal(JSON.stringify(calls[1]), JSON.stringify(['--cl-reading-scale', '1.4']));
  assert.equal(p.apply(null, 1), false);
  assert.equal(p.apply({}, 1), false);
});

test('fresh boot defaults to 1.0 without touching storage', () => {
  const { rs, st } = boot();
  assert.equal(rs.current(), 1);
  assert.equal(st.raw('castline.readscale'), undefined);
});

test('set persists and reload restores the stored step', () => {
  const first = boot();
  first.rs.set(1.15);
  assert.equal(first.st.raw('castline.readscale'), '1.15');
  assert.equal(first.rs.current(), 1.15);
  const second = boot({ 'castline.readscale': first.st.raw('castline.readscale') });
  assert.equal(second.rs.current(), 1.15);
  assert.equal(second.rs.stats().selfHeals, 0);
});

test('cross-work sharing is by design: single key, no work-key suffix in the module', () => {
  const { rs } = boot();
  assert.equal(rs.KEY.indexOf('.'), 'castline'.length);
  assert.ok(!SRC.includes('keyFor'), 'no per-work key derivation');
  assert.ok(!SRC.includes('CLApp.key'), 'does not read the work key');
});

test('corruption self-heal: junk key is removed at boot and value returns to 1.0', () => {
  const { rs, st } = boot({ 'castline.readscale': 'junk' });
  assert.equal(rs.current(), 1);
  assert.equal(st.raw('castline.readscale'), undefined);
  assert.equal(rs.stats().selfHeals, 1);
});

test('corruption self-heal: out-of-range stored values heal the same way', () => {
  for (const raw of ['9', '0.01', 'Infinity']) {
    const { rs, st } = boot({ 'castline.readscale': raw });
    assert.equal(rs.current(), 1, raw);
    assert.equal(st.raw('castline.readscale'), undefined, raw);
    assert.equal(rs.stats().selfHeals, 1, raw);
  }
});

test('button stepping walks the five steps and stops at both ends', () => {
  const { rs } = boot();
  assert.equal(rs.stepBy(-1), 0.85);
  assert.equal(rs.stepBy(-1), 0.85);
  assert.equal(rs.stepBy(1), 1);
  assert.equal(rs.stepBy(1), 1.15);
  assert.equal(rs.stepBy(1), 1.3);
  assert.equal(rs.stepBy(1), 1.4);
  assert.equal(rs.stepBy(1), 1.4);
  assert.equal(rs.reset(), 1);
});

test('set() clamps continuous input; the next step lands on a real step', () => {
  const { rs } = boot();
  rs.set(1.37);
  assert.equal(rs.current(), 1.37);
  assert.equal(rs.stepBy(1), 1.4);
  assert.equal(rs.stepBy(-1), 1.3);
  rs.set(0.01);
  assert.equal(rs.current(), 0.85);
});

test('unavailable storage never throws and keeps the in-memory value', () => {
  const { rs } = boot({}, { boom: true });
  assert.equal(rs.stats().storage, false);
  assert.equal(rs.set(1.3), 1.3);
  assert.equal(rs.current(), 1.3);
  assert.equal(rs.reset(), 1);
});

test('CSS mechanism: token cascade on the three prose containers, never zoom/transform', () => {
  const mech = CSS.slice(CSS.indexOf('--cl-reading-scale'));
  assert.ok(mech.includes('.sky-decon-panel .sd-scroll'), 'decon body container');
  assert.ok(mech.includes('.sky-search-panel .sks-detail'), 'evidence/search detail container');
  assert.ok(mech.includes('.sky-story-panel .ssp-body'), 'story panel body container');
  for (const tok of ['--skd-fs-sm', '--skd-fs-base', '--skd-fs-md', '--skd-fs-lg']) {
    assert.ok(mech.includes(tok + ': calc(var(--cl-rfs-'), 'scaled token ' + tok);
  }
  assert.ok(/max\(var\(--cl-rfs-xs\), calc\(/.test(mech), 'xs floor keeps the >=11px minimum step');
  const block = mech.slice(0, mech.indexOf('#skyPlayer .cl-rs'));
  assert.ok(!/\bzoom\s*:/.test(block), 'no zoom in the mechanism');
  assert.ok(!/transform\s*:/.test(block), 'no transform scaling in the mechanism');
});

test('CSS entry group reuses the 44px sky-speed chrome and exposes a live region slot', () => {
  assert.ok(CSS.includes('#skyPlayer .cl-rs'), 'player-bar group styles exist');
  assert.ok(SRC.includes("className = 'ssp-live'"), 'live region reuses the visually-hidden reading class');
  assert.ok(SRC.includes("'sky-speed'"), 'buttons reuse the 44px chrome class');
});

console.log('sky_readscale_contract: ' + passed + ' passed');
