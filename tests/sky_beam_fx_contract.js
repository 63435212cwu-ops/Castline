'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const code = fs.readFileSync('js/sky/sky-shell-player.js', 'utf8');
const FLOW_DASH = 22, FLOW_GAP = 16, FLOW_RATE = 24;
function expectFlow(from, to, age) {
  const px = Math.max(48, Math.hypot(to[0] - from[0], to[1] - from[1]) * 1.1), cycle = (FLOW_DASH + FLOW_GAP) / px;
  return {dash: (FLOW_DASH / px).toFixed(5) + ' ' + (FLOW_GAP / px).toFixed(5),
          off: (-((age * FLOW_RATE / px) % cycle)).toFixed(5)};
}
function make(extra) {
  const timers = new Map(); let serial = 0, cursor = null, now = 0, frameHook = null;
  const g = {Date: {now() {return now;}}, setTimeout(fn, ms) {const i = ++serial; timers.set(i, {fn, ms}); return i;}, clearTimeout(i) {timers.delete(i);}, navigator: {userActivation: {isActive: true}}, innerWidth: 800, innerHeight: 600};
  g.window = g; vm.createContext(g); vm.runInContext(code, g);
  const nodes = new Map();
  function element(id) {
    const el = {id: id || '', childNodes: [], hidden: false, listeners: {}, attrs: {}, writes: {}, styleProps: {}, tabIndex: 0,
      style: {setProperty(k, v) {el.styleProps[k] = String(v);}},
      focus() {},
      appendChild(child) {el.childNodes.push(child); return child;},
      addEventListener(name, fn) {el.listeners[name] = fn;},
      setAttribute(name, value) {el.attrs[name] = String(value); el.writes[name] = (el.writes[name] || 0) + 1;},
      getAttribute(name) {return el.attrs[name];},
      querySelector(sel) {const key = 'q:' + sel; if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key);}};
    let html = '', text = '';
    Object.defineProperty(el, 'innerHTML', {get() {return html;}, set(v) {html = v; for (const m of v.matchAll(/\bid="([^"]+)"/g)) if (!nodes.has(m[1])) nodes.set(m[1], element(m[1]));}});
    Object.defineProperty(el, 'textContent', {get() {return text;}, set(v) {text = v; if (v === '') el.childNodes = [];}});
    if (id) nodes.set(id, el); return el;
  }
  const X = {G: {events: [
    {id: 'a', title: '甲发现锁门', characters: ['甲']},
    {id: 'b', title: '甲找到钥匙', characters: ['甲', '乙']},
    {id: 'c', title: '乙开门救人', characters: ['乙']}
  ], causeEdges: [{fromEventId: 'a', toEventId: 'b', resolved: true}, {fromEventId: 'b', toEventId: 'c', resolved: true}], tasks: []},
  M: {nCh: 3, chapterEvents: [[0], [1], [2]], chapters: [{no: 1}, {no: 2}, {no: 3}], chapterCast: [['甲'], ['甲', '乙'], ['乙']]},
  disc: {setCursor(v) {cursor = v;}, cursor() {return cursor;}, eventPoint(i) {return {x: 100 + i * 150, y: 200 + i * 10, kind: 'bead'};}},
  doc: null, hud: element('hud'), el: {skyCaption: {}, skyScrub: {}, skyPlay: {setAttribute() {}, focus() {}}},
  plot: true, mode: 'constellation', playing: false, playT: null, speed: 1,
  esc(v) {return String(v).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));},
  unit() {return '章';}, reduced() {return false;}, light() {}, setPlot(v) {this.plot = v;},
  compassToPlot() {this.mode = 'constellation'; this.plot = true;},
  scene() {return {registerFrameHook(fn) {frameHook = fn;}};}, GLYPH: {play: 'play', pause: 'pause'}};
  X.doc = {hidden: false, createElement() {return element();}, createElementNS() {return element();}, getElementById(id) {return nodes.get(id);}};
  if (extra) extra(X, g);
  const P = g.CLSkyShellPlayer.create(X);
  return {X, g, P, timers,
    frame(dt) {assert(frameHook, 'frame hook must be registered'); frameHook(dt);},
    svg() {return X.hud.childNodes[1];},
    group(i) {return this.svg().childNodes[i];},
    fire() {assert.strictEqual(timers.size, 1); const [i, t] = timers.entries().next().value; timers.delete(i); now += t.ms; t.fn(); return t.ms;}};
}
const names = [];
function test(name, fn) {fn(); names.push(name); console.log('PASS ' + name);}
test('the beam grows along the path and the flow layer waits for growth to finish', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(0.3);
  assert.strictEqual(t.P.state().stage, 'after'); assert.strictEqual(t.P.state().links, 1);
  const path = t.group(0).childNodes[0], head = t.group(0).childNodes[1], flow = t.group(0).childNodes[2];
  assert.strictEqual(path.styleProps['--ssp-reveal'], '0.25');
  assert.strictEqual(flow.getAttribute('visibility'), 'hidden');
  assert.strictEqual(flow.writes['stroke-dashoffset'] || 0, 0);
  t.frame(0.4);
  assert.strictEqual(path.styleProps['--ssp-reveal'], String(0.7 / 1.2));
  assert.strictEqual(flow.getAttribute('visibility'), 'hidden');
  assert.strictEqual(head.getAttribute('opacity'), '0');
  t.frame(0.6);
  assert.strictEqual(path.styleProps['--ssp-reveal'], '1');
  assert.strictEqual(head.getAttribute('opacity'), '1');
  assert.strictEqual(flow.getAttribute('visibility'), 'visible');
  const want = expectFlow([100, 200], [250, 210], 0.6);
  assert.strictEqual(flow.getAttribute('stroke-dasharray'), want.dash);
  assert.strictEqual(flow.getAttribute('stroke-dashoffset'), want.off);
});
test('flow is driven by the shared frame clock and marches toward the consequence end', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(2);
  const flow = t.group(0).childNodes[2];
  const first = parseFloat(flow.getAttribute('stroke-dashoffset'));
  assert(first < 0, 'dash offset moves dashes forward along the path (cause → effect)');
  t.frame(0.2); const second = parseFloat(flow.getAttribute('stroke-dashoffset'));
  t.frame(0.2); const third = parseFloat(flow.getAttribute('stroke-dashoffset'));
  assert(second < first && third < second, 'offset must keep decreasing with frame time: ' + [first, second, third]);
  const want = expectFlow([100, 200], [250, 210], 2.4);
  assert.strictEqual(flow.getAttribute('stroke-dashoffset'), want.off);
});
test('attributes are written only when their value changes (attribute compare is the cache)', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(2);
  const flow = t.group(0).childNodes[2], path = t.group(0).childNodes[0];
  const flowWrites = flow.writes['stroke-dashoffset'] || 0, pathWrites = path.writes.d || 0;
  t.frame(0); t.frame(0);
  assert.strictEqual(flow.writes['stroke-dashoffset'], flowWrites);
  t.frame(0.15); assert.strictEqual(flow.writes['stroke-dashoffset'], flowWrites + 1);
  const dashWrites = flow.writes['stroke-dasharray'];
  t.frame(0.15); assert.strictEqual(flow.writes['stroke-dasharray'], dashWrites + 1);
  assert.strictEqual(path.writes.d, pathWrites, 'static pose re-renders no geometry');
});
test('pausing freezes the flow layer once and leaves the stable arrow state untouched', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(2);
  const flow = t.group(0).childNodes[2], path = t.group(0).childNodes[0], head = t.group(0).childNodes[1];
  const w = flow.writes['stroke-dashoffset'];
  t.P.stopPlay(); t.frame(0.5);
  assert.strictEqual(flow.getAttribute('visibility'), 'hidden');
  t.frame(0.5); t.frame(0.5);
  assert.strictEqual(flow.writes['stroke-dashoffset'], w, 'paused frames never advance flow');
  assert.strictEqual(path.styleProps['--ssp-reveal'], '1');
  assert.strictEqual(head.getAttribute('opacity'), '1');
  assert.strictEqual(t.timers.size, 0);
});
test('reduced motion lands on the terminal drawn state with zero animation frames', () => {
  const t = make(X => {X.reduced = () => true;}); t.P.togglePlay(); t.fire();
  t.frame(0.3);
  const path = t.group(0).childNodes[0], flow = t.group(0).childNodes[2];
  assert.strictEqual(path.styleProps['--ssp-reveal'], '1', 'no growth tween under reduced motion');
  t.frame(0.5); t.frame(0.5);
  assert.strictEqual(flow.getAttribute('visibility'), 'hidden');
  assert.strictEqual(flow.writes['stroke-dashoffset'] || 0, 0, 'zero flow frames under reduced motion');
  assert.strictEqual(flow.writes['stroke-dasharray'] || 0, 0);
  assert.strictEqual(flow.writes.visibility || 0, 1, 'the only visibility write is creation-time hidden');
  assert.strictEqual(t.timers.size, 1, 'playback itself still runs');
});
test('rapid re-entry across events stacks no leftover paths, layers or timers', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(0.1);
  for (let k = 0; k < 4; k++) {
    t.P.seekEventAt(2); t.frame(0.1);
    assert.strictEqual(t.svg().childNodes.length, 1, 'one group per live link');
    assert.strictEqual(t.group(0).childNodes.length, 3, 'path + head + flow per group');
    t.P.seekEventAt(0); t.frame(0.1);
    assert.strictEqual(t.svg().childNodes.length, t.P.state().links, 'groups always match live links');
    assert.strictEqual(t.timers.size, 1, 'exactly one playback timer survives every hop');
  }
  t.P.seekEventAt(2); t.P.seekEventAt(0); t.P.seekEventAt(2); t.frame(0.1);
  assert.strictEqual(t.svg().childNodes.length, 1);
  assert.strictEqual(t.timers.size, 1);
});
test('closing the panel destroys the overlay with it and leaves no clock behind', () => {
  const t = make(); t.P.togglePlay(); t.fire(); t.frame(2);
  const panel = t.X.hud.childNodes[0];
  panel.listeners.click({target: {closest() {return {getAttribute() {return 'close';}};}}});
  assert.strictEqual(t.X.playing, false); assert.strictEqual(t.timers.size, 0);
  t.frame(0.5);
  assert.strictEqual(t.svg().childNodes.length, 0, 'overlay is torn down on the next frame');
  t.frame(0.5);
  assert.strictEqual(t.svg().childNodes.length, 0);
});
test('same-bead loops flow at the clamped minimum length rather than dividing by zero', () => {
  const t = make(X => {X.disc.eventPoint = () => ({x: 240, y: 180, kind: 'bead'});});
  t.P.togglePlay(); t.fire(); t.frame(2);
  const flow = t.group(0).childNodes[2], want = expectFlow([240, 180], [240, 180], 2);
  assert.strictEqual(flow.getAttribute('visibility'), 'visible');
  assert.strictEqual(flow.getAttribute('stroke-dasharray'), want.dash);
  assert.strictEqual(flow.getAttribute('stroke-dashoffset'), want.off);
  assert(flow.getAttribute('d').startsWith('M240,180 C'));
});
console.log(names.length + ' beam fx behavior contracts passed');
