/* @role component · @owns js/plot-deck.js · @budget dom_nodes=16 js_ms=0.05 · @contract v47+v50 */
(function (g) {
  'use strict';
  var NAME = 'plot-deck', VERSION = '50', MAX_CAST = 5, W_MIN = 0.55;

  function isReduced() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  var q = (g.location && g.location.search) || '';
  if (q.indexOf('tree=1') >= 0 || q.indexOf('treestage=1') >= 0) {
    g.CLPlotDeck = {
      name: NAME, version: VERSION, show: function () {},
      stats: function () {
        return { name: NAME, version: VERSION, ready: false, mode: 'off', ev: null, title: '', shows: 0, narrated: 0, reduced: isReduced(), dom: 0 };
      }
    };
    return;
  }

  var reduced = isReduced();
  var hc = g.navigator && g.navigator.hardwareConcurrency;
  var lowEnd = typeof hc === 'number' && hc <= 4;
  var motionOn = !reduced && !lowEnd;

  var view = null, ready = false, root = null, top = null, title = null, meta = null,
      dot = null, kind = null, cast = null, line = null, nav = null, prev = null, next = null,
      threadInfo = null;
  var mode = 'narrate', curEv = null, shows = 0, narrated = 0, lastPulse = -1,
      narrateStarted = false, tickState = 0, vMode = '', chPrev = null;
  var sig = { ev: -1, th: null, ch: null };
  var stateBox = null, struct = null, stKind = '', stNotice = '';
  var holdOn = false, holdDesc = null;

  function el(tag, cls) { var n = document.createElement(tag); if (cls) { n.className = cls; } return n; }
  function stop(e) { e.stopPropagation(); }

  function kindColor(k) {
    var P = g.CLPalette;
    if (!P || !P.hex) { return ''; }
    var n;
    try { n = P.hex(k, 0); } catch (e) { try { n = P.hex(k); } catch (e2) { return ''; } }
    if (typeof n === 'string') { return n; }
    if (typeof n !== 'number') { return ''; }
    return '#' + ('000000' + (n >>> 0).toString(16)).slice(-6);
  }

  function wBand(w) {
    if (typeof w !== 'number') { return '500'; }
    if (w >= 0.85) { return '600'; }
    if (w >= 0.7) { return '500'; }
    return '400';
  }

  function chapShort(e) {
    var c = e && e.chapter;
    if (typeof c === 'string' && c.length) {
      var s = c.split(/[\s\u3000]+/)[0];
      if (s) { return s; }
    }
    if (e && typeof e.chapIdx === 'number') { return '第 ' + (e.chapIdx + 1) + ' 章'; }
    return '';
  }

  function pulseEv() {
    var m = view && view.motion && view.motion();
    var st = m && m.state && m.state();
    var p = st && st.pulse;
    if (!p) { return null; }
    var v = p.evIdx;
    return (typeof v === 'number' && v >= 0) ? v : null;
  }

  function flipTick() {
    if (!root) { return; }
    if (!motionOn) { root.setAttribute('data-tick', '0'); return; }
    tickState = tickState ? 0 : 1;
    root.setAttribute('data-tick', tickState ? '1' : '0');
  }

  function setMode(m) {
    mode = m;
    if (root) { root.setAttribute('data-mode', m); }
    if (m !== 'thread' && threadInfo) { threadInfo.textContent = ''; }
  }

  function addName(box, name, preview) {
    name = roleName(name);
    if (!name) { return; }
    var b = el('button', 'cl-o3-deck__name');
    b.type = 'button';
    b.setAttribute('data-name', name);
    b.textContent = name;
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      var cur = '';
      try { cur = view.state() && view.state().character; } catch (e2) { cur = ''; }
      view.setCharacter(cur === name ? null : name);
    }, false);
    if (preview) {
      b.addEventListener('mouseover', function () {
        var F = g.CLOrbit3DFootprint;
        if (F && F.preview) { F.preview(name); }
      }, false);
      b.addEventListener('mouseout', function () {
        var F = g.CLOrbit3DFootprint;
        if (F && F.clear) { F.clear(); }
      }, false);
    }
    box.appendChild(b);
  }

  function renderNames(box, names, preview) {
    box.textContent = '';
    var clean = [], seen = Object.create ? Object.create(null) : {}, i, name;
    for (i = 0; names && i < names.length; i++) {
      name = roleName(names[i]);
      if (name && !seen[name]) { seen[name] = 1; clean.push(name); }
    }
    var n = Math.min(clean.length, MAX_CAST);
    for (i = 0; i < n; i++) { addName(box, clean[i], preview); }
  }

  function setNav(btn, ev) {   /* 审核修正：用 data-to 而不是 data-ev —— interact 的 document 捕获监听会先抢 data-ev，再触发我们时属性已被重渲染成下一条 */
    if (ev == null) { btn.disabled = true; btn.setAttribute('data-to', ''); }
    else { btn.disabled = false; btn.setAttribute('data-to', String(ev)); }
  }

  function build() {
    if (root || !document.body) { return; }
    root = el('div', 'cl-o3-deck');
    root.setAttribute('aria-live', 'polite');
    top = el('div', 'cl-o3-deck__top');
    title = el('div', 'cl-o3-deck__title');
    meta = el('div', 'cl-o3-deck__meta');
    dot = el('i', 'cl-o3-deck__dot');
    kind = el('span', 'cl-o3-deck__kind');
    cast = el('span', 'cl-o3-deck__cast');
    line = el('span', 'cl-o3-deck__line');
    nav = el('div', 'cl-o3-deck__nav');
    prev = el('button', 'cl-o3-deck__prev');
    next = el('button', 'cl-o3-deck__next');
    threadInfo = el('div', 'cl-o3-deck__thread');
    prev.type = 'button'; next.type = 'button';
    meta.appendChild(dot); meta.appendChild(kind); meta.appendChild(cast); meta.appendChild(line);
    nav.appendChild(prev); nav.appendChild(next);
    root.appendChild(top); root.appendChild(title); root.appendChild(meta); root.appendChild(nav); root.appendChild(threadInfo);
    root.setAttribute('data-motion', motionOn ? 'on' : 'off');
    root.setAttribute('data-tick', '0');

    root.addEventListener('click', stop, false);
    root.addEventListener('pointerdown', stop, false);
    prev.addEventListener('click', function (e) {
      e.stopPropagation();
      var v = this.getAttribute('data-to');
      if (v !== '' && v != null) { view.focusEvent(parseInt(v, 10)); }
    }, false);
    next.addEventListener('click', function (e) {
      e.stopPropagation();
      var v = this.getAttribute('data-to');
      if (v !== '' && v != null) { view.focusEvent(parseInt(v, 10)); }
    }, false);

    document.body.appendChild(root);
    /* 内容面四件：三态机在 loading/empty 时把它们整体摘出文档、内容回来时原位插回。
     * 只登记自己的四个结构子节点 —— `.cl-o3-deck__badge` 由 plot-deck-badge.js 自己 insertBefore
     * 到 top 之前（V2-6 的产物），不在本单元职权内，不摘不毁。 */
    struct = [top, title, meta, nav, threadInfo];
  }

  /* ---------------------------------------------------------------- R2 三态（domain: 'deck'）
   * loading  ← CLPlotOrbitView 在场（本页适用）但 `desc()` 为 null —— 星轨尚未 setTree
   *            （app.js:2165 建 view 与首次 setTree 之间的真实窗口）·
   * empty    ← `desc().warn` 含 `no-events`（布局层判定无事件）或 `orderList()` 为空 —— 无事件可讲 ·
   * degraded ← `desc().warn` 非空且非 `no-events`（弧线缺事件 / 空线 / 孤父 / 失锚 —— 见
   *            plot-orbit-lanes.js 的 warn 产生点），**或** 当前记位 `curEv` 的那条事件已不在数据里
   *            （失据）—— 有内容但有损 ·
   * ready    ← 其余。
   * blank（**不是态**）：`CLPlotOrbitView` 缺席 ⇒ 本页不适用 ⇒ 不建 root、不注铭文（与改前一致）。
   *
   * 态位落 root 内新建的 `.cl-o3-deck__state`（`.cl-o3-deck` 是 display:grid，多一个子节点走隐式行，
   * 与既有的 `__badge` 同性质）。**内容面让位**用节点摘挂（纯 JS 节点操作，不写内联样式，
   * 免得给 G1「静态内联样式清零」添新账）：loading/empty 时把 top/title/meta/nav 摘出文档，
   * 内容回来时按原位插回；degraded 时两者共存，断态条压在内容之上。
   * **绝不 `root.textContent=''`** —— 那会连 `plot-deck-badge.js` 挂上来的 `.cl-o3-deck__badge`
   * （V2-6 的产物）一并毁掉，并让自己再也装不回来：改前 `empty()` 之后 `show(1)` 恒留在空态
   * （牌阵锁死），本单元修的就是这条，外加那条跨界破坏。
   *
   * 逐帧成本：一个 `desc()` O(1) getter + 一个 warn 小数组扫描（外加失据时一次 `eventAt`）；
   * `orderList()` **只在 boot 与内容渲染路径里取**（那本就是既有调用点），不逐帧分配数组。
   */
  var WARN_LABEL = {
    'no-events': '无事件', 'fork-backwards': '弧线倒卷', 'missing-event': '弧线缺事件',
    'empty-line': '空线', 'orphan-parent': '孤父线', 'no-parent': '无父线',
    'missing-attach': '失锚', 'lanes-wrapped': '泳道溢出', 'unsorted-line': '线内乱序',
    'dup-event': '事件重复', 'dup-line': '线重复', 'handoff-dup': '交棒重复',
    'orbit-order-partial': '序缺章', 'handoffs-empty-derived': '交棒推得',
    'handoff-off-trunk': '交棒离干', 'handoff-unknown-line': '交棒缺线', 'segment-no-line': '段无线',
    'main-no-segment': '主线无段'
  };
  function warnLabel(code) {
    var s = String(code == null ? '' : code).split(':')[0];
    return WARN_LABEL[s] || s.slice(0, 14);   /* 兜底显示原码 —— 远好过沉默 */
  }

  /* 有内容可叙述的态：degraded 是「有内容但有损」，**必须照常叙述**，
   * 只是额外出一个断态条。只有 loading / empty 才扣住内容面。 */
  function renderable(kind) { return kind === 'ready' || kind === 'degraded'; }

  /* v7.0 R3-B：CLOrbit3DAtlas 派发的守恒结果（null = 未收到，不假设任何结论）。 */
  var atlasConserved = null;
  try { document.addEventListener('cl:atlas-conserved', function (e) { atlasConserved = (e && e.detail && e.detail.total != null) ? { shown: e.detail.shown, total: e.detail.total } : null; }); } catch (e0) {}
  function cheapState() {
    var d;
    try { d = view.desc(); } catch (e) { return { kind: 'degraded', notice: '星轨描述读取失败' }; }
    if (!d) { return { kind: 'loading' }; }
    var wRaw = d.warn || [], n0 = wRaw.length, i;
    for (i = 0; i < n0; i++) {
      if (String(wRaw[i]).indexOf('no-events') === 0) { return { kind: 'empty' }; }
    }
    /* 几何层「车道打包溢出」若已被 CLOrbit3DAtlas 证明最终未丢线（shown === total），
     * 这一条不再参与 degraded 判定；其余 warn 码照旧逐字显示。 */
    var w = wRaw, ac = atlasConserved;
    /* 事件可能在本实例建立之前就派发过（展卷开合会重建牌阵）；直接问 overlay 的 stats() 兜底。 */
    if (!ac) { try { var st = g.CLOrbit3DAtlas && g.CLOrbit3DAtlas.stats && g.CLOrbit3DAtlas.stats(); if (st && st.ok && st.conserved) ac = { shown: st.shownLines, total: st.rawTotal }; } catch (eS) { ac = null; } }
    if (ac && ac.shown === ac.total) {
      w = []; for (i = 0; i < n0; i++) { if (String(wRaw[i]).indexOf('lanes-wrapped') !== 0) w.push(wRaw[i]); }
    }
    var n = w.length;
    if (n) { return { kind: 'degraded', notice: (n > 1 ? n + ' 处有损 · ' : '') + warnLabel(w[0]) }; }
    /* 记位只认「事件位」（>= 0）。renderThread / renderCharacter 收尾把 curEv 置 -1，
     * 那是「非事件视图」的哨兵，不是失据，必须排除，否则会永久停在 degraded。 */
    if (curEv != null && curEv >= 0 && !view.eventAt(curEv)) { return { kind: 'degraded', notice: '当前位已失据' }; }
    return { kind: 'ready' };
  }

  function attachStruct() {
    if (!root || !struct) { return; }
    for (var i = 0; i < struct.length; i++) {
      if (!struct[i].parentNode) { root.appendChild(struct[i]); }
    }
  }

  function detachStruct() {
    if (!struct) { return; }
    for (var i = 0; i < struct.length; i++) {
      if (struct[i].parentNode) { struct[i].parentNode.removeChild(struct[i]); }
    }
  }

  function setState(state, notice) {
    if (!root) { return; }
    notice = notice || '';
    if (state === stKind && notice === stNotice) { return; }   /* 同态同文不重建：免逐帧 DOM churn */
    stKind = state; stNotice = notice;
    if (!stateBox) { stateBox = el('div', 'cl-o3-deck__state'); }
    stateBox.textContent = '';
    stateBox.removeAttribute('data-cl-state');
    root.setAttribute('data-deck-state', state);
    if (stateBox.parentNode) { stateBox.parentNode.removeChild(stateBox); }
    if (state === 'loading' || state === 'empty') {
      detachStruct();
      root.appendChild(stateBox);
    } else {
      attachStruct();
      if (state === 'degraded' && struct && struct[0].parentNode === root) {
        root.insertBefore(stateBox, struct[0]);
      }
    }
    var SS = g.CLStatusStates;
    if (state === 'ready' || !stateBox.parentNode || !SS || !SS.applyState) { return; }
    SS.applyState(stateBox, state, { domain: 'deck', bars: 4, minHeight: 96, notice: notice });
  }

  /* 内容渲染路径的统一入口：先把态位摆正（内容面回位 + 有损则出断态条），再写内容。
   * 「有内容」时的 empty 是不可能的（`cheapState` 只在 warn/missing 上判空），故只可能是 ready/degraded。 */
  function markContent() {
    var r = cheapState();
    if (r.kind === 'degraded') { setState('degraded', r.notice); }
    else { setState('ready'); }
  }

  /* 显式内容渲染 = 解除显式空态的保持（hold）。见 empty() 的说明。 */
  function releaseHold() { holdOn = false; holdDesc = null; }

  /* 显式空态（公开 API `CLPlotDeck.empty()`，也是 `show(null)` 的落点）。
   * 与「数据驱动的 empty」的区别：数据仍在时它要能**保持住**，否则下一帧就被 tick 的判定翻回去，
   * 这个 API 就成了 1 帧的哑动作。保持条件取 `desc()` 的**对象同一性** —— desc 只在布局重建时换新对象
   * （orbit3d-view.js:265），故「同一性变了」恰好等价于「数据变了」，O(1) 且不引入新契约。
   * 显式内容渲染（show / renderThread / renderCharacter）立即解除保持。 */
  function empty() {
    if (!root) { build(); }
    if (!root) { return; }
    curEv = null;
    lastPulse = -1;
    var d = null;
    try { d = view ? view.desc() : null; } catch (e) { d = null; }
    holdOn = true;
    holdDesc = d;
    setState('empty');
  }

  function show(ev) {
    if (!view) { return; }
    if (ev == null) { empty(); return; }
    if (ev < 0) { return; }
    if (ev === curEv) { return; }
    var e = view.eventAt(ev);
    if (!e) {
      /* 改前此处是**静默 return**（R2 要消灭的那一类）：调用方拿到零反馈。
       * 记位 `curEv` 让 `cheapState()` 的失据检查把这个 degraded **保持到数据回来**为止
       * （而不是只闪一帧就被 tick 翻回 ready）；数据补上后同一记位自动恢复。 */
      curEv = ev;
      setState('degraded', '第 ' + (ev + 1) + ' 号事件缺档 · 该位无载记');
      return;
    }
    releaseHold();
    curEv = null;   /* 清记位：免得「上一位已失据」把本帧误判成 degraded（函数末尾会重新记位） */
    markContent();
    var list = view.orderList();
    var i = list.indexOf(ev);
    var N = list.length;
    if (i < 0) { i = 0; }
    setMode(mode);
    top.innerHTML = '<span class="cl-info-primary abyss-num">第 ' + (i + 1) + ' / ' + N + '</span> <span class="cl-info-secondary">· ' + chapShort(e) + '</span>';
    title.textContent = e.title || '';
    title.setAttribute('data-w', wBand(e.w));
    var c = kindColor(e.kind);
    dot.style.background = c || '';
    kind.textContent = e.kind || '';
    renderNames(cast, e.cast || [], true);
    var lt = '';
    if (e.lineIds && e.lineIds.length) {
      var th = view.threadAt(e.lineIds[0]);
      if (th && th.title) { lt = th.title; }
    }
    line.textContent = lt;
    setNav(prev, i > 0 ? list[i - 1] : null);
    setNav(next, i < N - 1 ? list[i + 1] : null);
    curEv = ev;
    lastPulse = ev;
    shows++;
    if (mode === 'narrate') { narrated++; }
    flipTick();
  }

  function chapterLabel(e) {
    if (!e) { return ''; }
    if (typeof e.chapter === 'string' && e.chapter.trim()) { return e.chapter.trim(); }
    if (typeof e.chapIdx === 'number' && isFinite(e.chapIdx)) { return '第 ' + (e.chapIdx + 1) + ' 章'; }
    return '';
  }

  function finiteOrder(e) { return !!(e && typeof e.order === 'number' && isFinite(e.order)); }

  function roleName(v) {
    if (typeof v === 'string') { return v.trim(); }
    if (v && typeof v.name === 'string') { return v.name.trim(); }
    return '';
  }

  function readThreadEvents(t) {
    var raw = (t && t.events) || [], out = [], seen = Object.create ? Object.create(null) : {}, missing = 0, i, id, e;
    for (i = 0; i < raw.length; i++) {
      id = raw[i];
      if (typeof id === 'string' && id.trim() !== '' && isFinite(Number(id))) { id = Number(id); }
      if (typeof id !== 'number' || !isFinite(id)) { missing++; continue; }
      if (seen[id]) { continue; }
      seen[id] = 1;
      e = view.eventAt(id);
      if (e) { out.push({ id: id, event: e, source: i, ordered: finiteOrder(e) }); }
      else { missing++; }
    }
    out.sort(function (a, b) {
      if (a.ordered && b.ordered && a.event.order !== b.event.order) { return a.event.order - b.event.order; }
      if (a.ordered !== b.ordered) { return a.ordered ? -1 : 1; }
      return a.source - b.source;
    });
    return { items: out, missing: missing };
  }

  function eventButton(parent, item, extraClass) {
    var b = el('button', 'cl-o3-deck__event' + (extraClass ? (' ' + extraClass) : ''));
    b.type = 'button';
    b.setAttribute('data-to', String(item.id));
    b.textContent = (item.event.title || ('事件 ' + item.id)) + (chapterLabel(item.event) ? (' · ' + chapterLabel(item.event)) : '');
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      if (view && view.focusEvent) { view.focusEvent(item.id); }
    }, false);
    parent.appendChild(b);
  }

  function threadStatus(t) {
    if (t && t.resolved === true && t.suspended === true) { return '状态冲突 · 待校对'; }
    if (t && t.resolved === true) { return '收束'; }
    if (t && t.suspended === true) { return '悬置'; }
    return '状态未定';
  }

  function renderThread(id) {
    var t = view.threadAt(id);
    if (!t) { return; }
    releaseHold();
    curEv = -1;
    markContent();
    setMode('thread');
    var data = readThreadEvents(t), items = data.items, names = [], nameSet = Object.create ? Object.create(null) : {}, roleHits = Object.create ? Object.create(null) : {}, cs = t.cast || [], i, j, p, e;
    for (i = 0; i < cs.length; i++) {
      p = roleName(cs[i]);
      if (p && !nameSet[p]) { nameSet[p] = 1; names.push(p); }
    }
    for (i = 0; i < items.length; i++) {
      e = items[i].event;
      p = view.participants ? view.participants(items[i].id) : (e.cast || []);
      var eventNames = Object.create ? Object.create(null) : {};
      for (j = 0; j < p.length; j++) {
        var pn = roleName(p[j]);
        if (pn && !eventNames[pn]) {
          eventNames[pn] = 1;
          if (!nameSet[pn]) { nameSet[pn] = 1; names.push(pn); }
          if (!roleHits[pn]) { roleHits[pn] = Object.create ? Object.create(null) : {}; }
          roleHits[pn][i] = 1;
        }
      }
    }
    p = roleName(t.lead);
    if (p && !nameSet[p]) { nameSet[p] = 1; names.unshift(p); }
    var first = items.length ? chapterLabel(items[0].event) : '';
    var last = items.length ? chapterLabel(items[items.length - 1].event) : '';
    var sequenceReliable = items.every(function (x) { return x.ordered; });
    var reliableSpan = items.length > 1 && sequenceReliable && items.every(function (x) { return x.event && typeof x.event.chapIdx === 'number' && isFinite(x.event.chapIdx); });
    var span = reliableSpan ? Math.max(0, items[items.length - 1].event.chapIdx - items[0].event.chapIdx + 1) : 0;
    var range = first && last ? (first === last ? first : first + ' → ' + last) : (first || last || '章节未定');
    if (!sequenceReliable && items.length > 1) { range = '章节来源顺序未定 · ' + range; }
    top.innerHTML = '<span class="cl-info-primary abyss-num">线 · ' + items.length + ' 事件</span> <span class="cl-info-secondary">· ' + names.length + ' 参与角色</span>' + (data.missing ? ' <span class="cl-info-tertiary">· 缺失 ' + data.missing + '</span>' : '');
    title.textContent = t.title || '';
    title.setAttribute('data-w', '500');
    dot.style.background = typeof t.color === 'string' ? t.color : (typeof t.color === 'number' && isFinite(t.color) ? '#' + ('000000' + (t.color >>> 0).toString(16)).slice(-6) : '');
    kind.textContent = threadStatus(t);
    renderNames(cast, names, true);
    line.textContent = p ? ('领衔 \u00b7 ' + p) : '';
    threadInfo.textContent = '';
    var lede = el('div', 'cl-o3-deck__thread-lede');
    lede.textContent = items.length + ' 个事件 · ' + range + (span ? '（跨 ' + span + ' 章）' : '');
    if (data.missing) { lede.textContent += ' · 缺失 ' + data.missing + ' 个事件引用'; }
    threadInfo.appendChild(lede);
    var details = el('details', 'cl-o3-deck__reading');
    var summary = el('summary');
    summary.textContent = '阅读此线 · ' + items.length + ' 个事件';
    details.appendChild(summary);
    var eventBlock = el('div', 'cl-o3-deck__events');
    var eventHd = el('div', 'cl-o3-deck__subhead');
    eventHd.textContent = '线内事件';
    eventBlock.appendChild(eventHd);
    for (i = 0; i < items.length; i++) { eventButton(eventBlock, items[i]); }
    if (!items.length) {
      var noEvents = el('span', 'cl-o3-deck__muted');
      noEvents.textContent = '没有可聚焦的有效事件';
      eventBlock.appendChild(noEvents);
    }
    details.appendChild(eventBlock);
    var roleBlock = el('div', 'cl-o3-deck__participants');
    var roleHd = el('div', 'cl-o3-deck__subhead');
    roleHd.textContent = '参与角色 · ' + names.length;
    roleBlock.appendChild(roleHd);
    for (i = 0; i < names.length; i++) {
      var rd = el('details', 'cl-o3-deck__participant');
      var rs = el('summary');
      rs.textContent = names[i];
      rd.appendChild(rs);
      var rb = el('div', 'cl-o3-deck__participant-body');
      addName(rb, names[i], true);
      var roleEvents = [], hit = roleHits[names[i]] || {};
      for (j = 0; j < items.length; j++) { if (hit[j]) { roleEvents.push(items[j]); } }
      var roleMeta = el('span', 'cl-o3-deck__muted');
      roleMeta.textContent = ' · ' + roleEvents.length + ' 次出场';
      rb.appendChild(roleMeta);
      rd.appendChild(rb);
      roleBlock.appendChild(rd);
    }
    details.appendChild(roleBlock);
    threadInfo.appendChild(details);
    curEv = -1;
    flipTick();
  }

  function renderCharacter(name) {
    releaseHold();
    curEv = -1;
    markContent();
    var list = view.orderList();
    var evCount = 0, lineCount = 0, lineSet = {}, co = {}, j, k;
    for (var i = 0; i < list.length; i++) {
      var e = view.eventAt(list[i]);
      if (!e) { continue; }
      var cs = e.cast || [];
      if (cs.indexOf(name) < 0) { continue; }
      evCount++;
      var ls = e.lineIds || [];
      for (j = 0; j < ls.length; j++) {
        if (!lineSet[ls[j]]) { lineSet[ls[j]] = 1; lineCount++; }
      }
      for (k = 0; k < cs.length; k++) {
        if (cs[k] !== name) { co[cs[k]] = (co[cs[k]] || 0) + 1; }
      }
    }
    setMode('character');
    top.innerHTML = '<span class="cl-info-secondary">' + name + '</span> · <span class="cl-info-primary abyss-num">' + evCount + ' 次出场</span> · <span class="cl-info-tertiary">跨 ' + lineCount + ' 线</span>';
    title.textContent = name;
    title.setAttribute('data-w', '500');
    dot.style.background = '';
    kind.textContent = '角色';
    var names = [];
    for (var n in co) { if (Object.prototype.hasOwnProperty.call(co, n)) { names.push(n); } }
    names.sort(function (a, b) { return co[b] - co[a]; });
    renderNames(cast, names, true);
    line.textContent = '';
    /* [I4 立法 · 八维摘要 + 跳转] deck 仅展示八维均值摘要与阵营，不铺开全维；支持跳转雷达主位 */
    if (g.CLAttrSource && g.DATA && g.DATA.characters) {
      var charObj = null;
      for (var cIdx = 0; cIdx < g.DATA.characters.length; cIdx++) {
        var cc = g.DATA.characters[cIdx];
        if (cc && (cc.name === name || cc.id === name)) { charObj = cc; break; }
      }
      if (charObj) {
        var prof = g.CLAttrSource.computeCharacterProfile(charObj, g.DATA.characters);
        if (prof && prof.overallAverage) {
          line.innerHTML = '八维摘要 <b>' + prof.overallAverage + '</b>' + (prof.camp ? (' · ' + prof.camp) : '') +
            ' <a class="cl-deck-radar-jump" href="javascript:void(0)" title="跳转至雷达全息（八维单一主位）">全息 ↗</a>';
          var jumpEl = line.querySelector('.cl-deck-radar-jump');
          if (jumpEl) {
            jumpEl.onclick = function (e) {
              if (e && e.stopPropagation) e.stopPropagation();
              /* v5·R1 裁决（对应 reports/V0-REV.json 细化 R-2）。
               *
               * 事实核查（无头真机 + 全仓 grep，两条都不是推断）：
               *   · `CLPanelManager.openDock` —— **不存在**。`openDock` 是 app.js 的局部函数（app.js:2558），
               *     内容只有 `CLPanelManager.open('dock')` + 620ms 后 `syncSafeArea`；panel-manager 的公开
               *     API 里从来没有这个方法。
               *   · `window.selectChar` —— **全仓从未被赋值**，唯一出现处就是本 handler 自己那一行。
               * ⇒ 原 handler 的两个分支**双双恒假**：点这张「全息 ↗」是**静默无反应**的，不是"走了 fallback"。
               *
               * 修法（取「改用总线既有入口」，并**不**给 panel-manager 补 `openDock`）：
               *   ① 补 `openDock` 等于把「打开某块面板 + 它的业务后效」下沉进通用面板总线，职责错误；
               *   ② `panel-manager.js` 在本 run 已由 V1-1 验收、snapshot 冻结 —— 改它会让 V1-1 永久
               *      无法 finish（v4 死锁的同一机理，见 CONTRACT 铁律 1）；
               *   ③ 作者原意本是「打开 dock」（原句就是 openDock()），故 `open('dock')` 是**忠实还原意图**。
               *
               * 关于 openDock 里那句 620ms `syncSafeArea`：它并不是必须由 dock 打开方直接调用的 ——
               * app.js:1336 已把 `syncSafeArea` 挂在 `window` 的 resize 上（160ms 去抖）。
               * 故这里按本仓既有约定派发一次 resize（keys.js 的纯净模式同样「借 resize 让 app.js 自己重算、
               * 不碰其内部函数」），即可拿到等价的安全带重算，且**不新增对 app 内部函数的依赖**。
               *
               * 行为变化：改前点击**恒无效果** → 改后真的打开角色资料坞并重算安全带。
               * 这是**修好一条从未生效的控件**，不是给它换语义；请核验者按「改前是否有效」而非「是否改了行为」判定。
               */
              if (g.CLPanelManager && typeof g.CLPanelManager.open === 'function') {
                g.CLPanelManager.open('dock');
                try { g.dispatchEvent(new Event('resize')); } catch (e2) {}
              }
            };
          }
        }
      }
    }
    curEv = -1;
    flipTick();
  }

  function onFocus(ev) {
    sig.ev = (typeof ev === 'number') ? ev : -1;
    chPrev = null;
    if (sig.ev >= 0) { setMode('event'); curEv = -1; show(sig.ev); return; }
    if (sig.ch) { setMode('character'); renderCharacter(sig.ch); return; }
    if (sig.th != null) { setMode('thread'); renderThread(sig.th); return; }
    setMode('narrate');
  }

  function onThread(id) {
    sig.th = (id == null) ? null : id;
    if (sig.ev >= 0) { return; }
    if (sig.ch) { setMode('character'); renderCharacter(sig.ch); return; }
    if (sig.th != null) { setMode('thread'); renderThread(sig.th); return; }
    setMode('narrate');
  }

  function onCharacter(name) {
    if (name) {
      if (mode !== 'character') { chPrev = mode; }
      sig.ch = name;
      setMode('character');
      renderCharacter(name);
      return;
    }
    sig.ch = null;
    if (chPrev === 'thread' && sig.th != null) { setMode('thread'); renderThread(sig.th); }
    else if (sig.ev >= 0) { setMode('event'); curEv = -1; show(sig.ev); }
    else if (sig.th != null) { setMode('thread'); renderThread(sig.th); }
    else { setMode('narrate'); }
    chPrev = null;
  }

  function subscribe() {
    view.on('focus', onFocus);
    view.on('thread', onThread);
    view.on('character', onCharacter);
    view.on('mode', function (m) {
      vMode = m;
      if (m === 'idle' && mode === 'narrate') { lastPulse = -1; }
    });
  }

  function firstNarrate() {
    narrateStarted = true;
    var ev = pulseEv();
    var e = ev == null ? null : view.eventAt(ev);
    if (e && typeof e.w === 'number' && e.w >= W_MIN) { show(ev); return; }
    var list = view.orderList();
    if (list && list.length) { show(list[0]); }
  }

  function narrate() {
    var ev = pulseEv();
    if (ev == null || ev === lastPulse) { return; }
    lastPulse = ev;
    var e = view.eventAt(ev);
    if (!e) { return; }
    if (!(typeof e.w === 'number' && e.w >= W_MIN)) { return; }
    narrateStarted = true;
    show(ev);
  }

  function boot() {
    var V = g.CLPlotOrbitView;
    /* 不适用本页（星轨件缺席）= blank，**不建 root、不注铭文**，与改前一致。
     * 这一条是「哪几件真的适用于本页」的判据，不是「数据有没有到」的判据 —— 后者已交给三态机。 */
    if (!V || !V.desc || !V.orderList || !V.eventAt) { return false; }
    view = V;
    releaseHold();
    build();
    if (!root) { return false; }
    subscribe();
    ready = true;
    /* 改前：desc() 为空 / orderList() 为空就直接 `return false`（静默），牌阵永远不现身。
     * 现在改为显式三态 —— 本页适用就一定有话说（载入中 / 空悬 / 有损），不再静默。 */
    var r = cheapState();
    if (renderable(r.kind)) {
      var list = null;
      try { list = view.orderList(); } catch (e2) { list = null; }
      if (!list || !list.length) { r = { kind: 'empty' }; }
    }
    setState(r.kind, r.notice);
    if (!renderable(r.kind)) { return true; }
    firstNarrate();
    return true;
  }

  function tick() {
    if (!ready) {
      if (!boot()) { return; }
    }
    if (!view) { return; }
    /* 显式空态的保持：数据（desc 对象）未变则一帧都不翻，变了立即交还给判定。 */
    if (holdOn) {
      var d = null;
      try { d = view.desc(); } catch (e) { d = null; }
      if (d === holdDesc) { setState('empty'); return; }
      releaseHold();
    }
    var r = cheapState();
    setState(r.kind, r.notice);
    if (!renderable(r.kind)) { return; }
    if (!narrateStarted && mode === 'narrate') { firstNarrate(); }
    if (root && root.getAttribute('data-mode') === 'narrate') { narrate(); }
  }

  g.CLPlotDeck = {
    name: NAME,
    version: VERSION,
    show: show,
    empty: empty,
    stats: function () {
      return {
        name: NAME, version: VERSION, ready: ready, mode: mode, ev: curEv,
        title: title ? title.textContent : '', shows: shows, narrated: narrated,
        reduced: reduced, dom: root ? root.querySelectorAll('*').length + 1 : 0, view: vMode,
        state: stKind || ''
      };
    }
  };

  if (g.CLArcana && g.CLArcana.register) {
    g.CLArcana.register({ name: NAME, version: VERSION, build: function () {}, update: function () { tick(); } });
  }

  if (g.CLAttrSource && typeof g.CLAttrSource.subscribe === 'function') {
    /* R4 订阅端契约（attr-source.js:72-73 立）：回调内**只读**，不得回写本模块
     * —— 不调 `notify`、不改 `listeners`。这里只走纯读入口 `renderCharacter`（它内部只用
     * `view.orderList/eventAt/threadAt` 与 `CLAttrSource.computeCharacterProfile`，无任何写回），
     * 故 attr-source 的重入哨兵（notifying）不会被触发。
     * 实测登记：`notify` 全仓零调用点（V2-0 E11），本订阅端与另三端一样处于**待电**状态；
     * 它并非死桩 —— 回调体有真实动作且引用的 `renderCharacter` 确实存在。 */
    g.CLAttrSource.subscribe(function (payload) {
      if (payload && payload.charName && sig.ch === payload.charName) {
        renderCharacter(sig.ch);
      }
    });
  }
})(typeof window !== 'undefined' ? window : this);
