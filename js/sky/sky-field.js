/**
 * @role component
 * @owns js/sky/sky-field.js
 * @contract deep-sky/3
 * 星域层：平面天球星座的「势力范围」——扇区界线、团名、组间联系的束线（丝）。
 *  · 与星座同一平面（scene.skyInfo() 的 R / pitch，锚在 scene.group 下），随镜头 3D 转动。
 *  · 扇区 = 一个分组；团名正立横排写在扇区外缘（圆外、朝外对齐），互不压字；
 *  · 组间联系 = 每条跨组关系一根细丝，经两端扇区的轮毂点成束（同一对扇区的丝汇成一股）；组内结构由星座线承担。
 *  · 盘心团（主角团）与各扇区的联系不画成放射细丝，而是每个扇区一束从盘心照出的光（宽度 = 联系数），径向淡出。
 *  · 悬停团名 → 该团星云与星座线提亮、它的丝点亮；点团名 → 选中该团（其余压暗），再点取消。悬停一颗星 → 它的丝点亮。
 *  · 剧情态压暗成底纹（名字与丝隐去），罗盘态隐藏。只读 scene / 视图图谱，不改数据；不私开 rAF（宿主帧钩子调 frame）。
 *  · 光层在时轮廓交给 CLSkyFieldGl（与星同一次投影），SVG 不再逐帧改写；团名各自一层，逐帧只改平移 / 透明度（Q5.6）。
 *  · 换分组：旧团名淡出，新团名自 12 点顺时针错峰发丝描出，与光层扇区边同一节拍；减弱动效 / low 直达终态（Q8.3）。
 */
(function (g) {
  'use strict';
  var TAU = Math.PI * 2, STEP = 3 * Math.PI / 180, SILK_MAX = 150, POOL_MAX = 1400, BETA = 0.86, PAD = 16;
  var mk = g.CLSkyUtil.svg;
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function hex(c) { var s = (Number(c) >>> 0).toString(16); while (s.length < 6) s = '0' + s; return '#' + s.slice(-6); }
  function TK() { return g.CLSkyTokens || null; }
  function dur(k, d) { var t = TK(); return t && t.DUR && t.DUR[k] ? t.DUR[k] : d; }

  function create(opts) {
    var scene = opts.scene, app = opts.app, THREE = g.THREE, stage = opts.stage || document.getElementById('stage') || document.body;
    var info = null, anchor = null, E = null, PM = null, TM = null, Wv = 0, Hv = 0, prevKey = '', state = 'show', dead = false;
    var secs = [], silk = [], pool = [], nStrong = 0, silkBy = {}, hotCamp = null, hoverStar = null, v3 = null, L = {}, liveUntil = 0;
    var glo = null, useGl = false, vbKey = '', graphRef = null, leaving = [], drawUntil = 0, lastT = 0, draws = 0, sliding = false;
    function now() { return g.CLSkyUtil.nowMs(0); }
    var root = document.createElement('div'), svg = mk('svg', 'sf-geo', root), gName = document.createElement('div');
    root.className = 'sky-field is-show'; root.setAttribute('aria-hidden', 'true'); gName.className = 'sf-names'; root.appendChild(gName);
    var defs = mk('defs', null, svg), grad = mk('radialGradient', null, defs), mask = mk('mask', null, defs), maskRect = mk('rect', null, mask);
    grad.setAttribute('id', 'sfBeamG'); grad.setAttribute('gradientUnits', 'userSpaceOnUse');
    [['0', 'sf-bm0'], ['0.5', 'sf-bm1'], ['1', 'sf-bm2']].forEach(function (st) { var e = mk('stop', st[1], grad); e.setAttribute('offset', st[0]); });
    mask.setAttribute('id', 'sfBeamM'); mask.setAttribute('maskUnits', 'userSpaceOnUse'); maskRect.setAttribute('fill', 'url(#sfBeamG)');
    var gTint = mk('g', 'sf-tints', svg), gBeam = mk('g', 'sf-beams', svg), gEdge = mk('g', 'sf-edges', svg), gSilk = mk('g', 'sf-silk', svg);
    gBeam.setAttribute('mask', 'url(#sfBeamM)');
    var beams = [];
    var rim = mk('path', 'sf-rim', gEdge), coreRing = mk('path', 'sf-core', gEdge), emblem = mk('path', 'sf-emblem', gEdge);   /* 无盘心团时，轮毂里一枚四芒星（北辰），不承载数据 */
    var disc = stage.querySelector('.sky-disc'), labelsHost = stage.querySelector('#labels');
    if (labelsHost && labelsHost.parentNode === stage) stage.insertBefore(root, labelsHost); else stage.appendChild(root);
    if (disc && disc.parentNode === stage && disc.nextSibling !== root) stage.insertBefore(root, disc.nextSibling);
    try { glo = g.CLSkyFieldGl && THREE ? g.CLSkyFieldGl.create({ scene: scene }) : null; } catch (eG) { glo = null; if (g.console) console.warn('[sky-field] 光层轮廓不可用，退回 SVG', eG); }

    function on(t, f) { (L[t] = L[t] || []).push(f); }
    function emit(t, p) { (L[t] || []).slice().forEach(function (f) { try { f(p); } catch (e) { if (g.console) console.warn('[sky-field]', e); } }); }

    /* ── 平面与投影（星座平面：u 右、v 上，θ 从 +v 顺时针；锚点局部坐标 = (u, v)/R） ── */
    function ensureAnchor() {
      if (anchor || !THREE || !scene.group) return anchor;
      anchor = new THREE.Object3D(); anchor.name = 'sky-field-plane'; scene.group.add(anchor); return anchor;
    }
    function applyPlane() {
      if (!anchor || !info) return;
      anchor.rotation.set(-(info.pitch || 0), 0, 0); anchor.scale.set(info.R, info.R, info.R); anchor.updateWorldMatrix(true, false);
    }
    function computeMatrix() {
      var cam = scene.camera; if (!cam || !anchor) return null;
      cam.updateMatrixWorld(true);
      if (!PM) { PM = new THREE.Matrix4(); TM = new THREE.Matrix4(); }
      TM.multiplyMatrices(cam.matrixWorldInverse, anchor.matrixWorld); PM.multiplyMatrices(cam.projectionMatrix, TM);
      return PM.elements;
    }
    function proj(x, y) {
      if (!E) return null;
      var w = E[3] * x + E[7] * y + E[15]; if (!(w > 1e-6)) return null;
      return [((E[0] * x + E[4] * y + E[12]) / w * 0.5 + 0.5) * Wv, (-(E[1] * x + E[5] * y + E[13]) / w * 0.5 + 0.5) * Hv];
    }
    function projPolar(r, th) { return proj(Math.sin(th) * r / info.R, Math.cos(th) * r / info.R); }
    function starXY(name) {
      var n = scene.nodeOf ? scene.nodeOf('c:' + name) : null; if (!n || !n.g || !scene.camera) return null;
      if (!v3) v3 = new THREE.Vector3();
      n.g.getWorldPosition(v3); v3.project(scene.camera); if (v3.z > 1) return null;
      return [(v3.x * 0.5 + 0.5) * Wv, (-v3.y * 0.5 + 0.5) * Hv];
    }
    function arcPath(r, a0, a1, move) {
      var n = Math.max(2, Math.ceil(Math.abs(a1 - a0) / STEP) + 1), d = '', i, p, any = false;
      for (i = 0; i < n; i++) { p = projPolar(r, a0 + (a1 - a0) * i / (n - 1)); if (!p) continue; d += (any || !move ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); any = true; }
      return d;
    }
    function wedgePath(s) {
      var R = info.R;
      if (s.core) return arcPath(s.rb, 0, TAU, true) + 'Z';
      var d = arcPath(s.rb, s.a0, s.a1, true), p = projPolar(s.ra, s.a1);
      if (p) d += 'L' + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      d += arcPath(s.ra, s.a1, s.a0, false);
      return d + 'Z';
    }

    /* ── 构建 ─────────────────────────────────────────── */
    function relClassOf(r) { try { return g.CLDomainsModel && CLDomainsModel.relClass ? CLDomainsModel.relClass(r) : null; } catch (e) { return null; } }
    /* 换分组 = 同一部书换了一份 skyInfo：旧团名淡出、新团名描出；换书 / 首建照旧淡入 */
    function fastMotion() { var t = TK(); return !!(t && t.reduced && t.reduced()) || !!(glo && glo.tier() === 'low'); }
    function retire(on) {
      var t = now() + dur('soft', 0.36) * 1000 + 60;
      secs.forEach(function (it) { if (!on) { if (it.nm.parentNode) it.nm.parentNode.removeChild(it.nm); return; } it.nm.classList.add('is-leave'); it.nm.style.opacity = '0'; leaving.push({ el: it.nm, t: t }); });
    }
    function build() {
      var prev = info, G0 = app && app.graph ? app.graph() : null;
      info = scene.skyInfo ? scene.skyInfo() : null;
      var redraw = !!(prev && info && G0 && G0 === graphRef) && !fastMotion();
      graphRef = G0;
      retire(redraw);
      [gTint, gSilk, gBeam].forEach(clear); beams = [];
      Array.prototype.slice.call(gEdge.querySelectorAll('.sf-edge')).forEach(function (n) { n.parentNode.removeChild(n); });
      secs = []; silk = []; pool = []; nStrong = 0; silkBy = {}; prevKey = ''; hotCamp = null; hoverStar = null;
      root.classList.toggle('is-empty', !info);
      if (!info) { if (glo) glo.build(null); return; }
      ensureAnchor(); applyPlane();
      var campOf = {}, ring = info.sectors.filter(function (s) { return !s.core; });
      var bt = glo ? glo.beat() : { delay: dur('flick', 0.14), span: dur('fly', 1.2), stagger: 0.3 };
      info.sectors.forEach(function (s, i) {
        var col = hex(s.color), it = { s: s, i: i, col: col };
        it.tint = mk('path', 'sf-tint' + (s.core ? ' is-core' : '') + (s.field ? ' is-field' : ''), gTint);
        it.tint.style.setProperty('--sf-c', col);
        if (!s.core && ring.length > 1) { it.edge = mk('path', 'sf-edge', gEdge); it.edge.setAttribute('pathLength', '1'); it.edge.style.setProperty('--sf-d', (bt.delay + bt.stagger * ((s.a0 % TAU + TAU) % TAU) / TAU).toFixed(3) + 's'); }
        /* 团名 = HTML 层包一枚小 SVG：平移写在 div 上（写在 <svg> 根上 Blink 会逐帧重排字 → 重绘） */
        var nm = document.createElement('div'), nv = mk('svg', 'sf-nv', nm); nm.className = 'sf-nm'; gName.appendChild(nm);
        var gn = mk('g', 'sf-name' + (s.core ? ' is-core' : '') + (s.field ? ' is-field' : ''), nv);
        gn.style.setProperty('--sf-c', col);
        var tn = mk('text', 'sf-n', gn); tn.textContent = s.name;
        var tk = mk('text', 'sf-k', gn); tk.textContent = String(s.count);
        var hit = mk('rect', 'sf-hit', gn);
        /* 团名是星座读层里真正可操作的节点：让键盘用户也能进入同一
           悬停/选中路径，避免只靠 SVG 指针命中。 */
        gn.setAttribute('role', 'button');
        gn.setAttribute('tabindex', '0');
        gn.setAttribute('aria-label', s.name + '，' + s.count + ' 位角色，查看该团');
        if (redraw) {   /* 描线副本：同字同排版只描不填，描完摘掉 */
          var nd = mk('text', 'sf-n sf-nd', gn); nd.textContent = s.name; it.nd = nd;
          nm.classList.add('is-draw'); nm.style.setProperty('--sf-d', (bt.delay + (s.core ? 0 : bt.stagger * ((s.a0 + s.a1) / 2 % TAU) / TAU)).toFixed(3) + 's');
        }
        function enter() { hotCamp = s.name; if (scene.hoverCamp) scene.hoverCamp(s.name); paintHot(); emit('hover', s); }
        function leave() { hotCamp = null; if (scene.hoverCamp) scene.hoverCamp(null); paintHot(); emit('hover', null); }
        function pick(e) { e.stopPropagation(); if (scene.selectCamp) scene.selectCamp(s.name); paintHot(); emit('select', s); }
        gn.addEventListener('pointerenter', enter);
        gn.addEventListener('pointerleave', leave);
        gn.addEventListener('focus', enter);
        gn.addEventListener('blur', leave);
        gn.addEventListener('click', pick);
        gn.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(e); }
        });
        it.nm = nm; it.nv = nv; it.g = gn; it.tn = tn; it.tk = tk; it.hit = hit; it.w = 0; it.vis = true;
        secs.push(it);
      });
      if (redraw) { draws++; drawUntil = now() + (bt.delay + bt.stagger + dur('focus', 0.9) + dur('soft', 0.36)) * 1000 + 120; root.classList.add('is-redraw'); }
      var cps = scene.camps ? scene.camps() : [];
      cps.forEach(function (cp) { (cp.members || []).forEach(function (m) { campOf[m] = cp.name; }); });
      var byName = {}; secs.forEach(function (it) { byName[it.s.name] = it; });
      /* 组间丝：跨扇区的关系，按强度 × 两端咖位取前 SILK_MAX 条（其余悬停可见，读数写在 stats） */
      var V = app && app.atlas && app.atlas.skyView ? app.atlas.skyView() : (app && app.graph ? app.graph() : null);
      var rels = (V && V.relations) || [], cand = [];
      var toCore = {};
      rels.forEach(function (r, ri) {
        var ca = campOf[r.a], cb = campOf[r.b]; if (!ca || !cb || ca === cb || !byName[ca] || !byName[cb]) return;
        var na = scene.nodeOf('c:' + r.a), nb = scene.nodeOf('c:' + r.b); if (!na || !nb) return;
        if (byName[ca].s.core || byName[cb].s.core) { var other = byName[ca].s.core ? cb : ca; toCore[other] = (toCore[other] || 0) + 1; return; }
        cand.push({ r: r, ri: ri, sa: byName[ca], sb: byName[cb], s: Math.min(na.w || 0, nb.w || 0) + 30 * (isFinite(r.strength) ? r.strength : 0.5) });
      });
      cand.sort(function (x, y) { return y.s - x.s || x.ri - y.ri; });
      var total = cand.length;
      /* 光层丝池：全部跨扇区关系（≤ POOL_MAX）；默认只亮前 nStrong 条强关系（大书降噪），其余悬停星 / 团时才现 */
      var nStars = info.sectors.reduce(function (a, x) { return a + (x.count || 0); }, 0);
      nStrong = Math.min(total, Math.max(16, Math.min(64, Math.round(40 * Math.sqrt(nStars / 450)))));
      pool = cand.slice(0, POOL_MAX).map(function (c, k) { var rc = relClassOf(c.r); return { a: c.r.a, b: c.r.b, ga: c.sa.i, gb: c.sb.i, color: rc ? rc.hex : 0x8d84a8, dash: rc && rc.dash ? rc.dash : 0, w: isFinite(c.r.strength) ? c.r.strength : 0.5, strong: k < nStrong, rank: k }; });
      cand.slice(0, SILK_MAX).forEach(function (c) {
        var rc = relClassOf(c.r), el = mk('path', 'sf-thread' + (rc && rc.dash ? ' is-dash' + rc.dash : ''), gSilk);
        el.style.setProperty('--sf-c', rc ? hex(rc.hex) : 'var(--abyss-ink-2)');
        el.style.setProperty('--sf-w', (0.5 + 0.9 * (isFinite(c.r.strength) ? c.r.strength : 0.5)).toFixed(2));
        var t = { a: c.r.a, b: c.r.b, sa: c.sa, sb: c.sb, el: el, cls: rc ? rc.id : '', hex: rc ? rc.hex : 0x8d84a8, dash: rc && rc.dash ? rc.dash : 0, w: isFinite(c.r.strength) ? c.r.strength : 0.5 };
        silk.push(t); (silkBy[t.a] = silkBy[t.a] || []).push(t); (silkBy[t.b] = silkBy[t.b] || []).push(t);
      });
      /* 盘心光束：每个扇区一束，宽度 ∝ √(与盘心团的联系数 / 最多者) */
      var kMax = 0; Object.keys(toCore).forEach(function (k) { kMax = Math.max(kMax, toCore[k]); });
      Object.keys(toCore).forEach(function (k) {
        var it = byName[k], wv = Math.sqrt(toCore[k] / Math.max(1, kMax));
        var el = mk('path', 'sf-beam', gBeam); el.style.setProperty('--sf-c', it.col); el.style.setProperty('--sf-k', (0.35 + 0.65 * wv).toFixed(3));
        var ln = mk('path', 'sf-beam-core', gBeam); ln.style.setProperty('--sf-c', it.col); ln.style.setProperty('--sf-w', (0.6 + 1.6 * wv).toFixed(2));
        beams.push({ it: it, n: toCore[k], w: wv, el: el, ln: ln });
      });
      root.dataset.beams = String(beams.length);
      root.style.setProperty('--sf-o', Math.max(0.07, Math.min(0.2, 0.2 * Math.sqrt(40 / Math.max(40, silk.length)))).toFixed(3));   /* 丝越多每根越淡：叠加后主干亮度大致恒定 */
      root.dataset.silk = silk.length + '/' + total; liveUntil = now() + 4800;   /* 入场 / 换分类飞行期间星在动：逐帧跟 */
      if (glo) glo.build({ anchor: anchor, R: info.R, rc: info.rc, ra: info.ra, rb: info.rb, sectors: info.sectors, draw: redraw });
      if (!redraw) { root.classList.remove('is-born'); void root.getBoundingClientRect(); root.classList.add('is-born'); }
      frame(true);
    }

    /* 轮毂点：扇区内缘中点往里一截（盘心团 = 盘心圆边朝向对方扇区）；同一对扇区的丝都经这两点 → 成束 */
    function hubXY(it, other) {
      var s = it.s, rc = info.rc || 0, ra = info.ra || 0, rh;
      if (s.core) { var o = other.s, th = o.core ? 0 : (o.a0 + o.a1) / 2; return projPolar(Math.max(8, rc * 0.92), th); }
      rh = rc > 0 ? rc + (ra - rc) * 0.45 : ra * 0.8;
      return projPolar(rh, (s.a0 + s.a1) / 2);
    }

    /* 团名的候选位移（径向外推 r、切向错开 t，屏幕 px），按位移代价排好：先原位，再小推，再错开 */
    var NAME_CAND = (function () {
      var out = [];
      [0, 14, 30, 48].forEach(function (r) { [0, 20, -20, 40, -40].forEach(function (t) { out.push([r, t, r + Math.abs(t) * 1.2]); }); });
      return out.sort(function (a, b) { return a[2] - b[2]; });
    })();
    /* 团名要让开的星名与界面栏：CLSkyFieldAvoid（逐帧不读布局） */
    var AV = g.CLSkyFieldAvoid ? g.CLSkyFieldAvoid.create(root, now) : { labels: function () { return []; }, obstacles: function () { return []; }, sig: function () { return ''; } };

    /* 团名：基点逐帧精确投影，避让位移按 DUR.soft 滑过去（不跳）；返回「还在滑」 */
    function layoutNames(labs, dt) {
      var R = info.R, boxes = AV.obstacles(labs || []), kk = fastMotion() ? 1 : 1 - Math.exp(-dt * 3 / dur('soft', 0.36)), sliding = false;
      secs.forEach(function (it) {
        var s = it.s, th = s.core ? Math.PI : (s.a0 + s.a1) / 2, sx = Math.sin(th), cy = Math.cos(th);
        var p = s.core ? projPolar(Math.max(s.rb, 1) + (info.ra - s.rb) * 0.5, Math.PI) : projPolar(R * 1.012, th);
        if (!p) { if (it.vis) { it.vis = false; it.nm.classList.add('is-off'); } it.ox = null; return; }
        if (!it.vis) { it.vis = true; it.nm.classList.remove('is-off'); }
        /* 侧视纵深：团名按离镜头的相对远近压淡（与星盘线名同一把尺：相对深度 >10% 起，最远 55%；正视不动） */
        var rr = s.core ? Math.max(s.rb, 1) + (info.ra - s.rb) * 0.5 : R * 1.012, wz = E[3] * Math.sin(th) * rr / R + E[7] * Math.cos(th) * rr / R + E[15];
        var fo = (1 - 0.45 * Math.max(0, Math.min(1, ((wz - E[15]) / E[15] - 0.10) / 0.10))).toFixed(2);
        if (it.fo !== fo) { it.fo = fo; it.nm.style.opacity = fo; }
        var anchorX = s.core ? 'middle' : sx > 0.34 ? 'start' : sx < -0.34 ? 'end' : 'middle';
        /* 字宽按真实排版量（含宽字距），视口宽变了才重量——不逐帧读布局 */
        if (!it.mw || it.mwW !== Wv) { var fs0 = parseFloat(g.getComputedStyle(it.tn).fontSize) || 14; it.fs = fs0; it.mw = (it.tn.getComputedTextLength ? it.tn.getComputedTextLength() : 0) || s.name.length * fs0 * 1.36; it.kwm = (it.tk.getComputedTextLength ? it.tk.getComputedTextLength() : 0) || String(s.count).length * fs0 * 0.5; it.mwW = Wv; }
        var fs = it.fs, nw = it.mw + 4, kw = it.kwm + 5, w = nw + kw;
        var dx = s.core ? 0 : sx * 10, dy = s.core ? 0 : -cy * 8, x = p[0] + dx, y = p[1] + dy;
        var bx = anchorX === 'start' ? x : anchorX === 'end' ? x - w : x - w / 2, by = (!s.core && cy > 0.34) ? y - fs : (!s.core && cy < -0.34) ? y : y - fs / 2;
        /* 互不压字：避开已放的团名、星名与界面栏——先原位，再沿径向外推、沿切向错开，取代价最小的空位；
           窄屏上出了屏边的位横向收进视口再比：先要全空的，再退到只压星名的（界面栏与团名始终让开）——团名不被屏边切掉 */
        var h = fs * 1.2, pick = null, alt = [null, null, null], lo = 8 - bx, hi = Wv - 8 - w - bx;
        for (var k = 0; k < NAME_CAND.length && !pick; k++) {
          var cd = NAME_CAND[k], ox = sx * cd[0] + cy * cd[1], oy = -cy * cd[0] + sx * cd[1], cx = Math.min(Math.max(ox, lo), hi), b0 = bx + cx, b1 = by + oy, hit = 0;
          if (b1 < 8 || b1 + h > Hv - 8 || lo > hi) continue;
          for (var j = 0; j < boxes.length && hit < 2; j++) { var b = boxes[j]; if (b0 < b[2] + 6 && b0 + w > b[0] - 6 && b1 < b[3] + 3 && b1 + h > b[1] - 3) hit = j < boxes.hudN || j >= boxes.obsN ? 2 : 1; }
          if (!hit && cx === ox) pick = [ox, oy];
          else { var r = !hit ? 0 : hit === 1 ? (cx === ox ? 1 : 2) : -1; if (r >= 0 && !alt[r]) alt[r] = [cx, oy]; }
        }
        if (!pick) pick = alt[0] || alt[1] || alt[2] || [Math.min(Math.max(0, lo), hi), 0];
        var px = pick[0], py = pick[1];
        boxes.push([bx + px, by + py, bx + px + w, by + py + h]);
        var ub = !!(AV.under && AV.under(boxes[boxes.length - 1], boxes)); if (ub !== !!it.under) { it.under = ub; it.nm.classList.toggle('is-under', ub); }
        if (it.ox == null) { it.ox = px; it.oy = py; }
        else { it.ox += (px - it.ox) * kk; it.oy += (py - it.oy) * kk; if (Math.abs(px - it.ox) < 0.3 && Math.abs(py - it.oy) < 0.3) { it.ox = px; it.oy = py; } else sliding = true; }
        /* 小画布（字 + 人数 + 命中框，四周留 PAD 给辉光）：锚向 / 字宽变了才重排，否则层内容不变 */
        var lk = anchorX + '|' + w.toFixed(1) + '|' + fs;
        if (it.lk !== lk) {
          it.lk = lk;
          var base = fs * 0.92 + 4 + PAD, tx = (anchorX === 'end' ? nw : anchorX === 'middle' ? nw / 2 : 0) + 6 + PAD, kx = (anchorX === 'start' ? nw : nw + 4) + 6 + PAD;
          [it.tn, it.nd].forEach(function (t) { if (t) { t.setAttribute('x', tx.toFixed(1)); t.setAttribute('y', base.toFixed(1)); t.setAttribute('text-anchor', anchorX); } });
          it.tk.setAttribute('x', kx.toFixed(1)); it.tk.setAttribute('y', (base - fs * 0.42).toFixed(1)); it.tk.setAttribute('text-anchor', 'start');
          it.hit.setAttribute('x', PAD); it.hit.setAttribute('y', PAD); it.hit.setAttribute('width', (w + 12).toFixed(1)); it.hit.setAttribute('height', (h + 8).toFixed(1));
          it.nv.setAttribute('width', Math.ceil(w + 12 + 2 * PAD)); it.nv.setAttribute('height', Math.ceil(h + 8 + 2 * PAD));
          if (it.nd) it.nd.style.setProperty('--sf-dl', (fs * 4.6).toFixed(1));
        }
        /* 与星名同一写法（scene-lod-labels）：直接写平移 */
        var X = bx + it.ox, Y = by + it.oy, tr = 'translate3d(' + (X - 6 - PAD).toFixed(1) + 'px,' + (Y - 4 - PAD).toFixed(1) + 'px,0)';
        if (it.tr !== tr) { it.tr = tr; it.nm.style.transform = tr; }
        it.box = [X, Y, X + w, Y + h];
      });
      return sliding;
    }

    function paintHot() {
      var sel = scene.campSel ? scene.campSel() : null, hot = hotCamp || sel, star = hoverStar;
      root.classList.toggle('sf-emph', !!(hot || star));
      secs.forEach(function (it) { var on = it.s.name === hot; it.g.classList.toggle('is-hot', on); it.tint.classList.toggle('is-hot', on); it.g.classList.toggle('is-sel', it.s.name === sel); });
      silk.forEach(function (t) { t.el.classList.toggle('is-on', star ? (t.a === star || t.b === star) : !!hot && (t.sa.s.name === hot || t.sb.s.name === hot)); });
      var coreHot = !!hot && secs.some(function (it) { return it.s.core && it.s.name === hot; });
      beams.forEach(function (b) { var on = !star && (coreHot || b.it.s.name === hot); b.el.classList.toggle('is-on', on); b.ln.classList.toggle('is-on', on); });
    }

    /* ── 每帧 ─────────────────────────────────────────── */
    function endDraw() {
      drawUntil = 0; root.classList.remove('is-redraw');
      secs.forEach(function (it) { if (it.nd) { if (it.nd.parentNode) it.nd.parentNode.removeChild(it.nd); it.nd = null; } it.nm.classList.remove('is-draw'); });
    }
    function frame(force) {
      if (dead) return;
      var t = now(), dt = lastT ? Math.min(0.1, Math.max(0, (t - lastT) / 1000)) : 0; lastT = t;
      if (leaving.length) leaving = leaving.filter(function (l) { if (t < l.t) return true; if (l.el.parentNode) l.el.parentNode.removeChild(l.el); return false; });
      if (drawUntil && t > drawUntil) endDraw();
      var cur = scene.skyInfo ? scene.skyInfo() : null;
      if (cur !== info) { build(); return; }
      if (!info || state === 'hidden') return;
      var cam = scene.camera; if (!cam) return;
      Wv = g.innerWidth || 1; Hv = g.innerHeight || 1;
      /* 光层接管时底色 / 光束 / 束丝由 WebGL 画（SVG 这几层 opacity 0），轮廓交给 CLSkyFieldGl：SVG 不再逐帧改写 */
      var lightLayer = document.body.classList.contains('skd-gl'), gl = lightLayer && !!glo && glo.ok();
      if (gl !== useGl) { useGl = gl; root.classList.toggle('sf-gl', gl); glo.setOn(gl); force = true; }
      applyPlane();
      E = computeMatrix(); if (!E) return;
      var hs = scene.hoverName ? scene.hoverName() : null;
      if (hs !== hoverStar) { hoverStar = hs && silkBy[hs] ? hs : null; paintHot(); }
      var labs = state === 'show' ? AV.labels() : null;
      var key = Array.prototype.slice.call(E, 0, 16).map(function (v) { return v.toFixed(4); }).join(',') + '|' + Wv + 'x' + Hv + '|' + (labs ? AV.sig(labs) : '');
      var moving = t < liveUntil || sliding;
      if (!force && key === prevKey && !moving) return;
      prevKey = key;
      var vb = '0 0 ' + Wv + ' ' + Hv;
      if (vb !== vbKey) { vbKey = vb; svg.setAttribute('viewBox', vb); }
      if (!useGl) {
        rim.setAttribute('d', arcPath(info.R, 0, TAU, true) + 'Z');
        coreRing.setAttribute('d', info.rc > 0 ? arcPath(info.rc, 0, TAU, true) + 'Z' : '');
        if (!(info.rc > 0) && info.ra > 0) {
          var ro = info.ra * 0.5, rn = info.ra * 0.1, pts = [];
          for (var e8 = 0; e8 < 8; e8++) { var pp = projPolar(e8 % 2 ? rn : ro, e8 * Math.PI / 4); if (pp) pts.push(pp[0].toFixed(1) + ' ' + pp[1].toFixed(1)); }
          emblem.setAttribute('d', pts.length === 8 ? 'M' + pts.join('L') + 'Z' : '');
        } else emblem.setAttribute('d', '');
      }
      secs.forEach(function (it) {
        if (!lightLayer) it.tint.setAttribute('d', wedgePath(it.s));
        /* 扇区界：只在外缘团名带里落一道刻（像表圈的分区刻），不贯穿星域——免得和束丝混读 */
        if (it.edge && !useGl) { var p0 = projPolar(info.rb + (info.R - info.rb) * 0.25, it.s.a0), p1 = projPolar(info.R * 1.035, it.s.a0); it.edge.setAttribute('d', p0 && p1 ? 'M' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) + 'L' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1) : ''); }
      });
      if (beams.length && !lightLayer) {
        var rc = info.rc || 0, rEnd = info.ra + (info.rb - info.ra) * 0.55, c0 = projPolar(0, 0), pr = projPolar(rEnd, Math.PI / 2), pl = projPolar(rEnd, -Math.PI / 2), pt = projPolar(rEnd, 0), pb = projPolar(rEnd, Math.PI);
        if (c0 && pr && pl && pt && pb) {
          var rx = Math.max(4, Math.hypot(pr[0] - pl[0], pr[1] - pl[1]) / 2), ry = Math.max(4, Math.hypot(pt[0] - pb[0], pt[1] - pb[1]) / 2), cx = (pt[0] + pb[0]) / 2, cy = (pt[1] + pb[1]) / 2;
          grad.setAttribute('cx', cx.toFixed(1)); grad.setAttribute('cy', cy.toFixed(1)); grad.setAttribute('r', rx.toFixed(1));
          grad.setAttribute('gradientTransform', 'translate(' + cx.toFixed(1) + ' ' + cy.toFixed(1) + ') scale(1 ' + (ry / rx).toFixed(4) + ') translate(' + (-cx).toFixed(1) + ' ' + (-cy).toFixed(1) + ')');
          maskRect.setAttribute('x', '0'); maskRect.setAttribute('y', '0'); maskRect.setAttribute('width', String(Wv)); maskRect.setAttribute('height', String(Hv));
        }
        beams.forEach(function (b) {
          var s = b.it.s, th = (s.a0 + s.a1) / 2, half = (s.a1 - s.a0) / 2, d1 = Math.min(0.5, 0.06 + 0.16 * b.w) * (rc > 0 ? 1 : 0.4), d2 = half * (0.25 + 0.5 * b.w);
          var q = [projPolar(Math.max(rc, 1), th - d1), projPolar(rEnd, th - d2), projPolar(rEnd, th + d2), projPolar(Math.max(rc, 1), th + d1)];
          b.el.setAttribute('d', q.every(Boolean) ? 'M' + q.map(function (p) { return p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join('L') + 'Z' : '');
          var a = projPolar(Math.max(rc, 1), th), e = projPolar(rEnd, th);
          b.ln.setAttribute('d', a && e ? 'M' + a[0].toFixed(1) + ' ' + a[1].toFixed(1) + 'L' + e[0].toFixed(1) + ' ' + e[1].toFixed(1) : '');
        });
      }
      if (state === 'show') {
        sliding = layoutNames(labs, dt);
        if (!lightLayer) silk.forEach(function (t) {
          var pa = starXY(t.a), pb = starXY(t.b), ha = hubXY(t.sa, t.sb), hb = hubXY(t.sb, t.sa);
          if (!pa || !pb || !ha || !hb) { t.el.setAttribute('d', ''); return; }
          var c1x = pa[0] + (ha[0] - pa[0]) * BETA, c1y = pa[1] + (ha[1] - pa[1]) * BETA, c2x = pb[0] + (hb[0] - pb[0]) * BETA, c2y = pb[1] + (hb[1] - pb[1]) * BETA;
          t.el.setAttribute('d', 'M' + pa[0].toFixed(1) + ' ' + pa[1].toFixed(1) + 'C' + c1x.toFixed(1) + ' ' + c1y.toFixed(1) + ' ' + c2x.toFixed(1) + ' ' + c2y.toFixed(1) + ' ' + pb[0].toFixed(1) + ' ' + pb[1].toFixed(1));
        });
      }
    }

    function setState(s) {
      if (s !== 'show' && s !== 'dim' && s !== 'hidden') return state;
      state = s;
      root.classList.toggle('is-show', s === 'show'); root.classList.toggle('is-dim', s === 'dim'); root.classList.toggle('is-hidden', s === 'hidden');
      if (glo) glo.setState(s);
      prevKey = ''; frame(true);
      return state;
    }

    return {
      el: root, frame: frame, setState: setState, state: function () { return state; }, rebuild: build, on: on, live: function (ms) { liveUntil = Math.max(liveUntil, now() + (ms || 1500)); },
      info: function () { return info; },
      /* 光层（sky-bundles / sky-nebula）读的数据：丝 = 跨扇区关系（扇区下标 + 关系类色 / 线型 / 强度），光束 = 盘心团到各扇区 */
      threads: function () { return pool.slice(); },
      beams: function () { return beams.map(function (b) { return { g: b.it.i, k: b.w, n: b.n }; }); },
      hot: function () { var sel = scene.campSel ? scene.campSel() : null; return { camp: hotCamp || sel || null, star: hoverStar || null }; },
      names: function () { return secs.map(function (it) { return { name: it.s.name, count: it.s.count, box: it.box ? it.box.slice() : null, visible: !!it.vis }; }); },
      hoverCamp: function (name) { hotCamp = name || null; if (scene.hoverCamp) scene.hoverCamp(hotCamp); paintHot(); },
      stats: function () { return { sectors: secs.length, beams: beams.length, silk: silk.length, pool: pool.length, strong: nStrong, silkTotal: +(String(root.dataset.silk || '0/0').split('/')[1]) || 0, state: state, R: info ? info.R : 0,
        gl: useGl, outline: glo ? glo.stats() : null, redraws: draws, drawing: drawUntil > 0, leaving: leaving.length, sliding: sliding }; },
      polar: function (r, th) { return info ? projPolar(r, th) : null; },
      dispose: function () { dead = true; if (root.parentNode) root.parentNode.removeChild(root); if (glo) glo.dispose(); glo = null; if (anchor && anchor.parent) anchor.parent.remove(anchor); }
    };
  }

  g.CLSkyField = { create: create, VERSION: '1' };
})(window);
