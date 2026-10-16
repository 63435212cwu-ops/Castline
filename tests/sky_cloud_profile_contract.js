'use strict';
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(require('path').join(__dirname, '../js/sky/sky-nebula-glsl.js'), 'utf8'), context);
const lib = context.window.CLSkyNebulaGLSL;
const body = lib.SPLAT_FS.match(/float splatDensity\(float envelope,float across\)\{([^}]+)\}/)[1];
const density = new Function('envelope', 'across', 'exp', 'pow', body.replace(/\bfloat\s+/g, 'let '));
let max = 0, values = 0;
for (let i = 0; i <= 100; i++) for (let j = -200; j <= 200; j++) {
  const value = density(i / 100, j / 100, Math.exp, Math.pow);
  assert(Number.isFinite(value) && value >= 0 && value <= lib.SPLAT_PEAK + 1e-12);
  if (i === 0) assert.strictEqual(value, 0);
  max = Math.max(max, value); values++;
}
assert(Math.abs(max - lib.SPLAT_PEAK) < 1e-12, 'declared pack limit equals the real shader peak');
const peak = density(1, 0, Math.exp, Math.pow), side = density(1, .3, Math.exp, Math.pow);
assert(peak > side * 2, 'density is redistributed into a strand rather than a flat circular slab');
console.log('PASS ' + values + ' shipped density profile values: finite, nonnegative, empty support, declared peak and directional separation');
