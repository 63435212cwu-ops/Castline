/*! 卡片叠的指针视差 — 剧情卡叠与分组卡叠共用
 * @role cards3d
 * @owns js/sky/sky-cards-3d.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * CLSkyCards3D = { stats, dispose }
 *
 * 指针在叠上移动时，整叠绕 X / Y 轻转：只往视口元素上写 --skc3-tx / --skc3-ty 两个角度，
 * 具体怎么转由 css/sky-cards-3d.css 决定（卡各自的 Z 不同，于是层与层的屏幕位移不同 = 层间视差）。
 * 角度走阻尼弹簧（CLSkyTokens.SPRING）：跟手用 follow（临界阻尼），指针离开用 back（欠阻尼，回正时轻轻过冲再停）——
 * 与星体牵引 / 拨盘同一套弹簧语汇；积分挂在场景帧钩子上，只在弹簧没停稳时写变量，停稳即清掉变量、钩子空转。
 * 静止即读字：纵深系数 --skc3-z（0 = 平面，1 = 全纵深）也走 follow 弹簧——指针在叠上移动时展开到 1，
 * 停下 IDLE 秒或离开就收回 0。透视下任何 Z ≠ 0 都是非整数缩放、文字被重采样发糊；收回 0 后卡片全是恒等变换，按像素栅格清晰。
 *
 * 纪律：ES5；不开 rAF / setInterval（pointermove 只改目标角，逐帧积分挂 CLScene.current.registerFrameHook）；
 * 不碰宿主 JS —— 用 document 级委托找 .skd-deck__viewport，两叠都不用改自己的代码；
 * 只读框一次并缓存（resize / 滚动才作废），逐次 pointermove 不读布局；
 * 减弱动效 / body.skylab-still / low 档：整个不挂（CSS 那边也各自退回平面，两道都兜住）。
 */
(function (g) {
  'use strict';
  var doc = document, SEL = '.skd-deck__viewport';
  var host = null, rect = null, on = false, moves = 0;
  /* 弹簧：ax / ay 各一个 {x, v}（度）；el = 正在回弹的那个视口（指针离开后 host 已空，el 还要弹完） */
  var ax = { x: 0, v: 0 }, ay = { x: 0, v: 0 }, tx = 0, ty = 0, el = null, live = false, hooked = null, offFrame = null, lowOn = false, frames = 0, flips = 0;
  var az = { x: 0, v: 0 }, tz = 0, idle = 0, rests = 0, IDLE = 0.7;   /* 纵深系数弹簧；指针停 IDLE 秒 → 收回平面读字 */

  function T() { return g.CLSkyTokens; }
  function tok() { var t = T() && T().CARD3D; return t || { tilt: 3.2 }; }
  function spr(k) { var s = T() && T().SPRING && T().SPRING[k]; return s || (k === 'back' ? { w: 11, z: 0.38 } : { w: 30, z: 1 }); }
  /* 卡片跟随真实场景档位；旧 data-tier 仍是显式展示策略，不改写全局属性。 */
  function sceneLow() {
    var s = g.CLScene && g.CLScene.current, q = s && s.quality ? s.quality() : null;
    return !!(q && q.degrade >= 2);
  }
  function syncLow() {
    var low = sceneLow();
    if (doc.body && low !== lowOn) { doc.body.classList.toggle('sky-cards-low', low); lowOn = low; }
    return low;
  }
  function still() {
    if (sceneLow()) { return true; }
    if (T() && T().reduced && T().reduced()) { return true; }
    if (doc.body && doc.body.classList.contains('skylab-still')) { return true; }
    var d = doc.documentElement.getAttribute('data-tier');
    return d === 'low';
  }
  var clamp = g.CLSkyUtil.clamp;

  function clear(el) {
    if (!el) { return; }
    el.style.removeProperty('--skc3-tx');
    el.style.removeProperty('--skc3-ty');
    el.style.removeProperty('--skc3-oy');
    el.style.removeProperty('--skc3-z');
  }
  /* 剧情卡叠的倾斜转轴放在可见段中间（spacer 高 = 全表，默认 50% 会把离轴很远的卡甩出大 Z）：滚动 / 首次读框时写一次 */
  function origin(el) { if (el && rect) { el.style.setProperty('--skc3-oy', (el.scrollTop + rect.height / 2).toFixed(0) + 'px'); } }
  /* 停：清变量、弹簧归零（换叠 / 降级 / 弹完时） */
  function zero() { ax.x = ax.v = ay.x = ay.v = az.x = az.v = 0; }
  function settle() { clear(el); el = null; live = false; zero(); tx = ty = tz = 0; }
  /* 指针离开：目标回 0，交给 back 弹簧弹回去；没有场景帧钩子可挂时直接回正 */
  function drop() { host = null; rect = null; tx = ty = tz = 0; if (!hooked) { settle(); } }
  function hook() {
    var sc = g.CLScene && g.CLScene.current;
    if (!sc || !sc.registerFrameHook || sc === hooked) { return; }
    if (offFrame) { offFrame(); }
    hooked = sc; offFrame = sc.registerFrameHook(frame);
  }
  function step(s, to, k, h) {
    g.CLSkyUtil.spring(s, to, k.w, k.z, h);
  }
  function frame(dt) {
    syncLow();
    if (!live || !el) { return; }
    if (still()) { settle(); return; }
    dt = Math.min(Math.max(+dt || 0, 0), 0.1);
    if (host) { idle += dt; if (idle > IDLE) { tx = ty = tz = 0; } }
    var rest = !host || idle > IDLE, k = spr(rest ? 'back' : 'follow'), kz = spr('follow'), n, h, i, sx = ax.x;
    n = Math.max(1, Math.ceil(dt * 240)); h = dt / n;   /* 细分到 ≤ 1/240 s，掉帧时也稳 */
    for (i = 0; i < n; i++) { step(ax, tx, k, h); step(ay, ty, k, h); step(az, tz, kz, h); }   /* 纵深走临界阻尼：不过冲，免得 Z 反号 */
    if (rest && sx !== 0 && (sx > 0) !== (ax.x > 0)) { flips++; }   /* 回正时越过 0 = 过冲（测试读它，证明是弹簧不是缓动） */
    frames++;
    if (rest && Math.abs(ax.x) < 0.01 && Math.abs(ay.x) < 0.01 && Math.abs(ax.v) < 0.05 && Math.abs(ay.v) < 0.05 && Math.abs(az.x) < 0.002 && Math.abs(az.v) < 0.02) {
      rests++;
      if (!host) { settle(); } else { clear(el); zero(); live = false; }   /* 指针还在叠上但停住了：回平面，等下一次移动 */
      return;
    }
    el.style.setProperty('--skc3-tx', ax.x.toFixed(2) + 'deg');
    el.style.setProperty('--skc3-ty', ay.x.toFixed(2) + 'deg');
    el.style.setProperty('--skc3-z', az.x.toFixed(3));
  }

  function onMove(e) {
    if (still()) { if (el) { settle(); } host = null; rect = null; return; }
    var t = e.target && e.target.closest ? e.target.closest(SEL) : null;
    if (!t) { if (host) { drop(); } return; }
    if (t !== host) { host = t; rect = null; }
    if (el !== t) { settle(); el = t; }
    if (!rect) { rect = t.getBoundingClientRect(); if (rect.width > 0 && rect.height > 0) { origin(t); } }   /* 一次布局读，之后只改目标角 */
    if (!(rect.width > 0 && rect.height > 0)) { rect = null; return; }
    var mx = clamp((e.clientX - rect.left) / rect.width, 0, 1) - 0.5;
    var my = clamp((e.clientY - rect.top) / rect.height, 0, 1) - 0.5;
    var k = +tok().tilt || 3.2;
    /* 指针往右 → 叠绕 Y 正转（右侧压向远处）；指针往下 → 绕 X 反转（下沿抬起），与真实倾斜同向 */
    tx = mx * 2 * k; ty = -my * 2 * k; tz = 1; idle = 0;
    hook(); live = true; flips = 0; moves++;
    if (!hooked) { ax.x = tx; ay.x = ty; az.x = 1; t.style.setProperty('--skc3-tx', tx.toFixed(2) + 'deg'); t.style.setProperty('--skc3-ty', ty.toFixed(2) + 'deg'); t.style.setProperty('--skc3-z', '1'); }
  }
  function onOut(e) {
    if (!host) { return; }
    var to = e.relatedTarget, inside = to && to.closest && to.closest(SEL) === host;
    if (!inside) { drop(); }
  }
  function onScroll(e) { if (el && e.target === el && (rect || live)) { if (!rect) { rect = el.getBoundingClientRect(); } origin(el); } }
  function onResize() { rect = null; }
  function onGraph() { hook(); syncLow(); }

  function attach() {
    if (on) { return; }
    on = true;
    doc.addEventListener('cl:graph-ready', onGraph, false);
    onGraph();
    doc.addEventListener('pointermove', onMove, { passive: true });
    doc.addEventListener('pointerout', onOut, { passive: true });
    doc.addEventListener('scroll', onScroll, true);
    g.addEventListener('resize', onResize, { passive: true });
  }
  function dispose() {
    if (!on) { return; }
    on = false;
    doc.removeEventListener('cl:graph-ready', onGraph, false);
    if (offFrame) { offFrame(); offFrame = null; } hooked = null;
    if (doc.body) { doc.body.classList.remove('sky-cards-low'); } lowOn = false;
    doc.removeEventListener('pointermove', onMove, { passive: true });
    doc.removeEventListener('pointerout', onOut, { passive: true });
    doc.removeEventListener('scroll', onScroll, true);
    g.removeEventListener('resize', onResize, { passive: true });
    host = null; rect = null; settle();
  }

  attach();

  g.CLSkyCards3D = {
    stats: function () {
      var e = el || host;
      return { on: on, host: host ? (host.className || '') : null, moves: moves, still: still(), live: live, hooked: !!hooked, frames: frames, flips: flips, rests: rests,
        depth: +az.x.toFixed(3), idle: +idle.toFixed(2), target: [+tx.toFixed(2), +ty.toFixed(2)],
        tx: e ? e.style.getPropertyValue('--skc3-tx') : '', ty: e ? e.style.getPropertyValue('--skc3-ty') : '', z: e ? e.style.getPropertyValue('--skc3-z') : '' };
    },
    dispose: dispose
  };
})(window);
