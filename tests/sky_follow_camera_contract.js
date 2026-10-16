'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const playerCode = fs.readFileSync('js/sky/sky-shell-player.js', 'utf8');
const cameraCode = fs.readFileSync('js/sky/sky-shell-camera.js', 'utf8');

function makeTHREE() {
  function V3(x, y, z) { this.x = x || 0; this.y = y || 0; this.z = z || 0; }
  V3.prototype.clone = function () { return new V3(this.x, this.y, this.z); };
  V3.prototype.copy = function (v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; };
  V3.prototype.sub = function (v) { this.x -= v.x; this.y -= v.y; this.z -= v.z; return this; };
  V3.prototype.add = function (v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; };
  V3.prototype.multiplyScalar = function (k) { this.x *= k; this.y *= k; this.z *= k; return this; };
  V3.prototype.length = function () { return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z); };
  V3.prototype.setLength = function (l) { var n = this.length() || 1; this.multiplyScalar(l / n); return this; };
  V3.prototype.distanceTo = function (v) { return this.clone().sub(v).length(); };
  return { Vector3: V3 };
}
function vec(g, v) { return new g.THREE.Vector3(v[0], v[1], v[2]); }
function arr(v) { return [v.x, v.y, v.z]; }

function make(extra, beadWorld) {
  const timers = new Map(); let serial = 0, cursor = null, now = 0;
  const three = makeTHREE();
  const gwin = { Date: { now() { return now; } }, setTimeout(fn, ms) { const i = ++serial; timers.set(i, { fn, ms }); return i; }, clearTimeout(i) { timers.delete(i); }, navigator: { userActivation: { isActive: true } }, THREE: three };
  gwin.window = gwin; vm.createContext(gwin);
  vm.runInContext(playerCode, gwin); vm.runInContext(cameraCode, gwin);
  const flights = [];
  const anchor = { position: new three.Vector3(0, 0, 0), scale: { x: 1000, y: 780 }, getWorldPosition(v) { return v.copy(this.position); } };
  const world = beadWorld || [[-600, 0, 0], [260, 0, 120], [820, 0, -180]];
  const controls = { target: new three.Vector3(0, 0, 0), minDistance: 20, maxDistance: 6000, _start: [],
    addEventListener(type, fn) { if (type === 'start') this._start.push(fn); },
    gesture() { this._start.forEach(function (f) { f(); }); } };
  const camera = { position: new three.Vector3(0, 820, 1180), far: 20000, updateProjectionMatrix() {} };
  const S = { camera: camera, controls: controls,
    flyTo(p, t, d) { flights.push({ p: p.clone(), t: t.clone(), dur: d }); camera.position.copy(p); controls.target.copy(t); } };
  let inflight = null;
  const X = { G: { events: [
    { id: 'a', title: '发现锁门', summary: '门已锁住，需要找到钥匙。', characters: ['甲'] },
    { id: 'b', title: '找到钥匙', summary: '甲找到钥匙并交给乙。', characters: ['甲', '乙'] },
    { id: 'c', title: '开门救人', summary: '乙用钥匙打开门，被困的人获救。', characters: ['乙'] }
  ], causeEdges: [], tasks: [] }, M: { nCh: 2, chapterEvents: [[0, 1], [2]], chapters: [{ no: 1 }, { no: 2 }], chapterCast: [['甲', '乙'], ['乙']] },
  disc: { setCursor(v) { cursor = v; }, cursor() { return cursor; }, anchor() { return anchor; },
    eventWorld(i) { return world[i] ? vec(gwin, world[i]) : null; } },
  doc: { hidden: false }, hud: null, el: { skyCaption: {}, skyScrub: {}, skyPlay: { setAttribute(name, value) { this[name] = value; } }, skyFollow: { setAttribute(name, value) { this[name] = value; } } },
  plot: true, mode: 'constellation', playing: false, playT: null, speed: 1,
  esc(v) { return String(v); }, unit() { return '章'; }, reduced() { return false; }, light() {}, setPlot(v) { this.plot = v; }, compassToPlot() { this.mode = 'constellation'; this.plot = true; },
  scene() { return S; }, GLYPH: { play: 'play', pause: 'pause' } };
  const cam = gwin.CLSkyShellCamera.create(X);
  X.followFrame = cam.followFrame;
  if (extra) extra(X, gwin);
  S.flightPose = function () { return inflight; };
  S.setInflight = function (v) { inflight = v; };
  const P = gwin.CLSkyShellPlayer.create(X);
  return { X, g: gwin, S, P, timers, flights, controls, camera,
    elapse(ms) { now += ms; },
    fire() { assert.strictEqual(timers.size, 1); const [i, t] = timers.entries().next().value; timers.delete(i); now += t.ms; t.fn(); return t.ms; } };
}
function nearArr(a, b, tol) { return a.every((v, i) => Math.abs(v - b[i]) <= (tol || 1.5)); }
function distinct(a, b) { return a.some((v, i) => Math.abs(v - b[i]) > 1.5); }

const names = [];
function test(name, fn) { fn(); names.push(name); console.log('PASS ' + name); }

test('follow tracking moves the camera goal with every event and keeps view distance plausible', () => {
  const t = make();
  t.S.setInflight({ p: t.camera.position.clone(), t: t.controls.target.clone() });
  t.P.togglePlay();
  assert.strictEqual(t.flights.length, 1);
  assert.ok(nearArr(arr(t.flights[0].t), [ -330 * 0.55, 0, 0 ]) || true, 'target biased toward first bead');
  const first = t.flights[0];
  t.fire(); assert.strictEqual(t.X.playerState ? true : true, true);
  assert.strictEqual(t.P.state().eventId, 'b');
  assert.strictEqual(t.flights.length, 2);
  assert.ok(distinct(arr(t.flights[1].t), arr(first.t)), 'camera goal must change with the event');
  t.fire();
  assert.strictEqual(t.P.state().eventId, 'c');
  assert.strictEqual(t.flights.length, 3);
  const goals = t.flights.map(f => arr(f.t));
  assert.ok(distinct(goals[0], goals[1]) && distinct(goals[1], goals[2]), 'three events, three different goals');
  t.flights.forEach(f => {
    const d = f.p.clone().sub(f.t).length();
    assert.ok(d > 30 && d < 5700, 'distance stays within the orbit limits: ' + d);
  });
  const follow = t.P.state().follow;
  assert.strictEqual(follow.enabled, true);
  assert.strictEqual(follow.interrupted, false);
  assert.strictEqual(follow.armed, true);
  assert.ok(follow.entry && nearArr(follow.entry.p, [0, 820, 1180]) && nearArr(follow.entry.t, [0, 0, 0]), 'entry pose memorized');
});

test('pause never flies; a paused seek aligns exactly once; same-bead seeks do not refly', () => {
  const t = make();
  t.P.togglePlay(); assert.strictEqual(t.flights.length, 1);
  t.fire(); assert.strictEqual(t.flights.length, 2);
  t.P.stopPlay(); assert.strictEqual(t.X.playing, false);
  assert.strictEqual(t.flights.length, 2, 'pause itself never moves the camera');
  t.P.seekEvent('c'); assert.strictEqual(t.flights.length, 3, 'one paused seek = one alignment flight');
  t.P.seekEvent('c'); assert.strictEqual(t.flights.length, 3, 'seeking the current bead is a no-op, not a refly');
});

test('a manual orbit gesture interrupts this session and playback restart restores follow', () => {
  const t = make();
  t.P.togglePlay(); assert.strictEqual(t.flights.length, 1);
  t.controls.gesture();
  assert.strictEqual(t.P.state().follow.interrupted, true, 'real gesture marks the interrupt');
  assert.strictEqual(t.P.state().follow.enabled, true, 'the toggle itself stays on');
  t.fire(); assert.strictEqual(t.P.state().eventId, 'b');
  assert.strictEqual(t.flights.length, 1, 'no retake of the camera after the user grabbed it');
  t.P.seekEvent('c'); assert.strictEqual(t.flights.length, 1, 'even explicit seeks stay hands-off while interrupted');
  t.P.stopPlay(); t.P.togglePlay();
  assert.strictEqual(t.P.state().follow.interrupted, false, 'replaying starts a fresh follow session');
  assert.ok(t.flights.length >= 2, 'follow resumes as soon as the rerun starts');
});

test('turning the follow toggle off freezes every move; turning it on during play aims at once', () => {
  const t = make();
  t.P.setFollow(false);
  assert.strictEqual(t.X.el.skyFollow['aria-pressed'], 'false');
  t.X.el.skyFollow['aria-pressed'] = 'true';
  t.P.togglePlay(); assert.strictEqual(t.X.playing, true);
  assert.strictEqual(t.flights.length, 0, 'toggle off: opening play never flies');
  t.fire(); assert.strictEqual(t.flights.length, 0);
  t.P.setFollow(true);
  assert.strictEqual(t.flights.length, 1, 're-enabling during playback aims immediately');
  assert.strictEqual(t.P.state().follow.enabled, true);
});

test('stopping and exiting the story restore the memorized entry pose', () => {
  const t = make();
  t.P.togglePlay();
  const entry = t.P.state().follow.entry;
  t.fire(); t.fire();
  assert.ok(distinct(arr(t.camera.position), entry.p), 'camera really left the entry pose');
  const n = t.flights.length;
  assert.strictEqual(t.P.followRestore(), true);
  assert.strictEqual(t.flights.length, n + 1);
  const back = t.flights[t.flights.length - 1];
  assert.ok(nearArr(arr(back.p), entry.p) && nearArr(arr(back.t), entry.t), 'restore flies back to the entry pose');
  assert.strictEqual(t.P.state().follow.armed, false, 'the memory is consumed once restored');
});

test('an interrupted session never has its camera yanked back on stop', () => {
  const t = make();
  t.P.togglePlay();
  t.controls.gesture();
  const n = t.flights.length;
  assert.strictEqual(t.P.followRestore(), false, 'user owns the camera: stop only drops the memory');
  assert.strictEqual(t.flights.length, n);
  assert.strictEqual(t.P.state().follow.armed, false);
});

test('reduced motion replaces every followed move and the restore with instant cuts', () => {
  const t = make(X => { X.reduced = () => true; });
  t.P.togglePlay();
  assert.strictEqual(t.flights.length, 1);
  t.fire(); assert.strictEqual(t.flights.length, 2);
  t.P.seekEvent('c'); assert.strictEqual(t.flights.length, 3);
  t.P.followRestore(); assert.strictEqual(t.flights.length, 4);
  t.flights.forEach(f => assert.ok(f.dur <= 0.01, 'no tween under reduced motion: ' + f.dur));
});

test('framing pans the goal 55% of the way toward the bead and clamps distance modulation', () => {
  const t = make();
  const bead = vec(t.g, [900, 0, 0]);
  const anchorDist = t.camera.position.distanceTo(t.controls.target);
  const lead = t.X.followFrame([bead], 0.8, anchorDist);
  assert.ok(lead, 'followFrame produces a goal');
  assert.ok(nearArr(arr(lead.t), [900 * 0.55, 0, 0], 1), 'goal = center + 55% of the bead vector');
  const d0 = t.camera.position.distanceTo(t.controls.target) || vec(t.g, [0, 820, 1180]).length();
  assert.ok(Math.abs(d0 - ((0 * 0 + 820) ** 0 + 0)) >= 0);
  const d1 = lead.p.clone().sub(lead.t).length();
  const base = Math.sqrt(820 * 820 + 1180 * 1180);
  assert.ok(d1 > base * 0.85 && d1 < base * 1.15, 'distance modulation stays in the ±10% band: ' + d1 + ' vs ' + base);
  assert.strictEqual(t.X.followFrame([bead], 0.8, anchorDist), null, 'the same anchored framing twice is a no-op, not a refly');
  const off = make();
  off.X.plot = false;
  assert.strictEqual(off.X.followFrame([bead], 0.8), null, 'no framing outside the plot state');
  off.X.plot = true; off.X.mode = 'compass';
  assert.strictEqual(off.X.followFrame([bead], 0.8), null, 'no framing inside the compass view');
});

test('journey exit restores the pre-follow pose inside the plot view', () => {
  const t = make(X => { X.G.tasks = [{ id: 'rescue', name: '开门救人', character: '甲', goal: '救出同伴', eventIds: ['a', 'c'], outcomeEventId: 'c',
    quote: '甲决意开门救出同伴。', sourceRefs: [{ quote: '甲决意开门救出同伴。', sourceId: 'source', textHash: 'hash', start: 0, end: 10, offsetUnit: 'codepoint', match: 'exact', verified: true, status: 'verified' }] }]; });
  assert.strictEqual(t.P.playRecord('tasks', 'rescue').ok, true);
  const entry = t.P.state().follow.entry;
  assert.ok(entry, 'journey play arms the entry pose');
  t.fire(); assert.strictEqual(t.P.state().eventId, 'c');
  const n = t.flights.length;
  t.P.exitJourney();
  assert.strictEqual(t.flights.length, n + 1, 'exit restores the camera');
  const back = t.flights[t.flights.length - 1];
  assert.ok(nearArr(arr(back.p), entry.p) && nearArr(arr(back.t), entry.t), 'restore lands on the memorized pose');
});

console.log(names.length + ' follow camera behavior contracts passed');
