// @role component (tree-follow & tree-follow-drive)
// @owns js/tree-follow.js
// @budget n/a — 纯数值核 step() O(1) + 帧驱动（<30us/frame，缓存解析）
// @contract v46
/**
 * tree-follow.js - H4: 跟读双生合并（CLTreeFollow 纯核 + CLTreeFollowDrive 驱动）
 * 将原有散落的双生文件合并为统一的 tree-follow.js，提供双导出：
 *   - window.CLTreeFollow: 瞄准偏置滤波与纯数值解算核
 *   - window.CLTreeFollowDrive: 帧驱动、微秒级节流与 Arcana 总线挂接
 */
(function () {
  'use strict';

  /* =========================================================================
   * 1. CLTreeFollow 纯数值核
   * ========================================================================= */
  var DEFAULT_GAIN = 0.55;
  var DEFAULT_MAX = 150;
  var DEFAULT_TAU = 0.5;
  var DEFAULT_DEAD = 50;
  var GAIN_LO = 0, GAIN_HI = 1;
  var MAX_LO = 0, MAX_HI = 1200;
  var TAU_LO = 0.05, TAU_HI = 5;
  var DEAD_LO = 0, DEAD_HI = 600;
  var SNAP_EPS = 0.05;
  var MS_PER_S = 1000;

  var _on = true;
  var _paused = false;
  var _gain = DEFAULT_GAIN;
  var _max = DEFAULT_MAX;
  var _tau = DEFAULT_TAU;
  var _dead = DEFAULT_DEAD;
  var _bias = { x: 0, y: 0, z: 0 };
  var _aim = null;
  var _ref = null;
  var _ticks = 0;
  var _lastDT = 0;

  function clamp(v, lo, hi) {
    if (v < lo) { return lo; }
    if (v > hi) { return hi; }
    return v;
  }

  function finite(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function len3(p) {
    return Math.sqrt(p.x * p.x + p.y * p.y + p.z * p.z);
  }

  function cp(p) {
    return p ? { x: p.x, y: p.y, z: p.z } : null;
  }

  function setOn(b) { _on = !!b; return _on; }
  function on() { return _on; }

  function aim(x, y, z) {
    if (!finite(x) || !finite(y) || !finite(z)) { _aim = null; return null; }
    _aim = { x: x, y: y, z: z };
    return cp(_aim);
  }
  function aimPoint() { return cp(_aim); }

  function ref(x, y, z) {
    if (!finite(x) || !finite(y) || !finite(z)) { _ref = null; return null; }
    _ref = { x: x, y: y, z: z };
    return cp(_ref);
  }
  function refPoint() { return cp(_ref); }

  function bias() { return { x: _bias.x, y: _bias.y, z: _bias.z }; }

  function step(dtMs) {
    if (!finite(dtMs) || dtMs < 0) { return bias(); }
    if (_paused) { return bias(); }

    var has = !!(_aim && _ref);
    var dt = dtMs / MS_PER_S;
    var desX = 0, desY = 0, desZ = 0;

    if (_on && has) {
      var dx = _aim.x - _ref.x;
      var dy = _aim.y - _ref.y;
      var dz = _aim.z - _ref.z;
      var L = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (L > _dead) {
        var k = Math.min((L - _dead) * _gain, _max) / L;
        desX = dx * k;
        desY = dy * k;
        desZ = dz * k;
      }
    }

    if (dt > 0) {
      var alpha = 1 - Math.exp(-dt / _tau);
      _bias.x += (desX - _bias.x) * alpha;
      _bias.y += (desY - _bias.y) * alpha;
      _bias.z += (desZ - _bias.z) * alpha;
      _ticks += 1;
      _lastDT = dtMs;
    }

    if ((!_on || !has) && len3(_bias) < SNAP_EPS) {
      _bias.x = 0;
      _bias.y = 0;
      _bias.z = 0;
    }

    return bias();
  }

  function setGain(v) {
    if (!finite(v)) { return _gain; }
    _gain = clamp(v, GAIN_LO, GAIN_HI);
    return _gain;
  }
  function gain() { return _gain; }

  function setMax(v) {
    if (!finite(v)) { return _max; }
    _max = clamp(v, MAX_LO, MAX_HI);
    return _max;
  }
  function max() { return _max; }

  function setTau(v) {
    if (!finite(v)) { return _tau; }
    _tau = clamp(v, TAU_LO, TAU_HI);
    return _tau;
  }
  function tau() { return _tau; }

  function setDead(v) {
    if (!finite(v)) { return _dead; }
    _dead = clamp(v, DEAD_LO, DEAD_HI);
    return _dead;
  }
  function dead() { return _dead; }

  function setPause(b) { _paused = !!b; return _paused; }
  function paused() { return _paused; }

  function statsFollow() {
    var has = !!(_aim && _ref);
    return {
      ready: true,
      on: _on,
      paused: _paused,
      has: has,
      ignore: !_on,
      ticks: _ticks,
      lastDT: _lastDT,
      bias: { x: _bias.x, y: _bias.y, z: _bias.z },
      aim: cp(_aim),
      ref: cp(_ref),
      gain: _gain,
      max: _max,
      tau: _tau,
      dead: _dead,
      name: 'tree-follow'
    };
  }

  var APIFollow = {
    name: 'tree-follow',
    setOn: setOn,
    on: on,
    aim: aim,
    aimPoint: aimPoint,
    ref: ref,
    refPoint: refPoint,
    step: step,
    bias: bias,
    setGain: setGain,
    gain: gain,
    setMax: setMax,
    max: max,
    setTau: setTau,
    tau: tau,
    setDead: setDead,
    dead: dead,
    setPause: setPause,
    paused: paused,
    stats: statsFollow
  };

  window.CLTreeFollow = APIFollow;

  /* =========================================================================
   * 2. CLTreeFollowDrive 帧驱动
   * ========================================================================= */
  var PUSH_EPS = 1e-4;
  var FRAME_FALLBACK = 0.016;
  var SYNC_DT = 0.016;
  var DT_MAX = 0.1;
  var DT_JUMP = 0.25;
  var DEGRADE_LIMIT = 2;
  var EPS = 1e-9;

  var _driveTicks = 0;
  var _lastT = null;
  var _calm = false;
  var _degrade = 0;
  var _driveDt = 0;
  var _lastEv = -1;
  var _point = null;
  var _driveRef = null;
  var _pushed = { x: 0, y: 0, z: 0 };
  var _cEv = -999999;
  var _cShape = null;
  var _cPt = null;
  var _ptrHooked = false;
  var _mounted = false;

  function documentHidden() {
    try {
      return !!(document && document.hidden);
    } catch (e) {
      return false;
    }
  }

  function sceneOf() {
    try {
      if (window.__cl && window.__cl.scene) return window.__cl.scene;
    } catch (e) {}
    try {
      if (window.CLApp && window.CLApp.scene && typeof window.CLApp.scene === 'function') {
        var s = window.CLApp.scene();
        if (s) return s;
      }
    } catch (e) {}
    return null;
  }

  function stageActive() {
    try {
      var T = window.CLTreeStage;
      if (T && T.stats) {
        var st = T.stats();
        if (st && st.active === true) return true;
      }
    } catch (e) {}
    return false;
  }

  function evIdxOf() {
    try {
      var E = window.CLTreeEvents;
      if (E && E.get) {
        var g = E.get();
        if (g && typeof g.evIdx === 'number' && isFinite(g.evIdx) && g.evIdx >= 0) {
          return g.evIdx;
        }
      }
    } catch (e) {}
    return -1;
  }

  function pointFor(ev) {
    var shape = null;
    try {
      var G = window.CLTreeGhost;
      if (G && G.shapeOf) shape = G.shapeOf();
    } catch (e) {
      shape = null;
    }
    if (_cEv === ev && _cShape === shape) return _cPt;
    _cEv = ev;
    _cShape = shape;
    _cPt = null;
    try {
      if (shape && shape.twigs && shape.twigs.length) {
        var twigs = shape.twigs;
        for (var i = 0; i < twigs.length; i++) {
          var tw = twigs[i];
          if (tw && tw.evIdx === ev && tw.pts && tw.pts.length) {
            var mid = tw.pts[Math.floor(tw.pts.length / 2)];
            var A = window.CLTreeAnchor;
            if (A && A.toWorld) {
              var w = A.toWorld(mid);
              if (w && isFinite(w.x) && isFinite(w.y) && isFinite(w.z)) {
                _cPt = { x: w.x, y: w.y, z: w.z };
              }
            }
            break;
          }
        }
      }
    } catch (e) {
      _cPt = null;
    }
    return _cPt;
  }

  function refFromScene(sc) {
    if (!sc || !sc.aimInfo) return null;
    try {
      var ai = sc.aimInfo();
      if (!ai) return null;
      if (!isFinite(ai.tx) || !isFinite(ai.ty) || !isFinite(ai.tz)) return null;
      if (!isFinite(ai.ax) || !isFinite(ai.ay) || !isFinite(ai.az)) return null;
      return { x: ai.tx - ai.ax, y: ai.ty - ai.ay, z: ai.tz - ai.az };
    } catch (e) {
      return null;
    }
  }

  function tickDrive(dtSec, isSync) {
    _driveTicks++;
    var F = window.CLTreeFollow;
    if (!F) return;

    var sc = sceneOf();
    var onVal = false;
    try {
      onVal = !!F.on();
    } catch (e) {
      onVal = false;
    }

    var pt = null;
    var rf = null;
    var ev = -1;
    if (onVal && stageActive()) {
      ev = evIdxOf();
      if (ev >= 0) {
        pt = pointFor(ev);
        rf = refFromScene(sc);
      }
    }

    _lastEv = ev;
    _point = pt ? { x: pt.x, y: pt.y, z: pt.z } : null;
    _driveRef = rf ? { x: rf.x, y: rf.y, z: rf.z } : null;

    if (pt && rf) {
      F.aim(pt.x, pt.y, pt.z);
      F.ref(rf.x, rf.y, rf.z);
    } else {
      F.aim(null);
      F.ref(null);
    }

    var dtMs = dtSec * MS_PER_S;
    var b = F.step(dtMs);

    var curScene = sceneOf();
    if (curScene && curScene.setTreeFollowBias) {
      var changed = Math.abs(b.x - _pushed.x) > PUSH_EPS ||
                    Math.abs(b.y - _pushed.y) > PUSH_EPS ||
                    Math.abs(b.z - _pushed.z) > PUSH_EPS;
      if (changed) {
        curScene.setTreeFollowBias(b.x, b.y, b.z);
        _pushed.x = b.x;
        _pushed.y = b.y;
        _pushed.z = b.z;
        _calm = false;
      } else {
        _calm = (Math.abs(b.x) < EPS && Math.abs(b.y) < EPS && Math.abs(b.z) < EPS);
      }
    }
  }

  function updateDrive(dtSec) {
    if (documentHidden()) {
      _lastT = null;
      return;
    }

    var dt = FRAME_FALLBACK;
    if (typeof dtSec === 'number' && isFinite(dtSec) && dtSec > 0) {
      dt = dtSec;
    } else {
      var now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
      if (_lastT === null) {
        _lastT = now;
        dt = FRAME_FALLBACK;
      } else {
        dt = (now - _lastT) / MS_PER_S;
        _lastT = now;
      }
    }

    if (dt > DT_JUMP) {
      dt = FRAME_FALLBACK;
    } else if (dt > DT_MAX) {
      _degrade++;
      if (_degrade > DEGRADE_LIMIT) {
        dt = FRAME_FALLBACK;
      }
    } else {
      _degrade = 0;
    }

    _driveDt = dt;
    tickDrive(dt, false);
  }

  function syncDrive(dtSec) {
    var dt = (typeof dtSec === 'number' && isFinite(dtSec) && dtSec > 0) ? dtSec : SYNC_DT;
    _driveDt = dt;
    tickDrive(dt, true);
  }

  function statsDrive() {
    var F = window.CLTreeFollow;
    var st = null;
    try {
      if (F && F.stats) st = F.stats();
    } catch (e) {
      st = null;
    }
    return {
      name: 'tree-follow-drive',
      ticks: _driveTicks,
      lastEv: _lastEv,
      hasPoint: !!_point,
      point: _point ? { x: _point.x, y: _point.y, z: _point.z } : null,
      hasRef: !!_driveRef,
      ref: _driveRef ? { x: _driveRef.x, y: _driveRef.y, z: _driveRef.z } : null,
      calm: _calm,
      lastDt: _driveDt,
      degrade: _degrade,
      pushed: { x: _pushed.x, y: _pushed.y, z: _pushed.z },
      follow: st,
      mounted: _mounted
    };
  }

  function onPointerDown() {
    try {
      var F = window.CLTreeFollow;
      if (F && F.setPause) F.setPause(true);
    } catch (e) {}
  }

  function onPointerUp() {
    try {
      var F = window.CLTreeFollow;
      if (F && F.setPause) F.setPause(false);
    } catch (e) {}
  }

  function hookPointer() {
    if (_ptrHooked) return;
    try {
      if (window.addEventListener) {
        window.addEventListener('pointerdown', onPointerDown, true);
        window.addEventListener('pointerup', onPointerUp, true);
        _ptrHooked = true;
      }
    } catch (e) {}
  }

  var APIDrive = {
    name: 'tree-follow-drive',
    update: updateDrive,
    sync: syncDrive,
    stats: statsDrive
  };

  window.CLTreeFollowDrive = APIDrive;

  /* =========================================================================
   * 3. Arcana 总线挂接
   * ========================================================================= */
  function hookArcana() {
    try {
      if (window.CLArcana && window.CLArcana.register) {
        window.CLArcana.register(APIFollow);
      }
    } catch (e) {}
    try {
      hookPointer();
      if (window.CLArcana && window.CLArcana.register) {
        window.CLArcana.register(APIDrive);
        _mounted = true;
      }
    } catch (e2) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hookArcana);
  } else {
    hookArcana();
  }
})();
