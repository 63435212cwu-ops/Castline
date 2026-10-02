(function () {
  'use strict';
  var svg = CLAnnulusSVG, labels = CLAnnulusLabels, marks = CLAnnulusMarks, S = window.__cl.scene;
  var checks = [], root = document.querySelector('.cl-ann-svg');
  function check(name, ok) { checks.push({ name: name, ok: !!ok }); if (!ok) throw new Error(name); }
  check('actual annulus renderer mounted', root && svg.ctx() && svg.stats().arcs > 0);
  svg.step(0);
  var ctx = svg.ctx(), maxError = 0, i;
  for (i = 0; i < 120; i++) {
    var a = i * 0.731, r = ctx.A.R * (0.2 + (i % 13) * 0.083), x = r * Math.cos(a), y = r * Math.sin(a);
    var expected = ctx.view.screenOf(CLOrbit3DLayer.localToGroup(x, y, 0)), actual = ctx.projectXY(x, y);
    maxError = Math.max(maxError, Math.abs(expected[0] - actual[0]), Math.abs(expected[1] - actual[1]));
  }
  check('batched projection equals true Three projection', maxError < 1e-6);
  var before = root.outerHTML, projection = svg.stats().projection;
  var labelBefore = labels.stats(), markBefore = marks.stats();
  var writes = 0, reads = 0, bboxes = 0;
  var oldSet = Element.prototype.setAttribute, oldRect = Element.prototype.getBoundingClientRect, oldBBox = SVGGraphicsElement.prototype.getBBox;
  Element.prototype.setAttribute = function (key, value) { if (root.contains(this)) writes++; return oldSet.call(this, key, value); };
  Element.prototype.getBoundingClientRect = function () { if (root.contains(this)) reads++; return oldRect.call(this); };
  SVGGraphicsElement.prototype.getBBox = function () { if (root.contains(this)) bboxes++; return oldBBox.apply(this, arguments); };
  var frozenMs, movingMs, camX = S.camera.position.x, zoom = S.camera.zoom, focus = svg.stats().focus;
  try {
    var t0 = performance.now();
    for (i = 0; i < 100; i++) svg.step(0);
    frozenMs = (performance.now() - t0) / 100;
    check('100 frozen frames write no repeated SVG geometry', writes === 0);
    check('100 frozen frames trigger no geometry reads', reads === 0 && bboxes === 0);
    check('100 frozen frames preserve every SVG node/label/path', root.outerHTML === before);
    check('frozen marks and labels reuse layouts', labels.stats().layoutPasses === labelBefore.layoutPasses && marks.stats().layoutPasses === markBefore.layoutPasses);
    check('projection work is bounded to four calibration points per frozen frame', svg.stats().projection.calibrationReads - projection.calibrationReads === 400);
    var revision = svg.stats().projection.revision;
    var oldPath = root.querySelector('.cl-ann-arc').getAttribute('d');
    S.camera.position.x += 16; S.camera.updateMatrixWorld(true); svg.step(0);
    check('camera move invalidates geometry and hit paths', svg.stats().projection.revision > revision && root.querySelector('.cl-ann-arc').getAttribute('d') !== oldPath);
    revision = svg.stats().projection.revision; S.camera.zoom *= 1.05; S.camera.updateProjectionMatrix(); svg.step(0);
    check('projection/zoom changes invalidate cached paths', svg.stats().projection.revision > revision);
    var lp = labels.stats().layoutPasses, mp = marks.stats().layoutPasses;
    var line = ctx.A.rings.filter(function (ring) { return ring.valid && String(ring.id) !== String(focus); })[0];
    svg.setFocus(line.id); svg.step(0);
    check('selection expands/reflows real marks and collision labels', marks.stats().layoutPasses > mp && labels.stats().layoutPasses > lp);
    if (document.fonts && document.fonts.dispatchEvent) {
      lp = labels.stats().layoutPasses; document.fonts.dispatchEvent(new Event('loadingdone')); svg.step(0);
      check('late fonts invalidate cached label metrics', labels.stats().layoutPasses > lp);
    }
    t0 = performance.now();
    for (i = 0; i < 12; i++) { S.camera.position.x += 1; S.camera.updateMatrixWorld(true); svg.step(0); }
    movingMs = (performance.now() - t0) / 12;
  } finally {
    Element.prototype.setAttribute = oldSet; Element.prototype.getBoundingClientRect = oldRect; SVGGraphicsElement.prototype.getBBox = oldBBox;
    S.camera.position.x = camX; S.camera.zoom = zoom; S.camera.updateProjectionMatrix(); S.camera.updateMatrixWorld(true);
    svg.setFocus(focus); svg.step(0);
  }
  return JSON.stringify({ ok: true, checks: checks.length, results: checks, maxProjectionError: maxError,
    frozenMs: frozenMs, movingMs: movingMs, svg: svg.stats(), labels: labels.stats(), marks: marks.stats() });
})()
