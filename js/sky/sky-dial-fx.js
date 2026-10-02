/*!
 * @role component
 * @owns js/sky/sky-dial-fx.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 拨盘读层（Q2.2 刻度光斑跟指针）：一张盖在星盘上的 canvas，只被宿主 sky-dial 每帧调用，自己不开 rAF / setInterval。
 *  · 刻度光斑：手指所在格位的刻度最亮，两侧按格距衰减（高斯），拖动中（gk）收窄、变亮；只是悬停（hot）时淡而宽。
 *  · 指针游标：刻度环上一道沿径向的亮痕 + 一点辉光，位置就是宿主给的 slot（含首尾软限位的回弹量，所以拖过头看得见「顶住了」）。
 *  · 落点提示：指针还在转（离格心 > 0.15 格）时，松手会落到的那一整回（near(slot)）在刻度环上点一道细亮刻痕；停在格心就与指针重合、不另画。
 *    只画在刻度带里（r0…r1）：环外是星盘的回数字、环内是主线弧名，记号放那两处会压字。已生效的当前回由星盘自己的回数字与光层指针表示，这里不重复。
 *  · 彗尾：指针走得越快，身后沿环拖出的一截越长（与揭幕彗头、牵引丝笔尖彗星同一语汇）；速度取相邻两帧格位差，low 档与减弱动效不画。
 * 全部颜色取 CLSkyTokens.C，不自带色值；坐标一律走宿主传进来的 pj / ang（与刻度、命中同一套投影）。
 * 样式：css/sky-dial.css（铺满 #stage、pointer-events:none、[hidden] 收起）；这里只切 hidden 与画布像素尺寸。
 * 降级：本层没有自有动画（每一帧都由宿主传进来的 al / gk 决定画什么），减弱动效时宿主把 al / gk 一帧推到位，
 *   这里自然就没有过渡；low 档 = 只画指针亮痕与落点刻痕，不画刻度光斑与辉光。
 * CLSkyDialFx = { mount(host, discEl), draw(o), hide(), stats() }
 */
(function (g) {
  'use strict';
  var doc = g.document;
  if (!doc) return;

  var cv = null, cx = null, host = null, ref = null, dpr = 1, W = 0, H = 0, on = false;
  var lastX = null, vSlot = 0;   /* 上一帧格位与平滑后的格位速度（格 / 秒），用来定彗尾长度 */
  var st = { mounts: 0, draws: 0, hides: 0, w: 0, h: 0 };
  /* 光斑覆盖的格数（拖动时收窄）· 指针亮痕沿径向的长度比 · 记号半径 px */
  var SPAN = [3.4, 1.9], LIFT = 1.5;
  /* 彗尾：每（格 / 秒）换算成多少格尾长 · 尾长上限（格） · 采样段数 */
  var TAILK = 0.16, TAILMAX = 9, TAILN = 14;

  function TK() { return g.CLSkyTokens; }
  function hex(n, a) {
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  /* 舞台尺寸由宿主传（它缓存的 #stage 矩形，窗口变化才重量）：逐帧读 getBoundingClientRect 会在别的层改过 DOM 后强制同步排版 */
  function size(o) {
    var r = o.w > 0 ? o : host.getBoundingClientRect(), d = g.devicePixelRatio || 1;
    if (d > 2) d = 2;   /* 读层是细线与光斑，2× 足够；4K 下再乘上去只是白烧填充 */
    if ((r.w || r.width) === W && (r.h || r.height) === H && d === dpr) return;
    W = r.w > 0 ? r.w : r.width; H = r.h > 0 ? r.h : r.height; dpr = d;
    cv.width = Math.max(1, Math.round(W * dpr));
    cv.height = Math.max(1, Math.round(H * dpr));
    st.w = cv.width; st.h = cv.height;
  }

  function show(v) {
    if (v === on) return;
    on = v;
    cv.hidden = !v;
  }

  function mount(h, el) {
    if (!h) return;
    if (cv && host === h) { ref = el || ref; return; }
    if (cv && cv.parentNode) cv.parentNode.removeChild(cv);
    host = h; ref = el || null;
    cv = doc.createElement('canvas');
    cv.className = 'sky-dial-fx';
    cv.setAttribute('aria-hidden', 'true');
    cv.hidden = true;   /* 位置 / 尺寸 / 穿透全在 css/sky-dial.css，不写行内样式 */
    /* 压在刻度盘上方、标签下方：插在 disc 元素之后 */
    if (ref && ref.nextSibling) host.insertBefore(cv, ref.nextSibling); else host.appendChild(cv);
    cx = cv.getContext('2d');
    W = H = 0; on = false;
    st.mounts++;
  }

  function hide() {
    if (!cv) return;
    if (on) { cx.clearRect(0, 0, cv.width, cv.height); st.hides++; }
    show(false);
    lastX = null; vSlot = 0;
  }

  /* 一格刻度：从刻度环沿径向往外的一小段 */
  function tick(o, x, r0, r1, col, wpx) {
    var a = o.ang(x), p = o.pj(r0, a), q = o.pj(r1, a);
    if (!p || !q) return;
    cx.strokeStyle = col; cx.lineWidth = wpx;
    cx.beginPath(); cx.moveTo(p[0], p[1]); cx.lineTo(q[0], q[1]); cx.stroke();
  }

  /* 彗尾：沿刻度环从 x 往 x+dx 方向铺一串短段，越远越淡（尾在指针身后，dx 与速度反号） */
  function tail(o, x, dx, al) {
    var i, t0, t1, p, q, a;
    cx.lineCap = 'round';
    for (i = 0; i < TAILN; i++) {
      t0 = x + dx * i / TAILN; t1 = x + dx * (i + 1) / TAILN;
      if (t1 < -0.5 || t1 > o.n - 0.5) break;
      p = o.pj(o.rB, o.ang(t0)); q = o.pj(o.rB, o.ang(t1));
      if (!p || !q) continue;
      a = Math.pow(1 - i / TAILN, 1.7) * 0.5 * al;
      cx.strokeStyle = hex(TK().C.BRASS_HOT, a);
      cx.lineWidth = 2.4 * (1 - i / TAILN) + 0.5;
      cx.beginPath(); cx.moveTo(p[0], p[1]); cx.lineTo(q[0], q[1]); cx.stroke();
    }
    cx.lineCap = 'butt';
  }

  function draw(o) {
    var T = TK(), C, al, i, x, k, d, span, r0, r1, glow, p;
    if (!cv || !o || !T) return;
    C = T.C;
    al = +o.al || 0;
    if (!(al > 0.004) || o.slot == null && !o.hot) { hide(); return; }
    size(o); show(true);
    st.draws++;
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx.clearRect(0, 0, W, H);

    x = o.slot != null ? o.slot : (o.hot && o.hot.slot != null ? o.hot.slot : null);
    if (x == null) { hide(); return; }
    r0 = o.rB; r1 = o.rB + (o.tk || 0.03) * LIFT;
    /* 拖动中收窄：手指所在那几格更「聚」，松开后摊开成一片淡光 */
    span = SPAN[0] + (SPAN[1] - SPAN[0]) * (+o.gk || 0);

    /* 刻度光斑：以手指格位为中心，两侧按格距高斯衰减 —— low 档跳过，只留指针亮痕 */
    if (!o.low) {
      /* 格太密（大书一格 ~2 px）时隔 stp 格取一道，刻痕间距保持 ≥ 4 px，不糊成一片斜纹 */
      p = o.pj(o.rB, o.ang(x)); d = o.pj(o.rB, o.ang(x + 1));
      var stp = p && d ? Math.max(1, Math.ceil(4 / Math.max(0.25, Math.hypot(p[0] - d[0], p[1] - d[1])))) : 1, x0 = Math.round(x / stp) * stp;
      k = Math.ceil(span * 2);
      for (i = -k; i <= k; i++) {
        d = Math.abs(i);
        glow = Math.exp(-(d * d) / (2 * span * span));
        if (glow < 0.03) continue;
        var xi = x0 + i * stp;
        if (xi < -0.5 || xi > o.n - 0.5) continue;
        tick(o, xi, r0, r1, hex(C.BRASS, (0.10 + 0.55 * glow) * al), 1 + 0.7 * glow);
      }
    }

    /* 彗尾：指针走得越快，身后沿刻度环拖出的一截越长（与揭幕彗头、牵引丝笔尖彗星同一语汇）。
       速度由相邻两帧的格位差 / dt 得到，只在拖动 / 甩动 / 落定这几个动着的相里出；low 档与减弱动效不画。 */
    if (lastX != null && o.dt > 0) {
      vSlot += ((x - lastX) / o.dt - vSlot) * Math.min(1, o.dt / 0.08);
    }
    lastX = x;
    if (!o.low && !o.red && Math.abs(vSlot) > 0.8) {
      tail(o, x, Math.max(-TAILMAX, Math.min(TAILMAX, -vSlot * TAILK)), al);
    }

    /* 指针亮痕：位置直接用宿主给的 slot（拖过首尾时它带着软限位回弹量，看得出顶住了） */
    tick(o, x, r0 - (o.tk || 0.03) * 0.45, r1 + (o.tk || 0.03) * 0.5,
      hex(o.drag ? C.BRASS_HOT : C.BRASS, (0.55 + 0.4 * (+o.gk || 0)) * al), o.drag ? 2.1 : 1.6);
    if (!o.low) {
      p = o.pj(o.rB, o.ang(x));
      if (p) {
        glow = cx.createRadialGradient(p[0], p[1], 0, p[0], p[1], 13 + 9 * (+o.gk || 0));
        glow.addColorStop(0, hex(C.BRASS_HOT, 0.38 * al));
        glow.addColorStop(1, hex(C.BRASS_HOT, 0));
        cx.fillStyle = glow;
        cx.beginPath(); cx.arc(p[0], p[1], 13 + 9 * (+o.gk || 0), 0, 6.2832); cx.fill();
      }
    }

    /* 落点刻痕：还在转时才画（停在格心 = 与指针重合） */
    if (o.near && Math.abs(o.near(x) - x) > 0.15) tick(o, o.near(x), r0, r1, hex(C.BRASS_HOT, 0.75 * al), 1.3);
  }

  g.CLSkyDialFx = {
    mount: mount,
    draw: draw,
    hide: hide,
    stats: function () {
      return { fxMounted: !!cv, fxOn: on, fxDraws: st.draws, fxHides: st.hides, fxW: st.w, fxH: st.h, fxMounts: st.mounts, fxVel: +vSlot.toFixed(2), fxTail: +Math.min(TAILMAX, Math.abs(vSlot) * TAILK).toFixed(2) };
    }
  };
})(window);
