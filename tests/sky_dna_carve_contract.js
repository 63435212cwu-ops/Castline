'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }

const context = { window: {} };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/sky/sky-nebula-glsl.js'), 'utf8'), context);
const lib = context.window.CLSkyNebulaGLSL;

function carveBody(shader) {
  const m = shader.match(/float dnaCarve\(vec4 f,float re,float fray,float cut\)\{([^}]*)\}/);
  if (!m) { throw new Error('dnaCarve not found in the shipped shader'); }
  return m[1];
}
const shaderOn = lib.splatFrag({ on: true, fray: 1, cut: 1 });
const src = carveBody(shaderOn);
need(src.indexOf('wob') >= 0 && src.indexOf('strand') >= 0, 'the shipped carve carries the rim (wob) and silk (strand) terms');

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const smoothstep = (lo, hi, x) => { const t = clamp((x - lo) / (hi - lo), 0, 1); return t * t * (3 - 2 * t); };
const pow = Math.pow, abs = Math.abs;
const max = Math.max, min = Math.min, mix = (a, b, t) => a + (b - a) * t;
const carve = new Function('f', 're', 'fray', 'cut', 'smoothstep', 'clamp', 'abs', 'pow', 'max', 'min', 'mix',
  src.replace(/\bfloat\s+/g, 'const '));

const deltaCeiling = 0.5 * 1.10 * lib.DNA_RIM_K + 0.5 * 0.62 * lib.DNA_RIM_K + (1 - 0.2778) * lib.DNA_SILK_K;
need(deltaCeiling > 0, 'the radius perturbation has a nonzero analytic ceiling');

const STEP = 1 / 41;
let samples = 0, sumZeroCut = 0, sumFull = 0, nZero = 0, nFull = 0;
let maxWithCut = 0, maxPureRim = 0;

for (let ri = 0; ri <= 41; ri++) {
  for (let gi = 0; gi <= 41; gi++) {
    for (let bi = 0; bi <= 41; bi += 5) {
      for (let ai = 0; ai <= 41; ai += 5) {
        const f = { r: ri * STEP, g: gi * STEP, b: bi * STEP, a: ai * STEP };
        for (const re of [0.35, 0.6, 0.85, 1.0]) {
          const delta = carve(f, re, 0.62, 0.60, smoothstep, clamp, abs, pow, max, min, mix);
          need(Number.isFinite(delta), 'the radius perturbation is finite');
          need(Math.abs(delta) <= deltaCeiling + 1e-9, 'the perturbation stays inside its analytic ceiling');
          const sup = smoothstep(1.02, 0.70, re + delta);
          need(sup >= -1e-12 && sup <= 1 + 1e-12, 'the shifted support stays a valid smoothstep value');
          sumFull += delta; nFull++;
          if (delta > maxWithCut) { maxWithCut = delta; }
          const z = carve(f, re, 0, 0, smoothstep, clamp, abs, pow, max, min, mix);
          need(z === 0, 'a zero-DNA perturbation is exactly zero everywhere (bit-identical identity)');
          sumZeroCut += z; nZero++;
          const rimOnly = carve(f, re, 0.62, 0, smoothstep, clamp, abs, pow, max, min, mix);
          if (rimOnly > maxPureRim) { maxPureRim = rimOnly; }
          samples++;
        }
      }
    }
  }
}

const meanDelta = sumFull / nFull;
need(Math.abs(meanDelta) < 5e-3,
  'the radius perturbation is zero-mean (no global dimming, no global brightening): mean=' + meanDelta.toFixed(5));
need(Math.abs(sumZeroCut / nZero) < 1e-12, 'the zero-DNA path is the exact identity');

const maxAbs = Math.max(maxWithCut, -Math.min(...[maxWithCut]));
need(Math.abs(maxWithCut) > 1e-6, 'the perturbation really moves the boundary');
need(Math.abs(maxPureRim) > 1e-6, 'the rim term alone moves the boundary');
need(samples > 50000, 'the sweep covers the full shared-field domain (' + samples + ' samples)');

const peak = lib.SPLAT_PEAK;
const peakBody = lib.SPLAT_FS.match(/float splatDensity\(float envelope,float across\)\{([^}]+)\}/)[1];
const density = new Function('envelope', 'across', 'exp', 'pow', peakBody.replace(/\bfloat\s+/g, 'let '));
let worst = 0, worstAt = 0;
for (let i = 0; i <= 400; i++) {
  const re = i / 400;
  const envelope = clamp(1 - re * re, 0, 1);
  const dMax = carve({ r: 1, g: 1, b: 0.5, a: 1 }, re, 1, 1, smoothstep, clamp, abs, pow, max, min, mix);
  const dMin = carve({ r: 0, g: 0, b: 0.5, a: 0.5 }, re, 1, 1, smoothstep, clamp, abs, pow, max, min, mix);
  let dmax = 0;
  for (let ac = -200; ac <= 200; ac++) {
    const d = density(envelope, ac / 100, Math.exp, Math.pow);
    if (d > dmax) { dmax = d; }
  }
  const sup = Math.max(smoothstep(1.02, 0.70, re + dMax), smoothstep(1.02, 0.70, re + dMin));
  const k = sup * dmax;
  if (k > worst) { worst = k; worstAt = re; }
}
need(worst <= peak + 1e-9,
  'density x shifted support never exceeds SPLAT_PEAK (8-bit pack ladder stays valid): ' + worst.toFixed(5) + ' at re=' + worstAt.toFixed(3));
need(worst > peak - 1e-6, 'the joint peak still reaches the declared pack limit (headroom unchanged)');

need(shaderOn.indexOf('smoothstep(1.02,0.70,rEff+dnaCarve(') > 0, 'the historical support curve survives inside the DNA shader (perturbed in place, not replaced)');
need(lib.SPLAT_SUPPORT.indexOf('dnaCarve') < 0, 'the historical support constant itself stays uncarved (it is the shared reference)');
need(shaderOn.indexOf(lib.SPLAT_SUPPORT) < 0, 'the DNA shader perturbs that support rather than reusing the bare line');

need(lib.splatFrag(null) === lib.SPLAT_FS + '\n/* dna off */', 'DNA off returns the historical shader text verbatim');
need(lib.splatFrag({ on: false, fray: 1, cut: 1 }) === lib.SPLAT_FS + '\n/* dna off */', 'explicit on:false also returns the historical text');

need(shaderOn.indexOf(lib.DNA_RIM_K.toFixed(4)) > 0, 'the shader carries the exported rim constant');
need(shaderOn.indexOf(lib.DNA_SILK_K.toFixed(4)) > 0, 'the shader carries the exported silk constant');
need(shaderOn.indexOf('smoothstep(1.02,0.70,rEff+dnaCarve(') > 0, 'the DNA shader perturbs the historical support radius in place');

console.log(JSON.stringify({
  ok: true, checks, cpuOnly: true, samples,
  meanDelta: +meanDelta.toFixed(6),
  maxDelta: +maxWithCut.toFixed(5),
  deltaCeiling: +deltaCeiling.toFixed(5),
  densityPeak: worst, declaredPeak: peak
}, null, 2));
