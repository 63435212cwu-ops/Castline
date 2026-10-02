load('js/atlas/atlas-world.js');
var pass = 0;
function ok(name, yes) { if (!yes) throw new Error(name); pass++; }
var G = { characters: [{ id: 'p', name: '甲' }], events: [{ id: 'e1', title: '开始', quote: '相同' }, { id: 'e2', title: '结果', quote: '结果引句' }], locations: [{ id: 'l', name: '地点' }], items: [], worldRules: [] };
var before = JSON.stringify(G);
var p = CLAtlasWorld.neighbors(G, 'causeEdges', { fromEventId: 'e1', toEventId: 'e2', relation: '促成' });
ok('known-edges', p.nodes.length === 2 && p.nodes[0].direction === 'in' && p.nodes[1].direction === 'out');
ok('existing-event-index', p.nodes[0].index === 0 && p.nodes[1].index === 1);
ok('missing-id-not-guessed', CLAtlasWorld.neighbors(G, 'causeEdges', { fromTitle: '开始', toTitle: '结果' }).nodes.length === 0);
ok('missing-endpoint-is-warning', CLAtlasWorld.neighbors(G, 'causeEdges', { fromEventId: 'bad' }).warnings.length === 1);
ok('explicit-participants', CLAtlasWorld.neighbors(G, 'locations', { id: 'l', characters: ['甲'] }).nodes[0].record.id === 'p');
ok('no-implicit-location-membership', CLAtlasWorld.neighbors(G, 'locations', { id: 'l' }).nodes.length === 0);
ok('quote-exact-only', CLAtlasWorld.neighbors(G, 'clues', { seedQuote: '相同', payoffQuote: '结果' }).nodes.length === 1);
G.events.push({ id: 'e3', quote: '相同' });
ok('ambiguous-quote-no-edge', CLAtlasWorld.neighbors(G, 'clues', { seedQuote: '相同' }).nodes.length === 0);
G.events.pop();
ok('read-only', JSON.stringify(G) === before);
print('ATLAS WORLD CONTRACT PASS ' + pass);
