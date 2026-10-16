(function (g) {
  'use strict';

  var VERSION = '2';

  var STATES = {
    knows: { code: 'knows', zh: '知道', short: '知道', tone: 'positive',
      hint: '此人知道这件事，且有事件或明确叙述可依。' },
    believes: { code: 'believes', zh: '相信', short: '相信', tone: 'positive',
      hint: '此人相信这件事，但记录没有把它当作已确证的事实。' },
    misbelief: { code: 'misbelief', zh: '误信', short: '误信', tone: 'warn',
      hint: '此人信的是错的。误信必须与「相信」分开 —— 否则读者会把错信当事实。' },
    conceals: { code: 'conceals', zh: '隐瞒', short: '隐瞒', tone: 'warn',
      hint: '此人知道但有意不说。隐瞒是**行为**，不等于别人不知道。' },
    unaware: { code: 'unaware', zh: '明确不知', short: '不知', tone: 'neutral',
      hint: '原文明确写出此人不知道。注意：「沉默」不构成这一档。' },
    readerKnows: { code: 'readerKnows', zh: '读者已知', short: '读者已知', tone: 'reader',
      hint: '读者掌握了人物尚未掌握的信息。**不得**因此记为人物知道。' },
    narrator: { code: 'narrator', zh: '叙述者全知', short: '全知', tone: 'narrator',
      hint: '这是叙述者层面的信息，**不得灌给任何人物**。' },
    unknown: { code: 'unknown', zh: '认知未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断认知状态的依据。未标明不等于知情。' }
  };

  var UNCERTAIN = /[?？]|是否|是不是|难道|能否|可能|或许|未必|不一定|不能(?:认定|断定|确认)|无法(?:确认|判断)|(?:尚|仍)(?:未|不)(?:确认|确定)|假如|如果|倘若|假设/;
  var MISBELIEF = /误信|错以为|误认|误以为|被骗|上当|中计|受了?骗|假消息|谣言/;
  var CONCEALS = /隐瞒|瞒着|不说|不肯说|未告知|秘而不宣|藏起|按下不表/;
  var UNAWARE = /不知道|不知|未知|未闻|不曾听闻|毫不知情|蒙在鼓里|未曾听说/;
  var READER = /读者/;
  var NARRATOR = /叙述者|叙述层|旁白|全知/;
  var BELIEVES = /相信|认为|以为|觉得|料想|自认|断定/;
  var KNOWS = /知道|明白|清楚|知晓|得知|获悉|掌握/;
  var DENIED_COGNITION = new RegExp('(?:并非|并不是|不是|并没有|没有|从未|不曾|未曾|未|并未)[^，。；！？]{0,8}(?:' + MISBELIEF.source + '|' + KNOWS.source + ')');

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    return true;
  }

  function of(rec, opts) {
    opts = opts || {};
    var declared = str(rec && (rec.status || rec.knowledgeStatus || rec.state));
    var mapped = {
      known: 'knows', knows: 'knows', aware: 'knows',
      believes: 'believes', believed: 'believes',
      misbelief: 'misbelief', false_belief: 'misbelief', deceived: 'misbelief',
      conceals: 'conceals', withheld: 'conceals',
      unaware: 'unaware', unknown: 'unaware', does_not_know: 'unaware', not_known: 'unaware',
      reader: 'readerKnows', reader_knows: 'readerKnows',
      narrator: 'narrator', omniscient: 'narrator'
    }[declared];
    if (mapped && STATES[mapped]) return finish(STATES[mapped], 'declared', declared, rec);

    var blob = str(rec && (rec.knows || rec.text || rec.value || rec.summary || rec.fact));
    if (!blob.trim()) {
      var unaware = UNAWARE.exec(str(rec && rec.unknownTo));
      if (unaware && !UNCERTAIN.test(str(rec.unknownTo))) return finish(STATES.unaware, 'marker', unaware[0], rec);
      return finish(STATES.unknown, 'no_text', null, rec);
    }

    if (UNCERTAIN.test(blob)) return finish(STATES.unknown, 'uncertain_text', null, rec);
    if (DENIED_COGNITION.test(blob)) return finish(STATES.unknown, 'negated_text', null, rec);

    var m;
    if ((m = MISBELIEF.exec(blob))) return finish(STATES.misbelief, 'marker', m[0], rec);
    if ((m = CONCEALS.exec(blob))) return finish(STATES.conceals, 'marker', m[0], rec);
    if ((m = READER.exec(blob))) return finish(STATES.readerKnows, 'marker', m[0], rec);
    if ((m = NARRATOR.exec(blob))) return finish(STATES.narrator, 'marker', m[0], rec);
    if ((m = UNAWARE.exec(blob))) return finish(STATES.unaware, 'marker', m[0], rec);
    if ((m = BELIEVES.exec(blob))) return finish(STATES.believes, 'marker', m[0], rec);
    if ((m = KNOWS.exec(blob))) return finish(STATES.knows, 'marker', m[0], rec);
    return finish(STATES.unknown, 'no_marker', null, rec);
  }

  function finish(entry, basis, marker, rec) {
    var who = str(rec && (rec.who || rec.character || rec.knower));
    return {
      code: entry.code, label: entry.zh, short: entry.short, hint: entry.hint, tone: entry.tone,
      basis: basis, who: who || null,
      countsAsKnowing: entry.code === 'knows',
      isFalseBelief: entry.code === 'misbelief',
      mustNotAttributeToCharacter: entry.code === 'narrator' || entry.code === 'readerKnows',
      version: VERSION
    };
  }

  function anachronism(rec, atChapter) {
    var evCh = num(rec && (rec.chapter || rec.eventChapter || rec.at));
    var at = num(atChapter);
    if (evCh == null || at == null) return { checked: false, anachronism: false };
    return { checked: true, anachronism: evCh > at, eventChapter: evCh, atChapter: at };
  }

  function num(v) {
    if (typeof v === 'number') return isFinite(v) ? v : null;
    var m = /(\d+)/.exec(str(v));
    return m ? parseInt(m[1], 10) : null;
  }

  function acquisition(rec, opts) {
    rec = rec || {};
    opts = opts || {};
    var hasEvent = present(rec.eventId) || present(rec.eventIds && rec.eventIds[0])
      || present(rec.chapter) || present(rec.eventChapter) || present(opts.chapter);
    var quotes = Array.isArray(rec.quotes) ? rec.quotes : [];
    var hasQuote = quotes.length > 0 || present(rec.quote) || present(rec.seedQuote);
    var verifiableQuote = quotes.some(function (q) {
      return q && typeof q === 'object' && present(q.quote)
        && (present(q.start) || present(q.offset)) ;
    }) || (present(rec.start) && present(rec.quote));
    var narrated = /叙述|旁白|交代|说明|告知|告诉/.test(str(rec.note || rec.basis || ''));
    var byEvidence = hasQuote && (hasEvent || narrated);
    return {
      hasEvent: hasEvent, hasQuote: hasQuote, narrated: narrated,
      verifiableQuote: verifiableQuote,
      bySilence: !hasQuote && !hasEvent && !narrated,
      acceptable: byEvidence || (hasEvent && narrated)
    };
  }

  function audit(rec, opts) {
    opts = opts || {};
    var s = of(rec, opts);
    var acq = acquisition(rec, opts);
    var ana = anachronism(rec, opts.atChapter);
    var out = {
      code: s.code, label: s.label, hint: s.hint, tone: s.tone, who: s.who,
      countsAsKnowing: s.countsAsKnowing, isFalseBelief: s.isFalseBelief,
      mustNotAttributeToCharacter: s.mustNotAttributeToCharacter,
      acquisition: acq, anachronism: ana,
      downgraded: false, downgradeReason: null
    };
    if (s.countsAsKnowing && !acq.acceptable) {
      out.downgraded = true; out.downgradeReason = 'acquisition_unsupported';
      out.code = 'unknown'; out.label = STATES.unknown.zh; out.hint = STATES.unknown.hint;
      out.countsAsKnowing = false;
    }
    if (s.code === 'narrator' && opts.attachToCharacter) {
      out.downgraded = true; out.downgradeReason = 'narrator_not_attributable';
      out.countsAsKnowing = false;
    }
    return out;
  }

  function badge(rec, opts) {
    var s = audit(rec, opts);
    var mark = s.code === 'knows' ? '●' : s.code === 'believes' ? '◐'
      : s.code === 'misbelief' ? '⚠' : s.code === 'conceals' ? '⊘'
      : s.code === 'unaware' ? '○' : s.code === 'readerKnows' ? '◉'
      : s.code === 'narrator' ? '☰' : '?';
    return { text: mark + ' ' + s.label, label: s.label, tone: s.tone, code: s.code, mark: mark };
  }

  function tally(records, opts) {
    var arrr = Array.isArray(records) ? records : [];
    var out = { total: arrr.length, byCode: {}, knowing: 0, misbelief: 0,
      downgraded: 0, anachronisms: 0, notAttributable: 0 };
    arrr.forEach(function (r) {
      var s = audit(r, opts);
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (s.countsAsKnowing) out.knowing++;
      if (s.isFalseBelief) out.misbelief++;
      if (s.downgraded) out.downgraded++;
      if (s.anachronism && s.anachronism.anachronism) out.anachronisms++;
      if (s.mustNotAttributeToCharacter) out.notAttributable++;
    });
    out.title = '认知状态分布';
    out.isWorldviewScore = false;
    out.note = '这是认知状态计数，不是清晰度评分。叙述者全知与读者已知不得灌给人物；'
      + '沉默不证明知情。';
    out.summary = arrr.length + ' 条认知记录里 ' + out.knowing + ' 条可确证「此人知道」；'
      + out.misbelief + ' 条是误信；' + out.notAttributable + ' 条属叙述者/读者层面（不得灌给人物）；'
      + out.downgraded + ' 条因缺事件或叙述依据被降级为未标明。';
    return out;
  }

  var API = { VERSION: VERSION, STATES: STATES, of: of, audit: audit, badge: badge,
    tally: tally, acquisition: acquisition, anachronism: anachronism };
  g.CLSkyKnowledgeView = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
