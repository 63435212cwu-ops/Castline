(function (root, factory) {
  'use strict';
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    var exp = factory();
    root.CLRadarMotion = exp;
    if (typeof window !== 'undefined') {
      window.CLRadarMotion = exp;
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = {
    智谋: 'MIND',
    实力: 'FORCE',
    意志: 'WILL',
    魅力: 'CHARM',
    情感: 'HEART',
    野心: 'DRIVE',
    权势: 'REACH',
    道义: 'CODE'
  };
  var EN_REV = {
    MIND: '智谋',
    FORCE: '实力',
    WILL: '意志',
    CHARM: '魅力',
    HEART: '情感',
    DRIVE: '野心',
    REACH: '权势',
    CODE: '道义'
  };

  var THEME = {
    obsidian: '#07060d',
    mint: '#7af0c8',
    amber: '#ffb45c',
    violet: '#a688ff',
    hot: '#ff5c7c'
  };

  var EASING = {
    out: 'cubic-bezier(.16, 1, .3, 1)',
    io: 'cubic-bezier(.65, 0, .35, 1)',
    back: 'cubic-bezier(.34, 1.32, .64, 1)'
  };

  var DURATION = {
    flashMs: 700,
    hoverMs: 220
  };

  var STYLE_ID = 'cl-radar-motion-style';

  function normalizeKey(k) {
    if (k == null) return null;
    if (typeof k === 'number') {
      return (k >= 0 && k < KEYS.length) ? KEYS[k] : null;
    }
    var str = String(k).trim();
    if (!str) return null;
    if (KEYS.indexOf(str) !== -1) return str;
    var upper = str.toUpperCase();
    if (EN_REV[upper]) return EN_REV[upper];
    var num = parseInt(str, 10);
    if (!isNaN(num) && num >= 0 && num < KEYS.length && String(num) === str) {
      return KEYS[num];
    }
    return null;
  }

  function isReducedMotion() {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {
      return false;
    }
  }

  if (typeof window !== 'undefined' && window.matchMedia) {
    try {
      var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      var mqHandler = function () { try { if (isReducedMotion()) clearHighlight(); } catch (e) {} };
      if (mq.addEventListener) {
        mq.addEventListener('change', mqHandler);
      } else if (mq.addListener) {
        mq.addListener(mqHandler);
      }
    } catch (e) {}
  }

  function ensureStyles() {
    if (typeof document === 'undefined') return;
    if (document.getElementById(STYLE_ID)) return;

    var css = [
      '/* CLRadarMotion 独立动效分层与触感微光表 */',
      '.radar-3d .rd-lab, .radar-3d .rd-vert, .radar-3d .rd-axis, .radar-3d .rd-beacon, .radar-3d .rd-lamp-cone, .rd-bar {',
      '  transition: transform 0.22s var(--e-out, cubic-bezier(.16, 1, .3, 1)), filter 0.22s var(--e-out, cubic-bezier(.16, 1, .3, 1)), opacity 0.2s ease, stroke 0.2s ease, fill 0.2s ease;',
      '}',
      '.radar-3d .rd-beacon { transform-box: fill-box; transform-origin: 50% 100%; }',
      '.radar-3d .rd-vert { transform-box: fill-box; }',
      '/* 悬停联动高亮态与触感微光 */',
      '.radar-3d .rd-axis.rd-motion-hover {',
      '  stroke: var(--mint, #7af0c8) !important;',
      '  stroke-opacity: 1 !important;',
      '  stroke-width: 2.2px !important;',
      '  filter: drop-shadow(0 0 6px rgba(122, 240, 200, 0.9)) drop-shadow(0 0 12px rgba(122, 240, 200, 0.45));',
      '}',
      '.radar-3d .rd-beacon.rd-motion-hover {',
      '  opacity: 1 !important;',
      '  fill: var(--mint, #7af0c8) !important;',
      '  filter: drop-shadow(0 0 8px rgba(122, 240, 200, 0.95)) brightness(1.7) !important;',
      '  transform: scaleY(1.15);',
      '}',
      '.radar-3d .rd-lamp-cone.rd-motion-hover {',
      '  opacity: 0.85 !important;',
      '  fill: rgba(122, 240, 200, 0.24) !important;',
      '}',
      '.radar-3d .rd-vert.rd-motion-hover { transform: scale(1.12); }',
      '.radar-3d .rd-vert.rd-motion-hover .rd-ring {',
      '  stroke: #ffffff !important;',
      '  stroke-width: 2.4px !important;',
      '  filter: drop-shadow(0 0 6px var(--mint, #7af0c8));',
      '}',
      '.radar-3d .rd-vert.rd-motion-hover .rd-dot {',
      '  fill: #ffffff !important;',
      '  filter: drop-shadow(0 0 8px var(--signal, #ffb45c));',
      '}',
      '.radar-3d .rd-vert.rd-motion-hover .rd-pulse { opacity: 0.9 !important; stroke: var(--mint, #7af0c8) !important; }',
      '.radar-3d .rd-lab.rd-motion-hover { cursor: pointer; }',
      '.radar-3d .rd-lab.rd-motion-hover .rd-chip {',
      '  fill: rgba(36, 26, 54, 0.92) !important;',
      '  stroke: var(--mint, #7af0c8) !important;',
      '  stroke-width: 1.4px !important;',
      '  filter: drop-shadow(0 0 8px rgba(122, 240, 200, 0.75)) drop-shadow(0 0 16px rgba(255, 180, 92, 0.4)) !important;',
      '}',
      '.radar-3d .rd-lab.rd-motion-hover .rd-name { fill: #fff6e8 !important; }',
      '.radar-3d .rd-lab.rd-motion-hover .rd-score { fill: #ffffff !important; filter: drop-shadow(0 0 7px var(--signal, #ffb45c)); }',
      '.rd-bar.rd-motion-hover {',
      '  background: linear-gradient(90deg, rgba(122, 240, 200, 0.18) 0%, rgba(255, 180, 92, 0.08) 65%, transparent 100%) !important;',
      '  border-left-color: var(--mint, #7af0c8) !important;',
      '  box-shadow: inset 0 0 14px rgba(122, 240, 200, 0.15), 0 0 10px rgba(122, 240, 200, 0.22) !important;',
      '  transform: translateX(4px);',
      '}',
      '.rd-bar.rd-motion-hover .rb-k { color: #fff6e8 !important; }',
      '.rd-bar.rd-motion-hover .rb-t i { box-shadow: 0 0 8px var(--mint, #7af0c8) !important; }',
      '/* 未聚焦轴线层次降权 */',
      '.radar-3d .rd-axis.rd-motion-dimmed, .radar-3d .rd-beacon.rd-motion-dimmed, .radar-3d .rd-lamp-cone.rd-motion-dimmed,',
      '.radar-3d .rd-vert.rd-motion-dimmed, .radar-3d .rd-lab.rd-motion-dimmed, .rd-bar.rd-motion-dimmed {',
      '  opacity: 0.35;',
      '}',
      '/* 能量爆发脉冲关键帧 */',
      '@keyframes clRadarBeaconPulse {',
      '  0% { transform: scaleY(1); opacity: 0.7; }',
      '  25% { transform: scaleY(1.48); opacity: 1; filter: brightness(2.6) drop-shadow(0 0 16px var(--signal, #ffb45c)) drop-shadow(0 0 28px var(--mint, #7af0c8)); }',
      '  100% { transform: scaleY(1); opacity: 0.7; }',
      '}',
      '@keyframes clRadarVertBurst {',
      '  0% { transform: scale(1); }',
      '  30% { transform: scale(1.55); }',
      '  100% { transform: scale(1); }',
      '}',
      '@keyframes clRadarBarPulse {',
      '  0% { transform: translateX(0); box-shadow: none; }',
      '  22% { transform: translateX(7px); background: linear-gradient(90deg, rgba(255, 180, 92, 0.36) 0%, rgba(122, 240, 200, 0.20) 70%, transparent 100%); box-shadow: 0 0 20px rgba(255, 180, 92, 0.55), inset 0 0 10px rgba(122, 240, 200, 0.3); }',
      '  100% { transform: translateX(0); box-shadow: none; }',
      '}',
      '@keyframes clRadarLabPulse {',
      '  0% { filter: brightness(1) drop-shadow(0 0 0 rgba(122, 240, 200, 0)); transform: scale(1); }',
      '  25% { stroke: var(--signal, #ffb45c) !important; filter: brightness(1.7) drop-shadow(0 0 16px rgba(255, 180, 92, 0.95)) drop-shadow(0 0 32px rgba(122, 240, 200, 0.7)); transform: scale(1.04); }',
      '  100% { filter: brightness(1) drop-shadow(0 0 0 rgba(122, 240, 200, 0)); transform: scale(1); }',
      '}',
      '@keyframes clRadarAxisPulse {',
      '  0% { stroke-width: 1px; stroke-opacity: 0.6; }',
      '  25% { stroke-width: 3.2px; stroke-opacity: 1; stroke: #fff6e8 !important; filter: drop-shadow(0 0 10px var(--signal, #ffb45c)) drop-shadow(0 0 20px var(--mint, #7af0c8)); }',
      '  100% { stroke-width: 1px; stroke-opacity: 0.6; }',
      '}',
      '.radar-3d .rd-axis.rd-motion-flash { animation: clRadarAxisPulse 0.7s var(--e-out, cubic-bezier(.16, 1, .3, 1)) both !important; }',
      '.radar-3d .rd-beacon.rd-motion-beacon-surge { animation: clRadarBeaconPulse 0.7s var(--e-out, cubic-bezier(.16, 1, .3, 1)) both !important; }',
      '.radar-3d .rd-vert.rd-motion-vert-burst { animation: clRadarVertBurst 0.7s var(--e-back, cubic-bezier(.34, 1.32, .64, 1)) both !important; }',
      '.radar-3d .rd-lab.rd-motion-flash { animation: clRadarLabPulse 0.7s var(--e-out, cubic-bezier(.16, 1, .3, 1)) both !important; }',
      '.rd-bar.rd-motion-flash { animation: clRadarBarPulse 0.7s var(--e-out, cubic-bezier(.16, 1, .3, 1)) both !important; }',
      '/* 降低动效保护 (prefers-reduced-motion) */',
      '@media (prefers-reduced-motion: reduce) {',
      '  .radar-3d .rd-lab, .radar-3d .rd-vert, .radar-3d .rd-axis, .radar-3d .rd-beacon, .radar-3d .rd-lamp-cone, .rd-bar { transition: none !important; }',
      '  .radar-3d .rd-axis.rd-motion-flash, .radar-3d .rd-beacon.rd-motion-beacon-surge, .radar-3d .rd-vert.rd-motion-vert-burst,',
      '  .radar-3d .rd-lab.rd-motion-flash, .rd-bar.rd-motion-flash { animation: none !important; }',
      '  .radar-3d .rd-vert.rd-motion-hover, .radar-3d .rd-lab.rd-motion-hover, .radar-3d .rd-beacon.rd-motion-hover, .rd-bar.rd-motion-hover { transform: none !important; }',
      '}'
    ].join('\n');

    try {
      var el = document.createElement('style');
      el.id = STYLE_ID;
      el.type = 'text/css';
      el.textContent = css;
      (document.head || document.documentElement).appendChild(el);
    } catch (e) {}
  }

  function resolveContainer(container) {
    if (!container) return null;
    if (typeof container === 'string') {
      if (typeof document !== 'undefined') {
        try {
          return document.querySelector(container);
        } catch (e) {
          return null;
        }
      }
      return null;
    }
    if (container && (container.nodeType === 1 || container.nodeType === 9)) {
      return container;
    }
    return null;
  }

  function getAxisKey(el) {
    if (!el || typeof el.getAttribute !== 'function') return null;
    var target = el.closest ? el.closest('[data-axis], [data-lamp-i]') : null;
    if (!target) return null;

    var k = target.getAttribute('data-axis');
    var norm = normalizeKey(k);
    if (norm) return norm;

    var lamp = target.getAttribute('data-lamp-i');
    if (lamp != null && lamp !== '') {
      var idx = parseInt(lamp, 10);
      if (!isNaN(idx) && idx >= 0 && idx < KEYS.length) {
        return KEYS[idx];
      }
    }
    return null;
  }

  function findAxisElements(root, k) {
    var empty = { key: null, index: -1, axis: [], beacon: [], cone: [], vert: [], lab: [], bar: [], all: [] };
    var norm = normalizeKey(k);
    if (!norm) return empty;
    var idx = KEYS.indexOf(norm);

    var scope = resolveContainer(root);
    if (!scope) {
      scope = typeof document !== 'undefined' ? document : null;
    }
    if (!scope || typeof scope.querySelectorAll !== 'function') {
      return empty;
    }

    var selAxis = '.rd-axis[data-axis="' + norm + '"], .rd-axis[data-lamp-i="' + idx + '"]';
    var selBeacon = '.rd-beacon[data-axis="' + norm + '"], .rd-beacon[data-lamp-i="' + idx + '"]';
    var selCone = '.rd-lamp-cone[data-axis="' + norm + '"], .rd-lamp-cone[data-lamp-i="' + idx + '"]';
    var selVert = '.rd-vert[data-axis="' + norm + '"], .rd-vert[data-lamp-i="' + idx + '"]';
    var selLab = '.rd-lab[data-axis="' + norm + '"], .rd-lab[data-lamp-i="' + idx + '"]';
    var selBar = '.rd-bar[data-axis="' + norm + '"]';

    var toArr = function (nl) { return Array.prototype.slice.call(nl || []); };

    var axes = toArr(scope.querySelectorAll(selAxis));
    var beacons = toArr(scope.querySelectorAll(selBeacon));
    var cones = toArr(scope.querySelectorAll(selCone));
    var verts = toArr(scope.querySelectorAll(selVert));
    var labs = toArr(scope.querySelectorAll(selLab));
    var bars = toArr(scope.querySelectorAll(selBar));

    if (bars.length === 0 && scope.ownerDocument && typeof scope.ownerDocument.querySelectorAll === 'function') {
      bars = toArr(scope.ownerDocument.querySelectorAll(selBar));
    }
    if (axes.length === 0 && scope.ownerDocument && typeof scope.ownerDocument.querySelectorAll === 'function') {
      axes = toArr(scope.ownerDocument.querySelectorAll(selAxis));
      beacons = toArr(scope.ownerDocument.querySelectorAll(selBeacon));
      cones = toArr(scope.ownerDocument.querySelectorAll(selCone));
      verts = toArr(scope.ownerDocument.querySelectorAll(selVert));
      labs = toArr(scope.ownerDocument.querySelectorAll(selLab));
    }

    var all = [].concat(axes, beacons, cones, verts, labs, bars);
    return {
      key: norm,
      index: idx,
      axis: axes,
      beacon: beacons,
      cone: cones,
      vert: verts,
      lab: labs,
      bar: bars,
      all: all
    };
  }

  function dispatchCustomEvent(target, name, detail) {
    if (typeof CustomEvent === 'undefined') return;
    try {
      var ev = new CustomEvent(name, { detail: detail, bubbles: true, cancelable: true });
      if (target && target.dispatchEvent) {
        target.dispatchEvent(ev);
      } else if (typeof document !== 'undefined' && document.dispatchEvent) {
        document.dispatchEvent(ev);
      }
    } catch (e) {}
  }

  function highlightAxis(container, k) {
    var norm = normalizeKey(k);
    if (!norm) {
      clearHighlight(container);
      return;
    }

    ensureStyles();
    var scope = resolveContainer(container) || (typeof document !== 'undefined' ? document : null);
    if (!scope || typeof scope.querySelectorAll !== 'function') return;

    var matched = findAxisElements(scope, norm);

    var allInteractive = Array.prototype.slice.call(
      scope.querySelectorAll('.rd-axis, .rd-beacon, .rd-lamp-cone, .rd-vert, .rd-lab, .rd-bar') || []
    );
    if (matched.bar.length > 0 && allInteractive.length > 0 && scope.ownerDocument) {
      var extBars = Array.prototype.slice.call(scope.ownerDocument.querySelectorAll('.rd-bar') || []);
      for (var b = 0; b < extBars.length; b++) {
        if (allInteractive.indexOf(extBars[b]) === -1) allInteractive.push(extBars[b]);
      }
    }

    var matchSet = matched.all;

    for (var i = 0; i < allInteractive.length; i++) {
      var el = allInteractive[i];
      if (matchSet.indexOf(el) !== -1) {
        el.classList.add('rd-motion-hover');
        el.classList.remove('rd-motion-dimmed');
      } else {
        el.classList.remove('rd-motion-hover');
        el.classList.add('rd-motion-dimmed');
      }
    }

    dispatchCustomEvent(scope, 'cl:radar-axis-hover', { axis: norm, key: norm, elements: matched });
  }

  function clearHighlight(container) {
    var scope = resolveContainer(container) || (typeof document !== 'undefined' ? document : null);
    if (!scope || typeof scope.querySelectorAll !== 'function') return;

    var allInteractive = Array.prototype.slice.call(
      scope.querySelectorAll('.rd-axis, .rd-beacon, .rd-lamp-cone, .rd-vert, .rd-lab, .rd-bar') || []
    );
    if (scope.ownerDocument && typeof scope.ownerDocument.querySelectorAll === 'function') {
      var extBars = Array.prototype.slice.call(scope.ownerDocument.querySelectorAll('.rd-bar') || []);
      for (var b = 0; b < extBars.length; b++) {
        if (allInteractive.indexOf(extBars[b]) === -1) allInteractive.push(extBars[b]);
      }
    }

    for (var i = 0; i < allInteractive.length; i++) {
      allInteractive[i].classList.remove('rd-motion-hover');
      allInteractive[i].classList.remove('rd-motion-dimmed');
    }

    dispatchCustomEvent(scope, 'cl:radar-axis-hover', { axis: null, key: null });
  }

  function flashAxis(k, container) {
    var norm = normalizeKey(k);
    if (!norm) {
      return { flashed: false, reduced: false, axis: null, count: 0 };
    }

    ensureStyles();
    var reduced = isReducedMotion();

    if (reduced) {
      dispatchCustomEvent(container, 'cl:radar-axis-flash', { axis: norm, reduced: true });
      return { flashed: false, reduced: true, axis: norm, count: 0 };
    }

    var scope = resolveContainer(container) || (typeof document !== 'undefined' ? document : null);
    var targets = findAxisElements(scope, norm);
    if (targets.all.length === 0) {
      return { flashed: false, reduced: false, axis: norm, count: 0 };
    }

    for (var i = 0; i < targets.all.length; i++) {
      var el = targets.all[i];
      if (el._clFlashTimer) {
        clearTimeout(el._clFlashTimer);
        el._clFlashTimer = null;
      }

      el.classList.remove('rd-motion-flash', 'rd-motion-beacon-surge', 'rd-motion-vert-burst');
      void el.offsetWidth;

      el.classList.add('rd-motion-flash');
      if (targets.beacon.indexOf(el) !== -1) {
        el.classList.add('rd-motion-beacon-surge');
      }
      if (targets.vert.indexOf(el) !== -1) {
        el.classList.add('rd-motion-vert-burst');
      }

      (function (elem) {
        elem._clFlashTimer = setTimeout(function () {
          elem.classList.remove('rd-motion-flash', 'rd-motion-beacon-surge', 'rd-motion-vert-burst');
          elem._clFlashTimer = null;
        }, DURATION.flashMs);
      })(el);
    }

    dispatchCustomEvent(scope, 'cl:radar-axis-flash', { axis: norm, reduced: false, elements: targets.all });
    return { flashed: true, reduced: false, axis: norm, count: targets.all.length };
  }

  function bindInteractions(container, onAxisSelect) {
    var root = resolveContainer(container);
    if (!root) {
      return function () {};
    }

    ensureStyles();

    if (typeof root._clRadarMotionCleanup === 'function') {
      root._clRadarMotionCleanup();
    }

    var currentHovered = null;

    var onMouseOver = function (e) {
      var target = e.target;
      if (!target) return;
      var k = getAxisKey(target);
      if (k && k !== currentHovered) {
        currentHovered = k;
        highlightAxis(root, k);
      }
    };

    var onMouseOut = function (e) {
      var rel = e.relatedTarget;
      var nextK = getAxisKey(rel);
      if (nextK !== currentHovered) {
        currentHovered = nextK;
        if (nextK) {
          highlightAxis(root, nextK);
        } else {
          clearHighlight(root);
        }
      }
    };

    var onClick = function (e) {
      var target = e.target;
      if (!target) return;
      var k = getAxisKey(target);
      if (!k) return;

      flashAxis(k, root);

      if (typeof onAxisSelect === 'function') {
        try {
          onAxisSelect(k, e);
        } catch (err) {
          if (typeof console !== 'undefined' && console.error) {
            console.error('[CLRadarMotion] onAxisSelect handler error:', err);
          }
        }
      }

      dispatchCustomEvent(root, 'cl:radar-axis-select', { axis: k, key: k, originalEvent: e });
    };

    var onFocusIn = function (e) {
      var k = getAxisKey(e.target);
      if (k && k !== currentHovered) {
        currentHovered = k;
        highlightAxis(root, k);
      }
    };

    var onFocusOut = function () {
      currentHovered = null;
      clearHighlight(root);
    };

    root.addEventListener('mouseover', onMouseOver, false);
    root.addEventListener('mouseout', onMouseOut, false);
    root.addEventListener('click', onClick, false);
    root.addEventListener('focusin', onFocusIn, false);
    root.addEventListener('focusout', onFocusOut, false);

    var cleanup = function () {
      root.removeEventListener('mouseover', onMouseOver, false);
      root.removeEventListener('mouseout', onMouseOut, false);
      root.removeEventListener('click', onClick, false);
      root.removeEventListener('focusin', onFocusIn, false);
      root.removeEventListener('focusout', onFocusOut, false);
      clearHighlight(root);
      if (root._clRadarMotionCleanup === cleanup) {
        delete root._clRadarMotionCleanup;
      }
    };

    root._clRadarMotionCleanup = cleanup;
    return cleanup;
  }

  function unbindInteractions(container) {
    var root = resolveContainer(container);
    if (root && typeof root._clRadarMotionCleanup === 'function') {
      root._clRadarMotionCleanup();
    }
  }

  var CLRadarMotion = {
    KEYS: KEYS,
    EN: EN,
    THEME: THEME,
    EASING: EASING,
    DURATION: DURATION,
    normalizeKey: normalizeKey,
    isReducedMotion: isReducedMotion,
    ensureStyles: ensureStyles,
    findAxisElements: findAxisElements,
    highlightAxis: highlightAxis,
    clearHighlight: clearHighlight,
    flashAxis: flashAxis,
    bindInteractions: bindInteractions,
    unbindInteractions: unbindInteractions
  };

  try {
    Object.defineProperty(CLRadarMotion, 'reducedMotion', {
      get: isReducedMotion,
      enumerable: true,
      configurable: true
    });
  } catch (e) {}

  return CLRadarMotion;
});
