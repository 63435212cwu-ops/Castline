/* @role component · @owns js/hud/status-states.js · @budget dom_nodes<=12 js_ms=0.04 · @contract v55 */
/**
 * status-states.js - W6 & I1 & I3: 空态 · 加载态 · 断态三态体系与铭文规范
 *
 * 核心法则：
 * 1. loading（加载态）：骨架屏，深渊雾纹理 + 优雅微光扫过（Shimmer Sweep）；
 * 2. empty（空态）：铭文式「此×尚无记载」+ 虚空符印，杜绝机械报错腔与生硬白屏，16 个显示件全量覆盖；
 * 3. degraded（断态/降级态）：数据部分缺失或断供时，降级收起不可用区块，而非整块崩溃消失；
 * 4. 推广标准：以 tree-narrate-ui 的守卫写法为范本，赋能全图 16 个显示构件，消灭静默 return；
 * 5. 信息层级：严格依从 I1 四档规范（--info-primary / secondary / tertiary / rune）。
 */
(function (g) {
  'use strict';

  var NAME = 'status-states';
  var VERSION = '55';

  var DOC = (typeof document !== 'undefined') ? document : null;

  /* 铭文风格默认空态文本字典（I3 空态铭文规范：16 个显示件全量覆盖，杜绝机械报错腔） */
  var EMPTY_INSCRIPTIONS = {
    'default': '此维尚无记载 · 诸元待定',
    'radar': '此魂八维待建档 · 宿命星轨未明',
    'deck': '牌阵空悬 · 待星位归一',
    'deck-badge': '此印尚无记载 · 待命格契约',
    'evidence': '此迹未载卷册 · 证据尚待归集',
    'attr-hud': '此界真元未显 · 属性尚在混沌',
    'plot-hud': '剧情未曾展开 · 卷宗尚待启封',
    'dock': '星港空泊 · 待航标锚定',
    'text-panel': '纪事未启 · 待岁月推移',
    'ops': '天枢静默 · 无待行法度',
    'viewbar': '苍穹无界 · 待诸天视阈',
    'app-modal': '经阁万卷 · 暂未启藏',
    'tray': '此际万籁俱寂 · 诸元平稳',
    'tree-tip': '此际万籁俱寂 · 未选细枝',
    'legend-tip': '图例隐迹 · 待指引探微',
    'peerchart': '星位未排 · 尚无双星相映',
    'cast-clones': '主命独行 · 暂无支线化身'
  };

  /* 空态对应古老符印体系（I3 规范：符印图形 + --info-rune 样式） */
  var EMPTY_SIGILS = {
    'default': '◇',
    'radar': '◇',
    'deck': '🂠',
    'deck-badge': '◈',
    'evidence': '📜',
    'attr-hud': '☵',
    'plot-hud': '❖',
    'dock': '⚓',
    'text-panel': '📖',
    'ops': '⚙',
    'viewbar': '👁',
    'app-modal': '📚',
    'tray': '⚑',
    'tree-tip': '⸙',
    'legend-tip': 'ᚱ',
    'peerchart': '⚔',
    'cast-clones': '✦'
  };

  /* 16 个显示件法定标识域 */
  var DOMAINS = [
    'radar', 'deck', 'deck-badge', 'evidence', 'attr-hud', 'plot-hud',
    'dock', 'text-panel', 'ops', 'viewbar', 'app-modal', 'tray',
    'tree-tip', 'legend-tip', 'peerchart', 'cast-clones'
  ];

  /* 注入基础微光扫过与三态样式（零重要性提权声明，契合 S3 门禁） */
  function injectStyles() {
    if (!DOC || typeof DOC.getElementById !== 'function' || !DOC.head || DOC.getElementById('clStatusStatesCss')) return;
    var s = DOC.createElement('style');
    s.id = 'clStatusStatesCss';
    s.textContent = [
      '/* D5/W6 三态体系基础样式与 I1/I3 规范（零提权声明） */',
      '.cl-state--loading { position: relative; overflow: hidden; min-height: 48px; border-radius: var(--abyss-radius-md, 6px); }',
      '.cl-state--loading::after {',
      '  content: ""; position: absolute; inset: 0; transform: translateX(-100%);',
      '  background: linear-gradient(90deg, transparent, var(--abyss-fade-08, rgba(255, 180, 92, 0.08)), transparent);',
      '  animation: clShimmer 1.8s infinite;',
      '}',
      '@keyframes clShimmer { 100% { transform: translateX(100%); } }',
      '.cl-skeleton-bar { height: 12px; margin: 8px 0; border-radius: var(--abyss-radius-sm, 4px); background: var(--abyss-border-subtle, rgba(255, 255, 255, 0.05)); }',
      '.cl-skeleton-bar.w-long { width: 85%; }',
      '.cl-skeleton-bar.w-mid { width: 55%; }',
      '.cl-skeleton-bar.w-short { width: 30%; }',
      '.cl-state--empty {',
      '  display: flex; flex-direction: column; align-items: center; justify-content: center;',
      '  padding: 24px 16px; text-align: center; color: var(--info-rune-color, var(--abyss-ink-ghost)); font-family: var(--info-rune-font, var(--abyss-font-serif, serif));',
      '}',
      '.cl-empty-sigil { font-size: 22px; line-height: 1; margin-bottom: 8px; opacity: var(--info-rune-opacity, 0.45); filter: drop-shadow(0 0 6px var(--abyss-signal, #ffb45c)); }',
      '.cl-empty-rune { font-size: var(--info-rune-fs, var(--abyss-fs-2xs, 12px)); letter-spacing: 0.12em; color: var(--info-rune-color, var(--abyss-ink-ghost)); font-family: var(--info-rune-font, var(--abyss-font-serif, serif)); }',
      '.cl-state--degraded { border-left: 2px dashed rgba(255, 180, 92, 0.4); opacity: 0.88; }',
      '.cl-degraded-tag { display: inline-block; font-size: 10px; padding: 1px 4px; border-radius: 3px; background: rgba(255,180,92,0.12); color: var(--abyss-signal, #ffb45c); margin-bottom: 4px; font-family: var(--abyss-font-mono, monospace); }'
    ].join('\n');
    DOC.head.appendChild(s);
  }

  /**
   * 创建 Loading 骨架容器
   */
  function renderLoading(options) {
    if (!DOC) return null;
    options = options || {};
    var container = DOC.createElement('div');
    container.className = 'cl-state--loading cl-panel-subtle';
    if (options.minHeight) container.style.minHeight = options.minHeight + 'px';

    var bars = options.bars || 3;
    for (var i = 0; i < bars; i++) {
      var bar = DOC.createElement('div');
      var widthCls = (i % 3 === 0) ? 'w-long' : ((i % 3 === 1) ? 'w-mid' : 'w-short');
      bar.className = 'cl-skeleton-bar ' + widthCls;
      container.appendChild(bar);
    }
    return container;
  }

  /**
   * 创建 Empty 铭文空态（I3 铭文格式 + 符印图形 + --info-rune 样式）
   */
  function renderEmpty(options) {
    if (!DOC) return null;
    options = options || {};
    var container = DOC.createElement('div');
    container.className = 'cl-state--empty';

    var key = options.domain || 'default';
    var sigil = DOC.createElement('div');
    sigil.className = 'cl-empty-sigil';
    sigil.textContent = options.sigil || EMPTY_SIGILS[key] || EMPTY_SIGILS.default;
    container.appendChild(sigil);

    var text = DOC.createElement('div');
    text.className = 'cl-empty-rune cl-info-rune';
    text.textContent = options.message || EMPTY_INSCRIPTIONS[key] || EMPTY_INSCRIPTIONS.default;
    container.appendChild(text);

    return container;
  }

  /**
   * 包装 Degraded 断态节点（收起缺失数据）
   */
  function renderDegraded(options) {
    if (!DOC) return null;
    options = options || {};
    var container = DOC.createElement('div');
    container.className = 'cl-state--degraded';

    if (options.notice) {
      var tag = DOC.createElement('span');
      tag.className = 'cl-degraded-tag';
      tag.textContent = '〔部分未全 · ' + options.notice + '〕';
      container.appendChild(tag);
    }

    if (options.contentEl) {
      container.appendChild(options.contentEl);
    }
    return container;
  }

  /**
   * 便捷装配状态到指定容器
   */
  function applyState(targetEl, state, options) {
    if (!targetEl) return false;
    while (targetEl.firstChild) targetEl.removeChild(targetEl.firstChild);

    if (state === 'loading') {
      targetEl.appendChild(renderLoading(options));
    } else if (state === 'empty') {
      targetEl.appendChild(renderEmpty(options));
    } else if (state === 'degraded') {
      targetEl.appendChild(renderDegraded(options));
    }
    targetEl.setAttribute('data-cl-state', state);
    return true;
  }

  /**
   * 清除状态并恢复容器
   */
  function clearState(targetEl) {
    if (!targetEl) return false;
    targetEl.removeAttribute('data-cl-state');
    return true;
  }

  /**
   * 获取容器当前挂载状态
   */
  function getState(targetEl) {
    if (!targetEl || !targetEl.getAttribute) return 'none';
    return targetEl.getAttribute('data-cl-state') || 'none';
  }

  function init() {
    injectStyles();
  }

  if (DOC && DOC.readyState === 'loading') {
    DOC.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  var API = {
    name: NAME,
    version: VERSION,
    renderLoading: renderLoading,
    renderEmpty: renderEmpty,
    renderDegraded: renderDegraded,
    applyState: applyState,
    clearState: clearState,
    getState: getState,
    inscriptions: EMPTY_INSCRIPTIONS,
    sigils: EMPTY_SIGILS,
    DOMAINS: DOMAINS,
    stats: function () {
      return {
        name: NAME,
        version: VERSION,
        ready: true,
        domains: Object.keys(EMPTY_INSCRIPTIONS),
        count: DOMAINS.length
      };
    }
  };

  g.CLStatusStates = API;
  if (!g.__cl) g.__cl = {};
  g.__cl.statusStates = API;

})(typeof window !== 'undefined' ? window : this);
