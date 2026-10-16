(async function () {
  var F = CLAtlasFallback, checks = [], entry = !!window.__fallbackMainEntry, initialWebGLAttempts = __fallbackProbe.webglAttempts;
  function check(name, value) { checks.push({ name: name, ok: !!value }); if (!value) throw new Error(name); }
  function click(n) { n.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
  function findButton(pattern) { return Array.from(document.querySelectorAll('#atlasFallback button')).filter(function (b) { return pattern.test(b.textContent); })[0]; }
  check('native SVG runs independently of WebGL', (entry || typeof THREE === 'undefined') && F.stats().renderer === 'svg-2d' && (entry || !initialWebGLAttempts));
  check('only three primary atlas choices', document.querySelectorAll('.afb-nav button').length === 3);
  check('explicit sample JSON loads actual source lines', F.stats().events === 81 && F.stats().lines === 22 && F.stats().characters === 27);
  var sourceLines = {}, n;
  do { document.querySelectorAll('[data-line]').forEach(function (p) { sourceLines[p.dataset.line] = 1; }); n = findButton(/^下页/); if (n.disabled) break; click(n); } while (true);
  check('all source lines reachable by graph pagination', Object.keys(sourceLines).length === 22);
  var count = 0; document.querySelectorAll('[data-event-start]').forEach(function (p) { count += Number(p.dataset.eventEnd) - Number(p.dataset.eventStart) + 1; });
  check('event overview conserves event IDs', count === 81);
  F.setView('gem'); check('existing SVG gem renderer supplies two faces', document.querySelectorAll('.afb-gem [data-face=attr].cl-gem-face,.afb-gem [data-face=meta].cl-gem-face').length === 2);
  var gemRect = document.querySelector('.afb-gem .cl-gem').getBoundingClientRect(), stageRect = document.querySelector('.afb-stage').getBoundingClientRect();
  check('gem geometry occupies visible stage, not below hidden SVG', gemRect.height > 100 && gemRect.top >= stageRect.top && gemRect.bottom <= stageRect.bottom + 2);
  check('narrative unknown is not filled with invented score', !F.stats().gem.narrativeKnown && document.querySelectorAll('.afb-gem [data-face=meta] .cl-gem-vertex[data-score]').length === 0);
  var character = F.stats().selectedCharacter; click(findButton(/^下页/)); check('character pagination changes real model', F.stats().selectedCharacter === character + 1);
  F.selectEvent(12); check('event selection shares chapter state with gem', F.stats().selectedEvent === 12 && F.stats().chapter);
  check('invalid selected event safely rejected', F.selectEvent(99999) === false);
  var axis = document.querySelector('.afb-gem .cl-gem-badge[data-key]'); click(axis); check('quantified axis opens source evidence', !document.querySelector('.afb-evidence').hidden && document.querySelector('.afb-evidence pre'));
  click(findButton(/^关闭$/)); F.setView('domains'); click(findButton(/^返回$/));
  check('constellation overview uses graphical camp stars', document.querySelectorAll('.afb-cluster').length > 0 && document.querySelectorAll('.afb-star').length > 0);
  click(document.querySelector('.afb-star')); check('camp drilldown remains a star map', document.querySelectorAll('.afb-star').length > 0 && !document.querySelectorAll('.afb-cluster').length);
  click(findButton(/^返回$/)); click(findButton(/^关系 /)); var relationIds = {};
  do { document.querySelectorAll('[data-relation]').forEach(function (p) { relationIds[p.dataset.relation] = 1; }); n = findButton(/^下页/); if (n.disabled) break; click(n); } while (true);
  check('every relation remains reachable across graph pages', Object.keys(relationIds).length === F.stats().relations);
  F.setView('annulus'); F.selectEvent(12);
  document.querySelector('.afb-map').dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }));
  check('keyboard chapter-event navigation updates shared cursor', F.stats().selectedEvent === 13);
  document.querySelector('.afb-map').dispatchEvent(new KeyboardEvent('keydown', { key: 'e', bubbles: true, cancelable: true }));
  check('E exposes source evidence only on demand', !document.querySelector('.afb-evidence').hidden);
  document.querySelector('.afb-map').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  check('Escape dismisses evidence without erasing selected event', document.querySelector('.afb-evidence').hidden && F.stats().selectedEvent === 13);
  var synth = { title: 'Dense source', characters: [{ name: '甲' }, { name: '乙' }], events: [], relations: [{ a: '甲', b: '缺档人物', kind: '来源边' }] };
  for (var i = 0; i < 350; i++) synth.events.push({ order: i + 1, title: '事件' + i, chapter: '章' + Math.floor(i / 10), characters: ['甲'] });
  F.load(synth); count = 0; document.querySelectorAll('[data-event-start]').forEach(function (p) { count += Number(p.dataset.eventEnd) - Number(p.dataset.eventStart) + 1; });
  check('large event aggregate is complete, not sliced away', count === 350 && document.querySelectorAll('[data-event-start]').length <= 110);
  click(document.querySelector('[data-event-start]')); check('aggregate star expands the true order window', F.stats().range && F.stats().range[1] > F.stats().range[0]);
  F.setView('domains'); click(findButton(/^关系 /)); check('unresolved relationship kept as graph entrance', document.querySelector('[data-relation="0"].is-unknown'));
  click(document.querySelector('[data-relation="0"]')); check('unresolved edge source remains inspectable', document.querySelector('.afb-evidence pre').textContent.indexOf('缺档人物') >= 0);
  F.load({}); ['annulus', 'gem', 'domains'].forEach(function (view) { F.setView(view); check('empty ' + view + ' is a safe SVG state', !!document.querySelector('.afb-map .afb-empty')); });
  await F.loadURL('data/__missing_fallback_contract__.json'); check('failed fetch is reported with retry', F.stats().error && !document.querySelector('.afb-head button:last-child').hidden);
  await F.loadURL('data/sample-saga.json'); check('retry recovers without model analysis', F.stats().events === 81 && !F.stats().error);
  F.start(); check('repeated start retains one stage', document.querySelectorAll('#atlasFallback').length === 1);
  F.stop(); F.stop(); check('stop is idempotent and removes reading surface', !F.stats().active && !document.querySelector('#atlasFallback'));
  F.start({ query: '' }); F.load(synth);
  check('no browser errors or new WebGL requests during 2D reading', !__fallbackProbe.errors.length && __fallbackProbe.webglAttempts === initialWebGLAttempts);
  return { ok: true, checks: checks.length, results: checks, stats: F.stats(), webgl: __fallbackProbe.webglAttempts };
})()
