/**
 * @role component
 * @owns js/sky/sky-disc-project.js
 * 真实盘面锚点、倾角与相机投影矩阵；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    function rimOf() {
      var r = C.scene.rimInfo ? C.scene.rimInfo() : null, R = r && r.R > 0 ? r.R : 0;
      if (!R && r) R = Math.max(r.halfW || 0, r.halfH || 0);
      if (!(R > 0)) R = 600;
      var V = r && r.V > 0 ? r.V : R * 0.62, pitch = r && isFinite(r.pitch) && r.pitch ? r.pitch : 0.46;
      return { R: R, sq: C.clamp(V / R, 0.35, 1), pitch: pitch };
    }
    function ensureAnchor() {
      if (C.anchor || !C.THREE || !C.scene.group) return C.anchor;
      C.anchor = new C.THREE.Object3D(); C.anchor.name = 'sky-disc-plane';
      C.scene.group.add(C.anchor);
      return C.anchor;
    }
    /* backdrop 与星座沿环同一平面；plot 把盘面放平一些（短长轴比 ≈ 0.78）以便读字——仍是 3D，随镜头转 */
    function applyTilt() {
      if (!C.anchor || !C.rim) return;
      /* 盘面倾角与碗深同一条缓动：进剧情态时车道随盘面放平一层层升起，退回背景态时压回星座平面 */
      /* 竖屏（高 > 宽）剧情态更接近正视：宽度吃紧，椭圆更圆才能在屏宽里放下又读得清 */
      var portrait = (g.innerHeight || 1) > (g.innerWidth || 1) * 1.1;
      var k = C.ease(C.tilt), sqP = portrait ? 1 : Math.max(C.rim.sq, 0.9), pitchP = portrait ? Math.min(C.rim.pitch, 0.22) : Math.min(C.rim.pitch, 0.42);
      C.anchor.rotation.set(-(C.rim.pitch + (pitchP - C.rim.pitch) * k), 0, 0);
      var sq = C.rim.sq + (sqP - C.rim.sq) * k;
      C.anchor.scale.set(C.rim.R, C.rim.R * sq, C.rim.R * Math.max(1e-3, k));
      C.anchor.updateWorldMatrix(true, false);
    }
    var PM = null, tmpM = null;
    function computeMatrix() {
      var cam = C.scene.camera; if (!cam || !C.anchor) return null;
      cam.updateMatrixWorld(true);
      if (!PM) { PM = new C.THREE.Matrix4(); tmpM = new C.THREE.Matrix4(); }
      tmpM.multiplyMatrices(cam.matrixWorldInverse, C.anchor.matrixWorld);
      PM.multiplyMatrices(cam.projectionMatrix, tmpM);
      return PM.elements;
    }
    function proj(x, y, z) { var E = C.E, Wv = C.Wv, Hv = C.Hv;
      if (!E) return null;
      z = z || 0;
      var w = E[3] * x + E[7] * y + E[11] * z + E[15]; if (!(w > 1e-6)) return null;
      var px = (E[0] * x + E[4] * y + E[8] * z + E[12]) / w, py = (E[1] * x + E[5] * y + E[9] * z + E[13]) / w;
      return [(px * 0.5 + 0.5) * Wv, (-py * 0.5 + 0.5) * Hv];
    }
    function zAt(r) { var geo = C.geo; if (!geo) return 0; var u = C.clamp((r - C.R_IN * 0.92) / Math.max(1e-3, geo.rMain - C.R_IN * 0.92), 0, 1); return C.LIFT * Math.pow(u, 1.6); }
    function projA(r, a) { return proj(r * Math.cos(a), r * Math.sin(a), zAt(r)); }
    function center() { return proj(0, 0); }

    return { rimOf: rimOf, ensureAnchor: ensureAnchor, applyTilt: applyTilt, computeMatrix: computeMatrix, proj: proj, zAt: zAt, projA: projA, center: center };
  }
  g.CLSkyDiscProject = { create: create };
})(window);
