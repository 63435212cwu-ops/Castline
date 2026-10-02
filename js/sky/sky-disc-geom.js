/**
 * @role component
 * @owns js/sky/sky-disc-geom.js
 * 剧情车道、弧采样、SVG构建与光层描述；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    function samplesOf(r, a0, a1) {
      var n = Math.max(2, Math.ceil(Math.abs(a0 - a1) / C.STEP) + 1), out = [], i, z = C.zAt(r);
      for (i = 0; i < n; i++) { var a = a0 + (a1 - a0) * i / (n - 1); out.push([r * Math.cos(a), r * Math.sin(a), z]); }
      return out;
    }
    function pathOf(sm, reverse) {
      var d = '', i, p, any = false, n = sm.length;
      for (i = 0; i < n; i++) { var q = sm[reverse ? n - 1 - i : i]; p = C.proj(q[0], q[1], q[2]); if (!p) continue; d += (any ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); any = true; }
      return d;
    }
    function ptsOf(sm) { var out = [], i, p; for (i = 0; i < sm.length; i++) { p = C.proj(sm[i][0], sm[i][1], sm[i][2]); if (p) out.push(p); } return out; }
    function dOfPts(points) { var d = '', i; for (i = 0; i < points.length; i++) d += (i ? 'L' : 'M') + points[i][0].toFixed(1) + ' ' + points[i][1].toFixed(1); return d; }
    function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
    /* 细纹车道：无名细弧自己成带（不再塞进具名车道的空档）——同一把尺、首次适配、同车道相邻区间至少隔 1 回 */
    function grooveLanes(list) {
      var ends = [], lane = {};
      list.slice().sort(function (a, b) { return a.c0 - b.c0 || (b.c1 - b.c0) - (a.c1 - a.c0); }).forEach(function (l) {
        for (var k = 0; k < ends.length; k++) if (ends[k] + 1 < l.c0) { ends[k] = l.c1; lane[l.id] = k; return; }
        ends.push(l.c1); lane[l.id] = ends.length - 1;
      });
      return { n: ends.length, of: lane };
    }

    /* 光层在时细纹弧与事件珠由 WebGL 画、SVG 里本来就透明：不建这些节点（大书约 1000 个），只留命中与名字 */
    function build() {
      C.rev++;
      [C.defs, C.gBezel, C.gDorm, C.gQuiet, C.gNamed, C.gMain, C.gDots, C.gHo, C.gLab, C.gCur, C.gTeth, C.gHit].forEach(clear);
      C.tethEls = []; if (C.tethGl) C.tethGl.set([], C.Wv, C.Hv);
      C.items = []; C.byId = {}; C.geo = null; C.prevKey = ''; C.dirty = true;
      C.builtGl = document.body.classList.contains('skd-gl');
      if (!C.M || !C.M.ok || !C.M.nCh) return;
      /* 由内向外：细纹带（车道 0 贴着具名带，越往里越稀）→ 具名车道（车道 0 贴着主线环）→ 主线环 → 刻度环 */
      var nl = C.M.namedLanes || 0, gv = grooveLanes(C.M.lines.filter(function (l) { return !l.named; })), rq = [], rc = [], r = C.R_IN, k;
      if (!C.P || C.P.nq !== gv.n || C.P.nl !== nl) C.P = C.tune(C.P ? C.P.K : C.estimateK(), gv.n, nl);
      for (k = gv.n - 1; k >= 0; k--) { rq[k] = r + C.P.wq / 2; r += C.P.wq; }
      var grooveOuter = r;
      if (gv.n && nl) r += C.P.gap;
      for (k = nl - 1; k >= 0; k--) { rc[k] = r + C.P.wn / 2; r += C.P.wn; }
      var rMain = r + C.P.mainGap, rBez = rMain + C.P.bez;
      C.geo = { rc: rc, rq: rq, rMain: rMain, rBez: rBez, rNum: rBez + C.P.num, E: rBez + C.P.tail, lanesOuter: r, grooveOuter: grooveOuter, grooveLane: gv.of };
      /* 刻度环：细环 + 每回细刻 + 主刻（≤12 个回数） */
      var ring = { el: C.mk('path', 'sd-ring', C.gBezel), sm: samplesOf(rBez, C.angle(0), C.angle(C.M.nCh)) };
      var step = [1, 2, 5, 10, 20, 25, 50, 100, 200].filter(function (s) { return C.M.nCh / s <= 12; })[0] || 500;
      var ticks = [], majors = [], nums = [];
      for (var c = 0; c <= C.M.nCh; c++) {
        var no = c < C.M.nCh ? C.M.chapters[c].no : C.M.chapters[C.M.nCh - 1].no + 1, major = c === 0 || (c < C.M.nCh && !C.M.chapters[c].special && no % step === 0);
        (major ? majors : ticks).push({ a: C.angle(c), major: major });
        if (major && c < C.M.nCh) { var t = C.mk('text', 'sd-num', C.gBezel); t.textContent = String(no); nums.push({ el: t, a: C.angle(c + 0.5) }); }
      }
      C.geo.ring = ring; C.geo.ticks = { el: C.mk('path', 'sd-tick', C.gBezel), list: ticks }; C.geo.majors = { el: C.mk('path', 'sd-tick is-major', C.gBezel), list: majors }; C.geo.nums = nums;
      /* 卷界：章号分卷重排时（轴为顺序号），在刻度环外写「卷N」 */
      C.geo.vols = ((C.M.axis && C.M.axis.volumes) || []).slice(1).map(function (v) { var t = C.mk('text', 'sd-vol', C.gBezel); t.textContent = v.label; return { el: t, a: C.angle(v.c) }; });
      C.geo.startMark = C.mk('path', 'sd-start', C.gBezel);
      /* 主线：阶段分段粗带；阶段之间的空档 = 同半径点线 */
      C.M.mains.forEach(function (m) { addItem(m, 'main', rMain, 0.05); });
      C.geo.lanes = nl + gv.n;
      var cov = [];
      C.M.mains.forEach(function (m) { cov.push([m.c0, m.c1]); });
      cov.sort(function (a, b) { return a[0] - b[0]; });
      var gaps = [], cur = 0;
      cov.forEach(function (iv) { if (iv[0] > cur) gaps.push([cur, iv[0] - 1]); cur = Math.max(cur, iv[1] + 1); });
      if (cur < C.M.nCh) gaps.push([cur, C.M.nCh - 1]);
      C.geo.dorm = gaps.map(function (gp) { return { el: C.mk('path', 'sd-dormant', C.gDorm), sm: samplesOf(rMain, C.angle(gp[0] + 0.1), C.angle(gp[1] + 0.9)) }; });
      /* 支线：具名在外侧车道，无名细弧在内侧细纹带 */
      var maxN = C.M.lines.reduce(function (a, l) { return Math.max(a, l.named ? l.n : 0); }, 1);
      C.M.lines.forEach(function (l) {
        var rr = l.named ? rc[l.lane] : rq[gv.of[l.id]];
        addItem(l, l.named ? 'named' : 'quiet', rr > 0 ? rr : C.R_IN + C.P.wq / 2, l.named ? 0.14 : 0.18, maxN);
      });
      /* 接棒结 */
      C.geo.hos = C.M.handoffs.map(function (h) {
        var el = C.mk('path', 'sd-knot', C.gHo); el.setAttribute('data-from', h.from); el.setAttribute('data-to', h.to);
        var tt = C.mk('title', null, el); tt.textContent = (h.leadFrom ? h.leadFrom + ' → ' : '') + (h.leadTo || '') + (h.reason ? ' · ' + h.reason : '');
        var to = C.byId[h.to], a = to ? to.a0 : C.angle(h.c);
        return { el: el, a: a + 0.006, h: h };
      });
      /* 游标 */
      C.geo.curMark = C.mk('path', 'sd-cur-mark', C.gCur); C.geo.curNum = C.mk('text', 'sd-cur-num', C.gCur);
      C.geo.comets = [];
      C.svg.setAttribute('data-lines', String(C.items.length));
    }
    function addItem(line, kind, r, pad, maxN) {
      var a0 = C.angle(line.c0 + pad), a1 = C.angle(line.c1 + 1 - pad);
      var it = { id: String(line.id), line: line, kind: kind, r: r, a0: a0, a1: a1, sm: samplesOf(r, a0, a1) };
      var host = kind === 'main' ? C.gMain : kind === 'named' ? C.gNamed : C.gQuiet;
      it.w = kind === 'main' ? C.MAIN_W : kind === 'named' ? C.NAMED_W0 + C.NAMED_W1 * Math.sqrt(line.n / (maxN || 1)) : 1;
      it.el = null;
      if (!(C.builtGl && kind === 'quiet')) {
        it.el = C.mk('path', 'sd-arc is-' + kind + ' g' + line.gen + (line.resolved ? ' is-resolved' : '') + (line.suspended ? ' is-suspended' : ''), host);
        it.el.setAttribute('data-id', it.id);
        /* 主线 / 具名支线用 pathLength=1 做「沿时间画出」；细纹是点线（点距按屏幕 px），不设 pathLength，生长 = 按开始时间依次浮现 */
        if (kind !== 'quiet') it.el.setAttribute('pathLength', '1');
        if (kind !== 'quiet') it.el.style.setProperty('--sd-w', it.w.toFixed(2) + 'px');
        it.el.style.setProperty('--sd-delay', (kind === 'main' ? line.c0 / C.M.nCh * 1.1 : 0.55 + line.c0 / C.M.nCh * 1.35).toFixed(3) + 's');
      }
      it.hit = C.mk('path', 'sd-hit', C.gHit); it.hit.setAttribute('data-id', it.id);
      if (kind !== 'quiet') {
        it.dots = line.events.map(function (ev) {
          var e = null;
          if (!C.builtGl) { e = C.mk('circle', 'sd-dot is-' + kind + ' g' + line.gen, C.gDots); e.setAttribute('r', kind === 'main' ? '1.5' : '1.1'); }
          return { el: e, a: C.angle(evSlot(ev) + 0.5) };
        });
        var id = 'sdlp-' + it.id.replace(/[^\w-]/g, '_');
        it.lp = C.mk('path', null, C.defs); it.lp.setAttribute('id', id);
        it.tx = C.mk('text', 'sd-label is-' + kind + ' g' + line.gen, C.gLab);
        var tp = C.mk('textPath', null, it.tx); tp.setAttribute('href', '#' + id); tp.setAttribute('startOffset', '50%'); tp.textContent = line.label;
        it.tp = tp; it.tw = 0; it.fh = 0;
      }
      C.items.push(it); C.byId[it.id] = it;
    }
    function evSlot(ev) {
      if (!C.evChIdx) { C.evChIdx = {}; C.M.chapterEvents.forEach(function (list, c) { list.forEach(function (i) { C.evChIdx[i] = c; }); }); }
      return C.evChIdx[ev] != null ? C.evChIdx[ev] : 0;
    }


    function descOf() {
      if (!C.M || !C.geo || !C.P) return null;
      var mainIdx = {};
      C.items.forEach(function (it, i) { if (it.kind === 'main') mainIdx[it.id] = i; });
      var list = C.items.map(function (it, i) {
        var l = it.line;
        return { id: it.id, kind: it.kind, r: it.r, z: C.zAt(it.r), a0: it.a0, a1: it.a1, w: it.w, gen: l.gen, c0: l.c0, c1: l.c1, lineIdx: i,
          mainIdx: it.kind === 'main' ? i : (l.mainId != null && mainIdx[String(l.mainId)] != null ? mainIdx[String(l.mainId)] : -1),
          resolved: !!l.resolved, suspended: !!l.suspended, beads: it.dots ? it.dots.map(function (o, k) { return { a: o.a, ev: l.events[k] }; }) : [] };
      });
      var bridges = [], caps = [];
      C.items.forEach(function (it) {
        var l = it.line;
        if (it.kind === 'named') {
          var par = (l.parent != null && C.byId[String(l.parent)]) || (l.mainId != null && C.byId[String(l.mainId)]) || null;
          if (par && par !== it) bridges.push({ a: it.a0, r0: it.r, r1: par.r, z0: C.zAt(it.r), z1: C.zAt(par.r), gen: l.gen });
        }
        if (it.kind !== 'quiet' && (l.resolved || l.suspended)) caps.push({ a: it.a1, r: it.r, z: C.zAt(it.r), kind: l.resolved ? 'resolved' : 'suspended', gen: l.gen });
      });
      return { nCh: C.M.nCh, angle0: C.angle(0), angle1: C.angle(C.M.nCh), rIn: C.R_IN, rMain: C.geo.rMain, rBez: C.geo.rBez, E: C.geo.E, zMain: C.zAt(C.geo.rMain), zBez: C.zAt(C.geo.rBez),
        tickLen: { major: C.P.tick, minor: C.P.tickMinor }, items: list, ticks: C.geo.ticks.list.concat(C.geo.majors.list), bridges: bridges, caps: caps, key: C.items.length + ':' + C.geo.rBez.toFixed(4) };
    }
    return { samplesOf: samplesOf, pathOf: pathOf, ptsOf: ptsOf, dOfPts: dOfPts, clear: clear, build: build, evSlot: evSlot, descOf: descOf };
  }
  g.CLSkyDiscGeom = { create: create };
})(window);
