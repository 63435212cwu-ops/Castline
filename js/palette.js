/* Castline · palette.js — 七类事件色的唯一真相（window.CLPalette）
 *
 * 为什么单独成文件：这七个色值在本仓里被写死了 **13 个文件、49 处**——
 * scene.js 15 处、plot-tree.js 8 处、tree-shape.js 6 处…… 任何一次「把"冲突"调亮一点」
 * 都得记得改 13 个地方，漏一处就有两条线上的同一个事件长得不一样。过去几十轮的返工
 * 有相当一部分就是漏改造成的。
 *
 * 本文件不给那些文件做「自动改写」（scene.js 有并行会话在改，动它就是丢改动），
 * 只提供两件事：
 *   ① 给**树层**（tree-shape / tree-ghost / tree-leaf / cast-clones）一个可以查的真值；
 *   ② 给验收侧一个**指纹**（fp）—— tests/palette_check.py 拿它去比对每个文件里写死的副本，
 *      任何一处色值与这里不一致就直接失败。「同源」从此是个可计算的数，不是注释里的承诺。
 *
 * ES5 IIFE，无依赖，必须在所有其它 js 之前加载（验收脚本要它最早可用）。
 */
(function () {
  'use strict';

  var KINDS = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
  var HEX = [0xffd166, 0xffb45c, 0xc8a7ff, 0xff5d73, 0xff9ad5, 0x7af0c8, 0x9a92b8];
  var CSS = ['#ffd166', '#ffb45c', '#c8a7ff', '#ff5d73', '#ff9ad5', '#7af0c8', '#9a92b8'];
  /* 阵营色（立场）唯一真相 —— 星渊宪法 C1：星座 = 阵营 · 色相 = 立场。
   * 与事件色刻意在明度通道上错开（阵营恒沉 / 事件恒亮），防止「他是谁」与「发生了什么」误读。
   * 真值在窗口 CLPalette.campHex()；constellation.js / plot-tree.js 的字面量只是回落副本。
   * 对立 0xff5d73 与事件色「冲突」同值 —— 立场对立与事件冲突是同一情感轴，刻意同源。 */
  var CAMPS = ['主角方', '盟友', '中立', '摇摆', '对立', ''];
  var CAMP_HEX = [0xffd27a, 0xf6dfa4, 0xcbbcf0, 0xffa07a, 0xff5d73, 0x8d84a8];
  var CAMP_CSS = ['#ffd27a', '#f6dfa4', '#cbbcf0', '#ffa07a', '#ff5d73', '#8d84a8'];
  /* 语义色（星渊宪法 G1 色板层）—— 全项目 CSS/3D 两侧的共用锚点：
   *   signal 金/琥珀 = 人物与信号 · violet 秘仪紫 = 时间 · mint 薄荷 = 特质 · hot 绯红 = 对立
   *   冥蓝 abyss  = 叙事位置层 / 底面（v17.9 底锥色族的中值）
   * 3D 渲染侧（scene.js TONE）允许按光效取明度变体，但色相必须落在这张表里。 */
  var SEM = {
    signal:   0xffb45c,
    signalHi: 0xffd9a0,
    violet:   0xa688ff,
    violetHi: 0xc9b8ff,
    violetLo: 0x6a4fd6,
    mint:     0x7af0c8,
    mintHi:   0x9af5d2,
    hot:      0xff5d73,
    abyss:    0x5c4d8f,
    abyssLo:  0x2e1580
  };
  /* 深渊灰阶（中性冷紫阶）—— 页面背景 / 文字 / 描边的唯一来源 */
  var GREY = {
    bg:    0x07060d,   // 深渊 0 · 背景
    s1:    0x14121f,   // 深渊 2 · 面板
    s2:    0x1a1728,   // 深渊 3 · 悬浮面
    s3:    0x2c2740,   // 深渊 4 · 描边
    s4:    0x8f86a8,   // 深渊 6 · 次级文字
    s5:    0xbfb8cf,   // 深渊 7 · 主文字弱化
    ink:   0xf4efe6    // 深渊 9 · 主文字
  };
  /* 主干每段色（换手色环）。与 storylines.js 的 MAIN_COLOR 同源：
   * 段与段的接缝必须一眼分得开，所以走色环轮转，而不是「取该段主导类型色」——
   * 后者会让相邻两段撞成同一个黄，换手的视觉证据就没了。 */
  var MAIN = [0xffb45c, 0x3fd6a8, 0x8a6cd8, 0xc84dff, 0xfff1da];

  var MAP = null, CSSMAP = null, MAIMAP = null, CAMPMAP = null, CAMPCSSMAP = null;

  function build() {
    MAP = {}; CSSMAP = {}; MAIMAP = {}; CAMPMAP = {}; CAMPCSSMAP = {};
    var i;
    for (i = 0; i < KINDS.length; i++) { MAP[KINDS[i]] = HEX[i]; CSSMAP[KINDS[i]] = CSS[i]; }
    for (i = 0; i < CAMPS.length; i++) { CAMPMAP[CAMPS[i]] = CAMP_HEX[i]; CAMPCSSMAP[CAMPS[i]] = CAMP_CSS[i]; }
    for (i = 0; i < MAIN.length; i++) MAIMAP['S' + i] = MAIN[i];
  }
  build();

  function idxOf(kind) {
    var k = kind == null ? '' : String(kind);
    for (var i = 0; i < KINDS.length; i++) if (KINDS[i] === k) return i;
    return -1;
  }

  function campIdxOf(camp) {
    var k = camp == null ? '' : String(camp);
    for (var i = 0; i < CAMPS.length; i++) if (CAMPS[i] === k) return i;
    return -1;
  }

  /** djb2 幂等哈希。取 >>> 0 保证跨平台是无符号 32 位，验收侧用 Python 复算同一个值。 */
  function djb2(str) {
    var h = 5381, i;
    for (i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) >>> 0;
    return h >>> 0;
  }
  /** 色板指纹：七色按 KINDS 顺序转成 6 位小写 hex 再拼接。改任何一个色值都会改指纹。 */
  function fp() {
    var out = [], i, v;
    for (i = 0; i < HEX.length; i++) {
      v = HEX[i].toString(16);
      while (v.length < 6) v = '0' + v;
      out.push(v);
    }
    return djb2(out.join(',')).toString(16);
  }

  var API = {
    name: 'palette',
    KINDS: KINDS,
    HEX: HEX,
    CSS: CSS,
    MAIN: MAIN,
    CAMPS: CAMPS,
    CAMP_HEX: CAMP_HEX,
    CAMP_CSS: CAMP_CSS,
    SEM: SEM,
    GREY: GREY,
    map: function () { return MAP; },
    cssMap: function () { return CSSMAP; },
    /** hex('冲突') → 0xff5d73；未知 kind 返回 dflt（默认取「日常」灰紫，绝不返回 undefined 上色变黑） */
    hex: function (kind, dflt) {
      var i = idxOf(kind);
      return i >= 0 ? HEX[i] : (dflt === undefined ? HEX[6] : dflt);
    },
    css: function (kind, dflt) {
      var i = idxOf(kind);
      return i >= 0 ? CSS[i] : (dflt === undefined ? CSS[6] : dflt);
    },
    /** campHex('主角方') → 0xffd27a；未知阵营回落「散星」灰，绝不 undefined 上色变黑 */
    campMap: function () { return CAMPMAP; },
    campCssMap: function () { return CAMPCSSMAP; },
    campHex: function (camp, dflt) {
      var i = campIdxOf(camp);
      return i >= 0 ? CAMP_HEX[i] : (dflt === undefined ? CAMP_HEX[5] : dflt);
    },
    campCss: function (camp, dflt) {
      var i = campIdxOf(camp);
      return i >= 0 ? CAMP_CSS[i] : (dflt === undefined ? CAMP_CSS[5] : dflt);
    },
    idx: idxOf,
    mainColor: function (i) { return MAIN[((i | 0) % MAIN.length + MAIN.length) % MAIN.length]; },
    fp: fp,
    /** 探针：验收侧一次拿全（表 + CSS + 主干环 + 阵营表 + 指纹） */
    audit: function () {
      return { kinds: KINDS.slice(), hex: HEX.slice(), css: CSS.slice(), main: MAIN.slice(), fp: fp(),
        camps: CAMPS.slice(), campHex: CAMP_HEX.slice(), campCss: CAMP_CSS.slice(),
        count: KINDS.length, mainCount: MAIN.length };
    }
  };

  window.CLPalette = API;
  // 本文件不注册 arcana 插件：它没有逐帧行为，也不需要 build/dispose。
  // 但若 arcana 已在（几乎不可能，它排在很后面），登记的 plugins 列表里也不该有它。
})();
