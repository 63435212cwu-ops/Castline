/*! sky-cloud-noise.js — deterministic, seamless density / curl lookup.
 * @role texture | @owns js/sky/sky-cloud-noise.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * 256 × 256 RGBA8: 262,144 base bytes; 349,524 bytes with the full mip chain.
 * R/G: independent 8/16/32/64-cell fBm; B: broad 4/8/16-cell flow;
 * A: fine 32/64/128-cell detail. Quintic lattice interpolation is periodic
 * in both axes. The data is linear scalar noise, not a colour texture.
 * create(THREE) generates one owned DataTexture: keep it for the owner's
 * lifetime and dispose() with that owner. No GPU resources are shared.
 */
(function (g) {
'use strict';
var SIZE = 256, COUNT = SIZE * SIZE;

/* Integer avalanche hash avoids trigonometric noise and engine-dependent
   accumulated random state. Every channel and octave has its own seed. */
function hash(x, y, seed) {
var n = Math.imul(x, 0x1f123bb5) ^ Math.imul(y, 0x5f356495) ^ seed;
n = Math.imul(n ^ (n >>> 16), 0x7feb352d);
n = Math.imul(n ^ (n >>> 15), 0x846ca68b);
return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}

function octave(field, cells, weight, seed) {
var grid = new Float32Array(cells * cells);
var cell = new Uint16Array(SIZE), fade = new Float32Array(SIZE);
var mask = cells - 1, x, y, i, t, a, b, row0, row1, x0, x1, fy;
for (y = 0; y < cells; y++) {
for (x = 0; x < cells; x++) grid[y * cells + x] = hash(x, y, seed);
}
/* Pixel centres keep the wrapped edge interval identical to every other
   lattice interval; modulo lattice indices also match the seam's slope. */
for (x = 0; x < SIZE; x++) {
t = (x + 0.5) * cells / SIZE;
cell[x] = Math.floor(t); t -= cell[x];
fade[x] = t * t * t * (t * (t * 6 - 15) + 10);
}
for (y = 0; y < SIZE; y++) {
row0 = cell[y] * cells; row1 = ((cell[y] + 1) & mask) * cells;
fy = fade[y];
for (x = 0; x < SIZE; x++) {
x0 = cell[x]; x1 = (x0 + 1) & mask;
a = grid[row0 + x0]; a += (grid[row0 + x1] - a) * fade[x];
b = grid[row1 + x0]; b += (grid[row1 + x1] - b) * fade[x];
i = y * SIZE + x; field[i] += (a + (b - a) * fy) * weight;
}
}
}

function channel(data, component, cells, weights, seed) {
var field = new Float32Array(COUNT), i, value, mean = 0;
for (i = 0; i < cells.length; i++) {
octave(field, cells[i], weights[i], seed ^ Math.imul(i + 1, 0x9e3779b9));
}
for (i = 0; i < COUNT; i++) mean += field[i];
mean /= COUNT;
/* Remove the small finite-grid DC offset. A gentle contrast lift retains
   smooth continuous values rather than thresholding into cellular blobs. */
for (i = 0; i < COUNT; i++) {
value = 0.5 + (field[i] - mean) * 1.35;
data[i * 4 + component] = Math.round(Math.max(0.015, Math.min(0.985, value)) * 255);
}
}

function create(THREE) {
var data = new Uint8Array(COUNT * 4);
channel(data, 0, [8, 16, 32, 64], [0.5, 0.25, 0.16, 0.09], 0x134f71ab);
channel(data, 1, [8, 16, 32, 64], [0.5, 0.25, 0.16, 0.09], 0x672a93cd);
channel(data, 2, [4, 8, 16], [0.58, 0.28, 0.14], 0x38bdf165);
channel(data, 3, [32, 64, 128], [0.52, 0.31, 0.17], 0x71c649e3);
var texture = new THREE.DataTexture(data, SIZE, SIZE, THREE.RGBAFormat, THREE.UnsignedByteType);
texture.name = 'sky-cloud-noise-256';
texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
texture.magFilter = THREE.LinearFilter;
texture.minFilter = THREE.LinearMipmapLinearFilter;
texture.generateMipmaps = true;
texture.anisotropy = 1;
texture.flipY = false;
texture.unpackAlignment = 1;
if (THREE.NoColorSpace !== undefined) texture.colorSpace = THREE.NoColorSpace;
texture.needsUpdate = true;
return texture;
}

g.CLSkyCloudNoise = { create: create };
})(window);
