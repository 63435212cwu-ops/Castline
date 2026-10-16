'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.resolve(__dirname, '..');
const window = { getComputedStyle() { return { fontSize: '11px' }; } };
const sandbox = vm.createContext({ window, document: { body: { classList: { contains: () => true } } } });
for (const file of ['sky-disc-tracks.js', 'sky-disc-labels.js', 'sky-disc-layout.js']) {
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'js/sky', file), 'utf8'), sandbox, { filename: file });
}
function element() {
  const attrs = {};
  return { attrs, setAttribute(k, v) { attrs[k] = String(v); }, getAttribute(k) { return attrs[k] || null; } };
}
let frames = 0;
for (const [metric, titleMetric] of [[null, null], [[-6, -9, 6, 2], null], [null, [-10, 10]]]) for (const side of [2, 3]) {
  const number = { el: element(), point: [200, 100], basePoint: [200, 100], layoutWidth: 12, fh: 11 };
  if (metric) number.textBox = metric;
  let availability = 'lane', cursorCalls = 0;
  const C = {
    Wv: 400, Hv: 300, LAB_PAD: 3.5, INK: .46, CLEAR_MAIN: 2.6, CLEAR_NAMED: 1.5,
    clamp: (n, low, high) => Math.max(low, Math.min(high, n)),
    geo: { nums: [number], rNum: 0 }, P: { num: 1 }, cursor: 0,
    projA: r => [200, 100 + r * 12],
    drawCursor() { cursorCalls++; },
    dOfPts: points => points.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1]).join('')
  };
  Object.assign(C, window.CLSkyDiscTracks.create(C));
  const lane = C.track([[100, 180], [300, 180]]), fallback = C.track([[100, 100], [300, 100]]);
  const item = { lp: element(), tp: element(), tracks: [], shown: true, side, f: .28, tw: 40, fh: 11, kind: 'named' };
  if (titleMetric) item.numberBounds = titleMetric;
  C.items = [item];
  C.trackFor = (it, requested) => availability === 'none' ? null : requested === 0 ? fallback : availability === 'lane' ? lane : null;
  const footprint = C.footprint, measured = [];
  C.footprint = (it, track, fraction) => {
    assert.ok(track, 'number clearance must never pass an unavailable lane to footprint');
    measured.push({ track, fraction });
    return footprint(it, track, fraction);
  };
  const labels = window.CLSkyDiscLabels.create(C);
  function follow(expectedTrack, expectedFraction) {
    measured.length = 0;
    const callsBefore = cursorCalls;
    labels.followLabels();
    frames++;
    assert.equal(item.shown, true, 'moving the camera does not hide an already shown title');
    assert.equal(item.side, side, 'temporary fallback does not overwrite the selected endpoint lane');
    assert.equal(item.f, .28, 'temporary fallback does not overwrite the saved title anchor');
    assert.equal(cursorCalls, callsBefore + 1, 'cursor masking sees the final number placement once');
    if (!expectedTrack) {
      assert.equal(measured.length, 0, 'no footprint is fabricated when both paths are unavailable');
      return;
    }
    assert.equal(measured.length, 1, 'the one shown title contributes one footprint');
    assert.equal(measured[0].track, expectedTrack, 'number clearance measures the path actually drawn');
    assert.equal(measured[0].fraction, expectedFraction, 'measurement uses the same fractional anchor as drawing');
    assert.equal(item.lp.attrs.d, C.dOfPts(expectedTrack.P), 'SVG drawing and clearance share the same projected path');
    assert.equal(item.tp.attrs.startOffset, (expectedFraction * 100).toFixed(1) + '%');
  }
  follow(lane, .28);
  assert.deepEqual(number.point, [200, 100], 'unobstructed number stays at its real tick');
  availability = 'fallback';
  for (let frame = 0; frame < 3; frame++) {
    follow(fallback, .5);
    assert.equal(number.point[0], 200, 'fallback clearance preserves the number radial line');
    assert.ok(number.point[1] > 100 && number.point[1] <= 122,
      'number clears the drawn fallback title with bounded radial compensation');
    if (metric) assert.ok(number.point[1] + metric[1] >= 100 + item.fh * C.INK + C.LAB_PAD,
      'asymmetric measured number bounds retain the full required gap');
    if (titleMetric) assert.ok(number.point[1] - number.fh * C.INK >= 100 + titleMetric[1] + C.LAB_PAD,
      'measured title font height, rather than nominal font size, controls number clearance');
  }
  availability = 'none';
  follow(null);
  availability = 'lane';
  follow(lane, .28);
  assert.deepEqual(number.point, [200, 100], 'restored lane releases the number back to its real tick');
}
const trace = [], numbers = [0, 1].map(i => {
  const el = element();
  el.attrs.x = String(40 + i * 20); el.attrs.y = '60';
  el.textContent = String(i + 1);
  el.getComputedTextLength = () => { trace.push('read-width-' + i); return 12; };
  el.getBBox = () => {
    trace.push('read-box-' + i);
    return { x: Number(el.attrs.x) - 6, y: Number(el.attrs.y) - 9, width: 12, height: 11 };
  };
  const write = el.setAttribute;
  el.setAttribute = (key, value) => { trace.push('write-' + i); write(key, value); };
  return { el, a: i };
});
const L = {
  stats: { projections: 0 }, items: [], E: null, INK: .46, cursor: null,
  geo: { nums: numbers, vols: [], dorm: [], hos: [], rNum: 1, rBez: 1, rMain: 1, startMark: element() },
  P: { tick: .1, mainGap: .1, num: .1 }, R_IN: 1.1,
  angle: n => n, projA: (r, a) => [r * 100, 100 + a * 50], center: () => [100, 100],
  placeLabels() {}, followLabels() {}
};
L.items = [0, 1].map(i => ({
  kind: 'named', sm: [], hit: element(),
  tx: {
    textContent: '真实标题', parentNode: { appendChild() { trace.push('append-label-' + i); } },
    cloneNode() {
      const probe = element();
      probe.getBBox = () => { trace.push('read-label-' + i); return { x: -20, y: -10, width: 40, height: 20 }; };
      probe.remove = () => { trace.push('remove-label-' + i); };
      return probe;
    }
  }
}));
L.ptsOf = () => []; L.dOfPts = () => '';
const layout = window.CLSkyDiscLayout.create(L);
layout.reproject(false);
assert.deepEqual(trace.slice(0, 8), ['append-label-0', 'append-label-1', 'read-width-0', 'read-box-0',
  'read-width-1', 'read-box-1', 'read-label-0', 'read-label-1'],
  'all font probes are created before geometry reads; all reads precede cleanup and position writes');
numbers.forEach(n => assert.deepEqual(Array.from(n.textBox), [-6, -9, 6, 2],
  'cached glyph bounds are relative to each original text anchor'));
L.items.forEach(it => assert.deepEqual(Array.from(it.numberBounds), [-10, 10],
  'the complete measured title font height is cached for number clearance'));
trace.length = 0;
layout.reproject(true);
assert.ok(trace.length > 0 && trace.every(entry => entry.startsWith('write-')),
  'later camera projections reuse cached bounds without geometry reads');
console.log('PASS endpoint lanes, measured numeric bounds, batched reads and recovery (' + frames + ' frames)');
