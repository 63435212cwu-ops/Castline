/**
 * @role shell-camera
 * @owns js/sky/sky-shell-camera.js
 * 三视图取景、视口变化、镜头限位与星点投影。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  function create(X) {
    var CONE_MAX = Math.PI * 70 / 180, tmpV = null;
  function refitPlot() {
    if (!X.plot || X.mode === 'compass' || !X.savedCam) return;
    var sc = fresh(X.savedCam); if (sc !== X.savedCam) { X.savedCam.p.copy(sc.p); X.savedCam.t.copy(sc.t); X.savedCam.vp = sc.vp; }
    plotFrame(X.savedCam, false);
  }
  function stageArea() {
    var top = X.hud ? X.hud.querySelector('.sky-top').getBoundingClientRect().bottom : 70, W = g.innerWidth, H = g.innerHeight, w = W - 64 - X.inset.right, dr = X.deckOn() ? X.deckRect() : null;
    if (dr) w = Math.min(w, W - 2 * (dr.left + dr.width + 20));   /* 盘面居中：左侧卡片叠占的宽度两边都让出来 */
    return { width: Math.max(200, w), height: Math.max(200, H - top - 128 - X.inset.bottom) };
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
  function plotFrame(base, reuse) {
    var S = X.scene(); if (!S || !S.camera || !S.controls || !S.flyTo || !g.THREE || !base) return;
    var vk = vpKey() + '|' + X.inset.right + ',' + X.inset.bottom;
    var f = reuse && X.lastFit && X.lastFit.key === vk ? X.lastFit.f : fitAt(base);
    if (isFinite(f) && f > 0) X.lastFit = { key: vk, f: f };
    if (!(isFinite(f) && f > 0)) return;
    var dir = base.p.clone().sub(base.t).multiplyScalar(Math.max(0.6, f * 1.04));
    /* 竖屏要退得更远：临时放宽最远距离与远裁剪面（否则整片星座被裁掉），关闭剧情时复原 */
    S.controls.maxDistance = Math.max(S.controls.maxDistance, dir.length() * 1.2);
    var R0 = ((S.rimInfo && S.rimInfo()) || {}).R || 1200, needFar = dir.length() * 1.2 + R0 * 2.5;
    if (needFar > S.camera.far) { S.camera.far = needFar; S.camera.updateProjectionMatrix(); }
    S.flyTo(base.t.clone().add(dir), base.t.clone(), X.reduced() ? 0.01 : 1.2);
    if (g.CLSkyDeep && CLSkyDeep.setPlotHome) CLSkyDeep.setPlotHome({ p: base.t.clone().add(dir), t: base.t.clone() });   /* 星盘态的「复位」回到这个取景 */
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
    c.minAzimuthAngle = -Infinity; c.maxAzimuthAngle = Infinity;   /* 锥限位接管方位，OrbitControls 自己的方位夹不再插手 */
    c.minPolarAngle = 0.01; c.maxPolarAngle = Math.PI - 0.01;
    S.setOrbitCone({ axis: [0, Math.sin(p), Math.cos(p)], max: CONE_MAX });
    return 'sky';
  }
  function compassArea() { var top = 110, W = g.innerWidth, H = g.innerHeight; return { left: 24, top: top, width: W - 48 - X.inset.right, height: Math.max(160, H - top - 90 - X.inset.bottom) }; }
  /* 星空画布按CSS铺满stage；尺寸与宿主camera/labels共用core.resize的同一份CSS像素，不读布局。 */
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
  /* 每次调用只共享当前画布盒；不跨帧/调用缓存，相机、scene和星的当前位置仍当场读取。 */
  function starScreens(names) {
    var points = Object.create(null); if (!names || !names.length) return points;
    var r = projectionRect(X.scene());
    names.forEach(function (name) { if (name && !Object.prototype.hasOwnProperty.call(points, name)) points[name] = starScreen(name, r); });
    return points;
  }
    return {
      starScreens: starScreens,
      refitPlot: refitPlot,
      stageArea: stageArea,
      vpKey: vpKey,
      fresh: fresh,
      fitAt: fitAt,
      plotFrame: plotFrame,
      applyCamLimits: applyCamLimits,
      compassArea: compassArea,
      starScreen: starScreen
    };
  }
  g.CLSkyShellCamera = { create: create };
})(window);
