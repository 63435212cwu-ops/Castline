/*!
 * @role component
 * @owns js/orbit3d-pick.js
 * @budget js_ms<=0.3
 * @contract v47
 *
 * CLOrbit3DPick —— ORBIT-3D 屏幕空间拾取与投影缓存（纯数学，无 DOM 监听）。
 *
 * 空间关系（契约 §2）：盘面内容都在 spin 的本地 XY 平面（z≈0），
 * spin 挂在 discRoot 下（rotation.x = −pitch、scale(1, ry, 1)），discRoot 挂在 o.group。
 * 所以珠/弧的「盘面本地坐标」就是正圆坐标 (r·cosθ, r·sinθ, 0)：自转、俯仰、压扁
 * 全部由 spin.matrixWorld 承担，本模块不重算这三件事，只做一次矩阵合成。
 *
 * 投影：mvp = camera.projectionMatrix × camera.matrixWorldInverse × spin.matrixWorld，
 * 之后每个点走裸浮点 4×4，不走 Vector3.project（省掉两次 applyMatrix4 与对象开销），
 * 全程零分配（坐标存在 Float64Array，输出经模块级标量 OX/OY 传递）。
 *
 * 两级缓存（关键：标签每帧要位置，但不需要每帧全量重投影）
 *   ensureMat()  —— 便宜。比对 camera.matrixWorld / projectionMatrix / spin.matrixWorld / W×H，
 *                   变了才重算 mvp 并 gen++（sig() 暴露给 labels 做帧门控）。
 *   ensurePts()  —— 贵。全部珠 + 弧粗采样重投影；只有 bead()/arc() 需要它。
 *   screenOf / screenOfLine / center 只走 ensureMat + 单点投影。
 */
(function (g) {
  'use strict';

  var VERSION = '47';
  var HIT_R = 10;            /* 屏幕拾取半径 px（契约 §3） */
  var HIT2 = HIT_R * HIT_R;
  var TIE = 0.25;            /* 平局判定容差 px²：并列时取 w 更大的珠 */
  var ARC_STEP = 0.09;       /* 弧粗采样角步长 rad（贴圆采样，不两点直连） */
  var ARC_MIN = 2, ARC_MAX = 96;
  var FORK_SEG = 10;         /* tendril 三次 Bezier 采样段数 */

  function fin(v) { return typeof v === 'number' && isFinite(v); }
  function num(v, d) { return fin(v) ? v : d; }
  function now() {
    try { return (g.performance && g.performance.now) ? g.performance.now() : 0; } catch (e) { return 0; }
  }

  /* ---- layer 的自转对象解析：契约给的是 layer.spinObject()，但同批模块在并行落地，
   *      这里按「函数 → 属性 → pickables() 的宿主」逐级探，拿到任何带 matrixWorld 的
   *      Object3D 即可；探不到就整体降级为 not-ready（拾取返回 -1/null，标签自行隐藏）。 */
  var SPIN_KEYS = ['spinObject', 'spinObj', 'spin', 'discSpin', 'disc', 'discRoot', 'root', 'group', 'object3D', 'object'];

  function asObj(v) {
    if (!v || typeof v !== 'object') return null;
    var m = v.matrixWorld;
    return (m && m.elements && m.elements.length === 16) ? v : null;
  }

  function create(layer, geomDesc, scene) {
    var T = g.THREE;
    var sc = scene || (g.__cl && g.__cl.scene) || null;
    var desc = null;

    /* ---- 投影缓存状态 ---- */
    var E = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    var camM = E.slice(), camP = E.slice(), spnM = E.slice();
    var W = 0, H = 0, sigW = -1, sigH = -1, gen = 0, matOk = false, ptsFresh = false;
    var mvp = (T && T.Matrix4) ? new T.Matrix4() : null;
    var vScratch = (T && T.Vector3) ? new T.Vector3() : null;   /* localToWorld 回退路径复用，不每帧新建 */
    var OX = 0, OY = 0;
    var spinCache = null;

    /* ---- 珠 ---- */
    var nb = 0, blx = null, bly = null, blz = null, blw = null, bx = null, by = null, beadLift = 0;
    var bok = null, bval = null, bev = null, bw = null, bmain = null, bline = null;
    var evMap = {};

    /* ---- 弧粗采样（含 tendril） ---- */
    var na = 0, ns = 0;
    var slx = null, sly = null, slz = null, sx = null, sy = null, sok = null;
    var aStartI = null, aCount = null, aId = null, aFork = null;
    var bbx0 = null, bby0 = null, bbx1 = null, bby1 = null, abok = null;

    /* ---- 线 / 段中点（盘面本地） ---- */
    var mids = {}, lineKind = {}, lineIdx = {}, segKeys = {};
    var nLines = 0, nForks = 0;

    /* ---- 计数 ---- */
    var refreshes = 0, builds = 0, lastMs = 0, hits = 0, misses = 0;

    /* =========================== 自转对象 =========================== */
    function resolveSpin() {
      var l = layer, i, k, v, o;
      if (!l) return null;
      o = asObj(l); if (o) return o;
      for (i = 0; i < SPIN_KEYS.length; i++) {
        k = SPIN_KEYS[i];
        try { v = l[k]; } catch (e) { v = null; }
        if (typeof v === 'function') { try { v = v.call(l); } catch (e2) { v = null; } }
        o = asObj(v); if (o) return o;
      }
      if (typeof l.pickables === 'function') {
        try { v = l.pickables(); } catch (e3) { v = null; }
        o = asObj(v); if (o) return o;
        if (v) {
          for (i = 0; i < SPIN_KEYS.length; i++) { o = asObj(v[SPIN_KEYS[i]]); if (o) return o; }
          if (v.length) {
            for (i = 0; i < v.length; i++) {
              var it = v[i];
              o = asObj(it && it.parent ? it.parent : it); if (o) return o;
            }
          }
        }
      }
      return null;
    }
    function spinObj() {
      if (spinCache) return spinCache;
      spinCache = resolveSpin();
      return spinCache;
    }
    function spinAngle() {
      var s = spinCache;
      return (s && s.rotation && fin(s.rotation.z)) ? s.rotation.z : 0;
    }

    /* =========================== 几何装载 =========================== */
    function pushSample(arr, x, y, z) { arr.push(x); arr.push(y); arr.push(z); }

    function bez(p0, c0, c1, p1, t) {
      var u = 1 - t, a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
      return a * p0 + b * c0 + c * c1 + d * p1;
    }

    function build() {
      builds++;
      var arcs = (desc && desc.arcs) || [];
      var beads = (desc && desc.beads) || [];
      var forks = (desc && desc.forks) || [];
      var i, j, k, a, r;

      /* 线索引 */
      mids = {}; lineKind = {}; lineIdx = {}; segKeys = {};
      nLines = arcs.length;
      for (i = 0; i < arcs.length; i++) {
        a = arcs[i];
        if (!a || a.lineId == null) continue;
        lineKind[a.lineId] = a.kind;
        lineIdx[a.lineId] = i;
        var a0 = num(a.aStart, NaN), a1 = num(a.aEnd, NaN), rr = num(a.r, NaN);
        if (fin(a0) && fin(a1) && fin(rr)) {
          var am = (a0 + a1) * 0.5;
          mids[a.lineId] = [rr * Math.cos(am), rr * Math.sin(am), 0];
        }
        var segs = a.segments;
        if (segs && segs.length) {
          var keys = [];
          for (j = 0; j < segs.length; j++) {
            var s0 = num(segs[j] && segs[j].aStart, NaN), s1 = num(segs[j] && segs[j].aEnd, NaN);
            var key = a.lineId + '#' + j;
            keys.push(key);
            if (fin(s0) && fin(s1) && fin(rr)) {
              var sm = (s0 + s1) * 0.5;
              mids[key] = [rr * Math.cos(sm), rr * Math.sin(sm), 0];
            }
          }
          segKeys[a.lineId] = keys;
        }
      }

      /* 珠 */
      var renderedBeads = {}, actualBeads = null;
      try { actualBeads = layer && layer.pickables ? layer.pickables().beads : null; } catch (eB) {}
      if (actualBeads) for (i = 0; i < actualBeads.length; i++) {
        var rendered = actualBeads[i];
        renderedBeads[String(rendered.evIdx) + '|' + String(rendered.lineId)] = rendered;
      }
      nb = beads.length;
      blx = new Float64Array(nb); bly = new Float64Array(nb); blz = new Float64Array(nb); blw = new Float64Array(nb);
      bx = new Float64Array(nb); by = new Float64Array(nb);
      bok = new Uint8Array(nb); bval = new Uint8Array(nb);
      bev = new Int32Array(nb); bw = new Float64Array(nb); bmain = new Uint8Array(nb);
      bline = new Array(nb); evMap = {};
      for (i = 0; i < nb; i++) {
        var b = beads[i] || {};
        a = num(b.angle, NaN); r = num(b.r, NaN);
        var lx = 0, ly = 0;
        if (fin(a) && fin(r)) { lx = r * Math.cos(a); ly = r * Math.sin(a); bval[i] = 1; }
        else if (fin(b.x) && fin(b.y)) { lx = b.x; ly = b.y; bval[i] = 1; }
        else bval[i] = 0;
        blx[i] = lx; bly[i] = ly; blz[i] = num(b.z, 0);
        bev[i] = fin(b.evIdx) ? (b.evIdx | 0) : -1;
        var wv = num(b.w, 0.5); bw[i] = wv < 0 ? 0 : (wv > 1 ? 1 : wv);
        bline[i] = (b.lineId == null) ? '' : b.lineId;
        var actual = renderedBeads[String(bev[i]) + '|' + String(bline[i])];
        if (actual && fin(actual.x) && fin(actual.y) && fin(actual.z)) {
          blx[i] = actual.x; bly[i] = actual.y; blz[i] = actual.z; blw[i] = num(actual.liftWeight, 0);
        }
        bmain[i] = (lineKind[bline[i]] === 'main') ? 1 : 0;
        if (bev[i] >= 0) {
          var lst = evMap[bev[i]];
          if (!lst) { lst = []; evMap[bev[i]] = lst; }
          lst.push(i);
        }
      }

      /* 弧粗采样：按角度贴圆 */
      var pts = [], ids = [], starts = [], counts = [], isFork = [];
      for (i = 0; i < arcs.length; i++) {
        a = arcs[i];
        if (!a || a.lineId == null) continue;
        var q0 = num(a.aStart, NaN), q1 = num(a.aEnd, NaN), qr = num(a.r, NaN);
        if (!fin(q0) || !fin(q1) || !fin(qr)) continue;
        var span = Math.abs(q1 - q0);
        var n = Math.ceil(span / ARC_STEP) + 1;
        if (n < ARC_MIN) n = ARC_MIN;
        if (n > ARC_MAX) n = ARC_MAX;
        starts.push(pts.length / 3); counts.push(n); ids.push(a.lineId); isFork.push(0);
        for (j = 0; j < n; j++) {
          var t = (n === 1) ? 0 : j / (n - 1);
          var qa = q0 + (q1 - q0) * t;
          pushSample(pts, qr * Math.cos(qa), qr * Math.sin(qa), 0);
        }
      }

      /* tendril：三次 Bezier；端点用 fork.rFrom/angle → 支线弧 aStart/rTo。
       * 契约未冻结 P3 的角度，这里取该支线弧的起始角；形状不合理（越界/跳变）就整条丢弃，
       * 宁可少一块拾取面，也不让错误曲线去遮别的弧。 */
      nForks = 0;
      var R = num(desc && desc.R, 0);
      for (i = 0; i < forks.length; i++) {
        var f = forks[i];
        if (!f || f.lineId == null || !f.ctrl || f.ctrl.length < 2) continue;
        var c0 = f.ctrl[0], c1 = f.ctrl[1];
        if (!c0 || !c1 || !fin(c0[0]) || !fin(c0[1]) || !fin(c1[0]) || !fin(c1[1])) continue;
        var fa = num(f.angle, NaN), rf = num(f.rFrom, NaN), rt = num(f.rTo, NaN);
        if (!fin(fa) || !fin(rf) || !fin(rt)) continue;
        var tgt = arcs[lineIdx[f.lineId]];
        var ta = num(tgt && tgt.aStart, fa);
        var x0 = rf * Math.cos(fa), y0 = rf * Math.sin(fa);
        var x3 = rt * Math.cos(ta), y3 = rt * Math.sin(ta);
        var tmp = [], okF = true, px0 = x0, py0 = y0;
        for (j = 0; j <= FORK_SEG; j++) {
          var tt = j / FORK_SEG;
          var vx = bez(x0, c0[0], c1[0], x3, tt), vy = bez(y0, c0[1], c1[1], y3, tt);
          if (!fin(vx) || !fin(vy)) { okF = false; break; }
          var rad = Math.sqrt(vx * vx + vy * vy);
          if (R > 0 && (rad > R * 1.08 || rad < R * 0.18)) { okF = false; break; }
          if (j > 0 && R > 0) {
            var sxx = vx - px0, syy = vy - py0;
            if (Math.sqrt(sxx * sxx + syy * syy) > R * 0.4) { okF = false; break; }
          }
          px0 = vx; py0 = vy;
          tmp.push(vx); tmp.push(vy); tmp.push(0);
        }
        if (!okF) continue;
        starts.push(pts.length / 3); counts.push(FORK_SEG + 1); ids.push(f.lineId); isFork.push(1);
        for (j = 0; j < tmp.length; j++) pts.push(tmp[j]);
        nForks++;
      }

      na = ids.length; ns = pts.length / 3;
      slx = new Float64Array(ns); sly = new Float64Array(ns); slz = new Float64Array(ns);
      sx = new Float64Array(ns); sy = new Float64Array(ns); sok = new Uint8Array(ns);
      for (i = 0; i < ns; i++) { slx[i] = pts[i * 3]; sly[i] = pts[i * 3 + 1]; slz[i] = pts[i * 3 + 2]; }
      aStartI = new Int32Array(na); aCount = new Int32Array(na); aId = new Array(na);
      aFork = new Uint8Array(na);
      bbx0 = new Float64Array(na); bby0 = new Float64Array(na);
      bbx1 = new Float64Array(na); bby1 = new Float64Array(na); abok = new Uint8Array(na);
      for (i = 0; i < na; i++) { aStartI[i] = starts[i]; aCount[i] = counts[i]; aId[i] = ids[i]; aFork[i] = isFork[i]; }
      ptsFresh = false;
    }

    /* =========================== 矩阵与投影 =========================== */
    function camInfoWH() {
      var w = 0, h = 0;
      if (sc && typeof sc.camInfo === 'function') {
        try { var f = sc.camInfo(); if (f) { w = num(f.W, 0); h = num(f.H, 0); } } catch (e) {}
      }
      if (!(w > 0) || !(h > 0)) { w = g.innerWidth || 0; h = g.innerHeight || 0; }
      return w > 0 && h > 0 ? (W = w, H = h, true) : false;
    }
    function same16(a, b) { for (var i = 0; i < 16; i++) { if (a[i] !== b[i]) return false; } return true; }
    function copy16(d, s) { for (var i = 0; i < 16; i++) d[i] = s[i]; }

    function ensureMat() {
      var cam = sc && sc.camera;
      if (!T || !mvp || !cam) { matOk = false; return false; }
      var sp = spinObj();
      if (!sp) { matOk = false; return false; }
      try {
        if (cam.updateMatrixWorld) cam.updateMatrixWorld(true);
        if (sp.updateWorldMatrix) sp.updateWorldMatrix(true, false);
        else if (sp.updateMatrixWorld) sp.updateMatrixWorld();
      } catch (e) {}
      if (!camInfoWH()) { matOk = false; return false; }
      var cm = cam.matrixWorld && cam.matrixWorld.elements;
      var cp = cam.projectionMatrix && cam.projectionMatrix.elements;
      var smx = sp.matrixWorld && sp.matrixWorld.elements;
      var ci = cam.matrixWorldInverse;
      if (!cm || !cp || !smx || !ci) { matOk = false; return false; }
      var nextLift = layer && typeof layer.beadElevation === 'function' ? num(layer.beadElevation(), 0) : 0;
      if (nextLift !== beadLift) { beadLift = nextLift; ptsFresh = false; }
      if (matOk && W === sigW && H === sigH && same16(camM, cm) && same16(camP, cp) && same16(spnM, smx)) return true;
      copy16(camM, cm); copy16(camP, cp); copy16(spnM, smx); sigW = W; sigH = H;
      mvp.multiplyMatrices(cam.projectionMatrix, ci);
      mvp.multiply(sp.matrixWorld);
      copy16(E, mvp.elements);
      matOk = true; ptsFresh = false; gen++;
      return true;
    }

    /* 裸 4×4 投影（列主序）：命中写入模块级 OX/OY，零分配 */
    function px(x, y, z) {
      var w = E[3] * x + E[7] * y + E[11] * z + E[15];
      if (!(w > 1e-6)) return false;
      w = 1 / w;
      var cx = (E[0] * x + E[4] * y + E[8] * z + E[12]) * w;
      var cy = (E[1] * x + E[5] * y + E[9] * z + E[13]) * w;
      if (!fin(cx) || !fin(cy)) return false;
      OX = (cx * 0.5 + 0.5) * W;
      OY = (-cy * 0.5 + 0.5) * H;
      return true;
    }

    function ensurePts() {
      if (!ensureMat()) return false;
      if (ptsFresh) return true;
      var t0 = now(), i, j, k, s, c, x, y;
      for (i = 0; i < nb; i++) {
        if (!bval[i]) { bok[i] = 0; continue; }
        if (px(blx[i], bly[i], blz[i] + blw[i] * beadLift)) { bx[i] = OX; by[i] = OY; bok[i] = 1; }
        else bok[i] = 0;
      }
      for (k = 0; k < na; k++) {
        s = aStartI[k]; c = aCount[k];
        var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = 0;
        for (j = s; j < s + c; j++) {
          if (px(slx[j], sly[j], slz[j])) {
            x = OX; y = OY; sx[j] = x; sy[j] = y; sok[j] = 1; any = 1;
            if (x < x0) x0 = x; if (x > x1) x1 = x;
            if (y < y0) y0 = y; if (y > y1) y1 = y;
          } else sok[j] = 0;
        }
        abok[k] = any;
        bbx0[k] = x0; bby0[k] = y0; bbx1[k] = x1; bby1[k] = y1;
      }
      ptsFresh = true; refreshes++; lastMs = now() - t0;
      return true;
    }

    /* =========================== 拾取 =========================== */
    function segDist2(px0, py0, ax, ay, bx0, by0) {
      var vx = bx0 - ax, vy = by0 - ay, wx = px0 - ax, wy = py0 - ay;
      var vv = vx * vx + vy * vy;
      var t = vv > 1e-9 ? (wx * vx + wy * vy) / vv : 0;
      if (t < 0) t = 0; else if (t > 1) t = 1;
      var dx = wx - vx * t, dy = wy - vy * t;
      return dx * dx + dy * dy;
    }

    function bead(x, y) {
      if (!fin(x) || !fin(y) || !ensurePts()) { misses++; return -1; }
      var best = -1, bd = HIT2 + 1, bwv = -1, i, dx, dy, d;
      for (i = 0; i < nb; i++) {
        if (!bok[i]) continue;
        dx = bx[i] - x; dy = by[i] - y;
        d = dx * dx + dy * dy;
        if (d > HIT2) continue;
        if (d < bd - TIE) { bd = d; best = bev[i]; bwv = bw[i]; }
        else if (d <= bd + TIE && bw[i] > bwv) { if (d < bd) bd = d; best = bev[i]; bwv = bw[i]; }
      }
      if (best < 0) misses++; else hits++;
      return best;
    }

    /* 两趟：先只看真弧，命中就收工；没命中才看 tendril。
     * 为什么不能一趟取最近：tendril 是从主线带横穿到支线车道的，它会压在别的支线弧正上方，
     * 一趟最近会让「指着 A 弧却选中 B 线」（实测 22 条线里有 5 条被须遮住）。
     * 须只在附近没有任何弧时才可拾取，这与视觉上「弧是主体、须是引线」一致。 */
    function scan(x, y, wantFork) {
      var best = null, bd = HIT2 + 1, k, j, s, c, d;
      for (k = 0; k < na; k++) {
        if (aFork[k] !== wantFork) continue;
        if (!abok[k] || aCount[k] < 2) continue;
        if (x < bbx0[k] - HIT_R || x > bbx1[k] + HIT_R || y < bby0[k] - HIT_R || y > bby1[k] + HIT_R) continue;
        s = aStartI[k]; c = aCount[k];
        for (j = s; j < s + c - 1; j++) {
          if (!sok[j] || !sok[j + 1]) continue;
          d = segDist2(x, y, sx[j], sy[j], sx[j + 1], sy[j + 1]);
          if (d < bd) { bd = d; best = aId[k]; }
        }
      }
      return (bd <= HIT2) ? best : null;
    }
    function arc(x, y) {
      if (!fin(x) || !fin(y) || !ensurePts()) return null;
      var hit = scan(x, y, 0);
      return (hit !== null) ? hit : scan(x, y, 1);
    }

    /* 共享事件有多颗珠：给 lineId 取该线上的那颗；不给就取主线珠，再退第一颗 */
    function screenOf(evIdx, lineId) {
      if (!ensureMat()) return null;
      var lst = evMap[evIdx];
      if (!lst || !lst.length) return null;
      var idx = -1, i;
      if (lineId != null && lineId !== '') {
        for (i = 0; i < lst.length; i++) { if (bline[lst[i]] === lineId) { idx = lst[i]; break; } }
      }
      if (idx < 0) { for (i = 0; i < lst.length; i++) { if (bmain[lst[i]]) { idx = lst[i]; break; } } }
      if (idx < 0) idx = lst[0];
      if (!bval[idx]) return null;
      if (bok && ptsFresh && bok[idx]) return [bx[idx], by[idx]];
      return px(blx[idx], bly[idx], blz[idx] + blw[idx] * beadLift) ? [OX, OY] : null;
    }

    function screenOfLine(id) {
      if (id == null || !ensureMat()) return null;
      var m = mids[id];
      if (!m) return null;
      return px(m[0], m[1], m[2]) ? [OX, OY] : null;
    }

    function center() {
      if (!ensureMat()) return null;
      return px(0, 0, 0) ? [OX, OY] : null;
    }

    /* 盘面本地 → 世界坐标：view 做 setStarTargets 时要这一步（契约 §2），
     * 复用同一个 Vector3，不每帧新建。 */
    function worldOf(x, y, z) {
      var sp = spinObj();
      if (!sp || !vScratch || !fin(x) || !fin(y)) return null;
      try {
        if (sp.updateWorldMatrix) sp.updateWorldMatrix(true, false);
        else if (sp.updateMatrixWorld) sp.updateMatrixWorld();
      } catch (e) {}
      vScratch.set(x, y, num(z, 0));
      sp.localToWorld(vScratch);
      return [vScratch.x, vScratch.y, vScratch.z];
    }

    function setGeom(d) { desc = d || null; build(); return api; }
    function rebind(l) { if (l) layer = l; spinCache = null; matOk = false; ptsFresh = false; return !!spinObj(); }

    function stats() {
      return {
        version: VERSION, ready: !!(matOk || ensureMat()), beads: nb, arcs: na, lines: nLines,
        samples: ns, forks: nForks, builds: builds, refreshes: refreshes,
        lastMs: Math.round(lastMs * 1000) / 1000, gen: gen, W: W, H: H,
        hitR: HIT_R, spin: Math.round(spinAngle() * 1000) / 1000,
        spinBound: !!spinCache, hits: hits, misses: misses, fresh: ptsFresh
      };
    }

    var api = {
      version: VERSION,
      refresh: function (force) { if (force) ptsFresh = false; return ensurePts(); },
      bead: bead,
      arc: arc,
      screenOf: screenOf,
      screenOfLine: screenOfLine,
      center: center,
      worldOf: worldOf,
      /* labels 的帧门控：投影矩阵没变就不必重写 transform */
      sig: function () { ensureMat(); return matOk ? gen : -1; },
      geom: function () { return desc; },
      segKeys: function (id) { var k = segKeys[id]; return k ? k.slice() : []; },
      lineKind: function (id) { return lineKind[id] || null; },
      linesOf: function (ev) { var l = evMap[ev], o = [], i; if (!l) return o; for (i = 0; i < l.length; i++) o.push(bline[l[i]]); return o; },
      setGeom: setGeom,
      rebind: rebind,
      hitRadius: function () { return HIT_R; },
      stats: stats
    };

    setGeom(geomDesc);
    spinObj();
    return api;
  }

  g.CLOrbit3DPick = { name: 'CLOrbit3DPick', version: VERSION, HIT_R: HIT_R, create: create };
})(typeof window !== 'undefined' ? window : this);
