'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../js/sky/sky-chrome.js'), 'utf8');
const start = source.indexOf('  var insetRO = null');
const end = source.indexOf('  /* ================================================================ 接线 */', start);
assert(start >= 0 && end > start, 'inset unit remains extractable');

let operations = [], classes = 0, observed = [];
const targets = Object.create(null);
function consumer(id) {
  const values = Object.create(null);
  return { id, style: {
    getPropertyValue(key) { return values[key] || ''; },
    setProperty(key, value) { operations.push(['write', id, key, value]); values[key] = value; }
  }};
}
function box(id, height, top, bottom, hidden) {
  return { id, height, top, bottom, hidden: !!hidden,
    get offsetHeight() { operations.push(['read', id, 'height']); return this.height; },
    getBoundingClientRect() { operations.push(['read', id, 'rect']); return { top: this.top, bottom: this.bottom }; }
  };
}
let bar = box('bar', 60, 0, 60.6);
let bottom = { children: [box('shown', 30, 1021.4, 1050), box('hidden', 20, 800, 820, true), box('zero', 0, 600, 600)] };
const d = { querySelector(selector) { return selector === '.sky-top' ? bar : bottom; } };
const g = { innerHeight: 1080, ResizeObserver: function (callback) { this.callback = callback; this.observe = el => observed.push(el); } };
const api = Function('d', 'g', '$', 'syncMenuToBody', source.slice(start, end) +
  '\nreturn {sync:syncInsets,publish:publishInsets,changed:onBodyChange,watch:watchInsets};')(
  d, g, id => targets[id] || null, () => { classes++; });
function sync() {
  operations = []; api.sync();
  const firstWrite = operations.findIndex(x => x[0] === 'write');
  assert(firstWrite < 0 || !operations.slice(firstWrite).some(x => x[0] === 'read'), 'all geometry reads precede style writes');
}
function value(id, token) { return targets[id].style.getPropertyValue('--sky-chrome-' + token); }

sync(); assert(!operations.some(x => x[0] === 'write'));
['attach', 'runbar', 'toast'].forEach(id => { targets[id] = consumer(id); });
operations = []; api.changed([{ type: 'childList' }]);
assert.deepStrictEqual(operations.map(x => x[1]), ['attach', 'runbar', 'toast']);
assert.strictEqual(value('attach', 'top'), '61px');
assert.strictEqual(value('runbar', 'bottom'), '59px');
assert.strictEqual(value('toast', 'bottom'), '59px');
assert.strictEqual(classes, 0, 'insertion does not rerun menu synchronization');
assert(!operations.some(x => x[0] === 'read'), 'late consumers use cached measurements without forcing layout');

sync(); assert(!operations.some(x => x[0] === 'write'), 'unchanged measurements make no style writes');
const old = targets.toast; targets.toast = consumer('toast');
operations = []; api.changed([{ type: 'childList' }, { type: 'attributes' }]);
assert.deepStrictEqual(operations, [['write', 'toast', '--sky-chrome-bottom', '59px']]);
assert.strictEqual(classes, 1, 'body class changes still synchronize the menu');
assert.strictEqual(old.style.getPropertyValue('--sky-chrome-bottom'), '59px');

bar.bottom = 80.2; bottom.children[0].top = 991.8;
sync(); assert.strictEqual(value('attach', 'top'), '80px');
assert.strictEqual(value('runbar', 'bottom'), '88px');
assert.strictEqual(value('toast', 'bottom'), '88px');
assert.strictEqual(operations.filter(x => x[0] === 'write').length, 3);

bottom.children[0].hidden = true;
sync(); assert.strictEqual(value('runbar', 'bottom'), '16px', 'empty footer preserves original minimum');
bar.height = 0; bar.bottom = 12;
sync(); assert.strictEqual(value('attach', 'top'), '80px', 'hidden top bar retains its previous inset');
bar = null; bottom = null;
sync(); assert(!operations.some(x => x[0] === 'write'), 'temporarily absent chrome retains prior measurements');
bar = box('bar', 42, 0, 42); bottom = { children: [box('footer', 25, 715, 750)] }; g.innerHeight = 768;
sync(); assert.strictEqual(value('attach', 'top'), '42px');
assert.strictEqual(value('toast', 'bottom'), '53px', 'resize uses the new viewport height');
api.watch(); api.watch(); assert.deepStrictEqual(observed, [bar, bottom], 'existing observer remains single');

const disabled = { document: { body: {}, documentElement: {}, addEventListener() {} }, CLSky: { enabled: () => false },
  matchMedia: () => ({ matches: true }) };
vm.runInNewContext(source, { window: disabled }, { filename: 'sky-chrome.js' });
assert.strictEqual(disabled.CLSkyChrome.enabled(), false);
console.log('SKY-CHROME-INSETS OK: scoped writes, batching, unchanged values, late/replaced consumers, resize, and legacy exit');
