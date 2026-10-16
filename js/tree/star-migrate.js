(function () {
  'use strict';

  var DUR = 2.2;
  var STAGGER = 0.6;

  var st = 'stars';
  var ready = false;
  var frames = 0;
  var tAcc = 0;
  var kFrom = 1;
  var curK = 0;
  var plan = [];
  var lastPlaced = 0, lastTargets = 0, lastNames = 0, lastDups = 0;


  function sceneRef() {
    try { return (window.__cl && window.__cl.scene) || null; }
    catch (e) { return null; }
  }
  function sceneOk() {
    var sc = sceneRef();
    return !!(sc && typeof sc.setStarTargets === 'function');
  }
  function nodeOf(name) {
    var sc = sceneRef();
    if (!sc || typeof sc.nodeOf !== 'function') return null;
    try { return sc.nodeOf('c:' + name) || null; }
    catch (e) { return null; }
  }
  function anchorOk() {
    try {
      var A = window.CLTreeAnchor;
      return !!(A && typeof A.ready === 'function' && A.ready() &&
                typeof A.root === 'function' && A.root());
    }
    catch (e) { return false; }
  }
  function prefersReduced() {
    try {
      return !!(window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }
    catch (e) { return false; }
  }
  function degrade() {
    try {
      var c = window.__cl, v;
      if (c && typeof c.degrade === 'number') v = c.degrade;
      if (typeof v !== 'number' && typeof window.CL_DEGRADE === 'number') v = window.CL_DEGRADE;
      return typeof v === 'number' ? v : 0;
    }
    catch (e) { return 0; }
  }
  function muted() { return prefersReduced() || degrade() >= 2; }

  function stepDt(s) {
    var d = (s && typeof s.dt === 'number' && isFinite(s.dt)) ? s.dt : (1 / 60);
    if (d > 1) d /= 1000;
    if (d < 0) d = 0;
    if (d > 0.25) d = 0.25;
    return d;
  }

  function easeInOutCubic(t) {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  var swScratch = [0, 0, 0];

  function leafLocal(leaf) {
    try {
      if (!anchorOk() || !window.THREE || !leaf || !leaf.pos) return null;
      /* v36 摇曳：必须在**单位空间**里摇，再送进 anchor 矩阵 —— 顺序反了就不是
       * 「绕树根柔弯」而是「绕 anchor 之后的原点柔弯」，完全另一回事。
       * 调用的是全仓唯一的 CLTreeSway.bendInto()，与 ghost 的 1.8 万顶点逐字同一套
       * 算法（同一个高度剖面、同一张 sin/cos 表），所以星点不可能从枝头飘走。 */
      var p = leaf.pos, SW = window.CLTreeSway;
      if (SW && typeof SW.bendInto === 'function') {
        var q = SW.bendInto(p[0], p[1], p[2], swScratch);
        if (q && isFinite(q[0]) && isFinite(q[1]) && isFinite(q[2])) p = q;
      }
      var v = new window.THREE.Vector3().fromArray(p);
      v.applyMatrix4(window.CLTreeAnchor.root().matrix);
      if (!isFinite(v.x) || !isFinite(v.y) || !isFinite(v.z)) return null;
      return [v.x, v.y, v.z];
    }
    catch (e) { return null; }
  }


  function assignLeaves() {
    try {
      var story = (window.CLStory && typeof window.CLStory.get === 'function')
        ? window.CLStory.get() : null;
      if (!story) return null;
      var shape = (window.CLTreeShape && typeof window.CLTreeShape.build === 'function')
        ? window.CLTreeShape.build(story) : null;
      if (!shape || !shape.ok) return null;
      var res = (window.CLTreeLeaf && typeof window.CLTreeLeaf.assign === 'function')
        ? window.CLTreeLeaf.assign(shape, story) : null;
      return (res && res.leaves && res.byName) ? res : null;
    }
    catch (e) { return null; }
  }

  function buildPlan() {
    var res = assignLeaves();
    if (!res) return null;
    var leaves = res.leaves, byName = res.byName;
    var out = [], names = 0, key, idxs, j, pick, leaf;
    for (key in byName) {
      if (!Object.prototype.hasOwnProperty.call(byName, key)) continue;
      names++;
      idxs = byName[key];
      if (!idxs || !idxs.length) continue;
      pick = -1;
      for (j = 0; j < idxs.length; j++) {
        leaf = leaves[idxs[j]];
        if (leaf && leaf.dupIdx === 0) { pick = idxs[j]; break; }
      }
      if (pick < 0) pick = idxs[0];
      leaf = leaves[pick];
      if (!leaf || !leaf.pos) continue;
      if (!nodeOf(key)) continue;
      out.push({
        name: key,
        leaf: leaf,
        w: (typeof leaf.w === 'number' && isFinite(leaf.w)) ? leaf.w : 0,
        entry: (typeof leaf.entry === 'number' && isFinite(leaf.entry)) ? leaf.entry : -1,
        delay: 0
      });
    }
    out.sort(function (a, b) {
      var ea = a.entry, eb = b.entry;
      if (ea < 0 && eb >= 0) return 1;
      if (eb < 0 && ea >= 0) return -1;
      if (ea !== eb) return ea - eb;
      if (b.w !== a.w) return b.w - a.w;
      return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
    });
    var n = out.length, i, maxE = 0;
    for (i = 0; i < n; i++) if (out[i].entry > maxE) maxE = out[i].entry;
    for (i = 0; i < n; i++) {
      if (n <= 1) { out[i].delay = 0; continue; }
      out[i].delay = (maxE > 0 && out[i].entry >= 0)
        ? (out[i].entry / maxE) * STAGGER
        : STAGGER;
    }
    return { plan: out, names: names, dups: Math.max(0, leaves.length - names) };
  }


  function sceneSetTargets(map, k) {
    var sc = sceneRef();
    if (!sc || typeof sc.setStarTargets !== 'function') return false;
    try { sc.setStarTargets(map, k); return true; }
    catch (e) { return false; }
  }

  /* v42 forge：可插拔覆盖源。override(name, it) 返回 [x,y,z]（anchor.root().matrix 之后、与 leafLocal 同一坐标系）
   * 则该角色本次落点改用它；返回 null/undefined 则用叶位。每次 refresh 都重新问一遍（3 帧一次），
   * 所以「选中某事件 → 参与者飘到那根枝」这类瞬态不必自己维护状态，也不会被 refresh 冲掉。 */
  var override = null, lastOverride = 0;
  function setOverride(fn) { override = (typeof fn === 'function') ? fn : null; return !!override; }
  function askOverride(it) {
    if (!override) return null;
    try { var r = override(it.name, it); return (r && isFinite(r[0]) && isFinite(r[1]) && isFinite(r[2])) ? [r[0], r[1], r[2]] : null; }
    catch (e) { return null; }
  }

  function refresh(k, now) {
    var map = {}, placed = 0, targets = 0, i, it, nd, tp, ov = 0;
    for (i = 0; i < plan.length; i++) {
      it = plan[i];
      nd = nodeOf(it.name);
      if (!nd || !nd.pos) continue;
      tp = null;
      if (now >= it.delay) {
        tp = askOverride(it);
        if (tp) ov++; else tp = leafLocal(it.leaf);
        if (tp) placed++;
      }
      if (!tp) tp = [nd.pos.x, nd.pos.y, nd.pos.z];
      map[it.name] = tp;
      targets++;
    }
    sceneSetTargets(map, k);
    lastPlaced = placed;
    lastTargets = targets;
    lastOverride = ov;
    curK = k;
  }

  function snapBack() {
    sceneSetTargets(null);
    st = 'stars';
    curK = 0;
    tAcc = 0;
    lastPlaced = 0;
    lastTargets = 0;
  }


  function go(on) {
    on = !!on;
    try {
      if (!sceneOk()) return false;
      if (on) {
        if (st === 'plot' || st === 'flying') return true;
        if (!anchorOk() || !window.THREE) return false;
        var built = buildPlan();
        if (!built || !built.plan.length) return false;
        plan = built.plan;
        lastNames = built.names;
        lastDups = built.dups;
        tAcc = 0;
        kFrom = 1;
        if (muted()) {
          refresh(1, Infinity);
          st = 'plot';
        }
        else {
          refresh(0, 0);
          st = 'flying';
        }
        return true;
      }
      if (st === 'stars') return true;
      if (muted()) { snapBack(); return true; }
      kFrom = curK;
      tAcc = 0;
      st = 'returning';
      return true;
    }
    catch (e) { return false; }
  }

  function update(s) {
    if (!ready) return;
    try {
      frames++;
      var dt = stepDt(s);
      if (st === 'flying' || st === 'returning') tAcc += dt;
      if (muted()) {
        if (st === 'flying') { refresh(1, Infinity); st = 'plot'; tAcc = 0; }
        else if (st === 'returning') snapBack();
        return;
      }
      if (st === 'flying') {
        refresh(easeInOutCubic(tAcc / DUR), tAcc);
        if (tAcc >= DUR) { st = 'plot'; tAcc = 0; refresh(1, Infinity); }
      }
      else if (st === 'plot') {
        if (frames % 3 === 0) refresh(1, Infinity);
      }
      else if (st === 'returning') {
        refresh(kFrom * (1 - easeInOutCubic(tAcc / DUR)), Infinity);
        if (tAcc >= DUR) snapBack();
      }
    }
    catch (e) {  }
  }

  function onEvent(e) {
    var on = !!(e && e.detail && e.detail.on);
    go(on);
  }

  function build() {
    try { document.removeEventListener('cl:tree-plotline', onEvent); } catch (e) {}
    try { document.addEventListener('cl:tree-plotline', onEvent, false); } catch (e) {}
    ready = true;
    return true;
  }

  function dispose() {
    try { document.removeEventListener('cl:tree-plotline', onEvent); } catch (e) {}
    try { snapBack(); } catch (e) {}
    plan = [];
    ready = false;
  }

  function stats() {
    var waves = 0, prev = null, i;
    for (i = 0; i < plan.length; i++) {
      if (prev === null || plan[i].delay !== prev) { waves++; prev = plan[i].delay; }
    }
    return {
      ready: !!ready,
      state: st,
      k: Math.round(curK * 1000) / 1000,
      placed: lastPlaced,
      targets: lastTargets,
      names: lastNames,
      dups: lastDups,
      ms: Math.round(tAcc * 1000),
      muted: muted(),
      waves: waves,
      stagger: STAGGER,
      order: plan.length ? plan.map(function (p) { return p.entry; }) : [],
      head: plan.length ? plan.slice(0, 4).map(function (p) {
        return { n: p.name, e: p.entry, d: Math.round(p.delay * 1000) / 1000 };
      }) : []
    };
  }

  var API = {
    name: 'star-migrate',
    build: build,
    update: update,
    dispose: dispose,
    setOn: function (v) { return go(v); },
    go: go,
    toggle: function () {
      var on = !(st === 'plot' || st === 'flying');
      return go(on);
    },
    state: function () { return st; },
    stats: stats,
    setOverride: setOverride,
    overrideCount: function () { return lastOverride; }
  };

  window.CLStarMigrate = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
