(async function () {
  'use strict';
  var out = [], R = __shellRegression, W = function (ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); };
  function check(name, ok, detail) { out.push({ name: name, ok: !!ok, detail: detail }); }
  function need(ok, what) { if (!ok) throw new Error(what); }
  async function until(fn, ms) { var at = performance.now(); while (performance.now() - at < ms) { if (fn()) return true; await W(25); } return false; }
  var A = await fetch('data/sample-saga.json').then(function (r) { if (!r.ok) throw new Error('A source missing'); return r.json(); });
  var B = await fetch('data/sample-mid.json').then(function (r) { if (!r.ok) throw new Error('B source missing'); return r.json(); });
  function begin(graph) { document.dispatchEvent(new CustomEvent('cl:graph-loading', { detail: { stage: 'fetch', frac: .08, title: graph.title } })); }
  function mount(graph) { CLApp.internal().mount(JSON.parse(JSON.stringify(graph))); }
  function validFetch(read) { return read.loader && read.loader.shown && read.loader.stage === 'fetch' && read.loader.frac <= .1 && read.hidden === false && read.display !== 'none' && read.box[0] > 0 && read.box[1] > 0 && read.title === B.title; }
  async function finishB(label) {
    mount(B); R.control.advance(10000); R.control.end();
    var fin = R.read(); check(label + ' B really mounts and its own curtain completes', fin.graph === B.title && fin.loader && fin.loader.stage === 'done' && fin.hidden === true, fin);
    await W(3100);
  }
  for (var kind of ['before-layout', 'during-hold', 'during-leave']) {
    try {
      R.control.begin(); begin(A); mount(A);
      need(R.read().loader.stage === 'layout' && R.control.pending('load').length > 0, 'did not reach A layout window');
      if (kind !== 'before-layout') {
        R.control.next('load'); need(R.read().loader.stage === 'compile', 'A compile window missing');
        R.control.next('load'); need(R.read().loader.stage === 'reveal' && R.ctx.revealT, 'A hold window missing');
      }
      if (kind === 'during-leave') {
        R.control.fire(R.ctx.revealT);
        need(R.read().loader.stage === 'done' && R.read().loader.shown && R.control.pending('leave').length > 0, 'A leave window missing');
      }
      var before = R.read(); begin(B); var started = R.read();
      R.control.advance(3000); await W(50); var after = R.read();
      check(kind + ' enters the intended real A/B window', before.graph === A.title && started.title === B.title, { before: before, started: started });
      check(kind + ' B stays visibly fetching at reset progress until its graph is ready', validFetch(after), after);
      check(kind + ' no A reveal occurs after B fetch begins', after.reveals === started.reveals, { before: started.reveals, after: after.reveals, fired: R.fired, canceled: R.canceled });
      await finishB(kind);
    } catch (error) {
      check(kind + ' experiment completed', false, String(error.stack || error)); R.control.cleanup(); R.unit.onLoading({ detail: { stage: 'error' } }); await W(50);
    }
  }
  try {
    var normal = R.read(); begin(A); mount(A);
    var finished = await until(function () { var s = R.read(); return s.hidden === true && s.loader.stage === 'done'; }, 6000);
    var read = R.read(); check('native normal flow completes A without controlled timers', finished && read.graph === A.title && read.reveals === normal.reveals + 1 && read.warms === normal.warms + 1, read);
    check('native normal flow leaves no controlled callbacks', R.control.pending().length === 0, R.control.pending());
    await W(3100);
  } catch (error) { check('native normal experiment completed', false, String(error.stack || error)); }
  try {
    begin(A); mount(A); var beforeError = R.read();
    document.dispatchEvent(new CustomEvent('cl:graph-loading', { detail: { stage: 'error', detail: 'test controlled read failure' } }));
    await W(250); var errorRead = R.read();
    check('native error hides the real curtain and invalidates pending compile work', errorRead.hidden === true && errorRead.warms === beforeError.warms && errorRead.reveals === beforeError.reveals + 1, errorRead);
    await W(3100);
  } catch (error) { check('native error experiment completed', false, String(error.stack || error)); }
  return { rows: out, expected: 15, limits: 'Only loader-owned timers are reordered in the three race cases; normal/error are native. Real DOM, production functions, renderer and fetched A/B graph data are used.' };
})()
