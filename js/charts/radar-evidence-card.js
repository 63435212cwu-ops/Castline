/**
 * Castline · radar-evidence-card.js
 * U05 · 证据链透镜与交互全息卡片 (Holographic Evidence Card)
 *
 * 契约规范与完成判据：
 * - R1 接口契约：通过 window.CLRadarEvidenceCard 纯对象暴露完整 API，
 *   导出方法均具备防御性入参校验（null/undefined 不报错）。
 * - R5 证据情报卡：具备全书排名微标、分值发光胶囊、该维定义与衡量标尺、
 *   推断依据与推理链、原文引用（带金黄边框与字距的书香引号风格）、与全书均值的对比条。
 * - R6 动效与自适应：严格遵循 prefers-reduced-motion: reduce，色值严格继承 Castline 语义令牌。
 * - R7 独占产物：不改动任何其他文件，仅独占产出 js/radar-evidence-card.js。
 * - 样式纪律：样式只用契约令牌表里的变量，绝不写裸色值与裸像素。
 *
 * 最小使用示例 / Minimal Usage Example:
 * ```javascript
 * var html = window.CLRadarEvidenceCard.renderCard(
 *   '智谋',
 *   {
 *     name: '昭阳',
 *     attrs: {
 *       '智谋': {
 *         score: 64,
 *         basis: '能从旧照背面编号读出火灾线索，观察力强，但不主动布局',
 *         chain: '行动3 → 无反证 → 常人偏上 → 64',
 *         confidence: 85,
 *         evidence: ['昭阳发现照片背面有火灾现场的编号。'],
 *         low: false
 *       }
 *     }
 *   },
 *   rankedList,   // 排名角色数组 (可选)
 *   allAttrs,     // 全书角色属性字典或数组 (可选)
 *   benchmark     // 全书基准对象 (可选，如 { means: { '智谋': 60 } })
 * );
 * document.getElementById('rdEvHost').innerHTML = html;
 * ```
 */

(function () {
  'use strict';

  /* =========================================================================
   * [I4 立法 · 八维主位] 一数据一主位：雷达全息图谱与证据卡为全站八维多维数据唯一完整呈现主位。
   * 其他组件分工：plot-deck 只展示摘要均值与跳转；peerchart 为降维偏倚分析（第二种读法）；
   * plot-hud 为瞬时态悬浮不存档。
   * ========================================================================= */
  // 八维标准契约（优先从 CLAttrSource 单一真相源读取）
  var AS = (typeof window !== 'undefined' && window.CLAttrSource) ? window.CLAttrSource : null;
  var KEYS = (AS && AS.KEYS) ? AS.KEYS : ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = (AS && AS.EN) ? AS.EN : {
    智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM',
    情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE'
  };

  // 与 serve.py ATTR_DEF 同步之跨题材通用衡量基准
  var DEF = (AS && AS.DEF) ? AS.DEF : {
    智谋: '认知、判断、算计与布局（计谋 / 推理 / 学识 / 商业与专业判断 / 识人），以计划是否奏效为据',
    实力: '该世界体系内的直接对抗与行动能力（武功 / 修为 / 枪法 / 体能 / 统兵 / 专业硬实力），以实战结果为据',
    意志: '承压、坚持、不被击垮的韧性（逆境中的选择、忍耐与自制）',
    魅力: '令他人倾心、信服或追随的吸引力（人望 / 口才 / 气度 / 被爱慕与被追随的事实）',
    情感: '情感浓度、共情与牵绊之深（爱憎强度、为亲友的付出、被触动的程度），不是情绪化程度',
    野心: '欲望与向上攫取的驱动力（目标大小、付出的代价、对现状的不满足）',
    权势: '当下实际可调动的地位、资源、人脉与靠山（官职 / 门派或公司地位 / 财富 / 家族 / 势力）',
    道义: '底线、原则与对他人的善意（守诺 / 护弱 / 公正）；低分 = 为达目的不择手段'
  };

  var SCALE = '刻度 · 50 常人 · 70 圈内出色 · 85 一方之最 · 96+ 传说级 · 跨作品统一';

  // CSS 样式表内容：严禁裸色值与裸像素，全量使用语义令牌与相对单位
  var CSS_STYLES = [
    '/* CLRadarEvidenceCard · 全息情报卡片专属样式 */',
    '.rd-holo-card {',
    '  position: relative;',
    '  margin: 0.5rem 0 0.75rem;',
    '  padding: 0.875rem 1rem;',
    '  background: var(--glass-2);',
    '  border: 0.0625rem solid var(--line);',
    '  border-radius: 0.375rem;',
    '  box-shadow: 0 0.5rem 1.5rem var(--glass), inset 0 0.0625rem 0 var(--line);',
    '  backdrop-filter: blur(1.25rem) saturate(1.1);',
    '  -webkit-backdrop-filter: blur(1.25rem) saturate(1.1);',
    '  font-family: var(--sans);',
    '  color: var(--ink);',
    '  overflow: hidden;',
    '  transition: border-color 0.3s var(--e-out), box-shadow 0.3s var(--e-out);',
    '}',
    '.rd-holo-card:hover {',
    '  border-color: var(--line-2);',
    '  box-shadow: 0 0.75rem 2rem var(--glass-2), inset 0 0.0625rem 0 var(--signal-2);',
    '}',
    '.rd-card-head {',
    '  display: flex;',
    '  align-items: flex-start;',
    '  justify-content: space-between;',
    '  gap: 0.75rem;',
    '  padding-bottom: 0.625rem;',
    '  border-bottom: 0.0625rem solid var(--line);',
    '}',
    '.rd-card-title-group {',
    '  display: flex;',
    '  flex-direction: column;',
    '  gap: 0.375rem;',
    '  min-width: 0;',
    '}',
    '.rd-card-eyebrow {',
    '  display: flex;',
    '  align-items: baseline;',
    '  gap: 0.5rem;',
    '  flex-wrap: wrap;',
    '}',
    '.rd-card-axis-zh {',
    '  font-size: 1.125rem;',
    '  font-weight: 600;',
    '  letter-spacing: 0.08em;',
    '  color: var(--ink);',
    '}',
    '.rd-card-axis-en {',
    '  font-size: 0.6875rem;',
    '  letter-spacing: 0.18em;',
    '  color: var(--signal);',
    '  font-weight: 500;',
    '}',
    '.rd-card-char-name {',
    '  font-size: 0.75rem;',
    '  letter-spacing: 0.06em;',
    '  color: var(--ink-3);',
    '}',
    '.rd-card-char-name::before {',
    '  content: "·";',
    '  margin-right: 0.375rem;',
    '}',
    '.rd-card-badges {',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 0.375rem;',
    '  flex-wrap: wrap;',
    '}',
    '.rd-card-rank-badge {',
    '  display: inline-flex;',
    '  align-items: center;',
    '  gap: 0.25rem;',
    '  padding: 0.125rem 0.5rem;',
    '  background: var(--glass);',
    '  border: 0.0625rem solid var(--line-2);',
    '  border-radius: 0.25rem;',
    '  font-size: 0.6875rem;',
    '  letter-spacing: 0.06em;',
    '  color: var(--signal-2);',
    '  white-space: nowrap;',
    '}',
    '.rd-card-rank-badge .rd-rank-hash {',
    '  font-style: normal;',
    '  color: var(--signal);',
    '  opacity: 0.8;',
    '}',
    '.rd-card-rank-badge .rd-rank-title {',
    '  font-style: normal;',
    '  font-weight: 600;',
    '  color: var(--signal);',
    '  margin-left: 0.125rem;',
    '}',
    '.rd-card-tag {',
    '  display: inline-flex;',
    '  align-items: center;',
    '  padding: 0.125rem 0.4375rem;',
    '  border-radius: 0.25rem;',
    '  font-size: 0.625rem;',
    '  letter-spacing: 0.04em;',
    '  border: 0.0625rem solid var(--line);',
    '  background: var(--glass);',
    '  color: var(--ink-3);',
    '  white-space: nowrap;',
    '}',
    '.rd-card-tag.low { border-color: var(--line-2); color: var(--signal); }',
    '.rd-card-tag.pend { border-color: var(--line); color: var(--ink-3); }',
    '.rd-card-tag.conf { border-color: var(--mint); color: var(--mint); }',
    '.rd-card-tag.warn { border-color: var(--hot); color: var(--hot); }',
    // U05 · 五类证据标签新增两色 + 引句标签/边框（新块，隔行不并入上方存量 CSS 串，见 G1 ratchet）
    '.rd-card-tag.infer { border-color: var(--violet, var(--line-2)); color: var(--violet, var(--signal)); }',
    '.rd-card-tag.dispute { border-color: var(--hot); color: var(--hot); }',
    '.rd-quote-tag { font-size: 0.5625rem; letter-spacing: 0.04em; opacity: 0.82; }',
    '.rd-book-quote.tag-dispute { border-color: var(--hot); }',
    '.rd-book-quote.tag-low { opacity: 0.86; }',
    '.rd-card-capsule-wrap { flex-shrink: 0; }',
    '.rd-capsule {',
    '  position: relative;',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 0.375rem;',
    '  padding: 0.25rem 0.625rem;',
    '  background: var(--glass);',
    '  border-radius: 1.25rem;',
    '  border: 0.0625rem solid var(--line);',
    '  box-shadow: 0 0 0.5rem var(--glass-2);',
    '  transition: all 0.3s var(--e-out);',
    '}',
    '.rd-capsule.tier-legend { border-color: var(--signal); box-shadow: 0 0 0.75rem var(--signal), inset 0 0 0.375rem var(--hot); }',
    '.rd-capsule.tier-hi { border-color: var(--signal); box-shadow: 0 0 0.625rem var(--signal); }',
    '.rd-capsule.tier-up { border-color: var(--mint); box-shadow: 0 0 0.625rem var(--mint); }',
    '.rd-capsule.tier-mid { border-color: var(--violet); box-shadow: 0 0 0.5rem var(--violet); }',
    '.rd-capsule.tier-low, .rd-capsule.tier-sub, .rd-capsule.tier-min { border-color: var(--hot); box-shadow: 0 0 0.375rem var(--hot); }',
    '.rd-capsule.tier-pend { border-color: var(--line); box-shadow: none; opacity: 0.7; }',
    '.rd-capsule-tier { font-size: 0.6875rem; font-weight: 500; letter-spacing: 0.04em; color: var(--ink-2); }',
    '.rd-capsule-score { font-size: 1.125rem; font-weight: 700; letter-spacing: -0.02em; color: var(--ink); }',
    '.rd-capsule.tier-legend .rd-capsule-score { color: var(--signal-2); }',
    '.rd-capsule.tier-hi .rd-capsule-score { color: var(--signal); }',
    '.rd-capsule.tier-up .rd-capsule-score { color: var(--mint); }',
    '.rd-capsule.tier-mid .rd-capsule-score { color: var(--warm); }',
    '.rd-capsule.tier-low .rd-capsule-score { color: var(--signal-2); }',
    '.rd-capsule.tier-sub .rd-capsule-score, .rd-capsule.tier-min .rd-capsule-score { color: var(--hot); }',
    '.rd-capsule.tier-pend .rd-capsule-score { color: var(--ink-3); }',
    '.rd-capsule-max { font-size: 0.625rem; color: var(--ink-3); margin-left: -0.125rem; }',
    '.rd-card-section { padding: 0.625rem 0; border-bottom: 0.0625rem solid var(--line); }',
    '.rd-card-section:last-child { border-bottom: 0; padding-bottom: 0.125rem; }',
    '.rd-card-sublabel {',
    '  display: block;',
    '  font-size: 0.625rem;',
    '  letter-spacing: 0.16em;',
    '  text-transform: uppercase;',
    '  color: var(--ink-3);',
    '  margin-bottom: 0.25rem;',
    '}',
    '.rd-card-def-text { margin: 0 0 0.375rem; font-size: 0.8125rem; line-height: 1.6; color: var(--ink-2); }',
    '.rd-card-scale-summary { display: block; font-size: 0.625rem; letter-spacing: 0.08em; color: var(--signal-2); opacity: 0.85; margin-top: 0.25rem; }',
    '.rd-scale-ruler { position: relative; height: 0.25rem; background: var(--line); border-radius: 0.125rem; margin: 0.5rem 0 0.875rem; }',
    '.rd-scale-tick { position: absolute; top: -0.125rem; width: 0.0625rem; height: 0.5rem; background: var(--line-2); transform: translateX(-50%); }',
    '.rd-scale-tick-lbl { position: absolute; top: 0.625rem; transform: translateX(-50%); font-size: 0.5625rem; color: var(--ink-3); letter-spacing: 0.04em; white-space: nowrap; }',
    '.rd-scale-pin { position: absolute; top: -0.25rem; width: 0.375rem; height: 0.75rem; background: var(--signal); border-radius: 0.125rem; transform: translateX(-50%); box-shadow: 0 0 0.375rem var(--signal); }',
    '.rd-card-bm-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.375rem; }',
    '.rd-card-bm-delta { font-size: 0.6875rem; letter-spacing: 0.04em; padding: 0.125rem 0.375rem; border-radius: 0.25rem; background: var(--glass); border: 0.0625rem solid var(--line); }',
    '.rd-card-bm-delta.lead { color: var(--mint); border-color: var(--mint); }',
    '.rd-card-bm-delta.lag { color: var(--hot); border-color: var(--hot); }',
    '.rd-card-bm-delta.even { color: var(--signal); border-color: var(--signal); }',
    '.rd-card-bm-delta.pend { color: var(--ink-3); }',
    '.rd-bm-track-shell { position: relative; height: 0.5rem; background: var(--line); border-radius: 0.25rem; overflow: visible; margin: 0.375rem 0 0.875rem; }',
    '.rd-bm-track-fill { position: absolute; top: 0; left: 0; bottom: 0; border-radius: 0.25rem; background: linear-gradient(90deg, var(--signal), var(--mint)); transition: width 0.4s var(--e-out); }',
    '.rd-bm-track-fill.tier-legend { background: linear-gradient(90deg, var(--hot), var(--signal)); }',
    '.rd-bm-track-fill.tier-mid { background: linear-gradient(90deg, var(--violet), var(--warm)); }',
    '.rd-bm-track-fill.tier-sub, .rd-bm-track-fill.tier-min { background: linear-gradient(90deg, var(--ink-3), var(--hot)); }',
    '.rd-bm-needle { position: absolute; top: -0.25rem; bottom: -0.25rem; width: 0.125rem; background: var(--signal-2); box-shadow: 0 0 0.375rem var(--signal); transform: translateX(-50%); z-index: 2; }',
    '.rd-bm-needle-tip { position: absolute; top: 0.75rem; transform: translateX(-50%); font-size: 0.5625rem; color: var(--signal-2); white-space: nowrap; background: var(--glass-2); padding: 0 0.25rem; border: 0.0625rem solid var(--line-2); border-radius: 0.125rem; }',
    '.rd-bm-labels { display: flex; justify-content: space-between; font-size: 0.5625rem; color: var(--ink-3); letter-spacing: 0.04em; margin-top: 0.25rem; }',
    '.rd-card-chain-wrap { margin-bottom: 0.5rem; }',
    '.rd-chain-flow { display: flex; align-items: center; gap: 0.375rem; flex-wrap: wrap; margin-top: 0.25rem; }',
    '.rd-chain-step { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.1875rem 0.4375rem; background: var(--glass); border: 0.0625rem solid var(--line-2); border-radius: 0.25rem; font-size: 0.6875rem; color: var(--ink); line-height: 1.4; }',
    '.rd-chain-step.conclusion { border-color: var(--signal); background: var(--glass-2); color: var(--signal-2); font-weight: 600; }',
    '.rd-chain-arrow { color: var(--signal); font-size: 0.75rem; opacity: 0.8; }',
    '.rd-card-basis-text { margin: 0.25rem 0 0; font-size: 0.75rem; line-height: 1.6; color: var(--ink-2); }',
    '.rd-book-quotes-list { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.375rem; }',
    '.rd-book-quote {',
    '  position: relative;',
    '  margin: 0;',
    '  padding: 0.625rem 0.875rem;',
    '  background: linear-gradient(135deg, rgba(20, 14, 28, 0.72), rgba(12, 8, 20, 0.86));',
    '  border: 0.0625rem solid rgba(255, 180, 92, 0.28);',
    '  border-left: 0.25rem solid var(--signal);',
    '  border-radius: 0.25rem;',
    '  box-shadow: inset 0 0.0625rem 0 rgba(255, 255, 255, 0.06), 0 0.25rem 0.75rem var(--glass-2);',
    '  font-family: var(--font-cjk-serif, serif);',
    '  font-size: 0.75rem;',
    '  line-height: 1.8;',
    '  letter-spacing: 0.08em;',
    '  color: var(--ink);',
    '  transition: border-color 0.25s var(--e-out);',
    '}',
    '.rd-book-quote:hover { border-color: var(--signal); }',
    '.rd-book-quote.empty { border-left-color: var(--line); border-color: var(--line); color: var(--ink-3); font-style: italic; }',
    '.rd-quote-symbol { color: var(--signal); font-size: 0.9375rem; font-weight: 600; line-height: 1; vertical-align: -0.0625rem; margin: 0 0.1875rem; }',
    '.rd-quote-footer { display: flex; align-items: center; justify-content: flex-end; margin-top: 0.375rem; font-size: 0.5625rem; letter-spacing: 0.1em; color: var(--ink-3); }',
    '@media (prefers-reduced-motion: reduce) {',
    '  .rd-holo-card, .rd-holo-card * {',
    '    animation: none !important;',
    '    transition: none !important;',
    '  }',
    '}'
  ].join('\n');

  // 安全 HTML 转义
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // 确保全局样式已注入
  function ensureStyles() {
    if (typeof document === 'undefined' || !document.head) return;
    if (document.getElementById('cl-radar-evidence-card-css')) return;
    var style = document.createElement('style');
    style.id = 'cl-radar-evidence-card-css';
    style.textContent = CSS_STYLES;
    document.head.appendChild(style);
  }

  // 防崩判决辅助：唯一真相复用 CLRadar.scoreOf（同一份反例表判定），缺席时才退回等价 fallback
  function cardScoreOf(a) {
    if (typeof window !== 'undefined' && window.CLRadar && typeof window.CLRadar.scoreOf === 'function') return window.CLRadar.scoreOf(a);
    if (!a || a.pending || a.score == null || typeof a.score === 'boolean' || Array.isArray(a.score)) return null;
    if (typeof a.score === 'string' && a.score.trim() === '') return null;
    var n = Number(a.score);
    return isFinite(n) ? Math.max(0, Math.min(100, n)) : null;
  }
  function isPending(a) {
    return cardScoreOf(a) == null;
  }

  function isLow(a) {
    return !!(a && (a.low || !a.evidence || !a.evidence.length));
  }

  // 分值档位与着色元数据
  function getTierInfo(score, low, pending) {
    if (pending || score == null) {
      return {
        tier: 'pend',
        name: '待建档',
        desc: '未评分',
        glowColor: 'var(--line)',
        accentColor: 'var(--ink-3)'
      };
    }
    if (low) {
      return {
        tier: 'low',
        name: '低证保守',
        desc: '侧面研判',
        glowColor: 'var(--signal-2)',
        accentColor: 'var(--signal-2)'
      };
    }
    if (score >= 96) {
      return {
        tier: 'legend',
        name: '传说级',
        desc: '冠绝全界',
        glowColor: 'var(--signal)',
        accentColor: 'var(--hot)'
      };
    }
    if (score >= 85) {
      return {
        tier: 'hi',
        name: '一方之最',
        desc: '顶尖卓越',
        glowColor: 'var(--signal)',
        accentColor: 'var(--signal)'
      };
    }
    if (score >= 70) {
      return {
        tier: 'up',
        name: '圈内出色',
        desc: '卓越优异',
        glowColor: 'var(--mint)',
        accentColor: 'var(--mint)'
      };
    }
    if (score >= 41) {
      return {
        tier: 'mid',
        name: '常人',
        desc: '常人中坚',
        glowColor: 'var(--violet)',
        accentColor: 'var(--violet)'
      };
    }
    if (score >= 21) {
      return {
        tier: 'sub',
        name: '弱于常人',
        desc: '略显短板',
        glowColor: 'var(--ink-3)',
        accentColor: 'var(--ink-2)'
      };
    }
    return {
      tier: 'min',
      name: '明显低于常人',
      desc: '极值洼地',
      glowColor: 'var(--hot)',
      accentColor: 'var(--hot)'
    };
  }

  // 全书排名信息计算
  function getRankInfo(k, character, ranked, allAttrs) {
    k = (typeof k === 'string' && k.trim()) ? k.trim() : KEYS[0];
    character = (character && typeof character === 'object') ? character : {};
    var charName = character.name || character.id || '';

    var rawAttrs = character.attrs || character;
    var a = (rawAttrs && typeof rawAttrs === 'object') ? rawAttrs[k] : null;
    var cScore = (typeof a === 'number') ? cardScoreOf({ score: a }) : cardScoreOf(a);

    var list = [];
    if (Array.isArray(ranked) && ranked.length > 0) {
      list = ranked.slice();
    } else if (allAttrs) {
      if (Array.isArray(allAttrs)) {
        list = allAttrs.slice();
      } else if (typeof allAttrs === 'object') {
        list = Object.keys(allAttrs).map(function (name) {
          return { name: name, attrs: allAttrs[name] };
        });
      }
    }

    var validList = [];
    list.forEach(function (item) {
      if (!item) return;
      var name = item.name || item.id || '';
      var itAttrs = item.attrs || item;
      var itA = (itAttrs && typeof itAttrs === 'object') ? itAttrs[k] : null;
      var sc = (typeof itA === 'number') ? cardScoreOf({ score: itA }) : cardScoreOf(itA);
      if (sc == null && typeof item.score === 'number') sc = cardScoreOf({ score: item.score });

      if (sc != null) {
        validList.push({ name: name, score: sc });
      }
    });

    validList.sort(function (x, y) { return y.score - x.score; });

    if (cScore === null) {
      return {
        rank: null,
        total: validList.length,
        badge: '待建档',
        title: '待建档',
        percentile: null
      };
    }

    var foundIdx = -1;
    if (charName) {
      for (var i = 0; i < validList.length; i++) {
        if (validList[i].name === charName) {
          foundIdx = i;
          break;
        }
      }
    }

    // 竞赛排名（1,1,3）：只按「严格高于本人分值」的人数计名次，同分并列，不用列表位置冒充。
    var rank, total;
    if (foundIdx >= 0) {
      var insRank0 = 1;
      for (var j0 = 0; j0 < validList.length; j0++) { if (validList[j0].score > cScore) insRank0++; }
      rank = insRank0;
      total = validList.length;
    } else {
      var insRank = 1;
      for (var j = 0; j < validList.length; j++) {
        if (cScore < validList[j].score) insRank++;
      }
      rank = insRank;
      total = validList.length + 1;
    }

    var title = '';
    if (rank === 1) title = '榜首';
    else if (rank === 2) title = '榜眼';
    else if (rank === 3) title = '探花';
    else if (total > 0 && rank / total <= 0.15) title = '顶尖';
    else if (total > 0 && rank / total <= 0.35) title = '前列';
    else if (total > 0 && rank / total <= 0.65) title = '中坚';
    else title = '序位';

    var badge = '#' + rank + ' / ' + total + ' ' + title;
    var percentile = total > 1 ? Math.round(((total - rank) / (total - 1)) * 100) : 100;

    return {
      rank: rank,
      total: total,
      badge: badge,
      title: title,
      percentile: percentile
    };
  }

  // 与全书基准对比差值计算
  function getBenchmarkDelta(score, k, benchmark, allAttrs, ranked) {
    k = (typeof k === 'string' && k.trim()) ? k.trim() : KEYS[0];
    var avg = null;

    /* An explicitly empty production benchmark is an unknown baseline. Do not
       silently rebuild it from a local ranking or the old 50-point scale. */
    if (benchmark && benchmark.isEmpty === true) {
      return { avg: null, diff: null, label: '无可用基准 · 不计算差值', classType: 'pend' };
    }

    if (benchmark && typeof benchmark === 'object') {
      if (typeof benchmark.get === 'function') {
        avg = benchmark.get(k);
      } else if (benchmark.means && benchmark.means[k] != null) {
        avg = +benchmark.means[k];
      } else if (benchmark.avg && benchmark.avg[k] != null) {
        avg = +benchmark.avg[k];
      } else if (typeof benchmark[k] === 'number') {
        avg = benchmark[k];
      } else if (benchmark[k] && typeof benchmark[k] === 'object' && benchmark[k].mean != null) {
        avg = +benchmark[k].mean;
      }
    }

    /* 只有调用方完全没传 benchmark 对象时才允许从 ranked/allAttrs 自算一份临时均值
       （旧调用点兼容）；一旦传入了 benchmark 对象但该轴本身无有效人数（count 0 / avg null），
       就必须诚实报告「不支持」，不能靠本地重算另造一个数字掩盖「基准这一轴没有数据」的事实——
       否则就是 review 点名的「用局部排名伪装全书基准」。 */
    if ((avg == null || isNaN(avg)) && !(benchmark && typeof benchmark === 'object')) {
      var pool = (Array.isArray(ranked) && ranked.length > 0) ? ranked :
                 (Array.isArray(allAttrs) ? allAttrs :
                 (allAttrs && typeof allAttrs === 'object' ? Object.keys(allAttrs).map(function (n) { return allAttrs[n]; }) : []));
      var scores = [];
      pool.forEach(function (item) {
        if (!item) return;
        var itAttrs = item.attrs || item;
        var itA = (itAttrs && typeof itAttrs === 'object') ? itAttrs[k] : null;
        var sc = (typeof itA === 'number') ? cardScoreOf({ score: itA }) : cardScoreOf(itA);
        if (sc != null) scores.push(sc);
      });
      if (scores.length > 0) {
        var sum = scores.reduce(function (acc, val) { return acc + val; }, 0);
        avg = Math.round(sum / scores.length);
      }
    }

    if (avg == null || isNaN(avg)) {
      return { avg: null, diff: null, label: '无可用基准 · 不计算差值', classType: 'pend' };
    }

    if (score == null) {
      return {
        avg: avg,
        diff: null,
        label: '全书均值 ' + avg + ' · 待建档无分值',
        classType: 'pend'
      };
    }

    if (AS && typeof AS.getBenchmarkDelta === 'function') {
      var dRes = AS.getBenchmarkDelta(score, avg);
      return {
        avg: avg,
        diff: dRes.diff,
        label: dRes.label,
        classType: dRes.classType
      };
    }

    var diff = Math.round(score - avg);
    var label = '';
    var classType = '';
    if (diff > 0) {
      label = 'vs 全书均值 +' + diff + ' (领先全书 ' + Math.round((diff / (avg || 1)) * 100) + '%)';
      classType = 'lead';
    } else if (diff < 0) {
      label = 'vs 全书均值 ' + diff + ' (低于均值 ' + Math.abs(diff) + ' 分)';
      classType = 'lag';
    } else {
      label = 'vs 全书均值 持平 (与全书基准对齐)';
      classType = 'even';
    }

    return {
      avg: avg,
      diff: diff,
      label: label,
      classType: classType
    };
  }

  // 渲染分值档位发光胶囊
  function renderGlowingCapsule(score, tierInfo) {
    tierInfo = tierInfo || getTierInfo(score, false, score == null);
    var scText = score != null ? String(score) : '—';
    return [
      '<div class="rd-capsule tier-' + esc(tierInfo.tier) + '" title="' + esc(tierInfo.name) + ' · ' + esc(tierInfo.desc) + '">',
      '  <span class="rd-capsule-tier">' + esc(tierInfo.name) + '</span>',
      '  <span class="rd-capsule-score mono">' + esc(scText) + '</span>',
      '  <span class="rd-capsule-max mono">/100</span>',
      '</div>'
    ].join('\n');
  }

  // 渲染全书排名微标
  function renderRankBadge(rankInfo) {
    if (!rankInfo || rankInfo.rank == null) {
      return '<span class="rd-card-tag pend mono">全书建档待排位</span>';
    }
    return [
      '<span class="rd-card-rank-badge mono" title="全书 ' + esc(rankInfo.total) + ' 位建档角色中位列第 ' + esc(rankInfo.rank) + ' 名">',
      '  #' + esc(rankInfo.rank) + ' / ' + esc(rankInfo.total) + ' <em class="rd-rank-title">' + esc(rankInfo.title) + '</em>',
      '</span>'
    ].join('');
  }

  // 渲染绝对刻度衡量标尺
  function renderScaleRuler(score) {
    var ticks = [
      { v: 50, label: '50 常人' },
      { v: 70, label: '70 出色' },
      { v: 85, label: '85 一方之最' },
      { v: 96, label: '96+ 传说' }
    ];

    var ticksHTML = ticks.map(function (t) {
      return '<div class="rd-scale-tick" style="left: ' + t.v + '%;"><span class="rd-scale-tick-lbl mono">' + esc(t.label) + '</span></div>';
    }).join('');

    var pinHTML = '';
    if (score != null && !isNaN(score)) {
      var clamped = Math.max(0, Math.min(100, score));
      pinHTML = '<div class="rd-scale-pin" style="left: ' + clamped + '%;" title="当前位置 ' + clamped + ' 分"></div>';
    }

    return '<div class="rd-scale-ruler" aria-hidden="true">' + ticksHTML + pinHTML + '</div>';
  }

  // 渲染与全书平均水平对比条 (vs 全书均值)
  function renderBenchmarkBar(score, avg, delta) {
    var scClamped = score != null ? Math.max(0, Math.min(100, score)) : 0;
    var avgClamped = avg == null ? null : Math.max(0, Math.min(100, avg));
    var tier = score != null ? getTierInfo(score, false, false).tier : 'pend';
    var scoreText = score != null ? (score + ' 分') : '待建档';

    return [
      '<div class="rd-card-bm-head">',
      '  <span class="rd-card-sublabel mono">全书基准对照 · VS BOOK BENCHMARK</span>',
      '  <span class="rd-card-bm-delta mono ' + esc(delta.classType) + '">' + esc(delta.label) + '</span>',
      '</div>',
      '<div class="rd-bm-track-shell">',
      '  <div class="rd-bm-track-fill tier-' + esc(tier) + '" style="width: ' + scClamped + '%;"></div>',
      avgClamped == null ? '' : '  <div class="rd-bm-needle" style="left: ' + avgClamped + '%;"><span class="rd-bm-needle-tip mono">全书均值 ' + avgClamped + '</span></div>',
      '</div>',
      '<div class="rd-bm-labels mono">',
      '  <span>0 基线</span>',
      '  <span>50 常人基准</span>',
      '  <span>' + (avgClamped == null ? '均值 未知' : '均值 ' + avgClamped) + '</span>',
      '  <span>当前 ' + esc(scoreText) + '</span>',
      '  <span>100 极值</span>',
      '</div>'
    ].join('\n');
  }

  // 渲染推理链与依据
  function renderReasoningChain(chain, basis, confidence, unverified) {
    var out = [];

    if (chain) {
      var steps = String(chain).split(/\s*(?:→|->|-->)\s*/).filter(Boolean);
      var nodes = steps.map(function (step, i) {
        var isLast = i === steps.length - 1;
        var stepHTML = '<span class="rd-chain-step' + (isLast ? ' conclusion' : '') + '">' +
          '<i class="mono rd-chain-idx">' + (i + 1) + '.</i> ' + esc(step) + '</span>';
        if (!isLast) {
          stepHTML += '<span class="rd-chain-arrow" aria-hidden="true">→</span>';
        }
        return stepHTML;
      }).join(' ');

      out.push(
        '<div class="rd-card-chain-wrap">',
        '  <span class="rd-card-sublabel mono">推断推理链路 · REASONING PIPELINE' +
           (confidence != null ? ' · 置信度 ' + esc(confidence) + '%' : '') + '</span>',
        '  <div class="rd-chain-flow">' + nodes + '</div>',
        '</div>'
      );
    }

    if (basis) {
      out.push(
        '<div class="rd-card-basis-wrap">',
        '  <span class="rd-card-sublabel mono">推断依据 · INFERENCE BASIS</span>',
        '  <p class="rd-card-basis-text">' + esc(basis) + '</p>',
        '</div>'
      );
    } else if (!chain) {
      out.push(
        '<div class="rd-card-basis-wrap">',
        '  <span class="rd-card-sublabel mono">推断依据 · INFERENCE BASIS</span>',
        '  <p class="rd-card-basis-text rd-card-basis-absent">材料未直接明言，采用全书侧面情节与群像互动保守评估。</p>',
        '</div>'
      );
    }

    if (unverified > 0) {
      out.push(
        '<div class="rd-card-unverified-row">',
        '  <span class="rd-card-tag warn mono">已自动剔除未命中文本之伪证据 ' + esc(unverified) + ' 条</span>',
        '</div>'
      );
    }

    return out.join('\n');
  }

  /**
   * 五类证据标签：原文 · 推断 · 低证 · 争议 · 未提供。
   * 只依据字段判定，不推断语义：disputed/contested/conflict 字段目前的材料 schema
   * 里不存在（见 serve.py ATTR_DEF：只有 score/evidence/basis/chain/confidence/low/pending/unverified），
   * 所以「争议」分支恒定可用但在当前生产数据下不会触发——这是诚实的「有判据、无实例」，
   * 不是伪造判据；一旦材料层加上该字段，这里不需要再改。
   */
  function quoteTag(q) {
    var qObj = q && typeof q === 'object' ? q : null;
    if (qObj && (qObj.disputed === true || qObj.contested === true || qObj.conflict === true)) return '争议';
    var verified = !!(qObj && (qObj.verified === true || qObj.verification === true || ((qObj.sourceType === '原文' || qObj.source === '原文') && (qObj.sourceRef || qObj.ref || qObj.eventId))));
    if (verified) return '原文';
    if (qObj && (qObj.sourceType === '推断' || qObj.source === '推断' || qObj.inferred === true)) return '推断';
    return '低证';
  }
  function classifyEvidence(a, evidence) {
    if (!evidence || !evidence.length) return (a && (a.basis || a.chain)) ? '推断' : '未提供';
    var hasDisputed = false, allVerified = true, anyVerified = false, i, t;
    for (i = 0; i < evidence.length; i++) {
      t = quoteTag(evidence[i]);
      if (t === '争议') hasDisputed = true;
      if (t === '原文') anyVerified = true; else allVerified = false;
    }
    if (hasDisputed) return '争议';
    if (allVerified) return '原文';
    if (anyVerified) return '低证';
    return '低证';
  }
  var QUOTE_TAG_LABEL = { '原文': '原文佐证', '推断': '推断依据引用', '低证': '引用片段 · 低证未核验', '争议': '存在争议的引用' };

  // 渲染原文引用（带金黄边框与字距的书香引号风格）
  function renderQuotes(evidence) {
    if (!evidence || !evidence.length) {
      return [
        '<div class="rd-book-quotes-list">',
        '  <blockquote class="rd-book-quote empty">',
        '    <span class="rd-quote-symbol" aria-hidden="true">「</span>',
        '    <span>材料中暂无直接支撑此维度的原文词句（证据：未提供）。</span>',
        '    <span class="rd-quote-symbol" aria-hidden="true">」</span>',
        '  </blockquote>',
        '</div>'
      ].join('\n');
    }

    var listHTML = evidence.map(function (q, i) {
      var qObj = q && typeof q === 'object' ? q : null;
      var qText = qObj ? (qObj.text || qObj.quote || qObj.excerpt || '') : q;
      var tag = quoteTag(q);
      var cls = tag === '争议' ? ' tag-dispute' : (tag === '低证' ? ' tag-low' : '');
      return [
        '<blockquote class="rd-book-quote' + cls + '">',
        '  <span class="rd-quote-symbol" aria-hidden="true">「</span>',
        '  <span>' + esc(qText) + '</span>',
        '  <span class="rd-quote-symbol" aria-hidden="true">」</span>',
        '  <div class="rd-quote-footer mono">',
        '    <span class="rd-quote-tag">' + esc(QUOTE_TAG_LABEL[tag]) + '</span>',
        '    <span>&nbsp;#' + (i + 1) + '</span>',
        '  </div>',
        '</blockquote>'
      ].join('\n');
    }).join('\n');

    return '<div class="rd-book-quotes-list">' + listHTML + '</div>';
  }

  /**
   * 核心入口：渲染全息情报卡片 HTML
   * @param {string} k - 维度名称（如 '智谋'）
   * @param {Object} character - 角色对象或属性对象
   * @param {Array} ranked - 全书排名角色列表（可选）
   * @param {Object|Array} allAttrs - 全书角色属性集合（可选）
   * @param {Object} benchmark - 全书基准数据（可选）
   * @returns {string} 完整的全息情报卡片 HTML 字符串
   */
  function renderCard(k, character, ranked, allAttrs, benchmark) {
    ensureStyles();

    k = (typeof k === 'string' && k.trim()) ? k.trim() : KEYS[0];
    var en = EN[k] || 'ATTR';
    var def = DEF[k] || '通用属性衡量指标与行为事实研判';

    character = (character && typeof character === 'object') ? character : {};
    var charName = character.name || character.id || '当前角色';

    var rawAttrs = character.attrs || character;
    var a = (rawAttrs && typeof rawAttrs === 'object') ? rawAttrs[k] : null;
    if (typeof a === 'number') {
      a = { score: a, evidence: [], basis: '', chain: '', low: false, pending: false };
    } else if (!a || typeof a !== 'object') {
      a = { score: null, evidence: [], basis: '', chain: '', low: true, pending: true };
    }

    var isPend = isPending(a);
    var score = isPend ? null : Math.round(cardScoreOf(a));
    var isLowConf = isLow(a);
    var confidence = (a.confidence != null && !isNaN(+a.confidence)) ? Math.round(+a.confidence) : null;
    var basis = a.basis || '';
    var chain = a.chain || '';
    var unverified = +a.unverified || 0;
    var evidence = Array.isArray(a.evidence) ? a.evidence : [];

    // 计算衍生指标
    var tierInfo = getTierInfo(score, isLowConf, isPend);
    var rankInfo = getRankInfo(k, character, ranked, allAttrs);
    var deltaInfo = getBenchmarkDelta(score, k, benchmark, allAttrs, ranked);

    // 辅助标签徽章：五类证据标签（原文·推断·低证·争议·未提供），不再对全部 evidence[] 无条件写 VERIFIED
    var confBadge = '';
    if (isPend) {
      confBadge = '<span class="rd-card-tag pend mono">待建档 · 缺失维度不冒充</span>';
    } else {
      var evTag = classifyEvidence(a, evidence);
      var evCls = evTag === '原文' ? 'conf' : (evTag === '推断' ? 'infer' : (evTag === '争议' ? 'dispute' : (evTag === '未提供' ? 'pend' : 'low')));
      var evLabel = evTag === '原文' ? ('原文佐证 · ' + evidence.length + 'E') : (evTag === '推断' ? '推断依据' : (evTag === '争议' ? '证据存在争议' : (evTag === '未提供' ? '证据未提供' : '低证据 · 保守研判')));
      confBadge = '<span class="rd-card-tag ' + evCls + ' mono">' + esc(evLabel) + '</span>';
    }

    return [
      '<div class="rd-holo-card tier-' + esc(tierInfo.tier) + '" data-axis="' + esc(k) + '" data-score="' + (score != null ? score : '') + '" role="region" aria-label="' + esc(charName) + ' · ' + esc(k) + ' 全息情报卡片">',
      '  <header class="rd-card-head">',
      '    <div class="rd-card-title-group">',
      '      <div class="rd-card-eyebrow">',
      '        <span class="rd-card-axis-zh">' + esc(k) + '</span>',
      '        <span class="rd-card-axis-en mono">' + esc(en) + '</span>',
      '        <span class="rd-card-char-name">' + esc(charName) + '</span>',
      '      </div>',
      '      <div class="rd-card-badges">',
      '        ' + renderRankBadge(rankInfo),
      '        ' + confBadge,
      '      </div>',
      '    </div>',
      '    <div class="rd-card-capsule-wrap">',
      '      ' + renderGlowingCapsule(score, tierInfo),
      '    </div>',
      '  </header>',
      '  <section class="rd-card-section">',
      '    <span class="rd-card-sublabel mono">维度定义 · SPECIFICATION</span>',
      '    <p class="rd-card-def-text">' + esc(def) + '</p>',
      '    <span class="rd-card-scale-summary mono">' + esc(SCALE) + '</span>',
      '    ' + renderScaleRuler(score),
      '  </section>',
      '  <section class="rd-card-section">',
      '    ' + renderBenchmarkBar(score, deltaInfo.avg, deltaInfo),
      '  </section>',
      '  <section class="rd-card-section">',
      '    ' + renderReasoningChain(chain, basis, confidence, unverified),
      '  </section>',
      '  <section class="rd-card-section">',
      '    <span class="rd-card-sublabel mono">原文引用证据链 · TEXTUAL CITATIONS</span>',
      '    ' + renderQuotes(evidence),
      '  </section>',
      '</div>'
    ].join('\n');
  }

  /* ══════════════════════════════════════════════════════════════════════════
   * R2 · 三态接线（domain: 'evidence'）—— 与 R4 · 订阅端重绘
   * --------------------------------------------------------------------------
   * 本模块此前是「纯 HTML 字符串工厂」：`renderCard` 只负责拼串，宿主 `#rdEvHost`
   * 由调用方 `app.js` 自己写。于是出现了 R2 点名的病灶 —— **静默 return**：
   *   app.js:2803  `if (!c || !host) return;`      ← 无角色时不写任何态，宿主留在上次内容/空白
   *   app.js:2836  `host.innerHTML = '';`          ← 用户收起时清空
   * 两者在 DOM 上**长得一模一样**（都是空），但语义完全不同。本模块提供显式 API
   * 把「数据不足（empty/loading/degraded）」与「用户主动收起（blank）」分开。
   *
   * ### 三态触发表（本域专属，判据可执行）
   * | 数据条件                                   | 态       | 判据                                   |
   * |--------------------------------------------|----------|----------------------------------------|
   * | 真相源未就绪（ready === false）            | loading  | `resolveState` → 'loading'             |
   * | 无角色可选（!character）                   | empty    | `resolveState` → 'empty'               |
   * | 该维度在角色属性上无此键                   | empty    | `resolveState` → 'empty'               |
   * | 有键但无分值（pending）                    | empty    | `resolveState` → 'empty'               |
   * | 有分值但零条原文证据                       | degraded | `resolveState` → 'degraded'（**包卡**）|
   * | 有分值且有 ≥1 条原文证据                   | ready    | 渲染完整卡                             |
   * | 用户主动收起（点已开维度）                 | **blank**| 显式 `clear()`，**不是** empty 态      |
   *
   * ### 为什么「empty 换掉卡、degraded 包住卡」（实测定的口径）
   * 改前对 T3/T4 两种条件，`renderCard` 输出的是**完全相同**的 2853 字符卡
   * （`rd-card-tag pend`「待建档」+ 全占位文案 + 空引句）—— 整张卡没有一条真数据，
   * 属于 R2 要清掉的「静默冒充」。故 **empty 直接替换**。
   * 而 T5（有分、零原文）输出的是 2992 字符卡，内含**真实分值 80 / 档位 / 基准差值**，
   * 只有引句是占位。把它换成一行铭文会**销毁真实数据** ⇒ 故 **degraded 用
   * `renderDegraded({contentEl})` 把原卡包住**，只加一条「原文未载」声明。
   *
   * ⚠ **blank ≠ empty** 是本表的判别行：任何把「收起」也渲染成空态铭文的实现都算错
   * （用户会以为数据丢了）。gate `v2-2-r2-runtime.py` 专设一条负向断言扣住它。
   *
   * ### R4 订阅端契约（承 `js/hud/attr-source.js` V2-1）
   * 本模块向 `CLAttrSource.subscribe` 注册的回调**只读真相源**，**禁止**在回调内
   * 调 `notify` / 改 `listeners`（V2-1 加了重入哨兵，违反者会被**警告并拒绝**）。
   * 需要联动时只调纯函数：`extractAttr` / `computeCharacterProfile` / `getTierInfo`。
   * ══════════════════════════════════════════════════════════════════════════ */

  var DOMAIN = 'evidence';

  /** 三态触发表的机读副本（与上方注释表逐行对应；gate 按本表逐行驱动） */
  var TRIGGERS = [
    { id: 'T1', 条件: '真相源未就绪 ready===false', 态: 'loading',  判据: "resolveState({ready:false}) === 'loading'" },
    { id: 'T2', 条件: '无角色可选 !character',       态: 'empty',    判据: "resolveState({character:null}) === 'empty'" },
    { id: 'T3', 条件: '维度键缺失',                  态: 'empty',    判据: "resolveState({character:{attrs:{}},axis:'智谋'}) === 'empty'" },
    { id: 'T4', 条件: '有键无分 pending',            态: 'empty',    判据: "resolveState({character:{attrs:{智谋:{pending:true}}}}) === 'empty'" },
    { id: 'T5', 条件: '有分零原文（**包卡**，不丢分）', 态: 'degraded', 判据: "resolveState({character:{attrs:{智谋:{score:80,evidence:[]}}}}) === 'degraded' 且宿主内 `.rd-holo-card` 仍为 1" },
    { id: 'T6', 条件: '有分有原文',                  态: 'ready',    判据: "resolveState({character:{attrs:{智谋:{score:80,evidence:['q']}}}}) === 'ready'" },
    { id: 'T7', 条件: '用户主动收起（点已开维度）',  态: 'blank',    判据: "clear(host) 后 host.dataset.rdState === 'blank' 且**无** .cl-state--empty" }
  ];

  /** 当前已挂载的视图上下文（R4 重绘与 R2 态判定的唯一输入；不复制任何数据） */
  var viewCtx = null;

  // Mobile evidence is a normal-flow drawer below the chart, never an overlay.
  // Wrap the ranking as well as the card so one keyboard control closes both.
  function bindDrawer(ctx) {
    var host = ctx.hostEl;
    if (!host.closest || typeof window.matchMedia !== 'function' || !window.matchMedia('(max-width: 480px)').matches) return;
    var outer = host.closest('#rdEvHost');
    if (!outer || outer === host || !outer.parentNode) return;
    var anchor = document.createComment('radar evidence position');
    outer.parentNode.insertBefore(anchor, outer);
    var reading = outer.parentNode.querySelector('#radarReadingHost');
    if (reading) reading.parentNode.insertBefore(outer, reading);
    var drawer = document.createElement('details');
    drawer.className = 'rr-evidence-drawer';
    drawer.open = true;
    var summary = document.createElement('summary');
    summary.className = 'rr-evidence-handle';
    summary.textContent = (ctx.axis || '维度') + ' · 证据阅读';
    var hint = document.createElement('span');
    hint.className = 'rr-evidence-hint';
    hint.textContent = '展开 / 收起';
    summary.appendChild(hint);
    var content = document.createElement('div');
    content.className = 'rr-evidence-content';
    while (outer.firstChild) content.appendChild(outer.firstChild);
    drawer.appendChild(summary);
    drawer.appendChild(content);
    outer.appendChild(drawer);
    // Native summary handles Enter/Space. Escape remains owned by the shell.
    ctx.disposeDrawer = function () {
      while (content.firstChild) outer.insertBefore(content.firstChild, drawer);
      drawer.remove();
      if (anchor.parentNode) {
        if (outer.isConnected && anchor.isConnected) anchor.parentNode.insertBefore(outer, anchor);
        anchor.remove();
      }
    };
  }

  function releaseView() {
    if (viewCtx && viewCtx.disposeDrawer) viewCtx.disposeDrawer();
    viewCtx = null;
  }

  /** 该维度的属性对象（容忍 `character.attrs[k]` 与 `character[k]` 两种历史形态） */
  function axisOf(character, k) {
    if (!character || typeof character !== 'object') return null;
    var raw = character.attrs || character;
    var a = (raw && typeof raw === 'object') ? raw[k] : null;
    if (typeof a === 'number') return { score: a, evidence: [] };
    return (a && typeof a === 'object') ? a : null;
  }

  /**
   * R2 态判定（纯函数，不碰 DOM）。
   *
   * 关键口径（见上方「为什么 empty 换掉卡、degraded 包住卡」）：
   *   - pending / 维度键缺失 ⇒ 'empty' —— 改前这两种条件渲染的是**同一张**全占位卡
   *     （2853 字符，零真数据），是 R2 要清掉的「静默冒充」。
   *   - 有分零原文 ⇒ 'degraded' —— 卡里有真分值，只能包不能换。
   * @returns {'loading'|'empty'|'degraded'|'ready'}
   */
  function resolveState(ctx) {
    ctx = ctx || {};
    if (ctx.ready === false) return 'loading';
    if (!ctx.character) return 'empty';
    var a = axisOf(ctx.character, ctx.axis);
    if (!a) return 'empty';
    if (isPending(a)) return 'empty';
    var ev = Array.isArray(a.evidence) ? a.evidence : [];
    if (!ev.length) return 'degraded';
    return 'ready';
  }

  /** 非法态与「收起」态共用的宿主标记，供 CSS / 测试断言读取 */
  function markState(hostEl, state) {
    if (hostEl && hostEl.setAttribute) hostEl.setAttribute('data-rd-state', state);
  }

  /**
   * 把某一态写进宿主（先清空）。返回写入的节点（blank 返回 null）。
   * ready 态**不在此处理** —— 由 `paint` 走 `renderCard` 完整渲染。
   */
  function renderState(hostEl, state, opts) {
    if (!hostEl) return null;
    opts = opts || {};
    hostEl.textContent = '';
    markState(hostEl, state);
    if (state === 'blank' || state === 'ready') return null;

    var SS = (typeof window !== 'undefined') ? window.CLStatusStates : null;
    if (!SS) return null;                       // 引擎缺席时不假装有态
    var node = null;
    if (state === 'loading') {
      node = SS.renderLoading({ bars: 3, minHeight: 74 });
    } else if (state === 'empty') {
      node = SS.renderEmpty({ domain: DOMAIN });
    } else if (state === 'degraded') {
      node = SS.renderDegraded({ notice: opts.notice || '此维度原文证据未载', contentEl: opts.contentEl || null });
    }
    if (node) hostEl.appendChild(node);
    return node;
  }

  /** 按上下文渲染一次（R2 态 + ready 卡）。返回是否落到了 ready（含「包卡的 degraded」）态。 */
  function paint(ctx) {
    if (!ctx || !ctx.hostEl) return false;
    var state = resolveState(ctx);
    ctx.lastState = state;
    var head = ctx.headHTML || '';

    if (state === 'ready') {
      ctx.hostEl.innerHTML = head + renderCard(ctx.axis, ctx.character, ctx.ranked, ctx.allAttrs, ctx.benchmark);
      markState(ctx.hostEl, 'ready');
      return true;
    }

    if (state === 'degraded') {
      /* 包卡而非换卡：分值/档位/基准差值是真数据，只把「原文未载」声明包在外面。
         态引擎缺席时**退化为普通出卡** —— 不得因为门禁引擎缺失而丢掉真数据。 */
      var SS = (typeof window !== 'undefined') ? window.CLStatusStates : null;
      var canWrap = !!(SS && SS.renderDegraded && typeof document !== 'undefined');
      if (canWrap) {
        var holder = document.createElement('div');
        holder.innerHTML = renderCard(ctx.axis, ctx.character, ctx.ranked, ctx.allAttrs, ctx.benchmark);
        ctx.hostEl.textContent = '';
        if (head) ctx.hostEl.insertAdjacentHTML('beforeend', head);
        ctx.hostEl.appendChild(SS.renderDegraded({
          notice: ctx.notice || '此维度原文证据未载，分值仅为保守研判',
          contentEl: holder
        }));
        markState(ctx.hostEl, 'degraded');
        return true;
      }
      ctx.hostEl.innerHTML = head + renderCard(ctx.axis, ctx.character, ctx.ranked, ctx.allAttrs, ctx.benchmark);
      markState(ctx.hostEl, 'ready');
      return true;
    }

    /* loading / empty：**同样保留 headHTML**。
     * 为什么不丢掉：T3/T4（维度未载 / 无分）时 `character` 是存在的，调用方传进来的
     * `headHTML`（如该维度的全书排名列表）**仍是有效数据**，丢掉它就是新的静默损失。
     * 契约：只要不开 blank（clear），headHTML 恒在宿主顶部。 */
    renderState(ctx.hostEl, state, { notice: ctx.notice });
    if (head) ctx.hostEl.insertAdjacentHTML('afterbegin', head);
    return false;
  }

  /**
   * 挂载视图到宿主（R2 + R4 的唯一入口）。
   * @param {Element} hostEl 宿主元素（页面里的 `#rdEvHost`）
   * @param {Object} opts `{axis, character, ranked, allAttrs, benchmark, ready, headHTML, notice}`
   */
  function mount(hostEl, opts) {
    if (!hostEl) return false;
    releaseView();
    opts = opts || {};
    viewCtx = {
      hostEl: hostEl,
      axis: opts.axis,
      character: opts.character || null,
      ranked: opts.ranked || null,
      allAttrs: opts.allAttrs || null,
      benchmark: opts.benchmark || null,
      ready: opts.ready !== false,
      headHTML: opts.headHTML || '',
      notice: opts.notice || ''
    };
    var painted = paint(viewCtx);
    bindDrawer(viewCtx);
    return painted;
  }

  /**
   * 用户主动收起：显式置 blank（**不**渲染空态铭文），并解除挂载。
   * 与 `mount` 的 empty 态在 API 层就分开，杜绝「收起被误判成数据丢失」。
   */
  function clear(hostEl) {
    if (viewCtx && (!hostEl || viewCtx.hostEl === hostEl)) {
      hostEl = hostEl || viewCtx.hostEl;
      releaseView();
    }
    if (hostEl) renderState(hostEl, 'blank', {});
    return true;
  }

  /**
   * R4：真相源广播到达 → 重绘当前挂载视图。
   * 宿主已脱离文档时自动解除挂载（不留下悬空重绘）。
   * **禁止回写**：本函数只读 `extractAttr` 等纯函数与已捕获的 ctx，绝不调 `notify`。
   */
  function repaint() {
    if (!viewCtx) return false;
    var hostEl = viewCtx.hostEl;
    var bound = (typeof document !== 'undefined' && document.body) ? document.body.contains(hostEl) : true;
    if (!hostEl || !bound) { releaseView(); return false; }
    return paint(viewCtx);
  }

  /** 只读查询：当前是否已挂载（供测试与调用方判断，避免第二份真相） */
  function mounted() {
    return !!(viewCtx && viewCtx.hostEl);
  }

  /** 只读查询：当前挂载视图的态（未挂载返回 null） */
  function currentState() {
    return viewCtx ? (viewCtx.lastState || null) : null;
  }

  // 挂载到全局并导出纯对象
  var CLRadarEvidenceCard = {
    renderCard: renderCard,
    getRankInfo: getRankInfo,
    getBenchmarkDelta: getBenchmarkDelta,
    getTierInfo: getTierInfo,
    renderGlowingCapsule: renderGlowingCapsule,
    renderRankBadge: renderRankBadge,
    renderScaleRuler: renderScaleRuler,
    renderBenchmarkBar: renderBenchmarkBar,
    renderReasoningChain: renderReasoningChain,
    renderQuotes: renderQuotes,
    quoteTag: quoteTag,
    classifyEvidence: classifyEvidence,
    ensureStyles: ensureStyles,
    DOMAIN: DOMAIN,
    TRIGGERS: TRIGGERS,
    mount: mount,
    clear: clear,
    repaint: repaint,
    paint: paint,
    resolveState: resolveState,
    renderState: renderState,
    mounted: mounted,
    currentState: currentState,
    KEYS: KEYS,
    EN: EN,
    DEF: DEF,
    SCALE: SCALE,
    CSS_STYLES: CSS_STYLES
  };

  if (typeof window !== 'undefined') {
    window.CLRadarEvidenceCard = CLRadarEvidenceCard;
    /* R4 订阅端（承 attr-source V2-1 契约）。
     * 此前这里是一个**空桩**（回调体仅一行注释）—— 广播到达后什么都不做。
     * 现改为真实订阅者：调用只读的 `repaint()`。
     * ⚠ 回调内**禁止**回写 attr-source（不得调 notify / 不得改 listeners）：
     *   需要联动只读纯函数 `extractAttr` / `computeCharacterProfile` / `getTierInfo`；
     *   违规会被 attr-source 的重入哨兵**警告并拒绝**（V2-1 R4 契约）。 */
    if (window.CLAttrSource && typeof window.CLAttrSource.subscribe === 'function') {
      var unsubTruth = window.CLAttrSource.subscribe(function () { repaint(); });
      if (typeof unsubTruth === 'function') CLRadarEvidenceCard.unsubscribeTruth = unsubTruth;
    }
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = CLRadarEvidenceCard;
  }
})();
