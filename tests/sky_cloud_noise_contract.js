/* Run: node tests/sky_cloud_noise_contract.js
 * Offline texture contract using the shipped Three.js, without a DOM or GPU.
 * Checks scalar continuity and resource ownership, not a particular noise
 * formula or rendered appearance. GPU release/performance need browser checks.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const THREE = require('../js/vendor/three.min.js');
const sourcePath = path.join(__dirname, '../js/sky/sky-cloud-noise.js');
const source = fs.readFileSync(sourcePath, 'utf8');
let checks = 0;
function need(value, label) { assert.ok(value, label); checks++; }
function loadFactory() {
  const context = { window: {} };
  vm.runInNewContext(source, context, { filename: sourcePath });
  return context.window.CLSkyCloudNoise;
}
function bytes(texture) {
  const data = texture.image.data;
  return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
}

// No shared mutable texture or payload, including after a fresh module load.
const factory = loadFactory();
need(factory && typeof factory.create === 'function', 'public create(THREE)');
const first = factory.create(THREE), second = factory.create(THREE);
const fresh = loadFactory().create(THREE);
need(first.isDataTexture && first instanceof THREE.DataTexture, 'real Three DataTexture');
need(first !== second && first.uuid !== second.uuid, 'each caller owns a distinct texture');
need(first.image !== second.image && first.image.data !== second.image.data,
  'image records and byte arrays are independently owned');
need(first.image.data.buffer !== second.image.data.buffer, 'no aliased backing storage');
need(bytes(first).equals(bytes(second)), 'same factory is deterministic');
need(bytes(first).equals(bytes(fresh)), 'fresh module load is deterministic');

const { width, height, data } = first.image;
need(width === 256 && height === 256, 'bounded 256-square lookup texture');
need(ArrayBuffer.isView(data) && data.BYTES_PER_ELEMENT === 1 && data.byteLength === width * height * 4,
  'packed RGBA8 storage without extra channels');
need(first.format === THREE.RGBAFormat && first.type === THREE.UnsignedByteType, 'RGBA unsigned-byte upload');
need(first.wrapS === THREE.RepeatWrapping && first.wrapT === THREE.RepeatWrapping, 'both axes repeat');
need(first.magFilter === THREE.LinearFilter, 'linear interpolation when magnified');
need(first.minFilter === THREE.LinearMipmapLinearFilter && first.generateMipmaps === true,
  'trilinear mip filtering when minified');
need(first.encoding === THREE.LinearEncoding, 'scalar noise bypasses sRGB decoding in shipped Three');
need(THREE.NoColorSpace === undefined || first.colorSpace === THREE.NoColorSpace, 'scalar data has no color-space conversion');
need(first.flipY === false && first.unpackAlignment === 1, 'predictable data orientation and row alignment');
need(first.version > 0, 'texture scheduled for initial upload');

function channelStats(component) {
  let sum = 0, sum2 = 0, min = 255, max = 0, clipped = 0;
  const values = new Set(), count = width * height;
  for (let i = component; i < data.length; i += 4) {
    const v = data[i];
    sum += v; sum2 += v * v;
    min = Math.min(min, v); max = Math.max(max, v); values.add(v);
    if (v === 0 || v === 255) clipped++;
  }
  const mean = sum / count;
  return { mean, variance: sum2 / count - mean * mean, min, max,
    levels: values.size, clipped: clipped / count };
}

// Pixel centres need not make the first and last column equal. Instead, the
// repeat interval must be no harder than neighbouring intervals, and changing
// slope across the boundary must not introduce a crease. All values are in
// byte units; +2 permits 8-bit quantization in a second difference.
function seamStats(component, axis) {
  const size = axis === 0 ? width : height, lines = axis === 0 ? height : width;
  let jump = 0, nearJump = 0, curvature = 0, nearCurvature = 0;
  let maxJump = 0, maxNearJump = 0;
  function sample(along, across) {
    along = (along + size) % size;
    const x = axis === 0 ? along : across, y = axis === 0 ? across : along;
    return data[(y * width + x) * 4 + component];
  }
  for (let line = 0; line < lines; line++) {
    const slopes = [];
    for (let at = size - 3; at <= size + 1; at++) {
      slopes.push(sample(at + 1, line) - sample(at, line));
    }
    jump += Math.abs(slopes[2]);
    nearJump += Math.abs(slopes[1]) + Math.abs(slopes[3]);
    maxJump = Math.max(maxJump, Math.abs(slopes[2]));
    maxNearJump = Math.max(maxNearJump, Math.abs(slopes[1]), Math.abs(slopes[3]));
    curvature += Math.abs(slopes[2] - slopes[1]) + Math.abs(slopes[3] - slopes[2]);
    nearCurvature += Math.abs(slopes[1] - slopes[0]) + Math.abs(slopes[4] - slopes[3]);
  }
  return { jump: jump / lines, nearJump: nearJump / (2 * lines), maxJump, maxNearJump,
    curvature: curvature / (2 * lines), nearCurvature: nearCurvature / (2 * lines) };
}

const channels = [], seams = [];
for (let channel = 0; channel < 4; channel++) {
  const s = channelStats(channel), label = 'channel ' + 'RGBA'[channel];
  channels.push(s);
  need(s.mean > 115 && s.mean < 140, label + ' is centred without density bias');
  need(s.min < 64 && s.max > 192, label + ' contains both low and high density');
  need(s.variance > 400 && s.variance < 7000, label + ' retains useful bounded variation');
  need(s.levels > 96 && s.clipped < 0.04, label + ' is continuous, not thresholded/binary');
  for (let axis = 0; axis < 2; axis++) {
    const seam = seamStats(channel, axis), detail = label + ' ' + 'XY'[axis];
    seams.push({ channel: 'RGBA'[channel], axis: 'XY'[axis], ...seam });
    need(seam.jump <= 2 * seam.nearJump + 2, detail + ' repeat has no average jump');
    need(seam.maxJump <= 2 * seam.maxNearJump + 2, detail + ' repeat has no isolated hard edge');
    need(seam.curvature <= 2 * seam.nearCurvature + 2, detail + ' repeat has no slope crease');
  }
}
for (let a = 0; a < 4; a++) {
  for (let b = a + 1; b < 4; b++) {
    let covariance = 0;
    for (let i = 0; i < data.length; i += 4) {
      covariance += (data[i + a] - channels[a].mean) * (data[i + b] - channels[b].mean);
    }
    const correlation = covariance / (width * height) / Math.sqrt(channels[a].variance * channels[b].variance);
    need(Math.abs(correlation) < 0.85, 'channels ' + a + '/' + b + ' are not duplicate density fields');
  }
}

// Mutation and disposal are local to the caller. Observe Three's actual
// dispose event; CPU-only execution cannot claim that GPU bytes were released.
const original = second.image.data[0];
first.image.data[0] = original ^ 255;
need(second.image.data[0] === original && fresh.image.data[0] === original,
  'one owner cannot mutate another owner or future factory output');
let disposedFirst = 0, disposedSecond = 0;
first.addEventListener('dispose', () => { disposedFirst++; });
second.addEventListener('dispose', () => { disposedSecond++; });
first.dispose();
need(disposedFirst === 1 && disposedSecond === 0, 'caller can dispose only its own texture');
need(bytes(second).equals(bytes(fresh)), 'disposing one owner preserves the other payload');
const afterDispose = factory.create(THREE);
need(afterDispose !== first && bytes(afterDispose).equals(bytes(second)),
  'factory remains usable after a caller mutation and disposal');
second.dispose(); fresh.dispose(); afterDispose.dispose();
need(disposedSecond === 1, 'second owner retains its own disposal lifecycle');

console.log(JSON.stringify({ ok: true, checks, three: THREE.REVISION, channels, seams }, null, 2));
