/**
 * @file radar-ritual.js
 * @role radar-ritual-engine · @owns js/radar-ritual.js · @contract P3/R4
 * 雷达解码仪式（19 步连续编排）
 * 
 * 方案契约：
 * 1. 19 步时序表：
 *    Step 01: 深渊之瞳先睁 (0-300ms)
 *    Step 02-09: 铭文环按八维方位逐枚点亮 (18ms 间隔，300-444ms)
 *    Step 10: 内网格自内向外生长 (450-700ms)
 *    Step 11: 外罗盘几何锁定 (700-900ms)
 *    Step 12: 轴线光柱升起 (900-1100ms)
 *    Step 13: 切面光影注入 (1100-1350ms)
 *    Step 14: 数据多边形墨水晕染成形 (1350-1600ms)
 *    Step 15: 晶体脊线凝结 (1600-1800ms)
 *    Step 16: 巅峰光晶簇凝聚 (1800-1950ms)
 *    Step 17: 主维数值胶囊落位弹章 (1950-2100ms)
 *    Step 18: 次维数值胶囊落位 (2100-2250ms)
 *    Step 19: 仪式收束进入常驻呼吸总线 (2250-2400ms)
 * 2. 全程 2400ms (--abyss-dur-epoch)，支持 skip() 即时跳过。
 * 3. 跳过或播放完成状态像素级一致。
 */
(function (global) {
  'use strict';

  var TOTAL_EPOCH_MS = 2400;

  var RITUAL_STEPS = [
    { id: 'step-01', name: '深渊之瞳睁眼', t0: 0, t1: 300, selector: '.rd-abyss' },
    { id: 'step-02', name: '铭文点亮·维0', t0: 300, t1: 318, selector: '.rd-runes [data-dim="0"], .rd-runes [data-i="0"]' },
    { id: 'step-03', name: '铭文点亮·维1', t0: 318, t1: 336, selector: '.rd-runes [data-dim="1"], .rd-runes [data-i="1"]' },
    { id: 'step-04', name: '铭文点亮·维2', t0: 336, t1: 354, selector: '.rd-runes [data-dim="2"], .rd-runes [data-i="2"]' },
    { id: 'step-05', name: '铭文点亮·维3', t0: 354, t1: 372, selector: '.rd-runes [data-dim="3"], .rd-runes [data-i="3"]' },
    { id: 'step-06', name: '铭文点亮·维4', t0: 372, t1: 390, selector: '.rd-runes [data-dim="4"], .rd-runes [data-i="4"]' },
    { id: 'step-07', name: '铭文点亮·维5', t0: 390, t1: 408, selector: '.rd-runes [data-dim="5"], .rd-runes [data-i="5"]' },
    { id: 'step-08', name: '铭文点亮·维6', t0: 408, t1: 426, selector: '.rd-runes [data-dim="6"], .rd-runes [data-i="6"]' },
    { id: 'step-09', name: '铭文点亮·维7', t0: 426, t1: 444, selector: '.rd-runes [data-dim="7"], .rd-runes [data-i="7"]' },
    { id: 'step-10', name: '同心网格自内生长', t0: 450, t1: 700, selector: '.rd-grid-sub, .rd-grid:not(.rd-grid-outer)' },
    { id: 'step-11', name: '外罗盘几何锁定', t0: 700, t1: 900, selector: '.rd-grid-outer, .rd-bezel, .rd-holo-rail' },
    { id: 'step-12', name: '轴线光柱升起', t0: 900, t1: 1100, selector: '.rd-axis, .rd-axis-node, .rd-lamp-cone' },
    { id: 'step-13', name: '切面光影注入', t0: 1100, t1: 1350, selector: '.rd-facet, .rd-fill-depth' },
    { id: 'step-14', name: '数据墨水晕染成形', t0: 1350, t1: 1600, selector: '.rd-fill, .rd-shape, .rd-shape-aura' },
    { id: 'step-15', name: '晶体切面脊线凝结', t0: 1600, t1: 1800, selector: '.rd-crystal-ridge' },
    { id: 'step-16', name: '巅峰光晶簇凝聚', t0: 1800, t1: 1950, selector: '.rd-crystal-cluster' },
    { id: 'step-17', name: '主要数值胶囊落位', t0: 1950, t1: 2100, selector: '.rd-capsules [data-tier="peak"], .rd-capsules [data-tier="high"]' },
    { id: 'step-18', name: '次要数值胶囊落位', t0: 2100, t1: 2250, selector: '.rd-capsules' },
    { id: 'step-19', name: '仪式收束入呼吸相', t0: 2250, t1: 2400, selector: '.radar-3d' }
  ];

  var _activeAnim = null;
  var _skipped = false;

  function isReducedMotion() {
    try {
      return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {
      return false;
    }
  }

  function start(svgEl, onComplete) {
    if (!svgEl) return;
    if (isReducedMotion()) {
      skip(svgEl);
      if (typeof onComplete === 'function') onComplete();
      return;
    }

    _skipped = false;
    if (_activeAnim) cancelAnimationFrame(_activeAnim);

    svgEl.classList.add('rd-ritual-running');
    svgEl.setAttribute('data-ritual', 'active');

    var startTime = performance.now();

    function frame(now) {
      if (_skipped) {
        finish(svgEl);
        if (typeof onComplete === 'function') onComplete();
        return;
      }

      var elapsed = now - startTime;
      var progress = Math.min(1.0, elapsed / TOTAL_EPOCH_MS);

      // 应用各步骤可见度与进度
      for (var i = 0; i < RITUAL_STEPS.length; i++) {
        var s = RITUAL_STEPS[i];
        var els = svgEl.querySelectorAll(s.selector);
        if (!els || els.length === 0) continue;

        if (elapsed < s.t0) {
          // 尚未开始
          for (var j = 0; j < els.length; j++) {
            els[j].style.opacity = '0';
          }
        } else if (elapsed >= s.t1) {
          // 已完成
          for (var k = 0; k < els.length; k++) {
            els[k].style.opacity = '';
          }
        } else {
          // 进行中
          var stepK = (elapsed - s.t0) / (s.t1 - s.t0);
          for (var m = 0; m < els.length; m++) {
            els[m].style.opacity = stepK.toFixed(3);
          }
        }
      }

      if (progress < 1.0) {
        _activeAnim = requestAnimationFrame(frame);
      } else {
        finish(svgEl);
        if (typeof onComplete === 'function') onComplete();
      }
    }

    _activeAnim = requestAnimationFrame(frame);
  }

  function finish(svgEl) {
    if (_activeAnim) {
      cancelAnimationFrame(_activeAnim);
      _activeAnim = null;
    }
    if (svgEl) {
      svgEl.classList.remove('rd-ritual-running');
      svgEl.setAttribute('data-ritual', 'settled');
      // 清除全部内联透明度样式，与静态渲染逐像素对齐
      var styledEls = svgEl.querySelectorAll('[style*="opacity"]');
      for (var i = 0; i < styledEls.length; i++) {
        styledEls[i].style.opacity = '';
      }
    }
  }

  function skip(svgEl) {
    _skipped = true;
    finish(svgEl);
  }

  function isRunning() {
    return !!_activeAnim && !_skipped;
  }

  function syncBreath() {
    var B = global.CLAbyssBreath;
    if (B && typeof B.getPhase === 'function') {
      return { phase: B.getPhase(), epoch: B.getEpoch(), synced: true };
    }
    var t = (performance.now ? performance.now() : Date.now()) / 1000;
    return { phase: (t % 3.6) / 3.6, epoch: Math.floor(t / 3.6), synced: true };
  }

  function dive(targetStar, onComplete) {
    if (isReducedMotion()) {
      skip();
      if (typeof onComplete === 'function') onComplete();
      return;
    }
    syncBreath();
    var markEl = document.getElementById('constellationMark');
    if (markEl) markEl.classList.add('ritual-focus');

    var scene = global.__CL_SCENE || global.scene;
    if (scene && scene.dofTarget) {
      scene.dofTarget.uFocD = (targetStar && targetStar.z != null) ? targetStar.z : 0.5;
    }

    var svgEl = document.querySelector('.radar-svg, #radarSvg, svg.radar, #radar');
    if (svgEl) {
      start(svgEl, function () {
        if (typeof onComplete === 'function') onComplete();
      });
    } else {
      setTimeout(function () {
        if (typeof onComplete === 'function') onComplete();
      }, 300);
    }
  }

  function graft(fromMode, toMode, onComplete) {
    syncBreath();
    var TL = global.CLTreeTimeline;
    var currentProg = (TL && typeof TL.getProgress === 'function') ? TL.getProgress() : 0.5;

    var stage = document.getElementById('stage') || document.body;
    if (stage) {
      if (toMode === 'tree') {
        stage.classList.remove('posture-constellation');
        stage.classList.add('posture-tree');
      } else if (toMode === 'constellation') {
        stage.classList.remove('posture-tree');
        stage.classList.add('posture-constellation');
      }
    }

    if (typeof onComplete === 'function') {
      setTimeout(onComplete, 200);
    }
    return { from: fromMode, to: toMode, progress: currentProg, synced: true };
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isRunning()) {
        skip();
      }
    });
  }

  var API = {
    STEPS: RITUAL_STEPS,
    TOTAL_EPOCH_MS: TOTAL_EPOCH_MS,
    start: start,
    runTransitions: start,
    skip: skip,
    isRunning: isRunning,
    isSkipped: function () { return _skipped; },
    dive: dive,
    graft: graft,
    syncBreath: syncBreath
  };

  global.CLRadarRitual = API;
  global.CLAbyssRitual = API;

})(typeof window !== 'undefined' ? window : this);
