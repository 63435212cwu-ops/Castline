/*! @role groups · @owns js/sky/sky-groups-body.js · @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0 · @contract deep-sky/3 */
/* 分组卡片叠 · 展开体：每个数字都能在图谱里指认——团名 · 人数与占比 · 主星（α/β/γ · 身份）· 团内 / 团外关系与分类计数 ·
   跨组对手团 · 参与的主线段 · 成员（按星等权重；点名字进罗盘）。文本一律 createTextNode（已转义）。 */
(function (g) {
  'use strict';
  var Q = 'skg-card__', NAM = 12;

  function build(r, x) {
    var gp = r.g, mk = x.mk, doc = x.doc, i, s, row, box, sp, li, p;
    var bd = mk('div', Q + 'body', r.n);
    r.bd = bd;
    /* 一句话读数：分类 / 团 · 占全书比例 / 场域团 */
    mk('div', Q + 'kind', bd, x.label + ' · 第 ' + (gp.idx + 1) + ' 组 · 占 ' + pct(gp.share) + (gp.field ? ' · 无组织散星' : '') + (gp.core ? ' · 盘心主角团' : ''));
    /* 主星：α 最重那颗，名字旁一句身份（点名字进其罗盘） */
    box = mk('div', Q + 'leads', bd);
    for (i = 0; i < gp.members.length && i < 3; i++) {
      var m = gp.members[i];
      row = mk('div', Q + 'lead', box);
      mk('b', Q + 'rank', row, m.bayer || chr(i));
      var b = mk('button', Q + 'name', row, m.name);
      b.type = 'button'; b.title = m.name + ' · ' + roleOf(m);
      (function (nmw) { b.addEventListener('click', function (e) { e.stopPropagation(); if (x.onPick) x.onPick(nmw); }, false); })(m.name);
      mk('span', Q + 'role', row, roleOf(m)).title = roleOf(m);
    }
    /* 关系读数 */
    mk('div', Q + 'stat', bd, '团内 ' + x.num(gp.inner) + ' · 团外 ' + x.num(gp.outer) + ' · 剧情点 ' + x.num(gp.evSum));
    if (gp.classes.length) {
      box = mk('div', Q + 'classes', bd);
      /* 表头：条长 = 该类占本团全部关系；实段 = 团内、虚段 = 团外；右列「团内 / 团外」 */
      p = mk('div', Q + 'cls is-cap', box); mk('span', null, p, '关系'); mk('span', null, p); mk('span', null, p, '内 / 外');
      for (i = 0; i < gp.classes.length; i++) {
        var c = gp.classes[i], ct = c.inner + c.outer;
        p = mk('div', Q + 'cls', box);
        p.style.setProperty('--c', x.hex(c.hex));
        p.title = c.label + ' · 团内 ' + c.inner + ' · 团外 ' + c.outer;
        mk('span', Q + 'cls-lab', p, c.label);
        var bar = mk('span', Q + 'cls-bar', p);
        sp = mk('i', null, bar);
        sp.style.setProperty('--w', (gp.relTotal ? ct / gp.relTotal : 0).toFixed(4));
        sp.style.setProperty('--wi', (ct ? c.inner / ct : 0).toFixed(4));
        sp = mk('em', Q + 'cls-in', p, String(c.inner));
        mk('i', null, sp, '/'); sp.appendChild(doc.createTextNode(String(c.outer)));
      }
    }
    if (gp.peers.length) {
      box = mk('div', Q + 'peers', bd);
      mk('span', Q + 'peers-lab', box, '最多往来');
      for (i = 0; i < gp.peers.length; i++) {
        li = mk('span', Q + 'peer', box);
        li.style.setProperty('--c', x.hex(gp.peers[i].hex));
        li.appendChild(doc.createTextNode(gp.peers[i].name + ' ' + gp.peers[i].n));
      }
    }
    if (gp.lines.length) {
      box = mk('ol', Q + 'lines', bd);
      for (i = 0; i < gp.lines.length; i++) {
        var l = gp.lines[i];
        li = mk('li', null, box);
        mk('b', null, li, '第 ' + x.chNo(l.c0) + (l.c1 > l.c0 ? '–' + x.chNo(l.c1) : '') + ' ' + x.unit);
        mk('span', null, li, (l.label || '主线') + ' · ' + l.n + '/' + l.castN + ' 人');
        li.title = (l.label || '主线') + ' · 本团 ' + l.n + ' 人 / 该段 ' + l.castN + ' 人';
      }
    }
    /* 成员星位微缩图：一张 canvas 一个节点，只在卡片展开时画一次 */
    minimap(bd, gp, x);
    /* 成员：按星等权重降序，先给 NAM 个，其余一键展开 */
    box = mk('div', Q + 'members', bd);
    var all = [], more = null;
    for (i = 0; i < gp.members.length; i++) {
      var mm = gp.members[i], chip = mk('button', Q + 'chip', box, mm.name);
      chip.type = 'button'; chip.title = mm.name + ' · ' + roleOf(mm) + ' · 剧情点 ' + mm.events + ' · 关系 ' + mm.relations;
      chip.style.setProperty('--c', x.hex(gp.hex));
      (function (nmw) { chip.addEventListener('click', function (e) { e.stopPropagation(); if (x.onPick) x.onPick(nmw); }, false); })(mm.name);
      if (i >= NAM) { chip.hidden = true; all.push(chip); }
    }
    if (all.length) {
      more = mk('button', Q + 'chip is-more', box, '展开其余 ' + (gp.members.length - NAM) + ' 人');
      more.type = 'button';
      more.addEventListener('click', function () { for (var q = 0; q < all.length; q++) all[q].hidden = false; more.hidden = true; x.remeasure(); }, false);
    }
    box = mk('div', Q + 'acts', bd);
    var ab = mk('button', Q + 'act', box, '聚焦此团');
    ab.type = 'button';
    ab.addEventListener('click', function (e) { e.stopPropagation(); if (x.onFocus) x.onFocus(gp.name); }, false);
    if (gp.lead) {
      var lb = mk('button', Q + 'act', box, '看 ' + gp.lead + ' 的罗盘');
      lb.type = 'button';
      lb.addEventListener('click', function (e) { e.stopPropagation(); if (x.onPick) x.onPick(gp.lead); }, false);
    }
    return bd;
  }

  /* 微缩星位图：真实坐标，不重算布局；取不到坐标就整块不画（不虚构）。
     投影 = 打开这张卡时主图的镜头（x.viewOf：盘面局部 → 镜头空间，正交），于是小图与眼前的星图同向、同倾角；
     拿不到镜头时退回固定倾角（上 = 盘面 +y，与主图默认视角同向）。 */
  var MW = 272, MH = 84, MH2 = 132, LEAN = 0.52;
  function minimap(bd, gp, x) {
    if (!x.posOf || !g.document.createElement('canvas').getContext) { return null; }
    var pts = [], i, p, mm, P = x.viewOf ? x.viewOf() : null, mz = 0, n = 0;
    for (i = 0; i < gp.members.length; i++) {
      mm = gp.members[i]; p = x.posOf(mm.name);
      if (p && isFinite(p.x) && isFinite(p.y)) { p = { x: p.x, y: p.y, z: +p.z || 0, w: +mm.w || 0.5, lead: i < 3, rk: i < 3 ? mm.bayer || chr(i) : '' }; pts.push(p); mz += p.z; n++; }
    }
    if (pts.length < 2) { return null; }
    mz /= n;   /* 盘面 = 团员离盘面高度的均值：垂线落到这一层 */
    function prj(a, b, c) {
      if (P) { var v = P(a, b, c); return [v[0], -v[1], v[2]]; }
      return [a, -(b * LEAN + (c - mz) * 0.55), c];
    }
    /* 星与垂足一起投影，按外接框等比缩放（不拉变形）；画布高随高宽比在 [MH, MH2] 内取（俯看时团是一整块，不挤成扁带） */
    var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, d0 = Infinity, d1 = -Infinity, bx0 = Infinity, bx1 = -Infinity, by0 = Infinity, by1 = -Infinity, wMax = 0;
    for (i = 0; i < pts.length; i++) {
      p = pts[i]; p.s = prj(p.x, p.y, p.z); p.f = prj(p.x, p.y, mz);
      x0 = Math.min(x0, p.s[0], p.f[0]); x1 = Math.max(x1, p.s[0], p.f[0]);
      y0 = Math.min(y0, p.s[1], p.f[1]); y1 = Math.max(y1, p.s[1], p.f[1]);
      d0 = Math.min(d0, p.s[2]); d1 = Math.max(d1, p.s[2]);
      bx0 = Math.min(bx0, p.x); bx1 = Math.max(bx1, p.x); by0 = Math.min(by0, p.y); by1 = Math.max(by1, p.y);
      if (p.w > wMax) { wMax = p.w; }   /* w 是咖位原值：按团内最大值归一 */
    }
    if (!(wMax > 0)) { wMax = 1; }
    var pad = 8, sw = Math.max(x1 - x0, 1e-6), sh = Math.max(y1 - y0, 1e-6);
    var H = Math.round(Math.max(MH, Math.min(MH2, (MW - pad * 2) * sh / sw * 0.9 + pad * 2)));
    var wrap = x.mk('div', Q + 'map', bd), cv = x.doc.createElement('canvas'), dpr = Math.min(2, g.devicePixelRatio || 1);
    cv.width = Math.round(MW * dpr); cv.height = Math.round(H * dpr);
    cv.className = Q + 'map-cv';
    cv.setAttribute('role', 'img');
    cv.setAttribute('aria-label', gp.name + ' 的 ' + pts.length + ' 位成员在星图上的位置');
    wrap.appendChild(cv);
    var c = cv.getContext('2d');
    c.scale(dpr, dpr);
    var dd = Math.max(d1 - d0, 1e-6), k = Math.min((MW - pad * 2) / sw, (H - pad * 2) / sh);
    var ox = MW / 2 - (x0 + x1) / 2 * k, oy = H / 2 - (y0 + y1) / 2 * k;
    var TC = (g.CLSkyTokens && g.CLSkyTokens.C) || {}, col = hexStr(gp.hex), star = hexStr(TC.STAR_WHITE != null ? TC.STAR_WHITE : 0xfff6e8);
    /* 盘面：团心那层两圈发丝椭圆（盘面上的圆经同一投影），给星点一个「地面」 */
    var bx = (bx0 + bx1) / 2, by = (by0 + by1) / 2, rx = (bx1 - bx0) * 0.24, ry = (by1 - by0) * 0.24, j, q;
    c.strokeStyle = col; c.lineWidth = 0.6;
    for (i = 1; i <= 2; i++) {
      c.globalAlpha = 0.2 / i; c.beginPath();
      for (j = 0; j <= 48; j++) { q = prj(bx + Math.cos(j / 48 * 6.2832) * rx * i, by + Math.sin(j / 48 * 6.2832) * ry * i, mz); if (j) { c.lineTo(ox + q[0] * k, oy + q[1] * k); } else { c.moveTo(ox + q[0] * k, oy + q[1] * k); } }
      c.stroke();
    }
    /* 远先近后；离盘面远的星拉一根垂到盘面的发丝 */
    pts.sort(function (a, b) { return a.s[2] - b.s[2]; });
    for (i = 0; i < pts.length; i++) {
      p = pts[i];
      var zn = (p.s[2] - d0) / dd, px = ox + p.s[0] * k, py = oy + p.s[1] * k, fx = ox + p.f[0] * k, fy = oy + p.f[1] * k;   /* zn：0 = 最远，1 = 最近 */
      if (Math.abs(py - fy) + Math.abs(px - fx) > 2.5) {
        c.globalAlpha = p.lead ? 0.34 : 0.1; c.strokeStyle = p.lead ? star : col; c.lineWidth = 0.5;
        c.beginPath(); c.moveTo(fx, fy); c.lineTo(px, py); c.stroke();
      }
      var w01 = Math.min(1, Math.max(0, p.w / wMax)), rr = (p.lead ? 2.1 : 1.15) * (0.7 + 0.6 * zn) * (0.75 + 0.5 * w01);
      rr = p.r = Math.max(0.4, Math.min(3.2, rr));
      c.globalAlpha = (p.lead ? 0.95 : 0.42) * (0.55 + 0.45 * zn);
      c.fillStyle = p.lead ? star : col;
      c.beginPath(); c.arc(px, py, rr, 0, 6.2832); c.fill();
    }
    var cs = g.getComputedStyle ? g.getComputedStyle(wrap) : null, brass = cs ? cs.getPropertyValue('--skd-brass-hot').trim() : '';
    c.globalAlpha = 0.9; c.fillStyle = brass || star; c.textBaseline = 'middle';
    c.font = '9px ' + (cs ? cs.getPropertyValue('--skd-font-serif').trim() || 'serif' : 'serif');
    /* 主星旁标 α / β / γ（与主星行同字同色）：8 个方向里挑离其余主星与已放标签最远的一处 */
    var put = [], L = [], j2, a2, bx2, by2, sc, best, bs, dq;
    for (i = 0; i < pts.length; i++) { if (pts[i].rk) { L.push(pts[i]); pts[i].q = [ox + pts[i].s[0] * k, oy + pts[i].s[1] * k]; } }
    L.sort(function (a, b) { return a.rk.charCodeAt(0) - b.rk.charCodeAt(0); });
    c.textAlign = 'center';
    for (i = 0; i < L.length; i++) {
      p = L[i]; best = null; bs = -1;
      for (j2 = 0; j2 < 8; j2++) {
        a2 = -Math.PI / 4 + j2 * Math.PI / 4; bx2 = p.q[0] + Math.cos(a2) * (p.r + 6); by2 = p.q[1] + Math.sin(a2) * (p.r + 6); sc = 99;
        for (q = 0; q < L.length; q++) { if (L[q] !== p) { dq = Math.sqrt(Math.pow(L[q].q[0] - bx2, 2) + Math.pow(L[q].q[1] - by2, 2)) - L[q].r; sc = Math.min(sc, dq); } }
        for (q = 0; q < put.length; q++) { sc = Math.min(sc, Math.sqrt(Math.pow(put[q][0] - bx2, 2) + Math.pow(put[q][1] - by2, 2)) - 4); }
        if (bx2 < 5 || bx2 > MW - 5 || by2 < 5 || by2 > H - 5) { sc -= 50; }
        if (sc > bs + 0.5) { bs = sc; best = [bx2, by2]; }
      }
      if (best && bs > 3) { put.push(best); c.fillText(p.rk, best[0], best[1]); }
    }
    c.globalAlpha = 1;
    return wrap;
  }
  function hexStr(h) { h = h | 0; return 'rgb(' + ((h >> 16) & 255) + ',' + ((h >> 8) & 255) + ',' + (h & 255) + ')'; }

  function pct(v) { v = +v || 0; return v >= 0.095 ? Math.round(v * 100) + '%' : (v * 100).toFixed(1) + '%'; }
  function chr(i) { return ['α', 'β', 'γ'][i] || '·'; }
  /* 角色定位 · 身份（身份很长时由 CSS 截断，全文在 title 里） */
  function roleOf(m) {
    var r = m.role && m.role !== '配角' ? m.role : '', id = m.identity ? String(m.identity) : '';
    return r && id ? r + ' · ' + id : r || id;
  }

  g.CLSkyGroupsBody = { build: build };
})(window);
