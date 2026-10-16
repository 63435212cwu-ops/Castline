(function (g) {
  'use strict';

  var VERSION = '1';

  var KINDS = {
    exact_quote: {
      code: 'exact_quote', label: '精确引句定位', short: '精确',
      hint: '该事件的引句在唯一来源里逐字命中，偏移与来源哈希均已核验。这只说明位置正确，不说明结论正确。',
      reader: '位置已核验', tone: 'located'
    },
    legacy_interval: {
      code: 'legacy_interval', label: '旧区间夹定', short: '区间',
      hint: '该事件来自旧数据，没有可逐字核验的引句；它的显示位置由同章或同尺度前后邻居夹定，位置本身未经核验。',
      reader: '位置未核验 · 按相邻事件夹定', tone: 'bounded'
    },
    unresolved: {
      code: 'unresolved', label: '位置未知', short: '未知',
      hint: '拿不到可信的引句锚点，因此这个事件在原文里的位置是未知的；它仍可阅读，但不应被当成发生在某个确定时间点。',
      reader: '位置未知 · 仍可阅读全文', tone: 'unknown'
    },
    conflicted: {
      code: 'conflicted', label: '来源冲突', short: '冲突',
      hint: '同一事件存在多个来源或多个版本哈希，无法在全局排出唯一顺序；冲突必须保留，不能被择一掩盖。',
      reader: '来源冲突 · 顺序待核', tone: 'conflict'
    },
    unknown: {
      code: 'unknown', label: '定位状态未提供', short: '未提供',
      hint: '这份数据没有给出定位状态字段（旧缓存兼容）。缺失不等于已确认，也不等于失败。',
      reader: '定位状态未提供', tone: 'unknown'
    }
  };

  var CONFLICT_REASONS = {
    multiple_sources_no_global_order: '存在多个来源，且没有全局顺序可比',
    missing_or_conflicting_source_identity: '来源身份缺失或相互冲突',
    ambiguous_primary_quote: '主引句不唯一，无法确定指的是哪一处',
    missing_trusted_primary_quote: '没有可信的主引句可作锚点'
  };

  function str(v) { return typeof v === 'string' ? v : ''; }


  function of(entity, opts) {
    opts = opts || {};
    var sp = entity && entity.sourcePosition;
    if (!sp || typeof sp !== 'object') {
      if (opts.kind && KINDS[opts.kind]) return finish(KINDS[opts.kind], null);
      return finish(KINDS.unknown, null);
    }
    var kind = str(sp.kind);
    var reason = str(sp.reason);
    var conflicts = Array.isArray(opts.sourceIds) && opts.sourceIds.length > 1;
    if (kind === 'unresolved' && (conflicts || /multiple_sources|conflicting|ambiguous/.test(reason))) {
      return finish(KINDS.conflicted, reason);
    }
    return finish(KINDS[kind] || KINDS.unknown, reason);
  }

  function finish(entry, reason) {
    var out = {
      code: entry.code, label: entry.label, short: entry.short, reader: entry.reader,
      hint: entry.hint, tone: entry.tone,
      located: entry.code === 'exact_quote',
      placesAtExactTime: entry.code === 'exact_quote'
    };
    if (reason) {
      out.reason = reason;
      out.reasonText = CONFLICT_REASONS[reason] || ('来源给的定位理由：' + reason);
    }
    return out;
  }

  function badge(entityOrKind) {
    var s = typeof entityOrKind === 'string' ? of(null, { kind: entityOrKind }) : of(entityOrKind);
    var mark = s.tone === 'located' ? '◆' : s.tone === 'bounded' ? '◇' : s.tone === 'conflict' ? '⚠' : '?';
    return { text: mark + ' ' + s.short, label: s.label, tone: s.tone, mark: mark };
  }

  function progress(counts) {
    counts = counts || {};
    var exact = num(counts.exact_quote) + num(counts.anchored);
    var bounded = num(counts.legacy_interval) + num(counts.unverified_offset);
    var unknown = num(counts.unresolved);
    var conflict = num(counts.conflicted);
    var noRef = num(counts.no_ref);
    var total = num(counts.total);
    if (!total) total = exact + bounded + unknown + conflict + noRef;
    var locatedPct = total ? Math.round(exact / total * 100) : null;
    return {
      total: total, exact: exact, bounded: bounded, unknown: unknown, conflict: conflict, noRef: noRef,
      locatedPercent: locatedPct,
      title: '定位进度',
      summary: (locatedPct == null ? '—' : locatedPct + '%') + ' 可精确回到原文',
      detail: '精确 ' + exact + ' · 区间 ' + bounded + ' · 未知 ' + unknown +
        (conflict ? ' · 冲突 ' + conflict : '') + (noRef ? ' · 无引用 ' + noRef : ''),
      isSemanticCompletion: false,
      semanticNote: '定位进度不等于语义完成率：位置对不代表结论对。'
    };
  }

  function num(v) { var n = typeof v === 'number' ? v : parseFloat(v); return isFinite(n) ? n : 0; }

  function countEvents(events) {
    var out = { total: 0, exact_quote: 0, legacy_interval: 0, unresolved: 0, conflicted: 0, unknown: 0, no_ref: 0 };
    (Array.isArray(events) ? events : []).forEach(function (e) {
      var s = of(e);
      out.total++;
      if (s.code === 'conflicted') out.conflicted++;
      else if (s.code === 'exact_quote') out.exact_quote++;
      else if (s.code === 'legacy_interval') out.legacy_interval++;
      else if (s.code === 'unresolved') out.unresolved++;
      else out.unknown++;
    });
    out.located = out.exact_quote;
    return out;
  }

  var API = {
    VERSION: VERSION, KINDS: KINDS, CONFLICT_REASONS: CONFLICT_REASONS,
    of: of, badge: badge, progress: progress, countEvents: countEvents
  };
  g.CLSkyPositionLabel = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
