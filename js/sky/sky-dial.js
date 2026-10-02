/*!
 * @role component
 * @owns js/sky/sky-dial.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 星盘拨盘（Q2.1 命中环 + 指针拖拽 · Q2.2 物理 · Q2.3 联动节流），只在剧情态工作；几何在 sky-dial-geom.js（CLSkyDialGeom），读层画面在 sky-dial-fx.js（CLSkyDialFx）。
 *  · 命中：document 捕获阶段（开书后才挂）——屏幕点 → 射线 → 盘面 → 极角 → 回目格；从命中环按下的左键 / 单指独占（不转镜头、不判点星）。
 *  · 物理：跟手 SPRING.follow + 慢拖章节磁吸；松手慢 / 点按 → SPRING.dial 落到手下那一回（欠阻尼，落定回弹）；快 → 甩动惯性（摩擦按落点整回反解）→ 落定回弹；
 *    首尾挡板 L·tanh 软限位 + 回弹。减弱动效：跟手照常，松手一帧落整回。
 *  · 联动：逐帧只推指针（CLSkyDeep.setCursor(slot − 0.5)：光层指针 / 尾迹 / 刻度尺）与读层；跨回的重活 CLSky.seek(c)（星盘各弧 / 参与者 / 卡片 / 点亮）
 *    转动中至多每 SEEK 秒一次，落定时补齐最后一回。disc 有 scrub(on) / setPointer(slot|null) 就用。
 * 测试钩子：at(slot, px) → 刻度环上格位的屏幕点（px 沿径向外移）· pick(x, y) · state() · stats()。不私开 rAF。
 */
(function (g) {
  'use strict';
  var doc = g.document, G = g.CLSkyDialGeom;
  if (!G || !doc || !doc.body) return;
  /* px / s：点击判别 · 摩擦 1/s · 甩动门槛（rad/s）· 转动中跨回重活的最短间隔 */
  var SLOP = { mouse: 3, touch: 8 }, MU = 3.2, FLING = 1.1, SEEK = 0.09, SNAP = { snap: true };
  var BC = doc.body.classList, TK = null, SP = null, S = null, hk = null, D = null, wired = false;
  var P = null, ph = 0, s = 0, v = 0, tgt = 0, mu = MU, cc = -1, tPh = 0, tSk = 0, hot = null, eat = 0, al = 0, gk = 0;
  var st = { grabs: 0, taps: 0, flings: 0, seeks: 0, deferred: 0, settle: 0, frames: 0 }, PH = ['idle', 'drag', 'coast', 'settle'];

  function sky() { return g.CLSky && CLSky.enabled && CLSky.enabled() ? g.CLSky : null; }
  function dsk() { var k = sky(); return k && k.disc ? k.disc() : null; }
  function ready() { var d = dsk(); return !!(S && d && BC.contains('sky-plot-on') && !BC.contains('sky-compass-on') && d.state() === 'plot' && d.anchor() && (D = G.sync(d))); }
  function disp(x) { var lo = 0.5, hi = D.n - 0.5, L = D.rub; return x < lo ? lo - L * Math.tanh((lo - x) / L) : x > hi ? hi + L * Math.tanh((x - hi) / L) : x; }
  function near(x) { return Math.max(0.5, Math.min(D.n - 0.5, Math.floor(x) + 0.5)); }
  function cur() { var c = D.d.cursor(); return c == null ? null : c; }
  function look() { G.rect(); G.mat(S); }
  function hit(x, y) { return G.hit(x, y, cur(), ph ? disp(s) : null); }
  function okT(t) {
    if (t === S.renderer.domElement) return true;
    if (!t || !t.closest || t.closest('button,a,input,select,textarea,[data-name],[data-line-id],.sd-hit')) return false;
    return !!t.closest('#labels,.sky-disc');
  }

  /* ── 输入 ─────────────────────────────────────────── */
  function onDown(e) {
    if (P) { if (e.pointerId !== P.id) up(null); return; }   /* 第二指 = 捏合：松开拨盘、放行 */
    var t = e.pointerType === 'touch', h, c;
    if (e.isPrimary === false || !t && (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) || !ready() || !okT(e.target)) return;
    G.rect(true); G.mat(S);
    if (!(h = hit(e.clientX, e.clientY))) return;
    e.stopPropagation(); e.preventDefault();
    c = cur();
    P = { id: e.pointerId, touch: t, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, a: h.a, f: h.slot, vf: 0, t: e.timeStamp, moved: false,
      px: G.dist(G.pj(D.rB, G.ang(h.slot)), G.pj(D.rB, G.ang(h.slot + 1))),
      camTarget: S.controls && S.controls.target ? S.controls.target.clone() : null,
      camPos: S.camera && S.camera.position ? S.camera.position.clone() : null };
    if (!ph) { s = c != null ? c + 0.5 : h.slot; v = 0; cc = c != null ? c : -1; }   /* 拨盘还在转 → 接住它（保留 s / v） */
    ph = 1; tPh = 0; tSk = SEEK; st.grabs++;
    try { CLSky.stop(); } catch (e1) {}
    if (D.d.scrub) D.d.scrub(true);
    try { doc.body.setPointerCapture(e.pointerId); P.cap = 1; } catch (e2) {}
    setHot(null); BC.add('sky-dial-grabbing');
  }
  /* 手指格位（跨接缝连续展开）；ts 只由指针事件给：帧里补算（镜头在动）只更新位置、不计速度 */
  function track(x, y, ts) {
    var h = G.plane(x, y), df, dt;
    if (!h || h.r < 0.35 * D.rB) return;   /* 指到盘心附近：方位不可信，不动 */
    df = -G.wrap(h.a - P.a) / D.dA; dt = ts ? (ts - P.t) / 1000 : 0;
    P.a = h.a; P.f += df;
    if (dt > 0) { P.vf = speed(ts) + (df / dt - speed(ts)) * Math.min(1, dt / 0.05); P.t = ts; }
  }
  function speed(ts) { return P.vf * Math.exp(-Math.max(0, ts - P.t) / 50); }   /* 手速按距上一个移动事件的时长衰减（停手 = 0） */
  function onMove(e) {
    if (!P) { if (!e.buttons && e.pointerType !== 'touch') hover(e); return; }
    if (e.pointerId !== P.id) return;
    e.stopPropagation();
    if (!P.touch && !(e.buttons & 1)) return up(e);
    P.x = e.clientX; P.y = e.clientY;
    if (!P.moved && Math.hypot(P.x - P.x0, P.y - P.y0) > SLOP[P.touch ? 'touch' : 'mouse']) P.moved = true;
    if (D) { G.mat(S); track(P.x, P.y, e.timeStamp); }
  }
  function onUp(e) { if (P && e.pointerId === P.id) { e.stopPropagation(); up(e.type === 'pointerup' ? e : null); } }
  /* 松手：点按 / 慢 → 落到手下那一回；快 → 甩；减弱动效 → 下一帧即整回 */
  function up(e) {
    var q = P, vr, T0, dd;
    if (!q) return;
    if (q.cap) try { doc.body.releasePointerCapture(q.id); } catch (e1) {}
    P = null; BC.remove('sky-dial-grabbing'); eat = e ? e.timeStamp : 0; tPh = 0;   /* 落定时长从松手起算 */
    if (!q.moved) st.taps++;
    if (!D || ph !== 1) return;
    vr = e && q.moved ? q.vf * Math.exp(-Math.max(0, e.timeStamp - q.t) / 50) : 0;
    if (TK.reduced()) { s = tgt = near(q.f); v = 0; ph = 3; return; }
    if (Math.abs(vr) * D.dA < FLING) { tgt = near(q.f); ph = 3; return; }
    st.flings++; T0 = near(q.f + vr / MU); dd = T0 - s; v = vr; tgt = T0; mu = MU; ph = 2;
    if (dd * vr > 0 && Math.abs(dd) > 0.3) mu = Math.max(0.6 * MU, Math.min(1.8 * MU, vr / dd)); else ph = 3;
  }
  function hover(e) { var h = null; if (ready() && okT(e.target)) { look(); h = hit(e.clientX, e.clientY); } setHot(h); }
  function setHot(h) { hot = h; if (!!h !== BC.contains('sky-dial-hot')) BC.toggle('sky-dial-hot', !!h); }

  /* ── 物理（格位 slot：第 c 回占 [c, c+1)，格心 c + 0.5）─────────── */
  function detent(f) {   /* 慢拖磁吸：格心附近变「粘」、过格界变快；手快或格窄（< 4 px）时退回线性 */
    var m, c, u;
    if (f <= 0.5 || f >= D.n - 0.5) return f;
    m = Math.max(0, 1 - Math.abs(speed(g.performance.now())) * D.dA / 1.2) * Math.max(0, Math.min(1, (P.px - 4) / 10));
    if (m < 0.02) return f;
    c = Math.floor(f); u = f - c - 0.5;
    return c + 0.5 + (u < 0 ? -0.5 : 0.5) * Math.pow(Math.abs(2 * u), 1 + 2 * m);
  }
  function spring(q, x, h) { v += (q.w * q.w * (x - s) - 2 * q.z * q.w * v) * h; s += v * h; }
  function step(dt) {
    var n = Math.max(1, Math.ceil(dt * 240)), h = dt / n, f = P ? detent(P.f) : 0, i;
    tPh += dt;
    for (i = 0; i < n && ph; i++) {
      if (ph === 1) spring(SP.follow, f, h);
      else if (ph === 2) { v *= Math.exp(-mu * h); s += v * h; if (Math.abs(tgt - s) < 0.25 || (tgt - s) * v <= 0 || Math.abs(v) * D.dA < 0.2) ph = 3; }
      else { spring(SP.dial, tgt, h); if (Math.abs(s - tgt) < 2e-3 && Math.abs(v) < 0.03) finish(); }
    }
  }
  function finish() { s = tgt; v = 0; ph = 0; st.settle = +tPh.toFixed(3); commit(tgt, 1); if (D.d.scrub) D.d.scrub(false); }
  function abort() { if (ph && D) { if (D.d.setPointer) D.d.setPointer(null); if (D.d.scrub) D.d.scrub(false); } ph = 0; }
  /* 指针逐帧；跨回的重活（CLSky.seek）转动中节流，force = 落定那一下必做 */
  function commit(x, force) {
    var c = Math.max(0, Math.min(D.n - 1, Math.floor(x)));
    if (c !== cc) {
      if (force || tSk >= SEEK) { cc = c; tSk = 0; st.seeks++; CLSky.seek(c); } else st.deferred++;
    }
    if (D.d.setPointer) D.d.setPointer(ph ? x : null);
    if (g.CLSkyDeep && CLSkyDeep.setCursor) CLSkyDeep.setCursor(x - 0.5, SNAP);   /* snap：光层指针不再叠自己的 0.12 s 平滑（待 sky-deep / sky-rings-fx 接） */
  }
  function frame(dt, _a, _b, _c, dg) {
    var FX = g.CLSkyDialFx, want, red;
    if (!ph && !P && !hot && !(al > 0.004)) { if (FX) FX.hide(); return; }
    if (!ready()) { if (P) up(null); abort(); setHot(null); al = 0; if (FX) FX.hide(); return; }
    /* Document capture owns the dial pointer, but the stage has its own
       cinematic drift loop. Hold the camera pose for the whole drag/settle
       transaction so a chapter scrub never becomes a hidden camera pan. */
    if ((P || ph) && P && P.camTarget && S.controls && S.controls.target) {
      S.controls.target.copy(P.camTarget);
      if (P.camPos && S.camera) { S.camera.position.copy(P.camPos); S.camera.lookAt(P.camTarget); S.camera.updateMatrixWorld(true); }
    }
    if (ph >= 2 && cur() !== cc) abort();   /* 落定途中别处改了当前回（播放 / 键盘）：让位 */
    st.frames++; dt = Math.min(0.05, Math.max(0, +dt || 0)); look(); tSk += dt;
    if (P) track(P.x, P.y, 0);
    if (ph) step(dt);
    if (ph) commit(disp(s));
    want = ph || P || hot ? 1 : 0; red = TK.reduced();
    al = red ? want : al + (want - al) * (1 - Math.exp(-dt / 0.12));
    gk = red ? (P ? 1 : 0) : gk + ((P ? 1 : 0) - gk) * (1 - Math.exp(-dt / 0.08));
    if (!want && al < 0.004) { al = 0; if (FX) FX.hide(); return; }
    if (FX) FX.draw({ dt: dt, low: TK.tierOf(dg) === 'low', red: red, al: al, gk: gk, drag: !!P, hot: hot, slot: ph ? disp(s) : null, cur: cur(),
      w: G.rect().width, h: G.rect().height, n: D.n, sp: D.sp, rB: D.rB, tk: D.tk, soft: TK.DUR.soft, pj: G.pj, ang: G.ang, near: near });
  }

  /* ── 接线（不写宿主文件）──────────────────────────── */
  function ensure() {
    var sc = g.CLScene && CLScene.current, d = dsk();
    if (!sc || !sc.registerFrameHook || !d || !d.el || !d.el.parentNode || !g.CLSkyTokens) return;
    TK = g.CLSkyTokens; SP = TK.SPRING; S = sc; G.reset();
    if (P) up(null); abort(); setHot(null);
    if (g.CLSkyDialFx) CLSkyDialFx.mount(d.el.parentNode, d.el);
    if (hk !== sc) { hk = sc; sc.registerFrameHook(frame); }
    if (wired) return;
    wired = true;
    doc.addEventListener('pointerdown', onDown, true); doc.addEventListener('pointermove', onMove, true); doc.addEventListener('pointerup', onUp, true);
    doc.addEventListener('pointercancel', onUp, true);
    doc.addEventListener('click', function (e) { if (eat && e.timeStamp - eat < 600) { eat = 0; e.stopImmediatePropagation(); e.preventDefault(); } }, true);
    g.addEventListener('blur', function () { if (P) up(null); setHot(null); });
    g.addEventListener('resize', function () { G.reset(); if (P) up(null); });
  }
  doc.addEventListener('cl:graph-ready', function () { g.setTimeout(ensure, 0); });
  if (g.CLSky && CLSky.model && CLSky.model()) ensure();

  g.CLSkyDial = {
    at: function (x, px) { var a, p, rc; if (!ready()) return null; rc = G.rect(true); G.mat(S); a = G.ang(x); p = G.pj(D.rB + (px || 0) / (G.prAt(a) || 1), a); return p ? [rc.left + p[0], rc.top + p[1]] : null; },
    pick: function (x, y) { var h; if (!ready()) return null; G.rect(true); G.mat(S); h = hit(x, y); return h ? { zone: h.zone, slot: +h.slot.toFixed(4), chapter: Math.max(0, Math.min(D.n - 1, Math.floor(h.slot))) } : null; },
    state: function () { return { phase: PH[ph], slot: D && ph ? +disp(s).toFixed(4) : null, v: +v.toFixed(4), target: ph >= 2 ? tgt : null, finger: P ? +P.f.toFixed(4) : null, chapter: cc, hot: !!hot, drag: !!P, cellPx: P ? +P.px.toFixed(2) : null, rub: D ? +D.rub.toFixed(4) : null }; },
    stats: function () { var o = { phase: PH[ph] }, k, f = g.CLSkyDialFx ? CLSkyDialFx.stats() : {}; for (k in st) o[k] = st[k]; for (k in f) o[k] = f[k]; return o; },
    release: function () { if (P) up(null); }
  };
})(window);
