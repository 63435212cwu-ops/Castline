(function (root) {
  'use strict';

  var PI = Math.PI, TWO_PI = PI * 2;
  var FRONT = -PI / 2;

  var DEF = {
    IDLE_SPIN: 0.02,
    FOCUS_MS: 900,
    PULSE_MS: 14000,
    FADE_MS: 400,
    HOLD_MS: 3000,
    RAMP_MS: 1200,
    FLASH_MS: 600,
    CYCLE_MS: 9400,
    ENVELOPE_AMP: 0.14,
    GAIN_MS: 320,
    DT_MAX: 0.05
  };

  var TIER = {
    high: { breath: 1, pulse: 1 },
    mid:  { breath: 0.7, pulse: 1 },
    low:  { breath: 0, pulse: 1 }
  };


  function wrapAngle(a) {
    a = +a;
    if (!isFinite(a)) return 0;
    a = a % TWO_PI;
    if (a > PI) a -= TWO_PI;
    else if (a <= -PI) a += TWO_PI;
    return a;
  }

  function clampNum(v, lo, hi, dflt) {
    v = +v;
    if (!isFinite(v)) return dflt;
    return v < lo ? lo : (v > hi ? hi : v);
  }

  function easeInOutCubic(u) {
    if (!(u > 0)) return 0;
    if (u >= 1) return 1;
    return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(2 - 2 * u, 3) / 2;
  }
  function easeInOutCubicD(u) {
    if (!(u > 0) || u >= 1) return 0;
    return u < 0.5 ? 12 * u * u : 12 * (1 - u) * (1 - u);
  }

  function posMs(v, dflt) { return (v === null || !(v >= 0)) ? dflt : v; }

  function readTime(tokens) {
    var src = (tokens && typeof tokens === 'object') ? tokens : {};
    var tm = (src.TIME && typeof src.TIME === 'object') ? src.TIME : null;
    function g(keys) {
      var i, key, v = null;
      for (i = 0; i < keys.length; i++) {
        key = keys[i];
        if (tm && tm[key] !== null && tm[key] !== undefined) { v = tm[key]; break; }
        if (src[key] !== null && src[key] !== undefined) { v = src[key]; break; }
      }
      if (v === null || v === undefined) return null;
      v = +v;
      return isFinite(v) ? v : null;
    }
    var T = {};
    var idle = g(['IDLE_SPIN']);
    T.IDLE_SPIN = (idle === null) ? DEF.IDLE_SPIN : clampNum(idle, -4, 4, DEF.IDLE_SPIN);
    T.FOCUS_MS  = posMs(g(['FOCUS_MS']), DEF.FOCUS_MS);
    T.FADE_MS   = posMs(g(['FADE_MS']),  DEF.FADE_MS);
    T.HOLD_MS   = posMs(g(['HOLD_MS']),  DEF.HOLD_MS);
    T.RAMP_MS   = posMs(g(['RESUME_MS', 'RAMP_MS']), DEF.RAMP_MS);
    T.FLASH_MS  = posMs(g(['PULSE_DECAY_MS', 'FLASH_MS']), DEF.FLASH_MS);
    T.GAIN_MS   = posMs(g(['GAIN_MS']), DEF.GAIN_MS);

    var pc = g(['PULSE_CYCLE_MS', 'PULSE_MS']);
    if (pc === null) {
      pc = g(['PULSE_CYCLE']);
      if (pc !== null && pc > 0 && pc <= 200) pc = pc * 1000;
    }
    T.PULSE_MS = (pc === null || !(pc > 0)) ? DEF.PULSE_MS : pc;

    var bms = g(['BREATH_CYCLE_MS', 'CYCLE_MS']);
    if (bms === null) {
      var bhz = g(['BREATH_HZ']);
      if (bhz !== null && bhz > 0) bms = 1000 / bhz;
    }
    T.CYCLE_MS = (bms === null || !(bms > 0)) ? DEF.CYCLE_MS : bms;

    var amp = g(['ENVELOPE_AMP', 'BREATH_AMP']);
    T.ENVELOPE_AMP = (amp === null) ? DEF.ENVELOPE_AMP : clampNum(amp, 0, 1, DEF.ENVELOPE_AMP);
    var dm = g(['DT_MAX']);
    T.DT_MAX = (dm === null) ? DEF.DT_MAX : clampNum(dm, 1 / 240, 1, DEF.DT_MAX);
    return T;
  }

  function readReduced(tokens) {
    if (!tokens || typeof tokens !== 'object') return false;
    if (tokens.reducedMotion !== undefined) return !!tokens.reducedMotion;
    if (tokens.REDUCED !== undefined) return !!tokens.REDUCED;
    if (tokens.TIME && tokens.TIME.REDUCED !== undefined) return !!tokens.TIME.REDUCED;
    return false;
  }

  function normTier(k) {
    if (k === 'low') return 'low';
    if (k === 'mid') return 'mid';
    return 'high';
  }

  function readTier(tokens) {
    var k = tokens && typeof tokens === 'object' ? (tokens.tier || tokens.TIER) : null;
    return normTier(k);
  }


  function create(tokens) {
    var T = readTime(tokens);

    var st = {
      mode: 'idle',
      spin: 0, spinVel: 0,
      idleSpeed: T.IDLE_SPIN,
      reducedMotion: readReduced(tokens),
      tier: readTier(tokens),
      visible: false, fade: 0, fadeTo: 0,
      env: 1,
      tAcc: 0, tLast: 0, ticks: 0,
      order: [], angleOf: {},
      pulseP: 0, pulseI: 0, pulseEv: -1, pulseK: 0, pulseA: 0, pulseGain: 1,
      focusFrom: 0, focusDelta: 0, focusT: 0, focusTarget: null,
      holdT: 0, rampT: 0, released: false
    };

    if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
      window.CLAbyssBreath.subscribe(function (snap) {
        if (snap && isFinite(snap.t)) {
          st.busSnap = snap;
        }
      });
    }

    var ctl;

    function tierCfg() { return TIER[st.tier] || TIER.high; }

    function angleAt(ev) {
      var a = st.angleOf[ev];
      a = +a;
      return isFinite(a) ? a : 0;
    }


    function stepSpin(d, ms) {
      if (st.reducedMotion) { st.spinVel = 0; return; }
      var u, r;
      if (st.mode === 'focus') {
        st.focusT += ms;
        u = T.FOCUS_MS > 0 ? st.focusT / T.FOCUS_MS : 1;
        if (u > 1) u = 1;
        st.spin = st.focusFrom + st.focusDelta * easeInOutCubic(u);
        st.spinVel = T.FOCUS_MS > 0
          ? st.focusDelta * easeInOutCubicD(u) / (T.FOCUS_MS / 1000)
          : 0;
        if (u >= 1) {
          st.spin = st.focusFrom + st.focusDelta;
          st.spinVel = 0;
          st.mode = st.released ? 'wait' : 'hold';
          st.holdT = 0;
        }
      } else if (st.mode === 'hold') {
        st.spinVel = 0;
      } else if (st.mode === 'wait') {
        st.spinVel = 0;
        st.holdT += ms;
        if (st.holdT >= T.HOLD_MS) { st.mode = 'resume'; st.rampT = 0; st.released = false; }
      } else if (st.mode === 'resume') {
        st.rampT += ms;
        r = T.RAMP_MS > 0 ? st.rampT / T.RAMP_MS : 1;
        if (r > 1) r = 1;
        st.spinVel = st.idleSpeed * easeInOutCubic(r);
        st.spin += st.spinVel * d;
        if (r >= 1) { st.mode = 'idle'; st.focusTarget = null; }
      } else {
        st.mode = 'idle';
        st.spinVel = st.idleSpeed;
        st.spin += st.idleSpeed * d;
      }
    }


    function stepPulse(ms) {
      var n = st.order.length;
      var cfg = tierCfg();
      if (!n || st.reducedMotion || !cfg.pulse) {
        st.pulseEv = -1; st.pulseK = 0; st.pulseGain = st.reducedMotion ? 0 : st.pulseGain;
        return;
      }
      var live = (st.mode === 'idle' || st.mode === 'resume');
      if (live && T.PULSE_MS > 0) {
        st.pulseP += ms / T.PULSE_MS;
        st.pulseP -= Math.floor(st.pulseP);
        if (!(st.pulseP >= 0 && st.pulseP < 1)) st.pulseP = 0;
      }
      var gStep = T.GAIN_MS > 0 ? ms / T.GAIN_MS : 1;
      st.pulseGain = live
        ? Math.min(1, st.pulseGain + gStep)
        : Math.max(0, st.pulseGain - gStep);

      var fi = st.pulseP * n;
      var i0 = Math.floor(fi);
      if (i0 >= n) i0 = n - 1;
      if (i0 < 0) i0 = 0;
      var fr = fi - i0;
      st.pulseI = fi;
      st.pulseEv = st.order[i0];

      var since = (T.PULSE_MS / n) * fr;
      var x = T.FLASH_MS > 0 ? since / T.FLASH_MS : 1;
      if (x > 1) x = 1;
      var k = (1 - x) * (1 - x);
      st.pulseK = k * st.pulseGain;

      var a0 = angleAt(st.order[i0]);
      var a1 = angleAt(st.order[(i0 + 1) % n]);
      st.pulseA = a0 + wrapAngle(a1 - a0) * fr;
    }


    function stepEnv(tt) {
      var amp = T.ENVELOPE_AMP * tierCfg().breath;
      if (st.reducedMotion || !(amp > 0)) { st.env = 1; return; }
      var B = (typeof window !== 'undefined') ? window.CLAbyssBreath : null;
      if (B && typeof B.envelope === 'function') {
        st.env = B.envelope(amp, 0);
        return;
      }
      if (B && typeof B.breath === 'function') {
        st.env = 1 - amp + amp * B.breath();
        return;
      }
      var ph = TWO_PI * (tt * 1000 / T.CYCLE_MS);
      st.env = 1 - amp + amp * (0.5 + 0.5 * Math.sin(ph));
    }

    function stepFade(ms) {
      if (st.reducedMotion) { st.fade = st.fadeTo; return; }
      if (st.fade === st.fadeTo) return;
      var step = T.FADE_MS > 0 ? ms / T.FADE_MS : 1;
      if (st.fadeTo > st.fade) st.fade = Math.min(st.fadeTo, st.fade + step);
      else st.fade = Math.max(st.fadeTo, st.fade - step);
    }


    function tick(dt, t) {
      var d = +dt;
      if (!isFinite(d) || d < 0) d = 0;
      if (d > T.DT_MAX) d = T.DT_MAX;
      var ms = d * 1000;
      st.tAcc += d;
      var tt = (typeof t === 'number' && isFinite(t)) ? t : st.tAcc;
      st.tLast = tt;
      st.ticks++;

      stepSpin(d, ms);
      stepPulse(ms);
      stepEnv(tt);
      stepFade(ms);

      return {
        spin: st.spin,
        spinVel: st.spinVel,
        pulse: { evIdx: st.pulseEv, k: st.pulseK, a: st.pulseA, i: st.pulseI, p: st.pulseP },
        env: st.env,
        fade: st.fade,
        mode: st.mode,
        tier: st.tier,
        reducedMotion: st.reducedMotion
      };
    }

    function setOrder(order, angleOf) {
      var arr = [], i, e;
      if (order && typeof order.length === 'number') {
        for (i = 0; i < order.length; i++) {
          e = order[i];
          if (typeof e === 'number' && isFinite(e)) arr.push(e | 0);
          else if (e && typeof e.evIdx === 'number' && isFinite(e.evIdx)) arr.push(e.evIdx | 0);
        }
      }
      var same = arr.length === st.order.length;
      if (same) {
        for (i = 0; i < arr.length; i++) {
          if (arr[i] !== st.order[i]) { same = false; break; }
        }
      }
      st.order = arr;

      var map = {}, keys, k, v;
      if (angleOf && typeof angleOf === 'object') {
        keys = Object.keys(angleOf);
        for (i = 0; i < keys.length; i++) {
          k = keys[i]; v = +angleOf[k];
          if (isFinite(v)) map[k] = v;
        }
      }
      st.angleOf = map;

      if (!same) {
        st.pulseP = 0; st.pulseI = 0; st.pulseK = 0;
        st.pulseEv = arr.length ? arr[0] : -1;
        st.pulseA = arr.length ? angleAt(arr[0]) : 0;
      }
      return ctl;
    }

    function focusAngle(a) {
      var av = +a;
      if (!isFinite(av)) return ctl;
      var delta = wrapAngle(FRONT - av - st.spin);
      st.focusTarget = av;
      st.released = false;
      st.holdT = 0;
      if (st.reducedMotion) {
        st.spin += delta;
        st.spinVel = 0;
        st.focusFrom = st.spin; st.focusDelta = 0; st.focusT = T.FOCUS_MS;
        st.mode = 'hold';
        return ctl;
      }
      st.focusFrom = st.spin;
      st.focusDelta = delta;
      st.focusT = 0;
      st.mode = 'focus';
      return ctl;
    }

    function focusEvent(evIdx) {
      var a = st.angleOf[evIdx];
      a = +a;
      if (!isFinite(a)) return ctl;
      return focusAngle(a);
    }

    function release() {
      st.released = true;
      if (st.reducedMotion) {
        st.released = false; st.mode = 'idle'; st.spinVel = 0; st.focusTarget = null;
        return ctl;
      }
      if (st.mode === 'hold') { st.mode = 'wait'; st.holdT = 0; }
      else if (st.mode === 'idle' || st.mode === 'resume') { st.released = false; }
      return ctl;
    }

    function setVisible(on) {
      st.visible = !!on;
      st.fadeTo = st.visible ? 1 : 0;
      if (st.reducedMotion) st.fade = st.fadeTo;
      return ctl;
    }

    function setReduced(on) {
      var v = !!on;
      if (v === st.reducedMotion) return ctl;
      st.reducedMotion = v;
      if (v) {
        if (st.mode === 'focus') { st.spin = st.focusFrom + st.focusDelta; st.mode = 'hold'; }
        else if (st.mode === 'wait' || st.mode === 'resume') { st.mode = 'idle'; }
        st.spinVel = 0;
        st.released = false;
        st.fade = st.fadeTo;
        st.env = 1;
        st.pulseEv = -1; st.pulseK = 0; st.pulseGain = 0;
      } else {
        st.pulseGain = 1;
        if (st.order.length) st.pulseEv = st.order[Math.min(st.order.length - 1, Math.floor(st.pulseP * st.order.length))];
      }
      return ctl;
    }

    function setTier(k) {
      st.tier = normTier(k);
      return ctl;
    }

    function setIdleSpeed(v) {
      var s = +v;
      if (!isFinite(s)) return ctl;
      st.idleSpeed = clampNum(s, -4, 4, DEF.IDLE_SPIN);
      return ctl;
    }

    function worldAngle(a) { return wrapAngle((+a || 0) + st.spin); }
    function frontError(a) { return wrapAngle((+a || 0) + st.spin - FRONT); }

    function state() {
      return {
        version: '47',
        mode: st.mode,
        spin: st.spin, spinVel: st.spinVel,
        idleSpeed: st.idleSpeed,
        fade: st.fade, fadeTo: st.fadeTo, visible: st.visible,
        env: st.env,
        reducedMotion: st.reducedMotion,
        tier: st.tier,
        front: FRONT,
        focusTarget: st.focusTarget,
        pulse: { evIdx: st.pulseEv, k: st.pulseK, a: st.pulseA, i: st.pulseI, p: st.pulseP, gain: st.pulseGain },
        orderLen: st.order.length,
        ticks: st.ticks, t: st.tLast,
        time: {
          IDLE_SPIN: T.IDLE_SPIN, FOCUS_MS: T.FOCUS_MS, PULSE_MS: T.PULSE_MS,
          FADE_MS: T.FADE_MS, HOLD_MS: T.HOLD_MS, RAMP_MS: T.RAMP_MS,
          FLASH_MS: T.FLASH_MS, CYCLE_MS: T.CYCLE_MS, ENVELOPE_AMP: T.ENVELOPE_AMP,
          DT_MAX: T.DT_MAX
        }
      };
    }

    ctl = {
      version: '47',
      FRONT: FRONT,
      tick: tick,
      setOrder: setOrder,
      focusAngle: focusAngle,
      focusEvent: focusEvent,
      release: release,
      setVisible: setVisible,
      setReduced: setReduced,
      setTier: setTier,
      setIdleSpeed: setIdleSpeed,
      worldAngle: worldAngle,
      frontError: frontError,
      wrapAngle: wrapAngle,
      state: state
    };
    return ctl;
  }

  var API = {
    version: '47',
    FRONT: FRONT,
    DEFAULTS: DEF,
    create: create,
    wrapAngle: wrapAngle,
    easeInOutCubic: easeInOutCubic
  };

  root.CLOrbit3DMotion = API;

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
