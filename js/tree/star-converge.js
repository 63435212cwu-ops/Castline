/* @role component · @owns js/star-converge.js · @budget dom_nodes=0 · @contract v41 */
(function () {
  'use strict';

  /* 契约允许的固定轮询参数：100ms 轮询、最长 15s（v41 冻结） */
  var POLL_MS = 100;
  var POLL_MAX = 15000;

  var RING = 0.035;              /* 单位空间环偏移，非 px/ms */
  var TWO_PI = Math.PI * 2;
  var NAME = 'star-converge';

  var _on = true;
  var _ready = false;
  var _calls = 0;
  var _timer = null;
  var _scratch = [0, 0, 0];
  var _vec = null;               /* 复用一个 THREE.Vector3 */
  var _tipCache = null;          /* {evIdx, tip} 一帧内复用 */
  var _twigsRef = null;          /* twigs 引用变了即作废缓存 */

  function W() { return typeof window !== 'undefined' ? window : null; }
  function eventsAPI() { var w = W(); return w ? w.CLTreeEvents : null; }
  function ghostAPI() { var w = W(); return w ? w.CLTreeGhost : null; }
  function swayAPI() { var w = W(); return w ? w.CLTreeSway : null; }
  function anchorAPI() { var w = W(); return w ? w.CLTreeAnchor : null; }
  function threeAPI() { var w = W(); return w ? w.THREE : null; }

  function namesOf(ev, evIdx) {
    var info = null;
    try { info = (ev && typeof ev.info === 'function') ? ev.info(evIdx) : null; } catch (e) { info = null; }
    /* 主控修：CLTreeEvents.info() 的参与者字段实为 characters（契约 v42 写成 names 是主控笔误），三种写法都兼容 */
    return (info && (info.characters || info.names || info.cast)) || [];
  }

  function findTip(evIdx, twigs) {
    if (_tipCache && _twigsRef === twigs && _tipCache.evIdx === evIdx) return _tipCache.tip;
    var tip = null;
    for (var i = 0; i < twigs.length; i++) {
      var t = twigs[i];
      if (t && t.evIdx === evIdx && t.pts && t.pts.length) {
        tip = t.pts[t.pts.length - 1];
        break;
      }
    }
    _twigsRef = twigs;
    _tipCache = { evIdx: evIdx, tip: tip };
    return tip;
  }

  /** 位置归一：支持 [x,y,z] / {pos} / 沿 path.pts 的 t（0..1）三种。 */
  function posFrom(x, path) {
    if (!x) return null;
    if (x.pos && x.pos.length >= 3 && isFinite(x.pos[0]) && isFinite(x.pos[1]) && isFinite(x.pos[2])) {
      return [x.pos[0], x.pos[1], x.pos[2]];
    }
    if (x.length >= 3 && isFinite(x[0]) && isFinite(x[1]) && isFinite(x[2])) {
      return [x[0], x[1], x[2]];
    }
    var t = isFinite(x) ? x : (isFinite(x.at) ? x.at : null);
    if (t != null && path && path.pts && path.pts.length) {
      var u = Math.max(0, Math.min(1, t)) * (path.pts.length - 1), a = Math.floor(u),
          b = Math.min(path.pts.length - 1, a + 1), f = u - a;
      return [
        path.pts[a][0] * (1 - f) + path.pts[b][0] * f,
        path.pts[a][1] * (1 - f) + path.pts[b][1] * f,
        path.pts[a][2] * (1 - f) + path.pts[b][2] * f
      ];
    }
    return null;
  }

  /** 被点线上下文（可选）：D 若在 get()/threadOf() 里给出 threadId，就用它取本线 occurrence。
   *  没有也不硬造——回退 canonical anchor，再回退 legacy twig 尖。 */
  function contextThreadId(ev, g, evIdx) {
    if (g && g.threadId != null && g.threadId !== '') return String(g.threadId);
    if (g && g.thread != null && g.thread !== '') return String(g.thread);
    if (ev && typeof ev.threadOf === 'function') {
      try { var th = ev.threadOf(evIdx); if (th && th.id != null) return String(th.id); } catch (e) {}
    }
    return '';
  }

  function occurrenceOf(sh, tid, evIdx) {
    var path = sh && sh.threadPaths && sh.threadPaths[tid];
    if (!path) return null;
    var ep = path.eventPositions;
    if (ep && !ep.length && ep[evIdx]) return posFrom(ep[evIdx], path);
    if (path.evPos && path.evPos[evIdx]) return posFrom(path.evPos[evIdx], path);
    if (ep && ep.length && path.events) {
      for (var i = 0; i < path.events.length; i++) {
        if (Math.floor(path.events[i]) === evIdx) return posFrom(ep[i], path);
      }
    }
    return null;
  }

  /** 汇聚中心：先取被点线的本线 occurrence；无 threadId 才用全局 canonical eventAnchors；
   *  非 logical 保留 legacy 的 twig 末端行为。取不到就 null，不硬造中心。 */
  function centerOf(sh, evIdx, tid) {
    var occ = tid ? occurrenceOf(sh, tid, evIdx) : null;
    if (occ) return occ;
    var ea = sh && sh.logical === true && sh.eventAnchors ? sh.eventAnchors[evIdx] : null;
    if (ea && ea.pos && ea.pos.length >= 3 &&
        isFinite(ea.pos[0]) && isFinite(ea.pos[1]) && isFinite(ea.pos[2])) {
      return ea.pos;
    }
    return findTip(evIdx, (sh && sh.twigs) || []);
  }

  function target(name) {
    _calls++;
    if (!_on) return null;
    var ev = eventsAPI();
    if (!ev || typeof ev.get !== 'function') return null;
    var g = null;
    try { g = ev.get(); } catch (e) { g = null; }
    if (!g || typeof g.evIdx !== 'number' || g.evIdx < 0) return null;
    var evIdx = g.evIdx;

    var names = namesOf(ev, evIdx);
    var n = names.length;
    var i = -1;
    for (var k = 0; k < n; k++) { if (names[k] === name) { i = k; break; } }
    if (i < 0 || n === 0) return null;

    var ghost = ghostAPI();
    if (!ghost || typeof ghost.shapeOf !== 'function') return null;
    var sh = ghost.shapeOf();
    var tid = contextThreadId(ev, g, evIdx);
    var center = centerOf(sh, evIdx, tid);
    if (!center) return null;

    /* 环偏移：单参与者精确落中心；多参与者绕锚点在一个**有限半径**的环上分开。
     * 竖直分量用 sin(ang)（有界、对称），不再用 0.01*i 这种随序号无限增长的偏移。 */
    var p;
    if (n <= 1) {
      p = [center[0], center[1], center[2]];
    } else {
      var ang = (i / n) * TWO_PI;
      p = [
        center[0] + RING * Math.cos(ang),
        center[1] + RING * 0.35 * Math.sin(ang),
        center[2] + RING * Math.sin(ang)
      ];
    }

    var q = p;
    var sway = swayAPI();
    if (sway && typeof sway.bendInto === 'function') {
      try { q = sway.bendInto(p[0], p[1], p[2], _scratch) || p; } catch (e) { q = p; }
    }

    var an = anchorAPI();
    var TH = threeAPI();
    if (an && TH && typeof an.root === 'function') {
      var root = null;
      try { root = an.root(); } catch (e) { root = null; }
      if (root && root.matrix) {
        if (!_vec) _vec = new TH.Vector3();
        _vec.fromArray(q).applyMatrix4(root.matrix);
        return [_vec.x, _vec.y, _vec.z];
      }
    }
    return [q[0], q[1], q[2]];
  }

  function current() {
    var ev = eventsAPI();
    if (!ev || typeof ev.get !== 'function') return { evIdx: -1, names: [], n: 0 };
    var g = null;
    try { g = ev.get(); } catch (e) { g = null; }
    if (!g || typeof g.evIdx !== 'number' || g.evIdx < 0) return { evIdx: -1, names: [], n: 0 };
    var names = namesOf(ev, g.evIdx);
    return { evIdx: g.evIdx, names: names.slice ? names.slice() : names, n: names.length };
  }

  function setOn(b) {
    _on = !!b;
    if (!_on) { _tipCache = null; _twigsRef = null; }
    return _on;
  }

  function isOn() { return _on; }

  function attach() {
    var w = W();
    var m = w ? w.CLStarMigrate : null;
    if (!m || typeof m.setOverride !== 'function') return false;
    m.setOverride(function (name) { return target(name); });
    _ready = true;
    if (_timer !== null) { clearInterval(_timer); _timer = null; }
    return true;
  }

  function boot() {
    if (attach()) return;
    var started = Date.now();
    _timer = setInterval(function () {
      if (attach()) return;
      if (Date.now() - started > POLL_MAX) {
        clearInterval(_timer);
        _timer = null;
      }
    }, POLL_MS);
  }

  function stats() {
    var ev = eventsAPI();
    var g = null;
    try { g = (ev && typeof ev.get === 'function') ? ev.get() : null; } catch (e) { g = null; }
    var evIdx = (g && typeof g.evIdx === 'number') ? g.evIdx : -1;
    var n = evIdx >= 0 ? namesOf(ev, evIdx).length : 0;
    return { on: _on, ready: _ready, evIdx: evIdx, n: n, calls: _calls };
  }

  window.CLStarConverge = {
    name: NAME,
    target: target,
    current: current,
    setOn: setOn,
    on: isOn,
    stats: stats
  };

  boot();
})();
