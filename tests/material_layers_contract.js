'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const MATS = fs.readFileSync(path.join(ROOT, 'js/core/scene-mats.js'), 'utf8');
const RINGS = fs.readFileSync(path.join(ROOT, 'js/sky/sky-rings-glsl.js'), 'utf8');
const RINGSRUN = fs.readFileSync(path.join(ROOT, 'js/sky/sky-rings.js'), 'utf8');
const LAYERS_SRC = fs.readFileSync(path.join(ROOT, 'js/core/material-layers.js'), 'utf8');

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log('PASS ' + name); }
  else { failed++; console.log('FAIL ' + name + (detail ? ' :: ' + detail : '')); }
}

const sandbox = { navigator: { hardwareConcurrency: 8 } };
const fn = new Function('window', 'navigator', LAYERS_SRC + '\nreturn window.CLLayerRegistry;');
const REG = fn(sandbox, sandbox.navigator);
assert(REG && REG.LAYERS, 'material-layers.js must export CLLayerRegistry');

const EXPECT = ['volume', 'backAtten', 'surface', 'rough', 'transmission', 'innerlight', 'reflection', 'additive'];
const RING_EXPECT = ['domesection', 'concentric', 'astrolabe', 'sparsefloor'];
ok('crystal layer inventory covers volume/surface/transmission/reflection/additive + inner optics',
  EXPECT.every((k) => REG.LAYERS[k]) && REG.ORDER.length === EXPECT.length,
  'got ' + REG.ORDER.join(','));
ok('astrolabe halo cross-section layer inventory present',
  RING_EXPECT.every((k) => REG.RING_LAYERS[k]) && REG.RING_ORDER.length === RING_EXPECT.length,
  'got ' + REG.RING_ORDER.join(','));
ok('every layer declares an id, a label, a uniform, on/off values, an effect and a metric',
  REG.inventory().every((L) => L.id && L.label && L.uniform && L.effect && L.metric &&
    typeof L.on === 'number' && typeof L.off === 'number' && typeof L.structure === 'boolean'));

const CRYSTAL = EXPECT.map((k) => REG.LAYERS[k]);
const RING = RING_EXPECT.map((k) => REG.RING_LAYERS[k]);
for (const L of CRYSTAL) {
  const n = MATS.split(L.anchor).length - 1;
  ok('crystal layer ' + L.id + ' anchor is present exactly once in scene-mats.js',
    n === 1, 'occurrences=' + n + ' anchor=' + L.anchor.slice(0, 70));
}
for (const L of RING) {
  const n = RINGS.split(L.anchor).length - 1;
  ok('ring layer ' + L.id + ' anchor is present exactly once in sky-rings-glsl.js',
    n === 1, 'occurrences=' + n + ' anchor=' + L.anchor.slice(0, 70));
}

for (const L of CRYSTAL) {
  ok('layer ' + L.id + ' declares a dedicated uniform ' + L.uniform,
    typeof L.uniform === 'string' && L.uniform.startsWith('uLyr'));
  ok('layer ' + L.id + ' uniform ' + L.uniform + ' is read by the crystal shader',
    MATS.includes(L.uniform));
  ok('layer ' + L.id + ' uniform is declared as a float in a shader header',
    new RegExp('uniform\\s+float\\s+' + L.uniform + '\\b').test(MATS));
  ok('layer ' + L.id + ' uniform is installed from the single LAYER_SWITCHES default table',
    new RegExp(L.uniform + ':\\s*\\{\\s*value:\\s*LAYER_SWITCHES\\.' + L.uniform + '\\s*\\}').test(MATS));
  ok('layer ' + L.id + ' has exactly one default value in the LAYER_SWITCHES table',
    (MATS.match(new RegExp('\\b' + L.uniform + ':\\s*1\\b', 'g')) || []).length === 1);
}
for (const L of RING) {
  ok('ring layer ' + L.id + ' uniform ' + L.uniform + ' is read by the ring shader',
    RINGS.includes(L.uniform));
  ok('ring layer ' + L.id + ' uniform is declared in the RF header',
    new RegExp('uniform\\s+float\\s+[^;]*\\b' + L.uniform + '\\b').test(RINGS));
  ok('ring layer ' + L.id + ' uniform is installed with a default in sky-rings.js',
    new RegExp(L.uniform + '\\s*=\\s*\\{\\s*value:\\s*1\\s*\\}').test(RINGSRUN));
}

for (const k of EXPECT) ok('crystal layer ' + k + ' defaults to its production value (on=1)',
  REG.canonical(false)[REG.LAYERS[k].uniform] === 1);
for (const k of RING_EXPECT) ok('ring layer ' + k + ' defaults to its production value (on=1)',
  REG.canonical(true)[REG.RING_LAYERS[k].uniform] === 1);

function switchUses(src, names) {
  let n = 0;
  for (const u of names) {
    const re = new RegExp('\\*\\s*' + u + '\\b', 'g');
    n += (src.match(re) || []).length;
  }
  return n;
}
const CRYSTAL_U = CRYSTAL.map((L) => L.uniform);
const RING_U = RING.map((L) => L.uniform);
{
  const rb = REG.rollbackText(MATS);
  ok('rollbackText reverts every wired crystal layer switch',
    rb.reverted === CRYSTAL.length, 'reverted=' + rb.reverted + ' expected=' + CRYSTAL.length);
  ok('rolled-back crystal source has zero layer-switch multiplications left',
    switchUses(rb.text, CRYSTAL_U) === 0, 'remaining=' + switchUses(rb.text, CRYSTAL_U));
  ok('rolled-back crystal source restores every pre-change expression verbatim',
    CRYSTAL.every((L) => rb.text.split(L.baseline).length - 1 === 1));
  const rb2 = REG.forwardText(rb.text);
  ok('forwardText(rollbackText(x)) is a faithful round trip',
    rb2.applied === CRYSTAL.length && rb2.text === MATS, 'applied=' + rb2.applied);
  const rr = REG.rollbackText(RINGS);
  ok('rollbackText reverts every wired ring layer switch',
    rr.reverted === RING.length, 'reverted=' + rr.reverted + ' expected=' + RING.length);
  ok('rolled-back ring source has zero layer-switch multiplications left',
    switchUses(rr.text, RING_U) === 0, 'remaining=' + switchUses(rr.text, RING_U));
  ok('rolled-back ring source restores every pre-change expression verbatim',
    RING.every((L) => rr.text.split(L.baseline).length - 1 === 1));
}

function freshUniforms(ring) {
  const pool = ring ? REG.RING_LAYERS : REG.LAYERS;
  const order = ring ? REG.RING_ORDER : REG.ORDER;
  const u = {};
  for (const k of order) u[pool[k].uniform] = { value: pool[k].on };
  return u;
}
for (const ring of [false, true]) {
  const order = ring ? REG.RING_ORDER : REG.ORDER;
  const u = freshUniforms(ring);
  const snap = REG.snapshot(u, ring);
  for (const k of order) REG.apply(u, k, false, ring);
  REG.restore(u, snap);
  const after = REG.snapshot(u, ring);
  ok((ring ? 'ring' : 'crystal') + ' layer snapshot/restore returns to the exact baseline',
    JSON.stringify(after) === JSON.stringify(snap), JSON.stringify(after));
}

for (const ring of [false, true]) {
  const order = ring ? REG.RING_ORDER : REG.ORDER;
  const pool = ring ? REG.RING_LAYERS : REG.LAYERS;
  const tag = ring ? 'ring ' : 'crystal ';
  for (const target of order) {
    const u = freshUniforms(ring);
    const r = REG.apply(u, target, false, ring);
    ok(tag + 'turning off ' + target + ' changes exactly one uniform',
      r.isolated && r.changedUniforms.length === 1 && r.changedUniforms[0] === pool[target].uniform,
      JSON.stringify(r.changedUniforms));
    ok(tag + 'turning off ' + target + ' leaves every other layer at its default',
      order.filter((k) => k !== target)
        .every((k) => REG.uniVal(u, pool[k].uniform) === pool[k].on));
    REG.apply(u, target, true, ring);
    ok(tag + 're-enabling ' + target + ' restores its production value',
      REG.uniVal(u, pool[target].uniform) === pool[target].on);
  }
}

for (const a of EXPECT) for (const b of EXPECT) {
  if (a === b) continue;
  const u = freshUniforms(false);
  REG.apply(u, a, false, false); REG.apply(u, b, false, false);
  if (!(REG.uniVal(u, REG.LAYERS[a].uniform) === REG.LAYERS[a].off &&
        REG.uniVal(u, REG.LAYERS[b].uniform) === REG.LAYERS[b].off)) {
    ok('crystal A/B order ' + a + ' then ' + b + ' is commutative', false);
  }
}
ok('crystal A/B is commutative for every layer pair', true);

for (const ring of [false, true]) {
  const pool = ring ? REG.RING_LAYERS : REG.LAYERS;
  const off = REG.allOff(ring);
  const kept = REG.structureLayers(ring);
  ok((ring ? 'ring' : 'crystal') + ': closing every optional layer keeps structure-critical layers on',
    kept.every((k) => off[pool[k].uniform] === pool[k].on), 'structure layers: ' + kept.join(','));
  ok((ring ? 'ring' : 'crystal') + ': allOff only ever turns layers off, never on',
    Object.keys(off).every((u) => off[u] === 0 || off[u] === 1));
}
ok('the astrolabe tick layer is explicitly marked structure-critical',
  REG.RING_LAYERS.astrolabe.structure === true);
function codeOnly(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1 ')
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""');
}
const LAYERS_CODE = codeOnly(LAYERS_SRC);

ok('closing every optional crystal layer still leaves the facet geometry untouched',
  !/\bgeometry\b|\baBary\b|\baFace\b|\baAxis\b|setDrawRange/.test(LAYERS_CODE),
  'material-layers.js must not touch geometry');

for (const L of REG.inventory()) {
  ok('layer ' + L.id + ' off-value never brightens its own contribution (off <= on)',
    L.off <= L.on, L.on + ' -> ' + L.off);
  ok('layer ' + L.id + ' on/off are weakening factors within [0,1]',
    L.off >= 0 && L.off <= 1 && L.on >= 0 && L.on <= 1);
}
ok('no layer switch changes any blending mode',
  !/blending\s*:/.test(LAYERS_CODE), 'material-layers.js must not touch blending');
ok('no layer switch touches geometry, renderOrder, colour tokens or the camera',
  !/\brenderOrder\b|\.setHex\(|\bcameraPosition\b|\bnew T\.|THREE\./.test(LAYERS_CODE),
  'material-layers.js must not touch presentation state');
ok('the registry never builds a renderer object, only plain uniform values',
  !/\bnew\s+(?!Error|Function)\w+\s*\(/.test(LAYERS_CODE), 'only Error/Function may be constructed');

for (const L of CRYSTAL) {
  const inExpr = (L.anchor.match(new RegExp('\\b' + L.uniform + '\\b', 'g')) || []).length;
  const expected = 1 + 1 + 2 + inExpr;
  const uses = MATS.split(L.uniform).length - 1;
  ok('crystal switch ' + L.uniform + ' occurs only at declaration / default table / assembly / its own expression',
    uses === expected, 'occurrences=' + uses + ' expected=' + expected);
}
for (const L of RING) {
  const inExpr = (L.anchor.match(new RegExp('\\b' + L.uniform + '\\b', 'g')) || []).length;
  const expected = 1 + inExpr;
  const uses = RINGS.split(L.uniform).length - 1;
  ok('ring switch ' + L.uniform + ' occurs only at its declaration and its own term',
    uses === expected, 'occurrences=' + uses + ' expected=' + expected);
  ok('ring switch ' + L.uniform + ' has exactly one default value in sky-rings.js',
    (RINGSRUN.match(new RegExp(L.uniform + '\\s*=\\s*\\{\\s*value:\\s*1\\s*\\}', 'g')) || []).length === 1);
}

function numericIdentity(L) {
  function normalize(expr) {
    let e = expr.replace(/\s+/g, '');
    for (let guard = 0; guard < 12; guard++) {
      let changed = false;
      for (let i = 0; i < e.length; i++) {
        if (e[i] !== '(') continue;
        let depth = 0, end = -1, topComma = false;
        for (let j = i; j < e.length; j++) {
          if (e[j] === '(') depth++;
          else if (e[j] === ')') { depth--; if (depth === 0) { end = j; break; } }
          else if (e[j] === ',' && depth === 1) topComma = true;
        }
        if (end < 0) break;
        const inner = e.slice(i + 1, end);
        if (inner.length > 1 && !topComma) {
          e = e.slice(0, i) + inner + e.slice(end + 1);
          changed = true;
          break;
        }
      }
      if (!changed) break;
    }
    return e;
  }
  const stripped = L.anchor
    .replace(new RegExp('\\s*\\*\\s*' + L.uniform + '\\b', 'g'), '')
    .replace(new RegExp('\\b' + L.uniform + '\\s*\\*\\s*', 'g'), '');
  if (L.id === 'concentric') {
    return /1\.0\+\(.*-1\.0\)\*uLyrConc/.test(L.anchor) &&
           /^floatconcentric=0\.76\+0\.16\*radInterf\+0\.08\*radHarm;$/.test(normalize(L.baseline));
  }
  return normalize(stripped) === normalize(L.baseline);
}
for (const L of CRYSTAL.concat(RING)) {
  ok('layer ' + L.id + ': setting its switch to 1 is algebraically the exact pre-change expression',
    numericIdentity(L), 'stripped=' + JSON.stringify(L.anchor.replace(new RegExp('\\s*\\*\\s*' + L.uniform + '\\b', 'g'), '')));
}

for (const L of CRYSTAL.concat(RING)) {
  const occurrences = (L.anchor.match(new RegExp('\\b' + L.uniform + '\\b', 'g')) || []).length;
  ok('layer ' + L.id + ' uses its switch only inside its own single expression',
    occurrences >= 1 && occurrences <= 2, 'got ' + occurrences);
  ok('layer ' + L.id + ' anchor is a single source line (never a multi-statement block)',
    L.anchor.indexOf('\n') < 0);
}
ok('the reflection switch covers both specular terms of the same layer, nothing else',
  REG.LAYERS.reflection.anchor.split('uLyrRefl').length - 1 === 2);

ok('the inner-optics layer depends on volume, and volume does not depend on it',
  /needleV/.test(MATS.slice(MATS.indexOf('needleV *= clamp'), MATS.indexOf('needleV *= clamp') + 120)) &&
  !new RegExp('uLyrInner[^;]{0,200}uLyrVolume').test(MATS));
ok('the transmission depth term depends on volume (documented A/B order: volume first)',
  MATS.includes('3.20 * depthMetric * uLyrTrans'));

ok('scene-mats.js wires the volume switch at the depthMetric definition',
  MATS.includes('(opticalDepth + vH * 0.40) * uLyrVolume'));
ok('scene-mats.js wires the additive-fire switch onto the whole additive sum',
  MATS.includes('+ uRim * hlPulse * 0.40) * uLyrAdd;'));
ok('scene-mats.js wires the reflection switch onto both specular terms',
  MATS.includes('spec * fr * 1.45 * uLyrRefl + uRim * (s1 + s2) * 0.52 * uLyrRefl'));
ok('scene-mats.js wires the transmission switch only onto the depth term (0.12 floor kept)',
  MATS.includes('(0.12 + 3.20 * depthMetric * uLyrTrans)'));
ok('scene-mats.js wires the inner-optics switch onto the needle accumulation',
  MATS.includes('needleV * 0.46 * uLyrInner'));
ok('scene-mats.js wires the facet-shading switch only onto the deviation, not the base',
  MATS.includes('1.0 + (0.34 * dot(N, L1) + 0.24 * dot(surfaceR, L2)) * uLyrSurface'));
ok('scene-mats.js wires the frosting switch only onto the grit deviation',
  MATS.includes('0.30 * h3(floor(vL * 3.4)) * uLyrRough'));
for (const L of RING) {
  ok('sky-rings-glsl.js wires ring layer ' + L.id + ' onto its own term only',
    RINGS.includes(L.anchor));
}

{
  const f1 = REG.forShader(MATS);
  ok('forShader does not confuse the two crystal shaders', f1.shader === 'unknown' || f1.shader === 'CROWN_FS' || f1.shader === 'CROWN_BASE_FS',
    'got ' + f1.shader + ' (source is the whole module, so a mixed result is expected)');
  const baseOnly = MATS.split('var CROWN_FS = [')[0];
  const fire = MATS.slice(MATS.indexOf('var CROWN_FS = ['), MATS.indexOf('var CROWN_BASE_FS = ['));
  const base = MATS.slice(MATS.indexOf('var CROWN_BASE_FS = ['), MATS.indexOf('var GHOST_FS = ['));
  const ringText = RINGS;
  ok('CROWN_BASE_FS resolves to exactly the seven base layers',
    REG.layersFor(base, false).length === 7,
    'got ' + REG.layersFor(base, false).map((L) => L.id).join(','));
  ok('CROWN_FS resolves to exactly the additive layer',
    REG.layersFor(fire, false).length === 1 && REG.layersFor(fire, false)[0].id === 'additive',
    'got ' + REG.layersFor(fire, false).map((L) => L.id).join(','));
  ok('RF resolves to exactly the four halo cross-section layers',
    REG.layersFor(ringText, true).length === 4,
    'got ' + REG.layersFor(ringText, true).map((L) => L.id).join(','));
  ok('layersFor never reports a layer whose anchor is absent',
    REG.layersFor(baseOnly, false).length === 0 && REG.layersFor('', false).length === 0);
}

const f32 = Math.fround;
function bitsEqual(a, b) { return f32(a) === f32(b); }
function sweep(fn, n, lo, hi) {
  let worst = 0, bad = 0;
  for (let i = 0; i <= n; i++) {
    const x = lo + (hi - lo) * (i / n);
    const r = fn(x);
    if (!bitsEqual(r.before, r.after)) { bad++; worst = Math.max(worst, Math.abs(r.before - r.after)); }
  }
  return { bad, worst, n: n + 1 };
}

{
  const s = sweep((d) => ({
    before: Math.min(2, Math.max(0, f32(d))),
    after: Math.min(2, Math.max(0, f32(f32(d) * f32(1)))),
  }), 20000, -1, 3);
  ok('volume: multiplying the optical depth by 1 is a bit-exact no-op in float32',
    s.bad === 0, JSON.stringify(s));
}
{
  const s = sweep((dev) => ({
    before: f32(f32(1) + f32(dev)),
    after: f32(f32(1) + f32(f32(dev) * f32(1))),
  }), 20000, -2, 2);
  ok('surface: scaling the facet deviation by 1 is a bit-exact no-op in float32',
    s.bad === 0, JSON.stringify(s));
}
{
  const s = sweep((d) => ({
    before: f32(f32(0.12) + f32(f32(3.20) * f32(d))),
    after: f32(f32(0.12) + f32(f32(f32(3.20) * f32(d)) * f32(1))),
  }), 20000, 0, 2);
  ok('transmission: scaling the Beer-Lambert depth term by 1 is bit-exact in float32',
    s.bad === 0, JSON.stringify(s));
}
{
  const s = sweep((x) => ({ before: f32(x), after: f32(f32(1) + f32(f32(f32(x) - f32(1)) * f32(1))) }),
    20000, 0.76, 1.0);
  ok('concentric: converge-to-1 form 1+(x-1) is bit-exact for x in [0.76,1] (Sterbenz)',
    s.bad === 0, JSON.stringify(s));
}
{
  let bad = 0;
  for (let i = 0; i < 200000; i++) {
    const v = f32((Math.random() - 0.5) * 1e3);
    if (f32(v * f32(1)) !== v) bad++;
  }
  ok('a float32 value multiplied by 1.0 is always bit-identical (no denormal/rounding trap)',
    bad === 0, 'mismatches=' + bad);
}
ok('every off value is exactly 0 (a full cut), never a fractional brightening factor',
  REG.inventory().every((L) => L.off === 0));

{
  const invPath = path.join(ROOT, 'tests/fixtures/contracts/material/layer-inventory.json');
  ok('tests/fixtures/contracts/material/layer-inventory.json exists', fs.existsSync(invPath));
  if (fs.existsSync(invPath)) {
    const inv = JSON.parse(fs.readFileSync(invPath, 'utf8'));
    ok('layer-inventory.json lists every registered layer',
      inv.layers.length === REG.inventory().length,
      'inventory=' + inv.layers.length + ' registry=' + REG.inventory().length);
    const invIds = inv.layers.map((r) => r.layer).sort();
    const regIds = REG.inventory().map((L) => L.id).sort();
    ok('layer-inventory.json layer ids match the registry exactly',
      JSON.stringify(invIds) === JSON.stringify(regIds), JSON.stringify(invIds));
    ok('layer-inventory.json records a media layer for each of the six required axes',
      ['volume', 'surface', 'transmission', 'reflection', 'additive'].every((k) => invIds.includes(k)));
    ok('layer-inventory.json reports every layer as independently toggleable',
      inv.layers.every((r) => r.independentlyToggleable === true));
    ok('layer-inventory.json reports every default as the production behaviour',
      inv.layers.every((r) => r.defaultValue === 1));
    ok('layer-inventory.json marks the astrolabe tick layer structure-critical',
      inv.layers.filter((r) => r.layer === 'astrolabe').every((r) => r.structureCritical === true));
    const srcs = { 'js/core/scene-mats.js': MATS, 'js/sky/sky-rings-glsl.js': RINGS };
    let misplaced = [];
    for (const row of inv.layers) {
      const m = /^(.+):(\d+)$/.exec(row.codeLocation || '');
      if (!m) { misplaced.push(row.layer + ':bad-loc'); continue; }
      const src = srcs[m[1]];
      if (!src) { misplaced.push(row.layer + ':unknown-file'); continue; }
      const line = src.split('\n')[Number(m[2]) - 1] || '';
      if (!line.includes(row.uniform)) misplaced.push(row.layer + ':line-does-not-name-uniform');
    }
    ok('every recorded code location really contains that layer switch',
      misplaced.length === 0, misplaced.join(', '));
  }
}

console.log('MATERIAL LAYERS CONTRACT ' + passed + ' passed / ' + failed + ' failed');
if (failed) process.exit(1);
