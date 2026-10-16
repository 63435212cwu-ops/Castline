(function (g) {
  'use strict';

  var VERSION = 'deep-sky/1';

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

  var GEN = [0xdfb949, 0xf7ac55, 0xff9a8c, 0xe6a0f1, 0xa5b6ff, 0x58d9a8];

  var FAMILY = {
    '主角方': [0xf2cc7a, 0xbbdf91, 0xffb999, 0xd9d67f, 0xffc183],
    '盟友': [0xedc291, 0xc9d195, 0xfbb7af, 0xddca8e, 0xf7bb9d],
    '中立': [0xb8b7f0, 0x8fc5ed, 0xdbacd7, 0xa3bef2, 0xcbb1e7],
    '摇摆': [0xf79e75, 0xf696b3, 0xd6b355, 0xfb9893, 0xeba85e],
    '对立': [0xf56b7c, 0xd972ce, 0xf4714b, 0xeb6ba7, 0xe45a5a],
    '': [0x9d9bb6, 0x8ba1b6, 0xaf96a9, 0x949eb8, 0xa798b1]
  };

  var STANCE_ALIAS = {
    '主角': '主角方', '主角方': '主角方', 'protagonist': '主角方', 'hero': '主角方',
    'lead': '主角方', 'main': '主角方',
    '盟友': '盟友', 'ally': '盟友', 'friend': '盟友', '同伙': '盟友',
    '中立': '中立', 'neutral': '中立', 'none': '中立',
    '摇摆': '摇摆', 'swing': '摇摆', 'waver': '摇摆', '浮动': '摇摆', '未定': '',
    '对立': '对立', 'oppose': '对立', 'opponent': '对立', 'enemy': '对立',
    'foe': '对立', '敌对': '对立'
  };

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

  var DUR = {
    flick: 0.14, soft: 0.36, focus: 0.9, fly: 1.2,
    dive: 1.1, unfurl: 2.2, ignite: 2.4, migrate: 2.2,
    panel: 0.24,
    nudge: 0.12, press: 0.08, pull: 0.52, regroup: 0.72,
    structure: 0.72, structureBack: 0.52, structureEnv: 0.16, structureFace: 0.40, structureLegend: 0.60, participants: 0.60, participantStagger: 0.04
  };

  var LOOP = { sweep: 40, breath: 24, drift: 90, tour: 60 };

  var ALPHA = {
    structureKeep: 0.20,
    nebula: 0.18, nebulaDim: 0.08, bundleBase: 0.07, bundleOn: 0.3,
    bundleOff: 0.05, litDim: 0.18, wedge: 0.16, wake: 0.2,
    readFar: 0.55
  };

  var BLUR = { backdrop: 11, none: 0 };

  var LAYER5 = {
    hero: { level: 0, alpha: 1.0, px: 22 },
    camp: { level: 1, alpha: 0.42, px: 0 },
    bundle: { level: 2, alpha: 0.3, px: 0 },
    star: { level: 3, alpha: 0.62, px: 6 },
    label: { level: 4, alpha: 0.78, px: 0 },
    deep: { level: 5, alpha: 0.26, px: 3 }
  };
  var LAYER5_ORDER = ['hero', 'camp', 'bundle', 'star', 'label', 'deep'];

  var DNA_KEYS = ['layerBands', 'lobe', 'fray', 'cut', 'bandThick', 'bandTilt', 'avoidDeg', 'dustN', 'period', 'halo', 'nodeHalo'];
  var DNA_LIMITS = {
    halo: [0.96, 1.4], nodeHalo: [0.86, 1.22], fray: [0.05, 0.7], cut: [0.24, 0.72],
    lobe: [0.95, 1.7], bandThick: [0.04, 0.19], bandTilt: [6, 38], avoidDeg: [24, 28],
    dustN: [700, 3000], period: [1600, 3400]
  };

  var ORRERY_UI = { occludeKeep: 0.16 };
  var DISC_WEDGE = { r0: 0.87, midR: 0.3, midA: 0.16, outerA: 0.62, longSpan: 2.3, tip: 0.5 };
  var DISC_THREADS = { cap: { high: 8, mid: 6, low: 2 }, segments: 20, halfPx: 3.2, lowHalfPx: 1.5, endpointPx: 7, alpha: 0.55, glow: 0.35, speed: 0.34 };

  var TIER = {
    high: { nebulaRT: 1024, fbm: 5, beads: 1, spikes: 1 },
    mid: { nebulaRT: 256, fbm: 3, beads: 1, spikes: 1 },
    low: { nebulaRT: 128, fbm: 0, beads: 0, spikes: 0 }
  };

  var VOL = { slices: { high: 24, mid: 14, low: 0 }, thick: 0.55, step: 0.055, jitter: 0.12 };

  var CARD3D = { tilt: 3.2 };

  var SPRING = { follow: { w: 30, z: 1 }, pull: { w: 11, z: 0.62 }, back: { w: 11, z: 0.38 }, dial: { w: 16, z: 0.55 }, sat: { w: 12, z: 0.36 } };

  var TUG = { maxR: 0.42, lift: 0.05, rep: 0.11, n1: 28, n2: 36, hitPx: [7, 18], slopPx: { mouse: 4, touch: 9 }, longPressMs: 550 };

  var OPEN = {
    rain: { cols: 44, near: 0.34, far: 0.16, len: [10, 26], dur: [1.6, 3.4], every: 1.1 },
    type: { cps: 12.5, log: 70, glint: 0.9, blinks: 6 },
    sweep: { lattice: [0.25, 1.35], threads: [0.55, 1.85], solid: [1.15, 2.3], flare: 1.75, flareDur: 1.1 },
    comet: { pass: 1.8, tail: 0.22 },
    hold: { boot: 0.9, swap: 0.35 },
    bead: { max: 3, speed: 0.34, gap: [2.6, 6] }
  };

  var METEOR = { gap: [20, 45], dur: [0.95, 1.35], settle: 5, retry: 1.5, len: [0.13, 0.21], tailRatio: 0.42, tilt: [18, 64], alpha: 0.9,
    px: { core: 0.5, halo: 2.4, head: 1.2, ring: 18, edge: 24 }, headColor: C.STAR_WHITE, tailColor: C.STAR_COOL };

  var SAT = { drag: 0.007, cap: 6, step: 1 / 240, yieldPx: 22, yieldR: 130, taut: 0.8, lift: 1.35, suck: 0.42, spin: 0.9 };

  var FAN = { pitch: 16, rise: 16, rows: 6, chars: 8, pad: 3, quick: 0.25 };

  var LAYER_DISC = 3;

  var dna = null;

  var layer5 = null;

  function clampNum(v, lo, hi, dflt) {
    var n = +v;
    if (!isFinite(n)) { return dflt; }
    return n < lo ? lo : n > hi ? hi : n;
  }

  function applyDNA(src) {
    if (!src || typeof src !== 'object') { dna = null; layer5 = null; return null; }
    var out = { version: String(src.version || ''), book: String(src.book || ''), fields: {}, clamped: [] };
    var i, k, v, lim;
    for (i = 0; i < DNA_KEYS.length; i++) {
      k = DNA_KEYS[i];
      lim = DNA_LIMITS[k];
      v = src[k];
      if (v === null || v === undefined || v === '' || typeof v === 'boolean' || !isFinite(+v)) {
        out.fields[k] = null; out.clamped.push(k); continue;
      }
      v = +v;
      if (v <= 0) { out.fields[k] = 0; if (src[k] !== 0) { out.clamped.push(k); } continue; }
      if (lim && v !== clampNum(v, lim[0], lim[1], v)) { out.clamped.push(k); }
      out.fields[k] = lim ? clampNum(v, lim[0], lim[1], v) : v;
    }
    var bands = Math.round(clampNum(src.layerBands, 1, 3, 1));
    if (bands !== Math.round(+src.layerBands)) { if (out.clamped.indexOf('layerBands') < 0) { out.clamped.push('layerBands'); } }
    out.fields.layerBands = bands;
    dna = out;
    layer5 = buildLayer5(out);
    return snapshot();
  }

  function buildLayer5(d) {
    var f = (d && d.fields) || {};
    var focal = clampNum(f.halo, DNA_LIMITS.halo[0], DNA_LIMITS.halo[1], 1);
    var starK = clampNum(f.nodeHalo, DNA_LIMITS.nodeHalo[0], DNA_LIMITS.nodeHalo[1], 1);
    var out = {}, i, k, base;
    for (i = 0; i < LAYER5_ORDER.length; i++) {
      k = LAYER5_ORDER[i]; base = LAYER5[k];
      out[k] = { level: base.level, alpha: base.alpha, px: base.px, key: k };
    }
    out.deep.alpha = round3(LAYER5.deep.alpha * clampNum(1 - (f.bandThick || 0) * 1.1, 0.5, 1, 1));
    out.hero.alpha = round3(Math.min(LAYER5.hero.alpha, LAYER5.hero.alpha * (0.94 + 0.06 * focal)));
    out.hero.px = Math.round(LAYER5.hero.px * clampNum(focal, 1, 1.22, 1));
    out.star.alpha = round3(Math.min(LAYER5.star.alpha, LAYER5.star.alpha * starK));
    out.star.px = Math.round(LAYER5.star.px * clampNum(starK, 0.85, 1.15, 1));
    if (out.deep.alpha * 2 > out.star.alpha) { out.deep.alpha = round3(out.star.alpha * 0.5); }
    for (i = 1; i < LAYER5_ORDER.length; i++) {
      if (out[LAYER5_ORDER[i]].alpha > out.hero.alpha) { out[LAYER5_ORDER[i]].alpha = out.hero.alpha; }
    }
    return out;
  }

  function round3(v) { return Math.round(v * 1000) / 1000; }

  function layer5Of() { return layer5; }

  function snapshot() {
    if (!dna) { return null; }
    var f = {}, k;
    for (k in dna.fields) { if (dna.fields.hasOwnProperty(k)) { f[k] = dna.fields[k]; } }
    return { version: dna.version, book: dna.book, fields: f, clamped: dna.clamped.slice(0) };
  }

  function dnaNum(key, dflt) {
    if (dna && dna.fields && typeof dna.fields[key] === 'number' && isFinite(dna.fields[key])) { return dna.fields[key]; }
    return dflt;
  }

  function hasDNA() { return !!dna; }

  function dnaBands(tier, want) {
    var w = Math.round(clampNum(want, 1, 3, 1));
    if (tier === 'low') { return 1; }
    if (tier === 'mid' && w > 2) { return 2; }
    return w;
  }

  function clamp01(t) {
    t = +t;
    if (!(t > 0)) { return 0; }
    return t > 1 ? 1 : t;
  }

  function easeOut(t) {
    var u = 1 - clamp01(t);
    return 1 - u * u * u * u;
  }

  function easeInOut(t) {
    t = clamp01(t);
    return t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2;
  }

  function easeLens(t) {
    var u = 1 - clamp01(t);
    return 1 - u * u * u;
  }

  function easeBack(t) {
    t = clamp01(t);
    var c = 1.2;
    var k = t - 1;
    return 1 + (c + 1) * k * k * k + c * k * k;
  }

  var EASE = { out: easeOut, inOut: easeInOut, lens: easeLens, back: easeBack };

  var reducedMql = null, reducedFn = null, reducedSys = false;
  function reduced() {
    try {
      if (g.matchMedia && g.matchMedia !== reducedFn) {
        reducedFn = g.matchMedia;
        reducedMql = g.matchMedia('(prefers-reduced-motion: reduce)');
        reducedSys = !!(reducedMql && reducedMql.matches);
        if (reducedMql && reducedMql.addEventListener) reducedMql.addEventListener('change', function (e) { reducedSys = !!e.matches; });
        else if (reducedMql && reducedMql.addListener) reducedMql.addListener(function (e) { reducedSys = !!e.matches; });
      }
      return reducedSys || !!(g.document && g.document.body && g.document.body.classList.contains('skylab-still'));
    } catch (e) {
      return false;
    }
  }

  function groupHex(stance, k) {
    var s = String(stance == null ? '' : stance).replace(/^\s+|\s+$/g, '').toLowerCase();
    var list = FAMILY[STANCE_ALIAS[s] || ''] || FAMILY[''];
    var i = Math.floor(Math.abs(+k));
    if (!isFinite(i)) { i = 0; }
    return list[i % 5];
  }

  function relRec(id) {
    var k = String(id == null ? '' : id).replace(/^\s+|\s+$/g, '').toLowerCase();
    return REL[k] || REL.other;
  }

  function relHex(id) {
    return relRec(id).hex;
  }

  function relDash(id) {
    return relRec(id).dash;
  }

  function hexCss(n) {
    return '#' + ('000000' + (n >>> 0).toString(16)).slice(-6);
  }

  function mix(a, b, t) {
    t = clamp01(t);
    var ar = (a >>> 16) & 255, ag = (a >>> 8) & 255, ab = a & 255;
    var br = (b >>> 16) & 255, bg = (b >>> 8) & 255, bb = b & 255;
    var r = Math.round(ar + (br - ar) * t);
    var gg = Math.round(ag + (bg - ag) * t);
    var bl = Math.round(ab + (bb - ab) * t);
    return (r << 16) | (gg << 8) | bl;
  }

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
    DISC_WEDGE: DISC_WEDGE,
    ORRERY_UI: ORRERY_UI,
    VOL: VOL,
    CARD3D: CARD3D,
    LAYER5: LAYER5,
    LAYER5_ORDER: LAYER5_ORDER,
    DNA_KEYS: DNA_KEYS,
    DNA_LIMITS: DNA_LIMITS,
    applyDNA: applyDNA,
    dna: snapshot,
    dnaNum: dnaNum,
    dnaBands: dnaBands,
    hasDNA: hasDNA,
    layer5: layer5Of,
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
