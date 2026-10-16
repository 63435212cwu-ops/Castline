'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }

const scenePath = path.join(__dirname, '../js/scene.js');
const source = fs.readFileSync(scenePath, 'utf8');

const DECL = 'var PLASMA_ON = (function () {';
const start = source.indexOf(DECL);
need(start >= 0, 'PLASMA_ON expression must exist verbatim in js/scene.js');
const end = source.indexOf('})();', start);
need(end > start, 'PLASMA_ON expression must be a self-contained IIFE');
const expr = source.slice(start, end + '})();'.length);
need(expr.indexOf('URLSearchParams') >= 0 && expr.indexOf("location.search") >= 0,
  'the switch must read location.search through URLSearchParams (exact key/value semantics)');

need(source.indexOf('?plasma=1 精确开启做对照') >= 0 && source.indexOf('开关按值精确读') >= 0,
  'scene.js header note still legislates exact opt-in (plasma=1 only)');

function onFor(search) {
  const context = { location: { search }, URLSearchParams };
  vm.createContext(context);
  vm.runInContext(expr, context, { filename: scenePath });
  return context.PLASMA_ON;
}

need(onFor('?plasma=1') === true, '?plasma=1 opts in (the only accepted value)');
need(onFor('?plasma=10') === false, '?plasma=10 must not opt in (exact value, no prefix match)');
need(onFor('?aplasma=1') === false, '?aplasma=1 must not opt in (exact key, no substring match)');
need(onFor('?demo=1&plasma=1') === true, 'plasma=1 works anywhere in the query string');
need(onFor('?demo=1') === false, 'no plasma key at all stays off');
need(onFor('?plasma=01') === false, '?plasma=01 stays off (string identity, not numeric)');
need(onFor('?plasma') === false, 'bare ?plasma (empty value) stays off');
need(onFor('') === false, 'empty query string stays off');

console.log(JSON.stringify({ ok: true, checks, cases: 8, cpuOnly: true }, null, 2));
