'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const window = { CLAtlasSource: require('../js/atlas/atlas-source.js') };
vm.runInNewContext(fs.readFileSync('js/sky/sky-util.js', 'utf8'), { window });
vm.runInNewContext(fs.readFileSync('js/sky/sky-compass-band.js', 'utf8'), { window });
const band = window.CLSkyCompassBand;
const graph = { characters: [{ name: '甲' }], events: [{ id: 'a' }, { id: 'b' }], causeEdges: [
  { fromEventId: 'a', toEventId: 'b', basis: 'inferred', description: '材料支持的推导' },
  { sourceId: 'a', targetId: 'b', quote: '待核对的引文' },
  { fromEventId: 'a', toEventId: 'b', resolved: false },
  { fromEventId: 'a', toEventId: 'b', referenceStatus: 'unresolved' },
  { fromEventId: 'a', toEventId: 'missing' }
] };
const before = JSON.stringify(graph), ctx = band.context('甲', graph);
assert.equal(ctx.causes.length, 2, 'unresolved, missing and invalid edges do not create causal arcs');
assert.equal(ctx.causes[0].basis, '推导', 'a valid event pair does not verify an inferred causal claim');
assert.equal(ctx.causes[1].basis, '有引文未核验', 'a supplied quotation alone does not certify the claim');
assert.equal(band.causeLinks(ctx, { 0: 0, 1: 1 }).arcs.length, 2);
assert.equal(JSON.stringify(graph), before, 'the display projection does not rewrite source evidence');
graph.events.push({ id: 'a' });
assert.equal(band.context('甲', graph).causes.length, 0, 'duplicate event IDs stay ambiguous');
graph.events = [{ id: 0 }, { id: 'b' }];
graph.causeEdges = [{ fromEventId: 0, toEventId: 'b', basisCode: 'unverified' }];
assert.equal(band.context('甲', graph).causes[0].basis, '未核验', 'zero is a valid unique ID, not a missing reference');
console.log('SKY COMPASS EVIDENCE PASSED · unresolved, ambiguous, inferred and quoted references');
