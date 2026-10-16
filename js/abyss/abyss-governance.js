(function (g) {
  'use strict';
  if (!g) return;

  var LIGHT_OWNER = {
    panorama: 'lead-star',
    constellation: 'crown-core',
    tree: 'mainline',
    radar: 'top-dimension'
  };

  var QUALITY_TIERS = [
    { tag: 'full', level: 0, glow: 12, labels: 'd2', particles: 1, animation: 1 },
    { tag: 'mid',  level: 1, glow: 8,  labels: 'd1', particles: 0.55, animation: 0.55 },
    { tag: 'low',  level: 2, glow: 4,  labels: 'd0', particles: 0, animation: 0 }
  ];

  var MOTION_LAYERS = {
    ritual: { min: 0.9, max: 4, loop: false },
    atmosphere: { min: 20, max: 200, loop: true },
    feedback: { min: 0, max: 0.3, loop: false },
    forbiddenLoop: { min: 0.3, max: 20, loop: true }
  };

  var clock = { t: 0, frame: 0, source: 'CLMotionClock' };
  function clampTier(n) { n = n | 0; return n < 0 ? 0 : (n > 2 ? 2 : n); }
  function tier(n) { return QUALITY_TIERS[clampTier(n)]; }
  function tick(dt) {
    dt = +dt;
    if (!isFinite(dt) || dt < 0) dt = 0;
    clock.t += dt;
    clock.frame++;
    return clock;
  }
  function reset() { clock.t = 0; clock.frame = 0; }

  var BUDGET = {
    targetFpsDesktop: 60,
    targetFpsMid: 45,
    maxJsFrameMs: 8.0,
    maxDrawCalls: 120,
    maxPostPasses: 4
  };

  var DURATIONS = {
    glint: 0.12,
    shift: 0.30,
    ritual: 0.90,
    epoch: 2.40,
    breath: 21.0,
    pulse: 21.0
  };

  var EASING = {
    sacred: 'cubic-bezier(0.16, 1, 0.3, 1)',
    mech: 'steps(8, end)',
    tide: 'cubic-bezier(0.37, 0, 0.63, 1)'
  };

  var activeTierLevel = 0;

  function applyQualityTier(lv) {
    activeTierLevel = clampTier(lv);
    var t = QUALITY_TIERS[activeTierLevel];

    if (g.CLAbyssTex && typeof g.CLAbyssTex.setEnabled === 'function') {
      g.CLAbyssTex.setEnabled(activeTierLevel < 2);
    }

    if (g.__cl && g.__cl.scene && typeof g.__cl.scene.setDegrade === 'function') {
      g.__cl.scene.setDegrade(activeTierLevel);
    }

    if (g.CLAbyssLOD && typeof g.CLAbyssLOD.applyGovernanceTier === 'function') {
      g.CLAbyssLOD.applyGovernanceTier(activeTierLevel);
    }

    return t;
  }

  g.CLAbyssGovernance = {
    name: 'abyss-governance',
    version: '1',
    LIGHT_OWNER: LIGHT_OWNER,
    QUALITY_TIERS: QUALITY_TIERS,
    MOTION_LAYERS: MOTION_LAYERS,
    BUDGET: BUDGET,
    DURATIONS: DURATIONS,
    EASING: EASING,
    clock: function () { return { t: clock.t, frame: clock.frame, source: clock.source }; },
    tick: tick,
    reset: reset,
    tier: tier,
    applyQualityTier: applyQualityTier,
    getActiveTierLevel: function () { return activeTierLevel; },
    audit: function () {
      return { name: 'abyss-governance', version: '1', lightOwner: LIGHT_OWNER,
        quality: QUALITY_TIERS.slice(), motion: MOTION_LAYERS, budget: BUDGET, durations: DURATIONS };
    }
  };
})(typeof window !== 'undefined' ? window : this);
