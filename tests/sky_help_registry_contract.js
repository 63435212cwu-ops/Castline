'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const keysSrc = fs.readFileSync(path.join(ROOT, 'js/keys.js'), 'utf8');
const shellSrc = fs.readFileSync(path.join(ROOT, 'js/sky/sky-shell.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

let count = 0;
function check(name, cond) {
  assert.ok(cond, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

function stubEl() {
  return {
    setAttribute() {}, removeAttribute() {}, appendChild() {}, insertBefore() {},
    addEventListener() {}, focus() {}, click() {}, querySelector() { return null; },
    querySelectorAll() { return []; }, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    style: {}, dataset: {}, hidden: false, innerHTML: '', textContent: ''
  };
}
const idMap = Object.create(null);
const docStub = {
  getElementById: id => idMap[id] || null,
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => stubEl(),
  body: stubEl(),
  head: stubEl()
};
const G = {
  console,
  setTimeout: () => 0, clearTimeout: () => {},
  Event: function () {}, CustomEvent: function () {},
  document: docStub,
  addEventListener: () => {},
  CLScene: { create: () => ({  }) }
};
G.window = G;
const ctx = vm.createContext(G);
vm.runInContext(keysSrc, ctx, { filename: 'js/keys.js' });
G.CLScene.create();
const K = G.CLKeys;

check('executing js/keys.js in a stub vm exposes the CLKeys probe with map and helpModel',
  !!K && Array.isArray(K.map) && K.map.length > 10 && typeof K.helpModel === 'function');

const firstModel = K.helpModel();
check('help model groups preserve the registry group order without inventing groups',
  (() => {
    const regOrder = [];
    K.map.forEach(m => { if (regOrder.indexOf(m.g) < 0 && K.alive(m)) regOrder.push(m.g); });
    return JSON.stringify(firstModel.groups.map(g => g.name)) === JSON.stringify(regOrder);
  })());

check('every rendered shortcut row comes from an alive registry entry (no hardcoded rows)',
  (() => {
    const aliveN = K.map.filter(m => K.alive(m)).length;
    const rowsN = firstModel.groups.reduce((n, g) => n + g.entries.length, 0);
    return rowsN === aliveN && aliveN > 10;
  })());

check('registry entries all carry group + key + label (the table cannot silently drop a column)',
  K.map.every(m => typeof m.g === 'string' && m.g.length > 0 && typeof m.k === 'string' && m.k.length > 0 && typeof m.label === 'string' && m.label.length > 0));

check('entries gated on the event/focus layers are absent while those layers are missing',
  (() => {
    const flat = firstModel.groups.reduce((a, g) => a.concat(g.entries), []);
    return !flat.some(e => e.k === '1-7') && !flat.some(e => e.k === ',') && !flat.some(e => e.k === 'A');
  })());

check('stubbing the event layer ON makes its registry entries appear in the very next model',
  (() => {
    G.CLTreeEvents = { pick() {}, get() { return {}; } };
    const flat = K.helpModel().groups.reduce((a, g) => a.concat(g.entries), []);
    return flat.some(e => e.k === ',') && flat.some(e => e.k === 'A');
  })());

check('stubbing the focus layer ON surfaces its 1-7 entry, and removing it hides it again',
  (() => {
    G.CLTreeFocus = { set() {} };
    const withFocus = K.helpModel().groups.reduce((a, g) => a.concat(g.entries), []);
    G.CLTreeFocus = undefined;
    G.CLTreeEvents = undefined;
    const without = K.helpModel().groups.reduce((a, g) => a.concat(g.entries), []);
    return withFocus.some(e => e.k === '1-7') && !without.some(e => e.k === '1-7') && !without.some(e => e.k === ',');
  })());

function viewWith(state) {
  G.CLSky = state == null ? undefined : { enabled: () => state !== 'off', state: () => state };
  return K.viewHelp();
}
const vCon = viewWith({ mode: 'constellation', plot: false, compass: null, playing: false, cursor: null });
const vPlot = viewWith({ mode: 'constellation', plot: true, compass: null, playing: true, cursor: 3 });
const vCom = viewWith({ mode: 'compass', plot: false, compass: '测试甲', playing: false, cursor: null });
const vOff = viewWith(null);

check('the four shell states produce four distinct help sections',
  vCon.key === 'constellation' && vPlot.key === 'plot' && vCom.key === 'compass' && vOff.key === 'legacy' &&
  JSON.stringify(vCon.lines) !== JSON.stringify(vPlot.lines) &&
  JSON.stringify(vPlot.lines) !== JSON.stringify(vCom.lines) &&
  JSON.stringify(vCon.lines) !== JSON.stringify(vCom.lines));

check('the plot section reflects the real playing state and cursor, not canned copy',
  vPlot.lines.some(l => /暂停/.test(l)) && vPlot.lines.some(l => /第 4 回/.test(l)) &&
  !viewWith({ mode: 'constellation', plot: true, compass: null, playing: false, cursor: null }).lines.some(l => /暂停播放/.test(l)));

check('the compass section names the actual character from shell state',
  vCom.title.indexOf('测试甲') >= 0);

check('the legacy (atlas shell) section is derived from registry keys, not a hardcoded list',
  vOff.key === 'legacy' && vOff.lines.length >= 3 && vOff.lines.every(l => /^.+ = .+/.test(l)));

G.CLSky = undefined;

check('with an empty DOM stub the panels section is honestly empty (no fabricated entries)',
  K.panelsHelp().length === 0);

check('a probed element appearing in the DOM yields a line whose key comes from the registry',
  (() => {
    idMap.btnLib = stubEl();
    const lines = K.panelsHelp();
    return lines.length === 1 && lines[0].name === '作品库' && /按 H/.test(lines[0].text);
  })());

check('removing the registry key degrades the line to the button path instead of fabricating the key',
  (() => {
    const entry = K.map.filter(m => m.k === 'H')[0];
    if (!entry) return false;
    entry.k = 'H-renamed-away';
    const degraded = K.panelsHelp()[0];
    entry.k = 'H';
    const restored = K.panelsHelp()[0];
    return !/按 H/.test(degraded.text) && /作品库」/.test(degraded.text) && /按 H/.test(restored.text);
  })());

const allJs = ['js', 'js/sky', 'js/hud', 'js/atlas', 'js/core'].map(d => {
  const dir = path.join(ROOT, d);
  if (!fs.existsSync(dir)) return '';
  return fs.readdirSync(dir).filter(f => f.endsWith('.js'))
    .map(f => fs.readFileSync(path.join(dir, f), 'utf8')).join('\n');
}).join('\n');
const probeIds = Array.from(keysSrc.matchAll(/\{ id: '([\w-]+)', name:/g)).map(m => m[1]);
check('the panel probe table registers a non-trivial set of ids (' + probeIds.length + ')',
  probeIds.length >= 4);
probeIds.forEach(id => {
  check('panel probe #' + id + ' still names an element that exists in the real source',
    indexHtml.includes('id="' + id + '"') ||
    allJs.includes("'" + id + "'") || allJs.includes('"' + id + '"') || allJs.includes('id="' + id + '"'));
});

check('the help layer is a labelled modal dialog in the source contract',
  /setAttribute\('role', 'dialog'\)/.test(keysSrc) &&
  /setAttribute\('aria-modal', 'true'\)/.test(keysSrc) &&
  /setAttribute\('aria-labelledby', 'clKeysTitle'\)/.test(keysSrc) &&
  /id="clKeysTitle"/.test(keysSrc));

check('render() consumes helpModel() — display and contract share one data source',
  /function render\(\)[\s\S]{0,200}helpModel\(\)/.test(keysSrc));

check('the shortcut table renders rows from registry groups via helpModel entries',
  /g\.entries\.forEach/.test(keysSrc) && /model\.groups\.forEach/.test(keysSrc));

check('dispatch and the help table share one availability predicate (alive)',
  /if \(!alive\(m\)\) continue/.test(keysSrc) && /if \(!alive\(m\)\) return/.test(keysSrc));

check('reduced-motion and narrow-viewport rules ship with the panel styles',
  /prefers-reduced-motion/.test(keysSrc) && /max-width:560px/.test(keysSrc));

check('the sky shell toolbar mounts the help button through the public probe',
  /CLKeys\.mountHelpButton/.test(shellSrc));

check('the ? registry entry still opens this very layer (single owner, no second help panel)',
  K.map.some(m => m.k === '?' && m.g === '面板' && typeof m.run === 'function'));

console.log('SKY HELP REGISTRY CONTRACT PASS · ' + count + ' checks');
