(function (g) {
  'use strict';

  var VERSION = '1';

  var FORBIDDEN = {
    density: { code: 'density', zh: '事件密度', hint: '事件数量的多寡**不构成**高潮判据。' },
    deathToll: { code: 'deathToll', zh: '死亡数', hint: '死了多少人**不构成**高潮判据。' },
    midpoint: { code: 'midpoint', zh: '时间中点', hint: '处在时间轴中间**不构成**高潮判据。' }
  };

  var FORCED_FRAMES = /三幕|英雄旅程|hero'?s journey|三段式|起承转合|幕结构/;

  var REQUIRED = {
    perspective: { code: 'perspective', zh: '分析视角', hint: '这是从哪个角度看的（谁的、哪种读法）。没有视角的解释会被当成唯一真相。' },
    support: { code: 'support', zh: '支撑场景', hint: '支持这个解释的具体场景或事件。' },
    counter: { code: 'counter', zh: '反例', hint: '不利或相反的证据。计划要求标注反例 —— 只列支持的叫论证，不叫解释。' }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }
  function norm(rec) {
    if (!rec || typeof rec !== 'object' || Array.isArray(rec)) return {};
    return rec;
  }

  function climaxBasis(claim) {
    claim = norm(claim);
    var declared = str(claim.basis || claim.basisCode);
    var blob = [claim.reason, claim.summary, claim.text, claim.desc].map(str).join(' ');
    if (FORBIDDEN[declared]) return forbidden(FORBIDDEN[declared], 'declared');
    if (declared === 'structural' || declared === 'structure') {
      return { code: 'structural', ok: true, basis: 'declared', label: '结构依据',
        hint: '以结构证据支撑（参与者分量、因果依赖、线结构），不是数量或位置。' };
    }
    if (/(事件|剧情点|节点)(数|密度|最多|最密)|密度最(高|大)/.test(blob)) {
      return forbidden(FORBIDDEN.density, 'marker');
    }
    if (/(死亡|阵亡|死伤|被杀)(人数|数|最多|最多)|死人最多|死者最多/.test(blob)) {
      return forbidden(FORBIDDEN.deathToll, 'marker');
    }
    if (/(时间|篇幅|章节|全书)(中点|中间|正中)|恰在中间|刚好一半/.test(blob)) {
      return forbidden(FORBIDDEN.midpoint, 'marker');
    }
    if (/(因果|依赖|伏笔|收束|线结构|主角目标|对抗|阵营|咖位|结构)/.test(blob)) {
      return { code: 'structural', ok: true, basis: 'marker', label: '结构依据',
        hint: '以结构证据支撑（参与者分量、因果依赖、线结构），不是数量或位置。' };
    }
    return { code: 'unknown', ok: false, basis: 'no_marker', label: '依据未标明',
      hint: '这条高潮判定没有说明依据。看数量、死亡数或位置都**不算**依据；缺依据不得默认成立。' };
  }

  function forbidden(entry, basis) {
    return { code: entry.code, ok: false, basis: basis, label: entry.zh,
      hint: entry.hint + '这是**被计划点名禁止**的伪高潮判据。' };
  }

  function interpretability(rec) {
    rec = norm(rec);
    var has = {
      perspective: present(rec.perspective || rec.lens || rec.viewpoint || rec.angle),
      support: present(rec.support || rec.supportScenes || rec.scenes || rec.evidence),
      counter: present(rec.counter || rec.counterEvidence || rec.counterexamples || rec.against)
    };
    var missing = Object.keys(has).filter(function (k) { return !has[k]; });
    return {
      has: has, missing: missing,
      complete: missing.length === 0,
      missingLabels: missing.map(function (k) { return REQUIRED[k].zh; }),
      hint: missing.length
        ? ('缺少：' + missing.map(function (k) { return REQUIRED[k].zh + '（' + REQUIRED[k].hint + '）'; }).join('；'))
        : '视角、支撑场景与反例齐全，可与其他解释并列比较。'
    };
  }

  function forcedFrame(rec) {
    rec = norm(rec);
    var declared = str(rec.frame || rec.structure || rec.model);
    var blob = declared + ' ' + [rec.summary, rec.text, rec.desc].map(str).join(' ');
    if (rec.frameForced === true || /\bforced\b|强制/.test(blob)) {
      return { forced: true, label: '强制套用框架',
        hint: '计划明令不得强制套三幕或英雄旅程。框架只能是**可选**的分析视角。' };
    }
    if (FORCED_FRAMES.test(blob)) {
      return { forced: false, mentions: true, label: '提及框架',
        hint: '提到了三幕/旅程类框架。只要是**可选视角**并标了视角与反例即可；强制套用才是问题。' };
    }
    return { forced: false, mentions: false, label: '未使用固定框架', hint: '' };
  }

  function of(rec) {
    rec = norm(rec);
    var kind = str(rec.kind || rec.type);
    var isTheme = /主题|theme/.test(kind) || present(rec.theme);
    var isTension = /张力|tension/.test(kind) || present(rec.tension);
    var claim = rec.climax || (/高潮/.test(kind) ? rec : null);
    var out = {
      kind: isTheme ? 'theme' : isTension ? 'tension' : claim ? 'climax' : 'unknown',
      kindLabel: isTheme ? '主题' : isTension ? '张力' : claim ? '高潮判定' : '类型未标明',
      interpretability: interpretability(rec),
      frame: forcedFrame(rec),
      isInterpretation: true,
      version: VERSION
    };
    if (claim) {
      var cb = climaxBasis(claim);
      out.climax = cb.code; out.climaxOk = cb.ok;
      out.climaxLabel = cb.label; out.climaxHint = cb.hint;
      out.forbiddenBasis = !cb.ok && cb.code !== 'unknown' ? cb.code : null;
    }
    return out;
  }

  function badge(rec) {
    var s = of(rec);
    var mark = s.kind === 'theme' ? '◈' : s.kind === 'tension' ? '⋈' : s.kind === 'climax' ? '▲' : '?';
    var tail = s.kind === 'climax'
      ? (s.climaxOk ? '结构依据' : s.forbiddenBasis ? '伪判据' : '依据未标明')
      : (s.interpretability.complete ? '三件齐全' : '缺' + s.interpretability.missingLabels.join('/'));
    return { text: mark + ' ' + s.kindLabel + ' · ' + tail, label: s.kindLabel,
      kind: s.kind, mark: mark, tone: s.forbiddenBasis ? 'bad' : s.climaxOk ? 'ok' : 'plain' };
  }

  function tally(records) {
    var arrr = Array.isArray(records) ? records : [];
    var out = { total: arrr.length, byKind: {}, complete: 0, incomplete: 0,
      forbiddenClimax: 0, forcedFrames: 0 };
    arrr.forEach(function (r) {
      var s = of(r);
      out.byKind[s.kind] = (out.byKind[s.kind] || 0) + 1;
      if (s.interpretability.complete) out.complete++; else out.incomplete++;
      if (s.forbiddenBasis) out.forbiddenClimax++;
      if (s.frame.forced) out.forcedFrames++;
    });
    out.title = '主题与张力解释层';
    out.isQualityScore = false;
    out.note = '这是解释层，不是事实层。事件密度、死亡数或时间中点不能自动定义高潮；'
      + '不强制套三幕或英雄旅程；多种合理解释可以并列。';
    if (!arrr.length) {
      out.summary = '本作品 0 条主题/张力记录 —— 这首先说明**从未被要求提取过**'
        + '（精读产出清单里没有主题/张力/结构解释），不能据此宣称作品没有主题。';
      out.neverRequested = true;
      out.mustNotClaim = '本作品没有主题或张力';
    } else {
      out.neverRequested = false;
      out.summary = arrr.length + ' 条解释记录里 ' + out.complete + ' 条视角/支撑/反例齐全；'
        + out.incomplete + ' 条缺件；' + out.forbiddenClimax + ' 条用了被禁止的伪高潮判据。';
    }
    return out;
  }

  var API = { VERSION: VERSION, FORBIDDEN: FORBIDDEN, REQUIRED: REQUIRED,
    of: of, badge: badge, tally: tally, climaxBasis: climaxBasis,
    interpretability: interpretability, forcedFrame: forcedFrame };
  g.CLSkyThemeTension = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
