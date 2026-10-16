(function (global) {
  'use strict';

  var VERSION = '47';

  var MAIN_FALLBACK = [0xffb45c, 0x3fd6a8, 0x8a6cd8, 0xc84dff, 0xfff1da];
  var KIND_FALLBACK = 0xc9b8ff;

  function palette() {
    return (global && global.CLPalette) ? global.CLPalette : null;
  }

  /* ================= 一、色组（COLOR） =================
   * 用途：盘面全部色彩的取色入口；禁止在 layer/geom 里裸写 hex。
   */
  var COLOR = {
    main: function (i) {
      var p = palette();
      var n = (i | 0);
      if (n < 0) n = 0;
      if (p && typeof p.mainColor === 'function') {
        return p.mainColor(n % MAIN_FALLBACK.length);
      }
      return MAIN_FALLBACK[n % MAIN_FALLBACK.length];
    },
    kind: function (k) {
      var p = palette();
      if (p && typeof p.hex === 'function') {
        var v = p.hex(k, KIND_FALLBACK);
        return (typeof v === 'number') ? v : KIND_FALLBACK;
      }
      return KIND_FALLBACK;
    },
    line: function (id, fallbackColor) {
      if (typeof fallbackColor === 'number') return fallbackColor;
      return COLOR.main(typeof id === 'number' ? id : 0);
    },
    MERIDIAN: 0x8d84a8,
    HALO: 0xfff1da,
    PENDING: 0x8d84a8,
    FORK: 0xa898d8,
    DIM: 0.44
  };

  /* ================= 二、尺寸组（SIZE，单位：R 倍数或像素） =================
   * R = rimR（半径基准）；*_PX 为屏幕像素常量，单位无关 DPR 由 layer 处理。
   * 圆角 RADIUS_* / 阴影 SHADOW_* / 字阶 TYPE_* / 缓动 EASE_*：n/a-group（见头注）。
   */
  var SIZE = {
    LANE0: 0.965,
    LANE_BASE: 0.905,
    LANE_STEP: 0.062,
    LANE_MIN: 0.45,
    BAND_W: 0.012,
    ARC_W: 0.0098,
    TENDRIL_W0: 0.0016,
    TENDRIL_W1: 0.008,
    BEAD_PX: 7,
    BEAD_PX_HOT: 12,
    BEAD_W_MIX: 0.55,
    HALO_PX: 26,
    MERIDIAN_W: 0.0022,
    RING_OFF: 0.058,
    SPRITE: 8.0,
    SPREAD: 2.4,
    STEP: 0.014,
    RAIL_W: 0.0022,
    RAIL_OFF: 0.0103,
    BEAD_R: 0.0195,
    GROOVE_W: 0.0016
  };

  /* ================= 三、时间组（TIME，毫秒 / 弧度每秒） =================
   * 缓动时长统一走这里；reduced-motion 下由 motion 置 0（见 tier / reduced 覆盖）。
   */
  var TIME = {
    IDLE_SPIN: 0.02,
    FOCUS_MS: 900,
    HOLD_MS: 3000,
    RESUME_MS: 1200,
    PULSE_CYCLE_MS: 14000,
    PULSE_DECAY_MS: 600,
    FADE_MS: 400,
    FLOW_SPEED: 0.12,
    BREATH_HZ: 0.11
  };

  /* ================= 四、预算组（BUDGET） =================
   * 用于主控验收与 layer 自检；超预算视为失败。
   */
  var BUDGET = {
    DRAWCALLS: 12,
    JS_MS: 1.5,
    LABELS: 8
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
    isLowDevice: function (nav) {
      var n = nav || global.navigator;
      return !!(n && typeof n.hardwareConcurrency === 'number' && n.hardwareConcurrency <= 4);
    }
  };
})(typeof window !== 'undefined' ? window : this);
