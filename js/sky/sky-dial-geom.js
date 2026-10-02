/*!
 * @role component
 * @owns js/sky/sky-dial-geom.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 星盘拨盘的几何（从 sky-dial.js 拆出，行为不变）：盘面描述缓存 · 投影 · 射线求盘面角 · 命中环判定。只读 sky-disc 的 desc() / anchor()，不写任何东西。
 *  · 映射：回目格 slot ↔ 极角 a（CLSkyModel.angleAt 之逆，与刻度同一映射）；第 c 回占 [c, c+1)，格心 c + 0.5。
 *  · 投影：与 sky-disc 同一组矩阵（相机 × 锚点），屏幕坐标以 #stage 左上为原点。
 *  · 命中环 = 刻度环带（rBez 内 8 px … 盘外缘 E 外 6 px）+ 指针外段（主线环外 8 px 起、离指针 ≤ 11 px）。
 * CLSkyDialGeom = { sync(disc) → D | null, get(), reset(), rect(force), mat(scene), ang(x), slotOf(a), wrap(a), pj(r, a), prAt(a), plane(x, y), hit(x, y, cur, needle), dist(p, q) }
 */
(function (g) {
  'use strict';
  var X3 = g.THREE;
  if (!X3) return;
  /* px：命中带内 / 外延 · 指针外段半宽 · 指针外段离主线环的起点 */
  var BIN = 8, BOUT = 6, NPX = 11, NIN = 8, PI2 = 2 * Math.PI;
  var D = null, dRev = null, rc = null, S = null;
  var M4 = new X3.Matrix4(), Mi = new X3.Matrix4(), V1 = new X3.Vector3(), V2 = new X3.Vector3();

  /* 盘面描述缓存：disc 的 rev() 变了（重建 / 换书 / 视口变）才重取 */
  function sync(d) {
    var r, A = g.CLSkyModel && CLSkyModel.angleAt, q, n, a0, sp;
    if (!d) return (D = null);
    r = d.rev ? d.rev() : 0;
    if (D && D.d === d && dRev === r) return D;
    q = d.desc && d.desc(); if (!q || !q.nCh || !A) return (D = null);
    n = q.nCh; a0 = A(0, n); sp = a0 - A(n, n); dRev = r;
    return (D = { d: d, n: n, rM: q.rMain, rB: q.rBez, E: q.E, z: q.zBez || 0, tk: q.tickLen ? q.tickLen.major : 0.03, a0: a0, sp: sp, dA: sp / n,
      rub: (0.5 * sp / n + Math.PI - sp / 2) * 0.6 * n / sp });   /* 挡板软限位（格）：首 / 尾格心到接缝的 60% */
  }
  function ang(x) { return D.a0 - x * D.dA; }
  function wrap(a) { return a - PI2 * Math.round(a / PI2); }
  /* 极角 → 格位；落在首尾之间的接缝里 → 贴到较近的一端 */
  function slotOf(a) { var d = ((D.a0 - a) % PI2 + PI2) % PI2; if (d > D.sp) d = d - D.sp < (PI2 - D.sp) / 2 ? D.sp : 0; return d / D.dA; }
  function rect(f) { if (f || !rc) rc = D.d.el.parentNode.getBoundingClientRect(); return rc; }
  function mat(sc) { var c, a = D.d.anchor(); S = sc; c = S.camera; M4.multiplyMatrices(c.projectionMatrix, c.matrixWorldInverse).multiply(a.matrixWorld); Mi.copy(a.matrixWorld).invert(); }
  function pj(r, a) {
    var e = M4.elements, x = r * Math.cos(a), y = r * Math.sin(a), z = D.z, w = e[3] * x + e[7] * y + e[11] * z + e[15];
    return w > 1e-6 ? [((e[0] * x + e[4] * y + e[8] * z + e[12]) / w + 1) * rc.width / 2, (1 - (e[1] * x + e[5] * y + e[9] * z + e[13]) / w) * rc.height / 2] : null;
  }
  function dist(p, q) { return p && q ? Math.hypot(p[0] - q[0], p[1] - q[1]) : 0; }
  function prAt(a) { return dist(pj(D.rB, a), pj(D.rB + 0.01, a)) / 0.01; }   /* 该方位刻度环处的径向 px / 单位 */
  /* 屏幕点（client 坐标）→ 射线 → 盘面交点 (r, a)；近乎平行或交在身后 → null */
  function plane(x, y) {
    var c = S.camera, nx = (x - rc.left) / rc.width * 2 - 1, ny = 1 - (y - rc.top) / rc.height * 2, t;
    V1.set(nx, ny, -1).unproject(c).applyMatrix4(Mi); V2.set(nx, ny, 1).unproject(c).applyMatrix4(Mi).sub(V1);
    if (Math.abs(V2.z) < 1e-9 || !((t = (D.z - V1.z) / V2.z) > 0)) return null;
    return { r: Math.hypot(V1.x + V2.x * t, V1.y + V2.y * t), a: Math.atan2(V1.y + V2.y * t, V1.x + V2.x * t) };
  }
  /* cur：当前回（null = 未定）· needle：指针此刻所在格位（拨盘在转时由宿主给，否则 null → 用 cur + 0.5） */
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
