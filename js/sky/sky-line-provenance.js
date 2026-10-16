(function (g) {
  'use strict';

  var VERSION = '1';

  var SOURCES = {
    mechanical: {
      code: 'mechanical', zh: '机械等分（仅导航）', short: '机械',
      tone: 'mechanical',
      hint: '这条线是按事件数量切出来的，不是按持续目标或因果依赖识别的。机械等分只当导航，不计故事结构。'
    },
    derived: {
      code: 'derived', zh: '推导（无独立依据）', short: '推导', tone: 'derived',
      hint: '由现有图谱数据推导，但记录里没有给出这条线为何独立的依据。'
    },
    reviewed: {
      code: 'reviewed', zh: '逐条审阅', short: '审阅', tone: 'reviewed',
      hint: '这条线来自对原文的逐条审阅，记录里带来源与依据。'
    },
    unknown: {
      code: 'unknown', zh: '来源未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有标明这条线是怎么来的。未标明不等于已审阅。'
    }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function num(v) { var n = typeof v === 'number' ? v : parseFloat(v); return isFinite(n) ? n : null; }

  function sizeOf(line) {
    if (!line || typeof line !== 'object') return 0;
    var a = line.events, b = line.eventIds;
    return (Array.isArray(a) ? a.length : 0) || (Array.isArray(b) ? b.length : 0);
  }

  function looksMechanical(lines, meta) {
    var sizes = (Array.isArray(lines) ? lines : []).map(sizeOf).filter(function (n) { return n > 0; });
    var src = str(meta && meta.src);
    var declared = (src === 'local-completion') || (str(meta && meta.method) === 'existing-graph-local-completion');
    if (sizes.length < 4) return { mechanical: declared, declared: declared, equalSplit: false, sizes: sizes };
    var sorted = sizes.slice().sort(function (a, b) { return a - b; });
    var mid = sorted[Math.floor(sorted.length / 2)];
    var spread = (sorted[sorted.length - 1] - sorted[0]) / Math.max(mid, 1);
    var equal = spread <= 0.05;
    return { mechanical: declared || equal, declared: declared, equalSplit: equal,
      spread: +spread.toFixed(4), sizes: sizes };
  }

  function of(line, meta) {
    meta = meta || {};
    var graphSrc = str(meta.src);
    var lineSrc = str(line && (line.provenance || line.src));
    var src, code;
    if (graphSrc === 'local-completion' || lineSrc === 'local-completion') {
      src = 'local-completion'; code = 'mechanical';
    } else if (graphSrc === 'assistant-reviewed-source' || graphSrc === 'reviewed'
               || lineSrc === 'assistant-reviewed-source' || lineSrc === 'reviewed') {
      src = 'assistant-reviewed-source'; code = 'reviewed';
    } else if (lineSrc === 'derived' || lineSrc === 'model' || lineSrc === 'synthesis') {
      src = lineSrc; code = 'derived';
    } else if (lineSrc) {
      src = lineSrc; code = 'unknown';
    } else {
      src = graphSrc; code = graphSrc ? 'unknown' : 'unknown';
    }
    var entry = SOURCES[code];
    var reason = str(line && line.handoff_reason);
    var temporalOnly = /时间顺序|承接上一|先后|按序/.test(reason);
    var mechanicalLabel = /阶段\s*[0-9一二三四五六七八九十]/.test(str(line && (line.theme || line.name || line.title)));
    var hasBasis = !!(line && (line.objective === 'declared'
      || (reason && !temporalOnly)));
    if (mechanicalLabel) hasBasis = false;
    return {
      code: entry.code, label: entry.zh, short: entry.short, hint: entry.hint, tone: entry.tone,
      countsAsStructure: entry.code === 'reviewed',
      navigableOnly: entry.code === 'mechanical',
      hasIndependenceBasis: hasBasis,
      rawSource: src || null,
      size: sizeOf(line)
    };
  }

  function tally(lines, meta) {
    var arrl = Array.isArray(lines) ? lines : [];
    var mech = looksMechanical(arrl, meta);
    var out = { total: arrl.length, byCode: {}, sizes: mech.sizes,
      equalSplit: !!mech.equalSplit, declaredByGraph: !!mech.declared,
      spread: mech.spread == null ? null : mech.spread,
      withoutBasis: 0, countsAsStructure: 0 };
    arrl.forEach(function (l) {
      var s = of(l, meta);
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (!s.hasIndependenceBasis) out.withoutBasis++;
      if (s.countsAsStructure) out.countsAsStructure++;
    });
    out.title = '剧情线来源';
    out.note = '机械等分只当导航，不计故事结构（计划 P3.4）。这是来源计数，不是结构质量分。';
    out.isStructureScore = false;
    if (mech.mechanical) {
      out.summary = '本作品当前 ' + arrl.length + ' 条线均为机械等分（段大小 ' +
        (mech.spread == null ? '—' : (mech.spread * 100).toFixed(1) + '% 极差') +
        (mech.declared ? '，图谱自述 local-completion' : '') + '）—— 只能当导航，不能当故事结构。';
    } else {
      out.summary = '本作品 ' + arrl.length + ' 条线中 ' + out.countsAsStructure + ' 条来自逐条审阅。';
    }
    return out;
  }

  var API = { VERSION: VERSION, SOURCES: SOURCES, of: of, tally: tally,
    looksMechanical: looksMechanical, sizeOf: sizeOf };
  g.CLSkyLineProvenance = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
