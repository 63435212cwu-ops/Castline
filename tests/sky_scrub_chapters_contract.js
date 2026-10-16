'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const code = fs.readFileSync('js/sky/sky-shell-player.js', 'utf8');
function addDom(X) {
  const nodes = new Map();
  function element(id = '') {
    const el = {id, childNodes: [], hidden: false, listeners: {}, attrs: {}, style: {setProperty() {}}, focus() {},
      appendChild(child) {this.childNodes.push(child); return child;},
      addEventListener(name, fn) {this.listeners[name] = fn;},
      setAttribute(name, value) {this.attrs[name] = String(value);}, getAttribute(name) {return this.attrs[name];},
      querySelector(selector) {const key = 'selector:' + selector; if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key);}};
    let html = '', text = '';
    Object.defineProperty(el, 'innerHTML', {get() {return html;}, set(value) {html = value; for (const match of value.matchAll(/\bid="([^"]+)"/g)) if (!nodes.has(match[1])) nodes.set(match[1], element(match[1]));}});
    Object.defineProperty(el, 'textContent', {get() {return text;}, set(value) {text = value; if (value === '') el.childNodes = [];}});
    if (id) nodes.set(id, el); return el;
  }
  X.doc = {hidden: false, createElement() {return element();}, createElementNS() {return element();}, getElementById(id) {return nodes.get(id);}};
  X.hud = element('hud'); X.el.skyPlay.focus = function () {};
}
function make(extra) {
  let cursor = null;
  const g = {Date: {now() {return 0;}}, setTimeout(fn) {return 0;}, clearTimeout() {}, navigator: {userActivation: {isActive: true}}};
  g.window = g; vm.createContext(g); vm.runInContext(code, g);
  const X = {G: {events: [], causeEdges: [], tasks: []}, M: {nCh: 0, chapters: [], chapterEvents: [], chapterCast: []},
    disc: {setCursor(v) {cursor = v;}, cursor() {return cursor;}},
    doc: {hidden: false}, hud: null, el: {skyCaption: {}, skyScrub: {}, skyPlay: {setAttribute(n, v) {this[n] = v;}}}, plot: true, mode: 'constellation', playing: false, playT: null, speed: 1,
    esc(v) {return String(v).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));}, unit() {return '章';}, reduced() {return false;}, light() {}, setPlot(v) {this.plot = v;}, compassToPlot() {this.mode = 'constellation'; this.plot = true;}, scene() {return null;}, GLYPH: {play: 'play', pause: 'pause'}};
  if (extra) extra(X, g);
  return {X, g, P: g.CLSkyShellPlayer.create(X)};
}
function book(n, chapters, events) {
  return X => {
    X.G.events = events || Array.from({length: n}, (_, i) => ({id: 'e' + i, title: '事件' + (i + 1)}));
    X.G.events.forEach((e, i) => { if (!e.id) e.id = 'e' + i; if (!e.title) e.title = '事件' + (i + 1); });
    X.M = {nCh: chapters.length, chapters, chapterEvents: chapters.map(() => []), chapterCast: chapters.map(() => [])};
    let used = 0;
    for (let c = 0; c < chapters.length; c++) {
      const take = Math.floor((n - used) / (chapters.length - c));
      X.M.chapterEvents[c] = Array.from({length: take}, (_, k) => used + k);
      used += take;
    }
  };
}
function explicitBook(events, chapters, chapterEvents) {
  return X => {
    X.G.events = events.map((e, i) => Object.assign({id: 'e' + i, title: '事件' + (i + 1)}, e));
    X.M = {nCh: chapters.length, chapters, chapterEvents, chapterCast: chapters.map(() => [])};
  };
}
function scrubOf(t) {const panel = t.X.hud.childNodes[0]; return panel && typeof panel.querySelector === 'function' ? panel.querySelector('#skyStoryScrub') : null;}
function key(t, k, opts) {
  let pd = false, sp = false;
  scrubOf(t).listeners.keydown(Object.assign({key: k, preventDefault() {pd = true;}, stopPropagation() {sp = true;}}, opts || {}));
  assert.ok(pd && sp, k + ' must be claimed by the scrubber');
}
const names = [];
function test(name, fn) {fn(); names.push(name); console.log('PASS ' + name);}
function plain(v) {return JSON.parse(JSON.stringify(v));}
test('multi-chapter books extract boundaries from the axis projection with real names', () => {
  const t = make(book(12, [{no: 1}, {no: 2}, {no: 3}]));
  const p = plain(t.P.chapters());
  assert.strictEqual(p.status, 'multi');
  assert.strictEqual(p.count, 3);
  assert.deepStrictEqual(p.boundaries.map(b => b.at), [0, 4, 8]);
  assert.deepStrictEqual(p.boundaries.map(b => b.name), ['第 1 章', '第 2 章', '第 3 章']);
  assert.ok(p.labels.length >= 2 && p.labels.length <= 3);
});
test('a single-chapter book keeps the chapter name but honestly admits no tick band', () => {
  const t = make(X => {addDom(X); book(6, [{name: '全一章'}])(X);});
  assert.strictEqual(t.P.chapters().status, 'single');
  assert.strictEqual(t.P.chapters().labels.length, 0);
  t.P.seekEvent('e0');
  assert.ok(scrubOf(t).getAttribute('aria-valuetext').includes('全一章'));
  const band = t.X.hud.childNodes[0].querySelector('#skyStoryScrub .ssp-scrub-ticks');
  assert.strictEqual(band.childNodes.length, 0);
});
test('books without usable chapter data degrade to the plain serial wording, byte for byte', () => {
  const t = make(X => {addDom(X); explicitBook([{}, {}, {}], [null], [[0, 1, 2]])(X);});
  assert.strictEqual(t.P.chapters().status, 'none');
  t.P.seekEvent('e1');
  assert.strictEqual(scrubOf(t).getAttribute('aria-valuetext'), '2 / 3 · 事件2');
  assert.strictEqual(t.P.chapters().current, null);
});
test('mixed gaps never invent boundaries: only mapped chapters get ticks', () => {
  const t = make(explicitBook([{}, {}, {}, {}, {}], [{no: 1}, null, {no: 7}], [[0, 1], [2, 3], [4]]));
  assert.strictEqual(t.P.chapters().status, 'multi');
  const p = plain(t.P.chapters());
  assert.deepStrictEqual(p.boundaries.map(b => b.at), [0, 4]);
  assert.deepStrictEqual(p.boundaries.map(b => b.name), ['第 1 章', '第 7 章']);
});
test('dense chapters merge labels by the 1/16-gap rule while ticks stay complete', () => {
  const t = make(book(904, Array.from({length: 100}, (_, i) => ({no: i + 1}))));
  const p = plain(t.P.chapters());
  assert.strictEqual(p.status, 'multi');
  assert.strictEqual(p.count, 100);
  const gap = Math.round(903 * 0.0625);
  assert.ok(p.labels.length >= 2 && p.labels.length <= 17, 'labels within merged cap: ' + p.labels.length);
  for (let i = 1; i < p.labels.length; i++) assert.ok(p.labels[i].at - p.labels[i - 1].at >= gap, 'adjacent labels keep the gap');
  const boundaryAts = new Set(p.boundaries.map(b => b.at));
  assert.ok(p.labels.every(l => boundaryAts.has(l.at)), 'every label sits on a real boundary');
  assert.strictEqual(p.labels[0].at, 0);
});
test('aria-valuetext carries the chapter name of the dragged position, not the committed one', () => {
  const t = make(X => {addDom(X); book(12, [{no: 1}, {no: 2}, {no: 3}])(X);});
  t.P.seekEvent('e0');
  const scrub = scrubOf(t);
  scrub.getBoundingClientRect = () => ({left: 0, width: 100});
  assert.strictEqual(scrub.getAttribute('aria-valuetext'), '1 / 12 · 事件1 · 第 1 章');
  scrub.listeners.pointerdown({clientX: 50, button: 0, pointerId: 3, currentTarget: scrub});
  scrub.listeners.pointermove({clientX: 97, button: 0, pointerId: 3, currentTarget: scrub});
  assert.strictEqual(scrub.getAttribute('aria-valuetext'), '12 / 12 · 事件12 · 第 3 章');
  assert.strictEqual(t.P.state().eventId, 'e0');
  scrub.listeners.pointerup({clientX: 97, button: 0, pointerId: 3, currentTarget: scrub});
  assert.strictEqual(t.P.state().eventId, 'e11');
  assert.strictEqual(t.P.chapters().current, '第 3 章');
});
test('the tick band renders one line per boundary and merged labels with edge classes', () => {
  const t = make(X => {addDom(X); book(24, [{no: 1}, {no: 2}, {no: 3}])(X);});
  t.P.seekEvent('e0');
  const panel = t.X.hud.childNodes[0];
  const band = panel.querySelector('#skyStoryScrub .ssp-scrub-ticks');
  const host = panel.querySelector('#skyStoryTickLabels');
  assert.strictEqual(band.childNodes.length, 3);
  assert.strictEqual(host.childNodes.length, 3);
  assert.ok(host.childNodes[0].attrs['class'].includes('is-first'));
  assert.strictEqual(host.childNodes[0].textContent, '第 1 章');
  assert.ok(!host.childNodes[2].attrs['class'].includes('is-last'), 'a chapter starting mid-track is not pinned to the rail end');
});
test('plain Page keys keep the ten-percent jump; Shift+Page seeks chapter boundaries', () => {
  const t = make(X => {addDom(X); book(40, [{no: 1}, {no: 2}, {no: 3}, {no: 4}])(X);});
  t.P.seekEvent('e0');
  key(t, 'PageDown');
  assert.strictEqual(t.P.state().eventId, 'e4', 'plain PageDown stays a 10% jump');
  key(t, 'PageDown', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e10', 'Shift+PageDown enters the next chapter start');
  key(t, 'PageDown', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e20');
  key(t, 'PageUp', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e10', 'Shift+PageUp returns to the previous chapter start');
  t.P.seekEvent('e13');
  key(t, 'PageUp', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e10', 'mid-chapter Shift+PageUp first lands on this chapter start');
});
test('shifted chapter seeks clamp at the book ends and stay claimed', () => {
  const t = make(X => {addDom(X); book(40, [{no: 1}, {no: 2}])(X);});
  t.P.seekEvent('e0');
  key(t, 'PageUp', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e0', 'first chapter: Shift+PageUp is a claimed no-op');
  t.P.seekEvent('e30');
  key(t, 'PageDown', {shiftKey: true});
  assert.strictEqual(t.P.state().eventId, 'e30', 'last chapter: Shift+PageDown is a claimed no-op');
});
test('without a tick band Shift+Page falls back to the ten-percent jump instead of inventing chapters', () => {
  for (const mk of [() => make(X => {addDom(X); book(40, [{name: '全一章'}])(X);}),
                    () => make(X => {addDom(X); explicitBook(Array.from({length: 40}, () => ({})), [null], [Array.from({length: 40}, (_, i) => i)])(X);})]) {
    const t = mk();
    t.P.seekEvent('e0');
    key(t, 'PageDown', {shiftKey: true});
    assert.strictEqual(t.P.state().eventId, 'e4', 'shift falls back to the plain jump: ' + t.P.chapters().status);
  }
});
test('the chapter projection follows the current event exactly', () => {
  const t = make(book(12, [{no: 40}, {no: 41}]));
  t.P.seekEvent('e7');
  assert.strictEqual(t.P.chapters().current, '第 41 章');
  assert.strictEqual(t.P.state().chapters.current, '第 41 章');
  assert.strictEqual(t.P.state().chapters.status, 'multi');
});
console.log(names.length + ' scrub chapter tick contracts passed');
