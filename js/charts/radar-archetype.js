/**
 * Castline · radar-archetype.js — 属性特征原型与极差谱系解析器
 * 
 * 职责：
 * 1. resolveArchetype(attrs): 依据八维分值分布自动判定角色核心原型与最高双维协同
 * 2. getBalanceMetrics(attrs): 量化八维极差 (range)、方差 (variance) 与均衡度指数 (balanceScore)
 * 3. 全防御性入参校验：对 null、undefined、空对象、全待建档等异常数据安全降级
 * 
 * 共享约定：
 * KEYS: ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义']
 * EN: { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' }
 * 主题色谱：黑曜石 #07060d，薄荷 #7af0c8，太阳琥珀 #ffb45c，虚空紫 #a688ff，绯红 #ff5c7c
 * 
 * 最小使用示例 / Minimal Usage Example:
 * -------------------------------------------------------------------------
 * // 1. 解析角色属性原型与最高双维协同
 * const archetype = window.CLRadarArchetype.resolveArchetype(character.attrs);
 * console.log(archetype.name);     // e.g. "深谋策士", "霸绝战将", "悲悯行者", "破阵狂澜", "全维均衡"
 * console.log(archetype.tagline);  // e.g. "帷幄定局，运筹乾坤；落子无声，翻覆间风云皆入彀中。"
 * console.log(archetype.color);    // e.g. "#7af0c8" (主题色十六进制)
 * console.log(archetype.token);    // e.g. "var(--mint, #7af0c8)" (CSS 语义令牌)
 * console.log(archetype.topPair);  // e.g. { primary: '智谋', secondary: '权势', label: '智谋 × 权势', synergy: '...' }
 * 
 * // 2. 计算八维极差谱系与均衡度指标
 * const metrics = window.CLRadarArchetype.getBalanceMetrics(character.attrs);
 * console.log(metrics.range);        // e.g. 25 (最高分 - 最低分，极差)
 * console.log(metrics.variance);     // e.g. 68.75 (方差 / 散度)
 * console.log(metrics.balanceScore); // e.g. 79 (0..100，各维越均匀得分越高)
 * 
 * // 3. 空数据 / 全待建档安全防御回退
 * const fallback = window.CLRadarArchetype.resolveArchetype(null);
 * console.log(fallback.isPending);  // true
 * console.log(fallback.name);       // "待建档"
 * console.log(fallback.topPair);    // null
 * -------------------------------------------------------------------------
 */

(function (root, factory) {
  if (typeof exports === 'object' && typeof module !== 'undefined') {
    module.exports = factory();
  } else if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else {
    var mod = factory();
    root.CLRadarArchetype = mod;
    if (typeof window !== 'undefined') {
      window.CLRadarArchetype = mod;
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  // 八维标准键名
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];

  // 英文代号映射
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

  // 英文反查中文映射（防防御性入参支持）
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

  // Castline 语义视觉主题色谱
  var THEME_COLORS = {
    mint: { hex: '#7af0c8', token: 'var(--mint, #7af0c8)', varName: '--mint', label: '核心薄荷翠' },
    signal: { hex: '#ffb45c', token: 'var(--signal, #ffb45c)', varName: '--signal', label: '太阳琥珀' },
    violet: { hex: '#a688ff', token: 'var(--violet, #a688ff)', varName: '--violet', label: '虚空秘紫' },
    hot: { hex: '#ff5c7c', token: 'var(--hot, #ff5d73)', varName: '--hot', label: '炽烈绯红' },
    obsidian: { hex: '#07060d', token: 'var(--bg, #05050b)', varName: '--bg', label: '黑曜石底色' },
    muted: { hex: '#7d7696', token: 'var(--ink-3, #88819d)', varName: '--ink-3', label: '沉寂墨灰' }
  };

  // 安全未建档原型对象模板
  var UNPROFILED = {
    id: 'unprofiled',
    name: '待建档',
    en: 'UNPROFILED',
    tagline: '卷宗空白，星轨未定；暂无足以定性的八维观测数据。',
    color: THEME_COLORS.muted.hex,
    token: THEME_COLORS.muted.token,
    theme: 'muted',
    cssVar: THEME_COLORS.muted.varName,
    description: '该角色尚未录入足够多维度的定性证据，属性矩阵处于待校准状态。',
    topPair: null,
    metrics: {
      range: 0,
      variance: 0,
      balanceScore: 0,
      mean: 0,
      stdDev: 0,
      min: 0,
      max: 0,
      scoredCount: 0,
      pending: true
    },
    isPending: true
  };

  // 28 组八维双核协同矩阵及原型谱系
  var TOP_PAIRS = {
    // 智谋系
    '智谋_实力': {
      name: '文武经纬',
      tagline: '文能提笔安天下，武能策马定乾坤；算计与锋刃并重。',
      synergy: '布局深远兼具强悍执行力，计出必行，行之必克。',
      theme: 'signal'
    },
    '智谋_意志': {
      name: '潜行策魂',
      tagline: '耐得极寒，算尽枯荣；经年隐忍只待一击必杀。',
      synergy: '如冰山下之暗流，以万古不移之韧性守护终极谋篇。',
      theme: 'violet'
    },
    '智谋_魅力': {
      name: '经世辩杰',
      tagline: '辩才无碍，智光灼然；以如簧之舌与超卓眼界折服四方。',
      synergy: '洞察人心幽微，言语兼具逻辑机锋与煽动威能。',
      theme: 'signal'
    },
    '智谋_情感': {
      name: '深情哲思',
      tagline: '情丝深重，慧眼穿石；在炽烈共情中洞悉人间终局。',
      synergy: '以敏锐情感感知苍生苦乐，以冷静智算推演解题之道。',
      theme: 'mint'
    },
    '智谋_野心': {
      name: '纵横枭谋',
      tagline: '胸罗万象，志吞山海；以无双算度构筑通天之梯。',
      synergy: '智计与欲望交织，长线落子步步为营，凡所谋求势必达成。',
      theme: 'violet'
    },
    '智谋_权势': {
      name: '深谋策士',
      tagline: '帷幄定局，运筹乾坤；落子无声，翻覆间风云皆入彀中。',
      synergy: '智计通神，手握重器；谋定后动，权倾一方。',
      theme: 'mint'
    },
    '智谋_道义': {
      name: '明德哲人',
      tagline: '格物明理，怀德致远；融博大智慧于清澈道义之中。',
      synergy: '智慧用于守护本心与公理，思虑通达而不堕深渊。',
      theme: 'mint'
    },

    // 实力系
    '实力_意志': {
      name: '霸绝战将',
      tagline: '横刀断水，气吞山河；千军辟易处，唯以硬实力破万法。',
      synergy: '百炼成钢，横推八极；武道硬实力与不可摧折之韧性相融贯通。',
      theme: 'hot'
    },
    '实力_魅力': {
      name: '盖世英豪',
      tagline: '力拔山兮气盖世，豪情动地万夫从；天生武宗领袖风范。',
      synergy: '绝对武勇引发追随狂潮，威名赫赫令敌胆寒、令友信服。',
      theme: 'signal'
    },
    '实力_情感': {
      name: '护道战狂',
      tagline: '拳握山河，心系一人；唯有挚爱牵绊能点燃焚天狂怒。',
      synergy: '炽烈情感化为无可遏止的力量源泉，因守护而所向披靡。',
      theme: 'hot'
    },
    '实力_野心': {
      name: '破阵狂澜',
      tagline: '狂澜既起，破阵摧坚；烈意奔涌处，万钧难当。',
      synergy: '锋芒裂阵，图谋浩瀚；以绝顶战力开疆拓土，欲壑所向无坚不摧。',
      theme: 'hot'
    },
    '实力_权势': {
      name: '铁腕霸主',
      tagline: '重兵在握，威加海内；实权与强横战力合二为一。',
      synergy: '以实战硬实力奠定政治根基，以铁血军权慑服四海。',
      theme: 'hot'
    },
    '实力_道义': {
      name: '仗剑侠尊',
      tagline: '侠之大者，以武卫道；仗剑斩尽天下不平事。',
      synergy: '绝顶战力恪守道义底线，行侠仗义，虽千万人吾往矣。',
      theme: 'mint'
    },

    // 意志系
    '意志_魅力': {
      name: '风骨行者',
      tagline: '傲骨铮铮，虽折不挠；以高洁气节感召天下同道。',
      synergy: '不可征服的坚韧心性凝聚为崇高人格魅力，四方景附。',
      theme: 'signal'
    },
    '意志_情感': {
      name: '执念守护',
      tagline: '情深不悔，志逾金石；为心中挚念甘受万劫千难。',
      synergy: '情感是唯一灯塔，意志是破浪长桨，任风暴摧残绝不回头。',
      theme: 'violet'
    },
    '意志_野心': {
      name: '宿命狂徒',
      tagline: '身负逆鳞，狂蹈死生；纵是万劫不复，亦要撞碎宿命桎梏。',
      synergy: '执念入骨，逆命狂歌；以不屈铁石意志托举滔天野心。',
      theme: 'violet'
    },
    '意志_权势': {
      name: '定鼎重臣',
      tagline: '砥柱中流，权柄在握；狂风骤雨中稳固社稷江山。',
      synergy: '身居高位而心性坚忍，临危受命力挽狂澜。',
      theme: 'signal'
    },
    '意志_道义': {
      name: '孤忠铁壁',
      tagline: '千磨万击，守死不移；狂澜既倒之际独撑天地脊梁。',
      synergy: '至高原则与铁石意志融为一体，舍生取义，誓不退让。',
      theme: 'mint'
    },

    // 魅力系
    '魅力_情感': {
      name: '倾世明珠',
      tagline: '情动四方，绝代风华；令万千生灵为之共鸣与驻足。',
      synergy: '真挚浓烈的情感赋魅于一颦一笑，具颠倒众生之感召力。',
      theme: 'signal'
    },
    '魅力_野心': {
      name: '煽惑枭杰',
      tagline: '欲壑吞天，言动天下；以天生魅力编织狂热幻梦引万人奔赴。',
      synergy: '野心隐于耀眼光环之下，极富鼓动性与号召力。',
      theme: 'violet'
    },
    '魅力_权势': {
      name: '天命领袖',
      tagline: '人望归心，坐断东南；超凡声望与实权统治无缝融合。',
      synergy: '权势放大个人威仪，魅力巩固统御根基，天生位居人上。',
      theme: 'signal'
    },
    '魅力_道义': {
      name: '德望贤者',
      tagline: '大德载物，四方景从；以温润仁德感化人间戾气。',
      synergy: '高尚道德情操凝聚无上人望，不怒而自威，不言而自化。',
      theme: 'mint'
    },

    // 情感系
    '情感_野心': {
      name: '狂焰殉欲',
      tagline: '情欲如炽，灼烧命运；以偏执烈火撕扯一切阻碍。',
      synergy: '私欲与深情剧烈纠缠，形成吞噬一切也毁灭自我的狂暴动力。',
      theme: 'violet'
    },
    '情感_权势': {
      name: '仁恩魁首',
      tagline: '情系袍泽，恩抚部曲；以深情牵绊织就牢固权力网络。',
      synergy: '权柄化为羽翼庇护所爱之人，部众感念恩义誓死效忠。',
      theme: 'signal'
    },
    '情感_道义': {
      name: '悲悯行者',
      tagline: '心怀万灵之痛，孤身涉渡长夜；以至柔之慈悲抵御凛冽宿命。',
      synergy: '慈悲济世，守正不移；至深共情化为坚不可摧的人间底线。',
      theme: 'mint'
    },

    // 野心系
    '野心_权势': {
      name: '登极枭雄',
      tagline: '九五之尊，野心勃勃；调动一切权柄资源只为登顶称王。',
      synergy: '欲望与地位互相催化，步步为营，凡所目及皆欲掌控。',
      theme: 'violet'
    },
    '野心_道义': {
      name: '改序仁雄',
      tagline: '胸怀宏图，正道直行；以不世雄心重塑世间公理秩序。',
      synergy: '既有颠覆旧秩序之雄图大略，又恪守仁义公理之赤子初心。',
      theme: 'mint'
    },

    // 权势系
    '权势_道义': {
      name: '清平宪首',
      tagline: '手握重柄，秉公持正；身居显赫而两袖清风、断恶抚弱。',
      synergy: '权位用于匡扶正义，以铁面无私之原则捍卫世间公道。',
      theme: 'mint'
    }
  };

  /**
   * 安全抽取单个维度的评分信息
   */
  function getEntry(attrs, k) {
    if (!attrs || typeof attrs !== 'object') {
      return { score: null, pending: true, low: true, evidence: [], basis: '' };
    }
    var val = attrs[k];
    // 兼容英文属性键名如 attrs.MIND
    if (val === undefined && EN[k] && attrs[EN[k]] !== undefined) {
      val = attrs[EN[k]];
    }
    if (val === null || val === undefined) {
      return { score: null, pending: true, low: true, evidence: [], basis: '' };
    }
    if (typeof val === 'number') {
      if (isNaN(val)) return { score: null, pending: true, low: true, evidence: [], basis: '' };
      return { score: Math.max(0, Math.min(100, val)), pending: false, low: false, evidence: [], basis: '' };
    }
    if (typeof val === 'object') {
      var s = val.score;
      var pend = !!(val.pending || s === null || s === undefined || isNaN(+s));
      var sc = pend ? null : Math.max(0, Math.min(100, +s));
      return {
        score: sc,
        pending: pend,
        low: !!val.low || !(Array.isArray(val.evidence) && val.evidence.length > 0),
        evidence: Array.isArray(val.evidence) ? val.evidence : [],
        basis: typeof val.basis === 'string' ? val.basis : ''
      };
    }
    return { score: null, pending: true, low: true, evidence: [], basis: '' };
  }

  /**
   * 判断单个属性对象是否为待建档
   */
  function isPending(a) {
    if (a === null || a === undefined) return true;
    if (typeof a === 'number') return isNaN(a);
    if (typeof a === 'object') return !!(a.pending || a.score === null || a.score === undefined || isNaN(+a.score));
    return true;
  }

  /**
   * 判断八维是否全为待建档
   */
  function allPending(attrs) {
    if (!attrs || typeof attrs !== 'object') return true;
    for (var i = 0; i < KEYS.length; i++) {
      var e = getEntry(attrs, KEYS[i]);
      if (!e.pending && e.score !== null) return false;
    }
    return true;
  }

  /**
   * 2. getBalanceMetrics(attrs): 计算八维分值的极差 range、方差/散度 variance、均衡度指数 balanceScore
   * 
   * @param {Object} attrs - 八维属性对象
   * @returns {Object} 包含 range, variance, balanceScore, mean, stdDev, min, max, scoredCount, pending
   */
  function getBalanceMetrics(attrs) {
    var scored = [];
    if (attrs && typeof attrs === 'object') {
      for (var i = 0; i < KEYS.length; i++) {
        var k = KEYS[i];
        var e = getEntry(attrs, k);
        if (!e.pending && e.score !== null && !isNaN(e.score)) {
          scored.push(e.score);
        }
      }
    }

    if (scored.length === 0) {
      return {
        range: 0,
        variance: 0,
        balanceScore: 0,
        mean: 0,
        stdDev: 0,
        min: 0,
        max: 0,
        scoredCount: 0,
        pending: true
      };
    }

    var min = scored[0], max = scored[0], sum = 0;
    for (var j = 0; j < scored.length; j++) {
      var v = scored[j];
      if (v < min) min = v;
      if (v > max) max = v;
      sum += v;
    }
    var range = Math.round((max - min) * 100) / 100;
    var mean = Math.round((sum / scored.length) * 100) / 100;

    var varSum = 0;
    for (var m = 0; m < scored.length; m++) {
      var diff = scored[m] - mean;
      varSum += diff * diff;
    }
    var variance = Math.round((varSum / scored.length) * 100) / 100;
    var stdDev = Math.round(Math.sqrt(variance) * 100) / 100;

    // 均衡度指数：0..100，越均匀越高
    // range 最大 100，stdDev 理论最大 50
    // 综合惩罚模型：range * 0.55 + stdDev * 0.90
    var penalty = range * 0.55 + stdDev * 0.90;
    var balanceScore = Math.max(0, Math.min(100, Math.round(100 - penalty)));

    return {
      range: range,
      variance: variance,
      balanceScore: balanceScore,
      mean: mean,
      stdDev: stdDev,
      min: min,
      max: max,
      scoredCount: scored.length,
      pending: false
    };
  }

  /**
   * 1. resolveArchetype(attrs): 输入八维属性，分析分值分布与高权重组合，输出角色原型定义对象
   * 
   * @param {Object} attrs - 八维属性对象
   * @returns {Object} 角色原型定义对象 { name, tagline, color, token, topPair, metrics, isPending, ... }
   */
  function resolveArchetype(attrs) {
    if (!attrs || typeof attrs !== 'object' || allPending(attrs)) {
      return JSON.parse(JSON.stringify(UNPROFILED));
    }

    var metrics = getBalanceMetrics(attrs);
    if (metrics.pending || metrics.scoredCount === 0) {
      return JSON.parse(JSON.stringify(UNPROFILED));
    }

    // 收集所有有效评分维度
    var scored = [];
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var e = getEntry(attrs, k);
      if (!e.pending && e.score !== null && !isNaN(e.score)) {
        scored.push({ key: k, score: e.score, en: EN[k] });
      }
    }

    if (scored.length === 0) {
      return JSON.parse(JSON.stringify(UNPROFILED));
    }

    // 按得分从高到低排序，判定第一峰值与第二峰值
    scored.sort(function (a, b) { return b.score - a.score; });
    var first = scored[0];
    var second = scored.length > 1 ? scored[1] : null;

    function getVal(key) {
      var entry = getEntry(attrs, key);
      return entry.pending ? null : entry.score;
    }

    function s(key) {
      var v = getVal(key);
      return v !== null ? v : 0;
    }

    // 组装最高前两维及协同说明对象
    var topPair = null;
    if (second) {
      var pairKey1 = first.key + '_' + second.key;
      var pairKey2 = second.key + '_' + first.key;
      var pairDef = TOP_PAIRS[pairKey1] || TOP_PAIRS[pairKey2] || {
        name: first.key + second.key + '先驱',
        tagline: first.key + '与' + second.key + '双核驱动，独树一帜。',
        synergy: first.key + '与' + second.key + '高频共鸣，构筑核心优势。',
        theme: 'mint'
      };
      topPair = {
        primary: first.key,
        secondary: second.key,
        keys: [first.key, second.key],
        label: first.key + ' × ' + second.key,
        synergy: pairDef.synergy
      };
    } else {
      // 仅有一维建档的情况
      topPair = {
        primary: first.key,
        secondary: null,
        keys: [first.key],
        label: first.key + ' 独曜',
        synergy: '当前仅建档 ' + first.key + ' 维度（' + first.score + ' 分），其余维度尚待建档观测。'
      };
    }

    // 优先匹配全局分布特征与专属原型：

    // 1. 全维均衡 (八维平正，极差小，各维融通)
    if (metrics.scoredCount >= 6 && (metrics.range <= 18 || (metrics.balanceScore >= 80 && metrics.variance <= 55))) {
      var isHi = metrics.mean >= 80;
      var balTheme = isHi ? 'signal' : 'mint';
      return {
        id: 'balanced_master',
        name: '全维均衡',
        en: 'HARMONIOUS_MASTER',
        tagline: '八极通融，万象并御；无偏无颇，兼修并济臻于至衡。',
        color: THEME_COLORS[balTheme].hex,
        token: THEME_COLORS[balTheme].token,
        theme: balTheme,
        cssVar: THEME_COLORS[balTheme].varName,
        description: '八维属性分布高度均衡，无明显短板，攻守兼备，综合适应性极强。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 2. 纯粹智囊 (智谋单维极高且明显高于实力/权势，专注心智与策略)
    if (first.key === '智谋' && first.score >= 75 && (first.score - s('实力') >= 18) && (first.score - s('权势') >= 14)) {
      return {
        id: 'pure_thinker',
        name: '纯粹智囊',
        en: 'PURE_THINKER',
        tagline: '寸缕烛光窥算天机；以思为刃，何须身先士卒。',
        color: THEME_COLORS.mint.hex,
        token: THEME_COLORS.mint.token,
        theme: 'mint',
        cssVar: THEME_COLORS.mint.varName,
        description: '心智算计超绝于世，以智谋为唯一信仰，布局深远而不涉短兵相接。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 3. 权谋枭雄 (高权势 + 高野心 + 高智谋，且道义偏低)
    if (s('野心') >= 70 && s('权势') >= 70 && s('智谋') >= 65 && s('道义') <= 58) {
      return {
        id: 'machiavellian_hegemon',
        name: '权谋枭雄',
        en: 'MACHIAVELLIAN_HEGEMON',
        tagline: '权倾朝野，野火燎原；以天下为棋局，凡涉道义皆可断舍。',
        color: THEME_COLORS.violet.hex,
        token: THEME_COLORS.violet.token,
        theme: 'violet',
        cssVar: THEME_COLORS.violet.varName,
        description: '深谙权力法则与欲望推力，算计深沉，行事不拘泥于道德底线。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 4. 悲悯行者 (情感 + 道义 双核高企)
    var isCompassionate = (first.key === '情感' && second && second.key === '道义') ||
                          (first.key === '道义' && second && second.key === '情感') ||
                          (s('情感') >= 72 && s('道义') >= 72);
    if (isCompassionate) {
      return {
        id: 'compassionate_pilgrim',
        name: '悲悯行者',
        en: 'COMPASSIONATE_PILGRIM',
        tagline: '心怀万灵之痛，孤身涉渡长夜；以至柔之慈悲抵御凛冽宿命。',
        color: THEME_COLORS.mint.hex,
        token: THEME_COLORS.mint.token,
        theme: 'mint',
        cssVar: THEME_COLORS.mint.varName,
        description: '心怀苍生万物，以极度共情与坚定道义为舟，涉渡乱世劫波。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 5. 超然圣者 (高道义 + 高智谋或意志，且极低野心/权势，情感非极端浓烈)
    if (s('道义') >= 75 && (s('智谋') >= 65 || s('意志') >= 65) && s('野心') <= 50 && s('权势') <= 55 && s('情感') <= 70) {
      return {
        id: 'transcendental_saint',
        name: '超然圣者',
        en: 'TRANSCENDENTAL_SAINT',
        tagline: '执道不孤，澄澈如渊；脱却人间利欲，立身万象之上。',
        color: THEME_COLORS.mint.hex,
        token: THEME_COLORS.mint.token,
        theme: 'mint',
        cssVar: THEME_COLORS.mint.varName,
        description: '行正道而弃利禄，心如明镜，超脱世俗凡尘之名利纠葛。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 6. 宿命狂徒 (高野心 + 高意志，抗拒天命，道义不居首)
    var isDestinyZealot = (first.key === '野心' && second && second.key === '意志') ||
                          (first.key === '意志' && second && second.key === '野心') ||
                          (s('野心') >= 75 && s('意志') >= 75 && s('道义') <= 65);
    if (isDestinyZealot) {
      return {
        id: 'destiny_zealot',
        name: '宿命狂徒',
        en: 'DESTINY_ZEALOT',
        tagline: '身负逆鳞，狂蹈死生；纵是万劫不复，亦要撞碎宿命桎梏。',
        color: THEME_COLORS.violet.hex,
        token: THEME_COLORS.violet.token,
        theme: 'violet',
        cssVar: THEME_COLORS.violet.varName,
        description: '欲望与意志燃烧至极限，向既定宿命发起狂烈冲撞，百死无悔。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 7. 霸绝战将 (实力极高 + 意志/权势雄厚)
    var isSupremeWarlord = (first.key === '实力' && first.score >= 75 && second && (second.key === '意志' || second.key === '权势')) ||
                           (first.key === '实力' && first.score >= 80);
    if (isSupremeWarlord && !(second && second.key === '野心' && second.score >= 75)) {
      return {
        id: 'supreme_warlord',
        name: '霸绝战将',
        en: 'SUPREME_WARLORD',
        tagline: '横刀断水，气吞山河；千军辟易处，唯以硬实力破万法。',
        color: THEME_COLORS.hot.hex,
        token: THEME_COLORS.hot.token,
        theme: 'hot',
        cssVar: THEME_COLORS.hot.varName,
        description: '个体武道或战场硬实力臻于极境，披坚执锐，无坚不摧。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 8. 破阵狂澜 (实力 + 野心 双核)
    var isRagingVanguard = (first.key === '实力' && second && second.key === '野心') ||
                           (first.key === '野心' && second && second.key === '实力');
    if (isRagingVanguard) {
      return {
        id: 'raging_vanguard',
        name: '破阵狂澜',
        en: 'RAGING_VANGUARD',
        tagline: '狂澜既起，破阵摧坚；烈意奔涌处，万钧难当。',
        color: THEME_COLORS.hot.hex,
        token: THEME_COLORS.hot.token,
        theme: 'hot',
        cssVar: THEME_COLORS.hot.varName,
        description: '以狂暴战力践行雄图野心，如山洪决堤，撕碎一切秩序阵型。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 9. 深谋策士 (智谋首位 + 权势/野心/意志)
    if (first.key === '智谋' && first.score >= 70) {
      return {
        id: 'master_strategist',
        name: '深谋策士',
        en: 'MASTER_STRATEGIST',
        tagline: '帷幄定局，运筹乾坤；落子无声，翻覆间风云皆入彀中。',
        color: THEME_COLORS.mint.hex,
        token: THEME_COLORS.mint.token,
        theme: 'mint',
        cssVar: THEME_COLORS.mint.varName,
        description: '心智如海，以策略谋算掌控事态走向，走一步看十步。',
        topPair: topPair,
        metrics: metrics,
        isPending: false
      };
    }

    // 回退到最高双维原型矩阵
    if (second) {
      var pairKey = first.key + '_' + second.key;
      var pairRev = second.key + '_' + first.key;
      var match = TOP_PAIRS[pairKey] || TOP_PAIRS[pairRev];
      if (match) {
        var th = match.theme || 'mint';
        return {
          id: 'archetype_' + (EN[first.key] || 'ATTR').toLowerCase() + '_' + (EN[second.key] || 'ATTR').toLowerCase(),
          name: match.name,
          en: (EN[first.key] || '') + '_' + (EN[second.key] || ''),
          tagline: match.tagline,
          color: THEME_COLORS[th].hex,
          token: THEME_COLORS[th].token,
          theme: th,
          cssVar: THEME_COLORS[th].varName,
          description: match.synergy,
          topPair: topPair,
          metrics: metrics,
          isPending: false
        };
      }
    }

    // 单维主导回退
    var singleTheme = (first.key === '实力' || first.key === '野心') ? 'hot' :
                      (first.key === '魅力' || first.key === '权势') ? 'signal' :
                      (first.key === '意志') ? 'violet' : 'mint';
    return {
      id: 'archetype_' + (EN[first.key] || 'ATTR').toLowerCase(),
      name: first.key + '先锋',
      en: EN[first.key] || 'PIONEER',
      tagline: first.key + '独耀星天，锋芒毕露。',
      color: THEME_COLORS[singleTheme].hex,
      token: THEME_COLORS[singleTheme].token,
      theme: singleTheme,
      cssVar: THEME_COLORS[singleTheme].varName,
      description: '在 ' + first.key + ' 维度展现出极高专注度，其余维度协同仍在展开。',
      topPair: topPair,
      metrics: metrics,
      isPending: false
    };
  }

  /**
   * 辅助函数：便捷提取最高双维协同对象
   */
  function getTopPair(attrs) {
    var arch = resolveArchetype(attrs);
    return arch.topPair;
  }

  /**
   * R7 · 24×24 原型几何矢量徽记发生器 (S5 图集规范)
   */
  var ARCH_SIGILS = {
    mind: 'M12 2L21 12L12 21L3 12Z M12 6L18 12L12 18L6 12Z M12 9A3 3 0 1 0 12 15A3 3 0 1 0 12 9Z',
    force: 'M4 4L10 10M20 4L14 10M4 20L10 14M20 20L14 14M12 2V22M2 12H22',
    will: 'M12 2L22 8V16L12 22L2 16V8Z M12 6L18 10V14L12 18L6 14V10Z',
    charm: 'M12 2C14 7 17 10 22 12C17 14 14 17 12 22C10 17 7 14 2 12C7 10 10 7 12 2Z',
    heart: 'M12 4C10 2 6 2 4 5C2 8 4 13 12 20C20 13 22 8 20 5C18 2 14 2 12 4Z',
    drive: 'M12 2L20 10H15V22H9V10H4Z',
    reach: 'M2 18L5 6L12 11L19 6L22 18Z M4 20H20',
    code: 'M12 3V21M3 8H21M5 8L2 15H8ZM19 8L16 15H22Z',
    balanced: 'M12 2L15 8L22 9L17 14L18 21L12 18L6 21L7 14L2 9L9 8Z'
  };

  function sigilSVG(archId, color, size) {
    size = size || 16;
    color = color || 'currentColor';
    var pathD = ARCH_SIGILS[archId] || ARCH_SIGILS.balanced;
    return '<svg class="rd-arch-sigil" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:4px;flex-shrink:0">' +
      '<path d="' + pathD + '"/>' +
      '</svg>';
  }

  /**
   * 辅助函数：生成语义化全息胶囊标签 HTML (含 R7 矢量徽记)
   */
  function badgeHTML(attrsOrArch) {
    var arch = (attrsOrArch && attrsOrArch.id && attrsOrArch.name)
      ? attrsOrArch
      : resolveArchetype(attrsOrArch);

    if (!arch || arch.isPending) {
      return '<span class="rd-arch-badge pend" style="color:var(--ink-3,#88819d);border:1px solid rgba(125,118,150,0.28);border-radius:2px;padding:2px 6px;font:600 11px var(--mono,monospace);letter-spacing:0.06em">待建档</span>';
    }

    var colorVal = arch.token || arch.color;
    var sigil = sigilSVG(arch.id, colorVal, 14);
    return '<span class="rd-arch-badge" data-arch-id="' + arch.id + '" style="color:' + colorVal + ';border:1px solid ' + colorVal + ';border-radius:2px;padding:2px 6px;font:600 11px var(--mono,monospace);letter-spacing:0.06em;background:rgba(7,6,13,0.72);display:inline-flex;align-items:center">' +
      sigil +
      '<b class="rd-arch-name">' + arch.name + '</b>' +
      (arch.topPair ? '<span class="rd-arch-sub" style="opacity:0.8;margin-left:4px">[' + arch.topPair.label + ']</span>' : '') +
      '</span>';
  }

  var CLRadarArchetype = {
    KEYS: KEYS,
    EN: EN,
    EN_REV: EN_REV,
    THEME_COLORS: THEME_COLORS,
    TOP_PAIRS: TOP_PAIRS,
    UNPROFILED: UNPROFILED,
    resolveArchetype: resolveArchetype,
    getBalanceMetrics: getBalanceMetrics,
    getTopPair: getTopPair,
    isPending: isPending,
    allPending: allPending,
    sigilSVG: sigilSVG,
    badgeHTML: badgeHTML
  };

  return CLRadarArchetype;
});
