(function (g) {
  'use strict';

  var VERSION = '1';

  var FACETS = {
    ability: { code: 'ability', zh: '能力', tone: 'ability', hint: '本事、修为、技艺的改变。' },
    resource: { code: 'resource', zh: '资源', tone: 'resource', hint: '财物、人手、法器、地盘的增减。' },
    identity: { code: 'identity', zh: '身份', tone: 'identity', hint: '官职、名分、归属的改变。' },
    goal: { code: 'goal', zh: '目标', tone: 'goal', hint: '想要的东西变了。' },
    stance: { code: 'stance', zh: '立场', tone: 'stance', hint: '站在哪一边、对谁的态度。' },
    cost: { code: 'cost', zh: '代价', tone: 'cost', hint: '为此付出了什么。' },
    unknown: { code: 'unknown', zh: '面向未标明', tone: 'unknown', hint: '记录没有说明这是哪个面的变化。' }
  };

  var EMOTION = /情绪|心情|心理|恐惧|害怕|愤怒|大怒|悲痛|惊喜|压力|兴致|指望|防线|绝望|紧张|激动|惭愧|汗颜|尴尬|欢喜|哀伤/;
  var OTHERS = /(众人|旁人|大家|他人|外人|百官|群臣|世人|时人|后人)[^。；]{0,12}(评价|看法|议论|称许|称颂|讥|笑|赞|畏|服)/;
  var STABLE = /性格|人格|本性|天性|脾气|为人|品性|一贯|素来|向来/;

  var IRREVERSIBLE = /(死|亡|殁|卒|殒|斩|处决|自尽|殉)/;
  var REVERSIBLE = /(复职|官复原职|恢复|痊愈|伤愈|获释|释放|重获|归还|赎回|复位|平反)/;

  function str(v) { return typeof v === 'string' ? v : ''; }

  function endsOf(rec) {
    rec = rec || {};
    var inner = (rec.transition && typeof rec.transition === 'object') ? rec.transition : null;
    var before = str(rec.before) || str(rec.after ? '' : '') || (inner ? str(inner.before) : '');
    var after = str(rec.after) || (inner ? str(inner.after) : '');
    if (!before) before = str(rec.from);
    if (!after) after = str(rec.to);
    return { before: before || null, after: after || null };
  }

  function facetOf(rec) {
    var a = str(rec && (rec.attribute || rec.attr || rec.facet));
    if (!a) return FACETS.unknown;
    if (/能力|修为|本事|技艺|武艺|法力|境界|战力|术/.test(a)) return FACETS.ability;
    if (/资源|财|银|钱|兵|人手|法器|地盘|粮|马|部曲/.test(a)) return FACETS.resource;
    if (/身份|官职|地位|名分|归属|封|爵|职/.test(a)) return FACETS.identity;
    if (/目标|目的|图谋|志向|打算/.test(a)) return FACETS.goal;
    if (/立场|阵营|态度|所属|所事|投|背|联盟/.test(a)) return FACETS.stance;
    if (/代价|失去|牺牲|付出|损失/.test(a)) return FACETS.cost;
    return FACETS.unknown;
  }

  function of(rec, opts) {
    opts = opts || {};
    var ends = endsOf(rec);
    var attr = str(rec && (rec.attribute || rec.attr || rec.facet));
    var summary = str(rec && (rec.summary || rec.description));
    var blob = attr + ' ' + summary;
    var hasBoth = !!(ends.before && ends.after);

    if (EMOTION.test(attr)) {
      return finish('emotion', 'attribute_emotion', ends, rec, attr);
    }
    if (OTHERS.test(blob)) {
      return finish('others', 'others_evaluation', ends, rec, attr);
    }
    if (STABLE.test(blob) && !hasBoth) {
      return finish('stable', 'stable_personality', ends, rec, attr);
    }
    if (hasBoth) {
      return finish('transition', 'both_ends', ends, rec, attr);
    }
    return finish('incomplete', 'missing_end', ends, rec, attr);
  }

  function finish(code, basis, ends, rec, attr) {
    var zh = { transition: '真实转变', emotion: '情绪瞬间', others: '旁人评价',
      stable: '稳定人格', incomplete: '前后依据不全' }[code];
    var hint = {
      transition: '两端（前/后）都有原文依据，可以画成长箭头。',
      emotion: '这是一次性的情绪反应，不是成长。情绪瞬间必须与稳定人格分开。',
      others: '这是旁人怎么看他，不是他自己的状态变化。',
      stable: '这是持续的人格属性，本身不是一次变化。',
      incomplete: '缺少前值或后值。无前后依据不画成长箭头。'
    }[code];
    var facet = facetOf(rec);
    var rev = reversibility(rec, ends);
    var declared = str(rec && (rec.basis || rec.provenance));
    var evidential = declared === 'explicit' || declared === 'explicit_text'
      || declared === 'assistant-reviewed-source' ? 'explicit'
      : declared === 'inferred' || declared === 'synthesis' ? 'inferred' : 'unknown';
    return {
      code: code, label: zh, hint: hint,
      basis: basis,
      ends: ends,
      facet: facet.code, facetLabel: facet.zh, facetHint: facet.hint,
      reversibility: rev.code, reversibilityLabel: rev.label, reversibilityHint: rev.hint,
      evidential: evidential,
      canDrawGrowth: code === 'transition',
      isEmotionalMoment: code === 'emotion',
      isOthersEvaluation: code === 'others',
      mustNotCountAsGrowth: code !== 'transition',
      version: VERSION
    };
  }

  function reversibility(rec, ends) {
    var blob = str(rec && (rec.attribute || '')) + ' ' + str(rec && (rec.summary || ''))
      + ' ' + (ends.before || '') + ' ' + (ends.after || '');
    if (IRREVERSIBLE.test(blob)) return { code: 'irreversible', label: '不可逆',
      hint: '这一步走完就回不去（如死亡、处决）。' };
    if (REVERSIBLE.test(blob)) return { code: 'reversible', label: '可逆',
      hint: '这一步可以复原（如复职、痊愈、获释）。' };
    return { code: 'unknown', label: '未标明', hint: '记录没有说明这一步能不能复原。' };
  }

  function badge(rec) {
    var s = of(rec);
    var mark = s.code === 'transition' ? '→' : s.code === 'emotion' ? '～'
      : s.code === 'others' ? '❞' : s.code === 'stable' ? '＝' : '…';
    return { text: mark + ' ' + s.label, label: s.label, code: s.code, mark: mark,
      facetLabel: s.facetLabel,
      reversibilityLabel: s.reversibilityLabel, tone: s.canDrawGrowth ? 'growth' : 'flat' };
  }

  function tally(records) {
    var arrr = Array.isArray(records) ? records : [];
    var out = { total: arrr.length, byCode: {}, byFacet: {}, drawable: 0,
      emotional: 0, others: 0, incomplete: 0, irreversible: 0 };
    arrr.forEach(function (r) {
      var s = of(r);
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      out.byFacet[s.facet] = (out.byFacet[s.facet] || 0) + 1;
      if (s.canDrawGrowth) out.drawable++;
      if (s.isEmotionalMoment) out.emotional++;
      if (s.isOthersEvaluation) out.others++;
      if (s.code === 'incomplete') out.incomplete++;
      if (s.reversibility === 'irreversible') out.irreversible++;
    });
    out.title = '状态记录构成';
    out.isGrowthScore = false;
    out.note = '这是记录构成计数，不是成长评分。情绪瞬间与旁人评价不得计入成长；'
      + '无前后依据不画成长箭头。';
    out.summary = arrr.length + ' 条状态记录里 ' + out.drawable + ' 条前后依据齐全可画成长箭头；'
      + out.emotional + ' 条是情绪瞬间；' + out.others + ' 条是旁人评价；'
      + out.incomplete + ' 条前后依据不全。';
    return out;
  }

  var API = { VERSION: VERSION, FACETS: FACETS, of: of, badge: badge, tally: tally,
    endsOf: endsOf, facetOf: facetOf, reversibility: reversibility };
  g.CLSkyStateTransition = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
