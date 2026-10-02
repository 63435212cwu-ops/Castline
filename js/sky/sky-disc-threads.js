/**
 * @role component
 * @owns js/sky/sky-disc-threads.js
 * 参与者光丝、播放归属与SVG后备绘制；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    function threadHex(name) {
      var TK = g.CLSkyTokens, n = C.scene.nodeOf('c:' + name), info = C.scene.skyInfo(), secs = info ? info.sectors : [];
      for (var i = 0; n && i < secs.length; i++) if (secs[i].name === n.camp) return secs[i].color;
      return TK.C.STAR_COOL;
    }
    function setTether(id, names, fromItems) { C.tetherFor = id; C.tetherNames = names || []; C.tetherFrom = fromItems || (id && C.byId[id] ? [C.byId[id]] : null); drawTethers(); }
    function nearestOn(list, sp) {
      var best = null, bd = Infinity;
      list.forEach(function (it) {
        var n = it.sm.length, stepI = Math.max(1, Math.floor(n / 24));
        for (var i = 0; i < n; i += stepI) { var p = C.proj(it.sm[i][0], it.sm[i][1], it.sm[i][2]); if (!p) continue; var dd = (p[0] - sp[0]) * (p[0] - sp[0]) + (p[1] - sp[1]) * (p[1] - sp[1]); if (dd < bd) { bd = dd; best = { p: p, it: it }; } }
        if (C.cursor != null && C.tetherFor == null) { var pc = C.projA(it.r, C.angle(C.cursor + 0.5)); if (pc) { var dc = (pc[0] - sp[0]) * (pc[0] - sp[0]) + (pc[1] - sp[1]) * (pc[1] - sp[1]); if (dc < bd * 4) { bd = dc; best = { p: pc, it: it }; } } }
      });
      return best;
    }
    function drawTethers() {
      var want = (C.state === 'plot' && C.tetherFrom && C.tetherFrom.length) ? C.tetherNames : [];
      var useGl = document.body.classList.contains('skd-gl') && !!g.CLSkyDiscGl, routes = [];
      if (useGl && !C.tethGl) C.tethGl = g.CLSkyDiscGl.create({ scene: C.scene });
      if (useGl) { if (C.tethEls.length) { C.clear(C.gTeth); C.tethEls = []; } }
      else {
        if (C.tethGl) C.tethGl.set([], C.Wv, C.Hv);
        while (C.tethEls.length < want.length) { var gp = C.mk('g', 'sd-tether', C.gTeth); gp.p = C.mk('path', null, gp); gp.c = C.mk('circle', null, gp); gp.c.setAttribute('r', '3.2'); C.tethEls.push(gp); }
      }
      var mid = C.center(), points = C.opts.starScreens ? C.opts.starScreens(want) : Object.create(null);
      function screen(name) {
        if (!name) return null;
        if (!Object.prototype.hasOwnProperty.call(points, name)) points[name] = C.opts.starScreen ? C.opts.starScreen(name) : null;
        return points[name];
      }
      /* 单条线：参与者按绕盘心的方位排序，起点沿弧均匀铺开——成一把扇，而不是全挤在最近的一点 */
      var fan = null;
      if (C.tetherFrom && C.tetherFrom.length === 1 && mid) {
        var it0 = C.tetherFrom[0], pts = it0.sm.map(function (q) { return C.proj(q[0], q[1], q[2]); }).filter(Boolean);
        var stars = want.map(function (nm, i) { var sp = screen(nm); return { i: i, sp: sp, a: sp ? Math.atan2(sp[1] - mid[1], sp[0] - mid[0]) : 0 }; }).filter(function (o) { return o.sp; });
        if (pts.length >= 2 && stars.length) {
          var a0 = Math.atan2(pts[0][1] - mid[1], pts[0][0] - mid[0]), a1 = Math.atan2(pts[pts.length - 1][1] - mid[1], pts[pts.length - 1][0] - mid[0]);
          var dir = ((a1 - a0 + Math.PI * 3) % (Math.PI * 2)) - Math.PI >= 0 ? 1 : -1;
          stars.sort(function (x, y) { var dx = ((x.a - a0 + Math.PI * 4) % (Math.PI * 2)), dy = ((y.a - a0 + Math.PI * 4) % (Math.PI * 2)); return dir > 0 ? dx - dy : dy - dx; });
          fan = {};
          stars.forEach(function (o, k) { var t = stars.length === 1 ? 0.5 : 0.12 + 0.76 * k / (stars.length - 1); fan[o.i] = { p: pts[Math.round(t * (pts.length - 1))], it: it0 }; });
        }
      }
      (useGl ? want : C.tethEls).forEach(function (el, i) {
        var nm = want[i], sp = screen(nm);
        if (!sp) { if (!useGl) el.setAttribute('visibility', 'hidden'); return; }
        var hit = fan ? fan[i] : null;
        /* 播放：这位角色此刻在哪条活跃线里，就从那条线的「此刻」（游标处的光点）连到他；都不在则取最近的活跃线 */
        if (!hit && C.cursor != null && C.tetherFor == null) {
          var own = C.tetherFrom.filter(function (it) { return it.line.cast.indexOf(nm) >= 0; });
          own.sort(function (a, b) { return (a.kind === 'main' ? 1 : 0) - (b.kind === 'main' ? 1 : 0) || a.line.n - b.line.n; });
          var host = own[0];
          if (!host) host = C.tetherFrom.filter(function (it) { return it.kind === 'main'; })[0] || C.tetherFrom[0];   /* 不在任何活跃支线里 → 从主线的「此刻」连出 */
          if (host) { var pc = C.projA(host.r, C.angle(C.cursor + 0.5)); if (pc) hit = { p: pc, it: host }; }
        }
        if (!hit) hit = nearestOn(C.tetherFrom, sp);
        if (!hit) { if (!useGl) el.setAttribute('visibility', 'hidden'); return; }
        var a = hit.p, cx = (a[0] + sp[0]) / 2, cy = (a[1] + sp[1]) / 2;
        if (mid) { cx += (mid[0] - cx) * 0.22; cy += (mid[1] - cy) * 0.22; }
        if (useGl) {
          var TK = g.CLSkyTokens, n = C.scene.nodeOf('c:' + nm);
          routes.push({ name: nm, line: hit.it.id, a: a, b: sp, c: [cx, cy], from: TK.GEN[hit.it.line.gen % TK.GEN.length], to: threadHex(nm), weight: n ? n.w || 0 : 0 });
          return;
        }
        el.setAttribute('visibility', 'visible');
        el.setAttribute('class', 'sd-tether g' + hit.it.line.gen);
        el.p.setAttribute('d', 'M' + a[0].toFixed(1) + ' ' + a[1].toFixed(1) + 'Q' + cx.toFixed(1) + ' ' + cy.toFixed(1) + ' ' + sp[0].toFixed(1) + ' ' + sp[1].toFixed(1));
        el.c.setAttribute('cx', sp[0].toFixed(1)); el.c.setAttribute('cy', sp[1].toFixed(1));
      });
      if (useGl) { routes.sort(function (a, b) { return b.weight - a.weight || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0); }); C.tethGl.set(routes, C.Wv, C.Hv); }
    }

    return { setTether: setTether, drawTethers: drawTethers };
  }
  g.CLSkyDiscThreads = { create: create };
})(window);
