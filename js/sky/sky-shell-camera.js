(function (g) {
  'use strict';
  function create(X) {
    var CONE_MAX = Math.PI * 70 / 180, tmpV = null;
  function refitPlot() {
    if (!X.plot || X.mode === 'compass' || !X.savedCam) return;
    var sc = fresh(X.savedCam); if (sc !== X.savedCam) { X.savedCam.p.copy(sc.p); X.savedCam.t.copy(sc.t); X.savedCam.vp = sc.vp; }
    plotFrame(X.savedCam, false);
  }
  function stageRect() {
    var W = g.innerWidth || 1200, H = g.innerHeight || 800;
    var top = X.hud ? X.hud.querySelector('.sky-top').getBoundingClientRect().bottom : 70;
    var left = 32, right = W - 32 - X.inset.right;
    var body = X.doc && X.doc.body, rail = X.doc ? X.doc.querySelector('.skg-deck') : null;
    if (rail && !rail.hidden && body) {
      if (W > 960 && body.classList.contains('sk-reading') && !body.classList.contains('sk-rail-peek')) left = Math.max(left, rail.getBoundingClientRect().left + 64 + 20);
      else { var rr = rail.getBoundingClientRect(); if (rr.width > 24) left = Math.max(left, rr.left + rr.width + 20); }
    }
    return { left: Math.round(left), top: Math.round(top), right: Math.round(right), bottom: Math.round(H - 128 - X.inset.bottom) };
  }
  function stageArea() {
    var r = stageRect(), W = g.innerWidth, w = r.right - r.left, dr = X.deckOn() ? X.deckRect() : null;
    if (dr) w = Math.min(w, W - 2 * (dr.left + dr.width + 20));
    return { width: Math.max(200, w), height: Math.max(200, r.bottom - r.top) };
  }
  function readingRect() {
    var W = g.innerWidth || 1200, H = g.innerHeight || 800;
    var s0 = stageRect();
    var left = s0.left, right = s0.right, top = s0.top, bottom = s0.bottom, panels = 0;
    var eL = left, eR = right, eT = top, eB = bottom;
    var list = X.doc ? X.doc.querySelectorAll('#skyDeconPanel,#skyStoryPanel,#skySearchPanel,#skyEnrichPanel,.skd-deck') : [];
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      if (e.hidden) continue;
      if (e.classList && e.classList.contains('skd-pm-out')) continue;
      var cs = g.getComputedStyle ? g.getComputedStyle(e) : null;
      if (cs && (cs.display === 'none' || cs.visibility === 'hidden')) continue;
      var r = e.getBoundingClientRect();
      if (r.width < 24 || r.height < 24) continue;
      panels++;
      var spansMidX = r.left <= W / 2 && r.right >= W / 2;
      var spansMidY = r.top <= H / 2 && r.bottom >= H / 2;
      if (spansMidX && !spansMidY) {
        if (r.top > H / 2) bottom = Math.min(bottom, r.top);
        else top = Math.max(top, r.bottom);
      } else if (r.left > W / 2) right = Math.min(right, r.left);
      else if (r.right < W / 2) left = Math.max(left, r.right);
    }
    var gap = 24;
    if (left > eL) left += gap; if (right < eR) right -= gap;
    var L = Math.min(left, W - 220);
    var R = Math.max(right, L + 220);
    return { left: Math.round(L), top: Math.round(top + 8), right: Math.round(R),
             bottom: Math.round(Math.max(top + 200, bottom - 8)),
             width: Math.max(220, Math.round(R - L)), height: Math.max(200, Math.round(bottom - top - 16)),
             panels: panels };
  }
  function readingArea() { return readingRect(); }
  function readingDelta() {
    var a = readingRect(), s = stageRect();
    var base = { left: s.left, top: s.top + 8, right: s.right,
                 bottom: Math.round(Math.max(s.top + 200, s.bottom - 8)) };
    return { area: a, base: base,
             dx: (a.left + a.right) / 2 - (base.left + base.right) / 2,
             dy: (a.top + a.bottom) / 2 - (base.top + base.bottom) / 2,
             panels: a.panels || 0 };
  }
  function vpKey() { return g.innerWidth + 'x' + g.innerHeight; }
  function fresh(cam) {
    if (!cam || !cam.vp || cam.vp === vpKey()) return cam;
    var h = X.app() && X.app().atlas && X.app().atlas.home ? X.app().atlas.home() : null;
    return h ? { p: h.p.clone(), t: h.t.clone(), vp: vpKey(), maxD: cam.maxD, far: cam.far } : cam;
  }
  function fitAt(base) {
    var S = X.scene(), cp = S.camera.position.clone(), ct = S.controls.target.clone(), cq = S.camera.quaternion.clone();
    S.camera.position.copy(base.p); S.camera.lookAt(base.t); S.camera.updateMatrixWorld(true);
    var f = X.disc.fitFactor(stageArea());
    S.camera.position.copy(cp); S.camera.quaternion.copy(cq); S.controls.target.copy(ct); S.camera.updateMatrixWorld(true);
    return f;
  }
  function plotFrame(base, reuse, onArrive) {
    var S = X.scene(); if (!S || !S.camera || !S.controls || !S.flyTo || !g.THREE || !base) { if (onArrive) onArrive(); return; }
    var vk = vpKey() + '|' + X.inset.right + ',' + X.inset.bottom;
    var dir0 = base.p.clone().sub(base.t);
    var home = X.app() && X.app().atlas && X.app().atlas.home ? X.app().atlas.home() : null;
    var hd = home ? home.p.distanceTo(home.t) : 0, base2 = base;
    if (hd > 0 && dir0.length() > 1e-9 && dir0.length() < hd)
      base2 = { p: base.t.clone().add(dir0.setLength(hd)), t: base.t, vp: base.vp };
    var f = reuse && X.lastFit && X.lastFit.key === vk ? X.lastFit.f : fitAt(base2);
    if (isFinite(f) && f > 0) X.lastFit = { key: vk, f: f };
    if (!(isFinite(f) && f > 0)) { if (onArrive) onArrive(); return; }
    var dir = base2.p.clone().sub(base2.t).multiplyScalar(Math.max(0.6, f * 1.08));
    S.controls.maxDistance = Math.max(S.controls.maxDistance, dir.length() * 1.2);
    var R0 = ((S.rimInfo && S.rimInfo()) || {}).R || 1200, needFar = dir.length() * 1.2 + R0 * 2.5;
    if (needFar > S.camera.far) { S.camera.far = needFar; S.camera.updateProjectionMatrix(); }
    S.flyTo(base.t.clone().add(dir), base.t.clone(), X.reduced() ? 0.01 : 1.2, false, onArrive);
    if (g.CLSkyDeep && CLSkyDeep.setPlotHome) CLSkyDeep.setPlotHome({ p: base.t.clone().add(dir), t: base.t.clone() });
  }
  function applyCamLimits() {
    var S = X.scene(); if (!S || !S.setOrbitCone || !S.controls) return null;
    var c = S.controls;
    if (X.mode === 'compass') {
      S.setOrbitCone(null);
      c.minAzimuthAngle = -Infinity; c.maxAzimuthAngle = Infinity;
      c.minPolarAngle = Math.PI * 20 / 180; c.maxPolarAngle = Math.PI * 160 / 180;
      return 'compass';
    }
    var info = S.skyInfo ? S.skyInfo() : null, p = info && +info.pitch || 0;
    c.minAzimuthAngle = -Infinity; c.maxAzimuthAngle = Infinity;
    c.minPolarAngle = 0.01; c.maxPolarAngle = Math.PI - 0.01;
    S.setOrbitCone({ axis: [0, Math.sin(p), Math.cos(p)], max: CONE_MAX });
    return 'sky';
  }
  function compassArea() { var top = 110, W = g.innerWidth, H = g.innerHeight; return { left: 24, top: top, width: W - 48 - X.inset.right, height: Math.max(160, H - top - 90 - X.inset.bottom), flightDuration: g.CLSkyTokens.DUR.dive }; }
  function projectionRect(S) {
    var cv = X.$('gl'), core = S && S.core && S.core(), w = core && core.getW && core.getW(), h = core && core.getH && core.getH();
    var body = g.document && g.document.body;
    if (body && body.classList.contains('sky-shell') && cv && cv.parentNode && cv.parentNode.id === 'stage' && S && S.renderer && S.renderer.domElement === cv && typeof w === 'number' && typeof h === 'number' && isFinite(w) && isFinite(h) && w > 0 && h > 0 && w === g.innerWidth && h === g.innerHeight) return { width: w, height: h };
    return cv ? cv.getBoundingClientRect() : { left: 0, top: 0, width: g.innerWidth, height: g.innerHeight };
  }
  function starScreen(name, rect) {
    var S = X.scene(), n = S && S.nodeOf && S.nodeOf('c:' + name); if (!n || !n.g || !g.THREE) return null;
    if (!tmpV) tmpV = new g.THREE.Vector3();
    n.g.getWorldPosition(tmpV); tmpV.project(S.camera);
    if (tmpV.z > 1) return null;
    var r = rect || projectionRect(S);
    return [(tmpV.x * 0.5 + 0.5) * r.width, (-tmpV.y * 0.5 + 0.5) * r.height];
  }
  function starScreens(names) {
    var points = Object.create(null); if (!names || !names.length) return points;
    var r = projectionRect(X.scene());
    names.forEach(function (name) { if (name && !Object.prototype.hasOwnProperty.call(points, name)) points[name] = starScreen(name, r); });
    return points;
  }
  function followFrame(points, dur, baseDistance) {
    var S = X.scene(); if (!S || !S.camera || !S.controls || !S.flyTo || !g.THREE || !X.plot || X.mode === 'compass') return null;
    if (!points || !points.length) return null;
    var D = X.disc, anchor = D && D.anchor && D.anchor(); if (!anchor) return null;
    var center = new g.THREE.Vector3();
    if (anchor.getWorldPosition) anchor.getWorldPosition(center); else center.copy(anchor.position);
    var focus = new g.THREE.Vector3(), w = 0;
    points.forEach(function (p, i) {
      var k = i === 0 ? 2 : 1;
      focus.x += p.x * k; focus.y += p.y * k; focus.z += p.z * k; w += k;
    });
    focus.multiplyScalar(1 / w);
    var t0 = S.controls.target, p0 = S.camera.position;
    var t1 = center.clone().add(focus.clone().sub(center).multiplyScalar(0.55));
    var discR = anchor.scale && anchor.scale.x > 0 ? anchor.scale.x : 0;
    var d0 = p0.distanceTo(t0);
    if (d0 < 1e-6) return null;
    var rr = discR > 0 ? Math.min(1, focus.distanceTo(center) / discR) : 0.45;
    var d1 = (baseDistance > 0 ? baseDistance : d0) * Math.max(0.9, Math.min(1.1, 1 + 0.22 * (rr - 0.45)));
    var dMin = +S.controls.minDistance, dMax = +S.controls.maxDistance;
    if (dMin > 0) d1 = Math.max(d1, dMin * 1.05);
    if (isFinite(dMax) && dMax > 0) d1 = Math.min(d1, dMax * 0.95);
    var dir = p0.clone().sub(t1);
    if (dir.length() < 1e-9) return null;
    var p1 = t1.clone().add(dir.setLength(d1));
    var moved = p1.distanceTo(p0) + t1.distanceTo(t0);
    if (moved < Math.max(1e-3, discR * 1e-4)) return null;
    S.flyTo(p1.clone(), t1.clone(), dur);
    return { p: p1, t: t1 };
  }
    return {
      starScreens: starScreens,
      refitPlot: refitPlot,
      stageArea: stageArea,
      readingArea: readingArea,
      readingDelta: readingDelta,
      vpKey: vpKey,
      fresh: fresh,
      fitAt: fitAt,
      plotFrame: plotFrame,
      followFrame: followFrame,
      applyCamLimits: applyCamLimits,
      compassArea: compassArea,
      starScreen: starScreen
    };
  }
  g.CLSkyShellCamera = { create: create };
})(window);
