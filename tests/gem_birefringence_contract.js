'use strict';
const assert = require('assert'), fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../js/core/scene-mats.js'), 'utf8');
assert(src.includes('float splitC = clamp(abs(cosC), 0.0, 1.0);'));
assert(src.includes('2.0 * splitC * sqrt(max(0.0, 1.0 - splitC * splitC))'));
let maxError = 0;
for (let i = 0; i <= 20000; i++) {
  const cos = -1 + i / 10000, c = Math.max(0, Math.min(1, Math.abs(cos)));
  const prior = Math.sin(Math.min(3.14159, 2 * Math.acos(c)));
  const current = 2 * c * Math.sqrt(Math.max(0, 1 - c * c));
  assert(Number.isFinite(current) && current >= 0 && current <= 1.0000000001);
  maxError = Math.max(maxError, Math.abs(prior - current));
}
assert(maxError < 2.66e-6, 'closed form differs only within prior rounded-PI residual');
console.log('PASS analytical crystal birefringence · 20,001 ray angles · max split-angle delta ' + (maxError * 0.046));
