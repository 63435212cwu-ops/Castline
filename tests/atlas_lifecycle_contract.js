/* W1/W5 offline contract: jsc tests/atlas_lifecycle_contract.js */
(function () {
  'use strict';
  var count = 0;
  function ok(value, label) {
    if (!value) throw new Error('FAIL ' + label);
    count++;
  }
  function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
  var coreText = read('js/core/scene-core.js');
  var registryText = coreText.slice(coreText.indexOf('    var frameHooks = []'), coreText.indexOf('    var snapReq = null;'));
  var batchText = coreText.slice(coreText.indexOf('      var hookBatch = frameHooks.slice();'), coreText.indexOf('      if (composer) composer.render();'));
  ok(registryText.length > 100 && batchText.length > 100, 'actual frame registry located');
  var registry = Function('var running=true;' + registryText + '\nreturn {register:registerFrameHook,stats:frameHookStats,tick:function(){var dt=1,tAcc=2,tAnim=2,calm=false,degrade=0;' + batchText + '}};')();
  var calls = [], offB, offA, offC, offD;
  offA = registry.register(function () { calls.push('a'); offA(); offB(); offD = registry.register(function () { calls.push('d'); }); });
  offB = registry.register(function () { calls.push('b'); });
  offC = registry.register(function () { calls.push('c'); });
  registry.tick();
  ok(same(calls, ['a', 'c']), 'unsubscribe does not skip C or run B/D in current frame');
  registry.tick();
  ok(same(calls, ['a', 'c', 'c', 'd']), 'new frame subscription starts next frame');
  ok(offA() === false && offB() === false, 'disposers idempotent');
  offC(); offD();
  ok(registry.stats().active === 0 && registry.stats().total === 0, 'disposal releases callback records');
  for (var cycle = 0; cycle < 100; cycle++) { var off = registry.register(function () {}); off(); off(); }
  ok(registry.stats().active === 0 && registry.stats().total === 0, '100 mount cycles do not accumulate');
  ok(typeof registry.register(null) === 'function', 'invalid hook gets safe noop disposer');
  var throwOff = registry.register(function () { throw new Error('isolated hook'); });
  var good = 0, goodOff = registry.register(function () { good++; }); registry.tick();
  ok(good === 1, 'one faulty hook does not stop following work'); throwOff(); goodOff();

  var win = {}, scope = Function('window', 'performance', read('js/domains/domains-model.js') + '\nreturn window.CLDomainsModel;');
  var model = scope(win, { now: function () { return 0; } });
  var nodes = { 'c:甲': { pos: { x: 0, y: 0, z: 0 } }, 'c:乙': { pos: { x: 50, y: 0, z: 0 } }, 'c:丙': { pos: { x: 0, y: 50, z: 0 } } };
  var api = { nodeOf: function (key) { return nodes[key]; } };
  var atlas = { lines: [
    { id: 'all', name: '长尾完整', lead: { name: '甲', known: true }, cast: [{ name: '甲' }, { name: '乙', role: 'minor' }, { name: '丙' }, { name: '丁', role: 'minor' }, { name: '乙', role: 'minor' }] },
    { id: 'single', cast: [{ name: '甲' }, { name: '丁' }] },
    { id: 'pair', cast: [{ name: '甲' }, { name: '乙' }] },
    { id: 'pending', cast: [{ name: '丁', role: 'minor' }] },
    { id: 'empty', cast: [] }
  ] };
  var before = JSON.stringify(atlas), D = model.build(atlas, api);
  ok(D.ok && D.domains.length === 5, 'all lines survive projection');
  ok(same(D.byId.all.members, ['甲', '乙', '丙', '丁']), 'minor and long tail kept with unique names');
  ok(D.byId.all.memberCount === 4 && D.byId.all.minorCount === 2, 'unique membership and minor counts');
  ok(D.byId.all.valid && D.byId.all.positionedCount === 3 && D.byId.all.unplacedCount === 1, 'one absent coordinate does not erase domain');
  ok(D.byId.single.layout === 'single' && D.byId.pair.layout === 'pair', 'single and pair layouts explicit');
  ok(D.byId.pending.layout === 'pending' && D.byId.pending.centroid === null, 'all absent positions stay unknown, not origin');
  ok(D.byId.empty.layout === 'pending' && D.byId.empty.memberCount === 0, 'empty member state retained');
  ok(JSON.stringify(atlas) === before, 'input facts untouched');
  nodes['c:丁'] = { pos: { x: 20, y: 80, z: 0 } };
  ok(model.refreshPositions(D, api) > 2 && D.byId.pending.valid, 'late coordinates activate pending domain');
  ok(D.byId.all.unplacedCount === 0 && D.byId.all.memberCount === 4, 'late projection preserves member accounting');
  delete nodes['c:丁']; model.refreshPositions(D, api);
  ok(!D.byId.pending.valid && D.byId.pending.centroid === null, 'lost coordinates return to pending');
  nodes['c:丙'].pos.x = Infinity; model.refreshPositions(D, api);
  ok(D.byId.all.positionedCount === 2 && D.byId.all.layout === 'pair', 'nonfinite positions never enter geometry');
  ok(model.build(atlas, {}).byId.all.memberCount === 4, 'missing projection API does not erase facts');
  ok(model.build({ lines: [] }, {}).ok && !model.build(null, api).ok, 'empty and absent models are safe');

  function Target() { this.handlers = {}; }
  Target.prototype.addEventListener = function (type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); };
  Target.prototype.removeEventListener = function (type, fn) { var a = this.handlers[type] || []; for (var i = a.length - 1; i >= 0; i--) if (a[i] === fn) a.splice(i, 1); };
  Target.prototype.dispatchEvent = function (event) { var a = (this.handlers[event.type] || []).slice(); for (var i = 0; i < a.length; i++) a[i](event); };
  var doc = new Target(), container = new Target(), styles = {}, bodyFlags = {}, bodyAttrs = {};
  container.classList = { add: function (x) { styles[x] = true; }, remove: function (x) { delete styles[x]; } };
  doc.body = { classList: { contains: function (key) { return !!bodyFlags[key]; } }, getAttribute: function (key) { return bodyAttrs[key]; } };
  doc.querySelector = function (sel) { return sel === '.cl-domains-lamps' ? container : null; };
  function Custom(type, opts) { this.type = type; this.detail = opts.detail; }
  function Observer() { this.observe = function () {}; this.disconnect = function () {}; }
  var timers = {}, timerId = 0, forced = [], hullSolo, lampSolo;
  var layer = function (isHull) { return { setHot: function () {}, setDim: function () {}, setSolo: function (v) { if (isHull) hullSolo = v; else lampSolo = v; } }; };
  var iw = { CLDomainsHull: layer(true), CLDomainsLamps: layer(false), matchMedia: function () { return { matches: false }; } };
  Function('window', 'document', 'navigator', 'CustomEvent', 'MutationObserver', 'setInterval', 'clearInterval', read('js/domains/domains-interact.js'))(
    iw, doc, { hardwareConcurrency: 8 }, Custom, Observer,
    function (fn) { timers[++timerId] = fn; return timerId; }, function (id) { delete timers[id]; });
  var inter = iw.CLDomainsInteract, ia = { setSearchSet: function (names) { forced = names.slice(); } };
  var oldDispose = inter.attach(D, ia), emitted = 0;
  doc.addEventListener('cl:plot-thread', function () { emitted++; });
  var got = inter.setSelection({ lineId: 'all', characterName: '乙' });
  ok(got.lineId === 'all' && got.characterName === '乙' && emitted === 0, 'public selection silent and complete');
  got.characterName = 'fake'; ok(inter.selection().characterName === '乙', 'selection snapshots cannot mutate state');
  ok(hullSolo === 'all' && lampSolo === 'all' && same(forced, ['乙']), 'selection updates both geometric layers and character highlight');
  doc.dispatchEvent(new Custom('cl:plot-thread', { detail: { id: 'pair' } }));
  ok(inter.selection().lineId === 'pair' && emitted === 1, 'external selection consumed without event echo');
  doc.dispatchEvent(new Custom('cl:plot-thread', { detail: { id: null } }));
  ok(inter.selection().lineId === null && hullSolo === null && emitted === 2, 'external clear restores domain view');
  inter.setSelection({ lineId: 'single', characterName: '甲' }, { emit: true });
  ok(emitted === 3 && inter.selection().characterName === '甲', 'local emission does not erase chosen character');
  bodyFlags['atlas-workspace'] = true; bodyAttrs['data-atlas-view'] = 'gem'; bodyAttrs['data-atlas-lens'] = 'story';
  doc.dispatchEvent(new Custom('cl:atlas-view', { detail: { view: 'gem', lens: 'story' } }));
  ok(inter.stats().hidden && styles['is-hidden'], 'gem view hides plot domains synchronously');
  bodyAttrs['data-atlas-view'] = 'domains'; bodyAttrs['data-atlas-lens'] = 'camps';
  doc.dispatchEvent(new Custom('cl:atlas-view', { detail: { view: 'domains', lens: 'camps' } }));
  ok(inter.stats().hidden, 'camp lens does not overlay plot hulls');
  bodyAttrs['data-atlas-lens'] = 'story';
  doc.dispatchEvent(new Custom('cl:atlas-view', { detail: { view: 'domains', lens: 'story' } }));
  ok(!inter.stats().hidden && !styles['is-hidden'], 'story lens owns the domain layer');
  iw.CLAtlasPreview = { active: function () { return true; }, handlesKey: function () { return true; } };
  doc.dispatchEvent({ type: 'keydown', key: 'Escape' });
  ok(inter.selection().lineId === 'single', 'workspace-owned Escape cannot clear domain selection');
  iw.CLAtlasPreview = null;
  var dispose = inter.attach(D, ia), listenerCount = inter.stats().listeners;
  oldDispose(); ok(inter.stats().listeners === listenerCount, 'stale disposer cannot detach current owner');
  for (cycle = 0; cycle < 100; cycle++) inter.attach(D, ia);
  ok(inter.stats().listeners === listenerCount, '100 interaction remounts retain constant listener count');
  inter.detach(); inter.detach();
  ok(inter.stats().listeners === 0 && Object.keys(timers).length === 0, 'detach removes listeners and timers');
  ok(inter.attach({ ok: true, domains: [] }, ia) === false && inter.stats().listeners === 0, 'empty mount adds no listeners');
  print('ATLAS-LIFECYCLE OK · ' + count + ' contracts');
})();
