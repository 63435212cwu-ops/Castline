/* jsc tests/atlas_fallback_contract.js */
var window = this;
load('js/tree/storylines.js'); load('js/atlas/atlas-model.js'); load('js/atlas/atlas-source.js');
load('js/gem/gem-model.js'); load('js/atlas/atlas-fallback.js');
(function () {
  var checks = 0;
  function check(value, label) { if (!value) throw new Error(label); checks++; }
  var raw = JSON.parse(read('data/sample-saga.json')), before = JSON.stringify(raw), prepared = CLAtlasFallback.prepare(raw);
  check(prepared.graph.events.length === raw.events.length, 'all events retained');
  check(prepared.graph.characters.length === raw.characters.length, 'all characters retained');
  check(prepared.graph.relations.length === raw.relations.length, 'all relations retained');
  check(prepared.atlas.lines.length === raw.storylines.length, 'all source lines retained');
  check(JSON.stringify(raw) === before, 'source JSON remains unchanged');
  check(prepared.story.strictTopology && prepared.story.src === 'model', 'same pure source topology model');
  var noSource = CLAtlasFallback.prepare({ characters: [{ name: '甲' }], events: [{ order: 1, title: '事件', characters: ['甲'] }], relations: [] });
  check(noSource.atlas.lines.length === 0 && noSource.graph.events.length === 1, 'missing storylines do not invent a main plot');
  var M = CLGemModel.build(noSource.graph.characters[0], noSource.graph, { atlas: noSource.atlas });
  check(M.scoredCount === 0 && M.mean === null && !M.metaReady, 'missing attributes and narrative scores remain unknown');
  check(CLAtlasFallback.prepare({ graph: raw }).graph.events.length === raw.events.length, 'graph envelope imports safely');
  check(CLAtlasFallback.prepare({}).graph.events.length === 0, 'empty graph accepted');
  var bad = false; try { CLAtlasFallback.prepare([]); } catch (e) { bad = true; }
  check(bad, 'array input rejected with recoverable error');
  var missingEvidence = CLAtlasFallback.prepare({ characters: [{ name: '甲', attrs: { '智谋': { score: 98 } } }] });
  check(missingEvidence.graph.characters[0].attrs['智谋'].score === null, 'unsubstantiated scores are not painted as true values');
  print('ATLAS-FALLBACK-PURE OK · ' + checks + ' contracts');
})();
