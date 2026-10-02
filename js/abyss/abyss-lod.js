/**
 * Castline · abyss-lod.js — 密度四级 LOD 体系（CORE · S6）
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§4 S6 密度四级 LOD 体系。
 * 定位：三图（雷达 / 角色星座场 / 星盘剧情树）共用的密度分级与防遮挡决策层。
 *       统一四级档位：L0 仪式全景 → L1 标准 → L2 聚焦 → L3 解码，
 *       由相机距离（z01 归一化深度）、聚焦态与手动 API 三通道换挡。
 *
 * ES5 IIFE · 零外部强依赖 · UMD 全局暴露 window.CLAbyssLOD。
 * ============================================================================
 */
(function (global) {
  'use strict';

  var TIERS = [
    { level: 0, tag: 'L0', name: '仪式全景', minZ01: 0.0,  maxZ01: 0.25 },
    { level: 1, tag: 'L1', name: '标准概览', minZ01: 0.25, maxZ01: 0.60 },
    { level: 2, tag: 'L2', name: '聚焦详查', minZ01: 0.60, maxZ01: 0.88 },
    { level: 3, tag: 'L3', name: '完全解码', minZ01: 0.88, maxZ01: 1.00 }
  ];

  var currentTier = 1; // 默认 L1 标准
  var manualOverride = null; // null 表示自动根据视角测算，否则锁定档位
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

  var governanceTier = 0; // 0: full, 1: mid, 2: low

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

  /**
   * 综合视角距离与场景模式进行 LOD 评定
   * ctx: { z01: 0..1, mode: 'atlas'|'focus'|'road', isFocus: bool, nodeCount: number }
   */
  function evaluate(ctx) {
    ctx = ctx || {};
    var z01 = ctx.z01 != null ? clamp(ctx.z01, 0, 1) : 0.5;
    var isFocus = !!(ctx.isFocus || ctx.mode === 'focus');
    var nodeCount = ctx.nodeCount || 0;

    var target;
    if (manualOverride != null) {
      target = manualOverride;
    } else if (isFocus) {
      // 聚焦态默认至少进入 L2 聚焦档，推至近处则进入 L3 解码
      target = z01 > 0.85 ? 3 : 2;
    } else {
      // 全景态根据相机深度映射四档
      if (z01 < 0.22) target = 0;
      else if (z01 < 0.65) target = 1;
      else if (z01 < 0.90) target = 2;
      else target = 3;

      // 极端高密度场景（节点 > 500）在远景适当收敛
      if (nodeCount > 500 && target > 1 && z01 < 0.5) {
        target = 1;
      }
      // 治理层低画质限制：当 governanceTier >= 2 且非聚焦态时，全景态限制最高到 L1
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
        showMacroStructures: true,                      // 宏观骨架与星云全档可见
        showMainLabels: currentTier >= 1,               // 主星名 / 阵营名在 L1+ 可见
        showSecondaryLabels: currentTier >= 2,          // 次级标签与角色名在 L2+ 可见
        showAttributes: currentTier >= 2,               // 属性分值 / 雷达胶囊在 L2+ 可见
        showInscriptions: currentTier >= 3,             // 完整铭文 / 原文证据在 L3 可见
        labelDensityRatio: currentTier === 0 ? 0.0 :
                           currentTier === 1 ? 0.35 :
                           currentTier === 2 ? 0.75 : 1.0
      }
    };
  }

  /**
   * 综合相机与控制器距离进行归一化深度求值与换挡
   */
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

  /**
   * 挂接相机与 OrbitControls 监听器
   */
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

  /**
   * 节点标签防遮挡与显示优先级判定辅助函数
   */
  function isNodeVisible(node, ctx, lodResult) {
    if (!node) return false;
    lodResult = lodResult || evaluate(ctx);

    // 强显优先级最高：高亮、悬停、搜索中或被钉住的节点无条件可见
    if (node.isPinned || node.isHovered || node.isFocused || node.isMatched) {
      return true;
    }

    var rules = lodResult.rules;
    if (!rules.showMainLabels) return false;

    // 主星 / 枢纽角色在 L1 即可见
    var isPrimary = (node.tier <= 1 || node.isLeader || node.kind === 'hub');
    if (isPrimary) return true;

    // 普通次级角色需要 L2
    if (!rules.showSecondaryLabels) return false;

    // 边缘末端角色受密度比率控制
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
