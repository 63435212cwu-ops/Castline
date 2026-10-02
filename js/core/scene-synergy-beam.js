/**
 * Castline · scene-synergy-beam.js — 双核属性协同光束与极值引力场生成器
 * ============================================================================
 * 模块：U07 · 双核属性协同光束与极值引力场生成器 (Swarm 20260912-2315-crown-hud)
 * 契约：
 *   - C1 接口契约：挂载 window.CLSceneSynergyBeam，全防御入参校验，非法/空数据安全优雅回退为 null
 *   - C4 能量光束：双核极值属性间构建三维与二维空间贝塞尔光束、高能光核、霓虹光晕、光子沿轨流动、顶点锁定环
 *   - C5 空间共振：与晶冠秒跳（tick）同拍微观呼吸、双核引力偶极场与相干驻波微震
 *   - C7 独占产物：仅在独占文件 js/scene-synergy-beam.js 产出代码，严禁篡改主干代码与冻结文件
 * 
 * 共享约定：
 *   KEYS: ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义']
 *   EN: { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' }
 *   色彩谱系：黑曜石 #07060d，薄荷 #7af0c8，太阳琥珀 #ffb45c，虚空紫 #a688ff，绯红 #ff5c7c
 *   设计令牌：严格使用 var(--abyss-*, #hex) 规范，不写裸色值裸像素
 * 
 * 最小使用示例 / Minimal Usage Example:
 * ----------------------------------------------------------------------------
 * // 1. 解析角色最高双核属性协同（如 智谋 × 实力、情感 × 道义）
 * const synergy = window.CLSceneSynergyBeam.resolveSynergyPair(character.attrs);
 * if (synergy) {
 *   console.log(synergy.label);       // e.g. "实力 × 情感"
 *   console.log(synergy.archetype);   // e.g. "护道战狂"
 *   console.log(synergy.synergy);     // e.g. "炽烈情感化为无可遏止的力量源泉，因守护而所向披靡。"
 *   console.log(synergy.color);       // e.g. "#ff5c7c"
 *   console.log(synergy.token);       // e.g. "var(--abyss-crimson, #ff5d73)"
 * }
 * 
 * // 2. 生成三维空间 / 2D 投影光束曲线与流动粒子波
 * const curve = window.CLSceneSynergyBeam.createSynergyCurve(ptA, ptB, tAnim, {
 *   curvature: 0.28,
 *   particleCount: 5,
 *   resonance: 0.8
 * });
 * console.log(curve.points);          // Array of {x, y, z} 三维曲线点集 (含 .clone() / .copy())
 * console.log(curve.svgPath);         // "M 120,80 Q 240,40 360,95" (SVG 导轨)
 * console.log(curve.particles);       // Array of { progress, x, y, z, size, alpha }
 * 
 * // 3. 极值引力场与拉格朗日鞍点计算
 * const field = window.CLSceneSynergyBeam.createGravityField(ptA, ptB, {
 *   scoreA: synergy.primary.score,
 *   scoreB: synergy.secondary.score
 * });
 * console.log(field.lagrangeL1);      // { x, y, z } 双核引力平衡中心
 * const evalAt = field.evaluateAt({ x: 100, y: 120, z: 0 }); // { force, potential, fieldStrength }
 * 
 * // 4. 钟表整秒跳动（tick）同拍共振
 * const resonance = window.CLSceneSynergyBeam.createResonanceField(ptA, ptB, tAnim);
 * console.log(resonance.ringA);       // 顶点锁定环瞬时激发尺度与光晕
 * 
 * // 5. SVG 全息导轨渲染与就地更新 (60 FPS 无 GC 抖动)
 * const svgHTML = window.CLSceneSynergyBeam.renderSVGBeam(ptA, ptB, tAnim, { theme: synergy.theme });
 * window.CLSceneSynergyBeam.updateSVGBeamElement(groupEl, ptA, ptB, tAnim);
 * ----------------------------------------------------------------------------
 */

(function (root, factory) {
  if (typeof exports === 'object' && typeof module !== 'undefined') {
    module.exports = factory();
  } else if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else {
    var mod = factory();
    root.CLSceneSynergyBeam = mod;
    if (typeof window !== 'undefined') {
      window.CLSceneSynergyBeam = mod;
      // 增强跨模块别名兼容
      window.CLRadarSynergyBeam = mod;
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

  // 核心色彩常量（十六进制标准色）
  var THEME_COLORS = {
    mint: '#7af0c8',
    signal: '#ffb45c',
    violet: '#a688ff',
    hot: '#ff5c7c',
    crimson: '#ff5c7c',
    legend: '#fff1c4',
    obsidian: '#07060d',
    muted: '#7d7696'
  };

  // CSS 语义令牌表映射（优先引用 --abyss-*，终极字面量 fallback）
  var THEME_TOKENS = {
    mint: 'var(--abyss-mint, #7af0c8)',
    signal: 'var(--abyss-signal, #ffb45c)',
    violet: 'var(--abyss-violet, #a688ff)',
    hot: 'var(--abyss-crimson, #ff5d73)',
    crimson: 'var(--abyss-crimson, #ff5d73)',
    legend: 'var(--abyss-tier-legend, #fff1c4)',
    obsidian: 'var(--abyss-obsidian, #05050b)',
    muted: 'var(--abyss-ink-3, #88819d)',
    inkBright: 'var(--abyss-ink-bright, #ffffff)'
  };

  // 28 组八维双核协同原型矩阵（权威标准谱系）
  var TOP_PAIRS = {
    // 智谋系 (7)
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

    // 实力系 (6)
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

    // 意志系 (5)
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

    // 魅力系 (4)
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

    // 情感系 (3)
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

    // 野心系 (2)
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

    // 权势系 (1)
    '权势_道义': {
      name: '清平宪首',
      tagline: '手握重柄，秉公持正；身居显赫而两袖清风、断恶抚弱。',
      synergy: '权位用于匡扶正义，以铁面无私之原则捍卫世间公道。',
      theme: 'mint'
    }
  };

  // ══════════════════════════════════════════════════════════════════════════
  // 辅助几何与数学向量工具
  // ══════════════════════════════════════════════════════════════════════════

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function isValidPoint(p) {
    if (!p || typeof p !== 'object') return false;
    var x = p.x != null ? p.x : p.x0;
    var y = p.y != null ? p.y : p.y0;
    if (typeof x !== 'number' || isNaN(x) || !isFinite(x)) return false;
    if (typeof y !== 'number' || isNaN(y) || !isFinite(y)) return false;
    if (p.z != null && (typeof p.z !== 'number' || isNaN(p.z) || !isFinite(p.z))) return false;
    return true;
  }

  function extractPoint(p) {
    return {
      x: p.x != null ? p.x : p.x0,
      y: p.y != null ? p.y : p.y0,
      z: p.z != null ? p.z : 0
    };
  }

  function dist3D(a, b) {
    var dx = b.x - a.x, dy = b.y - a.y, dz = (b.z || 0) - (a.z || 0);
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  function makeDuckVector3(x, y, z) {
    return {
      x: x,
      y: y,
      z: z,
      isVector3: true,
      set: function (nx, ny, nz) { this.x = nx; this.y = ny; this.z = nz; return this; },
      copy: function (v) { this.x = v.x; this.y = v.y; this.z = v.z || 0; return this; },
      clone: function () { return makeDuckVector3(this.x, this.y, this.z); },
      add: function (v) { this.x += v.x; this.y += v.y; this.z += v.z || 0; return this; },
      sub: function (v) { this.x -= v.x; this.y -= v.y; this.z -= v.z || 0; return this; },
      multiplyScalar: function (s) { this.x *= s; this.y *= s; this.z *= s; return this; },
      distanceTo: function (v) { return dist3D(this, v); }
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 1. resolveSynergyPair(attrs): 双核属性最高协同解析
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 找出角色八维分值最高的两个维度，并解析对应的双核协同原型与张力指标。
   * 
   * 全防御保障：
   * - 入参为 null、undefined、空对象、原始类型、全待建档或仅有 1 维建档时，优雅回退为 null，绝不抛错。
   * 
   * @param {Object} attrs 角色八维属性字典或包裹对象
   * @returns {Object|null} 双核协同描述对象，无协同/未建档则返回 null
   */
  function resolveSynergyPair(attrs) {
    if (!attrs || typeof attrs !== 'object') return null;

    // 容错解包：若传入角色实体对象 character，尝试解包 attrs.attrs
    var raw = attrs;
    if (attrs.attrs && typeof attrs.attrs === 'object') {
      raw = attrs.attrs;
    }

    var scored = [];

    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var item = raw[k];
      if (item === undefined || item === null) continue;

      var sc = NaN;
      if (typeof item === 'number') {
        sc = item;
      } else if (typeof item === 'object') {
        if (item.pending === true) continue;
        if (item.score !== undefined && item.score !== null) {
          sc = Number(item.score);
        }
      }

      if (typeof sc === 'number' && !isNaN(sc) && isFinite(sc) && sc >= 0) {
        scored.push({
          key: k,
          en: EN[k] || 'DIM',
          score: clamp(Math.round(sc), 0, 100),
          origIndex: i
        });
      }
    }

    // 防御：有效分值维度必须 >= 2，否则无双核协同关系，优雅回退为 null
    if (scored.length < 2) return null;

    // 按分值从高到低排序，同分依据 KEYS 固有次序保持稳定性
    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.origIndex - b.origIndex;
    });

    var first = scored[0];
    var second = scored[1];

    // 防御：若双峰均为 0 分，判定为未初始化的占位数据，回退为 null
    if (first.score <= 0 && second.score <= 0) return null;

    // 组合键匹配（无序两两匹配）
    var pairKey1 = first.key + '_' + second.key;
    var pairKey2 = second.key + '_' + first.key;
    var pairDef = TOP_PAIRS[pairKey1] || TOP_PAIRS[pairKey2] || {
      name: first.key + second.key + '先驱',
      tagline: first.key + '与' + second.key + '双核驱动，独树一帜。',
      synergy: first.key + '与' + second.key + '高频共鸣，构筑核心优势。',
      theme: 'mint'
    };

    var theme = pairDef.theme || 'mint';
    var color = THEME_COLORS[theme] || THEME_COLORS.mint;
    var token = THEME_TOKENS[theme] || THEME_TOKENS.mint;

    var delta = Math.abs(first.score - second.score);
    var meanScore = (first.score + second.score) / 2;
    var tension = Number(((first.score * 0.55 + second.score * 0.45) / 100).toFixed(3));
    var power = Number(((first.score * second.score) / 10000).toFixed(3));
    var closeness = Number((1 - delta / Math.max(1, first.score)).toFixed(3));
    var harmonicFreq = Number((1.2 + (first.score + second.score) / 160).toFixed(2));

    return {
      primary: {
        key: first.key,
        en: first.en,
        score: first.score,
        index: first.origIndex,
        rank: 1
      },
      secondary: {
        key: second.key,
        en: second.en,
        score: second.score,
        index: second.origIndex,
        rank: 2
      },
      keys: [first.key, second.key],
      pairKey: pairKey1,
      label: first.key + ' × ' + second.key,
      archetype: pairDef.name,
      tagline: pairDef.tagline,
      synergy: pairDef.synergy,
      theme: theme,
      color: color,
      token: token,
      delta: delta,
      mean: Number(meanScore.toFixed(1)),
      ratio: Number((second.score / Math.max(1, first.score)).toFixed(3)),
      tension: tension,
      power: power,
      closeness: closeness,
      harmonicFreq: harmonicFreq
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 2. createSynergyCurve(ptA, ptB, time, opt): 空间贝塞尔光束曲线点集
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 生成连接两属性顶点的三维圆弧 / 空间贝塞尔光束曲线点集及 2D SVG 投影路径。
   * 包含沿光束流动的粒子能量波、相干共振辉光与顶点微震。
   * 
   * 全防御保障：
   * - ptA 或 ptB 非法、缺失坐标或包含 NaN 时安全回退为 null，绝不报错。
   * 
   * @param {Object} ptA 起点顶点坐标 {x, y, [z]}
   * @param {Object} ptB 终点顶点坐标 {x, y, [z]}
   * @param {number} [time=0] 当前动画时间戳（秒）
   * @param {Object} [opt={}] 配置参数
   * @returns {Object|null} 曲线点集、SVG路径与流动能量包元数据
   */
  function createSynergyCurve(ptA, ptB, time, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var L = dist3D(pA, pB);
    if (L < 0.001) return null; // 零距离重合退化，优雅回退

    var t = (typeof time === 'number' && !isNaN(time) && isFinite(time)) ? time : 0;
    var options = (opt && typeof opt === 'object') ? opt : {};

    var samples = clamp(options.samples || 32, 8, 128);
    var curvature = (typeof options.curvature === 'number' && !isNaN(options.curvature)) ? options.curvature : 0.28;
    var sagitta = (typeof options.sagitta === 'number' && !isNaN(options.sagitta)) ? options.sagitta : L * curvature;
    var is3D = options.is3D !== undefined ? Boolean(options.is3D) : (ptA.z != null || ptB.z != null);
    var particleCount = clamp(options.particleCount || 5, 1, 16);
    var pulseSpeed = (typeof options.pulseSpeed === 'number') ? options.pulseSpeed : 0.85;
    var resonance = (typeof options.resonance === 'number') ? clamp(options.resonance, 0, 2) : 0.75;
    var harmonicFreq = (typeof options.harmonicFreq === 'number') ? options.harmonicFreq : 2.0;
    var elevation = (typeof options.elevation === 'number') ? options.elevation : (is3D ? L * 0.12 : 0);

    var gravityCenter = isValidPoint(options.gravityCenter) ? extractPoint(options.gravityCenter) : { x: 0, y: 0, z: 0 };

    // 中点 M 与 弦向量 D
    var Mx = (pA.x + pB.x) * 0.5;
    var My = (pA.y + pB.y) * 0.5;
    var Mz = (pA.z + pB.z) * 0.5;

    var Dx = pB.x - pA.x;
    var Dy = pB.y - pA.y;
    var Dz = pB.z - pA.z;

    var uDx = Dx / L;
    var uDy = Dy / L;
    var uDz = Dz / L;

    // 引力中心指向中点的向量 R
    var Rx = Mx - gravityCenter.x;
    var Ry = My - gravityCenter.y;
    var Rz = Mz - gravityCenter.z;

    // 计算拱起法向量 N
    var Nx = 0, Ny = 0, Nz = 0;

    if (!is3D) {
      // 2D 投影平面：取弦的垂直法线 (-uDy, uDx)
      Nx = -uDy;
      Ny = uDx;
      Nz = 0;
      // 若与重心朝向相反，反转以朝外拱起（如同向外辐射的电磁弧）
      var dot2D = Nx * Rx + Ny * Ry;
      if (dot2D < 0) {
        Nx = -Nx;
        Ny = -Ny;
      }
    } else {
      // 3D 空间：取 R 在垂直于弦平面上的投影
      var dotR = Rx * uDx + Ry * uDy + Rz * uDz;
      var rawNx = Rx - dotR * uDx;
      var rawNy = Ry - dotR * uDy;
      var rawNz = Rz - dotR * uDz;
      var lenN = Math.sqrt(rawNx * rawNx + rawNy * rawNy + rawNz * rawNz);

      if (lenN > 0.001) {
        Nx = rawNx / lenN;
        Ny = rawNy / lenN;
        Nz = rawNz / lenN;
      } else {
        // 退化情况：弦直指引力中心，以世界 Y 轴叉乘求法线
        Nx = -uDz;
        Ny = 0;
        Nz = uDx;
        var lenAlt = Math.sqrt(Nx * Nx + Nz * Nz);
        if (lenAlt > 0.001) {
          Nx /= lenAlt;
          Nz /= lenAlt;
        } else {
          Nx = 0; Ny = 1; Nz = 0;
        }
      }
    }

    // 二次贝塞尔顶点控制点 C
    var Cx = Mx + Nx * sagitta;
    var Cy = My + Ny * sagitta + elevation;
    var Cz = Mz + Nz * sagitta;

    // 三次贝塞尔双控制点 C1, C2（模拟双核引力井）
    var C1x = pA.x + Dx * 0.333 + Nx * sagitta * 0.85;
    var C1y = pA.y + Dy * 0.333 + Ny * sagitta * 0.85 + elevation * 0.7;
    var C1z = pA.z + Dz * 0.333 + Nz * sagitta * 0.85;

    var C2x = pA.x + Dx * 0.667 + Nx * sagitta * 0.85;
    var C2y = pA.y + Dy * 0.667 + Ny * sagitta * 0.85 + elevation * 0.7;
    var C2z = pA.z + Dz * 0.667 + Nz * sagitta * 0.85;

    // 相干共振波（秒跳同拍微观驻波，端点振幅为 0 绝对锚定顶点）
    var tickFrac = (typeof options.tickFrac === 'number') ? clamp(options.tickFrac, 0, 1) : (t % 1);
    var tickPulse = Math.exp(-tickFrac * 4.5);
    var waveAmp = (L * 0.024) * resonance * (1.0 + 0.45 * tickPulse);
    var phase = t * harmonicFreq * Math.PI * 2;

    // 计算副法向量 B (用于双螺旋伴流包裹光桥)
    var Bx = uDy * Nz - uDz * Ny;
    var By = uDz * Nx - uDx * Nz;
    var Bz = uDx * Ny - uDy * Nx;
    var lenB = Math.sqrt(Bx * Bx + By * By + Bz * Bz);
    if (lenB > 0.001) { Bx /= lenB; By /= lenB; Bz /= lenB; }
    else { Bx = 0; By = 0; Bz = 1; }

    var spiralA = [];
    var spiralB = [];
    var spiralRadius = L * 0.038;

    // 曲线采样点集合与 Float32Array 数组
    var points = [];
    var positions = new Float32Array((samples + 1) * 3);

    for (var s = 0; s <= samples; s++) {
      var u = s / samples;
      var omt = 1 - u;

      // 二次贝塞尔基底
      var b0 = omt * omt;
      var b1 = 2 * omt * u;
      var b2 = u * u;

      var bx = b0 * pA.x + b1 * Cx + b2 * pB.x;
      var by = b0 * pA.y + b1 * Cy + b2 * pB.y;
      var bz = b0 * pA.z + b1 * Cz + b2 * pB.z;

      // 叠加相干驻波：sin(pi * u) 确保两极零位移
      var sinEnvelope = Math.sin(Math.PI * u);
      var standingWave = Math.sin(Math.PI * 4.0 * u - phase) * sinEnvelope * waveAmp;

      var px = bx + Nx * standingWave;
      var py = by + Ny * standingWave;
      var pz = bz + Nz * standingWave;

      var ptVec = makeDuckVector3(
        Number(px.toFixed(2)),
        Number(py.toFixed(2)),
        Number(pz.toFixed(2))
      );

      points.push(ptVec);
      positions[s * 3] = px;
      positions[s * 3 + 1] = py;
      positions[s * 3 + 2] = pz;

      // C7: 螺旋伴流点 (两极收束为 0)
      var spEnv = sinEnvelope;
      var spR = spiralRadius * spEnv;
      var thetaA = u * Math.PI * 6.0 + phase;
      var thetaB = thetaA + Math.PI;

      var cosA = Math.cos(thetaA), sinA = Math.sin(thetaA);
      var cosB = Math.cos(thetaB), sinB = Math.sin(thetaB);

      var spAx = px + (Nx * cosA + Bx * sinA) * spR;
      var spAy = py + (Ny * cosA + By * sinA) * spR;
      var spAz = pz + (Nz * cosA + Bz * sinA) * spR;

      var spBx = px + (Nx * cosB + Bx * sinB) * spR;
      var spBy = py + (Ny * cosB + By * sinB) * spR;
      var spBz = pz + (Nz * cosB + Bz * sinB) * spR;

      spiralA.push(makeDuckVector3(Number(spAx.toFixed(2)), Number(spAy.toFixed(2)), Number(spAz.toFixed(2))));
      spiralB.push(makeDuckVector3(Number(spBx.toFixed(2)), Number(spBy.toFixed(2)), Number(spBz.toFixed(2))));
    }

    // 2D SVG 路径格式化
    var svgPath = 'M ' + pA.x.toFixed(1) + ' ' + pA.y.toFixed(1) +
                  ' Q ' + Cx.toFixed(1) + ' ' + Cy.toFixed(1) +
                  ' ' + pB.x.toFixed(1) + ' ' + pB.y.toFixed(1);

    var svgPathCubic = 'M ' + pA.x.toFixed(1) + ' ' + pA.y.toFixed(1) +
                       ' C ' + C1x.toFixed(1) + ' ' + C1y.toFixed(1) +
                       ' ' + C2x.toFixed(1) + ' ' + C2y.toFixed(1) +
                       ' ' + pB.x.toFixed(1) + ' ' + pB.y.toFixed(1);

    var waveParts = ['M ' + points[0].x.toFixed(1) + ' ' + points[0].y.toFixed(1)];
    for (var w = 1; w < points.length; w++) {
      waveParts.push('L ' + points[w].x.toFixed(1) + ' ' + points[w].y.toFixed(1));
    }
    var svgPathWave = waveParts.join(' ');

    // 沿导轨流动的粒子能量包 (Traveling Photon Energy Packets)
    var particles = [];
    for (var k = 0; k < particleCount; k++) {
      var progress = ((t * pulseSpeed + (k / particleCount)) % 1 + 1) % 1;
      var pomt = 1 - progress;

      var partBx = pomt * pomt * pA.x + 2 * pomt * progress * Cx + progress * progress * pB.x;
      var partBy = pomt * pomt * pA.y + 2 * pomt * progress * Cy + progress * progress * pB.y;
      var partBz = pomt * pomt * pA.z + 2 * pomt * progress * Cz + progress * progress * pB.z;

      var partWave = Math.sin(Math.PI * 4.0 * progress - phase) * Math.sin(Math.PI * progress) * waveAmp;
      var ppx = partBx + Nx * partWave;
      var ppy = partBy + Ny * partWave;
      var ppz = partBz + Nz * partWave;

      var env = Math.sin(Math.PI * progress);
      var alpha = Math.max(0, Math.min(1, Math.pow(env, 0.65) * (0.65 + 0.35 * Math.sin(t * 4.0 + k))));
      var size = Number((2.2 + 2.0 * env * (1.0 + 0.3 * tickPulse)).toFixed(2));
      var glow = Number((size * 2.8).toFixed(2));

      particles.push({
        index: k,
        progress: Number(progress.toFixed(4)),
        x: Number(ppx.toFixed(2)),
        y: Number(ppy.toFixed(2)),
        z: Number(ppz.toFixed(2)),
        size: size,
        alpha: Number(alpha.toFixed(3)),
        glow: glow
      });
    }

    // C7: 中途共鸣结节 (脉动光球，大小映射协同强度与 tick 脉冲)
    var midIdx = Math.floor(samples / 2);
    var midPt = points[midIdx] || points[0];
    var nodeSize = Number((4.2 + 3.2 * tickPulse * resonance).toFixed(2));
    var resonanceNode = {
      x: midPt.x,
      y: midPt.y,
      z: midPt.z,
      size: nodeSize,
      pulse: Number(tickPulse.toFixed(3)),
      phase: Number(phase.toFixed(3)),
      intensity: Number((0.65 + 0.35 * tickPulse).toFixed(3))
    };

    return {
      points: points,
      positions: positions,
      pointCount: points.length,
      distance: Number(L.toFixed(2)),
      midpoint: makeDuckVector3(Number(Mx.toFixed(2)), Number(My.toFixed(2)), Number(Mz.toFixed(2))),
      controlPoint: makeDuckVector3(Number(Cx.toFixed(2)), Number(Cy.toFixed(2)), Number(Cz.toFixed(2))),
      controlPoint1: makeDuckVector3(Number(C1x.toFixed(2)), Number(C1y.toFixed(2)), Number(C1z.toFixed(2))),
      controlPoint2: makeDuckVector3(Number(C2x.toFixed(2)), Number(C2y.toFixed(2)), Number(C2z.toFixed(2))),
      sagitta: Number(sagitta.toFixed(2)),
      svgPath: svgPath,
      svgPathCubic: svgPathCubic,
      svgPathWave: svgPathWave,
      particles: particles,
      hasLightBridge: true,
      spiralA: spiralA,
      spiralB: spiralB,
      resonanceNode: resonanceNode,
      resonance: {
        phase: Number(phase.toFixed(3)),
        intensity: Number((0.65 + 0.35 * tickPulse).toFixed(3)),
        tickPulse: Number(tickPulse.toFixed(3)),
        coreWidth: Number((1.6 + 0.6 * tickPulse).toFixed(2)),
        haloWidth: Number((5.5 + 2.5 * tickPulse).toFixed(2)),
        breath: Number((1.0 + 0.08 * Math.sin(t * 2.62)).toFixed(3)),
        coherence: Number((0.92 + 0.08 * tickPulse).toFixed(3))
      }
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 3. createGravityField(ptA, ptB, opt): 极值引力场与偶极势阱生成器
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 基于两极属性分值计算双核引力偶极场、内拉格朗日平衡点 (L1) 与空间任意点引力评估器。
   * 
   * @param {Object} ptA 顶点 A 坐标 {x, y, [z]}
   * @param {Object} ptB 顶点 B 坐标 {x, y, [z]}
   * @param {Object} [opt={}] 引力参数 (scoreA, scoreB 等)
   * @returns {Object|null} 引力场模型对象
   */
  function createGravityField(ptA, ptB, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);
    var L = dist3D(pA, pB);
    if (L < 0.001) return null;

    var options = (opt && typeof opt === 'object') ? opt : {};
    var scoreA = (typeof options.scoreA === 'number' && !isNaN(options.scoreA)) ? clamp(options.scoreA, 1, 100) : 80;
    var scoreB = (typeof options.scoreB === 'number' && !isNaN(options.scoreB)) ? clamp(options.scoreB, 1, 100) : 80;

    var massA = scoreA;
    var massB = scoreB;
    var totalMass = massA + massB;

    // 质心 (Barycenter)
    var bx = (massA * pA.x + massB * pB.x) / totalMass;
    var by = (massA * pA.y + massB * pB.y) / totalMass;
    var bz = (massA * pA.z + massB * pB.z) / totalMass;
    var barycenter = makeDuckVector3(Number(bx.toFixed(2)), Number(by.toFixed(2)), Number(bz.toFixed(2)));

    // 内拉格朗日鞍点 L1 (双极引力平衡中心: rA / rB = sqrt(mA / mB))
    var sqrtA = Math.sqrt(massA);
    var sqrtB = Math.sqrt(massB);
    var fracA = sqrtA / (sqrtA + sqrtB);

    var l1x = pA.x + fracA * (pB.x - pA.x);
    var l1y = pA.y + fracA * (pB.y - pA.y);
    var l1z = pA.z + fracA * (pB.z - pA.z);
    var lagrangeL1 = makeDuckVector3(Number(l1x.toFixed(2)), Number(l1y.toFixed(2)), Number(l1z.toFixed(2)));

    var fieldRadius = Number((L * 1.25).toFixed(2));
    var dipolePower = Number(((massA - massB) / Math.max(1, totalMass)).toFixed(3));
    var potentialDepth = Number((- (massA + massB) / Math.max(10, L)).toFixed(3));

    // 空间引力求值器 evaluateAt
    function evaluateAt(targetPt) {
      if (!isValidPoint(targetPt)) {
        return {
          force: makeDuckVector3(0, 0, 0),
          potential: 0,
          fieldStrength: 0,
          direction: makeDuckVector3(0, 0, 0)
        };
      }

      var pt = extractPoint(targetPt);
      var softening = 8.0; // 软化因子，防除以零

      var dxA = pt.x - pA.x, dyA = pt.y - pA.y, dzA = pt.z - pA.z;
      var distA = Math.sqrt(dxA * dxA + dyA * dyA + dzA * dzA + softening * softening);

      var dxB = pt.x - pB.x, dyB = pt.y - pB.y, dzB = pt.z - pB.z;
      var distB = Math.sqrt(dxB * dxB + dyB * dyB + dzB * dzB + softening * softening);

      var pot = - (massA / distA + massB / distB);

      var fA = massA / (distA * distA * distA);
      var fB = massB / (distB * distB * distB);

      var fx = - (fA * dxA + fB * dxB);
      var fy = - (fA * dyA + fB * dyB);
      var fz = - (fA * dzA + fB * dzB);

      var fMag = Math.sqrt(fx * fx + fy * fy + fz * fz);
      var dirX = fMag > 0.0001 ? fx / fMag : 0;
      var dirY = fMag > 0.0001 ? fy / fMag : 0;
      var dirZ = fMag > 0.0001 ? fz / fMag : 0;

      return {
        force: makeDuckVector3(Number(fx.toFixed(3)), Number(fy.toFixed(3)), Number(fz.toFixed(3))),
        potential: Number(pot.toFixed(3)),
        fieldStrength: Number(fMag.toFixed(3)),
        direction: makeDuckVector3(Number(dirX.toFixed(3)), Number(dirY.toFixed(3)), Number(dirZ.toFixed(3)))
      };
    }

    return {
      barycenter: barycenter,
      lagrangeL1: lagrangeL1,
      fieldRadius: fieldRadius,
      dipolePower: dipolePower,
      potentialDepth: potentialDepth,
      massA: massA,
      massB: massB,
      evaluateAt: evaluateAt
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 4. createResonanceField(ptA, ptB, time, opt): 晶冠秒跳相干共振
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 与 3D 晶冠整秒跳动 (tick) 完全同拍的微观呼吸共振状态计算器（契约 C5）。
   * 
   * @param {Object} ptA 顶点 A 坐标
   * @param {Object} ptB 顶点 B 坐标
   * @param {number} [time=0] 当前时间戳
   * @param {Object} [opt={}] 扩展参数
   * @returns {Object|null} 锁定环与光能共振指标
   */
  function createResonanceField(ptA, ptB, time, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);
    var t = (typeof time === 'number' && !isNaN(time) && isFinite(time)) ? time : 0;
    var options = (opt && typeof opt === 'object') ? opt : {};

    var tickFrac = (typeof options.tickFrac === 'number') ? clamp(options.tickFrac, 0, 1) : (t % 1);
    var pulse = Math.exp(-tickFrac * 4.5);
    var coherence = (typeof options.coherence === 'number') ? clamp(options.coherence, 0.5, 1) : 0.95;

    // 顶点准星锁定环瞬时激发尺度
    var ringA = {
      scale: Number((1.0 + 0.35 * pulse).toFixed(3)),
      opacity: Number((0.65 + 0.35 * pulse).toFixed(3)),
      glow: Number((6.0 + 10.0 * pulse).toFixed(2)),
      reticleRadius: Number((7.0 + 2.5 * pulse).toFixed(2))
    };

    var ringB = {
      scale: Number((1.0 + 0.30 * pulse).toFixed(3)),
      opacity: Number((0.60 + 0.35 * pulse).toFixed(3)),
      glow: Number((5.5 + 9.5 * pulse).toFixed(2)),
      reticleRadius: Number((6.5 + 2.2 * pulse).toFixed(2))
    };

    // 驻波节点与波腹位置
    var nodeMid = {
      x: Number(((pA.x + pB.x) * 0.5).toFixed(2)),
      y: Number(((pA.y + pB.y) * 0.5).toFixed(2)),
      z: Number(((pA.z + pB.z) * 0.5).toFixed(2))
    };

    return {
      ringA: ringA,
      ringB: ringB,
      nodeMid: nodeMid,
      tickPulse: Number(pulse.toFixed(3)),
      coherence: coherence,
      intensity: Number((0.70 + 0.30 * pulse).toFixed(3)),
      breath: Number((1.0 + 0.08 * Math.sin(t * 2.62)).toFixed(3))
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 5. renderSVGBeam(ptA, ptB, time, opt): 全息导轨 SVG 结构化标记生成
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 生成可直接挂载到全息悬浮卡导轨层 (cl-leads) 的 SVG 完整代码片段与元数据。
   * 严格遵守契约令牌规范：颜色使用 var(--abyss-*, ...)，零裸色值。
   * 
   * @param {Object} ptA 起点顶点坐标
   * @param {Object} ptB 终点顶点坐标
   * @param {number} [time=0] 时间戳
   * @param {Object} [opt={}] 样式与配置参数
   * @returns {Object} 结构化 SVG 结果包及 .svgHTML 标记
   */
  function renderSVGBeam(ptA, ptB, time, opt) {
    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) {
      return {
        svgHTML: '',
        curve: null,
        id: '',
        pathD: '',
        toString: function () { return ''; }
      };
    }

    var options = (opt && typeof opt === 'object') ? opt : {};
    var theme = options.theme || 'mint';
    var beamColor = THEME_TOKENS[theme] || THEME_TOKENS.mint;
    var beamId = options.id || ('cl-beam-' + Math.floor(Math.random() * 100000));
    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var partsHTML = [];
    for (var i = 0; i < curve.particles.length; i++) {
      var p = curve.particles[i];
      partsHTML.push(
        '<circle class="cl-synergy-particle" cx="' + p.x + '" cy="' + p.y + '" r="' + p.size + '" ' +
        'fill="var(--abyss-ink-bright, #ffffff)" opacity="' + p.alpha + '" ' +
        'style="filter:drop-shadow(0 0 4px ' + beamColor + ');vector-effect:non-scaling-stroke;" />'
      );
    }

    var lockRadiusA = (6.5 * curve.resonance.intensity).toFixed(1);
    var lockRadiusB = (6.5 * curve.resonance.intensity).toFixed(1);

    var svgHTML = [
      '<g class="cl-synergy-beam" id="' + beamId + '" data-theme="' + theme + '" style="opacity:0.96;">',
      '  <!-- 霓虹外层泛光导轨 (Halo) -->',
      '  <path class="cl-synergy-glow" d="' + curve.svgPath + '" fill="none" stroke="' + beamColor + '" ' +
         'stroke-width="var(--abyss-sp-sm, 6px)" stroke-linecap="round" opacity="' + (0.32 * curve.resonance.intensity).toFixed(3) + '" ' +
         'style="filter:drop-shadow(0 0 8px ' + beamColor + ');vector-effect:non-scaling-stroke;" />',
      '  <!-- 高能光核导轨 (Laser Core) -->',
      '  <path class="cl-synergy-core" d="' + curve.svgPath + '" fill="none" stroke="var(--abyss-ink-bright, #ffffff)" ' +
         'stroke-width="var(--abyss-sp-2xs, 2px)" stroke-linecap="round" opacity="0.94" ' +
         'style="filter:drop-shadow(0 0 3px var(--abyss-ink-bright, #ffffff));vector-effect:non-scaling-stroke;" />',
      '  <!-- 光子能量流动包 (Travelling Photons) -->',
      '  ' + partsHTML.join('\n  '),
      '  <!-- 晶冠顶点战术锁定环 A -->',
      '  <circle class="cl-synergy-lock cl-synergy-lock-a" cx="' + pA.x.toFixed(1) + '" cy="' + pA.y.toFixed(1) + '" r="' + lockRadiusA + '" ' +
         'fill="none" stroke="' + beamColor + '" stroke-width="1.2" style="filter:drop-shadow(0 0 5px ' + beamColor + ');" />',
      '  <!-- 晶冠顶点战术锁定环 B -->',
      '  <circle class="cl-synergy-lock cl-synergy-lock-b" cx="' + pB.x.toFixed(1) + '" cy="' + pB.y.toFixed(1) + '" r="' + lockRadiusB + '" ' +
         'fill="none" stroke="' + beamColor + '" stroke-width="1.2" style="filter:drop-shadow(0 0 5px ' + beamColor + ');" />',
      '</g>'
    ].join('\n');

    return {
      id: beamId,
      svgHTML: svgHTML,
      curve: curve,
      pathD: curve.svgPath,
      toString: function () { return svgHTML; }
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 6. updateSVGBeamElement: 60 FPS 就地属性极速更新器
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 极速无垃圾回收的 DOM 属性更新器。针对现有 SVG <g> 容器复用子图元进行纯属性改写。
   * 
   * @param {SVGElement} groupEl 已有 SVG <g> 容器节点
   * @param {Object} ptA 顶点 A 坐标
   * @param {Object} ptB 顶点 B 坐标
   * @param {number} [time=0] 时间戳
   * @param {Object} [opt={}] 配置参数
   * @returns {Object|null} 曲线点集计算结果
   */
  function updateSVGBeamElement(groupEl, ptA, ptB, time, opt) {
    if (!groupEl || typeof groupEl.setAttribute !== 'function') return null;

    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) {
      groupEl.style.display = 'none';
      return null;
    }

    groupEl.style.display = '';

    // 就地更新 glow 与 core path
    var glowPath = groupEl.querySelector('.cl-synergy-glow');
    if (glowPath) {
      glowPath.setAttribute('d', curve.svgPath);
      glowPath.setAttribute('opacity', (0.32 * curve.resonance.intensity).toFixed(3));
    }

    var corePath = groupEl.querySelector('.cl-synergy-core');
    if (corePath) {
      corePath.setAttribute('d', curve.svgPath);
    }

    // 就地更新粒子 circle
    var particleEls = groupEl.querySelectorAll('.cl-synergy-particle');
    for (var i = 0; i < particleEls.length; i++) {
      var pData = curve.particles[i];
      if (pData) {
        particleEls[i].setAttribute('cx', pData.x);
        particleEls[i].setAttribute('cy', pData.y);
        particleEls[i].setAttribute('r', pData.size);
        particleEls[i].setAttribute('opacity', pData.alpha);
      }
    }

    // 就地更新端点锁定环
    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var lockA = groupEl.querySelector('.cl-synergy-lock-a');
    if (lockA) {
      lockA.setAttribute('cx', pA.x.toFixed(1));
      lockA.setAttribute('cy', pA.y.toFixed(1));
      lockA.setAttribute('r', (6.5 * curve.resonance.intensity).toFixed(1));
    }

    var lockB = groupEl.querySelector('.cl-synergy-lock-b');
    if (lockB) {
      lockB.setAttribute('cx', pB.x.toFixed(1));
      lockB.setAttribute('cy', pB.y.toFixed(1));
      lockB.setAttribute('r', (6.5 * curve.resonance.intensity).toFixed(1));
    }

    return curve;
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 7. createSynergy3DGeometry: Three.js 3D 能量导轨几何体生成器
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 生成供 Three.js 使用的 3D 线段顶点与渐变颜色缓冲区。
   * 若全局存在 THREE.BufferGeometry，则直接包装为几何体；无 THREE 时安全输出纯 Float32Array。
   * 
   * @param {Object} ptA 顶点 A 坐标
   * @param {Object} ptB 顶点 B 坐标
   * @param {number} [time=0] 时间戳
   * @param {Object} [opt={}] 配置参数
   * @returns {Object|null} 3D 几何体与点集数据
   */
  function createSynergy3DGeometry(ptA, ptB, time, opt) {
    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) return null;

    var nPoints = curve.points.length;
    var colors = new Float32Array(nPoints * 3);

    // 颜色渐变：端点采用主题色，中段高光热点偏白
    var options = (opt && typeof opt === 'object') ? opt : {};
    var theme = options.theme || 'mint';
    var baseHex = THEME_COLORS[theme] || THEME_COLORS.mint;

    var r = parseInt(baseHex.slice(1, 3), 16) / 255;
    var g = parseInt(baseHex.slice(3, 5), 16) / 255;
    var b = parseInt(baseHex.slice(5, 7), 16) / 255;

    for (var i = 0; i < nPoints; i++) {
      var u = i / (nPoints - 1);
      var peak = Math.sin(Math.PI * u); // 中段热点增强

      colors[i * 3] = clamp(r + peak * (1.0 - r) * 0.75, 0, 1);
      colors[i * 3 + 1] = clamp(g + peak * (1.0 - g) * 0.75, 0, 1);
      colors[i * 3 + 2] = clamp(b + peak * (1.0 - b) * 0.75, 0, 1);
    }

    var geom = null;
    var T = (typeof window !== 'undefined' && window.THREE) ? window.THREE : (typeof root !== 'undefined' && root.THREE) ? root.THREE : null;

    if (T && typeof T.BufferGeometry === 'function') {
      try {
        geom = new T.BufferGeometry();
        geom.setAttribute('position', new T.BufferAttribute(curve.positions, 3));
        geom.setAttribute('color', new T.BufferAttribute(colors, 3));
      } catch (err) {
        geom = null;
      }
    }

    return {
      geometry: geom,
      positions: curve.positions,
      colors: colors,
      count: nPoints,
      curve: curve
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 8. getPairDefinition(keyA, keyB): 权威协同字典查询
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * 查询任意两个维度的协同原型定义
   * 
   * @param {string} keyA 维度 1
   * @param {string} keyB 维度 2
   * @returns {Object} 原型描述对象
   */
  function getPairDefinition(keyA, keyB) {
    if (!keyA || !keyB) {
      return {
        name: '未知协同',
        tagline: '未定之弦，静候启明。',
        synergy: '属性矩阵尚待校准，双核特征暂未显化。',
        theme: 'mint'
      };
    }

    var p1 = keyA + '_' + keyB;
    var p2 = keyB + '_' + keyA;
    return TOP_PAIRS[p1] || TOP_PAIRS[p2] || {
      name: keyA + keyB + '先驱',
      tagline: keyA + '与' + keyB + '双核驱动，独树一帜。',
      synergy: keyA + '与' + keyB + '高频共鸣，构筑核心优势。',
      theme: 'mint'
    };
  }

  // 导出接口对象
  return {
    KEYS: KEYS,
    EN: EN,
    THEME_COLORS: THEME_COLORS,
    THEME_TOKENS: THEME_TOKENS,
    TOP_PAIRS: TOP_PAIRS,

    resolveSynergyPair: resolveSynergyPair,
    createSynergyCurve: createSynergyCurve,
    createGravityField: createGravityField,
    createResonanceField: createResonanceField,
    renderSVGBeam: renderSVGBeam,
    updateSVGBeamElement: updateSVGBeamElement,
    createSynergy3DGeometry: createSynergy3DGeometry,
    getPairDefinition: getPairDefinition
  };
});
