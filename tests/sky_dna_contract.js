'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');

let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }

const BOOKS = [
  ['dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json'],
  ['xiyou', 'data/cache/d16db79a529a1727352091d5.json'],
  ['sanguo', 'data/cache/a935953b2678a80b352091d5.json']
];

function loadContext(search) {
  const context = { THREE, location: { search: search || '' }, matchMedia: () => ({ matches: false }) };
  context.window = context;
  vm.createContext(context);
  for (const name of ['sky-tokens', 'sky-cloud-noise', 'sky-nebula-glsl', 'sky-dna', 'sky-nebula']) {
    const file = path.join(__dirname, '../js/sky', name + '.js');
    vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
  }
  return context;
}

const ctx = loadContext('?dna=on');
const DNA = ctx.CLSkyDNA, T = ctx.CLSkyTokens, GL = ctx.CLSkyNebulaGLSL;
need(typeof DNA.of === 'function' && typeof T.applyDNA === 'function', 'factory DNA + token gate are exported');

{
  const offCtx = loadContext('');
  const onCtx = loadContext('?sky=1&probe=1');
  const onCtx2 = loadContext('?dna=off');
  const onCtx3 = loadContext('?dna=on');
  const g0 = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/sample-saga.json'), 'utf8'));
  need(offCtx.CLSkyDNA.of(g0) === null, 'no URL parameter keeps the historical render path (DNA is opt-in)');
  need(onCtx.CLSkyDNA.of(g0) === null, 'a plain probe URL does not enable DNA');
  need(onCtx2.CLSkyDNA.of(g0) === null, 'dna=off explicitly keeps the historical path');
  need(onCtx3.CLSkyDNA.of(g0) !== null, 'dna=on enables the DNA path');
}

const graphs = BOOKS.map(([alias, rel]) => [alias, JSON.parse(fs.readFileSync(path.join(__dirname, '..', rel), 'utf8'))]);

const computed = graphs.map(([alias, g]) => [alias, g, DNA.of(g)]);

for (const [alias, g, d] of computed) {
  const again = DNA.of(g);
  need(JSON.stringify(again) === JSON.stringify(d), alias + ': same graph computes bit-identical DNA');

  const shuffle = (list, seed) => {
    const out = list.slice(), n = out.length;
    let s = seed;
    for (let i = n - 1; i > 0; i--) { s = (s * 1103515245 + 12345) & 0x7fffffff; const j = s % (i + 1); const t = out[i]; out[i] = out[j]; out[j] = t; }
    return out;
  };
  const shuffled = {
    title: g.title, camps: shuffle(g.camps || [], 7), characters: shuffle(g.characters || [], 13),
    events: shuffle(g.events || [], 17), relations: shuffle(g.relations || [], 23)
  };
  const ds = DNA.of(shuffled);
  need(ds.book === d.book && ds.fingerprint === d.fingerprint, alias + ': identity ignores array order');
  for (const key of T.DNA_KEYS) {
    need(ds[key] === d[key], alias + ': ' + key + ' ignores array order');
  }

  const obs = d.obs;
  need(obs.characters === (g.characters || []).length, alias + ': character count is the graph count');
  need(obs.relations === (g.relations || []).length, alias + ': relation count is the graph count');
  need(obs.events === (g.events || []).length, alias + ': event count is the graph count');
  const chapterLabels = new Set((g.events || []).map(e => String((e && e.chapter) || '')).filter(Boolean));
  need(obs.chapters === chapterLabels.size, alias + ': chapter span is the real label count, not a declared number');
  const campSum = obs.campSizes.reduce((a, b) => a + b, 0);
  const memberSum = (g.camps || []).filter(c => c && c.name).reduce((a, c) => a + ((c.members || []).length), 0);
  need(campSum + obs.fieldMembers === memberSum, alias + ': every camp member is counted exactly once (named camps + field)');

  for (const key of T.DNA_KEYS) {
    const lim = T.DNA_LIMITS[key];
    const v = d[key];
    need(Number.isFinite(v), alias + ': ' + key + ' is finite');
    if (lim) { need(v >= lim[0] - 1e-9 && v <= lim[1] + 1e-9, alias + ': ' + key + ' inside declared limits'); }
  }
  need(Number.isInteger(d.layerBands) && d.layerBands >= 1 && d.layerBands <= 3, alias + ': band count is a declared integer');

  const applied = T.applyDNA(d);
  need(applied && applied.book === d.book, alias + ': token gate accepts a real DNA');
  need(applied.clamped.length === 0, alias + ': real book needs no clamping');
  for (const key of T.DNA_KEYS) { need(applied.fields[key] === d[key], alias + ': token gate passes ' + key + ' through unchanged'); }
}

const [dafeng, xiyou, sanguo] = computed.map(c => c[2]);

need(dafeng.layerBands !== xiyou.layerBands, 'dense relation web and linear journey differ in shell count');
need(dafeng.fray > sanguo.fray && sanguo.fray > xiyou.fray, 'fraying follows relation density (dafeng > sanguo > xiyou)');
need(xiyou.layerBands === 1, 'a book with no extracted relations keeps the single smooth shell (no invented layers)');
need(dafeng.obs.relationDensity > sanguo.obs.relationDensity && sanguo.obs.relationDensity > xiyou.obs.relationDensity,
  'relation density ordering matches the real graphs');
need(dafeng.period < xiyou.period && dafeng.period < sanguo.period,
  'the longest book turns faster than the shorter ones (span drives the modulation)');
for (const [alias, d] of computed.map(c => [c[0], c[2]])) {
  need(d.period >= 1600 && d.period <= 3400, alias + ': the precession period modulates around the historical 2400s instead of changing gear');
  need(Math.abs(d.period / 2400 - 1) < 0.35, alias + ': the period stays within 35% of the historical constant (phase stays comparable)');
}
need(dafeng.bandThick > xiyou.bandThick, 'the longest book carries the thickest galactic band');
need(new Set([dafeng.book, xiyou.book, sanguo.book]).size === 3, 'three books keep three distinct identities');
need(dafeng.book === 'dafeng' && xiyou.book === 'xiyou' && sanguo.book === 'sanguo', 'registered books resolve to their reviewed ids');

const frags = computed.map(([alias, , d]) => [alias, GL.splatFrag({ on: true, fray: d.fray, cut: d.cut })]);
for (const [alias, text] of frags) {
  need(text.indexOf('float dnaCarve(') > 0, alias + ': edge carving reaches the shipped shader');
  need(text.indexOf(GL.SPLAT_SUPPORT) < 0, alias + ': the rigid uniform support is perturbed rather than reused');
  need(/dnaCarve\(field,rEff,[\d.]+,[\d.]+\)/.test(text), alias + ': carve reads the already-sampled shared field');
  need(text.indexOf('splatDensity(float envelope,float across){float strand=0.08+0.92*exp(-80.0*across*across)') > 0,
    alias + ': the density profile itself is untouched (peak contract stays valid)');
  const carve = text.slice(text.indexOf('float dnaCarve('), text.indexOf('void main()'));
  need(carve.indexOf('texture2D') < 0, alias + ': carving adds no texture fetch');
}
const frayText = Object.fromEntries(frags);
need(frayText.dafeng !== frayText.xiyou && frayText.dafeng !== frayText.sanguo,
  'different books compile different carve constants (not a tint)');
need(frayText.dafeng.indexOf('0.6200') > 0 && frayText.xiyou.indexOf('0.1000') > 0,
  'the carve constants are the DNA values themselves');

function nebulaFixture() {
  const scene = new THREE.Scene(), group = new THREE.Group(), nodes = new Map();
  scene.add(group);
  ['甲', '乙', '丙'].forEach((k, i) => { const g = new THREE.Object3D(); g.position.set(i * 20 - 20, i * 7, i * 3); group.add(g); nodes.set('c:' + k, { g }); });
  let target = null;
  const renderer = {
    capabilities: { isWebGL2: true }, autoClear: false,
    getRenderTarget: () => target, setRenderTarget: (v) => { target = v; },
    getClearAlpha: () => 1, getClearColor: (v) => v.setRGB(0, 0, 0), setClearColor: () => {},
    getDrawingBufferSize: (v) => v.set(3840, 2160), clear: () => {}, render: () => {}
  };
  let splatMaterial = null;
  renderer.render = (rendered, camera) => {
    if (camera && camera.isOrthographicCamera) { rendered.traverse(o => { if (o.isPoints) { splatMaterial = o.material; } }); }
  };
  const owner = ctx.CLSkyNebula.create({ scene: { scene, group, camera: new THREE.PerspectiveCamera(), renderer, nodeOf: (k) => nodes.get(k) || null } });
  owner.build({ R: 100, groups: [{ color: 0xeecb78 }, { color: 0x8899dd }, { color: 0x79bdaf }],
    stars: ['甲', '乙', '丙'].map((k, i) => ({ key: k, group: i, w01: 0.8 - i * 0.1 })) });
  owner.setState('show', true);
  return { owner, splatMaterial: () => splatMaterial, volume: () => scene.getObjectByName('sky-nebula-volume') };
}

const nf = nebulaFixture();
nf.owner.setDNA(null);
nf.owner.update(1 / 60, 1 / 60, false);
let stats = nf.owner.stats();
need(stats.dna === false, 'a fresh nebula starts with DNA off (historical path)');
need(nf.splatMaterial(), 'the fixture observes a real splat draw');
need(nf.volume() && nf.volume().material, 'the fixture observes the real volume mesh');
need(nf.splatMaterial().fragmentShader === GL.SPLAT_FS, 'DNA off keeps the exact historical splat shader');

nf.owner.setDNA({ fields: { fray: dafeng.fray, cut: dafeng.cut, layerBands: dafeng.layerBands, lobe: dafeng.lobe } });
nf.owner.update(1 / 60, 1 / 60, false);
stats = nf.owner.stats();
need(stats.dna === true, 'setDNA turns the DNA path on');
need(stats.dnaBands === dafeng.layerBands || stats.dnaBands === T.dnaBands('high', dafeng.layerBands),
  'the DNA band count reaches the instance');
need(nf.splatMaterial().fragmentShader !== GL.SPLAT_FS, 'the DNA path compiles a different splat shader');
need(nf.splatMaterial().fragmentShader.indexOf('dnaCarve') > 0, 'the instance shader really carries the carve');

nf.owner.setTier('low');
need(nf.owner.stats().dnaBands === 1, 'the low tier caps the shell count at one');
nf.owner.setTier('high');
need(nf.owner.stats().dnaBands !== 1 || dafeng.layerBands === 1, 'returning to the high tier restores the DNA shell count');
function lobbyFixture() {
  const scene = new THREE.Scene(), group = new THREE.Group(), nodes = new Map();
  scene.add(group);
  const stars = [];
  for (let i = 0; i < 10; i++) {
    const key = (i < 8 ? 'big' : 'small') + i, g = new THREE.Object3D();
    g.position.set((i - 5) * 9, (i % 3) * 5, 0); group.add(g); nodes.set('c:' + key, { g });
    stars.push({ key, group: i < 8 ? 0 : 1, w01: 0.5 });
  }
  const renderer = { capabilities: { isWebGL2: true }, autoClear: false, getRenderTarget: () => null,
    setRenderTarget: () => {}, getClearAlpha: () => 1, getClearColor: (v) => v.setRGB(0, 0, 0),
    setClearColor: () => {}, getDrawingBufferSize: (v) => v.set(3840, 2160), clear: () => {}, render: () => {} };
  const owner = ctx.CLSkyNebula.create({ scene: { scene, group, camera: new THREE.PerspectiveCamera(), renderer, nodeOf: (k) => nodes.get(k) || null } });
  owner.build({ R: 100, rad: 0.2, groups: [{ color: 0xeecb78 }, { color: 0x8899dd }], stars });
  owner.setState('show', true);
  return owner;
}
const lf = lobbyFixture();
const flat = lf.stats();
need(JSON.stringify(flat.lobeK) === '[1,1]', 'lobe off: every camp gets the historical equal radius multiplier');
const flatRad = flat.radNow0, flatBase = flat.radBase0;
lf.setDNA({ fields: { lobe: 1.46, fray: 0, cut: 0, layerBands: 1 } });
const big = lf.stats();
need(big.lobeK[0] > 1.4 && big.lobeK[1] === 1, 'lobe>1 scales the large camp and leaves the smallest camp at 1');
need(big.radNow0 > flatRad + 1e-6, 'the large camp cloud really grows (camp size becomes readable in space)');
need(Math.abs(big.radBase0 - flatBase) < 1e-9, 'the base radius is untouched: lobe redistributes, it never inflates the whole field');
lf.setDNA({ fields: { lobe: 1.0, fray: 0, cut: 0, layerBands: 1 } });
need(Math.abs(lf.stats().radNow0 - flatRad) < 1e-9, 'setting lobe back to 1 restores the exact historical radius');
lf.setDNA({ fields: { lobe: 1.46, fray: 0, cut: 0, layerBands: 1 } });
need(Math.abs(lf.stats().radNow0 - big.radNow0) < 1e-9, 'repeated lobe changes are idempotent (no accumulated drift)');
lf.setDNA(null);
need(Math.abs(lf.stats().radNow0 - flatRad) < 1e-9 && JSON.stringify(lf.stats().lobeK) === '[1,1]',
  'clearing DNA returns the radii to the historical values');
lf.dispose();

nf.owner.dispose();

const off = GL.splatFrag(null);
need(off === GL.SPLAT_FS + '\n/* dna off */', 'DNA-off shader text is the historical text plus a trailing note');
need(GL.splatFrag({}) === off, 'an empty DNA object still yields the historical text');
need(GL.splatFrag(undefined) === off, 'a missing DNA argument yields the historical text');

const offUniforms = off.match(/uniform\s+\w+\s+\w+/g) || [];
const onUniforms = GL.splatFrag({ on: true, fray: 1, cut: 1 }).match(/uniform\s+\w+\s+\w+/g) || [];
need(JSON.stringify(offUniforms) === JSON.stringify(onUniforms), 'the DNA path declares no new uniform');

need(T.applyDNA(null) === null && T.layer5() === null && T.hasDNA() === false, 'clearing DNA restores the historical fallback');
need(T.dnaNum('period', 240) === 240, 'missing DNA falls back to the caller default, never to a guessed value');

const hostile = T.applyDNA({ book: 'synthetic', layerBands: 9, fray: 99, cut: -4, halo: 'x', period: null, bandThick: 5 });
need(hostile && hostile.fields.layerBands === 3 && hostile.fields.fray === 0.7 && hostile.fields.cut === 0,
  'out-of-range DNA is clamped to the declared limits (negative cut = off, huge fray = ceiling)');
need(hostile.clamped.length >= 4, 'every clamped or unusable field is recorded');
need(hostile.fields.halo === null && hostile.fields.period === null, 'non-numeric DNA fields stay null instead of becoming a default score');
const zeros = T.applyDNA({ book: 'diag', fray: 0, cut: 0, lobe: 0, halo: 0, nodeHalo: 0, layerBands: 1 });
need(zeros.fields.fray === 0 && zeros.fields.cut === 0 && zeros.fields.lobe === 0,
  'an explicit zero really turns a DNA term off instead of snapping to the declared minimum');
const zeroShader = GL.splatFrag({ on: true, fray: 0, cut: 0 });
need(zeroShader === GL.SPLAT_FS + '\n/* dna carve idle */', 'a zeroed carve returns the historical shader verbatim (exact ablation)');
need(zeros.fields.layerBands === 1, 'layerBands still clamps to its declared 1..3 range');
T.applyDNA(null);

(function deepLinkSemantics() {
  const { execFileSync } = require('child_process');
  const PROBE = `
    global.window = global;
    const q = JSON.parse(process.argv[1]);
    global.location = { search: q };
    require(${JSON.stringify(require('path').resolve(__dirname, '..', 'js', 'sky', 'sky-dna.js'))});
    const G = { title: 't', characters: [{ name: 'a' }], events: [], relations: [], camps: [] };
    const r = global.CLSkyDNA.of(G);
    process.stdout.write(JSON.stringify(r === null ? null : { overridden: r.overridden || [] }));
  `;
  const probe = (q) => JSON.parse(execFileSync(process.execPath, ['-e', PROBE, JSON.stringify(q)],
    { encoding: 'utf8' }).trim());
  const tag = 'deep-link';

  need(probe('') === null, tag + ': no dna param means DNA is OFF (whitelist opt-in)');
  need(probe('?dna=off') === null, tag + ': dna=off turns DNA off');
  need(probe('?dna=on') !== null, tag + ': dna=on turns DNA on');
  need(probe('?dna=fray:0,cut:0') === null,
       tag + ': a lone dna=<key>:<value> does NOT enable DNA (closes it entirely)');
  const okOrder = probe('?dna=fray:0,cut:0&dna=on');
  need(okOrder !== null && okOrder.overridden.includes('fray') && okOrder.overridden.includes('cut'),
       tag + ': override BEFORE dna=on is applied');
  const badOrder = probe('?dna=on&dna=fray:0,cut:0');
  need(badOrder !== null && !badOrder.overridden.includes('fray'),
       tag + ': override AFTER dna=on is NOT applied (order matters)');
  const bad = probe('?dna=fray:99&dna=on');
  need(bad !== null, tag + ': an out-of-range override still leaves DNA on');
  checks++;
})();

{
  const minFray = DNA.RANGE.fray[0], minCut = DNA.RANGE.cut[0];
  const atMin = GL.splatFrag({ on: true, fray: minFray, cut: minCut });
  const inertAtMin = atMin.indexOf('dnaCarve') < 0;
  need(!inertAtMin,
    'KNOWN DEFECT still present (pinned): RANGE minimum fray=' + minFray + ' cut=' + minCut +
    ' is NOT inert, so a minimum-valued DNA never reproduces the historical shader and ' +
    'ablation/rollback cannot reach a neutral control. If you just fixed the floors to 0, ' +
    'delete this pin and add a positive assertion that the minimum IS inert. ' +
    'See P06-W05 knownGaps.');
  const dReal = computed[0][2];
  need(GL.splatFrag({ on: true, fray: dReal.fray, cut: dReal.cut }).indexOf('dnaCarve') > 0,
    'a real book still carves (the mechanism is genuinely active at its real values)');
}
T.applyDNA(null);

for (const [alias, , d] of computed) {
  T.applyDNA(d);
  const l5 = T.layer5();
  need(JSON.stringify(T.LAYER5_ORDER.map(k => l5[k].level)) === JSON.stringify([0, 1, 2, 3, 4, 5]), alias + ': the five-level order is fixed by the token, never by DNA');
  need(l5.deep.alpha * 2 <= l5.star.alpha + 1e-9, alias + ': deep sky stays below half the ordinary star (background never grabs focus)');
  for (const k of T.LAYER5_ORDER) { need(l5[k].alpha <= l5.hero.alpha + 1e-9, alias + ': no level outshines the protagonist group (' + k + ')'); }
  for (const k of T.LAYER5_ORDER) { need(l5[k].alpha <= T.LAYER5[k].alpha + 1e-9, alias + ': DNA never raises a level above its declared ceiling (' + k + ')'); }
  need(T.hasDNA() === true, alias + ': tokens report DNA as active');
}
T.applyDNA(null);

console.log(JSON.stringify({
  ok: true, checks, cpuOnly: true,
  books: computed.map(([alias, , d]) => ({
    alias, book: d.book, layerBands: d.layerBands, fray: d.fray, cut: d.cut,
    bandThick: d.bandThick, period: d.period, relationDensity: d.obs.relationDensity, chapters: d.obs.chapters
  }))
}, null, 2));
