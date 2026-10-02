/*!
 * @role css-token
 * @owns js/orbit3d-tokens.js
 * @budget n/a
 * @contract v47
 * CLOrbit3DTokens —— ORBIT-3D 唯一数值来源（颜色 / 尺寸 / 时间 / 预算）
 * 说明：
 *  - 本文件是数值与令牌文件，允许写数值；颜色不裸传给网格，一律经 COLOR 取值。
 *  - 颜色优先取 window.CLPalette；缺失时回落契约 §1 MAIN 五色与 0xc9b8ff。
 *  - 圆角/阴影/字阶/缓动组：星盘为 WebGL 图层，无 DOM 圆角与阴影，
 *    字体由标签层 css/orbit3d.css 引 app.css 令牌承载，故此处只登记命名常量，
 *    不产生新数值（标注 n/a-group）。
 *  - ES5 IIFE，页面 <script> 直载，无 module 语法。
 */
(function (global) {
  'use strict';

  var VERSION = '47';

  /* MAIN 五色回落（契约 §1）；仅当 CLPalette 缺失时使用 */
  var MAIN_FALLBACK = [0xffb45c, 0x3fd6a8, 0x8a6cd8, 0xc84dff, 0xfff1da];
  var KIND_FALLBACK = 0xc9b8ff;

  function palette() {
    return (global && global.CLPalette) ? global.CLPalette : null;
  }

  /* ================= 一、色组（COLOR） =================
   * 用途：盘面全部色彩的取色入口；禁止在 layer/geom 里裸写 hex。
   */
  var COLOR = {
    /* 主线段色：按接棒段序取 CLPalette.mainColor(i)，越界取模 */
    main: function (i) {
      var p = palette();
      var n = (i | 0);
      if (n < 0) n = 0;
      if (p && typeof p.mainColor === 'function') {
        return p.mainColor(n % MAIN_FALLBACK.length);
      }
      return MAIN_FALLBACK[n % MAIN_FALLBACK.length];
    },
    /* 事件类色：按 kind 取 CLPalette.hex(kind)，缺失回落 KIND_FALLBACK */
    kind: function (k) {
      var p = palette();
      if (p && typeof p.hex === 'function') {
        var v = p.hex(k, KIND_FALLBACK);
        return (typeof v === 'number') ? v : KIND_FALLBACK;
      }
      return KIND_FALLBACK;
    },
    /* 线色：storylines 已配好的 thread.color，异常时回落主线色 */
    line: function (id, fallbackColor) {
      if (typeof fallbackColor === 'number') return fallbackColor;
      return COLOR.main(typeof id === 'number' ? id : 0);
    },
    /* 时间起点子午线：极细径向线，低亮 */
    MERIDIAN: 0x8d84a8,
    /* 珠外柔光晕 */
    HALO: 0xfff1da,
    /* 待校对线（anchored / topologyStatus!=='confirmed'）：低亮虚化 */
    PENDING: 0x8d84a8,
    /* 分叉 tendril 起色（自父线带长出的一端） */
    FORK: 0xa898d8,
    /* 非选中元素亮度乘法因子（0..1） */
    DIM: 0.44  /* CRITIQUE-1：0.35 会让选中态整盘消失 */
  };

  /* ================= 二、尺寸组（SIZE，单位：R 倍数或像素） =================
   * R = rimR（半径基准）；*_PX 为屏幕像素常量，单位无关 DPR 由 layer 处理。
   * 圆角 RADIUS_* / 阴影 SHADOW_* / 字阶 TYPE_* / 缓动 EASE_*：n/a-group（见头注）。
   */
  var SIZE = {
    LANE0: 0.965,       /* 主线带中心半径 = R·LANE0 */
    LANE_BASE: 0.905,   /* 支线 1 道中心半径 = R·LANE_BASE */
    LANE_STEP: 0.062,   /* 每加一道内缩 R·LANE_STEP */
    LANE_MIN: 0.45,     /* 车道半径下限 = R·LANE_MIN */
    BAND_W: 0.012,      /* 主线带发光丝带宽 = R·BAND_W */
    ARC_W: 0.0098,      /* 支线弧宽 = R·ARC_W（渲染补偿值：裙边修复后渲染宽度落到 2.7px，设计目标 2.3-2.7px） */
    TENDRIL_W0: 0.0016, /* tendril 起点宽（细）= R·TENDRIL_W0 */
    TENDRIL_W1: 0.008,  /* tendril 末端宽（渐宽）= R·TENDRIL_W1 */
    BEAD_PX: 7,         /* 常规珠点基础像素尺寸 */
    BEAD_PX_HOT: 12,    /* heat 高 / 读遍脉冲命中时珠点尺寸 */
    BEAD_W_MIX: 0.55,   /* 珠径混合比：size ∝ (1-BEAD_W_MIX)+BEAD_W_MIX·w */
    HALO_PX: 26,        /* 珠外柔光晕像素尺寸（无艾里环档仍保留） */
    MERIDIAN_W: 0.0022, /* 子午线宽 = R·MERIDIAN_W */
    RING_OFF: 0.058,    /* 参与者星点绕选中珠的切向散开半径 = R·RING_OFF（CRITIQUE-1） */
    SPRITE: 8.0,        /* 点精灵扩边倍数 */
    SPREAD: 2.4,        /* 初始法向散开比 */
    STEP: 0.014,        /* 弧线采样弧度步进 */
    RAIL_W: 0.0022,     /* 护轨半宽基准 */
    RAIL_OFF: 0.0103,   /* 护轨偏置半径 */
    BEAD_R: 0.0195,     /* 珠半径与 R 之比 */
    GROOVE_W: 0.0016    /* 碟面底槽宽 = R·GROOVE_W */
  };

  /* ================= 三、时间组（TIME，毫秒 / 弧度每秒） =================
   * 缓动时长统一走这里；reduced-motion 下由 motion 置 0（见 tier / reduced 覆盖）。
   */
  var TIME = {
    IDLE_SPIN: 0.02,        /* 闲置自转角速度 rad/s（reduced-motion = 0） */
    FOCUS_MS: 900,          /* 选中：把选中角缓动到 FRONT 的时长 */
    HOLD_MS: 3000,          /* 释放后恢复自转前的停转保持时长 */
    RESUME_MS: 1200,        /* 恢复自转的缓动时长 */
    PULSE_CYCLE_MS: 14000,  /* 读遍脉冲巡游周期 */
    PULSE_DECAY_MS: 600,    /* 经过珠时短暂增亮的衰减时长 */
    FADE_MS: 400,           /* 星座态 <-> 剧情态 淡入淡出时长 */
    FLOW_SPEED: 0.12,       /* 主线带流纹速度（uTime 驱动，随 heat 缩放） */
    BREATH_HZ: 0.11         /* 呼吸包络频率 Hz */
  };

  /* ================= 四、预算组（BUDGET） =================
   * 用于主控验收与 layer 自检；超预算视为失败。
   */
  var BUDGET = {
    DRAWCALLS: 12,  /* 剧情态每帧绘制调用上限 */
    JS_MS: 1.5,     /* 剧情态每帧 JS 耗时上限 */
    LABELS: 8       /* 同时在动的 HTML 标签上限 */
  };

  /* ================= 五、设备档覆盖表（tier） =================
   * t(t) ∈ 'high' | 'mid' | 'low'，其它输入按 'high'。
   * 返回覆盖表：airy=细艾里环，flow=主线流纹，tendrilAnim=tendril 动画；
   * BEAD_PX / HALO_PX 为像素尺寸覆盖；reduced=true 时由 motion 强制停转。
   */
  var TIER = {
    high: { name: 'high', BEAD_PX: 7, HALO_PX: 26, airy: true, flow: true, tendrilAnim: true, spin: true },
    mid:  { name: 'mid',  BEAD_PX: 6, HALO_PX: 26, airy: false, flow: true, tendrilAnim: true, spin: true },
    low:  { name: 'low',  BEAD_PX: 7, HALO_PX: 18, airy: false, flow: false, tendrilAnim: false, spin: true }
  };

  function tier(t) {
    var key = (t === 'mid' || t === 'low') ? t : 'high';
    var src = TIER[key];
    return {
      name: src.name,
      BEAD_PX: src.BEAD_PX,
      HALO_PX: src.HALO_PX,
      airy: src.airy,
      flow: src.flow,
      tendrilAnim: src.tendrilAnim,
      spin: src.spin
    };
  }

  global.CLOrbit3DTokens = {
    version: VERSION,
    COLOR: COLOR,
    SIZE: SIZE,
    TIME: TIME,
    BUDGET: BUDGET,
    tier: tier,
    /* 低端判定开关：契约指定 hardwareConcurrency<=4 视为低端档 */
    isLowDevice: function (nav) {
      var n = nav || global.navigator;
      return !!(n && typeof n.hardwareConcurrency === 'number' && n.hardwareConcurrency <= 4);
    }
  };
})(typeof window !== 'undefined' ? window : this);
