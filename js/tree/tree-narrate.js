/*!
 * @role component
 * @owns js/tree-narrate.js
 * @budget step() O(1) amortized (bounded by dt/dwell page count) + O(1) state; progress()/stats() O(n) read-through; no timers, no allocation in hot path beyond the returned plain object
 * @contract v43
 *
 * Pure playback kernel. Has no clock, no timer, no animation frame: time enters
 * only through step(dtMs). The UI layer feeds fixed deltas and drives redraw.
 */
(function (global) {
  'use strict';

  var NAME = 'tree-narrate';

  var DEF_DWELL = 2.4;
  var MIN_DWELL = 0.4;
  var MAX_DWELL = 30;
  var SPEED_STEPS = [0.5, 1, 2, 4];
  var MS_PER_SEC = 1000;

  var _playing = false;
  var _acc = 0;
  var _dwell = DEF_DWELL;
  var _speed = 1;
  var _loop = false;
  var _done = false;
  var _ticks = 0;

  function events() {
    return global.CLTreeEvents || null;
  }

  function hasEvents() {
    var e = global.CLTreeEvents;
    return !!(e && typeof e.pick === 'function' && typeof e.next === 'function');
  }

  function readIdx() {
    var e = events();
    if (!e || typeof e.get !== 'function') return -1;
    try {
      var cur = e.get();
      if (cur && typeof cur.evIdx === 'number') return cur.evIdx;
      if (typeof cur === 'number') return cur;
    } catch (err) { /* silent by contract */ }
    return -1;
  }

  function readDomain() {
    var e = events();
    if (!e || typeof e.domain !== 'function') return [];
    try {
      var d = e.domain();
      return (d && d.length) ? d : [];
    } catch (err) { /* silent by contract */ }
    return [];
  }

  function pick(v) {
    var e = events();
    if (!e || typeof e.pick !== 'function') return;
    try { e.pick(v); } catch (err) { /* silent by contract */ }
  }

  function clampDwell(s) {
    if (typeof s !== 'number' || !isFinite(s)) return _dwell;
    if (s < MIN_DWELL) return MIN_DWELL;
    if (s > MAX_DWELL) return MAX_DWELL;
    return s;
  }

  function nearestStep(v) {
    if (typeof v !== 'number' || !isFinite(v)) return _speed;
    var best = SPEED_STEPS[0];
    var bestGap = Math.abs(v - best);
    var i, gap;
    for (i = 1; i < SPEED_STEPS.length; i += 1) {
      gap = Math.abs(v - SPEED_STEPS[i]);
      if (gap < bestGap) {
        best = SPEED_STEPS[i];
        bestGap = gap;
      }
    }
    return best;
  }

  function play() {
    if (!hasEvents()) return false;
    var idx = readIdx();
    if (idx < 0) {
      var d0 = readDomain();
      if (!d0.length) return false;
      pick(d0[0]);
      _done = false;
      _acc = 0;
    } else if (_done) {
      var d1 = readDomain();
      if (!d1.length) return false;
      pick(d1[0]);
      _done = false;
      _acc = 0;
    } else {
      _acc = 0;
    }
    _playing = true;
    return true;
  }

  function pause() {
    _playing = false;
    return false;
  }

  function toggle() {
    if (_playing) {
      pause();
      return false;
    }
    return play();
  }

  function playing() {
    return _playing;
  }

  function step(dtMs) {
    if (!hasEvents()) return false;
    if (!_playing) return false;
    if (typeof dtMs !== 'number' || !isFinite(dtMs) || dtMs < 0) return false;

    var span = _dwell * MS_PER_SEC;
    if (!(span > 0)) return false;

    var e = events();
    _acc += dtMs;
    var changed = false;

    while (_acc >= span) {
      _acc -= span;

      var before = readIdx();
      var moved = before;
      try {
        var v = e.next();
        if (typeof v === 'number') moved = v;
      } catch (err) { /* silent by contract */ }

      var after = readIdx();
      var advanced = (after !== before) || (moved !== before);

      if (advanced) {
        _ticks += 1;
        changed = true;
        continue;
      }

      if (_loop) {
        var d = readDomain();
        if (d.length) {
          pick(d[0]);
          _ticks += 1;
          changed = true;
        }
        continue;
      }

      pause();
      _done = true;
      break;
    }

    return changed;
  }

  function setSpeed(v) {
    _speed = nearestStep(v);
    _dwell = clampDwell(DEF_DWELL / _speed);
    return _speed;
  }

  function speed() {
    return _speed;
  }

  function setDwell(s) {
    _dwell = clampDwell(s);
    return _dwell;
  }

  function dwell() {
    return _dwell;
  }

  function setLoop(b) {
    _loop = !!b;
    return _loop;
  }

  function loop() {
    return _loop;
  }

  function progress() {
    return {
      idx: readIdx(),
      n: readDomain().length,
      done: _done,
      playing: _playing,
      dwell: _dwell,
      speed: _speed
    };
  }

  function stats() {
    return {
      ready: hasEvents(),
      playing: _playing,
      idx: readIdx(),
      n: readDomain().length,
      done: _done,
      dwell: _dwell,
      speed: _speed,
      loop: _loop,
      ticks: _ticks
    };
  }

  global.CLTreeNarrate = {
    name: NAME,
    play: play,
    pause: pause,
    toggle: toggle,
    playing: playing,
    step: step,
    setSpeed: setSpeed,
    speed: speed,
    setDwell: setDwell,
    dwell: dwell,
    setLoop: setLoop,
    loop: loop,
    progress: progress,
    stats: stats
  };
}(typeof window !== 'undefined' ? window : this));
