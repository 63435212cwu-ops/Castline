/* Castline · abyss-breath.js — 三图唯一呼吸相位总线（CORE · S3）
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§4 S3。
 *
 * ── 为什么需要它（第三批实测的 A/B 基线，不是读码推测） ────────────────────
 * 接线前同屏采样四拍（demo=1&probe=1&tree=1，间隔 2 s），读数：
 *
 *   拍   performance.now()/1000   场景 tAnim    树 sway t    雷达 lampPhase 反推 t
 *   1          11.093            0.1879        0.188           19.08
 *   2          13.252            0.2879        0.288           19.08→ 每拍 +2.62 s/维
 *   3          15.253            0.7203        0.720            —
 *   4          17.865            1.0703        1.070            —
 *
 * 结论（三条，与总纲的判断部分吻合、部分更严重）：
 *   a) **树与场景已经同相**（swayT 与 tAnim 逐拍相等，差 < 0.001 s）。总纲
 *      「行星点 uBreath 与树行波各自为政」这一条**不成立**——它们同一个 tAnim。
 *   b) **雷达与场景相差 14.4 s 且持续发散**：Δ = nowSec − tAnim 从 10.905 s
 *      一路涨到 16.795 s（6.77 s 内漂 +5.89 s）。根因是雷达的 auraPhase 读
 *      `performance.now()/1000`（radar.js:39 nowSec），从**导航起点**起算；
 *      而场景 tAnim 是 rAF 循环里累加的 dt（scene.js:4280/4288），从**循环起点**
 *      起算并按 0.05 s 上限钳制。两者一旦有加载耗时或掉帧就永久错开。
 *   c) 雷达的 CSS 写入口（radar.js:126 tickClocks）在右坞挂载前 idle，
 *      挂载后每帧写 --rd-breath；本总线接管它的 t，即接管全部表盘相位。
 *
 * ── 契约 ────────────────────────────────────────────────────────────────────
 *   t 的**唯一权威源**是渲染主时钟（scene.js 的 tAnim）。场景每帧调 pub(tAnim)
 *   声明主权；总线在 PUB_TTL 内采纳它。场景缺席（雷达独立页 / 场景未接线）时，
 *   总线用自己的 rAF 累加时钟——与旧 nowSec() 同为「墙钟起算」，行为等价。
 *   因此：三图的呼吸是同一个 t 的同一个函数 ⇒ 波谷时间戳偏差恒 = 0。
 *
 * ── 守空与回退 ──────────────────────────────────────────────────────────────
 *   本文件缺失时：radar.js 的 auraPhase/lampPhase 走原 nowSec() 分支，逐位等同
 *   接线前；scene.js 的 pub 调用被 typeof 守卫吃掉。全部改动可整体回退。
 *
 * ES5 IIFE。必须在 scene.js / radar.js 之前加载（index.html 已置前）。
 * ============================================================================
 */
(function (g) {
  'use strict';
  if (!g) return;

  var C = {
    BREATH_CYCLE: 9.4,
    LAMP_SLOT: 2.62,
    IRIS_PER: 37.6,
    BLINK_PER: 28.3,
    KEYS: 8
  };

  var PUB_TTL = 1500;
  var pubT = null, pubAt = -1e9, handoff = false;
  var localT = 0, lastWall = -1;
  var frameNo = 0, rafId = 0, running = false;
  var subs = [];

  var TAU = Math.PI * 2;
  function wallMs() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  }
  function pubFresh(w) { return pubT !== null && (w - pubAt) <= PUB_TTL; }

  function tNow() {
    var w = wallMs();
    if (pubFresh(w)) { handoff = false; lastWall = -1; return pubT; }
    if (!handoff && pubT !== null) { localT = pubT; handoff = true; }
    if (lastWall < 0) lastWall = w;
    var dt = (w - lastWall) / 1000; lastWall = w;
    if (!(dt > 0) || dt > 0.25) dt = 0;
    localT += dt;
    return localT;
  }

  function snap() {
    var t = tNow();
    var bp = (t % C.BLINK_PER) / C.BLINK_PER;
    return {
      t: t,
      breath: 0.5 + 0.5 * Math.sin(t * TAU / C.BREATH_CYCLE),
      iris: 0.5 + 0.5 * Math.sin(t * TAU / C.IRIS_PER),
      blink: bp < 0.06 ? Math.exp(-Math.pow((bp - 0.03) / 0.014, 2)) : 0,
      phase: (t / C.LAMP_SLOT) % C.KEYS,
      frame: frameNo,
      source: pubFresh(wallMs()) ? 'render-master' : 'local'
    };
  }

  function sampleBreath(amp, phaseOffset, base) {
    var t = tNow();
    var pOff = (typeof phaseOffset === 'number' && isFinite(phaseOffset)) ? phaseOffset : 0;
    var ph = (t + pOff) * TAU / C.BREATH_CYCLE;
    var raw = 0.5 + 0.5 * Math.sin(ph);
    if (typeof amp !== 'number' || !isFinite(amp)) return raw;
    var b = (typeof base === 'number' && isFinite(base)) ? base : 0;
    return b + amp * raw;
  }

  function envelope(amp, phaseOffset) {
    var a = (typeof amp === 'number' && isFinite(amp)) ? amp : 0.14;
    return 1 - a + a * sampleBreath(1, phaseOffset, 0);
  }

  function lampAt(i, ph, n, wide, gain) {
    var d = (i - ph) % n; if (d < 0) d += n; if (d > n / 2) d -= n;
    var x = Math.abs(d) / (wide || 1.34);
    if (x >= 1) return 0;
    return Math.pow(Math.cos(x * Math.PI / 2), (gain || 1.55) * 2);
  }

  function pub(t) {
    t = +t;
    if (!isFinite(t)) return false;
    pubT = t; pubAt = wallMs();
    return true;
  }
  function frame() {
    frameNo++;
    var s = snap(), i;
    for (i = 0; i < subs.length; i++) {
      try { subs[i](s); } catch (e) {  }
    }
    return s;
  }
  function subscribe(fn) {
    if (typeof fn !== 'function') return function () {};
    subs.push(fn);
    return function () { var i = subs.indexOf(fn); if (i >= 0) subs.splice(i, 1); };
  }
  function skyOwned() { return !!(g.CLSky && g.CLSky.enabled && g.CLSky.enabled()); }
  function loop() {
    if (!running) return;
    if (skyOwned()) { running = false; rafId = 0; return; }
    frame();
    if (typeof g.requestAnimationFrame === 'function') rafId = g.requestAnimationFrame(loop);
  }
  function start() { if (!running) { running = true; loop(); } return running; }
  function stop() { running = false; if (rafId && g.cancelAnimationFrame) g.cancelAnimationFrame(rafId); rafId = 0; return !running; }

  g.CLAbyssBreath = {
    name: 'abyss-breath',
    version: '1',
    C: C,
    pub: pub,
    snap: snap,
    t: function () { return tNow(); },
    breath: function (amp, phaseOffset, base) {
      if (amp === undefined && phaseOffset === undefined) return snap().breath;
      return sampleBreath(amp, phaseOffset, base);
    },
    sampleBreath: sampleBreath,
    envelope: envelope,
    phase: function () { return snap().phase; },
    lampAt: lampAt,
    frame: frame,
    subscribe: subscribe,
    start: start,
    stop: stop,
    reset: function () { pubT = null; pubAt = -1e9; handoff = false; localT = 0; lastWall = -1; frameNo = 0; },
    audit: function () {
      var s = snap();
      return { name: 'abyss-breath', version: '1', source: s.source, t: s.t, breath: s.breath,
        phase: s.phase, frame: frameNo, subs: subs.length, running: running, constants: C,
        governor: !!(g.CLAbyssGovernance) };
    }
  };

  if (typeof g.requestAnimationFrame === 'function') start();
})(typeof window !== 'undefined' ? window : this);
