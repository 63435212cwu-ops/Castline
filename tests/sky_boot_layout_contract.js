'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = process.env.CASTLINE_ROOT ? path.resolve(process.env.CASTLINE_ROOT) : path.resolve(__dirname, '..');
const sceneSource = fs.readFileSync(process.env.CASTLINE_SCENE ? path.resolve(process.env.CASTLINE_SCENE) : path.join(ROOT, 'js/scene.js'), 'utf8');
const shellSource = fs.readFileSync(path.join(ROOT, 'js/sky/sky-shell.js'), 'utf8');
function declaration(source, pattern, label) {
  const match = source.match(pattern);
  assert.ok(match, 'could not extract real ' + label);
  return match[0];
}
function functionSource(source, name) {
  const start = source.indexOf('function ' + name + '(');
  assert.notEqual(start, -1, 'could not find real function ' + name);
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  assert.fail('unterminated function ' + name);
}
const layoutParam = declaration(sceneSource, /^  var LAYOUT_PARAM = .*;$/m, 'LAYOUT_PARAM');
const layoutMode = functionSource(sceneSource, 'layoutMode');
const shellEnabled = declaration(shellSource, /^  var ENABLED = .*;$/m, 'sky-shell ENABLED');
function evaluate(search, owner, includeOwner = true) {
  const context = {location: {search}, URLSearchParams, console};
  context.window = context;
  if (includeOwner) {
    const api = owner === 'throw' ? {enabled() { throw new Error('not ready'); }} :
      owner === 'missing' ? {} : {enabled() { return owner; }};
    context.CLSky = api;
    context.window.CLSky = api;
  }
  vm.runInNewContext(layoutParam + '\n' + layoutMode + '\nthis.result={param:LAYOUT_PARAM,mode:layoutMode()};', context);
  const shellContext = {location: {search}, URLSearchParams};
  vm.runInNewContext(shellEnabled + '\nthis.result=ENABLED;', shellContext);
  return {layout: context.result, shellEnabled: shellContext.result};
}
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('early boot URL policy matches sky-shell ENABLED for atlas, sky, probe, and production defaults', () => {
  for (const [search, expected] of [
    ['?shell=atlas', 'road'], ['?shell=sky', 'sky'], ['?sky=1', 'sky'],
    ['?probe=1', 'road'], ['', 'sky'],
    ['?shell=atlas&sky=1', 'road'], ['?probe=1&sky=1', 'sky'],
    ['?sky=0', 'sky'], ['?shell=other&sky=0&probe=1', 'sky']
  ]) {
    const got = evaluate(search, null, false);
    assert.equal(got.shellEnabled ? 'sky' : 'road', expected, search);
    assert.equal(got.layout.mode, expected, search);
  }
});
test('loaded CLSky.enabled is authoritative over shell URL defaults', () => {
  assert.equal(evaluate('?shell=atlas', true).layout.mode, 'sky');
  assert.equal(evaluate('?sky=1&probe=1', false).layout.mode, 'road');
  assert.equal(evaluate('', false).layout.mode, 'road');
});
test('explicit layout parameter takes priority over loaded owner and URL policy', () => {
  assert.equal(evaluate('?layout=camps&shell=atlas', true).layout.mode, 'camps');
  assert.equal(evaluate('?layout=road&sky=1', false).layout.mode, 'road');
});
test('missing or throwing owner falls back to the same URL policy as sky-shell', () => {
  for (const search of ['?shell=atlas', '?shell=sky', '?probe=1', '']) {
    const got = evaluate(search, search === '' ? 'throw' : 'missing');
    assert.equal(got.layout.mode, got.shellEnabled ? 'sky' : 'road', search);
  }
  assert.equal(evaluate('?sky=1', 'throw').layout.mode, 'sky');
});
console.log(passed + ' sky boot layout contracts passed');
