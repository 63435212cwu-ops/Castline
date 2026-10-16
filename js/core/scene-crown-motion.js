
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
    if (!globalScope.CLRadarCrownMotion) {
      globalScope.CLRadarCrownMotion = exp;
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

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
    obsidian: '#07060d',
    mint: '#7af0c8',
    amber: '#ffb45c',
    violet: '#a688ff',
    hot: '#ff5c7c',
    cyan: '#58d5ff',
    whiteCore: '#ffffff'
  };

  var EASING = {
    out: 'cubic-bezier(.16, 1, .3, 1)',
    io: 'cubic-bezier(.65, 0, .35, 1)',
    back: 'cubic-bezier(.34, 1.32, .64, 1)'
  };

  var DURATION = {
    hoverMs: 220,
    flashMs: 700,
    waveMs: 650,
    pulseMs: 380,
    settleMs: 340
  };

  var STYLE_ID = 'cl-scene-crown-motion-style';

  var _reducedMotionOverride = null;
  var _lastWallEpochSec = -1;
  var _lastTickTime = 0;
  var _activeHoverKey = null;


  function safeNum(val, fallback) {
    var fb = typeof fallback === 'number' && !isNaN(fallback) ? fallback : 0;
    var n = Number(val);
    return isFinite(n) && !isNaN(n) ? n : fb;
  }

  function clamp(val, min, max) {
    var n = safeNum(val, min);
    return n < min ? min : (n > max ? max : n);
  }

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

  function extractAttrKey(el) {
    if (!el || typeof el.getAttribute !== 'function') return null;

    var k = el.getAttribute('data-axis') ||
            el.getAttribute('data-attr') ||
            el.getAttribute('data-key');
    var norm = normalizeKey(k);
    if (norm) return norm;

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

    try {
      var nameEl = el.querySelector('.cl-attr-hud-name, .ln, .cl-hud-key, .rd-k');
      if (nameEl && nameEl.textContent) {
        norm = normalizeKey(nameEl.textContent);
        if (norm) return norm;
      }
    } catch (e) {}

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

  function setReducedMotionOverride(val) {
    _reducedMotionOverride = typeof val === 'boolean' ? val : null;
  }

  function getReducedMotionOverride() {
    return _reducedMotionOverride;
  }

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
    if (typeof container === 'object' &&
        (container.nodeType || typeof container.querySelectorAll === 'function')) {
      return container;
    }
    return null;
  }


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


  function triggerConduitSurge(key, active, container) {
    if (typeof document === 'undefined') return;
    var normKey = normalizeKey(key);
    var doc = (container && container.ownerDocument) ? container.ownerDocument : document;

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
        lead.classList.remove('conduit-surge');
        lead.classList.remove('hud-active');
        lead.classList.remove('conduit-dimmed');
      }
    }
  }


  function syncCrownAndDock(key, active) {
    var normKey = normalizeKey(key);

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

    triggerConduitSurge(normKey, true, cEl);

    syncCrownAndDock(normKey, true);

    dispatchHoverEvent(normKey, true, activeCardEl || cEl);
  }

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

    triggerConduitSurge(null, false, cEl);

    syncCrownAndDock(null, false);

    dispatchHoverEvent(null, false, cEl);
  }

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

    if (isReducedMotion()) {
      targetCard.classList.remove('hud-wave');
      return true;
    }

    targetCard.classList.remove('hud-wave');
    void targetCard.offsetWidth;
    targetCard.classList.add('hud-wave');

    var timer = setTimeout(function () {
      if (targetCard && targetCard.classList) {
        targetCard.classList.remove('hud-wave');
      }
    }, DURATION.waveMs + 50);

    return true;
  }


  function bindHUDInteractions(container, onAttrSelect) {
    ensureStyles();

    var rootEl = resolveContainer(container);
    var safeCallback = typeof onAttrSelect === 'function' ? onAttrSelect : function () {};

    var cleanups = [];

    if (!rootEl || typeof rootEl.querySelectorAll !== 'function') {
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

    function queryCards() {
      try {
        return Array.prototype.slice.call(rootEl.querySelectorAll('.cl-lab.attr'));
      } catch (e) {
        return [];
      }
    }

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
        return;
      }

      if (related && related.closest && related.closest('.cl-lab.attr')) {
        return;
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
        flashWave(card, rootEl);

        dispatchSelectEvent(k, card);

        try {
          safeCallback(k);
        } catch (cbErr) {
          if (typeof console !== 'undefined' && console.warn) {
            console.warn('[CLSceneCrownMotion] onAttrSelect callback error:', cbErr);
          }
        }
      }
    }

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


  function tickResonance(dt, time, wallSec, reducedMotion) {
    var isReduced = isReducedMotion({ reducedMotion: reducedMotion });

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

    if (_lastWallEpochSec === -1) {
      _lastWallEpochSec = secInt;
      _lastTickTime = animTime;
    } else if (secInt !== _lastWallEpochSec) {
      _lastWallEpochSec = secInt;
      _lastTickTime = animTime;
      didPulseThisTick = true;
    }

    if (isReduced) {
      return {
        pulse: 1.0,
        sec: secInt,
        frac: frac,
        pulsed: false,
        reduced: true
      };
    }

    var elapsedSinceTick = animTime >= _lastTickTime ? (animTime - _lastTickTime) : frac;
    var pulseK = Math.exp(-Math.max(0, elapsedSinceTick) * 5.0);

    if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.phase === 'function') {
      var breathVal = window.CLAbyssBreath.breath();
      pulseK = Math.max(pulseK, breathVal * 0.85);
    }

    if (didPulseThisTick && typeof document !== 'undefined') {
      try {
        ensureStyles();
        var cards = document.querySelectorAll('.cl-lab.attr');
        if (cards && cards.length) {
          for (var i = 0; i < cards.length; i++) {
            var c = cards[i];
            if (!c || !c.classList || c.classList.contains('hud-dimmed')) continue;
            c.classList.remove('hud-pulse');
            void c.offsetWidth;
            c.classList.add('hud-pulse');
          }
        }
      } catch (e) {}

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

  var CLSceneCrownMotion = {
    bindHUDInteractions: bindHUDInteractions,
    tickResonance: tickResonance,

    highlightAttr: highlightAttr,
    clearHighlight: clearHighlight,
    flashWave: flashWave,
    triggerConduitSurge: triggerConduitSurge,
    syncCrownAndDock: syncCrownAndDock,
    ensureStyles: ensureStyles,

    isReducedMotion: isReducedMotion,
    setReducedMotionOverride: setReducedMotionOverride,
    getReducedMotionOverride: getReducedMotionOverride,
    normalizeKey: normalizeKey,
    extractAttrKey: extractAttrKey,
    safeNum: safeNum,
    clamp: clamp,

    KEYS: KEYS,
    EN: EN,
    CN: CN,
    THEME: THEME,
    EASING: EASING,
    DURATION: DURATION
  };

  if (typeof window !== 'undefined' && window.CLAbyssBreath && typeof window.CLAbyssBreath.subscribe === 'function') {
    window.CLAbyssBreath.subscribe(function () {
    });
  }

  return CLSceneCrownMotion;
});
