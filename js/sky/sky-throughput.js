(function (g) {
  'use strict';

  var VERSION = '1';

  var BATCHES = {
    dafengSelfContained: { code: 'dafengSelfContained', zh: '大奉自足目标',
      hint: '选一个内部自足、目标清楚的大奉段落。' },
    sanguoCauseGap: { code: 'sanguoCauseGap', zh: '三国因果缺口',
      hint: '选三国里因果链有明显缺口的段落。' },
    xiyouHardEpisode: { code: 'xiyouHardEpisode', zh: '红孩儿之外西游一难',
      hint: '换一难，避免只在同一个已审过的段落上重复取分。' }
  };

  var RECORDS = {
    readChars: { code: 'readChars', zh: '阅读字符', hint: '实际读了多少字原文。' },
    independentReview: { code: 'independentReview', zh: '独立复核', hint: '复核是否由独立环节完成（不能自己审自己）。' },
    rejectReasons: { code: 'rejectReasons', zh: '拒绝原因', hint: '被拒的具体原因，不能只记"不合格"。' },
    rework: { code: 'rework', zh: '返工', hint: '返工次数与原因。' },
    pageSuccessRate: { code: 'pageSuccessRate', zh: '实际页面成功率', hint: '真实页面上的成功率，不是单测通过率。' }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function num(v) {
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (typeof v === 'string' && v.trim() !== '' && isFinite(+v)) return +v;
    return null;
  }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function qualifiedRate(batch) {
    batch = batch || {};
    var produced = num(batch.produced), rejected = num(batch.rejected) || 0;
    var reworked = num(batch.reworked) || 0;
    var chars = num(batch.readChars);
    var hours = num(batch.hours);
    if (produced == null) return { ok: false, reason: 'no_produced',
      hint: '缺少产出计数，无法算合格吞吐。' };
    var qualified = Math.max(0, produced - rejected);
    var out = {
      ok: true, produced: produced, rejected: rejected, reworked: reworked,
      qualified: qualified,
      qualifiedRate: hours && hours > 0 ? qualified / hours : null,
      charRate: hours && hours > 0 && chars != null ? chars / hours : null,
      pageSuccessRate: num(batch.pageSuccessRate),
      reviewedIndependently: batch.independentReview === true,
      hint: ''
    };
    if (out.reviewedIndependently !== true) {
      out.hint = '本批**未声明独立复核** —— 计划明令模型只替代候选抽取，不能替代审核。';
    }
    return out;
  }

  function expansionVerdict(prev, next) {
    prev = prev || {}; next = next || {};
    var nodesA = num(prev.nodes) || 0, nodesB = num(next.nodes) || 0;
    var missA = num(prev.majorOmissions), missB = num(next.majorOmissions);
    var added = nodesB - nodesA;
    if (missA == null || missB == null) {
      return { verdict: 'unknown', added: added,
        hint: '缺少主要遗漏计数，无法判断扩量是否有效 —— **不得**默认成有效。' };
    }
    var missDelta = missB - missA;
    if (added > 0 && missDelta >= 0) {
      return { verdict: 'pause', added: added, omissionsDelta: missDelta,
        hint: '新增节点 +' + added + ' 但主要遗漏未减（' + missA + '→' + missB + '）'
          + ' —— 按计划**暂停扩量**。产出量不能替代覆盖质量。' };
    }
    if (added > 0 && missDelta < 0) {
      return { verdict: 'continue', added: added, omissionsDelta: missDelta,
        hint: '新增节点 +' + added + ' 且主要遗漏减少（' + missA + '→' + missB + '），可以继续。' };
    }
    return { verdict: 'no_growth', added: added, omissionsDelta: missDelta,
      hint: '本批没有新增节点，不存在"扩量"问题。' };
  }

  function projectWorkload(opts) {
    opts = opts || {};
    var remaining = num(opts.remainingChars);
    var rate = num(opts.charRate);
    var out = { basis: 'qualified_char_rate', isCommitment: false };
    if (remaining == null || !rate || rate <= 0) {
      out.ok = false;
      out.hint = '缺少剩余字数或合格字符速率，无法推算 —— 不得凭感觉给数字。';
      return out;
    }
    var hours = remaining / rate;
    out.ok = true;
    out.remainingChars = remaining;
    out.charRate = rate;
    out.hours = hours;
    out.hoursLow = hours * 0.8;
    out.hoursHigh = hours * 1.5;
    out.uncertaintyNote = '区间为经验区间（0.8×–1.5×），不是统计置信区间；'
      + '返工、冲突与发布失败都会推高上界。';
    out.hint = '推算 ' + Math.round(out.hoursLow) + '–' + Math.round(out.hoursHigh)
      + ' 小时（依据：合格字符速率 ' + rate.toFixed(0) + ' 字/小时）。这是**推算**，不是承诺。';
    return out;
  }

  function capabilityWithoutApi(opts) {
    opts = opts || {};
    var hasSource = opts.hasSourceText !== false;
    var hasTools = opts.hasLocalTools !== false;
    return {
      hasSourceText: hasSource, hasLocalTools: hasTools,
      reviewPossible: hasSource && hasTools,
      hint: hasSource && hasTools
        ? '无额外 API 时仍可进行**原文审阅**（原文在本地、工具可用）。'
          + '不得把这种情况误判为停摆 —— 停下来的只是模型候选抽取。'
        : '缺少原文或本地工具，原文审阅确实无法进行。'
    };
  }

  function tally(batches) {
    var arrb = Array.isArray(batches) ? batches : [];
    var rates = arrb.map(qualifiedRate).filter(function (r) { return r.ok; });
    var missingRecords = Object.keys(RECORDS).filter(function (k) {
      return !arrb.some(function (b) { return present((b || {})[k]); });
    });
    var unindependentlyReviewed = rates.filter(function (r) { return !r.reviewedIndependently; }).length;
    return {
      title: '合格吞吐校准',
      isQualityScore: false,
      batches: arrb.length,
      qualified: rates.reduce(function (a, r) { return a + r.qualified; }, 0),
      produced: rates.reduce(function (a, r) { return a + r.produced; }, 0),
      rejected: rates.reduce(function (a, r) { return a + r.rejected; }, 0),
      reworked: rates.reduce(function (a, r) { return a + r.reworked; }, 0),
      unindependentlyReviewed: unindependentlyReviewed,
      missingRecords: missingRecords,
      missingRecordLabels: missingRecords.map(function (k) { return RECORDS[k].zh; }),
      note: '合格吞吐的分子只算合格产出（被拒不计入）。模型只替代候选抽取，'
        + '不能替代审核；无额外 API 仍可进行原文审阅。',
      summary: arrb.length
        ? (arrb.length + ' 批：产出 ' + rates.reduce(function (a, r) { return a + r.produced; }, 0)
          + '、拒绝 ' + rates.reduce(function (a, r) { return a + r.rejected; }, 0)
          + '、返工 ' + rates.reduce(function (a, r) { return a + r.reworked; }, 0)
          + '；缺记录项：' + (missingRecords.map(function (k) { return RECORDS[k].zh; }).join('、') || '无')
          + (unindependentlyReviewed ? '；**' + unindependentlyReviewed + ' 批未声明独立复核**' : ''))
        : '0 批 —— 首三批校准尚未开始；这不是"吞吐为零"，而是**尚无样本**。'
    };
  }

  var API = { VERSION: VERSION, BATCHES: BATCHES, RECORDS: RECORDS,
    qualifiedRate: qualifiedRate, expansionVerdict: expansionVerdict,
    projectWorkload: projectWorkload, capabilityWithoutApi: capabilityWithoutApi,
    tally: tally };
  g.CLSkyThroughput = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
