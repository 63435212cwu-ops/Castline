/* Run: node tests/sky_tug_camera_contract.js
 * Offline input/lifecycle regression using the shipped Three.js, sky tokens,
 * and complete sky-tug module. Synthetic pointer events enter its registered
 * handlers; the scene hook receives a host camera change before each frame.
 * Only DOM events/capture and scene ownership are doubles. No WebGL, browser,
 * source-shape assertions, or copied drag/camera implementation are involved.
 * Browser projection/performance acceptance remains in sky_tug/sky_chaos.py.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');
const ROOT = path.join(__dirname, '..');
const tokenSource = fs.readFileSync(path.join(ROOT, 'js/sky/sky-tokens.js'), 'utf8');
const sourcePath = path.join(ROOT, 'js/sky/sky-tug.js');

function eventTarget() {
  const handlers = new Map();
  return {
    addEventListener(type, fn) {
      if (!handlers.has(type)) handlers.set(type, []);
      handlers.get(type).push(fn);
    },
    dispatchEvent(event) {
      if (!event.target) event.target = this;
      for (const fn of (handlers.get(event.type) || []).slice()) {
        fn(event);
        if (event.immediateStopped) break;
      }
    }
  };
}

function fixture(source, options = {}) {
  const classes = new Set(['sky-shell']);
  const classList = {
    contains: value => classes.has(value),
    add: value => classes.add(value),
    remove: value => classes.delete(value),
    toggle(value, on) {
      if (on === undefined) on = !classes.has(value);
      if (on) classes.add(value); else classes.delete(value);
      return on;
    }
  };
  const captures = new Set(), captureLog = [];
  const document = Object.assign(eventTarget(), {
    body: {
      classList,
      setPointerCapture(id) { captures.add(id); captureLog.push(['set', id]); },
      releasePointerCapture(id) { captures.delete(id); captureLog.push(['release', id]); }
    }
  });
  const rect = { left: 40, top: 20, width: 1440, height: 900 };
  const canvas = { getBoundingClientRect: () => rect };
  const camera = new THREE.PerspectiveCamera(45, rect.width / rect.height, 1, 1000);
  camera.position.set(27, -18, 180);
  const controls = { target: new THREE.Vector3(4, 3, -5), enableRotate: options.rotate !== false };
  camera.lookAt(controls.target); camera.updateMatrixWorld(true);
  const group = new THREE.Group(), object = new THREE.Object3D();
  const home = new THREE.Vector3(1, 2, 0);
  object.position.copy(home); group.add(object); group.updateMatrixWorld(true);
  const node = { key: 'c:甲', kind: 'char', alpha: 1, tier: 0, g: object };
  const hooks = [], writes = [], lifecycle = [];
  const graph = { characters: [{ name: '甲' }], relations: [] };
  const scene = {
    camera, controls, group, renderer: { domElement: canvas },
    core: () => ({ nodes: [node], getDegrade: () => 0 }),
    rimInfo: () => ({ mode: 'sky', R: 100, pitch: 0 }),
    nodeOf: key => key === node.key ? node : null,
    registerFrameHook(fn) { hooks.push(fn); },
    // Scene adapter consumes the public displacement map, as the host would.
    setTug(map) {
      writes.push(map ? Object.keys(map) : null);
      node.tugO = map && map[node.key] ? map[node.key].clone() : null;
      object.position.copy(home);
      if (node.tugO) object.position.add(node.tugO);
    }
  };
  let tick = 0;
  const context = Object.assign(eventTarget(), {
    THREE, document, performance: { now: () => tick },
    matchMedia: () => ({ matches: !!options.reduced }),
    CLScene: { current: scene }, CLSky: { enabled: () => true },
    CLSkyDeep: { stats: () => ({ reveal: { playing: false, staged: false } }) },
    CLApp: { graph: () => graph, atlas: { skyView: () => graph } }
  });
  context.window = context;
  vm.createContext(context);
  vm.runInContext(tokenSource, context, { filename: 'js/sky/sky-tokens.js' });
  vm.runInContext(source, context, { filename: sourcePath });
  const tug = context.CLSkyTug;
  tug.on(event => lifecycle.push(event.type));

  function pointer(type, x, y, extra = {}) {
    context.dispatchEvent(Object.assign({
      type, target: canvas, pointerId: 1, pointerType: 'mouse', isPrimary: true,
      clientX: x, clientY: y, button: 0, buttons: type === 'pointerup' || type === 'pointercancel' ? 0 : 1,
      timeStamp: ++tick, preventDefault() {}, stopPropagation() {},
      stopImmediatePropagation() { this.immediateStopped = true; }
    }, extra));
  }
  function starPoint() {
    group.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    const p = object.getWorldPosition(new THREE.Vector3()).project(camera);
    return [rect.left + (p.x + 1) * rect.width / 2, rect.top + (1 - p.y) * rect.height / 2];
  }
  function pose() { return { position: camera.position.clone(), target: controls.target.clone() }; }
  function moveHost(dx = 10) {
    camera.position.add(new THREE.Vector3(dx, -dx / 2, dx / 3));
    controls.target.add(new THREE.Vector3(dx / 2, dx / 3, -dx / 4));
    camera.lookAt(controls.target); camera.updateMatrixWorld(true);
    return pose();
  }
  function frame(count = 1) {
    for (let i = 0; i < count; i++) {
      tick += 1000 / 60;
      for (const hook of hooks.slice()) hook(1 / 60, tick / 1000, tick / 1000, false, 0);
    }
  }
  function press() { const p = starPoint(); pointer('pointerdown', ...p); return p; }
  function grab() { const p = press(); pointer('pointermove', p[0] + 36, p[1] + 7); return p; }
  return { tug, scene, document, context, classes, captures, captureLog, writes, lifecycle,
    pointer, pose, moveHost, frame, press, grab };
}

function samePose(f, wanted, label) {
  assert.ok(f.scene.camera.position.distanceTo(wanted.position) < 1e-10, label + ': camera position');
  assert.ok(f.scene.controls.target.distanceTo(wanted.target) < 1e-10, label + ': controls target');
  const direction = wanted.target.clone().sub(wanted.position).normalize();
  assert.ok(f.scene.camera.getWorldDirection(new THREE.Vector3()).distanceTo(direction) < 1e-10,
    label + ': camera orientation/matrix');
}

function clean(f) {
  assert.equal(f.tug.state().phase, 'idle');
  assert.equal(f.tug.stats().bodies, 0);
  assert.equal(f.captures.size, 0);
  assert.equal(f.classes.has('sky-tug-grabbing'), false);
  assert.equal(f.writes[f.writes.length - 1], null);
  const count = f.writes.length, after = f.moveHost(13);
  f.frame(4);
  samePose(f, after, 'idle gives camera back to host');
  assert.equal(f.writes.length, count, 'idle does not keep writing displacement');
}

function runContract(source, report = () => {}) {
  let cases = 0;
  function test(label, action) { action(); cases++; report('PASS ' + label); }

  test('drag restores the pressed camera pose after every host update', () => {
    const f = fixture(source), initial = f.pose();
    f.grab();
    assert.equal(f.tug.state().phase, 'drag');
    assert.equal(f.tug.stats().grabs, 1);
    assert.equal(f.scene.controls.enableRotate, false);
    assert.equal(f.captures.size, 1);
    for (const dx of [10, -9, 17]) { f.moveHost(dx); f.frame(); samePose(f, initial, 'active drag'); }
    assert.ok(f.writes.some(keys => keys && keys.includes('c:甲')), 'real tug map reaches scene');
    assert.ok(f.tug.state().off.length() > 0, 'real spring responds to pointer input');
  });

  for (const ending of ['pointerup', 'pointercancel', 'blur']) {
    test(ending + ' releases camera ownership during spring return', () => {
      const f = fixture(source), p = f.grab(); f.frame(8);
      if (ending === 'blur') f.context.dispatchEvent({ type: 'blur' });
      else f.pointer(ending, p[0] + 36, p[1] + 7);
      assert.equal(f.tug.state().phase, 'back');
      assert.equal(f.captures.size, 0);
      assert.equal(f.scene.controls.enableRotate, true);
      assert.equal(f.classes.has('sky-tug-grabbing'), false);
      const host = f.moveHost(); f.frame(); samePose(f, host, 'released spring');
      f.frame(180); clean(f);
      assert.deepEqual(f.lifecycle, ['grab', 'release', 'sleep']);
    });
  }

  for (const event of ['cl:sky-plot', 'cl:sky-compass', 'cl:graph-loading']) {
    test(event + ' cancels drag/capture/displacement immediately', () => {
      const f = fixture(source); f.grab(); f.frame(4);
      f.document.dispatchEvent({ type: event });
      clean(f);
      assert.equal(f.scene.controls.enableRotate, true);
      assert.deepEqual(f.captureLog, [['set', 1], ['release', 1]]);
    });
  }

  test('display switch also clears a press below the drag threshold', () => {
    const f = fixture(source); f.press();
    assert.equal(f.tug.state().phase, 'idle');
    assert.equal(f.scene.controls.enableRotate, false);
    f.document.dispatchEvent({ type: 'cl:sky-plot' });
    clean(f);
    assert.equal(f.scene.controls.enableRotate, true);
    assert.equal(f.tug.stats().grabs, 0);
    assert.equal(f.captureLog.length, 0);
  });

  test('public cancel keeps a pre-existing rotation lock', () => {
    const f = fixture(source, { rotate: false }); f.grab(); f.frame();
    f.tug.cancel(); clean(f);
    assert.equal(f.scene.controls.enableRotate, false);
  });

  test('the next gesture captures its own camera pose', () => {
    const f = fixture(source); f.grab(); f.frame(); f.tug.cancel();
    f.moveHost(15); const next = f.pose();
    f.grab(); f.moveHost(-8); f.frame();
    samePose(f, next, 'second drag');
    assert.equal(f.tug.stats().grabs, 2);
  });

  test('reduced motion release returns camera ownership and sleeps immediately', () => {
    const f = fixture(source, { reduced: true }), p = f.grab(); f.frame(4);
    f.pointer('pointerup', p[0] + 36, p[1] + 7);
    clean(f);
    assert.equal(f.scene.controls.enableRotate, true);
  });

  return cases;
}

if (require.main === module) {
  const count = runContract(fs.readFileSync(sourcePath, 'utf8'), line => console.log(line));
  console.log(count + '/' + count + ' sky tug camera contracts passed');
}
module.exports = { runContract };
