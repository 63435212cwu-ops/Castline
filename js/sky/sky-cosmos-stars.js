/* cosmosstars · 深空点星 / 星团 / 远星系 / 近景尘 的纯数据生成器（无 THREE、无 DOM、无动画）
 * @role component
 * @owns js/sky/sky-cosmos-stars.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/2
 */
(function (g) {
  'use strict';

  var STAR_WHITE = 0xfff6e8;
  var STAR_COOL = 0xcfe0ff;
  var COSMOS_STAR_YELLOW = 0xffe6b8;
  var COSMOS_STAR_ORANGE = 0xffc48f;
  var COSMOS_STAR_RED = 0xff9f86;
  var COSMOS_GALAXY = 0xf6e6d0;

  var D2R = Math.PI / 180;
  var TAU = Math.PI * 2;
  var SEP = 25 * D2R;
  var PAL_CUM = [0.18, 0.58, 0.83, 0.96];

  var sc = [0, 0, 0];

  function num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }

  function intv(v, d, lo) { var n = Math.round(num(v, d)); return n < lo ? lo : n; }

  function unit3(v, d) {
    var x = 0, y = 0, z = 0, l;
    if (v && v.length >= 3) { x = num(v[0], 0); y = num(v[1], 0); z = num(v[2], 0); }
    l = Math.sqrt(x * x + y * y + z * z);
    if (l < 1e-6) { x = d[0]; y = d[1]; z = d[2]; l = 1; }
    return [x / l, y / l, z / l];
  }

  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }

  function angle(a, b) {
    var d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    if (d > 1) d = 1; else if (d < -1) d = -1;
    return Math.acos(d);
  }

  function basis(p) {
    var ax = Math.abs(p[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    var e1 = unit3(cross(ax, p), [1, 0, 0]);
    return [e1, cross(p, e1)];
  }

  function mulberry32(seed) {
    var a = seed | 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function gauss(rnd, cache) {
    var u, r, a;
    if (cache.spare !== null) { var s = cache.spare; cache.spare = null; return s; }
    u = rnd();
    if (u <= 1e-12) u = 1e-12;
    r = Math.sqrt(-2 * Math.log(u));
    a = TAU * rnd();
    cache.spare = r * Math.sin(a);
    return r * Math.cos(a);
  }

  function iso(rnd, out) {
    var z = 2 * rnd() - 1, a = TAU * rnd(), r = Math.sqrt(z < -1 ? 0 : (z > 1 ? 0 : 1 - z * z));
    out[0] = r * Math.cos(a); out[1] = r * Math.sin(a); out[2] = z;
    return out;
  }

  var rgb = g.CLSkyUtil.rgb;

  function palette() {
    var tk = g.CLSkyTokens || {}, c = tk.C || {}, x = tk.COSMOS || {};
    return [
      rgb(c.STAR_COOL || STAR_COOL),
      rgb(c.STAR_WHITE || STAR_WHITE),
      rgb(x.starYellow || COSMOS_STAR_YELLOW),
      rgb(x.starOrange || COSMOS_STAR_ORANGE),
      rgb(x.starRed || COSMOS_STAR_RED)
    ];
  }

  function mix(a, b, t, out) {
    out[0] = a[0] + (b[0] - a[0]) * t;
    out[1] = a[1] + (b[1] - a[1]) * t;
    out[2] = a[2] + (b[2] - a[2]) * t;
    return out;
  }

  function placeDir(rnd, avoid, avoidRad, placed) {
    var v = [0, 0, 0], k, ok, t;
    for (t = 0; t < 200; t++) {
      iso(rnd, v);
      if (angle(v, avoid) < avoidRad) continue;
      ok = true;
      for (k = 0; k < placed.length; k++) { if (angle(v, placed[k]) < SEP) { ok = false; break; } }
      if (ok) { placed.push([v[0], v[1], v[2]]); return [v[0], v[1], v[2]]; }
    }
    placed.push([v[0], v[1], v[2]]);
    return [v[0], v[1], v[2]];
  }

  function makeCluster(rnd, kind, avoid, avoidRad, placed) {
    var dir = placeDir(rnd, avoid, avoidRad, placed);
    if (kind === 'globular') {
      return { kind: kind, dir: dir, radius: 0.012 + 0.012 * rnd(), count: 500 + Math.round(400 * rnd()) };
    }
    return { kind: kind, dir: dir, radius: 0.03 + 0.025 * rnd(), count: 25 + Math.round(30 * rnd()) };
  }

  function twinkle(m, rnd) {
    if (m > 0.72 && rnd() < 0.6) return 0.001 + 0.999 * rnd();
    return 0;
  }

  function generate(opts) {
    var o = opts || {};
    var rnd = mulberry32(Math.round(num(o.seed, 1)) | 0);
    var cache = { spare: null };
    var fieldN = intv(o.count, 18000, 0);
    var pole = unit3(o.pole, [0, 0, 1]);
    var avoid = unit3(o.avoid, [0, 0, 1]);
    var avoidRad = num(o.avoidDeg, 40) * D2R;
    var pb = basis(pole), e1 = pb[0], e2 = pb[1];
    var pal = palette(), white = pal[1];
    var placed = [], clusters = [], i, k, p, p3, u, t;

    for (i = 0, k = intv(o.globular, 3, 0); i < k; i++) clusters.push(makeCluster(rnd, 'globular', avoid, avoidRad, placed));
    for (i = 0, k = intv(o.open, 4, 0); i < k; i++) clusters.push(makeCluster(rnd, 'open', avoid, avoidRad, placed));

    var nMem = 0;
    for (i = 0; i < clusters.length; i++) nMem += clusters[i].count;
    var total = fieldN + nMem;

    var dir = new Float32Array(3 * total);
    var mag = new Float32Array(total);
    var col = new Float32Array(3 * total);
    var tw = new Float32Array(total);
    var ranges = { field: [0, fieldN], globular: [], open: [] };
    var tmp = [0, 0, 0], c1 = [0, 0, 0];

    for (i = 0; i < fieldN; i++) {
      p = 3 * i;
      if (rnd() < 0.6) {
        iso(rnd, sc);
      } else {
        var lat = gauss(rnd, cache) * 0.11, ph = TAU * rnd();
        var cl = Math.cos(lat), sl = Math.sin(lat), cf = Math.cos(ph), sf = Math.sin(ph);
        var x = cl * (cf * e1[0] + sf * e2[0]) + sl * pole[0];
        var y = cl * (cf * e1[1] + sf * e2[1]) + sl * pole[1];
        var z = cl * (cf * e1[2] + sf * e2[2]) + sl * pole[2];
        var l = Math.sqrt(x * x + y * y + z * z) || 1;
        sc[0] = x / l; sc[1] = y / l; sc[2] = z / l;
      }
      dir[p] = sc[0]; dir[p + 1] = sc[1]; dir[p + 2] = sc[2];

      var m = Math.pow(rnd(), 3.2);
      mag[i] = m;

      u = rnd();
      var ci = u < PAL_CUM[0] ? 0 : (u < PAL_CUM[1] ? 1 : (u < PAL_CUM[2] ? 2 : (u < PAL_CUM[3] ? 3 : 4)));
      mix(pal[ci], white, rnd() * 0.15, c1);
      col[p] = c1[0]; col[p + 1] = c1[1]; col[p + 2] = c1[2];
      tw[i] = twinkle(m, rnd);
    }

    p = fieldN;
    for (i = 0; i < clusters.length; i++) {
      var c = clusters[i], isG = c.kind === 'globular';
      var cb = basis(c.dir), sig = c.radius / 2.2;
      var a = isG ? pal[2] : pal[0], b = isG ? pal[3] : pal[1];
      var start = p;
      for (k = 0; k < c.count; k++, p++) {
        var kc = isG ? 0.3 + 0.9 * rnd() * rnd() : 1, ox = gauss(rnd, cache) * sig * kc, oy = gauss(rnd, cache) * sig * kc;   /* 球状星团核心更密 */
        var dx = c.dir[0] + ox * cb[0][0] + oy * cb[1][0];
        var dy = c.dir[1] + ox * cb[0][1] + oy * cb[1][1];
        var dz = c.dir[2] + ox * cb[0][2] + oy * cb[1][2];
        var dl = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
        p3 = 3 * p;
        dir[p3] = dx / dl; dir[p3 + 1] = dy / dl; dir[p3 + 2] = dz / dl;
        var mm = isG ? 0.03 + 0.42 * Math.pow(rnd(), 3) : 0.45 + 0.55 * rnd();
        mag[p] = mm;
        mix(a, b, rnd(), c1);
        col[p3] = c1[0]; col[p3 + 1] = c1[1]; col[p3 + 2] = c1[2];
        tw[p] = twinkle(mm, rnd);
      }
      (isG ? ranges.globular : ranges.open).push([start, c.count]);
    }

    var tk = g.CLSkyTokens || {}, xk = tk.COSMOS || {}, ck = tk.C || {};
    var gA = rgb(xk.galaxy || COSMOS_GALAXY), gB = rgb(ck.STAR_COOL || STAR_COOL);
    var galN = intv(o.galaxies, 5, 0), galPlaced = [], galaxies = [];
    for (i = 0; i < galN; i++) {
      var gd = placeDir(rnd, avoid, avoidRad, galPlaced);
      var src = rnd() < 0.5 ? gA : gB;
      galaxies.push({
        dir: gd,
        size: 0.006 + 0.014 * rnd(),
        axis: Math.PI * rnd(),
        tilt: 0.25 + 0.65 * rnd(),
        bright: 0.25 + 0.35 * rnd(),
        col: [src[0], src[1], src[2]]
      });
    }

    var dustN = intv(o.dust, 3000, 0);
    var r0 = num(o.dustR0, 1.6), r1 = num(o.dustR1, 3.2);
    var dpos = new Float32Array(3 * dustN), dmag = new Float32Array(dustN);
    for (i = 0; i < dustN; i++) {
      iso(rnd, sc);
      var rr = r0 + (r1 - r0) * rnd();
      dpos[3 * i] = sc[0] * rr; dpos[3 * i + 1] = sc[1] * rr; dpos[3 * i + 2] = sc[2] * rr;
      dmag[i] = 0.1 + 0.4 * rnd();
    }

    t = total;
    return {
      stars: { n: t, dir: dir, mag: mag, col: col, tw: tw },
      ranges: ranges,
      clusters: clusters,
      galaxies: galaxies,
      dust: { n: dustN, pos: dpos, mag: dmag }
    };
  }

  g.CLSkyCosmosStars = { generate: generate };
})(window);
