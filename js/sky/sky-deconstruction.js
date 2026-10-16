/*
 * @role sky-reading
 * @owns js/sky/sky-deconstruction.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract narrative-deconstruction/1
 *
 * 第一批叙事解构读层：全书 DNA、主支线骨架、人物出场弧线、事件证据。
 * 纯 DOM，不创建 WebGL 层；所有跳转回到 CLSky 的既有星盘 / 罗盘状态机。
 */
(function (g) {
  'use strict';

  var doc = g.document;
  var state = { open: false, mode: 'overview', focus: null, restore: null, ready: false };
  var root = null, button = null, graph = null, model = null, index = null;
  var KEY_EVENT = /转折|高燃|抉择|冲突|高潮|揭秘|背叛|死亡|结局|反转/;
  var PAGE_SIZE = 24, TRACK_BINS = 48, searchTimer = null;
  var browse = { people: { query: '', filter: 'all', page: 0 }, evidence: { query: '', filter: 'all', kind: 'all', person: '', order: 'time', page: 0 }, arc: { page: 0 }, quotes: { page: 0 } };
  var personDetail = null;
  var causalFork = { source: null, returnTo: null, entrySnapshot: null, request: 0, tween: null, progress: 1, staticReason: '', layoutObserver: null, layoutFallback: null, layoutRoot: null };
  var m84 = { open: false, selected: 'characters', request: 0, selectionProgress: 1,
    returning: false, returnOpen: false, returnScroll: null, returnLayer: null, trigger: null, openScroll: null };
  var m103 = { open: false, eventIndex: null, returnSnapshot: null, request: 0, tween: null };
  var m106 = { open: false, view: 'group', refId: null, graph: null, indexGraph: null, byRef: null,
    returnSnapshot: null, groupSnapshot: null, recordSnapshot: null, sourceSnapshot: null, selectedRecord: null, sourceReturnView: null,
    page: 0, request: 0, sourceRequest: 0, tween: null, context: null };
  var m88 = { recordId: null, scope: 'reading', request: 0, tween: null, progress: 1, snapshot: null, entrySnapshot: null, sourceRequest: 0, source: null, sourceStatus: null, hookOff: null, hookedScene: null, scopeKey: '', orderByIndex: [], graphEpoch: 0, lastReading: null };
  var LAYERS = { tasks: '任务', relations: '人物关系', causeEdges: '因果', clues: '伏笔', characterStates: '状态', narrativeUnits: '剧情单元', reviewIssues: '核验批注' };
  browse.mechanics = { query: '', filter: 'all', layer: 'tasks', page: 0, selected: null };
  browse.mechanicQuotes = { page: 0 }; browse.references = { page: 0 }; browse.attributes = { page: 0 };
  browse.neighbors = { bId: '', kind: 'all', tab: 'common', result: null, origin: null, scrollTop: null };
  browse.coverage = { page: 0 };
  browse.causal = { query: '', filter: 'all', page: 0 }; browse.causalFork = { page: 0 };
  browse.payoffs = { page: 0 }; browse.unresolved = { page: 0 };
  browse.causalRoots = { page: 0 }; browse.causalLeaves = { page: 0 };
  browse.foreshadow = { query: '', filter: 'all', page: 0 };
  var STATUS_TEXT = {
    foreshadow: {
      resolved: { zh: '已兑现', hint: '兑现事件已显式关联' },
      pending: { zh: '待回收', hint: '当前记录尚未声明兑现事件' },
      broken: { zh: '引用断裂', hint: '兑现引用缺失、重复或顺序冲突' },
      conflicted: { zh: '身份冲突', hint: '同一声明身份存在多条记录' }
    },
    declared: {
      resolved: { zh: '已兑现声明', hint: '来源声明此伏笔已兑现' },
      pending: { zh: '待回收声明', hint: '来源声明兑现留待后文' },
      seeded: { zh: '已埋设声明', hint: '来源仅声明埋设，未提供兑现' },
      unresolved: { zh: '未解析声明', hint: '来源标记此伏笔未解析' }
    },
    mechanic: {
      active: { zh: '进行中', hint: '' },
      completed: { zh: '完成声明', hint: '' },
      failed: { zh: '失败声明', hint: '' },
      abandoned: { zh: '放弃声明', hint: '' },
      blocked: { zh: '受阻', hint: '' },
      unknown: { zh: '状态未提供', hint: '' },
      seeded: { zh: '已埋设声明', hint: '' },
      resolved: { zh: '已兑现声明', hint: '' },
      pending: { zh: '待回收声明', hint: '' },
      unresolved: { zh: '待确认', hint: '' },
      uncertain: { zh: '未确认', hint: '' },
      linked: { zh: '事件引用已关联', hint: '' },
      unlinked: { zh: '事件引用待匹配', hint: '' }
    },
    knowledge: {
      known: { zh: '已知声明', hint: '' },
      unknown: { zh: '不知声明', hint: '' },
      unaware: { zh: '不知声明', hint: '' },
      not_known: { zh: '不知声明', hint: '' },
      does_not_know: { zh: '不知声明', hint: '' },
      belief: { zh: '人物信念声明', hint: '' },
      suspected: { zh: '怀疑声明', hint: '' },
      unspecified: { zh: '状态未提供', hint: '' }
    },
    causalReason: {
      declared_unresolved: { zh: '来源标记为未解析', hint: '' },
      self_reference: { zh: '前因与后果指向同一事件', hint: '' },
      unresolved_or_conflicting: { zh: '引用缺失、重复或相互冲突', hint: '' },
      invalid_payoff_order: { zh: '埋设与兑现顺序待核', hint: '' },
      unresolved_endpoint: { zh: '事件引用未解析', hint: '' },
      duplicate_identity: { zh: '同一声明身份存在多条记录', hint: '' }
    }
  };
  function statusLabel(table, code) {
    var entry = code != null && code !== '' && STATUS_TEXT[table] && STATUS_TEXT[table][code];
    return entry ? entry.zh : code == null || code === '' ? '状态未提供' : '未识别状态（原文 ' + code + '）';
  }
  function statusHint(table, code) {
    var entry = code != null && code !== '' && STATUS_TEXT[table] && STATUS_TEXT[table][code];
    return entry && entry.hint ? entry.hint : '';
  }
  browse.states = { query: '', filter: 'all', kind: 'all', page: 0, selected: null, characterId: null, eventIndex: null };
  browse.stateQuotes = { page: 0 }; browse.stateAttributes = { page: 0 };
  var STATE_KINDS = { snapshot: '人物状态', transition: '变化声明', knowledge: '知情声明', turning: '转折声明' };

  function arr(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return v == null ? '' : String(v); }
  function num(v, d) { if (v == null || v === '') return d == null ? 0 : d; var n = +v; return isFinite(n) ? n : (d == null ? 0 : d); }
  function esc(v) {
    return str(v).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; });
  }
  function clip(v, n) { var s = str(v).trim(); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  function pct(v, total) { return total > 1 ? Math.max(0, Math.min(100, v / (total - 1) * 100)) : 0; }

  function chapterFor(i) {
    var c = index && index.eventChapter ? index.eventChapter[i] : null;
    return c == null ? null : (model.chapters[c] || null);
  }
  function eventStatus(e) {
    if (g.CLAtlasSource && g.CLAtlasSource.evidenceStatus) return g.CLAtlasSource.evidenceStatus(e);
    var quotes = evidenceText(e), inferred = e && (e.derived || e.inferred || e.basisCode === 'inference');
    return { code: inferred ? 'inference' : quotes.length ? 'quoted' : e ? 'synthesis' : 'unverified',
      label: inferred ? '推导' : quotes.length ? '有引文未核验' : e ? '归纳' : '未核验', quotes: quotes, anchored: false };
  }
  function eventBasis(e) { return eventStatus(e).label; }
  function eventClaim(e) {
    if (g.CLSkyEventClaim) return g.CLSkyEventClaim.classify(e);
    return { code: 'unknown', label: '类型未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断「主张还是发生」的文字。未标明不等于已发生。',
      isOccurrence: false, needsAttribution: false, isDeceptive: false };
  }
  function claimBadge(e) {
    if (g.CLSkyEventClaim) return g.CLSkyEventClaim.badge(e);
    var s = eventClaim(e);
    return { text: '? ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: '?' };
  }
  function claimNote(e) {
    var s = eventClaim(e);
    if (!s.needsAttribution || !s.hint) return '';
    var who = arr(e && e.characters).join('、');
    return (who ? who + '：' : '') + s.hint;
  }
  function eventPosition(e) {
    if (g.CLSkyPositionLabel) return g.CLSkyPositionLabel.of(e);
    var kind = e && e.sourcePosition && e.sourcePosition.kind;
    return { code: kind || 'unknown', label: kind === 'exact_quote' ? '精确引句定位' : '定位状态未提供',
      short: kind === 'exact_quote' ? '精确' : '未提供', located: kind === 'exact_quote',
      placesAtExactTime: kind === 'exact_quote', tone: kind === 'exact_quote' ? 'located' : 'unknown',
      hint: kind === 'exact_quote' ? '引句在唯一来源里逐字命中。' : '这份数据没有说明该事件的位置是怎么确定的。' };
  }
  function positionBadge(e) {
    var p = eventPosition(e);
    return { text: (p.tone === 'located' ? '◆ ' : p.tone === 'bounded' ? '◇ ' : p.tone === 'conflict' ? '⚠ ' : '? ') + p.short,
      label: p.label, hint: p.hint, code: p.code, tone: p.tone };
  }
  function eventIdentity(e) {
    if (!e) return null;
    var id = e.id != null && e.id !== '' ? str(e.id) : null;
    var entityId = e.entityId != null && e.entityId !== '' ? str(e.entityId) : null;
    if (id && entityId && id !== entityId) return null;
    return id || entityId;
  }
  function matchingSourcePosition(a, b) {
    return !!(a && b && a.sourceId != null && a.sourceId !== '' && b.sourceId != null && b.sourceId !== '' && a.textHash && b.textHash &&
      str(a.sourceId) === str(b.sourceId) && str(a.textHash) === str(b.textHash));
  }
  function positionBoundary(event, eventIndex, side) {
    var sp = event && event.sourcePosition, key = side === 'before' ? 'beforeEventId' : 'afterEventId';
    if (!sp || sp.kind !== 'legacy_interval') return { state: 'unavailable' };
    var id = sp[key];
    if (id == null || id === '') return { state: 'missing' };
    var matches = [];
    graph.events.forEach(function (candidate, i) { if (eventIdentity(candidate) === str(id)) matches.push({ event: candidate, index: i }); });
    if (matches.length !== 1) return { state: matches.length ? 'ambiguous' : 'missing' };
    var row = matches[0], bound = row.event.sourcePosition;
    if (row.index === eventIndex) return { state: 'conflict' };
    if (!matchingSourcePosition(sp, bound)) return { state: 'different-source' };
    if (!bound || bound.kind !== 'exact_quote') return { state: 'unavailable' };
    var raw = [sp.start, sp.end, bound && bound.start, bound && bound.end];
    if (!raw.every(function (n) { return typeof n === 'number' && Number.isInteger(n); })) return { state: 'unavailable' };
    var start = sp.start, end = sp.end, boundStart = bound.start, boundEnd = bound.end;
    if (start < 0 || end < start || boundStart < 0 || boundEnd <= boundStart) return { state: 'unavailable' };
    if ((side === 'before' && boundStart > start) || (side === 'after' && boundStart < end)) return { state: 'conflict' };
    return { state: 'matched', event: row.event, index: row.index };
  }
  function positionExplanationData(i) {
    var event = graph && graph.events && graph.events[i], status = eventPosition(event), sp = event && event.sourcePosition;
    var before = status.code === 'legacy_interval' ? positionBoundary(event, i, 'before') : { state: 'unavailable' };
    var after = status.code === 'legacy_interval' ? positionBoundary(event, i, 'after') : { state: 'unavailable' };
    if (before.state === 'matched' && after.state === 'matched' && before.index === after.index) {
      before = { state: 'ambiguous' }; after = { state: 'ambiguous' };
    }
    return { event: event, index: i, status: status, sourcePosition: sp,
      before: before, after: after };
  }
  function stopM103Tween() {
    if (m103.tween && g.CLSkyMotion) g.CLSkyMotion.cancelAll('m103');
    m103.tween = null; m103.request++;
  }
  function clearM103() {
    stopM103Tween(); m103.open = false; m103.eventIndex = null; m103.returnSnapshot = null;
  }
  function positionBoundaryMarkup(boundary, side) {
    var label = side === 'before' ? '前界' : '后界';
    if (boundary && boundary.state === 'matched') {
      return '<button type="button" class="sd-position-boundary" data-action="position-boundary" data-position-side="' + side + '" data-event-index="' + boundary.index + '"><small>原文' + label + '</small><b>' + esc(eventTitle(boundary.event)) + '</b><span>阅读此事件及其依据</span></button>';
    }
    var missing = !boundary || boundary.state === 'missing' ? label + '未提供' : boundary.state === 'ambiguous' ? label + '记录不唯一，未显示名称' : boundary.state === 'conflict' ? label + '顺序冲突，未显示名称' : boundary.state === 'unavailable' ? label + '位置数据不足，未显示名称' : label + '来源不匹配，未作比较';
    return '<div class="sd-position-boundary is-missing"><small>原文' + label + '</small><b>' + esc(missing) + '</b></div>';
  }
  function renderPositionExplanation(eventIndex) {
    var d = positionExplanationData(eventIndex), p = d.status, bounded = p.code === 'legacy_interval';
    var matchedBounds = (d.before.state === 'matched' ? 1 : 0) + (d.after.state === 'matched' ? 1 : 0);
    var boundaryNote = matchedBounds === 2 ? '当前两侧均找到同源、同版本的定位边界。'
      : matchedBounds === 1 ? '当前只有一侧找到可核验的定位边界；另一侧未提供或无法核验。'
      : '当前没有可核验的事件边界；范围端点保持开放。';
    var detail = bounded
      ? '<p class="sd-position-explanation-note">' + boundaryNote + '边界只在同一来源和文本版本中比较。</p><div class="sd-position-span' + (d.before.state === 'matched' ? '' : ' is-open-before') + (d.after.state === 'matched' ? '' : ' is-open-after') + '" aria-label="原文位置范围"><span class="sd-position-bracket" aria-hidden="true"></span>' +
        positionBoundaryMarkup(d.before, 'before') +
        '<div class="sd-position-range"><i class="sd-position-texture" aria-hidden="true"></i><b>具体位置未定</b></div>' +
        positionBoundaryMarkup(d.after, 'after') + '</div><p class="sd-position-explanation-note">这只说明原文位置范围，不代表剧情持续时间；不推测范围中的精确落点。</p>'
      : '<p class="sd-position-explanation-note"><b>' + esc(p.label) + '</b> · ' + esc(p.hint) + '</p>' +
        (p.code === 'exact_quote' ? '<p class="sd-position-explanation-note">该记录有精确引句锚点；引句位置准确不代表事件结论已核实。</p>' : p.code === 'conflicted' ? '<p class="sd-position-explanation-note">来源之间无法排出唯一顺序，因此不展开边界名称。</p>' : '<p class="sd-position-explanation-note">当前没有可展开的可信位置边界。</p>');
    return '<section class="sd-position-explanation" data-position-explanation data-position-event-index="' + eventIndex + '" data-position-kind="' + esc(p.code) + '"><div class="sd-position-explanation-head"><b>位置说明 · ' + esc(p.label) + '</b><button type="button" class="sd-detail-action sd-position-explain-action" data-action="position-explain" data-event-index="' + eventIndex + '">收起位置说明</button></div>' + detail + '</section>';
  }
  function animatePositionExplanation() {
    var stage = root && root.querySelector('[data-position-explanation]'); if (!stage) return;
    stopM103Tween(); var request = ++m103.request;
    function paint(v) { if (request !== m103.request || !stage.isConnected) return; stage.style.setProperty('--sd-position-progress', String(v)); stage.setAttribute('data-phase', v >= 1 ? 'settled' : 'opening'); }
    if ((g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) || !g.CLSkyMotion) { paint(1); return; }
    paint(0);
    m103.tween = g.CLSkyMotion.tween({ from: 0, to: 1, dur: .6, ease: function (v) { return v; }, tag: 'm103', onUpdate: paint, onDone: function () { if (request === m103.request) { paint(1); m103.tween = null; } } });
  }
  function openPositionExplanation(eventIndex) {
    if (!graph || !graph.events[eventIndex]) return false;
    clearM103(); m103.open = true; m103.eventIndex = eventIndex;
    state.mode = 'evidence'; state.focus = 'e:' + eventIndex;
    state.restore = { attr: 'data-event-index', value: String(eventIndex), action: 'position-explain' };
    render(); animatePositionExplanation();
    var stage = root && root.querySelector('[data-position-explanation]'); if (stage && stage.scrollIntoView) stage.scrollIntoView({ block: 'nearest' });
    return true;
  }
  function readPositionBoundary(side) {
    if (!m103.open || ['before', 'after'].indexOf(side) < 0) return false;
    var sourceIndex = m103.eventIndex, d = positionExplanationData(sourceIndex), bound = d[side];
    if (!bound || bound.state !== 'matched') return false;
    var source = d.sourcePosition, body = doc.getElementById('skyDeconBody');
    stopM103Tween();
    m103.returnSnapshot = {
      graph: graph, sourceIndex: sourceIndex, sourceId: str(source.sourceId), textHash: str(source.textHash),
      boundaryIndex: bound.index, scrollTop: body ? body.scrollTop : 0,
      page: browse.evidence.page, query: browse.evidence.query, filter: browse.evidence.filter,
      kind: browse.evidence.kind, person: browse.evidence.person, order: browse.evidence.order, quotePage: browse.quotes.page
    };
    m103.open = false; m103.eventIndex = null;
    browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = '';
    var ordered = evidenceItems(), at = ordered.map(function (x) { return x.i; }).indexOf(bound.index);
    browse.evidence.page = Math.floor(Math.max(0, at) / PAGE_SIZE); browse.quotes.page = 0;
    state.mode = 'evidence'; selectEvent(bound.index);
    return true;
  }
  function returnToPositionExplanation() {
    var snap = m103.returnSnapshot;
    if (!snap || snap.graph !== graph) { clearM103(); render(); return false; }
    var event = graph.events[snap.sourceIndex], sp = event && event.sourcePosition;
    if (!event || !sp || str(sp.sourceId) !== snap.sourceId || str(sp.textHash) !== snap.textHash) { clearM103(); render(); return false; }
    browse.evidence.page = snap.page; browse.evidence.query = snap.query; browse.evidence.filter = snap.filter;
    browse.evidence.kind = snap.kind; browse.evidence.person = snap.person; browse.evidence.order = snap.order; browse.quotes.page = snap.quotePage;
    openPositionExplanation(snap.sourceIndex);
    var body = doc.getElementById('skyDeconBody'); if (body) body.scrollTop = snap.scrollTop;
    return true;
  }
  function basisClass(b) { return b === '原文已核验' ? 'is-source' : b === '推导' ? 'is-derived' : b === '有引文未核验' || b === '未核验' ? 'is-unknown' : 'is-summary'; }
  function lineBasis(line) {
    var meta = graph && graph.meta || {}, current = meta.storylines || {}, provenance;
    if (g.CLSkyModel && g.CLSkyModel.storylineProvenance) provenance = g.CLSkyModel.storylineProvenance(graph || {}, line);
    else if (line && (line.derived || line.src === 'derived' || line.src === 'local-completion')) provenance = 'derived';
    else if (line && line.provenance === 'assistant-reviewed-source') provenance = 'assistant-reviewed-source';
    else if (line && line.provenance === 'model') provenance = 'synthesis';
    else if (current.derived || current.src === 'derived' || current.src === 'local-completion') provenance = 'derived';
    else if (current.src === 'assistant-reviewed-source') provenance = 'assistant-reviewed-source';
    else if (current.src !== 'model' && current.src !== 'mixed' && meta.completion && meta.completion.method === 'existing-graph-local-completion') provenance = 'derived';
    return provenance === 'derived' ? '推导' : provenance === 'assistant-reviewed-source' ? '对话审阅 · 待复核' : '归纳';
  }
  function lineProvenance(line) {
    if (g.CLSkyLineProvenance) {
      return g.CLSkyLineProvenance.of(line, (graph && graph.meta && graph.meta.storylines) || {});
    }
    return { code: 'unknown', label: '来源未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有标明这条线是怎么来的。未标明不等于已审阅。',
      countsAsStructure: false, navigableOnly: false, hasIndependenceBasis: false };
  }
  function lineProvenanceBadge(line) {
    var p = lineProvenance(line);
    var mark = p.code === 'mechanical' ? '▤' : p.code === 'reviewed' ? '◆'
      : p.code === 'derived' ? '◇' : '?';
    return { text: mark + ' ' + p.short, label: p.label, tone: p.tone, code: p.code, hint: p.hint };
  }
  function causalType(edge) {
    if (g.CLSkyCausalType) return g.CLSkyCausalType.of(edge);
    return { code: 'unknown', label: '类型未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断因果类型的文字。未标明不等于直接触发。',
      isEstablishedCausality: false, needsAttribution: false, mustNotBeCausalEdge: false };
  }
  function causalTypeBadge(edge) {
    if (g.CLSkyCausalType) return g.CLSkyCausalType.badge(edge);
    var s = causalType(edge);
    return { text: '? ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: '?' };
  }
  function foreshadowStage(rec) {
    if (g.CLSkyForeshadowStage) return g.CLSkyForeshadowStage.of(rec);
    return { code: 'unknown', label: '阶段未标明', short: '未标明', tone: 'unknown',
      hint: '记录没有给出足以判断阶段的信息。未标明不等于已兑现。',
      bothEndsVerifiable: false, closed: false, isDefect: false, openIsNotDefect: false };
  }
  function foreshadowStageBadge(rec) {
    if (g.CLSkyForeshadowStage) return g.CLSkyForeshadowStage.badge(rec);
    var s = foreshadowStage(rec);
    return { text: '? ' + s.short, label: s.label, tone: s.tone, code: s.code, mark: '?' };
  }
  function stateTransition(rec) {
    if (g.CLSkyStateTransition) return g.CLSkyStateTransition.of(rec);
    return { code: 'incomplete', label: '前后依据不全', hint: '缺少前值或后值。无前后依据不画成长箭头。',
      facet: 'unknown', facetLabel: '面向未标明', reversibility: 'unknown', reversibilityLabel: '未标明',
      evidential: 'unknown', canDrawGrowth: false, isEmotionalMoment: false,
      isOthersEvaluation: false, mustNotCountAsGrowth: true };
  }
  function stateTransitionBadge(rec) {
    if (g.CLSkyStateTransition) return g.CLSkyStateTransition.badge(rec);
    var s = stateTransition(rec);
    var mark = s.canDrawGrowth ? '→' : s.isEmotionalMoment ? '～' : s.isOthersEvaluation ? '❞' : '…';
    return { text: mark + ' ' + s.label, label: s.label, code: s.code, mark: mark,
      facetLabel: s.facetLabel, reversibilityLabel: s.reversibilityLabel,
      tone: s.canDrawGrowth ? 'growth' : 'flat' };
  }
  function knowledgeView(rec, opts) {
    if (g.CLSkyKnowledgeView) return g.CLSkyKnowledgeView.audit(rec, opts);
    return { code: 'unknown', label: '认知未标明', hint: '记录没有给出足以判断认知状态的依据。',
      tone: 'unknown', countsAsKnowing: false, isFalseBelief: false,
      mustNotAttributeToCharacter: false, downgraded: false, acquisition: {}, anachronism: {} };
  }
  function knowledgeBadge(rec, opts) {
    if (g.CLSkyKnowledgeView) return g.CLSkyKnowledgeView.badge(rec, opts);
    var s = knowledgeView(rec, opts);
    return { text: '? ' + s.label, label: s.label, tone: s.tone, code: s.code, mark: '?' };
  }
  function relationScope(rel) {
    if (g.CLSkyRelationScope) return g.CLSkyRelationScope.of(rel);
    return { kind: 'other', kindLabel: '其他类型', kindHint: '尚未归类。',
      isCopresence: false, needsManualKind: true,
      evidence: 'inherited-pending', evidenceLabel: '继承 · 待核验',
      evidenceHint: '这条关系没有已核验的原文引句。',
      anchored: false, mustShowPending: true,
      scope: 'bookSummary', scopeLabel: '全书汇总',
      scopeHint: '这是跨越全书的汇总结论，不对应某一时刻。',
      isBookSummary: true, strengthIsEvidence: false };
  }
  function relationScopeBadge(rel) {
    if (g.CLSkyRelationScope) return g.CLSkyRelationScope.badge(rel);
    var s = relationScope(rel);
    return { text: '◇ ' + s.kindLabel + ' · 全', label: s.kindLabel,
      evidenceLabel: s.evidenceLabel, scopeLabel: s.scopeLabel,
      code: s.kind, evidence: s.evidence, scope: s.scope, mark: '◇',
      tone: s.anchored ? 'anchored' : 'pending' };
  }
  function worldSetting(rec) {
    if (g.CLSkyWorldObject) return g.CLSkyWorldObject.of(rec);
    return { kind: 'unknown', kindLabel: '类型未标明', kindHint: '记录没有给出足以判断的文字。' };
  }
  function worldSettingBadge(rec) {
    if (g.CLSkyWorldObject) return g.CLSkyWorldObject.badge(rec);
    var s = worldSetting(rec);
    return { text: '? ' + s.kindLabel, label: s.kindLabel, kind: s.kind, mark: '?', tone: 'unknown' };
  }
  function themeTension(rec) {
    if (g.CLSkyThemeTension) return g.CLSkyThemeTension.of(rec);
    return { kind: 'unknown', kindLabel: '类型未标明',
      interpretability: { complete: false, missing: [], missingLabels: [], hint: '' },
      frame: { forced: false }, isInterpretation: true };
  }
  function themeTensionBadge(rec) {
    if (g.CLSkyThemeTension) return g.CLSkyThemeTension.badge(rec);
    var s = themeTension(rec);
    return { text: '? ' + s.kindLabel, label: s.kindLabel, kind: s.kind, mark: '?', tone: 'plain' };
  }
  function nameBudget(req) {
    if (g.CLSkyNameBudget) return g.CLSkyNameBudget.of(req);
    return { tier: 'unknown', tierLabel: '档次未标明', shapes: [], shapeLabels: [],
      label: (req && req.name) || '未命名对象', full: null, abbreviated: false,
      isPlaceholder: true, fullRetained: true };
  }
  function personKey(p) {
    if (!p) return '';
    var raw = p.raw || {};
    var id = raw.id != null ? raw.id : raw.entityId;
    if (id != null && String(id).trim()) return String(id);
    return 'name:' + String(p.name || '');
  }
  /* P4.6：**统一搜索索引**（跨类型）。
     实测背景：本文件有 **7 个**独立的 `searchControl(...)`，每个只在自己那层过滤
     ⇒ 计划要的「人物/别名/事件/任务/线路搜索结果显示类型和上下文」不存在，
     读者必须先知道去哪一层才能搜。
     实测收益（大奉）：「许七安」一次命中 **1722 条、跨 4 类**
     （人物 43 / 事件 1665 / 任务 12 / 线路 2）—— 这是 7 个分层搜索做不到的。
     本模块只建索引与检索；把 7 个分层框换成统一入口是接线工作，尚未做。 */
  function searchIndex(model) {
    if (!g.CLSkySearchIndex) return { items: [], tally: null };
    var items = g.CLSkySearchIndex.build(graph || {});
    return { items: items, tally: g.CLSkySearchIndex.tally(items) };
  }
  function readingVoice(signals) {
    if (g.CLSkyReadingVoice) return g.CLSkyReadingVoice.voice(signals);
    return { code: 'unknown', label: '状态未标明', text: '状态未标明',
      hint: '记录没有标明这是哪种状态。', basis: 'no_module' };
  }
  function readingLayer(what) {
    if (g.CLSkyReadingVoice) return g.CLSkyReadingVoice.layerOf(what);
    return { code: 'unknown', zh: '层级未标明', rank: null };
  }
  function evidenceText(e) {
    var out = [];
    if (e && str(e.quote).trim()) out.push(str(e.quote).trim());
    arr(e && e.evidence).forEach(function (x) {
      var s = typeof x === 'string' ? x : x && (x.quote || x.text || x.value);
      if (str(s).trim() && out.indexOf(str(s).trim()) < 0) out.push(str(s).trim());
    });
    return out;
  }
  function allEvidenceText(e) {
    var quotes = evidenceText(e);
    if (g.CLAtlasSource && g.CLAtlasSource.sourceRefs) g.CLAtlasSource.sourceRefs(e).forEach(function (ref) {
      var q = str(ref.quote).trim(); if (q && quotes.indexOf(q) < 0) quotes.push(q);
    });
    return quotes;
  }
  function eventTitle(e) { return clip(e && (e.title || e.summary || e.kind), 34) || '未命名剧情点'; }
  function reviewNotes(entity, type) {
    var key = entity && (entity.id != null ? entity.id : entity.entityId), issues = arr(graph && graph.reviewIssues).filter(function (issue) {
      return key != null && (type === 'character' ? str(issue.characterId) === str(key) : str(issue.eventId) === str(key) || arr(issue.eventIds).map(str).indexOf(str(key)) >= 0);
    });
    if (!issues.length) return '';
    return '<aside class="sd-review-note"><b>' + (type === 'character' && entity.identityStatus === 'ambiguous' ? '身份需区分 · 属性分暂停展示' : '原文核验批注') + '</b>' + issues.slice(0, 3).map(function (issue) {
      return '<p>' + esc(issue.description) + '</p><button type="button" class="sd-detail-action" data-action="read-review" data-review-key="' + esc(issue.id) + '">阅读依据与完整批注</button>';
    }).join('') + (issues.length > 3 ? '<p>另有 ' + (issues.length - 3) + ' 条，可在核验批注中查阅。</p>' : '') + '</aside>';
  }
  function searchText(values) { return values.map(str).join(' ').toLocaleLowerCase(); }

  function structureFacts() {
    var own = Object.prototype.hasOwnProperty, chars = arr(graph.characters), events = arr(graph.events), camps = arr(graph.camps), relations = arr(graph.relations);
    function recordId(row) { var id = row && (row.id != null ? row.id : row.entityId); return id == null || id === '' ? null : String(id); }
    function counts(rows) { var out = Object.create(null); rows.forEach(function (row) { var id = recordId(row); if (id != null) out[id] = (out[id] || 0) + 1; }); return out; }
    var relationProjection = g.CLSkyModel && g.CLSkyModel.relationPeople ? g.CLSkyModel.relationPeople(graph).people : [];
    var personIds = counts(chars), eventIds = counts(events), relationIds = counts(relations), peopleByName = Object.create(null), projectedById = Object.create(null);
    chars.forEach(function (row) { if (row && row.name != null) (peopleByName[String(row.name)] || (peopleByName[String(row.name)] = [])).push(row); });
    relationProjection.forEach(function (row) { if (row && row.id != null) (projectedById[String(row.id)] || (projectedById[String(row.id)] = [])).push(row); });
    function uniquePerson(name) {
      if (typeof name !== 'string' || !name) return null;
      var found = peopleByName[String(name)] || [];
      if (found.length !== 1) return null;
      var id = recordId(found[0]), projected = id && personIds[id] === 1 ? projectedById[id] || [] : [];
      return id && personIds[id] === 1 && projected.length === 1 && projected[0].selectable
        ? { id: id, name: found[0].name, identity: found[0].identity || found[0].role || '' } : null;
    }
    function tally(field) {
      var provided = own.call(graph, field), value = graph[field];
      return { provided: provided && Array.isArray(value), count: provided && Array.isArray(value) ? value.length : null };
    }
    var personRows = chars.filter(function (row) { return row && typeof row === 'object'; }), personSample = null;
    for (var pi = 0; pi < personRows.length && !personSample; pi++) personSample = uniquePerson(personRows[pi].name);
    var groupRows = camps.filter(function (row) { return row && typeof row === 'object'; }), groupNames = counts(groupRows.map(function (row) { return { id: row.name }; })), groupSample = null;
    for (var gi = 0; gi < groupRows.length && !groupSample; gi++) {
      var group = groupRows[gi], memberNames = arr(group.members).filter(function (name) { return typeof name === 'string'; }), members = [];
      memberNames.forEach(function (name) { var p = uniquePerson(name); if (p && members.length < 4 && !members.some(function (x) { return x.id === p.id; })) members.push(p); });
      if (group.name && groupNames[String(group.name)] === 1 && members.length) groupSample = { name: String(group.name), index: gi, ids: members.map(function (p) { return p.id; }), members: members, memberTotal: memberNames.length, key: 'camps:' + gi + ':' + String(group.name) };
    }
    var relationSample = null;
    for (var ri = 0; ri < relations.length && !relationSample; ri++) {
      var relation = relations[ri]; if (!relation || typeof relation !== 'object') continue;
      var relationId = recordId(relation), a = uniquePerson(relation.a), b = uniquePerson(relation.b);
      if (relationId && relationIds[relationId] === 1 && a && b && a.id !== b.id) {
        var scope = g.CLSkyRelationScope && relation ? g.CLSkyRelationScope.of(relation) : null;
        relationSample = { id: relationId, a: a, b: b, kind: relation.kind || '关系类型未提供',
          scope: scope && scope.scopeLabel || '范围未标明' };
      }
    }
    var eventSample = null;
    for (var ei = 0; ei < events.length && !eventSample; ei++) {
      var event = events[ei]; if (!event || typeof event !== 'object') continue;
      var eventId = recordId(event);
      if (eventId && eventIds[eventId] === 1) eventSample = { id: eventId, index: ei,
        title: event.title || event.summary || '剧情点', chapter: event.chapter || '章节范围未提供' };
    }
    var allLines = arr(model.mains).concat(arr(model.lines));
    function provenance(line) { return g.CLSkyModel && g.CLSkyModel.storylineProvenance ? g.CLSkyModel.storylineProvenance(graph, line) : line && line.provenance || ''; }
    var autoLines = allLines.filter(function (line) { return line && line.autoSegment === true; }).length;
    var derivedLines = allLines.filter(function (line) { return line && !line.autoSegment && (line.derived === true || provenance(line) === 'derived'); }).length;
    var synthesisLines = allLines.filter(function (line) { return line && !line.autoSegment && provenance(line) === 'synthesis'; }).length;
    var reviewedLines = allLines.filter(function (line) { return line && !line.autoSegment && provenance(line) === 'assistant-reviewed-source'; }).length;
    var unknownLines = allLines.filter(function (line) { return line && !line.autoSegment && ['derived', 'synthesis', 'assistant-reviewed-source'].indexOf(provenance(line)) < 0; }).length;
    var chapterRows = arr(model.chapters), axisRows = chapterRows.filter(function (chapter) { return chapter && chapter.raw != null && !chapter.special; }).length;
    var otherAxisRows = chapterRows.filter(function (chapter) { return !chapter || chapter.raw == null || chapter.special; }).length;
    return {
      scope: '当前载入图谱全量记录',
      people: { provided: own.call(graph, 'characters') && Array.isArray(graph.characters), count: own.call(graph, 'characters') && Array.isArray(graph.characters) ? chars.length : null, sample: personSample },
      groups: tally('camps'), groupSample: groupSample,
      relations: { provided: own.call(graph, 'relations') && Array.isArray(graph.relations), count: own.call(graph, 'relations') && Array.isArray(graph.relations) ? relations.length : null, sample: relationSample },
      events: { provided: own.call(graph, 'events') && Array.isArray(graph.events), count: own.call(graph, 'events') && Array.isArray(graph.events) ? events.length : null, sample: eventSample },
      axis: { summary: model.axis && model.axis.summary || '原文顺序轴说明未提供', sequential: axisRows, otherMaterials: otherAxisRows },
      units: tally('narrativeUnits'), clues: tally('clues'), causes: tally('causeEdges'),
      routes: { mains: arr(model.mains).length, branches: arr(model.lines).filter(function (line) { return line && (line.kind === 'branch' || line.kind === 'twig'); }).length,
        mainDeclared: arr(model.mains).filter(function (line) { return line && !line.autoSegment && provenance(line) === 'assistant-reviewed-source'; }).length,
        branchDeclared: arr(model.lines).filter(function (line) { return line && !line.autoSegment && provenance(line) === 'assistant-reviewed-source'; }).length,
        autoSegments: autoLines, derived: derivedLines,
        synthesis: synthesisLines, sourceUnclear: unknownLines, reviewed: reviewedLines }
    };
  }

  function buildIndex() {
    var eventChapter = {}, people = Object.create(null), eventIds = Object.create(null), list, ch, n, events = [], kinds = [], roles = [], layers = {};
    arr(model.chapterEvents).forEach(function (items, c) { arr(items).forEach(function (ev) { eventChapter[ev] = c; }); });
    arr(graph.characters).forEach(function (c) { if (c && c.name) people[c.name] = { name: c.name, raw: c, events: [], chapters: [], lines: [] }; });
    arr(graph.events).forEach(function (ev, ei) {
      var status = eventStatus(ev);
      [ev && ev.id, ev && ev.entityId].forEach(function (eid) {
        if (eid == null || eid === '') return;
        if (!Object.prototype.hasOwnProperty.call(eventIds, str(eid))) eventIds[str(eid)] = ei;
        else if (eventIds[str(eid)] !== ei) eventIds[str(eid)] = null;
      });
      events.push({ e: ev, i: ei, status: status, score: (KEY_EVENT.test(str(ev && ev.kind)) ? 50 : 0) + (status.anchored ? 15 : 0) + arr(ev && ev.characters).length,
        search: searchText([ev && ev.title, ev && ev.summary, ev && ev.chapter, ev && ev.kind, arr(ev && ev.characters).join(' '), status.quotes.join(' ')]) });
      if (ev && ev.kind && kinds.indexOf(ev.kind) < 0) kinds.push(ev.kind);
      arr(ev && ev.characters).forEach(function (name) {
        n = people[name] || (people[name] = { name: name, raw: {}, events: [], chapters: [], lines: [] });
        if (n.events[n.events.length - 1] !== ei) n.events.push(ei);
        ch = eventChapter[ei];
        if (ch != null && n.chapters.indexOf(ch) < 0) n.chapters.push(ch);
      });
    });
    arr(model.mains).concat(arr(model.lines)).forEach(function (line) {
      arr(line.cast).forEach(function (name) { if (people[name] && people[name].lines.indexOf(line.id) < 0) people[name].lines.push(line.id); });
    });
    list = Object.keys(people).map(function (k) { return people[k]; });
    list.forEach(function (p) {
      var c = p.raw;
      p.search = searchText([p.name, arr(c.aliases).join(' '), c.role, c.camp, c.identity, c.brief, arr(c.traits).join(' ')]);
      if (c.role && roles.indexOf(c.role) < 0) roles.push(c.role);
    });
    list.sort(function (a, b) { return b.events.length - a.events.length || a.name.localeCompare(b.name, 'zh'); });
    Object.keys(LAYERS).forEach(function (key) {
      var records = arr(graph[key]).filter(function (entity) { return entity && typeof entity === 'object'; }), reserved = Object.create(null), ids = Object.create(null);
      function recordId(entity) { var id = entity.id != null ? entity.id : entity.entityId; return id == null || id === '' ? null : str(id); }
      records.forEach(function (entity) { var id = recordId(entity); if (id != null) { reserved[id] = true; ids[id] = (ids[id] || 0) + 1; } });
      layers[key] = records.map(function (entity, i) {
        var status = mechanicsStatus(key, entity).code;
        var id = recordId(entity), rowKey = id;
        if (id == null || ids[id] !== 1) { rowKey = key + ':' + i; while (reserved[rowKey]) rowKey = ':' + rowKey; reserved[rowKey] = true; }
        return { raw: entity, i: i, key: rowKey, recordId: id, status: status,
          search: searchText([entity.name, entity.character, entity.a, entity.b, entity.kind, entity.desc, entity.goal, entity.obstacle, entity.action, entity.outcome, entity.cost,
            entity.chapter, entity.summary, entity.description, entity.quote, entity.seedQuote, entity.payoffQuote,
            arr(entity.attributes).map(function (a) { return a && [a.name, a.value, a.quote].join(' '); }).join(' ')]) };
      });
    });
    var reading = model.narrative && model.narrative.characterReading || {}, stateRows = [];
    [['states', 'snapshot'], ['transitions', 'transition'], ['knowledge', 'knowledge'], ['turningPoints', 'turning']].forEach(function (pair) {
      arr(reading[pair[0]]).forEach(function (entity) {
        var e = entity.eventIndex == null ? null : graph.events[entity.eventIndex];
        stateRows.push({ key: entity.key, kind: pair[1], raw: entity, status: eventStatus(entity),
          search: searchText([entity.character, entity.ownerName, entity.chapter, entity.summary, entity.description, entity.text, entity.before, entity.after,
            e && e.title, e && e.chapter, allEvidenceText(entity).join(' '), arr(entity.attributes).map(function (a) { return a && [a.name, a.value, a.quote].join(' '); }).join(' ')]) });
      });
    });
    stateRows.sort(function (a, b) { return (a.raw.eventIndex == null ? Infinity : a.raw.eventIndex) - (b.raw.eventIndex == null ? Infinity : b.raw.eventIndex); });
    return { eventChapter: eventChapter, people: list, peopleByName: people, events: events, kinds: kinds.sort(), roles: roles, eventIds: eventIds, layers: layers, stateRows: stateRows,
      structure: structureFacts(),
      coverage: g.CLSkyCoverage ? g.CLSkyCoverage.summarize(graph, g.CLAtlasSource) : null };
  }

  function ensure() {
    if (root) return root;
    root = doc.createElement('aside');
    root.id = 'skyDeconPanel'; root.className = 'sky-decon-panel'; root.hidden = true;
    root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'false'); root.setAttribute('aria-labelledby', 'skyDeconTitle');
    root.innerHTML =
      '<header class="sd-head"><div><div class="sd-eyebrow"><i></i>叙事解剖 · <b>NARRATIVE DISSECTION</b></div><h2 id="skyDeconTitle">全书叙事 DNA</h2><p id="skyDeconSub">从全书形状进入故事线、人物和证据</p></div><button type="button" class="sd-close" data-action="close" aria-label="关闭叙事解剖">×</button></header>' +
      '<nav class="sd-tabs" role="tablist" aria-label="解构视图"><button id="skyDeconTabOverview" type="button" role="tab" aria-selected="true" aria-controls="skyDeconBody" data-mode="overview">全书 DNA</button><button id="skyDeconTabLines" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="lines">故事骨架</button><button id="skyDeconTabPeople" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="people">人物弧线</button><button id="skyDeconTabEvidence" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="evidence">证据层</button><button id="skyDeconTabMechanics" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="mechanics">情节证据</button><button id="skyDeconTabCausal" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="causal">因果网络</button><button id="skyDeconTabForeshadow" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="foreshadow">伏笔</button><button id="skyDeconTabStates" type="button" role="tab" aria-selected="false" aria-controls="skyDeconBody" data-mode="states">状态与视野</button></nav>' +
      '<div class="sd-meta" id="skyDeconMeta" role="status" aria-live="polite"></div><div class="sd-scroll" id="skyDeconBody" role="tabpanel" tabindex="-1" aria-labelledby="skyDeconTabOverview"></div>' +
      '<footer class="sd-foot">' +
      '<span><i class="sd-key is-source"></i>原文已核验</span>' +
      '<span><i class="sd-key is-unknown"></i>有引文未核验（虚线边框）</span>' +
      '<span><i class="sd-key is-summary"></i>归纳</span>' +
      '<span><i class="sd-key is-derived"></i>推导</span>' +
      '<span><i class="sd-key is-cause-src"></i>因果 · 前因</span>' +
      '<span><i class="sd-key is-cause-dst"></i>因果 · 后果</span>' +
      '<span><i class="sd-key is-broken"></i>引用断裂 / 身份冲突</span>' +
      '</footer>';
    doc.body.appendChild(root);
    button = doc.getElementById('skyDecode');
    root.addEventListener('click', onClick);
    root.addEventListener('input', onInput);
    root.addEventListener('change', onChange);
    root.addEventListener('keydown', function (e) {
      var tab = e.target;
      if (!tab || tab.getAttribute('role') !== 'tab' || !tab.closest || !tab.closest('.sd-tabs') || !/^(ArrowLeft|ArrowRight|Home|End)$/.test(e.key)) return;
      var tabs = Array.prototype.slice.call(root.querySelectorAll('.sd-tabs [role="tab"]')), at = tabs.indexOf(tab), next = at;
      if (e.key === 'ArrowLeft') next = (at + tabs.length - 1) % tabs.length;
      if (e.key === 'ArrowRight') next = (at + 1) % tabs.length;
      if (e.key === 'Home') next = 0;
      if (e.key === 'End') next = tabs.length - 1;
      e.preventDefault(); tabs[next].focus({ preventScroll: true });
      if (tabs[next].scrollIntoView) tabs[next].scrollIntoView({ block: 'nearest', inline: 'nearest' });
      setMode(tabs[next].getAttribute('data-mode'));
    });
    doc.addEventListener('click', function (e) {
      if (suppressOutsideClose) { suppressOutsideClose = 0; return; }
      if (!state.open || !root || root.hidden || e.target === root || root.contains(e.target)) return;
      if (e.composedPath && e.composedPath().indexOf(root) >= 0) return;
      if (button && button.contains(e.target)) return;
      if (e.target.closest && e.target.closest('.sky-top')) return;
      if (e.target.closest && e.target.closest('.skg-deck')) return;
      close();
    });
    g.addEventListener('keydown', function (e) { if (state.open && e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); if (m84.open) cancelM84(true, true); else close(true); } }, true);
    return root;
  }

  function syncButton() {
    button = button || doc.getElementById('skyDecode');
    if (button) { button.setAttribute('aria-pressed', String(state.open)); button.classList.toggle('is-on', state.open); }
    if (root) root.hidden = !state.open;
    doc.body.classList.toggle('sky-decon-on', state.open);
  }
  function setMode(mode) {
    if (['overview', 'lines', 'people', 'evidence', 'mechanics', 'causal', 'foreshadow', 'states'].indexOf(mode) < 0) mode = 'overview';
    if (mode === 'overview' && m84.returning) { returnStructureOverview(); return; }
    if (m88.recordId && mode !== 'foreshadow' && !(mode === 'evidence' && m88.snapshot && m88.snapshot.view === 'event')) m88Close();
    if (mode !== 'causal' && (causalFork.source != null || causalFork.returnTo)) { stopCausalForkTween(); stopCausalForkLayout(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; causalFork.staticReason = ''; }
    if (m106.open && mode !== state.mode) clearM106();
    if (mode !== 'overview' && m84.open) cancelM84(true);
    if (mode !== 'people') { if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); browse.neighbors.bId = ''; browse.neighbors.result = null; browse.neighbors.demoCounts = null; browse.neighbors.origin = null; }
    if (searchTimer != null) { g.clearTimeout(searchTimer); searchTimer = null; }
    state.mode = mode; state.focus = null;
    if (mode === 'overview' && m84.selected) state.restore = { attr: 'data-structure-layer', value: m84.selected };
    render();
  }
  function open() {
    if (!state.ready) syncGraph();
    ensure(); state.open = true; syncButton(); render();
    reframe();
    var closeBtn = root.querySelector('.sd-close'); if (closeBtn && closeBtn.focus) closeBtn.focus({ preventScroll: true });
  }
  function close(refocus) {
    m88Close(); m88.scope = 'reading'; m88Unwatch();
    stopCausalForkTween(); stopCausalForkLayout(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; causalFork.staticReason = '';
    cancelM84(true);
    clearM103();
    clearM106();
    clearM84Return();
    if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
    browse.neighbors.bId = ''; browse.neighbors.result = null; browse.neighbors.demoCounts = null; browse.neighbors.origin = null; browse.neighbors.returnAfterBasis = false;
    state.open = false; syncButton();
    reframe();
    if (refocus && button && button.focus) button.focus({ preventScroll: true });
  }
  function reframe() {
    try { if (g.CLSky && g.CLSky.reframeForReading) g.CLSky.reframeForReading(null); } catch (eR) {}
  }
  function closeToPlot() {
    state.restore = null; close(false);
    if (button && button.focus) button.focus({ preventScroll: true });
  }
  function toggle() { if (state.open) close(true); else open(); }

  function onClick(e) {
    var b = e.target.closest && e.target.closest('button'); if (!b) return;
    if (searchTimer != null) { g.clearTimeout(searchTimer); searchTimer = null; }
    var action = b.getAttribute('data-action'), mode = b.getAttribute('data-mode');
    var layer = b.getAttribute('data-layer');
    if (action === 'foreshadow-echo-open') { openM88(b.getAttribute('data-foreshadow-id')); return; }
    if (action === 'foreshadow-echo-close') { closeM88(); return; }
    if (action === 'foreshadow-echo-stop') { m88Stop(); var stopButton = root.querySelector('[data-action="foreshadow-echo-stop"]'); if (stopButton) stopButton.disabled = true; return; }
    if (action === 'foreshadow-echo-replay') { animateM88(); return; }
    if (action === 'foreshadow-echo-scope') { var scopeWasSource = m88.snapshot && m88.snapshot.view === 'source'; m88Stop(); m88.sourceRequest++; m88.source = null; m88.sourceStatus = scopeWasSource ? 'unavailable:阅读范围已变化，原文请求已取消。' : null; m88.scope = m88.scope === 'published' ? 'reading' : 'published'; if (m88.snapshot) m88.snapshot.scope = m88.scope; state.restore = { attr: 'data-action', value: 'foreshadow-echo-scope' }; render(); animateM88(); return; }
    if (action === 'foreshadow-echo-read') { m88Read(b.getAttribute('data-echo-side')); return; }
    if (action === 'foreshadow-echo-source-back') { returnM88(); return; }
    if (action === 'foreshadow-echo-event-return') { returnM88(); return; }
    if (action === 'foreshadow-echo-event') {
      var echoIndex = +b.getAttribute('data-event-index'), echoSide = b.getAttribute('data-echo-side');
      if (!m88.snapshot || !stableEventIdentity(echoIndex, graph) || !m88EventVisible(echoIndex, m88Range())) return;
      if (g.CLSky && g.CLSky.stop) g.CLSky.stop(); m88Stop(); m88.sourceRequest++;
      var eventBody = root.querySelector('#skyDeconBody'); m88.snapshot = { graph: graph, scope: m88.scope, query: browse.foreshadow.query, filter: browse.foreshadow.filter, page: browse.foreshadow.page, scrollTop: eventBody ? eventBody.scrollTop : 0, recordId: m88.recordId, side: echoSide, view: 'event' };
      state.mode = 'evidence'; state.focus = 'e:' + echoIndex; state.restore = { attr: 'data-event-index', value: String(echoIndex) }; render(); return;
    }
    if (m84.open && action !== 'structure-stage' && action !== 'structure-layer' && action !== 'structure-nav') cancelM84(true);
    if (action === 'position-explain') {
      var positionEventIndex = +b.getAttribute('data-event-index');
      if (m103.open && m103.eventIndex === positionEventIndex) { clearM103(); state.restore = { attr: 'data-event-index', value: String(positionEventIndex), action: 'position-explain' }; render(); }
      else openPositionExplanation(positionEventIndex);
      return;
    }
    if (action === 'position-boundary') { readPositionBoundary(b.getAttribute('data-position-side')); return; }
    if (action === 'position-return') { returnToPositionExplanation(); return; }
    if (action === 'shared-citation-open') { openSharedCitation(b.getAttribute('data-citation-ref-id')); return; }
    if (action === 'shared-citation-close') { closeSharedCitation(); return; }
    if (action === 'shared-citation-page') {
      var citationGroup = m106.open && citationIndex()[m106.refId], page = +b.getAttribute('data-page');
      if (citationGroup && Number.isInteger(page) && page >= 0 && page < Math.ceil(citationGroup.records.length / PAGE_SIZE)) { stopM106Tween(); m106.page = page; render(); }
      return;
    }
    if (action === 'shared-citation-record') { citationRecordClick(b.getAttribute('data-record-layer'), b.getAttribute('data-record-id')); return; }
    if (action === 'shared-citation-return') { returnFromCitationRecord(); return; }
    if (action === 'shared-citation-context') { readSharedCitationSource(b); return; }
    if (action === 'shared-citation-context-back') { returnFromCitationContext(); return; }
    if (action === 'structure-stage') { if (m84.open) cancelM84(true, true); else if (structureReady()) openM84(); return; }
    if (action === 'structure-layer') { selectM84Layer(b.getAttribute('data-structure-layer')); return; }
    if (action === 'structure-return') { returnStructureOverview(); return; }
    if (action === 'structure-plot') { cancelM84(true); if (g.CLSky && g.CLSky.setPlot) g.CLSky.setPlot(true); return; }
    if (action === 'structure-nav') { navigateStructure(b.getAttribute('data-structure-nav')); return; }
    if (LAYERS[layer]) {
      browse.mechanics.layer = layer; browse.mechanics.filter = 'all'; browse.mechanics.page = 0; browse.mechanics.selected = null;
      state.restore = { attr: 'data-layer', value: layer }; render(); return;
    }
    if (action === 'close') { close(true); return; }
    if (action === 'coverage-layer') {
      var selectedLayer = b.getAttribute('data-record-layer');
      if (selectedLayer === 'storylines') setMode('lines');
      else if (LAYERS[selectedLayer]) { browse.mechanics.layer = selectedLayer; browse.mechanics.query = ''; browse.mechanics.filter = 'all'; browse.mechanics.page = 0; browse.mechanics.selected = null; setMode('mechanics'); }
      return;
    }
    if (action === 'back-to-list') {
      var selector = state.mode === 'mechanics' ? '[data-action="select-mechanic"]' : state.mode === 'states' ? '[data-action="select-state"]' : '[data-action="select-event"]';
      var rows = root.querySelectorAll(selector), target = null;
      Array.prototype.some.call(rows, function (row) {
        var match = state.mode === 'mechanics' ? row.getAttribute('data-mechanic-key') === browse.mechanics.selected : state.mode === 'states' ? row.getAttribute('data-state-key') === browse.states.selected : 'e:' + row.getAttribute('data-event-index') === state.focus;
        if (match) target = row; return match;
      });
      target = target || rows[0]; if (target) { target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'center' }); } return;
    }
    if (action === 'play-record') {
      var recordLayer = b.getAttribute('data-record-layer'), recordId = b.getAttribute('data-record-id');
      if (!g.CLSky || !g.CLSky.playRecord) return;
      var result = g.CLSky.playRecord(recordLayer, recordId);
      if (result && result.ok) close(false);
      else { var message = root.querySelector('.sd-journey-message'); if (message) message.textContent = result && result.message || '当前记录的事件或来源不足，暂不能播放。'; }
      return;
    }
    if (action === 'read-review') { showRecord('reviewIssues', b.getAttribute('data-review-key')); return; }
    if (action === 'read-record') { showRecord(b.getAttribute('data-record-layer'), b.getAttribute('data-record-id')); return; }
    if (action === 'neighbor-compare') { comparePersonNeighbors(); return; }
    if (action === 'neighbor-open') {
      var picked = index.people.filter(function (p) { return personKey(p) === personDetail; })[0];
      if (picked) { var origin = personKey(picked); if (browse.neighbors.origin !== origin) { browse.neighbors.bId = ''; browse.neighbors.kind = 'all'; browse.neighbors.result = null; }
        browse.neighbors.origin = origin; browse.neighbors.tab = 'common'; if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); state.restore = { attr: 'data-action', value: 'neighbor-open' }; render(); }
      return;
    }
    if (action === 'neighbor-clear-b') { clearNeighborPerson(); return; }
    if (action === 'neighbor-tab') {
      browse.neighbors.tab = b.getAttribute('data-neighbor-tab') || 'common';
      browse.neighbors.demoCounts = { common: 0, onlyA: 0, onlyB: 0, fibers: 0 };
      if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
      state.restore = { attr: 'data-neighbor-tab', value: browse.neighbors.tab }; render(); return;
    }
    if (action === 'neighbor-basis') {
      if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
      browse.neighbors.returnScrollTop = root.querySelector('#skyDeconBody').scrollTop;
      browse.neighbors.returnAfterBasis = true;
      if (!showRecord('relations', b.getAttribute('data-record-id'))) {
        browse.neighbors.returnAfterBasis = false;
        var note = root.querySelector('.sd-neighbor-basis-note'); if (note) note.textContent = '依据入口不可用：图中没有唯一的关系记录ID。';
      }
      return;
    }
    if (action === 'neighbor-return') {
      browse.neighbors.returnAfterBasis = false; state.mode = 'people'; personDetail = browse.neighbors.origin;
      browse.neighbors.scrollTop = browse.neighbors.returnScrollTop; browse.neighbors.returnScrollTop = null;
      if (browse.neighbors.result && g.CLSky && g.CLSky.beginNeighborCompare) { var demo = g.CLSky.beginNeighborCompare(browse.neighbors.result); browse.neighbors.demoCounts = demo && demo.demoCounts || null; }
      state.restore = { attr: 'data-neighbor-person', value: 'b' }; render(); return;
    }
    if (action === 'page-prev' || action === 'page-next') {
      var section = b.getAttribute('data-page-mode');
      if (browse[section]) { browse[section].page += action === 'page-prev' ? -1 : 1; state.restore = { attr: 'data-action', value: action, pageMode: section }; render(); }
      return;
    }
    if (action === 'clear-person') { browse.evidence.person = ''; browse.evidence.page = 0; render(); return; }
    if (action === 'clear-state-scope') { browse.states.eventIndex = null; browse.states.characterId = null; browse.states.page = 0; render(); return; }
    if (action === 'person-events') {
      browse.evidence.person = b.getAttribute('data-person-events') || ''; browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.page = 0;
      state.mode = 'evidence'; state.focus = null; render(); return;
    }
    if (action === 'causal-fork-open') { openCausalFork(+b.getAttribute('data-event-index')); return; }
    if (action === 'causal-fork-stop') { stopCausalForkTween(); setForkButtonsPlaying(false); return; }
    if (action === 'causal-fork-replay') { animateCausalFork(); return; }
    if (action === 'causal-fork-return') { returnCausalFork(); return; }
    if (action === 'causal-fork-event') { var linkedEventIndex = +b.getAttribute('data-event-index'); causalFork.returnTo = causalForkSnapshot('causal-fork-event', String(linkedEventIndex)); stopCausalForkTween(); selectEvent(linkedEventIndex); return; }
    if (action === 'causal-fork-record') { var recordId = b.getAttribute('data-record-id'), causalSnapshot = causalForkSnapshot('causal-fork-record', recordId); causalFork.returnTo = causalSnapshot; stopCausalForkTween(); if (!showRecord(b.getAttribute('data-record-layer'), recordId)) causalFork.returnTo = null; return; }
    if (action === 'select-event') { selectEvent(+b.getAttribute('data-event-index')); return; }
    if (action === 'select-state') {
      browse.states.selected = b.getAttribute('data-state-key'); browse.stateQuotes.page = 0; browse.stateAttributes.page = 0;
      state.restore = { attr: 'data-state-key', value: browse.states.selected }; render(); revealDetail('.sd-state-detail'); return;
    }
    if (action === 'select-mechanic') {
      browse.mechanics.selected = b.getAttribute('data-mechanic-key');
      browse.mechanicQuotes.page = 0; browse.references.page = 0; browse.attributes.page = 0;
      state.restore = { attr: 'data-mechanic-key', value: browse.mechanics.selected }; render(); revealDetail('.sd-mechanics-card'); return;
    }
    if (mode) { setMode(mode); return; }
    var detailPerson = b.getAttribute('data-person-detail');
    if (detailPerson) { if (browse.neighbors.origin !== detailPerson && g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); personDetail = detailPerson; browse.arc.page = 0; state.restore = { attr: 'data-person-detail', value: detailPerson }; render(); return; }
    var line = b.getAttribute('data-line-id'), event = b.getAttribute('data-event-index'), person = b.getAttribute('data-person');
    if (line) { focusLine(line); return; }
    if (event != null && event !== '' && /^\d+$/.test(event)) { focusEvent(+event); return; }
    if (person) { focusPerson(person); }
  }

  function navigateStructure(which) {
    if (!m84.returning) {
      var body = doc.getElementById('skyDeconBody');
      m84.returning = true; m84.returnOpen = m84.open; m84.returnLayer = m84.selected;
      m84.returnScroll = m84.open && m84.openScroll != null ? m84.openScroll : body ? body.scrollTop : 0;
    }
    cancelM84(true);
    if (which === 'people') { browse.people.query = ''; browse.people.filter = 'all'; setMode('people'); }
    else if (which === 'groups') { browse.people.query = ''; browse.people.filter = 'all'; setMode('people'); setText('skyDeconMeta', '群组/阵营记录通过人物条目的阵营字段浏览；此入口不合并人物身份。'); }
    else if (which === 'relations') { browse.mechanics.layer = 'relations'; browse.mechanics.query = ''; browse.mechanics.filter = 'all'; browse.mechanics.page = 0; browse.mechanics.selected = null; setMode('mechanics'); }
    else if (which === 'events') { browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = ''; browse.evidence.page = 0; setMode('evidence'); }
    else if (which === 'chapters') { browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = ''; browse.evidence.page = 0; setMode('evidence'); }
    else if (which === 'units') { browse.mechanics.layer = 'narrativeUnits'; browse.mechanics.query = ''; browse.mechanics.filter = 'all'; browse.mechanics.page = 0; browse.mechanics.selected = null; setMode('mechanics'); }
    else if (which === 'lines') setMode('lines');
    else if (which === 'clues') setMode('foreshadow');
  }
  function returnStructureOverview() {
    if (!m84.returning) { setMode('overview'); return; }
    var reopen = !!(m84.returnOpen && structureReady()), scroll = m84.returnScroll;
    if (m84.returnLayer && ['characters', 'groups', 'relations', 'events'].indexOf(m84.returnLayer) >= 0) m84.selected = m84.returnLayer;
    m84.returning = false; m84.returnOpen = false; m84.returnScroll = null; m84.returnLayer = null;
    state.mode = 'overview'; state.focus = null;
    state.restore = { attr: 'data-structure-layer', value: m84.selected };
    render();
    var body = doc.getElementById('skyDeconBody'); if (body && scroll != null) body.scrollTop = scroll;
    if (reopen) openM84();
  }
  function onInput(e) {
    var el = e.target, mode = el.getAttribute && el.getAttribute('data-search');
    if (!browse[mode]) return;
    if (mode === 'causal' && causalFork.source != null) { stopCausalForkTween(); stopCausalForkLayout(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; }
    browse[mode].query = el.value; browse[mode].page = 0;
    if (searchTimer != null) g.clearTimeout(searchTimer);
    searchTimer = g.setTimeout(function () {
      searchTimer = null;
      if (state.mode !== mode) return;
      state.restore = { attr: 'data-search', value: mode, start: el.selectionStart, end: el.selectionEnd }; render();
    }, 140);
  }
  function onChange(e) {
    var el = e.target, mode = el.getAttribute && el.getAttribute('data-filter'), order = el.getAttribute && el.getAttribute('data-order');
    var kind = el.getAttribute && el.getAttribute('data-event-kind'), stateKind = el.getAttribute && el.getAttribute('data-state-kind'), page = el.getAttribute && el.getAttribute('data-page-number');
    if (browse[mode]) { if (mode === 'causal' && causalFork.source != null) { stopCausalForkTween(); stopCausalForkLayout(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; } browse[mode].filter = el.value; browse[mode].page = 0; state.restore = { attr: 'data-filter', value: mode }; }
    else if (order === 'evidence') { browse.evidence.order = el.value; browse.evidence.page = 0; state.restore = { attr: 'data-order', value: order }; }
    else if (kind === 'evidence') { browse.evidence.kind = el.value; browse.evidence.page = 0; state.restore = { attr: 'data-event-kind', value: kind }; }
    else if (stateKind === 'states') { browse.states.kind = el.value; browse.states.page = 0; state.restore = { attr: 'data-state-kind', value: stateKind }; }
    else if (el.getAttribute('data-neighbor-person') === 'b') { browse.neighbors.scrollTop = root.querySelector('#skyDeconBody').scrollTop; state.restore = { attr: 'data-neighbor-person', value: 'b' }; browse.neighbors.bId = el.value; browse.neighbors.result = null; browse.neighbors.tab = 'common'; if (el.value) comparePersonNeighbors(); else { if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); render(); } return; }
    else if (el.getAttribute('data-neighbor-kind') === 'filter') { browse.neighbors.scrollTop = root.querySelector('#skyDeconBody').scrollTop; state.restore = { attr: 'data-neighbor-kind', value: 'filter' }; browse.neighbors.kind = el.value; comparePersonNeighbors(); return; }
    else if (browse[page]) { browse[page].page = Math.max(0, num(el.value, 1) - 1); state.restore = { attr: 'data-page-number', value: page }; }
    else return;
    render();
  }

  function focusLine(id) {
    state.focus = id; state.restore = { attr: 'data-line-id', value: String(id) }; render();
    if (!g.CLSky) return;
    whenDiscReady(function () {
      g.CLSky.setPlot(true);
      g.setTimeout(function () { if (g.CLSky && g.CLSky.plot && g.CLSky.plot()) g.CLSky.focusLine(String(id)); }, 0);
    });
  }
  function focusEvent(i) {
    var c = index && index.eventChapter ? index.eventChapter[i] : null;
    browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = '';
    var ordered = evidenceItems(), position = ordered.map(function (x) { return x.i; }).indexOf(i);
    browse.evidence.page = Math.floor(Math.max(0, position) / PAGE_SIZE); browse.quotes.page = 0;
    state.focus = 'e:' + i; state.mode = 'evidence'; state.restore = { attr: 'data-event-index', value: String(i) }; render();
    if (!g.CLSky) return;
    whenDiscReady(function () {
      g.CLSky.setPlot(true);
      if (g.CLSky.seekEventAt) g.CLSky.seekEventAt(i);
      else if (c != null) g.CLSky.seek(c);
    });
  }
  function selectEvent(i) {
    if (!graph.events[i]) return;
    if (m106.open) clearM106();
    if ((m103.open && i !== m103.eventIndex) || (m103.returnSnapshot && i !== m103.returnSnapshot.boundaryIndex)) clearM103();
    if (state.mode !== 'evidence') {
      state.mode = 'evidence'; browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = '';
      browse.evidence.page = Math.floor(Math.max(0, evidenceItems().map(function (x) { return x.i; }).indexOf(i)) / PAGE_SIZE);
    }
    browse.quotes.page = 0;
    state.focus = 'e:' + i; state.restore = { attr: 'data-event-index', value: String(i), action: 'select-event' }; render(); revealDetail('.sd-evidence-detail');
  }
  function revealDetail(selector) {
    var detail = root && root.querySelector(selector);
    if (!detail) return;
    var back = doc.createElement('button'); back.type = 'button'; back.className = 'sd-detail-action'; back.setAttribute('data-action', 'back-to-list'); back.textContent = '← 返回记录列表'; detail.insertBefore(back, detail.firstChild);
    detail.setAttribute('tabindex', '-1'); detail.focus({ preventScroll: true }); detail.scrollIntoView({ block: 'start' });
  }
  function focusPerson(name) { close(false); if (g.CLSky && g.CLSky.openCompass) g.CLSky.openCompass(name); }

  function whenDiscReady(run, tries) {
    tries = tries == null ? 120 : tries;
    if (g.CLSky && g.CLSky.disc && g.CLSky.disc()) { run(); return; }
    if (tries > 0) g.setTimeout(function () { whenDiscReady(run, tries - 1); }, 50);
  }

  function setText(id, value) { var el = doc.getElementById(id); if (el) el.textContent = value; }
  function stat(label, value, hint) { return '<div class="sd-stat"><b>' + esc(value) + '</b><span>' + esc(label) + '</span>' + (hint ? '<small>' + esc(hint) + '</small>' : '') + '</div>'; }
  function lineRow(line, total, main) {
    var count = Math.max(1, total), left = Math.max(0, num(line.c0)) / count * 100;
    var width = Math.min(100 - left, Math.max(0, num(line.c1) - num(line.c0) + 1) / count * 100);
    var sources = line.sourceId == null ? [] : arr(graph.storylines).filter(function (source) { return source && str(source.id != null ? source.id : source.entityId) === str(line.sourceId); });
    var source = sources.length === 1 ? sources[0] : null;
    var title = source && typeof source.name === 'string' && source.name.trim() || line.fullLabel || line.label || line.keyEvent || '未命名剧情线', basis = lineBasis(line), cls = main ? ' is-main' : ' is-branch';
    var topology = line.anchored || line.parentBasis === 'layout' ? '仅布局挂接，剧情父线待核' : '';
    var span = model && model.chapters && g.CLSkyModel && g.CLSkyModel.chapterSpan ? g.CLSkyModel.chapterSpan(model, num(line.c0), num(line.c1)) : '章节范围未提供';
    var kind = line.autoSegment ? '自动分段' : main ? '主线' : line.kind === 'twig' ? '细支线' : '支线';
    var objectiveText = source && typeof source.goal === 'string' ? source.goal.trim() : line.objectiveText;
    var objective = line.autoSegment ? '按已有事件自动分段，非作者结构' : line.objective === 'declared' && objectiveText ? '目标声明：' + objectiveText : '未提供明确目标，不能据此判断任务完整性';
    var drill = (line.objective !== 'declared' && line.taskGoalCount > 0)
      ? '（该线剧情点上另有 ' + line.taskGoalCount + ' 个任务声明了目标）' : '';
    var detail = kind + ' · ' + num(line.n) + ' 个事件 · ' + (line.resolved ? '收束声明' : line.suspended ? '悬置声明' : '结局未定');
    var spoken = title + ' · ' + span + ' · ' + detail + ' · ' + basis + ' · ' + objective + (topology ? ' · ' + topology : '') + '，点击在星盘定位';
    var lp = lineProvenanceBadge(line);
    var spoken2 = spoken + ' · ' + lp.label + '（' + lp.hint + '）';
    return '<button type="button" class="sd-line' + cls + ' ' + basisClass(basis) + ' line-' + esc(lp.tone) + (line.autoSegment ? ' is-auto' : '') + (state.focus === line.id ? ' is-focus' : '') + '" data-line-id="' + esc(line.id) + '" data-line-source="' + esc(lp.code) + '" title="' + esc(spoken2) + '" aria-label="' + esc(spoken2) + '"><span class="sd-line-name">' + esc(title) + '</span><span class="sd-line-meta">' + esc(detail) + '</span><span class="sd-line-track" aria-hidden="true"><i data-sd-l="' + left.toFixed(3) + '" data-sd-w="' + width.toFixed(3) + '"></i></span><span class="sd-line-range">' + esc(span) + '</span><span class="sd-line-objective">' + esc(objective + drill) + '</span><span class="sd-line-basis">' + esc(basis + (topology ? ' · ' + topology : '')) + '</span><span class="sd-line-source" title="' + esc(lp.hint) + '">' + esc(lp.text) + '</span></button>';
  }
  function eventRow(i, selected) {
    var e = graph.events[i] || {}, ch = chapterFor(i), basis = eventBasis(e), names = arr(e.characters).slice(0, 3).join('、'), pos = positionBadge(e);
    var label = eventTitle(e) + '，' + basis + '，' + pos.label + (pos.hint ? '（' + pos.hint + '）' : '') + '，' + (ch ? ch.no + ' ' + (model.axis && model.axis.unit || '回') : '章节未提供') + '，点击阅读完整事件与证据';
    var cl = claimBadge(e);
    var label = eventTitle(e) + '，' + basis + '，' + cl.label + '，' + pos.label + (pos.hint ? '（' + pos.hint + '）' : '') + '，' + (ch ? ch.no + ' ' + (model.axis && model.axis.unit || '回') : '章节未提供') + '，点击阅读完整事件与证据';
    return '<button type="button" class="sd-event ' + basisClass(basis) + ' pos-' + esc(pos.tone) + ' claim-' + esc(cl.tone) + (selected ? ' is-focus' : '') + '" data-action="select-event" data-event-index="' + i + '" data-position="' + esc(pos.code) + '" data-claim="' + esc(cl.code) + '" aria-label="' + esc(label) + '"' + (selected ? ' aria-current="true"' : '') + '><span class="sd-event-mark"></span><span class="sd-event-copy"><b>' + esc(eventTitle(e)) + '</b><small>' + esc((ch ? ch.no + ' ' + (model.axis && model.axis.unit || '回') : '章节未提供') + ' · ' + (e.kind || '剧情点') + (names ? ' · ' + names : '')) + '</small></span><span class="sd-event-flags"><em>' + esc(basis) + '</em><em class="sd-event-pos" title="' + esc(pos.hint) + '">' + esc(pos.text) + '</em><em class="sd-event-claim" title="' + esc(cl.label) + '">' + esc(cl.text) + '</em></span></button>';
  }

  function matches(text, query) {
    return str(query).trim().toLocaleLowerCase().split(/\s+/).every(function (term) { return !term || text.indexOf(term) >= 0; });
  }
  function pageWindow(items, cfg) {
    var pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
    cfg.page = Math.max(0, Math.min(pages - 1, Math.floor(num(cfg.page))));
    return { items: items.slice(cfg.page * PAGE_SIZE, (cfg.page + 1) * PAGE_SIZE), total: items.length, pages: pages, page: cfg.page };
  }
  function pager(mode, view) {
    var first = view.total ? view.page * PAGE_SIZE + 1 : 0, last = Math.min(view.total, (view.page + 1) * PAGE_SIZE);
    var labels = { people: '人物', arc: '角色弧', quotes: '引文', evidence: '事件', mechanics: '情节记录', mechanicQuotes: '情节引文', references: '相关事件', attributes: '人物属性', coverage: '审阅声明', causal: '因果声明', payoffs: '伏笔声明', unresolved: '未解析引用', causalRoots: '根节点', causalLeaves: '叶节点', foreshadow: '伏笔声明', states: '人物状态与视野', stateQuotes: '状态依据', stateAttributes: '状态属性' };
    return '<nav class="sd-pagination" aria-label="' + (labels[mode] || '记录') + '分页">' +
      '<span class="sd-page-count" role="status">' + first + '–' + last + ' / ' + view.total + ' 条</span>' +
      '<button type="button" class="sd-detail-action" data-action="page-prev" data-page-mode="' + mode + '"' + (view.page === 0 ? ' disabled' : '') + '>上一页</button>' +
      '<label class="sd-page-jump">第 <input type="number" min="1" max="' + view.pages + '" value="' + (view.page + 1) + '" data-page-number="' + mode + '" aria-label="页码，共' + view.pages + '页"> / ' + view.pages + ' 页</label>' +
      '<button type="button" class="sd-detail-action" data-action="page-next" data-page-mode="' + mode + '"' + (view.page + 1 >= view.pages ? ' disabled' : '') + '>下一页</button></nav>';
  }
  function options(items, selected) {
    return items.map(function (item) { var value = typeof item === 'string' ? item : item.value, label = typeof item === 'string' ? item : item.label;
      return '<option value="' + esc(value) + '"' + (selected === value ? ' selected' : '') + '>' + esc(label) + '</option>'; }).join('');
  }
  function searchControl(mode, placeholder) {
    return '<label class="sd-search"><span class="sd-control-label">搜索</span><input type="search" data-search="' + mode + '" value="' + esc(browse[mode].query) + '" placeholder="' + esc(placeholder) + '" aria-label="' + esc(placeholder) + '"></label>';
  }
  function evidenceItems() {
    var cfg = browse.evidence, items = index.events.filter(function (x) {
      return matches(x.search, cfg.query) && (cfg.filter === 'all' || x.status.code === cfg.filter) &&
        (cfg.kind === 'all' || x.e.kind === cfg.kind) && (!cfg.person || arr(x.e.characters).indexOf(cfg.person) >= 0);
    });
    return cfg.order === 'key' ? items.sort(function (a, b) { return b.score - a.score || a.i - b.i; }) : items;
  }
  var CITATION_LAYERS = ['events', 'tasks', 'relations', 'characterStates', 'causeEdges', 'clues'];
  var CITATION_LAYER_LABELS = { events: '事件', tasks: '任务', relations: '关系', characterStates: '状态', causeEdges: '因果', clues: '伏笔' };
  function citationIdentity(entity) {
    if (!entity) return { id: null, valid: false };
    var id = entity.id == null || entity.id === '' ? null : str(entity.id);
    var entityId = entity.entityId == null || entity.entityId === '' ? null : str(entity.entityId);
    if (id && entityId && id !== entityId) return { id: null, valid: false };
    return { id: id || entityId, valid: !!(id || entityId) };
  }
  function citationLocator(ref) {
    if (!ref || typeof ref.sourceId !== 'string' || !ref.sourceId.trim() ||
        typeof ref.textHash !== 'string' || !ref.textHash.trim() || ref.offsetUnit !== 'codepoint' ||
        !Number.isInteger(ref.start) || !Number.isInteger(ref.end) || ref.start < 0 || ref.end <= ref.start ||
        typeof ref.quote !== 'string' || !ref.quote || Array.from(ref.quote).length !== ref.end - ref.start) return null;
    var source = g.CLAtlasSource;
    return source && source.sourceRefId ? source.sourceRefId(ref) : null;
  }
  function citationRefs(entity) {
    var source = g.CLAtlasSource, refs = source && source.sourceRefs ? source.sourceRefs(entity) : [];
    function add(owner) { if (owner && source && source.sourceRefs) refs = refs.concat(source.sourceRefs(owner)); }
    function addMany(values) {
      if (Array.isArray(values)) values.forEach(add);
      else if (values && typeof values === 'object') Object.keys(values).forEach(function (key) { add(values[key]); });
    }
    addMany(entity && entity.evidence);
    addMany(entity && entity.fieldEvidence);
    arr(entity && entity.attributes).forEach(add);
    var aspects = entity && entity.aspects;
    if (aspects && typeof aspects === 'object') Object.keys(aspects).forEach(function (key) { add(aspects[key]); });
    return refs;
  }
  function citationIndex() {
    if (m106.indexGraph === graph && m106.byRef) return m106.byRef;
    var byRef = Object.create(null);
    CITATION_LAYERS.forEach(function (layer) {
      var rows = arr(graph && graph[layer]).filter(function (item) { return item && typeof item === 'object'; });
      var counts = Object.create(null);
      rows.forEach(function (item) {
        [item.id, item.entityId].forEach(function (value, i, all) {
          if (value == null || value === '' || i && String(value) === String(all[0])) return;
          var key = str(value); counts[key] = (counts[key] || 0) + 1;
        });
      });
      rows.forEach(function (item) {
        var ident = citationIdentity(item), clickable = ident.valid && counts[ident.id] === 1;
        citationRefs(item).forEach(function (ref) {
          var refId = citationLocator(ref); if (!refId) return;
          var group = byRef[refId] || (byRef[refId] = { id: refId, ref: ref, records: [], recordKeys: Object.create(null), unknownLayers: Object.create(null) });
          if (!clickable) { group.unknownLayers[layer] = true; return; }
          var recordKey = layer + '\u0000' + ident.id;
          if (!group.recordKeys[recordKey]) {
            group.recordKeys[recordKey] = true;
            group.records.push({ layer: layer, label: CITATION_LAYER_LABELS[layer] || layer, id: ident.id,
              entity: item, title: citationRecordTitle(layer, item), status: citationSemanticState(layer, item) });
          }
        });
      });
    });
    m106.indexGraph = graph; m106.byRef = byRef;
    return byRef;
  }
  function citationRecordTitle(layer, entity) {
    if (layer === 'events') return eventTitle(entity);
    if (layer === 'relations') return mechanicTitle(layer, entity);
    if (layer === 'characterStates') {
      var changed = (entity.before != null && entity.before !== '') || (entity.after != null && entity.after !== '');
      return (entity.character || '人物待核') + ' · ' + (changed ? '变化声明' : '状态声明');
    }
    return mechanicTitle(layer, entity);
  }
  function citationSourceLabel(ref) {
    var sources = arr(graph && graph.meta && graph.meta.sources).filter(function (row) { return row && str(row.id || row.sourceId) === str(ref.sourceId); });
    if (sources.length !== 1) return '原文来源未能唯一标名';
    return sources[0].name || sources[0].path || '原文';
  }
  function citationSemanticState(layer, entity) {
    var semantic = layer === 'characterStates' ? stateBasisLabel(entity) : semanticLabel(entity);
    if (layer === 'events') semantic += ' · 类型：' + eventClaim(entity).label;
    var citation = eventStatus(entity).label || '引句定位未标明';
    return { semantic: semantic || '语义状态未标明', citation: citation };
  }
  function selectedCitationRecord(refId) {
    if (!m106.selectedRecord) return false;
    var group = citationIndex()[refId]; if (!group) return false;
    var row = group.records.filter(function (item) { return item.layer === m106.selectedRecord.layer && item.id === m106.selectedRecord.id; })[0];
    return !!(row && citationRefs(row.entity).some(function (ref) { return citationLocator(ref) === refId; }));
  }
  function stopM106Tween() {
    if (m106.tween && g.CLSkyMotion) g.CLSkyMotion.cancelAll('m106');
    m106.tween = null; m106.request++;
  }
  function clearM106(clearReturn) {
    stopM106Tween(); m106.open = false; m106.view = 'group'; m106.refId = null; m106.context = null;
    m106.recordSnapshot = null; m106.sourceSnapshot = null; m106.sourceReturnView = null;
    m106.page = 0; m106.sourceRequest++;
    if (clearReturn !== false) { m106.returnSnapshot = null; m106.groupSnapshot = null; m106.selectedRecord = null; }
  }
  function m106Snapshot() {
    var body = doc.getElementById('skyDeconBody');
    return { graph: graph, mode: state.mode, focus: state.focus, restore: state.restore ? Object.assign({}, state.restore) : null,
      browse: JSON.parse(JSON.stringify(browse)), personDetail: personDetail, scrollTop: body ? body.scrollTop : 0,
      focusTarget: citationFocusTarget(doc.activeElement) };
  }
  function citationFocusTarget(el) {
    if (!el || !el.getAttribute) return null;
    var action = el.getAttribute('data-action');
    if (action === 'shared-citation-open') return { attr: 'data-action', value: action, citationRef: el.getAttribute('data-citation-ref-id') };
    if (action === 'shared-citation-record') return { attr: 'data-action', value: action, recordLayer: el.getAttribute('data-record-layer'), recordId: el.getAttribute('data-record-id') };
    if (action === 'shared-citation-context') return { attr: 'data-action', value: action };
    return null;
  }
  function openSharedCitation(refId) {
    var groups = citationIndex(), group = groups[refId];
    if (!group || !group.records.length && !Object.keys(group.unknownLayers).length) return false;
    if (m106.open && m106.view === 'group' && m106.refId === refId) return closeSharedCitation();
    stopM106Tween(); m106.sourceRequest++;
    if (!(m106.open && m106.view === 'group' && m106.returnSnapshot)) m106.returnSnapshot = m106Snapshot();
    m106.open = true; m106.view = 'group'; m106.refId = refId; m106.context = null; m106.selectedRecord = null; m106.page = 0;
    state.focus = m106.returnSnapshot && m106.returnSnapshot.focus || state.focus;
    render();
    var host = root && root.querySelector('[data-shared-citation]'), body = doc.getElementById('skyDeconBody');
    if (host && body) { var hr = host.getBoundingClientRect(), br = body.getBoundingClientRect(); body.scrollTop += hr.top - br.top - 8; }
    m106.groupSnapshot = m106Snapshot(); animateSharedCitation();
    return true;
  }
  function renderSharedCitation(refId) {
    var group = citationIndex()[refId]; if (!group) return '';
    var ref = group.ref, unknown = Object.keys(group.unknownLayers), totalPages = Math.max(1, Math.ceil(group.records.length / PAGE_SIZE));
    m106.page = Math.max(0, Math.min(totalPages - 1, m106.page));
    var start = m106.page * PAGE_SIZE, rows = group.records.slice(start, start + PAGE_SIZE);
    var cards = rows.map(function (row, i) {
      var animated = m106.page === 0 && i < 6, active = m106.view === 'record' && m106.selectedRecord && m106.selectedRecord.layer === row.layer && m106.selectedRecord.id === row.id;
      return '<button type="button" class="sd-citation-card' + (active ? ' is-selected' : '') + (animated ? ' is-animated' : ' is-static') + '"' + (animated ? ' data-citation-step="' + i + '"' : '') + ' data-action="shared-citation-record" data-record-layer="' + esc(row.layer) + '" data-record-id="' + esc(row.id) + '"><span class="sd-citation-line" aria-hidden="true"></span><small>' + esc(row.label) + '</small><b>' + esc(row.title) + '</b><span class="sd-citation-semantic">语义/声明 · ' + esc(row.status.semantic) + '</span><span class="sd-citation-anchor">引句定位 · ' + esc(row.status.citation) + '</span></button>';
    }).join('');
    var unknownHtml = unknown.length ? '<p class="sd-citation-unknown">另有身份不唯一或未提供稳定 ID 的记录（' + esc(unknown.map(function (layer) { return CITATION_LAYER_LABELS[layer] || layer; }).join('、')) + '），未计入可确认归属数，也不提供跳转。</p>' : '';
    var pagination = totalPages > 1 ? '<nav class="sd-citation-pages" aria-label="引用归属分页"><button type="button" data-action="shared-citation-page" data-page="' + Math.max(0, m106.page - 1) + '"' + (m106.page === 0 ? ' disabled' : '') + '>上一页</button><span>' + (m106.page + 1) + ' / ' + totalPages + ' · ' + group.records.length + ' 条</span><button type="button" data-action="shared-citation-page" data-page="' + Math.min(totalPages - 1, m106.page + 1) + '"' + (m106.page >= totalPages - 1 ? ' disabled' : '') + '>下一页</button></nav>' : '';
    var context = m106.view === 'source' && m106.refId === refId ? renderCitationContext(refId) : '';
    return '<section class="sd-shared-citation" data-shared-citation data-citation-ref-id="' + esc(refId) + '" aria-label="引用归属"><div class="sd-citation-head"><div><b>哪些记录引用这里</b><span>' + group.records.length + ' 条可唯一定位记录共用 1 处定位</span></div><button type="button" class="sd-detail-action" data-action="shared-citation-close">收起归属列表</button></div><div class="sd-citation-origin"><small>' + esc(citationSourceLabel(ref)) + '</small><p>' + esc(ref.quote) + '</p></div>' +
      '<div class="sd-citation-list" data-phase="settled">' + (cards || '<p class="sd-empty">未找到可唯一确认的记录归属。</p>') + '</div><p class="sd-citation-note">细线只表示这些记录引用同一处原文，不表示因果；每条记录的语义状态分别保留。</p>' + pagination + unknownHtml + (m106.view === 'source' ? '' : '<button type="button" class="sd-detail-action sd-citation-source" data-action="shared-citation-context">阅读这处原文</button>') + context + '</section>';
  }
  function animateSharedCitation() {
    var host = root && root.querySelector('[data-shared-citation]'); if (!host) return;
    stopM106Tween(); var req = ++m106.request;
    function paint(value) {
      if (req !== m106.request || !host.isConnected) return;
      host.style.setProperty('--sd-citation-progress', String(value));
      var settled = value >= 1; host.setAttribute('data-phase', settled ? 'settled' : 'opening');
      var list = host.querySelector('.sd-citation-list'); if (list) list.setAttribute('data-phase', settled ? 'settled' : 'opening');
      Array.prototype.forEach.call(host.querySelectorAll('.sd-citation-card.is-animated'), function (card, i) {
        var enter = Math.max(0, Math.min(1, (value - (0.25 + i * 0.055)) / 0.055));
        card.style.setProperty('--sd-citation-card-progress', String(enter));
        card.style.setProperty('--sd-citation-line-progress', String(Math.max(0, Math.min(1, (value - 0.58) / 0.42))));
      });
    }
    if ((g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) || !g.CLSkyMotion) { paint(1); return; }
    paint(0);
    m106.tween = g.CLSkyMotion.tween({ from: 0, to: 1, dur: .72, ease: function (v) { return v; }, tag: 'm106', onUpdate: paint,
      onDone: function () { if (req === m106.request) { paint(1); m106.tween = null; } } });
  }
  function citationRecordClick(layer, id) {
    var group = m106.open && citationIndex()[m106.refId];
    if (!group) return false;
    var row = group.records.filter(function (item) { return item.layer === layer && item.id === id; })[0];
    if (!row) return false;
    stopM106Tween(); m106.sourceRequest++;
    m106.groupSnapshot = m106Snapshot(); m106.view = 'record'; m106.selectedRecord = { layer: layer, id: id };
    if (layer === 'events') {
      var matches = [];
      graph.events.forEach(function (event, i) { var ident = citationIdentity(event); if (ident.valid && ident.id === id) matches.push(i); });
      if (matches.length !== 1) return false;
      var at = matches[0], all = index.events;
      browse.evidence.query = ''; browse.evidence.filter = 'all'; browse.evidence.kind = 'all'; browse.evidence.person = '';
      browse.evidence.page = Math.floor(Math.max(0, all.map(function (item) { return item.i; }).indexOf(at)) / PAGE_SIZE);
      browse.quotes.page = 0; state.mode = 'evidence'; state.focus = 'e:' + at; state.restore = { attr: 'data-event-index', value: String(at) };
      render(); revealDetail('.sd-evidence-detail'); m106.recordSnapshot = m106Snapshot(); return true;
    }
    if (!showRecord(layer, id, true)) { m106.view = 'group'; m106.selectedRecord = null; return false; }
    m106.recordSnapshot = m106Snapshot();
    return true;
  }
  function returnFromSharedCitation() {
    var snap = m106.groupSnapshot;
    if (!snap || snap.graph !== graph) { clearM106(); render(); return false; }
    var refId = m106.refId;
    stopM106Tween(); m106.sourceRequest++; m106.view = 'group'; m106.refId = refId; m106.context = null; m106.selectedRecord = null;
    m106.recordSnapshot = null; m106.sourceSnapshot = null; m106.sourceReturnView = null;
    state.mode = snap.mode; state.focus = snap.focus; state.restore = snap.focusTarget || snap.restore;
    Object.keys(snap.browse).forEach(function (key) { browse[key] = snap.browse[key]; });
    personDetail = snap.personDetail; render();
    var body = doc.getElementById('skyDeconBody'); if (body) body.scrollTop = snap.scrollTop;
    var panel = root && root.querySelector('[data-shared-citation]'); if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
    animateSharedCitation();
    return true;
  }
  function restoreCitationView(snap) {
    if (!snap || snap.graph !== graph) { clearM106(); render(); return false; }
    state.mode = snap.mode; state.focus = snap.focus; state.restore = snap.focusTarget || snap.restore;
    Object.keys(snap.browse).forEach(function (key) { browse[key] = snap.browse[key]; });
    personDetail = snap.personDetail; render();
    var body = doc.getElementById('skyDeconBody'); if (body) body.scrollTop = snap.scrollTop;
    return true;
  }
  function closeSharedCitation() {
    var snap = m106.returnSnapshot; clearM106(); return restoreCitationView(snap);
  }
  function returnFromCitationRecord() {
    if (!m106.open || !m106.groupSnapshot) return false;
    return returnFromSharedCitation();
  }
  function returnFromCitationContext() {
    if (!m106.open) return false;
    if (m106.sourceReturnView === 'group' && m106.sourceSnapshot) {
      var groupSnap = m106.sourceSnapshot;
      stopM106Tween(); m106.sourceRequest++; m106.view = 'group'; m106.context = null; m106.sourceReturnView = null; m106.sourceSnapshot = null;
      return restoreCitationView(groupSnap);
    }
    if (m106.sourceReturnView === 'record' && m106.recordSnapshot) {
      var recordSnap = m106.recordSnapshot;
      stopM106Tween(); m106.sourceRequest++; m106.view = 'record'; m106.context = null; m106.sourceReturnView = null; m106.sourceSnapshot = null;
      return restoreCitationView(recordSnap);
    }
    if (!m106.groupSnapshot) return false;
    return returnFromSharedCitation();
  }
  function m88Clue(rec) {
    var id = rec && (rec.ownerId || rec.recordId || rec.id), rows = arr(index && index.layers && index.layers.clues).filter(function (row) { return id != null && str(row.recordId) === str(id) && (!rec.ownerType || !row.ownerType || row.ownerType === rec.ownerType); });
    return rows.length === 1 ? rows[0].raw : null;
  }
  function m88Ref(rec, side) {
    var clue = m88Clue(rec), quote = clue && clue[side + 'Quote'], refs = clue && g.CLAtlasSource && g.CLAtlasSource.sourceRefs ? g.CLAtlasSource.sourceRefs(clue) : arr(clue && clue.sourceRefs);
    refs = arr(refs).filter(function (r) { return r && quote && r.quote === quote; });
    if (!quote) return null;
    var quoteLength = Array.from(quote).length;
    var located = refs.filter(function (r) { return r.offsetUnit === 'codepoint' && Number.isInteger(r.start) && Number.isInteger(r.end) && r.start >= 0 && r.end > r.start && r.end - r.start === quoteLength && r.sourceId && r.textHash; });
    var unique = Object.create(null); refs.forEach(function (r) { unique[[r.sourceId,r.textHash,r.offsetUnit,r.start,r.end,r.quote].join('|')] = r; });
    var keys = Object.keys(unique), ref = keys.length === 1 && located.length === 1 ? unique[keys[0]] : null;
    var location = ref && g.CLAtlasSource && g.CLAtlasSource.evidenceStatus ? g.CLAtlasSource.evidenceStatus({ quote: quote, sourceRefs: [ref] }) : null;
    return { quote: quote, ref: ref, clue: clue, refs: refs, label: !ref ? refs.length ? '定位不唯一或不完整' : '定位待核' : location && location.code === 'verified' ? '定位已核验' : location ? '定位未核验' : '定位状态不可用' };
  }
  function m88Read(side) {
    if (g.CLSky && g.CLSky.stop) g.CLSky.stop();
    var recs = arr(model && model.narrative && model.narrative.foreshadowLifecycles).filter(function (x) { return str(x.ownerId || x.recordId || x.id) === str(m88.recordId) && (!x.ownerType || x.ownerType === 'clue'); });
    var rec = recs.length === 1 ? recs[0] : null, vis = rec && m88Visibility(rec, m88Range());
    if (!rec || !vis || (side === 'payoff' && !vis.payoff) || (side === 'seed' && !vis.seed)) return false;
    var found = m88Ref(rec, side); if (!found || !found.ref) { m88.sourceStatus = 'unavailable:' + (found ? found.label : '引句尚未提供。'); state.restore = { attr: 'data-action', value: 'foreshadow-echo-close' }; render(); return false; }
    var sourceBody = root.querySelector('#skyDeconBody');
    m88.snapshot = { graph: graph, scope: m88.scope, query: browse.foreshadow.query, filter: browse.foreshadow.filter, page: browse.foreshadow.page, scrollTop: sourceBody ? sourceBody.scrollTop : 0, recordId: m88.recordId, side: side, view: 'source' };
    m88.sourceRequest++; var request = m88.sourceRequest, targetGraph = graph, targetId = m88.recordId, targetScope = m88ScopeKey();
    m88.source = null; m88.sourceStatus = 'loading'; state.restore = { attr: 'data-action', value: 'foreshadow-echo-source-back' }; render();
    if (!found) return false;
    var app = g.CLApp, ref = found.ref;
    Promise.resolve().then(function () { return app && app.sourceDocuments ? app.sourceDocuments() : []; }).then(function (docs) {
      if (request !== m88.sourceRequest || graph !== targetGraph || m88.recordId !== targetId) return;
      if (targetScope !== m88ScopeKey() || !m88Visibility(rec, m88Range())[side]) { m88.source = null; m88.sourceStatus = 'unavailable:阅读范围已变化，原文请求已取消。'; render(); return; }
      var declarations = arr(graph.meta && graph.meta.sources).filter(function (s) { return str(s.id || s.sourceId) === str(ref.sourceId); });
      if (declarations.length !== 1) throw new Error(declarations.length ? '同一来源ID对应多个版本声明。' : '图谱未声明该原文来源。');
      if (declarations[0].textHash !== ref.textHash) throw new Error('引用文本版本与来源声明不一致。');
      var decl = declarations[0], rows = Array.isArray(docs) ? docs : arr(docs && docs.docs), candidates = rows.filter(function (d) { var raw = d && (d.sourceText != null ? d.sourceText : d.text), names = [d && d.sourceId,d && d.id,d && d.path,d && d.name].filter(Boolean).map(String); return raw != null && (names.indexOf(str(ref.sourceId)) >= 0 || names.indexOf(str(decl.path || '')) >= 0) && (d.textHash || d.hash || decl.textHash) === ref.textHash; });
      if (candidates.length !== 1) throw new Error(candidates.length ? '同一来源与版本材料不唯一。' : '未找到同一来源与文本版本的原文。');
      var chars = Array.from(String(candidates[0].sourceText != null ? candidates[0].sourceText : candidates[0].text)), quote = chars.slice(ref.start, ref.end).join(''); if (quote !== ref.quote) throw new Error('codepoint 定位切出的引句不匹配。');
      if (request !== m88.sourceRequest || graph !== targetGraph || m88.recordId !== targetId || targetScope !== m88ScopeKey()) return;
      if (m88.snapshot) m88.snapshot.view = 'source';
      m88.source = { side: side, quote: quote, name: candidates[0].name || candidates[0].path || decl.name || '原文' }; m88.sourceStatus = 'ready';
      state.restore = { attr: 'data-action', value: 'foreshadow-echo-source-back' }; render();
    }).catch(function (e) { if (request === m88.sourceRequest && graph === targetGraph && m88.recordId === targetId) { m88.source = null; m88.sourceStatus = 'unavailable:' + (e && e.message || '读取原文失败。'); render(); } });
    return true;
  }
  function renderM88(rec, vis) {
    if (str(rec.ownerId || rec.recordId || rec.id) !== str(m88.recordId)) return '';
    var range = m88Range(), scope = '<div class="sd-echo-scope"><span role="status">' + esc(range.label) + '</span>' + (m88CanFollow() ? '<button type="button" class="sd-detail-action" data-action="foreshadow-echo-scope">' + (m88.scope === 'published' ? '跟随阅读位置' : '查看已发布记录') + '</button>' : '') + '</div>';
    var seed = graph.events[rec.seedIndex], payoff = vis.payoff && graph.events[rec.payoffIndex], seedCh = m88Chapter(rec.seedIndex), payoffCh = vis.payoff ? m88Chapter(rec.payoffIndex) : null;
    var chapterLine = vis.payoff ? '<p class="sd-echo-chapter-guide sd-echo-guide">章节位置未能唯一确认；两处并列呈现。</p>' : '<p class="sd-echo-chapter-guide sd-echo-guide">' + (rec.stage === 'resolved' ? '兑现尚未公开；当前仅标示可公开章节。' : '兑现端章节未提供或待核；当前仅标示可公开章节。') + '</p>';
    if (seedCh && payoffCh && Number.isInteger(seedCh.index) && Number.isInteger(payoffCh.index)) {
      var chapterCount = Math.max(1, arr(model.chapters).length), sx = chapterCount > 1 ? 5 + 90 * seedCh.index / (chapterCount - 1) : 50, px = chapterCount > 1 ? 5 + 90 * payoffCh.index / (chapterCount - 1) : 50;
      var sameChapter = seedCh.index === payoffCh.index, guidePath = sameChapter ? 'M ' + sx + ' 4 V 20' : 'M ' + sx + ' 12 H ' + px;
      chapterLine = '<p class="sd-echo-guide">' + (sameChapter ? '同章：' + esc(seedCh.name) + ' · 同一线索记录，虚线不表示时长。' : '章序提示：' + esc(seedCh.name) + ' 至 ' + esc(payoffCh.name) + ' · 虚线仅示顺序，不表示时长。') + '</p><svg class="sd-echo-axis sd-echo-guide" viewBox="0 0 100 24" role="img" aria-label="按已记录章节次序排列的同一线索记录埋设与兑现提示，无时长含义"><defs><mask class="sd-echo-guide-mask" id="m88-echo-guide-mask" mask-type="alpha" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="24"><path class="sd-echo-guide-reveal" pathLength="100" d="' + guidePath + '"></path></mask></defs><path class="sd-echo-guide-line" d="' + guidePath + '" mask="url(#m88-echo-guide-mask)"></path><circle class="sd-echo-seed-dot" cx="' + sx + '" cy="' + (sameChapter ? '4' : '12') + '" r="3"></circle><circle class="sd-echo-payoff-dot" cx="' + px + '" cy="' + (sameChapter ? '20' : '12') + '" r="3"></circle></svg><details class="sd-echo-axis-source"><summary>章节来源</summary><span>章节标签取自当前图谱已记录章节；虚线仅示顺序。</span></details>';
    }
    var seedQ = m88Ref(rec, 'seed'), payoffQ = vis.payoff ? m88Ref(rec, 'payoff') : null;
    var semanticClue = m88Clue(rec), semantic = semanticClue && semanticClue.claimVerified === true && semanticClue.semanticStatus === 'reviewed' ? '语义已复核' : '配对待核';
    var cards = '<div class="sd-echo-cards"><section class="sd-echo-seed"><b>埋设：' + esc(seed && (seed.title || seed.summary) || '事件记录') + '</b><small> · 埋设引句 · ' + esc(seedQ ? seedQ.label : '引用尚未提供') + '</small>' + (seedQ ? '<blockquote>' + esc(seedQ.quote) + '</blockquote>' : '<p>当前声明未提供埋设引句。</p>') + '<button type="button" data-action="foreshadow-echo-read" data-echo-side="seed"' + (seedQ && seedQ.ref ? '' : ' disabled') + '>阅读这处原文</button>' + (seedQ && !seedQ.ref ? '<p class="sd-reference-unavailable">该引句没有唯一完整定位，暂不能打开原文。</p>' : '') + (seed && stableEventIdentity(rec.seedIndex, graph) ? '<button type="button" data-action="foreshadow-echo-event" data-echo-side="seed" data-event-index="' + rec.seedIndex + '">阅读埋设事件</button>' : '') + '</section>' + (vis.payoff ? '<section class="sd-echo-payoff"><b>兑现：' + esc(payoff && (payoff.title || payoff.summary) || '事件记录') + '</b><small> · 兑现引句 · ' + esc(payoffQ ? payoffQ.label : '引用尚未提供') + '</small>' + (payoffQ ? '<blockquote>' + esc(payoffQ.quote) + '</blockquote>' : '<p>当前声明未提供兑现引句。</p>') + '<button type="button" data-action="foreshadow-echo-read" data-echo-side="payoff"' + (payoffQ && payoffQ.ref ? '' : ' disabled') + '>阅读这处原文</button>' + (payoffQ && !payoffQ.ref ? '<p class="sd-reference-unavailable">该引句没有唯一完整定位，暂不能打开原文。</p>' : '') + (payoff && stableEventIdentity(rec.payoffIndex, graph) ? '<button type="button" data-action="foreshadow-echo-event" data-echo-side="payoff" data-event-index="' + rec.payoffIndex + '">阅读兑现事件</button>' : '') + '</section>' : '<section class="sd-echo-payoff"><b>兑现端</b><p>' + (rec.stage === 'resolved' ? '兑现尚未公开。' : '这条记录未提供兑现事件。') + '</p></section>') + '</div>';
    var status = m88.sourceStatus ? '<p role="status">' + esc(m88.sourceStatus.indexOf('unavailable:') === 0 ? m88.sourceStatus.slice(12) : m88.sourceStatus === 'loading' ? '正在核对原文来源与版本…' : '原文已按引句定位显示；未展开前后文。') + '</p>' : '';
    var sourceView = m88.snapshot && m88.snapshot.view === 'source' ? '<div class="sd-echo-source"><button type="button" data-action="foreshadow-echo-source-back">返回伏笔回响</button>' + (m88.sourceStatus === 'loading' ? '<p role="status">正在核对原文来源与版本…</p>' : m88.sourceStatus && m88.sourceStatus.indexOf('unavailable:') === 0 ? '<p class="sd-reference-unavailable" role="status">' + esc(m88.sourceStatus.slice(12)) + '</p>' : '') + (m88.source ? '<p><small>' + esc(m88.source.name) + ' · 仅显示该声明引句</small></p><blockquote>' + esc(m88.source.quote) + '</blockquote>' : '') + '</div>' : '';
    return '<section class="sd-foreshadow-echo" data-foreshadow-echo data-echo-entry-focus="true" tabindex="-1" data-phase="' + (m88.tween ? 'opening' : 'settled') + '"><div class="sd-section-head"><b>伏笔回响</b><button type="button" class="sd-detail-action" data-action="foreshadow-echo-stop"' + (m88.tween ? '' : ' disabled') + '>停止</button><button type="button" class="sd-detail-action" data-action="foreshadow-echo-replay">重播说明</button><button type="button" class="sd-detail-action" data-action="foreshadow-echo-close">收起</button></div>' + scope + '<p class="sd-echo-status">语义状态：' + semantic + ' · 引句定位状态见各卡。</p>' + chapterLine + (m88.snapshot && m88.snapshot.view === 'source' ? sourceView : cards + status) + '</section>';
  }
  function readSharedCitationSource(trigger) {
    var group = m106.open && citationIndex()[m106.refId]; if (!group) return false;
    stopM106Tween(); var request = ++m106.sourceRequest, targetGraph = graph, targetId = m106.refId;
    m106.sourceReturnView = m106.view;
    m106.sourceSnapshot = m106Snapshot();
    m106.sourceSnapshot.focusTarget = citationFocusTarget(trigger) || m106.sourceSnapshot.focusTarget;
    if (m106.view === 'record') m106.recordSnapshot = m106Snapshot();
    m106.view = 'source'; m106.context = { status: 'loading' }; render();
    var app = g.CLApp;
    if (!app || typeof app.sourceDocuments !== 'function') { m106.context = { status: 'unavailable', reason: '当前接口未提供受信任的原始材料。' }; render(); return false; }
    Promise.resolve().then(function () { return app.sourceDocuments(); }).then(function (documents) {
      if (!m106.open || m106.view !== 'source' || m106.sourceRequest !== request || graph !== targetGraph || m106.refId !== targetId) return;
      var ref = group.ref, declarations = arr(graph.meta && graph.meta.sources).filter(function (row) { return row && str(row.id || row.sourceId) === str(ref.sourceId); });
      if (declarations.length !== 1 || declarations[0].textHash !== ref.textHash) throw new Error('来源身份或文本版本未能唯一核对。');
      var rows = Array.isArray(documents) ? documents : arr(documents && documents.docs), candidates = [];
      rows.forEach(function (document) {
        var raw = document && (document.sourceText != null ? document.sourceText : document.text);
        if (raw == null) return;
        var names = [document.sourceId, document.id, document.path, document.name].filter(Boolean).map(String);
        var hash = document.textHash || document.hash || declarations[0].textHash;
        if (names.indexOf(str(ref.sourceId)) >= 0 || names.indexOf(str(declarations[0].path || '')) >= 0) {
          if (hash === ref.textHash) candidates.push({ document: document, raw: String(raw) });
        }
      });
      if (candidates.length !== 1) throw new Error(candidates.length ? '对应材料不唯一，未选择其中任何一份。' : '未找到同一来源与文本版本的材料。');
      var raw = candidates[0].raw, chars = Array.from(raw), quote = chars.slice(ref.start, ref.end).join('');
      if (quote !== ref.quote) throw new Error('可信 codepoint 区间切出的引句与定位声明不一致。');
      if (!m106.open || m106.view !== 'source' || m106.sourceRequest !== request || graph !== targetGraph || m106.refId !== targetId) return;
      m106.context = { status: 'ready', before: chars.slice(Math.max(0, ref.start - 300), ref.start).join(''),
        after: chars.slice(ref.end, Math.min(chars.length, ref.end + 300)).join(''), quote: quote, total: chars.length,
        source: candidates[0].document.name || candidates[0].document.path || declarations[0].name || '原文' };
      render();
    }).catch(function (error) {
      if (!m106.open || m106.view !== 'source' || m106.sourceRequest !== request || graph !== targetGraph || m106.refId !== targetId) return;
      m106.context = { status: 'unavailable', reason: error && error.message || '读取原始材料失败。' }; render();
    });
    return true;
  }
  function renderCitationContext(refId) {
    var context = m106.context, group = citationIndex()[refId]; if (!group) return '';
    var back = '<button type="button" class="sd-detail-action" data-action="shared-citation-context-back">' + (m106.sourceReturnView === 'record' ? '返回记录详情' : '返回引用归属') + '</button>';
    if (!context || context.status === 'loading') return '<div class="sd-citation-context">' + back + '<p role="status">正在读取同一来源与文本版本…</p></div>';
    if (context.status !== 'ready') return '<div class="sd-citation-context">' + back + '<p class="sd-citation-unknown">无法定位原文：' + esc(context.reason || '材料身份未确认。') + '</p></div>';
    return '<div class="sd-citation-context">' + back + '<p class="sd-citation-context-text">' + esc(context.before) + '<mark>' + esc(context.quote) + '</mark>' + esc(context.after) + '</p><small>' + esc(context.source) + '</small></div>';
  }
  function citationButtons(entity, quote) {
    var refs = citationRefs(entity), seen = Object.create(null), buttons = [], incomplete = false;
    refs.forEach(function (ref) {
      if (!ref || ref.quote !== quote) return;
      var refId = citationLocator(ref);
      if (!refId) { incomplete = true; return; }
      if (seen[refId]) return; seen[refId] = true;
      var group = citationIndex()[refId], count = group ? group.records.length : 0;
      var active = m106.open && m106.refId === refId, selected = active && selectedCitationRecord(refId), detail = '';
      if (selected && m106.view === 'record') detail = '<button type="button" class="sd-detail-action sd-citation-source" data-action="shared-citation-context">阅读这处原文</button>';
      else if (selected && m106.view === 'source' && m106.sourceReturnView === 'record') detail = renderCitationContext(refId);
      else if (active && m106.view !== 'record' && !(m106.view === 'source' && m106.sourceReturnView === 'record')) detail = renderSharedCitation(refId);
      buttons.push('<button type="button" class="sd-citation-trigger" data-action="shared-citation-open" data-citation-ref-id="' + esc(refId) + '">哪些记录引用这里' + (count ? ' · ' + count + ' 条' : '') + '</button>' + detail);
    });
    if (incomplete) buttons.push('<span class="sd-citation-unavailable">引句缺少完整定位，未确认是否与其他记录共用同一位置。</span>');
    return buttons.join('');
  }
  function quoteRow(entity, quote) {
    var source = g.CLAtlasSource, refs = source && source.sourceRefs ? source.sourceRefs(entity) : [];
    arr(entity && entity.evidence).forEach(function (item) { if (item && typeof item === 'object' && source && source.sourceRefs) refs = refs.concat(source.sourceRefs(item)); });
    var status = eventStatus({ quote: quote, sourceRefs: refs, quoteReview: entity && entity.quoteReview, verified: entity && entity.quote === quote ? entity.verified : undefined });
    return '<blockquote class="sd-quote-reference"><small class="sd-quote-status ' + basisClass(status.label) + '">' + esc(status.label) + '</small><p>' + esc(quote) + '</p>' + citationButtons(entity, quote) + '</blockquote>';
  }
  function mechanicsStatus(layer, entity) {
    if (layer === 'relations') return { code: eventStatus(entity).code, label: eventStatus(entity).label };
    if (layer === 'characterStates') {
      var changed = (entity.before != null && entity.before !== '') || (entity.after != null && entity.after !== '');
      return { code: changed ? 'state-transition' : 'state-claim', label: (changed ? '变化声明' : '状态声明') + ' · ' + stateBasisLabel(entity) };
    }
    if (layer === 'narrativeUnits') return { code: 'unit', label: '目标单元 · 非独立支线' };
    if (layer === 'reviewIssues') return { code: entity.status || 'unresolved', label: entity.status === 'confirmed_issue' ? '已发现问题' : statusLabel('mechanic', entity.status || 'unresolved') };
    var status = layer === 'causeEdges' ? (entity.resolved === true ? 'linked' : 'unlinked') : entity.status || 'unknown';
    return { code: status, label: statusLabel('mechanic', status) };
  }
  function mechanicTitle(layer, entity) {
    if (layer === 'relations') return (entity.a || '人物未提供') + ' — ' + (entity.b || '人物未提供') + ' · ' + (entity.kind || '联系');
    if (layer === 'characterStates') {
      var changed = (entity.before != null && entity.before !== '') || (entity.after != null && entity.after !== '');
      return (entity.character || '人物未提供') + ' · ' + (changed ? '变化声明' : '状态声明');
    }
    return entity.name || (layer === 'characterStates' ? (entity.character || '人物') + '的状态' : entity.description || LAYERS[layer] + '记录');
  }
  function semanticLabel(entity) {
    if (entity.claimVerified === true && entity.semanticStatus === 'reviewed') return '语义已复核';
    if (entity.claimStatus === 'unreviewed' || entity.claimVerified === false || entity.semanticStatus === 'unreviewed') return '语义判断待核';
    if (entity.claimStatus == null && entity.claimVerified == null && entity.semanticStatus == null) return '语义状态未提供 · 待核';
    if (entity.provenance === 'assistant-reviewed-source') return '对话审阅 · 待复核';
    return entity.basis === 'inferred' || entity.basis === 'inference' ? '推导 · 待校对' : entity.basis === 'uncertain' ? '关系未确认' : '材料归纳 · 待校对';
  }
  function fact(label, value) {
    return '<div class="sd-fact"><span class="sd-fact-label">' + esc(label) + '</span><p class="sd-fact-text">' + esc(value == null || value === '' ? '材料未提供' : value) + '</p></div>';
  }
  function taskStatusFact(entity) {
    var s = g.CLSkyTaskStatus ? g.CLSkyTaskStatus.of(entity) : null;
    if (!s) return '';
    var detail = s.hint || '';
    if (s.downgradedFrom) detail = s.downgradeReason + '；' + detail;
    var fields = s.fields && s.fields.complete ? '' : '（五字段缺 ' + (s.fields.missing.length) + ' 项）';
    return '<div class="sd-fact sd-task-status" data-task-status="' + esc(s.code) + '"><span class="sd-fact-label">状态</span>' +
      '<p class="sd-fact-text"><b class="sd-status-tag sd-status-' + esc(s.tone) + '">' + esc(s.label) + '</b>' +
      (s.rawStatus && s.rawStatus !== s.code ? '<span class="sd-status-raw">原文标记：' + esc(s.rawStatus) + '</span>' : '') +
      fields + '<span class="sd-status-hint">' + esc(detail) + '</span></p></div>';
  }
  function mechanicReferences(layer, entity) {
    var refs = [];
    function add(label, value) { refs.push({ label: label, value: value }); }
    if (layer === 'tasks' || layer === 'narrativeUnits' || layer === 'relations') {
      if (entity.outcomeEventId != null && entity.outcomeEventId !== '') add('结果事件（声明）', entity.outcomeEventId);
      arr(entity.eventIds).forEach(function (id) { add('相关事件', id); });
    }
    else if (layer === 'clues') { add('埋设事件', entity.seedEventId); add('兑现事件（声明）', entity.payoffEventId); }
    else if (layer === 'causeEdges') {
      add('前因事件（声明）', Object.prototype.hasOwnProperty.call(entity, 'sourceId') ? entity.sourceId : entity.fromEventId);
      add('后果事件（声明）', Object.prototype.hasOwnProperty.call(entity, 'targetId') ? entity.targetId : entity.toEventId);
    } else if (layer === 'reviewIssues') {
      if (entity.eventId != null) add('相关事件', entity.eventId);
      arr(entity.eventIds).forEach(function (id) { add('相关事件', id); });
    } else if (layer === 'characterStates') {
      add('本条状态所在事件', entity.eventId);
      var neighbors = stateNeighbors(entity);
      if (neighbors.previous) add('前一状态记录所在事件', neighbors.previous.eventId);
      if (neighbors.next) add('后一状态记录所在事件', neighbors.next.eventId);
    }
    return refs;
  }
  function stateNeighbors(entity) {
    var who = entity.characterId || entity.character, at = index.eventIds[str(entity.eventId)], previous = null, next = null;
    if (!who || at == null) return { previous: null, next: null };
    index.layers.characterStates.forEach(function (row) {
      var other = row.raw, i = index.eventIds[str(other.eventId)];
      if ((other.characterId || other.character) !== who || i == null || i === at) return;
      if (i < at && (!previous || i > index.eventIds[str(previous.eventId)])) previous = other;
      if (i > at && (!next || i < index.eventIds[str(next.eventId)])) next = other;
    });
    return { previous: previous, next: next };
  }
  function referenceRow(ref) {
    var i = ref.value == null || ref.value === '' ? null : index.eventIds[str(ref.value)], e = i != null ? graph.events[i] : null;
    return e ? '<button type="button" class="sd-detail-action" data-action="select-event" data-event-index="' + i + '" aria-label="' + esc('阅读' + ref.label + '：' + (e.title || '事件')) + '">' + esc(ref.label + ' · ' + (e.title || e.chapter || '事件')) + '</button>' : '<span class="sd-reference-unavailable">' + esc(ref.label) + ' · 未提供可确认的事件引用</span>';
  }
  function renderMechanics() {
    var cfg = browse.mechanics, layer = cfg.layer, rows = index.layers[layer] || [];
    var filtered = rows.filter(function (row) { return matches(row.search, cfg.query) && (cfg.filter === 'all' || row.status === cfg.filter); });
    var view = pageWindow(filtered, cfg), statusOptions = [{ value: 'all', label: '全部状态' }], seen = Object.create(null);
    rows.forEach(function (row) { if (!seen[row.status]) { seen[row.status] = true; statusOptions.push({ value: row.status, label: mechanicsStatus(layer, row.raw).label }); } });
    var tabs = Object.keys(LAYERS).map(function (key) { return '<button type="button" class="sd-detail-action" data-layer="' + key + '" aria-pressed="' + (key === layer) + '">' + LAYERS[key] + ' · ' + index.layers[key].length + '</button>'; }).join('');
    var list = view.items.map(function (row) { var entity = row.raw;
      var rs = layer === 'relations' ? relationScope(entity) : null;
      var rsb = rs ? relationScopeBadge(entity) : null;
      var rowAria = (layer === 'relations' && rs)
        ? ('关系：' + mechanicTitle(layer, entity) + '，' + rs.kindLabel + '，' + rs.evidenceLabel
           + '，' + rs.scopeLabel + '，' + (rs.evidenceHint || '') + '，阅读完整记录')
        : null;
      return '<button type="button" class="sd-event sd-mechanic-row is-summary' + (rs ? ' sd-rel-row rel-' + esc(rsb.tone) : '') + '" data-action="select-mechanic" data-mechanic-key="' + esc(row.key) + '"' + (rs ? ' data-rel-kind="' + esc(rs.kind) + '" data-rel-evidence="' + esc(rs.evidence) + '" data-rel-scope="' + esc(rs.scope) + '"' : '') + (rowAria ? ' aria-label="' + esc(rowAria) + '"' : '') + '><span class="sd-event-mark"></span><span class="sd-event-copy"><b>' + esc(clip(mechanicTitle(layer, entity), 34)) + '</b><small>' + esc((entity.character || entity.chapter || '') + (entity.character || entity.chapter ? ' · ' : '') + semanticLabel(entity)) + '</small></span>' + (rsb ? '<span class="sd-rel-scope" title="' + esc(rs.scopeHint) + '">' + esc(rsb.scopeLabel) + '</span><span class="sd-rel-evidence" title="' + esc(rs.evidenceHint) + '">' + esc(rs.evidenceLabel) + '</span>' : '') + '<em>' + esc(mechanicsStatus(layer, entity).label) + '</em></button>';
    }).join('');
    var selected = filtered.filter(function (row) { return row.key === cfg.selected; })[0] || view.items[0], detail = '';
    if (selected) {
      var entity = selected.raw, fields;
      if (layer === 'tasks') fields = taskStatusFact(entity) + fact('人物', entity.character) + fact('目标', entity.goal) + fact('障碍', entity.obstacle) + fact('行动', entity.action) + fact('结果', entity.outcome) + fact('代价', entity.cost);
      else if (layer === 'relations') fields = fact('人物', entity.a) + fact('关联人物', entity.b) + fact('关系', entity.kind) + fact('依据说明', entity.desc) + (entity.reviewNotes ? fact('审阅范围', entity.reviewNotes) : '');
      else if (layer === 'causeEdges') fields = fact('因果声明', entity.description);
      else if (layer === 'clues') fields = fact('线索说明', entity.summary) + fact('兑现状态', mechanicsStatus(layer, entity).label);
      else if (layer === 'narrativeUnits') fields = fact('目标', entity.goal) + fact('障碍', entity.obstacle) + fact('结果', entity.outcome) + fact('范围', arr(entity.chapters).join('、'));
      else if (layer === 'reviewIssues') fields = fact('核验批注', entity.description) + fact('建议', entity.proposedCorrection || '保留原记录，并明确材料中的疑点');
      else if (layer === 'characterStates') fields = fact('人物', entity.character) + fact('章节', entity.chapter) +
        (((entity.before != null && entity.before !== '') || (entity.after != null && entity.after !== '')) ? fact('变化前（声明）', entity.before) + fact('变化后（声明）', entity.after) : '') +
        ((entity.summary || entity.text) ? fact('状态声明', entity.summary || entity.text) : '');
      else {
        var neighbors = stateNeighbors(entity);
        fields = fact('人物', entity.character) + fact('章节', entity.chapter) +
          ((entity.before != null || entity.after != null) ? fact('变化前（声明）', entity.before) + fact('变化后（声明）', entity.after) : '') +
          ((entity.summary || entity.text) ? fact('状态声明', entity.summary || entity.text) : '') +
          fact('前一状态记录', neighbors.previous && neighbors.previous.summary) + fact('后一状态记录', neighbors.next && neighbors.next.summary);
      }
      var quotes = evidenceText(entity);
      if (g.CLAtlasSource && g.CLAtlasSource.sourceRefs) g.CLAtlasSource.sourceRefs(entity).forEach(function (ref) {
        var q = str(ref.quote).trim(); if (q && quotes.indexOf(q) < 0) quotes.push(q);
      });
      [entity.seedQuote, entity.payoffQuote].forEach(function (q) { if (str(q).trim() && quotes.indexOf(str(q).trim()) < 0) quotes.push(str(q).trim()); });
      var quoteView = pageWindow(quotes, browse.mechanicQuotes), refs = pageWindow(mechanicReferences(layer, entity), browse.references);
      var attributes = pageWindow(arr(entity.attributes).filter(function (a) { return a && typeof a === 'object'; }), browse.attributes);
      var journey = (layer === 'tasks' || layer === 'narrativeUnits') && g.CLSky && g.CLSky.journeyPlan ? g.CLSky.journeyPlan(layer, entity.id) : null;
      var journeyAction = journey ? '<div class="sd-person-actions"><button type="button" class="sd-detail-action" data-action="play-record" data-record-layer="' + esc(layer) + '" data-record-id="' + esc(entity.id) + '"' + (journey.ok ? '' : ' disabled') + '>播放此' + (layer === 'tasks' ? '任务' : '剧情单元') + (journey.ok ? ' · ' + journey.count + ' 个事件' : '') + '</button></div><p class="sd-evidence-note sd-journey-message" role="status">' + esc(journey.ok ? '仅播放此记录引用的事件；可暂停、逐项阅读或返回全书。' : journey.message || '事件引用或原文依据不完整，暂不能播放。') + '</p>' : '';
      var detailStatus = layer === 'characterStates' ? ((entity.before != null || entity.after != null) ? '变化声明 · ' + stateBasisLabel(entity) : '状态声明 · ' + stateBasisLabel(entity)) : mechanicsStatus(layer, entity).label;
      detail = '<article class="sd-mechanics-card"><div class="sd-detail-top"><b>' + esc(mechanicTitle(layer, entity)) + '</b><em>' + esc(semanticLabel(entity)) + '</em></div>' + (layer === 'relations' && browse.neighbors.returnAfterBasis ? '<button type="button" class="sd-detail-action" data-action="neighbor-return">← 返回共同联系人</button>' : '') + journeyAction + '<p class="sd-evidence-note">' + esc(detailStatus) + (layer === 'characterStates' ? '。变化前后为记录声明；语义判断待核。' : '。引用通过校验不等于这条关系已经得到人工确认。') + '</p><div class="sd-fact-grid">' + fields + '</div>' +
        (attributes.items.length ? '<div class="sd-attributes">' + attributes.items.map(function (attribute) { return '<section class="sd-attribute">' + fact(attribute.name || '属性', attribute.value) + (attribute.quote ? quoteRow(attribute, attribute.quote) : '<p class="sd-empty">该属性未提供引句。</p>') + '</section>'; }).join('') + (attributes.pages > 1 ? pager('attributes', attributes) : '') + '</div>' : '') +
        '<div class="sd-evidence-links">' + refs.items.map(referenceRow).join('') + '</div>' + (refs.pages > 1 ? pager('references', refs) : '') +
        (quoteView.items.length ? '<div class="sd-mechanic-quotes">' + quoteView.items.map(function (q) { return quoteRow(entity, q); }).join('') + (quoteView.pages > 1 ? pager('mechanicQuotes', quoteView) : '') + '</div>' : '<p class="sd-empty">这条记录未提供原文引句。</p>') + '</article>';
    }
    var empty = rows.length ? '没有匹配的记录；可清空搜索或调整筛选。' : Object.prototype.hasOwnProperty.call(graph, layer) ? '本次分析未返回可确认的' + LAYERS[layer] + '记录；空结果不代表全书不存在。' : '这次分析尚未提供' + LAYERS[layer] + '层；无法据此判断全书有无相关结构。';
    return '<section class="sd-section sd-mechanics"><div class="sd-section-head"><b>目标、因果与状态</b><span>逐条回到材料</span></div><nav class="sd-mechanics-tabs" aria-label="情节证据类型">' + tabs + '</nav><div class="sd-controls">' + searchControl('mechanics', '目标、障碍、代价、人物或引文') + '<label class="sd-filter"><span class="sd-control-label">状态</span><select data-filter="mechanics" aria-label="按情节记录状态筛选">' + options(statusOptions, cfg.filter) + '</select></label></div><div class="sd-event-list">' + (list || '<p class="sd-empty sd-mechanics-empty">' + esc(empty) + '</p>') + '</div>' + (rows.length ? pager('mechanics', view) : '') + detail +
      (function () {
        var ws = arr(graph.worldSettings), th = arr(graph.themeReadings), out = '';
        if (!ws.length) {
          out += '<p class="sd-evidence-note sd-world-gap-note" role="status">'
            + esc('本片未显示世界规则、地点或物件：当前图谱版本没有这类记录，'
              + '而根因是此前的精读产出清单里没有要求提取它（已补入并重发给未完成任务）。'
              + '这不是「作品没有设定」。')
            + '</p>';
        }
        if (!th.length) {
          out += '<p class="sd-evidence-note sd-theme-gap-note" role="status">'
            + esc('本片未显示主题或张力解释：当前图谱版本没有这类记录，'
              + '根因同样是产出清单里此前没有要求（已补入 themeReadings 并重发给未完成任务）。'
              + '主题与张力属解释层，不是事实层；本作品是否具备主题不由此判定。')
            + '</p>';
        }
        return out;
      })() +
      (layer === 'relations' ? (function () {
        var tall = g.CLSkyRelationScope ? g.CLSkyRelationScope.tally(arr(graph.relations)) : null;
        if (!tall) return '';
        return '<p class="sd-evidence-note sd-rel-ledger" role="status">' + esc(tall.summary)
          + '　' + esc(tall.note) + '</p>';
      })() : '') + '</section>';
  }

  function renderCoverage() {
    var summary = index.coverage; if (!summary) return '';
    var labels = g.CLSkyCoverage.layers, view = pageWindow(summary.records, browse.coverage);
    var rows = view.items.map(function (record) {
      var source = record.applicability === 'current' ? '对应当前原文版本' : record.applicability === 'source_changed' ? '原文版本已变 · 不计当前范围' : '历史声明 · 原文版本未绑定';
      return '<details class="sd-coverage-record"><summary>' + esc(record.layers.map(function (layer) { return labels[layer]; }).join('、')) + '<small>' + esc(source) + '</small></summary>' + record.lines.map(function (line) { return '<p>' + esc(line) + '</p>'; }).join('') +
        (record.gaps.length ? '<p class="sd-evidence-note">未审范围与限制</p><ul>' + record.gaps.map(function (gap) { return '<li>' + esc(gap) + '</li>'; }).join('') + '</ul>' : '') + '<p class="sd-evidence-note">' + (record.origin === 'legacy_metadata' ? '保留的旧范围声明，没有在本次重新完成审阅。' : '对话审阅范围记录，未认证全书语义完整性。') + '</p></details>';
    }).join('');
    var layers = summary.layers.map(function (layer) {
      var declared = layer.count > 0, reviewed = layer.reviewed > 0;
      return '<button type="button" class="sd-detail-action sd-coverage-layer ' + (declared ? (reviewed ? 'is-reviewed' : 'is-declared') : 'is-absent') + '" data-action="coverage-layer" data-record-layer="' + layer.key + '" aria-label="' + esc(layer.label + '：' + (declared ? (reviewed ? '已有声明与审阅记录' : '有记录但未完成独立审阅') : '本次分析未声明该层')) + '"><b>' + layer.label + '</b><span>' + (declared ? (reviewed ? '已审阅 ' + layer.reviewed + ' / ' + layer.count : '已声明 ' + layer.count + ' · 待审') : '尚未声明') + '</span></button>';
    }).join('');
    return '<section class="sd-section sd-coverage"><div class="sd-section-head"><b>审阅范围</b><span>覆盖程度尚待完整核验</span></div><p class="sd-evidence-note">图谱可浏览，不表示整部原文已经精读。引句定位与内容判断分别记录。</p>' +
      '<p class="sd-coverage-count">引句已定位 <b>' + summary.anchoredEvents + ' / ' + summary.events + '</b> 个已有事件</p><div class="sd-section-head"><b>对话审阅标记 / 已有记录</b></div><div class="sd-coverage-layers">' + layers + '</div>' +
      (summary.issues ? '<button type="button" class="sd-detail-action" data-action="coverage-layer" data-record-layer="reviewIssues">查看 ' + summary.issues + ' 条核验批注</button>' : '<p class="sd-evidence-note">未登记核验批注，不代表没有问题。</p>') +
      (summary.malformed ? '<p class="sd-evidence-note">部分历史范围记录格式无效，未据此计算覆盖。</p>' : '') +
      (rows || '<p class="sd-empty">尚未保存明确的精读范围；不能从节点数量推算全文覆盖。</p>') + (view.pages > 1 ? pager('coverage', view) : '') + '</section>';
  }
  function structureReady() {
    var stats = g.CLSkyDeep && g.CLSkyDeep.stats ? g.CLSkyDeep.stats() : null;
    return !!(stats && stats.structure && stats.structure.progress >= 1 && !stats.structure.moving);
  }
  function renderOverview() {
    var facts = index.structure || structureFacts();
    var density = arr(model.density), stride = Math.max(1, Math.ceil(density.length / 128)), buckets = [];
    for (var lo = 0; lo < density.length; lo += stride) {
      var hi = Math.min(density.length, lo + stride), sum = 0, first = null;
      for (var ci = lo; ci < hi; ci++) { sum += num(density[ci]); if (first == null && arr(model.chapterEvents[ci]).length) first = model.chapterEvents[ci][0]; }
      buckets.push({ lo: lo, hi: hi - 1, n: sum, first: first });
    }
    var max = Math.max.apply(null, buckets.map(function (b) { return b.n; }).concat([1]));
    var pulse = buckets.map(function (b) {
      var first = b.first, chapter = (model.chapters[b.lo] || {}).no || b.lo + 1, last = (model.chapters[b.hi] || {}).no || b.hi + 1;
      var title = '第' + chapter + (chapter === last ? '' : '–' + last) + ' · ' + b.n + ' 个剧情点';
      if (first == null) return '<span class="sd-pulse-bar is-empty" data-sd-h="' + (8 + b.n / max * 92).toFixed(2) + '" title="' + esc(title) + ' · 无可定位事件" aria-hidden="true"><i></i></span>';
      return '<button type="button" class="sd-pulse-bar" data-event-index="' + first + '" data-sd-h="' + (8 + b.n / max * 92).toFixed(2) + '" aria-label="' + esc(title + '，点击定位') + '" title="' + esc(title) + '"><i></i></button>';
    }).join('');
    var key = index.events.slice().sort(function (a, b) { return b.score - a.score || a.i - b.i; }).slice(0, 6);
    return renderStructureOverview(facts) + renderCoverage() + '<section class="sd-section"><div class="sd-section-head"><b>叙事脉冲</b><span>横轴 = ' + esc(model.axis && model.axis.unit || '章节') + ' · 高度 = 区间事件数</span></div><div class="sd-pulse" data-sd-cols="' + Math.max(1, buckets.length) + '">' + (pulse || '<span class="sd-empty">暂无章节事件密度</span>') + '</div></section>' +
      '<section class="sd-section"><div class="sd-section-head"><b>关键转折</b><button type="button" class="sd-link" data-mode="evidence">进入证据层 →</button></div><div class="sd-event-list">' + (key.length ? key.map(function (x) { return eventRow(x.i, false); }).join('') : '<p class="sd-empty">暂未识别关键转折。</p>') + '</div></section>';
  }

  function shownCount(fact) { return !fact || !fact.provided ? '未提供记录' : String(fact.count); }
  function structureButton(label, value, action, extra) {
    return '<button type="button" class="sd-detail-action sd-structure-link" data-action="structure-nav" data-structure-nav="' + esc(action) + '"' + (extra || '') + '><b>' + esc(label) + '</b><span>' + esc(value) + ' →</span></button>';
  }
  function renderStructureOverview(f) {
    var r = f.routes || {}, groups = shownCount(f.groups), units = shownCount(f.units), clues = shownCount(f.clues);
    var plotNow = g.CLSky && g.CLSky.state && g.CLSky.state().plot;
    var routeHint = '来源标记主线 ' + (r.mainDeclared || 0) + ' · 来源标记支线 ' + (r.branchDeclared || 0) + ' · 模型综合 ' + (r.synthesis || 0) + ' · 自动分段 ' + (r.autoSegments || 0) + ' · 其他推导 ' + (r.derived || 0) + ' · 来源未明确 ' + (r.sourceUnclear || 0);
    var axisText = f.axis.sequential + ' 个原文顺序章节 + ' + f.axis.otherMaterials + ' 项其他材料；' + f.axis.summary;
    var layers = ['characters', 'groups', 'relations', 'events'].map(function (key) {
      var checked = m84.selected === key;
      return '<button type="button" class="sd-structure-layer" data-action="structure-layer" data-structure-layer="' + key + '" aria-pressed="' + checked + '">' + ({characters:'人物',groups:'群组',relations:'关系',events:'事件'}[key]) + '</button>';
    }).join('');
    var structureMode = structureReady();
    return '<section class="sd-section sd-structure-overview"><div class="sd-section-head"><b>同一张图的组成</b><span>' + esc(f.scope) + '</span></div>' +
      '<div class="sd-structure-grid">' +
      structureButton('人物', shownCount(f.people), 'people') +
      structureButton('群组 / 阵营', groups, 'groups') +
      structureButton('人物关系', shownCount(f.relations), 'relations') +
      structureButton('事件', shownCount(f.events), 'events') +
      structureButton('章节轴', model.nCh + ' 项 · ' + f.axis.sequential + ' 正文 / ' + f.axis.otherMaterials + ' 其他', 'chapters', ' title="' + esc(axisText) + '"') +
      structureButton('剧情单元', units, 'units') +
      structureButton('主线 / 支线', (r.mains || 0) + ' / ' + (r.branches || 0), 'lines', ' title="' + esc(routeHint) + '"') +
      structureButton('伏笔记录', clues, 'clues') + '</div>' +
      '<p class="sd-evidence-note">路线来源：' + esc(routeHint) + '。主线/支线的总数包含自动分段与推导记录，不能视作作者已声明的结构。伏笔显示已提供的记录数；没有兑现记录不等于没有伏笔。</p>' +
      '<div class="sd-structure-actions"><div class="sd-controls">' + (structureMode ? '<button type="button" class="sd-detail-action" data-action="structure-stage">分层解释</button>' : '') + (f.events.provided && f.events.count > 0 && !plotNow ? '<button type="button" class="sd-detail-action" data-action="structure-plot">进入剧情视图以展开事件位置</button>' : '') + '</div><div class="sd-structure-layers" role="group" aria-label="选择结构副本层">' + layers + '</div></div>' +
      '<p class="sd-evidence-note">分层只移动说明副本；原对象与镜头留在原位。</p></section>';
  }

  var m84Stage = null, m84Tween = null, m84InputCancel = null;
  function m84Projection(key, sample) {
    var sky = g.CLSky, pt = null;
    if (!sample || !sky) return null;
    if (key === 'characters') {
      var map = sky.starScreens ? sky.starScreens([sample.name]) : null;
      pt = map && map[sample.name];
    } else if (key === 'groups') {
      var points = sky.starScreens ? sky.starScreens(sample.members.map(function (p) { return p.name; })) : null;
      var visible = sample.members.map(function (p) { var xy = points && points[p.name]; return xy && isFinite(xy[0]) && isFinite(xy[1]) ? { id: p.id, point: xy } : null; }).filter(Boolean);
      if (visible.length) pt = visible[0].point;
      m84Projection.anchors = visible;
    } else if (key === 'relations') {
      var both = sky.starScreens ? sky.starScreens([sample.a.name, sample.b.name]) : null, a = both && both[sample.a.name], b = both && both[sample.b.name];
      if (a && b) { pt = a; m84Projection.anchors = [{ id: sample.a.id, point: a }, { id: sample.b.id, point: b }]; }
    } else if (key === 'events') {
      var skyState = sky.state && sky.state(), disc = skyState && skyState.plot && sky.disc && sky.disc(), event = disc && disc.eventPoint && disc.eventPoint(sample.index);
      if (event) pt = [event.x, event.y];
    }
    if (key !== 'groups' && key !== 'relations') m84Projection.anchors = pt ? [{ id: sample.id, point: pt }] : [];
    return pt && isFinite(pt[0]) && isFinite(pt[1]) ? pt : null;
  }
  function m84Sample(key, f) { return key === 'characters' ? f.people.sample : key === 'groups' ? f.groupSample : key === 'relations' ? f.relations.sample : f.events.sample; }
  function m84SourceId(key, sample) { return key === 'groups' ? sample && sample.key : sample && sample.id; }
  function m84CountSummary(key, f, sample, anchor) {
    var fact = key === 'characters' ? f.people : key === 'groups' ? f.groups : f[key];
    if (!fact || !fact.provided) return '记录总数未提供';
    var total = fact.count || 0;
    if (!total) return '共 0 条记录';
    if (!sample) return '共 ' + total + ' 条记录 · 暂无唯一示例';
    var summary = '示例 1 / ' + total;
    if (key === 'groups') summary += ' · 成员已解析并展示 ' + sample.members.length + ' / ' + sample.memberTotal;
    return summary;
  }
  function cancelM84(clear, returnFocus) {
    if (m84Tween && g.CLSkyMotion) g.CLSkyMotion.cancelAll('m84');
    if (m84InputCancel) { m84InputCancel(); m84InputCancel = null; }
    m84Tween = null;
    if (clear && m84Stage && m84Stage.parentNode) m84Stage.parentNode.removeChild(m84Stage);
    if (clear) m84Stage = null;
    var trigger = m84.trigger, restoreScroll = m84.openScroll;
    m84.open = false;
    if (returnFocus && trigger && trigger.isConnected) {
      var body = doc.getElementById('skyDeconBody'); if (body && restoreScroll != null) body.scrollTop = restoreScroll;
      if (trigger.focus) trigger.focus({ preventScroll: true });
      if (trigger.scrollIntoView) trigger.scrollIntoView({ block: 'nearest' });
    }
    m84.trigger = null; m84.openScroll = null;
  }
  function clearM84Return() {
    m84.returning = false; m84.returnOpen = false; m84.returnScroll = null; m84.returnLayer = null;
  }
  function stageMarkup(f) {
    var keys = ['characters', 'groups', 'relations', 'events'], labels = {characters:'人物',groups:'群组',relations:'关系',events:'事件'}, positions = {};
    var mobile = g.innerWidth <= 680;
    var cards = keys.map(function (key, i) {
      var sample = m84Sample(key, f), exists = key === 'groups' ? f.groups.provided && f.groups.count > 0 : f[key === 'characters' ? 'people' : key].provided && f[key === 'characters' ? 'people' : key].count > 0;
      var anchor = exists ? m84Projection(key, sample) : null, anchors = anchor ? (m84Projection.anchors || []) : [], name = sample ? (key === 'characters' ? sample.name : key === 'groups' ? sample.name : key === 'relations' ? sample.a.name + ' ↔ ' + sample.b.name : sample.title) : '';
      positions[key] = anchors;
      var plotNow = g.CLSky && g.CLSky.state && g.CLSky.state().plot;
      var detail = !exists ? '当前无记录' : !sample ? '有记录；当前未取得唯一对象引用' : key === 'events' && !anchor && !plotNow ? '当前视图未展开事件' : key === 'events' && !anchor ? '此事件在当前剧情视图没有投影' : !anchor ? '当前视图未投影此对象' : (name || labels[key]);
      var sourceId = m84SourceId(key, sample), sourceIndex = sample && sample.index;
      var sourcePoints = anchors.map(function (p) { return p.point[0] + ',' + p.point[1]; }).join(';');
      var meta = key === 'groups' && sample ? '展示成员：' + sample.members.map(function (person) { return person.name; }).join('、') : key === 'relations' ? sample && sample.kind + ' · ' + sample.scope : key === 'events' ? sample && sample.chapter : sample && (sample.identity || '身份未提供');
      return '<article class="sd-structure-copy layer-' + key + (m84.selected === key ? ' is-selected' : '') + (anchor ? ' has-source' : '') + '" data-structure-copy="' + key + '" data-layer-depth="' + i + '"' + (anchor ? ' data-source-x="' + anchor[0] + '" data-source-y="' + anchor[1] + '" data-source-points="' + sourcePoints + '"' : '') + (sourceId != null ? ' data-source-id="' + esc(sourceId) + '"' : '') + (key === 'groups' && sample ? ' data-source-members="' + esc(sample.ids.join(',')) + '"' : key === 'relations' && sample ? ' data-source-members="' + esc(sample.a.id + ',' + sample.b.id) + '"' : '') + (sourceIndex != null ? ' data-source-index="' + sourceIndex + '"' : '') + '><small>' + labels[key] + '</small><b>' + esc(detail) + '</b>' + (meta && (anchor || key === 'groups') ? '<span>' + esc(meta) + '</span>' : '') + '<span class="sd-structure-count">' + esc(m84CountSummary(key, f, sample, anchor)) + '</span></article>';
    }).join('');
    var lines = mobile ? '' : keys.map(function (key) { var ps = positions[key] || [], i = keys.indexOf(key), target = ps.length ? ps[0].point : null; if (!target) return ''; return ps.map(function (p, j) { return '<line data-guide="' + key + '" data-guide-index="' + j + '" x1="' + p.point[0] + '" y1="' + p.point[1] + '" x2="' + target[0] + '" y2="' + (target[1] - (i + 1) * 28) + '" />'; }).join(''); }).join('');
    return '<div class="sd-structure-stage' + (mobile ? ' is-inline' : '') + '" aria-hidden="' + String(!mobile) + '"><div class="sd-structure-stage-title">同一张图的组成' + (mobile ? '<button type="button" class="sd-structure-stage-close" data-action="structure-stage">收起</button>' : '') + '</div><svg class="sd-structure-guides" viewBox="0 0 ' + g.innerWidth + ' ' + g.innerHeight + '" preserveAspectRatio="none">' + lines + '</svg><div class="sd-structure-copies">' + cards + '</div></div>';
  }
  function openM84() {
    if (m84.open) return;
    m84.open = true; m84.request++;
    m84.returning = false;
    var readingBody = doc.getElementById('skyDeconBody');
    m84.openScroll = readingBody ? readingBody.scrollTop : 0;
    m84.trigger = root && root.querySelector('[data-action="structure-stage"]');
    var readingBody = doc.getElementById('skyDeconBody');
    m84.openScroll = readingBody ? readingBody.scrollTop : 0;
    m84.trigger = root && root.querySelector('[data-action="structure-stage"]');
    if (g.CLSky) {
      if (g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
      if (g.CLSky.showParticipants) g.CLSky.showParticipants(false);
      if (g.CLSky.state && g.CLSky.state().playing && g.CLSky.stop) g.CLSky.stop();
    }
    var f = index.structure || structureFacts(), mobile = g.innerWidth <= 680;
    m84Stage = doc.createElement('div'); m84Stage.innerHTML = stageMarkup(f); m84Stage = m84Stage.firstChild;
    var overview = root && root.querySelector('.sd-structure-overview');
    if (mobile && overview) overview.appendChild(m84Stage); else doc.body.appendChild(m84Stage);
    var dismiss = function (event) { if (event && root && root.contains(event.target)) return; if (m84.open) cancelM84(true); };
    var dismissOnRotateKey = function (event) { if (/^Arrow(Left|Right|Up|Down)$/.test(event.key || '')) dismiss(event); };
    g.addEventListener('resize', dismiss);
    g.addEventListener('pointerdown', dismiss, true);
    g.addEventListener('wheel', dismiss, { capture: true, passive: true });
    g.addEventListener('keydown', dismissOnRotateKey, true);
    m84InputCancel = function () { g.removeEventListener('resize', dismiss); g.removeEventListener('pointerdown', dismiss, true); g.removeEventListener('wheel', dismiss, true); g.removeEventListener('keydown', dismissOnRotateKey, true); };
    var safeRight = g.innerWidth - 24;
    if (!mobile && root) { var rb = root.getBoundingClientRect(); if (rb.width > 0) safeRight = Math.max(0, Math.min(safeRight, rb.left - 24)); }
    var margin = 24, gap = 32, cardWidth = Math.min(300, Math.max(150, (safeRight - margin * 2 - gap) / 2));
    var firstTop = Math.max(220, g.innerHeight * .26), secondTop = Math.max(firstTop + 250, g.innerHeight * .58);
    var targetByKey = {
      characters: { x: margin + cardWidth / 2, top: firstTop },
      groups: { x: safeRight - margin - cardWidth / 2, top: firstTop },
      relations: { x: margin + cardWidth / 2, top: secondTop },
      events: { x: safeRight - margin - cardWidth / 2, top: secondTop }
    };
    var copies = m84Stage.querySelectorAll('.sd-structure-copy');
    Array.prototype.forEach.call(copies, function (card) {
      var i = num(card.getAttribute('data-layer-depth'));
      var key = card.getAttribute('data-structure-copy'), target = targetByKey[key], x = num(card.getAttribute('data-source-x'), target.x), y = num(card.getAttribute('data-source-y'), target.top + card.offsetHeight + (i + 1) * 28);
      if (!mobile) card.style.width = cardWidth + 'px';
      card.style.setProperty('--sd-x', x + 'px'); card.style.setProperty('--sd-y', y + 'px');
      card.setAttribute('data-target-x', String(target.x)); card.setAttribute('data-target-top', String(target.top));
      var label = card.querySelector('small'); if (label) label.style.opacity = '0';
    });
    var prefersReduced = g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function paint(v) {
      if (!m84Stage || !m84Stage.isConnected) return;
      m84Stage.style.opacity = String(Math.min(1, v / .18));
      var lift = Math.max(0, Math.min(1, (v - .2) / .4));
      Array.prototype.forEach.call(m84Stage.querySelectorAll('.sd-structure-copy'), function (card) {
        var depth = num(card.getAttribute('data-layer-depth'));
        if (g.innerWidth > 680) {
          var height = card.offsetHeight, tx = num(card.getAttribute('data-target-x')), top = num(card.getAttribute('data-target-top'));
          var sx = num(card.getAttribute('data-source-x'), tx), sy = num(card.getAttribute('data-source-y'), top + height + (depth + 1) * 28);
          card.style.setProperty('--sd-x', (sx + (tx - sx) * lift) + 'px');
          card.style.setProperty('--sd-y', (sy + (top + height + (depth + 1) * 28 - sy) * lift) + 'px');
          card.style.transform = 'translate(-50%, -100%) translateY(' + (-28 * (depth + 1) * lift) + 'px)';
          card.style.opacity = String(v < .18 ? 0 : 1);
          var label = card.querySelector('small'); if (label) label.style.opacity = String(Math.max(0, Math.min(1, (v - .6) / .2)));
        } else { card.style.opacity = '1'; var mobileLabel = card.querySelector('small'); if (mobileLabel) mobileLabel.style.opacity = '1'; }
      });
      Array.prototype.forEach.call(m84Stage.querySelectorAll('[data-guide]'), function (line) {
        var key = line.getAttribute('data-guide'), card = m84Stage.querySelector('[data-structure-copy="' + key + '"]');
        if (!card) return;
        var depth = num(card.getAttribute('data-layer-depth')), h = card.offsetHeight, targetTop = num(card.getAttribute('data-target-top'));
        var targetX = num(card.getAttribute('data-target-x'), g.innerWidth / 2), startX = num(card.getAttribute('data-source-x'), targetX), startY = num(card.getAttribute('data-source-y'), targetTop + h);
        line.setAttribute('y2', String(startY + (targetTop + h - startY) * lift));
        line.setAttribute('x2', String(startX + (targetX - startX) * lift));
        line.style.opacity = String(lift);
      });
      var title = m84Stage.querySelector('.sd-structure-stage-title');
      if (title) title.style.opacity = String(Math.max(0, Math.min(1, (v - .6) / .2)));
      m84Stage.setAttribute('data-progress', String(v));
      m84Stage.setAttribute('data-phase', v < .2 ? 'create' : v < .6 ? 'lift' : v < .8 ? 'labels' : 'settled');
    }
    if (mobile || prefersReduced || !g.CLSkyMotion) paint(1);
    else { m84Tween = g.CLSkyMotion.tween({ from: 0, to: 1, dur: .9, ease: function (v) { return v; }, tag: 'm84', onUpdate: paint, onDone: function () { m84Tween = null; } }); }
    if (mobile && m84Stage.scrollIntoView) m84Stage.scrollIntoView({ block: 'nearest' });
    if (mobile && m84Stage.scrollIntoView) m84Stage.scrollIntoView({ block: 'nearest' });
  }
  function selectM84Layer(key) {
    if (['characters','groups','relations','events'].indexOf(key) < 0) return;
    m84.selected = key;
    if (root) Array.prototype.forEach.call(root.querySelectorAll('[data-structure-layer]'), function (b) { var on = b.getAttribute('data-structure-layer') === key; b.setAttribute('aria-pressed', String(on)); });
    if (m84Stage) {
      Array.prototype.forEach.call(m84Stage.querySelectorAll('.sd-structure-copy'), function (card) { var on = card.getAttribute('data-structure-copy') === key; card.classList.toggle('is-selected', on); });
      m84Stage.style.setProperty('--sd-select-progress', '1');
    }
    if (!m84.open && root && state.mode === 'overview' && !m84.returning) { state.restore = { attr: 'data-structure-layer', value: key }; render(); }
  }
  function renderLines() {
    var rows = arr(model.mains).map(function (line) { return { line: line, main: true }; }).concat(arr(model.lines).slice().sort(function (a, b) { return num(a.c0) - num(b.c0) || num(b.n) - num(a.n); }).map(function (line) { return { line: line, main: false }; }));
    var declared = [], automatic = [], focusedAutomatic = false;
    rows.forEach(function (row) {
      (row.line.autoSegment ? automatic : declared).push(lineRow(row.line, model.nCh, row.main));
      if (row.line.autoSegment && state.focus === row.line.id) focusedAutomatic = true;
    });
    var axis = [0, Math.floor(Math.max(0, model.nCh - 1) / 2), Math.max(0, model.nCh - 1)].filter(function (c, i, all) { return all.indexOf(c) === i; }).map(function (c) {
      var label = g.CLSkyModel && g.CLSkyModel.chapterLabel ? g.CLSkyModel.chapterLabel(model, c) : '章节 ' + (c + 1);
      return '<span>' + esc(label) + '</span>';
    }).join('');
    return '<section class="sd-section"><div class="sd-section-head"><b>故事线 · 章节跨度</b><span>点击定位星盘</span></div><p class="sd-evidence-note">轨道标出已有事件的章节范围。目标、结局与来源分别标注；章节中点不代表剧情高潮。</p><div class="sd-axis">' + axis + '</div><div class="sd-lines">' + (declared.join('') || (automatic.length ? '<p class="sd-evidence-note">当前仅有自动分段，尚未建立可确认的故事骨架。</p>' : '<p class="sd-empty">这份材料没有可绘制的剧情线。</p>')) + '</div>' +
      (automatic.length ? '<details class="sd-auto-lines"' + (focusedAutomatic ? ' open' : '') + '><summary>自动分段 ' + automatic.length + ' 条 · 非作者结构</summary><p class="sd-evidence-note">保留全部事件与定位入口，不将等分片段作为任务深度依据。</p><div class="sd-lines">' + automatic.join('') + '</div></details>' : '') + '</section>';
  }
  function personStableId(p) { var raw = p && p.raw || {}; var id = raw.id != null ? raw.id : raw.entityId; return id == null || id === '' ? null : String(id); }
  function comparePersonNeighbors() {
    var cfg = browse.neighbors, origin = cfg.origin, list = index && index.people || [];
    var person = list.filter(function (p) { return personKey(p) === origin; })[0], aId = personStableId(person);
    if (!aId || !cfg.bId || !g.CLSkyModel || typeof g.CLSkyModel.compareRelations !== 'function') { cfg.result = null; if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); render(); return false; }
    cfg.result = g.CLSkyModel.compareRelations(graph, aId, cfg.bId, { kind: cfg.kind }); cfg.tab = 'common'; cfg.demoCounts = null;
    if (cfg.result.ok && g.CLSky && g.CLSky.beginNeighborCompare) { var demo = g.CLSky.beginNeighborCompare(cfg.result); cfg.demoCounts = demo && demo.demoCounts || null; }
    else if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
    render(); return !!cfg.result.ok;
  }
  function clearNeighborPerson() {
    var cfg = browse.neighbors; cfg.bId = ''; cfg.tab = 'onlyA';
    var list = index && index.people || [], person = list.filter(function (p) { return personKey(p) === cfg.origin; })[0], aId = personStableId(person);
    cfg.result = aId && g.CLSkyModel && g.CLSkyModel.compareRelations ? g.CLSkyModel.compareRelations(graph, aId, null, { kind: cfg.kind }) : null; cfg.demoCounts = null;
    if (cfg.result && cfg.result.ok && g.CLSky && g.CLSky.beginNeighborCompare) { var demo = g.CLSky.beginNeighborCompare(cfg.result); cfg.demoCounts = demo && demo.demoCounts || null; }
    else if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare();
    render();
  }
  function renderNeighborPanel(detail) {
    var cfg = browse.neighbors, people = g.CLSkyModel && g.CLSkyModel.relationPeople ? g.CLSkyModel.relationPeople(graph).people : [];
    var aId = personStableId(detail), aRows = people.filter(function (p) { return p.id === aId; }), aOk = !!(aId && aRows.length === 1 && aRows[0].selectable);
    var choices = people.filter(function (p) { return p.id !== aId; });
    var select = '<label><span class="sd-control-label">B · 明确选择另一人</span><select data-neighbor-person="b" aria-label="选择比较人物B"><option value="">请选择人物B</option>' + choices.map(function (p) { return '<option value="' + esc(p.id || '') + '"' + (cfg.bId === p.id ? ' selected' : '') + (p.selectable ? '' : ' disabled') + '>' + esc(p.name + (p.role ? ' · ' + p.role : '') + (p.selectable ? '' : ' · ' + (p.reason || '身份待区分'))) + '</option>'; }).join('') + '</select></label>';
    if (cfg.result && cfg.result.ok) {
      var result = cfg.result, groups = { common: result.common, onlyA: result.onlyA, onlyB: result.onlyB }, labels = { common: '共同联系人', onlyA: result.mode === 'single' ? 'A的一度联系人' : '仅与A有记录', onlyB: '仅与B有记录' };
      var tabs = ['common','onlyA','onlyB'].map(function (key) { return '<button type="button" data-action="neighbor-tab" data-neighbor-tab="' + key + '" aria-pressed="' + (cfg.tab === key) + '">' + labels[key] + ' · ' + groups[key].length + '</button>'; }).join('');
      var rows = groups[cfg.tab] || [], list = rows.map(function (person) {
        var rels = cfg.tab === 'onlyB' ? person.relationsB : cfg.tab === 'onlyA' || result.mode === 'single' ? person.relationsA : person.relationsA.concat(person.relationsB);
        var summary = rels.map(function (rel) {
          var open = rel.id != null && rel.recordUnique;
          var owner = cfg.tab === 'common' ? (person.relationsA.indexOf(rel) >= 0 ? result.a.name : (result.b && result.b.name || 'B')) : cfg.tab === 'onlyA' ? result.a.name : result.b && result.b.name || 'B';
          return '<button type="button" class="sd-neighbor-record" data-action="neighbor-basis" data-record-id="' + esc(rel.id || '') + '"' + (open ? '' : ' disabled title="重复或缺少记录ID，不能唯一返回依据"') + '><b>' + esc(owner + ' · ' + (rel.kindLabel || rel.kind || '关系类型未标明')) + '</b><small>' + esc((rel.evidenceLabel || '依据状态未标明') + ' · ' + (rel.scopeLabel || '范围未标明')) + '</small></button>';
        }).join('');
        return '<article class="sd-neighbor-person" data-neighbor-id="' + esc(person.id) + '"><b>' + esc(person.name || '姓名未提供') + '</b>' + (summary || '<p class="sd-neighbor-note">当前筛选范围内没有可展示的关系记录。</p>') + '</article>';
      }).join('');
      var demos = cfg.demoCounts ? (cfg.tab === 'common' ? cfg.demoCounts.common : cfg.tab === 'onlyA' ? cfg.demoCounts.onlyA : cfg.demoCounts.onlyB) : 0;
      var totalDemo = cfg.demoCounts ? cfg.demoCounts.common + cfg.demoCounts.onlyA + cfg.demoCounts.onlyB : 0;
      return '<section class="sd-neighbor"><div class="sd-neighbor-head"><b>共同联系人</b><small>A · ' + esc(detail.name) + (result.b ? '　B · ' + esc(result.b.name) : '') + '</small><button type="button" class="sd-neighbor-clear" data-action="neighbor-clear-b">清除B，回到A</button></div>' +
        '<div class="sd-neighbor-controls">' + select + '<label><span class="sd-control-label">关系类型</span><select data-neighbor-kind="filter" aria-label="按关系类型筛选"><option value="all">全部关系类型</option>' + result.kinds.map(function (k) { return '<option value="' + esc(k.code) + '"' + (cfg.kind === k.code ? ' selected' : '') + '>' + esc(k.label) + '</option>'; }).join('') + '</select></label></div>' +
        '<p class="sd-neighbor-note">当前图谱关系汇总；每条范围分别标注，不表示同时生效。当前组原位演示 ' + demos + ' / ' + rows.length + ' 人；所有分组合计演示 ' + totalDemo + ' 人、' + (cfg.demoCounts ? cfg.demoCounts.fibers : 0) + ' 条关系线（最多8条），名单完整。</p><nav class="sd-neighbor-tabs" aria-label="关系集合分组">' + tabs + '</nav>' +
        '<div class="sd-neighbor-group"><h4><span>' + esc(labels[cfg.tab]) + '</span><span>' + rows.length + ' 人</span></h4>' + (list || '<p class="sd-empty">当前筛选范围没有此类关系记录。</p>') + '</div><p class="sd-neighbor-note sd-neighbor-basis-note" role="status"></p></section>';
    }
    var problem = !aOk ? 'A不可比较：' + (aRows[0] && aRows[0].reason || (aId ? '稳定身份重复或不唯一' : '缺少稳定ID')) : cfg.result && !cfg.result.ok ? '无法比较：' + (cfg.result.reason || '人物身份或关系记录不可用。') : '选择B后，再计算两侧的一度关系集合。';
    return '<section class="sd-neighbor"><div class="sd-neighbor-head"><b>共同联系人</b><small>A · ' + esc(detail.name) + '</small></div><div class="sd-neighbor-controls">' + select + '<button type="button" class="sd-neighbor-clear" data-action="neighbor-compare"' + (cfg.bId && aOk ? '' : ' disabled') + '>比较共同联系人</button></div><p class="sd-neighbor-note" role="status">' + esc(problem) + '</p></section>';
  }
  function renderPeople() {
    var cfg = browse.people, people = index.people.filter(function (p) { return matches(p.search, cfg.query) && (cfg.filter === 'all' || p.raw.role === cfg.filter); });
    var view = pageWindow(people, cfg), total = Math.max(1, model.nCh);
    var html = view.items.map(function (p) {
      var c = p.raw || {}, first = p.chapters.length ? Math.min.apply(null, p.chapters) : 0, last = p.chapters.length ? Math.max.apply(null, p.chapters) : 0;
      var bins = Object.create(null);
      p.chapters.forEach(function (x) { var bin = p.chapters.length > TRACK_BINS ? Math.floor(x / total * TRACK_BINS) : x; if (!bins[bin]) bins[bin] = []; bins[bin].push(x); });
      var dots = Object.keys(bins).map(function (key) {
        var chapters = bins[key], x = chapters.reduce(function (a, b) { return a + b; }, 0) / chapters.length;
        var title = chapters.length === 1 ? (model.chapters[chapters[0]] || {}).name : chapters.length + ' 个有出场回目合并显示';
        return '<i data-sd-x="' + pct(x, total).toFixed(3) + '" title="' + esc(title || '') + '"></i>';
      }).join('');
      var track = p.chapters.length ? '<i class="sd-person-span" data-sd-l="' + pct(first, total).toFixed(3) + '" data-sd-w="' + Math.max(1, pct(last, total) - pct(first, total)).toFixed(3) + '"></i>' + dots : '';
      var nbEv = (p.events && p.events.length && p.events[0] && p.events[0].i != null)
        ? graph.events[p.events[0].i] : null;
      var nb = nameBudget({ name: p.name, tier: 'related',
        chapter: (nbEv && nbEv.chapter) || '' });
      return '<button type="button" class="sd-person' + (personDetail === personKey(p) ? ' is-focus' : '') + '" data-person-detail="' + esc(personKey(p)) + '" data-person-name="' + esc(p.name) + '" aria-label="' + esc((nb.full || p.name) + '，' + p.events.length + ' 个事件，点击阅读人物弧线') + '"><span class="sd-person-head"><b title="' + esc(nb.full || p.name) + '">' + esc(nb.label) + '</b><small>' + esc((c.role || c.camp || '人物') + ' · ' + p.events.length + ' 事 · ' + p.lines.length + ' 线') + '</small></span><span class="sd-person-track" title="' + p.chapters.length + ' 个有出场回目；标记按区间合并">' + track + '</span><em>阅读弧线</em></button>';
    }).join('');
    var selected = people.filter(function (p) { return personKey(p) === personDetail; })[0], detail = selected || view.items[0], detailHtml = '';
    if (detail) {
      var c = detail.raw, arcs = pageWindow(arr(c.arc).filter(function (arc) { return arc && arc.text; }), browse.arc);
      detailHtml = '<section class="sd-section sd-person-detail"><div class="sd-detail-top"><b>' + esc(detail.name) + '</b><em>材料支持的归纳</em></div>' + reviewNotes(c, 'character') +
        (c.identity ? '<p class="sd-detail-meta">' + esc(c.identity) + '</p>' : '') + (c.brief ? '<p class="sd-detail-summary">' + esc(c.brief) + '</p>' : '') +
        '<div class="sd-person-actions"><button type="button" class="sd-detail-action" data-person="' + esc(detail.name) + '">进入人物罗盘</button><button type="button" class="sd-detail-action" data-action="person-events" data-person-events="' + esc(detail.name) + '">浏览全部 ' + detail.events.length + ' 个事件</button><button type="button" class="sd-detail-action" data-action="neighbor-open">共同联系人</button></div>' +
        (browse.neighbors.origin === personKey(detail) ? renderNeighborPanel(detail) : '') +
        '<div class="sd-arc-list">' + (arcs.items.length ? arcs.items.map(function (arc) { return '<article class="sd-arc"><b>' + esc(arc.phase || '角色阶段') + '</b><p>' + esc(arc.text || '') + '</p></article>'; }).join('') : '<p class="sd-empty">材料未提供角色弧；出场跨度不等于人物成长。</p>') + '</div>' + (arcs.pages > 1 ? pager('arc', arcs) : '') + '</section>';
    }
    return '<section class="sd-section"><div class="sd-section-head"><b>人物弧线</b><span>完整人物表 · 出场区间为概览</span></div>' +
      '<div class="sd-controls">' + searchControl('people', '人物、别名、阵营或身份') + '<label class="sd-filter"><span class="sd-control-label">角色</span><select data-filter="people" aria-label="按角色类型筛选">' + options([{ value: 'all', label: '全部角色' }].concat(index.roles), cfg.filter) + '</select></label></div>' +
      '<div class="sd-people">' + (html || '<p class="sd-empty">没有匹配的人物；可清空搜索或调整筛选。</p>') + '</div>' + pager('people', view) + '</section>' + detailHtml;
  }
  function renderEvidence() {
    var selected = state.focus && String(state.focus).indexOf('e:') === 0 ? +String(state.focus).slice(2) : null;
    var cfg = browse.evidence, all = evidenceItems(), view = pageWindow(all, cfg);
    var basisCounts = { '原文': 0, '有引文未核验': 0, '归纳': 0, '推导': 0, '未核验': 0 }, anchoredEvents = 0;
    index.events.forEach(function (x) { var b = { verified: '原文', quoted: '有引文未核验', synthesis: '归纳', inference: '推导', unverified: '未核验' }[x.status.code] || '未核验'; basisCounts[b]++; if (x.status.anchored) anchoredEvents++; });
    var anchored = graph.events.length ? Math.round(anchoredEvents / graph.events.length * 100) : null;
    var posCounts = g.CLSkyPositionLabel ? g.CLSkyPositionLabel.countEvents(graph.events)
      : (function () { var c = { total: graph.events.length, exact_quote: 0, legacy_interval: 0, unresolved: 0, conflicted: 0, unknown: 0 }; return c; })();
    var posProgress = g.CLSkyPositionLabel ? g.CLSkyPositionLabel.progress(posCounts) : null;
    var selectedRecord = all.filter(function (x) { return x.i === selected; })[0], record = selectedRecord || view.items[0];
    var detail = record && record.e, detailIndex = record && record.i;
    var quotes = evidenceText(detail), ch = detailIndex != null ? chapterFor(detailIndex) : null, basis = eventBasis(detail);
    var quoteView = pageWindow(quotes, browse.quotes);
    var positionControl = detail ? '<button type="button" class="sd-detail-action sd-position-explain-action" data-action="position-explain" data-event-index="' + detailIndex + '">' + (m103.open && m103.eventIndex === detailIndex ? '收起位置说明' : '位置说明') + '</button>' : '';
    var positionReturn = detail && m103.returnSnapshot && m103.returnSnapshot.graph === graph && m103.returnSnapshot.boundaryIndex === detailIndex
      ? '<button type="button" class="sd-detail-action sd-position-return" data-action="position-return">返回位置说明</button>' : '';
    var positionExplanation = detail && m103.open && m103.eventIndex === detailIndex ? renderPositionExplanation(detailIndex) : '';
    var provenance = [{ value: 'all', label: '全部依据' }, { value: 'verified', label: '原文已核验' }, { value: 'quoted', label: '有引文未核验' }, { value: 'synthesis', label: '归纳' }, { value: 'inference', label: '推导' }, { value: 'unverified', label: '未核验' }];
    var controls = '<div class="sd-controls">' + searchControl('evidence', '事件、章节、人物或引文') + '<label class="sd-filter"><span class="sd-control-label">依据</span><select data-filter="evidence" aria-label="按证据核验状态筛选">' + options(provenance, cfg.filter) + '</select></label><label class="sd-filter"><span class="sd-control-label">类型</span><select data-event-kind="evidence" aria-label="按剧情点类型筛选">' + options([{ value: 'all', label: '全部类型' }].concat(index.kinds), cfg.kind) + '</select></label><label class="sd-filter"><span class="sd-control-label">顺序</span><select data-order="evidence" aria-label="事件排序">' + options([{ value: 'time', label: '叙事顺序' }, { value: 'key', label: '关键事件优先' }], cfg.order) + '</select></label></div>';
    if (cfg.person) controls += '<button type="button" class="sd-detail-action sd-filter-person" data-action="clear-person">' + esc(cfg.person) + ' 的事件 · 清除人物筛选 ×</button>';
    return '<section class="sd-section"><div class="sd-section-head"><b>证据层</b><span>结构判断必须能回到材料</span></div><div class="sd-evidence-summary" aria-label="证据覆盖摘要"><div class="sd-evidence-summary-top"><b>原文锚定 <em>' + esc(anchored == null ? '—' : anchored + '%') + '</em></b><span>' + esc(anchoredEvents + ' / ' + graph.events.length + ' 个事件有已核验引文') + '</span></div><div class="sd-evidence-meter" aria-hidden="true"><i data-sd-w="' + (anchored == null ? 0 : anchored) + '"></i></div><div class="sd-evidence-counts"><span class="is-source">原文已核验 ' + basisCounts['原文'] + '</span><span class="is-unknown">有引文未核验 ' + basisCounts['有引文未核验'] + '</span><span class="is-summary">归纳 ' + basisCounts['归纳'] + '</span><span class="is-derived">推导 ' + basisCounts['推导'] + '</span><span class="is-unknown">未核验 ' + basisCounts['未核验'] + '</span></div><p class="sd-evidence-note">引文核验说明来源位置一致；归纳、推导及人物评分仍需依据情节判断。</p></div>' +
      (posProgress ? '<div class="sd-position-summary" aria-label="事件位置定位摘要"><div class="sd-evidence-summary-top"><b>' + esc(posProgress.title) + ' <em>' + esc(posProgress.locatedPercent == null ? '—' : posProgress.locatedPercent + '%') + '</em></b><span>' + esc(posProgress.summary) + '</span></div><div class="sd-evidence-meter is-position" aria-hidden="true"><i data-sd-w="' + (posProgress.locatedPercent == null ? 0 : posProgress.locatedPercent) + '"></i></div><div class="sd-evidence-counts"><span class="is-source">精确 ' + posProgress.exact + '</span><span class="is-summary">区间 ' + posProgress.bounded + '</span><span class="is-unknown">位置未知 ' + posProgress.unknown + '</span>' + (posProgress.conflict ? '<span class="is-derived">来源冲突 ' + posProgress.conflict + '</span>' : '') + '</div><p class="sd-evidence-note">' + esc(posProgress.semanticNote) + '位置未知的事件仍可阅读原文，但不应被当成发生在某个确定时间点。</p></div>' : '') + '</section>' +
      '<section class="sd-section"><div class="sd-section-head"><b>事件档案</b><span>完整记录 · 每页 ' + PAGE_SIZE + ' 条</span></div>' + controls + '<div class="sd-event-list">' + (view.items.length ? view.items.map(function (x) { return eventRow(x.i, x.i === detailIndex); }).join('') : '<p class="sd-empty">没有匹配的事件；可清空搜索或调整筛选。</p>') + '</div>' + pager('evidence', view) + '</section>' +
      (detail ? (function () { var dpos = eventPosition(detail); return '<section class="sd-section"><div class="sd-evidence-detail ' + basisClass(basis) + ' pos-' + esc(dpos.tone) + '"><div class="sd-detail-top"><b>' + esc(detail.title || detail.summary || '未命名剧情点') + '</b><em>' + esc(basis) + '</em></div><p class="sd-detail-meta">' + esc((ch ? ch.name : detail.chapter || '章节未提供') + ' · ' + (detail.kind || '剧情点') + (arr(detail.characters).length ? ' · ' + detail.characters.join('、') : '')) + '</p><p class="sd-position-line" data-position="' + esc(dpos.code) + '"><span class="sd-position-tag">' + esc(positionBadge(detail).text) + '</span> ' + esc(dpos.label) + ' · ' + esc(dpos.hint) + '</p>' + positionControl + positionReturn + positionExplanation + (function () { var dc = eventClaim(detail); var cn2 = claimNote(detail); return '<p class="sd-claim-line" data-claim="' + esc(dc.code) + '"><span class="sd-claim-tag">' + esc(claimBadge(detail).text) + '</span> ' + esc(dc.label) + ' · ' + esc(dc.hint) + (cn2 ? ' —— ' + esc(cn2) : '') + '</p>'; })() + ''+ (detail.summary ? '<p class="sd-detail-summary">' + esc(detail.summary) + '</p>' : '') + reviewNotes(detail, 'event') + (quotes.length ? quoteView.items.map(function (q) { return quoteRow(detail, q); }).join('') + (quoteView.pages > 1 ? pager('quotes', quoteView) : '') : '<p class="sd-empty">该记录未提供原文引句。</p>') + '<button type="button" class="sd-detail-action" data-event-index="' + detailIndex + '">在星盘定位此事件</button></div></section>'; })() : '');
  }
  function stateReadingTitle(row) {
    var item = row.raw;
    return row.kind === 'transition' ? (item.character || '人物待核') + ' · ' + item.before + ' → ' + item.after :
      row.kind === 'knowledge' ? (item.character || '人物待核') + ' · ' + item.text :
      row.kind === 'turning' ? (item.ownerName || '主体待核') + ' · ' + (item.summary || '转折声明') : (item.character || '人物待核') + ' · ' + (item.summary || '状态记录');
  }
  function stateBasisLabel(item) {
    var code = item && (item.basisCode || item.basis);
    var basis = code === 'explicit' || code === '原文明确' || code === '原文' ? '原文依据明确' : code === 'inference' || code === 'inferred' || code === '推导' ? '事件推导' : code === 'synthesis' || code === '归纳' ? '材料归纳' : code ? '依据类型未识别' : '依据类型未提供';
    var review = item && item.claimVerified === true && item.semanticStatus === 'reviewed' ? '语义已复核' :
      item && (item.claimStatus === 'unreviewed' || item.claimVerified === false || item.semanticStatus === 'unreviewed') ? '语义判断待核' : '语义状态未提供 · 待核';
    return basis + ' · ' + review;
  }
  function stateReadingEvidence(item) {
    var out = [];
    [item].concat(arr(item.attributes)).forEach(function (owner) {
      allEvidenceText(owner).forEach(function (quote) { out.push({ owner: owner, quote: quote }); });
    });
    return out;
  }
  function renderStates() {
    var reading = model.narrative && model.narrative.characterReading || {}, stats = reading.stats || {}, cfg = browse.states;
    var filtered = index.stateRows.filter(function (row) {
      return matches(row.search, cfg.query) && (cfg.filter === 'all' || row.status.code === cfg.filter) &&
        (cfg.eventIndex == null || row.raw.eventIndex === cfg.eventIndex) && (cfg.characterId == null || row.raw.characterId === cfg.characterId) &&
        (cfg.kind === 'all' || row.kind === cfg.kind || cfg.kind === 'gap' && row.kind === 'knowledge' && row.raw.isGap || cfg.kind === 'unresolved' && !row.raw.resolved);
    });
    var view = pageWindow(filtered, cfg), selected = view.items.filter(function (row) { return row.key === cfg.selected; })[0] || view.items[0];
    var list = view.items.map(function (row) {
      var item = row.raw, e = item.eventIndex == null ? null : graph.events[item.eventIndex], chosen = selected && selected.key === row.key;
      var sb = stateTransitionBadge(item);
      var kb = row.kind === 'knowledge' ? knowledgeBadge(item) : null;
      var saria = STATE_KINDS[row.kind] + '：' + stateReadingTitle(row) + '，'
        + stateTransition(item).label + '，' + sb.facetLabel + '，' + sb.reversibilityLabel
        + '，' + row.status.label + '，阅读完整记录';
      return '<button type="button" class="sd-event sd-state-row sd-state-' + esc(sb.tone) + ' ' + basisClass(row.status.label) + (chosen ? ' is-focus' : '') + '" data-action="select-state" data-state-key="' + esc(row.key) + '" data-state-nature="' + esc(sb.code) + '"' + (chosen ? ' aria-current="true"' : '') + ' aria-label="' + esc(saria) + '"><span class="sd-event-mark"></span><span class="sd-event-copy"><b>' + esc(clip(stateReadingTitle(row), 38)) + '</b><small>' + esc(STATE_KINDS[row.kind] + ' · ' + (item.chapter || e && e.chapter || '章节未提供') + (item.resolved ? '' : ' · 引用待核')) + '</small></span><span class="sd-state-nature" title="' + esc(stateTransition(item).hint) + '">' + esc(sb.text) + '</span>' + (kb ? '<span class="sd-knowledge-badge knowledge-' + esc(kb.tone) + '" data-knowledge="' + esc(kb.code) + '" title="' + esc(knowledgeView(item).hint) + '">' + esc(kb.text) + '</span>' : '') + '<em class="sd-state-facet">' + esc(sb.facetLabel + ' · ' + sb.reversibilityLabel) + '</em><em>' + esc(row.status.label) + '</em></button>';
    }).join('');
    var detail = '';
    if (selected) {
      if (cfg.detailKey !== selected.key) { cfg.detailKey = selected.key; browse.stateQuotes.page = 0; browse.stateAttributes.page = 0; }
      var item = selected.raw, event = item.eventIndex == null ? null : graph.events[item.eventIndex];
      var fields = fact(item.ownerType === 'storyline' ? '故事线' : '人物', item.ownerName || item.character) + fact('章节', item.chapter || event && event.chapter);
      if (selected.kind === 'transition') fields += fact('变化前（声明）', item.before) + fact('变化后（声明）', item.after) + fact('变化说明', item.description);
      else if (selected.kind === 'knowledge') fields += fact('知情内容', item.text) + fact('知情状态', statusLabel('knowledge', item.status));
      else fields += fact(selected.kind === 'turning' ? '转折说明' : '此刻状态', item.summary);
      var quotes = pageWindow(stateReadingEvidence(item), browse.stateQuotes), attrs = pageWindow(arr(item.attributes), browse.stateAttributes);
      var reference = event ? '<button type="button" class="sd-detail-action" data-action="select-event" data-event-index="' + item.eventIndex + '">阅读关联事件 · ' + esc(event.title || event.chapter || '事件') + '</button>' : '<span class="sd-reference-unavailable">事件引用缺失、重复或冲突；未自动补配。</span>';
      detail = '<article class="sd-mechanics-card sd-state-detail"><div class="sd-detail-top"><b>' + esc(stateReadingTitle(selected)) + '</b><em>' + esc(selected.status.label) + '</em></div><p class="sd-evidence-note">' + esc(stateBasisLabel(item)) + '。' + (selected.kind === 'knowledge' ? '人物信念、知情声明与客观真相分别阅读；未列出的事实不表示人物不知。' : selected.kind === 'transition' ? '变化前后由材料明确提供；时间相邻不构成变化原因。' : '状态与转折均来自现有声明，不按出场次数推断成长。') + '</p><div class="sd-fact-grid">' + fields + '</div>' +
        (attrs.items.length ? '<div class="sd-attributes">' + attrs.items.map(function (attribute) { return '<section class="sd-attribute"><div class="sd-fact-grid">' + fact(attribute.name || '属性', attribute.value) + '</div></section>'; }).join('') + (attrs.pages > 1 ? pager('stateAttributes', attrs) : '') + '</div>' : '') +
        '<div class="sd-evidence-links">' + reference + '</div>' + (!item.characterResolved && selected.kind !== 'turning' || item.ownerResolved === false ? '<p class="sd-reference-unavailable">所属人物或故事线引用待核；保留原声明供检查。</p>' : '') +
        (quotes.items.length ? '<div class="sd-mechanic-quotes">' + quotes.items.map(function (q) { return quoteRow(q.owner, q.quote); }).join('') + (quotes.pages > 1 ? pager('stateQuotes', quotes) : '') + '</div>' : '<p class="sd-empty">这条声明未提供原文引句。</p>') + '</article>';
    }
    var kinds = [{ value: 'all', label: '全部声明' }, { value: 'snapshot', label: '人物状态' }, { value: 'transition', label: '变化前后' }, { value: 'knowledge', label: '知情声明' }, { value: 'gap', label: '明确不知' }, { value: 'turning', label: '转折声明' }, { value: 'unresolved', label: '引用待核' }];
    var provenance = [{ value: 'all', label: '全部依据' }, { value: 'verified', label: '原文已核验' }, { value: 'quoted', label: '有引文未核验' }, { value: 'synthesis', label: '归纳' }, { value: 'inference', label: '推导' }, { value: 'unverified', label: '未核验' }];
    return '<section class="sd-section sd-state-reading"><div class="sd-section-head"><b>状态与视野</b><span>人物当时知道什么、处于何种状态</span></div><p class="sd-evidence-note">仅呈现已提供的状态、变化与知情声明。缺少记录表示尚未分析；不表示人物没有变化、全书没有信息差。</p>' +
      '<div class="sd-stats">' + stat('状态记录', stats.states || 0) + stat('变化声明', stats.transitions || 0) + stat('知情声明', stats.knowledge || 0) + stat('转折声明', stats.turningPoints || 0) + '</div>' +
      '<div class="sd-controls">' + searchControl('states', '人物、状态、转折或原文引句') + '<label class="sd-filter"><span class="sd-control-label">类型</span><select data-state-kind="states" aria-label="按状态与视野类型筛选">' + options(kinds, cfg.kind) + '</select></label><label class="sd-filter"><span class="sd-control-label">依据</span><select data-filter="states" aria-label="按状态声明依据筛选">' + options(provenance, cfg.filter) + '</select></label></div>' +
      (cfg.eventIndex != null || cfg.characterId != null ? '<button type="button" class="sd-detail-action" data-action="clear-state-scope">限定' + (cfg.eventIndex != null ? '当前事件' : '') + (cfg.characterId != null ? ' · 当前人物' : '') + ' · 查看全部声明 ×</button>' : '') + '<div class="sd-event-list">' +
      (list || '<p class="sd-empty">' + (index.stateRows.length ? '没有匹配的声明；可调整搜索与筛选。' : '这次分析尚未提供可读的状态、知情或转折声明；未从人物评分、事件标签或同场关系补造。') + '</p>') +
      (!(stats.knowledge || 0) ? '<p class="sd-evidence-note sd-knowledge-gap-note" role="status">知情面为空的原因：精读产物里已有认知结论（管线顶层 knowledgeGaps），但它们尚未进入当前图谱版本，且模型读取的 characters[].knowledge 字段在已发布数据里不存在。这是「尚未接线」，不代表人物没有知情差异。</p>' : '') + '</div>' + (index.stateRows.length ? pager('states', view) : '') + detail + '</section>';
  }
  function archNodes() { var narrative = model.narrative || {}, architecture = narrative.architecture || {}; return arr(architecture.nodes); }
  function archNodeLabel(i) { var nodes = archNodes(), n = nodes[i], e = n && graph.events[n.index]; return e ? e.title || e.summary || '未命名事件' : n && n.title || '未解析事件'; }
  function archNodeMeta(i) {
    var nodes = archNodes(), n = nodes[i], e = n && graph.events[n.index], ch = n && n.chapter || e && e.chapter || '';
    return (ch ? ch + ' · ' : '') + (n && n.kind || e && e.kind || '剧情点');
  }
  function archNodeButton(i, label, cls) {
    var nodes = archNodes();
    if (i == null || !nodes[i]) return '<span class="sd-reference-unavailable">' + esc(label) + '未能匹配事件</span>';
    var title = archNodeLabel(i);
    return '<button type="button" class="sd-causal-node ' + (cls || '') + '" data-action="select-event" data-event-index="' + nodes[i].index + '" aria-label="' + esc('阅读' + label + '：' + title) + '"><b>' + esc(title) + '</b><small>' + esc(archNodeMeta(i)) + '</small></button>';
  }
  function declarationLink(item) {
    var layer = item.ownerType === 'causeEdge' ? 'causeEdges' : item.ownerType === 'clue' ? 'clues' : null;
    if (!layer || item.ownerId == null) return '';
    var matching = arr(index.layers[layer]).filter(function (row) { return row.recordId === str(item.ownerId); });
    return matching.length === 1 ? '<button type="button" class="sd-detail-action" data-action="read-record" data-record-layer="' + layer + '" data-record-id="' + esc(item.ownerId) + '">阅读声明与全部依据</button>' : '<span class="sd-reference-unavailable">声明 ID 不唯一，请在情节证据列表逐条查阅。</span>';
  }
  function edgeBasis(item) {
    return item.basisCode === 'explicit' ? '原文明确声明 · 判断待核' : item.basisCode === 'inference' ? '事件推导 · 判断待核' : item.basisCode === 'synthesis' ? '材料归纳 · 判断待核' : '未核验声明';
  }
  function stableEventIdentity(eventIndex, book) {
    var event = book && arr(book.events)[eventIndex], id = eventIdentity(event);
    return id != null ? arr(book.events).filter(function (e) { return eventIdentity(e) === id; }).length === 1 : false;
  }
  function m88Stop() { if (m88.tween && g.CLSkyMotion) g.CLSkyMotion.cancelAll('m88'); m88.tween = null; m88.request++; }
  function m88Close() { m88Stop(); m88.sourceRequest++; m88.recordId = null; m88.source = null; m88.sourceStatus = null; m88.snapshot = null; m88.entrySnapshot = null; }
  function m88AlignHeading(echo, focus) {
    var body = root && root.querySelector('#skyDeconBody'), heading = echo && echo.querySelector('.sd-section-head');
    if (!body || !heading || !echo) return;
    if (focus && echo.focus) echo.focus({ preventScroll: true });
    body.scrollTop += heading.getBoundingClientRect().top - body.getBoundingClientRect().top - 8;
  }
  function m88FocusEntry() { var echo = root && root.querySelector('[data-foreshadow-echo]'); if (echo) m88AlignHeading(echo, true); }
  function m88EnsureGuideVisible() {
    var echo = root && root.querySelector('[data-foreshadow-echo]'), body = root && root.querySelector('#skyDeconBody');
    if (!echo || !body) return;
    var target = echo.querySelector('.sd-echo-axis') || echo.querySelector('.sd-echo-cards'), br = body.getBoundingClientRect(), tr = target && target.getBoundingClientRect();
    if (!target || tr.top < br.top || tr.bottom > br.bottom) m88AlignHeading(echo, false);
  }
  function m88ValidCursor(p) {
    var current = p && p.eventIndex;
    return Number.isInteger(current) && graph && graph.events[current] && stableEventIdentity(current, graph) && eventIdentity(graph.events[current]) === str(p.eventId);
  }
  function m88RememberReading(p) {
    if (!m88ValidCursor(p)) return false;
    var current = p.eventIndex, allowed = null, journey = !!(p.journey && Array.isArray(p.stops)), label = '截至当前阅读事件', order = null;
    if (journey) {
      allowed = Object.create(null);
      p.stops.slice(0, Math.max(-1, Number(p.stopIndex)) + 1).forEach(function (s) { if (s && Number.isInteger(s.eventIndex)) allowed[s.eventIndex] = true; });
      if (!allowed[current]) { allowed = Object.create(null); allowed[current] = true; }
      label += ' · 旅程已到停点';
    } else {
      var ev = graph.events[current];
      order = ev && ev.rawOrderKnown === false ? null : ev && ev.rawOrderKnown === true ? (typeof ev.rawOrder === 'number' ? ev.rawOrder : null) : m88.orderByIndex[current];
    }
    m88.lastReading = { graph: graph, current: current, eventId: str(p.eventId), allowed: allowed, order: order, journey: journey, label: label };
    return true;
  }
  function m88Range() {
    var p = g.CLSky && g.CLSky.playerState ? g.CLSky.playerState() : null, current = p && p.eventIndex;
    if (m88ValidCursor(p)) m88RememberReading(p);
    var hasReading = m88.lastReading && m88.lastReading.graph === graph;
    if (m88.scope === 'published') return { p: p, current: null, allowed: null, order: null, label: hasReading ? '已发布图谱范围（本次查看全部记录）' : '已发布图谱范围（无阅读进度）' };
    if (p && Number.isInteger(current) && graph && graph.events[current] && !m88ValidCursor(p) && !hasReading) return { p: p, current: current, allowed: null, order: null, label: '截至当前事件（身份待核，仅显示当前事件）', identityUnknown: true };
    if (hasReading && !m88ValidCursor(p)) return { p: p, current: m88.lastReading.current, allowed: m88.lastReading.allowed, order: m88.lastReading.order, label: '阅读定位暂不可用，保留上一位置 · ' + m88.lastReading.label, stale: true, journey: m88.lastReading.journey };
    if (!m88ValidCursor(p)) return { p: p, current: null, allowed: null, order: null, label: '已发布图谱范围（无可用阅读位置）' };
    return { p: p, current: m88.lastReading.current, allowed: m88.lastReading.allowed, order: m88.lastReading.order, label: m88.lastReading.label, journey: m88.lastReading.journey };
  }
  function m88EventVisible(i, range) {
    if (i == null || !graph || !graph.events[i]) return false;
    if (range.current == null) return true;
    if (range.identityUnknown) return i === range.current;
    if (range.allowed) return !!range.allowed[i];
    if (range.order == null) return i === range.current;
    var ev = graph.events[i], order = ev && ev.rawOrderKnown === false ? null : ev && ev.rawOrderKnown === true ? (typeof ev.rawOrder === 'number' ? ev.rawOrder : null) : m88.orderByIndex[i];
    return order != null && order <= range.order;
  }
  function m88Visibility(rec, range) {
    var seed = rec && rec.seedIndex, payoff = rec && rec.payoffIndex;
    return { seed: m88EventVisible(seed, range), payoff: rec && rec.stage === 'resolved' && m88EventVisible(payoff, range) };
  }
  function m88Chapter(i) {
    var e = graph && graph.events[i], ch = chapterFor(i), raw = e && str(e.chapter).trim();
    if (!raw || !ch || !ch.name || ch.name !== raw || /未定位|未知|未提供/.test(raw)) return null;
    var matches = arr(model && model.chapters).filter(function (x) { return x && x.name === raw; });
    return matches.length === 1 ? { name: raw, index: index && index.eventChapter ? index.eventChapter[i] : null } : null;
  }
  function m88CanFollow() { var p = g.CLSky && g.CLSky.playerState && g.CLSky.playerState(); return m88ValidCursor(p) || !!(m88.lastReading && m88.lastReading.graph === graph); }
  function m88ScopeKey() { var p = g.CLSky && g.CLSky.playerCursor ? g.CLSky.playerCursor() : null; return [m88.graphEpoch, m88.scope, p && p.eventIndex, p && p.eventId, p && p.position, p && p.stage, p && p.journeyId, p && p.journeyLayer, p && p.complete].join('|'); }
  function m88Unwatch() { if (m88.hookOff) m88.hookOff(); m88.hookOff = null; m88.hookedScene = null; }
  function m88Watch() {
    var scene = g.CLApp && g.CLApp.scene && g.CLApp.scene();
    if (!scene || !scene.registerFrameHook || !g.CLSky || !g.CLSky.playerCursor || scene === m88.hookedScene) return;
    if (m88.hookOff) m88.hookOff(); m88.hookedScene = scene;
    m88.hookOff = scene.registerFrameHook(function () {
      if (!state.open || ['foreshadow','causal'].indexOf(state.mode) < 0) return;
      var key = m88ScopeKey(); if (key !== m88.scopeKey) { m88.scopeKey = key; m88Stop(); m88.sourceRequest++; m88.source = null; m88.sourceStatus = m88.snapshot && m88.snapshot.view === 'source' ? 'unavailable:阅读范围已变化，原文请求已取消。' : null; render(); }
    });
  }
  function animateM88() {
    var stage = root && root.querySelector('[data-foreshadow-echo]'); if (!stage) return;
    m88EnsureGuideVisible();
    m88Stop(); var request = ++m88.request;
    if (g.CLSky && g.CLSky.stop) g.CLSky.stop();
    function buttons(playing) { var stop = root && root.querySelector('[data-action="foreshadow-echo-stop"]'); if (stop) stop.disabled = !playing; }
    function paint(v) { if (request !== m88.request || !stage.isConnected) return; m88.progress = v; stage.style.setProperty('--sd-echo-progress', String(v)); stage.setAttribute('data-phase', v >= 1 ? 'settled' : 'opening'); }
    if ((g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) || !g.CLSkyMotion || (g.CLSkyMotion.reduced && g.CLSkyMotion.reduced()) || forkLowTier()) { paint(1); buttons(false); return; }
    paint(0); buttons(true); m88.tween = g.CLSkyMotion.tween({ from: 0, to: 1, dur: .96, ease: function (v) { return v; }, tag: 'm88', onUpdate: paint, onDone: function () { if (request === m88.request) { paint(1); m88.tween = null; buttons(false); } } });
  }
  function openM88(id) {
    var recs = arr(model && model.narrative && model.narrative.foreshadowLifecycles).filter(function (r) { return str(r.ownerId || r.recordId || r.id) === str(id); });
    var clues = arr(index && index.layers && index.layers.clues).filter(function (r) { return str(r.recordId) === str(id); });
    if (recs.length !== 1 || clues.length !== 1 || (recs[0].ownerType && clues[0].ownerType && recs[0].ownerType !== clues[0].ownerType)) return false;
    if (g.CLSky && g.CLSky.playerState) m88RememberReading(g.CLSky.playerState());
    var selectedScope = m88.scope;
    m88Close(); if (g.CLSky && g.CLSky.stop) g.CLSky.stop();
    var entryBody = root.querySelector('#skyDeconBody');
    m88.recordId = str(id); m88.scope = selectedScope === 'published' ? 'published' : 'reading'; m88.scopeKey = m88ScopeKey();
    m88.entrySnapshot = { graph: graph, scope: m88.scope, query: browse.foreshadow.query, filter: browse.foreshadow.filter, page: browse.foreshadow.page, scrollTop: entryBody ? entryBody.scrollTop : 0, recordId: m88.recordId, focus: { attr: 'data-foreshadow-id', value: m88.recordId, action: 'foreshadow-echo-open' } };
    m88.snapshot = { graph: graph, scope: m88.scope, query: browse.foreshadow.query, filter: browse.foreshadow.filter, page: browse.foreshadow.page, scrollTop: root.querySelector('#skyDeconBody').scrollTop, recordId: m88.recordId, view: 'echo' };
    state.restore = null; render(); m88FocusEntry(); animateM88(); return true;
  }
  function closeM88() {
    var snap = m88.entrySnapshot; m88Close();
    if (!snap || snap.graph !== graph) { state.mode = 'foreshadow'; render(); return false; }
    browse.foreshadow.query = snap.query; browse.foreshadow.filter = snap.filter; browse.foreshadow.page = snap.page;
    state.mode = 'foreshadow'; state.focus = null; state.restore = snap.focus; render();
    var body = root && root.querySelector('#skyDeconBody'); if (body) body.scrollTop = snap.scrollTop;
    return true;
  }
  function returnM88() {
    var snap = m88.snapshot; m88Stop(); m88.sourceRequest++; m88.source = null; m88.sourceStatus = null;
    if (!snap || snap.graph !== graph) { m88Close(); state.mode = 'foreshadow'; render(); return false; }
    browse.foreshadow.query = snap.query; browse.foreshadow.filter = snap.filter; browse.foreshadow.page = snap.page;
    var view = snap.view; snap.view = 'echo'; state.mode = 'foreshadow'; state.focus = null;
    state.restore = view === 'event' ? { attr: 'data-echo-side', value: snap.side, action: 'foreshadow-echo-event' } : view === 'source' ? { attr: 'data-echo-side', value: snap.side, action: 'foreshadow-echo-read' } : { attr: 'data-foreshadow-id', value: snap.recordId, action: 'foreshadow-echo-open' };
    render(); var body = root.querySelector('#skyDeconBody'); if (body) body.scrollTop = snap.scrollTop; return true;
  }
  function causalNodeOrder(node, book) {
    var event = node && book && arr(book.events)[node.index];
    if (event && event.rawOrderKnown === false) return null;
    if (event && event.rawOrderKnown === true) return typeof event.rawOrder === 'number' && isFinite(event.rawOrder) ? event.rawOrder : null;
    return node && typeof node.order === 'number' && isFinite(node.order) ? node.order : null;
  }
  function analyzeCausalFork(source, edges, nodes, book, scopedEdges) {
    var adj = [], incoming = [], colors = [], stack = [], hasCycle = false, unknownOrder = false, orderSeen = Object.create(null), scope = arr(scopedEdges || edges).filter(function (edge) { return edge && nodes[edge.source] && nodes[edge.target] && !causalType(edge).mustNotBeCausalEdge; });
    for (var i = 0; i < nodes.length; i++) { adj[i] = []; incoming[i] = []; }
    arr(edges).forEach(function (edge) {
      if (!edge || !nodes[edge.source] || !nodes[edge.target] || causalType(edge).mustNotBeCausalEdge) return;
      incoming[edge.target].push(edge);
    });
    scope.forEach(function (edge) { adj[edge.source].push(edge); });
    var outgoing = scope.filter(function (edge) { return edge && edge.source === source && nodes[edge.target] && !causalType(edge).mustNotBeCausalEdge; });
    if (!nodes[source]) return { outgoing: [], cycle: false, unknownOrder: true, staticReason: '源事件未能唯一定位，静态说明。', shared: [], directTargets: [] };
    var sourceOrder = causalNodeOrder(nodes[source], book);
    if (sourceOrder == null) unknownOrder = true;
    else orderSeen[sourceOrder] = source;
    colors[source] = 1; stack.push({ node: source, next: 0 });
    while (stack.length) {
      var top = stack[stack.length - 1], edgesFromNode = adj[top.node] || [];
      if (top.next >= edgesFromNode.length) { colors[top.node] = 2; stack.pop(); continue; }
      var traversedEdge = edgesFromNode[top.next++], next = traversedEdge.target, sourceOrder = causalNodeOrder(nodes[top.node], book), order = causalNodeOrder(nodes[next], book);
      if (order == null || sourceOrder == null || order <= sourceOrder || (orderSeen[order] != null && orderSeen[order] !== next)) unknownOrder = true;
      else orderSeen[order] = next;
      if (colors[next] === 1) { hasCycle = true; continue; }
      if (!colors[next]) { colors[next] = 1; stack.push({ node: next, next: 0 }); }
    }
    var directTargets = [], directSeen = Object.create(null);
    outgoing.forEach(function (e) { if (!directSeen[e.target]) { directSeen[e.target] = true; directTargets.push(e.target); } });
    var shared = [];
    if (directTargets.length > 1) {
      var common = null;
      directTargets.forEach(function (target) {
        var found = Object.create(null); (adj[target] || []).forEach(function (edge) { found[edge.target] = true; });
        if (common == null) common = found; else Object.keys(common).forEach(function (key) { if (!found[key]) delete common[key]; });
      });
      Object.keys(common || {}).forEach(function (key) {
        var id = +key, node = nodes[id], prerequisites = incoming[id] || [];
        if (node && id !== source && stableEventIdentity(node.index, book)) shared.push({ index: id, extraPrerequisite: prerequisites.some(function (edge) { return directTargets.indexOf(edge.source) < 0; }), hiddenPrerequisite: prerequisites.some(function (edge) { return directTargets.indexOf(edge.source) < 0 && scope.indexOf(edge) < 0; }) });
      });
    }
    return { outgoing: outgoing, cycle: hasCycle, unknownOrder: unknownOrder,
      staticReason: hasCycle ? '当前可达因果网络含循环，静态说明。' : unknownOrder ? '节点顺序缺失或冲突，静态说明。' : '', shared: shared, directTargets: directTargets };
  }
  function forkLowTier() {
    var scene = g.CLApp && g.CLApp.scene && g.CLApp.scene(), core = scene && scene.core && scene.core(), tokens = g.CLSkyTokens;
    return !!(core && core.getDegrade && tokens && tokens.tierOf && tokens.tierOf(core.getDegrade()) === 'low');
  }
  function stopCausalForkLayout() {
    if (causalFork.layoutObserver) causalFork.layoutObserver.disconnect();
    if (causalFork.layoutFallback) g.removeEventListener('resize', causalFork.layoutFallback);
    causalFork.layoutObserver = null; causalFork.layoutFallback = null; causalFork.layoutRoot = null;
  }
  function updateCausalForkLayout(section) {
    if (!section || !section.isConnected) return;
    var svg = section.querySelector('.sd-fork-svg'); if (!svg) return;
    var svgRect = svg.getBoundingClientRect(), width = svgRect.width, height = svgRect.height;
    if (!(width > 0 && height > 0)) return;
    var cards = Object.create(null), cardRects = [];
    Array.prototype.forEach.call(section.querySelectorAll('[data-fork-node][data-node-index]'), function (card) {
      var kind = card.getAttribute('data-fork-node'), nodeIndex = card.getAttribute('data-node-index'), rect = card.getBoundingClientRect();
      cards[kind + ':' + nodeIndex] = rect; cardRects.push({ kind: kind, index: nodeIndex, rect: rect });
    });
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('preserveAspectRatio', 'none');
    function crosses(x1, y1, x2, y2, obstacle) {
      var left = obstacle.left - svgRect.left + 1, right = obstacle.right - svgRect.left - 1;
      var top = obstacle.top - svgRect.top + 1, bottom = obstacle.bottom - svgRect.top - 1;
      var dx = x2 - x1, dy = y2 - y1, lo = 0, hi = 1;
      function clip(p, q) {
        if (Math.abs(p) < .0001) return q >= 0;
        var t = q / p;
        if (p < 0) { if (t > hi) return false; if (t > lo) lo = t; }
        else { if (t < lo) return false; if (t < hi) hi = t; }
        return true;
      }
      if (!(left < right && top < bottom)) return false;
      return clip(-dx, x1 - left) && clip(dx, right - x1) && clip(-dy, y1 - top) && clip(dy, bottom - y1) && lo <= hi && hi >= 0 && lo <= 1;
    }
    function curveCrosses(x1, y1, c1x, c1y, c2x, c2y, x2, y2, obstacles) {
      var px = x1, py = y1;
      for (var i = 1; i <= 32; i++) {
        var t = i / 32, u = 1 - t;
        var x = u*u*u*x1 + 3*u*u*t*c1x + 3*u*t*t*c2x + t*t*t*x2;
        var y = u*u*u*y1 + 3*u*u*t*c1y + 3*u*t*t*c2y + t*t*t*y2;
        for (var j = 0; j < obstacles.length; j++) if (crosses(px, py, x, y, obstacles[j].rect)) return true;
        px = x; py = y;
      }
      return false;
    }
    function pathFor(rectA, rectB, direction, fromKind, fromIndex, toKind, toIndex) {
      var ax, ay, bx, by, dx, dy, obstacles = cardRects.filter(function (item) { return !(item.kind === fromKind && item.index === fromIndex) && !(item.kind === toKind && item.index === toIndex); });
      if (direction === 'merge' && rectB.top - rectA.bottom >= 28) {
        ax = (rectA.left + rectA.right) / 2 - svgRect.left; ay = rectA.bottom - svgRect.top + 2;
        bx = (rectB.left + rectB.right) / 2 - svgRect.left; by = rectB.top - svgRect.top - 12;
        dy = Math.max(8, (by - ay) * .38);
        if (!curveCrosses(ax, ay, ax, ay + dy, bx, by - dy, bx, by, obstacles)) return 'M ' + ax + ' ' + ay + ' C ' + ax + ' ' + (ay + dy) + ', ' + bx + ' ' + (by - dy) + ', ' + bx + ' ' + by;
        var gutter = rectA.left - svgRect.left - 20;
        var sx = rectA.left - svgRect.left - 2, sy = (rectA.top + rectA.bottom) / 2 - svgRect.top;
        var ey = rectB.top - svgRect.top - 12;
        var gutterBlocked = obstacles.some(function (item) { return crosses(gutter, sy + 8, gutter, ey, item.rect); });
        var exitBlocked = curveCrosses(sx, sy, sx - 8, sy, gutter, sy, gutter, sy + 8, obstacles);
        if (!gutterBlocked && !exitBlocked && gutter >= 0 && ey > sy) {
          return 'M ' + sx + ' ' + sy + ' C ' + (sx - 8) + ' ' + sy + ', ' + gutter + ' ' + sy + ', ' + gutter + ' ' + (sy + 8) + ' L ' + gutter + ' ' + ey;
        }
      }
      if (rectB.left - rectA.right >= 28) {
        ax = rectA.right - svgRect.left + 2; ay = (rectA.top + rectA.bottom) / 2 - svgRect.top;
        bx = rectB.left - svgRect.left - 12; by = (rectB.top + rectB.bottom) / 2 - svgRect.top;
        dx = Math.max(8, (bx - ax) * .38); return 'M ' + ax + ' ' + ay + ' C ' + (ax + dx) + ' ' + ay + ', ' + (bx - dx) + ' ' + by + ', ' + bx + ' ' + by;
      }
      if (rectB.top - rectA.bottom >= 28) {
        ax = (rectA.left + rectA.right) / 2 - svgRect.left; ay = rectA.bottom - svgRect.top + 2;
        bx = (rectB.left + rectB.right) / 2 - svgRect.left; by = rectB.top - svgRect.top - 12;
        dy = Math.max(8, (by - ay) * .38); return 'M ' + ax + ' ' + ay + ' C ' + ax + ' ' + (ay + dy) + ', ' + bx + ' ' + (by - dy) + ', ' + bx + ' ' + by;
      }
      if (rectA.left - rectB.right >= 28) {
        ax = rectA.left - svgRect.left - 2; ay = (rectA.top + rectA.bottom) / 2 - svgRect.top;
        bx = rectB.right - svgRect.left + 12; by = (rectB.top + rectB.bottom) / 2 - svgRect.top;
        dx = Math.max(8, (ax - bx) * .38); return 'M ' + ax + ' ' + ay + ' C ' + (ax - dx) + ' ' + ay + ', ' + (bx + dx) + ' ' + by + ', ' + bx + ' ' + by;
      }
      return '';
    }
    Array.prototype.forEach.call(section.querySelectorAll('.sd-fork-path[data-from-kind][data-from-index][data-to-kind][data-to-index]'), function (path) {
      var a = cards[path.getAttribute('data-from-kind') + ':' + path.getAttribute('data-from-index')], b = cards[path.getAttribute('data-to-kind') + ':' + path.getAttribute('data-to-index')];
      if (!a || !b) return;
      var d = pathFor(a, b, path.getAttribute('data-path-kind'), path.getAttribute('data-from-kind'), path.getAttribute('data-from-index'), path.getAttribute('data-to-kind'), path.getAttribute('data-to-index')); if (d) path.setAttribute('d', d);
    });
    Array.prototype.forEach.call(section.querySelectorAll('.sd-fork-reveal[data-from-kind][data-from-index][data-to-kind][data-to-index]'), function (path) {
      var a = cards[path.getAttribute('data-from-kind') + ':' + path.getAttribute('data-from-index')], b = cards[path.getAttribute('data-to-kind') + ':' + path.getAttribute('data-to-index')];
      if (!a || !b) return;
      var d = pathFor(a, b, path.getAttribute('data-path-kind'), path.getAttribute('data-from-kind'), path.getAttribute('data-from-index'), path.getAttribute('data-to-kind'), path.getAttribute('data-to-index')); if (d) path.setAttribute('d', d);
    });
    setForkProgress(section, causalFork.progress);
  }
  function bindCausalForkLayout(body) {
    stopCausalForkLayout();
    var section = body && body.querySelector('.sd-causal-fork'); if (!section) return;
    causalFork.layoutRoot = section;
    updateCausalForkLayout(section);
    if (g.ResizeObserver) {
      causalFork.layoutObserver = new g.ResizeObserver(function () { updateCausalForkLayout(section); });
      causalFork.layoutObserver.observe(section);
      Array.prototype.forEach.call(section.querySelectorAll('[data-fork-node]'), function (node) { causalFork.layoutObserver.observe(node); });
    } else {
      causalFork.layoutFallback = function () { updateCausalForkLayout(section); };
      g.addEventListener('resize', causalFork.layoutFallback);
    }
  }
  function setForkProgress(el, progress) {
    if (!el || !el.isConnected) return;
    causalFork.progress = progress;
    el.style.setProperty('--sd-fork-progress', String(progress));
    el.style.setProperty('--sd-label-progress', String(progress <= .57 ? 0 : progress >= .81 ? 1 : (progress - .57) / .24));
    el.style.setProperty('--sd-merge-progress', String(progress < .81 ? 0 : (progress - .81) / .19));
    var source = el.querySelector('.sd-fork-source'); if (source) source.style.setProperty('--sd-source-progress', String(Math.min(1, progress / .14)));
    Array.prototype.forEach.call(el.querySelectorAll('.sd-fork-path'), function (path) {
      var kind = path.getAttribute('data-path-kind'), foreground = kind === 'merge' ? progress >= .81 && progress < 1 : progress >= .14 && progress < .57;
      path.classList.toggle('is-foreground', foreground);
    });
    Array.prototype.forEach.call(el.querySelectorAll('.sd-fork-reveal[data-path-animate="true"]'), function (path) {
      var length = path.getTotalLength ? path.getTotalLength() : 0, local = progress < .14 ? 0 : progress < .57 ? (progress - .14) / .43 : progress < .81 ? 1 : (progress - .81) / .19;
      if (path.getAttribute('data-path-kind') === 'merge') local = progress < .81 ? 0 : (progress - .81) / .19;
      else if (progress >= .81) local = 1;
      path.style.setProperty('--sd-path-length', length + 'px'); path.style.setProperty('--sd-path-offset', (length * (1 - Math.max(0, Math.min(1, local)))) + 'px');
    });
  }
  function stopCausalForkTween() { if (causalFork.tween && g.CLSkyMotion) g.CLSkyMotion.cancelAll('m87'); causalFork.tween = null; }
  function setForkButtonsPlaying(playing) { var el = root && root.querySelector('.sd-causal-fork-stop'); if (el) el.disabled = !playing; }
  function animateCausalFork() {
    stopCausalForkTween(); var el = root && root.querySelector('.sd-causal-fork'); if (!el) return;
    setForkProgress(el, 1); setForkButtonsPlaying(false);
    if ((g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) || (g.CLSkyMotion && g.CLSkyMotion.reduced && g.CLSkyMotion.reduced()) || forkLowTier() || !g.CLSkyMotion || causalFork.staticReason) return;
    setForkButtonsPlaying(true); setForkProgress(el, 0);
    causalFork.tween = g.CLSkyMotion.tween({ from: 0, to: 1, dur: .84, ease: function (v) { return v; }, tag: 'm87', onUpdate: function (v) { setForkProgress(el, v); }, onDone: function () { causalFork.tween = null; setForkButtonsPlaying(false); } });
  }
  function openCausalFork(eventIndex) {
    var nodes = archNodes(), hits = [];
    nodes.forEach(function (n, i) { if (n && n.index === eventIndex) hits.push(i); });
    if (hits.length !== 1 || !graph.events[eventIndex] || !stableEventIdentity(eventIndex, graph)) return;
    var architecture = (model.narrative || {}).architecture || {}, cfg = browse.causal;
    var eligibleScope = arr(architecture.edges).filter(function (edge) { return (cfg.filter === 'all' || edge.basisCode === cfg.filter) && matches(searchText([archNodeLabel(edge.source), archNodeLabel(edge.target), archNodeMeta(edge.source), archNodeMeta(edge.target), edge.description, edge.summary, edge.quote, edge.basis]), cfg.query); });
    var analysis = analyzeCausalFork(hits[0], arr(architecture.edges), nodes, graph, eligibleScope);
    if (!analysis.outgoing.length) return;
    causalFork.staticReason = analysis.staticReason;
    causalFork.source = eventIndex; causalFork.returnTo = null; causalFork.entrySnapshot = causalForkSnapshot(); causalFork.request += 1;
    state.restore = { attr: 'data-event-index', value: String(eventIndex), action: 'causal-fork-open' }; render();
    var detail = root && root.querySelector('.sd-causal-fork'); if (detail) {
      detail.setAttribute('tabindex', '-1'); var body = root.querySelector('#skyDeconBody'), heading = detail.querySelector('.sd-section-head');
      if (body && heading) body.scrollTop += heading.getBoundingClientRect().top - body.getBoundingClientRect().top - 8;
      detail.focus({ preventScroll: true }); updateCausalForkLayout(detail);
    }
    animateCausalFork();
  }
  function causalForkSnapshot(triggerAction, triggerValue) { return { graph: graph, source: causalFork.source, scrollTop: root.querySelector('#skyDeconBody').scrollTop, query: browse.causal.query, filter: browse.causal.filter, page: browse.causal.page, forkPage: browse.causalFork.page, triggerAction: triggerAction || null, triggerValue: triggerValue == null ? null : String(triggerValue) }; }
  function returnCausalFork() {
    stopCausalForkTween();
    var snap = causalFork.returnTo && causalFork.returnTo.graph === graph ? causalFork.returnTo : causalFork.entrySnapshot && causalFork.entrySnapshot.graph === graph ? causalFork.entrySnapshot : null;
    if (snap) {
      var fromReading = !!causalFork.returnTo;
      causalFork.source = fromReading ? snap.source : null; causalFork.returnTo = null;
      browse.causal.query = snap.query; browse.causal.filter = snap.filter; browse.causal.page = snap.page; browse.causalFork.page = snap.forkPage;
      state.mode = 'causal'; state.restore = null;
      if (!fromReading) causalFork.entrySnapshot = null;
      render();
      var body = root && root.querySelector('#skyDeconBody'), target = null;
      if (body) {
        body.scrollTop = snap.scrollTop;
        updateCausalForkLayout(body.querySelector('.sd-causal-fork'));
        if (fromReading && snap.triggerAction === 'causal-fork-event' && snap.triggerValue != null) {
          Array.prototype.some.call(body.querySelectorAll('[data-action="causal-fork-event"][data-event-index]'), function (el) { if (el.getAttribute('data-event-index') === snap.triggerValue) { target = el; return true; } return false; });
        } else if (fromReading && snap.triggerAction === 'causal-fork-record' && snap.triggerValue != null) {
          Array.prototype.some.call(body.querySelectorAll('[data-action="causal-fork-record"][data-record-id]'), function (el) { if (el.getAttribute('data-record-id') === snap.triggerValue) { target = el; return true; } return false; });
        } else {
          Array.prototype.some.call(body.querySelectorAll('[data-action="causal-fork-open"][data-event-index]'), function (el) { if (el.getAttribute('data-event-index') === String(snap.source)) { target = el; return true; } return false; });
        }
        if (!target && fromReading) Array.prototype.some.call(body.querySelectorAll('[data-action="causal-fork-open"][data-event-index]'), function (el) { if (el.getAttribute('data-event-index') === String(snap.source)) { target = el; return true; } return false; });
        if (target && target.focus) target.focus({ preventScroll: true });
      }
    }
    else { causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; render(); }
  }
  function renderCausal() {
    var narrative = model.narrative || {}, architecture = narrative.architecture || {}, edges = arr(architecture.edges),
      nodes = arr(architecture.nodes), unresolved = arr(architecture.unresolved), stats = architecture.stats || {};
    var unresolvedScope = m88Range(), unrestricted = unresolvedScope.current == null && !unresolvedScope.allowed;
    if (!unrestricted) unresolved = unresolved.map(function (item) {
      if (item.ownerType !== 'clue') return item;
      var matches = arr(narrative.foreshadowLifecycles).filter(function (rec) { return rec.ownerType === 'clue' && str(rec.ownerId) === str(item.ownerId); });
      if (matches.length !== 1) return null;
      var rec = matches[0], vis = m88Visibility(rec, unresolvedScope);
      if (!vis.seed) return null;
      if (vis.payoff) return item;
      return { ownerType: 'clue', ownerId: item.ownerId, m88Foreshadow: true, reason: item.reason };
    }).filter(Boolean);
    var cfg = browse.causal, basisValues = [{ value: 'all', label: '全部依据' }, { value: 'explicit', label: '原文明确声明' }, { value: 'inference', label: '事件推导' }, { value: 'synthesis', label: '材料归纳' }, { value: 'unverified', label: '未核验' }];
    var nodeLabel = archNodeLabel, nodeMeta = archNodeMeta, nodeButton = archNodeButton;
    var filteredEdges = edges.filter(function (edge) {
      return (cfg.filter === 'all' || edge.basisCode === cfg.filter) && matches(searchText([nodeLabel(edge.source), nodeLabel(edge.target), nodeMeta(edge.source), nodeMeta(edge.target), edge.description, edge.summary, edge.quote, edge.basis]), cfg.query);
    });
    var edgeView = pageWindow(filteredEdges, cfg);
    var forkIndex = causalFork.source == null ? -1 : nodes.map(function (n) { return n && n.index; }).indexOf(causalFork.source);
    var forkAnalysis = forkIndex < 0 ? { outgoing: [], shared: [], staticReason: '' } : analyzeCausalFork(forkIndex, edges, nodes, graph, filteredEdges);
    var forkEdges = forkAnalysis.outgoing;
    var forkView = pageWindow(forkEdges, browse.causalFork);
    var forkRows = forkView.items.map(function (edge) {
      var ct = causalType(edge), target = nodes[edge.target], targetEventIndex = target && target.index;
      var targetButton = targetEventIndex != null && stableEventIdentity(targetEventIndex, graph)
        ? '<button type="button" class="sd-causal-node" data-action="causal-fork-event" data-event-index="' + targetEventIndex + '"><b>' + esc(nodeLabel(edge.target)) + '</b><small>' + esc(nodeMeta(edge.target)) + '</small></button>'
        : '<span class="sd-reference-unavailable">终点身份不唯一或未解析，不能跳转。</span>';
      var recordMatches = edge.ownerId == null ? [] : arr(index && index.layers && index.layers.causeEdges).filter(function (row) { return row.recordId === str(edge.ownerId); });
      var recordLink = recordMatches.length === 1 ? '<button type="button" class="sd-detail-action" data-action="causal-fork-record" data-record-layer="causeEdges" data-record-id="' + esc(edge.ownerId) + '">阅读声明与全部依据</button>' : '<span class="sd-reference-unavailable">声明身份缺失或不唯一，不能跳转。</span>';
      return '<li class="sd-fork-edge' + (edge.basisCode === 'inference' ? ' is-inference' : '') + '" data-record-id="' + esc(edge.ownerId == null ? '' : edge.ownerId) + '" data-causal-type="' + esc(ct.code) + '" data-basis="' + esc(edge.basisCode) + '"><span class="sd-fork-direction">' + esc(nodeLabel(edge.source)) + ' →</span>' + targetButton + '<em>' + esc(edgeBasis(edge)) + (edge.basisCode === 'inference' ? ' · 推断' : '') + '</em><em>' + esc(ct.label) + '</em><p>' + esc(edge.description || edge.summary || '未提供因果说明') + '</p>' + recordLink + (ct.hint ? '<small>' + esc(ct.hint) + '</small>' : '') + '</li>';
    }).join('');
    var animatedEdges = forkEdges.slice(0, 3), topologyTargets = [], topologySeen = Object.create(null);
    animatedEdges.forEach(function (edge) { if (!topologySeen[edge.target]) { topologySeen[edge.target] = true; topologyTargets.push(edge.target); } });
    var commonTarget = forkEdges.length <= 3 && forkAnalysis.shared.length === 1 ? forkAnalysis.shared[0] : null;
    function svgPath(edge, kind, animated, order) {
      var fromKind = kind === 'merge' ? 'branch' : 'source', toKind = kind === 'merge' ? 'common' : 'branch';
      var attrs = ' data-from-kind="' + fromKind + '" data-from-index="' + edge.source + '" data-to-kind="' + toKind + '" data-to-index="' + edge.target + '" data-path-kind="' + kind + '"';
      var maskId = 'm87-reveal-' + kind + '-' + order, d = 'M 0 0';
      return (animated ? '<defs><mask id="' + maskId + '" maskUnits="userSpaceOnUse"><path class="sd-fork-reveal"' + attrs + ' data-path-animate="true" d="' + d + '"></path></mask></defs>' : '') + '<path class="sd-fork-path ' + (kind === 'merge' ? 'is-merge' : '') + (edge.basisCode === 'inference' ? ' is-inference' : '') + '"' + attrs + (animated ? ' mask="url(#' + maskId + ')"' : '') + ' d="' + d + '" marker-end="url(#m87-arrow)"></path>';
    }
    var branchPaths = animatedEdges.map(function (edge, i) { return svgPath(edge, 'branch', true, i); }).join('');
    var mergeEdges = commonTarget ? forkAnalysis.directTargets.map(function (from) { return filteredEdges.filter(function (edge) { return edge.source === from && edge.target === commonTarget.index && !causalType(edge).mustNotBeCausalEdge; })[0]; }).filter(Boolean) : [];
    if (commonTarget && mergeEdges.length !== forkAnalysis.directTargets.length) { commonTarget = null; mergeEdges = []; }
    var mergePaths = commonTarget ? mergeEdges.slice(0, 3).map(function (edge, i) { return svgPath(edge, 'merge', true, i); }).join('') : '';
    var mergeCopy = commonTarget ? '<p class="sd-fork-merge">已记录的直接共同目标：<b>' + esc(nodeLabel(commonTarget.index)) + '</b>' + (commonTarget.extraPrerequisite ? ' · 另有前提' + (commonTarget.hiddenPrerequisite ? '（另有当前筛选外的已记录前提）' : '') : '') + '</p>' : forkAnalysis.shared.length > 1 ? '<p class="sd-fork-merge">发现多个直接共同目标：' + forkAnalysis.shared.map(function (x) { return esc(nodeLabel(x.index)); }).join('、') + '；并列列示，不择一汇合。</p>' : '<p class="sd-fork-merge">当前筛选的已记录方向未显示直接共同目标。</p>';
    var topologyMarkup = topologyTargets.map(function (target) { var inferred = animatedEdges.some(function (e) { return e.target === target && e.basisCode === 'inference'; }); return '<li data-fork-node="branch" data-node-index="' + target + '" class="' + (inferred ? 'is-inference' : '') + '"><b>' + esc(nodeLabel(target)) + '</b><small>' + esc(nodeMeta(target)) + (inferred ? ' · 推断' : '') + '</small></li>'; }).join('');
    var excludedCount = edges.filter(function (e) { return e.source === forkIndex && (causalType(e).mustNotBeCausalEdge || e.source === e.target); }).length;
    var forkMarkup = forkIndex >= 0 ? '<section class="sd-causal-fork" aria-label="因果分叉说明"><div class="sd-section-head"><b>当前筛选中的已记录方向</b><span class="sd-causal-fork-actions"><button type="button" class="sd-detail-action sd-causal-fork-stop" data-action="causal-fork-stop" disabled>停止</button><button type="button" class="sd-detail-action" data-action="causal-fork-replay">重播说明</button><button type="button" class="sd-detail-action" data-action="causal-fork-return">返回因果网络</button></span></div><p>当前范围 ' + forkEdges.length + ' 条记录，演示 ' + Math.min(3, forkEdges.length) + '/' + forkEdges.length + '；箭头表示事件声明方向，布局不代表剧情时间。' + esc(forkAnalysis.staticReason) + (excludedCount ? '排除非因果类型与自循环 ' + excludedCount + ' 条。' : '') + '</p><div class="sd-fork-topology' + (commonTarget ? ' has-common-target' : '') + '"><b class="sd-fork-source" data-fork-node="source" data-node-index="' + forkIndex + '">' + esc(nodeLabel(forkIndex)) + '</b><svg class="sd-fork-svg" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="m87-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z"></path></marker></defs>' + branchPaths + mergePaths + '</svg><ul class="sd-fork-targets">' + topologyMarkup + '</ul>' + (commonTarget ? '<b class="sd-fork-common" data-fork-node="common" data-node-index="' + commonTarget.index + '">' + esc(nodeLabel(commonTarget.index)) + '<small>' + esc(nodeMeta(commonTarget.index)) + '</small></b>' : '') + '</div>' + mergeCopy + '<ol class="sd-fork-list">' + (forkRows || '<li class="sd-empty">当前筛选中无可读分叉声明。</li>') + '</ol>' + (forkView.pages > 1 ? pager('causalFork', forkView) : '') + '</section>' : '';
    var edgeRows = edgeView.items.map(function (edge) {
      if (!nodes[edge.source] || !nodes[edge.target]) return '';
      var basis = edgeBasis(edge), ct = causalType(edge), cb = causalTypeBadge(edge);
      var aria = '因果声明：' + nodeLabel(edge.source) + ' → ' + nodeLabel(edge.target) + '，' + basis + '，' + ct.label
        + (ct.mustNotBeCausalEdge ? '（' + ct.hint + '）' : '');
      return '<article class="sd-causal-edge causal-' + esc(ct.tone) + '" role="listitem" data-causal-type="' + esc(ct.code) + '" aria-label="' + esc(aria) + '">' +
        nodeButton(edge.source, '前因', 'is-cause-src') + (!ct.mustNotBeCausalEdge && edge.source !== edge.target && graph.events[nodes[edge.source].index] && stableEventIdentity(nodes[edge.source].index, graph) ? '<button type="button" class="sd-fork-entry" data-action="causal-fork-open" data-event-index="' + nodes[edge.source].index + '" aria-label="解释这个事件的分叉">解释分叉</button>' : '') + '<span class="sd-causal-arrow" aria-hidden="true">→</span>' + nodeButton(edge.target, '后果', 'is-cause-dst') +
        '<em class="sd-causal-basis">' + esc(basis) + '</em><em class="sd-causal-type" title="' + esc(ct.hint) + '">' + esc(cb.text) + '</em><div class="sd-causal-evidence">' +
        (edge.description || edge.summary ? '<p>' + esc(edge.description || edge.summary) + '</p>' : '<p class="sd-evidence-note">未提供因果说明</p>') +
        (edge.quote ? quoteRow(edge, edge.quote) : '<p class="sd-evidence-note">未提供因果主引句</p>') + declarationLink(edge) + '</div></article>';
    }).join('');
    var currentRange = m88Range(), allPayoffs = unrestricted ? arr(narrative.foreshadowPayoffs) : arr(narrative.foreshadowPayoffs).map(function (pair) {
      var nodes = archNodes(), seedNode = nodes[pair.source], targetNode = nodes[pair.target], seedIndex = seedNode && seedNode.index, targetIndex = targetNode && targetNode.index;
      var vis = m88Visibility({ seedIndex: seedIndex, payoffIndex: targetIndex, stage: pair.resolved ? 'resolved' : pair.pending ? 'pending' : 'broken' }, currentRange);
      if (!vis.seed) return null;
      if (pair.resolved && !vis.payoff) return { source: pair.source, target: null, pending: false, resolved: false, m88Hidden: true, basisCode: pair.basisCode };
      return pair;
    }).filter(Boolean);
    var payoffView = pageWindow(allPayoffs, browse.payoffs);
    var payoffs = payoffView.items.map(function (pair) {
      return '<li><div class="sd-detail-top"><b>' + esc(pair.m88Hidden ? '伏笔声明' : pair.name || '伏笔与兑现声明') + '</b><em>' + esc(pair.m88Hidden ? '兑现尚未公开' : pair.pending ? '尚未声明兑现' : pair.resolved ? '事件引用已关联' : '引用或顺序待核') + '</em></div>' +
        (pair.summary && !pair.m88Hidden ? '<p class="sd-causal-description">' + esc(pair.summary) + '</p>' : '') +
        '<div class="sd-causal-pair">' + nodeButton(pair.source, '埋设', 'is-cause-src') + '<span class="sd-causal-arrow" aria-hidden="true">' + (pair.resolved ? '↝' : '…') + '</span>' +
        (pair.m88Hidden ? '<span class="sd-reference-unavailable">兑现尚未公开。</span>' : pair.pending ? '<span class="sd-reference-unavailable">当前记录未提供兑现；不能据此判断全书未回收。</span>' : nodeButton(pair.target, '兑现', 'is-cause-dst')) + '</div>' +
        '<em class="sd-causal-basis">' + esc(edgeBasis(pair)) + '</em>' + (pair.m88Hidden ? '' : declarationLink(pair)) + '</li>';
    }).join('');
    function boundary(items, type) {
      var view = pageWindow(items, browse[type]);
      return view.items.map(function (i) { return '<button type="button" class="sd-detail-action" data-action="select-event" data-event-index="' + i + '">' + esc(nodeLabel(i)) + '</button>'; }).join('') + (view.pages > 1 ? pager(type, view) : '') || '<span class="sd-empty">暂无</span>';
    }
    var unresolvedView = pageWindow(unresolved, browse.unresolved);
    var unresolvedRows = unresolvedView.items.map(function (x) {
      return x.m88Foreshadow ? '<li><b>伏笔声明 · 引用待核</b><p>兑现端引用按当前阅读范围隐藏。</p></li>' : '<li><b>' + esc(statusLabel('causalReason', x.reason)) + '</b><p>' + esc((x.sourceRef == null ? '未提供前项' : x.sourceRef) + ' → ' + (x.targetRef == null ? '未提供后项' : x.targetRef)) + '</p>' + declarationLink(x) + '</li>';
    }).join('');
    return '<section class="sd-section sd-causal"><div class="sd-section-head"><b>因果网络</b><span>声明方向与判断依据分别呈现</span></div>' +
      '<p class="sd-evidence-note">时间先后与同场不会自动变成因果。事件可进入证据层；声明可阅读原文与完整依据。引句定位不等于因果判断成立。</p>' +
      '<div class="sd-stats sd-causal-stats">' + stat('因果声明', edges.length) + stat('涉及事件', stats.linkedEvents || 0) + stat('根节点', arr(architecture.roots).length) + stat('叶节点', arr(architecture.leaves).length) + stat('未解析引用', unresolved.length) + '</div>' +
      '<div class="sd-controls">' + searchControl('causal', '事件、因果说明或引句') + '<label class="sd-filter"><span class="sd-control-label">依据</span><select data-filter="causal" aria-label="按因果依据筛选">' + options(basisValues, cfg.filter) + '</select></label></div>' +
      forkMarkup + '<div class="sd-causal-map" role="list" aria-label="因果声明">' + (edgeRows || '<p class="sd-empty">当前筛选没有可关联的因果声明。未声明不代表不存在因果。</p>') + '</div>' + (edges.length ? pager('causal', edgeView) : '') +
      (payoffs ? '<div class="sd-causal-sub"><div class="sd-section-head"><b>伏笔与兑现</b><span>已关联与待回收分别呈现</span></div><ul class="sd-causal-list">' + payoffs + '</ul>' + (payoffView.pages > 1 ? pager('payoffs', payoffView) : '') + '</div>' : '') +
      '<div class="sd-causal-sub"><div class="sd-section-head"><b>已记录的传播边界</b></div><p class="sd-evidence-note">根与叶仅代表当前已关联声明，没有记录前因或后果不等于全书中不存在。</p><div class="sd-causal-boundary"><div><small>根节点</small>' + boundary(arr(architecture.roots), 'causalRoots') + '</div><div><small>叶节点</small>' + boundary(arr(architecture.leaves), 'causalLeaves') + '</div></div></div>' +
      (unresolvedRows ? '<section class="sd-causal-sub sd-unresolved"><div class="sd-section-head"><b>未解析引用 · ' + unresolved.length + '</b></div><ul>' + unresolvedRows + '</ul>' + (unresolvedView.pages > 1 ? pager('unresolved', unresolvedView) : '') + '</section>' : '') + '</section>';
  }
  function renderForeshadow() {
    var narrative = model.narrative || {}, records = arr(narrative.foreshadowLifecycles);
    var fstats = narrative.architecture && narrative.architecture.stats && narrative.architecture.stats.foreshadow || {};
    var cfg = browse.foreshadow, nodeButton = archNodeButton, range = m88Range(), unrestricted = range.current == null && !range.allowed, projections = Object.create(null);
    function projection(rec) { var key = str(rec.ownerId || rec.recordId || rec.id), vis = m88Visibility(rec, range); if (unrestricted) vis = { seed: true, payoff: rec.stage === 'resolved' && rec.payoffIndex != null }; var stage = !vis.seed ? null : rec.stage === 'resolved' && !vis.payoff ? 'hidden-payoff' : rec.stage; projections[key] = { visible: vis, stage: stage }; return projections[key]; }
    var visibleRecords = records.filter(function (rec) { return projection(rec).visible.seed; });
    var projectedStats = { resolved: 0, pending: 0, broken: 0, conflicted: 0, 'hidden-payoff': 0 };
    visibleRecords.forEach(function (rec) { var p = projections[str(rec.ownerId || rec.recordId || rec.id)]; if (projectedStats[p.stage] != null) projectedStats[p.stage]++; });
    var filtered = visibleRecords.filter(function (rec) {
      var p = projections[str(rec.ownerId || rec.recordId || rec.id)], restricted = p.stage === 'hidden-payoff';
      var clue = m88Clue(rec), publicText = restricted ? [rec.seedTitle, rec.seedChapter, clue && clue.clueType, rec.basis, clue && clue.seedQuote] : [rec.name, rec.summary, rec.seedTitle, rec.payoffTitle, rec.seedChapter, rec.payoffChapter, rec.basis, rec.quote, clue && clue.seedQuote, clue && clue.payoffQuote, clue && clue.clueType, rec.declaredStatus];
      return (cfg.filter === 'all' || p.stage === cfg.filter) && matches(searchText(publicText), cfg.query);
    });
    var view = pageWindow(filtered, cfg);
    var stageOptions = [{ value: 'all', label: '全部阶段' }], seen = Object.create(null);
    visibleRecords.forEach(function (rec) { var stage = projections[str(rec.ownerId || rec.recordId || rec.id)].stage; if (!seen[stage]) { seen[stage] = true; stageOptions.push({ value: stage, label: stage === 'hidden-payoff' ? '兑现尚未公开' : statusLabel('foreshadow', stage) }); } });
    ['resolved', 'pending', 'broken', 'conflicted'].forEach(function (code) { if (!seen[code]) stageOptions.push({ value: code, label: statusLabel('foreshadow', code) }); });
    var cards = view.items.map(function (rec) {
      var proj = projections[str(rec.ownerId || rec.recordId || rec.id)], vis = proj.visible, effectiveStage = proj.stage, restricted = effectiveStage === 'hidden-payoff';
      var stageLabel = restricted ? '兑现尚未公开' : statusLabel('foreshadow', effectiveStage);
      var seed = rec.seedIndex != null ? nodeButton(rec.seedIndex, '埋设', 'is-cause-src') : '<span class="sd-reference-unavailable">埋设事件引用缺失或不唯一；未自动补配。</span>';
      var payoff = vis.payoff ? nodeButton(rec.payoffIndex, '兑现', 'is-cause-dst') : restricted ? '<span class="sd-reference-unavailable">兑现尚未公开。</span>' :
        rec.stage === 'pending' ? '<span class="sd-reference-unavailable">当前记录尚未声明兑现事件；不能据此判断全书未回收。</span>' :
        rec.stage === 'conflicted' ? '<span class="sd-reference-unavailable">同一声明身份出现多条记录；未选择其中任何一条。</span>' :
        '<span class="sd-reference-unavailable">兑现事件引用缺失、重复或顺序待核；未自动补配。</span>';
      var steps = rec.seedIndex != null ? '<p class="sd-fore-steps"><i' + (vis.payoff ? ' class="is-on"' : '') + '>已埋伏</i><span aria-hidden="true">→</span><i class="' + (vis.payoff ? 'is-on' : rec.stage === 'pending' || restricted ? 'is-waiting' : 'is-broken') + '">' + esc(stageLabel) + '</i></p>' : '';
      var declared = rec.declaredStatus ? ' · 声明状态：<span class="sd-status-text" data-status-code="' + esc(String(rec.declaredStatus)) + '">' + esc(statusLabel('declared', rec.declaredStatus)) + (statusHint('declared', rec.declaredStatus) ? '（' + esc(statusHint('declared', rec.declaredStatus)) + '）' : '') + '</span>' : '';
      var lp2 = foreshadowStageBadge(rec);
      var safeName = restricted ? (rec.seedTitle || '伏笔声明') : (rec.name || clip(rec.summary, 24) || '未命名伏笔声明');
      var foreAria = '伏笔生命周期：' + safeName + '，' + stageLabel + (restricted ? '' : '，八阶段：' + lp2.label + '，' + edgeBasis(rec) + (foreshadowStage(rec).isDefect ? '（' + foreshadowStage(rec).hint + '）' : ''));
      var ownerId = rec.ownerId || rec.recordId || rec.id, recordMatches = ownerId == null ? [] : arr(index && index.layers && index.layers.clues).filter(function (r) { return str(r.recordId) === str(ownerId); });
      var echoButton = recordMatches.length === 1 ? '<button type="button" class="sd-detail-action" data-action="foreshadow-echo-open" data-foreshadow-id="' + esc(ownerId) + '">解释伏笔回响</button>' : '';
      return '<article class="sd-causal-edge sd-fore-card fore-' + esc(restricted ? 'pending' : lp2.tone) + '" role="listitem" data-stage="' + esc(effectiveStage) + '" data-fore-stage="' + esc(restricted ? 'pending' : lp2.code) + '"' + (!restricted && rec.declaredStatus ? ' data-status-code="' + esc(String(rec.declaredStatus)) + '"' : '') + ' aria-label="' + esc(foreAria) + '">' +
        '<div class="sd-detail-top"><b>' + esc(safeName) + '</b><em class="sd-fore-stage is-' + esc(restricted ? 'pending' : effectiveStage) + '" data-stage="' + esc(effectiveStage) + '">' + esc(stageLabel) + '</em>' + (restricted ? '' : '<em class="sd-fore-lifecycle" data-fore-stage="' + esc(lp2.code) + '" title="' + esc(lp2.hint) + '">' + esc(lp2.text) + '</em>') + '</div>' +
        (!restricted && rec.summary ? '<p class="sd-causal-description">' + esc(rec.summary) + '</p>' : '') + steps +
        '<div class="sd-causal-pair">' + seed + '<span class="sd-causal-arrow" aria-hidden="true">' + (vis.payoff ? '↝' : '…') + '</span>' + payoff + '</div>' +
        (restricted ? '' : '<em class="sd-causal-basis">' + esc(edgeBasis(rec)) + declared + '</em>') + (unrestricted || vis.payoff ? declarationLink(rec) : '') + echoButton + (m88.recordId === str(ownerId) ? renderM88(rec, vis) : '') + '</article>';
    }).join('');
    var selectedRecords = m88.recordId ? records.filter(function (rec) { return str(rec.ownerId || rec.recordId || rec.id) === str(m88.recordId); }) : [];
    var detachedEcho = '';
    if (selectedRecords.length === 1) {
      var selectedRec = selectedRecords[0], selectedVis = m88Visibility(selectedRec, range);
      var selectedOnPage = view.items.some(function (rec) { return str(rec.ownerId || rec.recordId || rec.id) === str(m88.recordId); });
      if (selectedVis.seed && !selectedOnPage) detachedEcho = renderM88(selectedRec, selectedVis);
    }
    var empty = records.length ? '当前筛选没有匹配的伏笔声明；可清空搜索或调整阶段筛选。' :
      Object.prototype.hasOwnProperty.call(graph, 'clues') ? '这次分析尚未提供可确认的伏笔生命周期记录；没有声明不代表全书不存在伏笔。' :
        '这次分析尚未提供伏笔层；无法据此判断全书有无伏笔结构。';
    return '<section class="sd-section sd-causal sd-foreshadow"><div class="sd-section-head"><b>伏笔生命周期</b><span>每条声明从埋伏到兑现或断裂</span></div>' +
      '<p class="sd-evidence-note">仅呈现显式伏笔声明。事件先后与同场不会自动产生埋伏或兑现判断；埋设与兑现事件可回到证据层阅读原文。没有声明不代表不存在伏笔。</p>' +
      '<p class="sd-echo-scope"><span role="status">' + esc(range.label) + '</span>' + (m88CanFollow() ? '<button type="button" class="sd-detail-action" data-action="foreshadow-echo-scope">' + (m88.scope === 'published' ? '跟随阅读位置' : '查看已发布记录') + '</button>' : '') + '</p>' +
      '<div class="sd-stats sd-causal-stats">' + stat('伏笔声明', visibleRecords.length) + stat('已兑现', projectedStats.resolved) + stat('待回收', projectedStats.pending) + stat('断裂或冲突', projectedStats.broken + projectedStats.conflicted) + (projectedStats['hidden-payoff'] ? stat('兑现尚未公开', projectedStats['hidden-payoff']) : '') + '</div>' +
      '<div class="sd-controls">' + searchControl('foreshadow', '伏笔名、埋设或兑现事件、引文') + '<label class="sd-filter"><span class="sd-control-label">阶段</span><select data-filter="foreshadow" aria-label="按伏笔生命周期阶段筛选">' + options(stageOptions, cfg.filter) + '</select></label></div>' +
      '<div class="sd-causal-map" role="list" aria-label="伏笔生命周期 · ' + esc(range.label) + '">' + (cards || '<p class="sd-empty">' + esc(empty) + '</p>') + '</div>' + (visibleRecords.length ? pager('foreshadow', view) : '') + detachedEcho + '</section>';
  }

  function structureReturnMarkup() {
    return '<div class="sd-structure-return"><button type="button" class="sd-detail-action" data-action="structure-return">← 返回结构总览</button></div>';
  }
  function render() {
    if (!root || !state.ready) return;
    if (state.open && ['foreshadow','causal'].indexOf(state.mode) >= 0) { m88Watch(); m88.scopeKey = m88ScopeKey(); } else m88Unwatch();
    if (state.mode !== 'overview' && m84.open) cancelM84(true);
    var focusedEvent = state.mode === 'evidence' && state.focus && String(state.focus).indexOf('e:') === 0 ? +String(state.focus).slice(2) : null;
    if ((m103.open && (state.mode !== 'evidence' || focusedEvent !== m103.eventIndex)) ||
        (m103.returnSnapshot && (state.mode !== 'evidence' || focusedEvent !== m103.returnSnapshot.boundaryIndex))) clearM103();
    var title = state.mode === 'lines' ? '故事线骨架' : state.mode === 'people' ? '人物弧线' : state.mode === 'evidence' ? '原文证据层' : state.mode === 'mechanics' ? '情节证据' : state.mode === 'causal' ? '因果网络' : state.mode === 'foreshadow' ? '伏笔生命周期' : state.mode === 'states' ? '状态与视野' : '全书叙事 DNA';
    setText('skyDeconTitle', title);
    setText('skyDeconSub', state.mode === 'overview' ? '从全书形状进入故事线、人物和证据' : state.mode === 'lines' ? '完整线名、章节跨度与目标声明；自动分段单独收纳' : state.mode === 'people' ? '完整人物表、材料给出的角色弧与出现事件' : state.mode === 'mechanics' ? '目标、障碍、代价与状态声明逐条回到事件证据' : state.mode === 'causal' ? '显式前因、后果、伏笔与未解析引用' : state.mode === 'foreshadow' ? '每条显式伏笔声明的埋伏、兑现、待回收与断裂' : state.mode === 'states' ? '状态、变化、知情范围与转折逐条回到原文' : '已核验引文、未核验引文、归纳与推导分别呈现');
    var unresolved = arr(model.mains).concat(arr(model.lines)).filter(function (x) { return !x.resolved; }).length;
    setText('skyDeconMeta', (model.axis && model.axis.summary || model.nCh + ' 个章节段') + ' · ' + graph.events.length + ' 剧情点 · ' + graph.characters.length + ' 人物 · ' + unresolved + ' 条线未收束');
    Array.prototype.forEach.call(root.querySelectorAll('.sd-tabs [role="tab"]'), function (b) { var active = b.getAttribute('data-mode') === state.mode; b.classList.toggle('is-on', active); b.setAttribute('aria-selected', String(active)); b.tabIndex = active ? 0 : -1; });
    var body = doc.getElementById('skyDeconBody');
    if (body) {
      var content = state.mode === 'lines' ? renderLines() : state.mode === 'people' ? renderPeople() : state.mode === 'evidence' ? renderEvidence() : state.mode === 'mechanics' ? renderMechanics() : state.mode === 'causal' ? renderCausal() : state.mode === 'foreshadow' ? renderForeshadow() : state.mode === 'states' ? renderStates() : renderOverview();
      if (state.mode === 'evidence' && m88.snapshot && m88.snapshot.view === 'event') content = '<div class="sd-citation-return"><button type="button" class="sd-detail-action" data-action="foreshadow-echo-event-return">← 返回伏笔回响</button></div>' + content;
      if (state.mode !== 'overview' && m84.returning) content = structureReturnMarkup() + content;
      if (causalFork.returnTo && causalFork.returnTo.graph === graph && state.mode !== 'causal') content = '<div class="sd-citation-return"><button type="button" class="sd-detail-action" data-action="causal-fork-return">← 返回本次因果说明</button></div>' + content;
      if (m106.open && m106.view === 'record') content = '<div class="sd-citation-return"><button type="button" class="sd-detail-action" data-action="shared-citation-return">← 返回引用归属</button></div>' + content;
      body.innerHTML = content;
      body.setAttribute('aria-labelledby', 'skyDeconTab' + state.mode.charAt(0).toUpperCase() + state.mode.slice(1));
      if (browse.neighbors.scrollTop != null) { body.scrollTop = browse.neighbors.scrollTop; browse.neighbors.scrollTop = null; }
      bindVars(body); restoreFocus(body); bindCausalForkLayout(body);
    }
  }

  function restoreFocus(body) {
    var target = state.restore, found = null, buttons;
    if (!target || !body) return;
    buttons = body.querySelectorAll('[' + target.attr + ']');
    Array.prototype.some.call(buttons, function (el) {
      if (el.getAttribute(target.attr) === target.value && !el.disabled && (!target.action || el.getAttribute('data-action') === target.action) &&
          (!target.citationRef || el.getAttribute('data-citation-ref-id') === target.citationRef) &&
          (!target.recordLayer || el.getAttribute('data-record-layer') === target.recordLayer) &&
          (!target.recordId || el.getAttribute('data-record-id') === target.recordId) &&
          (!target.pageMode || el.getAttribute('data-page-mode') === target.pageMode)) { found = el; return true; }
      return false;
    });
    state.restore = null;
    if (found && found.focus) {
      found.focus({ preventScroll: true });
      if (typeof target.start === 'number' && found.setSelectionRange) found.setSelectionRange(target.start, target.end);
      if (target.attr !== 'data-search' && found.scrollIntoView) found.scrollIntoView({ block: 'nearest' });
    }
  }

  function bindVars(body) {
    Array.prototype.forEach.call(body.querySelectorAll('[data-sd-cols]'), function (el) { el.style.setProperty('--sd-cols', el.getAttribute('data-sd-cols') || '1'); });
    Array.prototype.forEach.call(body.querySelectorAll('[data-sd-h]'), function (el) { el.style.setProperty('--sd-h', el.getAttribute('data-sd-h') || '0'); });
    Array.prototype.forEach.call(body.querySelectorAll('[data-sd-l]'), function (el) { el.style.setProperty('--sd-l', el.getAttribute('data-sd-l') || '0'); });
    Array.prototype.forEach.call(body.querySelectorAll('[data-sd-w]'), function (el) { el.style.setProperty('--sd-w', el.getAttribute('data-sd-w') || '0'); });
    Array.prototype.forEach.call(body.querySelectorAll('[data-sd-x]'), function (el) { el.style.setProperty('--sd-x', el.getAttribute('data-sd-x') || '0'); });
  }

  function syncGraph() {
    var app = g.CLApp, sky = g.CLSky;
    if (!app || !app.graph || !sky || !sky.model) return false;
    var nextGraph = app.graph(), nextModel = sky.model();
    if (!nextGraph || !nextModel || !nextModel.ok) return false;
    clearM106(); m106.indexGraph = null; m106.byRef = null;
    if (nextGraph !== graph) {
      m88.graphEpoch++; m88Close(); m88.scope = 'reading'; m88.lastReading = null;
      stopCausalForkTween(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; causalFork.staticReason = '';
      cancelM84(true);
      clearM103();
      clearM84Return();
      if (searchTimer != null) { g.clearTimeout(searchTimer); searchTimer = null; }
      Object.keys(browse).forEach(function (key) { browse[key].page = 0; if (browse[key].query != null) browse[key].query = ''; if (browse[key].filter != null) browse[key].filter = 'all'; });
      browse.evidence.kind = 'all'; browse.evidence.person = ''; personDetail = null; state.focus = null;
      browse.mechanics.selected = null;
      browse.states.selected = null; browse.states.detailKey = null; browse.states.kind = 'all'; browse.states.eventIndex = null; browse.states.characterId = null;
    }
    graph = nextGraph; model = nextModel; index = buildIndex();
    m88.orderByIndex = []; var seenNodeIndex = Object.create(null);
    arr(model.narrative && model.narrative.architecture && model.narrative.architecture.nodes).forEach(function (n) {
      if (!n || n.index == null) return;
      if (seenNodeIndex[n.index]) m88.orderByIndex[n.index] = null;
      else { seenNodeIndex[n.index] = true; m88.orderByIndex[n.index] = causalNodeOrder(n, graph); }
    });
    state.ready = true; ensure(); render(); syncButton(); return true;
  }
  doc.addEventListener('cl:sky-deconstruct-toggle', toggle);
  doc.addEventListener('cl:graph-loading', function (event) {
    if (event && event.detail && event.detail.stage === 'fetch') { stopCausalForkTween(); stopCausalForkLayout(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; causalFork.staticReason = ''; m88Unwatch(); m88Close(); m88.scope = 'reading'; }
    if (!event || !event.detail || event.detail.stage !== 'fetch') return;
    cancelM84(true); clearM84Return(); clearM103(); clearM106();
    if (state.open) render();
  });
  doc.addEventListener('cl:sky-structure-state', function (event) {
    var ready = !!(event && event.detail && event.detail.ready === true);
    if (!ready && m84.open) cancelM84(true);
    if (state.open && state.mode === 'overview') render();
  });
  doc.addEventListener('cl:sky-plot', function () { if (m84.open) cancelM84(true); if (state.open && state.restore) closeToPlot(); });
  doc.addEventListener('cl:sky-compass', function () { stopCausalForkTween(); causalFork.source = null; causalFork.returnTo = null; causalFork.entrySnapshot = null; causalFork.staticReason = ''; if (state.open) close(false); });
  doc.addEventListener('cl:graph-ready', function () { if (m84.open) cancelM84(true); g.setTimeout(syncGraph, 0); });
  g.addEventListener('DOMContentLoaded', function () { g.setTimeout(syncGraph, 0); });
  function showRecord(layer, key, preserveCitation) {
    if (!state.ready) syncGraph();
    if (!index || !index.layers || !index.layers[layer]) return false;
    var rows = index.layers[layer], matches = rows.filter(function (row) { return row.recordId === String(key); });
    if (matches.length !== 1) return false;
    if (m106.open && !preserveCitation) clearM106();
    var at = rows.indexOf(matches[0]);
    open(); state.mode = 'mechanics';
    browse.mechanics.layer = layer; browse.mechanics.query = ''; browse.mechanics.filter = 'all';
    browse.mechanics.selected = rows[at].key; browse.mechanics.page = Math.floor(at / PAGE_SIZE);
    browse.references.page = 0; browse.mechanicQuotes.page = 0; render(); revealDetail('.sd-mechanics-card'); return true;
  }
  function showStates(scope) {
    if (m106.open) clearM106();
    if (!state.ready) syncGraph();
    if (!index) return false;
    scope = scope || {};
    var eventIndex = scope.eventIndex == null ? null : Number(scope.eventIndex), characterId = scope.characterId == null ? null : String(scope.characterId);
    if (eventIndex != null && (!isFinite(eventIndex) || eventIndex < 0 || Math.floor(eventIndex) !== eventIndex)) return false;
    var matching = index.stateRows.filter(function (row) { return (eventIndex == null || row.raw.eventIndex === eventIndex) && (characterId == null || row.raw.characterId === characterId); });
    if (!matching.length) return false;
    browse.states.query = ''; browse.states.filter = 'all'; browse.states.kind = 'all'; browse.states.page = 0;
    browse.states.eventIndex = eventIndex; browse.states.characterId = characterId; browse.states.selected = null;
    state.mode = 'states'; open(); return true;
  }
  var suppressOutsideClose = 0;
  function suppressOutsideOnce() { suppressOutsideClose = 1; }
  function showPerson(name) {
    if (m106.open) clearM106();
    if (!state.ready) syncGraph();
    if (!index || !index.people) return false;
    var p = index.people.filter(function (x) { return x.name === name; })[0];
    if (!p) return false;
    cancelM84(true);
    if (browse.neighbors.origin !== personKey(p)) { if (g.CLSky && g.CLSky.clearNeighborCompare) g.CLSky.clearNeighborCompare(); browse.neighbors.origin = null; browse.neighbors.bId = ''; browse.neighbors.result = null; browse.neighbors.demoCounts = null; }
    personDetail = personKey(p); browse.arc.page = 0;
    state.restore = { attr: 'data-person-detail', value: personDetail };
    state.mode = 'people'; open(); return true;
  }
  g.CLSkyStatusText = { label: statusLabel, hint: statusHint };
  g.CLSkyDeconstruction = { open: open, close: close, toggle: toggle, render: render, setMode: setMode, showRecord: showRecord, showStates: showStates, showPerson: showPerson, suppressOutsideOnce: suppressOutsideOnce, ready: function () { return state.ready; } };
})(window);
