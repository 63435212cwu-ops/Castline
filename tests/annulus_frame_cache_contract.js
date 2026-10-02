/* jsc tests/annulus_frame_cache_contract.js */
(function () {
  'use strict';
  var count = 0;
  function check(value, name) { if (!value) throw new Error(name); count++; }
  var source = read('js/annulus/annulus-svg.js');
  var projection = source.slice(source.indexOf('  function rawProject('), source.indexOf('  function tokenPx('));
  var camera = { x: 430, y: 270, scale: 1, perspective: 0.00041, missing: false };
  var L = { localToGroup: function (x, y) { return [x, y, 0]; } };
  var view = { screenOf: function (p) {
    if (camera.missing) return null;
    var den = 1 + camera.perspective * p[0] + 0.00031 * p[1];
    return [(camera.scale * (0.92 * p[0] - 0.42 * p[1]) + camera.x) / den,
      (camera.scale * (0.16 * p[0] + 0.69 * p[1]) + camera.y) / den];
  } };
  var api = Function('window', 'view', 'var A={R:300},planeProjection=null,projectionKey=null,cacheStats={calibrationReads:0};' + projection +
    '\nreturn {calibrate:calibrateProjection,project:projectXY,stats:cacheStats};')({ CLOrbit3DLayer: L }, view);
  check(api.calibrate() === true, 'initial pose calibrates');
  var max = 0;
  for (var i = 0; i < 160; i++) {
    var angle = i * 0.71831, r = 60 + (i % 12) * 45, x = Math.cos(angle) * r, y = Math.sin(angle) * r;
    var actual = view.screenOf([x, y]), fast = api.project(x, y);
    max = Math.max(max, Math.abs(actual[0] - fast[0]), Math.abs(actual[1] - fast[1]));
  }
  check(max < 1e-7, 'perspective projection mathematically equivalent inside and outside calibration square');
  var reads = api.stats.calibrationReads;
  for (i = 0; i < 100; i++) check(api.calibrate() === false, 'unchanged pose cached ' + i);
  check(api.stats.calibrationReads - reads === 400, 'exactly four real projection calibrations per frame');
  camera.x += 12; check(api.calibrate() === true, 'camera pan invalidates geometry');
  camera.scale = 1.4; check(api.calibrate() === true, 'zoom invalidates geometry');
  camera.perspective += 0.0001; check(api.calibrate() === true, 'perspective change invalidates geometry');
  camera.missing = true; api.calibrate(); check(api.project(20, 30) === null, 'projection loss never reuses stale screen coordinates');
  camera.missing = false; check(api.calibrate() === true, 'projection recovery recalibrates');
  print('ANNULUS-FRAME-CACHE OK · ' + count + ' contracts · max error ' + max);
})();
