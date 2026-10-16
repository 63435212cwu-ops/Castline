'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');
const context = { window: {} };
for (const name of ['sky-tokens', 'sky-cloud-noise', 'sky-nebula-glsl']) {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../js/sky', name + '.js'), 'utf8'), context);
}
const lib = context.window.CLSkyNebulaGLSL;
const helper = shader => shader.match(/float erodeCloud\(vec4 n,float dm\)\{([^}]+)\}/)[1];
const body = helper(lib.volFrag(4, 0.2, 24));
for (const [oct, steps] of [[3, 14], [0, 0], [4, 0], [4, 1]]) {
  assert.equal(helper(lib.volFrag(oct, 0.2, steps)), body, 'all tiers use the same density law');
}
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const smoothstep = (lo, hi, x) => { const t = clamp((x - lo) / (hi - lo), 0, 1); return t * t * (3 - 2 * t); };
const run = new Function('n', 'dm', 'smoothstep', 'clamp', body.replace(/\bfloat\s+/g, 'const '));
let samples = 0, curves = 0;
function probe(n, label) {
  let previous = -Infinity;
  for (let i = 0; i <= 128; i++) {
    const dm = i * 0.002, value = run(n, dm, smoothstep, clamp);
    if (!(Number.isFinite(value) && value >= -1e-14 && value <= 1 + 1e-14)) {
      assert.fail(label + ': nonphysical density ' + value + ' at support ' + dm);
    }
    if (value < previous - 1e-14) assert.fail(label + ': density decreases as member support increases');
    if (i === 0) assert.equal(value, 0, 'empty space stays empty');
    if (dm >= 0.18) assert.equal(value, 1, 'dense core stays intact');
    previous = value; samples++;
  }
  curves++;
}
for (let mask = 0; mask < 16; mask++) {
  probe({ r: mask & 1, g: (mask >> 1) & 1, b: (mask >> 2) & 1, a: (mask >> 3) & 1 }, 'RGBA corner ' + mask);
}
const texture = context.window.CLSkyCloudNoise.create(THREE), data = texture.image.data;
try {
  for (let i = 0; i < data.length; i += 4) {
    probe({ r: data[i] / 255, g: data[i + 1] / 255, b: data[i + 2] / 255, a: data[i + 3] / 255 }, 'texture texel ' + i / 4);
  }
  for (const r of [.2, .4, .6, .8]) for (const g of [.2, .5, .8]) {
    for (const b of [.2, .5, .8]) for (const a of [.2, .4, .6, .8]) probe({ r, g, b, a }, 'filtered domain');
  }
} finally { texture.dispose(); }
console.log('cloud density PASS · ' + curves + ' curves / ' + samples + ' scalar samples · bounded, monotonic, empty/core fixed points');
