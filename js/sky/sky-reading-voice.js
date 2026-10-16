(function (g) {
  'use strict';

  var VERSION = '1';

  var STATES = {
    loading: { code: 'loading', zh: '加载中',
      text: '正在加载…',
      hint: '内容还没到。它是**暂时**的，会自动结束；不得写成"没有"。' },
    missing: { code: 'missing', zh: '原文未提供',
      text: '原文未提供这一项',
      hint: '材料里**确实没有**这一项。这是关于**作品**的陈述。' },
    pendingReview: { code: 'pendingReview', zh: '待核',
      text: '待核验',
      hint: '有内容，但还没经过核验。它与"没有"完全不同 —— 内容在，只是判断未定。' },
    locateFailed: { code: 'locateFailed', zh: '定位失败',
      text: '引句未能在原文中定位',
      hint: '内容存在，但**引句定位没成功**（偏移对不上或找不到）。'
        + '这是关于**我们**的陈述，不是关于作品的 —— 不得与"原文未提供"混同。' },
    modelFailed: { code: 'modelFailed', zh: '模型失败',
      text: '这一层分析未成功',
      hint: '分析过程本身失败了（模型/管线）。它与"没有内容"是两件事，'
        + '下一步是重跑，而不是接受一个空结论。' },
    unknown: { code: 'unknown', zh: '状态未标明',
      text: '状态未标明',
      hint: '记录没有标明这是哪种状态。未标明不得默认成"原文未提供"。' }
  };

  var LAYERS = {
    body: { code: 'body', zh: '正文', rank: 1, tone: 'primary',
      hint: '原文本身。层级最高，不得被装饰挤占。' },
    summary: { code: 'summary', zh: '摘要', rank: 2, tone: 'secondary',
      hint: '对原文的概括。必须能看出它**不是**原文。' },
    meta: { code: 'meta', zh: '元信息', rank: 3, tone: 'tertiary',
      hint: '章节、人物、类型等定位信息。层级低于摘要。' },
    evidence: { code: 'evidence', zh: '证据状态', rank: 4, tone: 'status',
      hint: '这条结论的依据与核验状态。它可以低调，但不得看不见。' },
    action: { code: 'action', zh: '动作', rank: 5, tone: 'interactive',
      hint: '可点的下一步操作。层级最低，但必须**可达**。' }
  };

  var ENGINEERING = /(\b\d+(\.\d+)?\s*(ms|毫秒|秒|s)\b)|(\b\d+\s*(KB|MB|GB|字节|bytes)\b)|(@budget)|(\bdrawcalls?\s*=)|(\brtpx\s*=)|(\bfps\b\s*[=:]?\s*\d)|(\bconsole\.(log|warn|error)\s*\()/;

  var MIN_VISIBLE = {
    minFontSize: 11,
    minContrast: 4.5,
    minOpacity: 0.55
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function merge(a, b) {
    var out = {}, k;
    for (k in a) if (Object.prototype.hasOwnProperty.call(a, k)) out[k] = a[k];
    for (k in b) if (Object.prototype.hasOwnProperty.call(b, k)) out[k] = b[k];
    return out;
  }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function voice(signals) {
    signals = signals && typeof signals === 'object' ? signals : {};
    var declared = str(signals.status);
    if (STATES[declared]) return entry(STATES[declared], 'declared');
    if (signals.loading === true) return entry(STATES.loading, 'signal');
    if (signals.modelFailed === true) return entry(STATES.modelFailed, 'signal');
    if (signals.locateFailed === true) return entry(STATES.locateFailed, 'signal');
    if (signals.absent === true) return entry(STATES.missing, 'signal');
    if (signals.unverified === true || signals.pending === true) return entry(STATES.pendingReview, 'signal');
    return entry(STATES.unknown, 'no_signal');
  }

  function entry(e, basis) {
    return {
      code: e.code, label: e.zh, text: e.text, hint: e.hint, basis: basis,
      isTransient: e.code === 'loading',
      aboutWork: e.code === 'missing',
      aboutProcess: e.code === 'locateFailed' || e.code === 'modelFailed',
      contentMayExist: e.code === 'pendingReview' || e.code === 'locateFailed'
        || e.code === 'modelFailed' || e.code === 'loading',
      version: VERSION
    };
  }

  function layerOf(what) {
    what = what && typeof what === 'object' ? what : {};
    var declared = str(what.layer);
    if (LAYERS[declared]) return merge({ code: declared, basis: 'declared' }, LAYERS[declared]);
    var role = str(what.role || what.purpose);
    var byRole = { text: 'body', raw: 'body', quote: 'body', summary: 'summary',
      abstract: 'summary', meta: 'meta', chapter: 'meta', status: 'evidence',
      basis: 'evidence', button: 'action', link: 'action' }[role];
    if (byRole) return merge({ code: byRole, basis: 'role' }, LAYERS[byRole]);
    return { code: 'unknown', zh: '层级未标明', rank: null, tone: 'unknown',
      hint: '记录没有标明这属于哪一层级。未标明不得默认成正文。', basis: 'no_signal' };
  }

  function order(a, b) {
    var ra = LAYERS[a] ? LAYERS[a].rank : null;
    var rb = LAYERS[b] ? LAYERS[b].rank : null;
    if (ra == null || rb == null) return 0;
    return ra - rb;
  }

  function cleanForReading(text) {
    var s = str(text);
    var m = ENGINEERING.exec(s);
    return {
      ok: !m,
      found: m ? m[0] : null,
      hint: m
        ? ('阅读面出现了工程痕迹「' + m[0] + '」—— 计划明令不得让工程秒数或原始代码挤占阅读。')
        : '未发现工程秒数、原始代码或调试痕迹。'
    };
  }

  function visibilityCheck(style) {
    style = style && typeof style === 'object' ? style : {};
    var fs = typeof style.fontSize === 'number' ? style.fontSize : null;
    var ct = typeof style.contrast === 'number' ? style.contrast : null;
    var op = typeof style.opacity === 'number' ? style.opacity : null;
    var bad = [];
    if (fs != null && fs < MIN_VISIBLE.minFontSize) bad.push('字号 ' + fs + ' < ' + MIN_VISIBLE.minFontSize);
    if (ct != null && ct < MIN_VISIBLE.minContrast) bad.push('对比度 ' + ct + ' < ' + MIN_VISIBLE.minContrast);
    if (op != null && op < MIN_VISIBLE.minOpacity) bad.push('不透明度 ' + op + ' < ' + MIN_VISIBLE.minOpacity);
    return {
      ok: bad.length === 0, violations: bad, limits: MIN_VISIBLE,
      hint: bad.length
        ? ('未知/次级状态被弱化到看不见：' + bad.join('；')
           + ' —— 可以降低装饰权重，但不能弱化到看不见。')
        : '降低装饰权重后仍在可读下限之内。'
    };
  }

  function tally(usages) {
    var arrr = Array.isArray(usages) ? usages : [];
    var byCode = {}, dirty = 0, weak = 0;
    arrr.forEach(function (u) {
      var v = voice(u && u.signals ? u.signals : u);
      byCode[v.code] = (byCode[v.code] || 0) + 1;
      if (u && u.text != null && !cleanForReading(u.text).ok) dirty++;
      if (u && u.style && !visibilityCheck(u.style).ok) weak++;
    });
    var states = Object.keys(STATES).filter(function (k) { return k !== 'unknown'; });
    var used = states.filter(function (k) { return byCode[k]; });
    return {
      title: '阅读状态用法', isQualityScore: false,
      total: arrr.length, byCode: byCode,
      statesUsed: used.length, statesTotal: states.length,
      engineeringLeaks: dirty, weakenedBelowLimit: weak,
      singleVoice: used.length === 1 && arrr.length > 3,
      note: '五种状态必须分别表达：加载中／原文未提供／待核／定位失败／模型失败。'
        + '前两者一个说"还没到"、一个说"确实没有"；后两者是关于**我们**没做到，'
        + '不是关于作品。未知可以降装饰权重，不能弱化到看不见。',
      summary: arrr.length
        ? (arrr.length + ' 处文案用了 ' + used.length + '/' + states.length + ' 种状态'
           + (used.length ? '（' + used.map(function (k) { return STATES[k].zh + ' ' + byCode[k]; }).join('、') + '）' : '')
           + (dirty ? '；**工程痕迹 ' + dirty + ' 处**' : '')
           + (weak ? '；**弱化到看不见 ' + weak + ' 处**' : ''))
        : '0 处文案 —— 尚无样本，不得据此声称状态表达没有问题。'
    };
  }

  var API = { VERSION: VERSION, STATES: STATES, LAYERS: LAYERS, MIN_VISIBLE: MIN_VISIBLE,
    ENGINEERING: ENGINEERING, voice: voice, layerOf: layerOf, order: order,
    cleanForReading: cleanForReading, visibilityCheck: visibilityCheck, tally: tally };
  g.CLSkyReadingVoice = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
