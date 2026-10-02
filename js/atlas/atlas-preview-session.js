/* Three-atlas reading and reversible preview session. Real renderers, one scene, one state. */
(function (g) {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var root = $('atlasPreviewHUD'), trigger = $('btnPreview'), S = g.CLAtlasState;
  if (!root || !trigger || !S) return;
  var mountedGraph = null, previous = null, previousHistory = null, history = [], applying = false, timer = null, focusBefore = null, searchPosition = 0, evidenceQuote = '', evidenceVersion = 0, evidenceOpen = null;
  var LABEL = { annulus: '年轮 · 剧情结构', gem: '双晶 · 属性与叙事', domains: '星域 · 关系与世界' };
  function app() { return g.CLApp; }
  function bridge() { return app() && app().atlas; }
  function graph() { return app() && app().graph(); }
  function eid(x) { return x.id != null && x.id !== '' ? x.id : x.entityId != null && x.entityId !== '' ? x.entityId : x.name; }
  function lineId(x) { return x.sourceId != null && x.sourceId !== '' ? x.sourceId : x.id; }
  function scene() { return app() && app().scene(); }
  function active() { return !!mountedGraph && root.classList.contains('on'); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function notice(text) { $('aphCaption').textContent = text; }
  /* v90 F5：取景顶边 = 控制台真实高度 + 24，与 app.js syncSafeArea 同口径（控制台收窄后不再留旧的 175/242 空带）。 */
  function hudHeight() { var r = root.getBoundingClientRect ? root.getBoundingClientRect() : null; return r && r.height > 0 ? r.height : 0; }
  function area() { var h = hudHeight(), top = h ? Math.round(h + 24) : (innerWidth < 480 ? 242 : 175); return { left: 24, top: top, width: innerWidth - 48, height: Math.max(140, innerHeight - top - 150) }; }
  /* 字形按钮：只改小字名（≤480 隐藏）并同步 aria-label/title，不抹掉 SVG 字形。 */
  function nameButton(el, text, title) {
    var nm = el.querySelector && el.querySelector('.aph-nm');
    if (nm) { if (nm.textContent !== text) nm.textContent = text; } else el.textContent = text;
    el.setAttribute('aria-label', text); if (title) el.setAttribute('title', title);
  }
  function startrack() { return g.CLAtlasStartrack && CLAtlasStartrack.mounted && CLAtlasStartrack.mounted() ? CLAtlasStartrack : null; }
  function narrow() { try { return !!(g.matchMedia && g.matchMedia('(max-width: 480px)').matches); } catch (e) { return false; } }
  function character(ref) { if (!ref || !graph() || (ref.type && ref.type !== 'character')) return null; return graph().characters.filter(function (c) { return c.id === ref.id || c.entityId === ref.id || c.name === ref.name || c.name === ref.id; })[0] || null; }
  function selectedName() { var c = character(S.get().selected); return c ? c.name : null; }
  function currentEvent() { var G = graph(), st = S.get(); return G && st.cursor != null ? G.events[st.cursor] : null; }
  function selectedThread() { var st = S.get(), tree = app().story(); return tree && tree.threads.filter(function (t) { return st.selected && st.selected.type === 'line' && (t.id === st.selected.runtimeId || t.id === st.selected.id || t.sourceId === st.selected.id); })[0] || null; }
  function viewport(sc) {
    var canvas = sc.renderer && sc.renderer.domElement, rect = canvas && canvas.getBoundingClientRect();
    return { width: Math.max(1, rect && rect.width || innerWidth), height: Math.max(1, rect && rect.height || innerHeight) };
  }
  function cameraView(camera) {
    var view = camera.view;
    if (!view || !view.enabled) return null;
    return { enabled: true, fullWidth: view.fullWidth, fullHeight: view.fullHeight, offsetX: view.offsetX, offsetY: view.offsetY, width: view.width, height: view.height };
  }
  function restoreCameraView(sc, saved) {
    var camera = sc.camera, view = saved.view, current = viewport(sc), source = saved.viewport;
    var fields = ['fullWidth', 'fullHeight', 'offsetX', 'offsetY', 'width', 'height'];
    var valid = view && view.enabled && fields.every(function (key) { return typeof view[key] === 'number' && isFinite(view[key]); }) && view.fullWidth > 0 && view.fullHeight > 0 && view.width > 0 && view.height > 0;
    if (!valid) {
      /* A pre-lens-shift snapshot is an unshifted camera, not permission to
         inherit the outgoing crystal's off-axis projection. */
      camera.aspect = current.width / current.height;
      camera.clearViewOffset();
      return;
    }
    var oldWidth = source && source.width > 0 ? source.width : view.width;
    var oldHeight = source && source.height > 0 ? source.height : view.height;
    var sx = current.width / oldWidth, sy = current.height / oldHeight;
    camera.setViewOffset(view.fullWidth * sx, view.fullHeight * sy, view.offsetX * sx, view.offsetY * sy, view.width * sx, view.height * sy);
  }
  function snapshot() {
    var sc = scene(), camera = sc.camera, controls = sc.controls, nativeState = bridge().state();
    if (g.CLDomainsInteract && CLDomainsInteract.getSelection) nativeState.domains = CLDomainsInteract.getSelection();
    return { graph: graph(), state: S.get(), bridge: nativeState, searchNames: sc.searchNames ? sc.searchNames() : null, svgPaused: g.CLGemSVG && CLGemSVG.stats().paused, local: g.CLAtlasLocalGraph && CLAtlasLocalGraph.snapshot(), camera: { position: camera.position.toArray(), quaternion: camera.quaternion.toArray(), target: controls.target.toArray(), zoom: camera.zoom, view: cameraView(camera), viewport: viewport(sc) } };
  }
  function push() { if (!active()) return; history.push(snapshot()); if (history.length > 30) history.shift(); }
  function pause() { if (timer) clearInterval(timer); timer = null; S.dispatch({ type: 'motion', playing: false }); }
  function closeLocal() { if (g.CLAtlasLocalGraph) CLAtlasLocalGraph.close(); }
  function applyView(name) {
    if (!graph() || !bridge()) return false;
    var who = selectedName(), t = selectedThread();
    if (name === 'gem' && !who) who = t && t.lead || (graph().characters[0] && graph().characters[0].name);
    applying = true;
    var ok;
    try { ok = bridge().view(name, who, area(), S.get().peer); } finally { applying = false; }
    if (!ok) { notice(name === 'gem' ? '尚未识别角色 · 双晶不生成虚构人物' : '该图谱尚未就绪'); return false; }
    S.dispatch({ type: 'view', view: name }); document.body.dataset.atlasView = name;
    document.dispatchEvent(new CustomEvent('cl:atlas-view', { detail: { view: name, lens: S.get().lens } }));
    if (name === 'gem' && who) {
      var c = graph().characters.filter(function (x) { return x.name === who; })[0];
      S.dispatch({ type: 'select', entity: { type: 'character', id: eid(c), name: c.name } });
    }
    if (name !== 'gem') bridge().line(t ? t.id : null);
    var st = S.get(); if (st.cursor != null) { applying = true; try { bridge().seek(st.cursor); } finally { applying = false; } }
    render(); return true;
  }
  function view(name, remember) {
    if (!active() || ['annulus', 'gem', 'domains'].indexOf(name) < 0) return false;
    if (remember !== false) push(); pause(); closeLocal(); $('aphEvidenceCard').hidden = true;
    var ok = applyView(name); if (ok) notice(LABEL[name] + ' · 星、弧、晶面均来自当前作品'); return ok;
  }
  function chooseCharacter(name) {
    var G = graph(), c = G && G.characters.filter(function (x) { return x.name === name || x.id === name; })[0]; if (!c) return false;
    push(); pause(); closeLocal();
    S.dispatch({ type: 'select', entity: { type: 'character', id: eid(c), name: c.name } });
    var ok = applyView('gem');
    if (ok) notice(c.name + ' · ' + LABEL.gem + ' · 晶面来自当前作品');   /* v90 F7：从星核/珠/星域进入双晶时字幕同步，不残留上一图的说明 */
    return ok;
  }
  function chooseLine(id) {
    var tree = app().story(), t = tree && tree.threads.filter(function (x) { return x.id === id || x.sourceId === id; })[0]; if (!t) return false;
    push(); closeLocal(); S.dispatch({ type: 'select', entity: { type: 'line', id: lineId(t), runtimeId: t.id } });
    if (S.get().view !== 'annulus') applyView('annulus');
    applying = true; try { bridge().line(t.id); } finally { applying = false; }
    notice((t.src === 'derived' ? '算法推导 · ' : '') + (t.title || t.id) + ' · 点击「展开星簇」查看全部参与者'); render(); return true;
  }
  function seek(n, playing) {
    if (!active() || !graph().events.length) return false;
    if (!playing) pause();
    n = Math.max(0, Math.min(graph().events.length - 1, Math.floor(Number(n) || 0)));
    applying = true; try { if (!bridge().seek(n)) return false; } finally { applying = false; }
    S.dispatch({ type: 'cursor', index: n });
    var e = graph().events[n];
    notice((e.chapter || '未分章') + ' · ' + (e.title || '事件') + ' · 游标只选择已有事件，不推断成长');
    if (S.get().view === 'domains') scene().setSearchSet(e.characters || []);
    render(); return true;
  }
  /* v90 F5（F6-host.patch §P3.1）：清掉章节游标——状态与视觉一起清。
     宿主桥有 clearSeek 就走它；没有则沿用旧做法（桥 restore 一份 chapter=null / focusEv=-1 的当前态，
     双晶舞台被 restore 卸下后重新挂回）。 */
  function clearCursor() {
    if (!active()) return false;
    pause();
    var b = bridge(), was = S.get().view, direct = typeof b.clearSeek === 'function';
    applying = true;
    try {
      if (direct) b.clearSeek();
      else {
        var ns = b.state(); ns.chapter = null; if (ns.orbit) ns.orbit.focusEv = -1;
        if (g.CLDomainsInteract && CLDomainsInteract.getSelection) ns.domains = CLDomainsInteract.getSelection();
        b.restore(ns);
      }
    } finally { applying = false; }
    S.dispatch({ type: 'cursor', index: null });
    if (!direct && was === 'gem') applyView('gem');
    if (was === 'domains' && scene().setSearchSet) scene().setSearchSet(null);
    notice('游标已清空 · 回到全书视图');
    render(); return true;
  }
  function play() {
    if (S.get().playing) { pause(); return; }
    if (!active() || !graph().events.length) return;
    S.dispatch({ type: 'motion', playing: true });
    timer = setInterval(function () {
      var st = S.get(); if (!active() || document.hidden) { pause(); return; }
      if (st.cursor != null && st.cursor >= graph().events.length - 1) { pause(); return; }
      seek(st.cursor == null ? 0 : st.cursor + 1, true);
    }, 1100);
  }
  function restore(snap) {
    pause(); closeLocal(); $('aphEvidenceCard').hidden = true;
    if (!snap || snap.graph !== graph()) { notice('作品已变更 · 不恢复旧作品的选择'); return false; }
    S.dispatch({ type: 'restore', snapshot: snap.state });
    applying = true;
    try {
      bridge().restore(snap.bridge); applyView(snap.state.view);
      /* Empty selection is a state to restore, not a skipped operation.
         Reapply after view mounting so a preview-only solo cannot survive. */
      if (Object.prototype.hasOwnProperty.call(snap.bridge, 'domains') && g.CLDomainsInteract && CLDomainsInteract.setSelection) CLDomainsInteract.setSelection(snap.bridge.domains || { lineId: null, characterName: null }, { emit: false });
    } finally { applying = false; }
    var sc = scene(), p = new g.THREE.Vector3().fromArray(snap.camera.position), target = new g.THREE.Vector3().fromArray(snap.camera.target);
    sc.camera.zoom = snap.camera.zoom; restoreCameraView(sc, snap.camera); sc.camera.updateProjectionMatrix();
    sc.flyTo(p, target, .001); sc.camera.quaternion.fromArray(snap.camera.quaternion);
    sc.setCalm(!!snap.bridge.calm); document.body.dataset.atlasLens = snap.state.lens;
    sc.setSearchSet(snap.searchNames || null);
    if (g.CLGemMount && CLGemMount.setPaused) CLGemMount.setPaused(!!snap.svgPaused);
    if (snap.bridge.unfolded) bridge().unfold(snap.bridge.orbit && snap.bridge.orbit.thread);
    if (g.CLAtlasLocalGraph) CLAtlasLocalGraph.restore(snap.local);
    document.dispatchEvent(new CustomEvent('cl:atlas-view', { detail: { view: snap.state.view, lens: snap.state.lens } }));
    render(); return true;
  }
  function back() { if (g.CLAtlasLocalGraph && CLAtlasLocalGraph.isOpen()) { closeLocal(); return; } if (history.length) restore(history.pop()); render(); }
  function open() {
    if (!active()) { notice('先载入作品或示例，再进入三图预演'); return false; }
    if (S.get().preview) return true;
    previous = snapshot(); previousHistory = history.slice(); history = []; focusBefore = document.activeElement;
    S.dispatch({ type: 'preview', on: true }); document.body.classList.add('atlas-preview-open');
    notice('预演当前作品 · 使用真实三图渲染，退出恢复选择、章节和镜头'); render(); return true;
  }
  function close() {
    if (!S.get().preview) { pause(); closeLocal(); $('aphEvidenceCard').hidden = true; return false; }
    var snap = previous; previous = null; restore(snap); history = previousHistory || []; previousHistory = null; S.dispatch({ type: 'preview', on: false }); document.body.classList.remove('atlas-preview-open');
    if (focusBefore && focusBefore.isConnected) focusBefore.focus({ preventScroll: true });
    notice('已恢复预演前的图谱、选择与章节'); return true;
  }
  function expand() {
    if (!active() || !g.CLAtlasLocalGraph) return false;
    var G = graph(), selection = S.get().selected, t = selectedThread(), c = character(selection), e = currentEvent(), nodes = [], title;
    if (selection && selection.type === 'camp') {
      title = selection.name + ' · 成员星群';
      nodes = (selection.members || []).map(function (name) { return { id: name, label: name, type: 'character', edge: '属于此阵营' }; });
    } else if (t) {
      title = t.title || t.id;
      var names = Object.create(null); (t.events || []).forEach(function (i) { (G.events[i] && G.events[i].characters || []).forEach(function (n) { names[n] = true; }); });
      nodes = Object.keys(names).map(function (n) { return { id: n, label: n, type: 'character', edge: '参与此剧情线' }; });
    } else if (c && S.get().view === 'gem') {
      title = c.name + ' · 事件足迹';
      G.events.forEach(function (ev, i) { if ((ev.characters || []).indexOf(c.name) >= 0) nodes.push({ id: String(i), label: ev.title || '事件 ' + ev.order, type: 'event', edge: '角色参与' }); });
      (G.characterStates || []).forEach(function (stage) { var who = stage.characterId != null ? stage.characterId : stage.character || stage.name; if (String(who) === String(eid(c)) || who === c.name) nodes.push({ id: String(stage.id), label: stage.summary || stage.name || '阶段状态', type: 'state', edge: '已提供阶段记录', record: stage }); });
    } else if (e && S.get().view === 'annulus') {
      title = e.title || '事件'; nodes = (e.characters || []).map(function (n) { return { id: n, label: n, type: 'character', edge: '参与此事件' }; });
    } else {
      title = '角色星群'; nodes = G.characters.map(function (x) { return { id: x.name, label: x.name, type: 'character' }; });
    }
    if (!nodes.length) { notice('该记录暂无参与角色；原始事件仍可通过游标/取证查看'); return false; }
    CLAtlasLocalGraph.open({ title: title, note: nodes.length + ' 个节点 · 点星下潜', nodes: nodes,
      onSelect: function (n) { if (n.type === 'event') { closeLocal(); seek(Number(n.id)); evidence({ type: 'event', index: Number(n.id) }); } else if (n.type === 'state') evidence({ record: n.record }); else chooseCharacter(n.id); } });
    return true;
  }
  function expandLines() {
    var tree = app().story(), budget = g.CLPlot && CLPlot.annulusBudget(); if (!tree || !budget) return;
    var lookup = Object.create(null); budget.ids.forEach(function (id) { lookup[String(id)] = true; });
    var nodes = tree.threads.filter(function (t) { return lookup[String(t.id)]; }).map(function (t) { return { id: t.id, label: t.title || t.id, type: 'line', edge: '聚合剧情线成员' }; });
    CLAtlasLocalGraph.open({ title: '剧情星簇', note: nodes.length + ' 条真实线 · 分组展开', nodes: nodes, onSelect: function (n) { chooseLine(n.id); } });
  }
  function renderBudget() {
    var budget = g.CLPlot && CLPlot.annulusBudget && CLPlot.annulusBudget(), b = $('atlasAggregate'); if (!b) return;
    b.hidden = !active() || S.get().view !== 'annulus' || !budget || !budget.aggregated || !!(g.CLAtlasLocalGraph && CLAtlasLocalGraph.isOpen());
    if (budget && budget.aggregated) { $('atlasAggregateCount').textContent = '+' + budget.aggregated; b.setAttribute('aria-label', '展开其余 ' + budget.aggregated + ' 条剧情线，总线数 ' + budget.raw + '，当前绘制 ' + budget.visible); }
  }
  function evidence(ref) {
    var G = graph(); if (!G) return;
    evidenceQuote = ''; evidenceVersion++;
    ref = ref || {};
    var selection = S.get().selected;
    if (!ref.type && !ref.record && selection && selection.type === 'world') ref.record = (G[selection.field] || []).filter(function (x) { return String(x.id) === selection.id; })[0];
    var c = ref.name ? G.characters.filter(function (x) { return x.name === ref.name; })[0] : character(selection), e = ref.index != null ? G.events[ref.index] : currentEvent();
    var title = '', meta = '', body = '';
    var openRef = null;
    if (ref.type === 'attr' && c) {
      openRef = { type: 'attr', id: ref.id };
      var a = c.attrs[ref.id] || {}; title = c.name + ' · ' + ref.id;
      var gm = scene().gemModel && scene().gemModel(), gd = gm && gm.attr && gm.attr.filter(function (x) { return x.key === ref.id; })[0];
      if (gd) a = { score: gd.rawScore == null ? gd.score : gd.rawScore, pending: gd.score == null, low: gd.conf === 'low', basis: gd.basis || a.basis, evidence: gd.evidence || a.evidence || [] };
      meta = a.pending || a.score == null ? '未提供分值' : '评分 ' + a.score + '/100' + (a.low ? ' · 低证据' : '');
      if (gm && gm.stage) meta += ' · ' + (gm.stage.scope === 'chapter' ? '已知章节阶段' : '全书口径');
      body = '<p>' + esc(a.basis || '依据未提供') + '</p>' + (a.evidence || []).map(function (q) { return '<blockquote>' + esc(q) + '</blockquote>'; }).join('');
      evidenceQuote = a.evidence && a.evidence[0] || '';
    } else if (ref.type === 'meta' && c) {
      openRef = { type: 'meta', id: ref.id };
      var m = scene().metaOf(c.name); title = c.name + ' · ' + ref.id; meta = '确定性叙事度量 · 不是人物内在能力';
      body = '<p>' + esc(g.CLScene.META_DEF[ref.id] || '定义未提供') + '</p><p>原始值：' + esc(m && m.score ? m.score[ref.id] : '未提供') + '</p>';
    } else if (ref.record) {
      var r = ref.record; title = r.name || r.title || r.statement || r.question || r.id; meta = '扩展实体 · 来源状态以记录为准';
      body = '<p>' + esc(r.brief || r.description || r.summary || r.reason || r.statement || r.rule || '说明未提供') + '</p><small>' + esc(JSON.stringify(r.sourceRefs || [])) + '</small>';
      evidenceQuote = r.quote || r.seedQuote || '';
    } else if (e) {
      openRef = { type: 'event', index: G.events.indexOf(e) };
      title = e.title || '事件'; meta = (e.chapter || '未分章') + ' · ' + (e.kind || '类型未提供');
      body = '<p>' + esc(e.summary || '摘要未提供') + '</p>' + (e.quote ? '<blockquote>' + esc(e.quote) + '</blockquote>' : '<p>未提供原文引句</p>');
      body += '<small>' + (e.sourceRefs && e.sourceRefs.length ? '来源锚点 ' + e.sourceRefs.length + ' · 核验状态随记录保存' : '旧版记录无稳定原文锚点 · 引文未在本页重新核验') + '</small>';
      evidenceQuote = e.quote || '';
    } else if (c) { title = c.name; meta = c.identity || c.role; body = '<p>' + esc(c.brief || '简介未提供') + '</p>'; }
    else { notice('请先点选星体、事件或晶轴'); return; }
    if (evidenceQuote) body += '<p><button type="button" data-source-read>定位原文上下文</button></p><div id="aphSourceContext"></div>';
    evidenceOpen = openRef;
    pause(); $('aphEvidenceTitle').textContent = title; $('aphEvidenceMeta').textContent = meta; $('aphEvidenceBody').innerHTML = body; $('aphEvidenceCard').hidden = false;
  }
  function readSource(button) {
    var quote = evidenceQuote, version = evidenceVersion, mounted = graph(); if (!quote || !app().sourceDocuments) return;
    button.disabled = true; button.textContent = '正在本地核验…';
    app().sourceDocuments().then(function (docs) {
      if (version !== evidenceVersion || mounted !== graph()) return;
      var found = [];
      docs.forEach(function (d) { var text = String(d.text || ''), start = text.indexOf(quote); if (start >= 0) { found.push({ doc: d, start: start }); if (text.indexOf(quote, start + 1) >= 0) found.push({ ambiguous: true }); } });
      var host = $('aphSourceContext'); if (!host) return;
      if (found.length !== 1) { host.textContent = found.length ? '原文中存在多个逐字匹配，无法唯一定位；未选择近似段落。' : '当前材料未逐字命中此引文，不能当作已核验原文。'; return; }
      var match = found[0], raw = String(match.doc.text || ''), start = match.start;
      host.innerHTML = '<p>逐字命中 · ' + esc(match.doc.path || match.doc.name || '来源材料') + '</p><blockquote>' + esc(raw.slice(Math.max(0, start - 150), start)) + '<mark>' + esc(quote) + '</mark>' + esc(raw.slice(start + quote.length, start + quote.length + 150)) + '</blockquote><small>仅证明引文存在，不证明推断正确。此处未修改原始材料或图谱。</small>';
    }).catch(function (error) { if (version === evidenceVersion && $('aphSourceContext')) $('aphSourceContext').textContent = error.message; }).then(function () { if (button.isConnected) { button.disabled = false; button.textContent = '重新定位原文'; } });
  }
  function worldLens(kind) {
    S.dispatch({ type: 'lens', lens: kind });
    document.body.dataset.atlasLens = kind;
    document.dispatchEvent(new CustomEvent('cl:atlas-view', { detail: { view: S.get().view, lens: kind } }));
    if (kind === 'camps' || kind === 'story') { closeLocal(); scene().setInfoLayer(kind === 'story' ? 'story' : 'relations'); if (g.CLDomainsInteract && CLDomainsInteract.clearSelection) CLDomainsInteract.clearSelection(); if (g.CLDomainsHull) CLDomainsHull.setDim(kind === 'story' ? 1 : 0); notice(kind === 'story' ? '剧情域壳 · 成员共同参与，不等于彼此有关系' : '阵营与真实关系 · 空间距离不是地理位置'); return; }
    var G = graph(), rows = Array.isArray(G[kind]) ? G[kind] : [], cap = G.capabilities && G.capabilities[kind];
    if (!rows.length) { closeLocal(); notice('该作品' + (cap && cap.status === 'available' ? '未检出此类记录' : '尚未提供此类信息') + ' · 不生成占位星体'); return; }
    var types = { locations: 'location', items: 'item', worldRules: 'rule', clues: 'clue', causeEdges: 'cause' };
    var nodes = rows.map(function (r, i) { return { id: String(r.id || i), label: r.name || r.title || r.statement || r.question || ('记录 ' + (i + 1)), type: types[kind], record: r }; });
    CLAtlasLocalGraph.open({ title: $('aphLens').selectedOptions[0].text, note: rows.length + ' 条记录 · 关系拓扑非地理', nodes: nodes, onSelect: function (n) { worldDetail(kind, n.record); } });
  }
  function worldDetail(kind, record) {
    if (!g.CLAtlasWorld) { evidence({ record: record }); return; }
    var projection = CLAtlasWorld.neighbors(graph(), kind, record);
    push();
    S.dispatch({ type: 'select', entity: { type: 'world', field: kind, id: String(record.id) } });
    if (!projection.nodes.length) { evidence({ record: record }); notice('记录存在，但没有可唯一解析的关联端点 · 不补造关系'); return; }
    CLAtlasLocalGraph.open({ title: projection.title, note: projection.warnings.length ? projection.warnings.length + ' 引用待核对' : projection.nodes.length + ' 个明确关联', nodes: projection.nodes,
      onSelect: function (n) { if (n.type === 'character') chooseCharacter(n.record.name); else if (n.type === 'event') { closeLocal(); view('annulus'); seek(n.index); evidence({ index: n.index }); } else worldDetail(n.field, n.record); } });
    notice(projection.title + ' · 有向星弦只来自已提供的引用，点击原文可核查');
  }
  function search() {
    var q = $('aphSearch').value.trim().toLowerCase(), G = graph(); if (!q || !G) return;
    var hits = [], tree = app().story();
    G.characters.forEach(function (c) { if ([c.name].concat(c.aliases || []).join(' ').toLowerCase().includes(q)) hits.push({ type: 'character', id: c.name }); });
    (tree && tree.threads || []).forEach(function (t) { if ((t.title || '').toLowerCase().includes(q)) hits.push({ type: 'line', id: t.id }); });
    G.events.forEach(function (e, i) { if ((e.title + ' ' + e.chapter).toLowerCase().includes(q)) hits.push({ type: 'event', index: i }); });
    if (!hits.length) { notice('没有匹配实体 · 不改变当前图谱'); return; }
    var hit = hits[searchPosition++ % hits.length];
    if (hit.type === 'character') chooseCharacter(hit.id); else if (hit.type === 'line') chooseLine(hit.id); else { view('annulus'); seek(hit.index); }
    notice('匹配 ' + hits.length + ' 项 · 已在图中定位（再次搜索切下一项）');
  }
  function render() {
    if (!active()) return;
    var st = S.get(), G = graph(), e = currentEvent();
    $('aphTitle').textContent = st.preview ? 'LIVE PREVIEW · 真实图谱预演' : 'CASTLINE · ' + (G.title || '三图星典');
    $('aphState').textContent = LABEL[st.view]; $('aphPreview').setAttribute('aria-pressed', String(st.preview)); nameButton($('aphPreview'), st.preview ? '结束预演' : '预演');
    $('aphClose').hidden = !st.preview; $('aphCursor').max = Math.max(0, G.events.length - 1); $('aphCursor').value = st.cursor == null ? 0 : st.cursor;
    var cursorText = e ? '#' + e.order + ' · ' + e.chapter : '全书 · ' + G.events.length + ' 事件';
    $('aphCursorText').textContent = cursorText; $('aphCursor').setAttribute('aria-valuetext', e ? cursorText + ' · ' + (e.title || '事件') : cursorText);
    $('aphPlay').setAttribute('aria-pressed', String(st.playing)); $('aphPlay').setAttribute('title', st.playing ? '暂停章节游标（空格）' : '播放章节游标（空格）'); $('aphBack').disabled = !history.length;
    $('aphReduced').setAttribute('aria-pressed', String(st.reduced)); nameButton($('aphReduced'), st.reduced ? '恢复动效' : '静止', st.reduced ? '恢复动效' : '静止：停住全部动效');
    var T = startrack(); if (T) { T.sync(G, bridge().model ? bridge().model() : null); T.setCursor(st.cursor); }
    root.querySelectorAll('[data-preview-atlas]').forEach(function (b) { b.classList.toggle('on', b.dataset.previewAtlas === st.view); b.setAttribute('aria-pressed', String(b.dataset.previewAtlas === st.view)); });
    renderBudget();
  }
  function init() {
    if (g.CLSky && g.CLSky.enabled()) return;   // 星空壳接管；旧三页签工作区只在 ?shell=atlas 下启用
    var G = graph(); if (!G || mountedGraph === G) return;
    pause(); previous = null; previousHistory = null; history = []; mountedGraph = G; S.setGraph(G); closeLocal(); $('aphEvidenceCard').hidden = true;
    document.body.classList.add('atlas-workspace'); document.body.classList.remove('atlas-preview-open'); root.classList.add('on'); root.setAttribute('aria-hidden', 'false');
    scene().setHudSelector('.aph-head,.aph-controls,.aph-subcontrols,.aph-timeline,.aph-evidence:not([hidden]),.cl-dom-legend:not([hidden])');   // v90 F4：关系图例
    if (g.CLAtlasStartrack && $('aphTrack')) CLAtlasStartrack.mount($('aphTrack'), $('aphCursor'));
    var nativeState = bridge().state(), initial = nativeState.plot ? 'annulus' : 'domains';
    S.dispatch({ type: 'view', view: initial }); document.body.dataset.atlasView = initial; document.body.dataset.atlasLens = 'camps';
    $('aphPeer').replaceChildren(); var none = document.createElement('option'); none.value = ''; none.textContent = '无对比'; $('aphPeer').appendChild(none);
    G.characters.forEach(function (c) { var op = document.createElement('option'); op.value = c.name; op.textContent = c.name; $('aphPeer').appendChild(op); });
    render(); notice('左键/单指旋转 · 右键平移 · 滚轮/双指缩放 · 点星或点弧查看关联');
    if (g.CLDomainsHull) CLDomainsHull.setDim(0);
    g.dispatchEvent(new Event('resize'));
    if (new URLSearchParams(location.search).get('view') === 'annulus') view('annulus', false);
  }
  function handlesKey(e) { return active() && (e.key === 'Escape' || e.key === ' ' || e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key.toLowerCase() === 'u' || e.key.toLowerCase() === 'b'); }
  g.CLAtlasPreview = { open: open, close: close, active: active, isOpen: function () { return S.get().preview; }, isApplying: function () { return applying; }, handlesKey: handlesKey,
    setAtlas: view, setCursor: seek, chooseCharacter: chooseCharacter, chooseLine: chooseLine, expand: expand, expandLines: expandLines, evidence: evidence, play: play, pause: pause, back: back, snapshot: snapshot, restore: restore,
    state: S.get, stats: function () { return { active: active(), preview: S.get().preview, timer: !!timer, history: history.length }; },
    /* v90 F5 新增（F6-host.patch §P3）：只增不改 */
    clearCursor: clearCursor,
    evidenceRef: function () { return !$('aphEvidenceCard').hidden && evidenceOpen ? JSON.parse(JSON.stringify(evidenceOpen)) : null; },
    notice: function (text) { if (!active()) return false; notice(text == null ? '' : String(text)); return true; } };
  trigger.addEventListener('click', open); $('aphPreview').addEventListener('click', function () { S.get().preview ? close() : open(); }); $('aphClose').addEventListener('click', close);
  root.addEventListener('click', function (e) { var b = e.target.closest('[data-preview-atlas]'); if (b) view(b.dataset.previewAtlas); var sourceButton = e.target.closest('[data-source-read]'); if (sourceButton) readSource(sourceButton); });
  $('aphBack').addEventListener('click', back); $('aphExpand').addEventListener('click', expand); $('aphPlay').addEventListener('click', play);
  $('atlasAggregate').addEventListener('click', expandLines);
  $('aphEvidence').addEventListener('click', function () { evidence(); }); $('aphEvidenceClose').addEventListener('click', function () { $('aphEvidenceCard').hidden = true; });
  $('aphCursor').addEventListener('input', function () { seek(Number(this.value)); });
  $('aphCursor').addEventListener('keydown', function (e) {
    if (e.key !== 'PageUp' && e.key !== 'PageDown') return;
    var T = startrack(), starts = T ? T.chapterStarts() : [], cur = S.get().cursor == null ? 0 : S.get().cursor, to = null, i;
    if (!starts.length) return;
    e.preventDefault(); e.stopPropagation();
    if (e.key === 'PageDown') { for (i = 0; i < starts.length; i++) if (starts[i] > cur) { to = starts[i]; break; } }
    else { for (i = starts.length - 1; i >= 0; i--) if (starts[i] < cur) { to = starts[i]; break; } }
    if (to != null) seek(to);
  });
  $('aphReduced').addEventListener('click', function () { var quiet = !S.get().reduced; pause(); S.dispatch({ type: 'motion', reduced: quiet }); bridge().motion(quiet); render(); });
  $('aphTools').addEventListener('click', function () { var on = document.body.classList.toggle('atlas-tools-open'); this.setAttribute('aria-expanded', String(on)); });
  $('ops').addEventListener('click', function () { document.body.classList.remove('atlas-tools-open'); $('aphTools').setAttribute('aria-expanded', 'false'); });
  $('aphUnfold').addEventListener('click', function () { if (g.CLAtlasStage && CLAtlasStage.isOn()) bridge().closeUnfold(); else bridge().unfold(selectedThread() && selectedThread().id); });
  $('aphFace').addEventListener('click', function () { scene().setFace(scene().face() === 'top' ? 'under' : 'top'); scene().previewCrown(area()); });
  $('aphPeer').addEventListener('change', function () { S.dispatch({ type: 'peer', id: this.value || null }); applyView('gem'); });
  $('aphLens').addEventListener('change', function () { worldLens(this.value); });
  function searchBox() { var b = $('aphSearch').parentNode; return b && b.classList ? b : null; }
  function closeSearch() { var b = searchBox(); if (b) b.classList.remove('is-open'); }
  $('aphSearchGo').addEventListener('click', function () {
    var b = searchBox();
    if (narrow() && b && !b.classList.contains('is-open')) { b.classList.add('is-open'); $('aphSearch').focus(); return; }
    search();
  });
  $('aphSearch').addEventListener('input', function () { searchPosition = 0; });
  $('aphSearch').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); search(); } else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeSearch(); $('aphSearchGo').focus(); } });
  $('aphSearch').addEventListener('focusout', function (e) { var b = searchBox(); if (b && !this.value && !(e.relatedTarget && b.contains && b.contains(e.relatedTarget))) closeSearch(); });
  document.addEventListener('cl:graph-ready', init);
  document.addEventListener('cl:annulus-budget', renderBudget);
  g.addEventListener('cl:atlas-camp', function (event) {
    if (!active() || applying) return;
    var detail = event.detail || {}, seen = Object.create(null), members = [];
    (Array.isArray(detail.members) ? detail.members : []).forEach(function (name) {
      if (typeof name !== 'string' || !name || seen[name]) return;
      seen[name] = true; members.push(name);
    });
    if (!members.length) { notice('该阵营暂无可展开成员 · 不生成占位星体'); return; }
    push(); pause(); closeLocal(); $('aphEvidenceCard').hidden = true;
    S.dispatch({ type: 'select', entity: { type: 'camp', id: String(detail.id == null ? detail.name || '' : detail.id), name: detail.name || String(detail.id || '阵营'), members: members } });
    if (S.get().view !== 'domains') applyView('domains');
    expand(); render();
    notice((detail.name || '阵营') + ' · ' + members.length + ' 位成员，点星查看双晶；返回保留星群位置');
  });
  document.addEventListener('cl:atlas-stage', function (e) { if (active()) { S.dispatch({ type: 'pose', pose: e.detail && e.detail.on ? 'unfolded' : 'orbital' }); $('aphUnfold').setAttribute('aria-pressed', String(!!(e.detail && e.detail.on))); } });
  document.addEventListener('cl:plot-thread', function (e) { if (!active() || applying) return; var t = e.detail && e.detail.id; if (t != null && t !== '') { var tree = app().story(), found = tree && tree.threads.filter(function (x) { return x.id === t; })[0]; S.dispatch({ type: 'select', entity: { type: 'line', id: found ? lineId(found) : t, runtimeId: t } }); notice((found && found.title || t) + ' · 展开星簇查看参与者'); render(); } else { S.dispatch({ type: 'select', entity: null }); closeLocal(); notice('已取消剧情线选择'); } });
  document.addEventListener('cl:gem-event', function (e) { var d = e.detail || {}, G = graph(); if (!active() || !G) return; var i = G.events.findIndex(function (x) { return String(x.order) === String(d.order); }); if (i >= 0) seek(i); });
  document.addEventListener('visibilitychange', function () { if (document.hidden) pause(); });
  g.addEventListener('keydown', function (e) {
    if (!active() || (g.CLInformationArchitecture && CLInformationArchitecture.isOpen()) || document.querySelector('#apiPanel.on,#library.on,#confirm.on,#dsPanel.on')) return;
    if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    /* v90 F5（§P3.3）：焦点在预演实验室栏里时，Space/方向键/U/B 交还给那里的原生控件；Esc 仍退出层级 */
    if (e.key !== 'Escape' && e.target && e.target.closest && e.target.closest('#atlasLab')) return;
    if (!handlesKey(e)) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (e.key === 'Escape') { if (!$('aphEvidenceCard').hidden) $('aphEvidenceCard').hidden = true; else if (g.CLAtlasLocalGraph && CLAtlasLocalGraph.isOpen()) closeLocal(); else if (g.CLAtlasStage && CLAtlasStage.isOn()) bridge().closeUnfold(); else if (S.get().preview) close(); else back(); }
    else if (e.key === ' ') play(); else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') seek((S.get().cursor || 0) + (e.key === 'ArrowLeft' ? -1 : 1));
    else if (e.key.toLowerCase() === 'u') $('aphUnfold').click(); else if (e.key.toLowerCase() === 'b') $('aphFace').click();
  }, true);
  S.subscribe(function () { if (active()) render(); });
  init();
})(window);
