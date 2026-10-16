(function (g) {
  'use strict';

  var VERSION = '1';

  var CHANNELS = {
    position: { code: 'position', zh: '位置', must: '位置的含义（在哪里 = 什么）' },
    hue: { code: 'hue', zh: '色相', must: '色相的含义（什么颜色 = 什么类别）' },
    brightness: { code: 'brightness', zh: '亮度', must: '亮度的含义（明暗 = 什么）' },
    width: { code: 'width', zh: '线宽', must: '线宽的含义' },
    dash: { code: 'dash', zh: '线型', must: '线型的含义（实线/虚线/点线）' },
    size: { code: 'size', zh: '尺寸', must: '尺寸的含义' },
    motion: { code: 'motion', zh: '运动', must: '运动的含义' }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }

  function norm(entries) { return Array.isArray(entries) ? entries.filter(Boolean) : []; }

  function coverage(entries) {
    var seen = {};
    norm(entries).forEach(function (e) { seen[str(e.channel)] = true; });
    var missing = Object.keys(CHANNELS).filter(function (c) { return !seen[c]; });
    return {
      channels: Object.keys(CHANNELS).length,
      covered: Object.keys(CHANNELS).length - missing.length,
      missing: missing,
      missingLabels: missing.map(function (c) { return CHANNELS[c].zh; }),
      ok: missing.length === 0
    };
  }

  function conflicts(entries) {
    var by = {};
    norm(entries).forEach(function (e) {
      var key = [str(e.view), str(e.channel), str(e.value)].join('␟');
      (by[key] = by[key] || []).push({ meaning: str(e.meaning), where: str(e.where) });
    });
    var out = [];
    Object.keys(by).forEach(function (key) {
      var rows = by[key], meanings = {};
      rows.forEach(function (r) { meanings[r.meaning] = (meanings[r.meaning] || 0) + 1; });
      if (Object.keys(meanings).length > 1) {
        var parts = key.split('␟');
        out.push({
          view: parts[0], channel: parts[1], value: parts[2],
          meanings: Object.keys(meanings),
          where: rows.map(function (r) { return r.where; }).filter(Boolean),
          key: key,
          hint: '同一视图「' + parts[0] + '」里，' + (CHANNELS[parts[1]] ? CHANNELS[parts[1]].zh : parts[1])
            + '「' + parts[2] + '」同时代表 ' + Object.keys(meanings).join(' 与 ')
            + ' —— 计划要求一种取值只能有一个含义。'
        });
      }
    });
    return out;
  }

  function confidenceByDimmingOnly(entries) {
    var bad = [];
    norm(entries).forEach(function (e) {
      if (str(e.channel) !== 'brightness') return;
      var m = str(e.meaning);
      if (!/置信|不确定|待核|未核验|推断|存疑|低置信|unverified|uncertain/.test(m)) return;
      if (e.textOrSymbol === true) return;
      bad.push({ view: str(e.view), value: str(e.value), meaning: m, where: str(e.where),
        hint: '置信状态只用了亮度/明暗表达，没有文字或符号补充 —— 计划明令「不能只变暗」。' });
    });
    return bad;
  }

  function crossViewChanges(entries) {
    var by = {};
    norm(entries).forEach(function (e) {
      var key = [str(e.channel), str(e.value)].join('␟');
      (by[key] = by[key] || []).push(e);
    });
    var out = [];
    Object.keys(by).forEach(function (key) {
      var rows = by[key];
      var views = {}, meanings = {};
      rows.forEach(function (r) {
        views[str(r.view)] = true; meanings[str(r.meaning)] = true;
      });
      if (Object.keys(views).length < 2) return;
      if (Object.keys(meanings).length < 2) return;
      var anyContext = rows.some(function (r) { return r.context === true; });
      var anySyncedLegend = rows.some(function (r) { return r.syncedLegend === true; });
      var parts = key.split('␟');
      out.push({
        channel: parts[0], value: parts[1],
        views: Object.keys(views), meanings: Object.keys(meanings),
        hasContext: anyContext, hasSyncedLegend: anySyncedLegend,
        ok: anyContext && anySyncedLegend,
        hint: anyContext && anySyncedLegend
          ? '跨视图语义变化已声明上下文与同步图例。'
          : '跨视图语义变化缺少' + (anyContext ? '' : '上下文') + (anyContext ? '' : '与') + (anySyncedLegend ? '' : '同步图例')
            + ' —— 计划要求两者都有。'
      });
    });
    return out;
  }

  function ratchet(current, base) {
    var cur = conflicts(current).map(function (c) { return c.key; });
    var old = Array.isArray(base) ? base : [];
    var removed = old.filter(function (k) { return cur.indexOf(k) < 0; });
    var added = cur.filter(function (k) { return old.indexOf(k) < 0; });
    return {
      currentConflicts: cur.length, baselineConflicts: old.length,
      removedKeys: removed, addedKeys: added,
      shrunkWithoutFix: removed.length > 0,
      ok: added.length === 0,
      hint: removed.length
        ? '有 ' + removed.length + ' 条冲突从登记里消失。若真的修好了数据，应同步收紧基线并说明；'
          + '若只是删了登记，那就是「靠删除登记清零冲突」——计划明令禁止。'
        : (added.length ? '新增 ' + added.length + ' 条通道冲突，必须处理。' : '冲突未恶化。')
    };
  }

  function survivesDegradation(entries) {
    var views = {};
    norm(entries).forEach(function (e) {
      var v = str(e.view); if (!v) return;
      (views[v] = views[v] || {})[str(e.channel)] = true;
    });
    var out = [];
    Object.keys(views).forEach(function (v) {
      var hasNonColor = views[v].dash || views[v].size || views[v].motion;
      out.push({ view: v, hasNonColorChannel: !!hasNonColor,
        hint: hasNonColor
          ? '该视图有非颜色通道（线型/尺寸/运动），灰阶与关光下仍可区分结构。'
          : '该视图只有位置/色相/亮度这类通道 —— 灰阶或关光后主要结构将无法区分。' });
    });
    return out;
  }

  function tally(entries, base) {
    var e = norm(entries);
    var cov = coverage(e);
    var conf = conflicts(e);
    var dim = confidenceByDimmingOnly(e);
    var cross = crossViewChanges(e);
    var deg = survivesDegradation(e);
    return {
      title: '视觉通道登记',
      isQualityScore: false,
      entries: e.length,
      coverage: cov,
      conflicts: conf,
      dimmingOnly: dim,
      crossView: cross,
      degradation: deg,
      ratchet: base === undefined ? null : ratchet(e, base),
      note: '七个通道（位置/色相/亮度/线宽/线型/尺寸/运动）逐一登记；'
        + '同一视图同一取值只能有一个含义；置信状态须有文字或符号补充，不能只变暗；'
        + '跨视图语义变化须有上下文与同步图例；**冲突不能靠删除登记清零**。'
    };
  }

  var API = { VERSION: VERSION, CHANNELS: CHANNELS, coverage: coverage, conflicts: conflicts,
    confidenceByDimmingOnly: confidenceByDimmingOnly, crossViewChanges: crossViewChanges,
    ratchet: ratchet, survivesDegradation: survivesDegradation, tally: tally };
  g.CLSkyChannelRegistry = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
