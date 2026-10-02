/*!
 * sky-tokens.js — 深空观星台「光层」令牌唯一真源（其余单元只读，不得覆写）
 * @role tokens
 * @owns js/sky/sky-tokens.js
 * @budget n/a
 * @contract deep-sky/1
 * 约定：本文件是全项目唯一允许出现裸 0xRRGGBB / 秒数 / 缓动实现的地方；
 * 其它 js 与 css 一律按名引用。ES5 经典脚本，无依赖，不注册任何帧回调。
 */
(function (g) {
  'use strict';

  var VERSION = 'deep-sky/1';

  /**
   * 基础色常量（0xRRGGBB 数字）。
   * @type {Object.<string, number>}
   */
  var C = {
    VOID0: 0x010105,
    VOID1: 0x040411,
    VOID2: 0x0b0b1c,
    INK: 0xf2eee6,
    INK2: 0xbdbcca,
    INK3: 0x8b899e,
    BRASS: 0xeac07a,
    BRASS_HOT: 0xffd986,
    BRASS_DIM: 0xa37f4d,
    STAR_WHITE: 0xfff6e8,
    STAR_COOL: 0xcfe0ff,
    GOLD: 0xffd27a,
    OPPOSE: 0xff5d73,
    VIOLET: 0xa688ff,
    MINT: 0x7af0c8
  };

  /**
   * 主线阶段色（6 段，按阶段下标取）。
   * @type {number[]}
   */
  var GEN = [0xdfb949, 0xf7ac55, 0xff9a8c, 0xe6a0f1, 0xa5b6ff, 0x58d9a8];

  /**
   * 立场色族：同立场的第 k 个兄弟组取 [k % 5]，'' 为散星 / 未定。
   * @type {Object.<string, number[]>}
   */
  var FAMILY = {
    '主角方': [0xf2cc7a, 0xbbdf91, 0xffb999, 0xd9d67f, 0xffc183],
    '盟友': [0xedc291, 0xc9d195, 0xfbb7af, 0xddca8e, 0xf7bb9d],
    '中立': [0xb8b7f0, 0x8fc5ed, 0xdbacd7, 0xa3bef2, 0xcbb1e7],
    '摇摆': [0xf79e75, 0xf696b3, 0xd6b355, 0xfb9893, 0xeba85e],
    '对立': [0xf56b7c, 0xd972ce, 0xf4714b, 0xeb6ba7, 0xe45a5a],
    '': [0x9d9bb6, 0x8ba1b6, 0xaf96a9, 0x949eb8, 0xa798b1]
  };

  /* stance 文本 → FAMILY 键。内部用，不导出；未命中一律落 '' 族。 */
  var STANCE_ALIAS = {
    '主角': '主角方', '主角方': '主角方', 'protagonist': '主角方', 'hero': '主角方',
    'lead': '主角方', 'main': '主角方',
    '盟友': '盟友', 'ally': '盟友', 'friend': '盟友', '同伙': '盟友',
    '中立': '中立', 'neutral': '中立', 'none': '中立',
    '摇摆': '摇摆', 'swing': '摇摆', 'waver': '摇摆', '浮动': '摇摆', '未定': '',
    '对立': '对立', 'oppose': '对立', 'opponent': '对立', 'enemy': '对立',
    'foe': '对立', '敌对': '对立'
  };

  /**
   * 关系类色与线型（dash：0 实线 1 虚线 2 点线 3 点划）。
   * @type {Object.<string, {hex: number, dash: number}>}
   */
  /* 深空调色：天球星云 / 银河带 / 尘带是低亮度底色；点星色温与星团、远星系、近景尘 */
  var COSMOS = {
    base: 0x05040f, band: 0x2b2750, bandHot: 0x6a5a86, dust: 0x1a1020, core: 0x8a6a48,
    cloudViolet: 0x3b2a6e, cloudTeal: 0x16505a, cloudRose: 0x5e2748, cloudAmber: 0x5a3a1c,
    starYellow: 0xffe6b8, starOrange: 0xffc48f, starRed: 0xff9f86, galaxy: 0xf6e6d0, mote: 0x9c90c8
  };

  var REL = {
    ally: { hex: 0xffd27a, dash: 0 },
    kin: { hex: 0xffb45c, dash: 3 },
    bond: { hex: 0xffd9a0, dash: 2 },
    oppose: { hex: 0xff5d73, dash: 0 },
    dark: { hex: 0xa688ff, dash: 1 },
    other: { hex: 0x8d84a8, dash: 0 },
    cooccur: { hex: 0x9a8fc4, dash: 2 }
  };

  /**
   * 过渡时长（秒）。
   * @type {Object.<string, number>}
   */
  var DUR = {
    flick: 0.14, soft: 0.36, focus: 0.9, fly: 1.2,
    dive: 1.1, unfurl: 2.2, ignite: 2.4, migrate: 2.2
  };

  /**
   * 循环动画周期（秒）。
   * @type {Object.<string, number>}
   */
  var LOOP = { sweep: 40, breath: 24, drift: 90, tour: 60 };

  /**
   * 不透明度档（0..1）。
   * @type {Object.<string, number>}
   */
  var ALPHA = {
    nebula: 0.18, nebulaDim: 0.08, bundleBase: 0.07, bundleOn: 0.3,
    bundleOff: 0.05, litDim: 0.18, wedge: 0.16, wake: 0.2
  };

  /**
   * 背景虚化档（CSS px）。
   * @type {Object.<string, number>}
   */
  var BLUR = { backdrop: 11, none: 0 };

  /**
   * 档位预算：nebulaRT 为 RT 边长，fbm 为噪声层数，beads/spikes 为 0|1 开关。
   * @type {Object.<string, {nebulaRT: number, fbm: number, beads: number, spikes: number}>}
   */
  /* 参与者光丝：同屏绘制预算，完整名单保留在读层/卡片。 */
  var ORRERY_UI = { occludeKeep: 0.16 };
  var DISC_THREADS = { cap: { high: 8, mid: 6, low: 2 }, segments: 20, halfPx: 3.2, lowHalfPx: 1.5, endpointPx: 7, alpha: 0.55, glow: 0.35, speed: 0.34 };

  var TIER = {
    high: { nebulaRT: 512, fbm: 5, beads: 1, spikes: 1 },
    mid: { nebulaRT: 256, fbm: 3, beads: 1, spikes: 1 },
    low: { nebulaRT: 128, fbm: 0, beads: 0, spikes: 0 }
  };

  /**
   * 体积星云：势力星云从「贴在盘面上的一张平面」改成沿视线步进的发光吸收体积（单张面片，着色器 sky-nebula-glsl.js），
   * 斜视与旋转因此有真视差与厚度。slices = 每档步进数上限（low = 0 → 退回单张平面；画布像素多时 sky-nebula 再按像素量降）。
   * thick 为天球半径 R 的比例（气层总厚上限；0.34 → 0.38 → 0.47：团厚改按 σz 正比后，三书 55° 斜视外廓 ≥ 平面 1.18 倍，V1b）；step 为旧切片几何的层距下限（已不用）；jitter 是沿深度的气体扰动相位跨度。
   * @type {{slices: Object.<string, number>, thick: number, step: number, jitter: number}}
   */
  var VOL = { slices: { high: 24, mid: 14, low: 0 }, thick: 0.47, step: 0.055, jitter: 0.12 };

  /**
   * 卡片叠 3D：tilt = 指针在叠上移动时整叠的最大倾角（度，绕 X / Y 各 ±tilt）。
   * 其余几何量（透视距离 / 每层 Z 步进 / 展开抬起 / 微仰角）是纯观感，直接写在 css/sky-cards-3d.css 的
   * --skc3-persp / --skc3-step / --skc3-lift / --skc3-lean 里，JS 不碰。
   * @type {{tilt: number}}
   */
  var CARD3D = { tilt: 3.2 };

  /**
   * 弹簧（w 角频率 rad/s · z 阻尼比）：跟手临界阻尼、邻居欠阻尼轻晃、松手回弹过冲约 27%、拨盘 / 关系星。
   * @type {Object.<string, {w: number, z: number}>}
   */
  var SPRING = { follow: { w: 30, z: 1 }, pull: { w: 11, z: 0.62 }, back: { w: 11, z: 0.38 }, dial: { w: 16, z: 0.55 }, sat: { w: 12, z: 0.36 } };

  /**
   * 星体牵引（长度以天球半径 R 为单位）：软限位 · 抓起抬升 · 斥力半径 · 一 / 二跳上限 · 抓取半径随星等 · 点击 / 拖动判别。
   */
  var TUG = { maxR: 0.42, lift: 0.05, rep: 0.11, n1: 28, n2: 36, hitPx: [7, 18], slopPx: { mouse: 4, touch: 9 } };

  /**
   * 开篇与数据流（秒 / 像素 / 比例）：字符雨 · 打字 · 揭幕扫掠节拍 · 彗星轨 · 幕的最短停留 · 常驻数据珠。
   */
  var OPEN = {
    rain: { cols: 44, near: 0.34, far: 0.16, len: [10, 26], dur: [1.6, 3.4], every: 1.1 },
    type: { cps: 12.5, log: 70, glint: 0.9, blinks: 6 },
    sweep: { lattice: [0.25, 1.35], threads: [0.55, 1.85], solid: [1.15, 2.3], flare: 1.75, flareDur: 1.1 },   /* 0.25 起扫：读取幕离场的前 0.25 s 还挡着 */
    comet: { pass: 1.8, tail: 0.22 },
    hold: { boot: 0.9, swap: 0.35 },
    bead: { max: 3, speed: 0.34, gap: [2.6, 6] }
  };

  /**
   * 背景流星（sky-meteor · Q9.3，秒 / CSS 像素 / 比例）：星座态的深空远景层上偶尔划过一条发丝细光痕。
   * gap 两条之间（伪随机）· dur 一条划过 · settle 回到星座态后至少静候 · retry 条件不满足时隔多久再试 ·
   * len 轨迹长 / 视口对角线 · tailRatio 尾长 / 轨迹长 · tilt 偏离竖直下落的角（度）· alpha 峰值 ·
   * px：core 芯 σ · halo 辉光衰减长 · head 头 σ · ring 离图谱外接圆的余量 · edge 离屏边 / 界面面板的余量；headColor / tailColor 头尾色。
   */
  var METEOR = { gap: [20, 45], dur: [0.95, 1.35], settle: 5, retry: 1.5, len: [0.13, 0.21], tailRatio: 0.42, tilt: [18, 64], alpha: 0.9,
    px: { core: 0.5, halo: 2.4, head: 1.2, ring: 18, edge: 24 }, headColor: C.STAR_WHITE, tailColor: C.STAR_COOL };

  /**
   * 罗盘关系星拖拽（sky-compass-drag · Q3.1，秒 / CSS 像素）：跟手 SPRING.follow · 让位 SPRING.pull · 松手回弹 SPRING.sat。
   * drag 回弹的速度平方阻力（1/px：大幅拖回时限住过冲，小幅仍是 SPRING.sat 的欠阻尼）· cap 振幅低于它转临界阻尼收尾（≤ 1 s 入轨）·
   * step 积分定步长 · yieldPx / yieldR 其余关系星沿轨道让位的最大位移 / 影响半径 · taut 连线伸长到静长 (1 + taut) 倍为满张力 ·
   * lift 抓起时星点放大 · suck 拖入晶体的吸入时长 · spin 吸入时绕晶体心转过的角（弧度）。
   */
  var SAT = { drag: 0.007, cap: 6, step: 1 / 240, yieldPx: 22, yieldR: 130, taut: 0.8, lift: 1.35, suck: 0.42, spin: 0.9 };

  /**
   * 罗盘关键事件扇出（sky-compass-fan · Q9.4，CSS 像素 / 秒）：pitch 两摞短名的行距 · rise 最低一行离珠的高度下限 ·
   * rows 每侧最多几行 · chars 短名字数上限 · pad 短名互相 / 与障碍的留白 · quick 连续换回（扫带子）时免交错动画的间隔。
   */
  var FAN = { pitch: 16, rise: 16, rows: 6, chars: 8, pad: 3, quick: 0.25 };

  /**
   * 星盘光层所在的 layer 通道号。
   * @type {number}
   */
  var LAYER_DISC = 3;

  /**
   * 夹到 [0,1]，NaN / 负数归 0。
   * @param {number} t
   * @returns {number}
   */
  function clamp01(t) {
    t = +t;
    if (!(t > 0)) { return 0; }
    return t > 1 ? 1 : t;
  }

  /**
   * 四次缓出 1-(1-t)^4。
   * @param {number} t 0..1（内部夹取）
   * @returns {number}
   */
  function easeOut(t) {
    var u = 1 - clamp01(t);
    return 1 - u * u * u * u;
  }

  /**
   * 四次对称缓入缓出。
   * @param {number} t 0..1（内部夹取）
   * @returns {number}
   */
  function easeInOut(t) {
    t = clamp01(t);
    return t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2;
  }

  /**
   * 三次缓出（透镜式），用于收束类过渡。
   * @param {number} t 0..1（内部夹取）
   * @returns {number}
   */
  function easeLens(t) {
    var u = 1 - clamp01(t);
    return 1 - u * u * u;
  }

  /**
   * 轻回弹（峰值 ≈1.06）。
   * @param {number} t 0..1（内部夹取）
   * @returns {number}
   */
  function easeBack(t) {
    t = clamp01(t);
    var c = 1.2;
    var k = t - 1;
    return 1 + (c + 1) * k * k * k + c * k * k;
  }

  /**
   * 缓动集，供 tween 直接取名。
   * @type {Object.<string, function(number): number>}
   */
  var EASE = { out: easeOut, inOut: easeInOut, lens: easeLens, back: easeBack };

  /**
   * 是否处于减弱动效（系统偏好或 skylab-still 类）。
   * @returns {boolean}
   */
  function reduced() {
    try {
      return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) ||
        !!(g.document && g.document.body && g.document.body.classList.contains('skylab-still'));
    } catch (e) {
      return false;
    }
  }

  /**
   * 同立场第 k 个兄弟组的颜色；族不存在落 '' 族。
   * @param {string} stance 立场文本（大小写与首尾空白不敏感）
   * @param {number} k 组序号（非负整数，内部取绝对值后 % 5）
   * @returns {number} 0xRRGGBB
   */
  function groupHex(stance, k) {
    var s = String(stance == null ? '' : stance).replace(/^\s+|\s+$/g, '').toLowerCase();
    var list = FAMILY[STANCE_ALIAS[s] || ''] || FAMILY[''];
    var i = Math.floor(Math.abs(+k));
    if (!isFinite(i)) { i = 0; }
    return list[i % 5];
  }

  /**
   * 关系类记录，未知 id 回落 other。
   * @param {string} id 关系类 id
   * @returns {{hex: number, dash: number}}
   */
  function relRec(id) {
    var k = String(id == null ? '' : id).replace(/^\s+|\s+$/g, '').toLowerCase();
    return REL[k] || REL.other;
  }

  /**
   * 关系类颜色，未知 id 回落 other。
   * @param {string} id 关系类 id
   * @returns {number} 0xRRGGBB
   */
  function relHex(id) {
    return relRec(id).hex;
  }

  /**
   * 关系类线型，未知 id 回落 other（0 实 1 虚 2 点 3 点划）。
   * @param {string} id 关系类 id
   * @returns {number}
   */
  function relDash(id) {
    return relRec(id).dash;
  }

  /**
   * 转 CSS 颜色串，仅供 DOM / CSS-in-JS 用；JS 内部一律用 0x 数字。
   * @param {number} n 0xRRGGBB
   * @returns {string} '#rrggbb'
   */
  function hexCss(n) {
    return '#' + ('000000' + (n >>> 0).toString(16)).slice(-6);
  }

  /**
   * 两色按通道线性插值（t 夹到 [0,1]）。
   * @param {number} a 起始色 0xRRGGBB
   * @param {number} b 目标色 0xRRGGBB
   * @param {number} t 混合比
   * @returns {number} 0xRRGGBB 整数
   */
  function mix(a, b, t) {
    t = clamp01(t);
    var ar = (a >>> 16) & 255, ag = (a >>> 8) & 255, ab = a & 255;
    var br = (b >>> 16) & 255, bg = (b >>> 8) & 255, bb = b & 255;
    var r = Math.round(ar + (br - ar) * t);
    var gg = Math.round(ag + (bg - ag) * t);
    var bl = Math.round(ab + (bb - ab) * t);
    return (r << 16) | (gg << 8) | bl;
  }

  /**
   * 宿主 degrade 值 → 档位名。
   * @param {number} degrade 0 高 / 1 中 / ≥2 低
   * @returns {string} 'high' | 'mid' | 'low'
   */
  function tierOf(degrade) {
    var d = +degrade;
    if (!(d > 0)) { return 'high'; }
    return d >= 2 ? 'low' : 'mid';
  }

  g.CLSkyTokens = {
    version: VERSION,
    C: C,
    GEN: GEN,
    FAMILY: FAMILY,
    COSMOS: COSMOS,
    REL: REL,
    DUR: DUR,
    LOOP: LOOP,
    EASE: EASE,
    ALPHA: ALPHA,
    BLUR: BLUR,
    TIER: TIER,
    DISC_THREADS: DISC_THREADS,
    ORRERY_UI: ORRERY_UI,
    VOL: VOL,
    CARD3D: CARD3D,
    LAYER_DISC: LAYER_DISC,
    SPRING: SPRING,
    TUG: TUG,
    OPEN: OPEN,
    METEOR: METEOR,
    SAT: SAT,
    FAN: FAN,
    reduced: reduced,
    groupHex: groupHex,
    relHex: relHex,
    relDash: relDash,
    hexCss: hexCss,
    mix: mix,
    tierOf: tierOf
  };
})(window);
