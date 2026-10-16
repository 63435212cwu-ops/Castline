(function (g) {
  'use strict';

  var VERSION = '1';

  var KINDS = {
    hover: { code: 'hover', zh: '悬停', tone: 'hover',
      hint: '鼠标/触控指针**经过**某对象。它是预览，不是选择，指针移开即消失。' },
    focus: { code: 'focus', zh: '键盘焦点', tone: 'focus',
      hint: '键盘 Tab 落点。它与悬停无关，且**必须始终可见**（不能只在 hover 时显示）。' },
    selection: { code: 'selection', zh: '选中', tone: 'selection',
      hint: '用户明确选定的对象。它跨图传递、可恢复，且**不因指针移开而消失**。' },
    current: { code: 'current', zh: '播放当前', tone: 'current',
      hint: '播放器正在播放的那一个。它由播放进度驱动，**不由用户点击决定**。' }
  };

  var CROSS_GRAPH_KEYS = ('selectionId,selectionKind,filter,query,page,scrollTop,'
    + 'chapter,restoreAttr,restoreValue').split(',');

  var FORBIDDEN_CROSS_KEYS = ['name', 'character', 'characterName', 'personDetail',
    'label', 'title', 'displayName'];

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    if (Array.isArray(v)) return v.length > 0;
    return true;
  }

  function empty() {
    return { hover: null, focus: null, selection: null, current: null };
  }

  function set(state, kind, value) {
    var s = state && typeof state === 'object' ? state : empty();
    var next = { hover: s.hover, focus: s.focus, selection: s.selection, current: s.current };
    if (!KINDS[kind]) {
      return { ok: false, reason: 'unknown_kind', state: next,
        hint: '未知状态类型「' + str(kind) + '」—— 四种状态之外不得新增。' };
    }
    next[kind] = present(value) ? value : null;
    var others = Object.keys(KINDS).filter(function (k) { return k !== kind; });
    var leaked = others.filter(function (k) { return next[k] !== s[k]; });
    return {
      ok: true, state: next, kind: kind,
      leaked: leaked,
      isolated: leaked.length === 0,
      hint: leaked.length
        ? ('设置 ' + kind + ' 时改动了 ' + leaked.join('、') + ' —— 四种状态必须彼此独立。')
        : ('只设置了 ' + kind + '，其余三种未变。')
    };
  }

  function advance(state, currentId) {
    var r = set(state, 'current', currentId);
    var s = state && typeof state === 'object' ? state : empty();
    return {
      ok: r.ok, state: r.state,
      selectionKept: r.state.selection === s.selection,
      hint: r.state.selection === s.selection
        ? '播放推进只改了 current，用户的选择保持不变。'
        : '播放推进改动了 selection —— 计划要求两者分开。'
    };
  }

  function crossGraph(payload) {
    payload = payload && typeof payload === 'object' ? payload : {};
    var kept = {}, rejected = [];
    Object.keys(payload).forEach(function (k) {
      if (CROSS_GRAPH_KEYS.indexOf(k) >= 0) kept[k] = payload[k];
      else if (FORBIDDEN_CROSS_KEYS.indexOf(k) >= 0) rejected.push({ key: k, why: 'name_derived' });
      else rejected.push({ key: k, why: 'not_allowed' });
    });
    return {
      payload: kept, rejected: rejected,
      rejectedNames: rejected.filter(function (r) { return r.why === 'name_derived'; })
        .map(function (r) { return r.key; }),
      hasStableId: present(kept.selectionId),
      hint: rejected.length
        ? ('拒绝了 ' + rejected.length + ' 个键（' + rejected.map(function (r) { return r.key; }).join('、')
           + '）—— 跨图只传稳定 ID 与必要视图状态。')
        : '载荷只含允许的键。'
    };
  }

  function onBookSwitch(prevState, prevGraphKey, nextGraphKey, lookup) {
    prevState = prevState || empty();
    var changed = str(prevGraphKey) !== str(nextGraphKey);
    if (!changed) {
      return { cleared: false, state: prevState, reason: 'same_graph',
        hint: '同一部书，不需要清理。' };
    }
    var out = empty();
    var carried = [];
    var dropped = [];
    Object.keys(KINDS).forEach(function (k) {
      if (present(prevState[k])) {
        var sameById = lookup ? lookup(prevState[k], 'id') : null;
        dropped.push({ kind: k, value: prevState[k], matchedNew: sameById });
        if (sameById) carried.push(k);
      }
    });
    return {
      cleared: true, state: out, dropped: dropped, carried: carried,
      hint: ('换书：清掉 ' + dropped.length + ' 项旧引用。'
        + (carried.length
           ? ('其中 ' + carried.join('、') + ' 在新书里**按稳定 ID** 找到了对应对象 —— '
              + '但本函数一律不自动恢复，需用户重新选择。')
           : '新书里没有任何一项按稳定 ID 对应。')
        + ' 同名对象（若存在）**不会**被当作同一个。'),
      sameNameIsNotSame: true
    };
  }

  function restoreAfterRepaint(selectionId, items, idOf) {
    items = Array.isArray(items) ? items : [];
    var get = typeof idOf === 'function' ? idOf : function (x) { return x && (x.id != null ? x.id : x.entityId); };
    if (!present(selectionId)) {
      return { restored: false, index: null, reason: 'no_selection',
        fellBackToFirst: false,
        hint: '本来就没有选择 —— 不得因此选中第一条。' };
    }
    for (var i = 0; i < items.length; i++) {
      if (str(get(items[i])) === str(selectionId)) {
        return { restored: true, index: i, reason: 'id_match', fellBackToFirst: false,
          hint: '按稳定 ID 找回，位置可能在重绘后变化，但对象是同一个。' };
      }
    }
    return { restored: false, index: null, reason: 'not_found',
      fellBackToFirst: false,
      hint: ('选择的对象不在新列表里（可能被筛选掉或已删除）—— '
        + '**保持无选择**，不得回落到第一条。') };
  }

  function audit(state, previous, changedKind) {
    state = state && typeof state === 'object' ? state : empty();
    var out = { kinds: {}, present: 0, conflated: [], isolationChecked: !!(previous && KINDS[changedKind]) };
    Object.keys(KINDS).forEach(function (k) {
      out.kinds[k] = { value: state[k] === undefined ? null : state[k], has: present(state[k]) };
      if (present(state[k])) out.present++;
    });
    if (previous && KINDS[changedKind]) Object.keys(KINDS).forEach(function (kind) {
      if (kind !== changedKind && state[kind] !== previous[kind]) out.conflated.push(changedKind + ' 操作改写了 ' + kind);
    });
    if (present(state.hover) && present(state.selection)
        && state.hover === state.selection) {
      out.hoverOnSelection = true;
    }
    out.ok = out.conflated.length === 0;
    return out;
  }

  var API = { VERSION: VERSION, KINDS: KINDS, CROSS_GRAPH_KEYS: CROSS_GRAPH_KEYS,
    FORBIDDEN_CROSS_KEYS: FORBIDDEN_CROSS_KEYS,
    empty: empty, set: set, advance: advance, crossGraph: crossGraph,
    onBookSwitch: onBookSwitch, restoreAfterRepaint: restoreAfterRepaint, audit: audit };
  g.CLSkySelectionModel = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
