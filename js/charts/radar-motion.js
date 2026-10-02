/**
 * Castline · radar-motion.js — 雷达微交互与动效驱动总线 (U06)
 *
 * 契约核心实现：
 * 1. bindInteractions(container, onAxisSelect):
 *    统一为雷达的 SVG 胶囊 (.rd-lab)、明细条 (.rd-bar)、顶点 (.rd-vert) 绑定悬停与点击联动。
 *    当悬停某一维度时，同步高亮 SVG 轴线 (.rd-axis)、光柱 (.rd-beacon)、光锥 (.rd-lamp-cone) 与对应条形 (.rd-bar)，
 *    并发出基于薄荷翠 (#7af0c8) 与太阳琥珀 (#ffb45c) 的触感微光；
 * 2. flashAxis(k, container):
 *    触发指定维度的光能量爆发脉冲动效（契约缓动：cubic-bezier(.16, 1, .3, 1)）；
 * 3. 自动检测 window.matchMedia('(prefers-reduced-motion: reduce)')，
 *    在用户开启减弱动效时自动跳过高频闪烁与位移动效；
 * 4. 防御性入参校验：所有导出接口保证 null / undefined / 空参数安全不崩 (R1)。
 */
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

  // 共享约定规范
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

  // 主题语义色谱
  var THEME = {
    obsidian: '#07060d', // 黑曜石底色
    mint: '#7af0c8',     // 核心薄荷翠
    amber: '#ffb45c',    // 太阳琥珀
    violet: '#a688ff',   // 虚空秘紫
    hot: '#ff5c7c'       // 炽烈绯红
  };

  // 契约动效分层标准
  var EASING = {
    out: 'cubic-bezier(.16, 1, .3, 1)',      // 出场与快进慢收
    io: 'cubic-bezier(.65, 0, .35, 1)',      // 平滑位移
    back: 'cubic-bezier(.34, 1.32, .64, 1)'  // 轻过冲触感
  };

  // 动画时长常量
  var DURATION = {
    flashMs: 700,
    hoverMs: 220
  };

  // 样式表注入 ID
  var STYLE_ID = 'cl-radar-motion-style';

  /**
   * 规范化维度键值
   * 支持中文名、英文代码（如 MIND/mind）、索引号（0..7）
   * @param {*} k
   * @returns {string|null}
   */
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

  /**
   * 自动检测 prefers-reduced-motion
   * @returns {boolean}
   */
  function isReducedMotion() {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {
      return false;
    }
  }

  // 动态监听系统 reduced-motion 偏好变化
  if (typeof window !== 'undefined' && window.matchMedia) {
    try {
      var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      var mqHandler = function () {};
      if (mq.addEventListener) {
        mq.addEventListener('change', mqHandler);
      } else if (mq.addListener) {
        mq.addListener(mqHandler);
      }
    } catch (e) {}
  }

  /**
   * 确保微交互样式规则挂载（无侵入、单例）
   */
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

  /**
   * 解析安全容器节点
   * @param {*} container
   * @returns {Element|null}
   */
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

  /**
   * 从 DOM 节点及其祖先提取对应的八维键名
   * @param {Element} el
   * @returns {string|null}
   */
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

  /**
   * 在给定范围内查找指定维度的所有相关 DOM 元素
   * @param {Element|Document} root
   * @param {string} k
   * @returns {object}
   */
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

    // 若当前 scope 处于局部子树且缺失明细条或 SVG，自动向外探测联动物体
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

  /**
   * 安全派发自定义事件
   */
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

  /**
   * 高亮某一特定维度（悬停/联动）
   * @param {*} container
   * @param {*} k
   */
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

    // 查询作用域内全部相关节点以实现高低频分层
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

  /**
   * 清除所有高亮与降权
   * @param {*} container
   */
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

  /**
   * 触发指定维度的光能量爆发脉冲动效
   * 自动检测 prefers-reduced-motion，若减弱动效开启则跳过高频闪烁
   * @param {*} k 维度标识
   * @param {*} container 可选容器
   * @returns {object} 执行状态报告
   */
  function flashAxis(k, container) {
    var norm = normalizeKey(k);
    if (!norm) {
      return { flashed: false, reduced: false, axis: null, count: 0 };
    }

    ensureStyles();
    var reduced = isReducedMotion();

    // 减弱动效规范：自动跳过高频闪烁，仅派发降级事件
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
      // 清除旧有动画计时器
      if (el._clFlashTimer) {
        clearTimeout(el._clFlashTimer);
        el._clFlashTimer = null;
      }

      // 重置动效类并触发重排
      el.classList.remove('rd-motion-flash', 'rd-motion-beacon-surge', 'rd-motion-vert-burst');
      void el.offsetWidth;

      el.classList.add('rd-motion-flash');
      if (targets.beacon.indexOf(el) !== -1) {
        el.classList.add('rd-motion-beacon-surge');
      }
      if (targets.vert.indexOf(el) !== -1) {
        el.classList.add('rd-motion-vert-burst');
      }

      // 注册动画生命周期结束清理
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

  /**
   * 统一为雷达的 SVG 胶囊 (.rd-lab)、明细条 (.rd-bar)、顶点 (.rd-vert) 绑定悬停与点击联动
   * @param {Element|string} container 容器元素或选择器
   * @param {Function} onAxisSelect 点击选择回调 (k, event)
   * @returns {Function} 解绑函数
   */
  function bindInteractions(container, onAxisSelect) {
    var root = resolveContainer(container);
    if (!root) {
      return function () {};
    }

    ensureStyles();

    // 防止同容器重复绑定
    if (typeof root._clRadarMotionCleanup === 'function') {
      root._clRadarMotionCleanup();
    }

    var currentHovered = null;

    // 悬停移入（事件委托）
    var onMouseOver = function (e) {
      var target = e.target;
      if (!target) return;
      var k = getAxisKey(target);
      if (k && k !== currentHovered) {
        currentHovered = k;
        highlightAxis(root, k);
      }
    };

    // 悬停移出（事件委托）
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

    // 点击事件（联动、反馈与脉冲）
    var onClick = function (e) {
      var target = e.target;
      if (!target) return;
      var k = getAxisKey(target);
      if (!k) return;

      // 触发爆发光能脉冲动效
      flashAxis(k, root);

      // 触发业务选择回调
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

    // 键盘辅助聚焦支持
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

    // 绑定事件监听
    root.addEventListener('mouseover', onMouseOver, false);
    root.addEventListener('mouseout', onMouseOut, false);
    root.addEventListener('click', onClick, false);
    root.addEventListener('focusin', onFocusIn, false);
    root.addEventListener('focusout', onFocusOut, false);

    // 清理与解绑函数
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

  /**
   * 解绑指定容器上的雷达动效监听器
   * @param {Element|string} container
   */
  function unbindInteractions(container) {
    var root = resolveContainer(container);
    if (root && typeof root._clRadarMotionCleanup === 'function') {
      root._clRadarMotionCleanup();
    }
  }

  // 纯对象模块导出
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

  // 提供 reducedMotion 属性便捷访问
  try {
    Object.defineProperty(CLRadarMotion, 'reducedMotion', {
      get: isReducedMotion,
      enumerable: true,
      configurable: true
    });
  } catch (e) {}

  return CLRadarMotion;
});
