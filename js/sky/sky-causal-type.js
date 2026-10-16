(function (g) {
  'use strict';

  var VERSION = '1';

  var TYPES = {
    trigger: {
      code: 'trigger', zh: '直接触发', short: '触发', tone: 'strong',
      hint: 'A 的发生直接引起 B（原文写出机制）。这是最强的一类因果。'
    },
    necessary: {
      code: 'necessary', zh: '必要条件', short: '必要', tone: 'strong',
      hint: '没有 A 则 B 不成立（原文写出必要性）。'
    },
    contributing: {
      code: 'contributing', zh: '促成条件', short: '促成', tone: 'medium',
      hint: 'A 使 B 更容易发生，但不是唯一原因。'
    },
    believed: {
      code: 'believed', zh: '人物认为的因果', short: '人物认为', tone: 'weak',
      hint: '这是人物的判断或归因，不是叙述者确认的事实。读者不得当作已证实的因果。'
    },
    inferred: {
      code: 'inferred', zh: '分析推测', short: '推测', tone: 'weak',
      hint: '这是分析者的推断，原文没有直接写出机制。'
    },
    sequence: {
      code: 'sequence', zh: '纯先后', short: '先后', tone: 'none',
      hint: '两件事只是先后发生。相邻、同场、共同演员与「随后」都不足以建立因果。'
    },
    attribution: {
      code: 'attribution', zh: '归功与评价', short: '归功', tone: 'none',
      hint: '这是对功劳的归认或评价（某某曰"此人之功"），不是因果机制。不得当作因果边保留。'
    },
    counterfactual: {
      code: 'counterfactual', zh: '反事实（审阅问题）', short: '反事实', tone: 'none',
      hint: '「若…则…」是审阅提问，不是已发生的事实。不能自动生成事实边。'
    },
    unknown: {
      code: 'unknown', zh: '类型未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断因果类型的文字。未标明不等于直接触发。'
    }
  };

  var COUNTERFACTUAL = /若(不|无|没有|非|未)|倘若|假如|假使|如果(不|无|没有)|否则|不然|设若|纵(使|然)|假设.{0,12}(则|就)|早(已)?(失|亡|败)/;
  var ATTRIBUTION = /归功(于|给)|归美|推功|追认|褒奖|称颂|此.{0,8}之功|(有功|之功).{0,6}(重赏|加赏|赏赐)/;
  var BELIEVED = /(以为|认为|自以|误以为|疑心|疑是|只道|只当|错认|归咎|归罪|怪罪|迁怒)/;
  var INFERRED = /推测|推断|implies|估计|大概|想必|应是|当是|可见|说明|暗示/;
  var SEQUENCE = /随后|之后|其后|既而|接着|翌日|次日|俄而|少顷|方才|然后|乃遂|乃即|遂即|先是|过后/;
  var TRIGGER = /于是|遂|因此|故而|以致|致使|致使|引发|trigger|直接导致|立时|当即/;
  var NECESSARY = /非.{0,8}不可|必须|唯有|只有|若无|没有.{0,8}就不能|不可或缺|必要/;
  var CONTRIBUTING = /促成|有助于|利于|为.{0,6}创造条件|加速|推动|助长|铺垫/;

  function str(v) { return typeof v === 'string' ? v : ''; }

  function textOf(edge) {
    edge = edge || {};
    return [edge.description, edge.desc, edge.quote, edge.reason, edge.basisNote]
      .map(str).join(' ');
  }

  function of(edge, opts) {
    opts = opts || {};
    var declared = str(edge && (edge.causalType || edge.causeType || edge.type));
    if (declared && TYPES[declared]) return finish(TYPES[declared], 'declared', null);
    var blob = textOf(edge);
    if (!blob.trim()) return finish(TYPES.unknown, 'no_text', null);
    var selfText = [edge.description, edge.desc, edge.reason, edge.basisNote].map(str).join(' ');
    var mAttr = ATTRIBUTION.exec(selfText);
    if (mAttr) return finish(TYPES.attribution, 'marker', mAttr[0]);
    var mCf = COUNTERFACTUAL.exec(selfText);
    if (mCf) return finish(TYPES.counterfactual, 'marker', mCf[0]);
    var order = [
      ['believed', BELIEVED], ['inferred', INFERRED],
      ['necessary', NECESSARY], ['contributing', CONTRIBUTING],
      ['trigger', TRIGGER], ['sequence', SEQUENCE]
    ];
    for (var i = 0; i < order.length; i++) {
      var m = order[i][1].exec(blob);
      if (m) return finish(TYPES[order[i][0]], 'marker', m[0]);
    }
    return finish(TYPES.unknown, 'no_marker', null);
  }

  function finish(entry, basis, marker) {
    var out = {
      code: entry.code, label: entry.zh, short: entry.short, hint: entry.hint, tone: entry.tone,
      basis: basis,
      isEstablishedCausality: entry.code === 'trigger' || entry.code === 'necessary'
        || entry.code === 'contributing',
      needsAttribution: entry.code === 'believed' || entry.code === 'inferred',
      mustNotBeCausalEdge: entry.code === 'attribution' || entry.code === 'counterfactual'
        || entry.code === 'sequence',
      version: VERSION
    };
    if (marker) out.marker = marker;
    return out;
  }

  function endpointsOk(edge) {
    var from = str(edge && (edge.sourceId || edge.fromEventId || edge.from));
    var to = str(edge && (edge.targetId || edge.toEventId || edge.to));
    return { from: !!from, to: !!to, both: !!(from && to),
      unresolved: !!edge && (edge.resolved === false || edge.referenceStatus === 'unresolved'
        || edge.referenceStatus === 'unresolved_or_conflicting') };
  }

  function badge(edge) {
    var s = of(edge);
    var mark = s.code === 'trigger' ? '⇒' : s.code === 'necessary' ? '⇔'
      : s.code === 'contributing' ? '⇢' : s.code === 'attribution' ? '★'
      : s.code === 'counterfactual' ? '?' : s.code === 'sequence' ? '⋯'
      : s.code === 'believed' ? '❞' : s.code === 'inferred' ? '∴' : '?';
    return { text: mark + ' ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: mark };
  }

  function tally(edges) {
    var out = { total: 0, byCode: {}, established: 0, mustNotBeEdge: 0,
      unresolvedEndpoints: 0, noMechanism: 0 };
    (Array.isArray(edges) ? edges : []).forEach(function (e) {
      var s = of(e);
      out.total++;
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (s.isEstablishedCausality) out.established++;
      if (s.mustNotBeCausalEdge) out.mustNotBeEdge++;
      if (s.basis === 'no_marker') out.noMechanism++;
      if (endpointsOk(e).unresolved) out.unresolvedEndpoints++;
    });
    out.title = '因果类型分布';
    out.note = '这是类型计数，不是因果质量分。相邻/同场/共同演员/「随后」都不足以建立因果。';
    out.isCausalityScore = false;
    out.summary = out.total + ' 条边中 ' + out.established + ' 条写出了机制；'
      + out.mustNotBeEdge + ' 条属归功/评价、反事实或纯先后 —— 按计划**不应作为因果边保留**。';
    return out;
  }

  var API = { VERSION: VERSION, TYPES: TYPES, of: of, badge: badge, tally: tally,
    endpointsOk: endpointsOk, _markers: { COUNTERFACTUAL: COUNTERFACTUAL, ATTRIBUTION: ATTRIBUTION,
      BELIEVED: BELIEVED, INFERRED: INFERRED, SEQUENCE: SEQUENCE, TRIGGER: TRIGGER,
      NECESSARY: NECESSARY, CONTRIBUTING: CONTRIBUTING } };
  g.CLSkyCausalType = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
