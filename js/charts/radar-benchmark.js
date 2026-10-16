
(function (root, factory) {
  'use strict';
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    var exp = factory();
    root.CLRadarBenchmark = exp;
    if (typeof window !== 'undefined') {
      window.CLRadarBenchmark = exp;
    }
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
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
  var EN_REV = {};
  KEYS.forEach(function (k) { if (EN[k]) EN_REV[EN[k]] = k; });

  var FIELD_CAMP = '散星';

  function campNameOf(c) {
    if (!c) return '';
    var raw = c.camp;
    if (raw == null) return '';
    var s = String(raw).trim();
    if (!s) return '';
    var field = (typeof window !== 'undefined' && window.NCConstellation && window.NCConstellation.FIELD) || FIELD_CAMP;
    if (s === field) return '';
    if (/^(无|—|-|未知)$/.test(s)) return '';
    return s;
  }

  var THEME = {
    obsidian: '#07060d',
    mint: '#7af0c8',
    amber: '#ffb45c',
    violet: '#a688ff',
    crimson: '#ff5c7c'
  };

  var _cache = {
    ref: null,
    length: -1,
    benchmark: null
  };

  function legacyScoreOf(val) {
    if (val == null) return null;
    if (typeof val === 'boolean' || Array.isArray(val)) return null;
    if (typeof val === 'number') return isFinite(val) ? Math.max(0, Math.min(100, val)) : null;
    if (typeof val === 'object') {
      if (val.pending) return null;
      if (val.score == null) return null;
      if (typeof val.score === 'boolean' || Array.isArray(val.score)) return null;
      if (typeof val.score === 'string' && val.score.trim() === '') return null;
      var s = Number(val.score);
      return (isFinite(s)) ? Math.max(0, Math.min(100, s)) : null;
    }
    if (typeof val !== 'string' || val.trim() === '') return null;
    var num = Number(val);
    return isFinite(num) ? Math.max(0, Math.min(100, num)) : null;
  }
  function extractScore(val) {
    var hasRadar = typeof window !== 'undefined' && window.CLRadar && typeof window.CLRadar.scoreOf === 'function';
    var raw = hasRadar ? window.CLRadar.scoreOf(val) : legacyScoreOf(val);
    return raw == null ? null : Math.round(raw);
  }

  function createDefaultBenchmark() {
    var dimensions = [];
    var avgMap = {};
    var medianMap = {};
    var maxMap = {};
    var minMap = {};
    var stdMap = {};
    var countMap = {};

    KEYS.forEach(function (k) {
      var item = {
        key: k,
        en: EN[k] || '',
        avg: null,
        avgRound: null,
        median: null,
        max: null,
        min: null,
        std: null,
        count: 0
      };
      dimensions.push(item);
      avgMap[k] = null;
      medianMap[k] = null;
      maxMap[k] = null;
      minMap[k] = null;
      stdMap[k] = null;
      countMap[k] = 0;
    });

    var defBench = {
      characterCount: 0,
      profiledCount: 0,
      overallAvg: null,
      isEmpty: true,
      dimensions: dimensions,
      avg: avgMap,
      median: medianMap,
      max: maxMap,
      min: minMap,
      std: stdMap,
      count: countMap,
      byCamp: {},
      scope: 'book',
      percentileOf: function () { return null; },
      KEYS: KEYS,
      EN: EN,
      timestamp: Date.now()
    };

    KEYS.forEach(function (k, i) {
      defBench[k] = dimensions[i];
      if (EN[k]) defBench[EN[k]] = dimensions[i];
    });

    return defBench;
  }

  function buildDimensionStats(dimensionScores) {
    var dimensions = [];
    var avgMap = {};
    var medianMap = {};
    var maxMap = {};
    var minMap = {};
    var stdMap = {};
    var countMap = {};
    var dist = {};
    var sumAvgs = 0, avgDimensions = 0;

    KEYS.forEach(function (k) {
      var scores = dimensionScores[k];
      var stat;

      if (!scores || scores.length === 0) {
        stat = {
          key: k,
          en: EN[k] || '',
          avg: null,
          avgRound: null,
          median: null,
          max: null,
          min: null,
          std: null,
          count: 0
        };
        dist[k] = [];
      } else {
        scores.sort(function (a, b) { return a - b; });
        var count = scores.length;
        var sum = 0;
        for (var s = 0; s < count; s++) sum += scores[s];
        var mean = sum / count;
        var avg = Math.round(mean * 10) / 10;
        var avgRound = Math.round(mean);

        var mid = Math.floor(count / 2);
        var med = (count % 2 === 1) ? scores[mid] : (scores[mid - 1] + scores[mid]) / 2;
        var median = Math.round(med * 10) / 10;

        var min = scores[0];
        var max = scores[count - 1];

        var varianceSum = 0;
        for (var v = 0; v < count; v++) {
          var diff = scores[v] - mean;
          varianceSum += diff * diff;
        }
        var std = Math.round(Math.sqrt(varianceSum / count) * 10) / 10;

        stat = {
          key: k,
          en: EN[k] || '',
          avg: avg,
          avgRound: avgRound,
          median: median,
          max: max,
          min: min,
          std: std,
          count: count
        };
        dist[k] = scores.slice();
      }

      dimensions.push(stat);
      avgMap[k] = stat.avg;
      medianMap[k] = stat.median;
      maxMap[k] = stat.max;
      minMap[k] = stat.min;
      stdMap[k] = stat.std;
      countMap[k] = stat.count;
      if (stat.avg != null) { sumAvgs += stat.avg; avgDimensions++; }
    });

    return {
      dimensions: dimensions,
      avg: avgMap,
      median: medianMap,
      max: maxMap,
      min: minMap,
      std: stdMap,
      count: countMap,
      overallAvg: avgDimensions ? Math.round((sumAvgs / avgDimensions) * 10) / 10 : null,
      dist: dist
    };
  }

  function makePercentileOf(dist) {
    return function (key, score) {
      if (!dist) return null;
      var k = key;
      var arr = dist[k];
      if (!arr && EN_REV[k]) { k = EN_REV[k]; arr = dist[k]; }
      if (!arr || !arr.length) return null;
      var v = Number(score);
      if (!isFinite(v)) return null;
      v = Math.max(0, Math.min(100, v));
      var below = 0, equal = 0;
      for (var i = 0; i < arr.length; i++) {
        if (arr[i] < v) below++;
        else if (arr[i] === v) equal++;
      }
      return Math.round((below + equal / 2) / arr.length * 100);
    };
  }

  function finalizeBench(stats, characterCount, profiledCount, extra) {
    var benchmark = {
      characterCount: characterCount,
      profiledCount: profiledCount,
      overallAvg: stats.overallAvg,
      isEmpty: profiledCount === 0,
      dimensions: stats.dimensions,
      avg: stats.avg,
      median: stats.median,
      max: stats.max,
      min: stats.min,
      std: stats.std,
      count: stats.count,
      byCamp: {},
      scope: 'book',
      percentileOf: makePercentileOf(stats.dist),
      KEYS: KEYS,
      EN: EN,
      timestamp: Date.now()
    };

    KEYS.forEach(function (k, idx) {
      benchmark[k] = stats.dimensions[idx];
      if (EN[k]) benchmark[EN[k]] = stats.dimensions[idx];
    });

    if (extra) for (var p in extra) benchmark[p] = extra[p];
    return benchmark;
  }

  function computeBenchmark(characters, options) {
    options = options || {};
    var force = !!options.force;

    var list = characters;
    if (!list && typeof window !== 'undefined' && window.G && Array.isArray(window.G.characters)) {
      list = window.G.characters;
    }

    if (!Array.isArray(list) || list.length === 0) {
      return createDefaultBenchmark();
    }

    if (!force && options.version != null && _cache.benchmark && _cache.ref === list && _cache.length === list.length && _cache.version === options.version) return _cache.benchmark;

    var dimensionScores = {};
    KEYS.forEach(function (k) { dimensionScores[k] = []; });
    var campScores = {};
    var campProfiled = {};
    var campTotal = {};
    var campOrder = [];
    var profiledCount = 0;

    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if (!c) continue;
      var attrs = c.attrs || (c.score !== undefined ? null : c);
      if (!attrs) continue;

      var camp = campNameOf(c);
      if (camp && !campScores[camp]) {
        campScores[camp] = {};
        KEYS.forEach(function (k) { campScores[camp][k] = []; });
        campProfiled[camp] = 0;
        campTotal[camp] = 0;
        campOrder.push(camp);
      }
      if (camp) campTotal[camp]++;

      var hasProfiledAttr = false;
      for (var j = 0; j < KEYS.length; j++) {
        var k = KEYS[j];
        var val = attrs[k] !== undefined ? attrs[k] : (attrs[EN[k]] !== undefined ? attrs[EN[k]] : null);
        var score = extractScore(val);
        if (score !== null) {
          dimensionScores[k].push(score);
          if (camp) campScores[camp][k].push(score);
          hasProfiledAttr = true;
        }
      }
      if (hasProfiledAttr) {
        profiledCount++;
        if (camp) campProfiled[camp]++;
      }
    }

    if (profiledCount === 0) {
      var emptyBench = createDefaultBenchmark();
      emptyBench.characterCount = list.length;
      return emptyBench;
    }

    var benchmark = finalizeBench(buildDimensionStats(dimensionScores), list.length, profiledCount, null);

    var byCamp = {};
    for (var ci = 0; ci < campOrder.length; ci++) {
      var cname = campOrder[ci];
      if (!campProfiled[cname]) continue;
      var cb = finalizeBench(buildDimensionStats(campScores[cname]), campTotal[cname], campProfiled[cname], { scope: 'camp', camp: cname });
      cb.percentileOf = benchmark.percentileOf;
      byCamp[cname] = cb;
    }
    benchmark.byCamp = byCamp;

    _cache.ref = list;
    _cache.length = list.length;
    _cache.version = options.version == null ? null : options.version;
    _cache.benchmark = benchmark;

    return benchmark;
  }

  function getBenchAvg(bench, k) {
    if (!bench || bench.isEmpty) return null;
    if (typeof bench[k] === 'number') return bench[k];
    if (bench[k] && typeof bench[k].avg === 'number') return bench[k].avg;
    if (bench.avg && typeof bench.avg[k] === 'number') return bench.avg[k];

    var en = EN[k];
    if (en) {
      if (typeof bench[en] === 'number') return bench[en];
      if (bench[en] && typeof bench[en].avg === 'number') return bench[en].avg;
      if (bench.avg && typeof bench.avg[en] === 'number') return bench.avg[en];
    }
    return null;
  }

  function getGhostPoints(bench, R, cx, cy, squash) {
    var parsedR = Number(R);
    var radius = (isFinite(parsedR) && parsedR > 0) ? parsedR : 91.2;

    var parsedCx = Number(cx);
    var centerX = isFinite(parsedCx) ? parsedCx : 160;

    var parsedCy = Number(cy);
    var centerY = isFinite(parsedCy) ? parsedCy : 164;

    var parsedSquash = Number(squash);
    var squashFactor = (isFinite(parsedSquash) && parsedSquash > 0) ? parsedSquash : 0.9;

    var n = KEYS.length;
    var pts = [];

    for (var i = 0; i < n; i++) {
      var k = KEYS[i];
      var avgScore = getBenchAvg(bench, k);
      if (avgScore == null) return '';
      var clamped = Math.max(0, Math.min(100, Number(avgScore)));
      var r = radius * (clamped / 100);
      var a = -Math.PI / 2 + i * (2 * Math.PI / n);
      var x = Math.round((centerX + Math.cos(a) * r) * 100) / 100;
      var y = Math.round((centerY + Math.sin(a) * r * squashFactor) * 100) / 100;
      pts.push(x + ',' + y);
    }

    return pts.join(' ');
  }

  function ghostFor(bench, camp, R, cx, cy, squash) {
    var src = resolveCamp(bench, camp) || bench;
    return getGhostPoints(src, R, cx, cy, squash);
  }

  function resolveCamp(bench, camp) {
    if (!bench || !camp || !bench.byCamp) return null;
    var cb = bench.byCamp[camp];
    if (!cb || cb.isEmpty || !(cb.profiledCount >= 3)) return null;
    return cb;
  }

  function percentileOf(key, score) {
    var b = _cache.benchmark;
    if (!b || typeof b.percentileOf !== 'function') return null;
    return b.percentileOf(key, score);
  }

  function getGhostCoordinates(bench, R, cx, cy, squash) {
    var rawStr = getGhostPoints(bench, R, cx, cy, squash);
    if (!rawStr) return [];
    return rawStr.split(' ').map(function (pair) {
      var parts = pair.split(',');
      return [parseFloat(parts[0]), parseFloat(parts[1])];
    });
  }

  function renderGhostPolygon(bench, opt) {
    opt = opt || {};
    var points = getGhostPoints(bench, opt.R, opt.cx, opt.cy, opt.squash);
    var cls = opt.className || 'rd-ghost-baseline';
    var stroke = opt.stroke || 'var(--mint, #7af0c8)';
    var strokeWidth = opt.strokeWidth || '1';
    var strokeDasharray = opt.strokeDasharray || '3,3';
    var strokeOpacity = opt.strokeOpacity || '0.42';
    var fill = opt.fill || 'var(--mint, #7af0c8)';
    var fillOpacity = opt.fillOpacity || '0.06';

    return '<polygon class="' + cls + '" points="' + points + '" ' +
      'fill="' + fill + '" fill-opacity="' + fillOpacity + '" ' +
      'stroke="' + stroke + '" stroke-width="' + strokeWidth + '" ' +
      'stroke-dasharray="' + strokeDasharray + '" stroke-opacity="' + strokeOpacity + '"/>';
  }

  function getDeltas(attrs, bench) {
    var effectiveBench = bench || _cache.benchmark || null;
    var rawAttrs = attrs ? (attrs.attrs || attrs) : null;

    var deltasMap = {};
    var formattedMap = {};
    var detailsMap = {};
    var items = [];

    var aboveCount = 0;
    var belowCount = 0;
    var equalCount = 0;
    var profiledCount = 0;

    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var en = EN[k] || '';
      var rawItem = rawAttrs ? (rawAttrs[k] !== undefined ? rawAttrs[k] : (rawAttrs[en] !== undefined ? rawAttrs[en] : null)) : null;

      var isPending = true;
      var score = null;

      score = extractScore(rawItem);
      isPending = score == null;

      var benchAvg = getBenchAvg(effectiveBench, k);
      var benchSupported = benchAvg != null;
      var benchAvgRound = benchSupported ? Math.round(benchAvg) : null;

      var delta = 0;
      var deltaNum = null;
      var formatted = '—';
      var isAbove = false;
      var isBelow = false;
      var isEqual = false;

      if (!isPending && score !== null && benchSupported) {
        profiledCount++;
        delta = score - benchAvgRound;
        deltaNum = delta;
        formatted = (delta > 0 ? '+' : '') + delta;
        if (delta > 0) {
          isAbove = true;
          aboveCount++;
        } else if (delta < 0) {
          isBelow = true;
          belowCount++;
        } else {
          isEqual = true;
          equalCount++;
        }
      }

      var detail = {
        key: k,
        en: en,
        score: score,
        benchAvg: benchAvg,
        benchAvgRound: benchAvgRound,
        delta: benchSupported && !isPending ? delta : null,
        deltaNum: deltaNum,
        formatted: formatted,
        text: benchSupported && !isPending ? formatted : '不支持',
        above: isAbove,
        below: isBelow,
        equal: isEqual,
        pending: isPending,
        benchmarkSupported: benchSupported
      };

      deltasMap[k] = isPending || !benchSupported ? null : delta;
      if (en) deltasMap[en] = isPending || !benchSupported ? null : delta;

      formattedMap[k] = formatted;
      if (en) formattedMap[en] = formatted;

      detailsMap[k] = detail;
      if (en) detailsMap[en] = detail;

      items.push(detail);
    }

    var result = {
      aboveCount: aboveCount,
      aboveAvgCount: aboveCount,
      belowCount: belowCount,
      belowAvgCount: belowCount,
      equalCount: equalCount,
      profiledCount: profiledCount,
      totalDimensions: KEYS.length,
      deltas: deltasMap,
      formatted: formattedMap,
      details: detailsMap,
      byKey: detailsMap,
      items: items,
      KEYS: KEYS,
      EN: EN
    };

    for (var j = 0; j < KEYS.length; j++) {
      var key = KEYS[j];
      result[key] = deltasMap[key];
      if (EN[key]) result[EN[key]] = deltasMap[key];
    }

    return result;
  }

  function clearCache() {
    _cache.ref = null;
    _cache.length = -1;
    _cache.benchmark = null;
  }

  function getCachedBenchmark() {
    return _cache.benchmark;
  }

  return {
    KEYS: KEYS,
    EN: EN,
    THEME: THEME,
    computeBenchmark: computeBenchmark,
    getGhostPoints: getGhostPoints,
    ghostFor: ghostFor,
    resolveCamp: resolveCamp,
    percentileOf: percentileOf,
    getGhostCoordinates: getGhostCoordinates,
    renderGhostPolygon: renderGhostPolygon,
    getDeltas: getDeltas,
    getBenchAvg: getBenchAvg,
    getDefaultBenchmark: createDefaultBenchmark,
    clearCache: clearCache,
    getCachedBenchmark: getCachedBenchmark
  };
}));
