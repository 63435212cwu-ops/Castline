(function (g) {
  'use strict';

  var VERSION = '1';

  var KINDS = {
    deception: {
      code: 'deception', zh: '明知虚假的陈述', short: '欺瞒', tone: 'deception',
      hint: '记录里标明这是说给他人听的假话（谎称/诈/骗/佯装）。读者不得把它当事实。'
    },
    inference: {
      code: 'inference', zh: '人物的推理', short: '推理', tone: 'inference',
      hint: '记录写的是某个人的推断，不是已发生的事，也不是叙述者的断言。'
    },
    claim: {
      code: 'claim', zh: '人物的主张', short: '主张', tone: 'claim',
      hint: '记录写的是某个人说出的主张/要求/承诺；主张本身不等于事实成立。'
    },
    occurrence: {
      code: 'occurrence', zh: '实际发生', short: '发生', tone: 'occurrence',
      hint: '记录描述的是一次状态改变（谁做了什么、结果如何）。'
    },
    unknown: {
      code: 'unknown', zh: '类型未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断「主张还是发生」的文字。未标明不等于已发生。'
    }
  };

  var DECEPTION = /谎称|谎报|撒谎|诈(供|问|称|骗|降|死)|欺骗|骗得|骗取|佯装|假装|伪装|捏造|诬告|诬陷|栽赃|伪(书|证|造)|假冒|冒称|说谎|撒谎/;
  var NEGATED = /(未|没有|没|不曾|并未|并非|不是|绝非)[^。；，]{0,4}(说谎|撒谎|欺骗|伪装|假装)/;
  var JUDGING_OTHER = /(断言|判断|认为|确认|指出|质疑|怀疑|识破|看穿|揭穿|揭示|证实|认定|察觉)[^。；]{0,16}(说谎|撒谎|欺骗)/;
  var INFERENCE = /推理|推断|推测|猜想|猜测|怀疑|质疑|假设|假定|判断|断定|估计|臆测|揣测|复盘|分析出|推出/;
  var CLAIM = /主张|声称|宣称|要求|请求|许诺|承诺|答应|劝|劝谏|谏|建议|提议|坚称|自称|表示|陈述|申辩|辩称|否认|承认/;

  function str(v) { return typeof v === 'string' ? v : ''; }

  function textOf(rec) {
    rec = rec || {};
    return [rec.title, rec.name, rec.summary, rec.quote, rec.action, rec.goal]
      .map(str).join(' ');
  }

  function classify(rec, opts) {
    opts = opts || {};
    var declared = str(rec && (rec.claimType || rec.epistemicType || rec.recordType));
    if (declared && KINDS[declared]) return finish(KINDS[declared], 'declared', null);
    var blob = textOf(rec);
    if (!blob.trim()) return finish(KINDS.unknown, 'no_text', null);
    var hit, m;
    var forDeception = blob;
    if (NEGATED.test(forDeception) || JUDGING_OTHER.test(forDeception)) {
      forDeception = forDeception.replace(/说谎|撒谎/g, '　');
    }
    if ((m = DECEPTION.exec(forDeception))) hit = ['deception', m[0]];
    else if ((m = INFERENCE.exec(blob))) hit = ['inference', m[0]];
    else if ((m = CLAIM.exec(blob))) hit = ['claim', m[0]];
    if (!hit) {
      return finish(KINDS.unknown, 'no_marker', null);
    }
    return finish(KINDS[hit[0]], 'marker', hit[1]);
  }

  function finish(entry, basis, marker) {
    var out = {
      code: entry.code, label: entry.zh, short: entry.short, hint: entry.hint, tone: entry.tone,
      basis: basis,
      isOccurrence: entry.code === 'occurrence',
      needsAttribution: entry.code !== 'occurrence' && entry.code !== 'unknown',
      isDeceptive: entry.code === 'deception',
      version: VERSION
    };
    if (marker) out.marker = marker;
    return out;
  }

  function badge(rec) {
    var s = classify(rec);
    var mark = s.code === 'deception' ? '⚠' : s.code === 'inference' ? '∴'
      : s.code === 'claim' ? '❝' : s.code === 'occurrence' ? '◆' : '?';
    return { text: mark + ' ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: mark };
  }

  function tally(records) {
    var out = { total: 0, byCode: {}, attributed: 0, deceptive: 0, unknown: 0 };
    (Array.isArray(records) ? records : []).forEach(function (r) {
      var s = classify(r);
      out.total++;
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (s.needsAttribution) out.attributed++;
      if (s.isDeceptive) out.deceptive++;
      if (s.code === 'unknown') out.unknown++;
    });
    out.title = '记录类型分布';
    out.note = '这是认识论类型计数，不是内容质量分；「未标明」不等于已发生。';
    out.isQualityScore = false;
    return out;
  }

  function isClaimOnly(rec) {
    var s = classify(rec);
    return s.code === 'claim' || s.code === 'inference' || s.code === 'deception';
  }

  var API = { VERSION: VERSION, KINDS: KINDS, classify: classify, badge: badge,
    tally: tally, isClaimOnly: isClaimOnly, _markers: { DECEPTION: DECEPTION, INFERENCE: INFERENCE, CLAIM: CLAIM,
      NEGATED: NEGATED, JUDGING_OTHER: JUDGING_OTHER } };
  g.CLSkyEventClaim = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
