(function (global) {
  'use strict';

  var TIERS = [
    { level: 0, tag: 'L0', name: '仪式全景', minZ01: 0.0,  maxZ01: 0.25 },
    { level: 1, tag: 'L1', name: '标准概览', minZ01: 0.25, maxZ01: 0.60 },
    { level: 2, tag: 'L2', name: '聚焦详查', minZ01: 0.60, maxZ01: 0.88 },
    { level: 3, tag: 'L3', name: '完全解码', minZ01: 0.88, maxZ01: 1.00 }
  ];

  var currentTier = 1;
  var manualOverride = null;
  var listeners = [];

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function getTier() {
    return manualOverride != null ? manualOverride : currentTier;
  }

  function setTier(t) {
    if (t == null) {
      manualOverride = null;
    } else {
      var n = clamp(t | 0, 0, 3);
      manualOverride = n;
      emitChange(n, 'manual');
    }
    return getTier();
  }

  var governanceTier = 0;

  function applyGovernanceTier(lv) {
    governanceTier = clamp(lv | 0, 0, 2);
    if (manualOverride == null && governanceTier >= 2 && currentTier > 1) {
      currentTier = 1;
      emitChange(currentTier, 'governance');
    }
    return governanceTier;
  }

  function emitChange(newTier, reason) {
    var info = TIERS[newTier];
    for (var i = 0; i < listeners.length; i++) {
      try {
        listeners[i]({ tier: newTier, info: info, reason: reason, governanceTier: governanceTier });
      } catch (e) {}
    }
    if (typeof document !== 'undefined' && document.dispatchEvent && typeof CustomEvent === 'function') {
      try {
        document.dispatchEvent(new CustomEvent('cl:lod-change', {
          detail: { tier: newTier, info: info, reason: reason, governanceTier: governanceTier }
        }));
      } catch (e) {}
    }
  }

  function subscribe(fn) {
    if (typeof fn === 'function') listeners.push(fn);
  }

  function unsubscribe(fn) {
    var idx = listeners.indexOf(fn);
    if (idx !== -1) listeners.splice(idx, 1);
  }

  function evaluate(ctx) {
    ctx = ctx || {};
    var z01 = ctx.z01 != null ? clamp(ctx.z01, 0, 1) : 0.5;
    var isFocus = !!(ctx.isFocus || ctx.mode === 'focus');
    var nodeCount = ctx.nodeCount || 0;

    var target;
    if (manualOverride != null) {
      target = manualOverride;
    } else if (isFocus) {
      target = z01 > 0.85 ? 3 : 2;
    } else {
      if (z01 < 0.22) target = 0;
      else if (z01 < 0.65) target = 1;
      else if (z01 < 0.90) target = 2;
      else target = 3;

      if (nodeCount > 500 && target > 1 && z01 < 0.5) {
        target = 1;
      }
      if (governanceTier >= 2 && !isFocus && target > 1) {
        target = 1;
      }
    }

    if (target !== currentTier) {
      currentTier = target;
      emitChange(currentTier, 'auto');
    }

    var t = TIERS[currentTier];

    return {
      tier: currentTier,
      tag: t.tag,
      name: t.name,
      z01: z01,
      isFocus: isFocus,
      rules: {
        showMacroStructures: true,
        showMainLabels: currentTier >= 1,
        showSecondaryLabels: currentTier >= 2,
        showAttributes: currentTier >= 2,
        showInscriptions: currentTier >= 3,
        labelDensityRatio: currentTier === 0 ? 0.0 :
                           currentTier === 1 ? 0.35 :
                           currentTier === 2 ? 0.75 : 1.0
      }
    };
  }

  function evaluateCamera(cam, ctrl, extraCtx) {
    if (!cam) return evaluate(extraCtx);
    var targetPos = (ctrl && ctrl.target) ? ctrl.target : { x: 0, y: 0, z: 0 };
    var dx = cam.position.x - targetPos.x;
    var dy = cam.position.y - targetPos.y;
    var dz = cam.position.z - targetPos.z;
    var dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    var minDist = (ctrl && ctrl.minDistance != null) ? ctrl.minDistance : 160;
    var maxDist = (ctrl && ctrl.maxDistance != null) ? ctrl.maxDistance : 3400;
    var z01 = clamp(1 - (dist - minDist) / Math.max(1, maxDist - minDist), 0, 1);

    var ctx = extraCtx || {};
    ctx.z01 = z01;
    if (ctx.isFocus == null && global.__cl && global.__cl.scene && typeof global.__cl.scene.getMode === 'function') {
      ctx.isFocus = (global.__cl.scene.getMode() === 'focus');
    }
    return evaluate(ctx);
  }

  function attachCamera(cam, ctrl) {
    if (!ctrl) return;
    try {
      if (typeof ctrl.addEventListener === 'function') {
        ctrl.addEventListener('change', function () {
          evaluateCamera(cam, ctrl);
        });
      }
      evaluateCamera(cam, ctrl);
    } catch (e) {}
  }

  function isNodeVisible(node, ctx, lodResult) {
    if (!node) return false;
    lodResult = lodResult || evaluate(ctx);

    if (node.isPinned || node.isHovered || node.isFocused || node.isMatched) {
      return true;
    }

    var rules = lodResult.rules;
    if (!rules.showMainLabels) return false;

    var isPrimary = (node.tier <= 1 || node.isLeader || node.kind === 'hub');
    if (isPrimary) return true;

    if (!rules.showSecondaryLabels) return false;

    if (node.tier >= 4 && rules.labelDensityRatio < 0.7) {
      return false;
    }

    return true;
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('cl:cam-distance', function (e) {
      if (e && e.detail && e.detail.camera) {
        evaluateCamera(e.detail.camera, e.detail.controls, e.detail);
      } else if (e && e.detail && e.detail.z01 != null) {
        evaluate(e.detail);
      }
    });
    window.addEventListener('cl:quality-tier', function (e) {
      if (e && e.detail != null) {
        applyGovernanceTier(typeof e.detail === 'object' ? e.detail.level : e.detail);
      }
    });
  }

  var CLAbyssLOD = {
    name: 'abyss-lod',
    version: '1',
    TIERS: TIERS,
    getTier: getTier,
    setTier: setTier,
    evaluate: evaluate,
    evaluateCamera: evaluateCamera,
    attachCamera: attachCamera,
    applyGovernanceTier: applyGovernanceTier,
    isNodeVisible: isNodeVisible,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    audit: function () {
      return {
        name: 'abyss-lod',
        version: '1',
        currentTier: currentTier,
        tag: TIERS[currentTier].tag,
        isManual: manualOverride != null,
        governanceTier: governanceTier
      };
    }
  };

  global.CLAbyssLOD = CLAbyssLOD;
})(typeof window !== 'undefined' ? window : this);
