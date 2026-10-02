/**
 * Castline · scene-crown-motion.js — 晶冠与全息悬浮卡微交互共振总线 (U04)
 * ============================================================================
 * 独占单元：U04 · 动效与微交互工程师 (Swarm 20260912-2315-crown-hud)
 * 产物路径：/Users/carmen/Desktop/星系/js/scene-crown-motion.js
 * 
 * 契约合规：
 * - C1 接口契约：挂载 window.CLSceneCrownMotion（并提供 window.CLRadarCrownMotion 兼容别名），
 *   全防御入参校验（null / undefined / 异常入参绝不报错）。
 * - C5 晶冠与悬浮卡光能共振：悬浮卡与 3D 晶冠顶点建立双向高亮共振，
 *   表盘整秒跳动（tick）时 8 张卡片与能量导轨注入同相位的量子微脉冲。
 * - C6 动效自适应与平稳降级：完整覆盖 prefers-reduced-motion: reduce，
 *   在无头与低配模式下平稳降级为静态高清轮廓。
 * - C7 独占产物原则：仅写入独占产物文件，严禁篡改主干文件与冻结清单。
 * 
 * 核心功能：
 * 1. bindHUDInteractions(container, onAttrSelect):
 *    - 监听 8 个全息悬浮卡 (.cl-lab.attr) 的 hover / mouseenter / mouseleave；
 *    - 滑过属性卡时：
 *      ① 当前卡片爆发高能霓虹高亮 (.hud-active)，其余卡片平滑半透明退让 (.hud-dimmed)；
 *      ② 触发该维激光导轨能量激增 (.conduit-surge)；
 *      ③ 派发自定义事件 `cl:scene-attr-hover`，同步激活 3D 晶体对应顶点的光芒与右坞明细条；
 *    - 点击卡片时触发冲击波 (.hud-wave / flashWave) 并安全回调 onAttrSelect(k)。
 * 2. tickResonance(dt, time, wallSec, reducedMotion):
 *    - 与系统整秒跳时同拍：整秒跳动时，为 8 张卡片注入同相位的量子微脉冲 (.hud-pulse)；
 * 3. 动效分层与时长缓动：严格遵循契约动效表 (EASING.out, EASING.io, EASING.back, DURATION)。
 * ============================================================================
 */

(function (root, factory) {
  'use strict';
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    var exp = factory();
    var globalScope = (typeof window !== 'undefined' && window) ||
                      (typeof globalThis !== 'undefined' && globalThis) ||
                      (typeof self !== 'undefined' && self) ||
                      (typeof global !== 'undefined' && global) ||
                      root ||
                      {};
    globalScope.CLSceneCrownMotion = exp;
    // 共享约定兼容别名
    if (!globalScope.CLRadarCrownMotion) {
      globalScope.CLRadarCrownMotion = exp;
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  // ────────────────────────────────────────────────────────────────────────────
  // 1. 共享约定规范与主题色彩
  // ────────────────────────────────────────────────────────────────────────────
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];

  var EN = {
    '智谋': 'MIND',
    '实力': 'FORCE',
    '意志': 'WILL',
    '魅力': 'CHARM',
    '情感': 'HEART',
    '野心': 'DRIVE',
    '权势': 'REACH',
    '道义': 'CODE'
  };

  var CN = {
    'MIND': '智谋',
    'FORCE': '实力',
    'WILL': '意志',
    'CHARM': '魅力',
    'HEART': '情感',
    'DRIVE': '野心',
    'REACH': '权势',
    'CODE': '道义'
  };

  var THEME = {
    obsidian: '#07060d',       // 黑曜石底色
    mint: '#7af0c8',           // 核心薄荷翠
    amber: '#ffb45c',          // 太阳琥珀
    violet: '#a688ff',         // 虚空秘紫
    hot: '#ff5c7c',            // 炽烈绯红
    cyan: '#58d5ff',           // 激光偏振青
    whiteCore: '#ffffff'       // 光核纯白
  };

  // 契约动效分层标准
  var EASING = {
    out: 'cubic-bezier(.16, 1, .3, 1)',      // 出场、展开与快进慢收
    io: 'cubic-bezier(.65, 0, .35, 1)',      // 平滑位移与能量流动
    back: 'cubic-bezier(.34, 1.32, .64, 1)'  // 轻过冲触感与回弹
  };

  // 动画时长常量 (毫秒)
  var DURATION = {
    hoverMs: 220,     // 悬停展开/退让过渡
    flashMs: 700,     // 激光导轨频闪
    waveMs: 650,      // 点击冲击波扩散
    pulseMs: 380,     // 秒跳微脉冲衰减
    settleMs: 340     // 秒针擒纵回弹收敛
  };

  // 独立动效样式表 ID
  var STYLE_ID = 'cl-scene-crown-motion-style';

  // 内部状态跟踪
  var _reducedMotionOverride = null; // null: 自动检测; true/false: 强制重写
  var _lastWallEpochSec = -1;
  var _lastTickTime = 0;
  var _activeHoverKey = null;

  // ────────────────────────────────────────────────────────────────────────────
  // 2. 基础安全校验与工具函数
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 安全数值转换，遇到 NaN / null / undefined / 非有限数时平稳回退
   * @param {*} val
   * @param {number} [fallback=0]
   * @returns {number}
   */
  function safeNum(val, fallback) {
    var fb = typeof fallback === 'number' && !isNaN(fallback) ? fallback : 0;
    var n = Number(val);
    return isFinite(n) && !isNaN(n) ? n : fb;
  }

  /**
   * 数值截断到 [min, max] 区间
   * @param {*} val
   * @param {number} min
   * @param {number} max
   * @returns {number}
   */
  function clamp(val, min, max) {
    var n = safeNum(val, min);
    return n < min ? min : (n > max ? max : n);
  }

  /**
   * 规范化维度键值
   * 支持中文维度名 ('智谋')、英文代码 ('MIND' / 'mind')、索引 (0..7)
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
    if (CN[upper]) return CN[upper];
    var num = parseInt(str, 10);
    if (!isNaN(num) && num >= 0 && num < KEYS.length && String(num) === str) {
      return KEYS[num];
    }
    return null;
  }

  /**
   * 从 DOM 节点提取属性维度键名
   * @param {Element} el
   * @returns {string|null}
   */
  function extractAttrKey(el) {
    if (!el || typeof el.getAttribute !== 'function') return null;

    // 1. data-* 属性检查
    var k = el.getAttribute('data-axis') ||
            el.getAttribute('data-attr') ||
            el.getAttribute('data-key');
    var norm = normalizeKey(k);
    if (norm) return norm;

    // 2. 子元素 data-axis 或类名检查
    try {
      var child = el.querySelector('[data-axis], [data-attr], [data-key]');
      if (child) {
        var ck = child.getAttribute('data-axis') ||
                 child.getAttribute('data-attr') ||
                 child.getAttribute('data-key');
        norm = normalizeKey(ck);
        if (norm) return norm;
      }
    } catch (e) {}

    // 3. 寻找标题 .ln 或 .cl-attr-hud-name 或 .ln-name
    try {
      var nameEl = el.querySelector('.cl-attr-hud-name, .ln, .cl-hud-key, .rd-k');
      if (nameEl && nameEl.textContent) {
        norm = normalizeKey(nameEl.textContent);
        if (norm) return norm;
      }
    } catch (e) {}

    // 4. classList 中包含的 key
    if (el.className && typeof el.className === 'string') {
      for (var i = 0; i < KEYS.length; i++) {
        var cnKey = KEYS[i];
        var enKey = EN[cnKey];
        var cls = el.className.toLowerCase();
        if (cls.indexOf('attr-' + enKey.toLowerCase()) !== -1 ||
            cls.indexOf('key-' + enKey.toLowerCase()) !== -1 ||
            cls.indexOf(cnKey) !== -1) {
          return cnKey;
        }
      }
    }

    return null;
  }

  /**
   * 检测系统是否开启 prefers-reduced-motion
   * @param {Object} [opt]
   * @returns {boolean}
   */
  function isReducedMotion(opt) {
    if (opt && typeof opt.reducedMotion === 'boolean') {
      return opt.reducedMotion;
    }
    if (_reducedMotionOverride !== null) {
      return _reducedMotionOverride;
    }
    try {
      if (typeof window !== 'undefined' && window.matchMedia) {
        return !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) {}
    return false;
  }

  /**
   * 允许外部代码为测试或设置面板显式设置减弱动效偏好
   * @param {boolean|null} val
   */
  function setReducedMotionOverride(val) {
    _reducedMotionOverride = typeof val === 'boolean' ? val : null;
  }

  /**
   * 获取当前减弱动效偏好重写值
   * @returns {boolean|null}
   */
  function getReducedMotionOverride() {
    return _reducedMotionOverride;
  }

  /**
   * 解析安全容器节点
   * @param {*} container
   * @returns {Element|null}
   */
  function resolveContainer(container) {
    if (!container) {
      if (typeof document !== 'undefined') {
        return document.getElementById('labels') || document.body || document.documentElement || null;
      }
      return null;
    }
    if (typeof container === 'string') {
      if (typeof document !== 'undefined') {
        try {
          return document.querySelector(container) || document.getElementById('labels') || document.body;
        } catch (e) {
          return null;
        }
      }
      return null;
    }
    /* 浏览器节点有 nodeType；无头测试与部分宿主提供的是 DOM-like 容器，
     * 只要具备查询能力就可安全使用，避免把合法的动态卡片容器退化成 body。 */
    if (typeof container === 'object' &&
        (container.nodeType || typeof container.querySelectorAll === 'function')) {
      return container;
    }
    return null;
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 3. 独立微交互样式注入 (ensureStyles)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 确保微交互与生命共振样式规则单例挂载 (无侵入、防重复)
   */
  function ensureStyles() {
    if (typeof document === 'undefined') return;
    if (document.getElementById(STYLE_ID)) return;

    var css = [
      '/* CLSceneCrownMotion 独立动效与微交互共振总线样式表 */',
      '',
      '/* 1. 全息悬浮卡基础过渡层 (契约缓动与时长) */',
      '.cl-lab.attr {',
      '  transition: transform 0.22s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)),',
      '              opacity 0.22s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)),',
      '              filter 0.22s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)),',
      '              box-shadow 0.22s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)),',
      '              border-color 0.22s ease;',
      '  will-change: transform, opacity, filter;',
      '}',
      '',
      '/* 2. 当前卡片爆发高能霓虹高亮 (.hud-active) */',
      '.cl-lab.attr.hud-active,',
      '.cl-lab.attr.hover {',
      '  opacity: 1 !important;',
      '  transform: translateY(-3px) scale(1.05) !important;',
      '  z-index: 3500 !important;',
      '  border-color: var(--abyss-mint, #7af0c8) !important;',
      '  box-shadow: 0 16px 44px rgba(0, 0, 0, 0.95),',
      '              0 0 24px rgba(122, 240, 200, 0.75),',
      '              0 0 48px rgba(122, 240, 200, 0.35),',
      '              inset 0 0 16px rgba(122, 240, 200, 0.22) !important;',
      '  filter: brightness(1.26) drop-shadow(0 0 12px rgba(122, 240, 200, 0.85)) !important;',
      '}',
      '',
      '.cl-lab.attr.hud-active .cl-attr-hud-lamp-core,',
      '.cl-lab.attr.hover .cl-attr-hud-lamp-core {',
      '  box-shadow: 0 0 10px #ffffff, 0 0 18px var(--abyss-mint, #7af0c8) !important;',
      '  background: #ffffff !important;',
      '}',
      '',
      '/* 3. 其余卡片平滑半透明退让 (.hud-dimmed) */',
      '.cl-lab.attr.hud-dimmed {',
      '  opacity: 0.32 !important;',
      '  filter: blur(1.2px) saturate(0.65) !important;',
      '  transform: scale(0.97) !important;',
      '  pointer-events: auto;',
      '}',
      '',
      '/* 4. 点击冲击波爆发 (.hud-wave / flashWave) */',
      '@keyframes clSceneCardShockwave {',
      '  0% {',
      '    transform: scale(1);',
      '    filter: brightness(2.4) drop-shadow(0 0 28px var(--abyss-signal, #ffb45c));',
      '    box-shadow: 0 0 40px var(--abyss-signal, #ffb45c);',
      '  }',
      '  35% {',
      '    transform: scale(1.11);',
      '    filter: brightness(1.8) drop-shadow(0 0 44px var(--abyss-mint, #7af0c8));',
      '    box-shadow: 0 0 52px var(--abyss-mint, #7af0c8);',
      '  }',
      '  70% {',
      '    transform: scale(1.02);',
      '    filter: brightness(1.2) drop-shadow(0 0 16px rgba(122, 240, 200, 0.5));',
      '  }',
      '  100% {',
      '    transform: scale(1);',
      '    filter: brightness(1);',
      '  }',
      '}',
      '.cl-lab.attr.hud-wave {',
      '  animation: clSceneCardShockwave 0.65s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)) both !important;',
      '  z-index: 4000 !important;',
      '}',
      '',
      '/* 5. 表盘整秒跳动同相位量子微脉冲 (.hud-pulse) */',
      '@keyframes clSceneCardQuantumPulse {',
      '  0% {',
      '    filter: brightness(1);',
      '    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.85);',
      '  }',
      '  22% {',
      '    filter: brightness(1.24) drop-shadow(0 0 14px rgba(122, 240, 200, 0.6));',
      '    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.92), 0 0 22px rgba(122, 240, 200, 0.38);',
      '  }',
      '  100% {',
      '    filter: brightness(1);',
      '    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.85);',
      '  }',
      '}',
      '.cl-lab.attr.hud-pulse:not(.hud-dimmed) {',
      '  animation: clSceneCardQuantumPulse 0.38s var(--abyss-ease-spring, cubic-bezier(.34, 1.35, .64, 1)) both;',
      '}',
      '',
      '/* 6. 激光能量导轨能量激增频闪 (.conduit-surge) */',
      '@keyframes clConduitSurgePulse {',
      '  0% {',
      '    stroke-width: 3.2px;',
      '    stroke-opacity: 0.85;',
      '    filter: drop-shadow(0 0 8px var(--abyss-mint, #7af0c8));',
      '  }',
      '  50% {',
      '    stroke-width: 4.5px;',
      '    stroke-opacity: 1;',
      '    filter: drop-shadow(0 0 18px var(--abyss-mint, #7af0c8)) drop-shadow(0 0 32px var(--abyss-signal, #ffb45c));',
      '  }',
      '  100% {',
      '    stroke-width: 3.2px;',
      '    stroke-opacity: 0.85;',
      '    filter: drop-shadow(0 0 8px var(--abyss-mint, #7af0c8));',
      '  }',
      '}',
      '.cl-lead.conduit-surge,',
      '.cl-lead.hud-active,',
      'path.cl-lead-surge,',
      'svg.cl-leads path.conduit-surge {',
      '  stroke: var(--abyss-mint, #7af0c8) !important;',
      '  stroke-opacity: 1 !important;',
      '  stroke-width: 3.6px !important;',
      '  animation: clConduitSurgePulse 0.4s ease-in-out infinite alternate !important;',
      '}',
      '.cl-lead.conduit-dimmed,',
      'svg.cl-leads path.conduit-dimmed {',
      '  stroke-opacity: 0.25 !important;',
      '  filter: none !important;',
      '}',
      '',
      '/* 7. 右侧坞明细条联动高亮响应 (.rd-bar.rd-motion-hover) */',
      '.rd-bar.rd-motion-hover {',
      '  background: linear-gradient(90deg, rgba(122, 240, 200, 0.22) 0%, rgba(255, 180, 92, 0.12) 65%, transparent 100%) !important;',
      '  border-left-color: var(--abyss-mint, #7af0c8) !important;',
      '  box-shadow: inset 0 0 16px rgba(122, 240, 200, 0.2), 0 0 12px rgba(122, 240, 200, 0.3) !important;',
      '  transform: translateX(5px) !important;',
      '}',
      '.rd-bar.rd-motion-dimmed {',
      '  opacity: 0.35 !important;',
      '}',
      '',
      '/* 8. 动效自适应降级规范 (prefers-reduced-motion: reduce) */',
      '@media (prefers-reduced-motion: reduce) {',
      '  .cl-lab.attr {',
      '    transition: none !important;',
      '    animation: none !important;',
      '  }',
      '  .cl-lab.attr.hud-active,',
      '  .cl-lab.attr.hover {',
      '    transform: none !important;',
      '    filter: drop-shadow(0 0 6px var(--abyss-mint, #7af0c8)) !important;',
      '    box-shadow: 0 0 0 1.5px var(--abyss-mint, #7af0c8) !important;',
      '  }',
      '  .cl-lab.attr.hud-dimmed {',
      '    transform: none !important;',
      '    filter: none !important;',
      '    opacity: 0.42 !important;',
      '  }',
      '  .cl-lab.attr.hud-wave,',
      '  .cl-lab.attr.hud-pulse {',
      '    animation: none !important;',
      '    transform: none !important;',
      '  }',
      '  .cl-lead.conduit-surge,',
      '  svg.cl-leads path.conduit-surge {',
      '    animation: none !important;',
      '    stroke-width: 2.5px !important;',
      '    filter: none !important;',
      '  }',
      '  .rd-bar.rd-motion-hover {',
      '    transform: none !important;',
      '    box-shadow: none !important;',
      '  }',
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

  // ────────────────────────────────────────────────────────────────────────────
  // 4. 激光导轨能量激增触发器 (triggerConduitSurge)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 触发或清除指定维度的激光导轨能量激增态
   * @param {string|null} key 维度名称
   * @param {boolean} active 是否激增
   * @param {Element} [container] 容器范围
   */
  function triggerConduitSurge(key, active, container) {
    if (typeof document === 'undefined') return;
    var normKey = normalizeKey(key);
    var doc = (container && container.ownerDocument) ? container.ownerDocument : document;

    // 1. 查找激光引线元素 (兼容 .cl-lead, .scene-lead, svg.cl-leads path, [data-lead-attr])
    var leadElements = [];
    try {
      var selectors = [
        '.cl-lead',
        '.scene-lead',
        'svg.cl-leads path',
        'svg.scene-lead-fx path',
        '[data-lead-key]',
        '[data-lead-attr]'
      ];
      var inContainer = container ? Array.prototype.slice.call(container.querySelectorAll(selectors.join(', '))) : [];
      var inDoc = doc ? Array.prototype.slice.call(doc.querySelectorAll(selectors.join(', '))) : [];
      var seen = [];
      var combined = inContainer.concat(inDoc);
      for (var s = 0; s < combined.length; s++) {
        var el = combined[s];
        if (seen.indexOf(el) === -1) {
          seen.push(el);
          leadElements.push(el);
        }
      }
    } catch (e) {
      leadElements = [];
    }

    // 2. 如果存在外部激光管线模块 (window.CLSceneLeadFX)，联动通知
    try {
      if (typeof window !== 'undefined' && window.CLSceneLeadFX) {
        if (typeof window.CLSceneLeadFX.surgeConduit === 'function') {
          window.CLSceneLeadFX.surgeConduit(normKey, active);
        }
      }
    } catch (e) {}

    if (!leadElements || !leadElements.length) return;

    for (var i = 0; i < leadElements.length; i++) {
      var lead = leadElements[i];
      if (!lead || !lead.classList) continue;

      var leadKey = lead.getAttribute('data-lead-key') ||
                    lead.getAttribute('data-lead-attr') ||
                    lead.getAttribute('data-key') ||
                    lead.getAttribute('data-axis');
      var leadNorm = normalizeKey(leadKey);

      // 如果未标注 data 属性，根据顺序索引尝试对齐
      if (!leadNorm && i < KEYS.length) {
        leadNorm = KEYS[i];
      }

      if (active && normKey && leadNorm === normKey) {
        lead.classList.add('conduit-surge');
        lead.classList.add('hud-active');
        lead.classList.remove('conduit-dimmed');
      } else if (active && normKey) {
        lead.classList.remove('conduit-surge');
        lead.classList.remove('hud-active');
        lead.classList.add('conduit-dimmed');
      } else {
        // 清除所有激增与退让
        lead.classList.remove('conduit-surge');
        lead.classList.remove('hud-active');
        lead.classList.remove('conduit-dimmed');
      }
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 5. 3D 晶冠顶点与右坞条形同步联动 (syncCrownAndDock)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 同步激活 3D 晶冠顶点光芒与右侧坞明细条
   * @param {string|null} key 维度名称
   * @param {boolean} active 是否激活
   */
  function syncCrownAndDock(key, active) {
    var normKey = normalizeKey(key);

    // 1. 同步 3D 场景晶冠顶点光辉
    try {
      var scene = null;
      if (typeof window !== 'undefined') {
        scene = (window.__cl && window.__cl.scene) ||
                window.scene ||
                (window.CLScene && window.CLScene.current);
      }
      if (scene && typeof scene.hoverAttr === 'function') {
        scene.hoverAttr(active && normKey ? normKey : null);
      }
    } catch (e) {}

    // 2. 同步右坞明细条 (.rd-bar)
    if (typeof document === 'undefined') return;
    try {
      var bars = document.querySelectorAll('.rd-bar');
      if (bars && bars.length) {
        for (var b = 0; b < bars.length; b++) {
          var bar = bars[b];
          if (!bar || !bar.classList) continue;

          var barKey = bar.getAttribute('data-key') || bar.getAttribute('data-axis');
          if (!barKey) {
            var kEl = bar.querySelector('.rb-k, .rd-k, .bar-key');
            if (kEl && kEl.textContent) {
              barKey = kEl.textContent.trim();
            }
          }
          if (!barKey && b < KEYS.length) {
            barKey = KEYS[b];
          }

          var barNorm = normalizeKey(barKey);
          if (active && normKey && barNorm === normKey) {
            bar.classList.add('rd-motion-hover');
            bar.classList.remove('rd-motion-dimmed');
          } else if (active && normKey) {
            bar.classList.remove('rd-motion-hover');
            bar.classList.add('rd-motion-dimmed');
          } else {
            bar.classList.remove('rd-motion-hover');
            bar.classList.remove('rd-motion-dimmed');
          }
        }
      }
    } catch (e) {}
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 6. 自定义事件广播通道 (dispatchHoverEvent & dispatchSelectEvent)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 派发 `cl:scene-attr-hover` 事件
   * @param {string|null} key 维度键
   * @param {boolean} active 激活态
   * @param {Element} [targetEl] 触发源元素
   */
  function dispatchHoverEvent(key, active, targetEl) {
    var normKey = normalizeKey(key);
    var index = normKey ? KEYS.indexOf(normKey) : -1;
    var detail = {
      key: normKey,
      keyEn: normKey ? EN[normKey] : '',
      index: index,
      active: Boolean(active),
      source: 'hud-card',
      timestamp: Date.now()
    };

    var evt = null;
    try {
      if (typeof CustomEvent === 'function') {
        evt = new CustomEvent('cl:scene-attr-hover', {
          detail: detail,
          bubbles: true,
          cancelable: true
        });
      }
    } catch (e) {}

    if (!evt && typeof document !== 'undefined' && document.createEvent) {
      try {
        evt = document.createEvent('CustomEvent');
        evt.initCustomEvent('cl:scene-attr-hover', true, true, detail);
      } catch (e) {}
    }

    if (evt) {
      if (targetEl && typeof targetEl.dispatchEvent === 'function') {
        try { targetEl.dispatchEvent(evt); } catch (e) {}
      }
      if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
        try { window.dispatchEvent(evt); } catch (e) {}
      } else if (typeof document !== 'undefined' && typeof document.dispatchEvent === 'function') {
        try { document.dispatchEvent(evt); } catch (e) {}
      }
    }
  }

  /**
   * 派发 `cl:scene-attr-select` 事件
   * @param {string} key 维度键
   * @param {Element} [targetEl] 触发源元素
   */
  function dispatchSelectEvent(key, targetEl) {
    var normKey = normalizeKey(key);
    var index = normKey ? KEYS.indexOf(normKey) : -1;
    var detail = {
      key: normKey,
      keyEn: normKey ? EN[normKey] : '',
      index: index,
      timestamp: Date.now()
    };

    var evt = null;
    try {
      if (typeof CustomEvent === 'function') {
        evt = new CustomEvent('cl:scene-attr-select', {
          detail: detail,
          bubbles: true,
          cancelable: true
        });
      }
    } catch (e) {}

    if (evt) {
      if (targetEl && typeof targetEl.dispatchEvent === 'function') {
        try { targetEl.dispatchEvent(evt); } catch (e) {}
      }
      if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
        try { window.dispatchEvent(evt); } catch (e) {}
      }
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 7. 悬停与退让核心实现 (highlightCard & clearHighlight)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 激活指定卡片，令其余卡片退让
   * @param {string} key
   * @param {Element} [container]
   */
  function highlightAttr(key, container) {
    var normKey = normalizeKey(key);
    if (!normKey) return;
    ensureStyles();

    var cEl = resolveContainer(container);
    var doc = cEl || (typeof document !== 'undefined' ? document : null);
    if (!doc) return;

    var cards = [];
    try {
      cards = Array.prototype.slice.call(doc.querySelectorAll('.cl-lab.attr'));
    } catch (e) {
      cards = [];
    }

    _activeHoverKey = normKey;
    var activeCardEl = null;

    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (!card || !card.classList) continue;
      var cKey = extractAttrKey(card);
      if (!cKey && i < KEYS.length) {
        cKey = KEYS[i];
      }

      if (cKey === normKey) {
        card.classList.add('hud-active');
        card.classList.remove('hud-dimmed');
        activeCardEl = card;
      } else {
        card.classList.remove('hud-active');
        card.classList.add('hud-dimmed');
      }
    }

    // 导轨激增
    triggerConduitSurge(normKey, true, cEl);

    // 晶冠顶点与明细条
    syncCrownAndDock(normKey, true);

    // 派发事件
    dispatchHoverEvent(normKey, true, activeCardEl || cEl);
  }

  /**
   * 清除高亮与退让状态
   * @param {Element} [container]
   */
  function clearHighlight(container) {
    _activeHoverKey = null;
    var cEl = resolveContainer(container);
    var doc = cEl || (typeof document !== 'undefined' ? document : null);
    if (!doc) return;

    var cards = [];
    try {
      cards = Array.prototype.slice.call(doc.querySelectorAll('.cl-lab.attr'));
    } catch (e) {
      cards = [];
    }

    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (!card || !card.classList) continue;
      card.classList.remove('hud-active');
      card.classList.remove('hud-dimmed');
    }

    // 导轨复位
    triggerConduitSurge(null, false, cEl);

    // 晶冠顶点与明细条复位
    syncCrownAndDock(null, false);

    // 派发事件
    dispatchHoverEvent(null, false, cEl);
  }

  /**
   * 触发单张卡片的点击冲击波动效
   * @param {string|Element} keyOrEl 维度名或卡片元素
   * @param {Element} [container]
   * @returns {boolean} 是否成功触发
   */
  function flashWave(keyOrEl, container) {
    if (typeof document === 'undefined') return false;
    ensureStyles();

    var targetCard = null;
    if (keyOrEl && typeof keyOrEl === 'object' && keyOrEl.nodeType) {
      targetCard = keyOrEl;
    } else {
      var normKey = normalizeKey(keyOrEl);
      if (!normKey) return false;
      var cEl = resolveContainer(container);
      var doc = cEl || document;
      var cards = doc.querySelectorAll('.cl-lab.attr');
      for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var k = extractAttrKey(card) || (i < KEYS.length ? KEYS[i] : null);
        if (k === normKey) {
          targetCard = card;
          break;
        }
      }
    }

    if (!targetCard || !targetCard.classList) return false;

    // 减弱动效模式保护
    if (isReducedMotion()) {
      targetCard.classList.remove('hud-wave');
      return true;
    }

    // 重新应用动画
    targetCard.classList.remove('hud-wave');
    // 强制回流以重启动画
    void targetCard.offsetWidth;
    targetCard.classList.add('hud-wave');

    var timer = setTimeout(function () {
      if (targetCard && targetCard.classList) {
        targetCard.classList.remove('hud-wave');
      }
    }, DURATION.waveMs + 50);

    return true;
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 8. 全息卡片交互绑定总线 (bindHUDInteractions)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 绑定全息悬浮卡微交互与生命节拍共振总线
   * 
   * @param {Element|string} [container] 悬浮卡宿主容器 (默认为 #labels 或 body)
   * @param {Function} [onAttrSelect] 点击属性卡片时的回调函数 onAttrSelect(k)
   * @returns {Object} 交互控制器句柄 { unbind, getActiveKey, setActiveKey, clearActive, flashWave, getCards }
   */
  function bindHUDInteractions(container, onAttrSelect) {
    ensureStyles();

    var rootEl = resolveContainer(container);
    var safeCallback = typeof onAttrSelect === 'function' ? onAttrSelect : function () {};

    // 存储已绑定的解绑动作
    var cleanups = [];

    if (!rootEl || typeof rootEl.querySelectorAll !== 'function') {
      // 纯 Node 或 JSC 无 DOM 环境下的安全句柄
      return {
        container: null,
        unbind: function () {},
        getActiveKey: function () { return _activeHoverKey; },
        setActiveKey: function (k) { highlightAttr(k, null); },
        clearActive: function () { clearHighlight(null); },
        flashWave: function (k) { return flashWave(k, null); },
        getCards: function () { return []; }
      };
    }

    /**
     * 获取当前所有 .cl-lab.attr 节点
     */
    function queryCards() {
      try {
        return Array.prototype.slice.call(rootEl.querySelectorAll('.cl-lab.attr'));
      } catch (e) {
        return [];
      }
    }

    // 代理容器事件监听 (Event Delegation)，防止动态渲染卡片丢失监听
    function handleMouseOver(e) {
      if (!e || !e.target) return;
      var card = e.target.closest ? e.target.closest('.cl-lab.attr') : null;
      if (!card || !rootEl.contains(card)) return;

      var k = extractAttrKey(card);
      if (!k) {
        var allCards = queryCards();
        var idx = allCards.indexOf(card);
        if (idx >= 0 && idx < KEYS.length) {
          k = KEYS[idx];
        }
      }

      if (k && k !== _activeHoverKey) {
        highlightAttr(k, rootEl);
      }
    }

    function handleMouseOut(e) {
      if (!e || !e.target) return;
      var card = e.target.closest ? e.target.closest('.cl-lab.attr') : null;
      if (!card) return;

      var related = e.relatedTarget;
      if (related && (card === related || card.contains(related))) {
        return; // 仍在该卡片内
      }

      // 检查是否移入了另一张卡片
      if (related && related.closest && related.closest('.cl-lab.attr')) {
        return; // 会由 handleMouseOver 接管
      }

      clearHighlight(rootEl);
    }

    function handleClick(e) {
      if (!e || !e.target) return;
      var card = e.target.closest ? e.target.closest('.cl-lab.attr') : null;
      if (!card || !rootEl.contains(card)) return;

      var k = extractAttrKey(card);
      if (!k) {
        var allCards = queryCards();
        var idx = allCards.indexOf(card);
        if (idx >= 0 && idx < KEYS.length) {
          k = KEYS[idx];
        }
      }

      if (k) {
        // 1. 触发冲击波
        flashWave(card, rootEl);

        // 2. 派发选择事件
        dispatchSelectEvent(k, card);

        // 3. 回调业务侧
        try {
          safeCallback(k);
        } catch (cbErr) {
          if (typeof console !== 'undefined' && console.warn) {
            console.warn('[CLSceneCrownMotion] onAttrSelect callback error:', cbErr);
          }
        }
      }
    }

    // 挂载代理监听器
    try {
      rootEl.addEventListener('mouseover', handleMouseOver, false);
      cleanups.push(function () {
        rootEl.removeEventListener('mouseover', handleMouseOver, false);
      });

      rootEl.addEventListener('mouseout', handleMouseOut, false);
      cleanups.push(function () {
        rootEl.removeEventListener('mouseout', handleMouseOut, false);
      });

      rootEl.addEventListener('click', handleClick, false);
      cleanups.push(function () {
        rootEl.removeEventListener('click', handleClick, false);
      });
    } catch (e) {}

    // 返回生命周期管理控制器
    return {
      container: rootEl,
      unbind: function () {
        clearHighlight(rootEl);
        for (var c = 0; c < cleanups.length; c++) {
          try { cleanups[c](); } catch (err) {}
        }
        cleanups = [];
      },
      getActiveKey: function () {
        return _activeHoverKey;
      },
      setActiveKey: function (k) {
        highlightAttr(k, rootEl);
      },
      clearActive: function () {
        clearHighlight(rootEl);
      },
      flashWave: function (k) {
        return flashWave(k, rootEl);
      },
      getCards: function () {
        return queryCards();
      }
    };
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 9. 整秒跳时同相生命共振脉冲 (tickResonance)
  // ────────────────────────────────────────────────────────────────────────────

  /**
   * 与系统整秒跳时同拍的量子微脉冲发生器
   * 
   * 每当表盘挂钟发生整秒跳动 (wallSec 整数跳变)，为 8 张卡片注入同相位的量子微脉冲，
   * 让空间卡片与时钟表盘产生有机同拍的生命呼吸感。
   * 
   * @param {number} [dt=0.016] 帧间时间差 (秒)
   * @param {number} [time=0] 累计动画运行时间 (秒)
   * @param {number} [wallSec] 挂钟秒数 (浮点数或整数，如 Date.now()/1000 或 scene.wallClock().sec)
   * @param {boolean} [reducedMotion] 是否减弱动效
   * @returns {Object} 脉冲状态摘要 { pulse, sec, frac, pulsed, reduced }
   */
  function tickResonance(dt, time, wallSec, reducedMotion) {
    var isReduced = isReducedMotion({ reducedMotion: reducedMotion });

    // 挂钟时间防御解析：优先同步 CLAbyssBreath 权威时钟
    var B = (typeof window !== 'undefined') ? window.CLAbyssBreath : null;
    var snap = (B && typeof B.snap === 'function') ? B.snap() : null;
    var currentWallSec = safeNum(wallSec, -1);
    if (currentWallSec < 0) {
      if (snap && isFinite(snap.t)) {
        currentWallSec = snap.t;
      } else if (typeof Date !== 'undefined' && Date.now) {
        currentWallSec = (Date.now() % 60000) / 1000;
      } else {
        currentWallSec = 0;
      }
    }

    var secInt = Math.floor(currentWallSec);
    var frac = currentWallSec - secInt;
    if (frac < 0 || frac >= 1) {
      frac = clamp(frac, 0, 0.999);
    }

    var animTime = safeNum(time, 0);
    var didPulseThisTick = false;

    // 检查是否发生整秒跳跃 (Second Transition)
    if (_lastWallEpochSec === -1) {
      _lastWallEpochSec = secInt;
      _lastTickTime = animTime;
    } else if (secInt !== _lastWallEpochSec) {
      _lastWallEpochSec = secInt;
      _lastTickTime = animTime;
      didPulseThisTick = true;
    }

    // 减弱动效模式：平稳降级为静态恒定，消除周期脉冲与高频闪变 (C6)
    if (isReduced) {
      return {
        pulse: 1.0,
        sec: secInt,
        frac: frac,
        pulsed: false,
        reduced: true
      };
    }

    // 计算量子微脉冲衰减包络 (指数衰减，匹配 scene.js TICK_SETTLE 0.34s)
    var elapsedSinceTick = animTime >= _lastTickTime ? (animTime - _lastTickTime) : frac;
    // 脉冲衰减强度 (0..1)
    var pulseK = Math.exp(-Math.max(0, elapsedSinceTick) * 5.0);

    // C6 · 晶冠神圣化与呼吸同频：改订阅 S3 CLAbyssBreath 总线，与雷达虹膜、潮汐图同相
    if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.phase === 'function') {
      var breathVal = window.CLAbyssBreath.breath();
      pulseK = Math.max(pulseK, breathVal * 0.85);
    }

    // 若检测到整秒跳变上升沿，为 8 张卡片注入微脉冲类名
    if (didPulseThisTick && typeof document !== 'undefined') {
      try {
        ensureStyles();
        var cards = document.querySelectorAll('.cl-lab.attr');
        if (cards && cards.length) {
          for (var i = 0; i < cards.length; i++) {
            var c = cards[i];
            if (!c || !c.classList || c.classList.contains('hud-dimmed')) continue;
            c.classList.remove('hud-pulse');
            // 触发重新流动
            void c.offsetWidth;
            c.classList.add('hud-pulse');
          }
        }
      } catch (e) {}

      // 派发整秒跳跃事件广播
      try {
        if (typeof CustomEvent === 'function' && typeof window !== 'undefined') {
          var pulseEvt = new CustomEvent('cl:scene-tick-pulse', {
            detail: {
              sec: secInt,
              pulse: pulseK,
              time: animTime
            },
            bubbles: true
          });
          window.dispatchEvent(pulseEvt);
        }
      } catch (e) {}
    }

    return {
      pulse: +pulseK.toFixed(3),
      sec: secInt,
      frac: +frac.toFixed(3),
      pulsed: didPulseThisTick,
      reduced: false
    };
  }

  // ────────────────────────────────────────────────────────────────────────────
  // 10. 模块导出接口定义
  // ────────────────────────────────────────────────────────────────────────────
  var CLSceneCrownMotion = {
    // 核心契约接口
    bindHUDInteractions: bindHUDInteractions,
    tickResonance: tickResonance,

    // 联动控制与动效接口
    highlightAttr: highlightAttr,
    clearHighlight: clearHighlight,
    flashWave: flashWave,
    triggerConduitSurge: triggerConduitSurge,
    syncCrownAndDock: syncCrownAndDock,
    ensureStyles: ensureStyles,

    // 辅助工具与无障碍
    isReducedMotion: isReducedMotion,
    setReducedMotionOverride: setReducedMotionOverride,
    getReducedMotionOverride: getReducedMotionOverride,
    normalizeKey: normalizeKey,
    extractAttrKey: extractAttrKey,
    safeNum: safeNum,
    clamp: clamp,

    // 共享约定规范常量
    KEYS: KEYS,
    EN: EN,
    CN: CN,
    THEME: THEME,
    EASING: EASING,
    DURATION: DURATION
  };

  if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
    window.CLAbyssBreath.subscribe(function () {
      // 晶冠响应呼吸总线心跳
    });
  }

  return CLSceneCrownMotion;
});
