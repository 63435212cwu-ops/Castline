(function (g) {
  'use strict';

  var VERSION = '1';

  var TIERS = {
    current: { code: 'current', zh: '当前', tone: 'current',
      maxCount: 1, maxScreenShare: 0.35,
      hint: '读者当前正在看的那一个。数量上限 1，占屏预算最大。' },
    related: { code: 'related', zh: '相关', tone: 'related',
      maxCount: 12, maxScreenShare: 0.45,
      hint: '与当前直接相关的一组。计划明令「不要要求全景同时读上百个标签」，故设硬上限。' },
    background: { code: 'background', zh: '背景', tone: 'background',
      maxCount: 40, maxScreenShare: 0.20,
      hint: '背景对象。数量最多但每个占屏预算最小；超出部分应折叠而不是缩小到不可读。' },
    unknown: { code: 'unknown', zh: '档次未标明', tone: 'unknown',
      maxCount: 0, maxScreenShare: 0,
      hint: '记录没有标明这个对象属于哪一档。未标明不得默认成「当前」。' }
  };

  var SHAPES = {
    longChinese: { code: 'longChinese', zh: '长中文',
      hint: '较长的中文名称。缩写只允许出现在短标签层。' },
    duplicate: { code: 'duplicate', zh: '重名',
      hint: '多个对象同名。必须能靠稳定 id 或章节区分，否则读者无法分辨。' },
    singleChar: { code: 'singleChar', zh: '单字名',
      hint: '只有一个字的名字。缩写没有意义，且极易在密集图上被忽略。' },
    mixed: { code: 'mixed', zh: '混合字符',
      hint: '含非中文、括号、数字等混合字符。不得因编码或截断而损坏。' },
    veryLongChapter: { code: 'veryLongChapter', zh: '极长章名',
      hint: '章名很长。它是定位信息，缩写不应把可定位性缩掉。' }
  };

  var SHORT_MAX = { longChinese: 12, duplicate: 16, singleChar: 4, mixed: 14, veryLongChapter: 22 };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }
  function num(v) {
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (typeof v === 'string' && v.trim() !== '' && isFinite(+v)) return +v;
    return null;
  }

  function shapesOf(name, ctx) {
    name = str(name);
    ctx = ctx || {};
    var out = [];
    if (!name.trim()) return out;
    var cjk = name.split('').filter(function (c) { return /[\u4e00-\u9fff]/.test(c); }).length;
    var nonCjk = name.length - cjk;
    if (name.length >= 8) out.push('longChinese');
    if (name.length === 1) out.push('singleChar');
    if (nonCjk > 0) out.push('mixed');
    if (ctx.duplicateCount != null && num(ctx.duplicateCount) > 1) out.push('duplicate');
    if (ctx.isChapter && name.length >= 20) out.push('veryLongChapter');
    return out;
  }

  function shortLabel(name, kind) {
    var raw = str(name).trim().replace(/\s+/g, ' ');
    var cap = SHORT_MAX[kind] || 14;
    var short = raw.length > cap ? raw.slice(0, cap) : raw;
    return {
      text: short,
      full: raw,
      abbreviated: short !== raw,
      fullRetained: present(raw),
      kind: kind || null
    };
  }

  function unknownLabel(ctx) {
    ctx = ctx || {};
    var where = str(ctx.chapter || ctx.where);
    var id = str(ctx.id);
    var text = '未命名' + (ctx.kindZh ? ctx.kindZh : '对象');
    var suffix = id ? '#' + id.slice(-4) : '';
    return {
      text: text + suffix,
      isPlaceholder: true,
      nature: '原文未提供名称',
      locator: where || null,
      nonEmpty: (text + suffix).trim().length > 0
    };
  }

  function budget(actual) {
    actual = actual || {};
    var out = { tiers: {}, exceeded: [], total: 0, screenShare: 0 };
    Object.keys(TIERS).forEach(function (k) {
      if (k === 'unknown') return;
      var t = TIERS[k];
      var n = num(actual[k]) || 0;
      var share = num((actual.shares || {})[k]) || 0;
      out.tiers[k] = { count: n, maxCount: t.maxCount, screenShare: share,
        maxScreenShare: t.maxScreenShare,
        countOk: n <= t.maxCount, shareOk: share <= t.maxScreenShare };
      out.total += n;
      out.screenShare += share;
      if (n > t.maxCount) out.exceeded.push(k + ' 数量 ' + n + ' > ' + t.maxCount);
      if (share > t.maxScreenShare) out.exceeded.push(k + ' 占屏 ' + share + ' > ' + t.maxScreenShare);
    });
    out.ok = out.exceeded.length === 0;
    out.hint = out.ok
      ? ('三档均在上限内（当前 ≤1、相关 ≤12、背景 ≤40），总计 ' + out.total + ' 个标签')
      : ('超预算：' + out.exceeded.join('；') + ' —— 计划明令不要把上百个标签同时摊在全景上');
    return out;
  }

  function hitSource(visible, hit) {
    visible = visible || {}; hit = hit || {};
    var vKey = str(visible.key || visible.id || visible.ref);
    var hKey = str(hit.key || hit.id || hit.ref);
    if (!vKey || !hKey) {
      return { sameSource: false, coversVisible: null, ok: false, reason: 'no_key',
        hint: '可见对象或命中区没有身份键 —— 无法证明同源，故不得默认通过。' };
    }
    var same = vKey === hKey;
    var vw = num(visible.w) || 0, vh = num(visible.h) || 0;
    var hw = num(hit.w) || 0, hh = num(hit.h) || 0;
    var covers = (hw >= vw) && (hh >= vh);
    return {
      sameSource: same, coversVisible: covers,
      ok: same && covers,
      hint: !same
        ? ('命中区的身份键（' + hKey + '）与可见对象（' + vKey + '）不同源 —— '
           + '会出现"点到看不见的东西"或"看得见却点不到"。')
        : (!covers ? ('命中区 ' + hw + '×' + hh + ' 小于可见对象 ' + vw + '×' + vh + ' 的可点范围。')
                   : '命中区由同一可见对象导出，且不小于其可点范围。')
    };
  }

  function of(req) {
    req = req || {};
    var tier = TIERS[str(req.tier)] || TIERS.unknown;
    var name = str(req.name);
    var shapes = shapesOf(name, req);
    var primary = shapes[0] || (name.trim() ? 'longChinese' : null);
    var label = name.trim()
      ? shortLabel(name, primary)
      : unknownLabel({ chapter: req.chapter, id: req.id, kindZh: req.kindZh });
    return {
      tier: tier.code, tierLabel: tier.zh, tierHint: tier.hint,
      shapes: shapes,
      shapeLabels: shapes.map(function (s) { return SHAPES[s].zh; }),
      label: label.text,
      full: label.full !== undefined ? label.full : null,
      abbreviated: !!label.abbreviated,
      isPlaceholder: !!label.isPlaceholder,
      fullRetained: label.fullRetained !== false,
      version: VERSION
    };
  }

  function badge(req) {
    var s = of(req);
    var mark = s.tier === 'current' ? '◉' : s.tier === 'related' ? '○'
      : s.tier === 'background' ? '·' : '?';
    return { text: mark + ' ' + s.tierLabel, label: s.tierLabel, tier: s.tier, mark: mark,
      shapes: s.shapes, tone: s.tier };
  }

  function tally(requests) {
    var arrr = Array.isArray(requests) ? requests : [];
    var byTier = {}, byShape = {}, placeholder = 0, abbreviated = 0,
      noFull = 0, unbudgeted = 0;
    arrr.forEach(function (r) {
      var s = of(r);
      byTier[s.tier] = (byTier[s.tier] || 0) + 1;
      s.shapes.forEach(function (x) { byShape[x] = (byShape[x] || 0) + 1; });
      if (s.isPlaceholder) placeholder++;
      if (s.abbreviated) abbreviated++;
      if (!s.fullRetained) noFull++;
      if (s.tier === 'unknown') unbudgeted++;
    });
    var out = {
      title: '名称与标签构成', isQualityScore: false,
      total: arrr.length, byTier: byTier, byShape: byShape,
      placeholder: placeholder, abbreviated: abbreviated,
      lostFullText: noFull, unknownTier: unbudgeted,
      note: '缩写只允许发生在短标签层；详情/辅助名称/搜索必须取全文。'
        + '未知名称必须是有内容的占位，不是空白。'
    };
    out.summary = arrr.length
      ? (arrr.length + ' 个标签：' + Object.keys(byTier).map(function (k) {
          return (TIERS[k] ? TIERS[k].zh : k) + ' ' + byTier[k];
        }).join('、')
        + '；' + abbreviated + ' 个被缩写（全文入口全部保留：' + (noFull === 0) + '）'
        + '；占位 ' + placeholder + ' 个')
      : '0 个标签请求 —— 尚无样本，不得据此声称名称处理没有问题。';
    return out;
  }

  var API = { VERSION: VERSION, TIERS: TIERS, SHAPES: SHAPES, SHORT_MAX: SHORT_MAX,
    of: of, badge: badge, tally: tally, shapesOf: shapesOf, shortLabel: shortLabel,
    unknownLabel: unknownLabel, budget: budget, hitSource: hitSource };
  g.CLSkyNameBudget = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
