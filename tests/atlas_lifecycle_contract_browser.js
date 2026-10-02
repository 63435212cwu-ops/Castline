(function () {
  'use strict';
  var S = window.__cl && window.__cl.scene, original = window.__clDomains;
  var H = window.CLDomainsHull, L = window.CLDomainsLamps, I = window.CLDomainsInteract;
  var results = [], restoreSelection = I.getSelection();
  var wasWorkspace = document.body.classList.contains('atlas-workspace');
  var oldView = document.body.getAttribute('data-atlas-view'), oldLens = document.body.getAttribute('data-atlas-lens');
  function check(name, value) { results.push({ name: name, ok: !!value }); if (!value) throw new Error(name); }
  function hooks() { return S.stats().frameHooks; }
  var points = { 'c:甲': { pos: { x: -50, y: -20, z: 0 } }, 'c:乙': { pos: { x: 60, y: -20, z: 0 } }, 'c:丙': { pos: { x: 20, y: 60, z: 0 } } };
  var api = { scene: S.scene, camera: S.camera, renderer: S.renderer, registerFrameHook: S.registerFrameHook,
    nodeOf: function (id) { return points[id] || null; }, setSearchSet: function () {} };
  var atlas = { lines: [
    { id: 'full', name: '完整成员', gen: 0, kind: 'main', cast: [{ name: '甲' }, { name: '乙', role: 'minor' }, { name: '丙' }, { name: '丁', role: 'minor' }] },
    { id: 'pair', name: '双星支线', gen: 1, cast: [{ name: '甲' }, { name: '乙' }] },
    { id: 'single', name: '孤星支线', gen: 2, cast: [{ name: '丙' }] },
    { id: 'pending', name: '待布局支线', gen: 3, cast: [{ name: '丁', role: 'minor' }] },
    { id: 'unknown', name: '成员待核', gen: 4, cast: [] }
  ] };
  var D = CLDomainsModel.build(atlas, api), counter = 0, offA, offB, offC, offD, order = [];
  try {
    offA = S.registerFrameHook(function () { order.push('a'); offA(); offB(); offD = S.registerFrameHook(function () { order.push('d'); }); });
    offB = S.registerFrameHook(function () { order.push('b'); });
    offC = S.registerFrameHook(function () { order.push('c'); });
    S.step(1); check('real frame skips disposed callback, retains next, defers new', order.join('') === 'ac');
    S.step(1); check('new callback begins on next real frame', order.join('') === 'accd');
    check('real disposer is idempotent', offA() === false && offB() === false); offC(); offD();
    I.detach(); L.unmount(); H.detach();
    var base = hooks(), oldH = H.attach(api, D), oldL = L.mount(D, api), oldI = I.attach(D, api);
    check('all three mount APIs return disposer', typeof oldH === 'function' && typeof oldL === 'function' && typeof oldI === 'function');
    check('hulls and lamps own exactly two active frame callbacks', hooks().active === base.active + 2);
    var mountedListeners = I.stats().listeners;
    for (var n = 0; n < 100; n++) { H.attach(api, D); L.mount(D, api); I.attach(D, api); }
    oldH(); oldL(); oldI();
    check('100 remounts and stale disposers preserve exactly one owner', hooks().active === base.active + 2 && hooks().total === base.total + 2 && I.stats().listeners === mountedListeners);
    check('one geometric label layer survives remounts', document.querySelectorAll('.cl-domains-lamps').length === 1);
    check('all lines retain a star-map entrance including pending/small groups', L.stats().lamps === D.domains.length && L.stats().pending === 2);
    check('single, pair and full hull geometries stay distinguishable', H.stats().hulls === 1 && H.stats().pairs === 1 && H.stats().rings === 1);
    check('unknown positions clearly marked without fabricated centroid', D.byId.pending.centroid === null && document.querySelector('[data-id="pending"]').getAttribute('data-layout') === 'pending');
    document.body.classList.add('atlas-workspace'); document.body.setAttribute('data-atlas-view', 'gem'); document.body.setAttribute('data-atlas-lens', 'story');
    document.dispatchEvent(new CustomEvent('cl:atlas-view', { detail: { view: 'gem', lens: 'story' } }));
    check('gem cannot inherit plot-domain geometry or hit layer', I.stats().hidden && H.stats().dim === 0 && document.querySelector('.cl-domains-lamps').classList.contains('is-hidden'));
    document.body.setAttribute('data-atlas-view', 'domains');
    document.dispatchEvent(new CustomEvent('cl:atlas-view', { detail: { view: 'domains', lens: 'story' } }));
    check('story lens synchronously restores geometric ownership', !I.stats().hidden && H.stats().dim === 1);
    I.setSelection({ lineId: 'full', characterName: '乙' });
    check('explicit selection updates both layers and retains minor character', I.selection().characterName === '乙' && H.stats().solo === 'full' && L.stats().solo === 'full');
    function countEvent() { counter++; }
    document.addEventListener('cl:plot-thread', countEvent);
    document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: 'pair' } }));
    check('external selection does not echo', counter === 1 && I.selection().lineId === 'pair');
    document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: null } }));
    check('external clear restores constellation', counter === 2 && I.selection().lineId === null && H.stats().solo === null);
    document.removeEventListener('cl:plot-thread', countEvent);
    points['c:丁'] = { pos: { x: -60, y: 50, z: 0 } }; H.frame(); L.frame(); L.frame();
    check('late layout coordinates create a real singleton without reattaching', D.byId.pending.valid && H.stats().rings === 2 && L.stats().pending === 1);
    delete points['c:丁']; H.frame(); L.frame(); L.frame();
    check('lost layout returns to explicit pending entrance', !D.byId.pending.valid && H.stats().rings === 1 && L.stats().pending === 2);
    var root = document.querySelector('.cl-domains-lamps'); L.rebuild();
    check('layer rebuild rebinds active hit target', root !== document.querySelector('.cl-domains-lamps') && I.stats().bound && I.stats().listeners === mountedListeners);
    var entry = document.querySelector('.cl-domains-lamp[data-id="pair"]');
    entry.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    check('rebuilt geometric entrance still responds to pointer click', I.selection().lineId === 'pair');
    I.detach(); L.unmount(); H.detach(); I.detach(); L.unmount(); H.detach();
    check('repeated detach removes callbacks, hit layer and listeners', hooks().active === base.active && hooks().total === base.total && !document.querySelector('.cl-domains-lamps') && I.stats().listeners === 0);
    var empty = CLDomainsModel.build({ lines: [] }, api);
    check('empty model mounts schedule nothing', H.attach(api, empty) === false && L.mount(empty, api) === false && I.attach(empty, api) === false && hooks().active === base.active);
  } finally {
    if (offA) offA(); if (offB) offB(); if (offC) offC(); if (offD) offD();
    I.detach(); L.unmount(); H.detach();
    if (!wasWorkspace) document.body.classList.remove('atlas-workspace');
    if (oldView === null) document.body.removeAttribute('data-atlas-view'); else document.body.setAttribute('data-atlas-view', oldView);
    if (oldLens === null) document.body.removeAttribute('data-atlas-lens'); else document.body.setAttribute('data-atlas-lens', oldLens);
    if (original && original.ok) { H.attach(S, original); L.mount(original, S); I.attach(original, S); I.setSelection(restoreSelection); }
  }
  return JSON.stringify({ ok: true, checks: results.length, results: results, frameHooks: hooks() });
})()
