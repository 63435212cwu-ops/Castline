(function (g) {
  'use strict';
  var X3 = g.THREE;
  if (!X3) return;
  var BIN = 8, BOUT = 6, NPX = 11, NIN = 8, PI2 = 2 * Math.PI;
  var D = null, dRev = null, rc = null, S = null;
  var M4 = new X3.Matrix4(), Mi = new X3.Matrix4(), V1 = new X3.Vector3(), V2 = new X3.Vector3();

  function sync(d) {
    var r, A = g.CLSkyModel && CLSkyModel.angleAt, q, n, a0, sp;
    if (!d) return (D = null);
    r = d.rev ? d.rev() : 0;
    if (D && D.d === d && dRev === r) return D;
    q = d.desc && d.desc(); if (!q || !q.nCh || !A) return (D = null);
    n = q.nCh; a0 = A(0, n); sp = a0 - A(n, n); dRev = r;
    return (D = { d: d, n: n, rM: q.rMain, rB: q.rBez, E: q.E, z: q.zBez || 0, tk: q.tickLen ? q.tickLen.major : 0.03, a0: a0, sp: sp, dA: sp / n,
      rub: (0.5 * sp / n + Math.PI - sp / 2) * 0.6 * n / sp });
  }
  function ang(x) { return D.a0 - x * D.dA; }
  function wrap(a) { return a - PI2 * Math.round(a / PI2); }
  function slotOf(a) { var d = ((D.a0 - a) % PI2 + PI2) % PI2; if (d > D.sp) d = d - D.sp < (PI2 - D.sp) / 2 ? D.sp : 0; return d / D.dA; }
  function rect(f) { if (f || !rc) rc = D.d.el.parentNode.getBoundingClientRect(); return rc; }
  function mat(sc) { var c, a = D.d.anchor(); S = sc; c = S.camera; M4.multiplyMatrices(c.projectionMatrix, c.matrixWorldInverse).multiply(a.matrixWorld); Mi.copy(a.matrixWorld).invert(); }
  function pj(r, a) {
    var e = M4.elements, x = r * Math.cos(a), y = r * Math.sin(a), z = D.z, w = e[3] * x + e[7] * y + e[11] * z + e[15];
    return w > 1e-6 ? [((e[0] * x + e[4] * y + e[8] * z + e[12]) / w + 1) * rc.width / 2, (1 - (e[1] * x + e[5] * y + e[9] * z + e[13]) / w) * rc.height / 2] : null;
  }
  function dist(p, q) { return p && q ? Math.hypot(p[0] - q[0], p[1] - q[1]) : 0; }
  function prAt(a) { return dist(pj(D.rB, a), pj(D.rB + 0.01, a)) / 0.01; }
  function plane(x, y) {
    var c = S.camera, nx = (x - rc.left) / rc.width * 2 - 1, ny = 1 - (y - rc.top) / rc.height * 2, t;
    V1.set(nx, ny, -1).unproject(c).applyMatrix4(Mi); V2.set(nx, ny, 1).unproject(c).applyMatrix4(Mi).sub(V1);
    if (Math.abs(V2.z) < 1e-9 || !((t = (D.z - V1.z) / V2.z) > 0)) return null;
    return { r: Math.hypot(V1.x + V2.x * t, V1.y + V2.y * t), a: Math.atan2(V1.y + V2.y * t, V1.x + V2.x * t) };
  }
  function hit(x, y, cur, needle) {
    var h = plane(x, y), pr, dp, zone = '', nx;
    if (!h) return null;
    pr = prAt(h.a); dp = (h.r - D.rB) * pr;
    nx = needle != null ? needle : (cur != null ? cur + 0.5 : null);
    if (dp >= -BIN && dp <= (D.E - D.rB) * pr + BOUT) zone = 'ring';
    else if (nx != null && dp < 0 && (h.r - D.rM) * pr >= NIN && dist(pj(h.r, h.a), pj(h.r, ang(nx))) <= NPX) zone = 'needle';
    return zone ? { zone: zone, slot: slotOf(h.a), a: h.a } : null;
  }

  g.CLSkyDialGeom = {
    sync: sync, get: function () { return D; }, reset: function () { rc = null; }, rect: rect, mat: mat,
    ang: ang, slotOf: slotOf, wrap: wrap, pj: pj, prAt: prAt, plane: plane, hit: hit, dist: dist
  };
})(window);
