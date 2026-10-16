(function () {
  'use strict';

  var KINDS = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
  var HEX = [0xffd166, 0xffb45c, 0xc8a7ff, 0xff5d73, 0xff9ad5, 0x7af0c8, 0x9a92b8];
  var CSS = ['#ffd166', '#ffb45c', '#c8a7ff', '#ff5d73', '#ff9ad5', '#7af0c8', '#9a92b8'];
  var CAMPS = ['主角方', '盟友', '中立', '摇摆', '对立', ''];
  var CAMP_HEX = [0xffd27a, 0xf6dfa4, 0xcbbcf0, 0xffa07a, 0xff5d73, 0x8d84a8];
  var CAMP_CSS = ['#ffd27a', '#f6dfa4', '#cbbcf0', '#ffa07a', '#ff5d73', '#8d84a8'];
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
  var GREY = {
    bg:    0x07060d,
    s1:    0x14121f,
    s2:    0x1a1728,
    s3:    0x2c2740,
    s4:    0x8f86a8,
    s5:    0xbfb8cf,
    ink:   0xf4efe6
  };
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

  function djb2(str) {
    var h = 5381, i;
    for (i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) >>> 0;
    return h >>> 0;
  }
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
    hex: function (kind, dflt) {
      var i = idxOf(kind);
      return i >= 0 ? HEX[i] : (dflt === undefined ? HEX[6] : dflt);
    },
    css: function (kind, dflt) {
      var i = idxOf(kind);
      return i >= 0 ? CSS[i] : (dflt === undefined ? CSS[6] : dflt);
    },
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
    audit: function () {
      return { kinds: KINDS.slice(), hex: HEX.slice(), css: CSS.slice(), main: MAIN.slice(), fp: fp(),
        camps: CAMPS.slice(), campHex: CAMP_HEX.slice(), campCss: CAMP_CSS.slice(),
        count: KINDS.length, mainCount: MAIN.length };
    }
  };

  window.CLPalette = API;
})();
