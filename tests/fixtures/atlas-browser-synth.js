/* Explicit test-only fixture — U09 atlas-acceptance CDP runner.
 * 用途：给 tests/atlas_browser.py 提供可注入浏览器页面的合成 tree/graph，
 * 覆盖两种场景：
 *   1. small()  —— 7 线小样本，线名/lead 唯一可搜索，供「CLAtlasStage 缺席时的
 *      score-only 兜底路径」与一般断言使用（不依赖 CLStory.analyze 的真实解析结果，
 *      直接按 js/tree/storylines.js runStrict 的 out 字段手写，可直接喂给
 *      CLAtlasModel.build(tree, G)）。
 *   2. stress() —— 对齐 U01 fixture 命名习惯的 s7 同构体（3000 事件 / 60 线），
 *      用于 R10 性能压测（首绘 + 滚动 30 帧）；不等 U01 落地也能先跑通道路径。
 * 生产环境从不加载本文件（只由 tests/atlas_browser.py 通过 Runtime.evaluate 注入源码）。
 * @contract v70 (U09 atlas-acceptance · 只读参考 CONTRACT §1)
 */
(function (g) {
  'use strict';

  function mkEvent(i, order, chapIdx, chapName, title, kind, cast) {
    return { i: i, order: order, chapter: chapName, chapIdx: chapIdx, title: title,
      summary: '合成事件 ' + i, kind: kind, quote: '', cast: cast.slice(0), w: 1 };
  }

  function mkChapters(n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push({ name: '第' + (i + 1) + '章', idx: i, n: 0 });
    return out;
  }

  /** 7 线小样本：M0(gen0,resolved,3-8) --handoff--> M1(gen? 实为同代主线延续, resolved)
   *  分支 B0..B3 分别挂在 M0/M1 不同事件点，含一条 twig(Tw0) 挂在 B0 上；
   *  刻意让「第一条支线」= B0（按 kind!=main 且 attach 最早排序时命中），
   *  名字含唯一字符串 "測試支線A" 便于按文本定位，不依赖猜测的 CSS 选择器。
   */
  function small() {
    var KINDS = ['转折', '抉择', '高潮', '冲突', '日常'];
    var CAST_POOL = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛'];
    var chapters = mkChapters(14);
    var events = [], id = 0, i;
    function push(chapIdx, kind, cast) {
      var e = mkEvent(id, id + 1, chapIdx, chapters[chapIdx].name, '合成事件' + id, kind, cast);
      events.push(e); id++; return e.i;
    }
    // M0：第0..5章，10 事
    var m0 = [];
    for (i = 0; i < 10; i++) m0.push(push(Math.min(5, (i / 2) | 0), KINDS[i % KINDS.length], [CAST_POOL[i % 4]]));
    // M1：第5..13章，14 事（与 M0 在第5章接棒）
    var m1 = [];
    for (i = 0; i < 14; i++) m1.push(push(5 + ((i / 2) | 0), KINDS[i % KINDS.length], [CAST_POOL[(i + 2) % 8]]));
    // B0（测試支線A）：挂在 M0 第2个事件，第1..3章，4 事
    var b0 = [];
    for (i = 0; i < 4; i++) b0.push(push(1 + i, '关系', [CAST_POOL[4], CAST_POOL[5]]));
    // B1：挂在 M0 末尾，第4..7章，5 事
    var b1 = [];
    for (i = 0; i < 5; i++) b1.push(push(4 + i, '日常', [CAST_POOL[1]]));
    // B2：挂在 M1 中段，第7..10章，6 事
    var b2 = [];
    for (i = 0; i < 6; i++) b2.push(push(7 + i, '冲突', [CAST_POOL[6]]));
    // B3：挂在 M1 末尾，第11..13章，3 事（悬置，无 resolution → unknown）
    var b3 = [];
    for (i = 0; i < 3; i++) b3.push(push(11 + i, '转折', [CAST_POOL[7]]));
    // Tw0：twig，挂在 B0 上，第2章，2 事
    var tw0 = [];
    for (i = 0; i < 2; i++) tw0.push(push(2, '日常', [CAST_POOL[5]]));

    var threads = [
      { id: 'T0', kind: 'main', title: '測試主線零', en: '', lead: '甲', cast: ['甲', '乙', '丙', '丁'],
        events: m0, len: m0.length, span: { startChap: 0, endChap: 5, chapCount: 6, known: true },
        parent: null, attach: null, depth: 0, heat: 1, kindMix: {}, resolved: false, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S0', topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: '', declaredParent: '', declaredAttach: null,
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' },
      { id: 'T1', kind: 'main', title: '測試主線一', en: '', lead: '丙', cast: ['丙', '戊', '己', '庚', '辛'],
        events: m1, len: m1.length, span: { startChap: 5, endChap: 13, chapCount: 9, known: true },
        parent: null, attach: null, depth: 0, heat: 1, kindMix: {}, resolved: true, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S1', topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: '收束', declaredParent: '', declaredAttach: null,
        anchored: false, pendingReason: '', handoff_from: 'S0', handoff_reason: '合成 fixture 接棒证据' },
      { id: 'T2', kind: 'branch', title: '測試支線A', en: '', lead: '戊', cast: ['戊', '己'],
        events: b0, len: b0.length, span: { startChap: 1, endChap: 3, chapCount: 3, known: true },
        parent: 'T0', attach: m0[1], depth: 1, heat: .4, kindMix: {}, resolved: true, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S2', topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: '收束', declaredParent: 'S0', declaredAttach: m0[1],
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' },
      { id: 'T3', kind: 'branch', title: '測試支線B', en: '', lead: '乙', cast: ['乙'],
        events: b1, len: b1.length, span: { startChap: 4, endChap: 7, chapCount: 4, known: true },
        parent: 'T0', attach: m0[m0.length - 1], depth: 1, heat: .3, kindMix: {}, resolved: false, suspended: true,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S3', topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: '悬置', declaredParent: 'S0', declaredAttach: m0[m0.length - 1],
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' },
      { id: 'T4', kind: 'branch', title: '測試支線C', en: '', lead: '庚', cast: ['庚'],
        events: b2, len: b2.length, span: { startChap: 7, endChap: 10, chapCount: 4, known: true },
        parent: 'T1', attach: m1[6], depth: 1, heat: .5, kindMix: {}, resolved: false, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S4', topologyStatus: 'ok',
        completionKnown: false, completion: null, resolution: '', declaredParent: 'S1', declaredAttach: m1[6],
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' },
      { id: 'T5', kind: 'branch', title: '測試支線D', en: '', lead: '辛', cast: ['辛'],
        events: b3, len: b3.length, span: { startChap: 11, endChap: 13, chapCount: 3, known: true },
        parent: 'T1', attach: m1[m1.length - 1], depth: 1, heat: .2, kindMix: {}, resolved: false, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S5', topologyStatus: 'ok',
        completionKnown: false, completion: null, resolution: '', declaredParent: 'S1', declaredAttach: m1[m1.length - 1],
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' },
      { id: 'T6', kind: 'twig', title: '測試末梢甲', en: '', lead: '己', cast: ['己'],
        events: tw0, len: tw0.length, span: { startChap: 2, endChap: 2, chapCount: 1, known: true },
        parent: 'T2', attach: b0[0], depth: 2, heat: .1, kindMix: {}, resolved: true, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'S6', topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: '收束', declaredParent: 'S2', declaredAttach: b0[0],
        anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' }
    ];
    // 缺 chapIdx 的一个空槽事件下标（考验 model.build 不崩 · 计入 warnings）：追加一条非法引用的孤线不放，
    // 保持 7 条线（原样，rawThreads 用 threads.length 即可）；如需坏槽场景用 stress() 覆盖。
    var trunk = { segments: [
      { threadId: 'T0', from: m0[0], to: m0[m0.length - 1], events: m0.slice(0), t0: 0, t1: .42, color: '', lead: '甲' },
      { threadId: 'T1', from: m1[0], to: m1[m1.length - 1], events: m1.slice(0), t0: .42, t1: 1, color: '', lead: '丙' }
    ], events: m0.concat(m1), len: m0.length + m1.length, chapters: 14, gaps: [] };
    var handoffs = [{ at: m0[m0.length - 1], from: 'T0', to: 'T1', t: .42, reason: '合成 fixture 接棒证据' }];
    var junctions = [];
    var cast = {};
    for (i = 0; i < threads.length; i++) for (var c = 0; c < threads[i].cast.length; c++) {
      var nm = threads[i].cast[c];
      if (!cast[nm]) cast[nm] = { threads: [] };
      cast[nm].threads.push(threads[i].id);
    }
    var tree = { ok: true, reason: '', src: 'model', fp: 'synth-small-v1', strictTopology: true,
      chapters: chapters, events: events, threads: threads, trunk: trunk, handoffs: handoffs,
      junctions: junctions, cast: cast, warn: [], unresolved: [], pendingHandoffs: [],
      stats: { events: events.length, threads: threads.length, main: 2, branches: 4, twigs: 1,
        trunkLen: trunk.len, trunkChapters: 14, trunkSegs: 2, handoffs: 1, junctions: 0,
        maxBranchLen: 6, avgBranchLen: 4.4, suspended: 1, castCovered: 8, coverage: 1, ms: 0 } };
    return tree;
  }

  /** 与 tree 对齐的最小图谱 G（characters/events/relations/storylines），
   * 供需要「真实 CLStory.analyze 路径」交叉核验的调用方使用；atlas_browser.py
   * 默认走「tree 直喂 CLAtlasModel.build」的近路，本函数只在需要时提供。 */
  function graphOf(tree) {
    var chars = [], seen = {}, i, j;
    for (i = 0; i < tree.threads.length; i++) for (j = 0; j < tree.threads[i].cast.length; j++) {
      var n = tree.threads[i].cast[j];
      if (!seen[n]) { seen[n] = 1; chars.push({ name: n, role: '', importance: 50, camp: '', stance: '', identity: '', brief: '', traits: [], attrs: {} }); }
    }
    var events = [];
    for (i = 0; i < tree.events.length; i++) {
      var e = tree.events[i];
      events.push({ chapter: e.chapter, title: e.title, summary: e.summary, characters: e.cast.slice(0), kind: e.kind, quote: e.quote, order: e.order });
    }
    var storylines = [];
    for (i = 0; i < tree.threads.length; i++) {
      var t = tree.threads[i];
      storylines.push({ id: t.sourceId, name: t.title, kind: t.kind === 'main' ? '主线' : (t.kind === 'twig' ? '末梢' : '支线'),
        parent: t.declaredParent || '', attach_order: t.declaredAttach == null ? 0 : (t.declaredAttach + 1),
        events: t.events.map(function (x) { return x + 1; }), lead: t.lead, cast: t.cast.slice(0),
        theme: t.theme, resolution: t.resolution || '', handoff_from: t.handoff_from || '', handoff_reason: t.handoff_reason || '' });
    }
    return { title: 'atlas-browser-synth', synopsis: '', characters: chars, events: events, relations: [], camps: [], meta: {}, storylines: storylines };
  }

  /** s7 同构压力体：3000 事件 / 60 线（4 主线代次接棒 + 44 支线 + 12 twig），
   * 命名与 U01 fixture README 的 s7 描述对齐（程序生成、供 R10 性能门槛复核）。 */
  function stress() {
    var TOTAL_EV = 3000, MAIN_N = 4, BRANCH_N = 44, TWIG_N = 12;
    var chapCount = 240, chapters = mkChapters(chapCount);
    var events = [], id, i, cast;
    for (id = 0; id < TOTAL_EV; id++) {
      var chapIdx = Math.min(chapCount - 1, (id / (TOTAL_EV / chapCount)) | 0);
      cast = ['角色' + ((id % 30) + 1)];
      events.push(mkEvent(id, id + 1, chapIdx, chapters[chapIdx].name, '压测事件' + id, ['转折', '抉择', '高潮', '冲突', '日常'][id % 5], cast));
    }
    var threads = [], mainEvs = [], perMain = Math.floor((TOTAL_EV * 0.4) / MAIN_N), cursor = 0;
    for (i = 0; i < MAIN_N; i++) {
      var evs = []; for (var k = 0; k < perMain; k++) evs.push(cursor++);
      mainEvs.push(evs);
      threads.push({ id: 'T' + i, kind: 'main', title: '压测主线' + i, en: '', lead: '角色1', cast: ['角色1', '角色2'],
        events: evs, len: evs.length, span: { startChap: events[evs[0]].chapIdx, endChap: events[evs[evs.length - 1]].chapIdx, chapCount: 1 + events[evs[evs.length - 1]].chapIdx - events[evs[0]].chapIdx, known: true },
        parent: null, attach: null, depth: 0, heat: 1, kindMix: {}, resolved: i < MAIN_N - 1, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'MS' + i, topologyStatus: 'ok',
        completionKnown: true, completion: null, resolution: i < MAIN_N - 1 ? '收束' : '', declaredParent: '', declaredAttach: null,
        anchored: false, pendingReason: '', handoff_from: i > 0 ? ('MS' + (i - 1)) : '', handoff_reason: i > 0 ? '压测接棒' : '' });
    }
    var handoffs = [];
    for (i = 1; i < MAIN_N; i++) handoffs.push({ at: mainEvs[i - 1][mainEvs[i - 1].length - 1], from: 'T' + (i - 1), to: 'T' + i, t: i / MAIN_N, reason: '压测接棒' });
    var branchStart = cursor, remaining = TOTAL_EV - cursor, perBranch = Math.max(2, Math.floor(remaining / (BRANCH_N + TWIG_N)));
    for (i = 0; i < BRANCH_N; i++) {
      var bevs = []; for (var b = 0; b < perBranch && cursor < TOTAL_EV; b++) bevs.push(cursor++);
      if (!bevs.length) break;
      var parentIdx = i % MAIN_N;
      threads.push({ id: 'T' + threads.length, kind: 'branch', title: '压测支线' + i, en: '', lead: '角色' + ((i % 28) + 3), cast: ['角色' + ((i % 28) + 3)],
        events: bevs, len: bevs.length, span: { startChap: events[bevs[0]].chapIdx, endChap: events[bevs[bevs.length - 1]].chapIdx, chapCount: 1 + events[bevs[bevs.length - 1]].chapIdx - events[bevs[0]].chapIdx, known: true },
        parent: 'T' + parentIdx, attach: mainEvs[parentIdx][i % mainEvs[parentIdx].length], depth: 1, heat: .3, kindMix: {},
        resolved: i % 3 === 0, suspended: i % 3 === 1, color: '', theme: '', quote: '', src: 'model', sourceId: 'BS' + i,
        topologyStatus: 'ok', completionKnown: i % 3 !== 2, completion: null, resolution: i % 3 === 0 ? '收束' : (i % 3 === 1 ? '悬置' : ''),
        declaredParent: 'MS' + parentIdx, declaredAttach: mainEvs[parentIdx][i % mainEvs[parentIdx].length], anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' });
    }
    for (i = 0; i < TWIG_N; i++) {
      var tevs = []; for (var t2 = 0; t2 < 2 && cursor < TOTAL_EV; t2++) tevs.push(cursor++);
      if (!tevs.length) break;
      var hostBranch = threads[MAIN_N + (i % BRANCH_N)];
      threads.push({ id: 'T' + threads.length, kind: 'twig', title: '压测末梢' + i, en: '', lead: hostBranch.lead, cast: [hostBranch.lead],
        events: tevs, len: tevs.length, span: { startChap: events[tevs[0]].chapIdx, endChap: events[tevs[tevs.length - 1]].chapIdx, chapCount: 1 + events[tevs[tevs.length - 1]].chapIdx - events[tevs[0]].chapIdx, known: true },
        parent: hostBranch.id, attach: hostBranch.events[0], depth: 2, heat: .1, kindMix: {}, resolved: true, suspended: false,
        color: '', theme: '', quote: '', src: 'model', sourceId: 'TW' + i, topologyStatus: 'ok', completionKnown: true, completion: null,
        resolution: '收束', declaredParent: hostBranch.sourceId, declaredAttach: hostBranch.events[0], anchored: false, pendingReason: '', handoff_from: '', handoff_reason: '' });
    }
    // 剩余未分配事件（若整除不尽）挂进最后一条主线，保证守恒：threads 事件总数 + 剩余 = TOTAL_EV，
    // 而 rawThreads 只数线数不数事件，故这里只需保证不产生非法下标，不必强行清零 remainder。
    var trunkEvs = mainEvs.reduce(function (a, e) { return a.concat(e); }, []);
    var trunk = { segments: threads.slice(0, MAIN_N).map(function (t) { return { threadId: t.id, from: t.events[0], to: t.events[t.events.length - 1], events: t.events.slice(0), t0: 0, t1: 1, color: '', lead: t.lead }; }),
      events: trunkEvs, len: trunkEvs.length, chapters: chapCount, gaps: [] };
    var cast = {};
    for (i = 0; i < threads.length; i++) for (var c2 = 0; c2 < threads[i].cast.length; c2++) {
      var nm2 = threads[i].cast[c2]; if (!cast[nm2]) cast[nm2] = { threads: [] }; cast[nm2].threads.push(threads[i].id);
    }
    return { ok: true, reason: '', src: 'model', fp: 'synth-stress-s7-v1', strictTopology: true,
      chapters: chapters, events: events, threads: threads, trunk: trunk, handoffs: handoffs, junctions: [],
      cast: cast, warn: [], unresolved: [], pendingHandoffs: [],
      stats: { events: events.length, threads: threads.length, main: MAIN_N, branches: BRANCH_N, twigs: TWIG_N,
        trunkLen: trunk.len, trunkChapters: chapCount, trunkSegs: MAIN_N, handoffs: handoffs.length, junctions: 0,
        maxBranchLen: perBranch, avgBranchLen: perBranch, suspended: Math.round(BRANCH_N / 3), castCovered: 30, coverage: 1, ms: 0 } };
  }

  g.CLAtlasBrowserSynth = { name: 'atlas-browser-synth', small: small, graphOf: graphOf, stress: stress };
})(typeof window !== 'undefined' ? window : this);
