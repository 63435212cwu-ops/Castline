(function (g) {
  'use strict';

  var VERSION = '1';

  var STRATA = {
    opening: { code: 'opening', zh: '开篇', hint: '全书开头部分。' },
    middle: { code: 'middle', zh: '中段', hint: '全书中部。' },
    turning: { code: 'turning', zh: '转折', hint: '关键转折处。' },
    ending: { code: 'ending', zh: '结局', hint: '全书收束处。' },
    sparseBranch: { code: 'sparseBranch', zh: '稀疏支线', hint: '事件稀疏的支线 —— 最容易漏。' },
    crossVolumeForeshadow: { code: 'crossVolumeForeshadow', zh: '跨卷伏笔', hint: '跨卷铺设与回收。' },
    identityHardCase: { code: 'identityHardCase', zh: '身份难例', hint: '同名/别名/一人多名等难例。' }
  };

  var METRICS = {
    events: { code: 'events', zh: '事件' },
    tasks: { code: 'tasks', zh: '任务' },
    causeEdges: { code: 'causeEdges', zh: '因果' },
    clues: { code: 'clues', zh: '伏笔' },
    characterStates: { code: 'characterStates', zh: '状态' },
    relations: { code: 'relations', zh: '关系' }
  };

  var FLOOR = { strict: 0.98, loose: 0.95 };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function coverage(gold) {
    gold = gold || {};
    var declared = [].concat(gold.strata || [], gold.episode && gold.episode.strata || []);
    var inferable = [];
    var ep = gold.episode || {};
    var total = num(gold.sourceTotalChars) || num(gold.totalChars);
    var st = num(ep.start), en = num(ep.end);
    if (total && st != null && en != null && total > 0) {
      var mid = (st + en) / 2 / total;
      if (mid <= 0.08) inferable.push('opening');
      else if (mid >= 0.92) inferable.push('ending');
      else inferable.push('middle');
    }
    var covered = {};
    Object.keys(STRATA).forEach(function (k) { covered[k] = false; });
    declared.forEach(function (s) {
      var code = str(s && s.code || s);
      if (covered[code] !== undefined) covered[code] = true;
    });
    var have = Object.keys(covered).filter(function (k) { return covered[k]; });
    var missing = Object.keys(covered).filter(function (k) { return !covered[k]; });
    return {
      covered: covered, have: have, missing: missing,
      inferable: inferable,
      positionNote: inferable.length
        ? ('按偏移推断它位于「' + inferable.map(function (k) { return STRATA[k].zh; }).join('、')
           + '」，但 fixture 未声明分层，故不计入覆盖。')
        : '没有偏移信息，无法推断它落在哪一层。',
      coveredCount: have.length, total: Object.keys(STRATA).length,
      missingLabels: missing.map(function (k) { return STRATA[k].zh; }),
      complete: missing.length === 0,
      hint: missing.length
        ? ('尚未覆盖的分层：' + missing.map(function (k) { return STRATA[k].zh; }).join('、'))
        : '七个分层均已覆盖。'
    };
  }

  function independence(gold) {
    gold = gold || {};
    var method = str(gold.reviewMethod);
    var producer = str(gold.producer || gold.candidateProducer || gold.generatedBy);
    var reviewer = str(gold.reviewer || gold.reviewedBy || gold.provenance);
    var declaredIndependent = /independent|no model call|独立/i.test(method);
    var sameParty = !!(producer && reviewer && producer === reviewer);
    var reviewers = [].concat(gold.reviewers || (reviewer ? [reviewer] : []))
      .filter(function (r) { return present(r && (r.name || r)); });
    var twoReviewers = reviewers.length >= 2;
    var hasAdjudication = present(gold.adjudication) || present(gold.disagreements)
      || /裁决|adjudicat/i.test(method);
    return {
      declaredIndependent: declaredIndependent,
      sameParty: sameParty,
      reviewerCount: reviewers.length,
      twoReviewers: twoReviewers,
      hasAdjudication: hasAdjudication,
      ok: declaredIndependent && !sameParty && twoReviewers,
      hint: sameParty
        ? '候选生成者与标准答案作者是同一方 —— 计划明令禁止。'
        : !twoReviewers
          ? ('只找到 ' + reviewers.length + ' 位审阅者；计划要求**两位**各读原文再标注。')
          : !declaredIndependent
            ? 'reviewMethod 未声明独立（未读到 independent / no model call / 独立）。'
            : '独立性成立：非同方、两位审阅者、已声明独立读原文。'
    };
  }

  function score(report) {
    report = report || {};
    var layer = str(report.layer);
    if (!METRICS[layer]) return { layer: layer || null, ok: false, reason: 'unknown_layer',
      hint: '未标明这是哪一维度的报告（事件/任务/因果/伏笔/状态/关系）。' };
    var total = num(report.total), correct = num(report.correct);
    var missed = num(report.missed), major = num(report.majorErrors), disputes = num(report.disputes);
    var dropped = num(report.droppedSamples);
    if (total == null || correct == null) return { layer: layer, ok: false, reason: 'no_counts',
      hint: '缺少 total/correct 计数，无法算精度。' };
    var precision = total > 0 ? correct / total : 0;
    var deletedSamples = dropped != null && dropped > 0;
    return {
      layer: layer, layerLabel: METRICS[layer].zh,
      total: total, correct: correct, precision: precision,
      missed: missed, majorErrors: major, disputes: disputes,
      droppedSamples: dropped,
      meetsStrict: precision >= FLOOR.strict,
      meetsLoose: precision >= FLOOR.loose,
      floorIsFloorNotPass: true,
      deletedSamples: deletedSamples,
      ok: !deletedSamples && precision >= FLOOR.loose,
      hint: deletedSamples
        ? ('报告声明删除了 ' + dropped + ' 个失败样本 —— 计划明令**不删失败样本提高分数**。')
        : precision < FLOOR.loose
          ? ('精度 ' + (precision * 100).toFixed(1) + '% 低于下限 ' + (FLOOR.loose * 100) + '%。')
          : ('精度 ' + (precision * 100).toFixed(1) + '%，达下限；'
            + '但下限**不替代**主要任务链逐条审核。')
    };
  }

  function num(v) {
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (typeof v === 'string' && v.trim() !== '' && isFinite(+v)) return +v;
    return null;
  }

  function tally(gold, reports) {
    var cov = coverage(gold);
    var ind = independence(gold);
    var arrr = (Array.isArray(reports) ? reports : []).map(score);
    var byLayer = {};
    arrr.forEach(function (r) { if (r.layer) byLayer[r.layer] = r; });
    var missingLayers = Object.keys(METRICS).filter(function (k) { return !byLayer[k]; });
    return {
      title: '独立金标准覆盖',
      isQualityScore: false,
      coverage: cov, independence: ind, reports: arrr,
      reportedLayers: Object.keys(byLayer).length,
      missingLayers: missingLayers,
      missingLayerLabels: missingLayers.map(function (k) { return METRICS[k].zh; }),
      belowFloor: arrr.filter(function (r) { return r.ok === false && r.reason == null; }).length,
      deletedSamples: arrr.filter(function (r) { return r.deletedSamples; }).length,
      note: '≥98%/95% 是下限，不替代主要任务链逐条审核；不删失败样本提高分数。'
        + '候选生成过程不能同时写自己的标准答案。',
      summary: cov.coveredCount + '/' + cov.total + ' 个分层已覆盖（缺：'
        + (cov.missingLabels.join('、') || '无') + '）；'
        + Object.keys(METRICS).length + ' 个维度里已报告 ' + Object.keys(byLayer).length
        + ' 个' + (missingLayers.length ? '（缺：' + missingLayers.map(function (k) { return METRICS[k].zh; }).join('、') + '）' : '')
        + '；独立性' + (ind.ok ? '成立' : '**不成立**')
    };
  }

  var API = { VERSION: VERSION, STRATA: STRATA, METRICS: METRICS, FLOOR: FLOOR,
    coverage: coverage, independence: independence, score: score, tally: tally };
  g.CLSkyGoldStandard = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
