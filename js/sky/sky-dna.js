(function (g) {
  'use strict';

  var VERSION = 'deep-sky/dna/1';

  var ID = 'sha1';

  function digest(str) {
    var h1 = 0x811c9dc5, h2 = 0x01000193, i, c;
    str = String(str == null ? '' : str);
    for (i = 0; i < str.length; i++) {
      c = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 16777619);
      h2 = Math.imul(h2 ^ c, 2246822519);
    }
    return ((h1 >>> 0).toString(16) + (h2 >>> 0).toString(16)).slice(0, 16);
  }

  function num(v) { return (typeof v === 'number' && isFinite(v)) ? v : 0; }
  function arr(v) { return Object.prototype.toString.call(v) === '[object Array]' ? v : []; }
  function clamp(v, lo, hi) { v = num(v); return v < lo ? lo : v > hi ? hi : v; }
  function round(v, n) { var p = Math.pow(10, n || 3); return Math.round(v * p) / p; }

  function census(G) {
    var c = { characters: 0, camps: 0, campSizes: [], relations: 0, events: 0, chapters: 0, castSum: 0, castN: 0, fieldNames: 0 };
    if (!G) { return c; }
    var chars = arr(G.characters), camps = arr(G.camps), events = arr(G.events), rels = arr(G.relations);
    c.characters = chars.length;
    c.relations = rels.length;
    c.events = events.length;
    var i, cp;
    for (i = 0; i < camps.length; i++) {
      cp = camps[i];
      if (!cp || !cp.name) { continue; }
      var m = arr(cp.members);
      if (!m.length) { continue; }
      if (String(cp.stance == null ? '' : cp.stance) === '' && /散星|未归|其他/.test(String(cp.name))) { c.fieldNames += m.length; continue; }
      c.camps++; c.campSizes.push(m.length);
    }
    var seen = {}, k;
    for (i = 0; i < events.length; i++) {
      k = String((events[i] && events[i].chapter) || '');
      if (k && !seen[k]) { seen[k] = 1; c.chapters++; }
    }
    var n;
    for (i = 0; i < events.length; i++) {
      n = arr(events[i] && events[i].characters).length;
      if (n > 0) { c.castN++; c.castSum += n; }
    }
    c.campSizes.sort(function (a, b) { return b - a; });
    return c;
  }

  function hhi(sizes) {
    var t = 0, i;
    for (i = 0; i < sizes.length; i++) { t += sizes[i]; }
    if (!(t > 0) || sizes.length < 2) { return null; }
    var s = 0;
    for (i = 0; i < sizes.length; i++) { var p = sizes[i] / t; s += p * p; }
    var lo = 1 / sizes.length;
    return clamp((s - lo) / Math.max(1e-9, 1 - lo), 0, 1);
  }

  var RANGE = {
    layerBands: [1, 3],
    lobe: [1.0, 1.62],
    fray: [0.10, 0.62],
    cut: [0.30, 0.66],
    bandThick: [0.050, 0.170],
    bandTilt: [8, 34],
    avoidDeg: [24, 28],
    dustN: [900, 2600],
    period: [3000, 1900],
    halo: [1.0, 1.36],
    nodeHalo: [0.9, 1.18]
  };

  function lerpRange(r, t) { t = clamp(t, 0, 1); return r[0] + (r[1] - r[0]) * t; }

  function piece(v, pts) {
    v = num(v);
    if (v <= pts[0][0]) { return pts[0][1]; }
    var i, a, b, t;
    for (i = 1; i < pts.length; i++) {
      if (v <= pts[i][0]) {
        a = pts[i - 1]; b = pts[i]; t = (v - a[0]) / Math.max(1e-9, b[0] - a[0]);
        return a[1] + (b[1] - a[1]) * t;
      }
    }
    return pts[pts.length - 1][1];
  }

  function compute(G, c) {
    var gaps = [];
    var dens = c.characters > 0 ? c.relations / c.characters : null;
    var conc = hhi(c.campSizes);
    if (conc == null) { gaps.push('阵营数 < 2：规模集中度未定，星云角密度陡度取设计下限'); conc = 0; }
    if (dens == null) { gaps.push('人物数为 0：关系密度未定，丝状越界取设计下限'); dens = 0; }
    if (c.chapters < 2) { gaps.push('正文实际章节 < 2：时间跨度未定，运动周期取氛围层中值'); }

    var dN = clamp(dens / 4.5, 0, 1);
    var tN = clamp(Math.log(Math.max(2, c.chapters)) / Math.log(1000), 0, 1);
    var castMean = c.castN ? c.castSum / c.castN : 0;
    var cN = clamp((castMean - 2) / 1.6, 0, 1);
    var kN = clamp(conc / 0.22, 0, 1);

    return {
      layerBands: 1 + Math.round(piece(dens, [[0, 0], [1.2, 0.42], [2.6, 1.0], [4.0, 1.6], [4.6, 2]])),
      lobe: round(lerpRange(RANGE.lobe, kN), 3),
      fray: round(lerpRange(RANGE.fray, dN), 3),
      cut: round(lerpRange(RANGE.cut, kN * 0.35 + dN * 0.65), 3),
      bandThick: round(lerpRange(RANGE.bandThick, tN), 4),
      bandTilt: round(lerpRange(RANGE.bandTilt, cN * 0.5 + dN * 0.3 + kN * 0.2), 2),
      avoidDeg: round(lerpRange(RANGE.avoidDeg, dN), 2),
      dustN: Math.round(lerpRange(RANGE.dustN, tN)),
      period: Math.round(lerpRange(RANGE.period, tN) / 25) * 25,
      halo: round(lerpRange(RANGE.halo, c.fieldNames / Math.max(1, c.characters)), 3),
      nodeHalo: round(lerpRange(RANGE.nodeHalo, cN), 3),
      obs: {
        characters: c.characters, camps: c.camps, campSizes: c.campSizes.slice(0),
        relations: c.relations, events: c.events, chapters: c.chapters,
        relationDensity: round(dens, 4), campConcentration: round(conc, 4),
        castMean: c.castN ? round(castMean, 3) : null,
        fieldMembers: c.fieldNames
      },
      norm: { density: round(dN, 4), span: round(tN, 4), cast: round(cN, 4), concentration: round(kN, 4) },
      gaps: gaps
    };
  }

  function fingerprint(G) {
    if (!G) { return 'empty'; }
    var chars = arr(G.characters), i, names = [];
    for (i = 0; i < chars.length; i++) { names.push(String(chars[i] && chars[i].name || '')); }
    names.sort();
    return digest([String(G.title || ''), chars.length, arr(G.events).length, arr(G.relations).length,
      names.slice(0, 24).join('\u0001')].join('\u0000'));
  }

  var KNOWN = {
    '大奉打更人': 'dafeng',
    '西游记': 'xiyou',
    '三国演义': 'sanguo'
  };

  /* 默认**不接线**到渲染：P06 的候选在定相位量测中引入「中央塌黑」
     （3840×2160，中央近黑占比 0.21→0.77、中央亮度 0.134→0.039）。
     逐层排查已排除：着色器文本（off 与全中性逐字符相同）、全部 uniform、
     场景图 1453 个对象（仅 1 个可见性差异）、机位 / fov / 清屏色 / 后处理档位、
     时间相位（冻结时钟后仍复现）。既然在预算内无法归因到具体一行，
     就不把这条渲染路径默认打开 —— 产品的默认画面必须回到已知良好状态。

     接线方式改为显式开启：URL 带 `dna=on` 才注入。
       · 默认（无参数）  → 历史渲染路径，逐位不变
       · dna=on         → DNA 渲染路径（候选，已知有中央塌黑，未签收）
       · dna=off        → 强制历史路径（等价默认，供 A/B 显式声明基线）
     计算与契约不受影响：CLSkyDNA.of() 照常可调，artifacts/plan100/visual/dna-*.json 照常产出。 */
  function disabled() {
    try {
      var q = g.location && g.location.search;
      if (!q) { return true; }
      if (/(^|[?&])dna=off(&|$)/.test(q)) { return true; }
      return !/(^|[?&])dna=on(&|$)/.test(q);
    } catch (e) { return true; }
  }

  var KEYS = ['layerBands', 'lobe', 'fray', 'cut', 'bandThick', 'bandTilt', 'avoidDeg', 'dustN', 'period', 'halo', 'nodeHalo'];
  function overrides() {
    var out = {}, i, parts, kv, k, v;
    try {
      var q = g.location && g.location.search;
      if (!q) { return out; }
      var m = q.match(/(?:^|[?&])dna=([^&]*)/);
      if (!m || m[1] === 'off') { return out; }
      parts = decodeURIComponent(m[1]).split(',');
      for (i = 0; i < parts.length; i++) {
        kv = parts[i].split(':');
        if (kv.length !== 2) { continue; }
        k = kv[0].replace(/^\s+|\s+$/g, '');
        v = +kv[1];
        if (KEYS.indexOf(k) < 0 || !isFinite(v)) { continue; }
        out[k] = v;
      }
    } catch (e) { return {}; }
    return out;
  }

  function of(G) {
    if (disabled()) { return null; }
    var c = census(G);
    var d = compute(G, c);
    d.version = VERSION;
    d.title = String((G && G.title) || '');
    d.fingerprint = fingerprint(G);
    var ov = overrides(), ok2 = Object.keys(ov);
    if (ok2.length) {
      d = JSON.parse(JSON.stringify(d));
      for (var oi = 0; oi < ok2.length; oi++) { d[ok2[oi]] = ov[ok2[oi]]; }
      d.overridden = ok2.slice(0);
      d.gaps = (d.gaps || []).concat(['DNA 字段被 URL 诊断覆盖（非实测值）：' + ok2.join(', ')]);
    }
    d.book = KNOWN[d.title] || ('fp:' + d.fingerprint);
    d.known = !!KNOWN[d.title];
    if (!d.known) { d.gaps = d.gaps.concat(['未登记书目「' + (d.title || '无题') + '」：id 由图谱指纹生成，参数按同一公式计算']); }
    return d;
  }

  function describe(d) {
    if (!d) { return ''; }
    return (d.book || '?') + ' · 分层 ' + d.layerBands + ' · 越界 ' + d.fray.toFixed(2) +
      ' · 带宽 ' + d.bandThick.toFixed(3) + ' · 周期 ' + d.period + 's';
  }

  g.CLSkyDNA = {
    version: VERSION,
    ID: ID,
    RANGE: RANGE,
    KNOWN: KNOWN,
    disabled: disabled,
    census: census,
    hhi: hhi,
    fingerprint: fingerprint,
    of: of,
    describe: describe
  };
})(window);
