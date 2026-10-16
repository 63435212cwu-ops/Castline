(function (g) {
  'use strict';

  var VERSION = '1';

  var STAGES = {
    setup: { code: 'setup', zh: '铺设', short: '铺设', tone: 'open',
      hint: '在正文里埋下了尚未解释的东西。' },
    hint: { code: 'hint', zh: '提示', short: '提示', tone: 'open',
      hint: '对已有线索再给一次提示，仍未解释。' },
    misdirect: { code: 'misdirect', zh: '误导', short: '误导', tone: 'warn',
      hint: '文本有意把读者引向错误方向。它是手法，不是缺陷，但必须标明。' },
    delayed: { code: 'delayed', zh: '延迟解释', short: '延迟', tone: 'open',
      hint: '已经提示过一次以上、解释被有意推后。' },
    payoff: { code: 'payoff', zh: '兑现', short: '兑现', tone: 'closed',
      hint: '两端齐全（铺设与兑现都能回到原文），生命周期闭合。' },
    partial: { code: 'partial', zh: '部分兑现', short: '部分', tone: 'warn',
      hint: '只兑现了一部分，仍有未解释的残留。' },
    restart: { code: 'restart', zh: '重启', short: '重启', tone: 'warn',
      hint: '同一伏笔被重新铺设（旧线未收又开新线），需要单独看。' },
    open: { code: 'open', zh: '未回收', short: '未回收', tone: 'neutral',
      hint: '尚未回收。未完稿的作品里这不是缺陷；已完结作品里才需要追问。' },
    claimed_unbacked: { code: 'claimed_unbacked', zh: '声称已兑现但缺兑现端', short: '缺兑现端', tone: 'bad',
      hint: '记录标了 resolved，但没有 payoff 事件可以跳回原文。这是数据自相矛盾，不能当作已兑现。' },
    broken: { code: 'broken', zh: '引用断裂', short: '断裂', tone: 'bad',
      hint: '引用本身解析不出来（端点缺失或冲突）。与「未回收」是两件事。' },
    unknown: { code: 'unknown', zh: '阶段未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断阶段的信息。未标明不等于已兑现。' }
  };

  var CLUE_TYPE = {
    setup_payoff: 'payoff',
    resource_setup_payoff: 'payoff',
    promise_payoff: 'payoff',
    announced_sign_payoff: 'payoff',
    narrative_prolepsis: 'hint',
    diagnostic_evidence: 'hint',
    misdirection: 'misdirect',
    red_herring: 'misdirect',
    delayed_explanation: 'delayed',
    partial_payoff: 'partial',
    restart: 'restart',
    open: 'open',
    unresolved: 'open'
  };

  function str(v) { return typeof v === 'string' ? v : ''; }

  function anchorsOf(clue) {
    clue = clue || {};
    var seed = str(clue.seedEventId) || str(clue.foreshadowEventId) || str(clue.seedId);
    var payoff = str(clue.payoffEventId) || str(clue.resolveEventId) || str(clue.payoffId);
    if (!seed && Array.isArray(clue.eventIds) && clue.eventIds.length) seed = str(clue.eventIds[0]);
    if (!seed && clue.seedIndex != null) seed = 'idx:' + clue.seedIndex;
    if (!payoff && clue.payoffIndex != null) payoff = 'idx:' + clue.payoffIndex;
    return { seed: seed || null, payoff: payoff || null };
  }

  function of(clue, opts) {
    opts = opts || {};
    var a = anchorsOf(clue);
    var declared = str(clue && (clue.clueType || clue.stage || clue.lifecycle));
    var resolvedFlag = !!(clue && clue.resolved === true);
    var refStatus = str(clue && clue.referenceStatus);

    if (refStatus === 'unresolved_or_conflicting') {
      return finish(STAGES.broken, 'reference_status', refStatus, a);
    }
    if (a.seed && a.payoff) {
      var byType = CLUE_TYPE[declared];
      if (byType && byType !== 'payoff') return finish(STAGES[byType], 'clue_type', declared, a);
      return finish(STAGES.payoff, 'anchors_complete', null, a);
    }
    var claimedResolved = resolvedFlag
      || str(clue && clue.declaredStatus) === 'resolved'
      || str(clue && clue.referenceStatus) === 'resolved';
    var claimsButMissingPayoff = claimedResolved
      || str(clue && clue.declaredStatus) === 'unresolved'
      || str(clue && clue.stage) === 'pending';
    if (claimsButMissingPayoff && a.seed && !a.payoff) {
      return finish(STAGES.claimed_unbacked, 'claimed_without_payoff',
        str(clue && clue.declaredStatus) || refStatus || 'resolved', a);
    }
    var mapped = CLUE_TYPE[declared];
    if (mapped && STAGES[mapped]) return finish(STAGES[mapped], 'clue_type', declared, a);
    if (a.seed && !a.payoff) return finish(STAGES.open, 'seed_only', null, a);
    return finish(STAGES.unknown, 'no_anchor', null, a);
  }

  function finish(entry, basis, marker, anchors) {
    var out = {
      code: entry.code, label: entry.zh, short: entry.short, hint: entry.hint, tone: entry.tone,
      basis: basis,
      anchors: anchors,
      bothEndsVerifiable: !!(anchors && anchors.seed && anchors.payoff),
      closed: entry.code === 'payoff',
      isDefect: entry.code === 'claimed_unbacked' || entry.code === 'broken',
      openIsNotDefect: entry.code === 'open',
      version: VERSION
    };
    if (marker) out.marker = marker;
    return out;
  }

  function badge(clue) {
    var s = of(clue);
    var mark = s.code === 'payoff' ? '✓' : s.code === 'claimed_unbacked' ? '⚠'
      : s.code === 'broken' ? '✗' : s.code === 'open' ? '…'
      : s.code === 'misdirect' ? '↯' : s.code === 'partial' ? '◐'
      : s.code === 'restart' ? '↻' : s.code === 'setup' ? '·'
      : s.code === 'hint' ? '˙' : s.code === 'delayed' ? '⋯' : '?';
    return { text: mark + ' ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: mark };
  }

  function tally(clues) {
    var arrc = Array.isArray(clues) ? clues : [];
    var out = { total: arrc.length, byCode: {}, bothEnds: 0, defects: 0, open: 0,
      claimedUnbacked: 0 };
    arrc.forEach(function (c) {
      var s = of(c);
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (s.bothEndsVerifiable) out.bothEnds++;
      if (s.isDefect) out.defects++;
      if (s.code === 'open') out.open++;
      if (s.code === 'claimed_unbacked') out.claimedUnbacked++;
    });
    out.title = '伏笔生命周期分布';
    out.isQualityScore = false;
    if (!arrc.length) {
      out.summary = '本作品 0 条伏笔提取 —— 这首先说明「缺乏处置证据」，不能据此宣称作品没有伏笔。';
      out.lacksDispositionEvidence = true;
      out.mustNotClaim = '本作品无伏笔';
    } else {
      out.lacksDispositionEvidence = false;
      out.summary = arrc.length + ' 条中 ' + out.bothEnds + ' 条两端可跳原文；'
        + out.claimedUnbacked + ' 条声称已兑现但缺兑现端；'
        + out.open + ' 条未回收（未完稿里不算缺陷）。';
    }
    return out;
  }

  var API = { VERSION: VERSION, STAGES: STAGES, CLUE_TYPE: CLUE_TYPE, of: of, badge: badge,
    tally: tally, anchorsOf: anchorsOf };
  g.CLSkyForeshadowStage = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
