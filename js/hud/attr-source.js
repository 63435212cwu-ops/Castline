/* Castline · js/hud/attr-source.js — 属性数据单一真相源 (D2 / G2-3)
 * ============================================================================
 * 来源：grand-order-plan §4 D2 属性数据单一真相（八维一处算）。
 * 职责：作为人物内在八维（智谋/实力/意志/魅力/情感/野心/权势/道义）分值、排名、基准、
 *       证据链、档位与格式化的【唯一计算入口】。
 * 供 plot-hud / radar-evidence-card / plot-deck / peerchart 订阅使用。
 * 遵循 ES5 规范与 'use strict'，导出 window.CLAttrSource。
 * ============================================================================
 */
(function () {
  'use strict';

  // 八维标准中文主键与英文标识
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

  // 跨题材通用衡量基准与定义（与 serve.py / radar-evidence-card.js 保持一致）
  var DEF = {
    智谋: '认知、判断、算计与布局（计谋 / 推理 / 学识 / 商业与专业判断 / 识人），以计划是否奏效为据',
    实力: '该世界体系内的直接对抗与行动能力（武功 / 修为 / 枪法 / 体能 / 统兵 / 专业硬实力），以实战结果为据',
    意志: '承压、坚持、不被击垮的韧性（逆境中的选择、忍耐与自制）',
    魅力: '令他人倾心、信服或追随的吸引力（人望 / 口才 / 气度 / 被爱慕与被追随的事实）',
    情感: '情感浓度、共情与牵绊之深（爱憎强度、为亲友的付出、被触动的程度），不是情绪化程度',
    野心: '欲望与向上攫取的驱动力（目标大小、付出的代价、对现状的不满足）',
    权势: '当下实际可调动的地位、资源、人脉与靠山（官职 / 门派或公司地位 / 财富 / 家族 / 势力）',
    道义: '底线、原则与对他人的善意（守诺 / 护弱 / 公正）；低分 = 为达目的不择手段'
  };

  // 绝对刻度标尺（50 常人 · 70 圈内出色 · 85 一方之最 · 96+ 传说级）
  var SCALE_TICKS = [
    { v: 50, label: '50 常人', desc: '未经专业训练之常态基准' },
    { v: 70, label: '70 出色', desc: '圈内知名人物或专业骨干' },
    { v: 85, label: '85 一方之最', desc: '宗门领袖 / 巨贾大帅 / 拔尖精锐' },
    { v: 96, label: '96+ 传说', desc: '旷古绝今 / 世界观战力或智计天花板' }
  ];

  // 7 级档位与色彩语义
  var TIERS = [
    { min: 96, max: 100, tier: 'god',        name: '神圣极境', color: '#ffd27a', desc: '超凡入圣 · 跨时代传说' },
    { min: 85, max: 95,  tier: 'peerless',   name: '一方之最', color: '#ffb45c', desc: '宗门魁首 · 傲视群雄' },
    { min: 70, max: 84,  tier: 'elite',      name: '圈内翘楚', color: '#7af0c8', desc: '精锐中坚 · 卓越出众' },
    { min: 55, max: 69,  tier: 'proficient', name: '熟稔干练', color: '#c8a7ff', desc: '立足之地 · 稳定成熟' },
    { min: 40, max: 54,  tier: 'ordinary',   name: '众生基准', color: '#bfb8cf', desc: '寻常水平 · 芸芸众生' },
    { min: 25, max: 39,  tier: 'flawed',     name: '显现短板', color: '#ffa07a', desc: '明显匮乏 · 劣势所在' },
    { min: 0,  max: 24,  tier: 'abyss',      name: '深渊残缺', color: '#ff5d73', desc: '极端缺陷 · 致命弱点' }
  ];

  // 订阅者监听列表
  var listeners = [];

  /* ------------------------------------------------------------------ R4 事件环防护
   * **实测订正（见 reports/V2-1.json / reports/V2-0.json E11）**：
   *   `notify` 在**全仓零调用点** —— 广播器从未通电，故 plan R4 所担心的
   *   「同一 payload 下四订阅者级联重绘」在本批**并不会发生**，
   *   「去重 + rAF 合帧」的收益当下为**零**（且会把同步广播改成异步，反引入时序风险）。
   *   故**不实现** rAF 合帧；改做两处不依赖「是否被调用」的**结构**加固：
   *
   * ① **重入防护**：notify 同步遍历 listeners。若某监听器在回调里再次触发 notify，
   *    即重入 —— 轻则同一监听器在同一 tick 内被重复调用，重则遍历索引错乱。
   *    设 `notifying` 哨兵：重入时**警告并拒绝**（不递归）。
   * ② **遍历快照**：监听器在遍历中被 subscribe / unsubscribe 改写不影响本轮。
   *
   * **订阅端契约（禁止回写）**：回调内**不得**回写本模块（不得调 notify、不得改 listeners）。
   *    需要联动请只读 `extractAttr` / `computeCharacterProfile` / `getTierInfo` 等纯函数。
   *    违反该契约即触发 ① 的警告。 */
  var notifying = false;

  function getTierInfo(score, isLowConf, isPending) {
    if (isPending || score == null || isNaN(score)) {
      return {
        tier: 'pend',
        name: '存疑待定',
        color: '#7d7696',
        desc: '材料未明言，采用外围侧面情节保守估测'
      };
    }
    var s = Math.max(0, Math.min(100, Math.round(+score)));
    for (var i = 0; i < TIERS.length; i++) {
      if (s >= TIERS[i].min && s <= TIERS[i].max) {
        var res = {
          tier: TIERS[i].tier,
          name: TIERS[i].name,
          color: TIERS[i].color,
          desc: TIERS[i].desc
        };
        if (isLowConf) {
          res.name += ' (低置信)';
        }
        return res;
      }
    }
    return { tier: 'ordinary', name: '众生基准', color: '#bfb8cf', desc: '寻常水平' };
  }

  function extractAttr(charObj, key) {
    if (!charObj) return null;
    var raw = charObj.attrs || charObj;
    var v = raw[key];
    if (typeof v === 'number') {
      return { score: v, evidence: [], basis: '', chain: '', low: false, pending: false };
    }
    if (v && typeof v === 'object') {
      var score = isFinite(parseFloat(v.score)) ? parseFloat(v.score) : null;
      var ev = Array.isArray(v.evidence) ? v.evidence : [];
      return {
        score: score,
        evidence: ev,
        basis: v.basis || '',
        chain: v.chain || '',
        low: !!v.low || (!ev.length && !v.chain),
        pending: score == null,
        confidence: v.confidence != null ? +v.confidence : null,
        unverified: +v.unverified || 0
      };
    }
    return { score: null, evidence: [], basis: '', chain: '', low: true, pending: true };
  }

  function computeBenchmarks(allChars) {
    var chars = Array.isArray(allChars) ? allChars : [];
    var bm = {};
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var scores = [];
      for (var j = 0; j < chars.length; j++) {
        var a = extractAttr(chars[j], k);
        if (a && a.score != null && isFinite(a.score)) {
          scores.push(a.score);
        }
      }
      if (scores.length > 0) {
        scores.sort(function (a, b) { return a - b; });
        var sum = 0;
        for (var s = 0; s < scores.length; s++) sum += scores[s];
        var avg = Math.round((sum / scores.length) * 10) / 10;
        var med = scores[Math.floor(scores.length / 2)];
        bm[k] = {
          count: scores.length,
          avg: avg,
          min: scores[0],
          max: scores[scores.length - 1],
          median: med
        };
      } else {
        bm[k] = { count: 0, avg: 50, min: 50, max: 50, median: 50 };
      }
    }
    return bm;
  }

  function getRank(charOrName, key, allChars) {
    var chars = Array.isArray(allChars) ? allChars : [];
    if (!chars.length) return { rank: null, total: 0, percentile: 0, title: '未建档' };

    var name = typeof charOrName === 'string' ? charOrName : (charOrName.name || charOrName.id || '');
    var pool = [];
    for (var i = 0; i < chars.length; i++) {
      var c = chars[i];
      var a = extractAttr(c, key);
      if (a && a.score != null && isFinite(a.score)) {
        pool.push({ name: c.name || c.id || '', score: a.score });
      }
    }
    if (!pool.length) return { rank: null, total: 0, percentile: 0, title: '未建档' };

    pool.sort(function (a, b) { return b.score - a.score; });
    var targetRank = -1;
    for (var r = 0; r < pool.length; r++) {
      if (pool[r].name === name) {
        targetRank = r + 1;
        break;
      }
    }
    if (targetRank < 0) return { rank: null, total: pool.length, percentile: 0, title: '待考' };

    var pct = Math.round(((pool.length - targetRank) / pool.length) * 100);
    var title = '全书第 ' + targetRank;
    if (targetRank === 1) title = '全书之冠';
    else if (targetRank <= 3) title = '全书前甲';
    else if (pct >= 80) title = '全书前 20%';
    else if (pct >= 50) title = '全书前 50%';
    else title = '后位待进';

    return {
      rank: targetRank,
      total: pool.length,
      percentile: pct,
      title: title
    };
  }

  function getBenchmarkDelta(score, avg) {
    if (score == null || avg == null) {
      return { diff: 0, label: '无基准数据', classType: 'none' };
    }
    var diff = Math.round(score - avg);
    var label = '';
    var classType = '';
    if (diff > 0) {
      var pct = Math.round((diff / Math.max(1, avg)) * 100);
      label = 'vs 全书均值 +' + diff + ' (领先 ' + pct + '%)';
      classType = 'lead';
    } else if (diff < 0) {
      label = 'vs 全书均值 ' + diff + ' (低于均值 ' + Math.abs(diff) + ' 分)';
      classType = 'lag';
    } else {
      label = 'vs 全书均值 持平';
      classType = 'even';
    }
    return {
      diff: diff,
      label: label,
      classType: classType
    };
  }

  function formatScore(score) {
    if (score == null || isNaN(score)) return '—';
    return String(Math.round(+score));
  }

  function computeCharacterProfile(charObj, allChars) {
    if (!charObj) return null;
    var profile = {
      name: charObj.name || charObj.id || '未命名',
      camp: charObj.camp || '',
      attrs: {},
      averages: {}
    };
    var bm = computeBenchmarks(allChars);
    var totalScore = 0, count = 0;
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var raw = extractAttr(charObj, k);
      var sc = raw ? raw.score : null;
      var tier = getTierInfo(sc, raw && raw.low, raw && raw.pending);
      var rk = getRank(charObj, k, allChars);
      var bInfo = bm[k] || { avg: 50 };
      var delta = getBenchmarkDelta(sc, bInfo.avg);

      if (sc != null && isFinite(sc)) {
        totalScore += sc;
        count++;
      }

      profile.attrs[k] = {
        key: k,
        en: EN[k] || 'ATTR',
        def: DEF[k] || '',
        score: sc,
        formatted: formatScore(sc),
        tier: tier,
        rank: rk,
        benchmark: bInfo,
        delta: delta,
        evidence: raw ? raw.evidence : [],
        basis: raw ? raw.basis : '',
        chain: raw ? raw.chain : '',
        confidence: raw ? raw.confidence : null,
        low: raw ? raw.low : true,
        pending: raw ? raw.pending : true
      };
    }
    profile.overallAverage = count > 0 ? Math.round((totalScore / count) * 10) / 10 : null;
    return profile;
  }

  function subscribe(listener) {
    if (typeof listener === 'function' && listeners.indexOf(listener) < 0) {
      listeners.push(listener);
    }
    return function unsubscribe() {
      var idx = listeners.indexOf(listener);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  }

  function notify(payload) {
    /* R4：重入拒绝 + 遍历快照。语义对**单层广播**完全不变；
     * 仅对「监听器里再调 notify」这一病态路径从「静默递归」改为「警告 + 不递归」。 */
    if (notifying) {
      if (window.console && console.warn) {
        console.warn('[CLAttrSource] notify 重入被拒：订阅端不得在回调内回写本模块（R4 契约）');
      }
      return;
    }
    var snapshot = listeners.slice();   // 遍历期改表不影响本轮
    notifying = true;
    try {
      for (var i = 0; i < snapshot.length; i++) {
        try {
          snapshot[i](payload);
        } catch (err) {
          if (window.console && console.warn) console.warn('[CLAttrSource] listener error:', err);
        }
      }
    } finally {
      notifying = false;                // 异常也不留死锁哨兵
    }
  }

  window.CLAttrSource = {
    KEYS: KEYS,
    EN: EN,
    DEF: DEF,
    SCALE_TICKS: SCALE_TICKS,
    TIERS: TIERS,
    extractAttr: extractAttr,
    getTierInfo: getTierInfo,
    computeBenchmarks: computeBenchmarks,
    getRank: getRank,
    getBenchmarkDelta: getBenchmarkDelta,
    formatScore: formatScore,
    computeCharacterProfile: computeCharacterProfile,
    subscribe: subscribe,
    notify: notify
  };
})();
