/**
 * @role shell
 * @owns js/sky/sky-deep.js
 * 光层总调度：把 WebGL 光层（星体光学 / 势力星云 / 组间束 / 星盘光环与动态件 / 罗盘星仪 / 后期虚化）接到星空壳的三种状态上。
 *  · 星座：星盘光层独立虚化（背景）、星云与束常亮、悬停星 → 一跳网络点亮 + 角色卡，悬停团名 → 该团星云提亮 + 团卡。
 *  · 剧情：对焦（虚化 → 清晰）→ 光环按时间自 12 点顺时针展开；悬停线 → 时间扇区 + 参与者点亮；播放 → 时间指针与尾迹。
 *  · 罗盘：其余光层退场，晶体外三道星轨。
 * 只读 SVG 读层（sky-disc / sky-field）暴露的几何与数据；不改数据；不私开 rAF（sky-shell 的帧钩子调 frame）。
 */
(function (g) {
  'use strict';
  var doc = document;
  var T = null, S = null, disc = null, field = null, app = null;
  var cosmos = null, post = null, stars = null, trails = null, neb = null, bun = null, rings = null, fx = null, orb = null, sats = null, view = null, scale = null, rev = null;
  var heroKey = null, cosmosReady = false, homeSet = false, homeDir = null;
  var M = null, G = null, mode = 'constellation', inited = false, discRev = -1, skyRef = null, liveUntil = 0, clock = 0, tierName = '';
  var blur = 0, blurTw = null, revealTw = null, igniteTw = null, homeTw = null, lastHome = 0;
  var hoverStar = null, hotCamp = null, pointer = { x: 0, y: 0 }, evCount = {}, relCount = {}, lineIdx = null;
  var KEY = /转折|高燃|抉择|冲突|高潮|揭秘/;
  var cards = g.CLSkyDeepCards.create({
    scene: function () { return S; }, graph: function () { return G; }, model: function () { return M; },
    app: function () { return app; }, tokens: function () { return T; }, info: sky, color: groupColor,
    events: function () { return evCount; }, relations: function () { return relCount; },
    enabled: function () { return inited; }, mode: function () { return mode; }, pointer: pointer,
    stars: function () { return stars; }, bundles: function () { return bun; }, nebula: function () { return neb; },
    hoverStar: function () { return hoverStar; }, setHoverStar: function (v) { hoverStar = v; },
    hotCamp: function () { return hotCamp; }, setHotCamp: function (v) { hotCamp = v; }, hop: hop, sectorIndex: sectorIndex
  });
  var hideCard = cards.hide, lineCard = cards.line, onStarHover = cards.hoverStar, onCampHover = cards.hoverCamp;
  var toolbar = g.CLSkyDeepViews.create({ view: function () { return view; }, mode: function () { return mode; } });
  var buildViews = toolbar.mount, syncViews = toolbar.sync;

  function now() { return clock; }
  function reduced() { return !!(T && T.reduced()); }
  function sky() { return S && S.skyInfo ? S.skyInfo() : null; }
  var mk = g.CLSkyUtil.mk;
  function sectorIndex(info, camp) {
    if (!info) return -1;
    var name = camp || '散星';
    for (var i = 0; i < info.sectors.length; i++) if (info.sectors[i].name === name) return i;
    for (var k = 0; k < info.sectors.length; k++) if (info.sectors[k].field) return k;
    return -1;
  }
  function groupColor(info, camp) { var i = sectorIndex(info, camp); return i >= 0 ? info.sectors[i].color : T.FAMILY[''][0]; }

  /* ── 构建 ─────────────────────────────────────────── */
  function buildStars() {
    var info = sky(), list = [], wmax = 1;
    G.characters.forEach(function (c) { var n = S.nodeOf('c:' + c.name); if (n) wmax = Math.max(wmax, n.w || 0); });
    var order = G.characters.map(function (c) { var n = S.nodeOf('c:' + c.name); return { c: c, n: n, w: n ? n.w || 0 : 0 }; }).filter(function (o) { return o.n; })
      .sort(function (a, b) { return b.w - a.w; });
    order.forEach(function (o, rank) {
      var col = groupColor(info, o.n.camp), villain = o.c.role === '反派';
      list.push({ key: 'c:' + o.c.name, name: o.c.name, tier: o.n.tier, w01: o.w / wmax,
        core: T.mix(T.C.STAR_WHITE, villain ? T.C.OPPOSE : col, villain ? 0.35 : 0.22), halo: col,
        reveal: rev ? rev.starReveal(o.n, info, order.length > 1 ? rank / (order.length - 1) : 0) : order.length > 1 ? 0.85 * rank / (order.length - 1) : 0 });
    });
    heroKey = order.length ? 'c:' + order[0].c.name : null;   /* 点睛：全书最重的那颗星 */
    stars.setStars(list);
    /* 彗尾跟同一批星、同一组色：换分组时星在世界空间里飞，尾迹自己出现、落定自己消失 */
    if (trails) trails.setStars(list.map(function (o) { return { key: o.key, hex: o.halo }; }), info ? info.R : 1);
  }
  function buildField() {
    var info = sky(); skyRef = info;
    if (!info) { neb.setState('hidden'); bun.setState('hidden'); return; }
    var wmax = 1;
    G.characters.forEach(function (c) { var n = S.nodeOf('c:' + c.name); if (n) wmax = Math.max(wmax, n.w || 0); });
    neb.build({ R: info.R, pitch: info.pitch, rad: Math.min(0.3, Math.max(0.09, 1.02 * (info.s0 || 60) / info.R)), groups: info.sectors.map(function (s) { return { name: s.name, color: s.color }; }),
      stars: G.characters.map(function (c) { var n = S.nodeOf('c:' + c.name); return n ? { key: c.name, group: sectorIndex(info, n.camp), w01: (n.w || 0) / wmax } : null; }).filter(Boolean) });
    bun.build({ R: info.R, pitch: info.pitch, rc: info.rc || 0, ra: info.ra || 0, rb: info.rb || 0,
      sectors: info.sectors.map(function (s) { return { name: s.name, a0: s.a0, a1: s.a1, core: !!s.core, color: s.color }; }),
      threads: field && field.threads ? field.threads() : [], beams: field && field.beams ? field.beams() : [] });
    liveUntil = now() + 3.2;
  }
  function genHex(gen, kind) {
    var c = T.GEN[(gen | 0) % T.GEN.length];
    return kind === 'quiet' ? T.mix(T.C.INK3, c, 0.35) : kind === 'named' ? T.mix(c, T.C.INK2, 0.12) : c;
  }
  function buildRings() {
    var d = disc && disc.desc ? disc.desc() : null; discRev = disc && disc.rev ? disc.rev() : -1;
    if (!d) return;
    lineIdx = {};
    d.items.forEach(function (it) {
      lineIdx[it.id] = it.lineIdx;
      it.color = genHex(it.gen, it.kind);
      it.beads = it.kind === 'quiet' ? [] : it.beads.map(function (b) { var e = G.events[b.ev]; return { a: b.a, key: !!(e && KEY.test(e.kind || '')) }; });
    });
    rings.build(d);
    fx.build({ rIn: d.rIn, rMain: d.rMain, rBez: d.rBez, zMain: d.zMain || 0, zBez: d.zBez || 0,
      bridges: d.bridges.map(function (b) { return { a: b.a, r0: b.r0, r1: b.r1, z0: b.z0 || 0, z1: b.z1 || 0, color: genHex(b.gen, 'named') }; }),
      caps: d.caps.map(function (c) { return { a: c.a, r: c.r, z: c.z || 0, kind: c.kind, color: genHex(c.gen, 'main') }; }) });
  }
  /* 深空天球：每部书一片自己的天（种子 = 书名），数据区方向（开书时镜头看向图谱的方向）留给星图，星团 / 远星系 / 星云团都在它四周 */
  function seedOf(t) { var h = 2166136261, str = String(t || 'castline'); for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) % 100000 + 1; }
  function buildCosmos() {
    if (!cosmos || !S.camera || !S.controls) return;
    var info = sky(), c = S.controls.target, fwd = c.clone().sub(S.camera.position).normalize();
    try {
      cosmos.build({ R: info ? info.R : 400, center: [c.x, c.y, c.z], avoid: [fwd.x, fwd.y, fwd.z], seed: seedOf(G && G.title) });
      cosmos.setState('hidden');   /* 开书时天是黑的：星先点亮、光环展开，镜头落定（captureHome）后整片深空再浮现 */
      if (S.core && S.core().setLegacySky) S.core().setLegacySky(false);
    } catch (e) {
      if (g.console) console.warn('[sky-deep] 深空天球构建失败，退回旧背景', e);
      try { cosmos.dispose(); } catch (e2) {}
      cosmos = null;
      if (S.core && S.core().setLegacySky) S.core().setLegacySky(true);
    }
  }
  /* 背景压暗区 = 图谱在屏幕上的外接圆（星座：星域外缘；星盘：光环外缘；罗盘：晶体外接盒）：绚烂留在四周，图谱后面安静 */
  var _fv = null, _orbV = null;
  function cosmosFocus() {
    if (!S.camera || !S.controls) return;
    var W = g.innerWidth || 1, H = g.innerHeight || 1;
    if (mode === 'compass' && orb && orb.setCenter && S.crownAnchor) {
      var anchor = S.crownAnchor();
      if (anchor) { if (!_orbV) _orbV = new g.THREE.Vector3(); anchor.getWorldPosition(_orbV); orb.setCenter(_orbV); }
    }
    if (mode === 'compass' && S.crownScreenBounds) {
      var b = S.crownScreenBounds();
      if (b && b.right > b.left) {
        if (orb && orb.setOcclusion) orb.setOcclusion(b, W, H);
        if (cosmos) cosmos.setFocus({ cx: (b.left + b.right) / 2, cy: (b.top + b.bottom) / 2, rx: (b.right - b.left) * 0.72, ry: (b.bottom - b.top) * 0.62 });
        return;
      }
    }
    if (!cosmos) return;
    if (!_fv) _fv = new g.THREE.Vector3();
    var info = sky(), R = info ? info.R : 400, d = disc && disc.desc ? disc.desc() : null;
    var k = mode === 'plot' && d ? (d.rBez || 1.8) * 1.08 : 1.12;
    _fv.copy(S.controls.target).project(S.camera);
    var dist = S.camera.position.distanceTo(S.controls.target) || 1, px = R * k * (H / (2 * Math.tan((S.camera.fov || 42) * Math.PI / 360))) / dist;
    cosmos.setFocus({ cx: (_fv.x * 0.5 + 0.5) * W, cy: (-_fv.y * 0.5 + 0.5) * H, rx: px, ry: px });
  }

  var adj = {};
  function counts() {
    evCount = {}; relCount = {}; adj = {};
    G.events.forEach(function (e) { (e.characters || []).forEach(function (n) { evCount[n] = (evCount[n] || 0) + 1; }); });
    var V = app && app.atlas && app.atlas.skyView ? app.atlas.skyView() : G;
    (V.relations || []).forEach(function (r) {
      relCount[r.a] = (relCount[r.a] || 0) + 1; relCount[r.b] = (relCount[r.b] || 0) + 1;
      (adj[r.a] = adj[r.a] || {})[r.b] = 1; (adj[r.b] = adj[r.b] || {})[r.a] = 1;
    });
  }
  /* 一跳网络：悬停的星 + 与它有联系的星（其余压暗） */
  function hop(name) { return [name].concat(Object.keys(adj[name] || {})); }

  /* ── 状态 ─────────────────────────────────────────── */
  function starState(s) { stars.setState(s); if (trails) trails.setState(s); }
  function tweenBlur(to, dur) {
    if (blurTw) blurTw.cancel();
    blurTw = CLSkyMotion.tween({ from: blur, to: to, dur: dur, ease: T.EASE.lens, onUpdate: function (v) { blur = v; post.setBlur(v); }, tag: 'deep' });
  }
  function setMode(m, name) {
    if (!inited) return;
    var prev = mode; mode = m;
    /* 视角的家跟着态走（星座 / 星盘各一个）；罗盘绕晶体转，环游（绕盘心进动）必须让位 */
    if (view) { if (view.useHome) view.useHome(m === 'plot' ? 'plot' : 'constellation'); if (m === 'compass' && view.current().tour) view.tour(false); }
    doc.body.classList.toggle('skd-plot', m === 'plot');
    if (prev === 'compass' && m !== 'compass' && homeStale) refreshHome();
    /* 原生 4K 升档：罗盘（双晶折射 + 轴签引线）在满分辨率下掉到 52–54 fps，钉在标准像素上限；星座 / 星盘自动升档，换态清掉连败锁 */
    if (S.setBoost) S.setBoost(m === 'compass' ? false : null);
    /* 景深转场：对焦到近处（罗盘晶体 / 星盘）时远天失焦，回到星座时重新合焦 */
    if (cosmos && cosmos.setDefocus) cosmos.setDefocus(m === 'compass' ? 1 : m === 'plot' ? 0.35 : 0);
    if (m === 'plot') {
      tweenBlur(0, T.DUR.focus);
      rings.setState('plot'); fx.setState('plot');
      starState('dim'); neb.setState('dim'); bun.setState('dim'); bun.emphasize({ group: -1, star: null }); stars.setLit(null); neb.hover(-1);
      if (prev !== 'plot') {
        rings.reveal(0);
        if (revealTw) revealTw.cancel();
        revealTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.unfurl, delay: 0.25, ease: T.EASE.inOut, onUpdate: function (v) { rings.reveal(v); }, tag: 'deep' });
      }
      orb.close(); hideCard();
      if (cosmos) cosmos.setState('show');
    } else if (m === 'compass') {
      if (cosmos) cosmos.setState('dim');
      tweenBlur(0, 0);
      rings.setState('hidden'); fx.setState('hidden'); starState('hidden'); neb.setState('hidden'); bun.setState('hidden');
      stars.setLit(null); hideCard();
      var anchor = S.crownAnchor ? S.crownAnchor() : null, info = sky(), n = name ? S.nodeOf('c:' + name) : null;
      if (anchor && g.THREE) {
        var v = new g.THREE.Vector3(); anchor.getWorldPosition(v);
        orb.open({ center: v, radius: 150, color: n ? groupColor(info, n.camp) : T.C.BRASS });
        bindSats();
      }
      cascade();
      /* 俯冲：镜头飞向晶体的同时，泛光先冲高再回落——像推近一颗星时它在视野里爆亮 */
      if (prev !== 'compass') flare();
    } else {
      tweenBlur(T.BLUR.backdrop, prev === 'compass' ? 0.01 : T.DUR.focus);
      rings.setState('backdrop'); fx.setState('hidden'); starState('show'); neb.setState('show'); bun.setState('show');
      rings.setEmph(-1, -1); rings.setCursor(-1); fx.setNeedle(null); fx.setWake(null); fx.setWedge(null); stars.setLit(null);
      if (revealTw) { revealTw.cancel(); revealTw = null; } rings.reveal(1);
      orb.close(); if (cards.kind() === 'axis') hideCard();
      if (cosmos) cosmos.setState('show');
    }
    syncViews();
  }

  /* 关系星轨：罗盘的联系对象按关系类型上轨（内 亲近 = 合作 / 亲缘 / 情感 · 中 对抗 = 对立 / 暗线 · 外 其他 = 其余与同场推导），
     下标与罗盘卫星一致；悬停卫星或事件珠时，读层点亮哪几位，星轨上就是哪几颗亮、其余压暗 */
  var ORB_RING = { ally: 0, kin: 0, bond: 0, oppose: 1, dark: 1 }, ORB_NAME = ['内 亲近', '中 对抗', '外 其他'];
  function bindSats() {
    if (!sats || !g.CLSkyCompass) return;
    var list = CLSkyCompass.satellites(), kmax = 0, used = [0, 0, 0];
    list.forEach(function (s) { kmax = Math.max(kmax, s.strength || 0); });
    sats.set(orb.rig(), list.map(function (s) {
      var r = ORB_RING[s.cls] != null ? ORB_RING[s.cls] : 2; used[r]++;
      return { ring: r, hex: T.relHex(s.cls), k: kmax > 0 ? (s.strength || 0) / kmax : 0.5 };
    }));
    var note = doc.querySelector('.skc-note'), txt = ORB_NAME.filter(function (x, i) { return used[i] > 0; }).join(' · ');
    if (note) { if (txt && tierName !== 'low') note.setAttribute('data-orbit', txt); else note.removeAttribute('data-orbit'); }
    syncHot();
  }
  function syncHot() {
    var idx = [];
    Array.prototype.forEach.call(doc.querySelectorAll('.sky-compass .skc-sat.is-lit'), function (el) { idx.push(+el.getAttribute('data-sat')); });
    sats.setHot(idx);
  }
  function onSatSync(e) {
    if (!inited || mode !== 'compass' || !sats || !e.target.closest || !e.target.closest('.sky-compass')) return;
    syncHot();
  }
  /* 罗盘入场（一次性）：因果珠按回序从第一颗烧到最后一颗——先看见时间往哪走；联系对象按关系强弱依次浮现。减弱动效不播 */
  /* 收尾用墙钟（CSS 动画走墙钟；动效时钟在掉帧时会放慢，类名会赖着不走、挡住悬停压暗） */
  var cascadeTimer = 0;
  function cascade() {
    var el = doc.querySelector('.sky-compass'); if (!el) return;
    if (cascadeTimer) { clearTimeout(cascadeTimer); cascadeTimer = 0; }
    el.classList.remove('skd-cascade');
    if (reduced()) return;
    function stagger(list) { var n = list.length; Array.prototype.forEach.call(list, function (x, k) { x.style.setProperty('--skd-i', n > 1 ? (k / (n - 1)).toFixed(3) : '0'); }); }
    stagger(el.querySelectorAll('.skc-ev')); stagger(el.querySelectorAll('.skc-sat')); stagger(el.querySelectorAll('.skc-link'));
    /* 不读框重启动画（Q5.5）：CLSkyCompass.open 刚把卫星 / 连线 / 珠整批新建，新节点首次算样式时动画自然从头播；
       这里强制一次整页同步布局在大书进罗盘那一下要 11 ms */
    el.classList.add('skd-cascade');
    cascadeTimer = setTimeout(function () { el.classList.remove('skd-cascade'); cascadeTimer = 0; }, (T.DUR.fly + T.DUR.focus) * 1000 + 100);
  }

  var flareTw = null;
  function flare() {
    var core = S.core && S.core(), bloom = core && core.getBloom ? core.getBloom() : null;
    if (!bloom || reduced()) return;
    if (flareTw) flareTw.cancel();
    var base = bloom.strength;
    flareTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.dive, ease: function (t) { return t; },
      onUpdate: function (k) { bloom.strength = base * (1 + 1.6 * Math.sin(Math.PI * Math.min(1, k * 1.25)) * (1 - k * 0.2)); },
      onDone: function () { bloom.strength = base; }, tag: 'deep' });
  }

  /* ── 读层事件 ─────────────────────────────────────── */
  function light(names) { if (!inited) return; stars.setLit(names && names.length ? names : null); }
  function lineHover(info) {
    if (!inited || !rings) return;
    if (!info) { rings.setEmph(-1, -1); fx.setWedge(null); return; }
    var i = lineIdx && lineIdx[info.id] != null ? lineIdx[info.id] : -1, d = disc.desc(), it = d && i >= 0 ? d.items[i] : null;
    rings.setEmph(i, it ? it.mainIdx : -1);
    if (it) fx.setWedge({ a0: it.a0, a1: it.a1, r0: d.rIn * 0.22, r1: it.r, z1: it.z || 0, color: it.color || genHex(it.gen, it.kind) });
  }
  /* o.snap：拨盘拖动时指针已在 sky-dial 里按弹簧平滑过，光层指针直接落位、不再追 0.12 s（sky-rings-fx setNeedle 的第二参） */
  function setCursor(c, o) {
    if (!inited || !M) return;
    if (c == null) { rings.setCursor(-1); fx.setNeedle(null); fx.setWake(null); if (scale) scale.setCursor(null); return; }
    var A = g.CLSkyModel.angleAt, a = A(c + 0.5, M.nCh), k = Math.max(1, Math.round(M.nCh * 0.04));
    rings.setCursor((c + 0.5) / M.nCh); fx.setNeedle(a, !!(o && o.snap)); fx.setWake(A(Math.max(0, c + 0.5 - k), M.nCh), a);
    if (scale) scale.setCursor(c);
  }

  /* 深空浮现要两件事都到：镜头落定（captureHome 定下数据区方向）+ 揭幕走到实体化（solid）；谁后到谁放行 */
  function captureHome() {
    if (!view || !S.camera || !S.controls) return;
    view.setHome({ p: S.camera.position.clone(), t: S.controls.target.clone() }); syncViews(); homeSet = true;
    if (cosmos) {
      var f = S.controls.target.clone().sub(S.camera.position).normalize();
      if (!homeDir || homeDir.dot(f) < 0.99995) { cosmos.reorient([f.x, f.y, f.z]); homeDir = f; }   /* 同一方向（跳过揭幕时先定过一次）不重转天球，免得深空跳一下 */
      if (cosmosReady) cosmos.setState(mode === 'compass' ? 'dim' : 'show');
    }
  }
  /* now = 跳过揭幕：星云 / 深空一帧到位；镜头还没来得及定家就先定（镜头早已落定，之后 homeTw 那次只是复核） */
  function solid(now) {
    cosmosReady = true;
    if (now && !homeSet) captureHome();
    if (mode === 'constellation') neb.setState('show', now);
    if (cosmos && homeSet) cosmos.setState(mode === 'compass' ? 'dim' : 'show', now);
  }

  /* ── 生命周期 ─────────────────────────────────────── */
  function init(ctx) {
    T = g.CLSkyTokens; S = ctx.scene; disc = ctx.disc; field = ctx.field; app = ctx.app; cards.setElement(ctx.card || null);
    if (inited || !T || !S || !g.THREE || !g.CLSkyMotion) return false;
    try {
      post = g.CLSkyPost.install(S);
      cosmos = g.CLSkyCosmos && g.CLSkyCosmosBake && g.CLSkyCosmosStars ? g.CLSkyCosmos.create({ scene: S }) : null;
      stars = g.CLSkyStars.create({ scene: S });
      trails = g.CLSkyTrails ? g.CLSkyTrails.create({ scene: S }) : null;
      neb = g.CLSkyNebula.create({ scene: S });
      bun = g.CLSkyBundles.create({ scene: S });
      var anchor = disc && disc.anchor ? disc.anchor() : null;
      rings = g.CLSkyRings.create({ scene: S, anchor: anchor });
      fx = g.CLSkyRingsFx.create({ scene: S, anchor: anchor });
      orb = g.CLSkyOrrery.create({ scene: S });
      sats = g.CLSkyOrrerySats && orb.rig ? g.CLSkyOrrerySats.create({ scene: S }) : null;
      view = g.CLSkyView.install({ scene: S, canvas: doc.getElementById('gl'), onChange: syncViews });
      rev = g.CLSkyReveal && g.CLSkyRevealGLSL ? g.CLSkyReveal.create({ scene: S }) : null;
    } catch (e) {
      if (g.console) console.warn('[sky-deep] 光层初始化失败，退回 SVG 读层', e);
      [post, cosmos, stars, trails, neb, bun, rings, fx, orb, sats, view, rev].forEach(function (m) { try { if (m && m.dispose) m.dispose(); } catch (e2) {} });
      post = cosmos = stars = trails = neb = bun = rings = fx = orb = sats = view = rev = null;
      return false;
    }
    inited = true;
    doc.body.classList.add('skd-gl');
    buildViews(ctx.hud);
    if (S.on) S.on('hover', onStarHover);
    if (field && field.on) field.on('hover', onCampHover);
    g.addEventListener('pointermove', cards.move, { passive: true });
    doc.addEventListener('pointerover', cards.axisOver); doc.addEventListener('pointerout', cards.axisOut);
    doc.addEventListener('focusin', cards.axisOver); doc.addEventListener('focusout', cards.axisOut);
    doc.addEventListener('pointerover', onSatSync); doc.addEventListener('pointerout', onSatSync);
    /* 视口变了（拖窗口 / 窄屏 ↔ 宽屏）：星座的家换成新视口下的取景——否则复位与视角预设会飞回旧视口的中心。
       罗盘里星座组被晶体舞台接管（量出来的不是星座的取景），记下「家已过期」，退出罗盘时再量 */
    g.addEventListener('resize', function () {
      clearTimeout(homeT);
      homeT = setTimeout(function () { if (mode === 'compass') homeStale = true; else refreshHome(); }, 260);
    });
    /* 双击空白处 = 复位视角（双击星不算：星由单击进入罗盘） */
    var cv = doc.getElementById('gl');
    if (cv) cv.addEventListener('dblclick', function (e) { if (mode === 'compass' || !view) return; var hit = S.pick ? S.pick(e.clientX, e.clientY) : null; if (!hit) { view.reset(); syncViews(); } });
    return true;
  }
  function onGraph(model, graph, player) {
    if (!inited) return;
    if (rev) rev.finish();   /* 上一部书的揭幕若还没走完，先一帧收尾，免得它的补间改写新书的点火 */
    M = model; G = graph; mode = 'constellation'; hoverStar = null; hotCamp = null; hideCard(); cosmosReady = !rev; homeSet = false; homeDir = null;
    counts(); buildStars(); buildField(); buildRings(); buildCosmos();
    if (cosmos && cosmos.setDefocus) cosmos.setDefocus(0);
    if (S.setBoost) S.setBoost(null);
    CLSkyMotion.cancelAll('deep');
    blur = T.BLUR.backdrop; post.setBlur(blur);
    rings.setState('backdrop'); fx.setState('hidden'); neb.setState(rev ? 'hidden' : 'show'); bun.setState('show'); starState('show'); orb.close();
    /* 揭幕 = 线稿构建（sky-reveal）：一条自 12 点顺时针的扫掠——线框闪现 → 星座线描出 → 星随扫掠点亮 → 束丝生长 → 星云 / 深空实体化 → 主角星点睛；
       星盘主环随后自 12 点展开（背景态，仍虚化）。等读取幕离场那一刻才开始（reveal）；幕没开或壳层没来叫，6 秒后自己开始，星不会一直不亮 */
    stars.setIgnite(0, true); rings.reveal(0);
    pendingReveal = function () {
      if (rev) rev.stage({ info: sky(), hero: heroKey, stars: stars, bun: bun, solid: solid });
      else igniteTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.ignite, ease: T.EASE.out, onUpdate: function (v) { stars.setIgnite(v); }, tag: 'deep' });
      revealTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.unfurl, delay: 0.6, ease: T.EASE.inOut, onUpdate: function (v) { rings.reveal(v); }, tag: 'deep' });
    };
    if (revealFallback) clearTimeout(revealFallback);
    revealFallback = setTimeout(reveal, 6000);
    homeTw = CLSkyMotion.seq([{ at: 1.9, fn: captureHome }], 'deep');
    if (player && g.CLSkyScale) {
      if (!scale) {
        var scrub = player.querySelector('input[type=range]'), wrap = mk('div', 'skd-scale');
        if (scrub) { scrub.parentNode.insertBefore(wrap, scrub); wrap.appendChild(scrub); scale = CLSkyScale.mount(wrap, {}); }
      }
      if (scale) scale.update({ nCh: M.nCh, mains: M.mains.map(function (m) { return { c0: m.c0, c1: m.c1, color: T.GEN[m.gen % T.GEN.length] }; }), density: M.density || [], keys: M.keyChapters || [] });
    }
    syncViews();
  }
  var pendingReveal = null, revealFallback = 0, homeT = 0, homeStale = false;
  function refreshHome() { homeStale = false; var h = app && app.atlas && app.atlas.home ? app.atlas.home() : null; if (h && view && G) view.setHome({ p: h.p, t: h.t }); }
  function reveal() {
    if (revealFallback) { clearTimeout(revealFallback); revealFallback = 0; }
    if (!pendingReveal) return false;
    var f = pendingReveal; pendingReveal = null; f(); return true;
  }
  function regroup() { if (!inited) return; liveUntil = now() + 3.2; }
  function frame(dt, tAnim, degrade) {
    if (!inited) return;
    clock += dt || 0;
    CLSkyMotion.tick(dt || 0);
    var tn = T.tierOf(degrade | 0);
    if (tn !== tierName) {
      tierName = tn; [cosmos, post, stars, trails, neb, bun, rings, fx, orb, sats, rev].forEach(function (m) { if (m && m.setTier) m.setTier(tn); });
      if (mode === 'compass') bindSats();
    }
    if (sky() !== skyRef && G) { buildStars(); buildField(); }
    if (disc && disc.rev && disc.rev() !== discRev && G) buildRings();
    var live = now() < liveUntil;
    /* 背景视差：指针位置 → 背景三层星尘错动（uPar 原本从未被写） */
    var bg = S.core && S.core() && S.core().bgMat;
    if (bg && bg.uniforms.uPar && !reduced()) {
      var W = g.innerWidth || 1, H = g.innerHeight || 1, px = (pointer.x / W - 0.5) * 2, py = (pointer.y / H - 0.5) * -2, k = 1 - Math.exp(-(dt || 0) * 2.5);
      bg.uniforms.uPar.value.x += (px - bg.uniforms.uPar.value.x) * k; bg.uniforms.uPar.value.y += (py - bg.uniforms.uPar.value.y) * k;
    }
    if (cosmos) { cosmosFocus(); cosmos.update(dt, tAnim); }
    post.update(dt, tAnim); stars.update(dt, tAnim); if (trails) trails.update(dt, tAnim); neb.update(dt, tAnim, live); bun.update(dt, tAnim, live);
    rings.update(dt, tAnim); fx.update(dt, tAnim); orb.update(dt, tAnim); view.update(dt, tAnim);
    if (sats) sats.update(dt, tAnim, orb.stats().alpha);
    if (rev) rev.update(dt);
  }
  function stats() {
    if (!inited) return { inited: false };
    return { inited: true, mode: mode, blur: +blur.toFixed(2), cosmos: cosmos ? cosmos.stats() : null, legacySky: S.core && S.core().legacySky ? S.core().legacySky() : null, post: post.stats(), stars: stars.stats(), trails: trails ? trails.stats() : null, nebula: neb.stats(), bundles: bun.stats(),
      rings: rings.stats(), fx: fx.stats(), orrery: orb.stats(), sats: sats ? sats.stats() : null, view: view.current(), tier: tierName, motion: CLSkyMotion.stats(), reveal: rev ? rev.stats() : null };
  }

  /* Q5.5 · 罗盘星轨 / 卫星的着色器预热：读取幕里造一套一次性的星轨 + 卫星挂进场景，交给调用方在线性目标下编译，随后销毁
     （材质 dispose 在 scene-core 里置空，程序常驻缓存）——首开罗盘不再现场链接这 3 个程序。返回收尾函数；从不上屏（同一任务里就销毁） */
  function prewarmCompass() {
    if (!inited || !g.CLSkyOrrery || !g.THREE) return null;
    var o = null, st = null;
    try {
      o = g.CLSkyOrrery.create({ scene: S });
      o.open({ center: new g.THREE.Vector3(0, 0, 0), radius: 1 });
      if (g.CLSkyOrrerySats && o.rig) { st = g.CLSkyOrrerySats.create({ scene: S }); st.set(o.rig(), [0, 1, 2].map(function (r) { return { ring: r, hex: T.C.BRASS, k: 1 }; })); }
    } catch (e) {}
    return function () { try { if (st) st.dispose(); } catch (e1) {} try { if (o) o.dispose(); } catch (e2) {} };
  }

  g.CLSkyDeep = { init: init, onGraph: onGraph, reveal: reveal, frame: frame, setMode: setMode, light: light, lineHover: lineHover, setCursor: setCursor, regroup: regroup, prewarmCompass: prewarmCompass,
    lineCard: lineCard, resetView: function () { if (view && mode !== 'compass') view.reset(); syncViews(); }, captureHome: captureHome, stats: stats, enabled: function () { return inited; },
    /* 预演 / 验收用：模拟悬停一颗星 / 一个团名（与真实指针走同一条路径） */
    hoverStar: function (name, quiet) { onStarHover(name ? { name: name } : null, !!quiet); return hoverStar; },
    hoverCamp: function (name, quiet) { var info = sky(), i = name ? sectorIndex(info, name) : -1; onCampHover(i >= 0 ? info.sectors[i] : null, !!quiet); return hotCamp; },
    setPlotHome: function (pose) { return !!(view && view.setHome && view.setHome(pose, 'plot')); },
    nudge: function (dAz, dPol) { if (!view || !view.nudge) return false; var r = view.nudge(dAz, dPol); syncViews(); return r; },
    /* 视角预设 / 环游 / 复位只属于星座与星盘（罗盘绕晶体转，预设会把镜头拽回盘心、和轨道锁打架） */
    preset: function (k) { if (!view || mode === 'compass') return false; var r = k === 'tour' ? view.tour(true) : view.preset(k); syncViews(); return r !== false; } };
})(window);
