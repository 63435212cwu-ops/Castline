/**
 * Castline · radar-benchmark.js
 * 全书基准对照与人群分布引擎 (window.CLRadarBenchmark)
 *
 * 核心能力：
 * 1. computeBenchmark(characters, options):
 *    统计全书中所有已建档角色的 8 维平均分 avg、中位数 median、最高分 max、最低分 min、标准差 std，具备内存缓存。
 *    v71 W3·U8 起返回值新增：
 *      - byCamp: { 阵营名: 同款统计对象 }（只统计已建档角色；无阵营角色归入全书统计但不进任何 camp 桶；
 *        阵营对象额外带 scope:'camp' 与 camp 名，其 percentileOf 恒为全书口径）
 *      - percentileOf(key, score): 该维全书百分位（0-100，已建档角色内，中位秩：并列各计半）
 *      - scope: 'book'（全书基准标识）
 * 2. getGhostPoints(bench, R, cx, cy, squash):
 *    计算全书基准均值对应的 8 边形多边形坐标序列（points 字符串 "x1,y1 x2,y2..."），用于雷达背景上绘制半透明幽灵基准线
 * 2b. ghostFor(bench, camp, R, cx, cy, squash):
 *    阵营基准幽灵线：camp 有效且该阵营已建档 ≥3 人时返回该阵营均值幽灵点，否则回落全书幽灵点
 * 3. getDeltas(attrs, bench):
 *    计算当前角色对比全书平均分在各维度的差值 delta（如 +12, -5）以及高于平均分的维度数 aboveCount
 *
 * 共享约定：
 * KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义']
 * EN = { 智谋: 'MIND', 实力: 'FORCE', 意志: 'WILL', 魅力: 'CHARM', 情感: 'HEART', 野心: 'DRIVE', 权势: 'REACH', 道义: 'CODE' }
 *
 * 最小使用示例 / Minimal Usage Example:
 * ```js
 * // 1. 计算全书基准（自动内存缓存）
 * var bench = window.CLRadarBenchmark.computeBenchmark(G.characters);
 * console.log('智谋均值:', bench['智谋'].avg, '中位数:', bench['智谋'].median);
 *
 * // 2. 生成幽灵轮廓多边形 points 坐标串
 * var points = window.CLRadarBenchmark.getGhostPoints(bench, 91.2, 160, 164, 0.9);
 * // SVG 中使用: `<polygon class="rd-ghost" points="${points}"/>`
 *
 * // 3. 计算当前角色与基准的差值
 * var deltas = window.CLRadarBenchmark.getDeltas(character.attrs, bench);
 * console.log('超越基准维度数:', deltas.aboveCount); // 如 5
 * console.log('智谋相对差值:', deltas.formatted['智谋']); // 如 "+12"
 * ```
 */

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

  // 共享标准常量
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

  // 无阵营哨兵：与 window.NCConstellation.FIELD（'散星'）及 app.js 的 camp 归一化口径一致
  var FIELD_CAMP = '散星';

  /**
   * 提取角色所属阵营名；无阵营（空 / 散星 / 无·—·-·未知）返回 ''
   */
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

  // 语义设计令牌
  var THEME = {
    obsidian: '#07060d',
    mint: '#7af0c8',
    amber: '#ffb45c',
    violet: '#a688ff',
    crimson: '#ff5c7c'
  };

  // 内存缓存单例
  var _cache = {
    ref: null,
    length: -1,
    benchmark: null
  };

  /**
   * 安全提取分值（0~100，取整用于统计聚合）。
   * 唯一真相：有效性判定与夹取全部委托 `window.CLRadar.scoreOf`（同一份反例表：
   * 空白串/纯布尔/数组/{score:true}→无效，{score:80,pending:true}→pending(null)，
   * 真 0 有效，NaN/Infinity 无效）；只在 radar.js 未加载时退回下面这份逐字等价的
   * legacy 实现（供独立契约测试验证一致性，不允许出现另一套强转逻辑）。
   */
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

  /**
   * 构造全 50 分默认基准数据结构
   */
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

  /**
   * 由 dimensionScores { key: [scores] } 构建 8 维统计（avg/median/max/min/std/count + overallAvg）。
   * dist 保留各维已排序分值（四舍五入后的整数），供百分位计算使用。
   */
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

  /**
   * 生成 percentileOf(key, score) 闭包：该维在已建档角色中的全书百分位（0-100）。
   * 中位秩口径：严格低于的计 1，并列的各计半 —— 最高不顶 100、最低不触 0、全员同分得 50。
   * key 支持中文维度名与 EN 代号；维度无分布或分值非法时返回 null。
   */
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

  /**
   * 组装基准对象（全书或单阵营同款结构）。
   */
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

  /**
   * 1. computeBenchmark(characters, options)
   * 统计全书中所有已建档角色的 8 维平均分 avg、中位数 median、最高分 max、最低分 min、标准差 std
   * 具备内存缓存机制，若 characters 未变更则直接返回缓存对象
   *
   * @param {Array} characters - 角色列表，可为空或未建档
   * @param {Object} [options] - 选项配置 { force: boolean } 是否强制绕过缓存重算
   * @returns {Object} 基准统计对象
   */
  function computeBenchmark(characters, options) {
    options = options || {};
    var force = !!options.force;

    // 优雅回退：若未提供 characters，尝试从 window.G.characters 读取
    var list = characters;
    if (!list && typeof window !== 'undefined' && window.G && Array.isArray(window.G.characters)) {
      list = window.G.characters;
    }

    if (!Array.isArray(list) || list.length === 0) {
      return createDefaultBenchmark();
    }

    // 内存缓存命中判断（引用与长度相同）
    /* Character objects are mutable (CLAttrSource updates them in place); a
       reference+length cache therefore serves stale means. Recompute unless a
       caller explicitly supplies a future immutable version key. */
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

    // 阵营分桶：只统计已建档角色；全未建档的阵营不出空桶；无阵营角色不进任何桶。
    // byCamp 随主缓存一起缓存（同一缓存键：引用 + 长度 + version）。
    var byCamp = {};
    for (var ci = 0; ci < campOrder.length; ci++) {
      var cname = campOrder[ci];
      if (!campProfiled[cname]) continue;
      var cb = finalizeBench(buildDimensionStats(campScores[cname]), campTotal[cname], campProfiled[cname], { scope: 'camp', camp: cname });
      // 百分位恒为全书口径：阵营基准只改变对照均值，不改变百分位参照系
      cb.percentileOf = benchmark.percentileOf;
      byCamp[cname] = cb;
    }
    benchmark.byCamp = byCamp;

    // 写入内存缓存
    _cache.ref = list;
    _cache.length = list.length;
    _cache.version = options.version == null ? null : options.version;
    _cache.benchmark = benchmark;

    return benchmark;
  }

  /**
   * 从各种基准对象结构中安全获取指定维度的均值 avg
   * 若无法读取则安全回退至 50
   */
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

  /**
   * 2. getGhostPoints(bench, R, cx, cy, squash)
   * 计算全书基准均值对应的 8 边形多边形坐标序列（points 字符串 "x1,y1 x2,y2..."）
   * 用于在雷达背景上绘制半透明幽灵基准线
   *
   * @param {Object} bench - 基准统计数据（可为空，空时取默认 50 分）
   * @param {number} [R] - 雷达基础外径半径，默认 91.2 (320 * 0.285)
   * @param {number} [cx] - 雷达中心点 X 坐标，默认 160 (320 / 2)
   * @param {number} [cy] - 雷达中心点 Y 坐标，默认 164 (320 / 2 + 4)
   * @param {number} [squash] - 俯仰压缩系数，默认 0.9
   * @returns {string} 多边形 points 坐标字符串 "x1,y1 x2,y2..."
   */
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

  /**
   * 2b. ghostFor(bench, camp, R, cx, cy, squash)
   * 阵营基准幽灵线。回落语义：camp 为空、bench 无 byCamp、该阵营不存在、
   * 或该阵营已建档不足 3 人（样本太少，阵营均值不稳定）时，一律回落全书均值幽灵点。
   *
   * @param {Object} bench - computeBenchmark 返回的全书基准对象
   * @param {string} [camp] - 阵营名（调用方自己知道角色阵营）
   * @returns {string} 多边形 points 坐标字符串
   */
  function ghostFor(bench, camp, R, cx, cy, squash) {
    var src = resolveCamp(bench, camp) || bench;
    return getGhostPoints(src, R, cx, cy, squash);
  }

  /**
   * resolveCamp(bench, camp): 返回可用于渲染的阵营基准对象；不满足 ≥3 人已建档时返回 null
   * （调用方据此回落到全书 bench）。
   */
  function resolveCamp(bench, camp) {
    if (!bench || !camp || !bench.byCamp) return null;
    var cb = bench.byCamp[camp];
    if (!cb || cb.isEmpty || !(cb.profiledCount >= 3)) return null;
    return cb;
  }

  /**
   * percentileOf(key, score): 模块级便捷入口，对当前缓存的全书基准求百分位。
   * 单角色场景请优先使用 bench.percentileOf（绑定该次计算的分布）。
   */
  function percentileOf(key, score) {
    var b = _cache.benchmark;
    if (!b || typeof b.percentileOf !== 'function') return null;
    return b.percentileOf(key, score);
  }

  /**
   * 获取幽灵基准多边形的点数组 [[x,y], ...]
   */
  function getGhostCoordinates(bench, R, cx, cy, squash) {
    var rawStr = getGhostPoints(bench, R, cx, cy, squash);
    if (!rawStr) return [];
    return rawStr.split(' ').map(function (pair) {
      var parts = pair.split(',');
      return [parseFloat(parts[0]), parseFloat(parts[1])];
    });
  }

  /**
   * 渲染幽灵基准 SVG 多边形标签（辅助组件）
   * 样式统一采用设计令牌变量，避免裸色值
   */
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

  /**
   * 3. getDeltas(attrs, bench)
   * 计算当前角色对比全书平均分在各维度的差值 delta（如 +12, -5），以及高于平均分的维度数 aboveCount
   *
   * @param {Object} attrs - 角色的 8 维属性对象（支持 c.attrs 结构，或维度为 key 的对象）
   * @param {Object} [bench] - 全书基准对象，若未传则优先复用内存缓存或 50 分默认基准
   * @returns {Object} 差值分析结果对象
   */
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

    // 挂载直取属性，方便 result[k] 快捷取值
    for (var j = 0; j < KEYS.length; j++) {
      var key = KEYS[j];
      result[key] = deltasMap[key];
      if (EN[key]) result[EN[key]] = deltasMap[key];
    }

    return result;
  }

  /**
   * 清除内存缓存
   */
  function clearCache() {
    _cache.ref = null;
    _cache.length = -1;
    _cache.benchmark = null;
  }

  /**
   * 获取当前缓存的基准数据（若无则返回 null）
   */
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
