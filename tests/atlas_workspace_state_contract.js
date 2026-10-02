/* Reversible atlas workspace regression tests.
 * Run in this workspace (node is not on the default PATH):
 * /Users/carmen/.workbuddy/binaries/node/versions/22.22.2-3/bin/node tests/atlas_workspace_state_contract.js
 * Uses the real atlas state/session, real label search-state and GemSVG pause
 * APIs, and the actual CLApp.atlas object extracted from app.js. Only DOM,
 * camera, orbit/stage plumbing and timers are in-memory doubles. No network,
 * user storage, WebGL context or runtime source mutation is performed.
 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(ROOT, file), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));
const cases = [];
function test(name, fn) { cases.push([name, fn]); }

function classList() {
  const values = new Set();
  return { add(...items) { items.forEach(v => values.add(v)); }, remove(...items) { items.forEach(v => values.delete(v)); },
    contains(value) { return values.has(value); }, toggle(value, on) {
      on = on === undefined ? !values.has(value) : !!on;
      if (on) values.add(value); else values.delete(value);
      return on;
    } };
}
function target() {
  const handlers = new Map();
  return { addEventListener(type, handler) {
    if (!handlers.has(type)) handlers.set(type, []);
    handlers.get(type).push(handler);
  }, removeEventListener(type, handler) {
    handlers.set(type, (handlers.get(type) || []).filter(fn => fn !== handler));
  }, dispatchEvent(event) {
    if (!event.target) event.target = this;
    (handlers.get(event.type) || []).slice().forEach(fn => fn.call(this, event));
    return true;
  }, handlerCount(type) { return (handlers.get(type) || []).length; } };
}
function element(tag = 'div') {
  const attributes = new Map();
  return Object.assign(target(), { tagName: tag.toUpperCase(), classList: classList(), dataset: {}, style: {},
    hidden: true, value: '', textContent: '', innerHTML: '', isConnected: true, children: [],
    selectedOptions: [{ text: '阵营' }],
    setAttribute(key, value) { attributes.set(key, String(value)); }, getAttribute(key) { return attributes.get(key) || null; },
    querySelectorAll() { return []; }, querySelector() { return null; },
    appendChild(child) { this.children.push(child); child.parentNode = this; return child; },
    replaceChildren(...children) { this.children = children; },
    remove() { this.isConnected = false; }, focus() { this.focused = true; },
    click() { this.dispatchEvent({ type: 'click', preventDefault() {}, stopPropagation() {}, target: this }); }
  });
}
class Vector {
  constructor(values = [0, 0, 0]) { this.values = values.slice(); }
  toArray() { return this.values.slice(); }
  fromArray(values) { this.values = Array.from(values); return this; }
}
class Event {
  constructor(type, options = {}) { this.type = type; Object.assign(this, options); }
  preventDefault() {}
  stopPropagation() {}
  stopImmediatePropagation() {}
}

function fixture() {
  return { title: '回归星海', meta: { graph_key: 'workspace-fixture' },
    characters: [{ id: 0, entityId: 0, name: '甲', attrs: {} }, { id: 'beta', name: '乙', attrs: {} }],
    events: [{ id: 0, order: 1, chapter: '首章', title: '出发', characters: ['甲'] },
      { id: 'later', order: 2, chapter: '终章', title: '归来', characters: ['乙'] }],
    storylines: [{ id: 0, name: '归途', events: [1, 2], kind: '主线' }] };
}

function setup() {
  const elements = new Map(), intervals = new Map();
  let nextTimer = 0, chapter = null, face = 'top', calm = false, sceneLayer = 'overview', unfolded = false;
  let plot = false, thread = null, focusEvent = -1, orbitPaused = false, gemOn = false, stageFocus = null;
  const doc = Object.assign(target(), {
    body: element('body'), documentElement: element('html'), hidden: false, activeElement: element('button'),
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    createElement: element, createElementNS(_ns, tag) { return element(tag); }, querySelector() { return null; }
  });
  const context = Object.assign(target(), { console, document: doc, innerWidth: 1280, innerHeight: 900,
    location: { search: '' }, URLSearchParams, Event, CustomEvent: Event, THREE: { Vector3: Vector },
    navigator: { hardwareConcurrency: 8 }, matchMedia: () => ({ matches: false }),
    performance: { now: () => 0 }, requestAnimationFrame() { throw new Error('No render loop expected in this state contract'); }, cancelAnimationFrame() {},
    setInterval(fn) { const id = ++nextTimer; intervals.set(id, fn); return id; }, clearInterval(id) { intervals.delete(id); },
    setTimeout() { throw new Error('No asynchronous side effect expected in this state contract'); },
    fetch() { throw new Error('Network forbidden'); },
    localStorage: { getItem() { return null; }, setItem() { throw new Error('User storage write forbidden'); } }
  });
  context.window = context;
  context.G = fixture();
  context.AtlasModel = { ok: true };
  context.sel = null;
  context.infoLayer = 'overview';
  context.orbitView = { visible: () => plot, state: () => ({ thread, focusEv: focusEvent }),
    setMode(mode) { plot = mode === 'plot'; }, focusThread(id) { thread = id; }, focusEvent(index) { focusEvent = index; },
    motionPaused: () => orbitPaused, setMotionPaused(value) { orbitPaused = !!value; }
  };
  context.scene = {
    camera: { position: new Vector([1, 2, 3]), quaternion: new Vector([0, 0, 0, 1]), zoom: 1, view: null, aspect: 1280 / 900,
      setViewOffset(fullWidth, fullHeight, offsetX, offsetY, width, height) {
        this.aspect = fullWidth / fullHeight;
        this.view = { enabled: true, fullWidth, fullHeight, offsetX, offsetY, width, height };
      },
      clearViewOffset() { if (this.view) this.view.enabled = false; }, updateProjectionMatrix() {} },
    controls: { target: new Vector([4, 5, 6]) },
    chapSel: () => chapter, face: () => face, calm: () => calm,
    selectChapter(value) { chapter = value; }, setFace(value) { face = value; }, setCalm(value) { calm = !!value; },
    setInfoLayer(value) { sceneLayer = value; }, setHudSelector() {},
    flyTo(position, destination) { this.camera.position.fromArray(position.toArray()); this.controls.target.fromArray(destination.toArray()); },
    gemStage(options) { if (options.on !== undefined) gemOn = !!options.on; }, gemStageState: () => ({ on: gemOn }), previewCrown() {}
  };
  context.plotOrbitReady = () => true;
  context.byName = name => context.G.characters.find(c => c.name === name);
  context.deselect = () => { context.sel = null; };
  context.select = name => { context.sel = name; };
  context.setInfoLayer = layer => { context.infoLayer = layer; context.scene.setInfoLayer(layer); };
  context.showPlotTextTree = () => {};
  context.syncSafeArea = () => {};
  context.CLAtlasStage = { isOn: () => unfolded,
    open() { unfolded = true; doc.dispatchEvent(new Event('cl:atlas-stage', { detail: { on: true } })); },
    close() { unfolded = false; doc.dispatchEvent(new Event('cl:atlas-stage', { detail: { on: false } })); },
    setFocus(value) { stageFocus = value; }
  };
  context.CLApp = { graph: () => context.G, scene: () => context.scene,
    story: () => ({ threads: [{ id: 'runtime-main', sourceId: 0, title: '归途', events: [0, 1], lead: '甲' }] }) };
  vm.createContext(context);
  function load(file) { vm.runInContext(read(file), context, { filename: file }); }
  load('js/core/scene-lod-labels.js');
  const labels = context.CLSceneLodLabels.create({ getNodes: () => [], getNodeByKey: () => ({}), getNCharCount: () => 0 });
  context.scene.setSearchSet = labels.setSearchSet;
  context.scene.searchNames = labels.searchNames;
  assert.strictEqual(typeof context.scene.searchNames, 'function', 'real label manager must expose reversible search state');
  load('js/gem/gem-morph.js');
  load('js/gem/gem-svg.js');
  context.CLGemMount = { setPaused: value => context.CLGemSVG.setPaused(value), setChapter() {} };
  const app = read('js/app.js'), begin = app.indexOf('    atlas: {', app.indexOf('  window.CLApp = {'));
  const end = app.indexOf('\n    // 只读预览', begin);
  assert(begin >= 0 && end > begin, 'test must execute actual CLApp.atlas, not a handwritten replacement');
  const bridgeSource = app.slice(begin + '    atlas: '.length, end).trim().replace(/,$/, '');
  vm.runInContext('CLApp.atlas = ' + bridgeSource, context, { filename: 'js/app.js#CLApp.atlas' });
  load('js/atlas/atlas-state.js');
  load('js/atlas/atlas-preview-session.js');
  return { context, doc, labels, P: context.CLAtlasPreview, S: context.CLAtlasState,
    el: id => doc.getElementById(id), timerCount: () => intervals.size,
    read: () => ({ chapter, face, calm, sceneLayer, unfolded, stageFocus, orbitPaused,
      searchNames: plain(context.scene.searchNames()), svgPaused: context.CLGemSVG.stats().paused }) };
}

test('closed preview history never revives a session with no origin snapshot', () => {
  const t = setup();
  t.P.open(); t.P.setAtlas('annulus'); t.P.close();
  assert.strictEqual(t.P.state().preview, false);
  assert.strictEqual(t.P.stats().history, 0);
  t.P.back();
  assert.strictEqual(t.P.state().preview, false);
  assert.strictEqual(t.doc.body.classList.contains('atlas-preview-open'), false);
});
test('preview keeps its own history while preserving the pre-preview navigation stack', () => {
  const t = setup();
  t.P.setAtlas('annulus');
  assert.strictEqual(t.P.stats().history, 1);
  t.P.open();
  assert.strictEqual(t.P.stats().history, 0);
  t.P.setAtlas('domains'); t.P.chooseCharacter('甲');
  assert.strictEqual(t.P.stats().history, 2);
  t.P.close();
  assert.strictEqual(t.P.state().view, 'annulus');
  assert.strictEqual(t.P.stats().history, 1);
  t.P.back();
  assert.strictEqual(t.P.state().view, 'domains');
  assert.strictEqual(t.P.state().preview, false);
});
test('an originally unfolded annulus is restored after a preview view switch', () => {
  const t = setup();
  t.P.setAtlas('annulus'); t.context.CLApp.atlas.line('runtime-main'); t.context.CLAtlasStage.open();
  assert.strictEqual(t.P.snapshot().bridge.unfolded, true);
  t.P.open(); t.P.setAtlas('domains');
  assert.strictEqual(t.read().unfolded, false);
  t.P.close();
  assert.strictEqual(t.read().unfolded, true);
  assert.strictEqual(t.P.state().pose, 'unfolded');
  assert.strictEqual(t.read().stageFocus.lineId, 'runtime-main');
});
test('a preview-only unfolded stage does not survive closing the preview', () => {
  const t = setup();
  t.P.open(); t.context.CLAtlasStage.open(); t.P.close();
  assert.strictEqual(t.read().unfolded, false);
  assert.strictEqual(t.P.state().pose, 'orbital');
});
test('seeking in domains restores an originally empty label-search set', () => {
  const t = setup();
  t.P.open(); t.P.setCursor(0);
  assert.deepStrictEqual(t.read().searchNames, ['甲']);
  t.P.close();
  assert.strictEqual(t.P.state().cursor, null);
  assert.strictEqual(t.read().searchNames, null);
});
test('pre-existing label-search names survive preview and getters are defensive', () => {
  const t = setup();
  t.context.scene.setSearchSet(['乙']);
  const names = t.context.scene.searchNames(); names.push('甲');
  assert.deepStrictEqual(t.read().searchNames, ['乙']);
  t.P.open(); t.P.setCursor(0); t.P.close();
  assert.deepStrictEqual(t.read().searchNames, ['乙']);
});
test('temporary reduced motion restores real GemSVG pause and orbit flags', () => {
  const t = setup();
  t.P.open(); t.el('aphReduced').click();
  assert.strictEqual(t.read().svgPaused, true); assert.strictEqual(t.read().orbitPaused, true);
  t.P.close();
  assert.strictEqual(t.P.state().reduced, false);
  assert.strictEqual(t.read().svgPaused, false); assert.strictEqual(t.read().orbitPaused, false);
  assert.strictEqual(t.read().calm, false);
});
test('an originally paused workspace remains paused after temporary preview animation', () => {
  const t = setup();
  t.el('aphReduced').click();
  t.P.open(); t.el('aphReduced').click();
  assert.strictEqual(t.read().svgPaused, false);
  t.P.close();
  assert.strictEqual(t.P.state().reduced, true);
  assert.strictEqual(t.read().svgPaused, true); assert.strictEqual(t.read().orbitPaused, true);
  assert.strictEqual(t.read().calm, true);
});
test('zero IDs resolve by type and remain zero when selecting a character', () => {
  const t = setup();
  assert.strictEqual(t.S.entity('character', 0).name, '甲');
  assert.strictEqual(t.S.entity('event', 0).title, '出发');
  assert.strictEqual(t.S.entity('line', 0).name, '归途');
  assert.strictEqual(t.P.chooseCharacter(0), true);
  assert.strictEqual(t.P.state().selected.id, 0);
  t.S.dispatch({ type: 'peer', id: 0 });
  assert.strictEqual(t.S.get().peer, 0);
});
test('zero source storyline ID remains distinct from its renderer runtime ID', () => {
  const t = setup();
  assert.strictEqual(t.P.chooseLine('runtime-main'), true);
  assert.strictEqual(t.P.state().selected.runtimeId, 'runtime-main');
  assert.strictEqual(t.P.state().selected.id, 0);
  t.S.dispatch({ type: 'select', entity: null });
  t.doc.dispatchEvent(new Event('cl:plot-thread', { detail: { id: 'runtime-main' } }));
  assert.strictEqual(t.P.state().selected.id, 0, 'plot-thread event must preserve the same source ID as direct navigation');
});
test('repeated preview restore never writes the graph or leaves a playback interval', () => {
  const t = setup(), before = JSON.stringify(t.context.G), listeners = t.S.stats().listeners;
  for (let i = 0; i < 5; i++) {
    t.P.open(); t.P.setAtlas('annulus'); t.P.play();
    assert.strictEqual(t.timerCount(), 1);
    t.P.close();
    assert.strictEqual(t.timerCount(), 0);
    assert.strictEqual(t.P.state().preview, false);
  }
  assert.strictEqual(JSON.stringify(t.context.G), before);
  assert.strictEqual(t.S.stats().listeners, listeners);
});

test('camera lens snapshots are independent and restore proportional to the current viewport', () => {
  const t = setup(), camera = t.context.scene.camera;
  camera.setViewOffset(1280, 900, -50, 30, 1280, 900);
  const snap = t.P.snapshot();
  camera.view.offsetY = 999;
  assert.strictEqual(snap.camera.view.offsetY, 30);
  t.context.innerWidth = 640; t.context.innerHeight = 1200;
  assert.strictEqual(t.P.restore(snap), true);
  assert.deepStrictEqual(plain(camera.view), { enabled: true, fullWidth: 640, fullHeight: 1200, offsetX: -25, offsetY: 40, width: 640, height: 1200 });
  assert.deepStrictEqual(plain(snap.camera.viewport), { width: 1280, height: 900 });
});

test('legacy camera state clears a lens left by the outgoing crystal', () => {
  const t = setup(), camera = t.context.scene.camera, snap = t.P.snapshot();
  delete snap.camera.view; delete snap.camera.viewport;
  camera.setViewOffset(1280, 900, -50, 30, 1280, 900);
  assert.strictEqual(t.P.restore(snap), true);
  assert.strictEqual(camera.view.enabled, false);
  assert.strictEqual(camera.aspect, 1280 / 900);
});

test('preview exit restores an explicitly empty domain solo', () => {
  const t = setup(); let selection = { lineId: null, characterName: null };
  t.context.CLDomainsInteract = {
    getSelection: () => ({ ...selection }),
    setSelection: next => { selection = { lineId: next.lineId == null ? null : next.lineId, characterName: next.characterName || null }; }
  };
  t.P.open();
  t.context.CLDomainsInteract.setSelection({ lineId: 'preview-only', characterName: null });
  t.P.close();
  assert.deepStrictEqual(selection, { lineId: null, characterName: null });
});

test('preview exit preserves a domain selection not represented by the orbit thread', () => {
  const t = setup(); let selection = { lineId: 'domain-before', characterName: null };
  t.context.CLDomainsInteract = {
    getSelection: () => ({ ...selection }),
    setSelection: next => { selection = { lineId: next.lineId == null ? null : next.lineId, characterName: next.characterName || null }; }
  };
  t.P.open();
  t.context.CLDomainsInteract.setSelection({ lineId: null, characterName: null });
  t.P.close();
  assert.deepStrictEqual(selection, { lineId: 'domain-before', characterName: null });
});

let failed = 0;
for (const [name, fn] of cases) {
  try { fn(); console.log('PASS ' + name); }
  catch (error) { failed++; console.error('FAIL ' + name + '\n' + error.stack); }
}
console.log('\n' + (cases.length - failed) + '/' + cases.length + ' atlas workspace state checks passed');
process.exitCode = failed ? 1 : 0;
