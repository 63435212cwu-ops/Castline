/* Explicit test-only fixture. Production never loads this file. */
(function (g) {
  'use strict';
  function create() {
    var chapters = [], events = [], threads = [], i, j, cast, id;
    for (i = 0; i < 1000; i++) {
      chapters.push({ name: '第' + (i + 1) + '章', idx: i, n: 2 + (i % 2) });
      for (j = 0; j < chapters[i].n; j++) {
        id = events.length; cast = [{ name: '角色' + ((id % 12) + 1) }, '角色' + (((id + 3) % 12) + 1)];
        events.push({ i: id, order: id + 1, chapIdx: i, chapter: chapters[i].name,
          title: '合成事件 ' + id, summary: '公开合成 fixture', kind: ['高燃', '转折', '关系'][id % 3], cast: cast, w: .5 });
      }
    }
    while (events.length < 3202) { id = events.length; events.push({ i: id, order: id + 1, chapIdx: chapters.length - 1, chapter: chapters[chapters.length - 1].name, title: '合成事件 ' + id, summary: '公开合成 fixture', kind: '日常', cast: [{ name: 'constructor' }], w: .5 }); }
      for (i = 0; i < 4; i++) threads.push(line('T' + i, 'main', i * 3, i * 3 + 15, null, i));
    threads[1].events.push(threads[0].events[0]);
    threads[0].events.push(0, 0, 99999, null, false, '', 1);
    for (i = 0; i < 12; i++) threads.push(line('T' + (i + 4), 'branch', i * 2 + 1, i * 2 + 3, 'T' + (i % 4), i + 4));
    var handoffs = [{ at: 16, from: 'T0', to: 'T1', reason: 'fixture evidence' },
      { at: 32, from: 'T1', to: 'T2', reason: 'fixture evidence' }, { at: 48, from: 'T2', to: 'T3', reason: 'fixture evidence' }];
    return { ok: true, src: 'fixture', fp: 'fixture-plot-overview-v1', chapters: chapters, events: events,
      threads: threads, trunk: { segments: threads.slice(0, 4).map(function (t) {
        return { threadId: t.id, from: t.events[0], to: t.events[t.events.length - 1], events: t.events };
      }), events: threads.slice(0, 4).reduce(function (a, t) { return a.concat(t.events); }, []), len: 64, chapters: 30, gaps: [] },
      handoffs: handoffs, junctions: [], cast: {}, stats: { events: events.length, threads: threads.length,
        main: 4, branches: 12, twigs: 0, handoffs: handoffs.length, ms: 0 }, warn: [] };
    function line(id0, kind, from, to, parent, seed) {
      var evs = [], x;
      for (x = from; x <= to && x < events.length; x += kind === 'main' ? 1 : 2) evs.push(x);
      return { id: id0, kind: kind, title: 'fixture ' + id0, events: evs, len: evs.length,
        parent: parent, attach: evs[0], depth: kind === 'main' ? 0 : 1, cast: ['角色' + ((seed % 12) + 1)],
        kindMix: { '关系': evs.length }, status: seed % 3 === 0 ? 'resolved' : 'suspended' };
    }
  }
  g.CLPlotHudSynth = { name: 'plot-hud-synth', create: create };
})(typeof window !== 'undefined' ? window : this);
