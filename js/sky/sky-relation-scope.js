(function (g) {
  'use strict';

  var VERSION = '1';

  var KINDS = {
    kinship: { code: 'kinship', zh: '亲缘', tone: 'kin',
      hint: '血缘或姻亲关系。范围应写清是哪一支、隔几代。' },
    mentorship: { code: 'mentorship', zh: '师徒', tone: 'mentor',
      hint: '授受关系。范围应写清是正式拜师还是指点。' },
    alliance: { code: 'alliance', zh: '同盟', tone: 'ally',
      hint: '共同目标的联合。范围应写清结盟时限与条件。' },
    hostility: { code: 'hostility', zh: '敌对', tone: 'enemy',
      hint: '对抗关系。范围应写清敌对起于何时、是否解除。' },
    exploitation: { code: 'exploitation', zh: '利用', tone: 'use',
      hint: '一方把另一方当工具。范围应写清利用的是什么、持续多久。' },
    affection: { code: 'affection', zh: '情感', tone: 'love',
      hint: '情感联结。范围应写清是单向还是双向。' },
    secret: { code: 'secret', zh: '隐秘', tone: 'secret',
      hint: '有意隐藏的关系。它不等于不存在证据 —— 隐藏本身常在原文写明。' },
    copresence: { code: 'copresence', zh: '同场（非关系）', tone: 'none',
      hint: '两人只是同时出现在一处。同场不构成关系，也不得附任意同场引句当作关系证据。' },
    institutional: { code: 'institutional', zh: '制度关系', tone: 'inst',
      hint: '官署、朝堂、阵营里的位置关系（同僚/上下级/君臣/主仆）。不是计划七类之一，但确实存在。' },
    association: { code: 'association', zh: '泛交往', tone: 'assoc',
      hint: '相识、共事、协作、共处这类泛泛交往。强弱与性质都不明确，需要人工看。' },
    other: { code: 'other', zh: '其他类型', tone: 'other',
      hint: '现有分类里没有对应项。它可能是真实关系，只是尚未归类。' }
  };

  var KIND_PATTERNS = [
    ['copresence', /^同场$|同场|在场|同时出现|无明确直接互动/],
    ['institutional', /同僚|上下级|君臣|主仆|同朝|同阵营|同部|属官|旧部|帐下|麾下/],
    ['association', /相识|共事|协作|共处|宾客|故交|旧识|往来|结交|引荐/],
    ['kinship', /亲|父|母|子|兄|弟|姐|妹|夫|妻|族|舅|姨|叔|伯|祖|养|嗣|姻/],
    ['mentorship', /师|徒|门|弟子|传人|衣钵/],
    ['exploitation', /利用|交易|驱使|棋子|工具|借势|挟/],
    ['alliance', /同盟|盟友|结义|同道|合作|同谋|联盟|共谋/],
    ['hostility', /敌对|对抗|对立|仇|敌|反目|背叛|嫌隙|冲突|争/],
    ['affection', /情感|爱|恋|慕|恩|义|友|情/]
  ];

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0 && v.trim() !== '—';
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function kindOf(rel) {
    rel = rel || {};
    var k = str(rel.kind || rel.type || rel.relationType);
    var line = str(rel.line);
    var hidden = str(rel.hidden);
    var isSecret = (line === '暗线') || present(hidden);
    if (!k) return isSecret ? KINDS.secret : KINDS.other;
    var base = null;
    for (var i = 0; i < KIND_PATTERNS.length; i++) {
      if (KIND_PATTERNS[i][1].test(k)) { base = KIND_PATTERNS[i][0]; break; }
    }
    if (isSecret) {
      var out = Object.create(KINDS.secret);
      out.baseCode = base;
      return out;
    }
    return base ? KINDS[base] : KINDS.other;
  }

  function evidenceOf(rel) {
    rel = rel || {};
    if (rel.quoteVerified === true) return { code: 'anchored', label: '原文锚点',
      hint: '这条关系有已核验的原文引句可跳回。' };
    var refs = [].concat(rel.sourceRefs || [], rel.evidenceRefs || []);
    for (var i = 0; i < refs.length; i++) {
      var r = refs[i];
      if (r && typeof r === 'object' && r.verified === true && r.status === 'verified' &&
          (r.match == null || r.match === 'exact') && r.sourceId && r.textHash &&
          typeof r.start === 'number' && typeof r.end === 'number' &&
          r.end > r.start && str(r.quote)) {
        return { code: 'anchored', label: '原文锚点', hint: '这条关系有已核验的原文引句可跳回。' };
      }
    }
    return { code: 'inherited-pending', label: '继承 · 待核验',
      hint: '这条关系没有已核验的原文引句。描述写得好不构成证据；不得附任意同场引句充当证据。' };
  }

  function scopeOf(rel) {
    rel = rel || {};
    var eventIds = [].concat(rel.eventIds || [], rel.events || []);
    var hasEvents = eventIds.filter(present).length > 0;
    var hasRange = present(rel.fromChapter) || present(rel.toChapter)
      || present(rel.chapterRange) || present(rel.chapterSpan)
      || (present(rel.scope) && /章|时段|区间/.test(str(rel.scope)));
    if (hasEvents || hasRange) {
      return { code: 'atTime', label: '限定时段', events: eventIds,
        hint: '这条关系给出了时间范围或事件锚点，可以按时刻呈现。' };
    }
    return { code: 'bookSummary', label: '全书汇总',
      hint: '这条关系是跨越全书的汇总结论，不对应某一时刻。罗盘不得把它当成某时刻的关系。' };
  }

  function of(rel) {
    if (!rel || typeof rel !== 'object' || Array.isArray(rel)) rel = {};
    var kind = kindOf(rel);
    var ev = evidenceOf(rel);
    var sc = scopeOf(rel);
    return {
      kind: kind.code, kindLabel: kind.zh, kindHint: kind.hint, kindTone: kind.tone,
      baseKind: kind.baseCode || null,
      isCopresence: kind.code === 'copresence',
      needsManualKind: kind.code === 'other',
      evidence: ev.code, evidenceLabel: ev.label, evidenceHint: ev.hint,
      anchored: ev.code === 'anchored',
      mustShowPending: ev.code !== 'anchored',
      scope: sc.code, scopeLabel: sc.label, scopeHint: sc.hint,
      isBookSummary: sc.code === 'bookSummary',
      strength: (typeof rel.strength === 'number' && isFinite(rel.strength)) ? rel.strength : null,
      strengthIsEvidence: false,
      version: VERSION
    };
  }

  function badge(rel) {
    var s = of(rel);
    var mark = s.evidence === 'anchored' ? '◆' : '◇';
    var scopeMark = s.isBookSummary ? '全' : '时';
    return {
      text: mark + ' ' + s.kindLabel + ' · ' + scopeMark,
      label: s.kindLabel, evidenceLabel: s.evidenceLabel, scopeLabel: s.scopeLabel,
      code: s.kind, evidence: s.evidence, scope: s.scope, mark: mark,
      tone: s.anchored ? 'anchored' : 'pending'
    };
  }

  function tally(rels) {
    var arrr = Array.isArray(rels) ? rels : [];
    var out = { total: arrr.length, byKind: {}, anchored: 0, pending: 0,
      copresence: 0, bookSummary: 0, atTime: 0, secret: 0, other: 0 };
    arrr.forEach(function (r) {
      var s = of(r);
      out.byKind[s.kind] = (out.byKind[s.kind] || 0) + 1;
      if (s.anchored) out.anchored++; else out.pending++;
      if (s.isCopresence) out.copresence++;
      if (s.isBookSummary) out.bookSummary++; else out.atTime++;
      if (s.kind === 'secret') out.secret++;
      if (s.needsManualKind) out.other++;
    });
    out.title = '关系构成';
    out.isQualityScore = false;
    out.note = '这是关系构成计数，不是质量分。来源分数（strength）不是证据强度；'
      + '同场不构成关系；无锚点的关系须显式标为待核。';
    if (!arrr.length) {
      out.summary = '本作品 0 条关系记录 —— 这首先说明缺乏处置证据，不能据此宣称人物之间没有关系。';
      out.lacksDispositionEvidence = true;
    } else if (!out.anchored) {
      out.summary = arrr.length + ' 条关系里没有任何一条有已核验的原文锚点（全部为继承待核）；'
        + out.bookSummary + ' 条是全书汇总、' + out.atTime + ' 条限定时段；'
        + out.copresence + ' 条只是同场（不构成关系）。';
      out.allPending = true;
    } else {
      out.summary = arrr.length + ' 条关系里 ' + out.anchored + ' 条有原文锚点、'
        + out.pending + ' 条继承待核；' + out.bookSummary + ' 条是全书汇总。';
      out.allPending = false;
    }
    return out;
  }

  var API = { VERSION: VERSION, KINDS: KINDS, of: of, badge: badge, tally: tally,
    kindOf: kindOf, evidenceOf: evidenceOf, scopeOf: scopeOf };
  g.CLSkyRelationScope = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
