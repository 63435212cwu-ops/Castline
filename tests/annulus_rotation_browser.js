/* Actual WebGL geometry, screen-space registration, and picking across poses. */
(function () {
  'use strict';
  var S = window.__cl.scene, V = CLPlotOrbitView, L = CLOrbit3DLayer, A = CLAnnulusSVG;
  var camera = S.camera, spin = L.spinObject(), ctx = A.ctx(), checks = [], poses = [];
  function check(name, ok, detail) { checks.push({ name: name, ok: !!ok, detail: detail }); if (!ok) throw new Error(name + ': ' + JSON.stringify(detail)); }
  function distance(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }
  var saved = { position: camera.position.clone(), quaternion: camera.quaternion.clone(), zoom: camera.zoom,
    view: camera.view ? Object.assign({}, camera.view) : null, spin: spin.rotation.z, focus: A.stats().focus, hover: A.stats().hover,
    safe: L.framing().last && L.framing().last.safe };
  var center = spin.getWorldPosition(new THREE.Vector3()), dist = Math.max(600, camera.position.distanceTo(center));
  function project(x, y, z) {
    var point = new THREE.Vector3(x, y, z).applyMatrix4(spin.matrixWorld).project(camera), size = S.camInfo();
    return [(point.x + 1) * size.W / 2, (1 - point.y) * size.H / 2];
  }
  function pairs(path) {
    return (path.getAttribute('d') || '').replace(/Z$/i, '').replace(/^M/, '').split('L').filter(Boolean).map(function (p) { return p.trim().split(/[ ,]+/).map(Number); });
  }
  var orientations = [[0, -0.25, 1, 0], [0.65, 0.15, 1, 0.8], [-0.70, 0.30, 1, 1.9], [0.15, 0.75, 1, 3.2], [-0.20, -0.75, 1, 4.8], [0.80, -0.15, 1, 5.8]];
  var firstAnchor = null, greatestMove = 0;
  check('real annulus renderer mounted', !!ctx && !!spin, null);
  check('semantic tracks have real depth in the shared spin', spin.children.some(function (mesh) {
    return mesh.name === 'annulus-track-volume' && mesh.userData.annulus.minZ < -1 && mesh.userData.annulus.maxZ === 0;
  }), L.stats().annulus3D);
  try {
    A.setFocus(null); A.setHover(null);
    orientations.forEach(function (pose, index) {
      camera.position.copy(center).add(new THREE.Vector3(pose[0], pose[1], pose[2]).normalize().multiplyScalar(dist));
      camera.lookAt(center); camera.zoom = index % 2 ? 1.15 : 1;
      if (index % 2) camera.setViewOffset(S.camInfo().W, S.camInfo().H, -35, 12, S.camInfo().W, S.camInfo().H);
      else camera.clearViewOffset();
      camera.updateProjectionMatrix();
      L.setSpin(pose[3]);
      // Deliberately do not update camera.matrixWorld: projection/picking must
      // work before the renderer, as they do during a real pointer rotation.
      A.step(0); V.picker().refresh(true); spin.updateWorldMatrix(true, false);
      var maxProjectionError = 0, maxGuideError = 0, maxArcError = 0, maxPickError = 0, maxVolumeError = 0, isolated = 0, hits = 0, domHits = 0, upright = 0;
      var volume = spin.children.filter(function (mesh) { return mesh.name === 'annulus-track-volume'; })[0];
      var vp = volume.geometry.attributes.position, vl = volume.geometry.attributes.aLine, ends = {};
      for (var vi = 0; vi < vp.count; vi += 4) {
        var lineId = volume.userData.annulus.ids[vl.getX(vi)], centerTop = [(vp.getX(vi) + vp.getX(vi + 1)) / 2, (vp.getY(vi) + vp.getY(vi + 1)) / 2, 0];
        if (!ends[lineId]) ends[lineId] = [centerTop, centerTop]; else ends[lineId][1] = centerTop;
      }
      Object.keys(ends).forEach(function (id) {
        var ring = ctx.ringById(id); if (ring.a0 === ring.a1) return;
        ends[id].forEach(function (point, end) {
          var angle = end ? ring.a1 : ring.a0;
          maxVolumeError = Math.max(maxVolumeError, distance(project(point[0], point[1], point[2]), ctx.projectXY(ring.r * Math.cos(angle), ring.r * Math.sin(angle))));
        });
      });
      for (var i = 0; i < 96; i++) {
        var a = i * 0.743, r = ctx.A.R * (0.15 + (i % 11) * 0.085), x = r * Math.cos(a), y = r * Math.sin(a);
        maxProjectionError = Math.max(maxProjectionError, distance(ctx.projectXY(x, y), project(x, y, 0)));
      }
      document.querySelectorAll('.cl-ann-core').forEach(function (path, ci) {
        var pts = pairs(path), radius = ctx.A.R * (ci ? 0.34 : 0.18);
        check('guide samples stay in disc plane at pose ' + index + '/' + ci, pts.length === 97, pts.length);
        pts.forEach(function (p, pi) { var angle = pi / 96 * Math.PI * 2; maxGuideError = Math.max(maxGuideError, distance(p, project(radius * Math.cos(angle), radius * Math.sin(angle), 0))); });
      });
      document.querySelectorAll('.cl-ann-arc').forEach(function (path) {
        var ring = ctx.ringById(path.getAttribute('data-id')), pts = pairs(path);
        if (!ring || !pts.length) return;
        maxArcError = Math.max(maxArcError, distance(pts[0], project(ring.r * Math.cos(ring.a0), ring.r * Math.sin(ring.a0), 0)),
          distance(pts[pts.length - 1], project(ring.r * Math.cos(ring.a1), ring.r * Math.sin(ring.a1), 0)));
        var len = path.getTotalLength();
        [0.19, 0.43, 0.72].some(function (fraction) {
          var p = path.getPointAtLength(len * fraction), hit = document.elementFromPoint(p.x, p.y);
          if (hit && hit.closest && hit.closest('.cl-ann-arc') === path) { domHits++; return true; } return false;
        });
      });
      var rendered = L.pickables().beads.map(function (b) {
        return { event: b.evIdx, line: b.lineId, p: project(b.x, b.y, b.z + (b.liftWeight || 0) * L.beadElevation()) };
      });
      rendered.forEach(function (b, bi) {
        var p = V.picker().screenOf(b.event, b.line);
        if (p) maxPickError = Math.max(maxPickError, distance(p, b.p));
        // The picker resolves nearest centers, with a 0.5px tie window; a 2px
        // gap is unambiguous even when two 10px target areas overlap.
        var near = rendered.some(function (other, oi) { return oi !== bi && other.event !== b.event && distance(b.p, other.p) < 2; });
        if (!near && b.p[0] > 0 && b.p[1] > 0 && b.p[0] < innerWidth && b.p[1] < innerHeight) {
          isolated++; if (V.picker().bead(b.p[0], b.p[1]) === b.event) hits++;
        }
      });
      document.querySelectorAll('.cl-ann-label-path').forEach(function (path) {
        var len = path.getTotalLength(); if (!(len > 1)) return;
        var p0 = path.getPointAtLength(Math.max(0, len / 2 - 0.3)), p1 = path.getPointAtLength(Math.min(len, len / 2 + 0.3));
        check('text follows upright local tangent at pose ' + index, p1.x >= p0.x - 0.015, [p0.x, p1.x]); upright++;
      });
      var anchor = project(ctx.A.R, 0, 0); if (!firstAnchor) firstAnchor = anchor; else greatestMove = Math.max(greatestMove, distance(anchor, firstAnchor));
      var row = { pose: index, maxProjectionError: maxProjectionError, maxGuideError: maxGuideError, maxArcError: maxArcError, maxPickError: maxPickError, maxVolumeError: maxVolumeError, isolated: isolated, hits: hits, domHits: domHits, upright: upright };
      check('true camera/spin/viewOffset projection at pose ' + index, maxProjectionError < 0.00001, row);
      check('3D core guide registration at pose ' + index, maxGuideError < 0.015, row);
      check('semantic arcs register with real track tops at pose ' + index, maxArcError < 0.10, row);
      check('actual GPU track vertices register with the semantic layout at pose ' + index, maxVolumeError < 0.001, row);
      check('elevated WebGL stars and click anchors coincide at pose ' + index, maxPickError < 0.01, row);
      check('unambiguous stars remain clickable at pose ' + index, isolated > 2 && hits === isolated, row);
      check('actual projected paths remain DOM hit targets at pose ' + index, domHits >= 2, row);
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (i = 0; i < 24; i++) {
        a = i / 24 * Math.PI * 2; var rim = project(ctx.A.R * Math.cos(a), ctx.A.R * Math.sin(a), 0);
        minX = Math.min(minX, rim[0]); minY = Math.min(minY, rim[1]); maxX = Math.max(maxX, rim[0]); maxY = Math.max(maxY, rim[1]);
      }
      var origin = project(0, 0, 0), framing = L.setFraming({ x: minX - 24 + 18, y: minY - 24 - 12, w: maxX - minX + 48, h: maxY - minY + 48 });
      check('rotated/viewOffset framing resolves at pose ' + index, framing.ok, framing);
      var disc = L.root(), shifted = disc.position.clone().add(new THREE.Vector3(framing.dxWorld, framing.dyWorld, 0));
      disc.parent.localToWorld(shifted); shifted.project(camera);
      var actualShift = [(shifted.x + 1) * S.camInfo().W / 2 - origin[0], (1 - shifted.y) * S.camInfo().H / 2 - origin[1]];
      check('framing follows screen axes instead of world axes at pose ' + index,
        distance(actualShift, [framing.fit.offsetX, framing.fit.offsetY]) < 0.005, actualShift);
      poses.push(row);
    });
    check('rotation really moves the geometry', greatestMove > 50, greatestMove);
    var budget = CLPlot.annulusBudget();
    check('all original thread identities remain conserved', budget.visible + budget.aggregated === budget.raw && new Set(budget.ids).size === budget.aggregated, budget);
    check('every visible semantic line owns exactly one 3D track', L.stats().annulus3D.lines === ctx.A.rings.filter(function (r) { return r.valid; }).length, L.stats().annulus3D);
    check('3D tracks preserve exact visible semantic identities',
      JSON.stringify(L.stats().annulus3D.ids.slice().sort()) === JSON.stringify(ctx.A.rings.filter(function (r) { return r.valid; }).map(function (r) { return String(r.id); }).sort()), null);
    var hiddenLabel = document.querySelector('.cl-ann-label.is-hidden');
    if (hiddenLabel) {
      var chosenId = hiddenLabel.getAttribute('data-id');
      A.setFocus(chosenId); A.step(0);
      check('choosing a compressed or crowded arc restores its readable graph label', !hiddenLabel.classList.contains('is-hidden') && hiddenLabel.getBoundingClientRect().width > 0, chosenId);
      var arc = ctx.svg.querySelector('.cl-ann-arc[data-id="' + chosenId + '"]');
      if (arc && arc.getTotalLength() < hiddenLabel.getBoundingClientRect().width) {
        check('short-arc callout remains tethered to its real projected anchor', Array.prototype.some.call(document.querySelectorAll('.cl-ann-label-tether'), function (path) { return !!path.getAttribute('d'); }), chosenId);
      }
    }
    var single = Object.assign({}, ctx.A.rings[0]); single.a1 = single.a0; single.events = single.events.slice(0, 1); single.eventCount = 1;
    L.setAnnulus(Object.assign({}, ctx.A, { rings: [single] }));
    check('one-event lines retain a real anchored 3D prism', L.stats().annulus3D.lines === 1 && L.stats().annulus3D.singleEvents === 1, L.stats().annulus3D);
    L.setAnnulus(ctx.A);
  } finally {
    camera.position.copy(saved.position); camera.quaternion.copy(saved.quaternion); camera.zoom = saved.zoom;
    if (saved.view && saved.view.enabled) camera.setViewOffset(saved.view.fullWidth, saved.view.fullHeight, saved.view.offsetX, saved.view.offsetY, saved.view.width, saved.view.height);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix(); camera.updateMatrixWorld(true); L.setSpin(saved.spin);
    L.setAnnulus(ctx.A); if (saved.safe) L.setFraming(saved.safe);
    A.setFocus(saved.focus); A.setHover(saved.hover); A.step(0); V.picker().refresh(true);
  }
  return JSON.stringify({ ok: true, checks: checks.length, poses: poses, maxMovement: greatestMove, volume: L.stats().annulus3D });
})()
