/* @role micro · @owns js/orbit3d-cinema.js · @budget drawcalls=0 js_ms=0.05 · @contract v47+v48 */
/* v48 orbit3d-cinema · 相机慢漂：差量式极小三轴漂移（truck/升降/推拉），经 OrbitControls 等价绕 target 微转。
   任一用户输入即暂停，6 秒后淡入。只对 cam.position 做差量加法，不改 controls / target，0 draw call。
   降级：prefers-reduced-motion → k 归零；CLOrbit3DLayer.stats().tier===2 → 同归零。 */
(function (g) {
  'use strict';

  var name = 'orbit3d-cinema';
  var version = '48';

  var T = null;
  var cam = null;
  var lastRoot = null;
  var wrapped = null;
  var bound = false;

  var lastT = null;
  var k = 0;
  var px = 0, py = 0, pz = 0;
  var pauseUntil = 0;
  var enabled = true;
  var onState = false;
  var reduced = false;
  var updates = 0;

  function r4(v) { return Math.round(v * 10000) / 10000; }
  function nowT() { return lastT === null ? 0 : lastT; }

  function bindInput() {
    if (bound || !g.addEventListener) return;
    bound = true;
    var hit = function () { pauseUntil = nowT() + 6; };
    g.addEventListener('pointerdown', hit, true);
    g.addEventListener('wheel', hit, true);
    g.addEventListener('keydown', hit, true);
  }

  function findDish(root) {
    if (!root || !root.children) return null;
    var i, j, c, d;
    for (i = 0; i < root.children.length; i++) {
      c = root.children[i];
      if (c.renderOrder === -29) return c;
      d = c.children;
      if (d) for (j = 0; j < d.length; j++) if (d[j].renderOrder === -29) return d[j];
    }
    return null;
  }

  function wrapDish(L) {
    if (!L || typeof L.root !== 'function') return null;
    var root = L.root();
    if (!root) return null;
    if (root !== lastRoot) { lastRoot = root; wrapped = null; }
    if (wrapped) return cam;
    var dish = findDish(root);
    if (!dish) return null;
    wrapped = dish;
    var prev = dish.onBeforeRender;
    dish.onBeforeRender = function (r, sc, c) {
      if (prev) prev.apply(this, arguments);
      cam = c || cam;
    };
    return cam;
  }

  function ensureCam() {
    if (cam) return cam;
    var G = g.CLOrbit3DGrade;
    if (G && typeof G.camera === 'function') {
      var c = G.camera();
      if (c) { cam = c; return cam; }
    }
    return wrapDish(g.CLOrbit3DLayer);
  }

  function build(o) {
    if (o && o.T) T = o.T;
    bindInput();
  }

  function update(s) {
    if (!s) return;
    var t = s.t;
    if (typeof t !== 'number' || !isFinite(t)) return;
    var dt = lastT === null ? 0 : t - lastT;
    if (dt < 0) dt = 0;
    if (dt > 0.05) dt = 0.05;
    lastT = t;
    updates += 1;

    var mq = g.matchMedia;
    reduced = !!(mq && mq('(prefers-reduced-motion: reduce)').matches);

    var V = g.CLPlotOrbitView;
    var L = g.CLOrbit3DLayer;
    var ls = (L && typeof L.stats === 'function') ? L.stats() : null;
    var vis = false;
    if (V && typeof V.visible === 'function') vis = !!V.visible();

    var on = enabled && vis && !reduced && !!ls && ls.fade > 0.5 && ls.tier !== 2 && t >= pauseUntil;
    onState = on;

    var goal = 0;
    if (on) {
      var fe = -1;
      if (V && typeof V.state === 'function') fe = V.state().focusEv;
      goal = fe >= 0 ? 0.4 : 1;
    }
    var step = dt * (goal > k ? 0.6 : 6.0);   /* 审核修正：用户一碰就快停（~0.17 s 到 1/e），淡入仍慢（~3 s） */
    if (step > 1) step = 1;
    k += (goal - k) * step;

    var R = (ls && ls.R) || 400;
    var TAU = Math.PI * 2;
    var ox = k * 0.05 * R * Math.sin(TAU * t / 41);
    var oy = k * 0.025 * R * Math.sin(TAU * t / 67 + 0.7);
    var oz = k * 0.03 * R * Math.sin(TAU * t / 29 + 2.1);

    ensureCam();
    if (cam && cam.matrixWorld && cam.position) {
      var e = cam.matrixWorld.elements;
      var rx = e[0], ry = e[1], rz = e[2];
      var ux = e[4], uy = e[5], uz = e[6];
      var bx = e[8], by = e[9], bz = e[10];
      var dx = ox - px, dy = oy - py, dz = oz - pz;
      var pos = cam.position;
      pos.x += rx * dx + ux * dy + bx * dz;
      pos.y += ry * dx + uy * dy + by * dz;
      pos.z += rz * dx + uz * dy + bz * dz;
      px = ox; py = oy; pz = oz;
    }
  }

  function setOn(b) { enabled = !!b; }

  function pause(sec) {
    if (typeof sec !== 'number' || !isFinite(sec) || sec < 0) sec = 0;
    pauseUntil = nowT() + sec;
  }

  function kf() { return k; }

  function stats() {
    return {
      name: name,
      version: version,
      ready: !!cam,
      on: onState,
      enabled: enabled,
      k: r4(k),
      applied: [r4(px), r4(py), r4(pz)],
      pauseUntil: r4(pauseUntil),
      t: r4(nowT()),
      reduced: reduced,
      updates: updates
    };
  }

  var API = {
    name: name,
    version: version,
    build: build,
    update: update,
    setOn: setOn,
    pause: pause,
    k: kf,
    stats: stats
  };

  g.CLOrbit3DCinema = API;

  var isTree = /[?&](tree|treestage)=1(?:&|$)/.test(String((g.location && g.location.search) || ''));   /* 契约 §1：剧情树逃生口页面不注册 */
  if (g.CLArcana && typeof g.CLArcana.register === 'function' && !isTree) {
    g.CLArcana.register(API);
  }
  bindInput();
})(typeof window !== 'undefined' ? window : this);
