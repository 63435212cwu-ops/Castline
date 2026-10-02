/**
 * Castline · radar-bars-enhanced.js (U08)
 * 属性条明细与全息进度条增强模块
 *
 * 核心能力：
 * 1. renderBars(attrs, benchmark, activeKey, options):
 *    生成雷达下方的八维条形明细 HTML。
 *    每行包括：维度名、英文代号、全书平均对照标记线 (benchmark tick mark)、
 *    相对于全书均值的差值徽章 (如 +12 薄荷绿, -8 柔紫)、当前分值、证据条数标签、以及推断依据简评。
 *    支持通过 activeKey 处于高亮选中态。
 *    v71 W3·U8 起：差值徽章旁追加全书百分位读数（如 P87，来自 benchmark.percentileOf）；
 *    当 benchmark.scope === 'camp'（阵营基准）时，刻线与徽章 tooltip 注明「本阵营均值」。
 * 2. renderRow(key, attrs, benchmark, activeKey, options):
 *    单行明细条渲染，便于局部重绘或自定义遍历。
 * 3. calcDiff(score, benchmarkValue):
 *    高精度安全差值量化器，返回数值、符号文本与语义标签。
 * 4. diffBadge(score, benchmarkValue):
 *    生成差值徽章 HTML 片段。
 *
 * 共享约定：
 * KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义']
 * EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' }
 * 主题色彩（变量引用）：黑曜石 var(--bg), 薄荷 var(--mint), 太阳琥珀 var(--signal), 虚空紫 var(--violet), 绯红 var(--hot)
 *
 * 最小使用示例 / Minimal Usage Example:
 * ```javascript
 * // 1. 准备数据
 * var attrs = {
 *   '智谋': { score: 85, evidence: ['运筹帷幄', '连环布局'], basis: '谋略深远，决胜千里', low: false },
 *   '实力': { score: 62, evidence: ['近战不敌'], basis: '偏重指挥，个人武力中平', low: false }
 * };
 * var benchmark = { '智谋': 73, '实力': 70 }; // 或 CLRadarBenchmark 实例
 *
 * // 2. 渲染雷达下方增强属性条（高亮选中「智谋」）
 * var html = window.CLRadarBarsEnhanced.renderBars(attrs, benchmark, '智谋');
 * document.getElementById('barsContainer').innerHTML = html;
 * ```
 */

(function (root, factory) {
  'use strict';
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    var exp = factory();
    root.CLRadarBarsEnhanced = exp;
    if (typeof window !== 'undefined') {
      window.CLRadarBarsEnhanced = exp;
    }
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // 共享标准常量（8维跨题材统一标准）
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

  // 与 serve.py 同步的标准维度释义
  var DEF = {
    智谋: '认知、判断、算计与布局（计谋 / 推理 / 学识 / 商业与专业判断 / 识人），以计划是否奏效为据',
    实力: '该世界体系内的直接对抗与行动能力（武功 / 修为 / 枪法 / 体能 / 统兵 / 专业硬实力），以实战结果为据',
    意志: '承压、坚持、不被击垮的韧性（逆境中的选择、忍耐与自制）',
    魅力: '令他人倾心、信服或追随的吸引力（人望 / 口才 / 气度 / 被爱慕与被追随的事实）',
    情感: '情感浓度、共情与牵绊之深（爱憎强度、为亲友的付出、被触动的程度），不是情绪化程度',
    野心: '欲望与向上攫取的驱动力（目标大小、付出的代价、对现状的不满足）',
    权势: '当下实际可调动的地位、资源、人脉与靠山（官职 / 门派或公司地位 / 财富 / 家族 / 势力）',
    道义: '底线、原则与对他人的善意（守诺 / 护弱 / 公正）；低分 = 为达目的不择手段'
  };

  /**
   * HTML 安全字符转义
   */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /**
   * 等级档位计算（与 radar.js 算法契约保持一致）
   */
  function tierOf(score, isLow) {
    if (score == null || isNaN(score)) return 'pend';
    if (isLow) return 'low';
    if (score >= 96) return 'legend';
    if (score >= 85) return 'hi';
    if (score >= 70) return 'up';
    if (score >= 41) return 'mid';
    return 'low';
  }

  /**
   * 等级档位名称
   */
  function tierName(score, isLow) {
    if (score == null || isNaN(score)) return '待建档';
    if (isLow) return '低证保守';
    if (score >= 96) return '传说级';
    if (score >= 85) return '一方之最';
    if (score >= 70) return '圈内出色';
    if (score >= 41) return '常人';
    if (score >= 21) return '弱于常人';
    return '明显低于常人';
  }

  /**
   * 安全提取单维度属性数据，防御各种输入格式
   */
  function getAttr(attrs, key) {
    if (!attrs) {
      return { score: null, evidence: [], basis: '', low: true, pending: true };
    }
    var store = attrs.attrs || attrs;
    var raw = store[key] !== undefined ? store[key] : (EN[key] && store[EN[key]] !== undefined ? store[EN[key]] : null);

    if (raw == null) {
      return { score: null, evidence: [], basis: '', low: true, pending: true };
    }
    if (typeof raw === 'number') {
      if (isNaN(raw) || !isFinite(raw)) {
        return { score: null, evidence: [], basis: '', low: true, pending: true };
      }
      return {
        score: Math.max(0, Math.min(100, Math.round(raw))),
        evidence: [],
        basis: '',
        low: false,
        pending: false
      };
    }
    if (typeof raw === 'object') {
      var isPend = !!raw.pending || raw.score == null;
      var num = isPend ? null : Number(raw.score);
      var validNum = (num !== null && !isNaN(num) && isFinite(num)) ? Math.max(0, Math.min(100, Math.round(num))) : null;
      var evList = Array.isArray(raw.evidence) ? raw.evidence : [];
      var isLow = !!raw.low || evList.length === 0;

      return {
        score: validNum,
        evidence: evList,
        basis: typeof raw.basis === 'string' ? raw.basis : '',
        low: isLow,
        pending: isPend || validNum === null,
        unverified: raw.unverified || 0,
        chain: raw.chain || ''
      };
    }

    var parsed = parseFloat(raw);
    if (!isNaN(parsed) && isFinite(parsed)) {
      return {
        score: Math.max(0, Math.min(100, Math.round(parsed))),
        evidence: [],
        basis: '',
        low: false,
        pending: false
      };
    }

    return { score: null, evidence: [], basis: '', low: true, pending: true };
  }

  /**
   * 从各种基准结构（对象、实例、数值表）中安全获取指定维度的全书均值
   */
  function extractBenchmark(benchmark, key) {
    if (benchmark == null) return null;

    // 优先调用基准模块的 getBenchAvg 方法
    if (typeof benchmark.getBenchAvg === 'function') {
      var v1 = benchmark.getBenchAvg(benchmark, key);
      if (typeof v1 === 'number' && !isNaN(v1)) return v1;
    }
    if (typeof benchmark.getAvg === 'function') {
      var v2 = benchmark.getAvg(key);
      if (typeof v2 === 'number' && !isNaN(v2)) return v2;
    }

    var en = EN[key];
    var val = null;

    if (typeof benchmark[key] === 'number') {
      val = benchmark[key];
    } else if (benchmark[key] && typeof benchmark[key].avg === 'number') {
      val = benchmark[key].avg;
    } else if (benchmark[key] && typeof benchmark[key].avgRound === 'number') {
      val = benchmark[key].avgRound;
    } else if (benchmark.avg && typeof benchmark.avg[key] === 'number') {
      val = benchmark.avg[key];
    } else if (benchmark.averages && typeof benchmark.averages[key] === 'number') {
      val = benchmark.averages[key];
    } else if (en && typeof benchmark[en] === 'number') {
      val = benchmark[en];
    } else if (en && benchmark[en] && typeof benchmark[en].avg === 'number') {
      val = benchmark[en].avg;
    } else if (en && benchmark.avg && typeof benchmark.avg[en] === 'number') {
      val = benchmark.avg[en];
    }

    if (val !== null && typeof val === 'number' && !isNaN(val) && isFinite(val)) {
      return Math.max(0, Math.min(100, Math.round(val * 10) / 10));
    }
    return null;
  }

  /**
   * 从基准对象安全获取指定维度的全书百分位（0-100）。
   * 优先使用 benchmark.percentileOf（computeBenchmark 返回的实例方法，阵营基准亦恒为全书口径）；
   * 基准对象不带该方法时回落到 CLRadarBenchmark 模块级入口（当前缓存的全书基准）。
   */
  function extractPercentile(benchmark, key, score) {
    if (score == null || isNaN(score)) return null;
    if (benchmark && typeof benchmark.percentileOf === 'function') {
      var p = benchmark.percentileOf(key, score);
      if (typeof p === 'number' && !isNaN(p) && isFinite(p)) return p;
      return null;
    }
    if (typeof window !== 'undefined' && window.CLRadarBenchmark && typeof window.CLRadarBenchmark.percentileOf === 'function') {
      var p2 = window.CLRadarBenchmark.percentileOf(key, score);
      if (typeof p2 === 'number' && !isNaN(p2) && isFinite(p2)) return p2;
    }
    return null;
  }

  /**
   * 计算相对全书均值的差值
   * 返回: { diff: number|null, text: string, type: 'pos'|'neg'|'zero'|'na', isAbove: boolean, isBelow: boolean }
   */
  function calcDiff(score, benchmarkVal) {
    if (score == null || isNaN(score) || benchmarkVal == null || isNaN(benchmarkVal)) {
      return {
        diff: null,
        text: '—',
        type: 'na',
        isAbove: false,
        isBelow: false,
        isEqual: false
      };
    }
    var roundBm = Math.round(benchmarkVal);
    var d = Math.round(score - roundBm);
    if (d > 0) {
      return {
        diff: d,
        text: '+' + d,
        type: 'pos',
        isAbove: true,
        isBelow: false,
        isEqual: false
      };
    }
    if (d < 0) {
      return {
        diff: d,
        text: String(d),
        type: 'neg',
        isAbove: false,
        isBelow: true,
        isEqual: false
      };
    }
    return {
      diff: 0,
      text: '±0',
      type: 'zero',
      isAbove: false,
      isBelow: false,
      isEqual: true
    };
  }

  /**
   * 生成差值徽章 HTML
   * 遵循视觉契约：+12 薄荷绿 (diff-pos), -8 柔紫 (diff-neg), ±0 银灰 (diff-zero)
   */
  function diffBadge(score, benchmarkVal, options) {
    options = options || {};
    var diffInfo = calcDiff(score, benchmarkVal);
    var title = '';
    var cls = 'rd-bar-delta rb-diff';
    var scopeLabel = options.scope === 'camp' ? '本阵营均值' : '全书均值';

    if (diffInfo.type === 'pos') {
      cls += ' diff-pos positive';
      title = '相较' + scopeLabel + ' ' + diffInfo.text;
    } else if (diffInfo.type === 'neg') {
      cls += ' diff-neg negative';
      title = '相较' + scopeLabel + ' ' + diffInfo.text;
    } else if (diffInfo.type === 'zero') {
      cls += ' diff-zero zero';
      title = '与' + scopeLabel + '持平';
    } else {
      cls += ' diff-na na';
      title = '暂无基准对照';
    }

    if (options.className) cls += ' ' + options.className;

    return '<span class="' + cls + '" data-diff="' + (diffInfo.diff !== null ? diffInfo.diff : '') + '" title="' + esc(title) + '">' +
      esc(diffInfo.text) +
      '</span>';
  }

  /**
   * 判断维度键是否命中高亮选中态
   */
  function checkActive(key, activeKey, index) {
    if (activeKey == null) return false;
    if (typeof activeKey === 'number') {
      return activeKey === index;
    }
    var str = String(activeKey).trim().toLowerCase();
    if (!str) return false;
    if (key.toLowerCase() === str) return true;
    if (EN[key] && EN[key].toLowerCase() === str) return true;
    return false;
  }

  /**
   * 自动注入组件独占样式（自适应、无裸色值、无裸像素）
   */
  function ensureStyles() {
    if (typeof document === 'undefined') return;
    if (document.getElementById('cl-radar-bars-enhanced-css')) return;

    var css = [
      '/* Castline · radar-bars-enhanced 动态注入规范样式 */',
      '.rd-bars.rd-bars-enhanced {',
      '  display: flex;',
      '  flex-direction: column;',
      '  gap: 0.45rem;',
      '  margin: 0.35rem 0 0.5rem;',
      '  width: 100%;',
      '  font-family: var(--sans);',
      '}',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced {',
      '  display: grid;',
      '  grid-template-columns: minmax(4.6rem, 5.2rem) 1fr auto auto minmax(2rem, auto) auto;',
      '  grid-template-areas:',
      '    "k t diff pct v ev"',
      '    "b b b    b   b  b";',
      '  column-gap: 0.6rem;',
      '  row-gap: 0.25rem;',
      '  align-items: center;',
      '  padding: 0.45rem 0.65rem;',
      '  border-left-width: 0.15rem;',
      '  border-left-style: solid;',
      '  border-left-color: var(--line);',
      '  background: var(--glass);',
      '  border-radius: 0.15rem;',
      '  cursor: pointer;',
      '  position: relative;',
      '  transition: background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;',
      '}',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced:hover,',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.on,',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.active {',
      '  background: var(--glass-2);',
      '  border-left-color: var(--signal);',
      '}',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.on,',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.active {',
      '  box-shadow: inset 0.15rem 0 0 var(--signal);',
      '}',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.low {',
      '  opacity: 0.72;',
      '}',
      '.rd-bars-enhanced .rd-bar.rd-bar-enhanced.pend {',
      '  opacity: 0.55;',
      '}',
      '/* 维度名与代号 */',
      '.rd-bars-enhanced .rb-k {',
      '  grid-area: k;',
      '  display: flex;',
      '  align-items: baseline;',
      '  gap: 0.35rem;',
      '  font-size: 0.82rem;',
      '  font-weight: 600;',
      '  color: var(--ink);',
      '  line-height: 1.1;',
      '}',
      '.rd-bars-enhanced .rb-k .rb-name {',
      '  letter-spacing: 0.04em;',
      '}',
      '.rd-bars-enhanced .rb-k i,',
      '.rd-bars-enhanced .rb-k .rb-en {',
      '  font-family: var(--mono);',
      '  font-size: 0.69rem;',
      '  font-style: normal;',
      '  color: var(--ink-3);',
      '  letter-spacing: 0.12em;',
      '}',
      '/* 全息进度条与基准刻度线 */',
      '.rd-bars-enhanced .rb-t {',
      '  grid-area: t;',
      '  position: relative;',
      '  height: 0.38rem;',
      '  background: var(--line);',
      '  border-radius: 0.2rem;',
      '  overflow: visible;',
      '}',
      '.rd-bars-enhanced .rb-fill {',
      '  display: block;',
      '  height: 100%;',
      '  border-radius: inherit;',
      '  background: linear-gradient(90deg, var(--cold), var(--signal));',
      '  box-shadow: 0 0 0.35rem var(--signal);',
      '  transform-origin: left;',
      '  transition: width 0.45s ease;',
      '}',
      '.rd-bars-enhanced .rd-bar.low .rb-fill {',
      '  background: var(--ink-3);',
      '  box-shadow: none;',
      '}',
      '/* 全书基准对照标记线 (Benchmark Tick) */',
      '.rd-bars-enhanced .rb-benchmark-tick,',
      '.rd-bars-enhanced .rd-bar-benchmark {',
      '  position: absolute;',
      '  top: -0.15rem;',
      '  bottom: -0.15rem;',
      '  width: 0.12rem;',
      '  background: var(--mint);',
      '  box-shadow: 0 0 0.25rem var(--mint);',
      '  transform: translateX(-50%);',
      '  border-radius: 0.05rem;',
      '  pointer-events: none;',
      '  z-index: 2;',
      '}',
      '.rd-bars-enhanced .rb-benchmark-tick .rb-tick-pip {',
      '  position: absolute;',
      '  top: -0.2rem;',
      '  left: 50%;',
      '  transform: translateX(-50%);',
      '  width: 0.32rem;',
      '  height: 0.32rem;',
      '  border-radius: 50%;',
      '  background: var(--mint);',
      '}',
      '/* 相对于全书均值的差值徽章 */',
      '.rd-bars-enhanced .rb-diff,',
      '.rd-bars-enhanced .rd-bar-delta {',
      '  grid-area: diff;',
      '  font-family: var(--mono);',
      '  font-size: 0.65rem;',
      '  font-weight: 700;',
      '  padding: 0.12em 0.38em;',
      '  border-radius: 0.18rem;',
      '  text-align: center;',
      '  white-space: nowrap;',
      '  letter-spacing: 0.02em;',
      '  border-width: 0.06rem;',
      '  border-style: solid;',
      '}',
      '.rd-bars-enhanced .rb-diff.diff-pos,',
      '.rd-bars-enhanced .rd-bar-delta.positive {',
      '  color: var(--mint);',
      '  border-color: var(--mint);',
      '  background: var(--glass);',
      '}',
      '.rd-bars-enhanced .rb-diff.diff-neg,',
      '.rd-bars-enhanced .rd-bar-delta.negative {',
      '  color: var(--violet);',
      '  border-color: var(--violet);',
      '  background: var(--glass);',
      '}',
      '.rd-bars-enhanced .rb-diff.diff-zero,',
      '.rd-bars-enhanced .rd-bar-delta.zero {',
      '  color: var(--ink-2);',
      '  border-color: var(--line-2);',
      '  background: var(--glass);',
      '}',
      '.rd-bars-enhanced .rb-diff.diff-na,',
      '.rd-bars-enhanced .rd-bar-delta.na {',
      '  color: var(--ink-3);',
      '  border-color: var(--line);',
      '  background: transparent;',
      '}',
      '/* 全书百分位读数 (Percentile) */',
      '.rd-bars-enhanced .rb-pct {',
      '  grid-area: pct;',
      '  font-family: var(--mono);',
      '  font-size: 0.65rem;',
      '  font-weight: 700;',
      '  color: var(--ink-2);',
      '  letter-spacing: 0.03em;',
      '  white-space: nowrap;',
      '  text-align: center;',
      '  align-self: center;',
      '}',
      '/* 当前分值 */',
      '.rd-bars-enhanced .rb-v {',
      '  grid-area: v;',
      '  font-family: var(--mono);',
      '  font-size: 0.82rem;',
      '  font-weight: 700;',
      '  color: var(--ink);',
      '  text-align: right;',
      '  font-variant-numeric: tabular-nums;',
      '}',
      '.rd-bars-enhanced .rd-bar.tier-hi .rb-v,',
      '.rd-bars-enhanced .rd-bar.tier-legend .rb-v {',
      '  color: var(--signal-2);',
      '}',
      '.rd-bars-enhanced .rd-bar.tier-up .rb-v {',
      '  color: var(--mint);',
      '}',
      '.rd-bars-enhanced .rd-bar.pend .rb-v {',
      '  color: var(--signal);',
      '}',
      '/* 证据条数标签 */',
      '.rd-bars-enhanced .rb-ev,',
      '.rd-bars-enhanced .rd-bar-evidence {',
      '  grid-area: ev;',
      '  font-family: var(--mono);',
      '  font-size: 0.69rem;',
      '  color: var(--ink-2);',
      '  background: var(--line);',
      '  padding: 0.1em 0.35em;',
      '  border-radius: 0.18rem;',
      '  text-align: center;',
      '  white-space: nowrap;',
      '}',
      '.rd-bars-enhanced .rb-ev.low {',
      '  color: var(--ink-3);',
      '}',
      '.rd-bars-enhanced .rb-ev.pend {',
      '  color: var(--ink-3);',
      '  opacity: 0.5;',
      '}',
      '/* 推断依据简评 */',
      '.rd-bars-enhanced .rb-b,',
      '.rd-bars-enhanced .rd-bar-basis {',
      '  grid-area: b;',
      '  font-size: 0.7rem;',
      '  color: var(--ink-3);',
      '  line-height: 1.45;',
      '  overflow: hidden;',
      '  text-overflow: ellipsis;',
      '  white-space: nowrap;',
      '}',
      '.rd-bars-enhanced .rd-bar-enhanced:hover .rb-b,',
      '.rd-bars-enhanced .rd-bar-enhanced.on .rb-b {',
      '  color: var(--ink-2);',
      '}',
      '.rd-bars-enhanced .rd-bar-enhanced.pend .rb-b {',
      '  font-style: italic;',
      '  opacity: 0.75;',
      '}',
      '/* 降级与无障碍无动效保护 (prefers-reduced-motion) */',
      '@media (prefers-reduced-motion: reduce) {',
      '  .rd-bars-enhanced .rd-bar.rd-bar-enhanced,',
      '  .rd-bars-enhanced .rb-fill,',
      '  .rd-bars-enhanced .rb-benchmark-tick {',
      '    animation: none !important;',
      '    transition: none !important;',
      '  }',
      '}'
    ].join('\n');

    var style = document.createElement('style');
    style.id = 'cl-radar-bars-enhanced-css';
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
  }

  /**
   * 单行明细条渲染
   * @param {string} key - 维度名（如 '智谋'）
   * @param {Object} attrs - 八维属性字典或当前角色
   * @param {Object} [benchmark] - 全书基准对象
   * @param {string|number} [activeKey] - 激活选中的维度名或索引
   * @param {Object} [options] - 可选控制参数
   * @returns {string} 单行 HTML 片段
   */
  function renderRow(key, attrs, benchmark, activeKey, options) {
    options = options || {};
    var index = typeof options.index === 'number' ? options.index : KEYS.indexOf(key);
    if (index === -1) index = 0;

    var enCode = EN[key] || '';
    var a = getAttr(attrs, key);
    var isPending = a.pending;
    var isLow = a.low;
    var score = a.score;

    var bmVal = extractBenchmark(benchmark, key);
    var isActive = checkActive(key, activeKey, index);
    var tier = isPending ? 'pend' : tierOf(score, isLow);

    // 基准口径：'book' 全书 / 'camp' 本阵营（由 computeBenchmark 的 byCamp 桶携带 scope 标记）
    var benchScope = options.scope || (benchmark && benchmark.scope) || 'book';
    var scopeLabel = benchScope === 'camp' ? '本阵营均值' : '全书均值';

    // 进度条百分比
    var fillWidth = isPending ? 0 : (score !== null ? score : 0);

    // 基准标记线 HTML
    var tickHtml = '';
    if (bmVal !== null) {
      var tickLeft = Math.max(0, Math.min(100, Math.round(bmVal)));
      tickHtml = '<span class="rd-bar-benchmark rb-benchmark-tick rb-tick" style="left:' + tickLeft + '%;" title="' + scopeLabel + ' ' + bmVal + '" data-benchmark="' + bmVal + '">' +
        '<i class="rb-tick-pip"></i>' +
        '</span>';
    }

    // 差值徽章 HTML
    var diffHtml = diffBadge(score, bmVal, { scope: benchScope });

    // 全书百分位读数（如 P87）：百分位恒为全书口径，即使对照基准切换为本阵营
    var pct = (!isPending && score !== null) ? extractPercentile(benchmark, key, score) : null;
    var pctHtml = '';
    if (pct !== null) {
      pctHtml = '<span class="rb-pct" data-percentile="' + pct + '" title="全书百分位 P' + pct + ' · 在已建档角色中优于约 ' + pct + '%">P' + pct + '</span>';
    }

    // 证据条数标签
    var evCount = a.evidence ? a.evidence.length : 0;
    var evText = isPending ? '—' : evCount + 'E';
    var evCls = 'rb-ev rd-bar-evidence' + (isPending ? ' pend' : isLow ? ' low' : '');
    var evTitle = isPending ? '待建档 · 暂无证据' : (isLow ? '证据不足（' + evCount + '条），保守估计' : '有原文依据 ' + evCount + ' 条');
    var evHtml = '<span class="' + evCls + '" data-evidence="' + evCount + '" title="' + esc(evTitle) + '">' + esc(evText) + '</span>';

    // 推断依据简评
    var basisText = '';
    if (isPending) {
      basisText = '待建档 · 未评分';
    } else if (a.basis) {
      basisText = a.basis;
    } else if (isLow) {
      basisText = '材料未直接支撑，保守估计';
    } else {
      basisText = '有原文明确支撑';
    }

    // 容器类名
    var rowClass = [
      'rd-bar',
      'rd-bar-enhanced',
      'tier-' + tier,
      isLow ? 'low' : '',
      isPending ? 'pend' : '',
      isActive ? 'on active' : ''
    ].filter(Boolean).join(' ');

    // 屏幕阅读器友好文本
    var ariaText = key + ' ' + (isPending ? '待建档' : score + '分') +
      (bmVal !== null ? '，' + scopeLabel + ' ' + bmVal : '') +
      (pct !== null ? '，全书百分位 P' + pct : '') +
      '，证据 ' + evCount + ' 条' +
      (isLow ? '（低置信）' : '') +
      (isActive ? '，当前聚焦选中' : '');

    var animDelay = (index * 0.04).toFixed(2);

    return '<div class="' + rowClass + '"' +
      ' data-axis="' + esc(key) + '"' +
      ' data-en="' + esc(enCode) + '"' +
      ' data-score="' + (score !== null ? score : '') + '"' +
      ' data-benchmark="' + (bmVal !== null ? bmVal : '') + '"' +
      ' data-confidence="' + (isLow ? 'low' : 'supported') + '"' +
      ' data-active="' + (isActive ? 'true' : 'false') + '"' +
      ' role="button"' +
      ' tabindex="0"' +
      ' aria-label="' + esc(ariaText) + '"' +
      ' style="animation-delay:' + animDelay + 's;">' +
      '<div class="rb-k">' +
      '<span class="rb-name">' + esc(key) + '</span>' +
      '<i class="rb-en">' + esc(enCode) + '</i>' +
      '</div>' +
      '<div class="rb-t" role="progressbar" aria-valuenow="' + (score !== null ? score : 0) + '" aria-valuemin="0" aria-valuemax="100">' +
      '<i class="rb-fill" style="width:' + fillWidth + '%;"></i>' +
      tickHtml +
      '</div>' +
      diffHtml +
      pctHtml +
      '<span class="rb-v mono">' + (isPending ? '—' : score) + '</span>' +
      evHtml +
      '<div class="rb-b rd-bar-basis" title="' + esc(basisText) + '">' + esc(basisText) + '</div>' +
      '</div>';
  }

  /**
   * 1. renderBars(attrs, benchmark, activeKey, options)
   * 生成雷达下方的八维条形明细 HTML
   *
   * @param {Object} attrs - 角色的 8 维属性对象（支持 c.attrs 或纯字典）
   * @param {Object} [benchmark] - 全书基准对照对象（来自 CLRadarBenchmark 或纯字典）
   * @param {string|number} [activeKey] - 当前高亮选中的维度名或代号
   * @param {Object} [options] - 自定义渲染选项
   * @returns {string} 完整的八维条形明细 HTML 字符串
   */
  function renderBars(attrs, benchmark, activeKey, options) {
    options = options || {};
    ensureStyles();

    var rows = [];
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var rowOpt = { index: i };
      rows.push(renderRow(k, attrs, benchmark, activeKey, rowOpt));
    }

    var outerClass = 'rd-bars rd-bars-enhanced' + (options.className ? ' ' + options.className : '');
    return '<div class="' + outerClass + '" role="region" aria-label="八维属性条形明细">' +
      rows.join('') +
      '</div>';
  }

  // 对外暴露 API 纯对象
  return {
    KEYS: KEYS,
    EN: EN,
    DEF: DEF,
    renderBars: renderBars,
    barsHTML: renderBars,
    renderRow: renderRow,
    calcDiff: calcDiff,
    diffBadge: diffBadge,
    extractBenchmark: extractBenchmark,
    getAttr: getAttr,
    tierOf: tierOf,
    tierName: tierName,
    ensureStyles: ensureStyles
  };
}));
